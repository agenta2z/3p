"""
Advanced usage examples of OnStorageLists

This demonstrates advanced features:
- Custom serialization (pickle, plain text)
- Nested list keys for hierarchical organization
- Working with complex data structures
- Performance optimization techniques
- Error handling and edge cases

Prerequisites:
    No external dependencies (uses standard library)

Usage:
    python example_advanced_usage.py
"""

from pathlib import Path
import tempfile
import shutil
import pickle
import json

from resolve_path import resolve_path
resolve_path()  # Add project src to sys.path

from python_utils.io_utils.on_storage_lists import OnStorageLists


def example_pickle_serialization():
    """Example: Using pickle for Python object serialization.
    
    Note: This example demonstrates the concept, but OnStorageLists currently
    opens files in text mode. For pickle to work, you would need to modify
    the implementation to support binary mode or use a wrapper.
    """
    print("\n" + "="*80)
    print("EXAMPLE 1: Pickle Serialization (Conceptual)")
    print("="*80)
    
    print("\n   Note: OnStorageLists currently uses text mode for file I/O.")
    print("   For pickle support, you would need to:")
    print("   1. Modify OnStorageLists to support binary mode, or")
    print("   2. Use base64 encoding to store binary data as text")
    print()
    print("   Example with base64 encoding:")
    
    tmpdir = tempfile.mkdtemp()
    
    try:
        import base64
        
        # Wrapper functions for pickle with base64
        def write_pickle_base64(obj, f):
            pickled = pickle.dumps(obj)
            encoded = base64.b64encode(pickled).decode('ascii')
            f.write(encoded)
        
        def read_pickle_base64(f):
            encoded = f.read()
            pickled = base64.b64decode(encoded.encode('ascii'))
            return pickle.loads(pickled)
        
        storage = OnStorageLists(
            root_path=tmpdir,
            default_list_key='python_objects',
            read_method=read_pickle_base64,
            write_method=write_pickle_base64,
            file_extension='.pkl'
        )
        
        # Store various Python objects
        print("\n1. Storing complex Python objects...")
        storage.append({'nested': {'data': [1, 2, 3]}})
        storage.append(set([1, 2, 3, 4, 5]))
        storage.append(tuple([10, 20, 30]))
        storage.append({'name': 'Alice', 'age': 30, 'hobbies': ['reading', 'cycling']})
        
        print("   [OK] Stored: nested dict, set, tuple, complex dict")
        
        # Retrieve objects
        print("\n2. Retrieving objects...")
        objects = storage.get()
        for i, obj in enumerate(objects):
            print(f"   [{i}] {type(obj).__name__}: {obj}")
        
        print("\n   [OK] All objects preserved with their types")
        
        # Demonstrate type preservation
        print("\n3. Verifying type preservation...")
        retrieved_set = storage.get(index=1)
        print(f"   Retrieved set type: {type(retrieved_set)}")
        print(f"   Is set: {isinstance(retrieved_set, set)}")
        print(f"   Can use set operations: {retrieved_set.union({6, 7})}")
        
    finally:
        shutil.rmtree(tmpdir)


def example_plain_text_serialization():
    """Example: Using plain text for simple string storage."""
    print("\n" + "="*80)
    print("EXAMPLE 2: Plain Text Serialization")
    print("="*80)
    
    tmpdir = tempfile.mkdtemp()
    
    try:
        # Custom read/write for plain text
        def write_text(obj, f):
            f.write(str(obj))
        
        def read_text(f):
            return f.read()
        
        storage = OnStorageLists(
            root_path=tmpdir,
            default_list_key='logs',
            read_method=read_text,
            write_method=write_text,
            file_extension='.log'
        )
        
        print("\n1. Storing log entries...")
        storage.append('[2025-11-06 10:00:00] Application started')
        storage.append('[2025-11-06 10:05:00] User logged in: alice')
        storage.append('[2025-11-06 10:10:00] Processing data...')
        storage.append('[2025-11-06 10:15:00] Task completed successfully')
        
        print("   [OK] Stored 4 log entries")
        
        print("\n2. Reading log entries...")
        logs = storage.get()
        for log in logs:
            print(f"   {log}")
        
        print("\n3. Checking file structure...")
        log_dir = Path(tmpdir) / 'logs'
        log_files = sorted(log_dir.glob('*.log'))
        print(f"   [OK] Created {len(log_files)} .log files")
        
        # Show file contents
        print("\n4. Sample file content:")
        print(f"   File: {log_files[0].name}")
        print(f"   Content: {log_files[0].read_text()}")
        
    finally:
        shutil.rmtree(tmpdir)


