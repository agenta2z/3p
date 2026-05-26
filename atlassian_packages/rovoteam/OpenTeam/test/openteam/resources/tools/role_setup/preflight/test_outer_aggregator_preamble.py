"""Preflight: verify role_setup's OUTER aggregator renders correctly.

Tests:
1. Aggregation preamble is present (not the default planning preamble)
2. No ConflictAwarePromptBuilder in YAML (removed in favor of LLM-judgment)
3. task_instructions renders with worker discovery + integration instructions
4. Template variables (workspace_outputs, output_path) render correctly
5. task_preamble is not suppressed

Runtime: ~5s, no LLM cost.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from ._common import (
    AF_TEMPLATES_DIR,
    OPENSTARTUP_TEMPLATES_DIR,
    OUTER_YAML_PATH,
    set_template_root_env,
)


def _instantiate_outer_bta(tmp_path, monkeypatch):
    """Helper: instantiate role_setup YAML and return the outer BTA instance."""
    set_template_root_env(monkeypatch)

    import agent_foundation.common.configs.registered_targets  # noqa: F401
    from python_utils.config_utils import load_config, instantiate
    from omegaconf import OmegaConf

    import agent_foundation.resources as _af_res
    _os_templates = (
        Path(__file__).resolve().parents[6]
        / "src" / "openteam" / "server" / "resources" / "prompt_templates"
    )
    _af_templates = Path(_af_res.__file__).parent / "prompt_templates"

    overrides = {
        "_params": {"workspace_root": str(tmp_path)},
        "_target_path": str(tmp_path),
        "_template_manager.templates": [str(_os_templates), str(_af_templates)],
    }

    cfg = load_config(str(OUTER_YAML_PATH), overrides=overrides)
    cfg = OmegaConf.to_container(cfg, resolve=True)
    cfg = OmegaConf.create(cfg)
    return instantiate(cfg)


def test_outer_aggregator_has_aggregation_preamble(tmp_path, monkeypatch):
    """Aggregation preamble renders with upstream_artifacts."""
    inst = _instantiate_outer_bta(tmp_path, monkeypatch)
    agg = inst.aggregator_inferencer

    agg.template_extra_feed["upstream_artifacts"] = (
        "### Result 1\n(See file: `worker_0/outputs/skills/foo/SKILL.md`)\n\n"
        "### Result 2\n(See file: `worker_1/outputs/tools/bar/tool.json`)\n\n"
        "### Result 3\nRole-tool association JSON produced."
    )

    rendered = agg._render_prompt("Set up an MLE role")

    assert "aggregating" in rendered.lower(), (
        "Outer aggregator should have the aggregation preamble."
    )
    assert "## Planning Context" not in rendered, (
        "Outer aggregator should NOT have the default planning preamble."
    )
    assert "(See file:" in rendered, (
        "upstream_artifacts should render with (See file:) references."
    )


def test_no_conflict_aware_prompt_builder_in_yaml():
    """YAML should NOT have aggregator_prompt_builder (removed in favor of
    default upstream_artifacts + LLM-judgment integration)."""
    from omegaconf import OmegaConf

    cfg = OmegaConf.load(str(OUTER_YAML_PATH))
    assert "aggregator_prompt_builder" not in cfg, (
        "aggregator_prompt_builder should be removed from role_setup.yaml. "
        "The outer aggregator uses the default upstream_artifacts approach."
    )
    assert cfg.get("conflict_resolution_mode") is None, (
        "Top-level conflict_resolution_mode should be removed."
    )


def test_task_instructions_has_worker_discovery_content(tmp_path, monkeypatch):
    """The outer aggregator's task_instructions should contain LLM-judgment
    integration instructions (discover, check overlaps, deduplicate, write)."""
    inst = _instantiate_outer_bta(tmp_path, monkeypatch)
    agg = inst.aggregator_inferencer

    agg.template_extra_feed["upstream_artifacts"] = "### Result 1\ntest"

    rendered = agg._render_prompt("Set up a role")

    assert "Discover all worker deliverables" in rendered, (
        "task_instructions should instruct aggregator to discover worker deliverables."
    )
    assert "overlaps and duplicates" in rendered.lower(), (
        "task_instructions should instruct aggregator to check for overlaps."
    )
    assert "Integrate and deduplicate" in rendered, (
        "task_instructions should instruct aggregator to integrate and deduplicate."
    )


def test_workspace_outputs_renders_in_task_instructions(tmp_path, monkeypatch):
    """{{ workspace_outputs }} should render to an absolute path in the
    task_instructions, giving the aggregator correct write targets."""
    inst = _instantiate_outer_bta(tmp_path, monkeypatch)
    agg = inst.aggregator_inferencer

    ws = MagicMock()
    ws.root = str(tmp_path / "aggregator_ws")
    agg._workspace = ws

    agg.template_extra_feed["upstream_artifacts"] = "### Result 1\ntest"

    rendered = agg._render_prompt("Set up a role")

    expected_outputs = str(tmp_path / "aggregator_ws" / "outputs")
    assert expected_outputs in rendered, (
        f"workspace_outputs should render to {expected_outputs} in the prompt. "
        f"Got: {rendered[:500]!r}"
    )


def test_role_doc_path_renders_in_task_instructions(tmp_path, monkeypatch):
    """{{ role_doc_path }} should render in the task_instructions template,
    allowing the aggregator to reference the role document by path."""
    inst = _instantiate_outer_bta(tmp_path, monkeypatch)
    agg = inst.aggregator_inferencer

    # Simulate what the executor injects via template_extra_feed overrides.
    # At runtime, load_config applies "template_extra_feed.role_doc_path"
    # to each inferencer's config before instantiation.
    role_doc = str(tmp_path / "role_document.md")
    agg.template_extra_feed["role_doc_path"] = role_doc
    agg.template_extra_feed["upstream_artifacts"] = "### Result 1\ntest"

    rendered = agg._render_prompt("Set up a role")

    assert role_doc in rendered, (
        f"role_doc_path should render in the outer aggregator prompt. "
        f"Expected '{role_doc}' in rendered output."
    )


def test_outer_aggregator_no_task_preamble_suppression():
    """Verify role_setup.yaml does not suppress task_preamble with empty string."""
    from omegaconf import OmegaConf

    cfg = OmegaConf.load(str(OUTER_YAML_PATH))
    agg_vars = cfg.get("aggregator_inferencer", {}).get("template_variables", {})

    assert agg_vars.get("task_preamble", "NOT_SET") != "", (
        "aggregator_inferencer.template_variables.task_preamble must not be "
        "set to empty string — this suppresses the aggregation preamble. "
        "Remove it to let SLOT_DEFAULTS resolve to the aggregation variant."
    )
