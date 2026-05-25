"""Thread-safe session lifecycle management.

Provides SessionManager, an abstract Debuggable that manages sessions
including creation, updates, cleanup, and idle detection.

Subclasses implement ``_create_session()`` to build service-specific session
objects and optionally override ``_on_before_cleanup()`` for custom teardown.
"""
import abc
import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, ClassVar, Dict, Optional

from attr import attrs, attrib
from rich_python_utils.common_objects.debuggable import Debuggable

from .session_base import SessionBase


@attrs(slots=False)
class SessionManager(Debuggable, abc.ABC):
    """Abstract session manager with thread-safe lifecycle operations.

    Extends Debuggable for management-level logging (session creation,
    cleanup, idle detection). Per-session logging goes through each
    session's own Debuggable loggers.

    All operations are thread-safe using a reentrant lock (RLock) to support
    nested calls and concurrent access from multiple threads.

    Subclass contract:
        - Implement ``_create_session()`` to build the concrete session.
        - Override ``_on_before_cleanup()`` for service-specific teardown.
        - Set ``_RUNTIME_FIELDS`` for fields routed to session properties
          (vs. ``session.info``).
    """
    _session_idle_timeout: int = attrib(kw_only=True, default=1800)
    _service_log_dir: Path = attrib(kw_only=True, default=None)

    # Internal state (not in constructor)
    _sessions: Dict[str, SessionBase] = attrib(init=False, factory=dict)
    _lock: threading.RLock = attrib(init=False, factory=threading.RLock)

    # Subclass overrides: fields routed to session properties (not session.info)
    _RUNTIME_FIELDS: ClassVar[frozenset] = frozenset()

    # ------------------------------------------------------------------
    # Log type hooks (override to use service-specific log type enums)
    # ------------------------------------------------------------------

    def _get_log_type_session_management(self) -> str:
        """Return the log type string for session management events."""
        return 'SessionManagement'

    def _get_log_type_session_cleanup(self) -> str:
        """Return the log type string for session cleanup events."""
        return 'SessionCleanup'

    # ------------------------------------------------------------------
    # Abstract / hook methods
    # ------------------------------------------------------------------

    @abc.abstractmethod
    def _create_session(self, session_id: str, session_type: str, **kwargs) -> SessionBase:
        """Create a new session with all infrastructure.

        Called inside ``get_or_create()`` under the lock when a session does
        not yet exist. Implementations should create directory structure,
        loggers, info objects, and the concrete session.

        Args:
            session_id: Unique identifier for the session.
            session_type: Type/variant of session to create.
            **kwargs: Additional service-specific arguments.

        Returns:
            A fully constructed session instance.
        """

    def persist_session_state(self, session: SessionBase, status: str = "active") -> None:
        """Persist session state to disk for crash recovery.

        Default is a no-op. Subclasses override to implement persistence.
        """

    def _on_before_cleanup(self, session: SessionBase) -> None:
        """Hook for service-specific cleanup before session removal.

        Called inside ``cleanup_session()`` under the lock, before
        ``session.finalize()`` and removal from the sessions dict.
        Default implementation is a no-op.
        """

    # ------------------------------------------------------------------
    # Concrete lifecycle operations
    # ------------------------------------------------------------------

    def get_or_create(
        self,
        session_id: str,
        session_type: Optional[str] = None,
        **kwargs,
    ) -> SessionBase:
        """Get existing session or create new one (thread-safe).

        Args:
            session_id: Unique identifier for the session.
            session_type: Type/variant of session (required for new sessions).
            **kwargs: Forwarded to ``_create_session()``.

        Returns:
            The session for the given ID.
        """
        with self._lock:
            if session_id not in self._sessions:
                session = self._create_session(session_id, session_type, **kwargs)
                self._sessions[session_id] = session

                self.log_info({
                    'type': self._get_log_type_session_management(),
                    'message': f'Session created: {session_id}',
                    'session_type': session_type,
                })

            return self._sessions[session_id]

    def get(self, session_id: str) -> Optional[SessionBase]:
        """Get session if it exists (thread-safe).

        Args:
            session_id: Unique identifier for the session.

        Returns:
            Session if it exists, None otherwise.
        """
        with self._lock:
            return self._sessions.get(session_id)

    def update_session(self, session_id: str, **updates) -> None:
        """Update session fields (thread-safe).

        Routes runtime fields (defined in ``_RUNTIME_FIELDS``) to session
        properties, and data fields to ``session.info``.
        Automatically updates the ``last_active`` timestamp.

        Args:
            session_id: Unique identifier for the session.
            **updates: Field names and values to update.

        Raises:
            KeyError: If session does not exist.
            AttributeError: If trying to update non-existent field.
        """
        with self._lock:
            if session_id not in self._sessions:
                raise KeyError(f"Session {session_id} does not exist")

            session = self._sessions[session_id]
            for key, value in updates.items():
                if key in self._RUNTIME_FIELDS:
                    setattr(session, key, value)
                elif hasattr(session.info, key):
                    setattr(session.info, key, value)
                else:
                    raise AttributeError(
                        f"{type(session).__name__} has no attribute '{key}'"
                    )

            session.info.last_active = time.time()

    def cleanup_session(self, session_id: str) -> None:
        """Clean up session resources (thread-safe).

        Calls ``_on_before_cleanup()`` hook, finalizes the session logger,
        and removes the session from the sessions dictionary.

        Args:
            session_id: Unique identifier for the session.
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return

            session.log_info({
                'type': self._get_log_type_session_cleanup(),
                'message': f'Cleaning up session: {session_id}',
            })

            self._on_before_cleanup(session)

            session.finalize("cancelled")

            del self._sessions[session_id]

    def cleanup_idle_sessions(self) -> None:
        """Remove sessions idle beyond timeout (thread-safe).

        Checks all sessions and removes those that have been idle
        for longer than ``_session_idle_timeout`` seconds.
        """
        with self._lock:
            current_time = time.time()
            timeout = self._session_idle_timeout

            sessions_to_cleanup = []
            for session_id, session in self._sessions.items():
                idle_time = current_time - session.info.last_active
                if idle_time > timeout:
                    sessions_to_cleanup.append(session_id)
                    session.log_info({
                        'type': self._get_log_type_session_cleanup(),
                        'message': f'Session {session_id} idle for {idle_time:.1f}s (timeout: {timeout}s)',
                    })

            for session_id in sessions_to_cleanup:
                self.cleanup_session(session_id)

    def get_all_sessions(self) -> Dict[str, SessionBase]:
        """Get all active sessions (thread-safe).

        Returns a copy of the sessions dictionary to prevent external
        modification of internal state.

        Returns:
            Dictionary mapping session_id to session.
        """
        with self._lock:
            return dict(self._sessions)

    # ------------------------------------------------------------------
    # Session resume support
    # ------------------------------------------------------------------

    def _restore_session(
        self, session_state_path: Path, data: Dict[str, Any]
    ) -> SessionBase:
        """Restore a single session from a persisted state file.

        Default raises NotImplementedError. Subclasses that support resume
        should override this method.

        Args:
            session_state_path: Path to the session_state.json file.
            data: Already-parsed contents of the session_state.json file.

        Returns:
            A fully reconstructed session instance.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support session restore"
        )

    def restore_sessions(self, session_log_dir: Path) -> None:
        """Scan for persisted sessions and restore active ones (thread-safe).

        Looks for subdirectories containing ``session_state.json`` under
        ``session_log_dir``. Skips sessions with ``status == "closed"``.

        Args:
            session_log_dir: The persistent session log directory
                (e.g. ``<server_dir>/logs/sessions/``).
        """
        _logger = logging.getLogger(__name__)

        if not session_log_dir.is_dir():
            return

        restored = 0
        for subdir in sorted(session_log_dir.iterdir()):
            state_file = subdir / "session_state.json"
            if not state_file.is_file():
                continue

            try:
                data = json.loads(state_file.read_text(encoding="utf-8"))
                if data.get("status") == "closed":
                    continue

                session = self._restore_session(state_file, data)
                with self._lock:
                    self._sessions[session.session_id] = session
                restored += 1

            except NotImplementedError:
                _logger.debug(
                    "Session restore not supported, skipping %s", subdir.name
                )
                break
            except Exception as e:
                _logger.warning(
                    "Failed to restore session from %s: %s", subdir.name, e
                )

        if restored:
            _logger.info("Restored %d session(s) from previous run", restored)
            # Update the sessions index so the WebUI can list restored sessions
            if hasattr(self, '_write_sessions_index'):
                with self._lock:
                    self._write_sessions_index()
