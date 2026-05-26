"""
Unit tests for async_utils: call_maybe_async, maybe_await, and async_execute_with_retry.

Validates: Requirements 12.1, 12.2, 12.3, 12.4, 12.6, 7.6
"""
import asyncio
import functools

import pytest

from python_utils.common_utils.async_utils import (
    async_execute_with_retry,
    call_maybe_async,
    maybe_await,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sync_add(a, b):
    return a + b


async def async_add(a, b):
    return a + b


class SyncCallable:
    def __call__(self, x):
        return x * 2


class AsyncCallable:
    async def __call__(self, x):
        return x * 3


# ---------------------------------------------------------------------------
# call_maybe_async
# ---------------------------------------------------------------------------

class TestCallMaybeAsync:
    """Tests for call_maybe_async — Req 12.1, 12.2, 12.3, 12.4."""

    @pytest.mark.asyncio
    async def test_sync_function(self):
        result = await call_maybe_async(sync_add, 1, 2)
        assert result == 3

    @pytest.mark.asyncio
    async def test_async_function(self):
        result = await call_maybe_async(async_add, 3, 4)
        assert result == 7

    @pytest.mark.asyncio
    async def test_partial_wrapping_async(self):
        partial_fn = functools.partial(async_add, 10)
        result = await call_maybe_async(partial_fn, 5)
        assert result == 15

    @pytest.mark.asyncio
    async def test_sync_callable_object(self):
        obj = SyncCallable()
        result = await call_maybe_async(obj, 4)
        assert result == 8

    @pytest.mark.asyncio
    async def test_async_callable_object(self):
        obj = AsyncCallable()
        result = await call_maybe_async(obj, 5)
        assert result == 15


# ---------------------------------------------------------------------------
# maybe_await
# ---------------------------------------------------------------------------

class TestMaybeAwait:
    """Tests for maybe_await — Req 12.1, 12.2, 12.3."""

    @pytest.mark.asyncio
    async def test_coroutine(self):
        coro = async_add(1, 2)
        result = await maybe_await(coro)
        assert result == 3

    @pytest.mark.asyncio
    async def test_future(self):
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        fut.set_result(42)
        result = await maybe_await(fut)
        assert result == 42

    @pytest.mark.asyncio
    async def test_task(self):
        task = asyncio.create_task(async_add(5, 6))
        result = await maybe_await(task)
        assert result == 11

    @pytest.mark.asyncio
    async def test_plain_int(self):
        result = await maybe_await(99)
        assert result == 99

    @pytest.mark.asyncio
    async def test_plain_string(self):
        result = await maybe_await("hello")
        assert result == "hello"

    @pytest.mark.asyncio
    async def test_plain_none(self):
        result = await maybe_await(None)
        assert result is None


# ---------------------------------------------------------------------------
# async_execute_with_retry — output_validator
# ---------------------------------------------------------------------------

class TestAsyncExecuteWithRetryOutputValidator:
    """Tests for output_validator in async_execute_with_retry — Req 7.6."""

    @pytest.mark.asyncio
    async def test_validator_false_triggers_retry_then_true_accepts(self):
        counter = [0]

        def increment():
            counter[0] += 1
            return counter[0]

        def valid_result(r):
            return r >= 3

        result = await async_execute_with_retry(
            func=increment,
            max_retry=5,
            min_retry_wait=0.0,
            max_retry_wait=0.0,
            output_validator=valid_result,
        )
        assert result == 3
        assert counter[0] == 3

    @pytest.mark.asyncio
    async def test_async_output_validator(self):
        counter = [0]

        def increment():
            counter[0] += 1
            return counter[0]

        async def async_valid(r):
            return r >= 2

        result = await async_execute_with_retry(
            func=increment,
            max_retry=5,
            min_retry_wait=0.0,
            max_retry_wait=0.0,
            output_validator=async_valid,
        )
        assert result == 2


# ---------------------------------------------------------------------------
# async_execute_with_retry — pre_condition
# ---------------------------------------------------------------------------

class TestAsyncExecuteWithRetryPreCondition:
    """Tests for pre_condition in async_execute_with_retry — Req 7.6."""

    @pytest.mark.asyncio
    async def test_pre_condition_false_returns_default(self):
        result = await async_execute_with_retry(
            func=lambda: 42,
            max_retry=3,
            pre_condition=lambda: False,
            default_return_or_raise="skipped",
        )
        assert result == "skipped"

    @pytest.mark.asyncio
    async def test_pre_condition_true_allows_execution(self):
        result = await async_execute_with_retry(
            func=lambda: 42,
            max_retry=3,
            pre_condition=lambda: True,
        )
        assert result == 42

    @pytest.mark.asyncio
    async def test_async_pre_condition(self):
        async def always_true():
            return True

        result = await async_execute_with_retry(
            func=lambda: 99,
            max_retry=1,
            pre_condition=always_true,
        )
        assert result == 99

    @pytest.mark.asyncio
    async def test_pre_condition_false_returns_none_when_no_default(self):
        result = await async_execute_with_retry(
            func=lambda: 42,
            max_retry=3,
            pre_condition=lambda: False,
            default_return_or_raise=None,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_pre_condition_false_raises_when_default_is_exception(self):
        with pytest.raises(ValueError, match="stopped"):
            await async_execute_with_retry(
                func=lambda: 42,
                max_retry=3,
                pre_condition=lambda: False,
                default_return_or_raise=ValueError("stopped"),
            )


# ---------------------------------------------------------------------------
# async_execute_with_retry — backward compatibility (on_retry_callback)
# ---------------------------------------------------------------------------

class TestAsyncExecuteWithRetryBackwardCompat:
    """Backward compat: existing callers using only on_retry_callback still work."""

    @pytest.mark.asyncio
    async def test_on_retry_callback_invoked(self):
        attempts = []
        counter = [0]

        def flaky():
            counter[0] += 1
            if counter[0] < 3:
                raise RuntimeError("fail")
            return "ok"

        def on_retry(attempt, exc):
            attempts.append(attempt)

        result = await async_execute_with_retry(
            func=flaky,
            max_retry=5,
            min_retry_wait=0.0,
            max_retry_wait=0.0,
            retry_on_exceptions=(RuntimeError,),
            on_retry_callback=on_retry,
        )
        assert result == "ok"
        assert len(attempts) == 2  # retried on attempts 0 and 1

    @pytest.mark.asyncio
    async def test_no_new_params_still_works(self):
        """Calling without output_validator/pre_condition works as before."""
        result = await async_execute_with_retry(
            func=lambda: "hello",
            max_retry=1,
        )
        assert result == "hello"


# ---------------------------------------------------------------------------
# Backward-compat imports from async_function_helper.py
# ---------------------------------------------------------------------------

class TestBackwardCompatImports:
    """Verify imports from async_function_helper.py still work — Req 12.6."""

    def test_import_async_execute_with_retry(self):
        from python_utils.common_utils.async_function_helper import async_execute_with_retry as fn
        assert callable(fn)

    def test_import_run_async(self):
        from python_utils.common_utils.async_function_helper import _run_async as fn
        assert callable(fn)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])


