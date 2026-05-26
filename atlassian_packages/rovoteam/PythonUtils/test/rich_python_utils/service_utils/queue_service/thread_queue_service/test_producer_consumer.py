"""
Test Producer-Consumer pattern with ThreadQueueService

Tests true inter-process communication using a shared multiprocessing.Manager.
This validates that multiple processes can safely produce and consume items
from the same queues.

Tests:
- Single producer and single consumer across processes
- Multiple producers and single consumer
- Single producer and multiple consumers
- Multiple producers and multiple consumers

Prerequisites:
    No external dependencies (uses standard library)

Usage:
    python test_producer_consumer.py
"""

import sys
from pathlib import Path
import time
import multiprocessing as mp
from datetime import datetime

# Add src to path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root / 'src'))

from python_utils.service_utils.queue_service.thread_queue_service import ThreadQueueService


def producer(producer_id: int, queue_id: str, num_items: int, delay: float = 0.1):
    """
    Producer process that puts items onto queue.

    Args:
        producer_id: Unique producer identifier
        queue_id: Queue to produce into
        num_items: Number of items to produce
        delay: Delay between items (seconds)
    """
    service = ThreadQueueService()

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
    service.close()


def consumer(consumer_id: int, queue_id: str, timeout: float = 5.0):
    """
    Consumer process that gets items from queue.

    Args:
        consumer_id: Unique consumer identifier
        queue_id: Queue to consume from
        timeout: Timeout for blocking get (seconds)
    """
    service = ThreadQueueService()

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
    service.close()


def test_single_producer_single_consumer():
    """Test with 1 producer and 1 consumer."""
    print("\n" + "="*80)
    print("TEST 1: Single Producer, Single Consumer")
    print("="*80)

    queue_id = 'test_pc_queue_1'
    num_items = 10

    # Clean up queue first
    service = ThreadQueueService()
    service.delete(queue_id)
    service.close()

    print(f"\nStarting 1 producer (will produce {num_items} items)...")
    print(f"Starting 1 consumer (will consume until timeout)...\n")

    # Start producer and consumer processes
    producer_proc = mp.Process(target=producer, args=(1, queue_id, num_items, 0.2))
    consumer_proc = mp.Process(target=consumer, args=(1, queue_id, 3.0))

    consumer_proc.start()
    time.sleep(0.5)  # Let consumer start first
    producer_proc.start()

    # Wait for completion
    producer_proc.join()
    consumer_proc.join()

    print(f"\n[OK] Test completed")

    # Clean up
    service = ThreadQueueService()
    service.delete(queue_id)
    service.close()
    return True


def test_multiple_producers_single_consumer():
    """Test with multiple producers and 1 consumer."""
    print("\n" + "="*80)
    print("TEST 2: Multiple Producers, Single Consumer")
    print("="*80)

    queue_id = 'test_pc_queue_2'
    num_producers = 3
    items_per_producer = 5

    # Clean up queue first
    service = ThreadQueueService()
    service.delete(queue_id)
    service.close()

    print(f"\nStarting {num_producers} producers ({items_per_producer} items each)...")
    print(f"Starting 1 consumer...\n")

    # Start consumer
    consumer_proc = mp.Process(target=consumer, args=(1, queue_id, 3.0))
    consumer_proc.start()
    time.sleep(0.5)

    # Start multiple producers
    producer_procs = []
    for i in range(num_producers):
        proc = mp.Process(target=producer, args=(i+1, queue_id, items_per_producer, 0.15))
        proc.start()
        producer_procs.append(proc)

    # Wait for all producers to finish
    for proc in producer_procs:
        proc.join()

    # Wait for consumer
    consumer_proc.join()

    print(f"\n[OK] Test completed")

    # Clean up
    service = ThreadQueueService()
    service.delete(queue_id)
    service.close()
    return True


def test_single_producer_multiple_consumers():
    """Test with 1 producer and multiple consumers."""
    print("\n" + "="*80)
    print("TEST 3: Single Producer, Multiple Consumers")
    print("="*80)

    queue_id = 'test_pc_queue_3'
    num_consumers = 3
    num_items = 15

    # Clean up queue first
    service = ThreadQueueService()
    service.delete(queue_id)
    service.close()

    print(f"\nStarting {num_consumers} consumers...")
    print(f"Starting 1 producer ({num_items} items)...\n")

    # Start consumers
    consumer_procs = []
    for i in range(num_consumers):
        proc = mp.Process(target=consumer, args=(i+1, queue_id, 3.0))
        proc.start()
        consumer_procs.append(proc)
        time.sleep(0.1)

    # Start producer
    producer_proc = mp.Process(target=producer, args=(1, queue_id, num_items, 0.1))
    producer_proc.start()

    # Wait for producer
    producer_proc.join()

    # Wait for all consumers
    for proc in consumer_procs:
        proc.join()

    print(f"\n[OK] Test completed")

    # Clean up
    service = ThreadQueueService()
    service.delete(queue_id)
    service.close()
    return True


def test_multiple_producers_multiple_consumers():
    """Test with multiple producers and multiple consumers."""
    print("\n" + "="*80)
    print("TEST 4: Multiple Producers, Multiple Consumers")
    print("="*80)

    queue_id = 'test_pc_queue_4'
    num_producers = 3
    num_consumers = 2
    items_per_producer = 5

    # Clean up queue first
    service = ThreadQueueService()
    service.delete(queue_id)
    service.close()

    print(f"\nStarting {num_consumers} consumers...")
    print(f"Starting {num_producers} producers ({items_per_producer} items each)...\n")

    # Start consumers
    consumer_procs = []
    for i in range(num_consumers):
        proc = mp.Process(target=consumer, args=(i+1, queue_id, 3.0))
        proc.start()
        consumer_procs.append(proc)
        time.sleep(0.1)

    # Start producers
    producer_procs = []
    for i in range(num_producers):
        proc = mp.Process(target=producer, args=(i+1, queue_id, items_per_producer, 0.1))
        proc.start()
        producer_procs.append(proc)

    # Wait for all producers
    for proc in producer_procs:
        proc.join()

    # Wait for all consumers
    for proc in consumer_procs:
        proc.join()

    print(f"\n[OK] Test completed")

    # Clean up
    service = ThreadQueueService()
    service.delete(queue_id)
    service.close()
    return True


def run_all_tests():
    """Run all producer-consumer tests."""
    print("""
==============================================================================
        ThreadQueueService Producer-Consumer Tests                       
==============================================================================

This demonstrates how ThreadQueueService enables inter-process
communication using the producer-consumer pattern.
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
    # Multiprocessing setup for Windows
    if sys.platform == 'win32':
        mp.set_start_method('spawn', force=True)

    success = run_all_tests()
    sys.exit(0 if success else 1)
