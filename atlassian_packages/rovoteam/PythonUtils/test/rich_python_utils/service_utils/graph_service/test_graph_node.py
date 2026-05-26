"""
Unit tests for GraphNode and GraphEdge models.

Tests cover construction, defaults, serialization (to_dict / from_dict),
Node inheritance, and BFS/DFS compatibility.
"""

from python_utils.algorithms.graph.node import Node
from python_utils.service_utils.graph_service.graph_node import (
    GraphEdge,
    GraphNode,
)


class TestGraphNodeConstruction:
    """Tests for GraphNode construction and defaults."""

    def test_construction_with_required_fields(self):
        node = GraphNode(node_id="n1", node_type="person")
        assert node.node_id == "n1"
        assert node.node_type == "person"
        assert node.label == ""
        assert node.properties == {}

    def test_construction_with_all_fields(self):
        props = {"age": 30, "name": "Alice"}
        node = GraphNode(
            node_id="n1",
            node_type="person",
            label="Alice",
            properties=props,
        )
        assert node.node_id == "n1"
        assert node.node_type == "person"
        assert node.label == "Alice"
        assert node.properties == {"age": 30, "name": "Alice"}

    def test_empty_label_defaults_to_empty_string(self):
        node = GraphNode(node_id="n1", node_type="thing")
        assert node.label == ""

    def test_empty_properties_defaults_to_empty_dict(self):
        node = GraphNode(node_id="n1", node_type="thing")
        assert node.properties == {}

    def test_properties_factory_creates_independent_dicts(self):
        node1 = GraphNode(node_id="n1", node_type="a")
        node2 = GraphNode(node_id="n2", node_type="b")
        node1.properties["key"] = "value"
        assert "key" not in node2.properties


class TestGraphNodeValueEqualsNodeId:
    """Tests that GraphNode.value is set to node_id after construction."""

    def test_value_equals_node_id(self):
        node = GraphNode(node_id="abc-123", node_type="entity")
        assert node.value == "abc-123"

    def test_value_equals_node_id_with_special_chars(self):
        node = GraphNode(node_id="node/with:special%chars", node_type="test")
        assert node.value == "node/with:special%chars"

    def test_value_equals_node_id_empty_string(self):
        node = GraphNode(node_id="", node_type="test")
        assert node.value == ""


class TestGraphNodeInheritance:
    """Tests that GraphNode properly inherits from Node."""

    def test_is_instance_of_node(self):
        node = GraphNode(node_id="n1", node_type="test")
        assert isinstance(node, Node)

    def test_next_defaults_to_none(self):
        node = GraphNode(node_id="n1", node_type="test")
        assert node.next is None

    def test_previous_defaults_to_none(self):
        node = GraphNode(node_id="n1", node_type="test")
        assert node.previous is None


class TestGraphNodeBfsDfsCompatibility:
    """Tests that GraphNode works with inherited BFS/DFS methods."""

    def test_add_next_creates_link(self):
        parent = GraphNode(node_id="p1", node_type="person")
        child = GraphNode(node_id="c1", node_type="person")
        parent.add_next(child)
        assert child in parent.next
        assert parent in child.previous

    def test_bfs_traversal_finds_target(self):
        root = GraphNode(node_id="root", node_type="entity")
        child = GraphNode(node_id="child", node_type="entity")
        root.add_next(child)
        # BFS should find the child by its value (which is node_id)
        assert root.bfs("child") is True

    def test_bfs_traversal_returns_path(self):
        root = GraphNode(node_id="root", node_type="entity")
        child = GraphNode(node_id="child", node_type="entity")
        root.add_next(child)
        # BFS with return_path should return the path of nodes
        path = root.bfs("child", return_path=True)
        assert path is not None
        assert path[-1].node_id == "child"

    def test_add_next_with_multiple_children(self):
        parent = GraphNode(node_id="p", node_type="entity")
        c1 = GraphNode(node_id="c1", node_type="entity")
        c2 = GraphNode(node_id="c2", node_type="entity")
        parent.add_next(c1)
        parent.add_next(c2)
        assert len(parent.next) == 2
        assert c1 in parent.next
        assert c2 in parent.next


