"""Health and config endpoints."""

from fastapi import APIRouter, Request

# v6 defensive marker (I11): clients use the ``service`` field to distinguish
# an OpenTeam server from an impostor process that happens to also expose
# ``/api/health`` on the same port (R5 mitigation).
SERVICE_MARKER = "openteam"

router = APIRouter()


@router.get("/health")
async def health_check(request: Request):
    mode = getattr(request.app.state, "mode", "mock")
    svc = getattr(request.app.state, "data_service", None)
    has_real_sessions = svc is not None and hasattr(svc, "create_session")
    # Round-9 cleanup: use the public session_store accessor instead of
    # reaching into _session_store. Aligns with the docstring in
    # RealSessionDataService.get_session_dir which discourages that pattern.
    server_name = ""
    if svc is not None and hasattr(svc, "session_store"):
        server_name = getattr(svc.session_store, "server_name", "")
    return {
        "status": "ok",
        "service": SERVICE_MARKER,   # I11 — clients assert this matches "openteam"
        "mode": mode,
        "real_sessions": has_real_sessions,
        "version": "0.1.0",
        "server_name": server_name,
    }


@router.get("/config")
async def get_config(request: Request):
    mode = getattr(request.app.state, "mode", "mock")
    svc = getattr(request.app.state, "data_service", None)
    has_real_sessions = svc is not None and hasattr(svc, "create_session")
    return {
        "data": {
            "mode": mode,
            "real_sessions": has_real_sessions,
            "features": [
                "teams", "projects", "tasks", "employees",
                "conversations", "sprints", "intelligence",
            ],
        }
    }
