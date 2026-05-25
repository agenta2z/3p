# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict
"""Bridges the BreakdownThenAggregateInferencer into the chat CLI.

Follows the same pattern as DualInferencerBridge: constructs the
inferencer pipeline, runs it, and streams output via StreamBridgeAdapter.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.common import (
    ConsensusConfig,
)
from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.flow_inferencers.breakdown_then_aggregate_inferencer import (
    BreakdownThenAggregateInferencer,
    parse_numbered_list,
)
from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.flow_inferencers.dual_inferencer import (
    DualInferencer,
)
from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.flow_inferencers.plan_then_implement_inferencer import (
    PlanThenImplementInferencer,
)
from rankevolve.src.agentic_foundation.common.inferencers.inferencer_base import (
    InferencerBase,
)
from rankevolve.src.server.stream_bridge import StreamBridgeAdapter
from rankevolve.src.utils.common_objects.workflow.common.step_result_save_options import (
    StepResultSaveOptions,
)
from rankevolve.src.utils.string_utils.formatting.template_manager import (
    TemplateManager,
)

logger: logging.Logger = logging.getLogger(__name__)


def _get_repo_root() -> Path:
    """Walk up from this file to find the repository root (.sl directory)."""
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


def _get_templates_dir() -> Path:
    """Locate the shared prompt_templates/ directory.

    Tries importlib.resources first (works in Buck builds), then
    falls back to filesystem relative path for local development.
    """
    try:
        import importlib.resources as pkg_resources

        ref = pkg_resources.files("rankevolve.src.resources.prompt_templates")
        candidate = Path(str(ref))
        if candidate.is_dir():
            return candidate
    except (ImportError, TypeError, NotADirectoryError):
        pass

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


def _parse_max_from_range(value: str | int) -> int | None:
    """Extract the largest integer from a range string for BTA max_breakdown.

    Examples:
        "5 to 20 (or you really want to suggest more)" → 20
        "5-20" → 20
        "10" → 10
        3 → 3
        "or more" → None  (no cap)
    """
    if isinstance(value, int):
        return value
    numbers = re.findall(r"\d+", str(value))
    if numbers:
        return max(int(n) for n in numbers)
    return None  # no numbers found — don't cap


def parse_task_breakdown_response(raw: Any) -> list[str]:
    """Parse structured task breakdown JSON response, fallback to numbered list.

    The task_breakdown template instructs the LLM to output JSON with subtasks
    inside <Response> tags. This parser extracts subtask descriptions from
    that JSON, falling back to parse_numbered_list for backward compatibility.
    """
    text = str(raw)

    # Try to find JSON in ```json blocks, optionally within <Response> tags
    response_match = re.search(r"<Response>(.*?)</Response>", text, re.DOTALL)
    search_text = response_match.group(1) if response_match else text

    json_match = re.search(r"```json[\s\w]*\n(\{.*?\})\s*```", search_text, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            subtasks = data.get("subtasks", [])
            if subtasks:
                queries: list[str] = []
                for st in subtasks:
                    if not isinstance(st, dict) or "description" not in st:
                        continue
                    parts = [st["description"]]
                    todos = st.get("todos")
                    if isinstance(todos, list) and todos:
                        parts.append("\nResearch todos:")
                        for todo in todos:
                            parts.append(f"- {todo}")
                    queries.append("\n".join(parts))
                if queries:
                    return queries
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

    # Fallback: numbered list parsing
    return parse_numbered_list(text)


def _session_vars(ctx: dict[str, Any]) -> dict[str, Any]:
    """Extract session context values suitable for inference_config kwargs."""
    return {k: v for k, v in ctx.items() if isinstance(v, (str, int, float, bool))}


def parse_research_propose_options(
    args: str,
) -> tuple[str, dict[str, Any]]:
    """Parse /research-propose inline flags.

    Supported flags:
        --research-only             Run breakdown + deep research only
        --disable-unified-proposal  Skip the final unified proposal
        --max-breakdown N           Guidance for number of breakdown subtasks
        --model <name>              Override LLM model
        --resume <path>             Resume from a previous workspace
        --base-inferencer <type>    Override base inferencer type
        --review-inferencer <type>  Override review inferencer type

    Returns:
        (request_text, options_dict)
    """
    options: dict[str, Any] = {}
    tokens = args.split()
    request_parts: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "--research-only":
            options["research_only"] = True
        elif tok == "--disable-unified-proposal":
            options["disable_unified_proposal"] = True
        elif tok == "--breakdown-only":
            options["breakdown_only"] = True
        elif tok in ("--max-breakdown", "--max-queries") and i + 1 < len(tokens):
            i += 1
            options["max_breakdown"] = tokens[i]
        elif tok == "--model" and i + 1 < len(tokens):
            i += 1
            options["model"] = tokens[i]
        elif tok == "--resume" and i + 1 < len(tokens):
            i += 1
            options["resume"] = tokens[i]
        elif tok == "--base-inferencer" and i + 1 < len(tokens):
            i += 1
            options["base_inferencer"] = tokens[i]
        elif tok == "--review-inferencer" and i + 1 < len(tokens):
            i += 1
            options["review_inferencer"] = tokens[i]
        elif tok == "--research-inferencer" and i + 1 < len(tokens):
            i += 1
            options["research_inferencer"] = tokens[i]
        elif tok == "--proposal-inferencer" and i + 1 < len(tokens):
            i += 1
            options["proposal_inferencer"] = tokens[i]
        elif tok == "--workflow-target-path" and i + 1 < len(tokens):
            i += 1
            options["workflow_target_path"] = tokens[i]
        elif tok == "--docs-path" and i + 1 < len(tokens):
            i += 1
            options["docs_path"] = tokens[i]
        elif tok == "--max-researches" and i + 1 < len(tokens):
            i += 1
            try:
                options["max_researches"] = int(tokens[i])
            except ValueError:
                request_parts.append(tok)
                request_parts.append(tokens[i])
        else:
            request_parts.append(tok)
        i += 1
    return " ".join(request_parts), options


class ResearchProposeBridge:
    """Bridge for the /research-propose CLI directive.

    Constructs and runs a BreakdownThenAggregateInferencer pipeline,
    streaming output via StreamBridgeAdapter.
    """

    def __init__(
        self,
        root_folder: Path,
        model: str | None = None,
        research_only: bool = False,
        disable_unified_proposal: bool = False,
        max_breakdown: str | int = "5 to 20 (or you really want to suggest more)",
        max_researches: int | None = None,
        output_dir: Path | None = None,
        knowledge_bridge: Any | None = None,
        session_context: dict[str, Any] | None = None,
        resume_workspace: str | None = None,
        base_inferencer_type: str | None = None,
        review_inferencer_type: str | None = None,
        research_inferencer_type: str | None = None,
        proposal_inferencer_type: str | None = None,
        breakdown_only: bool = False,
    ) -> None:
        self._root_folder = root_folder
        self._session_context = dict(session_context) if session_context else {}
        if "session_root_path" not in self._session_context:
            self._session_context["session_root_path"] = str(root_folder)
        self._model = model
        self._research_only = research_only
        self._disable_unified_proposal = disable_unified_proposal
        self._max_breakdown = str(max_breakdown)
        self._max_researches = max_researches
        self._breakdown_only = breakdown_only
        self._output_dir = output_dir
        self._knowledge_bridge = knowledge_bridge
        self._resume_workspace = resume_workspace
        self._base_inferencer_type = base_inferencer_type or "devmate_cli"
        self._review_inferencer_type = review_inferencer_type or "devmate_cli"
        self._research_inferencer_type = research_inferencer_type or "metamate_cli"
        self._proposal_inferencer_type = (
            proposal_inferencer_type or self._base_inferencer_type
        )
        self._adapter = StreamBridgeAdapter()

        # Create workspace (at repo root, matching DualInferencerBridge pattern)
        if resume_workspace:
            self._workspace = Path(resume_workspace)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base = output_dir or (_get_repo_root() / "_rankevolve_workspace")
            self._workspace = base / f"research_{timestamp}"
        self._workspace.mkdir(parents=True, exist_ok=True)
        (self._workspace / "outputs").mkdir(exist_ok=True)
        (self._workspace / "results").mkdir(exist_ok=True)
        (self._workspace / "logs").mkdir(exist_ok=True)
        (self._workspace / "_runtime" / "inferencer_cache").mkdir(
            parents=True, exist_ok=True
        )
        (self._workspace / "_runtime" / "tmp_output_files").mkdir(
            parents=True, exist_ok=True
        )

    @property
    def token_stream(self) -> StreamBridgeAdapter:
        """Stream adapter for display layer."""
        return self._adapter

    @property
    def workspace(self) -> Path:
        """Workspace directory for this session."""
        return self._workspace

    def _setup_session_logging(self) -> None:
        """Set up structured session logging with JsonLogger."""
        logs_dir = self._workspace / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

        try:
            from rich_python_utils.common_objects.debuggable import LoggerConfig
            from rankevolve.src.utils.io_utils.json_io import JsonLogger, SpaceExtMode

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
            self._session_logger: list[Any] = [
                (
                    json_logger,
                    LoggerConfig(pass_item_key_as="parts_key_path_root"),
                ),
            ]
        except ImportError:
            logger.warning("Could not set up session logging — imports unavailable")
            self._session_logger = []

    def _create_inferencer(
        self, role: str, inferencer_type: str | None = None
    ) -> InferencerBase:
        """Create an inferencer for the given role.

        Follows the same pattern as ``dual_inferencer_bridge._create_inferencer``
        so that each sub-inferencer gets ``cache_folder``, ``logger``, and ``id``
        — producing the rich workspace logging (``logs/session/*.jsonl``,
        ``_runtime/inferencer_cache/``) that DualInferencerBridge creates.

        Args:
            role: Role label for the inferencer (used in id and log filenames).
            inferencer_type: Override type. Defaults to ``self._base_inferencer_type``.
        """
        inf_type = inferencer_type or self._base_inferencer_type
        cache_folder = str(self._workspace / "_runtime" / "inferencer_cache")
        tmp_dir = str(self._workspace / "_runtime" / "tmp_output_files")
        inf_logger = getattr(self, "_session_logger", None)
        inf_id = f"{inf_type}_{role}"

        try:
            if inf_type == "metamate_sdk":
                from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers import (
                    MetamateSDKInferencer,
                )

                return MetamateSDKInferencer(
                    model_id=self._model or "",
                    cache_folder=cache_folder,
                    id=inf_id,
                )
            elif inf_type == "metamate_cli":
                from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.external.metamate.metamate_cli_inferencer import (
                    MetamateCliInferencer,
                )

                kwargs: dict[str, Any] = {"id": inf_id, "cache_folder": cache_folder}
                if inf_logger is not None:
                    kwargs["logger"] = inf_logger
                return MetamateCliInferencer(**kwargs)
            elif inf_type == "devmate_cli":
                from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.external.devmate.devmate_cli_inferencer import (
                    DevmateCliInferencer,
                )

                kwargs: dict[str, Any] = {
                    "id": inf_id,
                    "cache_folder": cache_folder,
                }
                if self._model:
                    kwargs["model_name"] = self._model
                if self._session_context.get("session_root_path"):
                    kwargs["root_folder"] = self._session_context["session_root_path"]
                if inf_logger is not None:
                    kwargs["logger"] = inf_logger
                if tmp_dir:
                    kwargs["large_arg_temp_dir"] = tmp_dir
                return DevmateCliInferencer(**kwargs)
            else:
                from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers import (
                    MetamateSDKInferencer,
                )

                return MetamateSDKInferencer(
                    model_id=self._model or "",
                    cache_folder=cache_folder,
                    id=inf_id,
                )
        except ImportError:
            logger.warning(
                "Could not import inferencer type %s, using stub",
                self._base_inferencer_type,
            )
            raise

    def _build_dual(
        self,
        role: str,
        template_space: str,
        inferencer_type: str | None = None,
        template_version: str = "",
    ) -> DualInferencer:
        """Create a DualInferencer with a prompt template.

        Builds in initial-only mode (``max_iterations=0``).
        Template variables are resolved natively via TemplateManager's
        ``_variables`` file cascade + ``inference_config`` kwargs.
        """
        base_inf = self._create_inferencer(role, inferencer_type=inferencer_type)

        templates_dir = _get_templates_dir()
        prompt_tm = TemplateManager(
            templates=str(templates_dir),
            active_template_root_space=template_space,
            enable_templated_feed=True,
            predefined_variables=True,
            template_version=template_version,
        )

        return DualInferencer(
            base_inferencer=base_inf,
            review_inferencer=base_inf,  # unused with max_iterations=0
            consensus_config=ConsensusConfig(max_iterations=0),
            prompt_formatter=prompt_tm,
            initial_prompt="initial",
            review_prompt="review",
            followup_prompt="followup",
            logger=getattr(self, "_session_logger", []),
            debug_mode=True,
            id=f"{template_space.title().replace('_', '')}DualInferencer_{role}",
        )

    def _create_breakdown_dual_inferencer(self) -> DualInferencer:
        """Create breakdown DualInferencer with task_breakdown template."""
        return self._build_dual(
            role="breakdown",
            template_space="task_breakdown",
            inferencer_type="devmate_cli",
            template_version="research_codebase",
        )

    def _create_worker_pti(
        self, role: str, outputs_dir: Path | None = None
    ) -> PlanThenImplementInferencer:
        """Create a PTI worker: deep_research (plan) → individual_proposal (implement).

        Both phases use DualInferencers in initial-only mode (max_iterations=0).
        Template variables (session_root_path, docs_path, etc.) are resolved
        natively via _variables files + inference_config kwargs passed by BTA.

        If ``outputs_dir`` is provided, both phases write full output to files
        and return concise summaries via <Response> tags.
        """
        # Research phase uses research_inferencer_type (e.g., metamate_cli for
        # knowledge search). Proposal phase uses proposal_inferencer_type (e.g.,
        # devmate_cli for code reading and actionable proposals).
        plan_dual = self._build_dual(
            role=f"{role}_research",
            template_space="deep_research",
            inferencer_type=self._research_inferencer_type,
        )
        impl_dual = self._build_dual(
            role=f"{role}_proposal",
            template_space="plan",
            inferencer_type=self._proposal_inferencer_type,
            template_version="individual_proposal",
        )

        pti_kwargs: dict[str, Any] = dict(
            planner_inferencer=plan_dual,
            executor_inferencer=impl_dual,
            planner_phase="research",
            executor_phase="proposal",
            enable_planning=True,
            enable_implementation=not self._research_only,
            interactive=None,
            logger=getattr(self, "_session_logger", []),
            debug_mode=True,
            id=f"PTIWorker_{role}",
            # Enable PTI-level step checkpointing for recursive resume.
            # BTA worker nodes don't save coarse results — PTI handles its
            # own resume at the step level (plan done → skip, implement not
            # done → run). This enables research-only → full resume naturally.
            enable_result_save=StepResultSaveOptions.Always,
            resume_with_saved_results=(self._resume_workspace is not None),
        )
        if outputs_dir:
            pti_kwargs["planner_outputs_plan_to_file"] = True
            # Give PTI its own workspace for step-level checkpoints
            worker_workspace = str(outputs_dir.parent / "checkpoints" / "bta" / role)
            os.makedirs(worker_workspace, exist_ok=True)
            pti_kwargs["workspace_path"] = worker_workspace
        else:
            pti_kwargs["planner_outputs_plan_to_file"] = False

        return PlanThenImplementInferencer(**pti_kwargs)

    async def run(self, request: str) -> str:
        """Run the breakdown-then-aggregate pipeline."""
        try:
            await self._adapter.callback("Starting research-propose workflow...\n", {})

            # Save request (skip if resuming — file already exists)
            request_path = self._workspace / "request.txt"
            if not request_path.exists():
                request_path.write_text(request)

            # Set up session logging (matching DualInferencerBridge pattern)
            self._setup_session_logging()

            # Clear stale implement checkpoints from research-only runs.
            # When resuming with proposals enabled after a research-only run,
            # PTI's implement step has a saved empty checkpoint that blocks
            # re-execution. Remove these so PTI re-runs the implement step.
            if self._resume_workspace and not self._research_only:
                bta_dir = self._workspace / "checkpoints" / "bta"
                if bta_dir.exists():
                    for worker_dir in sorted(bta_dir.glob("worker_*")):
                        pti_dir = worker_dir / "checkpoints" / "pti"
                        if not pti_dir.exists():
                            continue
                        impl_ckpt = pti_dir / "step_implement___seq3.json"
                        if impl_ckpt.exists():
                            content = impl_ckpt.read_text().strip()
                            if content in ('""', "", "null"):
                                logger.info(
                                    "Clearing stale empty implement checkpoint: %s",
                                    impl_ckpt,
                                )
                                impl_ckpt.unlink()
                                # Reset workflow checkpoint so PTI re-runs
                                for f in pti_dir.glob("step___wf_checkpoint__*"):
                                    f.unlink()
                                for f in pti_dir.glob("step_analysis_*"):
                                    f.unlink()
                                for f in pti_dir.glob("step_approval_*"):
                                    f.unlink()

            # Session vars flow through inference_config → TemplateManager → _variables
            outputs_dir = self._workspace / "outputs"
            # proposals_dir: where individual proposal files live (for aggregator)
            proposals_dir = str(self._workspace / "checkpoints" / "bta")
            session_config = {
                **_session_vars(self._session_context),
                "max_breakdown": self._max_breakdown,
                "proposals_dir": proposals_dir,
                # NOTE: output_path is intentionally NOT set here for breakdown.
                # DualInferencer's _maybe_replace_with_file_reference would replace
                # the response with a short file reference, losing the <Response>
                # JSON that parse_task_breakdown_response() needs for resume.
                # The template still instructs the LLM to write full analysis to
                # {{ output_path }}, but since output_path is empty, the LLM
                # includes everything inline — which is fine since the parser
                # only extracts the <Response> JSON block.
            }
            augmented_request = request

            # Build breakdown inferencer as DualInferencer with task_breakdown template
            breakdown_inf = self._create_breakdown_dual_inferencer()

            if self._breakdown_only:
                # Breakdown-only mode: run decomposition, skip workers/aggregation
                result = await breakdown_inf.ainfer(
                    augmented_request, inference_config=session_config
                )
                result_str = str(result)
                (self._workspace / "outputs" / "breakdown_result.md").write_text(
                    result_str
                )
                # Save parsed sub_queries as checkpoint for future resume
                sub_queries = parse_task_breakdown_response(result)
                ckpt_dir = self._workspace / "checkpoints" / "bta"
                ckpt_dir.mkdir(parents=True, exist_ok=True)
                (ckpt_dir / "breakdown_result.json").write_text(
                    json.dumps(
                        {"raw_output": result_str, "sub_queries": sub_queries},
                        indent=2,
                    )
                )
            else:
                # Full BTA pipeline — workers are PTI (research → proposal)
                def create_worker(
                    sub_query: str, index: int, **kwargs: Any
                ) -> PlanThenImplementInferencer:
                    pti = self._create_worker_pti(
                        f"worker_{index}", outputs_dir=outputs_dir
                    )
                    # Inject per-worker output paths into PTI's inference_config
                    research_path = str(outputs_dir / f"worker_{index}_research.md")
                    proposal_path = str(outputs_dir / f"worker_{index}_proposal.md")
                    original_ainfer = pti.ainfer

                    async def ainfer_with_paths(inp, inference_config=None, **kw):
                        cfg = dict(inference_config or {})
                        cfg["plan_config"] = {
                            **cfg.get("plan_config", {}),
                            "output_path": research_path,
                        }
                        cfg["implement_config"] = {
                            **cfg.get("implement_config", {}),
                            "output_path": proposal_path,
                            "research_output_path": research_path,
                        }
                        result = await original_ainfer(inp, inference_config=cfg, **kw)
                        # Extract text from PTI response object so BTA/aggregator
                        # receives readable text, not raw PlanThenImplementResponse repr.
                        if (
                            hasattr(result, "executor_output")
                            and result.executor_output
                        ):
                            return result.executor_output
                        if hasattr(result, "plan_output") and result.plan_output:
                            return result.plan_output
                        if hasattr(result, "base_response"):
                            return str(result.base_response)
                        return str(result)

                    pti.ainfer = ainfer_with_paths
                    return pti

                aggregator = None
                if not self._research_only and not self._disable_unified_proposal:
                    # Aggregator is a PTI (plan-only) with unified_proposal preamble.
                    # It reads all individual proposal files and synthesizes them.
                    aggregator_dual = self._build_dual(
                        role="aggregator",
                        template_space="plan",
                        inferencer_type=self._base_inferencer_type,
                        template_version="unified_proposal",
                    )
                    aggregator = PlanThenImplementInferencer(
                        planner_inferencer=aggregator_dual,
                        executor_inferencer=aggregator_dual,  # unused (plan-only)
                        planner_phase="plan",
                        executor_phase="implementation",
                        enable_planning=True,
                        enable_implementation=False,
                        planner_outputs_plan_to_file=True,
                        interactive=None,
                        logger=getattr(self, "_session_logger", []),
                        debug_mode=True,
                        id="UnifiedProposalPTI",
                        enable_result_save=StepResultSaveOptions.Always,
                        resume_with_saved_results=(self._resume_workspace is not None),
                        workspace_path=str(
                            self._workspace / "checkpoints" / "bta" / "aggregator"
                        ),
                    )

                def agg_prompt_builder(
                    worker_results: tuple, original_query: str = ""
                ) -> str:
                    parts = [f"## Original Research Goal\n{original_query}\n"]
                    for idx, res in enumerate(worker_results):
                        # Include both the file path and a summary
                        proposal_path = str(
                            outputs_dir.parent
                            / "checkpoints"
                            / "bta"
                            / f"worker_{idx}"
                            / "outputs"
                            / f"worker_{idx}_proposal.md"
                        )
                        parts.append(
                            f"### Individual Proposal {idx + 1}\n"
                            f"Full proposal file: `{proposal_path}`\n"
                            f"You MUST read this file for the complete proposal.\n\n"
                            f"Summary: {res}"
                        )
                    return "\n\n".join(parts)

                checkpoint_dir = str(self._workspace / "checkpoints" / "bta")
                os.makedirs(checkpoint_dir, exist_ok=True)

                # max_researches caps how many workers run; falls back to
                # parsing the upper bound from the breakdown guidance string.
                max_breakdown = (
                    self._max_researches
                    if self._max_researches is not None
                    else _parse_max_from_range(self._max_breakdown)
                )

                bta = BreakdownThenAggregateInferencer(
                    breakdown_inferencer=breakdown_inf,
                    max_breakdown=max_breakdown,
                    breakdown_parser=parse_task_breakdown_response,
                    worker_factory=create_worker,
                    aggregator_inferencer=aggregator,
                    aggregator_prompt_builder=agg_prompt_builder,
                    checkpoint_dir=checkpoint_dir,
                    enable_result_save=StepResultSaveOptions.Always,
                    resume_with_saved_results=(self._resume_workspace is not None),
                    checkpoint_mode="jsonfy",
                )

                result = await bta.ainfer(
                    augmented_request, inference_config=session_config
                )
                # Extract text from response objects
                if hasattr(result, "plan_output") and result.plan_output:
                    result_str = str(result.plan_output)
                elif hasattr(result, "executor_output") and result.executor_output:
                    result_str = str(result.executor_output)
                elif hasattr(result, "base_response"):
                    result_str = str(result.base_response)
                else:
                    result_str = str(result)
                (self._workspace / "outputs" / "final_result.md").write_text(result_str)

                # Copy the aggregator's unified plan to outputs/ as the
                # primary viewable artifact (final_result.md is a raw BTA
                # dump with tool artifacts; unified_plan.md is the real
                # synthesis with deduplicated H1-H25 hypotheses).
                unified_src = (
                    self._workspace
                    / "checkpoints"
                    / "bta"
                    / "aggregator"
                    / "outputs"
                    / "unified_plan.md"
                )
                if unified_src.is_file():
                    import shutil

                    shutil.copy2(
                        str(unified_src),
                        str(self._workspace / "outputs" / "unified_plan.md"),
                    )

            # Save structured results (matching DualInferencerBridge pattern)
            results_dir = self._workspace / "results"
            results_dir.mkdir(parents=True, exist_ok=True)
            (results_dir / "research_output.txt").write_text(result_str)

            # Save summary metadata
            summary = {
                "status": "completed",
                "mode": "breakdown_only" if self._breakdown_only else "full",
                "base_inferencer": self._base_inferencer_type,
                "max_breakdown": self._max_breakdown,
                "research_only": self._research_only,
                "result_length": len(result_str),
                "workspace": str(self._workspace),
            }
            (results_dir / "research_summary.json").write_text(
                json.dumps(summary, indent=2)
            )

            await self._adapter.callback(result_str, {"phase": "result"})
            return result_str

        except Exception as e:
            logger.error("Research-propose pipeline failed: %s", e)
            await self._adapter.callback(f"\nError: {e}\n", {"error": True})
            raise
        finally:
            await self._adapter.close()
