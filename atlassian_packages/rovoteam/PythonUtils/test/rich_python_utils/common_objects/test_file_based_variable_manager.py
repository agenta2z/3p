"""Tests for FileBasedVariableManager and related classes."""

import unittest
from pathlib import Path

import pytest
from python_utils.common_objects.variable_manager import (
    AmbiguousVariableError,
    CircularReferenceError,
    FileBasedVariableManager,
    KeyDiscoveryMode,
    VariableManagerConfig,
    VariableSyntax,
)


@pytest.fixture
def mock_dir(tmp_path):
    """Create a mock variables directory structure."""
    # Global variables
    (tmp_path / "database_host.txt").write_text("localhost")
    (tmp_path / "database_port.txt").write_text("5432")
    (tmp_path / "database.txt").write_text("mydb")
    (tmp_path / "greeting.txt").write_text("Hello from global")
    (tmp_path / "connection_string.txt").write_text(
        "postgresql://{{database_host}}:{{database_port}}/{{database}}"
    )

    # Production space
    prod_dir = tmp_path / "production"
    prod_dir.mkdir()
    (prod_dir / "database_host.txt").write_text("prod-db.example.com")
    (prod_dir / "database_port.txt").write_text("5433")

    # Production/api type
    api_dir = prod_dir / "api"
    api_dir.mkdir()
    (api_dir / "database_host.txt").write_text("prod-api-db.example.com")

    # Staging space
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    (staging_dir / "database_host.txt").write_text("staging-db.example.com")

    # Version files
    (tmp_path / "api_url.txt").write_text("http://localhost:8000")
    (tmp_path / "api_url.production.txt").write_text("https://api.example.com")
    (tmp_path / "api_url.override.txt").write_text("http://localhost:9000")

    # Circular references
    circular_dir = tmp_path / "circular"
    circular_dir.mkdir()
    (circular_dir / "a.txt").write_text("A references {{circular_b}}")
    (circular_dir / "b.txt").write_text("B references {{circular_a}}")

    # Config subdirectory
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "timeout.txt").write_text("30")
    (config_dir / "retries.txt").write_text("3")

    return tmp_path


class TestBasicAccess:
    """Tests for basic dict-like access."""

    def test_getitem(self, mock_dir):
        """Test manager['key'] access."""
        manager = FileBasedVariableManager(base_path=str(mock_dir))
        assert manager["database_host"] == "localhost"
        assert manager["database_port"] == "5432"

    def test_get_with_default(self, mock_dir):
        """Test manager.get('key', default) access."""
        manager = FileBasedVariableManager(base_path=str(mock_dir))
        assert manager.get("database_host") == "localhost"
        assert manager.get("missing", "default") == "default"

    def test_contains(self, mock_dir):
        """Test 'key' in manager."""
        manager = FileBasedVariableManager(
            base_path=str(mock_dir), key_discovery_mode=KeyDiscoveryMode.EAGER
        )
        assert "database_host" in manager
        assert "missing_key" not in manager

    def test_len(self, mock_dir):
        """Test len(manager)."""
        manager = FileBasedVariableManager(
            base_path=str(mock_dir), key_discovery_mode=KeyDiscoveryMode.EAGER
        )
        assert len(manager) > 0

    def test_iteration(self, mock_dir):
        """Test iteration over keys."""
        manager = FileBasedVariableManager(
            base_path=str(mock_dir), key_discovery_mode=KeyDiscoveryMode.EAGER
        )
        keys = list(manager)
        assert "database_host" in keys

    def test_underscore_split_inference(self, mock_dir):
        """Test that config_timeout resolves to config/timeout.txt."""
        manager = FileBasedVariableManager(base_path=str(mock_dir))
        assert manager["config_timeout"] == "30"
        assert manager["config_retries"] == "3"


class TestClassLevelCascade:
    """Tests for class-level cascade configuration."""

    def test_no_cascade_by_default(self, mock_dir):
        """Test that default manager uses global only."""
        manager = FileBasedVariableManager(base_path=str(mock_dir))
        assert manager["database_host"] == "localhost"

    def test_class_level_variable_root_space(self, mock_dir):
        """Test class-level variable_root_space."""
        manager = FileBasedVariableManager(
            base_path=str(mock_dir),
            variable_root_space="production",
        )
        assert manager["database_host"] == "prod-db.example.com"
        assert manager["database_port"] == "5433"

    def test_class_level_variable_type(self, mock_dir):
        """Test class-level variable_type."""
        manager = FileBasedVariableManager(
            base_path=str(mock_dir),
            variable_root_space="production",
            variable_type="api",
        )
        assert manager["database_host"] == "prod-api-db.example.com"
        # Falls back to space level
        assert manager["database_port"] == "5433"

    def test_class_cascade_used_by_get(self, mock_dir):
        """Test that get() uses class-level cascade."""
        manager = FileBasedVariableManager(
            base_path=str(mock_dir),
            variable_root_space="production",
        )
        assert manager.get("database_host") == "prod-db.example.com"


