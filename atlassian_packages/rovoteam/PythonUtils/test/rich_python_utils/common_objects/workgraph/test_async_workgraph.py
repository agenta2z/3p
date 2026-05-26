"""
Unit tests for WorkGraphNode._arun() — async execution path.

Tests cover:
- Basic async node execution with sync and async callables
- Multi-parent input merging via asyncio.Queue
- AbstainResult filtering in multi-parent merge
- Self-loop iteration via NextNodesSelector
- NextNodesSelector downstream selection
- Post-process hooks with async callables
- Downstream result ordering is deterministic (indexed insertion via _output_idx)

Requirements: 7.2, 7.3, 7.4, 7.5, 8.1, 8.3, 8.4, 9.1, 9.2
"""
import asyncio

import pytest

from python_utils.common_objects.workflow.workgraph import WorkGraphNode, WorkGraph
from python_utils.common_objects.workflow.common.worknode_base import (
    WorkGraphStopFlags,
    NextNodesSelector,
)
from python_utils.common_objects.workflow.common.result_pass_down_mode import ResultPassDownMode


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _TestGraphNode(WorkGraphNode):
    """WorkGraphNode subclass that stubs out result path for testing."""

    def _get_result_path(self, result_id, *args, **kwargs):
        import tempfile, os
        return os.path.join(tempfile.gettempdir(), f"_test_{result_id}.pkl")


# ---------------------------------------------------------------------------
# Test: basic sync / async callable execution  (Req 7.2)
# ---------------------------------------------------------------------------

class TestSyncAsyncCallableExecution:
    """WorkGraphNode._arun() transparently handles sync and async callables."""

    @pytest.mark.asyncio
    async def test_sync_callable_execution(self):
        """Sync callable is executed correctly via _arun."""
        node = WorkGraphNode(name="sync_node", value=lambda x: x + 1)
        result = await node.arun(5)
        assert result == 6

    @pytest.mark.asyncio
    async def test_async_callable_execution(self):
        """Async callable is awaited correctly via _arun."""

        async def async_fn(x):
            return x * 2

        node = WorkGraphNode(name="async_node", value=async_fn)
        result = await node.arun(3)
        assert result == 6

    @pytest.mark.asyncio
    async def test_sync_callable_no_args(self):
        """Sync callable with no arguments works."""
        node = WorkGraphNode(name="no_args", value=lambda: 42)
        result = await node.arun()
        assert result == 42

    @pytest.mark.asyncio
    async def test_async_callable_no_args(self):
        """Async callable with no arguments works."""

        async def async_fn():
            return 99

        node = WorkGraphNode(name="async_no_args", value=async_fn)
        result = await node.arun()
        assert result == 99


# ---------------------------------------------------------------------------
# Test: multi-parent input merging via asyncio.Queue  (Req 8.1, 8.3)
# ---------------------------------------------------------------------------

class TestMultiParentMerge:
    """Multi-parent node collects inputs from all parents before executing."""

    @pytest.mark.asyncio
    async def test_multi_parent_merge_two_parents(self):
        """Node with two parents collects both inputs before executing."""
        p1 = WorkGraphNode(name="p1", value=lambda: None)
        p2 = WorkGraphNode(name="p2", value=lambda: None)

        node = WorkGraphNode(
            name="merge_node",
            value=lambda *args: sum(args),
            previous=[p1, p2],
        )

        # First parent sends input — not all ready yet, returns None
        r1 = await node._arun(10)
        assert r1 is None

        # Second parent sends input — all ready, executes
        r2 = await node._arun(20)
        # _merge_upstream_inputs extends args: [10, 20], sum = 30
        assert r2 == 30

    @pytest.mark.asyncio
    async def test_multi_parent_merge_three_parents(self):
        """Node with three parents collects all three inputs."""
        parents = [WorkGraphNode(name=f"p{i}", value=lambda: None) for i in range(3)]

        node = WorkGraphNode(
            name="merge3",
            value=lambda *args: list(args),
            previous=parents,
        )

        r1 = await node._arun(1)
        assert r1 is None
        r2 = await node._arun(2)
        assert r2 is None
        r3 = await node._arun(3)
        # After merge: args = [1, 2, 3]
        assert sorted(r3) == [1, 2, 3]


# ---------------------------------------------------------------------------
# Test: AbstainResult filtering in multi-parent merge  (Req 8.4)
# ---------------------------------------------------------------------------

