"""Tests for AsyncQueuedExecutor."""

import asyncio
import time

import pytest

from python_utils.mp_utils.async_queued_executor import AsyncQueuedExecutor
from python_utils.mp_utils.task import Task, TaskStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _async_sleep_task(duration: float, label: str = ""):
    await asyncio.sleep(duration)
    return f"done-{label}"


def _sync_task(x: int) -> int:
    return x * 2


async def _async_add(a: int, b: int) -> int:
    return a + b


async def _failing_task():
    raise ValueError("intentional failure")


# ---------------------------------------------------------------------------
# Basic execution
# ---------------------------------------------------------------------------

class TestBasicExecution:
    @pytest.mark.asyncio
    async def test_single_async_task(self):
        executor = AsyncQueuedExecutor(group_max_concurrency={"A": 1})
        await executor.async_submit(Task(callable=_async_add, args=(2, 3), group="A"))
        results = await executor.arun()
        assert len(results) == 1
        assert results[0].result == 5
        assert results[0].status == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_sync_task(self):
        executor = AsyncQueuedExecutor(group_max_concurrency={"A": 1})
        await executor.async_submit(Task(callable=_sync_task, args=(7,), group="A"))
        results = await executor.arun()
        assert len(results) == 1
        assert results[0].result == 14

    @pytest.mark.asyncio
    async def test_multiple_tasks_same_group(self):
        executor = AsyncQueuedExecutor(group_max_concurrency={"A": 2})
        for i in range(5):
            await executor.async_submit(
                Task(callable=_async_add, args=(i, 1), group="A")
            )
        results = await executor.arun()
        assert len(results) == 5
        result_values = sorted(r.result for r in results)
        assert result_values == [1, 2, 3, 4, 5]

    @pytest.mark.asyncio
    async def test_empty_submission(self):
        executor = AsyncQueuedExecutor(group_max_concurrency={"A": 1})
        results = await executor.arun()
        assert results == []


# ---------------------------------------------------------------------------
# Concurrency limits
# ---------------------------------------------------------------------------

class TestConcurrencyLimits:
    @pytest.mark.asyncio
    async def test_single_group_limit_2(self):
        """With limit=2, at most 2 tasks run concurrently."""
        timestamps = []

        async def _record_task(idx):
            timestamps.append(("start", idx, time.monotonic()))
            await asyncio.sleep(0.1)
            timestamps.append(("end", idx, time.monotonic()))
            return idx

        executor = AsyncQueuedExecutor(group_max_concurrency={"A": 2})
        for i in range(4):
            await executor.async_submit(Task(callable=_record_task, args=(i,), group="A"))
        results = await executor.arun()

        assert len(results) == 4
        # Check max concurrent: at any point, no more than 2 active
        active = 0
        max_active = 0
        events = sorted(timestamps, key=lambda x: x[2])
        for event_type, idx, ts in events:
            if event_type == "start":
                active += 1
            else:
                active -= 1
            max_active = max(max_active, active)
        assert max_active <= 2, f"Max concurrent was {max_active}, expected <= 2"

    @pytest.mark.asyncio
    async def test_multi_group_different_limits(self):
        """Groups A (limit=3) and B (limit=1) enforce independently."""
        active_a = [0]
        max_a = [0]
        active_b = [0]
        max_b = [0]

        async def _task_a(idx):
            active_a[0] += 1
            max_a[0] = max(max_a[0], active_a[0])
            await asyncio.sleep(0.05)
            active_a[0] -= 1
            return f"A-{idx}"

        async def _task_b(idx):
            active_b[0] += 1
            max_b[0] = max(max_b[0], active_b[0])
            await asyncio.sleep(0.05)
            active_b[0] -= 1
            return f"B-{idx}"

        executor = AsyncQueuedExecutor(group_max_concurrency={"A": 3, "B": 1})
        for i in range(6):
            await executor.async_submit(Task(callable=_task_a, args=(i,), group="A"))
        for i in range(3):
            await executor.async_submit(Task(callable=_task_b, args=(i,), group="B"))

        results = await executor.arun()
        assert len(results) == 9
        assert max_a[0] <= 3, f"Group A max concurrent: {max_a[0]}"
        assert max_b[0] <= 1, f"Group B max concurrent: {max_b[0]}"

    @pytest.mark.asyncio
    async def test_limit_1_serializes(self):
        """With limit=1, tasks run sequentially."""
        order = []

        async def _ordered_task(idx):
            order.append(idx)
            await asyncio.sleep(0.01)
            return idx

        executor = AsyncQueuedExecutor(group_max_concurrency={"A": 1})
        for i in range(5):
            await executor.async_submit(Task(callable=_ordered_task, args=(i,), group="A"))
        await executor.arun()
        assert order == [0, 1, 2, 3, 4]


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_failed_task_recorded(self):
        executor = AsyncQueuedExecutor(group_max_concurrency={"A": 1})
        await executor.async_submit(Task(callable=_failing_task, group="A"))
        results = await executor.arun()
        assert len(results) == 1
        assert results[0].status == TaskStatus.FAILED
        assert isinstance(results[0].exception, ValueError)

    @pytest.mark.asyncio
    async def test_failure_doesnt_stop_others(self):
        executor = AsyncQueuedExecutor(group_max_concurrency={"A": 2})
        await executor.async_submit(Task(callable=_async_add, args=(1, 1), group="A"))
        await executor.async_submit(Task(callable=_failing_task, group="A"))
        await executor.async_submit(Task(callable=_async_add, args=(2, 2), group="A"))
        results = await executor.arun()
        assert len(results) == 3
        completed = [r for r in results if r.status == TaskStatus.COMPLETED]
        failed = [r for r in results if r.status == TaskStatus.FAILED]
        assert len(completed) == 2
        assert len(failed) == 1

    @pytest.mark.asyncio
    async def test_failure_in_one_group_doesnt_stop_other(self):
        executor = AsyncQueuedExecutor(group_max_concurrency={"A": 1, "B": 1})
        await executor.async_submit(Task(callable=_failing_task, group="A"))
        await executor.async_submit(Task(callable=_async_add, args=(3, 4), group="B"))
        results = await executor.arun()
        assert len(results) == 2
        b_result = [r for r in results if r.status == TaskStatus.COMPLETED]
        assert len(b_result) == 1
        assert b_result[0].result == 7


