"""Unit tests for FileBasedVariableManager folder-level helpers.

Covers ``_find_in_variable_folder`` and ``_read_variable_folder_config``,
introduced as part of Refactor 12 (variable resolver fix).
"""

from pathlib import Path

import pytest

from python_utils.common_objects.variable_manager import (
    FileBasedVariableManager,
    VariableManagerConfig,
)


@pytest.fixture
def manager(tmp_path: Path) -> FileBasedVariableManager:
    """Default manager with default config (overrides disabled)."""
    return FileBasedVariableManager(base_path=str(tmp_path))


@pytest.fixture
def manager_with_overrides(tmp_path: Path) -> FileBasedVariableManager:
    """Manager with override files enabled."""
    config = VariableManagerConfig(enable_overrides=True)
    return FileBasedVariableManager(base_path=str(tmp_path), config=config)


# ---------------------------------------------------------------------------
# _read_variable_folder_config
# ---------------------------------------------------------------------------


class TestReadVariableFolderConfig:
    def test_returns_dict(self, manager, tmp_path):
        folder = tmp_path / "task_preamble"
        folder.mkdir()
        (folder / ".config.yaml").write_text(
            "default: generic\naggregation: agg_v2\n", encoding="utf-8"
        )

        result = manager._read_variable_folder_config(folder)
        assert result == {"default": "generic", "aggregation": "agg_v2"}

    def test_missing_file_returns_empty_dict(self, manager, tmp_path):
        folder = tmp_path / "task_preamble"
        folder.mkdir()
        # No .config.yaml at all

        assert manager._read_variable_folder_config(folder) == {}

    def test_malformed_yaml_returns_empty_dict(self, manager, tmp_path):
        folder = tmp_path / "task_preamble"
        folder.mkdir()
        # Invalid YAML
        (folder / ".config.yaml").write_text(
            "default: [unclosed\nbroken yaml: : :", encoding="utf-8"
        )

        assert manager._read_variable_folder_config(folder) == {}

    def test_non_dict_yaml_returns_empty_dict(self, manager, tmp_path):
        folder = tmp_path / "task_preamble"
        folder.mkdir()
        # Valid YAML but a list, not a dict
        (folder / ".config.yaml").write_text(
            "- item1\n- item2\n", encoding="utf-8"
        )

        assert manager._read_variable_folder_config(folder) == {}

    def test_none_values_filtered(self, manager, tmp_path):
        folder = tmp_path / "task_preamble"
        folder.mkdir()
        (folder / ".config.yaml").write_text(
            "default: generic\nempty_key:\nresearch: deep_v1\n",
            encoding="utf-8",
        )

        result = manager._read_variable_folder_config(folder)
        assert result == {"default": "generic", "research": "deep_v1"}

    def test_values_stringified(self, manager, tmp_path):
        folder = tmp_path / "task_preamble"
        folder.mkdir()
        # YAML may parse integers; we want strings out
        (folder / ".config.yaml").write_text(
            "default: 42\naggregation: v2\n", encoding="utf-8"
        )

        result = manager._read_variable_folder_config(folder)
        assert result == {"default": "42", "aggregation": "v2"}


# ---------------------------------------------------------------------------
# _find_in_variable_folder
# ---------------------------------------------------------------------------


