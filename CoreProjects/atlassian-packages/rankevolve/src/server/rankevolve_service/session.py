# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.

"""RankEvolve session — holds per-session agent state."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from attr import attrib, attrs
from agent_foundation.ui.queue_interactive import (
    QueueInteractive,
)
from rankevolve.src.server.config import AppConfig
from rankevolve.src.server.conversation import Conversation
from rankevolve.src.server.workflow_context import WorkflowContext
from rankevolve.src.utils.service_utils.session_management.session_base import (
    SessionBase,
)


@attrs(slots=False)
class RankEvolveSession(SessionBase):
    """Per-session state for the RankEvolve agent service.

    Lazily initialized on first message — only info and logger are set at creation.

    Attributes:
        interactive: QueueInteractive for queue-based I/O with InteractionFlags.
        llm_client: The LLM client for this session.
        conversation: Chat history.
        app_config: Session-scoped copy of AppConfig.
        knowledge_bridge: Optional knowledge bridge.
        active_task: Currently running asyncio.Task (if any).
        processing_lock: Per-session lock for message ordering.
    """

    interactive: QueueInteractive | None = attrib(default=None, kw_only=True)
    llm_client: Any = attrib(default=None, kw_only=True)
    conversation: Conversation | None = attrib(default=None, kw_only=True)
    app_config: AppConfig | None = attrib(default=None, kw_only=True)
    knowledge_bridge: Any = attrib(default=None, kw_only=True)
    conversation_inferencer: Any = attrib(default=None, kw_only=True)
    tool_registry: dict | None = attrib(default=None, kw_only=True)
    workflow_context: WorkflowContext = attrib(factory=WorkflowContext, kw_only=True)

    @property
    def session_tasks_dir(self) -> Path:
        """Per-session directory holding all task workspaces this session launched.

        Lives at ``<server>/sessions/<session_dir>/tasks/`` so that task
        workspaces are nested under the owning session — replaces the legacy
        flat ``<server>/tasks/`` layout. Callers (DualInferencerBridge,
        ResearchProposeBridge, mock_task, _exec_submission_run) mkdir the
        per-task subdir lazily on first task launch; nothing creates an empty
        ``tasks/`` upfront.
        """
        return self.session_logger.session_dir / "tasks"

    @property
    def session_context(self) -> dict[str, Any]:
        """ALL session-level context for prompt injection.

        Combines static config and rendered workflow state into a single dict.
        Consumed by TemplateManager.predefined_variables AND template.render().
        """
        ctx: dict[str, Any] = {}
        # Static config
        if hasattr(self.info, "session_root_path") and self.info.session_root_path:
            ctx["session_root_path"] = self.info.session_root_path
        else:
            ctx["session_root_path"] = "not set"
        if (
            hasattr(self.info, "workflow_target_path")
            and self.info.workflow_target_path
        ):
            ctx["workflow_target_path"] = self.info.workflow_target_path
        else:
            ctx["workflow_target_path"] = "not set"
        ctx["model"] = (
            self.app_config.model if self.app_config and self.app_config.model else ""
        )
        # Workflow state
        wc = self.workflow_context
        # Populate tool_phase_map from SOP if not already set
        if not wc.tool_phase_map:
            try:
                from importlib import resources

                from rankevolve.src.utils.string_utils.formatting.template_manager.sop_manager import (
                    SOPManager,
                )

                pkg = resources.files("rankevolve.src.resources.prompt_templates")
                for ext in (".jinja2", ".j2", ".md"):
                    candidate = pkg.joinpath(
                        "conversation", "main", "_variables", "workflow", f"sop{ext}"
                    )
                    if hasattr(candidate, "is_file") and candidate.is_file():
                        sop = SOPManager.load(candidate)
                        wc.tool_phase_map = sop.tool_to_phase_map
                        break
            except Exception:
                pass
        # Load workflow_description from prompt_renderer's template_dir if empty.
        # load_workflow_description() can fail with buck2 importlib.resources, but
        # the prompt_renderer's _template_dir is a known-working filesystem path.
        if not wc.workflow_description:
            ci = getattr(self, "conversation_inferencer", None)
            if ci:
                renderer = getattr(ci, "prompt_renderer", None)
                tpl_dir = getattr(renderer, "_template_dir", None) if renderer else None
                if tpl_dir:
                    desc_file = (
                        tpl_dir
                        / "conversation"
                        / "main"
                        / "_variables"
                        / "workflow_description"
                        / "default.jinja2"
                    )
                    if desc_file.is_file():
                        wc.workflow_description = desc_file.read_text(encoding="utf-8")
        # P5: pass sop_obj so to_status_text appends "Next pending: Phase X"
        # (and a REQUIRES USER CONFIRMATION instruction when applicable).
        # This is what makes gate phases like Phase 1b visible in the
        # status block — they have no tool to fire start_phase() so they
        # never become current_phase, but the LLM needs to know they're
        # the next gate to traverse.
        _sop_for_status = None
        ci = getattr(self, "conversation_inferencer", None)
        if ci is not None and hasattr(ci, "prior_context"):
            _sop_for_status = ci.prior_context.get("_sop")
        ctx["workflow_status"] = wc.to_status_text(sop_obj=_sop_for_status)
        ctx["workflow_description"] = wc.workflow_description
        # selected_strategy is the chosen strategy KEY (e.g.
        # "paradigm_shifting_innovation") — distinct from the
        # `strategy` alias defined in .variables.yaml which resolves
        # to the full employee.mindset dict. Overloading the same
        # name silently shadowed the alias and forced the template's
        # `employee.mindset[strategy]` lookup to fall through to a
        # `.values() | first` fallback — biasing the agent toward
        # the first declared strategy before the user picked one.
        ctx["selected_strategy"] = wc.strategy
        ctx["current_phase"] = wc.current_phase
        ctx["phase_status"] = wc.phase_status
        ctx["iteration_count"] = wc.iteration_count
        ctx["completed_phases"] = wc.completed_phases
        # State tracker fields (for SOP evaluation)
        # Use phase_outputs from WorkflowContext (always available),
        # falling back to state_tracker.state_outputs for backward compat.
        if wc.phase_outputs:
            ctx["phase_outputs"] = wc.phase_outputs
        elif wc.state_tracker is not None:
            ctx["phase_outputs"] = wc.state_tracker.state_outputs
        if wc.state_tracker is not None:
            ctx["goto_counts"] = wc.state_tracker.goto_counts

        # Task queue for prompt rendering
        if wc.task_queue:
            ctx["task_queue"] = wc.task_queue
            ctx["task_queue_summary"] = wc.get_queue_summary()

        return ctx

    active_task: asyncio.Task | None = attrib(default=None, init=False)
    active_conversation: asyncio.Task | None = attrib(default=None, init=False)
    processing_lock: asyncio.Lock = attrib(factory=asyncio.Lock, init=False)
    poll_task: asyncio.Task | None = attrib(default=None, init=False)
    # Per-task asyncio.Task handles for queued submission runs (and other
    # cancellable queue-managed work). Keyed by the queue task_id. The
    # legacy ``active_task`` attribute is overwritten across multiple paths
    # (chat / PTI / research-propose) and using it for SubmissionRunner
    # would risk a chat-loop cancel killing a running submission. This
    # registry is the ONLY handle for queued-task cancellation.
    running_task_handles: dict[str, asyncio.Task] = attrib(factory=dict, init=False)
