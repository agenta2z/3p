"""
Test NextNodesSelector and self-loop (continuous monitoring) functionality.

These tests verify the Phase 1 implementation of continuous monitoring where
a monitor node can re-run itself after downstream actions complete.

Key concepts tested:
- NextNodesSelector class for controlling downstream execution
- Self-edge (node.add_next(node)) for creating loops
- include_self flag for triggering self-loops
- include_others flag for selective downstream execution
- Cycle detection in str_all_descendants
"""
import pytest

from python_utils.common_objects.workflow.workgraph import WorkGraphNode, WorkGraph
from python_utils.common_objects.workflow.common.result_pass_down_mode import ResultPassDownMode
from python_utils.common_objects.workflow.common.worknode_base import NextNodesSelector
from python_utils.algorithms.graph.node import Node


class TestNextNodesSelectorBasic:
    """Test basic NextNodesSelector functionality."""

    def test_next_nodes_selector_defaults(self):
        """Test NextNodesSelector default values."""
        selector = NextNodesSelector()
        assert selector.include_self is False
        assert selector.include_others is True
        assert selector.result is None

    def test_next_nodes_selector_with_values(self):
        """Test NextNodesSelector with custom values."""
        selector = NextNodesSelector(
            include_self=True,
            include_others={'action1', 'action2'},
            result="test_result"
        )
        assert selector.include_self is True
        assert selector.include_others == {'action1', 'action2'}
        assert selector.result == "test_result"

    def test_next_nodes_selector_include_others_false(self):
        """Test NextNodesSelector with include_others=False."""
        selector = NextNodesSelector(include_self=True, include_others=False)
        assert selector.include_self is True
        assert selector.include_others is False


class TestHandleNextNodesSelector:
    """Test _handle_next_nodes_selector method."""

    def test_handle_regular_result(self):
        """Test handling of regular (non-NextNodesSelector) result."""
        node = WorkGraphNode(name="test", value=lambda: None)
        include_self, include_others, result = node._handle_next_nodes_selector("regular_result")

        assert include_self is False
        assert include_others is True
        assert result == "regular_result"

    def test_handle_next_nodes_selector_result(self):
        """Test handling of NextNodesSelector result."""
        node = WorkGraphNode(name="test", value=lambda: None)
        selector = NextNodesSelector(include_self=True, include_others={'a', 'b'}, result=42)
        include_self, include_others, result = node._handle_next_nodes_selector(selector)

        assert include_self is True
        assert include_others == {'a', 'b'}
        assert result == 42


class TestSelectDownstreamNodes:
    """Test _select_downstream_nodes method."""

    def test_select_all_nodes(self):
        """Test selecting all downstream nodes."""
        node_a = WorkGraphNode(name="A", value=lambda: None)
        node_b = WorkGraphNode(name="B", value=lambda: None)
        node_c = WorkGraphNode(name="C", value=lambda: None)

        node_a.add_next(node_b)
        node_a.add_next(node_c)

        selected = node_a._select_downstream_nodes(include_others=True, include_self=False)
        assert len(selected) == 2
        assert node_b in selected
        assert node_c in selected

    def test_select_no_nodes(self):
        """Test selecting no downstream nodes."""
        node_a = WorkGraphNode(name="A", value=lambda: None)
        node_b = WorkGraphNode(name="B", value=lambda: None)

        node_a.add_next(node_b)

        selected = node_a._select_downstream_nodes(include_others=False, include_self=False)
        assert len(selected) == 0

    def test_select_by_name(self):
        """Test selecting specific nodes by name."""
        node_a = WorkGraphNode(name="A", value=lambda: None)
        node_b = WorkGraphNode(name="B", value=lambda: None)
        node_c = WorkGraphNode(name="C", value=lambda: None)
        node_d = WorkGraphNode(name="D", value=lambda: None)

        node_a.add_next(node_b)
        node_a.add_next(node_c)
        node_a.add_next(node_d)

        selected = node_a._select_downstream_nodes(include_others={'B', 'D'}, include_self=False)
        assert len(selected) == 2
        assert node_b in selected
        assert node_d in selected
        assert node_c not in selected

    def test_select_self_edge(self):
        """Test selecting self-edge when include_self=True."""
        node_a = WorkGraphNode(name="A", value=lambda: None)
        node_b = WorkGraphNode(name="B", value=lambda: None)

        node_a.add_next(node_b)
        node_a.add_next(node_a)  # Self-edge

        # With include_self=True
        selected = node_a._select_downstream_nodes(include_others=True, include_self=True)
        assert len(selected) == 2
        assert node_a in selected
        assert node_b in selected

        # With include_self=False
        selected = node_a._select_downstream_nodes(include_others=True, include_self=False)
        assert len(selected) == 1
        assert node_b in selected
        assert node_a not in selected

    def test_select_only_self(self):
        """Test selecting only self (skip all others)."""
        node_a = WorkGraphNode(name="A", value=lambda: None)
        node_b = WorkGraphNode(name="B", value=lambda: None)

        node_a.add_next(node_b)
        node_a.add_next(node_a)  # Self-edge

        selected = node_a._select_downstream_nodes(include_others=False, include_self=True)
        assert len(selected) == 1
        assert node_a in selected


