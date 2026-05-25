# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from rankevolve.src.cli.chat_cli.app import chat_loop
from rankevolve.src.server.dual_inferencer_bridge import INFERENCER_CHOICES


def main() -> None:
    """Entry point for the chat CLI."""
    parser = argparse.ArgumentParser(
        description="Interactive chat CLI for LLMs",
    )
    parser.add_argument(
        "--model",
        "-m",
        type=str,
        default=None,
        help="Override the model name for chat (plugboard/anthropic/openai)",
    )
    parser.add_argument(
        "--provider",
        "-p",
        type=str,
        choices=["plugboard", "anthropic", "openai"],
        default=None,
        help="LLM provider (plugboard, anthropic, or openai)",
    )
    parser.add_argument(
        "--root-folder",
        "-r",
        type=str,
        default=None,
        help="Root code folder for dual agent tasks (default: cwd)",
    )
    # Dual agent options
    parser.add_argument(
        "--claude-model",
        type=str,
        default="claude-opus-4-6",
        help=(
            "Claude model for dual agent tasks (default: claude-opus-4-6). "
            "Supports: sonnet, opus, sonnet-4-5, opus-4-5, claude-sonnet-4-5, "
            "claude-opus-4-5, claude-opus-4-6, or any valid model name"
        ),
    )
    parser.add_argument(
        "--use-claude-only",
        action="store_true",
        default=False,
        help=(
            "Use Claude Code for both planner and reviewer agents in /task "
            "(default: False, both agents use DevmateCliInferencer)"
        ),
    )
    parser.add_argument(
        "--base-inferencer",
        type=str,
        choices=INFERENCER_CHOICES,
        default=None,
        help=(
            "Inferencer type for the base (proposer) agent. "
            "Overrides --use-claude-only when set. "
            f"Choices: {', '.join(INFERENCER_CHOICES)}"
        ),
    )
    parser.add_argument(
        "--review-inferencer",
        type=str,
        choices=INFERENCER_CHOICES,
        default=None,
        help=(
            "Inferencer type for the review agent. "
            "Overrides --use-claude-only when set. "
            f"Choices: {', '.join(INFERENCER_CHOICES)}"
        ),
    )
    parser.add_argument(
        "--execution-mode",
        "-e",
        type=str,
        choices=["plan", "execute", "full", "confirm"],
        default="full",
        help=(
            "Default execution mode for /task: plan only, execute only, "
            "full workflow (default), or plan then confirm"
        ),
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=str,
        default=None,
        help=(
            "Custom output directory for dual agent artifacts "
            "(default: fbsource/_rankevolve_workspace/)"
        ),
    )
    # Consensus / inferencer tuning
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=5,
        help="Max consensus iterations per DualInferencer (default: 5)",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=1,
        help="Max fresh-start consensus attempts (default: 1)",
    )
    parser.add_argument(
        "--consensus-threshold",
        type=str,
        choices=["NONE", "COSMETIC", "MINOR", "MAJOR", "CRITICAL"],
        default="COSMETIC",
        help="Max acceptable severity for consensus (default: COSMETIC)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=1800,
        help="Per-inferencer idle timeout in seconds (default: 1800)",
    )
    parser.add_argument(
        "--no-counter-feedback",
        action="store_true",
        default=False,
        help="Disable counter-feedback from the proposer agent",
    )
    parser.add_argument(
        "--enable-knowledge",
        action="store_true",
        default=False,
        help="Enable knowledge bridge for context retrieval (experimental, disabled by default)",
    )
    # PlanThenImplementInferencer flags
    parser.add_argument(
        "--enable-analysis",
        action="store_true",
        default=False,
        help="Enable the analysis phase after implementation",
    )
    parser.add_argument(
        "--enable-multiple-iterations",
        action="store_true",
        default=False,
        help="Enable multi-iteration refinement loop",
    )
    parser.add_argument(
        "--max-meta-iterations",
        type=int,
        default=3,
        help="Maximum number of meta-iterations (default: 3)",
    )
    parser.add_argument(
        "--resume-workspace",
        type=str,
        default=None,
        help="Path to an existing workspace to resume from",
    )
    parser.add_argument(
        "--analysis-only",
        type=str,
        default=None,
        metavar="WORKSPACE_PATH",
        help="Run analysis only on an existing completed workspace (shorthand for --resume <path> --enable-analysis)",
    )
    parser.add_argument(
        "--analysis-mode",
        type=str,
        choices=["last", "cross-ref", "all-rounds"],
        default="cross-ref",
        help=(
            "Analysis mode: last (latest round only), "
            "cross-ref (latest + compare earlier, default), "
            "all-rounds (per-round + summary)"
        ),
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        default=False,
        help="Modify the workspace in-place when resuming (default: copies to protect original)",
    )
    parser.add_argument(
        "--replay-streaming",
        action="store_true",
        default=False,
        help="Replay streaming output from completed phases on resume (default: skip to new work)",
    )

    parser.add_argument(
        "--initial-plan",
        type=str,
        default=None,
        help="Path to an initial plan file. Skips plan proposal, starts with plan review.",
    )

    # Research-propose defaults
    parser.add_argument(
        "--default-max-queries",
        type=int,
        default=5,
        help="Default max queries for /research-propose (default: 5)",
    )
    parser.add_argument(
        "--default-research-model",
        type=str,
        default=None,
        help="Default model for research phases",
    )

    # Server-client mode: connect to a running RankEvolve server
    parser.add_argument(
        "--server",
        action="store_true",
        default=False,
        help="Connect to a running RankEvolve server instead of running standalone",
    )
    parser.add_argument(
        "--queue-root",
        type=str,
        default="rankevolve/_runtime",
        help="Queue root path for server connection (default: rankevolve/_runtime)",
    )
    parser.add_argument(
        "--session-id",
        type=str,
        default=None,
        help="Session ID for server connection (default: auto-generated)",
    )

    args = parser.parse_args()

    # Handle --analysis-only shorthand: implies --resume <path> --enable-analysis
    # and explicitly disables planning/implementation
    effective_resume = args.resume_workspace
    effective_analysis = args.enable_analysis
    effective_planning = True
    effective_implementation = True
    if args.analysis_only:
        effective_resume = args.analysis_only
        effective_analysis = True
        effective_planning = False
        effective_implementation = False

    # Map CLI analysis-mode short names to internal mode names
    from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.flow_inferencers.plan_then_implement_inferencer import (
        ANALYSIS_MODE_CLI_MAP,
    )

    effective_analysis_mode = ANALYSIS_MODE_CLI_MAP.get(
        args.analysis_mode, "last_with_cross_ref"
    )

    # Server-client mode: connect to running server via queue
    if args.server:
        from rankevolve.src.cli.chat_cli.client import RankEvolveCLIClient

        client = RankEvolveCLIClient(
            queue_root_path=args.queue_root,
            session_id=args.session_id,
        )
        try:
            asyncio.run(client.run())
        except KeyboardInterrupt:
            print("\nGoodbye!")
            sys.exit(0)
        return

    try:
        asyncio.run(
            chat_loop(
                model_override=args.model,
                provider_override=args.provider,
                root_folder=Path(args.root_folder) if args.root_folder else None,
                claude_model=args.claude_model,
                use_claude_only=args.use_claude_only,
                base_inferencer_type=args.base_inferencer,
                review_inferencer_type=args.review_inferencer,
                execution_mode=args.execution_mode,
                output_dir=Path(args.output_dir) if args.output_dir else None,
                max_iterations=args.max_iterations,
                max_attempts=args.max_attempts,
                consensus_threshold=args.consensus_threshold,
                timeout=args.timeout,
                no_counter_feedback=args.no_counter_feedback,
                enable_knowledge=args.enable_knowledge,
                enable_planning=effective_planning,
                enable_implementation=effective_implementation,
                enable_analysis=effective_analysis,
                enable_multiple_iterations=args.enable_multiple_iterations,
                max_meta_iterations=args.max_meta_iterations,
                resume_workspace=effective_resume,
                analysis_mode=effective_analysis_mode,
                copy_workspace=False if args.in_place else None,
                replay_streaming=args.replay_streaming,
                initial_plan_file=args.initial_plan,
            )
        )
    except KeyboardInterrupt:
        print("\nGoodbye!")
        sys.exit(0)


if __name__ == "__main__":
    main()
