"""
SQLite KeyValue Service

SQLite-based key-value storage service using a single table with
(namespace, key, value_json) columns. Uses INSERT OR REPLACE for
upsert semantics.

Best suited for:
- Persistent storage without external dependencies
- Single-process or multi-threaded applications
- Moderate to large data volumes
- Applications needing ACID guarantees

Thread Safety:
- SQLite handles its own locking via WAL mode
- Connection is created at construction time

Batch Optimization:
- get_many and put_many override the base class defaults with
  executemany-based batch operations for better performance.

Usage:
    from python_utils.service_utils.keyvalue_service.sqlite_keyvalue_service import (
        SQLiteKeyValueService
    )

    service = SQLiteKeyValueService(db_path="/tmp/my_kv.db")
    service.put("my_key", {"name": "Alice", "age": 30})
    value = service.get("my_key")  # {"name": "Alice", "age": 30}

    # With namespaces
    service.put("key1", "value1", namespace="ns1")
    service.put("key1", "value2", namespace="ns2")

    # Context manager
    with SQLiteKeyValueService(db_path="/tmp/store.db") as svc:
        svc.put("key", "value")
        result = svc.get("key")
"""

import json
import sqlite3
from typing import Any, Optional, List, Dict

from attr import attrs, attrib

from .keyvalue_service_base import KeyValueServiceBase

_DEFAULT_NAMESPACE = "_default"


