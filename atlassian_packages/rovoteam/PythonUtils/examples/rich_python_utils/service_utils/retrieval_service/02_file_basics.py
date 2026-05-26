"""
Retrieval Service Tutorial 2: File-Based Backend

Demonstrates the FileRetrievalService -- stores documents as JSON files on
disk with text-based search (BM25 if rank-bm25 is installed, otherwise
term-overlap fallback).

Topics covered:
    - Creating the service with a directory path
    - Adding and searching documents
    - Metadata filtering
    - Persistence: close, reopen, data survives
    - Namespace isolation and statistics

Prerequisites:
    No required external dependencies.
    Optional: pip install rank-bm25  (for BM25 scoring; falls back to term overlap)

Usage:
    python 02_file_basics.py
"""

import shutil
import tempfile

from resolve_path import resolve_path
resolve_path()

from python_utils.service_utils.retrieval_service.file_retrieval_service import (
    FileRetrievalService,
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
        content="Lipid nanoparticle delivery system for CRISPR-Cas9 gene editing "
                "with efficient genome editing in liver cells.",
        metadata={"authors": ["Diana Lee"], "year": 2024,
                  "topics": ["gene_editing", "drug_delivery"], "open_access": False},
    ),
    Document(
        doc_id="paper:climate_model",
        content="Improved climate model with ocean-atmosphere coupling at "
                "unprecedented resolution for temperature trend prediction.",
        metadata={"authors": ["Carol Kim", "Eve Zhang"], "year": 2023,
                  "topics": ["climate_science", "machine_learning"], "open_access": True},
    ),
    Document(
        doc_id="paper:protein_structure",
        content="Deep learning methods predict protein tertiary structures with "
                "near-experimental accuracy using transformer architectures.",
        metadata={"authors": ["Bob Patel", "Diana Lee"], "year": 2023,
                  "topics": ["machine_learning", "structural_biology"], "open_access": False},
    ),
]


def main():
    tmpdir = tempfile.mkdtemp(prefix="ret_file_example_")

    try:
        # =============================================================
        # CORE CODE
        # =============================================================

        # 1. Create the service
        svc = FileRetrievalService(base_dir=tmpdir)
        svc_repr = repr(svc)

        # 2. Add papers
        added_ids = []
        for paper in PAPERS:
            svc.add(paper)
            added_ids.append(paper.doc_id)

        # 3. Search
        results_quantum = svc.search("quantum machine learning")
        results_quantum_formatted = [(d.doc_id, s) for d, s in results_quantum]

        results_protein = svc.search("protein deep learning")
        results_protein_formatted = [(d.doc_id, s) for d, s in results_protein]

        # 4. Filters
        results_year = svc.search("novel quantum algorithm prediction", filters={"year": 2024})
        results_oa = svc.search("novel quantum algorithm prediction", filters={"open_access": True})
        docs_2023 = svc.list_all(filters={"year": 2023})

        # 5. Persistence
        svc.close()

        svc2 = FileRetrievalService(base_dir=tmpdir)
        doc_reopened = svc2.get_by_id("paper:quantum_ml")
        doc_reopened_content_preview = doc_reopened.content[:60]
        size_reopened = svc2.size()

        # 6. Namespaces and stats
        svc2.add(Document(doc_id="ns_doc", content="Namespace test"), namespace="archive")
        ns_list = svc2.namespaces()
        stats = svc2.get_stats()

        svc2.close()

        # 7. Context manager
        with FileRetrievalService(base_dir=tmpdir) as ctx_svc:
            ctx_size = ctx_svc.size()

        # =============================================================
        # OUTPUT
        # =============================================================

        print("=" * 70)
        print("Retrieval Service Tutorial 2: File-Based Backend")
        print("=" * 70)
        print(f"\n    (Using temp directory: {tmpdir})")

        print("\n[1] Create the service")
        print("-" * 50)
        print(f"    Service created -> {svc_repr}")

        print("\n[2] Adding scientific papers")
        print("-" * 50)
        for pid in added_ids:
            print(f"    Added '{pid}'")

        print("\n[3] Searching documents")
        print("-" * 50)
        print(f"    'quantum machine learning' -> {len(results_quantum_formatted)} results:")
        for rid, score in results_quantum_formatted:
            print(f"        {rid:35s} score={score:.4f}")
        print(f"    'protein deep learning' -> {len(results_protein_formatted)} results:")
        for rid, score in results_protein_formatted:
            print(f"        {rid:35s} score={score:.4f}")

        print("\n[4] Searching with metadata filters")
        print("-" * 50)
        print(f"    year=2024: {len(results_year)} papers")
        print(f"    open_access=True: {len(results_oa)} papers")
        print(f"    list_all(year=2023): {len(docs_2023)} papers")

        print("\n[5] Persistence: close and reopen")
        print("-" * 50)
        print(f"    Service closed")
        print(f"    Reopened -- get_by_id('paper:quantum_ml') -> found!")
        print(f"    Content -> {doc_reopened_content_preview}...")
        print(f"    size() -> {size_reopened}")

        print("\n[6] Namespaces and stats")
        print("-" * 50)
        print(f"    Added doc in 'archive' namespace")
        print(f"    namespaces() -> {ns_list}")
        print(f"    Stats -> {stats}")

        print("\n[7] Context manager")
        print("-" * 50)
        print(f"    Inside context: size() -> {ctx_size}")
        print(f"    Context manager exited cleanly")

        print("\n" + "=" * 70)
        print("Tutorial 2 complete!")
        print("=" * 70)

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        print(f"\n    (Cleaned up temp directory)")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[X] Error: {e}")
        import traceback
        traceback.print_exc()
