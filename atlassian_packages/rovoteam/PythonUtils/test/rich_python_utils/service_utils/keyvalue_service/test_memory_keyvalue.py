"""
Unit tests for MemoryKeyValueService.

Tests cover core CRUD operations, namespace handling, thread safety,
context manager protocol, and edge cases.
"""

import threading

from python_utils.service_utils.keyvalue_service.memory_keyvalue_service import (
    MemoryKeyValueService,
)


class TestMemoryKeyValueServiceBasicOperations:
    """Tests for basic get/put/delete/exists operations."""

    def test_put_and_get(self):
        svc = MemoryKeyValueService()
        svc.put("key1", {"name": "Alice"})
        assert svc.get("key1") == {"name": "Alice"}

    def test_get_nonexistent_returns_none(self):
        svc = MemoryKeyValueService()
        assert svc.get("nonexistent") is None

    def test_put_overwrites_existing(self):
        svc = MemoryKeyValueService()
        svc.put("key1", "value1")
        svc.put("key1", "value2")
        assert svc.get("key1") == "value2"

    def test_delete_existing_key(self):
        svc = MemoryKeyValueService()
        svc.put("key1", "value1")
        assert svc.delete("key1") is True
        assert svc.get("key1") is None

    def test_delete_nonexistent_returns_false(self):
        svc = MemoryKeyValueService()
        assert svc.delete("nonexistent") is False

    def test_exists_true(self):
        svc = MemoryKeyValueService()
        svc.put("key1", "value1")
        assert svc.exists("key1") is True

    def test_exists_false(self):
        svc = MemoryKeyValueService()
        assert svc.exists("nonexistent") is False


class TestMemoryKeyValueServiceNamespaces:
    """Tests for namespace-scoped operations."""

    def test_default_namespace_when_none(self):
        svc = MemoryKeyValueService()
        svc.put("key1", "value1")
        svc.put("key1", "value2", namespace=None)
        # Both should target _default namespace, so value2 overwrites
        assert svc.get("key1") == "value2"

    def test_separate_namespaces(self):
        svc = MemoryKeyValueService()
        svc.put("key1", "ns1_value", namespace="ns1")
        svc.put("key1", "ns2_value", namespace="ns2")
        assert svc.get("key1", namespace="ns1") == "ns1_value"
        assert svc.get("key1", namespace="ns2") == "ns2_value"

    def test_keys_per_namespace(self):
        svc = MemoryKeyValueService()
        svc.put("a", 1, namespace="ns1")
        svc.put("b", 2, namespace="ns1")
        svc.put("c", 3, namespace="ns2")
        assert sorted(svc.keys(namespace="ns1")) == ["a", "b"]
        assert svc.keys(namespace="ns2") == ["c"]

    def test_keys_empty_namespace(self):
        svc = MemoryKeyValueService()
        assert svc.keys(namespace="nonexistent") == []

    def test_size_per_namespace(self):
        svc = MemoryKeyValueService()
        svc.put("a", 1, namespace="ns1")
        svc.put("b", 2, namespace="ns1")
        svc.put("c", 3, namespace="ns2")
        assert svc.size(namespace="ns1") == 2
        assert svc.size(namespace="ns2") == 1

    def test_size_empty_namespace(self):
        svc = MemoryKeyValueService()
        assert svc.size(namespace="nonexistent") == 0

    def test_clear_namespace(self):
        svc = MemoryKeyValueService()
        svc.put("a", 1, namespace="ns1")
        svc.put("b", 2, namespace="ns1")
        svc.put("c", 3, namespace="ns2")
        count = svc.clear(namespace="ns1")
        assert count == 2
        assert svc.size(namespace="ns1") == 0
        assert svc.size(namespace="ns2") == 1

    def test_clear_empty_namespace(self):
        svc = MemoryKeyValueService()
        assert svc.clear(namespace="nonexistent") == 0

    def test_namespaces_list(self):
        svc = MemoryKeyValueService()
        svc.put("a", 1, namespace="ns1")
        svc.put("b", 2, namespace="ns2")
        assert sorted(svc.namespaces()) == ["ns1", "ns2"]

    def test_namespaces_empty(self):
        svc = MemoryKeyValueService()
        assert svc.namespaces() == []

    def test_delete_cleans_up_empty_namespace(self):
        svc = MemoryKeyValueService()
        svc.put("key1", "value1", namespace="ns1")
        svc.delete("key1", namespace="ns1")
        assert "ns1" not in svc.namespaces()


