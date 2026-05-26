"""
Unit tests for WorkNodeBase.arun() and _arun().

Validates: Requirements 13.1, 13.2, 13.3, 13.4
"""
import asyncio

import pytest
from attr import attrs

from python_utils.common_objects.workflow.common.worknode_base import (
    WorkNodeBase,
    WorkGraphStopFlags,
)


# ---------------------------------------------------------------------------
# Concrete test subclass — overrides _arun() with a configurable async fn
# ---------------------------------------------------------------------------

@attrs(slots=False)
class AsyncTestNode(WorkNodeBase):
    """Concrete subclass for testing arun/async behavior."""
    _async_fn = None  # Set in tests

    def _run(self, *args, **kwargs):
        raise NotImplementedError("Use _arun for async tests")

    async def _arun(self, *args, **kwargs):
        if self._async_fn:
            if asyncio.iscoroutinefunction(self._async_fn):
                return await self._async_fn(*args, **kwargs)
            return self._async_fn(*args, **kwargs)
        return args[0] if args else None

    def _get_result_path(self, result_id, *args, **kwargs):
        raise NotImplementedError


@attrs(slots=False)
class BaseOnlyNode(WorkNodeBase):
    """Subclass that does NOT override _arun — used to test NotImplementedError."""

    def _run(self, *args, **kwargs):
        return "sync"

    def _get_result_path(self, result_id, *args, **kwargs):
        raise NotImplementedError


# ---------------------------------------------------------------------------
# 1. _arun() raises NotImplementedError on base class
# ---------------------------------------------------------------------------

class TestArunNotImplemented:
    """Req 13.2: _arun() raises NotImplementedError when not overridden."""

    @pytest.mark.asyncio
    async def test_base_arun_raises_not_implemented(self):
        node = BaseOnlyNode()
        with pytest.raises(NotImplementedError):
            await node.arun()


# ---------------------------------------------------------------------------
# 2. Structural checks
# ---------------------------------------------------------------------------

class TestArunStructural:
    """Req 13.1: arun() exists and is an async coroutine function."""

    def test_has_arun(self):
        assert hasattr(WorkNodeBase, 'arun')

    def test_arun_is_coroutine_function(self):
        assert asyncio.iscoroutinefunction(WorkNodeBase.arun)

    def test_has_private_arun(self):
        assert hasattr(WorkNodeBase, '_arun')

    def test_private_arun_is_coroutine_function(self):
        assert asyncio.iscoroutinefunction(WorkNodeBase._arun)


# ---------------------------------------------------------------------------
# 3. Stop-flag separation in arun()
# ---------------------------------------------------------------------------

class TestArunStopFlagSeparation:
    """Req 13.3: arun() separates stop flags from results."""

    @pytest.mark.asyncio
    async def test_terminate_flag_separated(self):
        """When _arun returns (Terminate, value), arun returns (Terminate, value)."""
        node = AsyncTestNode()
        node._async_fn = lambda: (WorkGraphStopFlags.Terminate, "value")
        result = await node.arun()
        assert result == (WorkGraphStopFlags.Terminate, "value")

    @pytest.mark.asyncio
    async def test_abstain_flag_separated(self):
        """When _arun returns (AbstainResult, value), arun returns (AbstainResult, value)."""
        node = AsyncTestNode()
        node._async_fn = lambda: (WorkGraphStopFlags.AbstainResult, "data")
        result = await node.arun()
        assert result == (WorkGraphStopFlags.AbstainResult, "data")

    @pytest.mark.asyncio
    async def test_continue_flag_returns_result_only(self):
        """When no stop flag, arun returns just the result (Continue is implicit)."""
        node = AsyncTestNode()
        node._async_fn = lambda: "plain_result"
        result = await node.arun()
        assert result == "plain_result"

    @pytest.mark.asyncio
    async def test_terminate_with_multiple_values(self):
        """When _arun returns (Terminate, v1, v2), arun returns (Terminate, (v1, v2))."""
        node = AsyncTestNode()
        node._async_fn = lambda: (WorkGraphStopFlags.Terminate, "a", "b")
        result = await node.arun()
        assert result == (WorkGraphStopFlags.Terminate, ("a", "b"))


# ---------------------------------------------------------------------------
# 4. Singleton unpacking in arun()
# ---------------------------------------------------------------------------

class TestArunSingletonUnpacking:
    """Req 13.3: arun() unpacks singleton lists/tuples."""

    @pytest.mark.asyncio
    async def test_singleton_list_unpacked(self):
        node = AsyncTestNode()
        node._async_fn = lambda: [42]
        result = await node.arun()
        assert result == 42

    @pytest.mark.asyncio
    async def test_singleton_tuple_unpacked(self):
        node = AsyncTestNode()
        node._async_fn = lambda: (99,)
        result = await node.arun()
        assert result == 99

    @pytest.mark.asyncio
    async def test_multi_element_list_not_unpacked(self):
        node = AsyncTestNode()
        node._async_fn = lambda: [1, 2, 3]
        result = await node.arun()
        assert result == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_unpack_disabled(self):
        """When unpack_single_result is False, singletons are NOT unpacked."""
        node = AsyncTestNode(unpack_single_result=False)
        node._async_fn = lambda: [42]
        result = await node.arun()
        assert result == [42]


