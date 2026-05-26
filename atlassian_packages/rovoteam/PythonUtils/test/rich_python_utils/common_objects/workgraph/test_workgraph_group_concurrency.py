"""
Unit tests for WorkGraph per-group concurrency limiting.

Tests cover:
- WorkGraphNode.group attribute
- WorkGraph.group_max_concurrency creating per-group semaphores
- Per-group concurrency limiting
- Mixed grouped and ungrouped nodes
- Backward compatibility
"""
import asyncio

import pytest

from python_utils.common_objects.workflow.workgraph import WorkGraphNode, WorkGraph
from python_utils.common_objects.workflow.common.result_pass_down_mode import ResultPassDownMode


class TestWorkGraphNodeGroup:
    """WorkGraphNode.group attribute."""

    def test_default_group_is_none(self):
        node = WorkGraphNode(name="n", value=lambda: 1)
        assert node.group is None

    def test_group_can_be_set(self):
        node = WorkGraphNode(name="n", value=lambda: 1, group="research")
        assert node.group == "research"

    def test_different_groups(self):
        n1 = WorkGraphNode(name="n1", value=lambda: 1, group="research")
        n2 = WorkGraphNode(name="n2", value=lambda: 1, group="investigation")
        assert n1.group != n2.group


class TestWorkGraphGroupMaxConcurrency:
    """WorkGraph.group_max_concurrency attribute."""

    def test_default_is_none(self):
        n = WorkGraphNode(name="n", value=lambda: 1)
        g = WorkGraph(start_nodes=[n])
        assert g.group_max_concurrency is None

    def test_can_be_set(self):
        n = WorkGraphNode(name="n", value=lambda: 1)
        g = WorkGraph(start_nodes=[n], group_max_concurrency={"research": 3})
        assert g.group_max_concurrency == {"research": 3}