class TestCascadeParameter:
    """Tests for cascade parameter in get()."""

    def test_cascade_false_ignores_class_settings(self, mock_dir):
        """Test cascade=False returns global value."""
        manager = FileBasedVariableManager(
            base_path=str(mock_dir),
            variable_root_space="production",
        )
        assert manager.get("database_host", cascade=False) == "localhost"

    def test_cascade_true_uses_class_settings(self, mock_dir):
        """Test cascade=True uses class-level settings."""
        manager = FileBasedVariableManager(
            base_path=str(mock_dir),
            variable_root_space="production",
        )
        assert manager.get("database_host", cascade=True) == "prod-db.example.com"

    def test_override_variable_root_space(self, mock_dir):
        """Test overriding class-level space."""
        manager = FileBasedVariableManager(
            base_path=str(mock_dir),
            variable_root_space="production",
        )
        # Override to staging
        assert (
            manager.get("database_host", variable_root_space="staging")
            == "staging-db.example.com"
        )

    def test_override_variable_type(self, mock_dir):
        """Test overriding class-level type."""
        manager = FileBasedVariableManager(
            base_path=str(mock_dir),
            variable_root_space="production",
        )
        # Override to add type
        assert (
            manager.get("database_host", variable_type="api")
            == "prod-api-db.example.com"
        )


class TestComposeOnAccess:
    """Tests for compose_on_access config and compose parameter."""

    def test_compose_on_access_default_true(self, mock_dir):
        """Test that compose_on_access defaults to True."""
        manager = FileBasedVariableManager(base_path=str(mock_dir))
        result = manager["connection_string"]
        assert result == "postgresql://localhost:5432/mydb"

    def test_compose_on_access_false(self, mock_dir):
        """Test compose_on_access=False returns raw content."""
        config = VariableManagerConfig(compose_on_access=False)
        manager = FileBasedVariableManager(base_path=str(mock_dir), config=config)
        result = manager["connection_string"]
        assert "{{database_host}}" in result

    def test_compose_parameter_false(self, mock_dir):
        """Test compose=False returns raw content."""
        manager = FileBasedVariableManager(base_path=str(mock_dir))
        result = manager.get("connection_string", compose=False)
        assert "{{database_host}}" in result

    def test_compose_parameter_true(self, mock_dir):
        """Test compose=True resolves variables."""
        manager = FileBasedVariableManager(base_path=str(mock_dir))
        result = manager.get("connection_string", compose=True)
        assert result == "postgresql://localhost:5432/mydb"

    def test_compose_override_config(self, mock_dir):
        """Test compose parameter overrides config."""
        config = VariableManagerConfig(compose_on_access=False)
        manager = FileBasedVariableManager(base_path=str(mock_dir), config=config)
        # Config says no compose, but parameter overrides
        result = manager.get("connection_string", compose=True)
        assert result == "postgresql://localhost:5432/mydb"

    def test_compose_with_cascade(self, mock_dir):
        """Test composition uses cascade settings."""
        manager = FileBasedVariableManager(
            base_path=str(mock_dir),
            variable_root_space="production",
        )
        result = manager["connection_string"]
        assert "prod-db.example.com" in result
        assert "5433" in result


class TestGetVariable:
    """Tests for get_variable() method."""

    def test_get_variable_basic(self, mock_dir):
        """Test get_variable returns content."""
        manager = FileBasedVariableManager(base_path=str(mock_dir))
        assert manager.get_variable("database_host") == "localhost"

    def test_get_variable_not_found(self, mock_dir):
        """Test get_variable returns None for missing."""
        manager = FileBasedVariableManager(base_path=str(mock_dir))
        assert manager.get_variable("missing") is None

    def test_get_variable_with_cascade(self, mock_dir):
        """Test get_variable with cascade parameters."""
        manager = FileBasedVariableManager(base_path=str(mock_dir))
        result = manager.get_variable(
            "database_host",
            variable_root_space="production",
        )
        assert result == "prod-db.example.com"

    def test_get_variable_compose_false(self, mock_dir):
        """Test get_variable with compose=False."""
        manager = FileBasedVariableManager(base_path=str(mock_dir))
        result = manager.get_variable("connection_string", compose=False)
        assert "{{database_host}}" in result


