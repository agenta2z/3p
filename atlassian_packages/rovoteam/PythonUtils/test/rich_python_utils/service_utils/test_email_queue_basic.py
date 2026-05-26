"""
Basic tests for Email Queue Service

Tests the core functionality without requiring actual Gmail credentials.
Uses mock email client for testing.
"""

import pytest
from datetime import datetime
from typing import Any, Optional, List, Dict

from python_utils.service_utils.email_utils import (
    EmailClientBase,
    QueueOperation,
    SyncState,
    extract_queue_id_from_subject,
    format_queue_subject
)
from python_utils.service_utils.queue_service.storage_based_queue_service import (
    StorageBasedQueueService
)
from python_utils.service_utils.queue_service.email_queue_service import (
    EmailQueueService
)


class MockEmailClient(EmailClientBase):
    """Mock email client for testing."""
    
    def __init__(self):
        self.threads = {}
        self.messages = {}
        self.authenticated = False
        self.thread_counter = 0
        self.message_counter = 0
    
    def authenticate(self) -> bool:
        self.authenticated = True
        return True
    
    def list_threads(
        self,
        query: Optional[str] = None,
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        results = []
        for thread_id, thread in self.threads.items():
            if query is None or query in thread['subject']:
                results.append({
                    'id': thread_id,
                    'subject': thread['subject'],
                    'timestamp': thread['timestamp']
                })
        return results[:max_results]
    
    def get_thread(self, thread_id: str) -> Dict[str, Any]:
        return self.threads.get(thread_id, {})
    
    def search_threads_by_subject(
        self,
        subject_pattern: str
    ) -> List[Dict[str, Any]]:
        results = []
        for thread_id, thread in self.threads.items():
            if subject_pattern in thread['subject']:
                results.append({
                    'id': thread_id,
                    'subject': thread['subject'],
                    'timestamp': thread['timestamp']
                })
        return results
    
    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        thread_id: Optional[str] = None
    ) -> Dict[str, Any]:
        self.message_counter += 1
        message_id = f'msg_{self.message_counter}'
        
        if thread_id is None:
            # Create new thread
            self.thread_counter += 1
            thread_id = f'thread_{self.thread_counter}'
            self.threads[thread_id] = {
                'id': thread_id,
                'subject': subject,
                'messages': [],
                'timestamp': datetime.now()
            }
        
        # Add message to thread
        message = {
            'id': message_id,
            'timestamp': datetime.now(),
            'body': body,
            'from': to,
            'to': to,
            'subject': subject
        }
        self.threads[thread_id]['messages'].append(message)
        self.messages[message_id] = message
        
        return {
            'message_id': message_id,
            'thread_id': thread_id
        }
    
    def get_messages_since(
        self,
        thread_id: str,
        since_timestamp: datetime
    ) -> List[Dict[str, Any]]:
        thread = self.threads.get(thread_id, {})
        messages = thread.get('messages', [])
        return [
            msg for msg in messages
            if msg['timestamp'] > since_timestamp
        ]
    
    def ping(self) -> bool:
        return self.authenticated
    
    def close(self):
        pass
    
    def __enter__(self):
        self.authenticate()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def test_queue_operation_serialization():
    """Test QueueOperation JSON serialization."""
    op = QueueOperation(
        operation='put',
        queue_id='test_queue',
        operation_id='op_123',
        timestamp=datetime(2025, 11, 27, 10, 30, 0),
        data={'task': 'test'}
    )
    
    # Serialize
    json_str = op.to_json()
    assert 'put' in json_str
    assert 'test_queue' in json_str
    assert 'op_123' in json_str
    
    # Deserialize
    op2 = QueueOperation.from_json(json_str)
    assert op2.operation == 'put'
    assert op2.queue_id == 'test_queue'
    assert op2.operation_id == 'op_123'
    assert op2.data == {'task': 'test'}


