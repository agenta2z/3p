# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.

from io import StringIO
from itertools import chain
from typing import Sequence, Any, List, Hashable, Type
from typing import Union, Callable

from attr import attrs, attrib

from rankevolve.src.utils.algorithms.graph.node import Node, str_all_descendants_of_nodes


def build_nodes_from_paths(
        paths: Sequence[Sequence[Any]],
        node_cls: Type[Node] = Node,
        node_list_factory: Callable[[], List] = list,
        return_all_nodes: bool = False,
        hashable: bool = True
) -> List[Node]:
    """Builds a directed acyclic graph (DAG) of `Node` objects from given paths, merging common subpaths.

    This function takes a sequence of paths, where each path is a sequence of values. It creates
    a DAG of `Node` instances such that each unique value across all paths corresponds to exactly
    one `Node`. If multiple paths share a common sequence of values at any point, that subpath
    in the DAG is reused rather than recreated. The resulting DAG may have one or multiple start
    nodes, depending on whether the paths share the initial nodes or not.

    Args:
        paths (Sequence[Sequence[Any]]): A sequence of paths, each a sequence of values.
            For example: `[["A", "B", "C"], ["A", "B", "D"], ["X", "Y"]]`.
        node_cls (Type[Node], optional):
            The class (or subclass) of `Node` to use when instantiating new nodes.
            Defaults to the base `Node` class.
        node_list_factory (Callable[[], List], optional): A callable that returns a new list-like
            container to store node connections. Defaults to the built-in `list`.
        return_all_nodes (bool, optional): If `True`, return all nodes in the DAG instead of just
            the start nodes. Defaults to `False`.
        hashable (bool): True if the values of the nodes are hashable.

    Returns:
        List[Node]: A list of start nodes in the constructed DAG. Start nodes are those with no
        predecessor nodes.

    Examples:
        >>> from typing import List
        >>> from rankevolve.src.utils.algorithms.graph.node import Node
        >>> def custom_list_factory():
        ...     return []
        ...
        >>> # Suppose we have three paths:
        >>> paths = [
        ...     ["A", "B", "C"],
        ...     ["A", "B", "D"],
        ...     ["A", "E", "F"]
        ... ]
        >>> start_nodes = build_nodes_from_paths(paths, node_list_factory=custom_list_factory)
        >>> # All paths start with "A", so there's only one start node.
        >>> len(start_nodes)
        1
        >>> start_nodes[0].value
        'A'

        >>> # From "A", there should be two branches: one going to "B" and one to "E".
        >>> [node.value for node in start_nodes[0].next]
        ['B', 'E']

        >>> # The "A -> B" segment is reused by the first two paths, so "B" is created once.
        >>> # "B" then leads to "C" and "D".
        >>> b_node = next(n for n in start_nodes[0].next if n.value == "B")
        >>> sorted(n.value for n in b_node.next)
        ['C', 'D']

        >>> # Similarly, from "A" to "E" is a separate branch, leading to "F".
        >>> e_node = next(n for n in start_nodes[0].next if n.value == "E")
        >>> [n.value for n in e_node.next]
        ['F']
    """

    if not paths:
        return []

    # List of start nodes for the entire DAG.
    if hashable:
        all_nodes: dict = {}
        def _find_node_with_value(_value) -> node_cls:
            return all_nodes.get(_value, None)
        def _add_new_node(_node: node_cls):
            all_nodes[_node.value] = _node
    else:
        all_nodes: List[node_cls] = []
        def _find_node_with_value(_value) -> node_cls:
            return  next((x for x in all_nodes if x.value == _value), None)
        def _add_new_node(_node: node_cls):
            all_nodes.append(_node)

    for path in paths:
        if not path:
            continue  # Skip empty paths

        # Start building (or merging) the path into the DAG.
        prev_node = None
        for value in path:
            current_node = _find_node_with_value(value)
            if current_node is None:
                # Create a new node since we don't have one with this value
                current_node = node_cls(value=value, node_list_factory=node_list_factory)
                _add_new_node(current_node)

            if prev_node is not None:
                # The `add_next` method will automatically skip duplicated node
                # and link `prev_node` as `current_node`'s predecessor
                prev_node.add_next(current_node, node_list_factory=node_list_factory)

            # Move forward along the path
            prev_node = current_node

    if hashable:
        if return_all_nodes:
            return list(all_nodes.values())
        else:
            start_nodes: List[node_cls] = list(filter(lambda node: not node.previous, all_nodes.values()))
            return start_nodes
    else:
        if return_all_nodes:
            return all_nodes
        else:
            start_nodes: List[node_cls] = list(filter(lambda node: not node.previous, all_nodes))
            return start_nodes



