"""
Email Queue Service

Email-based queue service using email threads as backing store.
Provides distributed, persistent queue operations through email synchronization.

This service wraps a local StorageBasedQueueService and synchronizes operations
with Gmail threads. Each queue is represented by an email thread with subject
'EmailQueue - {queue_id}', and operations are logged as JSON messages.

Features:
- Distributed queue access across machines
- Persistent storage in email
- Local caching for performance
- Automatic or manual synchronization
- Support for multiple email providers (Gmail, Outlook, etc.)

Requirements:
    - EmailClientBase implementation (e.g., GmailClient)
    - StorageBasedQueueService for local cache
    - Email account with API access

Usage:
    from python_utils.service_utils.email_utils.gmail_client import GmailClient
    from python_utils.service_utils.queue_service.storage_based_queue_service import (
        StorageBasedQueueService
    )
    from python_utils.service_utils.queue_service.email_queue_service import (
        EmailQueueService
    )
    
    # Create email client
    email_client = GmailClient(
        credentials_path='credentials.json',
        token_path='token.pickle'
    )
    
    # Create storage service
    storage_service = StorageBasedQueueService(
        root_path='/tmp/email_queues',
        archive_popped_items=True
    )
    
    # Create email queue service
    with EmailQueueService(
        email_client=email_client,
        storage_service=storage_service,
        email_address='queues@example.com',
        sync_interval=300.0
    ) as service:
        # Create queue
        service.create_queue('my_queue')
        
        # Put items
        service.put('my_queue', {'task': 'process_data'})
        
        # Get items
        item = service.get('my_queue')
"""

import time
import json
from typing import Any, Optional, List, Dict
from datetime import datetime, timedelta

from attr import attrs, attrib, Factory

from ..email_utils.email_client_base import EmailClientBase
from ..email_utils.models import QueueOperation, SyncState
from ..email_utils.utils import (
    extract_queue_id_from_subject,
    format_queue_subject
)
from .storage_based_queue_service import StorageBasedQueueService
from .queue_service_base import QueueServiceBase


