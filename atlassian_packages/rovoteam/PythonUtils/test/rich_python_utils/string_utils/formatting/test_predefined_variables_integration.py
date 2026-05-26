"""Tests for TemplateManager predefined_variables integration."""

import pytest
from pathlib import Path

from python_utils.string_utils.formatting.template_manager import (
    TemplateManager,
    VariableLoader,
    VariableLoaderConfig,
)


@pytest.fixture
def fixtures_dir():
    """Return the path to the fixtures directory (same as test_variable_manager)."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def mock_templates_dir():
    """Return the path to the example mock_templates directory."""
    return Path(__file__).parent.parent.parent.parent.parent / "examples" / "python_utils" / "string_utils" / "variable_loader_examples" / "mock_templates"


class TestPredefinedVariablesTrue:
    """Tests for predefined_variables=True (auto-create VariableLoader)."""

    def test_auto_creates_variable_loader(self, fixtures_dir):
        """Test that predefined_variables=True creates a VariableLoader."""
        tm = TemplateManager(
            templates=str(fixtures_dir),
            predefined_variables=True,
        )
        assert tm._variable_loader is not None
        assert tm._static_predefined_vars is None

    def test_resolves_variables_automatically(self, tmp_path):
        """Test that predefined variables are resolved and merged."""
        # Create a template structure with a template and _variables
        (tmp_path / "main").mkdir()
        (tmp_path / "main" / "default.j2").write_text("Hello {{notes_greeting}}, {{user_name}}!")

        vars_dir = tmp_path / "_variables" / "notes"
        vars_dir.mkdir(parents=True)
        (vars_dir / "greeting.hbs").write_text("Welcome")

        tm = TemplateManager(
            templates=str(tmp_path),
            predefined_variables=True,
            active_template_type="main",
        )
        result = tm(user_name="Alice")
        assert "Welcome" in result
        assert "Alice" in result

    def test_user_kwargs_override_predefined(self, tmp_path):
        """Test that user kwargs override predefined variables."""
        # Create a template structure
        (tmp_path / "main").mkdir()
        (tmp_path / "main" / "default.j2").write_text("{{notes_greeting}}, {{user_name}}!")

        vars_dir = tmp_path / "_variables" / "notes"
        vars_dir.mkdir(parents=True)
        (vars_dir / "greeting.hbs").write_text("Hello")

        tm = TemplateManager(
            templates=str(tmp_path),
            predefined_variables=True,
            active_template_type="main",
        )
        # Override the predefined variable
        result = tm(notes_greeting="CUSTOM OVERRIDE", user_name="Bob")
        assert "CUSTOM OVERRIDE" in result
        assert "Hello" not in result

    def test_raises_if_templates_not_path(self):
        """Test that predefined_variables=True raises if templates is not a path."""
        with pytest.raises(ValueError, match="requires templates to be a path string"):
            TemplateManager(
                default_template="Hello {{name}}",
                templates={"greet": "Hello {{name}}!"},
                predefined_variables=True,
            )


class TestPredefinedVariablesLoader:
    """Tests for predefined_variables=VariableLoader instance."""

    def test_uses_provided_loader(self, fixtures_dir):
        """Test that a provided VariableLoader is used."""
        config = VariableLoaderConfig(enable_overrides=True)
        custom_loader = VariableLoader(template_dir=str(fixtures_dir), config=config)

        tm = TemplateManager(
            templates=str(fixtures_dir),
            predefined_variables=custom_loader,
        )
        assert tm._variable_loader is custom_loader
        assert tm._static_predefined_vars is None


class TestPredefinedVariablesMapping:
    """Tests for predefined_variables=Mapping (static dict)."""

    def test_uses_static_mapping(self):
        """Test that a static mapping is used for predefined variables."""
        static_vars = {
            "header": "Static Header Content",
            "footer": "Static Footer Content",
        }
        tm = TemplateManager(
            default_template="{{header}} - {{name}} - {{footer}}",
            predefined_variables=static_vars,
        )
        assert tm._variable_loader is None
        assert tm._static_predefined_vars == static_vars

    def test_static_vars_merged_with_kwargs(self):
        """Test that static predefined vars are merged with kwargs."""
        static_vars = {
            "header": "Static Header",
            "footer": "Static Footer",
        }
        tm = TemplateManager(
            default_template="{{header}} - {{name}} - {{footer}}",
            predefined_variables=static_vars,
        )
        result = tm(name="Alice")
        assert "Static Header" in result
        assert "Static Footer" in result
        assert "Alice" in result

    def test_kwargs_override_static_vars(self):
        """Test that kwargs override static predefined variables."""
        static_vars = {
            "header": "Static Header",
            "name": "Default Name",
        }
        tm = TemplateManager(
            default_template="{{header}} - {{name}}",
            predefined_variables=static_vars,
        )
        result = tm(name="Override Name")
        assert "Override Name" in result
        assert "Default Name" not in result

    def test_feed_overrides_static_vars(self):
        """Test that feed dict overrides static predefined variables."""
        static_vars = {
            "header": "Static Header",
            "name": "Default Name",
        }
        tm = TemplateManager(
            default_template="{{header}} - {{name}}",
            predefined_variables=static_vars,
        )
        result = tm(feed={"name": "Feed Name"})
        assert "Feed Name" in result
        assert "Default Name" not in result


class TestPredefinedVariablesNone:
    """Tests for predefined_variables=None (disabled)."""

    def test_no_loader_created(self):
        """Test that no loader is created when predefined_variables=None."""
        tm = TemplateManager(
            default_template="Hello {{name}}",
        )
        assert tm._variable_loader is None
        assert tm._static_predefined_vars is None

    def test_no_loader_when_false(self):
        """Test that no loader is created when predefined_variables=False."""
        tm = TemplateManager(
            default_template="Hello {{name}}",
            predefined_variables=False,
        )
        assert tm._variable_loader is None
        assert tm._static_predefined_vars is None


class TestSkipPredefined:
    """Tests for skip_predefined parameter in __call__."""

    def test_skip_predefined_true(self):
        """Test that skip_predefined=True disables variable resolution."""
        static_vars = {"name": "Predefined Name"}
        tm = TemplateManager(
            default_template="Hello {{name}}",
            predefined_variables=static_vars,
        )
        # Without skip: should use predefined
        result_with = tm()
        assert "Predefined Name" in result_with

        # With skip: predefined not applied, variable stays as-is (or empty if Jinja2)
        result_skip = tm(skip_predefined=True)
        # Jinja2 raises or leaves empty for undefined
        assert "Predefined Name" not in result_skip

    def test_skip_predefined_kwargs_still_work(self):
        """Test that kwargs still work even when skip_predefined=True."""
        static_vars = {"greeting": "Hello"}
        tm = TemplateManager(
            default_template="{{greeting}}, {{name}}!",
            predefined_variables=static_vars,
        )
        result = tm(skip_predefined=True, greeting="Hi", name="Alice")
        assert result == "Hi, Alice!"


class TestSwitchPredefinedVariables:
    """Tests for switch() method with predefined_variables."""

    def test_switch_copies_predefined_by_default(self):
        """Test that switch() copies predefined_variables by default."""
        static_vars = {"header": "Header"}
        tm = TemplateManager(
            default_template="{{header}} - {{name}}",
            predefined_variables=static_vars,
        )
        tm2 = tm.switch(active_template_type="reflection")
        assert tm2._static_predefined_vars == static_vars

    def test_switch_can_override_to_true(self, fixtures_dir):
        """Test that switch() can change predefined_variables to True."""
        tm = TemplateManager(
            templates=str(fixtures_dir),
            predefined_variables=None,  # Start without predefined
        )
        assert tm._variable_loader is None

        tm2 = tm.switch(predefined_variables=True)
        assert tm2._variable_loader is not None

    def test_switch_can_override_to_mapping(self):
        """Test that switch() can change predefined_variables to a mapping."""
        tm = TemplateManager(
            default_template="{{header}} - {{name}}",
            predefined_variables=None,
        )
        assert tm._static_predefined_vars is None

        new_vars = {"header": "New Header"}
        tm2 = tm.switch(predefined_variables=new_vars)
        assert tm2._static_predefined_vars == new_vars

    def test_switch_can_disable_predefined(self):
        """Test that switch() can disable predefined_variables."""
        static_vars = {"header": "Header"}
        tm = TemplateManager(
            default_template="{{header}} - {{name}}",
            predefined_variables=static_vars,
        )
        assert tm._static_predefined_vars is not None

        tm2 = tm.switch(predefined_variables=False)
        assert tm2._variable_loader is None
        assert tm2._static_predefined_vars is None


class TestPredefinedVariablesWithVersion:
    """Tests for predefined_variables with template_version."""

    def test_version_passed_to_loader(self, tmp_path):
        """Test that template_version is passed to VariableLoader."""
        # Create a template structure with versioned variables
        (tmp_path / "main").mkdir()
        (tmp_path / "main" / "default.j2").write_text("Tier: {{notes_tier}}")

        vars_dir = tmp_path / "_variables" / "notes"
        vars_dir.mkdir(parents=True)
        (vars_dir / "tier.hbs").write_text("STANDARD tier")
        (vars_dir / "tier.enterprise.hbs").write_text("ENTERPRISE tier")

        tm = TemplateManager(
            templates=str(tmp_path),
            predefined_variables=True,
            template_version="enterprise",
            active_template_type="main",
        )
        result = tm()
        # Enterprise version should be used
        assert "ENTERPRISE tier" in result


class TestInvalidPredefinedVariables:
    """Tests for invalid predefined_variables values."""

    def test_invalid_type_raises_error(self):
        """Test that invalid predefined_variables type raises ValueError."""
        with pytest.raises(ValueError, match="must be True, False, None"):
            TemplateManager(
                default_template="Hello",
                predefined_variables=123,  # Invalid type
            )

    def test_invalid_type_in_switch_raises_error(self):
        """Test that invalid predefined_variables in switch() raises ValueError."""
        tm = TemplateManager(default_template="Hello")
        with pytest.raises(ValueError, match="must be True, False, None"):
            tm.switch(predefined_variables="invalid")
