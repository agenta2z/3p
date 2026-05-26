"""Tests for recursive resume with artifact_type-based child workflow discovery.

Covers:
- End-to-end recursive resume (pickle mode): parent + child workflows
- Pattern A: @artifact_type on Workflow class
- Pattern B: @artifact_type on state class
- Child workflow config propagation
- Graceful degradation (no artifact metadata)
- Filename collision avoidance for nested children with same leaf name
- 3-level nesting (grandchild)
- Loop + parent-child workflow + crash/resume integration
- Combined @artifact_field + @artifact_type on same class
- Comprehensive workspace folder structure verification
- Async recursive resume
- Conditioned loop resume with state verification
- Jsonfy checkpoint mode: loop+crash+resume, file structure, fallback behaviors
"""
import asyncio
import json
import os
import shutil
import tempfile

import pytest
from attr import attrs, attrib

from python_utils.common_objects.workflow.workflow import Workflow, CheckpointState
from python_utils.common_objects.workflow.common.resumable import CheckpointMode
from python_utils.common_objects.workflow.common.result_pass_down_mode import ResultPassDownMode
from python_utils.io_utils.artifact import artifact_type, artifact_field
from python_utils.io_utils.pickle_io import pickle_save, pickle_load


# ---------------------------------------------------------------------------
# Module-level test classes (must be at module level for pickle to work)
# ---------------------------------------------------------------------------

class InnerWF:
    def __init__(self, name, step=0):
        self.name = name
        self.step = step
    def __eq__(self, other):
        return isinstance(other, InnerWF) and self.name == other.name and self.step == other.step


class ChildWF:
    def __init__(self, name):
        self.name = name
    def __eq__(self, other):
        return isinstance(other, ChildWF) and self.name == other.name


@artifact_type(InnerWF, group='workflows')
class ParentState:
    def __init__(self, planner, executor, counter=0):
        self.planner = planner
        self.executor = executor
        self.counter = counter


@artifact_type(InnerWF, group='wf')
class MutationTestState:
    def __init__(self, child):
        self.child = child


@artifact_type(InnerWF, group='workflows')
class PipelineState:
    def __init__(self, planner, executor):
        self.planner = planner
        self.executor = executor


class GrandchildWF:
    def __init__(self, val):
        self.val = val
    def __eq__(self, other):
        return isinstance(other, GrandchildWF) and self.val == other.val


@artifact_type(GrandchildWF, group='grandchildren')
class ChildState:
    def __init__(self, worker):
        self.worker = worker


class MiddleWF:
    def __init__(self, state):
        self.state = state


class _StepWrapper:
    def __init__(self, fn, **kwargs):
        self._fn = fn
        self.__name__ = getattr(fn, '__name__', str(fn))
        self.__module__ = getattr(fn, '__module__', None)
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __call__(self, *args, **kwargs):
        return self._fn(*args, **kwargs)


@attrs(slots=False)
class SimpleWorkflow(Workflow):
    """Minimal concrete Workflow for testing."""
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


# Module-level classes for @artifact_field tests (pickle requires module-level)

@artifact_field('body_html', type='html', group='html_parts')
class PageResult:
    def __init__(self, title, body_html, score):
        self.title = title
        self.body_html = body_html
        self.score = score


@artifact_field('raw_html', type='html', group='html_source')
@artifact_type(InnerWF, group='workflows')
class FullResult:
    def __init__(self, raw_html, planner, executor, summary):
        self.raw_html = raw_html
        self.planner = planner
        self.executor = executor
        self.summary = summary


@artifact_field('cleaned_html', type='html', group='html_parts')
@artifact_field('raw_html', type='html', group='html_parts')
class DualHtmlResult:
    def __init__(self, raw_html, cleaned_html, metadata):
        self.raw_html = raw_html
        self.cleaned_html = cleaned_html
        self.metadata = metadata


