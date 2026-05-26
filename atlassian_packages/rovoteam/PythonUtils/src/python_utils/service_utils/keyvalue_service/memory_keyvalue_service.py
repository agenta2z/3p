"""
Memory KeyValue Service

In-memory key-value storage service using Python dictionaries.
Thread-safe with threading.Lock for concurrent access.

Best suited for:
- Testing and development
- Single-process applications
- Quick prototyping without external dependencies
- Caching scenarios where persistence is not required

Limitations:
- Data is lost when the process exits (not persistent)
- Not suitable for inter-process communication
- Memory-bound by available RAM

Usage:
    from python_utils.service_utils.keyvalue_service.memory_keyvalue_service import (
        MemoryKeyValueService
    )

    service = MemoryKeyValueService()
    service.put("my_key", {"name": "Alice", "age": 30})
    value = service.get("my_key")  # {"name": "Alice", "age": 30}

    # With namespaces
    service.put("key1", "value1", namespace="ns1")
    service.put("key1", "value2", namespace="ns2")

    # Context manager
    with MemoryKeyValueService() as svc:
        svc.put("key", "value")
        result = svc.get("key")
"""

import threading
from typing import Any, Optional, List, Dict

from attr import attrs, attrib

from .keyvalue_service_base import KeyValueServiceBase

_DEFAULT_NAMESPACE = "_default"


@attrs(slots=False, repr=False)
class MemoryKeyValueService(KeyValueServiceBase):
    """
    In-memory key-value storage service.

    Stores key-value pairs in a nested dictionary structure:
    ``Dict[str, Dict[str, Any]]`` where the outer key is the namespace
    and the inner key is the actual storage key.

    Thread-safe: all operations are protected by a threading.Lock.

    Attributes:
        _store: Nested dictionary for namespace-scoped key-value storage.
        _lock: Threading lock for thread-safe access.
        _closed: Flag indicating if the service has been closed.
    """

    _store: Dict[str, Dict[str, Any]] = attrib(init=False, factory=dict)
    _lock: threading.Lock = attrib(init=False, factory=threading.Lock)
    _closed: bool = attrib(init=False, default=False)

    def _resolve_namespace(self, namespace: Optional[str]) -> str:
        """Resolve namespace, mapping None to '_default'."""
        return namespace if namespace is not None else _DEFAULT_NAMESPACE

    def get(self, key: str, namespace: Optional[str] = None) -> Optional[Any]:
        """
        Retrieve a value by key.

        Args:
            key: The key to look up.
            namespace: Optional namespace to scope the lookup.
                      None maps to "_default" internally.

        Returns:
            The stored value, or None if the key does not exist.
        """
        ns = self._resolve_namespace(namespace)
        with self._lock:
            ns_store = self._store.get(ns)
            if ns_store is None:
                return None
            return ns_store.get(key)

    def put(self, key: str, value: Any, namespace: Optional[str] = None) -> None:
        """
        Store a value by key (upsert semantics).

        If the key already exists, the value is overwritten.

        Args:
            key: The key to store under.
            value: Any JSON-serializable Python object.
            namespace: Optional namespace to scope the storage.
                      None maps to "_default" internally.
        """
        ns = self._resolve_namespace(namespace)
        with self._lock:
            if ns not in self._store:
                self._store[ns] = {}
            self._store[ns][key] = value

    def delete(self, key: str, namespace: Optional[str] = None) -> bool:
        """
        Delete a key-value pair.

        Args:
            key: The key to delete.
            namespace: Optional namespace to scope the deletion.
                      None maps to "_default" internally.

        Returns:
            True if the key was deleted, False if it did not exist.
        """
        ns = self._resolve_namespace(namespace)
        with self._lock:
            ns_store = self._store.get(ns)
            if ns_store is None or key not in ns_store:
                return False
            del ns_store[key]
            # Clean up empty namespaces
            if not ns_store:
                del self._store[ns]
            return True

    def exists(self, key: str, namespace: Optional[str] = None) -> bool:
        """
        Check if a key exists.

        Args:
            key: The key to check.
            namespace: Optional namespace to scope the check.
                      None maps to "_default" internally.

        Returns:
            True if the key exists, False otherwise.
        """
        ns = self._resolve_namespace(namespace)
        with self._lock:
            ns_store = self._store.get(ns)
            if ns_store is None:
                return False
            return key in ns_store

    def keys(self, namespace: Optional[str] = None) -> List[str]:
        """
        List all keys in a namespace.

        Args:
            namespace: Optional namespace to list keys for.
                      None maps to "_default" internally.

        Returns:
            List of key strings in the namespace.
        """
        ns = self._resolve_namespace(namespace)
        with self._lock:
            ns_store = self._store.get(ns)
            if ns_store is None:
                return []
            return list(ns_store.keys())

    def size(self, namespace: Optional[str] = None) -> int:
        """
        Get the number of key-value pairs in a namespace.

        Args:
            namespace: Optional namespace to get the size of.
                      None maps to "_default" internally.

        Returns:
            Number of key-value pairs in the namespace.
        """
        ns = self._resolve_namespace(namespace)
        with self._lock:
            ns_store = self._store.get(ns)
            if ns_store is None:
                return 0
            return len(ns_store)

    def clear(self, namespace: Optional[str] = None) -> int:
        """
        Remove all key-value pairs in a namespace.

        Args:
            namespace: Optional namespace to clear.
                      None maps to "_default" internally.

        Returns:
            Number of items removed.
        """
        ns = self._resolve_namespace(namespace)
        with self._lock:
            ns_store = self._store.get(ns)
            if ns_store is None:
                return 0
            count = len(ns_store)
            del self._store[ns]
            return count

    def namespaces(self) -> List[str]:
        """
        List all namespaces that contain data.

        Returns:
            List of namespace strings.
        """
        with self._lock:
            return list(self._store.keys())

    def get_stats(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics about the service.

        Args:
            namespace: Optional namespace to get stats for.
                      If None, returns stats for all namespaces.

        Returns:
            Dictionary with service statistics including:
            - backend: "memory"
            - namespace_count: number of namespaces
            - total_keys: total number of keys
            - namespaces: per-namespace key counts (when no namespace specified)
            - keys: number of keys (when namespace specified)
        """
        with self._lock:
            if namespace is not None:
                ns = namespace
                ns_store = self._store.get(ns)
                return {
                    "backend": "memory",
                    "namespace": ns,
                    "keys": len(ns_store) if ns_store else 0,
                }
            else:
                total_keys = sum(len(v) for v in self._store.values())
                return {
                    "backend": "memory",
                    "namespace_count": len(self._store),
                    "total_keys": total_keys,
                    "namespaces": {
                        ns: len(store) for ns, store in self._store.items()
                    },
                }

    def ping(self) -> bool:
        """
        Check if service is responsive.

        Returns:
            True if service is not closed, False otherwise.
        """
        return not self._closed

    def close(self) -> None:
        """
        Close the service and clean up resources.

        This method is idempotent — calling it multiple times is safe.
        """
        self._closed = True

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit — delegates to close()."""
        self.close()

    def __repr__(self) -> str:
        """String representation of the service."""
        with self._lock:
            ns_count = len(self._store)
            total_keys = sum(len(v) for v in self._store.values())
        return (
            f"MemoryKeyValueService("
            f"namespaces={ns_count}, "
            f"total_keys={total_keys}, "
            f"closed={self._closed})"
        )
