"""
Single Thread Executor Example

This demonstrates basic queue-based task execution with SingleThreadExecutor:
- Creating an executor with input/output queues
- Submitting tasks to be executed
- Running the executor (blocking vs non-blocking)
- Collecting results from the output queue

Use Case:
    When you need sequential task processing with queue-based input/output,
    such as processing items from a message queue one at a time.

Prerequisites:
    No external dependencies (uses ThreadQueueService)

Usage:
    python example_single_thread_executor.py
"""

from resolve_path import resolve_path
resolve_path()  # Add project src to sys.path

import time
import threading
from python_utils.mp_utils.task import Task, TaskStatus
from python_utils.mp_utils.queued_executor import SingleThreadExecutor
from python_utils.service_utils.queue_service.thread_queue_service import ThreadQueueService


# =============================================================================
# Define some example task functions
# =============================================================================

def process_order(order_id, customer_name):
    """Simulate processing an order."""
    time.sleep(0.1)  # Simulate some work
    return {
        'order_id': order_id,
        'customer': customer_name,
        'status': 'processed',
        'timestamp': time.time()
    }


def calculate_discount(price, discount_percent):
    """Calculate discounted price."""
    discount_amount = price * (discount_percent / 100)
    final_price = price - discount_amount
    return {
        'original': price,
        'discount': discount_amount,
        'final': final_price
    }


def send_notification(user_id, message):
    """Simulate sending a notification."""
    time.sleep(0.05)  # Simulate network delay
    return f"Notification sent to user {user_id}: {message}"


def main():
    print("""
==============================================================================
             SingleThreadExecutor Usage Example
==============================================================================

This example shows how to use SingleThreadExecutor for sequential task
processing with queue-based input and output.
""")

    # =========================================================================
    # 1. Setup: Create queue service and executor
    # =========================================================================
    print("1. Setting up the executor...")

    # Create the queue service (manages input and output queues)
    queue_service = ThreadQueueService()

    # Create the executor
    # - input_queue_id: where tasks are submitted
    # - output_queue_id: where results appear
    executor = SingleThreadExecutor(
        input_queue_service=queue_service,
        output_queue_service=queue_service,
        input_queue_id='task_queue',
        output_queue_id='result_queue',
        name='OrderProcessor',
        verbose=False  # Set to True to see worker messages
    )

    print(f"   [OK] Executor created: {executor.name}")
    print(f"   [OK] Input queue: task_queue")
    print(f"   [OK] Output queue: result_queue")

    # =========================================================================
    # 2. Submit tasks to the input queue
    # =========================================================================
    print("\n2. Submitting tasks to the queue...")

    # Create and submit tasks
    tasks = [
        Task(callable=process_order, args=(1001, 'Alice'), name='Order-1001'),
        Task(callable=process_order, args=(1002, 'Bob'), name='Order-1002'),
        Task(callable=calculate_discount, args=(100.0, 15), name='Discount-Calc'),
        Task(callable=send_notification, args=(42, 'Your order is ready!'), name='Notify-42'),
        Task(callable=process_order, args=(1003, 'Charlie'), name='Order-1003'),
    ]

    for task in tasks:
        task_id = executor.submit(task)
        print(f"   [OK] Submitted: {task.name} (ID: {task_id[:8]}...)")

    print(f"\n   Queue size: {queue_service.size('task_queue')} tasks waiting")

    # =========================================================================
    # 3. Run the executor (non-blocking mode)
    # =========================================================================
    print("\n3. Starting the executor in non-blocking mode...")

    # Start the executor - it will process tasks in a background thread
    active_flag = executor.start()

    print(f"   [OK] Executor started")
    print(f"   [OK] is_running: {executor.is_running}")

    # =========================================================================
    # 4. Collect results as they complete
    # =========================================================================
    print("\n4. Collecting results...")

    results = []
    for i in range(len(tasks)):
        # Wait for each result (with timeout)
        result = executor.get_result(blocking=True, timeout=5.0)

        if result:
            results.append(result)
            status = "SUCCESS" if result.is_success() else "FAILED"
            print(f"   [{i+1}] {status}: Task completed in {result.execution_time:.4f}s")
            print(f"        Result: {result.result}")

    print(f"\n   Total results: {len(results)}")

    # =========================================================================
    # 5. Check executor statistics
    # =========================================================================
    print("\n5. Executor statistics...")

    stats = executor.get_stats()
    print(f"   Name: {stats['name']}")
    print(f"   Workers: {stats['num_workers']}")
    print(f"   Running: {stats['is_running']}")
    print(f"   Input queue size: {stats['input_queue_size']}")
    print(f"   Output queue size: {stats['output_queue_size']}")

    # =========================================================================
    # 6. Stop the executor gracefully
    # =========================================================================
    print("\n6. Stopping the executor...")

    all_stopped = executor.stop(active_flag, timeout=2.0)
    print(f"   [OK] Executor stopped: {all_stopped}")
    print(f"   [OK] is_running: {executor.is_running}")

    # =========================================================================
    # 7. Summary of results
    # =========================================================================
    print("\n7. Summary of processed tasks...")

    successful = sum(1 for r in results if r.is_success())
    failed = len(results) - successful

    print(f"   Total tasks: {len(results)}")
    print(f"   Successful: {successful}")
    print(f"   Failed: {failed}")

    if results:
        avg_time = sum(r.execution_time for r in results) / len(results)
        print(f"   Average execution time: {avg_time:.4f}s")

    # =========================================================================
    # 8. Cleanup
    # =========================================================================
    print("\n8. Cleaning up...")

    queue_service.delete('task_queue')
    queue_service.delete('result_queue')
    queue_service.close()

    print("   [OK] Queues deleted")
    print("   [OK] Service closed")

    print("\n" + "=" * 80)
    print("[OK] Example completed successfully!")
    print("=" * 80 + "\n")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n[X] Error: {e}")
        import traceback
        traceback.print_exc()
        import sys
        sys.exit(1)
