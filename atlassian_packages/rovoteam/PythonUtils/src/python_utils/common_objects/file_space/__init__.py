"""FileSpaceManager — canonical file-space resolver with cascade + master_version.

Public API:
    FileSpaceManager  — the main resolver class
    ResolvedContent   — result dataclass (lazy-readable, URI-shaped)
    FieldBackend      — Protocol for pluggable backends
    FileBackend       — filesystem-based backend (the MVP default)
"""

from .backends import FieldBackend, FileBackend
from .manager import FileSpaceManager
from .resolved_content import ResolvedContent

__all__ = [
    "FileSpaceManager",
    "ResolvedContent",
    "FieldBackend",
    "FileBackend",
]
