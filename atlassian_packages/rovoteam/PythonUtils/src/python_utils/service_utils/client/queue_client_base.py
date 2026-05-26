

"""Abstract base for queue-based clients that connect to a SessionAwareServer.

Handles session registration/deregistration, heartbeat sending, server
liveness detection, and response polling.  Concrete subclasses decide how
to present responses (CLI console, WebSocket callback, etc.).
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from abc import ABC
from typing import Any

from python_utils.service_utils.queue_service.storage_based_queue_service import (
    StorageBasedQueueService,
)

logger = logging.getLogger(__name__)


class QueueClientBase(ABC):
    """Abstract base for queue-based clients.

    Manages:
    - Session registration / deregistration on the server control queue
    - Per-session input & response queue IDs
    - Periodic heartbeat sending (so the server knows we're alive)
    - Server liveness tracking (based on last response timestamp)

    Subclasses use ``send_message()`` and ``poll_one_response()`` to
    communicate, and call ``_maybe_send_heartbeat()`` inside their
    polling loops.
    """

    def __init__(
        self,
        queue_root_path: str,
        session_id: str | None = None,
        session_type: str = "default",
        heartbeat_interval: float = 30.0,
        server_timeout: float = 90.0,
    ) -> None:
        self._session_id = session_id or str(uuid.uuid4())[:8]
        self._session_type = session_type
        self._queue_service = StorageBasedQueueService(root_path=queue_root_path)
        self._input_queue_id = f"user_input_{self._session_id}"
        self._response_queue_id = f"agent_response_{self._session_id}"

        # Heartbeat / liveness
        self._heartbeat_interval = heartbeat_interval
        self._server_timeout = server_timeout
        self._last_heartbeat_sent: float = 0.0
        self._last_server_response: float = time.time()

        # Register with the server
        self._register()

    # ── Properties ────────────────────────────────────────────────────

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def queue_service(self) -> StorageBasedQueueService:
        return self._queue_service

    # ── Registration ──────────────────────────────────────────────────

    def _register(self) -> None:
        """Send a register_session message to the server control queue."""
        self._queue_service.put("server_control", {
            "type": "register_session",
            "session_id": self._session_id,
            "session_type": self._session_type,
        })
        logger.info(
            "Registered session %s (type=%s)", self._session_id, self._session_type
        )

    def _deregister(self) -> None:
        """Send a deregister_session message so the server cleans up immediately."""
        self._queue_service.put("server_control", {
            "type": "deregister_session",
            "session_id": self._session_id,
        })
        logger.info("Deregistered session %s", self._session_id)

    # ── Messaging ─────────────────────────────────────────────────────

    def send_message(
        self,
        msg_type: str,
        content: str = "",
        **extra: Any,
    ) -> None:
        """Put a message on this session's input queue.

        Args:
            msg_type: Message type (e.g. "chat_message", "slash_command").
            content: Message body.
            **extra: Additional fields merged into the message dict.
        """
        self._queue_service.put(self._input_queue_id, {
            "type": msg_type,
            "content": content,
            "session_id": self._session_id,
            **extra,
        })

    async def poll_one_response(self) -> dict[str, Any] | None:
        """Poll the response queue for one message (non-blocking).

        Updates ``_last_server_response`` whenever a message is received,
        which feeds ``is_server_alive()``.

        Returns:
            The response dict, or None if the queue is empty.
        """
        resp = await asyncio.to_thread(
            self._queue_service.get,
            self._response_queue_id,
            blocking=False,
        )
        if resp is not None:
            self._last_server_response = time.time()
        return resp

    # ── Heartbeat / liveness ──────────────────────────────────────────

    def _maybe_send_heartbeat(self) -> None:
        """Send a ping if ``heartbeat_interval`` seconds have elapsed.

        Call this inside your polling loop.  The server's ``_handle_ping``
        responds with a pong, which ``poll_one_response`` records as proof
        of server liveness.
        """
        now = time.time()
        if now - self._last_heartbeat_sent >= self._heartbeat_interval:
            self._queue_service.put(self._input_queue_id, {
                "type": "ping",
                "session_id": self._session_id,
            })
            self._last_heartbeat_sent = now

    def is_server_alive(self) -> bool:
        """Return True if we've heard from the server within ``server_timeout``."""
        return (time.time() - self._last_server_response) < self._server_timeout

    # ── Lifecycle ─────────────────────────────────────────────────────

    def close(self) -> None:
        """Deregister from the server and close the queue service."""
        try:
            self._deregister()
        except Exception:
            logger.debug("Failed to deregister session %s", self._session_id)
        self._queue_service.close()
