"""
Unit tests for materialize_subgraph function.

Tests cover simple chains, branching graphs, edge type filtering,
depth limiting, cycle handling, non-existent start node, and
compatibility with bfs_traversal and dfs_traversal.
"""

import pytest

from python_utils.algorithms.graph.traversal import bfs_traversal, dfs_traversal
from python_utils.service_utils.graph_service.graph_node import GraphEdge, GraphNode
from python_utils.service_utils.graph_service.materialize import materialize_subgraph
from python_utils.service_utils.graph_service.memory_graph_service import (
    MemoryGraphService,
)


def _build_chain_service():
    """Build a simple chain: A -> B -> C."""
    svc = MemoryGraphService()
    svc.add_node(GraphNode(node_id="A", node_type="step", label="Node A"))
    svc.add_node(GraphNode(node_id="B", node_type="step", label="Node B"))
    svc.add_node(GraphNode(node_id="C", node_type="step", label="Node C"))
    svc.add_edge(GraphEdge(source_id="A", target_id="B", edge_type="next"))
    svc.add_edge(GraphEdge(source_id="B", target_id="C", edge_type="next"))
    return svc


def _build_branching_service():
    """Build a branching graph: A -> B, A -> C."""
    svc = MemoryGraphService()
    svc.add_node(GraphNode(node_id="A", node_type="step", label="Node A"))
    svc.add_node(GraphNode(node_id="B", node_type="step", label="Node B"))
    svc.add_node(GraphNode(node_id="C", node_type="step", label="Node C"))
    svc.add_edge(GraphEdge(source_id="A", target_id="B", edge_type="next"))
    svc.add_edge(GraphEdge(source_id="A", target_id="C", edge_type="next"))
    return svc


def _build_mixed_edge_service():
    """Build a graph with mixed edge types: A -next-> B, A -alt-> C, B -next-> D."""
    svc = MemoryGraphService()
    for nid in ["A", "B", "C", "D"]:
        svc.add_node(GraphNode(node_id=nid, node_type="step"))
    svc.add_edge(GraphEdge(source_id="A", target_id="B", edge_type="next"))
    svc.add_edge(GraphEdge(source_id="A", target_id="C", edge_type="alt"))
    svc.add_edge(GraphEdge(source_id="B", target_id="D", edge_type="next"))
    return svc


def _build_cycle_service():
    """Build a graph with a cycle: A -> B -> C -> A."""
    svc = MemoryGraphService()
    svc.add_node(GraphNode(node_id="A", node_type="step"))
    svc.add_node(GraphNode(node_id="B", node_type="step"))
    svc.add_node(GraphNode(node_id="C", node_type="step"))
    svc.add_edge(GraphEdge(source_id="A", target_id="B", edge_type="next"))
    svc.add_edge(GraphEdge(source_id="B", target_id="C", edge_type="next"))
    svc.add_edge(GraphEdge(source_id="C", target_id="A", edge_type="next"))
    return svc


class TestMaterializeSubgraphSimpleChain:
    """Tests for materializing a simple chain: A -> B -> C."""

    def test_chain_depth_1(self):
        svc = _build_chain_service()
        start = materialize_subgraph(svc, "A", depth=1)
        assert start.node_id == "A"
        assert start.label == "Node A"
        assert start.next is not None
        assert len(start.next) == 1
        assert start.next[0].node_id == "B"

    def test_chain_depth_2(self):
        svc = _build_chain_service()
        start = materialize_subgraph(svc, "A", depth=2)
        assert start.node_id == "A"
        assert len(start.next) == 1
        b = start.next[0]
        assert b.node_id == "B"
        assert b.next is not None
        assert len(b.next) == 1
        assert b.next[0].node_id == "C"

    def test_chain_depth_2_c_has_no_next(self):
        svc = _build_chain_service()
        start = materialize_subgraph(svc, "A", depth=2)
        c = start.next[0].next[0]
        assert c.node_id == "C"
        assert c.next is None or len(c.next) == 0 if isinstance(c.next, list) else c.next is None

    def test_chain_depth_0_returns_start_only(self):
        svc = _build_chain_service()
        start = materialize_subgraph(svc, "A", depth=0)
        assert start.node_id == "A"
        assert start.next is None


