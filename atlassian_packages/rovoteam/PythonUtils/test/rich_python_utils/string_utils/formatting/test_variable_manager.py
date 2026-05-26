"""Tests for VariableLoader and related classes."""

import pytest
from pathlib import Path

from python_utils.string_utils.formatting.template_manager import (
    AmbiguousVariableError,
    CircularReferenceError,
    MaxDepthExceededError,
    VariableLoader,
    VariableLoaderConfig,
)


@pytest.fixture
def fixtures_dir():
    """Return the path to the fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def loader(fixtures_dir):
    """Create a VariableLoader with default config."""
    return VariableLoader(template_dir=str(fixtures_dir))


@pytest.fixture
def loader_with_overrides(fixtures_dir):
    """Create a VariableLoader with overrides enabled."""
    config = VariableLoaderConfig(enable_overrides=True)
    return VariableLoader(template_dir=str(fixtures_dir), config=config)


class TestVariableLoaderInit:
    """Tests for VariableLoader initialization."""

    def test_init_with_default_config(self, fixtures_dir):
        """Test initialization with default config."""
        loader = VariableLoader(template_dir=str(fixtures_dir))
        assert loader.config.enable_overrides is False
        assert loader.config.cache_content is True
        assert loader.config.max_recursion_depth == 50

    def test_init_with_custom_config(self, fixtures_dir):
        """Test initialization with custom config."""
        config = VariableLoaderConfig(
            enable_overrides=True,
            cache_content=False,
            max_recursion_depth=10,
        )
        loader = VariableLoader(template_dir=str(fixtures_dir), config=config)
        assert loader.config.enable_overrides is True
        assert loader.config.cache_content is False
        assert loader.config.max_recursion_depth == 10


class TestUnderscoreSplits:
    """Tests for underscore split inference."""

    def test_no_underscore(self, loader):
        """Test that names without underscores generate only flat path."""
        splits = loader._generate_underscore_splits("mindset")
        assert splits == ["mindset"]

    def test_single_underscore(self, loader):
        """Test that single underscore generates two paths."""
        splits = loader._generate_underscore_splits("notes_mindset")
        assert "notes/mindset" in splits
        assert "notes_mindset" in splits
        assert len(splits) == 2

    def test_multiple_underscores(self, loader):
        """Test that multiple underscores generate all possible splits."""
        splits = loader._generate_underscore_splits("my_app_settings")
        assert "my/app_settings" in splits
        assert "my_app/settings" in splits
        assert "my_app_settings" in splits
        assert len(splits) == 3


class TestBasicResolution:
    """Tests for basic variable resolution."""

    def test_resolve_global_variable(self, loader):
        """Test resolving a variable from global _variables."""
        template = "{{notes_mindset}}"
        variables = loader.resolve_from_template(
            template, template_root_space="unknown_agent", template_type="main"
        )
        assert "notes_mindset" in variables
        assert "Global mindset content" in variables["notes_mindset"]

    def test_resolve_cascade_agent_level(self, loader):
        """Test cascade resolution uses agent-level when available."""
        template = "{{notes_mindset}}"
        variables = loader.resolve_from_template(
            template, template_root_space="action_agent", template_type="main"
        )
        assert "notes_mindset" in variables
        # Agent-level should take precedence over global
        assert "AGENT-LEVEL" in variables["notes_mindset"]

    def test_resolve_cascade_template_type_level(self, loader):
        """Test cascade resolution uses template-type level when available."""
        template = "{{notes_local}}"
        variables = loader.resolve_from_template(
            template, template_root_space="action_agent", template_type="main"
        )
        assert "notes_local" in variables
        assert "TEMPLATE-TYPE level" in variables["notes_local"]

    def test_unresolved_variable_not_in_dict(self, loader):
        """Test that variables without files are not in the result dict."""
        template = "{{unknown_variable}}"
        variables = loader.resolve_from_template(
            template, template_root_space="action_agent", template_type="main"
        )
        assert "unknown_variable" not in variables

    def test_multiple_variables(self, loader):
        """Test resolving multiple variables from template."""
        template = "{{notes_mindset}} and {{notes_clarification}}"
        variables = loader.resolve_from_template(
            template, template_root_space="action_agent", template_type="main"
        )
        assert "notes_mindset" in variables
        assert "notes_clarification" in variables


class TestScopeModifiers:
    """Tests for scope modifiers (^, ., ?)."""

    def test_global_scope_modifier(self, loader):
        """Test ^ modifier forces global scope."""
        template = "^{{notes_mindset}}"
        variables = loader.resolve_from_template(
            template, template_root_space="action_agent", template_type="main"
        )
        assert "notes_mindset" in variables
        # Should get global, not agent-level
        assert "Global mindset content" in variables["notes_mindset"]
        assert "AGENT-LEVEL" not in variables["notes_mindset"]

    def test_current_level_scope_modifier(self, loader):
        """Test . modifier forces current level scope."""
        template = ".{{notes_current_level}}"
        variables = loader.resolve_from_template(
            template, template_root_space="action_agent", template_type="main"
        )
        assert "notes_current_level" in variables
        # Should get template-type level
        assert "current level only" in variables["notes_current_level"]

    def test_current_level_scope_not_found(self, loader):
        """Test . modifier when variable doesn't exist at current level."""
        # notes_mindset exists at agent and global level, but not at template-type level
        template = ".{{notes_mindset}}"
        variables = loader.resolve_from_template(
            template, template_root_space="action_agent", template_type="main"
        )
        # Should NOT be found (. restricts to current level only)
        assert "notes_mindset" not in variables

    def test_optional_modifier_when_exists(self, loader):
        """Test ? modifier with existing variable."""
        template = "{{notes_mindset}}?"
        variables = loader.resolve_from_template(
            template, template_root_space="action_agent", template_type="main"
        )
        assert "notes_mindset" in variables

    def test_optional_modifier_when_not_exists(self, loader):
        """Test ? modifier with non-existing variable returns empty string."""
        template = "{{nonexistent_var}}?"
        variables = loader.resolve_from_template(
            template, template_root_space="action_agent", template_type="main"
        )
        # Optional non-existent should be in dict with empty string
        assert "nonexistent_var" in variables
        assert variables["nonexistent_var"] == ""

    def test_combined_global_optional_modifier(self, loader):
        """Test combined ^...? modifiers."""
        template = "^{{notes_mindset}}?"
        variables = loader.resolve_from_template(
            template, template_root_space="action_agent", template_type="main"
        )
        assert "notes_mindset" in variables
        assert "Global mindset content" in variables["notes_mindset"]

    def test_combined_current_level_optional_modifier(self, loader):
        """Test combined ....? modifiers."""
        template = ".{{nonexistent_at_level}}?"
        variables = loader.resolve_from_template(
            template, template_root_space="action_agent", template_type="main"
        )
        # Optional and not found at current level should be empty string
        assert "nonexistent_at_level" in variables
        assert variables["nonexistent_at_level"] == ""


