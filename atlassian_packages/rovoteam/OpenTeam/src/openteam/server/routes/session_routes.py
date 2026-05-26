"""Manager session endpoints."""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter()


class CreateSessionRequest(BaseModel):
    title: str | None = None


class SendMessageRequest(BaseModel):
    message: str


# ── v6 unified frontend session protocol ────────────────────────────────────
class AttachSessionRequest(BaseModel):
    """Request body for ``POST /api/sessions/attach``."""

    external_id: str = Field(
        ..., description="Prefix-validated external session id (e.g. rovodev-<uuid4>)."
    )
    frontend_id: str | None = Field(
        None,
        description="Optional frontend tag; defaults to the parsed prefix.",
    )
    frontend_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Opaque key/value pairs persisted alongside the session.",
    )
    title: str | None = None


class AttachSessionResponse(BaseModel):
    """Response body for ``POST /api/sessions/attach``."""

    session_id: str
    session_root: str
    created: bool


def _make_timestamp() -> str:
    """Generate ISO 8601 UTC timestamp."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@router.get("")
@router.get("/")
async def list_sessions(request: Request):
    svc = request.app.state.data_service
    return {"data": svc.get_sessions()}


@router.get("/{session_id}")
async def get_session(request: Request, session_id: str):
    svc = request.app.state.data_service
    session = svc.get_session(session_id)
    if not session:
        raise HTTPException(404, f"Session {session_id} not found")
    return {"data": session}


@router.post("")
@router.post("/")
async def create_session(
    request: Request, body: CreateSessionRequest = CreateSessionRequest()
):
    svc = request.app.state.data_service
    if not hasattr(svc, "create_session"):
        raise HTTPException(400, "Session creation not available in mock mode")
    session = svc.create_session(title=body.title)
    return {"data": session}


@router.post("/attach", response_model=AttachSessionResponse)
async def attach_session(
    request: Request, body: AttachSessionRequest,
) -> AttachSessionResponse:
    """Attach to or create a session by external_id (v6 unified frontend protocol).

    Idempotent: the same ``external_id`` always returns the same session
    (``created=False`` on the second call). This is the SOLE HTTP path that
    creates frontend-prefixed sessions (e.g. ``rovodev-...``), making the
    server the single writer for session creation (Invariant I9).

    Validates ``external_id`` via the prefix whitelist
    (:func:`openteam.server.services.session_store.validate_external_id`);
    bad prefixes return HTTP 400.

    Mock-mode safety (Invariant I18): returns HTTP 400 when the data service
    is the mock variant (no ``attach_or_create_session`` capability).
    """
    # Lazy import — keeps the route registration import-time light and
    # mirrors the pattern used elsewhere in this module.
    from openteam.server.services.session_store import validate_external_id

    svc = request.app.state.data_service
    # Capability check on the route layer (mock_data_service lacks attach).
    # Round-9 C4 fix: the predicate matches the actual call path we use below.
    if not hasattr(svc, "attach_or_create_session"):
        raise HTTPException(400, "Session attach not available in mock mode")

    try:
        prefix, _ = validate_external_id(body.external_id)
    except ValueError as e:
        raise HTTPException(400, str(e))

    # Detect created-vs-existing BEFORE the idempotent call. Two HTTP requests
    # racing here would both observe the same final state (one returns
    # created=True, the other created=False) thanks to the asyncio event-loop
    # serialisation of a single uvicorn worker (Invariant I20).
    existing = svc.get_session(body.external_id)
    created = existing is None

    session = svc.attach_or_create_session(
        external_id=body.external_id,
        frontend_id=body.frontend_id or prefix,
        frontend_metadata=body.frontend_metadata,
        title=body.title,
    )
    return AttachSessionResponse(
        session_id=session["id"],
        # Use the public DataService accessor; never reach into _session_store.
        session_root=str(svc.get_session_dir(session["id"])),
        created=created,
    )


@router.delete("/{session_id}")
async def delete_session(request: Request, session_id: str):
    svc = request.app.state.data_service
    if not hasattr(svc, "delete_session"):
        raise HTTPException(400, "Session deletion not available in mock mode")
    if not svc.delete_session(session_id):
        raise HTTPException(404, f"Session {session_id} not found")
    # Evict per-session inferencer to free memory
    conv_svc = getattr(request.app.state, "conversation_service", None)
    if conv_svc and hasattr(conv_svc, "evict_session_inferencer"):
        conv_svc.evict_session_inferencer(session_id)
    return {"data": {"deleted": True}}


@router.get("/{session_id}/turns/{turn_number}")
async def get_turn_data(request: Request, session_id: str, turn_number: int):
    """Fetch per-turn prompt metadata (template, feed, rendered prompt).

    Used by the frontend "View Prompt" button for history messages.
    turn_number is 1-based (first assistant message = turn 1).
    """
    svc = request.app.state.data_service
    if not hasattr(svc, "get_turn_data"):
        raise HTTPException(400, "Turn data not available in mock mode")
    data = svc.get_turn_data(session_id, turn_number)
    # Welcome message (turn 1) and other non-LLM turns have no saved prompt data.
    # Return graceful empty payload instead of 404 so the UI can show a friendly
    # "no prompt data" message rather than a console error.
    if data is None:
        return {"data": {
            "rendered_prompt": "",
            "template_source": "",
            "note": f"No prompt data for turn {turn_number} (likely a welcome or non-LLM turn)",
        }}
    return {"data": data}


@router.post("/{session_id}/messages")
async def send_message(request: Request, session_id: str, body: SendMessageRequest):
    """Send a user message to a session and get an AI response.

    Flow:
    1. Validate session exists
    2. Append user message to session
    3. Call ConversationService.get_response()
    4. Append assistant response to session
    5. Return both messages

    User message is persisted BEFORE calling LLM — if the LLM call fails,
    the user's message is still saved and an error message is appended.
    """
    svc = request.app.state.data_service
    conversation_svc = getattr(request.app.state, "conversation_service", None)

    # Check capabilities
    if not hasattr(svc, "append_message"):
        raise HTTPException(400, "Messaging not available in mock mode")
    if not conversation_svc:
        raise HTTPException(503, "Conversation service not initialized")

    # 1. Get current session
    session = svc.get_session(session_id)
    if not session:
        raise HTTPException(404, f"Session {session_id} not found")

    # 2. Build and append user message
    user_msg = {
        "id": f"msg-{uuid4().hex[:8]}",
        "role": "manager",
        "content": body.message,
        "timestamp": _make_timestamp(),
    }
    session = svc.append_message(session_id, user_msg)

    # 3. Get AI response
    try:
        response_text = await conversation_svc.get_response(session, body.message)
    except Exception as e:
        # Still saved the user message — append error as system message
        error_msg = {
            "id": f"msg-{uuid4().hex[:8]}",
            "role": "assistant",
            "agent_name": "Orchestrator",
            "agent_id": "orchestrator",
            "content": f"I encountered an error processing your request: {e!s}",
            "timestamp": _make_timestamp(),
            "error": True,
        }
        svc.append_message(session_id, error_msg)
        return {
            "data": {
                "user_message": user_msg,
                "assistant_message": error_msg,
                "error": True,
            }
        }

    # 4. Append assistant response
    assistant_msg = {
        "id": f"msg-{uuid4().hex[:8]}",
        "role": "assistant",
        "agent_name": "Orchestrator",
        "agent_id": "orchestrator",
        "content": response_text,
        "timestamp": _make_timestamp(),
    }
    svc.append_message(session_id, assistant_msg)

    # 5. Return both messages
    return {"data": {"user_message": user_msg, "assistant_message": assistant_msg}}
