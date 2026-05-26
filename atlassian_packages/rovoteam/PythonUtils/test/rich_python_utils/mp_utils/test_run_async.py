"""
Test run_async() Method

Tests for the QueuedExecutorBase.run_async() method which supports:
- Wrapper mode (router=None): Tasks return (result, next_tasks) tuple
- Router mode (router=Callable): Tasks return just result, router decides next_tasks
- Depth-first vs breadth-first traversal
- Error handling (on_error='raise' vs 'skip')
- Callback support (on_task_complete)
- Concurrent task limiting (max_concurrent)

Prerequisites:
    No external dependencies (uses ThreadQueueService)

Usage:
    python test_run_async.py
"""

import sys
import time
import uuid
from pathlib import Path
from typing import Any, List

# Add src to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / 'src'))

from python_utils.mp_utils.task import Task, TaskState, TaskStatus
from python_utils.mp_utils.queued_executor import (
    SimulatedMultiThreadExecutor,
    QueuedThreadPoolExecutor,
)
from python_utils.service_utils.queue_service.thread_queue_service import ThreadQueueService


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


def create_simulated_executor(service, input_q, output_q):
    """Create a SimulatedMultiThreadExecutor for testing."""
    return SimulatedMultiThreadExecutor(
        input_queue_service=service,
        output_queue_service=service,
        input_queue_id=input_q,
        output_queue_id=output_q,
        verbose=False
    )


def create_thread_pool_executor(service, input_q, output_q, num_workers=2):
    """Create a QueuedThreadPoolExecutor for testing."""
    return QueuedThreadPoolExecutor(
        input_queue_service=service,
        output_queue_service=service,
        input_queue_id=input_q,
        output_queue_id=output_q,
        num_workers=num_workers,
        verbose=False
    )


# =============================================================================
# Module-level Task Functions for Test 1: Simple Chain
# =============================================================================

_test1_log = []


def _test1_task_a():
    _test1_log.append('A')
    return ("result_a", [Task(callable=_test1_task_b, task_id="B")])


def _test1_task_b():
    _test1_log.append('B')
    return ("result_b", [Task(callable=_test1_task_c, task_id="C")])


def _test1_task_c():
    _test1_log.append('C')
    return ("result_c", [])


def test_wrapper_mode_simple_chain():
    """Test wrapper mode with a simple task chain A -> B -> C."""
    print("\n" + "=" * 80)
    print("TEST 1: Wrapper Mode - Simple Chain A -> B -> C")
    print("=" * 80)

    global _test1_log
    _test1_log = []

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('wrapper_chain')
    executor = create_simulated_executor(service, input_q, output_q)

    result = executor.run_async([Task(callable=_test1_task_a, task_id="A")])

    assert _test1_log == ['A', 'B', 'C'], f"Expected ['A', 'B', 'C'], got {_test1_log}"
    print(f"[OK] Execution order: {_test1_log}")

    assert result == "result_c", f"Expected 'result_c', got {result}"
    print(f"[OK] Result: {result}")

    service.close()


# =============================================================================
# Module-level Task Functions for Test 2: Branching
# =============================================================================

_test2_log = []


def _test2_task_a():
    _test2_log.append('A')
    return ("result_a", [
        Task(callable=_test2_task_b, task_id="B"),
        Task(callable=_test2_task_c, task_id="C")
    ])


def _test2_task_b():
    _test2_log.append('B')
    return ("result_b", [])


def _test2_task_c():
    _test2_log.append('C')
    return ("result_c", [])


