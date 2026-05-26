"""Unit tests for expansion data types: ExpansionResult, SubgraphSpec,
GraphExpansionResult, and ExpansionRecord.
"""
import pytest

from python_utils.common_objects.workflow.common.expansion import (
    ExpansionResult,
    GraphExpansionResult,
    SubgraphSpec,
    ExpansionRecord,
)


# ---------------------------------------------------------------------------
# Helpers — lightweight mock node for SubgraphSpec tests
# ---------------------------------------------------------------------------

class _MockNode:
    """Minimal stand-in for WorkGraphNode with name and to_serializable_obj."""

    def __init__(self, name):
        self.name = name

    def to_serializable_obj(self):
        return {"name": self.name}


# ---------------------------------------------------------------------------
# ExpansionResult
# ---------------------------------------------------------------------------

class TestExpansionResult:

    def test_construction_required_fields(self):
        er = ExpansionResult(result=42, new_steps=[lambda x: x])
        assert er.result == 42
        assert len(er.new_steps) == 1

    def test_defaults(self):
        er = ExpansionResult(result="ok", new_steps=[])
        assert er.expansion_id is None
        assert er.seed is None
        assert er.reconstruct_from_seed is None
        assert er.mode == "follow"

    def test_optional_fields(self):
        fn = lambda s: [lambda x: x]  # noqa: E731
        er = ExpansionResult(
            result="r",
            new_steps=[str],
            expansion_id="exp-1",
            seed={"k": "v"},
            reconstruct_from_seed=fn,
            mode="splice",
        )
        assert er.expansion_id == "exp-1"
        assert er.seed == {"k": "v"}
        assert er.reconstruct_from_seed is fn
        assert er.mode == "splice"


# ---------------------------------------------------------------------------
# SubgraphSpec
# ---------------------------------------------------------------------------

class TestSubgraphSpec:

    def test_valid_construction(self):
        n1 = _MockNode("a")
        n2 = _MockNode("b")
        spec = SubgraphSpec(nodes=[n1, n2], entry_nodes=[n1])
        assert spec.nodes == [n1, n2]
        assert spec.entry_nodes == [n1]

    def test_entry_nodes_not_in_nodes_raises(self):
        n1 = _MockNode("a")
        n2 = _MockNode("b")
        outsider = _MockNode("c")
        with pytest.raises(ValueError, match="entry_nodes must be present in nodes"):
            SubgraphSpec(nodes=[n1, n2], entry_nodes=[outsider])

    def test_none_name_raises(self):
        n1 = _MockNode(None)
        with pytest.raises(ValueError, match="non-None names"):
            SubgraphSpec(nodes=[n1], entry_nodes=[n1])

    def test_duplicate_name_raises(self):
        n1 = _MockNode("dup")
        n2 = _MockNode("dup")
        with pytest.raises(ValueError, match="Duplicate node name"):
            SubgraphSpec(nodes=[n1, n2], entry_nodes=[n1])

    def test_to_serializable_obj(self):
        n1 = _MockNode("x")
        n2 = _MockNode("y")
        spec = SubgraphSpec(nodes=[n1, n2], entry_nodes=[n1])
        obj = spec.to_serializable_obj()
        assert obj == {
            "nodes": [{"name": "x"}, {"name": "y"}],
            "entry_node_names": ["x"],
        }

    def test_all_entry_nodes_are_also_nodes(self):
        """entry_nodes that are a subset of nodes should pass validation."""
        n1 = _MockNode("a")
        n2 = _MockNode("b")
        spec = SubgraphSpec(nodes=[n1, n2], entry_nodes=[n1, n2])
        assert len(spec.entry_nodes) == 2


# ---------------------------------------------------------------------------
# GraphExpansionResult
# ---------------------------------------------------------------------------

class TestGraphExpansionResult:

    def test_construction(self):
        n1 = _MockNode("n1")
        spec = SubgraphSpec(nodes=[n1], entry_nodes=[n1])
        ger = GraphExpansionResult(result="res", subgraph=spec)
        assert ger.result == "res"
        assert ger.subgraph is spec

    def test_defaults(self):
        n1 = _MockNode("n1")
        spec = SubgraphSpec(nodes=[n1], entry_nodes=[n1])
        ger = GraphExpansionResult(result=None, subgraph=spec)
        assert ger.expansion_id is None
        assert ger.seed is None
        assert ger.reconstruct_from_seed is None
        assert ger.attach_mode == "insert"
        assert ger.include_self is False
        assert ger.include_others is True

    def test_optional_fields(self):
        n1 = _MockNode("n1")
        spec = SubgraphSpec(nodes=[n1], entry_nodes=[n1])
        ger = GraphExpansionResult(
            result=99,
            subgraph=spec,
            expansion_id="g-1",
            seed=[1, 2],
            include_self=True,
            include_others={"n1"},
        )
        assert ger.expansion_id == "g-1"
        assert ger.seed == [1, 2]
        assert ger.include_self is True
        assert ger.include_others == {"n1"}


# ---------------------------------------------------------------------------
# ExpansionRecord
# ---------------------------------------------------------------------------

class TestExpansionRecord:

    def test_construction_required_fields(self):
        rec = ExpansionRecord(
            after_step_name="step_a",
            expansion_id="e-1",
            num_steps=3,
        )
        assert rec.after_step_name == "step_a"
        assert rec.expansion_id == "e-1"
        assert rec.num_steps == 3

    def test_defaults(self):
        rec = ExpansionRecord(
            after_step_name="s",
            expansion_id=None,
            num_steps=0,
        )
        assert rec.seed is None
        assert rec.factory_module is None
        assert rec.factory_qualname is None

    def test_optional_fields(self):
        rec = ExpansionRecord(
            after_step_name="step_b",
            expansion_id="e-2",
            num_steps=2,
            seed={"plan": [1, 2]},
            factory_module="my_module",
            factory_qualname="my_factory",
        )
        assert rec.seed == {"plan": [1, 2]}
        assert rec.factory_module == "my_module"
        assert rec.factory_qualname == "my_factory"
