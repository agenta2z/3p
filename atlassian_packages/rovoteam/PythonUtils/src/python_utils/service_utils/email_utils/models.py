"""
Email Queue Data Models

Data classes for queue operations and synchronization state.
"""

import json
from typing import Any, Optional, Set
from datetime import datetime

from attr import attrs, attrib, Factory


@attrs(slots=False)
class QueueOperation:
    """
    Represents a queue operation for email encoding.
    
    Attributes:
        operation: Operation type ('put', 'get', 'clear', 'create', 'delete')
        queue_id: Queue identifier
        operation_id: Unique operation identifier
        timestamp: Operation timestamp
        data: Optional operation data
    """
    operation: str = attrib()
    queue_id: str = attrib()
    operation_id: str = attrib()
    timestamp: datetime = attrib()
    data: Optional[Any] = attrib(default=None)
    
    def to_json(self) -> str:
        """
        Serialize to JSON string.
        
        Returns:
            JSON string representation
        """
        obj = {
            'operation': self.operation,
            'queue_id': self.queue_id,
            'operation_id': self.operation_id,
            'timestamp': self.timestamp.isoformat(),
            'data': self.data
        }
        return json.dumps(obj, indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'QueueOperation':
        """
        Deserialize from JSON string.
        
        Args:
            json_str: JSON string
            
        Returns:
            QueueOperation instance
        """
        obj = json.loads(json_str)
        
        # Parse timestamp
        timestamp = datetime.fromisoformat(obj['timestamp'])
        
        return cls(
            operation=obj['operation'],
            queue_id=obj['queue_id'],
            operation_id=obj['operation_id'],
            timestamp=timestamp,
            data=obj.get('data')
        )


@attrs(slots=False)
class SyncState:
    """
    Tracks synchronization state for a queue.
    
    Attributes:
        queue_id: Queue identifier
        thread_id: Email thread identifier
        last_sync_time: Last synchronization timestamp
        last_message_id: Last processed message ID
        operation_ids_seen: Set of operation IDs already processed
    """
    queue_id: str = attrib()
    thread_id: str = attrib()
    last_sync_time: datetime = attrib()
    last_message_id: Optional[str] = attrib(default=None)
    operation_ids_seen: Set[str] = attrib(factory=set)
    
    def to_dict(self) -> dict:
        """
        Serialize to dictionary for persistence.
        
        Returns:
            Dictionary representation
        """
        return {
            'queue_id': self.queue_id,
            'thread_id': self.thread_id,
            'last_sync_time': self.last_sync_time.isoformat(),
            'last_message_id': self.last_message_id,
            'operation_ids_seen': list(self.operation_ids_seen)
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'SyncState':
        """
        Deserialize from dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            SyncState instance
        """
        return cls(
            queue_id=data['queue_id'],
            thread_id=data['thread_id'],
            last_sync_time=datetime.fromisoformat(data['last_sync_time']),
            last_message_id=data.get('last_message_id'),
            operation_ids_seen=set(data.get('operation_ids_seen', []))
        )
