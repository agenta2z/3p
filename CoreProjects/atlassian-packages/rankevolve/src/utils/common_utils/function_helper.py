import enum
import inspect
import warnings
from functools import reduce
from time import monotonic, sleep
from typing import Callable, List, Any, Union, Optional
from typing import Iterable
from typing import Mapping, Tuple, Sequence, Dict

from rankevolve.src.utils.common_objects.search_fallback_options import SearchFallbackOptions
from rankevolve.src.utils.common_utils.array_helper import index__
from rankevolve.src.utils.common_utils.map_helper import split_dict, merge_mappings
from rankevolve.src.utils.common_utils.typing_helper import iterable
from rankevolve.src.utils.datetime_utils.common import random_sleep


class FuncArgs:
    def __init__(self, positional_args=None, named_args=None):
        """
        Initializes a FuncArgs instance to represent function arguments.

        Args:
            positional_args (list): A list of positional arguments.
            named_args (dict): A dictionary of named (keyword) arguments.
        """
        self.positional_args = positional_args if positional_args is not None else []
        self.named_args = named_args if named_args is not None else {}

    def __repr__(self):
        return f"FuncArgs(positional_args={self.positional_args}, named_args={self.named_args})"

    def __str__(self):
        """
        Returns a string representation of the function arguments.

        The positional arguments are listed first, followed by named arguments in the format key=value.

        Examples:
            >>> func_args = FuncArgs([1, 2], {'a': 3, 'b': 4})
            >>> print(func_args)
            1, 2, a=3, b=4

            >>> func_args = FuncArgs([], {'x': 10})
            >>> print(func_args)
            x=10

            >>> func_args = FuncArgs([5])
            >>> print(func_args)
            5
        """
        pos_args_str = ', '.join(map(str, self.positional_args))
        named_args_str = ', '.join(f"{k}={v}" for k, v in self.named_args.items())
        return ', '.join(filter(None, [pos_args_str, named_args_str]))


def solve_args(args_names: Sequence[str], *args, **kwargs) -> Tuple:
    """
    Matches a list of argument names (`args_names`) with positional (`args`) and keyword (`kwargs`) arguments.

    The goal is to create a final tuple of arguments that align with the order of `args_names`.

    - **Exact match**: If the number of positional arguments equals the length of `args_names`,
      simply return those positional arguments as a tuple (ignoring any potential keyword overlap).
    - **Fewer positional args**: Fill the remaining needed arguments from `kwargs` based on their names.
      If a name is not present in `kwargs`, raise a `ValueError`.
    - **Conflicts**: If a name has already been provided by positional args but also appears in `kwargs`,
      raise a `ValueError`.
    - **More positional args**: If there are more positional args than names, simply return all the
      positional arguments in a tuple (i.e., “extra” positional arguments are not an error).

    Args:
        args_names (Sequence[str]):
            An ordered sequence of argument names.
        *args:
            Positional arguments corresponding (in order) to `args_names`.
        **kwargs:
            Optional keyword arguments, which can fill in missing arguments by name.

    Returns:
        Tuple: A tuple of arguments aligned with the order of `args_names`.
               If there are more positional args than needed, all are returned.

    Raises:
        ValueError:
            - If a name is already provided by a positional argument but also appears in `kwargs`.
            - If a required argument is missing in both `args` and `kwargs`.

    Examples:
        >>> solve_args(['a','b'], 1, 2)
        (1, 2)

        >>> solve_args(['x','y'], 10, y=20)
        (10, 20)

        # Conflict: 'a' given both positionally and in kwargs
        >>> solve_args(['a','b'], 1, a=999)
        Traceback (most recent call last):
        ...
        ValueError: Argument name 'a' conflicts: already provided via a positional argument.

        # Fill missing arguments from kwargs
        >>> solve_args(['a','b','c'], 1, b=2, c=3)
        (1, 2, 3)

        # Missing argument 'c' not found in kwargs
        >>> solve_args(['a','b','c'], 1, b=2)
        Traceback (most recent call last):
        ...
        ValueError: Required argument 'c' is missing in both args and kwargs.

        # More positional arguments than needed; not an error, all are returned
        >>> solve_args(['a','b'], 1, 2, 3)
        (1, 2, 3)
    """
    len_arg_names = len(args_names)
    len_args = len(args)

    # Case 1: If the counts match exactly, return positional args immediately.
    #         (No conflict check in this code branch; the existing code returns directly.)
    if len_arg_names == len_args:
        return args

    # Check conflicts: if a positional argument is also provided in kwargs, raise an error.
    for i in range(len_args):
        arg_name = args_names[i]
        if arg_name in kwargs:
            raise ValueError(
                f"Argument name '{arg_name}' conflicts: already provided via a positional argument."
            )

    # Case 2: If we have fewer positional arguments than needed,
    #         fill the rest from kwargs or raise ValueError if missing.
    if len_arg_names > len_args:
        missing_count = len_arg_names - len_args
        additional_args = [None] * missing_count  # placeholders for the missing positions

        for i in range(len_args, len_arg_names):
            arg_name = args_names[i]
            if arg_name in kwargs:
                additional_args[i - len_args] = kwargs[arg_name]
            else:
                raise ValueError(
                    f"Required argument '{arg_name}' is missing in both args and kwargs."
                )
        return (*args, *additional_args)

    # Case 3: If there are more positional arguments than argument names,
    #         simply return all positional arguments in a tuple.
    return args


