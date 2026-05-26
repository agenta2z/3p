"""Tests for the ${modpath:...} OmegaConf resolver."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from omegaconf import OmegaConf

from python_utils.config_utils._resolvers import _modpath_resolver, ensure_resolvers


# ---------------------------------------------------------------------------
# Direct unit tests for _modpath_resolver
# ---------------------------------------------------------------------------


class TestModpathResolverDirect:
    """Test _modpath_resolver function directly (no OmegaConf interpolation)."""

    def test_dotted_with_leaf_resolves_to_parent_slash_leaf(self):
        """os.path → parent of 'os' module / 'path' (the leaf segment)."""
        result = _modpath_resolver("os.path")
        result_path = Path(result)
        assert result_path.is_absolute()
        assert result_path.name == "path"
        # os.__file__ parent is the stdlib dir; os.path should be sibling
        import os as _os_mod

        expected = Path(_os_mod.__file__).parent / "path"
        assert result_path == expected

    def test_dotted_three_segments(self):
        """email.mime.text → imports email.mime, returns parent / 'text'."""
        result = _modpath_resolver("email.mime.text")
        result_path = Path(result)
        assert result_path.is_absolute()
        assert result_path.name == "text"
        import email.mime as _em

        expected = Path(_em.__file__).parent / "text"
        assert result_path == expected

    def test_single_segment_module(self):
        """Single-segment dotted string imports the module and returns its parent dir."""
        result = _modpath_resolver("json")
        result_path = Path(result)
        assert result_path.is_absolute()
        import json as _json_mod

        expected = Path(_json_mod.__file__).parent
        assert result_path == expected

    def test_nonexistent_module_raises(self):
        """Non-existent module prefix should raise ModuleNotFoundError."""
        with pytest.raises(ModuleNotFoundError):
            _modpath_resolver("nonexistent_module_xyz_12345.resources.templates")

    def test_nonexistent_single_segment_raises(self):
        """Non-existent single-segment module should raise ModuleNotFoundError."""
        with pytest.raises(ModuleNotFoundError):
            _modpath_resolver("nonexistent_module_xyz_12345")

    def test_agent_foundation_resources_prompt_templates(self):
        """${modpath:agent_foundation.resources.prompt_templates} resolves correctly.

        Skipped if agent_foundation is not installed/importable.
        """
        af_res = pytest.importorskip("agent_foundation.resources")
        result = _modpath_resolver("agent_foundation.resources.prompt_templates")
        result_path = Path(result)
        assert result_path.is_absolute()
        assert result_path.name == "prompt_templates"
        expected = Path(af_res.__file__).parent / "prompt_templates"
        assert result_path == expected


# ---------------------------------------------------------------------------
# Integration tests via OmegaConf interpolation
# ---------------------------------------------------------------------------


class TestModpathResolverViaOmegaConf:
    """Test ${modpath:...} resolver through OmegaConf config interpolation."""

    @pytest.fixture(autouse=True)
    def _register(self):
        """Ensure resolvers are registered before each test."""
        ensure_resolvers()

    def test_interpolation_resolves_correctly(self):
        """${modpath:os.path} resolves via OmegaConf interpolation."""
        cfg = OmegaConf.create({"os_path_dir": "${modpath:os.path}"})
        result = cfg.os_path_dir
        result_path = Path(result)
        assert result_path.is_absolute()
        assert result_path.name == "path"

        import os as _os_mod

        expected = Path(_os_mod.__file__).parent / "path"
        assert result_path == expected

    def test_interpolation_single_segment(self):
        """${modpath:json} resolves to json module's parent directory."""
        cfg = OmegaConf.create({"json_dir": "${modpath:json}"})
        result = cfg.json_dir
        result_path = Path(result)
        assert result_path.is_absolute()

        import json as _json_mod

        expected = Path(_json_mod.__file__).parent
        assert result_path == expected

    def test_interpolation_nonexistent_module_raises(self):
        """${modpath:bad.module.leaf} raises during resolution."""
        cfg = OmegaConf.create(
            {"bad": "${modpath:nonexistent_module_xyz_12345.sub.leaf}"}
        )
        with pytest.raises(Exception):
            _ = cfg.bad
