"""Unit tests: _ImportFactory aggregator isolation for role_setup.yaml.

Verifies the fix for the shared-aggregator concurrency bug: when multiple
inner BTA workers are created from the ``_import_`` factory, each must
receive its own ``aggregator_inferencer`` instance so concurrent workers
don't race to overwrite each other's ``_workspace``.

No live API calls — all assertions are on object identity.

Run::

    cd /Users/tchen7/MyProjects/CoreProjects/OpenTeam
    PYTHONPATH="../PythonUtils/src:../AgentFoundation/src:src:." \\
    python -m pytest test/openteam/resources/tools/role_setup/test_import_factory_isolation.py -v
"""

from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent
_SRC_ROOT = _ROOT.parents[4] / "src" / "openteam" / "server" / "resources" / "tools" / "role_setup"
_OUTER_YAML = _SRC_ROOT / "role_setup.yaml"
_INNER_YAML = _SRC_ROOT / "role_setup_skill_tool_creation.yaml"


def _yaml_bta(yaml_path=_OUTER_YAML, overrides=None):
    import agent_foundation.common.configs.registered_targets  # noqa: F401
    from python_utils.config_utils import load_config, instantiate

    cfg = load_config(str(yaml_path), overrides=overrides or {})
    return instantiate(cfg)


# ---------------------------------------------------------------------------
# Core isolation tests — the actual bug fix verification
# ---------------------------------------------------------------------------


class TestAggregatorIsolation:
    """Each inner BTA from the factory must have its own aggregator."""

    def setup_method(self):
        self.bta = _yaml_bta()
        self.factory = self.bta.worker_factory["skill_tool_creation"]

    def test_aggregator_instances_are_distinct(self):
        w1 = self.factory()
        w2 = self.factory()
        assert id(w1.aggregator_inferencer) != id(w2.aggregator_inferencer)

    def test_aggregator_instances_are_distinct_three_workers(self):
        workers = [self.factory() for _ in range(3)]
        agg_ids = [id(w.aggregator_inferencer) for w in workers]
        assert len(set(agg_ids)) == 3

    def test_breakdown_instances_are_distinct(self):
        w1 = self.factory()
        w2 = self.factory()
        assert id(w1.breakdown_inferencer) != id(w2.breakdown_inferencer)

    def test_workspace_instances_are_distinct(self):
        w1 = self.factory()
        w2 = self.factory()
        assert id(w1._workspace) != id(w2._workspace)

    def test_worker_factory_instances_are_distinct(self):
        w1 = self.factory()
        w2 = self.factory()
        assert id(w1.worker_factory) != id(w2.worker_factory)


class TestAggregatorWorkspaceSafety:
    """Simulates the concurrent workspace assignment that caused the bug."""

    def setup_method(self):
        self.bta = _yaml_bta()
        self.factory = self.bta.worker_factory["skill_tool_creation"]

    def test_workspace_assignment_does_not_cross_contaminate(self):
        from agent_foundation.common.inferencers.inferencer_workspace import (
            InferencerWorkspace,
        )
        w1 = self.factory()
        w2 = self.factory()

        ws1 = InferencerWorkspace(root="/tmp/test_worker_1")
        ws2 = InferencerWorkspace(root="/tmp/test_worker_2")
        w1.aggregator_inferencer._workspace = ws1
        w2.aggregator_inferencer._workspace = ws2

        assert w1.aggregator_inferencer._workspace.root == ws1.root
        assert w2.aggregator_inferencer._workspace.root == ws2.root

    def test_aggregator_type_is_correct(self):
        from agent_foundation.common.inferencers.agentic_inferencers.external.rovodev.rovodev_cli_inferencer import (
            RovoDevCliInferencer,
        )
        w = self.factory()
        assert isinstance(w.aggregator_inferencer, RovoDevCliInferencer)


# ---------------------------------------------------------------------------
# Inner BTA standalone: same guarantee when loaded directly
# ---------------------------------------------------------------------------


class TestInnerYamlAggregatorIsolation:
    """Load inner BTA yaml directly and verify factory isolation."""

    def test_inner_yaml_worker_factories_are_partials(self):
        import functools
        inner = _yaml_bta(_INNER_YAML)
        for key in ("skill_tool_creation_research", "skill_tool_creation_investigation"):
            assert isinstance(inner.worker_factory[key], functools.partial), (
                f"inner worker_factory[{key!r}] should be functools.partial "
                f"(no _import_ used), got {type(inner.worker_factory[key])}"
            )

    def test_inner_yaml_aggregator_is_not_shared_across_instances(self):
        i1 = _yaml_bta(_INNER_YAML)
        i2 = _yaml_bta(_INNER_YAML)
        assert id(i1.aggregator_inferencer) != id(i2.aggregator_inferencer)


# ---------------------------------------------------------------------------
# Dot-notation overrides survive _ImportFactory
# ---------------------------------------------------------------------------


class TestOverridesThroughFactory:
    def test_inner_max_breakdown_override(self):
        bta = _yaml_bta(overrides={
            "worker_factory.skill_tool_creation.max_breakdown": 2,
        })
        inner = bta.worker_factory["skill_tool_creation"]()
        assert inner.max_breakdown == 2

    def test_inner_override_preserved_across_calls(self):
        bta = _yaml_bta(overrides={
            "worker_factory.skill_tool_creation.max_breakdown": 3,
        })
        factory = bta.worker_factory["skill_tool_creation"]
        w1 = factory()
        w2 = factory()
        assert w1.max_breakdown == 3
        assert w2.max_breakdown == 3
        assert id(w1.aggregator_inferencer) != id(w2.aggregator_inferencer)