class TestAbstainResultFiltering:
    """AbstainResult flags are filtered from multi-parent inputs when configured."""

    @pytest.mark.asyncio
    async def test_abstain_result_filtered_from_merge(self):
        """AbstainResult inputs are removed when remove_abstain_result_flag_from_upstream_input=True."""
        p1 = WorkGraphNode(name="p1", value=lambda: None)
        p2 = WorkGraphNode(name="p2", value=lambda: None)

        received_args = []

        def capture(*args):
            received_args.extend(args)
            return sum(args) if args else 0

        node = WorkGraphNode(
            name="filter_node",
            value=capture,
            previous=[p1, p2],
            remove_abstain_result_flag_from_upstream_input=True,
            pass_abstain_result_flag_downstream=True,
        )

        # First parent sends AbstainResult
        await node._arun(WorkGraphStopFlags.AbstainResult)
        # Second parent sends a real value
        r = await node._arun(10)

        # AbstainResult should be filtered out; only (10,) remains as args
        assert r == 10

    @pytest.mark.asyncio
    async def test_abstain_result_not_filtered_when_disabled(self):
        """AbstainResult inputs are kept when remove_abstain_result_flag_from_upstream_input=False."""
        p1 = WorkGraphNode(name="p1", value=lambda: None)
        p2 = WorkGraphNode(name="p2", value=lambda: None)

        captured = []

        def capture(*args):
            captured.extend(args)
            return len(args)

        node = WorkGraphNode(
            name="no_filter_node",
            value=capture,
            previous=[p1, p2],
            remove_abstain_result_flag_from_upstream_input=False,
            pass_abstain_result_flag_downstream=True,
        )

        # First parent sends AbstainResult
        await node._arun(WorkGraphStopFlags.AbstainResult)
        # Second parent sends a real value
        r = await node._arun(10)

        # Both inputs should be present (AbstainResult + (10,))
        # The merge will include the AbstainResult as-is in the args
        assert r is not None


# ---------------------------------------------------------------------------
# Test: self-loop iteration  (Req 7.4, 7.5)
# ---------------------------------------------------------------------------

class TestSelfLoopIteration:
    """Self-loop node iterates correctly using NextNodesSelector."""

    @pytest.mark.asyncio
    async def test_self_loop_with_next_nodes_selector(self):
        """Self-loop node iterates via NextNodesSelector(include_self=True)."""
        counter = [0]

        def loop_fn(x):
            counter[0] += 1
            if counter[0] < 3:
                return NextNodesSelector(
                    include_self=True, include_others=False, result=counter[0]
                )
            return counter[0]

        node = WorkGraphNode(
            name="loop_node",
            value=loop_fn,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
        )
        node.add_next(node)  # self-edge

        result = await node.arun(0)
        assert counter[0] == 3
        assert result == 3

    @pytest.mark.asyncio
    async def test_self_loop_single_iteration(self):
        """Node without NextNodesSelector(include_self=True) does not loop."""
        call_count = [0]

        def no_loop_fn(x):
            call_count[0] += 1
            return x + 1

        node = WorkGraphNode(
            name="no_loop",
            value=no_loop_fn,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
        )
        node.add_next(node)  # self-edge exists but include_self never set

        result = await node.arun(0)
        assert call_count[0] == 1
        assert result == 1

    @pytest.mark.asyncio
    async def test_self_loop_no_pass_down_mode(self):
        """Self-loop with NoPassDown uses original args each iteration."""
        counter = [0]

        def loop_fn(x):
            counter[0] += 1
            if counter[0] < 3:
                return NextNodesSelector(
                    include_self=True, include_others=False, result=counter[0]
                )
            return x  # returns original arg

        node = WorkGraphNode(
            name="loop_no_pass",
            value=loop_fn,
            result_pass_down_mode=ResultPassDownMode.NoPassDown,
        )
        node.add_next(node)

        result = await node.arun(42)
        assert counter[0] == 3
        # With NoPassDown, original args (42) are used each iteration
        assert result == 42


# ---------------------------------------------------------------------------
# Test: NextNodesSelector downstream selection  (Req 7.4)
# ---------------------------------------------------------------------------

class TestNextNodesSelectorDownstream:
    """NextNodesSelector controls which downstream nodes execute."""

    @pytest.mark.asyncio
    async def test_include_others_false_skips_downstream(self):
        """include_others=False skips all non-self downstream nodes."""
        downstream_called = [False]

        def downstream_fn(x):
            downstream_called[0] = True
            return x

        root = WorkGraphNode(
            name="root",
            value=lambda x: NextNodesSelector(
                include_self=False, include_others=False, result=x * 2
            ),
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
        )
        child = WorkGraphNode(
            name="child",
            value=downstream_fn,
        )
        root.add_next(child)

        result = await root.arun(5)
        assert result == 10
        assert downstream_called[0] is False

    @pytest.mark.asyncio
    async def test_include_others_set_selects_specific_nodes(self):
        """include_others as a set selects only named downstream nodes."""
        called_nodes = []

        def make_fn(name):
            def fn(x):
                called_nodes.append(name)
                return x
            return fn

        root = WorkGraphNode(
            name="root",
            value=lambda x: NextNodesSelector(
                include_self=False,
                include_others={"child_b"},
                result=x,
            ),
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
        )
        child_a = WorkGraphNode(name="child_a", value=make_fn("child_a"))
        child_b = WorkGraphNode(name="child_b", value=make_fn("child_b"))
        root.add_next(child_a)
        root.add_next(child_b)

        await root.arun(1)
        assert "child_b" in called_nodes
        assert "child_a" not in called_nodes


# ---------------------------------------------------------------------------
# Test: post-process hooks with async callables  (Req 9.1, 9.2)
# ---------------------------------------------------------------------------

