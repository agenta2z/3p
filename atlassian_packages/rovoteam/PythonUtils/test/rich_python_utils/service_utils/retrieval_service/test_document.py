"""
Unit tests for the Document model.

Tests cover construction, auto-generated timestamps, serialization
(to_dict / from_dict), and edge cases.
"""

from datetime import datetime, timezone

from python_utils.service_utils.retrieval_service.document import Document


class TestDocumentConstruction:
    """Tests for Document construction and defaults."""

    def test_required_fields_only(self):
        doc = Document(doc_id="d1", content="hello world")
        assert doc.doc_id == "d1"
        assert doc.content == "hello world"
        assert doc.metadata == {}
        assert doc.embedding_text is None

    def test_all_fields_provided(self):
        doc = Document(
            doc_id="d2",
            content="some content",
            metadata={"key": "value"},
            embedding_text="embed me",
            created_at="2024-01-01T00:00:00+00:00",
            updated_at="2024-06-15T12:00:00+00:00",
        )
        assert doc.doc_id == "d2"
        assert doc.content == "some content"
        assert doc.metadata == {"key": "value"}
        assert doc.embedding_text == "embed me"
        assert doc.created_at == "2024-01-01T00:00:00+00:00"
        assert doc.updated_at == "2024-06-15T12:00:00+00:00"

    def test_metadata_factory_creates_independent_dicts(self):
        doc1 = Document(doc_id="a", content="x")
        doc2 = Document(doc_id="b", content="y")
        doc1.metadata["foo"] = "bar"
        assert "foo" not in doc2.metadata


class TestDocumentTimestamps:
    """Tests for auto-generated ISO 8601 timestamps."""

    def test_auto_generates_created_at_when_none(self):
        before = datetime.now(timezone.utc).isoformat()
        doc = Document(doc_id="d1", content="c")
        after = datetime.now(timezone.utc).isoformat()
        assert before <= doc.created_at <= after

    def test_auto_generates_updated_at_when_none(self):
        before = datetime.now(timezone.utc).isoformat()
        doc = Document(doc_id="d1", content="c")
        after = datetime.now(timezone.utc).isoformat()
        assert before <= doc.updated_at <= after

    def test_created_at_and_updated_at_are_same_when_auto_generated(self):
        doc = Document(doc_id="d1", content="c")
        assert doc.created_at == doc.updated_at

    def test_preserves_explicit_created_at(self):
        ts = "2020-05-10T08:30:00+00:00"
        doc = Document(doc_id="d1", content="c", created_at=ts)
        assert doc.created_at == ts

    def test_preserves_explicit_updated_at(self):
        ts = "2020-05-10T08:30:00+00:00"
        doc = Document(doc_id="d1", content="c", updated_at=ts)
        assert doc.updated_at == ts

    def test_auto_generates_only_missing_timestamps(self):
        explicit_ts = "2020-01-01T00:00:00+00:00"
        doc = Document(doc_id="d1", content="c", created_at=explicit_ts)
        assert doc.created_at == explicit_ts
        # updated_at should be auto-generated (different from explicit_ts)
        assert doc.updated_at != explicit_ts

    def test_timestamps_are_valid_iso_8601(self):
        doc = Document(doc_id="d1", content="c")
        # Should parse without error
        datetime.fromisoformat(doc.created_at)
        datetime.fromisoformat(doc.updated_at)


class TestDocumentToDict:
    """Tests for to_dict serialization."""

    def test_to_dict_contains_all_fields(self):
        doc = Document(
            doc_id="d1",
            content="hello",
            metadata={"k": "v"},
            embedding_text="embed",
            created_at="2024-01-01T00:00:00+00:00",
            updated_at="2024-06-01T00:00:00+00:00",
        )
        d = doc.to_dict()
        assert d == {
            "doc_id": "d1",
            "content": "hello",
            "metadata": {"k": "v"},
            "embedding_text": "embed",
            "created_at": "2024-01-01T00:00:00+00:00",
            "updated_at": "2024-06-01T00:00:00+00:00",
        }

    def test_to_dict_with_defaults(self):
        doc = Document(doc_id="d1", content="c")
        d = doc.to_dict()
        assert d["doc_id"] == "d1"
        assert d["content"] == "c"
        assert d["metadata"] == {}
        assert d["embedding_text"] is None
        assert d["created_at"] is not None
        assert d["updated_at"] is not None

    def test_to_dict_returns_copy_of_metadata(self):
        original_meta = {"key": "value"}
        doc = Document(doc_id="d1", content="c", metadata=original_meta)
        d = doc.to_dict()
        d["metadata"]["new_key"] = "new_value"
        assert "new_key" not in doc.metadata

    def test_to_dict_with_empty_content(self):
        doc = Document(doc_id="d1", content="")
        d = doc.to_dict()
        assert d["content"] == ""

    def test_to_dict_with_complex_metadata(self):
        meta = {"tags": ["a", "b"], "count": 42, "nested": {"x": 1}}
        doc = Document(doc_id="d1", content="c", metadata=meta)
        d = doc.to_dict()
        assert d["metadata"] == {"tags": ["a", "b"], "count": 42, "nested": {"x": 1}}


