"""Shared single-shot runtime helper for the simulation prototypes.

This module exists for the four ``code_optimization`` SOP prototype scripts
under ``openteam.use_cases``.  It centralises:

1. The **workspace root resolution** — where on disk per-workstream artifacts
   and run logs live.  Resolution order (most specific first):

   * ``--runtime-root <path>`` CLI flag (each script wires its own)
   * ``AI_EMPLOYEE_HOME`` environment variable
   * ``~/.ai-employee`` (default)

   Under that root, the canonical per-workstream layout is::

       <root>/projects/<workstream-slug>/
       ├── artifacts/                          (durable, latest-only)
       │   ├── codebase_documentation/
       │   ├── system_and_signals_documentation/
       │   └── proposals/
       └── _runtime/                           (full history, debug-only)
           ├── codebase_investigation/run_<ts>_<uuid>/...
           ├── system_and_signals_investigation/run_<ts>_<uuid>/...
           ├── research_and_propose/run_<ts>_<uuid>/...
           └── proposal_implementation/run_<ts>_<uuid>/...

2. The **single-shot run workspace dataclass** (``SingleShotRunWorkspace``)
   describing every path a per-call helper might need.

3. **Auto-discovery** of the latest artifacts for a given phase, with
   backward-compat fallbacks for the legacy in-package layouts.

4. A **sentinel parser** (``parse_sentinel``) and an **artifact promoter**
   (``promote_to_artifacts``) that mirrors a successful run's docs into the
   ``artifacts/<phase-folder>/`` directory (overwriting the previous copy).

Long-running script 4 (``proposal_implementation``) has its own richer
``runtime.py`` for many concurrent calls; this module is for single-shot
scripts (1-3).  The two share the workspace-root resolver below.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import re
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Workspace root resolution
# ---------------------------------------------------------------------------

DEFAULT_AI_EMPLOYEE_HOME = Path("~/.ai-employee").expanduser()
ENV_AI_EMPLOYEE_HOME = "AI_EMPLOYEE_HOME"

# Maps each phase to its canonical artifacts sub-folder.  These names are
# user-visible and are kept human-friendly.
PHASE_TO_ARTIFACTS_FOLDER: dict[str, str] = {
    "codebase": "codebase_documentation",
    "signals": "system_and_signals_documentation",
    "epic_creation": "proposals",
    # ``proposal_implementation`` is intentionally absent — its outputs land
    # in Jira+Bitbucket directly, not in this artifacts/ tree.
}


def workstream_slug_from_codebase(codebase: Path) -> str:
    """Derive a kebab-case workstream slug from the codebase path basename."""
    base = codebase.resolve().name
    base = re.sub(r"[^A-Za-z0-9]+", "-", base).strip("-").lower()
    return base or "code-optimization"


def resolve_ai_employee_home(override: Path | None = None) -> Path:
    """Pick the AI-employee root with override > env > default precedence."""
    if override is not None:
        return override.expanduser().resolve()
    env_val = os.environ.get(ENV_AI_EMPLOYEE_HOME)
    if env_val:
        return Path(env_val).expanduser().resolve()
    return DEFAULT_AI_EMPLOYEE_HOME


def resolve_project_root(
    codebase: Path,
    *,
    workstream_slug: str | None = None,
    runtime_root_override: Path | None = None,
) -> Path:
    """Return ``<ai-employee-home>/projects/<workstream>/`` for a codebase."""
    slug = workstream_slug or workstream_slug_from_codebase(codebase)
    home = resolve_ai_employee_home(runtime_root_override)
    project_root = home / "projects" / slug
    project_root.mkdir(parents=True, exist_ok=True)
    return project_root


# ---------------------------------------------------------------------------
# Single-shot run workspace (used by scripts 1-3)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SingleShotRunWorkspace:
    """Per-run workspace producing a single ``call_01_<phase>`` sub-dir.

    Important paths:

    * ``run_dir`` — full history root for this one run (``_runtime/<script>/run_*/``)
    * ``call_dir`` — single-call sub-dir (``call_01_<phase>/``)
    * ``docs_dir`` — the inferencer's working ``docs/`` output
    * ``artifacts_dir`` — destination for the post-run mirror (``artifacts/<phase-folder>/``)
    """

    project_root: Path
    run_dir: Path
    call_dir: Path
    docs_dir: Path
    prompt_path: Path
    stream_log_path: Path
    clean_output_path: Path
    phase_name: str
    artifacts_dir: Path
    run_meta_path: Path
    call_meta_path: Path

    # -- meta helpers ---------------------------------------------------

    def write_run_meta(self, extra: dict[str, Any] | None = None) -> None:
        meta: dict[str, Any] = {
            "phase": self.phase_name,
            "created_at_utc": dt.datetime.utcnow().isoformat() + "Z",
            "schema": "single_shot_run_v1",
            "project_root": str(self.project_root),
        }
        if extra:
            meta.update(extra)
        self.run_meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    def write_call_meta(self, extra: dict[str, Any] | None = None) -> None:
        meta: dict[str, Any] = {
            "phase": self.phase_name,
            "call_index": 1,
            "created_at_utc": dt.datetime.utcnow().isoformat() + "Z",
            "schema": "single_shot_call_v1",
        }
        if extra:
            meta.update(extra)
        self.call_meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def setup_run_workspace(
    *,
    codebase: Path,
    phase_name: str,
    script_dir_name: str,
    workstream_slug: str | None = None,
    runtime_root_override: Path | None = None,
) -> SingleShotRunWorkspace:
    """Create the canonical single-shot run + call directory layout.

    Parameters
    ----------
    codebase
        Absolute path of the codebase being optimised; used to derive the
        workstream slug (unless ``workstream_slug`` is given).
    phase_name
        Short slug used in the call-dir name (``codebase``, ``signals``,
        ``epic_creation``).  Must be a key in ``PHASE_TO_ARTIFACTS_FOLDER``.
    script_dir_name
        The script's package directory name (``codebase_investigation``,
        ``system_and_signals_investigation``, ``research_and_propose``).
        Used as the per-script _runtime sub-folder.
    workstream_slug
        Optional explicit override for the workstream slug.
    runtime_root_override
        Optional CLI-flag override that takes precedence over the
        ``AI_EMPLOYEE_HOME`` env var and the default ``~/.ai-employee``.
    """
    if phase_name not in PHASE_TO_ARTIFACTS_FOLDER:
        raise ValueError(
            f"Unknown phase_name {phase_name!r}; expected one of "
            f"{sorted(PHASE_TO_ARTIFACTS_FOLDER)}"
        )

    project_root = resolve_project_root(
        codebase,
        workstream_slug=workstream_slug,
        runtime_root_override=runtime_root_override,
    )

    ts = dt.datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S")
    run_id = f"run_{ts}_{uuid.uuid4().hex[:8]}"

    run_dir = project_root / "_runtime" / script_dir_name / run_id
    call_dir = run_dir / f"call_01_{phase_name}"
    docs_dir = call_dir / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    artifacts_dir = project_root / "artifacts" / PHASE_TO_ARTIFACTS_FOLDER[phase_name]

    ws = SingleShotRunWorkspace(
        project_root=project_root,
        run_dir=run_dir,
        call_dir=call_dir,
        docs_dir=docs_dir,
        prompt_path=call_dir / "prompt.md",
        stream_log_path=call_dir / "stream.log",
        clean_output_path=call_dir / "clean_output.md",
        phase_name=phase_name,
        artifacts_dir=artifacts_dir,
        run_meta_path=run_dir / "_run.json",
        call_meta_path=call_dir / "_meta.json",
    )
    ws.write_run_meta()
    ws.write_call_meta()
    logger.info("Workspace ready (project_root=%s, run_dir=%s)", project_root, run_dir)
    return ws


# ---------------------------------------------------------------------------
# Artifact promotion (latest-only mirroring)
# ---------------------------------------------------------------------------


def promote_to_artifacts(ws: SingleShotRunWorkspace) -> Path:
    """Copy the run's ``docs/`` into ``artifacts/<phase-folder>/`` (latest-only).

    Wipes the destination first (each phase's artifacts dir holds only the
    most-recent successful run's output).  Adds a tiny ``_provenance.json``
    so consumers can trace the artifact back to its run_dir / commit /
    timestamp.

    Returns the destination directory.
    """
    src = ws.docs_dir
    dst = ws.artifacts_dir

    if not src.exists():
        raise FileNotFoundError(f"Source docs dir does not exist: {src}")

    # Wipe destination if present, then copy fresh (no history retained).
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)

    provenance = {
        "phase": ws.phase_name,
        "promoted_at_utc": dt.datetime.utcnow().isoformat() + "Z",
        "source_run_dir": str(ws.run_dir),
        "source_call_dir": str(ws.call_dir),
        "schema": "artifact_provenance_v1",
    }
    (dst / "_provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")

    logger.info("Promoted artifacts: %s -> %s", src, dst)
    return dst


# ---------------------------------------------------------------------------
# Auto-discovery (with backward compatibility)
# ---------------------------------------------------------------------------


def autodiscover_phase_artifacts(
    *,
    codebase: Path,
    phase_name: str,
    workstream_slug: str | None = None,
    runtime_root_override: Path | None = None,
    legacy_in_package_runtime_root: Path | None = None,
) -> Path | None:
    """Find the latest artifacts directory for a given phase.

    Resolution order:

    1. ``<project_root>/artifacts/<phase-folder>/`` (canonical new layout)
    2. Most-recent ``run_*/call_01_*/docs/`` under
       ``<project_root>/_runtime/<script>/`` (in case a run didn't promote)
    3. Most-recent ``run_*/call_01_*/docs/`` under
       ``legacy_in_package_runtime_root`` (the old in-package
       ``test/openteam/use_cases/<script>/_runtime/`` location)
    4. Most-recent ``run_*/docs/`` under the same legacy root (oldest layout)

    Returns ``None`` if nothing is found.
    """
    if phase_name not in PHASE_TO_ARTIFACTS_FOLDER:
        raise ValueError(f"Unknown phase_name {phase_name!r}")

    project_root = resolve_project_root(
        codebase,
        workstream_slug=workstream_slug,
        runtime_root_override=runtime_root_override,
    )

    # 1. Canonical: artifacts/<phase-folder>/
    canonical = project_root / "artifacts" / PHASE_TO_ARTIFACTS_FOLDER[phase_name]
    if canonical.is_dir() and any(canonical.iterdir()):
        return canonical

    # 2. Project _runtime/<phase script>/run_*/call_01_*/docs/ — most recent
    #    Script-dir name lookup table: phase -> script dir
    phase_to_script_dir = {
        "codebase": "codebase_investigation",
        "signals": "system_and_signals_investigation",
        "epic_creation": "research_and_propose",
    }
    runtime_root = project_root / "_runtime" / phase_to_script_dir[phase_name]
    found = _latest_call_or_docs(runtime_root)
    if found is not None:
        return found

    # 3-4. Legacy in-package _runtime/
    if legacy_in_package_runtime_root is not None:
        found = _latest_call_or_docs(legacy_in_package_runtime_root)
        if found is not None:
            return found

    return None


def _latest_call_or_docs(runtime_root: Path) -> Path | None:
    """Find the newest ``run_*/call_01_*/docs/`` (or ``run_*/docs/`` legacy)."""
    if not runtime_root.exists():
        return None
    candidates: list[tuple[float, Path]] = []
    for run_dir in runtime_root.glob("run_*"):
        # Canonical layout (post-unification): run_*/call_01_*/docs/
        for call_dir in run_dir.glob("call_*"):
            docs = call_dir / "docs"
            if docs.is_dir():
                candidates.append((call_dir.stat().st_mtime, docs))
        # Legacy flat: run_*/docs/
        legacy_docs = run_dir / "docs"
        if legacy_docs.is_dir():
            candidates.append((run_dir.stat().st_mtime, legacy_docs))
    if not candidates:
        return None
    candidates.sort(key=lambda c: c[0], reverse=True)
    return candidates[0][1]


# Back-compat alias for the previous helper signature (used by scripts 2/3 before
# this rewrite).  Scripts that depend on the new path-aware version should call
# ``autodiscover_phase_artifacts`` directly.
def autodiscover_latest_docs(runtime_root: Path) -> Path | None:
    """Legacy entry point — use ``autodiscover_phase_artifacts`` instead."""
    return _latest_call_or_docs(runtime_root)


# ---------------------------------------------------------------------------
# Sentinel parsing
# ---------------------------------------------------------------------------


def parse_sentinel(clean_output: str) -> str:
    """Extract the final ``STATUS:`` line, defaulting to ``STATUS: UNKNOWN``."""
    for line in reversed(clean_output.splitlines()):
        if line.startswith("STATUS:"):
            return line.strip()
    return "STATUS: UNKNOWN"


def sentinel_indicates_success(sentinel: str, expected_complete_token: str) -> bool:
    """Return True iff the sentinel starts with ``STATUS: <expected_complete_token>``."""
    prefix = f"STATUS: {expected_complete_token}"
    return sentinel.startswith(prefix)


__all__: Iterable[str] = (
    "DEFAULT_AI_EMPLOYEE_HOME",
    "ENV_AI_EMPLOYEE_HOME",
    "PHASE_TO_ARTIFACTS_FOLDER",
    "SingleShotRunWorkspace",
    "autodiscover_latest_docs",
    "autodiscover_phase_artifacts",
    "parse_sentinel",
    "promote_to_artifacts",
    "resolve_ai_employee_home",
    "resolve_project_root",
    "sentinel_indicates_success",
    "setup_run_workspace",
    "workstream_slug_from_codebase",
)