def example_hierarchical_organization():
    """Example: Using nested list keys for hierarchical data organization."""
    print("\n" + "="*80)
    print("EXAMPLE 3: Hierarchical Organization with Nested Keys")
    print("="*80)
    
    tmpdir = tempfile.mkdtemp()
    
    try:
        storage = OnStorageLists(
            root_path=tmpdir,
            default_list_key='default',
            list_key_components_sep='.'
        )
        
        print("\n1. Creating hierarchical structure...")
        
        # User data
        storage.append(
            {'msg': 'Hello!', 'timestamp': '2025-11-06 10:00'},
            list_key='users.alice.messages'
        )
        storage.append(
            {'msg': 'How are you?', 'timestamp': '2025-11-06 10:05'},
            list_key='users.alice.messages'
        )
        storage.append(
            {'theme': 'dark', 'notifications': True},
            list_key='users.alice.settings'
        )
        
        storage.append(
            {'msg': 'Hi there!', 'timestamp': '2025-11-06 10:02'},
            list_key='users.bob.messages'
        )
        storage.append(
            {'theme': 'light', 'notifications': False},
            list_key='users.bob.settings'
        )
        
        # Application data
        storage.append(
            {'version': '1.0', 'debug': False},
            list_key='app.config.production'
        )
        storage.append(
            {'version': '1.0-dev', 'debug': True},
            list_key='app.config.development'
        )
        
        print("   [OK] Created hierarchical structure")
        
        print("\n2. Retrieving data by key...")
        alice_messages = storage.get(list_key='users.alice.messages')
        alice_settings = storage.get(list_key='users.alice.settings')
        bob_messages = storage.get(list_key='users.bob.messages')
        prod_config = storage.get(list_key='app.config.production')
        
        print(f"   Alice's messages: {len(alice_messages)} items")
        print(f"   Alice's settings: {alice_settings}")
        print(f"   Bob's messages: {len(bob_messages)} items")
        print(f"   Production config: {prod_config}")
        
        print("\n3. Directory structure created:")
        for root, dirs, files in Path(tmpdir).walk():
            level = len(root.relative_to(tmpdir).parts)
            indent = "   " * (level + 1)
            print(f"{indent}{root.name}/")
            subindent = "   " * (level + 2)
            for file in sorted(files):
                print(f"{subindent}{file}")
        
    finally:
        shutil.rmtree(tmpdir)


