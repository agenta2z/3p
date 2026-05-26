## StorageBasedQueueService - Examples and Documentation

## Overview

`StorageBasedQueueService` is a persistent, multiprocessing-capable queue service built on top of `OnStorageLists`. It provides true inter-process communication through file-based storage, making it ideal for distributed task processing without requiring external dependencies like Redis.

## Quick Start

```bash
# Run the simple usage example
python example_simple_usage.py

# Run the multiprocessing example
python example_multiprocessing.py
```

## Features

- **TRUE Multiprocessing Support**: Works across separate processes (unlike ThreadQueueService)
- **Persistent Queues**: Survive program restarts
- **No External Dependencies**: Uses file system only
- **Thread-Safe and Process-Safe**: File locking for concurrent access
- **Multiple Named Queues**: Manage multiple independent queues
- **Blocking/Non-Blocking Operations**: With timeout support
- **FIFO Ordering**: First-in, first-out queue semantics

## When to Use

### Best Use Cases

- Inter-process communication on a single machine
- Persistent task queues that survive restarts
- Development/testing without Redis
- Low to medium throughput applications (<1000 ops/sec)
- Data pipeline checkpointing
- Job queues with persistence requirements

### Not Suitable For

- Very high throughput applications (>1000 ops/sec)
- Distributed systems across multiple machines (unless using shared file system)
- Real-time applications requiring sub-millisecond latency

## Comparison with Other Queue Services

| Feature | StorageBasedQueueService | ThreadQueueService | RedisQueueService |
|---------|---------------------|-------------------|-------------------|
| Multiprocessing | ✓ Yes | ✗ No | ✓ Yes |
| Persistence | ✓ Yes | ✗ No | ✓ Yes (with config) |
| External Dependencies | ✗ None | ✗ None | ✓ Redis server |
| Performance | Medium | Fast | Very Fast |
| Setup Complexity | Low | Low | Medium |
| Distributed Systems | Limited | ✗ No | ✓ Yes |

## Basic Usage

### Simple Producer-Consumer

```python
from python_utils.service_utils.queue_service.storage_based_queue_service import (
    StorageBasedQueueService
)

# Producer
service = StorageBasedQueueService(root_path='/tmp/queues')
service.put('tasks', {'task_id': 1, 'action': 'process'})
service.close()

# Consumer (can be in a separate process)
service = StorageBasedQueueService(root_path='/tmp/queues')
task = service.get('tasks', blocking=True, timeout=5.0)
print(f"Got task: {task}")
service.close()
```

### Context Manager

```python
with StorageBasedQueueService(root_path='/tmp/queues') as service:
    service.put('queue', {'data': 'value'})
    item = service.get('queue')
```

### Multiprocessing Example

```python
import multiprocessing as mp

def producer():
    service = StorageBasedQueueService(root_path='/tmp/queues')
    for i in range(10):
        service.put('tasks', {'id': i})
    service.close()

def consumer():
    service = StorageBasedQueueService(root_path='/tmp/queues')
    while True:
        task = service.get('tasks', blocking=True, timeout=2.0)
        if task is None:
            break
        print(f"Processing: {task}")
    service.close()

# This WORKS - processes share the same file-based queues
p1 = mp.Process(target=producer)
p2 = mp.Process(target=consumer)
p1.start()
p2.start()
p1.join()
p2.join()
```

## API Reference

### Constructor

```python
StorageBasedQueueService(root_path: Optional[str] = None)
```

**Parameters:**
- `root_path`: Root directory for queue storage. If None, uses a temporary directory (not persistent across runs).

### Core Methods

#### `create_queue(queue_id: str) -> bool`

Create a new queue with the given ID.

```python
service = StorageBasedQueueService(root_path='/tmp/queues')
created = service.create_queue('my_queue')
# Returns True if created, False if already exists
```

#### `put(queue_id: str, obj: Any, timeout: Optional[float] = None) -> bool`

Put an object onto the queue.

```python
service.put('tasks', {'task_id': 1, 'data': 'value'})
```

**Parameters:**
- `queue_id`: Queue identifier
- `obj`: Any JSON-serializable Python object
- `timeout`: Optional timeout in seconds for lock acquisition

**Returns:** True if successful

#### `get(queue_id: str, blocking: bool = True, timeout: Optional[float] = None) -> Optional[Any]`

Get an object from the queue (FIFO).

```python
# Non-blocking
item = service.get('tasks', blocking=False)

# Blocking with timeout
item = service.get('tasks', blocking=True, timeout=5.0)

# Blocking forever
item = service.get('tasks', blocking=True)
```

