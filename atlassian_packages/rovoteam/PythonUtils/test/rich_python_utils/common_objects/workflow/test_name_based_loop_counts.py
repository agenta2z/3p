"""Tests for name-based loop counts (Task 19.4).

Validates: Requirements 31.1, 31.2, 31.3, 37.1
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
            self._save_dir = tempfile.mkdtemp(prefix="loopcount_test_")
        os.makedirs(self._save_dir, exist_ok=True)
        super().__attrs_post_init__()

    def _get_result_path(self, result_id, *args, **kwargs) -> str:
        return os.path.join(self._save_dir, f"step_{result_id}.pkl")


@pytest.fixture
def save_dir():
    d = tempfile.mkdtemp(prefix="loopcount_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


class TestNameBasedLoopCounts:
    """Validates: Requirements 31.1, 31.3 — loop counts keyed by name after expansion."""

    def test_loop_counts_keyed_by_name_after_expansion(self, save_dir):
        """After expansion, _loop_counts should use name-based keys."""
        loop_iterations = [0]

        def expanding_step(x):
            return ExpansionResult(
                result=x,
                new_steps=[
                    StepWrapper(
                        lambda v: v + 1,
                        name="looping_step",
                        loop_back_to="looping_step",
                        loop_condition=lambda state, result: loop_iterations[0] < 2,
                        max_loop_iterations=5,
                    ),
                ],
            )

        def looping_step_fn(v):
            loop_iterations[0] += 1
            return v + 1

        wf = _TestWorkflow(
            steps=[
                StepWrapper(expanding_step, name="expander"),
                StepWrapper(lambda x: x + 100, name="final"),
            ],
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            max_expansion_events=1,
            max_total_steps=20,
        )

        result = wf._run(0)

        # After expansion, _expansion_active should be True
        assert wf._expansion_active is True
        # Loop counts should be keyed by name, not index
        for key in wf._loop_counts:
            assert isinstance(key, str), f"Expected str key, got {type(key)}: {key}"

    def test_get_loop_count_key_returns_name_when_active(self, save_dir):
        """_get_loop_count_key returns name-based key when expansion is active."""
        wf = _TestWorkflow(
            steps=[StepWrapper(lambda x: x, name="my_step")],
            save_dir=save_dir,
            max_expansion_events=1,
        )
        wf._expansion_active = True

        step = wf._steps[0]
        key = wf._get_loop_count_key(step, 0)
        assert key == "my_step"

    def test_get_loop_count_key_returns_index_when_inactive(self, save_dir):
        """_get_loop_count_key returns index-based key when expansion is not active."""
        wf = _TestWorkflow(
            steps=[StepWrapper(lambda x: x, name="my_step")],
            save_dir=save_dir,
            max_expansion_events=0,
        )
        wf._expansion_active = False

        step = wf._steps[0]
        key = wf._get_loop_count_key(step, 0)
        assert key == 0


class TestSyntheticNames:
    """Validates: Requirement 31.2 — synthetic names assigned to unnamed steps."""

    def test_synthetic_name_for_unnamed_step(self, save_dir):
        """Unnamed steps get synthetic name __step_{index}__ when expansion is active."""
        wf = _TestWorkflow(
            steps=[lambda x: x],  # unnamed step
            save_dir=save_dir,
            max_expansion_events=1,
        )
        wf._expansion_active = True

        step = wf._steps[0]
        key = wf._get_loop_count_key(step, 0)
        assert key == "__step_0__"


class TestMigrationFromIntToName:
    """Validates: Requirement 31.1 — migration from int-keyed to name-keyed on first expansion."""

    def test_migrate_loop_counts_to_names(self, save_dir):
        """_migrate_loop_counts_to_names converts int keys to name keys."""
        wf = _TestWorkflow(
            steps=[
                StepWrapper(lambda x: x, name="step_a"),
                StepWrapper(lambda x: x, name="step_b"),
            ],
            save_dir=save_dir,
            max_expansion_events=1,
        )
        # Simulate int-keyed loop counts from before expansion
        wf._loop_counts = {0: 2, 1: 3}

        wf._migrate_loop_counts_to_names()

        assert wf._loop_counts == {"step_a": 2, "step_b": 3}

    def test_migrate_assigns_synthetic_names_for_unnamed(self, save_dir):
        """Migration assigns synthetic names for unnamed steps."""
        wf = _TestWorkflow(
            steps=[
                lambda x: x,  # unnamed
                StepWrapper(lambda x: x, name="named_step"),
            ],
            save_dir=save_dir,
            max_expansion_events=1,
        )
        wf._loop_counts = {0: 1, 1: 2}

        wf._migrate_loop_counts_to_names()

        assert "__step_0__" in wf._loop_counts
        assert wf._loop_counts["__step_0__"] == 1
        assert wf._loop_counts["named_step"] == 2


class TestResolveIntegerLoopBackToTargets:
    """Validates: Requirement 37.1 — integer loop_back_to resolved to names on first expansion."""

    def test_integer_loop_back_to_resolved_to_name(self, save_dir):
        """Integer loop_back_to targets are resolved to step names on first expansion."""
        wf = _TestWorkflow(
            steps=[
                StepWrapper(lambda x: x, name="target_step"),
                StepWrapper(
                    lambda x: x,
                    name="looper",
                    loop_back_to=0,  # integer target
                    loop_condition=lambda state, result: False,
                ),
            ],
            save_dir=save_dir,
            max_expansion_events=1,
        )

        wf._resolve_integer_loop_back_to_targets()

        # loop_back_to should now be the name "target_step" instead of 0
        assert wf._steps[1].loop_back_to == "target_step"

    def test_synthetic_name_assigned_to_unnamed_target(self, save_dir):
        """If target step has no name, a synthetic name is assigned."""
        wf = _TestWorkflow(
            steps=[
                lambda x: x,  # unnamed target
                StepWrapper(
                    lambda x: x,
                    name="looper",
                    loop_back_to=0,  # integer target pointing to unnamed step
                    loop_condition=lambda state, result: False,
                ),
            ],
            save_dir=save_dir,
            max_expansion_events=1,
        )

        wf._resolve_integer_loop_back_to_targets()

        # loop_back_to should now be the synthetic name
        assert wf._steps[1].loop_back_to == "__step_0__"

    def test_string_loop_back_to_unchanged(self, save_dir):
        """String loop_back_to targets are not modified."""
        wf = _TestWorkflow(
            steps=[
                StepWrapper(lambda x: x, name="target_step"),
                StepWrapper(
                    lambda x: x,
                    name="looper",
                    loop_back_to="target_step",  # already a string
                    loop_condition=lambda state, result: False,
                ),
            ],
            save_dir=save_dir,
            max_expansion_events=1,
        )

        wf._resolve_integer_loop_back_to_targets()

        # Should remain unchanged
        assert wf._steps[1].loop_back_to == "target_step"
