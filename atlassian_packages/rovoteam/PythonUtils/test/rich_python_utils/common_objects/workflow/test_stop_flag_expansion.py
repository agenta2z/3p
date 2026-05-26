"""Tests for stop-flag composition with expansion (Task 18.2).

Validates: Requirements 29.1, 29.2
"""
import os
import shutil
import tempfile

import pytest

from python_utils.common_objects.workflow.workgraph import WorkGraphNode
from python_utils.common_objects.workflow.common.expansion import (
    GraphExpansionResult,
    SubgraphSpec,
)
from python_utils.common_objects.workflow.common.result_pass_down_mode import ResultPassDownMode
from python_utils.common_objects.workflow.common.worknode_base import (
    WorkGraphStopFlags,
)


# ---------------------------------------------------------------------------
# Concrete test helpers
# ---------------------------------------------------------------------------

class _TestNode(WorkGraphNode):
    def __init__(self, save_dir=None, **kwargs):
        super().__init__(**kwargs)
        self._save_dir = save_dir or tempfile.mkdtemp(prefix="stopflag_test_")

    def _get_result_path(self, name, *args, **kwargs) -> str:
        os.makedirs(self._save_dir, exist_ok=True)
        return os.path.join(self._save_dir, f"{name}.pkl")


@pytest.fixture
def save_dir():
    d = tempfile.mkdtemp(prefix="stopflag_test_")
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


class TestTerminateWithExpansion:
    """Validates: Requirement 29.1 — (Terminate, GraphExpansionResult) applies expansion then stops."""

    def test_terminate_plus_expansion_applies_expansion_then_stops(self, save_dir):
        """(Terminate, GraphExpansionResult) applies expansion for observability, then halts fan-out."""
        sub_executed = [False]

        def sub_fn(x):
            sub_executed[0] = True
            return x + 10

        sub_node = _make_node("sub_a", sub_fn, save_dir)

        def expanding_fn(x):
            return (
                WorkGraphStopFlags.Terminate,
                GraphExpansionResult(
                    result=x + 1,
                    subgraph=SubgraphSpec(nodes=[sub_node], entry_nodes=[sub_node]),
                ),
            )

        # Leaf node — no downstream before expansion
        node = _make_node("expander", expanding_fn, save_dir)
        node._max_expansion_depth = 5
        node._max_total_nodes = 200

        result = node.run(0)

        # Expansion should have been applied (sub_node attached)
        assert node._expansion_applied is True
        # But sub_node should NOT have executed due to Terminate
        assert sub_executed[0] is False
        # Result should be a tuple (Terminate, result) since stop_flag != Continue
        assert isinstance(result, tuple)
        assert result[0] == WorkGraphStopFlags.Terminate


class TestAbstainResultWithExpansion:
    """Validates: Requirement 29.2 — (AbstainResult, GraphExpansionResult) applies expansion, fans out, no merge."""

    def test_abstain_plus_expansion_applies_expansion_fans_out(self, save_dir):
        """(AbstainResult, GraphExpansionResult) applies expansion, fans out with abstain notification."""
        sub_node = _make_node("sub_a", lambda x: x + 10, save_dir)

        def expanding_fn(x):
            return (
                WorkGraphStopFlags.AbstainResult,
                GraphExpansionResult(
                    result=x + 1,
                    subgraph=SubgraphSpec(nodes=[sub_node], entry_nodes=[sub_node]),
                ),
            )

        node = _make_node("expander", expanding_fn, save_dir)
        node._max_expansion_depth = 5
        node._max_total_nodes = 200

        result = node.run(0)

        # Expansion should have been applied (topology mutated for observability)
        assert node._expansion_applied is True
        # Sub node should be attached as downstream
        assert sub_node in node.next
