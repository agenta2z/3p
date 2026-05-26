"""
Test basic operations of RedisQueueService

Tests:
- Connection to Redis
- Create queue
- Put/Get operations
- Queue size
- Queue existence
- Delete queue
- List queues

Prerequisites:
    1. Install Redis: pip install redis
    2. Start Redis server:
       - Docker: docker run -d -p 6379:6379 redis
       - Or local Redis installation

Usage:
    python test_basic_operations.py
"""

import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root / 'src'))

from python_utils.service_utils.queue_service.redis_queue_service import RedisQueueService


def test_connection():
    """Test connection to Redis server."""
    print("\n" + "="*80)
    print("TEST 1: Connection to Redis Server")
    print("="*80)

    try:
        service = RedisQueueService(host='localhost', port=6379)
        print(f"[OK] Connected to Redis at localhost:6379")
        print(f"  Service: {service}")

        # Test ping
        assert service.ping(), "Ping failed"
        print(f"[OK] Ping successful")

        service.close()
        print(f"[OK] Connection closed")
        return True
    except Exception as e:
        print(f"[X] Connection failed: {e}")
        print(f"\nMake sure Redis is running:")
        print(f"  Docker: docker run -d -p 6379:6379 redis")
        print(f"  Or install Redis locally")
        return False


def test_create_queue():
    """Test creating queues."""
    print("\n" + "="*80)
    print("TEST 2: Create Queue")
    print("="*80)

    service = RedisQueueService()

    # Create queue
    queue_id = 'test_queue_1'
    created = service.create_queue(queue_id)
    print(f"[OK] Created queue: {queue_id} (created={created})")

    # Check existence
    exists = service.exists(queue_id)
    print(f"  Exists: {exists}")

    # Clean up
    service.delete(queue_id)
    service.close()
    return True


def test_put_get():
    """Test putting and getting objects."""
    print("\n" + "="*80)
    print("TEST 3: Put and Get Objects")
    print("="*80)

    service = RedisQueueService()
    queue_id = 'test_queue_2'

    # Test different object types
    test_objects = [
        42,
        "hello world",
        [1, 2, 3],
        {'key': 'value', 'number': 123},
        ('tuple', 'data'),
        {'nested': {'dict': {'with': ['list', 'inside']}}},
    ]

    print(f"\nPutting {len(test_objects)} objects onto queue '{queue_id}':")
    for i, obj in enumerate(test_objects):
        service.put(queue_id, obj)
        print(f"  [{i+1}] Put: {obj}")

    # Check size
    size = service.size(queue_id)
    print(f"\n[OK] Queue size: {size}")
    assert size == len(test_objects), f"Expected {len(test_objects)}, got {size}"

    # Get objects
    print(f"\nGetting objects from queue:")
    for i in range(len(test_objects)):
        obj = service.get(queue_id, blocking=False)
        print(f"  [{i+1}] Got: {obj}")
        assert obj == test_objects[i], f"Expected {test_objects[i]}, got {obj}"

    print(f"\n[OK] All objects retrieved correctly")

    # Check empty
    size = service.size(queue_id)
    print(f"[OK] Queue size after get: {size}")
    assert size == 0, f"Queue should be empty, but has {size} items"

    # Get from empty queue (non-blocking)
    obj = service.get(queue_id, blocking=False)
    print(f"[OK] Get from empty queue (non-blocking): {obj}")
    assert obj is None, "Should return None for empty queue"

    # Clean up
    service.delete(queue_id)
    service.close()
    return True


def test_blocking_get():
    """Test blocking get with timeout."""
    print("\n" + "="*80)
    print("TEST 4: Blocking Get with Timeout")
    print("="*80)

    service = RedisQueueService()
    queue_id = 'test_queue_3'

    # Get from empty queue with timeout
    print(f"Getting from empty queue with 2 second timeout...")
    import time
    start = time.time()
    obj = service.get(queue_id, blocking=True, timeout=2.0)
    elapsed = time.time() - start

    print(f"[OK] Returned after {elapsed:.2f} seconds")
    print(f"  Result: {obj}")
    assert obj is None, "Should return None after timeout"
    assert elapsed >= 1.9, f"Should wait ~2 seconds, but only waited {elapsed:.2f}"

    # Put object and get immediately
    print(f"\nPutting object and getting with blocking...")
    service.put(queue_id, "test_data")
    obj = service.get(queue_id, blocking=True, timeout=5.0)
    print(f"[OK] Got immediately: {obj}")
    assert obj == "test_data", f"Expected 'test_data', got {obj}"

    # Clean up
    service.delete(queue_id)
    service.close()
    return True