**Parameters:**
- `queue_id`: Queue identifier
- `blocking`: If True, block until item available or timeout
- `timeout`: Timeout in seconds (None = wait forever)

**Returns:** Python object, or None if queue is empty (non-blocking) or timeout reached

#### `peek(queue_id: str, index: int = 0) -> Optional[Any]`

Peek at an item without removing it.

```python
# Peek at front
item = service.peek('tasks', index=0)

# Peek at back
item = service.peek('tasks', index=-1)
```

#### `size(queue_id: str) -> int`

Get the number of items in the queue.

```python
size = service.size('tasks')
```

#### `exists(queue_id: str) -> bool`

Check if a queue exists.

```python
if service.exists('tasks'):
    print("Queue exists")
```

#### `delete(queue_id: str) -> bool`

Delete a queue and all its contents.

```python
deleted = service.delete('tasks')
```

#### `clear(queue_id: str) -> int`

Clear all items from a queue without deleting it.

```python
cleared_count = service.clear('tasks')
```

#### `list_queues() -> List[str]`

List all queue IDs.

```python
queues = service.list_queues()
print(f"All queues: {queues}")
```

#### `get_stats(queue_id: Optional[str] = None) -> Dict[str, Any]`

Get statistics about queues.

```python
# Stats for specific queue
stats = service.get_stats('tasks')

# Stats for all queues
stats = service.get_stats()
```

#### `ping() -> bool`

Check if service is responsive.

```python
if service.ping():
    print("Service is responsive")
```

#### `close()`

Close the service and clean up resources.

```python
service.close()
```

## Detailed Examples

### Example 1: Task Queue with Persistence

```python
from python_utils.service_utils.queue_service.storage_based_queue_service import (
    StorageBasedQueueService
)

# Add tasks
service = StorageBasedQueueService(root_path='/var/app/queues')
service.put('pending_tasks', {'task': 'send_email', 'to': 'user@example.com'})
service.put('pending_tasks', {'task': 'process_data', 'file': 'data.csv'})
service.close()

# Later (or in another process)...
service = StorageBasedQueueService(root_path='/var/app/queues')
while service.size('pending_tasks') > 0:
    task = service.get('pending_tasks', blocking=False)
    print(f"Processing: {task}")
    # Process task...
service.close()
```

### Example 2: Multiple Producers and Consumers

```python
import multiprocessing as mp
from python_utils.service_utils.queue_service.storage_based_queue_service import (
    StorageBasedQueueService
)


def producer(producer_id, num_tasks):
    service = StorageBasedQueueService(root_path='/tmp/queues')
    for i in range(num_tasks):
        task = {'producer': producer_id, 'task': i}
        service.put('tasks', task)
    service.close()


def consumer(consumer_id):
    service = StorageBasedQueueService(root_path='/tmp/queues')
    while True:
        task = service.get('tasks', blocking=True, timeout=2.0)
        if task is None:
            break
        print(f"Consumer {consumer_id} processing: {task}")
    service.close()


# Start 2 producers
producers = [mp.Process(target=producer, args=(i, 5)) for i in range(2)]
for p in producers:
    p.start()

# Start 3 consumers
consumers = [mp.Process(target=consumer, args=(i,)) for i in range(3)]
for c in consumers:
    c.start()

# Wait for completion
for p in producers:
    p.join()
for c in consumers:
    c.join()
```

### Example 3: Priority Queues

```python
from python_utils.service_utils.queue_service.storage_based_queue_service import (
    StorageBasedQueueService
)

service = StorageBasedQueueService(root_path='/tmp/queues')

# Add tasks to different priority queues
service.put('high_priority', {'task': 'urgent_task'})
service.put('normal_priority', {'task': 'regular_task'})
service.put('low_priority', {'task': 'background_task'})

# Process high priority first
while service.size('high_priority') > 0:
    task = service.get('high_priority', blocking=False)
    print(f"Processing high priority: {task}")

# Then normal priority
while service.size('normal_priority') > 0:
    task = service.get('normal_priority', blocking=False)
    print(f"Processing normal priority: {task}")

# Finally low priority
while service.size('low_priority') > 0:
    task = service.get('low_priority', blocking=False)
    print(f"Processing low priority: {task}")

service.close()
```

### Example 4: Progress Monitoring

