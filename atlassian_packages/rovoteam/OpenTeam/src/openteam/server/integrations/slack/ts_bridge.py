"""Generic TypeScript bridge — execute TS scripts via subprocess.

Calls ``npx tsx <script.ts>`` with JSON input and returns parsed JSON output.
Used by the Slack action executor to call ``slack_bridge.ts`` which wraps
the ``@slack/web-api`` WebClient.

This pattern is analogous to the TWG tool.json → subprocess approach:
- TWG: Python → subprocess(twg CLI binary) → Teamwork Graph API
- Slack actions: Python → subprocess(npx tsx slack_bridge.ts) → Slack Web API
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Path to the bridge TS file (co-located in bridge/ subdirectory)
_BRIDGE_DIR = Path(__file__).parent / "bridge"
_SLACK_BRIDGE_TS = _BRIDGE_DIR / "slack_bridge.ts"


def call_slack_api(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Call a Slack Web API method via the TypeScript bridge.

    Args:
        method: Slack API method (e.g., "chat.postMessage", "reactions.add").
        params: Parameters to pass to the API method.

    Returns:
        Parsed JSON response from the Slack API.

    Raises:
        RuntimeError: If the bridge process fails or returns an error.
        FileNotFoundError: If the bridge TS file is not found.
    """
    if not _SLACK_BRIDGE_TS.is_file():
        raise FileNotFoundError(
            f"Slack bridge not found at {_SLACK_BRIDGE_TS}. "
            f"Ensure the bridge/ directory is present."
        )

    input_json = json.dumps({"method": method, "params": params or {}})

    logger.debug("Calling Slack API via TS bridge: %s(%s)", method, json.dumps(params or {})[:200])

    try:
        result = subprocess.run(
            ["npx", "tsx", str(_SLACK_BRIDGE_TS), input_json],
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ},  # Pass through all env vars (incl. SLACK_BOT_TOKEN)
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"Slack bridge timed out for {method}") from e
    except FileNotFoundError as e:
        raise RuntimeError(
            "npx/tsx not found. Install Node.js and tsx: npm install -g tsx"
        ) from e

    if result.returncode != 0:
        # Parse structured error from stderr
        stderr = result.stderr.strip()
        try:
            err = json.loads(stderr)
            raise RuntimeError(f"Slack API error ({method}): {err.get('error', stderr)}")
        except json.JSONDecodeError:
            raise RuntimeError(f"Slack bridge failed ({method}): {stderr or 'unknown error'}")

    # Parse stdout
    stdout = result.stdout.strip()
    if not stdout:
        raise RuntimeError(f"Slack bridge returned empty output for {method}")

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Slack bridge returned invalid JSON for {method}: {stdout[:200]}") from e

    if not data.get("ok"):
        raise RuntimeError(f"Slack API returned ok=false ({method}): {data.get('error', 'unknown')}")

    return data


# ---------------------------------------------------------------------------
# Convenience wrappers — map tool names to Slack API methods + param reshaping
# ---------------------------------------------------------------------------

# Maps tool_name → (slack_method, param_transformer)
# The transformer reshapes tool params to Slack API params
_TOOL_METHOD_MAP: dict[str, tuple[str, dict[str, str] | None]] = {
    "slack_react": ("reactions.add", {"channel_id": "channel", "message_id": "timestamp", "emoji": "name"}),
    "slack_remove_reaction": ("reactions.remove", {"channel_id": "channel", "message_id": "timestamp", "emoji": "name"}),
    "slack_list_reactions": ("reactions.get", {"channel_id": "channel", "message_id": "timestamp"}),
    "slack_remove_own_reactions": (None, None),  # Multi-step — handled specially
    "slack_send_message": ("chat.postMessage", None),  # Complex — handled specially
    "slack_edit_message": ("chat.update", {"channel_id": "channel", "message_id": "ts", "content": "text"}),
    "slack_delete_message": ("chat.delete", {"channel_id": "channel", "message_id": "ts"}),
    "slack_read_messages": (None, None),  # Branch on thread_id — handled specially
    "slack_pin_message": ("pins.add", {"channel_id": "channel", "message_id": "timestamp"}),
    "slack_unpin_message": ("pins.remove", {"channel_id": "channel", "message_id": "timestamp"}),
    "slack_list_pins": ("pins.list", {"channel_id": "channel"}),
    "slack_member_info": ("users.info", {"user_id": "user"}),
    "slack_emoji_list": ("emoji.list", None),
}


def _normalize_emoji(raw: str) -> str:
    """Strip surrounding colons from emoji name."""
    return raw.strip().strip(":")