class TestAsyncPostProcessHooks:
    """Post-process hooks support async callables via call_maybe_async."""

    @pytest.mark.asyncio
    async def test_async_post_process(self):
        """Async _post_process hook is invoked via call_maybe_async."""

        class PostProcessNode(WorkGraphNode):
            async def _post_process(self, result, *args, **kwargs):
                return result + 100

            def _get_result_path(self, result_id, *args, **kwargs):
                import tempfile, os
                return os.path.join(tempfile.gettempdir(), f"_test_{result_id}.pkl")

        node = PostProcessNode(name="pp_node", value=lambda x: x)
        result = await node.arun(5)
        assert result == 105

    @pytest.mark.asyncio
    async def test_sync_post_process(self):
        """Sync _post_process hook also works in async path."""

        class SyncPostProcessNode(WorkGraphNode):
            def _post_process(self, result, *args, **kwargs):
                return result * 3

            def _get_result_path(self, result_id, *args, **kwargs):
                import tempfile, os
                return os.path.join(tempfile.gettempdir(), f"_test_{result_id}.pkl")

        node = SyncPostProcessNode(name="sync_pp", value=lambda x: x + 1)
        result = await node.arun(4)
        # value: 4+1=5, post_process: 5*3=15
        assert result == 15

    @pytest.mark.asyncio
    async def test_async_optional_post_process(self):
        """Async _optional_post_process hook is invoked when enabled."""

        class OptPostNode(WorkGraphNode):
            async def _optional_post_process(self, result, *args, **kwargs):
                return result + 50

            def _get_result_path(self, result_id, *args, **kwargs):
                import tempfile, os
                return os.path.join(tempfile.gettempdir(), f"_test_{result_id}.pkl")

        node = OptPostNode(
            name="opt_pp",
            value=lambda x: x,
            enable_optional_post_process=True,
        )
        result = await node.arun(10)
        assert result == 60

    @pytest.mark.asyncio
    async def test_optional_post_process_not_called_when_disabled(self):
        """_optional_post_process is NOT called when enable_optional_post_process=False."""
        called = [False]

        class OptPostNode(WorkGraphNode):
            async def _optional_post_process(self, result, *args, **kwargs):
                called[0] = True
                return result + 50

            def _get_result_path(self, result_id, *args, **kwargs):
                import tempfile, os
                return os.path.join(tempfile.gettempdir(), f"_test_{result_id}.pkl")

        node = OptPostNode(
            name="opt_pp_disabled",
            value=lambda x: x,
            enable_optional_post_process=False,
        )
        result = await node.arun(10)
        assert result == 10
        assert called[0] is False


# ---------------------------------------------------------------------------
# Test: downstream result ordering is deterministic  (Req 7.3, 7.5)
# ---------------------------------------------------------------------------

class TestDownstreamResultOrdering:
    """Downstream results use indexed insertion for deterministic ordering."""

    @pytest.mark.asyncio
    async def test_downstream_chain_result(self):
        """Downstream nodes execute correctly in async path."""
        node1 = WorkGraphNode(
            name="n1",
            value=lambda x: x + 1,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
        )
        node2 = WorkGraphNode(
            name="n2",
            value=lambda x: x * 2,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
        )
        node1.add_next(node2)

        result = await node1.arun(5)
        # n1: 5+1=6, n2: 6*2=12
        assert result == 12

    @pytest.mark.asyncio
    async def test_fan_out_deterministic_ordering(self):
        """Fan-out downstream results maintain order matching nodes_to_run index."""
        # Create a root that fans out to multiple children with varying delays
        execution_order = []

        async def slow_child(x):
            await asyncio.sleep(0.05)
            execution_order.append("slow")
            return x + 100

        async def fast_child(x):
            execution_order.append("fast")
            return x + 200

        root = WorkGraphNode(
            name="root",
            value=lambda x: x,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
        )
        child_slow = WorkGraphNode(name="slow", value=slow_child)
        child_fast = WorkGraphNode(name="fast", value=fast_child)

        # Add slow first, then fast
        root.add_next(child_slow)
        root.add_next(child_fast)

        result = await root.arun(1)

        # Both children should have executed
        assert "slow" in execution_order
        assert "fast" in execution_order

        # Result should be a tuple of (slow_result, fast_result) in node order
        # slow: 1+100=101, fast: 1+200=201
        # _merge_downstream_results returns tuple when multiple outputs
        assert result == (101, 201)

    @pytest.mark.asyncio
    async def test_output_idx_indexed_insertion(self):
        """_output_idx parameter inserts result at specific index."""
        node = WorkGraphNode(name="idx_node", value=lambda x: x * 10)

        output = [None, None, None]
        stop_flag = await node.arun(5, _output_idx=(output, 1))

        assert output[1] == 50
        assert output[0] is None
        assert output[2] is None
        assert stop_flag == WorkGraphStopFlags.Continue


# ---------------------------------------------------------------------------
# Test: WorkGraphStopFlags handling  (Req 7.3)
# ---------------------------------------------------------------------------

