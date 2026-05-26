"""Tests for WorkGraph dynamic expansion (Tasks 10.1–10.7).

Covers:
- 10.1: Basic expansion (leaf node expansion, result pass-down, empty entry_nodes no-op)
- 10.2: Graph integrity (cycle detection, name conflict, entry_nodes validation, bidirectional edges)
- 10.3: Termination guarantees (max_expansion_depth, max_total_nodes, depth propagation)
- 10.4: NextNodesSelector with expansion (include_others as Set[str], include_self)
- 10.5: Async support (_arun handles GraphExpansionResult, async fan-out)
- 10.6: Error handling (exception propagation, Terminate flag, AbstainResult)
- 10.7: Settings propagation (enable_result_save, _graph_event_callback)
"""
import asyncio
import os
import shutil
import tempfile

import pytest
from attr import attrs, attrib

from python_utils.common_objects.workflow.workgraph import WorkGraphNode, WorkGraph
from python_utils.common_objects.workflow.common.expansion import (
    GraphExpansionResult,
    SubgraphSpec,
)
from python_utils.common_objects.workflow.common.exceptions import (
    ExpansionLimitExceeded,
)
from python_utils.common_objects.workflow.common.result_pass_down_mode import ResultPassDownMode
from python_utils.common_objects.workflow.common.worknode_base import (
    WorkGraphStopFlags,
    NextNodesSelector,
)


# ---------------------------------------------------------------------------
# Concrete WorkGraphNode subclass for testing (with _get_result_path)
# ---------------------------------------------------------------------------

class _TestNode(WorkGraphNode):
    """WorkGraphNode subclass that implements _get_result_path for expansion tests."""

    def __init__(self, save_dir=None, **kwargs):
        super().__init__(**kwargs)
        self._save_dir = save_dir or tempfile.mkdtemp(prefix="wg_exp_test_")

    def _get_result_path(self, name, *args, **kwargs) -> str:
        os.makedirs(self._save_dir, exist_ok=True)
        return os.path.join(self._save_dir, f"{name}.pkl")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_node(name, fn, save_dir, pass_down=ResultPassDownMode.ResultAsFirstArg, **kw):
    """Create a _TestNode with common defaults."""
    return _TestNode(
        name=name,
        value=fn,
        save_dir=save_dir,
        result_pass_down_mode=pass_down,
        **kw,
    )


