"""
Unit tests for MemoryRetrievalService.

Tests cover core CRUD operations, search with term overlap scoring,
metadata filtering, namespace handling, context manager protocol,
and edge cases.

Validates: Requirements 5.1
"""

import pytest

from python_utils.service_utils.retrieval_service.document import Document
from python_utils.service_utils.retrieval_service.memory_retrieval_service import (
    MemoryRetrievalService,
)


class TestMemoryRetrievalServiceAdd:
    """Tests for adding documents."""

    def test_add_returns_doc_id(self):
        svc = MemoryRetrievalService()
        doc = Document(doc_id="d1", content="hello world")
        result = svc.add(doc)
        assert result == "d1"

    def test_add_stores_document(self):
        svc = MemoryRetrievalService()
        doc = Document(doc_id="d1", content="hello world")
        svc.add(doc)
        assert svc.size() == 1

    def test_add_duplicate_raises_value_error(self):
        svc = MemoryRetrievalService()
        doc1 = Document(doc_id="d1", content="first")
        doc2 = Document(doc_id="d1", content="second")
        svc.add(doc1)
        with pytest.raises(ValueError, match="already exists"):
            svc.add(doc2)

    def test_add_same_id_different_namespaces(self):
        svc = MemoryRetrievalService()
        doc1 = Document(doc_id="d1", content="first")
        doc2 = Document(doc_id="d1", content="second")
        svc.add(doc1, namespace="ns1")
        svc.add(doc2, namespace="ns2")  # Should not raise
        assert svc.get_by_id("d1", namespace="ns1").content == "first"
        assert svc.get_by_id("d1", namespace="ns2").content == "second"


class TestMemoryRetrievalServiceGetById:
    """Tests for retrieving documents by ID."""

    def test_get_existing_document(self):
        svc = MemoryRetrievalService()
        doc = Document(doc_id="d1", content="hello", metadata={"key": "val"})
        svc.add(doc)
        result = svc.get_by_id("d1")
        assert result.doc_id == "d1"
        assert result.content == "hello"
        assert result.metadata == {"key": "val"}

    def test_get_nonexistent_returns_none(self):
        svc = MemoryRetrievalService()
        assert svc.get_by_id("nonexistent") is None

    def test_get_from_empty_namespace_returns_none(self):
        svc = MemoryRetrievalService()
        assert svc.get_by_id("d1", namespace="empty_ns") is None

    def test_get_wrong_namespace_returns_none(self):
        svc = MemoryRetrievalService()
        doc = Document(doc_id="d1", content="hello")
        svc.add(doc, namespace="ns1")
        assert svc.get_by_id("d1", namespace="ns2") is None


class TestMemoryRetrievalServiceUpdate:
    """Tests for updating documents."""

    def test_update_existing_document(self):
        svc = MemoryRetrievalService()
        doc = Document(doc_id="d1", content="original")
        svc.add(doc)
        updated_doc = Document(doc_id="d1", content="updated")
        assert svc.update(updated_doc) is True
        result = svc.get_by_id("d1")
        assert result.content == "updated"

    def test_update_nonexistent_returns_false(self):
        svc = MemoryRetrievalService()
        doc = Document(doc_id="d1", content="hello")
        assert svc.update(doc) is False

    def test_update_wrong_namespace_returns_false(self):
        svc = MemoryRetrievalService()
        doc = Document(doc_id="d1", content="hello")
        svc.add(doc, namespace="ns1")
        updated = Document(doc_id="d1", content="updated")
        assert svc.update(updated, namespace="ns2") is False


class TestMemoryRetrievalServiceRemove:
    """Tests for removing documents."""

    def test_remove_existing_document(self):
        svc = MemoryRetrievalService()
        doc = Document(doc_id="d1", content="hello")
        svc.add(doc)
        assert svc.remove("d1") is True
        assert svc.get_by_id("d1") is None

    def test_remove_nonexistent_returns_false(self):
        svc = MemoryRetrievalService()
        assert svc.remove("nonexistent") is False

    def test_remove_cleans_up_empty_namespace(self):
        svc = MemoryRetrievalService()
        doc = Document(doc_id="d1", content="hello")
        svc.add(doc, namespace="ns1")
        svc.remove("d1", namespace="ns1")
        assert "ns1" not in svc.namespaces()


