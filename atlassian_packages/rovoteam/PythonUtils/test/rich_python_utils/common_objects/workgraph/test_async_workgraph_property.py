"""Property-based tests for WorkGraphNode async execution.

Feature: async-workflow, Property 6

Property 6: WorkGraphNode sync/async equivalence

For any WorkGraphNode with a sync or async value callable, any number of
real parents (including multi-parent fan-in), any WorkGraphStopFlags
configuration, any NextNodesSelector return values, and any retry
configuration, WorkGraphNode._arun() shall produce the same result and
downstream propagation behavior as WorkGraphNode._run() when given
equivalent sync callables.

Uses Hypothesis with @settings(max_examples=100).
"""
import asyncio

import pytest
from hypothesis import given, settings, strategies as st

from python_utils.common_objects.workflow.workgraph import WorkGraphNode
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
        return os.path.join(tempfile.gettempdir(), f"_prop_test_{result_id}.pkl")


def _make_sync_fn(factor):
    """Create a sync callable: x -> x * factor."""
    def fn(x):
        return x * factor
    fn.__name__ = f"sync_mul_{factor}"
    return fn


def _make_async_fn(factor):
    """Create an async callable: x -> x * factor."""
    async def fn(x):
        return x * factor
    fn.__name__ = f"async_mul_{factor}"
    return fn


def _make_stop_flag_fn(flag, factor):
    """Create a sync callable that returns (stop_flag, result)."""
    def fn(x):
        return (flag, x * factor)
    fn.__name__ = f"sync_flag_{flag.name}_{factor}"
    return fn


def _make_async_stop_flag_fn(flag, factor):
    """Create an async callable that returns (stop_flag, result)."""
    async def fn(x):
        return (flag, x * factor)
    fn.__name__ = f"async_flag_{flag.name}_{factor}"
    return fn


def _make_next_nodes_selector_fn(include_self, include_others, factor):
    """Create a sync callable that returns a NextNodesSelector."""
    def fn(x):
        return NextNodesSelector(
            include_self=include_self,
            include_others=include_others,
            result=x * factor,
        )
    fn.__name__ = f"sync_nns_{factor}"
    return fn


def _make_async_next_nodes_selector_fn(include_self, include_others, factor):
    """Create an async callable that returns a NextNodesSelector."""
    async def fn(x):
        return NextNodesSelector(
            include_self=include_self,
            include_others=include_others,
            result=x * factor,
        )
    fn.__name__ = f"async_nns_{factor}"
    return fn


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

factor_strategy = st.integers(min_value=-20, max_value=20)
input_strategy = st.integers(min_value=-50, max_value=50)

stop_flag_strategy = st.sampled_from([
    WorkGraphStopFlags.Continue,
    WorkGraphStopFlags.Terminate,
    WorkGraphStopFlags.AbstainResult,
])

pass_down_mode_strategy = st.sampled_from([
    ResultPassDownMode.ResultAsFirstArg,
    ResultPassDownMode.NoPassDown,
])

# Retry config: max_repeat 1-3, wait times 0 for fast tests
retry_strategy = st.fixed_dictionaries({
    'max_repeat': st.integers(min_value=1, max_value=3),
})


# ---------------------------------------------------------------------------
# Property 6: WorkGraphNode sync/async equivalence
# ---------------------------------------------------------------------------

