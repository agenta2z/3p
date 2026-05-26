"""Integration tests for the slot-defaults injection hook in `_walk`.

Covers the YAML-time mechanism that fills missing template fields based
on each orchestrator's class-declared ``SLOT_DEFAULTS``:

- direct slot path: applies to direct child slot
- list-element wildcard: ``flow_configs.*.followup_inferencer`` walks
  list and applies to each item's nested slot
- wrapping descent: when child is a transparent wrapper
  (``_TEMPLATE_TRANSPARENT_SLOTS``), defaults pass through to inner slots
- MRO inheritance + atomic-bundle replacement on subclasses
- ``_disable_slot_defaults_`` escape hatch
- per-key dict merge semantics preserved through Hydra walk
"""

from __future__ import annotations

import pytest
from omegaconf import OmegaConf

from python_utils.config_utils import instantiate

_MOD = "test_slot_defaults_helpers"


# ---------------------------------------------------------------------------
# Direct slot defaults
# ---------------------------------------------------------------------------


class TestDirectSlotDefaults:
    def test_unset_slot_field_gets_default(self):
        cfg = OmegaConf.create({
            "_target_": f"{_MOD}.FakeBTA",
            "breakdown_inferencer": {
                "_target_": f"{_MOD}.FakeTemplatedLeaf",
                "name": "br",
            },
        })
        obj = instantiate(cfg)
        # Default should have been injected before instantiation.
        assert obj.breakdown_inferencer.template_root_space == "task_breakdown"

    def test_user_set_slot_field_wins(self):
        cfg = OmegaConf.create({
            "_target_": f"{_MOD}.FakeBTA",
            "breakdown_inferencer": {
                "_target_": f"{_MOD}.FakeTemplatedLeaf",
                "template_root_space": "custom",
                "name": "br",
            },
        })
        obj = instantiate(cfg)
        assert obj.breakdown_inferencer.template_root_space == "custom"

    def test_aggregator_dict_default_full_when_user_absent(self):
        cfg = OmegaConf.create({
            "_target_": f"{_MOD}.FakeBTA",
            "aggregator_inferencer": {
                "_target_": f"{_MOD}.FakeTemplatedLeaf",
            },
        })
        obj = instantiate(cfg)
        assert obj.aggregator_inferencer.template_variables == {
            "task_preamble": "aggregation",
            "task_instructions": "aggregation",
            "task_response_format": "aggregation",
        }

    def test_aggregator_per_key_merge_user_overrides_one_key(self):
        cfg = OmegaConf.create({
            "_target_": f"{_MOD}.FakeBTA",
            "aggregator_inferencer": {
                "_target_": f"{_MOD}.FakeTemplatedLeaf",
                "template_variables": {"task_instructions": "create_role"},
            },
        })
        obj = instantiate(cfg)
        assert obj.aggregator_inferencer.template_variables == {
            "task_preamble": "aggregation",
            "task_instructions": "create_role",  # user override wins
            "task_response_format": "aggregation",
        }

    def test_slot_absent_in_yaml_does_nothing(self):
        # No breakdown_inferencer, no aggregator_inferencer: hook walks
        # SLOT_DEFAULTS, finds no matching child key, applies nothing.
        cfg = OmegaConf.create({"_target_": f"{_MOD}.FakeBTA"})
        obj = instantiate(cfg)
        assert obj.breakdown_inferencer is None
        assert obj.aggregator_inferencer is None


# ---------------------------------------------------------------------------
# Opt-out
# ---------------------------------------------------------------------------


class TestDisableOptOut:
    def test_disable_skips_all_slot_defaults(self):
        cfg = OmegaConf.create({
            "_target_": f"{_MOD}.FakeBTA",
            "_disable_slot_defaults_": True,
            "breakdown_inferencer": {
                "_target_": f"{_MOD}.FakeTemplatedLeaf",
            },
            "aggregator_inferencer": {
                "_target_": f"{_MOD}.FakeTemplatedLeaf",
            },
        })
        obj = instantiate(cfg)
        # Defaults skipped → fields stay at attrib defaults.
        assert obj.breakdown_inferencer.template_root_space is None
        assert obj.aggregator_inferencer.template_variables == {}


# ---------------------------------------------------------------------------
# MRO inheritance + atomic-bundle replacement
# ---------------------------------------------------------------------------


