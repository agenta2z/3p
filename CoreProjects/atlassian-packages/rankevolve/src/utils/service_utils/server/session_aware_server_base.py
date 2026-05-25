# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.

"""Abstract session-aware server base using template method pattern.

Subclasses implement _create_session_manager(), _create_message_handlers(),
and optionally override hooks (_on_startup, _on_shutdown, _create_session_monitor).
"""

from __future__ import annotations

import asyncio
import logging
import signal
import time
from abc import ABC, abstractmethod
from pathlib import Path

from rankevolve.src.utils.service_utils.queue_service.storage_based_queue_service import (
    StorageBasedQueueService,
)
from rankevolve.src.utils.service_utils.server.base_config import BaseServiceConfig
from rankevolve.src.utils.service_utils.server.base_message_handlers import (
    AbstractMessageHandlers,
)
from rankevolve.src.utils.service_utils.server.base_queue_manager import QueueManager
from rankevolve.src.utils.service_utils.session_management.session_manager import (
    SessionManager,
)
from rankevolve.src.utils.service_utils.session_management.session_monitor import (
    SessionMonitor,
)

logger = logging.getLogger(__name__)


class SessionAwareServerBase(ABC):
    """Abstract base for session-aware, queue-based agent services.

    Template method: subclasses implement factory methods for the session
    manager and message handlers. The base class orchestrates initialization,
    main loop, and shutdown.
    """

    def __init__(self, config: BaseServiceConfig) -> None:
        self._config = config
        self._running = False
        self._queue_manager: QueueManager | None = None
        self._queue_service: StorageBasedQueueService | None = None
        self._session_manager: SessionManager | None = None
        self._handlers: AbstractMessageHandlers | None = None
        self._session_monitor: SessionMonitor | None = None

    # ── Abstract factory methods ──────────────────────────────────────

    @abstractmethod
    def _create_session_manager(
        self, queue_service: StorageBasedQueueService, log_dir: Path
    ) -> SessionManager:
        """Create and return the concrete session manager."""
        ...

    @abstractmethod
    def _create_message_handlers(
        self,
        session_manager: SessionManager,
        queue_service: StorageBasedQueueService,
        tasks_dir: Path | None = None,
    ) -> AbstractMessageHandlers:
        """Create and return the concrete message handlers."""
        ...

    # ── Optional hooks ────────────────────────────────────────────────

    def _create_session_monitor(
        self, session_manager: SessionManager
    ) -> SessionMonitor:
        """Create session monitor. Override for custom monitoring."""
        return SessionMonitor(
            session_manager,
            cleanup_check_interval=self._config.cleanup_check_interval,
        )

    def _on_startup(self) -> None:
        """Hook called after all components are initialized, before main loop."""

    def _on_shutdown(self) -> None:
        """Hook called during graceful shutdown, after main loop exits."""

    # ── Main entry point ──────────────────────────────────────────────

    def run(self) -> None:
        """Initialize components and run the main loop."""
        self._setup()
        try:
            asyncio.run(self._async_main_loop())
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        finally:
            self._teardown()

    def _setup(self) -> None:
        """Initialize logging, queues, and components."""
        # Initialize queue manager (creates server directory structure)
        self._queue_manager = QueueManager(self._config.queue_root_path)
        self._queue_service = self._queue_manager.initialize(
            server_dir=self._config.server_dir,
        )

        # Set up per-run logging in the server directory
        run_log_dir = self._queue_manager.get_run_log_dir()
        logging.basicConfig(
            level=logging.DEBUG if self._config.debug_mode else logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(run_log_dir / "server.log"),
            ],
        )

        # Create control queues
        self._queue_manager.create_queues(
            [
                self._config.server_control_queue_id,
                self._config.client_control_queue_id,
            ]
        )

        queue_root = self._queue_manager.get_queue_root_path()
        server_dir = self._queue_manager.get_server_dir()
        sessions_dir = self._queue_manager.get_sessions_dir()

        logger.info("Server dir: %s", server_dir)
        logger.info("Queue root: %s", queue_root)
        logger.info("Run log dir: %s", run_log_dir)
        logger.info("Sessions dir: %s", sessions_dir)

        # Create components via template methods
        self._session_manager = self._create_session_manager(
            self._queue_service, sessions_dir
        )

        # Restore sessions from previous run if resuming
        if self._config.server_dir:
            self._session_manager.restore_sessions(sessions_dir)

        # Round 9: tasks_dir param dropped — per-session layout means each
        # task launcher derives its own dir from session.session_tasks_dir.
        # The legacy ``tasks_dir`` kwarg in the abstract _create_message_handlers
        # signature is kept for backwards compatibility (overrides may still
        # accept it), but we pass None to make the deprecation explicit.
        self._handlers = self._create_message_handlers(
            self._session_manager, self._queue_service, None
        )
        self._session_monitor = self._create_session_monitor(self._session_manager)

        self._on_startup()
        self._running = True

        logger.info("Server started. Queue root: %s", queue_root)
        # Sentinel for run.sh orchestrator to discover the queue root path.
        # Printed to stdout (logging goes to stderr) so it can be reliably parsed.
        print(f"QUEUE_ROOT={queue_root}", flush=True)

    def _teardown(self) -> None:
        """Clean up resources."""
        self._running = False
        self._on_shutdown()

        if self._queue_manager:
            self._queue_manager.close()

        logger.info("Server shut down.")

    async def _async_main_loop(self) -> None:
        """Async main loop: poll control queue, poll sessions, monitor."""
        loop = asyncio.get_running_loop()

        # Install signal handlers
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._signal_handler)

        session_tasks: dict[str, asyncio.Task] = {}

        while self._running:
            # Check for new session registrations on control queue
            ctrl_msg = await asyncio.to_thread(
                self._queue_service.get,
                self._config.server_control_queue_id,
                blocking=False,
            )
            if ctrl_msg:
                self._handle_session_registration(ctrl_msg)

            # Poll each active session's input queue
            if self._session_manager:
                active_ids = set()
                for (
                    session_id,
                    session,
                ) in self._session_manager.get_all_sessions().items():
                    active_ids.add(session_id)
                    task = session_tasks.get(session_id)
                    if task is None or task.done():
                        session_tasks[session_id] = asyncio.create_task(
                            self._poll_session(session_id)
                        )
                # Prune tasks for sessions that no longer exist
                for stale_id in set(session_tasks) - active_ids:
                    del session_tasks[stale_id]

            # Monitoring
            if self._session_monitor:
                self._session_monitor.run_monitoring_cycle()

            await asyncio.sleep(self._config.poll_interval)

    async def _poll_session(self, session_id: str) -> None:
        """Poll a single session's input queue and dispatch."""
        queue_id = f"{self._config.input_queue_id}_{session_id}"
        message = await asyncio.to_thread(
            self._queue_service.get, queue_id, blocking=False
        )
        if not message or not self._handlers:
            return

        # Update last_active so idle-timeout cleanup works correctly
        session = self._session_manager.get(session_id)
        if session:
            session.info.last_active = time.time()

        # Guard: don't start a new conversation while one is already running.
        # Only applies to conversation-triggering types (chat_message,
        # slash_command). Other types (ping, task_cancel, config_query)
        # must proceed immediately even during active conversations.
        msg_type = message.get("type", "")
        if msg_type in ("chat_message", "slash_command"):
            conv = getattr(session, "active_conversation", None) if session else None
            if conv is not None and not conv.done():
                # Re-queue: message stays for the next poll cycle
                await asyncio.to_thread(
                    self._queue_service.put, queue_id, message
                )
                return

        # Dispatch directly in the event loop thread (not via to_thread).
        # Handlers are fast sync routing functions that schedule async tasks
        # via asyncio.create_task(), which requires a running event loop.
        # Running dispatch in a worker thread causes RuntimeError because
        # worker threads have no event loop.
        if session and hasattr(session, "processing_lock"):
            async with session.processing_lock:
                self._handlers.dispatch(message)
        else:
            self._handlers.dispatch(message)

    def _handle_session_registration(self, msg: dict) -> None:
        """Handle register/deregister messages from the control queue."""
        msg_type = msg.get("type", "")
        session_id = msg.get("session_id")
        if not session_id or not self._session_manager:
            return

        if msg_type == "register_session":
            session_type = msg.get("session_type", "default")
            self._session_manager.get_or_create(session_id, session_type)
            logger.info("Session registered: %s (type=%s)", session_id, session_type)

        elif msg_type == "deregister_session":
            # Don't destroy the session — just log. The session persists in
            # memory so it can be reused when the same WebUI session reconnects
            # (page refresh, tab switch, network hiccup). Actual cleanup
            # happens via idle timeout (default 30 min).
            logger.info("Session deregistered: %s (session preserved for reconnect)", session_id)

    def _signal_handler(self) -> None:
        """Handle shutdown signals."""
        logger.info("Shutdown signal received")
        self._running = False
