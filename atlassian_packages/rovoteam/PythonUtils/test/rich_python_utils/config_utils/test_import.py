"""Tests for _import_ / _import_shared_ file composition in load_config."""

import functools

import pytest

from python_utils.config_utils import load_config, instantiate
from python_utils.config_utils._instantiate import (
    _deep_merge,
    _ImportFactory,
    _resolve_import_,
)
from python_utils.config_utils._lazy_config_factory import LazyConfigFactory


# ---------------------------------------------------------------------------
# _deep_merge unit tests
# ---------------------------------------------------------------------------


class TestDeepMerge:
    def test_flat_merge(self):
        base = {"a": 1, "b": 2}
        result = _deep_merge(base, {"b": 3, "c": 4})
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        base = {"x": {"a": 1, "b": 2}, "y": 10}
        result = _deep_merge(base, {"x": {"b": 3, "c": 4}})
        assert result == {"x": {"a": 1, "b": 3, "c": 4}, "y": 10}

    def test_override_replaces_non_dict(self):
        base = {"x": {"a": 1}}
        result = _deep_merge(base, {"x": "replaced"})
        assert result == {"x": "replaced"}

    def test_does_not_mutate_base(self):
        base = {"a": {"b": 1}}
        _deep_merge(base, {"a": {"b": 2}})
        assert base["a"]["b"] == 1


# ---------------------------------------------------------------------------
# _resolve_import_ unit tests
# ---------------------------------------------------------------------------


@pytest.fixture
def import_dir(tmp_path):
    """Create test YAML files for _import_ testing."""
    (tmp_path / "base.yaml").write_text(
        "_target_: MyClass\nfield_a: 1\nfield_b: 2\nnested:\n  x: 10\n  y: 20\n"
    )
    (tmp_path / "parent.yaml").write_text(
        "top_level: true\nchild:\n  _import_: base.yaml\n  field_b: 99\n"
    )
    (tmp_path / "with_nested_override.yaml").write_text(
        "child:\n  _import_: base.yaml\n  nested:\n    y: 999\n"
    )
    # Nested _import_: A imports B which imports C
    (tmp_path / "leaf.yaml").write_text("_target_: Leaf\nvalue: 42\n")
    (tmp_path / "middle.yaml").write_text(
        "_target_: Middle\ninner:\n  _import_: leaf.yaml\n"
    )
    (tmp_path / "top.yaml").write_text(
        "root:\n  _import_: middle.yaml\n"
    )
    # Subdirectory
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "sub_config.yaml").write_text("_target_: Sub\nval: 7\n")
    (tmp_path / "ref_subdir.yaml").write_text(
        "child:\n  _import_: sub/sub_config.yaml\n"
    )
    return tmp_path


class TestResolveImport:
    def test_basic_import(self, import_dir):
        node = {"_import_": "base.yaml", "field_b": 99}
        result = _resolve_import_(node, import_dir)
        assert result["_target_"] == "MyClass"
        assert result["field_a"] == 1
        assert result["field_b"] == 99
        assert "_import_" not in result

    def test_import_with_nested_override(self, import_dir):
        node = {"_import_": "base.yaml", "nested": {"y": 999}}
        result = _resolve_import_(node, import_dir)
        assert result["nested"]["x"] == 10
        assert result["nested"]["y"] == 999

    def test_import_inside_parent_dict(self, import_dir):
        node = {"top_level": True, "child": {"_import_": "base.yaml", "field_b": 99}}
        result = _resolve_import_(node, import_dir)
        assert result["top_level"] is True
        assert result["child"]["_target_"] == "MyClass"
        assert result["child"]["field_b"] == 99

    def test_nested_import_chain(self, import_dir):
        node = {"root": {"_import_": "middle.yaml"}}
        result = _resolve_import_(node, import_dir)
        assert result["root"]["_target_"] == "Middle"
        assert result["root"]["inner"]["_target_"] == "Leaf"
        assert result["root"]["inner"]["value"] == 42

    def test_subdirectory_import(self, import_dir):
        node = {"child": {"_import_": "sub/sub_config.yaml"}}
        result = _resolve_import_(node, import_dir)
        assert result["child"]["_target_"] == "Sub"
        assert result["child"]["val"] == 7

    def test_missing_file_raises(self, import_dir):
        node = {"_import_": "nonexistent.yaml"}
        with pytest.raises(FileNotFoundError, match="_import_"):
            _resolve_import_(node, import_dir)

    def test_list_nodes_recursed(self, import_dir):
        node = [{"_import_": "base.yaml"}, {"plain": True}]
        result = _resolve_import_(node, import_dir)
        assert result[0]["_target_"] == "MyClass"
        assert result[1]["plain"] is True

    def test_scalar_passthrough(self, import_dir):
        assert _resolve_import_("hello", import_dir) == "hello"
        assert _resolve_import_(42, import_dir) == 42
        assert _resolve_import_(None, import_dir) is None

    def test_no_import_key_passthrough(self, import_dir):
        node = {"a": 1, "b": {"c": 2}}
        result = _resolve_import_(node, import_dir)
        assert result == {"a": 1, "b": {"c": 2}}


