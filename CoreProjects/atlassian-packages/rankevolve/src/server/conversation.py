# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict

from __future__ import annotations

from rankevolve.src.server.schema import ChatMessage, MessageMetadata


class Conversation:
    """Manages conversation history for multi-turn chat."""

    def __init__(self, system_prompt: str) -> None:
        self.system_prompt: str = system_prompt
        self.messages: list[ChatMessage] = []

    def add_user_message(self, content: str) -> ChatMessage:
        msg = ChatMessage(role="user", content=content)
        self.messages.append(msg)
        return msg

    def add_assistant_message(
        self,
        content: str,
        metadata: MessageMetadata | None = None,
    ) -> ChatMessage:
        msg = ChatMessage(role="assistant", content=content, metadata=metadata)
        self.messages.append(msg)
        return msg

    def add_tool_call_message(
        self,
        tool_name: str,
        arguments: dict,
    ) -> ChatMessage:
        """Record that the assistant invoked a tool."""
        content = f"[Tool Call: {tool_name}] {arguments}"
        metadata = MessageMetadata(is_tool_call=True, tool_name=tool_name)
        msg = ChatMessage(role="assistant", content=content, metadata=metadata)
        self.messages.append(msg)
        return msg

    def add_tool_result_message(
        self,
        tool_name: str,
        result: str,
    ) -> ChatMessage:
        """Record the result of a tool execution.

        Tagged with is_auto_advance=True so the frontend hides this row in
        the chat transcript — it's a protocol echo, not a real user turn.
        """
        content = f"[Tool Result: {tool_name}] {result}"
        metadata = MessageMetadata(tool_name=tool_name, is_auto_advance=True)
        msg = ChatMessage(role="user", content=content, metadata=metadata)
        self.messages.append(msg)
        return msg

    def add_auto_advance_message(self, content: str) -> ChatMessage:
        """Add an auto-advance message (hidden from user in UI).

        Used when an async tool completes and the system needs to trigger
        a conversation turn to advance the workflow. Tagged with metadata
        so the frontend can identify and hide it.
        """
        metadata = MessageMetadata(is_auto_advance=True)
        msg = ChatMessage(role="user", content=content, metadata=metadata)
        self.messages.append(msg)
        return msg

    def add_widget_response(self, content: str) -> ChatMessage:
        """Record a `[Collected from conversation widget]` echo.

        Same shape as add_user_message but tagged with is_auto_advance=True
        so the frontend hides it from the chat transcript — it's a protocol
        echo of widget submission output, not a real user turn.
        """
        metadata = MessageMetadata(is_auto_advance=True)
        msg = ChatMessage(role="user", content=content, metadata=metadata)
        self.messages.append(msg)
        return msg

    def add_widget_response_card(
        self,
        widget_type: str,
        widget_data: dict,
        content: str = "",
    ) -> ChatMessage:
        """Persist an approved/submitted widget as a visible transcript row.

        Distinct from add_widget_response, which records the LLM-protocol
        echo tagged is_auto_advance=True. This row carries the structured
        fields (prompt, view, view_label, plus per-widget extras) the
        renderer needs so the "flat" approved card survives session resume.
        UI-only — excluded from get_api_messages so it never reaches the LLM.
        """
        metadata = MessageMetadata(
            widget_type=widget_type,
            widget_data=widget_data,
        )
        msg = ChatMessage(role="widget_response", content=content, metadata=metadata)
        self.messages.append(msg)
        return msg

    def add_task_ref(
        self,
        task_id: str,
        label: str,
        tool_name: str,
        multi_task_id: str | None = None,
        status: str = "queued",
    ) -> ChatMessage:
        """Record a task launch as a chronological event for UI replay.

        Persists alongside user/assistant turns so resume restores chip
        chips at the exact position they appeared during the live run. The
        task_ref role is UI-only and excluded from get_api_messages — it
        must NOT be sent to the LLM.

        F4: ``status`` (default ``"queued"``) is persisted into
        ``metadata.task_status``. Subsequent transitions go through
        ``update_task_ref_status``. The React reducer reads this value on
        session-load so disconnected-then-reconnected clients see the
        correct chip status.
        """
        metadata = MessageMetadata(
            is_task_ref=True, tool_name=tool_name, task_status=status
        )
        msg = ChatMessage(
            role="task_ref",
            content=label,
            metadata=metadata,
            task_id=task_id,
            multi_task_id=multi_task_id,
        )
        self.messages.append(msg)
        return msg

    def update_task_ref_status(self, task_id: str, status: str) -> bool:
        """F4: update the persisted ``metadata.task_status`` on the latest
        ``role="task_ref"`` row whose ``task_id`` matches.

        Called by ``tool_executor`` at every ``task_status`` emit site so the
        on-disk state mirrors what live WS clients see. Returns True iff a
        matching row was found and updated. Best-effort: if no matching row
        exists (e.g., status update fires before the task_ref was added),
        returns False — caller decides whether to log/skip.

        Latest-first scan because most callers update the most recently
        created task_ref; this short-circuits common cases without scanning
        the entire conversation.
        """
        for msg in reversed(self.messages):
            if msg.role == "task_ref" and msg.task_id == task_id:
                if msg.metadata is None:
                    msg.metadata = MessageMetadata(is_task_ref=True)
                msg.metadata.task_status = status
                return True
        return False

    def get_api_messages(self) -> list[dict[str, str]]:
        """Convert history to API format (list of role/content dicts).

        Excludes task_ref and widget_response rows — both are UI-only event
        markers and would be unknown roles to the LLM API. This is the
        chokepoint for LLM exposure; every consumer that feeds
        Anthropic/OpenAI should route through here rather than iterating
        self.messages directly.
        """
        ui_only_roles = {"task_ref", "widget_response"}
        return [m.to_api_dict() for m in self.messages if m.role not in ui_only_roles]

    def clear(self) -> None:
        self.messages.clear()

    def to_dict(self) -> dict:
        """Serialize conversation state to a JSON-compatible dictionary."""
        return {
            "system_prompt": self.system_prompt,
            "messages": [m.to_dict() for m in self.messages],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Conversation":
        """Deserialize from a dictionary."""
        conv = cls(system_prompt=data["system_prompt"])
        conv.messages = [ChatMessage.from_dict(m) for m in data.get("messages", [])]
        return conv
