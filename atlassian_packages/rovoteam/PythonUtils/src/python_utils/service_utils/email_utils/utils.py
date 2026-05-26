"""
Email Utility Functions

Helper functions for email parsing and formatting.
"""

import re
from typing import Dict, Any, Optional


def parse_email_body(message: Dict[str, Any]) -> str:
    """
    Extract plain text body from email message.
    
    Args:
        message: Message dictionary with 'body' field
        
    Returns:
        Plain text body content
    """
    return message.get('body', '')


def extract_thread_subject(thread: Dict[str, Any]) -> str:
    """
    Extract subject line from thread.
    
    Args:
        thread: Thread dictionary with 'subject' field
        
    Returns:
        Subject line
    """
    return thread.get('subject', '')


def extract_queue_id_from_subject(subject: str) -> Optional[str]:
    """
    Extract queue_id from 'EmailQueue - {queue_id}' format.
    
    Args:
        subject: Email subject line
        
    Returns:
        Queue ID if found, None otherwise
    """
    # Match pattern: "EmailQueue - {queue_id}"
    pattern = r'^EmailQueue\s*-\s*(.+)$'
    match = re.match(pattern, subject.strip())
    
    if match:
        return match.group(1).strip()
    
    return None


def format_queue_subject(queue_id: str) -> str:
    """
    Format subject line for queue: 'EmailQueue - {queue_id}'.
    
    Args:
        queue_id: Queue identifier
        
    Returns:
        Formatted subject line
    """
    return f'EmailQueue - {queue_id}'
