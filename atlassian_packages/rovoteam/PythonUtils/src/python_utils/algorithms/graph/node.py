from collections import deque
from io import StringIO
from queue import Queue
from typing import List
from typing import Optional, Any, Callable, Union

from attr import attrs, attrib

from python_utils.common_utils import make_list


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

    def __attrs_post_init__(self):
        # Call parent __attrs_post_init__ if it exists (for multiple inheritance support)
        super_post_init = getattr(super(), '__attrs_post_init__', None)
        if super_post_init:
            super_post_init()

        if isinstance(self.next, Node):
            self.next = make_list(self.next, list_factory=self._node_list_factory)
        elif not (self.next is None or isinstance(self.next, List) or callable(self.next)):
            raise ValueError(
                "`next` must be None, a Node, or a list of Nodes, or a callable that generates next Nodes.")

        if isinstance(self.previous, Node):
            self.previous = make_list(self.previous, list_factory=self._node_list_factory)
        elif not (self.previous is None or isinstance(self.previous, List) or callable(self.previous)):
            raise ValueError(
                "`previous` must be None, a Node, or a list of Nodes, or a callable that generates previous Nodes.")

        self._node_list_factory = None

    def add_next(self, next_value_or_node, node_list_factory: Callable[[], List] = list):
        """Adds a successor node to this node.

        If `next_value_or_node` is not a `Node`, a new `Node` will be created
        with this node as its predecessor. Mutual linking is maintained so that
        the newly created or added node also references this node as a predecessor.

        Args:
            next_value_or_node: A `Node` object or any value. If it's not a `Node`,
                a new `Node` will be created for it.
            node_list_factory: A callable returning a new list-like container for nodes if needed.

        Examples:
            >>> root = Node("root",None,None)
            >>> root.add_next("child1")
            >>> len(root.next)
            1
            >>> root.next[0].value
            'child1'
            >>> # Check mutual linking
            >>> len(root.next[0].previous)
            1
            >>> root.next[0].previous[0].value
            'root'

            >>> # Add another node as a Node instance
            >>> child2 = Node("child2",None,None)
            >>> root.add_next(child2)
            >>> len(root.next)
            2
            >>> root.next[1].value
            'child2'
            >>> len(child2.previous)
            1
            >>> child2.previous[0].value
            'root'
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

    def _post_adding_next_process(self, next_node):
        """
        Hook method called after a next node has been added.

        This method is called automatically by `add_next()` after successfully
        adding a successor node. Subclasses can override this method to perform
        custom post-processing, such as logging, validation, or updating metadata.

        Args:
            next_node: The Node instance that was just added as a successor

        Examples:
            >>> class LoggingNode(Node):
            ...     def __init__(self, *args, **kwargs):
            ...         super().__init__(*args, **kwargs)
            ...         self.add_log = []
            ...     def post_adding_next_process(self, next_node):
            ...         self.add_log.append(f"Added next: {next_node.value}")

            >>> node = LoggingNode("parent", None, None)
            >>> node.add_next("child")
            >>> node.add_log
            ['Added next: child']
            >>> len(node.next)
            1
        """
        pass

    def add_previous(self, previous_value_or_node, node_list_factory: Callable[[], List] = list):
        """Adds a predecessor node to this node.

        If `previous_value_or_node` is not a `Node`, a new `Node` will be created
        with this node as its successor. Mutual linking is maintained so that
        the newly created or added node also references this node as a successor.

        Args:
            previous_value_or_node: A `Node` object or any value. If it's not a `Node`,
                a new `Node` will be created for it.
            node_list_factory: A callable returning a new list-like container for nodes if needed.

        Examples:
            >>> root = Node("root",None,None)
            >>> root.add_previous("parent1")
            >>> len(root.previous)
            1
            >>> root.previous[0].value
            'parent1'
            >>> # Check mutual linking
            >>> len(root.previous[0].next)
            1
            >>> root.previous[0].next[0].value
            'root'

            >>> # Add another previous node as a Node instance
            >>> parent2 = Node("parent2",None,None)
            >>> root.add_previous(parent2)
            >>> len(root.previous)
            2
            >>> root.previous[1].value
            'parent2'
            >>> len(parent2.next)
            1
            >>> parent2.next[0].value
            'root'
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

    def _post_adding_previous_process(self, previous_node):
        """
        Hook method called after a previous node has been added.

        This method is called automatically by `add_previous()` after successfully
        adding a predecessor node. Subclasses can override this method to perform
        custom post-processing, such as logging, validation, or updating metadata.

        Args:
            previous_node: The Node instance that was just added as a predecessor

        Examples:
            >>> class LoggingNode(Node):
            ...     def __init__(self, *args, **kwargs):
            ...         super().__init__(*args, **kwargs)
            ...         self.add_log = []
            ...     def post_adding_previous_process(self, previous_node):
            ...         self.add_log.append(f"Added previous: {previous_node.value}")

            >>> node = LoggingNode("child", None, None)
            >>> node.add_previous("parent")
            >>> node.add_log
            ['Added previous: parent']
            >>> len(node.previous)
            1
            >>> node.previous[0].value
            'parent'
        """
        pass

    def get_next(self):
        return self.next(self.value) if callable(self.next) else self.next

    def get_previous(self):
        return self.previous(self.value) if callable(self.previous) else self.previous

    def bfs(self, target_value, is_equal_value: Callable = None, return_path: bool = False):
        """
        Performs a breadth-first search (BFS) starting from this node to find a node
        whose value matches `target_value`.

        This method traverses the graph formed by `self` and its descendants (via
        `get_next()`), looking for the first node whose value matches `target_value`.
        Because BFS explores nodes in layers, the first time a value matches
        `target_value` is guaranteed to be the shallowest such match in an
        unweighted, undirected sense.

        Args:
            target_value: The value we want to find in the graph.
            is_equal_value (Callable, optional): A custom comparison function that
                takes `(current_value, target_value)` and returns a bool. If None,
                the comparison defaults to `current.value == target_value`.
            return_path (bool, optional): If True, returns a list of visited nodes
                (in BFS order) up to and including the node that matched
                `target_value`. If False, returns a boolean `True` if found, otherwise `False`.

        Returns:
            bool or List[Node]:
                - If `return_path` is False, returns `True` if the node is found, else `False`.
                - If `return_path` is True, returns the list of visited nodes in BFS order up to
                  the matching node, or `None` if not found.

        Examples:
            >>> # Create a small node graph
            >>> root = Node("root")
            >>> child1 = Node("child1")
            >>> child2 = Node("child2")
            >>> child3 = Node("child3")
            >>> root.add_next(child1)
            >>> root.add_next(child2)
            >>> child2.add_next(child3)
            >>> # Visual representation of the graph:
            >>> #        root
            >>> #       /   \
            >>> #   child1  child2
            >>> #             |
            >>> #           child3

            >>> # BFS for an existing value
            >>> root.bfs("child3")
            True

            >>> # BFS for a non-existing value
            >>> root.bfs("childX")
            False

            >>> # If we want the BFS visitation list
            >>> path_up_to_target = root.bfs("child3", return_path=True)
            >>> [n.value for n in path_up_to_target]  # doctest: +NORMALIZE_WHITESPACE
            ['root', 'child2', 'child3']

            >>> # BFS for a non-existing value with return_path=True
            >>> print(root.bfs("childX", return_path=True))
            None
        """
        visited = set()

        if return_path:
            queue = deque([(self, [self])])
            while queue:
                current, _path = queue.popleft()

                is_target_value = (
                    current.value == target_value
                    if is_equal_value is None
                    else is_equal_value(current.value, target_value)
                )
                if is_target_value:
                    return _path

                visited.add(current)
                children: Optional[List[Node]] = current.get_next()
                if children:
                    for child in children:
                        if child not in visited:
                            queue.append((child, _path + [child]))

            return None
        else:
            queue = deque([self])
            while queue:
                current = queue.popleft()

                is_target_value = (
                    current.value == target_value
                    if is_equal_value is None
                    else is_equal_value(current.value, target_value)
                )
                if is_target_value:
                    return True

                visited.add(current)
                children: Optional[List[Node]] = current.get_next()
                if children:
                    for child in children:
                        if child not in visited:
                            queue.append(child)

            return False

    def shortest_path_to_target(self, target_value, is_equal_value: Callable = None):
        return self.bfs(target_value, is_equal_value=is_equal_value, return_path=True)

    def __eq__(self, other):
        return self is other

    def __hash__(self):
        return id(self)

    def __str__(self):
        """Returns a string representation of the node's value.

        Returns:
            str: The string representation of `self.value`.

        Examples:
            >>> n = Node("root",None,None)
            >>> str(n)
            'root'
        """
        return str(self.value)

    def str_all_descendants(
            self,
            level: int = 0,
            ascii_tree: bool = False,
            indent: int = 4,
            horizontal_char: str = '-',
            vertical_char: str = '|',
            _output: StringIO = None,
            _visited: set = None
    ) -> str:
        """
        Generates a string representation of the current node and all its descendant nodes.

        This method traverses the graph starting from the current node and produces a hierarchical
        view of the descendants. The hierarchy can be visualized using either spaces for indentation
        or an ASCII-style tree structure with customizable characters.

        Cycle Detection:
            This method supports graphs with cycles (e.g., self-edges via node.add_next(node)).
            When a cycle is detected, the node is marked with "[CYCLE]" suffix to prevent
            infinite recursion.

        Args:
            level (int): The current depth level for indentation or ASCII formatting. Defaults to 0.
            ascii_tree (bool): If True, uses `vertical_char` and `horizontal_char` for an ASCII-style tree.
                               If False, uses spaces for indentation. Defaults to False.
            indent (int): Number of spaces to use per indentation level when `ascii_tree` is False. Defaults to 4.
            horizontal_char (str): Character(s) used for horizontal lines in ASCII mode. Defaults to '-'.
            vertical_char (str): Character(s) used for vertical lines in ASCII mode. Defaults to '|'.
            _output (StringIO, optional): A `StringIO` object to collect the output. Defaults to None.
            _visited (set, optional): A set of visited node ids for cycle detection. Defaults to None.

        Returns:
            str: A string representation of the node and its descendants.

        Examples:
            >>> root = Node("A")
            >>> root.add_next("B")
            >>> root.add_next("C")
            >>> b = root.next[0]
            >>> b.add_next("D")
            >>> b.add_next("E")
            >>> c = root.next[1]
            >>> c.add_next("F")
            >>> # Default printing (indent=4 spaces, ascii_tree=False):
            >>> print(root.str_all_descendants(ascii_tree=False))  # doctest: +NORMALIZE_WHITESPACE
            A
                B
                    D
                    E
                C
                    F
            >>> # ASCII-style printing with default chars:
            >>> print(root.str_all_descendants(ascii_tree=True))  # doctest: +NORMALIZE_WHITESPACE
            A
            |-- B
            |   |-- D
            |   |-- E
            |-- C
            |   |-- F
            >>> # ASCII-style with custom chars and smaller indent:
            >>> print(root.str_all_descendants(ascii_tree=True, indent=2, vertical_char='¦', horizontal_char='='))  # doctest: +NORMALIZE_WHITESPACE
            A
            ¦== B
            ¦   ¦== D
            ¦   ¦== E
            ¦== C
            ¦   ¦== F

            >>> # Self-edge (cycle) detection:
            >>> monitor = Node("Monitor")
            >>> action = Node("Action")
            >>> monitor.add_next(action)
            >>> monitor.add_next(monitor)  # Self-edge
            >>> print(monitor.str_all_descendants(ascii_tree=True))  # doctest: +NORMALIZE_WHITESPACE
            Monitor
            |-- Action
            |-- Monitor [CYCLE]
        """

        if _output is None:
            _output = StringIO()

        if _visited is None:
            _visited = set()

        if ascii_tree:
            # For ASCII mode, build a prefix based on the level
            if level == 0:
                prefix = ""
            else:
                # For levels > 0:
                # We add vertical_char + '   ' for each previous level except the last
                # and at the end we use vertical_char + horizontal_char*2 + ' '.
                prefix = ((vertical_char + '   ') * (level - 1)) + vertical_char + horizontal_char * 2 + ' '
        else:
            # Use specified number of spaces per level
            prefix = ' ' * (indent * level)

        # Check for cycle - if we've already visited this node
        if id(self) in _visited:
            _output.write(prefix + str(self) + ' [CYCLE]\n')
            return _output.getvalue()

        # Mark this node as visited
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
            _output: StringIO = None,
            _visited: set = None
    ) -> str:
        """
        Generates a string representation of the current node and all its ancestor nodes.

        Each level of ancestors is indented or visualized using ASCII characters. The traversal
        includes all parent nodes recursively until no more ancestors are found.

        Cycle Detection:
            This method supports graphs with cycles. When a cycle is detected, the node
            is marked with "[CYCLE]" suffix to prevent infinite recursion.

        Args:
            level (int): Current depth level for indentation or ASCII art. Defaults to 0.
            ascii_tree (bool): If True, uses `vertical_char` and `horizontal_char` for an ASCII-style tree.
                               If False, uses spaces for indentation. Defaults to False.
            indent (int): Number of spaces to use per indentation level when `ascii_tree` is False. Defaults to 4.
            horizontal_char (str): Character(s) used for horizontal lines in ASCII mode. Defaults to '-'.
            vertical_char (str): Character(s) used for vertical lines in ASCII mode. Defaults to '|'.
            _output (StringIO, optional): A `StringIO` object to collect the output. Defaults to None.
            _visited (set, optional): A set of visited node ids for cycle detection. Defaults to None.

        Returns:
            str: A string representation of the current node and its ancestors.

        Examples:
            >>> root = Node("Parent0")
            >>> root.add_next("Child1")
            >>> root.add_next("Child2")
            >>> b = root.next[0]
            >>> b.add_previous("Parent1")
            >>> b.add_previous("Parent2")
            >>> b.previous[0].add_previous("GrandParent0")
            >>> print(b.str_all_ancestors(ascii_tree=False))  # doctest: +NORMALIZE_WHITESPACE
            Child1
                Parent0
                    GrandParent0
                Parent1
                Parent2
            >>> print(b.str_all_ancestors(ascii_tree=True))  # doctest: +NORMALIZE_WHITESPACE
            Child1
            |-- Parent0
            |   |-- GrandParent0
            |-- Parent1
            |-- Parent2
        """

        if _output is None:
            _output = StringIO()

        if _visited is None:
            _visited = set()

        # Build the prefix based on the current level and ASCII settings
        if ascii_tree:
            prefix = ((vertical_char + '   ') * (level - 1)) + (
                    vertical_char + horizontal_char * 2 + ' ') if level > 0 else ''
        else:
            prefix = ' ' * (indent * level)

        # Check for cycle - if we've already visited this node
        if id(self) in _visited:
            _output.write(prefix + str(self) + ' [CYCLE]\n')
            return _output.getvalue()

        # Mark this node as visited
        _visited.add(id(self))

        # Write the current node's value
        _output.write(prefix + str(self) + '\n')

        # Recursively process parent nodes
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

        # Return the accumulated string
        return _output.getvalue()


