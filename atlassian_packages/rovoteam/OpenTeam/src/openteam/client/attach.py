"""POST /api/sessions/attach helper. ``urllib`` (stdlib) only — no ``httpx`` dep.

Separate from ``supervisor.py`` so client consumers that only need discovery
don't pay for the HTTP attach surface, and so the supervisor stays free of
HTTP request/response handling.
"""
from __future__ import annotations

import dataclasses
import json
import urllib.error
import urllib.request
from typing import Any

from openteam.client.discovery import ServerHandle


@dataclasses.dataclass(frozen=True)
class AttachResult:
    """Response from ``POST /api/sessions/attach``."""

    session_id: str
    session_root: str        # absolute path on the server's filesystem
    created: bool            # True if freshly created, False if already existed


class AttachFailed(Exception):
    """HTTP error, timeout, or invalid response from ``/api/sessions/attach``.

    Callers (TUI slash handler) catch this and fall back to Subprocess Mode.
    """


def attach_session_via_http(
    handle: ServerHandle,
    *,
    external_id: str,
    frontend_id: str,
    frontend_metadata: dict[str, Any] | None = None,
    title: str | None = None,
    timeout_s: float = 5.0,
) -> AttachResult:
    """Synchronous POST. Idempotent: same ``external_id`` → same session.

    Raises:
        :class:`AttachFailed`: any of:
            - Network error (URLError / OSError / TimeoutError)
            - Server returned non-2xx (HTTPError, caught by URLError parent)
            - Response body isn't valid JSON
            - Response JSON missing required ``session_id`` / ``session_root`` / ``created``
    """
    body: dict[str, Any] = {
        "external_id": external_id,
        "frontend_id": frontend_id,
        "frontend_metadata": frontend_metadata or {},
    }
    if title is not None:
        body["title"] = title

    req = urllib.request.Request(
        f"{handle.http_endpoint}/api/sessions/attach",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read()
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise AttachFailed(
            f"POST {handle.http_endpoint}/api/sessions/attach failed: {e}"
        ) from e

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        raise AttachFailed(f"invalid JSON from /api/sessions/attach: {e}") from e

    # FastAPI route response model is bare (not wrapped in {"data": ...}).
    try:
        return AttachResult(
            session_id=payload["session_id"],
            session_root=payload["session_root"],
            created=bool(payload["created"]),
        )
    except KeyError as e:
        raise AttachFailed(
            f"missing required field in /api/sessions/attach response: {e}; "
            f"got keys={list(payload.keys())}"
        ) from e