class TestMROInheritance:
    def test_subclass_inherits_parent_slot_defaults(self):
        cfg = OmegaConf.create({
            "_target_": f"{_MOD}.FakeBTASubclass",
            "breakdown_inferencer": {
                "_target_": f"{_MOD}.FakeTemplatedLeaf",
            },
            "extra_inferencer": {
                "_target_": f"{_MOD}.FakeTemplatedLeaf",
            },
        })
        obj = instantiate(cfg)
        # Inherited from parent BTA
        assert obj.breakdown_inferencer.template_root_space == "task_breakdown"
        # Added by subclass
        assert obj.extra_inferencer.template_root_space == "extra"

    def test_subclass_override_replaces_parent_atomically(self):
        cfg = OmegaConf.create({
            "_target_": f"{_MOD}.FakeBTAOverride",
            "breakdown_inferencer": {
                "_target_": f"{_MOD}.FakeTemplatedLeaf",
            },
            # aggregator_inferencer NOT overridden — should inherit parent's
            "aggregator_inferencer": {
                "_target_": f"{_MOD}.FakeTemplatedLeaf",
            },
        })
        obj = instantiate(cfg)
        # breakdown overridden by subclass
        assert obj.breakdown_inferencer.template_root_space == "custom_space"
        # aggregator NOT overridden — uses parent's defaults
        assert (
            obj.aggregator_inferencer.template_variables.get("task_preamble")
            == "aggregation"
        )


# ---------------------------------------------------------------------------
# List-element wildcard
# ---------------------------------------------------------------------------


class TestListElementWildcard:
    def test_followup_default_applied_per_flow(self):
        cfg = OmegaConf.create({
            "_target_": f"{_MOD}.FakeMultiFlow",
            "flow_configs": [
                {
                    "input": "x",
                    "followup_inferencer": {
                        "_target_": f"{_MOD}.FakeTemplatedLeaf",
                    },
                },
                {
                    "input": "y",
                    "followup_inferencer": {
                        "_target_": f"{_MOD}.FakeTemplatedLeaf",
                    },
                },
            ],
        })
        obj = instantiate(cfg)
        for cfg_dict in obj.flow_configs:
            leaf = cfg_dict["followup_inferencer"]
            assert leaf.template_variables == {
                "task_preamble": "aggregation",
                "task_instructions": "aggregation",
                "task_response_format": "aggregation",
            }

    def test_followup_user_override_per_flow_per_key(self):
        cfg = OmegaConf.create({
            "_target_": f"{_MOD}.FakeMultiFlow",
            "flow_configs": [
                {
                    "input": "x",
                    "followup_inferencer": {
                        "_target_": f"{_MOD}.FakeTemplatedLeaf",
                        "template_variables": {"task_preamble": "custom"},
                    },
                },
            ],
        })
        obj = instantiate(cfg)
        leaf = obj.flow_configs[0]["followup_inferencer"]
        assert leaf.template_variables == {
            "task_preamble": "custom",
            "task_instructions": "aggregation",
            "task_response_format": "aggregation",
        }


# ---------------------------------------------------------------------------
# Wrapping descent
# ---------------------------------------------------------------------------


class TestWrappingDescent:
    def test_descent_through_transparent_wrapper(self):
        # FakeBTAWithWrappingAggregator's aggregator slot is filled by a
        # FakeTransparentWrapper, whose `inner` slot is transparent. The
        # parent's aggregation defaults should pass through to `inner`.
        cfg = OmegaConf.create({
            "_target_": f"{_MOD}.FakeBTAWithWrappingAggregator",
            "aggregator_inferencer": {
                "_target_": f"{_MOD}.FakeTransparentWrapper",
                "inner": {
                    "_target_": f"{_MOD}.FakeTemplatedLeaf",
                },
            },
        })
        obj = instantiate(cfg)
        # Parent's aggregation defaults landed on the inner leaf, NOT on
        # the wrapper (wrapper has no template fields anyway).
        assert obj.aggregator_inferencer.inner.template_variables == {
            "task_preamble": "aggregation",
            "task_instructions": "aggregation",
            "task_response_format": "aggregation",
        }


# ---------------------------------------------------------------------------
# No-decl no-op (class without SLOT_DEFAULTS)
# ---------------------------------------------------------------------------


class TestNoDecl:
    def test_class_without_slot_defaults_is_noop(self):
        # FakeTemplatedLeaf has no SLOT_DEFAULTS. Instantiating it should
        # not error or alter anything.
        cfg = OmegaConf.create({
            "_target_": f"{_MOD}.FakeTemplatedLeaf",
            "template_root_space": "implementation",
        })
        obj = instantiate(cfg)
        assert obj.template_root_space == "implementation"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
