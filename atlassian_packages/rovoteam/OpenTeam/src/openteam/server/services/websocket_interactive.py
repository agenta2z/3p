"""WebSocketInteractive — duck-typed adapter for ConversationalInferencer.run_agentic_loop().

Maps the 4 methods that run_agentic_loop() checks via hasattr() to WebSocket messages:
- stream_token_batches → batched {"type": "token"} messages
- send_turn_boundary → {"type": "turn_boundary"} message
- asend_response → {"type": "pending_input"} message (conversation tool prompts)
- aget_input → awaits from asyncio.Queue (fed by incoming WS messages)

Does NOT inherit from InteractiveBase — run_agentic_loop uses hasattr duck-typing.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncIterator, Callable, Coroutine


class WebSocketInteractive:
    """Adapts WebSocket transport for ConversationalInferencer.run_agentic_loop()."""

    def __init__(
        self,
        send_callback: Callable[[dict[str, Any]], Coroutine],
        input_queue: asyncio.Queue,
    ) -> None:
        self._send = send_callback
        self._input_queue = input_queue
        self._clean_output: str | None = None  # set by on_clean_output_available()
        # Latest rendered prompt data, kept in sync by ConversationService._on_new_turn
        # so that intermediate widget interactions can carry inline prompt_data.
        # Used by asend_response to populate pending_input messages without a REST round-trip.
        self._last_prompt_data: dict[str, Any] | None = None

    @property
    def clean_output(self) -> str | None:
        """Clean final output from --output-file, if available."""
        return self._clean_output

    _graph_send_failures: int = 0
    _graph_send_disabled: bool = False

    async def send_graph_event(self, event: Any, task_id: str = "") -> None:
        """Send a graph visualization event to the frontend.

        Dispatches GraphTopologyEvent, NodeStatusEvent, NodeStreamEvent to the
        appropriate WS message type. Wrapped in try/except with circuit breaker
        so visualization failures never abort computation.
        """
        if self._graph_send_disabled:
            return
        import logging as _log
        _logger = _log.getLogger(__name__)
        from agent_foundation.common.inferencers.graph_events import (
            GraphTopologyEvent, NodeStatusEvent, NodeStreamEvent, GraphReconcileEvent,
        )
        if isinstance(event, GraphTopologyEvent):
            msg: dict[str, Any] = {
                "type": "graph_topology",
                "task_id": task_id,
                "nodes": event.nodes,
                "edges": event.edges,
                "layout": event.layout,
            }
            if event.parent_node_id:
                msg["parent_node_id"] = event.parent_node_id
            if event.version:
                msg["version"] = event.version
            # Root topology resets the circuit breaker
            if not event.parent_node_id:
                self._graph_send_disabled = False
                self._graph_send_failures = 0
        elif isinstance(event, NodeStatusEvent):
            msg = {
                "type": "node_status",
                "task_id": task_id,
                "node_id": event.node_id,
                "status": event.status,
                "label": event.label,
                "error": event.error,
                "timestamp": event.timestamp,
                "output_path": event.output_path,
            }
        elif isinstance(event, NodeStreamEvent):
            msg = {
                "type": "node_stream",
                "task_id": task_id,
                "node_id": event.node_id,
                "content": event.content,
                "is_final": event.is_final,
            }
        elif isinstance(event, GraphReconcileEvent):
            msg = {
                "type": "graph_reconcile",
                "task_id": task_id,
                "nodes": event.node_statuses,
            }
        else:
            return
        try:
            await self._send(msg)
            self._graph_send_failures = 0
        except Exception as exc:
            self._graph_send_failures += 1
            if self._graph_send_failures >= 3:
                self._graph_send_disabled = True
                _logger.warning(
                    "[WS] Graph events disabled after %d consecutive failures: %s",
                    self._graph_send_failures, exc,
                )
            else:
                _logger.debug("[WS] send_graph_event failed (%d/3): %s", self._graph_send_failures, exc)

    async def on_clean_output_available(self, clean_output: str) -> None:
        """Called after streaming completes when a cleaner final output is available.

        Stores the clean output and sends a 'stream_correction' WS event so the
        frontend can replace the noisy streamed display with the exact LLM text.
        This fires before message_end, giving the frontend time to update the
        streaming bubble before it's committed as a message.

        Args:
            clean_output: Clean LLM output from --output-file (no TUI noise,
                code fences intact, no terminal-width line wrapping).
        """
        self._clean_output = clean_output
        await self._send({
            "type": "stream_correction",
            "content": clean_output,
        })

    async def stream_token_batches(
        self,
        token_stream: AsyncIterator[tuple[str, dict]],
        session_id: str,
        batch_interval_ms: float = 50.0,
        task_id: str | None = None,
        send_stream_end: bool = True,
        turn_number: int | None = None,
    ) -> str:
        """Accumulate tokens from an async generator, flush as batched WS messages.

        Returns the full concatenated response text.
        """
        full_text: list[str] = []
        batch: list[str] = []
        last_flush = time.monotonic()

        async for chunk, metadata in token_stream:
            batch.append(chunk)
            full_text.append(chunk)
            if (time.monotonic() - last_flush) * 1000 >= batch_interval_ms:
                combined = "".join(batch)
                msg = {
                    "type": "token",
                    "content": combined,
                    "metadata": {"agent_name": "Orchestrator"},
                }
                if task_id:
                    msg["task_id"] = task_id
                await self._send(msg)
                batch = []
                last_flush = time.monotonic()

        if batch:
            combined = "".join(batch)
            msg = {
                "type": "token",
                "content": combined,
                "metadata": {"agent_name": "Orchestrator"},
            }
            if task_id:
                msg["task_id"] = task_id
            await self._send(msg)

        return "".join(full_text)

    async def send_task_status(
        self,
        task_id: str,
        status: str,
        request: str = "",
        tool_name: str = "",
        error: str = "",
    ) -> None:
        """Notify the frontend of task lifecycle events (starting/running/completed/error).

        Creates or updates a task subtab in the UI.
        """
        msg: dict[str, Any] = {
            "type": "task_status",
            "task_id": task_id,
            "status": status,
        }
        if request:
            msg["request"] = request
        if tool_name:
            msg["tool_name"] = tool_name
        if error:
            msg["error"] = error
        await self._send(msg)

    async def send_turn_boundary(
        self,
        session_id: str,
        turn_number: int = 0,
        cache_folder: str = "",
    ) -> None:
        """Signal a turn boundary (agentic loop iteration boundary)."""
        await self._send({
            "type": "turn_boundary",
            "turn_number": turn_number,
        })

    @staticmethod
    def _sanitize_for_json(value: Any) -> Any:
        """Recursively make a value JSON-serializable.

        Mirrors `ConversationService._sanitize_feed` semantics but operates on
        any nested value (the top-level prompt_data dict contains both safe
        strings/dicts AND a `template_feed` dict that may contain workflow
        objects like SOP, SOPPhase, StateGraphTracker — those come from the
        Jinja2 template's prior_context spread).

        For each value:
          - Try `json.dumps(value)` — if it succeeds, keep as-is (preserves
            structure for the UI's prompt viewer).
          - Otherwise: if dict, recurse per key; if list/tuple, recurse per
            element; else fall back to `str(value)`.

        This is the same pattern used at multiple existing sites in the
        codebase (`_sanitize_feed`, `get_last_prompt_data`) — we centralize it
        here so the WS transport always produces serializable payloads
        regardless of what upstream code passes.
        """
        import json

        try:
            json.dumps(value)
            return value
        except (TypeError, ValueError):
            pass

        if isinstance(value, dict):
            return {
                k: WebSocketInteractive._sanitize_for_json(v)
                for k, v in value.items()
                if not (isinstance(k, str) and k.startswith("_"))  # drop private keys
            }
        if isinstance(value, (list, tuple)):
            return [WebSocketInteractive._sanitize_for_json(v) for v in value]
        try:
            return str(value)
        except Exception:
            return f"<non-serializable: {type(value).__name__}>"

    async def asend_response(
        self,
        response: Any,
        flag: Any = None,
        **kwargs: Any,
    ) -> None:
        """Send a conversation tool prompt (confirmation, clarification, etc.)."""
        import logging as _logging
        _log = _logging.getLogger(__name__)
        input_mode = kwargs.get("input_mode")
        msg: dict[str, Any] = {
            "type": "pending_input",
            "content": str(response),
        }
        if input_mode is not None:
            mode_dict = (
                input_mode.to_dict()
                if hasattr(input_mode, "to_dict")
                else input_mode
            )
            msg["input_mode"] = mode_dict
            _log.info("[asend_response] input_mode.mode=%s metadata=%s",
                      mode_dict.get("mode"), mode_dict.get("metadata"))
        else:
            _log.info("[asend_response] no input_mode (free_text fallback)")

        # Inline prompt_data so the UI's "View Prompt" button on the preamble
        # widget message has the rendered prompt available without a REST fetch.
        # ConversationalInferencer._handle_conversation_tool passes prompt_data=
        # explicitly (carrying the raw _last_template_feed which may contain
        # non-JSON-serializable objects like SOP, SOPPhase, StateGraphTracker
        # from the workflow's prior_context); otherwise we fall back to the
        # last-known value cached on this interactive (kept fresh by
        # ConversationService._on_new_turn, which IS already sanitized via
        # _sanitize_feed).
        #
        # We must sanitize before serializing — without it, json.dumps() raises
        # "Object of type SOP is not JSON serializable", send_safe drops the
        # entire pending_input message, and the agentic loop hangs at
        # aget_input() waiting for a user response that can never arrive
        # because the UI never received the widget request.
        prompt_data = kwargs.get("prompt_data") or self._last_prompt_data
        if prompt_data:
            msg["prompt_data"] = self._sanitize_for_json(prompt_data)

        await self._send(msg)

    async def aget_input(self) -> Any:
        """Wait for user input from the WebSocket (fed by incoming messages)."""
        return await self._input_queue.get()


class TaskWebSocketInteractive(WebSocketInteractive):
    """WebSocketInteractive subclass for background task streaming.

    Automatically injects `task_id` into all token messages, so the frontend
    routes them to the task panel instead of the conversation stream.
    The create_role/role_setup executors use BreakdownThenAggregateInferencer
    which doesn't call stream_token_batches directly — this subclass is provided
    for future executors that do stream through interactive.
    """

    def __init__(
        self,
        send_callback: Callable[[dict[str, Any]], Coroutine],
        input_queue: asyncio.Queue,
        *,
        task_id: str,
    ) -> None:
        super().__init__(send_callback, input_queue)
        self._task_id = task_id

    async def stream_token_batches(
        self,
        token_stream: AsyncIterator[tuple[str, dict]],
        session_id: str,
        **kwargs: Any,
    ) -> str:
        """Override to inject task_id into all token messages."""
        return await super().stream_token_batches(
            token_stream,
            session_id,
            task_id=self._task_id,
            **kwargs,
        )