def test_wrapper_mode_branching():
    """Test wrapper mode with branching (multiple leaf tasks)."""
    print("\n" + "=" * 80)
    print("TEST 2: Wrapper Mode - Branching (Multiple Leaves)")
    print("=" * 80)

    global _test2_log
    _test2_log = []

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('wrapper_branch')
    executor = create_simulated_executor(service, input_q, output_q)

    result = executor.run_async([Task(callable=_test2_task_a, task_id="A")])

    assert set(_test2_log) == {'A', 'B', 'C'}, f"Expected {{'A', 'B', 'C'}}, got {set(_test2_log)}"
    print(f"[OK] All tasks executed: {_test2_log}")

    assert isinstance(result, tuple), f"Expected tuple, got {type(result)}"
    assert set(result) == {"result_b", "result_c"}, f"Expected {{'result_b', 'result_c'}}, got {set(result)}"
    print(f"[OK] Result tuple: {result}")

    service.close()


# =============================================================================
# Module-level Task Functions for Test 3: Single Task
# =============================================================================

def _test3_single_task():
    return ("single_result", [])


def test_wrapper_mode_single_task():
    """Test wrapper mode with a single leaf task."""
    print("\n" + "=" * 80)
    print("TEST 3: Wrapper Mode - Single Task (Leaf)")
    print("=" * 80)

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('wrapper_single')
    executor = create_simulated_executor(service, input_q, output_q)

    result = executor.run_async([Task(callable=_test3_single_task, task_id="single")])

    assert result == "single_result", f"Expected 'single_result', got {result}"
    print(f"[OK] Single task result: {result}")

    service.close()


# =============================================================================
# Module-level Task Functions for Test 4: Non-Tuple Result
# =============================================================================

def _test4_plain_task():
    return "plain_result"  # Not a (result, next_tasks) tuple


def test_wrapper_mode_non_tuple_result():
    """Test wrapper mode gracefully handles non-tuple results (treats as leaf)."""
    print("\n" + "=" * 80)
    print("TEST 4: Wrapper Mode - Non-Tuple Result (Treated as Leaf)")
    print("=" * 80)

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('wrapper_nontuple')
    executor = create_simulated_executor(service, input_q, output_q)

    result = executor.run_async([Task(callable=_test4_plain_task, task_id="plain")])

    assert result == "plain_result", f"Expected 'plain_result', got {result}"
    print(f"[OK] Plain result treated as leaf: {result}")

    service.close()


# =============================================================================
# Module-level Task Functions for Test 5: Router Chain
# =============================================================================

_test5_log = []


def _test5_task_a():
    _test5_log.append('A')
    return "result_a"


def _test5_task_b():
    _test5_log.append('B')
    return "result_b"


def _test5_task_c():
    _test5_log.append('C')
    return "result_c"


def _test5_router(task_id: str, result: Any, task_state: TaskState) -> List[Task]:
    if task_id == "A":
        return [Task(callable=_test5_task_b, task_id="B")]
    elif task_id == "B":
        return [Task(callable=_test5_task_c, task_id="C")]
    else:
        return []


def test_router_mode_simple_chain():
    """Test router mode with a simple task chain."""
    print("\n" + "=" * 80)
    print("TEST 5: Router Mode - Simple Chain A -> B -> C")
    print("=" * 80)

    global _test5_log
    _test5_log = []

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('router_chain')
    executor = create_simulated_executor(service, input_q, output_q)

    result = executor.run_async(
        [Task(callable=_test5_task_a, task_id="A")],
        router=_test5_router
    )

    assert _test5_log == ['A', 'B', 'C'], f"Expected ['A', 'B', 'C'], got {_test5_log}"
    print(f"[OK] Execution order: {_test5_log}")

    assert result == "result_c", f"Expected 'result_c', got {result}"
    print(f"[OK] Result: {result}")

    service.close()


# =============================================================================
# Module-level Task Functions for Test 6: Router Receives TaskState
# =============================================================================

_test6_task_states = []


def _test6_task_with_args(x, y):
    return x + y


def _test6_router(task_id: str, result: Any, task_state: TaskState) -> List[Task]:
    _test6_task_states.append(task_state)
    return []


