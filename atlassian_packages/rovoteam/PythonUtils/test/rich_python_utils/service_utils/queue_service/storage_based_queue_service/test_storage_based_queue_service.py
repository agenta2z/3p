"""
Test StorageBasedQueueService

Comprehensive tests for the storage-based queue service including:
- Basic operations (put, get, peek, size)
- Queue management (create, delete, clear, exists)
- Blocking and non-blocking operations
- Timeout handling
- Multiprocessing support
- Persistence across service instances
- Error handling
"""

import sys
import tempfile
import shutil
import time
import multiprocessing as mp
from pathlib import Path

# Add src to path
# From: test/python_utils/service_utils/queue_service/test_storage_based_queue_service.py
# To: src/
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root / 'src'))

from python_utils.service_utils.queue_service.storage_based_queue_service import (
    StorageBasedQueueService
)


def test_basic_operations():
    """Test basic put, get, and size operations."""
    print("\n" + "="*80)
    print("TEST 1: Basic Operations")
    print("="*80)
    
    tmpdir = tempfile.mkdtemp()
    
    try:
        service = StorageBasedQueueService(root_path=tmpdir)
        
        print("\n1. Testing put and get...")
        service.put('test_queue', {'id': 1, 'data': 'first'})
        service.put('test_queue', {'id': 2, 'data': 'second'})
        service.put('test_queue', {'id': 3, 'data': 'third'})
        print("   [OK] Put 3 items")
        
        size = service.size('test_queue')
        print(f"   [OK] Queue size: {size}")
        assert size == 3, f"Expected size 3, got {size}"
        
        item1 = service.get('test_queue', blocking=False)
        print(f"   [OK] Got item: {item1}")
        assert item1['id'] == 1, "Expected FIFO order"
        
        item2 = service.get('test_queue', blocking=False)
        print(f"   [OK] Got item: {item2}")
        assert item2['id'] == 2, "Expected FIFO order"
        
        size = service.size('test_queue')
        print(f"   [OK] Queue size after 2 gets: {size}")
        assert size == 1, f"Expected size 1, got {size}"
        
        service.close()
        print("\n[OK] Basic operations test passed")
        return True
        
    finally:
        shutil.rmtree(tmpdir)


def test_queue_management():
    """Test queue creation, deletion, and existence checks."""
    print("\n" + "="*80)
    print("TEST 2: Queue Management")
    print("="*80)
    
    tmpdir = tempfile.mkdtemp()
    
    try:
        service = StorageBasedQueueService(root_path=tmpdir)
        
        print("\n1. Testing queue creation...")
        created = service.create_queue('queue1')
        print(f"   [OK] Created queue1: {created}")
        assert created == True, "Should create new queue"
        
        created = service.create_queue('queue1')
        print(f"   [OK] Tried to create queue1 again: {created}")
        assert created == False, "Should not create duplicate queue"
        
        print("\n2. Testing queue existence...")
        exists = service.exists('queue1')
        print(f"   [OK] queue1 exists: {exists}")
        assert exists == True, "Queue should exist"
        
        exists = service.exists('nonexistent')
        print(f"   [OK] nonexistent queue exists: {exists}")
        assert exists == False, "Queue should not exist"
        
        print("\n3. Testing list queues...")
        service.create_queue('queue2')
        service.create_queue('queue3')
        queues = service.list_queues()
        print(f"   [OK] All queues: {queues}")
        assert len(queues) == 3, f"Expected 3 queues, got {len(queues)}"
        
        print("\n4. Testing queue deletion...")
        deleted = service.delete('queue2')
        print(f"   [OK] Deleted queue2: {deleted}")
        assert deleted == True, "Should delete existing queue"
        
        queues = service.list_queues()
        print(f"   [OK] Queues after deletion: {queues}")
        assert len(queues) == 2, f"Expected 2 queues, got {len(queues)}"
        
        service.close()
        print("\n[OK] Queue management test passed")
        return True
        
    finally:
        shutil.rmtree(tmpdir)


