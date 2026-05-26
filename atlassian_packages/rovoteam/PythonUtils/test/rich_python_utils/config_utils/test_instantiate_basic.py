"""Tests for basic instantiation: dataclasses, plain classes, callables, shorthand."""

import functools

import pytest
from omegaconf import OmegaConf

from python_utils.config_utils import instantiate, register_alias, register_class

from test_helpers import PlainClass, SimpleAttrs, SimpleDataclass, ParentAttrs, create_simple

_MOD = "test_helpers"


class TestDataclass:
    def test_from_full_path(self):
        cfg = OmegaConf.create({"_target_": f"{_MOD}.SimpleDataclass", "x": 10, "y": 20})
        obj = instantiate(cfg)
        assert isinstance(obj, SimpleDataclass)
        assert obj.x == 10 and obj.y == 20

    def test_from_alias(self):
        register_alias("SDC", f"{_MOD}.SimpleDataclass")
        cfg = OmegaConf.create({"_target_": "SDC", "x": 5})
        obj = instantiate(cfg)
        assert isinstance(obj, SimpleDataclass)
        assert obj.x == 5


class TestPlainClass:
    def test_from_target(self):
        cfg = OmegaConf.create({"_target_": f"{_MOD}.PlainClass", "name": "hi", "value": 7})
        obj = instantiate(cfg)
        assert isinstance(obj, PlainClass)
        assert obj.name == "hi" and obj.value == 7


class TestFactoryFunction:
    def test_function_as_target(self):
        cfg = OmegaConf.create({"_target_": f"{_MOD}.create_simple", "name": "fn", "count": 99})
        obj = instantiate(cfg)
        assert isinstance(obj, SimpleAttrs)
        assert obj.name == "fn" and obj.count == 99


class TestNestedRecursive:
    def test_parent_with_nested_child(self):
        register_alias("SA", f"{_MOD}.SimpleAttrs")
        cfg = OmegaConf.create({
            "_target_": f"{_MOD}.ParentAttrs",
            "child": {"_target_": "SA", "name": "nested", "count": 3},
            "label": "parent",
        })
        obj = instantiate(cfg)
        assert isinstance(obj, ParentAttrs)
        assert isinstance(obj.child, SimpleAttrs)
        assert obj.child.name == "nested"
        assert obj.label == "parent"


class TestFullPathWithoutRegistration:
    def test_dotted_target_works(self):
        cfg = OmegaConf.create({"_target_": f"{_MOD}.SimpleAttrs", "name": "direct"})
        obj = instantiate(cfg)
        assert obj.name == "direct"


class TestConvertAll:
    def test_produces_native_types(self):
        cfg = OmegaConf.create({
            "_target_": f"{_MOD}.SimpleAttrs",
            "name": "test",
        })
        obj = instantiate(cfg)
        assert isinstance(obj, SimpleAttrs)


class TestUnknownTarget:
    def test_error_for_unresolvable(self):
        cfg = OmegaConf.create({"_target_": "NoSuchAlias"})
        with pytest.raises(KeyError, match="Unknown target alias"):
            instantiate(cfg)


class TestStringShorthand:
    def test_expands_alias_to_target(self):
        register_alias("SA", f"{_MOD}.SimpleAttrs")
        register_alias("PA", f"{_MOD}.ParentAttrs")
        cfg = OmegaConf.create({
            "_target_": "PA",
            "child": "SA",  # shorthand
            "label": "test",
        })
        obj = instantiate(cfg)
        assert isinstance(obj, ParentAttrs)
        assert isinstance(obj.child, SimpleAttrs)

    def test_non_alias_string_stays(self):
        register_alias("SA", f"{_MOD}.SimpleAttrs")
        cfg = OmegaConf.create({
            "_target_": "SA",
            "name": "hello",  # not an alias
        })
        obj = instantiate(cfg)
        assert obj.name == "hello"

    def test_skips_hydra_keys(self):
        register_alias("SA", f"{_MOD}.SimpleAttrs")
        cfg = OmegaConf.create({"_target_": "SA", "name": "ok"})
        obj = instantiate(cfg)
        # _target_ was not double-expanded
        assert isinstance(obj, SimpleAttrs)

    def test_mixed_shorthand_and_full(self):
        register_alias("SA", f"{_MOD}.SimpleAttrs")
        register_alias("PA", f"{_MOD}.ParentAttrs")
        cfg = OmegaConf.create({
            "_target_": "PA",
            "child": {"_target_": "SA", "name": "full_syntax", "count": 5},
            "label": "mixed",
        })
        obj = instantiate(cfg)
        assert obj.child.name == "full_syntax"
        assert obj.child.count == 5
