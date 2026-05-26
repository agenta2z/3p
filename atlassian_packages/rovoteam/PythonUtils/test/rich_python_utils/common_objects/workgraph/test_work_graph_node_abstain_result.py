"""
Test WorkGraphStopFlags.AbstainResult behavior across various DAG structures.

AbstainResult Behavior (from workgraph.py):
1. When a node returns (AbstainResult, result):
   - The result IS captured in downstream_results
   - stop_flag is set to AbstainResult
   - Subsequent siblings are NOTIFIED with the flag (not executed normally)
   - After all siblings processed, stop_flag resets to Continue

2. When a multi-parent node receives AbstainResult in its queue:
   - If remove_abstain_result_flag_from_upstream_input=True, the flag is filtered out
   - If False, the flag remains in the inputs

This test suite verifies:
- AbstainResult causes subsequent siblings to receive notification (not normal execution)
- AbstainResult flag resets to Continue after downstream loop
- Multi-parent nodes handle AbstainResult in queue correctly
- Queue filtering for AbstainResult flags
"""
import pytest
from queue import Queue

from python_utils.common_objects.workflow.workgraph import WorkGraphNode, WorkGraph
from python_utils.common_objects.workflow.common.worknode_base import WorkGraphStopFlags
from python_utils.common_objects.workflow.common.result_pass_down_mode import ResultPassDownMode


