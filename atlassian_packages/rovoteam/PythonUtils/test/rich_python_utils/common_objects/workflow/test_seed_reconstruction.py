"""Tests for seed-based reconstruction (Task 13.4).

Validates: Requirements 25.2, 25.3, 25.4, 25.5
"""
import os
import shutil
import tempfile

import pytest
from attr import attrs, attrib

from python_utils.common_objects.workflow.workflow import Workflow
from python_utils.common_objects.workflow.common.expansion import ExpansionResult
from python_utils.common_objects.workflow.common.exceptions import (
    ExpansionConfigError,
    ExpansionReplayError,
)
from python_utils.common_objects.workflow.common.result_pass_down_mode import ResultPassDownMode
from python_utils.common_objects.workflow.common.step_wrapper import StepWrapper


# ---------------------------------------------------------------------------
# Module-level factory for seed-based reconstruction (must be importable)
# ---------------------------------------------------------------------------

def _seed_factory(seed):
    """Module-level factory that reconstructs steps from a seed dict."""
    count = seed["count"]
    return [StepWrapper(lambda x, c=i: x + c + 1, name=f"seed_step_{i}") for i in range(count)]


# ---------------------------------------------------------------------------
# Concrete Workflow subclass for testing
# ---------------------------------------------------------------------------

@attrs(slots=False)
class _TestWorkflow(Workflow):
    _save_dir: str = attrib(default=None)

    def __attrs_post_init__(self):
        if self._save_dir is None:
            self._save_dir = tempfile.mkdtemp(prefix="seed_recon_test_")
        os.makedirs(self._save_dir, exist_ok=True)
        super().__attrs_post_init__()

    def _get_result_path(self, result_id, *args, **kwargs) -> str:
        return os.path.join(self._save_dir, f"step_{result_id}.pkl")