class TestVersionResolution:
    """Tests for version resolution."""

    def test_default_version(self, loader):
        """Test resolving without version uses base file."""
        template = "{{notes_mindset}}"
        variables = loader.resolve_from_template(
            template, template_root_space="unknown_agent", template_type="main"
        )
        assert "notes_mindset" in variables
        assert "BASE version" in variables["notes_mindset"]

    def test_enterprise_version(self, loader):
        """Test resolving with enterprise version."""
        template = "{{notes_mindset}}"
        variables = loader.resolve_from_template(
            template, template_root_space="unknown_agent", template_type="main", version="enterprise"
        )
        assert "notes_mindset" in variables
        assert "ENTERPRISE version" in variables["notes_mindset"]

    def test_override_with_overrides_disabled(self, loader):
        """Test that override files are ignored when disabled."""
        template = "{{notes_mindset}}"
        variables = loader.resolve_from_template(
            template, template_root_space="unknown_agent", template_type="main"
        )
        # Should use base version
        assert "BASE version" in variables["notes_mindset"]

    def test_override_with_overrides_enabled(self, loader_with_overrides):
        """Test that override files are used when enabled."""
        template = "{{notes_mindset}}"
        variables = loader_with_overrides.resolve_from_template(
            template, template_root_space="unknown_agent", template_type="main"
        )
        # Should use override file content
        assert "notes_mindset" in variables
        assert "GLOBAL MINDSET OVERRIDE" in variables["notes_mindset"]


class TestComposition:
    """Tests for variable-to-variable composition."""

    def test_simple_composition(self, loader):
        """Test variable that references another variable."""
        template = "{{notes_composed}}"
        variables = loader.resolve_from_template(
            template, template_root_space="unknown_agent", template_type="main"
        )
        assert "notes_composed" in variables
        # Should have resolved the nested {{notes_mindset}} reference
        content = variables["notes_composed"]
        assert "Composed notes" in content
        assert "Global mindset content" in content

    def test_global_scope_in_composition(self, loader):
        """Test composition with ^ modifier in variable file."""
        template = "{{notes_global_only_composed}}"
        variables = loader.resolve_from_template(
            template, template_root_space="action_agent", template_type="main"
        )
        assert "notes_global_only_composed" in variables
        content = variables["notes_global_only_composed"]
        # Should use global mindset despite agent-level existing
        assert "Global mindset content" in content
        assert "AGENT-LEVEL" not in content

    def test_optional_in_composition(self, loader):
        """Test composition with optional (?) variable."""
        template = "{{notes_composed}}"
        variables = loader.resolve_from_template(
            template, template_root_space="unknown_agent", template_type="main"
        )
        # notes_composed references {{notes_clarification}}? which should be resolved
        assert "notes_composed" in variables
        content = variables["notes_composed"]
        # The optional reference should be resolved (not left as template var)
        assert "{{notes_clarification}}" not in content

    def test_current_level_scope_in_composition(self, loader):
        """Test . modifier in composition is relative to variable file's level."""
        template = "{{notes_current_level_composed}}"
        variables = loader.resolve_from_template(
            template, template_root_space="action_agent", template_type="main"
        )
        assert "notes_current_level_composed" in variables
        content = variables["notes_current_level_composed"]
        # The .{{notes_current_level}} should be resolved from same level as the file
        assert "current level only" in content
        # The ^{{notes_mindset}} should use global
        assert "Global mindset content" in content