# ---------------------------------------------------------------------------
# Result metadata
# ---------------------------------------------------------------------------

class TestResultMetadata:
    @pytest.mark.asyncio
    async def test_timing_recorded(self):
        executor = AsyncQueuedExecutor(group_max_concurrency={"A": 1})
        await executor.async_submit(
            Task(callable=_async_sleep_task, args=(0.05, "x"), group="A")
        )
        results = await executor.arun()
        assert results[0].start_time > 0
        assert results[0].end_time >= results[0].start_time
        assert results[0].execution_time >= 0.04

    @pytest.mark.asyncio
    async def test_task_id_preserved(self):
        executor = AsyncQueuedExecutor(group_max_concurrency={"A": 1})
        await executor.async_submit(
            Task(callable=_sync_task, args=(5,), group="A", task_id="my-id-123")
        )
        results = await executor.arun()
        assert results[0].task_id == "my-id-123"


# ---------------------------------------------------------------------------
# Fresh instances
# ---------------------------------------------------------------------------

class TestFreshInstances:
    @pytest.mark.asyncio
    async def test_multiple_arun_calls(self):
        """Each arun() should produce independent results."""
        executor = AsyncQueuedExecutor(group_max_concurrency={"A": 1})
        await executor.async_submit(Task(callable=_sync_task, args=(1,), group="A"))
        r1 = await executor.arun()
        assert len(r1) == 1

        await executor.async_submit(Task(callable=_sync_task, args=(2,), group="A"))
        r2 = await executor.arun()
        assert len(r2) == 1
        assert r2[0].result == 4


# ---------------------------------------------------------------------------
# Ungrouped tasks
# ---------------------------------------------------------------------------

class TestUngroupedTasks:
    @pytest.mark.asyncio
    async def test_ungrouped_with_default_concurrency(self):
        executor = AsyncQueuedExecutor(default_concurrency=2)
        for i in range(4):
            await executor.async_submit(Task(callable=_sync_task, args=(i,)))
        results = await executor.arun()
        assert len(results) == 4

    @pytest.mark.asyncio
    async def test_mixed_grouped_and_ungrouped(self):
        executor = AsyncQueuedExecutor(
            group_max_concurrency={"A": 1},
            default_concurrency=1,
        )
        await executor.async_submit(Task(callable=_async_add, args=(1, 1), group="A"))
        await executor.async_submit(Task(callable=_sync_task, args=(5,)))
        results = await executor.arun()
        assert len(results) == 2
