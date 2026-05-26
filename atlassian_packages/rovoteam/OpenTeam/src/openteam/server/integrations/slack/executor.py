"""Slack tool executor — dispatches tool calls to operation functions.

Implements the ToolExecutorCallable protocol for all 8 Slack tools.
On any exception, returns {"ok": false, "error": "..."} so the LLM
can see the error and decide how to proceed.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Coroutine

from agent_foundation.common.inferencers.agentic_inferencers.conversational.protocols import (  # noqa: E501
    ToolExecutionResult,
)
from openteam.server.integrations.slack.operations import (
    find_channel,
    find_dm_channel,
    get_channel_history,
    get_dm_messages,
    get_thread,
    list_channels,
    search_files,
    search_messages,
)
from openteam.server.integrations.slack.ts_bridge import execute_slack_action

logger = logging.getLogger(__name__)

# Dispatch map: tool_name -> async operation function
_SLACK_DISPATCH: dict[
    str, Callable[..., Coroutine[Any, Any, dict[str, Any]]]
] = {
    "slack_search_messages": search_messages,
    "slack_search_files": search_files,
    "slack_get_thread": get_thread,
    "slack_list_channels": list_channels,
    "slack_find_channel": find_channel,
    "slack_find_dm_channel": find_dm_channel,
    "slack_get_channel_history": get_channel_history,
    "slack_get_dm_messages": get_dm_messages,
    "slack_get_messages_with_user": get_dm_messages,  # alias
}

# Action tools — dispatched via TS bridge (calls @slack/web-api via subprocess)
_SLACK_ACTION_TOOLS = frozenset({
    "slack_react",
    "slack_remove_reaction",
    "slack_list_reactions",
    "slack_remove_own_reactions",
    "slack_send_message",
    "slack_edit_message",
    "slack_delete_message",
    "slack_read_messages",
    "slack_pin_message",
    "slack_unpin_message",
    "slack_list_pins",
    "slack_member_info",
    "slack_emoji_list",
})


def is_slack_tool(tool_name: str) -> bool:
    """Check if a tool name is handled by this executor."""
    return tool_name in _SLACK_DISPATCH or tool_name in _SLACK_ACTION_TOOLS


async def execute_slack_tool(
    tool_name: str, arguments: dict[str, Any]
) -> ToolExecutionResult:
    """Execute a Slack tool by dispatching to the appropriate operation.

    Args:
        tool_name: Canonical tool name (e.g., "slack_search_messages").
        arguments: Tool arguments from the LLM.

    Returns:
        ToolExecutionResult with JSON-serialized result string.
    """
    handler = _SLACK_DISPATCH.get(tool_name)
    if not handler:
        return ToolExecutionResult(
            result=json.dumps({"ok": False, "error": f"Unknown Slack tool: {tool_name}"})
        )

    try:
        result = await handler(**arguments)
        return ToolExecutionResult(result=json.dumps(result, default=str))
    except Exception as e:
        logger.error("Slack tool %s failed: %s", tool_name, e)
        return ToolExecutionResult(
            result=json.dumps({"ok": False, "error": str(e)})
        )
