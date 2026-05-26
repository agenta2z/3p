"""
Integration tests for WorkGraph with executor (Phase 4).

Tests queue-based execution using wrapper mode (threads) and router mode (multi-processing).

Note: ThreadQueueService uses multiprocessing.Manager which requires pickling,
so we use module-level functions in tests instead of closures.
"""

import uuid
import pytest
from typing import List

from python_utils.common_objects.workflow.workgraph import WorkGraph, WorkGraphNode
from python_utils.common_objects.workflow.common.result_pass_down_mode import ResultPassDownMode
from python_utils.common_objects.workflow.common.worknode_base import NextNodesSelector
from python_utils.mp_utils.queued_executor import SimulatedMultiThreadExecutor
from python_utils.service_utils.queue_service.thread_queue_service import ThreadQueueService


# =============================================================================
# Helper Functions
# =============================================================================

_test_counter = 0


def unique_queue_ids(prefix='test'):
    """Generate unique queue IDs to avoid test contamination."""
    global _test_counter
    _test_counter += 1
    unique = f"{_test_counter}_{uuid.uuid4().hex[:6]}"
    return f'{prefix}_in_{unique}', f'{prefix}_out_{unique}'


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def executor():
    """Create a SimulatedMultiThreadExecutor for testing."""
    queue_service = ThreadQueueService()
    input_id, output_id = unique_queue_ids('workgraph')
    exec = SimulatedMultiThreadExecutor(
        input_queue_service=queue_service,
        output_queue_service=queue_service,
        input_queue_id=input_id,
        output_queue_id=output_id,
        verbose=False
    )
    yield exec
    exec.stop()


# =============================================================================
# Module-level functions for linear graph test
# =============================================================================

_linear_log = []


def linear_node_a(x):
    _linear_log.append("A")
    return x + 1


def linear_node_b(x):
    _linear_log.append("B")
    return x * 2


def linear_node_c(x):
    _linear_log.append("C")
    return x + 10


def test_linear_graph_with_executor(executor):
    """Test simple linear graph: A -> B -> C."""
    global _linear_log
    _linear_log = []

    a = WorkGraphNode(name="A", value=linear_node_a, result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg)
    b = WorkGraphNode(name="B", value=linear_node_b, result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg)
    c = WorkGraphNode(name="C", value=linear_node_c, result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg)

    a.add_next(b)
    b.add_next(c)

    graph = WorkGraph(start_nodes=[a], executor=executor)
    result = graph.run(5)

    # A(5) -> 6, B(6) -> 12, C(12) -> 22
    assert result == 22
    assert _linear_log == ["A", "B", "C"]


# =============================================================================
# Module-level functions for diamond graph test
# =============================================================================

_diamond_log = []


def diamond_node_a(x):
    _diamond_log.append("A")
    return x


def diamond_node_b(x):
    _diamond_log.append("B")
    return x + 10


def diamond_node_c(x):
    _diamond_log.append("C")
    return x + 20


def diamond_node_d(*args):
    _diamond_log.append("D")
    return sum(args)


def test_diamond_graph_with_executor(executor):
    """Test diamond graph: A -> B, A -> C, B -> D, C -> D.

    D should execute exactly once with merged inputs from B and C.
    """
    global _diamond_log
    _diamond_log = []

    a = WorkGraphNode(name="A", value=diamond_node_a, result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg)
    b = WorkGraphNode(name="B", value=diamond_node_b, result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg)
    c = WorkGraphNode(name="C", value=diamond_node_c, result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg)
    d = WorkGraphNode(name="D", value=diamond_node_d, result_pass_down_mode=ResultPassDownMode.NoPassDown)

    a.add_next(b)
    a.add_next(c)
    b.add_next(d)
    c.add_next(d)

    graph = WorkGraph(start_nodes=[a], executor=executor)
    result = graph.run(5)

    # A(5) -> 5
    # B(5) -> 15, C(5) -> 25
    # D(15, 25) -> 40
    assert result == 40

    # D should execute exactly ONCE (not twice)
    assert _diamond_log.count("D") == 1
    # All nodes should execute
    assert set(_diamond_log) == {"A", "B", "C", "D"}


# =============================================================================
# Module-level functions for multiple start nodes test
# =============================================================================

_multi_start_log = []


def multi_start_a(x):
    _multi_start_log.append("A")
    return x + 1


def multi_start_b(x):
    _multi_start_log.append("B")
    return x + 2


def test_multiple_start_nodes_with_executor(executor):
    """Test graph with multiple start nodes."""
    global _multi_start_log
    _multi_start_log = []

    a = WorkGraphNode(name="A", value=multi_start_a, result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg)
    b = WorkGraphNode(name="B", value=multi_start_b, result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg)

    graph = WorkGraph(start_nodes=[a, b], executor=executor)
    result = graph.run(10)

    # A(10) -> 11, B(10) -> 12
    # Result should be tuple of both
    assert result == (11, 12)
    assert set(_multi_start_log) == {"A", "B"}


