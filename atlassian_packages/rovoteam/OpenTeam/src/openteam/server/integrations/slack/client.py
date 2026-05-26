"""Async Slack Web API client with token management and retry logic.

Ported from openclaw extensions/slack-rts/index.ts.

Token priority:
1. SLACK_XOXC_TOKEN + SLACK_XOXD_TOKEN_ENCODED env vars
2. Proximity server at PROXIMITY_URL (fetches fresh xoxc/xoxd tokens)
3. SLACK_USER_TOKEN env var (fallback)

Auto-retries on auth failures by invalidating cached tokens and
fetching fresh ones from the proximity server.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SLACK_API_BASE = "https://slack.com/api"


@dataclass
class _TokenCache:
    token: str | None = None
    cookie: str | None = None
    expires_at: float = 0.0


_token_cache = _TokenCache()

# Auth error codes that trigger a token refresh
_AUTH_ERROR_CODES = {"invalid_auth", "token_expired", "token_revoked"}


async def _fetch_tokens_from_proximity() -> dict[str, str | None] | None:
    """Fetch fresh xoxc/xoxd tokens from the proximity server."""
    proximity_url = os.environ.get("PROXIMITY_URL", "http://localhost:29576")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{proximity_url}/slack/tokens",
                params={"workspace": "atlassian.slack.com", "include_cookie": "true"},
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok"):
                raise ValueError(data.get("error", "Unknown error from proximity"))
            return {
                "token": data.get("xoxc"),
                "cookie": data.get("xoxd_encoded"),
            }
    except Exception as e:
        logger.debug("Failed to fetch tokens from proximity: %s", e)
        return None


def _get_slack_token_from_env() -> dict[str, str | None]:
    """Get Slack token from environment variables."""
    xoxc = os.environ.get("SLACK_XOXC_TOKEN")
    if xoxc:
        return {
            "token": xoxc,
            "cookie": os.environ.get("SLACK_XOXD_TOKEN_ENCODED"),
        }
    user_token = os.environ.get("SLACK_USER_TOKEN")
    if user_token:
        return {"token": user_token, "cookie": None}
    raise RuntimeError(
        "No Slack token found. Set SLACK_XOXC_TOKEN+SLACK_XOXD_TOKEN_ENCODED "
        "or SLACK_USER_TOKEN."
    )


async def _get_token_with_refresh() -> dict[str, str | None]:
    """Get a valid Slack token, using cache and proximity refresh."""
    global _token_cache
    now = time.time()

    if _token_cache.token and now < _token_cache.expires_at:
        return {"token": _token_cache.token, "cookie": _token_cache.cookie}

    from_proximity = await _fetch_tokens_from_proximity()
    if from_proximity and from_proximity.get("token"):
        _token_cache = _TokenCache(
            token=from_proximity["token"],
            cookie=from_proximity.get("cookie"),
            expires_at=now + 3600,  # cache 1 hour
        )
        return from_proximity

    return _get_slack_token_from_env()


async def _do_slack_api_call(
    endpoint: str,
    params: dict[str, Any],
    token: str,
    cookie: str | None,
) -> dict[str, Any]:
    """Make a single Slack API GET request."""
    url = f"{SLACK_API_BASE}/{endpoint}"
    headers: dict[str, str] = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    if cookie:
        headers["Cookie"] = f"d={cookie}"

    filtered_params = {
        k: str(v) for k, v in params.items() if v is not None
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url, params=filtered_params, headers=headers)
        response.raise_for_status()
        return response.json()


async def slack_api_call(
    endpoint: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Make a Slack API call with automatic token refresh on auth failure.

    Args:
        endpoint: Slack API method (e.g., "search.messages").
        params: Query parameters for the API call.

    Returns:
        Parsed JSON response from the Slack API.

    Raises:
        RuntimeError: If the API call fails after retry.
    """
    global _token_cache
    if params is None:
        params = {}

    creds = await _get_token_with_refresh()
    token = creds["token"]
    cookie = creds.get("cookie")
    if not token:
        raise RuntimeError("No Slack token available")

    data = await _do_slack_api_call(endpoint, params, token, cookie)

    if data.get("ok"):
        return data

    # On auth failure, invalidate cache and retry with fresh tokens
    error_code = data.get("error", "")
    if error_code in _AUTH_ERROR_CODES:
        logger.warning("Slack token expired (%s), refreshing from proximity...", error_code)
        _token_cache = _TokenCache()

        fresh = await _fetch_tokens_from_proximity()
        if fresh and fresh.get("token"):
            _token_cache = _TokenCache(
                token=fresh["token"],
                cookie=fresh.get("cookie"),
                expires_at=time.time() + 3600,
            )
            retry_data = await _do_slack_api_call(
                endpoint, params, fresh["token"], fresh.get("cookie")
            )
            if retry_data.get("ok"):
                return retry_data
            raise RuntimeError(
                f"Slack API error: {retry_data.get('error', 'Unknown')} "
                f"(token refresh failed — restart Slack desktop)"
            )

    raise RuntimeError(f"Slack API error: {error_code or 'Unknown error'}")
