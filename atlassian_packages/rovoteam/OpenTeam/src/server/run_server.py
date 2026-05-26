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

# Add parent directory to path so 'server' package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenTeam API Server")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--mode", choices=["mock", "live"], default="mock", help="Server mode")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    import uvicorn
    from server.main import app

    app.state.mode = args.mode

    print(f"Starting OpenTeam API Server ({args.mode} mode)")
    print(f"  Host: {args.host}")
    print(f"  Port: {args.port}")
    print(f"  Debug: {args.debug}")
    print(f"  Reload: {args.reload}")
    print()

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="debug" if args.debug else "info",
    )


if __name__ == "__main__":
    main()
