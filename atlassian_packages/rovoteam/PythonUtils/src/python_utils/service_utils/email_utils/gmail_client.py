"""
Gmail Client Implementation

Gmail-specific implementation of EmailClientBase using Gmail API.
Provides OAuth2 authentication and full Gmail API integration.

Requirements:
    - google-auth
    - google-auth-oauthlib
    - google-auth-httplib2
    - google-api-python-client

Setup:
    1. Create a project in Google Cloud Console
    2. Enable Gmail API
    3. Create OAuth2 credentials (Desktop app)
    4. Download credentials.json
    5. First run will open browser for authentication
    6. Token will be saved for future use
"""

import os
import pickle
import base64
import time
from email.mime.text import MIMEText
from typing import Any, Optional, List, Dict
from datetime import datetime
from pathlib import Path

from attr import attrs, attrib

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    raise ImportError(
        "Gmail client requires google-auth, google-auth-oauthlib, and "
        "google-api-python-client. Install with: "
        "pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client"
    )

from .email_client_base import EmailClientBase
from .exceptions import (
    EmailAuthenticationError,
    EmailRateLimitError,
    EmailNetworkError,
    EmailAPIError
)


@attrs(slots=False)
class GmailClient(EmailClientBase):
    """
    Gmail API client for email operations.
    
    Attributes:
        credentials_path: Path to OAuth2 credentials JSON file
        token_path: Path to store OAuth2 token
        scopes: Gmail API scopes required
        service: Gmail API service instance
    """
    credentials_path: str
    token_path: str = attrib(default='token.pickle')
    scopes: List[str] = attrib(factory=lambda: ['https://www.googleapis.com/auth/gmail.modify'])
    service: Any = attrib(init=False, default=None)
    _authenticated: bool = attrib(init=False, default=False)
    
    def authenticate(self) -> bool:
        """
        Authenticate with Gmail API using OAuth2.
        
        Returns:
            True if authentication successful
            
        Raises:
            EmailAuthenticationError: If authentication fails
        """
        try:
            creds = None
            
            # Load existing token if available
            if os.path.exists(self.token_path):
                with open(self.token_path, 'rb') as token:
                    creds = pickle.load(token)
            
            # If no valid credentials, authenticate
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    # Refresh expired token
                    creds.refresh(Request())
                else:
                    # New authentication flow
                    if not os.path.exists(self.credentials_path):
                        raise EmailAuthenticationError(
                            f"Credentials file not found: {self.credentials_path}"
                        )
                    
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_path, self.scopes
                    )
                    creds = flow.run_local_server(port=0)
                
                # Save credentials for future use
                with open(self.token_path, 'wb') as token:
                    pickle.dump(creds, token)
            
            # Build Gmail service
            self.service = build('gmail', 'v1', credentials=creds)
            self._authenticated = True
            
            return True
            
        except Exception as e:
            raise EmailAuthenticationError(f"Gmail authentication failed: {str(e)}")
    
    def _ensure_authenticated(self):
        """Ensure client is authenticated before operations."""
        if not self._authenticated or self.service is None:
            self.authenticate()
    
    def _handle_api_error(self, error: HttpError, operation: str):
        """
        Handle Gmail API errors with appropriate exceptions.
        
        Args:
            error: HttpError from Gmail API
            operation: Description of operation that failed
        """
        if error.resp.status == 401:
            raise EmailAuthenticationError(f"Authentication failed during {operation}")
        elif error.resp.status == 429:
            raise EmailRateLimitError(f"Rate limit exceeded during {operation}")
        elif error.resp.status >= 500:
            raise EmailNetworkError(f"Server error during {operation}: {str(error)}")
        else:
            raise EmailAPIError(f"API error during {operation}: {str(error)}")
    
    def _retry_with_backoff(self, func, max_retries: int = 3, initial_delay: float = 1.0):
        """
        Retry function with exponential backoff.
        
        Args:
            func: Function to retry
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay in seconds
            
        Returns:
            Result of function call
        """
        delay = initial_delay
        last_error = None
        
        for attempt in range(max_retries):
            try:
                return func()
            except (EmailRateLimitError, EmailNetworkError) as e:
                last_error = e
                if attempt < max_retries - 1:
                    time.sleep(delay)
                    delay = min(delay * 2, 60.0)  # Cap at 60 seconds
                else:
                    raise
            except Exception as e:
                # Don't retry other errors
                raise
        
        raise last_error

    def list_threads(
        self,
        query: Optional[str] = None,
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List email threads matching query.
        
        Args:
            query: Optional search query (Gmail search syntax)
            max_results: Maximum number of threads to return
            
        Returns:
            List of thread dictionaries with 'id', 'subject', 'timestamp'
        """
        self._ensure_authenticated()
        
        def _list():
            try:
                results = self.service.users().threads().list(
                    userId='me',
                    q=query,
                    maxResults=max_results
                ).execute()
                
                threads = results.get('threads', [])
                thread_list = []
                
                for thread in threads:
                    # Get thread details to extract subject and timestamp
                    thread_data = self.get_thread(thread['id'])
                    thread_list.append({
                        'id': thread['id'],
                        'subject': thread_data.get('subject', ''),
                        'timestamp': thread_data.get('timestamp')
                    })
                
                return thread_list
                
            except HttpError as e:
                self._handle_api_error(e, "list_threads")
        
        return self._retry_with_backoff(_list)
    
    def get_thread(self, thread_id: str) -> Dict[str, Any]:
        """
        Get complete email thread with all messages.
        
        Args:
            thread_id: Thread identifier
            
        Returns:
            Thread dictionary with 'id', 'subject', 'messages' list
        """
        self._ensure_authenticated()
        
        def _get():
            try:
                thread = self.service.users().threads().get(
                    userId='me',
                    id=thread_id,
                    format='full'
                ).execute()
                
                messages = []
                subject = ''
                
                for msg in thread.get('messages', []):
                    # Extract headers
                    headers = {h['name']: h['value'] for h in msg['payload'].get('headers', [])}
                    
                    # Get subject from first message
                    if not subject and 'Subject' in headers:
                        subject = headers['Subject']
                    
                    # Extract body
                    body = self._extract_body(msg['payload'])
                    
                    # Parse timestamp
                    timestamp = datetime.fromtimestamp(int(msg['internalDate']) / 1000)
                    
                    messages.append({
                        'id': msg['id'],
                        'timestamp': timestamp,
                        'body': body,
                        'from': headers.get('From', ''),
                        'to': headers.get('To', ''),
                        'subject': headers.get('Subject', '')
                    })
                
                # Sort messages by timestamp
                messages.sort(key=lambda m: m['timestamp'])
                
                return {
                    'id': thread_id,
                    'subject': subject,
                    'messages': messages,
                    'timestamp': messages[0]['timestamp'] if messages else None
                }
                
            except HttpError as e:
                self._handle_api_error(e, "get_thread")
        
        return self._retry_with_backoff(_get)
    
    def _extract_body(self, payload: Dict[str, Any]) -> str:
        """
        Extract plain text body from message payload.
        
        Args:
            payload: Message payload from Gmail API
            
        Returns:
            Plain text body
        """
        body = ''
        
        if 'body' in payload and 'data' in payload['body']:
            body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
        elif 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    if 'data' in part['body']:
                        body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                        break
                elif 'parts' in part:
                    # Recursive for nested parts
                    body = self._extract_body(part)
                    if body:
                        break
        
        return body
    
    def search_threads_by_subject(
        self,
        subject_pattern: str
    ) -> List[Dict[str, Any]]:
        """
        Search for threads by subject pattern.
        
        Args:
            subject_pattern: Subject pattern to match
            
        Returns:
            List of matching thread dictionaries
        """
        query = f'subject:"{subject_pattern}"'
        return self.list_threads(query=query)
    
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
        self._ensure_authenticated()
        
        def _send():
            try:
                message = self.create_message(to, subject, body, thread_id)
                
                sent_message = self.service.users().messages().send(
                    userId='me',
                    body=message
                ).execute()
                
                return {
                    'message_id': sent_message['id'],
                    'thread_id': sent_message['threadId']
                }
                
            except HttpError as e:
                self._handle_api_error(e, "send_email")
        
        return self._retry_with_backoff(_send)
    
    def create_message(
        self,
        to: str,
        subject: str,
        body: str,
        thread_id: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Create email message in Gmail API format.
        
        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body (plain text)
            thread_id: Optional thread ID for replies
            
        Returns:
            Message dictionary for Gmail API
        """
        message = MIMEText(body)
        message['to'] = to
        message['subject'] = subject
        
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        
        result = {'raw': raw_message}
        if thread_id:
            result['threadId'] = thread_id
        
        return result
    
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
            List of message dictionaries
        """
        thread = self.get_thread(thread_id)
        messages = thread.get('messages', [])
        
        # Filter messages after timestamp
        filtered = [
            msg for msg in messages
            if msg['timestamp'] > since_timestamp
        ]
        
        return filtered
    
    def ping(self) -> bool:
        """
        Check if Gmail API is responsive.
        
        Returns:
            True if service is responsive
        """
        try:
            self._ensure_authenticated()
            # Try to get user profile as a lightweight check
            self.service.users().getProfile(userId='me').execute()
            return True
        except:
            return False
    
    def close(self):
        """Close Gmail API connection."""
        # Gmail API doesn't require explicit connection closing
        self.service = None
        self._authenticated = False
    
    def __enter__(self):
        """Context manager entry."""
        self.authenticate()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
