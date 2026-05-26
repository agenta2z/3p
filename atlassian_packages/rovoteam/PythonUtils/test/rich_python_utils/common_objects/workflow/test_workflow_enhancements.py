"""Tests for Workflow enhancements: named steps, flow state, loops,
error handlers, and WorkflowAborted.

Covers backward compatibility (plain steps with no new features) and
each enhancement in isolation and in combination.
"""
import pytest
from attr import attrs, attrib

from python_utils.common_objects.workflow.workflow import Workflow
from python_utils.common_objects.workflow.common.exceptions import WorkflowAborted
from python_utils.common_objects.workflow.common.result_pass_down_mode import ResultPassDownMode


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
# Concrete Workflow subclass for testing
# ---------------------------------------------------------------------------

@attrs(slots=False)
class SimpleWorkflow(Workflow):
    """Minimal concrete subclass — no save/resume."""

    def _get_result_path(self, result_id, *args, **kwargs):
        raise NotImplementedError("save not used in tests")


# ---------------------------------------------------------------------------
# 1. Backward compatibility — no enhancements used
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    """Existing Workflow behaviour must be identical when no enhancements
    are configured (no state, no loops, no named steps)."""

    def test_plain_steps_no_pass_down(self):
        """Plain steps with NoPassDown receive original args."""
        calls = []

        def s0(x):
            calls.append(('s0', x))
            return x + 1

        def s1(x):
            calls.append(('s1', x))
            return x * 2

        w = SimpleWorkflow(
            steps=[s0, s1],
            result_pass_down_mode=ResultPassDownMode.NoPassDown,
        )
        result = w.run(3)
        assert calls == [('s0', 3), ('s1', 3)]
        assert result == 6

    def test_plain_steps_result_as_first_arg(self):
        """ResultAsFirstArg passes previous result to next step."""
        w = SimpleWorkflow(
            steps=[lambda x: x + 1, lambda x: x * 2],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
        )
        result = w.run(5)
        assert result == 12  # (5+1)*2

    def test_empty_steps_returns_none(self):
        w = SimpleWorkflow(steps=[])
        assert w.run() is None

    def test_single_step(self):
        w = SimpleWorkflow(steps=[lambda x: x * 3])
        assert w.run(7) == 21

    def test_state_is_none_when_unused(self):
        """When no step declares update_state or receives_state, state
        stays None — no overhead."""
        w = SimpleWorkflow(steps=[lambda x: x])
        w.run(1)
        assert w._state is None

    def test_post_process_still_fires(self):
        """Existing _post_process hook fires for each step."""
        log = []

        @attrs(slots=False)
        class PPWorkflow(SimpleWorkflow):
            def _post_process(self, result, *args, **kwargs):
                log.append(result)
                return result

        w = PPWorkflow(
            steps=[lambda x: x + 1, lambda x: x + 2],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
        )
        w.run(0)
        assert log == [1, 3]


# ---------------------------------------------------------------------------
# 2. Named Steps
# ---------------------------------------------------------------------------

class TestNamedSteps:
    """Step names surface in hooks and error messages."""

    def test_get_step_name_from_attribute(self):
        step = _StepWrapper(lambda x: x, name="my_step")
        w = SimpleWorkflow(steps=[step])
        assert w._get_step_name(step, 0) == "my_step"

    def test_get_step_name_none_when_missing(self):
        step = lambda x: x  # noqa: E731
        w = SimpleWorkflow(steps=[step])
        assert w._get_step_name(step, 0) is None

    def test_on_step_complete_receives_name(self):
        names = []

        @attrs(slots=False)
        class HookWorkflow(SimpleWorkflow):
            def _on_step_complete(self, result, step_name, step_index,
                                  state, *args, **kwargs):
                names.append(step_name)

        s0 = _StepWrapper(lambda x: x, name="alpha",
                          update_state=lambda st, r: st)
        s1 = _StepWrapper(lambda x: x, name="beta",
                          update_state=lambda st, r: st)

        w = HookWorkflow(steps=[s0, s1])
        w.run(1)
        assert names == ["alpha", "beta"]


# ---------------------------------------------------------------------------
# 3. Flow State
# ---------------------------------------------------------------------------

