"""Tests for checkpoint v1→v2 migration (Task 22.2).

Covers:
- v1 checkpoint (no expansions key) loads cleanly
- Migration is transparent — no user action required
"""
import os
import shutil
import tempfile

import pytest
from attr import attrs

from python_utils.common_objects.workflow.workflow import Workflow
from python_utils.common_objects.workflow.common.step_wrapper import StepWrapper
from python_utils.common_objects.workflow.common.step_result_save_options import StepResultSaveOptions


@attrs(slots=False)
class _TestWorkflow(Workflow):
    """Minimal Workflow subclass for checkpoint migration tests."""

    def _get_result_path(self, result_id, *args, **kwargs) -> str:
        return os.path.join(self._save_dir, f"{result_id}.pkl")

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self._save_dir = tempfile.mkdtemp(prefix="ckpt_migration_test_")

    def cleanup(self):
        shutil.rmtree(self._save_dir, ignore_errors=True)


class TestCheckpointMigration:
    """Task 22.2: Tests for v1→v2 checkpoint migration."""

    def test_v1_checkpoint_no_expansions_key_loads_cleanly(self):
        """A v1 checkpoint (no 'expansions' key) loads without error."""
        step_a = StepWrapper(lambda x: x + 1, name="step_a")
        step_b = StepWrapper(lambda x: x + 2, name="step_b")

        wf = _TestWorkflow(
            steps=[step_a, step_b],
            enable_result_save=StepResultSaveOptions.Always,
            resume_with_saved_results=False,
            max_expansion_events=1,
        )

        try:
            # Run to completion
            result = wf.run(10)
            # With NoPassDown (default), step_b gets original args (10), so result = 12
            assert result == 12  # 10 + 2

            # Now simulate a v1 checkpoint by saving one without 'expansions' key
            v1_checkpoint = {
                "version": 1,
                "exec_seq": 2,
                "step_index": 1,
                "result_id": "step_b___seq2",
                "next_step_index": 2,
                "loop_counts": {},
                "state": None,
                # No "expansions" key — this is the v1 format
            }
            wf._save_checkpoint(v1_checkpoint)

            # Save the step result so resume can load it
            wf._save_result(
                12,
                output_path=wf._get_result_path("step_b___seq2"),
            )

            # Create a new workflow that resumes
            wf2 = _TestWorkflow(
                steps=[step_a, step_b],
                enable_result_save=StepResultSaveOptions.Always,
                resume_with_saved_results=True,
                max_expansion_events=1,
            )
            wf2._save_dir = wf._save_dir

            # _try_load_checkpoint should handle missing 'expansions' key gracefully
            ckpt = wf2._try_load_checkpoint()
            assert ckpt is not None
            # The checkpoint should load without error
            assert ckpt["next_step_index"] == 2
        finally:
            wf.cleanup()

    def test_migration_is_transparent_no_user_action_required(self):
        """v1 checkpoint migration happens automatically during _try_load_checkpoint."""
        step_a = StepWrapper(lambda x: x + 1, name="step_a")

        wf = _TestWorkflow(
            steps=[step_a],
            enable_result_save=StepResultSaveOptions.Always,
            resume_with_saved_results=False,
            max_expansion_events=1,
        )

        try:
            # Manually create a v1 checkpoint
            v1_checkpoint = {
                "version": 1,
                "exec_seq": 1,
                "step_index": 0,
                "result_id": "step_a___seq1",
                "next_step_index": 1,
                "loop_counts": {},
                "state": None,
            }
            wf._save_checkpoint(v1_checkpoint)
            wf._save_result(11, output_path=wf._get_result_path("step_a___seq1"))

            # Resume — should work transparently
            wf2 = _TestWorkflow(
                steps=[step_a],
                enable_result_save=StepResultSaveOptions.Always,
                resume_with_saved_results=True,
                max_expansion_events=1,
            )
            wf2._save_dir = wf._save_dir

            # The workflow should resume from the checkpoint without any user action
            result = wf2.run(10)
            # Since next_step_index=1 and there's only 1 step, it should return
            # the loaded result
            assert result == 11
        finally:
            wf.cleanup()
