"""Built-in inferencer backend factories.

Importing this module registers ``mock``, ``rovodev``, and ``claude_cli``
on the module-level :func:`get_registry` singleton.

Each non-mock factory builds a backend-specific ``base`` inferencer (step
1) then delegates to :func:`_wrap_in_conversational` for steps 2-11
(prompt renderer, tool registry + filter, dispatcher, ConversationalInferencer
wrap, ``_tool_dispatcher`` attach). This is the only place that knows how
to assemble OpenTeam's conversation-tool stack — adding a new backend
just means writing a base-builder.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

from openteam.server.backends.registry import (
    BackendBuildContext,
    BackendDescriptor,
    get_registry,
)

logger = logging.getLogger(__name__)

_rovodev_model_warning_logged = False


def _filter_tools_by_config(tool_registry: dict, prompt_renderer: object) -> dict:
    """Filter tool_registry based on .initial.config.yaml whitelist.

    Reads ``tools.enabled_action_tools`` from the template's config YAML.
    If the list is defined and non-empty, only tools whose name appears in
    the whitelist (or whose aliases include a whitelisted name) are kept.

    If the config key is absent, empty, or the config cannot be loaded,
    all tools are returned unchanged (safe default).
    """
    try:
        config = getattr(prompt_renderer, "template_config", None) or {}
        tools_config = config.get("tools", {})
        if not isinstance(tools_config, dict):
            return tool_registry
        enabled_list = tools_config.get("enabled_action_tools")
        if not enabled_list or not isinstance(enabled_list, list):
            return tool_registry
        enabled_set = set(enabled_list)
        filtered = {}
        for name, tool_def in tool_registry.items():
            aliases = set(getattr(tool_def, "aliases", []))
            if name in enabled_set or aliases & enabled_set:
                filtered[name] = tool_def
        logger.info(
            "Tool filtering applied: %d/%d tools enabled (whitelist: %s)",
            len(filtered),
            len(tool_registry),
            enabled_list,
        )
        return filtered
    except Exception as e:
        logger.warning(
            "Failed to apply tool filtering from config: %s — returning all tools",
            e,
        )
        return tool_registry


def _wrap_in_conversational(base: Any, ctx: BackendBuildContext) -> Any:
    """Wrap a base inferencer in OpenTeam's ConversationalInferencer stack.

    Steps (verified against the prior monolithic ``_build_rovodev_inferencer``):
      (a) JinjaPromptRenderer pointing at templates/conversation/main/initial.jinja2
      (b) load_all_tools(extra_dirs=[ctx.templates_dir.parent / "tools"])
      (c) _filter_tools_by_config (whitelist from .initial.config.yaml)
      (d) build_integration_executor()
      (e) build dispatcher session_context from ctx.working_dir + ctx.session_store
      (f) construct ToolDispatcher
      (g) define tool_executor closure that injects tool_phase_map
      (h) construct ConversationalInferencer
      (i) attach _tool_dispatcher for per-turn interactive injection
      (j) return conv_inferencer
    """
    from agent_foundation.common.inferencers.agentic_inferencers.conversational.conversational_inferencer import (
        ConversationalInferencer,
    )
    from agent_foundation.common.inferencers.agentic_inferencers.conversational.prompt_rendering import (
        JinjaPromptRenderer,
    )
    from agent_foundation.resources.tools.registry import load_all_tools
    from openteam.server.integrations.dispatch import build_integration_executor
    from openteam.server.services.tool_dispatcher import ToolDispatcher

    # (a) Prompt renderer
    prompt_renderer = JinjaPromptRenderer(
        template_dir=str(ctx.templates_dir),
        template_path="conversation/main/initial.jinja2",
    )

    # (b) + (c) Tool registry, with whitelist
    openteam_tools_dir = ctx.templates_dir.parent / "tools"
    tool_registry = load_all_tools(extra_dirs=[openteam_tools_dir])
    tool_registry = _filter_tools_by_config(tool_registry, prompt_renderer)

    # (d) Integration executor (Slack/TWG fallback path)
    integration_executor = build_integration_executor()

    # (e) + (f) Dispatcher
    _sid = getattr(ctx, "session_id", "") or ""
    _session_root = ""
    if (
        _sid
        and ctx.session_store is not None
        and hasattr(ctx.session_store, "get_session_dir")
    ):
        try:
            _session_root = str(ctx.session_store.get_session_dir(_sid))
        except Exception:
            pass
    session_context = {
        "session_id": _sid,
        "session_root": _session_root,
        "working_dir": ctx.working_dir,
        "server_dir": (
            str(ctx.session_store.server_dir)
            if ctx.session_store is not None
            and hasattr(ctx.session_store, "server_dir")
            else ""
        ),
        "cloud_id": "",
        "uct_token": None,
        "email": None,
    }
    dispatcher = ToolDispatcher(
        tool_registry=tool_registry,
        integration_executor=integration_executor,
        session_context=session_context,
        interactive=None,  # Injected per-turn by run_conversation_turn
    )

    # (g) Forward-decl + tool_executor closure with tool_phase_map injection
    conv_inferencer = None  # bound below; safe — tools only run during run_agentic_loop

    async def tool_executor(tool_name, arguments):
        result = await dispatcher(tool_name, arguments)
        if hasattr(result, "context_updates") and conv_inferencer is not None:
            tool_phase_map = conv_inferencer.prior_context.get("tool_phase_map", {})
            tool_phase = tool_phase_map.get(tool_name)
            if tool_phase and "current_phase" not in result.context_updates:
                result.context_updates["current_phase"] = tool_phase
                result.context_updates["phase_status"] = "completed"
        return result

    # (h) ConversationalInferencer
    conv_inferencer = ConversationalInferencer(
        base_inferencer=base,
        prompt_renderer=prompt_renderer,
        tool_registry=tool_registry,
        tool_executor=tool_executor,
        max_iterations=5,
        compression_threshold=8000,
    )
    # (i) Attach dispatcher for per-turn interactive injection
    conv_inferencer._tool_dispatcher = dispatcher

    logger.info(
        "ConversationalInferencer wrapping %s (tools: %d registered)",
        type(base).__name__,
        len(tool_registry),
    )
    # (j)
    return conv_inferencer


# ── Factory: rovodev ────────────────────────────────────────────────────


def _rovodev_factory(ctx: BackendBuildContext) -> Any:
    """Build a ConversationalInferencer wrapping RovoDevCliInferencer.

    Note: ``RovoDevCliInferencer`` has no ``model_name`` attribute — model
    selection happens via the ``config_override`` JSON string. We log once
    at INFO if the operator passed a model so they know it had no effect.
    """
    global _rovodev_model_warning_logged
    if ctx.model_name and not _rovodev_model_warning_logged:
        logger.info(
            "rovodev backend ignores model_name=%r (RovoDevCliInferencer "
            "selects model via config_override JSON; per-session UI override "
            "is a no-op for this backend)",
            ctx.model_name,
        )
        _rovodev_model_warning_logged = True

    from agent_foundation.common.inferencers.agentic_inferencers.external.rovodev import (
        RovoDevCliInferencer,
    )

    base = RovoDevCliInferencer(
        target_path=ctx.working_dir,
        idle_timeout_seconds=600,
        tool_use_idle_timeout_seconds=600,
        cache_folder=ctx.cache_dir,
        enable_legacy=True,
    )
    logger.info(
        "RovoDevCliInferencer initialized (target_path=%s, acli=%s, cache=%s)",
        ctx.working_dir,
        base.acli_path,
        ctx.cache_dir,
    )
    return _wrap_in_conversational(base, ctx)


def _rovodev_status_message() -> str:
    found = shutil.which("acli")
    if found:
        return f"acli found at {found}"
    return "acli binary not found on PATH — install Atlassian CLI to enable rovodev"


# ── Factory: claude_cli ─────────────────────────────────────────────────


def _claude_cli_factory(ctx: BackendBuildContext) -> Any:
    """Build a ConversationalInferencer wrapping ClaudeCodeCliInferencer.

    The two kwargs that match the class default (idle_timeout_seconds,
    permission_mode) are intentionally explicit so the factory's behavior
    is self-documenting and survives any future default change upstream
    in AgentFoundation.
    """
    from agent_foundation.common.inferencers.agentic_inferencers.external.claude_code.claude_code_cli_inferencer import (
        ClaudeCodeCliInferencer,
    )

    # claude.exe requires its target_path (--cwd) to exist; create on first
    # use so a fresh install with default OPENTEAM_WORKING_DIR=~/MyProjects
    # works without manual setup.
    target = Path(ctx.working_dir)
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.warning("Could not ensure target_path %s exists: %s", target, e)

    base = ClaudeCodeCliInferencer(
        target_path=str(target),
        model_name=ctx.model_name or "opus[1m]",
        idle_timeout_seconds=1800,
        permission_mode="bypassPermissions",
        cache_folder=ctx.cache_dir,
    )
    logger.info(
        "ClaudeCodeCliInferencer initialized (target_path=%s, model=%s, cache=%s)",
        ctx.working_dir,
        base.model_name,
        ctx.cache_dir,
    )
    return _wrap_in_conversational(base, ctx)


def _claude_cli_status_message() -> str:
    found = shutil.which("claude")
    if found:
        return f"claude found at {found}"
    return (
        "claude binary not found on PATH — install Claude Code "
        "(https://claude.com/claude-code) to enable claude_cli"
    )


# ── Factory: mock (guard) ───────────────────────────────────────────────


def _mock_guard_factory(ctx: BackendBuildContext) -> Any:
    """Should never be invoked — mock is service-handled in ConversationService."""
    raise RuntimeError(
        "mock is service-handled — never call mock factory through the registry. "
        "ConversationService._get_session_inferencer short-circuits before reaching here."
    )


# ── Registration ────────────────────────────────────────────────────────

_registry = get_registry()

_registry.register(
    "mock",
    _mock_guard_factory,
    BackendDescriptor(
        name="mock",
        display_name="Mock",
        description="Canned responses, no external dependencies — for UI testing.",
        default_model=None,
        is_available=lambda: True,
        status_message=lambda: "Always available",
    ),
)

_registry.register(
    "rovodev",
    _rovodev_factory,
    BackendDescriptor(
        name="rovodev",
        display_name="Rovo Dev (acli)",
        description="Atlassian Rovo Dev CLI via acli binary.",
        default_model=None,  # selected via config_override JSON
        is_available=lambda: shutil.which("acli") is not None,
        status_message=_rovodev_status_message,
    ),
)

_registry.register(
    "claude_cli",
    _claude_cli_factory,
    BackendDescriptor(
        name="claude_cli",
        display_name="Claude Code (CLI)",
        description="Anthropic Claude Code CLI via the `claude` binary.",
        default_model="opus[1m]",
        is_available=lambda: shutil.which("claude") is not None,
        status_message=_claude_cli_status_message,
    ),
)
