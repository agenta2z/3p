"""
QueuedProcessPoolExecutor Example (CPU-Bound Tasks)

This demonstrates QueuedProcessPoolExecutor from this library for CPU-bound tasks:
- Queue-based task distribution to multiple worker processes
- Uses StorageBasedQueueService for inter-process communication (IPC)
- Comparison of sequential vs parallel execution
- True parallel CPU execution bypassing Python's GIL

Note: This uses QueuedProcessPoolExecutor (from python_utils.mp_utils)
with StorageBasedQueueService for IPC. ThreadQueueService does NOT work with
processes because each process creates isolated queues.

Use Case:
    When you have CPU-intensive computations (data processing, mathematical
    calculations, image processing) that need true parallelism across processes.

Why Processes (not Threads) for CPU:
    Python's GIL (Global Interpreter Lock) prevents multiple threads from
    executing Python bytecode simultaneously. Processes have separate memory
    spaces and their own GIL, enabling true parallel CPU execution.

Prerequisites:
    No external dependencies (uses StorageBasedQueueService with file-based IPC)

Usage:
    python example_queued_process_pool.py
"""

from resolve_path import resolve_path
resolve_path()  # Add project src to sys.path

import os
import time
import math
import tempfile
import shutil
from functools import partial
from multiprocessing import Manager
from python_utils.mp_utils.task import Task
from python_utils.mp_utils.queued_executor import (
    SingleThreadExecutor,
    QueuedProcessPoolExecutor,
)
from python_utils.service_utils.queue_service.storage_based_queue_service import (
    StorageBasedQueueService
)


# =============================================================================
# Queue service factory (must be at module level for pickling)
# =============================================================================

def create_queue_service(root_path):
    """Factory function to create queue service instances.

    Each worker process calls this to create its own instance.
    Must be at module level (not inside a function) for pickling.
    """
    return StorageBasedQueueService(root_path=root_path, use_pickle=True)


# =============================================================================
# CPU-bound task functions (must be at module level for pickling)
# =============================================================================

def compute_primes(limit):
    """Find all prime numbers up to limit using trial division."""
    if limit < 2:
        return {'limit': limit, 'count': 0, 'largest': None}
    primes = []
    for num in range(2, limit + 1):
        is_prime = True
        for i in range(2, int(math.sqrt(num)) + 1):
            if num % i == 0:
                is_prime = False
                break
        if is_prime:
            primes.append(num)
    return {
        'limit': limit,
        'count': len(primes),
        'largest': primes[-1] if primes else None
    }


def matrix_multiply(size):
    """Perform matrix multiplication (CPU-intensive)."""
    matrix_a = [[i + j for j in range(size)] for i in range(size)]
    matrix_b = [[i * j for j in range(size)] for i in range(size)]

    result = [[0] * size for _ in range(size)]
    for i in range(size):
        for j in range(size):
            for k in range(size):
                result[i][j] += matrix_a[i][k] * matrix_b[k][j]

    checksum = sum(sum(row) for row in result)
    return {'size': size, 'checksum': checksum}


def hash_iterations(data, iterations):
    """Perform many hash iterations (CPU-intensive)."""
    import hashlib
    result = str(data).encode()
    for _ in range(iterations):
        result = hashlib.sha256(result).digest()
    return {
        'data': data,
        'iterations': iterations,
        'hash': result.hex()[:16]
    }


