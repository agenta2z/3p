"""Preflight: verify the CLI entry point (execute → _run_topology) produces
a TemplateManager with both template roots and correct aggregation preamble.

This catches the class of bugs where:
- The Python API (build_create_role_inferencer) works correctly
- But the CLI path (execute → YAML topology → _run_topology) breaks because
  the override map clobbers the multi-root template list

Root cause of the A14a regression runs #1-#4: execute() had
``"_template_manager.templates": str(single_path)`` which overwrote the
YAML's two-root list. The centralized fix in _run_topology() ensures all
task-based tools get both roots by default.

Runtime: ~5s, no LLM cost.
"""

from __future__ import annotations

from pathlib import Path

from ._common import (
    AF_TEMPLATES_DIR,
    OPENSTARTUP_TEMPLATES_DIR,
    YAML_PATH,
    set_template_root_env,
)


def test_cli_entry_point_has_both_template_roots(tmp_path, monkeypatch):
    """Simulate execute()'s override path and verify 2 template roots."""
    set_template_root_env(monkeypatch)

    import agent_foundation.common.configs.registered_targets  # noqa: F401
    from python_utils.config_utils import load_config, instantiate
    from omegaconf import OmegaConf

    # Replicate what execute() + _run_topology() do:
    # 1. Load YAML
    # 2. Apply the SAME overrides that _run_topology applies
    import agent_foundation.resources as _af_res
    _os_templates = Path(__file__).resolve().parents[6] / "src" / "openteam" / "server" / "resources" / "prompt_templates"
    _af_templates = Path(_af_res.__file__).parent / "prompt_templates"

    overrides = {
        "_params": {"workspace_root": str(tmp_path)},
        "_target_path": str(tmp_path),
        "_template_manager.templates": [str(_os_templates), str(_af_templates)],
    }

    cfg = load_config(str(YAML_PATH), overrides=overrides)
    cfg = OmegaConf.to_container(cfg, resolve=True)
    cfg = OmegaConf.create(cfg)
    inst = instantiate(cfg)

    agg = inst.aggregator_inferencer
    tm = agg.template_manager

    # Check 1: TemplateManager has BOTH roots
    roots = tm._original_templates_paths
    assert len(roots) >= 2, (
        f"TemplateManager should have >=2 roots (OpenTeam + AgentFoundation), "
        f"got {len(roots)}: {roots}"
    )
    roots_str = " ".join(str(r) for r in roots)
    assert "AgentFoundation" in roots_str or "agent_foundation" in roots_str, (
        f"AgentFoundation root missing from TemplateManager roots: {roots}"
    )

    # Check 2: FileSpaceManager also has both roots
    if hasattr(tm, "_file_space") and tm._file_space is not None:
        fsm_roots = [str(r) for r in tm._file_space.roots]
        assert len(fsm_roots) >= 2, (
            f"FileSpaceManager should have >=2 roots, got {len(fsm_roots)}: {fsm_roots}"
        )

    # Check 3: enable_templated_feed is True
    assert tm.enable_templated_feed is True, (
        "TemplateManager must have enable_templated_feed=True for wrapper "
        "variable resolution"
    )


def test_cli_entry_aggregator_resolves_aggregation_preamble(tmp_path, monkeypatch):
    """Verify the aggregator resolves the aggregation preamble (not the default)
    when going through the CLI override path."""
    set_template_root_env(monkeypatch)

    import agent_foundation.common.configs.registered_targets  # noqa: F401
    from python_utils.config_utils import load_config, instantiate
    from omegaconf import OmegaConf

    import agent_foundation.resources as _af_res
    _os_templates = Path(__file__).resolve().parents[6] / "src" / "openteam" / "server" / "resources" / "prompt_templates"
    _af_templates = Path(_af_res.__file__).parent / "prompt_templates"

    overrides = {
        "_params": {"workspace_root": str(tmp_path)},
        "_target_path": str(tmp_path),
        "_template_manager.templates": [str(_os_templates), str(_af_templates)],
    }

    cfg = load_config(str(YAML_PATH), overrides=overrides)
    cfg = OmegaConf.to_container(cfg, resolve=True)
    cfg = OmegaConf.create(cfg)
    inst = instantiate(cfg)

    agg = inst.aggregator_inferencer

    # Simulate BTA injecting upstream artifacts
    agg.template_extra_feed["upstream_artifacts"] = (
        "### Result 1\n(See file: worker_0/facet.md)"
    )

    # Call _render_prompt — the exact production path
    rendered = agg._render_prompt("hire a machine learning engineer")

    # A14a checks
    assert "aggregating" in rendered.lower(), (
        "Aggregator preamble should contain 'aggregating' keyword. "
        "Got default preamble instead — likely missing AgentFoundation template root."
    )
    assert "## Planning Context" not in rendered, (
        "Aggregator should NOT have the default planning preamble. "
        "Wrapper variable recomposition may not be working."
    )
    assert "(See file:" in rendered, (
        "upstream_artifacts should be rendered with (See file:) references "
        "inside the aggregation preamble."
    )
