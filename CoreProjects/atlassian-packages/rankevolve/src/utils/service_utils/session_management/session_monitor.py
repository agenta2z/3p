"""Generic session monitor with periodic cleanup and extensible hooks.

Provides a base monitor that handles periodic idle-session cleanup and
exposes an ``on_monitoring_cycle()`` hook for service-specific checks
(e.g. status polling, lazy resource creation).
"""
import time


class SessionMonitor:
    """Monitors sessions with periodic cleanup and extensible hooks.

    The monitor is designed to be called periodically from a service loop.
    It provides:

    - **periodic_cleanup()**: Cleans up idle sessions via the session manager.
    - **on_monitoring_cycle()**: Override hook for service-specific monitoring.
    - **run_monitoring_cycle()**: Runs the hook then periodic cleanup.

    All errors in ``periodic_cleanup`` are caught and printed to prevent
    monitoring failures from affecting the service.

    Subclasses override ``on_monitoring_cycle()`` to add checks like
    agent status detection, lazy creation, etc.
    """

    def __init__(self, session_manager, cleanup_check_interval: int = 300):
        """Initialize the session monitor.

        Args:
            session_manager: SessionManager instance for accessing sessions.
            cleanup_check_interval: Seconds between cleanup checks.
        """
        self._session_manager = session_manager
        self._cleanup_check_interval = cleanup_check_interval
        self._last_cleanup_time = time.time()

    def on_monitoring_cycle(self) -> None:
        """Override for service-specific monitoring checks.

        Called at the start of each ``run_monitoring_cycle()``.
        Default implementation is a no-op.
        """

    def periodic_cleanup(self) -> None:
        """Perform periodic cleanup of idle sessions.

        Triggers ``session_manager.cleanup_idle_sessions()`` if the
        cleanup interval has elapsed since the last run.
        """
        try:
            current_time = time.time()
            elapsed = current_time - self._last_cleanup_time

            if elapsed >= self._cleanup_check_interval:
                self._session_manager.cleanup_idle_sessions()
                self._last_cleanup_time = current_time

        except Exception as e:
            print(f"Error in periodic_cleanup: {e}")

    def run_monitoring_cycle(self) -> None:
        """Run one full monitoring cycle.

        Calls ``on_monitoring_cycle()`` (service-specific checks) followed
        by ``periodic_cleanup()`` (idle session removal).
        """
        self.on_monitoring_cycle()
        self.periodic_cleanup()
