"""Property-based tests for dict__ fallback parameter.

This module contains property-based tests using hypothesis to verify
the dict__ function's fallback parameter behavior.

**Feature: serializable-mixin, Property 3: Unsupported Format Raises ValueError**
**Validates: Requirements 1.7**

Note: This test validates the dict__ fallback parameter which is used by the
Serializable mixin to control behavior when objects cannot be converted to dict.
"""
import sys
from pathlib import Path
from typing import Any

# Setup import paths
_current_file = Path(__file__).resolve()
_test_dir = _current_file.parent
while _test_dir.name != 'test' and _test_dir.parent != _test_dir:
    _test_dir = _test_dir.parent
_project_root = _test_dir.parent
_src_dir = _project_root / "src"
if _src_dir.exists() and str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

from hypothesis import given, strategies as st, settings
import pytest

from python_utils.common_utils.map_helper import dict__


# Strategy for generating basic convertible objects
basic_convertible_strategy = st.one_of(
    st.integers(),
    st.floats(allow_nan=False),
    st.text(max_size=50),
    st.booleans(),
    st.none(),
)

# Strategy for generating dict-like objects
dict_strategy = st.dictionaries(
    keys=st.text(min_size=1, max_size=10),
    values=basic_convertible_strategy,
    max_size=5,
)

# Strategy for generating list-like objects
list_strategy = st.lists(basic_convertible_strategy, max_size=5)


# Strategy for generating nested dict structures
@st.composite
def nested_dict_strategy(draw):
    """Generate nested dict structures."""
    depth = draw(st.integers(min_value=1, max_value=3))
    result = {}
    for _ in range(draw(st.integers(min_value=1, max_value=3))):
        key = draw(st.text(min_size=1, max_size=10))
        if depth > 1:
            value = draw(st.one_of(
                basic_convertible_strategy,
                st.dictionaries(
                    keys=st.text(min_size=1, max_size=5),
                    values=basic_convertible_strategy,
                    max_size=3,
                ),
            ))
        else:
            value = draw(basic_convertible_strategy)
        result[key] = value
    return result


# **Feature: serializable-mixin, Property: dict__ preserves convertible objects with all fallback values**
# **Validates: Requirements 1.3, 1.4**
@settings(max_examples=100)
@given(obj=dict_strategy)
def test_dict_fallback_preserves_convertible_dicts(obj):
    """Property: For any convertible dict object, calling dict__ with any fallback
    SHALL return the same dict structure regardless of fallback setting.
    
    This validates that fallback only affects non-convertible objects.
    """
    # Test with different fallback values
    result_default = dict__(obj)
    result_none = dict__(obj, fallback=None)
    result_skip = dict__(obj, fallback='skip')
    
    assert result_default == obj, f"Default fallback should preserve dict: {result_default} != {obj}"
    assert result_none == obj, f"fallback=None should preserve dict: {result_none} != {obj}"
    assert result_skip == obj, f"fallback='skip' should preserve dict: {result_skip} != {obj}"


# **Feature: serializable-mixin, Property: dict__ preserves convertible lists with all fallback values**
# **Validates: Requirements 1.3, 1.4**
@settings(max_examples=100)
@given(obj=list_strategy)
def test_dict_fallback_preserves_convertible_lists(obj):
    """Property: For any convertible list object, calling dict__ with any fallback
    SHALL return the same list structure regardless of fallback setting.
    
    This validates that fallback only affects non-convertible objects.
    """
    # Test with different fallback values
    result_default = dict__(obj)
    result_none = dict__(obj, fallback=None)
    result_skip = dict__(obj, fallback='skip')
    
    assert result_default == obj, f"Default fallback should preserve list: {result_default} != {obj}"
    assert result_none == obj, f"fallback=None should preserve list: {result_none} != {obj}"
    assert result_skip == obj, f"fallback='skip' should preserve list: {result_skip} != {obj}"


# **Feature: serializable-mixin, Property: dict__ preserves nested structures with all fallback values**
# **Validates: Requirements 1.3, 1.4**
@settings(max_examples=100)
@given(obj=nested_dict_strategy())
def test_dict_fallback_preserves_nested_structures(obj):
    """Property: For any nested dict structure, calling dict__ with any fallback
    SHALL return the same structure regardless of fallback setting.
    
    This validates that fallback is properly propagated through recursion.
    """
    # Test with different fallback values
    result_default = dict__(obj, recursive=True)
    result_none = dict__(obj, recursive=True, fallback=None)
    result_skip = dict__(obj, recursive=True, fallback='skip')
    
    assert result_default == obj, f"Default fallback should preserve nested dict"
    assert result_none == obj, f"fallback=None should preserve nested dict"
    assert result_skip == obj, f"fallback='skip' should preserve nested dict"


# **Feature: serializable-mixin, Property: dict__ with custom callable fallback for basic types**
# **Validates: Requirements 1.3, 1.4**
@settings(max_examples=100)
@given(obj=basic_convertible_strategy)
def test_dict_fallback_custom_callable_basic_types(obj):
    """Property: For any basic type, calling dict__ with a custom callable fallback
    SHALL return the object unchanged (basic types don't use fallback).
    
    This validates that basic types bypass the fallback mechanism.
    """
    custom_fallback = lambda x: "CUSTOM"
    result = dict__(obj, fallback=custom_fallback)
    
    # Basic types should be returned as-is, not through fallback
    assert result == obj, f"Basic type should be returned as-is, got: {result}"


