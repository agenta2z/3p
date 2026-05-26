"""
Test WorkGraphStopFlags.Terminate behavior across various DAG structures.

This test suite verifies:
- Terminate stops entire graph execution immediately
- No downstream nodes execute after Terminate
- Queue clearing allows graph reuse after Terminate
- Terminate propagates correctly through different DAG topologies
"""
import pytest
from queue import Queue

from python_utils.common_objects.workflow.workgraph import WorkGraphNode, WorkGraph
from python_utils.common_objects.workflow.common.worknode_base import WorkGraphStopFlags
from python_utils.common_objects.workflow.common.result_pass_down_mode import ResultPassDownMode


class TestTerminateLinearChain:
    """Test Terminate behavior in linear chains (A -> B -> C -> D)."""

    def test_terminate_mid_chain_stops_downstream(self):
        """A -> B(Terminate) -> C -> D: C and D should not execute."""
        execution_order = []

        node_a = WorkGraphNode(
            name="A",
            value=lambda x: (execution_order.append("A"), x + 1)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda x: (execution_order.append("B"), (WorkGraphStopFlags.Terminate, x + 1))[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_c = WorkGraphNode(
            name="C",
            value=lambda x: (execution_order.append("C"), x + 1)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_d = WorkGraphNode(
            name="D",
            value=lambda x: (execution_order.append("D"), x + 1)[1],
        )

        node_a.add_next(node_b)
        node_b.add_next(node_c)
        node_c.add_next(node_d)

        result = node_a.run(0)

        assert execution_order == ["A", "B"], f"Expected ['A', 'B'], got {execution_order}"
        assert result == (WorkGraphStopFlags.Terminate, 2), f"Expected Terminate with result 2, got {result}"

    def test_terminate_at_first_node(self):
        """A(Terminate) -> B -> C: B and C should not execute."""
        execution_order = []

        node_a = WorkGraphNode(
            name="A",
            value=lambda x: (execution_order.append("A"), (WorkGraphStopFlags.Terminate, "stopped"))[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda x: (execution_order.append("B"), x)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_c = WorkGraphNode(
            name="C",
            value=lambda x: (execution_order.append("C"), x)[1],
        )

        node_a.add_next(node_b)
        node_b.add_next(node_c)

        result = node_a.run(0)

        assert execution_order == ["A"]
        assert result == (WorkGraphStopFlags.Terminate, "stopped")

    def test_terminate_at_leaf_node(self):
        """A -> B -> C(Terminate): All execute, Terminate returned."""
        execution_order = []

        node_a = WorkGraphNode(
            name="A",
            value=lambda x: (execution_order.append("A"), x + 1)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda x: (execution_order.append("B"), x + 1)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_c = WorkGraphNode(
            name="C",
            value=lambda x: (execution_order.append("C"), (WorkGraphStopFlags.Terminate, x + 1))[1],
        )

        node_a.add_next(node_b)
        node_b.add_next(node_c)

        result = node_a.run(0)

        assert execution_order == ["A", "B", "C"]
        assert result == (WorkGraphStopFlags.Terminate, 3)


class TestTerminateFork:
    """Test Terminate behavior in fork structures (A -> [B, C, D])."""

    def test_terminate_stops_remaining_siblings(self):
        """A -> [B(Terminate), C, D]: Only A and B execute, C and D are skipped."""
        execution_order = []

        node_a = WorkGraphNode(
            name="A",
            value=lambda x: (execution_order.append("A"), x + 1)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda x: (execution_order.append("B"), (WorkGraphStopFlags.Terminate, "B_result"))[1],
        )
        node_c = WorkGraphNode(
            name="C",
            value=lambda x: (execution_order.append("C"), "C_result")[1],
        )
        node_d = WorkGraphNode(
            name="D",
            value=lambda x: (execution_order.append("D"), "D_result")[1],
        )

        node_a.add_next(node_b)
        node_a.add_next(node_c)
        node_a.add_next(node_d)

        result = node_a.run(0)

        assert execution_order == ["A", "B"]
        assert result == (WorkGraphStopFlags.Terminate, "B_result")

    def test_terminate_mid_fork_with_partial_progress(self):
        """A -> [B, C(Terminate), D]: B executes, C executes and terminates, D skipped."""
        execution_order = []

        node_a = WorkGraphNode(
            name="A",
            value=lambda x: (execution_order.append("A"), x)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda x: (execution_order.append("B"), "B_done")[1],
        )
        node_c = WorkGraphNode(
            name="C",
            value=lambda x: (execution_order.append("C"), (WorkGraphStopFlags.Terminate, "C_terminate"))[1],
        )
        node_d = WorkGraphNode(
            name="D",
            value=lambda x: (execution_order.append("D"), "D_done")[1],
        )

        node_a.add_next(node_b)
        node_a.add_next(node_c)
        node_a.add_next(node_d)

        result = node_a.run(0)

        assert execution_order == ["A", "B", "C"]
        # B result and C's terminate result are both captured before D is skipped
        assert result[0] == WorkGraphStopFlags.Terminate
        # Result includes B_done and C_terminate merged
        assert "B_done" in str(result) or "C_terminate" in str(result)


class TestTerminateDiamond:
    """Test Terminate behavior in diamond structures (A -> [B, C] -> D)."""

    def test_terminate_in_diamond_branch(self):
        """
        A -> [B(Terminate), C] -> D
        D has two parents. B terminates, entire graph stops.
        D should NOT execute.
        """
        execution_order = []

        node_a = WorkGraphNode(
            name="A",
            value=lambda x: (execution_order.append("A"), x)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda x: (execution_order.append("B"), (WorkGraphStopFlags.Terminate, "B_terminate"))[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_c = WorkGraphNode(
            name="C",
            value=lambda x: (execution_order.append("C"), "C_result")[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_d = WorkGraphNode(
            name="D",
            value=lambda *args: (execution_order.append("D"), sum(len(str(a)) for a in args))[1],
        )

        node_a.add_next(node_b)
        node_a.add_next(node_c)
        node_b.add_next(node_d)
        node_c.add_next(node_d)
        node_d.previous = [node_b, node_c]

        result = node_a.run(0)

        # B terminates, C never executes, D never executes
        assert execution_order == ["A", "B"]
        assert result == (WorkGraphStopFlags.Terminate, "B_terminate")

    def test_terminate_after_diamond_merge(self):
        """
        A -> [B, C] -> D(Terminate) -> E
        All paths converge at D, D terminates, E should not execute.
        """
        execution_order = []

        node_a = WorkGraphNode(
            name="A",
            value=lambda x: (execution_order.append("A"), x)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda x: (execution_order.append("B"), x + 1)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_c = WorkGraphNode(
            name="C",
            value=lambda x: (execution_order.append("C"), x + 2)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_d = WorkGraphNode(
            name="D",
            value=lambda *args: (execution_order.append("D"), (WorkGraphStopFlags.Terminate, sum(args)))[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_e = WorkGraphNode(
            name="E",
            value=lambda x: (execution_order.append("E"), x * 10)[1],
        )

        node_a.add_next(node_b)
        node_a.add_next(node_c)
        node_b.add_next(node_d)
        node_c.add_next(node_d)
        node_d.previous = [node_b, node_c]
        node_d.add_next(node_e)

        result = node_a.run(0)

        # A, B, C all execute, D executes and terminates, E does not execute
        assert "A" in execution_order
        assert "B" in execution_order
        assert "C" in execution_order
        assert "D" in execution_order
        assert "E" not in execution_order
        # Terminate flag should be present, D computes sum(1, 2) = 3
        assert result[0] == WorkGraphStopFlags.Terminate
        # The result value contains 3 (could be nested due to result merging)
        assert "3" in str(result)


class TestTerminateMultipleStartNodes:
    """Test Terminate behavior with multiple start nodes in WorkGraph."""

    def test_terminate_in_first_start_node_stops_all(self):
        """WorkGraph with [A(Terminate), B, C]: Only A executes."""
        execution_order = []

        node_a = WorkGraphNode(
            name="A",
            value=lambda x: (execution_order.append("A"), (WorkGraphStopFlags.Terminate, "A_terminate"))[1],
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda x: (execution_order.append("B"), "B_result")[1],
        )
        node_c = WorkGraphNode(
            name="C",
            value=lambda x: (execution_order.append("C"), "C_result")[1],
        )

        graph = WorkGraph(start_nodes=[node_a, node_b, node_c])
        result = graph.run(0)

        assert execution_order == ["A"]
        # WorkGraph._post_process filters None values and returns tuple
        assert "A_terminate" in result

    def test_terminate_in_second_start_node(self):
        """WorkGraph with [A, B(Terminate), C]: A and B execute, C skipped."""
        execution_order = []

        node_a = WorkGraphNode(
            name="A",
            value=lambda x: (execution_order.append("A"), "A_result")[1],
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda x: (execution_order.append("B"), (WorkGraphStopFlags.Terminate, "B_terminate"))[1],
        )
        node_c = WorkGraphNode(
            name="C",
            value=lambda x: (execution_order.append("C"), "C_result")[1],
        )

        graph = WorkGraph(start_nodes=[node_a, node_b, node_c])
        result = graph.run(0)

        assert execution_order == ["A", "B"]


class TestTerminateGraphReuse:
    """Test that graph can be reused after Terminate (queue clearing)."""

    def test_graph_reuse_after_terminate(self):
        """
        First run: A -> [B, C(Terminate)] -> D
        Second run: Same graph should execute cleanly without stale queue items.
        """
        run_counter = [0]
        execution_order = []

        def run_a(x):
            execution_order.append("A")
            return x + 1

        def run_b(x):
            execution_order.append("B")
            return x + 2

        def run_c(x):
            execution_order.append("C")
            run_counter[0] += 1
            if run_counter[0] == 1:
                return WorkGraphStopFlags.Terminate, "first_run_terminate"
            return x + 3

        def run_d(*args):
            execution_order.append("D")
            return sum(args)

        node_a = WorkGraphNode(
            name="A",
            value=run_a,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_b = WorkGraphNode(
            name="B",
            value=run_b,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_c = WorkGraphNode(
            name="C",
            value=run_c,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_d = WorkGraphNode(
            name="D",
            value=run_d,
        )

        node_a.add_next(node_b)
        node_a.add_next(node_c)
        node_b.add_next(node_d)
        node_c.add_next(node_d)
        node_d.previous = [node_b, node_c]

        graph = WorkGraph(start_nodes=[node_a])

        # First run: C terminates
        execution_order.clear()
        result1 = graph.run(0)
        # Verify Terminate flag is present and D did not execute
        assert "first_run_terminate" in str(result1)
        assert "D" not in execution_order

        # Second run: C should not terminate, D should execute
        # Queue should be cleared, so D gets fresh inputs
        execution_order.clear()
        result2 = graph.run(0)

        # Now: A(0)->1, B(1)->3, C(1)->4, D(3,4)->7
        assert "D" in execution_order
        assert "7" in str(result2)

    def test_multi_parent_queue_cleared_on_reuse(self):
        """Verify that multi-parent node's queue is properly cleared between runs."""
        execution_order = []
        run_counter = [0]

        def run_b(x):
            execution_order.append("B")
            run_counter[0] += 1
            if run_counter[0] == 1:
                return WorkGraphStopFlags.Terminate, x + 1
            return x + 1

        node_a = WorkGraphNode(
            name="A",
            value=lambda x: (execution_order.append("A"), x)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_b = WorkGraphNode(
            name="B",
            value=run_b,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_c = WorkGraphNode(
            name="C",
            value=lambda x: (execution_order.append("C"), x + 2)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_d = WorkGraphNode(
            name="D",
            value=lambda *args: (execution_order.append("D"), sum(args))[1],
        )

        node_a.add_next(node_b)
        node_a.add_next(node_c)
        node_b.add_next(node_d)
        node_c.add_next(node_d)
        node_d.previous = [node_b, node_c]

        graph = WorkGraph(start_nodes=[node_a])

        # Run 1: B terminates, D's queue might have B's input
        execution_order.clear()
        result1 = graph.run(0)
        assert "D" not in execution_order

        # Run 2: After queue clearing, should work correctly
        # B no longer terminates (run_counter > 1)
        execution_order.clear()

        result2 = graph.run(0)

        # A(0)->0, B(0)->1, C(0)->2, D(1,2)->3
        assert "D" in execution_order
        assert "3" in str(result2)


class TestTerminateNestedStructure:
    """Test Terminate in complex nested structures."""

    def test_terminate_propagates_through_layers(self):
        """
        Layer 1: A -> [B, C]
        Layer 2: B -> [D, E], C -> [F]
        Layer 3: E(Terminate)

        Only A, B, D, E execute. C, F never start due to Terminate.
        """
        execution_order = []

        node_a = WorkGraphNode(
            name="A",
            value=lambda x: (execution_order.append("A"), x)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda x: (execution_order.append("B"), x)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_c = WorkGraphNode(
            name="C",
            value=lambda x: (execution_order.append("C"), x)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_d = WorkGraphNode(
            name="D",
            value=lambda x: (execution_order.append("D"), x + 1)[1],
        )
        node_e = WorkGraphNode(
            name="E",
            value=lambda x: (execution_order.append("E"), (WorkGraphStopFlags.Terminate, "E_terminate"))[1],
        )
        node_f = WorkGraphNode(
            name="F",
            value=lambda x: (execution_order.append("F"), x + 2)[1],
        )

        node_a.add_next(node_b)
        node_a.add_next(node_c)
        node_b.add_next(node_d)
        node_b.add_next(node_e)
        node_c.add_next(node_f)

        result = node_a.run(0)

        # A -> B -> D executes, B -> E terminates
        # After E terminates, we break and don't continue to C
        assert "A" in execution_order
        assert "B" in execution_order
        # D executes before E since it's first in B's children
        assert "D" in execution_order
        assert "E" in execution_order
        # C and F should NOT execute
        assert "C" not in execution_order
        assert "F" not in execution_order


class TestTerminateReturnValue:
    """Test that Terminate returns correct (flag, result) tuple."""

    def test_terminate_with_result_value(self):
        """Verify Terminate returns (Terminate, result) tuple."""
        node = WorkGraphNode(
            name="A",
            value=lambda x: (WorkGraphStopFlags.Terminate, {"key": "value", "num": 42}),
        )

        result = node.run(0)

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert result[0] == WorkGraphStopFlags.Terminate
        assert result[1] == {"key": "value", "num": 42}

    def test_terminate_with_none_result(self):
        """Verify Terminate with None result."""
        node = WorkGraphNode(
            name="A",
            value=lambda x: (WorkGraphStopFlags.Terminate, None),
        )

        result = node.run(0)

        assert result == (WorkGraphStopFlags.Terminate, None)

    def test_terminate_propagates_result_up_chain(self):
        """Result from Terminate should propagate back up to caller."""
        node_a = WorkGraphNode(
            name="A",
            value=lambda x: x * 2,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda x: (WorkGraphStopFlags.Terminate, f"terminated_with_{x}"),
        )

        node_a.add_next(node_b)

        result = node_a.run(5)

        assert result == (WorkGraphStopFlags.Terminate, "terminated_with_10")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