def solve_as_single_input(*args, **kwargs):
    """
    Processes input and returns a single value or a dictionary based on the following conditions:

    1. If a **single positional argument** is provided with **no** keyword arguments,
       that positional argument is returned as-is.

    2. If a **single positional argument** is provided and it is a **mapping** (dict-like object),
       and there are **keyword arguments**, then the single-positional-arg mapping and the
       keyword arguments are merged using ``merge_mappings`` and the merged result is returned.

    3. If **only keyword arguments** are provided:
       - If there is exactly **one** keyword argument, return its value.
       - If there are **multiple** keyword arguments, return the dictionary of those arguments.

    4. Otherwise (e.g. multiple positional arguments, or a single non-mapping positional argument
       with keyword arguments), a ``ValueError`` is raised.

    Parameters:
        *args: Positional arguments.
        **kwargs: Keyword arguments.

    Returns:
        - A single value (positional or keyword) if exactly one argument is provided,
        - A merged dictionary if a single positional mapping plus keyword arguments are given,
        - The dictionary of keyword arguments if multiple keyword arguments are provided.

    Raises:
        ValueError: If multiple positional arguments are provided,
                    or if the single positional argument is not a mapping
                    but still accompanied by keyword arguments,
                    or if no valid condition above is met.

    Examples:
        >>> solve_as_single_input(42)
        42

        >>> solve_as_single_input(a=100)
        100

        >>> solve_as_single_input(x=1, y=2)
        {'x': 1, 'y': 2}

        >>> solve_as_single_input({'key': 'value'}, extra=10)  # merging case
        {'extra': 10, 'key': 'value'}

        >>> solve_as_single_input(1, 2)  # multiple positional arguments
        Traceback (most recent call last):
        ...
        ValueError: Invalid input: either provide one positional argument (optionally a mapping) with keyword arguments, or provide keyword arguments only.

        >>> solve_as_single_input(42, b=100)  # single positional arg but it's not a mapping
        Traceback (most recent call last):
        ...
        ValueError: Invalid input: either provide one positional argument (optionally a mapping) with keyword arguments, or provide keyword arguments only.
    """
    if len(args) == 1:
        # Case 1: One positional argument, no kwargs
        if not kwargs:
            return args[0]
        # Case 2: One positional argument that is a mapping, with kwargs
        elif isinstance(args[0], Mapping):
            if len(kwargs) == 1:
                _kwargs = next(iter(kwargs.values()))
                if isinstance(_kwargs, Mapping):
                    kwargs = _kwargs
            return merge_mappings(mappings=(kwargs, args[0]))
    # Case 3: Only kwargs (no positional args)
    elif kwargs and not args:
        if len(kwargs) == 1:
            _kwargs = next(iter(kwargs.values()))
            if isinstance(_kwargs, Mapping):
                kwargs = _kwargs
        return kwargs

    # Case 4: Invalid input
    raise ValueError(
        "Invalid input: either provide one positional argument (optionally a mapping) "
        "with keyword arguments, or provide keyword arguments only. "
        f"Got args '{args}' and kwargs '{kwargs}'."
    )


def get_full_func_name(namespace, func_name: str, sep='.') -> str:
    """
    Constructs the full function name from the namespace and function name using the specified separator.

    Args:
        namespace (str or list): The namespace(s) or module(s) of the function.
        func_name (str): The name of the function.
        sep (str): The separator to use between the namespace and function name.

    Returns:
        str: The full function name.

    Examples:
        >>> get_full_func_name('my_module', 'my_function')
        'my_module.my_function'

        >>> get_full_func_name(['my_module', 'sub_module'], 'my_function')
        'my_module.sub_module.my_function'

        >>> get_full_func_name('my_module', 'my_function', sep='::')
        'my_module::my_function'
    """
    if not namespace:
        return func_name
    if isinstance(namespace, list):
        return sep.join((*namespace, func_name))
    return f'{namespace}{sep}{func_name}'


class FuncInvocation:
    def __init__(self, name: str, namespace=None, full_name: str = None, args: FuncArgs = None,
                 namespace_sep: str = '.'):
        """
        Initializes a FuncInvocation instance to represent a function invocation.

        Args:
            name (str): The name of the function.
            namespace (str or list): The namespace(s) or module(s) of the function.
            full_name (str): The full name of the function, including namespace/module.
            args (FuncArgs): An instance of FuncArgs representing the function arguments.
            namespace_sep (str): The separator to use between the namespace and function name if func_full_name is not provided.
        """
        self.name = name
        self.namespace = namespace
        self.namespace_sep = namespace_sep
        self.full_name = full_name if full_name else get_full_func_name(namespace, name, namespace_sep)
        self.args = args

    def __repr__(self):
        return (f"FuncInvocation(name={self.name}, "
                f"full_name={self.full_name}, namespace={self.namespace}, "
                f"args={self.args})")

    def __str__(self):
        """
        Returns a string representation of the function invocation.

        The string includes the full name of the function and its arguments.

        Examples:
            >>> invocation = FuncInvocation('my_function')
            >>> print(invocation)
            my_function()

            >>> pos_args = [1, 2, 3]
            >>> named_args = {'a': 4, 'b': 5}
            >>> func_args = FuncArgs(positional_args=pos_args, named_args=named_args)
            >>> invocation = FuncInvocation('my_function', 'my_module', args=func_args)
            >>> print(invocation)
            my_module.my_function(1, 2, 3, a=4, b=5)

            >>> pos_args = [10, 20]
            >>> named_args = {'x': 30}
            >>> func_args = FuncArgs(positional_args=pos_args, named_args=named_args)
            >>> invocation = FuncInvocation('another_function', ['another_module', 'sub_module'], args=func_args, namespace_sep='::')
            >>> print(invocation)
            another_module::sub_module::another_function(10, 20, x=30)
        """
        if not self.args:
            return f'{self.full_name}()'

        pos_args_str = ', '.join(map(str, self.args.positional_args))
        named_args_str = ', '.join(f"{k}={v}" for k, v in self.args.named_args.items())
        args_str = ', '.join(filter(None, [pos_args_str, named_args_str]))
        return f"{self.full_name}({args_str})"


class FallbackMode(enum.Enum):
    """Controls when the retry helper transitions to the next fallback callable.

    This is distinct from FallbackInferMode (in agent_foundation streaming_inferencer_base),
    which controls HOW a streaming inferencer's recovery uses a cached partial response.
    The two enums are orthogonal and live in separate packages.

    See also: FallbackInferMode in agent_foundation.common.inferencers.streaming_inferencer_base
    """
    NEVER = "never"           # No fallback — retry same func (today's behavior)
    ON_EXHAUSTED = "exhausted"  # Switch after max_retry attempts of current callable
    ON_FIRST_FAILURE = "first"  # Switch immediately on any failure of current callable