def test_peek_operation():
    """Test peek operation without removing items."""
    print("\n" + "="*80)
    print("TEST 3: Peek Operation")
    print("="*80)
    
    tmpdir = tempfile.mkdtemp()
    
    try:
        service = StorageBasedQueueService(root_path=tmpdir)
        
        print("\n1. Testing peek on empty queue...")
        item = service.peek('test_queue', index=0)
        print(f"   [OK] Peek on empty queue: {item}")
        assert item is None, "Should return None for empty queue"
        
        print("\n2. Adding items and testing peek...")
        service.put('test_queue', 'first')
        service.put('test_queue', 'second')
        service.put('test_queue', 'third')
        
        # Peek at front
        item = service.peek('test_queue', index=0)
        print(f"   [OK] Peek at index 0: {item}")
        assert item == 'first', "Should peek at front"
        
        # Peek at back
        item = service.peek('test_queue', index=-1)
        print(f"   [OK] Peek at index -1: {item}")
        assert item == 'third', "Should peek at back"
        
        # Verify size unchanged
        size = service.size('test_queue')
        print(f"   [OK] Size after peeks: {size}")
        assert size == 3, "Peek should not remove items"
        
        print("\n3. Testing peek with invalid index...")
        try:
            service.peek('test_queue', index=10)
            print("   [X] Should have raised IndexError")
            return False
        except IndexError as e:
            print(f"   [OK] Raised IndexError: {e}")
        
        service.close()
        print("\n[OK] Peek operation test passed")
        return True
        
    finally:
        shutil.rmtree(tmpdir)


def test_clear_operation():
    """Test clearing queue contents."""
    print("\n" + "="*80)
    print("TEST 4: Clear Operation")
    print("="*80)
    
    tmpdir = tempfile.mkdtemp()
    
    try:
        service = StorageBasedQueueService(root_path=tmpdir)
        
        print("\n1. Adding items to queue...")
        for i in range(5):
            service.put('test_queue', f'item_{i}')
        
        size = service.size('test_queue')
        print(f"   [OK] Queue size: {size}")
        assert size == 5, f"Expected size 5, got {size}"
        
        print("\n2. Clearing queue...")
        cleared = service.clear('test_queue')
        print(f"   [OK] Cleared {cleared} items")
        assert cleared == 5, f"Expected to clear 5 items, cleared {cleared}"
        
        size = service.size('test_queue')
        print(f"   [OK] Queue size after clear: {size}")
        assert size == 0, f"Expected size 0, got {size}"
        
        # Queue should still exist
        exists = service.exists('test_queue')
        print(f"   [OK] Queue still exists: {exists}")
        assert exists == True, "Queue should still exist after clear"
        
        service.close()
        print("\n[OK] Clear operation test passed")
        return True
        
    finally:
        shutil.rmtree(tmpdir)


def test_blocking_operations():
    """Test blocking get with timeout."""
    print("\n" + "="*80)
    print("TEST 5: Blocking Operations")
    print("="*80)
    
    tmpdir = tempfile.mkdtemp()
    
    try:
        service = StorageBasedQueueService(root_path=tmpdir)
        
        print("\n1. Testing non-blocking get on empty queue...")
        start = time.time()
        item = service.get('test_queue', blocking=False)
        elapsed = time.time() - start
        print(f"   [OK] Non-blocking get returned: {item} in {elapsed:.3f}s")
        assert item is None, "Should return None immediately"
        assert elapsed < 0.1, "Should be instant"
        
        print("\n2. Testing blocking get with timeout on empty queue...")
        start = time.time()
        item = service.get('test_queue', blocking=True, timeout=0.5)
        elapsed = time.time() - start
        print(f"   [OK] Blocking get with timeout returned: {item} in {elapsed:.3f}s")
        assert item is None, "Should return None after timeout"
        assert 0.4 < elapsed < 0.7, f"Should timeout around 0.5s, got {elapsed:.3f}s"
        
        print("\n3. Testing blocking get that succeeds...")
        service.put('test_queue', 'test_item')
        start = time.time()
        item = service.get('test_queue', blocking=True, timeout=1.0)
        elapsed = time.time() - start
        print(f"   [OK] Blocking get returned: {item} in {elapsed:.3f}s")
        assert item == 'test_item', "Should get the item"
        assert elapsed < 0.2, "Should return quickly when item available"
        
        service.close()
        print("\n[OK] Blocking operations test passed")
        return True
        
    finally:
        shutil.rmtree(tmpdir)


