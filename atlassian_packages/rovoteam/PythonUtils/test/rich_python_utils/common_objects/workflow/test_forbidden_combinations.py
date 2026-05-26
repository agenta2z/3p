"""Tests for forbidden combinations (Task 15.3).

Validates: Requirements 27.1, 27.2, 30.1, 30.2
"""
import os
import shutil
import tempfile

import pytest
from attr import attrs, attrib

from python_utils.common_objects.workflow.workflow import Workflow
from python_utils.common_objects.workflow.workgraph import WorkGraphNode, WorkGraph
from python_utils.common_objects.workflow.common.expansion import (
    ExpansionResult,
    GraphExpansionResult,
    SubgraphSpec,
)
from python_utils.common_objects.workflow.common.exceptions import (
    ExpansionConfigError,
)
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
            self._save_dir = tempfile.mkdtemp(prefix="forbidden_test_")
        os.makedirs(self._save_dir, exist_ok=True)
        super().__attrs_post_init__()

    def _get_result_path(self, result_id, *args, **kwargs) -> str:
        return os.path.join(self._save_dir, f"step_{result_id}.pkl")


# ---------------------------------------------------------------------------
# Concrete WorkGraphNode subclass for testing
# ---------------------------------------------------------------------------

class _TestNode(WorkGraphNode):
    def __init__(self, save_dir=None, **kwargs):
        super().__init__(**kwargs)
        self._save_dir = save_dir or tempfile.mkdtemp(prefix="forbidden_test_")

    def _get_result_path(self, name, *args, **kwargs) -> str:
        os.makedirs(self._save_dir, exist_ok=True)
        return os.path.join(self._save_dir, f"{name}.pkl")


@pytest.fixture
def save_dir():
    d = tempfile.mkdtemp(prefix="forbidden_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


def _make_node(name, fn, save_dir, **kw):
    return _TestNode(
        name=name,
        value=fn,
        save_dir=save_dir,
        result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
        **kw,
    )


class TestLoopBackToWithExpansion:
    """Validates: Requirements 27.1, 27.2 — loop_back_to + ExpansionResult is forbidden."""

    def test_loop_back_to_plus_expansion_raises_config_error(self, save_dir):
        """A step with loop_back_to that returns ExpansionResult raises ExpansionConfigError."""
        def expanding_step(x):
            return ExpansionResult(
                result=x,
                new_steps=[StepWrapper(lambda v: v + 1, name="extra")],
            )

        wf = _TestWorkflow(
            steps=[
                StepWrapper(lambda x: x, name="start"),
                StepWrapper(
                    expanding_step,
                    name="looper",
                    loop_back_to="start",
                    loop_condition=lambda state, result: True,
                    max_loop_iterations=3,
                ),
            ],
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            max_expansion_events=1,
            max_total_steps=20,
        )
        with pytest.raises(ExpansionConfigError, match="loop_back_to"):
            wf._run(1)

    def test_step_without_loop_back_to_can_expand(self, save_dir):
        """A step without loop_back_to can return ExpansionResult normally."""
        def expanding_step(x):
            return ExpansionResult(
                result=x * 2,
                new_steps=[StepWrapper(lambda v: v + 10, name="extra")],
            )

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
        result = wf._run(5)
        # 5 -> expander returns 10, extra adds 10 -> 20, final adds 100 -> 120
        assert result == 120


class TestWorkerManagesResumeWithExpansion:
    """Validates: Requirements 30.1, 30.2 — worker_manages_resume + GraphExpansionResult is forbidden."""

    def test_worker_manages_resume_plus_expansion_raises_config_error(self, save_dir):
        """A node with worker_manages_resume=True that returns GraphExpansionResult raises ExpansionConfigError."""
        sub_a = _make_node("sub_a", lambda x: x + 10, save_dir)

        node = _make_node("expander", lambda x: x, save_dir)
        node.worker_manages_resume = True
        node._max_expansion_depth = 5
        node._max_total_nodes = 200

        with pytest.raises(ExpansionConfigError, match="worker_manages_resume"):
            node._handle_graph_expansion(
                GraphExpansionResult(
                    result=42,
                    subgraph=SubgraphSpec(nodes=[sub_a], entry_nodes=[sub_a]),
                ),
            )

    def test_node_without_worker_manages_resume_can_expand(self, save_dir):
        """A node without worker_manages_resume can return GraphExpansionResult normally."""
        sub_a = _make_node("sub_a", lambda x: x + 10, save_dir)

        node = _make_node("expander", lambda x: x, save_dir)
        node._max_expansion_depth = 5
        node._max_total_nodes = 200

        result = node._handle_graph_expansion(
            GraphExpansionResult(
                result=42,
                subgraph=SubgraphSpec(nodes=[sub_a], entry_nodes=[sub_a]),
            ),
        )
        assert result == 42
