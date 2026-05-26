# ThreadQueueService - Examples and Quick Reference

## Overview

This directory contains comprehensive examples for the `ThreadQueueService` class, which provides a generic queue service built on Python's multiprocessing.Manager.

## Quick Start

```bash
# Run the simple usage example
python example_simple_usage.py
```

## Features

- **In-memory queue storage** - No external dependencies required
- **Thread-safe operations** - Uses multiprocessing.Manager for thread safety
- **Multiple named queues** - Create and manage multiple independent queues
- **Flexible operations** - Put/get any picklable Python object
- **Blocking and non-blocking** - Support for both blocking and non-blocking operations
- **Simple setup** - No external services required (unlike Redis)

## Important Limitations

- Queues are not persistent (lost when program exits)
- All processes must be on the same machine
- Limited to objects that can be pickled
- Performance may be lower than Redis for high throughput scenarios
- **Critical**: ThreadQueueService does NOT support true inter-process communication where producers and consumers run in separate processes. Each spawned process creates its own isolated Manager instance, so queues are NOT shared between processes. **For true inter-process communication (separate producer/consumer processes), use RedisQueueService instead.** ThreadQueueService works well for threading and single-process scenarios.

## Basic Usage

```python
from python_utils.service_utils.queue_service.thread_queue_service import ThreadQueueService

# Create service
service = ThreadQueueService()

# Put items
service.put('my_queue', {'data': 'value'})
service.put('my_queue', [1, 2, 3])

# Get items
item = service.get('my_queue', blocking=False)  # Non-blocking
item = service.get('my_queue', blocking=True, timeout=5.0)  # Blocking

# Check size
size = service.size('my_queue')

# Peek without removing
item = service.peek('my_queue', index=0)  # First item
item = service.peek('my_queue', index=-1)  # Last item

# Clean up
service.delete('my_queue')
service.close()
```

## Context Manager

```python
with ThreadQueueService() as service:
    service.put('queue', 'data')
    item = service.get('queue')
# Auto-closed
```

## Auto-Create Queue

```python
service = ThreadQueueService()

# Queue is automatically created on first put
service.put('auto_queue', 'data')  # Creates 'auto_queue' automatically

obj = service.get('auto_queue', blocking=False)
```

## Multiple Queues

```python
service = ThreadQueueService()

# Create multiple queues
service.put('queue_a', [1, 2, 3])
service.put('queue_b', {'key': 'value'})
service.put('queue_c', 'string data')

# List all queues
queues = service.list_queues()  # ['queue_a', 'queue_b', 'queue_c']

# Get stats
stats = service.get_stats()
print(stats)
```

## Threading Example (Recommended)

```python
import threading

service = ThreadQueueService()

def producer():
    for i in range(10):
        service.put('work', f'task_{i}')

def consumer():
    while True:
        task = service.get('work', blocking=True, timeout=2.0)
        if task is None:
            break
        print(f"Processing: {task}")

# Start threads
t1 = threading.Thread(target=producer)
t2 = threading.Thread(target=consumer)
t1.start()
t2.start()
t1.join()
t2.join()

service.close()
```

## API Reference

### ThreadQueueService

#### Constructor

```python
ThreadQueueService()
```

Creates a new queue service instance using multiprocessing.Manager.

**Parameters:**
- None

**Returns:**
- ThreadQueueService instance

#### Key Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `create_queue(queue_id)` | Create a new queue | `bool` - True if created |
| `put(queue_id, obj, timeout)` | Add item to queue | `bool` - True if successful |
| `get(queue_id, blocking, timeout)` | Get item from queue | `Optional[Any]` - Item or None |
| `peek(queue_id, index)` | View item without removing | `Optional[Any]` - Item or None |
| `size(queue_id)` | Get queue size | `int` - Number of items |
| `exists(queue_id)` | Check if queue exists | `bool` - True if exists |
| `delete(queue_id)` | Delete queue | `bool` - True if deleted |
| `clear(queue_id)` | Remove all items | `int` - Number removed |
| `list_queues()` | List all queue IDs | `List[str]` - Queue IDs |
| `get_stats(queue_id)` | Get statistics | `Dict[str, Any]` - Stats |
| `ping()` | Check if responsive | `bool` - True if responsive |
| `close()` | Close service | None |

### Method Details

##### put(queue_id: str, obj: Any, timeout: Optional[float] = None) -> bool

Put an object onto the queue.

**Parameters:**
- `queue_id` (str): Queue identifier
- `obj` (Any): Any picklable Python object
- `timeout` (Optional[float]): Not used (for API compatibility)

**Returns:**
- `bool`: True if successful

**Raises:**
- `RuntimeError`: If service is closed
- `Exception`: If object cannot be pickled

##### get(queue_id: str, blocking: bool = True, timeout: Optional[float] = None) -> Optional[Any]

