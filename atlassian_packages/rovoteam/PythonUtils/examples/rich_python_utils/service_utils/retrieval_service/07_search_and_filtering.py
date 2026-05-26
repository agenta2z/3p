"""
Retrieval Service Tutorial 7: Search and Filtering Deep-Dive

A comprehensive guide to filter semantics using the MemoryRetrievalService
(no external dependencies). Covers all filter types and edge cases.

Topics covered:
    - Scalar exact match: {"year": 2024}
    - String match: {"journal": "Nature Physics"}
    - Boolean match: {"open_access": True}
    - List AND containment: {"topics": ["machine_learning", "quantum_computing"]}
    - Combined filters: {"year": 2024, "open_access": True}
    - Filters on list_all (browse without search query)
    - Edge cases: filter key not in metadata

Usage:
    python 07_search_and_filtering.py
"""

from resolve_path import resolve_path
resolve_path()

from python_utils.service_utils.retrieval_service.memory_retrieval_service import (
    MemoryRetrievalService,
)
from python_utils.service_utils.retrieval_service.document import Document


PAPERS = [
    Document(
        doc_id="paper:quantum_ml",
        content="Quantum machine learning algorithm for molecular property prediction "
                "using variational quantum circuits.",
        metadata={
            "authors": ["Alice Chen", "Bob Patel"],
            "journal": "Nature Physics",
            "year": 2024,
            "topics": ["quantum_computing", "machine_learning"],
            "citations": 45,
            "open_access": True,
        },
    ),
    Document(
        doc_id="paper:crispr_delivery",
        content="Lipid nanoparticle delivery system for CRISPR-Cas9 gene editing "
                "demonstrates efficient genome editing in liver cells.",
        metadata={
            "authors": ["Diana Lee", "Bob Patel"],
            "journal": "Nature Biotechnology",
            "year": 2024,
            "topics": ["gene_editing", "drug_delivery"],
            "citations": 72,
            "open_access": False,
        },
    ),
    Document(
        doc_id="paper:climate_model",
        content="Improved climate model incorporating ocean-atmosphere coupling at "
                "unprecedented resolution reproduces observed temperature trends.",
        metadata={
            "authors": ["Carol Kim", "Eve Zhang"],
            "journal": "Science",
            "year": 2023,
            "topics": ["climate_science", "machine_learning"],
            "citations": 128,
            "open_access": True,
        },
    ),
    Document(
        doc_id="paper:topological_insulator",
        content="New class of topological insulators exhibiting robust surface states "
                "at room temperature for quantum computing devices.",
        metadata={
            "authors": ["Alice Chen", "Frank Wu"],
            "journal": "Physical Review Letters",
            "year": 2024,
            "topics": ["condensed_matter", "quantum_computing"],
            "citations": 31,
            "open_access": True,
        },
    ),
    Document(
        doc_id="paper:protein_structure",
        content="Deep learning methods predict protein tertiary structures with "
                "near-experimental accuracy using transformer architectures.",
        metadata={
            "authors": ["Bob Patel", "Diana Lee"],
            "journal": "Nature Methods",
            "year": 2023,
            "topics": ["machine_learning", "structural_biology"],
            "citations": 95,
            "open_access": False,
        },
    ),
    Document(
        doc_id="paper:battery_materials",
        content="Computational screening identifies novel solid-state electrolyte "
                "materials for next-generation lithium batteries.",
        metadata={
            "authors": ["Eve Zhang", "Frank Wu"],
            "journal": "Advanced Energy Materials",
            "year": 2024,
            "topics": ["materials_science", "energy_storage"],
            "citations": 18,
            "open_access": True,
        },
    ),
]


