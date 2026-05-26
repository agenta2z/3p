"""Slack operation functions — 8 async operations ported from openclaw slack-rts.

Each function calls the Slack Web API via client.slack_api_call() and returns
a dict suitable for JSON serialization back to the LLM.
"""

from __future__ import annotations

import logging
from typing import Any

from openteam.server.integrations.slack.client import slack_api_call

logger = logging.getLogger(__name__)


async def search_messages(
    query: str,
    count: int = 20,
    sort_dir: str = "desc",
    **_kwargs: Any,
) -> dict[str, Any]:
    """Search Slack messages using search.messages API."""
    if not query:
        raise ValueError("query parameter is required")

    result = await slack_api_call("search.messages", {
        "query": query,
        "count": count,
        "sort_dir": sort_dir,
    })
    return {
        "ok": True,
        "total": result.get("messages", {}).get("paging", {}).get("total", 0),
        "matches": result.get("messages", {}).get("matches", []),
        "paging": result.get("messages", {}).get("paging", {}),
    }


async def search_files(
    query: str,
    count: int = 20,
    **_kwargs: Any,
) -> dict[str, Any]:
    """Search Slack files using search.files API."""
    if not query:
        raise ValueError("query parameter is required")

    result = await slack_api_call("search.files", {
        "query": query,
        "count": count,
    })
    return {
        "ok": True,
        "total": result.get("files", {}).get("paging", {}).get("total", 0),
        "matches": result.get("files", {}).get("matches", []),
        "paging": result.get("files", {}).get("paging", {}),
    }


async def get_thread(
    channel: str,
    ts: str,
    limit: int = 100,
    **_kwargs: Any,
) -> dict[str, Any]:
    """Get all messages in a Slack thread using conversations.replies."""
    if not channel or not ts:
        raise ValueError("channel and ts parameters are required")

    result = await slack_api_call("conversations.replies", {
        "channel": channel,
        "ts": ts,
        "limit": limit,
    })
    return {
        "ok": True,
        "channel": result.get("channel"),
        "thread_ts": result.get("thread_ts"),
        "messages": result.get("messages", []),
    }


async def list_channels(
    limit: int = 100,
    exclude_archived: bool = True,
    types: str = "public_channel,private_channel",
    paginate_all: bool = True,
    **_kwargs: Any,
) -> dict[str, Any]:
    """List Slack channels with optional pagination across all pages."""
    channels: list[dict[str, Any]] = []
    cursor: str | None = None
    page_count = 0

    while True:
        params: dict[str, Any] = {
            "limit": limit,
            "exclude_archived": exclude_archived,
            "types": types,
        }
        if cursor:
            params["cursor"] = cursor

        result = await slack_api_call("conversations.list", params)
        channels.extend(result.get("channels", []))
        page_count += 1

        if paginate_all:
            cursor = (
                result.get("response_metadata", {}).get("next_cursor") or None
            )
        else:
            cursor = None

        if not cursor:
            break

    return {
        "ok": True,
        "channels": channels,
        "page_count": page_count,
        "types": types,
    }


async def find_channel(
    channel_name: str | None = None,
    channel_id: str | None = None,
    types: str = "public_channel,private_channel",
    exclude_archived: bool = True,
    **_kwargs: Any,
) -> dict[str, Any]:
    """Resolve a Slack channel name or ID by paginating accessible channels."""
    if channel_name:
        channel_name = channel_name.lstrip("#")

    listing = await list_channels(
        limit=1000,
        exclude_archived=exclude_archived,
        types=types,
        paginate_all=True,
    )
    all_channels = listing.get("channels", [])

    found = None
    for ch in all_channels:
        if (channel_id and ch.get("id") == channel_id) or (
            channel_name and ch.get("name") == channel_name
        ):
            found = ch
            break

    return {
        "ok": True,
        "found": found is not None,
        "channel_id": channel_id or None,
        "channel_name": channel_name or None,
        "channel": found,
        "total_channels_scanned": len(all_channels),
        "page_count": listing.get("page_count", 0),
        "types": listing.get("types", types),
    }


async def find_dm_channel(
    user_id: str,
    **_kwargs: Any,
) -> dict[str, Any]:
    """Find the direct-message channel ID for a Slack user."""
    if not user_id:
        raise ValueError("user_id parameter is required")

    result = await slack_api_call("conversations.list", {
        "types": "im",
        "limit": 1000,
    })
    channels = result.get("channels", [])

    found = None
    for ch in channels:
        if ch.get("user") == user_id:
            found = ch
            break

    return {
        "ok": True,
        "found": found is not None,
        "user_id": user_id,
        "channel": found,
        "total_channels_scanned": len(channels),
    }


