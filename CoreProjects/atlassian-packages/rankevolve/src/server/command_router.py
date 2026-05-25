# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict

"""Pure structured command routing — no Console, no I/O.

Replaces the Console-dependent handle_command() from chat_cli/app.py
with a structured CommandResult return type.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rankevolve.src.server.config import AppConfig
from rankevolve.src.server.conversation import Conversation


def parse_understand_codebase_options(
    args: str,
) -> tuple[str, dict[str, Any]]:
    """Parse /understand-codebase inline flags.

    Supported flags:
        --investigation-only        Run codebase investigation only (skip docs)
        --docs-only                 Skip investigation, generate docs from existing
        --model <name>              Override LLM model
        --resume <path>             Resume from a previous workspace
        --base-inferencer <type>    Override base inferencer type
        --review-inferencer <type>  Override review inferencer type

    Returns:
        (target_path_or_description, options_dict)
    """
    options: dict[str, Any] = {}
    tokens = args.split()
    request_parts: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "--investigation-only":
            options["investigation_only"] = True
        elif tok == "--docs-only":
            options["docs_only"] = True
        elif tok == "--model" and i + 1 < len(tokens):
            i += 1
            options["model"] = tokens[i]
        elif tok == "--resume" and i + 1 < len(tokens):
            i += 1
            options["resume"] = tokens[i]
        elif tok == "--base-inferencer" and i + 1 < len(tokens):
            i += 1
            options["base_inferencer"] = tokens[i]
        elif tok == "--review-inferencer" and i + 1 < len(tokens):
            i += 1
            options["review_inferencer"] = tokens[i]
        else:
            request_parts.append(tok)
        i += 1
    return " ".join(request_parts), options


@dataclass
class CommandResult:
    """Structured result from command routing."""

    action: str  # "exit", "clear", "model_set", "root_show", "root_set", "task", "kn", "help", "unknown"
    message: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    config_changed: bool = False
    updated_config: dict[str, Any] | None = None


def route_command(
    cmd: str,
    conversation: Conversation,
    config: AppConfig,
) -> CommandResult:
    """Route a slash command and return a structured result. No Console, no I/O."""
    cmd_lower = cmd.strip().lower()

    if cmd_lower in ("/exit", "/quit"):
        return CommandResult(action="exit")

    elif cmd_lower == "/clear":
        conversation.clear()
        return CommandResult(action="clear", message="Conversation cleared.")

    elif cmd_lower.startswith("/model "):
        new_model = cmd.strip().split(" ", 1)[1].strip()
        config.model = new_model
        return CommandResult(
            action="model_set",
            message=f"Model set to {new_model}",
            config_changed=True,
            updated_config={"model": new_model},
        )

    elif cmd_lower.startswith("/set-session-root"):
        args = cmd.strip()[17:].strip()
        if not args:
            return CommandResult(action="root_show")
        return CommandResult(action="root_set", data={"path": args})

    elif cmd_lower.startswith("/task"):
        task_prefix = cmd.strip().split()[0].lower()
        mode_shortcuts = {
            "/task-plan": "--plan",
            "/task-execute": "--execute",
            "/task-full": "--full",
            "/task-confirm": "--confirm",
        }
        if task_prefix in mode_shortcuts:
            args = cmd.strip()[len(task_prefix) :].strip()
            flag = mode_shortcuts[task_prefix]
            if not args:
                return CommandResult(
                    action="error",
                    message=f"Usage: {task_prefix} <request>",
                )
            return CommandResult(action="task", data={"args": f"{flag} {args}"})
        else:
            args = cmd.strip()[5:].strip()
            if not args:
                return CommandResult(
                    action="error",
                    message=(
                        "Usage: /task <request>, or /task-plan, "
                        "/task-execute, /task-full, /task-confirm"
                    ),
                )
            return CommandResult(action="task", data={"args": args})

    elif cmd_lower.startswith("/kn"):
        args = cmd.strip()[3:].strip()
        return CommandResult(action="kn", data={"args": args})

    elif cmd_lower.startswith("/understand-codebase"):
        parts = cmd.strip().split(None, 1)
        args = parts[1] if len(parts) > 1 else ""
        if not args:
            return CommandResult(
                action="error",
                message="Usage: /understand-codebase <path or description>",
            )
        target, uc_opts = parse_understand_codebase_options(args)
        if not target:
            return CommandResult(
                action="error",
                message="Usage: /understand-codebase <path or description>",
            )
        task_flags = ["--template-version", "understand_codebase"]
        if uc_opts.get("investigation_only"):
            task_flags.append("--no-implementation")
        if uc_opts.get("docs_only"):
            task_flags.append("--no-planning")
        for flag in ("model", "resume", "base_inferencer", "review_inferencer"):
            if uc_opts.get(flag):
                task_flags.extend([f"--{flag.replace('_', '-')}", uc_opts[flag]])
        task_args = " ".join(task_flags + [target])
        return CommandResult(action="task", data={"args": task_args})

    elif cmd_lower.startswith("/research-propose"):
        parts = cmd.strip().split(None, 1)
        args = parts[1] if len(parts) > 1 else ""
        if not args:
            return CommandResult(
                action="error",
                message="Usage: /research-propose <task or hypothesis>",
            )
        return CommandResult(action="research-propose", data={"args": args})

    elif cmd_lower == "/research" or cmd_lower.startswith("/research "):
        parts = cmd.strip().split(None, 1)
        args = parts[1] if len(parts) > 1 else ""
        return CommandResult(
            action="research-propose",
            data={"args": args, "research_only": True},
        )

    elif cmd_lower == "/propose" or cmd_lower.startswith("/propose "):
        parts = cmd.strip().split(None, 1)
        args = parts[1] if len(parts) > 1 else ""
        return CommandResult(
            action="research-propose",
            data={"args": args, "disable_unified_proposal": True},
        )

    elif cmd_lower.startswith("/implement-hypothesis"):
        # Round 11: split orchestrator — Stage 1 of /experiment.
        args = cmd.strip()[len("/implement-hypothesis"):].strip()
        ih_data = _parse_implement_hypothesis_args(args)
        if not ih_data.get("selected_ids"):
            return CommandResult(
                action="error",
                message=(
                    "Usage: /implement-hypothesis --select H1,H17,H8 "
                    "[--plan <path>] [--max-batch-size N] [--max-parallel N] "
                    "[--reuse-task <id>]"
                ),
            )
        return CommandResult(action="implement_hypothesis", data=ih_data)

    elif cmd_lower.startswith("/experiment-hypothesis-combos"):
        # Round 11: split orchestrator — Stage 2 of /experiment.
        args = cmd.strip()[len("/experiment-hypothesis-combos"):].strip()
        ec_data = _parse_experiment_combos_args(args)
        # --aggregate-only is the standalone "refresh narrative" path: skip
        # breakdown + workers, run only the LLM aggregator over per-combo
        # analyses already on disk. Combos arg is not required in that mode.
        if not ec_data.get("aggregate_only") and not ec_data.get("combos"):
            return CommandResult(
                action="error",
                message=(
                    "Usage: /experiment-hypothesis-combos --combos H1;H17,H8;H56 "
                    "[--max-concurrency N] [--rounds N] [--reuse-hub <mid>] "
                    "[--launcher local|fblearner]\n"
                    "Or: /experiment-hypothesis-combos --aggregate-only "
                    "[--aggregate-target <path>]"
                ),
            )
        return CommandResult(action="experiment_combos", data=ec_data)

    elif cmd_lower.startswith("/experiment"):
        args = cmd.strip()[11:].strip()
        exp_data = _parse_experiment_args(args)
        if not exp_data.get("plan_path") and not exp_data.get("implement_default"):
            return CommandResult(
                action="error",
                message=(
                    "Usage: /experiment --plan <path> [--select H1,H3,H17] [--implement-default]\n"
                    "  --plan <path>         Path to unified proposal plan\n"
                    "  --select H1,H3,...    Comma-separated hypothesis IDs to select\n"
                    "  --implement-default   Implement the default-selected hypotheses\n"
                    "\n"
                    "Round 11: /experiment is now a thin sequencer that runs "
                    "/implement-hypothesis followed by /experiment-hypothesis-combos. "
                    "Use the sub-commands directly for finer control."
                ),
            )
        return CommandResult(action="experiment", data=exp_data)

    elif cmd_lower == "/help":
        return CommandResult(
            action="help",
            message=_generate_help_text(),
        )

    elif cmd_lower.startswith("/view"):
        args = cmd.strip()[5:].strip()
        return CommandResult(
            action="view",
            data={"target": args or "docs"},
        )

    else:
        return CommandResult(
            action="unknown",
            message=f"Unknown command: {cmd}. Type /help for commands.",
        )


def _parse_implement_hypothesis_args(args: str) -> dict[str, Any]:
    """Parse /implement-hypothesis inline flags (Round 11 — Stage 1).

    Supported flags:
        --select H1,H17,...    Hypothesis IDs to implement (REQUIRED)
        --plan <path>          Path to unified proposal plan (mined for bodies)
        --max-batch-size N     Soft cap on per-batch size (default 5)
        --max-parallel N       Concurrent PTI worker cap (default 2)
        --reuse-task <id>      Resume into an existing implementation task workspace
        --workspace <path>     Override workspace location
        --base-inferencer <t>  LLM inferencer (default 'devmate_cli')
        --workflow-target-path Codebase root for ${CODEBASE_ROOT}
        --model <name>         LLM model override
        --hub-id <mid>         Bind this implementation to an Experiment Hub
                               (writes per-batch rows into the hub's
                               ``hub_<mid>_implementations.json`` so the
                               hub's Selection-tab "Done" badges + Apply
                               Combos preflight gate see the evidence).
                               Standalone callers (CLI, tests) omit this.
    """
    options: dict[str, Any] = {}
    tokens = args.split()
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "--select" and i + 1 < len(tokens):
            i += 1
            options["selected_ids"] = [
                h.strip() for h in tokens[i].split(",") if h.strip()
            ]
        elif tok == "--plan" and i + 1 < len(tokens):
            i += 1
            options["plan_path"] = tokens[i]
        elif tok == "--max-batch-size" and i + 1 < len(tokens):
            i += 1
            try:
                options["max_batch_size"] = int(tokens[i])
            except ValueError:
                pass
        elif tok == "--max-parallel" and i + 1 < len(tokens):
            i += 1
            try:
                options["max_parallel"] = int(tokens[i])
            except ValueError:
                pass
        elif tok == "--reuse-task" and i + 1 < len(tokens):
            i += 1
            options["reuse_task"] = tokens[i]
        elif tok == "--workspace" and i + 1 < len(tokens):
            i += 1
            options["workspace"] = tokens[i]
        elif tok == "--base-inferencer" and i + 1 < len(tokens):
            i += 1
            options["base_inferencer"] = tokens[i]
        elif tok == "--workflow-target-path" and i + 1 < len(tokens):
            i += 1
            options["workflow_target_path"] = tokens[i]
        elif tok == "--model" and i + 1 < len(tokens):
            i += 1
            options["model"] = tokens[i]
        elif tok == "--hub-id" and i + 1 < len(tokens):
            i += 1
            options["hub_id"] = tokens[i]
        i += 1
    return options


def _parse_experiment_combos_args(args: str) -> dict[str, Any]:
    """Parse /experiment-hypothesis-combos inline flags (Round 11 — Stage 2).

    Supported flags:
        --combos H1;H17,H8;H56  Semicolon-separated combos (REQUIRED unless --aggregate-only)
        --max-concurrency N     BTA worker semaphore (default 2)
        --rounds N              Multi-round outer LWI count (default 1)
        --reuse-hub <mid>       Resume into an existing hub
        --launcher local|fblearner  Training backend (default 'local')
        --workspace <path>      Override workspace location
        --workspace-keep-only-final  Reap intermediate artifacts post-completion
        --max-wait <seconds>    Per-monitor watchdog timeout
        --base-inferencer <t>   LLM inferencer for analyzers
        --workflow-target-path  Codebase root for ${CODEBASE_ROOT}
        --model <name>          LLM model override
        --aggregate-only        Skip breakdown + workers; re-run only the LLM
                                aggregator over per-combo analyses on disk.
                                Output goes to <session>/_learnings/
                                accumulated_learnings.md (or --aggregate-target).
        --aggregate-target P    Override output path for --aggregate-only.
    """
    options: dict[str, Any] = {}
    tokens = args.split()
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "--combos" and i + 1 < len(tokens):
            i += 1
            options["combos"] = tokens[i]  # raw; ExperimentBridge parses
        elif tok == "--max-concurrency" and i + 1 < len(tokens):
            i += 1
            try:
                options["max_concurrency"] = int(tokens[i])
            except ValueError:
                pass
        elif tok == "--rounds" and i + 1 < len(tokens):
            i += 1
            try:
                options["rounds"] = int(tokens[i])
            except ValueError:
                pass
        elif tok == "--reuse-hub" and i + 1 < len(tokens):
            i += 1
            options["reuse_hub"] = tokens[i]
        elif tok == "--launcher" and i + 1 < len(tokens):
            i += 1
            if tokens[i] not in ("local", "fblearner"):
                return {
                    "error": f"Invalid --launcher value: {tokens[i]}. "
                    "Must be 'local' or 'fblearner'."
                }
            options["launcher"] = tokens[i]
        elif tok == "--workspace" and i + 1 < len(tokens):
            i += 1
            options["workspace"] = tokens[i]
        elif tok == "--workspace-keep-only-final":
            options["workspace_keep_only_final"] = True
        elif tok == "--max-wait" and i + 1 < len(tokens):
            i += 1
            try:
                options["max_wait"] = float(tokens[i])
            except ValueError:
                pass
        elif tok == "--base-inferencer" and i + 1 < len(tokens):
            i += 1
            options["base_inferencer"] = tokens[i]
        elif tok == "--workflow-target-path" and i + 1 < len(tokens):
            i += 1
            options["workflow_target_path"] = tokens[i]
        elif tok == "--model" and i + 1 < len(tokens):
            i += 1
            options["model"] = tokens[i]
        elif tok == "--aggregate-only":
            options["aggregate_only"] = True
        elif tok == "--aggregate-target" and i + 1 < len(tokens):
            i += 1
            options["aggregate_target"] = tokens[i]
        elif tok == "--archive-keep" and i + 1 < len(tokens):
            i += 1
            try:
                options["archive_keep"] = int(tokens[i])
            except ValueError:
                pass
        elif tok == "--archive-reason" and i + 1 < len(tokens):
            i += 1
            options["archive_reason"] = tokens[i]
        elif tok == "--archive-source" and i + 1 < len(tokens):
            i += 1
            options["archive_source"] = tokens[i]
        elif tok == "--force-refresh":
            options["force_refresh"] = True
        # Plan v3 Layer 4 — aggregation settings (filter noise upstream).
        elif tok == "--min-epochs" and i + 1 < len(tokens):
            i += 1
            try:
                options["min_epochs"] = int(tokens[i])
            except ValueError:
                pass
        elif tok == "--exclude-incomparable":
            options["exclude_incomparable"] = True
        elif tok == "--exclude-errored":
            options["exclude_errored"] = True
        i += 1
    return options


def _parse_experiment_args(args: str) -> dict[str, Any]:
    """Parse /experiment inline flags.

    Supported flags:
        --plan <path>           Path to unified proposal plan
        --select H1,H3,...      Comma-separated hypothesis IDs to select
        --implement-default     Implement the default-selected hypotheses
        --group-by <mode>       Grouping mode: batch (default), all, or hypothesis
    """
    options: dict[str, Any] = {}
    tokens = args.split()
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "--plan" and i + 1 < len(tokens):
            i += 1
            options["plan_path"] = tokens[i]
        elif tok == "--select" and i + 1 < len(tokens):
            i += 1
            options["selected_ids"] = [
                h.strip() for h in tokens[i].split(",") if h.strip()
            ]
        elif tok == "--implement-default":
            options["implement_default"] = True
        elif tok == "--group-by" and i + 1 < len(tokens):
            i += 1
            if tokens[i] not in ("batch", "all", "hypothesis"):
                return {
                    "error": f"Invalid --group-by value: {tokens[i]}. "
                    "Must be batch, all, or hypothesis."
                }
            options["group_by"] = tokens[i]
        i += 1
    return options


def _generate_help_text() -> str:
    """Generate help text from the tool registry.

    Falls back to a static string if the registry is unavailable.
    """
    try:
        from rankevolve.src.resources.tools.formatters.markdown import (
            ToolMarkdownFormatter,
        )
        from rankevolve.src.resources.tools.registry import load_all_tools

        tools = load_all_tools()
        formatter = ToolMarkdownFormatter(compact=True)
        return (
            "# RankEvolve Commands\n\n"
            "Built-in: /exit, /quit, /clear, /help, "
            "/understand-codebase <path or description>\n\n"
            + formatter.format_all(list(tools.values()))
        )
    except Exception:
        return (
            "Commands: /exit, /clear, /model <name>, /set-session-root [path], "
            "/task <request>, /task-plan, /task-execute, /task-full, /task-confirm, "
            "/understand-codebase <path or description>, "
            "/research-propose <task>, /research <task>, /propose <task>, "
            "/kn [add|load|search|list|get|update|delete|restore|status|clear|"
            "history|rollback|export|import|spaces], /help"
        )