class TestCircularReference:
    """Tests for circular reference detection."""

    def test_circular_reference_error(self, loader):
        """Test that circular references raise error."""
        template = "{{notes_circular_a}}"
        with pytest.raises(CircularReferenceError) as excinfo:
            loader.resolve_from_template(
                template, template_root_space="unknown_agent", template_type="main"
            )
        assert "notes_circular_a" in str(excinfo.value)
        assert "notes_circular_b" in str(excinfo.value)


class TestAmbiguousVariable:
    """Tests for ambiguous variable detection."""

    @pytest.fixture
    def ambiguous_fixtures_dir(self):
        """Return the path to the ambiguous fixtures directory."""
        return Path(__file__).parent / "fixtures_ambiguous"

    def test_nested_path_wins_over_flat_file(self, ambiguous_fixtures_dir):
        """Test that nested path takes priority over flat file (no ambiguity error).

        With 3-phase resolution and underscore-to-slash splitting,
        ambig/test.hbs (deeper path) resolves before ambig_test.hbs (flat file).
        """
        loader = VariableLoader(template_dir=str(ambiguous_fixtures_dir))
        template = "{{ambig_test}}"
        result = loader.resolve_from_template(
            template, template_root_space="test", template_type="main"
        )
        assert "Content from ambig/test.hbs" in result["ambig_test"]


class TestMaxDepth:
    """Tests for max recursion depth."""

    def test_max_depth_config(self, fixtures_dir):
        """Test that max depth is configurable."""
        config = VariableLoaderConfig(max_recursion_depth=2)
        loader = VariableLoader(template_dir=str(fixtures_dir), config=config)
        # This should work at depth 2
        template = "{{notes_mindset}}"
        variables = loader.resolve_from_template(
            template, template_root_space="unknown_agent", template_type="main"
        )
        assert "notes_mindset" in variables


class TestHandlebarsPartials:
    """Tests for Handlebars partial handling."""

    def test_skip_handlebars_partials(self, loader):
        """Test that Handlebars partials ({{> name}}) are skipped."""
        template = "{{> some_partial}} and {{notes_mindset}}"
        variables = loader.resolve_from_template(
            template, template_root_space="action_agent", template_type="main"
        )
        # Partial should be skipped
        assert "> some_partial" not in variables
        # Normal variable should be resolved
        assert "notes_mindset" in variables


class TestWhitespace:
    """Tests for whitespace handling."""

    def test_whitespace_in_variable_name(self, loader):
        """Test that whitespace is trimmed from variable names."""
        template = "{{ notes_mindset }}"  # Jinja2 style with spaces
        variables = loader.resolve_from_template(
            template, template_root_space="action_agent", template_type="main"
        )
        assert "notes_mindset" in variables


class TestCache:
    """Tests for caching behavior."""

    def test_clear_cache(self, loader, fixtures_dir):
        """Test clearing the content cache."""
        # Resolve something to populate cache
        loader.resolve_from_template(
            "{{notes_mindset}}", template_root_space="action_agent", template_type="main"
        )
        assert len(loader._content_cache) > 0

        # Clear and verify
        loader.clear_cache()
        assert len(loader._content_cache) == 0

    def test_reload(self, loader, fixtures_dir):
        """Test reload clears cache."""
        # Populate cache
        loader.resolve_from_template(
            "{{notes_mindset}}", template_root_space="action_agent", template_type="main"
        )
        assert len(loader._content_cache) > 0

        # Reload
        loader.reload()

        # Cache should be cleared
        assert len(loader._content_cache) == 0


class TestEmptyFile:
    """Tests for empty file handling."""

    def test_empty_file_returns_empty_string(self, fixtures_dir, tmp_path):
        """Test that empty files return empty string (not None)."""
        # Create a temp directory structure with an empty file
        vars_dir = tmp_path / "_variables"
        vars_dir.mkdir()
        empty_file = vars_dir / "empty.hbs"
        empty_file.write_text("")

        loader = VariableLoader(template_dir=str(tmp_path))
        template = "{{empty}}"
        variables = loader.resolve_from_template(
            template, template_root_space="test", template_type="main"
        )
        assert "empty" in variables
        assert variables["empty"] == ""


class TestDuplicateVariables:
    """Tests for duplicate variable handling."""

    def test_same_variable_resolved_once(self, loader):
        """Test that the same variable appearing multiple times is resolved once."""
        template = "{{notes_mindset}} and again {{notes_mindset}}"
        variables = loader.resolve_from_template(
            template, template_root_space="action_agent", template_type="main"
        )
        # Should only have one entry
        assert list(variables.keys()).count("notes_mindset") == 1
