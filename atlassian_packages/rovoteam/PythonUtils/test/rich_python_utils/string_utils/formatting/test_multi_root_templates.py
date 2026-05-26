"""Tests for multi-root template overlay and variable isolation.

Covers:
- templates=[...] list input with first-write-wins deep merge
- _OriginTaggedStr preservation through lookup chains and pickling
- Per-root VariableLoader creation and isolation
- switch() with multi-root predefined_variables
- Component merging across roots
- Edge cases: single-element list, empty list, mixed types, fallback to default
"""

import pickle
import pytest
from pathlib import Path

from python_utils.string_utils.formatting.template_manager import (
    TemplateManager,
)
from python_utils.string_utils.formatting.template_manager.template_manager import (
    _OriginTaggedStr,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(path: Path, content: str):
    """Create parent dirs and write text to *path*."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_root(base: Path, templates: dict, variables: dict = None):
    """Build a template root directory.

    Args:
        base: Root directory path.
        templates: Mapping of ``"space/type/name"`` → content.
            The path separator ``/`` is split into directories;
            the last segment is the filename (with ``.j2`` appended).
        variables: Optional mapping of ``"scope/var_name"`` → content.
            Written under ``base/_variables/notes/<var_name>.hbs``
            (scope is prepended as parent directories).
    """
    for key, content in templates.items():
        parts = key.split("/")
        file_path = base.joinpath(*parts[:-1], f"{parts[-1]}.j2")
        _write(file_path, content)

    if variables:
        for key, content in variables.items():
            parts = key.split("/")
            file_path = base.joinpath("_variables", "notes", *parts[:-1], f"{parts[-1]}.hbs")
            _write(file_path, content)


# ---------------------------------------------------------------------------
# _OriginTaggedStr unit tests
# ---------------------------------------------------------------------------

class TestOriginTaggedStr:
    """Tests for the _OriginTaggedStr internal class."""

    def test_basic_creation(self):
        s = _OriginTaggedStr("hello", origin_root="/some/path")
        assert s == "hello"
        assert s._origin_root == "/some/path"

    def test_is_str_instance(self):
        s = _OriginTaggedStr("hello", origin_root="/path")
        assert isinstance(s, str)

    def test_none_origin(self):
        s = _OriginTaggedStr("hello")
        assert s._origin_root is None

    def test_str_operations_lose_origin(self):
        s = _OriginTaggedStr("  hello  ", origin_root="/path")
        stripped = s.strip()
        assert stripped == "hello"
        assert not hasattr(stripped, "_origin_root") or getattr(stripped, "_origin_root", None) is None

    def test_pickle_roundtrip(self):
        s = _OriginTaggedStr("hello", origin_root="/my/root")
        restored = pickle.loads(pickle.dumps(s))
        assert restored == "hello"
        assert restored._origin_root == "/my/root"
        assert isinstance(restored, _OriginTaggedStr)

    def test_pickle_none_origin(self):
        s = _OriginTaggedStr("hello")
        restored = pickle.loads(pickle.dumps(s))
        assert restored == "hello"
        assert restored._origin_root is None

    def test_getattr_safe_for_plain_str(self):
        """getattr with default works on plain str (used in __call__)."""
        plain = "hello"
        assert getattr(plain, "_origin_root", None) is None

    def test_equality_with_plain_str(self):
        s = _OriginTaggedStr("hello", origin_root="/path")
        assert s == "hello"
        assert "hello" == s

    def test_in_dict_key(self):
        """Tagged strings work as dict keys and values."""
        s = _OriginTaggedStr("key", origin_root="/path")
        d = {s: "value"}
        assert d["key"] == "value"


# ---------------------------------------------------------------------------
# Multi-root overlay: basic merge behavior
# ---------------------------------------------------------------------------

class TestMultiRootOverlay:
    """Tests for templates=[override_dir, base_dir] merge behavior."""

    def test_override_wins_for_same_template(self, tmp_path):
        """When both roots have the same template, override wins."""
        override = tmp_path / "override"
        base = tmp_path / "base"
        _make_root(override, {"main/default": "OVERRIDE {{name}}"})
        _make_root(base, {"main/default": "BASE {{name}}"})

        tm = TemplateManager(
            templates=[str(override), str(base)],
            active_template_type="main",
        )
        result = tm(name="Alice")
        assert result == "OVERRIDE Alice"

    def test_base_fills_missing_templates(self, tmp_path):
        """Templates only in base are available when override lacks them."""
        override = tmp_path / "override"
        base = tmp_path / "base"
        _make_root(override, {"main/Greet": "CUSTOM Greet {{name}}"})
        _make_root(base, {
            "main/Greet": "BASE Greet {{name}}",
            "main/Farewell": "BASE Farewell {{name}}",
        })

        tm = TemplateManager(
            templates=[str(override), str(base)],
            active_template_type="main",
        )
        assert tm("Greet", name="A") == "CUSTOM Greet A"
        assert tm("Farewell", name="B") == "BASE Farewell B"

    def test_single_element_list_same_as_scalar(self, tmp_path):
        """templates=[path] behaves identically to templates=path."""
        root = tmp_path / "root"
        _make_root(root, {"main/default": "Hello {{name}}"})

        tm_list = TemplateManager(
            templates=[str(root)],
            active_template_type="main",
        )
        tm_scalar = TemplateManager(
            templates=str(root),
            active_template_type="main",
        )
        assert tm_list(name="X") == tm_scalar(name="X")

    def test_empty_list_requires_default_template(self):
        """templates=[] with no default_template raises."""
        with pytest.raises(ValueError, match="No templates were provided"):
            TemplateManager(templates=[])

    def test_empty_list_with_default_template(self):
        """templates=[] with default_template works."""
        tm = TemplateManager(
            templates=[],
            default_template="fallback {{name}}",
        )
        assert tm(name="Z") == "fallback Z"

    def test_three_roots_priority(self, tmp_path):
        """Three roots: first wins, then second, then third."""
        r1 = tmp_path / "r1"
        r2 = tmp_path / "r2"
        r3 = tmp_path / "r3"
        _make_root(r1, {"main/A": "R1-A {{v}}"})
        _make_root(r2, {"main/A": "R2-A {{v}}", "main/B": "R2-B {{v}}"})
        _make_root(r3, {
            "main/A": "R3-A {{v}}",
            "main/B": "R3-B {{v}}",
            "main/C": "R3-C {{v}}",
        })

        tm = TemplateManager(
            templates=[str(r1), str(r2), str(r3)],
            active_template_type="main",
        )
        assert tm("A", v="x") == "R1-A x"
        assert tm("B", v="x") == "R2-B x"
        assert tm("C", v="x") == "R3-C x"

    def test_mixed_list_path_and_dict(self, tmp_path):
        """List mixing a path and a dict source."""
        root = tmp_path / "root"
        _make_root(root, {"main/FileTemplate": "FROM FILE {{v}}"})

        tm = TemplateManager(
            templates=[
                str(root),
                {"main": {"DictTemplate": "FROM DICT {{v}}"}},
            ],
            active_template_type="main",
        )
        assert tm("FileTemplate", v="x") == "FROM FILE x"
        assert tm("DictTemplate", v="x") == "FROM DICT x"

    def test_dict_templates_not_tagged(self, tmp_path):
        """Dict sources have no origin root (no variable isolation for dicts)."""
        tm = TemplateManager(
            templates=[{"main": {"default": "dict {{v}}"}}],
            active_template_type="main",
        )
        # Should work; the template value is a plain str (no origin)
        raw = tm.get_raw_template()
        assert getattr(raw, "_origin_root", None) is None


# ---------------------------------------------------------------------------
# Deep merge: same space key from different roots
# ---------------------------------------------------------------------------

class TestDeepMerge:
    """Verify one-level-deep merge within the same space key."""

    def test_templates_from_different_roots_coexist_in_same_space(self, tmp_path):
        """Override has main/A, base has main/B → both available."""
        override = tmp_path / "override"
        base = tmp_path / "base"
        _make_root(override, {"main/A": "OVR-A"})
        _make_root(base, {"main/B": "BASE-B"})

        tm = TemplateManager(
            templates=[str(override), str(base)],
            active_template_type="main",
        )
        assert tm("A") == "OVR-A"
        assert tm("B") == "BASE-B"

    def test_override_template_does_not_shadow_entire_space(self, tmp_path):
        """Having A in override doesn't prevent B from base in same space."""
        override = tmp_path / "override"
        base = tmp_path / "base"
        _make_root(override, {"agent/main/Search": "CUSTOM Search"})
        _make_root(base, {
            "agent/main/Search": "BASE Search",
            "agent/main/Browse": "BASE Browse",
        })

        tm = TemplateManager(
            templates=[str(override), str(base)],
            active_template_root_space="agent",
            active_template_type="main",
        )
        assert tm("Search") == "CUSTOM Search"
        assert tm("Browse") == "BASE Browse"


# ---------------------------------------------------------------------------
# Component merging across roots
# ---------------------------------------------------------------------------

class TestComponentMerge:
    """Test that components from different roots deep-merge correctly."""

    def test_components_from_different_roots_coexist(self, tmp_path):
        """Override has header component, base has footer component."""
        override = tmp_path / "override"
        base = tmp_path / "base"

        # Override root: template + header component
        _write(override / "main" / "default.j2", "{{header}} | {{footer}}")
        _write(override / "main" / "components" / "header.j2", "CUSTOM-HEADER")

        # Base root: footer component only (no template)
        _write(base / "main" / "components" / "footer.j2", "BASE-FOOTER")

        tm = TemplateManager(
            templates=[str(override), str(base)],
            active_template_type="main",
        )
        result = tm()
        assert "CUSTOM-HEADER" in result
        assert "BASE-FOOTER" in result

    def test_override_component_wins_over_base(self, tmp_path):
        """Same component in both roots: override wins."""
        override = tmp_path / "override"
        base = tmp_path / "base"

        _write(override / "main" / "default.j2", "{{header}}")
        _write(override / "main" / "components" / "header.j2", "OVERRIDE-HEADER")
        _write(base / "main" / "components" / "header.j2", "BASE-HEADER")

        tm = TemplateManager(
            templates=[str(override), str(base)],
            active_template_type="main",
        )
        assert tm() == "OVERRIDE-HEADER"


# ---------------------------------------------------------------------------
# Origin tagging through lookup chain
# ---------------------------------------------------------------------------

class TestOriginTracking:
    """Verify _OriginTaggedStr survives the lookup chain."""

    def test_get_raw_template_preserves_origin(self, tmp_path):
        """get_raw_template returns an _OriginTaggedStr with correct origin."""
        root = tmp_path / "root"
        _make_root(root, {"main/default": "Hello {{name}}"})

        tm = TemplateManager(
            templates=[str(root)],
            active_template_type="main",
        )
        raw = tm.get_raw_template()
        assert isinstance(raw, _OriginTaggedStr)
        assert raw._origin_root == str(root)

    def test_origin_tracks_correct_root_per_template(self, tmp_path):
        """Each template's origin points to its source root."""
        override = tmp_path / "override"
        base = tmp_path / "base"
        _make_root(override, {"main/A": "OVR-A"})
        _make_root(base, {"main/B": "BASE-B"})

        tm = TemplateManager(
            templates=[str(override), str(base)],
            active_template_type="main",
        )
        raw_a = tm.get_raw_template("A")
        raw_b = tm.get_raw_template("B")
        assert raw_a._origin_root == str(override)
        assert raw_b._origin_root == str(base)

    def test_fallback_to_default_template_has_no_origin(self, tmp_path):
        """When resolution falls back to default_template, there is no origin."""
        root = tmp_path / "root"
        _make_root(root, {"main/Exists": "yes"})

        tm = TemplateManager(
            templates=[str(root)],
            default_template="fallback {{v}}",
            active_template_type="main",
        )
        raw = tm.get_raw_template("NonExistent")
        assert getattr(raw, "_origin_root", None) is None


# ---------------------------------------------------------------------------
# Variable isolation across roots
# ---------------------------------------------------------------------------

class TestVariableIsolation:
    """Templates from root A use root A's _variables, not root B's."""

    def test_each_root_uses_own_variables(self, tmp_path):
        """Override template uses override vars; base template uses base vars."""
        override = tmp_path / "override"
        base = tmp_path / "base"

        _make_root(
            override,
            templates={"main/Greet": "{{notes_greeting}} {{user}}!"},
            variables={"greeting": "CUSTOM-HELLO"},
        )
        _make_root(
            base,
            templates={"main/Farewell": "{{notes_farewell}} {{user}}!"},
            variables={"farewell": "BASE-GOODBYE"},
        )

        tm = TemplateManager(
            templates=[str(override), str(base)],
            predefined_variables=True,
            active_template_type="main",
        )
        greet = tm("Greet", user="Alice")
        assert "CUSTOM-HELLO" in greet
        assert "Alice" in greet

        farewell = tm("Farewell", user="Bob")
        assert "BASE-GOODBYE" in farewell
        assert "Bob" in farewell

    def test_override_vars_not_used_for_base_templates(self, tmp_path):
        """A variable in override's _variables/ is NOT resolved for base templates.

        Base must have its own _variables/ for isolation to work — otherwise the
        template has no origin-matched loader and falls back to _variable_loader.
        """
        override = tmp_path / "override"
        base = tmp_path / "base"

        _make_root(
            override,
            templates={"main/A": "A: {{notes_secret}}"},
            variables={"secret": "OVERRIDE-SECRET"},
        )
        _make_root(
            base,
            templates={"main/B": "B: {{notes_secret}}"},
            variables={"secret": "BASE-SECRET"},
        )

        tm = TemplateManager(
            templates=[str(override), str(base)],
            predefined_variables=True,
            active_template_type="main",
        )
        result_a = tm("A")
        assert "OVERRIDE-SECRET" in result_a

        # Template B from base uses BASE's variable, not override's
        result_b = tm("B")
        assert "BASE-SECRET" in result_b
        assert "OVERRIDE-SECRET" not in result_b

    def test_per_root_loaders_created(self, tmp_path):
        """_variable_loaders_by_root has entries for roots with _variables."""
        r1 = tmp_path / "r1"
        r2 = tmp_path / "r2"
        _make_root(r1, {"main/default": "t"}, variables={"x": "val"})
        _make_root(r2, {"main/other": "t"}, variables={"y": "val"})

        tm = TemplateManager(
            templates=[str(r1), str(r2)],
            predefined_variables=True,
            active_template_type="main",
        )
        assert str(r1) in tm._variable_loaders_by_root
        assert str(r2) in tm._variable_loaders_by_root
        assert len(tm._variable_loaders_by_root) == 2

    def test_root_without_variables_has_no_loader(self, tmp_path):
        """A root with no _variables/ dir gets no VariableLoader entry."""
        with_vars = tmp_path / "with"
        without_vars = tmp_path / "without"
        _make_root(with_vars, {"main/default": "t"}, variables={"x": "v"})
        _make_root(without_vars, {"main/other": "t"})

        tm = TemplateManager(
            templates=[str(with_vars), str(without_vars)],
            predefined_variables=True,
            active_template_type="main",
        )
        assert str(with_vars) in tm._variable_loaders_by_root
        assert str(without_vars) not in tm._variable_loaders_by_root

    def test_cross_root_render_no_variables_root_uses_fallback(self, tmp_path):
        """Template from a root WITHOUT _variables/ renders with variables
        resolved from the first root's loader (the fallback _variable_loader).

        This is the exact production scenario for the template split: wrapper
        templates live in AgentFoundation (no _variables/), variables live in
        OpenTeam (has _variables/).  The fallback path must produce a fully
        rendered string containing the variable content.
        """
        vars_root = tmp_path / "vars_root"       # has _variables/, no template for "Greet"
        template_root = tmp_path / "template_root"  # has template, no _variables/

        _make_root(vars_root, {"main/default": "unused"}, variables={"greeting": "HELLO-FROM-VARS-ROOT"})
        _make_root(template_root, {"main/Greet": "{{notes_greeting}} {{user}}!"})
        # template_root intentionally has NO _variables/

        tm = TemplateManager(
            templates=[str(vars_root), str(template_root)],
            predefined_variables=True,
            active_template_type="main",
        )

        # "Greet" only exists in template_root (no _variables/ → no origin-matched
        # loader → falls back to _variable_loader which is vars_root's loader).
        result = tm("Greet", user="Alice")
        assert "HELLO-FROM-VARS-ROOT" in result, (
            "Variable from vars_root must resolve for template in template_root"
        )
        assert "Alice" in result

    def test_backward_compat_single_root(self, tmp_path):
        """Single root with predefined_variables=True still works exactly as before."""
        root = tmp_path / "root"
        _make_root(
            root,
            templates={"main/default": "{{notes_greeting}} {{user}}"},
            variables={"greeting": "Hi"},
        )

        tm = TemplateManager(
            templates=str(root),
            predefined_variables=True,
            active_template_type="main",
        )
        assert tm._variable_loader is not None
        assert len(tm._variable_loaders_by_root) == 1
        result = tm(user="Alice")
        assert "Hi" in result
        assert "Alice" in result


# ---------------------------------------------------------------------------
# switch() with multi-root
# ---------------------------------------------------------------------------

class TestSwitchMultiRoot:
    """Tests for switch() behavior with multi-root templates."""

    def test_switch_preserves_multi_root_templates(self, tmp_path):
        """switch() preserves the merged template dict."""
        override = tmp_path / "override"
        base = tmp_path / "base"
        _make_root(override, {"main/A": "OVR-A {{v}}"})
        _make_root(base, {"main/B": "BASE-B {{v}}"})

        tm = TemplateManager(
            templates=[str(override), str(base)],
            active_template_type="main",
        )
        tm2 = tm.switch(active_template_type="main")
        assert tm2("A", v="x") == "OVR-A x"
        assert tm2("B", v="x") == "BASE-B x"

    def test_switch_shares_variable_loaders(self, tmp_path):
        """switch() without predefined_variables shares loaders (read-only)."""
        root = tmp_path / "root"
        _make_root(root, {"main/default": "t"}, variables={"x": "v"})

        tm = TemplateManager(
            templates=[str(root)],
            predefined_variables=True,
            active_template_type="main",
        )
        tm2 = tm.switch(active_template_type="reflection")
        assert tm2._variable_loaders_by_root is tm._variable_loaders_by_root

    def test_switch_predefined_true_rebuilds_loaders(self, tmp_path):
        """switch(predefined_variables=True) rebuilds per-root loaders."""
        r1 = tmp_path / "r1"
        r2 = tmp_path / "r2"
        _make_root(r1, {"main/default": "t"}, variables={"x": "v1"})
        _make_root(r2, {"main/other": "t"}, variables={"y": "v2"})

        tm = TemplateManager(
            templates=[str(r1), str(r2)],
            predefined_variables=False,
            active_template_type="main",
        )
        assert tm._variable_loader is None
        assert not tm._variable_loaders_by_root

        tm2 = tm.switch(predefined_variables=True)
        assert tm2._variable_loader is not None
        assert len(tm2._variable_loaders_by_root) == 2

    def test_switch_predefined_false_clears_loaders(self, tmp_path):
        """switch(predefined_variables=False) clears all loaders."""
        root = tmp_path / "root"
        _make_root(root, {"main/default": "t"}, variables={"x": "v"})

        tm = TemplateManager(
            templates=[str(root)],
            predefined_variables=True,
            active_template_type="main",
        )
        assert tm._variable_loader is not None

        tm2 = tm.switch(predefined_variables=False)
        assert tm2._variable_loader is None
        assert not tm2._variable_loaders_by_root


# ---------------------------------------------------------------------------
# Fallback chain with multi-root
# ---------------------------------------------------------------------------

class TestFallbackChainMultiRoot:
    """Ensure the existing fallback chain works with merged multi-root dict."""

    def test_parent_space_fallback(self, tmp_path):
        """Template not found at space → falls back through parent spaces."""
        root = tmp_path / "root"
        _make_root(root, {
            "agent/main/default": "agent-default {{v}}",
        })

        tm = TemplateManager(
            templates=[str(root)],
            active_template_root_space="agent",
            active_template_type="main",
        )
        # "sub/NonExistent" → fallback → agent/main/default
        result = tm("sub/NonExistent", v="x")
        assert "agent-default" in result

    def test_root_space_removal_fallback(self, tmp_path):
        """Template not found with root_space → tries without root_space."""
        root = tmp_path / "root"
        _make_root(root, {
            "main/FallbackTemplate": "global-main {{v}}",
        })

        tm = TemplateManager(
            templates=[str(root)],
            active_template_root_space="nonexistent_root",
            active_template_type="main",
        )
        result = tm("FallbackTemplate", v="x")
        assert result == "global-main x"

    def test_fallback_uses_correct_origin_for_variables(self, tmp_path):
        """After fallback, the resolved template's origin is used for variables."""
        r1 = tmp_path / "r1"
        r2 = tmp_path / "r2"
        # r1 has no templates but has variables
        _make_root(r1, {}, variables={"greeting": "R1-HELLO"})
        # r2 has the fallback template + its own variables
        _make_root(
            r2,
            templates={"main/default": "{{notes_greeting}} {{user}}"},
            variables={"greeting": "R2-HELLO"},
        )

        tm = TemplateManager(
            templates=[str(r1), str(r2)],
            predefined_variables=True,
            active_template_type="main",
        )
        # Template comes from r2, so r2's variables should be used
        result = tm(user="Alice")
        assert "R2-HELLO" in result
        assert "R1-HELLO" not in result


# ---------------------------------------------------------------------------
# get_raw_template with multi-root
# ---------------------------------------------------------------------------

class TestGetRawTemplateMultiRoot:
    """get_raw_template respects multi-root merge."""

    def test_returns_override_template(self, tmp_path):
        override = tmp_path / "override"
        base = tmp_path / "base"
        _make_root(override, {"main/default": "OVERRIDE"})
        _make_root(base, {"main/default": "BASE"})

        tm = TemplateManager(
            templates=[str(override), str(base)],
            active_template_type="main",
        )
        assert tm.get_raw_template() == "OVERRIDE"

    def test_returns_base_when_override_missing(self, tmp_path):
        override = tmp_path / "override"
        base = tmp_path / "base"
        _make_root(override, {"main/A": "OVR-A"})
        _make_root(base, {"main/B": "BASE-B"})

        tm = TemplateManager(
            templates=[str(override), str(base)],
            active_template_type="main",
        )
        assert tm.get_raw_template("B") == "BASE-B"


# ---------------------------------------------------------------------------
# Cross-space root with multi-root
# ---------------------------------------------------------------------------

class TestCrossSpaceWithMultiRoot:
    """Verify cross_space_root works correctly with per-root loaders."""

    def test_cross_space_root_shared_across_loaders(self, tmp_path):
        """Each per-root loader gets the same cross_space_root config."""
        r1 = tmp_path / "r1"
        r2 = tmp_path / "r2"
        cross = tmp_path / "cross"
        _make_root(r1, {"main/default": "t"}, variables={"x": "v"})
        _make_root(r2, {"main/other": "t"}, variables={"y": "v"})
        # Create cross-space _variables dir
        _write(cross / "_variables" / "notes" / "shared.hbs", "SHARED-VAR")

        tm = TemplateManager(
            templates=[str(r1), str(r2)],
            predefined_variables=True,
            cross_space_root=str(cross),
            active_template_type="main",
        )
        # Both loaders should exist and have cross_space_root configured
        for loader in tm._variable_loaders_by_root.values():
            assert loader.config.cross_space_root == str(cross)
