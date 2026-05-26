"""
Hypothesis strategies and fixtures for KeyValue Service property-based tests.
"""

import string

import pytest
from hypothesis import strategies as st

from python_utils.service_utils.keyvalue_service.memory_keyvalue_service import (
    MemoryKeyValueService,
)
from python_utils.service_utils.keyvalue_service.file_keyvalue_service import (
    FileKeyValueService,
)
from python_utils.service_utils.keyvalue_service.sqlite_keyvalue_service import (
    SQLiteKeyValueService,
)

# Filesystem-safe alphabet for keys, namespaces, and text values.
_FS_SAFE_CHARS = string.ascii_letters + string.digits + "_-.,!@#$^&()+=[]{}~"

_json_leaf = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-10_000, max_value=10_000),
    st.floats(allow_nan=False, allow_infinity=False, min_value=-1e6, max_value=1e6),
    st.text(max_size=50, alphabet=_FS_SAFE_CHARS),
)


def json_value_strategy():
    """Generate a random JSON-serializable Python value."""
    return st.recursive(
        _json_leaf,
        lambda children: st.one_of(
            st.lists(children, max_size=5),
            st.dictionaries(
                st.text(min_size=1, max_size=20, alphabet=_FS_SAFE_CHARS),
                children,
                max_size=5,
            ),
        ),
        max_leaves=10,
    )


def key_strategy():
    """Generate a valid non-empty key string for key-value operations."""
    return st.text(min_size=1, max_size=50, alphabet=_FS_SAFE_CHARS)


def namespace_strategy():
    """Generate a namespace string, including None for the default namespace."""
    return st.one_of(
        st.none(),
        st.text(min_size=1, max_size=30, alphabet=_FS_SAFE_CHARS),
    )


def explicit_namespace_strategy():
    """Generate a non-None namespace string."""
    return st.text(min_size=1, max_size=30, alphabet=_FS_SAFE_CHARS)


def kv_items_strategy(min_size=1, max_size=5):
    """Generate a dictionary of key-value pairs for batch operations."""
    return st.dictionaries(
        keys=st.text(min_size=1, max_size=30, alphabet=_FS_SAFE_CHARS),
        values=json_value_strategy(),
        min_size=min_size,
        max_size=max_size,
    )


@pytest.fixture(params=["memory", "file", "sqlite"])
def kv_service(request, tmp_path):
    """Yield a fresh KeyValueServiceBase instance for each backend."""
    backend = request.param
    if backend == "memory":
        svc = MemoryKeyValueService()
    elif backend == "file":
        svc = FileKeyValueService(base_dir=str(tmp_path / "file_kv"))
    elif backend == "sqlite":
        svc = SQLiteKeyValueService(db_path=str(tmp_path / "test_kv.db"))
    else:
        raise ValueError(f"Unknown backend: {backend}")
    yield svc
    svc.close()