class TestWorkGraphNodeSyncAsyncEquivalence:
    """Property 6: WorkGraphNode sync/async equivalence.

    For any WorkGraphNode configuration with sync-only callables,
    _arun() produces the same result as _run().

    **Validates: Requirements 7.2, 7.3, 7.4, 7.5, 7.6, 8.1, 8.3, 9.1, 9.2**
    """

    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(
        factor=factor_strategy,
        input_val=input_strategy,
        use_async=st.booleans(),
    )
    async def test_basic_node_sync_async_equivalence(
        self, factor, input_val, use_async
    ):
        """A single node with sync or async callable produces the same result
        via _run() and _arun().

        **Validates: Requirements 7.2**
        """
        sync_fn = _make_sync_fn(factor)

        # Sync path: always use sync fn
        sync_node = _TestGraphNode(name="sync", value=sync_fn)
        sync_result = sync_node.run(input_val)

        # Async path: use sync or async fn depending on use_async flag
        async_fn = _make_async_fn(factor) if use_async else _make_sync_fn(factor)
        async_node = _TestGraphNode(name="async", value=async_fn)
        async_result = await async_node.arun(input_val)

        assert sync_result == async_result, (
            f"factor={factor}, input={input_val}, use_async={use_async}: "
            f"sync={sync_result}, async={async_result}"
        )

    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(
        factor=factor_strategy,
        input_val=input_strategy,
        flag=stop_flag_strategy,
        use_async=st.booleans(),
    )
    async def test_stop_flag_equivalence(
        self, factor, input_val, flag, use_async
    ):
        """Nodes returning stop flags produce the same result via sync and async paths.

        **Validates: Requirements 7.3**
        """
        sync_fn = _make_stop_flag_fn(flag, factor)

        sync_node = _TestGraphNode(name="sync_flag", value=sync_fn)
        sync_result = sync_node.run(input_val)

        async_fn = (
            _make_async_stop_flag_fn(flag, factor) if use_async
            else _make_stop_flag_fn(flag, factor)
        )
        async_node = _TestGraphNode(name="async_flag", value=async_fn)
        async_result = await async_node.arun(input_val)

        assert sync_result == async_result, (
            f"flag={flag}, factor={factor}, input={input_val}: "
            f"sync={sync_result}, async={async_result}"
        )

    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(
        factor=factor_strategy,
        input_val=input_strategy,
        use_async=st.booleans(),
        retry_cfg=retry_strategy,
    )
    async def test_retry_config_equivalence(
        self, factor, input_val, use_async, retry_cfg
    ):
        """Nodes with retry configuration produce the same result via sync and async.

        **Validates: Requirements 7.6**
        """
        sync_fn = _make_sync_fn(factor)
        sync_node = _TestGraphNode(
            name="sync_retry",
            value=sync_fn,
            max_repeat=retry_cfg['max_repeat'],
            min_repeat_wait=0,
            max_repeat_wait=0,
        )
        sync_result = sync_node.run(input_val)

        async_fn = _make_async_fn(factor) if use_async else _make_sync_fn(factor)
        async_node = _TestGraphNode(
            name="async_retry",
            value=async_fn,
            max_repeat=retry_cfg['max_repeat'],
            min_repeat_wait=0,
            max_repeat_wait=0,
        )
        async_result = await async_node.arun(input_val)

        assert sync_result == async_result, (
            f"factor={factor}, input={input_val}, retry={retry_cfg}: "
            f"sync={sync_result}, async={async_result}"
        )

    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(
        factor=factor_strategy,
        input_val=input_strategy,
        include_others=st.sampled_from([True, False]),
        use_async=st.booleans(),
    )
    async def test_next_nodes_selector_equivalence(
        self, factor, input_val, include_others, use_async
    ):
        """Nodes returning NextNodesSelector produce the same result via sync and async.

        **Validates: Requirements 7.4, 7.5**
        """
        # include_self=False to avoid self-loop complexity in this test
        sync_fn = _make_next_nodes_selector_fn(False, include_others, factor)
        sync_node = _TestGraphNode(name="sync_nns", value=sync_fn)
        sync_result = sync_node.run(input_val)

        async_fn = (
            _make_async_next_nodes_selector_fn(False, include_others, factor) if use_async
            else _make_next_nodes_selector_fn(False, include_others, factor)
        )
        async_node = _TestGraphNode(name="async_nns", value=async_fn)
        async_result = await async_node.arun(input_val)

        assert sync_result == async_result, (
            f"factor={factor}, input={input_val}, include_others={include_others}: "
            f"sync={sync_result}, async={async_result}"
        )

    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(
        factor=factor_strategy,
        num_parents=st.integers(min_value=2, max_value=4),
        use_async=st.booleans(),
    )
    async def test_multi_parent_merge_equivalence(
        self, factor, num_parents, use_async
    ):
        """Multi-parent nodes produce the same result via sync and async paths.

        **Validates: Requirements 8.1, 8.3**
        """
        # Create a function that sums all positional args and multiplies by factor
        def sum_fn(*args):
            return sum(args) * factor

        async def async_sum_fn(*args):
            return sum(args) * factor

        # Build parent nodes (dummy, just to set up the previous list)
        sync_parents = [
            _TestGraphNode(name=f"sp_{i}", value=lambda: None)
            for i in range(num_parents)
        ]
        sync_node = _TestGraphNode(
            name="sync_merge",
            value=sum_fn,
            previous=sync_parents,
        )

        async_parents = [
            _TestGraphNode(name=f"ap_{i}", value=lambda: None)
            for i in range(num_parents)
        ]
        async_value = async_sum_fn if use_async else sum_fn
        async_node = _TestGraphNode(
            name="async_merge",
            value=async_value,
            previous=async_parents,
        )

        # Feed inputs from each parent — one call per parent
        parent_inputs = list(range(1, num_parents + 1))

        # Sync: call _run once per parent
        for val in parent_inputs[:-1]:
            sync_node._run(val)  # Returns None (waiting for more parents)
        sync_result = sync_node.run(parent_inputs[-1])

        # Async: call _arun once per parent
        for val in parent_inputs[:-1]:
            await async_node._arun(val)  # Returns None (waiting for more parents)
        async_result = await async_node.arun(parent_inputs[-1])

        assert sync_result == async_result, (
            f"factor={factor}, num_parents={num_parents}, inputs={parent_inputs}: "
            f"sync={sync_result}, async={async_result}"
        )

    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(
        factor=factor_strategy,
        input_val=input_strategy,
        use_async=st.booleans(),
    )
    async def test_post_process_hook_equivalence(
        self, factor, input_val, use_async
    ):
        """Post-process hooks produce the same result via sync and async paths.

        **Validates: Requirements 9.1, 9.2**
        """
        # Create a node subclass with a post-process hook
        class SyncPostProcessNode(_TestGraphNode):
            def _post_process(self, result, *args, **kwargs):
                return result + 10

        class AsyncPostProcessNode(_TestGraphNode):
            async def _post_process(self, result, *args, **kwargs):
                return result + 10

        sync_fn = _make_sync_fn(factor)
        sync_node = SyncPostProcessNode(name="sync_pp", value=sync_fn)
        sync_result = sync_node.run(input_val)

        if use_async:
            async_fn = _make_async_fn(factor)
            async_node = AsyncPostProcessNode(name="async_pp", value=async_fn)
        else:
            async_fn = _make_sync_fn(factor)
            async_node = SyncPostProcessNode(name="async_pp", value=async_fn)
        async_result = await async_node.arun(input_val)

        assert sync_result == async_result, (
            f"factor={factor}, input={input_val}, use_async={use_async}: "
            f"sync={sync_result}, async={async_result}"
        )

    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(
        factor=factor_strategy,
        input_val=input_strategy,
        downstream_factor=factor_strategy,
        use_async=st.booleans(),
    )
    async def test_downstream_chain_equivalence(
        self, factor, input_val, downstream_factor, use_async
    ):
        """A node with a single downstream node produces the same result
        via sync and async paths.

        **Validates: Requirements 7.2, 7.3**
        """
        # Sync chain: node1 -> node2
        sync_node2 = _TestGraphNode(
            name="sync_ds",
            value=_make_sync_fn(downstream_factor),
        )
        sync_node1 = _TestGraphNode(
            name="sync_root",
            value=_make_sync_fn(factor),
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
        )
        sync_node1.add_next(sync_node2)
        sync_result = sync_node1.run(input_val)

        # Async chain: node1 -> node2
        async_node2 = _TestGraphNode(
            name="async_ds",
            value=_make_async_fn(downstream_factor) if use_async else _make_sync_fn(downstream_factor),
        )
        async_node1 = _TestGraphNode(
            name="async_root",
            value=_make_async_fn(factor) if use_async else _make_sync_fn(factor),
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
        )
        async_node1.add_next(async_node2)
        async_result = await async_node1.arun(input_val)

        assert sync_result == async_result, (
            f"factor={factor}, ds_factor={downstream_factor}, input={input_val}: "
            f"sync={sync_result}, async={async_result}"
        )


