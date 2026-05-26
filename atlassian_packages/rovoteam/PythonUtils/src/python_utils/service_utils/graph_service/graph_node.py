"""
GraphNode and GraphEdge Models

GraphNode extends the existing Node class from algorithms/graph with typed
identity and properties, enabling graph storage services while preserving
compatibility with BFS/DFS traversal algorithms.

GraphEdge represents a directed, typed edge between two graph nodes.
"""

from typing import Any, Dict, List

from attr import attrs, attrib

from python_utils.algorithms.graph.node import Node
from python_utils.service_utils.data_operation_record import DataOperationRecord


@attrs(slots=False, eq=False, hash=False)
class GraphNode(Node):
    """A graph node extending Node with typed identity and properties.

    Inherits BFS, DFS, shortest_path_to_target from Node.
    Uses kw_only=True to resolve attrs field ordering since Node has
    optional fields (value, next, previous) before GraphNode's required node_id.

    Attributes:
        node_id: Unique identifier for this node.
        node_type: The type/category of this node.
        label: Optional human-readable label for the node.
        properties: Arbitrary key-value properties associated with the node.
        history: List of DataOperationRecord tracking all operations on this node.
        is_active: Whether this node is active (False = soft-deleted).
    """

    node_id: str = attrib(kw_only=True)
    node_type: str = attrib(kw_only=True)
    label: str = attrib(default="", kw_only=True)
    properties: Dict[str, Any] = attrib(factory=dict, kw_only=True)
    history: List[DataOperationRecord] = attrib(factory=list, kw_only=True)
    is_active: bool = attrib(default=True, kw_only=True)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.value = self.node_id  # Enable inherited BFS equality

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict. Excludes inherited Node traversal fields.

        The inherited next, previous, and value fields are not serialized
        because storage backends manage edges separately. The materialize
        function reconstructs these links when loading from a backend.

        Returns:
            Dictionary containing node_id, node_type, label, and properties.
        """
        d = {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "label": self.label,
            "properties": dict(self.properties),
        }
        if self.history:
            d["history"] = [r.to_dict() for r in self.history]
        if not self.is_active:
            d["is_active"] = self.is_active
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GraphNode":
        """Reconstruct a GraphNode from a dictionary.

        Args:
            data: Dictionary containing node fields.
                Must include 'node_id' and 'node_type'.
                Optional fields default to their standard defaults.

        Returns:
            A new GraphNode instance.
        """
        return cls(
            node_id=data["node_id"],
            node_type=data["node_type"],
            label=data.get("label", ""),
            properties=data.get("properties", {}),
            history=[
                DataOperationRecord.from_dict(r)
                for r in data.get("history", [])
            ],
            is_active=data.get("is_active", True),
        )


@attrs
class GraphEdge:
    """A directed, typed edge between two graph nodes.

    Attributes:
        source_id: The node_id of the source (origin) node.
        target_id: The node_id of the target (destination) node.
        edge_type: The type/category of this edge relationship.
        properties: Arbitrary key-value properties associated with the edge.
        history: List of DataOperationRecord tracking all operations on this edge.
        is_active: Whether this edge is active (False = soft-deleted).
    """

    source_id: str = attrib()
    target_id: str = attrib()
    edge_type: str = attrib()
    properties: Dict[str, Any] = attrib(factory=dict)
    history: List[DataOperationRecord] = attrib(factory=list)
    is_active: bool = attrib(default=True)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the edge to a dictionary.

        Returns:
            Dictionary containing all edge fields.
        """
        d = {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "edge_type": self.edge_type,
            "properties": dict(self.properties),
        }
        if self.history:
            d["history"] = [r.to_dict() for r in self.history]
        if not self.is_active:
            d["is_active"] = self.is_active
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GraphEdge":
        """Reconstruct a GraphEdge from a dictionary.

        Args:
            data: Dictionary containing edge fields.
                Must include 'source_id', 'target_id', and 'edge_type'.
                Optional fields default to their standard defaults.

        Returns:
            A new GraphEdge instance.
        """
        return cls(
            source_id=data["source_id"],
            target_id=data["target_id"],
            edge_type=data["edge_type"],
            properties=data.get("properties", {}),
            history=[
                DataOperationRecord.from_dict(r)
                for r in data.get("history", [])
            ],
            is_active=data.get("is_active", True),
        )
