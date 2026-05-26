#!/usr/bin/env python3
"""CLI entry point for the OpenTeam API server.

Usage:
    python run_server.py                # Default: mock mode, port 8000
    python run_server.py --port 9000    # Custom port
    python run_server.py --reload       # Development with auto-reload
"""

import argparse
import logging
import sys
from pathlib import Path

# ── Python path setup ─────────────────────────────────────────────────────────
# Sibling repos AgentFoundation and PythonUtils have no pyproject.toml;
# we inject them via openteam.bootstrap so this CLI works whether started via
# `bash run.sh` (which sets PYTHONPATH) or directly via `python run_server.py`.
sys.path.insert(0, str(Path(__file__).parent.parent.parent))  # OpenTeam/src
from openteam.bootstrap import ensure_siblings_on_path  # noqa: E402
ensure_siblings_on_path()


def main() -> None:
    # Pre-import the backend registry so --llm-backend choices and
    # --list-backends can read it. Built-in backends register on import.
    from openteam.server.backends import get_registry
    from openteam.server.services.conversation_service import ConversationService

    parser = argparse.ArgumentParser(description="OpenTeam API Server")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--mode", choices=["mock", "live"], default="mock", help="Server mode")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--real-sessions",
        type=str,
        default=None,
        metavar="DIR",
        help="Enable persistent sessions from DIR (runtime root, default: mock fixture data)",
    )
    parser.add_argument(
        "--runtime-root",
        type=str,
        default=None,
        metavar="SPEC",
        help=(
            "Runtime root resolution (v6/I21). One of: 'auto' (4-tier default), "
            "'repo-root' (force walk-up; fail loud if not found), "
            "'user-home' (~/.openteam/_runtime), or an explicit path. "
            "Sets OPENTEAM_RUNTIME_DIR; takes precedence over --real-sessions. "
            "Pip-installed users typically want 'user-home'."
        ),
    )
    parser.add_argument(
        "--resume-server",
        type=str,
        default=None,
        metavar="NAME",
        help='Resume a specific server dir by name (e.g., server_20260406_...). Default: always create a new server.',
    )
    parser.add_argument(
        "--resume-latest-server",
        action="store_true",
        default=False,
        help='Resume the most recently created server directory instead of creating a new one.',
    )
    parser.add_argument(
        "--llm-backend",
        type=str,
        default=None,
        metavar="NAME",
        choices=ConversationService.AVAILABLE_BACKENDS(),
        help=(
            "Default conversation backend (override via OPENTEAM_LLM_BACKEND or "
            "the per-session UI selector). Choices: "
            + ", ".join(ConversationService.AVAILABLE_BACKENDS())
        ),
    )
    parser.add_argument(
        "--llm-model",
        type=str,
        default=None,
        metavar="NAME",
        help=(
            "Default model name to pass into the backend factory "
            "(e.g., 'opus[1m]' for claude_cli). Backend-specific. "
            "Override via OPENTEAM_LLM_MODEL or the per-session UI."
        ),
    )
    parser.add_argument(
        "--list-backends",
        action="store_true",
        default=False,
        help="Print all registered backends with availability status and exit.",
    )
    args = parser.parse_args()

    # v6/I21: --runtime-root SETS OPENTEAM_RUNTIME_DIR; any subsequent
    # find_runtime_root() call (including from inside the SessionStore
    # constructor's parent path resolution, or from any auxiliary tool that
    # gets invoked in-process) sees the same value. Single source of truth.
    #
    # Precedence: --runtime-root > --real-sessions DIR > env var > 4-tier.
    if args.runtime_root is not None:
        from openteam.server.runtime_root import apply_runtime_root
        resolved = apply_runtime_root(args.runtime_root)
        # Mirror onto --real-sessions for the lifespan code that still keys off
        # `app.state.real_sessions_dir`. Operators specifying --runtime-root
        # never need to also pass --real-sessions.
        if args.real_sessions is None:
            args.real_sessions = str(resolved)

    if args.list_backends:
        registry = get_registry()
        print("Registered inferencer backends:")
        print()
        for name, desc in sorted(registry.list_backends().items()):
            available = desc.is_available()
            status = "available  " if available else "unavailable"
            print(f"  [{status}] {desc.display_name} ({name})")
            if desc.description:
                print(f"             {desc.description}")
            print(f"             {desc.status_message()}")
            if desc.default_model:
                print(f"             default_model={desc.default_model}")
            print()
        sys.exit(0)

    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    import uvicorn
    from openteam.server.main import app

    app.state.mode = args.mode
    # v6: expose bind host/port to lifespan so _register can populate the
    # discovery file with the actual reachable endpoint.
    app.state.bind_host = args.host
    app.state.bind_port = args.port

    if args.real_sessions:
        app.state.real_sessions_dir = str(Path(args.real_sessions).expanduser())
    # --resume-latest-server → "latest"; --resume-server <name> → "<name>"; default → None (new)
    if args.resume_latest_server:
        app.state.resume_server = "latest"
    elif args.resume_server:
        app.state.resume_server = args.resume_server
    # else: app.state.resume_server is not set → session_store defaults to creating new

    if args.llm_backend:
        app.state.llm_backend = args.llm_backend
    if args.llm_model:
        app.state.llm_model = args.llm_model

    print(f"Starting OpenTeam API Server ({args.mode} mode)")
    print(f"  Host: {args.host}")
    print(f"  Port: {args.port}")
    print(f"  Debug: {args.debug}")
    print(f"  Reload: {args.reload}")
    if args.real_sessions:
        print(f"  Runtime Root: {app.state.real_sessions_dir}")
    if args.resume_server:
        print(f"  Resume Server: {args.resume_server}")
    print()

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="debug" if args.debug else "info",
    )


if __name__ == "__main__":
    main()
