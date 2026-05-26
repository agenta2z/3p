"""Property-based tests for Serializable file serialization.

This module contains property-based tests using hypothesis to verify
the Serializable mixin's file serialization behavior.

**Feature: serializable-mixin, Property 4: File Serialization Creates Valid File**
**Validates: Requirements 1.8, 1.9**
"""
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

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


# Test class that inherits from Serializable
@dataclass
class FileTestSerializable(Serializable):
    """Dataclass for testing file serialization."""
    name: str
    value: int
    tags: List[str]


# Strategies for generating test data
name_strategy = st.text(min_size=1, max_size=30, alphabet=st.characters(
    whitelist_categories=('L', 'N'),
    blacklist_characters='\x00'
))
value_strategy = st.integers(min_value=-10000, max_value=10000)
tags_strategy = st.lists(
    st.text(min_size=1, max_size=10, alphabet=st.characters(
        whitelist_categories=('L', 'N'),
        blacklist_characters='\x00'
    )),
    min_size=0,
    max_size=5
)


@st.composite
def file_test_serializable_strategy(draw):
    """Generate FileTestSerializable instances."""
    name = draw(name_strategy)
    value = draw(value_strategy)
    tags = draw(tags_strategy)
    return FileTestSerializable(name=name, value=value, tags=tags)


# **Feature: serializable-mixin, Property 4: File Serialization Creates Valid File**
# **Validates: Requirements 1.8, 1.9**
@settings(max_examples=100)
@given(obj=file_test_serializable_strategy())
def test_json_file_serialization_creates_valid_file(obj: FileTestSerializable):
    """Property: For any Serializable object and valid file path, calling
    serialize(path=path, output_format='json') SHALL create a file containing
    valid JSON that can be deserialized.
    
    This validates that JSON file serialization works correctly.
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = f.name
    
    try:
        # Serialize to file
        obj.serialize(output_format='json', path=temp_path)
        
        # Verify file exists
        assert os.path.exists(temp_path), f"File should exist at {temp_path}"
        
        # Verify file is not empty
        file_size = os.path.getsize(temp_path)
        assert file_size > 0, "File should not be empty"
        
        # Verify file can be deserialized
        restored = FileTestSerializable.deserialize(temp_path, output_format='json')
        
        # Verify data integrity
        assert restored.name == obj.name, f"Name mismatch: {restored.name} != {obj.name}"
        assert restored.value == obj.value, f"Value mismatch: {restored.value} != {obj.value}"
        assert restored.tags == obj.tags, f"Tags mismatch: {restored.tags} != {obj.tags}"
    finally:
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)


# **Feature: serializable-mixin, Property 4: File Serialization Creates Valid File**
# **Validates: Requirements 1.8, 1.9**
@settings(max_examples=100)
@given(obj=file_test_serializable_strategy())
def test_yaml_file_serialization_creates_valid_file(obj: FileTestSerializable):
    """Property: For any Serializable object and valid file path, calling
    serialize(path=path, output_format='yaml') SHALL create a file containing
    valid YAML that can be deserialized.
    
    This validates that YAML file serialization works correctly.
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        temp_path = f.name
    
    try:
        # Serialize to file
        obj.serialize(output_format='yaml', path=temp_path)
        
        # Verify file exists
        assert os.path.exists(temp_path), f"File should exist at {temp_path}"
        
        # Verify file is not empty
        file_size = os.path.getsize(temp_path)
        assert file_size > 0, "File should not be empty"
        
        # Verify file can be deserialized
        restored = FileTestSerializable.deserialize(temp_path, output_format='yaml')
        
        # Verify data integrity
        assert restored.name == obj.name, f"Name mismatch: {restored.name} != {obj.name}"
        assert restored.value == obj.value, f"Value mismatch: {restored.value} != {obj.value}"
        assert restored.tags == obj.tags, f"Tags mismatch: {restored.tags} != {obj.tags}"
    finally:
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)


# **Feature: serializable-mixin, Property 4: File Serialization Creates Valid File**
# **Validates: Requirements 1.8, 1.9**
@settings(max_examples=100, deadline=None)
@given(obj=file_test_serializable_strategy())
def test_pickle_file_serialization_creates_valid_file(obj: FileTestSerializable):
    """Property: For any Serializable object and valid file path, calling
    serialize(path=path, output_format='pickle') SHALL create a file containing
    valid pickle data that can be deserialized.
    
    This validates that pickle file serialization works correctly.
    """
    with tempfile.NamedTemporaryFile(mode='wb', suffix='.pkl', delete=False) as f:
        temp_path = f.name
    
    try:
        # Serialize to file
        obj.serialize(output_format='pickle', path=temp_path)
        
        # Verify file exists
        assert os.path.exists(temp_path), f"File should exist at {temp_path}"
        
        # Verify file is not empty
        file_size = os.path.getsize(temp_path)
        assert file_size > 0, "File should not be empty"
        
        # Verify file can be deserialized
        restored = FileTestSerializable.deserialize(temp_path, output_format='pickle')
        
        # Verify data integrity
        assert restored.name == obj.name, f"Name mismatch: {restored.name} != {obj.name}"
        assert restored.value == obj.value, f"Value mismatch: {restored.value} != {obj.value}"
        assert restored.tags == obj.tags, f"Tags mismatch: {restored.tags} != {obj.tags}"
    finally:
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)


# **Feature: serializable-mixin, Property 4: File Serialization Creates Valid File**
# **Validates: Requirements 1.8, 1.9**
@settings(max_examples=50)
@given(obj=file_test_serializable_strategy())
def test_serialize_returns_string_when_no_path(obj: FileTestSerializable):
    """Property: For any Serializable object, calling serialize() without a path
    SHALL return a string representation that can be deserialized.
    
    This validates that string serialization works correctly.
    """
    # Serialize to string (no path)
    json_str = obj.serialize(output_format='json')
    
    # Verify it's a string
    assert isinstance(json_str, str), f"Expected string, got {type(json_str)}"
    
    # Verify it can be deserialized
    restored = FileTestSerializable.deserialize(json_str, output_format='json')
    
    # Verify data integrity
    assert restored.name == obj.name
    assert restored.value == obj.value
    assert restored.tags == obj.tags


if __name__ == '__main__':
    print("Running property-based tests for file serialization...")
    print()
    
    tests = [
        ("JSON file serialization creates valid file",
         test_json_file_serialization_creates_valid_file),
        ("YAML file serialization creates valid file",
         test_yaml_file_serialization_creates_valid_file),
        ("Pickle file serialization creates valid file",
         test_pickle_file_serialization_creates_valid_file),
        ("Serialize returns string when no path",
         test_serialize_returns_string_when_no_path),
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
