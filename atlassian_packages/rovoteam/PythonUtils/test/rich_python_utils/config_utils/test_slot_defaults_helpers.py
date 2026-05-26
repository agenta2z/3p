"""Importable test classes for slot-defaults integration tests.

Like test_helpers.py, these need to be in a real Python module so Hydra's
``_target_`` can resolve them via importlib.
"""

from __future__ import annotations

from typing import Any, ClassVar, List, Optional

from attr import attrib, attrs


# A minimal "templated leaf" that has the four template fields so
# InferencerTemplateDefaults.apply_to has somewhere to write.
@attrs(slots=False)
class FakeTemplatedLeaf:
    template_root_space: Optional[str] = attrib(default=None)
    template_key: str = attrib(default="")
    template_variables: dict = attrib(factory=dict)
    template_extra_feed: dict = attrib(factory=dict)
    name: str = attrib(default="")


# A "transparent wrapper" that declares one inner slot transparent.
@attrs(slots=False)
class FakeTransparentWrapper:
    _TEMPLATE_TRANSPARENT_SLOTS: ClassVar[List[str]] = ["inner"]

    inner: Optional[FakeTemplatedLeaf] = attrib(default=None)


# A simple defaults bundle (duck-typed: implements apply_to).
class _SimpleDefaults:
    def __init__(self, *, template_root_space=None, template_variables=None):
        self.template_root_space = template_root_space
        self.template_variables = template_variables or {}

    def apply_to(self, node, parent_node=None):
        if not isinstance(node, dict):
            return
        if self.template_root_space is not None and "template_root_space" not in node:
            node["template_root_space"] = self.template_root_space
        if self.template_variables:
            existing = node.get("template_variables") or {}
            merged = dict(self.template_variables)
            merged.update(existing)
            node["template_variables"] = merged


_TASK_BREAKDOWN_DEFAULTS = _SimpleDefaults(template_root_space="task_breakdown")
_AGGREGATION_DEFAULTS = _SimpleDefaults(
    template_variables={
        "task_preamble": "aggregation",
        "task_instructions": "aggregation",
        "task_response_format": "aggregation",
    }
)


# ---------------------------------------------------------------------------
# Orchestrator-style test classes that declare SLOT_DEFAULTS
# ---------------------------------------------------------------------------


@attrs(slots=False)
class FakeBTA:
    """Mimics BreakdownThenAggregateInferencer for slot-default tests."""

    SLOT_DEFAULTS: ClassVar[dict] = {
        "breakdown_inferencer": _TASK_BREAKDOWN_DEFAULTS,
        "aggregator_inferencer": _AGGREGATION_DEFAULTS,
    }

    breakdown_inferencer: Optional[Any] = attrib(default=None)
    aggregator_inferencer: Optional[Any] = attrib(default=None)
    worker_factory: Optional[Any] = attrib(default=None)


# Subclass that adds a NEW slot default (atomic-bundle replacement
# is tested via override_default).
@attrs(slots=False)
class FakeBTASubclass(FakeBTA):
    SLOT_DEFAULTS: ClassVar[dict] = {
        # New slot — adds to inherited entries.
        "extra_inferencer": _SimpleDefaults(template_root_space="extra"),
    }

    extra_inferencer: Optional[Any] = attrib(default=None)


# Subclass that REPLACES one of the parent's slot defaults wholesale.
@attrs(slots=False)
class FakeBTAOverride(FakeBTA):
    SLOT_DEFAULTS: ClassVar[dict] = {
        # Replace the breakdown default with a different bundle.
        "breakdown_inferencer": _SimpleDefaults(template_root_space="custom_space"),
    }


# Orchestrator with a list-element slot path (mimics MultiFlow's
# flow_configs.*.followup_inferencer pattern).
@attrs(slots=False)
class FakeMultiFlow:
    SLOT_DEFAULTS: ClassVar[dict] = {
        "flow_configs.*.followup_inferencer": _AGGREGATION_DEFAULTS,
    }

    flow_configs: List[dict] = attrib(factory=list)


# Orchestrator that fills its aggregator with a transparent wrapper —
# used to test wrapping descent.
@attrs(slots=False)
class FakeBTAWithWrappingAggregator:
    SLOT_DEFAULTS: ClassVar[dict] = {
        "aggregator_inferencer": _AGGREGATION_DEFAULTS,
    }

    aggregator_inferencer: Optional[Any] = attrib(default=None)
