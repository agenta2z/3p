"""
Unit tests for FileGraphService.

Tests cover core CRUD operations for nodes and edges, cascade delete,
get_neighbors BFS traversal, edge direction filtering, namespace handling,
context manager protocol, and edge cases.

Follows the same test patterns as test_memory_graph.py.
"""

from python_utils.service_utils.graph_service.graph_node import GraphEdge, GraphNode
from python_utils.service_utils.graph_service.file_graph_service import (
    FileGraphService,
)

import pytest


class TestFileGraphServiceNodeOperations:
    """Tests for basic add_node/get_node/remove_node operations."""

    def test_add_and_get_node(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        node = GraphNode(node_id="n1", node_type="person", label="Alice")
        svc.add_node(node)
        result = svc.get_node("n1")
        assert result is not None
        assert result.node_id == "n1"
        assert result.node_type == "person"
        assert result.label == "Alice"

    def test_get_nonexistent_node_returns_none(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        assert svc.get_node("nonexistent") is None

    def test_get_node_from_empty_namespace_returns_none(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        assert svc.get_node("n1", namespace="empty_ns") is None

    def test_add_node_upsert_overwrites(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        node1 = GraphNode(node_id="n1", node_type="person", label="Alice")
        node2 = GraphNode(node_id="n1", node_type="person", label="Bob")
        svc.add_node(node1)
        svc.add_node(node2)
        result = svc.get_node("n1")
        assert result.label == "Bob"

    def test_add_node_with_properties(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        node = GraphNode(
            node_id="n1", node_type="person",
            label="Alice", properties={"age": 30, "city": "NYC"}
        )
        svc.add_node(node)
        result = svc.get_node("n1")
        assert result.properties == {"age": 30, "city": "NYC"}

    def test_remove_existing_node(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        node = GraphNode(node_id="n1", node_type="person")
        svc.add_node(node)
        assert svc.remove_node("n1") is True
        assert svc.get_node("n1") is None

    def test_remove_nonexistent_node_returns_false(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        assert svc.remove_node("nonexistent") is False

    def test_remove_node_from_empty_namespace_returns_false(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        assert svc.remove_node("n1", namespace="empty_ns") is False


class TestFileGraphServiceEdgeOperations:
    """Tests for add_edge/get_edges/remove_edge operations."""

    def test_add_and_get_edge(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(node_id="n1", node_type="person"))
        svc.add_node(GraphNode(node_id="n2", node_type="person"))
        edge = GraphEdge(source_id="n1", target_id="n2", edge_type="knows")
        svc.add_edge(edge)
        edges = svc.get_edges("n1", direction="outgoing")
        assert len(edges) == 1
        assert edges[0].source_id == "n1"
        assert edges[0].target_id == "n2"
        assert edges[0].edge_type == "knows"

    def test_add_edge_missing_source_raises_value_error(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(node_id="n2", node_type="person"))
        edge = GraphEdge(source_id="missing", target_id="n2", edge_type="knows")
        with pytest.raises(ValueError, match="Source node 'missing' does not exist"):
            svc.add_edge(edge)

    def test_add_edge_missing_target_raises_value_error(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(node_id="n1", node_type="person"))
        edge = GraphEdge(source_id="n1", target_id="missing", edge_type="knows")
        with pytest.raises(ValueError, match="Target node 'missing' does not exist"):
            svc.add_edge(edge)

    def test_add_edge_both_missing_raises_value_error(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        edge = GraphEdge(source_id="missing1", target_id="missing2", edge_type="knows")
        with pytest.raises(ValueError):
            svc.add_edge(edge)

    def test_add_edge_with_properties(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(node_id="n1", node_type="person"))
        svc.add_node(GraphNode(node_id="n2", node_type="person"))
        edge = GraphEdge(
            source_id="n1", target_id="n2", edge_type="knows",
            properties={"since": 2020, "strength": 0.9}
        )
        svc.add_edge(edge)
        edges = svc.get_edges("n1")
        assert edges[0].properties == {"since": 2020, "strength": 0.9}

    def test_remove_existing_edge(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(node_id="n1", node_type="person"))
        svc.add_node(GraphNode(node_id="n2", node_type="person"))
        svc.add_edge(GraphEdge(source_id="n1", target_id="n2", edge_type="knows"))
        assert svc.remove_edge("n1", "n2", "knows") is True
        assert svc.get_edges("n1") == []

    def test_remove_nonexistent_edge_returns_false(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        assert svc.remove_edge("n1", "n2", "knows") is False

    def test_remove_edge_wrong_type_returns_false(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(node_id="n1", node_type="person"))
        svc.add_node(GraphNode(node_id="n2", node_type="person"))
        svc.add_edge(GraphEdge(source_id="n1", target_id="n2", edge_type="knows"))
        assert svc.remove_edge("n1", "n2", "likes") is False


class TestFileGraphServiceEdgeDirectionFiltering:
    """Tests for get_edges direction and edge_type filtering."""

    def _setup_triangle(self, tmp_path):
        """Create a triangle graph: n1->n2, n2->n3, n3->n1."""
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(node_id="n1", node_type="person"))
        svc.add_node(GraphNode(node_id="n2", node_type="person"))
        svc.add_node(GraphNode(node_id="n3", node_type="person"))
        svc.add_edge(GraphEdge(source_id="n1", target_id="n2", edge_type="knows"))
        svc.add_edge(GraphEdge(source_id="n2", target_id="n3", edge_type="knows"))
        svc.add_edge(GraphEdge(source_id="n3", target_id="n1", edge_type="likes"))
        return svc

    def test_get_edges_outgoing(self, tmp_path):
        svc = self._setup_triangle(tmp_path)
        edges = svc.get_edges("n1", direction="outgoing")
        assert len(edges) == 1
        assert edges[0].target_id == "n2"

    def test_get_edges_incoming(self, tmp_path):
        svc = self._setup_triangle(tmp_path)
        edges = svc.get_edges("n1", direction="incoming")
        assert len(edges) == 1
        assert edges[0].source_id == "n3"

    def test_get_edges_both(self, tmp_path):
        svc = self._setup_triangle(tmp_path)
        edges = svc.get_edges("n1", direction="both")
        assert len(edges) == 2

    def test_get_edges_with_edge_type_filter(self, tmp_path):
        svc = self._setup_triangle(tmp_path)
        edges = svc.get_edges("n1", direction="both", edge_type="knows")
        assert len(edges) == 1
        assert edges[0].edge_type == "knows"

    def test_get_edges_with_edge_type_filter_no_match(self, tmp_path):
        svc = self._setup_triangle(tmp_path)
        edges = svc.get_edges("n1", direction="outgoing", edge_type="likes")
        assert len(edges) == 0

    def test_get_edges_empty_namespace(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        edges = svc.get_edges("n1", namespace="empty_ns")
        assert edges == []


class TestFileGraphServiceCascadeDelete:
    """Tests for cascade delete on remove_node."""

    def test_remove_node_deletes_outgoing_edges(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(node_id="n1", node_type="person"))
        svc.add_node(GraphNode(node_id="n2", node_type="person"))
        svc.add_edge(GraphEdge(source_id="n1", target_id="n2", edge_type="knows"))
        svc.remove_node("n1")
        # Edge from n1->n2 should be gone
        edges = svc.get_edges("n2", direction="incoming")
        assert len(edges) == 0

    def test_remove_node_deletes_incoming_edges(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(node_id="n1", node_type="person"))
        svc.add_node(GraphNode(node_id="n2", node_type="person"))
        svc.add_edge(GraphEdge(source_id="n1", target_id="n2", edge_type="knows"))
        svc.remove_node("n2")
        # Edge from n1->n2 should be gone
        edges = svc.get_edges("n1", direction="outgoing")
        assert len(edges) == 0

    def test_remove_node_preserves_unrelated_edges(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(node_id="n1", node_type="person"))
        svc.add_node(GraphNode(node_id="n2", node_type="person"))
        svc.add_node(GraphNode(node_id="n3", node_type="person"))
        svc.add_edge(GraphEdge(source_id="n1", target_id="n2", edge_type="knows"))
        svc.add_edge(GraphEdge(source_id="n2", target_id="n3", edge_type="knows"))
        svc.remove_node("n1")
        # Edge n2->n3 should still exist
        edges = svc.get_edges("n2", direction="outgoing")
        assert len(edges) == 1
        assert edges[0].target_id == "n3"

    def test_remove_node_cascade_deletes_all_connected_edges(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(node_id="n1", node_type="person"))
        svc.add_node(GraphNode(node_id="n2", node_type="person"))
        svc.add_node(GraphNode(node_id="n3", node_type="person"))
        # n2 has both incoming and outgoing edges
        svc.add_edge(GraphEdge(source_id="n1", target_id="n2", edge_type="knows"))
        svc.add_edge(GraphEdge(source_id="n2", target_id="n3", edge_type="knows"))
        svc.add_edge(GraphEdge(source_id="n3", target_id="n2", edge_type="likes"))
        svc.remove_node("n2")
        # All edges involving n2 should be gone
        assert svc.get_edges("n1", direction="outgoing") == []
        assert svc.get_edges("n3", direction="both") == []


class TestFileGraphServiceGetNeighbors:
    """Tests for BFS-based get_neighbors implementation."""

    def test_get_neighbors_depth_1(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(node_id="n1", node_type="person"))
        svc.add_node(GraphNode(node_id="n2", node_type="person"))
        svc.add_node(GraphNode(node_id="n3", node_type="person"))
        svc.add_edge(GraphEdge(source_id="n1", target_id="n2", edge_type="knows"))
        svc.add_edge(GraphEdge(source_id="n2", target_id="n3", edge_type="knows"))

        neighbors = svc.get_neighbors("n1", depth=1)
        assert len(neighbors) == 1
        assert neighbors[0][0].node_id == "n2"
        assert neighbors[0][1] == 1

    def test_get_neighbors_depth_2(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(node_id="n1", node_type="person"))
        svc.add_node(GraphNode(node_id="n2", node_type="person"))
        svc.add_node(GraphNode(node_id="n3", node_type="person"))
        svc.add_edge(GraphEdge(source_id="n1", target_id="n2", edge_type="knows"))
        svc.add_edge(GraphEdge(source_id="n2", target_id="n3", edge_type="knows"))

        neighbors = svc.get_neighbors("n1", depth=2)
        assert len(neighbors) == 2
        ids_and_depths = [(n.node_id, d) for n, d in neighbors]
        assert ("n2", 1) in ids_and_depths
        assert ("n3", 2) in ids_and_depths

    def test_get_neighbors_with_edge_type_filter(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(node_id="n1", node_type="person"))
        svc.add_node(GraphNode(node_id="n2", node_type="person"))
        svc.add_node(GraphNode(node_id="n3", node_type="person"))
        svc.add_edge(GraphEdge(source_id="n1", target_id="n2", edge_type="knows"))
        svc.add_edge(GraphEdge(source_id="n1", target_id="n3", edge_type="likes"))

        neighbors = svc.get_neighbors("n1", edge_type="knows", depth=1)
        assert len(neighbors) == 1
        assert neighbors[0][0].node_id == "n2"

    def test_get_neighbors_no_duplicates_in_cycle(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(node_id="n1", node_type="person"))
        svc.add_node(GraphNode(node_id="n2", node_type="person"))
        svc.add_node(GraphNode(node_id="n3", node_type="person"))
        svc.add_edge(GraphEdge(source_id="n1", target_id="n2", edge_type="knows"))
        svc.add_edge(GraphEdge(source_id="n2", target_id="n3", edge_type="knows"))
        svc.add_edge(GraphEdge(source_id="n3", target_id="n1", edge_type="knows"))

        neighbors = svc.get_neighbors("n1", depth=3)
        # Should visit n2 and n3 but not revisit n1
        assert len(neighbors) == 2
        ids = [n.node_id for n, _ in neighbors]
        assert "n2" in ids
        assert "n3" in ids

    def test_get_neighbors_nonexistent_node_returns_empty(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        assert svc.get_neighbors("nonexistent") == []

    def test_get_neighbors_no_outgoing_edges(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(node_id="n1", node_type="person"))
        assert svc.get_neighbors("n1") == []

    def test_get_neighbors_depth_0_returns_empty(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(node_id="n1", node_type="person"))
        svc.add_node(GraphNode(node_id="n2", node_type="person"))
        svc.add_edge(GraphEdge(source_id="n1", target_id="n2", edge_type="knows"))
        assert svc.get_neighbors("n1", depth=0) == []

    def test_get_neighbors_branching_graph(self, tmp_path):
        """Test BFS on a branching graph: n1 -> n2, n1 -> n3, n2 -> n4."""
        svc = FileGraphService(base_dir=str(tmp_path))
        for nid in ["n1", "n2", "n3", "n4"]:
            svc.add_node(GraphNode(node_id=nid, node_type="person"))
        svc.add_edge(GraphEdge(source_id="n1", target_id="n2", edge_type="knows"))
        svc.add_edge(GraphEdge(source_id="n1", target_id="n3", edge_type="knows"))
        svc.add_edge(GraphEdge(source_id="n2", target_id="n4", edge_type="knows"))

        neighbors = svc.get_neighbors("n1", depth=2)
        assert len(neighbors) == 3
        depth_1 = [n.node_id for n, d in neighbors if d == 1]
        depth_2 = [n.node_id for n, d in neighbors if d == 2]
        assert sorted(depth_1) == ["n2", "n3"]
        assert depth_2 == ["n4"]


class TestFileGraphServiceListNodes:
    """Tests for list_nodes with optional node_type filter."""

    def test_list_all_nodes(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(node_id="n1", node_type="person"))
        svc.add_node(GraphNode(node_id="n2", node_type="place"))
        nodes = svc.list_nodes()
        assert len(nodes) == 2

    def test_list_nodes_with_type_filter(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(node_id="n1", node_type="person"))
        svc.add_node(GraphNode(node_id="n2", node_type="place"))
        svc.add_node(GraphNode(node_id="n3", node_type="person"))
        nodes = svc.list_nodes(node_type="person")
        assert len(nodes) == 2
        assert all(n.node_type == "person" for n in nodes)

    def test_list_nodes_empty(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        assert svc.list_nodes() == []

    def test_list_nodes_no_match(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(node_id="n1", node_type="person"))
        assert svc.list_nodes(node_type="place") == []


class TestFileGraphServiceNamespaces:
    """Tests for namespace-scoped operations."""

    def test_default_namespace_when_none(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(node_id="n1", node_type="person"))
        svc.add_node(GraphNode(node_id="n1", node_type="person", label="updated"), namespace=None)
        # Both target _default namespace, so second overwrites
        assert svc.get_node("n1").label == "updated"

    def test_separate_namespaces(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(node_id="n1", node_type="person", label="Alice"), namespace="ns1")
        svc.add_node(GraphNode(node_id="n1", node_type="person", label="Bob"), namespace="ns2")
        assert svc.get_node("n1", namespace="ns1").label == "Alice"
        assert svc.get_node("n1", namespace="ns2").label == "Bob"

    def test_edges_scoped_to_namespace(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(node_id="n1", node_type="person"), namespace="ns1")
        svc.add_node(GraphNode(node_id="n2", node_type="person"), namespace="ns1")
        svc.add_edge(GraphEdge(source_id="n1", target_id="n2", edge_type="knows"), namespace="ns1")
        # Should not find edges in default namespace
        assert svc.get_edges("n1") == []
        assert len(svc.get_edges("n1", namespace="ns1")) == 1

    def test_add_edge_cross_namespace_fails(self, tmp_path):
        """Nodes must exist in the same namespace as the edge."""
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(node_id="n1", node_type="person"), namespace="ns1")
        svc.add_node(GraphNode(node_id="n2", node_type="person"), namespace="ns2")
        with pytest.raises(ValueError):
            svc.add_edge(
                GraphEdge(source_id="n1", target_id="n2", edge_type="knows"),
                namespace="ns1"  # n2 doesn't exist in ns1
            )

    def test_size_per_namespace(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(node_id="n1", node_type="person"), namespace="ns1")
        svc.add_node(GraphNode(node_id="n2", node_type="person"), namespace="ns1")
        svc.add_node(GraphNode(node_id="n3", node_type="person"), namespace="ns2")
        assert svc.size(namespace="ns1") == 2
        assert svc.size(namespace="ns2") == 1

    def test_size_empty_namespace(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        assert svc.size(namespace="nonexistent") == 0

    def test_clear_namespace(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(node_id="n1", node_type="person"), namespace="ns1")
        svc.add_node(GraphNode(node_id="n2", node_type="person"), namespace="ns1")
        svc.add_node(GraphNode(node_id="n3", node_type="person"), namespace="ns2")
        svc.add_edge(
            GraphEdge(source_id="n1", target_id="n2", edge_type="knows"),
            namespace="ns1"
        )
        count = svc.clear(namespace="ns1")
        assert count == 2
        assert svc.size(namespace="ns1") == 0
        assert svc.get_edges("n1", namespace="ns1") == []
        assert svc.size(namespace="ns2") == 1

    def test_clear_empty_namespace(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        assert svc.clear(namespace="nonexistent") == 0

    def test_namespaces_list(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(node_id="n1", node_type="person"), namespace="ns1")
        svc.add_node(GraphNode(node_id="n2", node_type="person"), namespace="ns2")
        assert sorted(svc.namespaces()) == ["ns1", "ns2"]

    def test_namespaces_empty(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        assert svc.namespaces() == []

    def test_remove_node_cleans_up_empty_namespace(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(node_id="n1", node_type="person"), namespace="ns1")
        svc.remove_node("n1", namespace="ns1")
        assert "ns1" not in svc.namespaces()

    def test_get_neighbors_scoped_to_namespace(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(node_id="n1", node_type="person"), namespace="ns1")
        svc.add_node(GraphNode(node_id="n2", node_type="person"), namespace="ns1")
        svc.add_edge(
            GraphEdge(source_id="n1", target_id="n2", edge_type="knows"),
            namespace="ns1"
        )
        # Should not find neighbors in default namespace
        assert svc.get_neighbors("n1") == []
        neighbors = svc.get_neighbors("n1", namespace="ns1")
        assert len(neighbors) == 1
        assert neighbors[0][0].node_id == "n2"


class TestFileGraphServiceLifecycle:
    """Tests for ping, close, context manager, repr, and get_stats."""

    def test_ping_when_open(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        assert svc.ping() is True

    def test_ping_when_closed(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.close()
        assert svc.ping() is False

    def test_close_is_idempotent(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.close()
        svc.close()  # Should not raise
        assert svc.ping() is False

    def test_context_manager(self, tmp_path):
        with FileGraphService(base_dir=str(tmp_path)) as svc:
            svc.add_node(GraphNode(node_id="n1", node_type="person"))
            assert svc.get_node("n1") is not None
        assert svc.ping() is False

    def test_repr(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(node_id="n1", node_type="person"))
        svc.add_node(GraphNode(node_id="n2", node_type="person"))
        svc.add_edge(GraphEdge(source_id="n1", target_id="n2", edge_type="knows"))
        r = repr(svc)
        assert "FileGraphService" in r
        assert "namespaces=1" in r
        assert "total_nodes=2" in r
        assert "total_edges=1" in r

    def test_get_stats_all(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(node_id="n1", node_type="person"), namespace="ns1")
        svc.add_node(GraphNode(node_id="n2", node_type="person"), namespace="ns2")
        stats = svc.get_stats()
        assert stats["backend"] == "file"
        assert stats["namespace_count"] == 2
        assert stats["total_nodes"] == 2

    def test_get_stats_specific_namespace(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(node_id="n1", node_type="person"), namespace="ns1")
        svc.add_node(GraphNode(node_id="n2", node_type="person"), namespace="ns1")
        svc.add_edge(
            GraphEdge(source_id="n1", target_id="n2", edge_type="knows"),
            namespace="ns1"
        )
        stats = svc.get_stats(namespace="ns1")
        assert stats["backend"] == "file"
        assert stats["namespace"] == "ns1"
        assert stats["nodes"] == 2
        assert stats["edges"] == 1

    def test_get_stats_empty_namespace(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        stats = svc.get_stats(namespace="empty_ns")
        assert stats["nodes"] == 0
        assert stats["edges"] == 0
