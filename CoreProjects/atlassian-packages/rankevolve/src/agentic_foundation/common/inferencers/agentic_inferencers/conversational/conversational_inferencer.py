# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.

"""ConversationalInferencer — self-contained agentic unit.

Owns the full agentic loop: render prompt → call LLM → parse tool calls →
execute tools → accumulate context → loop. The server layer becomes a thin
I/O adapter that sets prior_context, tool_executor, and syncs messages.

Key components (via composition/protocols):
  - base_inferencer: StreamingInferencerBase for actual LLM calls
  - tool_registry + tool_executor: tool definitions + execution dispatch
  - prompt_renderer: Jinja2 template rendering
  - prior_context: fixed static context (session_root_path, workflow state)
  - _dynamic_context: accumulated completed actions with compression
  - context_compressor: optional LLM-based context compression
  - context_budget: per-section character limits

Uses @attrs to match InferencerBase hierarchy.
"""

from __future__ import annotations

import logging
from types import MappingProxyType
from typing import Any, Optional

from attr import attrib, attrs
from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.common import (
    extract_response_text,
)
from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.conversational.context import (
    AgenticDynamicContext,
    AgenticResult,
    CompletedAction,
    ContextBudget,
)
from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.conversational.conversation_response_parser import (
    ConversationResponse,
    parse_conversation_response,
)
from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.conversational.conversation_tools import (
    ConversationTool,
    ConversationToolType,
)
from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.conversational.handler_protocol import (
    HandlerContext,
)
from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.conversational.handler_registry import (
    ConversationToolHandlerRegistry,
)
from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.conversational.handlers import (
    default_registry,
)
from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.conversational.protocols import (
    ToolExecutorCallable,
)
from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.conversational.tool_call_parser import (
    parse_llm_response,
    ParsedToolCall,
)
from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.conversational.tool_input_collector import (
    collect_human_inputs,
    has_human_input_sentinel,
)
from rankevolve.src.agentic_foundation.common.inferencers.inferencer_base import (
    InferencerBase,
)
from agent_foundation.ui.input_modes import (
    InputMode,
    InputModeConfig,
)
from agent_foundation.ui.interactive_base import (
    InteractionFlags,
    InteractiveBase,
)
from rankevolve.src.agentic_foundation.common.workflow_constants import (
    _WORKFLOW_DESC_PHASE_RE,
)
from rankevolve.src.resources.tools.formatters.markdown import ToolMarkdownFormatter
from rankevolve.src.resources.tools.models import ToolDefinition
from rankevolve.src.utils.string_utils.formatting.template_manager.sop_manager import (
    SOPManager,
)

logger = logging.getLogger(__name__)

# Maximum conversation loop iterations for standalone run_conversation()
_MAX_CONVERSATION_ITERATIONS = 20

# Protocol-level message markers used in the agentic loop conversation history.
# These strings are part of the LLM-facing protocol — changing them may affect
# prompt comprehension. Keep them short and bracketed for easy parsing.
_WIDGET_RESPONSE_PREFIX = "[Collected from conversation widget]"
_TOOL_RESULT_HEADER = "[Tool Result: {}]"  # .format(tool_name)
_TOOL_RESULTS_PREFIX = "[Tool execution results]"
_CONTINUE_AFTER_TOOLS = "Continue based on the tool execution results above."