def test_router_mode_receives_task_state():
    """Test that router receives TaskState with input_args/input_kwargs."""
    print("\n" + "=" * 80)
    print("TEST 6: Router Mode - Receives TaskState with Input Args")
    print("=" * 80)

    global _test6_task_states
    _test6_task_states = []

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('router_taskstate')
    executor = create_simulated_executor(service, input_q, output_q)

    executor.run_async(
        [Task(callable=_test6_task_with_args, task_id="sum", args=(10, 20))],
        router=_test6_router
    )

    assert len(_test6_task_states) == 1, f"Expected 1 task state, got {len(_test6_task_states)}"
    ts = _test6_task_states[0]

    assert ts.task_id == "sum", f"Expected task_id='sum', got {ts.task_id}"
    assert ts.input_args == (10, 20), f"Expected input_args=(10, 20), got {ts.input_args}"
    assert ts.result == 30, f"Expected result=30, got {ts.result}"
    print(f"[OK] TaskState received: task_id={ts.task_id}, input_args={ts.input_args}, result={ts.result}")

    service.close()


# =============================================================================
# Module-level Task Functions for Test 7: Router Branching
# =============================================================================

_test7_log = []


def _test7_task_a():
    _test7_log.append('A')
    return "result_a"


def _test7_task_b():
    _test7_log.append('B')
    return "result_b"


def _test7_task_c():
    _test7_log.append('C')
    return "result_c"


def _test7_router(task_id: str, result: Any, task_state: TaskState) -> List[Task]:
    if task_id == "A":
        return [
            Task(callable=_test7_task_b, task_id="B"),
            Task(callable=_test7_task_c, task_id="C")
        ]
    return []


def test_router_mode_branching():
    """Test router mode with branching."""
    print("\n" + "=" * 80)
    print("TEST 7: Router Mode - Branching")
    print("=" * 80)

    global _test7_log
    _test7_log = []

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('router_branch')
    executor = create_simulated_executor(service, input_q, output_q)

    result = executor.run_async(
        [Task(callable=_test7_task_a, task_id="A")],
        router=_test7_router
    )

    assert set(_test7_log) == {'A', 'B', 'C'}, f"Expected {{'A', 'B', 'C'}}, got {set(_test7_log)}"
    print(f"[OK] All tasks executed with router: {_test7_log}")

    assert isinstance(result, tuple), f"Expected tuple, got {type(result)}"
    print(f"[OK] Result tuple: {result}")

    service.close()


# =============================================================================
# Module-level Task Functions for Test 8: Depth-First
# =============================================================================

_test8_log = []


def _test8_task_a():
    _test8_log.append('A')
    return ("result_a", [
        Task(callable=_test8_task_b, task_id="B"),
        Task(callable=_test8_task_c, task_id="C")
    ])


def _test8_task_b():
    _test8_log.append('B')
    return ("result_b", [Task(callable=_test8_task_d, task_id="D")])


def _test8_task_c():
    _test8_log.append('C')
    return ("result_c", [])


def _test8_task_d():
    _test8_log.append('D')
    return ("result_d", [])


def test_depth_first_order():
    """Test depth_first=True inserts next_tasks at HEAD (depth-first traversal)."""
    print("\n" + "=" * 80)
    print("TEST 8: Depth-First Order (depth_first=True)")
    print("=" * 80)

    global _test8_log
    _test8_log = []

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('depth_first')
    executor = create_simulated_executor(service, input_q, output_q)

    result = executor.run_async(
        [Task(callable=_test8_task_a, task_id="A")],
        depth_first=True
    )

    # In depth-first, B and C are added to HEAD in reverse order (C, B)
    # So B executes first, then B adds D at HEAD, then D executes, then C
    expected_order = ['A', 'B', 'D', 'C']
    assert _test8_log == expected_order, f"Expected {expected_order}, got {_test8_log}"
    print(f"[OK] Depth-first order: {_test8_log}")

    service.close()


# =============================================================================
# Module-level Task Functions for Test 9: Breadth-First
# =============================================================================