def execute_with_retry(
        func: Callable,
        max_retry: int = 1,
        min_retry_wait: float = 0,
        max_retry_wait: float = 0,
        retry_on_exceptions: List[type] = None,
        output_validator: Callable[..., bool] = None,
        pre_condition: Callable[..., bool] = None,
        on_retry_callback: Callable = None,
        args: List = None,
        kwargs: Dict[str, Any] = None,
        default_return_or_raise: Union[Any, Exception] = None,
        *,
        total_timeout: Union[float, None] = None,
        attempt_timeout: Union[float, None] = None,
        fallback_func: Union[Callable, List[Callable], None] = None,
        fallback_mode: 'FallbackMode' = FallbackMode.NEVER,
        fallback_on_exceptions: Union[tuple, None] = None,
        on_fallback_callback: Union[Callable, None] = None,
) -> Any:
    """
    Executes a function with retry logic and optional pre-condition guard.

    The function retries execution when output_validator returns False or an exception occurs.
    The pre_condition acts as a guard checked before each attempt - if False, execution stops.

    Args:
        func (Callable): The function to execute.
        max_retry (int): Maximum number of retries. Retry is disabled if this number <=1. Defaults to 1.
        min_retry_wait (float): Minimum wait time between retries in seconds. Defaults to 0.
        max_retry_wait (float): Maximum wait time between retries in seconds. If this is 0, then no retry wait time. Defaults to 0.
        retry_on_exceptions (List[type]): List of exception types to retry on. If not specified, then retry on all types of exceptions. Defaults to None.
        output_validator (Callable[[Any], bool]): A callable to validate the output (post-check).
            Should return True if the output is valid. If False, triggers a retry. Defaults to None.
        pre_condition (Callable[..., bool]): A guard callable checked before each execution attempt.
            If it returns False, execution stops and returns default_return_or_raise. Defaults to None.
        on_retry_callback (Callable): Optional callback invoked on each retry attempt. Called with
            (attempt, exception) before the retry wait. Defaults to None.
        args (List): Positional arguments to pass to the function (also passed to pre_condition). Defaults to None.
        kwargs (Dict[str, Any]): Keyword arguments to pass to the function (also passed to pre_condition). Defaults to None.
        default_return_or_raise (Union[Any, Exception]): Value to return or exception to raise if all retries fail or pre_condition is False. Defaults to None.
        total_timeout (float | None): Wall-clock cap in seconds for the entire retry loop. None or 0 disables. Negative raises ValueError.
        attempt_timeout (float | None): Not supported in sync mode. Raises NotImplementedError if provided.
        fallback_func (Callable | list[Callable] | None): Alternative callable(s) to try on failure.
            Single callable is normalized to a one-element list. Empty list is treated as None.
        fallback_mode (FallbackMode): When to transition to next fallback. Defaults to NEVER.
            ON_EXHAUSTED: retry current callable up to max_retry, then transition.
            ON_FIRST_FAILURE: primary gets 1 attempt, subsequent fallbacks get full max_retry budget.
        fallback_on_exceptions (tuple[type, ...] | None): Exception types that trigger fallback transition.
            None means any exception triggers fallback. Non-matching exceptions propagate immediately.
        on_fallback_callback (Callable | None): Callback invoked once per chain transition.
            Signature: (from_func, to_func, exception, total_attempts).

    Returns:
        Any: The result of the function if successful, or default_return_or_raise if pre_condition is False or all retries fail.

    Raises:
        NotImplementedError: If attempt_timeout is provided (sync per-attempt timeout not supported).
        ValueError: If total_timeout is negative. If fallback_func is provided but fallback_mode is NEVER.
            If fallback_mode is not NEVER but no fallback_func provided. If any fallback callable is async.
        TimeoutError: If total_timeout expires during the retry loop.
        Exception: The last exception raised if all retries fail and `default_return_or_raise` is an exception,
                   or a default exception if `default_return_or_raise` is None.

    Examples:
        >>> def test_func(a, b):
        ...     return a / b

        >>> def validator(result):
        ...     return result > 0

        >>> execute_with_retry(test_func, max_retry=3, min_retry_wait=1, max_retry_wait=2, retry_on_exceptions=[ZeroDivisionError], output_validator=validator, args=[4, 2])
        2.0

        >>> execute_with_retry(test_func, max_retry=3, min_retry_wait=1, max_retry_wait=2, retry_on_exceptions=[ZeroDivisionError], output_validator=validator, args=[4, 0], default_return_or_raise="Fallback value")
        'Fallback value'

        >>> execute_with_retry(test_func, max_retry=3, min_retry_wait=1, max_retry_wait=2, output_validator=validator, args=[4, 0], default_return_or_raise=Exception("Custom Exception"))
        Traceback (most recent call last):
        ...
        Exception: Custom Exception

        # Pre-condition as guard (combined with validator for retry-until-success):
        >>> counter = [0]
        >>> def increment():
        ...     counter[0] += 1
        ...     return counter[0]
        >>> def allow_execution():
        ...     return counter[0] < 5  # Guard: stop if counter reaches 5
        >>> def valid_result(r):
        ...     return r >= 3  # Post-check: valid when result >= 3
        >>> execute_with_retry(increment, max_retry=10, pre_condition=allow_execution, output_validator=valid_result)
        3
    """
    # --- Early validation of new parameters ---
    if attempt_timeout is not None:
        raise NotImplementedError(
            "Sync per-attempt timeout is not supported. Use total_timeout for soft deadlines, "
            "or move the hot path to async_execute_with_retry."
        )

    if total_timeout is not None:
        if total_timeout < 0:
            raise ValueError("total_timeout must be non-negative")
        if total_timeout == 0:
            total_timeout = None  # treat 0 as disabled

    # --- Normalize fallback_func ---
    if fallback_func is not None:
        if callable(fallback_func):
            fallback_func = [fallback_func]
        elif isinstance(fallback_func, list):
            if len(fallback_func) == 0:
                fallback_func = None
        # else: leave as-is, validation below will catch non-callable items

    # --- Fallback input validation ---
    if fallback_func is not None and fallback_mode == FallbackMode.NEVER:
        raise ValueError("fallback_func provided but fallback_mode is NEVER")

    if fallback_mode != FallbackMode.NEVER and (fallback_func is None):
        raise ValueError("fallback_mode is not NEVER but no fallback_func provided")

    if fallback_func is not None:
        for fb in fallback_func:
            if inspect.iscoroutinefunction(fb):
                raise ValueError("Async fallback callable passed to sync execute_with_retry")

    if args is None:
        args = []
    if kwargs is None:
        kwargs = {}

    # Compute deadline from total_timeout
    deadline = None
    if total_timeout is not None:
        deadline = monotonic() + total_timeout

    # Handle single execution case (max_retry <= 1)
    # Bypass fast path when total_timeout or fallback_func is set
    if max_retry <= 1 and deadline is None and fallback_func is None:
        # Check pre_condition before execution
        if pre_condition is not None and not pre_condition(*args, **kwargs):
            if default_return_or_raise is None:
                return None
            elif isinstance(default_return_or_raise, Exception):
                raise default_return_or_raise
            else:
                return default_return_or_raise
        return func(*args, **kwargs)

    # --- Build callable chain ---
    if fallback_func is not None and fallback_mode != FallbackMode.NEVER:
        callable_chain = [func] + fallback_func
    else:
        callable_chain = [func]

    has_fallback = len(callable_chain) > 1
    total_attempts_across_chain = 0
    last_exception = None
    if not min_retry_wait:
        min_retry_wait = 0

    def _default_return_or_raise_terminal():
        """Consult default_return_or_raise at terminal."""
        nonlocal last_exception
        if default_return_or_raise is None:
            # Always re-raise the last exception to preserve its type for callers
            # (dest's pre-migration behavior; tests assert specific exception classes).
            if last_exception is not None:
                raise last_exception
            raise Exception("All retries failed and no default return value provided")
        elif isinstance(default_return_or_raise, Exception):
            raise default_return_or_raise from last_exception
        else:
            return default_return_or_raise

    def _check_deadline():
        """Check if deadline has expired. Raises TimeoutError if so."""
        nonlocal last_exception
        if deadline is not None and monotonic() >= deadline:
            raise TimeoutError(
                f"execute_with_retry exceeded total_timeout={total_timeout}s"
            ) from last_exception

    def _check_pre_condition():
        """Check pre_condition. Returns True if should stop (pre_condition is False)."""
        if pre_condition is not None and not pre_condition(*args, **kwargs):
            return True
        return False

    def _handle_pre_condition_stop():
        """Handle pre_condition returning False — return default_return_or_raise."""
        if default_return_or_raise is None:
            return None
        elif isinstance(default_return_or_raise, Exception):
            raise default_return_or_raise
        else:
            return default_return_or_raise

    for chain_idx, current_func in enumerate(callable_chain):
        is_last_in_chain = (chain_idx == len(callable_chain) - 1)
        is_primary = (chain_idx == 0)

        # Determine max attempts for this callable in the chain
        if is_primary and has_fallback and fallback_mode == FallbackMode.ON_FIRST_FAILURE:
            # ON_FIRST_FAILURE: primary gets exactly 1 attempt (no retries)
            current_max_retry = 0  # 0 retries = 1 attempt (initial + 0)
        else:
            # ON_EXHAUSTED or subsequent callables in ON_FIRST_FAILURE: full budget
            current_max_retry = max_retry

        attempts = 0
        transition_exception = None

        while True:
            _check_deadline()

            # Pre-condition check (per-attempt, per-callable)
            if _check_pre_condition():
                return _handle_pre_condition_stop()

            execution_failed = False
            try:
                result = current_func(*args, **kwargs)

                if output_validator and not output_validator(result):
                    execution_failed = True
                    last_exception = ValueError("Output validation failed")
                    transition_exception = last_exception
                    # ON_FIRST_FAILURE for primary: validator failure triggers immediate transition
                    if is_primary and has_fallback and fallback_mode == FallbackMode.ON_FIRST_FAILURE:
                        total_attempts_across_chain += 1
                        break  # break inner while to transition
                else:
                    return result

            except Exception as e:
                if retry_on_exceptions:
                    if not any(isinstance(e, ex) for ex in retry_on_exceptions):
                        raise e

                execution_failed = True
                last_exception = e
                transition_exception = e

            if execution_failed:
                total_attempts_across_chain += 1

                if attempts >= current_max_retry:
                    break  # exhausted this callable's budget

                if on_retry_callback is not None:
                    on_retry_callback(attempts, last_exception)

                warnings.warn(
                    f"Attempts {attempts} of '{current_func}' failed due to error '{last_exception}'. Retry in {min_retry_wait} to {max_retry_wait} seconds.")
                attempts += 1

                # Compute sleep time and truncate to remaining budget if deadline is set
                if not max_retry_wait:
                    sleep_time = min_retry_wait if min_retry_wait else 0
                else:
                    import random
                    sleep_time = random.uniform(min_retry_wait, max_retry_wait)

                if deadline is not None and sleep_time > 0:
                    remaining = deadline - monotonic()
                    if remaining <= 0:
                        raise TimeoutError(
                            f"execute_with_retry exceeded total_timeout={total_timeout}s"
                        ) from last_exception
                    sleep_time = min(sleep_time, remaining)

                if sleep_time > 0:
                    sleep(sleep_time)

        # This callable is exhausted (or ON_FIRST_FAILURE triggered transition)
        if is_last_in_chain:
            # Last callable exhausted — terminal
            _check_deadline()
            return _default_return_or_raise_terminal()

        # Not last in chain — check fallback_on_exceptions filter before transitioning
        if transition_exception is not None and fallback_on_exceptions is not None:
            if not isinstance(transition_exception, fallback_on_exceptions):
                # Exception doesn't match filter — propagate immediately
                raise transition_exception

        # Fire on_fallback_callback before transitioning to next callable
        if on_fallback_callback is not None:
            next_func = callable_chain[chain_idx + 1]
            on_fallback_callback(current_func, next_func, transition_exception, total_attempts_across_chain)

    # Should not reach here, but just in case
    return _default_return_or_raise_terminal()