def test_persistence():
    """Test that queues persist across service instances."""
    print("\n" + "="*80)
    print("TEST 6: Persistence")
    print("="*80)
    
    tmpdir = tempfile.mkdtemp()
    
    try:
        print("\n1. Creating service and adding items...")
        service1 = StorageBasedQueueService(root_path=tmpdir)
        service1.put('persistent_queue', {'id': 1, 'data': 'first'})
        service1.put('persistent_queue', {'id': 2, 'data': 'second'})
        size1 = service1.size('persistent_queue')
        print(f"   [OK] Added 2 items, size: {size1}")
        service1.close()
        
        print("\n2. Creating new service instance...")
        service2 = StorageBasedQueueService(root_path=tmpdir)
        size2 = service2.size('persistent_queue')
        print(f"   [OK] New instance sees size: {size2}")
        assert size2 == 2, f"Expected size 2, got {size2}"
        
        item = service2.get('persistent_queue', blocking=False)
        print(f"   [OK] Retrieved item: {item}")
        assert item['id'] == 1, "Should get first item"
        
        size3 = service2.size('persistent_queue')
        print(f"   [OK] Size after get: {size3}")
        assert size3 == 1, f"Expected size 1, got {size3}"
        
        service2.close()
        print("\n[OK] Persistence test passed")
        return True
        
    finally:
        shutil.rmtree(tmpdir)


def producer_process(root_path, num_items):
    """Producer process for multiprocessing test."""
    service = StorageBasedQueueService(root_path=root_path)
    for i in range(num_items):
        service.put('mp_queue', {'id': i, 'data': f'item_{i}'})
        time.sleep(0.01)  # Small delay
    service.close()


def consumer_process(root_path, num_items, results_queue):
    """Consumer process for multiprocessing test."""
    service = StorageBasedQueueService(root_path=root_path)
    items = []
    for _ in range(num_items):
        item = service.get('mp_queue', blocking=True, timeout=5.0)
        if item is not None:
            items.append(item['id'])
    service.close()
    results_queue.put(items)


def test_multiprocessing():
    """Test true multiprocessing support."""
    print("\n" + "="*80)
    print("TEST 7: Multiprocessing Support")
    print("="*80)
    
    tmpdir = tempfile.mkdtemp()
    
    try:
        print("\n1. Starting producer and consumer processes...")
        num_items = 10
        results_queue = mp.Queue()
        
        producer = mp.Process(target=producer_process, args=(tmpdir, num_items))
        consumer = mp.Process(target=consumer_process, args=(tmpdir, num_items, results_queue))
        
        producer.start()
        consumer.start()
        
        producer.join(timeout=10)
        consumer.join(timeout=10)
        
        print("   [OK] Processes completed")
        
        print("\n2. Verifying results...")
        items = results_queue.get(timeout=1)
        print(f"   [OK] Consumer received {len(items)} items")
        print(f"   [OK] Item IDs: {items}")
        
        assert len(items) == num_items, f"Expected {num_items} items, got {len(items)}"
        assert items == list(range(num_items)), "Items should be in order"
        
        print("\n[OK] Multiprocessing test passed")
        return True
        
    finally:
        shutil.rmtree(tmpdir)