@attrs(slots=False, repr=False)
class SQLiteKeyValueService(KeyValueServiceBase):
    """
    SQLite-based key-value storage service.

    Stores key-value pairs in a SQLite table with columns:
        (namespace TEXT, key TEXT, value_json TEXT)

    Uses a composite primary key of (namespace, key) and INSERT OR REPLACE
    for upsert semantics.

    Attributes:
        db_path: Path to the SQLite database file. Use ":memory:" for
                 an in-memory database.
    """

    db_path: str = attrib()
    _conn: sqlite3.Connection = attrib(init=False, default=None)
    _closed: bool = attrib(init=False, default=False)

    def __attrs_post_init__(self):
        """Initialize the SQLite connection and create the table."""
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS kv_store (
                namespace TEXT NOT NULL,
                key TEXT NOT NULL,
                value_json TEXT NOT NULL,
                PRIMARY KEY (namespace, key)
            )
            """
        )
        self._conn.commit()

    def _resolve_namespace(self, namespace: Optional[str]) -> str:
        """Resolve namespace, mapping None to '_default'."""
        return namespace if namespace is not None else _DEFAULT_NAMESPACE

    def get(self, key: str, namespace: Optional[str] = None) -> Optional[Any]:
        """
        Retrieve a value by key from the SQLite database.

        Args:
            key: The key to look up.
            namespace: Optional namespace to scope the lookup.
                      None maps to "_default" internally.

        Returns:
            The stored value deserialized from JSON, or None if the key
            does not exist.
        """
        ns = self._resolve_namespace(namespace)
        cursor = self._conn.execute(
            "SELECT value_json FROM kv_store WHERE namespace = ? AND key = ?",
            (ns, key),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def put(self, key: str, value: Any, namespace: Optional[str] = None) -> None:
        """
        Store a value by key using INSERT OR REPLACE (upsert semantics).

        If the key already exists, the value is overwritten.

        Args:
            key: The key to store under.
            value: Any JSON-serializable Python object.
            namespace: Optional namespace to scope the storage.
                      None maps to "_default" internally.

        Raises:
            TypeError: If the value is not JSON-serializable.
        """
        ns = self._resolve_namespace(namespace)
        value_json = json.dumps(value)
        self._conn.execute(
            "INSERT OR REPLACE INTO kv_store (namespace, key, value_json) VALUES (?, ?, ?)",
            (ns, key, value_json),
        )
        self._conn.commit()

    def delete(self, key: str, namespace: Optional[str] = None) -> bool:
        """
        Delete a key-value pair from the SQLite database.

        Args:
            key: The key to delete.
            namespace: Optional namespace to scope the deletion.
                      None maps to "_default" internally.

        Returns:
            True if the key was deleted, False if it did not exist.
        """
        ns = self._resolve_namespace(namespace)
        cursor = self._conn.execute(
            "DELETE FROM kv_store WHERE namespace = ? AND key = ?",
            (ns, key),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def exists(self, key: str, namespace: Optional[str] = None) -> bool:
        """
        Check if a key exists in the SQLite database.

        Args:
            key: The key to check.
            namespace: Optional namespace to scope the check.
                      None maps to "_default" internally.

        Returns:
            True if the key exists, False otherwise.
        """
        ns = self._resolve_namespace(namespace)
        cursor = self._conn.execute(
            "SELECT 1 FROM kv_store WHERE namespace = ? AND key = ?",
            (ns, key),
        )
        return cursor.fetchone() is not None

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
        cursor = self._conn.execute(
            "SELECT key FROM kv_store WHERE namespace = ?",
            (ns,),
        )
        return [row[0] for row in cursor.fetchall()]

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
        cursor = self._conn.execute(
            "SELECT COUNT(*) FROM kv_store WHERE namespace = ?",
            (ns,),
        )
        return cursor.fetchone()[0]

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
        cursor = self._conn.execute(
            "DELETE FROM kv_store WHERE namespace = ?",
            (ns,),
        )
        self._conn.commit()
        return cursor.rowcount

    def namespaces(self) -> List[str]:
        """
        List all namespaces that contain data.

        Returns:
            List of distinct namespace strings.
        """
        cursor = self._conn.execute(
            "SELECT DISTINCT namespace FROM kv_store"
        )
        return [row[0] for row in cursor.fetchall()]

    def get_stats(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics about the service.

        Args:
            namespace: Optional namespace to get stats for.
                      If None, returns stats for all namespaces.

        Returns:
            Dictionary with service statistics including:
            - backend: "sqlite"
            - db_path: the database file path
            - namespace_count / total_keys (when no namespace specified)
            - namespace / keys (when namespace specified)
        """
        if namespace is not None:
            ns = namespace
            return {
                "backend": "sqlite",
                "db_path": self.db_path,
                "namespace": ns,
                "keys": self.size(namespace=ns),
            }
        else:
            all_ns = self.namespaces()
            cursor = self._conn.execute("SELECT COUNT(*) FROM kv_store")
            total_keys = cursor.fetchone()[0]
            return {
                "backend": "sqlite",
                "db_path": self.db_path,
                "namespace_count": len(all_ns),
                "total_keys": total_keys,
                "namespaces": {
                    ns: self.size(namespace=ns) for ns in all_ns
                },
            }

    def ping(self) -> bool:
        """
        Check if service is responsive.

        Returns:
            True if the database connection is alive and service is not closed,
            False otherwise.
        """
        if self._closed or self._conn is None:
            return False
        try:
            self._conn.execute("SELECT 1")
            return True
        except sqlite3.Error:
            return False

    def close(self) -> None:
        """
        Close the SQLite connection and clean up resources.

        This method is idempotent — calling it multiple times is safe.
        """
        if not self._closed:
            self._closed = True
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    # ── Optimized batch methods using executemany ──

    def get_many(self, keys: List[str], namespace: Optional[str] = None) -> Dict[str, Any]:
        """
        Get multiple values by keys using a single query.

        Overrides the base class default with an optimized implementation
        that fetches all requested keys in a single SQL query.

        Args:
            keys: List of keys to retrieve.
            namespace: Optional namespace to scope the lookups.
                      None maps to "_default" internally.

        Returns:
            Dictionary mapping keys to their values.
            Keys with no stored value are omitted from the result.
        """
        if not keys:
            return {}
        ns = self._resolve_namespace(namespace)
        placeholders = ",".join("?" for _ in keys)
        cursor = self._conn.execute(
            f"SELECT key, value_json FROM kv_store WHERE namespace = ? AND key IN ({placeholders})",
            (ns, *keys),
        )
        result = {}
        for row in cursor.fetchall():
            value = json.loads(row[1])
            if value is not None:
                result[row[0]] = value
        return result

    def put_many(self, items: Dict[str, Any], namespace: Optional[str] = None) -> None:
        """
        Store multiple key-value pairs using executemany.

        Overrides the base class default with an optimized implementation
        that inserts all items in a single executemany call.

        Args:
            items: Dictionary mapping keys to values.
            namespace: Optional namespace to scope the storage.
                      None maps to "_default" internally.

        Raises:
            TypeError: If any value is not JSON-serializable.
        """
        if not items:
            return
        ns = self._resolve_namespace(namespace)
        rows = [(ns, key, json.dumps(value)) for key, value in items.items()]
        self._conn.executemany(
            "INSERT OR REPLACE INTO kv_store (namespace, key, value_json) VALUES (?, ?, ?)",
            rows,
        )
        self._conn.commit()

    # ── Context manager protocol ──

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit — delegates to close()."""
        self.close()

    def __repr__(self) -> str:
        """String representation of the service."""
        if self._closed:
            return (
                f"SQLiteKeyValueService("
                f"db_path='{self.db_path}', "
                f"closed=True)"
            )
        ns_count = len(self.namespaces())
        cursor = self._conn.execute("SELECT COUNT(*) FROM kv_store")
        total_keys = cursor.fetchone()[0]
        return (
            f"SQLiteKeyValueService("
            f"db_path='{self.db_path}', "
            f"namespaces={ns_count}, "
            f"total_keys={total_keys}, "
            f"closed={self._closed})"
        )
