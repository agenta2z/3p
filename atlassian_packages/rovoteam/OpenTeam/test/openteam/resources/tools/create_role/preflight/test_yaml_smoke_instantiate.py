"""Preflight: YAML smoke instantiate for ``create_role_bta.yaml``.

Loads ``create_role_bta.yaml`` via ``load_config + instantiate``. Catches
regressions in:
  * YAML schema (missing keys, wrong types)
  * ``_-prefix`` cascade (``_model_id``, ``_debug_mode``, etc.)
  * ``_params`` resolution (``${_params.default_research_inferencer}``)
  * OmegaConf interpolation
  * ``_partial_`` / ``_factory`` auto-injection
  * BTA + RovoChat + RovoDevCli construction
  * Option A MI fix: RovoChat inherits TemplatedInferencerBase

Runtime: ~5s, no LLM cost.
"""

from __future__ import annotations

from ._common import (  # noqa: F401  (used inside test body)
    COREPROJECTS_ROOT,
    OPENSTARTUP_ROOT,
    YAML_PATH,
    set_template_root_env,
)


def test_create_role_yaml_smoke_instantiate(tmp_path, monkeypatch):
    """Load + instantiate create_role_bta.yaml."""
    # Configure templates root (needed by aggregator's TemplateManager)
    set_template_root_env(monkeypatch)

    # Ensure registry imports run (registers @lazy_target classes)
    import agent_foundation.common.configs.registered_targets  # noqa: F401
    from python_utils.config_utils import load_config, instantiate

    # Load YAML and instantiate (must supply workspace_root — mandatory key)
    cfg = load_config(str(YAML_PATH), overrides={
        "_params": {"workspace_root": str(tmp_path)},
    })
    inst = instantiate(cfg)

    # Verify top-level is BTA
    from agent_foundation.common.inferencers.agentic_inferencers.flow_inferencers.breakdown_then_aggregate_inferencer import (
        BreakdownThenAggregateInferencer,
    )
    assert isinstance(inst, BreakdownThenAggregateInferencer), (
        f"Expected BTA, got {type(inst).__name__}"
    )

    # Verify breakdown_inferencer is RovoChat (default for research role)
    from agent_foundation.common.inferencers.agentic_inferencers.external.rovochat.rovochat_inferencer import (
        RovoChatInferencer,
    )
    assert isinstance(inst.breakdown_inferencer, RovoChatInferencer), (
        f"Expected breakdown=RovoChat, got "
        f"{type(inst.breakdown_inferencer).__name__}"
    )

    # Verify aggregator is RovoDevCLI (default for aggregation role)
    from agent_foundation.common.inferencers.agentic_inferencers.external.rovodev.rovodev_cli_inferencer import (
        RovoDevCliInferencer,
    )
    assert isinstance(inst.aggregator_inferencer, RovoDevCliInferencer), (
        f"Expected aggregator=RovoDevCLI, got "
        f"{type(inst.aggregator_inferencer).__name__}"
    )

    # Verify cascades reached children
    assert inst.debug_mode is True, "BTA.debug_mode should be cascaded from _debug_mode"
    assert inst.breakdown_inferencer.debug_mode is True, (
        "breakdown.debug_mode should be cascaded from _debug_mode"
    )
    assert inst.aggregator_inferencer.debug_mode is True, (
        "aggregator.debug_mode should be cascaded from _debug_mode"
    )

    # Verify Option A MI fix: RovoChat now has template_* attribs available
    assert hasattr(inst.breakdown_inferencer, "template_key"), (
        "RovoChatInferencer should have template_key attrib (MI fix). "
        "If missing, the TemplatedInferencerBase parent is not in MRO."
    )
    assert hasattr(inst.breakdown_inferencer, "template_root_space"), (
        "RovoChatInferencer should have template_root_space attrib (MI fix)"
    )
    assert hasattr(inst.breakdown_inferencer, "template_variables"), (
        "RovoChatInferencer should have template_variables attrib (MI fix)"
    )

    # Verify MI is in MRO
    from agent_foundation.common.inferencers.templated_inferencer_base import (
        TemplatedInferencerBase,
    )
    assert isinstance(inst.breakdown_inferencer, TemplatedInferencerBase), (
        "RovoChatInferencer must inherit from TemplatedInferencerBase (MI fix)"
    )

    # Verify worker_factory is set + callable
    assert inst.worker_factory is not None, "BTA.worker_factory must be set"
    assert callable(inst.worker_factory), (
        f"worker_factory should be callable; got {type(inst.worker_factory).__name__}"
    )

    # ------------------------------------------------------------------
    # Surfacing-mechanism contract (added 2026-05-18 with --output-path removal)
    # ------------------------------------------------------------------
    # The canonical role doc must surface inside the workspace via the
    # final_deliverables mechanism, not via an external --output-path copy.
    # This is a 3-attrib contract that must hold simultaneously.

    # 1) Workspace enables the final_deliverables/ promotion folder.
    # NOTE: `use_final_deliverables_folder` is a WORKSPACE attrib, NOT a BTA
    # attrib (a common confusion — putting it under `base_inferencer:` results
    # in a silent "Removing YAML key" framework warning).
    assert inst._workspace is not None, (
        "BTA must have a workspace bound at construction time"
    )
    assert getattr(inst._workspace, "use_final_deliverables_folder", False) is True, (
        "workspace.use_final_deliverables_folder must be True for canonical "
        "role_document.md to be promoted to outputs/final_deliverables/"
    )

    # 2) Aggregator declares its output is a deliverable (triggers promotion)
    assert inst.aggregator_inferencer.output_is_deliverable is True, (
        "aggregator.output_is_deliverable must be True so the aggregator's "
        "role_document.md is promoted up the BTA boundary"
    )

    # 3) BTA's own top-level output uses a NON-conflicting filename so the
    # summary text doesn't overwrite the real role_document.md
    assert inst.output_path == "run_summary.md", (
        f"BTA.output_path should be 'run_summary.md' (not 'role_document.md') "
        f"to avoid the summary text overwriting the canonical aggregator "
        f"deliverable at the top level. Got: {inst.output_path!r}"
    )
    assert inst.aggregator_inferencer.output_path == "role_document.md", (
        f"aggregator.output_path should be 'role_document.md' (the canonical "
        f"deliverable name). Got: {inst.aggregator_inferencer.output_path!r}"
    )
