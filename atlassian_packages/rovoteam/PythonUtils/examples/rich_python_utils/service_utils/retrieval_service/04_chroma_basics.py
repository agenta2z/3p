"""
Retrieval Service Tutorial 4: ChromaDB Backend

Demonstrates the ChromaRetrievalService -- uses ChromaDB for vector similarity
search. ChromaDB embeds documents using a sentence-transformer model and
searches by semantic similarity rather than keyword matching.

Topics covered:
    - Creating an in-memory Chroma collection
    - Adding documents
    - Vector similarity search (semantic, not keyword-based)
    - Comparing semantic vs keyword results
    - Metadata filtering
    - Namespace isolation
    - Statistics and context-manager usage

Prerequisites:
    pip install chromadb

    Note: On first run, ChromaDB downloads a small embedding model
    (~80 MB for all-MiniLM-L6-v2).

Usage:
    python 04_chroma_basics.py
"""

import sys

try:
    import chromadb
except ImportError:
    print("This example requires the 'chromadb' package.")
    print("Install it with:  pip install chromadb")
    sys.exit(0)

from resolve_path import resolve_path
resolve_path()

from python_utils.service_utils.retrieval_service.chroma_retrieval_service import (
    ChromaRetrievalService,
)
from python_utils.service_utils.retrieval_service.document import Document


PAPERS = [
    Document(
        doc_id="paper:quantum_ml",
        content="A novel quantum machine learning algorithm for molecular property "
                "prediction using variational quantum circuits achieves state-of-the-art "
                "accuracy on benchmark datasets.",
        metadata={"authors": ["Alice Chen", "Bob Patel"], "year": 2024,
                  "topics": ["quantum_computing", "machine_learning"], "open_access": True},
    ),
    Document(
        doc_id="paper:crispr_delivery",
        content="Lipid nanoparticle delivery system for CRISPR-Cas9 gene editing in vivo "
                "demonstrates efficient genome editing in liver cells with minimal "
                "off-target effects.",
        metadata={"authors": ["Diana Lee"], "year": 2024,
                  "topics": ["gene_editing", "drug_delivery"], "open_access": False},
    ),
    Document(
        doc_id="paper:climate_model",
        content="Improved climate model incorporating ocean-atmosphere coupling at "
                "unprecedented resolution accurately reproduces observed temperature "
                "trends and predicts regional precipitation.",
        metadata={"authors": ["Carol Kim", "Eve Zhang"], "year": 2023,
                  "topics": ["climate_science", "machine_learning"], "open_access": True},
    ),
    Document(
        doc_id="paper:protein_structure",
        content="Deep learning predicts protein tertiary structures with near-experimental "
                "accuracy using a transformer architecture that processes amino acid "
                "sequences end-to-end.",
        metadata={"authors": ["Bob Patel", "Diana Lee"], "year": 2023,
                  "topics": ["machine_learning", "structural_biology"], "open_access": False},
    ),
    Document(
        doc_id="paper:battery_materials",
        content="High-throughput computational screening identifies novel solid-state "
                "electrolyte materials for lithium batteries with ionic conductivity "
                "exceeding commercial electrolytes.",
        metadata={"authors": ["Eve Zhang", "Frank Wu"], "year": 2024,
                  "topics": ["materials_science", "energy_storage"], "open_access": True},
    ),
]


def main():
    # =================================================================
    # CORE CODE
    # =================================================================

    # 1. Create the service
    svc = ChromaRetrievalService(collection_name="science_papers")
    svc_repr = repr(svc)
    svc_ping = svc.ping()

    try:
        # 2. Add papers
        added_ids = []
        for paper in PAPERS:
            svc.add(paper)
            added_ids.append(paper.doc_id)
        size_after_add = svc.size()

        # 3. Vector similarity search
        results_ai_drug = svc.search("artificial intelligence for drug discovery")
        results_ai_drug_formatted = [(d.doc_id, s) for d, s in results_ai_drug]

        results_energy = svc.search("renewable energy and battery technology")
        results_energy_formatted = [(d.doc_id, s) for d, s in results_energy]

        # 4. Semantic vs keyword comparison
        results_warming = svc.search("global warming weather prediction")
        top_warming_doc_id = None
        top_warming_score = None
        if results_warming:
            top_warming_doc_id = results_warming[0][0].doc_id
            top_warming_score = results_warming[0][1]

        # 5. Filters
        results_year = svc.search("research", filters={"year": 2024})
        results_oa = svc.search("research", filters={"open_access": True})
        docs_2023 = svc.list_all(filters={"year": 2023})

        # 6. Namespaces
        svc.add(Document(doc_id="ns_doc", content="Physics experiment data"),
                namespace="physics")
        svc.add(Document(doc_id="ns_doc", content="Biology experiment data"),
                namespace="biology")

        p = svc.get_by_id("ns_doc", namespace="physics")
        b = svc.get_by_id("ns_doc", namespace="biology")
        p_content = p.content
        b_content = b.content
        ns_list = svc.namespaces()

        # 7. Stats
        stats = svc.get_stats()

    finally:
        svc.close()

    # 8. Context manager
    with ChromaRetrievalService(collection_name="ctx_test") as ctx_svc:
        ctx_svc.add(Document(doc_id="tmp", content="context manager test"))
        ctx_size = ctx_svc.size()

    # =================================================================
    # OUTPUT
    # =================================================================

    print("=" * 70)
    print("Retrieval Service Tutorial 4: ChromaDB Backend")
    print("=" * 70)

    print("\n    Note: ChromaDB uses vector embeddings for semantic search.")
    print("    First run may download ~80 MB embedding model.")

    print("\n[1] Create the service (in-memory)")
    print("-" * 50)
    print(f"    Service created -> {svc_repr}")
    print(f"    Ping -> {svc_ping}")

    print("\n[2] Adding scientific papers")
    print("-" * 50)
    for pid in added_ids:
        print(f"    Added '{pid}'")
    print(f"    size() -> {size_after_add}")

    print("\n[3] Vector similarity search (semantic matching)")
    print("-" * 50)
    print(f"    'AI for drug discovery' -> {len(results_ai_drug_formatted)} results:")
    for rid, score in results_ai_drug_formatted:
        print(f"        {rid:35s} score={score:.4f}")
    print(f"    'renewable energy and battery technology' -> {len(results_energy_formatted)} results:")
    for rid, score in results_energy_formatted:
        print(f"        {rid:35s} score={score:.4f}")

    print("\n[4] Semantic search finds meaning, not just keywords")
    print("-" * 50)
    print(f"    'global warming weather prediction' -> top result:")
    if top_warming_doc_id:
        print(f"        {top_warming_doc_id} (score={top_warming_score:.4f})")
        print(f"        (Semantic match -- no keyword overlap needed!)")

    print("\n[5] Metadata filters")
    print("-" * 50)
    print(f"    year=2024: {len(results_year)} papers")
    print(f"    open_access=True: {len(results_oa)} papers")
    print(f"    list_all(year=2023): {len(docs_2023)} papers")

    print("\n[6] Namespace isolation")
    print("-" * 50)
    print(f"    physics -> '{p_content}'")
    print(f"    biology -> '{b_content}'")
    print(f"    namespaces() -> {ns_list}")

    print("\n[7] Stats")
    print("-" * 50)
    print(f"    Stats -> {stats}")

    print("\n[8] Context manager usage")
    print("-" * 50)
    print(f"    Inside context: size() -> {ctx_size}")
    print(f"    Context manager exited cleanly")

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
