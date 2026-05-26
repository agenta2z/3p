"""
Property-based tests for Graph Service.

# Feature: knowledge-service-extraction
# Properties 9-16: Graph model serialization round-trip, GraphNode.value
#                  equals node_id invariant, node removal cascade-deletes
#                  edges, GraphNode add/get round-trip, GraphEdge add/get_edges
#                  round-trip, add edge with missing node raises error,
#                  materialize_subgraph produces correct links, materialized
#                  nodes compatible with BFS/DFS traversal.

Uses Hypothesis to verify universal correctness properties across
randomly generated inputs. Tests are parametrized across backends
via the graph_service fixture (currently memory only; Task 12.3
will add file and networkx).
"""

import uuid

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from python_utils.algorithms.graph.traversal import bfs_traversal
from python_utils.service_utils.graph_service.graph_node import GraphEdge, GraphNode
from python_utils.service_utils.graph_service.materialize import materialize_subgraph
from python_utils.service_utils.graph_service.memory_graph_service import (
    MemoryGraphService,
)

from conftest import (
    graph_node_strategy,
    graph_edge_strategy,
    _safe_string,
    _node_type_strategy,
    _properties_strategy,
)


# Shared settings for tests that use the graph_service fixture.
_fixture_settings = settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


def _unique_namespace():
    """Generate a unique namespace to isolate each Hypothesis iteration."""
    return f"ns_{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# Feature: knowledge-service-extraction, Property 9: Graph model serialization
# round-trip
# ---------------------------------------------------------------------------


class TestGraphModelSerializationRoundTrip:
    """Property 9: Graph model serialization round-trip.

    For any valid GraphNode, calling from_dict(to_dict(node)) should produce
    a GraphNode with equivalent node_id, node_type, label, and properties.
    The to_dict output should not contain keys "next", "previous", or "value".
    The same round-trip property applies to GraphEdge.

    **Validates: Requirements 7.2, 7.7**
    """

    @given(node=graph_node_strategy())
    @settings(max_examples=100)
    def test_graph_node_round_trip(self, node):
        """from_dict(to_dict(node)) produces equivalent GraphNode fields.

        **Validates: Requirements 7.2, 7.7**
        """
        d = node.to_dict()

        # to_dict must NOT contain inherited traversal fields
        assert "next" not in d, "to_dict should not contain 'next'"
        assert "previous" not in d, "to_dict should not contain 'previous'"
        assert "value" not in d, "to_dict should not contain 'value'"

        restored = GraphNode.from_dict(d)

        assert restored.node_id == node.node_id
        assert restored.node_type == node.node_type
        assert restored.label == node.label
        assert restored.properties == node.properties

    @given(
        source_id=_safe_string,
        target_id=_safe_string,
        edge_type=_node_type_strategy,
        properties=_properties_strategy,
    )
    @settings(max_examples=100)
    def test_graph_edge_round_trip(self, source_id, target_id, edge_type, properties):
        """from_dict(to_dict(edge)) produces equivalent GraphEdge fields.

        **Validates: Requirements 7.2, 7.7**
        """
        edge = GraphEdge(
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            properties=properties,
        )
        d = edge.to_dict()
        restored = GraphEdge.from_dict(d)

        assert restored.source_id == edge.source_id
        assert restored.target_id == edge.target_id
        assert restored.edge_type == edge.edge_type
        assert restored.properties == edge.properties


# ---------------------------------------------------------------------------
# Feature: knowledge-service-extraction, Property 10: GraphNode.value equals
# node_id invariant
# ---------------------------------------------------------------------------


class TestGraphNodeValueEqualsNodeId:
    """Property 10: GraphNode.value equals node_id invariant.

    For any GraphNode constructed with any node_id, after
    __attrs_post_init__ completes, node.value should equal node.node_id.

    **Validates: Requirements 7.6**
    """

    @given(node=graph_node_strategy())
    @settings(max_examples=100)
    def test_value_equals_node_id(self, node):
        """After construction, node.value == node.node_id.

        **Validates: Requirements 7.6**
        """
        assert node.value == node.node_id

    @given(node_id=_safe_string)
    @settings(max_examples=100)
    def test_value_equals_node_id_from_dict(self, node_id):
        """After from_dict, node.value == node.node_id.

        **Validates: Requirements 7.6**
        """
        data = {"node_id": node_id, "node_type": "test"}
        node = GraphNode.from_dict(data)
        assert node.value == node_id


# ---------------------------------------------------------------------------
# Feature: knowledge-service-extraction, Property 11: Node removal
# cascade-deletes edges
# ---------------------------------------------------------------------------


