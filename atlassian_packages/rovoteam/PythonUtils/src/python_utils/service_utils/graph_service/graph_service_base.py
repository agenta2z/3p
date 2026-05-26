"""
Graph Service Base Class

Abstract base class defining the interface for graph storage services.
All graph service implementations should inherit from this class.

This ensures a consistent API across different backend implementations
(memory, file, NetworkX, Neo4j, etc.).
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from attr import attrs

from python_utils.service_utils.graph_service.graph_node import GraphEdge, GraphNode


@attrs(slots=False)
class GraphServiceBase(ABC):
    """
    Abstract base class for graph storage services.

    Defines the standard interface that all graph service implementations
    must implement. This allows different backends (memory, file, NetworkX,
    Neo4j, etc.) to be used interchangeably.

    Core Node Operations:
        - add_node: Add a node to the graph
        - get_node: Retrieve a node by its ID
        - remove_node: Remove a node and cascade-delete all its edges
        - list_nodes: List nodes with optional type and namespace filters

    Core Edge Operations:
        - add_edge: Add a directed edge between two existing nodes
        - get_edges: Get edges for a node with optional type and direction filters
        - remove_edge: Remove a specific edge

    Traversal Operations:
        - get_neighbors: Get neighboring nodes up to a given depth

    Service Operations:
        - size: Get the number of nodes in a namespace
        - clear: Remove all nodes and edges in a namespace
        - close: Close the service connection
        - ping: Check if service is responsive
        - get_stats: Get statistics about the service
        - namespaces: List all namespaces

    Namespace Semantics:
        - namespace=None maps to "_default" internally
        - Each backend handles this mapping in its own implementation

    Edge Semantics:
        - add_edge raises ValueError if source or target node doesn't exist
        - remove_node cascade-deletes all edges where the removed node is
          source or target

    Context Manager Support:
        Services support the 'with' statement for automatic cleanup.
    """

    @abstractmethod
    def add_node(self, node: GraphNode, namespace: Optional[str] = None) -> None:
        """
        Add a node to the graph.

        If a node with the same node_id already exists in the namespace,
        it is overwritten (upsert semantics).

        Args:
            node: The GraphNode to add.
            namespace: Optional namespace to scope the storage.
                      None maps to "_default" internally.
        """
        pass

    @abstractmethod
    def get_node(self, node_id: str, namespace: Optional[str] = None) -> Optional[GraphNode]:
        """
        Retrieve a node by its ID.

        Args:
            node_id: The unique node identifier.
            namespace: Optional namespace to scope the lookup.
                      None maps to "_default" internally.

        Returns:
            The GraphNode if found, or None if no node with that ID exists.
        """
        pass

    @abstractmethod
    def remove_node(self, node_id: str, namespace: Optional[str] = None) -> bool:
        """
        Remove a node and cascade-delete all its edges.

        When a node is removed, all edges where the removed node is either
        source or target are also deleted (no orphaned edges).

        Args:
            node_id: The unique node identifier.
            namespace: Optional namespace to scope the removal.
                      None maps to "_default" internally.

        Returns:
            True if the node was removed, False if no node with that ID existed.
        """
        pass

    @abstractmethod
    def add_edge(self, edge: GraphEdge, namespace: Optional[str] = None) -> None:
        """
        Add a directed edge between two existing nodes.

        Args:
            edge: The GraphEdge to add.
            namespace: Optional namespace to scope the storage.
                      None maps to "_default" internally.

        Raises:
            ValueError: If the source or target node does not exist
                       in the namespace.
        """
        pass

    @abstractmethod
    def get_edges(
        self,
        node_id: str,
        edge_type: Optional[str] = None,
        direction: str = "outgoing",
        namespace: Optional[str] = None,
    ) -> List[GraphEdge]:
        """
        Get edges for a node with optional type and direction filters.

        Args:
            node_id: The node to get edges for.
            edge_type: Optional edge type filter. If None, returns all types.
            direction: Edge direction filter. One of "outgoing", "incoming",
                      or "both". Defaults to "outgoing".
            namespace: Optional namespace to scope the lookup.
                      None maps to "_default" internally.

        Returns:
            List of GraphEdge objects matching the filters.
        """
        pass

    @abstractmethod
    def remove_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        namespace: Optional[str] = None,
    ) -> bool:
        """
        Remove a specific edge.

        Args:
            source_id: The source node ID.
            target_id: The target node ID.
            edge_type: The edge type.
            namespace: Optional namespace to scope the removal.
                      None maps to "_default" internally.

        Returns:
            True if the edge was removed, False if no such edge existed.
        """
        pass

    @abstractmethod
    def get_neighbors(
        self,
        node_id: str,
        edge_type: Optional[str] = None,
        depth: int = 1,
        namespace: Optional[str] = None,
    ) -> List[Tuple[GraphNode, int]]:
        """
        Get neighboring nodes up to a given depth.

        Traverses outgoing edges from the specified node, following edges
        of the given type (or all types if None) up to the specified depth.

        Args:
            node_id: The starting node ID.
            edge_type: Optional edge type filter. If None, follows all types.
            depth: Maximum traversal depth. Defaults to 1.
            namespace: Optional namespace to scope the traversal.
                      None maps to "_default" internally.

        Returns:
            List of (GraphNode, depth) tuples, where depth indicates how
            many edges away the neighbor is from the starting node.
        """
        pass

    @abstractmethod
    def list_nodes(
        self,
        node_type: Optional[str] = None,
        namespace: Optional[str] = None,
    ) -> List[GraphNode]:
        """
        List nodes with optional type and namespace filters.

        Args:
            node_type: Optional node type filter. If None, returns all types.
            namespace: Optional namespace to scope the listing.
                      None maps to "_default" internally.

        Returns:
            List of GraphNode objects matching the filters.
        """
        pass

    @abstractmethod
    def size(self, namespace: Optional[str] = None) -> int:
        """
        Get the number of nodes in a namespace.

        Args:
            namespace: Optional namespace to get the size of.
                      None maps to "_default" internally.

        Returns:
            Number of nodes in the namespace.
        """
        pass

    @abstractmethod
    def clear(self, namespace: Optional[str] = None) -> int:
        """
        Remove all nodes and edges in a namespace.

        Args:
            namespace: Optional namespace to clear.
                      None maps to "_default" internally.

        Returns:
            Number of nodes removed.
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """
        Close the service connection and clean up resources.

        This method is idempotent — calling it multiple times is safe.
        """
        pass

    @abstractmethod
    def ping(self) -> bool:
        """
        Check if service is responsive.

        Returns:
            True if service is responsive, False otherwise.
        """
        pass

    @abstractmethod
    def get_stats(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics about the service.

        Args:
            namespace: Optional namespace to get stats for.
                      If None, returns stats for all namespaces.

        Returns:
            Dictionary with service statistics.
        """
        pass

    @abstractmethod
    def namespaces(self) -> List[str]:
        """
        List all namespaces that contain graph data.

        Returns:
            List of namespace strings.
        """
        pass

    # ── Context manager protocol ──

    @abstractmethod
    def __enter__(self):
        """Context manager entry."""
        pass

    @abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        pass

    @abstractmethod
    def __repr__(self) -> str:
        """String representation of the service."""
        pass

    # ── Optional search support ──

    @property
    def supports_search(self) -> bool:
        """Whether this service supports ``search_nodes()``.

        Subclasses that implement ``search_nodes()`` should override this
        to return ``True``.  Default is ``False``.
        """
        return False

    def search_nodes(
        self,
        query: str,
        top_k: int = 5,
        node_type: Optional[str] = None,
        namespace: Optional[str] = None,
    ) -> List[Tuple[GraphNode, float]]:
        """Search nodes by query text.

        Default raises ``NotImplementedError``.  Subclasses that support
        search should override this method and set ``supports_search``
        to return ``True``.

        Args:
            query: The search query string.
            top_k: Maximum number of results to return.
            node_type: Optional filter to return only nodes of this type.
            namespace: Optional namespace to scope the search.

        Returns:
            List of ``(GraphNode, score)`` tuples ordered by descending
            score.  Scores are in [0.0, 1.0].
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support search_nodes"
        )