# =============================================================================
# Test: Backward Compatibility (executor=None)
# =============================================================================

_compat_log = []


def compat_node_a(x):
    _compat_log.append("A")
    return x + 1


def compat_node_b(x):
    _compat_log.append("B")
    return x * 2


def test_backward_compatibility_no_executor():
    """Test that graphs work without executor (backward compatibility)."""
    global _compat_log
    _compat_log = []

    a = WorkGraphNode(name="A", value=compat_node_a, result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg)
    b = WorkGraphNode(name="B", value=compat_node_b, result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg)

    a.add_next(b)

    # No executor - uses recursive execution
    graph = WorkGraph(start_nodes=[a])
    result = graph.run(5)

    # A(5) -> 6, B(6) -> 12
    assert result == 12
    assert _compat_log == ["A", "B"]


# =============================================================================
# Module-level functions for self-loop test
# =============================================================================

_self_loop_counter = [0]


def self_loop_monitor(x):
    _self_loop_counter[0] += 1
    if _self_loop_counter[0] >= 3:
        return NextNodesSelector(
            include_self=False,
            include_others=True,
            result=f"done_after_{_self_loop_counter[0]}"
        )
    else:
        return NextNodesSelector(
            include_self=True,
            include_others=False,
            result=f"iteration_{_self_loop_counter[0]}"
        )


def self_loop_final(x):
    return f"final_{x}"


def test_self_loop_with_executor(executor):
    """Test self-loop pattern with executor (monitor use case).

    Note: This test uses ResultAsFirstArg to pass the result to the final node.
    For monitors that need to preserve original args (like webdriver), use NoPassDown
    but then downstream also receives original args, not the result.
    """
    global _self_loop_counter
    _self_loop_counter = [0]

    # Use ResultAsFirstArg so the result is passed to downstream
    # Note: This means self-loop also receives the result, not original args
    monitor = WorkGraphNode(
        name="monitor",
        value=self_loop_monitor,
        result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
    )
    final = WorkGraphNode(
        name="final",
        value=self_loop_final,
        result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
    )

    monitor.add_next(monitor)  # Self-edge
    monitor.add_next(final)

    graph = WorkGraph(start_nodes=[monitor], executor=executor)
    result = graph.run("input")

    # Should loop 3 times, then run final
    assert _self_loop_counter[0] == 3
    assert result == "final_done_after_3"


# =============================================================================
# Module-level functions for NoPassDown self-loop test
# =============================================================================

_no_pass_down_args = []


def no_pass_down_monitor(driver_obj):
    _no_pass_down_args.append(driver_obj)
    if len(_no_pass_down_args) >= 3:
        return NextNodesSelector(
            include_self=False,
            include_others=True,
            result="done"
        )
    else:
        return NextNodesSelector(
            include_self=True,
            include_others=False,
            result="continue"
        )


def test_self_loop_no_pass_down_with_executor(executor):
    """Test that self-loop preserves original args with NoPassDown mode."""
    global _no_pass_down_args
    _no_pass_down_args = []

    monitor = WorkGraphNode(
        name="monitor",
        value=no_pass_down_monitor,
        result_pass_down_mode=ResultPassDownMode.NoPassDown
    )
    monitor.add_next(monitor)

    graph = WorkGraph(start_nodes=[monitor], executor=executor)
    mock_driver = "mock_driver_string"  # Use string (picklable) instead of dict
    result = graph.run(mock_driver)

    # All iterations should receive the same original driver object
    assert len(_no_pass_down_args) == 3
    assert all(arg == mock_driver for arg in _no_pass_down_args)


# =============================================================================
# Module-level functions for branching test
# =============================================================================

_branch_log = []


def branch_node_a(x):
    _branch_log.append("A")
    return x


def branch_node_b(x):
    _branch_log.append("B")
    return x + 10


def branch_node_c(x):
    _branch_log.append("C")
    return x + 20


def test_branching_graph_with_executor(executor):
    """Test graph with branching: A -> B, A -> C (no merge)."""
    global _branch_log
    _branch_log = []

    a = WorkGraphNode(name="A", value=branch_node_a, result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg)
    b = WorkGraphNode(name="B", value=branch_node_b, result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg)
    c = WorkGraphNode(name="C", value=branch_node_c, result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg)

    a.add_next(b)
    a.add_next(c)

    graph = WorkGraph(start_nodes=[a], executor=executor)
    result = graph.run(5)

    # A(5) -> 5
    # B(5) -> 15, C(5) -> 25
    # Result should be tuple of leaf results
    assert result == (15, 25) or result == (25, 15)  # Order may vary
    assert set(_branch_log) == {"A", "B", "C"}


# =============================================================================
# Test: Single Node Graph
# =============================================================================

def single_node_func(x):
    return x * 2


def test_single_node_graph_with_executor(executor):
    """Test graph with single node."""
    a = WorkGraphNode(name="A", value=single_node_func)
    graph = WorkGraph(start_nodes=[a], executor=executor)
    result = graph.run(5)

    assert result == 10