@attrs(slots=False, repr=False)
class DirectedAcyclicGraph:
    start_nodes: Sequence[Node] = attrib()
    node_cls: Type[Node] = attrib(default=Node)
    verbose_repr: bool = attrib(default=False)

    def __attrs_post_init__(self):
        # Call parent __attrs_post_init__ if it exists (for multiple inheritance support)
        super_post_init = getattr(super(), '__attrs_post_init__', None)
        if super_post_init:
            super_post_init()

        start_nodes: Union[Sequence[Node], Sequence[Sequence[Any]]] = self.start_nodes
        if len(start_nodes) > 0 and all(isinstance(n, Node) for n in start_nodes):
            # If we got a sequence of Node objects directly
            self.start_nodes = list(start_nodes)
        else:
            # Otherwise, treat input as multiple paths and build the DAG
            hashable = all(isinstance(x, Hashable) for x in chain(*start_nodes))
            self.start_nodes = build_nodes_from_paths(start_nodes, node_cls=self.node_cls, hashable=hashable)

    def __repr__(self):
        """
        Returns a string representation of the DAG.

        When verbose_repr=False (default): Simple tree visualization
        When verbose_repr=True: Full structure with degrees, adjacency lists

        Examples:
            >>> paths = [
            ...     ["A", "B", "C"],
            ...     ["A", "B", "D"],
            ...     ["A", "E", "F"]
            ... ]
            >>> dag = DirectedAcyclicGraph(paths)
            >>> print(dag)  # doctest: +NORMALIZE_WHITESPACE
            DirectedAcyclicGraph:
            A
            |-- B
            |   |-- C
            |   |-- D
            |-- E
            |   |-- F

            # Example with multiple start nodes
            >>> paths = [
            ...     ["X", "Y"],
            ...     ["Z", "W", "Y"]
            ... ]
            >>> dag = DirectedAcyclicGraph(paths)
            >>> print(dag)  # doctest: +NORMALIZE_WHITESPACE
            DirectedAcyclicGraph:
            X
            |-- Y
            Z
            |-- W
            |   |-- Y
        """
        if self.verbose_repr:
            return self.print_structure(print_output=False)
        else:
            output = StringIO()
            output.write("DirectedAcyclicGraph:\n")
            output.write(str_all_descendants_of_nodes(self.start_nodes, ascii_tree=True, indent=4))
            return output.getvalue()

    def print_structure(
        self,
        ascii_tree: bool = True,
        include_degrees: bool = True,
        include_adjacency: bool = True,
        print_output: bool = True
    ) -> str:
        """
        Print detailed DAG structure for debugging and analysis.

        Shows complete DAG information:
        1. Summary statistics (nodes, edges, convergence points)
        2. Node list with in/out degrees
        3. Tree visualization (reuses str_all_descendants pattern)
        4. Adjacency lists (forward and reverse)

        Uses str(node) for display, so child classes customize via __str__ override.

        Args:
            ascii_tree: Use ASCII tree format (|-- ) for hierarchy visualization
            include_degrees: Show in/out degree for each node
            include_adjacency: Show forward/reverse adjacency lists
            print_output: Whether to print the result (default True). Set to False
                when calling from __repr__ to avoid side effects.

        Returns:
            String representation of the graph structure

        Examples:
            >>> paths = [
            ...     ["A", "B", "C"],
            ...     ["A", "B", "D"],
            ...     ["A", "E", "F"]
            ... ]
            >>> dag = DirectedAcyclicGraph(paths)
            >>> result = dag.print_structure()  # doctest: +NORMALIZE_WHITESPACE
            DAG Structure (6 nodes, 5 edges)
            Divergence points (out-degree > 1): [0, 1]
            <BLANKLINE>
            Nodes (in-degree -> out-degree):
              [0] A (0->2)
              [1] B (1->2)
              [2] C (1->0)
              [3] D (1->0)
              [4] E (1->1)
              [5] F (1->0)
            <BLANKLINE>
            Tree View:
            A
            |-- B
            |   |-- C
            |   |-- D
            |-- E
            |   |-- F
            <BLANKLINE>
            <BLANKLINE>
            Adjacency (forward -> successors):
              [0] -> [1], [4]
              [1] -> [2], [3]
              [2] -> (leaf)
              [3] -> (leaf)
              [4] -> [5]
              [5] -> (leaf)
            <BLANKLINE>
            Adjacency (reverse <- predecessors):
              [0] <- (root)
              [1] <- [0]
              [2] <- [1]
              [3] <- [1]
              [4] <- [0]
              [5] <- [4]
            <BLANKLINE>
        """
        from typing import Dict, List, Set

        output = StringIO()

        # Collect all nodes via DFS from start_nodes
        all_nodes: List = []
        visited_ids: Set[int] = set()

        def collect_nodes(node):
            if id(node) in visited_ids:
                return
            visited_ids.add(id(node))
            all_nodes.append(node)
            for child in (node.next or []):
                collect_nodes(child)

        for start in self.start_nodes:
            collect_nodes(start)

        # Build node index map
        node_indices = {id(node): i for i, node in enumerate(all_nodes)}

        # Compute degrees
        in_degree: Dict[int, int] = {i: 0 for i in range(len(all_nodes))}
        out_degree: Dict[int, int] = {i: 0 for i in range(len(all_nodes))}
        predecessors: Dict[int, List[int]] = {i: [] for i in range(len(all_nodes))}

        for i, node in enumerate(all_nodes):
            if node.next:
                out_degree[i] = len(node.next)
                for next_node in node.next:
                    next_idx = node_indices.get(id(next_node))
                    if next_idx is not None:
                        in_degree[next_idx] += 1
                        predecessors[next_idx].append(i)

        # Stats
        total_edges = sum(out_degree.values())
        convergence_points = [i for i, deg in in_degree.items() if deg > 1]
        divergence_points = [i for i, deg in out_degree.items() if deg > 1]

        # Header
        output.write(f"DAG Structure ({len(all_nodes)} nodes, {total_edges} edges)\n")
        if convergence_points:
            output.write(f"Convergence points (in-degree > 1): {convergence_points}\n")
        if divergence_points:
            output.write(f"Divergence points (out-degree > 1): {divergence_points}\n")
        output.write("\n")

        # Node list with degrees
        if include_degrees:
            output.write("Nodes (in-degree -> out-degree):\n")
            for i, node in enumerate(all_nodes):
                degree_info = f"({in_degree[i]}->{out_degree[i]})"
                convergence_marker = " *" if in_degree[i] > 1 else ""
                # Uses str(node) - child classes customize via __str__
                output.write(f"  [{i}] {str(node)} {degree_info}{convergence_marker}\n")
            output.write("\n")

        # Tree visualization (reuse existing method)
        output.write("Tree View:\n")
        output.write(str_all_descendants_of_nodes(self.start_nodes, ascii_tree=ascii_tree))
        output.write("\n\n")

        # Adjacency lists
        if include_adjacency:
            output.write("Adjacency (forward -> successors):\n")
            for i, node in enumerate(all_nodes):
                successors = [node_indices.get(id(n), "?") for n in (node.next or [])]
                succ_str = ", ".join(f"[{s}]" for s in successors) if successors else "(leaf)"
                output.write(f"  [{i}] -> {succ_str}\n")

            output.write("\nAdjacency (reverse <- predecessors):\n")
            for i in range(len(all_nodes)):
                pred = predecessors[i]
                pred_str = ", ".join(f"[{p}]" for p in pred) if pred else "(root)"
                convergence_marker = " *" if len(pred) > 1 else ""
                output.write(f"  [{i}] <- {pred_str}{convergence_marker}\n")

        result = output.getvalue()
        if print_output:
            print(result)
        return result