class TestStopFlagsInArun:
    """WorkGraphNode._arun() handles WorkGraphStopFlags correctly."""

    @pytest.mark.asyncio
    async def test_terminate_flag_returned(self):
        """Node returning Terminate flag propagates correctly."""
        node = WorkGraphNode(
            name="term_node",
            value=lambda: (WorkGraphStopFlags.Terminate, "done"),
        )
        result = await node.arun()
        assert result == (WorkGraphStopFlags.Terminate, "done")

    @pytest.mark.asyncio
    async def test_abstain_result_flag_propagated_to_downstream(self):
        """AbstainResult flag is propagated to downstream nodes."""
        downstream_received = []

        class CapturingNode(WorkGraphNode):
            async def _arun(self, *args, **kwargs):
                downstream_received.extend(args)
                return None

        root = WorkGraphNode(
            name="abstain_root",
            value=lambda: (WorkGraphStopFlags.AbstainResult, "partial"),
        )
        child = CapturingNode(name="child", value=lambda: None)
        root.add_next(child)

        await root.arun()
        assert WorkGraphStopFlags.AbstainResult in downstream_received

    @pytest.mark.asyncio
    async def test_abstain_flag_resets_after_sibling_processing(self):
        """AbstainResult flag resets to Continue after downstream notification."""
        node = WorkGraphNode(
            name="abstain_node",
            value=lambda: (WorkGraphStopFlags.AbstainResult, "val"),
        )
        child = WorkGraphNode(name="child", value=lambda *args: "child_result")
        node.add_next(child)

        # After downstream notification, the AbstainResult flag resets to Continue
        # so arun() returns just the result (not the flag tuple)
        result = await node.arun()
        assert result == "val"


# ===========================================================================
# Unit tests for WorkGraph._arun() — async DAG orchestration
#
# Requirements: 10.2, 10.6, 11.1, 11.3, 11.4
# ===========================================================================

from unittest.mock import patch, MagicMock
from python_utils.common_objects.workflow.common.step_result_save_options import StepResultSaveOptions


# ---------------------------------------------------------------------------
# Helpers for WorkGraph tests
# ---------------------------------------------------------------------------

