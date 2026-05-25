# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.

"""RankEvolve session monitor — checks for completed tasks."""

from __future__ import annotations

import logging

from rankevolve.src.utils.service_utils.session_management.session_monitor import (
    SessionMonitor,
)

from .session import RankEvolveSession

logger = logging.getLogger(__name__)


class RankEvolveSessionMonitor(SessionMonitor):
    """Extends SessionMonitor with RankEvolve-specific monitoring.

    Checks for completed async tasks and cleans up finished task references.
    """

    def on_monitoring_cycle(self) -> None:
        """Check for completed async tasks."""
        for session_id, session in self._session_manager.get_all_sessions().items():
            if isinstance(session, RankEvolveSession):
                if session.active_task and session.active_task.done():
                    exc = session.active_task.exception() if not session.active_task.cancelled() else None
                    if exc:
                        logger.error(
                            "Task failed for session %s: %s", session_id, exc
                        )
                    session.active_task = None
