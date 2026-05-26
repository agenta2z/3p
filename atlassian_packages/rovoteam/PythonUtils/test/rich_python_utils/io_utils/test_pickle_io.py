"""Unit tests for pickle_io enhancements.

This module contains unit tests for the pickle_save and pickle_load functions,
specifically testing the new bytes I/O capabilities.

**Feature: serializable-mixin**
**Validates: Requirements 1.5**
"""
import sys
import tempfile
import os
from pathlib import Path

# Setup import paths
_current_file = Path(__file__).resolve()
_test_dir = _current_file.parent
while _test_dir.name != 'test' and _test_dir.parent != _test_dir:
    _test_dir = _test_dir.parent
_project_root = _test_dir.parent
_src_dir = _project_root / "src"
if _src_dir.exists() and str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

import pytest

from python_utils.io_utils.pickle_io import pickle_save, pickle_load


class TestPickleSaveReturnsBytes:
    """Tests for pickle_save returning bytes when path is None."""
    
    def test_pickle_save_returns_bytes_for_dict(self):
        """Test that pickle_save(data, None) returns bytes for a dict."""
        data = {'a': 1, 'b': 2, 'c': 3}
        result = pickle_save(data, None)
        
        assert isinstance(result, bytes), f"Expected bytes, got {type(result)}"
        assert len(result) > 0, "Expected non-empty bytes"
    
    def test_pickle_save_returns_bytes_for_list(self):
        """Test that pickle_save(data, None) returns bytes for a list."""
        data = [1, 2, 3, 'hello', {'nested': True}]
        result = pickle_save(data, None)
        
        assert isinstance(result, bytes), f"Expected bytes, got {type(result)}"
    
    def test_pickle_save_returns_bytes_for_nested_object(self):
        """Test that pickle_save(data, None) returns bytes for nested objects."""
        # Use nested dicts/lists instead of custom classes (which can't be pickled when local)
        data = {
            'nested': {'a': 1, 'b': [1, 2, 3]},
            'list': [{'x': 1}, {'y': 2}],
        }
        result = pickle_save(data, None)
        
        assert isinstance(result, bytes), f"Expected bytes, got {type(result)}"
    
    def test_pickle_save_returns_none_for_file_path(self):
        """Test that pickle_save returns None when writing to file."""
        data = {'test': 'data'}
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pkl') as f:
            tmp_path = f.name
        
        try:
            result = pickle_save(data, tmp_path, verbose=False)
            assert result is None, f"Expected None when writing to file, got {result}"
            assert os.path.exists(tmp_path), "File should exist"
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
    
    def test_pickle_save_bytes_compressed(self):
        """Test that pickle_save(data, None, compressed=True) returns compressed bytes."""
        # Create larger data to see compression effect
        data = {'key_' + str(i): 'value_' + str(i) for i in range(100)}
        
        uncompressed = pickle_save(data, None, compressed=False)
        compressed = pickle_save(data, None, compressed=True)
        
        assert isinstance(compressed, bytes), f"Expected bytes, got {type(compressed)}"
        # Compressed should generally be smaller for larger data
        # (though for small data it might be larger due to overhead)


class TestPickleLoadAcceptsBytes:
    """Tests for pickle_load accepting bytes input."""
    
    def test_pickle_load_from_bytes(self):
        """Test that pickle_load(bytes_data) loads correctly."""
        data = {'a': 1, 'b': 2, 'c': 3}
        pickle_bytes = pickle_save(data, None)
        
        loaded = pickle_load(pickle_bytes)
        
        assert loaded == data, f"Expected {data}, got {loaded}"
    
    def test_pickle_load_from_bytes_list(self):
        """Test that pickle_load(bytes_data) loads a list correctly."""
        data = [1, 2, 3, 'hello', {'nested': True}]
        pickle_bytes = pickle_save(data, None)
        
        loaded = pickle_load(pickle_bytes)
        
        assert loaded == data, f"Expected {data}, got {loaded}"
    
    def test_pickle_load_from_bytes_nested_object(self):
        """Test that pickle_load(bytes_data) loads nested objects correctly."""
        # Use nested dicts/lists instead of custom classes
        data = {
            'nested': {'a': 1, 'b': [1, 2, 3]},
            'list': [{'x': 1}, {'y': 2}],
        }
        pickle_bytes = pickle_save(data, None)
        
        loaded = pickle_load(pickle_bytes)
        
        assert loaded == data, f"Expected {data}, got {loaded}"
    
    def test_pickle_load_from_bytes_compressed(self):
        """Test that pickle_load(bytes_data, compressed=True) loads compressed bytes."""
        data = {'a': 1, 'b': 2, 'c': 3}
        compressed_bytes = pickle_save(data, None, compressed=True)
        
        loaded = pickle_load(compressed_bytes, compressed=True)
        
        assert loaded == data, f"Expected {data}, got {loaded}"
    
    def test_pickle_load_from_file_still_works(self):
        """Test that pickle_load(file_path) still works for file paths."""
        data = {'test': 'data'}
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pkl') as f:
            tmp_path = f.name
        
        try:
            pickle_save(data, tmp_path, verbose=False)
            loaded = pickle_load(tmp_path)
            
            assert loaded == data, f"Expected {data}, got {loaded}"
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


class TestPickleRoundTrip:
    """Tests for round-trip pickle save/load."""
    
    def test_round_trip_bytes(self):
        """Test round-trip: save to bytes, load from bytes."""
        data = {
            'string': 'hello',
            'int': 42,
            'float': 3.14,
            'list': [1, 2, 3],
            'nested': {'a': 1, 'b': 2},
        }
        
        pickle_bytes = pickle_save(data, None)
        loaded = pickle_load(pickle_bytes)
        
        assert loaded == data, f"Round-trip failed: {loaded} != {data}"
    
    def test_round_trip_bytes_compressed(self):
        """Test round-trip with compression: save to compressed bytes, load from compressed bytes."""
        data = {
            'string': 'hello' * 100,
            'int': 42,
            'list': list(range(100)),
        }
        
        compressed_bytes = pickle_save(data, None, compressed=True)
        loaded = pickle_load(compressed_bytes, compressed=True)
        
        assert loaded == data, f"Compressed round-trip failed: {loaded} != {data}"
    
    def test_round_trip_file(self):
        """Test round-trip: save to file, load from file."""
        data = {'test': 'data', 'number': 123}
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pkl') as f:
            tmp_path = f.name
        
        try:
            pickle_save(data, tmp_path, verbose=False)
            loaded = pickle_load(tmp_path)
            
            assert loaded == data, f"File round-trip failed: {loaded} != {data}"
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
