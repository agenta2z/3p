# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.

"""Callable protocols for ConversationalInferencer pluggability.

These protocols define the interfaces that server-layer components implement
and framework-layer ConversationalInferencer consumes, keeping the dependency
direction clean (framework never imports server).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class ToolExecutionResult:
    """Return type from tool executor."""

    result: str  # tool output text
    context_updates: dict[str, Any] = field(
        default_factory=dict
    )  # updates to apply to prior_context


@runtime_checkable
class ToolExecutorCallable(Protocol):
    async def __call__(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> ToolExecutionResult: ...


@runtime_checkable
class HubAwareToolExecutor(ToolExecutorCallable, Protocol):
    """Capability Protocol for executors that can create batched task hubs.

    `SessionToolExecutor` (server-side) structurally satisfies this. Framework
    handlers narrow `ctx.tool_executor` via `isinstance(executor, HubAwareToolExecutor)`
    before calling `create_experiment_hub`.

    Mock gotcha: bare `Mock()` instances will lie about implementing this Protocol
    because they autocreate any attribute access. Tests MUST use
    `MagicMock(spec=ToolExecutorCallable)` (spec-restricted) to avoid false
    positives. A guardrail test in `test_proposal_selection_handler.py` locks
    in this discipline.
    """

    async def create_experiment_hub(
        self,
        selected_details: list[dict[str, Any]],
        proposals_data: dict[str, Any],
        custom_queries: list[str] | None = None,
        group_by: str = "batch",
    ) -> str: ...


@runtime_checkable
class ContextCompressorCallable(Protocol):
    async def __call__(self, context: str, max_length: int) -> str: ...


@runtime_checkable
class PromptRenderer(Protocol):
    def render(self, variables: dict[str, Any]) -> str: ...

    @property
    def template_source(self) -> str: ...

    def set_variable(self, name: str, value: str) -> None:
        """Set a runtime template variable.

        Typed replacement for the duck call
        `getattr(prompt_renderer, "variable_manager", None).set(name, value)`
        used throughout the conversational inferencer for collecting widget
        responses. Concrete implementations forward to their underlying
        VariableManager.
        """
        ...
