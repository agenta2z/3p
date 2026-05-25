# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict
"""ProposalSelectionHandler + Hub helpers (single source of truth).

Owns the framework's Hub-aware selection widget logic and three module-level
helpers used by both the widget path AND the `/experiment` slash-command path:

- `HUB_ANNOUNCEMENT_TEMPLATE` — single byte-pinned template string.
- `format_hub_announcement(n, group_by)` — wording assembler.
- `create_hub(executor, ...)` — calls `HubAwareToolExecutor.create_experiment_hub`
  and pairs the multi_task_id with the canonical announcement string.
- `_group_selected_by_batch(selected, proposals_data)` — moved from inferencer.

The handler narrows `ctx.tool_executor` via `isinstance(HubAwareToolExecutor)`
before calling `create_hub`. If not Hub-aware (or selection is empty), returns
a generic "Selected N proposals" message and SKIPS Hub creation.
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.conversational.conversation_tools import (
    ConversationTool,
    ConversationToolType,
)
from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.conversational.effects import (
    ApplyContextUpdates,
)
from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.conversational.handler_protocol import (
    ConversationToolHandler,
    HandlerContext,
    HandlerResult,
    InferencerEffect,
)
from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.conversational.protocols import (
    HubAwareToolExecutor,
)
from agent_foundation.ui.input_modes import (
    InputMode,
    InputModeConfig,
)

logger: logging.Logger = logging.getLogger(__name__)

HUB_ANNOUNCEMENT_TEMPLATE: str = (
    "Experiment Hub created. {n} hypotheses{group_suffix} queued. "
    "The system will execute them sequentially. Do NOT invoke /task manually."
)


def format_hub_announcement(n: int, group_by: str | None = None) -> str:
    """Single source of truth for the Experiment Hub announcement string.

    Examples:
        format_hub_announcement(2)
            → "Experiment Hub created. 2 hypotheses queued. ..."
        format_hub_announcement(3, "batch")
            → "Experiment Hub created. 3 hypotheses (group-by: batch) queued. ..."
    """
    suffix = f" (group-by: {group_by})" if group_by else ""
    return HUB_ANNOUNCEMENT_TEMPLATE.format(n=n, group_suffix=suffix)


async def create_hub(
    executor: HubAwareToolExecutor,
    selected_details: list[dict[str, Any]],
    proposals_data: dict[str, Any],
    custom_queries: list[str] | None = None,
    group_by: str = "batch",
) -> tuple[str, str]:
    """Create the Experiment Hub and return (multi_task_id, summary_text).

    Both call sites (widget handler + /experiment slash-command) reach this
    helper; the underlying `executor.create_experiment_hub` (server-side
    SessionToolExecutor.create_experiment_hub) is unchanged. All downstream
    side-effects (task_status notifications, _try_start_next_task, session
    state) fire identically.
    """
    multi_task_id = await executor.create_experiment_hub(
        selected_details,
        proposals_data,
        custom_queries=custom_queries or [],
        group_by=group_by,
    )
    summary = format_hub_announcement(len(selected_details), group_by=group_by)
    return multi_task_id, summary


def _group_selected_by_batch(
    selected: list[dict[str, Any]],
    proposals_data: dict[str, Any],
) -> list[dict[str, Any]]:
    """Group selected hypotheses by their research batch, preserving order.

    Args:
        selected: list of hypothesis dicts (full proposal dicts, not just IDs).
        proposals_data: the original proposals metadata from the conversation tool
            (tool.metadata.proposals), which has the full phases/batches structure.

    Returns:
        List of batch group dicts, each with 'batch_id', 'batch_label', 'hypotheses'.
    """
    selected_ids = {h["id"] for h in selected}
    selected_map = {h["id"]: h for h in selected}
    groups: list[dict[str, Any]] = []
    for phase in proposals_data.get("phases", []):
        for batch in phase.get("batches", []):
            batch_hyps = [
                selected_map[hid]
                for hid in batch.get("hypothesis_ids", [])
                if hid in selected_ids
            ]
            if batch_hyps:
                groups.append(
                    {
                        "batch_id": batch.get("id", ""),
                        "batch_label": batch.get("label", ""),
                        "hypotheses": batch_hyps,
                    }
                )
    # Hypotheses not in any batch (orphans) get an "Ungrouped" group.
    assigned = {h["id"] for g in groups for h in g["hypotheses"]}
    orphans = [h for h in selected if h["id"] not in assigned]
    if orphans:
        groups.append(
            {
                "batch_id": "misc",
                "batch_label": "Ungrouped",
                "hypotheses": orphans,
            }
        )
    return groups


class ProposalSelectionHandler(ConversationToolHandler):
    tool_type: ClassVar[ConversationToolType] = ConversationToolType.PROPOSAL_SELECTION

    def build_input_mode(
        self,
        tool: ConversationTool,
        ctx: HandlerContext,
    ) -> InputModeConfig:
        metadata: dict[str, Any] = {"widget_type": "proposal_selection"}
        if tool.metadata:
            metadata.update(tool.metadata)
        return InputModeConfig(
            mode=InputMode.FREE_TEXT,
            prompt=tool.prompt,
            metadata=metadata,
        )

    async def enrich_before_send(
        self,
        tool: ConversationTool,
        ctx: HandlerContext,
    ) -> None:
        """Populate proposals + view metadata for the selection widget.

        Primary: read pre-parsed `phase_outputs["research_proposals_data"]`.
        Fallback: parse via `parse_proposals(workspace)`.
        Also injects `view` (unified plan path) + `view_label` for the
        "View Full Research" button.
        """
        if not tool.metadata:
            tool.metadata = {}

        phase_outputs = ctx.prior_context.get("phase_outputs", {})
        if not isinstance(phase_outputs, dict):
            return

        # 1. Primary: pre-parsed proposals. `research_proposals_data` is
        # stored as a JSON string by `_exec_research_propose` (see
        # `tool_executor.py` — `_json.dumps(proposals_data.to_dict())`),
        # but the React widget at
        # `ProposalSelectionWidget.js:357` expects an object/dict. Deserialize
        # if needed. Same pattern as `message_handlers.py:1155-1162`
        # (`_handle_implement_hypothesis`).
        proposals_data = phase_outputs.get("research_proposals_data")
        if proposals_data:
            if isinstance(proposals_data, str):
                import json as _json

                try:
                    proposals_data = _json.loads(proposals_data)
                except (ValueError, TypeError) as e:
                    logger.warning(
                        "PROPOSAL_SELECTION: research_proposals_data is a "
                        "non-JSON string; widget may render empty: %s",
                        e,
                    )
            tool.metadata["proposals"] = proposals_data
        else:
            # 2. Fallback: parse from workspace path. `parse_proposals`
            # returns a `ProposalSelectionData` dataclass; widget needs a
            # dict, so call `.to_dict()` for symmetry with the Primary path.
            workspace = phase_outputs.get("research_proposals")
            if workspace:
                try:
                    from agent_foundation.ui.proposal_parser import (
                        parse_proposals,
                    )

                    data = parse_proposals(workspace)
                    if data:
                        tool.metadata["proposals"] = data.to_dict()
                except Exception as e:
                    logger.info(
                        "PROPOSAL_SELECTION: parse_proposals('%s') failed: %s",
                        workspace,
                        e,
                    )

        # 3. View injection: unified plan path → "View Full Research" button
        unified_plan = phase_outputs.get("unified_plan_path")
        if unified_plan:
            tool.metadata["view"] = unified_plan
            tool.metadata.setdefault("view_label", "View Full Research")

    async def handle_response(
        self,
        tool: ConversationTool,
        response: dict[str, Any],
        ctx: HandlerContext,
    ) -> HandlerResult:
        if not isinstance(response, dict):
            return HandlerResult(text=str(response))

        selected = response.get("selected_proposals", [])
        custom = response.get("custom_queries", [])
        total = response.get("total_available", "?")

        # Group selected by phase using proposals data
        proposals_data = (tool.metadata or {}).get("proposals", {})
        phase_map: dict[str, list[str]] = {}
        selected_details: list[dict[str, Any]] = []
        for phase_info in proposals_data.get("phases", []):
            label = phase_info.get(
                "label", f"Phase {phase_info.get('phase', '?')}"
            )
            for p in phase_info.get("proposals", []):
                if p.get("id") in selected:
                    phase_map.setdefault(label, []).append(p["id"])
                    selected_details.append(p)

        parts = [f"User selected {len(selected)} of {total} proposals:"]
        for label, ids in phase_map.items():
            parts.append(f"  {label}: {', '.join(ids)}")
        if custom:
            parts.append(f"  Custom queries: {'; '.join(custom)}")

        effects: list[InferencerEffect] = [
            ApplyContextUpdates({
                "_selected_proposals": selected_details,
                "_custom_queries": custom,
            })
        ]

        # Narrow tool_executor via Protocol; only Hub-aware executors create the hub.
        executor = ctx.tool_executor
        if (
            executor is not None
            and isinstance(executor, HubAwareToolExecutor)
            and selected_details
        ):
            try:
                _multi_task_id, summary = await create_hub(
                    executor,
                    selected_details,
                    proposals_data if isinstance(proposals_data, dict) else {},
                    custom_queries=custom,
                )
                parts.append(summary)
            except Exception as err:
                logger.warning(
                    "Experiment hub creation failed: %s", err, exc_info=True
                )

        return HandlerResult(text="\n".join(parts), effects=effects)
