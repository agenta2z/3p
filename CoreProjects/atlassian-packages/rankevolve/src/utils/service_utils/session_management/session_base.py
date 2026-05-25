"""Base session class with Debuggable logging and lifecycle management.

This module provides SessionBase, which IS the per-session Debuggable.
It replaces the pattern of creating standalone Debugger instances per session.
"""
from attr import attrs, attrib
from rich_python_utils.common_objects.debuggable import Debuggable

from .session_info import SessionInfo
from .session_logger import SessionLogger


@attrs(slots=False)
class SessionBase(Debuggable):
    """Base session with Debuggable logging and lifecycle management.

    The session itself IS the Debuggable — no separate Debugger instance needed.
    Provides session lifecycle methods and logger creation.

    Attributes:
        _info: Pure data container for session state.
        _session_logger: SessionLogger with turn-aware routing and console output.
    """
    _info: SessionInfo = attrib(kw_only=True)
    _session_logger: SessionLogger = attrib(kw_only=True)

    @property
    def info(self) -> SessionInfo:
        """Access the pure data container."""
        return self._info

    @property
    def session_id(self) -> str:
        """Convenience accessor for the session identity."""
        return self._info.session_id

    @property
    def session_logger(self) -> SessionLogger:
        """Access the session logger."""
        return self._session_logger

    def finalize(self, status: str) -> None:
        """Finalize session logger with the given status."""
        if self._session_logger is not None:
            self._session_logger.finalize(status)