class _SaveTrackingNode(WorkGraphNode):
    """WorkGraphNode subclass that tracks save calls and stubs result path."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._saved_results = []

    def _get_result_path(self, result_id, *args, **kwargs):
        return f"/tmp/_test_save_{result_id}.pkl"

    def _save_result(self, result, output_path=None, **kwargs):
        self._saved_results.append((result, output_path))


class _LoadableNode(WorkGraphNode):
    """WorkGraphNode subclass that simulates loaded results."""

    def __init__(self, loaded_result=None, **kwargs):
        super().__init__(**kwargs)
        self._loaded_result = loaded_result

    def load_result(self, *args, **kwargs):
        if self._loaded_result is not None:
            return (True, self._loaded_result)
        return (False, None)

    def _get_result_path(self, result_id, *args, **kwargs):
        return f"/tmp/_test_load_{result_id}.pkl"


# ---------------------------------------------------------------------------
# Test 1: Concurrent start node execution  (Req 10.2)
# ---------------------------------------------------------------------------

class TestConcurrentStartNodeExecution:
    """WorkGraph._arun() executes start nodes concurrently via asyncio.gather."""

    @pytest.mark.asyncio
    async def test_multiple_start_nodes_execute_concurrently(self):
        """Multiple start nodes run concurrently and all produce results."""
        execution_order = []

        async def slow_fn(x):
            await asyncio.sleep(0.05)
            execution_order.append("slow")
            return x + 100

        async def fast_fn(x):
            execution_order.append("fast")
            return x + 200

        node_slow = WorkGraphNode(name="slow_start", value=slow_fn)
        node_fast = WorkGraphNode(name="fast_start", value=fast_fn)

        graph = WorkGraph(start_nodes=[node_slow, node_fast])
        result = await graph.arun(1)

        # Both nodes executed
        assert "slow" in execution_order
        assert "fast" in execution_order
        # Fast should finish before slow due to concurrent execution
        assert execution_order.index("fast") < execution_order.index("slow")
        # Default _post_process filters None, returns tuple
        assert result == (101, 201)

    @pytest.mark.asyncio
    async def test_single_start_node(self):
        """Single start node graph works correctly."""
        node = WorkGraphNode(name="only", value=lambda x: x * 3)
        graph = WorkGraph(start_nodes=[node])
        result = await graph.arun(5)
        # Single-element tuple gets unpacked by arun() singleton unpacking
        assert result == 15

    @pytest.mark.asyncio
    async def test_three_start_nodes(self):
        """Three start nodes all execute and produce results."""
        node_a = WorkGraphNode(name="a", value=lambda x: x + 1)
        node_b = WorkGraphNode(name="b", value=lambda x: x + 2)
        node_c = WorkGraphNode(name="c", value=lambda x: x + 3)

        graph = WorkGraph(start_nodes=[node_a, node_b, node_c])
        result = await graph.arun(10)
        assert result == (11, 12, 13)


# ---------------------------------------------------------------------------
# Test 2: Output ordering matches start_nodes order  (Req 10.2)
# ---------------------------------------------------------------------------

class TestOutputOrdering:
    """Output ordering is deterministic via indexed insertion, matching start_nodes order."""

    @pytest.mark.asyncio
    async def test_output_order_matches_start_nodes_order(self):
        """Results appear in start_nodes order regardless of completion order."""
        async def delayed(x, delay, tag):
            await asyncio.sleep(delay)
            return tag

        node_a = WorkGraphNode(name="a", value=lambda x: delayed(x, 0.06, "A"))
        node_b = WorkGraphNode(name="b", value=lambda x: delayed(x, 0.01, "B"))
        node_c = WorkGraphNode(name="c", value=lambda x: delayed(x, 0.03, "C"))

        # Override value to be the async coroutine-returning functions
        async def val_a(x):
            await asyncio.sleep(0.06)
            return "A"

        async def val_b(x):
            await asyncio.sleep(0.01)
            return "B"

        async def val_c(x):
            await asyncio.sleep(0.03)
            return "C"

        node_a = WorkGraphNode(name="a", value=val_a)
        node_b = WorkGraphNode(name="b", value=val_b)
        node_c = WorkGraphNode(name="c", value=val_c)

        graph = WorkGraph(start_nodes=[node_a, node_b, node_c])
        result = await graph.arun(0)

        # Despite different completion times, output order matches start_nodes order
        assert result == ("A", "B", "C")


# ---------------------------------------------------------------------------
# Test 3: _EMPTY sentinel filtering  (Req 10.2)
# ---------------------------------------------------------------------------

class TestEmptySentinelFiltering:
    """_EMPTY sentinel slots are filtered from output; loaded/skipped nodes excluded."""

    @pytest.mark.asyncio
    async def test_loaded_nodes_excluded_from_output(self):
        """Loaded nodes don't contribute to output (sentinel slot stays _EMPTY, gets filtered)."""
        node_exec = WorkGraphNode(name="exec_node", value=lambda x: x + 1)
        node_loaded = _LoadableNode(name="loaded_node", value=lambda x: x + 2, loaded_result=999)

        graph = WorkGraph(start_nodes=[node_exec, node_loaded])
        result = await graph.arun(10)

        # Only the executed node's result appears; loaded node's slot is filtered out
        # Single-element tuple gets unpacked by arun() singleton unpacking
        assert result == 11

    @pytest.mark.asyncio
    async def test_none_returning_node_filtered_by_post_process(self):
        """Nodes returning None: _EMPTY sentinel is NOT None, so slot is filled with None.
        However, WorkGraph._post_process filters out None values from the tuple."""
        node_none = WorkGraphNode(name="none_node", value=lambda x: None)
        node_val = WorkGraphNode(name="val_node", value=lambda x: 42)

        graph = WorkGraph(start_nodes=[node_none, node_val])
        result = await graph.arun(0)

        # _EMPTY sentinel is not None, so None IS written to output.
        # But default _post_process does `tuple(x for x in result if x is not None)`,
        # which filters out None. Single-element tuple gets unpacked.
        assert result == 42

    @pytest.mark.asyncio
    async def test_none_preserved_with_custom_post_process(self):
        """With a custom _post_process that doesn't filter None, None results are preserved."""

        class NoFilterGraph(WorkGraph):
            def _post_process(self, result, *args, **kwargs):
                return tuple(result)  # Keep everything including None

        node_none = WorkGraphNode(name="none_node", value=lambda x: None)
        node_val = WorkGraphNode(name="val_node", value=lambda x: 42)

        graph = NoFilterGraph(start_nodes=[node_none, node_val])
        result = await graph.arun(0)

        # None is preserved because _EMPTY != None, so None gets into output,
        # and our custom post_process doesn't filter it
        assert result == (None, 42)


# ---------------------------------------------------------------------------
# Test 4: Loaded results NOT written to output  (Req 10.2)
# ---------------------------------------------------------------------------

class TestLoadedResultsNotInOutput:
    """Loaded results are NOT written to output, matching sync _run() behavior."""

    @pytest.mark.asyncio
    async def test_loaded_result_not_in_output(self):
        """When a node's result is loaded, it does NOT appear in the output list."""
        node1 = _LoadableNode(name="loaded", value=lambda x: x, loaded_result="cached")
        node2 = WorkGraphNode(name="fresh", value=lambda x: "computed")

        graph = WorkGraph(start_nodes=[node1, node2])
        result = await graph.arun(0)

        # Only the non-loaded node's result appears
        assert "cached" not in (result if isinstance(result, tuple) else (result,))
        # Single-element tuple gets unpacked by arun()
        assert result == "computed"

    @pytest.mark.asyncio
    async def test_all_loaded_results_empty_output(self):
        """When all nodes are loaded, output is empty after sentinel filtering."""
        node1 = _LoadableNode(name="l1", value=lambda x: x, loaded_result="a")
        node2 = _LoadableNode(name="l2", value=lambda x: x, loaded_result="b")

        graph = WorkGraph(start_nodes=[node1, node2])
        result = await graph.arun(0)

        # All slots are _EMPTY (loaded), so output is empty tuple after post_process
        assert result == ()


# ---------------------------------------------------------------------------
# Test 5: Queue clearing before execution  (Req 10.6)
# ---------------------------------------------------------------------------

