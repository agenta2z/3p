"""
Tests for Neo4jGraphService.

Requires a running Neo4j server and ``neo4j`` package.
Skipped automatically when not available.

# Feature: knowledge-service-extraction
# Task 20.2: Write tests for Neo4j backend
"""

import uuid

import pytest

neo4j = pytest.importorskip("neo4j")

from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from python_utils.service_utils.graph_service.neo4j_graph_service import (
    Neo4jGraphService,
)
from python_utils.service_utils.graph_service.graph_node import (
    GraphEdge,
    GraphNode,
)

pytestmark = pytest.mark.requires_neo4j

_NEO4J_URI = "bolt://localhost:7687"
_NEO4J_AUTH = ("neo4j", "testpassword")
_NEO4J_AVAILABLE = None


def _check_neo4j():
    global _NEO4J_AVAILABLE
    if _NEO4J_AVAILABLE is None:
        try:
            from neo4j import GraphDatabase
            driver = GraphDatabase.driver(_NEO4J_URI, auth=_NEO4J_AUTH)
            driver.verify_connectivity()
            driver.close()
            _NEO4J_AVAILABLE = True
        except Exception:
            _NEO4J_AVAILABLE = False
    return _NEO4J_AVAILABLE


_fx_settings = settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


@pytest.fixture()
def neo4j_svc():
    """Yield a Neo4jGraphService. Cleanup after test."""
    if not _check_neo4j():
        pytest.skip("Neo4j server not available")
    svc = Neo4jGraphService(uri=_NEO4J_URI, auth=_NEO4J_AUTH)
    # Use a unique namespace per test to avoid collisions
    ns = f"test_{uuid.uuid4().hex[:8]}"
    yield svc, ns
    # Cleanup
    svc.clear(namespace=ns)
    svc.close()


# ── Property 12: GraphNode add/get round-trip ──

class TestNeo4jNodeRoundTrip:
    """**Validates: Requirements 10.1**"""

    def test_add_get_round_trip(self, neo4j_svc):
        svc, ns = neo4j_svc
        node = GraphNode(node_id="n1", node_type="person", label="Alice", properties={"age": 30})
        svc.add_node(node, namespace=ns)
        retrieved = svc.get_node("n1", namespace=ns)
        assert retrieved is not None
        assert retrieved.node_id == "n1"
        assert retrieved.node_type == "person"
        assert retrieved.label == "Alice"
        assert retrieved.properties == {"age": 30}


# ── Property 13: GraphEdge add/get_edges round-trip ──

class TestNeo4jEdgeRoundTrip:
    """**Validates: Requirements 10.2**"""

    def test_add_get_edge_round_trip(self, neo4j_svc):
        svc, ns = neo4j_svc
        svc.add_node(GraphNode(node_id="a", node_type="t"), namespace=ns)
        svc.add_node(GraphNode(node_id="b", node_type="t"), namespace=ns)
        edge = GraphEdge(source_id="a", target_id="b", edge_type="knows", properties={"since": 2020})
        svc.add_edge(edge, namespace=ns)
        edges = svc.get_edges("a", namespace=ns)
        assert len(edges) >= 1
        found = [e for e in edges if e.target_id == "b" and e.edge_type == "knows"]
        assert len(found) == 1
        assert found[0].properties == {"since": 2020}


# ── Property 14: Add edge with missing node raises error ──

class TestNeo4jMissingNodeEdge:
    """**Validates: Requirements 10.3**"""

    def test_add_edge_missing_source(self, neo4j_svc):
        svc, ns = neo4j_svc
        svc.add_node(GraphNode(node_id="b", node_type="t"), namespace=ns)
        with pytest.raises(ValueError, match="Source"):
            svc.add_edge(GraphEdge(source_id="missing", target_id="b", edge_type="x"), namespace=ns)

    def test_add_edge_missing_target(self, neo4j_svc):
        svc, ns = neo4j_svc
        svc.add_node(GraphNode(node_id="a", node_type="t"), namespace=ns)
        with pytest.raises(ValueError, match="Target"):
            svc.add_edge(GraphEdge(source_id="a", target_id="missing", edge_type="x"), namespace=ns)