class TestGraphNodeToDict:
    """Tests for GraphNode.to_dict serialization."""

    def test_to_dict_contains_all_graph_fields(self):
        node = GraphNode(
            node_id="n1",
            node_type="person",
            label="Alice",
            properties={"age": 30},
        )
        d = node.to_dict()
        assert d == {
            "node_id": "n1",
            "node_type": "person",
            "label": "Alice",
            "properties": {"age": 30},
        }

    def test_to_dict_excludes_next(self):
        node = GraphNode(node_id="n1", node_type="test")
        d = node.to_dict()
        assert "next" not in d

    def test_to_dict_excludes_previous(self):
        node = GraphNode(node_id="n1", node_type="test")
        d = node.to_dict()
        assert "previous" not in d

    def test_to_dict_excludes_value(self):
        node = GraphNode(node_id="n1", node_type="test")
        d = node.to_dict()
        assert "value" not in d

    def test_to_dict_with_defaults(self):
        node = GraphNode(node_id="n1", node_type="test")
        d = node.to_dict()
        assert d["label"] == ""
        assert d["properties"] == {}

    def test_to_dict_returns_copy_of_properties(self):
        original_props = {"key": "value"}
        node = GraphNode(node_id="n1", node_type="test", properties=original_props)
        d = node.to_dict()
        d["properties"]["new_key"] = "new_value"
        assert "new_key" not in node.properties

    def test_to_dict_with_complex_properties(self):
        props = {"tags": ["a", "b"], "count": 42, "nested": {"x": 1}}
        node = GraphNode(node_id="n1", node_type="test", properties=props)
        d = node.to_dict()
        assert d["properties"] == {"tags": ["a", "b"], "count": 42, "nested": {"x": 1}}


class TestGraphNodeFromDict:
    """Tests for GraphNode.from_dict deserialization."""

    def test_from_dict_with_all_fields(self):
        data = {
            "node_id": "n1",
            "node_type": "person",
            "label": "Alice",
            "properties": {"age": 30},
        }
        node = GraphNode.from_dict(data)
        assert node.node_id == "n1"
        assert node.node_type == "person"
        assert node.label == "Alice"
        assert node.properties == {"age": 30}

    def test_from_dict_with_minimal_fields(self):
        data = {"node_id": "n1", "node_type": "test"}
        node = GraphNode.from_dict(data)
        assert node.node_id == "n1"
        assert node.node_type == "test"
        assert node.label == ""
        assert node.properties == {}

    def test_from_dict_sets_value_to_node_id(self):
        data = {"node_id": "n1", "node_type": "test"}
        node = GraphNode.from_dict(data)
        assert node.value == "n1"


class TestGraphNodeRoundTrip:
    """Tests for GraphNode to_dict / from_dict round-trip."""

    def test_round_trip_with_all_fields(self):
        original = GraphNode(
            node_id="n1",
            node_type="person",
            label="Alice",
            properties={"age": 30, "tags": ["a", "b"]},
        )
        restored = GraphNode.from_dict(original.to_dict())
        assert restored.node_id == original.node_id
        assert restored.node_type == original.node_type
        assert restored.label == original.label
        assert restored.properties == original.properties

    def test_round_trip_with_defaults(self):
        original = GraphNode(node_id="n1", node_type="test")
        restored = GraphNode.from_dict(original.to_dict())
        assert restored.node_id == original.node_id
        assert restored.node_type == original.node_type
        assert restored.label == original.label
        assert restored.properties == original.properties

    def test_round_trip_with_empty_properties(self):
        original = GraphNode(node_id="n1", node_type="test", properties={})
        restored = GraphNode.from_dict(original.to_dict())
        assert restored.properties == {}


