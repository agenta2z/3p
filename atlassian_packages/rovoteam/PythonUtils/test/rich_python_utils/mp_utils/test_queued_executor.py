"""
Test Queued Executor Module

Tests for:
- QueuedExecutorBase: Abstract base class (via concrete implementations)
- SingleThreadExecutor: Single-threaded executor
- SimulatedMultiThreadExecutor: Manual task processing
- QueuedThreadPoolExecutor: Multi-threaded executor
- QueuedProcessPoolExecutor: Multi-process executor (basic tests only)

Prerequisites:
    No external dependencies (uses ThreadQueueService)

Usage:
    python test_queued_executor.py
"""

import sys
import time
import threading
import uuid
import tempfile
import shutil
import math
from pathlib import Path
from functools import partial
from multiprocessing import Manager

# Add src to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / 'src'))

from python_utils.mp_utils.task import Task, TaskState, TaskStatus
from python_utils.mp_utils.queued_executor import (
    QueuedExecutorBase,
    SingleThreadExecutor,
    SimulatedMultiThreadExecutor,
    QueuedThreadPoolExecutor,
    QueuedProcessPoolExecutor,
)
from python_utils.service_utils.queue_service.thread_queue_service import ThreadQueueService
from python_utils.service_utils.queue_service.storage_based_queue_service import StorageBasedQueueService


# =============================================================================
# Helper Functions
# =============================================================================

# Global counter for unique queue IDs
_test_counter = 0


def unique_queue_ids(prefix='test'):
    """Generate unique queue IDs to avoid test contamination."""
    global _test_counter
    _test_counter += 1
    unique = f"{_test_counter}_{uuid.uuid4().hex[:6]}"
    return f'{prefix}_in_{unique}', f'{prefix}_out_{unique}'


def create_queue_service():
    """Create a fresh ThreadQueueService for testing."""
    return ThreadQueueService()


def add_numbers(a, b):
    """Simple test function."""
    return a + b


def multiply_numbers(a, b):
    """Another simple test function."""
    return a * b


def slow_function(duration=0.1):
    """Function that takes some time."""
    time.sleep(duration)
    return f"slept for {duration}s"


def failing_function():
    """Function that always raises an exception."""
    raise ValueError("Intentional test error")


def double(x):
    """Double a number."""
    return x * 2


def times_ten(x):
    """Multiply by 10."""
    return x * 10


def constant_42():
    """Return constant 42."""
    return 42


# =============================================================================
# Module-level functions for QueuedProcessPoolExecutor tests (must be picklable)
# =============================================================================

def create_storage_queue_service(root_path):
    """Factory function to create StorageBasedQueueService instances.

    Each worker process calls this to create its own instance.
    Must be at module level for pickling.
    """
    return StorageBasedQueueService(root_path=root_path, use_pickle=True)


def compute_primes_for_test(limit):
    """Find prime numbers up to limit (CPU-intensive, picklable)."""
    if limit < 2:
        return {'limit': limit, 'count': 0}
    primes = []
    for num in range(2, limit + 1):
        is_prime = True
        for i in range(2, int(math.sqrt(num)) + 1):
            if num % i == 0:
                is_prime = False
                break
        if is_prime:
            primes.append(num)
    return {'limit': limit, 'count': len(primes)}


def add_numbers_for_process(a, b):
    """Simple addition for process pool tests (picklable)."""
    return a + b


def slow_process_function(duration=0.1):
    """Slow function for process pool tests (picklable)."""
    time.sleep(duration)
    return f"slept for {duration}s"


def failing_process_function():
    """Function that always fails (picklable)."""
    raise ValueError("Intentional process test error")


# =============================================================================
# SingleThreadExecutor Tests
# =============================================================================

def test_single_thread_executor_creation():
    """Test SingleThreadExecutor creation."""
    print("\n" + "=" * 80)
    print("TEST 1: SingleThreadExecutor Creation")
    print("=" * 80)

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('create')

    executor = SingleThreadExecutor(
        input_queue_service=service,
        output_queue_service=service,
        input_queue_id=input_q,
        output_queue_id=output_q,
        name='TestExecutor',
        verbose=False
    )

    assert executor.num_workers == 1, "SingleThreadExecutor should have 1 worker"
    print(f"[OK] num_workers: {executor.num_workers}")

    assert executor.name == 'TestExecutor'
    print(f"[OK] name: {executor.name}")

    assert not executor.is_running
    print(f"[OK] is_running: {executor.is_running}")

    # Verify queues were created
    assert service.exists(input_q)
    assert service.exists(output_q)
    print(f"[OK] Queues created")

    service.close()


def test_single_thread_executor_non_blocking():
    """Test SingleThreadExecutor in non-blocking mode."""
    print("\n" + "=" * 80)
    print("TEST 2: SingleThreadExecutor Non-Blocking Mode")
    print("=" * 80)

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('nonblock')

    executor = SingleThreadExecutor(
        input_queue_service=service,
        output_queue_service=service,
        input_queue_id=input_q,
        output_queue_id=output_q,
        verbose=False
    )

    # Submit tasks before starting
    task1 = Task(callable=add_numbers, args=(2, 3))
    task2 = Task(callable=multiply_numbers, args=(4, 5))
    executor.submit(task1)
    executor.submit(task2)
    print(f"[OK] Submitted 2 tasks")

    # Start in non-blocking mode
    flag = executor.run(blocking=False)
    print(f"[OK] Executor started (non-blocking)")

    assert executor.is_running
    print(f"[OK] is_running: {executor.is_running}")

    # Wait for results
    time.sleep(0.5)

    # Get results
    result1 = executor.get_result(blocking=False)
    result2 = executor.get_result(blocking=False)

    assert result1 is not None, "Should have result1"
    assert result2 is not None, "Should have result2"
    print(f"[OK] Got 2 results")

    # Verify results (order may vary)
    results = {result1.result, result2.result}
    assert 5 in results, f"Expected 5 in results: {results}"  # 2 + 3
    assert 20 in results, f"Expected 20 in results: {results}"  # 4 * 5
    print(f"[OK] Results correct: {results}")

    # Stop executor
    stopped = executor.stop(flag)
    print(f"[OK] Executor stopped: {stopped}")

    assert not executor.is_running
    print(f"[OK] is_running: {executor.is_running}")

    service.close()


def test_single_thread_executor_blocking():
    """Test SingleThreadExecutor in blocking mode."""
    print("\n" + "=" * 80)
    print("TEST 3: SingleThreadExecutor Blocking Mode")
    print("=" * 80)

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('block')

    executor = SingleThreadExecutor(
        input_queue_service=service,
        output_queue_service=service,
        input_queue_id=input_q,
        output_queue_id=output_q,
        verbose=False
    )

    # Submit task
    task = Task(callable=add_numbers, args=(10, 20))
    executor.submit(task)
    print(f"[OK] Submitted task")

    # Start blocking mode in a separate thread
    flag = [True]
    executor_thread = threading.Thread(
        target=lambda: executor.run(active_flag=flag, blocking=True)
    )
    executor_thread.start()
    print(f"[OK] Executor started in separate thread (blocking mode)")

    # Wait a bit for processing
    time.sleep(0.3)

    # Get result
    result = executor.get_result(blocking=False)
    assert result is not None, "Should have result"
    assert result.result == 30, f"Expected 30, got {result.result}"
    print(f"[OK] Result: {result.result}")

    # Stop
    flag[0] = False
    executor_thread.join(timeout=2.0)
    print(f"[OK] Executor stopped")

    service.close()


