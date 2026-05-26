"""
Memory Graph Service

In-memory graph storage service using Python dictionaries.
Thread-safe with threading.Lock for concurrent access.

Best suited for:
- Testing and development
- Single-process applications
- Quick prototyping without external dependencies
- Small graph datasets where persistence is not required

Limitations:
- Data is lost when the process exits (not persistent)
- Not suitable for inter-process communication
- Memory-bound by available RAM

Usage:
    from python_utils.service_utils.graph_service.memory_graph_service import (
        MemoryGraphService
    )

    service = MemoryGraphService()
    node = GraphNode(node_id="n1", node_type="person", label="Alice")
    service.add_node(node)

    edge = GraphEdge(source_id="n1", target_id="n2", edge_type="knows")
    service.add_edge(edge)

    neighbors = service.get_neighbors("n1", depth=1)

    # With namespaces
    service.add_node(node, namespace="project_a")

    # Context manager
    with MemoryGraphService() as svc:
        svc.add_node(GraphNode(node_id="n1", node_type="person"))
        result = svc.get_node("n1")
"""

import threading
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

from attr import attrs, attrib

from .graph_node import GraphEdge, GraphNode
from .graph_service_base import GraphServiceBase

_DEFAULT_NAMESPACE = "_default"


@attrs(slots=False, repr=False)
class MemoryGraphService(GraphServiceBase):
    """
    In-memory graph storage service.

    Stores nodes in a nested dictionary structure:
    ``Dict[str, Dict[str, GraphNode]]`` where the outer key is the namespace
    and the inner key is the node_id.

    Stores edges in a dictionary structure:
    ``Dict[str, List[GraphEdge]]`` where the key is the namespace
    and the value is a list of edges in that namespace.

    Thread-safe: all operations are protected by a threading.Lock.

    Attributes:
        _nodes: Nested dictionary for namespace-scoped node storage.
        _edges: Dictionary mapping namespace to list of edges.
        _lock: Threading lock for thread-safe access.
        _closed: Flag indicating if the service has been closed.
    """

    _nodes: Dict[str, Dict[str, GraphNode]] = attrib(init=False, factory=dict)
    _edges: Dict[str, List[GraphEdge]] = attrib(init=False, factory=dict)
    _lock: threading.Lock = attrib(init=False, factory=threading.Lock)
    _closed: bool = attrib(init=False, default=False)

    def _resolve_namespace(self, namespace: Optional[str]) -> str:
        """Resolve namespace, mapping None to '_default'."""
        return namespace if namespace is not None else _DEFAULT_NAMESPACE

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
            if ns not in self._nodes:
                self._nodes[ns] = {}
            self._nodes[ns][node.node_id] = node

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
            ns_nodes = self._nodes.get(ns)
            if ns_nodes is None:
                return None
            return ns_nodes.get(node_id)

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
        ns = self._resolve_namespace(namespace)
        with self._lock:
            ns_nodes = self._nodes.get(ns)
            if ns_nodes is None or node_id not in ns_nodes:
                return False
            del ns_nodes[node_id]
            # Clean up empty namespace for nodes
            if not ns_nodes:
                del self._nodes[ns]
            # Cascade delete all edges involving this node
            if ns in self._edges:
                self._edges[ns] = [
                    e for e in self._edges[ns]
                    if e.source_id != node_id and e.target_id != node_id
                ]
                # Clean up empty namespace for edges
                if not self._edges[ns]:
                    del self._edges[ns]
            return True

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
        ns = self._resolve_namespace(namespace)
        with self._lock:
            ns_nodes = self._nodes.get(ns, {})
            if edge.source_id not in ns_nodes:
                raise ValueError(
                    f"Source node '{edge.source_id}' does not exist "
                    f"in namespace '{ns}'"
                )
            if edge.target_id not in ns_nodes:
                raise ValueError(
                    f"Target node '{edge.target_id}' does not exist "
                    f"in namespace '{ns}'"
                )
            if ns not in self._edges:
                self._edges[ns] = []
            self._edges[ns].append(edge)

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
            ns_edges = self._edges.get(ns, [])
            result = []
            for e in ns_edges:
                # Check direction
                if direction == "outgoing" and e.source_id != node_id:
                    continue
                if direction == "incoming" and e.target_id != node_id:
                    continue
                if direction == "both" and e.source_id != node_id and e.target_id != node_id:
                    continue
                # Check edge type filter
                if edge_type is not None and e.edge_type != edge_type:
                    continue
                result.append(e)
            return result

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
            ns_edges = self._edges.get(ns)
            if ns_edges is None:
                return False
            for i, e in enumerate(ns_edges):
                if (e.source_id == source_id
                        and e.target_id == target_id
                        and e.edge_type == edge_type):
                    ns_edges.pop(i)
                    # Clean up empty namespace for edges
                    if not ns_edges:
                        del self._edges[ns]
                    return True
            return False

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
            ns_nodes = self._nodes.get(ns, {})
            ns_edges = self._edges.get(ns, [])

            if node_id not in ns_nodes:
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
                for e in ns_edges:
                    if e.source_id != current_id:
                        continue
                    if edge_type is not None and e.edge_type != edge_type:
                        continue
                    if e.target_id not in visited and e.target_id in ns_nodes:
                        visited.add(e.target_id)
                        neighbor_depth = current_depth + 1
                        result.append((ns_nodes[e.target_id], neighbor_depth))
                        queue.append((e.target_id, neighbor_depth))

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
            ns_nodes = self._nodes.get(ns, {})
            if node_type is None:
                return list(ns_nodes.values())
            return [n for n in ns_nodes.values() if n.node_type == node_type]

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
            ns_nodes = self._nodes.get(ns)
            if ns_nodes is None:
                return 0
            return len(ns_nodes)

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
            ns_nodes = self._nodes.get(ns)
            if ns_nodes is None:
                return 0
            count = len(ns_nodes)
            del self._nodes[ns]
            # Also clear edges for this namespace
            if ns in self._edges:
                del self._edges[ns]
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
            - backend: "memory"
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
                ns_nodes = self._nodes.get(ns, {})
                ns_edges = self._edges.get(ns, [])
                return {
                    "backend": "memory",
                    "namespace": ns,
                    "nodes": len(ns_nodes),
                    "edges": len(ns_edges),
                }
            else:
                total_nodes = sum(len(v) for v in self._nodes.values())
                total_edges = sum(len(v) for v in self._edges.values())
                return {
                    "backend": "memory",
                    "namespace_count": len(self._nodes),
                    "total_nodes": total_nodes,
                    "total_edges": total_edges,
                    "namespaces": {
                        ns: {
                            "nodes": len(self._nodes.get(ns, {})),
                            "edges": len(self._edges.get(ns, [])),
                        }
                        for ns in set(list(self._nodes.keys()) + list(self._edges.keys()))
                    },
                }

    def namespaces(self) -> List[str]:
        """
        List all namespaces that contain graph data.

        Returns:
            List of namespace strings.
        """
        with self._lock:
            # Combine namespaces from both nodes and edges
            all_ns = set(list(self._nodes.keys()) + list(self._edges.keys()))
            return list(all_ns)

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
            ns_count = len(self._nodes)
            total_nodes = sum(len(v) for v in self._nodes.values())
            total_edges = sum(len(v) for v in self._edges.values())
        return (
            f"MemoryGraphService("
            f"namespaces={ns_count}, "
            f"total_nodes={total_nodes}, "
            f"total_edges={total_edges}, "
            f"closed={self._closed})"
        )
