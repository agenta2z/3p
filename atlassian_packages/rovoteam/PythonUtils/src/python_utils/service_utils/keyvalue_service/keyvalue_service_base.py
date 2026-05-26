"""
KeyValue Service Base Class

Abstract base class defining the interface for key-value storage services.
All key-value service implementations should inherit from this class.

This ensures a consistent API across different backend implementations
(memory, file, SQLite, Redis, etc.).
"""

from abc import ABC, abstractmethod
from typing import Any, Optional, List, Dict

from attr import attrs


@attrs(slots=False)
class KeyValueServiceBase(ABC):
    """
    Abstract base class for key-value storage services.

    Defines the standard interface that all key-value service implementations
    must implement. This allows different backends (memory, file, SQLite,
    Redis, etc.) to be used interchangeably.

    Core Operations:
        - get: Retrieve a value by key
        - put: Store a value by key (upsert semantics)
        - delete: Remove a key-value pair
        - exists: Check if a key exists
        - keys: List all keys in a namespace
        - size: Get the number of key-value pairs in a namespace
        - clear: Remove all key-value pairs in a namespace
        - namespaces: List all namespaces
        - get_stats: Get statistics about the service
        - ping: Check if service is responsive
        - close: Close the service connection

    Batch Operations:
        - get_many: Retrieve multiple values (default iterates; override for optimization)
        - put_many: Store multiple values (default iterates; override for optimization)

    Namespace Semantics:
        - namespace=None maps to "_default" internally
        - Each backend handles this mapping in its own implementation

    Context Manager Support:
        Services support the 'with' statement for automatic cleanup.
    """

    @abstractmethod
    def get(self, key: str, namespace: Optional[str] = None) -> Optional[Any]:
        """
        Retrieve a value by key.

        Args:
            key: The key to look up
            namespace: Optional namespace to scope the lookup.
                      None maps to "_default" internally.

        Returns:
            The stored value, or None if the key does not exist
        """
        pass

    @abstractmethod
    def put(self, key: str, value: Any, namespace: Optional[str] = None) -> None:
        """
        Store a value by key (upsert semantics).

        If the key already exists, the value is overwritten.

        Args:
            key: The key to store under
            value: Any JSON-serializable Python object
            namespace: Optional namespace to scope the storage.
                      None maps to "_default" internally.

        Raises:
            TypeError: If the value is not JSON-serializable
        """
        pass

    @abstractmethod
    def delete(self, key: str, namespace: Optional[str] = None) -> bool:
        """
        Delete a key-value pair.

        Args:
            key: The key to delete
            namespace: Optional namespace to scope the deletion.
                      None maps to "_default" internally.

        Returns:
            True if the key was deleted, False if it did not exist
        """
        pass

    @abstractmethod
    def exists(self, key: str, namespace: Optional[str] = None) -> bool:
        """
        Check if a key exists.

        Args:
            key: The key to check
            namespace: Optional namespace to scope the check.
                      None maps to "_default" internally.

        Returns:
            True if the key exists, False otherwise
        """
        pass

    @abstractmethod
    def keys(self, namespace: Optional[str] = None) -> List[str]:
        """
        List all keys in a namespace.

        Args:
            namespace: Optional namespace to list keys for.
                      None maps to "_default" internally.

        Returns:
            List of key strings in the namespace
        """
        pass

    @abstractmethod
    def size(self, namespace: Optional[str] = None) -> int:
        """
        Get the number of key-value pairs in a namespace.

        Args:
            namespace: Optional namespace to get the size of.
                      None maps to "_default" internally.

        Returns:
            Number of key-value pairs in the namespace
        """
        pass

    @abstractmethod
    def clear(self, namespace: Optional[str] = None) -> int:
        """
        Remove all key-value pairs in a namespace.

        Args:
            namespace: Optional namespace to clear.
                      None maps to "_default" internally.

        Returns:
            Number of items removed
        """
        pass

    @abstractmethod
    def namespaces(self) -> List[str]:
        """
        List all namespaces that contain data.

        Returns:
            List of namespace strings
        """
        pass

    @abstractmethod
    def get_stats(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics about the service.

        Args:
            namespace: Optional namespace to get stats for.
                      If None, returns stats for all namespaces.

        Returns:
            Dictionary with service statistics
        """
        pass

    @abstractmethod
    def ping(self) -> bool:
        """
        Check if service is responsive.

        Returns:
            True if service is responsive, False otherwise
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """
        Close the service connection and clean up resources.

        This method is idempotent — calling it multiple times is safe.
        """
        pass

    # ── Concrete batch methods (overridable for optimized implementations) ──

    def get_many(self, keys: List[str], namespace: Optional[str] = None) -> Dict[str, Any]:
        """
        Get multiple values by keys.

        Default implementation iterates over individual get calls.
        Override in backends that support batch operations for optimization
        (e.g., Redis pipelines, SQLite executemany).

        Args:
            keys: List of keys to retrieve
            namespace: Optional namespace to scope the lookups.
                      None maps to "_default" internally.

        Returns:
            Dictionary mapping keys to their values.
            Keys with no stored value are omitted from the result.
        """
        return {k: v for k, v in ((k, self.get(k, namespace)) for k in keys) if v is not None}

    def put_many(self, items: Dict[str, Any], namespace: Optional[str] = None) -> None:
        """
        Store multiple key-value pairs.

        Default implementation iterates over individual put calls.
        Override in backends that support batch operations for optimization
        (e.g., Redis pipelines, SQLite executemany).

        Args:
            items: Dictionary mapping keys to values
            namespace: Optional namespace to scope the storage.
                      None maps to "_default" internally.
        """
        for key, value in items.items():
            self.put(key, value, namespace)

    # ── Context manager protocol ──

    @abstractmethod
    def __enter__(self):
        """Context manager entry."""
        pass

    @abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        pass

    @abstractmethod
    def __repr__(self) -> str:
        """String representation of the service."""
        pass