Get an object from the queue.

**Parameters:**
- `queue_id` (str): Queue identifier
- `blocking` (bool): If True, block until item available or timeout
- `timeout` (Optional[float]): Timeout in seconds (None = wait forever)

**Returns:**
- `Optional[Any]`: Python object, or None if queue is empty (non-blocking) or timeout reached (blocking)

**Raises:**
- `RuntimeError`: If service is closed

##### peek(queue_id: str, index: int = -1) -> Optional[Any]

Peek at an item in the queue without removing it.

**Parameters:**
- `queue_id` (str): Queue identifier
- `index` (int): Index to peek at (0=front, -1=back, default=-1)

**Returns:**
- `Optional[Any]`: Python object at the specified index, or None if queue is empty

**Raises:**
- `IndexError`: If index is out of range

**Note:** This operation is not atomic and may be slow for large queues.

##### get_stats(queue_id: Optional[str] = None) -> Dict[str, Any]

Get statistics about queues.

**Parameters:**
- `queue_id` (Optional[str]): Optional queue ID to get stats for a specific queue. If None, returns stats for all queues.

**Returns:**
- `Dict[str, Any]`: Dictionary with queue statistics

## Comparison with RedisQueueService

| Feature | ThreadQueueService | RedisQueueService |
|---------|----------------------------|-------------------|
| External Dependencies | None | Redis server + redis-py |
| Setup Complexity | Simple (no setup) | Moderate (requires Redis) |
| Persistence | No (in-memory only) | Yes (Redis persistence) |
| Inter-Process Communication | No (threading only) | Yes (true inter-process) |
| Cross-Machine | No | Yes |
| Performance | Good | Excellent |
| Use Case | Single-process, threading, temporary queues | Distributed systems, persistent queues |

## When to Use

**Use ThreadQueueService for:**
- Thread-based concurrency within a single process
- No external dependencies required
- Temporary queues that don't need persistence
- Quick prototyping or testing
- Picklable Python objects

**Use RedisQueueService for:**
- True multi-process communication (separate processes)
- Persistent queues that survive restarts
- Cross-machine communication
- High throughput scenarios
- Advanced Redis features

## Troubleshooting

### Issue: "RuntimeError: Service is closed"

**Cause:** Trying to use the service after calling `close()`

**Solution:** Create a new service instance or don't close the service until you're done

### Issue: "TypeError: cannot pickle..."

**Cause:** Trying to put an object that cannot be pickled

**Solution:** Only put picklable objects (most built-in types work). Avoid file handles, sockets, lambda functions, etc.

### Issue: Processes hang or don't communicate

**Cause:** ThreadQueueService does not support inter-process communication

**Solution:** Use RedisQueueService for inter-process communication, or use threads instead of processes with ThreadQueueService

### Issue: Peek operation is slow

**Cause:** Peek temporarily removes and re-inserts all items

**Solution:** Use peek sparingly, especially on large queues. Consider using `get()` if you don't need to preserve the item.

## Best Practices

1. **Use context managers** for automatic cleanup:
   ```python
   with ThreadQueueService() as service:
       # Your code here
   # Service closed automatically
   ```

2. **Close services** when done to free resources:
   ```python
   service = ThreadQueueService()
   try:
       # Your code
   finally:
       service.close()
   ```

3. **Use meaningful queue IDs** to avoid confusion:
   ```python
   service.put('user_tasks', task)
   service.put('email_queue', email)
   ```

4. **Handle timeouts** in blocking operations:
   ```python
   obj = service.get('queue', blocking=True, timeout=5.0)
   if obj is None:
       print("Timeout or empty queue")
   ```

5. **Check queue existence** before operations if needed:
   ```python
   if service.exists('my_queue'):
       obj = service.get('my_queue')
   ```

6. **Use threading, not multiprocessing** for concurrent operations:
   ```python
   import threading  # Use this
   # NOT: import multiprocessing  # Avoid for ThreadQueueService

   def worker():
       service = ThreadQueueService()  # Each thread can use the service
       # ... work ...

   threads = [threading.Thread(target=worker) for _ in range(4)]
   for t in threads:
       t.start()
   for t in threads:
       t.join()
   ```

## Examples in This Directory

| File | Description |
|------|-------------|
| `example_simple_usage.py` | Simple usage example demonstrating common operations |
| `README.md` | This file - comprehensive documentation |

## Related Resources

For more information and test cases, see:
- Implementation: `src/python_utils/service_utils/queue_service/thread_queue_service.py`
- Tests: `test/service_utils/queue_service/thread_queue_service/`
- Abstract base: `src/python_utils/service_utils/queue_service/queue_service_base.py`
- Redis alternative: `src/python_utils/service_utils/queue_service/redis_queue_service.py`

## License

Part of the SciencePythonUtils package.
