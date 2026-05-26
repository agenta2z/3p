"""Tests for non-leaf insert mode (Task 21.3).

Covers:
- Non-leaf insert mode rewires topology correctly (Node → Subgraph → OriginalDownstream)
- Leaf node with insert mode behaves same as default
- Bidirectional edges correct after insert mode rewiring
- Post-wiring cycle check catches cross-boundary cycles
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
from python_utils.common_objects.workflow.common.result_pass_down_mode import ResultPassDownMode


class _TestNode(WorkGraphNode):
    """WorkGraphNode subclass with _get_result_path for expansion tests."""

    def __init__(self, save_dir=None, **kwargs):
        super().__init__(**kwargs)
        self._save_dir = save_dir or tempfile.mkdtemp(prefix="insert_mode_test_")

    def _get_result_path(self, name, *args, **kwargs) -> str:
        os.makedirs(self._save_dir, exist_ok=True)
        return os.path.join(self._save_dir, f"{name}.pkl")


def _make_node(name, fn, save_dir, pass_down=ResultPassDownMode.ResultAsFirstArg, **kw):
    return _TestNode(
        name=name, value=fn, save_dir=save_dir,
        result_pass_down_mode=pass_down, **kw,
    )


@pytest.fixture
def save_dir():
    d = tempfile.mkdtemp(prefix="insert_mode_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


class TestInsertMode:
    """Task 21.3: Tests for non-leaf insert mode."""

    def test_non_leaf_insert_mode_rewires_topology(self, save_dir):
        """Non-leaf node expansion rewires: Node → Subgraph → OriginalDownstream."""
        call_log = []

        # Build: root → downstream
        root = _make_node("root", lambda x: x, save_dir)
        downstream = _make_node("downstream", lambda x: (call_log.append("downstream"), x + 100)[1], save_dir)
        root.add_next(downstream)

        # Subgraph: sub_a → sub_b
        sub_a = _make_node("sub_a", lambda x: (call_log.append("sub_a"), x + 10)[1], save_dir)
        sub_b = _make_node("sub_b", lambda x: (call_log.append("sub_b"), x + 20)[1], save_dir)
        sub_a.add_next(sub_b)

        # Set expansion limits
        root._max_expansion_depth = 5
        root._max_total_nodes = 200

        # Emitter returns GraphExpansionResult
        def emitter(x):
            return GraphExpansionResult(
                result=x,
                subgraph=SubgraphSpec(nodes=[sub_a, sub_b], entry_nodes=[sub_a]),
            )

        root.value = emitter
        result = root.run(1)

        # Verify topology: root → sub_a → sub_b → downstream
        assert "sub_a" in call_log
        assert "sub_b" in call_log
        assert "downstream" in call_log
        # sub_a should run before sub_b, sub_b before downstream
        assert call_log.index("sub_a") < call_log.index("sub_b")
        assert call_log.index("sub_b") < call_log.index("downstream")

    def test_leaf_node_insert_mode_behaves_same_as_default(self, save_dir):
        """Leaf node expansion (no downstream) works the same regardless of attach_mode."""
        call_log = []

        root = _make_node("root", lambda x: x, save_dir)
        sub_a = _make_node("sub_a", lambda x: (call_log.append("sub_a"), x + 10)[1], save_dir)

        root._max_expansion_depth = 5
        root._max_total_nodes = 200

        def emitter(x):
            return GraphExpansionResult(
                result=x,
                subgraph=SubgraphSpec(nodes=[sub_a], entry_nodes=[sub_a]),
                attach_mode='insert',
            )

        root.value = emitter
        result = root.run(1)

        assert "sub_a" in call_log
        # sub_a is now downstream of root
        assert sub_a in root.next

    def test_bidirectional_edges_correct_after_insert_mode(self, save_dir):
        """After insert mode rewiring, previous/next edges are bidirectionally consistent."""
        root = _make_node("root", lambda x: x, save_dir)
        downstream = _make_node("downstream", lambda x: x, save_dir)
        root.add_next(downstream)

        sub_a = _make_node("sub_a", lambda x: x, save_dir)
        sub_b = _make_node("sub_b", lambda x: x, save_dir)
        sub_a.add_next(sub_b)

        root._max_expansion_depth = 5
        root._max_total_nodes = 200

        def emitter(x):
            return GraphExpansionResult(
                result=x,
                subgraph=SubgraphSpec(nodes=[sub_a, sub_b], entry_nodes=[sub_a]),
            )

        root.value = emitter
        root.run(1)

        # root → sub_a
        assert sub_a in root.next
        assert root in sub_a.previous

        # sub_a → sub_b
        assert sub_b in sub_a.next
        assert sub_a in sub_b.previous

        # sub_b → downstream
        assert downstream in sub_b.next
        assert sub_b in downstream.previous

        # root should NOT have downstream as direct next anymore
        assert downstream not in root.next

    def test_post_wiring_cycle_check_catches_cross_boundary_cycles(self, save_dir):
        """Cross-boundary cycle through existing graph topology is detected.
        
        Setup: root → downstream, downstream → root (existing back-edge)
        After insert mode: root → sub_a → sub_b → downstream → root (cycle!)
        """
        root = _make_node("root", lambda x: x, save_dir)
        downstream = _make_node("downstream", lambda x: x, save_dir)
        root.add_next(downstream)
        # Create existing back-edge: downstream → root
        downstream.add_next(root)

        sub_a = _make_node("sub_a", lambda x: x, save_dir)
        sub_b = _make_node("sub_b", lambda x: x, save_dir)
        sub_a.add_next(sub_b)

        root._max_expansion_depth = 5
        root._max_total_nodes = 200

        def emitter(x):
            return GraphExpansionResult(
                result=x,
                subgraph=SubgraphSpec(nodes=[sub_a, sub_b], entry_nodes=[sub_a]),
            )

        root.value = emitter
        with pytest.raises(ValueError, match="Cross-boundary cycle detected"):
            root.run(1)
