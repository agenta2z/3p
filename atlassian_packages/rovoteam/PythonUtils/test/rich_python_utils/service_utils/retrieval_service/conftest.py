"""
Hypothesis strategies and fixtures for Retrieval Service property-based tests.

Provides reusable strategies for generating:
- Document objects (document_strategy)
- Metadata dictionaries with scalar and list values (metadata_strategy)
- Filter dictionaries (filter_strategy)

Provides fixtures:
- retrieval_service: yields a fresh RetrievalServiceBase instance
  (currently MemoryRetrievalService; will be parametrized in Task 7.3).

Used by property-based tests across retrieval_service backends.
"""

import string

import pytest
from hypothesis import strategies as st

from python_utils.service_utils.retrieval_service.document import Document
from python_utils.service_utils.retrieval_service.file_retrieval_service import (
    FileRetrievalService,
)
from python_utils.service_utils.retrieval_service.memory_retrieval_service import (
    MemoryRetrievalService,
)
from python_utils.service_utils.retrieval_service.sqlite_fts5_retrieval_service import (
    SQLiteFTS5RetrievalService,
)


# Filesystem-safe alphabet for IDs, keys, and text values.
_SAFE_CHARS = string.ascii_letters + string.digits + "_-"


def _doc_id_strategy():
    """Generate a valid non-empty document ID string."""
    return st.text(min_size=1, max_size=30, alphabet=_SAFE_CHARS)


def _content_strategy():
    """Generate document content strings.

    Content contains space-separated words so that term-overlap search
    can find matches.
    """
    word = st.text(min_size=1, max_size=15, alphabet=string.ascii_lowercase)
    return st.lists(word, min_size=1, max_size=10).map(lambda words: " ".join(words))


def _scalar_value_strategy():
    """Generate scalar filter values: str, int, float, or bool."""
    return st.one_of(
        st.text(min_size=1, max_size=20, alphabet=_SAFE_CHARS),
        st.integers(min_value=-1000, max_value=1000),
        st.floats(
            allow_nan=False,
            allow_infinity=False,
            min_value=-1e4,
            max_value=1e4,
        ),
        st.booleans(),
    )


def _list_value_strategy():
    """Generate list filter values: lists of strings."""
    return st.lists(
        st.text(min_size=1, max_size=15, alphabet=_SAFE_CHARS),
        min_size=0,
        max_size=5,
        unique=True,
    )


def metadata_strategy():
    """Generate a metadata dictionary with a mix of scalar and list values.

    Keys are non-empty safe strings. Values are either scalars (str, int,
    float, bool) or lists of strings.
    """
    key = st.text(min_size=1, max_size=15, alphabet=_SAFE_CHARS)
    value = st.one_of(_scalar_value_strategy(), _list_value_strategy())
    return st.dictionaries(key, value, min_size=0, max_size=5)


def scalar_metadata_strategy():
    """Generate a metadata dictionary with only scalar values.

    Useful for filter tests where we want predictable scalar matching.
    """
    key = st.text(min_size=1, max_size=15, alphabet=_SAFE_CHARS)
    return st.dictionaries(key, _scalar_value_strategy(), min_size=0, max_size=5)


def list_metadata_strategy():
    """Generate a metadata dictionary with only list values.

    Useful for filter tests where we want predictable list containment matching.
    """
    key = st.text(min_size=1, max_size=15, alphabet=_SAFE_CHARS)
    return st.dictionaries(key, _list_value_strategy(), min_size=0, max_size=5)


def document_strategy():
    """Generate a valid Document object with random fields.

    Generates documents with:
    - Non-empty doc_id
    - Non-empty content (space-separated words)
    - Random metadata (mix of scalar and list values)
    - Optional embedding_text
    - Explicit timestamps to avoid auto-generation variability
    """
    return st.builds(
        Document,
        doc_id=_doc_id_strategy(),
        content=_content_strategy(),
        metadata=metadata_strategy(),
        embedding_text=st.one_of(st.none(), _content_strategy()),
        created_at=st.just("2024-01-01T00:00:00+00:00"),
        updated_at=st.just("2024-01-01T00:00:00+00:00"),
    )


def filter_strategy_from_metadata(metadata):
    """Build a filter dictionary that is a subset of the given metadata.

    This ensures the generated filter will match the metadata, which is
    useful for testing that matches_filters returns True for valid subsets.

    Args:
        metadata: A metadata dictionary to derive filters from.

    Returns:
        A Hypothesis strategy producing a filter dict that is a subset
        of the input metadata.
    """
    if not metadata:
        return st.just({})
    keys = list(metadata.keys())
    return st.sets(st.sampled_from(keys)).map(
        lambda selected: {k: metadata[k] for k in selected}
    )


@pytest.fixture(params=["memory", "file", "sqlite_fts5"])
def retrieval_service(request, tmp_path):
    """Yield a fresh RetrievalServiceBase instance.

    Parametrized across memory, file, and sqlite_fts5 backends so that
    property tests run against all three implementations.
    """
    backend = request.param
    if backend == "memory":
        svc = MemoryRetrievalService()
    elif backend == "file":
        svc = FileRetrievalService(base_dir=str(tmp_path / "retrieval_files"))
    elif backend == "sqlite_fts5":
        svc = SQLiteFTS5RetrievalService(db_path=str(tmp_path / "retrieval.db"))
    else:
        raise ValueError(f"Unknown backend: {backend}")

    yield svc
    svc.close()
