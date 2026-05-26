"""Combined tool executor dispatch for integration tools.

Provides build_integration_executor() which creates a ToolExecutorCallable
that dispatches to the appropriate integration executor (Slack, TWG, etc.).

Usage in application wiring:


    integration_executor = build_integration_executor()

    # Compose with existing executors:
    async def combined_executor(tool_name, arguments):
        if integration_executor.handles(tool_name):
            return await integration_executor(tool_name, arguments)
        # ... existing tool dispatch ...
"""

from __future__ import annotations

import logging
from typing import Any

from agent_foundation.common.inferencers.agentic_inferencers.conversational.protocols import (
    ToolExecutionResult,
)
from openteam.server.integrations.slack.executor import (
    execute_slack_tool,
    is_slack_tool,
)
from openteam.server.integrations.twg.executor import (
    execute_twg,
    is_twg_tool,
)

logger = logging.getLogger(__name__)


class IntegrationToolExecutor:
    """Dispatcher for integration tools (Slack, TWG, etc.).

    Conforms to the ToolExecutorCallable protocol.
    """

    def handles(self, tool_name: str) -> bool:
        """Check if this executor handles the given tool name."""
        return is_slack_tool(tool_name) or is_twg_tool(tool_name)

    async def __call__(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> ToolExecutionResult:
        """Dispatch to the appropriate integration executor."""
        if is_slack_tool(tool_name):
            return await execute_slack_tool(tool_name, arguments)
        if is_twg_tool(tool_name):
            return await execute_twg(tool_name, arguments)
        return ToolExecutionResult(
            result=f"Unknown integration tool: {tool_name}"
        )


def build_integration_executor() -> IntegrationToolExecutor:
    """Factory for the integration tool executor."""
    return IntegrationToolExecutor()
