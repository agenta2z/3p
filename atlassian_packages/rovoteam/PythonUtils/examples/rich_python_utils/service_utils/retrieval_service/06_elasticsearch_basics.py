"""
Retrieval Service Tutorial 6: Elasticsearch Backend

Demonstrates the ElasticsearchRetrievalService -- uses Elasticsearch for
full-text BM25 search with enterprise-grade scalability.

Topics covered:
    - Connecting to Elasticsearch
    - Adding documents
    - BM25 full-text search
    - Metadata filtering
    - Namespace isolation and statistics
    - Cleanup

Prerequisites:
    pip install elasticsearch

    You also need a running Elasticsearch server:
        docker run -d --name es-test -p 9200:9200 -e "discovery.type=single-node" \\
            -e "xpack.security.enabled=false" elasticsearch:8.12.0

Usage:
    python 06_elasticsearch_basics.py
"""

import sys

try:
    import elasticsearch
except ImportError:
    print("This example requires the 'elasticsearch' package.")
    print("Install it with:  pip install elasticsearch")
    print("\nYou also need a running Elasticsearch server:")
    print('  docker run -d --name es-test -p 9200:9200 -e "discovery.type=single-node" \\')
    print('      -e "xpack.security.enabled=false" elasticsearch:8.12.0')
    sys.exit(0)

from resolve_path import resolve_path
resolve_path()

from python_utils.service_utils.retrieval_service.elasticsearch_retrieval_service import (
    ElasticsearchRetrievalService,
)
from python_utils.service_utils.retrieval_service.document import Document


PAPERS = [
    Document(
        doc_id="paper:quantum_ml",
        content="A novel quantum machine learning algorithm for molecular property "
                "prediction using variational quantum circuits.",
        metadata={"authors": ["Alice Chen", "Bob Patel"], "year": 2024,
                  "topics": ["quantum_computing", "machine_learning"], "open_access": True},
    ),
    Document(
        doc_id="paper:crispr_delivery",
        content="Lipid nanoparticle delivery system for CRISPR-Cas9 gene editing in vivo "
                "demonstrates efficient genome editing in liver cells.",
        metadata={"authors": ["Diana Lee"], "year": 2024,
                  "topics": ["gene_editing", "drug_delivery"], "open_access": False},
    ),
    Document(
        doc_id="paper:climate_model",
        content="Improved climate model with ocean-atmosphere coupling at unprecedented "
                "resolution for temperature trend prediction.",
        metadata={"authors": ["Carol Kim", "Eve Zhang"], "year": 2023,
                  "topics": ["climate_science", "machine_learning"], "open_access": True},
    ),
    Document(
        doc_id="paper:protein_structure",
        content="Deep learning predicts protein tertiary structures with near-experimental "
                "accuracy using transformer architectures.",
        metadata={"authors": ["Bob Patel", "Diana Lee"], "year": 2023,
                  "topics": ["machine_learning", "structural_biology"], "open_access": False},
    ),
]


def main():
    # -- Early connection check (may exit) --
    svc = ElasticsearchRetrievalService(
        hosts=["http://localhost:9200"],
        index_name="science_papers_example",
    )

    if not svc.ping():
        print("Cannot connect to Elasticsearch. Is the server running?")
        print('Start it with: docker run -d --name es-test -p 9200:9200 \\')
        print('    -e "discovery.type=single-node" -e "xpack.security.enabled=false" \\')
        print('    elasticsearch:8.12.0')
        svc.close()
        return

    try:
        # =============================================================
        # CORE CODE
        # =============================================================

        # 1. Connection info
        svc_repr = repr(svc)
        ping_result = svc.ping()

        # 2. Add papers
        for paper in PAPERS:
            svc.add(paper)
        size_after_add = svc.size()

        # 3. BM25 search
        results_quantum = svc.search("quantum machine learning")
        results_crispr = svc.search("gene editing CRISPR")

        # 4. Filters
        results_year2024 = svc.search("novel quantum algorithm prediction", filters={"year": 2024})
        results_open = svc.search("novel quantum algorithm prediction", filters={"open_access": True})
        docs_2023 = svc.list_all(filters={"year": 2023})

        # 5. Namespaces
        svc.add(Document(doc_id="ns_doc", content="Physics data"), namespace="physics")
        svc.add(Document(doc_id="ns_doc", content="Biology data"), namespace="biology")

        ns_physics = svc.get_by_id("ns_doc", namespace="physics")
        ns_biology = svc.get_by_id("ns_doc", namespace="biology")
        all_namespaces = svc.namespaces()

        # 6. Stats
        stats = svc.get_stats()

        # 7. Cleanup (collect info before clearing)
        cleanup_results = []
        for ns in svc.namespaces():
            count = svc.clear(namespace=ns)
            cleanup_results.append((ns, count))

        # =============================================================
        # OUTPUT
        # =============================================================

        print("=" * 70)
        print("Retrieval Service Tutorial 6: Elasticsearch Backend")
        print("=" * 70)

        print("\n[1] Connect to Elasticsearch")
        print("-" * 50)
        print(f"    Service created -> {svc_repr}")
        print(f"    Ping -> {ping_result}")

        print("\n[2] Add papers")
        print("-" * 50)
        for paper in PAPERS:
            print(f"    Added '{paper.doc_id}'")
        print(f"    size() -> {size_after_add}")

        print("\n[3] BM25 full-text search")
        print("-" * 50)
        print(f"    'quantum machine learning' -> {len(results_quantum)} results:")
        for doc, score in results_quantum:
            print(f"        {doc.doc_id:35s} score={score:.4f}")
        print(f"    'gene editing CRISPR' -> {len(results_crispr)} results:")
        for doc, score in results_crispr:
            print(f"        {doc.doc_id:35s} score={score:.4f}")

        print("\n[4] Metadata filters")
        print("-" * 50)
        print(f"    year=2024 -> {len(results_year2024)} papers")
        print(f"    open_access=True -> {len(results_open)} papers")
        print(f"    list_all(year=2023) -> {len(docs_2023)} papers")

        print("\n[5] Namespace isolation")
        print("-" * 50)
        print(f"    physics -> '{ns_physics.content}'")
        print(f"    biology -> '{ns_biology.content}'")
        print(f"    namespaces() -> {all_namespaces}")

        print("\n[6] Statistics")
        print("-" * 50)
        print(f"    Stats -> {stats}")

        print("\n[7] Cleanup")
        print("-" * 50)
        for ns, count in cleanup_results:
            print(f"    Cleared namespace '{ns}' -> {count} documents removed")

        print("\n" + "=" * 70)
        print("Tutorial 6 complete!")
        print("=" * 70)

    finally:
        svc.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[X] Error: {e}")
        import traceback
        traceback.print_exc()
