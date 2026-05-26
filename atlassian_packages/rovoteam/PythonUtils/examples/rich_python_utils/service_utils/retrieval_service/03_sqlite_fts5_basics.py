"""
Retrieval Service Tutorial 3: SQLite FTS5 Backend

Demonstrates the SQLiteFTS5RetrievalService -- uses SQLite's built-in
Full-Text Search 5 (FTS5) extension for BM25-ranked keyword search.

Topics covered:
    - Creating the service with a database path
    - Adding documents
    - FTS5 search with BM25 scoring
    - FTS5 phrase search
    - Metadata filters (applied post-query)
    - Persistence: close, reopen, data survives
    - In-memory mode
    - Statistics and context-manager usage

Prerequisites:
    No external dependencies (sqlite3 with FTS5 is in the standard library).

Usage:
    python 03_sqlite_fts5_basics.py
"""

import os
import shutil
import tempfile

from resolve_path import resolve_path
resolve_path()

from python_utils.service_utils.retrieval_service.sqlite_fts5_retrieval_service import (
    SQLiteFTS5RetrievalService,
)
from python_utils.service_utils.retrieval_service.document import Document


PAPERS = [
    Document(
        doc_id="paper:quantum_ml",
        content="We present a novel quantum machine learning algorithm for molecular "
                "property prediction. By leveraging variational quantum circuits, our "
                "approach achieves state-of-the-art accuracy on benchmark datasets.",
        metadata={"authors": ["Alice Chen", "Bob Patel"], "year": 2024,
                  "topics": ["quantum_computing", "machine_learning"], "open_access": True},
    ),
    Document(
        doc_id="paper:crispr_delivery",
        content="This study develops a lipid nanoparticle delivery system for CRISPR-Cas9 "
                "gene editing in vivo. We demonstrate efficient genome editing in liver "
                "cells with minimal off-target effects.",
        metadata={"authors": ["Diana Lee"], "year": 2024,
                  "topics": ["gene_editing", "drug_delivery"], "open_access": False},
    ),
    Document(
        doc_id="paper:climate_model",
        content="We introduce an improved climate model incorporating ocean-atmosphere "
                "coupling at unprecedented resolution. The model accurately reproduces "
                "observed temperature trends and predicts regional precipitation changes.",
        metadata={"authors": ["Carol Kim", "Eve Zhang"], "year": 2023,
                  "topics": ["climate_science", "machine_learning"], "open_access": True},
    ),
    Document(
        doc_id="paper:protein_structure",
        content="Using deep learning methods we predict protein tertiary structures with "
                "near-experimental accuracy. Our transformer-based architecture processes "
                "amino acid sequences end-to-end without multiple sequence alignments.",
        metadata={"authors": ["Bob Patel", "Diana Lee"], "year": 2023,
                  "topics": ["machine_learning", "structural_biology"], "open_access": False},
    ),
    Document(
        doc_id="paper:battery_materials",
        content="High-throughput computational screening identifies novel solid-state "
                "electrolyte materials for next-generation lithium batteries. Candidates "
                "show ionic conductivity exceeding current commercial electrolytes.",
        metadata={"authors": ["Eve Zhang", "Frank Wu"], "year": 2024,
                  "topics": ["materials_science", "energy_storage"], "open_access": True},
    ),
]


