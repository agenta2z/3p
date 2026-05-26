"""
Unit tests for SQLiteKeyValueService.

Tests cover core CRUD operations, namespace handling, batch operations
with executemany optimization, context manager protocol, and edge cases.
"""

import os

from python_utils.service_utils.keyvalue_service.sqlite_keyvalue_service import (
    SQLiteKeyValueService,
)


class TestSQLiteKeyValueServiceBasicOperations:
    """Tests for basic get/put/delete/exists operations."""

    def test_put_and_get(self, tmp_path):
        svc = SQLiteKeyValueService(db_path=str(tmp_path / "test.db"))
        svc.put("key1", {"name": "Alice"})
        assert svc.get("key1") == {"name": "Alice"}

    def test_get_nonexistent_returns_none(self, tmp_path):
        svc = SQLiteKeyValueService(db_path=str(tmp_path / "test.db"))
        assert svc.get("nonexistent") is None

    def test_put_overwrites_existing(self, tmp_path):
        svc = SQLiteKeyValueService(db_path=str(tmp_path / "test.db"))
        svc.put("key1", "value1")
        svc.put("key1", "value2")
        assert svc.get("key1") == "value2"

    def test_delete_existing_key(self, tmp_path):
        svc = SQLiteKeyValueService(db_path=str(tmp_path / "test.db"))
        svc.put("key1", "value1")
        assert svc.delete("key1") is True
        assert svc.get("key1") is None

    def test_delete_nonexistent_returns_false(self, tmp_path):
        svc = SQLiteKeyValueService(db_path=str(tmp_path / "test.db"))
        assert svc.delete("nonexistent") is False

    def test_exists_true(self, tmp_path):
        svc = SQLiteKeyValueService(db_path=str(tmp_path / "test.db"))
        svc.put("key1", "value1")
        assert svc.exists("key1") is True

    def test_exists_false(self, tmp_path):
        svc = SQLiteKeyValueService(db_path=str(tmp_path / "test.db"))
        assert svc.exists("nonexistent") is False

    def test_stores_various_json_types(self, tmp_path):
        svc = SQLiteKeyValueService(db_path=str(tmp_path / "test.db"))
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

    def test_in_memory_database(self):
        """SQLite :memory: database should work for transient storage."""
        svc = SQLiteKeyValueService(db_path=":memory:")
        svc.put("key1", "value1")
        assert svc.get("key1") == "value1"
        svc.close()


class TestSQLiteKeyValueServiceNamespaces:
    """Tests for namespace-scoped operations."""

    def test_default_namespace_when_none(self, tmp_path):
        svc = SQLiteKeyValueService(db_path=str(tmp_path / "test.db"))
        svc.put("key1", "value1")
        svc.put("key1", "value2", namespace=None)
        # Both should target _default namespace, so value2 overwrites
        assert svc.get("key1") == "value2"

    def test_separate_namespaces(self, tmp_path):
        svc = SQLiteKeyValueService(db_path=str(tmp_path / "test.db"))
        svc.put("key1", "ns1_value", namespace="ns1")
        svc.put("key1", "ns2_value", namespace="ns2")
        assert svc.get("key1", namespace="ns1") == "ns1_value"
        assert svc.get("key1", namespace="ns2") == "ns2_value"

    def test_keys_per_namespace(self, tmp_path):
        svc = SQLiteKeyValueService(db_path=str(tmp_path / "test.db"))
        svc.put("a", 1, namespace="ns1")
        svc.put("b", 2, namespace="ns1")
        svc.put("c", 3, namespace="ns2")
        assert sorted(svc.keys(namespace="ns1")) == ["a", "b"]
        assert svc.keys(namespace="ns2") == ["c"]

    def test_keys_empty_namespace(self, tmp_path):
        svc = SQLiteKeyValueService(db_path=str(tmp_path / "test.db"))
        assert svc.keys(namespace="nonexistent") == []

    def test_size_per_namespace(self, tmp_path):
        svc = SQLiteKeyValueService(db_path=str(tmp_path / "test.db"))
        svc.put("a", 1, namespace="ns1")
        svc.put("b", 2, namespace="ns1")
        svc.put("c", 3, namespace="ns2")
        assert svc.size(namespace="ns1") == 2
        assert svc.size(namespace="ns2") == 1

    def test_size_empty_namespace(self, tmp_path):
        svc = SQLiteKeyValueService(db_path=str(tmp_path / "test.db"))
        assert svc.size(namespace="nonexistent") == 0

    def test_clear_namespace(self, tmp_path):
        svc = SQLiteKeyValueService(db_path=str(tmp_path / "test.db"))
        svc.put("a", 1, namespace="ns1")
        svc.put("b", 2, namespace="ns1")
        svc.put("c", 3, namespace="ns2")
        count = svc.clear(namespace="ns1")
        assert count == 2
        assert svc.size(namespace="ns1") == 0
        assert svc.size(namespace="ns2") == 1

    def test_clear_empty_namespace(self, tmp_path):
        svc = SQLiteKeyValueService(db_path=str(tmp_path / "test.db"))
        assert svc.clear(namespace="nonexistent") == 0

    def test_namespaces_list(self, tmp_path):
        svc = SQLiteKeyValueService(db_path=str(tmp_path / "test.db"))
        svc.put("a", 1, namespace="ns1")
        svc.put("b", 2, namespace="ns2")
        assert sorted(svc.namespaces()) == ["ns1", "ns2"]

    def test_namespaces_empty(self, tmp_path):
        svc = SQLiteKeyValueService(db_path=str(tmp_path / "test.db"))
        assert svc.namespaces() == []

    def test_namespace_removed_after_clear(self, tmp_path):
        """After clearing a namespace, it should no longer appear in namespaces()."""
        svc = SQLiteKeyValueService(db_path=str(tmp_path / "test.db"))
        svc.put("key1", "value1", namespace="ns1")
        svc.clear(namespace="ns1")
        assert "ns1" not in svc.namespaces()

    def test_namespace_removed_after_delete_last_key(self, tmp_path):
        """After deleting the last key in a namespace, it should no longer appear."""
        svc = SQLiteKeyValueService(db_path=str(tmp_path / "test.db"))
        svc.put("key1", "value1", namespace="ns1")
        svc.delete("key1", namespace="ns1")
        assert "ns1" not in svc.namespaces()