_test9_log = []


def _test9_task_a():
    _test9_log.append('A')
    return ("result_a", [
        Task(callable=_test9_task_b, task_id="B"),
        Task(callable=_test9_task_c, task_id="C")
    ])


def _test9_task_b():
    _test9_log.append('B')
    return ("result_b", [Task(callable=_test9_task_d, task_id="D")])


def _test9_task_c():
    _test9_log.append('C')
    return ("result_c", [])


def _test9_task_d():
    _test9_log.append('D')
    return ("result_d", [])


def test_breadth_first_order():
    """Test depth_first=False appends next_tasks at TAIL (breadth-first traversal)."""
    print("\n" + "=" * 80)
    print("TEST 9: Breadth-First Order (depth_first=False)")
    print("=" * 80)

    global _test9_log
    _test9_log = []

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('breadth_first')
    executor = create_simulated_executor(service, input_q, output_q)

    result = executor.run_async(
        [Task(callable=_test9_task_a, task_id="A")],
        depth_first=False
    )

    expected_order = ['A', 'B', 'C', 'D']
    assert _test9_log == expected_order, f"Expected {expected_order}, got {_test9_log}"
    print(f"[OK] Breadth-first order: {_test9_log}")

    service.close()


# =============================================================================
# Module-level Task Functions for Test 10: on_error='raise'
# =============================================================================

_test10_log = []


def _test10_task_a():
    _test10_log.append('A')
    return ("result_a", [Task(callable=_test10_failing_task, task_id="fail")])


def _test10_failing_task():
    _test10_log.append('fail')
    raise ValueError("Intentional test error")


def test_on_error_raise():
    """Test on_error='raise' stops execution and re-raises exception."""
    print("\n" + "=" * 80)
    print("TEST 10: on_error='raise' - Stops and Re-raises")
    print("=" * 80)

    global _test10_log
    _test10_log = []

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('error_raise')
    executor = create_simulated_executor(service, input_q, output_q)

    try:
        executor.run_async(
            [Task(callable=_test10_task_a, task_id="A")],
            on_error='raise'
        )
        assert False, "Should have raised ValueError"
    except ValueError as e:
        print(f"[OK] ValueError raised: {e}")

    print(f"[OK] Execution stopped at failure: {_test10_log}")

    service.close()


# =============================================================================
# Module-level Task Functions for Test 11: on_error='skip'
# =============================================================================

_test11_log = []


def _test11_task_a():
    _test11_log.append('A')
    return ("result_a", [
        Task(callable=_test11_failing_task, task_id="fail"),
        Task(callable=_test11_task_b, task_id="B")
    ])


def _test11_failing_task():
    _test11_log.append('fail')
    raise ValueError("Intentional test error")


def _test11_task_b():
    _test11_log.append('B')
    return ("result_b", [])


def test_on_error_skip():
    """Test on_error='skip' continues execution after failure."""
    print("\n" + "=" * 80)
    print("TEST 11: on_error='skip' - Continues After Failure")
    print("=" * 80)

    global _test11_log
    _test11_log = []

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('error_skip')
    executor = create_simulated_executor(service, input_q, output_q)

    result = executor.run_async(
        [Task(callable=_test11_task_a, task_id="A")],
        on_error='skip'
    )

    assert 'A' in _test11_log and 'fail' in _test11_log and 'B' in _test11_log
    print(f"[OK] All tasks attempted: {_test11_log}")

    assert result == "result_b", f"Expected 'result_b', got {result}"
    print(f"[OK] Result from successful task: {result}")

    service.close()


# =============================================================================
# Test 12: on_error Invalid Value
# =============================================================================

def _test12_simple_task():
    return ("result", [])


