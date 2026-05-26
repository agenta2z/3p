"""Organization, collaboration, and ACL permission endpoints."""

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


@router.get("")
@router.get("/")
async def list_organizations(request: Request):
    svc = request.app.state.data_service
    return {"data": svc.get_organizations()}


@router.get("/{org_id}")
async def get_organization(request: Request, org_id: str):
    svc = request.app.state.data_service
    org = svc.get_organization(org_id)
    if not org:
        raise HTTPException(404, f"Organization {org_id} not found")
    return {"data": org}


@router.get("/{org_id}/tree")
async def get_org_tree(request: Request, org_id: str):
    svc = request.app.state.data_service
    tree = svc.get_org_tree(org_id)
    if not tree:
        raise HTTPException(404, f"Organization {org_id} not found")
    return {"data": tree}


@router.get("/{org_id}/default-acl")
async def get_org_default_acl(request: Request, org_id: str):
    svc = request.app.state.data_service
    acl = svc.get_org_default_acl(org_id)
    if not acl:
        raise HTTPException(404, f"No default ACL for org {org_id}")
    return {"data": acl}


# Employee-scoped org endpoints (mounted under /api/employees in main.py)
employee_org_router = APIRouter()


@employee_org_router.get("/{employee_id}/org")
async def get_employee_org(request: Request, employee_id: str):
    svc = request.app.state.data_service
    org = svc.get_employee_org(employee_id)
    if not org:
        raise HTTPException(404, f"No org membership for employee {employee_id}")
    return {"data": org}


@employee_org_router.get("/{employee_id}/collaboration")
async def get_collaboration_config(request: Request, employee_id: str):
    svc = request.app.state.data_service
    config = svc.get_collaboration_config(employee_id)
    if not config:
        return {"data": {"employee_id": employee_id, "default_cross_org": "request", "rules": []}}
    return {"data": config}


@employee_org_router.put("/{employee_id}/collaboration")
async def update_collaboration_config(request: Request, employee_id: str):
    svc = request.app.state.data_service
    body = await request.json()
    result = svc.update_collaboration_config(employee_id, body)
    return {"data": result}


@employee_org_router.get("/{employee_id}/acl")
async def get_employee_acl(request: Request, employee_id: str):
    svc = request.app.state.data_service
    acl = svc.get_employee_acl(employee_id)
    if not acl:
        # Return empty ACL with org defaults if no explicit ACL exists
        org_membership = svc.get_employee_org(employee_id)
        if org_membership:
            org_acl = svc.get_org_default_acl(org_membership["org_id"])
            if org_acl:
                return {"data": {
                    "employee_id": employee_id,
                    "inherited_from_org": True,
                    "entries": org_acl.get("entries", []),
                }}
        return {"data": {"employee_id": employee_id, "inherited_from_org": True, "entries": []}}
    return {"data": acl}


@employee_org_router.put("/{employee_id}/acl")
async def update_employee_acl(request: Request, employee_id: str):
    svc = request.app.state.data_service
    body = await request.json()
    result = svc.update_employee_acl(employee_id, body)
    return {"data": result}


@employee_org_router.get("/{employee_id}/crash-events")
async def get_crash_events(request: Request, employee_id: str):
    svc = request.app.state.data_service
    return {"data": svc.get_crash_events(employee_id)}


@employee_org_router.get("/{employee_id}/issue-events")
async def get_issue_events(request: Request, employee_id: str):
    svc = request.app.state.data_service
    return {"data": svc.get_issue_events(employee_id)}
