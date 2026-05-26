"""
Monitor Pattern with Multiprocessing (run_async Router Mode)

This example demonstrates the queue-based monitor pattern using processes:
- A background process increments a counter in a file every 2 seconds
- A monitor task watches the file and triggers actions when count % 20 == 0
- Uses router mode (router=Callable) because closures can't cross process boundaries

Scenario:
    Same as the threading example, but using multiple processes for true parallelism.
    This is useful when monitor/action tasks are CPU-bound, or when you need
    isolation between tasks.

Key Concepts:
    - run_async() with router mode: tasks return just result, router decides next_tasks
    - Router runs in MAIN PROCESS: has access to graph logic, state dicts, closures
    - Only raw functions cross process boundary: must be picklable (no closures)
    - Self-loop pattern: router returns task pointing to same function

Why Router Mode for Multiprocessing?
    - Worker processes can only execute picklable functions
    - Closures capture local state -> not picklable
    - Router runs in main process -> CAN use closures and local state
    - This gives you the best of both worlds!

Usage:
    python example_monitor_multiprocessing.py
"""

from resolve_path import resolve_path
resolve_path()

import os
import time
import multiprocessing as mp
import tempfile
from pathlib import Path
from typing import Any, List

from python_utils.mp_utils.task import Task, TaskState, TaskStatus
from python_utils.mp_utils.queued_executor import SimulatedMultiThreadExecutor
from python_utils.service_utils.queue_service.thread_queue_service import ThreadQueueService


# =============================================================================
# Counter Process (Simulates a long-running process)
# =============================================================================

def counter_process_target(counter_file_path: str, interval: float, max_count: int, stop_event):
    """
    Process target that increments a counter in a file.

    Note: This is a top-level function (not a closure) because it runs
    in a separate process and must be picklable.
    """
    counter_file = Path(counter_file_path)
    count = 0

    while count < max_count and not stop_event.is_set():
        count += 1
        counter_file.write_text(str(count))
        print(f"   [Counter] Written count={count} to file")
        stop_event.wait(interval)

    print(f"   [Counter] Finished at count={count}")


# =============================================================================
# Monitor and Action Functions (Top-level - picklable)
# =============================================================================

# Shared state via file (processes don't share memory)
_COUNTER_FILE_PATH = None
_TARGET_DIVISOR = 20
_POLL_INTERVAL = 0.5


def set_monitor_config(counter_file_path: str, target_divisor: int = 20, poll_interval: float = 0.5):
    """Set global config for monitor (called before spawning processes)."""
    global _COUNTER_FILE_PATH, _TARGET_DIVISOR, _POLL_INTERVAL
    _COUNTER_FILE_PATH = counter_file_path
    _TARGET_DIVISOR = target_divisor
    _POLL_INTERVAL = poll_interval


def monitor_iteration():
    """
    Single iteration of the monitor.

    This is a top-level function (picklable) that workers can execute.
    It returns just the result - the router decides what comes next.

    Note: We use globals for config because closures can't cross process boundaries.
    In production, you might use environment variables, config files, or a
    shared database instead.
    """
    counter_file = Path(_COUNTER_FILE_PATH)

    # Read current count from file
    try:
        current_count = int(counter_file.read_text().strip())
    except (FileNotFoundError, ValueError):
        current_count = 0

    print(f"   [Monitor] Checking count={current_count}")

    # Return result - router will decide next steps
    return {
        'type': 'monitor_check',
        'count': current_count,
        'divisor': _TARGET_DIVISOR,
        'condition_met': current_count > 0 and current_count % _TARGET_DIVISOR == 0
    }


def action_handler(count: int):
    """
    Action that runs when milestone is reached.

    Note: This takes count as parameter (not closure) to be picklable.
    """
    print(f"   [Action] Processing milestone at count={count}")
    print(f"   [Action] Simulating work (e.g., send notification, update dashboard)...")
    time.sleep(0.5)  # Simulate some work

    result = {
        'type': 'action_completed',
        'count': count,
        'timestamp': time.time()
    }
    print(f"   [Action] Completed!")
    return result


# =============================================================================
# Router (Runs in Main Process - Can Use Closures!)
# =============================================================================