class TestSQLiteKeyValueServiceBatchOperations:
    """Tests for optimized get_many and put_many batch operations."""

    def test_put_many_and_get_many(self, tmp_path):
        svc = SQLiteKeyValueService(db_path=str(tmp_path / "test.db"))
        items = {"a": 1, "b": 2, "c": 3}
        svc.put_many(items)
        result = svc.get_many(["a", "b", "c"])
        assert result == items

    def test_get_many_skips_missing(self, tmp_path):
        svc = SQLiteKeyValueService(db_path=str(tmp_path / "test.db"))
        svc.put("a", 1)
        result = svc.get_many(["a", "missing"])
        assert result == {"a": 1}

    def test_batch_with_namespace(self, tmp_path):
        svc = SQLiteKeyValueService(db_path=str(tmp_path / "test.db"))
        svc.put_many({"a": 1, "b": 2}, namespace="ns1")
        result = svc.get_many(["a", "b"], namespace="ns1")
        assert result == {"a": 1, "b": 2}
        # Should not be in default namespace
        assert svc.get_many(["a", "b"]) == {}

    def test_put_many_empty_dict(self, tmp_path):
        """put_many with empty dict should be a no-op."""
        svc = SQLiteKeyValueService(db_path=str(tmp_path / "test.db"))
        svc.put_many({})
        assert svc.size() == 0

    def test_get_many_empty_list(self, tmp_path):
        """get_many with empty list should return empty dict."""
        svc = SQLiteKeyValueService(db_path=str(tmp_path / "test.db"))
        assert svc.get_many([]) == {}

    def test_put_many_upsert(self, tmp_path):
        """put_many should overwrite existing keys."""
        svc = SQLiteKeyValueService(db_path=str(tmp_path / "test.db"))
        svc.put("a", 1)
        svc.put_many({"a": 10, "b": 20})
        assert svc.get("a") == 10
        assert svc.get("b") == 20

    def test_put_many_with_complex_values(self, tmp_path):
        """put_many should handle complex JSON-serializable values."""
        svc = SQLiteKeyValueService(db_path=str(tmp_path / "test.db"))
        items = {
            "nested": {"a": [1, 2, 3], "b": {"c": True}},
            "list": [1, "two", None, 4.0],
            "simple": "hello",
        }
        svc.put_many(items)
        result = svc.get_many(["nested", "list", "simple"])
        assert result == items


