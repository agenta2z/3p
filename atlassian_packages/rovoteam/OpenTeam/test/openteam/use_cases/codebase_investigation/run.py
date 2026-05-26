"""Phase 1 prototype: codebase investigation.

Single-shot specialised script.  Required parameter: ``--codebase``.

Outputs land under ``~/.ai-employee/projects/<workstream>/`` with:

* ``artifacts/codebase_documentation/`` — durable, latest-only docs
* ``_runtime/codebase_investigation/run_<ts>_<uuid>/`` — full history (debug)

Override the workspace root via ``--runtime-root`` or the
``AI_EMPLOYEE_HOME`` environment variable.

Usage:
    python -m openteam.use_cases.codebase_investigation.run \\
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
except ImportError as exc:  # pragma: no cover - import-time only
    print(
        f"ERROR: cannot import RovoDevCliInferencer ({exc!s}). "
        "Make sure PYTHONPATH includes AgentFoundation/src.",
        file=sys.stderr,
    )
    raise

from openteam.use_cases._shared_runtime import (
    SingleShotRunWorkspace,
    parse_sentinel,
    promote_to_artifacts,
    sentinel_indicates_success,
    setup_run_workspace,
)

logger = logging.getLogger("codebase_investigation")

HERE = Path(__file__).parent
PROMPT_PATH = HERE / "prompts" / "investigate_codebase.md"
PHASE_NAME = "codebase"
SCRIPT_DIR_NAME = "codebase_investigation"
SENTINEL_COMPLETE = "INVESTIGATION_COMPLETE"


def _render_prompt(target_path: Path, output_docs_dir: Path) -> str:
    template = PROMPT_PATH.read_text(encoding="utf-8")
    return template.replace("{{TARGET_PATH}}", str(target_path)).replace(
        "{{OUTPUT_DOCS_DIR}}", str(output_docs_dir)
    )


async def _run_inferencer(prompt: str, target_path: Path, ws: SingleShotRunWorkspace) -> str:
    ws.prompt_path.write_text(prompt, encoding="utf-8")

    # Grant write access to the project root so create_file works for docs/runtime
    import json as _json
    _project_root_str = str(ws.project_root)
    _cfg_override = _json.dumps({
        "toolPermissions": {
            "allowedExternalPaths": [_project_root_str]
        }
    })
    inf = RovoDevCliInferencer(
        target_path=str(target_path),
        idle_timeout_seconds=900,
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
        prog="codebase_investigation",
        description="Phase 1 of code_optimization SOP — investigate a codebase end-to-end.",
    )
    parser.add_argument(
        "--codebase",
        required=True,
        type=Path,
        help="Absolute path to the codebase (or sub-tree) to investigate.",
    )
    parser.add_argument(
        "--runtime-root",
        type=Path,
        default=None,
        help="Override the AI-employee home (default: $AI_EMPLOYEE_HOME or ~/.ai-employee).",
    )
    parser.add_argument(
        "--workstream-slug",
        default=None,
        help="Override the auto-derived workstream slug (default: kebab-case codebase basename).",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    codebase = args.codebase.expanduser().resolve()
    if not codebase.exists():
        print(f"ERROR: codebase path does not exist: {codebase}", file=sys.stderr)
        return 2

    ws = setup_run_workspace(
        codebase=codebase,
        phase_name=PHASE_NAME,
        script_dir_name=SCRIPT_DIR_NAME,
        workstream_slug=args.workstream_slug,
        runtime_root_override=args.runtime_root,
    )
    ws.write_run_meta(extra={"target_codebase": str(codebase)})
    ws.write_call_meta(extra={"target_codebase": str(codebase)})
    logger.info("Project root: %s", ws.project_root)
    logger.info("Run dir     : %s", ws.run_dir)
    logger.info("Call dir    : %s", ws.call_dir)
    logger.info("Artifacts   : %s (will be (over)written on success)", ws.artifacts_dir)

    prompt = _render_prompt(target_path=codebase, output_docs_dir=ws.docs_dir)
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
