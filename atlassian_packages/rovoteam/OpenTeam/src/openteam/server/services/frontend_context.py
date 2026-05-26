"""Frontend session context resolution (v6 unified frontend protocol).

Single place where the subprocess-side env-var protocol is decoded into a
``session_context`` dict suitable for executors / workspace allocators. Used
by:

- :mod:`openteam.server.services.tool_cli` — populates ``session_context``
  passed to ``execute_fn(arguments, session_context)`` in CLI-invoked tools.
- :mod:`openteam.mcp_server.context` — same logic for in-process MCP tool
  calls (delegates here so MCP and CLI stay in sync).

Environment-variable contract (set by the frontend, read here):

  OPENTEAM_MODE             "server" | "subprocess" (Invariant I15; default "subprocess")
  OPENTEAM_SERVER_DIR       absolute path to the live server's ``server_<TS>_<uuid>``
  OPENTEAM_SESSION_ID       external session id (e.g. ``rovodev-<uuid4>``)
  OPENTEAM_FRONTEND_ID      frontend tag (defaults to parsed prefix)
  OPENTEAM_FRONTEND_METADATA  JSON object (optional)

Mode discipline (Invariant I9 + I15):

  Server Mode — TUI has already POSTed to ``/api/sessions/attach`` and the
    session is known to exist. Subprocess calls ``get_session`` only
    (read-only). If the session is unexpectedly missing the subprocess
    FAILS FAST with ``RuntimeError`` rather than silently creating a second
    writer (which would re-introduce the ``_update_index`` race I9 was
    designed to eliminate).

  Subprocess Mode — no live server reachable. Subprocess calls
    ``attach_or_create_session`` directly via the filesystem. No race
    because there's only one writer (us).
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


def build_frontend_session_context(
    *,
    frontend_id: Optional[str] = None,
    frontend_session_id: Optional[str] = None,
    frontend_metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Decode env vars + kwargs into a session_context dict.

    Returns an empty dict (``{}``) when no frontend context is present
    (``OPENTEAM_SESSION_ID`` unset OR ``OPENTEAM_SERVER_DIR`` unset). Callers
    interpret this as "Path A fallback — workspace lands under
    ``<runtime>/tasks/<tool>/`` (today's standalone behavior)".

    Args:
        frontend_id: optional override for the frontend tag. If None, falls
            back to ``OPENTEAM_FRONTEND_ID`` env, then to the parsed prefix
            of the session id.
        frontend_session_id: optional bare id (no prefix). If set, takes
            precedence over the env-supplied id. Used by MCP callers that
            already split prefix from remainder.
        frontend_metadata: optional metadata dict. If None, falls back to
            ``OPENTEAM_FRONTEND_METADATA`` env (JSON-decoded).

    Returns:
        ``{}`` (Path A fallback) OR a dict with at least:
            ``session_id``, ``session_root``, plus any auxiliary env-derived
            fields the existing context layer already populates.
    """
    # Mode discipline (I15): one of {"server", "subprocess"}; default to
    # subprocess so a stray invocation without OPENTEAM_MODE behaves like
    # the legacy Path A semantics (no surprises for CI / direct CLI users).
    mode = os.environ.get("OPENTEAM_MODE", "subprocess")
    if mode not in ("server", "subprocess"):
        logger.warning(
            "[frontend_context] invalid OPENTEAM_MODE=%r; treating as subprocess",
            mode,
        )
        mode = "subprocess"

    raw_session_id = frontend_session_id or os.environ.get("OPENTEAM_SESSION_ID")
    if not raw_session_id:
        return {}

    # Compose external_id from raw_session_id + frontend_id, with the
    # convention that an already-prefixed id passes through as-is.
    # Round-9 C3 fix: validate_external_id raises ValueError on failure;
    # there is no _safe boolean variant. Wrap in try/except.
    from openteam.server.services.session_store import validate_external_id

    composed_external_id: str
    already_prefixed = False
    if "-" in raw_session_id:
        try:
            validate_external_id(raw_session_id)
            already_prefixed = True
        except ValueError:
            already_prefixed = False

    if already_prefixed:
        composed_external_id = raw_session_id
    else:
        # Bare id: compose with frontend_id (kwarg wins over env over default).
        fid = (
            frontend_id
            or os.environ.get("OPENTEAM_FRONTEND_ID")
            or "rovodev"
        )
        composed_external_id = f"{fid}-{raw_session_id}"
        # Validate the composed id; if it still fails, fall back to Path A
        # rather than crashing the subprocess.
        try:
            validate_external_id(composed_external_id)
        except ValueError as e:
            logger.warning(
                "[frontend_context] composed external_id %r failed validation (%s); "
                "falling back to Path A",
                composed_external_id, e,
            )
            return {}

    server_dir = os.environ.get("OPENTEAM_SERVER_DIR")
    if not server_dir:
        # Frontend supplied an id but no server_dir — Path A fallback.
        # Subprocess can't reach a SessionStore without a server_dir.
        return {}

    # Lazy import — keeps top-of-module light and matches the pattern used
    # in mcp_server/context.py (this module is imported eagerly by tool_cli).
    from openteam.server.services.session_store import SessionStore

    server_path = Path(server_dir).resolve()
    # I7: SessionStore constructor accepts (runtime_root, *, resume_server=...).
    # The runtime_root is two levels up from a server_dir like
    # <runtime>/servers/server_<TS>_<uuid>/.
    store = SessionStore(
        runtime_root=server_path.parent.parent,
        resume_server=server_path.name,
    )

    # Resolve metadata from kwarg → env JSON.
    if frontend_metadata is None:
        raw_meta = os.environ.get("OPENTEAM_FRONTEND_METADATA", "")
        if raw_meta:
            try:
                frontend_metadata = json.loads(raw_meta)
            except json.JSONDecodeError as e:
                logger.warning(
                    "[frontend_context] OPENTEAM_FRONTEND_METADATA isn't valid JSON: %s",
                    e,
                )
                frontend_metadata = {}
        else:
            frontend_metadata = {}

    # Mode branch (I9 + I15).
    if mode == "server":
        # The TUI has already created the session via POST /api/sessions/attach.
        # Subprocess is read-only — never create.
        session = store.get_session(composed_external_id)
        if session is None:
            # Server mode + missing session = HARD ERROR. Calling
            # attach_or_create_session here would make the subprocess a
            # second writer (violating I9). Either the server crashed
            # between TUI POST and subprocess spawn (operator should
            # investigate) or OPENTEAM_SESSION_ID was tampered with
            # (security concern). Surface loudly.
            raise RuntimeError(
                f"[I9] OPENTEAM_MODE=server but session "
                f"{composed_external_id!r} missing in {server_dir!r}. "
                f"Server may have crashed after TUI POST. Restart your TUI "
                f"(or use --no-openteam-server to force Subprocess Mode)."
            )
    else:
        # Subprocess Mode — single writer (us); race-free because no server.
        # Default frontend_id to parsed prefix to match the route handler.
        prefix, _ = validate_external_id(composed_external_id)
        session = store.attach_or_create_session(
            external_id=composed_external_id,
            frontend_id=frontend_id or os.environ.get("OPENTEAM_FRONTEND_ID") or prefix,
            frontend_metadata=frontend_metadata,
        )

    return {
        "session_id": session["id"],
        "session_root": str(store.get_session_dir(session["id"])),
        "external_id": composed_external_id,
        "frontend_id": session.get("frontend_id"),
    }