class TestSQLiteKeyValueServiceLifecycle:
    """Tests for ping, close, context manager, and repr."""

    def test_ping_when_open(self, tmp_path):
        svc = SQLiteKeyValueService(db_path=str(tmp_path / "test.db"))
        assert svc.ping() is True

    def test_ping_when_closed(self, tmp_path):
        svc = SQLiteKeyValueService(db_path=str(tmp_path / "test.db"))
        svc.close()
        assert svc.ping() is False

    def test_close_is_idempotent(self, tmp_path):
        svc = SQLiteKeyValueService(db_path=str(tmp_path / "test.db"))
        svc.close()
        svc.close()  # Should not raise
        assert svc.ping() is False

    def test_context_manager(self, tmp_path):
        with SQLiteKeyValueService(db_path=str(tmp_path / "test.db")) as svc:
            svc.put("key1", "value1")
            assert svc.get("key1") == "value1"
        assert svc.ping() is False

    def test_repr(self, tmp_path):
        svc = SQLiteKeyValueService(db_path=str(tmp_path / "test.db"))
        svc.put("a", 1, namespace="ns1")
        svc.put("b", 2, namespace="ns1")
        r = repr(svc)
        assert "SQLiteKeyValueService" in r
        assert "namespaces=1" in r
        assert "total_keys=2" in r

    def test_repr_when_closed(self, tmp_path):
        svc = SQLiteKeyValueService(db_path=str(tmp_path / "test.db"))
        svc.close()
        r = repr(svc)
        assert "SQLiteKeyValueService" in r
        assert "closed=True" in r

    def test_get_stats_all(self, tmp_path):
        svc = SQLiteKeyValueService(db_path=str(tmp_path / "test.db"))
        svc.put("a", 1, namespace="ns1")
        svc.put("b", 2, namespace="ns2")
        stats = svc.get_stats()
        assert stats["backend"] == "sqlite"
        assert stats["namespace_count"] == 2
        assert stats["total_keys"] == 2
        assert "db_path" in stats

    def test_get_stats_specific_namespace(self, tmp_path):
        svc = SQLiteKeyValueService(db_path=str(tmp_path / "test.db"))
        svc.put("a", 1, namespace="ns1")
        svc.put("b", 2, namespace="ns1")
        stats = svc.get_stats(namespace="ns1")
        assert stats["backend"] == "sqlite"
        assert stats["namespace"] == "ns1"
        assert stats["keys"] == 2

    def test_data_persists_across_instances(self, tmp_path):
        """Data should persist when a new service instance opens the same db."""
        db_path = str(tmp_path / "test.db")
        svc1 = SQLiteKeyValueService(db_path=db_path)
        svc1.put("key1", "value1")
        svc1.close()

        svc2 = SQLiteKeyValueService(db_path=db_path)
        assert svc2.get("key1") == "value1"
        svc2.close()

    def test_db_file_created(self, tmp_path):
        """The SQLite database file should be created on disk."""
        db_path = str(tmp_path / "test.db")
        svc = SQLiteKeyValueService(db_path=db_path)
        svc.put("key1", "value1")
        assert os.path.exists(db_path)
        svc.close()


class TestSQLiteKeyValueServiceSpecialKeys:
    """Tests for keys with special characters."""

    def test_key_with_colon(self, tmp_path):
        svc = SQLiteKeyValueService(db_path=str(tmp_path / "test.db"))
        svc.put("user:xinli", {"role": "admin"})
        assert svc.get("user:xinli") == {"role": "admin"}

    def test_key_with_slashes(self, tmp_path):
        svc = SQLiteKeyValueService(db_path=str(tmp_path / "test.db"))
        svc.put("path/to/thing", "value")
        assert svc.get("path/to/thing") == "value"

    def test_key_with_special_chars(self, tmp_path):
        svc = SQLiteKeyValueService(db_path=str(tmp_path / "test.db"))
        svc.put("a:b/c\\d%e", "value")
        assert svc.get("a:b/c\\d%e") == "value"
        assert svc.exists("a:b/c\\d%e") is True

    def test_key_with_unicode(self, tmp_path):
        svc = SQLiteKeyValueService(db_path=str(tmp_path / "test.db"))
        svc.put("日本語キー", "value")
        assert svc.get("日本語キー") == "value"

    def test_keys_returns_original_keys(self, tmp_path):
        """keys() should return the original key strings."""
        svc = SQLiteKeyValueService(db_path=str(tmp_path / "test.db"))
        svc.put("user:xinli", "v1")
        svc.put("path/to/thing", "v2")
        result = sorted(svc.keys())
        assert result == ["path/to/thing", "user:xinli"]
