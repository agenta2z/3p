"""TIER-1 tests for openteam.mcp_server._helpers."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from openteam.mcp_server._helpers import render_result, strip_unset, to_dash_form


# ---- strip_unset -----------------------------------------------------------

class TestStripUnset:
    def test_strip_unset_preserves_zero(self):
        assert strip_unset({"x": 0}) == {"x": 0}

    def test_strip_unset_drops_false(self):
        assert strip_unset({"x": False}) == {}

    def test_strip_unset_drops_none(self):
        assert strip_unset({"x": None}) == {}

    def test_strip_unset_drops_empty_string(self):
        assert strip_unset({"x": ""}) == {}

    def test_strip_unset_drops_empty_list(self):
        assert strip_unset({"x": []}) == {}

    def test_strip_unset_keeps_true(self):
        assert strip_unset({"x": True}) == {"x": True}

    def test_strip_unset_keeps_nonempty(self):
        result = strip_unset({"x": "hi", "y": [1]})
        assert result == {"x": "hi", "y": [1]}


# ---- to_dash_form ----------------------------------------------------------

class TestToDashForm:
    def test_to_dash_form(self):
        assert to_dash_form({"foo_bar": 1, "baz": 2}) == {"foo-bar": 1, "baz": 2}


# ---- render_result ----------------------------------------------------------

class TestRenderResult:
    def test_render_result_dataclass(self):
        obj = SimpleNamespace(result="hi", context_updates={"workspace_path": "/tmp"})
        text = render_result(obj)
        assert "hi" in text
        assert "Artifacts:" in text
        assert "workspace_path: /tmp" in text

    def test_render_result_dict(self):
        assert render_result({"result": "ok"}) == "ok"

    def test_render_result_str(self):
        assert render_result("hello") == "hello"

    def test_render_result_unknown_keys_not_in_footer(self):
        """context_updates with keys that don't end in _path or _dir
        must NOT produce an Artifacts section."""
        obj = SimpleNamespace(result="done", context_updates={"foo": "bar"})
        text = render_result(obj)
        assert "Artifacts" not in text
