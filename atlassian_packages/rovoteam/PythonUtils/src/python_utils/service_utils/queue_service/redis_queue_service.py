"""
Redis Queue Service

A generic queue service built on Redis that allows multiple named queues
where you can put/get any Python object.

Features:
- Create multiple queues with unique IDs
- Put any serializable Python object onto a queue
- Get objects from queue (blocking or non-blocking)
- Thread-safe and process-safe
- Supports multiple producers and consumers
- Simple API: create_queue, put, get, size, exists, delete, list_queues

Requirements:
    pip install redis

Usage:
    # Start Redis server first (Docker or local installation)
    # docker run -d -p 6379:6379 redis

    # Create service
    service = RedisQueueService(host='localhost', port=6379)

    # Create queue
    service.create_queue('my_queue')

    # Put object
    service.put('my_queue', {'message': 'hello', 'value': 42})

    # Get object (blocking)
    obj = service.get('my_queue', blocking=True, timeout=5)

    # Get object (non-blocking)
    obj = service.get('my_queue', blocking=False)

    # Check queue size
    size = service.size('my_queue')

    # List all queues
    queues = service.list_queues()
"""

import pickle
import json
from typing import Any, Optional, List, Dict
import redis
from redis.exceptions import ConnectionError, TimeoutError

from attr import attrs, attrib

from .queue_service_base import QueueServiceBase


