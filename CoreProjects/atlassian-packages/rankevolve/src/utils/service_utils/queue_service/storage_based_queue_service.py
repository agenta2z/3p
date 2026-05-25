"""
Storage-Based Queue Service

A persistent, multiprocessing-capable queue service using OnStorageLists.
Provides true inter-process communication through file-based storage.

Key Features:
- TRUE multiprocessing support - works across separate processes
- Persistent queues - survive program restarts
- No external dependencies (uses file system)
- Thread-safe and process-safe operations
- Supports multiple named queues
- Put/get any JSON-serializable Python object
- Blocking and non-blocking operations with timeout support
- File locking for concurrent access

Advantages over ThreadQueueService:
- Works across separate processes (producer/consumer in different processes)
- Queues persist between program runs
- No Manager connection issues
- Simple file-based implementation

Advantages over RedisQueueService:
- No external dependencies (no Redis server needed)
- Persistent by default
- Simpler setup for local development

Limitations:
- Slower than in-memory solutions (Redis, ThreadQueue)
- Limited to JSON-serializable objects (or custom serialization)
- File I/O overhead
- Not suitable for very high throughput (>1000 ops/sec)
- Requires shared file system for distributed systems

Best Use Cases:
- Inter-process communication on single machine
- Persistent task queues
- Development/testing without Redis
- Low to medium throughput applications
- Data pipeline checkpointing
- Job queues that need to survive restarts

Requirements:
    No external dependencies (uses standard library + OnStorageLists)

Usage (Multiprocessing):
    from rich_python_utils.service_utils.queue_service.storage_queue_service import (
        StorageBasedQueueService
    )
    import multiprocessing as mp

    def producer():
        service = StorageBasedQueueService(root_path='/tmp/queues')
        for i in range(10):
            service.put('my_queue', {'task': f'item_{i}'})
        service.close()

    def consumer():
        service = StorageBasedQueueService(root_path='/tmp/queues')
        while True:
            item = service.get('my_queue', blocking=True, timeout=2.0)
            if item is None:
                break
            print(f"Got: {item}")
        service.close()

    # This WORKS - processes share the same file-based queues
    p1 = mp.Process(target=producer)
    p2 = mp.Process(target=consumer)
    p1.start()
    p2.start()
    p1.join()
    p2.join()

Usage (Context Manager):
    with StorageBasedQueueService(root_path='/tmp/queues') as service:
        service.put('queue', {'data': 'value'})
        item = service.get('queue')
"""

import os
import sys
import time
import tempfile
import pickle
import base64
import threading
from pathlib import Path
from typing import Any, Optional, List, Dict, Callable
from datetime import datetime

# Platform-specific imports for file locking
if sys.platform == 'win32':
    import msvcrt
else:
    import fcntl

from attr import attrs, attrib, Factory

from rankevolve.src.utils.io_utils.on_storage_lists import OnStorageLists
from .queue_service_base import QueueServiceBase


