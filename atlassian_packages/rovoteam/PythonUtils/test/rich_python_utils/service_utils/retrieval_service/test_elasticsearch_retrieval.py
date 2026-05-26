"""
Tests for ElasticsearchRetrievalService.

Requires a running Elasticsearch server and ``elasticsearch`` package.
Skipped automatically when not available.

# Feature: knowledge-service-extraction
# Task 19.4: Write tests for external retrieval backends
"""

import uuid

import pytest

elasticsearch = pytest.importorskip("elasticsearch")

from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from python_utils.service_utils.retrieval_service.elasticsearch_retrieval_service import (
    ElasticsearchRetrievalService,
)
from python_utils.service_utils.retrieval_service.document import Document

from conftest import document_strategy

pytestmark = pytest.mark.requires_elasticsearch

_ES_HOSTS = ["http://localhost:9200"]
_ES_AVAILABLE = None


def _check_es():
    global _ES_AVAILABLE
    if _ES_AVAILABLE is None:
        try:
            from elasticsearch import Elasticsearch
            c = Elasticsearch(hosts=_ES_HOSTS)
            c.ping()
            c.close()
            _ES_AVAILABLE = True
        except Exception:
            _ES_AVAILABLE = False
    return _ES_AVAILABLE


_fx_settings = settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


@pytest.fixture()
def es_svc():
    """Yield an ElasticsearchRetrievalService with a unique index."""
    if not _check_es():
        pytest.skip("Elasticsearch server not available")
    index_name = f"test_{uuid.uuid4().hex[:8]}"
    svc = ElasticsearchRetrievalService(hosts=_ES_HOSTS, index_name=index_name)
    yield svc
    # Cleanup
    try:
        svc._client.indices.delete(index=index_name, ignore_unavailable=True)
    except Exception:
        pass
    svc.close()


# ── Property 7: Document add/get round-trip ──

class TestESDocRoundTrip:
    """**Validates: Requirements 6.1**"""

    @given(doc=document_strategy())
    @_fx_settings
    def test_add_get_round_trip(self, es_svc, doc):
        # Remove if leftover from a previous example with same id
        es_svc.remove(doc.doc_id)
        es_svc.add(doc)
        retrieved = es_svc.get_by_id(doc.doc_id)
        assert retrieved is not None
        assert retrieved.doc_id == doc.doc_id
        assert retrieved.content == doc.content
        assert retrieved.metadata == doc.metadata
        # Cleanup for next example
        es_svc.remove(doc.doc_id)


# ── Property 8: Duplicate add raises error ──

class TestESDuplicateAdd:
    """**Validates: Requirements 6.2**"""

    @given(doc=document_strategy())
    @_fx_settings
    def test_duplicate_add_raises(self, es_svc, doc):
        # Remove if leftover from a previous example with same id
        es_svc.remove(doc.doc_id)
        es_svc.add(doc)
        with pytest.raises(ValueError, match="Duplicate"):
            es_svc.add(doc)
        # Cleanup for next example
        es_svc.remove(doc.doc_id)


# ── Unit tests ──

class TestESUnit:

    def test_get_nonexistent_returns_none(self, es_svc):
        assert es_svc.get_by_id("no_such_doc") is None

    def test_remove(self, es_svc):
        doc = Document(doc_id="d1", content="hello world")
        es_svc.add(doc)
        assert es_svc.remove("d1") is True
        assert es_svc.get_by_id("d1") is None
        assert es_svc.remove("d1") is False

    def test_update(self, es_svc):
        doc = Document(doc_id="d1", content="original")
        es_svc.add(doc)
        doc.content = "updated"
        assert es_svc.update(doc) is True
        retrieved = es_svc.get_by_id("d1")
        assert retrieved.content == "updated"

    def test_search_returns_scores_in_range(self, es_svc):
        for i in range(3):
            es_svc.add(Document(doc_id=f"d{i}", content=f"test document number {i}"))
        results = es_svc.search("test document")
        for doc, score in results:
            assert 0.0 <= score <= 1.0

    def test_size_and_clear(self, es_svc):
        es_svc.add(Document(doc_id="a", content="alpha"))
        es_svc.add(Document(doc_id="b", content="beta"))
        assert es_svc.size() == 2
        removed = es_svc.clear()
        assert removed == 2
        assert es_svc.size() == 0

    def test_namespaces(self, es_svc):
        es_svc.add(Document(doc_id="a", content="x"), namespace="ns1")
        es_svc.add(Document(doc_id="b", content="y"), namespace="ns2")
        ns = es_svc.namespaces()
        assert "ns1" in ns
        assert "ns2" in ns

    def test_ping(self, es_svc):
        assert es_svc.ping() is True

    def test_list_all_with_filters(self, es_svc):
        es_svc.add(Document(doc_id="a", content="x", metadata={"type": "alpha"}))
        es_svc.add(Document(doc_id="b", content="y", metadata={"type": "beta"}))
        docs = es_svc.list_all(filters={"type": "alpha"})
        assert len(docs) == 1
        assert docs[0].doc_id == "a"
