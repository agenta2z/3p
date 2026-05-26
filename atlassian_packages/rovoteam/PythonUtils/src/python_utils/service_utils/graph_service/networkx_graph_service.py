"""
NetworkX Graph Service

Graph storage service using NetworkX MultiDiGraph as the backend.
Each namespace gets its own MultiDiGraph instance, stored in a dict.
Thread-safe with threading.Lock for concurrent access.

Uses ``nx.MultiDiGraph`` to support multiple directed edges between the
same pair of nodes with different edge_types (e.g., A --knows--> B and
A --works_with--> B).

Best suited for:
- Graph analytics and algorithm integration with NetworkX ecosystem
- Medium-scale graphs that fit in memory
- Applications needing NetworkX's built-in algorithms (centrality,
  shortest paths, community detection, etc.)
- Testing and development with richer graph semantics

Limitations:
- Data is lost when the process exits (not persistent)
- Not suitable for inter-process communication
- Memory-bound by available RAM

Usage:
    from python_utils.service_utils.graph_service.networkx_graph_service import (
        NetworkxGraphService
    )

    service = NetworkxGraphService()
    node = GraphNode(node_id="n1", node_type="person", label="Alice")
    service.add_node(node)

    edge = GraphEdge(source_id="n1", target_id="n2", edge_type="knows")
    service.add_edge(edge)

    neighbors = service.get_neighbors("n1", depth=1)

    # With namespaces
    service.add_node(node, namespace="project_a")

    # Context manager
    with NetworkxGraphService() as svc:
        svc.add_node(GraphNode(node_id="n1", node_type="person"))
        result = svc.get_node("n1")

Requirements: 8.3
"""

import threading
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

import networkx as nx
from attr import attrs, attrib

from .graph_node import GraphEdge, GraphNode
from .graph_service_base import GraphServiceBase
from python_utils.service_utils.data_operation_record import DataOperationRecord

_DEFAULT_NAMESPACE = "_default"


