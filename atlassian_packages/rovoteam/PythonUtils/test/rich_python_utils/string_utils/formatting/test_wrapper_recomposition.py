"""Tests for wrapper variable recomposition in _resolve_templated_feed.

When enable_templated_feed=True and a wrapper variable (e.g.,
context.user_request_with_task_preamble) contains {{ task_preamble }},
auto-discovery resolves {{ task_preamble }} using the TemplateManager's
default version, baking in the wrong value. The recomposition step
re-loads the raw wrapper file and re-renders it against the resolved
feed (which has the caller's explicit values from load_variables with
master_version). This test verifies the recomposition works correctly.
"""

import pytest
from pathlib import Path
from python_utils.string_utils.formatting.template_manager import TemplateManager


@pytest.fixture
def recomposition_root(tmp_path):
    """Create a template tree that exercises the wrapper recomposition path."""
    root = tmp_path / "templates"

    # Main template
    main_dir = root / "plan" / "main"
    main_dir.mkdir(parents=True)
    (main_dir / "initial.jinja2").write_text(
        "{{ context.user_request_with_task_preamble }}\n---\n{{ task_instructions }}"
    )

    # Wrapper variable (references {{ task_preamble }} and {{ input }})
    wrapper_dir = root / "_variables" / "context"
    wrapper_dir.mkdir(parents=True)
    (wrapper_dir / "user_request_with_task_preamble.jinja2").write_text(
        "{{ task_preamble }}\n\n## Original User Request\n{{ input }}"
    )

    # task_preamble: default version
    preamble_dir = root / "plan" / "main" / "_variables" / "task_preamble"
    preamble_dir.mkdir(parents=True)
    (preamble_dir / "default.jinja2").write_text("DEFAULT_PREAMBLE_MARKER")

    # task_preamble: aggregation/default (master_version subdirectory)
    agg_preamble_dir = preamble_dir / "aggregation"
    agg_preamble_dir.mkdir(parents=True)
    (agg_preamble_dir / "default.jinja2").write_text(
        "AGGREGATION_PREAMBLE_MARKER with {{ upstream_artifacts }}"
    )

    # task_instructions: aggregation/create_role
    instr_dir = root / "plan" / "main" / "_variables" / "task_instructions"
    instr_dir.mkdir(parents=True)
    (instr_dir / "default.jinja2").write_text("DEFAULT_INSTRUCTIONS")
    agg_instr_dir = instr_dir / "aggregation"
    agg_instr_dir.mkdir(parents=True)
    (agg_instr_dir / "default.jinja2").write_text("AGG_DEFAULT_INSTRUCTIONS")
    (agg_instr_dir / "create_role.jinja2").write_text("AGG_CREATE_ROLE_INSTRUCTIONS")

    return root


class TestWrapperRecomposition:
    def test_without_master_version_uses_default_preamble(self, recomposition_root):
        """Without master_version but with explicit default_version,
        wrapper resolves task_preamble from the version-specific file
        (or default.jinja2 if the version doesn't exist)."""
        tm = TemplateManager(
            templates=str(recomposition_root),
            active_template_type="main",
            predefined_variables=True,
            enable_templated_feed=True,
        )
        feed = tm.load_variables(
            {"task_preamble": None, "task_instructions": None},
            root_space="plan",
            default_version="nonexistent_version",
        )
        feed["input"] = "test query"
        result = tm("initial", active_template_root_space="plan", **feed)

        assert "DEFAULT_PREAMBLE_MARKER" in result, \
            "Should fall back to default.jinja2 when version doesn't exist"
        assert "AGGREGATION_PREAMBLE_MARKER" not in result
        assert "test query" in result

    def test_with_master_version_recomposes_wrapper(self, recomposition_root):
        """With master_version, wrapper is recomposed using aggregation preamble."""
        tm = TemplateManager(
            templates=str(recomposition_root),
            active_template_type="main",
            predefined_variables=True,
            enable_templated_feed=True,
        )
        feed = tm.load_variables(
            {"task_preamble": None, "task_instructions": None},
            root_space="plan",
            default_version="create_role",
            master_version="aggregation",
        )
        feed["input"] = "hire MLE"
        feed["upstream_artifacts"] = "(See file: worker_0/facet.md)"
        result = tm("initial", active_template_root_space="plan", **feed)

        assert "AGGREGATION_PREAMBLE_MARKER" in result, \
            "Wrapper should use aggregation preamble after recomposition"
        assert "DEFAULT_PREAMBLE_MARKER" not in result, \
            "Default preamble should NOT appear after recomposition"
        assert "(See file: worker_0/facet.md)" in result, \
            "upstream_artifacts should be rendered inside the recomposed preamble"
        assert "hire MLE" in result, \
            "{{ input }} should still resolve correctly"
        assert "AGG_CREATE_ROLE_INSTRUCTIONS" in result, \
            "task_instructions should resolve via master_version+version"

    def test_recomposition_only_when_enabled(self, recomposition_root):
        """Without enable_templated_feed, wrapper keeps the auto-discovered default."""
        tm = TemplateManager(
            templates=str(recomposition_root),
            active_template_type="main",
            predefined_variables=True,
            enable_templated_feed=False,
        )
        feed = tm.load_variables(
            {"task_preamble": None},
            root_space="plan",
            master_version="aggregation",
        )
        feed["input"] = "test"
        result = tm("initial", active_template_root_space="plan", **feed)

        # Without enable_templated_feed, the wrapper is NOT recomposed
        # So the default preamble is baked in
        assert "DEFAULT_PREAMBLE_MARKER" in result

    def test_recomposition_preserves_non_wrapper_values(self, recomposition_root):
        """Recomposition only affects nested dict values from wrapper files,
        not top-level values or values without source files."""
        tm = TemplateManager(
            templates=str(recomposition_root),
            active_template_type="main",
            predefined_variables=True,
            enable_templated_feed=True,
        )
        feed = tm.load_variables(
            {"task_preamble": None, "task_instructions": None},
            root_space="plan",
            default_version="create_role",
            master_version="aggregation",
        )
        feed["input"] = "preserve this"
        feed["upstream_artifacts"] = "PRESERVED_ARTIFACTS"
        result = tm("initial", active_template_root_space="plan", **feed)

        assert "preserve this" in result
        assert "PRESERVED_ARTIFACTS" in result
        assert "AGG_CREATE_ROLE_INSTRUCTIONS" in result
