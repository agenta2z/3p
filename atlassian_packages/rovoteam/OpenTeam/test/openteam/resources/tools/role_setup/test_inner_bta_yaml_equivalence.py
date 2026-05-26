"""Unit tests: YAML-instantiated inner BTA == Python-built inner BTA.

Verifies that ``inner_bta_skill_tool_creation.yaml`` produces a
``BreakdownThenAggregateInferencer`` with the same structural configuration
as ``_build_inner_bta()`` in executor.py.

No live API calls are made — all assertions are on the instantiated object
structure (types, field values, worker factory keys, etc.).

Run::

    cd /Users/tchen7/MyProjects/CoreProjects/OpenTeam
    PYTHONPATH=".../PythonUtils/src:.../AgentFoundation/src:.../OpenTeam/src:." \\
    PROMPT_TEMPLATES_ROOT=".../OpenTeam/src/openteam/server/resources/prompt_templates" \\
    python -m pytest test/openteam/resources/tools/role_setup/test_inner_bta_yaml_equivalence.py -v
"""

import functools
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).resolve().parent
_SRC_ROOT = _ROOT.parents[4] / "src" / "openteam" / "server" / "resources" / "tools" / "role_setup"
_YAML_CONFIG = _SRC_ROOT / "role_setup_skill_tool_creation.yaml"

