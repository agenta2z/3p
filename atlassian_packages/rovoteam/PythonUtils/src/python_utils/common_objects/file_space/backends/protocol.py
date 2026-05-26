"""FieldBackend Protocol — pluggable resolution backends for FileSpaceManager.

MVP ships FileBackend only. Future backends (YamlFieldBackend, JsonFieldBackend)
implement this same Protocol for non-breaking additions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional, runtime_checkable

from typing_extensions import Protocol

from ..resolved_content import ResolvedContent

Parser = Callable[[Any], Any]


@runtime_checkable
class FieldBackend(Protocol):
    """A backend that resolves field-like lookups from a content source.

    All backends MUST be side-effect free for resolution; reads can be lazy.
    """

    scheme: str

    def can_resolve(self, *, folder: Path, name: str) -> bool:
        """Return True if this backend can resolve ``name`` in ``folder``."""
        ...

    def resolve(
        self,
        *,
        folder: Path,
        name: str,
        master_version: Optional[str] = None,
        encoding: str = "utf-8",
    ) -> Optional[ResolvedContent]:
        """Attempt to resolve ``name`` in ``folder``. Return None if not found."""
        ...

    def read(self, resolved: ResolvedContent, parser: Optional[Parser] = None) -> Any:
        """Read content from a previously resolved ResolvedContent.

        Args:
            resolved: produced by ``resolve()``.
            parser: optional post-processor applied to the raw decoded object.
                If None, returns the backend's natural raw type
                (str for FileBackend; native types for structured backends).

        Returns:
            The raw decoded object, OR ``parser(raw)`` if parser is provided.
        """
        ...
