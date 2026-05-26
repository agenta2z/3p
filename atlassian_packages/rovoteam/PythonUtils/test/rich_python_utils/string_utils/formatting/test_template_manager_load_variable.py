"""Tests for TemplateManager.load_variables unified batch API with cascade.

Covers:
- Per-folder version convention (``<var_name>/<version>.<ext>``)
- ``.config.yaml`` alias map (version -> filename)
- Pass 2 default fallback when version is missing
- Fallback-to-literal when no file matches
- ``@``-strict mode (raise FileNotFoundError)
- ``=``-literal mode (skip file lookup)
- Non-string pass-through
- Cross-space cascade (space/type → space → global _variables/)
"""

from pathlib import Path

import pytest

from python_utils.string_utils.formatting.template_manager import (
    TemplateManager,
)


@pytest.fixture
def templates_dir(tmp_path):
    """Build a minimal template tree used by load_variables.

    Layout::
        <root>/<root_space>/<tmpl_type>/_variables/<var_name>/<file>
    """
    root_space = tmp_path / "plan"
    main_dir = root_space / "main"
    vars_dir = main_dir / "_variables"
    main_dir.mkdir(parents=True)
    vars_dir.mkdir()
    (main_dir / "default.j2").write_text("dummy", encoding="utf-8")
    return tmp_path


def _make_manager(templates_dir, root_space="plan"):
    return TemplateManager(
        templates=str(templates_dir),
        active_template_type="main",
        active_template_root_space=root_space,
    )


class TestPerFolderVersionConvention:
    def test_version_specific_file(self, templates_dir):
        var_folder = (
            templates_dir / "plan" / "main" / "_variables" / "task_preamble"
        )
        var_folder.mkdir(parents=True)
        (var_folder / "aggregation.jinja2").write_text(
            "aggregation preamble", encoding="utf-8"
        )

        tm = _make_manager(templates_dir)
        result = tm.load_variables(
            {"task_preamble": "aggregation"}, root_space="plan"
        )
        assert result["task_preamble"] == "aggregation preamble"

    def test_default_fallback(self, templates_dir):
        var_folder = (
            templates_dir / "plan" / "main" / "_variables" / "task_instructions"
        )
        var_folder.mkdir(parents=True)
        (var_folder / "default.jinja2").write_text(
            "default instructions", encoding="utf-8"
        )

        tm = _make_manager(templates_dir)
        result = tm.load_variables(
            {"task_instructions": "aggregation"}, root_space="plan"
        )
        assert result["task_instructions"] == "default instructions"

    def test_config_yaml_alias(self, templates_dir):
        var_folder = (
            templates_dir / "plan" / "main" / "_variables" / "task_preamble"
        )
        var_folder.mkdir(parents=True)
        (var_folder / "agg_v2.jinja2").write_text(
            "aliased content", encoding="utf-8"
        )
        (var_folder / ".config.yaml").write_text(
            "aggregation: agg_v2\n", encoding="utf-8"
        )

        tm = _make_manager(templates_dir)
        result = tm.load_variables(
            {"task_preamble": "aggregation"}, root_space="plan"
        )
        assert result["task_preamble"] == "aliased content"

    def test_default_alias(self, templates_dir):
        var_folder = (
            templates_dir / "plan" / "main" / "_variables" / "task_preamble"
        )
        var_folder.mkdir(parents=True)
        (var_folder / "generic.jinja2").write_text(
            "generic default", encoding="utf-8"
        )
        (var_folder / ".config.yaml").write_text(
            "default: generic\n", encoding="utf-8"
        )

        tm = _make_manager(templates_dir)
        result = tm.load_variables(
            {"task_preamble": "aggregation"}, root_space="plan"
        )
        assert result["task_preamble"] == "generic default"


