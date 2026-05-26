"""Server meta routes — backend listing and per-session backend selection.

Endpoints:
  - GET  /api/server/backends           Lists registered backends with availability.
  - POST /api/sessions/{sid}/backend    Per-session backend choice.

The session-backend route is mounted under ``/api/sessions/...`` rather
than ``/api/server/...`` because the resource is the session, not the
server. The choice persists in session metadata via
``ConversationService.set_session_backend``.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


class BackendChoice(BaseModel):
    backend: str
    model: Optional[str] = None


def _conv_svc(request: Request):
    svc = getattr(request.app.state, "conversation_service", None)
    if svc is None:
        raise HTTPException(
            status_code=503,
            detail="ConversationService not initialized (mock mode without --real-sessions)",
        )
    return svc


@router.get("/server/backends")
async def list_backends(request: Request) -> dict:
    """List all registered inferencer backends with availability state."""
    from openteam.server.backends import get_registry

    registry = get_registry()
    descriptors = registry.list_backends()

    # Default backend/model — read from the live conversation service if
    # available; otherwise fall back to whatever app.state was set with.
    svc = getattr(request.app.state, "conversation_service", None)
    if svc is not None:
        default_backend = getattr(svc, "_llm_backend", None) or "mock"
        default_model = getattr(svc, "_llm_model", None)
    else:
        default_backend = getattr(request.app.state, "llm_backend", None) or "mock"
        default_model = getattr(request.app.state, "llm_model", None)

    backends_payload = []
    for name in sorted(descriptors):
        desc = descriptors[name]
        backends_payload.append({
            "name": name,
            "display_name": desc.display_name,
            "description": desc.description,
            "available": desc.is_available(),
            "status_message": desc.status_message(),
            "default_model": desc.default_model,
        })

    return {
        "default_backend": default_backend,
        "default_model": default_model,
        "backends": backends_payload,
    }


@router.post("/sessions/{session_id}/backend")
async def set_session_backend(
    session_id: str, choice: BackendChoice, request: Request
) -> dict:
    """Set the LLM backend for a specific session.

    Returns 400 with the available list if the backend name is unknown.
    Evicts any cached inferencer so the next turn rebuilds.
    """
    svc = _conv_svc(request)

    # Only operate on real sessions — the conversation service must have a
    # session_store wired (i.e., the server was started with --real-sessions).
    if getattr(svc, "_session_store", None) is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Server has no session_store (started without --real-sessions). "
                "Per-session backend selection requires persistent sessions."
            ),
        )

    try:
        updated = svc.set_session_backend(session_id, choice.backend, choice.model)
    except KeyError as e:
        from openteam.server.backends import get_registry
        available = sorted(get_registry().list_backends())
        raise HTTPException(
            status_code=400,
            detail={"error": str(e), "available": available},
        )

    if updated is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    return {
        "session_id": session_id,
        "llm_backend": updated.get("llm_backend"),
        "llm_model": updated.get("llm_model"),
    }