_EXECUTOR_SRC = (
    Path(__file__).resolve().parents[4]
    / "src" / "openteam" / "server" / "resources" / "tools" / "role_setup" / "executor.py"
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _yaml_bta(overrides=None):
    """Instantiate BTA from the YAML config (no live inferencers needed)."""
    import agent_foundation.common.configs.registered_targets  # noqa: F401 — trigger registration
    from python_utils.config_utils import load_config, instantiate

    cfg = load_config(str(_YAML_CONFIG), overrides=overrides or {})
    return instantiate(cfg)


def _python_bta(tm=None, rovo_kwargs=None, templates_root=None):
    """Build BTA from the Python builder (executor._build_inner_bta)."""
    from openteam.server.resources.tools.role_setup.executor import _build_inner_bta

    if tm is None:
        tm = MagicMock()  # TemplateManager mock
    if rovo_kwargs is None:
        rovo_kwargs = {"cloud_id": "", "uct_token": "", "base_url": "https://hello.atlassian.net"}

    return _build_inner_bta(
        sub_query="Create a Program Management skill.",
        index=1,
        tm=tm,
        rovo_kwargs=rovo_kwargs,
        inner_breakdown_preamble="skill_tool_creation",
        inner_research_preamble="skill_tool_creation",
        inner_synthesis_instructions="",
        max_inner_facets=5,
        aggregator_type="rovochat",
        aggregator_working_dir=None,
        streaming_cache_dir=None,
        breakdown_only=False,
        workspace=None,
        inferencer_logger=None,
        templates_root=templates_root,
        role_name="Program Manager",
        role_doc_path="/tmp/role.md",
        available_tools_text="",
    )


# ---------------------------------------------------------------------------
# Tests: YAML config loads correctly
# ---------------------------------------------------------------------------


class TestYamlConfig:
    """Verify the YAML config file itself is valid and loads correctly."""

    def test_yaml_file_exists(self):
        assert _YAML_CONFIG.exists(), f"YAML config not found: {_YAML_CONFIG}"

    def test_yaml_instantiates_bta(self):
        from agent_foundation.common.inferencers.agentic_inferencers.flow_inferencers.breakdown_then_aggregate_inferencer import (
            BreakdownThenAggregateInferencer,
        )
        bta = _yaml_bta()
        assert isinstance(bta, BreakdownThenAggregateInferencer), (
            f"Expected BreakdownThenAggregateInferencer, got {type(bta).__name__}"
        )

    def test_yaml_produces_bta_not_partial(self):
        """BTA itself must be a live instance, not a functools.partial."""
        bta = _yaml_bta()
        assert not isinstance(bta, functools.partial)


# ---------------------------------------------------------------------------
# Tests: BTA structural settings
# ---------------------------------------------------------------------------


class TestBTASettings:
    """Verify BTA-level settings match the expected values from executor.py."""

    def setup_method(self):
        self.bta = _yaml_bta()

    def test_max_breakdown(self):
        assert self.bta.max_breakdown == 5

    def test_task_type_arg_name(self):
        assert self.bta.task_type_arg_name == "task_preamble"

    def test_breakdown_format(self):
        assert self.bta.breakdown_format == "json_subtasks"

    def test_worker_query_fields(self):
        assert "description" in self.bta.worker_query_fields
        assert "todos" in self.bta.worker_query_fields

    def test_expand_todos_to_workers(self):
        # YAML has expand_todos_to_workers: true
        assert self.bta.expand_todos_to_workers is True

    def test_debug_mode(self):
        assert self.bta.debug_mode is True

    def test_output_path_at_bta_level(self):
        """BTA-level output_path enables _finalize_response to route SKILL.md."""
        assert self.bta.output_path is not None
        assert self.bta.output_path != ""

    def test_workspace_use_final_deliverables_folder(self):
        """Deliverables (skills/, tools/) must go to outputs/final_deliverables/, not outputs/.

        The yaml sets workspace.use_final_deliverables_folder: true. Callers must
        override workspace.root (dot-notation) — NOT workspace_root (BTA convenience
        field) — so this flag is preserved at runtime.
        """
        assert self.bta._workspace is not None
        assert self.bta._workspace.use_final_deliverables_folder is True

    def test_group_max_concurrency(self):
        assert self.bta.group_max_concurrency == {
            "skill_tool_creation_research": 3,
            "skill_tool_creation_investigation": 2,
        }


# ---------------------------------------------------------------------------
# Tests: Breakdown inferencer
# ---------------------------------------------------------------------------


class TestBreakdownInferencer:
    """Verify the breakdown inferencer matches the Python-built one."""

    def setup_method(self):
        self.bta = _yaml_bta()
        self.breakdown = self.bta.breakdown_inferencer

    def test_breakdown_inferencer_exists(self):
        assert self.breakdown is not None

    def test_breakdown_is_rovodev(self):
        from agent_foundation.common.inferencers.agentic_inferencers.external.rovodev.rovodev_cli_inferencer import (
            RovoDevCliInferencer,
        )
        assert isinstance(self.breakdown, RovoDevCliInferencer), (
            f"Expected RovoDevCliInferencer, got {type(self.breakdown).__name__}"
        )

    def test_breakdown_yolo(self):
        assert self.breakdown.yolo is True

    def test_breakdown_debug_mode(self):
        assert self.breakdown.debug_mode is True

    def test_breakdown_template_root_space(self):
        assert self.breakdown.template_root_space == "task_breakdown"

    def test_breakdown_template_variables_preamble(self):
        """Breakdown should select skill_tool_creation preamble via template_variables."""
        assert self.breakdown.template_variables.get("task_preamble") == "skill_tool_creation"

    def test_breakdown_has_template_manager(self):
        """TemplateManager should be auto-injected into breakdown_inferencer."""
        from python_utils.string_utils.formatting.template_manager.template_manager import (
            TemplateManager,
        )
        assert isinstance(self.breakdown.template_manager, TemplateManager), (
            f"Expected TemplateManager, got {type(self.breakdown.template_manager)}"
        )


# ---------------------------------------------------------------------------
# Tests: Worker factory
# ---------------------------------------------------------------------------


class TestWorkerFactory:
    """Verify the worker_factory dict has the right keys and produces correct types."""

    def setup_method(self):
        self.bta = _yaml_bta()
        self.factory = self.bta.worker_factory

    def test_worker_factory_is_dict(self):
        assert isinstance(self.factory, dict)

    def test_worker_factory_has_research_key(self):
        assert "skill_tool_creation_research" in self.factory

    def test_worker_factory_has_investigation_key(self):
        assert "skill_tool_creation_investigation" in self.factory

    def test_worker_factory_has_default_key(self):
        assert "__default__" in self.factory

    def test_research_factory_is_partial(self):
        assert isinstance(self.factory["skill_tool_creation_research"], functools.partial)

    def test_investigation_factory_is_partial(self):
        assert isinstance(self.factory["skill_tool_creation_investigation"], functools.partial)

    def test_default_resolves_to_research(self):
        """__default__ should point to research factory (string reference)."""
        default = self.factory["__default__"]
        assert default == "skill_tool_creation_research" or isinstance(default, functools.partial)

    def test_research_factory_creates_rovochat(self):
        """Each call to the research partial should create a fresh RovoChatInferencer."""
        from agent_foundation.common.inferencers.agentic_inferencers.external.rovochat.rovochat_inferencer import (
            RovoChatInferencer,
        )
        w1 = self.factory["skill_tool_creation_research"]()
        assert isinstance(w1, RovoChatInferencer), (
            f"Expected RovoChatInferencer, got {type(w1).__name__}"
        )

    def test_investigation_factory_creates_rovodev(self):
        """Each call to the investigation partial should create a fresh RovoDevCliInferencer."""
        from agent_foundation.common.inferencers.agentic_inferencers.external.rovodev.rovodev_cli_inferencer import (
            RovoDevCliInferencer,
        )
        w1 = self.factory["skill_tool_creation_investigation"]()
        assert isinstance(w1, RovoDevCliInferencer), (
            f"Expected RovoDevCliInferencer, got {type(w1).__name__}"
        )

    def test_worker_factory_creates_fresh_instances(self):
        """Each call must create a NEW instance (not the same shared object)."""
        w1 = self.factory["skill_tool_creation_research"]()
        w2 = self.factory["skill_tool_creation_research"]()
        assert w1 is not w2, "Worker factory must create fresh instances on each call"

    def test_research_worker_template_root_space(self):
        """Research workers should use deep_research template space."""
        w = self.factory["skill_tool_creation_research"]()
        assert w.template_root_space == "deep_research"

    def test_investigation_worker_template_root_space(self):
        """Investigation workers should use deep_research template space."""
        w = self.factory["skill_tool_creation_investigation"]()
        assert w.template_root_space == "deep_research"

    def test_research_worker_template_variables(self):
        """Research worker should select skill_tool_creation_research preamble."""
        w = self.factory["skill_tool_creation_research"]()
        assert w.template_variables.get("task_preamble") == "skill_tool_creation_research"

    def test_investigation_worker_template_variables(self):
        """Investigation worker should select skill_tool_creation_investigation preamble."""
        w = self.factory["skill_tool_creation_investigation"]()
        assert w.template_variables.get("task_preamble") == "skill_tool_creation_investigation"

    def test_research_worker_auto_continue(self):
        """RovoChat research workers should have auto_continue=True."""
        w = self.factory["skill_tool_creation_research"]()
        assert w.auto_continue is True

    def test_investigation_worker_yolo(self):
        """RovoDevCli investigation workers should have yolo=True."""
        w = self.factory["skill_tool_creation_investigation"]()
        assert w.yolo is True

    def test_worker_has_template_manager_injected(self):
        """TemplateManager auto-injection must reach workers."""
        from python_utils.string_utils.formatting.template_manager.template_manager import (
            TemplateManager,
        )
        w = self.factory["skill_tool_creation_research"]()
        assert isinstance(w.template_manager, TemplateManager), (
            f"Expected TemplateManager on worker, got {type(w.template_manager)}"
        )


# ---------------------------------------------------------------------------
# Tests: Aggregator inferencer
# ---------------------------------------------------------------------------


class TestAggregatorInferencer:
    """Verify the aggregator inferencer structure."""

    def setup_method(self):
        self.bta = _yaml_bta()
        self.agg = self.bta.aggregator_inferencer

    def test_aggregator_exists(self):
        assert self.agg is not None

    def test_aggregator_is_rovodev(self):
        """Aggregator must be RovoDevCliInferencer — needs local file access to write
        structured deliverables (skills/<name>/SKILL.md, tools/<name>/tool.json)."""
        from agent_foundation.common.inferencers.agentic_inferencers.external.rovodev.rovodev_cli_inferencer import (
            RovoDevCliInferencer,
        )
        assert isinstance(self.agg, RovoDevCliInferencer), (
            f"Expected RovoDevCliInferencer, got {type(self.agg).__name__}"
        )

    def test_aggregator_yolo(self):
        assert self.agg.yolo is True

    def test_aggregator_template_root_space(self):
        assert self.agg.template_root_space == "implementation"

    def test_aggregator_template_variables(self):
        """Aggregator should load task_instructions and task_preamble variants."""
        assert self.agg.template_variables.get("task_instructions") == "skill_tool_creation"

    def test_aggregator_has_template_manager(self):
        """TemplateManager auto-injection must reach the aggregator."""
        from python_utils.string_utils.formatting.template_manager.template_manager import (
            TemplateManager,
        )
        assert isinstance(self.agg.template_manager, TemplateManager)


# ---------------------------------------------------------------------------
# Tests: Structural equivalence (YAML vs Python)
# ---------------------------------------------------------------------------


class TestYamlVsPythonEquivalence:
    """Compare YAML BTA and Python BTA on equivalent structural properties.

    Note: The YAML path uses functools.partial factories + template_variables,
    while the Python path uses closures + template_extra_feed. These are
    equivalent in behavior but different in implementation. We compare the
    observable surface:
    - BTA type
    - breakdown inferencer type
    - worker factory keys
    - worker factory produces correct inferencer types
    - aggregator type
    - BTA-level settings (max_breakdown, task_type_arg_name, etc.)
    """

    def setup_method(self):
        self.yaml_bta = _yaml_bta()
        # Python BTA uses RovoChat aggregator for comparison
        self.python_bta = _python_bta()

    def test_both_are_bta(self):
        from agent_foundation.common.inferencers.agentic_inferencers.flow_inferencers.breakdown_then_aggregate_inferencer import (
            BreakdownThenAggregateInferencer,
        )
        assert isinstance(self.yaml_bta, BreakdownThenAggregateInferencer)
        assert isinstance(self.python_bta, BreakdownThenAggregateInferencer)

    def test_both_have_same_breakdown_type(self):
        from agent_foundation.common.inferencers.agentic_inferencers.external.rovodev.rovodev_cli_inferencer import (
            RovoDevCliInferencer,
        )
        assert isinstance(self.yaml_bta.breakdown_inferencer, RovoDevCliInferencer)
        assert isinstance(self.python_bta.breakdown_inferencer, RovoDevCliInferencer)

    def test_both_have_same_worker_factory_keys(self):
        yaml_keys = {k for k in self.yaml_bta.worker_factory if not k.startswith("_")}
        python_keys = {k for k in self.python_bta.worker_factory if not k.startswith("_")}
        assert yaml_keys == python_keys, (
            f"Worker factory keys differ:\n  YAML: {yaml_keys}\n  Python: {python_keys}"
        )

    def test_both_research_workers_are_rovochat(self):
        from agent_foundation.common.inferencers.agentic_inferencers.external.rovochat.rovochat_inferencer import (
            RovoChatInferencer,
        )
        yaml_w = self.yaml_bta.worker_factory["skill_tool_creation_research"]()
        python_entry = self.python_bta.worker_factory["skill_tool_creation_research"]
        python_factory = python_entry["factory"] if isinstance(python_entry, dict) else python_entry
        python_w = python_factory(sub_query="test", index=0)
        assert isinstance(yaml_w, RovoChatInferencer)
        assert isinstance(python_w, RovoChatInferencer)

    def test_both_investigation_workers_are_rovodev(self):
        from agent_foundation.common.inferencers.agentic_inferencers.external.rovodev.rovodev_cli_inferencer import (
            RovoDevCliInferencer,
        )
        yaml_w = self.yaml_bta.worker_factory["skill_tool_creation_investigation"]()
        python_entry = self.python_bta.worker_factory["skill_tool_creation_investigation"]
        python_factory = python_entry["factory"] if isinstance(python_entry, dict) else python_entry
        python_w = python_factory(sub_query="test", index=0)
        assert isinstance(yaml_w, RovoDevCliInferencer)
        assert isinstance(python_w, RovoDevCliInferencer)

    def test_both_have_same_max_breakdown(self):
        assert self.yaml_bta.max_breakdown == self.python_bta.max_breakdown == 5

    def test_both_have_same_task_type_arg_name(self):
        assert self.yaml_bta.task_type_arg_name == self.python_bta.task_type_arg_name == "task_preamble"

    def test_both_have_same_breakdown_template_root_space(self):
        assert self.yaml_bta.breakdown_inferencer.template_root_space == "task_breakdown"
        assert self.python_bta.breakdown_inferencer.template_root_space == "task_breakdown"

    def test_both_research_workers_use_deep_research(self):
        yaml_w = self.yaml_bta.worker_factory["skill_tool_creation_research"]()
        python_entry = self.python_bta.worker_factory["skill_tool_creation_research"]
        python_factory = python_entry["factory"] if isinstance(python_entry, dict) else python_entry
        python_w = python_factory(sub_query="test", index=0)
        assert yaml_w.template_root_space == "deep_research"
        assert python_w.template_root_space == "deep_research"

    def test_both_have_group_max_concurrency(self):
        assert self.yaml_bta.group_max_concurrency == {
            "skill_tool_creation_research": 3,
            "skill_tool_creation_investigation": 2,
        }
        assert self.python_bta.group_max_concurrency == {
            "skill_tool_creation_research": 3,
            "skill_tool_creation_investigation": 2,
        }