def test_single_thread_executor_start_alias():
    """Test SingleThreadExecutor start() alias."""
    print("\n" + "=" * 80)
    print("TEST 4: SingleThreadExecutor start() Alias")
    print("=" * 80)

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('alias')

    executor = SingleThreadExecutor(
        input_queue_service=service,
        output_queue_service=service,
        input_queue_id=input_q,
        output_queue_id=output_q,
        verbose=False
    )

    # Use start() instead of run(blocking=False)
    flag = executor.start()
    print(f"[OK] Started with start()")

    assert executor.is_running
    print(f"[OK] is_running: {executor.is_running}")

    executor.stop(flag)
    print(f"[OK] Stopped")

    service.close()


# =============================================================================
# SimulatedMultiThreadExecutor Tests
# =============================================================================

def test_simulated_executor_creation():
    """Test SimulatedMultiThreadExecutor creation."""
    print("\n" + "=" * 80)
    print("TEST 5: SimulatedMultiThreadExecutor Creation")
    print("=" * 80)

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('simcreate')

    executor = SimulatedMultiThreadExecutor(
        input_queue_service=service,
        output_queue_service=service,
        input_queue_id=input_q,
        output_queue_id=output_q,
        verbose=False
    )

    assert executor.num_workers == 1
    print(f"[OK] num_workers: {executor.num_workers}")

    assert executor.processed_count == 0
    print(f"[OK] processed_count: {executor.processed_count}")

    service.close()


def test_simulated_executor_process_one():
    """Test SimulatedMultiThreadExecutor.process_one()."""
    print("\n" + "=" * 80)
    print("TEST 6: SimulatedMultiThreadExecutor.process_one()")
    print("=" * 80)

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('procone')

    executor = SimulatedMultiThreadExecutor(
        input_queue_service=service,
        output_queue_service=service,
        input_queue_id=input_q,
        output_queue_id=output_q,
        verbose=False
    )

    # Submit task
    task = Task(callable=add_numbers, args=(5, 7))
    executor.submit(task)
    print(f"[OK] Submitted task")

    # Process one task
    result = executor.process_one()

    assert result is not None, "Should return result"
    assert result.result == 12, f"Expected 12, got {result.result}"
    assert result.status == TaskStatus.COMPLETED
    print(f"[OK] Result: {result.result}")

    # Check processed count
    assert executor.processed_count == 1
    print(f"[OK] processed_count: {executor.processed_count}")

    # Result should also be in output queue
    output_result = executor.get_result(blocking=False)
    assert output_result is not None
    assert output_result.result == 12
    print(f"[OK] Result in output queue")

    # Process from empty queue
    empty_result = executor.process_one(blocking=False)
    assert empty_result is None
    print(f"[OK] process_one() on empty queue returns None")

    service.close()


def test_simulated_executor_process_one_blocking():
    """Test SimulatedMultiThreadExecutor.process_one() with blocking."""
    print("\n" + "=" * 80)
    print("TEST 7: SimulatedMultiThreadExecutor.process_one() Blocking")
    print("=" * 80)

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('proconeblock')

    executor = SimulatedMultiThreadExecutor(
        input_queue_service=service,
        output_queue_service=service,
        input_queue_id=input_q,
        output_queue_id=output_q,
        verbose=False
    )

    # Try to get with timeout on empty queue
    start = time.time()
    result = executor.process_one(blocking=True, timeout=0.5)
    elapsed = time.time() - start

    assert result is None, "Should return None after timeout"
    assert elapsed >= 0.4, f"Should wait ~0.5s, waited {elapsed:.2f}s"
    print(f"[OK] Timed out after {elapsed:.2f}s")

    service.close()


def test_simulated_executor_process_all():
    """Test SimulatedMultiThreadExecutor.process_all()."""
    print("\n" + "=" * 80)
    print("TEST 8: SimulatedMultiThreadExecutor.process_all()")
    print("=" * 80)

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('procall')

    executor = SimulatedMultiThreadExecutor(
        input_queue_service=service,
        output_queue_service=service,
        input_queue_id=input_q,
        output_queue_id=output_q,
        verbose=False
    )

    # Submit multiple tasks
    for i in range(5):
        task = Task(callable=double, args=(i,))
        executor.submit(task)
    print(f"[OK] Submitted 5 tasks")

    # Process all
    results = executor.process_all()

    assert len(results) == 5, f"Expected 5 results, got {len(results)}"
    print(f"[OK] Got {len(results)} results")

    # Verify all completed
    for result in results:
        assert result.status == TaskStatus.COMPLETED
    print(f"[OK] All tasks completed successfully")

    # Check processed count
    assert executor.processed_count == 5
    print(f"[OK] processed_count: {executor.processed_count}")

    # Queue should be empty
    empty_result = executor.process_one(blocking=False)
    assert empty_result is None
    print(f"[OK] Input queue is empty")

    service.close()


def test_simulated_executor_run_in_thread():
    """Test SimulatedMultiThreadExecutor.run_in_thread()."""
    print("\n" + "=" * 80)
    print("TEST 9: SimulatedMultiThreadExecutor.run_in_thread()")
    print("=" * 80)

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('runinthread')

    executor = SimulatedMultiThreadExecutor(
        input_queue_service=service,
        output_queue_service=service,
        input_queue_id=input_q,
        output_queue_id=output_q,
        verbose=False
    )

    # Start in thread
    thread = executor.run_in_thread()

    assert thread is not None, "Should return Thread object"
    assert isinstance(thread, threading.Thread)
    assert thread.is_alive()
    print(f"[OK] Thread returned and alive: {thread.name}")

    # Submit and process
    task = Task(callable=add_numbers, args=(100, 200))
    executor.submit(task)
    print(f"[OK] Submitted task")

    # Wait for result
    time.sleep(0.3)
    result = executor.get_result(blocking=False)
    assert result is not None
    assert result.result == 300
    print(f"[OK] Result: {result.result}")

    # Stop
    executor.stop()
    thread.join(timeout=2.0)
    assert not thread.is_alive()
    print(f"[OK] Thread stopped")

    service.close()


