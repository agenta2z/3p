# OnStorageLists - Examples and Documentation

## Overview

`OnStorageLists` is a persistent list implementation where each list item is stored as a separate file on disk. Lists are organized in directories based on list keys, and items are stored with numeric filenames (0.json, 1.json, etc.). This provides a simple way to persist list data without requiring a database.

## Quick Start

```bash
# Run the simple usage example
python example_simple_usage.py
```

## Features

- **Persistent Storage**: Lists survive program restarts
- **File-based**: Each item stored as a separate file
- **Hierarchical Organization**: Use dot-separated keys for nested directory structures
- **Flexible Serialization**: Supports JSON (default), pickle, or custom serialization
- **List-like API**: Familiar methods like append, pop, insert, remove, sort, etc.
- **Multiple Lists**: Manage multiple independent lists in the same storage
- **No Dependencies**: Uses only Python standard library (json, pathlib)

## Basic Usage

```python
from python_utils.io_utils.on_storage_lists import OnStorageLists

# Create storage instance
storage = OnStorageLists(
    root_path='/path/to/storage',
    default_list_key='my_list'
)

# Append items
storage.append({'name': 'Alice', 'age': 30})
storage.append({'name': 'Bob', 'age': 25})

# Get entire list
items = storage.get()
# [{'name': 'Alice', 'age': 30}, {'name': 'Bob', 'age': 25}]

# Get specific item
first_item = storage.get(index=0)
# {'name': 'Alice', 'age': 30}

# Get list size
size = storage._get_list_size()
```

## Storage Structure

OnStorageLists creates a directory structure based on list keys:

```
root_path/
├── my_list/
│   ├── 0.json
│   ├── 1.json
│   └── 2.json
├── users/
│   └── alice/
│       └── messages/
│           ├── 0.json
│           └── 1.json
└── config/
    └── settings/
        └── 0.json
```

List key `"my_list"` → `root_path/my_list/`
List key `"users.alice.messages"` → `root_path/users/alice/messages/`

## API Reference

### Constructor

```python
OnStorageLists(
    root_path: str,
    default_list_key: str,
    list_key_components_sep: str = '.',
    read_method: Callable = json.load,
    write_method: Callable = json.dump,
    file_extension: str = '.json'
)
```

**Parameters:**
- `root_path`: Root directory where all lists are stored
- `default_list_key`: Default list key to use when none is specified
- `list_key_components_sep`: Separator for splitting list keys into path components (default: '.')
- `read_method`: Function to deserialize items from files (default: json.load)
- `write_method`: Function to serialize items to files (default: json.dump)
- `file_extension`: File extension for stored items (default: '.json')

### Core Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `append(obj, list_key)` | Append an object to the end of the list | None |
| `get(list_key, index, default)` | Get an item or the entire list | Any or List[Any] |
| `set(obj_or_list, list_key, index, overwrite)` | Set an item or replace entire list | None |
| `pop(index, list_key, default)` | Remove and return item at index | Any |
| `remove(index, list_key)` | Remove item at index | None |
| `insert(index, obj, list_key)` | Insert item at index | None |
| `clear(list_key)` | Remove all items from list | None |
| `extend(items, list_key)` | Extend list with items from iterable | None |

### Search and Analysis Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `index(item, list_key, start, stop)` | Find first index of item | int |
| `count(item, list_key)` | Count occurrences of item | int |
| `_get_list_size(list_key)` | Get number of items in list | int |

### Manipulation Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `reverse(list_key)` | Reverse list in place | None |
| `sort(list_key, key, reverse)` | Sort list in place | None |

## Detailed Examples

### 1. Basic List Operations