class TestResolveFromContent:
    """Tests for resolve_from_content() method."""

    def test_resolve_single_variable(self, mock_dir):
        """Test resolving a single variable."""
        manager = FileBasedVariableManager(base_path=str(mock_dir))
        result = manager.resolve_from_content("{{database_host}}")
        assert result["database_host"] == "localhost"

    def test_resolve_multiple_variables(self, mock_dir):
        """Test resolving multiple variables."""
        manager = FileBasedVariableManager(base_path=str(mock_dir))
        result = manager.resolve_from_content("{{database_host}} {{database_port}}")
        assert result["database_host"] == "localhost"
        assert result["database_port"] == "5432"

    def test_resolve_with_cascade(self, mock_dir):
        """Test resolving with cascade parameters."""
        manager = FileBasedVariableManager(base_path=str(mock_dir))
        result = manager.resolve_from_content(
            "{{database_host}}",
            variable_root_space="production",
        )
        assert result["database_host"] == "prod-db.example.com"

    def test_resolve_composition(self, mock_dir):
        """Test that resolved variables are composed."""
        manager = FileBasedVariableManager(base_path=str(mock_dir))
        result = manager.resolve_from_content("{{connection_string}}")
        assert result["connection_string"] == "postgresql://localhost:5432/mydb"


class TestVersionAndOverrides:
    """Tests for version and override functionality."""

    def test_version_resolution(self, mock_dir):
        """Test version suffix resolution."""
        manager = FileBasedVariableManager(base_path=str(mock_dir))
        result = manager.resolve_from_content(
            "{{api_url}}",
            version="production",
        )
        assert result["api_url"] == "https://api.example.com"

    def test_override_disabled_by_default(self, mock_dir):
        """Test overrides are disabled by default."""
        manager = FileBasedVariableManager(base_path=str(mock_dir))
        result = manager.resolve_from_content("{{api_url}}")
        assert result["api_url"] == "http://localhost:8000"

    def test_override_enabled(self, mock_dir):
        """Test overrides when enabled."""
        config = VariableManagerConfig(enable_overrides=True)
        manager = FileBasedVariableManager(base_path=str(mock_dir), config=config)
        result = manager.resolve_from_content("{{api_url}}")
        assert result["api_url"] == "http://localhost:9000"


class TestCircularReferenceDetection:
    """Tests for circular reference detection."""

    def test_circular_reference_raises_error(self, mock_dir):
        """Test that circular references raise CircularReferenceError."""
        manager = FileBasedVariableManager(base_path=str(mock_dir))
        with pytest.raises(CircularReferenceError) as excinfo:
            manager.resolve_from_content("{{circular_a}}")
        assert "circular_a" in str(excinfo.value)
        assert "circular_b" in str(excinfo.value)


class TestVariableSyntax:
    """Tests for different variable syntax options."""

    def test_handlebars_syntax(self, tmp_path):
        """Test HANDLEBARS syntax."""
        (tmp_path / "greeting.txt").write_text("Hello")
        (tmp_path / "message.hbs").write_text("{{greeting}}, World!")

        manager = FileBasedVariableManager(base_path=str(tmp_path))
        result = manager.resolve_from_content("{{message}}")
        assert result["message"] == "Hello, World!"

    def test_python_format_syntax(self, tmp_path):
        """Test PYTHON_FORMAT syntax."""
        (tmp_path / "greeting.txt").write_text("Hello")
        (tmp_path / "message.py").write_text("{greeting}, World!")

        config = VariableManagerConfig(
            variable_syntax=VariableSyntax.PYTHON_FORMAT,
            file_extensions=[".py", ".txt", ""],
        )
        manager = FileBasedVariableManager(base_path=str(tmp_path), config=config)
        result = manager.resolve_from_content("{message}")
        assert result["message"] == "Hello, World!"

    def test_template_syntax(self, tmp_path):
        """Test TEMPLATE syntax."""
        (tmp_path / "greeting.txt").write_text("Hello")
        (tmp_path / "message.tpl").write_text("$greeting, World!")

        config = VariableManagerConfig(
            variable_syntax=VariableSyntax.TEMPLATE,
            file_extensions=[".tpl", ".txt", ""],
        )
        manager = FileBasedVariableManager(base_path=str(tmp_path), config=config)
        result = manager.resolve_from_content("$message")
        assert result["message"] == "Hello, World!"

    def test_pure_text_mode(self, tmp_path):
        """Test pure text mode (no composition)."""
        (tmp_path / "greeting.txt").write_text("Hello")
        (tmp_path / "message.txt").write_text("{{greeting}}, World!")

        config = VariableManagerConfig(variable_syntax=None)
        manager = FileBasedVariableManager(base_path=str(tmp_path), config=config)
        # No composition - raw content
        assert manager["message"] == "{{greeting}}, World!"


class TestCacheAndReload:
    """Tests for caching functionality."""

    def test_clear_cache(self, mock_dir):
        """Test clearing the content cache."""
        manager = FileBasedVariableManager(base_path=str(mock_dir))
        _ = manager["database_host"]
        assert len(manager._content_cache) > 0

        manager.clear_cache()
        assert len(manager._content_cache) == 0

    def test_reload(self, mock_dir):
        """Test reload clears cache and discovered keys."""
        manager = FileBasedVariableManager(
            base_path=str(mock_dir), key_discovery_mode=KeyDiscoveryMode.EAGER
        )
        _ = manager["database_host"]
        assert len(manager._content_cache) > 0
        assert manager._discovered_keys is not None

        manager.reload()
        assert len(manager._content_cache) == 0
        assert manager._discovered_keys is None


