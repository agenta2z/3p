"""
File KeyValue Service

File-based key-value storage service using JSON files on disk.
Each value is stored as a separate JSON file at:
    {base_dir}/{namespace}/{encoded_key}.json

Keys are percent-encoded to produce safe filenames, using the same
encoding scheme as the knowledge module utils:
    '%' → '%25'  (first, to avoid double-encoding)
    ':' → '%3A'
    '/' → '%2F'
    '\\' → '%5C'

Best suited for:
- Persistent storage without external dependencies
- Single-process applications
- Human-readable data inspection on disk
- Moderate data volumes where file I/O is acceptable

Limitations:
- Not thread-safe (single-process only)
- Performance degrades with very large numbers of keys per namespace
- No atomic multi-key operations

Usage:
    from python_utils.service_utils.keyvalue_service.file_keyvalue_service import (
        FileKeyValueService
    )

    service = FileKeyValueService(base_dir="/tmp/my_kv_store")
    service.put("my_key", {"name": "Alice", "age": 30})
    value = service.get("my_key")  # {"name": "Alice", "age": 30}

    # With namespaces
    service.put("key1", "value1", namespace="ns1")
    service.put("key1", "value2", namespace="ns2")

    # Context manager
    with FileKeyValueService(base_dir="/tmp/store") as svc:
        svc.put("key", "value")
        result = svc.get("key")
"""

import json
import logging
import os
from typing import Any, Optional, List, Dict

from attr import attrs, attrib

from .keyvalue_service_base import KeyValueServiceBase

logger = logging.getLogger(__name__)

_DEFAULT_NAMESPACE = "_default"


def _encode_key(key: str) -> str:
    """Percent-encode a key for use as a filename.

    Uses the same encoding scheme as the knowledge module utils:
        '%' → '%25'  (must be first to avoid double-encoding)
        ':' → '%3A'
        '/' → '%2F'
        '\\' → '%5C'

    Args:
        key: The raw key string.

    Returns:
        A filesystem-safe encoded key string.
    """
    return (
        key
        .replace("%", "%25")
        .replace(":", "%3A")
        .replace("/", "%2F")
        .replace("\\", "%5C")
    )


def _decode_key(encoded_key: str) -> str:
    """Reverse of _encode_key. Decodes percent-encoded key.

    Decodes in reverse order of encoding to ensure correctness:
        '%5C' → '\\\\'
        '%2F' → '/'
        '%3A' → ':'
        '%25' → '%'  (must be last to avoid premature decoding)

    Args:
        encoded_key: The percent-encoded key string.

    Returns:
        The original key string.
    """
    return (
        encoded_key
        .replace("%5C", "\\")
        .replace("%2F", "/")
        .replace("%3A", ":")
        .replace("%25", "%")
    )


