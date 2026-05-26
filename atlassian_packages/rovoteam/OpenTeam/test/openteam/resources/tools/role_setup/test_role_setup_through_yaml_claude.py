"""Run role_setup.yaml end-to-end with ClaudeCodeCli substituted for
RovoChat/RovoDevCLI via runtime overrides — mirrors
test_create_role_through_yaml_claude.py pattern.

Architecture (nested BTA):
    outer BTA
      breakdown                       (RovoDevCLI -> ClaudeCodeCLI)
      worker_factory:
        skill_tool_creation           (inner BTA via _import_)
          breakdown                   (RovoDevCLI -> ClaudeCodeCLI)
          worker_factory:
            skill_tool_creation_research        (RovoChat -> ClaudeCodeCLI)
            skill_tool_creation_investigation   (RovoDevCLI -> ClaudeCodeCLI)
          aggregator                  (RovoDevCLI -> ClaudeCodeCLI)
        skill_tool_association        (RovoDevCLI -> ClaudeCodeCLI)
      aggregator                      (RovoDevCLI -> ClaudeCodeCLI)

Total: 8 inferencer slots.

Artifacts persist under `_runtime/<TIMESTAMP>/`.

Usage:
    cd OpenTeam
    python -m test.openteam.resources.tools.role_setup.test_role_setup_through_yaml_claude
"""

import asyncio
import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Bootstrap sys.path for `python -m` invocation
_HERE = Path(__file__).resolve()
_OPENSTARTUP = _HERE.parents[5]                   # OpenTeam/
_REPO_ROOT = _OPENSTARTUP.parent                   # CoreProjects/
for _dep in [
    _OPENSTARTUP / "src",
    _REPO_ROOT / "AgentFoundation" / "src",
    _REPO_ROOT / "PythonUtils" / "src",
]:
    _path = str(_dep)
    if _path not in sys.path:
        sys.path.insert(0, _path)

import agent_foundation.common.configs.registered_targets  # noqa: F401, E402
from python_utils.config_utils import load_config, instantiate  # noqa: E402

YAML_PATH = _OPENSTARTUP / "src/openteam/server/resources/tools/role_setup/role_setup.yaml"
TEMPLATES_PATH = _OPENSTARTUP / "src/openteam/server/resources/prompt_templates"
RUNTIME_BASE = _HERE.parent / "_runtime"

# Use the role document produced by the create_role test as input.
DEFAULT_ROLE_DOC = _OPENSTARTUP / (
    "test/openteam/resources/tools/create_role/_runtime/"
    "20260425_115535/outputs/role_responsibility_document.md"
)