def main():
    print("""
==============================================================================
      QueuedProcessPoolExecutor - Process Pool for CPU-Bound Tasks
==============================================================================

This example uses QueuedProcessPoolExecutor with StorageBasedQueueService
for true inter-process communication (IPC).

Processes excel at CPU-bound tasks because:
- Each process has its own GIL (no lock contention)
- True parallel execution on multiple CPU cores
- Can utilize 100% of multi-core CPUs
""")

    NUM_TASKS = 8
    NUM_WORKERS = 4

    # Create temporary directory for queue storage
    queue_dir = tempfile.mkdtemp(prefix='queued_process_pool_')
    print(f"   Queue storage: {queue_dir}")

    try:
        # =====================================================================
        # 1. Setup
        # =====================================================================
        print("\n1. Setup...")

        # Create factory function with bound queue_dir using partial
        # (Factory must be picklable for multiprocessing, so we use module-level function + partial)
        queue_factory = partial(create_queue_service, queue_dir)

        # Main process queue service instance
        queue_service = queue_factory()

        # Manager for process-safe active flag
        manager = Manager()

        print(f"   Tasks: {NUM_TASKS} CPU-intensive calculations")
        print(f"   Workers: {NUM_WORKERS} processes")

        # =====================================================================
        # 2. Sequential execution (baseline)
        # =====================================================================
        print("\n2. SEQUENTIAL execution (SingleThreadExecutor)...")

        seq_executor = SingleThreadExecutor(
            input_queue_service=queue_service,
            output_queue_service=queue_service,
            input_queue_id='seq_in',
            output_queue_id='seq_out',
            name='SequentialWorker',
            verbose=False
        )

        # Submit tasks - larger limits for meaningful CPU work to overcome file I/O overhead
        for i in range(NUM_TASKS):
            limit = 150000 + i * 25000
            seq_executor.submit(Task(
                callable=compute_primes,
                args=(limit,),
                name=f'Primes-{limit}'
            ))

        start = time.time()
        flag = seq_executor.start()

        seq_results = []
        for _ in range(NUM_TASKS):
            result = seq_executor.get_result(blocking=True, timeout=120.0)
            if result:
                seq_results.append(result)

        seq_time = time.time() - start
        seq_executor.stop(flag)

        print(f"   [OK] Completed {len(seq_results)} tasks in {seq_time:.2f}s")

        # =====================================================================
        # 3. Parallel execution with QueuedProcessPoolExecutor
        # =====================================================================
        print(f"\n3. PARALLEL execution (QueuedProcessPoolExecutor, {NUM_WORKERS} processes)...")

        # Create process-safe active flag
        active_flag = manager.list([True])

        par_executor = QueuedProcessPoolExecutor(
            input_queue_service=queue_service,
            output_queue_service=queue_service,
            input_queue_id='par_in',
            output_queue_id='par_out',
            num_workers=NUM_WORKERS,
            name='ProcessPool',
            verbose=False,
            queue_service_factory=queue_factory  # Factory for worker processes
        )

        # Submit same tasks
        for i in range(NUM_TASKS):
            limit = 150000 + i * 25000
            par_executor.submit(Task(
                callable=compute_primes,
                args=(limit,),
                name=f'Primes-{limit}'
            ))

        start = time.time()
        par_executor.start(active_flag)

        par_results = []
        for _ in range(NUM_TASKS):
            result = par_executor.get_result(blocking=True, timeout=120.0)
            if result:
                par_results.append(result)

        par_time = time.time() - start
        par_executor.stop(active_flag)

        print(f"   [OK] Completed {len(par_results)} tasks in {par_time:.2f}s")

        # =====================================================================
        # 4. Performance analysis
        # =====================================================================
        print("\n4. Performance analysis...")

        speedup = seq_time / par_time if par_time > 0 else 0
        efficiency = (speedup / NUM_WORKERS) * 100

        print(f"   Sequential:  {seq_time:.2f}s")
        print(f"   Parallel:    {par_time:.2f}s")
        print(f"   Speedup:     {speedup:.2f}x (ideal: {NUM_WORKERS}x)")
        print(f"   Efficiency:  {efficiency:.1f}%")
        print(f"   Time saved:  {seq_time - par_time:.2f}s")

        if speedup > 1.5:
            print("   [OK] Significant speedup achieved!")
        else:
            print("   Note: File I/O overhead may reduce speedup for small tasks")

        # =====================================================================
        # 5. Worker distribution
        # =====================================================================
        print("\n5. Worker load distribution...")

        worker_counts = {}
        for result in par_results:
            wid = result.worker_id
            worker_counts[wid] = worker_counts.get(wid, 0) + 1

        for wid in sorted(worker_counts.keys()):
            count = worker_counts[wid]
            bar = "#" * count
            print(f"   Process {wid}: {bar} ({count} tasks)")

        # =====================================================================
        # 6. Show sample results
        # =====================================================================
        print("\n6. Sample results (prime calculations)...")

        sorted_results = sorted(par_results, key=lambda r: r.result['limit'])
        for result in sorted_results[:4]:
            if result.is_success():
                data = result.result
                print(f"   Primes up to {data['limit']}: found {data['count']} primes "
                      f"(largest: {data['largest']})")

        # =====================================================================
        # 7. Mixed CPU workload
        # =====================================================================
        print("\n7. Mixed CPU workload (primes + matrix + hashing)...")

        active_flag = manager.list([True])

        mixed_executor = QueuedProcessPoolExecutor(
            input_queue_service=queue_service,
            output_queue_service=queue_service,
            input_queue_id='mixed_in',
            output_queue_id='mixed_out',
            num_workers=4,
            name='MixedCPU',
            verbose=False,
            queue_service_factory=queue_factory
        )

        # Submit different CPU task types - larger sizes to overcome IPC overhead
        mixed_tasks = 0
        for i in range(3):
            mixed_executor.submit(Task(callable=compute_primes, args=(100000 + i * 20000,)))
            mixed_tasks += 1
        for i in range(3):
            mixed_executor.submit(Task(callable=matrix_multiply, args=(120 + i * 20,)))
            mixed_tasks += 1
        for i in range(3):
            mixed_executor.submit(Task(callable=hash_iterations, args=(f'data_{i}', 500000)))
            mixed_tasks += 1

        start = time.time()
        mixed_executor.start(active_flag)

        mixed_results = []
        for _ in range(mixed_tasks):
            result = mixed_executor.get_result(blocking=True, timeout=120.0)
            if result:
                mixed_results.append(result)

        mixed_time = time.time() - start
        mixed_executor.stop(active_flag)

        # Count by type
        primes_done = sum(1 for r in mixed_results if r.is_success() and 'count' in r.result)
        matrix_done = sum(1 for r in mixed_results if r.is_success() and 'checksum' in r.result)
        hash_done = sum(1 for r in mixed_results if r.is_success() and 'hash' in r.result)

        print(f"   Completed {len(mixed_results)} mixed tasks in {mixed_time:.2f}s")
        print(f"   - Prime calculations: {primes_done}")
        print(f"   - Matrix multiplications: {matrix_done}")
        print(f"   - Hash iterations: {hash_done}")

        # =====================================================================
        # 8. Cleanup
        # =====================================================================
        print("\n8. Cleanup...")

        queue_service.close()
        print("   [OK] Queue service closed")

    finally:
        # Clean up temporary directory
        shutil.rmtree(queue_dir, ignore_errors=True)
        print(f"   [OK] Temporary files cleaned up")

    print("\n" + "=" * 80)
    print("[OK] Example completed successfully!")
    print("=" * 80)
    print("""
Key Takeaways:
- QueuedProcessPoolExecutor enables queue-based multi-process execution
- StorageBasedQueueService provides IPC through file-based storage
- Each process has its own GIL, enabling true parallel computation
- Processes have overhead (startup, file I/O) - best for larger tasks
- For I/O-bound tasks, use QueuedThreadPoolExecutor instead

Why StorageBasedQueueService (not ThreadQueueService):
- ThreadQueueService uses multiprocessing.Manager which creates isolated
  queues in each spawned process - tasks won't be shared
- StorageBasedQueueService uses file-based storage accessible by all processes
- RedisQueueService is another option for production use

Important Notes:
- Task functions must be defined at module level (for pickling)
- Use Manager().list() for the active flag in multi-process contexts
- File I/O adds overhead - best for tasks taking > 100ms each
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