def test_stats_and_ping():
    """Test statistics and ping operations."""
    print("\n" + "="*80)
    print("TEST 8: Stats and Ping")
    print("="*80)
    
    tmpdir = tempfile.mkdtemp()
    
    try:
        service = StorageBasedQueueService(root_path=tmpdir)
        
        print("\n1. Testing ping...")
        responsive = service.ping()
        print(f"   [OK] Service responsive: {responsive}")
        assert responsive == True, "Service should be responsive"
        
        print("\n2. Creating queues and adding items...")
        service.put('queue1', 'item1')
        service.put('queue1', 'item2')
        service.put('queue2', 'item1')
        
        print("\n3. Testing stats for specific queue...")
        stats = service.get_stats('queue1')
        print(f"   [OK] Stats for queue1: {stats}")
        assert stats['size'] == 2, "queue1 should have 2 items"
        assert stats['exists'] == True, "queue1 should exist"
        
        print("\n4. Testing stats for all queues...")
        stats = service.get_stats()
        print(f"   [OK] All stats: {stats}")
        assert stats['total_queues'] == 2, "Should have 2 queues"
        assert 'queue1' in stats['queues'], "Should include queue1"
        assert 'queue2' in stats['queues'], "Should include queue2"
        
        print("\n5. Testing ping after close...")
        service.close()
        responsive = service.ping()
        print(f"   [OK] Service responsive after close: {responsive}")
        assert responsive == False, "Service should not be responsive after close"
        
        print("\n[OK] Stats and ping test passed")
        return True
        
    finally:
        shutil.rmtree(tmpdir)


def test_context_manager():
    """Test context manager support."""
    print("\n" + "="*80)
    print("TEST 9: Context Manager")
    print("="*80)
    
    tmpdir = tempfile.mkdtemp()
    
    try:
        print("\n1. Using service as context manager...")
        with StorageBasedQueueService(root_path=tmpdir) as service:
            service.put('test_queue', 'item1')
            service.put('test_queue', 'item2')
            size = service.size('test_queue')
            print(f"   [OK] Added items, size: {size}")
            assert size == 2, f"Expected size 2, got {size}"
        
        print("   [OK] Context manager exited")
        
        print("\n2. Verifying service was closed...")
        # Service should be closed after context exit
        # We can verify by creating a new instance and checking persistence
        with StorageBasedQueueService(root_path=tmpdir) as service:
            size = service.size('test_queue')
            print(f"   [OK] New instance sees size: {size}")
            assert size == 2, "Items should persist"
        
        print("\n[OK] Context manager test passed")
        return True
        
    finally:
        shutil.rmtree(tmpdir)


def test_error_handling():
    """Test error handling and edge cases."""
    print("\n" + "="*80)
    print("TEST 10: Error Handling")
    print("="*80)
    
    tmpdir = tempfile.mkdtemp()
    
    try:
        service = StorageBasedQueueService(root_path=tmpdir)
        
        print("\n1. Testing operations on closed service...")
        service.close()
        
        try:
            service.put('test_queue', 'item')
            print("   [X] Should have raised RuntimeError")
            return False
        except RuntimeError as e:
            print(f"   [OK] Raised RuntimeError: {e}")
        
        try:
            service.get('test_queue')
            print("   [X] Should have raised RuntimeError")
            return False
        except RuntimeError as e:
            print(f"   [OK] Raised RuntimeError: {e}")
        
        print("\n2. Testing operations on nonexistent queue...")
        service2 = StorageBasedQueueService(root_path=tmpdir)
        
        size = service2.size('nonexistent')
        print(f"   [OK] Size of nonexistent queue: {size}")
        assert size == 0, "Should return 0 for nonexistent queue"
        
        item = service2.get('nonexistent', blocking=False)
        print(f"   [OK] Get from nonexistent queue: {item}")
        assert item is None, "Should return None"
        
        service2.close()
        print("\n[OK] Error handling test passed")
        return True
        
    finally:
        shutil.rmtree(tmpdir)


def run_all_tests():
    """Run all tests."""
    print("""
==============================================================================
                StorageBasedQueueService Test Suite
==============================================================================
""")
    
    tests = [
        ("Basic Operations", test_basic_operations),
        ("Queue Management", test_queue_management),
        ("Peek Operation", test_peek_operation),
        ("Clear Operation", test_clear_operation),
        ("Blocking Operations", test_blocking_operations),
        ("Persistence", test_persistence),
        ("Multiprocessing Support", test_multiprocessing),
        ("Stats and Ping", test_stats_and_ping),
        ("Context Manager", test_context_manager),
        ("Error Handling", test_error_handling),
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
