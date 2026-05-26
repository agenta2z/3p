"""Manual E2E test script for the create_role tool.

Uses ``BreakdownThenAggregateInferencer`` with ``RovoChatInferencer`` workers
to research role facets and produce a Role Responsibility Document.

Usage (UCT auth)::

    python -m test.resources.tools.create_role \
        --role-description "AI DevOps Engineer specializing in CI/CD" \
        --cloud-id <cloud-id> \
        --uct-token <token>

Usage (Basic Auth)::

    python -m test.resources.tools.create_role \
        --role-description "Senior ML Engineer for recommendation systems" \
        --email user@example.com \
        --api-token <api-token> \
        --base-url https://mysite.atlassian.net

Usage (env vars)::

    export ROVOCHAT_CLOUD_ID=...
    export ROVOCHAT_UCT_TOKEN=...
    python -m test.resources.tools.create_role \
        --role-description "Product Manager for developer tools"
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

logger = logging.getLogger(__name__)


@click.command()
@click.option(
    "--role-description",
    "-r",
    required=True,
    help="Role to create. Can be a string or a path to a file containing the description.",
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
    help="Maximum number of research facets (caps breakdown output).",
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
    help="Working directory for RovoDevCliInferencer aggregator. "
    "Defaults to the workspace root so checkpoint file paths resolve correctly.",
)
@click.option(
    "--output-dir",
    default=str(Path(__file__).resolve().parent / "_runtime"),
    type=click.Path(),
    help="Workspace directory. Default: test/.../create_role/_runtime/<timestamp>/",
)
@click.option(
    "--templates-dir",
    default=None,
    type=click.Path(exists=True),
    help="Override path to create_role prompt templates directory.",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    default="INFO",
    help="Python logging level.",
)
def main(
    role_description: str,
    cloud_id: str,
    uct_token: str | None,
    email: str | None,
    api_token: str | None,
    base_url: str | None,
    agent_named_id: str | None,
    max_facets: int,
    aggregator_type: str,
    aggregator_working_dir: str | None,
    output_dir: str | None,
    templates_dir: str | None,
    log_level: str,
) -> None:
    """Run the create_role tool end-to-end via BreakdownThenAggregateInferencer."""

    # 1. Configure logging
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    # 2. Validate auth
    has_uct = bool(uct_token)
    has_basic = bool(email and api_token)
    if not has_uct and not has_basic:
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

    # 3. Resolve role description (file or string)
    if os.path.isfile(role_description):
        logger.info("Reading role description from file: %s", role_description)
        role_description = Path(role_description).read_text().strip()

    # 4. Set up workspace
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    workspace = (Path(output_dir) / timestamp).resolve()

    from agent_foundation.common.inferencers.inferencer_workspace import InferencerWorkspace

    ws = InferencerWorkspace(root=str(workspace))
    ws.ensure_dirs("_runtime")  # outputs/, artifacts/, checkpoints/, logs/ + _runtime/
    artifacts_dir = Path(ws.artifacts_dir)
    outputs_dir = Path(ws.outputs_dir)  # InferencerWorkspace standard outputs/
    (workspace / "_runtime" / "inferencer_cache").mkdir(parents=True, exist_ok=True)
    (workspace / "_runtime" / "tmp_output_files").mkdir(parents=True, exist_ok=True)

    # Save config
    config = {
        "role_description": role_description,
        "cloud_id": cloud_id,
        "auth_mode": "uct" if has_uct else "basic",
        "base_url": base_url,
        "agent_named_id": agent_named_id,
        "max_facets": max_facets,
        "aggregator_type": aggregator_type,
        "timestamp": timestamp,
    }
    (workspace / "config.json").write_text(json.dumps(config, indent=2))
    (workspace / "request.txt").write_text(role_description)
    logger.info("Workspace: %s", workspace)

    # 5. Validate imports
    try:
        from openteam.server.resources.tools.create_role import (
            build_create_role_inferencer,
        )
    except ImportError as e:
        click.echo(
            f"ERROR: Failed to import create_role executor. "
            f"Ensure AgentFoundation is installed.\n  {e}",
            err=True,
        )
        sys.exit(1)

    # 6. Build inferencer
    logger.info("Building BreakdownThenAggregateInferencer pipeline...")
    inferencer = build_create_role_inferencer(
        cloud_id=cloud_id,
        uct_token=uct_token,
        email=email,
        api_token=api_token,
        base_url=base_url,
        agent_named_id=agent_named_id,
        max_facets=max_facets,
        templates_dir=templates_dir,
        aggregator_type=aggregator_type,
        aggregator_working_dir=aggregator_working_dir or str(workspace),
        workspace=str(workspace),
    )

    # 7. Run inference
    click.echo(f"Creating role: {role_description[:80]}...")
    click.echo(f"Max facets: {max_facets}")
    click.echo(f"Auth mode: {'UCT' if has_uct else 'Basic Auth'}")
    click.echo("")

    start_time = time.time()
    try:
        result = asyncio.run(inferencer.ainfer(role_description))
    except Exception:
        logger.exception("Inference failed")
        click.echo("ERROR: Inference failed. Check logs above.", err=True)
        sys.exit(1)
    elapsed = time.time() - start_time

    # 8. Save results
    # BTA may return:
    # - A string (simple case)
    # - A TerminalInferencerResponse (from RovoDevCliInferencer) — str() extracts .output
    # - A tuple/list (from WorkGraph collecting multiple results)
    #   In the tuple case, prefer TerminalInferencerResponse (aggregator output),
    #   then fall back to the longest non-empty string element.
    logger.info("Result type: %s", type(result).__name__)
    if isinstance(result, (tuple, list)):
        logger.info("Result is %s with %d elements", type(result).__name__, len(result))
        for i, r in enumerate(result):
            logger.info("  result[%d] type=%s len=%d", i, type(r).__name__, len(str(r)))
        result_text = ""
        # First: prefer TerminalInferencerResponse (aggregator output)
        for r in result:
            if hasattr(r, "output") and str(r).strip():
                result_text = str(r)
                logger.info("Using TerminalInferencerResponse element (%d chars)", len(result_text))
                break
        # Fallback: longest non-empty string
        if not result_text:
            for r in result:
                text = str(r).strip() if r is not None else ""
                if len(text) > len(result_text):
                    result_text = text
    else:
        result_text = str(result).strip() if result is not None else ""
    # Always save raw aggregator output to artifacts (audit trail)
    (artifacts_dir / "aggregator_raw_output.md").write_text(result_text)

    # Route deliverable based on aggregator type
    if aggregator_type == "rovodev":
        # Local agent — check if it created files in outputs/
        agent_files = list(outputs_dir.glob("*.md"))
        if agent_files:
            primary = sorted(agent_files)[-1]
            logger.info("Agent created deliverable: %s", primary.name)
        else:
            # Fallback — agent didn't write file, save raw output as deliverable
            logger.warning("Local agent did not create deliverable — using raw output")
            (outputs_dir / "role_document.md").write_text(result_text)
    else:
        # Cloud API — raw text IS the deliverable
        (outputs_dir / "role_document.md").write_text(result_text)

    # Determine primary deliverable path for summary
    deliverable_files = list(outputs_dir.glob("*.md"))
    primary_deliverable = sorted(deliverable_files)[-1] if deliverable_files else outputs_dir / "role_document.md"

    summary = {
        "role_description": role_description,
        "elapsed_seconds": round(elapsed, 1),
        "output_length": len(result_text),
        "workspace": str(workspace),
    }
    (artifacts_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    # 9. Print summary
    click.echo("")
    click.echo("=" * 60)
    click.echo("Create Role — Complete")
    click.echo("=" * 60)
    click.echo(f"Role:          {role_description[:60]}")
    click.echo(f"Elapsed:       {elapsed:.1f}s")
    click.echo(f"Output length: {len(result_text)} chars")
    click.echo(f"Document:      {primary_deliverable}")
    click.echo(f"Workspace:     {workspace}")
    click.echo("=" * 60)


if __name__ == "__main__":
    main()
