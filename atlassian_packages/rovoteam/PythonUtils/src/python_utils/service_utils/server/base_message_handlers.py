

"""Abstract message handler framework for session-aware services."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable

from python_utils.service_utils.session_management.session_manager import (
    SessionManager,
)


class AbstractMessageHandlers(ABC):
    """Abstract base for message dispatch.

    Provides a standard handler map (agent_control) merged with
    service-specific handlers from _get_handler_map().
    """

    def __init__(self, session_manager: SessionManager) -> None:
        self._session_manager = session_manager

    @abstractmethod
    def _get_handler_map(self) -> dict[str, Callable]:
        """Return service-specific message type -> handler mapping."""
        ...

    def dispatch(self, message: dict[str, Any]) -> Any:
        """Route message['type'] to handler via merged standard + custom handler map."""
        all_handlers = {**self._get_standard_handlers(), **self._get_handler_map()}
        msg_type = message.get("type")
        handler = all_handlers.get(msg_type)
        if handler:
            return handler(message)
        elif msg_type not in ("ping", "pong", "heartbeat"):
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "dispatch: no handler for type=%s (available: %s)",
                msg_type, list(all_handlers.keys()),
            )

    def _get_standard_handlers(self) -> dict[str, Callable]:
        """Standard handlers provided by the base."""
        return {"agent_control": self._handle_agent_control}

    def _handle_agent_control(self, message: dict[str, Any]) -> None:
        """Standard agent control — stop/pause/resume via session.interactive.

        Message format: {type: "agent_control", message: {session_id, control: "stop"|"pause"|"continue"|"step"}}
        """
        payload = message.get("message", {})
        session_id = payload.get("session_id")
        control = payload.get("control")
        session = self._session_manager.get(session_id)
        if session and hasattr(session, "interactive") and session.interactive:
            method_name = {"continue": "resume"}.get(control, control)
            if hasattr(session.interactive, method_name):
                getattr(session.interactive, method_name)()
