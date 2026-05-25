# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.

"""
Task Module

Provides shared task types for queue-based parallel execution.

This module contains backend-agnostic data structures:
- TaskStatus: Enum for task execution status
- Task: Wrapper for callables with task metadata
- TaskState: Container for execution results (renamed from TaskResult)

These types are used by all QueuedExecutor implementations
(SingleThreadExecutor, QueuedThreadPoolExecutor, QueuedProcessPoolExecutor).

Usage:
    from rich_python_utils.mp_utils.task import Task, TaskState, TaskStatus

Example:
    >>> task = Task(callable=lambda x: x * 2, args=(5,))
    >>> result = task.execute()
    >>> print(result)
    10
"""

from enum import Enum
from typing import Any, Callable, Optional, Tuple
import uuid

from attr import attrs, attrib


class TaskStatus(Enum):
    """Status codes for task execution."""

    PENDING = 'pending'
    """Task is waiting to be executed (not yet ready for execution)."""

    READY = 'ready'
    """Task is ready to be executed (all dependencies satisfied)."""

    RUNNING = 'running'
    """Task is currently being executed."""

    COMPLETED = 'completed'
    """Task completed successfully."""

    FAILED = 'failed'
    """Task execution raised an exception."""


@attrs(slots=True)
class Task:
    """
    Wrapper for a callable with task identification and metadata.

    Encapsulates a task (callable) with a unique identifier and optional metadata
    for execution in queue-based executors.

    Attributes:
        callable: The function or callable to execute.
        task_id: Unique identifier for this task. Auto-generated UUID if not provided.
        args: Positional arguments to pass to the callable.
        kwargs: Keyword arguments to pass to the callable.
        name: Human-readable name for the task. Defaults to callable name.

    Examples:
        >>> def my_func(x, y):
        ...     return x + y
        >>> task = Task(callable=my_func, args=(1, 2))
        >>> task.execute()
        3

        >>> task = Task(
        ...     callable=my_func,
        ...     task_id='custom-id',
        ...     args=(1, 2),
        ...     name='Addition Task'
        ... )
        >>> task.task_id
        'custom-id'
    """

    _callable = attrib(type=Callable)
    task_id = attrib(type=str, default=None)
    args = attrib(type=Tuple, default=())
    kwargs = attrib(type=dict, factory=dict)
    name = attrib(type=Optional[str], default=None)

    def __attrs_post_init__(self):
        """Validate parameters and set defaults after initialization."""
        self._validate_parameters()
        if self.task_id is None:
            object.__setattr__(self, 'task_id', str(uuid.uuid4()))
        if self.name is None:
            object.__setattr__(self, 'name', self._get_callable_name())

    def _validate_parameters(self):
        """Validate that the callable is actually callable."""
        if not callable(self._callable):
            raise ValueError(
                f"The 'callable' parameter must be a callable object; "
                f"got {type(self._callable).__name__}."
            )

    def _get_callable_name(self) -> str:
        """Extract a name from the callable."""
        if hasattr(self._callable, '__name__'):
            return self._callable.__name__
        return str(self._callable)

    def execute(self) -> Any:
        """
        Execute the wrapped callable with stored arguments.

        Returns:
            Any: The return value of the callable.

        Raises:
            Exception: Any exception raised by the callable.
        """
        return self._callable(*self.args, **self.kwargs)

    def __repr__(self) -> str:
        """Return a string representation of the task."""
        return f"Task(task_id={self.task_id!r}, name={self.name!r})"


@attrs(slots=True)
class TaskState:
    """
    Container for task execution results with timing and status information.

    Stores the result of a task execution including the return value (or exception),
    status, worker information, and timing data.

    Attributes:
        task_id: The unique identifier of the executed task.
        result: The return value from the task, or None if failed.
        status: The execution status (defaults to PENDING).
        exception: The exception raised if status is FAILED.
        next_tasks: List of downstream tasks generated when this task completed.
            Useful for recording execution history, debugging task relationships,
            and visualizing execution graphs.
        input_args: Original positional arguments passed to the task.
            Critical for router mode to handle self-edges with NoPassDown mode -
            the router needs access to original args to re-create the self-loop task.
        input_kwargs: Original keyword arguments passed to the task.
            Critical for router mode to handle self-edges with NoPassDown mode.
        worker_id: The ID of the worker that executed this task.
        start_time: Unix timestamp when execution started.
        end_time: Unix timestamp when execution ended.
        execution_time: Total execution time in seconds.

    Examples:
        >>> result = TaskState(
        ...     task_id='task-123',
        ...     result=42,
        ...     status=TaskStatus.COMPLETED,
        ...     worker_id=0,
        ...     start_time=1000.0,
        ...     end_time=1001.5,
        ...     execution_time=1.5
        ... )
        >>> result.is_success()
        True

        >>> failed_result = TaskState(
        ...     task_id='task-456',
        ...     result=None,
        ...     status=TaskStatus.FAILED,
        ...     exception=ValueError('Invalid input'),
        ...     worker_id=1,
        ...     start_time=1000.0,
        ...     end_time=1000.1,
        ...     execution_time=0.1
        ... )
        >>> failed_result.is_success()
        False
    """

    task_id = attrib(type=str)
    result = attrib(type=Any, default=None)
    status = attrib(type=TaskStatus, default=TaskStatus.PENDING)
    exception = attrib(type=Optional[Exception], default=None)
    next_tasks = attrib(factory=list)  # List['Task'] - for recording/debugging
    input_args = attrib(type=Tuple, default=())  # Original input args (for NoPassDown self-edges)
    input_kwargs = attrib(type=dict, factory=dict)  # Original input kwargs (for NoPassDown self-edges)
    worker_id = attrib(type=int, default=0)
    start_time = attrib(type=float, default=0.0)
    end_time = attrib(type=float, default=0.0)
    execution_time = attrib(type=float, default=0.0)

    def is_success(self) -> bool:
        """
        Check if the task completed successfully.

        Returns:
            bool: True if status is COMPLETED, False otherwise.
        """
        return self.status == TaskStatus.COMPLETED

    def __repr__(self) -> str:
        """Return a string representation of the result."""
        return (
            f"TaskState(task_id={self.task_id!r}, status={self.status.value}, "
            f"worker_id={self.worker_id}, execution_time={self.execution_time:.4f}s)"
        )


__all__ = [
    'TaskStatus',
    'Task',
    'TaskState',
]