@attrs(slots=False)
class RedisQueueService(QueueServiceBase):
    """
    Generic queue service using Redis as backend.

    This service provides named queues where you can put/get any Python object.
    Multiple processes can safely access the same queues.

    Attributes:
        host: Redis server host
        port: Redis server port
        db: Redis database number
        redis_client: Redis connection client
        namespace: Prefix for queue keys (to avoid collisions)
        serialization: Serialization method ('pickle' or 'json')
    """

    host: str = attrib(default='localhost')
    port: int = attrib(default=6379)
    db: int = attrib(default=0)
    namespace: str = attrib(default='queue')
    serialization: str = attrib(default='pickle')
    decode_responses: bool = attrib(default=False)
    redis_client: redis.Redis = attrib(init=False)

    def __attrs_post_init__(self):
        """
        Initialize Redis queue service after attrs initialization.

        Raises:
            ConnectionError: If cannot connect to Redis server
        """
        # Create Redis client
        try:
            self.redis_client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                decode_responses=self.decode_responses,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            self.redis_client.ping()
        except (ConnectionError, TimeoutError) as e:
            raise ConnectionError(
                f"Cannot connect to Redis at {self.host}:{self.port}. "
                f"Make sure Redis server is running. Error: {e}"
            )

    def _get_queue_key(self, queue_id: str) -> str:
        """
        Get the Redis key for a queue.

        Args:
            queue_id: Queue identifier

        Returns:
            Full Redis key with namespace prefix
        """
        return f"{self.namespace}:{queue_id}"

    def _serialize(self, obj: Any) -> bytes:
        """
        Serialize Python object to bytes.

        Args:
            obj: Python object to serialize

        Returns:
            Serialized bytes

        Raises:
            ValueError: If serialization fails
        """
        try:
            if self.serialization == 'pickle':
                return pickle.dumps(obj)
            elif self.serialization == 'json':
                return json.dumps(obj).encode('utf-8')
            else:
                raise ValueError(f"Unknown serialization method: {self.serialization}")
        except Exception as e:
            raise ValueError(f"Failed to serialize object: {e}")

    def _deserialize(self, data: bytes) -> Any:
        """
        Deserialize bytes to Python object.

        Args:
            data: Serialized bytes

        Returns:
            Deserialized Python object

        Raises:
            ValueError: If deserialization fails
        """
        try:
            if self.serialization == 'pickle':
                return pickle.loads(data)
            elif self.serialization == 'json':
                return json.loads(data.decode('utf-8'))
            else:
                raise ValueError(f"Unknown serialization method: {self.serialization}")
        except Exception as e:
            raise ValueError(f"Failed to deserialize data: {e}")

    def create_queue(self, queue_id: str) -> bool:
        """
        Create a new queue with the given ID.

        Note: In Redis, queues are created implicitly when first used.
        This method is provided for API consistency and can be used to
        register the queue in metadata.

        Args:
            queue_id: Unique identifier for the queue

        Returns:
            True if queue was created, False if already exists
        """
        queue_key = self._get_queue_key(queue_id)
        # Check if queue already exists (has items or is registered)
        exists = self.redis_client.exists(queue_key)
        return not exists  # Return True if newly created

    def put(self, queue_id: str, obj: Any, timeout: Optional[float] = None) -> bool:
        """
        Put an object onto the queue.

        Args:
            queue_id: Queue identifier
            obj: Any serializable Python object
            timeout: Optional timeout in seconds (for future use)

        Returns:
            True if successful

        Raises:
            ValueError: If serialization fails
            ConnectionError: If Redis connection fails
        """
        queue_key = self._get_queue_key(queue_id)
        serialized = self._serialize(obj)

        # Use LPUSH to add to the left (head) of the list
        # RPOP will remove from right (tail), giving FIFO behavior
        self.redis_client.lpush(queue_key, serialized)
        return True

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
            ConnectionError: If Redis connection fails
        """
        queue_key = self._get_queue_key(queue_id)

        if blocking:
            # Use BRPOP for blocking pop (removes from right/tail)
            if timeout is None:
                # Wait forever (Redis BRPOP timeout=0 means wait indefinitely)
                result = self.redis_client.brpop(queue_key, timeout=0)
            else:
                # Wait for specified timeout
                result = self.redis_client.brpop(queue_key, timeout=int(timeout))

            if result is None:
                return None  # Timeout reached

            # result is a tuple: (key, value)
            _, serialized = result
        else:
            # Use RPOP for non-blocking pop
            serialized = self.redis_client.rpop(queue_key)

            if serialized is None:
                return None  # Queue is empty

        return self._deserialize(serialized)

    def peek(self, queue_id: str, index: int = -1) -> Optional[Any]:
        """
        Peek at an item in the queue without removing it.

        Args:
            queue_id: Queue identifier
            index: Index to peek at (0=head, -1=tail, default=-1)

        Returns:
            Deserialized Python object, or None if queue is empty

        Raises:
            ValueError: If deserialization fails
        """
        queue_key = self._get_queue_key(queue_id)
        serialized = self.redis_client.lindex(queue_key, index)

        if serialized is None:
            return None

        return self._deserialize(serialized)

    def size(self, queue_id: str) -> int:
        """
        Get the number of items in the queue.

        Args:
            queue_id: Queue identifier

        Returns:
            Number of items in the queue
        """
        queue_key = self._get_queue_key(queue_id)
        return self.redis_client.llen(queue_key)

    def exists(self, queue_id: str) -> bool:
        """
        Check if a queue exists.

        Args:
            queue_id: Queue identifier

        Returns:
            True if queue exists, False otherwise
        """
        queue_key = self._get_queue_key(queue_id)
        return self.redis_client.exists(queue_key) > 0

    def delete(self, queue_id: str) -> bool:
        """
        Delete a queue and all its contents.

        Args:
            queue_id: Queue identifier

        Returns:
            True if queue was deleted, False if it didn't exist
        """
        queue_key = self._get_queue_key(queue_id)
        deleted = self.redis_client.delete(queue_key)
        return deleted > 0

    def clear(self, queue_id: str) -> int:
        """
        Clear all items from a queue without deleting it.

        Args:
            queue_id: Queue identifier

        Returns:
            Number of items removed
        """
        queue_key = self._get_queue_key(queue_id)
        size = self.size(queue_id)
        self.redis_client.delete(queue_key)
        return size

    def list_queues(self) -> List[str]:
        """
        List all queue IDs in this namespace.

        Returns:
            List of queue IDs (without namespace prefix)
        """
        pattern = f"{self.namespace}:*"
        keys = self.redis_client.keys(pattern)

        # Remove namespace prefix from keys
        queue_ids = []
        for key in keys:
            # Decode if bytes
            if isinstance(key, bytes):
                key = key.decode('utf-8')
            # Remove namespace prefix
            queue_id = key[len(self.namespace) + 1:]  # +1 for the ':'
            queue_ids.append(queue_id)

        return queue_ids

    def get_stats(self, queue_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics about queues.

        Args:
            queue_id: Optional queue ID to get stats for a specific queue.
                     If None, returns stats for all queues.

        Returns:
            Dictionary with queue statistics
        """
        if queue_id:
            # Stats for specific queue
            return {
                'queue_id': queue_id,
                'size': self.size(queue_id),
                'exists': self.exists(queue_id)
            }
        else:
            # Stats for all queues
            queues = self.list_queues()
            stats = {
                'total_queues': len(queues),
                'queues': {}
            }
            for qid in queues:
                stats['queues'][qid] = {
                    'size': self.size(qid),
                    'exists': self.exists(qid)
                }
            return stats

    def ping(self) -> bool:
        """
        Check if Redis server is responsive.

        Returns:
            True if server is responsive, False otherwise
        """
        try:
            return self.redis_client.ping()
        except:
            return False

    def close(self):
        """Close the Redis connection."""
        if self.redis_client:
            self.redis_client.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"RedisQueueService(host='{self.host}', port={self.port}, "
            f"db={self.db}, namespace='{self.namespace}', "
            f"serialization='{self.serialization}')"
        )
