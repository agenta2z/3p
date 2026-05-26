"""
Queue Service Base Class

Abstract base class defining the interface for queue services.
All queue service implementations should inherit from this class.

This ensures a consistent API across different backend implementations
(Redis, multiprocessing, RabbitMQ, etc.).
"""

from abc import ABC, abstractmethod
from typing import Any, Optional, List, Dict

from attr import attrs


@attrs(slots=False)
class QueueServiceBase(ABC):
    """
    Abstract base class for queue services.

    Defines the standard interface that all queue service implementations
    must implement. This allows different backends (Redis, multiprocessing,
    etc.) to be used interchangeably.

    Core Operations:
        - create_queue: Create a new named queue
        - put: Add an object to a queue
        - get: Remove and return an object from a queue
        - peek: View an object without removing it
        - size: Get the number of items in a queue
        - exists: Check if a queue exists
        - delete: Delete a queue and all its contents
        - clear: Remove all items from a queue
        - list_queues: List all queue IDs
        - get_stats: Get statistics about queues
        - ping: Check if service is responsive
        - close: Close the service connection

    Context Manager Support:
        Services should support the 'with' statement for automatic cleanup.
    """

    @abstractmethod
    def create_queue(self, queue_id: str) -> bool:
        """
        Create a new queue with the given ID.

        Args:
            queue_id: Unique identifier for the queue

        Returns:
            True if queue was created, False if already exists
        """
        pass

    @abstractmethod
    def put(self, queue_id: str, obj: Any, timeout: Optional[float] = None) -> bool:
        """
        Put an object onto the queue.

        Args:
            queue_id: Queue identifier
            obj: Any serializable Python object
            timeout: Optional timeout in seconds

        Returns:
            True if successful

        Raises:
            ValueError: If serialization fails
            Exception: If backend operation fails
        """
        pass

    @abstractmethod
    def get(
        self,
        queue_id: str,
        blocking: bool = True,
        timeout: Optional[float] = None
    ) -> Optional[Any]:
        """
        Get an object from the queue.

        Args:
            queue_id: Queue identifier
            blocking: If True, block until item available or timeout
            timeout: Timeout in seconds (None = wait forever, 0 = non-blocking)

        Returns:
            Deserialized Python object, or None if queue is empty (non-blocking)
            or timeout reached (blocking)

        Raises:
            ValueError: If deserialization fails
            Exception: If backend operation fails
        """
        pass

    @abstractmethod
    def peek(self, queue_id: str, index: int = -1) -> Optional[Any]:
        """
        Peek at an item in the queue without removing it.

        Args:
            queue_id: Queue identifier
            index: Index to peek at (0=head/front, -1=tail/back, default=-1)

        Returns:
            Python object at the specified index, or None if queue is empty

        Raises:
            ValueError: If deserialization fails
            IndexError: If index is out of range
        """
        pass

    @abstractmethod
    def size(self, queue_id: str) -> int:
        """
        Get the number of items in the queue.

        Args:
            queue_id: Queue identifier

        Returns:
            Number of items in the queue
        """
        pass

    @abstractmethod
    def exists(self, queue_id: str) -> bool:
        """
        Check if a queue exists.

        Args:
            queue_id: Queue identifier

        Returns:
            True if queue exists, False otherwise
        """
        pass

    @abstractmethod
    def delete(self, queue_id: str) -> bool:
        """
        Delete a queue and all its contents.

        Args:
            queue_id: Queue identifier

        Returns:
            True if queue was deleted, False if it didn't exist
        """
        pass

    @abstractmethod
    def clear(self, queue_id: str) -> int:
        """
        Clear all items from a queue without deleting it.

        Args:
            queue_id: Queue identifier

        Returns:
            Number of items removed
        """
        pass

    @abstractmethod
    def list_queues(self) -> List[str]:
        """
        List all queue IDs.

        Returns:
            List of queue identifiers
        """
        pass

    @abstractmethod
    def get_stats(self, queue_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics about queues.

        Args:
            queue_id: Optional queue ID to get stats for a specific queue.
                     If None, returns stats for all queues.

        Returns:
            Dictionary with queue statistics
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
    def close(self):
        """
        Close the service connection and clean up resources.
        """
        pass

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