# ---------------------------------------------------------------------------
# 5. _output parameter behavior
# ---------------------------------------------------------------------------

class TestArunOutputParam:
    """Req 13.4: _output parameter appends result and returns stop_flag."""

    @pytest.mark.asyncio
    async def test_output_appends_result(self):
        node = AsyncTestNode()
        node._async_fn = lambda: "hello"
        output = []
        stop_flag = await node.arun(_output=output)
        assert output == ["hello"]
        assert stop_flag == WorkGraphStopFlags.Continue

    @pytest.mark.asyncio
    async def test_output_with_terminate_flag(self):
        node = AsyncTestNode()
        node._async_fn = lambda: (WorkGraphStopFlags.Terminate, "val")
        output = []
        stop_flag = await node.arun(_output=output)
        assert output == ["val"]
        assert stop_flag == WorkGraphStopFlags.Terminate

    @pytest.mark.asyncio
    async def test_output_multiple_calls(self):
        """Multiple arun calls with same _output list accumulate results."""
        node = AsyncTestNode()
        output = []
        node._async_fn = lambda: "first"
        await node.arun(_output=output)
        node._async_fn = lambda: "second"
        await node.arun(_output=output)
        assert output == ["first", "second"]


# ---------------------------------------------------------------------------
# 6. _output_idx parameter behavior
# ---------------------------------------------------------------------------

class TestArunOutputIdxParam:
    """Req 13.4: _output_idx inserts result at index for deterministic ordering."""

    @pytest.mark.asyncio
    async def test_output_idx_inserts_at_index(self):
        output = [None, None, None]
        node = AsyncTestNode()
        node._async_fn = lambda: "middle"
        stop_flag = await node.arun(_output_idx=(output, 1))
        assert output == [None, "middle", None]
        assert stop_flag == WorkGraphStopFlags.Continue

    @pytest.mark.asyncio
    async def test_output_idx_with_terminate_flag(self):
        output = [None, None]
        node = AsyncTestNode()
        node._async_fn = lambda: (WorkGraphStopFlags.Terminate, "val")
        stop_flag = await node.arun(_output_idx=(output, 0))
        assert output == ["val", None]
        assert stop_flag == WorkGraphStopFlags.Terminate

    @pytest.mark.asyncio
    async def test_output_idx_deterministic_ordering(self):
        """Concurrent arun calls with _output_idx produce deterministic output."""
        output = [None, None, None]

        async def make_node(value, idx):
            n = AsyncTestNode()
            n._async_fn = lambda: value
            await n.arun(_output_idx=(output, idx))

        await asyncio.gather(
            make_node("c", 2),
            make_node("a", 0),
            make_node("b", 1),
        )
        assert output == ["a", "b", "c"]

    @pytest.mark.asyncio
    async def test_output_idx_takes_precedence_over_output(self):
        """When both _output_idx and _output are provided, _output_idx wins."""
        output_list = [None, None]
        append_list = []
        node = AsyncTestNode()
        node._async_fn = lambda: "val"
        stop_flag = await node.arun(_output=append_list, _output_idx=(output_list, 0))
        # _output_idx is checked first in the implementation
        assert output_list == ["val", None]
        assert append_list == []  # _output not used
        assert stop_flag == WorkGraphStopFlags.Continue

# ---------------------------------------------------------------------------
# Imports for Workflow._arun() tests
# ---------------------------------------------------------------------------
from python_utils.common_objects.workflow.common.exceptions import WorkflowAborted
from python_utils.common_objects.workflow.common.result_pass_down_mode import ResultPassDownMode
from python_utils.common_objects.workflow.workflow import Workflow


# ---------------------------------------------------------------------------
# Helpers for Workflow._arun() tests
# ---------------------------------------------------------------------------

@attrs(slots=False)
class SimpleAsyncWorkflow(Workflow):
    """Minimal concrete subclass for async testing — no save/resume."""
    def _get_result_path(self, result_id, *args, **kwargs):
        raise NotImplementedError("save not used in tests")


class _StepWrapper:
    """Wraps a callable so per-step attributes can be attached."""
    def __init__(self, fn, **kwargs):
        self._fn = fn
        self.__name__ = getattr(fn, '__name__', str(fn))
        self.__module__ = getattr(fn, '__module__', None)
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __call__(self, *args, **kwargs):
        return self._fn(*args, **kwargs)