def _claude_available() -> bool:
    try:
        r = subprocess.run("claude --version", shell=True,
                           capture_output=True, text=True, timeout=10)
        return r.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def _opus_1m_smoke_check():
    try:
        r = subprocess.run(
            'claude --print --model "opus[1m]" "Reply with the single word: pong"',
            shell=True, capture_output=True, text=True, timeout=60,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        return False, f"smoke check raised: {e}"
    out = (r.stdout or "").strip()
    err = (r.stderr or "").strip()
    if r.returncode != 0:
        return False, f"exit={r.returncode}, stderr={err[:300]}"
    bad = ("Execution error", "model not found", "unknown model",
           "invalid model", "Unsupported model")
    for m in bad:
        if m.lower() in out.lower() or m.lower() in err.lower():
            return False, f"got error marker {m!r}: out={out[:200]} err={err[:200]}"
    if not out:
        return False, f"empty stdout, stderr={err[:200]}"
    return True, f"opus[1m] responded ({len(out)}B): {out[:120]}"


def _claude_overrides_for_slot(workspace: Path, model: str) -> dict:
    """Per-slot ClaudeCodeCli config (excluding _target_ which we set separately)."""
    return {
        "target_path": str(workspace),
        "model_name": model,
        "idle_timeout_seconds": 300,
        "permission_mode": "bypassPermissions",
    }


def build_overrides(workspace: Path, model: str = "opus[1m]") -> dict:
    """Build dotted-key overrides to swap all 8 inferencer slots to ClaudeCodeCLI."""
    overrides: dict = {
        "workspace.root": str(workspace),
        "_template_manager.templates": str(TEMPLATES_PATH),
        # The inner BTA (imported from role_setup_skill_tool_creation.yaml)
        # has its OWN _template_manager block — patch its templates path too,
        # otherwise its breakdown/workers/aggregator silently fall back to
        # rendering the literal token "prompt_templates" as the prompt.
        "worker_factory.skill_tool_creation._template_manager.templates": str(TEMPLATES_PATH),
        # Outer BTA constraints (keep cost bounded)
        "max_breakdown": 2,
    }

    # Slots to swap: (dotted_path, is_homogeneous_factory_slot)
    # is_homogeneous_factory_slot=True means this is a *_factory entry that gets
    # auto-_partial_'d by load_config; we set _target_ but skip the assertion.
    slot_paths = [
        # Outer BTA
        "breakdown_inferencer",
        "aggregator_inferencer",
        "worker_factory.skill_tool_association",
        # Inner BTA (imported via _import_; dotted path traverses into it)
        "worker_factory.skill_tool_creation.breakdown_inferencer",
        "worker_factory.skill_tool_creation.aggregator_inferencer",
        "worker_factory.skill_tool_creation.worker_factory.skill_tool_creation_research",
        "worker_factory.skill_tool_creation.worker_factory.skill_tool_creation_investigation",
    ]

    # Inner BTA constraint (lives under the imported config)
    overrides["worker_factory.skill_tool_creation.max_breakdown"] = 2

    for slot in slot_paths:
        overrides[f"{slot}._target_"] = "ClaudeCodeCLI"
        for k, v in _claude_overrides_for_slot(workspace, model).items():
            overrides[f"{slot}.{k}"] = v

    return overrides


async def run(role_doc_text: str, role_doc_path: Path, workspace: Path):
    overrides = build_overrides(workspace)

    cfg = load_config(str(YAML_PATH), overrides=overrides)
    bta = instantiate(cfg)

    print(f"[sanity] outer BTA type: {type(bta).__name__}", flush=True)
    print(f"[sanity] outer breakdown: {type(bta.breakdown_inferencer).__name__}", flush=True)
    print(f"[sanity] outer aggregator: {type(bta.aggregator_inferencer).__name__}", flush=True)
    print(f"[sanity] outer worker_factory keys: {[k for k in bta.worker_factory if not k.startswith('_')]}", flush=True)

    # Provide template_extra_feed values that the inner BTA + workers expect
    # (mirrors test_role_setup_inner_bta_through_yaml.py and executor.py).
    bta.template_extra_feed.update({
        "role_name": role_doc_path.stem,
        "role_doc_path": str(role_doc_path),
        "available_tools_skills": "(tools registry not enumerated in this test)",
    })

    return await bta.ainfer(role_doc_text)


def main():
    if not _claude_available():
        print("ERROR: claude CLI not available", file=sys.stderr)
        sys.exit(2)

    print("[pre-flight] Checking opus[1m] availability ...", flush=True)
    ok, diag = _opus_1m_smoke_check()
    if not ok:
        print(f"ERROR: opus[1m] pre-flight failed: {diag}", file=sys.stderr)
        sys.exit(3)
    print(f"[pre-flight] OK -- {diag}", flush=True)

    role_doc = DEFAULT_ROLE_DOC
    if not role_doc.is_file():
        print(f"ERROR: role document not found at {role_doc}", file=sys.stderr)
        print("Run test_create_role_through_yaml_claude first to generate one,",
              file=sys.stderr)
        print("or hardcode DEFAULT_ROLE_DOC to a valid markdown path.", file=sys.stderr)
        sys.exit(4)

    role_doc_text = role_doc.read_text(encoding="utf-8")
    print(f"[input] role document: {role_doc} ({len(role_doc_text)}B)", flush=True)

    logging.basicConfig(level=logging.INFO)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    workspace = RUNTIME_BASE / timestamp
    workspace.mkdir(parents=True, exist_ok=True)
    print(f"[workspace] Artifacts -> {workspace}", flush=True)

    (workspace / "config.json").write_text(json.dumps({
        "model": "opus[1m]",
        "max_breakdown_outer": 2,
        "max_breakdown_inner": 2,
        "role_doc_source": str(role_doc),
        "timestamp": timestamp,
    }, indent=2), encoding="utf-8")
    (workspace / "input_role_doc.md").write_text(role_doc_text, encoding="utf-8")

    try:
        result = asyncio.run(run(role_doc_text, role_doc, workspace))
        print("=== RESULT (first 2000 chars) ===")
        print(str(result)[:2000])
        print("=== WORKSPACE FILES ===")
        for p in sorted(workspace.rglob("*")):
            if p.is_file():
                print(f"  {p.relative_to(workspace)}  ({p.stat().st_size}B)")
        print(f"\nArtifacts saved at: {workspace}")
        return 0
    except Exception:
        import traceback
        traceback.print_exc()
        print(f"\nPartial artifacts (if any) at: {workspace}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