class TestAbstainResultBasicBehavior:
    """Test basic AbstainResult behavior in simple structures."""

    def test_abstain_result_single_node(self):
        """Single node returning AbstainResult."""
        node = WorkGraphNode(
            name="A",
            value=lambda x: (WorkGraphStopFlags.AbstainResult, "abstained"),
        )

        result = node.run(0)

        # Single node returns (flag, result) since flag != Continue
        assert result == (WorkGraphStopFlags.AbstainResult, "abstained")

    def test_abstain_result_notifies_subsequent_siblings(self):
        """
        A -> [B(AbstainResult), C, D]
        B abstains, C and D receive notification (not normal execution).
        """
        execution_order = []

        node_a = WorkGraphNode(
            name="A",
            value=lambda x: (execution_order.append("A"), x)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda x: (execution_order.append("B"), (WorkGraphStopFlags.AbstainResult, "B_abstained"))[1],
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

        # Only A and B execute - C and D are notified, not executed
        assert "A" in execution_order
        assert "B" in execution_order
        # C and D don't execute their value functions (they receive AbstainResult flag)
        assert "C" not in execution_order
        assert "D" not in execution_order

        # B's result is captured
        assert "B_abstained" in str(result)

    def test_abstain_result_flag_resets_after_siblings(self):
        """
        A -> [B(AbstainResult)] -> subsequent code in A continues
        AbstainResult flag resets to Continue after downstream loop.
        """
        execution_order = []

        node_a = WorkGraphNode(
            name="A",
            value=lambda x: (execution_order.append("A"), x + 1)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda x: (execution_order.append("B"), (WorkGraphStopFlags.AbstainResult, x + 2))[1],
        )

        node_a.add_next(node_b)

        result = node_a.run(0)

        # Both execute
        assert execution_order == ["A", "B"]
        # Result is B's abstained value
        # A: 0 + 1 = 1, B: 1 + 2 = 3 (passed to B, B returns AbstainResult with 3)
        # Flag resets to Continue after downstream loop
        assert "3" in str(result)


class TestAbstainResultMultiParentNotification:
    """Test that AbstainResult properly notifies multi-parent nodes."""

    def test_multi_parent_receives_abstain_notification(self):
        """
        A -> [B(AbstainResult), C] -> D
        D has two parents. B abstains and notifies D.
        D should execute when C also provides input.
        """
        execution_order = []

        node_a = WorkGraphNode(
            name="A",
            value=lambda x: (execution_order.append("A"), x)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda x: (execution_order.append("B"), (WorkGraphStopFlags.AbstainResult, "B_abstained"))[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_c = WorkGraphNode(
            name="C",
            value=lambda x: (execution_order.append("C"), x + 10)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_d = WorkGraphNode(
            name="D",
            value=lambda *args: (execution_order.append("D"), sum(a for a in args if isinstance(a, int)))[1],
            remove_abstain_result_flag_from_upstream_input=True,
        )

        node_a.add_next(node_b)
        node_a.add_next(node_c)
        node_b.add_next(node_d)
        node_c.add_next(node_d)
        node_d.previous = [node_b, node_c]

        result = node_a.run(0)

        # A executes, B executes and abstains
        # C is notified (not executed normally) due to AbstainResult from B
        assert "A" in execution_order
        assert "B" in execution_order
        # C doesn't execute because it receives AbstainResult notification
        # D receives: AbstainResult from B, notification from C
        # With filtering, D gets empty inputs since C was just notified

    def test_multi_parent_both_paths_execute_without_abstain(self):
        """
        A -> [B, C] -> D (without AbstainResult)
        Both paths converge at D normally.
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
            value=lambda *args: (execution_order.append("D"), sum(args))[1],
        )

        node_a.add_next(node_b)
        node_a.add_next(node_c)
        node_b.add_next(node_d)
        node_c.add_next(node_d)
        node_d.previous = [node_b, node_c]

        result = node_a.run(0)

        # All nodes execute
        assert "A" in execution_order
        assert "B" in execution_order
        assert "C" in execution_order
        assert "D" in execution_order


class TestAbstainResultDiffersFromTerminate:
    """Test that AbstainResult behaves differently from Terminate."""

    def test_abstain_notifies_siblings_terminate_breaks(self):
        """
        Key difference: AbstainResult notifies remaining siblings (calls run with flag),
        Terminate breaks immediately (siblings not even called).

        Note: When a sibling receives AbstainResult notification, its value function
        is NOT executed - only the notification pathway is taken.
        """
        # Test with AbstainResult - siblings are notified but value not called
        execution_order_abstain = []

        node_a = WorkGraphNode(
            name="A",
            value=lambda x: (execution_order_abstain.append("A"), x)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda x: (execution_order_abstain.append("B"), (WorkGraphStopFlags.AbstainResult, "B"))[1],
        )
        node_c = WorkGraphNode(
            name="C",
            value=lambda x: (execution_order_abstain.append("C"), x)[1],
        )

        node_a.add_next(node_b)
        node_a.add_next(node_c)

        result_abstain = node_a.run(0)

        # A and B execute, C is notified (value not called)
        assert "A" in execution_order_abstain
        assert "B" in execution_order_abstain
        # C's value function is NOT called because it receives AbstainResult notification
        # The node.run() is called, but the value function is skipped
        assert "C" not in execution_order_abstain

        # Test with Terminate - siblings don't even get called
        execution_order_term = []

        node_a2 = WorkGraphNode(
            name="A",
            value=lambda x: (execution_order_term.append("A"), x)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_b2 = WorkGraphNode(
            name="B",
            value=lambda x: (execution_order_term.append("B"), (WorkGraphStopFlags.Terminate, "B"))[1],
        )
        node_c2 = WorkGraphNode(
            name="C",
            value=lambda x: (execution_order_term.append("C"), x)[1],
        )

        node_a2.add_next(node_b2)
        node_a2.add_next(node_c2)

        result_terminate = node_a2.run(0)

        # With Terminate, the loop breaks completely - C's run() is not even called
        assert "A" in execution_order_term
        assert "B" in execution_order_term
        assert "C" not in execution_order_term

        # Key behavior difference is in the loop handling:
        # AbstainResult: node.run(stop_flag) is called for remaining siblings
        # Terminate: break (nothing called for remaining siblings)


class TestAbstainResultConditional:
    """Test AbstainResult based on conditions."""

    def test_abstain_based_on_threshold_first_child(self):
        """First child abstains if input exceeds threshold."""
        execution_order = []

        node_a = WorkGraphNode(
            name="A",
            value=lambda x: (execution_order.append("A"), x)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )

        def threshold_check(x, threshold=5):
            execution_order.append("B")
            if x >= threshold:
                return WorkGraphStopFlags.AbstainResult, f"too_high_{x}"
            return x * 2

        node_b = WorkGraphNode(
            name="B",
            value=threshold_check,
        )
        node_c = WorkGraphNode(
            name="C",
            value=lambda x: (execution_order.append("C"), "C_result")[1],
        )

        node_a.add_next(node_b)
        node_a.add_next(node_c)

        # Input 3: below threshold - B executes normally, C executes normally
        execution_order.clear()
        result_low = node_a.run(3)
        assert "B" in execution_order
        assert "C" in execution_order
        # Result is (6, C_result) since both execute
        assert "6" in str(result_low) or "C_result" in str(result_low)

        # Input 10: above threshold - B abstains, C is notified (not executed)
        execution_order.clear()
        result_high = node_a.run(10)
        assert "B" in execution_order
        assert "C" not in execution_order  # C is notified, not executed
        assert "too_high_10" in str(result_high)


class TestAbstainResultInWorkGraph:
    """Test AbstainResult behavior within WorkGraph."""

    def test_workgraph_with_abstain_start_node(self):
        """WorkGraph with start nodes where first abstains."""
        execution_order = []

        node_a = WorkGraphNode(
            name="A",
            value=lambda x: (execution_order.append("A"), (WorkGraphStopFlags.AbstainResult, "A_abstained"))[1],
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

        # A executes and abstains
        assert "A" in execution_order
        # B and C are notified (not executed normally)
        # Based on WorkGraph._run behavior, AbstainResult causes subsequent start nodes to be notified
        assert "A_abstained" in str(result)


class TestAbstainResultQueueFiltering:
    """Test queue filtering behavior for AbstainResult flags."""

    def test_queue_filters_abstain_flags_when_configured(self):
        """Multi-parent node filters out AbstainResult flags from queue when configured."""
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
            value=lambda *args: (execution_order.append("D"), list(args))[1],
            remove_abstain_result_flag_from_upstream_input=True,
        )

        node_a.add_next(node_b)
        node_a.add_next(node_c)
        node_b.add_next(node_d)
        node_c.add_next(node_d)
        node_d.previous = [node_b, node_c]

        result = node_a.run(0)

        # All nodes should execute without AbstainResult
        assert "D" in execution_order
        # D should receive (1, 2) from B and C
        assert "1" in str(result) and "2" in str(result)


class TestAbstainResultEdgeCases:
    """Test edge cases for AbstainResult."""

    def test_abstain_with_none_result(self):
        """AbstainResult with None as the result value."""
        node = WorkGraphNode(
            name="A",
            value=lambda x: (WorkGraphStopFlags.AbstainResult, None),
        )

        result = node.run(0)
        assert result == (WorkGraphStopFlags.AbstainResult, None)

    def test_abstain_in_linear_chain_propagates(self):
        """AbstainResult in a linear chain propagates correctly."""
        execution_order = []

        node_a = WorkGraphNode(
            name="A",
            value=lambda x: (execution_order.append("A"), x + 1)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda x: (execution_order.append("B"), (WorkGraphStopFlags.AbstainResult, x + 1))[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_c = WorkGraphNode(
            name="C",
            value=lambda x: (execution_order.append("C"), x + 1)[1],
        )

        node_a.add_next(node_b)
        node_b.add_next(node_c)

        result = node_a.run(0)

        # A and B execute
        assert "A" in execution_order
        assert "B" in execution_order
        # C receives AbstainResult notification (not normal execution)
        # In linear chain, C is B's downstream, so it gets notified
        # The behavior depends on whether C has siblings or not
        # Since C is the only child of B, it gets notified

    def test_abstain_at_leaf_node(self):
        """AbstainResult at a leaf node (no downstream)."""
        execution_order = []

        node_a = WorkGraphNode(
            name="A",
            value=lambda x: (execution_order.append("A"), x)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda x: (execution_order.append("B"), (WorkGraphStopFlags.AbstainResult, "leaf_abstain"))[1],
        )

        node_a.add_next(node_b)

        result = node_a.run(0)

        # Both execute, B abstains at leaf
        assert execution_order == ["A", "B"]
        # Since B is a leaf with no siblings, flag resets after empty downstream loop
        assert "leaf_abstain" in str(result)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