class TestKeyDiscoveryMode:
    """Tests for key discovery modes."""

    def test_lazy_mode_default(self, mock_dir):
        """Test lazy mode is default."""
        manager = FileBasedVariableManager(base_path=str(mock_dir))
        assert manager._discovered_keys is None

    def test_eager_mode_discovers_immediately(self, mock_dir):
        """Test eager mode discovers keys on init."""
        manager = FileBasedVariableManager(
            base_path=str(mock_dir), key_discovery_mode=KeyDiscoveryMode.EAGER
        )
        assert manager._discovered_keys is not None
        assert len(manager._discovered_keys) > 0

    def test_lazy_mode_discovers_on_iteration(self, mock_dir):
        """Test lazy mode discovers keys when needed."""
        manager = FileBasedVariableManager(base_path=str(mock_dir))
        assert manager._discovered_keys is None
        _ = list(manager)  # Trigger discovery
        assert manager._discovered_keys is not None


class TestFolderBasedResolution(unittest.TestCase):
    """Tests for subfolder-based variable resolution."""

    def _make_dir(self):
        import tempfile

        d = tempfile.mkdtemp()
        self._tmp_dirs.append(d)
        return Path(d)

    def setUp(self):
        self._tmp_dirs = []

    def tearDown(self):
        import shutil

        for d in self._tmp_dirs:
            shutil.rmtree(d, ignore_errors=True)

    def test_config_yaml_default(self):
        """Folder with .config.yaml pointing to 'modeling' resolves modeling.jinja2."""
        tmp = self._make_dir()
        folder = tmp / "task_preamble" / "v1"
        folder.mkdir(parents=True)
        (folder / ".config.yaml").write_text("default: modeling")
        (folder / "modeling.txt").write_text("ML opportunities")
        (folder / "generic.txt").write_text("Generic opportunities")

        manager = FileBasedVariableManager(base_path=str(tmp))
        result = manager.resolve_from_content("{{task_preamble}}", version="v1")
        self.assertEqual(result["task_preamble"], "ML opportunities")

    def test_default_file_wins_over_config(self):
        """default.jinja2 takes priority over .config.yaml."""
        tmp = self._make_dir()
        folder = tmp / "my_var" / "v1"
        folder.mkdir(parents=True)
        (folder / "default.txt").write_text("default content")
        (folder / ".config.yaml").write_text("default: other")
        (folder / "other.txt").write_text("other content")

        manager = FileBasedVariableManager(base_path=str(tmp))
        result = manager.resolve_from_content("{{my_var}}", version="v1")
        self.assertEqual(result["my_var"], "default content")

    def test_single_file_folder(self):
        """Folder with exactly one content file resolves without config."""
        tmp = self._make_dir()
        folder = tmp / "my_var" / "v1"
        folder.mkdir(parents=True)
        (folder / "only.txt").write_text("only content")

        manager = FileBasedVariableManager(base_path=str(tmp))
        result = manager.resolve_from_content("{{my_var}}", version="v1")
        self.assertEqual(result["my_var"], "only content")

    def test_ambiguous_folder_raises_error(self):
        """Folder with 2+ files and no default raises AmbiguousVariableError."""
        tmp = self._make_dir()
        folder = tmp / "my_var" / "v1"
        folder.mkdir(parents=True)
        (folder / "a.txt").write_text("A")
        (folder / "b.txt").write_text("B")

        manager = FileBasedVariableManager(base_path=str(tmp))
        with self.assertRaises(AmbiguousVariableError):
            manager.resolve_from_content("{{my_var}}", version="v1")

    def test_empty_folder_falls_through(self):
        """Empty folder falls through to unversioned file."""
        tmp = self._make_dir()
        folder = tmp / "my_var" / "v1"
        folder.mkdir(parents=True)
        (tmp / "my_var.txt").write_text("unversioned")

        manager = FileBasedVariableManager(base_path=str(tmp))
        result = manager.resolve_from_content("{{my_var}}", version="v1")
        self.assertEqual(result["my_var"], "unversioned")

    def test_folder_wins_over_unversioned_file(self):
        """Versioned folder takes priority over unversioned flat file."""
        tmp = self._make_dir()
        folder = tmp / "my_var" / "v1"
        folder.mkdir(parents=True)
        (folder / "default.txt").write_text("folder content")
        (tmp / "my_var.txt").write_text("unversioned fallback")

        manager = FileBasedVariableManager(base_path=str(tmp))
        result = manager.resolve_from_content("{{my_var}}", version="v1")
        self.assertEqual(result["my_var"], "folder content")

    def test_file_wins_over_folder(self):
        """Versioned flat file takes priority over folder."""
        tmp = self._make_dir()
        (tmp / "my_var.v1.txt").write_text("flat file wins")
        folder = tmp / "my_var" / "v1"
        folder.mkdir(parents=True)
        (folder / "default.txt").write_text("folder content")

        manager = FileBasedVariableManager(base_path=str(tmp))
        result = manager.resolve_from_content("{{my_var}}", version="v1")
        self.assertEqual(result["my_var"], "flat file wins")

    def test_no_version_ignores_folder(self):
        """Non-versioned resolution never triggers folder fallback."""
        tmp = self._make_dir()
        folder = tmp / "my_var" / "v1"
        folder.mkdir(parents=True)
        (folder / "default.txt").write_text("folder content")
        (tmp / "my_var.txt").write_text("global")

        manager = FileBasedVariableManager(base_path=str(tmp))
        result = manager.resolve_from_content("{{my_var}}")
        self.assertEqual(result["my_var"], "global")

    def test_underscore_split_folder(self):
        """Underscore-split path variant resolves via folder."""
        tmp = self._make_dir()
        folder = tmp / "task_preamble" / "uc"
        folder.mkdir(parents=True)
        (folder / ".config.yaml").write_text("default: modeling")
        (folder / "modeling.txt").write_text("modeling content")

        manager = FileBasedVariableManager(base_path=str(tmp))
        result = manager.resolve_from_content("{{task_preamble}}", version="uc")
        self.assertEqual(result["task_preamble"], "modeling content")

    def test_config_yaml_missing_target_file(self):
        """Config points to non-existent file, falls through to single-file."""
        tmp = self._make_dir()
        folder = tmp / "my_var" / "v1"
        folder.mkdir(parents=True)
        (folder / ".config.yaml").write_text("default: missing")
        (folder / "only.txt").write_text("only content")

        manager = FileBasedVariableManager(base_path=str(tmp))
        result = manager.resolve_from_content("{{my_var}}", version="v1")
        self.assertEqual(result["my_var"], "only content")

    def test_dotfiles_excluded_from_content_files(self):
        """Dotfiles like .config.yaml are not counted as content files."""
        tmp = self._make_dir()
        folder = tmp / "my_var" / "v1"
        folder.mkdir(parents=True)
        (folder / ".config.yaml").write_text("some: config")
        (folder / ".hidden").write_text("hidden")
        (folder / "only.txt").write_text("only content")

        manager = FileBasedVariableManager(base_path=str(tmp))
        result = manager.resolve_from_content("{{my_var}}", version="v1")
        self.assertEqual(result["my_var"], "only content")


