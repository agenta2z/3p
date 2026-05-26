"""Preflight: LazyConfigFactory isolation for role_setup's nested-BTA topology.

role_setup uses a UNIQUE pattern: the outer BTA's ``worker_factory``
dict has a ``skill_tool_creation`` slot that imports an entire INNER
BTA YAML (``role_setup_skill_tool_creation.yaml``). Each call to this
factory must produce a fully fresh inner-BTA tree (own breakdown,
aggregator, workspace, worker_factory) — otherwise concurrent inner
workers would race to overwrite each other's state.

Regression test for the LazyConfigFactory fix (Fix #9 from
mfdual_workspace_layout_anomalies_fix_plan.md) — applied at the
factory layer that wraps the ``_import_`` directive.

Runtime: ~5s, no LLM cost.

Ported from test_import_factory_isolation.py.
"""

from __future__ import annotations

import pytest

from ._common import OUTER_YAML_PATH, set_template_root_env


def _yaml_bta(tmp_path, monkeypatch, overrides=None):
    set_template_root_env(monkeypatch)
    import agent_foundation.common.configs.registered_targets  # noqa: F401
    from python_utils.config_utils import load_config, instantiate

    base_overrides = {"_params": {"workspace_root": str(tmp_path)}}
    if overrides:
        base_overrides.update(overrides)
    cfg = load_config(str(OUTER_YAML_PATH), overrides=base_overrides)
    return instantiate(cfg)


# ---------------------------------------------------------------------------
# Core isolation tests — the actual bug fix verification
# ---------------------------------------------------------------------------


class TestAggregatorIsolation:
    """Each inner BTA produced by the factory must own a distinct aggregator."""

    @pytest.fixture
    def factory(self, tmp_path, monkeypatch):
        bta = _yaml_bta(tmp_path, monkeypatch)
        return bta.worker_factory["skill_tool_creation"]

    def test_aggregator_instances_are_distinct_two_workers(self, factory):
        w1 = factory()
        w2 = factory()
        assert id(w1.aggregator_inferencer) != id(w2.aggregator_inferencer), (
            "Factory reused the same aggregator across two calls — "
            "indicates LazyConfigFactory regression"
        )

    def test_aggregator_instances_are_distinct_three_workers(self, factory):
        workers = [factory() for _ in range(3)]
        agg_ids = [id(w.aggregator_inferencer) for w in workers]
        assert len(set(agg_ids)) == 3, (
            f"Expected 3 distinct aggregators, got {len(set(agg_ids))} unique "
            f"out of 3 calls (ids={agg_ids})"
        )

    def test_breakdown_instances_are_distinct(self, factory):
        w1 = factory()
        w2 = factory()
        assert id(w1.breakdown_inferencer) != id(w2.breakdown_inferencer)

    def test_workspace_instances_are_distinct(self, factory):
        w1 = factory()
        w2 = factory()
        assert id(w1._workspace) != id(w2._workspace)

    def test_worker_factory_instances_are_distinct(self, factory):
        w1 = factory()
        w2 = factory()
        assert id(w1.worker_factory) != id(w2.worker_factory)


class TestAggregatorWorkspaceSafety:
    """Simulates the concurrent workspace assignment that caused the bug."""

    @pytest.fixture
    def factory(self, tmp_path, monkeypatch):
        bta = _yaml_bta(tmp_path, monkeypatch)
        return bta.worker_factory["skill_tool_creation"]

    def test_workspace_assignment_does_not_cross_contaminate(self, factory):
        from agent_foundation.common.inferencers.inferencer_workspace import (
            InferencerWorkspace,
        )

        w1 = factory()
        w2 = factory()

        ws1 = InferencerWorkspace(root="/tmp/test_worker_1")
        ws2 = InferencerWorkspace(root="/tmp/test_worker_2")
        w1.aggregator_inferencer._workspace = ws1
        w2.aggregator_inferencer._workspace = ws2

        assert w1.aggregator_inferencer._workspace.root == ws1.root, (
            "Worker 1 aggregator workspace was contaminated by worker 2"
        )
        assert w2.aggregator_inferencer._workspace.root == ws2.root, (
            "Worker 2 aggregator workspace was contaminated by worker 1"
        )

    def test_aggregator_type_is_correct(self, factory):
        from agent_foundation.common.inferencers.agentic_inferencers.external.rovodev.rovodev_cli_inferencer import (
            RovoDevCliInferencer,
        )

        w = factory()
        assert isinstance(w.aggregator_inferencer, RovoDevCliInferencer)
