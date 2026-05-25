# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict

from collections import deque
from io import StringIO
from queue import Queue
from typing import Any, Callable, List, Optional, Union

from attr import attrs, attrib


def _make_list(
    _x: object,
    list_factory: Union[type, Callable] = list,
) -> list:
    """Wrap a single value into a list-like container using list_factory.

    Handles the common cases needed by Node:
    - If _x is already the right type, return as-is
    - If _x is iterable (but not a string), convert via list_factory
    - Otherwise wrap _x in a new container from list_factory
    """
    if _x is None:
        container = list_factory()
        container.append(_x)
        return container

    if isinstance(list_factory, type) and isinstance(_x, list_factory):
        return _x

    # For non-string iterables, convert directly
    if not isinstance(_x, str):
        try:
            iter(_x)
            return list_factory(_x)
        except TypeError:
            pass

    # Wrap single value
    container = list_factory()
    container.append(_x)
    return container


@attrs(slots=False, eq=False, hash=False)
class Node:
    """A node in a doubly-linked structure that can maintain multiple predecessors and successors.

    This class allows creating nodes that can link to multiple next and previous nodes.
    A node can be initialized with:
    - A single `Node` or a list of `Node` objects as either `next` or `previous`.
    - `None` as `next` or `previous`, indicating no successors or predecessors respectively.

    By default, `value` is `None`, but it can hold any Python object. You can also customize the
    list-like container used for storing predecessor and successor nodes via the `node_list_factory`
    parameter.

    Attributes:
        value: The value associated with this `Node`.
        next: A `Node`, a list of `Node` objects, or `None`, representing successor nodes.
        previous: A `Node`, a list of `Node` objects, or `None`, representing predecessor nodes.
    """

    value: Any = attrib(default=None)
    next: Union['Node', List['Node'], Callable] = attrib(default=None)
    previous: Union['Node', List['Node'], Callable] = attrib(default=None)

    # region temporary attributes for init
    _node_list_factory: Callable[[], List] = attrib(
        default=list,
        repr=False,
        init=True
    )
    # endregion

    def __attrs_post_init__(self) -> None:
        # Call parent __attrs_post_init__ if it exists (for multiple inheritance support)
        super_post_init = getattr(super(), '__attrs_post_init__', None)
        if super_post_init:
            super_post_init()

        if isinstance(self.next, Node):
            self.next = _make_list(self.next, list_factory=self._node_list_factory)
        elif not (self.next is None or isinstance(self.next, List) or callable(self.next)):
            raise ValueError(
                "`next` must be None, a Node, or a list of Nodes, or a callable that generates next Nodes.")

        if isinstance(self.previous, Node):
            self.previous = _make_list(self.previous, list_factory=self._node_list_factory)
        elif not (self.previous is None or isinstance(self.previous, List) or callable(self.previous)):
            raise ValueError(
                "`previous` must be None, a Node, or a list of Nodes, or a callable that generates previous Nodes.")

        self._node_list_factory = None

    def add_next(self, next_value_or_node: object, node_list_factory: Callable[[], List] = list) -> None:
        """Adds a successor node to this node.

        If `next_value_or_node` is not a `Node`, a new `Node` will be created
        with this node as its predecessor. Mutual linking is maintained so that
        the newly created or added node also references this node as a predecessor.

        Args:
            next_value_or_node: A `Node` object or any value. If it's not a `Node`,
                a new `Node` will be created for it.
            node_list_factory: A callable returning a new list-like container for nodes if needed.
        """
        if callable(self.next):
            raise ValueError("'next' is a predefined callable")

        if isinstance(next_value_or_node, Node):
            next_node = next_value_or_node
            if self.next is not None and next_node in self.next:
                return
            if next_node.previous is None:
                next_node.previous = node_list_factory()
            next_node.previous.append(self)
        else:
            next_node = Node(next_value_or_node, None, self, node_list_factory)

        if self.next is None:
            self.next = node_list_factory()
        self.next.append(next_node)
        self._post_adding_next_process(next_node)

    def _post_adding_next_process(self, next_node: 'Node') -> None:
        """Hook method called after a next node has been added.

        Subclasses can override this method to perform custom post-processing.
        """
        pass

    def add_previous(self, previous_value_or_node: object, node_list_factory: Callable[[], List] = list) -> None:
        """Adds a predecessor node to this node.

        If `previous_value_or_node` is not a `Node`, a new `Node` will be created
        with this node as its successor. Mutual linking is maintained so that
        the newly created or added node also references this node as a successor.

        Args:
            previous_value_or_node: A `Node` object or any value. If it's not a `Node`,
                a new `Node` will be created for it.
            node_list_factory: A callable returning a new list-like container for nodes if needed.
        """
        if callable(self.previous):
            raise ValueError("'previous' is a predefined callable")

        if isinstance(previous_value_or_node, Node):
            previous_node = previous_value_or_node
            if self.previous is not None and previous_node in self.previous:
                return
            if previous_node.next is None:
                previous_node.next = node_list_factory()
            previous_node.next.append(self)
        else:
            previous_node = Node(previous_value_or_node, self, None, node_list_factory)

        if self.previous is None:
            self.previous = node_list_factory()
            self.previous.append(previous_node)
        else:
            self.previous.append(previous_node)

        self._post_adding_previous_process(previous_node)

    def _post_adding_previous_process(self, previous_node: 'Node') -> None:
        """Hook method called after a previous node has been added.

        Subclasses can override this method to perform custom post-processing.
        """
        pass

    def get_next(self) -> Optional[List['Node']]:
        return self.next(self.value) if callable(self.next) else self.next

    def get_previous(self) -> Optional[List['Node']]:
        return self.previous(self.value) if callable(self.previous) else self.previous

    def bfs(
        self,
        target_value: object,
        is_equal_value: Callable | None = None,
        return_path: bool = False,
    ) -> bool | list['Node'] | None:
        """Performs a breadth-first search (BFS) starting from this node.

        Args:
            target_value: The value we want to find in the graph.
            is_equal_value: A custom comparison function that takes
                (current_value, target_value) and returns a bool.
            return_path: If True, returns visited nodes up to the match.

        Returns:
            If return_path is False: True if found, else False.
            If return_path is True: list of visited nodes up to match, or None.
        """
        visited: set[int] = set()

        if return_path:
            queue: deque[tuple[Node, list[Node]]] = deque([(self, [self])])
            while queue:
                current, _path = queue.popleft()

                is_target_value = (
                    current.value == target_value
                    if is_equal_value is None
                    else is_equal_value(current.value, target_value)
                )
                if is_target_value:
                    return _path

                visited.add(id(current))
                children: list[Node] | None = current.get_next()
                if children:
                    for child in children:
                        if id(child) not in visited:
                            queue.append((child, _path + [child]))

            return None
        else:
            simple_queue: deque[Node] = deque([self])
            while simple_queue:
                current = simple_queue.popleft()

                is_target_value = (
                    current.value == target_value
                    if is_equal_value is None
                    else is_equal_value(current.value, target_value)
                )
                if is_target_value:
                    return True

                visited.add(id(current))
                children = current.get_next()
                if children:
                    for child in children:
                        if id(child) not in visited:
                            simple_queue.append(child)

            return False

    def shortest_path_to_target(
        self,
        target_value: object,
        is_equal_value: Callable | None = None,
    ) -> list['Node'] | None:
        return self.bfs(target_value, is_equal_value=is_equal_value, return_path=True)

    def __eq__(self, other: object) -> bool:
        return self is other

    def __hash__(self) -> int:
        return id(self)

    def __str__(self) -> str:
        return str(self.value)

    def str_all_descendants(
            self,
            level: int = 0,
            ascii_tree: bool = False,
            indent: int = 4,
            horizontal_char: str = '-',
            vertical_char: str = '|',
            _output: StringIO | None = None,
            _visited: set | None = None
    ) -> str:
        """Generates a string representation of the current node and all its descendant nodes.

        Supports cycle detection — nodes already visited are marked with [CYCLE].

        Args:
            level: The current depth level for indentation. Defaults to 0.
            ascii_tree: If True, uses ASCII-style tree characters.
            indent: Number of spaces per indentation level when ascii_tree is False.
            horizontal_char: Character for horizontal lines in ASCII mode.
            vertical_char: Character for vertical lines in ASCII mode.
        """
        if _output is None:
            _output = StringIO()

        if _visited is None:
            _visited = set()

        if ascii_tree:
            if level == 0:
                prefix = ""
            else:
                prefix = ((vertical_char + '   ') * (level - 1)) + vertical_char + horizontal_char * 2 + ' '
        else:
            prefix = ' ' * (indent * level)

        if id(self) in _visited:
            _output.write(prefix + str(self) + ' [CYCLE]\n')
            return _output.getvalue()

        _visited.add(id(self))

        _output.write(prefix + str(self) + '\n')
        children = self.get_next()
        if children:
            for child in children:
                child.str_all_descendants(
                    level=level + 1,
                    ascii_tree=ascii_tree,
                    indent=indent,
                    horizontal_char=horizontal_char,
                    vertical_char=vertical_char,
                    _output=_output,
                    _visited=_visited
                )
        return _output.getvalue()

    def str_all_ancestors(
            self,
            level: int = 0,
            ascii_tree: bool = False,
            indent: int = 4,
            horizontal_char: str = '-',
            vertical_char: str = '|',
            _output: StringIO | None = None,
            _visited: set | None = None
    ) -> str:
        """Generates a string representation of the current node and all its ancestor nodes.

        Supports cycle detection — nodes already visited are marked with [CYCLE].

        Args:
            level: Current depth level for indentation.
            ascii_tree: If True, uses ASCII-style tree characters.
            indent: Number of spaces per indentation level when ascii_tree is False.
            horizontal_char: Character for horizontal lines in ASCII mode.
            vertical_char: Character for vertical lines in ASCII mode.
        """
        if _output is None:
            _output = StringIO()

        if _visited is None:
            _visited = set()

        if ascii_tree:
            prefix = ((vertical_char + '   ') * (level - 1)) + (
                    vertical_char + horizontal_char * 2 + ' ') if level > 0 else ''
        else:
            prefix = ' ' * (indent * level)

        if id(self) in _visited:
            _output.write(prefix + str(self) + ' [CYCLE]\n')
            return _output.getvalue()

        _visited.add(id(self))

        _output.write(prefix + str(self) + '\n')

        parents = self.get_previous()
        if parents:
            for parent in parents:
                parent.str_all_ancestors(
                    level=level + 1,
                    ascii_tree=ascii_tree,
                    indent=indent,
                    horizontal_char=horizontal_char,
                    vertical_char=vertical_char,
                    _output=_output,
                    _visited=_visited
                )

        return _output.getvalue()


def str_all_descendants_of_nodes(
        nodes: List['Node'],
        ascii_tree: bool = False,
        indent: int = 4,
        horizontal_char: str = '-',
        vertical_char: str = '|'
) -> str:
    """Generates a combined string representation of all descendants for multiple nodes."""
    output = StringIO()
    for node in nodes:
        node.str_all_descendants(
            ascii_tree=ascii_tree,
            indent=indent,
            horizontal_char=horizontal_char,
            vertical_char=vertical_char,
            _output=output
        )
        output.write('\n')
    return output.getvalue().strip()


def str_all_ancestors_of_nodes(
        nodes: List['Node'],
        ascii_tree: bool = False,
        indent: int = 4,
        horizontal_char: str = '-',
        vertical_char: str = '|'
) -> str:
    """Generates a combined string representation of all ancestors for multiple nodes."""
    output = StringIO()
    for node in nodes:
        node.str_all_ancestors(
            ascii_tree=ascii_tree,
            indent=indent,
            horizontal_char=horizontal_char,
            vertical_char=vertical_char,
            _output=output
        )
        output.write('\n')
    return output.getvalue().strip()
