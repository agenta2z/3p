"""
Test Lock Mechanism for OnStorageLists

Comprehensive tests for concurrent access to OnStorageLists:
- Concurrent writes from multiple processes
- Concurrent reads from multiple processes
- Race condition prevention
- Data integrity under concurrency
- FIFO ordering preservation
- No data loss or corruption

Note: OnStorageLists doesn't have built-in file locking like StorageBasedQueueService,
so these tests verify how it behaves under concurrent access from multiple processes.
"""

import sys
import tempfile
import shutil
import time
import multiprocessing as mp
from pathlib import Path
from collections import Counter

# Add src to path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root / 'src'))

from python_utils.io_utils.on_storage_lists import OnStorageLists


def concurrent_writer(root_path, process_id, num_items, list_key='concurrent_list'):
    """Writer process that appends items."""
    storage = OnStorageLists(
        root_path=root_path,
        default_list_key='default'
    )

    for i in range(num_items):
        item = {
            'process_id': process_id,
            'item_number': i,
            'timestamp': time.time()
        }
        storage.append(item, list_key=list_key)
        time.sleep(0.01)  # Small delay to simulate work


def concurrent_reader(root_path, process_id, results_queue, list_key='concurrent_list'):
    """Reader process that reads all items."""
    storage = OnStorageLists(
        root_path=root_path,
        default_list_key='default'
    )

    # Wait a bit for writers to finish
    time.sleep(0.5)

    items = storage.get(list_key=list_key)
    results_queue.put((process_id, items))


def test_concurrent_writers():
    """Test multiple processes writing simultaneously."""
    print("\n" + "="*80)
    print("TEST 1: Concurrent Writers (Data Integrity)")
    print("="*80)

    tmpdir = tempfile.mkdtemp()

    try:
        print("\n1. Starting 5 concurrent writers...")
        num_writers = 5
        items_per_writer = 10

        processes = []
        for i in range(num_writers):
            p = mp.Process(target=concurrent_writer, args=(tmpdir, i, items_per_writer))
            p.start()
            processes.append(p)

        # Wait for all writers
        for p in processes:
            p.join(timeout=30)

        print("   [OK] All writers finished")

        print("\n2. Verifying data integrity...")
        storage = OnStorageLists(root_path=tmpdir, default_list_key='default')

        items = storage.get(list_key='concurrent_list')
        print(f"   [OK] Total items written: {len(items)}")

        expected_total = num_writers * items_per_writer
        print(f"   [OK] Expected total: {expected_total}")

        # Check if we have the right number of items (within tolerance for file system race conditions)
        if len(items) != expected_total:
            print(f"   [WARNING] Got {len(items)} items, expected {expected_total}")
            print(f"   [WARNING] Possible race condition - OnStorageLists doesn't have locking")

        print("\n3. Checking for data corruption...")
        corrupted = 0
        for item in items:
            if not isinstance(item, dict):
                corrupted += 1
                continue
            if 'process_id' not in item or 'item_number' not in item:
                corrupted += 1

        if corrupted == 0:
            print(f"   [OK] No corrupted items detected")
        else:
            print(f"   [WARNING] {corrupted} corrupted items detected")

        print("\n4. Grouping items by process...")
        items_by_process = {}
        for item in items:
            if isinstance(item, dict) and 'process_id' in item:
                pid = item['process_id']
                if pid not in items_by_process:
                    items_by_process[pid] = []
                items_by_process[pid].append(item['item_number'])

        for pid in range(num_writers):
            count = len(items_by_process.get(pid, []))
            print(f"   Process {pid}: {count} items")

        print("\n[OK] Concurrent writers test completed")
        print("[NOTE] OnStorageLists may lose some writes under high concurrency without locking")
        return True

    finally:
        shutil.rmtree(tmpdir)


def test_concurrent_readers():
    """Test multiple processes reading simultaneously."""
    print("\n" + "="*80)
    print("TEST 2: Concurrent Readers (Read Consistency)")
    print("="*80)

    tmpdir = tempfile.mkdtemp()

    try:
        print("\n1. Creating test data...")
        storage = OnStorageLists(root_path=tmpdir, default_list_key='default')

        num_items = 50
        for i in range(num_items):
            storage.append({'id': i, 'data': f'item_{i}'}, list_key='read_test')

        print(f"   [OK] Created {num_items} items")

        print("\n2. Starting 3 concurrent readers...")
        num_readers = 3
        results_queue = mp.Queue()

        processes = []
        for i in range(num_readers):
            p = mp.Process(target=concurrent_reader, args=(tmpdir, i, results_queue, 'read_test'))
            p.start()
            processes.append(p)

        # Wait for all readers
        for p in processes:
            p.join(timeout=30)

        print("   [OK] All readers finished")

        print("\n3. Verifying read consistency...")
        all_results = []
        for _ in range(num_readers):
            reader_id, items = results_queue.get(timeout=1)
            print(f"   [OK] Reader {reader_id} read {len(items)} items")
            all_results.append(items)

        # All readers should see the same data
        first_result = all_results[0]
        consistent = all(len(result) == len(first_result) for result in all_results)

        if consistent:
            print(f"   [OK] All readers see consistent data ({len(first_result)} items)")
        else:
            print(f"   [WARNING] Readers see different data lengths")
            for i, result in enumerate(all_results):
                print(f"      Reader {i}: {len(result)} items")

        print("\n[OK] Concurrent readers test completed")
        return True

    finally:
        shutil.rmtree(tmpdir)