```python
storage = OnStorageLists(root_path='/tmp/storage', default_list_key='tasks')

# Append items
storage.append('Buy groceries')
storage.append('Walk the dog')
storage.append('Finish report')

# Get all items
tasks = storage.get()
# ['Buy groceries', 'Walk the dog', 'Finish report']

# Get specific item
first_task = storage.get(index=0)
# 'Buy groceries'

# Pop last item
last = storage.pop()
# 'Finish report'

# Insert at position
storage.insert(0, 'Morning meeting')
# ['Morning meeting', 'Buy groceries', 'Walk the dog']
```

### 2. Using Nested List Keys

```python
storage = OnStorageLists(root_path='/tmp/storage', default_list_key='default')

# Organize data hierarchically
storage.append('Message 1', list_key='users.alice.inbox')
storage.append('Message 2', list_key='users.alice.inbox')
storage.append('Setting 1', list_key='users.alice.settings')
storage.append('Message 1', list_key='users.bob.inbox')

# Retrieve specific user's data
alice_inbox = storage.get(list_key='users.alice.inbox')
# ['Message 1', 'Message 2']

alice_settings = storage.get(list_key='users.alice.settings')
# ['Setting 1']
```

### 3. Working with Complex Objects

```python
storage = OnStorageLists(root_path='/tmp/storage', default_list_key='people')

# Store dictionaries
storage.append({
    'name': 'Alice',
    'age': 30,
    'email': 'alice@example.com',
    'hobbies': ['reading', 'cycling']
})

storage.append({
    'name': 'Bob',
    'age': 25,
    'email': 'bob@example.com',
    'hobbies': ['gaming', 'cooking']
})

# Retrieve and filter
people = storage.get()
adults = [p for p in people if p['age'] >= 18]

# Search for specific person
alice_index = storage.index({'name': 'Alice', 'age': 30, 'email': 'alice@example.com', 'hobbies': ['reading', 'cycling']})
```

### 4. Custom Serialization (Plain Text)

```python
def write_text(obj, f):
    f.write(str(obj))

def read_text(f):
    return f.read()

storage = OnStorageLists(
    root_path='/tmp/storage',
    default_list_key='logs',
    read_method=read_text,
    write_method=write_text,
    file_extension='.txt'
)

storage.append('2025-01-05 12:00:00 - Application started')
storage.append('2025-01-05 12:05:00 - User logged in')
storage.append('2025-01-05 12:10:00 - Data processed')

logs = storage.get()
# ['2025-01-05 12:00:00 - Application started', ...]
```

### 5. Custom Serialization (Pickle)

```python
import pickle

storage = OnStorageLists(
    root_path='/tmp/storage',
    default_list_key='objects',
    read_method=pickle.load,
    write_method=pickle.dump,
    file_extension='.pkl'
)

# Can store any picklable Python object
class CustomObject:
    def __init__(self, value):
        self.value = value

storage.append(CustomObject(42))
storage.append(lambda x: x * 2)  # Note: lambdas are not picklable by default

objects = storage.get()
```

### 6. Set Entire List at Once

```python
storage = OnStorageLists(root_path='/tmp/storage', default_list_key='numbers')

# Set entire list
storage.set([1, 2, 3, 4, 5])

# Get entire list
numbers = storage.get()
# [1, 2, 3, 4, 5]

# Update specific item
storage.set(99, index=2, overwrite=True)
# [1, 2, 99, 4, 5]

# Replace entire list
storage.set([10, 20, 30], overwrite=True)
# [10, 20, 30]
```

### 7. List Manipulation

```python
storage = OnStorageLists(root_path='/tmp/storage', default_list_key='data')

# Extend with multiple items
storage.extend([1, 2, 3, 4, 5])

# Sort
storage.sort()
# [1, 2, 3, 4, 5]

# Reverse
storage.reverse()
# [5, 4, 3, 2, 1]

# Sort with custom key
storage.clear()
storage.extend(['apple', 'pie', 'a', 'longer'])
storage.sort(key=len)
# ['a', 'pie', 'apple', 'longer']
```

### 8. Search and Count

