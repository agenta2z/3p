"""Team endpoints."""

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter()


@router.get("")
@router.get("/")
async def list_teams(request: Request):
    svc = request.app.state.data_service
    return {"data": svc.get_teams()}


@router.get("/{team_id}")
async def get_team(request: Request, team_id: str, resolve: str = Query(default="")):
    svc = request.app.state.data_service
    resolve_fields = [r.strip() for r in resolve.split(",") if r.strip()] if resolve else None
    team = svc.get_team(team_id, resolve=resolve_fields)
    if not team:
        raise HTTPException(404, f"Team {team_id} not found")
    return {"data": team}
