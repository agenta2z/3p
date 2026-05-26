"""
QueuedThreadPoolExecutor Example (I/O-Bound Tasks)

This demonstrates QueuedThreadPoolExecutor from this library for I/O-bound tasks:
- Queue-based task distribution to multiple worker threads
- Comparison of sequential (SingleThreadExecutor) vs parallel execution
- Worker load distribution analysis

Note: This uses QueuedThreadPoolExecutor (from python_utils.mp_utils),
NOT Python's built-in concurrent.futures.ThreadPoolExecutor.

Use Case:
    When you have many I/O-bound tasks that spend time waiting (network latency,
    disk I/O, database responses). Multiple threads can process other tasks
    while one is waiting, dramatically reducing total execution time.

Why Threads (not Processes) for I/O:
    Python's GIL (Global Interpreter Lock) only blocks CPU-bound operations.
    During I/O waits, the GIL is released, allowing true concurrency.
    Threads are lightweight and share memory, making them efficient for I/O.

Prerequisites:
    No external dependencies (uses ThreadQueueService)

Usage:
    python example_queued_thread_pool.py
"""

from resolve_path import resolve_path
resolve_path()  # Add project src to sys.path

import time
from python_utils.mp_utils.task import Task
from python_utils.mp_utils.queued_executor import (
    SingleThreadExecutor,
    QueuedThreadPoolExecutor,
)
from python_utils.service_utils.queue_service.thread_queue_service import ThreadQueueService


# =============================================================================
# Simulated I/O-bound tasks
# =============================================================================

def fetch_api_data(endpoint_id):
    """Simulate fetching data from an API endpoint."""
    time.sleep(0.15)  # Simulate network latency
    return {
        'endpoint_id': endpoint_id,
        'data': f'response_from_endpoint_{endpoint_id}',
        'latency_ms': 150
    }


def read_file(file_id):
    """Simulate reading a file from disk."""
    time.sleep(0.10)  # Simulate disk I/O
    return {
        'file_id': file_id,
        'content': f'file_{file_id}_contents',
        'size_kb': 100 + file_id * 10
    }


def query_database(query_id):
    """Simulate executing a database query."""
    time.sleep(0.12)  # Simulate query execution
    return {
        'query_id': query_id,
        'rows': query_id * 5,
        'execution_ms': 120
    }


