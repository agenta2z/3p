"""
Validation Test for Inter-Process Communication

This test specifically validates whether queues are actually shared across processes.
We'll count the exact number of items produced and consumed to verify sharing.
"""

import sys
from pathlib import Path
import time
import multiprocessing as mp

# Add src to path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root / 'src'))

from python_utils.service_utils.queue_service.thread_queue_service import ThreadQueueService


def producer_with_count(queue_id: str, num_items: int, result_queue):
    """Producer that reports how many items it successfully produced."""
    service = ThreadQueueService()

    produced = 0
    for i in range(num_items):
        service.put(queue_id, f'item_{i}')
        produced += 1

    service.close()
    result_queue.put(('produced', produced))
    print(f"Producer: Successfully produced {produced} items")


def consumer_with_count(queue_id: str, timeout: float, result_queue):
    """Consumer that reports how many items it successfully consumed."""
    service = ThreadQueueService()

    consumed = 0
    start_time = time.time()

    while True:
        # Try to get an item
        item = service.get(queue_id, blocking=True, timeout=1.0)

        if item is not None:
            consumed += 1
            print(f"Consumer: Got item {consumed}: {item}")

        # Check if we should exit
        if time.time() - start_time > timeout:
            break

    service.close()
    result_queue.put(('consumed', consumed))
    print(f"Consumer: Successfully consumed {consumed} items")


def test_interprocess_sharing():
    """
    Critical test: Verify that items produced in one process can be consumed in another.

    Expected behavior:
    - Producer produces N items in its process
    - Consumer consumes N items in its process
    - If consumed == produced, then queues are truly shared
    - If consumed == 0, then queues are NOT shared (each process has its own)
    """
    print("\n" + "="*80)
    print("INTER-PROCESS QUEUE SHARING VALIDATION TEST")
    print("="*80)

    queue_id = 'validation_queue'
    num_items = 10

    # Use a simple multiprocessing Queue for results (this definitely works)
    result_queue = mp.Queue()

    print(f"\nTest setup:")
    print(f"  - Producer will produce {num_items} items in its process")
    print(f"  - Consumer will try to consume items in its process")
    print(f"  - We'll check if consumer gets the items\n")

    # Start consumer first (so it's ready to receive)
    consumer_proc = mp.Process(target=consumer_with_count, args=(queue_id, 8.0, result_queue))
    consumer_proc.start()

    # Give consumer time to start
    time.sleep(1)

    # Start producer
    producer_proc = mp.Process(target=producer_with_count, args=(queue_id, num_items, result_queue))
    producer_proc.start()

    # Wait for both to finish
    producer_proc.join()
    consumer_proc.join()

    # Collect results
    results = {}
    while not result_queue.empty():
        key, value = result_queue.get()
        results[key] = value

    produced = results.get('produced', 0)
    consumed = results.get('consumed', 0)

    print("\n" + "="*80)
    print("TEST RESULTS")
    print("="*80)
    print(f"Items produced: {produced}")
    print(f"Items consumed: {consumed}")
    print()

    if consumed == produced and consumed == num_items:
        print("[SUCCESS] Queues ARE shared across processes!")
        print("Inter-process communication is working correctly.")
        return True
    elif consumed == 0:
        print("[FAILED] Queues are NOT shared across processes!")
        print("Each process has its own Manager/queues (isolation issue).")
        print("\nExplanation: On Windows with 'spawn' method, each process gets")
        print("a fresh Python interpreter. The global _shared_manager in each")
        print("process is a different instance, so queues are not shared.")
        return False
    else:
        print(f"[PARTIAL] Consumer got {consumed}/{produced} items.")
        print("This suggests intermittent or timing issues.")
        return False


def test_single_process_control():
    """
    Control test: Verify that the queue service works correctly within a single process.
    This should always work.
    """
    print("\n" + "="*80)
    print("SINGLE-PROCESS CONTROL TEST")
    print("="*80)

    service = ThreadQueueService()
    queue_id = 'control_queue'

    # Produce items
    num_items = 10
    for i in range(num_items):
        service.put(queue_id, f'item_{i}')

    print(f"\nProduced {num_items} items in same process")

    # Consume items
    consumed = 0
    while True:
        item = service.get(queue_id, blocking=False)
        if item is None:
            break
        consumed += 1

    print(f"Consumed {consumed} items in same process")

    service.close()

    print("\n" + "="*80)
    print("CONTROL TEST RESULTS")
    print("="*80)

    if consumed == num_items:
        print(f"[SUCCESS] Single-process queue works correctly ({consumed}/{num_items})")
        return True
    else:
        print(f"[FAILED] Single-process queue failed ({consumed}/{num_items})")
        return False


if __name__ == '__main__':
    # Set up multiprocessing for Windows
    if sys.platform == 'win32':
        mp.set_start_method('spawn', force=True)

    print("""
================================================================================
    ThreadQueueService Inter-Process Validation
================================================================================

This test validates whether the ThreadQueueService truly supports
inter-process communication, or if each process has its own isolated queues.

""")

    # Run control test first
    control_passed = test_single_process_control()

    # Run the critical inter-process test
    interprocess_passed = test_interprocess_sharing()

    print("\n" + "="*80)
    print("FINAL SUMMARY")
    print("="*80)
    print(f"Single-process test: {'PASS' if control_passed else 'FAIL'}")
    print(f"Inter-process test:  {'PASS' if interprocess_passed else 'FAIL'}")
    print()

    if control_passed and not interprocess_passed:
        print("CONCLUSION:")
        print("ThreadQueueService works for single-process scenarios but")
        print("does NOT support true inter-process communication on this platform.")
        print("\nRECOMMENDATION: Use RedisQueueService for inter-process communication.")
    elif control_passed and interprocess_passed:
        print("CONCLUSION:")
        print("ThreadQueueService works for both single-process and")
        print("inter-process scenarios on this platform.")
    else:
        print("CONCLUSION:")
        print("ThreadQueueService has fundamental issues.")

    print("="*80 + "\n")

    sys.exit(0 if (control_passed and interprocess_passed) else 1)