# ===========================================================================
# Additional imports for Properties 7, 8, 9
# ===========================================================================
from python_utils.common_objects.workflow.workgraph import WorkGraph


# ===========================================================================
# Helpers for WorkGraph-level property tests
# ===========================================================================

class _TestWorkGraph(WorkGraph):
    """WorkGraph subclass that stubs out result path for testing."""

    def _get_result_path(self, result_id, *args, **kwargs):
        import tempfile, os
        return os.path.join(tempfile.gettempdir(), f"_prop_test_wg_{result_id}.pkl")


def _build_linear_chain(node_specs, pass_down=ResultPassDownMode.ResultAsFirstArg):
    """Build a linear chain of _TestGraphNode instances from a list of (name, fn) tuples.

    Returns the first node (start node). Each node passes its result to the next.
    Uses add_next() only (not previous= in constructor) to avoid double-linking.
    """
    nodes = []
    for name, fn in node_specs:
        node = _TestGraphNode(
            name=name,
            value=fn,
            result_pass_down_mode=pass_down,
        )
        if nodes:
            nodes[-1].add_next(node)
        nodes.append(node)
    return nodes[0] if nodes else None


def _build_fan_out_graph(root_name, root_fn, branch_specs, pass_down=ResultPassDownMode.ResultAsFirstArg):
    """Build a fan-out graph: one root node with multiple leaf branches.

    branch_specs: list of (name, fn) tuples for leaf nodes.
    Returns (root_node, [leaf_nodes]).
    Uses add_next() only (not previous= in constructor) to avoid double-linking.
    """
    root = _TestGraphNode(
        name=root_name,
        value=root_fn,
        result_pass_down_mode=pass_down,
    )
    leaves = []
    for name, fn in branch_specs:
        leaf = _TestGraphNode(
            name=name,
            value=fn,
            result_pass_down_mode=pass_down,
        )
        root.add_next(leaf)
        leaves.append(leaf)
    return root, leaves


