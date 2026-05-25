# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict

"""Factory functions for creating LLM clients, inferencers, and parsing task options.

Extracted from chat_cli/app.py to decouple business logic from CLI presentation.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

from rankevolve.src.server.config import AppConfig
from rankevolve.src.server.task_types import TaskMode
from rankevolve.src.server.llm.base import BaseLLMClient


def create_llm_client(config: AppConfig) -> BaseLLMClient:
    """Factory to create the appropriate LLM client based on config."""
    if config.provider == "plugboard":
        from rankevolve.src.server.llm.plugboard_client import PlugboardClient

        return PlugboardClient(
            pipeline=config.pipeline,
            model_pipeline_overrides=config.model_pipeline_overrides,
        )
    elif config.provider == "openai":
        from rankevolve.src.server.llm.openai_client import OpenAIClient

        return OpenAIClient(api_key=config.api_key, base_url=config.base_url)
    else:
        from rankevolve.src.server.llm.anthropic_client import AnthropicClient

        return AnthropicClient(api_key=config.api_key, base_url=config.base_url)


def create_sync_inferencer(
    client: BaseLLMClient,
    config: AppConfig,
) -> Any:
    """Create a synchronous inferencer wrapper for the async LLM client.

    This wrapper allows the DocumentIngester (which expects a sync callable)
    to use the async streaming LLM client.

    Args:
        client: The async LLM client (PlugboardClient, AnthropicClient, etc.).
        config: App configuration with model settings.

    Returns:
        A callable that takes a prompt string and returns the LLM response.
    """

    def sync_infer(prompt: str) -> str:
        """Synchronous LLM inference wrapper."""

        async def _async_infer() -> str:
            chunks = []
            async for chunk in client.stream_response(
                messages=[{"role": "user", "content": prompt}],
                system="",
                model=config.model,
                max_tokens=config.max_tokens,
                temperature=0.3,  # Lower temperature for structured output
            ):
                chunks.append(chunk)
            return "".join(chunks)

        # Run async function in event loop
        try:
            loop = asyncio.get_running_loop()
            # If we're already in an async context, use run_coroutine_threadsafe
            future = asyncio.run_coroutine_threadsafe(_async_infer(), loop)
            return future.result(timeout=120)  # 2 minute timeout
        except RuntimeError:
            # No running loop, create a new one
            return asyncio.run(_async_infer())

    return sync_infer


def parse_task_options(
    args: str,
) -> tuple[str, str | None, bool, TaskMode | None, dict[str, Any]]:
    """Parse inline /task options.

    Supports:
        /task --plan <request>           -> task_mode=plan
        /task --full <request>           -> task_mode=full
        /task --confirm <request>        -> task_mode=confirm
        /task --execute <request>        -> task_mode=execute
        /task --claude-only <request>    -> use_claude_only=True
        /task --model opus <request>     -> claude_model=opus
        /task --no-planning <request>    -> enable_planning=False
        /task --no-implementation <req>  -> enable_implementation=False
        /task --analysis <request>       -> enable_analysis=True
        /task --multi-iter <request>     -> enable_multiple_iterations=True
        /task --base-inferencer <type>   -> base_inferencer_type=<type>
        /task --review-inferencer <type> -> review_inferencer_type=<type>
        /task --resume <path> <request>  -> resume_workspace=<path>
        /task --analysis-only <path>     -> resume + analysis only (skip plan/impl)
        /task --analysis-mode <mode>     -> analysis_mode (last|cross-ref|all-rounds)
        /task <request>                  -> defaults

    Returns:
        (request, claude_model, use_claude_only, task_mode, pti_flags)
    """
    from rankevolve.src.server.dual_inferencer_bridge import INFERENCER_CHOICES

    claude_model: str | None = None
    use_claude_only = False
    task_mode: TaskMode | None = None
    pti_flags: dict[str, Any] = {}

    # Extract --model <value> first (has argument)
    model_match = re.match(r"--model\s+(\S+)\s*(.*)", args, re.DOTALL)
    if model_match:
        claude_model = model_match.group(1)
        args = model_match.group(2).strip()

    # Extract flags (no argument)
    while args.startswith("--"):
        if args.startswith("--plan"):
            task_mode = TaskMode.PLAN_ONLY
            args = args[6:].strip()
        elif args.startswith("--full"):
            task_mode = TaskMode.FULL_WORKFLOW
            args = args[6:].strip()
        elif args.startswith("--confirm"):
            task_mode = TaskMode.PLAN_THEN_CONFIRM
            args = args[9:].strip()
        elif args.startswith("--execute"):
            task_mode = TaskMode.EXECUTE_ONLY
            args = args[9:].strip()
        elif args.startswith("--claude-only"):
            use_claude_only = True
            args = args[13:].strip()
        elif args.startswith("--no-planning"):
            pti_flags["enable_planning"] = False
            args = args[13:].strip()
        elif args.startswith("--no-implementation"):
            pti_flags["enable_implementation"] = False
            args = args[19:].strip()
        elif args.startswith("--analysis-mode"):
            am_match = re.match(r"--analysis-mode\s+(\S+)\s*(.*)", args, re.DOTALL)
            if am_match:
                from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.flow_inferencers.plan_then_implement_inferencer import (
                    ANALYSIS_MODE_CLI_MAP,
                )

                raw_mode = am_match.group(1)
                mapped = ANALYSIS_MODE_CLI_MAP.get(raw_mode)
                if mapped is not None:
                    pti_flags["analysis_mode"] = mapped
                else:
                    pti_flags["_analysis_mode_error"] = (
                        f"Invalid --analysis-mode '{raw_mode}'. "
                        f"Valid: {', '.join(ANALYSIS_MODE_CLI_MAP.keys())}"
                    )
                args = am_match.group(2).strip()
            else:
                break
        elif args.startswith("--copy-workspace"):
            pti_flags["copy_workspace"] = True
            args = args[16:].strip()
        elif args.startswith("--in-place"):
            pti_flags["copy_workspace"] = False
            args = args[10:].strip()
        elif args.startswith("--replay-streaming"):
            pti_flags["replay_streaming"] = True
            args = args[18:].strip()
        elif args.startswith("--initial-plan"):
            remaining = args[14:].strip()
            if " " in remaining:
                path, remaining = remaining.split(None, 1)
            else:
                path, remaining = remaining, ""
            pti_flags["initial_plan_file"] = path
            args = remaining.strip()
        elif args.startswith("--analysis-only"):
            remaining = args[15:].strip()
            ao_match = re.match(r"(\S+)\s*(.*)", remaining, re.DOTALL)
            if ao_match:
                pti_flags["resume_workspace"] = ao_match.group(1)
                pti_flags["enable_analysis"] = True
                pti_flags["enable_planning"] = False
                pti_flags["enable_implementation"] = False
                args = ao_match.group(2).strip()
                if not args:
                    args = "Run analysis on existing workspace"
            else:
                break
        elif args.startswith("--analysis"):
            pti_flags["enable_analysis"] = True
            args = args[10:].strip()
        elif args.startswith("--mock"):
            pti_flags["mock"] = True
            args = args[6:].strip()
        elif args.startswith("--no-queue"):
            pti_flags["no_queue"] = True
            args = args[10:].strip()
        elif args.startswith("--multi-iter"):
            pti_flags["enable_multiple_iterations"] = True
            args = args[12:].strip()
        elif args.startswith("--base-inferencer"):
            bi_match = re.match(r"--base-inferencer\s+(\S+)\s*(.*)", args, re.DOTALL)
            if bi_match:
                val = bi_match.group(1)
                if val in INFERENCER_CHOICES:
                    pti_flags["base_inferencer_type"] = val
                else:
                    pti_flags["_base_inferencer_error"] = (
                        f"Invalid --base-inferencer '{val}'. "
                        f"Valid: {', '.join(INFERENCER_CHOICES)}"
                    )
                args = bi_match.group(2).strip()
            else:
                break
        elif args.startswith("--review-inferencer"):
            ri_match = re.match(r"--review-inferencer\s+(\S+)\s*(.*)", args, re.DOTALL)
            if ri_match:
                val = ri_match.group(1)
                if val in INFERENCER_CHOICES:
                    pti_flags["review_inferencer_type"] = val
                else:
                    pti_flags["_review_inferencer_error"] = (
                        f"Invalid --review-inferencer '{val}'. "
                        f"Valid: {', '.join(INFERENCER_CHOICES)}"
                    )
                args = ri_match.group(2).strip()
            else:
                break
        elif args.startswith("--template-version"):
            tv_match = re.match(r"--template-version\s+(\S+)\s*(.*)", args, re.DOTALL)
            if tv_match:
                pti_flags["template_version"] = tv_match.group(1)
                args = tv_match.group(2).strip()
            else:
                break
        elif args.startswith("--resume"):
            resume_match = re.match(r"--resume\s+(\S+)\s*(.*)", args, re.DOTALL)
            if resume_match:
                pti_flags["resume_workspace"] = resume_match.group(1)
                args = resume_match.group(2).strip()
            else:
                break
        elif args.startswith("--model"):
            model_match = re.match(r"--model\s+(\S+)\s*(.*)", args, re.DOTALL)
            if model_match:
                claude_model = model_match.group(1)
                args = model_match.group(2).strip()
            else:
                break
        else:
            break

    # Auto-fill request when flags consumed all tokens.
    if not args:
        if pti_flags.get("mock"):
            args = "Mock task for UI testing"
        elif "resume_workspace" in pti_flags:
            args = "Run analysis on existing workspace"
        elif "initial_plan_file" in pti_flags:
            if pti_flags.get("enable_implementation") is False:
                args = "Review the provided plan"
            else:
                args = "Implement the provided plan"

    return (args, claude_model, use_claude_only, task_mode, pti_flags)
