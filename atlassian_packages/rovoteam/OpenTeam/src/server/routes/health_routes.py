"""Health and config endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    return {"status": "ok", "mode": "mock", "version": "0.1.0"}


@router.get("/config")
async def get_config():
    return {
        "data": {
            "mode": "mock",
            "features": [
                "teams", "projects", "tasks", "employees",
                "conversations", "sprints", "intelligence",
            ],
        }
    }
