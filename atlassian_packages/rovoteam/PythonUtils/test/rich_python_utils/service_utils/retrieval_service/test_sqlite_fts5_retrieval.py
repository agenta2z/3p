"""
Unit tests for SQLiteFTS5RetrievalService.

Tests cover core CRUD operations, FTS5 search with BM25 scoring,
metadata filtering, namespace handling, context manager protocol,
query sanitization, and edge cases.

Validates: Requirements 5.3
"""

import pytest

from python_utils.service_utils.retrieval_service.document import Document
from python_utils.service_utils.retrieval_service.sqlite_fts5_retrieval_service import (
    SQLiteFTS5RetrievalService,
)


class TestSQLiteFTS5RetrievalServiceAdd:
    """Tests for adding documents."""

    def test_add_returns_doc_id(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        doc = Document(doc_id="d1", content="hello world")
        result = svc.add(doc)
        assert result == "d1"

    def test_add_stores_document(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        doc = Document(doc_id="d1", content="hello world")
        svc.add(doc)
        assert svc.size() == 1

    def test_add_duplicate_raises_value_error(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        doc1 = Document(doc_id="d1", content="first")
        doc2 = Document(doc_id="d1", content="second")
        svc.add(doc1)
        with pytest.raises(ValueError, match="already exists"):
            svc.add(doc2)

    def test_add_same_id_different_namespaces(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        doc1 = Document(doc_id="d1", content="first")
        doc2 = Document(doc_id="d1", content="second")
        svc.add(doc1, namespace="ns1")
        svc.add(doc2, namespace="ns2")  # Should not raise
        assert svc.get_by_id("d1", namespace="ns1").content == "first"
        assert svc.get_by_id("d1", namespace="ns2").content == "second"

    def test_add_preserves_metadata(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        doc = Document(doc_id="d1", content="hello", metadata={"key": "val", "tags": ["a", "b"]})
        svc.add(doc)
        result = svc.get_by_id("d1")
        assert result.metadata == {"key": "val", "tags": ["a", "b"]}

    def test_add_preserves_embedding_text(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        doc = Document(doc_id="d1", content="hello", embedding_text="embed this")
        svc.add(doc)
        result = svc.get_by_id("d1")
        assert result.embedding_text == "embed this"

    def test_add_preserves_timestamps(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        doc = Document(doc_id="d1", content="hello")
        svc.add(doc)
        result = svc.get_by_id("d1")
        assert result.created_at == doc.created_at
        assert result.updated_at == doc.updated_at


class TestSQLiteFTS5RetrievalServiceGetById:
    """Tests for retrieving documents by ID."""

    def test_get_existing_document(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        doc = Document(doc_id="d1", content="hello", metadata={"key": "val"})
        svc.add(doc)
        result = svc.get_by_id("d1")
        assert result.doc_id == "d1"
        assert result.content == "hello"
        assert result.metadata == {"key": "val"}

    def test_get_nonexistent_returns_none(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        assert svc.get_by_id("nonexistent") is None

    def test_get_from_empty_namespace_returns_none(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        assert svc.get_by_id("d1", namespace="empty_ns") is None

    def test_get_wrong_namespace_returns_none(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        doc = Document(doc_id="d1", content="hello")
        svc.add(doc, namespace="ns1")
        assert svc.get_by_id("d1", namespace="ns2") is None


class TestSQLiteFTS5RetrievalServiceUpdate:
    """Tests for updating documents."""

    def test_update_existing_document(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        doc = Document(doc_id="d1", content="original")
        svc.add(doc)
        updated_doc = Document(doc_id="d1", content="updated")
        assert svc.update(updated_doc) is True
        result = svc.get_by_id("d1")
        assert result.content == "updated"

    def test_update_nonexistent_returns_false(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        doc = Document(doc_id="d1", content="hello")
        assert svc.update(doc) is False

    def test_update_wrong_namespace_returns_false(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        doc = Document(doc_id="d1", content="hello")
        svc.add(doc, namespace="ns1")
        updated = Document(doc_id="d1", content="updated")
        assert svc.update(updated, namespace="ns2") is False

    def test_update_changes_updated_at(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        doc = Document(doc_id="d1", content="original")
        svc.add(doc)
        original_updated_at = svc.get_by_id("d1").updated_at
        updated_doc = Document(doc_id="d1", content="updated")
        svc.update(updated_doc)
        result = svc.get_by_id("d1")
        assert result.updated_at >= original_updated_at

    def test_update_reflects_in_search(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        doc = Document(doc_id="d1", content="python tutorial")
        svc.add(doc)
        updated_doc = Document(doc_id="d1", content="java guide")
        svc.update(updated_doc)
        # Should find with new content
        results = svc.search("java")
        assert len(results) == 1
        assert results[0][0].doc_id == "d1"
        # Should not find with old content
        results = svc.search("python")
        assert len(results) == 0


class TestSQLiteFTS5RetrievalServiceRemove:
    """Tests for removing documents."""

    def test_remove_existing_document(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        doc = Document(doc_id="d1", content="hello")
        svc.add(doc)
        assert svc.remove("d1") is True
        assert svc.get_by_id("d1") is None

    def test_remove_nonexistent_returns_false(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        assert svc.remove("nonexistent") is False

    def test_remove_decrements_size(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        svc.add(Document(doc_id="d1", content="hello"))
        svc.add(Document(doc_id="d2", content="world"))
        assert svc.size() == 2
        svc.remove("d1")
        assert svc.size() == 1

    def test_remove_cleans_fts_index(self, tmp_path):
        """Removed documents should not appear in search results."""
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        svc.add(Document(doc_id="d1", content="python tutorial"))
        svc.remove("d1")
        results = svc.search("python")
        assert len(results) == 0


class TestSQLiteFTS5RetrievalServiceSearch:
    """Tests for FTS5 search with BM25 scoring."""

    def test_search_finds_matching_document(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        doc = Document(doc_id="d1", content="python is great for data science")
        svc.add(doc)
        results = svc.search("python data")
        assert len(results) == 1
        assert results[0][0].doc_id == "d1"

    def test_search_score_normalized_to_0_1(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        doc = Document(doc_id="d1", content="python is great for data science")
        svc.add(doc)
        results = svc.search("python data")
        score = results[0][1]
        assert 0.0 <= score <= 1.0

    def test_search_best_match_gets_score_1(self, tmp_path):
        """The best matching document should get a score of 1.0."""
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        svc.add(Document(doc_id="d1", content="python"))
        svc.add(Document(doc_id="d2", content="python python python"))
        results = svc.search("python")
        # The best match should have score 1.0
        assert results[0][1] == 1.0

    def test_search_no_match_returns_empty(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        doc = Document(doc_id="d1", content="hello world")
        svc.add(doc)
        results = svc.search("xyznonexistent")
        assert len(results) == 0

    def test_search_case_insensitive(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        doc = Document(doc_id="d1", content="Python Data Science")
        svc.add(doc)
        results = svc.search("python data")
        assert len(results) == 1

    def test_search_ordered_by_descending_score(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        svc.add(Document(doc_id="d1", content="alpha"))
        svc.add(Document(doc_id="d2", content="alpha beta"))
        svc.add(Document(doc_id="d3", content="alpha beta gamma"))
        results = svc.search("alpha beta gamma")
        scores = [score for _, score in results]
        assert scores == sorted(scores, reverse=True)

    def test_search_respects_top_k(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        for i in range(10):
            svc.add(Document(doc_id=f"d{i}", content=f"common term document number {i}"))
        results = svc.search("common", top_k=3)
        assert len(results) == 3

    def test_search_empty_query_returns_empty(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        svc.add(Document(doc_id="d1", content="hello world"))
        results = svc.search("")
        assert results == []

    def test_search_whitespace_only_query_returns_empty(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        svc.add(Document(doc_id="d1", content="hello world"))
        results = svc.search("   ")
        assert results == []

    def test_search_empty_store_returns_empty(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        results = svc.search("hello")
        assert results == []

    def test_search_with_metadata_filters(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        svc.add(Document(doc_id="d1", content="python tutorial", metadata={"type": "article"}))
        svc.add(Document(doc_id="d2", content="python guide", metadata={"type": "blog"}))
        results = svc.search("python", filters={"type": "article"})
        assert len(results) == 1
        assert results[0][0].doc_id == "d1"

    def test_search_with_list_filter(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
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
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        svc.add(Document(doc_id="d1", content="hello world", metadata={"type": "article"}))
        results = svc.search("hello", filters={"type": "blog"})
        assert len(results) == 0

    def test_search_scoped_to_namespace(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        svc.add(Document(doc_id="d1", content="python tutorial"), namespace="ns1")
        svc.add(Document(doc_id="d2", content="python guide"), namespace="ns2")
        results = svc.search("python", namespace="ns1")
        assert len(results) == 1
        assert results[0][0].doc_id == "d1"

    def test_search_special_characters_in_query(self, tmp_path):
        """Special characters in query should not cause FTS5 syntax errors."""
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        svc.add(Document(doc_id="d1", content="hello world"))
        # These should not raise, even if they contain FTS5 special chars
        results = svc.search('hello "world"')
        assert len(results) >= 0  # Just ensure no error
        results = svc.search("hello OR world")
        assert len(results) >= 0
        results = svc.search("hello*")
        assert len(results) >= 0

    def test_search_punctuation_only_query_returns_empty(self, tmp_path):
        """A query with only punctuation should return empty results."""
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        svc.add(Document(doc_id="d1", content="hello world"))
        results = svc.search("!!! ???")
        assert results == []


class TestSQLiteFTS5RetrievalServiceListAll:
    """Tests for listing all documents."""

    def test_list_all_returns_all_documents(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        svc.add(Document(doc_id="d1", content="first"))
        svc.add(Document(doc_id="d2", content="second"))
        docs = svc.list_all()
        assert len(docs) == 2
        doc_ids = {d.doc_id for d in docs}
        assert doc_ids == {"d1", "d2"}

    def test_list_all_empty_returns_empty(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        assert svc.list_all() == []

    def test_list_all_with_filters(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        svc.add(Document(doc_id="d1", content="a", metadata={"type": "article"}))
        svc.add(Document(doc_id="d2", content="b", metadata={"type": "blog"}))
        docs = svc.list_all(filters={"type": "article"})
        assert len(docs) == 1
        assert docs[0].doc_id == "d1"

    def test_list_all_scoped_to_namespace(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        svc.add(Document(doc_id="d1", content="a"), namespace="ns1")
        svc.add(Document(doc_id="d2", content="b"), namespace="ns2")
        docs = svc.list_all(namespace="ns1")
        assert len(docs) == 1
        assert docs[0].doc_id == "d1"


class TestSQLiteFTS5RetrievalServiceNamespaces:
    """Tests for namespace-scoped operations."""

    def test_default_namespace_when_none(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        svc.add(Document(doc_id="d1", content="hello"))
        assert svc.get_by_id("d1") is not None
        assert svc.get_by_id("d1", namespace=None) is not None

    def test_separate_namespaces(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        svc.add(Document(doc_id="d1", content="ns1 content"), namespace="ns1")
        svc.add(Document(doc_id="d1", content="ns2 content"), namespace="ns2")
        assert svc.get_by_id("d1", namespace="ns1").content == "ns1 content"
        assert svc.get_by_id("d1", namespace="ns2").content == "ns2 content"

    def test_size_per_namespace(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        svc.add(Document(doc_id="d1", content="a"), namespace="ns1")
        svc.add(Document(doc_id="d2", content="b"), namespace="ns1")
        svc.add(Document(doc_id="d3", content="c"), namespace="ns2")
        assert svc.size(namespace="ns1") == 2
        assert svc.size(namespace="ns2") == 1

    def test_size_empty_namespace(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        assert svc.size(namespace="nonexistent") == 0

    def test_clear_namespace(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        svc.add(Document(doc_id="d1", content="a"), namespace="ns1")
        svc.add(Document(doc_id="d2", content="b"), namespace="ns1")
        svc.add(Document(doc_id="d3", content="c"), namespace="ns2")
        count = svc.clear(namespace="ns1")
        assert count == 2
        assert svc.size(namespace="ns1") == 0
        assert svc.size(namespace="ns2") == 1

    def test_clear_empty_namespace(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        assert svc.clear(namespace="nonexistent") == 0

    def test_namespaces_list(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        svc.add(Document(doc_id="d1", content="a"), namespace="ns1")
        svc.add(Document(doc_id="d2", content="b"), namespace="ns2")
        assert sorted(svc.namespaces()) == ["ns1", "ns2"]

    def test_namespaces_empty(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        assert svc.namespaces() == []

    def test_search_scoped_to_namespace(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        svc.add(Document(doc_id="d1", content="python tutorial"), namespace="ns1")
        svc.add(Document(doc_id="d2", content="python guide"), namespace="ns2")
        results = svc.search("python", namespace="ns1")
        assert len(results) == 1
        assert results[0][0].doc_id == "d1"


class TestSQLiteFTS5RetrievalServiceQuerySanitization:
    """Tests for FTS5 query sanitization."""

    def test_sanitize_basic_query(self):
        result = SQLiteFTS5RetrievalService._sanitize_fts_query("hello world")
        assert result == '"hello" "world"'

    def test_sanitize_strips_special_chars(self):
        result = SQLiteFTS5RetrievalService._sanitize_fts_query("hello! world?")
        assert result == '"hello" "world"'

    def test_sanitize_empty_query(self):
        result = SQLiteFTS5RetrievalService._sanitize_fts_query("")
        assert result == ""

    def test_sanitize_only_special_chars(self):
        result = SQLiteFTS5RetrievalService._sanitize_fts_query("!!! ???")
        assert result == ""

    def test_sanitize_preserves_alphanumeric(self):
        result = SQLiteFTS5RetrievalService._sanitize_fts_query("python3 data2")
        assert result == '"python3" "data2"'


class TestSQLiteFTS5RetrievalServiceLifecycle:
    """Tests for ping, close, context manager, and repr."""

    def test_ping_when_open(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        assert svc.ping() is True

    def test_ping_when_closed(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        svc.close()
        assert svc.ping() is False

    def test_close_is_idempotent(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        svc.close()
        svc.close()  # Should not raise
        assert svc.ping() is False

    def test_context_manager(self, tmp_path):
        with SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db")) as svc:
            svc.add(Document(doc_id="d1", content="hello"))
            assert svc.get_by_id("d1") is not None
        assert svc.ping() is False

    def test_repr_when_open(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        svc.add(Document(doc_id="d1", content="a"), namespace="ns1")
        svc.add(Document(doc_id="d2", content="b"), namespace="ns1")
        r = repr(svc)
        assert "SQLiteFTS5RetrievalService" in r
        assert "namespaces=1" in r
        assert "total_documents=2" in r
        assert "tokenizer='unicode61'" in r

    def test_repr_when_closed(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        svc.close()
        r = repr(svc)
        assert "SQLiteFTS5RetrievalService" in r
        assert "closed=True" in r

    def test_get_stats_all(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        svc.add(Document(doc_id="d1", content="a"), namespace="ns1")
        svc.add(Document(doc_id="d2", content="b"), namespace="ns2")
        stats = svc.get_stats()
        assert stats["backend"] == "sqlite_fts5"
        assert stats["namespace_count"] == 2
        assert stats["total_documents"] == 2
        assert "db_path" in stats
        assert stats["tokenizer"] == "unicode61"

    def test_get_stats_specific_namespace(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        svc.add(Document(doc_id="d1", content="a"), namespace="ns1")
        svc.add(Document(doc_id="d2", content="b"), namespace="ns1")
        stats = svc.get_stats(namespace="ns1")
        assert stats["backend"] == "sqlite_fts5"
        assert stats["namespace"] == "ns1"
        assert stats["documents"] == 2

    def test_get_stats_empty_namespace(self, tmp_path):
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "test.db"))
        stats = svc.get_stats(namespace="nonexistent")
        assert stats["documents"] == 0

    def test_custom_tokenizer(self, tmp_path):
        """Service should accept a custom tokenizer parameter."""
        svc = SQLiteFTS5RetrievalService(
            db_path=str(tmp_path / "test.db"),
            tokenizer="porter",
        )
        assert svc.tokenizer == "porter"
        # Should still work for basic operations
        svc.add(Document(doc_id="d1", content="running runners run"))
        results = svc.search("run")
        # Porter stemmer should match "running", "runners", "run"
        assert len(results) >= 1

    def test_data_persists_across_connections(self, tmp_path):
        """Data should persist when reopening the database."""
        db_path = str(tmp_path / "test.db")
        svc1 = SQLiteFTS5RetrievalService(db_path=db_path)
        svc1.add(Document(doc_id="d1", content="persistent data"))
        svc1.close()

        svc2 = SQLiteFTS5RetrievalService(db_path=db_path)
        result = svc2.get_by_id("d1")
        assert result is not None
        assert result.content == "persistent data"
        svc2.close()

    def test_search_persists_across_connections(self, tmp_path):
        """FTS5 index should persist when reopening the database."""
        db_path = str(tmp_path / "test.db")
        svc1 = SQLiteFTS5RetrievalService(db_path=db_path)
        svc1.add(Document(doc_id="d1", content="persistent search data"))
        svc1.close()

        svc2 = SQLiteFTS5RetrievalService(db_path=db_path)
        results = svc2.search("persistent")
        assert len(results) == 1
        assert results[0][0].doc_id == "d1"
        svc2.close()