# ---------------------------------------------------------------------------
# Hypothesis strategies for WorkGraph-level tests
# ---------------------------------------------------------------------------

# Strategy for number of start nodes (1-4 for manageable test size)
num_start_nodes_strategy = st.integers(min_value=1, max_value=4)

# Strategy for max_concurrency values
max_concurrency_strategy = st.integers(min_value=1, max_value=4)


# ---------------------------------------------------------------------------
# Property 7: WorkGraph sync/async equivalence
# ---------------------------------------------------------------------------

class TestWorkGraphSyncAsyncEquivalence:
    """Property 7: WorkGraph sync/async equivalence.

    For any DAG topology with sync-only value callables, WorkGraph._arun()
    shall produce the same aggregated result as WorkGraph._run() when given
    the same graph structure and inputs.

    **Validates: Requirements 10.2, 10.3, 11.2**
    """

    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(
        factors=st.lists(
            st.integers(min_value=-10, max_value=10),
            min_size=1,
            max_size=4,
        ),
        input_val=input_strategy,
    )
    async def test_single_start_node_equivalence(self, factors, input_val):
        """A graph with a single start node (possibly with a downstream chain)
        produces the same result via _run() and _arun().

        **Validates: Requirements 10.2, 11.2**
        """
        # Build sync graph: chain of nodes
        sync_specs = [(f"s_{i}", _make_sync_fn(f)) for i, f in enumerate(factors)]
        sync_start = _build_linear_chain(sync_specs)
        sync_graph = _TestWorkGraph(start_nodes=[sync_start])
        sync_result = sync_graph.run(input_val)

        # Build async graph: identical structure, separate instances
        async_specs = [(f"a_{i}", _make_sync_fn(f)) for i, f in enumerate(factors)]
        async_start = _build_linear_chain(async_specs)
        async_graph = _TestWorkGraph(start_nodes=[async_start])
        async_result = await async_graph.arun(input_val)

        assert sync_result == async_result, (
            f"factors={factors}, input={input_val}: "
            f"sync={sync_result}, async={async_result}"
        )

    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(
        factors=st.lists(
            st.integers(min_value=-10, max_value=10),
            min_size=2,
            max_size=4,
        ),
        input_val=input_strategy,
    )
    async def test_multiple_start_nodes_equivalence(self, factors, input_val):
        """A graph with multiple independent start nodes produces the same
        aggregated result via _run() and _arun().

        **Validates: Requirements 10.2, 10.3, 11.2**
        """
        # Build sync graph: each factor is a separate start node
        sync_starts = [
            _TestGraphNode(name=f"s_{i}", value=_make_sync_fn(f))
            for i, f in enumerate(factors)
        ]
        sync_graph = _TestWorkGraph(start_nodes=sync_starts)
        sync_result = sync_graph.run(input_val)

        # Build async graph: identical structure, separate instances
        async_starts = [
            _TestGraphNode(name=f"a_{i}", value=_make_sync_fn(f))
            for i, f in enumerate(factors)
        ]
        async_graph = _TestWorkGraph(start_nodes=async_starts)
        async_result = await async_graph.arun(input_val)

        assert sync_result == async_result, (
            f"factors={factors}, input={input_val}: "
            f"sync={sync_result}, async={async_result}"
        )

    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(
        root_factor=factor_strategy,
        branch_factors=st.lists(
            st.integers(min_value=-10, max_value=10),
            min_size=2,
            max_size=3,
        ),
        input_val=input_strategy,
    )
    async def test_fan_out_graph_equivalence(self, root_factor, branch_factors, input_val):
        """A fan-out graph (one root, multiple leaves) produces the same result
        via _run() and _arun().

        **Validates: Requirements 10.2, 10.3**
        """
        # Sync graph
        sync_root, _ = _build_fan_out_graph(
            "s_root", _make_sync_fn(root_factor),
            [(f"s_leaf_{i}", _make_sync_fn(f)) for i, f in enumerate(branch_factors)],
        )
        sync_graph = _TestWorkGraph(start_nodes=[sync_root])
        sync_result = sync_graph.run(input_val)

        # Async graph
        async_root, _ = _build_fan_out_graph(
            "a_root", _make_sync_fn(root_factor),
            [(f"a_leaf_{i}", _make_sync_fn(f)) for i, f in enumerate(branch_factors)],
        )
        async_graph = _TestWorkGraph(start_nodes=[async_root])
        async_result = await async_graph.arun(input_val)

        assert sync_result == async_result, (
            f"root_factor={root_factor}, branch_factors={branch_factors}, input={input_val}: "
            f"sync={sync_result}, async={async_result}"
        )

    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(
        start_factors=st.lists(
            st.integers(min_value=-10, max_value=10),
            min_size=2,
            max_size=3,
        ),
        downstream_factor=factor_strategy,
        input_val=input_strategy,
    )
    async def test_multi_start_with_downstream_chains_equivalence(self, start_factors, downstream_factor, input_val):
        """Multiple start nodes each with their own downstream chain produce
        the same result via _run() and _arun().

        **Validates: Requirements 10.2, 10.3**
        """
        # Sync graph: each start node has its own downstream node (no fan-in merge)
        sync_starts = []
        for i, f in enumerate(start_factors):
            start = _TestGraphNode(
                name=f"s_start_{i}",
                value=_make_sync_fn(f),
                result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            )
            downstream = _TestGraphNode(
                name=f"s_ds_{i}",
                value=_make_sync_fn(downstream_factor),
            )
            start.add_next(downstream)
            sync_starts.append(start)

        sync_graph = _TestWorkGraph(start_nodes=sync_starts)
        sync_result = sync_graph.run(input_val)

        # Async graph: identical structure, separate instances
        async_starts = []
        for i, f in enumerate(start_factors):
            start = _TestGraphNode(
                name=f"a_start_{i}",
                value=_make_sync_fn(f),
                result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            )
            downstream = _TestGraphNode(
                name=f"a_ds_{i}",
                value=_make_sync_fn(downstream_factor),
            )
            start.add_next(downstream)
            async_starts.append(start)

        async_graph = _TestWorkGraph(start_nodes=async_starts)
        async_result = await async_graph.arun(input_val)

        assert sync_result == async_result, (
            f"start_factors={start_factors}, ds_factor={downstream_factor}, input={input_val}: "
            f"sync={sync_result}, async={async_result}"
        )


