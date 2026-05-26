"""E2E test for the real /create_role command path.

Calls ``executor.execute()`` directly with arguments + session_context
dicts — the same entry point that MCP uses. Validates the FULL command
path including argument parsing, workspace resolution, yaml loading,
override construction, and result wrapping.

Usage::

    python -m test.openteam.resources.tools.create_role.test_create_role_through_yaml \
        --role-description "Senior Backend Engineer focused on microservices" \
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
@click.option("--role-description", "-r", required=True,
              help="Role to create — inline text or path to a .md/.txt file.")
@click.option("--max-facets", default=None, type=int,
              help="Override max_breakdown (default 8).")
@click.option("--output-dir", default=str(Path(__file__).resolve().parent / "_runtime"),
              type=click.Path())
@click.option("--log-level", type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
              default="INFO")
def main(role_description, max_facets, output_dir, log_level):
    """Run /create_role via executor.execute() — real command path."""

    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    # Resolve role description (file or inline)
    role_desc_path = Path(role_description)
    if role_desc_path.is_file():
        role_description = role_desc_path.read_text(encoding="utf-8")
        click.echo(f"Role description from file: {role_desc_path} ({len(role_description)} chars)")
    else:
        click.echo(f"Role description (inline): {role_description[:80]}...")

    # Workspace
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    workspace = Path(output_dir) / timestamp
    workspace.mkdir(parents=True, exist_ok=True)

    # =====================================================================
    # Build arguments + session_context — same shape as MCP passes
    # =====================================================================
    arguments = {"role_description": role_description}
    if max_facets is not None:
        arguments["--max-facets"] = max_facets

    session_context = {
        "working_dir": str(workspace),
        "interactive": None,
        "task_id": f"test-create-role-{timestamp}",
        "cloud_id": os.environ.get("ROVOCHAT_CLOUD_ID", ""),
        "uct_token": os.environ.get("ROVOCHAT_UCT_TOKEN"),
        "email": os.environ.get("JIRA_EMAIL"),
    }

    # Save request for reference
    (workspace / "request.txt").write_text(role_description, encoding="utf-8")
    (workspace / "config.json").write_text(json.dumps({
        "arguments": {k: v for k, v in arguments.items() if k != "role_description"},
        "role_description_length": len(role_description),
        "timestamp": timestamp,
    }, indent=2))

    # =====================================================================
    # Call the REAL execute() — same entry point as MCP
    # =====================================================================
    from openteam.server.resources.tools.create_role.executor import execute

    click.echo(f"\nRunning /create_role via execute()...")
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

    doc_path = result.context_updates.get("role_document_path")
    if doc_path and Path(doc_path).exists():
        click.echo(f"Role document: {doc_path} ({Path(doc_path).stat().st_size} bytes)")
    else:
        click.echo(f"WARNING: role_document_path missing or not found: {doc_path}")

    # Save summary
    artifacts_dir = workspace / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "summary.json").write_text(json.dumps({
        "mode": "real_execute",
        "elapsed_seconds": round(elapsed, 1),
        "output_length": len(str(result.result)),
        "context_updates": result.context_updates,
        "workspace": str(workspace),
    }, indent=2), encoding="utf-8")

    click.echo("")
    click.echo("=" * 60)
    click.echo("Create Role — Complete (via execute())")
    click.echo("=" * 60)
    click.echo(f"Elapsed:   {elapsed:.1f}s")
    click.echo(f"Document:  {doc_path}")
    click.echo(f"Workspace: {workspace}")
    click.echo("=" * 60)


if __name__ == "__main__":
    main()