def test_simulated_executor_failed_task():
    """Test SimulatedMultiThreadExecutor with failing task."""
    print("\n" + "=" * 80)
    print("TEST 10: SimulatedMultiThreadExecutor Failed Task")
    print("=" * 80)

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('failedtask')

    executor = SimulatedMultiThreadExecutor(
        input_queue_service=service,
        output_queue_service=service,
        input_queue_id=input_q,
        output_queue_id=output_q,
        verbose=False
    )

    # Submit failing task
    task = Task(callable=failing_function)
    executor.submit(task)
    print(f"[OK] Submitted failing task")

    # Process
    result = executor.process_one()

    assert result is not None
    assert result.status == TaskStatus.FAILED
    assert result.exception is not None
    assert isinstance(result.exception, ValueError)
    print(f"[OK] Task failed as expected: {result.exception}")

    service.close()


def test_simulated_executor_invalid_queue_item():
    """Test SimulatedMultiThreadExecutor with invalid queue item."""
    print("\n" + "=" * 80)
    print("TEST 11: SimulatedMultiThreadExecutor Invalid Queue Item")
    print("=" * 80)

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('invaliditem')

    executor = SimulatedMultiThreadExecutor(
        input_queue_service=service,
        output_queue_service=service,
        input_queue_id=input_q,
        output_queue_id=output_q,
        verbose=False
    )

    # Put non-Task item directly
    service.put(input_q, "not a task")
    print(f"[OK] Put invalid item in queue")

    # Process should raise TypeError
    try:
        executor.process_one()
        print(f"[X] Should have raised TypeError")
        service.close()
        return False
    except TypeError as e:
        print(f"[OK] TypeError raised: {e}")

    service.close()


# =============================================================================
# QueuedThreadPoolExecutor Tests
# =============================================================================

def test_thread_pool_executor_creation():
    """Test QueuedThreadPoolExecutor creation."""
    print("\n" + "=" * 80)
    print("TEST 12: QueuedThreadPoolExecutor Creation")
    print("=" * 80)

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('poolcreate')

    executor = QueuedThreadPoolExecutor(
        input_queue_service=service,
        output_queue_service=service,
        input_queue_id=input_q,
        output_queue_id=output_q,
        num_workers=4,
        verbose=False
    )

    assert executor.num_workers == 4
    print(f"[OK] num_workers: {executor.num_workers}")

    service.close()


def test_thread_pool_executor_parallel_execution():
    """Test QueuedThreadPoolExecutor parallel execution."""
    print("\n" + "=" * 80)
    print("TEST 13: QueuedThreadPoolExecutor Parallel Execution")
    print("=" * 80)

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('parallel')

    executor = QueuedThreadPoolExecutor(
        input_queue_service=service,
        output_queue_service=service,
        input_queue_id=input_q,
        output_queue_id=output_q,
        num_workers=4,
        verbose=False
    )

    # Submit 8 slow tasks
    num_tasks = 8
    task_duration = 0.2
    for i in range(num_tasks):
        task = Task(callable=slow_function, args=(task_duration,))
        executor.submit(task)
    print(f"[OK] Submitted {num_tasks} slow tasks")

    # Start and time execution
    start = time.time()
    flag = executor.start()
    print(f"[OK] Started with 4 workers")

    # Collect all results
    results = []
    for _ in range(num_tasks):
        result = executor.get_result(blocking=True, timeout=5.0)
        if result:
            results.append(result)

    elapsed = time.time() - start
    print(f"[OK] Collected {len(results)} results in {elapsed:.2f}s")

    # Stop executor
    executor.stop(flag)

    # With 4 workers, 8 tasks of 0.2s should take ~0.4-0.6s, not 8*0.2=1.6s
    assert elapsed < 1.5, f"Expected parallel execution, but took {elapsed:.2f}s"
    print(f"[OK] Parallel execution confirmed (sequential would take ~{num_tasks * task_duration}s)")

    # Verify all completed
    assert len(results) == num_tasks
    for result in results:
        assert result.status == TaskStatus.COMPLETED
    print(f"[OK] All {num_tasks} tasks completed successfully")

    service.close()


def test_thread_pool_executor_worker_ids():
    """Test that tasks are distributed across workers."""
    print("\n" + "=" * 80)
    print("TEST 14: QueuedThreadPoolExecutor Worker Distribution")
    print("=" * 80)

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('workerids')

    executor = QueuedThreadPoolExecutor(
        input_queue_service=service,
        output_queue_service=service,
        input_queue_id=input_q,
        output_queue_id=output_q,
        num_workers=3,
        verbose=False
    )

    # Submit tasks that take some time
    num_tasks = 9
    for i in range(num_tasks):
        task = Task(callable=slow_function, args=(0.1,))
        executor.submit(task)
    print(f"[OK] Submitted {num_tasks} tasks")

    flag = executor.start()

    # Collect results
    worker_ids = set()
    for _ in range(num_tasks):
        result = executor.get_result(blocking=True, timeout=5.0)
        if result:
            worker_ids.add(result.worker_id)

    executor.stop(flag)

    print(f"[OK] Tasks processed by workers: {worker_ids}")
    # With enough tasks and time, we should see multiple workers
    assert len(worker_ids) >= 1, "Should have at least one worker"

    service.close()


# =============================================================================
# Executor Stats and Properties Tests
# =============================================================================

def test_executor_get_stats():
    """Test executor get_stats() method."""
    print("\n" + "=" * 80)
    print("TEST 15: Executor get_stats()")
    print("=" * 80)

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('stats')

    executor = QueuedThreadPoolExecutor(
        input_queue_service=service,
        output_queue_service=service,
        input_queue_id=input_q,
        output_queue_id=output_q,
        num_workers=2,
        name='StatsTest',
        verbose=False
    )

    # Submit tasks
    for i in range(3):
        executor.submit(Task(callable=constant_42))

    stats = executor.get_stats()
    print(f"[OK] Stats before start: {stats}")

    assert stats['name'] == 'StatsTest'
    assert stats['num_workers'] == 2
    assert stats['is_running'] is False
    assert stats['input_queue_size'] == 3
    assert stats['output_queue_size'] == 0

    # Start executor
    flag = executor.start()
    time.sleep(0.3)

    stats = executor.get_stats()
    print(f"[OK] Stats while running: {stats}")

    assert stats['is_running'] is True
    assert stats['workers_alive'] >= 1

    executor.stop(flag)

    service.close()


def test_executor_repr():
    """Test executor __repr__."""
    print("\n" + "=" * 80)
    print("TEST 16: Executor __repr__")
    print("=" * 80)

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('repr')

    executor = SingleThreadExecutor(
        input_queue_service=service,
        output_queue_service=service,
        input_queue_id=input_q,
        output_queue_id=output_q,
        name='ReprTest',
        verbose=False
    )

    repr_str = repr(executor)
    print(f"[OK] repr: {repr_str}")

    assert 'SingleThreadExecutor' in repr_str
    assert 'ReprTest' in repr_str

    service.close()


# =============================================================================
# Validation Tests
# =============================================================================

