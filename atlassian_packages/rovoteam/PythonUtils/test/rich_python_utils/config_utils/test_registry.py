"""Tests for the target alias registry."""

import pytest

from python_utils.config_utils._registry import (
    _make_import_path,
    _reset_registry,
    list_registered,
    register,
    register_alias,
    register_class,
    resolve_target,
)

from test_helpers import SimpleAttrs, SimpleDataclass


class TestRegisterDecorator:
    def test_registers_alias_and_returns_class_unchanged(self):
        register_class(SimpleAttrs, "TestSimple", category="test")
        assert resolve_target("TestSimple").endswith(".SimpleAttrs")
        # Class is not modified by registration
        assert SimpleAttrs.__name__ == "SimpleAttrs"

    def test_no_parens_raises_type_error(self):
        with pytest.raises(TypeError, match="string alias"):
            @register
            class Foo:
                pass

    def test_non_string_alias_raises_type_error(self):
        with pytest.raises(TypeError, match="string alias"):
            @register(42)
            class Foo:
                pass


class TestRegisterClass:
    def test_imperative_registration(self):
        register_class(SimpleAttrs, "SA")
        path = resolve_target("SA")
        assert "SimpleAttrs" in path


class TestRegisterAlias:
    def test_string_only_no_import(self):
        register_alias("Foo", "some.module.Foo", "test")
        assert resolve_target("Foo") == "some.module.Foo"

    def test_duplicate_same_path_idempotent(self):
        register_alias("Bar", "a.b.Bar")
        register_alias("Bar", "a.b.Bar")  # no error
        assert resolve_target("Bar") == "a.b.Bar"

    def test_duplicate_different_path_raises(self):
        register_alias("Baz", "a.b.Baz")
        with pytest.raises(ValueError, match="already registered"):
            register_alias("Baz", "x.y.Baz")


class TestResolveTarget:
    def test_alias_resolves(self):
        register_alias("X", "mod.X")
        assert resolve_target("X") == "mod.X"

    def test_dotted_path_passthrough(self):
        assert resolve_target("some.module.Class") == "some.module.Class"

    def test_interpolation_passthrough(self):
        assert resolve_target("${some_var}") == "${some_var}"

    def test_unknown_raises_key_error(self):
        with pytest.raises(KeyError, match="Unknown target alias"):
            resolve_target("NonExistent")


class TestListRegistered:
    def test_all(self):
        register_alias("A", "mod.A", "cat1")
        register_alias("B", "mod.B", "cat2")
        result = list_registered()
        assert result == {"A": "mod.A", "B": "mod.B"}

    def test_by_category(self):
        register_alias("A", "mod.A", "cat1")
        register_alias("B", "mod.B", "cat2")
        assert list_registered("cat1") == {"A": "mod.A"}
        assert list_registered("cat2") == {"B": "mod.B"}
        assert list_registered("cat3") == {}


class TestNestedClassGuard:
    def test_nested_class_rejected(self):
        class Outer:
            class Inner:
                pass

        with pytest.raises(ValueError, match="nested class"):
            _make_import_path(Outer.Inner)


class TestResetRegistry:
    def test_clears_state(self):
        register_alias("X", "mod.X", "cat")
        _reset_registry()
        assert list_registered() == {}
        assert list_registered("cat") == {}