class TestFindInVariableFolder:
    def test_direct_file_hit(self, manager, tmp_path):
        folder = tmp_path / "task_preamble"
        folder.mkdir()
        target = folder / "aggregation.j2"
        target.write_text("aggregation content", encoding="utf-8")

        result = manager._find_in_variable_folder(folder, "aggregation")
        assert result == target

    def test_extension_priority(self, manager, tmp_path):
        # Default file_extensions: [".hbs", ".j2", ".jinja2", ".jinja", ".txt", ""]
        folder = tmp_path / "task_preamble"
        folder.mkdir()
        # Create both .j2 and .txt -- .j2 should win (earlier in list)
        (folder / "aggregation.j2").write_text("j2 content", encoding="utf-8")
        (folder / "aggregation.txt").write_text("txt content", encoding="utf-8")

        result = manager._find_in_variable_folder(folder, "aggregation")
        assert result is not None
        assert result.name == "aggregation.j2"

    def test_config_yaml_alias_hit(self, manager, tmp_path):
        folder = tmp_path / "task_preamble"
        folder.mkdir()
        (folder / "agg_v2.j2").write_text("aliased content", encoding="utf-8")
        (folder / ".config.yaml").write_text(
            "aggregation: agg_v2\n", encoding="utf-8"
        )
        # Note: aggregation.j2 does NOT exist directly

        result = manager._find_in_variable_folder(folder, "aggregation")
        assert result is not None
        assert result.name == "agg_v2.j2"

    def test_direct_file_wins_over_config_alias(self, manager, tmp_path):
        folder = tmp_path / "task_preamble"
        folder.mkdir()
        # Both direct file and alias exist
        (folder / "aggregation.j2").write_text(
            "direct content", encoding="utf-8"
        )
        (folder / "agg_v2.j2").write_text("alias content", encoding="utf-8")
        (folder / ".config.yaml").write_text(
            "aggregation: agg_v2\n", encoding="utf-8"
        )

        result = manager._find_in_variable_folder(folder, "aggregation")
        assert result is not None
        assert result.name == "aggregation.j2"

    def test_missing_returns_none(self, manager, tmp_path):
        folder = tmp_path / "task_preamble"
        folder.mkdir()
        # Empty folder

        assert manager._find_in_variable_folder(folder, "aggregation") is None

    def test_non_directory_returns_none(self, manager, tmp_path):
        # Path doesn't exist as a directory
        not_a_folder = tmp_path / "ghost"

        assert manager._find_in_variable_folder(not_a_folder, "aggregation") is None

    def test_name_none_returns_none(self, manager, tmp_path):
        folder = tmp_path / "task_preamble"
        folder.mkdir()
        (folder / "aggregation.j2").write_text("content", encoding="utf-8")

        assert manager._find_in_variable_folder(folder, None) is None

    def test_name_empty_returns_none(self, manager, tmp_path):
        folder = tmp_path / "task_preamble"
        folder.mkdir()
        (folder / "aggregation.j2").write_text("content", encoding="utf-8")

        assert manager._find_in_variable_folder(folder, "") is None

    def test_override_suffix_priority(self, manager_with_overrides, tmp_path):
        folder = tmp_path / "task_preamble"
        folder.mkdir()
        # Both override and direct exist
        (folder / "aggregation.j2").write_text(
            "regular content", encoding="utf-8"
        )
        (folder / "aggregation.override.j2").write_text(
            "override content", encoding="utf-8"
        )

        result = manager_with_overrides._find_in_variable_folder(
            folder, "aggregation"
        )
        assert result is not None
        assert result.name == "aggregation.override.j2"

    def test_override_ignored_when_disabled(self, manager, tmp_path):
        # Default manager has enable_overrides=False
        folder = tmp_path / "task_preamble"
        folder.mkdir()
        (folder / "aggregation.j2").write_text(
            "regular content", encoding="utf-8"
        )
        (folder / "aggregation.override.j2").write_text(
            "override content", encoding="utf-8"
        )

        result = manager._find_in_variable_folder(folder, "aggregation")
        assert result is not None
        # Without overrides enabled, regular file wins
        assert result.name == "aggregation.j2"

    def test_config_yaml_malformed_silent_skip(self, manager, tmp_path):
        folder = tmp_path / "task_preamble"
        folder.mkdir()
        (folder / ".config.yaml").write_text(
            "broken: yaml: : :", encoding="utf-8"
        )
        # No direct file either

        # Should return None silently (no exception)
        assert manager._find_in_variable_folder(folder, "aggregation") is None

    def test_alias_target_missing_returns_none(self, manager, tmp_path):
        folder = tmp_path / "task_preamble"
        folder.mkdir()
        # alias points to non-existent file
        (folder / ".config.yaml").write_text(
            "aggregation: agg_missing\n", encoding="utf-8"
        )

        assert manager._find_in_variable_folder(folder, "aggregation") is None

    def test_alias_path_traversal_rejected(self, manager, tmp_path):
        # Adversarial .config.yaml: alias value contains a path separator,
        # attempting to escape the variable folder.
        outside = tmp_path / "outside.j2"
        outside.write_text("escaped content", encoding="utf-8")

        folder = tmp_path / "task_preamble"
        folder.mkdir()
        (folder / ".config.yaml").write_text(
            "aggregation: ../outside\n", encoding="utf-8"
        )

        # Path-traversal guard rejects the alias. Returns None instead of
        # reading the file outside the folder.
        assert manager._find_in_variable_folder(folder, "aggregation") is None

    def test_alias_backslash_traversal_rejected(self, manager, tmp_path):
        folder = tmp_path / "task_preamble"
        folder.mkdir()
        (folder / ".config.yaml").write_text(
            "aggregation: subdir\\file\n", encoding="utf-8"
        )

        assert manager._find_in_variable_folder(folder, "aggregation") is None
