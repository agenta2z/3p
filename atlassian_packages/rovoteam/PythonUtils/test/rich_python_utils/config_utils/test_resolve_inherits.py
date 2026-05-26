"""Unit tests for the ``_inherits_`` directive in the config loader.

Covers semantics defined in ``_instantiate.py:_resolve_inherits_``:

* Deep copy + override merge (source unchanged; result distinct).
* Recursive ``_deep_merge`` for nested dicts; lists replaced wholesale.
* Dotted-path resolution + list-index segments.
* Chained inheritance (depth-first via active-stack cycle detection).
* Order-independent (target may appear before or after the inheritor).
* Cycle detection (self-loops + multi-step chains).
* Error cases (non-existent path, non-string directive value).
* Directive stripped from output.
* OmegaConf interpolation behavior (absolute vs ``${.field}`` relative)
  after inheritance.
* End-to-end through Hydra: distinct Python instances after instantiate().
* Nested ``_inherits_`` resolves recursively inside an inherited dict.
"""
from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any, Dict

import attr
import pytest
from omegaconf import OmegaConf

from python_utils.config_utils._instantiate import (
    _resolve_inherits_,
    _resolve_path_in_root,
)
from python_utils.config_utils import instantiate, load_config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _yaml_to_container(yaml_text: str) -> Dict[str, Any]:
    """Load YAML text into a plain Python dict (for direct ``_resolve_inherits_`` testing)."""
    cfg = OmegaConf.create(textwrap.dedent(yaml_text).strip())
    return OmegaConf.to_container(cfg, resolve=False)


def _write_yaml(tmp_path: Path, yaml_text: str, name: str = "config.yaml") -> str:
    """Write YAML to disk and return the path (for end-to-end ``load_config`` tests)."""
    fpath = tmp_path / name
    fpath.write_text(textwrap.dedent(yaml_text).strip(), encoding="utf-8")
    return str(fpath)


# A simple attrs target for end-to-end Hydra instantiation tests.
@attr.attrs(slots=False)
class _Bag:
    name: str = attr.attrib(default="")
    value: int = attr.attrib(default=0)


_BAG_TARGET = f"{_Bag.__module__}.{_Bag.__qualname__}"


# ---------------------------------------------------------------------------
# 1. Basic deep-copy, no overrides
# ---------------------------------------------------------------------------


def test_basic_deepcopy_no_overrides():
    container = _yaml_to_container(
        """
        a:
          name: alpha
          value: 1
        b:
          _inherits_: a
        """
    )
    result = _resolve_inherits_(container, container)
    assert result["b"] == {"name": "alpha", "value": 1}
    # Mutating b must not affect a (deepcopy invariant)
    result["b"]["name"] = "MUTATED"
    assert result["a"]["name"] == "alpha"


# ---------------------------------------------------------------------------
# 2. Override top-level keys
# ---------------------------------------------------------------------------


def test_override_top_level_keys():
    container = _yaml_to_container(
        """
        a:
          name: alpha
          value: 1
        b:
          _inherits_: a
          value: 99
        """
    )
    result = _resolve_inherits_(container, container)
    assert result["b"] == {"name": "alpha", "value": 99}


# ---------------------------------------------------------------------------
# 3. Override nested dict — recursive merge
# ---------------------------------------------------------------------------


def test_override_nested_dict_recursive_merge():
    container = _yaml_to_container(
        """
        a:
          inner:
            y: 1
            z: 2
        b:
          _inherits_: a
          inner:
            y: 99
        """
    )
    result = _resolve_inherits_(container, container)
    # Recursive merge: y overridden, z preserved
    assert result["b"]["inner"] == {"y": 99, "z": 2}


# ---------------------------------------------------------------------------
# 4. Override list — replaces wholesale
# ---------------------------------------------------------------------------


def test_override_list_replaces_wholesale():
    container = _yaml_to_container(
        """
        a:
          items: [1, 2, 3]
        b:
          _inherits_: a
          items: [9]
        """
    )
    result = _resolve_inherits_(container, container)
    # Lists are replaced, not merged
    assert result["b"]["items"] == [9]


# ---------------------------------------------------------------------------
# 5. Dotted path resolution
# ---------------------------------------------------------------------------


def test_dotted_path_resolution():
    container = _yaml_to_container(
        """
        foo:
          bar:
            baz:
              x: 42
        target:
          _inherits_: foo.bar.baz
        """
    )
    result = _resolve_inherits_(container, container)
    assert result["target"] == {"x": 42}


# ---------------------------------------------------------------------------
# 6. List-index path resolution
# ---------------------------------------------------------------------------


def test_list_index_path_resolution():
    container = _yaml_to_container(
        """
        flow_configs:
          - initial:
              x: 1
            followup:
              y: 2
          - initial:
              x: 99
            followup:
              y: 100
        target:
          _inherits_: flow_configs.0.initial
        """
    )
    result = _resolve_inherits_(container, container)
    assert result["target"] == {"x": 1}


# ---------------------------------------------------------------------------
# 7. Chained inheritance
# ---------------------------------------------------------------------------


def test_chained_inheritance():
    container = _yaml_to_container(
        """
        a:
          x: 1
        b:
          _inherits_: a
          y: 2
        c:
          _inherits_: b
          z: 3
        """
    )
    result = _resolve_inherits_(container, container)
    # c chains: a -> b -> c, so c has all three keys
    assert result["c"] == {"x": 1, "y": 2, "z": 3}


# ---------------------------------------------------------------------------
# 8. Order independence (lexically)
# ---------------------------------------------------------------------------