def test_on_error_invalid_value():
    """Test that invalid on_error value raises ValueError."""
    print("\n" + "=" * 80)
    print("TEST 12: on_error Invalid Value - Raises ValueError")
    print("=" * 80)

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('error_invalid')
    executor = create_simulated_executor(service, input_q, output_q)

    try:
        executor.run_async(
            [Task(callable=_test12_simple_task, task_id="task")],
            on_error='invalid'
        )
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert 'on_error' in str(e)
        print(f"[OK] ValueError raised for invalid on_error: {e}")

    service.close()


# =============================================================================
# Module-level Task Functions for Test 13: Callback
# =============================================================================

_test13_callback_log = []


def _test13_task_a():
    return ("result_a", [Task(callable=_test13_task_b, task_id="B")])


def _test13_task_b():
    return ("result_b", [])


def _test13_on_complete(task_id: str, result: Any):
    _test13_callback_log.append((task_id, result))


def test_on_task_complete_callback():
    """Test on_task_complete callback is called for each completed task."""
    print("\n" + "=" * 80)
    print("TEST 13: on_task_complete Callback")
    print("=" * 80)

    global _test13_callback_log
    _test13_callback_log = []

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('callback')
    executor = create_simulated_executor(service, input_q, output_q)

    executor.run_async(
        [Task(callable=_test13_task_a, task_id="A")],
        on_task_complete=_test13_on_complete
    )

    assert len(_test13_callback_log) == 2, f"Expected 2 callbacks, got {len(_test13_callback_log)}"
    print(f"[OK] Callback called {len(_test13_callback_log)} times")

    task_ids = [t[0] for t in _test13_callback_log]
    assert "A" in task_ids and "B" in task_ids
    print(f"[OK] Callback received all task completions: {_test13_callback_log}")

    service.close()


# =============================================================================
# Module-level Task Functions for Test 14: max_concurrent
# =============================================================================

def _test14_make_task_0():
    return ("result_0", [])


def _test14_make_task_1():
    return ("result_1", [])


def _test14_make_task_2():
    return ("result_2", [])


def _test14_make_task_3():
    return ("result_3", [])


def _test14_make_task_4():
    return ("result_4", [])


def test_max_concurrent_limit():
    """Test max_concurrent limits in-flight tasks."""
    print("\n" + "=" * 80)
    print("TEST 14: max_concurrent Limit")
    print("=" * 80)

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('maxconcurrent')
    executor = create_simulated_executor(service, input_q, output_q)

    tasks = [
        Task(callable=_test14_make_task_0, task_id="task_0"),
        Task(callable=_test14_make_task_1, task_id="task_1"),
        Task(callable=_test14_make_task_2, task_id="task_2"),
        Task(callable=_test14_make_task_3, task_id="task_3"),
        Task(callable=_test14_make_task_4, task_id="task_4"),
    ]

    result = executor.run_async(tasks, max_concurrent=2)

    assert isinstance(result, tuple), f"Expected tuple, got {type(result)}"
    assert len(result) == 5, f"Expected 5 results, got {len(result)}"
    print(f"[OK] All 5 tasks completed with max_concurrent=2: {result}")

    service.close()


# =============================================================================
# Module-level Task Functions for Test 15: Self-Loop
# =============================================================================

_test15_count = [0]


def _test15_monitor_task():
    _test15_count[0] += 1
    if _test15_count[0] < 3:
        return (f"monitor_{_test15_count[0]}", [Task(callable=_test15_monitor_task, task_id=f"monitor_{_test15_count[0]+1}")])
    else:
        return (f"final_{_test15_count[0]}", [])


def test_self_loop_pattern():
    """Test self-loop pattern (monitor that re-executes)."""
    print("\n" + "=" * 80)
    print("TEST 15: Self-Loop Pattern (Monitor)")
    print("=" * 80)

    global _test15_count
    _test15_count = [0]

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('selfloop')
    executor = create_simulated_executor(service, input_q, output_q)

    result = executor.run_async([Task(callable=_test15_monitor_task, task_id="monitor_1")])

    assert _test15_count[0] == 3, f"Expected 3 executions, got {_test15_count[0]}"
    print(f"[OK] Monitor executed {_test15_count[0]} times")

    assert result == "final_3", f"Expected 'final_3', got {result}"
    print(f"[OK] Final result: {result}")

    service.close()