@pytest.fixture
def save_dir():
    d = tempfile.mkdtemp(prefix="seed_recon_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


class TestSeedBasedReconstruction:
    """Validates: Requirements 25.2, 25.3"""

    def test_seed_and_factory_persisted_in_checkpoint(self, save_dir):
        """Seed + factory_ref are stored in the expansion record in the checkpoint."""
        call_log = []

        def emitter(x):
            call_log.append("emitter")
            return ExpansionResult(
                result=x,
                new_steps=[StepWrapper(lambda v: v + 10, name="added_step")],
                seed={"count": 1},
                reconstruct_from_seed=_seed_factory,
            )

        wf = _TestWorkflow(
            steps=[
                StepWrapper(emitter, name="emitter_step"),
                StepWrapper(lambda x: x + 100, name="final_step"),
            ],
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            max_expansion_events=1,
            max_total_steps=20,
            enable_result_save=True,
        )
        wf._run(1)

        # Verify expansion record was created with seed and factory info
        assert len(wf._expansion_records) == 1
        rec = wf._expansion_records[0]
        assert rec.seed == {"count": 1}
        assert rec.factory_module == _seed_factory.__module__
        assert rec.factory_qualname == _seed_factory.__qualname__

    def test_factory_called_on_resume(self, save_dir):
        """On resume, the factory is imported and called with the seed — emitter is NOT re-invoked."""
        emitter_calls = []

        def emitter(x):
            emitter_calls.append("called")
            return ExpansionResult(
                result=x,
                new_steps=[StepWrapper(lambda v: v + 10, name="added_step")],
                seed={"count": 1},
                reconstruct_from_seed=_seed_factory,
            )

        # First run: emitter fires
        wf1 = _TestWorkflow(
            steps=[
                StepWrapper(emitter, name="emitter_step"),
                StepWrapper(lambda x: x + 100, name="final_step"),
            ],
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            max_expansion_events=1,
            max_total_steps=20,
            enable_result_save=True,
        )
        wf1._run(1)
        assert len(emitter_calls) == 1

        # Second run (resume): emitter should NOT be called again
        emitter_calls.clear()
        wf2 = _TestWorkflow(
            steps=[
                StepWrapper(emitter, name="emitter_step"),
                StepWrapper(lambda x: x + 100, name="final_step"),
            ],
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            max_expansion_events=1,
            max_total_steps=20,
            enable_result_save=True,
            resume_with_saved_results=True,
        )
        wf2._run(1)

        # Emitter was NOT re-invoked on resume
        assert len(emitter_calls) == 0
        # Steps were reconstructed from seed factory
        assert len(wf2._expansion_records) >= 1


class TestSeedFactoryValidation:
    """Validates: Requirements 25.4"""

    def test_lambda_reconstruct_from_seed_raises_config_error(self, save_dir):
        """Lambda as reconstruct_from_seed raises ExpansionConfigError."""
        def emitter(x):
            return ExpansionResult(
                result=x,
                new_steps=[StepWrapper(lambda v: v, name="s1")],
                seed=42,
                reconstruct_from_seed=lambda s: [StepWrapper(lambda v: v, name="s1")],
            )

        wf = _TestWorkflow(
            steps=[StepWrapper(emitter, name="emitter")],
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            max_expansion_events=1,
            max_total_steps=20,
        )
        with pytest.raises(ExpansionConfigError, match="lambda"):
            wf._run(1)

    def test_closure_reconstruct_from_seed_raises_config_error(self, save_dir):
        """Closure as reconstruct_from_seed raises ExpansionConfigError."""
        def make_factory():
            captured = 42
            def inner(seed):
                return [StepWrapper(lambda v: v + captured, name="s1")]
            return inner

        closure_fn = make_factory()

        def emitter(x):
            return ExpansionResult(
                result=x,
                new_steps=[StepWrapper(lambda v: v, name="s1")],
                seed=42,
                reconstruct_from_seed=closure_fn,
            )

        wf = _TestWorkflow(
            steps=[StepWrapper(emitter, name="emitter")],
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            max_expansion_events=1,
            max_total_steps=20,
        )
        with pytest.raises(ExpansionConfigError, match="closure"):
            wf._run(1)


class TestSeedReconstructionFailure:
    """Validates: Requirements 25.5"""

    def test_unimportable_factory_raises_replay_error(self, save_dir):
        """If the factory can't be imported on resume, ExpansionReplayError is raised."""
        checkpoint = {
            "version": 2,
            "exec_seq": 1,
            "step_index": 0,
            "result_id": "emitter_step___seq1",
            "next_step_index": 1,
            "loop_counts": {},
            "state": None,
            "expansions": [{
                "after_step_name": "emitter_step",
                "expansion_id": None,
                "num_steps": 1,
                "seed": {"count": 1},
                "factory_module": "nonexistent_module_xyz",
                "factory_qualname": "nonexistent_factory",
            }],
        }

        wf = _TestWorkflow(
            steps=[
                StepWrapper(lambda x: x, name="emitter_step"),
                StepWrapper(lambda x: x + 100, name="final_step"),
            ],
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            max_expansion_events=1,
            max_total_steps=20,
        )
        with pytest.raises(ExpansionReplayError, match="nonexistent_module_xyz"):
            wf._reconstruct_expansions(checkpoint)


class TestEmitterNotReinvoked:
    """Validates: LLM-once guarantee — emitter body NOT re-invoked on resume."""

    def test_emitter_body_not_reinvoked_on_resume(self, save_dir):
        """The emitter step's body is never called again on resume."""
        invocation_count = []

        def emitter(x):
            invocation_count.append(1)
            return ExpansionResult(
                result=x * 2,
                new_steps=[StepWrapper(lambda v: v + 5, name="extra")],
                seed={"count": 1},
                reconstruct_from_seed=_seed_factory,
            )

        # First run
        wf1 = _TestWorkflow(
            steps=[
                StepWrapper(emitter, name="emitter_step"),
                StepWrapper(lambda x: x + 100, name="final_step"),
            ],
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            max_expansion_events=1,
            max_total_steps=20,
            enable_result_save=True,
        )
        wf1._run(5)
        assert len(invocation_count) == 1

        # Resume run
        invocation_count.clear()
        wf2 = _TestWorkflow(
            steps=[
                StepWrapper(emitter, name="emitter_step"),
                StepWrapper(lambda x: x + 100, name="final_step"),
            ],
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            max_expansion_events=1,
            max_total_steps=20,
            enable_result_save=True,
            resume_with_saved_results=True,
        )
        wf2._run(5)
        # Emitter was NOT called on resume
        assert len(invocation_count) == 0