# ---------------------------------------------------------------------------
# Backward compatibility verification — structural assertions
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    """Verify backward compatibility: imports, sync path unchanged.

    Validates: Requirements 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7
    """

    # -- Import checks from async_function_helper (Req 14.7) --

    def test_import_async_execute_with_retry_from_helper(self):
        from python_utils.common_utils.async_function_helper import async_execute_with_retry
        assert callable(async_execute_with_retry)

    def test_import_run_async_from_helper(self):
        from python_utils.common_utils.async_function_helper import _run_async
        assert callable(_run_async)

    def test_import_call_maybe_async_from_helper(self):
        from python_utils.common_utils.async_function_helper import call_maybe_async
        assert callable(call_maybe_async)

    def test_import_maybe_await_from_helper(self):
        from python_utils.common_utils.async_function_helper import maybe_await
        assert callable(maybe_await)

    # -- Import checks from workflow/__init__.py (Req 13.8) --

    def test_import_call_maybe_async_from_workflow_init(self):
        from python_utils.common_objects.workflow import call_maybe_async
        assert callable(call_maybe_async)

    def test_import_maybe_await_from_workflow_init(self):
        from python_utils.common_objects.workflow import maybe_await
        assert callable(maybe_await)

    # -- Structural assertions: sync path unchanged (Req 14.1–14.5) --

    def test_worknode_base_has_run_and_arun(self):
        """WorkNodeBase has both run and arun methods (Req 14.1)."""
        from python_utils.common_objects.workflow.common.worknode_base import WorkNodeBase
        assert hasattr(WorkNodeBase, 'run')
        assert hasattr(WorkNodeBase, 'arun')

    def test_worknode_base_run_is_not_async(self):
        """WorkNodeBase.run is NOT async — sync path unchanged (Req 14.1)."""
        import asyncio
        from python_utils.common_objects.workflow.common.worknode_base import WorkNodeBase
        assert not asyncio.iscoroutinefunction(WorkNodeBase.run)

    def test_workflow_run_is_not_async(self):
        """Workflow._run is NOT async — sync path unchanged (Req 14.2)."""
        import asyncio
        from python_utils.common_objects.workflow.workflow import Workflow
        assert not asyncio.iscoroutinefunction(Workflow._run)

    def test_workgraphnode_run_is_not_async(self):
        """WorkGraphNode._run is NOT async — sync path unchanged (Req 14.3)."""
        import asyncio
        from python_utils.common_objects.workflow.workgraph import WorkGraphNode
        assert not asyncio.iscoroutinefunction(WorkGraphNode._run)

    def test_workgraph_run_is_not_async(self):
        """WorkGraph._run is NOT async — sync path unchanged (Req 14.4)."""
        import asyncio
        from python_utils.common_objects.workflow.workgraph import WorkGraph
        assert not asyncio.iscoroutinefunction(WorkGraph._run)


# =============================================================================
# Post-mortem fix 3: surface swallowed retry exceptions at terminal
# =============================================================================


class TestRetryTerminalExceptionLogging:
    """Fix 3: when async_execute_with_retry exhausts the chain, log the
    terminal exception at WARNING level once. Per-attempt INFO logs already
    exist; this is the missing summary that fires only on exhaustion."""

    @pytest.mark.asyncio
    async def test_terminal_exception_logged_at_warning(self, caplog):
        async def always_fail(_):
            raise ValueError("boom")

        caplog.set_level("WARNING")
        with pytest.raises(ValueError):
            await async_execute_with_retry(
                func=always_fail,
                max_retry=2,
                args=["irrelevant"],
                retry_on_exceptions=(ValueError,),
            )
        warnings = [
            r for r in caplog.records
            if r.levelname == "WARNING" and "retry chain exhausted" in r.message.lower()
        ]
        assert len(warnings) == 1
        assert "ValueError" in warnings[0].message
        assert "boom" in warnings[0].message