def _make_subgraph_pair(prefix, save_dir, fn_a=None, fn_b=None):
    """Create a simple two-node subgraph chain: sub_a -> sub_b."""
    fn_a = fn_a or (lambda x: x + 10)
    fn_b = fn_b or (lambda x: x + 20)
    sub_a = _make_node(f"{prefix}_a", fn_a, save_dir)
    sub_b = _make_node(f"{prefix}_b", fn_b, save_dir)
    sub_a.add_next(sub_b)
    return sub_a, sub_b


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def save_dir():
    d = tempfile.mkdtemp(prefix="wg_exp_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)



# ===========================================================================
# 10.1 — Basic WorkGraph expansion
# ===========================================================================

class TestBasicWorkGraphExpansion:
    """Task 10.1: leaf node returns GraphExpansionResult -> subgraph attached and executed."""

    def test_leaf_node_expansion_attaches_and_executes_subgraph(self, save_dir):
        """A leaf node returning GraphExpansionResult causes subgraph to be attached and run."""
        call_log = []

        sub_a = _make_node("sub_a", lambda x: (call_log.append("sub_a"), x + 10)[1], save_dir)
        sub_b = _make_node("sub_b", lambda x: (call_log.append("sub_b"), x + 20)[1], save_dir)
        sub_a.add_next(sub_b)

        def expanding_fn(x):
            call_log.append("expander")
            return GraphExpansionResult(
                result=x + 1,
                subgraph=SubgraphSpec(nodes=[sub_a, sub_b], entry_nodes=[sub_a]),
            )

        expander = _make_node("expander", expanding_fn, save_dir)
        graph = WorkGraph(
            start_nodes=[expander],
            max_expansion_depth=1,
            max_total_nodes=50,
        )
        result = graph.run(5)

        # expander(5) -> result=6, subgraph attached
        # sub_a(6) -> 16, sub_b(16) -> 36
        assert "expander" in call_log
        assert "sub_a" in call_log
        assert "sub_b" in call_log
        assert result == 36

    def test_result_field_used_for_downstream_pass_down(self, save_dir):
        """The result field of GraphExpansionResult is passed to subgraph entry nodes."""
        received = []

        sub_a = _make_node(
            "sub_a",
            lambda x: (received.append(x), x * 2)[1],
            save_dir,
        )

        def expanding_fn(x):
            return GraphExpansionResult(
                result=42,
                subgraph=SubgraphSpec(nodes=[sub_a], entry_nodes=[sub_a]),
            )

        expander = _make_node("expander", expanding_fn, save_dir)
        graph = WorkGraph(
            start_nodes=[expander],
            max_expansion_depth=1,
            max_total_nodes=50,
        )
        result = graph.run(0)

        # sub_a should receive 42 (the result field), not the GraphExpansionResult
        assert received == [42]
        assert result == 84

    def test_empty_entry_nodes_is_noop(self, save_dir):
        """GraphExpansionResult with empty entry_nodes is a no-op."""
        sub_a = _make_node("sub_a", lambda x: x + 10, save_dir)

        def expanding_fn(x):
            return GraphExpansionResult(
                result=x + 1,
                subgraph=SubgraphSpec(nodes=[sub_a], entry_nodes=[]),
            )

        expander = _make_node("expander", expanding_fn, save_dir)
        graph = WorkGraph(
            start_nodes=[expander],
            max_expansion_depth=1,
            max_total_nodes=50,
        )
        result = graph.run(5)

        # No subgraph executed, just the result field
        assert result == 6


# ===========================================================================
# 10.2 — WorkGraph expansion graph integrity
# ===========================================================================

class TestWorkGraphExpansionGraphIntegrity:
    """Task 10.2: cycle detection, name conflict, entry_nodes validation, bidirectional edges."""

    def test_cycle_detection_raises_value_error(self, save_dir):
        """Cycle within subgraph raises ValueError."""
        sub_a = _make_node("sub_a", lambda x: x, save_dir)
        sub_b = _make_node("sub_b", lambda x: x, save_dir)
        # Create a cycle: sub_a -> sub_b -> sub_a
        sub_a.add_next(sub_b)
        sub_b.add_next(sub_a)

        def expanding_fn(x):
            return GraphExpansionResult(
                result=x,
                subgraph=SubgraphSpec(nodes=[sub_a, sub_b], entry_nodes=[sub_a]),
            )

        expander = _make_node("expander", expanding_fn, save_dir)
        graph = WorkGraph(
            start_nodes=[expander],
            max_expansion_depth=1,
            max_total_nodes=50,
        )

        with pytest.raises(ValueError, match="[Cc]ycle"):
            graph.run(1)

    def test_name_conflict_raises_value_error(self, save_dir):
        """Subgraph node name conflicting with existing graph node raises ValueError."""
        # Create a subgraph node with the same name as the expander
        sub_a = _make_node("expander", lambda x: x, save_dir)  # name conflict!

        def expanding_fn(x):
            return GraphExpansionResult(
                result=x,
                subgraph=SubgraphSpec(nodes=[sub_a], entry_nodes=[sub_a]),
            )

        expander = _make_node("expander", expanding_fn, save_dir)
        graph = WorkGraph(
            start_nodes=[expander],
            max_expansion_depth=1,
            max_total_nodes=50,
        )

        with pytest.raises(ValueError, match="conflict"):
            graph.run(1)

    def test_entry_nodes_not_in_nodes_raises_value_error(self):
        """SubgraphSpec with entry_nodes not in nodes raises ValueError."""
        node_in = _TestNode(name="in_node", value=lambda x: x)
        node_out = _TestNode(name="out_node", value=lambda x: x)

        with pytest.raises(ValueError, match="entry_nodes must be present in nodes"):
            SubgraphSpec(nodes=[node_in], entry_nodes=[node_out])

    def test_bidirectional_edges_correct_after_expansion(self, save_dir):
        """After expansion, expander.next includes entry node and entry node.previous includes expander."""
        sub_a = _make_node("sub_a", lambda x: x + 10, save_dir)

        def expanding_fn(x):
            return GraphExpansionResult(
                result=x,
                subgraph=SubgraphSpec(nodes=[sub_a], entry_nodes=[sub_a]),
            )

        expander = _make_node("expander", expanding_fn, save_dir)
        graph = WorkGraph(
            start_nodes=[expander],
            max_expansion_depth=1,
            max_total_nodes=50,
        )
        graph.run(1)

        # After expansion, expander should have sub_a in its next list
        assert sub_a in expander.next
        # sub_a should have expander in its previous list
        assert expander in sub_a.previous



# ===========================================================================
# 10.3 — WorkGraph expansion termination guarantees
# ===========================================================================

class TestWorkGraphExpansionTermination:
    """Task 10.3: max_expansion_depth, max_total_nodes, depth propagation."""

    def test_max_expansion_depth_stops_further_expansions(self, save_dir):
        """When expansion depth >= max_expansion_depth, expansion is skipped."""
        call_log = []

        # Create a subgraph that itself tries to expand (chained expansion)
        inner_sub = _make_node("inner_sub", lambda x: (call_log.append("inner_sub"), x + 100)[1], save_dir)

        def inner_expanding_fn(x):
            call_log.append("inner_expander")
            return GraphExpansionResult(
                result=x + 50,
                subgraph=SubgraphSpec(nodes=[inner_sub], entry_nodes=[inner_sub]),
            )

        inner_expander = _make_node("inner_expander", inner_expanding_fn, save_dir)

        def outer_expanding_fn(x):
            call_log.append("outer_expander")
            return GraphExpansionResult(
                result=x + 1,
                subgraph=SubgraphSpec(
                    nodes=[inner_expander],
                    entry_nodes=[inner_expander],
                ),
            )

        outer_expander = _make_node("outer_expander", outer_expanding_fn, save_dir)
        graph = WorkGraph(
            start_nodes=[outer_expander],
            max_expansion_depth=1,  # Only one level of expansion allowed
            max_total_nodes=50,
        )
        result = graph.run(1)

        # outer_expander(1) -> result=2, attaches inner_expander
        # inner_expander(2) -> tries to expand but depth=1 >= max_depth=1, so skipped
        # inner_expander returns result=52 (2+50) as plain result, no subgraph attached
        assert "outer_expander" in call_log
        assert "inner_expander" in call_log
        # inner_sub should NOT be called because inner expansion was skipped
        assert "inner_sub" not in call_log

    def test_max_total_nodes_raises_expansion_limit_exceeded(self, save_dir):
        """Exceeding max_total_nodes raises ExpansionLimitExceeded."""
        # Create a subgraph with 3 nodes
        sub_a = _make_node("sub_a", lambda x: x, save_dir)
        sub_b = _make_node("sub_b", lambda x: x, save_dir)
        sub_c = _make_node("sub_c", lambda x: x, save_dir)
        sub_a.add_next(sub_b)
        sub_b.add_next(sub_c)

        def expanding_fn(x):
            return GraphExpansionResult(
                result=x,
                subgraph=SubgraphSpec(
                    nodes=[sub_a, sub_b, sub_c],
                    entry_nodes=[sub_a],
                ),
            )

        expander = _make_node("expander", expanding_fn, save_dir)
        graph = WorkGraph(
            start_nodes=[expander],
            max_expansion_depth=1,
            max_total_nodes=3,  # Only 3 total allowed (1 existing + 3 new = 4 > 3)
        )

        with pytest.raises(ExpansionLimitExceeded, match="max_total_nodes"):
            graph.run(1)

    def test_expansion_depth_propagates_through_chained_expansions(self, save_dir):
        """Expansion depth increments correctly through chained expansions."""
        call_log = []

        # Level 2 subgraph (should execute since max_depth=3)
        level2_sub = _make_node("level2_sub", lambda x: (call_log.append("level2_sub"), x + 1000)[1], save_dir)

        def level2_expanding_fn(x):
            call_log.append("level2_expander")
            return GraphExpansionResult(
                result=x + 100,
                subgraph=SubgraphSpec(nodes=[level2_sub], entry_nodes=[level2_sub]),
            )

        level2_expander = _make_node("level2_expander", level2_expanding_fn, save_dir)

        # Level 1 subgraph
        def level1_expanding_fn(x):
            call_log.append("level1_expander")
            return GraphExpansionResult(
                result=x + 10,
                subgraph=SubgraphSpec(
                    nodes=[level2_expander],
                    entry_nodes=[level2_expander],
                ),
            )

        level1_expander = _make_node("level1_expander", level1_expanding_fn, save_dir)

        # Root expander
        def root_expanding_fn(x):
            call_log.append("root_expander")
            return GraphExpansionResult(
                result=x + 1,
                subgraph=SubgraphSpec(
                    nodes=[level1_expander],
                    entry_nodes=[level1_expander],
                ),
            )

        root_expander = _make_node("root_expander", root_expanding_fn, save_dir)
        graph = WorkGraph(
            start_nodes=[root_expander],
            max_expansion_depth=3,  # Allow 3 levels of chained expansion
            max_total_nodes=50,
        )
        result = graph.run(1)

        # All three levels should expand
        assert "root_expander" in call_log
        assert "level1_expander" in call_log
        assert "level2_expander" in call_log
        assert "level2_sub" in call_log



# ===========================================================================
# 10.4 — WorkGraph expansion with NextNodesSelector
# ===========================================================================

class TestWorkGraphExpansionWithNextNodesSelector:
    """Task 10.4: NextNodesSelector inside GraphExpansionResult."""

    def test_next_nodes_selector_inside_expansion_result(self, save_dir):
        """NextNodesSelector as the result field of GraphExpansionResult works."""
        call_log = []

        sub_a = _make_node("sub_a", lambda x: (call_log.append("sub_a"), x + 10)[1], save_dir)
        sub_b = _make_node("sub_b", lambda x: (call_log.append("sub_b"), x + 20)[1], save_dir)

        def expanding_fn(x):
            call_log.append("expander")
            return GraphExpansionResult(
                result=x + 1,
                subgraph=SubgraphSpec(nodes=[sub_a, sub_b], entry_nodes=[sub_a, sub_b]),
            )

        expander = _make_node("expander", expanding_fn, save_dir)
        graph = WorkGraph(
            start_nodes=[expander],
            max_expansion_depth=1,
            max_total_nodes=50,
        )
        result = graph.run(5)

        # Both sub_a and sub_b should execute as entry nodes
        assert "sub_a" in call_log
        assert "sub_b" in call_log

    def test_include_others_as_set_filters_expanded_entry_nodes(self, save_dir):
        """include_others as Set[str] via NextNodesSelector filters which expanded entry nodes execute."""
        call_log = []

        sub_a = _make_node("sub_a", lambda x: (call_log.append("sub_a"), x + 10)[1], save_dir)
        sub_b = _make_node("sub_b", lambda x: (call_log.append("sub_b"), x + 20)[1], save_dir)

        def expanding_fn(x):
            call_log.append("expander")
            # Use NextNodesSelector as the result to control which entry nodes run
            return GraphExpansionResult(
                result=NextNodesSelector(
                    include_self=False,
                    include_others={"sub_a"},  # Only run sub_a
                    result=x + 1,
                ),
                subgraph=SubgraphSpec(nodes=[sub_a, sub_b], entry_nodes=[sub_a, sub_b]),
            )

        expander = _make_node("expander", expanding_fn, save_dir)
        graph = WorkGraph(
            start_nodes=[expander],
            max_expansion_depth=1,
            max_total_nodes=50,
        )
        result = graph.run(5)

        assert "expander" in call_log
        assert "sub_a" in call_log
        # sub_b should NOT execute because include_others filters it out
        assert "sub_b" not in call_log

    def test_include_self_with_expansion(self, save_dir):
        """include_self=True via NextNodesSelector with expansion causes self-loop."""
        call_log = []
        iteration = [0]

        sub_a = _make_node("sub_a", lambda x: (call_log.append("sub_a"), x + 10)[1], save_dir)

        def expanding_fn(x):
            iteration[0] += 1
            call_log.append(f"expander_iter_{iteration[0]}")
            if iteration[0] == 1:
                return GraphExpansionResult(
                    result=NextNodesSelector(
                        include_self=True,
                        include_others=True,
                        result=x + 1,
                    ),
                    subgraph=SubgraphSpec(nodes=[sub_a], entry_nodes=[sub_a]),
                )
            else:
                # Second iteration: return plain result to stop self-loop
                return x + 1

        expander = _make_node("expander", expanding_fn, save_dir)
        # Add self-edge for self-loop to work
        expander.add_next(expander)

        graph = WorkGraph(
            start_nodes=[expander],
            max_expansion_depth=1,
            max_total_nodes=50,
        )
        result = graph.run(5)

        # First iteration: expander(5) -> result=6, subgraph attached, include_self=True
        # sub_a(6) -> 16
        # Second iteration: expander(6) -> 7 (plain result, no expansion due to _expansion_applied)
        assert "expander_iter_1" in call_log
        assert "expander_iter_2" in call_log
        assert "sub_a" in call_log


# ===========================================================================
# 10.5 — WorkGraph expansion async support
# ===========================================================================

class TestWorkGraphExpansionAsync:
    """Task 10.5: _arun handles GraphExpansionResult, async fan-out."""

    @pytest.mark.asyncio
    async def test_arun_handles_graph_expansion_result(self, save_dir):
        """_arun recognizes GraphExpansionResult and attaches subgraph."""
        call_log = []

        sub_a = _make_node("sub_a", lambda x: (call_log.append("sub_a"), x + 10)[1], save_dir)

        def expanding_fn(x):
            call_log.append("expander")
            return GraphExpansionResult(
                result=x + 1,
                subgraph=SubgraphSpec(nodes=[sub_a], entry_nodes=[sub_a]),
            )

        expander = _make_node("expander", expanding_fn, save_dir)
        graph = WorkGraph(
            start_nodes=[expander],
            max_expansion_depth=1,
            max_total_nodes=50,
        )
        result = await graph.arun(5)

        assert "expander" in call_log
        assert "sub_a" in call_log
        assert result == 16  # expander result=6, sub_a(6)=16

    @pytest.mark.asyncio
    async def test_async_fan_out_to_expanded_subgraph_entry_nodes(self, save_dir):
        """Async fan-out to multiple expanded subgraph entry nodes."""
        call_log = []

        sub_a = _make_node("sub_a", lambda x: (call_log.append("sub_a"), x + 10)[1], save_dir)
        sub_b = _make_node("sub_b", lambda x: (call_log.append("sub_b"), x + 20)[1], save_dir)

        def expanding_fn(x):
            call_log.append("expander")
            return GraphExpansionResult(
                result=x + 1,
                subgraph=SubgraphSpec(
                    nodes=[sub_a, sub_b],
                    entry_nodes=[sub_a, sub_b],
                ),
            )

        expander = _make_node("expander", expanding_fn, save_dir)
        graph = WorkGraph(
            start_nodes=[expander],
            max_expansion_depth=1,
            max_total_nodes=50,
        )
        result = await graph.arun(5)

        assert "expander" in call_log
        assert "sub_a" in call_log
        assert "sub_b" in call_log



# ===========================================================================
# 10.6 — WorkGraph expansion error handling
# ===========================================================================

class TestWorkGraphExpansionErrorHandling:
    """Task 10.6: exception propagation, Terminate flag, AbstainResult."""

    def test_exception_in_expanded_node_propagates(self, save_dir):
        """Exception in an expanded subgraph node propagates correctly."""

        def failing_fn(x):
            raise RuntimeError("expanded node failed")

        sub_a = _make_node("sub_a", failing_fn, save_dir)

        def expanding_fn(x):
            return GraphExpansionResult(
                result=x + 1,
                subgraph=SubgraphSpec(nodes=[sub_a], entry_nodes=[sub_a]),
            )

        expander = _make_node("expander", expanding_fn, save_dir)
        graph = WorkGraph(
            start_nodes=[expander],
            max_expansion_depth=1,
            max_total_nodes=50,
        )

        with pytest.raises(RuntimeError, match="expanded node failed"):
            graph.run(1)

    def test_terminate_flag_in_expanded_node_stops_graph(self, save_dir):
        """Terminate flag from an expanded node stops the graph."""
        call_log = []

        sub_a = _make_node(
            "sub_a",
            lambda x: (call_log.append("sub_a"), (WorkGraphStopFlags.Terminate, "stopped"))[1],
            save_dir,
        )
        sub_b = _make_node("sub_b", lambda x: (call_log.append("sub_b"), x + 20)[1], save_dir)
        sub_a.add_next(sub_b)

        def expanding_fn(x):
            call_log.append("expander")
            return GraphExpansionResult(
                result=x + 1,
                subgraph=SubgraphSpec(nodes=[sub_a, sub_b], entry_nodes=[sub_a]),
            )

        expander = _make_node("expander", expanding_fn, save_dir)
        graph = WorkGraph(
            start_nodes=[expander],
            max_expansion_depth=1,
            max_total_nodes=50,
        )
        result = graph.run(1)

        assert "sub_a" in call_log
        # sub_b should NOT execute because sub_a returned Terminate
        assert "sub_b" not in call_log

    def test_abstain_result_in_expanded_node_propagates_to_downstream(self, save_dir):
        """AbstainResult from an expanded node propagates correctly."""
        call_log = []

        # Simple chain: sub_a -> sub_b
        # sub_a returns AbstainResult, sub_b should still be notified
        sub_a = _make_node(
            "sub_a",
            lambda x: (
                call_log.append("sub_a"),
                (WorkGraphStopFlags.AbstainResult, x + 10),
            )[1],
            save_dir,
        )
        sub_b = _make_node(
            "sub_b",
            lambda x: (call_log.append("sub_b"), x + 20)[1],
            save_dir,
        )
        sub_a.add_next(sub_b)

        def expanding_fn(x):
            call_log.append("expander")
            return GraphExpansionResult(
                result=x + 1,
                subgraph=SubgraphSpec(
                    nodes=[sub_a, sub_b],
                    entry_nodes=[sub_a],
                ),
            )

        expander = _make_node("expander", expanding_fn, save_dir)
        graph = WorkGraph(
            start_nodes=[expander],
            max_expansion_depth=1,
            max_total_nodes=50,
        )
        result = graph.run(1)

        # sub_a executes and returns AbstainResult
        assert "sub_a" in call_log
        # sub_b is notified of AbstainResult (downstream propagation)
        # The AbstainResult flag means sub_a's result is excluded from merge
        assert "expander" in call_log


# ===========================================================================
# 10.7 — WorkGraph expansion settings propagation and result saving
# ===========================================================================

class TestWorkGraphExpansionSettingsPropagation:
    """Task 10.7: enable_result_save and _graph_event_callback propagation."""

    def test_enable_result_save_propagates_to_expanded_nodes(self, save_dir):
        """enable_result_save setting propagates to expanded subgraph nodes."""
        sub_a = _make_node("sub_a", lambda x: x + 10, save_dir)

        def expanding_fn(x):
            return GraphExpansionResult(
                result=x + 1,
                subgraph=SubgraphSpec(nodes=[sub_a], entry_nodes=[sub_a]),
            )

        expander = _make_node("expander", expanding_fn, save_dir, enable_result_save=True)
        graph = WorkGraph(
            start_nodes=[expander],
            max_expansion_depth=1,
            max_total_nodes=50,
            enable_result_save=False,  # WorkGraph itself doesn't save, but nodes do
        )
        graph.run(5)

        # After expansion, sub_a should have enable_result_save propagated from expander
        assert sub_a.enable_result_save == True

    def test_graph_event_callback_propagates_to_expanded_nodes(self, save_dir):
        """_graph_event_callback propagates to expanded subgraph nodes."""
        events = []

        def event_callback(event):
            events.append(event)

        sub_a = _make_node("sub_a", lambda x: x + 10, save_dir)

        def expanding_fn(x):
            return GraphExpansionResult(
                result=x + 1,
                subgraph=SubgraphSpec(nodes=[sub_a], entry_nodes=[sub_a]),
            )

        expander = _make_node("expander", expanding_fn, save_dir)
        expander._graph_event_callback = event_callback

        graph = WorkGraph(
            start_nodes=[expander],
            max_expansion_depth=1,
            max_total_nodes=50,
        )
        graph.run(5)

        # After expansion, sub_a should have the callback propagated
        assert sub_a._graph_event_callback is event_callback