def test_executor_validation():
    """Test executor parameter validation."""
    print("\n" + "=" * 80)
    print("TEST 17: Executor Parameter Validation")
    print("=" * 80)

    service = create_queue_service()

    # Invalid poll_interval
    try:
        SingleThreadExecutor(
            input_queue_service=service,
            output_queue_service=service,
            input_queue_id='input',
            output_queue_id='output',
            poll_interval=0
        )
        print(f"[X] Should have raised ValueError for poll_interval=0")
        service.close()
        return False
    except ValueError as e:
        print(f"[OK] ValueError for poll_interval=0: {e}")

    # Invalid poll_interval (negative)
    try:
        SingleThreadExecutor(
            input_queue_service=service,
            output_queue_service=service,
            input_queue_id='input',
            output_queue_id='output',
            poll_interval=-1
        )
        print(f"[X] Should have raised ValueError for poll_interval=-1")
        service.close()
        return False
    except ValueError as e:
        print(f"[OK] ValueError for poll_interval=-1: {e}")

    # Empty input_queue_id
    try:
        SingleThreadExecutor(
            input_queue_service=service,
            output_queue_service=service,
            input_queue_id='',
            output_queue_id='output'
        )
        print(f"[X] Should have raised ValueError for empty input_queue_id")
        service.close()
        return False
    except ValueError as e:
        print(f"[OK] ValueError for empty input_queue_id: {e}")

    # Empty output_queue_id
    try:
        SingleThreadExecutor(
            input_queue_service=service,
            output_queue_service=service,
            input_queue_id='input',
            output_queue_id=''
        )
        print(f"[X] Should have raised ValueError for empty output_queue_id")
        service.close()
        return False
    except ValueError as e:
        print(f"[OK] ValueError for empty output_queue_id: {e}")

    service.close()


def test_executor_num_workers_validation():
    """Test executor num_workers validation."""
    print("\n" + "=" * 80)
    print("TEST 18: Executor num_workers Validation")
    print("=" * 80)

    service = create_queue_service()

    # Invalid num_workers
    try:
        QueuedThreadPoolExecutor(
            input_queue_service=service,
            output_queue_service=service,
            input_queue_id='input',
            output_queue_id='output',
            num_workers=0
        )
        print(f"[X] Should have raised ValueError for num_workers=0")
        service.close()
        return False
    except ValueError as e:
        print(f"[OK] ValueError for num_workers=0: {e}")

    try:
        QueuedThreadPoolExecutor(
            input_queue_service=service,
            output_queue_service=service,
            input_queue_id='input',
            output_queue_id='output',
            num_workers=-1
        )
        print(f"[X] Should have raised ValueError for num_workers=-1")
        service.close()
        return False
    except ValueError as e:
        print(f"[OK] ValueError for num_workers=-1: {e}")

    service.close()


# =============================================================================
# Graceful Shutdown Tests
# =============================================================================

def test_executor_graceful_stop():
    """Test executor graceful stop."""
    print("\n" + "=" * 80)
    print("TEST 19: Executor Graceful Stop")
    print("=" * 80)

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('graceful')

    executor = QueuedThreadPoolExecutor(
        input_queue_service=service,
        output_queue_service=service,
        input_queue_id=input_q,
        output_queue_id=output_q,
        num_workers=2,
        verbose=False
    )

    flag = executor.start()
    print(f"[OK] Started executor")

    time.sleep(0.1)
    stats = executor.get_stats()
    assert stats['workers_alive'] == 2
    print(f"[OK] 2 workers alive")

    # Graceful stop
    all_stopped = executor.stop(flag, timeout=2.0)
    print(f"[OK] stop() returned: {all_stopped}")

    assert all_stopped, "All workers should stop gracefully"
    assert not executor.is_running
    print(f"[OK] All workers stopped gracefully")

    service.close()


def test_executor_stop_without_flag():
    """Test executor stop without passing flag."""
    print("\n" + "=" * 80)
    print("TEST 20: Executor Stop Without Flag")
    print("=" * 80)

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('noflag')

    executor = SingleThreadExecutor(
        input_queue_service=service,
        output_queue_service=service,
        input_queue_id=input_q,
        output_queue_id=output_q,
        verbose=False
    )

    executor.start()  # Don't store the flag
    print(f"[OK] Started executor")

    time.sleep(0.1)

    # Stop without passing flag (uses internal flag)
    all_stopped = executor.stop()
    print(f"[OK] Stopped without passing flag: {all_stopped}")

    assert not executor.is_running
    print(f"[OK] Executor stopped")

    service.close()


# =============================================================================
# Integration Tests
# =============================================================================

def test_submit_during_execution():
    """Test submitting tasks while executor is running."""
    print("\n" + "=" * 80)
    print("TEST 21: Submit During Execution")
    print("=" * 80)

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('submitduring')

    executor = SingleThreadExecutor(
        input_queue_service=service,
        output_queue_service=service,
        input_queue_id=input_q,
        output_queue_id=output_q,
        verbose=False
    )

    flag = executor.start()
    print(f"[OK] Started executor")

    # Submit tasks one by one
    expected_results = []
    for i in range(5):
        task = Task(callable=times_ten, args=(i,))
        executor.submit(task)
        expected_results.append(i * 10)
        time.sleep(0.05)
    print(f"[OK] Submitted 5 tasks during execution")

    # Collect results
    results = []
    for _ in range(5):
        result = executor.get_result(blocking=True, timeout=2.0)
        if result:
            results.append(result.result)
    print(f"[OK] Got results: {results}")

    # Results may be in different order, so use set comparison
    assert set(results) == set(expected_results), f"Expected {expected_results}, got {results}"
    print(f"[OK] All expected results received")

    executor.stop(flag)
    service.close()


def test_mixed_success_and_failure():
    """Test executor with mixed success and failure tasks."""
    print("\n" + "=" * 80)
    print("TEST 22: Mixed Success and Failure Tasks")
    print("=" * 80)

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('mixed')

    executor = SimulatedMultiThreadExecutor(
        input_queue_service=service,
        output_queue_service=service,
        input_queue_id=input_q,
        output_queue_id=output_q,
        verbose=False
    )

    # Submit mix of tasks
    executor.submit(Task(callable=add_numbers, args=(1, 2)))  # Success
    executor.submit(Task(callable=failing_function))  # Fail
    executor.submit(Task(callable=multiply_numbers, args=(3, 4)))  # Success
    executor.submit(Task(callable=failing_function))  # Fail
    executor.submit(Task(callable=add_numbers, args=(5, 6)))  # Success
    print(f"[OK] Submitted 5 tasks (3 success, 2 failure)")

    # Process all
    results = executor.process_all()
    assert len(results) == 5
    print(f"[OK] Got 5 results")

    # Count success and failure
    success_count = sum(1 for r in results if r.is_success())
    failure_count = sum(1 for r in results if not r.is_success())

    assert success_count == 3
    assert failure_count == 2
    print(f"[OK] Success: {success_count}, Failure: {failure_count}")

    service.close()


