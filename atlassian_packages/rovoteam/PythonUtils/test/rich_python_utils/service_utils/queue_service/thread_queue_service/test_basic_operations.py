"""
Test basic operations of ThreadQueueService

Tests:
- Service initialization
- Create queue
- Put/Get operations
- Queue size
- Queue existence
- Delete queue
- List queues
- Clear queue
- Peek operations
- Context manager

Prerequisites:
    No external dependencies (uses standard library)

Usage:
    python test_basic_operations.py
"""

import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root / 'src'))

from python_utils.service_utils.queue_service.thread_queue_service import ThreadQueueService


def test_initialization():
    """Test service initialization."""
    print("\n" + "="*80)
    print("TEST 1: Service Initialization")
    print("="*80)

    try:
        service = ThreadQueueService()
        print(f"[OK] Service initialized: {service}")

        # Test ping
        assert service.ping(), "Ping failed"
        print(f"[OK] Ping successful")

        service.close()
        print(f"[OK] Service closed")
        return True
    except Exception as e:
        print(f"[X] Initialization failed: {e}")
        return False


def test_create_queue():
    """Test creating queues."""
    print("\n" + "="*80)
    print("TEST 2: Create Queue")
    print("="*80)

    service = ThreadQueueService()

    # Create queue
    queue_id = 'test_queue_1'
    created = service.create_queue(queue_id)
    print(f"[OK] Created queue: {queue_id} (created={created})")
    assert created, "Should return True for new queue"

    # Try to create same queue again
    created_again = service.create_queue(queue_id)
    print(f"[OK] Create same queue again: {created_again} (should be False)")
    assert not created_again, "Should return False for existing queue"

    # Check existence
    exists = service.exists(queue_id)
    print(f"[OK] Queue exists: {exists}")
    assert exists, "Queue should exist"

    # Clean up
    service.delete(queue_id)
    service.close()
    return True


def test_put_get():
    """Test putting and getting objects."""
    print("\n" + "="*80)
    print("TEST 3: Put and Get Objects")
    print("="*80)

    service = ThreadQueueService()
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

    service = ThreadQueueService()
    queue_id = 'test_queue_3'

    # Create the queue first
    service.create_queue(queue_id)

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

    service = ThreadQueueService()
    queue_id = 'test_queue_4'

    # Put multiple items
    items = ['first', 'second', 'third']
    for item in items:
        service.put(queue_id, item)

    print(f"Put items: {items}")

    # Peek at tail (last item in queue)
    tail = service.peek(queue_id, index=-1)
    print(f"[OK] Peek at tail (index=-1): {tail}")
    assert tail == 'third', f"Expected 'third', got {tail}"

    # Peek at head (first item in queue)
    head = service.peek(queue_id, index=0)
    print(f"[OK] Peek at head (index=0): {head}")
    assert head == 'first', f"Expected 'first', got {head}"

    # Peek at middle
    middle = service.peek(queue_id, index=1)
    print(f"[OK] Peek at middle (index=1): {middle}")
    assert middle == 'second', f"Expected 'second', got {middle}"

    # Check size didn't change
    size = service.size(queue_id)
    print(f"[OK] Queue size after peek: {size} (unchanged)")
    assert size == 3, f"Peek should not remove items"

    # Test peek on empty queue
    service.clear(queue_id)
    empty_peek = service.peek(queue_id, index=0)
    print(f"[OK] Peek on empty queue: {empty_peek}")
    assert empty_peek is None, "Should return None for empty queue"

    # Test peek with invalid index
    service.put(queue_id, "item")
    try:
        service.peek(queue_id, index=10)
        print(f"[X] Should have raised IndexError")
        assert False, "Should raise IndexError for invalid index"
    except IndexError as e:
        print(f"[OK] Raised IndexError for invalid index: {e}")

    # Clean up
    service.delete(queue_id)
    service.close()
    return True


def test_multiple_queues():
    """Test multiple independent queues."""
    print("\n" + "="*80)
    print("TEST 6: Multiple Independent Queues")
    print("="*80)

    service = ThreadQueueService()

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

    service = ThreadQueueService()
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
    assert cleared == 5, f"Should have cleared 5 items, got {cleared}"

    # Queue should still exist after clear
    assert service.exists(queue_id), "Queue should still exist after clear"

    # Put more items
    service.put(queue_id, "test")
    print(f"\nPut 1 item, size: {service.size(queue_id)}")

    # Delete queue
    deleted = service.delete(queue_id)
    print(f"[OK] Deleted queue: {deleted}")
    print(f"  Exists: {service.exists(queue_id)}")
    assert not service.exists(queue_id), "Queue should not exist after delete"

    # Try to delete non-existent queue
    deleted_again = service.delete(queue_id)
    print(f"[OK] Delete non-existent queue: {deleted_again} (should be False)")
    assert not deleted_again, "Should return False for non-existent queue"

    service.close()
    return True