```python
storage = OnStorageLists(root_path='/tmp/storage', default_list_key='items')

storage.extend(['apple', 'banana', 'apple', 'cherry', 'apple'])

# Count occurrences
count = storage.count('apple')
# 3

# Find index
index = storage.index('banana')
# 1

# Find index in range
index = storage.index('apple', start=2)
# 2 (finds the second occurrence)

# Item not found raises ValueError
try:
    storage.index('orange')
except ValueError:
    print("Item not found")
```

## Use Cases

### 1. Persistent Task Queue

```python
# Producer
storage = OnStorageLists(root_path='/shared/tasks', default_list_key='pending')
storage.append({'task': 'process_data', 'params': {'file': 'data.csv'}})
storage.append({'task': 'send_email', 'params': {'to': 'user@example.com'}})

# Consumer
storage = OnStorageLists(root_path='/shared/tasks', default_list_key='pending')
while storage._get_list_size() > 0:
    task = storage.pop(index=0)  # FIFO
    process_task(task)
```

### 2. User Data Storage

```python
storage = OnStorageLists(root_path='/app/data', default_list_key='default')

# Store user messages
storage.append(
    {'timestamp': '2025-01-05T12:00:00', 'message': 'Hello!'},
    list_key=f'users.{user_id}.messages'
)

# Store user preferences
storage.append(
    {'theme': 'dark', 'notifications': True},
    list_key=f'users.{user_id}.preferences'
)

# Retrieve user data
messages = storage.get(list_key=f'users.{user_id}.messages')
```

### 3. Log Aggregation

```python
storage = OnStorageLists(
    root_path='/var/log/app',
    default_list_key='application.logs',
    read_method=lambda f: f.read(),
    write_method=lambda obj, f: f.write(str(obj)),
    file_extension='.log'
)

# Append log entries
storage.append('[INFO] Application started')
storage.append('[WARNING] Memory usage high')
storage.append('[ERROR] Connection failed')

# Read all logs
all_logs = storage.get()
```

### 4. Configuration History

```python
storage = OnStorageLists(root_path='/app/config', default_list_key='history')

# Save configuration versions
storage.append({
    'version': '1.0',
    'timestamp': '2025-01-05T12:00:00',
    'settings': {'timeout': 30, 'retries': 3}
})

# Get configuration history
history = storage.get()

# Rollback to previous version
previous_config = storage.get(index=-2)  # Second to last
```

## Comparison with Alternatives

| Feature | OnStorageLists | Regular List | Database | JSON File |
|---------|----------------|--------------|----------|-----------|
| Persistent | Yes | No | Yes | Yes |
| File per item | Yes | N/A | No | No |
| Hierarchical keys | Yes | No | Depends | No |
| List-like API | Yes | Yes | No | No |
| Setup required | None | None | Yes | None |
| Performance (large lists) | Moderate | Excellent | Excellent | Poor |
| Concurrent access | Limited | No | Yes | Limited |

## Performance Considerations

### Strengths

- **Individual item access**: Fast for getting/setting specific items by index
- **Append operations**: Fast, only writes one file
- **Small to medium lists**: Good performance for lists with < 10,000 items

### Limitations

- **Large lists**: Slow for very large lists (>10,000 items)
- **Iteration**: Reading entire list requires opening many files
- **Sorting/Reversing**: Must read entire list into memory
- **Concurrent writes**: No locking mechanism (use for single-process or coordinate access)

### Optimization Tips

1. **Use appropriate serialization**: JSON for readability, pickle for performance
2. **Batch operations**: Use `extend()` instead of multiple `append()` calls when possible
3. **Index access**: Prefer index-based access over full list retrieval
4. **List size**: Keep lists reasonably sized (< 10,000 items)
5. **File system**: Use SSD for better I/O performance

## Best Practices

### 1. Use Context Managers for Temporary Storage