class TestNodeRemovalCascadeDeletesEdges:
    """Property 11: Node removal cascade-deletes edges.

    For any graph containing nodes and edges, removing a node should result
    in get_edges returning no edges where the removed node is either
    source_id or target_id.

    **Validates: Requirements 7.4**
    """

    @given(
        node_ids=st.lists(
            _safe_string,
            min_size=3,
            max_size=6,
            unique=True,
        ),
        data=st.data(),
    )
    @_fixture_settings
    def test_cascade_delete_edges_on_node_removal(self, graph_service, node_ids, data):
        """Removing a node removes all edges where it is source or target.

        **Validates: Requirements 7.4**
        """
        ns = _unique_namespace()

        # Add all nodes
        for nid in node_ids:
            graph_service.add_node(
                GraphNode(node_id=nid, node_type="test"),
                namespace=ns,
            )

        # Generate and add some edges between existing nodes
        edges = data.draw(
            st.lists(
                graph_edge_strategy(node_ids),
                min_size=2,
                max_size=10,
            )
        )
        for edge in edges:
            graph_service.add_edge(edge, namespace=ns)

        # Pick a node to remove
        removed_id = data.draw(st.sampled_from(node_ids))
        graph_service.remove_node(removed_id, namespace=ns)

        # Verify: no edges reference the removed node as source or target
        remaining_ids = [nid for nid in node_ids if nid != removed_id]
        for nid in remaining_ids:
            outgoing = graph_service.get_edges(nid, direction="outgoing", namespace=ns)
            incoming = graph_service.get_edges(nid, direction="incoming", namespace=ns)
            all_edges = outgoing + incoming

            for e in all_edges:
                assert e.source_id != removed_id, (
                    f"Edge with source_id={removed_id!r} still exists after removal"
                )
                assert e.target_id != removed_id, (
                    f"Edge with target_id={removed_id!r} still exists after removal"
                )


# ---------------------------------------------------------------------------
# Feature: knowledge-service-extraction, Property 12: GraphNode add/get
# round-trip
# ---------------------------------------------------------------------------


class TestGraphNodeAddGetRoundTrip:
    """Property 12: GraphNode add/get round-trip.

    For any valid GraphNode, adding it to a graph service and then
    retrieving it by node_id should return a GraphNode with equivalent
    node_id, node_type, label, and properties.

    **Validates: Requirements 10.1**
    """

    @given(node=graph_node_strategy())
    @_fixture_settings
    def test_add_get_round_trip(self, graph_service, node):
        """add_node(node) followed by get_node(node_id) returns equivalent fields.

        **Validates: Requirements 10.1**
        """
        ns = _unique_namespace()

        graph_service.add_node(node, namespace=ns)
        retrieved = graph_service.get_node(node.node_id, namespace=ns)

        assert retrieved is not None, (
            f"get_node returned None for node_id={node.node_id!r}"
        )
        assert retrieved.node_id == node.node_id
        assert retrieved.node_type == node.node_type
        assert retrieved.label == node.label
        assert retrieved.properties == node.properties


# ---------------------------------------------------------------------------
# Feature: knowledge-service-extraction, Property 13: GraphEdge add/get_edges
# round-trip
# ---------------------------------------------------------------------------


class TestGraphEdgeAddGetEdgesRoundTrip:
    """Property 13: GraphEdge add/get_edges round-trip.

    For any valid GraphEdge between two existing nodes, adding it to a graph
    service and then calling get_edges for the source node should include an
    edge with equivalent source_id, target_id, edge_type, and properties.

    **Validates: Requirements 10.2**
    """

    @given(
        source_id=_safe_string,
        target_id=_safe_string,
        edge_type=_node_type_strategy,
        properties=_properties_strategy,
    )
    @_fixture_settings
    def test_add_get_edges_round_trip(
        self, graph_service, source_id, target_id, edge_type, properties
    ):
        """add_edge(edge) followed by get_edges(source) includes equivalent edge.

        **Validates: Requirements 10.2**
        """
        ns = _unique_namespace()

        # Create and add both nodes
        graph_service.add_node(
            GraphNode(node_id=source_id, node_type="test"),
            namespace=ns,
        )
        graph_service.add_node(
            GraphNode(node_id=target_id, node_type="test"),
            namespace=ns,
        )

        edge = GraphEdge(
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            properties=properties,
        )
        graph_service.add_edge(edge, namespace=ns)

        edges = graph_service.get_edges(source_id, direction="outgoing", namespace=ns)

        # Find the matching edge
        matching = [
            e for e in edges
            if e.source_id == source_id
            and e.target_id == target_id
            and e.edge_type == edge_type
        ]
        assert len(matching) >= 1, (
            f"Expected to find edge ({source_id!r} -> {target_id!r}, "
            f"type={edge_type!r}) in get_edges results"
        )
        found = matching[0]
        assert found.properties == properties


