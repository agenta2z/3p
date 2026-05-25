"""
Thread Queue Service

A simple in-memory queue service using Python's standard queue.Queue.
Best suited for single-process applications with threading or quick prototyping.

IMPORTANT LIMITATION - Inter-Process Communication:
    This service does NOT support inter-process communication where
    producers and consumers run in separate processes. Each process
    has its own isolated queue instances.

    For inter-process communication, use RedisQueueService instead.

Best Use Cases:
- Single-process applications with multiple threads
- Quick prototyping without external dependencies
- Testing and development
- Thread-based concurrency (works perfectly)

NOT Suitable For:
- Separate producer/consumer processes (use RedisQueueService)
- Distributed systems (use RedisQueueService)
- Production inter-process communication (use RedisQueueService)

Features:
- In-memory queue storage (no external dependencies)
- Thread-safe operations using threading.Lock
- Supports multiple named queues
- Put/get any Python object (no pickling required)
- Blocking and non-blocking operations
- Works with closures and lambdas

Limitations:
- Does NOT work for inter-process communication (separate processes)
- Queues are not persistent (lost when program exits)
- All threads must be in the same process

Requirements:
    No external dependencies (uses standard library)

Usage (Single-Process with Threading):
    from rich_python_utils.service_utils.queue_service.thread_queue_service import (
        ThreadQueueService
    )
    import threading

    service = ThreadQueueService()

    def producer():
        for i in range(10):
            service.put('my_queue', f'item_{i}')

    def consumer():
        while True:
            item = service.get('my_queue', blocking=True, timeout=2.0)
            if item is None:
                break
            print(f"Got: {item}")

    # Use threads (NOT processes)
    t1 = threading.Thread(target=producer)
    t2 = threading.Thread(target=consumer)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

For Inter-Process Communication:
    # Use RedisQueueService instead
    from rich_python_utils.service_utils.queue_service.redis_queue_service import (
        RedisQueueService
    )

    service = RedisQueueService()
    # This works across separate processes
"""

import threading
from queue import Queue, Empty
from typing import Any, Optional, List, Dict

from attr import attrs, attrib

from .queue_service_base import QueueServiceBase


