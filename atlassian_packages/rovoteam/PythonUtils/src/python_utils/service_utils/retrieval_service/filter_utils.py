"""
Filter Utilities

Shared filter matching logic for retrieval service backends.
All backends use these utilities to ensure consistent metadata filtering.

Filter semantics:
- Scalar value (str, int, float, bool): exact equality match
- List value: AND containment — all items in filter list must be
  present in the metadata value (which must also be a list)
- Missing key in metadata: filter not matched
"""

from typing import Any, Dict


def matches_filters(metadata: Dict[str, Any], filters: Dict[str, Any]) -> bool:
    """Check if document metadata matches all filter criteria.

    Evaluates whether a document's metadata satisfies a set of filter
    criteria. All filter conditions must be met (AND semantics across keys).

    Args:
        metadata: The document's metadata dictionary to check.
        filters: The filter criteria to apply. Each key-value pair
            defines a condition:
            - Scalar value (str, int, float, bool): requires exact
              equality with the metadata value for that key.
            - List value: requires AND containment — all items in the
              filter list must be present in the metadata value for
              that key (which must also be a list).

    Returns:
        True if the metadata satisfies all filter criteria, False otherwise.
        Returns True if filters is empty (vacuous truth).
    """
    for key, filter_value in filters.items():
        if key not in metadata:
            return False
        doc_value = metadata[key]
        if isinstance(filter_value, list):
            if not isinstance(doc_value, list):
                return False
            if not all(item in doc_value for item in filter_value):
                return False
        else:
            if doc_value != filter_value:
                return False
    return True
