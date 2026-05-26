"""
Queued Executor Module

Provides queue-based parallel execution with customizable backends.

This module contains:
- QueuedExecutorBase: Abstract base class for queue-based executors
- SingleThreadExecutor: Single-threaded executor (runs in one thread)
- SimulatedMultiThreadExecutor: Single-threaded with manual task processing
- QueuedThreadPoolExecutor: Multi-threaded executor (multiple threads)
- QueuedProcessPoolExecutor: Multi-process executor (multiple processes)

All executors use QueueServiceBase for task input/output, allowing
customizable queue backends (in-memory, Redis, file-based, etc.).

Usage:
    from python_utils.mp_utils.queued_executor import (
        SingleThreadExecutor,
        QueuedThreadPoolExecutor,
        QueuedProcessPoolExecutor,
    )
    from python_utils.mp_utils.task import Task

Example:
    >>> executor = QueuedThreadPoolExecutor(
    ...     input_queue_service=queue_service,
    ...     output_queue_service=queue_service,
    ...     input_queue_id='tasks',
    ...     output_queue_id='results',
    ...     num_workers=4
    ... )
    >>> flag = executor.start()
    >>> executor.submit(Task(callable=lambda: 42))
    >>> result = executor.get_result()
    >>> executor.stop(flag)
"""

from abc import ABC, abstractmethod
from multiprocessing import Process, get_context
from multiprocessing.context import BaseContext
from threading import Thread
from time import time, sleep
from typing import Any, Callable, List, Optional, Union

from attr import attrs, attrib

from python_utils.console_utils import hprint_message
from python_utils.mp_utils.task import Task, TaskState, TaskStatus
from python_utils.service_utils.queue_service.queue_service_base import QueueServiceBase