def test_context_manager():
    """Test using service as context manager."""
    print("\n" + "="*80)
    print("TEST 8: Context Manager")
    print("="*80)

    queue_id = 'test_queue_6'

    with ThreadQueueService() as service:
        service.put(queue_id, "test_data")
        obj = service.get(queue_id, blocking=False)
        print(f"[OK] Context manager works: {obj}")
        assert obj == "test_data"
        service.delete(queue_id)

    print(f"[OK] Service closed automatically")
    return True


def test_auto_create_queue():
    """Test automatic queue creation on put."""
    print("\n" + "="*80)
    print("TEST 9: Auto-Create Queue on Put")
    print("="*80)

    service = ThreadQueueService()
    queue_id = 'test_queue_auto'

    # Put to non-existent queue (should auto-create)
    print(f"Putting to non-existent queue '{queue_id}'...")
    service.put(queue_id, "auto_created")
    print(f"[OK] Queue auto-created")

    # Verify queue exists
    assert service.exists(queue_id), "Queue should exist after put"
    print(f"[OK] Queue exists: {service.exists(queue_id)}")

    # Verify item is there
    obj = service.get(queue_id, blocking=False)
    print(f"[OK] Retrieved item: {obj}")
    assert obj == "auto_created", f"Expected 'auto_created', got {obj}"

    # Clean up
    service.delete(queue_id)
    service.close()
    return True


def test_get_stats():
    """Test getting statistics."""
    print("\n" + "="*80)
    print("TEST 10: Get Statistics")
    print("="*80)

    service = ThreadQueueService()

    # Create queues with different sizes
    service.put('queue_1', 'item1')
    service.put('queue_2', 'item1')
    service.put('queue_2', 'item2')
    service.put('queue_3', 'item1')
    service.put('queue_3', 'item2')
    service.put('queue_3', 'item3')

    # Get stats for specific queue
    stats_q2 = service.get_stats('queue_2')
    print(f"[OK] Stats for queue_2: {stats_q2}")
    assert stats_q2['size'] == 2, f"Expected size 2, got {stats_q2['size']}"
    assert stats_q2['exists'], "Queue should exist"

    # Get stats for all queues
    stats_all = service.get_stats()
    print(f"[OK] Stats for all queues: {stats_all}")
    assert stats_all['total_queues'] == 3, f"Expected 3 queues, got {stats_all['total_queues']}"
    assert 'queue_1' in stats_all['queues'], "queue_1 should be in stats"
    assert 'queue_2' in stats_all['queues'], "queue_2 should be in stats"
    assert 'queue_3' in stats_all['queues'], "queue_3 should be in stats"

    # Clean up
    service.delete('queue_1')
    service.delete('queue_2')
    service.delete('queue_3')
    service.close()
    return True


def test_closed_service():
    """Test operations on closed service."""
    print("\n" + "="*80)
    print("TEST 11: Operations on Closed Service")
    print("="*80)

    service = ThreadQueueService()
    queue_id = 'test_queue_closed'

    # Close the service
    service.close()
    print(f"[OK] Service closed")

    # Try operations on closed service
    try:
        service.put(queue_id, "data")
        print(f"[X] Should have raised RuntimeError")
        return False
    except RuntimeError as e:
        print(f"[OK] Put raised RuntimeError: {e}")

    try:
        service.get(queue_id)
        print(f"[X] Should have raised RuntimeError")
        return False
    except RuntimeError as e:
        print(f"[OK] Get raised RuntimeError: {e}")

    # Ping should return False
    assert not service.ping(), "Ping should return False for closed service"
    print(f"[OK] Ping returns False for closed service")

    return True


def run_all_tests():
    """Run all tests."""
    print("""
==============================================================================
            ThreadQueueService Basic Operations Tests                    
==============================================================================
""")

    tests = [
        ("Initialization", test_initialization),
        ("Create Queue", test_create_queue),
        ("Put/Get", test_put_get),
        ("Blocking Get", test_blocking_get),
        ("Peek", test_peek),
        ("Multiple Queues", test_multiple_queues),
        ("Clear/Delete", test_clear_and_delete),
        ("Context Manager", test_context_manager),
        ("Auto-Create Queue", test_auto_create_queue),
        ("Get Statistics", test_get_stats),
        ("Closed Service", test_closed_service),
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
        print("\n[SUCCESS] All tests passed!")
        return True
    else:
        print(f"\n[FAILED] {total - passed} test(s) failed")
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
