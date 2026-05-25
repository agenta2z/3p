# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.

"""RankEvolve concrete server service."""

from __future__ import annotations

import logging
from pathlib import Path

from rankevolve.src.utils.service_utils.queue_service.storage_based_queue_service import (
    StorageBasedQueueService,
)
from rankevolve.src.utils.service_utils.server.base_message_handlers import (
    AbstractMessageHandlers,
)
from rankevolve.src.utils.service_utils.server.session_aware_server_base import (
    SessionAwareServerBase,
)
from rankevolve.src.utils.service_utils.session_management.session_manager import (
    SessionManager,
)
from rankevolve.src.utils.service_utils.session_management.session_monitor import (
    SessionMonitor,
)

from .config import RankEvolveServiceConfig
from .message_handlers import RankEvolveMessageHandlers
from .session_manager import RankEvolveSessionManager
from .session_monitor import RankEvolveSessionMonitor

logger = logging.getLogger(__name__)


class RankEvolveAgentService(SessionAwareServerBase):
    """Concrete RankEvolve server using the SessionAwareServerBase template."""

    def __init__(self, config: RankEvolveServiceConfig) -> None:
        super().__init__(config)
        self._re_config = config

    def _create_session_manager(
        self,
        queue_service: StorageBasedQueueService,
        log_dir: Path,
    ) -> SessionManager:
        return RankEvolveSessionManager(
            queue_service=queue_service,
            service_config=self._re_config,
            service_log_dir=log_dir,
            session_idle_timeout=self._re_config.session_idle_timeout,
        )

    def _create_message_handlers(
        self,
        session_manager: SessionManager,
        queue_service: StorageBasedQueueService,
        tasks_dir: Path | None = None,
    ) -> AbstractMessageHandlers:
        # Per-session task workspace layout: tasks now live under
        # <server>/sessions/<session>/tasks/, derived per-call from
        # session.session_tasks_dir. The legacy global `tasks_dir` parameter
        # accepted by the abstract base class is intentionally ignored here;
        # kept in the signature for backwards compatibility.
        del tasks_dir  # noqa: F841 — drop reference to unused legacy plumbing
        return RankEvolveMessageHandlers(session_manager, queue_service)

    def _create_session_monitor(
        self, session_manager: SessionManager
    ) -> SessionMonitor:
        return RankEvolveSessionMonitor(
            session_manager,
            cleanup_check_interval=self._re_config.cleanup_check_interval,
        )

    def _on_startup(self) -> None:
        logger.info(
            "RankEvolve server started (provider=%s, model=%s)",
            self._re_config.provider,
            self._re_config.model,
        )
        self._write_default_welcome_message()

    def _write_default_welcome_message(self) -> None:
        """Write the default welcome message to _runtime/ so the WebUI can read it.

        The WebUI backend (config_routes) has no Buck dependency on prompt_templates,
        so it cannot load the default template via importlib.resources. Instead, the
        server (which does have the dependency) writes it to the runtime directory on
        startup. This file is never overwritten if it already exists.
        """
        if not self._queue_manager:
            return
        server_dir = self._queue_manager.get_server_dir()
        runtime_dir = (
            server_dir.parent.parent
        )  # _runtime/servers/server_XXX -> _runtime/
        default_path = runtime_dir / "welcome_message_default.md"
        if default_path.is_file():
            return  # Already written (previous run or restart)
        try:
            from importlib import resources as importlib_resources

            pkg = importlib_resources.files("rankevolve.src.resources.prompt_templates")
            content = pkg.joinpath("welcome_message", "default.md").read_text(
                encoding="utf-8"
            )
            runtime_dir.mkdir(parents=True, exist_ok=True)
            default_path.write_text(content, encoding="utf-8")
            logger.info("Wrote default welcome message to %s", default_path)
        except Exception as e:
            logger.warning("Could not write default welcome message: %s", e)

    def _on_shutdown(self) -> None:
        logger.info("RankEvolve server shutting down")