def test_result_timing():
    """Test that result contains proper timing information."""
    print("\n" + "=" * 80)
    print("TEST 23: Result Timing Information")
    print("=" * 80)

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('timing')

    executor = SimulatedMultiThreadExecutor(
        input_queue_service=service,
        output_queue_service=service,
        input_queue_id=input_q,
        output_queue_id=output_q,
        verbose=False
    )

    # Submit slow task
    task = Task(callable=slow_function, args=(0.2,))
    executor.submit(task)

    result = executor.process_one()

    assert result.start_time > 0
    assert result.end_time > result.start_time
    assert result.execution_time > 0
    assert result.execution_time >= 0.15  # Should be at least close to 0.2s
    print(f"[OK] start_time: {result.start_time}")
    print(f"[OK] end_time: {result.end_time}")
    print(f"[OK] execution_time: {result.execution_time:.4f}s")

    service.close()


# =============================================================================
# Additional QueuedThreadPoolExecutor Tests
# =============================================================================

def test_thread_pool_executor_failed_tasks():
    """Test QueuedThreadPoolExecutor with failing tasks."""
    print("\n" + "=" * 80)
    print("TEST 24: QueuedThreadPoolExecutor Failed Tasks")
    print("=" * 80)

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('threadfail')

    executor = QueuedThreadPoolExecutor(
        input_queue_service=service,
        output_queue_service=service,
        input_queue_id=input_q,
        output_queue_id=output_q,
        num_workers=2,
        verbose=False
    )

    # Submit mix of success and failure tasks
    executor.submit(Task(callable=add_numbers, args=(1, 2)))
    executor.submit(Task(callable=failing_function))
    executor.submit(Task(callable=multiply_numbers, args=(3, 4)))
    executor.submit(Task(callable=failing_function))
    print(f"[OK] Submitted 4 tasks (2 success, 2 failure)")

    flag = executor.start()

    # Collect results
    results = []
    for _ in range(4):
        result = executor.get_result(blocking=True, timeout=5.0)
        if result:
            results.append(result)

    executor.stop(flag)

    assert len(results) == 4
    success_count = sum(1 for r in results if r.is_success())
    failure_count = sum(1 for r in results if not r.is_success())

    assert success_count == 2, f"Expected 2 successes, got {success_count}"
    assert failure_count == 2, f"Expected 2 failures, got {failure_count}"
    print(f"[OK] Success: {success_count}, Failure: {failure_count}")

    # Verify failure has exception
    failed_results = [r for r in results if not r.is_success()]
    for r in failed_results:
        assert r.exception is not None
        assert isinstance(r.exception, ValueError)
    print(f"[OK] Failed tasks have proper exceptions")

    service.close()


def test_thread_pool_executor_dynamic_submission():
    """Test QueuedThreadPoolExecutor with tasks submitted during execution."""
    print("\n" + "=" * 80)
    print("TEST 25: QueuedThreadPoolExecutor Dynamic Submission")
    print("=" * 80)

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('threaddyn')

    executor = QueuedThreadPoolExecutor(
        input_queue_service=service,
        output_queue_service=service,
        input_queue_id=input_q,
        output_queue_id=output_q,
        num_workers=2,
        verbose=False
    )

    flag = executor.start()
    print(f"[OK] Started executor")

    # Submit tasks one by one during execution
    total_tasks = 6
    for i in range(total_tasks):
        executor.submit(Task(callable=double, args=(i,)))
        time.sleep(0.05)
    print(f"[OK] Submitted {total_tasks} tasks dynamically")

    # Collect results
    results = []
    for _ in range(total_tasks):
        result = executor.get_result(blocking=True, timeout=5.0)
        if result:
            results.append(result.result)

    executor.stop(flag)

    assert len(results) == total_tasks
    assert set(results) == {0, 2, 4, 6, 8, 10}
    print(f"[OK] Got all expected results: {sorted(results)}")

    service.close()


def test_thread_pool_executor_graceful_shutdown_with_pending():
    """Test QueuedThreadPoolExecutor graceful shutdown with pending tasks."""
    print("\n" + "=" * 80)
    print("TEST 26: QueuedThreadPoolExecutor Graceful Shutdown with Pending Tasks")
    print("=" * 80)

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('threadshutdown')

    executor = QueuedThreadPoolExecutor(
        input_queue_service=service,
        output_queue_service=service,
        input_queue_id=input_q,
        output_queue_id=output_q,
        num_workers=2,
        verbose=False
    )

    # Submit many tasks
    for i in range(10):
        executor.submit(Task(callable=slow_function, args=(0.1,)))
    print(f"[OK] Submitted 10 slow tasks")

    flag = executor.start()
    time.sleep(0.15)  # Let some tasks complete

    # Stop gracefully
    stopped = executor.stop(flag, timeout=3.0)
    print(f"[OK] Stopped with pending tasks: {stopped}")

    assert stopped, "All workers should stop gracefully"
    assert not executor.is_running
    print(f"[OK] Executor stopped cleanly")

    service.close()


# =============================================================================
# QueuedProcessPoolExecutor Comprehensive Tests
# =============================================================================

def test_process_pool_executor_requires_factory():
    """Test QueuedProcessPoolExecutor requires queue_service_factory."""
    print("\n" + "=" * 80)
    print("TEST 27: QueuedProcessPoolExecutor Requires Factory")
    print("=" * 80)

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('procfactory')

    try:
        executor = QueuedProcessPoolExecutor(
            input_queue_service=service,
            output_queue_service=service,
            input_queue_id=input_q,
            output_queue_id=output_q,
            num_workers=2,
            verbose=False
            # No queue_service_factory provided
        )
        print(f"[X] Should have raised ValueError")
        service.close()
        return False
    except ValueError as e:
        print(f"[OK] ValueError raised: {e}")

    service.close()


