"""Tests for forced loop mode under expansion (Task 20.2).

Validates: Requirements 32.1, 32.2
"""
import os
import shutil
import tempfile

import pytest
from attr import attrs, attrib

from python_utils.common_objects.workflow.workflow import Workflow
from python_utils.common_objects.workflow.common.result_pass_down_mode import ResultPassDownMode
from python_utils.common_objects.workflow.common.step_wrapper import StepWrapper


# ---------------------------------------------------------------------------
# Concrete Workflow subclass for testing
# ---------------------------------------------------------------------------

@attrs(slots=False)
class _TestWorkflow(Workflow):
    _save_dir: str = attrib(default=None)

    def __attrs_post_init__(self):
        if self._save_dir is None:
            self._save_dir = tempfile.mkdtemp(prefix="forcedloop_test_")
        os.makedirs(self._save_dir, exist_ok=True)
        super().__attrs_post_init__()

    def _get_result_path(self, result_id, *args, **kwargs) -> str:
        return os.path.join(self._save_dir, f"step_{result_id}.pkl")


@pytest.fixture
def save_dir():
    d = tempfile.mkdtemp(prefix="forcedloop_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


class TestHasLoopStepsWithExpansion:
    """Validates: Requirement 32.1 — _has_loop_steps() returns True when max_expansion_events > 0."""

    def test_has_loop_steps_true_with_expansion_configured(self, save_dir):
        """_has_loop_steps() returns True when max_expansion_events > 0 even with no loop_back_to steps."""
        wf = _TestWorkflow(
            steps=[
                StepWrapper(lambda x: x, name="step_a"),
                StepWrapper(lambda x: x, name="step_b"),
            ],
            save_dir=save_dir,
            max_expansion_events=1,
        )
        assert wf._has_loop_steps() is True

    def test_has_loop_steps_false_without_expansion_or_loops(self, save_dir):
        """_has_loop_steps() returns False when max_expansion_events=0 and no loop_back_to."""
        wf = _TestWorkflow(
            steps=[
                StepWrapper(lambda x: x, name="step_a"),
                StepWrapper(lambda x: x, name="step_b"),
            ],
            save_dir=save_dir,
            max_expansion_events=0,
        )
        assert wf._has_loop_steps() is False

    def test_has_loop_steps_true_with_loop_back_to(self, save_dir):
        """_has_loop_steps() returns True when a step has loop_back_to (regardless of expansion)."""
        wf = _TestWorkflow(
            steps=[
                StepWrapper(lambda x: x, name="step_a"),
                StepWrapper(
                    lambda x: x,
                    name="step_b",
                    loop_back_to="step_a",
                    loop_condition=lambda state, result: False,
                ),
            ],
            save_dir=save_dir,
            max_expansion_events=0,
        )
        assert wf._has_loop_steps() is True


class TestSeqNNamingWithExpansion:
    """Validates: Requirement 32.2 — ___seqN naming used from first step when expansion is configured."""

    def test_seq_naming_used_from_first_step(self, save_dir):
        """Steps before first expansion use sequential ___seqN naming."""
        saved_result_ids = []
        original_save = _TestWorkflow._save_result

        def tracking_save(self_wf, result, output_path=None, **kw):
            if output_path:
                basename = os.path.basename(output_path)
                saved_result_ids.append(basename)
            return original_save(self_wf, result, output_path=output_path, **kw)

        wf = _TestWorkflow(
            steps=[
                StepWrapper(lambda x: x + 1, name="step_a"),
                StepWrapper(lambda x: x + 2, name="step_b"),
            ],
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            max_expansion_events=1,
            max_total_steps=20,
            enable_result_save=True,
        )

        # Monkey-patch _save_result to track what result IDs are used
        wf._save_result = lambda result, output_path=None, **kw: tracking_save(
            wf, result, output_path=output_path, **kw
        )

        result = wf._run(0)

        # With max_expansion_events > 0, _has_loop_steps() returns True,
        # so ___seqN naming should be used
        seq_files = [f for f in saved_result_ids if "___seq" in f]
        assert len(seq_files) > 0, (
            f"Expected ___seqN naming but got: {saved_result_ids}"
        )

    def test_no_seq_naming_without_expansion(self, save_dir):
        """Without expansion configured, plain naming is used (no ___seqN)."""
        saved_result_ids = []
        original_save = _TestWorkflow._save_result

        def tracking_save(self_wf, result, output_path=None, **kw):
            if output_path:
                basename = os.path.basename(output_path)
                saved_result_ids.append(basename)
            return original_save(self_wf, result, output_path=output_path, **kw)

        wf = _TestWorkflow(
            steps=[
                StepWrapper(lambda x: x + 1, name="step_a"),
                StepWrapper(lambda x: x + 2, name="step_b"),
            ],
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            max_expansion_events=0,
            enable_result_save=True,
        )

        wf._save_result = lambda result, output_path=None, **kw: tracking_save(
            wf, result, output_path=output_path, **kw
        )

        result = wf._run(0)

        # Without expansion, no ___seqN naming
        seq_files = [f for f in saved_result_ids if "___seq" in f]
        assert len(seq_files) == 0, (
            f"Expected no ___seqN naming but got: {saved_result_ids}"
        )
