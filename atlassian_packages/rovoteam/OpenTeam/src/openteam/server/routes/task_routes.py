"""Task endpoints."""

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter()


@router.get("")
@router.get("/")
async def list_tasks(
    request: Request,
    project_id: str | None = Query(default=None),
    assignee_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    priority: str | None = Query(default=None),
):
    svc = request.app.state.data_service
    return {
        "data": svc.get_tasks(
            project_id=project_id,
            assignee_id=assignee_id,
            status=status,
            priority=priority,
        )
    }


@router.get("/{task_id}")
async def get_task(request: Request, task_id: str):
    svc = request.app.state.data_service
    task = svc.get_task(task_id)
    if not task:
        raise HTTPException(404, f"Task {task_id} not found")
    return {"data": task}


@router.get("/{task_id}/prediction")
async def get_task_prediction(request: Request, task_id: str):
    intel_svc = request.app.state.intelligence_service
    prediction = intel_svc.get_predictive_timeline(task_id)
    if not prediction:
        raise HTTPException(404, f"No prediction for task {task_id}")
    return {"data": prediction}