class TestMemoryKeyValueServiceBatchOperations:
    """Tests for get_many and put_many batch operations."""

    def test_put_many_and_get_many(self):
        svc = MemoryKeyValueService()
        items = {"a": 1, "b": 2, "c": 3}
        svc.put_many(items)
        result = svc.get_many(["a", "b", "c"])
        assert result == items

    def test_get_many_skips_missing(self):
        svc = MemoryKeyValueService()
        svc.put("a", 1)
        result = svc.get_many(["a", "missing"])
        assert result == {"a": 1}

    def test_batch_with_namespace(self):
        svc = MemoryKeyValueService()
        svc.put_many({"a": 1, "b": 2}, namespace="ns1")
        result = svc.get_many(["a", "b"], namespace="ns1")
        assert result == {"a": 1, "b": 2}
        # Should not be in default namespace
        assert svc.get_many(["a", "b"]) == {}


class TestMemoryKeyValueServiceLifecycle:
    """Tests for ping, close, context manager, and repr."""

    def test_ping_when_open(self):
        svc = MemoryKeyValueService()
        assert svc.ping() is True

    def test_ping_when_closed(self):
        svc = MemoryKeyValueService()
        svc.close()
        assert svc.ping() is False

    def test_close_is_idempotent(self):
        svc = MemoryKeyValueService()
        svc.close()
        svc.close()  # Should not raise
        assert svc.ping() is False

    def test_context_manager(self):
        with MemoryKeyValueService() as svc:
            svc.put("key1", "value1")
            assert svc.get("key1") == "value1"
        assert svc.ping() is False

    def test_repr(self):
        svc = MemoryKeyValueService()
        svc.put("a", 1, namespace="ns1")
        svc.put("b", 2, namespace="ns1")
        r = repr(svc)
        assert "MemoryKeyValueService" in r
        assert "namespaces=1" in r
        assert "total_keys=2" in r

    def test_get_stats_all(self):
        svc = MemoryKeyValueService()
        svc.put("a", 1, namespace="ns1")
        svc.put("b", 2, namespace="ns2")
        stats = svc.get_stats()
        assert stats["backend"] == "memory"
        assert stats["namespace_count"] == 2
        assert stats["total_keys"] == 2

    def test_get_stats_specific_namespace(self):
        svc = MemoryKeyValueService()
        svc.put("a", 1, namespace="ns1")
        svc.put("b", 2, namespace="ns1")
        stats = svc.get_stats(namespace="ns1")
        assert stats["backend"] == "memory"
        assert stats["namespace"] == "ns1"
        assert stats["keys"] == 2


class TestMemoryKeyValueServiceThreadSafety:
    """Tests for thread-safe concurrent access."""

    def test_concurrent_puts(self):
        svc = MemoryKeyValueService()
        errors = []

        def writer(thread_id):
            try:
                for i in range(100):
                    svc.put(f"key_{thread_id}_{i}", f"value_{thread_id}_{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        # Each thread wrote 100 keys
        total = sum(svc.size(ns) for ns in svc.namespaces())
        assert total == 500

    def test_concurrent_reads_and_writes(self):
        svc = MemoryKeyValueService()
        errors = []

        def writer():
            try:
                for i in range(100):
                    svc.put(f"key_{i}", f"value_{i}")
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for i in range(100):
                    svc.get(f"key_{i}")  # May return None or value
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=reader),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