def apply_arg(
        func: Callable,
        arg: Any = None,
        map_type: Union[type, Tuple[type]] = Mapping,
        seq_type: Union[type, Tuple[type]] = (list, tuple),
        allows_mixed_positional_and_named_arg: bool = False
) -> Any:
    """
    Applies a function `func` to `arg`.
    If `arg` is None, then `func` is executed without arguments.
    If `arg` is of `map_type` (default Mapping), then expand it as named arguments.
    If `arg` is of `seq_type` (default list or tuple), then expand it as positional arguments.
    Otherwise, `arg` is passed as a single argument for `func`.

    if `allows_mixed_positional_and_named_arg` is set True,
    then 'arg' must be a list or tuple of length at least 2,
    and the last element of the list or tuple can be a mapping of named arguments.

    This utility function is helpful when `func` is a function with all optional arguments,
    and we are giving flexibility to the format of the `func`'s arguments.

    Examples:
        >>> def greet(name="John", age=30):
        ...     return f"Hello, {name}! You are {age} years old."

        >>> apply_arg(greet, None)
        'Hello, John! You are 30 years old.'

        >>> apply_arg(greet, ("Alice", 25))
        'Hello, Alice! You are 25 years old.'

        >>> apply_arg(greet, {"name": "Alice", "age": 25})
        'Hello, Alice! You are 25 years old.'

        >>> apply_arg(greet, (["Alice", {"age": 25}]), allows_mixed_positional_and_named_arg=True)
        'Hello, Alice! You are 25 years old.'
    """

    if arg is not None:
        if allows_mixed_positional_and_named_arg:
            if isinstance(arg, (list, tuple)) and len(arg) > 1:
                positional_args, arg = arg[:-1], arg[-1]
                if isinstance(arg, map_type):
                    return func(*positional_args, **arg)
                elif isinstance(arg, seq_type):
                    return func(*positional_args, *arg)
                else:
                    return func(*positional_args, arg)
            else:
                raise ValueError(
                    "when 'allows_mixed_positional_and_named_arg' is set True, "
                    "'arg' must be a list or tuple of length at least 2;"
                    f"got {arg}"
                )
        else:
            if isinstance(arg, map_type):
                return func(**arg)
            elif isinstance(arg, seq_type):
                return func(*arg)
            else:
                return func(arg)
    else:
        return func()