# ── Property 11: Node removal cascade-deletes edges ──

class TestNeo4jCascadeDelete:
    """**Validates: Requirements 7.4**"""

    def test_remove_node_cascades_edges(self, neo4j_svc):
        svc, ns = neo4j_svc
        svc.add_node(GraphNode(node_id="a", node_type="t"), namespace=ns)
        svc.add_node(GraphNode(node_id="b", node_type="t"), namespace=ns)
        svc.add_edge(GraphEdge(source_id="a", target_id="b", edge_type="x"), namespace=ns)
        svc.remove_node("a", namespace=ns)
        assert svc.get_edges("b", direction="incoming", namespace=ns) == []


# ── Unit tests ──

class TestNeo4jUnit:

    def test_get_nonexistent_returns_none(self, neo4j_svc):
        svc, ns = neo4j_svc
        assert svc.get_node("no_such", namespace=ns) is None

    def test_remove_nonexistent_returns_false(self, neo4j_svc):
        svc, ns = neo4j_svc
        assert svc.remove_node("no_such", namespace=ns) is False

    def test_size_and_clear(self, neo4j_svc):
        svc, ns = neo4j_svc
        svc.add_node(GraphNode(node_id="a", node_type="t"), namespace=ns)
        svc.add_node(GraphNode(node_id="b", node_type="t"), namespace=ns)
        assert svc.size(namespace=ns) == 2
        removed = svc.clear(namespace=ns)
        assert removed == 2
        assert svc.size(namespace=ns) == 0

    def test_list_nodes(self, neo4j_svc):
        svc, ns = neo4j_svc
        svc.add_node(GraphNode(node_id="a", node_type="person"), namespace=ns)
        svc.add_node(GraphNode(node_id="b", node_type="place"), namespace=ns)
        persons = svc.list_nodes(node_type="person", namespace=ns)
        assert len(persons) == 1
        assert persons[0].node_id == "a"

    def test_get_neighbors(self, neo4j_svc):
        svc, ns = neo4j_svc
        svc.add_node(GraphNode(node_id="a", node_type="t"), namespace=ns)
        svc.add_node(GraphNode(node_id="b", node_type="t"), namespace=ns)
        svc.add_node(GraphNode(node_id="c", node_type="t"), namespace=ns)
        svc.add_edge(GraphEdge(source_id="a", target_id="b", edge_type="x"), namespace=ns)
        svc.add_edge(GraphEdge(source_id="b", target_id="c", edge_type="x"), namespace=ns)
        neighbors = svc.get_neighbors("a", depth=2, namespace=ns)
        ids = {n.node_id for n, d in neighbors}
        assert "b" in ids
        assert "c" in ids

    def test_namespaces(self, neo4j_svc):
        svc, ns = neo4j_svc
        svc.add_node(GraphNode(node_id="a", node_type="t"), namespace=ns)
        all_ns = svc.namespaces()
        assert ns in all_ns

    def test_ping(self, neo4j_svc):
        svc, ns = neo4j_svc
        assert svc.ping() is True

    def test_remove_edge(self, neo4j_svc):
        svc, ns = neo4j_svc
        svc.add_node(GraphNode(node_id="a", node_type="t"), namespace=ns)
        svc.add_node(GraphNode(node_id="b", node_type="t"), namespace=ns)
        svc.add_edge(GraphEdge(source_id="a", target_id="b", edge_type="x"), namespace=ns)
        assert svc.remove_edge("a", "b", "x", namespace=ns) is True
        assert svc.get_edges("a", namespace=ns) == []
        assert svc.remove_edge("a", "b", "x", namespace=ns) is False

    def test_get_stats(self, neo4j_svc):
        svc, ns = neo4j_svc
        svc.add_node(GraphNode(node_id="a", node_type="t"), namespace=ns)
        stats = svc.get_stats(namespace=ns)
        assert stats["backend"] == "neo4j"
        assert stats["nodes"] == 1
