"""Backend registry for pluggable inferencer backends.

The registry maps a backend name (e.g. ``"rovodev"``, ``"claude_cli"``,
``"mock"``) to a factory callable that builds a fully wired
``ConversationalInferencer`` for that backend.

Adding a new backend = write one factory function + register it. No
changes to ``ConversationService`` are needed.

The ``mock`` backend is registered for descriptor/listing purposes but is
intentionally NOT routed through ``create()`` — it is fast-pathed in
``ConversationService._get_session_inferencer`` because it has no real
inferencer to build. Its registry entry holds a guard factory that raises
if invoked, which keeps the ``BackendFactory`` contract non-Optional.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, Protocol

__all__ = [
    "BackendBuildContext",
    "BackendDescriptor",
    "BackendFactory",
    "BackendRegistry",
    "get_registry",
    "register_backend",
]


@dataclass(frozen=True)
class BackendBuildContext:
    """Everything a factory needs from the server to build an inferencer."""

    templates_dir: Path
    working_dir: str
    cache_dir: Optional[str] = None
    session_store: Optional[Any] = None
    model_name: Optional[str] = None
    session_id: str = ""


class BackendFactory(Protocol):
    def __call__(self, ctx: BackendBuildContext) -> Any: ...  # ConversationalInferencer


@dataclass
class BackendDescriptor:
    """Metadata + availability probe for a registered backend.

    ``is_available`` and ``status_message`` are zero-arg callables so they
    re-evaluate at call time (e.g. ``shutil.which`` reads PATH on each
    invocation, picking up freshly-installed binaries).
    """

    name: str
    display_name: str
    description: str
    default_model: Optional[str] = None
    is_available: Callable[[], bool] = field(default=lambda: True)
    status_message: Callable[[], str] = field(default=lambda: "Available")


class BackendRegistry:
    """Maps backend name → (factory, descriptor)."""

    def __init__(self) -> None:
        self._entries: dict[str, tuple[BackendFactory, BackendDescriptor]] = {}

    def register(
        self,
        name: str,
        factory: BackendFactory,
        descriptor: BackendDescriptor,
    ) -> None:
        """Register a backend. Last write wins for duplicate names."""
        self._entries[name] = (factory, descriptor)

    def register_backend(
        self, name: str, descriptor: BackendDescriptor
    ) -> Callable[[BackendFactory], BackendFactory]:
        """Decorator form: ``@registry.register_backend("foo", descriptor)``."""

        def decorator(factory: BackendFactory) -> BackendFactory:
            self.register(name, factory, descriptor)
            return factory

        return decorator

    def create(self, name: str, ctx: BackendBuildContext) -> Any:
        """Invoke the named factory with ``ctx`` and return the inferencer.

        Raises KeyError if ``name`` is not registered.
        """
        if name not in self._entries:
            available = ", ".join(sorted(self._entries)) or "(none)"
            raise KeyError(
                f"Unknown backend {name!r}. Registered backends: {available}"
            )
        factory, _ = self._entries[name]
        return factory(ctx)

    def list_backends(self) -> dict[str, BackendDescriptor]:
        """Return a copy of {name → descriptor} for all registered backends."""
        return {name: desc for name, (_, desc) in self._entries.items()}

    def get_descriptor(self, name: str) -> BackendDescriptor:
        if name not in self._entries:
            available = ", ".join(sorted(self._entries)) or "(none)"
            raise KeyError(
                f"Unknown backend {name!r}. Registered backends: {available}"
            )
        return self._entries[name][1]


_registry = BackendRegistry()


def get_registry() -> BackendRegistry:
    """Module-level singleton accessor."""
    return _registry


def register_backend(
    name: str, descriptor: BackendDescriptor
) -> Callable[[BackendFactory], BackendFactory]:
    """Module-level decorator that registers on the singleton."""
    return _registry.register_backend(name, descriptor)
