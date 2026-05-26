"""
Test Task Module

Tests for:
- TaskStatus: Enum for task execution status
- Task: Wrapper for callables with task metadata
- TaskResult: Container for execution results

Prerequisites:
    No external dependencies (uses standard library)

Usage:
    python test_task.py
"""

import sys
import uuid
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / 'src'))

from python_utils.mp_utils.task import Task, TaskState, TaskStatus


# =============================================================================
# TaskStatus Tests
# =============================================================================

def test_task_status_values():
    """Test TaskStatus enum values."""
    print("\n" + "=" * 80)
    print("TEST 1: TaskStatus Enum Values")
    print("=" * 80)

    # Check all expected values exist
    assert TaskStatus.PENDING.value == 'pending', "PENDING should be 'pending'"
    print(f"[OK] TaskStatus.PENDING = '{TaskStatus.PENDING.value}'")

    assert TaskStatus.RUNNING.value == 'running', "RUNNING should be 'running'"
    print(f"[OK] TaskStatus.RUNNING = '{TaskStatus.RUNNING.value}'")

    assert TaskStatus.COMPLETED.value == 'completed', "COMPLETED should be 'completed'"
    print(f"[OK] TaskStatus.COMPLETED = '{TaskStatus.COMPLETED.value}'")

    assert TaskStatus.FAILED.value == 'failed', "FAILED should be 'failed'"
    print(f"[OK] TaskStatus.FAILED = '{TaskStatus.FAILED.value}'")

    # Check READY status (added for queue-based execution)
    assert TaskStatus.READY.value == 'ready', "READY should be 'ready'"
    print(f"[OK] TaskStatus.READY = '{TaskStatus.READY.value}'")

    # Check enum count (5 statuses: PENDING, READY, RUNNING, COMPLETED, FAILED)
    assert len(TaskStatus) == 5, f"Expected 5 status values, got {len(TaskStatus)}"
    print(f"[OK] Total status values: {len(TaskStatus)}")

    return True


def test_task_status_comparison():
    """Test TaskStatus comparison."""
    print("\n" + "=" * 80)
    print("TEST 2: TaskStatus Comparison")
    print("=" * 80)

    status1 = TaskStatus.COMPLETED
    status2 = TaskStatus.COMPLETED
    status3 = TaskStatus.FAILED

    assert status1 == status2, "Same status should be equal"
    print(f"[OK] TaskStatus.COMPLETED == TaskStatus.COMPLETED")

    assert status1 != status3, "Different status should not be equal"
    print(f"[OK] TaskStatus.COMPLETED != TaskStatus.FAILED")

    # Test lookup by value
    assert TaskStatus('completed') == TaskStatus.COMPLETED
    print(f"[OK] TaskStatus('completed') == TaskStatus.COMPLETED")

    return True


# =============================================================================
# Task Tests
# =============================================================================

def test_task_creation_simple():
    """Test simple task creation."""
    print("\n" + "=" * 80)
    print("TEST 3: Simple Task Creation")
    print("=" * 80)

    def simple_func():
        return 42

    task = Task(callable=simple_func)

    # Check callable is stored
    assert task._callable == simple_func
    print(f"[OK] Callable stored correctly")

    # Check task_id is auto-generated UUID
    try:
        uuid.UUID(task.task_id)
        print(f"[OK] Auto-generated task_id is valid UUID: {task.task_id}")
    except ValueError:
        print(f"[X] Invalid UUID: {task.task_id}")
        return False

    # Check name is extracted from function
    assert task.name == 'simple_func', f"Expected 'simple_func', got {task.name}"
    print(f"[OK] Name extracted from callable: {task.name}")

    # Check default args and kwargs
    assert task.args == (), f"Expected empty args, got {task.args}"
    assert task.kwargs == {}, f"Expected empty kwargs, got {task.kwargs}"
    print(f"[OK] Default args=() and kwargs={{}}")

    return True


def test_task_creation_with_args():
    """Test task creation with arguments."""
    print("\n" + "=" * 80)
    print("TEST 4: Task Creation with Arguments")
    print("=" * 80)

    def add(a, b, c=0):
        return a + b + c

    task = Task(
        callable=add,
        args=(1, 2),
        kwargs={'c': 3}
    )

    assert task.args == (1, 2), f"Expected (1, 2), got {task.args}"
    print(f"[OK] Args stored: {task.args}")

    assert task.kwargs == {'c': 3}, f"Expected {{'c': 3}}, got {task.kwargs}"
    print(f"[OK] Kwargs stored: {task.kwargs}")

    return True