async def get_channel_history(
    channel: str,
    channel_name: str | None = None,
    limit: int = 20,
    cursor: str | None = None,
    **_kwargs: Any,
) -> dict[str, Any]:
    """Get recent messages from a Slack channel.

    Dual-API fallback:
    1. Try conversations.history (requires channel membership)
    2. On access errors, fall back to search.messages with in:#channel
    """
    resolved_channel = channel
    clean_name = channel_name.lstrip("#") if channel_name else None

    # Resolve channel name to ID if needed
    if not resolved_channel and clean_name:
        try:
            resolved = await find_channel(
                channel_name=clean_name,
            )
            resolved_channel = (resolved.get("channel") or {}).get("id", "")
        except Exception:
            pass

    # Try conversations.history first
    if resolved_channel:
        try:
            params: dict[str, Any] = {
                "channel": resolved_channel,
                "limit": limit,
            }
            if cursor:
                params["cursor"] = cursor

            result = await slack_api_call("conversations.history", params)
            return {
                "ok": True,
                "channel": resolved_channel,
                "channel_name": clean_name,
                "has_more": bool(result.get("has_more")),
                "messages": result.get("messages", []),
                "response_metadata": result.get("response_metadata"),
                "method": "conversations.history",
            }
        except RuntimeError as e:
            error_msg = str(e)
            is_access_error = any(
                code in error_msg
                for code in ("channel_not_found", "not_in_channel", "missing_scope")
            )
            if not is_access_error:
                raise
            logger.debug(
                "conversations.history failed, falling back to search.messages: %s",
                error_msg,
            )

    # Fallback: search.messages with in:#channel-name
    search_channel = clean_name or resolved_channel
    if not search_channel:
        raise ValueError("channel or channel_name parameter is required")

    query = f"in:#{search_channel}"
    search_result = await slack_api_call("search.messages", {
        "query": query,
        "count": min(limit, 100),
        "sort": "timestamp",
        "sort_dir": "desc",
    })

    matches = search_result.get("messages", {}).get("matches", [])

    # Normalize search results to conversations.history format
    messages = [
        {
            "type": "message",
            "text": m.get("text", ""),
            "user": m.get("user"),
            "ts": m.get("ts"),
            "channel": (m.get("channel") or {}).get("id"),
            "permalink": m.get("permalink"),
            "username": m.get("username"),
        }
        for m in matches
    ]

    paging = search_result.get("messages", {}).get("paging", {})
    return {
        "ok": True,
        "channel": resolved_channel or search_channel,
        "channel_name": clean_name,
        "has_more": paging.get("total", 0) > len(messages),
        "messages": messages,
        "response_metadata": paging,
        "method": "search.messages",
        "note": (
            "Used search.messages fallback (enterprise-wide). "
            "Results may not include full history."
        ),
    }


async def get_dm_messages(
    other_user_id: str,
    sender_user_id: str | None = None,
    limit: int = 20,
    **_kwargs: Any,
) -> dict[str, Any]:
    """Get DM messages with a specific Slack user.

    Optionally filter to messages sent by a specific sender.
    """
    if not other_user_id:
        raise ValueError("other_user_id parameter is required")

    dm_lookup = await find_dm_channel(user_id=other_user_id)
    if not dm_lookup.get("found") or not dm_lookup.get("channel", {}).get("id"):
        return {
            "ok": True,
            "found": False,
            "other_user_id": other_user_id,
            "sender_user_id": sender_user_id,
            "channel": None,
            "messages": [],
        }

    dm_channel_id = dm_lookup["channel"]["id"]
    history = await get_channel_history(channel=dm_channel_id, limit=limit)

    all_messages = history.get("messages", [])
    if sender_user_id:
        filtered = [m for m in all_messages if m.get("user") == sender_user_id]
    else:
        filtered = all_messages

    return {
        "ok": True,
        "found": True,
        "other_user_id": other_user_id,
        "sender_user_id": sender_user_id,
        "channel": dm_lookup["channel"],
        "messages": filtered[:limit],
        "total_messages_before_filter": len(all_messages),
        "total_messages_after_filter": len(filtered),
        "has_more": history.get("has_more", False),
    }