def apply_func(
        func: Callable,
        input,
        seq_type=(list, tuple),
        mapping_type=Mapping,
        skip_if_neither_seq_or_mapping: bool = False,
        pass_seq_index: bool = False,
        pass_mapping_key: bool = False
):
    """
    Applies a function `func` to the input object.
    If `_input` is of `sequence_type`, then `func` is applied to each object in the sequence,
        and returns a sequence of the same type.
    If `_input` is of `mapping_type`, then `func` is applied to the values of the mapping,
        and returns a dictionary of the original keys
        and their corresponding values processed by `func`.
    Otherwise, applies `func` to `_input` itself if `skip_if_neither_seq_or_mapping` is set False.

    Args:
        func: the function to apply on the input object.
        input: the input object.
        seq_type: applies `func` to elements of `input`
            if `input` is of the specified sequence type.
        mapping_type: applies `func` to values of `input`
            if `input` is of the specified mapping type.
        skip_if_neither_seq_or_mapping: True to skip applying `func` if `input`
            is neither of `seq_type` or of `mapping_type`.
        pass_seq_index: True to pass sequence index to `func` as the first argument;
            if `input` is not a `seq_type` and also not a `mapping_type`,
            then `func(None, input)` is executed if this argument is True.
        pass_mapping_key: True to pass mapping key to `func` as the first argument.

    Returns: the output of applying `func` on `input`.

    """
    if isinstance(input, seq_type):
        if pass_seq_index:
            return type(input)(func(i, x) for i, x in enumerate(input))
        else:
            return type(input)(func(x) for x in input)
    elif isinstance(input, mapping_type):
        if pass_mapping_key:
            return {
                k: func(k, v) for k, v in input.items()
            }
        else:
            return {
                k: func(v) for k, v in input.items()
            }
    elif not skip_if_neither_seq_or_mapping:
        if pass_seq_index:
            return func(None, input)
        else:
            return func(input)


def has_parameter(func: Callable, para: str) -> bool:
    """
    Checks if a callable has a parameter of the specified name.

    Args:
        func: The callable to check for the parameter.
        para: The parameter name to search for.

    Returns:
        True if the callable has a parameter of the specified name; otherwise, False.

    Examples:
        >>> def example_func(a, b, c):
        ...     pass
        ...
        >>> has_parameter(example_func, 'a')
        True

        >>> has_parameter(example_func, 'x')
        False
    """
    return para in inspect.signature(func).parameters


def has_varkw(func: Callable) -> bool:
    """
    Checks if a callable supports variable keyword arguments (**kwargs).

    Args:
        func: The callable to check for variable keyword arguments.

    Returns:
        True if the callable has **kwargs parameter; otherwise, False.

    Examples:
        >>> def func_with_kwargs(a, b, **kwargs):
        ...     pass
        ...
        >>> has_varkw(func_with_kwargs)
        True

        >>> def func_without_kwargs(a, b):
        ...     pass
        ...
        >>> has_varkw(func_without_kwargs)
        False

        >>> def func_with_only_kwargs(**kwargs):
        ...     pass
        ...
        >>> has_varkw(func_with_only_kwargs)
        True
    """
    return inspect.getfullargspec(func).varkw is not None


def has_varpos(func: Callable) -> bool:
    """
    Checks if a callable supports variable positional arguments (*args).

    Args:
        func: The callable to check for variable positional arguments.

    Returns:
        True if the callable has *args parameter; otherwise, False.

    Examples:
        >>> def func_with_varargs(a, b, *args):
        ...     pass
        ...
        >>> has_varpos(func_with_varargs)
        True

        >>> def func_without_varargs(a, b):
        ...     pass
        ...
        >>> has_varpos(func_without_varargs)
        False

        >>> def func_with_only_varargs(*args):
        ...     pass
        ...
        >>> has_varpos(func_with_only_varargs)
        True
    """
    return inspect.getfullargspec(func).varargs is not None


def is_first_parameter_varpos(func: Callable) -> bool:
    """
    Checks if the first parameter of a callable is a variable positional parameter.

    Args:
        func: The callable to check for the variable positional parameter.

    Returns:
        True if the first parameter is a variable positional parameter; otherwise, False.

    Examples:
        >>> def example_func(*args, b, c):
        ...     pass
        ...
        >>> is_first_parameter_varpos(example_func)
        True

        >>> def example_func(a, b, c):
        ...     pass
        ...
        >>> is_first_parameter_varpos(example_func)
        False
    """
    return (
            next(iter(inspect.signature(func).parameters.values())).kind
            == inspect.Parameter.VAR_POSITIONAL
    )


def get_arg_names(
        func: Callable,
        include_varargs: bool = False,
        include_varkw: bool = False,
        return_varargs_and_varkw_names: bool = False,
) -> Union[
    List[str],
    Tuple[List[str], Optional[str], Optional[str]],
]:
    """
    Return the argument names of a callable.

    By default, returns a list of all positional and keyword-only argument names
    in the order they are defined. You can optionally include the special argument
    names for *args and **kwargs, and you can choose to have them returned
    separately if desired.

    Args:
        func (Callable):
            The callable (function, method, class, etc.) to analyze.
        include_varargs (bool, optional):
            If True, include the *args name (if present) in the returned list.
            If the callable does not define *args, `None` is appended.
            Defaults to False.
        include_varkw (bool, optional):
            If True, include the **kwargs name (if present) in the returned list.
            If the callable does not define **kwargs, `None` is appended.
            Defaults to False.
        return_varargs_and_varkw_names (bool, optional):
            If True, return a tuple of:
                1. The list of argument names,
                2. The *args name (or None),
                3. The **kwargs name (or None).
            If False (default), only the list of argument names is returned.

    Returns:
        Union[List[Optional[str]], Tuple[List[Optional[str]], Optional[str], Optional[str]]]:
            - If `return_varargs_and_varkw_names` is False (the default):
              A list of argument names. The *args and **kwargs names
              are included as `None` if the callable doesn't define them
              but `include_varargs` or `include_varkw` is True.

            - If `return_varargs_and_varkw_names` is True:
              A tuple of three elements:
                1) The list of argument names (with possible `None`s),
                2) The *args name (or None),
                3) The **kwargs name (or None).

    Examples:
        >>> get_arg_names(get_arg_names)
        ['func', 'include_varargs', 'include_varkw', 'return_varargs_and_varkw_names']

        >>> get_arg_names(sum)
        ['iterable', 'start']

        >>> get_arg_names(sum, include_varargs=True)
        ['iterable', 'start', None]

        >>> get_arg_names(sum, include_varargs=True, include_varkw=True)
        ['iterable', 'start', None, None]

        >>> get_arg_names(dict.__new__)
        ['type']

        >>> get_arg_names(dict.__new__, include_varargs=True, include_varkw=True)
        ['type', 'args', 'kwargs']

        >>> get_arg_names(get_relevant_named_args, return_varargs_and_varkw_names=True)
        (['func', 'include_varargs', 'include_varkw', 'return_other_args', 'exclusion', 'all_named_args_relevant_if_func_support_named_args'], None, 'kwargs')
    """
    arg_spec = inspect.getfullargspec(func)
    out = arg_spec.args + arg_spec.kwonlyargs
    if include_varargs:
        out.append(arg_spec.varargs)
    if include_varkw:
        out.append(arg_spec.varkw)

    if return_varargs_and_varkw_names:
        return out, arg_spec.varargs, arg_spec.varkw
    else:
        return out


