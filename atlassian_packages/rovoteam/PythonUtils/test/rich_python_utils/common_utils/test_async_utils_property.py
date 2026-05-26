"""Property-based tests for call_maybe_async correctness.

Feature: async-workflow, Property 1: call_maybe_async correctness

For any callable f (sync function, async function, functools.partial wrapping
an async function, or __call__-based object) and any valid arguments,
call_maybe_async(f, *args, **kwargs) shall return the same value that directly
calling and (if async) awaiting f(*args, **kwargs) would produce.

**Validates: Requirements 12.1, 12.2, 12.3**
"""
import asyncio
import functools
import sys
from enum import IntEnum
from pathlib import Path

# Setup import paths
_current_file = Path(__file__).resolve()
_test_dir = _current_file.parent
while _test_dir.name != "test" and _test_dir.parent != _test_dir:
    _test_dir = _test_dir.parent
_project_root = _test_dir.parent
_src_dir = _project_root / "src"
if _src_dir.exists() and str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

import pytest
from hypothesis import given, settings, strategies as st

from python_utils.common_utils.async_utils import call_maybe_async


# ---------------------------------------------------------------------------
# Callable type enum for strategy generation
# ---------------------------------------------------------------------------

class CallableType(IntEnum):
    SYNC_FUNC = 0
    ASYNC_FUNC = 1
    PARTIAL_ASYNC = 2
    SYNC_CALL_OBJ = 3
    ASYNC_CALL_OBJ = 4


# ---------------------------------------------------------------------------
# Callable factories — each takes an integer and returns it multiplied by a factor
# ---------------------------------------------------------------------------

def _make_sync_func(factor: int):
    """Create a sync function that multiplies input by factor."""
    def sync_fn(x: int) -> int:
        return x * factor
    return sync_fn


def _make_async_func(factor: int):
    """Create an async function that multiplies input by factor."""
    async def async_fn(x: int) -> int:
        return x * factor
    return async_fn


def _make_partial_async(factor: int):
    """Create a functools.partial wrapping an async function."""
    async def async_mul(f: int, x: int) -> int:
        return x * f
    return functools.partial(async_mul, factor)


def _make_sync_call_obj(factor: int):
    """Create a __call__-based object (sync)."""
    class SyncCallObj:
        def __init__(self, f):
            self._f = f
        def __call__(self, x: int) -> int:
            return x * self._f
    return SyncCallObj(factor)


def _make_async_call_obj(factor: int):
    """Create a __call__-based object (async)."""
    class AsyncCallObj:
        def __init__(self, f):
            self._f = f
        async def __call__(self, x: int) -> int:
            return x * self._f
    return AsyncCallObj(factor)


# Map callable type to factory
_FACTORIES = {
    CallableType.SYNC_FUNC: _make_sync_func,
    CallableType.ASYNC_FUNC: _make_async_func,
    CallableType.PARTIAL_ASYNC: _make_partial_async,
    CallableType.SYNC_CALL_OBJ: _make_sync_call_obj,
    CallableType.ASYNC_CALL_OBJ: _make_async_call_obj,
}


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

callable_type_strategy = st.sampled_from(list(CallableType))
factor_strategy = st.integers(min_value=-100, max_value=100)
input_strategy = st.integers(min_value=-1000, max_value=1000)


# ---------------------------------------------------------------------------
# Property test
# ---------------------------------------------------------------------------

class TestCallMaybeAsyncProperty:
    """Property 1: call_maybe_async correctness.

    **Validates: Requirements 12.1, 12.2, 12.3**
    """

    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(
        callable_type=callable_type_strategy,
        factor=factor_strategy,
        arg=input_strategy,
    )
    async def test_call_maybe_async_returns_same_as_direct_call(
        self, callable_type: CallableType, factor: int, arg: int
    ):
        """For any callable type and any arguments, call_maybe_async returns
        the same value as directly calling (and awaiting if async) the callable.

        **Validates: Requirements 12.1, 12.2, 12.3**
        """
        # Build the callable
        factory = _FACTORIES[callable_type]
        fn = factory(factor)

        # Expected result via direct call + await if needed
        expected = arg * factor

        # Actual result via call_maybe_async
        actual = await call_maybe_async(fn, arg)

        assert actual == expected, (
            f"callable_type={callable_type.name}, factor={factor}, arg={arg}: "
            f"expected={expected}, actual={actual}"
        )