def _remap_params(tool_params: dict[str, Any], mapping: dict[str, str]) -> dict[str, Any]:
    """Remap tool parameter names to Slack API parameter names."""
    result = {}
    for tool_key, api_key in mapping.items():
        if tool_key in tool_params and tool_params[tool_key] is not None:
            val = tool_params[tool_key]
            if tool_key == "emoji":
                val = _normalize_emoji(val)
            result[api_key] = val
    return result


def execute_slack_action(tool_name: str, tool_params: dict[str, Any]) -> dict[str, Any]:
    """Execute a Slack action tool by name.

    Maps tool names to Slack API methods, reshapes parameters, and calls
    the TS bridge. Handles multi-step actions (remove_own_reactions, send_message,
    read_messages) specially.

    Args:
        tool_name: Tool name (e.g., "slack_react").
        tool_params: Parameters from the tool call.

    Returns:
        JSON result from the Slack API.
    """
    if tool_name not in _TOOL_METHOD_MAP:
        raise ValueError(f"Unknown Slack action tool: {tool_name}")

    method, param_map = _TOOL_METHOD_MAP[tool_name]

    # --- Special cases ---

    if tool_name == "slack_remove_own_reactions":
        return _remove_own_reactions(tool_params)

    if tool_name == "slack_send_message":
        return _send_message(tool_params)

    if tool_name == "slack_read_messages":
        return _read_messages(tool_params)

    if tool_name == "slack_list_reactions":
        data = call_slack_api(method, _remap_params(tool_params, param_map))
        return {"ok": True, "reactions": data.get("message", {}).get("reactions", [])}

    if tool_name == "slack_emoji_list":
        data = call_slack_api("emoji.list")
        emoji = data.get("emoji", {})
        limit = tool_params.get("limit")
        if limit and int(limit) > 0:
            entries = sorted(emoji.items())[:int(limit)]
            emoji = dict(entries)
        return {"ok": True, "emoji": emoji}

    # --- Standard cases ---
    api_params = _remap_params(tool_params, param_map) if param_map else tool_params
    return call_slack_api(method, api_params)


def _send_message(params: dict[str, Any]) -> dict[str, Any]:
    """Handle slack_send_message with target resolution."""
    to = params.get("to", "")
    content = params.get("content", "")
    thread_ts = params.get("thread_ts")

    channel = to
    if ":" in to:
        kind, target_id = to.split(":", 1)
        if kind == "user":
            dm = call_slack_api("conversations.open", {"users": target_id})
            channel = dm.get("channel", {}).get("id", target_id)
        else:
            channel = target_id

    api_params: dict[str, Any] = {"channel": channel, "text": content}
    if thread_ts:
        api_params["thread_ts"] = thread_ts

    return call_slack_api("chat.postMessage", api_params)


def _read_messages(params: dict[str, Any]) -> dict[str, Any]:
    """Handle slack_read_messages with thread/history branching."""
    channel_id = params.get("channel_id", "")
    limit = params.get("limit", 20)
    thread_id = params.get("thread_id")
    before = params.get("before")
    after = params.get("after")

    if thread_id:
        api_params: dict[str, Any] = {"channel": channel_id, "ts": thread_id, "limit": limit}
        if before:
            api_params["latest"] = before
        if after:
            api_params["oldest"] = after
        data = call_slack_api("conversations.replies", api_params)
        messages = [m for m in data.get("messages", []) if m.get("ts") != thread_id]
        return {"ok": True, "messages": messages, "has_more": data.get("has_more", False)}
    else:
        api_params = {"channel": channel_id, "limit": limit}
        if before:
            api_params["latest"] = before
        if after:
            api_params["oldest"] = after
        data = call_slack_api("conversations.history", api_params)
        return {"ok": True, "messages": data.get("messages", []), "has_more": data.get("has_more", False)}


def _remove_own_reactions(params: dict[str, Any]) -> dict[str, Any]:
    """Remove all of the bot's own reactions from a message (multi-step)."""
    channel_id = params.get("channel_id", "")
    message_id = params.get("message_id", "")

    # Get bot user ID
    auth = call_slack_api("auth.test")
    bot_user_id = auth.get("user_id")
    if not bot_user_id:
        raise RuntimeError("Failed to resolve bot user ID")

    # Get current reactions
    data = call_slack_api("reactions.get", {"channel": channel_id, "timestamp": message_id, "full": "true"})
    reactions = data.get("message", {}).get("reactions", [])

    removed = []
    for reaction in reactions:
        name = reaction.get("name")
        users = reaction.get("users", [])
        if name and bot_user_id in users:
            call_slack_api("reactions.remove", {"channel": channel_id, "timestamp": message_id, "name": name})
            removed.append(name)

    return {"ok": True, "removed": removed}