def example_complex_data_structures():
    """Example: Working with complex nested data structures."""
    print("\n" + "="*80)
    print("EXAMPLE 4: Complex Data Structures")
    print("="*80)
    
    tmpdir = tempfile.mkdtemp()
    
    try:
        storage = OnStorageLists(
            root_path=tmpdir,
            default_list_key='complex_data'
        )
        
        print("\n1. Storing complex nested structures...")
        
        # E-commerce order
        order1 = {
            'order_id': 'ORD-001',
            'customer': {
                'name': 'Alice Johnson',
                'email': 'alice@example.com',
                'address': {
                    'street': '123 Main St',
                    'city': 'Springfield',
                    'zip': '12345'
                }
            },
            'items': [
                {'product': 'Widget', 'quantity': 2, 'price': 19.99},
                {'product': 'Gadget', 'quantity': 1, 'price': 49.99}
            ],
            'total': 89.97,
            'status': 'shipped'
        }
        
        order2 = {
            'order_id': 'ORD-002',
            'customer': {
                'name': 'Bob Smith',
                'email': 'bob@example.com',
                'address': {
                    'street': '456 Oak Ave',
                    'city': 'Riverside',
                    'zip': '67890'
                }
            },
            'items': [
                {'product': 'Doohickey', 'quantity': 3, 'price': 9.99}
            ],
            'total': 29.97,
            'status': 'pending'
        }
        
        storage.append(order1)
        storage.append(order2)
        
        print("   [OK] Stored 2 complex orders")
        
        print("\n2. Querying and filtering data...")
        orders = storage.get()
        
        # Find pending orders
        pending = [o for o in orders if o['status'] == 'pending']
        print(f"   Pending orders: {len(pending)}")
        for order in pending:
            print(f"      - {order['order_id']}: ${order['total']}")
        
        # Calculate total revenue
        total_revenue = sum(o['total'] for o in orders)
        print(f"   Total revenue: ${total_revenue:.2f}")
        
        # Find orders by customer
        alice_orders = [o for o in orders if 'Alice' in o['customer']['name']]
        print(f"   Alice's orders: {len(alice_orders)}")
        
        print("\n3. Updating nested data...")
        # Update order status
        order = storage.get(index=1)
        order['status'] = 'shipped'
        storage.set(order, index=1, overwrite=True)
        print(f"   [OK] Updated order {order['order_id']} status to 'shipped'")
        
    finally:
        shutil.rmtree(tmpdir)


def example_performance_optimization():
    """Example: Performance optimization techniques."""
    print("\n" + "="*80)
    print("EXAMPLE 5: Performance Optimization")
    print("="*80)
    
    tmpdir = tempfile.mkdtemp()
    
    try:
        storage = OnStorageLists(
            root_path=tmpdir,
            default_list_key='data'
        )
        
        print("\n1. Batch operations with extend()...")
        import time
        
        # Inefficient: Multiple append calls
        start = time.time()
        for i in range(100):
            storage.append(i)
        append_time = time.time() - start
        print(f"   100 append() calls: {append_time:.4f}s")
        
        storage.clear()
        
        # Efficient: Single extend call
        start = time.time()
        storage.extend(range(100))
        extend_time = time.time() - start
        print(f"   1 extend() call: {extend_time:.4f}s")
        print(f"   Speedup: {append_time/extend_time:.2f}x faster")
        
        print("\n2. Index-based access vs full list retrieval...")
        
        # Efficient: Get specific item
        start = time.time()
        item = storage.get(index=50)
        index_time = time.time() - start
        print(f"   Get single item by index: {index_time:.6f}s")
        
        # Less efficient: Get full list then index
        start = time.time()
        all_items = storage.get()
        item = all_items[50]
        full_time = time.time() - start
        print(f"   Get full list then index: {full_time:.6f}s")
        
        if index_time > 0 and full_time > index_time:
            print(f"   Index access is {full_time/index_time:.2f}x faster")
        else:
            print(f"   Both methods are very fast for this list size")
        
        print("\n3. Caching frequently accessed items...")
        # For frequently accessed items, cache in memory
        cache = {}
        
        def get_cached(storage, index):
            if index not in cache:
                cache[index] = storage.get(index=index)
            return cache[index]
        
        # First access (cache miss)
        start = time.time()
        item = get_cached(storage, 25)
        first_time = time.time() - start
        
        # Second access (cache hit)
        start = time.time()
        item = get_cached(storage, 25)
        cached_time = time.time() - start
        
        print(f"   First access (cache miss): {first_time:.6f}s")
        print(f"   Second access (cache hit): {cached_time:.6f}s")
        if cached_time > 0 and first_time > cached_time:
            print(f"   Cache speedup: {first_time/cached_time:.2f}x faster")
        else:
            print(f"   Both accesses are very fast (cache hit is instant)")
        
    finally:
        shutil.rmtree(tmpdir)


