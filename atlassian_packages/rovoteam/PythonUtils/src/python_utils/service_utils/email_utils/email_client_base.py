"""
Email Client Base Class

Abstract base class defining the interface for email clients.
Allows different providers (Gmail, Outlook, etc.) to be used interchangeably.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional, List, Dict
from datetime import datetime

from attr import attrs


@attrs(slots=False)
class EmailClientBase(ABC):
    """
    Abstract base class for email clients.
    
    Defines the standard interface that all email client implementations
    must implement. This allows different providers (Gmail, Outlook, etc.)
    to be used interchangeably with the Email Queue Service.
    
    All methods should be implemented by subclasses to provide
    provider-specific functionality.
    """
    
    @abstractmethod
    def authenticate(self) -> bool:
        """
        Authenticate with the email service.
        
        Returns:
            True if authentication successful
            
        Raises:
            EmailAuthenticationError: If authentication fails
        """
        pass
    
    @abstractmethod
    def list_threads(
        self,
        query: Optional[str] = None,
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List email threads matching query.
        
        Args:
            query: Optional search query
            max_results: Maximum number of threads to return
            
        Returns:
            List of thread dictionaries with 'id', 'subject', 'timestamp'
        """
        pass
    
    @abstractmethod
    def get_thread(self, thread_id: str) -> Dict[str, Any]:
        """
        Get complete email thread with all messages.
        
        Args:
            thread_id: Thread identifier
            
        Returns:
            Thread dictionary with 'id', 'subject', 'messages' list
            Each message has 'id', 'timestamp', 'body', 'from', 'to'
        """
        pass
    
    @abstractmethod
    def search_threads_by_subject(
        self,
        subject_pattern: str
    ) -> List[Dict[str, Any]]:
        """
        Search for threads by subject pattern.
        
        Args:
            subject_pattern: Subject pattern to match
            
        Returns:
            List of matching thread dictionaries with 'id', 'subject', 'timestamp'
        """
        pass
    
    @abstractmethod
    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        thread_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send new email or reply to existing thread.
        
        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body (plain text)
            thread_id: Optional thread ID to reply to
            
        Returns:
            Dictionary with 'message_id', 'thread_id'
        """
        pass
    
    @abstractmethod
    def get_messages_since(
        self,
        thread_id: str,
        since_timestamp: datetime
    ) -> List[Dict[str, Any]]:
        """
        Get messages in thread since timestamp.
        
        Args:
            thread_id: Thread identifier
            since_timestamp: Only return messages after this time
            
        Returns:
            List of message dictionaries with 'id', 'timestamp', 'body', 'from', 'to'
        """
        pass
    
    @abstractmethod
    def ping(self) -> bool:
        """
        Check if email service is responsive.
        
        Returns:
            True if service is responsive
        """
        pass
    
    @abstractmethod
    def close(self):
        """Close the email client connection."""
        pass
    
    @abstractmethod
    def __enter__(self):
        """Context manager entry."""
        pass
    
    @abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        pass