@attrs(slots=False)  # slots=False required for ABC
class QueuedExecutorBase(ABC):
    """
    Abstract base class for queue-based task executors.

    Pulls tasks from an input queue, executes them via workers,
    and pushes results to an output queue. Uses the Template Method
    pattern - subclasses provide backend-specific worker management.

    Attributes:
        input_queue_service: Queue service for receiving tasks.
        output_queue_service: Queue service for storing results.
        input_queue_id: Identifier for the input queue.
        output_queue_id: Identifier for the output queue.
        num_workers: Number of worker threads/processes.
        name: Name for this executor instance, used in logging.
        poll_interval: Time in seconds to wait between queue polls.
        verbose: If True, prints status messages during execution.

    Examples:
        Subclasses implement the abstract methods to provide
        backend-specific worker creation and management:

        >>> class MyExecutor(QueuedExecutorBase):
        ...     def _create_worker(self, worker_id, active_flag):
        ...         return Thread(target=self._worker_loop, args=(worker_id, active_flag))
        ...     def _start_worker(self, worker):
        ...         worker.start()
        ...     def _join_worker(self, worker, timeout):
        ...         worker.join(timeout=timeout)
        ...     def _is_worker_alive(self, worker):
        ...         return worker.is_alive()
    """

    # Queue configuration
    input_queue_service = attrib(type=QueueServiceBase)
    output_queue_service = attrib(type=QueueServiceBase)
    input_queue_id = attrib(type=str)
    output_queue_id = attrib(type=str)

    # Executor configuration
    num_workers = attrib(type=int, default=1)
    name = attrib(type=str, default='QueuedExecutor')
    poll_interval = attrib(type=float, default=0.1)
    verbose = attrib(type=bool, default=__debug__)

    # Internal state (not constructor parameters)
    _is_running = attrib(type=bool, default=False, init=False)
    _processed_count = attrib(type=int, default=0, init=False)
    _workers = attrib(type=list, factory=list, init=False)
    _active_flag = attrib(type=Optional[list], default=None, init=False)

    def __attrs_post_init__(self):
        """Validate parameters after initialization."""
        self._validate_parameters()
        self._ensure_queues_exist()

    def _validate_parameters(self):
        """Validate constructor parameters."""
        if self.poll_interval <= 0:
            raise ValueError(
                f"poll_interval must be positive; got {self.poll_interval}"
            )
        if not self.input_queue_id:
            raise ValueError("input_queue_id cannot be empty")
        if not self.output_queue_id:
            raise ValueError("output_queue_id cannot be empty")
        if self.num_workers < 1:
            raise ValueError(
                f"num_workers must be at least 1; got {self.num_workers}"
            )

    def _ensure_queues_exist(self):
        """Create input and output queues if they don't exist."""
        if not self.input_queue_service.exists(self.input_queue_id):
            self.input_queue_service.create_queue(self.input_queue_id)
        if not self.output_queue_service.exists(self.output_queue_id):
            self.output_queue_service.create_queue(self.output_queue_id)

    # === Abstract methods (backend-specific) ===

    @abstractmethod
    def _create_worker(self, worker_id: int, active_flag: list) -> Any:
        """
        Create a worker (Thread or Process).

        Args:
            worker_id: Unique identifier for this worker.
            active_flag: Mutable list [True/False] for stop signaling.

        Returns:
            The worker object (Thread, Process, etc.).
        """
        pass

    @abstractmethod
    def _start_worker(self, worker: Any) -> None:
        """
        Start the worker.

        Args:
            worker: The worker object to start.
        """
        pass

    @abstractmethod
    def _join_worker(self, worker: Any, timeout: float) -> None:
        """
        Wait for worker to finish.

        Args:
            worker: The worker object to wait for.
            timeout: Maximum time to wait in seconds.
        """
        pass

    @abstractmethod
    def _is_worker_alive(self, worker: Any) -> bool:
        """
        Check if worker is still running.

        Args:
            worker: The worker object to check.

        Returns:
            True if worker is alive, False otherwise.
        """
        pass

    # === Concrete template methods ===

    def _worker_loop(self, worker_id: int, active_flag: list):
        """
        The main worker loop - common pattern for all backends.

        Continuously pulls tasks from input queue, executes them,
        and pushes results to output queue until active_flag is False.

        Args:
            worker_id: Unique identifier for this worker.
            active_flag: Mutable list [True/False] for stop signaling.
        """
        no_task_count = 0

        if self.verbose:
            hprint_message('worker started', f'{self.name}-{worker_id}')

        try:
            while active_flag[0]:
                task = self.input_queue_service.get(
                    self.input_queue_id,
                    blocking=False
                )

                if task is None:
                    no_task_count += 1
                    if self.verbose and no_task_count % 100 == 0:
                        hprint_message(
                            'worker waiting', f'{self.name}-{worker_id}',
                            'poll_interval', self.poll_interval
                        )
                    sleep(self.poll_interval)
                    continue

                no_task_count = 0

                if not isinstance(task, Task):
                    if self.verbose:
                        hprint_message(
                            'invalid task type', type(task).__name__,
                            'worker', f'{self.name}-{worker_id}'
                        )
                    continue

                result = self._execute_task(worker_id, task)
                self.output_queue_service.put(self.output_queue_id, result)

        finally:
            if self.verbose:
                hprint_message('worker stopped', f'{self.name}-{worker_id}')

    def _execute_task(self, worker_id: int, task: Task) -> TaskState:
        """
        Execute a task and return result with timing.

        Args:
            worker_id: ID of the worker executing the task.
            task: The Task to execute.

        Returns:
            TaskResult with execution details.
        """
        start_time = time()

        if self.verbose:
            hprint_message(
                'executing', task.name,
                'task_id', task.task_id,
                'worker', worker_id
            )

        try:
            result_value = task.execute()
            end_time = time()

            return TaskState(
                task_id=task.task_id,
                result=result_value,
                status=TaskStatus.COMPLETED,
                input_args=task.args,
                input_kwargs=task.kwargs,
                worker_id=worker_id,
                start_time=start_time,
                end_time=end_time,
                execution_time=end_time - start_time
            )
        except Exception as e:
            end_time = time()

            if self.verbose:
                hprint_message(
                    'task failed', task.task_id,
                    'worker', worker_id,
                    'error', str(e)
                )

            return TaskState(
                task_id=task.task_id,
                result=None,
                status=TaskStatus.FAILED,
                exception=e,
                input_args=task.args,
                input_kwargs=task.kwargs,
                worker_id=worker_id,
                start_time=start_time,
                end_time=end_time,
                execution_time=end_time - start_time
            )

    def run(self, active_flag: Optional[list] = None, blocking: bool = True) -> list:
        """
        Run the executor.

        Args:
            active_flag: Optional mutable list [True] for stop signaling.
                If None, a new flag is created.
            blocking: If True, blocks the current thread until stopped.
                If False, spawns background workers and returns immediately.

        Returns:
            The active_flag list. Set active_flag[0] = False to stop workers.

        Examples:
            Blocking mode (runs in current thread):

            >>> flag = [True]
            >>> executor.run(flag, blocking=True)  # Blocks until flag[0] = False

            Non-blocking mode (spawns background workers):

            >>> flag = executor.run(blocking=False)
            >>> # ... do other work ...
            >>> executor.stop(flag)
        """
        if active_flag is None:
            active_flag = [True]

        self._active_flag = active_flag
        self._is_running = True

        if blocking:
            # Run directly in current thread (single worker)
            if self.verbose:
                hprint_message(
                    'running executor (blocking)', self.name,
                    'num_workers', 1
                )
            try:
                self._worker_loop(0, active_flag)
            finally:
                self._is_running = False
        else:
            # Spawn background workers
            self._workers = []

            if self.verbose:
                hprint_message(
                    'running executor (non-blocking)', self.name,
                    'num_workers', self.num_workers
                )

            for i in range(self.num_workers):
                worker = self._create_worker(i, active_flag)
                self._start_worker(worker)
                self._workers.append(worker)
                sleep(0.01)  # Small delay between worker starts

        return active_flag

    def start(self, active_flag: Optional[list] = None) -> list:
        """
        Start workers in background (non-blocking).

        This is an alias for run(blocking=False).

        Args:
            active_flag: Optional mutable list [True] for stop signaling.

        Returns:
            The active_flag list.
        """
        return self.run(active_flag=active_flag, blocking=False)

    def stop(self, active_flag: Optional[list] = None, timeout: float = 5.0) -> bool:
        """
        Stop all workers gracefully.

        Args:
            active_flag: The flag returned by start(). If None, uses internal flag.
            timeout: Maximum time to wait for each worker to stop.

        Returns:
            True if all workers stopped successfully, False if timeout.
        """
        flag = active_flag if active_flag is not None else self._active_flag

        if flag is not None:
            flag[0] = False

        if self.verbose:
            hprint_message('stopping executor', self.name)

        for worker in self._workers:
            self._join_worker(worker, timeout)

        self._is_running = False
        all_stopped = all(not self._is_worker_alive(w) for w in self._workers)

        if self.verbose:
            hprint_message(
                'executor stopped', self.name,
                'all_workers_stopped', all_stopped
            )

        return all_stopped

    def submit(self, task: Task) -> str:
        """
        Submit a task to the input queue.

        Args:
            task: The Task to submit.

        Returns:
            The task_id of the submitted task.
        """
        self.input_queue_service.put(self.input_queue_id, task)
        return task.task_id

    def get_result(
            self,
            blocking: bool = True,
            timeout: Optional[float] = None
    ) -> Optional[TaskState]:
        """
        Get a result from the output queue.

        Args:
            blocking: If True, block until a result is available.
            timeout: Maximum time to wait (seconds). None = wait forever.

        Returns:
            TaskResult if available, None if queue is empty (non-blocking)
            or timeout reached.
        """
        return self.output_queue_service.get(
            self.output_queue_id,
            blocking=blocking,
            timeout=timeout
        )

    def get_stats(self) -> dict:
        """
        Get statistics about the executor.

        Returns:
            Dictionary with executor statistics.
        """
        return {
            'name': self.name,
            'num_workers': self.num_workers,
            'is_running': self._is_running,
            'input_queue_size': self.input_queue_service.size(self.input_queue_id),
            'output_queue_size': self.output_queue_service.size(self.output_queue_id),
            'workers_alive': sum(1 for w in self._workers if self._is_worker_alive(w)),
        }

    @property
    def is_running(self) -> bool:
        """Check if the executor is currently running."""
        return self._is_running

    def __repr__(self) -> str:
        """String representation of the executor."""
        return (
            f"{self.__class__.__name__}(name={self.name!r}, "
            f"num_workers={self.num_workers}, "
            f"input_queue={self.input_queue_id!r}, "
            f"output_queue={self.output_queue_id!r})"
        )

    def run_async(
        self,
        tasks: List[Task],
        router: Optional[Callable[[str, Any, TaskState], List[Task]]] = None,
        depth_first: bool = True,
        on_error: str = 'raise',
        on_task_complete: Optional[Callable[[str, Any], None]] = None,
        max_concurrent: Optional[int] = None
    ) -> Any:
        """
        Run tasks asynchronously with dynamic task generation.

        This method executes tasks and dynamically generates follow-up tasks based on
        task results. It supports two modes of operation:

        1. **Wrapper Mode** (router=None):
           - Tasks return ``(result, next_tasks)`` tuple
           - Works for thread-based executors where closures are allowed
           - NOT suitable for multi-processing (closures not picklable)

        2. **Router Mode** (router=Callable):
           - Tasks return just ``result``
           - Router callback decides which tasks to run next
           - Router receives TaskState with ``input_args``/``input_kwargs`` for NoPassDown self-edges
           - Works for both threads AND multi-processing
           - Router runs in MAIN PROCESS (never crosses process boundary)

        Args:
            tasks: Initial list of tasks to execute.
            router: Optional callback with signature ``(task_id, result, task_state) -> List[Task]``.
                If provided, tasks return just result and router decides next_tasks.
                The ``task_state`` contains ``input_args``/``input_kwargs`` for NoPassDown self-edges.
                If None, tasks must return ``(result, next_tasks)`` tuple.
            depth_first: If True, insert next_tasks at HEAD of pending queue (depth-first).
                If False, append to TAIL (breadth-first). Default: True.
            on_error: Error handling strategy:
                - ``'raise'``: Stop execution and re-raise the exception (default)
                - ``'skip'``: Log the error and continue with remaining tasks
            on_task_complete: Optional callback called after each task completes.
                Signature: ``(task_id, result) -> None``
            max_concurrent: Maximum number of tasks in-flight simultaneously.
                If None, defaults to ``num_workers``.

        Returns:
            Single result if only one leaf task (no next_tasks), otherwise a tuple
            of all leaf results.

        Raises:
            RuntimeError: If a task fails and ``on_error='raise'``.
            ValueError: If ``on_error`` is not 'raise' or 'skip'.

        Examples:
            **Wrapper Mode** (tasks return (result, next_tasks)):

            >>> def task_a():
            ...     return ("result_a", [Task(callable=task_b, task_id="B")])
            >>> def task_b():
            ...     return ("result_b", [])  # Leaf task
            >>> executor.run_async([Task(callable=task_a, task_id="A")])
            'result_b'

            **Router Mode** (router decides next tasks):

            >>> def my_router(task_id, result, task_state):
            ...     if task_id == "A":
            ...         return [Task(callable=task_b, task_id="B")]
            ...     return []  # Leaf task
            >>> executor.run_async([Task(callable=task_a, task_id="A")], router=my_router)
            'result_b'

            **Depth-First vs Breadth-First**:

            >>> # depth_first=True (default): A -> B -> C (B's children before A's siblings)
            >>> # depth_first=False: A -> A's siblings -> B -> B's siblings -> C

        Note:
            For ``QueuedProcessPoolExecutor``, you MUST use router mode because
            wrapper closures cannot be pickled for cross-process communication.
        """
        from collections import deque

        if on_error not in ('raise', 'skip'):
            raise ValueError(f"on_error must be 'raise' or 'skip', got {on_error!r}")

        pending = deque(tasks)
        in_flight = {}  # task_id -> Task
        leaf_results = []

        # Ensure workers are running for thread/process-based executors
        workers_started = False
        if not self._workers and hasattr(self, 'start'):
            self.start()
            workers_started = True

        # Default max_concurrent to num_workers
        if max_concurrent is None:
            max_concurrent = getattr(self, 'num_workers', 1)

        try:
            while pending or in_flight:
                # === SUBMIT PHASE ===
                # Submit tasks up to max_concurrent limit
                while pending and len(in_flight) < max_concurrent:
                    task = pending.popleft()
                    self.submit(task)
                    in_flight[task.task_id] = task

                # === POLL PHASE ===
                # Wait for a result with timeout to avoid blocking forever
                task_state = self.get_result(blocking=True, timeout=self.poll_interval)

                if task_state is None:
                    # No result yet, continue polling
                    continue

                # Remove from in-flight tracking
                in_flight.pop(task_state.task_id, None)

                # === ERROR HANDLING ===
                if task_state.status == TaskStatus.FAILED:
                    if on_error == 'raise':
                        raise task_state.exception or RuntimeError(
                            f"Task {task_state.task_id} failed"
                        )
                    else:
                        # on_error == 'skip'
                        if self.verbose:
                            hprint_message(
                                'task failed, skipping', task_state.task_id,
                                'error', str(task_state.exception)
                            )
                        continue

                # === ROUTING PHASE ===
                # Determine the actual result and next tasks
                if router is not None:
                    # Router mode: router decides next tasks
                    # Pass TaskState so router can access input_args for NoPassDown
                    actual_result = task_state.result
                    next_tasks = router(task_state.task_id, actual_result, task_state)
                else:
                    # Wrapper mode: result is (actual_result, next_tasks) tuple
                    if (isinstance(task_state.result, tuple) and
                            len(task_state.result) == 2 and
                            isinstance(task_state.result[1], list)):
                        actual_result, next_tasks = task_state.result
                    else:
                        # Not a proper wrapper result - treat as leaf
                        actual_result = task_state.result
                        next_tasks = []

                # Store next_tasks in TaskState for recording/debugging
                task_state.next_tasks = next_tasks if next_tasks else []

                # === ENQUEUE PHASE ===
                # Check if there were any next_tasks BEFORE filtering
                # Router can return [None] to indicate "not a leaf but no tasks"
                # (e.g., intermediate node waiting for other parents in multi-parent handling)
                has_next = bool(next_tasks)

                # Filter out None markers
                actual_next_tasks = [t for t in next_tasks if t is not None] if next_tasks else []

                if actual_next_tasks:
                    if depth_first:
                        # Insert at HEAD for depth-first traversal
                        for t in reversed(actual_next_tasks):
                            pending.appendleft(t)
                    else:
                        # Append to TAIL for breadth-first traversal
                        pending.extend(actual_next_tasks)

                if not has_next:
                    # Only add to leaf_results if there were truly no next tasks
                    # (not just filtered out markers)
                    leaf_results.append(actual_result)

                # === CALLBACK PHASE ===
                if on_task_complete:
                    on_task_complete(task_state.task_id, actual_result)

        finally:
            # Stop workers if we started them
            if workers_started and hasattr(self, 'stop'):
                self.stop()

        # Return single result or tuple based on leaf count
        if len(leaf_results) == 0:
            return None
        elif len(leaf_results) == 1:
            return leaf_results[0]
        else:
            return tuple(leaf_results)