@attrs(slots=False, repr=False)
class FileKeyValueService(KeyValueServiceBase):
    """
    File-based key-value storage service.

    Stores each value as a JSON file at:
        {base_dir}/{namespace}/{encoded_key}.json

    Keys are percent-encoded to produce safe filenames.
    Namespace=None maps to "_default" internally.

    Attributes:
        base_dir: Root directory for all key-value files.
    """

    base_dir: str = attrib()
    _closed: bool = attrib(init=False, default=False)

    def __attrs_post_init__(self):
        """Create the base directory on initialization."""
        os.makedirs(self.base_dir, exist_ok=True)

    def _resolve_namespace(self, namespace: Optional[str]) -> str:
        """Resolve namespace, mapping None to '_default'."""
        return namespace if namespace is not None else _DEFAULT_NAMESPACE

    def _namespace_dir(self, namespace: str) -> str:
        """Return the directory path for a namespace."""
        return os.path.join(self.base_dir, namespace)

    def _key_path(self, namespace: str, key: str) -> str:
        """Return the file path for a key within a namespace."""
        encoded = _encode_key(key)
        return os.path.join(self._namespace_dir(namespace), f"{encoded}.json")

    def get(self, key: str, namespace: Optional[str] = None) -> Optional[Any]:
        """
        Retrieve a value by key by reading its JSON file.

        Args:
            key: The key to look up.
            namespace: Optional namespace to scope the lookup.
                      None maps to "_default" internally.

        Returns:
            The stored value, or None if the key does not exist
            or the file contains malformed JSON.
        """
        ns = self._resolve_namespace(namespace)
        path = self._key_path(ns, key)

        if not os.path.exists(path):
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("Skipping malformed JSON file %s: %s", path, exc)
            return None

    def put(self, key: str, value: Any, namespace: Optional[str] = None) -> None:
        """
        Store a value by key as a JSON file (upsert semantics).

        If the key already exists, the file is overwritten.
        Creates the namespace directory if it does not already exist.

        Args:
            key: The key to store under.
            value: Any JSON-serializable Python object.
            namespace: Optional namespace to scope the storage.
                      None maps to "_default" internally.

        Raises:
            TypeError: If the value is not JSON-serializable.
        """
        ns = self._resolve_namespace(namespace)
        path = self._key_path(ns, key)
        os.makedirs(os.path.dirname(path), exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(value, f, indent=2, ensure_ascii=False)

    def delete(self, key: str, namespace: Optional[str] = None) -> bool:
        """
        Delete a key-value pair by removing its JSON file.

        Args:
            key: The key to delete.
            namespace: Optional namespace to scope the deletion.
                      None maps to "_default" internally.

        Returns:
            True if the file existed and was deleted, False otherwise.
        """
        ns = self._resolve_namespace(namespace)
        path = self._key_path(ns, key)

        if os.path.exists(path):
            os.remove(path)
            # Clean up empty namespace directory
            ns_dir = self._namespace_dir(ns)
            if os.path.isdir(ns_dir) and not os.listdir(ns_dir):
                os.rmdir(ns_dir)
            return True
        return False

    def exists(self, key: str, namespace: Optional[str] = None) -> bool:
        """
        Check if a key exists by checking for its JSON file.

        Args:
            key: The key to check.
            namespace: Optional namespace to scope the check.
                      None maps to "_default" internally.

        Returns:
            True if the file exists, False otherwise.
        """
        ns = self._resolve_namespace(namespace)
        path = self._key_path(ns, key)
        return os.path.exists(path)

    def keys(self, namespace: Optional[str] = None) -> List[str]:
        """
        List all keys in a namespace by scanning the namespace directory.

        Filenames are decoded back to original key strings.

        Args:
            namespace: Optional namespace to list keys for.
                      None maps to "_default" internally.

        Returns:
            List of key strings in the namespace.
        """
        ns = self._resolve_namespace(namespace)
        ns_dir = self._namespace_dir(ns)

        if not os.path.isdir(ns_dir):
            return []

        result = []
        for filename in os.listdir(ns_dir):
            if filename.endswith(".json"):
                encoded_key = filename[:-5]  # strip .json
                result.append(_decode_key(encoded_key))
        return result

    def size(self, namespace: Optional[str] = None) -> int:
        """
        Get the number of key-value pairs in a namespace.

        Args:
            namespace: Optional namespace to get the size of.
                      None maps to "_default" internally.

        Returns:
            Number of JSON files in the namespace directory.
        """
        ns = self._resolve_namespace(namespace)
        ns_dir = self._namespace_dir(ns)

        if not os.path.isdir(ns_dir):
            return 0

        return sum(1 for f in os.listdir(ns_dir) if f.endswith(".json"))

    def clear(self, namespace: Optional[str] = None) -> int:
        """
        Remove all key-value pairs in a namespace by deleting all JSON files.

        Also removes the namespace directory if it becomes empty.

        Args:
            namespace: Optional namespace to clear.
                      None maps to "_default" internally.

        Returns:
            Number of items removed.
        """
        ns = self._resolve_namespace(namespace)
        ns_dir = self._namespace_dir(ns)

        if not os.path.isdir(ns_dir):
            return 0

        count = 0
        for filename in os.listdir(ns_dir):
            if filename.endswith(".json"):
                os.remove(os.path.join(ns_dir, filename))
                count += 1

        # Clean up empty namespace directory
        if os.path.isdir(ns_dir) and not os.listdir(ns_dir):
            os.rmdir(ns_dir)

        return count

    def namespaces(self) -> List[str]:
        """
        List all namespaces that contain data.

        Scans subdirectories of base_dir that contain at least one JSON file.

        Returns:
            List of namespace strings.
        """
        if not os.path.isdir(self.base_dir):
            return []

        result = []
        for entry in os.listdir(self.base_dir):
            entry_path = os.path.join(self.base_dir, entry)
            if os.path.isdir(entry_path):
                # Only include if it has at least one JSON file
                if any(f.endswith(".json") for f in os.listdir(entry_path)):
                    result.append(entry)
        return result

    def get_stats(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics about the service.

        Args:
            namespace: Optional namespace to get stats for.
                      If None, returns stats for all namespaces.

        Returns:
            Dictionary with service statistics including:
            - backend: "file"
            - base_dir: the base directory path
            - namespace_count / total_keys (when no namespace specified)
            - namespace / keys (when namespace specified)
        """
        if namespace is not None:
            ns = namespace
            return {
                "backend": "file",
                "base_dir": self.base_dir,
                "namespace": ns,
                "keys": self.size(namespace=ns),
            }
        else:
            all_ns = self.namespaces()
            total_keys = sum(self.size(namespace=ns) for ns in all_ns)
            return {
                "backend": "file",
                "base_dir": self.base_dir,
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
            True if the base directory exists and service is not closed,
            False otherwise.
        """
        return not self._closed and os.path.isdir(self.base_dir)

    def close(self) -> None:
        """
        Close the service.

        This method is idempotent — calling it multiple times is safe.
        Note: does not delete any files on disk.
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
        ns_count = len(self.namespaces())
        total_keys = sum(self.size(namespace=ns) for ns in self.namespaces())
        return (
            f"FileKeyValueService("
            f"base_dir='{self.base_dir}', "
            f"namespaces={ns_count}, "
            f"total_keys={total_keys}, "
            f"closed={self._closed})"
        )