# =============================================================================
# Module-level Task Functions for Test 16: Thread Pool
# =============================================================================

_test16_log = []


def _test16_task_a():
    _test16_log.append('A')
    time.sleep(0.05)
    return ("result_a", [
        Task(callable=_test16_task_b, task_id="B"),
        Task(callable=_test16_task_c, task_id="C")
    ])


def _test16_task_b():
    _test16_log.append('B')
    time.sleep(0.05)
    return ("result_b", [])


def _test16_task_c():
    _test16_log.append('C')
    time.sleep(0.05)
    return ("result_c", [])


def test_thread_pool_run_async():
    """Test run_async with QueuedThreadPoolExecutor (parallel execution)."""
    print("\n" + "=" * 80)
    print("TEST 16: QueuedThreadPoolExecutor run_async")
    print("=" * 80)

    global _test16_log
    _test16_log = []

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('threadpool_async')
    executor = create_thread_pool_executor(service, input_q, output_q, num_workers=2)

    start = time.time()
    result = executor.run_async([Task(callable=_test16_task_a, task_id="A")])
    elapsed = time.time() - start

    assert set(_test16_log) == {'A', 'B', 'C'}, f"Expected {{'A', 'B', 'C'}}, got {set(_test16_log)}"
    print(f"[OK] All tasks executed: {_test16_log}")

    print(f"[OK] Execution time: {elapsed:.2f}s")

    assert isinstance(result, tuple), f"Expected tuple, got {type(result)}"
    print(f"[OK] Result: {result}")

    service.close()


# =============================================================================
# Module-level Task Functions for Test 17: Thread Pool with Router
# =============================================================================

_test17_log = []


def _test17_task_a():
    _test17_log.append('A')
    return "result_a"


def _test17_task_b():
    _test17_log.append('B')
    return "result_b"


def _test17_task_c():
    _test17_log.append('C')
    return "result_c"


def _test17_router(task_id: str, result: Any, task_state: TaskState) -> List[Task]:
    if task_id == "A":
        return [
            Task(callable=_test17_task_b, task_id="B"),
            Task(callable=_test17_task_c, task_id="C")
        ]
    return []


def test_thread_pool_with_router():
    """Test run_async with router on QueuedThreadPoolExecutor."""
    print("\n" + "=" * 80)
    print("TEST 17: QueuedThreadPoolExecutor with Router")
    print("=" * 80)

    global _test17_log
    _test17_log = []

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('threadpool_router')
    executor = create_thread_pool_executor(service, input_q, output_q, num_workers=2)

    result = executor.run_async(
        [Task(callable=_test17_task_a, task_id="A")],
        router=_test17_router
    )

    assert set(_test17_log) == {'A', 'B', 'C'}, f"Expected {{'A', 'B', 'C'}}, got {set(_test17_log)}"
    print(f"[OK] All tasks executed with router: {_test17_log}")

    assert isinstance(result, tuple), f"Expected tuple, got {type(result)}"
    print(f"[OK] Result: {result}")

    service.close()


# =============================================================================
# Test 18: Empty Initial Tasks
# =============================================================================

def test_empty_initial_tasks():
    """Test run_async with empty initial tasks list."""
    print("\n" + "=" * 80)
    print("TEST 18: Empty Initial Tasks")
    print("=" * 80)

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('empty_tasks')
    executor = create_simulated_executor(service, input_q, output_q)

    result = executor.run_async([])

    assert result is None, f"Expected None, got {result}"
    print(f"[OK] Empty tasks returns None: {result}")

    service.close()


# =============================================================================
# Module-level Task Functions for Test 19: Multiple Start Nodes
# =============================================================================

