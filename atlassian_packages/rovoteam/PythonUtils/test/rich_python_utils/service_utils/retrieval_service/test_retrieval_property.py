"""
Property-based tests for Retrieval Service.

# Feature: knowledge-service-extraction
# Properties 5-8: Filter matching correctness, search results ordering and
#                 score bounds, document add/get round-trip, duplicate document
#                 add raises error.

Uses Hypothesis to verify universal correctness properties across
randomly generated inputs. Tests are parametrized across backends
via the retrieval_service fixture (currently memory only; Task 7.3
will add file and sqlite_fts5).
"""

import uuid

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from python_utils.service_utils.retrieval_service.document import Document
from python_utils.service_utils.retrieval_service.filter_utils import (
    matches_filters,
)
from python_utils.service_utils.retrieval_service.memory_retrieval_service import (
    MemoryRetrievalService,
)

from conftest import (
    document_strategy,
    metadata_strategy,
    _scalar_value_strategy,
    _list_value_strategy,
    _doc_id_strategy,
    _content_strategy,
    _SAFE_CHARS,
)


# Shared settings for tests that use the retrieval_service fixture.
_fixture_settings = settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


def _unique_namespace():
    """Generate a unique namespace to isolate each Hypothesis iteration."""
    return f"ns_{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# Feature: knowledge-service-extraction, Property 5: Filter matching correctness
# ---------------------------------------------------------------------------


class TestFilterMatchingCorrectness:
    """Property 5: Filter matching correctness.

    For any document metadata dictionary and any filter dictionary, the
    matches_filters function should return True if and only if:
    (a) for every scalar filter value, the metadata contains that key with
        an equal value, and
    (b) for every list filter value, the metadata contains that key with a
        list value containing all filter items.

    **Validates: Requirements 4.3, 15.2, 15.3**
    """

    @given(
        metadata=metadata_strategy(),
    )
    @settings(max_examples=100)
    def test_subset_filter_always_matches(self, metadata):
        """A filter that is a subset of the metadata should always match.

        We pick a random subset of keys from the metadata and use their
        exact values as the filter. This must always return True.

        **Validates: Requirements 4.3, 15.2, 15.3**
        """
        if not metadata:
            # Empty metadata with empty filter should match
            assert matches_filters(metadata, {}) is True
            return

        # Build a filter from all keys of the metadata (strongest subset test)
        subset_filter = {k: metadata[k] for k in metadata}
        assert matches_filters(metadata, subset_filter) is True

    @given(
        metadata=st.dictionaries(
            st.text(min_size=1, max_size=10, alphabet=_SAFE_CHARS),
            _scalar_value_strategy(),
            min_size=1,
            max_size=5,
        ),
    )
    @settings(max_examples=100)
    def test_scalar_mismatch_does_not_match(self, metadata):
        """If a scalar filter value differs from the metadata value, the
        filter should not match.

        We pick a key from the metadata and change its value to something
        different.

        **Validates: Requirements 4.3, 15.2**
        """
        key = list(metadata.keys())[0]
        original_value = metadata[key]

        # Create a mismatched value: use a sentinel that differs from original
        mismatched_value = "__MISMATCH__"
        if original_value == mismatched_value:
            mismatched_value = "__MISMATCH_ALT__"

        bad_filter = {key: mismatched_value}
        assert matches_filters(metadata, bad_filter) is False

    @given(
        key=st.text(min_size=1, max_size=10, alphabet=_SAFE_CHARS),
        metadata_list=st.lists(
            st.text(min_size=1, max_size=10, alphabet=_SAFE_CHARS),
            min_size=2,
            max_size=8,
            unique=True,
        ),
    )
    @settings(max_examples=100)
    def test_list_containment_matches_when_subset(self, key, metadata_list):
        """A list filter that is a subset of the metadata list should match.

        **Validates: Requirements 4.3, 15.3**
        """
        # Use a strict subset (first half) as the filter
        subset = metadata_list[: len(metadata_list) // 2]
        if not subset:
            subset = metadata_list[:1]

        metadata = {key: metadata_list}
        filt = {key: subset}
        assert matches_filters(metadata, filt) is True

    @given(
        key=st.text(min_size=1, max_size=10, alphabet=_SAFE_CHARS),
        metadata_list=st.lists(
            st.text(min_size=1, max_size=10, alphabet=_SAFE_CHARS),
            min_size=0,
            max_size=5,
            unique=True,
        ),
        extra_item=st.text(min_size=1, max_size=10, alphabet=_SAFE_CHARS),
    )
    @settings(max_examples=100)
    def test_list_containment_fails_when_item_missing(self, key, metadata_list, extra_item):
        """A list filter with an item not in the metadata list should not match.

        **Validates: Requirements 4.3, 15.3**
        """
        assume(extra_item not in metadata_list)

        metadata = {key: metadata_list}
        filt = {key: [extra_item]}
        assert matches_filters(metadata, filt) is False

    @given(
        metadata=metadata_strategy(),
        missing_key=st.text(min_size=1, max_size=10, alphabet=_SAFE_CHARS),
    )
    @settings(max_examples=100)
    def test_missing_key_does_not_match(self, metadata, missing_key):
        """A filter with a key not present in metadata should not match.

        **Validates: Requirements 4.3, 15.2, 15.3**
        """
        assume(missing_key not in metadata)

        filt = {missing_key: "any_value"}
        assert matches_filters(metadata, filt) is False


# ---------------------------------------------------------------------------
# Feature: knowledge-service-extraction, Property 6: Search results ordering
# and score bounds
# ---------------------------------------------------------------------------


class TestSearchResultsOrderingAndScoreBounds:
    """Property 6: Search results ordering and score bounds.

    For any search query returning results, all relevance scores should be
    in the range [0.0, 1.0] and the results should be ordered by descending
    score.

    **Validates: Requirements 4.5**
    """

    @given(
        docs=st.lists(
            document_strategy(),
            min_size=1,
            max_size=10,
        ).filter(lambda ds: len({d.doc_id for d in ds}) == len(ds)),
        query=_content_strategy(),
    )
    @_fixture_settings
    def test_scores_in_range_and_ordered(self, retrieval_service, docs, query):
        """All search result scores are in [0.0, 1.0] and ordered descending.

        Each Hypothesis iteration uses a unique namespace to avoid doc_id
        collisions across iterations (the fixture is shared).

        **Validates: Requirements 4.5**
        """
        ns = _unique_namespace()

        for doc in docs:
            retrieval_service.add(doc, namespace=ns)

        results = retrieval_service.search(query, namespace=ns, top_k=len(docs))

        # All scores must be in [0.0, 1.0]
        for doc, score in results:
            assert 0.0 <= score <= 1.0, (
                f"Score {score} out of bounds for doc_id={doc.doc_id!r}"
            )

        # Results must be ordered by descending score
        scores = [score for _, score in results]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1], (
                f"Results not ordered by descending score: "
                f"score[{i}]={scores[i]} < score[{i+1}]={scores[i+1]}"
            )


