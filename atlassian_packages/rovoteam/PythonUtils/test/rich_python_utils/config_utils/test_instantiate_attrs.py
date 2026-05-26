"""Tests for attrs-specific instantiation: underscore-stripping, aliases, init=False, etc."""

import logging

import pytest
from omegaconf import OmegaConf

from python_utils.config_utils import instantiate, register_alias

from test_helpers import (
    AttrsKwOnly,
    AttrsWithAlias,
    AttrsWithCallable,
    AttrsWithConverter,
    AttrsWithInitFalse,
    AttrsWithPostInit,
    AttrsWithUnderscore,
    ParentAttrs,
    SimpleAttrs,
    SimpleDataclass,
    SlottedAttrs,
    UnslottedAttrs,
)

_MOD = "test_helpers"


class TestSimpleAttrs:
    def test_basic(self):
        cfg = OmegaConf.create({"_target_": f"{_MOD}.SimpleAttrs", "name": "x", "count": 1})
        obj = instantiate(cfg)
        assert isinstance(obj, SimpleAttrs)
        assert obj.name == "x" and obj.count == 1


class TestKwOnly:
    def test_kw_only_fields(self):
        cfg = OmegaConf.create({"_target_": f"{_MOD}.AttrsKwOnly", "name": "kw", "value": 42})
        obj = instantiate(cfg)
        assert obj.name == "kw" and obj.value == 42


class TestUnderscoreStripping:
    def test_stripped_name(self):
        # attrs strips leading _ → init param is 'secret'
        cfg = OmegaConf.create({"_target_": f"{_MOD}.AttrsWithUnderscore", "secret": "s3cr3t"})
        obj = instantiate(cfg)
        assert obj._secret == "s3cr3t"


class TestExplicitAlias:
    def test_alias_as_yaml_key(self):
        # alias='public_name' → YAML key must be 'public_name'
        cfg = OmegaConf.create({"_target_": f"{_MOD}.AttrsWithAlias", "public_name": "hello"})
        obj = instantiate(cfg)
        assert obj._internal == "hello"


class TestFactoryDefault:
    def test_omitted_field_uses_factory(self):
        cfg = OmegaConf.create({"_target_": f"{_MOD}.SimpleAttrs"})
        obj = instantiate(cfg)
        assert obj.name == "" and obj.count == 0


class TestConverter:
    def test_dict_converter(self):
        cfg = OmegaConf.create({"_target_": f"{_MOD}.AttrsWithConverter", "data": {"a": 1}})
        obj = instantiate(cfg)
        assert obj.data == {"a": 1}

    def test_none_input(self):
        cfg = OmegaConf.create({"_target_": f"{_MOD}.AttrsWithConverter", "data": None})
        obj = instantiate(cfg)
        assert obj.data == {}


class TestSlots:
    def test_slots_true(self):
        cfg = OmegaConf.create({"_target_": f"{_MOD}.SlottedAttrs", "value": 3.14})
        obj = instantiate(cfg)
        assert isinstance(obj, SlottedAttrs) and obj.value == 3.14

    def test_slots_false(self):
        cfg = OmegaConf.create({"_target_": f"{_MOD}.UnslottedAttrs", "value": 2.71})
        obj = instantiate(cfg)
        assert isinstance(obj, UnslottedAttrs) and obj.value == 2.71


class TestInitFalseFiltering:
    def test_init_false_removed_with_warning(self, caplog):
        cfg = OmegaConf.create({
            "_target_": f"{_MOD}.AttrsWithInitFalse",
            "name": "test",
            "_cache": {"stale": True},  # init=False — should be filtered
        })
        with caplog.at_level(logging.WARNING):
            obj = instantiate(cfg)
        assert isinstance(obj, AttrsWithInitFalse)
        assert obj.name == "test"
        assert obj._cache == {}  # factory default, not YAML value
        assert "_cache" in caplog.text  # warning was logged


class TestPostInit:
    def test_post_init_fires(self):
        cfg = OmegaConf.create({"_target_": f"{_MOD}.AttrsWithPostInit", "name": "hello"})
        obj = instantiate(cfg)
        assert obj._computed == "computed_hello"


class TestNestedAttrsInAttrs:
    def test_recursive(self):
        cfg = OmegaConf.create({
            "_target_": f"{_MOD}.ParentAttrs",
            "child": {"_target_": f"{_MOD}.SimpleAttrs", "name": "inner", "count": 9},
            "label": "outer",
        })
        obj = instantiate(cfg)
        assert isinstance(obj.child, SimpleAttrs)
        assert obj.child.name == "inner"


class TestMixedAttrsAndDataclass:
    def test_attrs_parent_dataclass_child(self):
        cfg = OmegaConf.create({
            "_target_": f"{_MOD}.ParentAttrs",
            "child": {"_target_": f"{_MOD}.SimpleDataclass", "x": 10, "y": 20},
            "label": "mixed",
        })
        obj = instantiate(cfg)
        assert isinstance(obj.child, SimpleDataclass)
        assert obj.child.x == 10


class TestCallableFieldDefault:
    def test_omit_callable_uses_default(self):
        cfg = OmegaConf.create({"_target_": f"{_MOD}.AttrsWithCallable", "name": "test"})
        obj = instantiate(cfg)
        assert obj.processor is None
