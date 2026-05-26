from collections import deque
from typing import Any, Iterable, Callable, Sequence

from python_utils.algorithms.graph.node import Node
from python_utils.common_utils import get_, get__


def _resolve_children(node, get_children):
    if node is None:
        return None
    if callable(get_children):
        return get_children(node)
    elif isinstance(get_children, str):
        return get_(node, get_children)
    else:
        return get__(node, *get_children)


def _resolve_value(node, get_value):
    if node is None:
        return None
    if get_value is None:
        return node
    if callable(get_value):
        return get_value(node)
    elif isinstance(get_value, str):
        return get_(node, get_value)
    elif isinstance(get_value, Sequence):
        return get__(node, *get_value)


def bfs_traversal(
        root,
        get_children: Callable[[Any], Iterable] = None,
        process_node: Callable = None,
        get_value: Callable = None,
        return_iterator: bool = True,
):
    """
    Performs a breadth-first (level-order) traversal of a generic tree or tree-like structure,
    optionally extracting node values and applying a custom node-processing function.

    Args:
        root (Any):
            The root node or object from which to start the traversal.
        get_children (Callable[[Any], Iterable] | str | tuple, optional):
            Defines how to retrieve children from each node. Defaults to ``('next', 'children')``,
            meaning the function will try to look up attributes or callables named ``'next'`` or
            ``'children'`` via :func:`get__`.
        process_node (Callable[[Any], Any], optional):
            A function called on each node's resolved value in BFS order. If ``None``, the
            resolved value is directly returned or yielded.
        get_value (Callable[[Any], Any] | str | tuple, optional):
            Determines how to extract a "value" from each node. If ``None``, the node itself
            is used. Otherwise, this can be a string, tuple of strings, or a callable, and is
            applied to the node to get its "value."
        return_iterator (bool, optional):
            If ``True``, returns an iterator of results in BFS order. If ``False``, the function
            does not return anything and only calls ``process_node`` for side effects (if
            provided). Defaults to ``True``.

    Returns:
        Union[Iterator[Any], None]:
            - If ``return_iterator=True``, returns an iterator of the BFS results (the
              output of ``process_node`` if provided, or else the resolved node values).
            - If ``return_iterator=False``, returns ``None``, since results are not collected.

    Examples:
        # 1) BFS traversal of a simple tree structure
        >>> #         A
        >>> #       /   \\
        >>> #      B     C
        >>> #     / \\   / \\
        >>> #    D   E F   G
        >>> A = Node('A')
        >>> B = Node('B')
        >>> C = Node('C')
        >>> D = Node('D')
        >>> E = Node('E')
        >>> F = Node('F')
        >>> G = Node('G')
        >>> A.add_next(B)
        >>> A.add_next(C)
        >>> B.add_next(D)
        >>> B.add_next(E)
        >>> C.add_next(F)
        >>> C.add_next(G)
        >>> list(bfs_traversal(A, get_value='value'))
        ['A', 'B', 'C', 'D', 'E', 'F', 'G']
        >>> list(bfs_traversal(A, get_value='value', process_node=str.lower))
        ['a', 'b', 'c', 'd', 'e', 'f', 'g']

        # 2) BFS traversal of a non-binary tree
        >>> #         A
        >>> #       / | \\
        >>> #      B  C  D
        >>> #      |  /|\\  \\
        >>> #      F G H I  J
        >>> A2 = Node('A')
        >>> B2 = Node('B')
        >>> C2 = Node('C')
        >>> D2 = Node('D')
        >>> F2 = Node('F')
        >>> G2 = Node('G')
        >>> H2 = Node('H')
        >>> I2 = Node('I')
        >>> J2 = Node('J')
        >>> A2.add_next(B2)
        >>> A2.add_next(C2)
        >>> A2.add_next(D2)
        >>> B2.add_next(F2)
        >>> C2.add_next(G2)
        >>> C2.add_next(H2)
        >>> C2.add_next(I2)
        >>> D2.add_next(J2)
        >>> list(bfs_traversal(A2, get_value='value'))
        ['A', 'B', 'C', 'D', 'F', 'G', 'H', 'I', 'J']
    """
    if get_children is None:
        get_children = ('next', 'children')

    queue = deque([root])

    if return_iterator:
        def _iterator():
            while queue:
                node = queue.popleft()
                children = _resolve_children(node, get_children)
                if children:
                    queue.extend(children)
                value = _resolve_value(node, get_value)
                if process_node is None:
                    yield value
                else:
                    yield process_node(value)

        return _iterator()
    else:
        while queue:
            node = queue.popleft()
            children = _resolve_children(node, get_children)
            if children:
                queue.extend(children)
            if process_node is not None:
                process_node(_resolve_value(node, get_value))


