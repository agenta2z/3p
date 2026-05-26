"""Conversation endpoints."""

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter()


@router.get("")
@router.get("/")
async def list_conversations(
    request: Request,
    participant_id: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
):
    svc = request.app.state.data_service
    return {"data": svc.get_conversations(participant_id=participant_id, project_id=project_id)}


@router.get("/{conversation_id}")
async def get_conversation(request: Request, conversation_id: str):
    svc = request.app.state.data_service
    conversation = svc.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(404, f"Conversation {conversation_id} not found")
    return {"data": conversation}