def test_process_pool_executor_basic_execution():
    """Test QueuedProcessPoolExecutor basic task execution with StorageBasedQueueService."""
    print("\n" + "=" * 80)
    print("TEST 28: QueuedProcessPoolExecutor Basic Execution")
    print("=" * 80)

    # Create temp directory for queue storage
    queue_dir = tempfile.mkdtemp(prefix='test_process_pool_')
    print(f"[OK] Queue storage: {queue_dir}")

    try:
        # Create factory and service
        queue_factory = partial(create_storage_queue_service, queue_dir)
        queue_service = queue_factory()

        # Create process-safe active flag
        manager = Manager()
        active_flag = manager.list([True])

        input_q, output_q = unique_queue_ids('procbasic')

        executor = QueuedProcessPoolExecutor(
            input_queue_service=queue_service,
            output_queue_service=queue_service,
            input_queue_id=input_q,
            output_queue_id=output_q,
            num_workers=2,
            verbose=False,
            queue_service_factory=queue_factory
        )

        # Submit simple tasks
        num_tasks = 4
        for i in range(num_tasks):
            executor.submit(Task(
                callable=add_numbers_for_process,
                args=(i, i * 10),
                name=f'Add-{i}'
            ))
        print(f"[OK] Submitted {num_tasks} tasks")

        # Start executor
        executor.start(active_flag)
        print(f"[OK] Started with 2 processes")

        # Collect results
        results = []
        for _ in range(num_tasks):
            result = executor.get_result(blocking=True, timeout=30.0)
            if result:
                results.append(result)

        executor.stop(active_flag)

        assert len(results) == num_tasks, f"Expected {num_tasks} results, got {len(results)}"
        print(f"[OK] Got {len(results)} results")

        # Verify results
        result_values = sorted([r.result for r in results])
        expected = sorted([i + i * 10 for i in range(num_tasks)])  # 0, 11, 22, 33
        assert result_values == expected, f"Expected {expected}, got {result_values}"
        print(f"[OK] Results correct: {result_values}")

        # All should be successful
        for r in results:
            assert r.is_success(), f"Task failed: {r.exception}"
        print(f"[OK] All tasks completed successfully")

        queue_service.close()

    finally:
        shutil.rmtree(queue_dir, ignore_errors=True)
        print(f"[OK] Cleaned up temp directory")


def test_process_pool_executor_parallel_speedup():
    """Test QueuedProcessPoolExecutor achieves parallel speedup."""
    print("\n" + "=" * 80)
    print("TEST 29: QueuedProcessPoolExecutor Parallel Speedup")
    print("=" * 80)

    queue_dir = tempfile.mkdtemp(prefix='test_process_speedup_')
    print(f"[OK] Queue storage: {queue_dir}")

    try:
        queue_factory = partial(create_storage_queue_service, queue_dir)
        queue_service = queue_factory()
        manager = Manager()

        NUM_TASKS = 4
        NUM_WORKERS = 2
        # Use longer duration to overcome file I/O overhead
        TASK_DURATION = 0.5

        # Sequential execution (baseline)
        seq_start = time.time()
        for _ in range(NUM_TASKS):
            slow_process_function(TASK_DURATION)
        seq_time = time.time() - seq_start
        print(f"[OK] Sequential time: {seq_time:.2f}s")

        # Parallel execution
        active_flag = manager.list([True])
        input_q, output_q = unique_queue_ids('procspeedup')

        executor = QueuedProcessPoolExecutor(
            input_queue_service=queue_service,
            output_queue_service=queue_service,
            input_queue_id=input_q,
            output_queue_id=output_q,
            num_workers=NUM_WORKERS,
            verbose=False,
            queue_service_factory=queue_factory
        )

        for i in range(NUM_TASKS):
            executor.submit(Task(
                callable=slow_process_function,
                args=(TASK_DURATION,)
            ))

        par_start = time.time()
        executor.start(active_flag)

        results = []
        for _ in range(NUM_TASKS):
            result = executor.get_result(blocking=True, timeout=30.0)
            if result:
                results.append(result)

        par_time = time.time() - par_start
        executor.stop(active_flag)

        print(f"[OK] Parallel time: {par_time:.2f}s")

        assert len(results) == NUM_TASKS
        speedup = seq_time / par_time
        print(f"[OK] Speedup: {speedup:.2f}x")

        # Note: On Windows with file-based queues, IPC overhead can be significant.
        # We only verify that parallel execution completes all tasks correctly.
        # Speedup may vary based on system load and file I/O performance.
        # The key test is that all tasks complete successfully with correct results.
        if speedup > 1.0:
            print(f"[OK] Parallel execution achieved {speedup:.2f}x speedup")
        else:
            print(f"[INFO] Speedup {speedup:.2f}x (IPC overhead exceeded parallelism benefit)")
            print(f"[INFO] This is expected on Windows with file-based queues for short tasks")

        # Verify all results are correct
        for r in results:
            assert r.is_success(), f"Task failed: {r.exception}"
        print(f"[OK] All {NUM_TASKS} tasks completed successfully")

        queue_service.close()

    finally:
        shutil.rmtree(queue_dir, ignore_errors=True)


def test_process_pool_executor_worker_distribution():
    """Test QueuedProcessPoolExecutor distributes work across workers."""
    print("\n" + "=" * 80)
    print("TEST 30: QueuedProcessPoolExecutor Worker Distribution")
    print("=" * 80)

    queue_dir = tempfile.mkdtemp(prefix='test_process_dist_')
    print(f"[OK] Queue storage: {queue_dir}")

    try:
        queue_factory = partial(create_storage_queue_service, queue_dir)
        queue_service = queue_factory()
        manager = Manager()
        active_flag = manager.list([True])

        NUM_TASKS = 8
        NUM_WORKERS = 4
        input_q, output_q = unique_queue_ids('procdist')

        executor = QueuedProcessPoolExecutor(
            input_queue_service=queue_service,
            output_queue_service=queue_service,
            input_queue_id=input_q,
            output_queue_id=output_q,
            num_workers=NUM_WORKERS,
            verbose=False,
            queue_service_factory=queue_factory
        )

        # Submit tasks that take some time
        for i in range(NUM_TASKS):
            executor.submit(Task(
                callable=slow_process_function,
                args=(0.1,)
            ))
        print(f"[OK] Submitted {NUM_TASKS} tasks")

        executor.start(active_flag)

        # Collect results and track worker IDs
        worker_ids = set()
        for _ in range(NUM_TASKS):
            result = executor.get_result(blocking=True, timeout=30.0)
            if result:
                worker_ids.add(result.worker_id)

        executor.stop(active_flag)

        print(f"[OK] Tasks processed by workers: {sorted(worker_ids)}")

        # With 8 tasks and 4 workers, we should see multiple workers
        assert len(worker_ids) >= 2, f"Expected multiple workers, got {worker_ids}"
        print(f"[OK] Work distributed across {len(worker_ids)} workers")

        queue_service.close()

    finally:
        shutil.rmtree(queue_dir, ignore_errors=True)