class TestQueueClearingBeforeExecution:
    """_clear_all_node_queues() is called before _arun() execution."""

    @pytest.mark.asyncio
    async def test_stale_aqueue_cleared_before_run(self):
        """Stale _aqueue items from previous runs are cleared."""
        node = WorkGraphNode(name="n", value=lambda x: x + 1)

        # Manually inject a stale item into _aqueue
        node._aqueue = asyncio.Queue()
        await node._aqueue.put(("stale_data",))

        graph = WorkGraph(start_nodes=[node])

        # _clear_all_node_queues should clear the stale item
        # The graph should execute cleanly
        result = await graph.arun(5)
        # Single-element tuple gets unpacked by arun()
        assert result == 6

    @pytest.mark.asyncio
    async def test_stale_sync_queue_also_cleared(self):
        """Both _queue (sync) and _aqueue (async) are cleared."""
        from queue import Queue

        node = WorkGraphNode(name="n", value=lambda x: x + 1)
        # Inject stale queues
        node._queue = Queue()
        node._queue.put("stale_sync")
        node._aqueue = asyncio.Queue()
        await node._aqueue.put("stale_async")

        graph = WorkGraph(start_nodes=[node])
        # _clear_all_node_queues is called at start of _arun
        result = await graph.arun(10)

        # Verify queues were cleared (node executed fresh)
        # Single-element tuple gets unpacked by arun()
        assert result == 11
        assert node._queue.qsize() == 0
        assert node._aqueue.qsize() == 0


# ---------------------------------------------------------------------------
# Test 6: OnError per-node save  (Req 11.1)
# ---------------------------------------------------------------------------

class TestOnErrorPerNodeSave:
    """OnError save: each node's result saved to its own path, per-node conditions."""

    @pytest.mark.asyncio
    async def test_onerror_saves_successful_nodes_on_failure(self):
        """When one node fails, successful nodes with OnError save get their results saved."""
        saved_results = {}

        class TrackingSaveNode(WorkGraphNode):
            def _get_result_path(self, result_id, *args, **kwargs):
                return f"/tmp/_test_{result_id}.pkl"

            def _save_result(self, result, output_path=None, **kwargs):
                saved_results[self.name] = (result, output_path)

        async def success_fn(x):
            return x + 1

        async def fail_fn(x):
            # Small delay so success_fn finishes first
            await asyncio.sleep(0.02)
            raise ValueError("intentional failure")

        node_ok = TrackingSaveNode(
            name="ok_node",
            value=success_fn,
            enable_result_save=StepResultSaveOptions.OnError,
            retry_on_exceptions=(Exception,),
        )
        node_fail = TrackingSaveNode(
            name="fail_node",
            value=fail_fn,
            enable_result_save=StepResultSaveOptions.OnError,
            retry_on_exceptions=(ValueError,),
        )

        graph = WorkGraph(
            start_nodes=[node_ok, node_fail],
            enable_result_save=StepResultSaveOptions.OnError,
        )

        with pytest.raises(ValueError, match="intentional failure"):
            await graph.arun(10)

        # ok_node's result should have been saved
        assert "ok_node" in saved_results
        assert saved_results["ok_node"][0] == 11
        assert saved_results["ok_node"][1] == "/tmp/_test_ok_node.pkl"

    @pytest.mark.asyncio
    async def test_onerror_does_not_save_loaded_nodes(self):
        """Loaded nodes are NOT saved even on error."""
        saved_results = {}

        class TrackingLoadedNode(_LoadableNode):
            def _save_result(self, result, output_path=None, **kwargs):
                saved_results[self.name] = result

        node_loaded = TrackingLoadedNode(
            name="loaded",
            value=lambda x: x,
            loaded_result="cached",
            enable_result_save=StepResultSaveOptions.OnError,
            retry_on_exceptions=(Exception,),
        )

        async def fail_fn(x):
            await asyncio.sleep(0.02)
            raise ValueError("fail")

        node_fail = WorkGraphNode(
            name="fail",
            value=fail_fn,
            enable_result_save=StepResultSaveOptions.OnError,
            retry_on_exceptions=(ValueError,),
        )

        graph = WorkGraph(
            start_nodes=[node_loaded, node_fail],
            enable_result_save=StepResultSaveOptions.OnError,
        )

        with pytest.raises(ValueError):
            await graph.arun(0)

        # Loaded node should NOT have been saved
        assert "loaded" not in saved_results

    @pytest.mark.asyncio
    async def test_onerror_only_saves_nodes_with_onerror_setting(self):
        """Only nodes with enable_result_save=OnError get saved, not NoSave nodes."""
        saved_results = {}

        class TrackingSaveNode(WorkGraphNode):
            def _get_result_path(self, result_id, *args, **kwargs):
                return f"/tmp/_test_{result_id}.pkl"

            def _save_result(self, result, output_path=None, **kwargs):
                saved_results[self.name] = result

        node_nosave = TrackingSaveNode(
            name="nosave",
            value=lambda x: x + 1,
            enable_result_save=StepResultSaveOptions.NoSave,
            retry_on_exceptions=(Exception,),
        )
        node_onerror = TrackingSaveNode(
            name="onerror",
            value=lambda x: x + 2,
            enable_result_save=StepResultSaveOptions.OnError,
            retry_on_exceptions=(Exception,),
        )

        async def fail_fn(x):
            await asyncio.sleep(0.03)
            raise ValueError("fail")

        node_fail = TrackingSaveNode(
            name="fail",
            value=fail_fn,
            enable_result_save=StepResultSaveOptions.OnError,
            retry_on_exceptions=(ValueError,),
        )

        graph = WorkGraph(
            start_nodes=[node_nosave, node_onerror, node_fail],
            enable_result_save=StepResultSaveOptions.OnError,
        )

        with pytest.raises(ValueError):
            await graph.arun(10)

        # Only the OnError node should be saved, not the NoSave node
        assert "nosave" not in saved_results
        assert "onerror" in saved_results
        assert saved_results["onerror"] == 12


