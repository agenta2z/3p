"""
Unit tests for FileGraphService search_nodes() term-overlap search.
"""

import pytest

from python_utils.service_utils.graph_service.graph_node import GraphNode
from python_utils.service_utils.graph_service.file_graph_service import (
    FileGraphService,
)


class TestFileGraphServiceSearch:
    """Tests for search_nodes() term-overlap search."""

    def test_supports_search_is_true(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        assert svc.supports_search is True

    def test_search_empty_query_returns_empty(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(node_id="n1", node_type="person", label="Alice"))
        assert svc.search_nodes("") == []
        assert svc.search_nodes("   ") == []

    def test_search_empty_graph_returns_empty(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        assert svc.search_nodes("alice") == []

    def test_search_matches_label(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(node_id="n1", node_type="person", label="Alice Smith"))
        svc.add_node(GraphNode(node_id="n2", node_type="person", label="Bob Jones"))
        results = svc.search_nodes("alice")
        assert len(results) == 1
        assert results[0][0].node_id == "n1"
        assert results[0][1] > 0.0

    def test_search_matches_node_type(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(node_id="n1", node_type="person", label="Alice"))
        results = svc.search_nodes("person")
        assert len(results) == 1
        assert results[0][0].node_id == "n1"

    def test_search_matches_properties(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(
            node_id="n1", node_type="person", label="Alice",
            properties={"city": "Seattle", "role": "engineer"},
        ))
        results = svc.search_nodes("seattle")
        assert len(results) == 1
        assert results[0][0].node_id == "n1"

    def test_search_no_match_returns_empty(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(node_id="n1", node_type="person", label="Alice"))
        assert svc.search_nodes("nonexistent") == []

    def test_search_top_k_limits_results(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        for i in range(10):
            svc.add_node(GraphNode(
                node_id=f"n{i}", node_type="person", label=f"Person {i}",
            ))
        results = svc.search_nodes("person", top_k=3)
        assert len(results) == 3

    def test_search_node_type_filter(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(node_id="n1", node_type="person", label="Alice"))
        svc.add_node(GraphNode(node_id="n2", node_type="place", label="Alice Springs"))
        results = svc.search_nodes("alice", node_type="person")
        assert len(results) == 1
        assert results[0][0].node_type == "person"

    def test_search_namespace_scoping(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(
            GraphNode(node_id="n1", node_type="person", label="Alice"),
            namespace="ns1",
        )
        svc.add_node(
            GraphNode(node_id="n2", node_type="person", label="Alice"),
            namespace="ns2",
        )
        results = svc.search_nodes("alice", namespace="ns1")
        assert len(results) == 1
        assert results[0][0].node_id == "n1"

    def test_search_scores_ordered_descending(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(node_id="n1", node_type="person", label="Alice"))
        svc.add_node(GraphNode(
            node_id="n2", node_type="person", label="Alice",
            properties={"nickname": "alice"},
        ))
        results = svc.search_nodes("alice")
        assert len(results) == 2
        assert results[0][1] >= results[1][1]

    def test_search_case_insensitive(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(node_id="n1", node_type="Person", label="ALICE"))
        results = svc.search_nodes("alice")
        assert len(results) == 1

    def test_search_multi_term_query(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(
            node_id="n1", node_type="person", label="Alice",
            properties={"city": "Seattle"},
        ))
        svc.add_node(GraphNode(node_id="n2", node_type="person", label="Bob"))
        results = svc.search_nodes("alice seattle")
        assert len(results) >= 1
        assert results[0][0].node_id == "n1"

    def test_search_skips_embedding_text_property(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(
            node_id="n1", node_type="item", label="Widget",
            properties={"embedding_text": "secret keyword"},
        ))
        # "secret" should NOT match because embedding_text is skipped
        results = svc.search_nodes("secret")
        assert results == []

    def test_search_deterministic_tiebreak_by_node_id(self, tmp_path):
        svc = FileGraphService(base_dir=str(tmp_path))
        svc.add_node(GraphNode(node_id="b_node", node_type="t", label="match"))
        svc.add_node(GraphNode(node_id="a_node", node_type="t", label="match"))
        results = svc.search_nodes("match")
        assert len(results) == 2
        assert results[0][0].node_id == "a_node"
        assert results[1][0].node_id == "b_node"
