"""
Graph Service Tutorial 3: NetworkX Backend

Demonstrates the NetworkxGraphService -- uses NetworkX MultiDiGraph internally,
giving you the familiar Graph service API backed by a mature graph library.

Topics covered:
    - Creating the service
    - Building a full research collaboration network
    - Standard queries (get_edges, get_neighbors)
    - Namespace isolation
    - Size, statistics, and context-manager usage

Prerequisites:
    pip install networkx
    (NetworkX is commonly already installed as a dependency of many packages.)

Usage:
    python 03_networkx_basics.py
"""

import sys

try:
    import networkx
except ImportError:
    print("This example requires the 'networkx' package.")
    print("Install it with:  pip install networkx")
    sys.exit(0)

from resolve_path import resolve_path
resolve_path()

from python_utils.service_utils.graph_service.networkx_graph_service import (
    NetworkxGraphService,
)
from python_utils.service_utils.graph_service.graph_node import GraphNode, GraphEdge


def main():
    # =================================================================
    # CORE CODE
    # =================================================================

    # 1. Create the service
    svc = NetworkxGraphService()
    svc_repr = repr(svc)
    svc_ping = svc.ping()

    try:
        # 2. Build the full research network
        researcher_data = [
            ("alice", "Dr. Alice Chen", {"institution": "MIT", "department": "Physics", "h_index": 42}),
            ("bob",   "Dr. Bob Patel",  {"institution": "Stanford", "department": "Bioinformatics", "h_index": 35}),
            ("carol", "Dr. Carol Kim",  {"institution": "MIT", "department": "Climate Science", "h_index": 28}),
            ("diana", "Dr. Diana Lee",  {"institution": "Harvard", "department": "Genetics", "h_index": 51}),
            ("eve",   "Dr. Eve Zhang",  {"institution": "Caltech", "department": "Materials", "h_index": 33}),
        ]
        for nid, label, props in researcher_data:
            svc.add_node(GraphNode(node_id=nid, node_type="researcher", label=label, properties=props))

        institution_data = [
            ("mit",      "MIT",                {"location": "Cambridge, MA", "ranking": 1}),
            ("stanford", "Stanford University", {"location": "Stanford, CA", "ranking": 2}),
            ("harvard",  "Harvard University",  {"location": "Cambridge, MA", "ranking": 3}),
            ("caltech",  "Caltech",             {"location": "Pasadena, CA", "ranking": 4}),
        ]
        for nid, label, props in institution_data:
            svc.add_node(GraphNode(node_id=nid, node_type="institution", label=label, properties=props))

        collab_edges = [
            ("alice", "bob",   {"paper_count": 3, "since": 2020}),
            ("alice", "carol", {"paper_count": 5, "since": 2018}),
            ("bob",   "diana", {"paper_count": 2, "since": 2022}),
            ("carol", "eve",   {"paper_count": 1, "since": 2023}),
            ("diana", "eve",   {"paper_count": 4, "since": 2019}),
            ("bob",   "carol", {"paper_count": 1, "since": 2024}),
        ]
        for src, tgt, props in collab_edges:
            svc.add_edge(GraphEdge(source_id=src, target_id=tgt, edge_type="co_authored", properties=props))

        affil_edges = [
            ("alice", "mit"), ("carol", "mit"),
            ("bob", "stanford"),
            ("diana", "harvard"),
            ("eve", "caltech"),
        ]
        for src, tgt in affil_edges:
            svc.add_edge(GraphEdge(source_id=src, target_id=tgt, edge_type="affiliated_with"))

        svc.add_edge(GraphEdge(source_id="bob", target_id="alice", edge_type="mentored_by",
                               properties={"year": 2019}))
        svc.add_edge(GraphEdge(source_id="eve", target_id="diana", edge_type="mentored_by",
                               properties={"year": 2020}))

        total_nodes = svc.size()

        # 3. Standard queries
        alice_out = svc.get_edges("alice", direction="outgoing")
        alice_collab = svc.get_edges("alice", edge_type="co_authored", direction="outgoing")
        neighbors_1 = svc.get_neighbors("alice", depth=1)
        neighbors_1_ids = [n.node_id for n, d in neighbors_1]
        neighbors_2 = svc.get_neighbors("alice", edge_type="co_authored", depth=2)
        researchers_list = svc.list_nodes(node_type="researcher")
        researcher_ids = [n.node_id for n in researchers_list]

        # 4. Namespaces
        svc.add_node(GraphNode(node_id="alice", node_type="researcher",
                               label="Alice (Quantum)", properties={"role": "PI"}),
                     namespace="quantum_project")
        svc.add_node(GraphNode(node_id="bob", node_type="researcher",
                               label="Bob (Quantum)", properties={"role": "postdoc"}),
                     namespace="quantum_project")
        svc.add_edge(GraphEdge(source_id="alice", target_id="bob", edge_type="supervises"),
                     namespace="quantum_project")

        default_size = svc.size()
        quantum_size = svc.size(namespace="quantum_project")
        ns_list = svc.namespaces()

        # 5. Stats
        stats = svc.get_stats()

    finally:
        svc.close()

    # 6. Context manager
    with NetworkxGraphService() as ctx_svc:
        ctx_svc.add_node(GraphNode(node_id="x", node_type="test", label="Test"))
        ctx_size = ctx_svc.size()

    # =================================================================
    # OUTPUT
    # =================================================================

    print("=" * 70)
    print("  Graph Service Tutorial 3: NetworkX Backend")
    print("=" * 70)

    print("\n[1] Create the service")
    print("-" * 50)
    print(f"    Service created: {svc_repr}")
    print(f"    Ping: {svc_ping}")

    print("\n[2] Build the full research network")
    print("-" * 50)
    print(f"    Added {len(researcher_data)} researchers")
    print(f"    Added {len(institution_data)} institutions")
    print(f"    Added {len(collab_edges)} co_authored edges")
    print(f"    Added {len(affil_edges)} affiliated_with edges")
    print(f"    Added 2 mentored_by edges")
    print(f"    Total nodes: {total_nodes}")

    print("\n[3] Standard queries")
    print("-" * 50)
    print(f"    Alice's outgoing edges: {len(alice_out)}")
    for e in alice_out:
        print(f"        {e.source_id} --{e.edge_type}--> {e.target_id}")
    print(f"    Alice's co_authored edges: {len(alice_collab)}")
    print(f"    Alice's neighbors (depth=1): {neighbors_1_ids}")
    print(f"    Alice's co_authored network (depth=2):")
    for node, depth in neighbors_2:
        print(f"        {node.node_id:10s} depth={depth}")
    print(f"    Researchers: {researcher_ids}")

    print("\n[4] Namespace isolation")
    print("-" * 50)
    print(f"    Default namespace size: {default_size}")
    print(f"    quantum_project size: {quantum_size}")
    print(f"    namespaces() -> {ns_list}")

    print("\n[5] Statistics")
    print("-" * 50)
    print(f"    Stats: {stats}")

    print("\n[6] Context manager")
    print("-" * 50)
    print(f"    Service closed")
    print(f"    Context manager: size() -> {ctx_size}")
    print(f"    Context manager exited cleanly")

    print("\n" + "=" * 70)
    print("Tutorial 3 complete!")
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[X] Error: {e}")
        import traceback
        traceback.print_exc()
