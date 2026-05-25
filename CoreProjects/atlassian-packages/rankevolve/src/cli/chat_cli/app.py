# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from rankevolve.src.cli.chat_cli.ui.chat_display import ChatDisplay
from rankevolve.src.cli.chat_cli.ui.dual_agent_display import DualAgentDisplay
from rankevolve.src.cli.chat_cli.ui.input_handler import InputHandler
from rankevolve.src.cli.chat_cli.ui.theme import ThemeManager
from rankevolve.src.server.command_router import CommandResult, route_command
from rankevolve.src.server.config import AppConfig, load_config
from rankevolve.src.server.conversation import Conversation
from rankevolve.src.server.dual_inferencer_bridge import DualInferencerBridge
from rankevolve.src.server.factories import (
    create_llm_client,
    create_sync_inferencer,
    parse_task_options,
)
from rankevolve.src.server.research_propose_bridge import (
    parse_research_propose_options,
    ResearchProposeBridge,
)
from rankevolve.src.server.schema import MessageMetadata
from rankevolve.src.server.shared_loader import (
    load_system_prompt,
    load_theme,
    load_welcome_message,
)
from rankevolve.src.server.task_types import TaskMode
from rich.console import Console

logger: logging.Logger = logging.getLogger(__name__)


def display_command_result(result: CommandResult, console: Console) -> None:
    """Render a CommandResult to the Rich console."""
    if result.message:
        if result.action in ("error", "unknown"):
            console.print(f"[dim]{result.message}[/dim]")
        else:
            console.print(f"[dim]{result.message}[/dim]")