def main():
    tmpdir = tempfile.mkdtemp(prefix="ret_sqlite_example_")
    db_path = os.path.join(tmpdir, "papers.db")

    try:
        # =============================================================
        # CORE CODE
        # =============================================================

        # 1. Create the service
        svc = SQLiteFTS5RetrievalService(db_path=db_path)
        svc_repr = repr(svc)
        svc_ping = svc.ping()

        # 2. Add papers
        added_ids = []
        for paper in PAPERS:
            svc.add(paper)
            added_ids.append(paper.doc_id)
        size_after_add = svc.size()

        # 3. FTS5 search with BM25 scoring
        results_quantum = svc.search("quantum machine learning")
        results_quantum_formatted = [(d.doc_id, s) for d, s in results_quantum]

        results_protein = svc.search("protein structure prediction")
        results_protein_formatted = [(d.doc_id, s) for d, s in results_protein]

        # 4. FTS5 phrase search
        results_gene_editing = svc.search('"gene editing"')
        results_gene_editing_formatted = [(d.doc_id, s) for d, s in results_gene_editing]

        results_climate_model = svc.search('"climate model"')
        results_climate_model_formatted = [(d.doc_id, s) for d, s in results_climate_model]

        # 5. Metadata filters
        results_year = svc.search("novel quantum algorithm prediction", filters={"year": 2024})
        results_oa = svc.search("novel quantum algorithm prediction", filters={"open_access": True})
        docs_2023 = svc.list_all(filters={"year": 2023})
        docs_2023_ids = [d.doc_id for d in docs_2023]

        # 6. Persistence
        svc.close()

        svc2 = SQLiteFTS5RetrievalService(db_path=db_path)
        doc_reopened = svc2.get_by_id("paper:crispr_delivery")
        doc_reopened_id = doc_reopened.doc_id
        size_reopened = svc2.size()
        svc2.close()

        # 7. In-memory mode
        with SQLiteFTS5RetrievalService(db_path=":memory:") as mem_svc:
            mem_svc.add(Document(doc_id="tmp", content="temporary FTS5 document for testing"))
            mem_results = mem_svc.search("temporary")
            mem_size = mem_svc.size()

        # 8. Stats and context manager
        with SQLiteFTS5RetrievalService(db_path=db_path) as ctx_svc:
            ctx_stats = ctx_svc.get_stats()

        # =============================================================
        # OUTPUT
        # =============================================================

        print("=" * 70)
        print("Retrieval Service Tutorial 3: SQLite FTS5 Backend")
        print("=" * 70)
        print(f"\n    (Using database: {db_path})")

        print("\n[1] Create the service")
        print("-" * 50)
        print(f"    Service created -> {svc_repr}")
        print(f"    Ping -> {svc_ping}")

        print("\n[2] Adding scientific papers")
        print("-" * 50)
        for pid in added_ids:
            print(f"    Added '{pid}'")
        print(f"    size() -> {size_after_add}")

        print("\n[3] FTS5 search with BM25 scoring")
        print("-" * 50)
        print(f"    'quantum machine learning' -> {len(results_quantum_formatted)} results:")
        for rid, score in results_quantum_formatted:
            print(f"        {rid:35s} score={score:.4f}")
        print(f"    'protein structure prediction' -> {len(results_protein_formatted)} results:")
        for rid, score in results_protein_formatted:
            print(f"        {rid:35s} score={score:.4f}")

        print("\n[4] FTS5 phrase search (exact phrases)")
        print("-" * 50)
        print(f"    '\"gene editing\"' -> {len(results_gene_editing_formatted)} results:")
        for rid, score in results_gene_editing_formatted:
            print(f"        {rid:35s} score={score:.4f}")
        print(f"    '\"climate model\"' -> {len(results_climate_model_formatted)} results:")
        for rid, score in results_climate_model_formatted:
            print(f"        {rid:35s} score={score:.4f}")

        print("\n[5] Metadata filters (applied post-query)")
        print("-" * 50)
        print(f"    year=2024: {len(results_year)} papers")
        print(f"    open_access=True: {len(results_oa)} papers")
        print(f"    list_all(year=2023): {len(docs_2023)} papers")
        for did in docs_2023_ids:
            print(f"        {did}")

        print("\n[6] Persistence: close and reopen")
        print("-" * 50)
        print(f"    Service closed")
        print(f"    Reopened -- found '{doc_reopened_id}'")
        print(f"    size() -> {size_reopened}")

        print("\n[7] In-memory mode (db_path=':memory:')")
        print("-" * 50)
        print(f"    In-memory search: {len(mem_results)} result(s)")
        print(f"    size() -> {mem_size}")
        print(f"    In-memory data gone after close")

        print("\n[8] Stats and context manager")
        print("-" * 50)
        print(f"    Stats -> {ctx_stats}")
        print(f"    Context manager exited cleanly")

        print("\n" + "=" * 70)
        print("Tutorial 3 complete!")
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