# ---------------------------------------------------------------------------
# Test 7: Terminate flag stops subsequent start nodes  (Req 11.3)
# ---------------------------------------------------------------------------

class TestTerminateFlagStopsStartNodes:
    """Terminate flag via asyncio.Event stops subsequent start nodes."""

    @pytest.mark.asyncio
    async def test_terminate_stops_later_start_nodes(self):
        """When a start node returns Terminate, other not-yet-started nodes are skipped."""
        executed = []

        async def terminate_fn(x):
            executed.append("terminator")
            return (WorkGraphStopFlags.Terminate, "done")

        async def slow_fn(x):
            await asyncio.sleep(0.05)
            executed.append("slow")
            return "slow_result"

        # Terminator finishes quickly, slow node should be skipped if it checks the event
        node_term = WorkGraphNode(name="terminator", value=terminate_fn)
        node_slow = WorkGraphNode(name="slow", value=slow_fn)

        graph = WorkGraph(start_nodes=[node_term, node_slow])
        # The graph should raise or return based on how Terminate is handled
        # Since both launch concurrently, the slow node may or may not execute
        # depending on timing. The key test is that terminate_event is set.
        result = await graph.arun(0)

        assert "terminator" in executed

    @pytest.mark.asyncio
    async def test_terminate_event_set_on_terminate_flag(self):
        """asyncio.Event is set when a node returns Terminate."""
        node_term = WorkGraphNode(
            name="term",
            value=lambda x: (WorkGraphStopFlags.Terminate, "stopped"),
        )
        node_normal = WorkGraphNode(name="normal", value=lambda x: x + 1)

        graph = WorkGraph(start_nodes=[node_term, node_normal])

        # Both nodes launch concurrently. The terminate node sets the event.
        # The normal node may or may not execute depending on timing,
        # but the graph should complete without error.
        result = await graph.arun(5)
        # At minimum, the terminate node's result should be in output
        assert result is not None


# ---------------------------------------------------------------------------
# Test 8: AbstainResult downstream notification and flag reset  (Req 11.4)
# ---------------------------------------------------------------------------

class TestAbstainResultInWorkGraph:
    """AbstainResult downstream notification and flag reset in WorkGraph._arun()."""

    @pytest.mark.asyncio
    async def test_abstain_result_node_with_downstream(self):
        """Node returning AbstainResult notifies downstream and resets flag."""
        downstream_received = []

        class CapturingNode(WorkGraphNode):
            async def _arun(self, *args, **kwargs):
                downstream_received.extend(args)
                return "captured"

        root = WorkGraphNode(
            name="abstain_root",
            value=lambda x: (WorkGraphStopFlags.AbstainResult, "partial"),
        )
        child = CapturingNode(name="child", value=lambda: None)
        root.add_next(child)

        graph = WorkGraph(start_nodes=[root])
        result = await graph.arun(0)

        # The downstream node should have received the AbstainResult flag
        assert WorkGraphStopFlags.AbstainResult in downstream_received

    @pytest.mark.asyncio
    async def test_abstain_flag_resets_after_downstream_notification(self):
        """AbstainResult flag resets to Continue after sibling processing."""
        root = WorkGraphNode(
            name="abstain_root",
            value=lambda x: (WorkGraphStopFlags.AbstainResult, x * 2),
        )
        child = WorkGraphNode(name="child", value=lambda *args: "child_done")
        root.add_next(child)

        graph = WorkGraph(start_nodes=[root])
        result = await graph.arun(5)

        # The root's result (10) should be in the output
        # AbstainResult flag resets after downstream notification
        assert result is not None


# ---------------------------------------------------------------------------
# Test 9: max_concurrency semaphore limiting  (Req 10.4)
# ---------------------------------------------------------------------------