class TestMaterializeSubgraphBranching:
    """Tests for materializing a branching graph: A -> B, A -> C."""

    def test_branching_depth_1(self):
        svc = _build_branching_service()
        start = materialize_subgraph(svc, "A", depth=1)
        assert start.node_id == "A"
        assert start.next is not None
        assert len(start.next) == 2
        child_ids = sorted([n.node_id for n in start.next])
        assert child_ids == ["B", "C"]

    def test_branching_children_have_previous_set(self):
        svc = _build_branching_service()
        start = materialize_subgraph(svc, "A", depth=1)
        for child in start.next:
            assert child.previous is not None
            assert len(child.previous) == 1
            assert child.previous[0].node_id == "A"
            assert child.previous[0] is start


class TestMaterializeSubgraphEdgeTypeFiltering:
    """Tests for edge type filtering during materialization."""

    def test_filter_by_edge_type(self):
        svc = _build_mixed_edge_service()
        start = materialize_subgraph(svc, "A", edge_type="next", depth=2)
        assert start.node_id == "A"
        assert start.next is not None
        assert len(start.next) == 1
        assert start.next[0].node_id == "B"
        # B -> D via "next" edge
        b = start.next[0]
        assert b.next is not None
        assert len(b.next) == 1
        assert b.next[0].node_id == "D"

    def test_filter_by_alt_edge_type(self):
        svc = _build_mixed_edge_service()
        start = materialize_subgraph(svc, "A", edge_type="alt", depth=1)
        assert start.next is not None
        assert len(start.next) == 1
        assert start.next[0].node_id == "C"

    def test_no_edge_type_follows_all(self):
        svc = _build_mixed_edge_service()
        start = materialize_subgraph(svc, "A", edge_type=None, depth=1)
        assert start.next is not None
        assert len(start.next) == 2
        child_ids = sorted([n.node_id for n in start.next])
        assert child_ids == ["B", "C"]


class TestMaterializeSubgraphDepthLimiting:
    """Tests for depth limiting."""

    def test_depth_limits_traversal(self):
        svc = _build_chain_service()
        start = materialize_subgraph(svc, "A", depth=1)
        # Should only reach B, not C
        assert len(start.next) == 1
        assert start.next[0].node_id == "B"
        b = start.next[0]
        # B should have no next since depth=1 stops at B
        assert b.next is None


class TestMaterializeSubgraphCycleHandling:
    """Tests for cycle handling (no infinite loop)."""

    def test_cycle_does_not_loop_infinitely(self):
        svc = _build_cycle_service()
        # Depth 10 should not cause infinite loop even with A->B->C->A cycle
        start = materialize_subgraph(svc, "A", depth=10)
        assert start.node_id == "A"

    def test_cycle_links_back_to_existing_copy(self):
        svc = _build_cycle_service()
        start = materialize_subgraph(svc, "A", depth=3)
        # A -> B -> C -> A (back to start copy)
        assert start.node_id == "A"
        b = start.next[0]
        assert b.node_id == "B"
        c = b.next[0]
        assert c.node_id == "C"
        # C should link back to the same start copy
        assert c.next is not None
        assert len(c.next) == 1
        assert c.next[0].node_id == "A"
        assert c.next[0] is start  # Same object reference


class TestMaterializeSubgraphNonExistentStart:
    """Tests for non-existent start node."""

    def test_nonexistent_start_raises_value_error(self):
        svc = MemoryGraphService()
        with pytest.raises(ValueError, match="Start node 'missing' does not exist"):
            materialize_subgraph(svc, "missing")

    def test_nonexistent_start_with_namespace_raises_value_error(self):
        svc = MemoryGraphService()
        with pytest.raises(ValueError, match="namespace"):
            materialize_subgraph(svc, "missing", namespace="ns1")


class TestMaterializeSubgraphCopiesNodes:
    """Tests that materialized nodes are copies, not the stored originals."""

    def test_returned_nodes_are_copies(self):
        svc = MemoryGraphService()
        original = GraphNode(node_id="A", node_type="step", label="Original")
        svc.add_node(original)
        start = materialize_subgraph(svc, "A", depth=0)
        assert start.node_id == "A"
        assert start is not original
        # Modifying the copy should not affect the stored node
        start.label = "Modified"
        stored = svc.get_node("A")
        assert stored.label == "Original"

    def test_linked_nodes_are_copies(self):
        svc = _build_chain_service()
        start = materialize_subgraph(svc, "A", depth=1)
        b_copy = start.next[0]
        b_stored = svc.get_node("B")
        assert b_copy is not b_stored
        assert b_copy.node_id == b_stored.node_id

    def test_properties_are_preserved_in_copies(self):
        svc = MemoryGraphService()
        svc.add_node(GraphNode(
            node_id="A", node_type="step",
            properties={"key": "value", "count": 42}
        ))
        start = materialize_subgraph(svc, "A", depth=0)
        assert start.properties == {"key": "value", "count": 42}


