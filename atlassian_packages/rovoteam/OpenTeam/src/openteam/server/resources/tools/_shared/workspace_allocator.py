"""Backward-compatible re-export. The canonical implementation has moved to
agent_foundation.common.workspace.allocator.
"""
import warnings

warnings.warn(
    "openteam.server.resources.tools._shared.workspace_allocator is deprecated. "
    "Use agent_foundation.common.workspace.allocator instead.",
    DeprecationWarning,
    stacklevel=2,
)
from agent_foundation.common.workspace.allocator import (
    find_runtime_root,
    make_workspace_dirname,
    allocate_tool_workspace,
)