```python
import multiprocessing as mp
import time
from python_utils.service_utils.queue_service.storage_based_queue_service import (
    StorageBasedQueueService
)


def monitor(total_expected):
    service = StorageBasedQueueService(root_path='/tmp/queues')
    while True:
        pending = service.size('tasks')
        completed = service.size('results')
        print(f"Progress: {completed}/{total_expected} (Pending: {pending})")

        if completed >= total_expected:
            break
        time.sleep(0.5)
    service.close()


# Start monitor in separate process
total_tasks = 10
m = mp.Process(target=monitor, args=(total_tasks,))
m.start()

# Add tasks and process them...
# (producer and consumer code here)

m.join()
```

## Performance Considerations

### Strengths

- **Persistence**: Data survives crashes and restarts
- **Simplicity**: No external dependencies
- **Multiprocessing**: True inter-process communication

### Limitations

- **Throughput**: ~100-500 ops/sec (vs Redis: 10,000+ ops/sec)
- **Latency**: 1-10ms per operation (vs Redis: <1ms)
- **File I/O**: Overhead from disk operations

### Optimization Tips

1. **Batch Operations**: Process multiple items at once
2. **SSD Storage**: Use SSD for better I/O performance
3. **Reduce Lock Contention**: Use multiple queues instead of one
4. **Appropriate Timeouts**: Set reasonable timeout values
5. **Clean Up**: Delete old queues to reduce directory scanning

## Error Handling

### Common Errors

```python
from python_utils.service_utils.queue_service.storage_based_queue_service import (
    StorageBasedQueueService
)

service = StorageBasedQueueService(root_path='/tmp/queues')

# Handle closed service
service.close()
try:
    service.put('queue', 'data')
except RuntimeError as e:
    print(f"Service is closed: {e}")

# Handle timeout
service2 = StorageBasedQueueService(root_path='/tmp/queues')
item = service2.get('empty_queue', blocking=True, timeout=1.0)
if item is None:
    print("Timeout or empty queue")

# Handle index errors
try:
    service2.peek('queue', index=100)
except IndexError as e:
    print(f"Index out of range: {e}")

service2.close()
```

## Best Practices

### 1. Use Context Managers

```python
with StorageBasedQueueService(root_path='/tmp/queues') as service:
    service.put('queue', 'data')
    # Automatically closed
```

### 2. Set Appropriate Timeouts

```python
# For consumers that should exit when no work
item = service.get('queue', blocking=True, timeout=5.0)

# For long-running consumers
item = service.get('queue', blocking=True, timeout=None)
```

### 3. Handle Empty Queues

```python
if service.size('queue') > 0:
    item = service.get('queue', blocking=False)
else:
    print("Queue is empty")
```

### 4. Clean Up Old Queues

```python
# Delete queues when done
service.delete('old_queue')

# Or clear if you want to reuse
service.clear('queue')
```

### 5. Use Meaningful Queue Names

```python
# Good
service.put('user_notifications', notification)
service.put('data_processing_tasks', task)

# Avoid
service.put('queue1', data)
service.put('temp', data)
```

## Troubleshooting

### Issue: Slow Performance

**Cause:** File I/O overhead, many small operations

**Solution:**
- Use SSD storage
- Batch operations when possible
- Reduce number of queues
- Consider Redis for high throughput

### Issue: Lock Timeout

**Cause:** High contention, slow operations

**Solution:**
- Increase timeout values
- Use multiple queues to reduce contention
- Optimize processing time

### Issue: Disk Space

**Cause:** Many items in queues

**Solution:**
- Regularly clear completed queues
- Delete old queues
- Monitor disk usage

## Examples in This Directory

| File | Description |
|------|-------------|
| `example_simple_usage.py` | Basic operations and queue management |
| `example_multiprocessing.py` | Producer-consumer patterns with multiple processes |
| `README.md` | This file - complete documentation |

### Running the Examples

```bash
# Basic usage
python example_simple_usage.py

# Multiprocessing examples
python example_multiprocessing.py
```

## Related Resources

- Implementation: [src/python_utils/service_utils/queue_service/storage_based_queue_service.py](../../../../../../src/python_utils/service_utils/queue_service/storage_based_queue_service.py)
- Tests: [test/python_utils/service_utils/queue_service/test_storage_based_queue_service.py](../../../../../../test/python_utils/service_utils/queue_service/test_storage_based_queue_service.py)
- OnStorageLists: [src/python_utils/io_utils/on_storage_lists.py](../../../../../../src/python_utils/io_utils/on_storage_lists.py)

## License

Part of the SciencePythonUtils package.
