# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.

"""SOPManager — parse, validate, and render Standard Operating Procedures.

An SOP extends StateGraph with domain-specific semantics:
  - SOPPhase(StateNode): adds name, description, subsections, parent_id
  - SOP(StateGraph): collection of SOPPhases
  - SOPManager: parsing (markdown/YAML) + guidance rendering

Evaluation is handled by StateGraphTracker (from stategraph.py), not SOPManager.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from attr import attrib, attrs

from rankevolve.src.utils.common_objects.workflow.stategraph import (
    StateGraph,
    StateGraphTracker,
    StateNode,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns for markdown parsing
# ---------------------------------------------------------------------------

_PHASE_HEADING_RE = re.compile(
    r"^(#{2,3})\s+Phase\s+(\w+)"
    r"(?:\s+--\s+([^[\]:]+?))?"  # optional: -- PhaseName
    r"\s*(?:\[([^\]]*)\])?"      # optional: [directives]
    r"(?:\s*:\s*(.+))?$",         # optional: heading_rest (outputs)
    re.MULTILINE,
)

_OUTPUT_RE = re.compile(r"`(\w+)`")

_SUBSECTION_RE = re.compile(
    r"^\*\*(\w+)\*\*"
    r"\s*(?:\[__(\w[\w\s]*)__\])?"
    r"\s*:\s*$",
    re.MULTILINE,
)

_DEPENDS_ON_RE = re.compile(
    r"__depends\s+on__\s+Phase\s+([\w\s,]+)", re.IGNORECASE
)

_FOR_EACH_RE = re.compile(
    r"__for\s+each__\s+`(\w+)`\s+__in__\s+`(\w+)`"
    r"(?:\s+__sequentially__)?",
    re.IGNORECASE,
)

_GOTO_RE = re.compile(
    r"__go\s+to__\s+Phase\s+(\w+)"
    r"(?:\s+__if__\s+`(\w+)`"
    r"(?:\s+__is__\s+`([^`]+)`)?"
    r")?",
    re.IGNORECASE,
)

_IF_RE = re.compile(
    r"__if__\s+`(\w+)`"
    r"(?:\s+__is__\s+`([^`]+)`)?",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Guidance text templates — used by SOPManager.render_guidance()
#
# Each template is an f-string-style string.  Keeping them here makes it
# easy to tweak wording without hunting through render_guidance() logic.
# ---------------------------------------------------------------------------

_GUIDANCE_HEADER = "### Nextstep Guidance:"

_GUIDANCE_RUNNING = (
    "- **In progress:** Phase {phase_id} "
    "({phase_name}) is currently running. Wait for completion."
)

_GUIDANCE_ERROR = (
    "- **Error occurred:** Phase {phase_id} "
    "({phase_name}) had an error. Review, retry, or adjust."
)

_GUIDANCE_MISSING_OUTPUTS = (
    "- **Phase {phase_id} ({phase_name}) incomplete:** "
    "Missing outputs: {outputs}. "
    "Please provide the missing information."
)

_GUIDANCE_AVAILABLE_HEADER = "The following phases are available:"

_GUIDANCE_AVAILABLE_PHASE = "- **{phase_name}:** {description}"

_GUIDANCE_ALL_COMPLETE = (
    "- **All phases complete.** Suggest iterating or starting a new task."
)

_GUIDANCE_READY = "- **Ready:** Begin with the first available phase."

_GUIDANCE_FOOTER = (
    '\nWhen the user asks "what should I do next?", use the guidance '
    "above to give a concrete recommendation."
)


# ---------------------------------------------------------------------------
# SOP data classes (extend StateNode/StateGraph)
# ---------------------------------------------------------------------------


@dataclass
class SOPSubsection:
    """A subsection within a phase body (e.g., **Tools**, **Rules**)."""
    name: str
    directive: str | None = None
    content: str = ""


@attrs(slots=False, eq=False, hash=False)
class SOPPhase(StateNode):
    """A phase in an SOP — extends StateNode with description and subsections."""
    name: str = attrib(default="")
    description: str = attrib(default="")
    subsections: list = attrib(factory=list)
    parent_id: str = attrib(default=None)
    directives: list = attrib(factory=list)

    def __str__(self) -> str:
        return f"{self.id}: {self.name}" if self.name else self.id


class SOP(StateGraph):
    """A Standard Operating Procedure — a StateGraph of SOPPhases."""

    @property
    def phases(self) -> list[SOPPhase]:
        return self.nodes

    @property
    def phase_ids(self) -> list[str]:
        return self.node_ids

    def get_phase(self, phase_id: str) -> SOPPhase | None:
        return self.get_node(phase_id)

    def get_next_pending_phase(
        self, completed_ids: set[str]
    ) -> "SOPPhase | None":
        """P5: Return the first phase in SOP order whose dependencies are all
        satisfied (in ``completed_ids``) AND that itself is NOT in
        ``completed_ids``. Returns None when no such phase exists (workflow
        complete OR blocked by an unsatisfied dep).

        Used by ``WorkflowContext.to_status_text(sop_obj=...)`` to render an
        explicit "Next pending" line for the LLM, including a
        REQUIRES USER CONFIRMATION instruction when the next pending phase
        carries the ``"requires confirmation"`` directive. Crucial for gate
        phases like Phase 1b that have no tool to call ``start_phase`` —
        without this, ``current_phase`` stays at the previous tool-phase
        forever and gate phases are invisible in the status block.
        """
        for phase in self.phases:
            if phase.id in completed_ids:
                continue
            deps = getattr(phase, "depends_on", []) or []
            if all(dep in completed_ids for dep in deps):
                return phase
        return None

    @property
    def tool_to_phase_map(self) -> dict[str, str]:
        """Extract tool name → phase ID mapping from SOP subsections.

        Parses tool names from Tools/Command subsections and the phase body.
        Tool names are normalized: /understand-codebase → understand_codebase.

        Returns:
            Dict mapping tool names to phase IDs,
            e.g. {"understand_codebase": "1", "research_propose": "2", "task": "3"}
        """
        mapping: dict[str, str] = {}
        for phase in self.phases:
            # Extract from subsections (e.g., Tools[__must__]: - /tool-name)
            for sub in phase.subsections:
                if sub.name.lower() in ("tools", "command"):
                    for line in sub.content.split("\n"):
                        line = line.strip().lstrip("- ")
                        if line.startswith("/"):
                            # Extract tool name: "/understand-codebase <path>" → "understand_codebase"
                            tool_name = line.split()[0].lstrip("/").replace("-", "_")
                            mapping[tool_name] = phase.id
            # Also extract from phase body (e.g., "Command: `/research-propose <goal>`")
            for match in re.finditer(r"Command:\s*`/([a-zA-Z0-9_-]+)", phase.description):
                tool_name = match.group(1).replace("-", "_")
                mapping[tool_name] = phase.id
        return mapping


# ---------------------------------------------------------------------------
# SOPManager
# ---------------------------------------------------------------------------


class SOPManager:
    """Parse SOP definitions and render guidance text."""

    # -- Loading -----------------------------------------------------------

    @staticmethod
    def load(path: Path | str) -> SOP:
        path = Path(path)
        content = path.read_text(encoding="utf-8")
        if path.suffix in (".yaml", ".yml"):
            data = yaml.safe_load(content)
            return SOPManager.parse_yaml(data)
        return SOPManager.parse_markdown(content)

    # -- Markdown parser ---------------------------------------------------

    @staticmethod
    def parse_markdown(content: str) -> SOP:
        phases: list[SOPPhase] = []
        matches = list(_PHASE_HEADING_RE.finditer(content))

        for i, match in enumerate(matches):
            heading_level = len(match.group(1))
            phase_id = match.group(2)
            phase_name_raw = (match.group(3) or "").strip()
            directives_raw = match.group(4) or ""
            heading_rest = match.group(5) or ""

            outputs = _OUTPUT_RE.findall(heading_rest)

            if phase_name_raw:
                name = phase_name_raw
            else:
                name = _OUTPUT_RE.sub("", heading_rest).strip()
                name = re.sub(r"\s+and\s*$", "", name).strip()
                name = re.sub(r"^\s*and\s+", "", name).strip()
                name = name.rstrip(",").strip()

            raw_parts = [d.strip() for d in directives_raw.split(";") if d.strip()]

            depends_on = []
            remaining_directives = []
            foreach_item_var = None
            foreach_collection_var = None
            foreach_sequential = False
            gate_var = None
            gate_value = None
            goto_target = None
            goto_condition_var = None
            goto_condition_value = None

            for part in raw_parts:
                dep_match = _DEPENDS_ON_RE.search(part)
                if dep_match:
                    dep_ids = [d.strip() for d in dep_match.group(1).split(",") if d.strip()]
                    depends_on.extend(dep_ids)
                    continue

                fe_match = _FOR_EACH_RE.search(part)
                if fe_match:
                    foreach_item_var = fe_match.group(1)
                    foreach_collection_var = fe_match.group(2)
                    foreach_sequential = "__sequentially__" in part.lower()
                    continue

                goto_match = _GOTO_RE.search(part)
                if goto_match:
                    goto_target = goto_match.group(1)
                    goto_condition_var = goto_match.group(2)
                    goto_condition_value = goto_match.group(3)
                    continue

                if_match = _IF_RE.search(part)
                if if_match and not goto_match:
                    gate_var = if_match.group(1)
                    gate_value = if_match.group(2)
                    continue

                remaining_directives.append(part.strip().lower())

            body_start = match.end()
            body_end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            body = content[body_start:body_end].strip()

            description, subsections = _parse_subsections(body)

            parent_id = None
            if heading_level == 3:
                for prev_phase in reversed(phases):
                    if prev_phase.parent_id is None:
                        parent_id = prev_phase.id
                        break

            phases.append(
                SOPPhase(
                    id=phase_id,
                    depends_on=depends_on,
                    outputs=outputs,
                    gate_var=gate_var,
                    gate_value=gate_value,
                    goto_target=goto_target,
                    goto_condition_var=goto_condition_var,
                    goto_condition_value=goto_condition_value,
                    foreach_item_var=foreach_item_var,
                    foreach_collection_var=foreach_collection_var,
                    foreach_sequential=foreach_sequential,
                    name=name,
                    description=description,
                    subsections=subsections,
                    parent_id=parent_id,
                    directives=remaining_directives,
                )
            )

        return SOP(phases)

    # -- YAML parser -------------------------------------------------------

    @staticmethod
    def parse_yaml(data: dict[str, Any]) -> SOP:
        phases = []
        for entry in data.get("phases", []):
            subsections = [
                SOPSubsection(
                    name=s.get("name", ""),
                    directive=s.get("directive"),
                    content=s.get("content", ""),
                )
                for s in entry.get("subsections", [])
            ]
            phases.append(
                SOPPhase(
                    id=str(entry.get("id", "")),
                    depends_on=[str(d) for d in entry.get("depends_on", [])],
                    outputs=entry.get("outputs", []),
                    gate_var=entry.get("gate_var"),
                    gate_value=entry.get("gate_value"),
                    goto_target=entry.get("goto_target"),
                    goto_condition_var=entry.get("goto_condition_var"),
                    goto_condition_value=entry.get("goto_condition_value"),
                    foreach_item_var=entry.get("foreach_item_var"),
                    foreach_collection_var=entry.get("foreach_collection_var"),
                    foreach_sequential=entry.get("foreach_sequential", False),
                    name=entry.get("name", ""),
                    description=entry.get("description", ""),
                    subsections=subsections,
                    parent_id=entry.get("parent_id"),
                    directives=entry.get("directives", []),
                )
            )
        return SOP(phases)

    # -- Guidance rendering ------------------------------------------------

    @staticmethod
    def render_guidance(
        tracker: StateGraphTracker,
        sop: SOP | None = None,
        context: dict[str, Any] | None = None,
        sop_config: dict[str, Any] | None = None,
    ) -> str:
        """Render next-step guidance from tracker state."""
        if context is None:
            context = {}
        parts: list[str] = [_GUIDANCE_HEADER]

        if tracker.status == "running" and tracker.current_state:
            phase = sop.get_phase(tracker.current_state) if sop else None
            phase_name = phase.name if phase else tracker.current_state
            parts.append(
                _GUIDANCE_RUNNING.format(
                    phase_id=tracker.current_state, phase_name=phase_name,
                )
            )
        elif tracker.status == "error" and tracker.current_state:
            phase = sop.get_phase(tracker.current_state) if sop else None
            phase_name = phase.name if phase else tracker.current_state
            parts.append(
                _GUIDANCE_ERROR.format(
                    phase_id=tracker.current_state, phase_name=phase_name,
                )
            )
        else:
            missing = tracker.get_missing_outputs()
            if missing:
                for phase_id, m in missing.items():
                    phase = sop.get_phase(phase_id) if sop else None
                    phase_name = phase.name if phase else phase_id
                    parts.append(
                        _GUIDANCE_MISSING_OUTPUTS.format(
                            phase_id=phase_id,
                            phase_name=phase_name,
                            outputs=", ".join(f"`{o}`" for o in m),
                        )
                    )
            else:
                available = tracker.get_available_next()
                if available:
                    parts.append(_GUIDANCE_AVAILABLE_HEADER)
                    for node in available:
                        phase = sop.get_phase(node.id) if sop else None
                        if phase:
                            desc = phase.description
                            parts.append(
                                _GUIDANCE_AVAILABLE_PHASE.format(
                                    phase_name=phase.name,
                                    description=desc.strip(),
                                )
                            )
                            for sub in phase.subsections:
                                instruction = _get_directive_instruction(
                                    sub.name, sub.directive, sop_config,
                                )
                                if instruction:
                                    parts.append(f"  {instruction}")
                                parts.append(f"  {sub.content.strip()}")
                        else:
                            parts.append(f"- **{node.id}**")
                elif tracker.status == "completed":
                    parts.append(_GUIDANCE_ALL_COMPLETE)
                else:
                    parts.append(_GUIDANCE_READY)

            # Task queue status (shown regardless of phase state)
            task_queue = context.get("task_queue", [])
            if task_queue:
                queue_summary = context.get("task_queue_summary", "")
                if queue_summary:
                    parts.append(f"\n**Task queue:** {queue_summary}")
                next_task = next(
                    (t for t in task_queue if t.get("status") == "queued"), None
                )
                if next_task:
                    h_id = next_task.get("hypothesis_id") or next_task.get("task_id", "")
                    parts.append(f"  Next: {h_id} — {next_task.get('title', '')}")

        parts.append(_GUIDANCE_FOOTER)
        return "\n".join(parts)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_subsections(body: str) -> tuple[str, list[SOPSubsection]]:
    matches = list(_SUBSECTION_RE.finditer(body))
    if not matches:
        return body, []

    description = body[: matches[0].start()].strip()
    subsections = []

    for i, match in enumerate(matches):
        name = match.group(1)
        directive = match.group(2)
        if directive:
            directive = directive.strip().lower()

        content_start = match.end()
        content_end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        content = body[content_start:content_end].strip()

        subsections.append(SOPSubsection(name=name, directive=directive, content=content))

    return description, subsections


def _get_directive_instruction(
    section_name: str, directive: str | None, sop_config: dict[str, Any] | None,
) -> str:
    if not directive or not sop_config:
        return ""
    subsections_config = sop_config.get("subsections", {})
    section_config = subsections_config.get(section_name, {})
    directives_map = section_config.get("directives", {})
    return directives_map.get(f"__{directive}__", directives_map.get(directive, ""))