def test_order_independence_lexical():
    container = _yaml_to_container(
        """
        b:
          _inherits_: a
          extra: from_b
        a:
          base_key: from_a
        """
    )
    result = _resolve_inherits_(container, container)
    # b is defined lexically BEFORE a but still resolves correctly
    assert result["b"] == {"base_key": "from_a", "extra": "from_b"}


# ---------------------------------------------------------------------------
# 9. Cycle detection — self-loop
# ---------------------------------------------------------------------------


def test_cycle_detection_self():
    container = _yaml_to_container(
        """
        a:
          _inherits_: a
        """
    )
    with pytest.raises(ValueError, match="cycle"):
        _resolve_inherits_(container, container)


# ---------------------------------------------------------------------------
# 10. Cycle detection — multi-step chain
# ---------------------------------------------------------------------------


def test_cycle_detection_chain():
    container = _yaml_to_container(
        """
        a:
          _inherits_: b
        b:
          _inherits_: a
        """
    )
    with pytest.raises(ValueError, match="cycle") as exc_info:
        _resolve_inherits_(container, container)
    # Error message names at least one of the paths
    assert "a" in str(exc_info.value) and "b" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 11. Non-existent path raises clear error
# ---------------------------------------------------------------------------


def test_nonexistent_path_raises():
    container = _yaml_to_container(
        """
        target:
          _inherits_: does.not.exist
        """
    )
    with pytest.raises(ValueError, match="does.not.exist"):
        _resolve_inherits_(container, container)


# ---------------------------------------------------------------------------
# 12. _inherits_ value must be a string (no multi-inheritance)
# ---------------------------------------------------------------------------


def test_inherits_value_must_be_string_not_list():
    container = {
        "a": {"x": 1},
        "b": {"x": 2},
        "c": {"_inherits_": ["a", "b"]},
    }
    with pytest.raises(TypeError, match="string"):
        _resolve_inherits_(container, container)


def test_inherits_value_must_be_string_not_int():
    container = {"a": {"x": 1}, "b": {"_inherits_": 42}}
    with pytest.raises(TypeError, match="string"):
        _resolve_inherits_(container, container)


# ---------------------------------------------------------------------------
# 13. Directive stripped from output
# ---------------------------------------------------------------------------


def test_directive_stripped_from_output():
    container = _yaml_to_container(
        """
        a:
          x: 1
        b:
          _inherits_: a
          y: 2
        """
    )
    result = _resolve_inherits_(container, container)
    assert "_inherits_" not in result["b"]
    # And `a` itself never had it
    assert "_inherits_" not in result["a"]


# ---------------------------------------------------------------------------
# 14. OmegaConf interpolation — absolute (root-relative) after inheritance
# ---------------------------------------------------------------------------


def test_omegaconf_interpolation_absolute_after_inherit(tmp_path):
    yaml_path = _write_yaml(
        tmp_path,
        """
        root_var: /from_root
        a:
          path: ${root_var}/foo
        b:
          _inherits_: a
          root_var: /from_b_local
        """,
    )
    cfg = load_config(yaml_path)
    # Absolute interpolation: b.path resolves against the ROOT root_var,
    # not b's local override. Documents the footgun.
    assert cfg.b.path == "/from_root/foo"


# ---------------------------------------------------------------------------
# 15. OmegaConf interpolation — relative form ${.field} respects local context
# ---------------------------------------------------------------------------


def test_omegaconf_relative_interpolation_after_inherit(tmp_path):
    yaml_path = _write_yaml(
        tmp_path,
        """
        a:
          local_var: /from_a
          path: ${.local_var}/foo
        b:
          _inherits_: a
          local_var: /from_b
        """,
    )
    cfg = load_config(yaml_path)
    # Relative ${.local_var} resolves against the inheritor's local context
    # since after the deepcopy+merge, b has its own local_var.
    assert cfg.b.path == "/from_b/foo"


# ---------------------------------------------------------------------------
# 16. End-to-end: distinct Python instances through instantiate()
# ---------------------------------------------------------------------------


def test_distinct_python_instances_through_hydra_pipeline(tmp_path):
    yaml_path = _write_yaml(
        tmp_path,
        f"""
        a:
          _target_: {_BAG_TARGET}
          name: alpha
          value: 1
        b:
          _inherits_: a
          name: beta
        """,
    )
    cfg = load_config(yaml_path)
    result = instantiate(cfg)
    # Top-level dict (no _target_); Hydra returns a dict whose values are
    # the instantiated targets.
    a_obj = result["a"]
    b_obj = result["b"]
    assert isinstance(a_obj, _Bag)
    assert isinstance(b_obj, _Bag)
    # Distinct instances — critical invariant
    assert a_obj is not b_obj
    # Override applied
    assert a_obj.name == "alpha"
    assert b_obj.name == "beta"
    # Inherited field preserved
    assert b_obj.value == 1


# ---------------------------------------------------------------------------
# 17. _inherits_ inside an inherited dict (nested directive)
# ---------------------------------------------------------------------------


def test_inherits_inside_inherited_dict():
    container = _yaml_to_container(
        """
        c:
          z: 2
        a:
          inner:
            _inherits_: c
            extra: 1
        b:
          _inherits_: a
        """
    )
    result = _resolve_inherits_(container, container)
    # b inherits a; a's inner has _inherits_: c. After full resolution,
    # b.inner should have c's content + a.inner.extra.
    assert result["b"]["inner"] == {"z": 2, "extra": 1}
    # And a.inner is also resolved in place (a's inner has _inherits_: c)
    assert result["a"]["inner"] == {"z": 2, "extra": 1}