# ============================================================
# Phase 1: Tests for Override/Sidecar/Alias API (current flat behavior)
# ============================================================


@pytest.fixture
def sidecar_dir(tmp_path):
    """Create a directory with a YAML sidecar file mimicking .initial.variables.yaml."""
    yaml_content = """\
employee:
  name: RankEvolve
  role: an AI scientist
  mindset:
    paradigm_shifting: |
      - Challenge every assumption
      - Survey state-of-the-art across adjacent fields
    incremental: |
      - Start with profiling and bottleneck analysis
      - Propose minimal, targeted changes

__alias__:
  strategy: employee.mindset
"""
    (tmp_path / ".initial.variables.yaml").write_text(yaml_content)
    return tmp_path


class TestOverrideAndAliasAPI:
    """Tests for the Override/Sidecar/Alias API (lines 976-1150 of file_based.py)."""

    def test_load_yaml_sidecar_basic(self, sidecar_dir):
        """Verify yaml data is loaded into _yaml_sidecar."""
        vm = FileBasedVariableManager(base_path=str(sidecar_dir))
        data = vm.load_yaml_sidecar(sidecar_dir / ".initial.variables.yaml")

        assert "employee" in data
        assert data["employee"]["name"] == "RankEvolve"
        assert "__alias__" not in data

    def test_load_yaml_sidecar_alias_extraction(self, sidecar_dir):
        """Verify __alias__ section extracted into _aliases dict."""
        vm = FileBasedVariableManager(base_path=str(sidecar_dir))
        vm.load_yaml_sidecar(sidecar_dir / ".initial.variables.yaml")

        assert vm.aliases == {"strategy": "employee.mindset"}

    def test_load_yaml_sidecar_nonexistent_file(self, sidecar_dir):
        """Nonexistent file returns empty dict."""
        vm = FileBasedVariableManager(base_path=str(sidecar_dir))
        data = vm.load_yaml_sidecar(sidecar_dir / "nonexistent.yaml")
        assert data == {}

    def test_set_with_alias_and_subkey(self, sidecar_dir):
        """set("strategy", "paradigm_shifting") resolves alias + sub-key selection."""
        vm = FileBasedVariableManager(base_path=str(sidecar_dir))
        vm.load_yaml_sidecar(sidecar_dir / ".initial.variables.yaml")

        vm.set("strategy", "paradigm_shifting")

        effective = vm.get_effective_value("strategy")
        assert "Challenge every assumption" in effective
        assert effective != "paradigm_shifting"

    def test_set_raw_value_when_not_subkey(self, sidecar_dir):
        """set("strategy", "custom text") stores raw value when not a sub-key."""
        vm = FileBasedVariableManager(base_path=str(sidecar_dir))
        vm.load_yaml_sidecar(sidecar_dir / ".initial.variables.yaml")

        vm.set("strategy", "My custom strategy text")

        effective = vm.get_effective_value("strategy")
        assert effective == "My custom strategy text"

    def test_set_override_false_guard(self, sidecar_dir):
        """set(key, value, override=False) raises KeyError if already set."""
        vm = FileBasedVariableManager(base_path=str(sidecar_dir))
        vm.load_yaml_sidecar(sidecar_dir / ".initial.variables.yaml")

        vm.set("strategy", "paradigm_shifting")
        with pytest.raises(KeyError):
            vm.set("strategy", "incremental", override=False)

    def test_get_effective_value_priority(self, sidecar_dir):
        """Resolution priority: overrides > yaml_sidecar."""
        vm = FileBasedVariableManager(base_path=str(sidecar_dir))
        vm.load_yaml_sidecar(sidecar_dir / ".initial.variables.yaml")

        assert vm.get_effective_value("employee")["name"] == "RankEvolve"

        vm.set("employee", {"name": "CustomName"})
        assert vm.get_effective_value("employee") == {"name": "CustomName"}

    def test_get_effective_value_default(self, sidecar_dir):
        """Returns default when key not found anywhere."""
        vm = FileBasedVariableManager(base_path=str(sidecar_dir))
        result = vm.get_effective_value("nonexistent", default="fallback")
        assert result == "fallback"

    def test_get_all_variables_merge(self, sidecar_dir):
        """get_all_variables() returns yaml_sidecar data."""
        vm = FileBasedVariableManager(base_path=str(sidecar_dir))
        vm.load_yaml_sidecar(sidecar_dir / ".initial.variables.yaml")

        all_vars = vm.get_all_variables()
        assert all_vars["employee"]["name"] == "RankEvolve"
        assert "paradigm_shifting" in all_vars["employee"]["mindset"]

    def test_get_all_variables_dot_path_override(self, sidecar_dir):
        """Override with dot-path merges correctly into nested structure."""
        vm = FileBasedVariableManager(base_path=str(sidecar_dir))
        vm.load_yaml_sidecar(sidecar_dir / ".initial.variables.yaml")

        vm.set("strategy", "paradigm_shifting")

        all_vars = vm.get_all_variables()
        assert isinstance(all_vars["employee"]["mindset"], str)
        assert "Challenge every assumption" in all_vars["employee"]["mindset"]
        assert all_vars["employee"]["name"] == "RankEvolve"

    def test_get_all_variables_returns_deep_copy(self, sidecar_dir):
        """Mutating returned dict does not affect internal state."""
        vm = FileBasedVariableManager(base_path=str(sidecar_dir))
        vm.load_yaml_sidecar(sidecar_dir / ".initial.variables.yaml")

        vars1 = vm.get_all_variables()
        vars1["employee"]["name"] = "MUTATED"
        vars2 = vm.get_all_variables()
        assert vars2["employee"]["name"] == "RankEvolve"

    def test_clear_specific_key(self, sidecar_dir):
        """clear() removes a single override, revealing yaml_sidecar value."""
        vm = FileBasedVariableManager(base_path=str(sidecar_dir))
        vm.load_yaml_sidecar(sidecar_dir / ".initial.variables.yaml")

        vm.set("strategy", "paradigm_shifting")
        assert isinstance(vm.get_effective_value("strategy"), str)

        vm.clear("strategy")
        result = vm.get_effective_value("strategy")
        assert isinstance(result, dict)