class TestMemoryRetrievalServiceSearch:
    """Tests for search with term overlap scoring."""

    def test_search_finds_matching_document(self):
        svc = MemoryRetrievalService()
        doc = Document(doc_id="d1", content="python is great for data science")
        svc.add(doc)
        results = svc.search("python data")
        assert len(results) == 1
        assert results[0][0].doc_id == "d1"

    def test_search_score_normalized_to_0_1(self):
        svc = MemoryRetrievalService()
        doc = Document(doc_id="d1", content="python is great for data science")
        svc.add(doc)
        results = svc.search("python data")
        score = results[0][1]
        assert 0.0 <= score <= 1.0

    def test_search_full_overlap_score_is_1(self):
        svc = MemoryRetrievalService()
        doc = Document(doc_id="d1", content="hello world")
        svc.add(doc)
        results = svc.search("hello world")
        assert results[0][1] == 1.0

    def test_search_partial_overlap(self):
        svc = MemoryRetrievalService()
        doc = Document(doc_id="d1", content="hello world")
        svc.add(doc)
        results = svc.search("hello universe")
        assert len(results) == 1
        assert results[0][1] == 0.5  # 1 of 2 query terms match

    def test_search_no_overlap_returns_empty(self):
        svc = MemoryRetrievalService()
        doc = Document(doc_id="d1", content="hello world")
        svc.add(doc)
        results = svc.search("foo bar")
        assert len(results) == 0

    def test_search_case_insensitive(self):
        svc = MemoryRetrievalService()
        doc = Document(doc_id="d1", content="Python Data Science")
        svc.add(doc)
        results = svc.search("python data")
        assert len(results) == 1
        assert results[0][1] == 1.0

    def test_search_ordered_by_descending_score(self):
        svc = MemoryRetrievalService()
        svc.add(Document(doc_id="d1", content="alpha"))
        svc.add(Document(doc_id="d2", content="alpha beta"))
        svc.add(Document(doc_id="d3", content="alpha beta gamma"))
        results = svc.search("alpha beta gamma")
        assert len(results) == 3
        scores = [score for _, score in results]
        assert scores == sorted(scores, reverse=True)
        # d3 has all 3 terms, d2 has 2, d1 has 1
        assert results[0][0].doc_id == "d3"
        assert results[1][0].doc_id == "d2"
        assert results[2][0].doc_id == "d1"

    def test_search_respects_top_k(self):
        svc = MemoryRetrievalService()
        for i in range(10):
            svc.add(Document(doc_id=f"d{i}", content=f"common term doc{i}"))
        results = svc.search("common", top_k=3)
        assert len(results) == 3

    def test_search_empty_query_returns_empty(self):
        svc = MemoryRetrievalService()
        svc.add(Document(doc_id="d1", content="hello world"))
        results = svc.search("")
        assert results == []

    def test_search_empty_store_returns_empty(self):
        svc = MemoryRetrievalService()
        results = svc.search("hello")
        assert results == []

    def test_search_with_metadata_filters(self):
        svc = MemoryRetrievalService()
        svc.add(Document(doc_id="d1", content="python tutorial", metadata={"type": "article"}))
        svc.add(Document(doc_id="d2", content="python guide", metadata={"type": "blog"}))
        results = svc.search("python", filters={"type": "article"})
        assert len(results) == 1
        assert results[0][0].doc_id == "d1"

    def test_search_with_list_filter(self):
        svc = MemoryRetrievalService()
        svc.add(Document(
            doc_id="d1",
            content="python tutorial",
            metadata={"tags": ["python", "beginner"]},
        ))
        svc.add(Document(
            doc_id="d2",
            content="python advanced",
            metadata={"tags": ["python", "advanced"]},
        ))
        results = svc.search("python", filters={"tags": ["python", "beginner"]})
        assert len(results) == 1
        assert results[0][0].doc_id == "d1"

    def test_search_filters_exclude_all(self):
        svc = MemoryRetrievalService()
        svc.add(Document(doc_id="d1", content="hello", metadata={"type": "article"}))
        results = svc.search("hello", filters={"type": "blog"})
        assert len(results) == 0


class TestMemoryRetrievalServiceListAll:
    """Tests for listing all documents."""

    def test_list_all_returns_all_documents(self):
        svc = MemoryRetrievalService()
        svc.add(Document(doc_id="d1", content="first"))
        svc.add(Document(doc_id="d2", content="second"))
        docs = svc.list_all()
        assert len(docs) == 2
        doc_ids = {d.doc_id for d in docs}
        assert doc_ids == {"d1", "d2"}

    def test_list_all_empty_returns_empty(self):
        svc = MemoryRetrievalService()
        assert svc.list_all() == []

    def test_list_all_with_filters(self):
        svc = MemoryRetrievalService()
        svc.add(Document(doc_id="d1", content="a", metadata={"type": "article"}))
        svc.add(Document(doc_id="d2", content="b", metadata={"type": "blog"}))
        docs = svc.list_all(filters={"type": "article"})
        assert len(docs) == 1
        assert docs[0].doc_id == "d1"

    def test_list_all_scoped_to_namespace(self):
        svc = MemoryRetrievalService()
        svc.add(Document(doc_id="d1", content="a"), namespace="ns1")
        svc.add(Document(doc_id="d2", content="b"), namespace="ns2")
        docs = svc.list_all(namespace="ns1")
        assert len(docs) == 1
        assert docs[0].doc_id == "d1"