# ---------------------------------------------------------------------------
# Feature: knowledge-service-extraction, Property 14: Add edge with missing
# node raises error
# ---------------------------------------------------------------------------


class TestAddEdgeWithMissingNodeRaisesError:
    """Property 14: Add edge with missing node raises error.

    For any GraphEdge where either source_id or target_id does not exist
    in the graph service, calling add_edge should raise a ValueError.

    **Validates: Requirements 10.3**
    """

    @given(
        existing_id=_safe_string,
        missing_id=_safe_string,
        edge_type=_node_type_strategy,
    )
    @_fixture_settings
    def test_missing_source_raises_value_error(
        self, graph_service, existing_id, missing_id, edge_type
    ):
        """add_edge with non-existent source raises ValueError.

        **Validates: Requirements 10.3**
        """
        assume(existing_id != missing_id)
        ns = _unique_namespace()

        # Only add the target node, not the source
        graph_service.add_node(
            GraphNode(node_id=existing_id, node_type="test"),
            namespace=ns,
        )

        edge = GraphEdge(
            source_id=missing_id,
            target_id=existing_id,
            edge_type=edge_type,
        )
        with pytest.raises(ValueError):
            graph_service.add_edge(edge, namespace=ns)

    @given(
        existing_id=_safe_string,
        missing_id=_safe_string,
        edge_type=_node_type_strategy,
    )
    @_fixture_settings
    def test_missing_target_raises_value_error(
        self, graph_service, existing_id, missing_id, edge_type
    ):
        """add_edge with non-existent target raises ValueError.

        **Validates: Requirements 10.3**
        """
        assume(existing_id != missing_id)
        ns = _unique_namespace()

        # Only add the source node, not the target
        graph_service.add_node(
            GraphNode(node_id=existing_id, node_type="test"),
            namespace=ns,
        )

        edge = GraphEdge(
            source_id=existing_id,
            target_id=missing_id,
            edge_type=edge_type,
        )
        with pytest.raises(ValueError):
            graph_service.add_edge(edge, namespace=ns)


# ---------------------------------------------------------------------------
# Feature: knowledge-service-extraction, Property 15: materialize_subgraph
# produces correct links
# ---------------------------------------------------------------------------


class TestMaterializeSubgraphProducesCorrectLinks:
    """Property 15: materialize_subgraph produces correct links.

    For any graph with edges, materialize_subgraph returns a GraphNode whose
    next list contains GraphNode references for outgoing edges of that type,
    and whose previous list contains GraphNode references for incoming edges,
    up to the specified depth.

    **Validates: Requirements 9.1, 9.2**
    """

    @given(
        node_ids=st.lists(
            _safe_string,
            min_size=2,
            max_size=4,
            unique=True,
        ),
        edge_type=_node_type_strategy,
    )
    @settings(max_examples=100)
    def test_materialize_next_contains_correct_targets(self, node_ids, edge_type):
        """Materialized start node's next list contains correct targets.

        Build a star graph: node_ids[0] -> node_ids[1], node_ids[0] -> node_ids[2], ...
        Materialize from node_ids[0] with depth=1 and verify next list.

        **Validates: Requirements 9.1, 9.2**
        """
        svc = MemoryGraphService()
        start_id = node_ids[0]
        target_ids = node_ids[1:]

        # Add all nodes
        for nid in node_ids:
            svc.add_node(GraphNode(node_id=nid, node_type="test"))

        # Add edges from start to all targets
        for tid in target_ids:
            svc.add_edge(GraphEdge(
                source_id=start_id,
                target_id=tid,
                edge_type=edge_type,
            ))

        # Materialize
        start = materialize_subgraph(
            svc, start_id, edge_type=edge_type, depth=1
        )

        assert start.node_id == start_id

        # next list should contain all target nodes
        assert start.next is not None, "start.next should not be None"
        next_ids = sorted([n.node_id for n in start.next])
        assert next_ids == sorted(target_ids), (
            f"Expected next ids {sorted(target_ids)}, got {next_ids}"
        )

        # Each target's previous should contain the start node
        for child in start.next:
            assert child.previous is not None
            prev_ids = [n.node_id for n in child.previous]
            assert start_id in prev_ids

        svc.close()

    @given(
        node_ids=st.lists(
            _safe_string,
            min_size=3,
            max_size=4,
            unique=True,
        ),
        edge_type=_node_type_strategy,
    )
    @settings(max_examples=100)
    def test_materialize_chain_depth_2(self, node_ids, edge_type):
        """Materialized chain A -> B -> C has correct links at depth 2.

        **Validates: Requirements 9.1, 9.2**
        """
        svc = MemoryGraphService()

        # Add all nodes
        for nid in node_ids:
            svc.add_node(GraphNode(node_id=nid, node_type="test"))

        # Build chain: node_ids[0] -> node_ids[1] -> node_ids[2] -> ...
        for i in range(len(node_ids) - 1):
            svc.add_edge(GraphEdge(
                source_id=node_ids[i],
                target_id=node_ids[i + 1],
                edge_type=edge_type,
            ))

        start = materialize_subgraph(
            svc, node_ids[0], edge_type=edge_type, depth=2
        )

        # Verify chain links
        assert start.node_id == node_ids[0]
        assert start.next is not None
        assert len(start.next) == 1
        assert start.next[0].node_id == node_ids[1]

        second = start.next[0]
        assert second.next is not None
        assert len(second.next) == 1
        assert second.next[0].node_id == node_ids[2]

        svc.close()


