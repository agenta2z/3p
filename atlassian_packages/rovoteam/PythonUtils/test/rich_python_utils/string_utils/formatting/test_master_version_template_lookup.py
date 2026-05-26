"""Tests for master_version parameter in TemplateManager.__call__ and get_raw_template.

master_version adds a subdirectory level to wrapper template lookup,
mirroring how it works for variables. With master_version="aggregation":
  - Try: space/main/aggregation/initial.jinja2
  - Fallback: space/main/initial.jinja2
"""

import pytest

from python_utils.string_utils.formatting.template_manager import TemplateManager


@pytest.fixture
def templates_with_master_version(tmp_path):
    """Create a template tree with master_version subdirectory variants."""
    main_dir = tmp_path / "space" / "main"
    main_dir.mkdir(parents=True)

    (main_dir / "initial.jinja2").write_text("DEFAULT: Hello {{ name }}")
    (main_dir / "review.jinja2").write_text("DEFAULT REVIEW: {{ name }}")

    agg_dir = main_dir / "aggregation"
    agg_dir.mkdir()
    (agg_dir / "initial.jinja2").write_text("AGGREGATION: Aggregating {{ name }}")

    return tmp_path


@pytest.fixture
def tm(templates_with_master_version):
    return TemplateManager(
        templates=str(templates_with_master_version),
        active_template_root_space="space",
        active_template_type="main",
    )


class TestMasterVersionCallLookup:

    def test_master_version_finds_subdirectory_template(self, tm):
        result = tm("initial", master_version="aggregation", name="Alice")
        assert "AGGREGATION" in result
        assert "Alice" in result

    def test_master_version_falls_back_when_no_subdirectory_variant(self, tm):
        result = tm("review", master_version="aggregation", name="Bob")
        assert "DEFAULT REVIEW" in result
        assert "Bob" in result

    def test_no_master_version_uses_default(self, tm):
        result = tm("initial", name="Carol")
        assert "DEFAULT" in result
        assert "Carol" in result

    def test_master_version_none_preserves_existing_behavior(self, tm):
        result = tm("initial", master_version=None, name="Dave")
        assert "DEFAULT" in result

    def test_nonexistent_master_version_falls_back(self, tm):
        result = tm("initial", master_version="nonexistent", name="Eve")
        assert "DEFAULT" in result


class TestMasterVersionGetRawTemplate:

    def test_get_raw_template_with_master_version(self, tm):
        raw = tm.get_raw_template("initial", master_version="aggregation")
        assert raw is not None
        assert "AGGREGATION" in raw

    def test_get_raw_template_fallback(self, tm):
        raw = tm.get_raw_template("review", master_version="aggregation")
        assert raw is not None
        assert "DEFAULT REVIEW" in raw

    def test_get_raw_template_no_master_version(self, tm):
        raw = tm.get_raw_template("initial")
        assert raw is not None
        assert "DEFAULT" in raw


class TestMasterVersionBackwardCompat:

    def test_existing_template_version_still_works(self, templates_with_master_version):
        main_dir = templates_with_master_version / "space" / "main"
        (main_dir / "initial.enterprise.jinja2").write_text("ENTERPRISE: {{ name }}")

        tm = TemplateManager(
            templates=str(templates_with_master_version),
                        active_template_root_space="space",
            active_template_type="main",
            template_version="enterprise",
        )
        result = tm("initial", name="Frank")
        assert "ENTERPRISE" in result

    def test_master_version_and_template_version_coexist(self, templates_with_master_version):
        main_dir = templates_with_master_version / "space" / "main"
        (main_dir / "initial.enterprise.jinja2").write_text("ENTERPRISE: {{ name }}")

        tm = TemplateManager(
            templates=str(templates_with_master_version),
                        active_template_root_space="space",
            active_template_type="main",
            template_version="enterprise",
        )
        result = tm("initial", master_version="aggregation", name="Grace")
        assert "AGGREGATION" in result
