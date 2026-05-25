# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict

"""F4-cleanup: Backfill metadata.task_status onto legacy task_ref rows.

For each ``role="task_ref"`` message in a session's ``session_state.json``
that lacks ``metadata.task_status`` (the field added by F4), check the
session's ``tasks/`` directory for a completed workspace and write
``"completed"`` (or ``"error"``) into the persisted metadata. After
running, the React reducer at ``useSessionManager.js:880`` will read this
value on session-load so the chip shows the correct status instead of
defaulting to ``'queued'``.

Idempotent: skips task_refs that already carry ``metadata.task_status``.
Atomic write via ``.tmp`` + ``os.replace`` (mirrors the pattern used by
``persist_session_state``).

PRECONDITION: stop the agent server before running. Concurrent writes will
corrupt session_state.json. Each rewritten file is backed up to
``<file>.pre_task_status_backup``.

Usage:
    # Single session:
    buck run fbcode//rankevolve/src/server:migrate_task_ref_status -- \\
        --session-state /data/.../sessions/<sid>/session_state.json

    # All sessions under a server-dir:
    buck run fbcode//rankevolve/src/server:migrate_task_ref_status -- \\
        --server-dir /data/.../_runtime/servers/<server>

    # Dry-run to preview changes:
    buck run fbcode//rankevolve/src/server:migrate_task_ref_status -- \\
        --session-state <path> --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any


def _is_completed_workspace(workspace: Path) -> bool:
    """A workspace is "completed" iff both plan + impl markers exist in
    ``artifacts/`` (canonical) or ``outputs/`` (legacy fallback). Mirrors
    ``InferencerWorkspace.has_marker`` semantics from
    ``inferencer_workspace.py:221``."""
    for marker_dir in ("artifacts", "outputs"):
        plan = workspace / marker_dir / ".plan_completed"
        impl = workspace / marker_dir / ".impl_completed"
        impl_long = workspace / marker_dir / ".implementation_completed"
        if plan.is_file() and (impl.is_file() or impl_long.is_file()):
            return True
    return False


def _is_error_workspace(workspace: Path) -> bool:
    """Heuristic: an explicit ``.error`` marker indicates failure. Otherwise
    we treat absence of completion markers as "uncertain" and skip — better
    than miscategorizing as 'error'."""
    for marker_dir in ("artifacts", "outputs"):
        if (workspace / marker_dir / ".error").is_file():
            return True
    return False


def _classify_workspace(workspace: Path) -> str | None:
    """Return ``"completed"``, ``"error"``, or None when uncertain."""
    if _is_completed_workspace(workspace):
        return "completed"
    if _is_error_workspace(workspace):
        return "error"
    return None


def _find_workspace_for_task_ref(
    session_dir: Path, task_id: str, label: str
) -> Path | None:
    """Locate the most-likely task workspace for a task_ref row.

    The legacy task_ref schema didn't store the workspace path, so we use
    heuristics in priority order:

      1. EXACT match: ``tasks/<task_id>/`` exists (some recent task_ids
         literally name the workspace).
      2. Match by request.txt content: scan ``tasks/task_*/`` for a
         workspace whose ``request.txt`` content matches the task_ref's
         label (which the backend writer stores as the human-readable
         label — often the target path for understand_codebase).
      3. SINGLE-WORKSPACE fallback: if the session has exactly one
         ``task_*/`` workspace AND it's completed, return it (most common
         for short sessions like the user's ``ses-mofybenm-6p1k``).

    Returns None when no match is found.
    """
    tasks_dir = session_dir / "tasks"
    if not tasks_dir.is_dir():
        return None

    # 1. Exact match
    direct = tasks_dir / task_id
    if direct.is_dir():
        return direct

    candidates: list[Path] = []
    try:
        for cand in tasks_dir.iterdir():
            if not cand.is_dir():
                continue
            if not (
                cand.name.startswith("task_") or cand.name.startswith("task-")
            ):
                continue
            candidates.append(cand)
    except OSError:
        return None

    # 2. Match by request.txt content equal to label (trimmed).
    label_norm = (label or "").strip()
    if label_norm:
        for cand in candidates:
            req_file = cand / "request.txt"
            if not req_file.is_file():
                continue
            try:
                content = req_file.read_text(encoding="utf-8").strip()
            except OSError:
                continue
            if content == label_norm:
                return cand

    # 3. Single-workspace fallback.
    if len(candidates) == 1:
        return candidates[0]
    return None


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    """Write data atomically via ``.tmp`` + ``os.replace``."""
    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def migrate_session(
    session_state_path: Path,
    dry_run: bool = False,
) -> int:
    """Migrate one session_state.json. Returns count of migrated task_refs."""
    if not session_state_path.is_file():
        print(f"WARN: {session_state_path} not found", file=sys.stderr)
        return 0

    session_dir = session_state_path.parent
    try:
        data = json.loads(session_state_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(
            f"WARN: failed to parse {session_state_path}: {e}", file=sys.stderr
        )
        return 0

    conv = data.get("conversation") or {}
    messages = conv.get("messages") or []

    migrated = 0
    for msg in messages:
        if msg.get("role") != "task_ref":
            continue
        metadata = msg.get("metadata") or {}
        if metadata.get("task_status"):
            continue  # already has F4 status; skip

        task_id = msg.get("task_id") or ""
        label = msg.get("content") or msg.get("label") or ""
        ws = _find_workspace_for_task_ref(session_dir, task_id, label)
        if ws is None:
            print(
                f"  SKIP task_id={task_id} label={label!r}: no matching workspace"
            )
            continue
        status = _classify_workspace(ws)
        if status is None:
            print(
                f"  SKIP task_id={task_id} workspace={ws.name}: no completion markers"
            )
            continue

        metadata["task_status"] = status
        msg["metadata"] = metadata
        migrated += 1
        print(
            f"  MIGRATE task_id={task_id} workspace={ws.name} → status={status!r}"
        )

    if migrated == 0:
        print(f"{session_state_path}: nothing to migrate")
        return 0
    if dry_run:
        print(
            f"{session_state_path}: DRY RUN — would migrate {migrated} task_ref(s)"
        )
        return migrated

    backup = session_state_path.with_suffix(
        session_state_path.suffix + ".pre_task_status_backup"
    )
    try:
        shutil.copy2(session_state_path, backup)
    except Exception as e:
        print(
            f"ERROR: could not back up {session_state_path}: {e}",
            file=sys.stderr,
        )
        return 0

    try:
        _atomic_write_json(session_state_path, data)
    except Exception as e:
        print(
            f"ERROR: write failed for {session_state_path}: {e}",
            file=sys.stderr,
        )
        return 0

    print(
        f"{session_state_path}: migrated {migrated} task_ref(s); "
        f"backup at {backup.name}"
    )
    return migrated


def migrate_server_dir(server_dir: Path, dry_run: bool = False) -> int:
    """Migrate every session under ``<server_dir>/sessions/*/session_state.json``."""
    sessions_root = server_dir / "sessions"
    if not sessions_root.is_dir():
        print(
            f"ERROR: {sessions_root} is not a directory", file=sys.stderr
        )
        return 0
    total = 0
    for sess in sorted(sessions_root.iterdir()):
        ssp = sess / "session_state.json"
        if ssp.is_file():
            print(f"--- {sess.name} ---")
            total += migrate_session(ssp, dry_run=dry_run)
    print(f"=== TOTAL migrated: {total} task_ref(s) across all sessions ===")
    return total


def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Backfill metadata.task_status on legacy task_ref rows so the "
            "WebUI chip status restores correctly on session-load."
        )
    )
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--session-state",
        type=Path,
        help="Path to a single session_state.json to migrate.",
    )
    group.add_argument(
        "--server-dir",
        type=Path,
        help=(
            "Path to a server directory; migrates every session under "
            "<server-dir>/sessions/*/session_state.json."
        ),
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Print proposed changes without writing.",
    )
    args = ap.parse_args()

    if args.session_state is not None:
        migrate_session(args.session_state, dry_run=args.dry_run)
    else:
        migrate_server_dir(args.server_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
