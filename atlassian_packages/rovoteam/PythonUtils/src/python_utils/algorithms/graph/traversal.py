"""
Graph traversal algorithms supporting heterogeneous node types.
"""
from collections import deque
from typing import Dict, Type, Iterator, Optional, Callable, Any, Set

from python_utils.common_utils.iter_helper import iter__


def bfs_traversal(
        start_node: Any,
        children_attr_map: Dict[Type, str],
        atom_types=(str,),
        visit_func: Optional[Callable[[Any], None]] = None,
        yield_nodes: bool = True
) -> Iterator:
    """
    Perform breadth-first search (BFS) traversal on a graph with heterogeneous node types.

    This function supports graphs where different node types have different attributes
    for accessing their children. For example, in a graph with nodes of type A and B,
    type A nodes might have children in 'attr1' while type B nodes have children in 'attr2'.

    Args:
        start_node: The node to start traversal from. Can be a single node or iterable of nodes.
        children_attr_map: A dictionary mapping node types to their children attribute names.
            For example: {NodeTypeA: 'children', NodeTypeB: 'child_nodes'}
        atom_types: Types to treat as atomic (non-iterable) when processing children.
            Defaults to (str,) so strings are treated as single nodes, not iterables of characters.
        visit_func: Optional function to call on each visited node. The function should
            accept a single argument (the node).
        yield_nodes: If True, yields each visited node. If False, only performs traversal
            without yielding (useful when only visit_func side effects are needed).

    Yields:
        Nodes in BFS order if yield_nodes is True.

    Examples:
        Basic usage with homogeneous node types:
        >>> class TreeNode:
        ...     def __init__(self, value, children=None):
        ...         self.value = value
        ...         self.children = children or []
        >>>
        >>> root = TreeNode(1, [TreeNode(2), TreeNode(3, [TreeNode(4)])])
        >>> nodes = list(bfs_traversal(root, {TreeNode: 'children'}))
        >>> [n.value for n in nodes]
        [1, 2, 3, 4]

        Heterogeneous node types:
        >>> class TypeA:
        ...     def __init__(self, value, attr1=None):
        ...         self.value = value
        ...         self.attr1 = attr1 or []
        >>> class TypeB:
        ...     def __init__(self, value, attr2=None):
        ...         self.value = value
        ...         self.attr2 = attr2 or []
        >>>
        >>> node_b = TypeB('b', [TypeA('c')])
        >>> root = TypeA('a', [node_b, TypeA('d')])
        >>> nodes = list(bfs_traversal(root, {TypeA: 'attr1', TypeB: 'attr2'}))
        >>> [n.value for n in nodes]
        ['a', 'b', 'd', 'c']

        With visit function:
        >>> visited = []
        >>> def visit(node):
        ...     visited.append(node.value)
        >>> list(bfs_traversal(root, {TypeA: 'attr1', TypeB: 'attr2'}, visit_func=visit))
        ['a', 'b', 'd', 'c']
        >>> visited
        ['a', 'b', 'd', 'c']

        Multiple start nodes:
        >>> root1 = TreeNode(1, [TreeNode(2)])
        >>> root2 = TreeNode(3, [TreeNode(4)])
        >>> nodes = list(bfs_traversal([root1, root2], {TreeNode: 'children'}))
        >>> [n.value for n in nodes]
        [1, 3, 2, 4]
    """
    # Track visited nodes to avoid cycles
    visited: Set[int] = set()

    # Initialize queue with start node(s)
    queue = deque()

    # Use iter__ to handle both single nodes and iterables of nodes
    for node in iter__(start_node, atom_types=atom_types):
        if node is not None:
            node_id = id(node)
            if node_id not in visited:
                queue.append(node)
                visited.add(node_id)

    # BFS traversal
    while queue:
        current_node = queue.popleft()

        # Apply visit function if provided
        if visit_func is not None:
            visit_func(current_node)

        # Yield current node if requested
        if yield_nodes:
            yield current_node

        # Get children attribute name for this node type
        children_attr = None
        for node_type, attr_name in children_attr_map.items():
            if isinstance(current_node, node_type):
                children_attr = attr_name
                break

        # Process children if attribute is found
        if children_attr is not None:
            children = getattr(current_node, children_attr, None)
            if children is not None:
                # Use iter__ to handle both single children and iterables
                for child in iter__(children, atom_types=atom_types):
                    if child is not None:
                        child_id = id(child)
                        if child_id not in visited:
                            queue.append(child)
                            visited.add(child_id)


def dfs_traversal(
        start_node: Any,
        children_attr_map: Dict[Type, str],
        atom_types=(str,),
        visit_func: Optional[Callable[[Any], None]] = None,
        yield_nodes: bool = True,
        preorder: bool = True
) -> Iterator:
    """
    Perform depth-first search (DFS) traversal on a graph with heterogeneous node types.

    Similar to bfs_traversal but uses depth-first search instead of breadth-first.

    Args:
        start_node: The node to start traversal from. Can be a single node or iterable of nodes.
        children_attr_map: A dictionary mapping node types to their children attribute names.
        atom_types: Types to treat as atomic (non-iterable) when processing children.
        visit_func: Optional function to call on each visited node.
        yield_nodes: If True, yields each visited node.
        preorder: If True, yields nodes in preorder (parent before children).
            If False, yields in postorder (children before parent).

    Yields:
        Nodes in DFS order if yield_nodes is True.

    Examples:
        >>> class TreeNode:
        ...     def __init__(self, value, children=None):
        ...         self.value = value
        ...         self.children = children or []
        >>>
        >>> root = TreeNode(1, [TreeNode(2), TreeNode(3, [TreeNode(4)])])
        >>> nodes = list(dfs_traversal(root, {TreeNode: 'children'}))
        >>> [n.value for n in nodes]
        [1, 2, 3, 4]

        Postorder traversal:
        >>> nodes = list(dfs_traversal(root, {TreeNode: 'children'}, preorder=False))
        >>> [n.value for n in nodes]
        [2, 4, 3, 1]
    """
    # Track visited nodes to avoid cycles
    visited: Set[int] = set()

    def _dfs_recursive(node):
        """Recursive helper for DFS traversal."""
        node_id = id(node)
        if node_id in visited or node is None:
            return

        visited.add(node_id)

        # Preorder: visit/yield before children
        if preorder:
            if visit_func is not None:
                visit_func(node)
            if yield_nodes:
                yield node

        # Get children attribute name for this node type
        children_attr = None
        for node_type, attr_name in children_attr_map.items():
            if isinstance(node, node_type):
                children_attr = attr_name
                break

        # Recursively process children
        if children_attr is not None:
            children = getattr(node, children_attr, None)
            if children is not None:
                for child in iter__(children, atom_types=atom_types):
                    if child is not None:
                        yield from _dfs_recursive(child)

        # Postorder: visit/yield after children
        if not preorder:
            if visit_func is not None:
                visit_func(node)
            if yield_nodes:
                yield node

    # Process start node(s)
    for node in iter__(start_node, atom_types=atom_types):
        if node is not None:
            yield from _dfs_recursive(node)