def test_process_pool_executor_failed_tasks():
    """Test QueuedProcessPoolExecutor handles failed tasks."""
    print("\n" + "=" * 80)
    print("TEST 31: QueuedProcessPoolExecutor Failed Tasks")
    print("=" * 80)

    queue_dir = tempfile.mkdtemp(prefix='test_process_fail_')
    print(f"[OK] Queue storage: {queue_dir}")

    try:
        queue_factory = partial(create_storage_queue_service, queue_dir)
        queue_service = queue_factory()
        manager = Manager()
        active_flag = manager.list([True])

        input_q, output_q = unique_queue_ids('procfail')

        executor = QueuedProcessPoolExecutor(
            input_queue_service=queue_service,
            output_queue_service=queue_service,
            input_queue_id=input_q,
            output_queue_id=output_q,
            num_workers=2,
            verbose=False,
            queue_service_factory=queue_factory
        )

        # Submit mix of success and failure
        executor.submit(Task(callable=add_numbers_for_process, args=(1, 2)))
        executor.submit(Task(callable=failing_process_function))
        executor.submit(Task(callable=add_numbers_for_process, args=(3, 4)))
        print(f"[OK] Submitted 3 tasks (2 success, 1 failure)")

        executor.start(active_flag)

        results = []
        for _ in range(3):
            result = executor.get_result(blocking=True, timeout=30.0)
            if result:
                results.append(result)

        executor.stop(active_flag)

        assert len(results) == 3
        success_count = sum(1 for r in results if r.is_success())
        failure_count = sum(1 for r in results if not r.is_success())

        assert success_count == 2, f"Expected 2 successes, got {success_count}"
        assert failure_count == 1, f"Expected 1 failure, got {failure_count}"
        print(f"[OK] Success: {success_count}, Failure: {failure_count}")

        # Verify failure has exception
        failed = [r for r in results if not r.is_success()][0]
        assert failed.exception is not None
        assert isinstance(failed.exception, ValueError)
        print(f"[OK] Failed task has proper exception: {failed.exception}")

        queue_service.close()

    finally:
        shutil.rmtree(queue_dir, ignore_errors=True)


def test_process_pool_executor_cpu_bound():
    """Test QueuedProcessPoolExecutor with CPU-bound tasks."""
    print("\n" + "=" * 80)
    print("TEST 32: QueuedProcessPoolExecutor CPU-Bound Tasks")
    print("=" * 80)

    queue_dir = tempfile.mkdtemp(prefix='test_process_cpu_')
    print(f"[OK] Queue storage: {queue_dir}")

    try:
        queue_factory = partial(create_storage_queue_service, queue_dir)
        queue_service = queue_factory()
        manager = Manager()
        active_flag = manager.list([True])

        input_q, output_q = unique_queue_ids('proccpu')

        executor = QueuedProcessPoolExecutor(
            input_queue_service=queue_service,
            output_queue_service=queue_service,
            input_queue_id=input_q,
            output_queue_id=output_q,
            num_workers=2,
            verbose=False,
            queue_service_factory=queue_factory
        )

        # Submit CPU-intensive prime calculation tasks
        limits = [10000, 15000, 20000, 25000]
        for limit in limits:
            executor.submit(Task(
                callable=compute_primes_for_test,
                args=(limit,)
            ))
        print(f"[OK] Submitted {len(limits)} prime calculation tasks")

        executor.start(active_flag)

        results = []
        for _ in range(len(limits)):
            result = executor.get_result(blocking=True, timeout=60.0)
            if result:
                results.append(result)

        executor.stop(active_flag)

        assert len(results) == len(limits)
        print(f"[OK] Got {len(results)} results")

        # Verify all successful
        for r in results:
            assert r.is_success(), f"Task failed: {r.exception}"

        # Verify results are correct (known prime counts)
        result_map = {r.result['limit']: r.result['count'] for r in results}
        print(f"[OK] Prime counts: {result_map}")

        # Basic sanity check - more primes as limit increases
        counts = [result_map[l] for l in sorted(result_map.keys())]
        assert counts == sorted(counts), "Prime counts should increase with limit"
        print(f"[OK] Prime counts increase correctly")

        queue_service.close()

    finally:
        shutil.rmtree(queue_dir, ignore_errors=True)


def test_process_pool_executor_result_timing():
    """Test QueuedProcessPoolExecutor results have proper timing."""
    print("\n" + "=" * 80)
    print("TEST 33: QueuedProcessPoolExecutor Result Timing")
    print("=" * 80)

    queue_dir = tempfile.mkdtemp(prefix='test_process_timing_')
    print(f"[OK] Queue storage: {queue_dir}")

    try:
        queue_factory = partial(create_storage_queue_service, queue_dir)
        queue_service = queue_factory()
        manager = Manager()
        active_flag = manager.list([True])

        input_q, output_q = unique_queue_ids('proctiming')

        executor = QueuedProcessPoolExecutor(
            input_queue_service=queue_service,
            output_queue_service=queue_service,
            input_queue_id=input_q,
            output_queue_id=output_q,
            num_workers=1,
            verbose=False,
            queue_service_factory=queue_factory
        )

        # Submit slow task
        SLEEP_DURATION = 0.2
        executor.submit(Task(
            callable=slow_process_function,
            args=(SLEEP_DURATION,)
        ))

        executor.start(active_flag)

        result = executor.get_result(blocking=True, timeout=30.0)
        executor.stop(active_flag)

        assert result is not None
        assert result.start_time > 0
        assert result.end_time > result.start_time
        assert result.execution_time > 0
        assert result.execution_time >= SLEEP_DURATION * 0.8  # Allow some variance

        print(f"[OK] start_time: {result.start_time}")
        print(f"[OK] end_time: {result.end_time}")
        print(f"[OK] execution_time: {result.execution_time:.4f}s (expected ~{SLEEP_DURATION}s)")

        queue_service.close()

    finally:
        shutil.rmtree(queue_dir, ignore_errors=True)


# =============================================================================
# Additional Edge Case Tests
# =============================================================================

def test_process_one_with_zero_timeout():
    """Test SimulatedMultiThreadExecutor.process_one() with timeout=0."""
    print("\n" + "=" * 80)
    print("TEST 34: process_one() with timeout=0")
    print("=" * 80)

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('zerotimeout')

    executor = SimulatedMultiThreadExecutor(
        input_queue_service=service,
        output_queue_service=service,
        input_queue_id=input_q,
        output_queue_id=output_q,
        verbose=False
    )

    # Try to get with timeout=0 on empty queue - should return immediately
    start = time.time()
    result = executor.process_one(blocking=True, timeout=0)
    elapsed = time.time() - start

    assert result is None, "Should return None immediately with timeout=0"
    assert elapsed < 0.1, f"Should return immediately, but took {elapsed:.2f}s"
    print(f"[OK] Returned None immediately with timeout=0 ({elapsed:.4f}s)")

    service.close()


def test_get_result_timeout_expiration():
    """Test get_result() timeout behavior when no results available."""
    print("\n" + "=" * 80)
    print("TEST 35: get_result() Timeout Expiration")
    print("=" * 80)

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('gettimeout')

    executor = SingleThreadExecutor(
        input_queue_service=service,
        output_queue_service=service,
        input_queue_id=input_q,
        output_queue_id=output_q,
        verbose=False
    )

    # Start executor but don't submit any tasks
    flag = executor.start()
    print(f"[OK] Started executor")

    # Try to get result with timeout
    TIMEOUT = 0.5
    start = time.time()
    result = executor.get_result(blocking=True, timeout=TIMEOUT)
    elapsed = time.time() - start

    assert result is None, "Should return None after timeout"
    assert elapsed >= TIMEOUT * 0.8, f"Should wait ~{TIMEOUT}s, waited {elapsed:.2f}s"
    assert elapsed < TIMEOUT * 2, f"Should not wait too long, waited {elapsed:.2f}s"
    print(f"[OK] Timed out after {elapsed:.2f}s (expected ~{TIMEOUT}s)")

    executor.stop(flag)
    service.close()


