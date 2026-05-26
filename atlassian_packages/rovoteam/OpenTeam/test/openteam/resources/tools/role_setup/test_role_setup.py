"""Manual E2E test script for the role_setup tool.

Use Python 3.11+ (e.g. ``/opt/homebrew/anaconda3/bin/python``); macOS CLI Python 3.9
lacks ``StrEnum`` and may miss dependencies (e.g. PyYAML).

Uses a nested ``BreakdownThenAggregateInferencer`` to:
1. Analyze a role document and identify missing skills/tools
2. For each missing skill/tool, run a full creation pipeline (breakdown → research → synthesis)
3. Produce a comprehensive Role Setup Report

Usage (UCT auth)::

    python -m test.openteam.resources.tools.role_setup.test_role_setup \
        --role-document /path/to/program_manager_role.md \
        --cloud-id <cloud-id> \
        --uct-token <token>

Usage (Basic Auth)::

    python -m test.openteam.resources.tools.role_setup.test_role_setup \
        --role-document /path/to/program_manager_role.md \
        --email user@example.com \
        --api-token <api-token> \
        --base-url https://mysite.atlassian.net

Usage (env vars)::

    export ROVOCHAT_CLOUD_ID=...
    export ROVOCHAT_UCT_TOKEN=...
    python -m test.openteam.resources.tools.role_setup.test_role_setup \
        --role-document /path/to/program_manager_role.md
"""

import asyncio
import json
import logging
import os
import sys
import time

from python_utils.common_objects.debuggable import LoggerConfig
from python_utils.string_utils.formatting.template_manager import TemplateManager
from python_utils.io_utils.json_io import JsonLogger, SpaceExtMode
from datetime import datetime
from pathlib import Path

import click

logger = logging.getLogger(__name__)


def _run_async_with_forced_cleanup(coro, cleanup_timeout: float = 15.0):
    """Run an async coroutine and force-exit event loop cleanup.

    ``asyncio.run()`` can hang indefinitely during its cleanup phase
    (``shutdown_asyncgens()`` / ``shutdown_default_executor()``) when
    workers leave unclosed async resources (e.g., httpx connection pools,
    subprocess pipe transports held by child processes like MCP servers).

    This wrapper runs the coroutine in a background thread.  Once the
    coroutine completes, the main thread gets the result immediately.
    Event loop cleanup is attempted with a timeout — if it hangs, we
    force-close the loop and continue.

    Args:
        coro: The coroutine to run.
        cleanup_timeout: Max seconds for event loop cleanup after the
            coroutine returns.

    Returns:
        The coroutine's return value.
    """
    import threading

    result_holder = {}
    work_done = threading.Event()

    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result_holder["result"] = loop.run_until_complete(coro)
        except Exception as e:
            result_holder["exception"] = e
        finally:
            # Signal that the coroutine is done (before cleanup)
            work_done.set()

            # Best-effort cleanup — may hang, but that's OK (daemon thread)
            try:
                to_cancel = asyncio.all_tasks(loop)
                for task in to_cancel:
                    task.cancel()
                if to_cancel:
                    loop.run_until_complete(
                        asyncio.wait_for(
                            asyncio.gather(*to_cancel, return_exceptions=True),
                            timeout=cleanup_timeout,
                        )
                    )
            except Exception:
                pass
            try:
                loop.run_until_complete(
                    asyncio.wait_for(loop.shutdown_asyncgens(), timeout=cleanup_timeout)
                )
            except Exception:
                pass
            loop.close()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    # Wait for the coroutine to complete (not for cleanup)
    work_done.wait()

    if "exception" in result_holder:
        raise result_holder["exception"]
    return result_holder.get("result")


