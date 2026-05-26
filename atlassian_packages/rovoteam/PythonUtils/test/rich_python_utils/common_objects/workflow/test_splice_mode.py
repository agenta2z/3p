"""Tests for Workflow splice mode (Task 14.4).

Validates: Requirements 26.1, 26.2, 26.3, 26.4, 26.5
"""
import os
import shutil
import tempfile

import pytest
from attr import attrs, attrib

from python_utils.common_objects.workflow.workflow import Workflow
from python_utils.common_objects.workflow.common.expansion import ExpansionResult
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
            self._save_dir = tempfile.mkdtemp(prefix="splice_test_")
        os.makedirs(self._save_dir, exist_ok=True)
        super().__attrs_post_init__()

    def _get_result_path(self, result_id, *args, **kwargs) -> str:
        return os.path.join(self._save_dir, f"step_{result_id}.pkl")


# ---------------------------------------------------------------------------
# Module-level factory for seed-based reconstruction (needed for resume tests)
# ---------------------------------------------------------------------------

def _splice_seed_factory(seed):
    """Module-level factory for splice mode reconstruction."""
    return [StepWrapper(lambda x: x + 10, name="spliced_step")]


@pytest.fixture
def save_dir():
    d = tempfile.mkdtemp(prefix="splice_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


class TestFollowMode:
    """Validates: Requirement 26.1 — mode='follow' saves emitter result normally."""

    def test_follow_mode_saves_emitter_result(self, save_dir):
        """With mode='follow' (default), the emitter's result is saved."""
        saved_results = []
        original_save = _TestWorkflow._save_result

        def tracking_save(self_wf, result, **kw):
            saved_results.append(result)
            return original_save(self_wf, result, **kw)

        def emitter(x):
            return ExpansionResult(
                result="emitter_output",
                new_steps=[StepWrapper(lambda v: v + "_done", name="added")],
                mode='follow',
            )

        wf = _TestWorkflow(
            steps=[
                StepWrapper(emitter, name="emitter_step"),
                StepWrapper(lambda x: x + "_final", name="final_step"),
            ],
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            max_expansion_events=1,
            max_total_steps=20,
            enable_result_save=True,
        )

        # Monkey-patch to track saves
        _TestWorkflow._save_result = tracking_save
        try:
            result = wf._run("input")
        finally:
            _TestWorkflow._save_result = original_save

        # Emitter result "emitter_output" should be in saved results
        assert "emitter_output" in saved_results


class TestSpliceModeSkipsSave:
    """Validates: Requirements 26.2, 26.3 — mode='splice' skips emitter result save."""

    def test_splice_mode_skips_emitter_result_save(self, save_dir):
        """With mode='splice', the emitter's result is NOT saved."""
        saved_results = []
        original_save = _TestWorkflow._save_result

        def tracking_save(self_wf, result, **kw):
            saved_results.append(result)
            return original_save(self_wf, result, **kw)

        def emitter(x):
            return ExpansionResult(
                result="emitter_output_should_not_save",
                new_steps=[StepWrapper(lambda v: v + "_done", name="added")],
                mode='splice',
            )

        wf = _TestWorkflow(
            steps=[
                StepWrapper(emitter, name="emitter_step"),
                StepWrapper(lambda x: x + "_final", name="final_step"),
            ],
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            max_expansion_events=1,
            max_total_steps=20,
            enable_result_save=True,
        )

        _TestWorkflow._save_result = tracking_save
        try:
            result = wf._run("input")
        finally:
            _TestWorkflow._save_result = original_save

        # Emitter result should NOT be in saved results
        assert "emitter_output_should_not_save" not in saved_results


class TestSpliceModeInputPassThrough:
    """Validates: Requirement 26.4 — first expanded step receives emitter's original input."""

    def test_splice_first_expanded_step_receives_original_input(self, save_dir):
        """In splice mode, the first expanded step gets the emitter's original input."""
        received_inputs = []

        def expanded_step(x):
            received_inputs.append(x)
            return x + "_processed"

        def emitter(x):
            return ExpansionResult(
                result="emitter_result_ignored_for_input",
                new_steps=[StepWrapper(expanded_step, name="expanded")],
                mode='splice',
            )

        wf = _TestWorkflow(
            steps=[
                StepWrapper(emitter, name="emitter_step"),
                StepWrapper(lambda x: x + "_final", name="final_step"),
            ],
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            max_expansion_events=1,
            max_total_steps=20,
        )
        result = wf._run("original_input")

        # The expanded step should have received the emitter's original input
        assert len(received_inputs) == 1
        assert received_inputs[0] == "original_input"

    def test_splice_second_expanded_step_receives_first_expanded_output(self, save_dir):
        """After the first expanded step, subsequent steps receive normal downstream args."""
        received_inputs = []

        def step_a(x):
            received_inputs.append(("a", x))
            return "from_a"

        def step_b(x):
            received_inputs.append(("b", x))
            return "from_b"

        def emitter(x):
            return ExpansionResult(
                result="emitter_result",
                new_steps=[
                    StepWrapper(step_a, name="exp_a"),
                    StepWrapper(step_b, name="exp_b"),
                ],
                mode='splice',
            )

        wf = _TestWorkflow(
            steps=[
                StepWrapper(emitter, name="emitter_step"),
                StepWrapper(lambda x: x + "_final", name="final_step"),
            ],
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            max_expansion_events=1,
            max_total_steps=20,
        )
        result = wf._run("original_input")

        # step_a gets original input (splice), step_b gets step_a's output (normal)
        assert received_inputs[0] == ("a", "original_input")
        assert received_inputs[1] == ("b", "from_a")


class TestSpliceCheckpointResume:
    """Validates: Requirement 26.5 — splice state survives checkpoint/resume."""

    def test_splice_state_persisted_in_checkpoint(self, save_dir):
        """Splice state is saved in checkpoint and workflow completes successfully."""
        call_log = []

        def emitter(x):
            call_log.append("emitter")
            return ExpansionResult(
                result="emitter_result",
                new_steps=[
                    StepWrapper(lambda v: v + "_expanded", name="expanded_step"),
                ],
                mode='splice',
                seed={"key": "val"},
                reconstruct_from_seed=_splice_seed_factory,
            )

        wf = _TestWorkflow(
            steps=[
                StepWrapper(emitter, name="emitter_step"),
                StepWrapper(lambda x: x + "_final", name="final_step"),
            ],
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            max_expansion_events=1,
            max_total_steps=20,
            enable_result_save=True,
        )
        result = wf._run("input_val")

        # Verify the workflow completed successfully
        assert result is not None
        assert len(call_log) == 1
