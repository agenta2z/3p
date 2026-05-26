"""Backend implementations for FileSpaceManager."""

from .file_backend import FileBackend
from .protocol import FieldBackend

__all__ = ["FieldBackend", "FileBackend"]