class TestMaterializeSubgraphNextPreviousLinks:
    """Tests that next/previous links are correctly set."""

    def test_next_links_set(self):
        svc = _build_chain_service()
        start = materialize_subgraph(svc, "A", depth=2)
        assert start.next is not None
        assert len(start.next) == 1
        assert start.next[0].node_id == "B"
        assert start.next[0].next is not None
        assert len(start.next[0].next) == 1
        assert start.next[0].next[0].node_id == "C"

    def test_previous_links_set(self):
        svc = _build_chain_service()
        start = materialize_subgraph(svc, "A", depth=2)
        b = start.next[0]
        c = b.next[0]
        # B's previous should point to A
        assert b.previous is not None
        assert len(b.previous) == 1
        assert b.previous[0] is start
        # C's previous should point to B
        assert c.previous is not None
        assert len(c.previous) == 1
        assert c.previous[0] is b

    def test_start_node_has_no_previous(self):
        svc = _build_chain_service()
        start = materialize_subgraph(svc, "A", depth=1)
        assert start.previous is None


class TestMaterializeSubgraphBfsCompatibility:
    """Tests that materialized nodes are compatible with bfs_traversal."""

    def test_bfs_traversal_on_chain(self):
        svc = _build_chain_service()
        start = materialize_subgraph(svc, "A", depth=2)
        visited = list(bfs_traversal(start, {GraphNode: 'next'}))
        visited_ids = [n.node_id for n in visited]
        assert visited_ids == ["A", "B", "C"]

    def test_bfs_traversal_on_branching(self):
        svc = _build_branching_service()
        start = materialize_subgraph(svc, "A", depth=1)
        visited = list(bfs_traversal(start, {GraphNode: 'next'}))
        visited_ids = [n.node_id for n in visited]
        assert visited_ids[0] == "A"
        assert sorted(visited_ids[1:]) == ["B", "C"]

    def test_bfs_traversal_on_cycle(self):
        svc = _build_cycle_service()
        start = materialize_subgraph(svc, "A", depth=3)
        visited = list(bfs_traversal(start, {GraphNode: 'next'}))
        visited_ids = [n.node_id for n in visited]
        # BFS should visit each node exactly once despite cycle
        assert sorted(visited_ids) == ["A", "B", "C"]


class TestMaterializeSubgraphDfsCompatibility:
    """Tests that materialized nodes are compatible with dfs_traversal."""

    def test_dfs_traversal_on_chain(self):
        svc = _build_chain_service()
        start = materialize_subgraph(svc, "A", depth=2)
        visited = list(dfs_traversal(start, {GraphNode: 'next'}))
        visited_ids = [n.node_id for n in visited]
        assert visited_ids == ["A", "B", "C"]

    def test_dfs_traversal_on_cycle(self):
        svc = _build_cycle_service()
        start = materialize_subgraph(svc, "A", depth=3)
        visited = list(dfs_traversal(start, {GraphNode: 'next'}))
        visited_ids = [n.node_id for n in visited]
        # DFS should visit each node exactly once despite cycle
        assert sorted(visited_ids) == ["A", "B", "C"]


class TestMaterializeSubgraphNamespace:
    """Tests for namespace-scoped materialization."""

    def test_materialize_with_namespace(self):
        svc = MemoryGraphService()
        svc.add_node(GraphNode(node_id="A", node_type="step"), namespace="ns1")
        svc.add_node(GraphNode(node_id="B", node_type="step"), namespace="ns1")
        svc.add_edge(
            GraphEdge(source_id="A", target_id="B", edge_type="next"),
            namespace="ns1",
        )
        start = materialize_subgraph(svc, "A", depth=1, namespace="ns1")
        assert start.node_id == "A"
        assert start.next is not None
        assert len(start.next) == 1
        assert start.next[0].node_id == "B"

    def test_materialize_wrong_namespace_raises(self):
        svc = MemoryGraphService()
        svc.add_node(GraphNode(node_id="A", node_type="step"), namespace="ns1")
        with pytest.raises(ValueError):
            materialize_subgraph(svc, "A", depth=1, namespace="ns2")


class TestMaterializeSubgraphValueField:
    """Tests that the value field is correctly set on materialized nodes."""

    def test_value_equals_node_id(self):
        svc = _build_chain_service()
        start = materialize_subgraph(svc, "A", depth=2)
        assert start.value == "A"
        assert start.next[0].value == "B"
        assert start.next[0].next[0].value == "C"