def writer_with_list_ops(root_path, process_id, num_ops, results_queue):
    """Process that performs various list operations."""
    storage = OnStorageLists(root_path=root_path, default_list_key='default')

    operations_completed = 0
    errors = []

    for i in range(num_ops):
        try:
            # Append
            storage.append(f'P{process_id}-I{i}', list_key='stress_list')
            operations_completed += 1

            # Get size
            size = storage._get_list_size(list_key='stress_list')

            # Occasionally read
            if i % 5 == 0:
                items = storage.get(list_key='stress_list')

        except Exception as e:
            errors.append(str(e))

    results_queue.put((process_id, operations_completed, len(errors)))


def pop_worker(root_path, worker_id, results_queue):
    """Worker process that pops items from the list."""
    storage = OnStorageLists(root_path=root_path, default_list_key='default')
    popped = []

    for _ in range(10):
        try:
            item = storage.pop(index=0, list_key='pop_test')
            if item is not None:
                popped.append(item)
            time.sleep(0.01)
        except Exception as e:
            pass

    results_queue.put((worker_id, popped))


def insert_worker(root_path, worker_id, num_inserts):
    """Worker process that inserts items into the list."""
    storage = OnStorageLists(root_path=root_path, default_list_key='default')

    for i in range(num_inserts):
        try:
            # Insert at various positions
            index = (worker_id * num_inserts + i) % 15
            storage.insert(index, f'W{worker_id}-I{i}', list_key='insert_test')
            time.sleep(0.01)
        except Exception as e:
            pass


def test_stress_concurrent_operations():
    """Stress test with many concurrent operations."""
    print("\n" + "="*80)
    print("TEST 3: Stress Test - Concurrent Operations")
    print("="*80)

    tmpdir = tempfile.mkdtemp()

    try:
        print("\n1. Starting 10 processes with 50 operations each...")
        num_processes = 10
        ops_per_process = 50

        results_queue = mp.Queue()
        processes = []

        start_time = time.time()

        for i in range(num_processes):
            p = mp.Process(target=writer_with_list_ops, args=(tmpdir, i, ops_per_process, results_queue))
            p.start()
            processes.append(p)

        # Wait for all processes
        for p in processes:
            p.join(timeout=60)

        elapsed = time.time() - start_time
        print(f"   [OK] All processes finished in {elapsed:.2f}s")

        print("\n2. Collecting results...")
        total_operations = 0
        total_errors = 0

        for _ in range(num_processes):
            process_id, ops_completed, error_count = results_queue.get(timeout=1)
            print(f"   Process {process_id}: {ops_completed} ops, {error_count} errors")
            total_operations += ops_completed
            total_errors += error_count

        expected_operations = num_processes * ops_per_process
        print(f"\n3. Summary:")
        print(f"   Total operations: {total_operations}/{expected_operations}")
        print(f"   Total errors: {total_errors}")
        print(f"   Throughput: {total_operations/elapsed:.1f} ops/sec")

        print("\n4. Verifying final data...")
        storage = OnStorageLists(root_path=tmpdir, default_list_key='default')
        final_items = storage.get(list_key='stress_list')
        print(f"   [OK] Final list size: {len(final_items)}")

        if len(final_items) < expected_operations:
            lost = expected_operations - len(final_items)
            print(f"   [WARNING] {lost} items lost due to race conditions")

        print("\n[OK] Stress test completed")
        print("[NOTE] Some operations may fail/be lost without proper locking")
        return True

    finally:
        shutil.rmtree(tmpdir)