# ---------------------------------------------------------------------------
# Feature: knowledge-service-extraction, Property 7: Document add/get round-trip
# ---------------------------------------------------------------------------


class TestDocumentAddGetRoundTrip:
    """Property 7: Document add/get round-trip.

    For any valid Document object, adding it to a retrieval service and then
    retrieving it by doc_id should return a Document with equivalent doc_id,
    content, metadata, and embedding_text fields.

    **Validates: Requirements 6.1**
    """

    @given(doc=document_strategy())
    @_fixture_settings
    def test_add_get_round_trip(self, retrieval_service, doc):
        """add(doc) followed by get_by_id(doc.doc_id) returns an equivalent
        Document.

        Each Hypothesis iteration uses a unique namespace to avoid doc_id
        collisions across iterations (the fixture is shared).

        **Validates: Requirements 6.1**
        """
        ns = _unique_namespace()

        retrieval_service.add(doc, namespace=ns)
        retrieved = retrieval_service.get_by_id(doc.doc_id, namespace=ns)

        assert retrieved is not None, (
            f"get_by_id returned None for doc_id={doc.doc_id!r}"
        )
        assert retrieved.doc_id == doc.doc_id, (
            f"doc_id mismatch: expected {doc.doc_id!r}, got {retrieved.doc_id!r}"
        )
        assert retrieved.content == doc.content, (
            f"content mismatch: expected {doc.content!r}, got {retrieved.content!r}"
        )
        assert retrieved.metadata == doc.metadata, (
            f"metadata mismatch: expected {doc.metadata!r}, got {retrieved.metadata!r}"
        )
        assert retrieved.embedding_text == doc.embedding_text, (
            f"embedding_text mismatch: expected {doc.embedding_text!r}, "
            f"got {retrieved.embedding_text!r}"
        )


# ---------------------------------------------------------------------------
# Feature: knowledge-service-extraction, Property 8: Duplicate document add
# raises error
# ---------------------------------------------------------------------------


class TestDuplicateDocumentAddRaisesError:
    """Property 8: Duplicate document add raises error.

    For any valid Document, adding it to a retrieval service and then adding
    a document with the same doc_id again should raise a ValueError.

    **Validates: Requirements 6.2**
    """

    @given(doc=document_strategy())
    @_fixture_settings
    def test_duplicate_add_raises_value_error(self, retrieval_service, doc):
        """Adding a document with the same doc_id twice raises ValueError.

        Each Hypothesis iteration uses a unique namespace to avoid doc_id
        collisions across iterations (the fixture is shared).

        **Validates: Requirements 6.2**
        """
        ns = _unique_namespace()

        retrieval_service.add(doc, namespace=ns)

        # Create a second document with the same doc_id but different content
        duplicate = Document(
            doc_id=doc.doc_id,
            content="different content",
            metadata={},
            created_at="2024-01-01T00:00:00+00:00",
            updated_at="2024-01-01T00:00:00+00:00",
        )

        with pytest.raises(ValueError):
            retrieval_service.add(duplicate, namespace=ns)
