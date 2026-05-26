"""Pluggable inferencer backends for the OpenTeam conversation loop.

Importing this package triggers registration of the built-in ``mock``,
``rovodev``, and ``claude_cli`` backends on the module-level singleton.
"""

from openteam.server.backends.registry import (
    BackendBuildContext,
    BackendDescriptor,
    BackendFactory,
    BackendRegistry,
    get_registry,
    register_backend,
)

# Triggers built-in registration as a side effect of importing the package.
from openteam.server.backends import factories  # noqa: F401

__all__ = [
    "BackendBuildContext",
    "BackendDescriptor",
    "BackendFactory",
    "BackendRegistry",
    "get_registry",
    "register_backend",
]