@attrs(slots=False)
class ConversationalInferencer(InferencerBase):
    """Self-contained agentic inferencer with tool execution, context management,
    and prompt rendering.

    In server context, message_handlers calls run_agentic_loop() which owns the
    full render→infer→parse→execute→loop cycle.

    For standalone use, run_conversation() provides a simpler convenience loop
    (conversation tools only, no action tools).
    """

    # --- Core composition ---
    base_inferencer: InferencerBase = attrib(kw_only=True)
    interactive: Optional[InteractiveBase] = attrib(default=None, kw_only=True)
    # Legacy: used only by _ainfer()/run_conversation() (standalone path).
    # Server path uses _messages via run_agentic_loop(). The two are separate.
    conversation_history: list[dict[str, str]] = attrib(factory=list, init=False)

    # --- Agentic loop components ---
    tool_registry: dict[str, ToolDefinition] = attrib(factory=dict, kw_only=True)
    tool_executor: ToolExecutorCallable | None = attrib(default=None, kw_only=True)
    prompt_renderer: Any = attrib(default=None, kw_only=True)  # PromptRenderer
    context_compressor: Any = attrib(
        default=None, kw_only=True
    )  # ContextCompressorCallable
    prior_context: dict[str, Any] = attrib(factory=dict, kw_only=True)
    handler_registry: ConversationToolHandlerRegistry = attrib(
        factory=default_registry, kw_only=True
    )

    # --- Configuration ---
    compression_threshold: int = attrib(default=8000, kw_only=True)
    context_budget: ContextBudget = attrib(factory=ContextBudget, kw_only=True)
    max_iterations: int = attrib(default=5, kw_only=True)
    max_tool_result_chars: int = attrib(default=4000, kw_only=True)

    # --- Internal state (init=False) ---
    _dynamic_context: AgenticDynamicContext = attrib(
        factory=AgenticDynamicContext, init=False
    )
    _messages: list[dict[str, str]] = attrib(factory=list, init=False)
    _last_rendered_prompt: str = attrib(default="", init=False)
    _last_template_source: str = attrib(default="", init=False)
    _last_template_feed: dict[str, Any] = attrib(factory=dict, init=False)
    _last_template_config: dict[str, Any] = attrib(factory=dict, init=False)
    # Typed-mailbox replacements for the dynamic `_pending_*` attributes set/read
    # by widget handlers. Effects (OverrideNextActionToolArgs / SetTurnVariables)
    # write here from the dispatcher loop; the action-tool processing block
    # consumes + clears on the next iteration.
    _next_action_tool_overrides: dict[str, Any] | None = attrib(
        default=None, init=False
    )
    _next_turn_variables: dict[str, str] | None = attrib(default=None, init=False)

    def __attrs_post_init__(self) -> None:
        """Validate every declared ConversationToolType has a registered handler.

        Diff 5b validation: ensures dispatch never silently falls through to
        legacy branches in production. Diffs 1-5a built up the registry; this
        gate prevents future regressions where a handler is dropped.
        """
        registered = set(self.handler_registry.list_registered())
        all_types = set(ConversationToolType)
        missing = all_types - registered
        if missing:
            raise ValueError(
                f"ConversationalInferencer constructed with handler_registry "
                f"missing handlers for: {sorted(t.value for t in missing)}. "
                f"Registered: {sorted(t.value for t in registered)}."
            )

    # =========================================================================
    # Agentic Loop
    # =========================================================================

    async def run_agentic_loop(
        self,
        content: str,
        *,
        interactive: Optional[InteractiveBase] = None,
        session_id: str = "",
        turn_number: int = 0,
        on_new_turn: Optional[Any] = None,
        on_prompt_rendered: Optional[Any] = None,
    ) -> AgenticResult:
        """Main entry point — the agentic loop for free-chat conversations.

        When interactive + session_id are provided AND base_inferencer supports
        ainfer_streaming(), uses stream_token_batches() for token-by-token delivery.
        Otherwise falls back to non-streaming ainfer().

        NOTE (V2 TODO): Passing interactive + session_id creates a transport
        coupling between the framework-layer inferencer and the server-layer
        InteractiveBase. Consider introducing a StreamingCallback protocol
        to decouple them in a future iteration.
        """
        loop_actions: list[CompletedAction] = []
        # Resolve interactive: prefer per-call arg, fallback to self.interactive
        effective_interactive = interactive or self.interactive
        can_stream = (
            effective_interactive is not None
            and hasattr(effective_interactive, "stream_token_batches")
            and hasattr(self.base_inferencer, "ainfer_streaming")
        )
        last_raw_response = ""
        last_boundary_turn: int | None = None  # track last sent turn_boundary

        for iteration in range(self.max_iterations):
            # Create a new turn directory for each iteration (iteration > 0)
            # so each gets its own RenderedPrompt, TemplateFeed, ApiPayload.
            # This ensures View Prompt works for every iteration, and the
            # file tailer watches a fresh directory (enabling incremental
            # streaming instead of replaying all content at once).
            if iteration > 0 and on_new_turn:
                new_turn = await on_new_turn(turn_number, content)
                if new_turn is not None:
                    turn_number = new_turn

            # Signal turn boundary ONLY when the server turn number has
            # changed (i.e., _on_new_turn created a new turn directory).
            # This keeps frontend turn numbers in sync with server turn
            # directories so "View Prompt" maps correctly.
            if (
                iteration > 0
                and can_stream
                and effective_interactive is not None
                and turn_number != last_boundary_turn
            ):
                if hasattr(effective_interactive, "send_turn_boundary"):
                    await effective_interactive.send_turn_boundary(
                        session_id,
                        turn_number=turn_number,
                        cache_folder=getattr(self, "cache_folder", ""),
                    )
                    last_boundary_turn = turn_number

            # 1. Compress dynamic context if needed
            await self._compress_context_if_needed()

            # 2. Render prompt
            rendered = self._render_prompt(content)
            self._last_rendered_prompt = rendered

            # 3. Call LLM (streaming or non-streaming)
            # The rendered prompt is self-contained: it includes the system
            # role text, tools, conversation history, and the current user
            # message. We send it as a single user message with no separate
            # system_prompt, so what gets logged == what gets sent.
            try:
                if can_stream:
                    # Clear any prior system_prompt/messages on the base
                    # inferencer so the rendered prompt is the sole input.
                    self.base_inferencer.system_prompt = ""

                    async def token_gen():
                        async for chunk in self.base_inferencer.ainfer_streaming(
                            rendered
                        ):
                            yield chunk, {"turn_number": turn_number}

                    raw_response = await effective_interactive.stream_token_batches(
                        token_gen(),
                        session_id,
                        send_stream_end=False,
                        turn_number=turn_number,
                    )
                else:
                    raw_response = await self.base_inferencer.ainfer(rendered)
            except Exception as e:
                logger.error("Inferencer error in agentic loop: %s", e)
                raise
            last_raw_response = raw_response

            # Flush prompt + response artifacts to disk so "View Prompt"
            # works even while waiting for user input (confirmation, etc.).
            if on_prompt_rendered:
                try:
                    await on_prompt_rendered(self, raw_response)
                except Exception:
                    pass

            # Add assistant response to conversation history so subsequent
            # turns include it in the rendered prompt.
            self.add_message("assistant", raw_response)

            # 4. Check for conversation tools
            conv_response = parse_conversation_response(raw_response)

            if conv_response.has_conversation_tool and effective_interactive:
                collected = await self._handle_conversation_tools(
                    conv_response.conversation_tools,
                    conv_response.text,
                    interactive_override=effective_interactive,
                    action_tools=conv_response.action_tools,
                )
                if collected is None:
                    return AgenticResult(
                        text=conv_response.text,
                        raw_response=raw_response,
                        completed_actions=loop_actions,
                        iterations_used=iteration + 1,
                        has_conversation_tool=True,
                        conversation_tool=conv_response.conversation_tool,
                        last_rendered_prompt=self._last_rendered_prompt,
                        last_template_source=self._last_template_source,
                        last_template_feed=self._last_template_feed,
                        last_template_config=self._last_template_config,
                    )
                # Combine all collected inputs as the user message
                if isinstance(collected, dict):
                    parts = [f"{k}: {v}" for k, v in collected.items() if v]
                    user_input = f"{_WIDGET_RESPONSE_PREFIX}\n" + (
                        "\n".join(parts) if parts else str(collected)
                    )
                else:
                    user_input = f"{_WIDGET_RESPONSE_PREFIX}\n{collected}"
                self.add_message("user", user_input)
                content = user_input

                # Notify server of new turn boundary so it can start
                # a new turn directory and send stream_start/stream_end
                if on_new_turn:
                    new_turn = await on_new_turn(turn_number, user_input)
                    if new_turn is not None:
                        turn_number = new_turn

                # Execute any action tools from the same ToolsToInvoke block,
                # resolving __var__ placeholders with the collected user inputs.
                if conv_response.action_tools and self.tool_executor:
                    # Apply any param_overrides from confirmation widget.
                    # Typed mailbox replacing legacy _pending_param_overrides;
                    # written by OverrideNextActionToolArgs effect.
                    param_overrides = self._next_action_tool_overrides
                    if param_overrides:
                        self._next_action_tool_overrides = None

                    # Apply any generic variables from widget response.
                    # Typed mailbox replacing legacy _pending_variables;
                    # written by SetTurnVariables effect.
                    pending_vars = self._next_turn_variables
                    if pending_vars:
                        self._next_turn_variables = None
                        if self.prompt_renderer is not None:
                            for vk, vv in pending_vars.items():
                                self.prompt_renderer.set_variable(vk, vv)
                        # Append to the synthesized user turn so LLM sees them
                        var_lines = [f"[{k}]: {v}" for k, v in pending_vars.items()]
                        self.add_message("user", "\n".join(var_lines))

                    action_tool_results: list[str] = []
                    for at in conv_response.action_tools:
                        resolved_args = {}
                        for k, v in at.get("arguments", {}).items():
                            if (
                                isinstance(v, str)
                                and v.startswith("__")
                                and v.endswith("__")
                            ):
                                var_name = v[2:-2]
                                if (
                                    isinstance(collected, dict)
                                    and var_name in collected
                                ):
                                    resolved_args[k] = collected[var_name]
                                else:
                                    resolved_args[k] = v
                            else:
                                resolved_args[k] = v
                        # Merge user-configured param overrides from confirmation UI
                        if param_overrides:
                            resolved_args.update(param_overrides)
                        tc = ParsedToolCall(
                            name=at.get("name", ""),
                            arguments=resolved_args,
                            raw=str(at),
                        )
                        result_text = await self._execute_tool_call(tc)
                        summary = result_text[:200]
                        action = CompletedAction(tool=tc.name, summary=summary)
                        loop_actions.append(action)
                        self._dynamic_context.add_action(tc.name, summary)
                        action_tool_results.append(
                            f"{_TOOL_RESULT_HEADER.format(tc.name)}\n{result_text}"
                        )
                    # Add tool results to conversation so the LLM sees them
                    combined_results = "\n\n".join(action_tool_results)
                    self.add_message(
                        "user", f"{_TOOL_RESULTS_PREFIX}\n{combined_results}"
                    )

                # Update content so the next iteration's <CurrentTurn> shows
                # a continuation prompt instead of re-feeding the widget response.
                content = _CONTINUE_AFTER_TOOLS
                continue

            # 5a. Execute action tools from ToolsToInvoke (if any)
            if conv_response.action_tools and self.tool_executor:
                tool_results: list[str] = []
                for at in conv_response.action_tools:
                    tc = ParsedToolCall(
                        name=at.get("name", ""),
                        arguments=at.get("arguments", {}),
                        raw=str(at),
                    )
                    result_text = await self._execute_tool_call(tc)
                    summary = result_text[:200]
                    action = CompletedAction(tool=tc.name, summary=summary)
                    loop_actions.append(action)
                    self._dynamic_context.add_action(tc.name, summary)
                    tool_results.append(
                        f"{_TOOL_RESULT_HEADER.format(tc.name)}\n{result_text}"
                    )

                combined = "\n\n".join(tool_results)
                if len(combined) > self.max_tool_result_chars:
                    combined = (
                        combined[: self.max_tool_result_chars] + "\n... (truncated)"
                    )
                self.add_message("user", f"{_TOOL_RESULTS_PREFIX}\n{combined}")

                # P2: if ANY tool in this batch returned the
                # "launched asynchronously" sentinel, exit the agentic loop
                # immediately. This frees session.active_conversation
                # (becomes done()), so the next _poll_session cycle can
                # dispatch the auto-advance synthetic message that the
                # async tool's _exec_task will queue on completion. Without
                # this, the loop continues with _CONTINUE_AFTER_TOOLS as
                # the next prompt, racing (and winning against) the
                # auto-advance dispatcher — causing the LLM to see stale
                # state and skip gate phases like Phase 1b confirmation.
                # Replaces the previous coarse `await asyncio.sleep(2)`
                # defense which was an unreliable race rather than a real
                # fix.
                if "launched asynchronously" in combined:
                    logger.info(
                        "P2: async tool launched — exiting agentic loop so the "
                        "auto-advance synthetic message becomes the next prompt. "
                        "iteration=%s, completed_actions=%s",
                        iteration + 1, [a.tool for a in loop_actions],
                    )
                    return AgenticResult(
                        text=raw_response,
                        raw_response=raw_response,
                        completed_actions=loop_actions,
                        iterations_used=iteration + 1,
                        last_rendered_prompt=self._last_rendered_prompt,
                        last_template_source=self._last_template_source,
                        last_template_feed=self._last_template_feed,
                        last_template_config=self._last_template_config,
                    )

                content = _CONTINUE_AFTER_TOOLS
                continue

            # 5b. Parse for action tool calls (legacy XML format)
            parsed = parse_llm_response(raw_response, self._valid_tool_names)
            if not parsed.has_tool_calls:
                return AgenticResult(
                    text=parsed.text,
                    raw_response=raw_response,
                    completed_actions=loop_actions,
                    iterations_used=iteration + 1,
                    last_rendered_prompt=self._last_rendered_prompt,
                    last_template_source=self._last_template_source,
                    last_template_feed=self._last_template_feed,
                    last_template_config=self._last_template_config,
                )

            # 6. Execute tools
            tool_results: list[str] = []
            for tc in parsed.tool_calls:
                # Collect __human_input__ values if present
                if has_human_input_sentinel(tc.arguments) and effective_interactive:
                    tool_def = self.tool_registry.get(self._resolve_tool_name(tc.name))
                    tc.arguments = await collect_human_inputs(
                        tc.arguments, tool_def, effective_interactive
                    )
                result_text = await self._execute_tool_call(tc)
                summary = result_text[:200]
                action = CompletedAction(tool=tc.name, summary=summary)
                loop_actions.append(action)
                self._dynamic_context.add_action(tc.name, summary)
                tool_results.append(
                    f"{_TOOL_RESULT_HEADER.format(tc.name)}\n{result_text}"
                )

            combined = "\n\n".join(tool_results)
            if len(combined) > self.max_tool_result_chars:
                combined = combined[: self.max_tool_result_chars] + "\n... (truncated)"

            if parsed.text:
                self.add_message("assistant", parsed.text)
            self.add_message("user", f"{_TOOL_RESULTS_PREFIX}\n{combined}")
            content = _CONTINUE_AFTER_TOOLS

        # Exhausted max iterations — return last raw response
        return AgenticResult(
            text=last_raw_response,
            raw_response=last_raw_response,
            completed_actions=loop_actions,
            iterations_used=self.max_iterations,
            exhausted_max_iterations=True,
            last_rendered_prompt=self._last_rendered_prompt,
            last_template_source=self._last_template_source,
            last_template_feed=self._last_template_feed,
            last_template_config=self._last_template_config,
        )

    # =========================================================================

    def set_prior_context(self, ctx: dict[str, Any]) -> None:
        self.prior_context = dict(ctx)

    def update_prior_context(self, **kwargs: Any) -> None:
        self.prior_context.update(kwargs)

    def set_messages(self, messages: list) -> None:
        """Set conversation messages for prompt rendering.

        Messages are incorporated into the rendered prompt by _render_prompt().
        We do NOT delegate to base_inferencer.set_messages() because that would
        set _messages_override on PlugboardApiInferencer, causing
        ainfer_streaming() to ignore the rendered prompt.
        """
        self._messages = list(messages)

    def add_message(self, role: str, content: str) -> None:
        self._messages.append({"role": role, "content": content})

    def get_messages(self) -> list[dict[str, str]]:
        return list(self._messages)

    @property
    def dynamic_context(self) -> AgenticDynamicContext:
        return self._dynamic_context

    def reset_dynamic_context(self) -> None:
        self._dynamic_context = AgenticDynamicContext()

    # =========================================================================
    # Prompt Rendering
    # =========================================================================

    def _render_prompt(self, current_message: str) -> str:
        """Build template variables and render via prompt_renderer."""
        if not self.prompt_renderer:
            return self._render_fallback_prompt(current_message)

        # Format tools — separate action tools from conversation tools
        formatter = ToolMarkdownFormatter()
        tools_list = list(self.tool_registry.values())
        # Exclude user-only tools (agent_enabled=False) from LLM prompt
        agent_tools = [t for t in tools_list if getattr(t, "agent_enabled", True)]
        action_tools = [t for t in agent_tools if t.tool_type != "Conversation"]
        available_tools = formatter.format_all(action_tools)

        # Build conversation history (exclude last user msg to avoid duplication)
        messages = list(self._messages)
        if (
            messages
            and messages[-1].get("role") == "user"
            and messages[-1].get("content") == current_message
        ):
            messages = messages[:-1]

        # Build completed_actions for template, respecting dynamic_context_max budget
        all_actions = [
            {"tool": a.tool, "summary": a.summary}
            for a in self._dynamic_context.completed_actions
        ]
        actions_text = "\n".join(f"- {a['tool']}: {a['summary']}" for a in all_actions)
        if len(actions_text) > self.context_budget.dynamic_context_max:
            # Keep most recent actions that fit within budget
            truncated: list[dict[str, str]] = []
            total = 0
            for action in reversed(all_actions):
                line = f"- {action['tool']}: {action['summary']}"
                if total + len(line) + 1 > self.context_budget.dynamic_context_max:
                    break
                truncated.insert(0, action)
                total += len(line) + 1
            all_actions = truncated

        # Render conversation tools
        conv_tools = [t for t in agent_tools if t.tool_type == "Conversation"]
        conversation_tools_text = ""
        if conv_tools:
            conversation_tools_text = formatter._format_conversation_tools(conv_tools)

        # Template variable defaults from .variables.yaml (lowest priority)
        template_vars = getattr(self.prompt_renderer, "template_variables", {}) or {}

        # Evaluate SOP to generate nextstep guidance
        nextstep_guidance = ""
        sop_path = getattr(self.prompt_renderer, "find_sop_file", lambda: None)()
        if sop_path is not None:
            try:
                from rankevolve.src.utils.common_objects.workflow.stategraph import (
                    StateGraphTracker,
                )

                sop = SOPManager.load(sop_path)
                # Store SOP for confirmation gate checks in _execute_tool_call
                self.prior_context["_sop"] = sop

                # Extract and store tool-to-phase mapping from SOP
                if hasattr(sop, "tool_to_phase_map"):
                    tool_map = sop.tool_to_phase_map
                    if tool_map:
                        self.prior_context["tool_phase_map"] = tool_map

                # Validate SOP phase IDs match workflow_description (single source of truth)
                workflow_desc_phases = self.prior_context.get(
                    "workflow_description", ""
                )
                if workflow_desc_phases:
                    desc_phase_ids = {
                        m.group(1)
                        for m in _WORKFLOW_DESC_PHASE_RE.finditer(workflow_desc_phases)
                    }
                    sop_phase_ids = (
                        set(sop.phase_ids) if hasattr(sop, "phase_ids") else set()
                    )
                    if (
                        desc_phase_ids
                        and sop_phase_ids
                        and desc_phase_ids != sop_phase_ids
                    ):
                        logger.warning(
                            "SOP phase IDs %s do not match workflow_description phase IDs %s. "
                            "workflow_description is the single source of truth for phase definitions.",
                            sop_phase_ids,
                            desc_phase_ids,
                        )

                # Build tracker from prior_context state
                completed = [
                    r.phase if hasattr(r, "phase") else str(r)
                    for r in self.prior_context.get("completed_phases", [])
                ]
                cp = self.prior_context.get("current_phase")
                ps = self.prior_context.get("phase_status", "idle")
                tracker = StateGraphTracker(
                    graph=sop,
                    current_state=cp if ps in ("running", "error") else None,
                    state_status=ps,
                    completed_states=completed,
                    state_outputs=self.prior_context.get("phase_outputs", {}),
                    goto_counts=self.prior_context.get("goto_counts", {}),
                )

                # Auto-complete confirmation-gate phases (no tools, no outputs)
                # after user confirmed via a confirmation widget
                if self.prior_context.pop("_confirmation_gate_passed", False):
                    from rankevolve.src.utils.string_utils.formatting.template_manager.sop_manager import (
                        SOPPhase,
                    )

                    for node in tracker.get_available_next():
                        if not isinstance(node, SOPPhase):
                            continue
                        has_tools = any(
                            s.name.lower() in ("tools", "command")
                            for s in getattr(node, "subsections", [])
                        )
                        if (
                            not has_tools
                            and not node.outputs
                            and "requires confirmation"
                            in " ".join(getattr(node, "directives", []))
                        ):
                            if node.id not in tracker.completed_states:
                                tracker.completed_states.append(node.id)
                            self.prior_context.setdefault(
                                "_completed_gate_phases", []
                            ).append(node.id)
                            break

                nextstep_guidance = SOPManager.render_guidance(
                    tracker,
                    sop,
                    context=dict(self.prior_context),
                )
            except Exception as e:
                logger.warning("SOP evaluation failed: %s", e)

        feed = {
            **template_vars,
            "workflow_nextstep_guidance": nextstep_guidance,
            "action_tools": available_tools,
            **self.prior_context,
            "completed_actions": all_actions,
            "conversation_history": messages,
            "current_turn": {"role": "user", "content": current_message},
            "conversation_tools": conversation_tools_text,
        }

        # Resolve feed values that are themselves templates (e.g., SOP guidance
        # containing {{ session_root_path }}).  Uses the same Jinja2 Environment
        # as the main template so behaviour is identical.
        if hasattr(self.prompt_renderer, "render_string"):
            try:
                from rankevolve.src.utils.string_utils.formatting.common import (
                    resolve_templated_feed,
                )
                from rankevolve.src.utils.string_utils.formatting.jinja2_format import (
                    extract_variables as jinja2_extract_variables,
                )

                feed = resolve_templated_feed(
                    feed,
                    extract_variables=jinja2_extract_variables,
                    render_template=self.prompt_renderer.render_string,
                )
            except ValueError as e:
                logger.warning("Feed self-resolution failed: %s", e)

        self._last_template_feed = dict(feed)
        self._last_template_source = self.prompt_renderer.template_source
        self._last_template_config = (
            getattr(self.prompt_renderer, "template_config", {}) or {}
        )
        return self.prompt_renderer.render(feed)

    def _render_fallback_prompt(self, current_message: str) -> str:
        """Fallback prompt when prompt_renderer is None."""
        formatter = ToolMarkdownFormatter()
        tools_list = [
            t for t in self.tool_registry.values() if getattr(t, "agent_enabled", True)
        ]
        available_tools = formatter.format_all(tools_list)
        parts = [
            "You are RankEvolve, an AI experiment orchestrator for Meta's ranking models.",
            "",
            "## Available Tools",
            available_tools,
            "",
            'To invoke a tool: <tool_call>{"name": "...", "arguments": {...}}</tool_call>',
            "",
        ]
        if self._messages:
            parts.append("## Conversation")
            for msg in self._messages:
                if (
                    msg == self._messages[-1]
                    and msg.get("role") == "user"
                    and msg.get("content") == current_message
                ):
                    continue
                parts.append(f"<{msg['role']}>{msg['content']}</{msg['role']}>")
        parts.append(f"\n<user>{current_message}</user>")
        return "\n".join(parts)

    # =========================================================================
    # Tool Execution
    # =========================================================================

    async def _execute_tool_call(self, tool_call: Any) -> str:
        """Execute a tool call and apply context_updates from the result.

        Tools marked asynchronous=True in the tool registry are launched as
        background asyncio tasks (fire-and-forget) so the conversation turn
        completes immediately. The tool sends task_status notifications to
        the frontend independently.
        """
        import asyncio

        canonical = self._resolve_tool_name(tool_call.name)
        if self.tool_executor is None:
            return f"No tool executor configured for: {canonical}"

        # Check if this tool should run asynchronously (fire-and-forget)
        tool_def = self.tool_registry.get(canonical)
        is_async = tool_def and getattr(tool_def, "asynchronous", False)

        if is_async:
            executor = self.tool_executor

            # Update prior_context immediately so the next iteration's prompt
            # sees the correct SOP phase as "running", preventing the LLM from
            # retrying with stale "error" status.
            # BUT: don't overwrite "completed" back to "running" — if a
            # previous async tool already completed the phase (e.g., resumed
            # task finished instantly), the status should stay "completed".
            tool_map = self.prior_context.get("tool_phase_map", {})
            sop_phase = tool_map.get(canonical, canonical)
            if self.prior_context.get("phase_status") != "completed":
                self.prior_context["current_phase"] = sop_phase
                self.prior_context["phase_status"] = "running"
                # Build workflow_status with phase name from workflow_description
                phase_name = sop_phase
                try:
                    wd = self.prior_context.get("workflow_description", "")
                    if wd:
                        for m in _WORKFLOW_DESC_PHASE_RE.finditer(wd):
                            if m.group(1) == sop_phase:
                                phase_name = m.group(2).strip()
                                break
                except Exception:
                    pass
                active_summary = (
                    f"{canonical} — {str(tool_call.arguments.get('target', ''))[:80]}"
                )
                self.prior_context["workflow_status"] = (
                    f"Current phase: Phase {sop_phase} — {phase_name} (running)\n"
                    f"  Active task: {active_summary}"
                )
                self.prior_context["active_task_summary"] = active_summary

            async def _run_async() -> None:
                try:
                    result = await executor(canonical, tool_call.arguments)
                    if hasattr(result, "context_updates") and result.context_updates:
                        self.update_prior_context(**result.context_updates)
                except Exception as e:
                    logger.error("Async tool %s failed: %s", canonical, e)

            # Save strong reference to prevent GC of the background task.
            # asyncio._all_tasks is a WeakSet, so without a strong reference
            # the task could theoretically be collected during long I/O waits.
            self._active_async_task = asyncio.create_task(_run_async())
            return (
                f"Tool '{canonical}' launched asynchronously. "
                f"Check the task panel for progress and results."
            )

        try:
            result = await self.tool_executor(canonical, tool_call.arguments)
            # result is ToolExecutionResult — apply context_updates to prior_context
            if hasattr(result, "context_updates") and result.context_updates:
                self.update_prior_context(**result.context_updates)
            if hasattr(result, "result"):
                return result.result
            return str(result)
        except Exception as e:
            logger.error("Tool execution error for %s: %s", canonical, e)
            return f"Error executing {canonical}: {e}"

    def _resolve_tool_name(self, name: str) -> str:
        """Resolve a tool name or alias to the canonical tool name."""
        if name in self.tool_registry:
            return name
        for tool in self.tool_registry.values():
            if (
                name in getattr(tool, "aliases", [])
                or name.replace("-", "_") == tool.name
            ):
                return tool.name
        normalized = name.replace("-", "_")
        if normalized in self.tool_registry:
            return normalized
        return name

    @property
    def _valid_tool_names(self) -> set[str]:
        """Set of valid tool names including aliases."""
        names: set[str] = set()
        for tool in self.tool_registry.values():
            names.add(tool.name)
            for alias in getattr(tool, "aliases", []):
                names.add(alias)
        return names

    # =========================================================================
    # Context Compression
    # =========================================================================

    async def _compress_context_if_needed(self) -> None:
        if self.context_compressor is None:
            return
        if self._dynamic_context.total_chars() < self.compression_threshold:
            return
        compressed = await self.context_compressor(
            self._dynamic_context.to_text(),
            self.context_budget.dynamic_context_max,
        )
        self._dynamic_context.compress(compressed)

    # =========================================================================
    # Single-step inference (kept for backward compat / standalone use)
    # =========================================================================

    def _infer(
        self,
        inference_input: Any,
        inference_config: Any = None,
        **_inference_args,
    ) -> ConversationResponse:
        """Sync single-step inference with conversation tool parsing."""
        raw = self.base_inferencer.infer(
            inference_input, inference_config, **_inference_args
        )
        # Use ``extract_response_text`` (NOT raw ``str()``) so dict-returning
        # base inferencers (DevmateCli / ClaudeCodeCli) get unwrapped via
        # their ``output`` key instead of being stringified to a dict-repr —
        # which would escape real newlines to literal ``\n`` and break the
        # conversation-response parser downstream.
        raw_str = raw if isinstance(raw, str) else extract_response_text(raw)
        return parse_conversation_response(raw_str)

    async def _ainfer(
        self,
        inference_input: Any,
        inference_config: Any = None,
        **_inference_args,
    ) -> ConversationResponse:
        """Async single-step inference with conversation tool parsing."""
        if isinstance(inference_input, str):
            self.conversation_history.append(
                {"role": "user", "content": inference_input}
            )

        raw = await self.base_inferencer.ainfer(
            inference_input, inference_config, **_inference_args
        )
        # See ``_infer`` above for why we use ``extract_response_text`` instead
        # of raw ``str()``.
        raw_str = raw if isinstance(raw, str) else extract_response_text(raw)

        self.conversation_history.append({"role": "assistant", "content": raw_str})

        return parse_conversation_response(raw_str)

    async def run_conversation(
        self,
        initial_input: str,
        inference_config: Any = None,
        **inference_args,
    ) -> str:
        """Convenience loop for standalone use (outside server context).

        .. deprecated::
            Use run_agentic_loop() for new code. This method is kept for
            backward compatibility with standalone/CLI callers that only
            need conversation tool handling (no action tools).

        Calls _ainfer() in a loop, handling conversation tools internally.
        Uses self.conversation_history (not self._messages).
        """
        current_input = initial_input

        for iteration in range(_MAX_CONVERSATION_ITERATIONS):
            response = await self._ainfer(
                current_input, inference_config, **inference_args
            )

            if not response.has_conversation_tool:
                return response.text

            if self.interactive is None:
                logger.warning(
                    "Conversation tool requested but no interactive transport"
                )
                return response.text

            user_response = await self._handle_conversation_tool(
                response.conversation_tool, response.text
            )

            if user_response is None:
                return response.text

            current_input = user_response

        logger.warning(
            "Conversation loop exhausted after %d iterations",
            _MAX_CONVERSATION_ITERATIONS,
        )
        return response.text

    async def _handle_conversation_tool(
        self,
        tool: ConversationTool,
        assistant_text: str,
        interactive_override: Optional[InteractiveBase] = None,
    ) -> Optional[str]:
        """Handle a single conversation tool by collecting user input.

        Enriches the input_mode with variable content metadata (for UI display)
        and processes the response with choice_index→value mapping and
        variable override application.
        """
        active_interactive = interactive_override or self.interactive
        if active_interactive is None:
            return None

        input_mode = _build_input_mode(tool, self.handler_registry)

        # Enrich with variable content for UI display (editable text block)
        if self.prompt_renderer:
            try:
                var_name = tool.output_vars[0] if tool.output_vars else None
                vm = self.prompt_renderer.variable_manager

                # If output_vars is set, resolve directly
                if var_name:
                    content = vm.get_effective_value(var_name, skip_overrides=True)
                    if isinstance(content, dict):
                        input_mode.metadata["variable_content"] = {
                            k: str(v).strip() for k, v in content.items()
                        }
                        input_mode.metadata["variable_name"] = var_name
                # Otherwise, try to auto-detect by matching choice values
                # against known alias-target dicts in the variable manager
                elif tool.tool_type == "single_choice" and tool.choices:
                    choice_values = [
                        c.get("value", "").lower().replace(" ", "_").replace("-", "_")
                        for c in tool.choices
                        if c.get("value")
                    ]
                    for alias in getattr(vm, "_scoped_aliases", {}).values():
                        try:
                            candidate = vm.get_effective_value(
                                alias, skip_overrides=True
                            )
                            if isinstance(candidate, dict):
                                norm_keys = {
                                    k.lower().replace(" ", "_").replace("-", "_"): k
                                    for k in candidate
                                }
                                if choice_values and all(
                                    v in norm_keys for v in choice_values
                                ):
                                    input_mode.metadata["variable_content"] = {
                                        k: str(v).strip() for k, v in candidate.items()
                                    }
                                    input_mode.metadata["variable_name"] = alias
                                    break
                        except Exception:
                            continue
            except Exception:
                pass  # Non-critical — widget works without enrichment

        await active_interactive.asend_response(
            assistant_text,
            flag=InteractionFlags.PendingInput,
            input_mode=input_mode,
        )

        user_input = await active_interactive.aget_input()
        if user_input is None:
            return None

        # Extract the response payload
        if isinstance(user_input, dict):
            response = user_input.get(
                "user_input", user_input.get("content", user_input)
            )
        else:
            response = str(user_input)

        # Registry dispatch: __attrs_post_init__ guarantees every
        # ConversationToolType has a registered handler.
        handler = self.handler_registry.require(tool.tool_type)
        ctx = HandlerContext(
            prior_context=MappingProxyType(self.prior_context),
            prompt_renderer=self.prompt_renderer,
            tool_executor=self.tool_executor,
            interactive=active_interactive,
            action_tools=None,
            tool_registry=self.tool_registry,
            resolve_tool_name=self._resolve_tool_name,
        )
        response_dict: dict[str, Any] = (
            response if isinstance(response, dict) else {"content": response}
        )
        result = await handler.handle_response(tool, response_dict, ctx)
        for effect in result.effects:
            await effect.apply(self)
        return result.text

    async def _handle_conversation_tools(
        self,
        tools: list[ConversationTool],
        assistant_text: str,
        interactive_override: Optional[InteractiveBase] = None,
        action_tools: Optional[list[dict]] = None,
    ) -> Optional[dict[str, str]]:
        """Handle conversation tools by presenting a compound widget.

        For a single tool, delegates to _handle_conversation_tool().
        For multiple tools, bundles all into one compound pending_input
        so the frontend renders them as a tabbed multi-input widget.

        Returns a dict mapping output variable names to user values,
        or None if input collection fails.
        """
        if not tools:
            return None

        active_interactive = interactive_override or self.interactive
        if active_interactive is None:
            return None

        # ---------- Rich-group dispatch (Plan v3 — Phase 2b two-paths UX) ----------
        # If 2+ tools share the same non-empty `metadata["group_id"]`, route
        # through the rich-group path INSTEAD of the existing scalar-only
        # `compound` (MultiInputWidget) path. Rich-group preserves each
        # child's structured response (proposal_selection's selected_ids
        # list, confirmation's choice/multi_task_id) — no scalar coercion.
        # Detection is STRICT: ALL tools must share the SAME non-empty
        # group_id; mixed group_ids fall through to existing behavior.
        if len(tools) > 1:
            group_ids = [
                (t.metadata or {}).get("group_id") for t in tools
            ]
            shared_gid = group_ids[0]
            if (
                shared_gid
                and isinstance(shared_gid, str)
                and all(g == shared_gid for g in group_ids)
            ):
                logger.info(
                    "rich-group dispatch: %d tools share group_id=%r; "
                    "bypassing scalar-only constraint",
                    len(tools),
                    shared_gid,
                )
                return await self._handle_rich_group(
                    tools,
                    assistant_text,
                    interactive_override,
                    action_tools,
                    group_id=shared_gid,
                )
            # If only some tools have group_id, log a WARNING — likely an LLM
            # SOP mistake (forgot to set group_id on one) — but fall through
            # to existing per-tool dispatch so the user still sees something.
            if any(g for g in group_ids) and not all(
                g == shared_gid for g in group_ids
            ):
                logger.warning(
                    "rich-group: %d tools have inconsistent group_ids %r; "
                    "falling back to scalar-only compound path (LLM may "
                    "have forgotten to set group_id on a sibling)",
                    len(tools),
                    group_ids,
                )

        # Bundle scalar-only constraint: MultiInputWidget.js flattens each
        # per-tool response to a single string before bundling, so rich-response
        # tools (CONFIRMATION, PROPOSAL_SELECTION) cannot survive bundling.
        # Reject early with explicit error rather than silently losing payload.
        if len(tools) > 1:
            _bundle_scalar_allow = {
                ConversationToolType.CLARIFICATION,
                ConversationToolType.SINGLE_CHOICE,
                ConversationToolType.MULTIPLE_CHOICE,
                ConversationToolType.TOOL_ARGUMENT_FORM,
            }
            for _t in tools:
                if _t.tool_type not in _bundle_scalar_allow:
                    raise ValueError(
                        f"Rich-response tool {_t.tool_type!r} cannot be bundled "
                        f"with other tools (bundle wire format is scalar-only). "
                        f"Use the single-tool path instead."
                    )

        # Single tool: delegate to handler for enrichment, then to the
        # simple-tool path. The gate flag, tool_params, view metadata, etc.
        # are handled by the handler's enrich_before_send/handle_response.
        if len(tools) == 1:
            tool = tools[0]
            single_handler = self.handler_registry.require(tool.tool_type)
            single_ctx = HandlerContext(
                prior_context=MappingProxyType(self.prior_context),
                prompt_renderer=self.prompt_renderer,
                tool_executor=self.tool_executor,
                interactive=active_interactive,
                action_tools=action_tools,
                tool_registry=self.tool_registry,
                resolve_tool_name=self._resolve_tool_name,
            )
            await single_handler.enrich_before_send(tool, single_ctx)
            result = await self._handle_conversation_tool(
                tool, assistant_text, interactive_override
            )
            if result is None:
                return None
            var_name = tools[0].output_vars[0] if tools[0].output_vars else "input"
            return {var_name: result}

        # Multiple tools: send ALL as a compound widget in one pending_input
        tool_configs = []
        for tool in tools:
            mode = _build_input_mode(tool, self.handler_registry)

            # Enrich with variable content for UI display (editable text block)
            if self.prompt_renderer:
                try:
                    var_name = tool.output_vars[0] if tool.output_vars else None
                    vm = self.prompt_renderer.variable_manager

                    if var_name:
                        content = vm.get_effective_value(var_name, skip_overrides=True)
                        if isinstance(content, dict):
                            mode.metadata["variable_content"] = {
                                k: str(v).strip() for k, v in content.items()
                            }
                            mode.metadata["variable_name"] = var_name
                    elif tool.tool_type == "single_choice" and tool.choices:
                        choice_values = [
                            c.get("value", "")
                            .lower()
                            .replace(" ", "_")
                            .replace("-", "_")
                            for c in tool.choices
                            if c.get("value")
                        ]
                        for alias in getattr(vm, "_scoped_aliases", {}).values():
                            try:
                                candidate = vm.get_effective_value(
                                    alias, skip_overrides=True
                                )
                                if isinstance(candidate, dict):
                                    norm_keys = {
                                        k.lower().replace(" ", "_").replace("-", "_"): k
                                        for k in candidate
                                    }
                                    if choice_values and all(
                                        v in norm_keys for v in choice_values
                                    ):
                                        mode.metadata["variable_content"] = {
                                            k: str(v).strip()
                                            for k, v in candidate.items()
                                        }
                                        mode.metadata["variable_name"] = alias
                                        break
                            except Exception:
                                continue
                except Exception:
                    pass  # Non-critical — widget works without enrichment

            tool_configs.append(
                {
                    "tool_type": tool.tool_type,
                    "prompt": tool.prompt,
                    "input_mode": mode.to_dict(),
                    "output_var": tool.output_vars[0]
                    if tool.output_vars
                    else tool.tool_type,
                    "expected_input_type": tool.expected_input_type,
                    "prefix": tool.prefix,
                }
            )

        compound_mode = InputModeConfig(
            mode=InputMode.FREE_TEXT,
            prompt=assistant_text,
            metadata={
                "compound": True,
                "tools": tool_configs,
            },
        )
        await active_interactive.asend_response(
            assistant_text,
            flag=InteractionFlags.PendingInput,
            input_mode=compound_mode,
        )

        # Wait for ONE response with all collected values
        user_input = await active_interactive.aget_input()
        if user_input is None:
            return None

        # Extract values from compound response
        collected: dict[str, str] = {}
        if isinstance(user_input, dict):
            values = user_input.get("values", user_input.get("user_input", user_input))
            # Unwrap nested "values" dict from compound widget response
            # Frontend sends {user_input: {values: {...}}} which arrives as
            # {user_input: {values: {...}}, session_id: ...}
            if (
                isinstance(values, dict)
                and "values" in values
                and isinstance(values["values"], dict)
            ):
                values = values["values"]
            if isinstance(values, dict):
                # Extract variable_override if present
                variable_override = values.get("variable_override")
                for tool in tools:
                    var = tool.output_vars[0] if tool.output_vars else tool.tool_type
                    raw_value = values.get(var, "")
                    collected[var] = str(raw_value)

                    # Apply variable override or choice value to template system
                    if (
                        variable_override
                        and isinstance(variable_override, dict)
                        and var in variable_override
                        and self.prompt_renderer
                    ):
                        vm = self.prompt_renderer.variable_manager
                        vm.set(var, variable_override[var])
                    elif tool.output_vars and self.prompt_renderer and raw_value:
                        vm = self.prompt_renderer.variable_manager
                        vm.set(tool.output_vars[0], str(raw_value))
            else:
                # Fallback: single value
                collected["input"] = str(values)
        else:
            collected["input"] = str(user_input)

        return collected

    async def _handle_rich_group(
        self,
        tools: list[ConversationTool],
        assistant_text: str,
        interactive_override: Optional[InteractiveBase],
        action_tools: Optional[list[dict]],
        *,
        group_id: str,
    ) -> Optional[dict[str, str]]:
        """Rich-group dispatch (Plan v3): 2+ rich widgets sharing `group_id`.

        Bundles each child's enriched config into ONE `widget_type=grouped`
        envelope so React's `GroupedWidget` can render them stacked. On
        user submit, decodes `{submitted_child, payload}`, runs ONLY the
        submitted child's `handle_response` (siblings get card-emission
        via `_apply_group_resolution` server-side at the
        `_handle_pending_input_response` layer).

        Wire envelope shape:
            InputModeConfig.metadata = {
                "widget_type": "grouped",
                "group_id": <gid>,
                "tools": [
                    {
                        "child_id": "tool0",          # auto-assigned
                        "tool_type": <tt str>,
                        "prompt": <child prompt>,
                        "input_mode": <child input_mode dict, full enriched>,
                        "output_var": <child output var>,
                        "metadata": <child tool.metadata, includes
                                     on_group_resolve, on_yes_action,
                                     hide_no_button, etc.>,
                    },
                    ...
                ],
            }

        Inbound response shape (from React `GroupedWidget`):
            {"widget_id": <env_id>,
             "values": {
                 "submitted_child": "tool0",
                 "payload": <child_response_dict>,
             }}
        """
        active_interactive = interactive_override or self.interactive
        if active_interactive is None:
            return None

        # Build per-child enriched configs. Each child's enrich_before_send
        # runs normally so proposal_selection's `metadata.proposals` gets
        # loaded, confirmation's `view`/`view_label` get resolved, etc.
        single_ctx_factory = lambda: HandlerContext(
            prior_context=MappingProxyType(self.prior_context),
            prompt_renderer=self.prompt_renderer,
            tool_executor=self.tool_executor,
            interactive=active_interactive,
            action_tools=action_tools,
            tool_registry=self.tool_registry,
            resolve_tool_name=self._resolve_tool_name,
        )

        child_configs: list[dict[str, Any]] = []
        for idx, tool in enumerate(tools):
            ctx = single_ctx_factory()
            handler = self.handler_registry.require(tool.tool_type)
            await handler.enrich_before_send(tool, ctx)
            mode = handler.build_input_mode(tool, ctx)
            child_id = f"tool{idx}"
            child_configs.append(
                {
                    "child_id": child_id,
                    "tool_type": str(tool.tool_type.value)
                    if hasattr(tool.tool_type, "value")
                    else str(tool.tool_type),
                    "prompt": tool.prompt,
                    "input_mode": mode.to_dict(),
                    "output_var": tool.output_vars[0]
                    if tool.output_vars
                    else tool.tool_type,
                    "expected_input_type": tool.expected_input_type,
                    "prefix": tool.prefix,
                    "metadata": dict(tool.metadata or {}),
                }
            )

        grouped_mode = InputModeConfig(
            mode=InputMode.FREE_TEXT,
            prompt=assistant_text,
            metadata={
                "widget_type": "grouped",
                "group_id": group_id,
                "tools": child_configs,
            },
        )
        await active_interactive.asend_response(
            assistant_text,
            flag=InteractionFlags.PendingInput,
            input_mode=grouped_mode,
        )

        user_input = await active_interactive.aget_input()
        if user_input is None:
            return None

        # Decode {submitted_child, payload} from the response envelope.
        # The shape may be wrapped as {user_input: {values: {...}}} per the
        # existing compound-path conventions, so unwrap defensively.
        submitted_child_id: str = ""
        payload: dict[str, Any] = {}
        if isinstance(user_input, dict):
            values = user_input.get("values", user_input.get("user_input", user_input))
            if (
                isinstance(values, dict)
                and "values" in values
                and isinstance(values["values"], dict)
            ):
                values = values["values"]
            if isinstance(values, dict):
                submitted_child_id = str(values.get("submitted_child", ""))
                raw_payload = values.get("payload")
                # Mirror single-tool wrapping at _handle_conversation_tool:1063-1066 —
                # wrap non-dict payloads as {"content": <str>} so handlers see the
                # uniform dict shape. Handles ConfirmationWidget's string-when-no-overrides
                # path correctly for BOTH yes AND no choices (a hardcoded "force=yes"
                # normalizer would mis-route explicit no-clicks).
                payload = (
                    raw_payload
                    if isinstance(raw_payload, dict)
                    else {
                        "content": str(raw_payload) if raw_payload is not None else ""
                    }
                )

        if not submitted_child_id:
            logger.warning(
                "rich-group: response envelope missing `submitted_child` "
                "for group_id=%r; cannot route to handler",
                group_id,
            )
            return None

        # Find the submitted child + its handler.
        submitted_idx = next(
            (
                i
                for i, c in enumerate(child_configs)
                if c["child_id"] == submitted_child_id
            ),
            None,
        )
        if submitted_idx is None:
            logger.warning(
                "rich-group: submitted_child=%r not found among %s",
                submitted_child_id,
                [c["child_id"] for c in child_configs],
            )
            return None

        submitted_tool = tools[submitted_idx]
        handler = self.handler_registry.require(submitted_tool.tool_type)
        ctx = single_ctx_factory()
        result = await handler.handle_response(submitted_tool, payload, ctx)
        for effect in result.effects:
            await effect.apply(self)

        # Return output mapping for the submitted child only. Siblings'
        # cards are emitted server-side by `_apply_group_resolution` in
        # `_handle_pending_input_response`; their output_vars are NOT
        # populated here (the SOP that emitted the group should not
        # reference their output vars on the path-not-taken).
        var_name = (
            submitted_tool.output_vars[0]
            if submitted_tool.output_vars
            else submitted_tool.tool_type
        )
        logger.info(
            "rich-group resolved: group_id=%r, submitted_child=%s "
            "(child_id=%s), output_var=%s",
            group_id,
            submitted_tool.tool_type,
            submitted_child_id,
            var_name,
        )
        return {var_name: result.text}

    def reset_history(self) -> None:
        """Clear conversation history."""
        self.conversation_history.clear()

    # --- Streaming delegation to base_inferencer ---

    @property
    def system_prompt(self) -> str:
        return getattr(self.base_inferencer, "system_prompt", "")

    @system_prompt.setter
    def system_prompt(self, value: str) -> None:
        if hasattr(self.base_inferencer, "system_prompt"):
            self.base_inferencer.system_prompt = value

    @property
    def cache_folder(self) -> str | None:
        return getattr(self.base_inferencer, "cache_folder", None)

    @cache_folder.setter
    def cache_folder(self, value: str) -> None:
        if hasattr(self.base_inferencer, "cache_folder"):
            self.base_inferencer.cache_folder = value

    async def ainfer_streaming(
        self, inference_input: Any, inference_config: Any = None, **kwargs: Any
    ):
        """Delegate streaming to base inferencer."""
        if hasattr(self.base_inferencer, "ainfer_streaming"):
            async for chunk in self.base_inferencer.ainfer_streaming(
                inference_input, inference_config, **kwargs
            ):
                yield chunk
        else:
            result = await self.base_inferencer.ainfer(
                inference_input, inference_config, **kwargs
            )
            yield str(result) if not isinstance(result, str) else result


def _build_input_mode(
    tool: ConversationTool,
    registry: ConversationToolHandlerRegistry | None = None,
    ctx: HandlerContext | None = None,
) -> InputModeConfig:
    """Build an InputModeConfig from a ConversationTool.

    Pure registry dispatch — every declared `ConversationToolType` has a
    registered handler (validated by `ConversationalInferencer.__attrs_post_init__`).
    External callers that don't pass a registry get the framework default
    lazily.
    """
    if registry is None:
        from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.conversational.handlers import (
            default_registry as _default_registry,
        )

        registry = _default_registry()
    if ctx is None:
        ctx = HandlerContext(
            prior_context=MappingProxyType({}),
            prompt_renderer=None,
            tool_executor=None,
            interactive=None,
            action_tools=None,
            tool_registry=None,
            resolve_tool_name=None,
        )
    handler = registry.require(tool.tool_type)
    return handler.build_input_mode(tool, ctx)
