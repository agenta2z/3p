"""
Tests for ChromaRetrievalService.

Requires ``chromadb`` to be installed. Skipped automatically when not available.

# Feature: knowledge-service-extraction
# Task 19.4: Write tests for external retrieval backends
"""

import uuid

import pytest

chromadb = pytest.importorskip("chromadb")

from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from python_utils.service_utils.retrieval_service.chroma_retrieval_service import (
    ChromaRetrievalService,
)
from python_utils.service_utils.retrieval_service.document import Document

from conftest import document_strategy

pytestmark = pytest.mark.requires_chroma

_fx_settings = settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


def _unique_namespace():
    """Generate a unique namespace to isolate each Hypothesis iteration."""
    return f"ns_{uuid.uuid4().hex[:12]}"


@pytest.fixture()
def chroma_svc():
    """Yield an in-memory ChromaRetrievalService with a unique collection."""
    name = f"test_{uuid.uuid4().hex[:8]}"
    svc = ChromaRetrievalService(collection_name=name)
    yield svc
    svc.close()


# ── Property 7: Document add/get round-trip ──

class TestChromaDocRoundTrip:
    """**Validates: Requirements 6.1**"""

    @given(doc=document_strategy())
    @_fx_settings
    def test_add_get_round_trip(self, chroma_svc, doc):
        ns = _unique_namespace()
        chroma_svc.add(doc, namespace=ns)
        retrieved = chroma_svc.get_by_id(doc.doc_id, namespace=ns)
        assert retrieved is not None
        assert retrieved.doc_id == doc.doc_id
        assert retrieved.content == doc.content
        assert retrieved.metadata == doc.metadata


# ── Property 8: Duplicate add raises error ──

class TestChromaDuplicateAdd:
    """**Validates: Requirements 6.2**"""

    @given(doc=document_strategy())
    @_fx_settings
    def test_duplicate_add_raises(self, chroma_svc, doc):
        ns = _unique_namespace()
        chroma_svc.add(doc, namespace=ns)
        with pytest.raises(ValueError, match="Duplicate"):
            chroma_svc.add(doc, namespace=ns)


# ── Unit tests ──

class TestChromaUnit:

    def test_get_nonexistent_returns_none(self, chroma_svc):
        assert chroma_svc.get_by_id("no_such_doc") is None

    def test_remove(self, chroma_svc):
        doc = Document(doc_id="d1", content="hello world")
        chroma_svc.add(doc)
        assert chroma_svc.remove("d1") is True
        assert chroma_svc.get_by_id("d1") is None
        assert chroma_svc.remove("d1") is False

    def test_update(self, chroma_svc):
        doc = Document(doc_id="d1", content="original")
        chroma_svc.add(doc)
        doc.content = "updated"
        assert chroma_svc.update(doc) is True
        retrieved = chroma_svc.get_by_id("d1")
        assert retrieved.content == "updated"

    def test_search_returns_scores_in_range(self, chroma_svc):
        for i in range(3):
            chroma_svc.add(Document(doc_id=f"d{i}", content=f"test document number {i}"))
        results = chroma_svc.search("test document")
        for doc, score in results:
            assert 0.0 <= score <= 1.0

    def test_size_and_clear(self, chroma_svc):
        chroma_svc.add(Document(doc_id="a", content="alpha"))
        chroma_svc.add(Document(doc_id="b", content="beta"))
        assert chroma_svc.size() == 2
        removed = chroma_svc.clear()
        assert removed == 2
        assert chroma_svc.size() == 0

    def test_namespaces(self, chroma_svc):
        chroma_svc.add(Document(doc_id="a", content="x"), namespace="ns1")
        chroma_svc.add(Document(doc_id="b", content="y"), namespace="ns2")
        ns = chroma_svc.namespaces()
        assert "ns1" in ns
        assert "ns2" in ns

    def test_ping(self, chroma_svc):
        assert chroma_svc.ping() is True

    def test_context_manager(self):
        name = f"test_ctx_{uuid.uuid4().hex[:8]}"
        with ChromaRetrievalService(collection_name=name) as svc:
            svc.add(Document(doc_id="k", content="v"))
            assert svc.get_by_id("k") is not None

    def test_list_all_with_filters(self, chroma_svc):
        chroma_svc.add(Document(doc_id="a", content="x", metadata={"type": "alpha"}))
        chroma_svc.add(Document(doc_id="b", content="y", metadata={"type": "beta"}))
        docs = chroma_svc.list_all(filters={"type": "alpha"})
        assert len(docs) == 1
        assert docs[0].doc_id == "a"