def main():
    # =================================================================
    # CORE CODE
    # =================================================================

    # Setup
    svc = MemoryRetrievalService()
    for paper in PAPERS:
        svc.add(paper)
    total_loaded = svc.size()

    # 1. Scalar exact match
    results_year2024 = svc.search("novel quantum algorithm prediction learning materials", filters={"year": 2024})
    results_year2023 = svc.search("novel quantum algorithm prediction learning materials", filters={"year": 2023})

    # 2. String exact match
    results_nature_physics = svc.search("novel quantum algorithm prediction learning materials", filters={"journal": "Nature Physics"})
    results_science = svc.search("novel quantum algorithm prediction learning materials", filters={"journal": "Science"})

    # 3. Boolean match
    results_open_true = svc.search("novel quantum algorithm prediction learning materials", filters={"open_access": True})
    results_open_false = svc.search("novel quantum algorithm prediction learning materials", filters={"open_access": False})

    # 4. List AND containment
    results_ml = svc.search("novel quantum algorithm prediction learning materials", filters={"topics": ["machine_learning"]})
    results_qc = svc.search("novel quantum algorithm prediction learning materials", filters={"topics": ["quantum_computing"]})
    results_both = svc.search("novel quantum algorithm prediction learning materials", filters={"topics": ["quantum_computing", "machine_learning"]})

    # 5. Combined filters
    results_2024_open = svc.search("novel quantum algorithm prediction learning materials", filters={"year": 2024, "open_access": True})
    results_2024_nbt = svc.search("novel quantum algorithm prediction learning materials", filters={"year": 2024, "journal": "Nature Biotechnology"})

    # 6. Filters on list_all
    docs_open = svc.list_all(filters={"open_access": True})
    docs_2024_closed = svc.list_all(filters={"year": 2024, "open_access": False})

    # 7. Edge cases
    results_nonexistent = svc.search("novel quantum algorithm prediction learning materials", filters={"nonexistent_key": "value"})
    results_empty_query = svc.search("")

    # Duplicate add test
    duplicate_error_msg = None
    try:
        svc.add(PAPERS[0])
    except ValueError as e:
        duplicate_error_msg = str(e)

    svc.close()

    # =================================================================
    # OUTPUT
    # =================================================================

    print("=" * 70)
    print("Retrieval Service Tutorial 7: Search & Filtering Deep-Dive")
    print("=" * 70)

    print(f"\nLoaded {total_loaded} papers into MemoryRetrievalService.")

    print("\n[1] Scalar exact match: {\"year\": 2024}")
    print("-" * 50)
    print(f"    year=2024 -> {len(results_year2024)} match(es)")
    for doc, score in results_year2024:
        print(f"        {doc.doc_id:35s} score={score:.4f}")
    print(f"    year=2023 -> {len(results_year2023)} match(es)")
    for doc, score in results_year2023:
        print(f"        {doc.doc_id:35s} score={score:.4f}")

    print("\n[2] String exact match: {\"journal\": \"Nature Physics\"}")
    print("-" * 50)
    print(f"    journal=\"Nature Physics\" -> {len(results_nature_physics)} match(es)")
    for doc, score in results_nature_physics:
        print(f"        {doc.doc_id:35s} score={score:.4f}")
    print(f"    journal=\"Science\" -> {len(results_science)} match(es)")
    for doc, score in results_science:
        print(f"        {doc.doc_id:35s} score={score:.4f}")

    print("\n[3] Boolean match: {\"open_access\": True}")
    print("-" * 50)
    print(f"    open_access=True -> {len(results_open_true)} match(es)")
    for doc, score in results_open_true:
        print(f"        {doc.doc_id:35s} score={score:.4f}")
    print(f"    open_access=False -> {len(results_open_false)} match(es)")
    for doc, score in results_open_false:
        print(f"        {doc.doc_id:35s} score={score:.4f}")

    print("\n[4] List AND containment: all items must be present in the document's list")
    print("-" * 50)
    print('    Rule: {"topics": ["a", "b"]} matches when BOTH "a" AND "b" are in doc.topics')
    print(f"    topics contains \"machine_learning\" -> {len(results_ml)} match(es)")
    for doc, score in results_ml:
        print(f"        {doc.doc_id:35s} score={score:.4f}")
    print(f"    topics contains \"quantum_computing\" -> {len(results_qc)} match(es)")
    for doc, score in results_qc:
        print(f"        {doc.doc_id:35s} score={score:.4f}")
    print(f"    topics contains BOTH \"quantum_computing\" AND \"machine_learning\" -> {len(results_both)} match(es)")
    for doc, score in results_both:
        print(f"        {doc.doc_id:35s} score={score:.4f}")
    print("    (Only paper:quantum_ml has both topics)")

    print("\n[5] Combined filters: all conditions must match (AND logic)")
    print("-" * 50)
    print(f"    year=2024 AND open_access=True -> {len(results_2024_open)} match(es)")
    for doc, score in results_2024_open:
        print(f"        {doc.doc_id:35s} score={score:.4f}")
    print(f"    year=2024 AND journal=\"Nature Biotechnology\" -> {len(results_2024_nbt)} match(es)")
    for doc, score in results_2024_nbt:
        print(f"        {doc.doc_id:35s} score={score:.4f}")

    print("\n[6] Filters on list_all (browse without search query)")
    print("-" * 50)
    print(f"    list_all: open_access=True -> {len(docs_open)} match(es)")
    for doc in docs_open:
        print(f"        {doc.doc_id}")
    print(f"    list_all: year=2024 AND open_access=False -> {len(docs_2024_closed)} match(es)")
    for doc in docs_2024_closed:
        print(f"        {doc.doc_id}")

    print("\n[7] Edge cases")
    print("-" * 50)
    print(f"    filter on key \"nonexistent_key\" (not in any metadata) -> {len(results_nonexistent)} match(es)")
    print("    (No matches -- missing filter key means filter not satisfied)")
    print(f"    empty search query \"\" -> {len(results_empty_query)} match(es)")
    print("    (Returns empty -- empty query matches nothing)")
    if duplicate_error_msg:
        print(f"    Duplicate add -> ValueError: {duplicate_error_msg}")
    else:
        print("    Duplicate add -> should have raised ValueError")

    print("\n" + "=" * 70)
    print("Tutorial 7 complete!")
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[X] Error: {e}")
        import traceback
        traceback.print_exc()
