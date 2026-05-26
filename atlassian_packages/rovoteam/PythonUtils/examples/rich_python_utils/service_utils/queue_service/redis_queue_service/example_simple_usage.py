"""
Simple usage example of RedisQueueService

This demonstrates the most common operations:
- Creating a queue
- Putting objects
- Getting objects
- Checking queue status

Prerequisites:
    1. Redis server running (docker run -d -p 6379:6379 redis)
    2. pip install redis

Usage:
    python example_simple_usage.py
"""

from resolve_path import resolve_path
resolve_path()  # Add project src to sys.path

from python_utils.service_utils.queue_service.redis_queue_service import RedisQueueService


def main():
    print("""
==============================================================================
                   RedisQueueService Simple Usage Example                    
==============================================================================
""")

    # 1. Create service instance
    print("1. Creating RedisQueueService...")
    service = RedisQueueService(host='localhost', port=6379)
    print(f"   [OK] Connected: {service}")

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
        "Hello, Redis Queue!",
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
    next_item = service.peek(queue_id, index=-1)
    print(f"   [OK] Next item: {next_item}")
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
    print(f"   [OK] Stats: {stats}")

    # 10. Clean up
    print("\n10. Cleaning up...")
    deleted = service.delete(queue_id)
    print(f"   [OK] Queue deleted: {deleted}")

    # 11. Close connection
    print("\n11. Closing connection...")
    service.close()
    print(f"   [OK] Connection closed")

    print("\n" + "="*80)
    print("[OK] Example completed successfully!")
    print("="*80 + "\n")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n[X] Error: {e}")
        print(f"\nMake sure Redis is running:")
        print(f"  Docker: docker run -d -p 6379:6379 redis")
        sys.exit(1)
