# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict

"""One-shot: migrate task workspaces from flat <server>/tasks/ → per-session.

Moves each task workspace directory under
<server>/tasks/<basename>/  →  <server>/sessions/<session_dir>/tasks/<basename>/
and rewrites the absolute paths persisted in every session_state.json
(workflow_context.task_queue[*].workspace and
workflow_context.completed_phases[*].workspace_path) to point at the new
locations.

Ownership is determined by scanning each session_state.json's persisted
workspace strings; any task workspace not claimed by any session is treated
as an orphan and (by default) moved under <server>/tasks/_orphans/ for
later inspection.

PRECONDITION: stop the agent server before running. Concurrent writes to
session_state.json or task workspaces will corrupt the migration. Each
session_state.json is backed up to <file>.pre_tasks_migration_backup
before rewrite, and rewrites are atomic (temp file + os.replace).

Usage:
    buck run fbcode//rankevolve/src/server:migrate_tasks_per_session -- \\
        --runtime-root /data/users/<you>/fbsource/fbcode/rankevolve/_runtime \\
        [--server-dir <server_subdir_name>] \\
        [--dry-run] \\
        [--keep-orphans]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

logger: logging.Logger = logging.getLogger("migrate_tasks_per_session")


_BACKUP_SUFFIX = ".pre_tasks_migration_backup"
_ORPHANS_DIRNAME = "_orphans"


def _atomic_write_json(path: Path, data: dict) -> None:
    """Write JSON atomically (tmpfile + os.replace) preserving file mode."""
    tmp = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(path.parent),
        prefix=path.name + ".",
        suffix=".tmp",
        delete=False,
    )
    try:
        json.dump(data, tmp, indent=2, ensure_ascii=False)
        tmp.write("\n")
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp.close()
        os.replace(tmp.name, str(path))
    except Exception:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        raise


_MAX_PATH_LEN = 4096  # Skip any string longer than this — it's not a path.


def _walk_strings(node: Any) -> Any:
    """Generator yielding str leaves in a JSON-like tree.

    Walks dicts + lists recursively. Filters to strings that LOOK like
    absolute paths (start with ``/`` and are < 4096 chars) so we don't
    try to treat narrative markdown text as a path. Round 7-8 added
    fields beyond ``task_queue[*].workspace`` — this generic walker
    catches them all (hypothesis_results.experimentList[*].workspace,
    reviewSummaryPath, codebase_understanding, unified_plan_path,
    active_workspace, etc.) without re-listing every field.
    """
    if isinstance(node, dict):
        for v in node.values():
            yield from _walk_strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk_strings(v)
    elif isinstance(node, str):
        if 0 < len(node) <= _MAX_PATH_LEN and (node.startswith("/") or "/tasks/" in node):
            yield node


def _collect_workspace_paths(state: dict) -> list[str]:
    """Extract every plausible workspace path string referenced anywhere
    in the session_state JSON tree.

    Round 9: walks the entire tree (not just task_queue + completed_phases)
    so that Round 7-8 fields (hypothesis_results, codebase_understanding,
    unified_plan_path, active_workspace, etc.) are covered.
    """
    return list(_walk_strings(state))


def _collect_task_meta_indices(server_dir: Path) -> dict[str, dict[str, str]]:
    """Build a per-task-dir index of identifying fields read from each
    ``<server>/tasks/<task_dir>/.task_meta.json`` sidecar.

    Returns ``{task_dir_name: {"task_id": str, "multi_task_id": str,
    "session_id": str (if pre-Round-9 already-migrated)}}``.

    Used to identify task ownership for dirs NOT in any session_state's
    persisted ``task_queue`` (e.g., synth-built workspaces whose state
    was added later, or batch sub-tasks of a multi_task hub: many tasks
    share one multi_task_id, so a flat ``multi_task_id → task_dir`` map
    would collapse them).
    """
    tasks_dir = server_dir / "tasks"
    out: dict[str, dict[str, str]] = {}
    if not tasks_dir.is_dir():
        return out
    for child in sorted(tasks_dir.iterdir()):
        if not child.is_dir() or child.name == _ORPHANS_DIRNAME:
            continue
        meta = child / ".task_meta.json"
        if not meta.is_file():
            continue
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        out[child.name] = {
            "task_id": str(data.get("task_id") or ""),
            "multi_task_id": str(data.get("multi_task_id") or ""),
            "session_id": str(data.get("session_id") or ""),
        }
    return out


def _build_session_indices(
    state: dict,
) -> tuple[set[str], set[str]]:
    """Return ``(task_ids, multi_task_ids)`` referenced by this session_state.

    Used by the migration to attribute task dirs (via .task_meta.json) to
    the session that owns them.
    """
    task_ids: set[str] = set()
    multi_ids: set[str] = set()
    wc = state.get("workflow_context") or {}
    for entry in wc.get("task_queue") or []:
        tid = entry.get("task_id")
        if isinstance(tid, str) and tid:
            task_ids.add(tid)
        mtid = entry.get("multi_task_id")
        if isinstance(mtid, str) and mtid:
            multi_ids.add(mtid)
    for phase in wc.get("completed_phases") or []:
        tid = phase.get("task_id")
        if isinstance(tid, str) and tid:
            task_ids.add(tid)
    amt = wc.get("active_multi_task_id")
    if isinstance(amt, str) and amt:
        multi_ids.add(amt)
    cmt = wc.get("closed_multi_task_ids") or []
    for mtid in cmt:
        if isinstance(mtid, str) and mtid:
            multi_ids.add(mtid)
    return task_ids, multi_ids


def _resolve_under_old_tasks(ws: str, old_tasks_dir: Path) -> Path | None:
    """Return the absolute Path of `ws` IF it points under old_tasks_dir.

    Handles both absolute paths and fbcode-relative legacy paths. Returns
    None if the path doesn't resolve under old_tasks_dir (e.g. references a
    different server's tasks dir, an external location, or the basename
    only).
    """
    if not ws or len(ws) > _MAX_PATH_LEN:
        return None
    if "\n" in ws or "\0" in ws:
        # Defensive: narrative markdown / binary blobs are not paths.
        return None
    try:
        p = Path(ws)
    except (ValueError, OSError):
        return None
    if not p.is_absolute():
        # Legacy fbcode-relative form. The actual on-disk location is
        # <fbcode>/<ws>; if it resolves under old_tasks_dir, accept.
        # We resolve by checking whether old_tasks_dir/<basename> exists
        # AND <fbcode>/<ws> resolves to that same path.
        try:
            candidate = old_tasks_dir / p.name
            if candidate.is_dir():
                return candidate
        except OSError:
            pass
        return None
    try:
        p_resolved = p.resolve()
    except OSError:
        return None
    try:
        p_resolved.relative_to(old_tasks_dir.resolve())
        return p_resolved
    except ValueError:
        return None


def _move_workspace(src: Path, dst: Path, dry_run: bool) -> bool:
    """Move src → dst. Returns True if a move was performed (or planned)."""
    if not src.exists():
        if dst.exists():
            logger.debug("ALREADY MIGRATED: %s → %s", src, dst)
            return False
        logger.warning("MISSING SOURCE: %s (dst=%s)", src, dst)
        return False
    if dst.exists():
        logger.warning(
            "CONFLICT: dst already exists, leaving src in place: src=%s dst=%s",
            src,
            dst,
        )
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    logger.info("MOVE %s → %s", src, dst)
    if not dry_run:
        # Same-filesystem rename — atomic on POSIX.
        shutil.move(str(src), str(dst))
    return True


def _rewrite_in_tree(
    node: Any,
    old_tasks_dir: Path,
    new_tasks_dir: Path,
    moved_basenames: set[str] | None = None,
) -> int:
    """Walk a JSON-like tree (dicts + lists); rewrite every str leaf that
    points under ``old_tasks_dir/<basename>`` (or any descendant path) to
    the matching ``new_tasks_dir/<basename>`` path.

    Returns the number of strings rewritten. Mutates the tree in place.

    Round 9: handles
      (a) absolute paths under old_tasks_dir (`<server>/tasks/<dir>`)
      (b) deeper abs paths inside them (`<server>/tasks/<dir>/outputs/foo.md`)
      (c) relative paths where the source dir was already moved BUT the
          basename is in ``moved_basenames`` (this branch fixes a bug where
          completed_phases[*].workspace_path stores fbcode-relative forms
          that can't be resolved post-move via on-disk existence check).
    """
    n = 0
    old_prefix = str(old_tasks_dir.resolve()) + "/"
    new_prefix = str(new_tasks_dir.resolve()) + "/"

    # Pattern for the relative-path fallback: matches any "/tasks/<basename>"
    # substring. Used only when moved_basenames is provided (post-move state).
    rel_pat = re.compile(r"/tasks/([a-zA-Z0-9_\-]+)(?=/|$|\b)")

    def rewrite_str(s: str) -> tuple[str, bool]:
        # Absolute path under old_tasks_dir → rewrite prefix.
        if s.startswith(old_prefix):
            return new_prefix + s[len(old_prefix):], True
        # Bare equality with old_tasks_dir (no trailing slash) → rewrite.
        if s == str(old_tasks_dir.resolve()):
            return str(new_tasks_dir.resolve()), True
        # Try _resolve_under_old_tasks (handles relative paths whose source
        # still exists on disk).
        resolved = _resolve_under_old_tasks(s, old_tasks_dir)
        if resolved is not None:
            try:
                rel = resolved.resolve().relative_to(old_tasks_dir.resolve())
                return str(new_tasks_dir / rel), True
            except ValueError:
                return s, False
        # Round 9 relative-path fallback: source already moved (so on-disk
        # check fails) but basename matches a moved task → rewrite.
        if moved_basenames and "/tasks/" in s:
            for m in rel_pat.finditer(s):
                basename = m.group(1)
                if basename not in moved_basenames:
                    continue
                # Rewrite this occurrence.  The string fragment from start
                # of "/tasks/" through end of "<basename>" is replaced by
                # str(new_tasks_dir / basename).
                old_fragment = s[m.start():m.end()]
                new_fragment = str(new_tasks_dir / basename)
                # Preserve everything BEFORE the /tasks/ marker (the
                # "rankevolve/_runtime/servers/<srv>" prefix becomes
                # irrelevant since new_tasks_dir is absolute).
                # Strategy: replace the leading prefix-up-through-old-/tasks/
                # with new_tasks_dir/.
                pre_idx = s.rfind("/tasks/", 0, m.end())
                pre = s[:pre_idx]
                post = s[m.end():]
                # Drop everything before /tasks/ and substitute new_tasks_dir.
                s = str(new_tasks_dir / basename) + post
                return s, True
        return s, False

    if isinstance(node, dict):
        for k, v in list(node.items()):
            if isinstance(v, str):
                new, changed = rewrite_str(v)
                if changed:
                    node[k] = new
                    n += 1
            else:
                n += _rewrite_in_tree(v, old_tasks_dir, new_tasks_dir, moved_basenames)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            if isinstance(v, str):
                new, changed = rewrite_str(v)
                if changed:
                    node[i] = new
                    n += 1
            else:
                n += _rewrite_in_tree(v, old_tasks_dir, new_tasks_dir, moved_basenames)
    return n


def _rewrite_session_state(
    state_path: Path,
    state: dict,
    old_tasks_dir: Path,
    new_tasks_dir: Path,
    dry_run: bool,
    moved_basenames: set[str] | None = None,
) -> int:
    """Rewrite ANY workspace path string in `state` (Round 9: walks the
    whole tree) to point under new_tasks_dir.

    Returns the number of strings rewritten. Performs atomic write only if
    not dry_run.
    """
    n = _rewrite_in_tree(state, old_tasks_dir, new_tasks_dir, moved_basenames)

    if n > 0 and not dry_run:
        backup = state_path.with_suffix(state_path.suffix + _BACKUP_SUFFIX)
        if not backup.exists():
            shutil.copy2(state_path, backup)
        _atomic_write_json(state_path, state)
    return n


def _rewrite_hub_submissions(
    session_dir: Path,
    old_tasks_dir: Path,
    new_tasks_dir: Path,
    dry_run: bool,
    moved_basenames: set[str] | None = None,
) -> int:
    """Round 9: rewrite ``<session_dir>/hub_<mid>_submissions.json`` files.

    Round 7-8 added ``submissions[*].analysisFile`` (abs path to a sidecar
    inside a task workspace). The same generic walker handles all fields.
    Returns total strings rewritten across all hub_*_submissions.json files
    in the session_dir.
    """
    n_total = 0
    for hub_path in sorted(session_dir.glob("hub_*_submissions.json")):
        try:
            data = json.loads(hub_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to read %s: %s — skipping.", hub_path, e)
            continue
        n = _rewrite_in_tree(data, old_tasks_dir, new_tasks_dir, moved_basenames)
        if n > 0:
            if not dry_run:
                backup = hub_path.with_suffix(hub_path.suffix + _BACKUP_SUFFIX)
                if not backup.exists():
                    shutil.copy2(hub_path, backup)
                _atomic_write_json(hub_path, data)
            n_total += n
            logger.info("REWRITE %s — %d strings updated", hub_path, n)
    return n_total


def _augment_moved_sidecar(
    moved_dir: Path,
    session_id: str,
    session_dir_name: str,
) -> None:
    """Add ``session_id`` + ``session_dir`` fields to a moved task's
    ``.task_meta.json`` sidecar (Round 9 — direct FK so future migrations
    don't need to scan every session_state.json again).

    Idempotent: skips if both fields are already present.
    """
    meta_path = moved_dir / ".task_meta.json"
    if not meta_path.is_file():
        return
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    if not isinstance(data, dict):
        return
    changed = False
    if data.get("session_id") != session_id:
        data["session_id"] = session_id
        changed = True
    if data.get("session_dir") != session_dir_name:
        data["session_dir"] = session_dir_name
        changed = True
    if changed:
        try:
            _atomic_write_json(meta_path, data)
        except OSError:
            pass


def _process_server(
    server_dir: Path, dry_run: bool, keep_orphans: bool
) -> dict[str, Any]:
    """Migrate one server's tasks. Returns a stats dict.

    Round 9 algorithm:
      1. Build per-session indices: {task_id, multi_task_id} → session_dir.
         Detect conflicts (same id → multiple sessions); ABORT this server
         on any conflict so the operator can hand-investigate.
      2. Build sidecar indices from <server>/tasks/<dir>/.task_meta.json:
         {task_id, multi_task_id} → task_dir basename.
      3. For each task dir under <server>/tasks/, attribute it to a session by:
         (a) direct workspace path match in session_state, OR
         (b) .task_meta.json.task_id → session via task_id_index, OR
         (c) .task_meta.json.multi_task_id → session via multi_task_id_index.
      4. Move attributed tasks under <session_dir>/tasks/.
      5. For EACH session: rewrite paths in session_state.json (whole tree)
         AND every hub_*_submissions.json. Augment moved sidecars with
         session_id + session_dir fields.
      6. Orphans (no attribution) → <server>/tasks/_orphans/ if --keep-orphans.
      7. Cleanup: rmdir <server>/tasks/ if empty.
    """
    sessions_root = server_dir / "sessions"
    old_tasks_dir = server_dir / "tasks"
    if not sessions_root.is_dir():
        logger.warning("No sessions/ under %s — skipping.", server_dir)
        return {}
    if not old_tasks_dir.is_dir():
        logger.info(
            "No global tasks/ under %s — already migrated or fresh server.",
            server_dir,
        )
        return {}

    # Step 1+2: build the cross-session id indices.
    task_id_to_session: dict[str, Path] = {}
    multi_task_id_to_session: dict[str, Path] = {}
    conflicts: list[tuple[str, str, str, str]] = []  # (kind, id, session_a, session_b)
    session_states: dict[Path, dict] = {}

    for session_dir in sorted(sessions_root.iterdir()):
        if not session_dir.is_dir():
            continue
        state_path = session_dir / "session_state.json"
        if not state_path.is_file():
            continue
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        session_states[session_dir] = state
        tids, mtids = _build_session_indices(state)
        for tid in tids:
            prev = task_id_to_session.get(tid)
            if prev is not None and prev != session_dir:
                conflicts.append(("task_id", tid, prev.name, session_dir.name))
            else:
                task_id_to_session[tid] = session_dir
        for mtid in mtids:
            prev = multi_task_id_to_session.get(mtid)
            if prev is not None and prev != session_dir:
                conflicts.append(("multi_task_id", mtid, prev.name, session_dir.name))
            else:
                multi_task_id_to_session[mtid] = session_dir

    if conflicts:
        logger.error(
            "ABORT %s: %d task/multi_task ownership conflicts detected:",
            server_dir, len(conflicts),
        )
        for kind, ident, a, b in conflicts[:10]:
            logger.error("  %s=%s claimed by %s AND %s", kind, ident, a, b)
        return {"aborted": True, "conflicts": len(conflicts)}

    # Sidecar indices: per-task-dir IDs read from .task_meta.json.
    sidecar_meta = _collect_task_meta_indices(server_dir)

    claimed: set[str] = set()  # basenames moved or already at dst
    moved = 0
    rewritten = 0
    hub_rewritten = 0
    sessions_seen = 0
    moved_dst_paths: list[tuple[Path, str, str]] = []  # (dst, sid, session_dir_name)

    for session_dir, state in sorted(session_states.items()):
        sessions_seen += 1
        state_path = session_dir / "session_state.json"
        sid_full = session_dir.name  # e.g. "ses-...._20260330_175458"
        # Bare session_id (without timestamp) for the sidecar field
        sid_bare = (state.get("info") or {}).get("session_id") or sid_full.rsplit("_", 2)[0]

        new_tasks_dir = session_dir / "tasks"
        seen_basenames: set[str] = set()

        # Step 3a: attribute via direct workspace paths in session_state.
        for ws in _collect_workspace_paths(state):
            resolved = _resolve_under_old_tasks(ws, old_tasks_dir)
            if resolved is None:
                continue
            basename = resolved.name
            if basename in seen_basenames:
                continue
            seen_basenames.add(basename)
            src = old_tasks_dir / basename
            dst = new_tasks_dir / basename
            if _move_workspace(src, dst, dry_run):
                moved += 1
            claimed.add(basename)
            if not dry_run:
                _augment_moved_sidecar(dst, sid_bare, sid_full)
                moved_dst_paths.append((dst, sid_bare, sid_full))

        # Step 3b+3c: attribute remaining task_dirs via .task_meta.json
        # (Round 9 — covers synth-built tasks whose workspace path may not be
        # in session_state's task_queue but whose task_id or multi_task_id
        # matches this session). Iterates per task_dir so that many tasks
        # sharing one multi_task_id (e.g., 56 eval_H<N>_* under multi-syn00001)
        # all get attributed to the right session.
        own_tids, own_mtids = _build_session_indices(state)
        for basename, ids in sidecar_meta.items():
            if basename in claimed:
                continue
            tid = ids.get("task_id") or ""
            mtid = ids.get("multi_task_id") or ""
            sid_in_meta = ids.get("session_id") or ""
            attributed = (
                (tid and tid in own_tids)
                or (mtid and mtid in own_mtids)
                or (sid_in_meta and sid_in_meta == sid_bare)
            )
            if not attributed:
                continue
            src = old_tasks_dir / basename
            dst = new_tasks_dir / basename
            if _move_workspace(src, dst, dry_run):
                moved += 1
            claimed.add(basename)
            if not dry_run:
                _augment_moved_sidecar(dst, sid_bare, sid_full)
                moved_dst_paths.append((dst, sid_bare, sid_full))

        # Per-session moved basenames — used by the relative-path rewrite
        # branch in _rewrite_in_tree to handle paths whose source dir was
        # already moved (so the on-disk existence check fails).
        sess_moved = {dst.name for (dst, _, _) in moved_dst_paths
                      if str(dst).startswith(str(session_dir))}

        # Step 5: rewrite paths in session_state (whole tree) + hub_*_submissions.json.
        n = _rewrite_session_state(
            state_path, state, old_tasks_dir, new_tasks_dir, dry_run,
            moved_basenames=sess_moved,
        )
        rewritten += n
        if n > 0:
            logger.info("REWRITE %s — %d workspace strings updated", state_path, n)

        nh = _rewrite_hub_submissions(
            session_dir, old_tasks_dir, new_tasks_dir, dry_run,
            moved_basenames=sess_moved,
        )
        hub_rewritten += nh

    # Orphans: anything still under old_tasks_dir not claimed by any session.
    orphans: list[Path] = []
    for child in sorted(old_tasks_dir.iterdir()):
        if not child.is_dir():
            continue
        if child.name == _ORPHANS_DIRNAME:
            continue
        if child.name in claimed:
            # Successfully migrated already — moved out of old_tasks_dir.
            # If still present, that means the move failed (conflict).
            continue
        orphans.append(child)

    if orphans and keep_orphans:
        orphans_dir = old_tasks_dir / _ORPHANS_DIRNAME
        for src in orphans:
            dst = orphans_dir / src.name
            logger.info("ORPHAN → %s", dst)
            if not dry_run:
                orphans_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dst))
    elif orphans:
        for src in orphans:
            logger.warning("ORPHAN (not moved; rerun with --keep-orphans): %s", src)

    # Remove old_tasks_dir if empty and no orphans were preserved.
    if not dry_run and old_tasks_dir.is_dir():
        try:
            remaining = [c for c in old_tasks_dir.iterdir()]
            if not remaining:
                old_tasks_dir.rmdir()
                logger.info("REMOVED empty %s", old_tasks_dir)
        except OSError as e:
            logger.warning("Could not rmdir %s: %s", old_tasks_dir, e)

    return {
        "sessions_seen": sessions_seen,
        "moved": moved,
        "rewritten": rewritten,
        "hub_rewritten": hub_rewritten,
        "orphans": len(orphans),
    }


def _check_no_running_server() -> None:
    """Round 9 pre-flight: refuse to run if any pid matches the agent-server
    invocation pattern. The migration mutates session_state.json + moves
    task workspaces — concurrent writes by a running server would corrupt
    state.

    Mirrors the precondition documented for `migrate_session_task_refs.py`,
    but enforces it programmatically.
    """
    try:
        import subprocess

        out = subprocess.run(
            ["ps", "-eo", "pid,command"],
            capture_output=True, text=True, timeout=5,
        ).stdout
    except Exception:
        # Best effort — if ps isn't available, log a warning + proceed.
        logger.warning("Could not run `ps` for pre-flight pid check; proceeding.")
        return
    matches = []
    for line in out.splitlines():
        if "run_webui_real" in line or "agent_server" in line:
            matches.append(line.strip())
    if matches:
        logger.error(
            "ABORT: detected running agent server pid(s); stop them before "
            "migrating. Matches:\n  %s",
            "\n  ".join(matches[:5]),
        )
        sys.exit(3)


def main() -> None:
    """Entry point. See module docstring for usage."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runtime-root",
        type=Path,
        required=True,
        help="Path to <repo>/rankevolve/_runtime (the parent of servers/).",
    )
    parser.add_argument(
        "--server-dir",
        type=str,
        default=None,
        help="Optional server subdir name to scope the migration "
        "(e.g. 'server_20260330_174845_5173c924'). If omitted, all servers "
        "under <runtime-root>/servers/ are processed.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned moves and rewrites without touching disk.",
    )
    parser.add_argument(
        "--keep-orphans",
        action="store_true",
        help="Move unclaimed task workspaces to <server>/tasks/_orphans/ "
        "(default: leave in place under <server>/tasks/, log a warning).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip the running-agent-server pre-flight check. Use ONLY when "
        "you know the server is stopped and the ps check is a false positive.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Verbose (DEBUG) logging."
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Round 9 pre-flight: refuse to run if an agent server is alive (would
    # corrupt the migration via concurrent writes).
    if not args.dry_run and not args.force:
        _check_no_running_server()

    servers_dir = args.runtime_root / "servers"
    if not servers_dir.is_dir():
        logger.error("No servers/ under %s — nothing to migrate.", args.runtime_root)
        sys.exit(2)

    targets: list[Path]
    if args.server_dir:
        cand = servers_dir / args.server_dir
        if not cand.is_dir():
            logger.error("Server dir not found: %s", cand)
            sys.exit(2)
        targets = [cand]
    else:
        targets = sorted(d for d in servers_dir.iterdir() if d.is_dir())

    total = {
        "sessions_seen": 0, "moved": 0, "rewritten": 0,
        "hub_rewritten": 0, "orphans": 0,
    }
    aborted: list[Path] = []
    for server in targets:
        logger.info("=== Processing %s ===", server)
        stats = _process_server(server, args.dry_run, args.keep_orphans)
        if stats.get("aborted"):
            aborted.append(server)
            continue
        for k in total:
            total[k] += stats.get(k, 0)

    logger.info(
        "=== Summary: sessions_seen=%d moved=%d rewritten=%d hub_rewritten=%d "
        "orphans=%d aborted=%d (dry_run=%s) ===",
        total["sessions_seen"], total["moved"], total["rewritten"],
        total["hub_rewritten"], total["orphans"], len(aborted), args.dry_run,
    )
    if aborted:
        logger.error("Aborted servers (id conflicts; investigate manually):")
        for srv in aborted:
            logger.error("  %s", srv)
        sys.exit(4)
