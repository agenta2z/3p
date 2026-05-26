"""
Subgraph Materialization

Loads a subgraph from any GraphServiceBase backend into linked GraphNode
objects with next/previous references, enabling in-memory traversal using
existing BFS/DFS algorithms from algorithms/graph.

The materialize_subgraph function performs a BFS from a start node, following
outgoing edges of a given type up to a specified depth. It creates copies of
all traversed nodes (via from_dict(to_dict())) to avoid mutating stored nodes,
and links them using add_next (which automatically sets previous on the target).

The returned GraphNode objects are fully compatible with:
- bfs_traversal({GraphNode: 'next'})
- dfs_traversal({GraphNode: 'next'})
- Node.shortest_path_to_target()

Usage:
    from python_utils.service_utils.graph_service.materialize import (
        materialize_subgraph,
    )
    from python_utils.service_utils.graph_service.memory_graph_service import (
        MemoryGraphService,
    )

    service = MemoryGraphService()
    # ... add nodes and edges ...

    start = materialize_subgraph(service, "node_a", edge_type="knows", depth=2)
    # start.next contains linked GraphNode copies for outgoing edges

    # Compatible with traversal algorithms:
    from python_utils.algorithms.graph.traversal import bfs_traversal
    for node in bfs_traversal(start, {GraphNode: 'next'}):
        print(node.node_id)
"""

from collections import deque
from typing import Optional

from python_utils.service_utils.graph_service.graph_node import GraphNode
from python_utils.service_utils.graph_service.graph_service_base import GraphServiceBase


def materialize_subgraph(
    service: GraphServiceBase,
    start_node_id: str,
    edge_type: Optional[str] = None,
    depth: int = 1,
    namespace: Optional[str] = None,
) -> GraphNode:
    """Traverse from a start node, following edges of a given type up to depth.

    Starting from start_node_id, follows outgoing edges matching edge_type
    up to the specified depth. If edge_type is None, follows all edge types.
    Returns the start GraphNode with next/previous links populated according
    to the traversed edges.

    All returned GraphNode objects are copies created via from_dict(to_dict())
    to avoid mutating nodes stored in the service.

    The returned GraphNode objects are fully compatible with bfs_traversal,
    dfs_traversal, and Node.shortest_path_to_target.

    Args:
        service: The graph service backend to load nodes and edges from.
        start_node_id: The node_id of the starting node.
        edge_type: Optional edge type filter. If None, follows all edge types.
        depth: Maximum traversal depth. Defaults to 1.
        namespace: Optional namespace to scope the traversal.

    Returns:
        The start GraphNode (a copy) with next/previous links populated
        for all traversed edges up to the specified depth.

    Raises:
        ValueError: If the start node does not exist in the service.
    """
    # Get the start node from the service
    start_node = service.get_node(start_node_id, namespace=namespace)
    if start_node is None:
        raise ValueError(
            f"Start node '{start_node_id}' does not exist"
            + (f" in namespace '{namespace}'" if namespace is not None else "")
        )

    # Create a copy of the start node to avoid mutating stored nodes
    # Map from node_id -> copied GraphNode for deduplication
    node_copies = {}
    start_copy = GraphNode.from_dict(start_node.to_dict())
    node_copies[start_node_id] = start_copy

    # BFS traversal from start node, following outgoing edges up to depth
    # Queue entries: (node_id, current_depth)
    queue = deque()
    queue.append((start_node_id, 0))

    while queue:
        current_id, current_depth = queue.popleft()

        if current_depth >= depth:
            continue

        # Get outgoing edges from the current node
        edges = service.get_edges(
            current_id,
            edge_type=edge_type,
            direction="outgoing",
            namespace=namespace,
        )

        for edge in edges:
            target_id = edge.target_id

            # Get or create a copy of the target node
            if target_id not in node_copies:
                target_node = service.get_node(target_id, namespace=namespace)
                if target_node is None:
                    # Target node doesn't exist in service, skip
                    continue
                target_copy = GraphNode.from_dict(target_node.to_dict())
                node_copies[target_id] = target_copy
                # Only enqueue nodes we haven't seen before to avoid cycles
                queue.append((target_id, current_depth + 1))

            # Link the current node copy to the target node copy
            current_copy = node_copies[current_id]
            target_copy = node_copies[target_id]
            current_copy.add_next(target_copy)

    return start_copy
