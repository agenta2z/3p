"""Property-based tests for Serializable mixin.

This module contains property-based tests using hypothesis to verify
the Serializable mixin's serialization round-trip behavior.

**Feature: serializable-mixin, Property 1: Serialization Round-Trip Preserves Data**
**Validates: Requirements 7.1, 7.2, 7.4**
"""
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

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

from python_utils.common_objects.serializable import (
    Serializable,
    SerializationMode,
    FIELD_TYPE,
    FIELD_MODULE,
    FIELD_SERIALIZATION,
    FIELD_DATA,
    SERIALIZATION_DICT,
)


# Test class that inherits from Serializable
@dataclass
class SimpleSerializable(Serializable):
    """Simple dataclass for testing serialization."""
    name: str
    value: int
    active: bool = True


@dataclass
class NestedSerializable(Serializable):
    """Nested dataclass for testing serialization."""
    title: str
    items: List[str]
    metadata: Dict[str, Any]


# Strategies for generating test data
name_strategy = st.text(min_size=1, max_size=50, alphabet=st.characters(
    whitelist_categories=('L', 'N', 'P', 'S'),
    blacklist_characters='\x00'
))
value_strategy = st.integers(min_value=-1000000, max_value=1000000)
bool_strategy = st.booleans()

# Strategy for generating simple serializable objects
@st.composite
def simple_serializable_strategy(draw):
    """Generate SimpleSerializable instances."""
    name = draw(name_strategy)
    value = draw(value_strategy)
    active = draw(bool_strategy)
    return SimpleSerializable(name=name, value=value, active=active)


# Strategy for generating nested serializable objects
@st.composite
def nested_serializable_strategy(draw):
    """Generate NestedSerializable instances."""
    title = draw(name_strategy)
    items = draw(st.lists(name_strategy, min_size=0, max_size=5))
    metadata = draw(st.dictionaries(
        keys=st.text(min_size=1, max_size=10, alphabet=st.characters(
            whitelist_categories=('L', 'N'),
            blacklist_characters='\x00'
        )),
        values=st.one_of(
            st.integers(),
            st.text(max_size=20),
            st.booleans(),
        ),
        max_size=5,
    ))
    return NestedSerializable(title=title, items=items, metadata=metadata)


# **Feature: serializable-mixin, Property 1: Serialization Round-Trip Preserves Data**
# **Validates: Requirements 7.1, 7.2, 7.4**
@settings(max_examples=100)
@given(obj=simple_serializable_strategy())
def test_json_round_trip_preserves_simple_data(obj: SimpleSerializable):
    """Property: For any SimpleSerializable object, serializing to JSON then
    deserializing SHALL produce an object with identical primitive values.
    
    This validates that JSON round-trip preserves data integrity.
    """
    # Serialize to JSON
    json_str = obj.serialize(output_format='json')
    
    # Deserialize back
    restored = SimpleSerializable.deserialize(json_str, output_format='json')
    
    # Verify all fields are preserved
    assert restored.name == obj.name, f"Name mismatch: {restored.name} != {obj.name}"
    assert restored.value == obj.value, f"Value mismatch: {restored.value} != {obj.value}"
    assert restored.active == obj.active, f"Active mismatch: {restored.active} != {obj.active}"


# **Feature: serializable-mixin, Property 1: Serialization Round-Trip Preserves Data**
# **Validates: Requirements 7.1, 7.2, 7.4**
@settings(max_examples=100)
@given(obj=nested_serializable_strategy())
def test_json_round_trip_preserves_nested_data(obj: NestedSerializable):
    """Property: For any NestedSerializable object with nested structures,
    serializing to JSON then deserializing SHALL preserve nested object structures.
    
    This validates that JSON round-trip preserves nested data integrity.
    """
    # Serialize to JSON
    json_str = obj.serialize(output_format='json')
    
    # Deserialize back
    restored = NestedSerializable.deserialize(json_str, output_format='json')
    
    # Verify all fields are preserved
    assert restored.title == obj.title, f"Title mismatch: {restored.title} != {obj.title}"
    assert restored.items == obj.items, f"Items mismatch: {restored.items} != {obj.items}"
    assert restored.metadata == obj.metadata, f"Metadata mismatch: {restored.metadata} != {obj.metadata}"


# **Feature: serializable-mixin, Property 1: Serialization Round-Trip Preserves Data**
# **Validates: Requirements 7.1, 7.2, 7.4**
@settings(max_examples=100)
@given(obj=simple_serializable_strategy())
def test_to_serializable_obj_contains_metadata(obj: SimpleSerializable):
    """Property: For any Serializable object, to_serializable_obj() SHALL return
    a dict containing type metadata and the original data.
    
    This validates that serializable objects contain proper metadata.
    """
    serializable_obj = obj.to_serializable_obj()
    
    # Verify metadata fields
    assert FIELD_TYPE in serializable_obj, f"Missing {FIELD_TYPE} field"
    assert FIELD_MODULE in serializable_obj, f"Missing {FIELD_MODULE} field"
    assert FIELD_SERIALIZATION in serializable_obj, f"Missing {FIELD_SERIALIZATION} field"
    assert FIELD_DATA in serializable_obj, f"Missing {FIELD_DATA} field"
    
    # Verify metadata values
    assert serializable_obj[FIELD_TYPE] == 'SimpleSerializable'
    assert serializable_obj[FIELD_SERIALIZATION] == SERIALIZATION_DICT
    
    # Verify data contains original values
    data = serializable_obj[FIELD_DATA]
    assert data['name'] == obj.name
    assert data['value'] == obj.value
    assert data['active'] == obj.active


# **Feature: serializable-mixin, Property 1: Serialization Round-Trip Preserves Data**
# **Validates: Requirements 7.1, 7.2, 7.4**
@settings(max_examples=100)
@given(obj=simple_serializable_strategy())
def test_from_serializable_obj_reconstructs_instance(obj: SimpleSerializable):
    """Property: For any Serializable object, from_serializable_obj() SHALL
    reconstruct an instance with identical field values.
    
    This validates that deserialization properly reconstructs objects.
    """
    # Convert to serializable object
    serializable_obj = obj.to_serializable_obj()
    
    # Reconstruct from serializable object
    restored = SimpleSerializable.from_serializable_obj(serializable_obj)
    
    # Verify reconstruction
    assert restored.name == obj.name
    assert restored.value == obj.value
    assert restored.active == obj.active


if __name__ == '__main__':
    print("Running property-based tests for Serializable mixin...")
    print()
    
    tests = [
        ("JSON round-trip preserves simple data",
         test_json_round_trip_preserves_simple_data),
        ("JSON round-trip preserves nested data",
         test_json_round_trip_preserves_nested_data),
        ("to_serializable_obj contains metadata",
         test_to_serializable_obj_contains_metadata),
        ("from_serializable_obj reconstructs instance",
         test_from_serializable_obj_reconstructs_instance),
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
