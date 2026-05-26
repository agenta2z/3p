"""Registry-driven generic tool dispatcher.

Reads the 'executor' field from each tool's tool.json (via source_path on
ToolDefinition) and imports the callable at construction time. Conforms to
the ToolExecutorCallable protocol: async (tool_name, arguments) → ToolExecutionResult.

Usage::

    dispatcher = ToolDispatcher(
        tool_registry=tool_registry,          # {name: ToolDefinition}
        integration_executor=integration_executor,
        session_context={
            "working_dir": "/path/to/working_dir",
            "cloud_id": "...",
            "uct_token": "...",
        },
    )

    # In tool_executor closure:
    result = await dispatcher(tool_name, arguments)

Adding a new tool:
    1. Add "executor": "module.path:execute" to tool.json
    2. Implement execute(arguments, session_context) -> ToolExecutionResult in executor.py
    No changes needed to dispatch.py or conversation_service.py.
"""

from __future__ import annotations

import importlib
import json
import logging
from pathlib import Path
from typing import Any, Callable

from agent_foundation.resources.tools.models import ToolDefinition

logger = logging.getLogger(__name__)


class ToolDispatcher:
    """Registry-driven generic tool dispatcher.

    Reads 'executor' field from each tool's tool.json (via source_path on
    ToolDefinition). Falls back to IntegrationToolExecutor for integration
    tools (Slack, TWG). Session context is captured at construction —
    __call__ conforms to ToolExecutorCallable protocol.
    """

    def __init__(
        self,
        tool_registry: dict[str, ToolDefinition],
        integration_executor: Any,
        session_context: dict[str, Any],
        interactive: Any = None,
    ) -> None:
        self._integration_executor = integration_executor
        self._session_context = session_context
        self._interactive = interactive          # WebSocketInteractive — injected per-turn
        self._tool_registry = tool_registry     # kept for asynchronous flag check
        self._executor_map: dict[str, Callable] = {}
        self._load_executors(tool_registry)
        logger.info(
            "[ToolDispatcher] Loaded %d registry executors: %s",
            len(self._executor_map),
            list(self._executor_map.keys()),
        )

    def _load_executors(self, tool_registry: dict[str, ToolDefinition]) -> None:
        """Read 'executor' from each tool's source tool.json, import the callable."""
        for name, tool_def in tool_registry.items():
            if not tool_def.source_path:  # guard: skip tools without source_path
                continue
            tool_json_path = Path(tool_def.source_path)
            if not tool_json_path.exists():
                logger.warning(
                    "[ToolDispatcher] tool.json not found for %s at %s",
                    name, tool_json_path,
                )
                continue
            try:
                data = json.loads(tool_json_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(
                    "[ToolDispatcher] Failed to read tool.json for %s: %s", name, e
                )
                continue
            executor_ref = data.get("executor")
            if executor_ref:
                try:
                    self._executor_map[name] = self._import_callable(executor_ref)
                    logger.debug(
                        "[ToolDispatcher] Loaded executor for %s: %s", name, executor_ref
                    )
                except (ImportError, AttributeError, ValueError) as e:
                    logger.warning(
                        "[ToolDispatcher] Failed to load executor for %s (%s): %s",
                        name, executor_ref, e,
                    )

    @staticmethod
    def _import_callable(ref: str) -> Callable:
        """Import 'module.path:callable_name' → callable.

        Args:
            ref: Entry-point style reference, e.g.
                 'openteam.server.resources.tools.create_role.executor:execute'

        Raises:
            ValueError: If ref doesn't contain ':'.
            ImportError: If module cannot be imported.
            AttributeError: If callable not found in module.
        """
        if ":" not in ref:
            raise ValueError(
                f"Invalid executor reference '{ref}' — expected 'module.path:callable'"
            )
        module_path, _, callable_name = ref.rpartition(":")
        module = importlib.import_module(module_path)
        return getattr(module, callable_name)

    def handles(self, tool_name: str) -> bool:
        """Check if this dispatcher can handle the given tool name."""
        return (
            tool_name in self._executor_map
            or self._integration_executor.handles(tool_name)
        )

    async def __call__(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> Any:  # ToolExecutionResult
        """Dispatch tool_name to the appropriate executor.

        Priority:
        1. Async (background) registry tools — spawn task, return immediately
        2. Sync registry-declared executors (create_role, role_setup, future tools)
        3. Integration tools fallback (Slack, TWG)
        4. Unknown tool fallback
        """
        from agent_foundation.common.inferencers.agentic_inferencers.conversational.protocols import (
            ToolExecutionResult,
        )

        # 1. Async tools → background task with subtab
        tool_def = self._tool_registry.get(tool_name)
        if tool_def and tool_def.asynchronous and self._interactive:
            return await self._dispatch_as_task(tool_name, arguments, tool_def)

        # 2. Registry-declared executors (sync)
        if tool_name in self._executor_map:
            logger.info("[ToolDispatcher] Dispatching '%s' to registry executor", tool_name)
            return await self._executor_map[tool_name](
                arguments, self._session_context
            )

        # 2. Integration tools fallback (Slack, TWG)
        if self._integration_executor.handles(tool_name):
            logger.info("[ToolDispatcher] Dispatching '%s' to integration executor", tool_name)
            return await self._integration_executor(tool_name, arguments)

        # 4. Unknown
        logger.warning("[ToolDispatcher] Unknown tool: %s", tool_name)
        return ToolExecutionResult(result=f"Unknown tool: {tool_name}")

    async def _dispatch_as_task(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        tool_def: Any,
    ) -> Any:
        """Spawn a background asyncio task for long-running tools.

        Immediately sends task_status "starting", spawns the executor via
        asyncio.create_task(), and returns a brief ToolExecutionResult so the
        agentic loop continues. The task panel in the UI streams progress.
        When the task completes, a task_completed WS event triggers the
        client-side auto-advance mechanism for the next SOP phase.
        """
        import asyncio
        import uuid

        from agent_foundation.common.inferencers.agentic_inferencers.conversational.protocols import (
            ToolExecutionResult,
        )

        task_id = f"task-{uuid.uuid4().hex[:8]}"
        request_label = (
            arguments.get("role_description")
            or arguments.get("role_document_path")
            or arguments.get("request")
            or tool_name
        )
        if isinstance(request_label, str):
            request_label = request_label[:80]

        # Notify UI: task starting — creates task_ref card in conversation
        await self._interactive.send_task_status(
            task_id, "starting", request=request_label, tool_name=tool_name,
        )

        interactive_ref = self._interactive  # capture for closure

        # Allocate per-task workspace via shared helper.
        # Path B (server-affiliated): session_root → <session>/tasks/<tool>_<TS>_<uuid8>/
        # Path A (standalone): no session_root → _runtime/tasks/<tool>/<tool>_<TS>_<uuid8>/
        from openteam.server.resources.tools._shared.workspace_allocator import (
            allocate_tool_workspace,
        )
        session_root_str = self._session_context.get("session_root", "")
        if session_root_str:
            from pathlib import Path as _Path
            tasks_parent = _Path(session_root_str) / "tasks"
            tasks_parent.mkdir(parents=True, exist_ok=True)
            task_workspace = allocate_tool_workspace(tool_name, base_dir=tasks_parent)
        else:
            task_workspace = allocate_tool_workspace(tool_name, base_dir=None)
        task_working_dir = str(task_workspace)

        async def _run() -> None:
            try:
                await interactive_ref.send_task_status(
                    task_id, "running", tool_name=tool_name,
                )
                task_context = {
                    **self._session_context,
                    "task_id": task_id,
                    "session_root": session_root_str,
                    "working_dir": task_working_dir,
                    "interactive": interactive_ref,
                }
                result = await self._executor_map[tool_name](arguments, task_context)

                result_summary = (
                    str(result.result)[:500]
                    if result and result.result
                    else ""
                )
                # Patch 3.6 — generalized document_path fallback chain so /task's
                # workspace_path / plan_path / impl_path artifacts surface in the UI
                # via the same hook /create_role uses. role_document_path stays first
                # so /create_role's existing UI behavior is unchanged.
                _ctx = result.context_updates if (result and result.context_updates) else {}
                _doc = (
                    _ctx.get("role_document_path")
                    or _ctx.get("plan_path")
                    or _ctx.get("impl_path")
                    or _ctx.get("doc_path")
                    or _ctx.get("workspace_path")
                )
                await interactive_ref._send({
                    "type": "task_completed",
                    "task_id": task_id,
                    "tool_name": tool_name,
                    "result_summary": result_summary,
                    "workspace": task_working_dir,
                    "document_path": _doc,
                    "context_updates": dict(_ctx),
                })
                await interactive_ref.send_task_status(
                    task_id, "completed", tool_name=tool_name,
                )
            except Exception as e:
                logger.error(
                    "[ToolDispatcher] Background task %s (%s) error: %s",
                    task_id, tool_name, e, exc_info=True,
                )
                try:
                    await interactive_ref.send_task_status(
                        task_id, "error", tool_name=tool_name, error=str(e)[:200],
                    )
                except Exception:
                    pass

        asyncio.create_task(_run())

        return ToolExecutionResult(
            result=(
                f"[Task {task_id} started — running '{tool_name}' in background. "
                "See task panel for progress.]"
            ),
            context_updates={"task_id": task_id, "is_background_task": True},
        )
