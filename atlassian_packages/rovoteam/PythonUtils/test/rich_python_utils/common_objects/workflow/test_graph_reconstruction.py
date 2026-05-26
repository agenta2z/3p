"""Tests for cross-boundary cycle detection and graph reconstruction (Task 24.4).

Covers:
- Cross-boundary cycle detected and rejected
- Graph reconstruction without seed or registry raises ExpansionReplayError
- NextNodesSelector precedence when both GER and NNS have conflicting values
"""
import os
import shutil
import tempfile

import pytest

from python_utils.common_objects.workflow.workgraph import WorkGraphNode, WorkGraph
from python_utils.common_objects.workflow.common.expansion import (
    GraphExpansionResult,
    SubgraphSpec,
)
from python_utils.common_objects.workflow.common.exceptions import (
    ExpansionReplayError,
)
from python_utils.common_objects.workflow.common.result_pass_down_mode import ResultPassDownMode
from python_utils.common_objects.workflow.common.worknode_base import NextNodesSelector


class _TestNode(WorkGraphNode):
    """WorkGraphNode subclass with _get_result_path for tests."""

    def __init__(self, save_dir=None, **kwargs):
        super().__init__(**kwargs)
        self._save_dir = save_dir or tempfile.mkdtemp(prefix="graph_recon_test_")

    def _get_result_path(self, name, *args, **kwargs) -> str:
        os.makedirs(self._save_dir, exist_ok=True)
        return os.path.join(self._save_dir, f"{name}.pkl")


def _make_node(name, fn, save_dir, **kw):
    return _TestNode(
        name=name, value=fn, save_dir=save_dir,
        result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg, **kw,
    )


@pytest.fixture
def save_dir():
    d = tempfile.mkdtemp(prefix="graph_recon_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


class TestCrossBoundaryCycleDetection:
    """Task 24.4: Cross-boundary cycle detection."""

    def test_cross_boundary_cycle_detected_and_rejected(self, save_dir):
        """A cross-boundary cycle through existing topology is rejected.
        
        Setup: root → downstream, downstream → root (existing back-edge)
        After insert mode: root → sub_a → downstream → root (cycle!)
        """
        root = _make_node("root", lambda x: x, save_dir)
        downstream = _make_node("downstream", lambda x: x, save_dir)
        root.add_next(downstream)
        # Create existing back-edge: downstream → root
        downstream.add_next(root)

        sub_a = _make_node("sub_a", lambda x: x, save_dir)

        root._max_expansion_depth = 5
        root._max_total_nodes = 200

        def emitter(x):
            return GraphExpansionResult(
                result=x,
                subgraph=SubgraphSpec(nodes=[sub_a], entry_nodes=[sub_a]),
            )

        root.value = emitter
        with pytest.raises(ValueError, match="Cross-boundary cycle detected"):
            root.run(1)

    def test_leaf_expansion_cross_boundary_cycle_detected(self, save_dir):
        """Leaf node expansion with cycle back to root is detected via _validate_no_cross_boundary_cycles."""
        # Use _validate_no_cross_boundary_cycles directly to test leaf case
        root = _make_node("root", lambda x: x, save_dir)

        sub_a = _make_node("sub_a", lambda x: x, save_dir)
        sub_b = _make_node("sub_b", lambda x: x, save_dir)
        sub_a.add_next(sub_b)

        root._max_expansion_depth = 5
        root._max_total_nodes = 200

        # Manually wire: root → sub_a (as if expansion happened)
        root.add_next(sub_a)
        # Then wire sub_b → root (creating a cycle)
        sub_b.add_next(root)

        # Now validate — should detect the cycle
        with pytest.raises(ValueError, match="Cross-boundary cycle detected"):
            root._validate_no_cross_boundary_cycles([sub_a, sub_b])


class TestGraphReconstruction:
    """Task 24.4: Graph reconstruction tests."""

    def test_reconstruction_without_seed_or_registry_raises_error(self, save_dir):
        """Graph reconstruction without seed or registry raises ExpansionReplayError."""

        class _TestGraph(WorkGraph):
            def __init__(self, save_dir, **kwargs):
                super().__init__(**kwargs)
                self._save_dir = save_dir

            def _get_result_path(self, result_id, *args, **kwargs) -> str:
                os.makedirs(self._save_dir, exist_ok=True)
                return os.path.join(self._save_dir, f"{result_id}.pkl")

        # Create a node that expanded
        root = _make_node("root", lambda x: x + 1, save_dir)
        root._max_expansion_depth = 5
        root._max_total_nodes = 200

        # Simulate a persisted expansion record (as if expansion happened in a prior run)
        expansion_record = {
            'expanding_node': 'root',
            'expansion_id': 'test_expansion',
            'subgraph': {'nodes': [], 'entry_node_names': []},
            # No seed, no factory_module, no factory_qualname
        }
        root._save_result(
            expansion_record,
            output_path=root._get_result_path("__graph_expansion__root"),
        )

        graph = _TestGraph(
            save_dir=save_dir,
            start_nodes=[root],
            max_expansion_depth=5,
            max_total_nodes=200,
            # No subgraph_registry
        )

        with pytest.raises(ExpansionReplayError, match="Cannot reconstruct"):
            graph._reconstruct_graph_expansions()


class TestNNSPrecedence:
    """Task 24.4: NextNodesSelector precedence with GraphExpansionResult."""

    def test_ger_include_self_takes_precedence_over_nns(self, save_dir):
        """GraphExpansionResult.include_self overrides NextNodesSelector.include_self."""
        call_count = [0]

        sub_a = _make_node("sub_a", lambda x: x + 10, save_dir)

        root = _make_node("root", lambda x: x, save_dir)
        root.add_next(root)  # self-edge
        root._max_expansion_depth = 5
        root._max_total_nodes = 200

        def emitter(x):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call: expand with include_self=True
                return GraphExpansionResult(
                    result=x,
                    subgraph=SubgraphSpec(nodes=[sub_a], entry_nodes=[sub_a]),
                    include_self=True,
                )
            else:
                # Second call: stop self-loop
                return NextNodesSelector(include_self=False, include_others=True, result=x + 1)

        root.value = emitter
        result = root.run(1)

        # Should have looped once (include_self=True from GER), then stopped
        assert call_count[0] == 2
