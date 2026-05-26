"""
Test Threading pattern with ThreadQueueService

This demonstrates how multiple threads can use the queue service
for inter-thread communication. ThreadQueueService works
well with threads since they share the same memory space.

Tests:
- Multiple producer threads putting items
- Multiple consumer threads getting items
- Thread-safe operations

Prerequisites:
    No external dependencies (uses standard library)

Usage:
    python test_threading.py
"""

import sys
from pathlib import Path
import time
import threading
from datetime import datetime

# Add src to path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root / 'src'))

from python_utils.service_utils.queue_service.thread_queue_service import ThreadQueueService


def producer(service: ThreadQueueService, producer_id: int, queue_id: str, num_items: int, delay: float = 0.1):
    """
    Producer thread that puts items onto queue.

    Args:
        service: Shared service instance
        producer_id: Unique producer identifier
        queue_id: Queue to produce into
        num_items: Number of items to produce
        delay: Delay between items (seconds)
    """
    print(f"[Producer {producer_id}] Started, will produce {num_items} items")

    for i in range(num_items):
        item = {
            'producer_id': producer_id,
            'item_number': i,
            'timestamp': datetime.now().isoformat(),
            'message': f'Item {i} from producer {producer_id}'
        }

        service.put(queue_id, item)
        print(f"[Producer {producer_id}] Put item {i}: {item['message']}")

        time.sleep(delay)

    print(f"[Producer {producer_id}] Finished producing {num_items} items")


def consumer(service: ThreadQueueService, consumer_id: int, queue_id: str, timeout: float = 5.0):
    """
    Consumer thread that gets items from queue.

    Args:
        service: Shared service instance
        consumer_id: Unique consumer identifier
        queue_id: Queue to consume from
        timeout: Timeout for blocking get (seconds)
    """
    print(f"[Consumer {consumer_id}] Started, waiting for items...")

    consumed_count = 0
    last_empty_time = None

    while True:
        # Blocking get with timeout
        item = service.get(queue_id, blocking=True, timeout=2.0)

        if item is None:
            # No item available
            if last_empty_time is None:
                last_empty_time = time.time()
            elif time.time() - last_empty_time > timeout:
                # No items for timeout duration, exit
                break
        else:
            # Got an item
            consumed_count += 1
            last_empty_time = None  # Reset timeout
            print(f"[Consumer {consumer_id}] Got item {consumed_count}: {item['message']}")

    print(f"[Consumer {consumer_id}] Finished consuming {consumed_count} items")


def test_single_producer_single_consumer():
    """Test with 1 producer and 1 consumer thread."""
    print("\n" + "="*80)
    print("TEST 1: Single Producer, Single Consumer (Threads)")
    print("="*80)

    service = ThreadQueueService()
    queue_id = 'test_thread_queue_1'
    num_items = 10

    # Clean up queue first
    service.delete(queue_id)

    print(f"\nStarting 1 producer thread (will produce {num_items} items)...")
    print(f"Starting 1 consumer thread (will consume until timeout)...\n")

    # Start producer and consumer threads
    producer_thread = threading.Thread(target=producer, args=(service, 1, queue_id, num_items, 0.2))
    consumer_thread = threading.Thread(target=consumer, args=(service, 1, queue_id, 3.0))

    consumer_thread.start()
    time.sleep(0.5)  # Let consumer start first
    producer_thread.start()

    # Wait for completion
    producer_thread.join()
    consumer_thread.join()

    print(f"\n[OK] Test completed")

    # Clean up
    service.delete(queue_id)
    service.close()
    return True


