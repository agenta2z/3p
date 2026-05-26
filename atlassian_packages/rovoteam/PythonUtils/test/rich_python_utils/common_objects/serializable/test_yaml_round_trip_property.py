"""Property-based tests for Serializable YAML round-trip.

This module contains property-based tests using hypothesis to verify
the Serializable mixin's YAML serialization round-trip behavior.

**Feature: serializable-mixin, Property 2: YAML Round-Trip Preserves Data**
**Validates: Requirements 7.3**
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

from python_utils.common_objects.serializable import Serializable


# Test classes that inherit from Serializable
@dataclass
class YamlSimpleSerializable(Serializable):
    """Simple dataclass for testing YAML serialization."""
    name: str
    value: int
    enabled: bool = True


@dataclass
class YamlNestedSerializable(Serializable):
    """Nested dataclass for testing YAML serialization."""
    title: str
    count: int
    items: List[str]
    config: Dict[str, Any]


@dataclass
class YamlComplexSerializable(Serializable):
    """Complex dataclass with optional fields for testing YAML serialization."""
    id: str
    score: float
    tags: List[str]
    metadata: Dict[str, Any]
    description: Optional[str] = None


# Strategies for generating test data
safe_text_strategy = st.text(
    min_size=1, 
    max_size=30, 
    alphabet=st.characters(
        whitelist_categories=('L', 'N'),
        blacklist_characters='\x00\n\r\t'
    )
)

value_strategy = st.integers(min_value=-10000, max_value=10000)
float_strategy = st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False)
bool_strategy = st.booleans()

tags_strategy = st.lists(
    safe_text_strategy,
    min_size=0,
    max_size=5
)

simple_dict_strategy = st.dictionaries(
    keys=safe_text_strategy,
    values=st.one_of(
        st.integers(min_value=-1000, max_value=1000),
        safe_text_strategy,
        st.booleans(),
    ),
    max_size=5,
)


@st.composite
def yaml_simple_strategy(draw):
    """Generate YamlSimpleSerializable instances."""
    name = draw(safe_text_strategy)
    value = draw(value_strategy)
    enabled = draw(bool_strategy)
    return YamlSimpleSerializable(name=name, value=value, enabled=enabled)


@st.composite
def yaml_nested_strategy(draw):
    """Generate YamlNestedSerializable instances."""
    title = draw(safe_text_strategy)
    count = draw(value_strategy)
    items = draw(tags_strategy)
    config = draw(simple_dict_strategy)
    return YamlNestedSerializable(title=title, count=count, items=items, config=config)


@st.composite
def yaml_complex_strategy(draw):
    """Generate YamlComplexSerializable instances."""
    id_val = draw(safe_text_strategy)
    score = draw(float_strategy)
    tags = draw(tags_strategy)
    metadata = draw(simple_dict_strategy)
    description = draw(st.one_of(st.none(), safe_text_strategy))
    return YamlComplexSerializable(
        id=id_val, score=score, tags=tags, metadata=metadata, description=description
    )


# **Feature: serializable-mixin, Property 2: YAML Round-Trip Preserves Data**
# **Validates: Requirements 7.3**
@settings(max_examples=100)
@given(obj=yaml_simple_strategy())
def test_yaml_round_trip_preserves_simple_data(obj: YamlSimpleSerializable):
    """Property: For any YamlSimpleSerializable object with primitive values,
    serializing to YAML then deserializing SHALL produce an object with
    identical primitive values.
    
    This validates that YAML round-trip preserves simple data integrity.
    """
    # Serialize to YAML
    yaml_str = obj.serialize(output_format='yaml')
    
    # Deserialize back
    restored = YamlSimpleSerializable.deserialize(yaml_str, output_format='yaml')
    
    # Verify all fields are preserved
    assert restored.name == obj.name, f"Name mismatch: {restored.name} != {obj.name}"
    assert restored.value == obj.value, f"Value mismatch: {restored.value} != {obj.value}"
    assert restored.enabled == obj.enabled, f"Enabled mismatch: {restored.enabled} != {obj.enabled}"


# **Feature: serializable-mixin, Property 2: YAML Round-Trip Preserves Data**
# **Validates: Requirements 7.3**
@settings(max_examples=100)
@given(obj=yaml_nested_strategy())
def test_yaml_round_trip_preserves_nested_data(obj: YamlNestedSerializable):
    """Property: For any YamlNestedSerializable object with nested structures,
    serializing to YAML then deserializing SHALL preserve nested object structures.
    
    This validates that YAML round-trip preserves nested data integrity.
    """
    # Serialize to YAML
    yaml_str = obj.serialize(output_format='yaml')
    
    # Deserialize back
    restored = YamlNestedSerializable.deserialize(yaml_str, output_format='yaml')
    
    # Verify all fields are preserved
    assert restored.title == obj.title, f"Title mismatch: {restored.title} != {obj.title}"
    assert restored.count == obj.count, f"Count mismatch: {restored.count} != {obj.count}"
    assert restored.items == obj.items, f"Items mismatch: {restored.items} != {obj.items}"
    assert restored.config == obj.config, f"Config mismatch: {restored.config} != {obj.config}"


# **Feature: serializable-mixin, Property 2: YAML Round-Trip Preserves Data**
# **Validates: Requirements 7.3**
@settings(max_examples=100)
@given(obj=yaml_complex_strategy())
def test_yaml_round_trip_preserves_complex_data(obj: YamlComplexSerializable):
    """Property: For any YamlComplexSerializable object with optional fields,
    serializing to YAML then deserializing SHALL preserve all field values
    including optional fields.
    
    This validates that YAML round-trip preserves complex data integrity.
    """
    # Serialize to YAML
    yaml_str = obj.serialize(output_format='yaml')
    
    # Deserialize back
    restored = YamlComplexSerializable.deserialize(yaml_str, output_format='yaml')
    
    # Verify all fields are preserved
    assert restored.id == obj.id, f"ID mismatch: {restored.id} != {obj.id}"
    # Use approximate comparison for floats
    assert abs(restored.score - obj.score) < 1e-6, f"Score mismatch: {restored.score} != {obj.score}"
    assert restored.tags == obj.tags, f"Tags mismatch: {restored.tags} != {obj.tags}"
    assert restored.metadata == obj.metadata, f"Metadata mismatch: {restored.metadata} != {obj.metadata}"
    assert restored.description == obj.description, f"Description mismatch: {restored.description} != {obj.description}"


# **Feature: serializable-mixin, Property 2: YAML Round-Trip Preserves Data**
# **Validates: Requirements 7.3**
@settings(max_examples=50)
@given(
    name=safe_text_strategy,
    value=value_strategy,
)
def test_yaml_round_trip_multiple_cycles(name: str, value: int):
    """Property: For any Serializable object, multiple YAML round-trips
    SHALL produce identical results (idempotent serialization).
    
    This validates that YAML serialization is stable across multiple cycles.
    """
    obj = YamlSimpleSerializable(name=name, value=value, enabled=True)
    
    # First round-trip
    yaml_str1 = obj.serialize(output_format='yaml')
    restored1 = YamlSimpleSerializable.deserialize(yaml_str1, output_format='yaml')
    
    # Second round-trip
    yaml_str2 = restored1.serialize(output_format='yaml')
    restored2 = YamlSimpleSerializable.deserialize(yaml_str2, output_format='yaml')
    
    # Verify both round-trips produce identical results
    assert restored1.name == restored2.name
    assert restored1.value == restored2.value
    assert restored1.enabled == restored2.enabled


if __name__ == '__main__':
    print("Running property-based tests for YAML round-trip...")
    print()
    
    tests = [
        ("YAML round-trip preserves simple data",
         test_yaml_round_trip_preserves_simple_data),
        ("YAML round-trip preserves nested data",
         test_yaml_round_trip_preserves_nested_data),
        ("YAML round-trip preserves complex data",
         test_yaml_round_trip_preserves_complex_data),
        ("YAML round-trip multiple cycles",
         test_yaml_round_trip_multiple_cycles),
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