@attrs(slots=False)
class EmailQueueService(QueueServiceBase):
    """
    Email-based queue service using email threads.
    
    Attributes:
        email_client: EmailClientBase instance for email operations
        storage_service: StorageBasedQueueService for local cache
        email_address: Email address for queue operations
        sync_interval: Seconds between automatic syncs (None = manual only)
        sync_on_read: Whether to sync before get operations
        last_sync_times: Dict mapping queue_id to last sync timestamp
        operation_id_counter: Counter for generating unique operation IDs
        _thread_id_cache: Cache of queue_id to thread_id mappings
        _sync_states: Cache of SyncState objects per queue
        _closed: Flag indicating if service is closed
    """
    email_client: EmailClientBase = attrib()
    storage_service: StorageBasedQueueService = attrib()
    email_address: str = attrib()
    sync_interval: Optional[float] = attrib(default=300.0)  # 5 minutes
    sync_on_read: bool = attrib(default=False)
    last_sync_times: Dict[str, datetime] = attrib(factory=dict)
    operation_id_counter: int = attrib(default=0)
    _thread_id_cache: Dict[str, str] = attrib(factory=dict)
    _sync_states: Dict[str, SyncState] = attrib(factory=dict)
    _closed: bool = attrib(init=False, default=False)
    
    def __attrs_post_init__(self):
        """Initialize email queue service after attrs initialization."""
        # Ensure email client is authenticated
        if not self.email_client.ping():
            self.email_client.authenticate()

    def _generate_operation_id(self) -> str:
        """
        Generate unique operation ID.
        
        Returns:
            Unique operation ID string
        """
        self.operation_id_counter += 1
        timestamp = int(time.time() * 1000)  # milliseconds
        return f"op_{timestamp}_{self.operation_id_counter:06d}"
    
    def _encode_operation(
        self,
        operation: str,
        queue_id: str,
        data: Optional[Any] = None
    ) -> str:
        """
        Encode queue operation as JSON string.
        
        Args:
            operation: Operation type ('put', 'get', 'clear', etc.)
            queue_id: Queue identifier
            data: Optional operation data
            
        Returns:
            JSON string representation
        """
        op = QueueOperation(
            operation=operation,
            queue_id=queue_id,
            operation_id=self._generate_operation_id(),
            timestamp=datetime.now(),
            data=data
        )
        return op.to_json()
    
    def _decode_operation(self, json_str: str) -> Dict[str, Any]:
        """
        Decode JSON operation string.
        
        Args:
            json_str: JSON string
            
        Returns:
            Dictionary with operation details
        """
        try:
            op = QueueOperation.from_json(json_str)
            return {
                'operation': op.operation,
                'queue_id': op.queue_id,
                'operation_id': op.operation_id,
                'timestamp': op.timestamp,
                'data': op.data
            }
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # Return None for invalid operations
            return None

    def _get_or_create_thread_id(self, queue_id: str) -> str:
        """
        Get thread ID for queue, creating if necessary.
        
        Args:
            queue_id: Queue identifier
            
        Returns:
            Thread ID
        """
        # Check cache first
        if queue_id in self._thread_id_cache:
            return self._thread_id_cache[queue_id]
        
        # Search for existing thread
        subject = format_queue_subject(queue_id)
        threads = self.email_client.search_threads_by_subject(subject)
        
        if threads:
            # Use existing thread
            thread_id = threads[0]['id']
        else:
            # Create new thread
            result = self.email_client.send_email(
                to=self.email_address,
                subject=subject,
                body=f"Queue created: {queue_id}\nTimestamp: {datetime.now().isoformat()}"
            )
            thread_id = result['thread_id']
        
        # Cache thread ID
        self._thread_id_cache[queue_id] = thread_id
        
        return thread_id
    
    def _send_operation_email(
        self,
        queue_id: str,
        operation: str,
        data: Optional[Any] = None
    ) -> bool:
        """
        Send email documenting queue operation.
        
        Args:
            queue_id: Queue identifier
            operation: Operation type
            data: Optional operation data
            
        Returns:
            True if successful
        """
        try:
            # Get thread ID
            thread_id = self._get_or_create_thread_id(queue_id)
            
            # Encode operation
            operation_json = self._encode_operation(operation, queue_id, data)
            
            # Send email
            subject = format_queue_subject(queue_id)
            self.email_client.send_email(
                to=self.email_address,
                subject=subject,
                body=operation_json,
                thread_id=thread_id
            )
            
            return True
            
        except Exception as e:
            # Log error but don't fail the operation
            print(f"Warning: Failed to send operation email: {e}")
            return False

    def create_queue(self, queue_id: str) -> bool:
        """
        Create a new queue with the given ID.
        
        Args:
            queue_id: Unique identifier for the queue
            
        Returns:
            True if queue was created, False if already exists
        """
        if self._closed:
            raise RuntimeError("Service is closed")
        
        # Check if queue already exists
        if self.exists(queue_id):
            return False
        
        # Create local storage queue
        self.storage_service.create_queue(queue_id)
        
        # Send initial email to create thread
        thread_id = self._get_or_create_thread_id(queue_id)
        
        # Initialize sync state
        self._sync_states[queue_id] = SyncState(
            queue_id=queue_id,
            thread_id=thread_id,
            last_sync_time=datetime.now()
        )
        self.last_sync_times[queue_id] = datetime.now()
        
        return True

    def exists(self, queue_id: str) -> bool:
        """
        Check if a queue exists.
        
        Args:
            queue_id: Queue identifier
            
        Returns:
            True if queue exists, False otherwise
        """
        # Check local storage first
        if self.storage_service.exists(queue_id):
            return True
        
        # Check email threads
        subject = format_queue_subject(queue_id)
        threads = self.email_client.search_threads_by_subject(subject)
        
        return len(threads) > 0
    
    def list_queues(self) -> List[str]:
        """
        List all queue IDs.
        
        Returns:
            List of queue identifiers
        """
        queue_ids = set()
        
        # Get queues from local storage
        local_queues = self.storage_service.list_queues()
        queue_ids.update(local_queues)
        
        # Get queues from email threads
        threads = self.email_client.search_threads_by_subject("EmailQueue")
        
        for thread in threads:
            subject = thread.get('subject', '')
            queue_id = extract_queue_id_from_subject(subject)
            if queue_id:
                queue_ids.add(queue_id)
        
        return sorted(list(queue_ids))

    def delete(self, queue_id: str) -> bool:
        """
        Delete a queue and all its contents.
        
        Args:
            queue_id: Queue identifier
            
        Returns:
            True if queue was deleted, False if it didn't exist
        """
        if not self.exists(queue_id):
            return False
        
        # Send delete operation email
        self._send_operation_email(queue_id, 'delete')
        
        # Delete local storage queue
        self.storage_service.delete(queue_id)
        
        # Clean up caches
        self._thread_id_cache.pop(queue_id, None)
        self._sync_states.pop(queue_id, None)
        self.last_sync_times.pop(queue_id, None)
        
        return True
    
    def clear(self, queue_id: str) -> int:
        """
        Clear all items from a queue without deleting it.
        
        Args:
            queue_id: Queue identifier
            
        Returns:
            Number of items removed
        """
        # Get count before clearing
        count = self.storage_service.size(queue_id)
        
        # Send clear operation email
        self._send_operation_email(queue_id, 'clear')
        
        # Clear local storage queue
        self.storage_service.clear(queue_id)
        
        return count

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
            RuntimeError: If service is closed
        """
        if self._closed:
            raise RuntimeError("Service is closed")
        
        # Auto-create queue if it doesn't exist
        if not self.exists(queue_id):
            self.create_queue(queue_id)
        
        # Add to local storage immediately
        self.storage_service.put(queue_id, obj, timeout=timeout)
        
        # Send operation email asynchronously (don't block on failure)
        try:
            self._send_operation_email(queue_id, 'put', data=obj)
        except Exception as e:
            print(f"Warning: Failed to send put operation email: {e}")
        
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
            timeout: Timeout in seconds
            
        Returns:
            Python object, or None if queue is empty
            
        Raises:
            RuntimeError: If service is closed
        """
        if self._closed:
            raise RuntimeError("Service is closed")
        
        # Optionally sync before get
        if self.sync_on_read:
            try:
                self._sync_queue(queue_id)
            except Exception as e:
                print(f"Warning: Sync before get failed: {e}")
        
        # Get from local storage
        item = self.storage_service.get(queue_id, blocking=blocking, timeout=timeout)
        
        # Send operation email if item was retrieved
        if item is not None:
            try:
                self._send_operation_email(queue_id, 'get', data=item)
            except Exception as e:
                print(f"Warning: Failed to send get operation email: {e}")
        
        return item

    def _sync_queue(self, queue_id: str) -> int:
        """
        Synchronize local queue with email thread.
        
        Args:
            queue_id: Queue identifier
            
        Returns:
            Number of operations processed
        """
        if not self.exists(queue_id):
            return 0
        
        # Get thread ID
        thread_id = self._get_or_create_thread_id(queue_id)
        
        # Get last sync time
        last_sync = self.last_sync_times.get(queue_id, datetime.min)
        
        # Fetch new messages since last sync
        try:
            messages = self.email_client.get_messages_since(thread_id, last_sync)
        except Exception as e:
            print(f"Warning: Failed to fetch messages for sync: {e}")
            return 0
        
        # Parse and sort operations by timestamp
        operations = []
        for msg in messages:
            body = msg.get('body', '')
            op_dict = self._decode_operation(body)
            if op_dict:
                operations.append(op_dict)
        
        # Sort by timestamp
        operations.sort(key=lambda op: op['timestamp'])
        
        # Apply operations
        processed_count = 0
        for op in operations:
            try:
                if self._apply_operation(op, queue_id):
                    processed_count += 1
            except Exception as e:
                print(f"Warning: Failed to apply operation {op.get('operation_id')}: {e}")
        
        # Update last sync time
        if messages:
            latest_timestamp = max(msg['timestamp'] for msg in messages)
            self.last_sync_times[queue_id] = latest_timestamp
        else:
            self.last_sync_times[queue_id] = datetime.now()
        
        return processed_count

    def _apply_operation(
        self,
        operation: Dict[str, Any],
        queue_id: str
    ) -> bool:
        """
        Apply operation from email to local queue.
        
        Args:
            operation: Operation dictionary
            queue_id: Queue identifier
            
        Returns:
            True if operation was applied, False if skipped (duplicate)
        """
        op_id = operation.get('operation_id')
        op_type = operation.get('operation')
        op_data = operation.get('data')
        
        # Get or create sync state
        if queue_id not in self._sync_states:
            thread_id = self._get_or_create_thread_id(queue_id)
            self._sync_states[queue_id] = SyncState(
                queue_id=queue_id,
                thread_id=thread_id,
                last_sync_time=datetime.now()
            )
        
        sync_state = self._sync_states[queue_id]
        
        # Check if operation already processed (idempotency)
        if op_id in sync_state.operation_ids_seen:
            return False
        
        # Apply operation based on type
        try:
            if op_type == 'put':
                # Add item to local queue if not already present
                self.storage_service.put(queue_id, op_data)
            
            elif op_type == 'get':
                # Remove item from local queue (if present)
                # Note: This is best-effort since we don't know exact item
                if self.storage_service.size(queue_id) > 0:
                    self.storage_service.get(queue_id, blocking=False)
            
            elif op_type == 'clear':
                # Clear local queue
                self.storage_service.clear(queue_id)
            
            elif op_type == 'delete':
                # Delete local queue
                self.storage_service.delete(queue_id)
            
            elif op_type == 'create':
                # Create local queue if doesn't exist
                if not self.storage_service.exists(queue_id):
                    self.storage_service.create_queue(queue_id)
            
            # Mark operation as seen
            sync_state.operation_ids_seen.add(op_id)
            
            return True
            
        except Exception as e:
            print(f"Warning: Failed to apply operation {op_id}: {e}")
            return False

    def peek(self, queue_id: str, index: int = 0) -> Optional[Any]:
        """
        Peek at an item in the queue without removing it.
        
        Args:
            queue_id: Queue identifier
            index: Index to peek at (0=front, -1=back, default=0)
            
        Returns:
            Python object at the specified index, or None if queue is empty
            
        Raises:
            IndexError: If index is out of range
            RuntimeError: If service is closed
        """
        if self._closed:
            raise RuntimeError("Service is closed")
        
        # Peek from local storage (no email sent)
        return self.storage_service.peek(queue_id, index=index)
    
    def size(self, queue_id: str) -> int:
        """
        Get the number of items in the queue.
        
        Args:
            queue_id: Queue identifier
            
        Returns:
            Number of items in the queue
        """
        return self.storage_service.size(queue_id)
    
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
            stats = {
                'queue_id': queue_id,
                'local_size': self.storage_service.size(queue_id),
                'exists': self.exists(queue_id)
            }
            
            # Add last sync time if available
            if queue_id in self.last_sync_times:
                last_sync = self.last_sync_times[queue_id]
                stats['last_sync_time'] = last_sync.isoformat()
                stats['time_since_last_sync'] = (datetime.now() - last_sync).total_seconds()
            
            # Add email thread message count if available
            if queue_id in self._thread_id_cache:
                try:
                    thread_id = self._thread_id_cache[queue_id]
                    thread = self.email_client.get_thread(thread_id)
                    stats['email_message_count'] = len(thread.get('messages', []))
                except:
                    stats['email_message_count'] = None
            
            return stats
        else:
            # Stats for all queues
            queues = self.list_queues()
            stats = {
                'total_queues': len(queues),
                'email_address': self.email_address,
                'sync_interval': self.sync_interval,
                'sync_on_read': self.sync_on_read,
                'queues': {}
            }
            
            for qid in queues:
                stats['queues'][qid] = self.get_stats(qid)
            
            return stats

    def _should_sync(self, queue_id: str) -> bool:
        """
        Check if queue should be synchronized based on interval.
        
        Args:
            queue_id: Queue identifier
            
        Returns:
            True if sync should occur
        """
        # If no sync interval, don't auto-sync
        if self.sync_interval is None:
            return False
        
        # Check time since last sync
        if queue_id not in self.last_sync_times:
            return True
        
        last_sync = self.last_sync_times[queue_id]
        elapsed = (datetime.now() - last_sync).total_seconds()
        
        return elapsed >= self.sync_interval
    
    def _auto_sync_if_needed(self, queue_id: str):
        """
        Automatically sync queue if interval has elapsed.
        
        Args:
            queue_id: Queue identifier
        """
        if self._should_sync(queue_id):
            try:
                self._sync_queue(queue_id)
            except Exception as e:
                print(f"Warning: Auto-sync failed for queue {queue_id}: {e}")
    
    def sync(self, queue_id: Optional[str] = None) -> int:
        """
        Manually synchronize queue(s) with email.
        
        Args:
            queue_id: Optional queue ID to sync. If None, syncs all queues.
            
        Returns:
            Number of operations processed
        """
        if queue_id:
            return self._sync_queue(queue_id)
        else:
            # Sync all queues
            total_processed = 0
            for qid in self.list_queues():
                try:
                    total_processed += self._sync_queue(qid)
                except Exception as e:
                    print(f"Warning: Sync failed for queue {qid}: {e}")
            return total_processed

    def ping(self) -> bool:
        """
        Check if service is responsive.
        
        Returns:
            True if service is responsive, False otherwise
        """
        if self._closed:
            return False
        
        try:
            # Check email client connectivity
            if not self.email_client.ping():
                return False
            
            # Check local storage availability
            if not self.storage_service.ping():
                return False
            
            return True
        except:
            return False
    
    def close(self):
        """
        Close the service and clean up resources.
        """
        if not self._closed:
            self._closed = True
            
            # Perform final synchronization for all queues
            try:
                self.sync()
            except Exception as e:
                print(f"Warning: Final sync failed during close: {e}")
            
            # Close email client
            try:
                self.email_client.close()
            except Exception as e:
                print(f"Warning: Failed to close email client: {e}")
            
            # Close storage service
            try:
                self.storage_service.close()
            except Exception as e:
                print(f"Warning: Failed to close storage service: {e}")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    def __repr__(self) -> str:
        """String representation of the service."""
        try:
            num_queues = len(self.list_queues())
        except:
            num_queues = "unknown"
        
        return (
            f"EmailQueueService("
            f"email_address='{self.email_address}', "
            f"queues={num_queues}, "
            f"sync_interval={self.sync_interval}, "
            f"closed={self._closed})"
        )