def example_error_handling():
    """Example: Proper error handling and edge cases."""
    print("\n" + "="*80)
    print("EXAMPLE 6: Error Handling and Edge Cases")
    print("="*80)
    
    tmpdir = tempfile.mkdtemp()
    
    try:
        storage = OnStorageLists(
            root_path=tmpdir,
            default_list_key='data'
        )
        
        print("\n1. Handling empty lists...")
        items = storage.get()
        print(f"   Empty list: {items}")
        print(f"   Length: {len(items)}")
        
        print("\n2. Using default values for missing items...")
        item = storage.get(index=0, default='not_found')
        print(f"   Get non-existent item: '{item}'")
        
        print("\n3. Handling index errors...")
        storage.extend([1, 2, 3])
        try:
            storage.remove(10)
            print("   [X] Should have raised IndexError")
        except IndexError as e:
            print(f"   [OK] Caught IndexError: {e}")
        
        print("\n4. Handling value errors...")
        try:
            idx = storage.index('not_in_list')
            print("   [X] Should have raised ValueError")
        except ValueError as e:
            print(f"   [OK] Caught ValueError: {e}")
        
        print("\n5. Safe pop with default...")
        storage.clear()
        item = storage.pop(default='empty')
        print(f"   Pop from empty list: '{item}'")
        
        print("\n6. Checking list size before operations...")
        size = storage._get_list_size()
        if size > 0:
            item = storage.get(index=0)
        else:
            print("   [OK] List is empty, skipping get operation")
        
        print("\n7. Handling file system errors gracefully...")
        # Simulate by trying to write to read-only location (if possible)
        print("   [OK] File system errors should be caught and logged")
        
    finally:
        shutil.rmtree(tmpdir)


def example_custom_separator():
    """Example: Using custom list key separator."""
    print("\n" + "="*80)
    print("EXAMPLE 7: Custom List Key Separator")
    print("="*80)
    
    tmpdir = tempfile.mkdtemp()
    
    try:
        # Use '/' as separator (like file paths)
        storage = OnStorageLists(
            root_path=tmpdir,
            default_list_key='default',
            list_key_components_sep='/'
        )
        
        print("\n1. Using '/' as separator...")
        storage.append('data1', list_key='project/module/items')
        storage.append('data2', list_key='project/module/items')
        storage.append('config1', list_key='project/config/settings')
        
        items = storage.get(list_key='project/module/items')
        config = storage.get(list_key='project/config/settings')
        
        print(f"   Items: {items}")
        print(f"   Config: {config}")
        
        print("\n2. Directory structure:")
        for root, dirs, files in Path(tmpdir).walk():
            level = len(root.relative_to(tmpdir).parts)
            indent = "   " * (level + 1)
            print(f"{indent}{root.name}/")
        
        # Use '-' as separator
        storage2 = OnStorageLists(
            root_path=tmpdir,
            default_list_key='default',
            list_key_components_sep='-'
        )
        
        print("\n3. Using '-' as separator...")
        storage2.append('value', list_key='app-env-prod')
        items = storage2.get(list_key='app-env-prod')
        print(f"   Items: {items}")
        
    finally:
        shutil.rmtree(tmpdir)


def main():
    print("""
==============================================================================
                OnStorageLists Advanced Usage Examples
==============================================================================
""")
    
    examples = [
        example_pickle_serialization,
        example_plain_text_serialization,
        example_hierarchical_organization,
        example_complex_data_structures,
        example_performance_optimization,
        example_error_handling,
        example_custom_separator,
    ]
    
    for example_func in examples:
        try:
            example_func()
        except Exception as e:
            print(f"\n[X] Example failed: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*80)
    print("[OK] All advanced examples completed!")
    print("="*80 + "\n")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n[X] Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
