"""
File Graph Service

File-based graph storage service using JSON files on disk.
Nodes are stored as individual JSON files at:
    {base_dir}/{namespace}/nodes/{encoded_node_id}.json

Edges are stored as individual JSON files at:
    {base_dir}/{namespace}/edges/{encoded_edge_key}.json

where the edge key is a composite of source_id, target_id, and edge_type.

Keys are percent-encoded to produce safe filenames, using the same
encoding scheme as FileKeyValueService:
    '%' → '%25'  (first, to avoid double-encoding)
    ':' → '%3A'
    '/' → '%2F'
    '\\' → '%5C'

Best suited for:
- Persistent graph storage without external dependencies
- Single-process applications
- Human-readable data inspection on disk
- Moderate graph sizes where file I/O is acceptable

Limitations:
- Not thread-safe (single-process only)
- Performance degrades with very large numbers of nodes/edges per namespace
- No atomic multi-operation transactions

Usage:
    from python_utils.service_utils.graph_service.file_graph_service import (
        FileGraphService
    )

    service = FileGraphService(base_dir="/tmp/my_graph_store")
    node = GraphNode(node_id="n1", node_type="person", label="Alice")
    service.add_node(node)

    edge = GraphEdge(source_id="n1", target_id="n2", edge_type="knows")
    service.add_edge(edge)

    neighbors = service.get_neighbors("n1", depth=1)

    # With namespaces
    service.add_node(node, namespace="project_a")

    # Context manager
    with FileGraphService(base_dir="/tmp/store") as svc:
        svc.add_node(GraphNode(node_id="n1", node_type="person"))
        result = svc.get_node("n1")
"""

import json
import logging
import os
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

from attr import attrs, attrib

from .graph_node import GraphEdge, GraphNode
from .graph_service_base import GraphServiceBase
from python_utils.nlp_utils.semantic_search import tokenize, term_overlap_search

logger = logging.getLogger(__name__)

_DEFAULT_NAMESPACE = "_default"


def _encode_key(key: str) -> str:
    """Percent-encode a key for use as a filename.

    Uses the same encoding scheme as FileKeyValueService, plus additional
    characters that are invalid in Windows filenames:
        '%' → '%25'  (must be first to avoid double-encoding)
        ':' → '%3A'
        '/' → '%2F'
        '\\' → '%5C'
        '|' → '%7C'
        '<' → '%3C'
        '>' → '%3E'
        '"' → '%22'
        '?' → '%3F'
        '*' → '%2A'

    Args:
        key: The raw key string.

    Returns:
        A filesystem-safe encoded key string.
    """
    return (
        key
        .replace("%", "%25")
        .replace(":", "%3A")
        .replace("/", "%2F")
        .replace("\\", "%5C")
        .replace("|", "%7C")
        .replace("<", "%3C")
        .replace(">", "%3E")
        .replace('"', "%22")
        .replace("?", "%3F")
        .replace("*", "%2A")
    )


def _decode_key(encoded_key: str) -> str:
    """Reverse of _encode_key. Decodes percent-encoded key.

    Decodes in reverse order of encoding to ensure correctness:
        '%2A' → '*'
        '%3F' → '?'
        '%22' → '"'
        '%3E' → '>'
        '%3C' → '<'
        '%7C' → '|'
        '%5C' → '\\\\'
        '%2F' → '/'
        '%3A' → ':'
        '%25' → '%'  (must be last to avoid premature decoding)

    Args:
        encoded_key: The percent-encoded key string.

    Returns:
        The original key string.
    """
    return (
        encoded_key
        .replace("%2A", "*")
        .replace("%3F", "?")
        .replace("%22", '"')
        .replace("%3E", ">")
        .replace("%3C", "<")
        .replace("%7C", "|")
        .replace("%5C", "\\")
        .replace("%2F", "/")
        .replace("%3A", ":")
        .replace("%25", "%")
    )