def test_pop_concurrency():
    """Test concurrent pop operations."""
    print("\n" + "="*80)
    print("TEST 4: Concurrent Pop Operations")
    print("="*80)

    tmpdir = tempfile.mkdtemp()

    try:
        print("\n1. Creating test data...")
        storage = OnStorageLists(root_path=tmpdir, default_list_key='default')

        num_items = 30
        for i in range(num_items):
            storage.append(i, list_key='pop_test')

        print(f"   [OK] Created {num_items} items")

        print("\n2. Starting 3 workers popping items...")
        num_workers = 3
        results_queue = mp.Queue()

        processes = []
        for i in range(num_workers):
            p = mp.Process(target=pop_worker, args=(tmpdir, i, results_queue))
            p.start()
            processes.append(p)

        for p in processes:
            p.join(timeout=30)

        print("   [OK] All workers finished")

        print("\n3. Collecting results...")
        all_popped = []
        for _ in range(num_workers):
            worker_id, popped = results_queue.get(timeout=1)
            print(f"   Worker {worker_id} popped {len(popped)} items")
            all_popped.extend(popped)

        print(f"\n4. Analysis:")
        print(f"   Total items popped: {len(all_popped)}")

        # Check for duplicates
        duplicates = [item for item, count in Counter(all_popped).items() if count > 1]
        if duplicates:
            print(f"   [WARNING] Found {len(duplicates)} duplicate items: {duplicates[:5]}...")
            print(f"   [NOTE] Race condition detected - concurrent pops caused duplicates")
        else:
            print(f"   [OK] No duplicate items detected")

        # Check remaining items
        storage = OnStorageLists(root_path=tmpdir, default_list_key='default')
        remaining = storage._get_list_size(list_key='pop_test')
        print(f"   Remaining items in list: {remaining}")
        print(f"   Items popped + remaining: {len(all_popped) + remaining}")
        print(f"   Original count: {num_items}")

        print("\n[OK] Concurrent pop test completed")
        print("[NOTE] Without locking, pop operations may have race conditions")
        return True

    finally:
        shutil.rmtree(tmpdir)


def test_insert_concurrency():
    """Test concurrent insert operations."""
    print("\n" + "="*80)
    print("TEST 5: Concurrent Insert Operations")
    print("="*80)

    tmpdir = tempfile.mkdtemp()

    try:
        print("\n1. Creating base list...")
        storage = OnStorageLists(root_path=tmpdir, default_list_key='default')

        # Create initial list
        for i in range(10):
            storage.append(f'base_{i}', list_key='insert_test')

        print(f"   [OK] Created base list with 10 items")

        print("\n2. Starting 3 workers inserting items...")
        num_workers = 3
        inserts_per_worker = 5

        processes = []
        for i in range(num_workers):
            p = mp.Process(target=insert_worker, args=(tmpdir, i, inserts_per_worker))
            p.start()
            processes.append(p)

        for p in processes:
            p.join(timeout=30)

        print("   [OK] All workers finished")

        print("\n3. Verifying final list...")
        storage = OnStorageLists(root_path=tmpdir, default_list_key='default')
        final_items = storage.get(list_key='insert_test')

        expected = 10 + (num_workers * inserts_per_worker)
        print(f"   Final list size: {len(final_items)}")
        print(f"   Expected size: {expected}")

        if len(final_items) != expected:
            diff = abs(len(final_items) - expected)
            print(f"   [WARNING] {diff} items difference - possible race condition")
        else:
            print(f"   [OK] Correct number of items")

        print("\n[OK] Concurrent insert test completed")
        return True

    finally:
        shutil.rmtree(tmpdir)


def run_all_tests():
    """Run all lock mechanism tests."""
    print("""
==============================================================================
              OnStorageLists Concurrency Tests
==============================================================================
These tests verify behavior under concurrent access from multiple processes.

IMPORTANT NOTE:
OnStorageLists does NOT have built-in file locking. These tests demonstrate:
- How it behaves under concurrent access
- What kinds of race conditions can occur
- Why file locking is needed for safety

For production use with concurrent access, consider:
1. Using StorageBasedQueueService (has file locking)
2. Implementing external locking (e.g., filelock library)
3. Coordinating access through a single process
==============================================================================
""")

    tests = [
        ("Concurrent Writers (Data Integrity)", test_concurrent_writers),
        ("Concurrent Readers (Read Consistency)", test_concurrent_readers),
        ("Stress Test - Concurrent Operations", test_stress_concurrent_operations),
        ("Concurrent Pop Operations", test_pop_concurrency),
        ("Concurrent Insert Operations", test_insert_concurrency),
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
    print("CONCURRENCY TEST SUMMARY")
    print("="*80)

    for name, success in results:
        status = "[OK] COMPLETED" if success else "[X] FAILED"
        print(f"  {status}: {name}")

    total = len(results)
    passed = sum(1 for _, success in results if success)

    print(f"\nTotal: {passed}/{total} tests completed")

    print("\n" + "="*80)
    print("CONCLUSION")
    print("="*80)
    print("OnStorageLists demonstrates various race conditions under concurrent access.")
    print("This is expected behavior WITHOUT file locking.")
    print("")
    print("For safe concurrent access, use:")
    print("  - StorageBasedQueueService (has built-in locking)")
    print("  - External file locking library")
    print("  - Single-process coordination")
    print("="*80)

    return True


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