def _extract_aggregator_result(result) -> str:
    """Extract the aggregator output from a BTA ainfer() result.

    BTA._infer returns a tuple from WorkGraph._run() — one element per
    start-node (worker).  In a diamond graph (N workers → 1 aggregator),
    only the *last* worker to trigger the aggregator carries the real
    aggregator result; the other (N-1) elements are None (aggregator
    was not yet ready when those workers' downstream calls returned).

    This helper walks the tuple and finds the actual aggregator result,
    preferring TerminalInferencerResponse.output over raw strings.
    """
    if result is None:
        return "(no result — workers ran independently)"

    if not isinstance(result, (tuple, list)):
        # Single result (e.g., tuple auto-unwrapped by _infer)
        if hasattr(result, "output") and result.output:
            return str(result.output)
        text = str(result).strip()
        return text if text else "(empty result)"

    # Tuple/list: find the non-None element with real content.
    # Prefer TerminalInferencerResponse objects (have .output attribute).
    best = None
    best_len = 0
    for i, r in enumerate(result):
        if r is None:
            continue
        if hasattr(r, "output") and r.output:
            text = str(r.output)
        else:
            text = str(r).strip()
        if not text:
            continue
        logger.debug(
            "Result element [%d]: type=%s, len=%d",
            i, type(r).__name__, len(text),
        )
        # Prefer TerminalInferencerResponse over plain strings
        is_response = hasattr(r, "output")
        is_best_response = hasattr(best, "output") if best is not None else False
        if is_response and not is_best_response:
            best = r
            best_len = len(text)
        elif (is_response == is_best_response) and len(text) > best_len:
            best = r
            best_len = len(text)

    if best is None:
        return "(all results were None or empty)"
    if hasattr(best, "output") and best.output:
        return str(best.output)
    return str(best).strip()