@attrs(slots=False)
class ThreadQueueService(QueueServiceBase):
    """
    In-memory queue service using Python's standard queue.Queue.

    CRITICAL LIMITATION:
        This service does NOT support inter-process communication where
        producers and consumers are in separate processes. Each process
        has its own isolated queues.

        Use RedisQueueService for inter-process communication.

    This service provides named queues where you can put/get any Python
    object. It works perfectly for:
    - Single-process applications with multiple threads
    - Thread-based concurrency
    - Quick prototyping

    It does NOT work for:
    - Separate producer/consumer processes
    - Distributed systems
    - Production inter-process communication

    Attributes:
        queues: Dictionary of queue_id -> Queue objects
        metadata: Dictionary storing queue metadata
        _lock: Lock for thread-safe access to queues dict
        _closed: Flag indicating if service is closed

    Example (Works - Threading):
        import threading
        service = ThreadQueueService()

        def producer():
            service.put('queue', 'data')

        def consumer():
            item = service.get('queue')

        t1 = threading.Thread(target=producer)
        t2 = threading.Thread(target=consumer)
        t1.start()
        t2.start()

    Example (Works - Closures):
        # Unlike multiprocessing.Manager, closures work fine
        def create_processor(multiplier):
            return lambda x: x * multiplier

        service.put('queue', create_processor(5))
        func = service.get('queue')
        result = func(10)  # Returns 50
    """

    queues: Dict[str, Queue] = attrib(init=False, factory=dict)
    metadata: Dict[str, Dict[str, Any]] = attrib(init=False, factory=dict)
    _lock: threading.Lock = attrib(init=False, factory=threading.Lock)
    _closed: bool = attrib(init=False, default=False)

    def create_queue(self, queue_id: str) -> bool:
        """
        Create a new queue with the given ID.

        Args:
            queue_id: Unique identifier for the queue

        Returns:
            True if queue was created, False if already exists
        """
        with self._lock:
            if queue_id in self.queues:
                return False

            self.queues[queue_id] = Queue()
            self.metadata[queue_id] = {'created': True}
            return True

    def put(self, queue_id: str, obj: Any, timeout: Optional[float] = None) -> bool:
        """
        Put an object onto the queue.

        Args:
            queue_id: Queue identifier
            obj: Any Python object (closures, lambdas, etc. all work)
            timeout: Optional timeout in seconds (not used, for API compatibility)

        Returns:
            True if successful

        Raises:
            RuntimeError: If service is closed
        """
        if self._closed:
            raise RuntimeError("Service is closed")

        # Get or create queue
        with self._lock:
            if queue_id not in self.queues:
                # Auto-create queue if it doesn't exist
                self.queues[queue_id] = Queue()
                self.metadata[queue_id] = {'created': True}
            queue = self.queues[queue_id]

        # Put the object
        queue.put(obj, block=False)
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
            timeout: Timeout in seconds (None = wait forever)

        Returns:
            Python object, or None if queue is empty (non-blocking)
            or timeout reached (blocking)

        Raises:
            RuntimeError: If service is closed
        """
        if self._closed:
            raise RuntimeError("Service is closed")

        with self._lock:
            if queue_id not in self.queues:
                return None
            queue = self.queues[queue_id]

        try:
            if blocking:
                # Block with optional timeout
                if timeout is None:
                    obj = queue.get(block=True)
                else:
                    obj = queue.get(block=True, timeout=timeout)
            else:
                # Non-blocking get
                obj = queue.get(block=False)

            return obj
        except Empty:
            # Queue is empty or timeout reached
            return None

    def peek(self, queue_id: str, index: int = -1) -> Optional[Any]:
        """
        Peek at an item in the queue without removing it.

        Note: This is not atomic and may be slow for large queues.
        Items are temporarily removed and re-inserted.

        Args:
            queue_id: Queue identifier
            index: Index to peek at (0=front, -1=back, default=-1)

        Returns:
            Python object at the specified index, or None if queue is empty

        Raises:
            IndexError: If index is out of range
            RuntimeError: If service is closed
        """
        if self._closed:
            raise RuntimeError("Service is closed")

        with self._lock:
            if queue_id not in self.queues:
                return None

            queue = self.queues[queue_id]

            # Get all items (not efficient, but necessary for peek)
            items = []
            try:
                while True:
                    items.append(queue.get(block=False))
            except Empty:
                pass

            # Check if index is valid
            if not items:
                return None

            if index < 0:
                # Negative indexing from the end
                actual_index = len(items) + index
            else:
                actual_index = index

            if actual_index < 0 or actual_index >= len(items):
                # Put items back
                for item in items:
                    queue.put(item, block=False)
                raise IndexError(f"Index {index} out of range for queue with {len(items)} items")

            # Get the item at the index
            result = items[actual_index]

            # Put all items back
            for item in items:
                queue.put(item, block=False)

            return result

    def size(self, queue_id: str) -> int:
        """
        Get the number of items in the queue.

        Args:
            queue_id: Queue identifier

        Returns:
            Number of items in the queue
        """
        with self._lock:
            if queue_id not in self.queues:
                return 0
            return self.queues[queue_id].qsize()

    def exists(self, queue_id: str) -> bool:
        """
        Check if a queue exists.

        Args:
            queue_id: Queue identifier

        Returns:
            True if queue exists, False otherwise
        """
        with self._lock:
            return queue_id in self.queues

    def delete(self, queue_id: str) -> bool:
        """
        Delete a queue and all its contents.

        Args:
            queue_id: Queue identifier

        Returns:
            True if queue was deleted, False if it didn't exist
        """
        with self._lock:
            if queue_id not in self.queues:
                return False

            # Remove from dictionaries
            del self.queues[queue_id]
            if queue_id in self.metadata:
                del self.metadata[queue_id]

            return True

    def clear(self, queue_id: str) -> int:
        """
        Clear all items from a queue without deleting it.

        Args:
            queue_id: Queue identifier

        Returns:
            Number of items removed
        """
        with self._lock:
            if queue_id not in self.queues:
                return 0

            queue = self.queues[queue_id]
            count = 0

            # Remove all items
            try:
                while True:
                    queue.get(block=False)
                    count += 1
            except Empty:
                pass

            return count

    def list_queues(self) -> List[str]:
        """
        List all queue IDs.

        Returns:
            List of queue identifiers
        """
        with self._lock:
            return list(self.queues.keys())

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
        Check if service is responsive.

        Returns:
            True if service is responsive, False otherwise
        """
        return not self._closed

    def close(self):
        """
        Close the service and clean up resources.
        """
        if not self._closed:
            self._closed = True
            # Clear all queues
            with self._lock:
                self.queues.clear()
                self.metadata.clear()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def __repr__(self) -> str:
        """String representation."""
        try:
            num_queues = len(self.list_queues())
        except:
            num_queues = "unknown"
        return f"ThreadQueueService(queues={num_queues}, closed={self._closed})"