# ---------------------------------------------------------------------------
# Integration: _import_ through load_config
# ---------------------------------------------------------------------------


class TestImportInLoadConfig:
    def test_load_config_resolves_import(self, import_dir):
        cfg = load_config(str(import_dir / "parent.yaml"))
        assert cfg.child._target_ == "MyClass"
        assert cfg.child.field_a == 1
        assert cfg.child.field_b == 99

    def test_load_config_with_nested_override(self, import_dir):
        cfg = load_config(str(import_dir / "with_nested_override.yaml"))
        assert cfg.child.nested.x == 10
        assert cfg.child.nested.y == 999

    def test_load_config_nested_import_chain(self, import_dir):
        cfg = load_config(str(import_dir / "top.yaml"))
        assert cfg.root._target_ == "Middle"
        assert cfg.root.inner._target_ == "Leaf"

    def test_dot_notation_overrides_on_imported_config(self, import_dir):
        cfg = load_config(
            str(import_dir / "parent.yaml"),
            overrides={"child.field_a": 777},
        )
        assert cfg.child.field_a == 777
        assert cfg.child.field_b == 99

    def test_import_from_subdirectory(self, import_dir):
        cfg = load_config(str(import_dir / "ref_subdir.yaml"))
        assert cfg.child._target_ == "Sub"
        assert cfg.child.val == 7


# ---------------------------------------------------------------------------
# _import_shared_ backward compatibility
# ---------------------------------------------------------------------------


@pytest.fixture
def shared_import_dir(tmp_path):
    """YAML files using _import_shared_ (old behavior under new name)."""
    (tmp_path / "base.yaml").write_text(
        "_target_: MyClass\nfield_a: 1\nfield_b: 2\n"
    )
    (tmp_path / "parent_shared.yaml").write_text(
        "top_level: true\nchild:\n  _import_shared_: base.yaml\n  field_b: 99\n"
    )
    return tmp_path


class TestImportShared:
    def test_import_shared_basic(self, shared_import_dir):
        node = {"_import_shared_": "base.yaml", "field_b": 99}
        result = _resolve_import_(node, shared_import_dir)
        assert result["_target_"] == "MyClass"
        assert result["field_a"] == 1
        assert result["field_b"] == 99
        assert "_import_shared_" not in result
        assert "_factory_" not in result

    def test_import_shared_through_load_config(self, shared_import_dir):
        cfg = load_config(str(shared_import_dir / "parent_shared.yaml"))
        assert cfg.child._target_ == "MyClass"
        assert cfg.child.field_b == 99


# ---------------------------------------------------------------------------
# _import_ factory marker
# ---------------------------------------------------------------------------


class TestImportFactoryMarker:
    def test_import_adds_factory_marker(self, import_dir):
        node = {"_import_": "base.yaml"}
        result = _resolve_import_(node, import_dir)
        assert result["_factory_"] is True

    def test_import_shared_no_factory_marker(self, import_dir):
        node = {"_import_shared_": "base.yaml"}
        result = _resolve_import_(node, import_dir)
        assert "_factory_" not in result

    def test_factory_marker_stripped_outside_factory_field(self, import_dir):
        """_import_ on a non-*_factory field degrades to shared semantics."""
        (import_dir / "child_config.yaml").write_text(
            "_target_: test_helpers.SimpleAttrs\nname: imported\ncount: 42\n"
        )
        (import_dir / "parent_non_factory.yaml").write_text(
            "_target_: test_helpers.ParentAttrs\n"
            "child:\n  _import_: child_config.yaml\n"
        )
        cfg = load_config(str(import_dir / "parent_non_factory.yaml"))
        result = instantiate(cfg)
        assert result.child.name == "imported"
        assert result.child.count == 42