@click.command()
@click.option(
    "--role-document",
    "-r",
    required=True,
    type=click.Path(exists=True),
    help="Path to the role document markdown file.",
)
@click.option(
    "--cloud-id",
    envvar="ROVOCHAT_CLOUD_ID",
    default="",
    help="Atlassian Cloud ID. Required for UCT auth; optional for Basic Auth gateway.",
)
@click.option(
    "--uct-token",
    envvar="ROVOCHAT_UCT_TOKEN",
    default=None,
    help="UCT authentication token.",
)
@click.option(
    "--email",
    envvar="JIRA_EMAIL",
    default=None,
    help="Email for Basic Auth (alternative to UCT).",
)
@click.option(
    "--api-token",
    envvar="JIRA_API_TOKEN",
    default=None,
    help="API token for Basic Auth (alternative to UCT).",
)
@click.option(
    "--base-url",
    envvar="ROVOCHAT_BASE_URL",
    default=None,
    help="RovoChat API base URL override.",
)
@click.option(
    "--agent-named-id",
    default=None,
    help="Route to a specific Rovo agent by named ID.",
)
@click.option(
    "--max-facets",
    default=8,
    type=int,
    help="Maximum setup tasks from outer breakdown (default 8).",
)
@click.option(
    "--max-inner-facets",
    default=5,
    type=int,
    help="Maximum research facets per inner breakdown (default 5).",
)
@click.option(
    "--aggregator-type",
    type=click.Choice(["rovochat", "rovodev"]),
    default="rovochat",
    help="Aggregator backend: rovochat (API) or rovodev (local CLI).",
)
@click.option(
    "--aggregator-working-dir",
    default=None,
    type=click.Path(),
    help="Working directory for RovoDevCliInferencer aggregator.",
)
@click.option(
    "--output-dir",
    default=str(Path(__file__).resolve().parent / "_runtime"),
    type=click.Path(),
    help="Workspace directory. Default: test/.../role_setup/_runtime/<timestamp>/",
)
@click.option(
    "--templates-dir",
    default=None,
    type=click.Path(exists=True),
    help="Override path to prompt templates directory.",
)
@click.option(
    "--breakdown-only",
    is_flag=True,
    default=False,
    help="Run only the outer breakdown step (identify setup tasks). Skip workers and aggregation.",
)
@click.option("--subtask-breakdown-only", is_flag=True, default=False, help="Run inner BTA breakdown only for a specific subtask (no workers, no aggregation)")
@click.option("--run-subtask", is_flag=True, default=False, help="Run full inner BTA for a specific subtask (breakdown + workers). Use --disable-subtask-aggregator to skip aggregation.")
@click.option("--breakdown-file", default=None, type=click.Path(), help="Path to outer breakdown output file (for --subtask-breakdown-only / --run-subtask)")
@click.option("--subtask-index", default=1, type=int, help="1-based subtask index (for --subtask-breakdown-only / --run-subtask)")
@click.option("--inner-research-only", is_flag=True, default=False, help="Run inner BTA workers only (needs --breakdown-file with inner breakdown output)")
@click.option(
    "--resume-workspace",
    default=None,
    type=str,
    help=(
        "Inner BTA only: workspace root that contains this inner run's "
        "checkpoints/breakdown_result.json (research/investigation facet list). "
        "After a full nested role_setup run, use .../children/worker_<i>/ — "
        "not the outer experiment root (that file is the outer breakdown)."
    ),
)
@click.option("--disable-subtask-aggregator", is_flag=True, default=False, help="Skip inner (subtask-level) aggregation phase (run breakdown + workers only). For --run-subtask mode.")
@click.option(
    "--tools-file",
    default=None,
    type=click.Path(exists=True),
    help="Path to a file listing available tools/skills. Defaults to loading from AgentFoundation registry.",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    default="INFO",
    help="Python logging level.",
)
def main(
    role_document: str,
    cloud_id: str,
    uct_token: str | None,
    email: str | None,
    api_token: str | None,
    base_url: str | None,
    agent_named_id: str | None,
    max_facets: int,
    max_inner_facets: int,
    aggregator_type: str,
    aggregator_working_dir: str | None,
    output_dir: str | None,
    templates_dir: str | None,
    breakdown_only: bool,
    subtask_breakdown_only: bool,
    run_subtask: bool,
    breakdown_file: str | None,
    subtask_index: int,
    inner_research_only: bool,
    resume_workspace: str | None,
    disable_subtask_aggregator: bool,
    tools_file: str | None,
    log_level: str,
) -> None:
    """Run the role_setup tool end-to-end via nested BreakdownThenAggregateInferencer."""

    # 1. Configure logging
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    # 2. Validate auth (not required for breakdown-only with RovoDevCli)
    has_uct = bool(uct_token)
    has_basic = bool(email and api_token)
    if not has_uct and not has_basic and not breakdown_only and not subtask_breakdown_only and not inner_research_only and not resume_workspace:
        click.echo(
            "ERROR: Provide either --uct-token or (--email + --api-token) for authentication.",
            err=True,
        )
        sys.exit(1)
    if has_uct and not cloud_id:
        click.echo(
            "ERROR: --cloud-id is required when using UCT auth.",
            err=True,
        )
        sys.exit(1)

    # 3. Resolve role document path
    role_document_path = str(Path(role_document).resolve())
    role_doc_text = Path(role_document_path).read_text(encoding="utf-8")
    logger.info("Role document: %s (%d chars)", role_document_path, len(role_doc_text))

    # 4. Set up workspace (skip for resume mode — reuse existing)
    if resume_workspace:
        resume_ws = Path(resume_workspace)
        if not resume_ws.is_absolute():
            resume_ws = Path(__file__).resolve().parent / "_runtime" / resume_workspace
        if not resume_ws.exists():
            click.echo(f"ERROR: Workspace not found: {resume_ws}", err=True)
            sys.exit(1)
        workspace = resume_ws
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        workspace = (Path(output_dir) / timestamp).resolve()

    from agent_foundation.common.inferencers.inferencer_workspace import InferencerWorkspace

    ws = InferencerWorkspace(root=str(workspace))
    ws.ensure_dirs("_runtime")
    artifacts_dir = Path(ws.artifacts_dir)
    outputs_dir = Path(ws.outputs_dir)
    (workspace / "_runtime" / "inferencer_cache").mkdir(parents=True, exist_ok=True)
    (workspace / "_runtime" / "tmp_output_files").mkdir(parents=True, exist_ok=True)

    # Save config
    config = {
        "role_document": role_document_path,
        "role_document_length": len(role_doc_text),
        "cloud_id": cloud_id,
        "auth_mode": "uct" if has_uct else "basic",
        "base_url": base_url,
        "agent_named_id": agent_named_id,
        "max_facets": max_facets,
        "max_inner_facets": max_inner_facets,
        "aggregator_type": aggregator_type,
        "timestamp": workspace.name,  # folder name is the timestamp
        "mode": "resume" if resume_workspace else "new",
    }
    # Preserve task_query in config for resume (so aggregator knows the
    # original task, not the literal string "resume")
    if resume_workspace:
        prev_config_path = Path(resume_workspace) / "config.json"
        if prev_config_path.exists():
            prev_config = json.loads(prev_config_path.read_text())
            if "task_query" in prev_config:
                config["task_query"] = prev_config["task_query"]
    (workspace / "config.json").write_text(json.dumps(config, indent=2))
    logger.info("Workspace: %s", workspace)

    # 5. Validate imports
    try:
        from openteam.server.resources.tools.role_setup.executor import (
            build_breakdown_only,
            build_subtask_breakdown_only,
            build_inner_research_only,
            build_role_setup_inferencer,
        )
    except ImportError as e:
        click.echo(
            f"ERROR: Failed to import role_setup executor. "
            f"Ensure AgentFoundation and OpenTeam are installed.\n  {e}",
            err=True,
        )
        sys.exit(1)

    # 6. Build inferencer
    role_name = role_doc_text.split("\n")[0].strip("# ").strip()
    streaming_cache_dir = str(workspace / "_runtime" / "inferencer_cache")

    # Set up structured session logging
    json_logger = JsonLogger(
        file_path=str(workspace / "logs" / "session.jsonl"),
        append=True,
        is_artifact=True,
        parts_min_size=0,
        space_ext_mode=SpaceExtMode.MOVE,
        parts_file_namer=lambda obj: obj.get("type", "") if isinstance(obj, dict) else "",
    )
    inferencer_logger = [
        (json_logger, LoggerConfig(pass_item_key_as="parts_key_path_root")),
    ]

    if breakdown_only:
        click.echo(f"[Breakdown Only] Analyzing role: {role_name[:80]}")
        click.echo(f"Auth mode: {'UCT' if has_uct else 'Basic Auth'}")
        click.echo("")

        inferencer, inference_input = build_breakdown_only(
            role_document_path=role_document_path,
            cloud_id=cloud_id,
            uct_token=uct_token,
            email=email,
            api_token=api_token,
            base_url=base_url,
            agent_named_id=agent_named_id,
            templates_dir=templates_dir,
            tools_file=tools_file,
            streaming_cache_dir=streaming_cache_dir,
            workspace=str(workspace),
            inferencer_logger=inferencer_logger,
        )
    elif resume_workspace:
        # Inner-BTA resume only: we build a single inner BreakdownThenAggregateInferencer
        # whose workspace_root is this folder. Its checkpoint is inner breakdown (facet
        # sub_queries). Nested outer runs store that under children/worker_<i>/;
        # the outer experiment root has a different breakdown_result.json (role tasks).

        # Verify inner breakdown checkpoint exists
        ckpt = workspace / "checkpoints" / "breakdown_result.json"
        if not ckpt.exists():
            click.echo(f"ERROR: No breakdown checkpoint at {ckpt}", err=True)
            sys.exit(1)

        import json as _json
        saved = _json.loads(ckpt.read_text())
        sub_queries = saved.get("sub_queries", saved) if isinstance(saved, dict) else saved
        click.echo(f"[Resume] Workspace: {resume_ws}")
        click.echo(f"[Resume] {len(sub_queries)} sub_queries from checkpoint")
        click.echo(f"Auth: {'UCT' if has_uct else 'Basic' if has_basic else 'None (local only)'}")
        click.echo("")

        # Build the same inner BTA that was used for breakdown — just with resume enabled
        from openteam.server.resources.tools.role_setup.executor import (
            _aggregation_instructions_from_path,
            _build_inner_bta,
            _load_variable_file,
            _PROMPT_TEMPLATES_ROOT,
            _APP_TOOLS_DIR,
            _APP_SKILLS_DIR,
            _render_variable_file,
            format_available_tools_and_skills,
        )

        role_doc_text = Path(role_document_path).read_text(encoding="utf-8")
        role_name = role_doc_text.split("\n")[0].strip("# ").strip()
        role_doc_path_resolved = str(Path(role_document_path).resolve())
        available_tools_text = format_available_tools_and_skills(
            extra_tool_dirs=[_APP_TOOLS_DIR], extra_skill_dirs=[_APP_SKILLS_DIR]
        )

        templates_root = Path(templates_dir) if templates_dir else _PROMPT_TEMPLATES_ROOT
        tm = TemplateManager(
            templates=str(templates_root),
            active_template_type="main",
            predefined_variables=True,
        )

        inner_breakdown_preamble = _render_variable_file(
            "task_breakdown",
            "task_preamble",
            "skill_tool_creation",
            role_name=role_name,
            role_doc_path=role_doc_path_resolved,
            available_tools_skills=available_tools_text,
        )
        inner_research_preamble = _load_variable_file(
            "deep_research", "task_preamble", "skill_tool_creation"
        )
        inner_synthesis_instructions = _aggregation_instructions_from_path(
            templates_root,
            "implementation",
            "task_instructions",
            "skill_tool_creation",
        )

        rovo_kwargs = dict(
            cloud_id=cloud_id, uct_token=uct_token, email=email,
            api_token=api_token, base_url=base_url, agent_named_id=agent_named_id,
        )

        streaming_cache_dir = str(workspace / "_runtime" / "inferencer_cache")

        # Recover the original subtask query from config (so the aggregator
        # sees the real task description, not the literal string "resume").
        _prev_config_path = Path(resume_workspace) / "config.json"
        _prev_config = json.loads(_prev_config_path.read_text()) if _prev_config_path.exists() else {}
        _task_query = _prev_config.get("task_query", "resume")
        _subtask_index = _prev_config.get("subtask_index", 0)
        if _task_query == "resume":
            click.echo(
                "WARNING: No task_query found in config.json — aggregator "
                "will receive 'resume' as the task description. Re-run with "
                "--run-subtask to save the subtask query first.",
                err=True,
            )

        bta = _build_inner_bta(
            sub_query=_task_query,
            index=_subtask_index,
            tm=tm,
            rovo_kwargs=rovo_kwargs,
            inner_breakdown_preamble=inner_breakdown_preamble,
            inner_research_preamble=inner_research_preamble,
            inner_synthesis_instructions=inner_synthesis_instructions,
            max_inner_facets=8,
            aggregator_type="rovodev",
            aggregator_working_dir=str(workspace),
            streaming_cache_dir=streaming_cache_dir,
            breakdown_only=False,
            workspace=str(workspace),
            inferencer_logger=inferencer_logger,
            templates_root=templates_root,
            role_name=role_name,
            role_doc_path=role_doc_path_resolved,
            available_tools_text=available_tools_text,
        )

        # Enable resume
        bta.resume_with_saved_results = True
        bta.enable_result_save = True

        for sq in sub_queries:
            if isinstance(sq, dict):
                tp = sq.get("args", {}).get("task_preamble", "?")
                desc = sq.get("query", "")[:60]
            else:
                tp = "str"
                desc = str(sq)[:60]
            click.echo(f"  [{tp}] {desc}...")

        click.echo(f"\nRunning BTA (resume=True, query={_task_query[:60]}...)...")
        start_time = time.time()
        result = _run_async_with_forced_cleanup(bta.ainfer(_task_query, inference_config={}))
        elapsed = time.time() - start_time

        result_text = _extract_aggregator_result(result)
        (workspace / "artifacts" / "resume_output.md").write_text(
            result_text[:50000], encoding="utf-8"
        )
        (workspace / "artifacts" / "summary.json").write_text(
            json.dumps({
                "mode": "resume",
                "workspace": str(workspace),
                "sub_queries_count": len(sub_queries),
                "duration_seconds": round(elapsed, 1),
            }, indent=2),
            encoding="utf-8",
        )

        click.echo(f"\nResume complete in {elapsed:.1f}s")
        click.echo(f"Workspace: {workspace}")
        sys.exit(0)

    elif inner_research_only:
        if not breakdown_file:
            click.echo("ERROR: --breakdown-file is required with --inner-research-only", err=True)
            sys.exit(1)

        click.echo(f"[Inner Research] Workers from: {breakdown_file}")
        click.echo(f"Auth: {'UCT' if has_uct else 'Basic' if has_basic else 'None (local only)'}")
        click.echo("")

        bta, sub_queries = build_inner_research_only(
            inner_breakdown_file=breakdown_file,
            role_document_path=role_document_path,
            cloud_id=cloud_id,
            uct_token=uct_token,
            email=email,
            api_token=api_token,
            base_url=base_url,
            agent_named_id=agent_named_id,
            templates_dir=templates_dir,
            streaming_cache_dir=streaming_cache_dir,
            workspace=str(workspace),
            inferencer_logger=inferencer_logger,
        )

        click.echo(f"Sub-queries: {len(sub_queries)}")
        for i, sq in enumerate(sub_queries):
            if isinstance(sq, dict):
                tp = sq.get("args", {}).get("task_preamble", "?")
                desc = sq.get("query", "")[:60]
            else:
                tp = "str"
                desc = str(sq)[:60]
            click.echo(f"  {i}: [{tp}] {desc}...")

        # Build diamond graph and run workers
        click.echo(f"\nRunning {len(sub_queries)} workers...")
        start_time = time.time()
        bta._build_diamond_graph(sub_queries)
        results = _run_async_with_forced_cleanup(bta.arun())
        elapsed = time.time() - start_time

        result_text = str(results)
        (workspace / "artifacts" / "inner_research_output.md").write_text(
            result_text, encoding="utf-8"
        )
        (workspace / "artifacts" / "summary.json").write_text(
            json.dumps({
                "mode": "inner_research_only",
                "breakdown_file": breakdown_file,
                "sub_queries_count": len(sub_queries),
                "result_length": len(result_text),
                "duration_seconds": round(elapsed, 1),
            }, indent=2),
            encoding="utf-8",
        )

        click.echo(f"\nInner research complete in {elapsed:.1f}s")
        click.echo(f"Output: {workspace / 'artifacts' / 'inner_research_output.md'}")
        sys.exit(0)

    elif run_subtask:
        if not breakdown_file:
            click.echo("ERROR: --breakdown-file is required with --run-subtask", err=True)
            sys.exit(1)

        mode_desc = "breakdown + workers" + (" (skip aggregation)" if disable_subtask_aggregator else " + aggregation")
        click.echo(f"[Run Subtask] Subtask {subtask_index} from: {breakdown_file}")
        click.echo(f"[Run Subtask] Mode: {mode_desc}")
        click.echo(f"Auth mode: {'UCT' if has_uct else 'Basic Auth'}")
        click.echo("")

        inferencer, inference_input = build_subtask_breakdown_only(  # inference_input = subtask_desc
            breakdown_file=breakdown_file,
            subtask_index=subtask_index,
            role_document_path=role_document_path,
            cloud_id=cloud_id,
            uct_token=uct_token,
            email=email,
            api_token=api_token,
            base_url=base_url,
            agent_named_id=agent_named_id,
            templates_dir=templates_dir,
            streaming_cache_dir=streaming_cache_dir,
            workspace=str(workspace),
            inferencer_logger=inferencer_logger,
        )
        # Override: run full inner BTA (breakdown + workers), not just breakdown
        inferencer.breakdown_only = False
        inferencer.disable_aggregator = disable_subtask_aggregator

        # Save subtask query to config so --resume-workspace can recover it
        config["task_query"] = inference_input
        config["subtask_index"] = subtask_index
        config["mode"] = "run_subtask"
        (workspace / "config.json").write_text(json.dumps(config, indent=2))

    elif subtask_breakdown_only:
        if not breakdown_file:
            click.echo("ERROR: --breakdown-file is required with --subtask-breakdown-only", err=True)
            sys.exit(1)

        click.echo(f"[Subtask Breakdown Only] Subtask {subtask_index} from: {breakdown_file}")
        click.echo(f"Auth mode: {'UCT' if has_uct else 'Basic Auth'}")
        click.echo("")

        inferencer, inference_input = build_subtask_breakdown_only(
            breakdown_file=breakdown_file,
            subtask_index=subtask_index,
            role_document_path=role_document_path,
            cloud_id=cloud_id,
            uct_token=uct_token,
            email=email,
            api_token=api_token,
            base_url=base_url,
            agent_named_id=agent_named_id,
            templates_dir=templates_dir,
            streaming_cache_dir=streaming_cache_dir,
            workspace=str(workspace),
            inferencer_logger=inferencer_logger,
        )

    else:
        click.echo(f"Setting up role: {role_name[:80]}")
        click.echo(f"Max outer facets: {max_facets}, inner facets: {max_inner_facets}")
        click.echo(f"Auth mode: {'UCT' if has_uct else 'Basic Auth'}")
        click.echo("")

        inferencer, inference_input = build_role_setup_inferencer(
            role_document_path=role_document_path,
            cloud_id=cloud_id,
            uct_token=uct_token,
            email=email,
            api_token=api_token,
            base_url=base_url,
            agent_named_id=agent_named_id,
            max_facets=max_facets,
            max_inner_facets=max_inner_facets,
            templates_dir=templates_dir,
            aggregator_type=aggregator_type,
            aggregator_working_dir=aggregator_working_dir or str(workspace),
            workspace=str(workspace),
            tools_file=tools_file,
        )

    # 7. Run inference
    start_time = time.time()
    try:
        result = _run_async_with_forced_cleanup(inferencer.ainfer(inference_input))
    except Exception:
        logger.exception("Inference failed")
        click.echo("ERROR: Inference failed. Check logs above.", err=True)
        sys.exit(1)
    elapsed = time.time() - start_time

    # 8. Save results
    logger.info("Result type: %s", type(result).__name__)
    result_text = _extract_aggregator_result(result)

    # Save output
    if breakdown_only:
        output_file = artifacts_dir / "breakdown_output.md"
        output_file.write_text(result_text)
        primary_deliverable = output_file
    else:
        from agent_foundation.common.response_parsers import extract_delimited
        clean_text = extract_delimited(result_text) if "<Response>" in result_text else result_text
        (artifacts_dir / "aggregator_raw_output.md").write_text(clean_text)

        deliverable_files = list(outputs_dir.rglob("skills/**/*.md")) + \
                           list(outputs_dir.rglob("tools/**/*"))
        if deliverable_files:
            logger.info(
                "Agent created %d deliverable(s): %s",
                len(deliverable_files),
                ", ".join(f.name for f in sorted(deliverable_files)),
            )
        else:
            logger.info("No deliverable files found in %s", outputs_dir)

        primary_deliverable = (
            sorted(deliverable_files)[-1]
            if deliverable_files
            else artifacts_dir / "aggregator_raw_output.md"
        )

    summary = {
        "role_document": role_document_path,
        "role_name": role_name,
        "mode": "breakdown_only" if breakdown_only else "full",
        "elapsed_seconds": round(elapsed, 1),
        "output_length": len(result_text),
        "workspace": str(workspace),
    }
    (artifacts_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    # 9. Print summary
    mode_label = "Breakdown" if breakdown_only else "Role Setup"
    click.echo("")
    click.echo("=" * 60)
    click.echo(f"{mode_label} — Complete")
    click.echo("=" * 60)
    click.echo(f"Role:          {role_name[:60]}")
    click.echo(f"Elapsed:       {elapsed:.1f}s")
    click.echo(f"Output length: {len(result_text)} chars")
    click.echo(f"Output:        {primary_deliverable}")
    click.echo(f"Workspace:     {workspace}")
    click.echo("=" * 60)


if __name__ == "__main__":
    main()
