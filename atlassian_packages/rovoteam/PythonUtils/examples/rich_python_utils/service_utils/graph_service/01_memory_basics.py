"""
Graph Service Tutorial 1: In-Memory Backend

Demonstrates all core operations of the Graph service using the
MemoryGraphService -- no external dependencies, no files on disk.

Topics covered:
    - Creating the service
    - Adding nodes (researchers, institutions)
    - Getting nodes by ID
    - Adding edges (co_authored, affiliated_with)
    - Error handling for edges to nonexistent nodes
    - Getting edges: outgoing, incoming, both, with edge_type filter
    - Getting neighbors: depth=1, depth=2, with edge_type filter
    - Listing nodes: all, by node_type
    - Namespace isolation
    - Removing edges and nodes (cascade deletes)
    - Size, statistics, and context-manager usage

Usage:
    python 01_memory_basics.py
"""

from resolve_path import resolve_path
resolve_path()

from python_utils.service_utils.graph_service.memory_graph_service import (
    MemoryGraphService,
)
from python_utils.service_utils.graph_service.graph_node import GraphNode, GraphEdge


def main():
    # =================================================================
    # CORE CODE
    # =================================================================

    # 1. Create the service
    svc = MemoryGraphService()
    svc_repr = repr(svc)
    svc_ping = svc.ping()

    # 2. Add researcher nodes
    researchers = [
        GraphNode(node_id="alice", node_type="researcher", label="Dr. Alice Chen",
                  properties={"institution": "MIT", "department": "Physics", "h_index": 42}),
        GraphNode(node_id="bob", node_type="researcher", label="Dr. Bob Patel",
                  properties={"institution": "Stanford", "department": "Bioinformatics", "h_index": 35}),
        GraphNode(node_id="carol", node_type="researcher", label="Dr. Carol Kim",
                  properties={"institution": "MIT", "department": "Climate Science", "h_index": 28}),
        GraphNode(node_id="diana", node_type="researcher", label="Dr. Diana Lee",
                  properties={"institution": "Harvard", "department": "Genetics", "h_index": 51}),
        GraphNode(node_id="eve", node_type="researcher", label="Dr. Eve Zhang",
                  properties={"institution": "Caltech", "department": "Materials", "h_index": 33}),
    ]
    for node in researchers:
        svc.add_node(node)

    # 3. Get node by ID
    alice = svc.get_node("alice")
    alice_label = alice.label
    alice_h_index = alice.properties["h_index"]
    missing = svc.get_node("nobody")

    # 4. Add institution nodes
    institutions = [
        GraphNode(node_id="mit", node_type="institution", label="MIT",
                  properties={"location": "Cambridge, MA", "ranking": 1}),
        GraphNode(node_id="stanford", node_type="institution", label="Stanford University",
                  properties={"location": "Stanford, CA", "ranking": 2}),
        GraphNode(node_id="harvard", node_type="institution", label="Harvard University",
                  properties={"location": "Cambridge, MA", "ranking": 3}),
    ]
    for node in institutions:
        svc.add_node(node)

    # 5. Add collaboration edges
    collaborations = [
        GraphEdge(source_id="alice", target_id="bob", edge_type="co_authored",
                  properties={"paper_count": 3, "since": 2020}),
        GraphEdge(source_id="alice", target_id="carol", edge_type="co_authored",
                  properties={"paper_count": 5, "since": 2018}),
        GraphEdge(source_id="bob", target_id="diana", edge_type="co_authored",
                  properties={"paper_count": 2, "since": 2022}),
        GraphEdge(source_id="carol", target_id="eve", edge_type="co_authored",
                  properties={"paper_count": 1, "since": 2023}),
        GraphEdge(source_id="diana", target_id="eve", edge_type="co_authored",
                  properties={"paper_count": 4, "since": 2019}),
    ]
    for edge in collaborations:
        svc.add_edge(edge)

    # 6. Error handling: edge to nonexistent node
    error_msg = None
    try:
        svc.add_edge(GraphEdge(source_id="alice", target_id="frank", edge_type="co_authored"))
    except ValueError as e:
        error_msg = str(e)

    # 7. Add affiliation edges
    affiliations = [
        ("alice", "mit"), ("carol", "mit"),
        ("bob", "stanford"),
        ("diana", "harvard"),
    ]
    for src, tgt in affiliations:
        svc.add_edge(GraphEdge(source_id=src, target_id=tgt, edge_type="affiliated_with"))

    # 8. Get edges
    out_edges = svc.get_edges("alice", direction="outgoing")
    in_edges = svc.get_edges("bob", direction="incoming")
    both_edges = svc.get_edges("alice", direction="both")
    collab_only = svc.get_edges("alice", edge_type="co_authored", direction="outgoing")

    # 9. Get neighbors
    neighbors_1 = svc.get_neighbors("alice", depth=1)
    neighbors_2 = svc.get_neighbors("alice", depth=2)
    collab_neighbors = svc.get_neighbors("alice", edge_type="co_authored", depth=2)

    # 10. List nodes
    all_nodes = svc.list_nodes()
    just_researchers = svc.list_nodes(node_type="researcher")
    just_institutions = svc.list_nodes(node_type="institution")

    # 11. Namespaces
    svc.add_node(GraphNode(node_id="alice", node_type="researcher", label="Alice (Quantum Project)",
                           properties={"project": "quantum"}), namespace="project_quantum")
    svc.add_node(GraphNode(node_id="alice", node_type="researcher", label="Alice (Climate Project)",
                           properties={"project": "climate"}), namespace="project_climate")

    q = svc.get_node("alice", namespace="project_quantum")
    c = svc.get_node("alice", namespace="project_climate")
    ns_list = svc.namespaces()

    # 12. Remove edge
    removed_edge = svc.remove_edge("alice", "bob", "co_authored")
    remaining = svc.get_edges("alice", edge_type="co_authored", direction="outgoing")

    # 13. Remove node (cascade)
    eve_edges_before = svc.get_edges("eve", direction="both")
    removed_node = svc.remove_node("eve")
    eve_after = svc.get_node("eve")

    # 14. Size and stats
    size_default = svc.size()
    stats = svc.get_stats()

    # 15. Context manager
    with MemoryGraphService() as tmp_svc:
        tmp_svc.add_node(GraphNode(node_id="n1", node_type="test", label="Test"))
        ctx_size = tmp_svc.size()

    svc.close()
    closed_ping = svc.ping()

    # =================================================================
    # OUTPUT
    # =================================================================

    print("=" * 70)
    print("  Graph Service Tutorial 1: In-Memory Backend")
    print("=" * 70)

    print("\n[1] Create the service")
    print("-" * 50)
    print(f"    Service created: {svc_repr}")
    print(f"    Ping: {svc_ping}")

    print("\n[2] Add researcher nodes")
    print("-" * 50)
    for node in researchers:
        print(f"    Added '{node.node_id}' ({node.label})")

    print("\n[3] Get node by ID")
    print("-" * 50)
    print(f"    get_node('alice') -> {alice_label}, h_index={alice_h_index}")
    print(f"    get_node('nobody') -> {missing}")

    print("\n[4] Add institution nodes")
    print("-" * 50)
    for node in institutions:
        print(f"    Added '{node.node_id}' ({node.label})")

    print("\n[5] Add collaboration edges (co_authored)")
    print("-" * 50)
    for edge in collaborations:
        print(f"    {edge.source_id} --co_authored--> {edge.target_id} "
              f"({edge.properties['paper_count']} papers)")

    print("\n[6] Error handling: edge to nonexistent node")
    print("-" * 50)
    if error_msg:
        print(f"    Caught ValueError: {error_msg}")
    else:
        print(f"    [!!] Should have raised ValueError")

    print("\n[7] Add affiliation edges")
    print("-" * 50)
    for src, tgt in affiliations:
        print(f"    {src} --affiliated_with--> {tgt}")

    print("\n[8] Get edges")
    print("-" * 50)
    print(f"    Alice's outgoing edges: {len(out_edges)}")
    for e in out_edges:
        print(f"        {e.source_id} --{e.edge_type}--> {e.target_id}")
    print(f"    Bob's incoming edges: {len(in_edges)}")
    for e in in_edges:
        print(f"        {e.source_id} --{e.edge_type}--> {e.target_id}")
    print(f"    Alice's edges (both): {len(both_edges)}")
    print(f"    Alice's co_authored edges only: {len(collab_only)}")

    print("\n[9] Get neighbors")
    print("-" * 50)
    print(f"    Alice's neighbors (depth=1): {len(neighbors_1)}")
    for node, depth in neighbors_1:
        print(f"        {node.node_id:10s} (depth={depth})")
    print(f"    Alice's neighbors (depth=2): {len(neighbors_2)}")
    for node, depth in neighbors_2:
        print(f"        {node.node_id:10s} (depth={depth})")
    print(f"    Alice's co_authored neighbors (depth=2): {len(collab_neighbors)}")
    for node, depth in collab_neighbors:
        print(f"        {node.node_id:10s} (depth={depth})")

    print("\n[10] List nodes")
    print("-" * 50)
    print(f"    All nodes: {len(all_nodes)}")
    print(f"    Researchers: {len(just_researchers)}")
    for n in just_researchers:
        print(f"        {n.node_id:10s} {n.label}")
    print(f"    Institutions: {len(just_institutions)}")

    print("\n[11] Namespace isolation")
    print("-" * 50)
    print(f"    project_quantum -> '{q.label}'")
    print(f"    project_climate -> '{c.label}'")
    print(f"    Same node_id, different namespaces!")
    print(f"    namespaces() -> {ns_list}")

    print("\n[12] Remove an edge")
    print("-" * 50)
    print(f"    remove_edge(alice->bob, co_authored) -> {removed_edge}")
    print(f"    Alice's remaining co_authored edges: {len(remaining)}")

    print("\n[13] Remove a node (cascade deletes connected edges)")
    print("-" * 50)
    print(f"    Eve's edges before removal: {len(eve_edges_before)}")
    print(f"    remove_node('eve') -> {removed_node}")
    print(f"    get_node('eve') -> {eve_after}")

    print("\n[14] Size and statistics")
    print("-" * 50)
    print(f"    size() (default namespace) -> {size_default}")
    print(f"    Stats: {stats}")

    print("\n[15] Context manager usage")
    print("-" * 50)
    print(f"    Inside context: size() -> {ctx_size}")
    print(f"    Context manager exited cleanly")
    print(f"    Service closed. Ping: {closed_ping}")

    print("\n" + "=" * 70)
    print("Tutorial 1 complete!")
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[X] Error: {e}")
        import traceback
        traceback.print_exc()
