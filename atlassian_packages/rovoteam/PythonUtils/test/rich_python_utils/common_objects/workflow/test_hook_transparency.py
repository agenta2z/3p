"""Tests for hook transparency (Task 23.3).

Covers:
- _post_process receives unwrapped result, not ExpansionResult
- _update_state receives unwrapped result
- _on_step_complete receives unwrapped result
- WorkGraphNode _post_process receives unwrapped result
"""
import os
import shutil
import tempfile

import pytest
from attr import attrs, attrib

from python_utils.common_objects.workflow.workflow import Workflow
from python_utils.common_objects.workflow.workgraph import WorkGraphNode
from python_utils.common_objects.workflow.common.expansion import (
    ExpansionResult,
    GraphExpansionResult,
    SubgraphSpec,
)
from python_utils.common_objects.workflow.common.step_wrapper import StepWrapper
from python_utils.common_objects.workflow.common.step_result_save_options import StepResultSaveOptions
from python_utils.common_objects.workflow.common.result_pass_down_mode import ResultPassDownMode


# ---------------------------------------------------------------------------
# Workflow hook transparency
# ---------------------------------------------------------------------------

@attrs(slots=False)
class _HookTrackingWorkflow(Workflow):
    """Workflow that records what hooks receive."""

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self._save_dir = tempfile.mkdtemp(prefix="hook_test_")
        self.post_process_results = []
        self.update_state_results = []
        self.on_step_complete_results = []

    def _get_result_path(self, result_id, *args, **kwargs) -> str:
        return os.path.join(self._save_dir, f"{result_id}.pkl")

    def _init_state(self):
        return {"count": 0}

    def _post_process(self, result, *args, **kwargs):
        self.post_process_results.append(result)
        return result

    def _update_state(self, state, result, step, step_name, step_index):
        self.update_state_results.append(result)
        state["count"] += 1
        return state

    def _on_step_complete(self, result, step_name, step_index, state, *args, **kwargs):
        self.on_step_complete_results.append(result)

    def cleanup(self):
        shutil.rmtree(self._save_dir, ignore_errors=True)


class TestWorkflowHookTransparency:
    """Task 23.3: Workflow hooks see unwrapped results."""

    def test_post_process_receives_unwrapped_result(self):
        """_post_process receives the actual result, not ExpansionResult."""
        expanded_step = StepWrapper(lambda x: x + 100, name="expanded")

        def emitter(x):
            return ExpansionResult(
                result=42,
                new_steps=[expanded_step],
            )

        step_a = StepWrapper(emitter, name="emitter")

        wf = _HookTrackingWorkflow(
            steps=[step_a],
            max_expansion_events=5,
            max_total_steps=100,
        )
        try:
            wf.run(1)
            # The first hook call should receive 42 (unwrapped), not ExpansionResult
            assert wf.post_process_results[0] == 42
            assert not isinstance(wf.post_process_results[0], ExpansionResult)
        finally:
            wf.cleanup()

    def test_update_state_receives_unwrapped_result(self):
        """_update_state receives the actual result, not ExpansionResult."""
        expanded_step = StepWrapper(lambda x: x + 100, name="expanded", receives_state=True)

        def emitter(x):
            return ExpansionResult(
                result=42,
                new_steps=[expanded_step],
            )

        step_a = StepWrapper(emitter, name="emitter", receives_state=True)

        wf = _HookTrackingWorkflow(
            steps=[step_a],
            max_expansion_events=5,
            max_total_steps=100,
        )
        try:
            wf.run(1)
            assert wf.update_state_results[0] == 42
            assert not isinstance(wf.update_state_results[0], ExpansionResult)
        finally:
            wf.cleanup()

    def test_on_step_complete_receives_unwrapped_result(self):
        """_on_step_complete receives the actual result, not ExpansionResult."""
        expanded_step = StepWrapper(lambda x: x + 100, name="expanded")

        def emitter(x):
            return ExpansionResult(
                result=42,
                new_steps=[expanded_step],
            )

        step_a = StepWrapper(emitter, name="emitter")

        wf = _HookTrackingWorkflow(
            steps=[step_a],
            max_expansion_events=5,
            max_total_steps=100,
        )
        try:
            wf.run(1)
            assert wf.on_step_complete_results[0] == 42
            assert not isinstance(wf.on_step_complete_results[0], ExpansionResult)
        finally:
            wf.cleanup()


# ---------------------------------------------------------------------------
# WorkGraphNode hook transparency
# ---------------------------------------------------------------------------

class _HookTrackingNode(WorkGraphNode):
    """WorkGraphNode that records what _post_process receives."""

    def __init__(self, save_dir=None, **kwargs):
        super().__init__(**kwargs)
        self._save_dir = save_dir or tempfile.mkdtemp(prefix="hook_node_test_")
        self.post_process_results = []

    def _get_result_path(self, name, *args, **kwargs) -> str:
        os.makedirs(self._save_dir, exist_ok=True)
        return os.path.join(self._save_dir, f"{name}.pkl")

    def _post_process(self, result, *args, **kwargs):
        self.post_process_results.append(result)
        return result


class TestWorkGraphNodeHookTransparency:
    """Task 23.3: WorkGraphNode hooks see unwrapped results."""

    def test_post_process_receives_unwrapped_result(self):
        save_dir = tempfile.mkdtemp(prefix="hook_node_test_")
        try:
            sub_a = WorkGraphNode(
                name="sub_a", value=lambda x: x + 10,
                result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            )

            root = _HookTrackingNode(
                name="root",
                value=lambda x: x,
                save_dir=save_dir,
                result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            )
            root._max_expansion_depth = 5
            root._max_total_nodes = 200

            def emitter(x):
                return GraphExpansionResult(
                    result=99,
                    subgraph=SubgraphSpec(nodes=[sub_a], entry_nodes=[sub_a]),
                )

            root.value = emitter
            root.run(1)

            # _post_process should receive 99 (unwrapped), not GraphExpansionResult
            assert root.post_process_results[0] == 99
            assert not isinstance(root.post_process_results[0], GraphExpansionResult)
        finally:
            shutil.rmtree(save_dir, ignore_errors=True)