@attrs(slots=False)
class SingleThreadExecutor(QueuedExecutorBase):
    """
    Single-threaded executor - runs in one thread (current or background).

    This executor processes tasks sequentially in a single thread.
    Use run(blocking=True) for synchronous execution in the current thread,
    or run(blocking=False) for asynchronous execution in a background thread.

    Attributes:
        Inherits all attributes from QueuedExecutorBase.
        num_workers is fixed to 1.

    Examples:
        Blocking mode (runs in current thread):

        >>> executor = SingleThreadExecutor(
        ...     input_queue_service=queue_service,
        ...     output_queue_service=queue_service,
        ...     input_queue_id='tasks',
        ...     output_queue_id='results'
        ... )
        >>> executor.run(blocking=True)  # Blocks until stopped

        Non-blocking mode (background thread):

        >>> flag = executor.run(blocking=False)
        >>> executor.submit(Task(callable=lambda: 42))
        >>> result = executor.get_result()
        >>> executor.stop(flag)
    """

    def __attrs_post_init__(self):
        """Force num_workers to 1 for single-thread executor."""
        object.__setattr__(self, 'num_workers', 1)
        super().__attrs_post_init__()

    def _create_worker(self, worker_id: int, active_flag: list) -> Thread:
        """Create a worker thread."""
        return Thread(
            target=self._worker_loop,
            args=(worker_id, active_flag),
            name=f"{self.name}-worker-{worker_id}",
            daemon=True
        )

    def _start_worker(self, worker: Thread) -> None:
        """Start the worker thread."""
        worker.start()

    def _join_worker(self, worker: Thread, timeout: float) -> None:
        """Wait for the worker thread to finish."""
        worker.join(timeout=timeout)

    def _is_worker_alive(self, worker: Thread) -> bool:
        """Check if the worker thread is still running."""
        return worker.is_alive()