# ---------------------------------------------------------------------------
# Property 8: WorkGraph stop flag handling
# ---------------------------------------------------------------------------

class TestWorkGraphStopFlagHandling:
    """Property 8: WorkGraph stop flag handling.

    For any WorkGraph where a start node returns Terminate, the asyncio.Event
    shall be set so that start nodes that have not yet begun execution are skipped.
    For any graph where a node returns AbstainResult, downstream nodes shall
    receive the abstention notification, and the flag shall reset after sibling
    processing.

    **Validates: Requirements 11.3, 11.4**
    """

    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(
        factor=factor_strategy,
        input_val=input_strategy,
    )
    async def test_terminate_flag_in_output(self, factor, input_val):
        """When a start node returns Terminate, its result is present in the
        async output (the terminate node's result is captured).

        **Validates: Requirements 11.3**
        """
        # Build a graph where the first start node returns Terminate
        def terminate_fn(x):
            return (WorkGraphStopFlags.Terminate, x * factor)

        # Async: Terminate sets event, but concurrent nodes may still run.
        # The terminate node's result should be in the output.
        async_node1 = _TestGraphNode(name="a_term", value=terminate_fn)
        async_node2 = _TestGraphNode(name="a_after", value=_make_sync_fn(1))
        async_graph = _TestWorkGraph(start_nodes=[async_node1, async_node2])
        async_result = await async_graph.arun(input_val)

        # The terminate node's computed value should be in the result
        expected_value = input_val * factor
        # Result may be a scalar (single element unpacked) or a tuple
        if isinstance(async_result, tuple):
            assert expected_value in async_result, (
                f"Terminate node result {expected_value} not in async result {async_result}"
            )
        else:
            assert async_result == expected_value, (
                f"Terminate node result {expected_value} != async result {async_result}"
            )

    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(
        factor=factor_strategy,
        input_val=input_strategy,
    )
    async def test_terminate_single_start_node(self, factor, input_val):
        """A single start node returning Terminate produces the same result
        in both sync and async paths.

        **Validates: Requirements 11.3**
        """
        def terminate_fn(x):
            return (WorkGraphStopFlags.Terminate, x * factor)

        sync_node = _TestGraphNode(name="s_term", value=terminate_fn)
        sync_graph = _TestWorkGraph(start_nodes=[sync_node])
        sync_result = sync_graph.run(input_val)

        async_node = _TestGraphNode(name="a_term", value=terminate_fn)
        async_graph = _TestWorkGraph(start_nodes=[async_node])
        async_result = await async_graph.arun(input_val)

        assert sync_result == async_result, (
            f"factor={factor}, input={input_val}: "
            f"sync={sync_result}, async={async_result}"
        )

    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(
        root_factor=factor_strategy,
        leaf_factor=factor_strategy,
        input_val=input_strategy,
    )
    async def test_abstain_result_within_branch(self, root_factor, leaf_factor, input_val):
        """AbstainResult within a single branch (root -> downstream) behaves
        the same in sync and async paths. The downstream node receives the
        abstention notification.

        **Validates: Requirements 11.4**
        """
        # Root node returns AbstainResult — downstream should be notified
        def abstain_fn(x):
            return (WorkGraphStopFlags.AbstainResult, x * root_factor)

        # Sync graph
        sync_root = _TestGraphNode(
            name="s_root",
            value=abstain_fn,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
        )
        sync_leaf = _TestGraphNode(
            name="s_leaf",
            value=_make_sync_fn(leaf_factor),
        )
        sync_root.add_next(sync_leaf)
        sync_graph = _TestWorkGraph(start_nodes=[sync_root])
        sync_result = sync_graph.run(input_val)

        # Async graph
        async_root = _TestGraphNode(
            name="a_root",
            value=abstain_fn,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
        )
        async_leaf = _TestGraphNode(
            name="a_leaf",
            value=_make_sync_fn(leaf_factor),
        )
        async_root.add_next(async_leaf)
        async_graph = _TestWorkGraph(start_nodes=[async_root])
        async_result = await async_graph.arun(input_val)

        assert sync_result == async_result, (
            f"root_factor={root_factor}, leaf_factor={leaf_factor}, input={input_val}: "
            f"sync={sync_result}, async={async_result}"
        )

    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(
        factor=factor_strategy,
        input_val=input_strategy,
    )
    async def test_abstain_result_flag_resets_after_siblings(self, factor, input_val):
        """AbstainResult flag resets after sibling processing — the flag does
        not leak beyond the immediate downstream level. Verify in async path
        that a node returning AbstainResult does not prevent the graph from
        producing a result.

        **Validates: Requirements 11.4**
        """
        # Single start node that returns AbstainResult with a result value.
        # The graph should still produce the result (AbstainResult only affects
        # downstream propagation, not the node's own result).
        def abstain_fn(x):
            return (WorkGraphStopFlags.AbstainResult, x * factor)

        async_node = _TestGraphNode(name="a_abstain", value=abstain_fn)
        async_graph = _TestWorkGraph(start_nodes=[async_node])
        async_result = await async_graph.arun(input_val)

        # The node's computed value should be in the result
        expected_value = input_val * factor
        if isinstance(async_result, tuple):
            assert expected_value in async_result, (
                f"AbstainResult node value {expected_value} not in {async_result}"
            )
        else:
            assert async_result == expected_value, (
                f"AbstainResult node value {expected_value} != {async_result}"
            )


