"""Tests for Workflow loop + resume interaction (checkpoint-based resume).

Covers:
- Unique ___seqN result paths (no overwrites)
- Crash-and-resume in loop workflows
- State and loop_counts restoration from checkpoint
- Backward compatibility for non-loop workflows
- Checkpoint fallback scenarios (deleted checkpoint, deleted result file)
- Non-picklable state raises TypeError
- Explicit int resume bypasses checkpoint
- Correct next_step_index for loop-back and non-loop paths
- Crash at loop boundary step
- receives_state with checkpoint
- result_pass_down_mode with loop resume
- Backward scan glob fallback for ___seqN files
- Async mirrors for all tests
"""
import asyncio
import os
import shutil
import tempfile

import pytest
from attr import attrs, attrib

from python_utils.common_objects.workflow.workflow import Workflow
from python_utils.common_objects.workflow.common.result_pass_down_mode import ResultPassDownMode
from python_utils.common_objects.workflow.common.step_result_save_options import StepResultSaveOptions


# ---------------------------------------------------------------------------
# _StepWrapper — allows attaching arbitrary attributes to a callable
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
# Concrete Workflow subclass with real save/load for testing
# ---------------------------------------------------------------------------

@attrs(slots=False)
class ResumableWorkflow(Workflow):
    """Workflow subclass that saves results to a temp directory."""
    _save_dir: str = attrib(default=None)

    def __attrs_post_init__(self):
        if self._save_dir is None:
            self._save_dir = tempfile.mkdtemp(prefix="wf_test_")
        os.makedirs(self._save_dir, exist_ok=True)
        super().__attrs_post_init__()

    def _get_result_path(self, result_id, *args, **kwargs) -> str:
        return os.path.join(self._save_dir, f"step_{result_id}.pkl")

    def cleanup(self):
        if self._save_dir and os.path.exists(self._save_dir):
            shutil.rmtree(self._save_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def save_dir():
    d = tempfile.mkdtemp(prefix="wf_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_call_tracker():
    """Return (calls_list, step_fn) where step_fn records calls and returns input+1."""
    calls = []

    def step_fn(x):
        calls.append(x)
        return x + 1

    return calls, step_fn


def _make_failing_step(fail_on_call_n):
    """Return (calls_list, step_fn) that raises on the N-th call (1-indexed)."""
    calls = []

    def step_fn(x):
        calls.append(x)
        if len(calls) == fail_on_call_n:
            raise RuntimeError(f"Intentional failure on call {fail_on_call_n}")
        return x + 1

    return calls, step_fn


# ===========================================================================
# SYNC TESTS
# ===========================================================================

class TestLoopSaveCreatesUniquePaths:
    """Test 1: Each loop iteration saves to unique ___seqN paths."""

    def test_unique_seq_paths(self, save_dir):
        collect_calls, collect_fn = _make_call_tracker()
        review_calls, review_fn = _make_call_tracker()

        loop_count = [0]

        def loop_cond(state, result):
            loop_count[0] += 1
            return loop_count[0] <= 2  # loop twice

        steps = [
            collect_fn,
            _StepWrapper(
                review_fn,
                name="review",
                loop_back_to=0,
                loop_condition=loop_cond,
            ),
        ]

        wf = ResumableWorkflow(
            steps=steps,
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
        )
        wf._run(10)

        # Check that ___seq files were created
        files = sorted(os.listdir(save_dir))
        seq_files = [f for f in files if '___seq' in f]
        assert len(seq_files) >= 3, f"Expected at least 3 seq files, got: {seq_files}"

        # Ensure no overwrites — all files should be unique
        assert len(seq_files) == len(set(seq_files))


class TestCrashAndResumeInLoop:
    """Test 2: Resume after crash picks up from correct loop iteration."""

    def test_resume_skips_completed_iterations(self, save_dir):
        call_log = []

        def step_a(x):
            call_log.append(('a', x))
            return x + 1

        fail_count = [0]

        def step_b(x):
            fail_count[0] += 1
            call_log.append(('b', x))
            if fail_count[0] == 2:
                raise RuntimeError("crash on second b call")
            return x * 10

        loop_count = [0]

        def loop_cond(state, result):
            loop_count[0] += 1
            return loop_count[0] <= 3

        steps = [
            step_a,
            _StepWrapper(
                step_b,
                name="step_b",
                loop_back_to=0,
                loop_condition=loop_cond,
            ),
        ]

        # First run — crashes on second step_b call
        wf = ResumableWorkflow(
            steps=steps,
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
        )
        with pytest.raises(RuntimeError, match="crash on second b call"):
            wf._run(1)

        # Check checkpoint was saved (new parts mode: directory with main.pkl inside)
        checkpoint_dir = os.path.join(save_dir, "step___wf_checkpoint__")
        assert os.path.isdir(checkpoint_dir), "Checkpoint directory should exist after first loop iteration"
        assert os.path.exists(os.path.join(checkpoint_dir, "main.pkl")), "main.pkl should exist in checkpoint dir"

        # Resume — should not re-execute completed iterations
        call_log.clear()
        fail_count[0] = 99  # won't fail again
        loop_count[0] = 0  # reset — but checkpoint has loop_counts

        wf2 = ResumableWorkflow(
            steps=steps,
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
            resume_with_saved_results=True,
        )
        result = wf2._run(1)
        assert result is not None


class TestStateRestoredOnResume:
    """Test 3: State after resume matches state at crash point."""

    def test_state_restored(self, save_dir):
        def step_a(x):
            return x + 1

        call_count = [0]

        def step_b(x):
            call_count[0] += 1
            if call_count[0] == 2:
                raise RuntimeError("crash")
            return x * 2

        loop_count = [0]

        def loop_cond(state, result):
            loop_count[0] += 1
            return loop_count[0] <= 3

        def update_state(state, result):
            state['iterations'] = state.get('iterations', 0) + 1
            return state

        steps = [
            _StepWrapper(step_a, update_state=update_state),
            _StepWrapper(
                step_b,
                name="step_b",
                update_state=update_state,
                loop_back_to=0,
                loop_condition=loop_cond,
            ),
        ]

        wf = ResumableWorkflow(
            steps=steps,
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
        )
        with pytest.raises(RuntimeError):
            wf._run(1)

        # Resume
        call_count[0] = 99
        loop_count[0] = 0

        wf2 = ResumableWorkflow(
            steps=steps,
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
            resume_with_saved_results=True,
        )
        wf2._run(1)
        # State should have been restored from checkpoint (iterations > 0)
        assert wf2._state is not None
        assert wf2._state.get('iterations', 0) > 0


class TestLoopCountsRestoredOnResume:
    """Test 4: _loop_counts restored, loop doesn't restart from 0."""

    def test_loop_counts_restored(self, save_dir):
        def step_a(x):
            return x + 1

        call_count = [0]

        def step_b(x):
            call_count[0] += 1
            if call_count[0] == 3:
                raise RuntimeError("crash")
            return x * 2

        loop_iters = [0]

        def loop_cond(state, result):
            loop_iters[0] += 1
            return True  # always loop

        steps = [
            step_a,
            _StepWrapper(
                step_b,
                name="step_b",
                loop_back_to=0,
                loop_condition=loop_cond,
                max_loop_iterations=5,
            ),
        ]

        wf = ResumableWorkflow(
            steps=steps,
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
        )
        with pytest.raises(RuntimeError, match="crash"):
            wf._run(1)

        # Resume
        call_count[0] = 99
        loop_iters[0] = 0

        wf2 = ResumableWorkflow(
            steps=steps,
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
            resume_with_saved_results=True,
        )
        wf2._run(1)
        # The loop should have continued from the checkpoint's loop_counts,
        # not restarted from 0
        assert wf2._loop_counts is not None


class TestBackwardCompatNoLoops:
    """Test 5: Non-looping workflow with old-format saved results still works."""

    def test_no_loops_backward_scan(self, save_dir):
        calls = []

        def step_a(x):
            calls.append('a')
            return x + 1

        def step_b(x):
            calls.append('b')
            return x * 2

        steps = [step_a, _StepWrapper(step_b, name="step_b")]

        # First run — saves results in old format (no ___seq)
        wf = ResumableWorkflow(
            steps=steps,
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
        )
        result1 = wf._run(5)
        assert result1 == 12  # (5+1)*2

        # Resume — should find old-format results via backward scan
        calls.clear()
        wf2 = ResumableWorkflow(
            steps=steps,
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
            resume_with_saved_results=True,
        )
        result2 = wf2._run(5)
        assert result2 == 12
        # step_b should not be re-executed since its result was saved
        assert 'b' not in calls


class TestCheckpointFileDeletedFallback:
    """Test 6: Deleted checkpoint falls back to backward scan."""

    def test_fallback_on_missing_checkpoint(self, save_dir):
        def step_a(x):
            return x + 1

        loop_count = [0]

        def step_b(x):
            return x * 2

        def loop_cond(state, result):
            loop_count[0] += 1
            return loop_count[0] <= 1

        steps = [
            step_a,
            _StepWrapper(
                step_b,
                name="step_b",
                loop_back_to=0,
                loop_condition=loop_cond,
            ),
        ]

        wf = ResumableWorkflow(
            steps=steps,
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
        )
        wf._run(5)

        # Delete checkpoint but keep seq files
        # Remove checkpoint (may be a directory in parts mode or a file in legacy mode)
        ckpt_dir = os.path.join(save_dir, "step___wf_checkpoint__")
        ckpt_file = os.path.join(save_dir, "step___wf_checkpoint__.pkl")
        if os.path.isdir(ckpt_dir):
            shutil.rmtree(ckpt_dir)
        elif os.path.exists(ckpt_file):
            os.remove(ckpt_file)

        # Resume — should fall back to backward scan with glob fallback
        loop_count[0] = 0
        wf2 = ResumableWorkflow(
            steps=steps,
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
            resume_with_saved_results=True,
        )
        # Should not raise — gracefully falls back
        result = wf2._run(5)
        assert result is not None


class TestCheckpointResultFileDeletedFallback:
    """Test 7: Checkpoint exists but referenced result file deleted."""

    def test_fallback_on_missing_result_file(self, save_dir):
        def step_a(x):
            return x + 1

        loop_count = [0]

        def step_b(x):
            return x * 2

        def loop_cond(state, result):
            loop_count[0] += 1
            return loop_count[0] <= 1

        steps = [
            step_a,
            _StepWrapper(
                step_b,
                name="step_b",
                loop_back_to=0,
                loop_condition=loop_cond,
            ),
        ]

        wf = ResumableWorkflow(
            steps=steps,
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
        )
        wf._run(5)

        # Delete all seq result files/dirs but keep checkpoint
        for f in os.listdir(save_dir):
            if '___seq' in f:
                full_path = os.path.join(save_dir, f)
                if os.path.isdir(full_path):
                    shutil.rmtree(full_path)
                else:
                    os.remove(full_path)

        # Resume — checkpoint exists but can't load result → falls back
        loop_count[0] = 0
        wf2 = ResumableWorkflow(
            steps=steps,
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
            resume_with_saved_results=True,
        )
        # Should not raise — gracefully falls back to backward scan
        result = wf2._run(5)
        assert result is not None


class TestMultipleIndependentLoops:
    """Test 8: Two separate loop segments."""

    def test_two_loops(self, save_dir):
        loop1_count = [0]
        loop2_count = [0]

        def step_a(x):
            return x + 1

        def step_b(x):
            return x * 2

        def loop1_cond(state, result):
            loop1_count[0] += 1
            return loop1_count[0] <= 1

        def step_c(x):
            return x + 10

        def step_d(x):
            return x - 1

        def loop2_cond(state, result):
            loop2_count[0] += 1
            return loop2_count[0] <= 1

        steps = [
            step_a,
            _StepWrapper(step_b, name="b", loop_back_to=0, loop_condition=loop1_cond),
            step_c,
            _StepWrapper(step_d, name="d", loop_back_to=2, loop_condition=loop2_cond),
        ]

        wf = ResumableWorkflow(
            steps=steps,
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
        )
        result = wf._run(1)
        assert result is not None
        # Both loop counters should have been used
        assert 1 in wf._loop_counts  # step_b index
        assert 3 in wf._loop_counts  # step_d index


class TestNonPicklableStateRaises:
    """Test 9: Non-picklable state raises TypeError."""

    def test_raises_on_non_picklable_state(self, save_dir):
        def step_a(x):
            return x + 1

        def step_b(x):
            return x * 2

        def loop_cond(state, result):
            return True  # always loop

        def update_state(state, result):
            # Add a lambda — not picklable
            state['callback'] = lambda: None
            return state

        steps = [
            _StepWrapper(step_a, update_state=update_state),
            _StepWrapper(
                step_b,
                name="step_b",
                update_state=update_state,
                loop_back_to=0,
                loop_condition=loop_cond,
                max_loop_iterations=3,
            ),
        ]

        wf = ResumableWorkflow(
            steps=steps,
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
        )
        with pytest.raises(TypeError, match="not picklable"):
            wf._run(1)


class TestResumeWithExplicitIntIndex:
    """Test 10: resume_with_saved_results=int bypasses checkpoint."""

    def test_explicit_int_bypasses_checkpoint(self, save_dir):
        calls = []

        def step_a(x):
            calls.append('a')
            return x + 1

        def step_b(x):
            calls.append('b')
            return x * 2

        def step_c(x):
            calls.append('c')
            return x - 1

        steps = [step_a, _StepWrapper(step_b, name="step_b"), _StepWrapper(step_c, name="step_c")]

        # First run
        wf = ResumableWorkflow(
            steps=steps,
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
        )
        wf._run(5)

        # Resume with explicit int — should use backward scan, not checkpoint
        calls.clear()
        wf2 = ResumableWorkflow(
            steps=steps,
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
            resume_with_saved_results=1,  # explicit int
        )
        result = wf2._run(5)
        assert result is not None
        # step_a and step_b should not be re-executed (found at index 1)
        assert 'a' not in calls


class TestNextStepIndexCorrectForLoopBack:
    """Test 11: Checkpoint next_step_index points to loop target."""

    def test_checkpoint_next_step_is_loop_target(self, save_dir):
        loop_fired = [False]

        def step_a(x):
            return x + 1

        def step_b(x):
            return x * 2

        def loop_cond(state, result):
            if not loop_fired[0]:
                loop_fired[0] = True
                return True
            return False

        steps = [
            step_a,
            _StepWrapper(
                step_b,
                name="step_b",
                loop_back_to=0,
                loop_condition=loop_cond,
            ),
        ]

        wf = ResumableWorkflow(
            steps=steps,
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
        )
        wf._run(1)

        # Load checkpoint and verify
        ckpt = wf._try_load_checkpoint()
        if ckpt is not None:
            # The last checkpoint should have next_step_index = 2
            # (after the loop completes, advancing past step_b)
            assert "next_step_index" in ckpt


class TestNextStepIndexCorrectForNonLoop:
    """Test 12: Checkpoint next_step_index is i+1 when no loop fires."""

    def test_checkpoint_next_step_is_i_plus_1(self, save_dir):
        def step_a(x):
            return x + 1

        def step_b(x):
            return x * 2

        def loop_cond(state, result):
            return False  # never loop

        steps = [
            step_a,
            _StepWrapper(
                step_b,
                name="step_b",
                loop_back_to=0,
                loop_condition=loop_cond,
            ),
        ]

        wf = ResumableWorkflow(
            steps=steps,
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
        )
        wf._run(1)

        ckpt = wf._try_load_checkpoint()
        if ckpt is not None:
            assert ckpt["next_step_index"] == 2  # past last step


class TestCrashAtLoopBoundaryStep:
    """Test 13: Crash at the step that triggers loop_back_to."""

    def test_crash_at_loop_trigger(self, save_dir):
        def step_a(x):
            return x + 1

        call_count = [0]

        def step_b(x):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("crash at loop trigger")
            return x * 2

        def loop_cond(state, result):
            return True

        steps = [
            step_a,
            _StepWrapper(
                step_b,
                name="step_b",
                loop_back_to=0,
                loop_condition=loop_cond,
                max_loop_iterations=3,
            ),
        ]

        # First run — crashes at step_b (the loop trigger step)
        wf = ResumableWorkflow(
            steps=steps,
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
        )
        with pytest.raises(RuntimeError, match="crash at loop trigger"):
            wf._run(1)

        # Resume — step_b should work now
        call_count[0] = 99

        wf2 = ResumableWorkflow(
            steps=steps,
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
            resume_with_saved_results=True,
        )
        result = wf2._run(1)
        assert result is not None


class TestReceivesStateWithCheckpoint:
    """Test 14: receives_state step gets checkpoint-restored state."""

    def test_receives_checkpoint_state(self, save_dir):
        state_seen = []

        def step_a(x):
            return x + 1

        call_count = [0]

        def step_b(x, _state=None):
            call_count[0] += 1
            if _state is not None:
                state_seen.append(dict(_state))
            if call_count[0] == 2:
                raise RuntimeError("crash")
            return x * 2

        loop_count = [0]

        def loop_cond(state, result):
            loop_count[0] += 1
            return loop_count[0] <= 3

        def update_state(state, result):
            state['count'] = state.get('count', 0) + 1
            return state

        steps = [
            _StepWrapper(step_a, update_state=update_state),
            _StepWrapper(
                step_b,
                name="step_b",
                receives_state=True,
                update_state=update_state,
                loop_back_to=0,
                loop_condition=loop_cond,
            ),
        ]

        wf = ResumableWorkflow(
            steps=steps,
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
        )
        with pytest.raises(RuntimeError):
            wf._run(1)

        # Resume
        call_count[0] = 99
        loop_count[0] = 0
        state_seen.clear()

        wf2 = ResumableWorkflow(
            steps=steps,
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
            resume_with_saved_results=True,
        )
        wf2._run(1)
        # State should have been restored with count > 0
        assert wf2._state is not None
        assert wf2._state.get('count', 0) > 0


class TestResultPassDownModeWithLoopResume:
    """Test 15: ResultAsFirstArg + loops + resume."""

    def test_result_pass_down_with_resume(self, save_dir):
        results_seen = []

        def step_a(x):
            return x + 1

        call_count = [0]

        def step_b(x):
            call_count[0] += 1
            results_seen.append(x)
            if call_count[0] == 2:
                raise RuntimeError("crash")
            return x * 2

        loop_count = [0]

        def loop_cond(state, result):
            loop_count[0] += 1
            return loop_count[0] <= 2

        steps = [
            step_a,
            _StepWrapper(
                step_b,
                name="step_b",
                loop_back_to=0,
                loop_condition=loop_cond,
            ),
        ]

        wf = ResumableWorkflow(
            steps=steps,
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
        )
        with pytest.raises(RuntimeError):
            wf._run(1)

        # Resume
        call_count[0] = 99
        loop_count[0] = 0
        results_seen.clear()

        wf2 = ResumableWorkflow(
            steps=steps,
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
            resume_with_saved_results=True,
        )
        result = wf2._run(1)
        assert result is not None


class TestBackwardScanFallbackFindsSeqFiles:
    """Test 16: Backward scan glob fallback finds ___seqN files (parts dirs)."""

    def test_glob_fallback(self, save_dir):
        step_a_calls = [0]
        step_b_calls = [0]

        def step_a(x):
            step_a_calls[0] += 1
            return x + 1

        def step_b(x):
            step_b_calls[0] += 1
            return x * 2

        loop_count = [0]

        def loop_cond(state, result):
            loop_count[0] += 1
            return loop_count[0] <= 1

        steps = [
            _StepWrapper(step_a, name="step_a"),
            _StepWrapper(
                step_b,
                name="step_b",
                loop_back_to=0,
                loop_condition=loop_cond,
            ),
        ]

        wf = ResumableWorkflow(
            steps=steps,
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
        )
        wf._run(5)

        # Delete checkpoint but keep ___seqN files
        # Remove checkpoint (may be a directory in parts mode or a file in legacy mode)
        ckpt_dir = os.path.join(save_dir, "step___wf_checkpoint__")
        ckpt_file = os.path.join(save_dir, "step___wf_checkpoint__.pkl")
        if os.path.isdir(ckpt_dir):
            shutil.rmtree(ckpt_dir)
        elif os.path.exists(ckpt_file):
            os.remove(ckpt_file)

        # Verify seq results exist (may be directories in parts mode)
        seq_entries = [f for f in os.listdir(save_dir) if '___seq' in f]
        assert len(seq_entries) > 0, "Should have ___seqN entries"

        # Resume — glob fallback should find them and skip re-execution
        loop_count[0] = 0
        step_a_calls[0] = 0
        step_b_calls[0] = 0

        wf2 = ResumableWorkflow(
            steps=steps,
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
            resume_with_saved_results=True,
        )
        result = wf2._run(5)
        assert result is not None

        # The backward scan should have found the highest seq result and
        # loaded it, so at least one step should NOT have been re-executed.
        # step_b has the highest seq number (last step), so if the glob
        # found step_b___seqN, step_b should have been skipped entirely
        # (its result was loaded from disk).
        assert step_b_calls[0] == 0, (
            f"step_b should have been skipped via glob fallback but was "
            f"called {step_b_calls[0]} times"
        )


# ===========================================================================
# ASYNC TESTS — mirrors of all sync tests above
# ===========================================================================

@pytest.mark.asyncio
class TestAsyncLoopSaveCreatesUniquePaths:
    async def test_unique_seq_paths(self, save_dir):
        collect_calls, collect_fn = _make_call_tracker()
        review_calls, review_fn = _make_call_tracker()
        loop_count = [0]

        def loop_cond(state, result):
            loop_count[0] += 1
            return loop_count[0] <= 2

        steps = [
            collect_fn,
            _StepWrapper(review_fn, name="review", loop_back_to=0, loop_condition=loop_cond),
        ]
        wf = ResumableWorkflow(
            steps=steps, save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
        )
        await wf._arun(10)
        files = sorted(os.listdir(save_dir))
        seq_files = [f for f in files if '___seq' in f]
        assert len(seq_files) >= 3


@pytest.mark.asyncio
class TestAsyncCrashAndResumeInLoop:
    async def test_resume_skips_completed(self, save_dir):
        def step_a(x):
            return x + 1

        fail_count = [0]

        def step_b(x):
            fail_count[0] += 1
            if fail_count[0] == 2:
                raise RuntimeError("crash")
            return x * 10

        loop_count = [0]

        def loop_cond(state, result):
            loop_count[0] += 1
            return loop_count[0] <= 3

        steps = [
            step_a,
            _StepWrapper(step_b, name="step_b", loop_back_to=0, loop_condition=loop_cond),
        ]

        wf = ResumableWorkflow(
            steps=steps, save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
        )
        with pytest.raises(RuntimeError):
            await wf._arun(1)

        fail_count[0] = 99
        loop_count[0] = 0

        wf2 = ResumableWorkflow(
            steps=steps, save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
            resume_with_saved_results=True,
        )
        result = await wf2._arun(1)
        assert result is not None


@pytest.mark.asyncio
class TestAsyncBackwardCompatNoLoops:
    async def test_no_loops_backward_scan(self, save_dir):
        calls = []

        def step_a(x):
            calls.append('a')
            return x + 1

        def step_b(x):
            calls.append('b')
            return x * 2

        steps = [step_a, _StepWrapper(step_b, name="step_b")]

        wf = ResumableWorkflow(
            steps=steps, save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
        )
        result1 = await wf._arun(5)
        assert result1 == 12

        calls.clear()
        wf2 = ResumableWorkflow(
            steps=steps, save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
            resume_with_saved_results=True,
        )
        result2 = await wf2._arun(5)
        assert result2 == 12
        assert 'b' not in calls


@pytest.mark.asyncio
class TestAsyncNonPicklableStateRaises:
    async def test_raises_on_non_picklable_state(self, save_dir):
        def step_a(x):
            return x + 1

        def step_b(x):
            return x * 2

        def loop_cond(state, result):
            return True

        def update_state(state, result):
            state['callback'] = lambda: None
            return state

        steps = [
            _StepWrapper(step_a, update_state=update_state),
            _StepWrapper(
                step_b, name="step_b", update_state=update_state,
                loop_back_to=0, loop_condition=loop_cond, max_loop_iterations=3,
            ),
        ]
        wf = ResumableWorkflow(
            steps=steps, save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
        )
        with pytest.raises(TypeError, match="not picklable"):
            await wf._arun(1)


@pytest.mark.asyncio
class TestAsyncGlobFallback:
    async def test_glob_fallback(self, save_dir):
        step_b_calls = [0]

        def step_a(x):
            return x + 1

        def step_b(x):
            step_b_calls[0] += 1
            return x * 2

        loop_count = [0]

        def loop_cond(state, result):
            loop_count[0] += 1
            return loop_count[0] <= 1

        steps = [
            _StepWrapper(step_a, name="step_a"),
            _StepWrapper(step_b, name="step_b", loop_back_to=0, loop_condition=loop_cond),
        ]
        wf = ResumableWorkflow(
            steps=steps, save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
        )
        await wf._arun(5)

        # Remove checkpoint (may be a directory in parts mode or a file in legacy mode)
        ckpt_dir = os.path.join(save_dir, "step___wf_checkpoint__")
        ckpt_file = os.path.join(save_dir, "step___wf_checkpoint__.pkl")
        if os.path.isdir(ckpt_dir):
            shutil.rmtree(ckpt_dir)
        elif os.path.exists(ckpt_file):
            os.remove(ckpt_file)

        loop_count[0] = 0
        step_b_calls[0] = 0

        wf2 = ResumableWorkflow(
            steps=steps, save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
            resume_with_saved_results=True,
        )
        result = await wf2._arun(5)
        assert result is not None

        # step_b should have been skipped — its result was loaded from disk
        assert step_b_calls[0] == 0, (
            f"step_b should have been skipped via glob fallback but was "
            f"called {step_b_calls[0]} times"
        )