def test_task_creation_custom_id_and_name():
    """Test task creation with custom ID and name."""
    print("\n" + "=" * 80)
    print("TEST 5: Task Creation with Custom ID and Name")
    print("=" * 80)

    def my_func():
        pass

    task = Task(
        callable=my_func,
        task_id='custom-task-123',
        name='My Custom Task'
    )

    assert task.task_id == 'custom-task-123', f"Expected 'custom-task-123', got {task.task_id}"
    print(f"[OK] Custom task_id: {task.task_id}")

    assert task.name == 'My Custom Task', f"Expected 'My Custom Task', got {task.name}"
    print(f"[OK] Custom name: {task.name}")

    return True


def test_task_execute_no_args():
    """Test task execution without arguments."""
    print("\n" + "=" * 80)
    print("TEST 6: Task Execution (No Args)")
    print("=" * 80)

    def get_answer():
        return 42

    task = Task(callable=get_answer)
    result = task.execute()

    assert result == 42, f"Expected 42, got {result}"
    print(f"[OK] Task executed, result: {result}")

    return True


def test_task_execute_with_args():
    """Test task execution with positional arguments."""
    print("\n" + "=" * 80)
    print("TEST 7: Task Execution (With Args)")
    print("=" * 80)

    def multiply(a, b):
        return a * b

    task = Task(callable=multiply, args=(6, 7))
    result = task.execute()

    assert result == 42, f"Expected 42, got {result}"
    print(f"[OK] Task executed with args, result: {result}")

    return True


def test_task_execute_with_kwargs():
    """Test task execution with keyword arguments."""
    print("\n" + "=" * 80)
    print("TEST 8: Task Execution (With Kwargs)")
    print("=" * 80)

    def greet(name, greeting='Hello'):
        return f"{greeting}, {name}!"

    task = Task(
        callable=greet,
        args=('World',),
        kwargs={'greeting': 'Hi'}
    )
    result = task.execute()

    assert result == 'Hi, World!', f"Expected 'Hi, World!', got {result}"
    print(f"[OK] Task executed with kwargs, result: {result}")

    return True


def test_task_execute_lambda():
    """Test task execution with lambda function."""
    print("\n" + "=" * 80)
    print("TEST 9: Task Execution (Lambda)")
    print("=" * 80)

    task = Task(callable=lambda x: x ** 2, args=(5,))
    result = task.execute()

    assert result == 25, f"Expected 25, got {result}"
    print(f"[OK] Lambda task executed, result: {result}")

    # Lambda doesn't have __name__, check name extraction
    print(f"[OK] Lambda name: {task.name}")

    return True


def test_task_execute_raises_exception():
    """Test task execution that raises an exception."""
    print("\n" + "=" * 80)
    print("TEST 10: Task Execution (Raises Exception)")
    print("=" * 80)

    def failing_func():
        raise ValueError("Intentional error")

    task = Task(callable=failing_func)

    try:
        task.execute()
        print(f"[X] Should have raised ValueError")
        return False
    except ValueError as e:
        print(f"[OK] Task raised ValueError: {e}")

    return True


def test_task_validation_non_callable():
    """Test task validation rejects non-callables."""
    print("\n" + "=" * 80)
    print("TEST 11: Task Validation (Non-Callable)")
    print("=" * 80)

    try:
        Task(callable="not a function")
        print(f"[X] Should have raised ValueError")
        return False
    except ValueError as e:
        print(f"[OK] ValueError raised: {e}")

    try:
        Task(callable=42)
        print(f"[X] Should have raised ValueError")
        return False
    except ValueError as e:
        print(f"[OK] ValueError raised for int: {e}")

    try:
        Task(callable=[1, 2, 3])
        print(f"[X] Should have raised ValueError")
        return False
    except ValueError as e:
        print(f"[OK] ValueError raised for list: {e}")

    return True


def test_task_repr():
    """Test task string representation."""
    print("\n" + "=" * 80)
    print("TEST 12: Task __repr__")
    print("=" * 80)

    def my_func():
        pass

    task = Task(callable=my_func, task_id='test-id', name='Test Task')
    repr_str = repr(task)

    assert 'test-id' in repr_str, f"task_id should be in repr: {repr_str}"
    assert 'Test Task' in repr_str, f"name should be in repr: {repr_str}"
    print(f"[OK] repr(task): {repr_str}")

    return True


