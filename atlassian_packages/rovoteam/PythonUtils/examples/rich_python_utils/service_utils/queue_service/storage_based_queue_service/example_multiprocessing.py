"""
Multiprocessing example of StorageBasedQueueService

This demonstrates true multiprocessing support:
- Producer-consumer pattern across separate processes
- Multiple producers and consumers
- Task distribution
- Progress tracking

Prerequisites:
    No external dependencies (uses standard library)

Usage:
    python example_multiprocessing.py
"""

from pathlib import Path
import tempfile
import shutil
import time
import multiprocessing as mp
from datetime import datetime

from resolve_path import resolve_path
resolve_path()  # Add project src to sys.path

from python_utils.service_utils.queue_service.storage_based_queue_service import (
    StorageBasedQueueService
)


def producer(root_path, producer_id, num_tasks):
    """Producer process that creates tasks."""
    service = StorageBasedQueueService(root_path=root_path)
    
    print(f"[Producer {producer_id}] Starting, will create {num_tasks} tasks")
    
    for i in range(num_tasks):
        task = {
            'task_id': f'P{producer_id}-T{i}',
            'producer_id': producer_id,
            'data': f'Task data from producer {producer_id}, task {i}',
            'created_at': datetime.now().isoformat()
        }
        service.put('task_queue', task)
        print(f"[Producer {producer_id}] Created task: {task['task_id']}")
        time.sleep(0.1)  # Simulate work
    
    service.close()
    print(f"[Producer {producer_id}] Finished")


def consumer(root_path, consumer_id, timeout):
    """Consumer process that processes tasks."""
    service = StorageBasedQueueService(root_path=root_path)
    
    print(f"[Consumer {consumer_id}] Starting")
    processed = 0
    
    while True:
        # Try to get a task
        task = service.get('task_queue', blocking=True, timeout=timeout)
        
        if task is None:
            # No more tasks available
            print(f"[Consumer {consumer_id}] No more tasks, stopping")
            break
        
        # Process the task
        print(f"[Consumer {consumer_id}] Processing task: {task['task_id']}")
        time.sleep(0.2)  # Simulate processing
        
        # Store result
        result = {
            'task_id': task['task_id'],
            'consumer_id': consumer_id,
            'processed_at': datetime.now().isoformat(),
            'status': 'completed'
        }
        service.put('result_queue', result)
        processed += 1
    
    service.close()
    print(f"[Consumer {consumer_id}] Finished, processed {processed} tasks")


def monitor(root_path, total_expected, check_interval=0.5):
    """Monitor process that tracks progress."""
    service = StorageBasedQueueService(root_path=root_path)
    
    print("[Monitor] Starting")
    
    while True:
        pending = service.size('task_queue')
        completed = service.size('result_queue')
        
        print(f"[Monitor] Pending: {pending}, Completed: {completed}/{total_expected}")
        
        if completed >= total_expected:
            print("[Monitor] All tasks completed!")
            break
        
        time.sleep(check_interval)
    
    service.close()
    print("[Monitor] Finished")


def example_basic_producer_consumer():
    """Example 1: Basic producer-consumer pattern."""
    print("\n" + "="*80)
    print("EXAMPLE 1: Basic Producer-Consumer Pattern")
    print("="*80)
    
    tmpdir = tempfile.mkdtemp()
    
    try:
        print("\n1. Starting producer and consumer processes...")
        
        num_tasks = 5
        
        # Start producer
        p = mp.Process(target=producer, args=(tmpdir, 1, num_tasks))
        p.start()
        
        # Start consumer
        c = mp.Process(target=consumer, args=(tmpdir, 1, 2.0))
        c.start()
        
        # Wait for completion
        p.join()
        c.join()
        
        print("\n2. Checking results...")
        service = StorageBasedQueueService(root_path=tmpdir)
        
        pending = service.size('task_queue')
        completed = service.size('result_queue')
        
        print(f"   [OK] Pending tasks: {pending}")
        print(f"   [OK] Completed tasks: {completed}")
        
        # Get all results
        results = []
        while service.size('result_queue') > 0:
            result = service.get('result_queue', blocking=False)
            if result:
                results.append(result)
        
        print(f"\n   Results:")
        for result in results:
            print(f"   - {result['task_id']}: {result['status']} by Consumer {result['consumer_id']}")
        
        service.close()
        
    finally:
        time.sleep(0.1)
        try:
            shutil.rmtree(tmpdir)
        except:
            pass


