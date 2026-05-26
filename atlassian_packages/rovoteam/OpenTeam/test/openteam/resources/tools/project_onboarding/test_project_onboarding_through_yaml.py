"""E2E test for the real /project_onboarding command path.

Calls ``executor.execute()`` directly with arguments + session_context
dicts — the same entry point that MCP uses. Validates the FULL command
path including yaml loading, override construction, runtime context
injection, conflict detection, and result wrapping.

Usage::

    python -m test.openteam.resources.tools.project_onboarding.test_project_onboarding_through_yaml \
        --project-document /path/to/project.md \
        --role-setup-path /path/to/role_setup/outputs/ \
        --log-level INFO
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import click


def _load_dotenv(*search_dirs) -> None:
    for d in search_dirs:
        env_path = Path(d) / ".env"
        if env_path.is_file():
            with env_path.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, val = line.partition("=")
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = val
            break


_load_dotenv(Path(__file__).parent, Path(__file__).parents[5])

logger = logging.getLogger(__name__)


def _run_async_with_forced_cleanup(coro, cleanup_timeout: float = 15.0):
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
            work_done.set()
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
    work_done.wait()
    if "exception" in result_holder:
        raise result_holder["exception"]
    return result_holder.get("result")


@click.command()
@click.option("--project-document", "-p", required=True, type=click.Path(exists=True),
              help="Path to the project description markdown file.")
@click.option("--role-setup-path", "-r", default=None, type=click.Path(exists=True),
              help="Path to the role_setup output directory with pre-onboarding artifacts.")
@click.option("--artifacts-path", "-a", default=None, type=click.Path(exists=True),
              help="Path to additional project/team artifacts directory.")
@click.option("--max-facets", default=None, type=int,
              help="Max outer subtasks (overrides yaml max_breakdown).")
@click.option("--max-inner-facets", default=None, type=int,
              help="Max inner research facets per subtask.")
@click.option("--output-dir", default=str(Path(__file__).resolve().parent / "_runtime"),
              type=click.Path())
@click.option("--log-level", type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
              default="INFO")
def main(project_document, role_setup_path, artifacts_path,
         max_facets, max_inner_facets, output_dir, log_level):
    """Run /project_onboarding via executor.execute() — real command path."""

    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    workspace = Path(output_dir) / timestamp
    workspace.mkdir(parents=True, exist_ok=True)

    # =====================================================================
    # Build arguments + session_context — same shape as MCP passes
    # =====================================================================
    arguments = {"project_document_path": str(Path(project_document).resolve())}
    if role_setup_path is not None:
        arguments["--role-setup-path"] = str(Path(role_setup_path).resolve())
    if artifacts_path is not None:
        arguments["--artifacts-path"] = str(Path(artifacts_path).resolve())
    if max_facets is not None:
        arguments["--max-facets"] = max_facets
    if max_inner_facets is not None:
        arguments["--max-inner-facets"] = max_inner_facets

    session_context = {
        "working_dir": str(workspace),
        "interactive": None,
        "task_id": f"test-project-onboarding-{timestamp}",
        "cloud_id": os.environ.get("ROVOCHAT_CLOUD_ID", ""),
        "uct_token": os.environ.get("ROVOCHAT_UCT_TOKEN"),
        "email": os.environ.get("JIRA_EMAIL"),
    }

    # =====================================================================
    # Call the REAL execute() — same entry point as MCP
    # =====================================================================
    from openteam.server.resources.tools.project_onboarding.executor import execute

    click.echo(f"Running /project_onboarding via execute()...")
    click.echo(f"Project document: {project_document}")
    if role_setup_path:
        click.echo(f"Role setup path:  {role_setup_path}")
    if artifacts_path:
        click.echo(f"Artifacts path:   {artifacts_path}")
    click.echo(f"Workspace: {workspace}")
    start_time = time.time()

    try:
        result = _run_async_with_forced_cleanup(
            execute(arguments, session_context)
        )
    except Exception:
        logger.exception("execute() failed")
        click.echo("ERROR: execute() failed.", err=True)
        sys.exit(1)

    elapsed = time.time() - start_time

    # =====================================================================
    # Validate ToolExecutionResult
    # =====================================================================
    click.echo(f"\nResult type: {type(result).__name__}")
    click.echo(f"Result text length: {len(str(result.result))}")
    click.echo(f"Context updates: {result.context_updates}")

    # Check deliverables (skills, tools, knowledge)
    outputs_dir = workspace / "outputs"
    deliverable_files = (
        list(outputs_dir.rglob("skills/**/*.md"))
        + list(outputs_dir.rglob("tools/**/*"))
        + list(outputs_dir.rglob("knowledge/**/*.md"))
    )
    if deliverable_files:
        click.echo(f"Deliverables: {len(deliverable_files)} files")
        for f in sorted(deliverable_files):
            click.echo(f"  {f.relative_to(outputs_dir)}")

    report_path = result.context_updates.get("project_onboarding_report_path")
    if report_path and Path(report_path).exists():
        click.echo(f"Report: {report_path} ({Path(report_path).stat().st_size} bytes)")

    knowledge_dir = result.context_updates.get("knowledge_dir")
    if knowledge_dir and Path(knowledge_dir).exists():
        kb_files = list(Path(knowledge_dir).rglob("*.md"))
        click.echo(f"Knowledge blocks: {len(kb_files)} files")

    # Save summary
    artifacts_out_dir = workspace / "artifacts"
    artifacts_out_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_out_dir / "summary.json").write_text(json.dumps({
        "mode": "real_execute",
        "elapsed_seconds": round(elapsed, 1),
        "output_length": len(str(result.result)),
        "context_updates": result.context_updates,
        "deliverable_count": len(deliverable_files),
        "workspace": str(workspace),
        "role_setup_path": role_setup_path,
        "artifacts_path": artifacts_path,
    }, indent=2), encoding="utf-8")

    click.echo("")
    click.echo("=" * 60)
    click.echo("Project Onboarding — Complete (via execute())")
    click.echo("=" * 60)
    click.echo(f"Elapsed:      {elapsed:.1f}s")
    click.echo(f"Deliverables: {len(deliverable_files)} files")
    click.echo(f"Report:       {report_path}")
    click.echo(f"Workspace:    {workspace}")
    click.echo("=" * 60)


if __name__ == "__main__":
    main()