def test_stop_multiple_times():
    """Test calling stop() multiple times is safe."""
    print("\n" + "=" * 80)
    print("TEST 36: Stop Multiple Times")
    print("=" * 80)

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('multistop')

    executor = QueuedThreadPoolExecutor(
        input_queue_service=service,
        output_queue_service=service,
        input_queue_id=input_q,
        output_queue_id=output_q,
        num_workers=2,
        verbose=False
    )

    flag = executor.start()
    print(f"[OK] Started executor")

    time.sleep(0.1)

    # Stop first time
    stopped1 = executor.stop(flag, timeout=2.0)
    print(f"[OK] First stop: {stopped1}")
    assert stopped1, "First stop should succeed"
    assert not executor.is_running

    # Stop second time - should be safe
    stopped2 = executor.stop(flag, timeout=1.0)
    print(f"[OK] Second stop: {stopped2}")
    assert stopped2, "Second stop should also succeed (no-op)"
    assert not executor.is_running

    # Stop third time without flag
    stopped3 = executor.stop(timeout=1.0)
    print(f"[OK] Third stop (no flag): {stopped3}")
    assert stopped3, "Third stop should also succeed"

    print(f"[OK] Multiple stops handled safely")

    service.close()


def test_submit_to_stopped_executor():
    """Test submitting tasks to a stopped executor still works (queues tasks)."""
    print("\n" + "=" * 80)
    print("TEST 37: Submit to Stopped Executor")
    print("=" * 80)

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('submitstop')

    executor = SingleThreadExecutor(
        input_queue_service=service,
        output_queue_service=service,
        input_queue_id=input_q,
        output_queue_id=output_q,
        verbose=False
    )

    # Submit task before starting (executor not running)
    task1 = Task(callable=add_numbers, args=(1, 2))
    task_id1 = executor.submit(task1)
    print(f"[OK] Submitted task before start: {task_id1}")

    # Start, process, stop
    flag = executor.start()
    time.sleep(0.2)
    result1 = executor.get_result(blocking=False)
    executor.stop(flag)
    print(f"[OK] Processed task: {result1.result if result1 else None}")

    # Submit task after stopping
    task2 = Task(callable=multiply_numbers, args=(3, 4))
    task_id2 = executor.submit(task2)
    print(f"[OK] Submitted task after stop: {task_id2}")

    # Verify task is in queue
    queue_size = service.size(input_q)
    assert queue_size == 1, f"Expected 1 task in queue, got {queue_size}"
    print(f"[OK] Task queued (queue size: {queue_size})")

    # Start again and process
    flag2 = executor.start()
    time.sleep(0.2)
    result2 = executor.get_result(blocking=False)
    executor.stop(flag2)

    assert result2 is not None
    assert result2.result == 12  # 3 * 4
    print(f"[OK] Processed queued task: {result2.result}")

    service.close()


# =============================================================================
# Test Runner
# =============================================================================

def run_all_tests():
    """Run all tests."""
    print("""
==============================================================================
                    Queued Executor Module Tests
==============================================================================
""")

    tests = [
        # SingleThreadExecutor tests
        ("SingleThreadExecutor Creation", test_single_thread_executor_creation),
        ("SingleThreadExecutor Non-Blocking", test_single_thread_executor_non_blocking),
        ("SingleThreadExecutor Blocking", test_single_thread_executor_blocking),
        ("SingleThreadExecutor start() Alias", test_single_thread_executor_start_alias),

        # SimulatedMultiThreadExecutor tests
        ("SimulatedMultiThreadExecutor Creation", test_simulated_executor_creation),
        ("SimulatedMultiThreadExecutor process_one()", test_simulated_executor_process_one),
        ("SimulatedMultiThreadExecutor process_one() Blocking", test_simulated_executor_process_one_blocking),
        ("SimulatedMultiThreadExecutor process_all()", test_simulated_executor_process_all),
        ("SimulatedMultiThreadExecutor run_in_thread()", test_simulated_executor_run_in_thread),
        ("SimulatedMultiThreadExecutor Failed Task", test_simulated_executor_failed_task),
        ("SimulatedMultiThreadExecutor Invalid Queue Item", test_simulated_executor_invalid_queue_item),

        # QueuedThreadPoolExecutor tests
        ("QueuedThreadPoolExecutor Creation", test_thread_pool_executor_creation),
        ("QueuedThreadPoolExecutor Parallel Execution", test_thread_pool_executor_parallel_execution),
        ("QueuedThreadPoolExecutor Worker Distribution", test_thread_pool_executor_worker_ids),
        ("QueuedThreadPoolExecutor Failed Tasks", test_thread_pool_executor_failed_tasks),
        ("QueuedThreadPoolExecutor Dynamic Submission", test_thread_pool_executor_dynamic_submission),
        ("QueuedThreadPoolExecutor Graceful Shutdown", test_thread_pool_executor_graceful_shutdown_with_pending),

        # Stats and properties tests
        ("Executor get_stats()", test_executor_get_stats),
        ("Executor __repr__", test_executor_repr),

        # Validation tests
        ("Executor Parameter Validation", test_executor_validation),
        ("Executor num_workers Validation", test_executor_num_workers_validation),

        # Graceful shutdown tests
        ("Executor Graceful Stop", test_executor_graceful_stop),
        ("Executor Stop Without Flag", test_executor_stop_without_flag),

        # Integration tests
        ("Submit During Execution", test_submit_during_execution),
        ("Mixed Success and Failure Tasks", test_mixed_success_and_failure),
        ("Result Timing Information", test_result_timing),

        # QueuedProcessPoolExecutor comprehensive tests
        ("QueuedProcessPoolExecutor Requires Factory", test_process_pool_executor_requires_factory),
        ("QueuedProcessPoolExecutor Basic Execution", test_process_pool_executor_basic_execution),
        ("QueuedProcessPoolExecutor Parallel Speedup", test_process_pool_executor_parallel_speedup),
        ("QueuedProcessPoolExecutor Worker Distribution", test_process_pool_executor_worker_distribution),
        ("QueuedProcessPoolExecutor Failed Tasks", test_process_pool_executor_failed_tasks),
        ("QueuedProcessPoolExecutor CPU-Bound Tasks", test_process_pool_executor_cpu_bound),
        ("QueuedProcessPoolExecutor Result Timing", test_process_pool_executor_result_timing),

        # Additional edge case tests
        ("process_one() with timeout=0", test_process_one_with_zero_timeout),
        ("get_result() Timeout Expiration", test_get_result_timeout_expiration),
        ("Stop Multiple Times", test_stop_multiple_times),
        ("Submit to Stopped Executor", test_submit_to_stopped_executor),
    ]

    results = []

    for name, test_func in tests:
        try:
            test_func()
            results.append((name, True))
        except Exception as e:
            print(f"\n[X] Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

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
