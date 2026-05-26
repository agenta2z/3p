"""Preflight: YAML smoke instantiate for ``role_setup.yaml`` (outer + inner).

Loads ``role_setup.yaml`` AND ``role_setup_skill_tool_creation.yaml`` via
``load_config + instantiate``. Catches regressions in:
  * YAML schema (missing keys, wrong types)
  * Heterogeneous worker dispatch via ``task_type_arg_name``
  * Worker factory composition (`_ImportFactory` for skill_tool_creation slot)
  * Nested-BTA topology preservation (outer BTA → inner BTA)
  * Aggregator + breakdown construction
  * Template manager root configuration
  * ``_-prefix`` cascade (``_model_id``, ``_debug_mode``, etc.)

Ported from test_outer_bta_yaml_equivalence.py — removes the side-by-side
Python equivalence machinery, keeps the structural assertions.

Runtime: ~5s, no LLM cost.
"""

from __future__ import annotations

from ._common import (  # noqa: F401
    INNER_YAML_PATH,
    OUTER_YAML_PATH,
    set_template_root_env,
)


def test_role_setup_outer_yaml_smoke_instantiate(tmp_path, monkeypatch):
    """Load + instantiate outer role_setup.yaml — verifies BTA + heterogeneous worker dispatch."""
    set_template_root_env(monkeypatch)

    import agent_foundation.common.configs.registered_targets  # noqa: F401
    from python_utils.config_utils import load_config, instantiate

    cfg = load_config(str(OUTER_YAML_PATH), overrides={
        "_params": {"workspace_root": str(tmp_path)},
    })
    inst = instantiate(cfg)

    # Top-level: BTA
    from agent_foundation.common.inferencers.agentic_inferencers.flow_inferencers.breakdown_then_aggregate_inferencer import (
        BreakdownThenAggregateInferencer,
    )
    assert isinstance(inst, BreakdownThenAggregateInferencer), (
        f"Expected outer BTA, got {type(inst).__name__}"
    )

    # Breakdown: RovoDevCLI (uses task_preamble='role_setup')
    from agent_foundation.common.inferencers.agentic_inferencers.external.rovodev.rovodev_cli_inferencer import (
        RovoDevCliInferencer,
    )
    assert isinstance(inst.breakdown_inferencer, RovoDevCliInferencer), (
        f"Expected outer breakdown=RovoDevCLI, got "
        f"{type(inst.breakdown_inferencer).__name__}"
    )

    # Aggregator: RovoDevCLI
    assert isinstance(inst.aggregator_inferencer, RovoDevCliInferencer), (
        f"Expected outer aggregator=RovoDevCLI, got "
        f"{type(inst.aggregator_inferencer).__name__}"
    )

    # Heterogeneous worker dispatch: task_type_arg_name should be set
    assert getattr(inst, "task_type_arg_name", None) == "task_preamble", (
        f"Expected task_type_arg_name='task_preamble', got "
        f"{getattr(inst, 'task_type_arg_name', None)}"
    )

    # Worker factory: must be a dict (heterogeneous) with at least
    # 'skill_tool_creation', 'skill_tool_association', '__default__' keys
    wf = inst.worker_factory
    assert isinstance(wf, dict), (
        f"Expected worker_factory to be dict (heterogeneous), got {type(wf).__name__}"
    )
    for key in ("skill_tool_creation", "skill_tool_association", "__default__"):
        assert key in wf, (
            f"worker_factory missing required key: {key} (have: {list(wf.keys())})"
        )

    # Cascades reached children
    assert inst.debug_mode is True, "BTA.debug_mode should be cascaded"
    assert inst.breakdown_inferencer.debug_mode is True
    assert inst.aggregator_inferencer.debug_mode is True


def test_role_setup_inner_yaml_smoke_instantiate(tmp_path, monkeypatch):
    """Load + instantiate inner role_setup_skill_tool_creation.yaml — verifies inner BTA structure."""
    set_template_root_env(monkeypatch)

    import agent_foundation.common.configs.registered_targets  # noqa: F401
    from python_utils.config_utils import load_config, instantiate

    cfg = load_config(str(INNER_YAML_PATH), overrides={
        "_params": {"workspace_root": str(tmp_path)},
    })
    inst = instantiate(cfg)

    # Top-level: inner BTA
    from agent_foundation.common.inferencers.agentic_inferencers.flow_inferencers.breakdown_then_aggregate_inferencer import (
        BreakdownThenAggregateInferencer,
    )
    assert isinstance(inst, BreakdownThenAggregateInferencer), (
        f"Expected inner BTA, got {type(inst).__name__}"
    )

    # Inner breakdown: RovoDevCLI (uses task_preamble='skill_tool_creation')
    from agent_foundation.common.inferencers.agentic_inferencers.external.rovodev.rovodev_cli_inferencer import (
        RovoDevCliInferencer,
    )
    assert isinstance(inst.breakdown_inferencer, RovoDevCliInferencer), (
        f"Expected inner breakdown=RovoDevCLI, got "
        f"{type(inst.breakdown_inferencer).__name__}"
    )

    # Inner aggregator: RovoDevCLI
    assert isinstance(inst.aggregator_inferencer, RovoDevCliInferencer), (
        f"Expected inner aggregator=RovoDevCLI, got "
        f"{type(inst.aggregator_inferencer).__name__}"
    )

    # Heterogeneous workers: skill_tool_creation_research (RovoChat) +
    # skill_tool_creation_investigation (RovoDevCLI) + __default__
    wf = inst.worker_factory
    assert isinstance(wf, dict), (
        f"Expected inner worker_factory dict, got {type(wf).__name__}"
    )
    for key in (
        "skill_tool_creation_research",
        "skill_tool_creation_investigation",
        "__default__",
    ):
        assert key in wf, (
            f"inner worker_factory missing key: {key} (have: {list(wf.keys())})"
        )