def post_order_traversal(
        root,
        get_children: Callable[[Any], Iterable] = None,
        process_node: Callable = None,
        get_value: Callable = None,
        return_iterator: bool = True,
):
    r"""
    Performs a post-order traversal of a generic tree (or tree-like structure) using a stack,
    optionally extracting node values and applying a custom node-processing function.

    Post-order traversal means we visit all children of a node before visiting the node itself.
    This implementation uses an iterative approach (managing its own stack) to avoid Python's
    default recursion limits on deeply nested trees.

    Args:
        root (Any):
            The root node or object from which to start the traversal.
        get_children (Callable[[Any], Iterable] | str | tuple, optional):
            Defines how to retrieve children from each node. Defaults to ``('next', 'children')``,
            meaning the function will try to look up attributes or callables named ``'next'`` or
            ``'children'`` via :func:`get__`.
        process_node (Callable[[Any], Any], optional):
            A function called on each node’s resolved value in post-order. If ``None``, the
            resolved value is directly returned or yielded.
        get_value (Callable[[Any], Any] | str | tuple, optional):
            Determines how to extract a “value” from each node. If ``None``, the node itself
            is used. Otherwise, this can be a string, tuple of strings, or a callable, and is
            applied to the node to get its “value.”
        return_iterator (bool, optional):
            If ``True``, returns an iterator of results in post-order. If ``False``, the function
            does not return anything and only calls ``process_node`` for side effects (if
            provided). Defaults to ``True``.

    Returns:
        Union[Iterator[Any], None]:
            - If ``return_iterator=True``, returns an iterator of the post-order results (the
              output of ``process_node`` if provided, or else the resolved node values).
            - If ``return_iterator=False``, returns ``None``, since results are not collected.

    Notes:
        * **Post-Order Details**:
          1. The function pushes ``(root, False)`` onto an internal stack, indicating the
             root is unvisited.
          2. When popping an item ``(node, visited)``, if ``visited`` is ``False``, it re-pushes
             the node as ``(node, True)`` and then all children (marked not visited).
          3. When popping an item with ``visited=True``, the node’s children have already been
             handled, so this node is processed next (i.e., post-order).
        * **Child Retrieval**:
          The default ``get_children=('next','children')`` tries each key in sequence.
          You can supply your own callable (like ``lambda x: x.get_next()``) for custom logic.
        * **Value Extraction**:
          If ``get_value`` is a string, the function attempts to retrieve an attribute or dict key
          with that name from the node. If it's a tuple/list of strings, it tries them in order
          until one succeeds. If it's a callable, the node is passed to it directly.

    Examples:
        # 1) Post-order traversal of a simple tree structure
        >>> #         A
        >>> #       /   \
        >>> #      B     C
        >>> #     / \   / \
        >>> #    D   E F   G
        >>> A = Node('A')
        >>> B = Node('B')
        >>> C = Node('C')
        >>> D = Node('D')
        >>> E = Node('E')
        >>> F = Node('F')
        >>> G = Node('G')
        >>> A.add_next(B)
        >>> A.add_next(C)
        >>> B.add_next(D)
        >>> B.add_next(E)
        >>> C.add_next(F)
        >>> C.add_next(G)
        >>> list(post_order_traversal(A, get_value='value'))
        ['D', 'E', 'B', 'F', 'G', 'C', 'A']
        >>> list(post_order_traversal(A, get_value='value', process_node=str.lower))
        ['d', 'e', 'b', 'f', 'g', 'c', 'a']

        # 2) Post-order traversal of a non-binary tree
        >>> #         A
        >>> #       / | \
        >>> #      B  C  D
        >>> #      |  /|\  \
        >>> #      F G H I  J
        >>> A2 = Node('A')
        >>> B2 = Node('B')
        >>> C2 = Node('C')
        >>> D2 = Node('D')
        >>> F2 = Node('F')
        >>> G2 = Node('G')
        >>> H2 = Node('H')
        >>> I2 = Node('I')
        >>> J2 = Node('J')
        >>> A2.add_next(B2)  # A has children B, C, D
        >>> A2.add_next(C2)
        >>> A2.add_next(D2)
        >>> B2.add_next(F2)  # B has child F
        >>> C2.add_next(G2)  # C has children G, H, I
        >>> C2.add_next(H2)
        >>> C2.add_next(I2)
        >>> D2.add_next(J2)  # D has child J
        >>> list(post_order_traversal(A2, get_value='value'))
        ['F', 'B', 'G', 'H', 'I', 'C', 'J', 'D', 'A']
    """
    if get_children is None:
        get_children = ('next', 'children')

    stack = [(root, False)]

    def _process_not_visited(_node):
        # 1) We'll revisit this node in "post" mode, so push again with visited=True
        stack.append((_node, True))

        # 2) Push each child onto the stack to be visited first
        children = _resolve_children(_node, get_children)
        # Reverse if you want the first child processed last
        if children:
            if isinstance(children, Sequence):
                # If we want to process from left to right, we push children in reverse
                for child in reversed(children):
                    stack.append((child, False))
            else:
                # If 'children' is not a Sequence (maybe an iterator),
                # we can convert it to a list and reverse:
                for child in children:
                    stack.append((child, False))

    if return_iterator:
        def _iterator():
            while stack:
                node, visited = stack.pop()
                if not visited:
                    _process_not_visited(node)
                elif process_node is None:
                    yield _resolve_value(node, get_value)
                else:
                    yield process_node(_resolve_value(node, get_value))

        return _iterator()
    else:
        # Non-iterator mode: we do not yield or collect results;
        # we only call process_node if provided.
        while stack:
            node, visited = stack.pop()
            if not visited:
                _process_not_visited(node)
            elif process_node is not None:
                process_node(_resolve_value(node, get_value))
