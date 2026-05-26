"""
Retrieval Service Tutorial 1: In-Memory Backend

Demonstrates all core operations of the Retrieval service using the
MemoryRetrievalService -- no external dependencies, no files on disk.

Topics covered:
    - Creating the service
    - Adding Document objects
    - Retrieving by ID (get_by_id)
    - Keyword search with relevance scores
    - Metadata filtering (scalar, boolean, list, combined)
    - Updating and removing documents
    - Listing all documents with filters
    - Namespace isolation
    - Statistics, clearing, and context-manager usage

Usage:
    python 01_memory_basics.py
"""

from resolve_path import resolve_path
resolve_path()

from python_utils.service_utils.retrieval_service.memory_retrieval_service import (
    MemoryRetrievalService,
)
from python_utils.service_utils.retrieval_service.document import Document


# -- Mock data: scientific paper abstracts --

PAPERS = [
    Document(
        doc_id="paper:quantum_ml_2024",
        content="We present a novel quantum machine learning algorithm for molecular "
                "property prediction. By leveraging variational quantum circuits, our "
                "approach achieves state-of-the-art accuracy on benchmark datasets.",
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
        doc_id="paper:crispr_delivery_2024",
        content="This study develops a lipid nanoparticle delivery system for CRISPR-Cas9 "
                "gene editing in vivo. We demonstrate efficient genome editing in liver "
                "cells with minimal off-target effects.",
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
        doc_id="paper:climate_model_2023",
        content="We introduce an improved climate model incorporating ocean-atmosphere "
                "coupling at unprecedented resolution. The model accurately reproduces "
                "observed temperature trends and predicts regional precipitation changes.",
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
        doc_id="paper:topological_insulator_2024",
        content="Discovery of a new class of topological insulators exhibiting robust "
                "surface states at room temperature. Our findings open pathways for "
                "low-power quantum computing devices.",
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
        doc_id="paper:protein_structure_2023",
        content="Using deep learning methods we predict protein tertiary structures with "
                "near-experimental accuracy. Our transformer-based architecture processes "
                "amino acid sequences end-to-end without multiple sequence alignments.",
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
        doc_id="paper:battery_materials_2024",
        content="High-throughput computational screening identifies novel solid-state "
                "electrolyte materials for next-generation lithium batteries. Candidates "
                "show ionic conductivity exceeding current commercial electrolytes.",
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

    # 1. Create the service
    svc = MemoryRetrievalService()
    svc_repr = repr(svc)
    svc_ping = svc.ping()

    # 2. Add papers
    added_papers = []
    for paper in PAPERS:
        svc.add(paper)
        added_papers.append((paper.doc_id, paper.metadata["journal"]))

    # 3. Retrieve by ID
    doc = svc.get_by_id("paper:quantum_ml_2024")
    doc_id = doc.doc_id
    doc_content_preview = doc.content[:80]
    doc_authors = doc.metadata["authors"]

    missing = svc.get_by_id("paper:nonexistent")

    # 4. Search by keyword
    results_quantum = svc.search("quantum computing machine learning")
    results_quantum_formatted = [(d.doc_id, s) for d, s in results_quantum]

    results_protein = svc.search("protein structure deep learning")
    results_protein_formatted = [(d.doc_id, s) for d, s in results_protein]

    # 5. Metadata filters
    results_year = svc.search("novel algorithm quantum materials", filters={"year": 2024})
    results_year_ids = [d.doc_id for d, _ in results_year]

    results_oa = svc.search("novel algorithm quantum materials", filters={"open_access": True})

    results_topics = svc.search("novel algorithm quantum materials", filters={"topics": ["quantum_computing", "machine_learning"]})
    results_topics_detail = [(d.doc_id, d.metadata["topics"]) for d, _ in results_topics]

    results_combined = svc.search("novel algorithm quantum materials", filters={"year": 2024, "open_access": True})

    # 6. Update a document
    doc_to_update = svc.get_by_id("paper:quantum_ml_2024")
    doc_to_update.content = doc_to_update.content + " Updated with new experimental validation results."
    doc_to_update.metadata["citations"] = 52
    update_success = svc.update(doc_to_update)
    updated_doc = svc.get_by_id("paper:quantum_ml_2024")
    updated_citations = updated_doc.metadata["citations"]

    # 7. List all with filters
    all_docs = svc.list_all()
    all_docs_count = len(all_docs)

    physics_docs = svc.list_all(filters={"journal": "Nature Physics"})
    physics_docs_count = len(physics_docs)

    # 8. Namespaces
    physics_paper = Document(doc_id="cross_ns_1", content="Quantum entanglement experiment",
                             metadata={"field": "physics"})
    biology_paper = Document(doc_id="cross_ns_1", content="DNA methylation patterns",
                             metadata={"field": "biology"})

    svc.add(physics_paper, namespace="physics")
    svc.add(biology_paper, namespace="biology")

    p = svc.get_by_id("cross_ns_1", namespace="physics")
    b = svc.get_by_id("cross_ns_1", namespace="biology")
    p_content_preview = p.content[:30]
    b_content_preview = b.content[:30]
    all_namespaces = svc.namespaces()

    # 9. Size and stats
    size_default = svc.size()
    size_physics = svc.size(namespace="physics")
    stats = svc.get_stats()

    # 10. Remove and clear
    removed = svc.remove("paper:battery_materials_2024")
    size_after_remove = svc.size()

    cleared = svc.clear(namespace="physics")

    # 11. Context manager
    with MemoryRetrievalService() as tmp_svc:
        tmp_svc.add(Document(doc_id="tmp", content="temporary document"))
        ctx_size = tmp_svc.size()

    # 12. Close
    svc.close()
    ping_after_close = svc.ping()

    # =================================================================
    # OUTPUT
    # =================================================================

    print("=" * 70)
    print("Retrieval Service Tutorial 1: In-Memory Backend")
    print("=" * 70)

    print("\n[1] Create the service")
    print("-" * 50)
    print(f"    Service created -> {svc_repr}")
    print(f"    Ping -> {svc_ping}")

    print("\n[2] Adding scientific papers")
    print("-" * 50)
    for pid, journal in added_papers:
        print(f"    Added '{pid}' ({journal})")

    print("\n[3] Retrieve by ID (get_by_id)")
    print("-" * 50)
    print(f"    Found -> '{doc_id}'")
    print(f"    Content -> {doc_content_preview}...")
    print(f"    Authors -> {doc_authors}")
    print(f"    get_by_id('paper:nonexistent') -> {missing}")

    print("\n[4] Search by keyword")
    print("-" * 50)
    print(f"    'quantum computing machine learning' -> {len(results_quantum_formatted)} results:")
    for rid, score in results_quantum_formatted:
        print(f"        {rid:40s} score={score:.4f}")
    print(f"    'protein structure deep learning' -> {len(results_protein_formatted)} results:")
    for rid, score in results_protein_formatted:
        print(f"        {rid:40s} score={score:.4f}")

    print("\n[5] Metadata filters")
    print("-" * 50)
    print(f"    year=2024: {len(results_year)} papers")
    for rid in results_year_ids:
        print(f"        {rid}")
    print(f"    open_access=True: {len(results_oa)} papers")
    print(f"    topics contains BOTH 'quantum_computing' AND 'machine_learning': {len(results_topics)} papers")
    for rid, topics in results_topics_detail:
        print(f"        {rid} -- topics={topics}")
    print(f"    year=2024 AND open_access=True: {len(results_combined)} papers")

    print("\n[6] Update a document")
    print("-" * 50)
    print(f"    update() -> {update_success}")
    print(f"    New citation count -> {updated_citations}")

    print("\n[7] List all documents (list_all)")
    print("-" * 50)
    print(f"    list_all() -> {all_docs_count} documents")
    print(f"    list_all(journal='Nature Physics') -> {physics_docs_count} document(s)")

    print("\n[8] Namespace isolation")
    print("-" * 50)
    print(f"    physics namespace -> '{p_content_preview}...'")
    print(f"    biology namespace -> '{b_content_preview}...'")
    print(f"    Same doc_id, different namespaces, different content!")
    print(f"    namespaces() -> {all_namespaces}")

    print("\n[9] Size and statistics")
    print("-" * 50)
    print(f"    size() (default namespace) -> {size_default}")
    print(f"    size('physics')            -> {size_physics}")
    print(f"    Stats -> {stats}")

    print("\n[10] Remove and clear")
    print("-" * 50)
    print(f"    remove('paper:battery_materials_2024') -> {removed}")
    print(f"    size() -> {size_after_remove}")
    print(f"    clear('physics') removed {cleared} document(s)")

    print("\n[11] Context manager usage")
    print("-" * 50)
    print(f"    Inside context: size() -> {ctx_size}")
    print(f"    Context manager exited cleanly")

    print("\n[12] Closing service")
    print("-" * 50)
    print(f"    Service closed. Ping -> {ping_after_close}")

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