@attrs(slots=False)
class SimulatedMultiThreadExecutor(SingleThreadExecutor):
    """
    Single-threaded executor with manual task processing methods.

    Extends SingleThreadExecutor with pull-based methods for processing
    tasks one at a time or in batches, useful for scenarios requiring
    fine-grained control over task execution (e.g., WebDriver automation
    where only one thread can interact with a browser).

    This executor "simulates" multi-threaded behavior by processing tasks
    sequentially from a queue, allowing the caller to control when each
    task is executed.

    Attributes:
        Inherits all attributes from SingleThreadExecutor.

    Examples:
        Manual task processing:

        >>> executor = SimulatedMultiThreadExecutor(
        ...     input_queue_service=queue_service,
        ...     output_queue_service=queue_service,
        ...     input_queue_id='tasks',
        ...     output_queue_id='results'
        ... )
        >>> task = Task(callable=lambda x: x * 2, args=(5,))
        >>> executor.submit(task)
        >>> result = executor.process_one()
        >>> print(result.result)  # 10

        Process all available tasks:

        >>> for i in range(5):
        ...     executor.submit(Task(callable=lambda x: x * 2, args=(i,)))
        >>> results = executor.process_all()
        >>> print(len(results))  # 5
    """

    def process_one(
            self,
            blocking: bool = False,
            timeout: Optional[float] = None
    ) -> Optional[TaskState]:
        """
        Process a single task from the input queue.

        Pulls one task from the queue, executes it, and puts the result
        in the output queue. This method does NOT start a worker loop.

        Args:
            blocking: If True, block until a task is available.
            timeout: Maximum time to wait for a task (seconds).

        Returns:
            TaskResult if a task was processed, None if queue was empty.

        Raises:
            TypeError: If the item from queue is not a Task.
        """
        task = self.input_queue_service.get(
            self.input_queue_id,
            blocking=blocking,
            timeout=timeout
        )

        if task is None:
            return None

        if not isinstance(task, Task):
            raise TypeError(
                f"Expected Task from queue, got {type(task).__name__}"
            )

        result = self._execute_task(0, task)
        self.output_queue_service.put(self.output_queue_id, result)
        self._processed_count += 1

        return result

    def process_all(self) -> List[TaskState]:
        """
        Process all currently available tasks in the input queue.

        Continues processing until the input queue is empty.

        Returns:
            List of TaskResults for all processed tasks.
        """
        results = []
        while self.input_queue_service.size(self.input_queue_id) > 0:
            result = self.process_one(blocking=False)
            if result is not None:
                results.append(result)
        return results

    def run_in_thread(self, active_flag: Optional[list] = None) -> Thread:
        """
        Start the executor in a background thread.

        This is similar to run(blocking=False) but returns the Thread
        object instead of the active_flag.

        Args:
            active_flag: Optional mutable list [True] for stop signaling.

        Returns:
            The started Thread object.
        """
        self.start(active_flag)
        return self._workers[0] if self._workers else None

    @property
    def processed_count(self) -> int:
        """Get the total number of tasks processed."""
        return self._processed_count