class TestFallbackToLiteral:
    def test_fallback_when_nothing_found(self, templates_dir):
        var_folder = (
            templates_dir / "plan" / "main" / "_variables" / "task_preamble"
        )
        var_folder.mkdir(parents=True)

        tm = _make_manager(templates_dir)
        result = tm.load_variables(
            {"task_preamble": "aggregation"}, root_space="plan"
        )
        assert result["task_preamble"] == "aggregation", (
            "load_variables must fall back to the literal version string "
            "when no file matches"
        )

    def test_fallback_when_folder_missing(self, templates_dir):
        tm = _make_manager(templates_dir)
        result = tm.load_variables(
            {"task_preamble": "aggregation"}, root_space="plan"
        )
        assert result["task_preamble"] == "aggregation"

    def test_empty_version_returns_empty_string(self, templates_dir):
        var_folder = (
            templates_dir / "plan" / "main" / "_variables" / "task_preamble"
        )
        var_folder.mkdir(parents=True)
        (var_folder / "default.jinja2").write_text(
            "default content", encoding="utf-8"
        )

        tm = _make_manager(templates_dir)
        result = tm.load_variables({"task_preamble": ""}, root_space="plan")
        assert result["task_preamble"] == ""


class TestStrictMode:
    def test_at_prefix_raises_when_missing(self, templates_dir):
        tm = _make_manager(templates_dir)
        with pytest.raises(FileNotFoundError, match="@aggregation"):
            tm.load_variables(
                {"task_preamble": "@aggregation"}, root_space="plan"
            )

    def test_at_prefix_resolves_when_present(self, templates_dir):
        var_folder = (
            templates_dir / "plan" / "main" / "_variables" / "task_preamble"
        )
        var_folder.mkdir(parents=True)
        (var_folder / "aggregation.jinja2").write_text(
            "strict content", encoding="utf-8"
        )

        tm = _make_manager(templates_dir)
        result = tm.load_variables(
            {"task_preamble": "@aggregation"}, root_space="plan"
        )
        assert result["task_preamble"] == "strict content"


class TestLiteralMode:
    def test_equals_prefix_skips_file_lookup(self, templates_dir):
        tm = _make_manager(templates_dir)
        result = tm.load_variables(
            {"task_preamble": "=inline content here"}, root_space="plan"
        )
        assert result["task_preamble"] == "inline content here"


class TestNonStringPassThrough:
    def test_dict_value_passes_through(self, templates_dir):
        tm = _make_manager(templates_dir)
        data = {"key": "value"}
        result = tm.load_variables(
            {"structured": data}, root_space="plan"
        )
        assert result["structured"] is data

    def test_none_value_with_default_version(self, templates_dir):
        var_folder = (
            templates_dir / "plan" / "main" / "_variables" / "task_preamble"
        )
        var_folder.mkdir(parents=True)
        (var_folder / "aggregation.jinja2").write_text(
            "agg content", encoding="utf-8"
        )

        tm = _make_manager(templates_dir)
        result = tm.load_variables(
            {"task_preamble": None},
            root_space="plan",
            default_version="aggregation",
        )
        assert result["task_preamble"] == "agg content"


class TestBatchResolution:
    def test_multiple_variables_different_versions(self, templates_dir):
        preamble_folder = (
            templates_dir / "plan" / "main" / "_variables" / "task_preamble"
        )
        preamble_folder.mkdir(parents=True)
        (preamble_folder / "aggregation.jinja2").write_text(
            "agg preamble", encoding="utf-8"
        )
        instr_folder = (
            templates_dir / "plan" / "main" / "_variables" / "task_instructions"
        )
        instr_folder.mkdir(parents=True)
        (instr_folder / "default.jinja2").write_text(
            "default instructions", encoding="utf-8"
        )

        tm = _make_manager(templates_dir)
        result = tm.load_variables(
            {
                "task_preamble": "aggregation",
                "task_instructions": "default",
            },
            root_space="plan",
        )
        assert result["task_preamble"] == "agg preamble"
        assert result["task_instructions"] == "default instructions"


