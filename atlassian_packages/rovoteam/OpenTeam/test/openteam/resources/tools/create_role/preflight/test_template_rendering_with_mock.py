"""Preflight: RovoChat template rendering (mock inferencer, no LLM call).

CRITICAL regression test for the Option A MI fix (RovoChat now inherits
``TemplatedInferencerBase``). Verifies the breakdown inferencer's
``_render_prompt`` produces a fully-rendered Jinja template (~3000+ chars)
rather than passing the raw 38-byte role description through unchanged.

The empirical bug this catches: pre-MI, the breakdown InferenceInput was the
bare 38-byte role_description instead of the fully-rendered Jinja template.

Runtime: ~10s, no LLM cost.
"""

from __future__ import annotations

import pytest

from ._common import (
    YAML_PATH,
    set_template_root_env,
)


@pytest.mark.asyncio
async def test_template_rendering_with_mock_inferencer(tmp_path, monkeypatch):
    """Verify breakdown InferenceInput is a fully-rendered Jinja template.

    Approach: load the create_role topology, then invoke the breakdown
    inferencer's ``_render_prompt`` directly. Confirm the rendered output
    contains template markers (NOT just the raw role_description).

    This catches regressions where:
      * RovoChat falls back to StreamingInferencerBase-only (no template
        rendering — the original bug Option A fixed)
      * The template attribs (``template_key``, ``template_root_space``)
        are silently dropped instead of accepted
      * The framework's ``_render_prompt`` hook is bypassed
    """
    set_template_root_env(monkeypatch)

    import agent_foundation.common.configs.registered_targets  # noqa: F401
    from python_utils.config_utils import load_config, instantiate

    # Instantiate BTA from YAML (must supply workspace_root)
    cfg = load_config(str(YAML_PATH), overrides={
        "_params": {"workspace_root": str(tmp_path)},
    })
    bta = instantiate(cfg)

    # Render the breakdown prompt using the actual code path.
    breakdown = bta.breakdown_inferencer
    raw_request = "hire a machine learning engineer (MLE)"

    # Call the framework's template rendering hook directly
    rendered = breakdown._render_prompt(raw_request, extra_feed={})

    # CRITICAL ASSERTION: rendered must be MUCH longer than raw input
    assert len(rendered) > 500, (
        f"Rendered prompt is too short ({len(rendered)} chars). "
        f"Expected fully-rendered template (>500 chars). "
        f"This suggests RovoChat is NOT rendering templates — "
        f"the MI fix (TemplatedInferencerBase parent) may be missing. "
        f"Got: {rendered[:200]}"
    )

    # Verify rendered content has template-injected markers
    assert raw_request in rendered, (
        "Rendered prompt should contain the original role description"
    )
    # The breakdown template (task_breakdown/main/initial.jinja2) has:
    # "break it into {{ max_breakdown | default('3-5') }} focused subtasks"
    assert "subtasks" in rendered.lower(), (
        f"Rendered prompt should contain 'subtasks' from breakdown template. "
        f"Got first 500 chars: {rendered[:500]}"
    )
    # Templates use <OriginalUserRequest> or similar delimiter tags
    assert "<" in rendered and ">" in rendered, (
        "Rendered prompt should contain Jinja-rendered XML-like tags"
    )

    print(f"\n[template-rendering] raw input: {len(raw_request)} chars")
    print(f"[template-rendering] rendered:   {len(rendered)} chars")
    print(f"[template-rendering] template_key: {breakdown.template_key}")
    print(
        "[template-rendering] template_root_space: "
        f"{breakdown.template_root_space}"
    )