def test_sync_state_serialization():
    """Test SyncState serialization."""
    state = SyncState(
        queue_id='test_queue',
        thread_id='thread_123',
        last_sync_time=datetime(2025, 11, 27, 10, 30, 0),
        operation_ids_seen={'op_1', 'op_2'}
    )
    
    # Serialize
    data = state.to_dict()
    assert data['queue_id'] == 'test_queue'
    assert data['thread_id'] == 'thread_123'
    assert set(data['operation_ids_seen']) == {'op_1', 'op_2'}
    
    # Deserialize
    state2 = SyncState.from_dict(data)
    assert state2.queue_id == 'test_queue'
    assert state2.thread_id == 'thread_123'
    assert state2.operation_ids_seen == {'op_1', 'op_2'}


def test_queue_subject_formatting():
    """Test queue subject formatting and extraction."""
    queue_id = 'my_test_queue'
    
    # Format
    subject = format_queue_subject(queue_id)
    assert subject == 'EmailQueue - my_test_queue'
    
    # Extract
    extracted = extract_queue_id_from_subject(subject)
    assert extracted == queue_id
    
    # Extract with extra spaces
    extracted = extract_queue_id_from_subject('EmailQueue  -  my_test_queue  ')
    assert extracted == 'my_test_queue'
    
    # Non-matching subject
    extracted = extract_queue_id_from_subject('Regular Email Subject')
    assert extracted is None


def test_email_queue_service_basic_operations(tmp_path):
    """Test basic email queue service operations."""
    # Create mock email client
    email_client = MockEmailClient()
    email_client.authenticate()
    
    # Create storage service
    storage_service = StorageBasedQueueService(
        root_path=str(tmp_path / 'queues')
    )
    
    # Create email queue service
    service = EmailQueueService(
        email_client=email_client,
        storage_service=storage_service,
        email_address='test@example.com',
        sync_interval=None  # Manual sync only
    )
    
    try:
        # Create queue
        queue_id = 'test_queue'
        assert service.create_queue(queue_id) == True
        assert service.exists(queue_id) == True
        
        # Put items
        service.put(queue_id, {'task': 'item1'})
        service.put(queue_id, {'task': 'item2'})
        service.put(queue_id, {'task': 'item3'})
        
        # Check size
        assert service.size(queue_id) == 3
        
        # Peek
        first = service.peek(queue_id, index=0)
        assert first['task'] == 'item1'
        assert service.size(queue_id) == 3  # Peek doesn't remove
        
        # Get items
        item1 = service.get(queue_id, blocking=False)
        assert item1['task'] == 'item1'
        assert service.size(queue_id) == 2
        
        item2 = service.get(queue_id, blocking=False)
        assert item2['task'] == 'item2'
        assert service.size(queue_id) == 1
        
        # Clear queue
        count = service.clear(queue_id)
        assert count == 1
        assert service.size(queue_id) == 0
        
        # List queues
        queues = service.list_queues()
        assert queue_id in queues
        
        # Get stats
        stats = service.get_stats(queue_id)
        assert stats['queue_id'] == queue_id
        assert stats['local_size'] == 0
        assert stats['exists'] == True
        
        # Delete queue
        assert service.delete(queue_id) == True
        # Note: Queue still "exists" because email thread persists
        # This is correct behavior - email threads aren't deleted, just marked
        # Local storage is cleared though
        assert service.size(queue_id) == 0
        
    finally:
        service.close()


def test_email_queue_service_context_manager(tmp_path):
    """Test email queue service as context manager."""
    email_client = MockEmailClient()
    storage_service = StorageBasedQueueService(root_path=str(tmp_path / 'queues'))
    
    with EmailQueueService(
        email_client=email_client,
        storage_service=storage_service,
        email_address='test@example.com'
    ) as service:
        service.create_queue('test_queue')
        service.put('test_queue', {'data': 'test'})
        assert service.size('test_queue') == 1
    
    # Service should be closed after context exit
    assert service._closed == True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