def example_multiple_producers_consumers():
    """Example 2: Multiple producers and consumers."""
    print("\n" + "="*80)
    print("EXAMPLE 2: Multiple Producers and Consumers")
    print("="*80)
    
    tmpdir = tempfile.mkdtemp()
    
    try:
        print("\n1. Starting multiple producers and consumers...")
        
        num_producers = 2
        num_consumers = 3
        tasks_per_producer = 4
        total_tasks = num_producers * tasks_per_producer
        
        processes = []
        
        # Start producers
        for i in range(num_producers):
            p = mp.Process(target=producer, args=(tmpdir, i+1, tasks_per_producer))
            p.start()
            processes.append(p)
        
        # Start consumers
        for i in range(num_consumers):
            c = mp.Process(target=consumer, args=(tmpdir, i+1, 3.0))
            c.start()
            processes.append(c)
        
        # Start monitor
        m = mp.Process(target=monitor, args=(tmpdir, total_tasks, 0.5))
        m.start()
        processes.append(m)
        
        # Wait for all processes
        for p in processes:
            p.join()
        
        print("\n2. Final statistics...")
        service = StorageBasedQueueService(root_path=tmpdir)
        
        stats = service.get_stats()
        print(f"   [OK] Total queues: {stats['total_queues']}")
        for queue_id, queue_stats in stats['queues'].items():
            print(f"   - {queue_id}: {queue_stats['size']} items")
        
        service.close()
        
    finally:
        time.sleep(0.1)
        try:
            shutil.rmtree(tmpdir)
        except:
            pass


def priority_consumer(root_path, consumer_id):
    """Consumer that processes high priority tasks first."""
    service = StorageBasedQueueService(root_path=root_path)
    
    # Process high priority first
    while True:
        task = service.get('high_priority_queue', blocking=False)
        if task is None:
            break
        print(f"[Consumer {consumer_id}] Processing HIGH: {task['task_id']}")
        time.sleep(0.1)
    
    # Then process normal priority
    while True:
        task = service.get('normal_priority_queue', blocking=False)
        if task is None:
            break
        print(f"[Consumer {consumer_id}] Processing NORMAL: {task['task_id']}")
        time.sleep(0.1)
    
    service.close()


def example_task_distribution():
    """Example 3: Task distribution with priority."""
    print("\n" + "="*80)
    print("EXAMPLE 3: Task Distribution with Priority")
    print("="*80)
    
    tmpdir = tempfile.mkdtemp()
    
    try:
        print("\n1. Creating tasks with different priorities...")
        service = StorageBasedQueueService(root_path=tmpdir)
        
        # Create high priority tasks
        for i in range(3):
            task = {
                'task_id': f'HIGH-{i}',
                'priority': 'high',
                'data': f'High priority task {i}'
            }
            service.put('high_priority_queue', task)
            print(f"   [+] Created high priority task: {task['task_id']}")
        
        # Create normal priority tasks
        for i in range(5):
            task = {
                'task_id': f'NORMAL-{i}',
                'priority': 'normal',
                'data': f'Normal priority task {i}'
            }
            service.put('normal_priority_queue', task)
            print(f"   [+] Created normal priority task: {task['task_id']}")
        
        service.close()
        
        print("\n2. Processing high priority tasks first...")
        
        # Start consumer
        c = mp.Process(target=priority_consumer, args=(tmpdir, 1))
        c.start()
        c.join()
        
        print("\n   [OK] All tasks processed in priority order")
        
    finally:
        time.sleep(0.1)
        try:
            shutil.rmtree(tmpdir)
        except:
            pass


def main():
    print("""
==============================================================================
        StorageBasedQueueService Multiprocessing Examples
==============================================================================
""")
    
    examples = [
        example_basic_producer_consumer,
        example_multiple_producers_consumers,
        example_task_distribution,
    ]
    
    for example_func in examples:
        try:
            example_func()
        except Exception as e:
            print(f"\n[X] Example failed: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*80)
    print("[OK] All multiprocessing examples completed!")
    print("="*80 + "\n")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n[X] Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
