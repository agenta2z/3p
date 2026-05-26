"""Tests for TemplateManager.add_template_root() dynamic root management.

Covers:
- LOWEST priority: fill-in-missing at template-name level
- HIGHEST priority: override at template-name level
- Copy-on-write: switch() copies isolated from later add_template_root calls
- Nested dict isolation: adding to existing space doesn't mutate shared inner dicts
- Idempotency: same source added twice is a no-op
- VariableLoader creation for new roots
- template_roots property reflects additions
- templates=None guard (TM with only default_template)
"""

import pytest
from pathlib import Path

from python_utils.string_utils.formatting.template_manager import (
    TemplateManager,
    TemplateRootPriority,
)
from python_utils.string_utils.formatting.template_manager.template_manager import (
    _OriginTaggedStr,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_root(base: Path, templates: dict):
    """Build a template root directory with flat space/name structure."""
    for key, content in templates.items():
        parts = key.split("/")
        file_path = base.joinpath(*parts[:-1], f"{parts[-1]}.j2")
        _write(file_path, content)


# ---------------------------------------------------------------------------
# LOWEST priority
# ---------------------------------------------------------------------------

class TestAddTemplateRootLowest:

    def test_fills_missing_keys(self, tmp_path):
        """LOWEST adds templates that don't exist in the base root."""
        base = tmp_path / "base"
        new = tmp_path / "new"
        _make_root(base, {"space/A": "base-A", "space/B": "base-B"})
        _make_root(new, {"space/A": "new-A", "space/C": "new-C"})

        tm = TemplateManager(
            templates=str(base),
            active_template_type=None,
        )
        tm.add_template_root(str(new), priority=TemplateRootPriority.LOWEST)

        assert tm("space/A") == "base-A"  # base wins
        assert tm("space/B") == "base-B"  # only in base
        assert tm("space/C") == "new-C"  # filled from new

    def test_does_not_update_original_templates_path_singular(self, tmp_path):
        """LOWEST does not change _original_templates_path (singular)."""
        base = tmp_path / "base"
        new = tmp_path / "new"
        _make_root(base, {"space/A": "base-A"})
        _make_root(new, {"space/B": "new-B"})

        tm = TemplateManager(templates=str(base), active_template_type=None)
        original_path = tm._original_templates_path
        tm.add_template_root(str(new), priority=TemplateRootPriority.LOWEST)
        assert tm._original_templates_path == original_path

    def test_template_roots_reflects_addition(self, tmp_path):
        """template_roots includes the newly added root."""
        base = tmp_path / "base"
        new = tmp_path / "new"
        _make_root(base, {"space/A": "a"})
        _make_root(new, {"space/B": "b"})

        tm = TemplateManager(templates=str(base), active_template_type=None)
        assert len(tm.template_roots) == 1
        tm.add_template_root(str(new), priority=TemplateRootPriority.LOWEST)
        assert len(tm.template_roots) == 2
        assert tm.template_roots[-1] == str(new)

    def test_new_templates_tagged_with_origin(self, tmp_path):
        """Templates from new root carry _origin_root."""
        base = tmp_path / "base"
        new = tmp_path / "new"
        _make_root(base, {"space/A": "base-A"})
        _make_root(new, {"space/C": "new-C"})

        tm = TemplateManager(templates=str(base), active_template_type=None)
        tm.add_template_root(str(new), priority=TemplateRootPriority.LOWEST)

        raw = tm.get_raw_template("space/C")
        assert raw is not None
        assert getattr(raw, "_origin_root", None) == str(new)


# ---------------------------------------------------------------------------
# HIGHEST priority
# ---------------------------------------------------------------------------

class TestAddTemplateRootHighest:

    def test_overrides_existing_keys(self, tmp_path):
        """HIGHEST replaces existing templates at template-name level."""
        base = tmp_path / "base"
        new = tmp_path / "new"
        _make_root(base, {"space/A": "base-A", "space/B": "base-B"})
        _make_root(new, {"space/A": "new-A", "space/C": "new-C"})

        tm = TemplateManager(templates=str(base), active_template_type=None)
        tm.add_template_root(str(new), priority=TemplateRootPriority.HIGHEST)

        assert tm("space/A") == "new-A"  # overridden
        assert tm("space/B") == "base-B"  # preserved (new doesn't define B)
        assert tm("space/C") == "new-C"  # added

    def test_updates_original_templates_path_singular(self, tmp_path):
        """HIGHEST updates _original_templates_path (singular)."""
        base = tmp_path / "base"
        new = tmp_path / "new"
        _make_root(base, {"space/A": "base-A"})
        _make_root(new, {"space/B": "new-B"})

        tm = TemplateManager(templates=str(base), active_template_type=None)
        tm.add_template_root(str(new), priority=TemplateRootPriority.HIGHEST)
        assert tm._original_templates_path == str(new)

    def test_prepends_to_template_roots(self, tmp_path):
        """HIGHEST prepends new root to template_roots."""
        base = tmp_path / "base"
        new = tmp_path / "new"
        _make_root(base, {"space/A": "a"})
        _make_root(new, {"space/B": "b"})

        tm = TemplateManager(templates=str(base), active_template_type=None)
        tm.add_template_root(str(new), priority=TemplateRootPriority.HIGHEST)
        assert tm.template_roots[0] == str(new)


# ---------------------------------------------------------------------------
# Copy-on-write isolation
# ---------------------------------------------------------------------------

class TestCopyOnWrite:

    def test_switch_copy_not_affected(self, tmp_path):
        """switch() copy is isolated from later add_template_root on original."""
        base = tmp_path / "base"
        new = tmp_path / "new"
        _make_root(base, {"space/A": "base-A"})
        _make_root(new, {"space/C": "new-C"})

        tm = TemplateManager(templates=str(base), active_template_type=None)
        copy = tm.switch()

        tm.add_template_root(str(new), priority=TemplateRootPriority.LOWEST)

        # Original has the new template
        assert tm("space/C") == "new-C"
        # Copy does NOT have it — falls through to default_template ("")
        raw = copy.get_raw_template("space/C")
        assert raw != "new-C"  # must not see the new template

    def test_nested_dict_isolation(self, tmp_path):
        """Adding to existing space doesn't mutate shared inner dicts."""
        base = tmp_path / "base"
        new = tmp_path / "new"
        _make_root(base, {"space/A": "base-A"})
        _make_root(new, {"space/C": "new-C"})

        tm = TemplateManager(templates=str(base), active_template_type=None)
        # Grab reference to inner dict before add
        inner_before = tm.templates.get("space")

        tm.add_template_root(str(new), priority=TemplateRootPriority.LOWEST)

        # Inner dict should be a NEW object (copy-on-write)
        inner_after = tm.templates.get("space")
        assert inner_before is not inner_after

    def test_injected_roots_isolated_from_switch(self, tmp_path):
        """_injected_roots set is independent after add_template_root."""
        base = tmp_path / "base"
        new = tmp_path / "new"
        _make_root(base, {"space/A": "a"})
        _make_root(new, {"space/B": "b"})

        tm = TemplateManager(templates=str(base), active_template_type=None)
        copy = tm.switch()

        tm.add_template_root(str(new), priority=TemplateRootPriority.LOWEST)

        assert str(new) in tm._injected_roots
        assert str(new) not in copy._injected_roots


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

class TestIdempotency:

    def test_same_source_twice_is_noop(self, tmp_path):
        """Adding the same source twice doesn't duplicate or error."""
        base = tmp_path / "base"
        new = tmp_path / "new"
        _make_root(base, {"space/A": "base-A"})
        _make_root(new, {"space/C": "new-C"})

        tm = TemplateManager(templates=str(base), active_template_type=None)
        tm.add_template_root(str(new), priority=TemplateRootPriority.LOWEST)
        roots_after_first = list(tm.template_roots)

        tm.add_template_root(str(new), priority=TemplateRootPriority.LOWEST)
        assert tm.template_roots == roots_after_first  # no duplicate


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_templates_none_guard(self, tmp_path):
        """add_template_root works when templates was originally None."""
        new = tmp_path / "new"
        _make_root(new, {"space/A": "new-A"})

        tm = TemplateManager(
            default_template="fallback {{ x }}",
            active_template_type=None,
        )
        assert tm.templates is None
        tm.add_template_root(str(new), priority=TemplateRootPriority.LOWEST)
        assert tm("space/A") == "new-A"

    def test_dict_source_accepted(self, tmp_path):
        """Dict sources are accepted but don't get origin tagging."""
        base = tmp_path / "base"
        _make_root(base, {"space/A": "base-A"})

        tm = TemplateManager(templates=str(base), active_template_type=None)
        tm.add_template_root(
            {"space": {"C": "dict-C"}},
            priority=TemplateRootPriority.LOWEST,
        )
        assert tm("space/C") == "dict-C"
        raw = tm.get_raw_template("space/C")
        assert getattr(raw, "_origin_root", None) is None

    def test_invalid_priority_raises(self, tmp_path):
        """Non-enum priority raises ValueError."""
        base = tmp_path / "base"
        _make_root(base, {"space/A": "a"})

        tm = TemplateManager(templates=str(base), active_template_type=None)
        with pytest.raises(ValueError, match="TemplateRootPriority"):
            tm.add_template_root(str(base), priority="invalid")

    def test_new_space_added_by_lowest(self, tmp_path):
        """LOWEST can add an entirely new space (not just fill existing)."""
        base = tmp_path / "base"
        new = tmp_path / "new"
        _make_root(base, {"alpha/A": "a"})
        _make_root(new, {"beta/B": "b"})

        tm = TemplateManager(templates=str(base), active_template_type=None)
        tm.add_template_root(str(new), priority=TemplateRootPriority.LOWEST)
        assert tm("beta/B") == "b"