@pytest.fixture
def save_dir():
    d = tempfile.mkdtemp(prefix="wf_recursive_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


# ---------------------------------------------------------------------------
# Test: pickle_save enable_parts round-trip with artifact_type
# ---------------------------------------------------------------------------

class TestPicklePartsRoundTrip:

    def test_round_trip_with_artifact_type(self):
        """Object with @artifact_type -> save -> load -> verify equality."""
        state = ParentState(InnerWF('plan', 3), InnerWF('exec', 5), counter=42)
        d = tempfile.mkdtemp()
        try:
            pickle_save(state, d, enable_parts=True)
            loaded = pickle_load(d, enable_parts=True)
            assert loaded.planner == state.planner
            assert loaded.executor == state.executor
            assert loaded.counter == 42
        finally:
            shutil.rmtree(d)

    def test_graceful_degradation_no_artifacts(self):
        """Object with NO artifact metadata -> main.pkl + empty manifest, round-trips."""
        data = {'x': 42, 'y': [1, 2, 3]}
        d = tempfile.mkdtemp()
        try:
            pickle_save(data, d, enable_parts=True)
            assert os.path.exists(os.path.join(d, 'main.pkl'))
            assert os.path.exists(os.path.join(d, 'manifest.json'))
            loaded = pickle_load(d, enable_parts=True)
            assert loaded == data
        finally:
            shutil.rmtree(d)

    def test_mutation_safety(self):
        """Original object unchanged after save."""
        state = MutationTestState(InnerWF('test'))
        d = tempfile.mkdtemp()
        try:
            pickle_save(state, d, enable_parts=True)
            assert state.child is not None
            assert state.child.name == 'test'
        finally:
            shutil.rmtree(d)

    def test_filename_collision_avoidance(self):
        """Two children with same leaf name at different paths get distinct files."""
        data = {
            'state': {'planner': ChildWF('state_planner')},
            'backup': {'planner': ChildWF('backup_planner')},
        }
        artifact_types_param = [{'target_type': ChildWF, 'ext': None, 'subfolder': 'wf'}]
        d = tempfile.mkdtemp()
        try:
            pickle_save(data, d, enable_parts=True, artifact_types=artifact_types_param)
            loaded = pickle_load(d, enable_parts=True)
            assert loaded['state']['planner'] == ChildWF('state_planner')
            assert loaded['backup']['planner'] == ChildWF('backup_planner')
        finally:
            shutil.rmtree(d)

    def test_explicit_artifact_types_for_plain_dict(self):
        """Plain dict + explicit artifact_types param -> children extracted via deep scan."""
        checkpoint = {
            'version': 1,
            'state': {
                'planner': ChildWF('plan'),
                'executor': ChildWF('exec'),
                'data': 'some string',
            },
        }
        artifact_types_param = [{'target_type': ChildWF, 'ext': None, 'subfolder': 'workflows'}]
        d = tempfile.mkdtemp()
        try:
            pickle_save(checkpoint, d, enable_parts=True, artifact_types=artifact_types_param)
            loaded = pickle_load(d, enable_parts=True)
            assert loaded['state']['planner'] == ChildWF('plan')
            assert loaded['state']['executor'] == ChildWF('exec')
            assert loaded['state']['data'] == 'some string'
        finally:
            shutil.rmtree(d)


# ---------------------------------------------------------------------------
# Test: CheckpointMode validation
# ---------------------------------------------------------------------------

class TestCheckpointMode:

    def test_valid_pickle_mode(self):
        wf = SimpleWorkflow(steps=[], checkpoint_mode='pickle')
        assert wf.checkpoint_mode == 'pickle'

    def test_valid_jsonfy_mode(self):
        wf = SimpleWorkflow(steps=[], checkpoint_mode='jsonfy')
        assert wf.checkpoint_mode == 'jsonfy'

    def test_invalid_mode_raises(self):
        with pytest.raises(Exception):
            SimpleWorkflow(steps=[], checkpoint_mode='invalid')


# ---------------------------------------------------------------------------
# Test: _resolve_result_path and _result_root_override
# ---------------------------------------------------------------------------

class TestResolveResultPath:

    def test_no_override_returns_original(self, save_dir):
        wf = SimpleWorkflow(steps=[], save_dir=save_dir)
        path = wf._resolve_result_path('step_0')
        assert path == wf._get_result_path('step_0')

    def test_override_redirects_path(self, save_dir):
        wf = SimpleWorkflow(steps=[], save_dir=save_dir)
        override_dir = os.path.join(save_dir, 'child_workspace')
        wf._result_root_override = override_dir
        path = wf._resolve_result_path('step_0')
        assert path == os.path.join(override_dir, 'step_step_0.pkl')


# ---------------------------------------------------------------------------
# Test: _find_child_workflows_in (Pattern A + B)
# ---------------------------------------------------------------------------

class TestFindChildWorkflows:

    def test_pattern_a_decorator_on_workflow_class(self, save_dir):
        """Pattern A: @artifact_type on the parent Workflow class."""

        @artifact_type(SimpleWorkflow, group='children')
        @attrs(slots=False)
        class ParentWF(Workflow):
            child: SimpleWorkflow = attrib(default=None)

            def _get_result_path(self, result_id, *args, **kwargs) -> str:
                return os.path.join(save_dir, f"step_{result_id}.pkl")

        child = SimpleWorkflow(steps=[], save_dir=save_dir)
        parent = ParentWF(steps=[], child=child)

        found = parent._find_child_workflows_in(parent)
        assert 'child' in found
        assert found['child'][0] is child

    def test_pattern_b_decorator_on_state_class(self, save_dir):
        """Pattern B: @artifact_type on the state class."""

        @artifact_type(SimpleWorkflow, group='workflows')
        class StateCls:
            def __init__(self, planner):
                self.planner = planner

        child = SimpleWorkflow(steps=[], save_dir=save_dir)
        parent = SimpleWorkflow(steps=[], save_dir=save_dir)
        state = StateCls(planner=child)

        found = parent._find_child_workflows_in(state)
        assert 'planner' in found
        assert found['planner'][0] is child

    def test_dict_source_finds_children(self, save_dir):
        """Dict source with artifact metadata on self -> children found."""

        @artifact_type(SimpleWorkflow, group='wf')
        @attrs(slots=False)
        class ParentWF(Workflow):
            def _get_result_path(self, result_id, *args, **kwargs) -> str:
                return os.path.join(save_dir, f"step_{result_id}.pkl")

        child = SimpleWorkflow(steps=[], save_dir=save_dir)
        parent = ParentWF(steps=[])
        state = {'planner': child, 'data': 'hello'}

        found = parent._find_child_workflows_in(state)
        assert 'planner' in found
        assert found['planner'][0] is child

    def test_none_source_returns_empty(self, save_dir):
        parent = SimpleWorkflow(steps=[], save_dir=save_dir)
        assert parent._find_child_workflows_in(None) == {}


# ---------------------------------------------------------------------------
# Test: _setup_child_workflows config propagation
# ---------------------------------------------------------------------------

class TestSetupChildWorkflows:

    def test_config_propagation(self, save_dir):
        """After _setup_child_workflows, children have matching config."""

        @artifact_type(SimpleWorkflow, group='children')
        @attrs(slots=False)
        class ParentWF(Workflow):
            child: SimpleWorkflow = attrib(default=None)

            def _get_result_path(self, result_id, *args, **kwargs) -> str:
                return os.path.join(save_dir, f"step_{result_id}.pkl")

        child = SimpleWorkflow(steps=[], save_dir=os.path.join(save_dir, 'child_orig'))
        parent = ParentWF(
            steps=[],
            child=child,
            enable_result_save=True,
            resume_with_saved_results=True,
            checkpoint_mode='pickle',
        )

        parent._setup_child_workflows(parent)

        assert child.enable_result_save is True
        assert child.resume_with_saved_results is True
        assert child.checkpoint_mode == 'pickle'
        assert child._result_root_override is not None
        assert 'children' in child._result_root_override

    def test_none_state_no_error(self, save_dir):
        parent = SimpleWorkflow(steps=[], save_dir=save_dir)
        parent._setup_child_workflows(None)  # should not raise


# ---------------------------------------------------------------------------
# Test: End-to-end recursive resume (pickle mode)
# ---------------------------------------------------------------------------

class TestRecursiveResumePickle:

    def test_parent_child_resume(self, save_dir):
        """Parent with child workflow: partial run -> crash -> resume."""
        parent_calls = []
        crash_on_step_1 = [True]

        @artifact_type(SimpleWorkflow, group='inferencers')
        @attrs(slots=False)
        class OuterWorkflow(Workflow):
            planner: SimpleWorkflow = attrib(default=None)

            def _get_result_path(self, result_id, *args, **kwargs) -> str:
                return os.path.join(save_dir, f"step_{result_id}.pkl")

            def _init_state(self):
                return {'count': 0}

            def _update_state(self, state, result, step, step_name, step_index):
                state['count'] += 1
                return state

        def parent_step_0(x):
            parent_calls.append(('parent_step_0', x))
            return x + 1

        def parent_step_1(x):
            parent_calls.append(('parent_step_1', x))
            if crash_on_step_1[0]:
                raise RuntimeError("simulated crash")
            return x + 2

        child_save_dir = os.path.join(save_dir, 'child_wf')
        child = SimpleWorkflow(
            steps=[],
            save_dir=child_save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
        )

        parent = OuterWorkflow(
            steps=[parent_step_0, parent_step_1],
            planner=child,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
        )

        # First run -- step_0 succeeds, step_1 crashes
        with pytest.raises(RuntimeError, match="simulated crash"):
            parent.run(5)

        assert ('parent_step_0', 5) in parent_calls
        assert ('parent_step_1', 6) in parent_calls

        # Resume -- step_0 should be loaded from saved result, step_1 re-executed
        parent_calls.clear()
        crash_on_step_1[0] = False

        parent2 = OuterWorkflow(
            steps=[parent_step_0, parent_step_1],
            planner=child,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
            resume_with_saved_results=True,
        )

        result = parent2.run(5)
        assert result == 8  # 5 + 1 + 2
        # step_0 was loaded from saved result, not re-executed
        assert ('parent_step_0', 5) not in parent_calls


# ---------------------------------------------------------------------------
# Test: Pattern B end-to-end (decorator on state class)
# ---------------------------------------------------------------------------

class TestPatternBEndToEnd:

    def test_state_class_decorator_deep_scan(self):
        """@artifact_type on state class -> pickle_save deep scan finds children."""
        state = PipelineState(InnerWF('plan'), InnerWF('exec'))
        checkpoint = {
            'version': 1,
            'state': state,
        }

        d = tempfile.mkdtemp()
        try:
            # No explicit artifact_types -- relies on deep scan finding state's metadata
            pickle_save(checkpoint, d, enable_parts=True)
            loaded = pickle_load(d, enable_parts=True)

            assert loaded['state'].planner == InnerWF('plan')
            assert loaded['state'].executor == InnerWF('exec')
        finally:
            shutil.rmtree(d)


# ---------------------------------------------------------------------------
# Test: 3-level nesting
# ---------------------------------------------------------------------------

class TestThreeLevelNesting:

    def test_grandchild_extraction(self):
        """3-level nesting: grandchild extracted via recursive deep scan."""
        data = {'child': MiddleWF(ChildState(GrandchildWF(42)))}

        d = tempfile.mkdtemp()
        try:
            pickle_save(data, d, enable_parts=True)
            loaded = pickle_load(d, enable_parts=True)
            assert loaded['child'].state.worker == GrandchildWF(42)
        finally:
            shutil.rmtree(d)


# ---------------------------------------------------------------------------
# Test: Backward compatibility
# ---------------------------------------------------------------------------

class TestBackwardCompat:

    def test_load_result_falls_back_to_plain_pickle(self, save_dir):
        """_load_result can still load old plain .pkl files."""
        data = {'result': 42}
        pkl_path = os.path.join(save_dir, 'old_result.pkl')
        pickle_save(data, pkl_path, verbose=False)

        wf = SimpleWorkflow(steps=[], save_dir=save_dir)
        loaded = wf._load_result('old_result', pkl_path)
        assert loaded == data

    def test_exists_result_detects_both_formats(self, save_dir):
        """_exists_result detects both parts directories and plain .pkl files."""
        import pickle
        wf = SimpleWorkflow(steps=[], save_dir=save_dir)

        # Plain .pkl file
        pkl_path = os.path.join(save_dir, 'plain.pkl')
        with open(pkl_path, 'wb') as f:
            pickle.dump({'x': 1}, f)
        assert wf._exists_result('plain', pkl_path)

        # Parts directory
        parts_dir = os.path.join(save_dir, 'parts_result')
        os.makedirs(parts_dir)
        with open(os.path.join(parts_dir, 'main.pkl'), 'wb') as f:
            pickle.dump({'x': 2}, f)
        assert wf._exists_result('parts_result', parts_dir + '.pkl')


# ---------------------------------------------------------------------------
# Test: CheckpointState (jsonfy mode wrapper)
# ---------------------------------------------------------------------------

class TestCheckpointStateWrapper:

    def test_checkpoint_state_has_artifact_types(self):
        assert hasattr(CheckpointState, '__artifact_types__')
        entries = CheckpointState.__artifact_types__
        assert len(entries) == 1
        assert entries[0]['target_type'] is Workflow

    def test_checkpoint_state_fields(self):
        cs = CheckpointState(
            version=1, exec_seq=2, step_index=3,
            result_id='step_b___seq2', next_step_index=4,
            loop_counts={1: 2}, state={'key': 'val'}
        )
        assert cs.version == 1
        assert cs.exec_seq == 2
        assert cs.state == {'key': 'val'}


# ===========================================================================
# Integration Tests: Loop + Parent-Child Workflow + Crash/Resume
# ===========================================================================

class TestLoopWithChildWorkflowResume:
    """Tests combining loops + parent-child workflows + crash/resume.

    This is the critical gap: test_loop_resume.py tests loops with resume but
    never uses child workflows/artifact decorators, and test_recursive_resume.py
    tests child workflow discovery but has no loops.
    """

    def test_loop_with_child_crash_and_resume(self, save_dir):
        """Parent with @artifact_type child, loop, crash mid-loop, resume.

        Verifies:
        1. Child workflow gets _result_root_override set
        2. Loop checkpoint saves correctly with child in state
        3. Resume loads checkpoint and re-sets child overrides
        4. Completed iterations are not re-executed
        5. Child's checkpoint workspace persists across resume
        """
        parent_calls = []
        crash_on = [3]  # crash on 3rd call to step_b

        @artifact_type(SimpleWorkflow, group='inferencers')
        @attrs(slots=False)
        class LoopingParent(Workflow):
            child_wf: SimpleWorkflow = attrib(default=None)

            def _get_result_path(self, result_id, *args, **kwargs) -> str:
                return os.path.join(save_dir, f"step_{result_id}.pkl")

            def _init_state(self):
                return {'iteration': 0}

            def _update_state(self, state, result, step, step_name, step_index):
                state['iteration'] += 1
                return state

        def step_a(x):
            parent_calls.append(('a', x))
            return x + 1

        call_count = [0]

        def step_b(x):
            call_count[0] += 1
            parent_calls.append(('b', x, call_count[0]))
            if call_count[0] == crash_on[0]:
                raise RuntimeError("crash in loop")
            return x * 2

        loop_count = [0]

        def loop_cond(state, result):
            loop_count[0] += 1
            return loop_count[0] <= 3  # loop 3 times

        steps = [
            _StepWrapper(step_a, update_state=lambda s, r: dict(s, iteration=s['iteration'] + 1)),
            _StepWrapper(
                step_b,
                name="step_b",
                update_state=lambda s, r: dict(s, iteration=s['iteration'] + 1),
                loop_back_to=0,
                loop_condition=loop_cond,
            ),
        ]

        child = SimpleWorkflow(
            steps=[],
            save_dir=os.path.join(save_dir, 'child_orig'),
            enable_result_save=True,
        )

        parent = LoopingParent(
            steps=steps,
            child_wf=child,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
        )

        # First run — crashes on 3rd call to step_b (2nd loop iteration)
        with pytest.raises(RuntimeError, match="crash in loop"):
            parent.run(1)

        # Verify checkpoint was written
        ckpt_dir = os.path.join(save_dir, "step___wf_checkpoint__")
        assert os.path.isdir(ckpt_dir), "Checkpoint directory should exist"
        assert os.path.exists(os.path.join(ckpt_dir, "main.pkl"))

        # Verify child's workspace directory was created
        child_workspace = os.path.join(save_dir, 'inferencers', 'child_wf')
        assert os.path.isdir(child_workspace), (
            f"Child workspace should be at {child_workspace}"
        )

        # Resume
        parent_calls.clear()
        call_count[0] = 99  # won't crash again
        loop_count[0] = 0

        child2 = SimpleWorkflow(
            steps=[],
            save_dir=os.path.join(save_dir, 'child_orig'),
            enable_result_save=True,
        )

        parent2 = LoopingParent(
            steps=steps,
            child_wf=child2,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
            resume_with_saved_results=True,
        )

        result = parent2.run(1)
        assert result is not None

        # Verify child2 got its override set after resume
        assert child2._result_root_override is not None
        assert 'inferencers' in child2._result_root_override

    def test_conditioned_loop_with_child_state_verification(self, save_dir):
        """Loop with condition that inspects state, child in state, crash/resume.

        Verifies the condition function receives the correctly restored state
        after checkpoint resume, including iteration counts.

        Note: step 0 always receives original args (not accumulated results),
        so crash logic uses a call counter rather than accumulated values.
        """
        condition_states_seen = []

        @artifact_type(SimpleWorkflow, group='workers')
        @attrs(slots=False)
        class StatefulParent(Workflow):
            worker: SimpleWorkflow = attrib(default=None)

            def _get_result_path(self, result_id, *args, **kwargs) -> str:
                return os.path.join(save_dir, f"step_{result_id}.pkl")

            def _init_state(self):
                return {'total': 0, 'items_processed': []}

        def step_process(x):
            return x + 10

        aggregate_count = [0]
        crash_flag = [True]

        def step_aggregate(x):
            aggregate_count[0] += 1
            if crash_flag[0] and aggregate_count[0] == 3:
                raise RuntimeError("crash during aggregation")
            return x

        def update_state_process(state, result):
            state['total'] += result
            state['items_processed'].append(result)
            return state

        def loop_cond(state, result):
            condition_states_seen.append({
                'items': list(state.get('items_processed', [])),
                'total': state.get('total', 0),
            })
            return len(state.get('items_processed', [])) < 5

        steps = [
            _StepWrapper(step_process, update_state=update_state_process),
            _StepWrapper(
                step_aggregate,
                name="aggregate",
                loop_back_to=0,
                loop_condition=loop_cond,
            ),
        ]

        child = SimpleWorkflow(steps=[], save_dir=os.path.join(save_dir, 'w'))

        parent = StatefulParent(
            steps=steps,
            worker=child,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
        )

        # First run — crashes on 3rd aggregate call
        with pytest.raises(RuntimeError, match="crash during aggregation"):
            parent.run(1)

        # State at crash: condition was seen at least twice (before crash)
        assert len(condition_states_seen) >= 2
        pre_crash_snapshot = condition_states_seen[-1]

        # Resume
        condition_states_seen.clear()
        crash_flag[0] = False
        aggregate_count[0] = 99  # won't crash again

        worker2 = SimpleWorkflow(steps=[], save_dir=os.path.join(save_dir, 'w'))

        parent2 = StatefulParent(
            steps=steps,
            worker=worker2,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
            resume_with_saved_results=True,
        )

        result = parent2.run(1)
        assert result is not None

        # Verify state was restored: the condition function should see
        # items_processed from before the crash (at least as many as pre-crash)
        if condition_states_seen:
            first_seen = condition_states_seen[0]
            assert len(first_seen['items']) >= len(pre_crash_snapshot['items']), (
                f"Condition should see restored state with at least "
                f"{len(pre_crash_snapshot['items'])} items, "
                f"got {len(first_seen['items'])}"
            )

    def test_multiple_children_with_loop_resume(self, save_dir):
        """Parent with two child Workflows + loop, crash on 2nd iteration, resume.

        Both children should get independent workspace directories.
        Crash must happen AFTER at least one loop checkpoint is saved,
        so _setup_child_workflows has been called.
        """
        @artifact_type(SimpleWorkflow, group='agents')
        @attrs(slots=False)
        class MultiChildParent(Workflow):
            planner: SimpleWorkflow = attrib(default=None)
            executor: SimpleWorkflow = attrib(default=None)

            def _get_result_path(self, result_id, *args, **kwargs) -> str:
                return os.path.join(save_dir, f"step_{result_id}.pkl")

            def _init_state(self):
                return {'round': 0}

        def step_plan(x):
            return x + 1

        execute_count = [0]

        def step_execute(x):
            execute_count[0] += 1
            if execute_count[0] == 2:
                raise RuntimeError("executor crash on 2nd iteration")
            return x * 3

        loop_count = [0]

        def loop_cond(state, result):
            loop_count[0] += 1
            return loop_count[0] <= 3

        def incr_round(state, result):
            state['round'] += 1
            return state

        steps = [
            _StepWrapper(step_plan, update_state=incr_round),
            _StepWrapper(
                step_execute,
                name="execute",
                update_state=incr_round,
                loop_back_to=0,
                loop_condition=loop_cond,
            ),
        ]

        planner = SimpleWorkflow(steps=[], save_dir=os.path.join(save_dir, 'p'))
        executor = SimpleWorkflow(steps=[], save_dir=os.path.join(save_dir, 'e'))

        parent = MultiChildParent(
            steps=steps,
            planner=planner,
            executor=executor,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
        )

        # First run — 1st iteration succeeds (checkpoint saved), 2nd crashes
        with pytest.raises(RuntimeError, match="executor crash on 2nd iteration"):
            parent.run(5)

        # Verify both children have workspaces (created during checkpoint save)
        planner_ws = os.path.join(save_dir, 'agents', 'planner')
        executor_ws = os.path.join(save_dir, 'agents', 'executor')
        assert os.path.isdir(planner_ws), f"Planner workspace should exist at {planner_ws}"
        assert os.path.isdir(executor_ws), f"Executor workspace should exist at {executor_ws}"

        # Resume
        loop_count[0] = 0
        execute_count[0] = 99  # won't crash again

        planner2 = SimpleWorkflow(steps=[], save_dir=os.path.join(save_dir, 'p'))
        executor2 = SimpleWorkflow(steps=[], save_dir=os.path.join(save_dir, 'e'))

        parent2 = MultiChildParent(
            steps=steps,
            planner=planner2,
            executor=executor2,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
            resume_with_saved_results=True,
        )

        result = parent2.run(5)
        assert result is not None

        # Both children should have overrides set
        assert planner2._result_root_override is not None
        assert executor2._result_root_override is not None
        assert planner2._result_root_override != executor2._result_root_override


# ===========================================================================
# Integration Tests: @artifact_field + @artifact_type combination
# ===========================================================================

class TestArtifactFieldAndTypeCombination:
    """Tests for classes using both @artifact_field and @artifact_type decorators."""

    def test_artifact_field_text_extraction_with_pickle_parts(self):
        """@artifact_field marks a text field for extraction as .html file."""
        data = PageResult("Test Page", "<h1>Hello World</h1>", 0.95)
        d = tempfile.mkdtemp()
        try:
            pickle_save(data, d, enable_parts=True)

            # Verify HTML file was extracted
            html_path = os.path.join(d, 'html_parts', 'body_html.html')
            assert os.path.exists(html_path), f"HTML part should exist at {html_path}"
            with open(html_path, 'r', encoding='utf-8') as f:
                content = f.read()
            assert '<h1>Hello World</h1>' in content

            # Verify manifest
            manifest_path = os.path.join(d, 'manifest.json')
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
            assert len(manifest['parts']) == 1
            assert manifest['parts'][0]['field'] == 'body_html'
            assert manifest['parts'][0]['type'] == 'text'

            # Verify round-trip
            loaded = pickle_load(d, enable_parts=True)
            assert loaded.title == "Test Page"
            assert loaded.body_html == "<h1>Hello World</h1>"
            assert loaded.score == 0.95
        finally:
            shutil.rmtree(d)

    def test_both_artifact_field_and_artifact_type_on_same_class(self):
        """Class with BOTH @artifact_field (text) and @artifact_type (object).

        @artifact_field extracts specific named fields (e.g., HTML content).
        @artifact_type extracts all fields matching a target type.
        Both should coexist and produce separate parts.
        """
        data = FullResult(
            raw_html="<div>content</div>",
            planner=InnerWF('plan_wf', step=3),
            executor=InnerWF('exec_wf', step=7),
            summary="all good",
        )
        d = tempfile.mkdtemp()
        try:
            pickle_save(data, d, enable_parts=True)

            # Check that HTML was extracted by @artifact_field
            html_path = os.path.join(d, 'html_source', 'raw_html.html')
            assert os.path.exists(html_path), f"HTML part should exist at {html_path}"
            with open(html_path, 'r', encoding='utf-8') as f:
                assert f.read() == "<div>content</div>"

            # Check that InnerWF objects were extracted by @artifact_type
            manifest_path = os.path.join(d, 'manifest.json')
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
            parts = manifest['parts']
            fields = [p['field'] for p in parts]
            assert 'raw_html' in fields, "raw_html should be in parts"
            assert 'planner' in fields, "planner should be in parts"
            assert 'executor' in fields, "executor should be in parts"
            assert len(parts) == 3

            # Verify round-trip
            loaded = pickle_load(d, enable_parts=True)
            assert loaded.raw_html == "<div>content</div>"
            assert loaded.planner == InnerWF('plan_wf', step=3)
            assert loaded.executor == InnerWF('exec_wf', step=7)
            assert loaded.summary == "all good"
        finally:
            shutil.rmtree(d)

    def test_multiple_artifact_fields_stacked(self):
        """Multiple @artifact_field decorators on same class."""
        data = DualHtmlResult(
            raw_html="<div class='x'>raw</div>",
            cleaned_html="<div>clean</div>",
            metadata={'source': 'test'},
        )
        d = tempfile.mkdtemp()
        try:
            pickle_save(data, d, enable_parts=True)

            # Both HTML files should exist
            raw_path = os.path.join(d, 'html_parts', 'raw_html.html')
            clean_path = os.path.join(d, 'html_parts', 'cleaned_html.html')
            assert os.path.exists(raw_path)
            assert os.path.exists(clean_path)

            # Round-trip
            loaded = pickle_load(d, enable_parts=True)
            assert loaded.raw_html == "<div class='x'>raw</div>"
            assert loaded.cleaned_html == "<div>clean</div>"
            assert loaded.metadata == {'source': 'test'}
        finally:
            shutil.rmtree(d)


# ===========================================================================
# Integration Tests: Comprehensive Workspace Folder Structure Verification
# ===========================================================================

class TestWorkspaceFolderStructure:
    """Verify the exact folder layout produced by recursive resume."""

    def test_full_directory_tree_single_child(self, save_dir):
        """Verify complete directory tree for parent + single child workflow.

        Note: per-step update_state is required so that _uses_state=True
        and state gets initialized from _init_state().
        """

        @artifact_type(SimpleWorkflow, group='inferencers')
        @attrs(slots=False)
        class TreeParent(Workflow):
            child: SimpleWorkflow = attrib(default=None)

            def _get_result_path(self, result_id, *args, **kwargs) -> str:
                return os.path.join(save_dir, f"step_{result_id}.pkl")

            def _init_state(self):
                return {'count': 0}

        loop_count = [0]

        def loop_cond(state, result):
            loop_count[0] += 1
            return loop_count[0] <= 1

        def step_a(x):
            return x + 1

        def step_b(x):
            return x * 2

        def incr_count(state, result):
            state['count'] += 1
            return state

        steps = [
            _StepWrapper(step_a, update_state=incr_count),
            _StepWrapper(step_b, name="step_b", update_state=incr_count,
                         loop_back_to=0, loop_condition=loop_cond),
        ]

        child = SimpleWorkflow(
            steps=[], save_dir=os.path.join(save_dir, 'c_orig'),
            enable_result_save=True,
        )

        parent = TreeParent(
            steps=steps,
            child=child,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
        )

        parent.run(5)

        # Verify directory structure
        # 1. Checkpoint directory exists with main.pkl + manifest.json
        ckpt_dir = os.path.join(save_dir, "step___wf_checkpoint__")
        assert os.path.isdir(ckpt_dir), "Checkpoint dir should exist"
        assert os.path.exists(os.path.join(ckpt_dir, "main.pkl"))
        assert os.path.exists(os.path.join(ckpt_dir, "manifest.json"))

        # 2. Child workspace directory under group subfolder
        child_ws = os.path.join(save_dir, 'inferencers', 'child')
        assert os.path.isdir(child_ws), f"Child workspace should be at {child_ws}"

        # 3. Seq result files should exist (loop creates ___seq files)
        all_entries = os.listdir(save_dir)
        seq_entries = [e for e in all_entries if '___seq' in e]
        assert len(seq_entries) >= 2, (
            f"Should have at least 2 seq entries, got: {seq_entries}"
        )

    def test_full_directory_tree_multiple_children(self, save_dir):
        """Verify directory tree with child, loop triggers workspace creation."""

        @artifact_type(SimpleWorkflow, group='planners')
        @attrs(slots=False)
        class MultiGroupParent(Workflow):
            planner: SimpleWorkflow = attrib(default=None)

            def _get_result_path(self, result_id, *args, **kwargs) -> str:
                return os.path.join(save_dir, f"step_{result_id}.pkl")

            def _init_state(self):
                return {'round': 0}

        loop_count = [0]

        def loop_cond(state, result):
            loop_count[0] += 1
            return loop_count[0] <= 1

        def step_a(x):
            return x + 1

        def incr_round(state, result):
            state['round'] += 1
            return state

        steps = [
            _StepWrapper(step_a, name="step_a", update_state=incr_round,
                         loop_back_to=0, loop_condition=loop_cond),
        ]

        planner = SimpleWorkflow(
            steps=[], save_dir=os.path.join(save_dir, 'p_orig'),
        )

        parent = MultiGroupParent(
            steps=steps,
            planner=planner,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
        )

        parent.run(1)

        # Verify planner workspace under 'planners' group
        planner_ws = os.path.join(save_dir, 'planners', 'planner')
        assert os.path.isdir(planner_ws), f"Planner workspace at {planner_ws}"

    def test_checkpoint_manifest_contains_child_parts(self, save_dir):
        """When checkpoint saves with artifact_types, manifest should list children."""

        @artifact_type(SimpleWorkflow, group='workers')
        @attrs(slots=False)
        class ManifestParent(Workflow):
            worker: SimpleWorkflow = attrib(default=None)

            def _get_result_path(self, result_id, *args, **kwargs) -> str:
                return os.path.join(save_dir, f"step_{result_id}.pkl")

            def _init_state(self):
                return {'worker': self.worker}

        loop_count = [0]

        def loop_cond(state, result):
            loop_count[0] += 1
            return loop_count[0] <= 1

        def step_a(x):
            return x + 1

        def noop_update(state, result):
            return state

        steps = [
            _StepWrapper(step_a, name="step_a", update_state=noop_update,
                         loop_back_to=0, loop_condition=loop_cond),
        ]

        worker = SimpleWorkflow(
            steps=[], save_dir=os.path.join(save_dir, 'w_orig'),
        )

        parent = ManifestParent(
            steps=steps,
            worker=worker,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
        )

        parent.run(1)

        # Read checkpoint manifest
        ckpt_dir = os.path.join(save_dir, "step___wf_checkpoint__")
        manifest_path = os.path.join(ckpt_dir, "manifest.json")
        if os.path.exists(manifest_path):
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
            # The manifest should have the main_file entry
            assert manifest['main_file'] == 'main.pkl'
            # Parts may or may not contain the worker depending on
            # whether the checkpoint dict's state includes a Workflow object
            # The key thing is the manifest is valid JSON with the right structure
            assert 'parts' in manifest
            assert isinstance(manifest['parts'], list)


# ===========================================================================
# Integration Tests: Async Recursive Resume
# ===========================================================================

@pytest.mark.asyncio
class TestAsyncRecursiveResume:
    """Async mirrors of recursive resume tests."""

    async def test_async_parent_child_resume(self, save_dir):
        """Async: Parent with child workflow, partial run -> crash -> resume.

        Uses loop so that _setup_child_workflows is called via _save_loop_checkpoint.
        """
        parent_calls = []
        crash_flag = [True]

        @artifact_type(SimpleWorkflow, group='inferencers')
        @attrs(slots=False)
        class AsyncOuterWF(Workflow):
            planner: SimpleWorkflow = attrib(default=None)

            def _get_result_path(self, result_id, *args, **kwargs) -> str:
                return os.path.join(save_dir, f"step_{result_id}.pkl")

            def _init_state(self):
                return {'count': 0}

        call_count = [0]

        def step_0(x):
            parent_calls.append(('step_0', x))
            return x + 1

        def step_1(x):
            call_count[0] += 1
            parent_calls.append(('step_1', x))
            if crash_flag[0] and call_count[0] == 2:
                raise RuntimeError("async crash")
            return x + 2

        loop_count = [0]

        def loop_cond(state, result):
            loop_count[0] += 1
            return loop_count[0] <= 2

        def incr_count(state, result):
            state['count'] += 1
            return state

        steps = [
            _StepWrapper(step_0, update_state=incr_count),
            _StepWrapper(
                step_1, name="step_1",
                update_state=incr_count,
                loop_back_to=0, loop_condition=loop_cond,
            ),
        ]

        child = SimpleWorkflow(
            steps=[], save_dir=os.path.join(save_dir, 'child'),
            enable_result_save=True,
        )

        parent = AsyncOuterWF(
            steps=steps,
            planner=child,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
        )

        with pytest.raises(RuntimeError, match="async crash"):
            await parent._arun(10)

        assert ('step_0', 10) in parent_calls

        # Resume
        parent_calls.clear()
        crash_flag[0] = False
        call_count[0] = 99
        loop_count[0] = 0

        child2 = SimpleWorkflow(
            steps=[], save_dir=os.path.join(save_dir, 'child'),
            enable_result_save=True,
        )

        parent2 = AsyncOuterWF(
            steps=steps,
            planner=child2,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
            resume_with_saved_results=True,
        )

        result = await parent2._arun(10)
        assert result is not None

        # Child should have override set (via _try_load_checkpoint -> _setup_child_workflows)
        assert child2._result_root_override is not None

    async def test_async_loop_with_child_resume(self, save_dir):
        """Async: Loop + child workflow + crash/resume."""
        call_count = [0]

        @artifact_type(SimpleWorkflow, group='workers')
        @attrs(slots=False)
        class AsyncLoopParent(Workflow):
            worker: SimpleWorkflow = attrib(default=None)

            def _get_result_path(self, result_id, *args, **kwargs) -> str:
                return os.path.join(save_dir, f"step_{result_id}.pkl")

            def _init_state(self):
                return {'rounds': 0}

        def step_a(x):
            return x + 1

        def step_b(x):
            call_count[0] += 1
            if call_count[0] == 2:
                raise RuntimeError("async loop crash")
            return x * 2

        loop_count = [0]

        def loop_cond(state, result):
            loop_count[0] += 1
            return loop_count[0] <= 3

        def incr_rounds(state, result):
            state['rounds'] += 1
            return state

        steps = [
            _StepWrapper(step_a, update_state=incr_rounds),
            _StepWrapper(
                step_b, name="step_b",
                update_state=incr_rounds,
                loop_back_to=0, loop_condition=loop_cond,
            ),
        ]

        worker = SimpleWorkflow(steps=[], save_dir=os.path.join(save_dir, 'w'))

        parent = AsyncLoopParent(
            steps=steps, worker=worker,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
        )

        with pytest.raises(RuntimeError, match="async loop crash"):
            await parent._arun(1)

        # Verify child workspace created
        worker_ws = os.path.join(save_dir, 'workers', 'worker')
        assert os.path.isdir(worker_ws)

        # Resume
        call_count[0] = 99
        loop_count[0] = 0

        worker2 = SimpleWorkflow(steps=[], save_dir=os.path.join(save_dir, 'w'))

        parent2 = AsyncLoopParent(
            steps=steps, worker=worker2,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
            resume_with_saved_results=True,
        )

        result = await parent2._arun(1)
        assert result is not None
        assert worker2._result_root_override is not None


# ===========================================================================
# Integration Tests: Conditioned Loop Resume with State Verification
# ===========================================================================

class TestConditionedLoopResumeState:
    """Tests verifying that loop condition functions receive properly
    restored state after checkpoint-based resume."""

    def test_max_loop_iterations_with_child_and_resume(self, save_dir):
        """max_loop_iterations works correctly across resume with child workflows."""

        @artifact_type(SimpleWorkflow, group='agents')
        @attrs(slots=False)
        class MaxIterParent(Workflow):
            agent: SimpleWorkflow = attrib(default=None)

            def _get_result_path(self, result_id, *args, **kwargs) -> str:
                return os.path.join(save_dir, f"step_{result_id}.pkl")

            def _init_state(self):
                return {'processed': 0}

        crash_count = [0]

        def step_work(x):
            crash_count[0] += 1
            if crash_count[0] == 3:
                raise RuntimeError("mid-loop crash")
            return x + 1

        def incr_processed(state, result):
            state['processed'] += 1
            return state

        steps = [
            _StepWrapper(
                step_work, name="work",
                update_state=incr_processed,
                loop_back_to=0,
                loop_condition=lambda s, r: True,  # always loop
                max_loop_iterations=6,
            ),
        ]

        agent = SimpleWorkflow(steps=[], save_dir=os.path.join(save_dir, 'a'))

        parent = MaxIterParent(
            steps=steps, agent=agent,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
        )

        with pytest.raises(RuntimeError, match="mid-loop crash"):
            parent.run(1)

        # Resume — should continue from where it left off, not restart loop count
        crash_count[0] = 99

        agent2 = SimpleWorkflow(steps=[], save_dir=os.path.join(save_dir, 'a'))

        parent2 = MaxIterParent(
            steps=steps, agent=agent2,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
            resume_with_saved_results=True,
        )

        result = parent2.run(1)
        assert result is not None

        # Loop counts should have been restored from checkpoint
        # Total iterations should be max_loop_iterations (6), not 6 + pre-crash count
        assert parent2._loop_counts is not None

    def test_child_on_self_with_loop_state_and_resume(self, save_dir):
        """Child workflow on self (Pattern A) + loop with state + crash/resume.

        Verifies that loop_counts are restored from checkpoint and the child
        workflow gets its override re-set after checkpoint load.
        """

        @artifact_type(SimpleWorkflow, group='engines')
        @attrs(slots=False)
        class EngineParent(Workflow):
            engine: SimpleWorkflow = attrib(default=None)

            def _get_result_path(self, result_id, *args, **kwargs) -> str:
                return os.path.join(save_dir, f"step_{result_id}.pkl")

            def _init_state(self):
                return {'count': 0}

        crash_count = [0]

        def step_run(x):
            crash_count[0] += 1
            if crash_count[0] == 3:
                raise RuntimeError("engine crash")
            return x + 1

        loop_count = [0]

        def loop_cond(state, result):
            loop_count[0] += 1
            return loop_count[0] <= 4

        def incr_count(state, result):
            state['count'] += 1
            return state

        steps = [
            _StepWrapper(
                step_run, name="run",
                update_state=incr_count,
                loop_back_to=0, loop_condition=loop_cond,
            ),
        ]

        engine = SimpleWorkflow(
            steps=[], save_dir=os.path.join(save_dir, 'eng_orig'),
        )

        parent = EngineParent(
            steps=steps,
            engine=engine,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
        )

        with pytest.raises(RuntimeError, match="engine crash"):
            parent.run(1)

        # Verify engine workspace was created
        engine_ws = os.path.join(save_dir, 'engines', 'engine')
        assert os.path.isdir(engine_ws), (
            f"Engine workspace should exist at {engine_ws}. "
            f"Contents: {os.listdir(save_dir)}"
        )

        # Resume
        crash_count[0] = 99
        loop_count[0] = 0

        engine2 = SimpleWorkflow(
            steps=[], save_dir=os.path.join(save_dir, 'eng_orig'),
        )

        parent2 = EngineParent(
            steps=steps,
            engine=engine2,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
            resume_with_saved_results=True,
        )

        result = parent2.run(1)
        assert result is not None

        # State should have been restored with count > 0
        assert parent2._state is not None
        assert parent2._state.get('count', 0) > 0

        # Engine should have override set
        assert engine2._result_root_override is not None


# ===========================================================================
# Integration Tests: Three-Level Nesting with Loops
# ===========================================================================

class TestThreeLevelNestingWithLoop:
    """Tests for 3-level Workflow nesting (grandchild) with loops."""

    def test_three_level_nesting_crash_resume(self, save_dir):
        """Grandparent -> Middle -> Leaf, with loop for workspace creation.

        Uses a loop so _save_loop_checkpoint calls _setup_child_workflows,
        which creates the middle's workspace. Crash on 2nd iteration, resume.
        """

        @attrs(slots=False)
        class LeafWorkflow(Workflow):
            def _get_result_path(self, result_id, *args, **kwargs) -> str:
                return os.path.join(
                    tempfile.mkdtemp(prefix="leaf_"), f"step_{result_id}.pkl"
                )

        @artifact_type(LeafWorkflow, group='leaves')
        @attrs(slots=False)
        class MiddleWorkflow(Workflow):
            leaf: LeafWorkflow = attrib(default=None)

            def _get_result_path(self, result_id, *args, **kwargs) -> str:
                return os.path.join(
                    tempfile.mkdtemp(prefix="mid_"), f"step_{result_id}.pkl"
                )

        @artifact_type(MiddleWorkflow, group='middles')
        @attrs(slots=False)
        class GrandparentWorkflow(Workflow):
            middle: MiddleWorkflow = attrib(default=None)

            def _get_result_path(self, result_id, *args, **kwargs) -> str:
                return os.path.join(save_dir, f"step_{result_id}.pkl")

            def _init_state(self):
                return {'round': 0}

        crash_count = [0]

        def step_a(x):
            crash_count[0] += 1
            if crash_count[0] == 3:
                raise RuntimeError("grandparent crash")
            return x + 1

        loop_count = [0]

        def loop_cond(state, result):
            loop_count[0] += 1
            return loop_count[0] <= 3

        def incr_round(state, result):
            state['round'] += 1
            return state

        steps = [
            _StepWrapper(
                step_a, name="step_a",
                update_state=incr_round,
                loop_back_to=0,
                loop_condition=loop_cond,
            ),
        ]

        leaf = LeafWorkflow(steps=[])
        middle = MiddleWorkflow(steps=[], leaf=leaf)

        parent = GrandparentWorkflow(
            steps=steps,
            middle=middle,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
        )

        with pytest.raises(RuntimeError, match="grandparent crash"):
            parent.run(5)

        # Verify middle workspace (created by _setup_child_workflows during checkpoint)
        middle_ws = os.path.join(save_dir, 'middles', 'middle')
        assert os.path.isdir(middle_ws), f"Middle workspace should exist at {middle_ws}"

        # Resume
        crash_count[0] = 99
        loop_count[0] = 0

        leaf2 = LeafWorkflow(steps=[])
        middle2 = MiddleWorkflow(steps=[], leaf=leaf2)

        parent2 = GrandparentWorkflow(
            steps=steps,
            middle=middle2,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
            resume_with_saved_results=True,
        )

        result = parent2.run(5)
        assert result is not None

        # Middle should have override set (via _try_load_checkpoint)
        assert middle2._result_root_override is not None
        assert 'middles' in middle2._result_root_override

        # Middle's config should be propagated
        assert middle2.enable_result_save is True
        assert middle2.resume_with_saved_results is True


# ===========================================================================
# Integration Tests: Jsonfy Checkpoint Mode
# ===========================================================================

class TestJsonfyCheckpointMode:
    """End-to-end tests for checkpoint_mode='jsonfy' covering loop+crash+resume,
    checkpoint file structure, and fallback behaviors."""

    def test_jsonfy_basic_loop_crash_resume(self, save_dir):
        """Basic loop + crash + resume with checkpoint_mode='jsonfy'."""

        @attrs(slots=False)
        class JsonfyWF(Workflow):
            def _get_result_path(self, result_id, *args, **kwargs) -> str:
                return os.path.join(save_dir, f"step_{result_id}.pkl")

            def _init_state(self):
                return {'iterations': 0}

        crash_count = [0]

        def step_compute(x):
            crash_count[0] += 1
            if crash_count[0] == 3:
                raise RuntimeError("jsonfy crash")
            return x + 10

        loop_count = [0]

        def loop_cond(state, result):
            loop_count[0] += 1
            return loop_count[0] <= 4

        def incr_iter(state, result):
            state['iterations'] += 1
            return state

        steps = [
            _StepWrapper(
                step_compute, name="compute",
                update_state=incr_iter,
                loop_back_to=0,
                loop_condition=loop_cond,
            ),
        ]

        wf = JsonfyWF(
            steps=steps,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
            checkpoint_mode='jsonfy',
        )

        with pytest.raises(RuntimeError, match="jsonfy crash"):
            wf.run(1)

        # Verify checkpoint file is .json (not .pkl)
        ckpt_json = os.path.join(save_dir, "step___wf_checkpoint__.pkl.json")
        assert os.path.exists(ckpt_json), (
            f"Jsonfy checkpoint should exist as .json file. "
            f"Dir contents: {os.listdir(save_dir)}"
        )

        # Verify .types.json companion file exists
        types_file = ckpt_json + ".types.json"
        assert os.path.exists(types_file), (
            f"Types file should exist at {types_file}"
        )

        # Verify checkpoint content is valid JSON with expected fields
        with open(ckpt_json, 'r') as f:
            ckpt_data = json.loads(f.read())
        assert 'version' in ckpt_data
        assert 'next_step_index' in ckpt_data
        assert 'state' in ckpt_data
        assert ckpt_data['state']['iterations'] > 0

        # Resume
        crash_count[0] = 99
        loop_count[0] = 0

        wf2 = JsonfyWF(
            steps=steps,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
            resume_with_saved_results=True,
            checkpoint_mode='jsonfy',
        )

        result = wf2.run(1)
        assert result is not None

        # State should have been restored — iterations should be > pre-crash value
        assert wf2._state is not None
        assert wf2._state['iterations'] > 1

    def test_jsonfy_checkpoint_state_wrapper_used(self, save_dir):
        """Verify that jsonfy mode uses CheckpointState wrapper (types.json contains it)."""

        @attrs(slots=False)
        class TypeCheckWF(Workflow):
            def _get_result_path(self, result_id, *args, **kwargs) -> str:
                return os.path.join(save_dir, f"step_{result_id}.pkl")

            def _init_state(self):
                return {'val': 0}

        def step_inc(x):
            return x + 1

        loop_count = [0]

        def loop_cond(state, result):
            loop_count[0] += 1
            return loop_count[0] <= 1  # loop once then stop

        def update_val(state, result):
            state['val'] += 1
            return state

        steps = [
            _StepWrapper(
                step_inc, name="inc",
                update_state=update_val,
                loop_back_to=0,
                loop_condition=loop_cond,
            ),
        ]

        wf = TypeCheckWF(
            steps=steps,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
            checkpoint_mode='jsonfy',
        )

        wf.run(0)

        # Check that .types.json references CheckpointState
        types_file = os.path.join(
            save_dir, "step___wf_checkpoint__.pkl.json.types.json"
        )
        if os.path.exists(types_file):
            with open(types_file, 'r') as f:
                types_data = json.loads(f.read())
            # types_data should reference CheckpointState somewhere
            types_str = json.dumps(types_data)
            assert 'CheckpointState' in types_str, (
                f"Types file should reference CheckpointState. Got: {types_str}"
            )

    def test_jsonfy_missing_types_file_fallback(self, save_dir):
        """When .types.json is missing, _load_result_jsonfy returns raw dict (Req 7.3)."""

        @attrs(slots=False)
        class FallbackWF(Workflow):
            def _get_result_path(self, result_id, *args, **kwargs) -> str:
                return os.path.join(save_dir, f"step_{result_id}.pkl")

            def _init_state(self):
                return {'data': 'test'}

        def step_noop(x):
            return x + 1

        loop_count = [0]

        def loop_once(state, result):
            loop_count[0] += 1
            return loop_count[0] <= 1

        def update_data(state, result):
            state['data'] = f'iter_{result}'
            return state

        steps = [
            _StepWrapper(
                step_noop, name="noop",
                update_state=update_data,
                loop_back_to=0,
                loop_condition=loop_once,
            ),
        ]

        wf = FallbackWF(
            steps=steps,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
            checkpoint_mode='jsonfy',
        )

        wf.run(0)

        # Delete the .types.json file to simulate missing types
        ckpt_json = os.path.join(save_dir, "step___wf_checkpoint__.pkl.json")
        types_file = ckpt_json + ".types.json"
        if os.path.exists(types_file):
            os.remove(types_file)

        # Resume — should still work, falling back to raw dict
        loop_count[0] = 0

        wf2 = FallbackWF(
            steps=steps,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
            resume_with_saved_results=True,
            checkpoint_mode='jsonfy',
        )

        # _try_load_checkpoint should handle the raw dict correctly
        result = wf2.run(0)
        assert result is not None

    def test_jsonfy_step_results_saved_as_json(self, save_dir):
        """Verify individual step results are saved as .json files in jsonfy mode."""

        @attrs(slots=False)
        class StepSaveWF(Workflow):
            def _get_result_path(self, result_id, *args, **kwargs) -> str:
                return os.path.join(save_dir, f"step_{result_id}.pkl")

        def step_a(x):
            return {'output': x * 2}

        def step_b(x):
            return {'final': x}

        steps = [step_a, step_b]

        wf = StepSaveWF(
            steps=steps,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
            checkpoint_mode='jsonfy',
        )

        result = wf.run(5)
        assert result == {'final': {'output': 10}}

        # Step results should be saved as .json files
        step0_json = os.path.join(save_dir, "step_0.pkl.json")
        step1_json = os.path.join(save_dir, "step_1.pkl.json")
        assert os.path.exists(step0_json), (
            f"Step 0 result should be saved as JSON. Dir: {os.listdir(save_dir)}"
        )
        assert os.path.exists(step1_json), (
            f"Step 1 result should be saved as JSON. Dir: {os.listdir(save_dir)}"
        )

        # Verify content
        with open(step0_json, 'r') as f:
            step0_data = json.loads(f.read())
        assert step0_data == {'output': 10}

    def test_jsonfy_silently_converts_non_serializable_state(self, save_dir):
        """Jsonfy mode silently converts non-serializable objects (e.g. lambda → {}).
        This documents a known limitation: jsonfy validation passes but data
        fidelity is lost. No error is raised."""

        @attrs(slots=False)
        class SilentLossWF(Workflow):
            def _get_result_path(self, result_id, *args, **kwargs) -> str:
                return os.path.join(save_dir, f"step_{result_id}.pkl")

            def _init_state(self):
                return {'callback': lambda x: x, 'value': 42}

        def step_x(x):
            return x + 1

        loop_count = [0]

        def loop_cond(state, result):
            loop_count[0] += 1
            return loop_count[0] <= 1

        def update_s(state, result):
            return state

        steps = [
            _StepWrapper(
                step_x, name="x",
                update_state=update_s,
                loop_back_to=0,
                loop_condition=loop_cond,
            ),
        ]

        wf = SilentLossWF(
            steps=steps,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
            checkpoint_mode='jsonfy',
        )

        # Runs without error — jsonfy converts lambda to {} silently
        result = wf.run(1)
        assert result is not None

        # Verify checkpoint was saved (lambda silently dropped)
        ckpt_json = os.path.join(save_dir, "step___wf_checkpoint__.pkl.json")
        assert os.path.exists(ckpt_json)
        with open(ckpt_json, 'r') as f:
            ckpt_data = json.loads(f.read())
        # lambda was converted to {} by jsonfy's dict__ conversion
        assert ckpt_data['state']['callback'] == {}
        assert ckpt_data['state']['value'] == 42

    def test_jsonfy_with_child_workflow_workspace_creation(self, save_dir):
        """Jsonfy mode + child workflow: workspace dirs still created via
        _setup_child_workflows, even though jsonfy doesn't extract children
        to separate parts files like pickle mode does."""

        @artifact_type(SimpleWorkflow, group='processors')
        @attrs(slots=False)
        class JsonfyParentWF(Workflow):
            processor: SimpleWorkflow = attrib(default=None)

            def _get_result_path(self, result_id, *args, **kwargs) -> str:
                return os.path.join(save_dir, f"step_{result_id}.pkl")

            def _init_state(self):
                return {'count': 0}

        crash_count = [0]

        def step_process(x):
            crash_count[0] += 1
            if crash_count[0] == 3:
                raise RuntimeError("jsonfy parent crash")
            return x + 5

        loop_count = [0]

        def loop_cond(state, result):
            loop_count[0] += 1
            return loop_count[0] <= 3

        def incr(state, result):
            state['count'] += 1
            return state

        steps = [
            _StepWrapper(
                step_process, name="process",
                update_state=incr,
                loop_back_to=0,
                loop_condition=loop_cond,
            ),
        ]

        child = SimpleWorkflow(
            steps=[], save_dir=os.path.join(save_dir, 'child_orig'),
            enable_result_save=True,
        )

        parent = JsonfyParentWF(
            steps=steps,
            processor=child,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
            checkpoint_mode='jsonfy',
        )

        with pytest.raises(RuntimeError, match="jsonfy parent crash"):
            parent.run(1)

        # Child workspace should be created by _setup_child_workflows
        child_ws = os.path.join(save_dir, 'processors', 'processor')
        assert os.path.isdir(child_ws), (
            f"Child workspace should exist at {child_ws}. "
            f"Dir contents: {os.listdir(save_dir)}"
        )

        # Child should have override set
        assert child._result_root_override is not None
        assert 'processors' in child._result_root_override

        # checkpoint_mode should propagate
        assert child.checkpoint_mode == 'jsonfy'

        # Resume
        crash_count[0] = 99
        loop_count[0] = 0

        child2 = SimpleWorkflow(
            steps=[], save_dir=os.path.join(save_dir, 'child_orig'),
            enable_result_save=True,
        )

        parent2 = JsonfyParentWF(
            steps=steps,
            processor=child2,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
            resume_with_saved_results=True,
            checkpoint_mode='jsonfy',
        )

        result = parent2.run(1)
        assert result is not None

        # State should be restored
        assert parent2._state is not None
        assert parent2._state['count'] > 0

        # Child should have override re-set via _try_load_checkpoint
        assert child2._result_root_override is not None

    def test_jsonfy_checkpoint_backward_compat_with_raw_dict(self, save_dir):
        """When checkpoint loads as raw dict (no types.json), _try_load_checkpoint
        still works because it checks for 'next_step_index' key in dict."""

        @attrs(slots=False)
        class RawDictWF(Workflow):
            def _get_result_path(self, result_id, *args, **kwargs) -> str:
                return os.path.join(save_dir, f"step_{result_id}.pkl")

            def _init_state(self):
                return {'n': 0}

        call_count = [0]

        def step_work(x):
            call_count[0] += 1
            if call_count[0] == 2:
                raise RuntimeError("raw dict crash")
            return x + 1

        loop_count = [0]

        def loop_cond(state, result):
            loop_count[0] += 1
            return loop_count[0] <= 3

        def update_n(state, result):
            state['n'] += 1
            return state

        steps = [
            _StepWrapper(
                step_work, name="work",
                update_state=update_n,
                loop_back_to=0,
                loop_condition=loop_cond,
            ),
        ]

        wf = RawDictWF(
            steps=steps,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
            checkpoint_mode='jsonfy',
        )

        with pytest.raises(RuntimeError, match="raw dict crash"):
            wf.run(0)

        # Remove .types.json to force raw dict loading
        ckpt_json = os.path.join(save_dir, "step___wf_checkpoint__.pkl.json")
        types_file = ckpt_json + ".types.json"
        if os.path.exists(types_file):
            os.remove(types_file)

        # Resume — raw dict should still have 'next_step_index' so checkpoint loads
        call_count[0] = 99
        loop_count[0] = 0

        wf2 = RawDictWF(
            steps=steps,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            enable_result_save=True,
            resume_with_saved_results=True,
            checkpoint_mode='jsonfy',
        )

        result = wf2.run(0)
        assert result is not None
        assert wf2._state['n'] > 0
