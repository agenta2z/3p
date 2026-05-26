"""Project endpoints."""

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter()


@router.get("")
@router.get("/")
async def list_projects(
    request: Request,
    status: str | None = Query(default=None),
    team_id: str | None = Query(default=None),
):
    svc = request.app.state.data_service
    return {"data": svc.get_projects(status=status, team_id=team_id)}


@router.get("/{project_id}")
async def get_project(request: Request, project_id: str):
    svc = request.app.state.data_service
    project = svc.get_project(project_id)
    if not project:
        raise HTTPException(404, f"Project {project_id} not found")
    return {"data": project}


@router.get("/{project_id}/sprint")
async def get_sprint(
    request: Request,
    project_id: str,
    sprint_number: int | None = Query(default=None),
):
    svc = request.app.state.data_service
    sprint = svc.get_sprint(project_id, sprint_number)
    if not sprint:
        raise HTTPException(404, f"Sprint not found for project {project_id}")
    return {"data": sprint}