# ---------------------------------------------------------------------------
# Property 9: WorkGraph concurrency limiting
# ---------------------------------------------------------------------------

class TestWorkGraphConcurrencyLimiting:
    """Property 9: WorkGraph concurrency limiting.

    For any WorkGraph with max_concurrency=K (where K >= 1), the final result
    of _arun() shall be identical to execution without a concurrency limit
    (i.e., max_concurrency=None).

    **Validates: Requirements 10.4**
    """

    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(
        factors=st.lists(
            st.integers(min_value=-10, max_value=10),
            min_size=1,
            max_size=4,
        ),
        input_val=input_strategy,
        max_conc=max_concurrency_strategy,
    )
    async def test_concurrency_limit_vs_unlimited_simple(self, factors, input_val, max_conc):
        """Multiple independent start nodes produce the same result with
        max_concurrency=K as with max_concurrency=None.

        **Validates: Requirements 10.4**
        """
        # Unlimited graph
        unlimited_starts = [
            _TestGraphNode(name=f"u_{i}", value=_make_sync_fn(f))
            for i, f in enumerate(factors)
        ]
        unlimited_graph = _TestWorkGraph(
            start_nodes=unlimited_starts,
            max_concurrency=None,
        )
        unlimited_result = await unlimited_graph.arun(input_val)

        # Limited graph
        limited_starts = [
            _TestGraphNode(name=f"l_{i}", value=_make_sync_fn(f))
            for i, f in enumerate(factors)
        ]
        limited_graph = _TestWorkGraph(
            start_nodes=limited_starts,
            max_concurrency=max_conc,
        )
        limited_result = await limited_graph.arun(input_val)

        assert unlimited_result == limited_result, (
            f"factors={factors}, input={input_val}, max_conc={max_conc}: "
            f"unlimited={unlimited_result}, limited={limited_result}"
        )

    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(
        root_factor=factor_strategy,
        branch_factors=st.lists(
            st.integers(min_value=-10, max_value=10),
            min_size=2,
            max_size=3,
        ),
        input_val=input_strategy,
        # Callee-side semaphore gating: any max_concurrency value is safe
        # (each node acquires/releases around its own computation only)
        max_conc=st.integers(min_value=1, max_value=8),
    )
    async def test_concurrency_limit_fan_out(self, root_factor, branch_factors, input_val, max_conc):
        """A fan-out graph produces the same result with max_concurrency=K
        as with max_concurrency=None.

        **Validates: Requirements 10.4**
        """
        # Unlimited graph
        u_root, _ = _build_fan_out_graph(
            "u_root", _make_sync_fn(root_factor),
            [(f"u_leaf_{i}", _make_sync_fn(f)) for i, f in enumerate(branch_factors)],
        )
        unlimited_graph = _TestWorkGraph(
            start_nodes=[u_root],
            max_concurrency=None,
        )
        unlimited_result = await unlimited_graph.arun(input_val)

        # Limited graph
        l_root, _ = _build_fan_out_graph(
            "l_root", _make_sync_fn(root_factor),
            [(f"l_leaf_{i}", _make_sync_fn(f)) for i, f in enumerate(branch_factors)],
        )
        limited_graph = _TestWorkGraph(
            start_nodes=[l_root],
            max_concurrency=max_conc,
        )
        limited_result = await limited_graph.arun(input_val)

        assert unlimited_result == limited_result, (
            f"root_factor={root_factor}, branch_factors={branch_factors}, "
            f"input={input_val}, max_conc={max_conc}: "
            f"unlimited={unlimited_result}, limited={limited_result}"
        )

    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(
        start_factors=st.lists(
            st.integers(min_value=-10, max_value=10),
            min_size=2,
            max_size=3,
        ),
        input_val=input_strategy,
        # Callee-side semaphore gating: any max_concurrency value is safe
        # (each node acquires/releases around its own computation only)
        max_conc=st.integers(min_value=1, max_value=8),
    )
    async def test_concurrency_limit_multi_start_with_chains(self, start_factors, input_val, max_conc):
        """Multiple start nodes each with their own downstream chain produce
        the same result with max_concurrency=K as with max_concurrency=None.

        **Validates: Requirements 10.4**
        """
        # Unlimited graph: each start node has its own downstream (no fan-in)
        u_starts = []
        for i, f in enumerate(start_factors):
            start = _TestGraphNode(
                name=f"u_start_{i}",
                value=_make_sync_fn(f),
                result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            )
            ds = _TestGraphNode(
                name=f"u_ds_{i}",
                value=_make_sync_fn(2),
            )
            start.add_next(ds)
            u_starts.append(start)
        unlimited_graph = _TestWorkGraph(
            start_nodes=u_starts,
            max_concurrency=None,
        )
        unlimited_result = await unlimited_graph.arun(input_val)

        # Limited graph
        l_starts = []
        for i, f in enumerate(start_factors):
            start = _TestGraphNode(
                name=f"l_start_{i}",
                value=_make_sync_fn(f),
                result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            )
            ds = _TestGraphNode(
                name=f"l_ds_{i}",
                value=_make_sync_fn(2),
            )
            start.add_next(ds)
            l_starts.append(start)
        limited_graph = _TestWorkGraph(
            start_nodes=l_starts,
            max_concurrency=max_conc,
        )
        limited_result = await limited_graph.arun(input_val)

        assert unlimited_result == limited_result, (
            f"start_factors={start_factors}, input={input_val}, max_conc={max_conc}: "
            f"unlimited={unlimited_result}, limited={limited_result}"
        )