class TestMemoryRetrievalServiceNamespaces:
    """Tests for namespace-scoped operations."""

    def test_default_namespace_when_none(self):
        svc = MemoryRetrievalService()
        svc.add(Document(doc_id="d1", content="hello"))
        assert svc.get_by_id("d1") is not None
        assert svc.get_by_id("d1", namespace=None) is not None

    def test_separate_namespaces(self):
        svc = MemoryRetrievalService()
        svc.add(Document(doc_id="d1", content="ns1 content"), namespace="ns1")
        svc.add(Document(doc_id="d1", content="ns2 content"), namespace="ns2")
        assert svc.get_by_id("d1", namespace="ns1").content == "ns1 content"
        assert svc.get_by_id("d1", namespace="ns2").content == "ns2 content"

    def test_size_per_namespace(self):
        svc = MemoryRetrievalService()
        svc.add(Document(doc_id="d1", content="a"), namespace="ns1")
        svc.add(Document(doc_id="d2", content="b"), namespace="ns1")
        svc.add(Document(doc_id="d3", content="c"), namespace="ns2")
        assert svc.size(namespace="ns1") == 2
        assert svc.size(namespace="ns2") == 1

    def test_size_empty_namespace(self):
        svc = MemoryRetrievalService()
        assert svc.size(namespace="nonexistent") == 0

    def test_clear_namespace(self):
        svc = MemoryRetrievalService()
        svc.add(Document(doc_id="d1", content="a"), namespace="ns1")
        svc.add(Document(doc_id="d2", content="b"), namespace="ns1")
        svc.add(Document(doc_id="d3", content="c"), namespace="ns2")
        count = svc.clear(namespace="ns1")
        assert count == 2
        assert svc.size(namespace="ns1") == 0
        assert svc.size(namespace="ns2") == 1

    def test_clear_empty_namespace(self):
        svc = MemoryRetrievalService()
        assert svc.clear(namespace="nonexistent") == 0

    def test_namespaces_list(self):
        svc = MemoryRetrievalService()
        svc.add(Document(doc_id="d1", content="a"), namespace="ns1")
        svc.add(Document(doc_id="d2", content="b"), namespace="ns2")
        assert sorted(svc.namespaces()) == ["ns1", "ns2"]

    def test_namespaces_empty(self):
        svc = MemoryRetrievalService()
        assert svc.namespaces() == []

    def test_search_scoped_to_namespace(self):
        svc = MemoryRetrievalService()
        svc.add(Document(doc_id="d1", content="python tutorial"), namespace="ns1")
        svc.add(Document(doc_id="d2", content="python guide"), namespace="ns2")
        results = svc.search("python", namespace="ns1")
        assert len(results) == 1
        assert results[0][0].doc_id == "d1"


class TestMemoryRetrievalServiceLifecycle:
    """Tests for ping, close, context manager, and repr."""

    def test_ping_when_open(self):
        svc = MemoryRetrievalService()
        assert svc.ping() is True

    def test_ping_when_closed(self):
        svc = MemoryRetrievalService()
        svc.close()
        assert svc.ping() is False

    def test_close_is_idempotent(self):
        svc = MemoryRetrievalService()
        svc.close()
        svc.close()  # Should not raise
        assert svc.ping() is False

    def test_context_manager(self):
        with MemoryRetrievalService() as svc:
            svc.add(Document(doc_id="d1", content="hello"))
            assert svc.get_by_id("d1") is not None
        assert svc.ping() is False

    def test_repr(self):
        svc = MemoryRetrievalService()
        svc.add(Document(doc_id="d1", content="a"), namespace="ns1")
        svc.add(Document(doc_id="d2", content="b"), namespace="ns1")
        r = repr(svc)
        assert "MemoryRetrievalService" in r
        assert "namespaces=1" in r
        assert "total_documents=2" in r

    def test_get_stats_all(self):
        svc = MemoryRetrievalService()
        svc.add(Document(doc_id="d1", content="a"), namespace="ns1")
        svc.add(Document(doc_id="d2", content="b"), namespace="ns2")
        stats = svc.get_stats()
        assert stats["backend"] == "memory"
        assert stats["namespace_count"] == 2
        assert stats["total_documents"] == 2

    def test_get_stats_specific_namespace(self):
        svc = MemoryRetrievalService()
        svc.add(Document(doc_id="d1", content="a"), namespace="ns1")
        svc.add(Document(doc_id="d2", content="b"), namespace="ns1")
        stats = svc.get_stats(namespace="ns1")
        assert stats["backend"] == "memory"
        assert stats["namespace"] == "ns1"
        assert stats["documents"] == 2

    def test_get_stats_empty_namespace(self):
        svc = MemoryRetrievalService()
        stats = svc.get_stats(namespace="nonexistent")
        assert stats["documents"] == 0
