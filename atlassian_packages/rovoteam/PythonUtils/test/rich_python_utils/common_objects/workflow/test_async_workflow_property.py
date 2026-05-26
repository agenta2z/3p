"""Property-based tests for Workflow async execution.

Feature: async-workflow, Properties 2-5

Property 2: Workflow sync/async equivalence
Property 3: Workflow save/resume round-trip
Property 4: Workflow loop-back correctness
Property 5: Workflow error handler invocation

Uses Hypothesis with @settings(max_examples=100) for each property.
"""
import asyncio
import os
import shutil
import tempfile

import pytest
from attr import attrs, attrib
from hypothesis import given, settings, strategies as st

from python_utils.common_objects.workflow.workflow import Workflow
from python_utils.common_objects.workflow.common.result_pass_down_mode import (
    ResultPassDownMode,
)
from python_utils.common_objects.workflow.common.exceptions import WorkflowAborted
from python_utils.common_objects.workflow.common.step_result_save_options import (
    StepResultSaveOptions,
)


# ---------------------------------------------------------------------------
# Concrete Workflow subclasses for testing
# ---------------------------------------------------------------------------

@attrs(slots=False)
class SimpleTestWorkflow(Workflow):
    """Minimal concrete subclass — no save/resume."""
    def _get_result_path(self, result_id, *args, **kwargs):
        raise NotImplementedError("save not used in property tests")


@attrs(slots=False)
class SaveableTestWorkflow(Workflow):
    """Concrete subclass that saves results to a temp directory."""
    _save_dir = attrib(default=None)

    def _get_result_path(self, result_id, *args, **kwargs):
        return os.path.join(self._save_dir, f"step_{result_id}.pkl")


# ---------------------------------------------------------------------------
# Step wrapper for attaching per-step attributes
# ---------------------------------------------------------------------------

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
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Factors for step functions: multiply input by this factor
factor_strategy = st.integers(min_value=-50, max_value=50)

# Number of steps in a workflow
num_steps_strategy = st.integers(min_value=1, max_value=5)

# Input value for the workflow
input_strategy = st.integers(min_value=-100, max_value=100)

# ResultPassDownMode — only the two main modes that work with int→int steps
pass_down_mode_strategy = st.sampled_from([
    ResultPassDownMode.ResultAsFirstArg,
    ResultPassDownMode.NoPassDown,
])


def _make_sync_step(factor):
    """Create a sync step: x -> x * factor."""
    def step(x):
        return x * factor
    step.__name__ = f"sync_mul_{factor}"
    return step


def _make_async_step(factor):
    """Create an async step: x -> x * factor."""
    async def step(x):
        return x * factor
    step.__name__ = f"async_mul_{factor}"
    return step


# ---------------------------------------------------------------------------
# Property 2: Workflow sync/async equivalence
# ---------------------------------------------------------------------------

