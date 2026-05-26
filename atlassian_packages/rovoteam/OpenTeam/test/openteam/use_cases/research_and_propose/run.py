"""Phase 3 prototype: research, proposal & Jira Epic creation.

Single-shot specialised script.  Required parameter: ``--codebase``.

Auto-discovers Phase-1 and Phase-2 outputs from
``~/.ai-employee/projects/<workstream>/artifacts/`` (with backward-compat
fallback to the legacy in-package ``_runtime/`` locations).

Creates a Jira Epic + child issues via the inferencer's Atlassian MCP
tools (no direct MCP calls from this script).  Writes the proposal to
``~/.ai-employee/projects/<workstream>/artifacts/proposals/``.

Usage:
    python -m openteam.use_cases.research_and_propose.run \\
        --codebase /path/to/repo
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

try:
    from agent_foundation.common.inferencers.agentic_inferencers.external.rovodev.rovodev_cli_inferencer import (  # noqa: E501
        RovoDevCliInferencer,
    )
except ImportError as exc:  # pragma: no cover
    print(
        f"ERROR: cannot import RovoDevCliInferencer ({exc!s}). "
        "Make sure PYTHONPATH includes AgentFoundation/src.",
        file=sys.stderr,
    )
    raise

from openteam.use_cases._shared_runtime import (
    SingleShotRunWorkspace,
    autodiscover_phase_artifacts,
    parse_sentinel,
    promote_to_artifacts,
    sentinel_indicates_success,
    setup_run_workspace,
    workstream_slug_from_codebase,
)

logger = logging.getLogger("research_and_propose")

HERE = Path(__file__).parent
PROMPT_PATH = HERE / "prompts" / "research_propose_and_create_epic.md"
PHASE_NAME = "epic_creation"
SCRIPT_DIR_NAME = "research_and_propose"
SENTINEL_COMPLETE = "EPIC_CREATION_COMPLETE"

# Legacy in-package runtime locations (for backward-compat docs discovery).
LEGACY_PHASE1_IN_PACKAGE_RUNTIME = HERE.parent / "codebase_investigation" / "_runtime"
LEGACY_PHASE2_IN_PACKAGE_RUNTIME = HERE.parent / "system_and_signals_investigation" / "_runtime"

DEFAULT_JIRA_PROJECT = "AI"
# AI Lab board on the Atlassian hello instance — issues with project_key=AI
# automatically appear here via the board's JQL filter.
DEFAULT_JIRA_BOARD_URL = "https://hello.atlassian.net/jira/software/projects/AI/boards/22269"
DEFAULT_ASSIGNEE_ACCOUNT_ID = "712020:5cf4b2db-f12d-4739-867d-9fe8ecb66d54"


def _default_workstream_label(codebase: Path) -> str:
    """Build a kebab-case label like 'conversational-ai-platform-optimization'."""
    slug = workstream_slug_from_codebase(codebase)
    return f"{slug}-optimization"


def _render_prompt(
    target_path: Path,
    codebase_docs: Path | None,
    signals_docs: Path | None,
    output_docs_dir: Path,
    jira_project: str,
    jira_board_url: str,
    workstream_label: str,
    assignee_account_id: str,
) -> str:
    template = PROMPT_PATH.read_text(encoding="utf-8")
    return (
        template.replace("{{TARGET_PATH}}", str(target_path))
        .replace("{{CODEBASE_DOCS_DIR}}", str(codebase_docs) if codebase_docs else "(no Phase-1 docs found)")
        .replace("{{SIGNALS_DOCS_DIR}}", str(signals_docs) if signals_docs else "(no Phase-2 docs found)")
        .replace("{{OUTPUT_DOCS_DIR}}", str(output_docs_dir))
        .replace("{{JIRA_PROJECT_KEY}}", jira_project)
        .replace("{{JIRA_BOARD_URL}}", jira_board_url)
        .replace("{{WORKSTREAM_LABEL}}", workstream_label)
        .replace("{{ASSIGNEE_ACCOUNT_ID}}", assignee_account_id)
    )


async def _run_inferencer(prompt: str, target_path: Path, ws: SingleShotRunWorkspace) -> str:
    ws.prompt_path.write_text(prompt, encoding="utf-8")

    # Grant write access to the project root so create_file works for docs/runtime
    import json as _json
    _cfg_override = _json.dumps({
        "toolPermissions": {
            "allowedExternalPaths": [str(ws.project_root)]
        }
    })
    inf = RovoDevCliInferencer(
        target_path=str(target_path),
        idle_timeout_seconds=1200,
        tool_use_idle_timeout_seconds=1800,
        output_file=str(ws.clean_output_path),
        config_override=_cfg_override,
    )
    logger.info("Inferencer kicked off — streaming to %s", ws.stream_log_path)

    with ws.stream_log_path.open("w", encoding="utf-8") as fh:
        async for chunk in inf.ainfer_streaming(prompt):
            text = getattr(chunk, "text", None) or str(chunk)
            if text:
                fh.write(text)
                fh.flush()

    try:
        return ws.clean_output_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return getattr(inf, "_last_clean_output", "") or ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="research_and_propose",
        description="Phase 3 of code_optimization SOP — research, proposal & Jira Epic creation.",
    )
    parser.add_argument(
        "--codebase",
        required=True,
        type=Path,
        help="Absolute path to the codebase under investigation.",
    )
    parser.add_argument("--codebase-docs", type=Path, default=None,
                        help="Optional Phase-1 docs path (auto-discovered otherwise).")
    parser.add_argument("--signals-docs", type=Path, default=None,
                        help="Optional Phase-2 docs path (auto-discovered otherwise).")
    parser.add_argument("--jira-project", default=DEFAULT_JIRA_PROJECT,
                        help=f"Jira project key (default: {DEFAULT_JIRA_PROJECT}).")
    parser.add_argument("--jira-board-url", default=DEFAULT_JIRA_BOARD_URL,
                        help=f"Jira board UI URL where the new Epic + children will appear "
                             f"(informational; default: AI Lab board {DEFAULT_JIRA_BOARD_URL}).")
    parser.add_argument("--workstream-label", default=None,
                        help="Shared workstream label (default: <codebase-basename>-optimization).")
    parser.add_argument("--assignee-account-id", default=DEFAULT_ASSIGNEE_ACCOUNT_ID,
                        help=f"AAID for issue Reporter (default: {DEFAULT_ASSIGNEE_ACCOUNT_ID}).")
    parser.add_argument("--runtime-root", type=Path, default=None,
                        help="Override the AI-employee home (default: $AI_EMPLOYEE_HOME or ~/.ai-employee).")
    parser.add_argument("--workstream-slug", default=None,
                        help="Override the auto-derived workstream slug.")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    codebase = args.codebase.expanduser().resolve()
    if not codebase.exists():
        print(f"ERROR: codebase path does not exist: {codebase}", file=sys.stderr)
        return 2

    codebase_docs = (
        args.codebase_docs.expanduser().resolve()
        if args.codebase_docs
        else autodiscover_phase_artifacts(
            codebase=codebase,
            phase_name="codebase",
            workstream_slug=args.workstream_slug,
            runtime_root_override=args.runtime_root,
            legacy_in_package_runtime_root=LEGACY_PHASE1_IN_PACKAGE_RUNTIME,
        )
    )
    signals_docs = (
        args.signals_docs.expanduser().resolve()
        if args.signals_docs
        else autodiscover_phase_artifacts(
            codebase=codebase,
            phase_name="signals",
            workstream_slug=args.workstream_slug,
            runtime_root_override=args.runtime_root,
            legacy_in_package_runtime_root=LEGACY_PHASE2_IN_PACKAGE_RUNTIME,
        )
    )

    if codebase_docs:
        logger.info("Phase-1 docs: %s", codebase_docs)
    else:
        logger.warning("No Phase-1 docs found — proposal quality will be lower.")
    if signals_docs:
        logger.info("Phase-2 docs: %s", signals_docs)
    else:
        logger.warning("No Phase-2 docs found — proposal will lack runtime grounding.")

    workstream_label = args.workstream_label or _default_workstream_label(codebase)
    logger.info("Workstream label: %s", workstream_label)
    logger.info("Jira project key: %s", args.jira_project)
    logger.info("Jira board URL:   %s", args.jira_board_url)
    logger.info("Reporter AAID    : %s", args.assignee_account_id)

    ws = setup_run_workspace(
        codebase=codebase,
        phase_name=PHASE_NAME,
        script_dir_name=SCRIPT_DIR_NAME,
        workstream_slug=args.workstream_slug,
        runtime_root_override=args.runtime_root,
    )
    extra_meta = {
        "target_codebase": str(codebase),
        "phase1_docs": str(codebase_docs) if codebase_docs else None,
        "phase2_docs": str(signals_docs) if signals_docs else None,
        "jira_project": args.jira_project,
        "jira_board_url": args.jira_board_url,
        "workstream_label": workstream_label,
    }
    ws.write_run_meta(extra=extra_meta)
    ws.write_call_meta(extra=extra_meta)
    logger.info("Project root: %s", ws.project_root)
    logger.info("Run dir     : %s", ws.run_dir)
    logger.info("Artifacts   : %s (will be (over)written on success)", ws.artifacts_dir)

    prompt = _render_prompt(
        target_path=codebase,
        codebase_docs=codebase_docs,
        signals_docs=signals_docs,
        output_docs_dir=ws.docs_dir,
        jira_project=args.jira_project,
        jira_board_url=args.jira_board_url,
        workstream_label=workstream_label,
        assignee_account_id=args.assignee_account_id,
    )
    clean_output = asyncio.run(_run_inferencer(prompt, codebase, ws))

    sentinel = parse_sentinel(clean_output)
    logger.info("Final sentinel: %s", sentinel)

    promoted = None
    if sentinel_indicates_success(sentinel, SENTINEL_COMPLETE):
        try:
            promoted = promote_to_artifacts(ws)
            logger.info("Promoted to: %s", promoted)
        except FileNotFoundError as exc:
            logger.warning("Artifact promotion skipped: %s", exc)

    print("\n=== Run complete ===")
    print(f"Project root: {ws.project_root}")
    print(f"Run dir     : {ws.run_dir}")
    print(f"Docs (run)  : {ws.docs_dir}")
    print(f"Artifacts   : {promoted if promoted else '(not promoted — sentinel was ' + sentinel + ')'}")
    print(f"Status      : {sentinel}")
    return 0 if promoted is not None else 1


if __name__ == "__main__":
    sys.exit(main())
