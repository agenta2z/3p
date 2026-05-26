"""Dashboard summary endpoint."""

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/summary")
async def dashboard_summary(request: Request):
    svc = request.app.state.data_service
    return {"data": svc.get_dashboard_summary()}