@attrs(slots=False, repr=False)
class NetworkxGraphService(GraphServiceBase):
    """
    NetworkX-backed graph storage service.

    Stores each namespace as a separate ``nx.MultiDiGraph`` instance in a
    dictionary: ``Dict[str, nx.MultiDiGraph]``.

    Node attributes (node_type, label, properties) are stored as NetworkX
    node data. Edge attributes (edge_type, properties) are stored as
    NetworkX edge data, with edge_type used as the edge key to support
    multiple edges between the same pair of nodes.

    Thread-safe: all operations are protected by a threading.Lock.

    Attributes:
        _graphs: Dictionary mapping namespace to MultiDiGraph instance.
        _lock: Threading lock for thread-safe access.
        _closed: Flag indicating if the service has been closed.
    """

    _graphs: Dict[str, nx.MultiDiGraph] = attrib(init=False, factory=dict)
    _lock: threading.Lock = attrib(init=False, factory=threading.Lock)
    _closed: bool = attrib(init=False, default=False)

    def _resolve_namespace(self, namespace: Optional[str]) -> str:
        """Resolve namespace, mapping None to '_default'."""
        return namespace if namespace is not None else _DEFAULT_NAMESPACE

    def _get_graph(self, ns: str) -> nx.MultiDiGraph:
        """Get or create the MultiDiGraph for a namespace.

        Must be called within a lock context.
        """
        if ns not in self._graphs:
            self._graphs[ns] = nx.MultiDiGraph()
        return self._graphs[ns]

    def add_node(self, node: GraphNode, namespace: Optional[str] = None) -> None:
        """
        Add a node to the graph (upsert semantics).

        If a node with the same node_id already exists in the namespace,
        it is overwritten.

        Args:
            node: The GraphNode to add.
            namespace: Optional namespace to scope the storage.
                      None maps to "_default" internally.
        """
        ns = self._resolve_namespace(namespace)
        with self._lock:
            graph = self._get_graph(ns)
            graph.add_node(
                node.node_id,
                node_type=node.node_type,
                label=node.label,
                properties=dict(node.properties),
                history=[r.to_dict() for r in node.history],
                is_active=node.is_active,
            )

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
        ns = self._resolve_namespace(namespace)
        with self._lock:
            if ns not in self._graphs:
                return None
            graph = self._graphs[ns]
            if node_id not in graph:
                return None
            data = dict(graph.nodes[node_id])
            history_raw = data.get("history", [])
            history = [
                DataOperationRecord.from_dict(r) if isinstance(r, dict) else r
                for r in history_raw
            ]
            return GraphNode(
                node_id=node_id,
                node_type=data["node_type"],
                label=data.get("label", ""),
                properties=data.get("properties", {}),
                history=history,
                is_active=data.get("is_active", True),
            )

    def remove_node(self, node_id: str, namespace: Optional[str] = None) -> bool:
        """
        Remove a node and cascade-delete all its edges.

        NetworkX's ``remove_node`` automatically removes all edges
        connected to the node (both incoming and outgoing).

        Args:
            node_id: The unique node identifier.
            namespace: Optional namespace to scope the removal.
                      None maps to "_default" internally.

        Returns:
            True if the node was removed, False if no node with that ID existed.
        """
        ns = self._resolve_namespace(namespace)
        with self._lock:
            if ns not in self._graphs:
                return False
            graph = self._graphs[ns]
            if node_id not in graph:
                return False
            graph.remove_node(node_id)
            # Clean up empty namespace
            if graph.number_of_nodes() == 0:
                del self._graphs[ns]
            return True

    def add_edge(self, edge: GraphEdge, namespace: Optional[str] = None) -> None:
        """
        Add a directed edge between two existing nodes.

        Uses edge_type as the edge key in the MultiDiGraph, allowing
        multiple edges between the same pair of nodes with different types.

        Args:
            edge: The GraphEdge to add.
            namespace: Optional namespace to scope the storage.
                      None maps to "_default" internally.

        Raises:
            ValueError: If the source or target node does not exist
                       in the namespace.
        """
        ns = self._resolve_namespace(namespace)
        with self._lock:
            graph = self._graphs.get(ns)
            if graph is None or edge.source_id not in graph:
                raise ValueError(
                    f"Source node '{edge.source_id}' does not exist "
                    f"in namespace '{ns}'"
                )
            if edge.target_id not in graph:
                raise ValueError(
                    f"Target node '{edge.target_id}' does not exist "
                    f"in namespace '{ns}'"
                )
            graph.add_edge(
                edge.source_id,
                edge.target_id,
                key=edge.edge_type,
                edge_type=edge.edge_type,
                properties=dict(edge.properties),
                history=[r.to_dict() for r in edge.history],
                is_active=edge.is_active,
            )

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
        ns = self._resolve_namespace(namespace)
        with self._lock:
            if ns not in self._graphs:
                return []
            graph = self._graphs[ns]
            if node_id not in graph:
                return []

            results = []

            def _edge_from_data(src, tgt, key, data):
                et = data.get("edge_type", key)
                history_raw = data.get("history", [])
                history = [
                    DataOperationRecord.from_dict(r) if isinstance(r, dict) else r
                    for r in history_raw
                ]
                return GraphEdge(
                    source_id=src, target_id=tgt, edge_type=et,
                    properties=data.get("properties", {}),
                    history=history,
                    is_active=data.get("is_active", True),
                )

            # Collect outgoing edges
            if direction in ("outgoing", "both"):
                for source, target, key, data in graph.out_edges(
                    node_id, keys=True, data=True
                ):
                    et = data.get("edge_type", key)
                    if edge_type is not None and et != edge_type:
                        continue
                    results.append(_edge_from_data(source, target, key, data))

            # Collect incoming edges
            if direction in ("incoming", "both"):
                for source, target, key, data in graph.in_edges(
                    node_id, keys=True, data=True
                ):
                    et = data.get("edge_type", key)
                    if edge_type is not None and et != edge_type:
                        continue
                    results.append(_edge_from_data(source, target, key, data))

            return results

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
        ns = self._resolve_namespace(namespace)
        with self._lock:
            if ns not in self._graphs:
                return False
            graph = self._graphs[ns]
            if not graph.has_edge(source_id, target_id, key=edge_type):
                return False
            graph.remove_edge(source_id, target_id, key=edge_type)
            return True

    def get_neighbors(
        self,
        node_id: str,
        edge_type: Optional[str] = None,
        depth: int = 1,
        namespace: Optional[str] = None,
    ) -> List[Tuple[GraphNode, int]]:
        """
        Get neighboring nodes up to a given depth using BFS traversal.

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
            The starting node is NOT included in the results.
        """
        ns = self._resolve_namespace(namespace)
        with self._lock:
            if ns not in self._graphs:
                return []
            graph = self._graphs[ns]
            if node_id not in graph:
                return []

            # BFS traversal
            visited = {node_id}
            queue = deque()
            queue.append((node_id, 0))
            result: List[Tuple[GraphNode, int]] = []

            while queue:
                current_id, current_depth = queue.popleft()
                if current_depth >= depth:
                    continue

                # Find outgoing edges from current node
                for _, target_id, key, data in graph.out_edges(
                    current_id, keys=True, data=True
                ):
                    # Filter by edge_type if specified
                    et = data.get("edge_type", key)
                    if edge_type is not None and et != edge_type:
                        continue

                    if target_id in visited:
                        continue
                    if target_id not in graph:
                        continue

                    visited.add(target_id)
                    neighbor_depth = current_depth + 1

                    # Reconstruct GraphNode from graph node data
                    node_data = dict(graph.nodes[target_id])
                    n_history_raw = node_data.get("history", [])
                    n_history = [
                        DataOperationRecord.from_dict(r) if isinstance(r, dict) else r
                        for r in n_history_raw
                    ]
                    neighbor_node = GraphNode(
                        node_id=target_id,
                        node_type=node_data["node_type"],
                        label=node_data.get("label", ""),
                        properties=node_data.get("properties", {}),
                        history=n_history,
                        is_active=node_data.get("is_active", True),
                    )
                    result.append((neighbor_node, neighbor_depth))
                    queue.append((target_id, neighbor_depth))

            return result

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
        ns = self._resolve_namespace(namespace)
        with self._lock:
            if ns not in self._graphs:
                return []
            graph = self._graphs[ns]
            result = []
            for nid, data in graph.nodes(data=True):
                if node_type is not None and data.get("node_type") != node_type:
                    continue
                l_history_raw = data.get("history", [])
                l_history = [
                    DataOperationRecord.from_dict(r) if isinstance(r, dict) else r
                    for r in l_history_raw
                ]
                result.append(
                    GraphNode(
                        node_id=nid,
                        node_type=data["node_type"],
                        label=data.get("label", ""),
                        properties=data.get("properties", {}),
                        history=l_history,
                        is_active=data.get("is_active", True),
                    )
                )
            return result

    def size(self, namespace: Optional[str] = None) -> int:
        """
        Get the number of nodes in a namespace.

        Args:
            namespace: Optional namespace to get the size of.
                      None maps to "_default" internally.

        Returns:
            Number of nodes in the namespace.
        """
        ns = self._resolve_namespace(namespace)
        with self._lock:
            if ns not in self._graphs:
                return 0
            return self._graphs[ns].number_of_nodes()

    def clear(self, namespace: Optional[str] = None) -> int:
        """
        Remove all nodes and edges in a namespace.

        Args:
            namespace: Optional namespace to clear.
                      None maps to "_default" internally.

        Returns:
            Number of nodes removed.
        """
        ns = self._resolve_namespace(namespace)
        with self._lock:
            if ns not in self._graphs:
                return 0
            count = self._graphs[ns].number_of_nodes()
            del self._graphs[ns]
            return count

    def close(self) -> None:
        """
        Close the service and clean up resources.

        This method is idempotent — calling it multiple times is safe.
        """
        self._closed = True

    def ping(self) -> bool:
        """
        Check if service is responsive.

        Returns:
            True if service is not closed, False otherwise.
        """
        return not self._closed

    def get_stats(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics about the service.

        Args:
            namespace: Optional namespace to get stats for.
                      If None, returns stats for all namespaces.

        Returns:
            Dictionary with service statistics including:
            - backend: "networkx"
            - namespace_count: number of namespaces
            - total_nodes: total number of nodes
            - total_edges: total number of edges
            - namespaces: per-namespace node/edge counts (when no namespace specified)
            - nodes: number of nodes (when namespace specified)
            - edges: number of edges (when namespace specified)
        """
        with self._lock:
            if namespace is not None:
                ns = namespace
                if ns not in self._graphs:
                    return {
                        "backend": "networkx",
                        "namespace": ns,
                        "nodes": 0,
                        "edges": 0,
                    }
                graph = self._graphs[ns]
                return {
                    "backend": "networkx",
                    "namespace": ns,
                    "nodes": graph.number_of_nodes(),
                    "edges": graph.number_of_edges(),
                }
            else:
                total_nodes = sum(g.number_of_nodes() for g in self._graphs.values())
                total_edges = sum(g.number_of_edges() for g in self._graphs.values())
                return {
                    "backend": "networkx",
                    "namespace_count": len(self._graphs),
                    "total_nodes": total_nodes,
                    "total_edges": total_edges,
                    "namespaces": {
                        ns: {
                            "nodes": g.number_of_nodes(),
                            "edges": g.number_of_edges(),
                        }
                        for ns, g in self._graphs.items()
                    },
                }

    def namespaces(self) -> List[str]:
        """
        List all namespaces that contain graph data.

        Returns:
            List of namespace strings.
        """
        with self._lock:
            return list(self._graphs.keys())

    # ── Context manager protocol ──

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit — delegates to close()."""
        self.close()

    def __repr__(self) -> str:
        """String representation of the service."""
        with self._lock:
            ns_count = len(self._graphs)
            total_nodes = sum(g.number_of_nodes() for g in self._graphs.values())
            total_edges = sum(g.number_of_edges() for g in self._graphs.values())
        return (
            f"NetworkxGraphService("
            f"namespaces={ns_count}, "
            f"total_nodes={total_nodes}, "
            f"total_edges={total_edges}, "
            f"closed={self._closed})"
        )