def get_relevant_named_args(
        func: Union[Callable, Iterable[Callable]],
        include_varargs: bool = False,
        include_varkw: bool = False,
        return_other_args: bool = False,
        exclusion: Sequence[str] = None,
        all_named_args_relevant_if_func_support_named_args: bool = False,
        **kwargs
) -> Union[Mapping, Tuple[Mapping, Mapping]]:
    """
    Extracts named arguments from `kwargs` that are relevant to the callable `func`.

    Args:
        func: the callable; if a list callable
        include_varargs: True to consider the name of the positional arguments of `func`
            when looking into `kwargs`.
        include_varkw: True to consider the name of the named arguments of `func`
            when looking into `kwargs`.
        exclusion: A sequence of argument names to be excluded from the result.
        return_other_args: returns a 2-tuple, and the second element in the tuple is the other args
            not considered relevant to `func`.
        all_named_args_relevant_if_func_support_named_args (bool, optional):
            If True and every callable in `func` defines **kwargs, then all named arguments
            from `kwargs` are assumed to be relevant (minus any `exclusion`). Defaults to False.
        **kwargs: extracts arguments relevant to `func` from these named arguments.

    Returns: a mapping consisting of the named arguments relevant to `func` if `return_other_args`
        is set False; otherwise, two mappings of named arguments, where the first mapping consists
        of relevant named arguments, and the second mapping consists of other named arguments.

    Examples:
        >>> get_relevant_named_args(sum, iterable=[1, 2], start=0, seed=0)
        {'iterable': [1, 2], 'start': 0}
        >>> get_relevant_named_args(sum, iterable=[1, 2], return_other_args=True, start=0, seed=0)
        ({'iterable': [1, 2], 'start': 0}, {'seed': 0})
        >>> get_relevant_named_args(
        ...    dict.__new__,
        ...    include_varargs=True,
        ...    include_varkw=False,
        ...    type=dict,
        ...    args=None,
        ...    kwargs={1:2, 3:4}
        ... )
        {'type': <class 'dict'>, 'args': None}
        >>> get_relevant_named_args(
        ...    dict.__new__,
        ...    include_varargs=True,
        ...    include_varkw=True,
        ...    type=dict,
        ...    args=None,
        ...    kwargs={1:2, 3:4}
        ... )
        {'type': <class 'dict'>, 'args': None, 'kwargs': {1: 2, 3: 4}}

        >>> def func_with_kwargs(a, **kwargs):
        ...     return a

        # Since func_with_kwargs defines **kwargs, all named arguments become relevant
        # when we enable all_named_args_relevant_if_func_support_named_args=True.
        >>> get_relevant_named_args(
        ...     func_with_kwargs,
        ...     all_named_args_relevant_if_func_support_named_args=True,
        ...     a='value_for_a', x=1, y=2
        ... )
        {'a': 'value_for_a', 'x': 1, 'y': 2}

        >>> get_relevant_named_args(
        ...     func_with_kwargs,
        ...     all_named_args_relevant_if_func_support_named_args=True,
        ...     return_other_args=True,
        ...     exclusion=['x'],
        ...     a='value_for_a', x=1, y=2
        ... )
        ({'a': 'value_for_a', 'y': 2}, {'x': 1})
    """
    all_has_varkw_name = True
    if callable(func):
        arg_names, _, varkw_name = get_arg_names(
            func,
            include_varargs=include_varargs,
            include_varkw=include_varkw,
            return_varargs_and_varkw_names=True
        )
        if not varkw_name:
            all_has_varkw_name = False
    elif iterable(func):
        arg_names = []
        for _func in func:
            _arg_names, _, varkw_name = get_arg_names(
                _func,
                include_varargs=include_varargs,
                include_varkw=include_varkw
            )
            arg_names.extend(_arg_names)
            if not varkw_name:
                all_has_varkw_name = False
    else:
        raise ValueError("'func' must be a callable, or an iterable of callables")

    if all_has_varkw_name and all_named_args_relevant_if_func_support_named_args:
        related_args, unrelated_args = split_dict(kwargs, exclusion, reverse=True)
    else:
        related_args = {
            k: v
            for k, v in kwargs.items()
            if k in arg_names and (not exclusion or k not in exclusion)
        }
        if return_other_args:
            unrelated_args = {
                k: v
                for k, v in kwargs.items()
                if k not in arg_names and (not exclusion or k not in exclusion)
            }

    if return_other_args:
        return related_args, unrelated_args
    else:
        return related_args