class TestSelfLoopExecution:
    """Test self-loop execution with NextNodesSelector."""

    def test_simple_self_loop_with_counter(self):
        """Test a simple self-loop that runs a fixed number of times."""
        execution_count = [0]
        max_iterations = 3

        def monitor_func():
            execution_count[0] += 1
            if execution_count[0] < max_iterations:
                return NextNodesSelector(include_self=True, include_others=False, result=execution_count[0])
            else:
                return execution_count[0]  # Normal return stops the loop

        monitor = WorkGraphNode(
            name="monitor",
            value=monitor_func,
            result_pass_down_mode=ResultPassDownMode.NoPassDown
        )
        monitor.add_next(monitor)  # Explicit self-edge

        result = monitor.run()

        assert execution_count[0] == max_iterations
        assert result == max_iterations

    def test_self_loop_with_downstream(self):
        """Test self-loop that also runs downstream nodes."""
        monitor_count = [0]
        action_count = [0]
        max_iterations = 2

        def monitor_func():
            monitor_count[0] += 1
            if monitor_count[0] < max_iterations:
                return NextNodesSelector(include_self=True, include_others=True, result=monitor_count[0])
            else:
                return monitor_count[0]

        def action_func(x):
            action_count[0] += 1
            return x * 2

        monitor = WorkGraphNode(
            name="monitor",
            value=monitor_func,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        action = WorkGraphNode(
            name="action",
            value=action_func,
        )

        monitor.add_next(action)
        monitor.add_next(monitor)  # Self-edge

        result = monitor.run()

        # Monitor runs max_iterations times
        assert monitor_count[0] == max_iterations
        # Action runs max_iterations times (once per monitor execution)
        assert action_count[0] == max_iterations

    def test_self_loop_with_no_pass_down(self):
        """Test that NoPassDown mode preserves original args for self-loop."""
        received_args = []
        execution_count = [0]
        max_iterations = 3

        def monitor_func(driver_arg):
            received_args.append(driver_arg)
            execution_count[0] += 1
            if execution_count[0] < max_iterations:
                return NextNodesSelector(include_self=True, include_others=False, result="some_result")
            else:
                return "final"

        monitor = WorkGraphNode(
            name="monitor",
            value=monitor_func,
            result_pass_down_mode=ResultPassDownMode.NoPassDown  # Keep original args
        )
        monitor.add_next(monitor)  # Self-edge

        result = monitor.run("original_driver")

        assert execution_count[0] == max_iterations
        # All executions should receive the original argument
        assert received_args == ["original_driver"] * max_iterations

    def test_self_loop_with_result_as_first_arg(self):
        """Test that ResultAsFirstArg mode passes result to self-loop."""
        received_args = []
        execution_count = [0]
        max_iterations = 3

        def monitor_func(arg):
            received_args.append(arg)
            execution_count[0] += 1
            new_result = arg + 1 if isinstance(arg, int) else 1
            if execution_count[0] < max_iterations:
                return NextNodesSelector(include_self=True, include_others=False, result=new_result)
            else:
                return new_result

        monitor = WorkGraphNode(
            name="monitor",
            value=monitor_func,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg  # Pass result
        )
        monitor.add_next(monitor)  # Self-edge

        result = monitor.run(0)

        assert execution_count[0] == max_iterations
        # Each execution receives the result from the previous one
        assert received_args == [0, 1, 2]
        assert result == 3


class TestCycleDetection:
    """Test cycle detection in graph traversal methods."""

    def test_str_all_descendants_with_self_edge(self):
        """Test that str_all_descendants detects self-edges."""
        monitor = Node("Monitor")
        action = Node("Action")

        monitor.add_next(action)
        monitor.add_next(monitor)  # Self-edge

        output = monitor.str_all_descendants(ascii_tree=True)

        assert "Monitor" in output
        assert "Action" in output
        assert "[CYCLE]" in output

    def test_str_all_descendants_with_diamond_cycle(self):
        """Test cycle detection with diamond pattern and cycle."""
        a = Node("A")
        b = Node("B")
        c = Node("C")
        d = Node("D")

        a.add_next(b)
        a.add_next(c)
        b.add_next(d)
        c.add_next(d)
        d.add_next(a)  # Cycle back to A

        output = a.str_all_descendants(ascii_tree=True)

        assert "A" in output
        assert "[CYCLE]" in output

    def test_str_all_ancestors_with_cycle(self):
        """Test that str_all_ancestors detects cycles."""
        a = Node("A")
        b = Node("B")

        a.add_next(b)
        b.add_next(a)  # Mutual cycle

        output = b.str_all_ancestors(ascii_tree=True)

        assert "A" in output
        assert "B" in output
        assert "[CYCLE]" in output


class TestWorkGraphNodeStrWithCycle:
    """Test WorkGraphNode string representation with cycles."""

    def test_workgraph_node_with_self_edge(self):
        """Test WorkGraphNode with self-edge displays correctly (no infinite recursion)."""
        monitor = WorkGraphNode(name="Monitor", value=lambda: None)
        action = WorkGraphNode(name="Action", value=lambda: None)

        monitor.add_next(action)
        monitor.add_next(monitor)  # Self-edge

        # This should not cause infinite recursion
        output = monitor.str_all_descendants(ascii_tree=True)

        # WorkGraphNode uses value for str, so check for cycle marker
        assert "[CYCLE]" in output
        # Verify the output contains the expected structure
        lines = output.strip().split('\n')
        assert len(lines) == 3  # Monitor, Action, Monitor [CYCLE]


class TestSelectiveDownstreamExecution:
    """Test selective downstream execution with include_others set."""

    def test_run_only_specific_nodes(self):
        """Test running only specific downstream nodes by name."""
        execution_log = []

        def make_node(name):
            # Use a closure to capture name correctly, ignore any passed arguments
            def node_func(*args, **kwargs):
                execution_log.append(name)
                return name
            return WorkGraphNode(
                name=name,
                value=node_func,
            )

        def selector_func():
            return NextNodesSelector(
                include_self=False,
                include_others={'B', 'D'},  # Only run B and D
                result="selector_result"
            )

        node_a = WorkGraphNode(
            name="A",
            value=selector_func,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_b = make_node("B")
        node_c = make_node("C")
        node_d = make_node("D")

        node_a.add_next(node_b)
        node_a.add_next(node_c)
        node_a.add_next(node_d)

        result = node_a.run()

        # Only B and D should have executed
        assert "B" in execution_log
        assert "D" in execution_log
        assert "C" not in execution_log


class TestNoSelfEdgeWithIncludeSelf:
    """Test behavior when include_self=True but no self-edge exists."""

    def test_include_self_without_self_edge(self):
        """include_self=True without explicit self-edge should have no effect."""
        execution_count = [0]

        def node_func():
            execution_count[0] += 1
            # Returns include_self=True, but there's no self-edge
            return NextNodesSelector(include_self=True, include_others=True, result="done")

        node_a = WorkGraphNode(
            name="A",
            value=node_func,
            result_pass_down_mode=ResultPassDownMode.NoPassDown
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda: "B_result",
        )

        node_a.add_next(node_b)
        # Note: NO self-edge added

        result = node_a.run()

        # Node A should only execute once since there's no self-edge
        assert execution_count[0] == 1


class TestSelfLoopWithMultipleParents:
    """Test self-looping nodes with multiple parents (edge case)."""

    def test_self_loop_receives_merged_args_with_no_pass_down(self):
        """
        Self-looping node with multiple parents should receive MERGED args on self-loop.

        This tests the fix for the bug where original_args was captured before
        multi-parent merge, causing self-loops to receive incorrect args.
        """
        received_args_list = []
        execution_count = [0]
        max_iterations = 2

        def monitor_func(*args):
            received_args_list.append(args)
            execution_count[0] += 1
            if execution_count[0] < max_iterations:
                return NextNodesSelector(include_self=True, include_others=False, result="continue")
            else:
                return "done"

        # Create a diamond structure where monitor has two parents
        parent1 = WorkGraphNode(
            name="parent1",
            value=lambda x: x + 10,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        parent2 = WorkGraphNode(
            name="parent2",
            value=lambda x: x + 20,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        monitor = WorkGraphNode(
            name="monitor",
            value=monitor_func,
            result_pass_down_mode=ResultPassDownMode.NoPassDown  # Keep original (merged) args
        )

        # Both parents feed into monitor
        parent1.add_next(monitor)
        parent2.add_next(monitor)
        # Monitor has self-edge
        monitor.add_next(monitor)

        # Create WorkGraph with both start nodes
        graph = WorkGraph(start_nodes=[parent1, parent2])
        result = graph.run(5)

        # Monitor should have executed max_iterations times
        assert execution_count[0] == max_iterations

        # First call: monitor receives merged args from both parents (15, 25)
        # Second call (self-loop with NoPassDown): should receive SAME merged args (15, 25)
        assert len(received_args_list) == max_iterations
        # Both calls should have the same args (the merged args)
        assert received_args_list[0] == received_args_list[1]
        # Args should be merged from both parents: (15, 25) since parent1 returns 5+10=15, parent2 returns 5+20=25
        assert 15 in received_args_list[0]
        assert 25 in received_args_list[0]
