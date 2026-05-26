"""Slack action operations — ported from openclaw extensions/slack/src/actions.ts.

These operations use **bot tokens** (xoxb-*) via the Slack Web API for write
operations (reactions, pins, messaging, etc.).  The search operations in
``operations.py`` use user tokens (xoxc/xoxp); actions require bot tokens
because write scopes are typically only granted to bot installations.

Token resolution priority:
1. ``SLACK_BOT_TOKEN`` env var
2. Proximity server at ``PROXIMITY_URL`` (``/slack/bot-token``)
3. Falls back to the user-token client if ``SLACK_BOT_TOKEN`` is not set
   (some workspaces grant write scopes to user tokens)
"""

from __future__ import annotations

import logging
import os
from typing import Any

from openteam.server.integrations.slack.client import slack_api_call

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Bot-token aware API call
# ---------------------------------------------------------------------------

async def _slack_bot_api_call(
    method: str,
    params: dict[str, Any] | None = None,
    *,
    post: bool = False,
) -> dict[str, Any]:
    """Make a Slack API call using bot token if available, else user token.

    For write operations (reactions.add, chat.postMessage, etc.) the Slack API
    requires a POST request with a JSON body.  For read operations a GET with
    query params suffices.

    The ``post`` flag controls which HTTP method is used.  All write
    operations in this module set ``post=True``.
    """
    import httpx

    bot_token = os.environ.get("SLACK_BOT_TOKEN")
    if bot_token:
        url = f"https://slack.com/api/{method}"
        headers = {
            "Authorization": f"Bearer {bot_token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            if post:
                resp = await client.post(url, json=params or {}, headers=headers)
            else:
                filtered = {k: str(v) for k, v in (params or {}).items() if v is not None}
                resp = await client.get(url, params=filtered, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok"):
                raise RuntimeError(f"Slack API error ({method}): {data.get('error', 'unknown')}")
            return data

    # Fallback to user-token client (may work for some write operations)
    logger.debug("No SLACK_BOT_TOKEN set, falling back to user-token client for %s", method)
    return await slack_api_call(method, params)


def _normalize_emoji(raw: str) -> str:
    """Strip surrounding colons from emoji name."""
    trimmed = raw.strip()
    if not trimmed:
        raise ValueError("Emoji is required for Slack reactions")
    return trimmed.strip(":")


# ---------------------------------------------------------------------------
# Reactions
# ---------------------------------------------------------------------------

async def react(
    channel_id: str,
    message_id: str,
    emoji: str,
    **_kwargs: Any,
) -> dict[str, Any]:
    """Add an emoji reaction to a message."""
    await _slack_bot_api_call("reactions.add", {
        "channel": channel_id,
        "timestamp": message_id,
        "name": _normalize_emoji(emoji),
    }, post=True)
    return {"ok": True, "action": "react", "emoji": _normalize_emoji(emoji)}


async def remove_reaction(
    channel_id: str,
    message_id: str,
    emoji: str,
    **_kwargs: Any,
) -> dict[str, Any]:
    """Remove an emoji reaction from a message."""
    await _slack_bot_api_call("reactions.remove", {
        "channel": channel_id,
        "timestamp": message_id,
        "name": _normalize_emoji(emoji),
    }, post=True)
    return {"ok": True, "action": "remove_reaction", "emoji": _normalize_emoji(emoji)}


async def list_reactions(
    channel_id: str,
    message_id: str,
    **_kwargs: Any,
) -> dict[str, Any]:
    """List reactions on a message."""
    data = await _slack_bot_api_call("reactions.get", {
        "channel": channel_id,
        "timestamp": message_id,
        "full": "true",
    })
    message = data.get("message", {})
    return {"ok": True, "reactions": message.get("reactions", [])}


async def remove_own_reactions(
    channel_id: str,
    message_id: str,
    **_kwargs: Any,
) -> dict[str, Any]:
    """Remove all of the bot's own reactions from a message."""
    # Get bot user ID
    auth = await _slack_bot_api_call("auth.test")
    bot_user_id = auth.get("user_id")
    if not bot_user_id:
        raise RuntimeError("Failed to resolve bot user ID")

    # Get current reactions
    result = await list_reactions(channel_id, message_id)
    removed = []
    for reaction in result.get("reactions", []):
        name = reaction.get("name")
        users = reaction.get("users", [])
        if name and bot_user_id in users:
            await _slack_bot_api_call("reactions.remove", {
                "channel": channel_id,
                "timestamp": message_id,
                "name": name,
            }, post=True)
            removed.append(name)

    return {"ok": True, "removed": removed}


# ---------------------------------------------------------------------------
# Messaging
# ---------------------------------------------------------------------------

async def send_message(
    to: str,
    content: str,
    thread_ts: str | None = None,
    **_kwargs: Any,
) -> dict[str, Any]:
    """Send a message to a channel or user.

    ``to`` can be a channel ID (C...), user ID (U...), or prefixed
    ``channel:C123`` / ``user:U123``.
    """
    # Parse target
    channel = to
    if ":" in to:
        kind, target_id = to.split(":", 1)
        if kind == "user":
            # Open a DM conversation first
            dm = await _slack_bot_api_call("conversations.open", {
                "users": target_id,
            }, post=True)
            channel = dm.get("channel", {}).get("id", target_id)
        else:
            channel = target_id

    params: dict[str, Any] = {
        "channel": channel,
        "text": content,
    }
    if thread_ts:
        params["thread_ts"] = thread_ts

    data = await _slack_bot_api_call("chat.postMessage", params, post=True)
    return {
        "ok": True,
        "channel": data.get("channel"),
        "ts": data.get("ts"),
        "message": data.get("message", {}),
    }


async def edit_message(
    channel_id: str,
    message_id: str,
    content: str,
    **_kwargs: Any,
) -> dict[str, Any]:
    """Edit an existing message."""
    await _slack_bot_api_call("chat.update", {
        "channel": channel_id,
        "ts": message_id,
        "text": content.strip() or " ",
    }, post=True)
    return {"ok": True, "action": "edit", "channel": channel_id, "ts": message_id}


async def delete_message(
    channel_id: str,
    message_id: str,
    **_kwargs: Any,
) -> dict[str, Any]:
    """Delete a message."""
    await _slack_bot_api_call("chat.delete", {
        "channel": channel_id,
        "ts": message_id,
    }, post=True)
    return {"ok": True, "action": "delete", "channel": channel_id, "ts": message_id}


async def read_messages(
    channel_id: str,
    limit: int = 20,
    thread_id: str | None = None,
    before: str | None = None,
    after: str | None = None,
    **_kwargs: Any,
) -> dict[str, Any]:
    """Read recent messages from a channel or thread."""
    if thread_id:
        params: dict[str, Any] = {
            "channel": channel_id,
            "ts": thread_id,
            "limit": limit,
        }
        if before:
            params["latest"] = before
        if after:
            params["oldest"] = after
        data = await _slack_bot_api_call("conversations.replies", params)
        messages = data.get("messages", [])
        # Drop parent message (same behavior as OpenClaw)
        messages = [m for m in messages if m.get("ts") != thread_id]
        return {"ok": True, "messages": messages, "has_more": data.get("has_more", False)}
    else:
        params = {
            "channel": channel_id,
            "limit": limit,
        }
        if before:
            params["latest"] = before
        if after:
            params["oldest"] = after
        data = await _slack_bot_api_call("conversations.history", params)
        return {"ok": True, "messages": data.get("messages", []), "has_more": data.get("has_more", False)}


# ---------------------------------------------------------------------------
# Pins
# ---------------------------------------------------------------------------

async def pin_message(
    channel_id: str,
    message_id: str,
    **_kwargs: Any,
) -> dict[str, Any]:
    """Pin a message in a channel."""
    await _slack_bot_api_call("pins.add", {
        "channel": channel_id,
        "timestamp": message_id,
    }, post=True)
    return {"ok": True, "action": "pin"}


async def unpin_message(
    channel_id: str,
    message_id: str,
    **_kwargs: Any,
) -> dict[str, Any]:
    """Unpin a message from a channel."""
    await _slack_bot_api_call("pins.remove", {
        "channel": channel_id,
        "timestamp": message_id,
    }, post=True)
    return {"ok": True, "action": "unpin"}


async def list_pins(
    channel_id: str,
    **_kwargs: Any,
) -> dict[str, Any]:
    """List pinned items in a channel."""
    data = await _slack_bot_api_call("pins.list", {
        "channel": channel_id,
    })
    return {"ok": True, "pins": data.get("items", [])}


# ---------------------------------------------------------------------------
# Member info & emoji
# ---------------------------------------------------------------------------

async def member_info(
    user_id: str,
    **_kwargs: Any,
) -> dict[str, Any]:
    """Get Slack user profile information."""
    data = await _slack_bot_api_call("users.info", {"user": user_id})
    return {"ok": True, "user": data.get("user", {})}


async def emoji_list(
    limit: int | None = None,
    **_kwargs: Any,
) -> dict[str, Any]:
    """List custom emojis in the workspace."""
    data = await _slack_bot_api_call("emoji.list")
    emoji = data.get("emoji", {})
    if limit and limit > 0:
        entries = sorted(emoji.items())
        if len(entries) > limit:
            emoji = dict(entries[:limit])
    return {"ok": True, "emoji": emoji}
