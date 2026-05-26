"""YAML-driven E2E test for the inner BTA pipeline (skill/tool creation).

Loads the inner BTA entirely from a YAML config file using
``load_config()`` + ``instantiate()`` — no hardcoded builder functions.

Usage::

    python -m test.openteam.resources.tools.role_setup.test_role_setup_inner_bta_through_yaml \
        --role-document /path/to/role.md \
        --breakdown-file /path/to/outer_breakdown.md \
        --subtask-index 1 \
        --cloud-id "$ROVOCHAT_CLOUD_ID" \
        --uct-token "$ROVOCHAT_UCT_TOKEN"
"""

import asyncio
import functools
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import click

# ---------------------------------------------------------------------------
# .env loading — stdlib only, no extra deps needed
# ---------------------------------------------------------------------------
def _load_dotenv(*search_dirs) -> None:
    """Load KEY=VALUE pairs from the first .env found in search_dirs.

    Only sets vars not already present in the environment (shell wins).
    Supports: blank lines, # comments, optional quotes around values.
    """
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
            break  # stop at first .env found

# Search: test script dir, then OpenTeam repo root
_load_dotenv(Path(__file__).parent, Path(__file__).parents[5])  # parents[5] = repo root

# Ensure registrations are loaded before instantiate()
import agent_foundation.common.configs.registered_targets  # noqa: F401

from python_utils.config_utils import load_config, instantiate

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Reuse helpers from test_role_setup.py
# ---------------------------------------------------------------------------

def _run_async_with_forced_cleanup(coro, cleanup_timeout: float = 15.0):
    """Run an async coroutine with forced event loop cleanup."""
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


def _extract_aggregator_result(result) -> str:
    """Extract the aggregator output from a BTA ainfer() result."""
    if result is None:
        return "(no result)"
    if not isinstance(result, (tuple, list)):
        if hasattr(result, "output") and result.output:
            return str(result.output)
        return str(result).strip() or "(empty result)"
    best = None
    best_len = 0
    for r in result:
        if r is None:
            continue
        text = str(r.output) if hasattr(r, "output") and r.output else str(r).strip()
        if not text:
            continue
        if len(text) > best_len:
            best = r
            best_len = len(text)
    if best is None:
        return "(all results were None or empty)"
    return str(best.output) if hasattr(best, "output") and best.output else str(best).strip()


def _extract_subtask(breakdown_file: str, subtask_index: int) -> str:
    """Extract a subtask description from an outer breakdown output file."""
    raw_file = Path(breakdown_file).read_text(encoding="utf-8")

    # The checkpoint file is a JSON object with a "raw_output" key — decode it first
    # so that escaped sequences (\\n, \") are resolved before regex matching.
    try:
        parsed = json.loads(raw_file)
        text = parsed.get("raw_output", raw_file) if isinstance(parsed, dict) else raw_file
    except json.JSONDecodeError:
        text = raw_file

    # Extract from <Response> tags if present
    response_match = re.search(r"<Response>(.*?)</Response>", text, re.DOTALL)
    search_text = response_match.group(1) if response_match else text

    # Find JSON
    json_match = re.search(r"```json.*?\n(.*?)```", search_text, re.DOTALL)
    if not json_match:
        json_match = re.search(r'\{[^{}]*"subtasks"\s*:\s*\[.*?\]\s*[^{}]*\}', search_text, re.DOTALL)
    if not json_match:
        raise ValueError(f"No subtasks found in breakdown file: {breakdown_file}")

    json_str = json_match.group(1) if "```" in json_match.group(0) else json_match.group(0)
    data = json.loads(json_str)
    subtasks = data.get("subtasks", data.get("decomposed_subtasks", []))

    if subtask_index < 1 or subtask_index > len(subtasks):
        raise ValueError(f"Subtask index {subtask_index} out of range (1-{len(subtasks)})")

    subtask = subtasks[subtask_index - 1]
    return subtask.get("description", subtask.get("subtask", ""))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.command()
@click.option("--yaml-config", default=None, type=click.Path(exists=True),
              help="Inner BTA YAML config. Default: src/.../role_setup/role_setup_skill_tool_creation.yaml")
@click.option("--breakdown-file", "-b", required=True, type=click.Path(exists=True),
              help="Outer breakdown output file.")
@click.option("--subtask-index", default=1, type=int,
              help="1-based subtask index from outer breakdown.")
@click.option("--role-document", "-r", required=True, type=click.Path(exists=True),
              help="Path to the role document markdown file.")
