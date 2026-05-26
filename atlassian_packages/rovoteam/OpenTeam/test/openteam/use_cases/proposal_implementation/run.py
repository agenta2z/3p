"""Entry point. See README.md for usage.

Example:
    python3 -m openteam.use_cases.proposal_implementation.run \\
        --epic AI-236 \\
        --assignee-hint "Tony Chen" \\
        --assignee-account-id "712020:5cf4b2db-f12d-4739-867d-9fe8ecb66d54" \\
        --workspace /Users/.../atlassian_packages/conversational-ai-platform \\
        --max-parallel-inferencers 2 \\
        --epic-poll-interval-seconds 600 \\
        --pr-poll-interval-seconds 300
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# Eager sys.path extension — must happen BEFORE we import tasks.py (which
# lazily imports agent_foundation in _run_inferencer). Without these, the
# inferencer will crash on the first invocation with ModuleNotFoundError and
# the orchestrator will tight-loop on safety re-enqueue.
#
# Default locations (CoreProjects-relative). Override via JIRA_BOARD_PYTHONPATH
# env var (colon-separated, prepended).
_DEFAULT_DEP_PATHS = [
    "/Users/tchen7/MyProjects/CoreProjects/AgentFoundation/src",
    "/Users/tchen7/MyProjects/CoreProjects/PythonUtils/src",
    "/Users/tchen7/MyProjects/CoreProjects/ScienceModelingTools/src",
    "/Users/tchen7/MyProjects/CoreProjects/SciencePythonUtils/src",
]
for _extra in (os.environ.get("JIRA_BOARD_PYTHONPATH", "") or "").split(":"):
    if _extra and _extra not in sys.path:
        sys.path.insert(0, _extra)
for _p in _DEFAULT_DEP_PATHS:
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

from .orchestrator import Orchestrator, install_sigint_handler
from .runtime import RunWorkspace
from .state import load_state
from .tasks import MonitorEpicTask, MonitorPRTask


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Jira-board + PR monitor PoC: ALL Atlassian ops via RovoDev CLI inferencer."
    )
    p.add_argument("--epic", required=True, help="Epic key to watch, e.g. AI-236")
    p.add_argument("--assignee-hint", required=True,
                   help='Display name of the target assignee (e.g. "Tony Chen"). '
                        'Used in prompts for human-readable context.')
    p.add_argument("--assignee-account-id", required=True,
                   help='Atlassian accountId of the target assignee '
                        '(e.g. "712020:5cf4b2db-f12d-4739-867d-9fe8ecb66d54"). '
                        'Used in the JQL the inferencer constructs.')
    # --codebase is the canonical name (matches scripts 1-3); --workspace is an
    # accepted alias for backward compatibility with existing live invocations.
    p.add_argument("--codebase", "--workspace",
                   dest="workspace", required=True,
                   help="Local checkout path of the target repo (alias: --workspace).")
    p.add_argument("--num-workers", type=int, default=4,
                   help="Number of concurrent task workers (default 4).")
    p.add_argument("--max-parallel-inferencers", type=int, default=2,
                   help="Max concurrent RovoDevCliInferencer instances (default 2). "
                        "Each inferencer run can take 5-30 minutes, so keep this low.")
    p.add_argument("--epic-poll-interval-seconds", type=int, default=600,
                   help="Epic polling interval (default 600s / 10min). HARD FLOOR "
                        "is MIN_EPIC_POLL_SECONDS (180s / 3min) — values below "
                        "the floor are clamped UP and a warning is logged. "
                        "Each poll spawns an inferencer call (~$0.10-0.30).")
    p.add_argument("--pr-poll-interval-seconds", type=int, default=1800,
                   help="Per-PR polling interval (default 1800s / 30min). HARD FLOOR "
                        "is MIN_PR_POLL_SECONDS (900s / 15min) — values below "
                        "the floor are clamped UP and a warning is logged. "
                        "CI build cycles are typically 10-30 min, so polling more "
                        "often is wasted cost.")
    p.add_argument("--runtime-root", default=None,
                   help="Override the AI-employee home (default: $AI_EMPLOYEE_HOME or ~/.ai-employee). "
                        "Ignored if --runtime-base-dir is set.")
    p.add_argument("--workstream-slug", default=None,
                   help="Override the auto-derived workstream slug "
                        "(default: kebab-case --codebase basename).")
    p.add_argument("--runtime-base-dir", default=None,
                   help="Where per-run inferencer debug logs are written "
                        "(default: <module>/_runtime). One subdirectory per run.")
    p.add_argument("--no-runtime-logs", action="store_true",
                   help="Disable per-call inferencer logging (prompts, stream chunks, sentinels). "
                        "Useful for tight-loop tests where disk I/O is unwanted.")
    p.add_argument("--max-runtime-call-dirs", type=int, default=1000,
                   help="Defense G-3: hard cap on the number of per-call dirs that "
                        "the runtime workspace will create. Above this, per-call logging "
                        "is silently disabled (orchestrator continues; disk is protected). "
                        "Default 1000 — generous for normal runs (10 issues × 100 polls).")
    p.add_argument("--state-path", default="./.state/queue.json",
                   help="JSON file for orchestrator state (default ./.state/queue.json).")
    p.add_argument("-v", "--verbose", action="store_true", help="Debug logging.")
    return p.parse_args()


async def _main_async() -> None:
    args = _parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    state = load_state(args.state_path)
    workspace_abs = os.path.abspath(args.workspace)

    # Create a per-run debug workspace (prompts, streaming logs, sentinels, meta).
    # Default: ~/.ai-employee/projects/<workstream>/_runtime/proposal_implementation/
    # (workstream derived from --codebase / --workspace basename).
    # Overrides:
    #   1. --runtime-base-dir (most specific)
    #   2. $AI_EMPLOYEE_HOME env var
    #   3. ~/.ai-employee (default)
    if args.runtime_base_dir:
        runtime_base = Path(args.runtime_base_dir)
    else:
        try:
            from openteam.use_cases._shared_runtime import resolve_project_root
            project_root = resolve_project_root(
                Path(workspace_abs),
                workstream_slug=getattr(args, "workstream_slug", None),
                runtime_root_override=Path(args.runtime_root) if getattr(args, "runtime_root", None) else None,
            )
            runtime_base = project_root / "_runtime" / "proposal_implementation"
            runtime_base.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            # Fallback to legacy in-package _runtime/ for resilience.
            logging.getLogger(__name__).warning(
                "Could not resolve project_root (%s); falling back to <module>/_runtime/.", e
            )
            runtime_base = Path(__file__).resolve().parent / "_runtime"
    runtime_ws = None
    if not args.no_runtime_logs:
        try:
            runtime_ws = RunWorkspace.create(
                runtime_base,
                max_call_dirs=args.max_runtime_call_dirs,
            )
            logging.getLogger(__name__).info("Runtime logs in: %s", runtime_ws.run_dir)
        except Exception as e:
            logging.getLogger(__name__).warning(
                "Failed to create runtime workspace (%s); continuing without per-call logs.", e
            )

    orch = Orchestrator(
        state=state,
        state_path=args.state_path,
        workspace_path=workspace_abs,
        num_workers=args.num_workers,
        max_parallel_inferencers=args.max_parallel_inferencers,
        runtime_ws=runtime_ws,
    )

    # Seed: Epic monitor (immediate first poll, then steady-state cadence)
    # + re-hydrate any PR monitors from prior state.
    #
    # `delay_seconds=0` lets the first poll run immediately (the dataclass
    # `_floor` helper preserves 0). `steady_state_delay_seconds` is what the
    # handler uses for subsequent re-enqueues — clamped to the per-task
    # MIN_*_POLL_SECONDS floor.
    seed: list = [
        MonitorEpicTask(
            epic_key=args.epic,
            assignee_hint=args.assignee_hint,
            assignee_account_id=args.assignee_account_id,
            workspace_path=workspace_abs,
            delay_seconds=0,  # immediate first poll
            steady_state_delay_seconds=args.epic_poll_interval_seconds,
        )
    ]
    for issue_key, rec in state.issue_to_pr.items():
        if issue_key in state.completed:
            continue
        seed.append(MonitorPRTask(
            issue_key=issue_key,
            pr_url=rec.pr_url,
            workspace_path=workspace_abs,
            delay_seconds=0,  # immediate first poll of rehydrated PR
            steady_state_delay_seconds=args.pr_poll_interval_seconds,
        ))

    install_sigint_handler(orch)
    await orch.start(seed)
    try:
        while True:
            await asyncio.sleep(5)
    except asyncio.CancelledError:
        pass


def main() -> None:
    try:
        asyncio.run(_main_async())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