```python
import tempfile
import shutil

tmpdir = tempfile.mkdtemp()
try:
    storage = OnStorageLists(root_path=tmpdir, default_list_key='temp')
    # Your code here
finally:
    shutil.rmtree(tmpdir)
```

### 2. Use Meaningful List Keys

```python
# Good
storage.append(data, list_key='users.alice.messages')
storage.append(data, list_key='orders.2025.january')

# Avoid
storage.append(data, list_key='list1')
storage.append(data, list_key='temp')
```

### 3. Handle Missing Items Gracefully

```python
# Use default parameter
item = storage.get(index=10, default='not_found')

# Or check size first
size = storage._get_list_size()
if index < size:
    item = storage.get(index=index)
```

### 4. Choose Appropriate Serialization

```python
# JSON - Human-readable, cross-language
storage = OnStorageLists(
    root_path=path,
    default_list_key='data',
    read_method=json.load,
    write_method=json.dump,
    file_extension='.json'
)

# Pickle - Python objects, faster
storage = OnStorageLists(
    root_path=path,
    default_list_key='data',
    read_method=pickle.load,
    write_method=pickle.dump,
    file_extension='.pkl'
)

# Plain text - Simple strings
def write_text(obj, f): f.write(str(obj))
def read_text(f): return f.read()

storage = OnStorageLists(
    root_path=path,
    default_list_key='data',
    read_method=read_text,
    write_method=write_text,
    file_extension='.txt'
)
```

### 5. Clean Up When Done

```python
# Clear list but keep directory
storage.clear()

# Remove entire directory structure
import shutil
shutil.rmtree(storage._get_list_dir())
```

## Troubleshooting

### Issue: FileNotFoundError

**Cause:** Trying to access a list that hasn't been created yet

**Solution:** Use `append()` or `set()` to create the list first, or check existence:

```python
list_dir = storage._get_list_dir(list_key)
if list_dir.exists():
    items = storage.get(list_key)
```

### Issue: JSONDecodeError

**Cause:** Corrupted JSON file or wrong serialization method

**Solution:** Check file contents, ensure using correct read_method:

```python
# Check file contents
import pathlib
file_path = storage._get_item_path(0)
print(pathlib.Path(file_path).read_text())
```

### Issue: Slow Performance

**Cause:** Large lists or many file operations

**Solutions:**
- Reduce list size by splitting into multiple lists
- Use pickle instead of JSON
- Cache frequently accessed items in memory
- Consider using a database for very large datasets

### Issue: Concurrent Access

**Cause:** Multiple processes writing to same list simultaneously

**Solution:** Implement file locking or use a database for concurrent access:

```python
import fcntl  # Unix only

# Add locking to write operations
with open(file_path, 'w') as f:
    fcntl.flock(f, fcntl.LOCK_EX)
    storage.write_method(obj, f)
    fcntl.flock(f, fcntl.LOCK_UN)
```

## Examples in This Directory

| File | Description |
|------|-------------|
| `example_simple_usage.py` | Comprehensive example demonstrating all major features and basic operations |
| `example_advanced_usage.py` | Advanced features including custom serialization, pickle, nested keys, performance optimization, and error handling |
| `example_use_cases.py` | Real-world use cases: task queues, log aggregation, config history, user data management, event sourcing, and data pipeline checkpointing |
| `README.md` | This file - complete documentation |

### Running the Examples

```bash
# Basic usage - covers all fundamental operations
python example_simple_usage.py

# Advanced features - custom serialization, performance tips
python example_advanced_usage.py

# Real-world applications - practical use cases
python example_use_cases.py
```

## Related Resources

- Implementation: [src/python_utils/io_utils/on_storage_lists.py](../../../../../../src/python_utils/io_utils/on_storage_lists.py)
- Tests: [test/python_utils/io_utils/test_on_storage_lists.py](../../../../../../test/python_utils/io_utils/test_on_storage_lists.py)

## License

Part of the SciencePythonUtils package.