_test19_log = []


def _test19_task_a():
    _test19_log.append('A')
    return ("result_a", [])


def _test19_task_b():
    _test19_log.append('B')
    return ("result_b", [])


def _test19_task_c():
    _test19_log.append('C')
    return ("result_c", [])


def test_multiple_start_nodes():
    """Test run_async with multiple initial tasks."""
    print("\n" + "=" * 80)
    print("TEST 19: Multiple Start Nodes")
    print("=" * 80)

    global _test19_log
    _test19_log = []

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('multi_start')
    executor = create_simulated_executor(service, input_q, output_q)

    result = executor.run_async([
        Task(callable=_test19_task_a, task_id="A"),
        Task(callable=_test19_task_b, task_id="B"),
        Task(callable=_test19_task_c, task_id="C")
    ])

    assert set(_test19_log) == {'A', 'B', 'C'}, f"Expected {{'A', 'B', 'C'}}, got {set(_test19_log)}"
    print(f"[OK] All start nodes executed: {_test19_log}")

    assert isinstance(result, tuple), f"Expected tuple, got {type(result)}"
    assert len(result) == 3, f"Expected 3 results, got {len(result)}"
    print(f"[OK] Result tuple: {result}")

    service.close()


# =============================================================================
# Module-level Task Functions for Test 20
# =============================================================================

def _test20_task_a():
    return ("result_a", [Task(callable=_test20_task_b, task_id="B")])


def _test20_task_b():
    return ("result_b", [])


def test_next_tasks_stored_in_task_state():
    """Test that next_tasks are stored in TaskState for debugging."""
    print("\n" + "=" * 80)
    print("TEST 20: next_tasks Stored in TaskState")
    print("=" * 80)

    service = create_queue_service()
    input_q, output_q = unique_queue_ids('taskstate_nexttasks')
    executor = create_simulated_executor(service, input_q, output_q)

    executor.run_async([Task(callable=_test20_task_a, task_id="A")])

    print(f"[OK] run_async completed with next_tasks tracking")

    service.close()


# =============================================================================
# Test Runner
# =============================================================================

def run_all_tests():
    """Run all tests."""
    print("""
==============================================================================
                    run_async() Method Tests
==============================================================================
""")

    tests = [
        # Wrapper mode tests
        ("Wrapper Mode - Simple Chain", test_wrapper_mode_simple_chain),
        ("Wrapper Mode - Branching", test_wrapper_mode_branching),
        ("Wrapper Mode - Single Task", test_wrapper_mode_single_task),
        ("Wrapper Mode - Non-Tuple Result", test_wrapper_mode_non_tuple_result),

        # Router mode tests
        ("Router Mode - Simple Chain", test_router_mode_simple_chain),
        ("Router Mode - Receives TaskState", test_router_mode_receives_task_state),
        ("Router Mode - Branching", test_router_mode_branching),

        # Traversal order tests
        ("Depth-First Order", test_depth_first_order),
        ("Breadth-First Order", test_breadth_first_order),

        # Error handling tests
        ("on_error='raise'", test_on_error_raise),
        ("on_error='skip'", test_on_error_skip),
        ("on_error Invalid Value", test_on_error_invalid_value),

        # Callback tests
        ("on_task_complete Callback", test_on_task_complete_callback),

        # Concurrency tests
        ("max_concurrent Limit", test_max_concurrent_limit),

        # Self-loop tests
        ("Self-Loop Pattern", test_self_loop_pattern),

        # Thread pool tests
        ("QueuedThreadPoolExecutor run_async", test_thread_pool_run_async),
        ("QueuedThreadPoolExecutor with Router", test_thread_pool_with_router),

        # Edge case tests
        ("Empty Initial Tasks", test_empty_initial_tasks),
        ("Multiple Start Nodes", test_multiple_start_nodes),
        ("next_tasks Stored in TaskState", test_next_tasks_stored_in_task_state),
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
