# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.

"""Entry point for the RankEvolve agent server."""

from __future__ import annotations

import argparse
from pathlib import Path

from .config import RankEvolveServiceConfig
from .service import RankEvolveAgentService


def main() -> None:
    parser = argparse.ArgumentParser(description="RankEvolve Agent Server")
    parser.add_argument("--model", default="claude-3.5-sonnet", help="LLM model name")
    parser.add_argument(
        "--provider",
        default="plugboard",
        choices=["plugboard", "anthropic", "openai"],
        help="LLM provider",
    )
    parser.add_argument(
        "--session-root",
        default=None,
        help="Session root path (defaults to current working directory)",
    )
    parser.add_argument("--pipeline", default="", help="Plugboard pipeline")
    parser.add_argument(
        "--enable-knowledge", action="store_true", help="Enable knowledge bridge"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--service-root",
        default="rankevolve/_runtime",
        help="Root directory for server data (default: rankevolve/_runtime)",
    )
    parser.add_argument(
        "--server-dir",
        default=None,
        help="Resume from existing server directory (e.g., _runtime/servers/server_20260317_042359_a1b2c3d4)",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=0.1,
        help="Main loop poll interval in seconds",
    )
    parser.add_argument(
        "--session-idle-timeout",
        type=int,
        default=3600,
        help="Session idle timeout in seconds",
    )

    args = parser.parse_args()

    session_root = args.session_root or str(Path.cwd())

    config = RankEvolveServiceConfig(
        provider=args.provider,
        model=args.model,
        session_root_path=session_root,
        pipeline=args.pipeline,
        enable_knowledge=args.enable_knowledge,
        debug_mode=args.debug,
        queue_root_path=args.service_root,
        log_root_path=args.service_root,
        poll_interval=args.poll_interval,
        session_idle_timeout=args.session_idle_timeout,
        server_dir=args.server_dir,
    )

    service = RankEvolveAgentService(config)
    service.run()


if __name__ == "__main__":
    main()