def get_relevant_args(
        func: Union[Callable, Iterable[Callable]],
        include_varargs: bool = False,
        include_varkw: bool = False,
        return_other_args: bool = False,
        named_args_exclusion: Sequence[str] = None,
        all_var_args_relevant_if_func_support_var_args: bool = False,
        all_named_args_relevant_if_func_support_named_args: bool = False,
        args=None,
        **kwargs
) -> Union[
    Tuple[Tuple, Mapping],
    Tuple[Tuple[Tuple, Mapping], Tuple[Tuple, Mapping]]
]:
    """
    Return a tuple of (positional_args, named_args) relevant to the given function(s),
    optionally along with leftover/unmatched arguments.

    This function is similar to `get_relevant_named_args`, but also accounts for
    positional arguments in `*args`, trimming them to match what the function
    can accept. Specifically, it:
      1. Determines how many items from `*args` can map to the function's named
         parameters, stopping before the first parameter that appears in `**kwargs`.
      2. Optionally includes additional positional arguments in the "relevant" set
         if the function defines a varargs parameter (`*rest`) and
         `all_var_args_relevant_if_func_support_var_args=True`.
      3. Uses `get_relevant_named_args` to find the relevant named parameters
         in `**kwargs`.
      4. Optionally returns “other” (leftover) positional and named arguments
         if `return_other_args=True`.

    Args:
        func (Union[Callable, Iterable[Callable]]):
            A single callable or an iterable of callables.
        include_varargs (bool, optional):
            Passed through to `get_relevant_named_args`. If True, consider
            the function’s varargs name as a valid “named argument” slot.
            Defaults to False.
        include_varkw (bool, optional):
            Passed through to `get_relevant_named_args`. If True, consider
            the function’s **kwargs name as a valid argument slot.
            Defaults to False.
        return_other_args (bool, optional):
            If True, return a 2-tuple: ((relevant_positional, relevant_named),
            (other_positional, other_named)). If False (default), return a
            single (relevant_positional, relevant_named). Defaults to False.
        named_args_exclusion (Sequence[str], optional):
            A set of argument names that should be excluded from
            the “relevant” named dictionary. Defaults to None.
        all_var_args_relevant_if_func_support_var_args (bool, optional):
            If True and the function (or all callables) defines a varargs
            parameter (e.g., `*rest`), then all items in `*args` are deemed
            relevant. Otherwise, extra items (beyond the function’s
            positional parameters) become “other” arguments if
            `return_other_args=True`. Defaults to False.
        all_named_args_relevant_if_func_support_named_args (bool, optional):
            Passed through to `get_relevant_named_args`. If True and the
            function (or all callables) defines **kwargs, then *all* named
            arguments in `kwargs` are deemed relevant (except those in
            `named_args_exclusion`). Defaults to False.
        *args:
            Positional arguments to be split into relevant vs. other
            based on the function’s parameters.
        **kwargs:
            Named arguments to be split into relevant vs. other.

    Returns:
        Union[Tuple[Tuple, Mapping], Tuple[Tuple[Tuple, Mapping], Tuple[Tuple, Mapping]]]:
          - If `return_other_args=False`:
              (relevant_positional, relevant_named)
          - If `return_other_args=True`:
              ((relevant_positional, relevant_named), (other_positional, other_named))

    Examples:
        >>> def f(a, b, c=3, *rest, d=10, **kw):
        ...     return a + b + c

        # If we call get_relevant_args with a=1, b=2, c=5 in kwargs,
        # that means the earliest named param from is 'a', so we
        # won't take anything from *args for 'a' again. We'll see how leftover
        # vs relevant is split.
        >>> rel_pos, rel_named = get_relevant_args(f, args=(100, 200), a=1, b=2, c=5, x='X')
        >>> rel_pos
        ()
        >>> rel_named
        {'a': 1, 'b': 2, 'c': 5}
        >>> rel_pos, rel_named = get_relevant_args(
        ...     f, args=(100, 200), a=1, b=2, c=5, x='X',
        ...     all_named_args_relevant_if_func_support_named_args=True
        ... )
        >>> rel_pos
        ()
        >>> rel_named
        {'a': 1, 'b': 2, 'c': 5, 'x': 'X'}

        # The earliest named param from is 'b'.
        >>> get_relevant_args(f, args=(100, 200, 300, 400), b=2)
        ((100,), {'b': 2})

        # If the function has varargs and we want all positional
        # to be considered relevant, set all_var_args_relevant_if_func_support_var_args=True
        >>> get_relevant_args(
        ...     f, args=(100, 200, 300, 400),
        ...     all_var_args_relevant_if_func_support_var_args=True
        ... )
        ((100, 200, 300, 400), {})

        # Return leftover as well
        >>> relevant_args, other_args = get_relevant_args(
        ...     f, args=(1, 2, 3, 4, 5), b=10, return_other_args=True
        ... )
        >>> relevant_args
        ((1,), {'b': 10})
        >>> other_args
        ((2, 3, 4, 5), {})
    """

    if args is None:
        get_relevant_named_args_results = get_relevant_named_args(
            func=func,
            include_varargs=include_varargs,
            include_varkw=include_varkw,
            return_other_args=return_other_args,
            exclusion=named_args_exclusion,
            all_named_args_relevant_if_func_support_named_args=all_named_args_relevant_if_func_support_named_args
        )
        if return_other_args:
            return ((), ()), get_relevant_named_args_results
        else:
            return (), get_relevant_named_args_results

    all_has_vararg_name = all_has_varkw_name = True
    kwargs_names = list(kwargs.keys())
    if callable(func):
        arg_names, vararg_name, varkw_name = get_arg_names(
            func,
            include_varargs=include_varargs,
            include_varkw=include_varkw,
            return_varargs_and_varkw_names=True
        )
        if not vararg_name:
            all_has_vararg_name = False
        if not varkw_name:
            all_has_varkw_name = False

    elif iterable(func):
        arg_names = []
        for _func in func:
            _arg_names, _vararg_name, _varkw_name = get_arg_names(
                _func,
                include_varargs=include_varargs,
                include_varkw=include_varkw
            )
            arg_names.extend(_arg_names)
            if not _vararg_name:
                all_has_vararg_name = False
            if not _varkw_name:
                all_has_varkw_name = False
    else:
        raise ValueError("'func' must be a callable, or an iterable of callables")

    if all_has_vararg_name and all_var_args_relevant_if_func_support_var_args:
        relevant_pos_args = args
        leftover_pos_args = ()
    elif not arg_names:
        relevant_pos_args = ()
        leftover_pos_args = args
    else:
        # If kwargs_names is empty, then no arguments are provided via kwargs,
        # so all positional args should be considered up to the function's parameter count
        if not kwargs_names:
            # Take as many positional args as the function can accept
            max_pos_args = len(arg_names)
            relevant_pos_args = args[:max_pos_args]
            leftover_pos_args = args[max_pos_args:]
        else:
            earliest_named_index = index__(
                seq=arg_names,
                search=kwargs_names,
                return_at_first_match=True,
                search_fallback_option=SearchFallbackOptions.Empty
            )

            relevant_pos_args = args[:earliest_named_index]
            leftover_pos_args = args[earliest_named_index:]

    if all_has_varkw_name and all_named_args_relevant_if_func_support_named_args:
        relevant_named_args, other_named_args = split_dict(kwargs, named_args_exclusion, reverse=True)
    else:
        relevant_named_args = {
            k: v
            for k, v in kwargs.items()
            if k in arg_names and (not named_args_exclusion or k not in named_args_exclusion)
        }
        if return_other_args:
            other_named_args = {
                k: v
                for k, v in kwargs.items()
                if k not in arg_names and (not named_args_exclusion or k not in named_args_exclusion)
            }

    if return_other_args:
        return (relevant_pos_args, relevant_named_args), (leftover_pos_args, other_named_args)
    else:
        return relevant_pos_args, relevant_named_args


