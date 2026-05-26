"""ResolvedContent dataclass — the universal return shape for FileSpaceManager.resolve()."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from .backends.protocol import FieldBackend

Parser = Callable[[Any], Any]


@dataclass(frozen=True)
class ResolvedContent:
    """Result of a successful resolve().

    Carries enough info to read the content lazily AND diagnose where it came from.
    The ``uri`` field uniquely identifies the content source for caching and diagnostics.
    """

    name: str
    kind: str
    uri: str
    path: Path
    field: Optional[str] = None
    mime: Optional[str] = None
    _backend: Optional[Any] = None

    def read(self, parser: Optional[Parser] = None) -> Any:
        """Lazily read the content via the resolving backend.

        Args:
            parser: optional post-processor. Default None returns the backend's
                natural raw type (str for FileBackend).

        Returns:
            Raw decoded object, OR ``parser(raw)`` if parser is provided.
        """
        if self._backend is None:
            raise RuntimeError("ResolvedContent has no backend — cannot read")
        return self._backend.read(self, parser=parser)

    def read_text(self) -> str:
        """Convenience helper enforcing str return.

        Raises TypeError if backend cannot produce str.
        """
        raw = self.read()
        if not isinstance(raw, str):
            raise TypeError(
                f"ResolvedContent.read_text() expected str from backend "
                f"{getattr(self._backend, 'scheme', '?')!r} but got "
                f"{type(raw).__name__}"
            )
        return raw