class TestWorkflowSyncAsyncEquivalence:
    """Property 2: Workflow sync/async equivalence.

    For any sequence of callable steps (mixed sync and async), any
    ResultPassDownMode, and any valid input arguments, Workflow._arun()
    shall produce the same final result as Workflow._run() when given
    the same steps (with async steps replaced by their sync equivalents).

    **Validates: Requirements 1.2, 1.3, 1.4, 1.5, 1.6, 3.1, 3.3, 6.1, 6.2, 6.3, 13.1, 13.3, 13.4**
    """

    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(
        factors=st.lists(factor_strategy, min_size=1, max_size=5),
        use_async=st.lists(st.booleans(), min_size=1, max_size=5),
        mode=pass_down_mode_strategy,
        input_val=input_strategy,
    )
    async def test_sync_async_produce_same_result(
        self, factors, use_async, mode, input_val
    ):
        """_arun() with mixed sync/async steps produces the same result as
        _run() with equivalent sync-only steps.

        **Validates: Requirements 1.2, 1.3, 1.4, 1.5, 1.6, 3.1, 3.3, 6.1, 6.2, 6.3, 13.1, 13.3, 13.4**
        """
        # Align lengths: trim use_async to match factors
        n = len(factors)
        async_flags = (use_async * ((n // len(use_async)) + 1))[:n]

        # Build sync-only steps for _run()
        sync_steps = [_make_sync_step(f) for f in factors]

        # Build mixed steps for _arun() (some async, some sync)
        mixed_steps = []
        for f, is_async in zip(factors, async_flags):
            if is_async:
                mixed_steps.append(_make_async_step(f))
            else:
                mixed_steps.append(_make_sync_step(f))

        # For NoPassDown mode, each step ignores previous result and just
        # receives the original args. So the final result is just the last
        # step applied to input_val.
        # For ResultAsFirstArg, result chains through.

        sync_wf = SimpleTestWorkflow(
            steps=sync_steps,
            result_pass_down_mode=mode,
        )
        async_wf = SimpleTestWorkflow(
            steps=mixed_steps,
            result_pass_down_mode=mode,
        )

        sync_result = sync_wf.run(input_val)
        async_result = await async_wf.arun(input_val)

        assert sync_result == async_result, (
            f"mode={mode}, factors={factors}, async_flags={async_flags}, "
            f"input={input_val}: sync={sync_result}, async={async_result}"
        )


# ---------------------------------------------------------------------------
# Property 3: Workflow save/resume round-trip
# ---------------------------------------------------------------------------

class TestWorkflowSaveResumeRoundTrip:
    """Property 3: Workflow save/resume round-trip.

    For any Workflow with enable_result_save=Always and a sequence of steps,
    running _arun() to completion and then creating a new Workflow with
    resume_with_saved_results=True over the same steps shall produce the
    same final result without re-executing already-saved steps.

    **Validates: Requirements 2.1, 2.2, 2.3, 2.4**
    """

    @pytest.mark.asyncio
    @settings(max_examples=100, deadline=None)
    @given(
        factors=st.lists(
            st.integers(min_value=-10, max_value=10), min_size=2, max_size=4
        ),
        input_val=st.integers(min_value=-50, max_value=50),
    )
    async def test_save_then_resume_produces_same_result(
        self, factors, input_val
    ):
        """Run _arun() with Always save, then resume — same final result.

        **Validates: Requirements 2.1, 2.2, 2.3, 2.4**
        """
        save_dir = tempfile.mkdtemp()
        try:
            steps = [_make_sync_step(f) for f in factors]

            # First run: execute and save all intermediate results
            wf1 = SaveableTestWorkflow(
                steps=steps,
                result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
                enable_result_save=StepResultSaveOptions.Always,
                resume_with_saved_results=False,
                save_dir=save_dir,
            )
            first_result = await wf1.arun(input_val)

            # Track which steps actually execute on resume
            execution_log = []

            def _make_tracked_step(factor, idx):
                def step(x):
                    execution_log.append(idx)
                    return x * factor
                step.__name__ = f"tracked_mul_{factor}"
                return step

            tracked_steps = [
                _make_tracked_step(f, i) for i, f in enumerate(factors)
            ]

            # Second run: resume from saved results.
            # Use an explicit int index (last step) because
            # isinstance(True, int) is True in Python, so
            # resume_with_saved_results=True is treated as 1.
            last_idx = len(factors) - 1
            wf2 = SaveableTestWorkflow(
                steps=tracked_steps,
                result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
                enable_result_save=StepResultSaveOptions.Always,
                resume_with_saved_results=last_idx,
                save_dir=save_dir,
            )
            resumed_result = await wf2.arun(input_val)

            # Results must match
            assert first_result == resumed_result, (
                f"factors={factors}, input={input_val}: "
                f"first={first_result}, resumed={resumed_result}"
            )

            # The last step's result was saved, so resume finds it and
            # no steps should re-execute
            assert len(execution_log) == 0, (
                f"Expected no steps to re-execute on resume, "
                f"but {execution_log} executed"
            )
        finally:
            shutil.rmtree(save_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Property 4: Workflow loop-back correctness
# ---------------------------------------------------------------------------

class TestWorkflowLoopBackCorrectness:
    """Property 4: Workflow loop-back correctness.

    For any Workflow with a step that has loop_back_to, a loop_condition,
    and max_loop_iterations=N, when the loop condition returns True, the
    workflow shall execute the loop body exactly min(actual_true_count, N)
    times before proceeding.

    **Validates: Requirements 4.1, 4.2**
    """

    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(
        max_iters=st.integers(min_value=1, max_value=5),
        actual_true_count=st.integers(min_value=0, max_value=10),
        use_async_condition=st.booleans(),
    )
    async def test_loop_iteration_count_matches_expected(
        self, max_iters, actual_true_count, use_async_condition
    ):
        """Loop runs exactly min(actual_true_count, max_loop_iterations) times.

        **Validates: Requirements 4.1, 4.2**
        """
        call_count = [0]
        condition_calls = [0]

        def counting_step(x):
            call_count[0] += 1
            return call_count[0]

        # Build a condition that returns True for `actual_true_count` times
        def sync_condition(state, result):
            condition_calls[0] += 1
            return condition_calls[0] <= actual_true_count

        async def async_condition(state, result):
            condition_calls[0] += 1
            return condition_calls[0] <= actual_true_count

        condition = async_condition if use_async_condition else sync_condition

        step = _StepWrapper(
            counting_step,
            loop_back_to=0,
            loop_condition=condition,
            max_loop_iterations=max_iters,
        )

        wf = SimpleTestWorkflow(steps=[step])
        await wf.arun(0)

        expected_loops = min(actual_true_count, max_iters)
        # Total calls = 1 (initial) + expected_loops (loop-backs)
        expected_total_calls = 1 + expected_loops

        assert call_count[0] == expected_total_calls, (
            f"max_iters={max_iters}, actual_true_count={actual_true_count}, "
            f"expected_total_calls={expected_total_calls}, "
            f"actual_calls={call_count[0]}"
        )


# ---------------------------------------------------------------------------
# Property 5: Workflow error handler invocation
# ---------------------------------------------------------------------------

class TestWorkflowErrorHandlerInvocation:
    """Property 5: Workflow error handler invocation.

    For any Workflow step that raises an exception, if the step has an
    error_handler attribute (sync or async) that returns a recovery value,
    _arun() shall use that value as the step result and continue execution.
    If the step has no error handler, the exception shall propagate.

    **Validates: Requirements 5.1, 5.2**
    """

    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(
        recovery_value=st.integers(min_value=-1000, max_value=1000),
        use_async_handler=st.booleans(),
    )
    async def test_error_handler_recovery_value_used(
        self, recovery_value, use_async_handler
    ):
        """When a step raises and has an error_handler, the handler's return
        value becomes the step result.

        **Validates: Requirements 5.1, 5.2**
        """
        def failing_step(x):
            raise ValueError("intentional failure")

        def sync_handler(err, result, state, name, idx):
            return recovery_value

        async def async_handler(err, result, state, name, idx):
            return recovery_value

        handler = async_handler if use_async_handler else sync_handler
        step = _StepWrapper(failing_step, error_handler=handler)

        wf = SimpleTestWorkflow(steps=[step])
        result = await wf.arun(42)

        assert result == recovery_value, (
            f"recovery_value={recovery_value}, use_async={use_async_handler}: "
            f"expected={recovery_value}, actual={result}"
        )

    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(
        error_msg=st.text(
            min_size=1, max_size=50,
            alphabet=st.characters(whitelist_categories=('L', 'N')),
        ),
    )
    async def test_no_handler_exception_propagates(self, error_msg):
        """When a step raises and has no error_handler, the exception propagates.

        **Validates: Requirements 5.1, 5.2**
        """
        import re

        def failing_step(x):
            raise ValueError(error_msg)

        wf = SimpleTestWorkflow(steps=[failing_step])

        with pytest.raises(ValueError, match=re.escape(error_msg[:20])):
            await wf.arun(42)