# ============================================================
# Phase 5: Tests for Scoped Override/Sidecar/Alias API
# ============================================================


@pytest.fixture
def multi_scope_dir(tmp_path):
    """Create directory with YAML sidecars for multiple scopes."""
    (tmp_path / ".variables.yaml").write_text("""\
app_name: GlobalApp
settings:
  debug: false
  timeout: 30

__alias__:
  mode: settings.debug
""")

    conv_dir = tmp_path / "conversation" / "main"
    conv_dir.mkdir(parents=True)
    (conv_dir / ".initial.variables.yaml").write_text("""\
employee:
  name: RankEvolve
  mindset:
    paradigm_shifting: |
      - Challenge every assumption
    incremental: |
      - Start with profiling

__alias__:
  strategy: employee.mindset
""")

    plan_dir = tmp_path / "plan" / "main"
    plan_dir.mkdir(parents=True)
    (plan_dir / ".initial.variables.yaml").write_text("""\
employee:
  name: PlanAgent
  mindset:
    aggressive: |
      - Move fast and break things
    conservative: |
      - Measure twice, cut once

__alias__:
  strategy: employee.mindset
""")

    return tmp_path


class TestScopedOverrideAndAlias:
    """Tests for the space-aware Override/Sidecar/Alias API."""

    def test_scoped_yaml_sidecar_isolation(self, multi_scope_dir):
        """Loading different yamls for different scopes — no collision."""
        vm = FileBasedVariableManager(base_path=str(multi_scope_dir))

        vm.load_yaml_sidecar(multi_scope_dir / ".variables.yaml")
        vm.load_yaml_sidecar(
            multi_scope_dir / "conversation" / "main" / ".initial.variables.yaml",
            variable_root_space="conversation",
            variable_type="main",
        )
        vm.load_yaml_sidecar(
            multi_scope_dir / "plan" / "main" / ".initial.variables.yaml",
            variable_root_space="plan",
            variable_type="main",
        )

        conv_vars = vm.get_all_variables(
            variable_root_space="conversation",
            variable_type="main",
        )
        assert conv_vars["employee"]["name"] == "RankEvolve"

        plan_vars = vm.get_all_variables(
            variable_root_space="plan",
            variable_type="main",
        )
        assert plan_vars["employee"]["name"] == "PlanAgent"

        global_vars = vm.get_all_variables()
        assert global_vars["app_name"] == "GlobalApp"
        assert "employee" not in global_vars

    def test_scoped_override_isolation(self, multi_scope_dir):
        """Overrides in different scopes don't interfere."""
        vm = FileBasedVariableManager(base_path=str(multi_scope_dir))

        vm.load_yaml_sidecar(
            multi_scope_dir / "conversation" / "main" / ".initial.variables.yaml",
            variable_root_space="conversation",
            variable_type="main",
        )
        vm.load_yaml_sidecar(
            multi_scope_dir / "plan" / "main" / ".initial.variables.yaml",
            variable_root_space="plan",
            variable_type="main",
        )

        vm.set(
            "strategy",
            "paradigm_shifting",
            variable_root_space="conversation",
            variable_type="main",
        )
        vm.set(
            "strategy", "conservative", variable_root_space="plan", variable_type="main"
        )

        conv_val = vm.get_effective_value(
            "strategy",
            variable_root_space="conversation",
            variable_type="main",
        )
        assert "Challenge every assumption" in conv_val

        plan_val = vm.get_effective_value(
            "strategy",
            variable_root_space="plan",
            variable_type="main",
        )
        assert "Measure twice" in plan_val

    def test_cascade_override_resolution(self, multi_scope_dir):
        """More specific scope wins: (root_space, type) > (root_space, "") > ("", "")."""
        vm = FileBasedVariableManager(base_path=str(multi_scope_dir))

        vm.set("color", "blue")
        vm.set("color", "green", variable_root_space="plan")
        vm.set("color", "red", variable_root_space="plan", variable_type="main")

        assert (
            vm.get_effective_value(
                "color",
                variable_root_space="plan",
                variable_type="main",
            )
            == "red"
        )

    def test_cascade_fallback_to_space_level(self, multi_scope_dir):
        """Space-level falls through when type-specific not set."""
        vm = FileBasedVariableManager(base_path=str(multi_scope_dir))

        vm.set("color", "blue")
        vm.set("color", "green", variable_root_space="plan")

        assert (
            vm.get_effective_value(
                "color",
                variable_root_space="plan",
                variable_type="backup1",
            )
            == "green"
        )

    def test_cascade_fallback_to_global(self, multi_scope_dir):
        """Global fallback when nothing more specific."""
        vm = FileBasedVariableManager(base_path=str(multi_scope_dir))
        vm.set("color", "blue")

        assert (
            vm.get_effective_value(
                "color",
                variable_root_space="analysis",
                variable_type="main",
            )
            == "blue"
        )

    def test_cascade_yaml_sidecar_resolution(self, multi_scope_dir):
        """Specific scope sidecar data wins over global via deep merge."""
        vm = FileBasedVariableManager(base_path=str(multi_scope_dir))

        vm.load_yaml_sidecar(multi_scope_dir / ".variables.yaml")
        vm.load_yaml_sidecar(
            multi_scope_dir / "conversation" / "main" / ".initial.variables.yaml",
            variable_root_space="conversation",
            variable_type="main",
        )

        conv_vars = vm.get_all_variables(
            variable_root_space="conversation",
            variable_type="main",
        )
        assert conv_vars["employee"]["name"] == "RankEvolve"
        assert conv_vars["app_name"] == "GlobalApp"

    def test_get_all_variables_deep_merge(self, multi_scope_dir):
        """Cascade merge is DEEP — nested dicts from global are preserved."""
        vm = FileBasedVariableManager(base_path=str(multi_scope_dir))

        vm.load_yaml_sidecar(multi_scope_dir / ".variables.yaml")
        vm.load_yaml_sidecar(
            multi_scope_dir / "conversation" / "main" / ".initial.variables.yaml",
            variable_root_space="conversation",
            variable_type="main",
        )

        conv_vars = vm.get_all_variables(
            variable_root_space="conversation",
            variable_type="main",
        )
        assert conv_vars["settings"]["timeout"] == 30
        assert conv_vars["employee"]["name"] == "RankEvolve"

    def test_skip_overrides(self, multi_scope_dir):
        """skip_overrides=True returns source value even when override exists."""
        vm = FileBasedVariableManager(base_path=str(multi_scope_dir))
        vm.load_yaml_sidecar(
            multi_scope_dir / "conversation" / "main" / ".initial.variables.yaml",
            variable_root_space="conversation",
            variable_type="main",
        )

        vm.set(
            "strategy",
            "paradigm_shifting",
            variable_root_space="conversation",
            variable_type="main",
        )

        with_override = vm.get_effective_value(
            "strategy",
            variable_root_space="conversation",
            variable_type="main",
        )
        assert isinstance(with_override, str)
        assert "Challenge every assumption" in with_override

        source = vm.get_effective_value(
            "strategy",
            variable_root_space="conversation",
            variable_type="main",
            skip_overrides=True,
        )
        assert isinstance(source, dict)
        assert "paradigm_shifting" in source

    def test_backward_compat_property_overrides(self, multi_scope_dir):
        """vm._overrides returns global scope dict (backward compat)."""
        vm = FileBasedVariableManager(base_path=str(multi_scope_dir))

        vm.set("color", "blue")

        assert "color" in vm._overrides
        assert vm._overrides["color"] == "blue"

        vm.set("color", "red", variable_root_space="plan", variable_type="main")
        assert vm._overrides["color"] == "blue"

    def test_backward_compat_property_yaml_sidecar(self, multi_scope_dir):
        """vm._yaml_sidecar returns global scope dict."""
        vm = FileBasedVariableManager(base_path=str(multi_scope_dir))
        vm.load_yaml_sidecar(multi_scope_dir / ".variables.yaml")
        vm.load_yaml_sidecar(
            multi_scope_dir / "conversation" / "main" / ".initial.variables.yaml",
            variable_root_space="conversation",
            variable_type="main",
        )

        assert "app_name" in vm._yaml_sidecar
        assert "employee" not in vm._yaml_sidecar

    def test_backward_compat_hasattr_overrides(self, multi_scope_dir):
        """hasattr(vm, '_overrides') works (used by prompt_rendering.py:144)."""
        vm = FileBasedVariableManager(base_path=str(multi_scope_dir))

        assert hasattr(vm, "_overrides")
        assert vm._overrides == {}

        vm.set("x", "y")
        assert vm._overrides

    def test_no_scope_params_equals_global(self, multi_scope_dir):
        """Calling methods without scope params uses global scope."""
        vm = FileBasedVariableManager(base_path=str(multi_scope_dir))
        vm.load_yaml_sidecar(multi_scope_dir / ".variables.yaml")

        vm.set("color", "blue")
        assert vm.get_effective_value("color") == "blue"
        assert (
            vm.get_effective_value(
                "color",
                variable_root_space="",
                variable_type="",
            )
            == "blue"
        )

    def test_clear_scoped(self, multi_scope_dir):
        """clear() in one scope doesn't affect other scopes."""
        vm = FileBasedVariableManager(base_path=str(multi_scope_dir))

        vm.set("color", "blue")
        vm.set("color", "red", variable_root_space="plan", variable_type="main")

        vm.clear("color", variable_root_space="plan", variable_type="main")

        assert (
            vm.get_effective_value(
                "color",
                variable_root_space="plan",
                variable_type="main",
            )
            == "blue"
        )
        assert vm.get_effective_value("color") == "blue"

    def test_clear_all_clears_everything(self, multi_scope_dir):
        """clear_all() clears ALL scopes."""
        vm = FileBasedVariableManager(base_path=str(multi_scope_dir))

        vm.set("color", "blue")
        vm.set("color", "red", variable_root_space="plan", variable_type="main")
        vm.set(
            "color", "green", variable_root_space="conversation", variable_type="main"
        )

        vm.clear_all()

        assert vm.get_effective_value("color") is None
        assert (
            vm.get_effective_value(
                "color",
                variable_root_space="plan",
                variable_type="main",
            )
            is None
        )
        assert (
            vm.get_effective_value(
                "color",
                variable_root_space="conversation",
                variable_type="main",
            )
            is None
        )

    def test_clear_all_overrides(self, sidecar_dir):
        """clear_all() empties all overrides."""
        vm = FileBasedVariableManager(base_path=str(sidecar_dir))
        vm.load_yaml_sidecar(sidecar_dir / ".initial.variables.yaml")

        vm.set("strategy", "paradigm_shifting")
        vm.set("employee", "override_value")
        vm.clear_all()

        result = vm.get_effective_value("strategy")
        assert isinstance(result, dict)
