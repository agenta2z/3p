"""Tests for load_config and merge_configs."""

import os
import tempfile

import pytest

from python_utils.config_utils import load_config, merge_configs


@pytest.fixture
def yaml_dir(tmp_path):
    """Create a temporary directory with test YAML files."""
    (tmp_path / "simple.yaml").write_text("name: hello\ncount: 42\n")
    (tmp_path / "override_test.yaml").write_text("a: 1\nb: 2\nc: 3\n")
    (tmp_path / "with_env.yaml").write_text(
        'value: ${oc.env:_TEST_CONFIG_VAR,fallback_val}\n'
    )
    (tmp_path / "with_path.yaml").write_text(
        'data_dir: ${path:data/input}\n'
    )
    return tmp_path


class TestLoadYaml:
    def test_basic_load(self, yaml_dir):
        cfg = load_config(str(yaml_dir / "simple.yaml"))
        assert cfg.name == "hello"
        assert cfg.count == 42

    def test_load_with_overrides(self, yaml_dir):
        cfg = load_config(
            str(yaml_dir / "override_test.yaml"),
            overrides={"b": 99, "d": 4},
        )
        assert cfg.a == 1
        assert cfg.b == 99  # overridden
        assert cfg.c == 3
        assert cfg.d == 4  # added

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/path.yaml")


class TestMergeConfigs:
    def test_later_wins(self, yaml_dir):
        cfg1 = load_config(str(yaml_dir / "simple.yaml"))
        merged = merge_configs(cfg1, {"name": "world", "extra": True})
        assert merged.name == "world"
        assert merged.count == 42
        assert merged.extra is True


class TestEnvResolver:
    def test_oc_env_with_default(self, yaml_dir):
        cfg = load_config(str(yaml_dir / "with_env.yaml"))
        assert cfg.value == "fallback_val"

    def test_oc_env_reads_var(self, yaml_dir, monkeypatch):
        monkeypatch.setenv("_TEST_CONFIG_VAR", "from_env")
        cfg = load_config(str(yaml_dir / "with_env.yaml"))
        assert cfg.value == "from_env"


class TestPathResolver:
    def test_resolves_relative_to_yaml_dir(self, yaml_dir):
        cfg = load_config(str(yaml_dir / "with_path.yaml"))
        expected = str((yaml_dir / "data" / "input").resolve())
        assert cfg.data_dir == expected

    def test_absolute_path_base(self, yaml_dir):
        # Verify the base is the YAML file's parent, not CWD
        cfg = load_config(str(yaml_dir / "with_path.yaml"))
        assert str(yaml_dir.resolve()) in cfg.data_dir
