"""
Graph Service Tutorial 5: Subgraph Materialization and Traversal

Demonstrates advanced graph operations: materializing a subgraph from a
service backend into linked GraphNode objects, then traversing with BFS/DFS.

Topics covered:
    - Building a collaboration network in MemoryGraphService
    - materialize_subgraph: extract linked node copies from the service
    - BFS traversal on materialized graph
    - DFS traversal on materialized graph
    - Materialized nodes are copies (service data unchanged)
    - Materialization with different edge types
    - Materialization with deeper depth

Prerequisites:
    No external dependencies.

Usage:
    python 05_traversal_and_queries.py
"""

from resolve_path import resolve_path
resolve_path()

from python_utils.service_utils.graph_service.memory_graph_service import (
    MemoryGraphService,
)
from python_utils.service_utils.graph_service.graph_node import GraphNode, GraphEdge
from python_utils.service_utils.graph_service.materialize import materialize_subgraph
from python_utils.algorithms.graph.traversal import bfs_traversal, dfs_traversal


def _build_network(svc):
    """Build a research collaboration network.

    Network structure (co_authored edges):
        alice --> bob --> diana --> frank
        alice --> carol --> eve
        diana --> eve

    Affiliation edges:
        alice --> mit
        bob --> stanford
        carol --> mit
        diana --> harvard
        eve --> caltech
        frank --> stanford
    """
    # Researchers
    for nid, label, props in [
        ("alice", "Dr. Alice Chen", {"department": "Physics", "h_index": 42}),
        ("bob",   "Dr. Bob Patel",  {"department": "Bioinformatics", "h_index": 35}),
        ("carol", "Dr. Carol Kim",  {"department": "Climate", "h_index": 28}),
        ("diana", "Dr. Diana Lee",  {"department": "Genetics", "h_index": 51}),
        ("eve",   "Dr. Eve Zhang",  {"department": "Materials", "h_index": 33}),
        ("frank", "Dr. Frank Wu",   {"department": "Chemistry", "h_index": 22}),
    ]:
        svc.add_node(GraphNode(node_id=nid, node_type="researcher",
                               label=label, properties=props))

    # Institutions
    for nid, label in [
        ("mit", "MIT"), ("stanford", "Stanford"),
        ("harvard", "Harvard"), ("caltech", "Caltech"),
    ]:
        svc.add_node(GraphNode(node_id=nid, node_type="institution",
                               label=label, properties={}))

    # Co-authored edges (directed: source co-authored with target)
    for src, tgt, papers in [
        ("alice", "bob", 3), ("alice", "carol", 5),
        ("bob", "diana", 2), ("carol", "eve", 1),
        ("diana", "eve", 4), ("diana", "frank", 2),
    ]:
        svc.add_edge(GraphEdge(source_id=src, target_id=tgt,
                               edge_type="co_authored",
                               properties={"paper_count": papers}))

    # Affiliated_with edges
    for src, tgt in [
        ("alice", "mit"), ("bob", "stanford"), ("carol", "mit"),
        ("diana", "harvard"), ("eve", "caltech"), ("frank", "stanford"),
    ]:
        svc.add_edge(GraphEdge(source_id=src, target_id=tgt,
                               edge_type="affiliated_with"))


