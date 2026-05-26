"""
Simple usage example of ThreadQueueService

This demonstrates the most common operations:
- Creating a queue
- Putting objects
- Getting objects
- Checking queue status

Prerequisites:
    No external dependencies (uses standard library)

Usage:
    python example_simple_usage.py
"""

from resolve_path import resolve_path
resolve_path()  # Add project src to sys.path

from python_utils.service_utils.queue_service.thread_queue_service import ThreadQueueService


def main():
    print("""
==============================================================================
             ThreadQueueService Simple Usage Example                    
==============================================================================
""")

    # 1. Create service instance
    print("1. Creating ThreadQueueService...")
    service = ThreadQueueService()
    print(f"   [OK] Service initialized: {service}")

    # 2. Create a queue
    print("\n2. Creating a queue...")
    queue_id = 'my_example_queue'
    service.create_queue(queue_id)
    print(f"   [OK] Queue created: {queue_id}")

    # 3. Put different types of objects
    print("\n3. Putting objects onto the queue...")

    objects_to_put = [
        # Simple types
        42,
        "Hello, Multiprocessing Queue!",
        3.14159,
        True,

        # Collections
        [1, 2, 3, 4, 5],
        {'name': 'Alice', 'age': 30, 'city': 'Seattle'},
        ('tuple', 'data', 123),

        # Nested structures
        {
            'user': {
                'id': 1,
                'profile': {
                    'name': 'Bob',
                    'interests': ['coding', 'music', 'reading']
                }
            },
            'metadata': {
                'timestamp': '2025-01-05T12:00:00',
                'version': '1.0'
            }
        }
    ]

    for i, obj in enumerate(objects_to_put, 1):
        service.put(queue_id, obj)
        print(f"   [{i}] Put: {obj}")

    # 4. Check queue size
    print("\n4. Checking queue size...")
    size = service.size(queue_id)
    print(f"   [OK] Queue size: {size} items")

    # 5. Peek at next item (without removing)
    print("\n5. Peeking at next item (without removing)...")
    next_item = service.peek(queue_id, index=0)
    print(f"   [OK] Next item (head): {next_item}")
    last_item = service.peek(queue_id, index=-1)
    print(f"   [OK] Last item (tail): {last_item}")
    print(f"   [OK] Queue size still: {service.size(queue_id)}")

    # 6. Get objects from queue
    print("\n6. Getting objects from the queue...")

    retrieved_count = 0
    while service.size(queue_id) > 0:
        obj = service.get(queue_id, blocking=False)
        retrieved_count += 1
        print(f"   [{retrieved_count}] Got: {obj}")

        # Verify it matches original
        assert obj == objects_to_put[retrieved_count - 1], "Object mismatch!"

    print(f"   [OK] Retrieved all {retrieved_count} objects")

    # 7. Try to get from empty queue
    print("\n7. Getting from empty queue (non-blocking)...")
    obj = service.get(queue_id, blocking=False)
    print(f"   [OK] Result: {obj} (None means empty)")

    # 8. List all queues
    print("\n8. Listing all queues...")
    all_queues = service.list_queues()
    print(f"   [OK] Found {len(all_queues)} queue(s): {all_queues}")

    # 9. Get stats
    print("\n9. Getting queue statistics...")
    stats = service.get_stats(queue_id)
    print(f"   [OK] Stats for '{queue_id}': {stats}")

    stats_all = service.get_stats()
    print(f"   [OK] Stats for all queues: {stats_all}")

    # 10. Test auto-create on put
    print("\n10. Testing auto-create on put...")
    auto_queue = 'auto_created_queue'
    service.put(auto_queue, "This queue was auto-created!")
    print(f"   [OK] Queue '{auto_queue}' auto-created on put")
    print(f"   [OK] Exists: {service.exists(auto_queue)}")
    obj = service.get(auto_queue, blocking=False)
    print(f"   [OK] Retrieved: {obj}")

    # 11. Test clear operation
    print("\n11. Testing clear operation...")
    test_queue = 'test_clear_queue'
    for i in range(5):
        service.put(test_queue, f"item_{i}")
    print(f"   [OK] Put 5 items, size: {service.size(test_queue)}")
    cleared = service.clear(test_queue)
    print(f"   [OK] Cleared {cleared} items, size now: {service.size(test_queue)}")

    # 12. Clean up
    print("\n12. Cleaning up...")
    service.delete(queue_id)
    service.delete(auto_queue)
    service.delete(test_queue)
    print(f"   [OK] Queues deleted")

    # 13. Close connection
    print("\n13. Closing service...")
    service.close()
    print(f"   [OK] Service closed")

    print("\n" + "="*80)
    print("[OK] Example completed successfully!")
    print("="*80 + "\n")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n[X] Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