class TestPerGroupConcurrency:
    """Verify per-group semaphores limit concurrency correctly."""

    @pytest.mark.asyncio
    async def test_group_limited_to_1_runs_sequentially(self):
        """With group max_concurrency=1, only 1 node runs at a time."""
        max_concurrent = 0
        current_concurrent = 0
        lock = asyncio.Lock()

        async def tracked_task():
            nonlocal max_concurrent, current_concurrent
            async with lock:
                current_concurrent += 1
                if current_concurrent > max_concurrent:
                    max_concurrent = current_concurrent
            await asyncio.sleep(0.03)
            async with lock:
                current_concurrent -= 1
            return "done"

        nodes = [
            WorkGraphNode(name=f"n{i}", value=tracked_task, group="limited")
            for i in range(4)
        ]
        g = WorkGraph(start_nodes=nodes, group_max_concurrency={"limited": 1})
        await g.arun()
        assert max_concurrent == 1, f"Expected max 1 concurrent, got {max_concurrent}"

    @pytest.mark.asyncio
    async def test_group_max_3_allows_parallel(self):
        """With group max_concurrency=3, up to 3 nodes run concurrently."""
        max_concurrent = 0
        current_concurrent = 0
        lock = asyncio.Lock()

        async def tracked_task():
            nonlocal max_concurrent, current_concurrent
            async with lock:
                current_concurrent += 1
                if current_concurrent > max_concurrent:
                    max_concurrent = current_concurrent
            await asyncio.sleep(0.03)
            async with lock:
                current_concurrent -= 1
            return "done"

        nodes = [
            WorkGraphNode(name=f"n{i}", value=tracked_task, group="parallel")
            for i in range(6)
        ]
        g = WorkGraph(start_nodes=nodes, group_max_concurrency={"parallel": 3})
        await g.arun()
        assert max_concurrent <= 3, f"Expected max 3 concurrent, got {max_concurrent}"
        assert max_concurrent > 1, f"Expected >1 concurrent with 6 nodes, got {max_concurrent}"

    @pytest.mark.asyncio
    async def test_different_groups_independent(self):
        """Two groups with different limits operate independently."""
        group_a_max = 0
        group_b_max = 0
        group_a_current = 0
        group_b_current = 0
        lock = asyncio.Lock()

        async def tracked_a():
            nonlocal group_a_max, group_a_current
            async with lock:
                group_a_current += 1
                if group_a_current > group_a_max:
                    group_a_max = group_a_current
            await asyncio.sleep(0.03)
            async with lock:
                group_a_current -= 1
            return "a"

        async def tracked_b():
            nonlocal group_b_max, group_b_current
            async with lock:
                group_b_current += 1
                if group_b_current > group_b_max:
                    group_b_max = group_b_current
            await asyncio.sleep(0.03)
            async with lock:
                group_b_current -= 1
            return "b"

        slow_nodes = [WorkGraphNode(name=f"s{i}", value=tracked_a, group="slow") for i in range(3)]
        fast_nodes = [WorkGraphNode(name=f"f{i}", value=tracked_b, group="fast") for i in range(4)]

        g = WorkGraph(
            start_nodes=slow_nodes + fast_nodes,
            group_max_concurrency={"slow": 1, "fast": 4},
        )
        await g.arun()
        assert group_a_max == 1, f"Group 'slow' (limit=1): expected max 1, got {group_a_max}"
        assert group_b_max > 1, f"Group 'fast' (limit=4): expected >1, got {group_b_max}"

    @pytest.mark.asyncio
    async def test_ungrouped_nodes_use_global_semaphore_with_groups(self):
        """Ungrouped nodes (group=None) use global max_concurrency when groups exist."""
        ungrouped_max = 0
        ungrouped_current = 0
        lock = asyncio.Lock()

        async def tracked_task():
            nonlocal ungrouped_max, ungrouped_current
            async with lock:
                ungrouped_current += 1
                if ungrouped_current > ungrouped_max:
                    ungrouped_max = ungrouped_current
            await asyncio.sleep(0.03)
            async with lock:
                ungrouped_current -= 1
            return "done"

        ungrouped = [WorkGraphNode(name=f"u{i}", value=tracked_task) for i in range(3)]
        g = WorkGraph(
            start_nodes=ungrouped,
            max_concurrency=1,
            group_max_concurrency={"grouped": 5},
        )
        await g.arun()
        assert ungrouped_max == 1, f"Ungrouped (global limit=1): expected 1, got {ungrouped_max}"


class TestBackwardCompatibility:
    """Existing behavior unchanged when group features not used."""

    @pytest.mark.asyncio
    async def test_no_groups_uses_global_max_concurrency(self):
        """Without group_max_concurrency, global max_concurrency applies to all."""
        max_concurrent = 0
        current_concurrent = 0
        lock = asyncio.Lock()

        async def tracked_task():
            nonlocal max_concurrent, current_concurrent
            async with lock:
                current_concurrent += 1
                if current_concurrent > max_concurrent:
                    max_concurrent = current_concurrent
            await asyncio.sleep(0.03)
            async with lock:
                current_concurrent -= 1
            return "done"

        nodes = [WorkGraphNode(name=f"n{i}", value=tracked_task) for i in range(5)]
        g = WorkGraph(start_nodes=nodes, max_concurrency=2)
        await g.arun()
        assert max_concurrent <= 2, f"Expected max 2, got {max_concurrent}"

    def test_sync_execution_unaffected(self):
        """Sync _run() ignores semaphores — groups don't affect sync execution."""
        results = []

        n1 = WorkGraphNode(name="n1", value=lambda: results.append("n1") or "n1", group="a")
        n2 = WorkGraphNode(name="n2", value=lambda: results.append("n2") or "n2", group="a")
        g = WorkGraph(start_nodes=[n1, n2], group_max_concurrency={"a": 1})
        g.run()
        assert set(results) == {"n1", "n2"}
