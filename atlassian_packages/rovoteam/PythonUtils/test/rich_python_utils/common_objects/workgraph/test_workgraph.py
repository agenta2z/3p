"""
Test WorkGraph and WorkGraphNode with Continue flag across various DAG structures.

All nodes in these tests return Continue (normal execution flow).
Tests verify that complex graph structures produce expected final results.

Structures tested:
- Linear chains (A -> B -> C)
- Forks (A -> [B, C])
- Diamonds (A -> [B, C] -> D)
- Multiple start nodes
- Deep nested structures
- Wide structures (many siblings)
- Complex multi-layer DAGs
- Edge cases (empty nodes, single values, etc.)
"""
import pytest

from python_utils.common_objects.workflow.workgraph import WorkGraphNode, WorkGraph
from python_utils.common_objects.workflow.common.result_pass_down_mode import ResultPassDownMode


class TestLinearChain:
    """Test linear chain structures (A -> B -> C -> ...)."""

    def test_two_node_chain(self):
        """A -> B: Simple two-node chain."""
        execution_order = []

        node_a = WorkGraphNode(
            name="A",
            value=lambda x: (execution_order.append("A"), x + 1)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda x: (execution_order.append("B"), x * 2)[1],
        )

        node_a.add_next(node_b)
        result = node_a.run(5)

        assert execution_order == ["A", "B"]
        # A: 5+1=6, B: 6*2=12
        assert result == 12

    def test_three_node_chain(self):
        """A -> B -> C: Three-node chain."""
        execution_order = []

        node_a = WorkGraphNode(
            name="A",
            value=lambda x: (execution_order.append("A"), x + 1)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda x: (execution_order.append("B"), x * 2)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_c = WorkGraphNode(
            name="C",
            value=lambda x: (execution_order.append("C"), x + 10)[1],
        )

        node_a.add_next(node_b)
        node_b.add_next(node_c)
        result = node_a.run(5)

        assert execution_order == ["A", "B", "C"]
        # A: 5+1=6, B: 6*2=12, C: 12+10=22
        assert result == 22

    def test_long_chain(self):
        """A -> B -> C -> D -> E: Five-node chain."""
        execution_order = []

        def make_node(name, operation):
            return WorkGraphNode(
                name=name,
                value=lambda x, n=name, op=operation: (execution_order.append(n), op(x))[1],
                result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
            )

        node_a = make_node("A", lambda x: x + 1)
        node_b = make_node("B", lambda x: x * 2)
        node_c = make_node("C", lambda x: x + 3)
        node_d = make_node("D", lambda x: x * 2)
        node_e = WorkGraphNode(
            name="E",
            value=lambda x: (execution_order.append("E"), x - 5)[1],
        )

        node_a.add_next(node_b)
        node_b.add_next(node_c)
        node_c.add_next(node_d)
        node_d.add_next(node_e)

        result = node_a.run(0)

        assert execution_order == ["A", "B", "C", "D", "E"]
        # A: 0+1=1, B: 1*2=2, C: 2+3=5, D: 5*2=10, E: 10-5=5
        assert result == 5


class TestForkStructure:
    """Test fork structures (A -> [B, C, ...])."""

    def test_simple_fork_two_children(self):
        """A -> [B, C]: Fork with two children."""
        execution_order = []

        node_a = WorkGraphNode(
            name="A",
            value=lambda x: (execution_order.append("A"), x)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda x: (execution_order.append("B"), x + 1)[1],
        )
        node_c = WorkGraphNode(
            name="C",
            value=lambda x: (execution_order.append("C"), x + 2)[1],
        )

        node_a.add_next(node_b)
        node_a.add_next(node_c)

        result = node_a.run(10)

        assert execution_order == ["A", "B", "C"]
        # B: 10+1=11, C: 10+2=12, merged as tuple
        assert result == (11, 12)

    def test_fork_three_children(self):
        """A -> [B, C, D]: Fork with three children."""
        execution_order = []

        node_a = WorkGraphNode(
            name="A",
            value=lambda x: (execution_order.append("A"), x * 2)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda x: (execution_order.append("B"), x + 1)[1],
        )
        node_c = WorkGraphNode(
            name="C",
            value=lambda x: (execution_order.append("C"), x + 2)[1],
        )
        node_d = WorkGraphNode(
            name="D",
            value=lambda x: (execution_order.append("D"), x + 3)[1],
        )

        node_a.add_next(node_b)
        node_a.add_next(node_c)
        node_a.add_next(node_d)

        result = node_a.run(5)

        assert execution_order == ["A", "B", "C", "D"]
        # A: 5*2=10, B: 10+1=11, C: 10+2=12, D: 10+3=13
        assert result == (11, 12, 13)

    def test_fork_with_different_result_types(self):
        """Fork children returning different types."""
        node_a = WorkGraphNode(
            name="A",
            value=lambda x: x,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda x: f"string_{x}",
        )
        node_c = WorkGraphNode(
            name="C",
            value=lambda x: {"value": x},
        )
        node_d = WorkGraphNode(
            name="D",
            value=lambda x: [x, x * 2],
        )

        node_a.add_next(node_b)
        node_a.add_next(node_c)
        node_a.add_next(node_d)

        result = node_a.run(5)

        assert result == ("string_5", {"value": 5}, [5, 10])


class TestDiamondStructure:
    """Test diamond structures (A -> [B, C] -> D).

    Note: In diamond structures, when the first sibling (B) calls the multi-parent
    node (D), D queues the input and returns None (waiting for C). This None gets
    captured in B's downstream_results. When C calls D, D has all inputs and executes.
    The final merged result from A includes both the None from B's path and D's actual
    result from C's path.
    """

    def test_simple_diamond(self):
        """
        A -> [B, C] -> D
        D sums inputs from B and C.
        """
        execution_order = []

        node_a = WorkGraphNode(
            name="A",
            value=lambda x: (execution_order.append("A"), x)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda x: (execution_order.append("B"), x + 1)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_c = WorkGraphNode(
            name="C",
            value=lambda x: (execution_order.append("C"), x + 2)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_d = WorkGraphNode(
            name="D",
            value=lambda *args: (execution_order.append("D"), sum(args))[1],
        )

        node_a.add_next(node_b)
        node_a.add_next(node_c)
        node_b.add_next(node_d)
        node_c.add_next(node_d)
        node_d.previous = [node_b, node_c]

        result = node_a.run(10)

        assert "A" in execution_order
        assert "B" in execution_order
        assert "C" in execution_order
        assert "D" in execution_order
        # A: 10, B: 10+1=11, C: 10+2=12, D: 11+12=23
        # Result includes None from B's path (D was waiting) and 23 from C's path
        assert "23" in str(result)

    def test_diamond_with_multiplication(self):
        """
        A -> [B, C] -> D
        D multiplies inputs from B and C.
        """
        execution_order = []

        node_a = WorkGraphNode(
            name="A",
            value=lambda x: (execution_order.append("A"), x + 1)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda x: (execution_order.append("B"), x * 2)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_c = WorkGraphNode(
            name="C",
            value=lambda x: (execution_order.append("C"), x * 3)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_d = WorkGraphNode(
            name="D",
            value=lambda *args: (execution_order.append("D"), args[0] * args[1] if len(args) >= 2 else args[0])[1],
        )

        node_a.add_next(node_b)
        node_a.add_next(node_c)
        node_b.add_next(node_d)
        node_c.add_next(node_d)
        node_d.previous = [node_b, node_c]

        result = node_a.run(2)

        assert "D" in execution_order
        # A: 2+1=3, B: 3*2=6, C: 3*3=9, D: 6*9=54
        assert "54" in str(result)

    def test_diamond_three_branches(self):
        """
        A -> [B, C, D] -> E
        E sums all three inputs.
        """
        execution_order = []

        node_a = WorkGraphNode(
            name="A",
            value=lambda x: (execution_order.append("A"), x)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda x: (execution_order.append("B"), x + 1)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_c = WorkGraphNode(
            name="C",
            value=lambda x: (execution_order.append("C"), x + 2)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_d = WorkGraphNode(
            name="D",
            value=lambda x: (execution_order.append("D"), x + 3)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_e = WorkGraphNode(
            name="E",
            value=lambda *args: (execution_order.append("E"), sum(args))[1],
        )

        node_a.add_next(node_b)
        node_a.add_next(node_c)
        node_a.add_next(node_d)
        node_b.add_next(node_e)
        node_c.add_next(node_e)
        node_d.add_next(node_e)
        node_e.previous = [node_b, node_c, node_d]

        result = node_a.run(0)

        assert "E" in execution_order
        # A: 0, B: 0+1=1, C: 0+2=2, D: 0+3=3, E: 1+2+3=6
        assert "6" in str(result)


class TestNestedDiamond:
    """Test nested diamond structures.

    Note: Same as TestDiamondStructure, multi-parent nodes return None when waiting
    for more inputs, which gets included in the merged results.
    """

    def test_double_diamond(self):
        r"""
             A
            / \
           B   C
            \ /
             D
            / \
           E   F
            \ /
             G
        """
        execution_order = []

        node_a = WorkGraphNode(
            name="A",
            value=lambda x: (execution_order.append("A"), x)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda x: (execution_order.append("B"), x + 1)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_c = WorkGraphNode(
            name="C",
            value=lambda x: (execution_order.append("C"), x + 2)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_d = WorkGraphNode(
            name="D",
            value=lambda *args: (execution_order.append("D"), sum(args))[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_e = WorkGraphNode(
            name="E",
            value=lambda x: (execution_order.append("E"), x * 2)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_f = WorkGraphNode(
            name="F",
            value=lambda x: (execution_order.append("F"), x * 3)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_g = WorkGraphNode(
            name="G",
            value=lambda *args: (execution_order.append("G"), sum(args))[1],
        )

        # First diamond: A -> [B, C] -> D
        node_a.add_next(node_b)
        node_a.add_next(node_c)
        node_b.add_next(node_d)
        node_c.add_next(node_d)
        node_d.previous = [node_b, node_c]

        # Second diamond: D -> [E, F] -> G
        node_d.add_next(node_e)
        node_d.add_next(node_f)
        node_e.add_next(node_g)
        node_f.add_next(node_g)
        node_g.previous = [node_e, node_f]

        result = node_a.run(0)

        assert "G" in execution_order
        # A: 0, B: 1, C: 2, D: sum(1,2)=3
        # D passes (3, 2) to E and F (ResultAsFirstArg keeps trailing args)
        # E: 3*2=6, F: 3*3=9
        # E passes (6, 2) to G, F passes (9, 2) to G
        # G merges all: sum([6, 2, 9, 2]) = 19
        assert "19" in str(result)

    def test_diamond_with_chain_branches(self):
        r"""
             A
            / \
           B   C
           |   |
           B2  C2
            \ /
             D
        """
        execution_order = []

        node_a = WorkGraphNode(
            name="A",
            value=lambda x: (execution_order.append("A"), x)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda x: (execution_order.append("B"), x + 1)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_b2 = WorkGraphNode(
            name="B2",
            value=lambda x: (execution_order.append("B2"), x * 2)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_c = WorkGraphNode(
            name="C",
            value=lambda x: (execution_order.append("C"), x + 2)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_c2 = WorkGraphNode(
            name="C2",
            value=lambda x: (execution_order.append("C2"), x * 3)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_d = WorkGraphNode(
            name="D",
            value=lambda *args: (execution_order.append("D"), sum(args))[1],
        )

        node_a.add_next(node_b)
        node_a.add_next(node_c)
        node_b.add_next(node_b2)
        node_c.add_next(node_c2)
        node_b2.add_next(node_d)
        node_c2.add_next(node_d)
        node_d.previous = [node_b2, node_c2]

        result = node_a.run(1)

        assert "D" in execution_order
        # A: 1, B: 1+1=2, B2: 2*2=4, C: 1+2=3, C2: 3*3=9, D: 4+9=13
        assert "13" in str(result)


class TestMultipleStartNodes:
    """Test WorkGraph with multiple start nodes."""

    def test_two_independent_start_nodes(self):
        """Two independent start nodes with no connection."""
        execution_order = []

        node_a = WorkGraphNode(
            name="A",
            value=lambda x: (execution_order.append("A"), x + 1)[1],
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda x: (execution_order.append("B"), x + 2)[1],
        )

        graph = WorkGraph(start_nodes=[node_a, node_b])
        result = graph.run(10)

        assert "A" in execution_order
        assert "B" in execution_order
        # Results are filtered for None in WorkGraph._post_process
        # A: 10+1=11, B: 10+2=12
        assert result == (11, 12)

    def test_three_start_nodes_converging(self):
        """
        [A, B, C] -> D
        Three start nodes converge to one node.
        """
        execution_order = []

        node_a = WorkGraphNode(
            name="A",
            value=lambda x: (execution_order.append("A"), x + 1)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda x: (execution_order.append("B"), x + 2)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_c = WorkGraphNode(
            name="C",
            value=lambda x: (execution_order.append("C"), x + 3)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_d = WorkGraphNode(
            name="D",
            value=lambda *args: (execution_order.append("D"), sum(args))[1],
        )

        node_a.add_next(node_d)
        node_b.add_next(node_d)
        node_c.add_next(node_d)
        node_d.previous = [node_a, node_b, node_c]

        graph = WorkGraph(start_nodes=[node_a, node_b, node_c])
        result = graph.run(0)

        assert "D" in execution_order
        # A: 0+1=1, B: 0+2=2, C: 0+3=3, D: 1+2+3=6
        assert "6" in str(result)

    def test_start_nodes_with_separate_subgraphs(self):
        """
        A -> B (subgraph 1)
        C -> D (subgraph 2)
        Two independent subgraphs.
        """
        execution_order = []

        node_a = WorkGraphNode(
            name="A",
            value=lambda x: (execution_order.append("A"), x + 1)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda x: (execution_order.append("B"), x * 2)[1],
        )
        node_c = WorkGraphNode(
            name="C",
            value=lambda x: (execution_order.append("C"), x + 10)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_d = WorkGraphNode(
            name="D",
            value=lambda x: (execution_order.append("D"), x * 3)[1],
        )

        node_a.add_next(node_b)
        node_c.add_next(node_d)

        graph = WorkGraph(start_nodes=[node_a, node_c])
        result = graph.run(5)

        assert execution_order == ["A", "B", "C", "D"]
        # A: 5+1=6, B: 6*2=12, C: 5+10=15, D: 15*3=45
        assert result == (12, 45)


class TestComplexDAG:
    """Test complex DAG structures."""

    def test_tree_structure(self):
        """
            A
           /|\
          B C D
         /|   |\
        E F   G H
        """
        execution_order = []

        def make_node(name, op, pass_down=False):
            return WorkGraphNode(
                name=name,
                value=lambda x, n=name, o=op: (execution_order.append(n), o(x))[1],
                result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg if pass_down else ResultPassDownMode.NoPassDown
            )

        node_a = make_node("A", lambda x: x, pass_down=True)
        node_b = make_node("B", lambda x: x + 1, pass_down=True)
        node_c = make_node("C", lambda x: x + 2)
        node_d = make_node("D", lambda x: x + 3, pass_down=True)
        node_e = make_node("E", lambda x: x * 2)
        node_f = make_node("F", lambda x: x * 3)
        node_g = make_node("G", lambda x: x * 4)
        node_h = make_node("H", lambda x: x * 5)

        node_a.add_next(node_b)
        node_a.add_next(node_c)
        node_a.add_next(node_d)
        node_b.add_next(node_e)
        node_b.add_next(node_f)
        node_d.add_next(node_g)
        node_d.add_next(node_h)

        result = node_a.run(1)

        # All nodes should execute
        assert len(execution_order) == 8
        # Check leaf node results are in the final result
        # B branch: E: (1+1)*2=4, F: (1+1)*3=6 -> (4, 6)
        # C: 1+2=3
        # D branch: G: (1+3)*4=16, H: (1+3)*5=20 -> (16, 20)
        # Final: ((4, 6), 3, (16, 20))
        assert "4" in str(result) and "6" in str(result)
        assert "3" in str(result)
        assert "16" in str(result) and "20" in str(result)

    def test_complex_multi_diamond(self):
        r"""
              A
             /|\
            B C D
            |X| |
            E F G
             \|/
              H
        Where E receives from B and C, F receives from C, G receives from D.
        """
        execution_order = []

        node_a = WorkGraphNode(
            name="A",
            value=lambda x: (execution_order.append("A"), x)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda x: (execution_order.append("B"), x + 1)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_c = WorkGraphNode(
            name="C",
            value=lambda x: (execution_order.append("C"), x + 2)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_d = WorkGraphNode(
            name="D",
            value=lambda x: (execution_order.append("D"), x + 3)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_e = WorkGraphNode(
            name="E",
            value=lambda *args: (execution_order.append("E"), sum(args))[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_f = WorkGraphNode(
            name="F",
            value=lambda x: (execution_order.append("F"), x * 2)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_g = WorkGraphNode(
            name="G",
            value=lambda x: (execution_order.append("G"), x * 3)[1],
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_h = WorkGraphNode(
            name="H",
            value=lambda *args: (execution_order.append("H"), sum(args))[1],
        )

        # A -> [B, C, D]
        node_a.add_next(node_b)
        node_a.add_next(node_c)
        node_a.add_next(node_d)

        # B -> E, C -> E (E has two parents)
        node_b.add_next(node_e)
        node_c.add_next(node_e)
        node_e.previous = [node_b, node_c]

        # C -> F (F has one parent)
        node_c.add_next(node_f)

        # D -> G (G has one parent)
        node_d.add_next(node_g)

        # E, F, G -> H (H has three parents)
        node_e.add_next(node_h)
        node_f.add_next(node_h)
        node_g.add_next(node_h)
        node_h.previous = [node_e, node_f, node_g]

        result = node_a.run(0)

        assert "H" in execution_order
        # A: 0, B: 1, C: 2, D: 3
        # E: sum(1,2)=3, F: 2*2=4, G: 3*3=9
        # E passes (3, 2) to H (trailing arg from C), F passes (4,), G passes (9,)
        # H merges inputs: sum([3, 2, 4, 9]) = 18
        # Result may include None values from multi-parent wait paths
        assert "18" in str(result)


class TestEdgeCases:
    """Test edge cases and special scenarios."""

    def test_single_node(self):
        """Single node with no children."""
        node = WorkGraphNode(
            name="A",
            value=lambda x: x * 2,
        )

        result = node.run(5)
        assert result == 10

    def test_node_returning_none(self):
        """Node explicitly returning None."""
        node_a = WorkGraphNode(
            name="A",
            value=lambda x: None,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda x: x if x is not None else "default",
        )

        node_a.add_next(node_b)
        result = node_a.run(5)

        assert result == "default"

    def test_node_returning_empty_tuple(self):
        """Node returning empty tuple."""
        node = WorkGraphNode(
            name="A",
            value=lambda x: (),
        )

        result = node.run(5)
        # Empty tuple is unpacked to... depends on unpack_single_result
        assert result == ()

    def test_node_returning_single_element_tuple(self):
        """Node returning single-element tuple (should be unpacked)."""
        node = WorkGraphNode(
            name="A",
            value=lambda x: (x * 2,),
            unpack_single_result=True
        )

        result = node.run(5)
        # Single element tuple should be unpacked
        assert result == 10

    def test_node_returning_single_element_list(self):
        """Node returning single-element list (should be unpacked)."""
        node = WorkGraphNode(
            name="A",
            value=lambda x: [x * 2],
            unpack_single_result=True
        )

        result = node.run(5)
        # Single element list should be unpacked
        assert result == 10

    def test_no_pass_down_mode(self):
        """Nodes with NoPassDown mode don't pass results."""
        execution_order = []

        node_a = WorkGraphNode(
            name="A",
            value=lambda x: (execution_order.append("A"), x + 100)[1],
            result_pass_down_mode=ResultPassDownMode.NoPassDown
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda x: (execution_order.append("B"), x + 1)[1],
        )

        node_a.add_next(node_b)
        result = node_a.run(5)

        assert execution_order == ["A", "B"]
        # B receives original args (5), not A's result (105)
        # So B computes 5+1=6
        assert result == 6

    def test_result_as_leading_args_mode(self):
        """Test ResultAsLeadingArgs mode with tuple result."""
        node_a = WorkGraphNode(
            name="A",
            value=lambda x: (x, x + 1, x + 2),
            result_pass_down_mode=ResultPassDownMode.ResultAsLeadingArgs
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda *args: sum(args),
        )

        node_a.add_next(node_b)
        result = node_a.run(1)

        # A returns (1, 2, 3), B receives these as leading args plus original (1)
        # B: sum(1, 2, 3, 1) = 7
        assert result == 7

    def test_graph_rerun_produces_same_result(self):
        """Running the same graph twice produces consistent results."""
        node_a = WorkGraphNode(
            name="A",
            value=lambda x: x + 1,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda x: x * 2,
        )

        node_a.add_next(node_b)

        result1 = node_a.run(5)
        result2 = node_a.run(5)

        assert result1 == result2 == 12


class TestResultMerging:
    """Test result merging behavior in various scenarios."""

    def test_merge_two_results(self):
        """Two sibling results are merged as tuple."""
        node_a = WorkGraphNode(
            name="A",
            value=lambda x: x,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda x: "B_result",
        )
        node_c = WorkGraphNode(
            name="C",
            value=lambda x: "C_result",
        )

        node_a.add_next(node_b)
        node_a.add_next(node_c)

        result = node_a.run(0)
        assert result == ("B_result", "C_result")

    def test_merge_nested_tuples(self):
        """Nested fork results are flattened and merged."""
        node_a = WorkGraphNode(
            name="A",
            value=lambda x: x,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda x: x,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_c = WorkGraphNode(
            name="C",
            value=lambda x: x,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_d = WorkGraphNode(
            name="D",
            value=lambda x: "D",
        )
        node_e = WorkGraphNode(
            name="E",
            value=lambda x: "E",
        )
        node_f = WorkGraphNode(
            name="F",
            value=lambda x: "F",
        )

        # A -> [B, C]
        # B -> [D, E]
        # C -> F
        node_a.add_next(node_b)
        node_a.add_next(node_c)
        node_b.add_next(node_d)
        node_b.add_next(node_e)
        node_c.add_next(node_f)

        result = node_a.run(0)

        # B's result: (D, E), C's result: F
        # _merge_downstream_results flattens nested results
        # All leaf results should be present
        assert "D" in str(result)
        assert "E" in str(result)
        assert "F" in str(result)

    def test_single_child_no_tuple_wrapping(self):
        """Single child result is not wrapped in tuple."""
        node_a = WorkGraphNode(
            name="A",
            value=lambda x: x,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda x: "only_child",
        )

        node_a.add_next(node_b)
        result = node_a.run(0)

        assert result == "only_child"


class TestWorkGraphReuse:
    """Test that WorkGraph can be reused multiple times."""

    def test_workgraph_multiple_runs(self):
        """WorkGraph can be run multiple times with different inputs."""
        node_a = WorkGraphNode(
            name="A",
            value=lambda x: x * 2,
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda x: x + 1,
        )

        node_a.add_next(node_b)
        graph = WorkGraph(start_nodes=[node_a])

        result1 = graph.run(5)
        result2 = graph.run(10)
        result3 = graph.run(0)

        # 5*2+1=11, 10*2+1=21, 0*2+1=1
        # WorkGraph._post_process filters None and unpacks single elements
        assert "11" in str(result1)
        assert "21" in str(result2)
        assert "1" in str(result3)

    def test_diamond_reuse_with_queue_clearing(self):
        """Diamond structure works correctly on multiple runs (queue clearing)."""
        run_count = [0]

        def make_value(name, op):
            def fn(x):
                run_count[0] += 1
                return op(x)
            return fn

        node_a = WorkGraphNode(
            name="A",
            value=make_value("A", lambda x: x),
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_b = WorkGraphNode(
            name="B",
            value=make_value("B", lambda x: x + 1),
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_c = WorkGraphNode(
            name="C",
            value=make_value("C", lambda x: x + 2),
            result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        )
        node_d = WorkGraphNode(
            name="D",
            value=lambda *args: sum(args),
        )

        node_a.add_next(node_b)
        node_a.add_next(node_c)
        node_b.add_next(node_d)
        node_c.add_next(node_d)
        node_d.previous = [node_b, node_c]

        graph = WorkGraph(start_nodes=[node_a])

        # First run
        run_count[0] = 0
        result1 = graph.run(0)
        first_run_count = run_count[0]

        # Second run
        run_count[0] = 0
        result2 = graph.run(10)
        second_run_count = run_count[0]

        # 0: B=1, C=2, D=3
        # 10: B=11, C=12, D=23
        assert "3" in str(result1)
        assert "23" in str(result2)

        # Each run should execute A, B, C (D uses lambda, not tracked)
        assert first_run_count == 3
        assert second_run_count == 3


class TestKwargsPassDown:
    """Test passing results via kwargs (string mode)."""

    def test_pass_result_as_kwarg(self):
        """Pass result to downstream as named kwarg."""
        node_a = WorkGraphNode(
            name="A",
            value=lambda x: x * 2,
            result_pass_down_mode="upstream_result"  # String mode
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda x, upstream_result=None: f"got_{upstream_result}",
        )

        node_a.add_next(node_b)
        result = node_a.run(5)

        assert result == "got_10"

    def test_pass_result_as_kwarg_with_existing_kwargs(self):
        """Kwarg mode overwrites existing kwarg."""
        node_a = WorkGraphNode(
            name="A",
            value=lambda x: "new_value",
            result_pass_down_mode="data"
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda data="default": f"received_{data}",
        )

        node_a.add_next(node_b)
        result = node_a.run(0)

        assert result == "received_new_value"


class TestCallablePassDownMode:
    """Test callable pass-down mode for custom result handling."""

    def test_callable_mode_custom_merge(self):
        """Callable mode allows custom result merging."""
        def custom_merger(result, *args, **kwargs):
            # Put result in a special key
            return args, {**kwargs, "custom_data": {"result": result, "extra": "info"}}

        node_a = WorkGraphNode(
            name="A",
            value=lambda x: x * 3,
            result_pass_down_mode=custom_merger
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda x, custom_data=None: custom_data["result"] + 10 if custom_data else 0,
        )

        node_a.add_next(node_b)
        result = node_a.run(5)

        # A: 5*3=15, custom_merger puts in custom_data, B: 15+10=25
        assert result == 25

    def test_callable_mode_accumulate_results(self):
        """Callable mode can accumulate results across nodes."""
        def accumulator(result, *args, **kwargs):
            history = kwargs.get("history", [])
            return args, {**kwargs, "history": history + [result]}

        node_a = WorkGraphNode(
            name="A",
            value=lambda x: f"A_{x}",
            result_pass_down_mode=accumulator
        )
        node_b = WorkGraphNode(
            name="B",
            value=lambda x, history=None: f"B_with_history_{len(history or [])}",
            result_pass_down_mode=accumulator
        )
        node_c = WorkGraphNode(
            name="C",
            value=lambda x, history=None: history,
        )

        node_a.add_next(node_b)
        node_b.add_next(node_c)
        result = node_a.run(1)

        # History should contain A's and B's results
        assert result == ["A_1", "B_with_history_1"]


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
