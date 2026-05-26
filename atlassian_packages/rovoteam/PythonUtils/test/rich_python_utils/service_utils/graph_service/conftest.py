"""
Hypothesis strategies and fixtures for Graph Service property-based tests.

Provides reusable strategies for generating:
- GraphNode objects (graph_node_strategy)
- GraphEdge objects (graph_edge_strategy)

Provides fixtures:
- graph_service: yields a fresh GraphServiceBase instance
  parametrized across memory, file, and networkx backends.

Used by property-based tests across graph_service backends.
"""

import string

import pytest
from hypothesis import strategies as st

from python_utils.service_utils.graph_service.graph_node import GraphEdge, GraphNode
from python_utils.service_utils.graph_service.memory_graph_service import (
    MemoryGraphService,
)


# Filesystem-safe alphabet for IDs and text values.
_safe_string = st.text(
    alphabet=string.ascii_letters + string.digits + "_-",
    min_size=1,
    max_size=20,
)

_node_type_strategy = st.text(
    alphabet=string.ascii_lowercase,
    min_size=1,
    max_size=10,
)

_properties_strategy = st.dictionaries(
    st.text(min_size=1, max_size=10, alphabet=string.ascii_lowercase),
    st.one_of(
        st.text(max_size=20),
        st.integers(-100, 100),
        st.booleans(),
    ),
    max_size=5,
)


def graph_node_strategy():
    """Generate a valid GraphNode object with random fields."""
    return st.builds(
        GraphNode,
        node_id=_safe_string,
        node_type=_node_type_strategy,
        label=st.text(max_size=20),
        properties=_properties_strategy,
    )


def graph_edge_strategy(node_ids):
    """Generate a valid GraphEdge between nodes from the given node_ids list.

    Args:
        node_ids: A list of node_id strings to sample source_id and target_id from.
    """
    return st.builds(
        GraphEdge,
        source_id=st.sampled_from(node_ids),
        target_id=st.sampled_from(node_ids),
        edge_type=_node_type_strategy,
        properties=_properties_strategy,
    )


@pytest.fixture(params=["memory", "file", "networkx"])
def graph_service(request, tmp_path):
    """Yield a fresh GraphServiceBase instance.

    Parametrized across backends so that property tests run against all
    implementations: memory, file, and networkx.
    """
    backend = request.param
    if backend == "memory":
        svc = MemoryGraphService()
    elif backend == "file":
        from python_utils.service_utils.graph_service.file_graph_service import FileGraphService
        svc = FileGraphService(base_dir=str(tmp_path / "graph_store"))
    elif backend == "networkx":
        from python_utils.service_utils.graph_service.networkx_graph_service import NetworkxGraphService
        svc = NetworkxGraphService()
    else:
        raise ValueError(f"Unknown backend: {backend}")

    yield svc
    svc.close()
