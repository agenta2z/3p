# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict
"""Bridges the DualInferencer consensus workflow into the chat CLI.

Replaces the old DualAgentBridge that used the dual_agent module directly.
Now uses DualInferencer from agentic_foundation with ClaudeCodeInferencer
and DevmateCliInferencer as sub-inferencers.
"""

from __future__ import annotations

import asyncio
import glob
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.common import (
    ConsensusConfig,
    DualInferencerResponse,
    Severity,
)
from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.flow_inferencers.dual_inferencer import (
    DualInferencer,
)
from rankevolve.src.agentic_foundation.common.inferencers.inferencer_base import (
    InferencerBase,
)
from rankevolve.src.agentic_foundation.common.response_parsers import extract_delimited
from rankevolve.src.server.stream_bridge import StreamBridgeAdapter
from rankevolve.src.server.task_types import TaskMode
from rich_python_utils.common_objects.debuggable import LoggerConfig
from rankevolve.src.utils.common_objects.workflow.common.step_result_save_options import (
    StepResultSaveOptions,
)
from rankevolve.src.utils.io_utils.json_io import JsonLogger, SpaceExtMode
from rankevolve.src.utils.string_utils.formatting.template_manager import (
    TemplateManager,
)

logger: logging.Logger = logging.getLogger(__name__)

# Marker written by StreamingInferencerBase._finalize_cache when done
from rankevolve.src.common.streaming.markers import (
    STREAM_DONE_MARKER as _STREAM_DONE_MARKER,
    STREAM_FAIL_MARKER as _STREAM_FAIL_MARKER,
)

INFERENCER_CHOICES = ["claude_code", "claude_code_cli", "devmate_sdk", "devmate_cli"]


