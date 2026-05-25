# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.

"""RankEvolve message handlers — routes messages to business logic."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from agent_foundation.ui.interactive_base import (
    InteractionFlags,
)
from rankevolve.src.server.command_router import CommandResult, route_command
from rankevolve.src.server.factories import create_llm_client, parse_task_options
from rankevolve.src.server.kn_command_router import KnResult, route_kn_command
from rankevolve.src.server.research_propose_bridge import parse_research_propose_options
from rankevolve.src.server.schema import MessageMetadata
from rankevolve.src.utils.service_utils.queue_service.queue_service_base import (
    QueueServiceBase,
)
from rankevolve.src.utils.service_utils.server.base_message_handlers import (
    AbstractMessageHandlers,
)

logger: logging.Logger = logging.getLogger(__name__)


def _schedule_async(session: Any, coro: Any) -> None:
    """Schedule an async coroutine as a background task on the session.

    Handles the case where the handler is called from a thread (via
    asyncio.to_thread in session_aware_server_base.py) where there is
    no running event loop. Falls back to asyncio.run() which creates
    a temporary event loop in the current thread and blocks until done.
    """
    try:
        session.active_task = asyncio.create_task(coro)
    except RuntimeError:
        # No running event loop — we're in a worker thread.
        # Run the coroutine synchronously in a new event loop.
        asyncio.run(coro)
        session.active_task = None


async def _asend_dict(interactive: Any, msg: dict, flag: Any) -> None:
    """Send a dict message directly to the response queue, bypassing iter_().

    asend_response() -> send_response() -> iter_() decomposes dicts into
    individual keys instead of sending the dict as one message. This calls
    _send_response() directly to preserve the dict structure.
    See _handle_config_query for the same pattern (sync variant).
    """
    await asyncio.to_thread(interactive._send_response, msg, flag)


from rankevolve.src.server.workflow_context import WorkflowPhaseRecord
from rankevolve.src.utils.service_utils.session_management.session_manager import (
    SessionManager,
)

from . import message_protocol as proto
from .session import RankEvolveSession

logger = logging.getLogger(__name__)


class RankEvolveMessageHandlers(AbstractMessageHandlers):
    """Routes incoming messages to RankEvolve business logic.

    All communication goes through QueueInteractive, gaining InteractionFlags,
    automatic logging, and InputMode support.
    """

    def __init__(
        self,
        session_manager: SessionManager,
        queue_service: QueueServiceBase,
    ) -> None:
        super().__init__(session_manager)
        self._queue_service = queue_service

    def _make_persist_callback(self) -> Callable:
        """Build the async persist_callback wired into SessionToolExecutor.
        Wraps the synchronous persist_session_state in asyncio.to_thread so
        invoking it from inside an event loop never blocks (Layer 1)."""

        async def _persist_cb(session: Any) -> None:
            await asyncio.to_thread(
                self._session_manager.persist_session_state, session
            )

        return _persist_cb

    def _get_handler_map(self) -> dict[str, Callable]:
        return {
            proto.CHAT_MESSAGE: self._handle_chat,
            proto.SLASH_COMMAND: self._handle_slash_command,
            proto.TASK_CANCEL: self._handle_task_cancel,
            proto.CONFIG_QUERY: self._handle_config_query,
            proto.PING: self._handle_ping,
            proto.SESSION_SYNC_REQUEST: self._handle_session_sync,
            proto.QUEUE_STATUS_REQUEST: self._handle_queue_status,
            proto.PENDING_INPUT_RESPONSE: self._handle_pending_input_response,
            proto.SETUP_SUBMISSION: self._handle_setup_submission,
            proto.RUN_SUBMISSION: self._handle_run_submission,
            proto.TASK_CANCEL_BY_ID: self._handle_task_cancel_by_id,
        }

    def _handle_chat(self, message: dict[str, Any]) -> None:
        """Handle a chat message — route through ConversationalInferencer agentic loop."""
        session_id = message.get("session_id", "")
        content = message.get("content", "")
        session = self._session_manager.get(session_id)

        if not isinstance(session, RankEvolveSession) or not session.interactive:
            logger.warning("No session for chat message: %s", session_id)
            return

        conversation_inferencer = getattr(session, "conversation_inferencer", None)
        tool_registry = getattr(session, "tool_registry", None)

        if conversation_inferencer is None or tool_registry is None:
            error_msg = (
                "ConversationalInferencer not initialized for session "
                f"{session_id}. Check server logs for initialization errors."
            )
            logger.error(error_msg)
            _schedule_async(
                session,
                _asend_dict(
                    session.interactive,
                    {
                        "type": proto.ERROR,
                        "message": error_msg,
                        "session_id": session_id,
                    },
                    flag=InteractionFlags.TurnCompleted,
                ),
            )
            return

        async def _run_conversation() -> None:
            is_auto_advance = message.get("auto_advance", False)
            session._is_auto_advance_turn = is_auto_advance
            try:
                if is_auto_advance:
                    session.conversation.add_auto_advance_message(content)
                else:
                    session.conversation.add_user_message(content)

                from rankevolve.src.server.tool_executor import SessionToolExecutor

                inferencer = conversation_inferencer

                # ASYNC DEFENSE: For auto-advance turns (after task completion),
                # refresh the session's workflow context BEFORE set_prior_context
                # reads it. The async tool executor called complete_phase() in a
                # background task, and set_prior_context triggers prompt rendering
                # that would capture stale "running" status if we update after.
                if is_auto_advance:
                    wc = session.workflow_context
                    ctx = session.session_context
                    logger.info(
                        "ASYNC DEFENSE: auto-advance turn. "
                        "wc.phase_status=%s, wc.current_phase=%s, "
                        "ctx[phase_status]=%s, "
                        "ctx[workflow_status]=%s",
                        wc.phase_status,
                        wc.current_phase,
                        ctx.get("phase_status"),
                        ctx.get("workflow_status", "")[:100],
                    )

                # Wire up inferencer for this turn — this reads session.session_context
                # which includes workflow_status, current_phase, phase_status etc.
                # For auto-advance turns, the values are already correct (refreshed above).
                inferencer.set_prior_context(
                    {
                        **session.session_context,
                        "system_prompt": session.conversation.system_prompt or "",
                    }
                )
                msg_count_before = len(session.conversation.get_api_messages())
                inferencer.set_messages(session.conversation.get_api_messages())
                inferencer.tool_executor = SessionToolExecutor(
                    session,
                    tasks_dir=session.session_tasks_dir,
                    queue_service=self._queue_service,
                    persist_callback=self._make_persist_callback(),
                )

                # Start turn for per-turn logging
                session.session_logger.start_turn()
                turn_number = session.session_logger.current_turn_number

                # Log user input (best-effort)
                try:
                    session.session_logger(
                        {"type": "UserInput", "item": content},
                        parts_key_path_root="item",
                    )
                except Exception:
                    pass

                # Set cache_folder for this turn's stream files
                turn_dir = (
                    session.session_logger.session_dir / f"turn_{turn_number:03d}"
                )
                turn_dir.mkdir(parents=True, exist_ok=True)
                inferencer.cache_folder = str(turn_dir)

                # Notify bridge to start file-based streaming
                await _asend_dict(
                    session.interactive,
                    {
                        "type": "stream_start",
                        "session_id": session_id,
                        "cache_folder": str(turn_dir),
                        "turn_number": turn_number,
                    },
                    flag=InteractionFlags.MessageOnly,
                )

                # Callback for turn boundaries within the agentic loop.
                # When the inferencer processes conversation tools and starts
                # a new LLM call, this creates a new turn for logging so
                # the 2nd LLM call's artifacts are in a separate turn directory.
                current_turn = [turn_number]  # mutable container for closure

                async def _on_new_turn(prev_turn: int, user_input: str) -> int:
                    # Log current turn's artifacts before starting new turn
                    try:
                        import json as _json

                        if inferencer._last_template_source:
                            session.session_logger(
                                {
                                    "type": "PromptTemplate",
                                    "item": inferencer._last_template_source,
                                },
                                parts_key_path_root="item",
                            )
                        if inferencer._last_template_feed:
                            session.session_logger(
                                {
                                    "type": "TemplateFeed",
                                    "item": _json.dumps(
                                        inferencer._last_template_feed,
                                        indent=2,
                                        ensure_ascii=False,
                                        default=str,
                                    ),
                                },
                                parts_key_path_root="item",
                            )
                        if inferencer._last_rendered_prompt:
                            session.session_logger(
                                {
                                    "type": "RenderedPrompt",
                                    "item": inferencer._last_rendered_prompt,
                                },
                                parts_key_path_root="item",
                            )
                        if inferencer._last_template_config:
                            session.session_logger(
                                {
                                    "type": "TemplateConfig",
                                    "item": _json.dumps(
                                        inferencer._last_template_config,
                                        ensure_ascii=False,
                                    ),
                                },
                                parts_key_path_root="item",
                            )
                        # Log API payload
                        api_messages = session.conversation.get_api_messages()
                        sys_prompt = session.conversation.system_prompt or ""
                        session.session_logger(
                            {
                                "type": "ApiPayload",
                                "item": _json.dumps(
                                    {
                                        "system_prompt": sys_prompt,
                                        "messages": api_messages,
                                    },
                                    indent=2,
                                    ensure_ascii=False,
                                    default=str,
                                ),
                            },
                            parts_key_path_root="item",
                        )
                        # Log inference response
                        session.session_logger(
                            {"type": "InferenceResponse", "item": ""},
                            parts_key_path_root="item",
                        )
                    except Exception:
                        pass

                    # Start new turn for logging
                    session.session_logger.start_turn()
                    new_turn = session.session_logger.current_turn_number
                    current_turn[0] = new_turn
                    new_turn_dir = (
                        session.session_logger.session_dir / f"turn_{new_turn:03d}"
                    )
                    new_turn_dir.mkdir(parents=True, exist_ok=True)
                    inferencer.cache_folder = str(new_turn_dir)

                    # Log synthesized user input
                    try:
                        session.session_logger(
                            {"type": "UserInput", "item": user_input},
                            parts_key_path_root="item",
                        )
                    except Exception:
                        pass

                    return new_turn

                async def _on_prompt_rendered(
                    inf: Any,
                    raw_response: str = "",
                ) -> None:
                    """Log prompt + response artifacts after each LLM call so
                    View Prompt works even while waiting for user input."""
                    import json as _json

                    logger.info(
                        "_on_prompt_rendered: flushing artifacts "
                        "(has_prompt=%s, has_feed=%s, has_response=%s)",
                        bool(getattr(inf, "_last_rendered_prompt", None)),
                        bool(getattr(inf, "_last_template_feed", None)),
                        bool(raw_response),
                    )

                    try:
                        if inf._last_template_source:
                            session.session_logger(
                                {
                                    "type": "PromptTemplate",
                                    "item": inf._last_template_source,
                                },
                                parts_key_path_root="item",
                            )
                        if inf._last_template_feed:
                            session.session_logger(
                                {
                                    "type": "TemplateFeed",
                                    "item": _json.dumps(
                                        inf._last_template_feed,
                                        indent=2,
                                        ensure_ascii=False,
                                        default=str,
                                    ),
                                },
                                parts_key_path_root="item",
                            )
                        if inf._last_rendered_prompt:
                            session.session_logger(
                                {
                                    "type": "RenderedPrompt",
                                    "item": inf._last_rendered_prompt,
                                },
                                parts_key_path_root="item",
                            )
                        if inf._last_template_config:
                            session.session_logger(
                                {
                                    "type": "TemplateConfig",
                                    "item": _json.dumps(
                                        inf._last_template_config,
                                        ensure_ascii=False,
                                    ),
                                },
                                parts_key_path_root="item",
                            )
                        # Log API payload and response
                        api_messages = session.conversation.get_api_messages()
                        sys_prompt = session.conversation.system_prompt or ""
                        session.session_logger(
                            {
                                "type": "ApiPayload",
                                "item": _json.dumps(
                                    {
                                        "system_prompt": sys_prompt,
                                        "messages": api_messages,
                                    },
                                    indent=2,
                                    ensure_ascii=False,
                                    default=str,
                                ),
                            },
                            parts_key_path_root="item",
                        )
                        if raw_response:
                            session.session_logger(
                                {"type": "InferenceResponse", "item": raw_response},
                                parts_key_path_root="item",
                            )
                    except Exception:
                        pass

                # Run the agentic loop
                result = await inferencer.run_agentic_loop(
                    content,
                    interactive=session.interactive,
                    session_id=session_id,
                    turn_number=turn_number,
                    on_new_turn=_on_new_turn,
                    on_prompt_rendered=_on_prompt_rendered,
                )

                final_text = result.text

                # NOTE: Batch enqueue for selected proposals is now done INSIDE
                # _handle_conversation_tool() in conversational_inferencer.py,
                # BEFORE the LLM gets another agentic loop iteration. This prevents
                # the LLM from invoking /task directly and combining hypotheses.

                # Send stream_end
                await asyncio.to_thread(
                    session.interactive.response_queue.put,
                    session.interactive.response_queue_id,
                    {
                        "type": "stream_end",
                        "session_id": session_id,
                        "final_content": final_text or "",
                        "flag": InteractionFlags.TurnCompleted,
                        "turn_number": current_turn[0],
                    },
                )

                # Sync new messages back to session.conversation
                # Exclude the last assistant message — it will be added
                # explicitly below from result.text (which may differ from
                # raw_response, e.g. with tool markup stripped).
                new_messages = inferencer.get_messages()[msg_count_before:]
                if new_messages and new_messages[-1]["role"] == "assistant":
                    new_messages = new_messages[:-1]
                for msg in new_messages:
                    if msg["role"] == "user":
                        # Route protocol echoes through tagged writers so
                        # the frontend can hide them via metadata, not by
                        # content-prefix sniffing on restore. Constants
                        # come from conversational_inferencer's protocol
                        # markers ([Collected from conversation widget],
                        # [Tool execution results]).
                        content_str = msg["content"] or ""
                        if content_str.startswith(
                            "[Collected from conversation widget]"
                        ):
                            session.conversation.add_widget_response(content_str)
                        elif content_str.startswith("[Tool execution results]"):
                            # add_tool_result_message expects (tool_name, result);
                            # this is a multi-tool combined echo, so reuse the
                            # widget tagger which sets is_auto_advance=True.
                            session.conversation.add_widget_response(content_str)
                        else:
                            session.conversation.add_user_message(content_str)
                    elif msg["role"] == "assistant":
                        session.conversation.add_assistant_message(
                            msg["content"],
                            metadata=MessageMetadata(
                                model=session.app_config.model,
                            ),
                        )

                # Add final assistant response
                if final_text:
                    session.conversation.add_assistant_message(
                        final_text,
                        metadata=MessageMetadata(
                            model=session.app_config.model,
                        ),
                    )

                # Log turn artifacts (best-effort)
                try:
                    import json as _json

                    if result.last_template_source:
                        session.session_logger(
                            {
                                "type": "PromptTemplate",
                                "item": result.last_template_source,
                            },
                            parts_key_path_root="item",
                        )
                    if result.last_template_feed:
                        session.session_logger(
                            {
                                "type": "TemplateFeed",
                                "item": _json.dumps(
                                    result.last_template_feed,
                                    indent=2,
                                    ensure_ascii=False,
                                    default=str,
                                ),
                            },
                            parts_key_path_root="item",
                        )
                    if result.last_rendered_prompt:
                        session.session_logger(
                            {
                                "type": "RenderedPrompt",
                                "item": result.last_rendered_prompt,
                            },
                            parts_key_path_root="item",
                        )
                    if result.last_template_config:
                        session.session_logger(
                            {
                                "type": "TemplateConfig",
                                "item": _json.dumps(
                                    result.last_template_config,
                                    ensure_ascii=False,
                                ),
                            },
                            parts_key_path_root="item",
                        )
                    # Log the actual API payload sent to the LLM
                    api_messages = session.conversation.get_api_messages()
                    sys_prompt = session.conversation.system_prompt or ""
                    session.session_logger(
                        {
                            "type": "ApiPayload",
                            "item": _json.dumps(
                                {
                                    "system_prompt": sys_prompt,
                                    "messages": api_messages,
                                },
                                indent=2,
                                ensure_ascii=False,
                                default=str,
                            ),
                        },
                        parts_key_path_root="item",
                    )
                    if final_text:
                        session.session_logger(
                            {
                                "type": "InferenceResponse",
                                "item": final_text,
                            },
                            parts_key_path_root="item",
                        )
                except Exception:
                    pass

                # Sync confirmation-gate phase completions back to WorkflowContext
                for gate_phase in inferencer.prior_context.get(
                    "_completed_gate_phases", []
                ):
                    wc = session.workflow_context
                    wc.complete_phase(gate_phase, "User confirmed")

                await asyncio.to_thread(
                    self._session_manager.persist_session_state, session
                )

            except Exception as e:
                logger.error(
                    "Agentic loop error for session %s: %s",
                    session_id,
                    e,
                )
                await _asend_dict(
                    session.interactive,
                    {
                        "type": proto.ERROR,
                        "message": str(e),
                        "session_id": session_id,
                    },
                    flag=InteractionFlags.TurnCompleted,
                )
                await asyncio.to_thread(
                    self._session_manager.persist_session_state, session
                )
            finally:
                session._is_auto_advance_turn = False

        _schedule_async(session, _run_conversation())
        # Track as active conversation for the concurrency guard in _poll_session
        session.active_conversation = session.active_task

    def _handle_slash_command(self, message: dict[str, Any]) -> None:
        """Handle a slash command — route and return structured result."""
        session_id = message.get("session_id", "")
        content = message.get("content", "")
        session = self._session_manager.get(session_id)

        if not isinstance(session, RankEvolveSession) or not session.interactive:
            return

        result = route_command(content, session.conversation, session.app_config)

        if result.action == "task":
            self._handle_task(message, session, result)
            return

        if result.action == "kn":
            self._handle_kn_command(message, session, result)
            return

        if result.action == "research-propose":
            self._handle_research_propose(message, session, result)
            return

        if result.action == "experiment":
            self._handle_experiment(message, session, result)
            return

        if result.action == "experiment_combos":
            # /experiment-hypothesis-combos — Stage 2 of split orchestrator,
            # AND the slash route the WebUI's "Refresh Learnings" button
            # uses (with --aggregate-only). Without this arm the slash
            # falls through to the generic _send_result and the underlying
            # _exec_experiment_combos / _exec_aggregator_only_refresh
            # pipeline never runs.
            self._handle_experiment_combos(message, session, result)
            return

        if result.action == "implement_hypothesis":
            # /implement-hypothesis — Stage 1 of split orchestrator. Same
            # missing-arm bug shape as experiment_combos; without this the
            # slash invocation silently no-ops.
            self._handle_implement_hypothesis(message, session, result)
            return

        if result.action == "root_set":
            self._handle_root_set(message, session, result)
            return

        if result.action == "root_show":
            self._handle_root_show(message, session)
            return

        if result.action == "view":
            self._handle_view(message, session, result)
            return

        async def _send_result() -> None:
            response = {
                "type": proto.COMMAND_RESPONSE,
                "session_id": session_id,
                "action": result.action,
                "message": result.message,
                "data": result.data,
            }
            if result.config_changed:
                response["config_changed"] = True
                response["updated_config"] = result.updated_config
                # Record config-changing commands in conversation so they persist
                session.conversation.add_user_message(content)
                session.conversation.add_assistant_message(result.message)
            await _asend_dict(
                session.interactive,
                response,
                flag=InteractionFlags.TurnCompleted,
            )
            # Persist after config-changing commands
            if result.config_changed:
                await asyncio.to_thread(
                    self._session_manager.persist_session_state, session
                )

        asyncio.create_task(_send_result())

    def _handle_task(
        self,
        message: dict[str, Any],
        session: RankEvolveSession,
        cmd_result: CommandResult,
    ) -> None:
        """Handle a /task command — run DualInferencerBridge."""
        session_id = message.get("session_id", "")
        task_args = cmd_result.data.get("args", "")

        task_id = f"task-{uuid.uuid4().hex[:8]}"
        session.info.active_task_id = task_id

        # Parse options early to check for --mock
        (
            request,
            inline_model,
            inline_claude_only,
            inline_task_mode,
            inline_pti_flags,
        ) = parse_task_options(task_args)

        if inline_pti_flags.get("mock"):
            self._handle_mock_task(session, session_id, task_id, request)
            return

        # Hub routing: if an active experiment hub exists and --no-queue is not set,
        # route this /task to the hub's queue instead of creating a standalone task.
        # This check MUST come before start_phase() to avoid dangling phase state.
        no_queue = inline_pti_flags.get("no_queue", False)
        if not no_queue:
            wc = session.workflow_context
            if wc.active_multi_task_id:

                async def _route_to_hub() -> None:
                    try:
                        from rankevolve.src.server.tool_executor import (
                            SessionToolExecutor,
                        )

                        tool_executor = SessionToolExecutor(
                            session,
                            tasks_dir=session.session_tasks_dir,
                            persist_callback=self._make_persist_callback(),
                        )
                        await tool_executor.add_to_experiment_hub(
                            multi_task_id=wc.active_multi_task_id,
                            request=request,
                            title=request[:40],
                        )
                        await _asend_dict(
                            session.interactive,
                            {
                                "type": proto.COMMAND_RESPONSE,
                                "session_id": session_id,
                                "action": "task",
                                "message": f"Task added to Experiment Hub queue.",
                            },
                            flag=InteractionFlags.TurnCompleted,
                        )
                    except Exception as e:
                        logger.error("Hub routing failed: %s", e, exc_info=True)
                        await _asend_dict(
                            session.interactive,
                            {
                                "type": proto.COMMAND_RESPONSE,
                                "session_id": session_id,
                                "action": "error",
                                "message": f"Failed to add task to hub: {e}",
                            },
                            flag=InteractionFlags.TurnCompleted,
                        )

                asyncio.create_task(_route_to_hub())
                return

        async def _run_task() -> None:
            try:
                from pathlib import Path

                from rankevolve.src.server.dual_inferencer_bridge import (
                    DualInferencerBridge,
                )
                from rankevolve.src.server.task_types import TaskMode

                root = Path(
                    session.info.session_root_path
                    if hasattr(session.info, "session_root_path")
                    and session.info.session_root_path
                    else "."
                )
                # Determine SOP phase from tool_phase_map (extracted from SOP)
                tool_map = session.workflow_context.tool_phase_map
                template_version = inline_pti_flags.get("template_version", "")
                sop_phase = tool_map.get(template_version, tool_map.get("task", "3"))
                # Update workflow_context BEFORE bridge construction (snapshot timing)
                session.workflow_context.start_phase(sop_phase, request[:80])

                bridge = DualInferencerBridge(
                    root_folder=root,
                    claude_model=inline_model or session.app_config.model,
                    use_claude_only=inline_claude_only,
                    output_dir=session.session_tasks_dir,
                    knowledge_bridge=getattr(session, "knowledge_bridge", None),
                    session_context=session.session_context,
                    **(inline_pti_flags or {}),
                )
                session.workflow_context.active_workspace = str(bridge.workspace)

                # Persist a chronological task_ref BEFORE the WS emit so a
                # crash in the persist→emit window doesn't cost positional
                # fidelity on resume. The chip's tool_name uses
                # template_version (e.g. "understand_codebase") so frontend
                # correlation distinguishes delegated tools from plain /task.
                # Best-effort chip-write — failure here MUST NOT abort
                # the task launch. Chip placement is auxiliary UI metadata.
                if session.conversation:
                    try:
                        session.conversation.add_task_ref(
                            task_id=task_id,
                            label=(request or "Task")[:60],
                            tool_name=template_version or "task",
                        )
                        await asyncio.to_thread(
                            self._session_manager.persist_session_state, session
                        )
                    except Exception as chip_err:
                        logger.warning(
                            "add_task_ref failed for task_id=%s — task "
                            "will still launch, chip placement may be "
                            "missing on resume: %s",
                            task_id,
                            chip_err,
                        )

                await _asend_dict(
                    session.interactive,
                    {
                        "type": proto.TASK_STATUS,
                        "session_id": session_id,
                        "task_id": task_id,
                        "status": "starting",
                        "request": request[:80],
                        "workspace": str(bridge.workspace),
                    },
                    flag=InteractionFlags.MessageOnly,
                )

                task_mode = inline_task_mode or TaskMode.FULL_WORKFLOW
                await bridge.run(request, task_mode=task_mode)

                session.workflow_context.complete_phase(
                    sop_phase,
                    summary=request[:80],
                    workspace_path=str(bridge.workspace),
                    task_id=task_id,
                )
                await asyncio.to_thread(
                    self._session_manager.persist_session_state, session
                )

                await _asend_dict(
                    session.interactive,
                    {
                        "type": proto.TASK_STATUS,
                        "session_id": session_id,
                        "task_id": task_id,
                        "status": "completed",
                        "workspace": str(bridge.workspace),
                    },
                    flag=InteractionFlags.TurnCompleted,
                )
                session.info.active_task_id = None

                # Auto-advance: inject synthetic message to advance workflow
                if not getattr(session, "_is_auto_advance_turn", False):
                    auto_msg = (
                        f"[System notification: Phase {sop_phase} task completed successfully. "
                        f"Workspace: {bridge.workspace}. "
                        f"Please review the results and guide the user to the next workflow phase.]"
                    )
                    await asyncio.to_thread(
                        self._queue_service.put,
                        f"user_input_{session_id}",
                        {
                            "type": "chat_message",
                            "content": auto_msg,
                            "session_id": session_id,
                            "auto_advance": True,
                        },
                    )

            except Exception as e:
                logger.error("Task error for session %s: %s", session_id, e)
                session.workflow_context.fail_phase(
                    sop_phase,
                    error=str(e)[:80],
                    task_id=task_id,
                )
                await asyncio.to_thread(
                    self._session_manager.persist_session_state, session
                )
                await _asend_dict(
                    session.interactive,
                    {
                        "type": proto.ERROR,
                        "message": f"Task error: {e}",
                        "session_id": session_id,
                        "task_id": task_id,
                    },
                    flag=InteractionFlags.TurnCompleted,
                )
                session.info.active_task_id = None

        session.active_task = asyncio.create_task(_run_task())

    def _handle_mock_task(
        self,
        session: RankEvolveSession,
        session_id: str,
        task_id: str,
        request: str,
    ) -> None:
        """Handle /task --mock — run a simulated task for UI testing."""

        async def _run_mock() -> None:
            try:
                from rankevolve.src.server.rankevolve_service.mock_task import (
                    run_mock_task,
                )

                await run_mock_task(
                    session=session,
                    session_id=session_id,
                    task_id=task_id,
                    request=request,
                    tasks_dir=session.session_tasks_dir,
                )
            except BaseException as e:
                if isinstance(e, asyncio.CancelledError):
                    logger.info("Mock task cancelled for session %s", session_id)
                else:
                    logger.error("Mock task error for session %s: %s", session_id, e)
                session.workflow_context.phase_status = "error"
                session.workflow_context.active_task_summary = ""
                session.info.active_task_id = None
                if not isinstance(e, asyncio.CancelledError):
                    await _asend_dict(
                        session.interactive,
                        {
                            "type": proto.ERROR,
                            "message": f"Mock task error: {e}",
                            "session_id": session_id,
                            "task_id": task_id,
                        },
                        flag=InteractionFlags.TurnCompleted,
                    )

        _schedule_async(session, _run_mock())

    def _handle_kn_command(
        self,
        message: dict[str, Any],
        session: RankEvolveSession,
        cmd_result: CommandResult,
    ) -> None:
        """Handle a /kn command."""
        session_id = message.get("session_id", "")
        kn_args = cmd_result.data.get("args", "")

        async def _run_kn() -> None:
            result = route_kn_command(
                kn_args, session.knowledge_bridge, session.conversation
            )
            await _asend_dict(
                session.interactive,
                {
                    "type": proto.COMMAND_RESPONSE,
                    "session_id": session_id,
                    "action": "kn",
                    "message": result.message,
                    "success": result.success,
                    "data": result.data,
                },
                flag=InteractionFlags.TurnCompleted,
            )

        asyncio.create_task(_run_kn())

    def _handle_root_set(
        self,
        message: dict[str, Any],
        session: RankEvolveSession,
        cmd_result: CommandResult,
    ) -> None:
        """Handle /set-session-root <path> — validate and persist to session."""
        session_id = message.get("session_id", "")
        raw_path = cmd_result.data.get("path", "")

        async def _set_root() -> None:
            from pathlib import Path

            path = Path(raw_path).expanduser().resolve()
            if not path.is_dir():
                await _asend_dict(
                    session.interactive,
                    {
                        "type": proto.COMMAND_RESPONSE,
                        "session_id": session_id,
                        "action": "root_set",
                        "message": f"Not a valid directory: {path}",
                        "success": False,
                    },
                    flag=InteractionFlags.TurnCompleted,
                )
                return

            session.info.session_root_path = str(path)
            # Record the command in conversation history so it persists across restarts
            session.conversation.add_user_message(f"/set-session-root {raw_path}")
            session.conversation.add_assistant_message(f"Session root set to: {path}")
            await _asend_dict(
                session.interactive,
                {
                    "type": proto.COMMAND_RESPONSE,
                    "session_id": session_id,
                    "action": "root_set",
                    "message": f"Session root set to: {path}",
                    "success": True,
                    "data": {"path": str(path)},
                    "config_changed": True,
                    "updated_config": {"target_path": str(path)},
                },
                flag=InteractionFlags.TurnCompleted,
            )
            await asyncio.to_thread(
                self._session_manager.persist_session_state,
                session,
                change_types=["config", "content"],
            )

        asyncio.create_task(_set_root())

    def _handle_root_show(
        self,
        message: dict[str, Any],
        session: RankEvolveSession,
    ) -> None:
        """Handle /set-session-root with no args — show current session root."""
        session_id = message.get("session_id", "")

        async def _show_root() -> None:
            current = (
                session.info.session_root_path
                if hasattr(session.info, "session_root_path")
                and session.info.session_root_path
                else "(not set)"
            )
            await _asend_dict(
                session.interactive,
                {
                    "type": proto.COMMAND_RESPONSE,
                    "session_id": session_id,
                    "action": "root_show",
                    "message": f"Session root: {current}",
                    "data": {"path": current},
                },
                flag=InteractionFlags.TurnCompleted,
            )

        asyncio.create_task(_show_root())

    def _handle_view(
        self,
        message: dict[str, Any],
        session: RankEvolveSession,
        cmd_result: CommandResult,
    ) -> None:
        """Handle /view command — resolve file path and send to frontend."""
        session_id = message.get("session_id", "")
        target = cmd_result.data.get("target", "docs")

        async def _resolve_view() -> None:
            view_url = None
            msg = ""

            if target == "docs":
                # Resolve docs path from workflow target
                target_path = session.session_context.get("workflow_target_path", "")
                if target_path:
                    from pathlib import Path

                    target_dir = Path(target_path)
                    if target_dir.is_file():
                        target_dir = target_dir.parent
                    docs_index = target_dir / "docs" / "_build" / "html" / "index.html"
                    if docs_index.exists():
                        view_url = str(docs_index)
                        msg = f"Opening documentation: {docs_index}"
                    else:
                        msg = (
                            f"No documentation found at {docs_index}. "
                            "Run /understand-codebase first."
                        )
                else:
                    msg = "No workflow target set. Set a target path first."
            else:
                # Treat as a direct file path
                view_url = target
                msg = f"Opening: {target}"

            await _asend_dict(
                session.interactive,
                {
                    "type": proto.COMMAND_RESPONSE,
                    "session_id": session_id,
                    "action": "view",
                    "message": msg,
                    "data": {"view_url": view_url},
                },
                flag=InteractionFlags.TurnCompleted,
            )

        asyncio.create_task(_resolve_view())

    def _handle_experiment(
        self,
        message: dict[str, Any],
        session: "RankEvolveSession",
        result: "CommandResult",
    ) -> None:
        """Handle /experiment command — create implementation hub with batch-grouped tasks.

        Reads the unified proposal plan, groups selected hypotheses by batch,
        creates a multi-task notification, and enqueues batch tasks.
        """
        import uuid as _uuid

        session_id = message.get("session_id", "")
        data = result.data or {}
        plan_path = data.get("plan_path", "")
        selected_ids = data.get("selected_ids", [])
        implement_default = data.get("implement_default", False)

        # Get proposals data from workflow context (from previous research phase)
        wc = session.workflow_context
        proposals_data = wc.phase_outputs.get("research_proposals_data")

        # If no proposals data in context, try to load from the plan path
        if not proposals_data and plan_path:
            try:
                from pathlib import Path

                from agent_foundation.ui.proposal_parser import (
                    parse_proposals,
                )

                parsed = parse_proposals(str(Path(plan_path).parent))
                if parsed:
                    proposals_data = parsed.to_dict()
            except Exception as e:
                logger.warning("Failed to parse proposals from %s: %s", plan_path, e)

        if not proposals_data:

            async def _send_error() -> None:
                await _asend_dict(
                    session.interactive,
                    {
                        "type": proto.COMMAND_RESPONSE,
                        "session_id": session_id,
                        "action": "error",
                        "message": "No proposals data available. Run /research-propose first.",
                    },
                    flag=InteractionFlags.TurnCompleted,
                )

            asyncio.create_task(_send_error())
            return

        # Parse proposals_data if it's a JSON string
        if isinstance(proposals_data, str):
            import json

            try:
                proposals_data = json.loads(proposals_data)
            except Exception:
                pass

        # Build selected_details from proposals_data
        all_proposals = []
        for phase in (proposals_data if isinstance(proposals_data, dict) else {}).get(
            "phases", []
        ):
            all_proposals.extend(phase.get("proposals", []))

        if implement_default and not selected_ids:
            # Select top proposals (default behavior)
            selected_ids = [p.get("id", "") for p in all_proposals[:4]]

        selected_details = [
            p for p in all_proposals if p.get("id") in set(selected_ids)
        ]

        if not selected_details:

            async def _send_no_selection() -> None:
                available = [p.get("id", "") for p in all_proposals]
                await _asend_dict(
                    session.interactive,
                    {
                        "type": proto.COMMAND_RESPONSE,
                        "session_id": session_id,
                        "action": "error",
                        "message": f"No matching hypotheses found. Available: {', '.join(available[:20])}",
                    },
                    flag=InteractionFlags.TurnCompleted,
                )

            asyncio.create_task(_send_no_selection())
            return

        async def _run_experiment() -> None:
            try:
                from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.conversational.handlers.proposal_selection import (
                    create_hub,
                )
                from rankevolve.src.server.tool_executor import SessionToolExecutor

                tool_executor = SessionToolExecutor(
                    session,
                    tasks_dir=session.session_tasks_dir,
                    persist_callback=self._make_persist_callback(),
                )
                group_by = data.get("group_by", "batch")
                # `create_hub` is the single source of truth for both the widget
                # path and this slash-command path; produces a byte-identical
                # announcement string via `format_hub_announcement`.
                _multi_task_id, summary = await create_hub(
                    tool_executor,
                    selected_details,
                    proposals_data if isinstance(proposals_data, dict) else {},
                    custom_queries=[],
                    group_by=group_by,
                )
                session.conversation.add_user_message(
                    f"/experiment --select {','.join(selected_ids)}"
                )
                session.conversation.add_assistant_message(summary)

                await _asend_dict(
                    session.interactive,
                    {
                        "type": proto.COMMAND_RESPONSE,
                        "session_id": session_id,
                        "action": "experiment",
                        "message": summary,
                    },
                    flag=InteractionFlags.TurnCompleted,
                )

            except Exception as e:
                logger.error("Experiment command failed: %s", e, exc_info=True)
                await _asend_dict(
                    session.interactive,
                    {
                        "type": proto.COMMAND_RESPONSE,
                        "session_id": session_id,
                        "action": "error",
                        "message": f"Experiment command failed: {e}",
                    },
                    flag=InteractionFlags.TurnCompleted,
                )

        asyncio.create_task(_run_experiment())

    def _run_executor_action(
        self,
        message: dict[str, Any],
        session: "RankEvolveSession",
        result: "CommandResult",
        *,
        action: str,
        executor_method_name: str,
        log_label: str,
    ) -> None:
        """Bridge a slash command directly into a SessionToolExecutor method.

        Mirrors `_handle_experiment`'s shape (build executor → call → emit
        COMMAND_RESPONSE → persist) but parameterized so the small set of
        slash commands that map 1:1 to a single tool_executor method
        (experiment_combos, implement_hypothesis) don't each need their
        own near-identical handler. Methods invoked here MUST accept a
        single `args: dict` and return `ToolExecutionResult`.
        """
        session_id = message.get("session_id", "")
        content = message.get("content", "")
        data = result.data or {}

        async def _run() -> None:
            try:
                from rankevolve.src.server.tool_executor import (
                    SessionToolExecutor,
                )

                te = SessionToolExecutor(
                    session,
                    tasks_dir=session.session_tasks_dir,
                    persist_callback=self._make_persist_callback(),
                )
                method = getattr(te, executor_method_name)
                tr = await method(data)
                # Persist the slash command + tool result in conversation so
                # they survive reconnect (matches _handle_experiment pattern).
                if content:
                    session.conversation.add_user_message(content)
                if getattr(tr, "result", None):
                    session.conversation.add_assistant_message(tr.result)
                await _asend_dict(
                    session.interactive,
                    {
                        "type": proto.COMMAND_RESPONSE,
                        "session_id": session_id,
                        "action": action,
                        "message": getattr(tr, "result", "") or "",
                    },
                    flag=InteractionFlags.TurnCompleted,
                )
                await asyncio.to_thread(
                    self._session_manager.persist_session_state, session,
                )
            except Exception as e:
                logger.exception(
                    "%s slash handler failed: %s", log_label, e,
                )
                await _asend_dict(
                    session.interactive,
                    {
                        "type": proto.COMMAND_RESPONSE,
                        "session_id": session_id,
                        "action": "error",
                        "message": f"{log_label} failed: {e}",
                    },
                    flag=InteractionFlags.TurnCompleted,
                )

        _schedule_async(session, _run())

    def _handle_experiment_combos(
        self,
        message: dict[str, Any],
        session: "RankEvolveSession",
        result: "CommandResult",
    ) -> None:
        """Dispatch /experiment-hypothesis-combos (incl. --aggregate-only)
        directly into the tool executor pipeline."""
        self._run_executor_action(
            message, session, result,
            action="experiment_combos",
            executor_method_name="_exec_experiment_combos",
            log_label="experiment_combos",
        )

    def _handle_implement_hypothesis(
        self,
        message: dict[str, Any],
        session: "RankEvolveSession",
        result: "CommandResult",
    ) -> None:
        """Dispatch /implement-hypothesis directly into the tool executor."""
        self._run_executor_action(
            message, session, result,
            action="implement_hypothesis",
            executor_method_name="_exec_implement_hypothesis",
            log_label="implement_hypothesis",
        )

    def _handle_setup_submission(self, message: dict[str, Any]) -> None:
        """Handle ``setup_submission`` — enqueue a PTI run that generates
        the Implementation Hub's submission script.

        Forwarded by the WebUI from the SetupWizardModal POST. The expected
        message body is:

            {
              session_id, multi_task_id, setup_id, setup_name,
              reference_scripts, library_template, reference_command,
              additional_instructions, selected_hypothesis_ids,
            }

        Note (v2): ``hypothesis_flag_map`` is no longer forwarded — flag-name
        resolution moved to the WebUI Submit modal, so the script receives
        canonical config field names verbatim.

        The handler builds a ``SessionToolExecutor`` with the same wiring as
        ``_handle_experiment`` (queue_service + persist_callback) so the
        enqueued PTI task starts immediately and is restart-safe.
        """
        session_id = message.get("session_id", "")
        session = self._session_manager.get(session_id)

        if not isinstance(session, RankEvolveSession) or not session.interactive:
            logger.warning("setup_submission: no active session for %s", session_id)
            return

        multi_task_id = message.get("multi_task_id", "")
        setup_id = message.get("setup_id", "")
        setup_name = message.get("setup_name", "")
        if not multi_task_id or not setup_id:
            logger.warning(
                "setup_submission: missing multi_task_id or setup_id "
                "(session=%s, keys=%s)",
                session_id,
                list(message.keys()),
            )
            return

        reference_scripts = message.get("reference_scripts") or []
        if not isinstance(reference_scripts, list):
            reference_scripts = []
        library_template = message.get("library_template") or None
        reference_command = message.get("reference_command", "")
        additional_instructions = message.get("additional_instructions", "")
        selected_hypothesis_ids = message.get("selected_hypothesis_ids") or []
        if not isinstance(selected_hypothesis_ids, list):
            selected_hypothesis_ids = []

        async def _run_setup() -> None:
            try:
                from rankevolve.src.server.tool_executor import SessionToolExecutor

                # Pass queue_service + persist_callback so the executor's
                # enqueue_and_maybe_execute fires _try_start_next_task
                # AND the queue mutation persists to disk immediately
                # (Layer 1 invariant — same wiring asymmetry the chat
                # handler had before the persist_callback fix).
                tool_executor = SessionToolExecutor(
                    session,
                    tasks_dir=session.session_tasks_dir,
                    queue_service=self._queue_service,
                    persist_callback=self._make_persist_callback(),
                )
                task_id = await tool_executor.setup_submission_script(
                    multi_task_id=multi_task_id,
                    setup_id=setup_id,
                    setup_name=setup_name,
                    reference_scripts=reference_scripts,
                    library_template=library_template,
                    reference_command=reference_command,
                    additional_instructions=additional_instructions,
                    selected_hypothesis_ids=selected_hypothesis_ids,
                )
                logger.info(
                    "setup_submission: enqueued PTI task=%s "
                    "(session=%s, multi=%s, setup=%s)",
                    task_id,
                    session_id,
                    multi_task_id,
                    setup_id,
                )
            except Exception as e:
                logger.error(
                    "setup_submission failed (session=%s, setup=%s): %s",
                    session_id,
                    setup_id,
                    e,
                    exc_info=True,
                )
                # Surface the failure to the WebUI so the setup state can
                # be flipped from in_progress → error without waiting for
                # the (non-existent) PTI completion.
                await _asend_dict(
                    session.interactive,
                    {
                        "type": proto.SETUP_COMPLETED,
                        "session_id": session_id,
                        "multi_task_id": multi_task_id,
                        "setup_id": setup_id,
                        "setup_name": setup_name,
                        "task_id": "",
                        "status": "error",
                        "error": f"Failed to enqueue setup PTI: {e}"[:200],
                    },
                    flag=InteractionFlags.MessageOnly,
                )

        _schedule_async(session, _run_setup())

    def _handle_run_submission(self, message: dict[str, Any]) -> None:
        """Handle ``run_submission`` — enqueue a submission_run that spawns
        the user's submit_v<n>.py as a subprocess.

        Forwarded by the WebUI from the SubmitExperimentConfirm POST.
        Expected message body:

            {
              session_id, multi_task_id, submission_id, setup_id,
              script_path, launch_path, enable_flags, experiment_name,
              submission_label,
            }
        """
        session_id = message.get("session_id", "")
        session = self._session_manager.get(session_id)
        if not isinstance(session, RankEvolveSession) or not session.interactive:
            logger.warning("run_submission: no active session for %s", session_id)
            return

        multi_task_id = message.get("multi_task_id", "")
        submission_id = message.get("submission_id", "")
        setup_id = message.get("setup_id", "")
        script_path = message.get("script_path", "")
        launch_path = message.get("launch_path", "")
        if not (multi_task_id and submission_id and script_path and launch_path):
            logger.warning(
                "run_submission: missing required field (session=%s, keys=%s)",
                session_id,
                list(message.keys()),
            )
            return

        enable_flags = message.get("enable_flags") or []
        if not isinstance(enable_flags, list):
            enable_flags = []
        experiment_name = message.get("experiment_name", "") or ""
        submission_label = message.get("submission_label", "") or submission_id
        app_layer_version = message.get("app_layer_version", "") or ""
        build_command = message.get("build_command", "") or ""

        async def _run_run() -> None:
            try:
                from rankevolve.src.server.tool_executor import SessionToolExecutor

                tool_executor = SessionToolExecutor(
                    session,
                    tasks_dir=session.session_tasks_dir,
                    queue_service=self._queue_service,
                    persist_callback=self._make_persist_callback(),
                )
                task_id = await tool_executor.run_submission_script(
                    multi_task_id=multi_task_id,
                    submission_id=submission_id,
                    setup_id=setup_id,
                    script_path=script_path,
                    launch_path=launch_path,
                    enable_flags=enable_flags,
                    experiment_name=experiment_name,
                    submission_label=submission_label,
                    app_layer_version=app_layer_version,
                    build_command=build_command,
                )
                logger.info(
                    "run_submission: enqueued task=%s (session=%s, sub=%s)",
                    task_id,
                    session_id,
                    submission_id,
                )
            except Exception as e:
                logger.error(
                    "run_submission failed (session=%s, sub=%s): %s",
                    session_id,
                    submission_id,
                    e,
                    exc_info=True,
                )
                # Surface to WebUI so the run row shows error rather than
                # sitting on 'submitted' indefinitely.
                await _asend_dict(
                    session.interactive,
                    {
                        "type": proto.SUBMISSION_STATE,
                        "session_id": session_id,
                        "multi_task_id": multi_task_id,
                        "submission_id": submission_id,
                        "setup_id": setup_id,
                        "status": "error",
                        "fblearnerError": (f"Failed to enqueue submission_run: {e}")[
                            :200
                        ],
                    },
                    flag=InteractionFlags.MessageOnly,
                )

        _schedule_async(session, _run_run())

    def _handle_task_cancel_by_id(self, message: dict[str, Any]) -> None:
        """Cancel a specific queue-managed task by task_id.

        Distinct from ``_handle_task_cancel`` which generically cancels
        ``session.active_task`` (overwritten across multiple paths). The
        plan's M-cancel infrastructure (Section 5) requires a per-task
        registry — see ``RankEvolveSession.running_task_handles``.

        Cleanup after cancel:
          1. Cancel the asyncio.Task — propagates as CancelledError into
             ``SubmissionRunner.run`` which terminates the subprocess
             under asyncio.shield.
          2. Mark the queue entry status='error' with reason='cancelled by
             user' so resume reconcile sees the cancel rather than a
             phantom 'running'.
          3. Persist + emit ``submission_state`` with status='cancelled'
             so the WebUI flips the run row.
        """
        session_id = message.get("session_id", "")
        target_task_id = message.get("task_id", "")
        if not target_task_id:
            return

        session = self._session_manager.get(session_id)
        if not isinstance(session, RankEvolveSession):
            return

        handle = (
            session.running_task_handles.get(target_task_id)
            if hasattr(session, "running_task_handles")
            else None
        )
        if handle is None or handle.done():
            logger.info(
                "task_cancel_by_id: no live handle for task_id=%s "
                "(already finished or never started)",
                target_task_id,
            )
            return

        # Cancel — the wrapping create_task() raises CancelledError into
        # the runner. Cleanup state in a follow-up coroutine after the
        # cancel is acknowledged so we don't race the queue runner's
        # mark_completed/mark_error.
        handle.cancel()

        async def _post_cancel_cleanup() -> None:
            # Wait for the cancelled task to actually unwind so
            # mark_error doesn't race with the queue runner's own
            # mark_completed in _try_start_next_task.
            try:
                await asyncio.gather(handle, return_exceptions=True)
            except Exception:
                pass
            wc = session.workflow_context
            entry = wc.get_entry(target_task_id) or {}
            if entry.get("status") not in ("completed", "error"):
                wc.mark_error(target_task_id, error="cancelled by user")
                try:
                    await asyncio.to_thread(
                        self._session_manager.persist_session_state, session
                    )
                except Exception as e:
                    logger.warning("task_cancel_by_id persist failed: %s", e)

            # Emit submission_state for run-task entries so the WebUI's
            # PATCH path flips status='cancelled' on the submission row.
            # Sole owner of the cancelled-state emission (the
            # _exec_submission_run sibling deliberately does NOT emit on
            # CancelledError to keep the writer count at 1 — see comment
            # there).
            tool_name = entry.get("tool_name", "")
            if tool_name == "submission_run" and session.interactive:
                import time as _time

                args = entry.get("args") or {}
                await _asend_dict(
                    session.interactive,
                    {
                        "type": proto.SUBMISSION_STATE,
                        "session_id": session_id,
                        "multi_task_id": entry.get("multi_task_id", ""),
                        "submission_id": args.get("submission_id", ""),
                        "setup_id": args.get("setup_id", ""),
                        "status": "cancelled",
                        "runTaskId": target_task_id,
                        "runFinishedAt": int(_time.time() * 1000),
                    },
                    flag=InteractionFlags.MessageOnly,
                )
                # Also update the task subtab so the spinner stops.
                await _asend_dict(
                    session.interactive,
                    {
                        "type": proto.TASK_STATUS,
                        "session_id": session_id,
                        "task_id": target_task_id,
                        "status": "error",
                        "message": "cancelled by user",
                        "multi_task_id": entry.get("multi_task_id", ""),
                    },
                    flag=InteractionFlags.MessageOnly,
                )

        try:
            asyncio.create_task(_post_cancel_cleanup())
        except RuntimeError:
            # No running loop — fall back to synchronous run, mirroring
            # _schedule_async's worker-thread fallback.
            try:
                asyncio.run(_post_cancel_cleanup())
            except Exception as e:
                logger.warning("task_cancel_by_id sync cleanup failed: %s", e)

    def _handle_research_propose(
        self,
        message: dict[str, Any],
        session: RankEvolveSession,
        cmd_result: CommandResult,
    ) -> None:
        """Handle a /research-propose command — run ResearchProposeBridge."""
        session_id = message.get("session_id", "")
        raw_args = cmd_result.data.get("args", "")

        task_id = f"rp-{uuid.uuid4().hex[:8]}"
        session.info.active_task_id = task_id

        async def _run_rp() -> None:
            try:
                request, options = parse_research_propose_options(raw_args)

                # Merge data-level flags (from /research, /propose shortcuts)
                if cmd_result.data.get("research_only"):
                    options["research_only"] = True
                if cmd_result.data.get("disable_unified_proposal"):
                    options["disable_unified_proposal"] = True

                from pathlib import Path

                from rankevolve.src.server.research_propose_bridge import (
                    ResearchProposeBridge,
                )

                root = Path(
                    session.info.session_root_path
                    if hasattr(session.info, "session_root_path")
                    and session.info.session_root_path
                    else "."
                )
                # Override root if --workflow-target-path provided
                workflow_target = options.get("workflow_target_path")
                if workflow_target:
                    target_path = Path(workflow_target)
                    if target_path.is_file():
                        root = target_path.parent
                    elif target_path.is_dir():
                        root = target_path

                # Update workflow_context BEFORE bridge construction
                rp_phase = session.workflow_context.tool_phase_map.get(
                    "research_propose", "2"
                )
                session.workflow_context.start_phase(rp_phase, request[:80])

                # Merge paths into session_context
                session_ctx = dict(session.session_context or {})
                if workflow_target:
                    session_ctx["workflow_target_path"] = workflow_target
                docs_path = options.get("docs_path")
                if docs_path:
                    session_ctx["docs_path"] = docs_path

                bridge = ResearchProposeBridge(
                    root_folder=root,
                    model=options.get("model"),
                    research_only=options.get("research_only", False),
                    disable_unified_proposal=options.get(
                        "disable_unified_proposal", False
                    ),
                    breakdown_only=options.get("breakdown_only", False),
                    max_breakdown=options.get(
                        "max_breakdown",
                        options.get(
                            "max_queries",
                            "5 to 20 (or you really want to suggest more)",
                        ),
                    ),
                    max_researches=options.get("max_researches"),
                    output_dir=session.session_tasks_dir,
                    knowledge_bridge=getattr(session, "knowledge_bridge", None),
                    session_context=session_ctx,
                    resume_workspace=options.get("resume"),
                    base_inferencer_type=options.get("base_inferencer"),
                    research_inferencer_type=options.get("research_inferencer"),
                    proposal_inferencer_type=options.get("proposal_inferencer"),
                )
                session.workflow_context.active_workspace = str(bridge.workspace)

                # Persist a chronological task_ref BEFORE the WS emit (see
                # _run_task / _exec_research_propose for the same pattern).
                # Best-effort: chip-write failures MUST NOT abort the task
                # launch — chip placement is auxiliary UI metadata.
                if session.conversation:
                    try:
                        session.conversation.add_task_ref(
                            task_id=task_id,
                            label="Research & Proposal",
                            tool_name="research_propose",
                        )
                        await asyncio.to_thread(
                            self._session_manager.persist_session_state, session
                        )
                    except Exception as chip_err:
                        logger.warning(
                            "add_task_ref failed for research_propose "
                            "task_id=%s — task will still launch, chip "
                            "placement may be missing on resume: %s",
                            task_id,
                            chip_err,
                        )

                await _asend_dict(
                    session.interactive,
                    {
                        "type": proto.TASK_STATUS,
                        "session_id": session_id,
                        "task_id": task_id,
                        "status": "starting",
                        "request": request[:80],
                        "workspace": str(bridge.workspace),
                    },
                    flag=InteractionFlags.MessageOnly,
                )

                await bridge.run(request)

                session.workflow_context.complete_phase(
                    rp_phase,
                    summary=request[:80],
                    workspace_path=str(bridge.workspace),
                    task_id=task_id,
                )
                await asyncio.to_thread(
                    self._session_manager.persist_session_state, session
                )

                await _asend_dict(
                    session.interactive,
                    {
                        "type": proto.TASK_STATUS,
                        "session_id": session_id,
                        "task_id": task_id,
                        "status": "completed",
                        "workspace": str(bridge.workspace),
                    },
                    flag=InteractionFlags.TurnCompleted,
                )
                session.info.active_task_id = None

                # Auto-advance for research_propose
                if not getattr(session, "_is_auto_advance_turn", False):
                    auto_msg = (
                        f"[System notification: Phase {rp_phase} (Research & Proposal) completed. "
                        f"Workspace: {bridge.workspace}. "
                        f"Please review the results and guide the user to the next workflow phase.]"
                    )
                    await asyncio.to_thread(
                        self._queue_service.put,
                        f"user_input_{session_id}",
                        {
                            "type": "chat_message",
                            "content": auto_msg,
                            "session_id": session_id,
                            "auto_advance": True,
                        },
                    )

            except Exception as e:
                logger.error("Research-propose error for session %s: %s", session_id, e)
                session.workflow_context.fail_phase(
                    rp_phase,
                    error=str(e)[:80],
                    task_id=task_id,
                )
                await asyncio.to_thread(
                    self._session_manager.persist_session_state, session
                )
                await _asend_dict(
                    session.interactive,
                    {
                        "type": proto.ERROR,
                        "message": f"Research-propose error: {e}",
                        "session_id": session_id,
                        "task_id": task_id,
                    },
                    flag=InteractionFlags.TurnCompleted,
                )
                session.info.active_task_id = None

        session.active_task = asyncio.create_task(_run_rp())

    # Map of live-widget metadata.widget_type -> persisted "flat card" widget_type.
    # Cancellations (confirmation choice == "no") are intentionally absent — the
    # canceled card has no value to keep around.
    #
    # Grouped-widgets (Plan v3 / Phase 2b two-paths UX): the entry "grouped"
    # signals the per-child branch in `_maybe_persist_widget_card` — that
    # branch iterates `live_metadata["tools"]` and emits one card per child
    # via `_GROUPED_CHILD_CARD_TYPE` per the child's `on_group_resolve`.
    _WIDGET_CARD_TYPE: dict[str, str] = {
        "confirmation": "confirmation_approved",
        "proposal_selection": "proposal_selection_submitted",
        "grouped": "grouped",  # sentinel — grouped branch handles per-child emit
    }

    # Per-child card types for grouped widgets (Plan v3).
    # Indexed by (child_widget_type, role) where role is one of:
    #   "approved"  — the submitted child + on_group_resolve="flatten"
    #   "skipped"   — a sibling child   + on_group_resolve="flatten"
    #   "disabled"  — any child         + on_group_resolve="keep"
    # `on_group_resolve="hide"` suppresses card emission entirely (no entry).
    _GROUPED_CHILD_CARD_TYPE: dict[tuple[str, str], str] = {
        ("confirmation", "approved"):       "confirmation_approved",
        ("confirmation", "skipped"):        "confirmation_skipped",
        ("confirmation", "disabled"):       "confirmation_disabled",
        ("proposal_selection", "approved"): "proposal_selection_submitted",
        ("proposal_selection", "skipped"):  "proposal_selection_skipped",
        ("proposal_selection", "disabled"): "proposal_selection_disabled",
    }

    def _maybe_persist_widget_card(
        self, session: RankEvolveSession, message: dict[str, Any]
    ) -> None:
        """Persist a structured widget_response row + WS-echo to the client.

        Reads the live InputModeConfig from interactive.pending_input_mode for
        prompt/view/view_label/widget_type, and the user's selection from the
        message dict. No-ops when the active widget is not a card-bearing
        widget, or when the user's choice cancels the action.
        """
        interactive = session.interactive
        pending_mode = getattr(interactive, "pending_input_mode", None)
        if pending_mode is None:
            # Diagnostic: each early-return path below logs why no card was
            # written. Without this, the helper would silently swallow misroutes
            # (e.g. interactive subclass without the accessor, or a widget that
            # uses send_widget instead of asend_response+input_mode).
            logger.info(
                "widget_card.skip session=%s reason=no_pending_input_mode "
                "interactive=%s",
                session.session_id,
                type(interactive).__name__,
            )
            return

        live_metadata: dict[str, Any] = getattr(pending_mode, "metadata", None) or {}
        live_widget_type = live_metadata.get("widget_type")
        card_widget_type = self._WIDGET_CARD_TYPE.get(live_widget_type or "")
        if card_widget_type is None:
            logger.info(
                "widget_card.skip session=%s reason=unsupported_widget_type "
                "live_widget_type=%r metadata_keys=%s",
                session.session_id,
                live_widget_type,
                list(live_metadata.keys()),
            )
            return

        # Grouped-widget branch (Plan v3): iterate per-child config, emit
        # one card per child per its `on_group_resolve`. Returns early —
        # the per-child cards replace the single-widget card emission.
        if live_widget_type == "grouped":
            self._persist_grouped_widget_cards(session, message, pending_mode)
            return

        user_input = message.get("content") or message.get("user_input")
        widget_data: dict[str, Any] = {
            "prompt": getattr(pending_mode, "prompt", "") or "",
            "view": live_metadata.get("view"),
            "view_label": live_metadata.get("view_label"),
        }

        if live_widget_type == "confirmation":
            choice = self._extract_confirmation_choice(user_input)
            # Only commit the approved card on yes — cancellations do not
            # produce a transcript entry.
            if choice != "yes":
                logger.info(
                    "widget_card.skip session=%s reason=confirmation_not_yes choice=%r",
                    session.session_id,
                    choice,
                )
                return
            widget_data["choice"] = choice
        elif live_widget_type == "proposal_selection":
            widget_data["proposals"] = live_metadata.get("proposals") or {}
            selection = self._extract_proposal_selection(user_input, message)
            widget_data["selected_proposals"] = selection.get("selected_proposals", [])
            widget_data["custom_queries"] = selection.get("custom_queries", [])

        client_id = message.get("client_id")
        msg_row = session.conversation.add_widget_response_card(
            widget_type=card_widget_type,
            widget_data=widget_data,
        )
        logger.info(
            "widget_card.write session=%s widget_type=%s row_id=%s view=%s "
            "view_label=%s",
            session.session_id,
            card_widget_type,
            msg_row.id,
            widget_data.get("view"),
            widget_data.get("view_label"),
        )

        # Persist immediately so a crash before the next persist tick does not
        # lose the card. Best-effort — the inferencer turn-end persist will
        # cover us if this throws.
        try:
            self._session_manager.persist_session_state(session)
        except Exception:
            logger.exception(
                "persist after widget card write failed for session %s",
                session.session_id,
            )

        echo: dict[str, Any] = {
            "type": proto.WIDGET_RESPONSE_COMMITTED,
            "session_id": session.session_id,
            "id": msg_row.id,
            "widget_type": card_widget_type,
            "widget_data": widget_data,
            "timestamp": msg_row.timestamp,
        }
        if client_id is not None:
            echo["client_id"] = client_id
        # Push the echo via the synchronous _send_response path. _schedule_async
        # would clobber session.active_task (which holds the agent's running
        # coroutine that's blocked on aget_input). _send_response just enqueues
        # onto the response queue (asyncio.Queue.put_nowait), which is the same
        # path used right below for _input_queue.put_nowait — safe from this
        # handler thread context.
        interactive._send_response(echo, InteractionFlags.MessageOnly)

    def _persist_grouped_widget_cards(
        self,
        session: RankEvolveSession,
        message: dict[str, Any],
        pending_mode: Any,
    ) -> None:
        """Emit per-child widget_response_cards for a grouped widget submission.

        Plan v3 / Phase 2b two-paths UX. Iterates `live_metadata["tools"]`
        (each child carries its own `widget_type`, `prompt`, `metadata`,
        `output_var`, `child_id`). For each child:
          * If submitted (matches `values.submitted_child`): emit
            `<wt>_approved` (flatten) | no card (hide) | `<wt>_disabled` (keep)
          * Else (sibling): emit
            `<wt>_skipped` (flatten) | no card (hide) | `<wt>_disabled` (keep)

        Default `on_group_resolve` is "flatten". Unknown values logged
        as WARNING + treated as "flatten".
        """
        live_metadata: dict[str, Any] = getattr(pending_mode, "metadata", None) or {}
        group_id = live_metadata.get("group_id", "")
        children: list[dict[str, Any]] = live_metadata.get("tools") or []
        if not children:
            logger.warning(
                "widget_card.grouped.skip session=%s group_id=%r "
                "reason=no_children_in_metadata",
                session.session_id,
                group_id,
            )
            return

        # Race protection (Plan v3): if a near-simultaneous double-click
        # delivers two `pending_input_response` messages for the same
        # group, the FIRST wins and emits cards; the SECOND skips card
        # emission. Per-session in-memory `_resolved_groups` set is
        # session-scoped and survives only the current process — sufficient
        # because the per-session async loop serializes handler-message
        # processing.
        if group_id:
            resolved: set[str] = getattr(session, "_resolved_groups", set())
            if group_id in resolved:
                logger.info(
                    "widget_card.grouped.skip session=%s group_id=%r "
                    "reason=group_already_resolved (race protection)",
                    session.session_id,
                    group_id,
                )
                return
            try:
                resolved.add(group_id)
                # Attribute may not exist on first add — set it.
                session._resolved_groups = resolved  # type: ignore[attr-defined]
            except Exception:
                pass

        # Decode the submitted child's id from the response envelope.
        # Plan v5 Bug B fix: response can arrive via either
        #   message.values     — when AgentChatPanel.js's widget_id branch fires
        #                        (legacy single-widget path)
        #   message.user_input — when widget_id is absent from pendingInput.widget
        #                        (the default for grouped widgets — the envelope
        #                        doesn't carry a top-level widget_id)
        # Without the user_input fallback both children get is_submitted=False
        # and are flagged "skipped" (the v3 cosmetic bug verified in server.log).
        values = message.get("values")
        if not isinstance(values, dict) or not values:
            ui = message.get("user_input")
            if isinstance(ui, dict):
                values = ui
            else:
                values = {}
        # Unwrap nested {values: {...}} (legacy compound-path convention).
        if isinstance(values, dict):
            inner = values.get("values")
            if isinstance(inner, dict):
                values = inner
        submitted_child_id = ""
        # Accept any type — _extract_*_choice handles dict/str/None polymorphically.
        # Mirrors the rich-group dispatch's payload wrap so card persistence and
        # handler dispatch agree on which child was submitted.
        submitted_payload: Any = None
        if isinstance(values, dict):
            submitted_child_id = str(values.get("submitted_child", ""))
            submitted_payload = values.get("payload")

        client_id = message.get("client_id")
        interactive = session.interactive

        for child in children:
            if not isinstance(child, dict):
                continue
            child_id = str(child.get("child_id", ""))
            child_wt = str(child.get("tool_type", "")) or str(
                (child.get("input_mode") or {}).get("metadata", {}).get(
                    "widget_type", ""
                )
            )
            child_meta: dict[str, Any] = child.get("metadata") or {}
            on_resolve = str(
                child_meta.get("on_group_resolve", "flatten") or "flatten"
            ).lower()
            if on_resolve not in ("flatten", "hide", "keep"):
                logger.warning(
                    "widget_card.grouped: unknown on_group_resolve=%r for "
                    "child %s — defaulting to 'flatten'",
                    on_resolve,
                    child_id,
                )
                on_resolve = "flatten"

            is_submitted = child_id == submitted_child_id
            if on_resolve == "hide":
                logger.info(
                    "widget_card.grouped.hide session=%s child=%s wt=%s "
                    "(no card emitted)",
                    session.session_id,
                    child_id,
                    child_wt,
                )
                continue

            if on_resolve == "keep":
                role = "disabled"
            elif is_submitted:
                role = "approved"
            else:
                role = "skipped"

            card_type = self._GROUPED_CHILD_CARD_TYPE.get((child_wt, role))
            if card_type is None:
                logger.warning(
                    "widget_card.grouped.skip session=%s child=%s "
                    "reason=unsupported_(wt,role)=%r",
                    session.session_id,
                    child_id,
                    (child_wt, role),
                )
                continue

            # Build per-child widget_data. Reuses the shape the existing
            # single-widget cards use so React's persisted-card replay
            # branches stay symmetric.
            child_input_mode: dict[str, Any] = child.get("input_mode") or {}
            child_input_metadata: dict[str, Any] = (
                child_input_mode.get("metadata") or {}
            )
            widget_data: dict[str, Any] = {
                "prompt": child.get("prompt", "")
                or child_input_mode.get("prompt", ""),
                "view": child_input_metadata.get("view"),
                "view_label": child_input_metadata.get("view_label"),
                "group_id": group_id,
                "group_role": child_meta.get("group_role"),
            }
            if child_wt == "confirmation":
                if is_submitted:
                    widget_data["choice"] = self._extract_confirmation_choice(
                        submitted_payload
                    )
                # If this confirmation submission triggered a server-side
                # action (e.g., open_experiment_hub), forward the
                # multi_task_id so the [View Hub →] button on the card works.
                action = child_meta.get("on_yes_action")
                if action and is_submitted:
                    widget_data["action"] = action
                    # multi_task_id is set on the workflow_context after
                    # open_experiment_hub completes; read it back.
                    try:
                        wc = session.workflow_context
                        mid = getattr(wc, "active_multi_task_id", None)
                        if mid:
                            widget_data["multi_task_id"] = mid
                    except Exception:
                        pass
            elif child_wt == "proposal_selection":
                widget_data["proposals"] = child_input_metadata.get(
                    "proposals"
                ) or {}
                if is_submitted:
                    sel = self._extract_proposal_selection(
                        submitted_payload, message
                    )
                    widget_data["selected_proposals"] = sel.get(
                        "selected_proposals", []
                    )
                    widget_data["custom_queries"] = sel.get("custom_queries", [])
            # For `keep` (disabled) cards, also pass the full original
            # input_mode so React can render the live widget shape with
            # `disabled=true` prop.
            if on_resolve == "keep":
                widget_data["live_input_mode"] = child_input_mode

            msg_row = session.conversation.add_widget_response_card(
                widget_type=card_type,
                widget_data=widget_data,
            )
            logger.info(
                "widget_card.grouped.write session=%s group_id=%r "
                "child=%s wt=%s role=%s card_type=%s row_id=%s",
                session.session_id,
                group_id,
                child_id,
                child_wt,
                role,
                card_type,
                msg_row.id,
            )

            # Emit echo for each child card so React's WIDGET_RESPONSE_COMMITTED
            # reducer renders them stacked in the chat transcript.
            echo: dict[str, Any] = {
                "type": proto.WIDGET_RESPONSE_COMMITTED,
                "session_id": session.session_id,
                "id": msg_row.id,
                "widget_type": card_type,
                "widget_data": widget_data,
                "timestamp": msg_row.timestamp,
            }
            if client_id is not None:
                echo["client_id"] = client_id
            if interactive is not None:
                interactive._send_response(echo, InteractionFlags.MessageOnly)

        # Persist immediately so the per-child cards survive a crash.
        try:
            self._session_manager.persist_session_state(session)
        except Exception:
            logger.exception(
                "persist after grouped widget card writes failed for session %s",
                session.session_id,
            )

    @staticmethod
    def _extract_confirmation_choice(user_input: Any) -> str:
        """Normalize the confirmation widget's response to 'yes' | 'no' | other."""
        if isinstance(user_input, dict):
            choice = user_input.get("choice", "")
        else:
            choice = user_input or ""
        return str(choice).strip().lower()

    @staticmethod
    def _extract_proposal_selection(
        user_input: Any, message: dict[str, Any]
    ) -> dict[str, Any]:
        """Extract selected_proposals / custom_queries from a proposal response.

        Looks first inside user_input (dict form), then falls back to the
        top-level message dict (the WidgetResponse path puts these under
        `values`).
        """
        if isinstance(user_input, dict):
            return {
                "selected_proposals": user_input.get("selected_proposals", []),
                "custom_queries": user_input.get("custom_queries", []),
            }
        values = message.get("values") or {}
        if isinstance(values, dict):
            return {
                "selected_proposals": values.get("selected_proposals", []),
                "custom_queries": values.get("custom_queries", []),
            }
        return {"selected_proposals": [], "custom_queries": []}

    def _handle_pending_input_response(self, message: dict[str, Any]) -> None:
        """Handle a pending_input_response — push user input to interactive's queue.

        The frontend sends this when the user responds to a PENDING_INPUT prompt
        (either text input or structured widget response).
        """
        session_id = message.get("session_id", "")
        logger.info(
            "pending_input_response received for session %s, msg_keys=%s",
            session_id,
            list(message.keys()),
        )
        session = self._session_manager.get(session_id)

        if not isinstance(session, RankEvolveSession) or not session.interactive:
            logger.warning("No session for pending_input_response: %s", session_id)
            return

        # Snapshot the live widget config + user response into a persisted
        # `widget_response` row BEFORE pushing into the input queue. After
        # aget_input() consumes the response, _pending_input_mode is cleared
        # and the structured fields (prompt/view/view_label) are gone.
        # Failures here must not block the input handoff — log and continue.
        try:
            self._maybe_persist_widget_card(session, message)
        except Exception:
            logger.exception(
                "Failed to persist widget_response card for session %s",
                session_id,
            )

        # Push the response into the interactive's input queue so the
        # awaiting aget_input() call receives it
        user_input = message.get("content") or message.get("user_input", "")
        widget_id = message.get("widget_id")

        if widget_id:
            # Structured widget response
            input_data = {
                "widget_id": widget_id,
                "values": message.get("values", {}),
                "action": message.get("action", "submit"),
                "session_id": session_id,
            }
        else:
            # Text input response
            input_data = {
                "user_input": user_input,
                "session_id": session_id,
                "timestamp": message.get("timestamp", ""),
            }

        # Push to the interactive's input queue
        interactive = session.interactive
        logger.info(
            "pending_input_response: interactive=%s, has _input_queue=%s, "
            "has input_queue=%s",
            type(interactive).__name__,
            hasattr(interactive, "_input_queue"),
            hasattr(interactive, "input_queue"),
        )
        if hasattr(interactive, "_input_queue"):
            # WebUIInteractive — put_nowait is thread-safe for asyncio.Queue
            try:
                interactive._input_queue.put_nowait(input_data)
                logger.info("Pushed to _input_queue for session %s", session_id)
            except asyncio.QueueFull:
                logger.error("Input queue full for session %s", session_id)
        elif hasattr(interactive, "push_input"):
            # Fallback for other async interactive implementations
            try:
                asyncio.run(interactive.push_input(input_data))
            except Exception as e:
                logger.error("push_input failed for session %s: %s", session_id, e)
        elif hasattr(interactive, "input_queue"):
            # QueueInteractive — sync push to queue service
            interactive.input_queue.put(
                queue_id=interactive.input_queue_id, obj=input_data
            )
            logger.info(
                "Pushed to file-based input_queue (queue_id=%s) for session %s",
                interactive.input_queue_id,
                session_id,
            )

        # Clear any persisted pending_widget.json for this session — the user
        # has now answered, so a later WebSocket reconnect must NOT re-prompt.
        # Best-effort; failure here cannot block the input handoff above.
        # Inlined (no cross-cut import of the WebUI bridge from the agent
        # server, which lives in a different Buck cell). Mirrors the
        # PENDING_WIDGET_FILENAME constant in agent_service_bridge.py.
        try:
            session_dir = (
                session.session_logger.session_dir
                if getattr(session, "session_logger", None) is not None
                else None
            )
            if session_dir is not None:
                target = Path(session_dir) / "pending_widget.json"
                try:
                    target.unlink()
                    logger.info(
                        "clear_pending_widget: removed %s for session %s",
                        target,
                        session_id,
                    )
                except FileNotFoundError:
                    pass
        except Exception:
            logger.exception(
                "clear_pending_widget failed for session %s", session_id
            )

    def _handle_task_cancel(self, message: dict[str, Any]) -> None:
        """Handle task cancellation."""
        session_id = message.get("session_id", "")
        session = self._session_manager.get(session_id)

        if isinstance(session, RankEvolveSession):
            if session.active_task and not session.active_task.done():
                session.active_task.cancel()
                logger.info("Task cancelled for session %s", session_id)

    def _handle_config_query(self, message: dict[str, Any]) -> None:
        """Handle config query — return current config (sync, runs in thread)."""
        session_id = message.get("session_id", "")
        session = self._session_manager.get(session_id)

        if not isinstance(session, RankEvolveSession) or not session.interactive:
            logger.warning(
                "CONFIG_QUERY: session %s not ready (type=%s, interactive=%s)",
                session_id,
                type(session).__name__ if session else "None",
                "yes" if session and getattr(session, "interactive", None) else "no",
            )
            return

        session_root_path = (
            session.info.session_root_path
            if hasattr(session.info, "session_root_path")
            else ""
        )
        model = session.app_config.model if session.app_config else ""

        logger.info(
            "CONFIG_QUERY: Sending config for session %s — model=%s, session_root_path=%s",
            session_id,
            model,
            session_root_path,
        )

        config_dict = {
            "type": proto.CONFIG_UPDATE,
            "session_id": session_id,
            "config": {
                "model": model,
                "provider": session.app_config.provider if session.app_config else "",
                "target_path": session_root_path,
            },
        }
        # Use _send_response directly — send_response() uses iter_() which
        # iterates over dict keys instead of sending the dict as one message.
        session.interactive._send_response(
            config_dict, flag=InteractionFlags.MessageOnly
        )

    def _handle_ping(self, message: dict[str, Any]) -> None:
        """Handle ping — respond with pong (sync, runs in thread)."""
        session_id = message.get("session_id", "")
        session = self._session_manager.get(session_id)

        if not isinstance(session, RankEvolveSession) or not session.interactive:
            return

        session.interactive._send_response(
            {"type": proto.PONG, "session_id": session_id},
            flag=InteractionFlags.MessageOnly,
        )

    def _handle_session_sync(self, message: dict[str, Any]) -> None:
        """Handle session_sync_request — return session state summary (sync, runs in thread)."""
        session_id = message.get("session_id", "")
        session = self._session_manager.get(session_id)

        if not isinstance(session, RankEvolveSession) or not session.interactive:
            return

        conv_length = len(session.conversation.messages) if session.conversation else 0
        response = {
            "type": proto.SESSION_SYNC_RESPONSE,
            "session_id": session_id,
            "is_restored": getattr(session, "_restored", False),
            "conversation_length": conv_length,
            "active_task_id": session.info.active_task_id,
            "workspace_path": getattr(session.info, "session_root_path", ""),
        }
        session.interactive._send_response(response, flag=InteractionFlags.MessageOnly)

    def _handle_queue_status(self, message: dict[str, Any]) -> None:
        """Handle queue_status_request — return queue depth and server info (sync, runs in thread)."""
        session_id = message.get("session_id", "")
        session = self._session_manager.get(session_id)

        if not isinstance(session, RankEvolveSession) or not session.interactive:
            return

        input_queue_id = f"user_input_{session_id}"
        response_queue_id = f"agent_response_{session_id}"

        try:
            input_depth = self._queue_service.size(input_queue_id)
        except Exception:
            input_depth = -1
        try:
            response_depth = self._queue_service.size(response_queue_id)
        except Exception:
            response_depth = -1
        try:
            control_depth = self._queue_service.size("server_control")
        except Exception:
            control_depth = -1

        total_sessions = len(self._session_manager.get_all_sessions())

        response = {
            "type": proto.QUEUE_STATUS_RESPONSE,
            "session_id": session_id,
            "global": {
                "server_control_depth": control_depth,
                "total_sessions": total_sessions,
            },
            "session": {
                "session_id": session_id,
                "input_queue": input_queue_id,
                "response_queue": response_queue_id,
                "input_depth": input_depth,
                "response_depth": response_depth,
                "active_task_id": session.info.active_task_id,
            },
        }
        session.interactive._send_response(response, flag=InteractionFlags.MessageOnly)
