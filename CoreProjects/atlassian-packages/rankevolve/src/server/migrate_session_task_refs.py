# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict

"""One-shot: backfill role='task_ref' rows into existing session_state.json files.

Anchors each task chip to the conversation point where it was launched, so
resumed sessions show chips inline instead of clustered at the bottom.

Also backfills metadata.is_auto_advance: True on widget-submission and
tool-result user rows so the frontend protocol-prefix list can be retired.

PRECONDITION: stop the agent server before running. Concurrent writes will
corrupt session_state.json. Each session_state.json is backed up to
'<file>.pre_task_ref_backup' before rewrite, and rewrites are atomic
(temp file + os.replace).

Usage:
    buck run fbcode//rankevolve/src/server:migrate_session_task_refs -- \\
        /data/users/<you>/fbsource/fbcode/rankevolve/_runtime
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

# Locate the start of any ```json ToolsToInvoke ... ``` block, then extract
# ALL "name": "..." occurrences inside it. A single block may declare multiple
# tools (e.g. clarification + single_choice on the very first turn) and we
# need to consider every one of them as a candidate anchor name.
TOOLS_BLOCK_RE: re.Pattern[str] = re.compile(
    r"```json\s+ToolsToInvoke\s*\n(.*?)```",
    re.DOTALL,
)
NAME_RE: re.Pattern[str] = re.compile(r'"name"\s*:\s*"([^"]+)"')

WIDGET_PREFIX: str = "[Collected from conversation widget]"
TOOL_RESULT_PREFIXES: tuple[str, ...] = ("[Tool execution results]", "[Tool Result:")

# Tool names whose ToolsToInvoke blocks correspond to a top-level task launch
# that should produce a chip. Other tool names (clarification, single_choice,
# confirmation, proposal_selection, set_*, etc.) are handled separately
# (widgets) or don't produce chips.
TASK_LAUNCH_TOOLS: frozenset[str] = frozenset(
    {"understand_codebase", "research_propose", "task"}
)


def assistant_tool_names(content: str) -> list[str]:
    """Return every tool name declared in any ToolsToInvoke block of the
    assistant content, in document order."""
    names: list[str] = []
    for block in TOOLS_BLOCK_RE.findall(content or ""):
        names.extend(NAME_RE.findall(block))
    return names


def find_assistant_anchor(
    messages: list[dict[str, Any]],
    tool_name: str,
    used_anchors: set[int],
) -> int | None:
    """Scan assistant messages for any ToolsToInvoke block whose declared
    tool names include `tool_name`. Skips indices already claimed by an
    earlier task (handles repeat invocations and batched multi-tool blocks)."""
    for i, m in enumerate(messages):
        if m.get("role") != "assistant" or i in used_anchors:
            continue
        if tool_name in assistant_tool_names(m.get("content") or ""):
            return i
    return None


def find_widget_anchor(
    messages: list[dict[str, Any]],
    output_field: str,
    used_anchors: set[int],
) -> int | None:
    """Anchor a multi-task hub on the widget submission user message that
    produced its `selected_proposals` (or other output) field. Skips indices
    already claimed so distinct hubs land on distinct widget submissions."""
    for i, m in enumerate(messages):
        if i in used_anchors:
            continue
        content = m.get("content") or ""
        if (
            m.get("role") == "user"
            and content.startswith(WIDGET_PREFIX)
            and output_field in content
        ):
            return i
    return None


def _tool_name_label(tool_name: str) -> str:
    """Human-readable chip label for known top-level task tools."""
    return {
        "understand_codebase": "Codebase Investigation",
        "research_propose": "Research & Proposal",
    }.get(tool_name, "Task")


def _tool_name_from_workspace(ws_basename: str) -> str | None:
    """Infer the tool that produced a workspace from its directory name.

    Verified naming conventions (server/dual_inferencer_bridge.py + server/
    research_propose_bridge.py + server/tool_executor.py):
      - `research_<timestamp>` → research_propose
      - `task_<timestamp>` → understand_codebase or generic /task; we treat
        it as understand_codebase since that's the chip-producing flavor on
        completed_phases (plain /task runs end up under multi_task_id).
    """
    if ws_basename.startswith("research_"):
        return "research_propose"
    if ws_basename.startswith("task_"):
        return "understand_codebase"
    return None


def collect_chip_insertions(
    messages: list[dict[str, Any]],
    state: dict[str, Any],
) -> list[tuple[int, dict[str, Any]]]:
    """Build (anchor_idx, chip_dict) pairs for every task that needs a chip.

    Sources (all under workflow_context — verified key on disk):
      - workflow_context.active_multi_task_id + closed_multi_task_ids → hub chips
      - workflow_context.task_queue entries WITHOUT multi_task_id → standalone
        /task chips
      - workflow_context.completed_phases entries with workspace_path →
        understand_codebase / research_propose chips

    Per-batch sub-tasks (multi_task_id set in task_queue) are SKIPPED;
    they appear inside the hub panel, not as top-level chips. Phase-only
    completion records (no workspace_path) are also skipped — they're
    bookkeeping, not user-visible task launches.

    Tool-name correlation: for each completed phase / standalone task,
    walk assistant ToolsToInvoke blocks chronologically and pick the next
    unclaimed tool-launch invocation (understand_codebase, research_propose,
    task). Older persisted records don't carry tool_name on completed_phases,
    so we read it from the actual assistant message that fired the launch.
    """
    wc = state.get("workflow_context") or {}
    queue = list(wc.get("task_queue") or [])
    completed_phases = list(wc.get("completed_phases") or [])

    used_anchors: set[int] = set()
    insertions: list[tuple[int, dict[str, Any]]] = []

    # --- Hub chips: synthesized from active_multi_task_id + closed_multi_task_ids
    multi_ids: list[str] = []
    if wc.get("active_multi_task_id"):
        multi_ids.append(wc["active_multi_task_id"])
    multi_ids.extend(wc.get("closed_multi_task_ids") or [])
    for multi_id in multi_ids:
        anchor = find_widget_anchor(messages, "selected_proposals", used_anchors)
        if anchor is not None:
            used_anchors.add(anchor)
        chip: dict[str, Any] = {
            "role": "task_ref",
            "content": "Experiment Hub",
            "task_id": multi_id,
            "multi_task_id": multi_id,
            "metadata": {
                "is_task_ref": True,
                "tool_name": "proposal_selection",
            },
        }
        insertions.append((anchor if anchor is not None else len(messages) - 1, chip))

    # --- completed_phases entries with a real workspace_path. These were
    #     produced by understand_codebase / research_propose / task launches.
    #     Match each phase to its specific tool by the workspace-name prefix
    #     (research_* → research_propose, task_* → understand_codebase or
    #     /task), then anchor on the next unused assistant message that
    #     declared THAT specific tool. Falls back to any TASK_LAUNCH_TOOLS
    #     match if the precise one isn't found.
    phase_chips_pending = [
        p for p in completed_phases if (p.get("workspace_path") or "")
    ]
    for phase in phase_chips_pending:
        ws = phase.get("workspace_path") or ""
        ws_basename = Path(ws).name
        expected_tool = _tool_name_from_workspace(ws_basename)
        anchor = (
            find_assistant_anchor(messages, expected_tool, used_anchors)
            if expected_tool
            else None
        )
        chosen_tool = expected_tool
        if anchor is None:
            # Fallback: pick the next unused task-launch invocation regardless
            # of name (handles unusual workspace names).
            chosen_tool, anchor = _next_unused_task_launch(messages, used_anchors)
        if anchor is not None:
            used_anchors.add(anchor)
        synthesized_id = (
            phase.get("task_id") or f"phase-{phase.get('phase', '')}-{ws_basename}"
        )
        chip = {
            "role": "task_ref",
            "content": _tool_name_label(chosen_tool or ""),
            "task_id": synthesized_id,
            "multi_task_id": None,
            "metadata": {
                "is_task_ref": True,
                "tool_name": chosen_tool or "task",
            },
        }
        insertions.append((anchor if anchor is not None else len(messages) - 1, chip))

    # --- Standalone task_queue entries (no multi_task_id). In recent sessions
    #     these carry tool_name + created_at directly, so anchor by tool_name.
    standalone = sorted(
        [t for t in queue if not t.get("multi_task_id")],
        key=lambda t: t.get("created_at") or "",
    )
    for task in standalone:
        tool_name = task.get("tool_name")
        if not tool_name:
            continue
        anchor = find_assistant_anchor(messages, tool_name, used_anchors)
        if anchor is not None:
            used_anchors.add(anchor)
        chip = {
            "role": "task_ref",
            "content": task.get("title") or (task.get("request") or "")[:60] or "Task",
            "task_id": task["task_id"],
            "multi_task_id": None,
            "metadata": {
                "is_task_ref": True,
                "tool_name": tool_name,
            },
            "timestamp": task.get("created_at"),
        }
        insertions.append((anchor if anchor is not None else len(messages) - 1, chip))

    return insertions


def _next_unused_task_launch(
    messages: list[dict[str, Any]],
    used_anchors: set[int],
) -> tuple[str | None, int | None]:
    """Find the next assistant message (in document order) whose
    ToolsToInvoke block declares a TASK_LAUNCH_TOOLS name and that hasn't
    been claimed yet. Returns (tool_name, message_index) or (None, None)."""
    for i, m in enumerate(messages):
        if m.get("role") != "assistant" or i in used_anchors:
            continue
        for name in assistant_tool_names(m.get("content") or ""):
            if name in TASK_LAUNCH_TOOLS:
                return name, i
    return None, None


def backfill_protocol_metadata(messages: list[dict[str, Any]]) -> int:
    """Set metadata.is_auto_advance=True on widget/tool-result user rows that
    lack it. Returns count modified. Lets us retire PROTOCOL_USER_PREFIXES."""
    n = 0
    for m in messages:
        if m.get("role") != "user":
            continue
        content = m.get("content") or ""
        if not (
            content.startswith(WIDGET_PREFIX)
            or any(content.startswith(p) for p in TOOL_RESULT_PREFIXES)
        ):
            continue
        meta = m.get("metadata") or {}
        if meta.get("is_auto_advance") is True:
            continue
        meta["is_auto_advance"] = True
        m["metadata"] = meta
        n += 1
    return n


def migrate_session(path: Path) -> bool:
    """Migrate one session_state.json. Returns True if file was rewritten,
    False if already migrated or contains no conversation."""
    state = json.loads(path.read_text())
    conv = state.get("conversation")
    if not isinstance(conv, dict):
        return False
    messages = conv.get("messages") or []
    if any(m.get("role") == "task_ref" for m in messages):
        return False  # already migrated

    insertions = collect_chip_insertions(messages, state)
    backfill_protocol_metadata(messages)

    # Apply insertions back-to-front so earlier indices stay valid.
    for anchor_idx, chip in sorted(insertions, key=lambda x: x[0], reverse=True):
        messages.insert(anchor_idx + 1, chip)

    # `state.get("conversation")` may have returned None for a malformed file —
    # we already short-circuited above, but be defensive in case any code
    # path lands here with conversation absent.
    state.setdefault("conversation", {})["messages"] = messages

    # Backup + atomic rewrite
    backup = path.with_suffix(path.suffix + ".pre_task_ref_backup")
    backup.write_bytes(path.read_bytes())
    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent), prefix=path.name + ".", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(state, f, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        Path(tmp_path).unlink(missing_ok=True)
        raise
    return True


def main() -> None:
    runtime_root = sys.argv[1] if len(sys.argv) > 1 else "fbcode/rankevolve/_runtime"
    root = Path(runtime_root)
    files = list(root.glob("servers/*/sessions/*/session_state.json"))
    migrated = 0
    skipped = 0
    failed = 0
    for p in files:
        try:
            changed = migrate_session(p)
            if changed:
                migrated += 1
                print(f"migrated: {p}")
            else:
                skipped += 1
                print(f"skipped: {p}")
        except Exception as e:
            failed += 1
            print(f"FAILED: {p}: {e}")
    print(
        f"\nDone. migrated={migrated} skipped={skipped} failed={failed} "
        f"total={len(files)}"
    )


if __name__ == "__main__":
    main()