class TestFlowState:
    """State initialization, updating, and accumulation across steps."""

    def test_state_initialized_when_update_state_present(self):
        step = _StepWrapper(lambda x: x,
                            update_state=lambda st, r: st)
        w = SimpleWorkflow(steps=[step])
        w.run(0)
        assert w._state is not None
        assert isinstance(w._state, dict)

    def test_state_initialized_when_receives_state_present(self):
        step = _StepWrapper(lambda x: x, receives_state=True)
        w = SimpleWorkflow(steps=[step])
        w.run(0)
        assert w._state is not None

    def test_custom_init_state(self):
        @attrs(slots=False)
        class CustomStateWorkflow(SimpleWorkflow):
            def _init_state(self):
                return {"counter": 0}

        step = _StepWrapper(lambda x: x,
                            update_state=lambda st, r: st)
        w = CustomStateWorkflow(steps=[step])
        w.run(0)
        assert w._state == {"counter": 0}

    def test_state_accumulates_across_steps(self):
        def updater0(state, result):
            state['vals'] = state.get('vals', []) + [result]
            return state

        def updater1(state, result):
            state['vals'] = state.get('vals', []) + [result]
            return state

        s0 = _StepWrapper(lambda x: x + 1, update_state=updater0)
        s1 = _StepWrapper(lambda x: x + 2, update_state=updater1)

        w = SimpleWorkflow(
            steps=[s0, s1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
        )
        w.run(10)
        assert w._state['vals'] == [11, 13]

    def test_update_state_delegates_to_per_step(self):
        """Per-step update_state attribute is called by _update_state."""
        called_with = []

        def my_updater(state, result):
            called_with.append((dict(state), result))
            state['seen'] = True
            return state

        step = _StepWrapper(lambda x: x * 2, update_state=my_updater)
        w = SimpleWorkflow(steps=[step])
        w.run(5)
        assert called_with == [({}, 10)]
        assert w._state == {'seen': True}


# ---------------------------------------------------------------------------
# 4. Loop Segments
# ---------------------------------------------------------------------------

class TestLoopSegments:
    """Loop-back mechanism: loop_back_to, loop_condition, max_loop_iterations."""

    def test_simple_loop_by_index(self):
        """Loop back to step 0 until condition is met."""
        call_count = [0]

        def step0(x):
            call_count[0] += 1
            return x

        def should_loop(state, result):
            return state.get('count', 0) < 3

        def updater(state, result):
            state['count'] = state.get('count', 0) + 1
            return state

        s0 = _StepWrapper(step0, update_state=updater)
        s1 = _StepWrapper(
            lambda x: x,
            update_state=lambda st, r: st,
            loop_back_to=0,
            loop_condition=should_loop,
            max_loop_iterations=10,
        )

        w = SimpleWorkflow(
            steps=[s0, s1],
            result_pass_down_mode=ResultPassDownMode.NoPassDown,
        )
        w.run(0)
        # s0 runs → count=1 → s1 checks count<3 → loop back
        # s0 runs → count=2 → s1 checks count<3 → loop back
        # s0 runs → count=3 → s1 checks count<3 → no loop
        # s0 runs 3 times total
        assert call_count[0] == 3

    def test_loop_by_name(self):
        """loop_back_to can be a step name string."""
        iterations = [0]

        def updater(state, result):
            state['n'] = state.get('n', 0) + 1
            return state

        s0 = _StepWrapper(lambda x: x, name="start",
                          update_state=updater)
        s1 = _StepWrapper(
            lambda x: x,
            update_state=lambda st, r: st,
            loop_back_to="start",
            loop_condition=lambda st, r: st.get('n', 0) < 2,
            max_loop_iterations=5,
        )

        w = SimpleWorkflow(steps=[s0, s1])
        w.run(0)
        # s0 updater increments n: initial → n=1, loop → n=2
        # s1 checks n<2: True at n=1 (loop back), False at n=2 (exit)
        assert w._state['n'] == 2

    def test_loop_max_iterations_respected(self):
        """Loop stops after max_loop_iterations even if condition is True."""
        s0 = _StepWrapper(lambda x: x,
                          update_state=lambda st, r: st)
        s1 = _StepWrapper(
            lambda x: x,
            update_state=lambda st, r: st,
            loop_back_to=0,
            loop_condition=lambda st, r: True,  # always true
            max_loop_iterations=3,
        )

        w = SimpleWorkflow(steps=[s0, s1])
        w.run(0)
        assert w._loop_counts[1] == 3

    def test_on_loop_exhausted_called(self):
        """on_loop_exhausted fires when max iterations reached."""
        exhausted_calls = []

        def on_exhausted(state, result):
            exhausted_calls.append(True)

        s0 = _StepWrapper(lambda x: x,
                          update_state=lambda st, r: st)
        s1 = _StepWrapper(
            lambda x: x,
            update_state=lambda st, r: st,
            loop_back_to=0,
            loop_condition=lambda st, r: True,
            max_loop_iterations=2,
            on_loop_exhausted=on_exhausted,
        )

        w = SimpleWorkflow(steps=[s0, s1])
        w.run(0)
        assert len(exhausted_calls) == 1

    def test_no_loop_when_condition_false(self):
        """Loop doesn't fire when condition returns False."""
        call_count = [0]

        def step0():
            call_count[0] += 1

        s0 = _StepWrapper(step0, update_state=lambda st, r: st)
        s1 = _StepWrapper(
            lambda: None,
            update_state=lambda st, r: st,
            loop_back_to=0,
            loop_condition=lambda st, r: False,
            max_loop_iterations=10,
        )

        w = SimpleWorkflow(steps=[s0, s1])
        w.run()
        assert call_count[0] == 1  # only initial run

    def test_on_step_complete_skipped_on_loop_back(self):
        """_on_step_complete does NOT fire when looping back."""
        complete_names = []

        @attrs(slots=False)
        class TrackingWorkflow(SimpleWorkflow):
            def _on_step_complete(self, result, step_name, step_index,
                                  state, *args, **kwargs):
                complete_names.append(step_name)

        s0 = _StepWrapper(lambda: None, name="A",
                          update_state=lambda st, r: st)
        s1 = _StepWrapper(
            lambda: None, name="B",
            update_state=lambda st, r: {**st, 'n': st.get('n', 0) + 1},
            loop_back_to="A",
            loop_condition=lambda st, r: st.get('n', 0) < 2,
            max_loop_iterations=5,
        )

        w = TrackingWorkflow(steps=[s0, s1])
        w.run()
        # s1 update_state increments n each time s1 runs.
        # Pass 1: s0 complete("A"), s1 → n=1 < 2 → loop back
        # Pass 2: s0 complete("A"), s1 → n=2, not < 2 → complete("B")
        # A fires on_step_complete 2 times, B fires 1 time.
        assert complete_names.count("A") == 2
        assert complete_names.count("B") == 1

    def test_resolve_step_index_by_int(self):
        w = SimpleWorkflow(steps=[])
        assert w._resolve_step_index(2, []) == 2

    def test_resolve_step_index_by_name(self):
        s0 = _StepWrapper(lambda: None, name="first")
        s1 = _StepWrapper(lambda: None, name="second")
        w = SimpleWorkflow(steps=[s0, s1])
        assert w._resolve_step_index("second", [s0, s1]) == 1

    def test_resolve_step_index_not_found(self):
        w = SimpleWorkflow(steps=[])
        with pytest.raises(ValueError, match="not found"):
            w._resolve_step_index("nonexistent", [])


# ---------------------------------------------------------------------------
# 5. WorkflowAborted & _handle_abort
# ---------------------------------------------------------------------------

class TestWorkflowAborted:
    """WorkflowAborted exception and _handle_abort hook."""

    def test_abort_from_error_handler(self):
        """Error handler raises WorkflowAborted → _handle_abort is called."""
        def failing_step():
            raise RuntimeError("boom")

        def abort_handler(error, step_result, state, step_name, step_index):
            raise WorkflowAborted(
                message="aborting",
                step_name=step_name,
                step_index=step_index,
                partial_result={"partial": True},
            )

        s0 = _StepWrapper(
            failing_step,
            name="fail_step",
            error_handler=abort_handler,
            update_state=lambda st, r: st,
        )

        @attrs(slots=False)
        class AbortWorkflow(SimpleWorkflow):
            def _handle_abort(self, abort_exc, step_result, state):
                return abort_exc.partial_result

        w = AbortWorkflow(steps=[s0])
        result = w.run()
        assert result == {"partial": True}

    def test_abort_from_on_step_complete(self):
        """WorkflowAborted raised in _on_step_complete is caught."""
        @attrs(slots=False)
        class AbortOnComplete(SimpleWorkflow):
            def _on_step_complete(self, result, step_name, step_index,
                                  state, *args, **kwargs):
                raise WorkflowAborted(
                    step_name=step_name, partial_result="aborted_result"
                )

            def _handle_abort(self, abort_exc, step_result, state):
                return abort_exc.partial_result

        s0 = _StepWrapper(lambda: 42, update_state=lambda st, r: st)
        w = AbortOnComplete(steps=[s0])
        result = w.run()
        assert result == "aborted_result"

    def test_abort_from_on_loop_exhausted(self):
        """WorkflowAborted from on_loop_exhausted is caught."""

        def exhausted_abort(state, result):
            raise WorkflowAborted(
                message="loop exhausted",
                partial_result=state,
            )

        s0 = _StepWrapper(lambda: None, update_state=lambda st, r: st)
        s1 = _StepWrapper(
            lambda: None,
            update_state=lambda st, r: {**st, 'x': True},
            loop_back_to=0,
            loop_condition=lambda st, r: True,
            max_loop_iterations=1,
            on_loop_exhausted=exhausted_abort,
        )

        @attrs(slots=False)
        class AbortWorkflow(SimpleWorkflow):
            def _handle_abort(self, abort_exc, step_result, state):
                return abort_exc.partial_result

        w = AbortWorkflow(steps=[s0, s1])
        result = w.run()
        assert result['x'] is True

    def test_default_handle_abort_returns_step_result(self):
        """Default _handle_abort returns step_result."""

        def failing_step():
            raise RuntimeError("fail")

        def abort_handler(error, step_result, state, step_name, step_index):
            raise WorkflowAborted(partial_result="ignored")

        s0 = _StepWrapper(lambda: "first_result",
                          update_state=lambda st, r: st)
        s1 = _StepWrapper(
            failing_step,
            error_handler=abort_handler,
            update_state=lambda st, r: st,
        )

        w = SimpleWorkflow(
            steps=[s0, s1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
        )
        # Default _handle_abort returns step_result (from s0)
        result = w.run()
        assert result == "first_result"

    def test_workflow_aborted_attributes(self):
        exc = WorkflowAborted(
            message="test", step_name="step_x", step_index=3,
            partial_result={"data": 1}
        )
        assert str(exc) == "test"
        assert exc.step_name == "step_x"
        assert exc.step_index == 3
        assert exc.partial_result == {"data": 1}


# ---------------------------------------------------------------------------
# 6. Per-step Error Handler
# ---------------------------------------------------------------------------

class TestPerStepErrorHandler:
    """Per-step error_handler attribute allows recovering from step errors."""

    def test_error_handler_return_continues_execution(self):
        """Error handler returns a value → becomes step_result, next step
        executes."""
        def failing():
            raise ValueError("oops")

        def recover(error, step_result, state, step_name, step_index):
            return "recovered"

        s0 = _StepWrapper(failing, error_handler=recover)
        s1 = _StepWrapper(lambda x: x + "_done")

        w = SimpleWorkflow(
            steps=[s0, s1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
        )
        result = w.run()
        assert result == "recovered_done"

    def test_error_handler_reraise_propagates(self):
        """Error handler re-raises → exception propagates to caller
        (not WorkflowAborted, so not caught by outer try)."""
        def failing():
            raise ValueError("oops")

        def reraise_handler(error, step_result, state, step_name, step_index):
            raise error

        s0 = _StepWrapper(failing, error_handler=reraise_handler,
                          update_state=lambda st, r: st)

        w = SimpleWorkflow(steps=[s0])
        with pytest.raises(ValueError, match="oops"):
            w.run()

    def test_no_error_handler_preserves_default_reraise(self):
        """Steps without error_handler raise normally (backward compat)."""
        def failing(x):
            raise RuntimeError("step failed")

        w = SimpleWorkflow(steps=[failing])
        with pytest.raises(RuntimeError, match="step failed"):
            w.run(1)

    def test_error_handler_receives_correct_args(self):
        """Error handler receives (error, step_result, state, step_name,
        step_index)."""
        captured = {}

        def failing():
            raise ValueError("test_error")

        def capture_handler(error, step_result, state, step_name, step_index):
            captured['error'] = error
            captured['step_result'] = step_result
            captured['state'] = state
            captured['step_name'] = step_name
            captured['step_index'] = step_index
            return "handled"

        s0 = _StepWrapper(
            lambda: "first",
            name="s0",
            update_state=lambda st, r: {**st, 'val': r},
        )
        s1 = _StepWrapper(
            failing,
            name="s1",
            error_handler=capture_handler,
            update_state=lambda st, r: st,
        )

        w = SimpleWorkflow(
            steps=[s0, s1],
            result_pass_down_mode=ResultPassDownMode.NoPassDown,
        )
        w.run()

        assert isinstance(captured['error'], ValueError)
        assert str(captured['error']) == "test_error"
        assert captured['step_result'] == "first"  # result from s0
        assert captured['state'] == {'val': 'first'}
        assert captured['step_name'] == "s1"
        assert captured['step_index'] == 1


# ---------------------------------------------------------------------------
# 7. Integration — combined features
# ---------------------------------------------------------------------------

class TestIntegration:
    """Multiple enhancements working together."""

    def test_loop_with_state_and_named_steps(self):
        """Full scenario: collect → evaluate with retry loop, abort on
        exhaustion — mimicking MetaAgentPipeline pattern."""
        items_collected = []
        eval_results = []

        def collect():
            items_collected.append(f"item_{len(items_collected)}")
            return items_collected[-1]

        def evaluate():
            eval_results.append(len(items_collected))
            return eval_results[-1]

        def collect_updater(state, result):
            state['items'] = list(items_collected)
            return state

        def eval_updater(state, result):
            state['eval_count'] = len(eval_results)
            return state

        def insufficient(state, result):
            return len(state.get('items', [])) < 3

        exhausted_called = [False]

        def on_exhausted(state, result):
            exhausted_called[0] = True
            raise WorkflowAborted(
                message="not enough",
                partial_result={'items': state['items']},
            )

        s_collect = _StepWrapper(
            collect, name="collection",
            update_state=collect_updater,
        )
        s_evaluate = _StepWrapper(
            evaluate, name="evaluation",
            update_state=eval_updater,
            loop_back_to="collection",
            loop_condition=insufficient,
            max_loop_iterations=5,
            on_loop_exhausted=on_exhausted,
        )
        s_process = _StepWrapper(
            lambda: "done", name="process",
            update_state=lambda st, r: st,
        )

        @attrs(slots=False)
        class PipelineWorkflow(SimpleWorkflow):
            def _handle_abort(self, abort_exc, step_result, state):
                return abort_exc.partial_result

        # With max_loop_iterations=5, loop runs 5 times + initial = 6 total
        # but insufficient checks items < 3, so after 3 iterations it stops
        w = PipelineWorkflow(steps=[s_collect, s_evaluate, s_process])
        result = w.run()
        # After initial: items=1, eval loops back because <3
        # After 1st loop: items=2, eval loops back because <3
        # After 2nd loop: items=3, eval doesn't loop (>=3)
        # Process runs → returns "done"
        assert result == "done"
        assert len(items_collected) == 3
        assert exhausted_called[0] is False

    def test_post_process_fires_on_loop_iterations(self):
        """_post_process fires on every iteration including loops."""
        pp_calls = []

        @attrs(slots=False)
        class PPWorkflow(SimpleWorkflow):
            def _post_process(self, result, *args, **kwargs):
                pp_calls.append(result)
                return result

        s0 = _StepWrapper(lambda: "a", update_state=lambda st, r: st)
        s1 = _StepWrapper(
            lambda: "b",
            update_state=lambda st, r: {**st, 'n': st.get('n', 0) + 1},
            loop_back_to=0,
            loop_condition=lambda st, r: st.get('n', 0) < 2,
            max_loop_iterations=5,
        )

        w = PPWorkflow(steps=[s0, s1])
        w.run()
        # Pass 1: pp("a"), pp("b"), s1 update → n=1, n<2 → loop back
        # Pass 2: pp("a"), pp("b"), s1 update → n=2, not <2 → done
        # Total _post_process calls: 4 (2x s0 + 2x s1)
        assert len(pp_calls) == 4

    def test_error_in_middle_step_with_handler(self):
        """Error in step 1 (of 3) with handler → step 2 still runs."""
        def step0():
            return "ok0"

        def step1():
            raise RuntimeError("fail1")

        def step2(x):
            return f"step2_{x}"

        def handler(error, step_result, state, step_name, step_index):
            return "recovered1"

        s0 = _StepWrapper(step0)
        s1 = _StepWrapper(step1, error_handler=handler)
        s2 = _StepWrapper(step2)

        w = SimpleWorkflow(
            steps=[s0, s1, s2],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
        )
        result = w.run()
        assert result == "step2_recovered1"

    def test_workflow_aborted_import_from_package(self):
        """WorkflowAborted can be imported from the workflow package."""
        from python_utils.common_objects.workflow import WorkflowAborted as WA
        assert WA is WorkflowAborted

    def test_state_survives_error_recovery(self):
        """State is preserved when error handler recovers."""
        def updater0(state, result):
            state['step0'] = result
            return state

        def updater1(state, result):
            state['step1'] = result
            return state

        def failing():
            raise RuntimeError("boom")

        def recover(error, step_result, state, step_name, step_index):
            return "recovered"

        s0 = _StepWrapper(lambda: "val0", update_state=updater0)
        s1 = _StepWrapper(failing, error_handler=recover,
                          update_state=updater1)

        w = SimpleWorkflow(
            steps=[s0, s1],
            result_pass_down_mode=ResultPassDownMode.NoPassDown,
        )
        w.run()
        assert w._state['step0'] == 'val0'
        assert w._state['step1'] == 'recovered'