def main():
    # =================================================================
    # CORE CODE
    # =================================================================

    # 1. Build the network
    svc = MemoryGraphService()
    _build_network(svc)
    total_nodes = svc.size()

    # 2. Materialize subgraph from 'alice' (co_authored, depth=2)
    start = materialize_subgraph(svc, "alice", edge_type="co_authored", depth=2)
    start_id = start.node_id
    start_label = start.label
    direct_links = [n.node_id for n in (start.next if isinstance(start.next, list) else [start.next] if start.next else [])]

    # 3. BFS traversal
    bfs_nodes = list(bfs_traversal(start, {GraphNode: 'next'}))

    # 4. DFS traversal
    dfs_nodes = list(dfs_traversal(start, {GraphNode: 'next'}))
    dfs_post = list(dfs_traversal(start, {GraphNode: 'next'}, preorder=False))

    # 5. Materialized nodes are copies
    start.properties["modified"] = True
    original = svc.get_node("alice")
    mat_has_modified = "modified" in start.properties
    orig_has_modified = "modified" in original.properties

    # 6. Materialize with different edge type
    start_affil = materialize_subgraph(svc, "alice", edge_type="affiliated_with", depth=1)
    affil_nodes = list(bfs_traversal(start_affil, {GraphNode: 'next'}))

    # 7. Materialize with deeper depth
    start_deep = materialize_subgraph(svc, "alice", edge_type="co_authored", depth=3)
    deep_nodes = list(bfs_traversal(start_deep, {GraphNode: 'next'}))

    # 8. Materialize all edge types
    start_all = materialize_subgraph(svc, "alice", edge_type=None, depth=1)
    all_nodes = list(bfs_traversal(start_all, {GraphNode: 'next'}))

    svc.close()

    # =================================================================
    # OUTPUT
    # =================================================================

    print("=" * 70)
    print("  Graph Service Tutorial 5: Subgraph Materialization & Traversal")
    print("=" * 70)

    print("\n[1] Build the collaboration network")
    print("-" * 50)
    print(f"    Nodes: {total_nodes}")
    print(f"    Network: alice->bob->diana->frank, alice->carol->eve, diana->eve")

    print("\n[2] Materialize subgraph from 'alice' (co_authored, depth=2)")
    print("-" * 50)
    print(f"    materialize_subgraph follows outgoing edges and creates linked")
    print(f"    GraphNode copies with next/previous references.")
    print(f"    Start node: {start_id} ({start_label})")
    print(f"    Direct links (next): {direct_links}")

    print("\n[3] BFS traversal on materialized graph")
    print("-" * 50)
    print(f"    BFS visits nodes level by level (breadth-first).")
    print(f"    BFS order ({len(bfs_nodes)} nodes):")
    for i, node in enumerate(bfs_nodes):
        print(f"        [{i}] {node.node_id:10s} ({node.label})")

    print("\n[4] DFS traversal on materialized graph")
    print("-" * 50)
    print(f"    DFS goes deep before going wide (depth-first).")
    print(f"    DFS preorder ({len(dfs_nodes)} nodes):")
    for i, node in enumerate(dfs_nodes):
        print(f"        [{i}] {node.node_id:10s} ({node.label})")
    print(f"    DFS postorder ({len(dfs_post)} nodes):")
    for i, node in enumerate(dfs_post):
        print(f"        [{i}] {node.node_id:10s} ({node.label})")

    print("\n[5] Materialized nodes are copies (service data unchanged)")
    print("-" * 50)
    print(f"    Materialized alice has 'modified': {mat_has_modified}")
    print(f"    Service alice has 'modified': {orig_has_modified}")
    print(f"    Copies are independent of the service!")

    print("\n[6] Materialization with edge_type='affiliated_with' (depth=1)")
    print("-" * 50)
    print(f"    BFS from alice (affiliated_with, depth=1):")
    for node in affil_nodes:
        print(f"        {node.node_id:10s} ({node.label})")

    print("\n[7] Materialization with depth=3 (co_authored)")
    print("-" * 50)
    print(f"    BFS from alice (co_authored, depth=3): {len(deep_nodes)} nodes")
    for node in deep_nodes:
        print(f"        {node.node_id:10s} ({node.label})")
    print(f"    Depth=3 reaches frank via alice->bob->diana->frank")

    print("\n[8] Materialization with edge_type=None (all edges, depth=1)")
    print("-" * 50)
    print(f"    BFS from alice (all edges, depth=1): {len(all_nodes)} nodes")
    for node in all_nodes:
        print(f"        {node.node_id:10s} ({node.label})")
    print(f"    Includes both co-authors (bob, carol) and institution (mit)")

    print("\n" + "=" * 70)
    print("Tutorial 5 complete!")
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[X] Error: {e}")
        import traceback
        traceback.print_exc()