def test_task_callable_class():
    """Test task with callable class instance."""
    print("\n" + "=" * 80)
    print("TEST 13: Task with Callable Class")
    print("=" * 80)

    class Multiplier:
        def __init__(self, factor):
            self.factor = factor

        def __call__(self, x):
            return x * self.factor

    multiplier = Multiplier(10)
    task = Task(callable=multiplier, args=(5,))
    result = task.execute()

    assert result == 50, f"Expected 50, got {result}"
    print(f"[OK] Callable class executed, result: {result}")
    print(f"[OK] Task name: {task.name}")

    return True


# =============================================================================
# TaskResult Tests
# =============================================================================

def test_task_result_creation():
    """Test TaskResult creation."""
    print("\n" + "=" * 80)
    print("TEST 14: TaskResult Creation")
    print("=" * 80)

    result = TaskState(
        task_id='task-123',
        result=42,
        status=TaskStatus.COMPLETED,
        worker_id=0,
        start_time=1000.0,
        end_time=1001.5,
        execution_time=1.5
    )

    assert result.task_id == 'task-123'
    print(f"[OK] task_id: {result.task_id}")

    assert result.result == 42
    print(f"[OK] result: {result.result}")

    assert result.status == TaskStatus.COMPLETED
    print(f"[OK] status: {result.status}")

    assert result.worker_id == 0
    print(f"[OK] worker_id: {result.worker_id}")

    assert result.start_time == 1000.0
    print(f"[OK] start_time: {result.start_time}")

    assert result.end_time == 1001.5
    print(f"[OK] end_time: {result.end_time}")

    assert result.execution_time == 1.5
    print(f"[OK] execution_time: {result.execution_time}")

    return True


def test_task_result_defaults():
    """Test TaskResult default values."""
    print("\n" + "=" * 80)
    print("TEST 15: TaskResult Default Values")
    print("=" * 80)

    result = TaskState(task_id='task-456')

    assert result.result is None, f"Expected None, got {result.result}"
    print(f"[OK] Default result: {result.result}")

    # Default status is now PENDING (changed from COMPLETED for queue-based execution)
    assert result.status == TaskStatus.PENDING
    print(f"[OK] Default status: {result.status}")

    assert result.exception is None
    print(f"[OK] Default exception: {result.exception}")

    # New fields for queue-based execution
    assert result.next_tasks == []
    print(f"[OK] Default next_tasks: {result.next_tasks}")

    assert result.input_args == ()
    print(f"[OK] Default input_args: {result.input_args}")

    assert result.input_kwargs == {}
    print(f"[OK] Default input_kwargs: {result.input_kwargs}")

    assert result.worker_id == 0
    print(f"[OK] Default worker_id: {result.worker_id}")

    assert result.start_time == 0.0
    print(f"[OK] Default start_time: {result.start_time}")

    assert result.end_time == 0.0
    print(f"[OK] Default end_time: {result.end_time}")

    assert result.execution_time == 0.0
    print(f"[OK] Default execution_time: {result.execution_time}")

    return True


def test_task_result_is_success():
    """Test TaskResult.is_success() method."""
    print("\n" + "=" * 80)
    print("TEST 16: TaskResult.is_success()")
    print("=" * 80)

    # Successful result
    success_result = TaskState(
        task_id='task-success',
        result=42,
        status=TaskStatus.COMPLETED
    )
    assert success_result.is_success() is True
    print(f"[OK] COMPLETED result.is_success() = True")

    # Failed result
    failed_result = TaskState(
        task_id='task-failed',
        status=TaskStatus.FAILED,
        exception=ValueError("Error")
    )
    assert failed_result.is_success() is False
    print(f"[OK] FAILED result.is_success() = False")

    # Pending result
    pending_result = TaskState(
        task_id='task-pending',
        status=TaskStatus.PENDING
    )
    assert pending_result.is_success() is False
    print(f"[OK] PENDING result.is_success() = False")

    # Running result
    running_result = TaskState(
        task_id='task-running',
        status=TaskStatus.RUNNING
    )
    assert running_result.is_success() is False
    print(f"[OK] RUNNING result.is_success() = False")

    return True


def test_task_result_with_exception():
    """Test TaskResult with exception."""
    print("\n" + "=" * 80)
    print("TEST 17: TaskResult with Exception")
    print("=" * 80)

    exception = ValueError("Something went wrong")
    result = TaskState(
        task_id='task-error',
        status=TaskStatus.FAILED,
        exception=exception,
        execution_time=0.1
    )

    assert result.status == TaskStatus.FAILED
    print(f"[OK] status: {result.status}")

    assert result.exception is exception
    print(f"[OK] exception stored: {result.exception}")

    assert result.result is None
    print(f"[OK] result is None for failed task")

    assert not result.is_success()
    print(f"[OK] is_success() returns False")

    return True


