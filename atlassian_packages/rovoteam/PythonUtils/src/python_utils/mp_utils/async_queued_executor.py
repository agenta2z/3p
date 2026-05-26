"""Async-native queued executor with per-group concurrency limiting.

Provides ``AsyncQueuedExecutorBase`` (abstract) and ``AsyncQueuedExecutor``
(concrete, asyncio.Queue-backed). Concurrency is enforced structurally:
N consumers per group = N max concurrent tasks in that group.

Usage::

    executor = AsyncQueuedExecutor(
        group_max_concurrency={"research": 3, "investigation": 2},
    )
    await executor.async_submit(Task(callable=coro_fn, args=(...,), group="research"))
    results = await executor.arun()
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Hashable, List, Optional

from python_utils.mp_utils.task import Task, TaskState, TaskStatus

_logger = logging.getLogger(__name__)


class AsyncQueuedExecutorBase(ABC):
    """Abstract base for async queued executors with per-group concurrency.

    Subclasses provide the queue backend (``_create_queue``, ``_get_from_queue``,
    ``_put_to_queue``) and task execution (``_execute_task``).  The base class
    handles group routing, consumer lifecycle, sentinel-based shutdown, and
    result collection.

    Args:
        group_max_concurrency: Dict mapping group name to max concurrent tasks.
        default_concurrency: Max concurrent tasks for ungrouped (group=None) tasks.
        name: Executor name for logging.
    """

    def __init__(
        self,
        group_max_concurrency: Optional[Dict[Hashable, int]] = None,
        default_concurrency: Optional[int] = None,
        name: str = "AsyncQueuedExecutor",
    ):
        self.group_max_concurrency = group_max_concurrency or {}
        self.default_concurrency = default_concurrency
        self.name = name
        self._queues: Dict[Hashable, Any] = {}
        self._results: List[TaskState] = []
        self._tasks_submitted = 0

    # ------------------------------------------------------------------
    # Abstract methods — subclasses provide the queue + execution backend
    # ------------------------------------------------------------------

    @abstractmethod
    def _create_queue(self) -> Any:
        """Create and return a new queue instance for a group."""

    @abstractmethod
    async def _put_to_queue(self, queue: Any, item: Any) -> None:
        """Put an item (Task or None sentinel) into the queue."""

    @abstractmethod
    async def _get_from_queue(self, queue: Any) -> Any:
        """Get the next item from the queue. Awaits until available."""

    @abstractmethod
    async def _execute_task(self, worker_name: str, task: Task) -> TaskState:
        """Execute a single task and return a TaskState result."""

    @abstractmethod
    def _mark_queue_done(self, queue: Any) -> None:
        """Signal that a dequeued item has been fully processed."""

    # ------------------------------------------------------------------
    # Concrete methods — orchestration
    # ------------------------------------------------------------------

    async def async_submit(self, task: Task) -> str:
        """Submit a task to the appropriate group queue."""
        group = task.group
        if group not in self._queues:
            self._queues[group] = self._create_queue()
        await self._put_to_queue(self._queues[group], task)
        self._tasks_submitted += 1
        return task.task_id

    def _resolve_limit(self, group: Hashable, queue_size: int) -> int:
        """Resolve the concurrency limit for a group."""
        limit = self.group_max_concurrency.get(group)
        if limit is None and group is not None:
            limit = self.group_max_concurrency.get(None, self.default_concurrency)
        if limit is None:
            limit = max(queue_size, 1)
        return max(limit, 1)

    async def arun(self) -> List[TaskState]:
        """Run all submitted tasks to completion.

        Spawns consumer tasks per group, sends sentinels, gathers results.
        """
        self._results = []
        workers = []

        for group, queue in self._queues.items():
            limit = self._resolve_limit(group, self._queue_size(queue))
            for i in range(limit):
                worker = asyncio.create_task(
                    self._consumer_loop(f"{self.name}-{group}-{i}", group)
                )
                workers.append(worker)
            for _ in range(limit):
                await self._put_to_queue(queue, None)

        await asyncio.gather(*workers, return_exceptions=True)
        return list(self._results)

    async def _consumer_loop(self, worker_name: str, group: Hashable):
        """Consumer loop: pulls from group queue, executes tasks."""
        queue = self._queues[group]
        while True:
            task = await self._get_from_queue(queue)
            if task is None:
                self._mark_queue_done(queue)
                return
            try:
                state = await self._execute_task(worker_name, task)
            except asyncio.CancelledError:
                state = TaskState(
                    task_id=task.task_id,
                    status=TaskStatus.FAILED,
                    exception=asyncio.CancelledError(),
                )
                raise
            finally:
                self._results.append(state)
                self._mark_queue_done(queue)

    def _queue_size(self, queue: Any) -> int:
        """Return current queue size. Override if queue type differs."""
        if hasattr(queue, "qsize"):
            return queue.qsize()
        return 0


class AsyncQueuedExecutor(AsyncQueuedExecutorBase):
    """Concrete async executor backed by ``asyncio.Queue``.

    Each group gets its own ``asyncio.Queue`` with a fixed number of
    consumer ``asyncio.Task`` objects.  Supports both sync and async
    callables — sync callables run directly in the event loop (suitable
    for fast, non-blocking work; use ``loop.run_in_executor`` for
    CPU-heavy sync work).

    Usage::

        executor = AsyncQueuedExecutor(
            group_max_concurrency={"research": 3, "investigation": 2},
        )
        await executor.async_submit(Task(callable=my_coro, args=(x,), group="research"))
        results = await executor.arun()
    """

    def _create_queue(self) -> asyncio.Queue:
        return asyncio.Queue()

    async def _put_to_queue(self, queue: asyncio.Queue, item: Any) -> None:
        await queue.put(item)

    async def _get_from_queue(self, queue: asyncio.Queue) -> Any:
        return await queue.get()

    def _mark_queue_done(self, queue: asyncio.Queue) -> None:
        queue.task_done()

    async def _execute_task(self, worker_name: str, task: Task) -> TaskState:
        """Execute task, handling both sync and async callables."""
        start_time = time.time()
        try:
            if asyncio.iscoroutinefunction(task._callable):
                result = await task._callable(*task.args, **task.kwargs)
            else:
                result = task._callable(*task.args, **task.kwargs)
            return TaskState(
                task_id=task.task_id,
                result=result,
                status=TaskStatus.COMPLETED,
                worker_id=0,
                input_args=task.args,
                input_kwargs=task.kwargs,
                start_time=start_time,
                end_time=time.time(),
                execution_time=time.time() - start_time,
            )
        except asyncio.CancelledError:
            raise
        except Exception as e:
            _logger.warning("%s: task %s failed: %s", worker_name, task.task_id, e)
            return TaskState(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                exception=e,
                start_time=start_time,
                end_time=time.time(),
                execution_time=time.time() - start_time,
            )