@attrs(slots=False)
class StorageBasedQueueService(QueueServiceBase):
    """
    File-based queue service using OnStorageLists for persistent storage.

    This service provides true multiprocessing support through file-based
    storage. Multiple processes can safely access the same queues through
    the shared file system.

    Attributes:
        root_path: Root directory for queue storage
        archive_popped_items: Whether to archive popped items instead of deleting them. Defaults to False.
        archive_dir_name: Name of subdirectory for archived items. Defaults to '_archive'.
        storage: OnStorageLists instance for queue data
        metadata_storage: OnStorageLists instance for queue metadata
        _closed: Flag indicating if service is closed
        _lock_file: File handle for global lock
        _lock_path: Path to lock file

    Example:
        # Producer process
        service = StorageBasedQueueService(root_path='/tmp/queues')
        service.put('tasks', {'task_id': 1, 'action': 'process'})

        # Consumer process (separate process)
        service = StorageBasedQueueService(root_path='/tmp/queues')
        task = service.get('tasks')  # Gets the task from producer
    """

    root_path: Optional[str] = attrib(default=None)
    archive_popped_items: bool = attrib(default=False)
    archive_dir_name: str = attrib(default='_archive')
    use_pickle: bool = attrib(default=False)
    """Use pickle serialization instead of JSON. Required for storing non-JSON-serializable objects like Task."""
    _temp_dir: bool = attrib(init=False, default=False)
    storage: OnStorageLists = attrib(init=False)
    metadata_storage: OnStorageLists = attrib(init=False)
    _lock_path: str = attrib(init=False)
    _lock_file: Optional[Any] = attrib(init=False, default=None)
    _thread_lock: threading.Lock = attrib(init=False, factory=threading.Lock)
    _closed: bool = attrib(init=False, default=False)

    def __attrs_post_init__(self):
        """
        Initialize storage-based queue service after attrs initialization.

        Root directory for queue storage. If None, uses a
        temporary directory (not persistent across runs).
        """
        if self.root_path is None:
            # Use temporary directory
            self.root_path = tempfile.mkdtemp(prefix='storage_queue_')
            self._temp_dir = True
        else:
            self._temp_dir = False
            # Ensure directory exists
            Path(self.root_path).mkdir(parents=True, exist_ok=True)

        # Configure serialization method
        if self.use_pickle:
            # Use base64-encoded pickle since OnStorageLists uses text mode files
            def pickle_load(f):
                b64_str = f.read()
                return pickle.loads(base64.b64decode(b64_str))
            def pickle_dump(obj, f):
                b64_str = base64.b64encode(pickle.dumps(obj)).decode('ascii')
                f.write(b64_str)
            read_method = pickle_load
            write_method = pickle_dump
            file_extension = '.pkl'
        else:
            read_method = None  # Use default JSON
            write_method = None
            file_extension = '.json'

        # Create storage for queue data
        storage_kwargs = {
            'root_path': os.path.join(self.root_path, 'queues'),
            'default_list_key': 'default',
            'archive_enabled': self.archive_popped_items,
            'archive_dir_name': self.archive_dir_name,
        }
        if self.use_pickle:
            storage_kwargs['read_method'] = read_method
            storage_kwargs['write_method'] = write_method
            storage_kwargs['file_extension'] = file_extension
        self.storage = OnStorageLists(**storage_kwargs)

        # Create storage for metadata (always JSON for human-readability)
        self.metadata_storage = OnStorageLists(
            root_path=os.path.join(self.root_path, 'metadata'),
            default_list_key='default'
        )

        # Lock file for global operations
        self._lock_path = os.path.join(self.root_path, '.lock')
        self._lock_file = None

        # Service state
        self._closed = False

    def _acquire_lock(self, timeout: Optional[float] = None):
        """
        Acquire global lock for atomic operations.

        Uses both a threading.Lock (for intra-process thread safety) and
        a file lock via fcntl.flock (for inter-process safety). The flock
        is process-level and does NOT protect against concurrent threads
        within the same process.

        Args:
            timeout: Optional timeout in seconds

        Returns:
            True if lock acquired, False if timeout

        Raises:
            RuntimeError: If service is closed
        """
        if self._closed:
            raise RuntimeError("Service is closed")

        # Acquire thread lock first (intra-process safety)
        if not self._thread_lock.acquire(timeout=timeout if timeout is not None else -1):
            return False

        # Open lock file
        if self._lock_file is None or self._lock_file.closed:
            self._lock_file = open(self._lock_path, 'a')

        start_time = time.time()
        while True:
            try:
                # Try to acquire exclusive lock (platform-specific)
                if sys.platform == 'win32':
                    # Windows: use msvcrt
                    msvcrt.locking(self._lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    # Unix: use fcntl
                    fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return True
            except (IOError, OSError):
                # Lock is held by another process
                if timeout is not None:
                    elapsed = time.time() - start_time
                    if elapsed >= timeout:
                        self._thread_lock.release()
                        return False
                # Wait a bit before retrying
                time.sleep(0.01)

    def _release_lock(self):
        """Release global lock (both file lock and thread lock)."""
        try:
            if self._lock_file and not self._lock_file.closed:
                try:
                    if sys.platform == 'win32':
                        # Windows: use msvcrt
                        msvcrt.locking(self._lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        # Unix: use fcntl
                        fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
                except (IOError, OSError):
                    pass
        finally:
            self._thread_lock.release()

    def create_queue(self, queue_id: str) -> bool:
        """
        Create a new queue with the given ID.

        Args:
            queue_id: Unique identifier for the queue

        Returns:
            True if queue was created, False if already exists
        """
        if not self._acquire_lock(timeout=5.0):
            raise TimeoutError("Could not acquire lock to create queue")

        try:
            # Check if queue already exists
            if self.exists(queue_id):
                return False

            # Create metadata entry
            metadata = {
                'queue_id': queue_id,
                'created_at': datetime.now().isoformat(),
                'created': True
            }
            self.metadata_storage.append(metadata, list_key=f'queue.{queue_id}.meta')

            return True
        finally:
            self._release_lock()

    def put(self, queue_id: str, obj: Any, timeout: Optional[float] = None) -> bool:
        """
        Put an object onto the queue.

        Args:
            queue_id: Queue identifier
            obj: Any JSON-serializable Python object
            timeout: Optional timeout in seconds (for lock acquisition)

        Returns:
            True if successful

        Raises:
            RuntimeError: If service is closed
            ValueError: If object cannot be serialized
            TimeoutError: If lock cannot be acquired within timeout
        """
        if self._closed:
            raise RuntimeError("Service is closed")

        lock_timeout = timeout if timeout is not None else 5.0
        if not self._acquire_lock(timeout=lock_timeout):
            raise TimeoutError(f"Could not acquire lock within {lock_timeout}s")

        try:
            # Auto-create queue if it doesn't exist
            if not self.exists(queue_id):
                metadata = {
                    'queue_id': queue_id,
                    'created_at': datetime.now().isoformat(),
                    'created': True
                }
                self.metadata_storage.append(metadata, list_key=f'queue.{queue_id}.meta')

            # Add item to queue
            item_data = {
                'data': obj,
                'timestamp': datetime.now().isoformat()
            }
            self.storage.append(item_data, list_key=f'queue.{queue_id}.items')

            return True
        finally:
            self._release_lock()

    def get(
        self,
        queue_id: str,
        blocking: bool = True,
        timeout: Optional[float] = None
    ) -> Optional[Any]:
        """
        Get an object from the queue (FIFO - first in, first out).

        Args:
            queue_id: Queue identifier
            blocking: If True, block until item available or timeout
            timeout: Timeout in seconds (None = wait forever for blocking)

        Returns:
            Python object, or None if queue is empty (non-blocking)
            or timeout reached (blocking)

        Raises:
            RuntimeError: If service is closed
        """
        if self._closed:
            raise RuntimeError("Service is closed")

        start_time = time.time()

        while True:
            # Try to get an item
            if not self._acquire_lock(timeout=1.0):
                if not blocking:
                    return None
                # Check timeout
                if timeout is not None:
                    elapsed = time.time() - start_time
                    if elapsed >= timeout:
                        return None
                continue

            try:
                # Check if queue exists and has items
                size = self.storage._get_list_size(list_key=f'queue.{queue_id}.items')
                if size == 0:
                    if not blocking:
                        return None
                    # Check timeout
                    if timeout is not None:
                        elapsed = time.time() - start_time
                        if elapsed >= timeout:
                            return None
                else:
                    # Pop first item (FIFO)
                    try:
                        item_data = self.storage.pop(index=0, list_key=f'queue.{queue_id}.items')
                    except (IndexError, FileNotFoundError):
                        # Race condition: queue was emptied/deleted between
                        # the size check and the pop (e.g. session cleanup).
                        return None
                    if item_data is not None:
                        return item_data.get('data')
                    return None
            finally:
                self._release_lock()

            # If blocking and no item, wait a bit before retrying
            if blocking:
                time.sleep(0.05)
            else:
                return None

    def peek(self, queue_id: str, index: int = 0) -> Optional[Any]:
        """
        Peek at an item in the queue without removing it.

        Args:
            queue_id: Queue identifier
            index: Index to peek at (0=front/head, -1=back/tail, default=0)

        Returns:
            Python object at the specified index, or None if queue is empty

        Raises:
            IndexError: If index is out of range
            RuntimeError: If service is closed
        """
        if self._closed:
            raise RuntimeError("Service is closed")

        if not self._acquire_lock(timeout=5.0):
            raise TimeoutError("Could not acquire lock to peek")

        try:
            size = self.storage._get_list_size(list_key=f'queue.{queue_id}.items')
            if size == 0:
                return None

            # Handle negative indexing
            if index < 0:
                actual_index = size + index
            else:
                actual_index = index

            if actual_index < 0 or actual_index >= size:
                raise IndexError(f"Index {index} out of range for queue with {size} items")

            item_data = self.storage.get(index=actual_index, list_key=f'queue.{queue_id}.items')
            if item_data is not None:
                return item_data.get('data')
            return None
        finally:
            self._release_lock()

    def size(self, queue_id: str) -> int:
        """
        Get the number of items in the queue.

        Args:
            queue_id: Queue identifier

        Returns:
            Number of items in the queue
        """
        if not self._acquire_lock(timeout=5.0):
            return 0

        try:
            return self.storage._get_list_size(list_key=f'queue.{queue_id}.items')
        finally:
            self._release_lock()

    def exists(self, queue_id: str) -> bool:
        """
        Check if a queue exists.

        Args:
            queue_id: Queue identifier

        Returns:
            True if queue exists, False otherwise
        """
        # Check if metadata exists
        meta_size = self.metadata_storage._get_list_size(list_key=f'queue.{queue_id}.meta')
        return meta_size > 0

    def delete(self, queue_id: str) -> bool:
        """
        Delete a queue and all its contents.

        Args:
            queue_id: Queue identifier

        Returns:
            True if queue was deleted, False if it didn't exist
        """
        if not self._acquire_lock(timeout=5.0):
            raise TimeoutError("Could not acquire lock to delete queue")

        try:
            if not self.exists(queue_id):
                return False

            # Clear queue data
            self.storage.clear(list_key=f'queue.{queue_id}.items')

            # Clear metadata
            self.metadata_storage.clear(list_key=f'queue.{queue_id}.meta')

            return True
        finally:
            self._release_lock()

    def clear(self, queue_id: str) -> int:
        """
        Clear all items from a queue without deleting it.

        Args:
            queue_id: Queue identifier

        Returns:
            Number of items removed
        """
        if not self._acquire_lock(timeout=5.0):
            raise TimeoutError("Could not acquire lock to clear queue")

        try:
            size = self.storage._get_list_size(list_key=f'queue.{queue_id}.items')
            self.storage.clear(list_key=f'queue.{queue_id}.items')
            return size
        finally:
            self._release_lock()

    def list_queues(self) -> List[str]:
        """
        List all queue IDs.

        Returns:
            List of queue identifiers
        """
        if not self._acquire_lock(timeout=5.0):
            return []

        try:
            # List all directories under metadata/queue/
            queues_dir = Path(self.root_path) / 'metadata' / 'queue'
            if not queues_dir.exists():
                return []

            queue_ids = []
            for queue_dir in queues_dir.iterdir():
                if queue_dir.is_dir() and not queue_dir.name.startswith('.'):
                    # Check if it has metadata (to confirm it's a real queue)
                    meta_files = list(queue_dir.glob('meta/*.json'))
                    if meta_files:
                        queue_ids.append(queue_dir.name)

            return sorted(queue_ids)
        finally:
            self._release_lock()

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
                'exists': self.exists(queue_id),
                'root_path': self.root_path
            }
        else:
            # Stats for all queues
            queues = self.list_queues()
            stats = {
                'total_queues': len(queues),
                'root_path': self.root_path,
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
        if self._closed:
            return False

        try:
            # Try to acquire and release lock
            if self._acquire_lock(timeout=1.0):
                self._release_lock()
                return True
            return False
        except:
            return False

    def close(self):
        """
        Close the service and clean up resources.
        """
        if not self._closed:
            self._closed = True

            # Release lock if held
            try:
                self._release_lock()
            except:
                pass

            # Close lock file
            if self._lock_file and not self._lock_file.closed:
                try:
                    self._lock_file.close()
                except:
                    pass
                self._lock_file = None

            # Clean up temp directory if created
            if self._temp_dir:
                import shutil
                try:
                    shutil.rmtree(self.root_path)
                except:
                    pass

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
        return f"StorageBasedQueueService(root_path='{self.root_path}', queues={num_queues}, closed={self._closed})"