# ---------------------------------------------------------------------------
# Feature: knowledge-service-extraction, Property 16: Materialized nodes
# compatible with BFS/DFS traversal
# ---------------------------------------------------------------------------


class TestMaterializedNodesCompatibleWithBfsDfs:
    """Property 16: Materialized nodes compatible with BFS/DFS traversal.

    For any materialized subgraph produced by materialize_subgraph, running
    bfs_traversal from the returned start node using {GraphNode: 'next'}
    as the children_attr_map should visit all nodes reachable via outgoing
    edges without error.

    **Validates: Requirements 9.3**
    """

    @given(
        node_ids=st.lists(
            _safe_string,
            min_size=2,
            max_size=4,
            unique=True,
        ),
        edge_type=_node_type_strategy,
    )
    @settings(max_examples=100)
    def test_bfs_traversal_visits_all_reachable_nodes(self, node_ids, edge_type):
        """bfs_traversal on materialized subgraph visits all reachable nodes.

        Build a star graph: node_ids[0] -> all others.
        Materialize from node_ids[0] with depth=1.
        BFS should visit start + all targets.

        **Validates: Requirements 9.3**
        """
        svc = MemoryGraphService()
        start_id = node_ids[0]

        # Add all nodes
        for nid in node_ids:
            svc.add_node(GraphNode(node_id=nid, node_type="test"))

        # Add edges from start to all others
        for tid in node_ids[1:]:
            svc.add_edge(GraphEdge(
                source_id=start_id,
                target_id=tid,
                edge_type=edge_type,
            ))

        start = materialize_subgraph(
            svc, start_id, edge_type=edge_type, depth=1
        )

        # BFS traversal should not raise and should visit all nodes
        visited = list(bfs_traversal(start, {GraphNode: 'next'}))
        visited_ids = sorted([n.node_id for n in visited])

        assert visited_ids == sorted(node_ids), (
            f"BFS visited {visited_ids}, expected {sorted(node_ids)}"
        )

        svc.close()

    @given(
        node_ids=st.lists(
            _safe_string,
            min_size=3,
            max_size=4,
            unique=True,
        ),
        edge_type=_node_type_strategy,
    )
    @settings(max_examples=100)
    def test_bfs_traversal_on_chain(self, node_ids, edge_type):
        """bfs_traversal on materialized chain visits nodes in order.

        Build chain: node_ids[0] -> node_ids[1] -> ... -> node_ids[-1].
        Materialize with depth=len-1.
        BFS should visit all nodes.

        **Validates: Requirements 9.3**
        """
        svc = MemoryGraphService()

        # Add all nodes
        for nid in node_ids:
            svc.add_node(GraphNode(node_id=nid, node_type="test"))

        # Build chain
        for i in range(len(node_ids) - 1):
            svc.add_edge(GraphEdge(
                source_id=node_ids[i],
                target_id=node_ids[i + 1],
                edge_type=edge_type,
            ))

        depth = len(node_ids) - 1
        start = materialize_subgraph(
            svc, node_ids[0], edge_type=edge_type, depth=depth
        )

        # BFS traversal should visit all nodes in chain order
        visited = list(bfs_traversal(start, {GraphNode: 'next'}))
        visited_ids = [n.node_id for n in visited]

        assert visited_ids == node_ids, (
            f"BFS visited {visited_ids}, expected {node_ids}"
        )

        svc.close()
