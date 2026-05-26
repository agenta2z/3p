# Email Queue Service Examples

Examples demonstrating the Email Queue Service functionality.

## Setup

### 1. Google Cloud Console Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Gmail API:
   - Go to "APIs & Services" > "Library"
   - Search for "Gmail API"
   - Click "Enable"

### 2. Create OAuth2 Credentials

1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "OAuth client ID"
3. Select "Desktop app" as the application type
4. Name it (e.g., "Email Queue Service")
5. Click "Create"
6. Download the credentials JSON file
7. Save it as `credentials.json` in this directory

### 3. Install Dependencies

```bash
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

### 4. First Run

The first time you run any example, it will:
1. Open your browser for authentication
2. Ask you to grant permissions to the app
3. Save the token to `token.pickle` for future use

## Examples

### Basic Usage (`example_basic_usage.py`)

Demonstrates basic queue operations:
- Creating a queue
- Putting items
- Getting items
- Peeking at items
- Getting statistics

```bash
python example_basic_usage.py
```

### Distributed Consumers (`example_distributed_consumers.py`)

Demonstrates distributed queue consumption:
- Multiple processes sharing the same queue
- Producer/consumer pattern
- Synchronization across processes

Run in multiple terminals:

```bash
# Terminal 1 - Producer
python example_distributed_consumers.py
# Choose option 1

# Terminal 2 - Consumer
python example_distributed_consumers.py
# Choose option 2

# Terminal 3 - Another Consumer
python example_distributed_consumers.py
# Choose option 2
```

## How It Works

### Email Thread as Queue

Each queue is represented by an email thread with subject:
```
EmailQueue - {queue_id}
```

### Operation Logging

Every queue operation (put, get, clear, etc.) is logged as an email message containing JSON:

```json
{
  "operation": "put",
  "queue_id": "my_queue",
  "operation_id": "op_1234567890_001",
  "timestamp": "2025-11-27T10:30:00.123456",
  "data": {
    "task": "process_data",
    "priority": 1
  }
}
```

### Local Cache + Email Sync

- Operations are performed on local storage immediately (fast)
- Operations are logged to email asynchronously (persistent)
- Synchronization brings email operations into local storage
- Multiple machines can share the same queue through email

### Synchronization

Synchronization can happen:
1. **Automatically** - Based on `sync_interval` (e.g., every 5 minutes)
2. **On Read** - Before each `get()` if `sync_on_read=True`
3. **Manually** - By calling `service.sync(queue_id)`

## Configuration Options

```python
EmailQueueService(
    email_client=gmail_client,
    storage_service=storage_service,
    email_address='your-email@gmail.com',
    sync_interval=300.0,  # Seconds between auto-sync (None = manual only)
    sync_on_read=False    # Whether to sync before each get()
)
```

## Troubleshooting

### "credentials.json not found"
- Download OAuth2 credentials from Google Cloud Console
- Save as `credentials.json` in the examples directory

### "Authentication failed"
- Delete `token.pickle` and re-authenticate
- Check that Gmail API is enabled in your project
- Verify credentials are for "Desktop app" type

### "Rate limit exceeded"
- Gmail API has rate limits (250 requests/minute)
- Increase `sync_interval` to reduce API calls
- Use `sync_on_read=False` for better performance

### Items not appearing in other processes
- Call `service.sync(queue_id)` to fetch latest from email
- Increase `sync_interval` for more frequent auto-sync
- Enable `sync_on_read=True` for immediate consistency

## Best Practices

1. **Use appropriate sync intervals**
   - High frequency (10-30s) for real-time coordination
   - Low frequency (5-10min) for background jobs
   - Manual sync for batch processing

2. **Handle email failures gracefully**
   - Local operations succeed even if email fails
   - Email operations are logged but don't block
   - Sync will catch up when email is available

3. **Use unique storage paths per process**
   - Each process should have its own local storage
   - This prevents file locking issues
   - Email provides the shared state

4. **Monitor queue statistics**
   - Use `get_stats()` to monitor queue health
   - Check `time_since_last_sync` for sync issues
   - Compare `local_size` vs `email_message_count`

## Security Notes

- OAuth2 tokens are stored in `token.pickle`
- Keep credentials.json secure (don't commit to git)
- Queue data is visible in your email
- Consider encrypting sensitive data before queuing
- Use a dedicated email account for queues
