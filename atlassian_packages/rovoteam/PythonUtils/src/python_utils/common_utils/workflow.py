from typing import Callable, Union, Sequence
from enum import StrEnum


class CommonWorkflowControls(StrEnum):
    """
    Common workflow control signals for controlling execution flow.

    This enum provides standard control signals that can be used across different
    workflow and execution systems to manage execution state.

    Attributes:
        Stop: Signal to stop execution immediately
        Pause: Signal to pause execution (can be resumed)
        Continue: Signal to continue or resume execution
    """
    Stop = 'Stop'
    Pause = 'Pause'
    Continue = 'Continue'

class CommonWorkflowStatus(StrEnum):
    """
    Common workflow status states representing execution state.

    This enum provides standard status states that represent the current execution
    state of workflow and agent systems. These states are typically the result of
    applying workflow control signals (see CommonWorkflowControls).

    Attributes:
        Stopped: Execution has been stopped and cannot continue without restart
        Paused: Execution is temporarily paused and can be resumed
        Running: Execution is actively running
    """
    Stopped = 'Stopped'
    Paused = 'Paused'
    Running = 'Running'

class Repeat:
    """
    Class to control the repetition of an operation based on count or condition.

    This class allows repeating an operation a specific number of times or until a condition is met.

    Attributes:
        index (int): The current index of repetition.

    Args:
        repeat (int): Number of times to repeat the operation. Defaults to 0.
        repeat_cond (Callable[[], bool]): A callable condition to determine whether to repeat the operation. Defaults to None.
        init_cond (Union[bool, Callable[[], bool]]): A flag or callable condition to determine the initial repetition check. Defaults to None.

    Examples:
        >>> # Repeat 3 times
        >>> repeat = Repeat(repeat=3)
        >>> [bool(repeat) for _ in range(5)]
        [True, True, True, False, False]

        >>> # Repeat while a condition is True
        >>> condition = lambda: False
        >>> repeat = Repeat(repeat_cond=condition)
        >>> [bool(repeat) for _ in range(3)]
        [False, False, False]

        >>> # Repeat 2 times and then while a condition is True
        >>> condition = lambda: True
        >>> repeat = Repeat(repeat=2, repeat_cond=condition)
        >>> [bool(repeat) for _ in range(5)]
        [True, True, False, False, False]

        >>> # Skip the initial check and repeat while a condition is True
        >>> condition = lambda: False
        >>> repeat = Repeat(repeat_cond=condition, init_cond=True)
        >>> [bool(repeat) for _ in range(3)]
        [True, False, False]

        >>> # Repeat based on a condition that switches from True to False
        >>> condition_list = [True, True, True, False]
        >>> repeat_cond_list = lambda: condition_list.pop(0)
        >>> repeat = Repeat(repeat_cond=repeat_cond_list)
        >>> [bool(repeat) for _ in range(4)]
        [True, True, True, False]

        >>> # Repeat with an initial condition that is True
        >>> init_condition = lambda: True
        >>> repeat = Repeat(init_cond=init_condition)
        >>> [bool(repeat) for _ in range(2)]
        [True, False]

        >>> # Repeat with an initial condition that is False
        >>> init_condition = lambda: False
        >>> repeat = Repeat(repeat=3, init_cond=init_condition)
        >>> [bool(repeat) for _ in range(2)]
        [False, False]
    """

    def __init__(self, repeat: int = 0, repeat_cond: Callable[[], bool] = None, init_cond: Union[bool, Callable[[], bool]] = None):
        """
        Initializes the Repeat class.

        Args:
            repeat (int): Number of times to repeat the operation. Defaults to 0.
            repeat_cond (Callable[[], bool]): A callable condition to determine whether to repeat the operation. Defaults to None.
            init_cond (Union[bool, Callable[[], bool]]): A flag or callable condition to determine the initial repetition check. Defaults to None.
        """
        self._repeat = repeat
        self._repeat_cond = repeat_cond
        self._init_cond = init_cond
        self.index = 0

    def __bool__(self):
        """
        Determines whether to continue repeating based on the index, repeat count, and conditions.

        Returns:
            bool: True if the operation should be repeated, False otherwise.
        """
        if self.index == 0 and self._init_cond is not None:
            if not (self._init_cond is True or self._init_cond()):
                return False
        else:
            if self._repeat_cond is None:
                if not (self.index < self._repeat):
                    return False
            else:
                if self._repeat > 0:
                    if not (
                            (self.index < self._repeat)
                            and self._repeat_cond()
                    ):
                        return False
                else:
                    if not self._repeat_cond():
                        return False

        self.index += 1
        return True


def cleanup_obj(obj, cleanup_methods:Sequence[str]=('quit', 'close', 'exit', '__del__'), raise_on_failure: bool=False):
    """
    Helper function to cleanup an object by trying various cleanup methods.

    This function attempts to clean up an object by:
    1. First trying to use `del` if the object has a `__del__` method defined
    2. Then trying each cleanup method in the provided tuple (quit, close, exit, etc.)

    Args:
        obj: The object instance to cleanup
        cleanup_methods: Tuple of method names to try for cleanup (default: ('quit', 'close', 'exit'))
        raise_on_failure: If True, raises the last exception encountered; otherwise silently handles errors (default: False)

    Returns:
        bool: True if cleanup was successful, False otherwise

    Raises:
        Exception: If raise_on_failure is True and all cleanup attempts fail

    Examples:
        >>> # Cleanup an object with a quit() method
        >>> cleanup_obj(webdriver_instance)
        True

        >>> # Cleanup with custom methods
        >>> cleanup_obj(my_resource, cleanup_methods=('shutdown', 'dispose', 'close'))
        True

        >>> # Raise exception on failure
        >>> cleanup_obj(problematic_obj, raise_on_failure=True)
        Exception: ...
    """
    if obj is None:
        return True

    last_exception = None

    # Try each cleanup method in order
    for cleanup_method_name in cleanup_methods:
        if hasattr(obj, cleanup_method_name):
            cleanup_method = getattr(obj, cleanup_method_name)
            if callable(cleanup_method):
                try:
                    cleanup_method()  # Don't pass obj - it's a bound method
                    return True
                except Exception as e:
                    last_exception = e
                    # Continue to next method

    # If we reach here, all cleanup attempts failed
    if raise_on_failure and last_exception:
        raise last_exception

    return False