# ---------------------------------------------------------------------------
# 7. Workflow._arun() tests
# ---------------------------------------------------------------------------

class TestWorkflowArun:
    """Tests for Workflow._arun() — Req 1.2, 1.3, 1.4, 2.5, 3.2, 4.3, 5.1, 5.2, 5.3"""

    @pytest.mark.asyncio
    async def test_sync_steps_result_as_first_arg(self):
        """Sync steps with ResultAsFirstArg pass previous result."""
        w = SimpleAsyncWorkflow(
            steps=[lambda x: x + 1, lambda x: x * 2],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
        )
        result = await w.arun(5)
        assert result == 12  # (5+1)*2

    @pytest.mark.asyncio
    async def test_async_steps(self):
        """Async steps are awaited correctly."""
        async def async_add(x):
            return x + 10

        async def async_mul(x):
            return x * 3

        w = SimpleAsyncWorkflow(
            steps=[async_add, async_mul],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
        )
        result = await w.arun(2)
        assert result == 36  # (2+10)*3

    @pytest.mark.asyncio
    async def test_mixed_sync_async_steps(self):
        """Mixed sync and async steps work transparently."""
        async def async_step(x):
            return x + 5

        w = SimpleAsyncWorkflow(
            steps=[lambda x: x * 2, async_step],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
        )
        result = await w.arun(3)
        assert result == 11  # 3*2=6, 6+5=11

    @pytest.mark.asyncio
    async def test_empty_steps_returns_none(self):
        w = SimpleAsyncWorkflow(steps=[])
        assert await w.arun() is None

    @pytest.mark.asyncio
    async def test_workflow_aborted_handling(self):
        """WorkflowAborted is caught and _handle_abort is called."""
        def failing_step(x):
            raise WorkflowAborted("abort")

        w = SimpleAsyncWorkflow(steps=[failing_step])
        result = await w.arun(1)
        # Default _handle_abort returns step_result (None since step didn't complete)
        assert result is None

    @pytest.mark.asyncio
    async def test_state_none_when_unused(self):
        """When no step declares update_state, state stays None."""
        w = SimpleAsyncWorkflow(steps=[lambda x: x])
        await w.arun(1)
        assert w._state is None

    @pytest.mark.asyncio
    async def test_per_step_error_handler_sync(self):
        """Sync error handler returns recovery value."""
        def bad_step(x):
            raise ValueError("oops")

        handler = lambda err, result, state, name, idx: "recovered"
        step = _StepWrapper(bad_step, error_handler=handler)
        w = SimpleAsyncWorkflow(steps=[step])
        result = await w.arun(1)
        assert result == "recovered"

    @pytest.mark.asyncio
    async def test_per_step_error_handler_async(self):
        """Async error handler returns recovery value."""
        def bad_step(x):
            raise ValueError("oops")

        async def async_handler(err, result, state, name, idx):
            return "async_recovered"

        step = _StepWrapper(bad_step, error_handler=async_handler)
        w = SimpleAsyncWorkflow(steps=[step])
        result = await w.arun(1)
        assert result == "async_recovered"

    @pytest.mark.asyncio
    async def test_loop_exhaustion_handler(self):
        """Loop exhaustion handler is invoked when max iterations reached."""
        exhausted_calls = []

        def on_exhausted(state, result):
            exhausted_calls.append(result)

        counter = [0]

        def counting_step(x):
            counter[0] += 1
            return counter[0]

        step = _StepWrapper(
            counting_step,
            loop_back_to=0,
            loop_condition=lambda state, result: True,  # always loop
            max_loop_iterations=3,
            on_loop_exhausted=on_exhausted,
        )
        w = SimpleAsyncWorkflow(steps=[step])
        result = await w.arun(0)
        assert len(exhausted_calls) == 1
        assert counter[0] == 4  # 1 initial + 3 loops

    @pytest.mark.asyncio
    async def test_on_error_save_behavior(self):
        """OnError save: when step fails without handler, previous result is saved."""
        from python_utils.common_objects.workflow.common.step_result_save_options import (
            StepResultSaveOptions,
        )

        saved = {}

        @attrs(slots=False)
        class SaveTrackingWorkflow(Workflow):
            def _get_result_path(self, result_id, *args, **kwargs):
                return f"fake_path/{result_id}"

            def _save_result(self, result, output_path=None, **kwargs):
                saved[output_path] = result

        def good_step(x):
            return x + 10

        def bad_step(x):
            raise RuntimeError("boom")

        w = SaveTrackingWorkflow(
            steps=[good_step, bad_step],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=StepResultSaveOptions.OnError,
        )
        with pytest.raises(RuntimeError, match="boom"):
            await w.arun(5)

        # The previous step's result (15) should have been saved
        assert len(saved) == 1
        assert list(saved.values())[0] == 15