class TestGraphEdgeConstruction:
    """Tests for GraphEdge construction and defaults."""

    def test_construction_with_required_fields(self):
        edge = GraphEdge(source_id="s1", target_id="t1", edge_type="knows")
        assert edge.source_id == "s1"
        assert edge.target_id == "t1"
        assert edge.edge_type == "knows"
        assert edge.properties == {}

    def test_construction_with_all_fields(self):
        props = {"weight": 0.5, "since": "2024"}
        edge = GraphEdge(
            source_id="s1",
            target_id="t1",
            edge_type="knows",
            properties=props,
        )
        assert edge.source_id == "s1"
        assert edge.target_id == "t1"
        assert edge.edge_type == "knows"
        assert edge.properties == {"weight": 0.5, "since": "2024"}

    def test_empty_properties_defaults_to_empty_dict(self):
        edge = GraphEdge(source_id="s1", target_id="t1", edge_type="rel")
        assert edge.properties == {}

    def test_properties_factory_creates_independent_dicts(self):
        e1 = GraphEdge(source_id="s1", target_id="t1", edge_type="rel")
        e2 = GraphEdge(source_id="s2", target_id="t2", edge_type="rel")
        e1.properties["key"] = "value"
        assert "key" not in e2.properties


class TestGraphEdgeToDict:
    """Tests for GraphEdge.to_dict serialization."""

    def test_to_dict_contains_all_fields(self):
        edge = GraphEdge(
            source_id="s1",
            target_id="t1",
            edge_type="knows",
            properties={"weight": 0.5},
        )
        d = edge.to_dict()
        assert d == {
            "source_id": "s1",
            "target_id": "t1",
            "edge_type": "knows",
            "properties": {"weight": 0.5},
        }

    def test_to_dict_with_defaults(self):
        edge = GraphEdge(source_id="s1", target_id="t1", edge_type="rel")
        d = edge.to_dict()
        assert d["properties"] == {}

    def test_to_dict_returns_copy_of_properties(self):
        original_props = {"key": "value"}
        edge = GraphEdge(
            source_id="s1", target_id="t1", edge_type="rel", properties=original_props
        )
        d = edge.to_dict()
        d["properties"]["new_key"] = "new_value"
        assert "new_key" not in edge.properties


class TestGraphEdgeFromDict:
    """Tests for GraphEdge.from_dict deserialization."""

    def test_from_dict_with_all_fields(self):
        data = {
            "source_id": "s1",
            "target_id": "t1",
            "edge_type": "knows",
            "properties": {"weight": 0.5},
        }
        edge = GraphEdge.from_dict(data)
        assert edge.source_id == "s1"
        assert edge.target_id == "t1"
        assert edge.edge_type == "knows"
        assert edge.properties == {"weight": 0.5}

    def test_from_dict_with_minimal_fields(self):
        data = {"source_id": "s1", "target_id": "t1", "edge_type": "rel"}
        edge = GraphEdge.from_dict(data)
        assert edge.source_id == "s1"
        assert edge.target_id == "t1"
        assert edge.edge_type == "rel"
        assert edge.properties == {}


class TestGraphEdgeRoundTrip:
    """Tests for GraphEdge to_dict / from_dict round-trip."""

    def test_round_trip_with_all_fields(self):
        original = GraphEdge(
            source_id="s1",
            target_id="t1",
            edge_type="knows",
            properties={"weight": 0.5, "tags": ["a"]},
        )
        restored = GraphEdge.from_dict(original.to_dict())
        assert restored.source_id == original.source_id
        assert restored.target_id == original.target_id
        assert restored.edge_type == original.edge_type
        assert restored.properties == original.properties

    def test_round_trip_with_empty_properties(self):
        original = GraphEdge(source_id="s1", target_id="t1", edge_type="rel")
        restored = GraphEdge.from_dict(original.to_dict())
        assert restored.source_id == original.source_id
        assert restored.target_id == original.target_id
        assert restored.edge_type == original.edge_type
        assert restored.properties == {}
