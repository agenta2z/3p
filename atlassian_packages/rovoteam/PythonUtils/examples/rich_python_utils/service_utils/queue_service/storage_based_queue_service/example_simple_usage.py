"""
Simple usage example of StorageBasedQueueService

This demonstrates the most common operations:
- Creating a storage-based queue service
- Putting and getting items
- Blocking and non-blocking operations
- Queue management
- Multiprocessing support

Prerequisites:
    No external dependencies (uses standard library)

Usage:
    python example_simple_usage.py
"""

from pathlib import Path
import tempfile
import shutil
import time

from resolve_path import resolve_path
resolve_path()  # Add project src to sys.path

from python_utils.service_utils.queue_service.storage_based_queue_service import (
    StorageBasedQueueService
)


def main():
    print("""
==============================================================================
            StorageBasedQueueService Simple Usage Example
==============================================================================
""")

    # Create a temporary directory for this demo
    tmpdir = tempfile.mkdtemp()
    print(f"Using temporary storage: {tmpdir}")

    try:
        # 1. Basic Setup - Create StorageBasedQueueService instance
        print("\n1. Creating StorageBasedQueueService instance...")
        service = StorageBasedQueueService(root_path=tmpdir)
        print(f"   [OK] Service initialized: {service}")

        # 2. Put items into a queue
        print("\n2. Putting items into queue...")
        tasks = [
            {'task_id': 1, 'action': 'process_data', 'file': 'data1.csv'},
            {'task_id': 2, 'action': 'send_email', 'to': 'user@example.com'},
            {'task_id': 3, 'action': 'generate_report', 'format': 'pdf'},
        ]

        for task in tasks:
            service.put('task_queue', task)
            print(f"   [+] Queued: {task}")

        # 3. Check queue size
        print("\n3. Checking queue size...")
        size = service.size('task_queue')
        print(f"   [OK] Queue size: {size}")

        # 4. Get items from queue (FIFO)
        print("\n4. Getting items from queue (FIFO)...")
        item1 = service.get('task_queue', blocking=False)
        print(f"   [>] Got: {item1}")

        item2 = service.get('task_queue', blocking=False)
        print(f"   [>] Got: {item2}")

        size = service.size('task_queue')
        print(f"   [OK] Queue size after 2 gets: {size}")

        # 5. Peek at next item without removing it
        print("\n5. Peeking at next item...")
        next_item = service.peek('task_queue', index=0)
        print(f"   [*] Peeked: {next_item}")

        size = service.size('task_queue')
        print(f"   [OK] Queue size after peek: {size} (unchanged)")

        # 6. Clear the queue
        print("\n6. Clearing the queue...")
        cleared = service.clear('task_queue')
        print(f"   [OK] Cleared {cleared} items")

        size = service.size('task_queue')
        print(f"   [OK] Queue size after clear: {size}")

        # 7. Test blocking operations
        print("\n7. Testing blocking operations...")
        print("   Testing non-blocking get on empty queue...")
        start = time.time()
        item = service.get('task_queue', blocking=False)
        elapsed = time.time() - start
        print(f"   [OK] Non-blocking get returned: {item} in {elapsed:.3f}s")

        print("   Testing blocking get with timeout...")
        start = time.time()
        item = service.get('task_queue', blocking=True, timeout=0.5)
        elapsed = time.time() - start
        print(f"   [OK] Blocking get with timeout returned: {item} in {elapsed:.3f}s")

        # 8. Multiple queues
        print("\n8. Working with multiple queues...")
        service.put('queue_a', 'data_a1')
        service.put('queue_a', 'data_a2')
        service.put('queue_b', 'data_b1')
        service.put('queue_b', 'data_b2')
        service.put('queue_b', 'data_b3')

        queues = service.list_queues()
        print(f"   [OK] All queues: {queues}")

        for queue_id in queues:
            size = service.size(queue_id)
            print(f"   - {queue_id}: {size} items")

        # 9. Get statistics
        print("\n9. Getting queue statistics...")
        stats = service.get_stats()
        print(f"   [OK] Total queues: {stats['total_queues']}")
        for queue_id, queue_stats in stats['queues'].items():
            print(f"   - {queue_id}: {queue_stats}")

        # 10. Test persistence
        print("\n10. Testing persistence...")
        service.put('persistent_queue', {'data': 'important'})
        print("   [OK] Added item to persistent_queue")
        service.close()
        print("   [OK] Closed service")

        print("   Creating new service instance...")
        service2 = StorageBasedQueueService(root_path=tmpdir)
        size = service2.size('persistent_queue')
        print(f"   [OK] New instance sees queue size: {size}")

        item = service2.get('persistent_queue', blocking=False)
        print(f"   [OK] Retrieved persisted item: {item}")
        service2.close()

        # 11. Context manager usage
        print("\n11. Using context manager...")
        with StorageBasedQueueService(root_path=tmpdir) as service3:
            service3.put('context_queue', 'item1')
            service3.put('context_queue', 'item2')
            size = service3.size('context_queue')
            print(f"   [OK] Added items, size: {size}")
        print("   [OK] Context manager automatically closed service")

        print("\n" + "="*80)
        print("[OK] Example completed successfully!")
        print("="*80 + "\n")

    finally:
        # Clean up temporary directory
        print(f"\nCleaning up temporary directory: {tmpdir}")
        time.sleep(0.1)  # Small delay to ensure file handles are released
        try:
            shutil.rmtree(tmpdir)
            print("[OK] Cleanup complete")
        except Exception as e:
            print(f"[!] Cleanup warning: {e}")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n[X] Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
