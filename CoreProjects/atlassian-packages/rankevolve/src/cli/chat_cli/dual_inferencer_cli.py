# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict
"""NDJSON streaming CLI wrapper for DualInferencer.

Used by the TypeScript CLI (chat_cli_ts) as a subprocess.
Emits NDJSON events compatible with the old dual_agent/cli.py protocol:
  {"event": "token", "chunk": "...", "phase": "...", "agent_id": "..."}
  {"event": "complete"}
  {"event": "error", "message": "..."}

Usage:
    buck2 run fbcode//rankevolve/src/cli/chat_cli:dual_inferencer_cli -- \
        --root-folder /path/to/repo \
        --request "Your coding task"
"""

from __future__ import annotations

import asyncio
import glob
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import click


def _emit(event: dict[str, Any]) -> None:
    """Write a single NDJSON event to stdout."""
    sys.stdout.write(json.dumps(event) + "\n")
    sys.stdout.flush()


def _get_repo_root() -> Path:
    """Find the fbsource repo root using `sl root`.

    Falls back to walking up from __file__ looking for .sl/ directory,
    then to the devmate common module's get_source_repo_root().
    """
    import subprocess as _subprocess

    try:
        result = _subprocess.run(
            ["sl", "root"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip())
    except (FileNotFoundError, _subprocess.TimeoutExpired, OSError):
        pass

    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / ".sl").is_dir():
            return parent

    try:
        from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.external.devmate.common import (
            get_source_repo_root,
        )

        return Path(get_source_repo_root())
    except (ImportError, IndexError):
        pass

    return current.parent