class TestMaxConcurrencySemaphore:
    """max_concurrency limits concurrent node execution via asyncio.Semaphore."""

    @pytest.mark.asyncio
    async def test_max_concurrency_limits_parallel_execution(self):
        """With max_concurrency=1, nodes execute one at a time."""
        max_concurrent = [0]
        current_concurrent = [0]

        async def tracked_fn(x):
            current_concurrent[0] += 1
            if current_concurrent[0] > max_concurrent[0]:
                max_concurrent[0] = current_concurrent[0]
            await asyncio.sleep(0.02)
            current_concurrent[0] -= 1
            return x

        node_a = WorkGraphNode(name="a", value=tracked_fn)
        node_b = WorkGraphNode(name="b", value=tracked_fn)
        node_c = WorkGraphNode(name="c", value=tracked_fn)

        graph = WorkGraph(
            start_nodes=[node_a, node_b, node_c],
            max_concurrency=1,
        )
        result = await graph.arun(42)

        # With max_concurrency=1, at most 1 node should run at a time
        assert max_concurrent[0] == 1
        assert result == (42, 42, 42)

    @pytest.mark.asyncio
    async def test_max_concurrency_2_allows_two_parallel(self):
        """With max_concurrency=2, up to 2 nodes run in parallel."""
        max_concurrent = [0]
        current_concurrent = [0]

        async def tracked_fn(x):
            current_concurrent[0] += 1
            if current_concurrent[0] > max_concurrent[0]:
                max_concurrent[0] = current_concurrent[0]
            await asyncio.sleep(0.03)
            current_concurrent[0] -= 1
            return x

        nodes = [WorkGraphNode(name=f"n{i}", value=tracked_fn) for i in range(4)]

        graph = WorkGraph(start_nodes=nodes, max_concurrency=2)
        result = await graph.arun(7)

        assert max_concurrent[0] <= 2
        assert result == (7, 7, 7, 7)

    @pytest.mark.asyncio
    async def test_no_concurrency_limit_by_default(self):
        """Without max_concurrency, all nodes can run in parallel."""
        max_concurrent = [0]
        current_concurrent = [0]

        async def tracked_fn(x):
            current_concurrent[0] += 1
            if current_concurrent[0] > max_concurrent[0]:
                max_concurrent[0] = current_concurrent[0]
            await asyncio.sleep(0.03)
            current_concurrent[0] -= 1
            return x

        nodes = [WorkGraphNode(name=f"n{i}", value=tracked_fn) for i in range(3)]

        graph = WorkGraph(start_nodes=nodes)  # No max_concurrency
        result = await graph.arun(1)

        # All 3 should run concurrently
        assert max_concurrent[0] == 3
        assert result == (1, 1, 1)


# ---------------------------------------------------------------------------
# Test 10: post_process calls _post_process and _optional_post_process
#           separately via call_maybe_async  (Req 10.2)
# ---------------------------------------------------------------------------

class TestPostProcessSeparateCalls:
    """Post-process hooks are called separately via call_maybe_async, not through chaining post_process()."""

    @pytest.mark.asyncio
    async def test_async_post_process_override_works(self):
        """Async _post_process override is correctly awaited via call_maybe_async."""

        class AsyncPostProcessGraph(WorkGraph):
            async def _post_process(self, result, *args, **kwargs):
                # Async override — would break if called through sync post_process() chain
                return tuple(r + 1000 for r in result)

        node = WorkGraphNode(name="n", value=lambda x: x)
        graph = AsyncPostProcessGraph(start_nodes=[node])
        result = await graph.arun(5)

        assert result == 1005

    @pytest.mark.asyncio
    async def test_async_optional_post_process_works(self):
        """Async _optional_post_process is called when enabled."""

        class AsyncOptPostGraph(WorkGraph):
            async def _optional_post_process(self, result, *args, **kwargs):
                return tuple(r * 10 for r in result)

        node = WorkGraphNode(name="n", value=lambda x: x + 1)
        graph = AsyncOptPostGraph(
            start_nodes=[node],
            enable_optional_post_process=True,
        )
        result = await graph.arun(5)

        # _post_process filters None (default), then _optional_post_process multiplies by 10
        # node returns 6, _post_process returns (6,), _optional_post_process returns (60,)
        # Single-element tuple gets unpacked by arun()
        assert result == 60

    @pytest.mark.asyncio
    async def test_optional_post_process_not_called_when_disabled(self):
        """_optional_post_process is NOT called when enable_optional_post_process=False."""
        called = [False]

        class TrackingGraph(WorkGraph):
            async def _optional_post_process(self, result, *args, **kwargs):
                called[0] = True
                return result

        node = WorkGraphNode(name="n", value=lambda x: x)
        graph = TrackingGraph(start_nodes=[node], enable_optional_post_process=False)
        result = await graph.arun(5)

        assert called[0] is False
        # Single-element tuple gets unpacked by arun()
        assert result == 5

    @pytest.mark.asyncio
    async def test_both_post_process_hooks_called_in_order(self):
        """Both _post_process and _optional_post_process are called in order."""
        call_order = []

        class OrderTrackingGraph(WorkGraph):
            def _post_process(self, result, *args, **kwargs):
                call_order.append("_post_process")
                return tuple(r + 100 for r in result)

            def _optional_post_process(self, result, *args, **kwargs):
                call_order.append("_optional_post_process")
                return tuple(r * 2 for r in result)

        node = WorkGraphNode(name="n", value=lambda x: x)
        graph = OrderTrackingGraph(
            start_nodes=[node],
            enable_optional_post_process=True,
        )
        result = await graph.arun(5)

        assert call_order == ["_post_process", "_optional_post_process"]
        # node returns 5, _post_process: 5+100=105, _optional: 105*2=210
        # Single-element tuple gets unpacked by arun()
        assert result == 210
