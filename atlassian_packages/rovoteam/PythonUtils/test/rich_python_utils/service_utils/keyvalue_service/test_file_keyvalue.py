"""
Unit tests for FileKeyValueService.

Tests cover core CRUD operations, namespace handling, percent-encoding,
malformed JSON handling, context manager protocol, and edge cases.
"""

import json
import os

from python_utils.service_utils.keyvalue_service.file_keyvalue_service import (
    FileKeyValueService,
    _encode_key,
    _decode_key,
)


class TestFileKeyValueServiceBasicOperations:
    """Tests for basic get/put/delete/exists operations."""

    def test_put_and_get(self, tmp_path):
        svc = FileKeyValueService(base_dir=str(tmp_path))
        svc.put("key1", {"name": "Alice"})
        assert svc.get("key1") == {"name": "Alice"}

    def test_get_nonexistent_returns_none(self, tmp_path):
        svc = FileKeyValueService(base_dir=str(tmp_path))
        assert svc.get("nonexistent") is None

    def test_put_overwrites_existing(self, tmp_path):
        svc = FileKeyValueService(base_dir=str(tmp_path))
        svc.put("key1", "value1")
        svc.put("key1", "value2")
        assert svc.get("key1") == "value2"

    def test_delete_existing_key(self, tmp_path):
        svc = FileKeyValueService(base_dir=str(tmp_path))
        svc.put("key1", "value1")
        assert svc.delete("key1") is True
        assert svc.get("key1") is None

    def test_delete_nonexistent_returns_false(self, tmp_path):
        svc = FileKeyValueService(base_dir=str(tmp_path))
        assert svc.delete("nonexistent") is False

    def test_exists_true(self, tmp_path):
        svc = FileKeyValueService(base_dir=str(tmp_path))
        svc.put("key1", "value1")
        assert svc.exists("key1") is True

    def test_exists_false(self, tmp_path):
        svc = FileKeyValueService(base_dir=str(tmp_path))
        assert svc.exists("nonexistent") is False

    def test_put_creates_json_file(self, tmp_path):
        svc = FileKeyValueService(base_dir=str(tmp_path))
        svc.put("mykey", [1, 2, 3])
        expected_path = os.path.join(str(tmp_path), "_default", "mykey.json")
        assert os.path.exists(expected_path)
        with open(expected_path, "r") as f:
            assert json.load(f) == [1, 2, 3]

    def test_stores_various_json_types(self, tmp_path):
        svc = FileKeyValueService(base_dir=str(tmp_path))
        test_values = [
            ("str_val", "hello"),
            ("int_val", 42),
            ("float_val", 3.14),
            ("bool_val", True),
            ("none_val", None),
            ("list_val", [1, "two", 3.0]),
            ("dict_val", {"nested": {"key": "value"}}),
        ]
        for key, value in test_values:
            svc.put(key, value)
            assert svc.get(key) == value