def _edge_key(source_id: str, target_id: str, edge_type: str) -> str:
    """Build a composite key for an edge file.

    Uses '||' as separator since it's unlikely to appear in IDs and
    will be percent-encoded anyway.

    Args:
        source_id: The source node ID.
        target_id: The target node ID.
        edge_type: The edge type.

    Returns:
        A composite key string.
    """
    return f"{source_id}||{target_id}||{edge_type}"


@attrs(slots=False, repr=False)
class FileGraphService(GraphServiceBase):
    """
    File-based graph storage service.

    Stores nodes as JSON files at:
        {base_dir}/{namespace}/nodes/{encoded_node_id}.json

    Stores edges as JSON files at:
        {base_dir}/{namespace}/edges/{encoded_edge_key}.json

    Node IDs and edge keys are percent-encoded to produce safe filenames.
    Namespace=None maps to "_default" internally.

    Attributes:
        base_dir: Root directory for all graph files.
    """

    base_dir: str = attrib()
    _closed: bool = attrib(init=False, default=False)

    def __attrs_post_init__(self):
        """Create the base directory on initialization."""
        os.makedirs(self.base_dir, exist_ok=True)

    # ── Internal helpers ──

    def _resolve_namespace(self, namespace: Optional[str]) -> str:
        """Resolve namespace, mapping None to '_default'."""
        return namespace if namespace is not None else _DEFAULT_NAMESPACE

    def _nodes_dir(self, namespace: str) -> str:
        """Return the directory path for nodes in a namespace."""
        return os.path.join(self.base_dir, namespace, "nodes")

    def _edges_dir(self, namespace: str) -> str:
        """Return the directory path for edges in a namespace."""
        return os.path.join(self.base_dir, namespace, "edges")

    def _node_path(self, namespace: str, node_id: str) -> str:
        """Return the file path for a node."""
        encoded = _encode_key(node_id)
        return os.path.join(self._nodes_dir(namespace), f"{encoded}.json")

    def _edge_path(self, namespace: str, source_id: str, target_id: str, edge_type: str) -> str:
        """Return the file path for an edge."""
        key = _edge_key(source_id, target_id, edge_type)
        encoded = _encode_key(key)
        return os.path.join(self._edges_dir(namespace), f"{encoded}.json")

    def _read_json(self, path: str) -> Optional[Dict[str, Any]]:
        """Read and parse a JSON file, returning None on error."""
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("Skipping malformed JSON file %s: %s", path, exc)
            return None

    def _write_json(self, path: str, data: Dict[str, Any]) -> None:
        """Write data as JSON to a file, creating directories as needed."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _load_all_edges(self, namespace: str) -> List[GraphEdge]:
        """Load all edges from a namespace's edges directory."""
        edges_dir = self._edges_dir(namespace)
        if not os.path.isdir(edges_dir):
            return []
        result = []
        for filename in os.listdir(edges_dir):
            if filename.endswith(".json"):
                path = os.path.join(edges_dir, filename)
                data = self._read_json(path)
                if data is not None:
                    try:
                        result.append(GraphEdge.from_dict(data))
                    except (KeyError, TypeError) as exc:
                        logger.warning("Skipping malformed edge file %s: %s", path, exc)
        return result

    def _node_exists(self, namespace: str, node_id: str) -> bool:
        """Check if a node file exists."""
        return os.path.exists(self._node_path(namespace, node_id))

    def _cleanup_empty_dirs(self, namespace: str) -> None:
        """Remove empty nodes/edges/namespace directories."""
        nodes_dir = self._nodes_dir(namespace)
        edges_dir = self._edges_dir(namespace)
        ns_dir = os.path.join(self.base_dir, namespace)

        if os.path.isdir(nodes_dir) and not os.listdir(nodes_dir):
            os.rmdir(nodes_dir)
        if os.path.isdir(edges_dir) and not os.listdir(edges_dir):
            os.rmdir(edges_dir)
        if os.path.isdir(ns_dir) and not os.listdir(ns_dir):
            os.rmdir(ns_dir)

    # ── Node operations ──

    def add_node(self, node: GraphNode, namespace: Optional[str] = None) -> None:
        """
        Add a node to the graph by writing its JSON file (upsert semantics).

        If a node with the same node_id already exists in the namespace,
        the file is overwritten.

        Args:
            node: The GraphNode to add.
            namespace: Optional namespace to scope the storage.
                      None maps to "_default" internally.
        """
        ns = self._resolve_namespace(namespace)
        path = self._node_path(ns, node.node_id)
        self._write_json(path, node.to_dict())

    def get_node(self, node_id: str, namespace: Optional[str] = None) -> Optional[GraphNode]:
        """
        Retrieve a node by its ID by reading its JSON file.

        Args:
            node_id: The unique node identifier.
            namespace: Optional namespace to scope the lookup.
                      None maps to "_default" internally.

        Returns:
            The GraphNode if found, or None if no node with that ID exists
            or the file contains malformed JSON.
        """
        ns = self._resolve_namespace(namespace)
        path = self._node_path(ns, node_id)
        data = self._read_json(path)
        if data is None:
            return None
        try:
            return GraphNode.from_dict(data)
        except (KeyError, TypeError) as exc:
            logger.warning("Skipping malformed node file %s: %s", path, exc)
            return None

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
        node_path = self._node_path(ns, node_id)

        if not os.path.exists(node_path):
            return False

        os.remove(node_path)

        # Cascade delete all edges involving this node
        edges_dir = self._edges_dir(ns)
        if os.path.isdir(edges_dir):
            for filename in os.listdir(edges_dir):
                if not filename.endswith(".json"):
                    continue
                edge_path = os.path.join(edges_dir, filename)
                data = self._read_json(edge_path)
                if data is not None:
                    if data.get("source_id") == node_id or data.get("target_id") == node_id:
                        os.remove(edge_path)

        self._cleanup_empty_dirs(ns)
        return True

    # ── Edge operations ──

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

        if not self._node_exists(ns, edge.source_id):
            raise ValueError(
                f"Source node '{edge.source_id}' does not exist "
                f"in namespace '{ns}'"
            )
        if not self._node_exists(ns, edge.target_id):
            raise ValueError(
                f"Target node '{edge.target_id}' does not exist "
                f"in namespace '{ns}'"
            )

        path = self._edge_path(ns, edge.source_id, edge.target_id, edge.edge_type)
        self._write_json(path, edge.to_dict())

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
        all_edges = self._load_all_edges(ns)

        result = []
        for e in all_edges:
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
        Remove a specific edge by deleting its JSON file.

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
        path = self._edge_path(ns, source_id, target_id, edge_type)

        if os.path.exists(path):
            os.remove(path)
            self._cleanup_empty_dirs(ns)
            return True
        return False

    # ── Traversal operations ──

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

        # Check if start node exists
        if not self._node_exists(ns, node_id):
            return []

        # Load all edges for this namespace once
        all_edges = self._load_all_edges(ns)

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
            for e in all_edges:
                if e.source_id != current_id:
                    continue
                if edge_type is not None and e.edge_type != edge_type:
                    continue
                if e.target_id not in visited and self._node_exists(ns, e.target_id):
                    visited.add(e.target_id)
                    neighbor_node = self.get_node(e.target_id, namespace=namespace)
                    if neighbor_node is not None:
                        neighbor_depth = current_depth + 1
                        result.append((neighbor_node, neighbor_depth))
                        queue.append((e.target_id, neighbor_depth))

        return result

    # ── List and size operations ──

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
        nodes_dir = self._nodes_dir(ns)

        if not os.path.isdir(nodes_dir):
            return []

        result = []
        for filename in os.listdir(nodes_dir):
            if not filename.endswith(".json"):
                continue
            path = os.path.join(nodes_dir, filename)
            data = self._read_json(path)
            if data is not None:
                try:
                    node = GraphNode.from_dict(data)
                    if node_type is None or node.node_type == node_type:
                        result.append(node)
                except (KeyError, TypeError) as exc:
                    logger.warning("Skipping malformed node file %s: %s", path, exc)
        return result

    def size(self, namespace: Optional[str] = None) -> int:
        """
        Get the number of nodes in a namespace.

        Args:
            namespace: Optional namespace to get the size of.
                      None maps to "_default" internally.

        Returns:
            Number of node JSON files in the namespace.
        """
        ns = self._resolve_namespace(namespace)
        nodes_dir = self._nodes_dir(ns)

        if not os.path.isdir(nodes_dir):
            return 0

        return sum(1 for f in os.listdir(nodes_dir) if f.endswith(".json"))

    def clear(self, namespace: Optional[str] = None) -> int:
        """
        Remove all nodes and edges in a namespace.

        Also removes the namespace directories if they become empty.

        Args:
            namespace: Optional namespace to clear.
                      None maps to "_default" internally.

        Returns:
            Number of nodes removed.
        """
        ns = self._resolve_namespace(namespace)
        nodes_dir = self._nodes_dir(ns)
        edges_dir = self._edges_dir(ns)

        # Count and remove nodes
        count = 0
        if os.path.isdir(nodes_dir):
            for filename in os.listdir(nodes_dir):
                if filename.endswith(".json"):
                    os.remove(os.path.join(nodes_dir, filename))
                    count += 1

        # Remove edges
        if os.path.isdir(edges_dir):
            for filename in os.listdir(edges_dir):
                if filename.endswith(".json"):
                    os.remove(os.path.join(edges_dir, filename))

        self._cleanup_empty_dirs(ns)
        return count

    # ── Service operations ──

    def close(self) -> None:
        """
        Close the service.

        This method is idempotent — calling it multiple times is safe.
        Note: does not delete any files on disk.
        """
        self._closed = True

    def ping(self) -> bool:
        """
        Check if service is responsive.

        Returns:
            True if the base directory exists and service is not closed,
            False otherwise.
        """
        return not self._closed and os.path.isdir(self.base_dir)

    def get_stats(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics about the service.

        Args:
            namespace: Optional namespace to get stats for.
                      If None, returns stats for all namespaces.

        Returns:
            Dictionary with service statistics including:
            - backend: "file"
            - base_dir: the base directory path
            - namespace / nodes / edges (when namespace specified)
            - namespace_count / total_nodes / total_edges (when no namespace specified)
        """
        if namespace is not None:
            ns = namespace
            nodes_dir = self._nodes_dir(ns)
            edges_dir = self._edges_dir(ns)
            node_count = (
                sum(1 for f in os.listdir(nodes_dir) if f.endswith(".json"))
                if os.path.isdir(nodes_dir) else 0
            )
            edge_count = (
                sum(1 for f in os.listdir(edges_dir) if f.endswith(".json"))
                if os.path.isdir(edges_dir) else 0
            )
            return {
                "backend": "file",
                "base_dir": self.base_dir,
                "namespace": ns,
                "nodes": node_count,
                "edges": edge_count,
            }
        else:
            all_ns = self.namespaces()
            total_nodes = 0
            total_edges = 0
            ns_stats = {}
            for ns in all_ns:
                nodes_dir = self._nodes_dir(ns)
                edges_dir = self._edges_dir(ns)
                nc = (
                    sum(1 for f in os.listdir(nodes_dir) if f.endswith(".json"))
                    if os.path.isdir(nodes_dir) else 0
                )
                ec = (
                    sum(1 for f in os.listdir(edges_dir) if f.endswith(".json"))
                    if os.path.isdir(edges_dir) else 0
                )
                total_nodes += nc
                total_edges += ec
                ns_stats[ns] = {"nodes": nc, "edges": ec}
            return {
                "backend": "file",
                "base_dir": self.base_dir,
                "namespace_count": len(all_ns),
                "total_nodes": total_nodes,
                "total_edges": total_edges,
                "namespaces": ns_stats,
            }

    def namespaces(self) -> List[str]:
        """
        List all namespaces that contain graph data.

        Scans subdirectories of base_dir that contain a nodes or edges
        subdirectory with at least one JSON file.

        Returns:
            List of namespace strings.
        """
        if not os.path.isdir(self.base_dir):
            return []

        result = []
        for entry in os.listdir(self.base_dir):
            entry_path = os.path.join(self.base_dir, entry)
            if not os.path.isdir(entry_path):
                continue
            # Check if namespace has any nodes or edges
            nodes_dir = os.path.join(entry_path, "nodes")
            edges_dir = os.path.join(entry_path, "edges")
            has_nodes = (
                os.path.isdir(nodes_dir)
                and any(f.endswith(".json") for f in os.listdir(nodes_dir))
            )
            has_edges = (
                os.path.isdir(edges_dir)
                and any(f.endswith(".json") for f in os.listdir(edges_dir))
            )
            if has_nodes or has_edges:
                result.append(entry)
        return result

    # ── Search operations ──

    @staticmethod
    def _build_node_search_text(node: GraphNode) -> str:
        """Build searchable text from a graph node.

        Concatenates node_type, label, and property values.  Mirrors the
        ``default_node_text_builder`` pattern used by ``SemanticGraphStore``.
        Skips the ``embedding_text`` property key.

        Args:
            node: The GraphNode to convert to searchable text.

        Returns:
            A space-joined string of non-empty parts.
        """
        parts = [node.node_type, node.label]
        for key in sorted(node.properties.keys()):
            val = node.properties[key]
            if key == "embedding_text":
                continue
            if isinstance(val, str):
                parts.append(val)
            else:
                parts.append(f"{key}: {val}")
        return " ".join(p for p in parts if p)

    @property
    def supports_search(self) -> bool:
        """FileGraphService supports term-overlap search."""
        return True

    def search_nodes(
        self,
        query: str,
        top_k: int = 5,
        node_type: Optional[str] = None,
        namespace: Optional[str] = None,
    ) -> List[Tuple[GraphNode, float]]:
        """Search nodes by term-overlap scoring.

        Loads all nodes (optionally filtered by ``node_type``), builds
        searchable text for each, and delegates scoring to the shared
        ``term_overlap_search`` utility.

        Args:
            query: The search query string.  Empty/whitespace returns ``[]``.
            top_k: Maximum number of results to return.
            node_type: Optional filter to return only nodes of this type.
            namespace: Optional namespace to scope the search.

        Returns:
            List of ``(GraphNode, score)`` tuples ordered by descending
            score, then by ``node_id`` for determinism.  At most ``top_k``
            results.
        """
        if not query or not query.strip():
            return []
        query_tokens = tokenize(query, stem=True)
        if not query_tokens:
            return []
        nodes = self.list_nodes(node_type=node_type, namespace=namespace)
        if not nodes:
            return []
        return term_overlap_search(
            items=nodes,
            query_tokens=query_tokens,
            text_fn=self._build_node_search_text,
            id_fn=lambda n: n.node_id,
            top_k=top_k,
            stem=True,
        )

    # ── Context manager protocol ──

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit — delegates to close()."""
        self.close()

    def __repr__(self) -> str:
        """String representation of the service."""
        all_ns = self.namespaces()
        total_nodes = sum(self.size(namespace=ns) for ns in all_ns)
        total_edges = sum(
            len(self._load_all_edges(ns)) for ns in all_ns
        )
        return (
            f"FileGraphService("
            f"base_dir='{self.base_dir}', "
            f"namespaces={len(all_ns)}, "
            f"total_nodes={total_nodes}, "
            f"total_edges={total_edges}, "
            f"closed={self._closed})"
        )
