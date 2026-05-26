"""Role skill pool endpoints."""

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


@router.get("")
@router.get("/")
async def get_all_role_skills(request: Request):
    svc = request.app.state.data_service
    return {"data": svc.get_role_skills()}


@router.get("/configs")
async def get_all_role_configs(request: Request):
    svc = request.app.state.data_service
    return {"data": svc.get_role_configs()}


@router.get("/configs/{role}")
async def get_role_config(request: Request, role: str):
    svc = request.app.state.data_service
    config = svc.get_role_config(role)
    if config is None:
        raise HTTPException(404, f"Role config '{role}' not found")
    return {"data": config}


@router.get("/{role}")
async def get_role_skill_pool(request: Request, role: str):
    svc = request.app.state.data_service
    pool = svc.get_role_skill_pool(role)
    if pool is None:
        raise HTTPException(404, f"Role '{role}' not found")
    return {"data": pool}