class TestFileKeyValueServiceNamespaces:
    """Tests for namespace-scoped operations."""

    def test_default_namespace_when_none(self, tmp_path):
        svc = FileKeyValueService(base_dir=str(tmp_path))
        svc.put("key1", "value1")
        svc.put("key1", "value2", namespace=None)
        # Both should target _default namespace, so value2 overwrites
        assert svc.get("key1") == "value2"

    def test_separate_namespaces(self, tmp_path):
        svc = FileKeyValueService(base_dir=str(tmp_path))
        svc.put("key1", "ns1_value", namespace="ns1")
        svc.put("key1", "ns2_value", namespace="ns2")
        assert svc.get("key1", namespace="ns1") == "ns1_value"
        assert svc.get("key1", namespace="ns2") == "ns2_value"

    def test_keys_per_namespace(self, tmp_path):
        svc = FileKeyValueService(base_dir=str(tmp_path))
        svc.put("a", 1, namespace="ns1")
        svc.put("b", 2, namespace="ns1")
        svc.put("c", 3, namespace="ns2")
        assert sorted(svc.keys(namespace="ns1")) == ["a", "b"]
        assert svc.keys(namespace="ns2") == ["c"]

    def test_keys_empty_namespace(self, tmp_path):
        svc = FileKeyValueService(base_dir=str(tmp_path))
        assert svc.keys(namespace="nonexistent") == []

    def test_size_per_namespace(self, tmp_path):
        svc = FileKeyValueService(base_dir=str(tmp_path))
        svc.put("a", 1, namespace="ns1")
        svc.put("b", 2, namespace="ns1")
        svc.put("c", 3, namespace="ns2")
        assert svc.size(namespace="ns1") == 2
        assert svc.size(namespace="ns2") == 1

    def test_size_empty_namespace(self, tmp_path):
        svc = FileKeyValueService(base_dir=str(tmp_path))
        assert svc.size(namespace="nonexistent") == 0

    def test_clear_namespace(self, tmp_path):
        svc = FileKeyValueService(base_dir=str(tmp_path))
        svc.put("a", 1, namespace="ns1")
        svc.put("b", 2, namespace="ns1")
        svc.put("c", 3, namespace="ns2")
        count = svc.clear(namespace="ns1")
        assert count == 2
        assert svc.size(namespace="ns1") == 0
        assert svc.size(namespace="ns2") == 1

    def test_clear_empty_namespace(self, tmp_path):
        svc = FileKeyValueService(base_dir=str(tmp_path))
        assert svc.clear(namespace="nonexistent") == 0

    def test_namespaces_list(self, tmp_path):
        svc = FileKeyValueService(base_dir=str(tmp_path))
        svc.put("a", 1, namespace="ns1")
        svc.put("b", 2, namespace="ns2")
        assert sorted(svc.namespaces()) == ["ns1", "ns2"]

    def test_namespaces_empty(self, tmp_path):
        svc = FileKeyValueService(base_dir=str(tmp_path))
        assert svc.namespaces() == []

    def test_delete_cleans_up_empty_namespace_dir(self, tmp_path):
        svc = FileKeyValueService(base_dir=str(tmp_path))
        svc.put("key1", "value1", namespace="ns1")
        svc.delete("key1", namespace="ns1")
        assert "ns1" not in svc.namespaces()
        # Directory should be removed
        assert not os.path.isdir(os.path.join(str(tmp_path), "ns1"))

    def test_namespace_creates_subdirectory(self, tmp_path):
        svc = FileKeyValueService(base_dir=str(tmp_path))
        svc.put("key1", "value1", namespace="my_namespace")
        assert os.path.isdir(os.path.join(str(tmp_path), "my_namespace"))


class TestFileKeyValueServicePercentEncoding:
    """Tests for percent-encoding of keys to produce safe filenames."""

    def test_encode_colon(self):
        assert _encode_key("user:xinli") == "user%3Axinli"

    def test_encode_forward_slash(self):
        assert _encode_key("path/to/thing") == "path%2Fto%2Fthing"

    def test_encode_backslash(self):
        assert _encode_key("back\\slash") == "back%5Cslash"

    def test_encode_percent_first(self):
        """Percent must be encoded before other characters to avoid double-encoding."""
        assert _encode_key("100%") == "100%25"

    def test_encode_percent_before_colon(self):
        """Ensure '%' is encoded before ':' so '%3A' in input doesn't get mangled."""
        assert _encode_key("%3A") == "%253A"

    def test_encode_multiple_special_chars(self):
        assert _encode_key("a:b/c\\d%e") == "a%3Ab%2Fc%5Cd%25e"

    def test_encode_no_special_chars(self):
        assert _encode_key("simple_key") == "simple_key"

    def test_encode_empty_string(self):
        assert _encode_key("") == ""

    def test_decode_reverses_encode(self):
        original = "user:xinli/path\\back%percent"
        assert _decode_key(_encode_key(original)) == original

    def test_decode_colon(self):
        assert _decode_key("user%3Axinli") == "user:xinli"

    def test_decode_forward_slash(self):
        assert _decode_key("path%2Fto%2Fthing") == "path/to/thing"

    def test_decode_backslash(self):
        assert _decode_key("back%5Cslash") == "back\\slash"

    def test_decode_percent(self):
        assert _decode_key("already%25encoded") == "already%encoded"

    def test_put_get_with_special_key(self, tmp_path):
        """Keys with special characters should round-trip correctly."""
        svc = FileKeyValueService(base_dir=str(tmp_path))
        svc.put("user:xinli", {"role": "admin"})
        assert svc.get("user:xinli") == {"role": "admin"}

    def test_keys_returns_decoded_keys(self, tmp_path):
        """keys() should return decoded (original) key strings."""
        svc = FileKeyValueService(base_dir=str(tmp_path))
        svc.put("user:xinli", "v1")
        svc.put("path/to/thing", "v2")
        result = sorted(svc.keys())
        assert result == ["path/to/thing", "user:xinli"]

    def test_exists_with_special_key(self, tmp_path):
        svc = FileKeyValueService(base_dir=str(tmp_path))
        svc.put("a:b/c\\d%e", "value")
        assert svc.exists("a:b/c\\d%e") is True

    def test_delete_with_special_key(self, tmp_path):
        svc = FileKeyValueService(base_dir=str(tmp_path))
        svc.put("user:xinli", "value")
        assert svc.delete("user:xinli") is True
        assert svc.exists("user:xinli") is False


