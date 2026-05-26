"""Employee endpoints (CRUD only — AI features in intelligence_routes)."""

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter()


@router.get("")
@router.get("/")
async def list_employees(
    request: Request,
    type: str | None = Query(default=None, alias="type"),
    team_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
):
    svc = request.app.state.data_service
    return {"data": svc.get_employees(type_filter=type, team_id=team_id, status=status)}


@router.get("/{employee_id}")
async def get_employee(request: Request, employee_id: str):
    svc = request.app.state.data_service
    employee = svc.get_employee(employee_id)
    if not employee:
        raise HTTPException(404, f"Employee {employee_id} not found")
    return {"data": employee}


@router.get("/{employee_id}/task-queue")
async def get_task_queue(request: Request, employee_id: str):
    svc = request.app.state.data_service
    queue = svc.get_task_queue(employee_id)
    return {"data": queue}
