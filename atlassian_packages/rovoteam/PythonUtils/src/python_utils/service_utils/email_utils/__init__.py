"""
Email Utils Module

Provides email client abstraction and implementations for various email providers.
Enables programmatic email operations for queue services and other applications.

Key Components:
- EmailClientBase: Abstract base class for email clients
- GmailClient: Gmail-specific implementation (requires google-auth packages)
- Custom exceptions for email operations
- Utility functions for email parsing and formatting
- Data models for queue operations
"""

from .email_client_base import EmailClientBase
from .exceptions import (
    EmailAuthenticationError,
    EmailRateLimitError,
    EmailNetworkError,
    EmailAPIError
)
from .models import QueueOperation, SyncState
from .utils import (
    parse_email_body,
    extract_thread_subject,
    extract_queue_id_from_subject,
    format_queue_subject
)

# GmailClient is optional - requires google-auth packages
try:
    from .gmail_client import GmailClient
    _gmail_available = True
except ImportError:
    _gmail_available = False
    GmailClient = None

__all__ = [
    'EmailClientBase',
    'EmailAuthenticationError',
    'EmailRateLimitError',
    'EmailNetworkError',
    'EmailAPIError',
    'QueueOperation',
    'SyncState',
    'parse_email_body',
    'extract_thread_subject',
    'extract_queue_id_from_subject',
    'format_queue_subject',
]

if _gmail_available:
    __all__.append('GmailClient')