def test_multiple_producers_single_consumer():
    """Test with multiple producer threads and 1 consumer thread."""
    print("\n" + "="*80)
    print("TEST 2: Multiple Producers, Single Consumer (Threads)")
    print("="*80)

    service = ThreadQueueService()
    queue_id = 'test_thread_queue_2'
    num_producers = 3
    items_per_producer = 5

    # Clean up queue first
    service.delete(queue_id)

    print(f"\nStarting {num_producers} producer threads ({items_per_producer} items each)...")
    print(f"Starting 1 consumer thread...\n")

    # Start consumer
    consumer_thread = threading.Thread(target=consumer, args=(service, 1, queue_id, 3.0))
    consumer_thread.start()
    time.sleep(0.5)

    # Start multiple producers
    producer_threads = []
    for i in range(num_producers):
        thread = threading.Thread(target=producer, args=(service, i+1, queue_id, items_per_producer, 0.15))
        thread.start()
        producer_threads.append(thread)

    # Wait for all producers to finish
    for thread in producer_threads:
        thread.join()

    # Wait for consumer
    consumer_thread.join()

    print(f"\n[OK] Test completed")

    # Clean up
    service.delete(queue_id)
    service.close()
    return True


def test_single_producer_multiple_consumers():
    """Test with 1 producer thread and multiple consumer threads."""
    print("\n" + "="*80)
    print("TEST 3: Single Producer, Multiple Consumers (Threads)")
    print("="*80)

    service = ThreadQueueService()
    queue_id = 'test_thread_queue_3'
    num_consumers = 3
    num_items = 15

    # Clean up queue first
    service.delete(queue_id)

    print(f"\nStarting {num_consumers} consumer threads...")
    print(f"Starting 1 producer thread ({num_items} items)...\n")

    # Start consumers
    consumer_threads = []
    for i in range(num_consumers):
        thread = threading.Thread(target=consumer, args=(service, i+1, queue_id, 3.0))
        thread.start()
        consumer_threads.append(thread)
        time.sleep(0.1)

    # Start producer
    producer_thread = threading.Thread(target=producer, args=(service, 1, queue_id, num_items, 0.1))
    producer_thread.start()

    # Wait for producer
    producer_thread.join()

    # Wait for all consumers
    for thread in consumer_threads:
        thread.join()

    print(f"\n[OK] Test completed")

    # Clean up
    service.delete(queue_id)
    service.close()
    return True


def test_multiple_producers_multiple_consumers():
    """Test with multiple producer threads and multiple consumer threads."""
    print("\n" + "="*80)
    print("TEST 4: Multiple Producers, Multiple Consumers (Threads)")
    print("="*80)

    service = ThreadQueueService()
    queue_id = 'test_thread_queue_4'
    num_producers = 3
    num_consumers = 2
    items_per_producer = 5

    # Clean up queue first
    service.delete(queue_id)

    print(f"\nStarting {num_consumers} consumer threads...")
    print(f"Starting {num_producers} producer threads ({items_per_producer} items each)...\n")

    # Start consumers
    consumer_threads = []
    for i in range(num_consumers):
        thread = threading.Thread(target=consumer, args=(service, i+1, queue_id, 3.0))
        thread.start()
        consumer_threads.append(thread)
        time.sleep(0.1)

    # Start producers
    producer_threads = []
    for i in range(num_producers):
        thread = threading.Thread(target=producer, args=(service, i+1, queue_id, items_per_producer, 0.1))
        thread.start()
        producer_threads.append(thread)

    # Wait for all producers
    for thread in producer_threads:
        thread.join()

    # Wait for all consumers
    for thread in consumer_threads:
        thread.join()

    print(f"\n[OK] Test completed")

    # Clean up
    service.delete(queue_id)
    service.close()
    return True


def run_all_tests():
    """Run all threading tests."""
    print("""
==============================================================================
        ThreadQueueService Threading Tests                       
==============================================================================

This demonstrates how ThreadQueueService enables inter-thread
communication using the producer-consumer pattern with threads.

Note: ThreadQueueService works well with threads since they share
the same memory space and service instance. For true multi-process scenarios,
consider using RedisQueueService.
""")

    tests = [
        ("1 Producer, 1 Consumer", test_single_producer_single_consumer),
        ("Multiple Producers, 1 Consumer", test_multiple_producers_single_consumer),
        ("1 Producer, Multiple Consumers", test_single_producer_multiple_consumers),
        ("Multiple Producers, Multiple Consumers", test_multiple_producers_multiple_consumers),
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
