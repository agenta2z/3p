"""
Retrieval Service Tutorial 5: LanceDB Backend

Demonstrates the LanceDBRetrievalService -- uses LanceDB for hybrid search
that combines vector similarity (cosine distance) with BM25 keyword scoring.

Topics covered:
    - Defining a simple embedding function
    - Creating the service (db_path, embedding_function, hybrid_alpha)
    - Adding documents
    - Hybrid search: vector + BM25 combination
    - Metadata filtering and statistics

Prerequisites:
    pip install lancedb

Usage:
    python 05_lancedb_basics.py
"""

import shutil
import sys
import tempfile

try:
    import lancedb
except ImportError:
    print("This example requires the 'lancedb' package.")
    print("Install it with:  pip install lancedb")
    sys.exit(0)

from resolve_path import resolve_path
resolve_path()

from python_utils.service_utils.retrieval_service.lancedb_retrieval_service import (
    LanceDBRetrievalService,
)
from python_utils.service_utils.retrieval_service.document import Document


# -- Simple hash-based embedding for demonstration --
# In production, use a real model (e.g. sentence-transformers).
# This deterministic function maps text -> 16-dim vector via MD5 hash.

def demo_embedding(text: str) -> list:
    """Hash-based embedding for demo purposes (16 dimensions)."""
    import hashlib
    h = hashlib.sha256(text.encode()).hexdigest()
    return [int(h[i:i+2], 16) / 255.0 for i in range(0, 32, 2)]


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
                "demonstrates efficient genome editing in liver cells.",
        metadata={"authors": ["Diana Lee"], "year": 2024,
                  "topics": ["gene_editing", "drug_delivery"], "open_access": False},
    ),
    Document(
        doc_id="paper:climate_model",
        content="Improved climate model incorporating ocean-atmosphere coupling at "
                "unprecedented resolution for temperature trend prediction.",
        metadata={"authors": ["Carol Kim", "Eve Zhang"], "year": 2023,
                  "topics": ["climate_science", "machine_learning"], "open_access": True},
    ),
    Document(
        doc_id="paper:protein_structure",
        content="Deep learning predicts protein tertiary structures with near-experimental "
                "accuracy using a transformer architecture.",
        metadata={"authors": ["Bob Patel", "Diana Lee"], "year": 2023,
                  "topics": ["machine_learning", "structural_biology"], "open_access": False},
    ),
    Document(
        doc_id="paper:battery_materials",
        content="High-throughput computational screening identifies solid-state electrolyte "
                "materials for next-generation lithium batteries.",
        metadata={"authors": ["Eve Zhang", "Frank Wu"], "year": 2024,
                  "topics": ["materials_science", "energy_storage"], "open_access": True},
    ),
]


def main():
    tmpdir = tempfile.mkdtemp(prefix="ret_lance_example_")

    try:
        # =============================================================
        # CORE CODE
        # =============================================================

        # 1. Demo embedding function
        sample = demo_embedding("hello world")

        # 2. Create the service
        svc = LanceDBRetrievalService(
            db_path=tmpdir,
            embedding_function=demo_embedding,
            table_name="science_papers",
            hybrid_alpha=0.7,  # 70% vector + 30% BM25
        )
        svc_repr = repr(svc)

        # 3. Add papers
        for paper in PAPERS:
            svc.add(paper)
        size_after_add = svc.size()

        # 4. Hybrid search
        results_quantum = svc.search("quantum machine learning algorithm")
        results_crispr = svc.search("gene editing CRISPR delivery")

        # 5. Filters and stats (using the same service)
        results_year2024 = svc.search("novel quantum algorithm prediction", filters={"year": 2024})
        docs_open_access = svc.list_all(filters={"open_access": True})
        stats = svc.get_stats()

        svc.close()

        # =============================================================
        # OUTPUT
        # =============================================================

        print("=" * 70)
        print("Retrieval Service Tutorial 5: LanceDB Backend")
        print("=" * 70)

        print(f"\n   (Using temp directory: {tmpdir})")

        print("\n[1] Demo embedding function")
        print("-" * 50)
        print(f"    demo_embedding('hello world') -> [{sample[0]:.3f}, {sample[1]:.3f}, ...]")
        print(f"    (In production, use sentence-transformers or similar)")

        print("\n[2] Create LanceDBRetrievalService")
        print("-" * 50)
        print(f"    Service created -> {svc_repr}")
        print(f"    hybrid_alpha=0.7 -> blends 70% vector + 30% BM25 scoring")

        print("\n[3] Add papers")
        print("-" * 50)
        for paper in PAPERS:
            print(f"    Added '{paper.doc_id}'")
        print(f"    size() -> {size_after_add}")

        print("\n[4] Hybrid search (vector + BM25)")
        print("-" * 50)
        print(f"    'quantum machine learning algorithm' -> {len(results_quantum)} results:")
        for doc, score in results_quantum:
            print(f"        {doc.doc_id:35s} score={score:.4f}")
        print(f"    'gene editing CRISPR delivery' -> {len(results_crispr)} results:")
        for doc, score in results_crispr:
            print(f"        {doc.doc_id:35s} score={score:.4f}")

        print("\n[5] Filters and stats")
        print("-" * 50)
        print(f"    search with year=2024 -> {len(results_year2024)} results")
        print(f"    list_all(open_access=True) -> {len(docs_open_access)} papers")
        print(f"    Stats -> {stats}")

        print("\n" + "=" * 70)
        print("Tutorial 5 complete!")
        print("=" * 70)

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[X] Error: {e}")
        import traceback
        traceback.print_exc()
