# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.

"""Conversation tool data models.

Defines the structured types for conversation tools that the LLM can invoke
to interact with the user: clarification, single/multiple choice, confirmation,
and tool argument collection.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


class ConversationToolType(str, enum.Enum):
    """Conversation tool type values.

    Subclasses str so members compare equal to their string value
    (e.g., `ConversationToolType.CLARIFICATION == "clarification"`)
    and hash identically — registry lookups work with either form.

    Wire format is byte-identical to the previous plain-string constants:
    `to_dict()` emits the string value, `from_dict()` coerces strings back
    to enum members.
    """

    CLARIFICATION = "clarification"
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    CONFIRMATION = "confirmation"
    TOOL_ARGUMENT_FORM = "tool_argument_form"
    PROPOSAL_SELECTION = "proposal_selection"


@dataclass
class ChoiceItem:
    """A single choice option for single/multiple choice tools."""

    label: str
    value: str
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"label": self.label, "value": self.value}
        if self.description:
            d["description"] = self.description
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChoiceItem:
        return cls(
            label=data.get("label", ""),
            value=data.get("value", ""),
            description=data.get("description", ""),
        )


@dataclass
class ConversationTool:
    """A conversation tool invocation parsed from the LLM response.

    Represents the LLM's request to interact with the user in a structured
    way (ask a question, present choices, collect form input, etc.).

    `metadata` is the freeform extension point. Beyond the per-handler
    keys (view/view_label/yes_label/no_label/tool_params/proposals/...),
    these CONVENTION keys are honored by the rich-group dispatch path
    (see conversational_inferencer._handle_conversation_tools):

      group_id              str — tools sharing this in one turn form an
                                  atomic resolution group (rich-group path)
      on_group_resolve      "flatten"|"hide"|"keep" — what happens to THIS
                                  tool when ANY child in its group resolves.
                                  Default "flatten" (grayed disabled card
                                  with badge); "hide" removes from chat;
                                  "keep" renders live widget with disabled
                                  prop (read-only reference content).
      on_yes_action         str — server-side side-effect when THIS widget's
                                  YES button is clicked (v1: "open_experiment_hub").
                                  PURELY BEHAVIORAL — does not affect UI rendering.
      hide_no_button        bool — when true, the NO button is not rendered
                                   (single-action CTA mode). Use together with
                                   `on_yes_action` for one-button CTAs.

    Deprecated CONVENTION keys (Plan v8 — tolerated as no-op for in-flight
    LLM emissions / stale React bundles; drop in next release):
      group_role            str — telemetry/labeling stub (0 read sites)
      on_self_submit_action str — renamed to on_yes_action
    """

    tool_type: ConversationToolType
    prompt: str = ""
    choices: list[ChoiceItem] = field(default_factory=list)
    allow_custom: bool = True
    expected_input_type: str = "free_text"  # "free_text" or "path"
    prefix: str = ""  # Path prefix for path input mode
    tool_name: str = ""  # For tool_argument_form: which tool
    fields: list[dict[str, Any]] = field(default_factory=list)  # For tool_argument_form
    output_vars: list[str] = field(default_factory=list)  # Variable names to capture
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        # Cast enum to str for byte-identical wire format
        d: dict[str, Any] = {"tool_type": str(self.tool_type.value)}
        if self.prompt:
            d["prompt"] = self.prompt
        if self.choices:
            d["choices"] = [c.to_dict() for c in self.choices]
        if not self.allow_custom:
            d["allow_custom"] = False
        if self.tool_name:
            d["tool_name"] = self.tool_name
        if self.fields:
            d["fields"] = self.fields
        if self.metadata:
            d["metadata"] = self.metadata
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConversationTool:
        choices = [
            ChoiceItem.from_dict(c) for c in data.get("choices", [])
        ]
        # Coerce string → enum member; raises ValueError on unknown value.
        # Caller is expected to gate on `if data.get("tool_type"):` before invoking.
        return cls(
            tool_type=ConversationToolType(data["tool_type"]),
            prompt=data.get("prompt", ""),
            choices=choices,
            allow_custom=data.get("allow_custom", True),
            expected_input_type=data.get("expected_input_type", "free_text"),
            prefix=data.get("prefix", ""),
            tool_name=data.get("tool_name", ""),
            fields=data.get("fields", []),
            output_vars=data.get("output_vars", data.get("output", [])),
            metadata=data.get("metadata", {}),
        )