@click.command()
@click.option(
    "--root-folder",
    "-r",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Root code folder for the task.",
)
@click.option(
    "--request",
    "-q",
    type=str,
    required=True,
    help="The coding task/request to execute.",
)
@click.option(
    "--mode",
    "-e",
    type=click.Choice(["plan", "full", "execute", "confirm"]),
    default="full",
    help="Execution mode: plan only, full workflow, execute only, or plan then confirm.",
)
@click.option(
    "--use-claude-only",
    is_flag=True,
    default=False,
    help="Use Claude Code for both proposer and reviewer (bypass Devmate).",
)
@click.option(
    "--claude-model",
    type=str,
    default=None,
    help="Claude model name (e.g., opus, sonnet, claude-sonnet-4-5).",
)
@click.option(
    "--max-iterations",
    type=int,
    default=5,
    help="Max consensus iterations per attempt.",
)
@click.option(
    "--max-attempts",
    type=int,
    default=1,
    help="Max fresh-start consensus attempts.",
)
@click.option(
    "--consensus-threshold",
    type=str,
    default="COSMETIC",
    help="Max acceptable severity for consensus (NONE, COSMETIC, MINOR, MAJOR, CRITICAL).",
)
@click.option(
    "--timeout",
    type=int,
    default=1800,
    help="Per-inferencer idle timeout in seconds.",
)
@click.option(
    "--no-counter-feedback",
    is_flag=True,
    default=False,
    help="Disable counter-feedback from fixer.",
)
def main(
    root_folder: Path,
    request: str,
    mode: str,
    use_claude_only: bool,
    claude_model: str | None,
    max_iterations: int,
    max_attempts: int,
    consensus_threshold: str,
    timeout: int,
    no_counter_feedback: bool,
) -> None:
    """Run DualInferencer with NDJSON streaming output."""
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s: %(name)s: %(message)s",
        stream=sys.stderr,
    )

    async def _run() -> None:
        from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.common import (
            ConsensusConfig,
            DualInferencerResponse,
            Severity,
        )
        from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.external.claude_code.claude_code_inferencer import (  # noqa: E501
            ClaudeCodeInferencer,
        )
        from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.flow_inferencers.dual_inferencer import (
            DualInferencer,
        )
        from rankevolve.src.agentic_foundation.common.response_parsers import (
            extract_delimited,
        )
        from rich_python_utils.common_objects.debuggable import LoggerConfig
        from rankevolve.src.utils.io_utils.json_io import JsonLogger, SpaceExtMode
        from rankevolve.src.utils.string_utils.formatting.template_manager import (
            TemplateManager,
        )

        # Setup workspace — use fbsource/_rankevolve_workspace
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_dir = _get_repo_root() / "_rankevolve_workspace"
        workspace = base_dir / f"cli_task_{timestamp}"
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "outputs").mkdir(exist_ok=True)
        (workspace / "results").mkdir(exist_ok=True)

        cache_dir = workspace / "_runtime" / "inferencer_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_folder = str(cache_dir)

        tmp_offload_dir = workspace / "_runtime" / "tmp_output_files"
        tmp_offload_dir.mkdir(parents=True, exist_ok=True)

        # Set up session logging
        logs_dir = workspace / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

        json_logger = JsonLogger(
            file_path=str(logs_dir / "session.jsonl"),
            append=True,
            is_artifact=True,
            parts_min_size=0,
            space_ext_mode=SpaceExtMode.MOVE,
            parts_file_namer=lambda obj: obj.get("type", "")
            if isinstance(obj, dict)
            else "",
        )
        dual_logger: list[Any] = [
            (json_logger, LoggerConfig(pass_item_key_as="parts_key_path_root")),
            # NOTE: Intentionally omitting `print` — output goes through NDJSON _emit().
        ]

        enable_counter_feedback = not no_counter_feedback
        consensus_config = ConsensusConfig(
            max_iterations=max_iterations,
            max_consensus_attempts=max_attempts,
            consensus_threshold=Severity[consensus_threshold],
            enable_counter_feedback=enable_counter_feedback,
        )

        # Locate shared prompt_templates directory
        templates_dir: Path = (
            Path(__file__).resolve().parents[2] / "resources" / "prompt_templates"
        )
        if not templates_dir.is_dir():
            raise FileNotFoundError(
                f"prompt_templates directory not found at '{templates_dir}'. "
                f"Expected at rankevolve/src/resources/prompt_templates/."
            )

        rf: str = str(root_folder)
        cache_folder_str: str = cache_folder
        tmp_offload_str: str = str(tmp_offload_dir)

        def _create_inferencers(phase_label: str) -> tuple[Any, Any]:
            """Create fresh inferencer instances for a phase."""
            if use_claude_only:
                base = ClaudeCodeInferencer(
                    root_folder=rf,
                    model_id=claude_model or "",
                    system_prompt="You are an expert software architect and planner.",
                    idle_timeout_seconds=timeout,
                    allowed_tools=["Read", "Write", "Bash", "Glob", "Grep"],
                    id=f"claude_code_base_{phase_label}",
                    cache_folder=cache_folder_str,
                    logger=dual_logger,
                )
                review = ClaudeCodeInferencer(
                    root_folder=rf,
                    model_id=claude_model or "",
                    system_prompt="You are an expert code reviewer and implementer.",
                    idle_timeout_seconds=timeout,
                    allowed_tools=["Read", "Write", "Bash", "Glob", "Grep"],
                    id=f"claude_code_review_{phase_label}",
                    cache_folder=cache_folder_str,
                    logger=dual_logger,
                )
            else:
                from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.external.devmate.common import (
                    SessionMode,
                )
                from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.external.devmate.devmate_cli_inferencer import (  # noqa: E501
                    DevmateCliInferencer,
                )

                # Default to NEW_SESSION_PER_CALL for dual_inferencer use:
                # eliminates devmate per-session iteration cap accumulation
                # by construction. See dual_inferencer_bridge.py for full
                # rationale; same default applied here for CLI consistency.
                base_kwargs: dict[str, Any] = dict(
                    root_folder=rf,
                    idle_timeout_seconds=timeout,
                    # Wall-clock cap on the entire ainfer() call. See
                    # dual_inferencer_bridge.py for the full rationale (devmate
                    # heartbeat-flood evades idle_timeout; CLI inferencer has
                    # no built-in total cap unlike SDK). 3600s = 1 hour.
                    total_timeout_seconds=3600,
                    # Tightened cap activated by devmate-internal-failure watcher
                    # (see dual_inferencer_bridge.py + devmate_cli_inferencer.py
                    # for design). 2400s = 40 min.
                    total_timeout_on_internal_error_detection_seconds=2400,
                    id=f"devmate_cli_base_{phase_label}",
                    cache_folder=cache_folder_str,
                    large_arg_temp_dir=tmp_offload_str,
                    session_mode=SessionMode.NEW_SESSION_PER_CALL,
                )
                if claude_model is not None:
                    base_kwargs["model_name"] = claude_model
                if dual_logger:
                    base_kwargs["logger"] = dual_logger
                base = DevmateCliInferencer(**base_kwargs)
                review_kwargs: dict[str, Any] = dict(
                    root_folder=rf,
                    idle_timeout_seconds=timeout,
                    total_timeout_seconds=3600,  # see base_kwargs comment
                    total_timeout_on_internal_error_detection_seconds=2400,
                    id=f"devmate_cli_review_{phase_label}",
                    cache_folder=cache_folder_str,
                    large_arg_temp_dir=tmp_offload_str,
                    session_mode=SessionMode.NEW_SESSION_PER_CALL,
                )
                if claude_model is not None:
                    review_kwargs["model_name"] = claude_model
                if dual_logger:
                    review_kwargs["logger"] = dual_logger
                review = DevmateCliInferencer(**review_kwargs)
            return base, review

        consensus_cfg: ConsensusConfig = consensus_config
        templates_path: str = str(templates_dir)

        def _build_dual_inferencer(phase: str) -> DualInferencer:
            """Build a configured DualInferencer for a phase."""
            base_inf, review_inf = _create_inferencers(phase)

            prompt_tm = TemplateManager(
                templates=templates_path,
                active_template_root_space=phase,
                enable_templated_feed=True,
            )

            return DualInferencer(
                base_inferencer=base_inf,
                review_inferencer=review_inf,
                consensus_config=consensus_cfg,
                prompt_formatter=prompt_tm,
                initial_prompt="initial",
                review_prompt="review",
                followup_prompt="followup",
                placeholder_proposal="main_response",
                phase=phase,
                response_parser=extract_delimited,
                logger=dual_logger,
                debug_mode=True,
                id=f"{phase.title()}DualInferencer",
            )

        def _save_phase_results(
            results_dir: Path,
            output_dir: Path,
            phase: str,
            result: Any,
        ) -> None:
            """Save DualInferencerResponse results for a single phase."""
            if not isinstance(result, DualInferencerResponse):
                (results_dir / f"{phase}_output.txt").write_text(str(result))
                return

            pattern = str(output_dir / f"round*_{phase}.md")
            output_files = glob.glob(pattern)
            if output_files:

                def _extract_round(path: str) -> int:
                    match = re.search(r"round(\d+)_", Path(path).name)
                    return int(match.group(1)) if match else -1

                latest_file = max(output_files, key=_extract_round)
                content = Path(latest_file).read_text()
                (results_dir / f"{phase}_final_output.txt").write_text(content)
            else:
                (results_dir / f"{phase}_final_output.txt").write_text(
                    str(result.base_response)
                )

            summary = {
                "phase": phase,
                "consensus_achieved": result.consensus_achieved,
                "total_iterations": result.total_iterations,
            }
            (results_dir / f"{phase}_consensus_summary.json").write_text(
                json.dumps(summary, indent=2)
            )

            history: list[dict[str, Any]] = []
            for attempt in result.consensus_history:
                attempt_data: dict[str, Any] = {
                    "attempt": attempt.attempt,
                    "consensus_reached": attempt.consensus_reached,
                    "final_output_length": len(attempt.final_output),
                    "iterations": [],
                }
                iterations_list: list[dict[str, Any]] = attempt_data["iterations"]
                for iter_rec in attempt.iterations:
                    iter_data = {
                        "iteration": iter_rec.iteration,
                        "consensus_reached": iter_rec.consensus_reached,
                        "review_feedback": iter_rec.review_feedback,
                        "counter_feedback": iter_rec.counter_feedback,
                    }
                    iterations_list.append(iter_data)

                    prefix = (
                        f"{phase}_attempt_{attempt.attempt}_iter_{iter_rec.iteration}"
                    )
                    (results_dir / f"{prefix}_proposal.txt").write_text(
                        iter_rec.base_output
                    )
                    if iter_rec.review_feedback is not None:
                        (results_dir / f"{prefix}_review.json").write_text(
                            json.dumps(iter_rec.review_feedback, indent=2)
                        )
                    if iter_rec.counter_feedback is not None:
                        (results_dir / f"{prefix}_counter_feedback.json").write_text(
                            json.dumps(iter_rec.counter_feedback, indent=2)
                        )

                history.append(attempt_data)

            (results_dir / f"{phase}_consensus_history.json").write_text(
                json.dumps(history, indent=2, default=str)
            )

        try:
            if mode == "full":
                # Use PlanThenImplementInferencer for full workflow
                from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.flow_inferencers.plan_then_implement_inferencer import (
                    PlanThenImplementInferencer,
                )

                plan_dual = _build_dual_inferencer("plan")
                impl_dual = _build_dual_inferencer("implementation")

                output_dir = workspace.resolve() / "outputs"
                plan_output_path = str(output_dir) + "/round{{ round_index }}_plan.md"
                impl_output_path = (
                    str(output_dir) + "/round{{ round_index }}_implementation.md"
                )

                pti = PlanThenImplementInferencer(
                    planner_inferencer=plan_dual,
                    executor_inferencer=impl_dual,
                    interactive=None,
                    planner_phase="plan",
                    executor_phase="implementation",
                    planner_outputs_plan_to_file=True,
                    logger=dual_logger,
                    debug_mode=True,
                    id="PlanThenImplementInferencer",
                )

                _emit(
                    {
                        "event": "token",
                        "chunk": "Starting full workflow (PlanThenImplementInferencer)...\n",
                        "phase": "plan",
                        "agent_id": "system",
                    }
                )

                async with pti:
                    result = await pti.ainfer(
                        request,
                        inference_config={
                            "plan_config": {"output_path": plan_output_path},
                            "implement_config": {"output_path": impl_output_path},
                        },
                    )

                # Emit plan result
                plan_text = str(result.plan_output) if result.plan_output else ""
                if plan_text:
                    _emit(
                        {
                            "event": "token",
                            "chunk": plan_text,
                            "phase": "plan",
                            "agent_id": "base",
                        }
                    )

                # Emit implementation result
                impl_text = str(result.base_response)
                _emit(
                    {
                        "event": "token",
                        "chunk": impl_text,
                        "phase": "implementation",
                        "agent_id": "base",
                    }
                )

                # Save results
                results_dir = workspace / "results"
                output_dir_path = workspace / "outputs"
                if result.plan_response is not None:
                    _save_phase_results(
                        results_dir, output_dir_path, "plan", result.plan_response
                    )
                if result.executor_output is not None:
                    _save_phase_results(
                        results_dir,
                        output_dir_path,
                        "implementation",
                        result.executor_output,
                    )

            else:
                # Single-phase mode (plan, execute, confirm)
                phases: list[str] = []
                if mode == "plan":
                    phases = ["plan"]
                elif mode == "execute":
                    phases = ["implementation"]
                elif mode == "confirm":
                    phases = ["plan"]

                current_request = request
                for phase in phases:
                    _emit(
                        {
                            "event": "token",
                            "chunk": f"Starting {phase} phase...\n",
                            "phase": phase,
                            "agent_id": "system",
                        }
                    )

                    dual = _build_dual_inferencer(phase)

                    output_path = (
                        str(workspace.resolve() / "outputs")
                        + "/round{{ round_index }}_"
                        + phase
                        + ".md"
                    )

                    async with dual:
                        result = await dual.ainfer(
                            current_request,
                            inference_config={"output_path": output_path},
                        )

                    response_text = (
                        str(result.base_response)
                        if hasattr(result, "base_response")
                        else str(result)
                    )

                    _emit(
                        {
                            "event": "token",
                            "chunk": response_text,
                            "phase": phase,
                            "agent_id": "base",
                        }
                    )

                    # Save phase results
                    _save_phase_results(
                        workspace / "results",
                        workspace / "outputs",
                        phase,
                        result,
                    )

            _emit({"event": "complete"})
        except Exception as e:
            _emit({"event": "error", "message": str(e)})
            sys.exit(1)

    asyncio.run(_run())


if __name__ == "__main__":
    main()