def test_task_result_repr():
    """Test TaskResult string representation."""
    print("\n" + "=" * 80)
    print("TEST 18: TaskResult __repr__")
    print("=" * 80)

    result = TaskState(
        task_id='task-repr-test',
        status=TaskStatus.COMPLETED,
        worker_id=5,
        execution_time=1.2345
    )
    repr_str = repr(result)

    assert 'task-repr-test' in repr_str
    assert 'completed' in repr_str
    assert 'worker_id=5' in repr_str
    assert '1.2345' in repr_str
    print(f"[OK] repr(result): {repr_str}")

    return True


def test_task_result_various_result_types():
    """Test TaskResult with various result types."""
    print("\n" + "=" * 80)
    print("TEST 19: TaskResult with Various Result Types")
    print("=" * 80)

    test_cases = [
        ("string", "hello world"),
        ("integer", 42),
        ("float", 3.14159),
        ("list", [1, 2, 3]),
        ("dict", {'key': 'value'}),
        ("tuple", (1, 2, 3)),
        ("None", None),
        ("nested", {'nested': {'data': [1, 2, {'x': 'y'}]}}),
    ]

    for name, value in test_cases:
        result = TaskState(task_id=f'task-{name}', result=value)
        assert result.result == value, f"Failed for {name}: expected {value}, got {result.result}"
        print(f"[OK] {name}: {value}")

    return True


# =============================================================================
# Integration Tests
# =============================================================================

def test_task_result_integration():
    """Test Task and TaskResult integration."""
    print("\n" + "=" * 80)
    print("TEST 20: Task and TaskResult Integration")
    print("=" * 80)

    import time

    def compute_sum(numbers):
        return sum(numbers)

    # Create and execute task
    task = Task(
        callable=compute_sum,
        task_id='integration-test',
        args=([1, 2, 3, 4, 5],)
    )

    start_time = time.time()
    result_value = task.execute()
    end_time = time.time()

    # Create result
    result = TaskState(
        task_id=task.task_id,
        result=result_value,
        status=TaskStatus.COMPLETED,
        worker_id=0,
        start_time=start_time,
        end_time=end_time,
        execution_time=end_time - start_time
    )

    assert result.task_id == task.task_id
    print(f"[OK] Task ID matches: {result.task_id}")

    assert result.result == 15
    print(f"[OK] Result value: {result.result}")

    assert result.is_success()
    print(f"[OK] Task completed successfully")

    assert result.execution_time >= 0
    print(f"[OK] Execution time: {result.execution_time:.6f}s")

    return True


# =============================================================================
# Test Runner
# =============================================================================

def run_all_tests():
    """Run all tests."""
    print("""
==============================================================================
                        Task Module Tests
==============================================================================
""")

    tests = [
        # TaskStatus tests
        ("TaskStatus Enum Values", test_task_status_values),
        ("TaskStatus Comparison", test_task_status_comparison),

        # Task tests
        ("Simple Task Creation", test_task_creation_simple),
        ("Task Creation with Args", test_task_creation_with_args),
        ("Task Creation with Custom ID/Name", test_task_creation_custom_id_and_name),
        ("Task Execution (No Args)", test_task_execute_no_args),
        ("Task Execution (With Args)", test_task_execute_with_args),
        ("Task Execution (With Kwargs)", test_task_execute_with_kwargs),
        ("Task Execution (Lambda)", test_task_execute_lambda),
        ("Task Execution (Raises Exception)", test_task_execute_raises_exception),
        ("Task Validation (Non-Callable)", test_task_validation_non_callable),
        ("Task __repr__", test_task_repr),
        ("Task with Callable Class", test_task_callable_class),

        # TaskResult tests
        ("TaskResult Creation", test_task_result_creation),
        ("TaskResult Default Values", test_task_result_defaults),
        ("TaskResult.is_success()", test_task_result_is_success),
        ("TaskResult with Exception", test_task_result_with_exception),
        ("TaskResult __repr__", test_task_result_repr),
        ("TaskResult Various Result Types", test_task_result_various_result_types),

        # Integration tests
        ("Task and TaskResult Integration", test_task_result_integration),
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
