"""TWG tool executor — runs TWG CLI commands via subprocess.

Implements the ToolExecutorCallable protocol for the TWG tool.
Uses asyncio.create_subprocess_exec (no shell) for safe execution.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shlex
from typing import Any

from agent_foundation.common.inferencers.agentic_inferencers.conversational.protocols import (
    ToolExecutionResult,
)

logger = logging.getLogger(__name__)

# Known TWG surface names for input validation (warn-not-block on unknown)
_KNOWN_SURFACES = {
    # Federated surfaces
    "docs", "videos", "meetings", "spaces", "recently-viewed",
    # Projection surfaces
    "work", "org-tree", "context",
    # Native surfaces
    "jira", "confluence", "bitbucket", "goals", "projects", "teams",
    # Identity & resolution
    "user-search", "resolve", "collaborators",
    # Bitbucket shorthand
    "bb", "pr",
    # Schema exploration
    "cypher",
    # Other
    "focus-areas", "assets", "login", "echo",
}


def _resolve_twg_binary() -> str:
    """Resolve TWG binary path.

    Priority:
    1. TWG_BINARY_PATH env var (explicit full path)
    2. TWG_INSTALL_DIR env var + "/scripts/twg" (skill installation dir)
    3. "twg" (assumes on PATH)

    The SKILL.md specifies `scripts/twg` resolved relative to the skill
    directory. When installed externally, set TWG_INSTALL_DIR to the skill root.
    """
    if explicit := os.environ.get("TWG_BINARY_PATH"):
        return explicit
    if install_dir := os.environ.get("TWG_INSTALL_DIR"):
        return os.path.join(install_dir, "scripts", "twg")
    return "twg"


def is_twg_tool(tool_name: str) -> bool:
    """Check if a tool name is handled by this executor."""
    return tool_name == "twg"


async def execute_twg(
    tool_name: str, arguments: dict[str, Any]
) -> ToolExecutionResult:
    """Execute a TWG CLI command via subprocess.

    Args:
        tool_name: Should be "twg".
        arguments: Must contain "command" key with TWG command arguments.

    Returns:
        ToolExecutionResult with CLI stdout on success or error message on failure.
    """
    command = str(arguments.get("command", "")).strip()
    if not command:
        return ToolExecutionResult(result="Error: empty TWG command")

    twg_binary = _resolve_twg_binary()
    args = shlex.split(command)

    # Warn on unknown surface (first arg), but proceed
    if args and args[0] not in _KNOWN_SURFACES:
        logger.warning("Unknown TWG surface '%s'", args[0])

    try:
        proc = await asyncio.create_subprocess_exec(
            twg_binary,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ},
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode == 0:
            return ToolExecutionResult(result=stdout.decode())
        else:
            return ToolExecutionResult(
                result=f"TWG error (exit {proc.returncode}): {stderr.decode()}"
            )
    except FileNotFoundError:
        return ToolExecutionResult(
            result=(
                f"TWG binary not found at '{twg_binary}'. "
                f"Set TWG_BINARY_PATH or TWG_INSTALL_DIR, or ensure 'twg' is on PATH."
            )
        )
    except Exception as e:
        logger.error("TWG execution failed: %s", e)
        return ToolExecutionResult(result=f"TWG execution error: {e}")