def create_router(target_divisor: int):
    """
    Create a router that decides next tasks based on results.

    The router runs in the MAIN PROCESS, so it CAN use closures and
    local state. Only the task functions need to be picklable.

    This is the key insight that makes router mode powerful:
    - Complex routing logic stays in main process
    - Workers only execute simple, stateless functions
    """

    iteration_count = [0]  # Closure state - this works because router is in main process!

    def router(task_id: str, result: Any, task_state: TaskState) -> List[Task]:
        """
        Router callback - receives result and returns next tasks.

        Args:
            task_id: ID of the completed task
            result: The result returned by the task
            task_state: Full TaskState with input_args, status, etc.

        Returns:
            List of next Task objects to execute
        """
        iteration_count[0] += 1

        # Handle monitor check result
        if result.get('type') == 'monitor_check':
            if result.get('condition_met'):
                # Milestone reached! Trigger action
                count = result['count']
                print(f"   [Router] Milestone detected at count={count}, triggering action")

                # Create action task
                # Note: We pass count as argument, not closure
                action_task = Task(
                    callable=action_handler,
                    task_id=f"action_{count}",
                    args=(count,)  # Pass count as argument
                )
                return [action_task]

            else:
                # Not met yet - continue monitoring
                time.sleep(_POLL_INTERVAL)

                # Create next monitor iteration
                monitor_task = Task(
                    callable=monitor_iteration,  # Same function, new task
                    task_id=f"monitor_iter_{iteration_count[0]}"
                )
                return [monitor_task]

        # Action completed - no more tasks (leaf node)
        elif result.get('type') == 'action_completed':
            print(f"   [Router] Action completed, no more tasks")
            return []

        # Unknown result type - stop
        else:
            print(f"   [Router] Unknown result type: {result}")
            return []

    return router


# =============================================================================
# Main Example
# =============================================================================

def main():
    print("""
==============================================================================
        Monitor Pattern with Multiprocessing (Router Mode)
==============================================================================

This example shows:
1. A background process incrementing a counter every 2 seconds
2. A monitor task (top-level function) checking for count % 20 == 0
3. A router (in main process) deciding next tasks based on results
4. An action task triggered when the condition is met

Using router mode (router=Callable):
- Tasks return just result (not tuple)
- Router in main process decides next_tasks
- Router CAN use closures (it never crosses process boundary)
- Task functions must be top-level (picklable)
""")

    # =========================================================================
    # 1. Setup
    # =========================================================================
    print("1. Setup...")

    # Create temporary file for counter
    counter_file = Path(tempfile.gettempdir()) / "monitor_mp_example_counter.txt"
    counter_file.write_text("0")
    print(f"   Counter file: {counter_file}")

    # Configure monitor (before any processes are spawned)
    set_monitor_config(
        counter_file_path=str(counter_file),
        target_divisor=20,
        poll_interval=0.5
    )

    # Create queue service and executor
    # Note: Using SimulatedMultiThreadExecutor for this example
    # In production with true multiprocessing, you'd use QueuedProcessPoolExecutor
    queue_service = ThreadQueueService()
    executor = SimulatedMultiThreadExecutor(
        input_queue_service=queue_service,
        output_queue_service=queue_service,
        input_queue_id='monitor_in',
        output_queue_id='monitor_out',
        verbose=False
    )

    print("   [OK] Executor created")

    # =========================================================================
    # 2. Start counter process
    # =========================================================================
    print("\n2. Starting counter process...")

    stop_event = mp.Event()
    counter_proc = mp.Process(
        target=counter_process_target,
        args=(str(counter_file), 2.0, 25, stop_event)
    )
    counter_proc.start()
    print("   [OK] Counter process started (incrementing every 2 seconds)")

    # =========================================================================
    # 3. Run monitor with run_async() and router
    # =========================================================================
    print("\n3. Running monitor with run_async() + router...")
    print("   (Monitor will poll until count % 20 == 0, then trigger action)")
    print()

    # Create initial monitor task
    initial_task = Task(
        callable=monitor_iteration,  # Top-level function - picklable
        task_id="monitor_start"
    )

    # Create router (closure is fine - runs in main process)
    router = create_router(target_divisor=20)

    start_time = time.time()

    # Run with router mode
    result = executor.run_async(
        [initial_task],
        router=router,  # Router mode!
        depth_first=True
    )

    elapsed = time.time() - start_time

    # =========================================================================
    # 4. Results
    # =========================================================================
    print(f"\n4. Results (completed in {elapsed:.1f}s)...")
    print(f"   Final result: {result}")

    # =========================================================================
    # 5. Cleanup
    # =========================================================================
    print("\n5. Cleanup...")

    stop_event.set()
    counter_proc.join(timeout=5.0)
    if counter_proc.is_alive():
        counter_proc.terminate()

    executor.stop()
    queue_service.close()

    # Remove temp file
    if counter_file.exists():
        counter_file.unlink()

    print("   [OK] Complete")

    print("\n" + "=" * 80)
    print("[OK] Example completed successfully!")
    print("=" * 80)
    print("""
Key Takeaways:
- Router mode: tasks return just result, router decides next_tasks
- Router runs in MAIN PROCESS: can use closures and local state
- Task functions must be top-level (picklable for multiprocessing)
- Router pattern separates execution (workers) from orchestration (main)
- This enables complex workflows with true process isolation

When to use Router Mode:
- Multiprocessing (closures can't cross process boundaries)
- Complex routing logic that needs access to shared state
- When you want to keep orchestration logic centralized
- Integration with WorkGraph (router is auto-generated)
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
