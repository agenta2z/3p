"""
Unit tests for FileRetrievalService.

Tests cover core CRUD operations, BM25/term-overlap search, metadata
filtering, namespace handling, percent-encoding of doc_ids, malformed
JSON handling, context manager protocol, and edge cases.

Validates: Requirements 5.2
"""

import json
import os

import pytest

from python_utils.service_utils.retrieval_service.document import Document
from python_utils.service_utils.retrieval_service.file_retrieval_service import (
    FileRetrievalService,
    _encode_doc_id,
    _decode_doc_id,
)
from python_utils.nlp_utils.semantic_search import tokenize as _tokenize


class TestFileRetrievalServiceAdd:
    """Tests for adding documents."""

    def test_add_returns_doc_id(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        doc = Document(doc_id="d1", content="hello world")
        result = svc.add(doc)
        assert result == "d1"

    def test_add_stores_document_as_json_file(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        doc = Document(doc_id="d1", content="hello world")
        svc.add(doc)
        expected_path = os.path.join(str(tmp_path), "_default", "d1.json")
        assert os.path.exists(expected_path)
        with open(expected_path, "r") as f:
            data = json.load(f)
        assert data["doc_id"] == "d1"
        assert data["content"] == "hello world"

    def test_add_increments_size(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        doc = Document(doc_id="d1", content="hello world")
        svc.add(doc)
        assert svc.size() == 1

    def test_add_duplicate_raises_value_error(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        doc1 = Document(doc_id="d1", content="first")
        doc2 = Document(doc_id="d1", content="second")
        svc.add(doc1)
        with pytest.raises(ValueError, match="already exists"):
            svc.add(doc2)

    def test_add_same_id_different_namespaces(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        doc1 = Document(doc_id="d1", content="first")
        doc2 = Document(doc_id="d1", content="second")
        svc.add(doc1, namespace="ns1")
        svc.add(doc2, namespace="ns2")  # Should not raise
        assert svc.get_by_id("d1", namespace="ns1").content == "first"
        assert svc.get_by_id("d1", namespace="ns2").content == "second"

    def test_add_preserves_metadata(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        doc = Document(doc_id="d1", content="hello", metadata={"key": "val", "tags": ["a", "b"]})
        svc.add(doc)
        result = svc.get_by_id("d1")
        assert result.metadata == {"key": "val", "tags": ["a", "b"]}

    def test_add_preserves_embedding_text(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        doc = Document(doc_id="d1", content="hello", embedding_text="embed this")
        svc.add(doc)
        result = svc.get_by_id("d1")
        assert result.embedding_text == "embed this"


class TestFileRetrievalServiceGetById:
    """Tests for retrieving documents by ID."""

    def test_get_existing_document(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        doc = Document(doc_id="d1", content="hello", metadata={"key": "val"})
        svc.add(doc)
        result = svc.get_by_id("d1")
        assert result.doc_id == "d1"
        assert result.content == "hello"
        assert result.metadata == {"key": "val"}

    def test_get_nonexistent_returns_none(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        assert svc.get_by_id("nonexistent") is None

    def test_get_from_empty_namespace_returns_none(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        assert svc.get_by_id("d1", namespace="empty_ns") is None

    def test_get_wrong_namespace_returns_none(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        doc = Document(doc_id="d1", content="hello")
        svc.add(doc, namespace="ns1")
        assert svc.get_by_id("d1", namespace="ns2") is None


class TestFileRetrievalServiceUpdate:
    """Tests for updating documents."""

    def test_update_existing_document(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        doc = Document(doc_id="d1", content="original")
        svc.add(doc)
        updated_doc = Document(doc_id="d1", content="updated")
        assert svc.update(updated_doc) is True
        result = svc.get_by_id("d1")
        assert result.content == "updated"

    def test_update_nonexistent_returns_false(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        doc = Document(doc_id="d1", content="hello")
        assert svc.update(doc) is False

    def test_update_wrong_namespace_returns_false(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        doc = Document(doc_id="d1", content="hello")
        svc.add(doc, namespace="ns1")
        updated = Document(doc_id="d1", content="updated")
        assert svc.update(updated, namespace="ns2") is False


class TestFileRetrievalServiceRemove:
    """Tests for removing documents."""

    def test_remove_existing_document(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        doc = Document(doc_id="d1", content="hello")
        svc.add(doc)
        assert svc.remove("d1") is True
        assert svc.get_by_id("d1") is None

    def test_remove_nonexistent_returns_false(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        assert svc.remove("nonexistent") is False

    def test_remove_cleans_up_empty_namespace_dir(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        doc = Document(doc_id="d1", content="hello")
        svc.add(doc, namespace="ns1")
        svc.remove("d1", namespace="ns1")
        assert "ns1" not in svc.namespaces()
        assert not os.path.isdir(os.path.join(str(tmp_path), "ns1"))


class TestFileRetrievalServiceSearch:
    """Tests for search with BM25/term-overlap scoring."""

    def test_search_finds_matching_document(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        doc = Document(doc_id="d1", content="python is great for data science")
        svc.add(doc)
        results = svc.search("python data")
        assert len(results) == 1
        assert results[0][0].doc_id == "d1"

    def test_search_score_normalized_to_0_1(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        doc = Document(doc_id="d1", content="python is great for data science")
        svc.add(doc)
        results = svc.search("python data")
        score = results[0][1]
        assert 0.0 <= score <= 1.0

    def test_search_no_overlap_returns_empty(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        doc = Document(doc_id="d1", content="hello world")
        svc.add(doc)
        results = svc.search("foo bar")
        assert len(results) == 0

    def test_search_case_insensitive(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        doc = Document(doc_id="d1", content="Python Data Science")
        svc.add(doc)
        results = svc.search("python data")
        assert len(results) == 1

    def test_search_ordered_by_descending_score(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        svc.add(Document(doc_id="d1", content="alpha"))
        svc.add(Document(doc_id="d2", content="alpha beta"))
        svc.add(Document(doc_id="d3", content="alpha beta gamma"))
        results = svc.search("alpha beta gamma")
        assert len(results) == 3
        scores = [score for _, score in results]
        assert scores == sorted(scores, reverse=True)

    def test_search_respects_top_k(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        for i in range(10):
            svc.add(Document(doc_id=f"d{i}", content=f"common term doc{i}"))
        results = svc.search("common", top_k=3)
        assert len(results) == 3

    def test_search_empty_query_returns_empty(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        svc.add(Document(doc_id="d1", content="hello world"))
        results = svc.search("")
        assert results == []

    def test_search_empty_store_returns_empty(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        results = svc.search("hello")
        assert results == []

    def test_search_with_metadata_filters(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        svc.add(Document(doc_id="d1", content="python tutorial", metadata={"type": "article"}))
        svc.add(Document(doc_id="d2", content="python guide", metadata={"type": "blog"}))
        results = svc.search("python", filters={"type": "article"})
        assert len(results) == 1
        assert results[0][0].doc_id == "d1"

    def test_search_with_list_filter(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
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

    def test_search_filters_exclude_all(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        svc.add(Document(doc_id="d1", content="hello", metadata={"type": "article"}))
        results = svc.search("hello", filters={"type": "blog"})
        assert len(results) == 0

    def test_search_scoped_to_namespace(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        svc.add(Document(doc_id="d1", content="python tutorial"), namespace="ns1")
        svc.add(Document(doc_id="d2", content="python guide"), namespace="ns2")
        results = svc.search("python", namespace="ns1")
        assert len(results) == 1
        assert results[0][0].doc_id == "d1"


class TestFileRetrievalServiceListAll:
    """Tests for listing all documents."""

    def test_list_all_returns_all_documents(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        svc.add(Document(doc_id="d1", content="first"))
        svc.add(Document(doc_id="d2", content="second"))
        docs = svc.list_all()
        assert len(docs) == 2
        doc_ids = {d.doc_id for d in docs}
        assert doc_ids == {"d1", "d2"}

    def test_list_all_empty_returns_empty(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        assert svc.list_all() == []

    def test_list_all_with_filters(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        svc.add(Document(doc_id="d1", content="a", metadata={"type": "article"}))
        svc.add(Document(doc_id="d2", content="b", metadata={"type": "blog"}))
        docs = svc.list_all(filters={"type": "article"})
        assert len(docs) == 1
        assert docs[0].doc_id == "d1"

    def test_list_all_scoped_to_namespace(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        svc.add(Document(doc_id="d1", content="a"), namespace="ns1")
        svc.add(Document(doc_id="d2", content="b"), namespace="ns2")
        docs = svc.list_all(namespace="ns1")
        assert len(docs) == 1
        assert docs[0].doc_id == "d1"


class TestFileRetrievalServiceNamespaces:
    """Tests for namespace-scoped operations."""

    def test_default_namespace_when_none(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        svc.add(Document(doc_id="d1", content="hello"))
        assert svc.get_by_id("d1") is not None
        assert svc.get_by_id("d1", namespace=None) is not None

    def test_separate_namespaces(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        svc.add(Document(doc_id="d1", content="ns1 content"), namespace="ns1")
        svc.add(Document(doc_id="d1", content="ns2 content"), namespace="ns2")
        assert svc.get_by_id("d1", namespace="ns1").content == "ns1 content"
        assert svc.get_by_id("d1", namespace="ns2").content == "ns2 content"

    def test_size_per_namespace(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        svc.add(Document(doc_id="d1", content="a"), namespace="ns1")
        svc.add(Document(doc_id="d2", content="b"), namespace="ns1")
        svc.add(Document(doc_id="d3", content="c"), namespace="ns2")
        assert svc.size(namespace="ns1") == 2
        assert svc.size(namespace="ns2") == 1

    def test_size_empty_namespace(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        assert svc.size(namespace="nonexistent") == 0

    def test_clear_namespace(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        svc.add(Document(doc_id="d1", content="a"), namespace="ns1")
        svc.add(Document(doc_id="d2", content="b"), namespace="ns1")
        svc.add(Document(doc_id="d3", content="c"), namespace="ns2")
        count = svc.clear(namespace="ns1")
        assert count == 2
        assert svc.size(namespace="ns1") == 0
        assert svc.size(namespace="ns2") == 1

    def test_clear_empty_namespace(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        assert svc.clear(namespace="nonexistent") == 0

    def test_namespaces_list(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        svc.add(Document(doc_id="d1", content="a"), namespace="ns1")
        svc.add(Document(doc_id="d2", content="b"), namespace="ns2")
        assert sorted(svc.namespaces()) == ["ns1", "ns2"]

    def test_namespaces_empty(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        assert svc.namespaces() == []


class TestFileRetrievalServicePercentEncoding:
    """Tests for percent-encoding of doc_ids to produce safe filenames."""

    def test_encode_colon(self):
        assert _encode_doc_id("user:xinli") == "user%3Axinli"

    def test_encode_forward_slash(self):
        assert _encode_doc_id("path/to/thing") == "path%2Fto%2Fthing"

    def test_encode_backslash(self):
        assert _encode_doc_id("back\\slash") == "back%5Cslash"

    def test_encode_percent_first(self):
        assert _encode_doc_id("100%") == "100%25"

    def test_encode_no_special_chars(self):
        assert _encode_doc_id("simple_id") == "simple_id"

    def test_decode_reverses_encode(self):
        original = "user:xinli/path\\back%percent"
        assert _decode_doc_id(_encode_doc_id(original)) == original

    def test_add_get_with_special_doc_id(self, tmp_path):
        """Doc IDs with special characters should round-trip correctly."""
        svc = FileRetrievalService(base_dir=str(tmp_path))
        doc = Document(doc_id="user:xinli", content="hello")
        svc.add(doc)
        result = svc.get_by_id("user:xinli")
        assert result is not None
        assert result.doc_id == "user:xinli"
        assert result.content == "hello"

    def test_remove_with_special_doc_id(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        doc = Document(doc_id="a:b/c\\d%e", content="hello")
        svc.add(doc)
        assert svc.remove("a:b/c\\d%e") is True
        assert svc.get_by_id("a:b/c\\d%e") is None


class TestFileRetrievalServiceMalformedJSON:
    """Tests for handling malformed JSON files."""

    def test_malformed_json_returns_none_on_get(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        ns_dir = os.path.join(str(tmp_path), "_default")
        os.makedirs(ns_dir, exist_ok=True)
        malformed_path = os.path.join(ns_dir, "bad_doc.json")
        with open(malformed_path, "w") as f:
            f.write("{invalid json content")
        assert svc.get_by_id("bad_doc") is None

    def test_malformed_json_skipped_in_list_all(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        svc.add(Document(doc_id="good_doc", content="hello"))
        # Create a malformed JSON file
        ns_dir = os.path.join(str(tmp_path), "_default")
        with open(os.path.join(ns_dir, "bad_doc.json"), "w") as f:
            f.write("not json")
        docs = svc.list_all()
        assert len(docs) == 1
        assert docs[0].doc_id == "good_doc"

    def test_malformed_json_skipped_in_search(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        svc.add(Document(doc_id="good_doc", content="hello world"))
        # Create a malformed JSON file
        ns_dir = os.path.join(str(tmp_path), "_default")
        with open(os.path.join(ns_dir, "bad_doc.json"), "w") as f:
            f.write("not json")
        results = svc.search("hello")
        assert len(results) == 1
        assert results[0][0].doc_id == "good_doc"


class TestFileRetrievalServiceTokenize:
    """Tests for the _tokenize helper function."""

    def test_basic_tokenization(self):
        assert _tokenize("Hello World") == ["hello", "world"]

    def test_strips_punctuation(self):
        assert _tokenize("hello, world!") == ["hello", "world"]

    def test_empty_string(self):
        assert _tokenize("") == []

    def test_only_punctuation(self):
        assert _tokenize("!!! ???") == []

    def test_mixed_case(self):
        assert _tokenize("Python DATA Science") == ["python", "data", "science"]


class TestFileRetrievalServiceLifecycle:
    """Tests for ping, close, context manager, and repr."""

    def test_ping_when_open(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        assert svc.ping() is True

    def test_ping_when_closed(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        svc.close()
        assert svc.ping() is False

    def test_close_is_idempotent(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        svc.close()
        svc.close()  # Should not raise
        assert svc.ping() is False

    def test_context_manager(self, tmp_path):
        with FileRetrievalService(base_dir=str(tmp_path)) as svc:
            svc.add(Document(doc_id="d1", content="hello"))
            assert svc.get_by_id("d1") is not None
        assert svc.ping() is False

    def test_repr(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        svc.add(Document(doc_id="d1", content="a"), namespace="ns1")
        svc.add(Document(doc_id="d2", content="b"), namespace="ns1")
        r = repr(svc)
        assert "FileRetrievalService" in r
        assert "namespaces=1" in r
        assert "total_documents=2" in r

    def test_get_stats_all(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        svc.add(Document(doc_id="d1", content="a"), namespace="ns1")
        svc.add(Document(doc_id="d2", content="b"), namespace="ns2")
        stats = svc.get_stats()
        assert stats["backend"] == "file"
        assert stats["namespace_count"] == 2
        assert stats["total_documents"] == 2
        assert "base_dir" in stats
        assert "bm25_available" in stats

    def test_get_stats_specific_namespace(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        svc.add(Document(doc_id="d1", content="a"), namespace="ns1")
        svc.add(Document(doc_id="d2", content="b"), namespace="ns1")
        stats = svc.get_stats(namespace="ns1")
        assert stats["backend"] == "file"
        assert stats["namespace"] == "ns1"
        assert stats["documents"] == 2

    def test_get_stats_empty_namespace(self, tmp_path):
        svc = FileRetrievalService(base_dir=str(tmp_path))
        stats = svc.get_stats(namespace="nonexistent")
        assert stats["documents"] == 0
