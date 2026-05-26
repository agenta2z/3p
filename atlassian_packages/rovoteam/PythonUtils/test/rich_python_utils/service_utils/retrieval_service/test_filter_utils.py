"""
Unit tests for the filter_utils module.

Tests cover scalar equality, list AND containment, missing keys,
empty filters, and edge cases for the matches_filters function.

Validates: Requirements 15.1, 15.2, 15.3, 15.4
"""

from python_utils.service_utils.retrieval_service.filter_utils import (
    matches_filters,
)


class TestMatchesFiltersScalar:
    """Tests for scalar (exact equality) filter matching.

    Validates: Requirements 15.2
    """

    def test_string_exact_match(self):
        metadata = {"color": "red"}
        filters = {"color": "red"}
        assert matches_filters(metadata, filters) is True

    def test_string_no_match(self):
        metadata = {"color": "red"}
        filters = {"color": "blue"}
        assert matches_filters(metadata, filters) is False

    def test_int_exact_match(self):
        metadata = {"count": 42}
        filters = {"count": 42}
        assert matches_filters(metadata, filters) is True

    def test_int_no_match(self):
        metadata = {"count": 42}
        filters = {"count": 99}
        assert matches_filters(metadata, filters) is False

    def test_float_exact_match(self):
        metadata = {"score": 0.95}
        filters = {"score": 0.95}
        assert matches_filters(metadata, filters) is True

    def test_bool_exact_match(self):
        metadata = {"active": True}
        filters = {"active": True}
        assert matches_filters(metadata, filters) is True

    def test_bool_no_match(self):
        metadata = {"active": True}
        filters = {"active": False}
        assert matches_filters(metadata, filters) is False

    def test_multiple_scalar_filters_all_match(self):
        metadata = {"color": "red", "size": 10, "active": True}
        filters = {"color": "red", "size": 10}
        assert matches_filters(metadata, filters) is True

    def test_multiple_scalar_filters_one_fails(self):
        metadata = {"color": "red", "size": 10}
        filters = {"color": "red", "size": 20}
        assert matches_filters(metadata, filters) is False


class TestMatchesFiltersList:
    """Tests for list (AND containment) filter matching.

    Validates: Requirements 15.3
    """

    def test_list_all_items_present(self):
        metadata = {"tags": ["python", "testing", "ci"]}
        filters = {"tags": ["python", "testing"]}
        assert matches_filters(metadata, filters) is True

    def test_list_exact_match(self):
        metadata = {"tags": ["a", "b"]}
        filters = {"tags": ["a", "b"]}
        assert matches_filters(metadata, filters) is True

    def test_list_subset_present(self):
        metadata = {"tags": ["a", "b", "c"]}
        filters = {"tags": ["a"]}
        assert matches_filters(metadata, filters) is True

    def test_list_item_missing(self):
        metadata = {"tags": ["a", "b"]}
        filters = {"tags": ["a", "c"]}
        assert matches_filters(metadata, filters) is False

    def test_list_filter_against_non_list_metadata(self):
        metadata = {"tags": "single_value"}
        filters = {"tags": ["single_value"]}
        assert matches_filters(metadata, filters) is False

    def test_empty_filter_list_matches_any_list(self):
        metadata = {"tags": ["a", "b"]}
        filters = {"tags": []}
        assert matches_filters(metadata, filters) is True

    def test_empty_filter_list_matches_empty_metadata_list(self):
        metadata = {"tags": []}
        filters = {"tags": []}
        assert matches_filters(metadata, filters) is True

    def test_non_empty_filter_list_against_empty_metadata_list(self):
        metadata = {"tags": []}
        filters = {"tags": ["a"]}
        assert matches_filters(metadata, filters) is False


class TestMatchesFiltersMissingKey:
    """Tests for missing key behavior.

    Validates: Requirements 15.4
    """

    def test_missing_key_scalar_filter(self):
        metadata = {"color": "red"}
        filters = {"size": 10}
        assert matches_filters(metadata, filters) is False

    def test_missing_key_list_filter(self):
        metadata = {"color": "red"}
        filters = {"tags": ["a"]}
        assert matches_filters(metadata, filters) is False

    def test_one_key_present_one_missing(self):
        metadata = {"color": "red"}
        filters = {"color": "red", "size": 10}
        assert matches_filters(metadata, filters) is False

    def test_empty_metadata_with_filters(self):
        metadata = {}
        filters = {"color": "red"}
        assert matches_filters(metadata, filters) is False


class TestMatchesFiltersEmpty:
    """Tests for empty filter edge cases.

    Validates: Requirements 15.1
    """

    def test_empty_filters_matches_any_metadata(self):
        metadata = {"color": "red", "tags": ["a"]}
        filters = {}
        assert matches_filters(metadata, filters) is True

    def test_empty_filters_matches_empty_metadata(self):
        metadata = {}
        filters = {}
        assert matches_filters(metadata, filters) is True


class TestMatchesFiltersMixed:
    """Tests for mixed scalar and list filters."""

    def test_scalar_and_list_both_match(self):
        metadata = {"type": "article", "tags": ["python", "testing"]}
        filters = {"type": "article", "tags": ["python"]}
        assert matches_filters(metadata, filters) is True

    def test_scalar_matches_list_fails(self):
        metadata = {"type": "article", "tags": ["python"]}
        filters = {"type": "article", "tags": ["python", "java"]}
        assert matches_filters(metadata, filters) is False

    def test_scalar_fails_list_matches(self):
        metadata = {"type": "article", "tags": ["python", "testing"]}
        filters = {"type": "blog", "tags": ["python"]}
        assert matches_filters(metadata, filters) is False

    def test_metadata_has_extra_keys(self):
        """Extra metadata keys not in filters should not affect matching."""
        metadata = {"type": "article", "author": "alice", "tags": ["a"]}
        filters = {"type": "article"}
        assert matches_filters(metadata, filters) is True
