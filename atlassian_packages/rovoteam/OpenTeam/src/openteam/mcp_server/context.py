"""Build session_context for in-process executor calls.

When the v6 unified frontend protocol env vars are set
(OPENTEAM_SERVER_DIR + OPENTEAM_SESSION_ID), this composes a full
session_context (session_id, session_root, ...) via
:func:`openteam.server.services.frontend_context.build_frontend_session_context`.
Otherwise falls back to today's behavior: ``task_id`` only + auxiliary env
vars (working_dir / cloud_id / etc.).
"""
from __future__ import annotations
import logging
import os
import uuid
from typing import Any

logger = logging.getLogger(__name__)

# Auxiliary env-var passthroughs (independent of the v6 session protocol).
# These are session-context fields the existing executors already read for
# their own purposes (working dir resolution, Atlassian auth, etc.).
_ENV_MAP = {
    "OPENTEAM_WORKING_DIR": "working_dir",
    "OPENTEAM_SERVER_DIR":  "server_dir",
    "OPENTEAM_CLOUD_ID":    "cloud_id",
    "OPENTEAM_UCT_TOKEN":   "uct_token",
    "OPENTEAM_EMAIL":       "email",
}


def build_session_context(
    *,
    frontend_id: str | None = None,
    frontend_session_id: str | None = None,
    frontend_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build session_context for MCP / in-process executor calls.

    v6 unified frontend protocol: when ``OPENTEAM_SESSION_ID`` +
    ``OPENTEAM_SERVER_DIR`` are present, delegate to the shared resolver
    so MCP and CLI agree on the (composed_external_id, session_root, mode)
    triple. Otherwise fall through to today's task-id-only context.

    Kwargs (all optional) override the corresponding env vars when the
    caller already has them in-hand (e.g., MCP tool layer parsing them
    out of the JSON-RPC request).
    """
    # Default skeleton — kept stable for back-compat with existing executors
    # that read ``task_id`` and ``interactive``.
    ctx: dict[str, Any] = {
        "task_id": f"mcp-{uuid.uuid4().hex[:8]}",
        "interactive": None,
    }
    # Auxiliary env-var passthroughs (working_dir, cloud_id, etc.)
    for env_key, ctx_key in _ENV_MAP.items():
        v = os.environ.get(env_key)
        if v:
            ctx[ctx_key] = v

    # v6 overlay: if frontend protocol env vars are present, merge in the
    # unified context (session_id, session_root, external_id, frontend_id).
    from openteam.server.services.frontend_context import build_frontend_session_context

    try:
        frontend_ctx = build_frontend_session_context(
            frontend_id=frontend_id,
            frontend_session_id=frontend_session_id,
            frontend_metadata=frontend_metadata,
        )
    except RuntimeError as e:
        # I9 fail-fast: surface as a logged error AND re-raise so the MCP
        # tool returns the error to the caller (rather than silently
        # ignoring the user's session intent).
        logger.error("[context] frontend session resolution failed: %s", e)
        raise

    ctx.update(frontend_ctx)
    return ctx
