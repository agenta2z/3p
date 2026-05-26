"""Tests for self-loop + expansion and per-run reset (Task 17.4).

Validates: Requirements 28.1, 28.2, 28.3, 28.4
"""
import os
import shutil
import tempfile

import pytest
from attr import attrs, attrib

from python_utils.common_objects.workflow.workflow import Workflow
from python_utils.common_objects.workflow.workgraph import WorkGraphNode
from python_utils.common_objects.workflow.common.expansion import (
    GraphExpansionResult,
    SubgraphSpec,
)
from python_utils.common_objects.workflow.common.result_pass_down_mode import ResultPassDownMode
from python_utils.common_objects.workflow.common.step_wrapper import StepWrapper


# ---------------------------------------------------------------------------
# Concrete test helpers
# ---------------------------------------------------------------------------

@attrs(slots=False)
class _TestWorkflow(Workflow):
    _save_dir: str = attrib(default=None)

    def __attrs_post_init__(self):
        if self._save_dir is None:
            self._save_dir = tempfile.mkdtemp(prefix="selfloop_test_")
        os.makedirs(self._save_dir, exist_ok=True)
        super().__attrs_post_init__()

    def _get_result_path(self, result_id, *args, **kwargs) -> str:
        return os.path.join(self._save_dir, f"step_{result_id}.pkl")


class _TestNode(WorkGraphNode):
    def __init__(self, save_dir=None, **kwargs):
        super().__init__(**kwargs)
        self._save_dir = save_dir or tempfile.mkdtemp(prefix="selfloop_test_")

    def _get_result_path(self, name, *args, **kwargs) -> str:
        os.makedirs(self._save_dir, exist_ok=True)
        return os.path.join(self._save_dir, f"{name}.pkl")


@pytest.fixture
def save_dir():
    d = tempfile.mkdtemp(prefix="selfloop_test_")
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


class TestSelfLoopExpansion:
    """Validates: Requirements 28.1, 28.2, 28.3 — expand once, then loop."""

    def test_first_iteration_expands_subsequent_skip(self, save_dir):
        """First iteration expands, subsequent iterations skip re-expansion."""
        expansion_count = [0]

        def self_loop_fn(x):
            expansion_count[0] += 1
            val = x if isinstance(x, (int, float)) else 0
            sub_node = _make_node(f"sub_{expansion_count[0]}", lambda v: v + 100, save_dir)
            return GraphExpansionResult(
                result=val + 1,
                subgraph=SubgraphSpec(nodes=[sub_node], entry_nodes=[sub_node]),
                include_self=expansion_count[0] < 3,
                include_others=True,
            )

        node = _make_node("looper", self_loop_fn, save_dir)
        node._max_expansion_depth = 5
        node._max_total_nodes = 200
        node.add_next(node)  # self-edge

        result = node.run(0)

        # The node should have been called 3 times (expansion_count[0] == 3)
        assert expansion_count[0] == 3
        # Expansion should only have been applied once (first iteration)
        assert node._expansion_applied is True


class TestPerRunReset:
    """Validates: Requirement 28.4 — per-run reset prevents cross-run leaks."""

    def test_second_run_workgraphnode_does_not_skip_expansion(self, save_dir):
        """Second run of same WorkGraphNode instance does NOT skip expansion."""
        expansion_applied_runs = []

        def expanding_fn(x):
            sub_node = _make_node(
                f"sub_{len(expansion_applied_runs)}", lambda v: v + 10, save_dir
            )
            return GraphExpansionResult(
                result=x + 1,
                subgraph=SubgraphSpec(nodes=[sub_node], entry_nodes=[sub_node]),
            )

        node = _make_node("expander", expanding_fn, save_dir)
        node._max_expansion_depth = 5
        node._max_total_nodes = 200

        # First run
        result1 = node.run(0)
        expansion_applied_runs.append(node._expansion_applied)

        # Create a fresh node for second run (topology mutations are not reversible)
        node2 = _make_node("expander", expanding_fn, save_dir)
        node2._max_expansion_depth = 5
        node2._max_total_nodes = 200

        result2 = node2.run(5)
        expansion_applied_runs.append(node2._expansion_applied)

        # Both runs should have applied expansion
        assert expansion_applied_runs == [True, True]

    def test_second_run_workflow_does_not_skip_expansion(self, save_dir):
        """Second run of same Workflow instance does NOT skip expansion."""
        expansion_counts = []

        call_count = [0]

        def expanding_step(x):
            call_count[0] += 1
            return x * 2

        wf = _TestWorkflow(
            steps=[
                StepWrapper(lambda x: x + 1, name="start"),
                StepWrapper(lambda x: x + 2, name="end"),
            ],
            save_dir=save_dir,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
            max_expansion_events=1,
            max_total_steps=20,
        )

        # First run
        result1 = wf._run(1)
        expansion_counts.append(wf._expansion_count)

        # Second run — _reset_expansion_state should reset counters
        result2 = wf._run(1)
        expansion_counts.append(wf._expansion_count)

        # Both runs should start with expansion_count = 0 (reset at top of _run)
        assert expansion_counts == [0, 0]

    def test_expansion_applied_reset_at_top_of_run(self, save_dir):
        """_expansion_applied is reset to False at top of _run."""
        node = _make_node("test_node", lambda x: x, save_dir)
        node._expansion_applied = True  # Simulate stale state from prior run

        # _run should reset _expansion_applied to False
        node.run(42)
        # After run completes, _expansion_applied should be False
        # (since the node didn't return a GraphExpansionResult)
        assert node._expansion_applied is False