class TestRootSpaceCascade:
    def test_root_space_argument_overrides_active(self, templates_dir):
        plan_folder = (
            templates_dir / "plan" / "main" / "_variables" / "task_preamble"
        )
        plan_folder.mkdir(parents=True)
        (plan_folder / "aggregation.jinja2").write_text(
            "plan content", encoding="utf-8"
        )
        impl_dir = templates_dir / "implementation" / "main"
        impl_dir.mkdir(parents=True)
        (impl_dir / "default.j2").write_text("dummy", encoding="utf-8")
        impl_folder = impl_dir / "_variables" / "task_preamble"
        impl_folder.mkdir(parents=True)
        (impl_folder / "aggregation.jinja2").write_text(
            "impl content", encoding="utf-8"
        )

        tm = _make_manager(templates_dir, root_space="plan")
        result = tm.load_variables(
            {"task_preamble": "aggregation"}, root_space="implementation"
        )
        assert result["task_preamble"] == "impl content"


class TestCrossSpaceCascade:
    def test_global_variables_found_when_space_specific_missing(self, templates_dir):
        global_folder = templates_dir / "_variables" / "notes"
        global_folder.mkdir(parents=True)
        (global_folder / "local_search_efficiency.jinja2").write_text(
            "shared search notes", encoding="utf-8"
        )

        tm = _make_manager(templates_dir)
        result = tm.load_variables(
            {"notes": "local_search_efficiency"}, root_space="plan"
        )
        assert result["notes"] == "shared search notes"

    def test_space_specific_overrides_global(self, templates_dir):
        global_folder = templates_dir / "_variables" / "notes"
        global_folder.mkdir(parents=True)
        (global_folder / "local_search_efficiency.jinja2").write_text(
            "global version", encoding="utf-8"
        )
        specific_folder = (
            templates_dir / "plan" / "main" / "_variables" / "notes"
        )
        specific_folder.mkdir(parents=True)
        (specific_folder / "local_search_efficiency.jinja2").write_text(
            "plan-specific version", encoding="utf-8"
        )

        tm = _make_manager(templates_dir)
        result = tm.load_variables(
            {"notes": "local_search_efficiency"}, root_space="plan"
        )
        assert result["notes"] == "plan-specific version"

    def test_space_level_cascade(self, templates_dir):
        space_folder = templates_dir / "plan" / "_variables" / "notes"
        space_folder.mkdir(parents=True)
        (space_folder / "local_search_efficiency.jinja2").write_text(
            "space-level version", encoding="utf-8"
        )

        tm = _make_manager(templates_dir)
        result = tm.load_variables(
            {"notes": "local_search_efficiency"}, root_space="plan"
        )
        assert result["notes"] == "space-level version"