class TestDocumentFromDict:
    """Tests for from_dict deserialization."""

    def test_from_dict_with_all_fields(self):
        data = {
            "doc_id": "d1",
            "content": "hello",
            "metadata": {"k": "v"},
            "embedding_text": "embed",
            "created_at": "2024-01-01T00:00:00+00:00",
            "updated_at": "2024-06-01T00:00:00+00:00",
        }
        doc = Document.from_dict(data)
        assert doc.doc_id == "d1"
        assert doc.content == "hello"
        assert doc.metadata == {"k": "v"}
        assert doc.embedding_text == "embed"
        assert doc.created_at == "2024-01-01T00:00:00+00:00"
        assert doc.updated_at == "2024-06-01T00:00:00+00:00"

    def test_from_dict_with_minimal_fields(self):
        data = {"doc_id": "d1", "content": "hello"}
        doc = Document.from_dict(data)
        assert doc.doc_id == "d1"
        assert doc.content == "hello"
        assert doc.metadata == {}
        assert doc.embedding_text is None
        # Timestamps auto-generated since not in data
        assert doc.created_at is not None
        assert doc.updated_at is not None

    def test_from_dict_preserves_timestamps(self):
        data = {
            "doc_id": "d1",
            "content": "c",
            "created_at": "2020-01-01T00:00:00+00:00",
            "updated_at": "2020-06-01T00:00:00+00:00",
        }
        doc = Document.from_dict(data)
        assert doc.created_at == "2020-01-01T00:00:00+00:00"
        assert doc.updated_at == "2020-06-01T00:00:00+00:00"


class TestDocumentRoundTrip:
    """Tests for to_dict / from_dict round-trip."""

    def test_round_trip_with_all_fields(self):
        original = Document(
            doc_id="d1",
            content="hello world",
            metadata={"tags": ["a", "b"], "score": 0.95},
            embedding_text="embed text",
            created_at="2024-01-01T00:00:00+00:00",
            updated_at="2024-06-01T00:00:00+00:00",
        )
        restored = Document.from_dict(original.to_dict())
        assert restored.doc_id == original.doc_id
        assert restored.content == original.content
        assert restored.metadata == original.metadata
        assert restored.embedding_text == original.embedding_text
        assert restored.created_at == original.created_at
        assert restored.updated_at == original.updated_at

    def test_round_trip_with_defaults(self):
        original = Document(doc_id="d1", content="c")
        restored = Document.from_dict(original.to_dict())
        assert restored.doc_id == original.doc_id
        assert restored.content == original.content
        assert restored.metadata == original.metadata
        assert restored.embedding_text == original.embedding_text
        assert restored.created_at == original.created_at
        assert restored.updated_at == original.updated_at

    def test_round_trip_with_none_embedding_text(self):
        original = Document(
            doc_id="d1",
            content="c",
            embedding_text=None,
            created_at="2024-01-01T00:00:00+00:00",
            updated_at="2024-01-01T00:00:00+00:00",
        )
        restored = Document.from_dict(original.to_dict())
        assert restored.embedding_text is None

    def test_round_trip_with_empty_metadata(self):
        original = Document(
            doc_id="d1",
            content="c",
            metadata={},
            created_at="2024-01-01T00:00:00+00:00",
            updated_at="2024-01-01T00:00:00+00:00",
        )
        restored = Document.from_dict(original.to_dict())
        assert restored.metadata == {}