@attrs(slots=False)
class QueuedThreadPoolExecutor(QueuedExecutorBase):
    """
    Multi-threaded executor - multiple threads pulling from queue.

    This executor spawns multiple worker threads that concurrently
    pull tasks from the input queue and execute them.

    Best for I/O-bound tasks (network, file, database operations)
    due to Python's GIL limiting CPU-bound parallelism.

    Attributes:
        Inherits all attributes from QueuedExecutorBase.

    Examples:
        >>> executor = QueuedThreadPoolExecutor(
        ...     input_queue_service=queue_service,
        ...     output_queue_service=queue_service,
        ...     input_queue_id='tasks',
        ...     output_queue_id='results',
        ...     num_workers=4
        ... )
        >>> flag = executor.start()
        >>> for i in range(10):
        ...     executor.submit(Task(callable=process_data, args=(i,)))
        >>> # Collect results
        >>> results = [executor.get_result() for _ in range(10)]
        >>> executor.stop(flag)
    """

    def _create_worker(self, worker_id: int, active_flag: list) -> Thread:
        """Create a worker thread."""
        return Thread(
            target=self._worker_loop,
            args=(worker_id, active_flag),
            name=f"{self.name}-worker-{worker_id}",
            daemon=True
        )

    def _start_worker(self, worker: Thread) -> None:
        """Start the worker thread."""
        worker.start()

    def _join_worker(self, worker: Thread, timeout: float) -> None:
        """Wait for the worker thread to finish."""
        worker.join(timeout=timeout)

    def _is_worker_alive(self, worker: Thread) -> bool:
        """Check if the worker thread is still running."""
        return worker.is_alive()


