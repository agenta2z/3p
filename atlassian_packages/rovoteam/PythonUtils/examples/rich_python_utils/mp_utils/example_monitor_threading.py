"""
Monitor Pattern with Threading (run_async Wrapper Mode)

This example demonstrates the queue-based monitor pattern using threads:
- A background thread increments a counter in a file every 2 seconds
- A monitor task watches the file and triggers actions when count % 20 == 0
- Uses wrapper mode (router=None) which allows closures

Scenario:
    Imagine a long-running process that writes progress to a file.
    You want to monitor this progress and take action at certain milestones
    (e.g., send notifications, trigger dependent tasks).

Key Concepts:
    - run_async() with wrapper mode: tasks return (result, next_tasks)
    - Self-loop pattern: monitor re-queues itself until condition is met
    - ThreadQueueService: simple in-memory queue for threading
    - No pickling required: closures work because everything is in same process

Usage:
    python example_monitor_threading.py
"""

from resolve_path import resolve_path
resolve_path()

import os
import time
import threading
import tempfile
from pathlib import Path

from python_utils.mp_utils.task import Task
from python_utils.mp_utils.queued_executor import QueuedThreadPoolExecutor
from python_utils.service_utils.queue_service.thread_queue_service import ThreadQueueService


# =============================================================================
# Counter Thread (Simulates a long-running process)
# =============================================================================

class CounterThread(threading.Thread):
    """Background thread that increments a counter in a file every 2 seconds."""

    def __init__(self, counter_file: Path, interval: float = 2.0, max_count: int = 100):
        super().__init__(daemon=True)
        self.counter_file = counter_file
        self.interval = interval
        self.max_count = max_count
        self._stop_event = threading.Event()

    def run(self):
        """Increment counter and write to file."""
        count = 0
        while count < self.max_count and not self._stop_event.is_set():
            count += 1
            self.counter_file.write_text(str(count))
            print(f"   [Counter] Written count={count} to file")
            self._stop_event.wait(self.interval)

        print(f"   [Counter] Finished at count={count}")

    def stop(self):
        self._stop_event.set()


# =============================================================================
# Monitor Tasks (Wrapper Mode - returns (result, next_tasks) tuple)
# =============================================================================

def create_monitor_task(counter_file: Path, target_divisor: int = 20):
    """
    Create a monitor task that checks if count % target_divisor == 0.

    This uses a closure to capture counter_file and target_divisor.
    Closures work in wrapper mode because everything runs in the same process.

    Returns:
        A callable that returns (result, next_tasks) tuple
    """
    poll_interval = 0.5  # Check every 0.5 seconds

    def monitor_iteration():
        """
        Single iteration of the monitor.

        Returns:
            (result, next_tasks) tuple:
            - If condition met: (milestone_info, [action_task])
            - If not met: (status_info, [self_task]) to continue monitoring
        """
        # Read current count from file
        try:
            current_count = int(counter_file.read_text().strip())
        except (FileNotFoundError, ValueError):
            current_count = 0

        print(f"   [Monitor] Checking count={current_count}")

        # Check if milestone reached
        if current_count > 0 and current_count % target_divisor == 0:
            # Condition met! Return action task as next_task
            print(f"   [Monitor] Milestone reached: count={current_count} (divisible by {target_divisor})")

            milestone_result = {
                'status': 'milestone_reached',
                'count': current_count,
                'divisor': target_divisor
            }

            # Create action task to handle the milestone
            action_task = Task(
                callable=create_action_task(current_count),
                task_id=f"action_{current_count}"
            )

            return (milestone_result, [action_task])

        else:
            # Condition not met - continue monitoring
            time.sleep(poll_interval)

            status_result = {
                'status': 'monitoring',
                'count': current_count
            }

            # Re-queue self to continue monitoring (self-loop pattern)
            self_task = Task(
                callable=monitor_iteration,  # Closure - works in threads!
                task_id=f"monitor_{current_count + 1}"
            )

            return (status_result, [self_task])

    return monitor_iteration


def create_action_task(count: int):
    """
    Create an action task that runs when milestone is reached.

    This could be: sending a notification, triggering another job,
    updating a dashboard, etc.
    """
    def action():
        print(f"   [Action] Processing milestone at count={count}")
        print(f"   [Action] Simulating work (e.g., send notification, update dashboard)...")
        time.sleep(0.5)  # Simulate some work

        result = {
            'action': 'milestone_processed',
            'count': count,
            'timestamp': time.time()
        }
        print(f"   [Action] Completed!")

        # This is a leaf task - no next_tasks
        return (result, [])

    return action


# =============================================================================
# Main Example
# =============================================================================

def main():
    print("""
==============================================================================
        Monitor Pattern with Threading (Wrapper Mode)
==============================================================================

This example shows:
1. A background thread incrementing a counter every 2 seconds
2. A monitor task watching for count % 20 == 0
3. An action task triggered when the condition is met

Using wrapper mode (router=None):
- Tasks return (result, next_tasks) tuple
- Closures work because everything is in the same process
- Simple and intuitive for single-process applications
""")

    # =========================================================================
    # 1. Setup
    # =========================================================================
    print("1. Setup...")

    # Create temporary file for counter
    counter_file = Path(tempfile.gettempdir()) / "monitor_example_counter.txt"
    counter_file.write_text("0")
    print(f"   Counter file: {counter_file}")

    # Create queue service and executor
    queue_service = ThreadQueueService()
    executor = QueuedThreadPoolExecutor(
        input_queue_service=queue_service,
        output_queue_service=queue_service,
        input_queue_id='monitor_in',
        output_queue_id='monitor_out',
        num_workers=2,
        name='MonitorPool',
        verbose=False
    )

    print("   [OK] Executor created with 2 worker threads")

    # =========================================================================
    # 2. Start counter thread
    # =========================================================================
    print("\n2. Starting counter thread...")

    counter_thread = CounterThread(
        counter_file=counter_file,
        interval=2.0,
        max_count=25  # Will reach 20 milestone
    )
    counter_thread.start()
    print("   [OK] Counter thread started (incrementing every 2 seconds)")

    # =========================================================================
    # 3. Run monitor with run_async()
    # =========================================================================
    print("\n3. Running monitor with run_async()...")
    print("   (Monitor will poll until count % 20 == 0, then trigger action)")
    print()

    # Create initial monitor task
    monitor_task = Task(
        callable=create_monitor_task(counter_file, target_divisor=20),
        task_id="monitor_start"
    )

    start_time = time.time()

    # Run the monitor - it will self-loop until condition is met
    result = executor.run_async(
        [monitor_task],
        depth_first=True  # Process next iteration before other tasks
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

    counter_thread.stop()
    counter_thread.join(timeout=5.0)
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
- Wrapper mode: tasks return (result, next_tasks) tuple
- Self-loop pattern: monitor re-queues itself to continue polling
- Closures work in threading (no pickling needed)
- run_async() handles the queue management automatically
- depth_first=True ensures monitor iterations run in order
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