async def chat_loop(
    model_override: str | None = None,
    provider_override: str | None = None,
    root_folder: Path | None = None,
    claude_model: str | None = None,
    use_claude_only: bool = False,
    base_inferencer_type: str | None = None,
    review_inferencer_type: str | None = None,
    execution_mode: str = "full",
    output_dir: Path | None = None,
    max_iterations: int = 5,
    max_attempts: int = 1,
    consensus_threshold: str = "COSMETIC",
    timeout: int = 1800,
    no_counter_feedback: bool = False,
    enable_knowledge: bool = False,
    enable_planning: bool = True,
    enable_implementation: bool = True,
    enable_analysis: bool = False,
    enable_multiple_iterations: bool = False,
    max_meta_iterations: int = 3,
    resume_workspace: str | None = None,
    analysis_mode: str = "last_with_cross_ref",
    copy_workspace: bool | None = None,
    replay_streaming: bool = False,
    initial_plan_file: str | None = None,
) -> None:
    """Main interactive chat loop.

    Args:
        model_override: Override the LLM model for chat.
        provider_override: Override the LLM provider.
        root_folder: Root code folder for dual agent tasks.
        claude_model: Claude model for dual agent tasks (e.g., "opus", "sonnet").
        use_claude_only: Use Claude Code for both planner and reviewer.
        base_inferencer_type: Explicit inferencer type for the base (proposer) agent.
        review_inferencer_type: Explicit inferencer type for the review agent.
        execution_mode: Default execution mode for /task ("plan", "full", etc.).
        output_dir: Custom output directory for dual agent artifacts.
        max_iterations: Max consensus iterations per DualInferencer.
        max_attempts: Max fresh-start consensus attempts.
        consensus_threshold: Max acceptable severity for consensus.
        timeout: Per-inferencer idle timeout in seconds.
        no_counter_feedback: Disable counter-feedback from the proposer agent.
        enable_knowledge: Enable knowledge bridge (experimental, default False).
        enable_planning: Enable the planning phase (default True).
        enable_implementation: Enable the implementation phase (default True).
        enable_analysis: Enable the analysis phase after implementation.
        enable_multiple_iterations: Enable multi-iteration refinement loop.
        max_meta_iterations: Maximum number of meta-iterations.
        resume_workspace: Path to an existing workspace to resume from.
        analysis_mode: Analysis mode (last_round_only, last_with_cross_ref, all_rounds).
        copy_workspace: None=auto (copy on resume), True=force copy, False=in-place.
        replay_streaming: Replay streaming output from completed phases on resume.
    """
    config = load_config(
        model_override=model_override,
        provider_override=provider_override,
    )
    console = Console()
    theme_data = load_theme(config.theme)
    theme = ThemeManager(theme_data)
    display = ChatDisplay(console, theme, config.ui)
    dual_display = DualAgentDisplay(console, theme, config.ui)
    input_handler = InputHandler(theme)

    system_prompt = load_system_prompt(config.system_prompt_file)
    welcome = load_welcome_message()

    client = create_llm_client(config)
    conversation = Conversation(system_prompt)

    # Convert execution_mode string to TaskMode enum
    default_task_mode = TaskMode(execution_mode)

    # Initialize knowledge bridge with file-backed persistence and LLM inferencer
    # Disabled by default — pass --enable-knowledge to activate
    knowledge_bridge = None
    if enable_knowledge:
        try:
            from rankevolve.src.server.knowledge_bridge import KnowledgeBridge

            # Create sync inferencer for knowledge ingestion
            inferencer = create_sync_inferencer(client, config)
            knowledge_bridge = KnowledgeBridge(inferencer=inferencer)
            if knowledge_bridge.has_llm:
                logger.info("Knowledge bridge initialized with LLM ingestion")
            else:
                logger.info("Knowledge bridge initialized (basic mode)")
        except Exception as e:
            logger.warning("Knowledge bridge unavailable: %s", e)
    else:
        logger.info("Knowledge bridge disabled (use --enable-knowledge to activate)")

    # Mutable root folder — can be changed at runtime via /set-session-root
    current_root_folder = root_folder

    display.render_welcome(welcome)
    console.print(f"[dim]Provider: {config.provider} | Model: {config.model}[/dim]")
    # Display dual agent configuration if non-default
    da_config_parts = []
    if use_claude_only:
        da_config_parts.append("claude-only")
    if base_inferencer_type:
        da_config_parts.append(f"base={base_inferencer_type}")
    if review_inferencer_type:
        da_config_parts.append(f"review={review_inferencer_type}")
    if claude_model:
        da_config_parts.append(f"model={claude_model}")
    if execution_mode != "full":
        da_config_parts.append(f"mode={execution_mode}")
    if output_dir:
        da_config_parts.append(f"output={output_dir}")
    if da_config_parts:
        console.print(f"[dim]Dual Agent: {', '.join(da_config_parts)}[/dim]")
    console.print()

    try:
        while True:
            user_input = await input_handler.get_input()

            if user_input is None:
                console.print("\n[dim]Goodbye![/dim]")
                break

            if not user_input:
                continue

            if user_input.startswith("/"):
                result = route_command(user_input, conversation, config)
                if result.action == "exit":
                    console.print("[dim]Goodbye![/dim]")
                    break
                display_command_result(result, console)
                if result.action == "root_show":
                    effective = current_root_folder or Path.cwd()
                    console.print(f"[dim]Codebase root: {effective}[/dim]")
                if result.action == "root_set":
                    raw_path = result.data.get("path", "")
                    if not raw_path.startswith("/") and not raw_path.startswith("~"):
                        raw_path = "/" + raw_path
                    new_root = Path(raw_path).expanduser().resolve()
                    if new_root.is_dir():
                        current_root_folder = new_root
                        console.print(
                            f"[dim]Codebase root set to: {current_root_folder}[/dim]"
                        )
                    else:
                        console.print(f"[red]Not a valid directory: {new_root}[/red]")
                if result.action == "task":
                    task_args = result.data.get("args", "")
                    # Parse inline options (--plan, --claude-only, --model, etc.)
                    (
                        request,
                        inline_model,
                        inline_claude_only,
                        inline_task_mode,
                        inline_pti_flags,
                    ) = parse_task_options(task_args)

                    # Merge inline options with CLI defaults (inline takes precedence)
                    effective_model = inline_model or claude_model
                    effective_claude_only = inline_claude_only or use_claude_only
                    effective_task_mode = inline_task_mode or default_task_mode
                    effective_root = current_root_folder or Path.cwd()
                    effective_base_inferencer = inline_pti_flags.get(
                        "base_inferencer_type", base_inferencer_type
                    )
                    effective_review_inferencer = inline_pti_flags.get(
                        "review_inferencer_type", review_inferencer_type
                    )

                    # Display task configuration
                    console.print(f"[dim]Starting task: {request[:80]}...[/dim]")
                    console.print(f"[dim]Root folder: {effective_root}[/dim]")
                    config_parts = [f"mode={effective_task_mode.value}"]
                    if effective_claude_only:
                        config_parts.append("claude-only")
                    if effective_base_inferencer:
                        config_parts.append(f"base={effective_base_inferencer}")
                    if effective_review_inferencer:
                        config_parts.append(f"review={effective_review_inferencer}")
                    if effective_model:
                        config_parts.append(f"model={effective_model}")
                    console.print(f"[dim]Config: {', '.join(config_parts)}[/dim]")

                    # Merge PTI flags: inline overrides > CLI defaults
                    effective_enable_analysis = inline_pti_flags.get(
                        "enable_analysis", enable_analysis
                    )
                    effective_enable_multiple_iterations = inline_pti_flags.get(
                        "enable_multiple_iterations", enable_multiple_iterations
                    )
                    effective_resume_workspace = inline_pti_flags.get(
                        "resume_workspace", resume_workspace
                    )
                    effective_enable_planning = inline_pti_flags.get(
                        "enable_planning", enable_planning
                    )
                    effective_enable_implementation = inline_pti_flags.get(
                        "enable_implementation", enable_implementation
                    )
                    effective_analysis_mode = inline_pti_flags.get(
                        "analysis_mode", analysis_mode
                    )
                    effective_copy_workspace = inline_pti_flags.get(
                        "copy_workspace", copy_workspace
                    )
                    effective_replay_streaming = inline_pti_flags.get(
                        "replay_streaming", replay_streaming
                    )
                    effective_initial_plan_file = inline_pti_flags.get(
                        "initial_plan_file", initial_plan_file
                    )

                    # Report invalid --analysis-mode early
                    if "_analysis_mode_error" in inline_pti_flags:
                        console.print(
                            f"[red]{inline_pti_flags['_analysis_mode_error']}[/red]"
                        )
                        continue
                    if "_base_inferencer_error" in inline_pti_flags:
                        console.print(
                            f"[red]{inline_pti_flags['_base_inferencer_error']}[/red]"
                        )
                        continue
                    if "_review_inferencer_error" in inline_pti_flags:
                        console.print(
                            f"[red]{inline_pti_flags['_review_inferencer_error']}[/red]"
                        )
                        continue

                    # Create bridge with all options
                    bridge = DualInferencerBridge(
                        root_folder=effective_root,
                        claude_model=effective_model,
                        use_claude_only=effective_claude_only,
                        base_inferencer_type=effective_base_inferencer,
                        review_inferencer_type=effective_review_inferencer,
                        output_dir=output_dir,
                        knowledge_bridge=knowledge_bridge,
                        max_iterations=max_iterations,
                        max_attempts=max_attempts,
                        consensus_threshold=consensus_threshold,
                        timeout=timeout,
                        no_counter_feedback=no_counter_feedback,
                        enable_planning=effective_enable_planning,
                        enable_implementation=effective_enable_implementation,
                        enable_analysis=effective_enable_analysis,
                        enable_multiple_iterations=effective_enable_multiple_iterations,
                        max_meta_iterations=max_meta_iterations,
                        resume_workspace=effective_resume_workspace,
                        analysis_mode=effective_analysis_mode,
                        copy_workspace=effective_copy_workspace,
                        replay_streaming=effective_replay_streaming,
                        initial_plan_file=effective_initial_plan_file,
                        template_version=inline_pti_flags.get("template_version", ""),
                    )
                    # Show workspace location
                    console.print(f"[dim]Artifacts: {bridge.workspace}[/dim]")
                    task = asyncio.create_task(
                        bridge.run(request, task_mode=effective_task_mode)
                    )
                    try:
                        response_text = await dual_display.stream_dual_agent_response(
                            bridge.token_stream
                        )
                        await task
                        state_msg = ""
                        if effective_task_mode == TaskMode.PLAN_ONLY:
                            state_msg = " [plan_consensus]"
                        elif effective_task_mode == TaskMode.PLAN_THEN_CONFIRM:
                            state_msg = " [awaiting_approval]"
                        console.print(f"[dim]Session complete{state_msg}.[/dim]")
                        if (
                            knowledge_bridge is not None
                            and effective_task_mode != TaskMode.PLAN_THEN_CONFIRM
                        ):
                            console.print(
                                "[dim]Task results saved to knowledge base.[/dim]"
                            )
                        conversation.add_assistant_message(
                            response_text,
                            metadata=MessageMetadata(model="dual_inferencer"),
                        )
                    except Exception as e:
                        try:
                            await task
                        except Exception:
                            pass
                        console.print(f"[red]DualInferencer error: {e}[/red]")
                        console.print(f"[dim]Check workspace: {bridge.workspace}[/dim]")
                if result.action == "research-propose":
                    rp_raw_args = result.data.get("args", "")
                    request, rp_options = parse_research_propose_options(rp_raw_args)
                    # Merge shortcut flags from command router
                    if result.data.get("research_only"):
                        rp_options["research_only"] = True
                    if result.data.get("disable_unified_proposal"):
                        rp_options["disable_unified_proposal"] = True

                    if not request:
                        console.print(
                            "[dim]Usage: /research-propose <task or hypothesis>[/dim]"
                        )
                        continue

                    effective_root = current_root_folder or Path.cwd()
                    console.print(f"[dim]Starting research-propose workflow...[/dim]")
                    console.print(f"[dim]Root: {effective_root}[/dim]")

                    bridge = ResearchProposeBridge(
                        root_folder=effective_root,
                        model=rp_options.get("model") or claude_model,
                        research_only=rp_options.get("research_only", False),
                        disable_unified_proposal=rp_options.get(
                            "disable_unified_proposal", False
                        ),
                        max_queries=rp_options.get("max_queries", 5),
                        output_dir=output_dir,
                        knowledge_bridge=knowledge_bridge,
                        resume_workspace=rp_options.get("resume"),
                        base_inferencer_type=(
                            rp_options.get("base_inferencer") or base_inferencer_type
                        ),
                        review_inferencer_type=(
                            rp_options.get("review_inferencer")
                            or review_inferencer_type
                        ),
                    )

                    console.print(f"[dim]Workspace: {bridge.workspace}[/dim]")

                    task = asyncio.create_task(bridge.run(request))
                    try:
                        response_text = await dual_display.stream_dual_agent_response(
                            bridge.token_stream
                        )
                        await task
                        console.print("[dim]Research-propose workflow complete.[/dim]")
                        conversation.add_assistant_message(
                            response_text,
                            metadata=MessageMetadata(model="research_propose"),
                        )
                    except Exception as e:
                        try:
                            await task
                        except Exception:
                            pass
                        console.print(f"[red]Research-propose error: {e}[/red]")
                        console.print(f"[dim]Check workspace: {bridge.workspace}[/dim]")

                if result.action == "kn":
                    from rankevolve.src.cli.chat_cli.kn_command_handler import (
                        handle_kn_command,
                    )

                    handle_kn_command(
                        result.data.get("args", ""),
                        knowledge_bridge,
                        console,
                        conversation,
                    )
                continue

            # Display user message
            user_msg = conversation.add_user_message(user_input)
            console.print(display.render_message_panel(user_msg))

            # Stream assistant response
            try:
                # Auto-retrieve relevant knowledge context
                effective_system = system_prompt
                if knowledge_bridge is not None:
                    try:
                        knowledge_context = knowledge_bridge.query(user_input)
                        if knowledge_context.strip():
                            effective_system = (
                                system_prompt
                                + "\n\n## Retrieved Knowledge\n"
                                + knowledge_context
                            )
                    except Exception:
                        pass

                start_time = time.time()
                token_stream = client.stream_response(
                    messages=conversation.get_api_messages(),
                    system=effective_system,
                    model=config.model,
                    max_tokens=config.max_tokens,
                    temperature=config.temperature,
                )
                response_text = await display.stream_assistant_response(token_stream)
                elapsed_ms = int((time.time() - start_time) * 1000)

                conversation.add_assistant_message(
                    response_text,
                    metadata=MessageMetadata(
                        model=config.model,
                        duration_ms=elapsed_ms,
                    ),
                )

                if config.ui.show_timing:
                    console.print(f"[dim]{elapsed_ms}ms[/dim]")

            except KeyboardInterrupt:
                console.print("\n[dim]Response interrupted.[/dim]")
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")

    finally:
        if knowledge_bridge is not None:
            knowledge_bridge.close()
        await client.close()