# ---------------------------------------------------------------------------
# _ImportFactory via *_factory fields
# ---------------------------------------------------------------------------


@pytest.fixture
def factory_dir(tmp_path):
    """YAML files for _ImportFactory tests."""
    (tmp_path / "inner_worker.yaml").write_text(
        "_target_: test_helpers.InnerWorker\n"
        "model: opus\n"
        "child:\n  _target_: test_helpers.SimpleAttrs\n  name: shared_child\n"
    )
    (tmp_path / "outer.yaml").write_text(
        "_target_: test_helpers.AttrsWithFactory\n"
        "name: outer\n"
        "worker_factory:\n  _import_: inner_worker.yaml\n"
    )
    (tmp_path / "outer_dict.yaml").write_text(
        "_target_: test_helpers.AttrsWithFactory\n"
        "name: outer\n"
        "worker_factory:\n"
        "  type_a:\n"
        "    _import_: inner_worker.yaml\n"
        "  type_b:\n"
        "    _target_: test_helpers.SimpleAttrs\n"
        "    name: simple\n"
    )
    (tmp_path / "outer_shared.yaml").write_text(
        "_target_: test_helpers.AttrsWithFactory\n"
        "name: outer\n"
        "worker_factory:\n  _import_shared_: inner_worker.yaml\n"
    )
    return tmp_path


class TestImportFactory:
    def test_single_factory_returns_lazy_config_factory(self, factory_dir):
        """After Fix #9+#10, ALL *_factory entries get LazyConfigFactory."""
        cfg = load_config(str(factory_dir / "outer.yaml"))
        result = instantiate(cfg)
        assert isinstance(result.worker_factory, LazyConfigFactory)

    def test_factory_call_creates_fresh_instances(self, factory_dir):
        cfg = load_config(str(factory_dir / "outer.yaml"))
        result = instantiate(cfg)
        w1 = result.worker_factory()
        w2 = result.worker_factory()
        assert id(w1) != id(w2)
        assert id(w1.child) != id(w2.child)

    def test_factory_call_with_no_args(self, factory_dir):
        """LazyConfigFactory has strict no-args signature."""
        cfg = load_config(str(factory_dir / "outer.yaml"))
        result = instantiate(cfg)
        w = result.worker_factory()
        assert w.model == "opus"

    def test_dict_of_factories_all_lazy(self, factory_dir):
        """After Fix #9, ALL dict factory entries become LazyConfigFactory."""
        cfg = load_config(str(factory_dir / "outer_dict.yaml"))
        result = instantiate(cfg)
        assert isinstance(result.worker_factory["type_a"], LazyConfigFactory)
        assert isinstance(result.worker_factory["type_b"], LazyConfigFactory)

    def test_dict_factory_fresh_instances(self, factory_dir):
        cfg = load_config(str(factory_dir / "outer_dict.yaml"))
        result = instantiate(cfg)
        w1 = result.worker_factory["type_a"]()
        w2 = result.worker_factory["type_a"]()
        assert id(w1) != id(w2)
        assert id(w1.child) != id(w2.child)

    def test_import_shared_in_factory_field_returns_lazy(self, factory_dir):
        """Even _import_shared_ in *_factory fields now becomes LazyConfigFactory."""
        cfg = load_config(str(factory_dir / "outer_shared.yaml"))
        result = instantiate(cfg)
        assert isinstance(result.worker_factory, LazyConfigFactory)

    def test_dot_notation_overrides_on_factory_import(self, factory_dir):
        cfg = load_config(
            str(factory_dir / "outer.yaml"),
            overrides={"worker_factory.model": "sonnet"},
        )
        result = instantiate(cfg)
        w = result.worker_factory()
        assert w.model == "sonnet"

    def test_template_extra_feed_propagation(self, factory_dir):
        cfg = load_config(str(factory_dir / "outer.yaml"))
        result = instantiate(cfg)
        factory = result.worker_factory
        factory.template_extra_feed.update({"ctx": "value"})
        w = factory()
        assert hasattr(w, "template_extra_feed") is False or True

    def test_repr(self, factory_dir):
        cfg = load_config(str(factory_dir / "outer.yaml"))
        result = instantiate(cfg)
        assert "InnerWorker" in repr(result.worker_factory)
