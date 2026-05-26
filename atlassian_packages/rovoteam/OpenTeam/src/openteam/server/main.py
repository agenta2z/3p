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

from openteam.server.routes.health_routes import router as health_router
from openteam.server.routes.team_routes import router as team_router
from openteam.server.routes.project_routes import router as project_router
from openteam.server.routes.task_routes import router as task_router
from openteam.server.routes.task_topology_routes import router as task_topology_router
from openteam.server.routes.employee_routes import router as employee_router
from openteam.server.routes.conversation_routes import router as conversation_router
from openteam.server.routes.dashboard_routes import router as dashboard_router
from openteam.server.routes.intelligence_routes import router as intelligence_router
from openteam.server.routes.session_routes import router as session_router
from openteam.server.routes.role_skill_routes import router as role_skill_router
from openteam.server.routes.manager_websocket_routes import router as manager_ws_router
from openteam.server.routes.org_routes import router as org_router, employee_org_router
from openteam.server.routes.meta_routes import router as meta_router
from openteam.server.services.data_service import MockDataService
from openteam.server.services.intelligence_service import MockIntelligenceService

logger = logging.getLogger(__name__)


def _load_env_file(path: Path) -> None:
    """Load key=value pairs from a .env file into os.environ.

    Skips blank lines and comments. Does NOT override existing env vars
    so shell exports (e.g. from ~/.zshrc) always take precedence.
    """
    import os

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")  # strip optional quotes
        if key and key not in os.environ:
            os.environ[key] = value


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize services at startup, cleanup at shutdown."""
    # Load .env from server directory (RovoChat credentials, Slack tokens, etc.)
    _env_file = Path(__file__).parent / ".env"
    if _env_file.is_file():
        _load_env_file(_env_file)
        logger.info("Loaded environment from %s", _env_file)

    fixtures_dir = Path(__file__).parent / "fixtures"
    mode = getattr(app.state, "mode", "mock")

    real_sessions_dir = getattr(app.state, "real_sessions_dir", None)

    if mode == "mock":
        if real_sessions_dir:
            from openteam.server.services.session_store import SessionStore
            from openteam.server.services.data_service import RealSessionDataService
            from openteam.server.services.conversation_service import ConversationService

            resume_server = getattr(app.state, "resume_server", None)
            session_store = SessionStore(
                real_sessions_dir, resume_server=resume_server
            )

            # Persist all logs to server workspace for post-mortem analysis.
            # Each server run gets its own server.log alongside session/turn/task data.
            _log_file = session_store.server_dir / "server.log"
            _file_handler = logging.FileHandler(str(_log_file), encoding="utf-8")
            _file_handler.setFormatter(logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            ))
            _file_handler.setLevel(logging.DEBUG)
            logging.getLogger().addHandler(_file_handler)
            app.state._log_file_handler = _file_handler  # for cleanup on shutdown
            logger.info("Server log file: %s", _log_file)

            data_svc = RealSessionDataService(fixtures_dir, session_store)

            # ── Discovery registry (v6 unified frontend protocol) ─────────
            # Register this live server in ~/.openteam/_runtime/registry/ so
            # other frontends (RovoDev TUI, future IDE extensions) can
            # discover it. Best-effort: registration failures are logged but
            # do NOT block server startup — discovery is a convenience for
            # clients, not a hard dependency.
            try:
                from openteam.server import _register as _registry
                from openteam.server import __version__ as _server_version  # may not exist
            except ImportError:
                _server_version = "unknown"  # type: ignore[assignment]
                from openteam.server import _register as _registry

            host = getattr(app.state, "bind_host", "127.0.0.1")
            port = getattr(app.state, "bind_port", 8000)
            try:
                _handle = _registry.register_server(
                    runtime_root=session_store.runtime_root,
                    host=host,
                    port=port,
                    server_dir_name=session_store.server_name,
                    version=_server_version,
                )
                app.state.discovery_handle = _handle
                logger.info(
                    "Registered in discovery registry: %s (sid=%s)",
                    _handle.registry_file, _handle.server_id,
                )
            except _registry.ConflictError as _e:
                # Another live server owns the same (runtime_root, host, port).
                # Surface clearly but don't crash — operator may have started
                # this server intentionally for a different purpose.
                logger.warning("[discovery] %s", _e)
                app.state.discovery_handle = None
            except Exception as _e:  # noqa: BLE001
                logger.warning("[discovery] failed to register: %s", _e)
                app.state.discovery_handle = None

            # Initialize conversation service
            # LLM backend: "mock" (default), "rovodev" (real AI via acli)
            # Set via env var OPENTEAM_LLM_BACKEND or app.state.llm_backend
            import os

            llm_backend = (
                os.environ.get("OPENTEAM_LLM_BACKEND")
                or getattr(app.state, "llm_backend", None)
                or "mock"
            )
            llm_model = (
                os.environ.get("OPENTEAM_LLM_MODEL")
                or getattr(app.state, "llm_model", None)
            )
            templates_dir = Path(__file__).parent / "resources" / "prompt_templates"
            working_dir = os.environ.get(
                "OPENTEAM_WORKING_DIR", str(Path.home() / "MyProjects")
            )
            # Streaming cache: saved under server_dir/cache/streaming_cache/
            # Uses cache/streaming_cache/ subdirectory to leave room for
            # future cache types (e.g., cache/embedding_cache/, cache/tool_cache/)
            # Matches the convention in create_role/executor.py
            cache_dir = os.environ.get(
                "OPENTEAM_CACHE_DIR",
                str(session_store.server_dir / "cache" / "streaming_cache"),
            )
            conversation_svc = ConversationService(
                templates_dir,
                llm_backend=llm_backend,
                llm_model=llm_model,
                working_dir=working_dir,
                cache_dir=cache_dir,
                session_store=session_store,
            )
            app.state.conversation_service = conversation_svc

            logger.info("Real sessions enabled: %s", real_sessions_dir)
            logger.info(
                "Conversation service: backend=%s, model=%s, working_dir=%s",
                llm_backend,
                llm_model or "(default)",
                working_dir,
            )
        else:
            data_svc = MockDataService(fixtures_dir)
            app.state.conversation_service = None
        intel_svc = MockIntelligenceService(fixtures_dir)
    else:
        raise ValueError(f"Unsupported mode: {mode}. Only 'mock' is implemented.")

    app.state.data_service = data_svc
    app.state.intelligence_service = intel_svc

    logger.info("OpenTeam API started in %s mode", mode)
    yield
    logger.info("OpenTeam API shutting down")
    # Remove file handler to avoid handler accumulation on restart
    _handler = getattr(app.state, "_log_file_handler", None)
    if _handler:
        logging.getLogger().removeHandler(_handler)
        _handler.close()


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
app.include_router(task_topology_router, prefix="/api/task", tags=["task"])
app.include_router(employee_org_router, prefix="/api/employees", tags=["employee-org"])
app.include_router(employee_router, prefix="/api/employees", tags=["employees"])
app.include_router(conversation_router, prefix="/api/conversations", tags=["conversations"])
app.include_router(dashboard_router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(intelligence_router, prefix="/api/intelligence", tags=["intelligence"])
app.include_router(session_router, prefix="/api/sessions", tags=["sessions"])
app.include_router(role_skill_router, prefix="/api/role-skills", tags=["role-skills"])
app.include_router(manager_ws_router, prefix="/ws", tags=["websocket"])
app.include_router(org_router, prefix="/api/orgs", tags=["organizations"])
app.include_router(meta_router, prefix="/api", tags=["meta"])

from openteam.server.routes.view_routes import router as view_router
app.include_router(view_router, prefix="/api", tags=["file-viewer"])


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
