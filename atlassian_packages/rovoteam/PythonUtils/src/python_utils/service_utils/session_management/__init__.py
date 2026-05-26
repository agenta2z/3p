"""Generic session management framework.

Provides reusable infrastructure for services that manage sessions with
turn-aware logging, manifest tracking, thread-safe lifecycle, and monitoring.

Classes:
    SessionInfo: Pure dataclass for session metadata.
    ArtifactEntry: Artifact metadata in the manifest.
    TurnEntry: Turn metadata in the manifest.
    SessionManifest: Top-level manifest indexing logs and artifacts.
    SessionLogger: Callable logger with turn-aware file routing.
    SessionBase: Base session (Debuggable) with lifecycle management.
    SessionManager: Abstract thread-safe session lifecycle manager.
    SessionMonitor: Monitor with periodic cleanup and extensible hooks.
"""

from .session_info import SessionInfo
from .session_manifest import ArtifactEntry, TurnEntry, SessionManifest
from .session_logger import SessionLogger, SessionLogReader
from .session_base import SessionBase
from .session_manager import SessionManager
from .session_monitor import SessionMonitor

__all__ = [
    'SessionInfo',
    'ArtifactEntry',
    'TurnEntry',
    'SessionManifest',
    'SessionLogger',
    'SessionLogReader',
    'SessionBase',
    'SessionManager',
    'SessionMonitor',
]
