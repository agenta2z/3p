"""Unit tests: YAML-instantiated outer BTA (role_setup.yaml) structural verification.

Verifies that ``role_setup.yaml`` produces a correctly composed
``BreakdownThenAggregateInferencer`` with _import_-loaded inner BTA as worker factory.

No live API calls — all assertions are on the instantiated object structure.

Run::

    cd /Users/tchen7/MyProjects/CoreProjects/OpenTeam
    PYTHONPATH=".../PythonUtils/src:.../AgentFoundation/src:.../OpenTeam/src:." \\
    python -m pytest test/openteam/resources/tools/role_setup/test_outer_bta_yaml_equivalence.py -v
"""

import functools
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent
_SRC_ROOT = _ROOT.parents[4] / "src" / "openteam" / "server" / "resources" / "tools" / "role_setup"
_YAML_CONFIG = _SRC_ROOT / "role_setup.yaml"


def _yaml_bta(overrides=None):
    import agent_foundation.common.configs.registered_targets  # noqa: F401
    from python_utils.config_utils import load_config, instantiate

    cfg = load_config(str(_YAML_CONFIG), overrides=overrides or {})
    return instantiate(cfg)


class TestOuterYamlConfig:
    def test_yaml_file_exists(self):
        assert _YAML_CONFIG.exists()

    def test_inner_yaml_file_exists(self):
        inner = _SRC_ROOT / "role_setup_skill_tool_creation.yaml"
        assert inner.exists()

    def test_instantiates_bta(self):
        from agent_foundation.common.inferencers.agentic_inferencers.flow_inferencers.breakdown_then_aggregate_inferencer import (
            BreakdownThenAggregateInferencer,
        )
        bta = _yaml_bta()
        assert isinstance(bta, BreakdownThenAggregateInferencer)

    def test_not_partial(self):
        bta = _yaml_bta()
        assert not isinstance(bta, functools.partial)


class TestOuterBreakdown:
    def setup_method(self):
        self.bta = _yaml_bta()
        self.breakdown = self.bta.breakdown_inferencer

    def test_breakdown_is_rovodev(self):
        from agent_foundation.common.inferencers.agentic_inferencers.external.rovodev.rovodev_cli_inferencer import (
            RovoDevCliInferencer,
        )
        assert isinstance(self.breakdown, RovoDevCliInferencer)

    def test_breakdown_template_root_space(self):
        assert self.breakdown.template_root_space == "task_breakdown"

    def test_breakdown_preamble(self):
        assert self.breakdown.template_variables.get("task_preamble") == "role_setup"

    def test_breakdown_has_template_manager(self):
        from python_utils.string_utils.formatting.template_manager.template_manager import (
            TemplateManager,
        )
        assert isinstance(self.breakdown.template_manager, TemplateManager)


class TestOuterSettings:
    def setup_method(self):
        self.bta = _yaml_bta()

    def test_max_breakdown(self):
        assert self.bta.max_breakdown == 8

    def test_breakdown_format(self):
        assert self.bta.breakdown_format == "json_subtasks"

    def test_output_path(self):
        assert self.bta.output_path == "role_setup_report.md"

    def test_name(self):
        assert self.bta.name == "outer_bta"

    def test_outer_workspace_uses_final_deliverables(self):
        # Outer BTA uses final_deliverables/ — deliverables (skills, tools, association JSON)
        # go to outputs/final_deliverables/; records (reports) stay in outputs/
        assert self.bta._workspace is not None
        assert self.bta._workspace.use_final_deliverables_folder is True


