"""OpenTeam API Server — FastAPI backend for the AI Company Dashboard.

Supports two modes:
- "mock" (default): Serves fixture JSON data for all views
- "live" (future): Connects to real agent orchestration APIs

Usage:
    python run_server.py                    # Mock mode on port 8000
    python run_server.py --port 9000        # Custom port
    uvicorn server.main:app --reload        # Development with hot reload
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from server.routes.health_routes import router as health_router
from server.routes.team_routes import router as team_router
from server.routes.project_routes import router as project_router
from server.routes.task_routes import router as task_router
from server.routes.employee_routes import router as employee_router
from server.routes.conversation_routes import router as conversation_router
from server.routes.dashboard_routes import router as dashboard_router
from server.routes.intelligence_routes import router as intelligence_router
from server.routes.session_routes import router as session_router
from server.routes.role_skill_routes import router as role_skill_router
from server.services.data_service import MockDataService
from server.services.intelligence_service import MockIntelligenceService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize services at startup, cleanup at shutdown."""
    fixtures_dir = Path(__file__).parent / "fixtures"
    mode = getattr(app.state, "mode", "mock")

    if mode == "mock":
        data_svc = MockDataService(fixtures_dir)
        intel_svc = MockIntelligenceService(fixtures_dir)
    else:
        raise ValueError(f"Unsupported mode: {mode}. Only 'mock' is implemented.")

    app.state.data_service = data_svc
    app.state.intelligence_service = intel_svc

    logger.info("OpenTeam API started in %s mode", mode)
    yield
    logger.info("OpenTeam API shutting down")


# Create FastAPI app
app = FastAPI(
    title="OpenTeam",
    description="AI Company Dashboard — Backend API",
    version="0.1.0",
    lifespan=lifespan,
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )


# CORS middleware (allows React dev server)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(health_router, prefix="/api", tags=["system"])
app.include_router(team_router, prefix="/api/teams", tags=["teams"])
app.include_router(project_router, prefix="/api/projects", tags=["projects"])
app.include_router(task_router, prefix="/api/tasks", tags=["tasks"])
app.include_router(employee_router, prefix="/api/employees", tags=["employees"])
app.include_router(conversation_router, prefix="/api/conversations", tags=["conversations"])
app.include_router(dashboard_router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(intelligence_router, prefix="/api/intelligence", tags=["intelligence"])
app.include_router(session_router, prefix="/api/sessions", tags=["sessions"])
app.include_router(role_skill_router, prefix="/api/role-skills", tags=["role-skills"])


# SPA fallback — only enabled when the build directory exists (production).
# In development, CRA dev server on port 3000 serves the frontend and
# proxies /api requests here, so the catch-all is not needed.
frontend_path = Path(__file__).parent.parent / "ui" / "build"

if frontend_path.exists() and (frontend_path / "index.html").exists():
    # Mount static files first (CSS, JS, images)
    if (frontend_path / "static").exists():
        app.mount(
            "/static",
            StaticFiles(directory=str(frontend_path / "static")),
            name="static",
        )

    @app.get("/{full_path:path}", response_model=None, include_in_schema=False)
    async def serve_spa(full_path: str):
        """Serve the React app (SPA fallback to index.html)."""
        if full_path.startswith("api") or full_path.startswith("ws"):
            return JSONResponse(status_code=404, content={"detail": "Not found"})

        file_path = frontend_path / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))

        return FileResponse(str(frontend_path / "index.html"))
