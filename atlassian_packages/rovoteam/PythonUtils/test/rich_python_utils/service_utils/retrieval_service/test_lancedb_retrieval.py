"""
Tests for LanceDBRetrievalService.

Requires ``lancedb`` to be installed. Skipped automatically when not available.

# Feature: knowledge-service-extraction
# Task 19.4: Write tests for external retrieval backends
"""

import uuid

import pytest

lancedb = pytest.importorskip("lancedb")

from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from python_utils.service_utils.retrieval_service.lancedb_retrieval_service import (
    LanceDBRetrievalService,
)
from python_utils.service_utils.retrieval_service.document import Document

from conftest import document_strategy

pytestmark = pytest.mark.requires_lancedb

_fx_settings = settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


def _dummy_embed(text: str) -> list:
    """Deterministic dummy embedding for testing (8-dim)."""
    import hashlib
    h = hashlib.md5(text.encode()).hexdigest()
    return [int(h[i:i+2], 16) / 255.0 for i in range(0, 16, 2)]


def _unique_namespace():
    """Generate a unique namespace to isolate each Hypothesis iteration."""
    return f"ns_{uuid.uuid4().hex[:12]}"


@pytest.fixture()
def lance_svc(tmp_path):
    """Yield a LanceDBRetrievalService with a unique table."""
    db_path = str(tmp_path / f"lance_{uuid.uuid4().hex[:8]}")
    svc = LanceDBRetrievalService(
        db_path=db_path,
        embedding_function=_dummy_embed,
        table_name=f"test_{uuid.uuid4().hex[:6]}",
    )
    yield svc
    svc.close()


# ── Property 7: Document add/get round-trip ──

class TestLanceDocRoundTrip:
    """**Validates: Requirements 6.1**"""

    @given(doc=document_strategy())
    @_fx_settings
    def test_add_get_round_trip(self, lance_svc, doc):
        ns = _unique_namespace()
        lance_svc.add(doc, namespace=ns)
        retrieved = lance_svc.get_by_id(doc.doc_id, namespace=ns)
        assert retrieved is not None
        assert retrieved.doc_id == doc.doc_id
        assert retrieved.content == doc.content
        assert retrieved.metadata == doc.metadata


# ── Property 8: Duplicate add raises error ──

class TestLanceDuplicateAdd:
    """**Validates: Requirements 6.2**"""

    @given(doc=document_strategy())
    @_fx_settings
    def test_duplicate_add_raises(self, lance_svc, doc):
        ns = _unique_namespace()
        lance_svc.add(doc, namespace=ns)
        with pytest.raises(ValueError, match="Duplicate"):
            lance_svc.add(doc, namespace=ns)


# ── Unit tests ──

class TestLanceUnit:

    def test_get_nonexistent_returns_none(self, lance_svc):
        assert lance_svc.get_by_id("no_such_doc") is None

    def test_remove(self, lance_svc):
        doc = Document(doc_id="d1", content="hello world")
        lance_svc.add(doc)
        assert lance_svc.remove("d1") is True
        assert lance_svc.get_by_id("d1") is None
        assert lance_svc.remove("d1") is False

    def test_update(self, lance_svc):
        doc = Document(doc_id="d1", content="original")
        lance_svc.add(doc)
        doc.content = "updated"
        assert lance_svc.update(doc) is True
        retrieved = lance_svc.get_by_id("d1")
        assert retrieved.content == "updated"

    def test_search_returns_scores_in_range(self, lance_svc):
        for i in range(3):
            lance_svc.add(Document(doc_id=f"d{i}", content=f"test document number {i}"))
        results = lance_svc.search("test document")
        for doc, score in results:
            assert 0.0 <= score <= 1.0

    def test_size_and_clear(self, lance_svc):
        lance_svc.add(Document(doc_id="a", content="alpha"))
        lance_svc.add(Document(doc_id="b", content="beta"))
        assert lance_svc.size() == 2
        removed = lance_svc.clear()
        assert removed == 2
        assert lance_svc.size() == 0

    def test_namespaces(self, lance_svc):
        lance_svc.add(Document(doc_id="a", content="x"), namespace="ns1")
        lance_svc.add(Document(doc_id="b", content="y"), namespace="ns2")
        ns = lance_svc.namespaces()
        assert "ns1" in ns
        assert "ns2" in ns

    def test_ping(self, lance_svc):
        assert lance_svc.ping() is True

    def test_list_all_with_filters(self, lance_svc):
        lance_svc.add(Document(doc_id="a", content="x", metadata={"type": "alpha"}))
        lance_svc.add(Document(doc_id="b", content="y", metadata={"type": "beta"}))
        docs = lance_svc.list_all(filters={"type": "alpha"})
        assert len(docs) == 1
        assert docs[0].doc_id == "a"