@click.option("--cloud-id", envvar="ROVOCHAT_CLOUD_ID", default="")
@click.option("--uct-token", envvar="ROVOCHAT_UCT_TOKEN", default=None)
@click.option("--email", envvar="JIRA_EMAIL", default=None)
@click.option("--api-token", envvar="JIRA_API_TOKEN", default=None)
@click.option("--base-url", envvar="ROVOCHAT_BASE_URL", default=None)
@click.option("--aggregator-type", type=click.Choice(["rovochat", "rovodev"]), default="rovochat")
@click.option("--output-dir", default=str(Path(__file__).resolve().parent / "_runtime"), type=click.Path())
@click.option("--breakdown-only", is_flag=True, default=False)
@click.option("--log-level", type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]), default="INFO")
def main(
    yaml_config, breakdown_file, subtask_index, role_document,
    cloud_id, uct_token, email, api_token, base_url,
    aggregator_type, output_dir, breakdown_only, log_level,
):
    """Run inner BTA for a single skill/tool creation subtask, loaded from YAML."""

    logging.basicConfig(level=getattr(logging, log_level),
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")

    # Default YAML config
    if yaml_config is None:
        yaml_config = str(
            Path(__file__).resolve().parents[5]
            / "src" / "openteam" / "server" / "resources" / "tools" / "role_setup"
            / "role_setup_skill_tool_creation.yaml"
        )

    # Extract subtask
    subtask_desc = _extract_subtask(breakdown_file, subtask_index)
    click.echo(f"Subtask {subtask_index}: {subtask_desc[:80]}...")

    # Role context
    role_doc_text = Path(role_document).read_text(encoding="utf-8")
    role_name = role_doc_text.split("\n")[0].strip("# ").strip()
    role_doc_path = str(Path(role_document).resolve())

    # Available tools
    try:
        from openteam.server.resources.tools.role_setup.executor import (
            format_available_tools_and_skills, _APP_TOOLS_DIR, _APP_SKILLS_DIR,
        )
        available_tools_text = format_available_tools_and_skills(
            extra_tool_dirs=[_APP_TOOLS_DIR], extra_skill_dirs=[_APP_SKILLS_DIR]
        )
    except ImportError:
        available_tools_text = "(tools registry not available)"

    # Workspace
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    workspace = Path(output_dir) / timestamp
    workspace.mkdir(parents=True, exist_ok=True)
    # cache_folder and logs are auto-configured from workspace_root via BTA

    # =====================================================================
    # 1. Build overrides (auth + workspace — runtime values)
    # =====================================================================
    overrides = {
        # Use dot-notation so load_config patches only the root field of the
        # yaml's workspace object, preserving use_final_deliverables_folder: true.
        # Using "workspace_root" (BTA convenience field) bypasses the yaml workspace
        # definition entirely and creates a bare InferencerWorkspace without
        # use_final_deliverables_folder — causing deliverables to land in outputs/
        # instead of outputs/final_deliverables/.
        "workspace.root": str(workspace),
    }
    if breakdown_only:
        overrides["breakdown_only"] = True

    # Auth overrides for worker factory entries
    auth_fields = {}
    if uct_token:
        auth_fields["uct_token"] = uct_token
    if cloud_id:
        auth_fields["cloud_id"] = cloud_id
    if email:
        auth_fields["email"] = email
    if api_token:
        auth_fields["api_token"] = api_token
    if base_url:
        auth_fields["base_url"] = base_url

    # Worker-level auth overrides
    for worker_key in ["skill_tool_creation_research", "skill_tool_creation_investigation"]:
        if auth_fields:
            for k, v in auth_fields.items():
                overrides[f"worker_factory.{worker_key}.{k}"] = v
    if auth_fields:
        for k, v in auth_fields.items():
            overrides[f"aggregator_inferencer.{k}"] = v

    # =====================================================================
    # 2. Load + instantiate (config_utils handles everything)
    # =====================================================================
    click.echo(f"Loading YAML config: {yaml_config}")
    cfg = load_config(yaml_config, overrides=overrides)
    bta = instantiate(cfg)

    click.echo(f"BTA type: {type(bta).__name__}")
    click.echo(f"Breakdown inferencer: {type(bta.breakdown_inferencer).__name__}")
    click.echo(f"Aggregator inferencer: {type(bta.aggregator_inferencer).__name__}")
    click.echo(f"Worker factory keys: {[k for k in bta.worker_factory if not k.startswith('_')]}")

    # logger and cache_folder are auto-configured via _logger: auto in YAML
    # and BTA._configure_child_workspace() for each child inferencer.

    # =====================================================================
    # 3. Runtime injection: role_name + role_doc_path + available_tools
    #    Set on the BTA — _propagate_to_children() in InferencerBase
    #    automatically pushes to all children at inference time.
    # =====================================================================
    bta.template_extra_feed.update({
        "role_name": role_name,
        "role_doc_path": role_doc_path,
        "available_tools_skills": available_tools_text,
    })

    # =====================================================================
    # 4. Run
    # =====================================================================
    click.echo(f"\nRunning inner BTA (breakdown_only={breakdown_only})...")
    start_time = time.time()

    try:
        result = _run_async_with_forced_cleanup(bta.ainfer(subtask_desc))
    except Exception:
        logger.exception("Inference failed")
        click.echo("ERROR: Inference failed.", err=True)
        sys.exit(1)

    elapsed = time.time() - start_time
    result_text = _extract_aggregator_result(result)

    # Save results
    artifacts_dir = workspace / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    from agent_foundation.common.response_parsers import extract_delimited
    clean_text = extract_delimited(result_text) if "<Response>" in result_text else result_text

    output_file = artifacts_dir / ("breakdown_output.md" if breakdown_only else "inner_bta_output.md")
    output_file.write_text(clean_text, encoding="utf-8")

    if not breakdown_only:
        outputs_dir = workspace / "outputs"
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

    (artifacts_dir / "summary.json").write_text(json.dumps({
        "mode": "yaml_driven",
        "yaml_config": yaml_config,
        "subtask_index": subtask_index,
        "subtask_desc": subtask_desc[:200],
        "breakdown_only": breakdown_only,
        "elapsed_seconds": round(elapsed, 1),
        "output_length": len(result_text),
        "workspace": str(workspace),
    }, indent=2), encoding="utf-8")

    click.echo("")
    click.echo("=" * 60)
    click.echo("Inner BTA — Complete (YAML-driven)")
    click.echo("=" * 60)
    click.echo(f"Subtask:   {subtask_desc[:60]}")
    click.echo(f"Elapsed:   {elapsed:.1f}s")
    click.echo(f"Output:    {output_file}")
    click.echo(f"Workspace: {workspace}")
    click.echo("=" * 60)


if __name__ == "__main__":
    main()