def str_all_descendants_of_nodes(
        nodes: List['Node'],
        ascii_tree: bool = False,
        indent: int = 4,
        horizontal_char: str = '-',
        vertical_char: str = '|'
) -> str:
    """
    Generates a combined string representation of all descendants for multiple nodes.

    Args:
        nodes (List[Node]): A list of `Node` objects whose descendants will be included in the output.
        ascii_tree (bool): If True, uses `vertical_char` and `horizontal_char` for ASCII-style visualization.
                           If False, uses spaces for indentation.
        indent (int): Number of spaces to use per indentation level when ascii_tree=False. Defaults to 4.
        horizontal_char (str): Character(s) to use for horizontal lines in ASCII mode. Default: '-'.
        vertical_char (str): Character(s) to use for vertical lines in ASCII mode. Default: '|'.

    Returns:
        str: A combined string representation of all descendants for the given nodes.

    Examples:
        >>> a = Node("A")
        >>> b = Node("B")
        >>> c = Node("C")
        >>> d = Node("D")
        >>> a.add_next(b)
        >>> b.add_next(c)
        >>> b.add_next(d)
        >>> print(str_all_descendants_of_nodes([a, b], ascii_tree=True))  # doctest: +NORMALIZE_WHITESPACE
        A
        |-- B
        |   |-- C
        |   |-- D
        B
        |-- C
        |-- D
    """
    output = StringIO()
    for node in nodes:
        node.str_all_descendants(
            ascii_tree=ascii_tree,
            indent=indent,
            horizontal_char=horizontal_char,
            vertical_char=vertical_char,
            _output=output
        )
        output.write('\n')  # Add a blank line between outputs for readability
    return output.getvalue().strip()


