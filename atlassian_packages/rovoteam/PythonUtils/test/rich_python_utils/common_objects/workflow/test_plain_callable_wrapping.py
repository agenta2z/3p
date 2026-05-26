"""Tests for plain callable wrapping in expansion (Task 25.2).

Covers:
- Plain function gets synthetic name via wrapping
- Lambda gets synthetic name via wrapping
- StepWrapper instances keep their existing name
"""
import os
import shutil
import tempfile

import pytest
from attr import attrs

from python_utils.common_objects.workflow.workflow import Workflow
from python_utils.common_objects.workflow.common.expansion import ExpansionResult
from python_utils.common_objects.workflow.common.step_wrapper import StepWrapper
from python_utils.common_objects.workflow.common.result_pass_down_mode import ResultPassDownMode


@attrs(slots=False)
class _TestWorkflow(Workflow):
    """Minimal Workflow subclass for callable wrapping tests."""

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self._save_dir = tempfile.mkdtemp(prefix="callable_wrap_test_")

    def _get_result_path(self, result_id, *args, **kwargs) -> str:
        return os.path.join(self._save_dir, f"{result_id}.pkl")

    def cleanup(self):
        shutil.rmtree(self._save_dir, ignore_errors=True)


def plain_function(x):
    """A plain function without a 'name' attribute."""
    return x + 100


class TestPlainCallableWrapping:
    """Task 25.2: Plain callable wrapping for synthetic names."""

    def test_plain_function_gets_synthetic_name(self):
        """A plain function (no 'name' attr) gets wrapped with a synthetic name."""
        def emitter(x):
            return ExpansionResult(
                result=x,
                new_steps=[plain_function],
            )

        step_a = StepWrapper(emitter, name="emitter")

        wf = _TestWorkflow(
            steps=[step_a],
            max_expansion_events=5,
            max_total_steps=100,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
        )
        try:
            result = wf.run(1)
            # plain_function should have been wrapped and given a synthetic name
            # After expansion, _steps should have 2 items: emitter + wrapped plain_function
            assert len(wf._steps) == 2
            expanded_step = wf._steps[1]
            assert isinstance(expanded_step, StepWrapper)
            assert expanded_step.name is not None
            assert "__expanded_" in expanded_step.name
            # The wrapped step should still work correctly
            assert result == 101  # 1 + 100
        finally:
            wf.cleanup()

    def test_lambda_gets_synthetic_name(self):
        """A lambda (no 'name' attr) gets wrapped with a synthetic name."""
        my_lambda = lambda x: x + 200  # noqa: E731

        def emitter(x):
            return ExpansionResult(
                result=x,
                new_steps=[my_lambda],
            )

        step_a = StepWrapper(emitter, name="emitter")

        wf = _TestWorkflow(
            steps=[step_a],
            max_expansion_events=5,
            max_total_steps=100,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
        )
        try:
            result = wf.run(1)
            assert len(wf._steps) == 2
            expanded_step = wf._steps[1]
            assert isinstance(expanded_step, StepWrapper)
            assert expanded_step.name is not None
            assert "__expanded_" in expanded_step.name
            assert result == 201  # 1 + 200
        finally:
            wf.cleanup()

    def test_step_wrapper_keeps_existing_name(self):
        """StepWrapper instances keep their existing name, not wrapped again."""
        named_step = StepWrapper(lambda x: x + 300, name="my_named_step")

        def emitter(x):
            return ExpansionResult(
                result=x,
                new_steps=[named_step],
            )

        step_a = StepWrapper(emitter, name="emitter")

        wf = _TestWorkflow(
            steps=[step_a],
            max_expansion_events=5,
            max_total_steps=100,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
        )
        try:
            result = wf.run(1)
            assert len(wf._steps) == 2
            expanded_step = wf._steps[1]
            # Should be the same StepWrapper, not re-wrapped
            assert expanded_step is named_step
            assert expanded_step.name == "my_named_step"
            assert result == 301  # 1 + 300
        finally:
            wf.cleanup()