class TestOuterWorkerFactory:
    def setup_method(self):
        self.bta = _yaml_bta()
        self.factory = self.bta.worker_factory

    def test_is_dict(self):
        assert isinstance(self.factory, dict)

    def test_has_skill_tool_creation_key(self):
        assert "skill_tool_creation" in self.factory

    def test_has_default_key(self):
        assert "__default__" in self.factory

    def test_default_points_to_skill_tool_creation(self):
        assert self.factory["__default__"] == "skill_tool_creation"

    def test_factory_entry_is_import_factory(self):
        from python_utils.config_utils._instantiate import _ImportFactory
        # _import_: in yaml produces _ImportFactory (lazy, creates fresh instance per call)
        # Previously was functools.partial (shared aggregator_inferencer — concurrency bug)
        assert isinstance(self.factory["skill_tool_creation"], _ImportFactory)

    def test_partial_creates_inner_bta(self):
        from agent_foundation.common.inferencers.agentic_inferencers.flow_inferencers.breakdown_then_aggregate_inferencer import (
            BreakdownThenAggregateInferencer,
        )
        inner = self.factory["skill_tool_creation"]()
        assert isinstance(inner, BreakdownThenAggregateInferencer)

    def test_partial_creates_fresh_instances(self):
        inner1 = self.factory["skill_tool_creation"]()
        inner2 = self.factory["skill_tool_creation"]()
        assert inner1 is not inner2

    def test_inner_bta_has_correct_breakdown(self):
        from agent_foundation.common.inferencers.agentic_inferencers.external.rovodev.rovodev_cli_inferencer import (
            RovoDevCliInferencer,
        )
        inner = self.factory["skill_tool_creation"]()
        assert isinstance(inner.breakdown_inferencer, RovoDevCliInferencer)

    def test_inner_bta_has_heterogeneous_workers(self):
        inner = self.factory["skill_tool_creation"]()
        assert isinstance(inner.worker_factory, dict)
        assert "skill_tool_creation_research" in inner.worker_factory
        assert "skill_tool_creation_investigation" in inner.worker_factory

    def test_inner_bta_workspace_has_final_deliverables(self):
        inner = self.factory["skill_tool_creation"]()
        assert inner._workspace is not None
        assert inner._workspace.use_final_deliverables_folder is True

    def test_inner_bta_max_breakdown(self):
        inner = self.factory["skill_tool_creation"]()
        assert inner.max_breakdown == 5

    def test_inner_bta_has_template_manager(self):
        from python_utils.string_utils.formatting.template_manager.template_manager import (
            TemplateManager,
        )
        inner = self.factory["skill_tool_creation"]()
        assert isinstance(inner.breakdown_inferencer.template_manager, TemplateManager)


class TestAssociateWorkerFactory:
    """Verify the skill_tool_association worker factory entry."""

    def setup_method(self):
        self.bta = _yaml_bta()
        self.factory = self.bta.worker_factory

    def test_has_skill_tool_association_key(self):
        assert "skill_tool_association" in self.factory

    def test_associate_is_partial(self):
        assert isinstance(self.factory["skill_tool_association"], functools.partial)

    def test_associate_creates_rovodev(self):
        from agent_foundation.common.inferencers.agentic_inferencers.external.rovodev.rovodev_cli_inferencer import (
            RovoDevCliInferencer,
        )
        worker = self.factory["skill_tool_association"]()
        assert isinstance(worker, RovoDevCliInferencer)

    def test_associate_is_not_bta(self):
        from agent_foundation.common.inferencers.agentic_inferencers.flow_inferencers.breakdown_then_aggregate_inferencer import (
            BreakdownThenAggregateInferencer,
        )
        worker = self.factory["skill_tool_association"]()
        assert not isinstance(worker, BreakdownThenAggregateInferencer)

    def test_associate_template_root_space(self):
        worker = self.factory["skill_tool_association"]()
        assert worker.template_root_space == "implementation"

    def test_associate_template_variables(self):
        worker = self.factory["skill_tool_association"]()
        assert worker.template_variables.get("task_instructions") == "skill_tool_association"

    def test_associate_creates_fresh_instances(self):
        w1 = self.factory["skill_tool_association"]()
        w2 = self.factory["skill_tool_association"]()
        assert w1 is not w2


class TestHeterogeneousDispatch:
    """Verify task_type_arg_name and promote_worker_deliverables settings."""

    def setup_method(self):
        self.bta = _yaml_bta()

    def test_task_type_arg_name(self):
        assert self.bta.task_type_arg_name == "task_preamble"

    def test_promote_worker_deliverables(self):
        assert self.bta.promote_worker_deliverables is True


class TestOuterAggregator:
    def setup_method(self):
        self.bta = _yaml_bta()
        self.agg = self.bta.aggregator_inferencer

    def test_aggregator_is_rovodev(self):
        from agent_foundation.common.inferencers.agentic_inferencers.external.rovodev.rovodev_cli_inferencer import (
            RovoDevCliInferencer,
        )
        assert isinstance(self.agg, RovoDevCliInferencer)

    def test_aggregator_template_root_space(self):
        assert self.agg.template_root_space == "implementation"

    def test_aggregator_task_instructions(self):
        assert self.agg.template_variables.get("task_instructions") == "role_setup_report"


class TestDotNotationOverrides:
    def test_override_max_breakdown(self):
        bta = _yaml_bta(overrides={"max_breakdown": 3})
        assert bta.max_breakdown == 3

    def test_override_inner_max_breakdown(self):
        bta = _yaml_bta(overrides={
            "worker_factory.skill_tool_creation.max_breakdown": 2
        })
        inner = bta.worker_factory["skill_tool_creation"]()
        assert inner.max_breakdown == 2