def main():
    print("""
==============================================================================
        QueuedThreadPoolExecutor - Thread Pool for I/O-Bound Tasks
==============================================================================

Threads excel at I/O-bound tasks because:
- The GIL is released during I/O waits
- Multiple threads can wait on different I/O operations simultaneously
- Low overhead for creating and switching between threads
""")

    # =========================================================================
    # 1. Setup
    # =========================================================================
    print("1. Setup...")

    queue_service = ThreadQueueService()
    NUM_TASKS = 12
    NUM_WORKERS = 4

    print(f"   Tasks: {NUM_TASKS} API calls (each takes ~150ms)")
    print(f"   Workers: {NUM_WORKERS} threads")
    print(f"   Expected sequential time: ~{NUM_TASKS * 0.15:.2f}s")
    print(f"   Expected parallel time: ~{(NUM_TASKS / NUM_WORKERS) * 0.15:.2f}s")

    # =========================================================================
    # 2. Sequential execution (baseline)
    # =========================================================================
    print("\n2. SEQUENTIAL execution (1 thread)...")

    seq_executor = SingleThreadExecutor(
        input_queue_service=queue_service,
        output_queue_service=queue_service,
        input_queue_id='seq_in',
        output_queue_id='seq_out',
        name='SequentialWorker',
        verbose=False
    )

    for i in range(NUM_TASKS):
        seq_executor.submit(Task(callable=fetch_api_data, args=(i,)))

    start = time.time()
    flag = seq_executor.start()

    seq_results = []
    for _ in range(NUM_TASKS):
        result = seq_executor.get_result(blocking=True, timeout=30.0)
        if result:
            seq_results.append(result)

    seq_time = time.time() - start
    seq_executor.stop(flag)

    print(f"   [OK] Completed {len(seq_results)} tasks in {seq_time:.2f}s")

    # =========================================================================
    # 3. Parallel execution with thread pool
    # =========================================================================
    print(f"\n3. PARALLEL execution ({NUM_WORKERS} threads)...")

    par_executor = QueuedThreadPoolExecutor(
        input_queue_service=queue_service,
        output_queue_service=queue_service,
        input_queue_id='par_in',
        output_queue_id='par_out',
        num_workers=NUM_WORKERS,
        name='ThreadPool',
        verbose=False
    )

    for i in range(NUM_TASKS):
        par_executor.submit(Task(callable=fetch_api_data, args=(i,)))

    start = time.time()
    flag = par_executor.start()

    par_results = []
    for _ in range(NUM_TASKS):
        result = par_executor.get_result(blocking=True, timeout=30.0)
        if result:
            par_results.append(result)

    par_time = time.time() - start
    par_executor.stop(flag)

    print(f"   [OK] Completed {len(par_results)} tasks in {par_time:.2f}s")

    # =========================================================================
    # 4. Performance analysis
    # =========================================================================
    print("\n4. Performance analysis...")

    speedup = seq_time / par_time if par_time > 0 else 0
    efficiency = (speedup / NUM_WORKERS) * 100

    print(f"   Sequential:  {seq_time:.2f}s")
    print(f"   Parallel:    {par_time:.2f}s")
    print(f"   Speedup:     {speedup:.2f}x (ideal: {NUM_WORKERS}x)")
    print(f"   Efficiency:  {efficiency:.1f}%")
    print(f"   Time saved:  {seq_time - par_time:.2f}s")

    # =========================================================================
    # 5. Worker distribution
    # =========================================================================
    print("\n5. Worker load distribution...")

    worker_counts = {}
    for result in par_results:
        wid = result.worker_id
        worker_counts[wid] = worker_counts.get(wid, 0) + 1

    for wid in sorted(worker_counts.keys()):
        count = worker_counts[wid]
        bar = "#" * count
        print(f"   Thread {wid}: {bar} ({count} tasks)")

    # =========================================================================
    # 6. Mixed I/O workload
    # =========================================================================
    print("\n6. Mixed I/O workload (API + File + DB)...")

    mixed_executor = QueuedThreadPoolExecutor(
        input_queue_service=queue_service,
        output_queue_service=queue_service,
        input_queue_id='mixed_in',
        output_queue_id='mixed_out',
        num_workers=4,
        name='MixedIO',
        verbose=False
    )

    # Submit different I/O task types
    for i in range(4):
        mixed_executor.submit(Task(callable=fetch_api_data, args=(i,), name=f'API-{i}'))
        mixed_executor.submit(Task(callable=read_file, args=(i,), name=f'File-{i}'))
        mixed_executor.submit(Task(callable=query_database, args=(i,), name=f'DB-{i}'))

    total_tasks = 12

    start = time.time()
    flag = mixed_executor.start()

    mixed_results = []
    for _ in range(total_tasks):
        result = mixed_executor.get_result(blocking=True, timeout=30.0)
        if result:
            mixed_results.append(result)

    mixed_time = time.time() - start
    mixed_executor.stop(flag)

    # Calculate theoretical sequential time
    theoretical_seq = 4 * (0.15 + 0.10 + 0.12)  # 4 each of API, File, DB

    print(f"   Completed {len(mixed_results)} mixed tasks in {mixed_time:.2f}s")
    print(f"   (Sequential would take ~{theoretical_seq:.2f}s)")

    # =========================================================================
    # 7. Cleanup
    # =========================================================================
    print("\n7. Cleanup...")

    for qid in ['seq_in', 'seq_out', 'par_in', 'par_out', 'mixed_in', 'mixed_out']:
        queue_service.delete(qid)
    queue_service.close()

    print("   [OK] Complete")

    print("\n" + "=" * 80)
    print("[OK] Example completed successfully!")
    print("=" * 80)
    print("""
Key Takeaways:
- QueuedThreadPoolExecutor is ideal for I/O-bound parallel tasks
- Threads share memory, making them lightweight and efficient
- The GIL is released during I/O waits, enabling true parallelism
- Speedup approaches N workers for pure I/O workloads
- For CPU-bound tasks, use QueuedProcessPoolExecutor instead
""")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n[X] Error: {e}")
        import traceback
        traceback.print_exc()
        import sys
        sys.exit(1)
