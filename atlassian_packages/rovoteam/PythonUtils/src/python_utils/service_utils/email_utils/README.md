# Email Utils Module

Email client abstraction and implementations for various email providers.

## Overview

The Email Utils module provides a unified interface for email operations across different providers (Gmail, Outlook, etc.). It's designed to support the Email Queue Service but can be used independently for any email automation needs.

## Components

### EmailClientBase

Abstract base class defining the standard interface for email clients.

**Key Methods:**
- `authenticate()` - Authenticate with email service
- `list_threads()` - List email threads
- `get_thread()` - Get complete thread with messages
- `search_threads_by_subject()` - Search by subject pattern
- `send_email()` - Send new email or reply to thread
- `get_messages_since()` - Get messages after timestamp
- `ping()` - Check service connectivity
- `close()` - Clean up resources

### GmailClient

Gmail-specific implementation using Gmail API.

**Features:**
- OAuth2 authentication with token refresh
- Full Gmail API integration
- Exponential backoff for rate limits
- Error handling with custom exceptions
- Context manager support

**Setup:**

1. Create Google Cloud project
2. Enable Gmail API
3. Create OAuth2 credentials (Desktop app)
4. Download credentials.json

**Usage:**

```python
from python_utils.service_utils.email_utils import GmailClient

# Create client
client = GmailClient(
    credentials_path='credentials.json',
    token_path='token.pickle'
)

# Authenticate (opens browser first time)
client.authenticate()

# List threads
threads = client.list_threads(query='subject:test', max_results=10)

# Get thread details
thread = client.get_thread(thread_id='abc123')

# Send email
result = client.send_email(
    to='recipient@example.com',
    subject='Test Email',
    body='Hello from GmailClient!'
)

# Reply to thread
result = client.send_email(
    to='recipient@example.com',
    subject='Re: Test Email',
    body='This is a reply',
    thread_id='abc123'
)

# Search by subject
threads = client.search_threads_by_subject('EmailQueue')

# Get new messages
messages = client.get_messages_since(
    thread_id='abc123',
    since_timestamp=datetime(2025, 11, 27)
)

# Check connectivity
if client.ping():
    print("Gmail is responsive")

# Clean up
client.close()
```

**Context Manager:**

```python
with GmailClient(credentials_path='credentials.json') as client:
    threads = client.list_threads()
    # Client automatically closed on exit
```

### Custom Exceptions

- `EmailAuthenticationError` - Authentication failures
- `EmailRateLimitError` - Rate limit exceeded
- `EmailNetworkError` - Network/connectivity issues
- `EmailAPIError` - API errors

### Utility Functions

**parse_email_body(message)**
Extract plain text body from message dictionary.

**extract_thread_subject(thread)**
Extract subject line from thread dictionary.

**extract_queue_id_from_subject(subject)**
Parse queue ID from 'EmailQueue - {queue_id}' format.

**format_queue_subject(queue_id)**
Format subject line for queue: 'EmailQueue - {queue_id}'.

### Data Models

**QueueOperation**
Represents a queue operation for email encoding.

```python
from python_utils.service_utils.email_utils import QueueOperation
from datetime import datetime

op = QueueOperation(
    operation='put',
    queue_id='my_queue',
    operation_id='op_123',
    timestamp=datetime.now(),
    data={'task': 'process'}
)

# Serialize to JSON
json_str = op.to_json()

# Deserialize from JSON
op2 = QueueOperation.from_json(json_str)
```

**SyncState**
Tracks synchronization state for a queue.

```python
from python_utils.service_utils.email_utils import SyncState
from datetime import datetime

state = SyncState(
    queue_id='my_queue',
    thread_id='thread_123',
    last_sync_time=datetime.now(),
    operation_ids_seen={'op_1', 'op_2'}
)

# Serialize
data = state.to_dict()

# Deserialize
state2 = SyncState.from_dict(data)
```

## Gmail API Setup

### 1. Google Cloud Console

1. Go to https://console.cloud.google.com/
2. Create a new project or select existing
3. Enable Gmail API:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Gmail API"
   - Click "Enable"

### 2. OAuth2 Credentials

1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "OAuth client ID"
3. Select "Desktop app" as application type
4. Name it (e.g., "Email Queue Service")
5. Click "Create"
6. Download credentials JSON file
7. Save as `credentials.json`

### 3. First Authentication

First run will:
1. Open browser for authentication
2. Ask for permissions
3. Save token to `token.pickle`
4. Subsequent runs use saved token

### 4. Token Refresh

Tokens are automatically refreshed when expired. If refresh fails, delete `token.pickle` and re-authenticate.

## Dependencies

```bash
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

## Error Handling

### Rate Limits

Gmail API has rate limits (250 requests/minute). The client automatically:
- Retries with exponential backoff
- Caps retry delay at 60 seconds
- Raises `EmailRateLimitError` after max retries

### Network Errors

Transient network errors are retried automatically. Persistent errors raise `EmailNetworkError`.

### Authentication Errors

Authentication failures raise `EmailAuthenticationError` with diagnostic information.

## Best Practices

1. **Use context managers** for automatic cleanup
2. **Handle exceptions** appropriately for your use case
3. **Respect rate limits** by batching operations
4. **Secure credentials** - don't commit to version control
5. **Use dedicated email account** for automation
6. **Monitor API usage** in Google Cloud Console

## Future Providers

The module is designed to support additional providers:

- **OutlookClient** - Microsoft Outlook/Office 365
- **IMAPClient** - Generic IMAP support
- **SendGridClient** - SendGrid API

To add a provider, implement `EmailClientBase` interface.

## Security Considerations

- OAuth2 tokens stored in `token.pickle`
- Keep `credentials.json` secure
- Use environment variables for paths in production
- Consider encrypting sensitive email content
- Limit API scopes to minimum required
- Monitor for unauthorized access

## Troubleshooting

### "credentials.json not found"
Download OAuth2 credentials from Google Cloud Console.

### "Authentication failed"
- Delete `token.pickle` and re-authenticate
- Verify Gmail API is enabled
- Check credentials are for "Desktop app"

### "Rate limit exceeded"
- Reduce request frequency
- Implement request batching
- Use exponential backoff (built-in)

### "Invalid grant" error
- Token may be revoked
- Delete `token.pickle` and re-authenticate
- Check OAuth consent screen configuration

## Examples

See `examples/python_utils/service_utils/email_queue/` for complete examples.