class TestFileKeyValueServiceMalformedJSON:
    """Tests for handling malformed JSON files."""

    def test_malformed_json_returns_none(self, tmp_path):
        """Malformed JSON files should be logged and treated as missing keys."""
        svc = FileKeyValueService(base_dir=str(tmp_path))
        # Create a malformed JSON file manually
        ns_dir = os.path.join(str(tmp_path), "_default")
        os.makedirs(ns_dir, exist_ok=True)
        malformed_path = os.path.join(ns_dir, "bad_key.json")
        with open(malformed_path, "w") as f:
            f.write("{invalid json content")
        assert svc.get("bad_key") is None

    def test_malformed_json_does_not_affect_other_keys(self, tmp_path):
        """Other valid keys should still work when a malformed file exists."""
        svc = FileKeyValueService(base_dir=str(tmp_path))
        svc.put("good_key", "good_value")
        # Create a malformed JSON file
        ns_dir = os.path.join(str(tmp_path), "_default")
        with open(os.path.join(ns_dir, "bad_key.json"), "w") as f:
            f.write("not json")
        assert svc.get("good_key") == "good_value"
        assert svc.get("bad_key") is None


class TestFileKeyValueServiceBatchOperations:
    """Tests for get_many and put_many batch operations."""

    def test_put_many_and_get_many(self, tmp_path):
        svc = FileKeyValueService(base_dir=str(tmp_path))
        items = {"a": 1, "b": 2, "c": 3}
        svc.put_many(items)
        result = svc.get_many(["a", "b", "c"])
        assert result == items

    def test_get_many_skips_missing(self, tmp_path):
        svc = FileKeyValueService(base_dir=str(tmp_path))
        svc.put("a", 1)
        result = svc.get_many(["a", "missing"])
        assert result == {"a": 1}

    def test_batch_with_namespace(self, tmp_path):
        svc = FileKeyValueService(base_dir=str(tmp_path))
        svc.put_many({"a": 1, "b": 2}, namespace="ns1")
        result = svc.get_many(["a", "b"], namespace="ns1")
        assert result == {"a": 1, "b": 2}
        # Should not be in default namespace
        assert svc.get_many(["a", "b"]) == {}


class TestFileKeyValueServiceLifecycle:
    """Tests for ping, close, context manager, and repr."""

    def test_ping_when_open(self, tmp_path):
        svc = FileKeyValueService(base_dir=str(tmp_path))
        assert svc.ping() is True

    def test_ping_when_closed(self, tmp_path):
        svc = FileKeyValueService(base_dir=str(tmp_path))
        svc.close()
        assert svc.ping() is False

    def test_close_is_idempotent(self, tmp_path):
        svc = FileKeyValueService(base_dir=str(tmp_path))
        svc.close()
        svc.close()  # Should not raise
        assert svc.ping() is False

    def test_context_manager(self, tmp_path):
        with FileKeyValueService(base_dir=str(tmp_path)) as svc:
            svc.put("key1", "value1")
            assert svc.get("key1") == "value1"
        assert svc.ping() is False

    def test_repr(self, tmp_path):
        svc = FileKeyValueService(base_dir=str(tmp_path))
        svc.put("a", 1, namespace="ns1")
        svc.put("b", 2, namespace="ns1")
        r = repr(svc)
        assert "FileKeyValueService" in r
        assert "namespaces=1" in r
        assert "total_keys=2" in r

    def test_get_stats_all(self, tmp_path):
        svc = FileKeyValueService(base_dir=str(tmp_path))
        svc.put("a", 1, namespace="ns1")
        svc.put("b", 2, namespace="ns2")
        stats = svc.get_stats()
        assert stats["backend"] == "file"
        assert stats["namespace_count"] == 2
        assert stats["total_keys"] == 2
        assert "base_dir" in stats

    def test_get_stats_specific_namespace(self, tmp_path):
        svc = FileKeyValueService(base_dir=str(tmp_path))
        svc.put("a", 1, namespace="ns1")
        svc.put("b", 2, namespace="ns1")
        stats = svc.get_stats(namespace="ns1")
        assert stats["backend"] == "file"
        assert stats["namespace"] == "ns1"
        assert stats["keys"] == 2