def str_all_ancestors_of_nodes(
        nodes: List['Node'],
        ascii_tree: bool = False,
        indent: int = 4,
        horizontal_char: str = '-',
        vertical_char: str = '|'
) -> str:
    """
    Generates a combined string representation of all ancestors for multiple nodes.

    Args:
        nodes (List[Node]): A list of `Node` objects whose ancestors will be included in the output.
        ascii_tree (bool): If True, uses `vertical_char` and `horizontal_char` for ASCII-style visualization.
                           If False, uses spaces for indentation.
        indent (int): Number of spaces to use per indentation level when ascii_tree=False. Defaults to 4.
        horizontal_char (str): Character(s) to use for horizontal lines in ASCII mode. Default: '-'.
        vertical_char (str): Character(s) to use for vertical lines in ASCII mode. Default: '|'.

    Returns:
        str: A combined string representation of all ancestors for the given nodes.

    Examples:
        >>> a = Node("A")
        >>> b = Node("B")
        >>> c = Node("C")
        >>> d = Node("D")
        >>> b.add_previous(a)
        >>> c.add_previous(b)
        >>> d.add_previous(b)
        >>> print(str_all_ancestors_of_nodes([c, d], ascii_tree=True))  # doctest: +NORMALIZE_WHITESPACE
        C
        |-- B
        |   |-- A
        D
        |-- B
        |   |-- A
    """
    output = StringIO()
    for node in nodes:
        node.str_all_ancestors(
            ascii_tree=ascii_tree,
            indent=indent,
            horizontal_char=horizontal_char,
            vertical_char=vertical_char,
            _output=output
        )
        output.write('\n')  # Add a blank line between outputs for readability
    return output.getvalue().strip()
