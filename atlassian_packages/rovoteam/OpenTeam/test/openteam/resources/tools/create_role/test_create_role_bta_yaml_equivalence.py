"""Equivalence test: YAML-driven BTA vs hardcoded build_create_role_inferencer.

Verifies the YAML config produces the same BTA object graph as the
hardcoded builder — same inferencer types, same template spaces, same
structure. No auth or LLM calls needed.

Usage::

    PROMPT_TEMPLATES_ROOT=.../src/openteam/server/resources \
    python -m pytest test/openteam/resources/tools/create_role/test_create_role_bta_yaml_equivalence.py -v
"""

import functools
import os
import sys
from pathlib import Path

import pytest

# Ensure PROMPT_TEMPLATES_ROOT is set for TemplateManager resolution
_REPO_ROOT = Path(__file__).resolve().parents[4]
_RESOURCES = _REPO_ROOT / "src" / "openteam" / "server" / "resources"
if "PROMPT_TEMPLATES_ROOT" not in os.environ:
    os.environ["PROMPT_TEMPLATES_ROOT"] = str(_RESOURCES)

# Add source paths
for _sub in ["AgentFoundation/src", "PythonUtils/src", "OpenTeam/src"]:
    _p = str(_REPO_ROOT.parent / _sub)
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

import agent_foundation.common.configs.registered_targets  # noqa: F401
from python_utils.config_utils import load_config, instantiate


_YAML_PATH = str(
    Path(__file__).resolve().parents[5]
    / "src" / "openteam" / "server" / "resources" / "tools" / "create_role" / "create_role_bta.yaml"
)


@pytest.fixture
def yaml_bta():
    """Build BTA from YAML config."""
    cfg = load_config(_YAML_PATH)
    return instantiate(cfg)


@pytest.fixture
def hardcoded_bta():
    """Build BTA from hardcoded builder (needs auth kwargs, use empty)."""
    from openteam.server.resources.tools.create_role.executor import (
        build_create_role_inferencer,
    )
    # Use aggregator_type="rovodev" to match the YAML config which uses RovoDevCLI
    # for aggregation (RovoChat cannot write local files, so the synthesized
    # document was lost — RovoDevCLI writes files correctly via --output-file)
    bta = build_create_role_inferencer(aggregator_type="rovodev")
    return bta


class TestBTAStructure:
    def test_bta_type(self, yaml_bta, hardcoded_bta):
        assert type(yaml_bta).__name__ == type(hardcoded_bta).__name__

    def test_breakdown_inferencer_type(self, yaml_bta, hardcoded_bta):
        assert (type(yaml_bta.breakdown_inferencer).__name__
                == type(hardcoded_bta.breakdown_inferencer).__name__)

    def test_breakdown_template_space(self, yaml_bta, hardcoded_bta):
        assert (yaml_bta.breakdown_inferencer.template_root_space
                == hardcoded_bta.breakdown_inferencer.template_root_space)

    def test_max_breakdown(self, yaml_bta, hardcoded_bta):
        assert yaml_bta.max_breakdown == hardcoded_bta.max_breakdown

    def test_aggregator_type(self, yaml_bta, hardcoded_bta):
        assert (type(yaml_bta.aggregator_inferencer).__name__
                == type(hardcoded_bta.aggregator_inferencer).__name__)


class TestWorkerFactory:
    def test_creates_correct_type(self, yaml_bta, hardcoded_bta):
        yaml_worker = yaml_bta.worker_factory()
        hardcoded_worker = hardcoded_bta.worker_factory(
            sub_query="test query", index=0
        )
        assert type(yaml_worker).__name__ == type(hardcoded_worker).__name__

    def test_worker_template_space(self, yaml_bta, hardcoded_bta):
        yaml_worker = yaml_bta.worker_factory()
        hardcoded_worker = hardcoded_bta.worker_factory(
            sub_query="test query", index=0
        )
        assert yaml_worker.template_root_space == hardcoded_worker.template_root_space

    def test_creates_fresh_instances(self, yaml_bta):
        w1 = yaml_bta.worker_factory()
        w2 = yaml_bta.worker_factory()
        assert w1 is not w2

    def test_yaml_worker_is_partial(self, yaml_bta):
        assert isinstance(yaml_bta.worker_factory, functools.partial)


class TestTemplateManager:
    def test_breakdown_has_template_manager(self, yaml_bta):
        assert yaml_bta.breakdown_inferencer.template_manager is not None

    def test_worker_has_template_manager(self, yaml_bta):
        w = yaml_bta.worker_factory()
        assert w.template_manager is not None

    def test_aggregator_has_template_manager(self, yaml_bta):
        assert yaml_bta.aggregator_inferencer.template_manager is not None

    def test_template_variables_on_breakdown(self, yaml_bta):
        assert "task_preamble" in yaml_bta.breakdown_inferencer.template_variables

    def test_template_variables_on_worker(self, yaml_bta):
        w = yaml_bta.worker_factory()
        assert "task_preamble" in w.template_variables

    def test_template_variables_on_aggregator(self, yaml_bta):
        assert "task_instructions" in yaml_bta.aggregator_inferencer.template_variables