def compose2(func2: Callable, func1: Callable) -> Callable:
    """
    A composition of two functions.

    Examples:
        >>> def f1(x):
        ...     return x + 2
        >>> def f2(x):
        ...     return x * 2
        >>> assert compose2(f2, f1)(5) == 14  # f2(f1(5))

    Args:
        func2: the outside function.
        func1: the inside function.
    Returns:
        the composed function.
    """

    def _composed(*args, **kwargs):
        return func2(func1(*args, **kwargs))

    return _composed


def compose(*funcs: Callable) -> Callable:
    """
    A composition of multiple functions.

    Examples:
        >>> from timeit import timeit
        >>> def f1(x):
        ...     return x + 2
        >>> def f2(x):
        ...     return x * 2
        >>> assert compose(f2, f1)(5) == 14

        # `compose2` is faster to compose two functions
        >>> def target1():
        ...     compose2(f2, f1)(5)
        >>> def target2():
        ...     compose(f2, f1)(5)
        >>> 0.6 < timeit(target1) / timeit(target2) < 0.8 # `compose2` is about 20% to 40% faster
        True

    Args:
        funcs: the functions to compose.
    Returns:
        the composed function
    """
    return reduce(compose2, funcs)


def sequential(*funcs: Callable) -> Callable:
    """
    Returns a new callable that, when invoked, calls all callables in sequence.
    The results of all callables are collected and returned as a list.

    Examples:
        >>> def greet(name):
        ...     print(f"Hello, {name}!")
        ...     return f"Greeting done for {name}"

        >>> def farewell(name):
        ...     print(f"Goodbye, {name}!")
        ...     return f"Farewell done for {name}"

        >>> seq = sequential(greet, farewell)
        >>> results = seq("Alice")
        Hello, Alice!
        Goodbye, Alice!
        >>> results
        ['Greeting done for Alice', 'Farewell done for Alice']

        >>> # Example with side effects only (printing, no return values).
        >>> def side_effect1(x):
        ...     print("side_effect1 ran")
        >>> def side_effect2(x):
        ...     print("side_effect2 ran")

        >>> seq = sequential(side_effect1, side_effect2)
        >>> results = seq("anything")
        side_effect1 ran
        side_effect2 ran
        >>> results  # Both functions return None, so the result is a list of None.
        [None, None]

    Args:
        *funcs: A variadic list of callables. Each callable should accept
            the same arguments (e.g., (*args, **kwargs)).

    Returns:
        Callable: A new callable that, when invoked, executes all provided
        callables in order and returns a list of their results.
    """

    def chained(*args, **kwargs) -> List:
        results = []
        for func in funcs:
            if func is None:
                results.append(None)
            else:
                results.append(func(*args, **kwargs))
        return results

    return chained


def get_func_name() -> str:
    return inspect.stack()[1][3]


def get_func_caller_name() -> str:
    return inspect.stack()[2][3]


def is_bounded_callable(f: Callable) -> bool:
    return hasattr(f, "__self__")


# region apply processors

def get_processor(processor_name: str, modules: Iterable[Any] = None, processors: Mapping = None) -> Callable:
    """
    Get a processor function based on its name.

    Args:
        processor_name (str): The name of the processor function to retrieve.
        modules (Iterable[Any], optional): An iterable containing modules to search for the processor function. Defaults to None.
        processors (Mapping, optional): A dictionary mapping processor names to functions. Defaults to None.

    Returns:
        Callable: The processor function.

    Raises:
        ValueError: If the specified processor name is not found.

    Example:
        >>> get_processor('strip', modules=[str])
        <method 'strip' of 'str' objects>
    """
    if processors is not None and processor_name in processors:
        processor = processors[processor_name]
        if callable(processor):
            return processor
    else:
        buildins = globals()['__builtins__']
        if processor_name in buildins:
            processor = buildins[processor_name]
            if callable(processor):
                return processor
        for module in modules:
            if hasattr(module, processor_name):
                processor = getattr(module, processor_name)
                if callable(processor):
                    return processor

    raise ValueError(f"processor '{processor_name}' not found")


def process(obj: Any, modules: Iterable[Any] = None, processors: Mapping = None,
            output_as_arg_place_holder: str = '#output', **kwargs) -> Any:
    """
    Apply processing functions to the input object.

    Args:
        obj (Any): The input object to be processed.
        modules (Iterable[Any], optional): An iterable containing modules to search for processor functions. Defaults to None.
        processors (Mapping, optional): A dictionary mapping processor names to functions. Defaults to None.
        output_as_arg_place_holder (str, optional): Placeholder string used to indicate the output argument position. Defaults to '#output'.
        **kwargs: Keyword arguments where the key is the processor name and the value is either True, False,
            a dictionary of processor arguments, or directly the arguments.

    Returns:
        Any: The processed object.


    Example:
        >>> s = "   Hello, World!   "
        >>> process(s, modules=[str], strip=True)
        'Hello, World!'
        >>> process(s, modules=[str], strip=True, lower=True)
        'hello, world!'
        >>> s = "   Hello, World!   xxx"
        >>> process(s, modules=[str], rstrip=' x')
        '   Hello, World!'
        >>> process(s, modules=[str], isdigit=True)
        False
        >>> my_list = [1, 2, 3, 4, 5]
        >>> process(my_list, reverse=True)
        [5, 4, 3, 2, 1]
        >>> my_dict = {'a': 1, 'b': 2, 'c': 3}
        >>> process(my_dict, items=True)
        dict_items([('a', 1), ('b', 2), ('c', 3)])
    """
    if modules is None and processors is None:
        modules = [type(obj), obj]
    for processor_name, processor_args in kwargs.items():
        processor = get_processor(
            processor_name=processor_name,
            modules=modules,
            processors=processors
        )
        _obj = None
        if processor_args is True:
            if is_bounded_callable(processor):
                _obj = processor()
            else:
                _obj = processor(obj)

        elif isinstance(processor_args, Mapping):
            if output_as_arg_place_holder in processor_args.values():
                processor_args = {
                    k: v if v == output_as_arg_place_holder else v
                    for k, v in processor_args.items()
                }

            if is_bounded_callable(processor):
                _obj = processor(**processor_args)
            else:
                _obj = processor(obj, **processor_args)
        elif isinstance(processor_args, List):
            if output_as_arg_place_holder in processor_args:
                processor_args = [
                    obj if v == output_as_arg_place_holder else v
                    for v in processor_args
                ]
                _obj = processor(*processor_args)
            else:
                if is_bounded_callable(processor):
                    _obj = processor(*processor_args)
                else:
                    _obj = processor(obj, *processor_args)
        else:
            if is_bounded_callable(processor):
                _obj = processor(processor_args)
            else:
                _obj = processor(obj, processor_args)
        if _obj is not None:
            obj = _obj
    return obj

# endregion
