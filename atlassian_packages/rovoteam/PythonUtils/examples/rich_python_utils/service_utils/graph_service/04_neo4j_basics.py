"""
Graph Service Tutorial 4: Neo4j Backend

Demonstrates the Neo4jGraphService -- stores graph data in a Neo4j database
using the Bolt protocol. Provides the same API as all other backends with
Cypher-powered queries under the hood.

Topics covered:
    - Connecting to Neo4j
    - Adding nodes and edges
    - Getting neighbors (Cypher variable-length paths)
    - Namespace isolation and statistics
    - Cleanup

Prerequisites:
    pip install neo4j

    You also need a running Neo4j server:
        docker run -d --name neo4j-test -p 7687:7687 -p 7474:7474 \\
            -e NEO4J_AUTH=neo4j/testpassword neo4j:5-community

Usage:
    python 04_neo4j_basics.py
"""

import sys

try:
    import neo4j
except ImportError:
    print("This example requires the 'neo4j' package.")
    print("Install it with:  pip install neo4j")
    print("\nYou also need a running Neo4j server:")
    print("  docker run -d --name neo4j-test -p 7687:7687 -p 7474:7474 \\")
    print("      -e NEO4J_AUTH=neo4j/testpassword neo4j:5-community")
    sys.exit(0)

from resolve_path import resolve_path
resolve_path()

from python_utils.service_utils.graph_service.neo4j_graph_service import (
    Neo4jGraphService,
)
from python_utils.service_utils.graph_service.graph_node import GraphNode, GraphEdge


def main():
    # =================================================================
    # CORE CODE
    # =================================================================

    # 1. Connect
    svc = Neo4jGraphService(
        uri="bolt://localhost:7687",
        auth=("neo4j", "testpassword"),
        database="neo4j",
    )

    if not svc.ping():
        print("   [!!] Cannot connect to Neo4j. Is the server running?")
        print("   Start it with:")
        print("     docker run -d --name neo4j-test -p 7687:7687 -p 7474:7474 \\")
        print("         -e NEO4J_AUTH=neo4j/testpassword neo4j:5-community")
        svc.close()
        return

    svc_repr = repr(svc)
    svc_ping = svc.ping()

    try:
        # 2. Add researchers
        researcher_data = [
            ("alice", "Dr. Alice Chen", {"institution": "MIT", "h_index": 42}),
            ("bob",   "Dr. Bob Patel",  {"institution": "Stanford", "h_index": 35}),
            ("carol", "Dr. Carol Kim",  {"institution": "MIT", "h_index": 28}),
            ("diana", "Dr. Diana Lee",  {"institution": "Harvard", "h_index": 51}),
        ]
        for nid, label, props in researcher_data:
            svc.add_node(GraphNode(node_id=nid, node_type="researcher",
                                   label=label, properties=props))

        # 3. Add institution nodes
        institution_data = [("mit", "MIT"), ("stanford", "Stanford")]
        for nid, label in institution_data:
            svc.add_node(GraphNode(node_id=nid, node_type="institution",
                                   label=label, properties={}))

        # 4. Add edges
        edge_data = [
            ("alice", "bob", "co_authored", {"papers": 3}),
            ("alice", "carol", "co_authored", {"papers": 5}),
            ("bob", "diana", "co_authored", {"papers": 2}),
            ("alice", "mit", "affiliated_with", {}),
            ("carol", "mit", "affiliated_with", {}),
            ("bob", "stanford", "affiliated_with", {}),
        ]
        for src, tgt, etype, props in edge_data:
            svc.add_edge(GraphEdge(source_id=src, target_id=tgt,
                                   edge_type=etype, properties=props))

        # 5. Neighbors (Cypher variable-length paths)
        n1 = svc.get_neighbors("alice", depth=1)
        n2 = svc.get_neighbors("alice", edge_type="co_authored", depth=2)

        # 6. Namespaces
        svc.add_node(GraphNode(node_id="alice", node_type="researcher",
                               label="Alice (Project X)"), namespace="project_x")
        default_size = svc.size()
        project_x_size = svc.size(namespace="project_x")
        ns_list = svc.namespaces()

        # 7. Stats
        stats = svc.get_stats()

        # 8. Cleanup
        cleanup_results = []
        for ns in svc.namespaces():
            count = svc.clear(namespace=ns)
            cleanup_results.append((ns, count))

    finally:
        svc.close()

    # =================================================================
    # OUTPUT
    # =================================================================

    print("=" * 70)
    print("  Graph Service Tutorial 4: Neo4j Backend")
    print("=" * 70)

    print("\n[1] Connect to Neo4j")
    print("-" * 50)
    print(f"    Service created: {svc_repr}")
    print(f"    Ping: {svc_ping}")

    print("\n[2] Add researcher nodes")
    print("-" * 50)
    for nid, label, props in researcher_data:
        print(f"    Added '{nid}' ({label})")

    print("\n[3] Add institution nodes")
    print("-" * 50)
    for nid, label in institution_data:
        print(f"    Added '{nid}'")

    print("\n[4] Add edges")
    print("-" * 50)
    for src, tgt, etype, props in edge_data:
        print(f"    {src} --{etype}--> {tgt}")

    print("\n[5] Get neighbors (Cypher-powered)")
    print("-" * 50)
    print(f"    Alice's neighbors (depth=1): {len(n1)}")
    for node, depth in n1:
        print(f"        {node.node_id:10s} depth={depth}")
    print(f"    Alice's co_authored network (depth=2): {len(n2)}")
    for node, depth in n2:
        print(f"        {node.node_id:10s} depth={depth}")

    print("\n[6] Namespace isolation")
    print("-" * 50)
    print(f"    Added alice in 'project_x' namespace")
    print(f"    Default size: {default_size}")
    print(f"    project_x size: {project_x_size}")
    print(f"    namespaces() -> {ns_list}")

    print("\n[7] Statistics")
    print("-" * 50)
    print(f"    Stats: {stats}")

    print("\n[8] Cleanup")
    print("-" * 50)
    for ns, count in cleanup_results:
        print(f"    Cleared namespace '{ns}': {count} nodes removed")
    print(f"    Service closed")

    print("\n" + "=" * 70)
    print("Tutorial 4 complete!")
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[X] Error: {e}")
        import traceback
        traceback.print_exc()
