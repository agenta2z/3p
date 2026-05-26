"""Manager session endpoints."""

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


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