def test_peek():
    """Test peeking at queue without removing items."""
    print("\n" + "="*80)
    print("TEST 5: Peek Operation")
    print("="*80)

    service = RedisQueueService()
    queue_id = 'test_queue_4'

    # Put multiple items
    items = ['first', 'second', 'third']
    for item in items:
        service.put(queue_id, item)

    print(f"Put items: {items}")

    # Peek at tail (last item to be retrieved)
    tail = service.peek(queue_id, index=-1)
    print(f"[OK] Peek at tail (index=-1): {tail}")
    assert tail == 'first', f"Expected 'first', got {tail}"

    # Peek at head (first item to be retrieved)
    head = service.peek(queue_id, index=0)
    print(f"[OK] Peek at head (index=0): {head}")
    assert head == 'third', f"Expected 'third', got {head}"

    # Check size didn't change
    size = service.size(queue_id)
    print(f"[OK] Queue size after peek: {size} (unchanged)")
    assert size == 3, f"Peek should not remove items"

    # Clean up
    service.delete(queue_id)
    service.close()
    return True


def test_multiple_queues():
    """Test multiple independent queues."""
    print("\n" + "="*80)
    print("TEST 6: Multiple Independent Queues")
    print("="*80)

    service = RedisQueueService()

    # Create multiple queues
    queues = {
        'queue_a': [1, 2, 3],
        'queue_b': ['a', 'b', 'c'],
        'queue_c': [{'key': 'value'}]
    }

    # Put items
    print("\nCreating queues and adding items:")
    for queue_id, items in queues.items():
        for item in items:
            service.put(queue_id, item)
        print(f"  {queue_id}: {items} (size={service.size(queue_id)})")

    # List queues
    all_queues = service.list_queues()
    print(f"\n[OK] Listed queues: {all_queues}")

    for queue_id in queues.keys():
        assert queue_id in all_queues, f"Queue {queue_id} should be listed"

    # Get stats
    stats = service.get_stats()
    print(f"\n[OK] Stats: {stats}")

    # Verify each queue
    print(f"\nVerifying each queue:")
    for queue_id, expected_items in queues.items():
        retrieved_items = []
        while True:
            item = service.get(queue_id, blocking=False)
            if item is None:
                break
            retrieved_items.append(item)

        print(f"  {queue_id}: {retrieved_items}")
        assert retrieved_items == expected_items, f"Queue {queue_id} mismatch"

    print(f"\n[OK] All queues verified")

    # Clean up
    for queue_id in queues.keys():
        service.delete(queue_id)
    service.close()
    return True


def test_clear_and_delete():
    """Test clearing and deleting queues."""
    print("\n" + "="*80)
    print("TEST 7: Clear and Delete Operations")
    print("="*80)

    service = RedisQueueService()
    queue_id = 'test_queue_5'

    # Put items
    for i in range(5):
        service.put(queue_id, i)

    print(f"Put 5 items, size: {service.size(queue_id)}")

    # Clear queue
    cleared = service.clear(queue_id)
    print(f"[OK] Cleared queue, removed {cleared} items")
    print(f"  Size after clear: {service.size(queue_id)}")
    assert service.size(queue_id) == 0, "Queue should be empty after clear"

    # Put more items
    service.put(queue_id, "test")
    print(f"\nPut 1 item, size: {service.size(queue_id)}")

    # Delete queue
    deleted = service.delete(queue_id)
    print(f"[OK] Deleted queue: {deleted}")
    print(f"  Exists: {service.exists(queue_id)}")
    assert not service.exists(queue_id), "Queue should not exist after delete"

    service.close()
    return True


def test_context_manager():
    """Test using service as context manager."""
    print("\n" + "="*80)
    print("TEST 8: Context Manager")
    print("="*80)

    queue_id = 'test_queue_6'

    with RedisQueueService() as service:
        service.put(queue_id, "test_data")
        obj = service.get(queue_id, blocking=False)
        print(f"[OK] Context manager works: {obj}")
        assert obj == "test_data"
        service.delete(queue_id)

    print(f"[OK] Service closed automatically")
    return True


def run_all_tests():
    """Run all tests."""
    print("""
==============================================================================
                  RedisQueueService Basic Operations Tests                    
==============================================================================
""")

    tests = [
        ("Connection", test_connection),
        ("Create Queue", test_create_queue),
        ("Put/Get", test_put_get),
        ("Blocking Get", test_blocking_get),
        ("Peek", test_peek),
        ("Multiple Queues", test_multiple_queues),
        ("Clear/Delete", test_clear_and_delete),
        ("Context Manager", test_context_manager),
    ]

    results = []

    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"\n[X] Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    for name, success in results:
        status = "[OK] PASS" if success else "[X] FAIL"
        print(f"  {status}: {name}")

    total = len(results)
    passed = sum(1 for _, success in results if success)

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n All tests passed!")
        return True
    else:
        print(f"\n❌ {total - passed} test(s) failed")
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