def _get_repo_root() -> Path:
    """Find the fbsource repo root using `sl root`.

    Falls back to walking up from __file__ looking for .sl/ directory,
    then to the devmate common module's get_source_repo_root() which
    uses a hardcoded parent count.
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

    # Fallback: walk up from __file__ looking for .sl/
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / ".sl").is_dir():
            return parent

    # Last resort: use devmate common's hardcoded parent count
    try:
        from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.external.devmate.common import (
            get_source_repo_root,
        )

        return Path(get_source_repo_root())
    except (ImportError, IndexError):
        pass

    return current.parent


def _get_templates_dir() -> Path:
    """Locate the shared prompt_templates/ directory.

    Tries importlib.resources first (works in Buck builds), then
    falls back to filesystem relative path for local development.

    Raises:
        FileNotFoundError: If the prompt_templates directory cannot be found.
    """
    # Primary: importlib.resources (reliable in Buck builds)
    try:
        import importlib.resources as pkg_resources

        ref = pkg_resources.files("rankevolve.src.resources.prompt_templates")
        candidate = Path(str(ref))
        if candidate.is_dir():
            return candidate
    except (ImportError, ModuleNotFoundError, TypeError):
        pass

    # Secondary: filesystem relative to this file
    candidate = (
        Path(__file__).resolve().parent.parent / "resources" / "prompt_templates"
    )
    if candidate.is_dir():
        return candidate

    raise FileNotFoundError(
        f"prompt_templates directory not found. "
        f"Tried importlib.resources('rankevolve.src.resources.prompt_templates') "
        f"and filesystem path '{candidate}'. "
        f"Ensure the '//rankevolve/src/resources:prompt_templates' "
        f"Buck target is in your deps."
    )


def _create_inferencer(
    inferencer_type: str,
    root_folder: str,
    model: str | None,
    system_prompt: str,
    inferencer_id: str,
    cache_folder: str | None = None,
    large_arg_temp_dir: str | None = None,
    timeout: int = 1800,
    inferencer_logger: Any = None,
) -> InferencerBase:
    """Factory to create the appropriate sub-inferencer.

    Following the pattern from test_plan_then_implement.py.
    """
    if inferencer_type == "claude_code":
        from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.external.claude_code.claude_code_inferencer import (  # noqa: E501
            ClaudeCodeInferencer,
        )

        return ClaudeCodeInferencer(
            root_folder=root_folder,
            model_id=model or "",
            system_prompt=system_prompt,
            idle_timeout_seconds=timeout,
            allowed_tools=["Read", "Write", "Bash", "Glob", "Grep"],
            id=inferencer_id,
            cache_folder=cache_folder,
            logger=inferencer_logger,
        )
    elif inferencer_type == "claude_code_cli":
        from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.external.claude_code.claude_code_cli_inferencer import (  # noqa: E501
            ClaudeCodeCliInferencer,
        )

        kwargs: dict[str, Any] = dict(
            root_folder=root_folder,
            allowed_tools=["Read", "Write", "Bash", "Glob", "Grep"],
            idle_timeout_seconds=timeout,
        )
        if model is not None:
            kwargs["model_name"] = model
        if system_prompt:
            kwargs["system_prompt"] = system_prompt
        if inferencer_logger is not None:
            kwargs["logger"] = inferencer_logger
        if inferencer_id is not None:
            kwargs["id"] = inferencer_id
        if cache_folder is not None:
            kwargs["cache_folder"] = cache_folder
        if large_arg_temp_dir is not None:
            kwargs["large_arg_temp_dir"] = large_arg_temp_dir
        return ClaudeCodeCliInferencer(**kwargs)
    elif inferencer_type == "devmate_sdk":
        from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.external.devmate.devmate_sdk_inferencer import (  # noqa: E501
            DevmateSDKInferencer,
        )

        # Note: DevmateSDKInferencer does not accept `startup_timeout_seconds`
        # — only total_timeout_seconds + idle_timeout_seconds (verified against
        # `devmate_sdk_inferencer.py`'s attrib declarations).
        kwargs: dict[str, Any] = dict(
            root_folder=root_folder,
            total_timeout_seconds=timeout,
            idle_timeout_seconds=timeout,
            id=inferencer_id,
        )
        if model is not None:
            kwargs["model_name"] = model
        if cache_folder is not None:
            kwargs["cache_folder"] = cache_folder
        if inferencer_logger is not None:
            kwargs["logger"] = inferencer_logger
        return DevmateSDKInferencer(**kwargs)
    elif inferencer_type == "devmate_cli":
        from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.external.devmate.common import (  # noqa: E501
            SessionMode,
        )
        from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.external.devmate.devmate_cli_inferencer import (  # noqa: E501
            DevmateCliInferencer,
        )

        kwargs: dict[str, Any] = dict(
            root_folder=root_folder,
            idle_timeout_seconds=timeout,
            # Wall-clock cap on the entire ``ainfer()`` call (incl. retry
            # envelope). Prevents indefinite stalls when devmate hangs in
            # an internal LLM-API call (devmate emits empty heartbeat
            # sentinels that reset the per-chunk ``idle_timeout_seconds``
            # timer, so idle-timeout alone is NOT sufficient — verified in
            # the 70+ min stall of task_20260426_064353 R1 base where the
            # 30-min idle_timeout never fired). 3600s = 1 hour is a generous
            # cap for a single round of /understand-codebase / /task work.
            # ``InferencerBase.total_timeout_seconds`` defaults to 0 (disabled);
            # ``DevmateCliInferencer`` does not override it (unlike
            # ``DevmateSDKInferencer`` which sets 1800). This bridge override
            # gives /task-triggered DevmateCli inferencers a cap by default.
            total_timeout_seconds=3600,
            # Tighter cap that activates when the devmate-internal-failure
            # watcher detects a known-fatal pattern in devmate.stderr AND
            # our cache is silent for >120s. Soft signal (deadline tightening,
            # not abort) — devmate may still self-recover within this window.
            # 2400s = 40min gives observed median round time (~15-20 min) ~2x
            # headroom; saves ~20 min on confirmed-stuck calls vs the 3600s cap.
            total_timeout_on_internal_error_detection_seconds=2400,
            id=inferencer_id,
            # Default to NEW_SESSION_PER_CALL for dual_inferencer use because:
            # - Each round/step is conceptually independent (prompts are
            #   self-contained; verified via prompt-self-containment audit)
            # - Eliminates devmate per-session iteration cap accumulation by
            #   construction (the failure mode in forensics_round_template_echo_bug
            #   where 4 review calls accumulated past 50 iterations on one session)
            # The class-level default (SAME_SESSION_ACROSS_ROUNDS) preserves
            # chat_cli backward-compat; this bridge override applies only to
            # dual_inferencer-constructed instances.
            session_mode=SessionMode.NEW_SESSION_PER_CALL,
        )
        if model is not None:
            kwargs["model_name"] = model
        if cache_folder is not None:
            kwargs["cache_folder"] = cache_folder
        if large_arg_temp_dir is not None:
            kwargs["large_arg_temp_dir"] = large_arg_temp_dir
        if inferencer_logger is not None:
            kwargs["logger"] = inferencer_logger
        return DevmateCliInferencer(**kwargs)
    else:
        raise ValueError(f"Unknown inferencer type: {inferencer_type}")


class DualInferencerBridge:
    """Bridges DualInferencer consensus workflow into the chat CLI.

    Usage:
        bridge = DualInferencerBridge(
            root_folder=Path.cwd(),
            claude_model="opus",
            use_claude_only=True,
        )
        task = asyncio.create_task(bridge.run(request, task_mode=TaskMode.PLAN_ONLY))
        response_text = await display.stream_dual_agent_response(bridge.token_stream)
        await task
    """

    def __init__(
        self,
        root_folder: Path,
        claude_model: str | None = None,
        use_claude_only: bool = False,
        output_dir: Path | None = None,
        knowledge_bridge: Any | None = None,
        session_context: dict[str, Any] | None = None,
        max_iterations: int = 5,
        max_attempts: int = 1,
        consensus_threshold: str = "COSMETIC",
        timeout: int = 1800,
        no_counter_feedback: bool = False,
        enable_planning: bool = True,
        enable_implementation: bool = True,
        enable_analysis: bool = False,
        enable_multiple_iterations: bool = False,
        max_meta_iterations: int = 3,
        resume_workspace: Optional[str] = None,
        analysis_mode: str = "last_with_cross_ref",
        copy_workspace: Optional[bool] = None,
        replay_streaming: bool = False,
        initial_plan_file: Optional[str] = None,
        base_inferencer_type: Optional[str] = None,
        review_inferencer_type: Optional[str] = None,
        template_version: str = "",
    ) -> None:
        self._root_folder = root_folder
        self._session_context = dict(session_context) if session_context else {}
        if "session_root_path" not in self._session_context:
            self._session_context["session_root_path"] = str(root_folder)
        self._claude_model = claude_model
        self._use_claude_only = use_claude_only
        self._template_version = template_version

        # Resolve inferencer types: explicit flags > use_claude_only > default
        if base_inferencer_type is not None:
            self._base_inferencer_type = base_inferencer_type
        elif use_claude_only:
            self._base_inferencer_type = "claude_code"
        else:
            self._base_inferencer_type = "devmate_cli"

        if review_inferencer_type is not None:
            self._review_inferencer_type = review_inferencer_type
        elif use_claude_only:
            self._review_inferencer_type = "claude_code"
        else:
            self._review_inferencer_type = "devmate_cli"
        self._output_dir = output_dir
        self._knowledge_bridge = knowledge_bridge
        self._adapter = StreamBridgeAdapter()
        self._tailed_bytes: int = 0

        # Consensus / inferencer configuration
        self._max_iterations = max_iterations
        self._max_attempts = max_attempts
        self._consensus_threshold: Severity = Severity[consensus_threshold]
        self._timeout = timeout
        self._enable_counter_feedback: bool = not no_counter_feedback

        # PlanThenImplementInferencer flags
        self._enable_planning = enable_planning
        self._enable_implementation = enable_implementation
        self._enable_analysis = enable_analysis
        self._enable_multiple_iterations = enable_multiple_iterations
        self._max_meta_iterations = max_meta_iterations
        self._analysis_mode = analysis_mode
        self._replay_streaming = replay_streaming
        self._initial_plan_file = initial_plan_file

        # Workspace setup: copy by default on resume, override with explicit bool
        if resume_workspace is not None:
            source_ws = Path(resume_workspace)
            should_copy = copy_workspace if copy_workspace is not None else True
            if should_copy:
                import shutil

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                is_analysis_only = (
                    not enable_planning
                    and not enable_implementation
                    and enable_analysis
                )
                suffix = "analysis" if is_analysis_only else "resumed"
                self._workspace: Path = (
                    source_ws.parent / f"{source_ws.name}_{suffix}_{timestamp}"
                )
                try:
                    shutil.copytree(str(source_ws), str(self._workspace))
                except Exception:
                    if self._workspace.exists():
                        shutil.rmtree(str(self._workspace), ignore_errors=True)
                    raise

                # For analysis-only, remove stale analysis artifacts so
                # _detect_resume_point doesn't short-circuit to "complete".
                if is_analysis_only:
                    stale_summary = (
                        self._workspace / "results" / "analysis_summary.json"
                    )
                    if stale_summary.exists():
                        stale_summary.unlink()
                    stale_analysis_dir = self._workspace / "analysis"
                    if stale_analysis_dir.exists():
                        shutil.rmtree(str(stale_analysis_dir))
                        stale_analysis_dir.mkdir()

                self._resume_workspace = str(self._workspace)
                logger.info("Copied workspace %s → %s", source_ws, self._workspace)
            else:
                self._workspace: Path = source_ws
                self._resume_workspace = resume_workspace
                logger.info("Resuming in-place: %s", source_ws)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_dir = output_dir or (_get_repo_root() / "_rankevolve_workspace")
            self._workspace: Path = base_dir / f"task_{timestamp}"
            self._resume_workspace = resume_workspace

        # Session logging (initialized in run())
        self._dual_logger: list[Any] = []

    @property
    def token_stream(self) -> StreamBridgeAdapter:
        """The stream adapter to iterate for display tokens."""
        return self._adapter

    @property
    def workspace(self) -> Path:
        """The workspace directory for this session."""
        return self._workspace

    def _setup_session_logging(self) -> None:
        """Set up structured session logging with JsonLogger."""
        logs_dir = self._workspace / "logs"
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
        self._dual_logger = [
            (json_logger, LoggerConfig(pass_item_key_as="parts_key_path_root")),
            # NOTE: Intentionally omitting `print` (which the reference uses).
            # The chat CLI streams output via StreamBridgeAdapter, not stdout.
        ]

    async def _tail_cache_files(
        self,
        cache_dir: str,
        phase: str,
        pre_existing_cutoff: float = 0.0,
    ) -> None:
        """Background task: watch cache dir for new stream files, tail and forward to adapter.

        Delegates to WorkspaceStreamTailer for the actual file tailing logic.

        Args:
            cache_dir: The inferencer cache directory to watch.
            phase: Current phase label ("plan" or "implementation"), used as fallback.
            pre_existing_cutoff: Unix timestamp recorded before inferencers are built.
                Only files with mtime strictly before this cutoff are treated as
                pre-existing (skipped).  Files created during or after inferencer
                construction are always tailed.  0.0 disables the cutoff.
        """
        from rankevolve.src.common.streaming.file_tailer import WorkspaceStreamTailer

        tailer = WorkspaceStreamTailer(
            cache_dir,
            default_phase=phase,
            replay_existing=self._replay_streaming,
            pre_existing_cutoff=pre_existing_cutoff,
        )
        self._tailer = tailer
        await tailer.tail(callback=self._adapter.callback)

    def _build_dual_inferencer(self, phase: str) -> tuple[DualInferencer, str]:
        """Build a configured DualInferencer for a phase.

        Returns:
            (dual_inferencer, cache_folder) tuple.
        """
        cache_dir = self._workspace / "_runtime" / "inferencer_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_folder = str(cache_dir)

        tmp_offload_dir = self._workspace / "_runtime" / "tmp_output_files"
        tmp_offload_dir.mkdir(parents=True, exist_ok=True)

        base_type = self._base_inferencer_type
        review_type = self._review_inferencer_type

        # Build base inferencer
        base_system_prompt = (
            "You are an expert software architect and planner. "
            "Create detailed, actionable implementation plans with "
            "clear steps, file changes, and testing strategies."
            if base_type.startswith("claude_code")
            else ""
        )
        base_inf = _create_inferencer(
            base_type,
            str(self._root_folder),
            self._claude_model,
            base_system_prompt,
            f"{base_type}_base_{phase}",
            cache_folder,
            large_arg_temp_dir=str(tmp_offload_dir),
            timeout=self._timeout,
            inferencer_logger=self._dual_logger,
        )

        # Build review inferencer
        review_system_prompt = (
            "You are an expert code reviewer and implementer. "
            "Review plans and code critically, identify issues, "
            "and suggest improvements."
            if review_type.startswith("claude_code")
            else ""
        )
        review_inf = _create_inferencer(
            review_type,
            str(self._root_folder),
            self._claude_model,
            review_system_prompt,
            f"{review_type}_review_{phase}",
            cache_folder,
            large_arg_temp_dir=str(tmp_offload_dir),
            timeout=self._timeout,
            inferencer_logger=self._dual_logger,
        )

        # Create TemplateManager pointing to shared prompt_templates
        templates_dir = _get_templates_dir()
        prompt_tm = TemplateManager(
            templates=str(templates_dir),
            active_template_root_space=phase,
            enable_templated_feed=True,
            predefined_variables=True,
            template_version=self._template_version,
            cross_space_root=str(templates_dir),
        )

        proposal_placeholder = "main_response"

        # Create DualInferencer with full config
        dual = DualInferencer(
            base_inferencer=base_inf,
            review_inferencer=review_inf,
            consensus_config=ConsensusConfig(
                max_iterations=self._max_iterations,
                max_consensus_attempts=self._max_attempts,
                consensus_threshold=self._consensus_threshold,
                enable_counter_feedback=self._enable_counter_feedback,
            ),
            prompt_formatter=prompt_tm,
            initial_prompt="initial",
            review_prompt="review",
            followup_prompt="followup",
            placeholder_proposal=proposal_placeholder,
            phase=phase,
            response_parser=extract_delimited,
            logger=self._dual_logger,
            debug_mode=True,
            id=f"{phase.title()}DualInferencer",
        )

        return dual, cache_folder

    def _save_phase_results(
        self,
        results_dir: Path,
        output_dir: Path,
        phase: str,
        result: Any,
    ) -> None:
        """Save DualInferencerResponse results for a single phase.

        Modeled on test_plan_then_implement.py save_phase_results().
        """
        if not isinstance(result, DualInferencerResponse):
            (results_dir / f"{phase}_output.txt").write_text(str(result))
            return

        # Find the final output file by scanning for largest round index
        pattern = str(output_dir / f"round*_{phase}.md")
        output_files = glob.glob(pattern)

        if output_files:

            def _extract_round(path: str) -> int:
                match = re.search(r"round(\d+)_", Path(path).name)
                return int(match.group(1)) if match else -1

            latest_file = max(output_files, key=_extract_round)
            content = Path(latest_file).read_text()
            (results_dir / f"{phase}_final_output.txt").write_text(content)
            logger.info("[%s] Final output from: %s", phase, latest_file)
        else:
            (results_dir / f"{phase}_final_output.txt").write_text(
                str(result.base_response)
            )

        # Save consensus summary
        summary = {
            "phase": phase,
            "consensus_achieved": result.consensus_achieved,
            "total_iterations": result.total_iterations,
        }
        (results_dir / f"{phase}_consensus_summary.json").write_text(
            json.dumps(summary, indent=2)
        )

        # Save per-iteration files and full history
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

                prefix = f"{phase}_attempt_{attempt.attempt}_iter_{iter_rec.iteration}"
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

    async def run(
        self,
        request: str,
        task_mode: TaskMode = TaskMode.FULL_WORKFLOW,
    ) -> str:
        """Run the DualInferencer consensus workflow.

        Tokens/progress are pushed to self._adapter for display.
        Must be run as asyncio.create_task() concurrently with display iteration.

        Args:
            request: The coding task/request to execute.
            task_mode: Execution mode (PLAN_ONLY, FULL_WORKFLOW, etc.).

        Returns:
            The final response text.
        """
        try:
            sys.stderr.write("[bridge] Setting up DualInferencer workspace...\n")
            sys.stderr.flush()

            # Setup workspace directories
            self._workspace.mkdir(parents=True, exist_ok=True)
            (self._workspace / "outputs").mkdir(exist_ok=True)
            (self._workspace / "results").mkdir(exist_ok=True)

            # Set up session logging
            self._setup_session_logging()

            # Save request (skip if resuming — file already exists)
            request_path = self._workspace / "request.txt"
            if not request_path.exists():
                request_path.write_text(request)

            # Pre-task: retrieve relevant knowledge context
            knowledge_context = ""
            if self._knowledge_bridge is not None:
                try:
                    knowledge_context = self._knowledge_bridge.query_for_task(request)
                    if knowledge_context.strip():
                        (self._workspace / "knowledge_context.txt").write_text(
                            knowledge_context
                        )
                        sys.stderr.write(
                            f"[bridge] Retrieved {len(knowledge_context)} chars of knowledge context\n"
                        )
                        sys.stderr.flush()
                except Exception as e:
                    logger.warning("Knowledge retrieval failed: %s", e)

            # Augment request with knowledge context if available
            augmented_request = request
            if knowledge_context.strip():
                augmented_request = (
                    request + "\n\n## Retrieved Knowledge Context\n" + knowledge_context
                )

            sys.stderr.write(f"[bridge] Workspace: {self._workspace}\n")
            sys.stderr.flush()

            if task_mode == TaskMode.PLAN_ONLY:
                response_text = await self._run_phase("plan", augmented_request)
            elif task_mode == TaskMode.EXECUTE_ONLY:
                response_text = await self._run_phase(
                    "implementation", augmented_request
                )
            elif task_mode == TaskMode.FULL_WORKFLOW:
                response_text = await self._run_full_workflow(
                    augmented_request, request
                )
            elif task_mode == TaskMode.PLAN_THEN_CONFIRM:
                # For now, same as PLAN_ONLY; confirmation logic is in the UI layer
                response_text = await self._run_phase("plan", augmented_request)
            else:
                response_text = await self._run_phase("plan", augmented_request)

            # Post-task: feed results back into knowledge base
            if (
                self._knowledge_bridge is not None
                and task_mode != TaskMode.PLAN_THEN_CONFIRM
                and response_text.strip()
            ):
                try:
                    self._knowledge_bridge.add_task_result(
                        request,
                        response_text,
                        metadata={
                            "task_mode": task_mode.value,
                            "workspace": str(self._workspace),
                        },
                    )
                except Exception as e:
                    logger.warning("Failed to save task result to KB: %s", e)

            return response_text

        except Exception:
            logger.exception("DualInferencer run failed")
            sys.stderr.write("[bridge] DualInferencer run FAILED (see log)\n")
            sys.stderr.flush()
            raise
        finally:
            await self._adapter.close()

    async def _run_full_workflow(
        self,
        augmented_request: str,
        original_request: str,
    ) -> str:
        """Run FULL_WORKFLOW using PlanThenImplementInferencer.

        Replaces the manual plan→implementation string chaining with proper PTI.

        Args:
            augmented_request: Request with optional knowledge context.
            original_request: Original user request (without knowledge augmentation).

        Returns:
            The final response text from the executor.
        """
        from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.flow_inferencers.plan_then_implement_inferencer import (
            PlanThenImplementInferencer,
        )

        # Record cutoff time BEFORE building inferencers.
        # _tail_cache_files uses this to distinguish pre-existing stream files
        # (from copied workspaces) vs. files created during this session.
        self._tail_cutoff = time.time()

        plan_dual, cache_folder = self._build_dual_inferencer("plan")
        impl_dual, _ = self._build_dual_inferencer("implementation")

        # Build analyzer DualInferencer if analysis is enabled
        analyzer_dual: DualInferencer | None = None
        if self._enable_analysis:
            analyzer_dual, _ = self._build_dual_inferencer("analysis")
            (self._workspace / "analysis").mkdir(parents=True, exist_ok=True)

        templates_dir = _get_templates_dir()
        output_dir = self._workspace.resolve() / "outputs"
        plan_output_path = str(output_dir) + "/round{{ round_index }}_plan.md"
        impl_output_path = str(output_dir) + "/round{{ round_index }}_implementation.md"

        pti_kwargs: dict[str, Any] = dict(
            planner_inferencer=plan_dual,
            executor_inferencer=impl_dual,
            interactive=None,
            planner_phase="plan",
            executor_phase="implementation",
            planner_outputs_plan_to_file=True,
            logger=self._dual_logger,
            debug_mode=True,
            id="PlanThenImplementInferencer",
            enable_planning=self._enable_planning,
            enable_implementation=self._enable_implementation,
            enable_analysis=self._enable_analysis,
            enable_multiple_iterations=self._enable_multiple_iterations,
            max_meta_iterations=self._max_meta_iterations,
            analysis_mode=self._analysis_mode,
            analysis_templates_dir=str(templates_dir),
            enable_result_save=StepResultSaveOptions.Always,
            resume_with_saved_results=True,
        )
        if analyzer_dual is not None:
            pti_kwargs["analyzer_inferencer"] = analyzer_dual
        pti_kwargs["workspace_path"] = str(self._workspace)
        if self._resume_workspace is not None:
            pti_kwargs["resume_workspace"] = self._resume_workspace
        if self._initial_plan_file:
            pti_kwargs["initial_plan_file"] = self._initial_plan_file

        pti = PlanThenImplementInferencer(**pti_kwargs)

        sys.stderr.write("[bridge] Running PlanThenImplementInferencer...\n")
        sys.stderr.flush()

        self._tailed_bytes = 0
        tail_task = asyncio.create_task(
            self._tail_cache_files(
                cache_folder, "plan", pre_existing_cutoff=self._tail_cutoff
            )
        )

        # Session context values flow as kwargs (highest merge priority)
        # since predefined_variables=True uses VariableLoader instead of static dict
        session_vars = {
            k: v
            for k, v in self._session_context.items()
            if isinstance(v, (str, int, float, bool))
        }

        try:
            async with pti:
                result = await pti.ainfer(
                    augmented_request,
                    inference_config={
                        "plan_config": {
                            "output_path": plan_output_path,
                            **session_vars,
                        },
                        "implement_config": {
                            "output_path": impl_output_path,
                            **session_vars,
                        },
                    },
                )
        except Exception:
            logger.exception("PlanThenImplementInferencer failed")
            raise
        finally:
            tail_task.cancel()
            try:
                await tail_task
            except asyncio.CancelledError:
                pass

        # Extract final response
        response_text = str(result.base_response)

        sys.stderr.write(
            f"[bridge] PTI complete. Tailed {self._tailed_bytes} bytes to UI.\n"
        )
        sys.stderr.flush()

        # Save results for both phases
        results_dir = self._workspace / "results"
        output_dir_path = self._workspace / "outputs"
        if result.plan_response is not None:
            self._save_phase_results(
                results_dir, output_dir_path, "plan", result.plan_response
            )
        if result.executor_output is not None:
            self._save_phase_results(
                results_dir, output_dir_path, "implementation", result.executor_output
            )

        # Push completion to UI
        if (
            self._enable_analysis
            and not self._enable_planning
            and not self._enable_implementation
        ):
            display_phase = "analysis"
        else:
            display_phase = "implementation"

        if self._tailed_bytes == 0:
            await self._adapter.callback(
                response_text,
                {"phase": display_phase, "agent_id": "base"},
            )
        else:
            await self._adapter.callback(
                "\n\n--- full workflow complete ---\n",
                {"phase": display_phase, "agent_id": "system"},
            )

        return response_text

    async def _run_phase(
        self,
        phase: str,
        request: str,
    ) -> str:
        """Run a single DualInferencer phase (plan or implementation).

        Creates fresh inferencer instances per phase to avoid stale connection
        state between phases.

        Args:
            phase: "plan" or "implementation"
            request: The request text for this phase.

        Returns:
            The final consensus response text.
        """
        await self._adapter.callback(
            f"Starting {phase} phase...\n",
            {"phase": phase, "agent_id": "system"},
        )

        dual, cache_folder = self._build_dual_inferencer(phase)

        # Output path template with Jinja2 round_index variable
        output_dir = self._workspace.resolve() / "outputs"
        output_path = str(output_dir) + "/round{{ round_index }}_" + phase + ".md"

        sys.stderr.write(f"[bridge] Running DualInferencer ({phase})...\n")
        sys.stderr.flush()

        # Start cache file tailer to stream intermediate output to UI
        self._tailed_bytes = 0
        tail_task = asyncio.create_task(
            self._tail_cache_files(cache_folder, phase, pre_existing_cutoff=time.time())
        )

        # Session context as kwargs for VariableLoader-based templates
        session_vars = {
            k: v
            for k, v in self._session_context.items()
            if isinstance(v, (str, int, float, bool))
        }

        # Run with proper lifecycle
        try:
            async with dual:
                result = await dual.ainfer(
                    request,
                    inference_config={"output_path": output_path, **session_vars},
                )
        finally:
            tail_task.cancel()
            try:
                await tail_task
            except asyncio.CancelledError:
                pass

        # Extract the final text
        response_text = (
            str(result.base_response)
            if hasattr(result, "base_response")
            else str(result)
        )

        sys.stderr.write(
            f"[bridge] {phase} phase complete. "
            f"Consensus: {'achieved' if hasattr(result, 'consensus_achieved') and result.consensus_achieved else 'not achieved'}. "
            f"Tailed {self._tailed_bytes} bytes to UI.\n"
        )
        sys.stderr.flush()

        # Save phase results
        results_dir = self._workspace / "results"
        output_dir_path = self._workspace / "outputs"
        self._save_phase_results(results_dir, output_dir_path, phase, result)

        # Only push final result if tailer didn't stream anything
        # (avoids duplicating content already shown to user)
        if self._tailed_bytes == 0:
            await self._adapter.callback(
                response_text,
                {"phase": phase, "agent_id": "base"},
            )
        else:
            # Push a brief summary instead of the full (already-streamed) text
            await self._adapter.callback(
                f"\n\n--- {phase} phase complete ---\n",
                {"phase": phase, "agent_id": "system"},
            )

        return response_text