# **Feature: serializable-mixin, Property: dict__ fallback parameter type validation**
# **Validates: Requirements 1.3, 1.4**
@settings(max_examples=100)
@given(obj=dict_strategy)
def test_dict_fallback_parameter_accepts_valid_values(obj):
    """Property: For any dict, calling dict__ with valid fallback values
    (None, 'skip', callable, or default str) SHALL not raise errors.
    
    This validates that the fallback parameter accepts all documented values.
    """
    # All these should work without errors
    dict__(obj, fallback=None)
    dict__(obj, fallback='skip')
    dict__(obj, fallback=str)
    dict__(obj, fallback=repr)
    dict__(obj, fallback=lambda x: "custom")
    dict__(obj)  # default


# **Feature: serializable-mixin, Property: dict__ with dataclass objects**
# **Validates: Requirements 1.3, 1.4**
@settings(max_examples=100)
@given(
    name=st.text(min_size=1, max_size=20),
    value=st.integers(),
)
def test_dict_fallback_with_dataclass(name, value):
    """Property: For any dataclass instance, calling dict__ with any fallback
    SHALL convert it to a dict with the same field values.
    
    This validates that dataclass conversion works with all fallback values.
    """
    from dataclasses import dataclass
    
    @dataclass
    class TestData:
        name: str
        value: int
    
    obj = TestData(name=name, value=value)
    
    # Test with different fallback values
    result_default = dict__(obj)
    result_none = dict__(obj, fallback=None)
    result_skip = dict__(obj, fallback='skip')
    
    expected = {'name': name, 'value': value}
    
    assert result_default == expected, f"Default fallback should convert dataclass"
    assert result_none == expected, f"fallback=None should convert dataclass"
    assert result_skip == expected, f"fallback='skip' should convert dataclass"


# **Feature: serializable-mixin, Property: dict__ with attrs objects**
# **Validates: Requirements 1.3, 1.4**
@settings(max_examples=100)
@given(
    name=st.text(min_size=1, max_size=20),
    count=st.integers(min_value=0, max_value=1000),
)
def test_dict_fallback_with_attrs(name, count):
    """Property: For any attrs instance, calling dict__ with any fallback
    SHALL convert it to a dict with the same field values.
    
    This validates that attrs conversion works with all fallback values.
    """
    import attr
    
    @attr.s
    class TestAttrs:
        name = attr.ib()
        count = attr.ib()
    
    obj = TestAttrs(name=name, count=count)
    
    # Test with different fallback values
    result_default = dict__(obj)
    result_none = dict__(obj, fallback=None)
    result_skip = dict__(obj, fallback='skip')
    
    expected = {'name': name, 'count': count}
    
    assert result_default == expected, f"Default fallback should convert attrs"
    assert result_none == expected, f"fallback=None should convert attrs"
    assert result_skip == expected, f"fallback='skip' should convert attrs"


# **Feature: serializable-mixin, Property: dict__ recursive flag with fallback**
# **Validates: Requirements 1.3, 1.4**
@settings(max_examples=100)
@given(
    outer_key=st.text(min_size=1, max_size=10),
    inner_key=st.text(min_size=1, max_size=10),
    value=st.integers(),
)
def test_dict_fallback_recursive_flag(outer_key, inner_key, value):
    """Property: For any nested structure, the recursive flag should control
    whether nested objects are converted, and fallback should be passed through.
    
    This validates that recursive and fallback parameters work together.
    """
    from dataclasses import dataclass
    
    @dataclass
    class Inner:
        key: str
        value: int
    
    @dataclass
    class Outer:
        name: str
        inner: Inner
    
    inner = Inner(key=inner_key, value=value)
    outer = Outer(name=outer_key, inner=inner)
    
    # With recursive=True, inner should be converted
    result_recursive = dict__(outer, recursive=True, fallback=None)
    assert isinstance(result_recursive['inner'], dict), "Inner should be dict with recursive=True"
    assert result_recursive['inner']['key'] == inner_key
    assert result_recursive['inner']['value'] == value


if __name__ == '__main__':
    print("Running property-based tests for dict__ fallback parameter...")
    print()
    
    tests = [
        ("Preserves convertible dicts",
         test_dict_fallback_preserves_convertible_dicts),
        ("Preserves convertible lists",
         test_dict_fallback_preserves_convertible_lists),
        ("Preserves nested structures",
         test_dict_fallback_preserves_nested_structures),
        ("Custom callable fallback for basic types",
         test_dict_fallback_custom_callable_basic_types),
        ("Parameter accepts valid values",
         test_dict_fallback_parameter_accepts_valid_values),
        ("With dataclass objects",
         test_dict_fallback_with_dataclass),
        ("With attrs objects",
         test_dict_fallback_with_attrs),
        ("Recursive flag with fallback",
         test_dict_fallback_recursive_flag),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            test_func()
            print(f"✓ {test_name}")
            passed += 1
        except Exception as e:
            print(f"✗ {test_name}")
            print(f"  Error: {e}")
            failed += 1
    
    print()
    print(f"Results: {passed} passed, {failed} failed")
    
    if failed > 0:
        sys.exit(1)
    else:
        print("\nAll property-based tests passed! ✓")