def _process_worker_loop(
    worker_id: int,
    active_flag: list,
    queue_service_factory: Callable,
    input_queue_id: str,
    output_queue_id: str,
    poll_interval: float,
    verbose: bool,
    name: str
):
    """
    Standalone worker loop for process pool executor.

    This is a module-level function (not an instance method) to enable
    pickling for cross-process communication on Windows.

    Each worker creates its own queue service instance using the factory
    to avoid pickling issues with file handles and connections.

    Args:
        worker_id: Unique identifier for this worker.
        active_flag: Mutable list [True/False] for stop signaling.
        queue_service_factory: Callable that creates a queue service instance.
        input_queue_id: ID of the input queue.
        output_queue_id: ID of the output queue.
        poll_interval: Seconds to wait between queue polls.
        verbose: Whether to print debug messages.
        name: Name prefix for this executor.
    """
    # Each worker creates its own queue service instance for IPC
    queue_service = queue_service_factory()
    no_task_count = 0

    if verbose:
        hprint_message('worker started', f'{name}-{worker_id}')

    try:
        while active_flag[0]:
            task = queue_service.get(input_queue_id, blocking=False)

            if task is None:
                no_task_count += 1
                if verbose and no_task_count % 100 == 0:
                    hprint_message(
                        'worker waiting', f'{name}-{worker_id}',
                        'poll_interval', poll_interval
                    )
                sleep(poll_interval)
                continue

            no_task_count = 0

            if not isinstance(task, Task):
                if verbose:
                    hprint_message(
                        'invalid task type', type(task).__name__,
                        'worker', f'{name}-{worker_id}'
                    )
                continue

            # Execute task
            start_time = time()
            try:
                result_value = task.execute()
                end_time = time()

                result = TaskState(
                    task_id=task.task_id,
                    result=result_value,
                    status=TaskStatus.COMPLETED,
                    input_args=task.args,
                    input_kwargs=task.kwargs,
                    worker_id=worker_id,
                    start_time=start_time,
                    end_time=end_time,
                    execution_time=end_time - start_time
                )
            except Exception as e:
                end_time = time()

                if verbose:
                    hprint_message(
                        'task failed', task.task_id,
                        'worker', worker_id,
                        'error', str(e)
                    )

                result = TaskState(
                    task_id=task.task_id,
                    result=None,
                    status=TaskStatus.FAILED,
                    exception=e,
                    input_args=task.args,
                    input_kwargs=task.kwargs,
                    worker_id=worker_id,
                    start_time=start_time,
                    end_time=end_time,
                    execution_time=end_time - start_time
                )

            queue_service.put(output_queue_id, result)

    finally:
        # Close the worker's queue service instance
        if hasattr(queue_service, 'close'):
            queue_service.close()
        if verbose:
            hprint_message('worker stopped', f'{name}-{worker_id}')


