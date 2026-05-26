"""
Graph Service Tutorial 2: File-Based Backend

Demonstrates the FileGraphService -- stores graph nodes and edges as JSON
files on disk. Data persists across restarts.

Topics covered:
    - Creating the service with a directory path
    - Adding nodes and edges
    - Persistence: close, reopen, graph intact
    - Namespace isolation
    - Removing a node with cascade edge deletion
    - Statistics and context-manager usage

Prerequisites:
    No external dependencies (uses standard library only).

Usage:
    python 02_file_basics.py
"""

import shutil
import tempfile

from resolve_path import resolve_path
resolve_path()

from python_utils.service_utils.graph_service.file_graph_service import (
    FileGraphService,
)
from python_utils.service_utils.graph_service.graph_node import GraphNode, GraphEdge


def _build_network(svc, namespace=None):
    """Populate a small research collaboration network."""
    # Researchers
    for nid, label, props in [
        ("alice", "Dr. Alice Chen", {"institution": "MIT", "h_index": 42}),
        ("bob",   "Dr. Bob Patel",  {"institution": "Stanford", "h_index": 35}),
        ("carol", "Dr. Carol Kim",  {"institution": "MIT", "h_index": 28}),
    ]:
        svc.add_node(GraphNode(node_id=nid, node_type="researcher",
                               label=label, properties=props), namespace=namespace)

    # Institutions
    for nid, label, props in [
        ("mit",     "MIT",      {"location": "Cambridge, MA"}),
        ("stanford", "Stanford", {"location": "Stanford, CA"}),
    ]:
        svc.add_node(GraphNode(node_id=nid, node_type="institution",
                               label=label, properties=props), namespace=namespace)

    # Edges
    edges = [
        ("alice", "bob", "co_authored", {"papers": 3}),
        ("alice", "carol", "co_authored", {"papers": 5}),
        ("bob", "carol", "co_authored", {"papers": 1}),
        ("alice", "mit", "affiliated_with", {}),
        ("carol", "mit", "affiliated_with", {}),
        ("bob", "stanford", "affiliated_with", {}),
    ]
    for src, tgt, etype, props in edges:
        svc.add_edge(GraphEdge(source_id=src, target_id=tgt,
                               edge_type=etype, properties=props), namespace=namespace)


def main():
    tmpdir = tempfile.mkdtemp(prefix="graph_file_example_")

    try:
        # =============================================================
        # CORE CODE
        # =============================================================

        # 1. Create the service
        svc = FileGraphService(base_dir=tmpdir)
        svc_repr = repr(svc)

        # 2. Build the network
        _build_network(svc)
        size_after_build = svc.size()
        alice_out_edges = svc.get_edges("alice", direction="outgoing")

        # 3. Verify retrieval
        alice = svc.get_node("alice")
        alice_label = alice.label
        alice_h_index = alice.properties["h_index"]
        alice_coauthors = svc.get_neighbors("alice", edge_type="co_authored", depth=1)
        alice_coauthor_ids = [n.node_id for n, d in alice_coauthors]

        # 4. Persistence: close and reopen
        svc.close()
        svc2 = FileGraphService(base_dir=tmpdir)
        alice_reopened = svc2.get_node("alice")
        alice_reopened_label = alice_reopened.label
        size_reopened = svc2.size()
        edges_reopened = svc2.get_edges("alice", direction="outgoing")

        # 5. Namespaces
        _build_network(svc2, namespace="quantum_project")
        default_size = svc2.size()
        quantum_size = svc2.size(namespace="quantum_project")
        ns_list = svc2.namespaces()

        # 6. Remove node with cascade
        bob_edges_before = svc2.get_edges("bob", direction="both")
        removed_bob = svc2.remove_node("bob")
        bob_after = svc2.get_node("bob")
        size_after_remove = svc2.size()

        # 7. Stats and context manager
        stats = svc2.get_stats()
        svc2.close()

        with FileGraphService(base_dir=tmpdir) as ctx_svc:
            ctx_size = ctx_svc.size()

        # =============================================================
        # OUTPUT
        # =============================================================

        print("=" * 70)
        print("  Graph Service Tutorial 2: File-Based Backend")
        print("=" * 70)
        print(f"\n    (Using temp directory: {tmpdir})")

        print("\n[1] Create the service")
        print("-" * 50)
        print(f"    Service created: {svc_repr}")

        print("\n[2] Build the network")
        print("-" * 50)
        print(f"    Added {size_after_build} nodes")
        print(f"    Alice has {len(alice_out_edges)} outgoing edges")

        print("\n[3] Verify retrieval")
        print("-" * 50)
        print(f"    get_node('alice') -> {alice_label}, h_index={alice_h_index}")
        print(f"    Alice's co-authors: {alice_coauthor_ids}")

        print("\n[4] Persistence: close and reopen")
        print("-" * 50)
        print(f"    Service closed")
        print(f"    Reopened -- get_node('alice') -> {alice_reopened_label}")
        print(f"    size() -> {size_reopened}")
        print(f"    Alice still has {len(edges_reopened)} outgoing edges -- graph intact!")

        print("\n[5] Namespace isolation")
        print("-" * 50)
        print(f"    Built same network in 'quantum_project' namespace")
        print(f"    Default size: {default_size}")
        print(f"    quantum_project size: {quantum_size}")
        print(f"    namespaces() -> {ns_list}")

        print("\n[6] Remove node with cascade edge deletion")
        print("-" * 50)
        print(f"    Bob has {len(bob_edges_before)} edges before removal")
        print(f"    remove_node('bob') -> {removed_bob}")
        print(f"    get_node('bob') -> {bob_after}")
        print(f"    size() -> {size_after_remove}")

        print("\n[7] Stats and context manager")
        print("-" * 50)
        print(f"    Stats: {stats}")
        print(f"    Context manager: size() -> {ctx_size}")
        print(f"    Context manager exited cleanly")

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        print(f"\n    (Cleaned up temp directory)")

    print("\n" + "=" * 70)
    print("Tutorial 2 complete!")
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[X] Error: {e}")
        import traceback
        traceback.print_exc()