class TestDotKeyNotation:
    """Test dot-separated keys for Jinja2 dot-access: {{ notes.local_search_efficiency }}.

    Key "notes.local_search_efficiency" splits into var_name="notes" + version="local_search_efficiency".
    Result is nested: {"notes": {"local_search_efficiency": "<content>"}}.
    """

    def test_dot_key_returns_nested_dict(self, templates_dir):
        var_folder = (
            templates_dir / "plan" / "main" / "_variables" / "notes"
        )
        var_folder.mkdir(parents=True)
        (var_folder / "local_search_efficiency.jinja2").write_text(
            "search notes content", encoding="utf-8"
        )

        tm = _make_manager(templates_dir)
        result = tm.load_variables(
            {"notes.local_search_efficiency": None}, root_space="plan"
        )
        assert isinstance(result["notes"], dict)
        assert result["notes"]["local_search_efficiency"] == "search notes content"

    def test_dot_key_with_global_cascade(self, templates_dir):
        global_folder = templates_dir / "_variables" / "notes"
        global_folder.mkdir(parents=True)
        (global_folder / "local_search_efficiency.jinja2").write_text(
            "global search notes", encoding="utf-8"
        )

        tm = _make_manager(templates_dir)
        result = tm.load_variables(
            {"notes.local_search_efficiency": None}, root_space="plan"
        )
        assert result["notes"]["local_search_efficiency"] == "global search notes"

    def test_dot_key_renders_in_jinja2_template(self, templates_dir):
        """End-to-end: {{ notes.local_search_efficiency }} renders file content."""
        from python_utils.string_utils.formatting.jinja2_format import (
            format_template,
        )

        var_folder = (
            templates_dir / "plan" / "main" / "_variables" / "notes"
        )
        var_folder.mkdir(parents=True)
        (var_folder / "local_search_efficiency.jinja2").write_text(
            "## NOTES\n- Scope searches narrowly", encoding="utf-8"
        )
        tmpl_dir = templates_dir / "plan" / "main"
        (tmpl_dir / "initial.jinja2").write_text(
            "Before\n{{ notes.local_search_efficiency }}\nAfter",
            encoding="utf-8",
        )

        tm = TemplateManager(
            templates=str(templates_dir),
            active_template_type="main",
            template_formatter=format_template,
        )
        feed = tm.load_variables(
            {"notes.local_search_efficiency": None}, root_space="plan"
        )
        rendered = tm("initial", active_template_root_space="plan", **feed)
        assert "## NOTES" in rendered
        assert "Scope searches narrowly" in rendered
        assert "Before" in rendered
        assert "After" in rendered

    def test_dot_key_undefined_renders_empty(self, templates_dir):
        """{{ notes.local_search_efficiency }} renders empty when not configured."""
        from python_utils.string_utils.formatting.jinja2_format import (
            format_template,
        )

        tmpl_dir = templates_dir / "plan" / "main"
        (tmpl_dir / "initial.jinja2").write_text(
            "Before|{{ notes.local_search_efficiency }}|After",
            encoding="utf-8",
        )

        tm = TemplateManager(
            templates=str(templates_dir),
            active_template_type="main",
            template_formatter=format_template,
        )
        # No notes in feed — ChainableUndefined renders empty
        rendered = tm("initial", active_template_root_space="plan")
        assert rendered == "Before||After"

    def test_dot_key_mixed_with_flat(self, templates_dir):
        """Dot keys and flat keys coexist in the same call."""
        preamble_folder = (
            templates_dir / "plan" / "main" / "_variables" / "task_preamble"
        )
        preamble_folder.mkdir(parents=True)
        (preamble_folder / "default.jinja2").write_text(
            "preamble content", encoding="utf-8"
        )
        notes_folder = (
            templates_dir / "plan" / "main" / "_variables" / "notes"
        )
        notes_folder.mkdir(parents=True)
        (notes_folder / "local_search_efficiency.jinja2").write_text(
            "search notes", encoding="utf-8"
        )

        tm = _make_manager(templates_dir)
        result = tm.load_variables(
            {
                "task_preamble": "default",
                "notes.local_search_efficiency": None,
            },
            root_space="plan",
        )
        assert result["task_preamble"] == "preamble content"
        assert result["notes"]["local_search_efficiency"] == "search notes"

    def test_dot_key_fallback_to_literal(self, templates_dir):
        """When file not found, dot key falls back to version string in nested dict."""
        tm = _make_manager(templates_dir)
        result = tm.load_variables(
            {"notes.nonexistent": None}, root_space="plan"
        )
        assert result["notes"]["nonexistent"] == "nonexistent"


class TestEmptyFileSemantics:
    def test_empty_file_returns_empty_string_not_fallback(self, templates_dir):
        var_folder = (
            templates_dir / "plan" / "main" / "_variables" / "task_preamble"
        )
        var_folder.mkdir(parents=True)
        (var_folder / "aggregation.jinja2").write_text("", encoding="utf-8")

        tm = _make_manager(templates_dir)
        result = tm.load_variables(
            {"task_preamble": "aggregation"}, root_space="plan"
        )
        assert result["task_preamble"] == "", (
            "Empty file should return '' (file was found), not fall back to "
            "the literal version string"
        )