@attrs(slots=False)
class QueuedProcessPoolExecutor(QueuedExecutorBase):
    """
    Multi-process executor - multiple processes pulling from queue.

    This executor spawns multiple worker processes that concurrently
    pull tasks from the input queue and execute them.

    Best for CPU-bound tasks as it bypasses Python's GIL.

    Note:
        Requires a queue_service that supports inter-process communication
        (e.g., StorageBasedQueueService or Redis-based queue).

        Each worker process creates its own queue service instance using the
        provided queue_service_factory to avoid pickling issues with file
        handles and connections.

        The active_flag for process communication should be created using
        multiprocessing.Manager().list() for cross-process visibility.

    Attributes:
        Inherits all attributes from QueuedExecutorBase.
        queue_service_factory: Callable that creates a queue service instance.
            Each worker process calls this to create its own instance.
        mp_context: Multiprocessing context ('spawn', 'fork', etc.).

    Examples:
        >>> from multiprocessing import Manager
        >>> from functools import partial
        >>> from python_utils.service_utils.queue_service.storage_based_queue_service import (
        ...     StorageBasedQueueService
        ... )
        >>>
        >>> # Factory function to create queue service in each worker
        >>> def create_queue_service():
        ...     return StorageBasedQueueService(root_path='/tmp/queues', use_pickle=True)
        >>>
        >>> manager = Manager()
        >>> active_flag = manager.list([True])
        >>> queue_service = create_queue_service()  # Main process instance
        >>>
        >>> executor = QueuedProcessPoolExecutor(
        ...     input_queue_service=queue_service,
        ...     output_queue_service=queue_service,
        ...     input_queue_id='tasks',
        ...     output_queue_id='results',
        ...     num_workers=4,
        ...     queue_service_factory=create_queue_service
        ... )
        >>> executor.start(active_flag)
        >>> # Submit tasks...
        >>> active_flag[0] = False  # Stop workers
    """

    queue_service_factory = attrib(default=None)
    """Callable that creates a queue service instance for each worker process."""

    mp_context = attrib(type=Optional[BaseContext], default=None)

    def __attrs_post_init__(self):
        """Initialize multiprocessing context and validate factory."""
        super().__attrs_post_init__()
        if self.mp_context is None:
            object.__setattr__(self, 'mp_context', get_context('spawn'))
        if self.queue_service_factory is None:
            raise ValueError(
                "queue_service_factory is required for QueuedProcessPoolExecutor. "
                "Provide a callable that creates a queue service instance."
            )

    def _create_worker(self, worker_id: int, active_flag: list) -> Process:
        """Create a worker process.

        Uses a module-level function instead of instance method to avoid
        pickling issues with attrs-generated weakrefs on Windows.

        Each worker creates its own queue service instance using the factory.
        """
        return self.mp_context.Process(
            target=_process_worker_loop,
            args=(
                worker_id,
                active_flag,
                self.queue_service_factory,
                self.input_queue_id,
                self.output_queue_id,
                self.poll_interval,
                self.verbose,
                self.name
            ),
            name=f"{self.name}-worker-{worker_id}",
            daemon=True
        )

    def _start_worker(self, worker: Process) -> None:
        """Start the worker process."""
        worker.start()

    def _join_worker(self, worker: Process, timeout: float) -> None:
        """Wait for the worker process to finish."""
        worker.join(timeout=timeout)

    def _is_worker_alive(self, worker: Process) -> bool:
        """Check if the worker process is still running."""
        return worker.is_alive()


__all__ = [
    'QueuedExecutorBase',
    'SingleThreadExecutor',
    'SimulatedMultiThreadExecutor',
    'QueuedThreadPoolExecutor',
    'QueuedProcessPoolExecutor',
]
