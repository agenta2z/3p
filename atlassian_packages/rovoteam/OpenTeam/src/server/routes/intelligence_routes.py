"""AI-native intelligence endpoints.

All AI reasoning features are grouped here, separate from CRUD routes.
These use IntelligenceService, not DataService.
"""

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter()


@router.get("/suggested-actions")
async def get_suggested_actions(
    request: Request,
    context: str = Query(default="projects", description="View context: projects|tasks|team|employees"),
):
    intel_svc = request.app.state.intelligence_service
    return {"data": intel_svc.get_suggested_actions(context)}


@router.get("/employees/{employee_id}/thinking")
async def get_thinking_state(request: Request, employee_id: str):
    intel_svc = request.app.state.intelligence_service
    state = intel_svc.get_thinking_state(employee_id)
    if not state:
        raise HTTPException(404, f"No thinking state for {employee_id}")
    return {"data": state}


@router.get("/employees/{employee_id}/decisions")
async def get_decisions(request: Request, employee_id: str):
    intel_svc = request.app.state.intelligence_service
    return {"data": intel_svc.get_decisions(employee_id)}


@router.get("/employees/{employee_id}/autonomy")
async def get_autonomy(request: Request, employee_id: str):
    intel_svc = request.app.state.intelligence_service
    autonomy = intel_svc.get_autonomy(employee_id)
    if not autonomy:
        raise HTTPException(404, f"No autonomy config for {employee_id}")
    return {"data": autonomy}


@router.get("/workload-balance")
async def get_workload_balance(request: Request):
    intel_svc = request.app.state.intelligence_service
    return {"data": intel_svc.get_workload_balance()}
