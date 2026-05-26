"""Async utility functions.

Provides universal async callable detection and execution utilities, async retry logic,
and sync-to-async bridge utilities. This module consolidates all async helpers that were
previously in async_function_helper.py, with extensions for output_validator and
pre_condition support in async_execute_with_retry.

Key design decision: call_maybe_async() uses the "call first, check result" pattern
via inspect.isawaitable() instead of asyncio.iscoroutinefunction(). This works universally
with functools.partial, descriptors, __call__-based objects, and decorated/wrapped callables
— unlike iscoroutinefunction() which fails on many callable wrappers.
"""

import asyncio
import inspect
import logging
import random
from time import monotonic
from typing import Any, Callable, Dict, Sequence, Tuple, Union

from python_utils.common_utils.function_helper import FallbackMode  # noqa: F401 — re-exported


async def maybe_await(result: Any) -> Any:
    """If result is awaitable (coroutine, Future, Task), await it; otherwise return as-is.

    Uses inspect.isawaitable() which covers coroutines, asyncio.Future, asyncio.Task,
    and any object with __await__.

    Args:
        result: Any value or awaitable to potentially await.

    Returns:
        The awaited result if awaitable, or the original value otherwise.
    """
    if inspect.isawaitable(result):
        return await result
    return result


async def call_maybe_async(func: Callable, *args: Any, **kwargs: Any) -> Any:
    """Call func(*args, **kwargs), then await the result if it's awaitable.

    This pattern works universally with:
    - Regular sync functions
    - Regular async functions
    - functools.partial wrapping async functions
    - Descriptors and __call__-based callables
    - Decorated/wrapped callables

    Unlike asyncio.iscoroutinefunction(), which pre-inspects the callable
    and fails on partials/descriptors, this calls first and checks the result.

    Args:
        func: Any callable (sync or async).
        *args: Positional arguments to pass to func.
        **kwargs: Keyword arguments to pass to func.

    Returns:
        The result of calling func, awaited if the result was awaitable.
    """
    result = func(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


async def async_execute_with_retry(
    func: Callable,
    args: Sequence = None,
    kwargs: Dict = None,
    max_retry: int = 3,
    min_retry_wait: float = 0.0,
    max_retry_wait: float = 1.0,
    retry_on_exceptions: Tuple[type, ...] = (Exception,),
    non_retryable_exceptions: Tuple[type, ...] = (),
    output_validator: Callable[..., bool] = None,
    pre_condition: Callable[..., bool] = None,
    default_return_or_raise: Any = None,
    on_retry_callback: Callable = None,
    *,
    total_timeout: Union[float, None] = None,
    attempt_timeout: Union[float, None] = None,
    fallback_func: Union[Callable, list, None] = None,
    fallback_mode: FallbackMode = FallbackMode.NEVER,
    fallback_on_exceptions: Union[tuple, None] = None,
    on_fallback_callback: Union[Callable, None] = None,
) -> Any:
    """Async execute a function with retry logic, pre-condition guard, output validation,
    and optional fallback chain.

    Mirrors the sync execute_with_retry behavior with async support. Both pre_condition
    and output_validator are invoked via call_maybe_async, so they can be sync or async.

    Args:
        func: Function to execute (sync or async — handled via call-first pattern).
        args: Positional arguments passed to func and pre_condition.
        kwargs: Keyword arguments passed to func and pre_condition.
        max_retry: Maximum number of retry attempts.
        min_retry_wait: Minimum wait time between retries in seconds.
        max_retry_wait: Maximum wait time between retries in seconds.
        retry_on_exceptions: Tuple of exception types that trigger retry.
        output_validator: Post-check callable invoked via call_maybe_async(output_validator, result).
            Should return True if the output is valid. If False, triggers a retry.
        pre_condition: Guard callable invoked via call_maybe_async(pre_condition, *args, **kwargs)
            before each attempt. If it returns False, execution stops and returns
            default_return_or_raise.
        default_return_or_raise: Value to return or exception to raise on failure
            or when pre_condition is False.
        on_retry_callback: Callback function on each retry (can be sync or async).
            Called with (attempt_number, exception).
        total_timeout: Wall-clock cap in seconds for the entire retry loop. None or 0 disables.
            Negative raises ValueError.
        attempt_timeout: Per-attempt cap in seconds via asyncio.wait_for. None disables.
        fallback_func: Alternative callable(s) to try on failure. Single callable is normalized
            to a one-element list. Empty list is treated as None.
        fallback_mode: When to transition to next fallback. Defaults to NEVER.
            ON_EXHAUSTED: retry current callable up to max_retry, then transition.
            ON_FIRST_FAILURE: primary gets 1 attempt, subsequent fallbacks get full max_retry budget.
        fallback_on_exceptions: Exception types that trigger fallback transition.
            None means any exception triggers fallback. Non-matching exceptions propagate immediately.
        on_fallback_callback: Sync or async callback invoked once per chain transition.
            Signature: (from_func, to_func, exception, total_attempts).

    Returns:
        Result of the function call.

    Raises:
        ValueError: If total_timeout is negative. If fallback_func is provided but
            fallback_mode is NEVER. If fallback_mode is not NEVER but no fallback_func provided.
        TimeoutError: If total_timeout or attempt_timeout expires and no retries remain.
        Exception: If all retries fail and default_return_or_raise is an Exception or None.
    """
    # --- Early validation of new parameters ---
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

    # --- Fallback input validation (no async-callable check needed for async helper) ---
    if fallback_func is not None and fallback_mode == FallbackMode.NEVER:
        raise ValueError("fallback_func provided but fallback_mode is NEVER")

    if fallback_mode != FallbackMode.NEVER and (fallback_func is None):
        raise ValueError("fallback_mode is not NEVER but no fallback_func provided")

    args = args or []
    kwargs = kwargs or {}

    # Compute deadline from total_timeout
    deadline = None
    if total_timeout is not None:
        deadline = monotonic() + total_timeout

    # --- Build callable chain ---
    if fallback_func is not None and fallback_mode != FallbackMode.NEVER:
        callable_chain = [func] + fallback_func
    else:
        callable_chain = [func]

    has_fallback = len(callable_chain) > 1
    total_attempts_across_chain = 0
    last_exception = None

    def _default_return_or_raise_terminal():
        """Consult default_return_or_raise at terminal."""
        nonlocal last_exception
        # Surface the terminal exception once per chain so operators can see
        # what drove retries. Per-attempt INFO logs already exist; this is the
        # WARNING-level summary that fires only when retries are exhausted.
        if last_exception is not None:
            logging.getLogger(__name__).warning(
                "async_execute_with_retry: retry chain exhausted after %d total "
                "attempts. Last exception: %s: %s",
                total_attempts_across_chain,
                type(last_exception).__name__,
                str(last_exception)[:500],
            )
        # Normalize timeout errors before terminal
        if isinstance(last_exception, asyncio.TimeoutError):
            raise TimeoutError(
                f"async_execute_with_retry exceeded timeout after exhausting chain"
            ) from last_exception
        if default_return_or_raise is None:
            if has_fallback:
                raise last_exception
            else:
                if last_exception:
                    raise last_exception
                raise RuntimeError(
                    f"Function {func.__name__} failed after {max_retry} attempts"
                )
        elif isinstance(default_return_or_raise, Exception):
            raise default_return_or_raise
        else:
            return default_return_or_raise

    def _check_deadline():
        """Check if deadline has expired. Raises TimeoutError if so."""
        nonlocal last_exception
        if deadline is not None and monotonic() >= deadline:
            raise TimeoutError(
                f"async_execute_with_retry exceeded total_timeout={total_timeout}s"
            ) from last_exception

    async def _check_pre_condition():
        """Check pre_condition. Returns True if should stop (pre_condition is False)."""
        if pre_condition is not None:
            condition_result = await call_maybe_async(pre_condition, *args, **kwargs)
            if not condition_result:
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

    def _compute_effective_timeout():
        """Compute effective timeout for an attempt, capping to remaining budget."""
        effective = None
        if attempt_timeout is not None:
            effective = attempt_timeout
        if deadline is not None:
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise TimeoutError(
                    f"async_execute_with_retry exceeded total_timeout={total_timeout}s"
                ) from last_exception
            if effective is not None:
                effective = min(effective, remaining)
            else:
                effective = remaining
        return effective

    async def _sleep_with_budget(wait_time):
        """Sleep with budget truncation. Raises TimeoutError if budget exhausted."""
        nonlocal last_exception
        if wait_time > 0:
            if deadline is not None:
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise TimeoutError(
                        f"async_execute_with_retry exceeded total_timeout={total_timeout}s"
                    ) from last_exception
                wait_time = min(wait_time, remaining)
            await asyncio.sleep(wait_time)

    for chain_idx, current_func in enumerate(callable_chain):
        is_last_in_chain = (chain_idx == len(callable_chain) - 1)
        is_primary = (chain_idx == 0)

        # Determine max attempts for this callable in the chain
        # CRITICAL: Preserve async semantics: `for attempt in range(max_retry)` = max_retry total calls
        if is_primary and has_fallback and fallback_mode == FallbackMode.ON_FIRST_FAILURE:
            # ON_FIRST_FAILURE: primary gets exactly 1 attempt
            current_max_attempts = 1
        else:
            # ON_EXHAUSTED or subsequent callables in ON_FIRST_FAILURE: full budget
            current_max_attempts = max(1, max_retry)

        transition_exception = None

        for attempt in range(current_max_attempts):
            # Check deadline before each attempt
            _check_deadline()

            # Pre-condition guard: check before each attempt
            if await _check_pre_condition():
                return _handle_pre_condition_stop()

            try:
                effective = _compute_effective_timeout()

                # Execute with or without per-attempt timeout
                if effective is not None:
                    coro = current_func(*args, **kwargs)
                    result = await asyncio.wait_for(maybe_await(coro), timeout=effective)
                else:
                    result = current_func(*args, **kwargs)
                    result = await maybe_await(result)

                # Output validation: check after successful execution
                if output_validator is not None:
                    is_valid = await call_maybe_async(output_validator, result)
                    if not is_valid:
                        last_exception = ValueError("Output validation failed")
                        transition_exception = last_exception
                        total_attempts_across_chain += 1

                        # ON_FIRST_FAILURE for primary: validator failure triggers immediate transition
                        if is_primary and has_fallback and fallback_mode == FallbackMode.ON_FIRST_FAILURE:
                            break  # break inner for to transition

                        # Fire on_retry_callback for validation failure
                        if on_retry_callback:
                            await maybe_await(on_retry_callback(attempt, last_exception))

                        if attempt < current_max_attempts - 1:
                            wait_time = random.uniform(min_retry_wait, max_retry_wait)
                            await _sleep_with_budget(wait_time)
                        continue

                return result

            except asyncio.TimeoutError as e:
                last_exception = e
                transition_exception = e
                total_attempts_across_chain += 1

                logging.getLogger(__name__).warning(
                    "Retry attempt %d/%d after %s: %s",
                    attempt + 1,
                    current_max_attempts,
                    type(e).__name__,
                    str(e)[:200],
                )

                if on_retry_callback:
                    await maybe_await(on_retry_callback(attempt, e))

                if attempt < current_max_attempts - 1:
                    wait_time = random.uniform(min_retry_wait, max_retry_wait)
                    await _sleep_with_budget(wait_time)

            except retry_on_exceptions as e:
                if non_retryable_exceptions and isinstance(e, non_retryable_exceptions):
                    raise

                last_exception = e
                transition_exception = e
                total_attempts_across_chain += 1

                logging.getLogger(__name__).warning(
                    "Retry attempt %d/%d after %s: %s",
                    attempt + 1,
                    current_max_attempts,
                    type(e).__name__,
                    str(e)[:200],
                )

                if on_retry_callback:
                    await maybe_await(on_retry_callback(attempt, e))

                if attempt < current_max_attempts - 1:
                    wait_time = random.uniform(min_retry_wait, max_retry_wait)
                    await _sleep_with_budget(wait_time)

        # This callable is exhausted (or ON_FIRST_FAILURE triggered transition)
        if is_last_in_chain:
            # Last callable exhausted — terminal
            _check_deadline()
            return _default_return_or_raise_terminal()

        # Not last in chain — check fallback_on_exceptions filter before transitioning
        if transition_exception is not None and fallback_on_exceptions is not None:
            if not isinstance(transition_exception, fallback_on_exceptions):
                # Exception doesn't match filter — propagate immediately
                # Normalize asyncio.TimeoutError before propagating
                if isinstance(transition_exception, asyncio.TimeoutError):
                    raise TimeoutError(
                        f"async_execute_with_retry: timeout exception does not match fallback filter"
                    ) from transition_exception
                raise transition_exception

        # Fire on_fallback_callback before transitioning to next callable
        if on_fallback_callback is not None:
            next_func = callable_chain[chain_idx + 1]
            await maybe_await(
                on_fallback_callback(current_func, next_func, transition_exception, total_attempts_across_chain)
            )

    # Should not reach here, but just in case
    return _default_return_or_raise_terminal()



def _run_async(coro) -> Any:
    """Run an async coroutine from a sync context.

    This is a sync-to-async bridge that handles the common case of needing
    to run async code from synchronous Python code.

    WARNING — Cross-loop hazards:
        If an async SDK client (like ClaudeSDKClient or DevmateSDKClient) was
        connected in one event loop and then used from a sync bridge that creates
        a different event loop, the client's internal state (background tasks,
        anyio TaskGroups, subprocess pipes) will be invalid. This manifests as
        cryptic errors like "Task was destroyed but it is pending!" or
        "Event loop is closed" on the second call.

        Callers should detect and guard against this situation. See the
        ClaudeCodeInferencer._infer() implementation for an example.

    Args:
        coro: Async coroutine to run.

    Returns:
        Result of the coroutine.

    Raises:
        RuntimeError: If called from within a running event loop (use await directly).
    """
    try:
        asyncio.get_running_loop()
        raise RuntimeError(
            "Cannot use _run_async() from within a running event loop. "
            "Use 'await coro' directly instead."
        )
    except RuntimeError as e:
        if "no running event loop" in str(e).lower() or "no current event loop" in str(e).lower():
            return asyncio.run(coro)
        raise
