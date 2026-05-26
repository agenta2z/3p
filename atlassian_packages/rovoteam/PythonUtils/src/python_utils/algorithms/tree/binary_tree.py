from collections import deque, defaultdict
from math import inf
from typing import Any, Callable, Union, List, TypeVar, Optional, Generic, Tuple, Sequence, Iterator, Iterable

from python_utils.algorithms.array.binary_search import binary_post_order_result_compute
from python_utils.common_utils.array_helper import index_of_last_non_null, index_

T = TypeVar('T')


class BinaryTree(Generic[T]):
    def __init__(self, value: T, left: Optional['BinaryTree[T]'] = None, right: Optional['BinaryTree[T]'] = None):
        self.value = value
        self.left = left
        self.right = right

    def in_order_dfs(self, yield_value: bool = True) -> Iterator[Union[T, 'BinaryTree[T]']]:
        """
        Performs an in-order traversal of the binary tree.

        This method generates either the values of the binary tree or the nodes themselves
        in in-order traversal order, which visits the left subtree, then the root node,
        and finally the right subtree.

        Args:
            yield_value (bool, optional): If True, yields the value of each node.
                                          If False, yields the nodes themselves. Defaults to True.

        Yields:
            Union[T, BinaryTree[T]]: The next value or node in the in-order traversal of the binary tree.

        Examples:
            # Example 1: Full binary tree
            >>> #      4
            >>> #     / \
            >>> #    2   6
            >>> #   / \\ / \
            >>> #  1  3 5  7
            >>> node1 = BinaryTree(1,None,None)
            >>> node3 = BinaryTree(3,None,None)
            >>> node5 = BinaryTree(5,None,None)
            >>> node7 = BinaryTree(7,None,None)
            >>> node2 = BinaryTree(2,node1,node3)
            >>> node6 = BinaryTree(6,node5,node7)
            >>> root = BinaryTree(4,node2,node6)
            >>> list(root.in_order_dfs())
            [1, 2, 3, 4, 5, 6, 7]
            >>> [node.value for node in root.in_order_dfs(yield_value=False)]
            [1, 2, 3, 4, 5, 6, 7]

            # Example 2: Single-node binary tree
            >>> root = BinaryTree(42,None,None)
            >>> list(root.in_order_dfs())
            [42]
            >>> [node.value for node in root.in_order_dfs(yield_value=False)]
            [42]

            # Example 3: Binary tree with only left children
            >>> #      3
            >>> #     /
            >>> #    2
            >>> #   /
            >>> #  1
            >>> node1 = BinaryTree(1,None,None)
            >>> node2 = BinaryTree(2,node1,None)
            >>> root = BinaryTree(3,node2,None)
            >>> list(root.in_order_dfs())
            [1, 2, 3]
            >>> [node.value for node in root.in_order_dfs(yield_value=False)]
            [1, 2, 3]

        Notes:
            - The method assumes the binary tree is properly constructed.
            - Time Complexity: O(n), where n is the number of nodes in the tree.
            - Space Complexity: O(h), where h is the height of the tree, due to the recursion stack.
        """

        def _dfs(node: 'BinaryTree'):
            if node.left is not None:
                yield from _dfs(node.left)
            yield node.value if yield_value else node
            if node.right is not None:
                yield from _dfs(node.right)

        yield from _dfs(self)

    def post_order_dfs(self, yield_value: bool = True) -> Iterator[Union[T, 'BinaryTree[T]']]:
        """
        Performs a post-order traversal of the binary tree.

        This method generates the values of the binary tree in post-order traversal order,
        which visits the left subtree, then the right subtree, and finally the root node.

        Args:
            yield_value (bool, optional): If True, yields the value of each node.
                                          If False, yields the nodes themselves. Defaults to True.

        Yields:
            Union[T, BinaryTree[T]]: The next value or node in the post-order traversal of the binary tree.

        Examples:
            # Example 1: Full binary tree
            >>> #      4
            >>> #     / \
            >>> #    2   6
            >>> #   / \\ / \
            >>> #  1  3 5  7
            >>> node1 = BinaryTree(1,None,None)
            >>> node3 = BinaryTree(3,None,None)
            >>> node5 = BinaryTree(5,None,None)
            >>> node7 = BinaryTree(7,None,None)
            >>> node2 = BinaryTree(2,node1,node3)
            >>> node6 = BinaryTree(6,node5,node7)
            >>> root = BinaryTree(4,node2,node6)
            >>> list(root.post_order_dfs())
            [1, 3, 2, 5, 7, 6, 4]

            # Example 2: Single-node binary tree
            >>> root = BinaryTree(42,None,None)
            >>> list(root.post_order_dfs())
            [42]

            # Example 3: Binary tree with only right children
            >>> #  1
            >>> #   \
            >>> #    2
            >>> #     \
            >>> #      3
            >>> node3 = BinaryTree(3,None,None)
            >>> node2 = BinaryTree(2,None,node3)
            >>> root = BinaryTree(1,None,node2)
            >>> list(root.post_order_dfs())
            [3, 2, 1]

        Notes:
            - The method assumes the binary tree is properly constructed.
            - Time Complexity: O(n), where n is the number of nodes in the tree.
            - Space Complexity: O(h), where h is the height of the tree, due to the recursion stack.
        """

        def _dfs(node: 'BinaryTree'):
            if node.left is not None:
                yield from _dfs(node.left)
            if node.right is not None:
                yield from _dfs(node.right)
            yield node.value if yield_value else node

        yield from _dfs(self)

    def pre_order_dfs(self, yield_value: bool = True) -> Iterator[Union[T, 'BinaryTree[T]']]:
        """
        Performs a pre-order traversal of the binary tree.

        This method generates the values of the binary tree in pre-order traversal order,
        which visits the root node first, then the left subtree, and finally the right subtree.

        Args:
            yield_value (bool, optional): If True, yields the value of each node.
                                          If False, yields the nodes themselves. Defaults to True.

        Yields:
            Union[T, BinaryTree[T]]: The next value or node in the pre-order traversal of the binary tree.

        Examples:
            # Example 1: Full binary tree
            >>> #      4
            >>> #     / \
            >>> #    2   6
            >>> #   / \\ / \
            >>> #  1  3 5  7
            >>> node1 = BinaryTree(1, None, None)
            >>> node3 = BinaryTree(3, None, None)
            >>> node5 = BinaryTree(5, None, None)
            >>> node7 = BinaryTree(7, None, None)
            >>> node2 = BinaryTree(2, node1, node3)
            >>> node6 = BinaryTree(6, node5, node7)
            >>> root = BinaryTree(4, node2, node6)
            >>> list(root.pre_order_dfs())
            [4, 2, 1, 3, 6, 5, 7]

            # Example 2: Single-node binary tree
            >>> root = BinaryTree(42, None, None)
            >>> list(root.pre_order_dfs())
            [42]

            # Example 3: Binary tree with only right children
            >>> #  1
            >>> #   \
            >>> #    2
            >>> #     \
            >>> #      3
            >>> node3 = BinaryTree(3, None, None)
            >>> node2 = BinaryTree(2, None, node3)
            >>> root = BinaryTree(1, None, node2)
            >>> list(root.pre_order_dfs())
            [1, 2, 3]

        Notes:
            - The method assumes the binary tree is properly constructed.
            - Time Complexity: O(n), where n is the number of nodes in the tree.
            - Space Complexity: O(h), where h is the height of the tree, due to the recursion stack.
        """

        def _dfs(node: 'BinaryTree'):
            yield node.value if yield_value else node
            if node.left is not None:
                yield from _dfs(node.left)
            if node.right is not None:
                yield from _dfs(node.right)

        yield from _dfs(self)

    def post_order_dfs_with_result_compute(
            self,
            compute_at_parent_node: Callable = None,
            pass_parent_node_value: bool = True,
            early_termination_at_parent_node: Callable[[Union['BinaryTree[T]', Any], ...], Any] = None,
            *args, **kwargs
    ):
        """
        Performs a post-order traversal of the binary tree and computes a result at each node.

        This method traverses the binary tree in post-order (left subtree, right subtree, root)
        and optionally computes a result at each root node using the provided function `compute_at_parent_node`.
        It also supports early termination of traversal if a condition (`early_termination_cond`) is met.


        Args:
            compute_at_parent_node (Callable, optional): A function to compute the result at each parent node.
                The function should accept the following arguments:
                    - node_value (T): The value of the current parent node.
                    - left_result (Any): The computed result from the left child (or `None` if no left child).
                    - right_result (Any): The computed result from the right child (or `None` if no right child).
                    - *args, **kwargs: Additional arguments passed to the function.
                If `None`, no computation is performed, and the traversal proceeds without result computation.
                Defaults to `None`.
            pass_parent_node_value (bool, optional): If `True`, passes the parent node's value to the
                `compute_at_parent_node` function. If `False`, passes the node itself. Defaults to `True`.
            early_termination_at_parent_node (Callable, optional): A condition function that determines
                whether to terminate the traversal early at a parent node. The function should accept the
                following arguments:
                    - current_node (BinaryTree[T]): The current node being visited.
                    - *args, **kwargs: Additional arguments passed to the function.
                If the function returns a non-`None` value, traversal terminates, and this value is returned.
                Defaults to `None`.
            *args: Additional positional arguments for the `compute_at_parent_node` function.
            **kwargs: Additional keyword arguments for the `compute_at_parent_node` function.

        Returns:
            Any: The result of the computation at the root of the tree, as determined by `compute_at_root_node`.

        Examples:
            # Example 1: Full binary tree
            >>> #      4
            >>> #     / \
            >>> #    2   6
            >>> #   / \\ / \
            >>> #  1  3 5  7
            >>> node1 = BinaryTree(1, None, None)
            >>> node3 = BinaryTree(3, None, None)
            >>> node5 = BinaryTree(5, None, None)
            >>> node7 = BinaryTree(7, None, None)
            >>> node2 = BinaryTree(2, node1, node3)
            >>> node6 = BinaryTree(6, node5, node7)
            >>> root = BinaryTree(4, node2, node6)

            # Summing all values in the binary tree (0 for None)
            >>> summing_values = lambda val, left, right: (left or 0) + (right or 0) + val
            >>> root.post_order_dfs_with_result_compute(summing_values)
            28

            # Finding the maximum value in the binary tree
            >>> get_max_value = lambda val, left, right: max(val, left or float('-inf'), right or float('-inf'))
            >>> root.post_order_dfs_with_result_compute(get_max_value)
            7

            # Getting tree depth
            >>> get_depth = lambda val, left, right: max(left or 0, right or 0) + 1
            >>> root.post_order_dfs_with_result_compute(get_depth)
            3

            # Testing early termination
            >>> early_terminate_at_6 = lambda node: node.value if node.value == 6 else None
            >>> root.post_order_dfs_with_result_compute(
            ...     early_termination_at_parent_node=early_terminate_at_6
            ... )
            6

            # Example 2: Single-node binary tree
            >>> root = BinaryTree(42, None, None)
            >>> root.post_order_dfs_with_result_compute(summing_values)
            42
            >>> root.post_order_dfs_with_result_compute(get_depth)
            1

            # Example 3: Binary tree with only right children
            >>> #  1
            >>> #   \
            >>> #    2
            >>> #     \
            >>> #      3
            >>> node3 = BinaryTree(3, None, None)
            >>> node2 = BinaryTree(2, None, node3)
            >>> root = BinaryTree(1, None, node2)
            >>> root.post_order_dfs_with_result_compute(summing_values)
            6
            >>> root.post_order_dfs_with_result_compute(get_max_value)
            3
            >>> root.post_order_dfs_with_result_compute(get_depth)
            3

            # Example 4: Binary tree with only left children
            >>> #      3
            >>> #     /
            >>> #    2
            >>> #   /
            >>> #  1
            >>> node1 = BinaryTree(1, None, None)
            >>> node2 = BinaryTree(2, node1, None)
            >>> root = BinaryTree(3, node2, None)
            >>> root.post_order_dfs_with_result_compute(summing_values)
            6
            >>> root.post_order_dfs_with_result_compute(get_max_value)
            3
            >>> root.post_order_dfs_with_result_compute(get_depth)
            3

        """
        if early_termination_at_parent_node is not None:
            early_termination_result = early_termination_at_parent_node(self, *args, **kwargs)
            if early_termination_result is not None:
                return early_termination_result

        left_result = right_result = None
        if self.left is not None:
            left_result = self.left.post_order_dfs_with_result_compute(
                compute_at_parent_node=compute_at_parent_node,
                pass_parent_node_value=pass_parent_node_value,
                early_termination_at_parent_node=early_termination_at_parent_node,
                *args, **kwargs
            )
        if self.right is not None:
            right_result = self.right.post_order_dfs_with_result_compute(
                compute_at_parent_node=compute_at_parent_node,
                pass_parent_node_value=pass_parent_node_value,
                early_termination_at_parent_node=early_termination_at_parent_node,
                *args, **kwargs
            )
        if compute_at_parent_node is not None:
            return compute_at_parent_node(
                (self.value if pass_parent_node_value else self),  # parent node
                left_result,  # result from left child
                right_result,  # result from right child
                *args,
                **kwargs
            )
        else:
            return left_result or right_result

    def pre_order_dfs_with_result_compute(
            self,
            compute_at_parent_node: Callable = None,
            pass_parent_node_value: bool = True,
            initial_state: Optional[Any] = None,
            *args, **kwargs
    ):
        """
        Performs a pre-order traversal of the binary tree and computes a result at each node.

        This method traverses the binary tree in pre-order (root, left subtree, right subtree)
        and optionally computes a result at each node using the provided function `compute_at_parent_node`.
        The function receives the current node's value, state information from the parent node,
        and any additional arguments passed to the method.

        Args:
            compute_at_parent_node (Callable, optional): A function to compute the result at each parent node.
                The function should accept the following arguments:
                    - node_value (T): The value of the current parent node (or the node itself if `pass_parent_node_value` is False).
                    - previous_result (Any): The result of the computation from the parent node (or `None` if no parent node exists).
                    - state (Any): A state passed from the parent node to its children.
                    - *args, **kwargs: Additional arguments passed to the function.
                The function should return:
                    - result (Any): The computed result at the current node.
                    - new_state (Any): A state to be passed to the children of the current node.
                Defaults to `None`.
            pass_parent_node_value (bool, optional): If `True`, passes the current node's value to the
                `compute_at_parent_node` function. If `False`, passes the node itself. Defaults to `True`.
            initial_state (Any, optional): The initial state passed to the root node. Defaults to `None`.
            *args: Additional positional arguments for the `compute_at_parent_node` function.
            **kwargs: Additional keyword arguments for the `compute_at_parent_node` function.

        Returns:
            Any: The result of the computation at the root of the tree, as determined by `compute_at_parent_node`.

        Examples:
            # Example 1: Binary tree with node-wise sum computation
            >>> #      4
            >>> #     / \
            >>> #    2   6
            >>> #   / \ / \
            >>> #  1  3 5  7
            >>> node1 = BinaryTree(1, None, None)
            >>> node3 = BinaryTree(3, None, None)
            >>> node5 = BinaryTree(5, None, None)
            >>> node7 = BinaryTree(7, None, None)
            >>> node2 = BinaryTree(2, node1, node3)
            >>> node6 = BinaryTree(6, node5, node7)
            >>> root = BinaryTree(4, node2, node6)
            >>> def sum_values(val, prev_result, state):
            ...     return ((prev_result or 0) + val), state
            >>> root.pre_order_dfs_with_result_compute(sum_values)
            28
            >>> def count_nodes(val, prev_result, state):
            ...     return (prev_result or 0) + 1, state
            >>> root.pre_order_dfs_with_result_compute(count_nodes)
            7
            >>> def max_value(val, prev_result, state):
            ...     return max(prev_result or float('-inf'), val), state
            >>> root.pre_order_dfs_with_result_compute(max_value)
            7

            # Example 2: Concatenate string values in the tree
            >>> #      A
            >>> #     / \
            >>> #    B   C
            >>> #   / \ / \
            >>> #  D  E F  G
            >>> nodeD = BinaryTree("D", None, None)
            >>> nodeE = BinaryTree("E", None, None)
            >>> nodeF = BinaryTree("F", None, None)
            >>> nodeG = BinaryTree("G", None, None)
            >>> nodeB = BinaryTree("B", nodeD, nodeE)
            >>> nodeC = BinaryTree("C", nodeF, nodeG)
            >>> root = BinaryTree("A", nodeB, nodeC)
            >>> def concat_strings(val, prev_result, state):
            ...     return (prev_result or "") + val, state
            >>> root.pre_order_dfs_with_result_compute(concat_strings)
            'ABDECFG'

            # Example 3: Compute depth-weighted sum with a tree with missing nodes
            # The depth weighted sum is 4*1+2*2+6*2+3*3+7*3=50
            >>> #      4
            >>> #     / \
            >>> #    2   6
            >>> #     \    \
            >>> #      3    7
            >>> node3 = BinaryTree(3, None, None)
            >>> node7 = BinaryTree(7, None, None)
            >>> node2 = BinaryTree(2, None, node3)
            >>> node6 = BinaryTree(6, None, node7)
            >>> root = BinaryTree(4, node2, node6)
            >>> def depth_weighted_sum(val, prev_result, state):
            ...     # `state` tracks the current depth.
            ...     depth = state or 0
            ...     return (prev_result or 0) + val * (depth + 1), depth + 1
            >>> root.pre_order_dfs_with_result_compute(depth_weighted_sum, initial_state=0)
            50
        """

        result = None

        def _dfs(parent_node: Optional[BinaryTree[T]], state: Optional):
            nonlocal result

            result, state = compute_at_parent_node(
                (
                    parent_node.value
                    if pass_parent_node_value
                    else parent_node
                ),
                result,
                state,
                *args, **kwargs
            )
            if parent_node.left:
                _dfs(parent_node.left, state)
            if parent_node.right:
                _dfs(parent_node.right, state)

        _dfs(self, initial_state)
        return result

    # region Level BFS
    def _level_bfs_with_state_handler(
            self,
            yield_value: bool,
            decodable: bool,
            level_yield_cond: Callable[['BinaryTree', int, int], bool],
            state_handler: Callable[['BinaryTree[T]', Any, bool, ...], Any],
            unpack_singleton_level: bool,
            *args, **kwargs
    ) -> Iterator[List[Union['BinaryTree[T]', T, None]]]:
        queue = deque([
            (self, state_handler(self, None, None, *args, **kwargs))
        ])
        if level_yield_cond is not None:
            # region customized level yield
            if decodable:
                raise ValueError("'decodable' cannot be True while 'level_yield_cond' is specified")

            while queue:
                level_size = len(queue)
                level = []

                for i in range(level_size):
                    node, state = queue.popleft()
                    if level_yield_cond(node, i, level_size):
                        # Append node or value based on the flag
                        if node:
                            level.append((node.value, state) if yield_value else (node, state))
                        else:
                            level.append((None, None))

                    if node:
                        # Enqueue children
                        if node.left:
                            queue.append((node.left, state_handler(node.left, state, True, *args, **kwargs)))
                        if node.right:
                            queue.append((node.right, state_handler(node.right, state, False, *args, **kwargs)))

                if len(level) == 1 and unpack_singleton_level:
                    level = level[0]

                yield level
            # endregion
        elif decodable:
            # region decodable mode: Includes `None` for missing children
            while queue:
                level_size = len(queue)
                level = []

                # The "decodable" mode needs a `next_queue_all_null` flag
                next_queue_all_null = True

                for _ in range(level_size):
                    node, state = queue.popleft()
                    if node:
                        level.append((node.value, state) if yield_value else (node, state))

                        # Enqueue children with state transformations
                        queue.append(
                            (
                                node.left,
                                state_handler(node.left, state, True, *args, **kwargs) if node.left else None
                            )
                        )
                        queue.append(
                            (
                                node.right,
                                state_handler(node.right, state, False, *args, **kwargs) if node.right else None
                            )
                        )
                        if node.left or node.right:
                            next_queue_all_null = False
                    else:
                        # Include None for missing children when decodable is True
                        level.append((None, state))

                if next_queue_all_null:
                    # For the last level, remove all tailing nulls
                    level = level[:(index_(level, lambda x: x[0] is not None) + 1)]

                if len(level) == 1 and unpack_singleton_level:
                    level = level[0]

                yield level

                if next_queue_all_null:
                    break
            # endregion
        else:
            # region non-decodable level yield
            while queue:
                level_size = len(queue)
                level = []

                for _ in range(level_size):
                    node, state = queue.popleft()
                    if node:
                        level.append((node.value, state) if yield_value else (node, state))

                        # Enqueue children with state transformations
                        if node.left:
                            queue.append((node.left, state_handler(node.left, state, True, *args, **kwargs)))
                        if node.right:
                            queue.append((node.right, state_handler(node.right, state, False, *args, **kwargs)))

                if len(level) == 1 and unpack_singleton_level:
                    level = level[0]

                yield level
            # endregion

    def _level_bfs(
            self,
            yield_value: bool,
            decodable: bool,
            level_yield_cond: Callable[['BinaryTree', int, int], bool],
            unpack_singleton_level: bool,
    ) -> Iterator[List[Union['BinaryTree[T]', T, None]]]:
        queue = deque([self])
        if level_yield_cond is not None:
            # region customized level yield
            if decodable:
                raise ValueError("'decodable' cannot be True while 'level_yield_cond' is specified")

            while queue:
                level_size = len(queue)
                level = []

                for i in range(level_size):
                    node = queue.popleft()
                    if level_yield_cond(node, i, level_size):
                        # Append node or value based on the flag
                        if node:
                            level.append(node.value if yield_value else node)
                        else:
                            level.append(None)

                    if node:
                        # Enqueue children
                        if node.left:
                            queue.append(node.left)
                        if node.right:
                            queue.append(node.right)

                if len(level) == 1 and unpack_singleton_level:
                    level = level[0]

                yield level
            # endregion
        elif decodable:
            # region decodable level yield
            while queue:
                level_size = len(queue)
                level = []

                # The "decodable" mode needs a `next_queue_all_null` flag
                next_queue_all_null = True

                for _ in range(level_size):
                    node = queue.popleft()
                    if node:
                        # Append node or value based on the flag
                        level.append(node.value if yield_value else node)

                        # Enqueue children
                        queue.append(node.left)
                        queue.append(node.right)
                        if node.left or node.right:
                            next_queue_all_null = False
                    else:
                        # Include None for missing children when decodable is True
                        level.append(None)

                if next_queue_all_null:
                    # For the last level, remove all tailing nulls
                    level = level[:(index_of_last_non_null(level) + 1)]

                if len(level) == 1 and unpack_singleton_level:
                    level = level[0]

                yield level

                if next_queue_all_null:
                    break
            # endregion
        else:
            # region non-decodable level yield
            while queue:
                level_size = len(queue)
                level = []

                for _ in range(level_size):
                    node = queue.popleft()
                    if node:
                        # Append node or value based on the flag
                        level.append(node.value if yield_value else node)

                        # Enqueue children
                        if node.left:
                            queue.append(node.left)
                        if node.right:
                            queue.append(node.right)

                if len(level) == 1 and unpack_singleton_level:
                    level = level[0]

                yield level
            # endregion

    def level_bfs(
            self,
            yield_value: bool = False,
            decodable: bool = False,
            level_yield_cond: Callable[['BinaryTree', int, int], bool] = None,
            state_handler: Callable[['BinaryTree[T]', Any, bool, ...], Any] = None,
            unpack_singleton_level: bool = False,
    ) -> Iterator[List[Union['BinaryTree[T]', T, None]]]:
        """
        Perform a level-by-level Breadth-First Search (BFS) traversal of the binary tree.

        This method traverses the binary tree level by level and yields all nodes or their
        values (depending on `yield_value`) at each level. Additional options allow
        conditional yielding, reconstruction support, and customizable output formats.

        Args:
            yield_value (bool): If True, yields the values of the nodes instead of the nodes themselves.
                                Defaults to False.
            decodable (bool): If True, includes `None` for missing children (nulls) to allow tree reconstruction.
                              Cannot be used with `level_yield_cond`. Defaults to False.
            level_yield_cond (Callable, optional): A custom condition function to decide whether to yield nodes
                                                   at a specific level. The function takes three arguments:
                                                   the node, its index within the level, and the total level size.
                                                   Cannot be used with `decodable`. Defaults to None.
            state_handler (Callable, optional): A custom function that manages state transitions during
                                                 traversal. This function allows tracking or augmenting
                                                 information as the traversal progresses. It takes the
                                                 following arguments:

                                                 - `node` (`BinaryTree[T]`): The current node being processed.
                                                 - `parent_state` (`Any`): The state from the parent node.
                                                 - `is_left_child` (`bool`): True if the node is a left child, False otherwise.
                                                 - Additional arguments (`*args` and `**kwargs`) can be passed as needed.

                                                 The function should return the updated state for the current node.
                                                 Defaults to None, in which case no state management is performed.
            unpack_singleton_level (bool): If True, unpacks levels with only one node into a scalar value
                                           instead of a list. Defaults to False.

        Yields:
            List[Union[BinaryTree[T], T, None]]: A list of nodes (or their values/nulls) at each level,
                                                or a scalar value if `unpack_singleton_level` is True.

        Raises:
            ValueError: If `decodable` is True and `level_yield_cond` is also specified.

        Examples:
            # Example 1: Simple binary tree
            >>> # Tree Structure:
            >>> #      1
            >>> #     / \
            >>> #    2   3
            >>> #       /
            >>> #      4
            >>> tree = BinaryTree(
            ...     value=1,
            ...     left=BinaryTree(left=None, right=None, value=2),
            ...     right=BinaryTree(left=BinaryTree(left=None, right=None, value=4), right=None, value=3)
            ... )

            >>> list(tree.level_bfs(yield_value=True))
            [[1], [2, 3], [4]]
            >>> list(tree.level_bfs(yield_value=True, decodable=True))
            [[1], [2, 3], [None, None, 4]]

            # Example 2: Binary tree with a custom condition
            >>> # Tree Structure:
            >>> #      1
            >>> #     / \
            >>> #    2   3
            >>> #   /     \
            >>> #  4       5
            >>> tree_with_condition = BinaryTree(
            ...     value=1,
            ...     left=BinaryTree(
            ...         value=2,
            ...         left=BinaryTree(value=4),
            ...         right=None
            ...     ),
            ...     right=BinaryTree(
            ...         value=3,
            ...         left=None,
            ...         right=BinaryTree(value=5)
            ...     )
            ... )
            >>> def cond(node, idx, size): return idx == size - 1
            >>> list(tree_with_condition.level_bfs(yield_value=True, level_yield_cond=cond))
            [[1], [3], [5]]

            # Example 3: Binary tree with four levels
            >>> # Tree Structure:
            >>> #              1
            >>> #           /     \
            >>> #          2       3
            >>> #         /       /
            >>> #        4       6
            >>> #       /
            >>> #      8
            >>> tree_4_layers = BinaryTree(
            ...     value=1,
            ...     left=BinaryTree(
            ...         value=2,
            ...         left=BinaryTree(
            ...             value=4,
            ...             left=BinaryTree(value=8),
            ...             right=None
            ...         ),
            ...         right=None
            ...     ),
            ...     right=BinaryTree(
            ...         value=3,
            ...         left=BinaryTree(value=6),
            ...         right=None
            ...     )
            ... )

            >>> list(tree_4_layers.level_bfs(yield_value=True))
            [[1], [2, 3], [4, 6], [8]]
            >>> list(tree_4_layers.level_bfs(yield_value=True, decodable=True))
            [[1], [2, 3], [4, None, 6, None], [8]]
            >>> list(tree_4_layers.level_bfs(yield_value=True, unpack_singleton_level=True))
            [1, [2, 3], [4, 6], 8]

            # Example 4: Binary tree with a custom condition
            >>> # Tree Structure:
            >>> #       1
            >>> #      / \
            >>> #     2   3
            >>> #    /     \
            >>> #   4       5
            >>> def cond_yield_last(node, idx, size): return idx == size - 1
            >>> tree_with_condition = BinaryTree(
            ...     value=1,
            ...     left=BinaryTree(
            ...         value=2,
            ...         left=BinaryTree(value=4),
            ...         right=None
            ...     ),
            ...     right=BinaryTree(
            ...         value=3,
            ...         left=None,
            ...         right=BinaryTree(value=5)
            ...     )
            ... )
            >>> list(tree_with_condition.level_bfs(yield_value=True, level_yield_cond=cond_yield_last))
            [[1], [3], [5]]

            # Example 5: Binary tree with a state handler to track node depths
            >>> # Tree Structure:
            >>> #       1
            >>> #     /   \
            >>> #    2     3
            >>> #   / \   / \
            >>> #  4   5 6   7
            >>> tree_with_depth = BinaryTree(
            ...     value=1,
            ...     left=BinaryTree(
            ...         value=2,
            ...         left=BinaryTree(value=4),
            ...         right=BinaryTree(value=5)
            ...     ),
            ...     right=BinaryTree(
            ...         value=3,
            ...         left=BinaryTree(value=6),
            ...         right=BinaryTree(value=7)
            ...     )
            ... )

            >>> # Define a state handler to track node depth
            >>> def depth_state_handler(node, parent_state, is_left_child, *args, **kwargs):
            ...     return (parent_state or 0) + 1

            >>> # Perform BFS with the state handler
            >>> list(tree_with_depth.level_bfs(
            ...     yield_value=True,
            ...     state_handler=depth_state_handler
            ... ))
            [[(1, 1)], [(2, 2), (3, 2)], [(4, 3), (5, 3), (6, 3), (7, 3)]]

            # Example 6: Binary tree with a state handler to track cumulative sums
            >>> # Tree Structure:
            >>> #              5
            >>> #           /     \
            >>> #         3         8
            >>> #       /  \       /
            >>> #      1    4     7
            >>> tree_with_cumsum = BinaryTree(
            ...     value=5,
            ...     left=BinaryTree(
            ...         value=3,
            ...         left=BinaryTree(value=1),
            ...         right=BinaryTree(value=4)
            ...     ),
            ...     right=BinaryTree(
            ...         value=8,
            ...         left=BinaryTree(value=7),
            ...         right=None
            ...     )
            ... )

            >>> # Define a state handler to track cumulative sums
            >>> def cumsum_state_handler(node, parent_state, is_left_child, *args, **kwargs):
            ...     return (parent_state or 0) + node.value

            >>> # Perform BFS with the cumulative sum state handler
            >>> list(tree_with_cumsum.level_bfs(
            ...     yield_value=True,
            ...     state_handler=cumsum_state_handler
            ... ))
            [[(5, 5)], [(3, 8), (8, 13)], [(1, 9), (4, 12), (7, 20)]]

            # Example 7: Binary tree with a state handler and decodable=True
            >>> # Tree Structure:
            >>> #              10
            >>> #           /      \
            >>> #         6          15
            >>> #       /  \       /    \
            >>> #     None  7    None   None
            >>> tree_with_state_decodable = BinaryTree(
            ...     value=10,
            ...     left=BinaryTree(
            ...         value=6,
            ...         left=None,
            ...         right=BinaryTree(value=7)
            ...     ),
            ...     right=BinaryTree(
            ...         value=15,
            ...         left=None,
            ...         right=None
            ...     )
            ... )

            >>> # Define a state handler to track whether the node is a left or right child
            >>> def left_right_state_handler(node, parent_state, is_left_child, *args, **kwargs):
            ...     if parent_state is None:
            ...         return 'Root'
            ...     else:
            ...         return f"{parent_state} -> {'Left' if is_left_child else 'Right'}"

            >>> # Perform BFS with decodable=True
            >>> list(tree_with_state_decodable.level_bfs(
            ...     yield_value=True,
            ...     decodable=True
            ... ))
            [[10], [6, 15], [None, 7]]

            >>> # Perform BFS with the state handler and decodable=True
            >>> list(tree_with_state_decodable.level_bfs(
            ...     yield_value=True,
            ...     decodable=True,
            ...     state_handler=left_right_state_handler
            ... ))
            [[(10, 'Root')], [(6, 'Root -> Left'), (15, 'Root -> Right')], [(None, None), (7, 'Root -> Left -> Right')]]

            >>> list(tree_with_state_decodable.level_bfs(
            ...     yield_value=True,
            ...     decodable=False,
            ...     state_handler=left_right_state_handler
            ... ))
            [[(10, 'Root')], [(6, 'Root -> Left'), (15, 'Root -> Right')], [(7, 'Root -> Left -> Right')]]
        """
        if state_handler is None:
            return self._level_bfs(
                yield_value=yield_value,
                decodable=decodable,
                level_yield_cond=level_yield_cond,
                unpack_singleton_level=unpack_singleton_level
            )
        else:
            return self._level_bfs_with_state_handler(
                yield_value=yield_value,
                decodable=decodable,
                level_yield_cond=level_yield_cond,
                state_handler=state_handler,
                unpack_singleton_level=unpack_singleton_level
            )

    # endregion

    def bfs(
            self,
            yield_value: bool = False,
            decodable: bool = False,
            allow_tailing_nones: bool = True,
            state_handler: Callable[['BinaryTree[T]', Any, bool, ...], Any] = None,
            *args, **kwargs
    ) -> Iterator[Union['BinaryTree[T]', T]]:
        """Perform a Breadth-First Search (BFS) traversal of the binary tree as an iterator.

        Args:
            yield_value (bool): If True, yields the value of the nodes instead of the nodes themselves.
                                Defaults to False.
            decodable (bool): If True, includes `None` for missing children during traversal.
                              Defaults to False.
            allow_tailing_nones (bool): If True, retains trailing `None` values when `decodable=True`.
                                        If False, removes trailing `None` values.
                                        Defaults to True.
            state_handler (Callable, optional): A custom function for managing state during traversal.
                                                 Takes the following arguments:
                                                 - `node` (`BinaryTree[T]`): The current node being processed.
                                                 - `parent_state` (`Any`): The state from the parent node.
                                                 - `is_left_child` (`bool`): True if the node is a left child, False otherwise.
                                                 - Additional arguments (`*args`, `**kwargs`) can be passed as needed.
                                                 Should return the updated state for the current node. Defaults to None.

        Yields:
            Union[BinaryTree[T], T]: The current node or its value in BFS order, depending on `yield_value`.

        Examples:
            # Example 1: A sample binary tree
            >>> #      1
            >>> #     / \
            >>> #    2   3
            >>> #       /
            >>> #      4
            >>> tree = BinaryTree(
            ...     value=1,
            ...     left=BinaryTree(left=None, right=None, value=2),
            ...     right=BinaryTree(left=BinaryTree(left=None, right=None, value=4), right=None, value=3)
            ... )

            >>> [node.value for node in tree.bfs()]
            [1, 2, 3, 4]
            >>> list(tree.bfs(yield_value=True))
            [1, 2, 3, 4]
            >>> list(tree.bfs(yield_value=True, decodable=True))
            [1, 2, 3, None, None, 4, None, None, None]
            >>> list(tree.bfs(yield_value=True, decodable=True, allow_tailing_nones=False))
            [1, 2, 3, None, None, 4]

            # Example 2: Another sample binary tree
            >>> #      1
            >>> #     / \
            >>> #    2   3
            >>> #   /     \
            >>> #  4       5
            >>> tree_with_gaps = BinaryTree(
            ...     value=1,
            ...     left=BinaryTree(left=BinaryTree(left=None, right=None, value=4), right=None, value=2),
            ...     right=BinaryTree(left=None, right=BinaryTree(left=None, right=None, value=5), value=3)
            ... )

            >>> list(tree_with_gaps.bfs(yield_value=True))
            [1, 2, 3, 4, 5]
            >>> list(tree_with_gaps.bfs(yield_value=True, decodable=True))
            [1, 2, 3, 4, None, None, 5, None, None, None, None]
            >>> list(tree_with_gaps.bfs(yield_value=True, decodable=True, allow_tailing_nones=False))
            [1, 2, 3, 4, None, None, 5]

            # Example 3: A single-node binary tree
            >>> #      1
            >>> tree_single = BinaryTree(value=1)
            >>> list(tree_single.bfs(yield_value=True))
            [1]
            >>> list(tree_single.bfs(yield_value=True, decodable=True))
            [1, None, None]
            >>> list(tree_single.bfs(yield_value=True, decodable=True, allow_tailing_nones=False))
            [1]

            # Example 4: BFS with a state handler to track depth
            >>> # Binary tree:
            >>> #       5
            >>> #      / \
            >>> #     3   8
            >>> #    / \
            >>> #   1   4
            >>> tree_with_depth = BinaryTree(
            ...     value=5,
            ...     left=BinaryTree(
            ...         value=3,
            ...         left=BinaryTree(value=1),
            ...         right=BinaryTree(value=4)
            ...     ),
            ...     right=BinaryTree(value=8)
            ... )

            >>> # Define a state handler to track depth
            >>> def depth_state_handler(node, parent_state, is_left_child, *args, **kwargs):
            ...     return (parent_state or 0) + 1

            >>> list(tree_with_depth.bfs(
            ...     yield_value=True,
            ...     state_handler=depth_state_handler
            ... ))
            [(5, 1), (3, 2), (8, 2), (1, 3), (4, 3)]

            # Example 5: BFS with a state handler for tracking cumulative sums
            >>> # Binary tree:
            >>> #       10
            >>> #      /  \
            >>> #     7    15
            >>> #    /
            >>> #   3
            >>> tree_with_cumsum = BinaryTree(
            ...     value=10,
            ...     left=BinaryTree(
            ...         value=7,
            ...         left=BinaryTree(value=3)
            ...     ),
            ...     right=BinaryTree(value=15)
            ... )

            >>> # Define a state handler for cumulative sums
            >>> def cumsum_state_handler(node, parent_state, is_left_child, *args, **kwargs):
            ...     return (parent_state or 0) + node.value

            >>> list(tree_with_cumsum.bfs(
            ...     yield_value=True,
            ...     state_handler=cumsum_state_handler
            ... ))
            [(10, 10), (7, 17), (15, 25), (3, 20)]
        """
        if decodable:
            if allow_tailing_nones:
                if state_handler is None:
                    # region decodable mode and allows trailing None values
                    queue = deque([self])
                    while queue:
                        node = queue.popleft()

                        if node:
                            # Yield node or value based on the flag
                            yield node.value if yield_value else node

                            # Enqueue both children, including None for missing nodes
                            queue.append(node.left)
                            queue.append(node.right)
                        else:
                            # Yield None for missing nodes
                            yield None
                    # endregion
                else:
                    queue = deque(
                        [(
                            self,
                            state_handler(self, None, None, *args, **kwargs)
                        )]
                    )
                    while queue:
                        node, state = queue.popleft()
                        if node:
                            yield (node.value, state) if yield_value else (node, state)
                            queue.append((
                                node.left,
                                state_handler(node.left, state, True, *args, **kwargs)
                            ))
                            queue.append((
                                node.right,
                                state_handler(node.right, state, False, *args, **kwargs)
                            ))
                        else:
                            yield (None, state)
            else:
                # region only leveraging level traversal can elegantly remove tailing None values for decoddable mode
                for level in self.level_bfs(yield_value=yield_value, decodable=True, state_handler=state_handler):
                    yield from level
                # endregion
        else:
            # region non-decodable mode, naturally excludes any None value
            if state_handler is None:
                queue = deque([self])
                while queue:
                    node = queue.popleft()
                    if node:
                        # Yield node or value based on the flag
                        yield node.value if yield_value else node

                        # Enqueue both children
                        if node.left:
                            queue.append(node.left)
                        if node.right:
                            queue.append(node.right)
            else:
                queue = deque([(self, state_handler(self, None, None, *args, **kwargs))])
                while queue:
                    node, state = queue.popleft()
                    if node:
                        # Yield node or value based on the flag
                        yield (node.value, state) if yield_value else (node, state)

                        # Enqueue both children
                        if node.left:
                            queue.append(
                                (
                                    node.left,
                                    state_handler(node.left, state, True, *args, **kwargs)
                                )
                            )
                        if node.right:
                            queue.append(
                                (
                                    node.right,
                                    state_handler(node.right, state, False, *args, **kwargs)
                                )
                            )
            # endregion

    @classmethod
    def decode_bfs(cls, value_seq: Sequence, pop_queue: Callable[[Sequence], Any] = None):
        """Decode a sequence of values into a binary tree using level-order traversal (BFS).

        Args:
            value_seq (Sequence[Union[T, None]]):
                A sequence of values representing a level-order traversal of the binary tree.
                Use `None` for missing children.

        Returns:
            Optional[BinaryTree[T]]: The root of the reconstructed binary tree, or `None` if the input sequence is empty.

        Examples:
            # Example 1: Decode a simple binary tree
            >>> #      1
            >>> #     / \
            >>> #    2   3
            >>> #       /
            >>> #      4
            >>> values = [1, 2, 3, None, None, 4, None, None, None]
            >>> tree = BinaryTree.decode_bfs(values)
            >>> list(tree.bfs(yield_value=True, decodable=True, allow_tailing_nones=False))
            [1, 2, 3, None, None, 4]

            # Example 2: Decode a binary tree with missing nodes
            >>> #              1
            >>> #           /     \
            >>> #          2       3
            >>> #         /       /
            >>> #        4       6
            >>> #       /
            >>> #      8
            >>> values = [1, 2, 3, 4, None, 6, None, 8]
            >>> tree_with_gaps = BinaryTree.decode_bfs(values)
            >>> list(tree_with_gaps.bfs(yield_value=True, decodable=True, allow_tailing_nones=False))
            [1, 2, 3, 4, None, 6, None, 8]

            # Example 3: Decode an empty tree
            >>> empty_tree = BinaryTree.decode_bfs([])
            >>> empty_tree is None
            True

            # Example 4: Single-node tree
            >>> single_node_tree = BinaryTree.decode_bfs([1])
            >>> list(single_node_tree.bfs(yield_value=True))
            [1]
        """
        if value_seq:
            queue = deque(value_seq)
            root = cls(
                queue.popleft()
                if pop_queue is None
                else pop_queue(queue)
            )
            level = [root]
            while level:
                next_level = []
                for i in range(len(level)):
                    if queue:
                        curr = (
                            queue.popleft()
                            if pop_queue is None
                            else pop_queue(queue)
                        )
                        if curr is not None:
                            curr = cls(curr)
                        level[i].left = curr
                        if curr is not None:
                            next_level.append(curr)
                    if queue:
                        curr = (
                            queue.popleft()
                            if pop_queue is None
                            else pop_queue(queue)
                        )
                        if curr is not None:
                            curr = cls(curr)
                        level[i].right = curr
                        if curr is not None:
                            next_level.append(curr)
                level = next_level
            return root

    @property
    def depth(self):
        """
        Computes the depth of the binary tree.

        The depth (or height) of a binary tree is the number of edges on the longest path
        from the root to a leaf node.

        Returns:
            int: The depth of the tree, measured in number of edges.

        Examples:
            # Example 1: Full binary tree
            >>> #      4
            >>> #     / \
            >>> #    2   6
            >>> #   / \\ / \
            >>> #  1  3 5  7
            >>> node1 = BinaryTree(1, None, None)
            >>> node3 = BinaryTree(3, None, None)
            >>> node5 = BinaryTree(5, None, None)
            >>> node7 = BinaryTree(7, None, None)
            >>> node2 = BinaryTree(2, node1, node3)
            >>> node6 = BinaryTree(6, node5, node7)
            >>> root = BinaryTree(4, node2, node6)
            >>> root.depth
            2

            # Example 2: Single-node binary tree
            >>> root = BinaryTree(42, None, None)
            >>> root.depth
            0

            # Example 3: Left-skewed binary tree
            >>> #      3
            >>> #     /
            >>> #    2
            >>> #   /
            >>> #  1
            >>> node1 = BinaryTree(1, None, None)
            >>> node2 = BinaryTree(2, node1, None)
            >>> root = BinaryTree(3, node2, None)
            >>> root.depth
            2

            # Example 4: Right-skewed binary tree
            >>> #  1
            >>> #   \
            >>> #    2
            >>> #     \
            >>> #      3
            >>> node3 = BinaryTree(3, None, None)
            >>> node2 = BinaryTree(2, None, node3)
            >>> root = BinaryTree(1, None, node2)
            >>> root.depth
            2

        Notes:
            - The depth is measured in the number of edges from the root to the deepest leaf.
            - Time Complexity: This implementation uses a post-order traversal and computes the depth in O(N) time,
              where N is the number of nodes in the tree.
            - Space Complexity: The space complexity is determined by the maximum depth of the recursion stack
              during the post-order traversal, and thus it is O(H) and worst case is O(N).
        """

        def get_depth(_, left, right):
            return max(left or 0, right or 0) + 1

        return self.post_order_dfs_with_result_compute(get_depth) - 1

    @property
    def diameter(self):
        """
        Computes the diameter of the binary tree.

        The diameter of a binary tree is the length of the longest path between any two nodes
        in a tree. This path may or may not pass through the root.

        Returns:
            int: The diameter of the tree, measured in number of edges.

        Examples:
            # Example 1: The longest path is [4,2,1,3] or [5,2,1,3], so the diameter is 3.
            >>> #       1
            >>> #      / \
            >>> #     2   3
            >>> #    / \
            >>> #   4   5
            >>> node4 = BinaryTree(4, None, None)
            >>> node5 = BinaryTree(5, None, None)
            >>> node2 = BinaryTree(2, node4, node5)
            >>> node3 = BinaryTree(3, None, None)
            >>> root = BinaryTree(1, node2, node3)
            >>> root.diameter
            3

            # Example 2: The longest path is [5,4,3,2,1], so the diameter is 4.
            >>> #           1
            >>> #          /
            >>> #         2
            >>> #        /
            >>> #       3
            >>> #      /
            >>> #     4
            >>> #    /
            >>> #   5
            >>> node5 = BinaryTree(5, None, None)
            >>> node4 = BinaryTree(4, node5, None)
            >>> node3 = BinaryTree(3, node4, None)
            >>> node2 = BinaryTree(2, node3, None)
            >>> root = BinaryTree(1, node2, None)
            >>> root.diameter
            4

            >>> # Example 3: The tree has only one node, so the diameter is 0.
            >>> root = BinaryTree(1, None, None)
            >>> root.diameter
            0

        Notes:
            - The diameter is measured in the number of edges between nodes.
            - This implementation uses depth-first search (DFS) and computes the diameter in O(N) time,
              where N is the number of nodes in the tree.
        """

        def compute_diameter(_, left_result, right_result):
            # Unpack results from left and right subtrees
            left_diameter, left_depth = left_result or (0, 0)
            right_diameter, right_depth = right_result or (0, 0)

            # Compute the depth for the current node
            current_depth = max(left_depth, right_depth) + 1

            # Compute the diameter at the current node
            current_diameter = max(
                left_diameter,  # Diameter in the left subtree
                right_diameter,  # Diameter in the right subtree
                left_depth + right_depth  # Path passing through this node
            )

            return current_diameter, current_depth

        # Compute the diameter and return it
        return self.post_order_dfs_with_result_compute(compute_diameter)[0]

    @property
    def right_side_view(self):
        """
        Returns an iterator of the values of the nodes visible from the right side of the binary tree,
        ordered from top to bottom.

        This method performs a breadth-first search (BFS) traversal of the tree using the
        `level_bfs` method with a custom condition (`level_yield_cond`) to collect the
        rightmost node at each level.

        Returns:
            Iterator[T]: An iterator of node values visible from the right side.

        Examples:
            # Example 1:
            >>> # Construct the following tree:
            >>> #       1
            >>> #      / \
            >>> #     2   3
            >>> #      \    \
            >>> #       5    4
            >>> node5 = BinaryTree(5, None, None)
            >>> node4 = BinaryTree(4, None, None)
            >>> node2 = BinaryTree(2, None, node5)
            >>> node3 = BinaryTree(3, None, node4)
            >>> root = BinaryTree(1, node2, node3)
            >>> list(root.right_side_view)
            [1, 3, 4]

            # Example 2:
            >>> # Construct the following tree:
            >>> #       1
            >>> #        \
            >>> #         3
            >>> node3 = BinaryTree(3, None, None)
            >>> root = BinaryTree(1, None, node3)
            >>> list(root.right_side_view)
            [1, 3]

        """

        # Define a custom condition to yield only the last node at each level
        def cond_yield_last(_, idx, size):
            return idx == size - 1

        # Use the level_bfs method with the custom condition
        return self.level_bfs(
            yield_value=True,
            level_yield_cond=cond_yield_last,
            unpack_singleton_level=True
        )

    def encode_with_existence_flags(
            self,
            null_flag: Any,
            existence_flag: Any,
            value_encoder: Callable[[T], Any] = None,
            encode_as_string_sep: str = chr(31)
    ) -> Union[List, str]:
        """
        Encodes the binary tree into a string or list representation.

        This method serializes the binary tree into a sequence of tokens,
        which can be either returned as a list or joined into a string using
        a specified separator. The encoding uses existence flags to indicate
        whether a node exists or is null, and optionally applies a value encoder
        to the node values.

        Parameters:
            null_flag (Any): A marker used to represent null (missing) nodes.
            existence_flag (Any): A marker used to indicate existing nodes.
            value_encoder (Callable, optional): A function to encode node values.
                If None, the node's value is used directly. Defaults to None.
            encode_as_string_sep (str, optional): Separator used to join tokens into a string.
                If None or empty, tokens are returned as a list. Defaults to ','.

        Returns:
            Union[List, str]: The encoded representation of the binary tree,
                either as a list of tokens or a joined string.

        Example:
            # A simple test case
            >>> null_flag = '0'
            >>> existence_flag = '1'
            >>> separator = ','
            >>> value_encoder = str
            >>> # Create a sample binary tree
            >>> #      1
            >>> #     / \
            >>> #    2   3
            >>> left_child = BinaryTree(2,None,None)
            >>> right_child = BinaryTree(3,None,None)
            >>> tree = BinaryTree(1, left_child, right_child)
            >>> tree.encode_with_existence_flags(null_flag, existence_flag, value_encoder, separator)
            '1,1,1,2,1,3'

            # Another test case with null nodes
            >>> null_flag = '0'
            >>> existence_flag = '1'
            >>> separator = ','
            >>> value_encoder = str

            >>> # Construct a tree with some null nodes
            >>> #         10
            >>> #        /  \
            >>> #      None  2
            >>> #           / \
            >>> #         3   None
            >>> right_child = BinaryTree(2, BinaryTree(3, None, None), None)
            >>> tree_with_nulls = BinaryTree(10,None,right_child)

            >>> encoded_representation = tree_with_nulls.encode_with_existence_flags(
            ...     null_flag,
            ...     existence_flag,
            ...     value_encoder,
            ...     separator
            ... )
            >>> encoded_representation
            '1,10,0,1,2,1,3'
        """
        tokens = []
        for node in self.bfs(yield_value=False, decodable=True, allow_tailing_nones=False):
            if node is not None:
                # Node exists
                tokens.append(existence_flag)  # Existence flag
                if value_encoder:
                    tokens.append(value_encoder(node.value))
                else:
                    tokens.append(node.value)
            else:
                # Null node
                tokens.append(null_flag)  # Null flag

        if encode_as_string_sep:
            return encode_as_string_sep.join(map(str, tokens))
        else:
            return tokens

    @classmethod
    def decode_with_existence_flags(
            cls,
            encoding: Union[str, List],
            null_flag: Any,
            existence_flag: Any,
            value_decoder: Callable[[Any], T],
            encode_as_string_sep: str = chr(31)
    ) -> 'BinaryTree[T]':
        """
        Decodes an encoded representation of a binary tree into a `BinaryTree` object.

        This method reconstructs the binary tree from the encoded representation
        produced by the `encode_with_existence_flags` method. It parses the tokens
        and rebuilds the tree using the specified null and existence flags, and applies
        a value decoder to the encoded node values.

        Args:
            encoding (Union[str, List]): The encoded binary tree data, either as a string or list of tokens.
            null_flag (Any): Marker used to represent null (missing) nodes in the encoding.
            existence_flag (Any): Marker used to indicate existing nodes in the encoding.
            value_decoder (Callable): Function to decode node values from their encoded representation.
            encode_as_string_sep (str, optional): Separator used if `encoding` is a string.
                Defaults to `chr(31)`.

        Returns:
            Optional[BinaryTree[T]]: The reconstructed binary tree, or `None` if the encoding is empty or invalid.

        Examples:
            # Example 1: Simple binary tree
            >>> null_flag = '0'
            >>> existence_flag = '1'
            >>> separator = ','
            >>> value_decoder = int
            >>> # Construct an encoded tree
            >>> #      1
            >>> #     / \
            >>> #    2   3
            >>> encoded = '1,1,1,2,1,3'
            >>> tree = BinaryTree.decode_with_existence_flags(encoded, null_flag, existence_flag, value_decoder, separator)
            >>> list(tree.bfs(yield_value=True, decodable=True, allow_tailing_nones=False))
            [1, 2, 3]

            # Example 2: Binary tree with missing nodes
            >>> null_flag = '0'
            >>> existence_flag = '1'
            >>> separator = ','
            >>> value_decoder = int
            >>> # Construct an encoded tree with gaps
            >>> #      1
            >>> #     / \
            >>> #    2   3
            >>> #   /     \
            >>> #  4       6
            >>> encoded = '1,1,1,2,1,3,1,4,0,0,1,6'
            >>> tree_with_gaps = BinaryTree.decode_with_existence_flags(encoded, null_flag, existence_flag, value_decoder, separator)
            >>> list(tree_with_gaps.bfs(yield_value=True, decodable=True, allow_tailing_nones=False))
            [1, 2, 3, 4, None, None, 6]

            # Example 3: Four-level binary tree
            >>> null_flag = '0'
            >>> existence_flag = '1'
            >>> separator = ','
            >>> value_decoder = int
            >>> # Construct a four-level binary tree
            >>> #              1
            >>> #           /     \
            >>> #          2       3
            >>> #         / \     / \
            >>> #        4   5   6   7
            >>> #       / \
            >>> #      8   9
            >>> encoded = '1,1,1,2,1,3,1,4,1,5,1,6,1,7,1,8,1,9'
            >>> tree_4_levels = BinaryTree.decode_with_existence_flags(encoded, null_flag, existence_flag, value_decoder, separator)
            >>> list(tree_4_levels.bfs(yield_value=True, decodable=True, allow_tailing_nones=False))
            [1, 2, 3, 4, 5, 6, 7, 8, 9]
        """
        # Parse the encoding into tokens
        if isinstance(encoding, str):
            tokens = encoding.split(encode_as_string_sep)
        else:
            tokens = encoding

        if not tokens:
            return None

        # Define a custom pop function to handle null and existence flags
        def pop_with_flags(queue):
            if not queue:
                return None
            token = queue.popleft()
            if token == null_flag:
                return None
            elif token == existence_flag:
                if not queue:
                    raise ValueError("Incomplete encoding: expected node value after existence flag.")
                value_token = queue.popleft()
                return (
                    value_token
                    if value_decoder is None
                    else value_decoder(value_token)
                )
            else:
                raise ValueError(f"Invalid token: expected {null_flag} or {existence_flag}, got {token}")

        # Use decode_bfs with the custom pop function
        return cls.decode_bfs(tokens, pop_queue=pop_with_flags)

    def longest_consecutive_sequence(
            self,
            increase_value: Union[T, Callable[[T], T]] = None,
    ) -> int:
        """
        Computes the length of the longest consecutive sequence path in the binary tree.

        A consecutive sequence path is a path where the values increase by one (or as defined by
        the `increase_value` function) along the path. The path can start at any node in the tree,
        and you cannot go from a node to its parent in the path.

        Args:
            increase_value (Callable[[T], T], optional): A function that defines how to compute
                the expected next value in the consecutive sequence. If None, defaults to incrementing
                the value by 1.

        Returns:
            int: The length of the longest consecutive sequence path in the tree.

        Examples:
            # Example 1:
            >>> #      1
            >>> #       \
            >>> #        3
            >>> #       / \
            >>> #      2   4
            >>> #           \
            >>> #            5
            >>> node5 = BinaryTree(5, None, None)
            >>> node4 = BinaryTree(4, None, node5)
            >>> node2 = BinaryTree(2, None, None)
            >>> node3 = BinaryTree(3, node2, node4)
            >>> root = BinaryTree(1, None, node3)
            >>> root.longest_consecutive_sequence()
            3

            # Example 2:
            >>> #      2
            >>> #       \
            >>> #        3
            >>> #       /
            >>> #      2
            >>> #     /
            >>> #    1
            >>> node1 = BinaryTree(1, None, None)
            >>> node2_left = BinaryTree(2, node1, None)
            >>> node3 = BinaryTree(3, node2_left, None)
            >>> root = BinaryTree(2, None, node3)
            >>> root.longest_consecutive_sequence()
            2

        Notes:
            - This implementation uses a post-order traversal and computes the result in O(N) time,
              where N is the number of nodes in the tree.
            - The function handles any custom `increase_value` logic if provided.

        """

        def _compute_next_value(value: T) -> T:
            """
            Computes the expected next value in the consecutive sequence using `increase_value` or defaults to +1.

            Args:
                value (T): The current node's value.

            Returns:
                T: The expected value for the next node in the consecutive sequence.
            """
            if increase_value is not None:
                return increase_value(value) if callable(increase_value) else value + increase_value
            else:
                return value + 1

        def _compute_lcs(curr_node: BinaryTree, left_result: Tuple, right_result: Tuple) -> Tuple[int, int]:
            """
            Computes the longest consecutive sequence (LCS) for the current node.

            Args:
                value (T): The current node's value.
                left_result (Tuple[int, int]): The LCS from the left child.
                right_result (Tuple[int, int]): The LCS from the right child.

            Returns:
                Tuple[int, int]: A tuple containing:
                    - The maximum LCS length found in the subtree rooted at this node.
                    - The LCS length ending at the current node.
            """
            (
                left_lcs,  # LCS in the left subtree
                left_ending  # LCS ending at the left child
            ) = left_result or (0, 0)
            (
                right_lcs,  # LCS in the right subtree
                right_ending  # LCS ending at the right child
            ) = right_result or (0, 0)

            # Start with the node itself
            expected_next_value = _compute_next_value(curr_node.value)

            # Check left child
            if curr_node.left is not None and curr_node.left.value == expected_next_value:
                lcs_ending_here = left_ending + 1
            else:
                lcs_ending_here = 1

            # Check right child
            if curr_node.right is not None and curr_node.right.value == expected_next_value:
                lcs_ending_here = max(lcs_ending_here, right_ending + 1)

            # Max LCS in the subtree
            max_lcs_in_subtree = max(left_lcs, right_lcs, lcs_ending_here)

            return max_lcs_in_subtree, lcs_ending_here

        # Return the longest consecutive sequence in the tree
        return self.post_order_dfs_with_result_compute(_compute_lcs, pass_parent_node_value=False)[0]

    def longest_consecutive_sequence_pre_order_dfs(
            self,
            increase_value: Callable[[T], T] = None,
    ) -> int:
        """
        Computes the length of the longest consecutive sequence path in the binary tree.

        A consecutive sequence path is a path where the values increase by one (or as defined by
        the `increase_value` function) along the path. The path can start at any node in the tree,
        and you cannot go from a node to its parent in the path.

        Args:
            increase_value (Callable[[T], T], optional): A function that defines how to compute
                the expected next value in the consecutive sequence. If None, defaults to incrementing
                the value by 1.

        Returns:
            int: The length of the longest consecutive sequence path in the tree.

        Examples:
            # Example 1:
            >>> #      1
            >>> #       \
            >>> #        3
            >>> #       / \
            >>> #      2   4
            >>> #           \
            >>> #            5
            >>> node5 = BinaryTree(5, None, None)
            >>> node4 = BinaryTree(4, None, node5)
            >>> node2 = BinaryTree(2, None, None)
            >>> node3 = BinaryTree(3, node2, node4)
            >>> root = BinaryTree(1, None, node3)
            >>> root.longest_consecutive_sequence_pre_order_dfs()
            3

            # Example 2:
            >>> #      2
            >>> #       \
            >>> #        3
            >>> #       /
            >>> #      2
            >>> #     /
            >>> #    1
            >>> node1 = BinaryTree(1, None, None)
            >>> node2 = BinaryTree(2, node1, None)
            >>> node3 = BinaryTree(3, node2, None)
            >>> root = BinaryTree(2, None, node3)
            >>> root.longest_consecutive_sequence_pre_order_dfs()
            2

        Notes:
            This implementation uses pre-order traversal to calculate the result efficiently.
        """

        def _compute_next_value(value: T) -> T:
            if increase_value is not None:
                return increase_value(value) if callable(increase_value) else value + increase_value
            else:
                return value + 1

        def _compute_lcs(curr_value: T, global_lcs: int, state):
            if state is None:
                global_lcs = curr_lcs = 1
            else:
                parent_lcs, parent_value = state

                # Determine if the current node continues the consecutive sequence
                if parent_value is not None and curr_value == _compute_next_value(parent_value):
                    curr_lcs = parent_lcs + 1
                else:
                    curr_lcs = 1

                # Update the global maximum consecutive sequence length
                global_lcs = max(global_lcs, curr_lcs)

            return global_lcs, (curr_lcs, curr_value)

        # Perform pre-order DFS traversal and compute the longest consecutive sequence
        return self.pre_order_dfs_with_result_compute(
            _compute_lcs,
            pass_parent_node_value=True
        )

    def largest_path_sum(self, negative_inf=-inf):
        """
         Computes the maximum path sum in the binary tree.

         A path in a binary tree is a sequence of nodes where each pair of adjacent nodes
         in the sequence has an edge connecting them. A node can only appear in the sequence
         at most once. Note that the path does not need to pass through the root.

         Returns:
             T: The maximum path sum of any non-empty path in the tree.

         Examples:
             # Example 1:
             >>> #      1
             >>> #     / \
             >>> #    2   3
             >>> node2 = BinaryTree(2,None,None)
             >>> node3 = BinaryTree(3,None,None)
             >>> root = BinaryTree(1,node2,node3)
             >>> root.largest_path_sum()
             6

             # Example 2:
             >>> #      -10
             >>> #      /  \
             >>> #     9   20
             >>> #        /  \
             >>> #       15   7
             >>> node15 = BinaryTree(15,None,None)
             >>> node7 = BinaryTree(7,None,None)
             >>> node20 = BinaryTree(20,node15,node7)
             >>> node9 = BinaryTree(9,None,None)
             >>> root = BinaryTree(-10,node9,node20)
             >>> root.largest_path_sum()
             42

            # Example 3:
            >>> #          1
            >>> #        /   \
            >>> #      -2     -3
            >>> #     /  \     /
            >>> #    1    3  -2
            >>> #   /
            >>> # -1
            >>> node_minus1 = BinaryTree(-1,None,None)
            >>> node1_left = BinaryTree(1,node_minus1,None)
            >>> node3 = BinaryTree(3,None,None)
            >>> node_minus2_left = BinaryTree(-2,node1_left,node3)
            >>> node_minus2_right = BinaryTree(-2,None,None)
            >>> node_minus3 = BinaryTree(-3,node_minus2_right,None)
            >>> root = BinaryTree(1,node_minus2_left,node_minus3)
            >>> root.largest_path_sum()
            3
         """

        def _compute_max_path_sum(
                node_value: T,
                left_result: Tuple[T, T],
                right_result: Tuple[T, T]
        ) -> Tuple[T, T]:
            """
            Computes the maximum path sum for the current node.

            Args:
                node_value (T): The value of the current node.
                left_result (Tuple[T, T]): The maximum path sum and maximum sum ending at the left child.
                right_result (Tuple[T, T]): The maximum path sum and maximum sum ending at the right child.

            Returns:
                Tuple[T, T]: A tuple containing:
                    - The maximum path sum found in the subtree rooted at this node.
                    - The maximum sum of any path ending at this node.
            """
            left_path_sum, left_ending_sum = left_result or (negative_inf, negative_inf)
            right_path_sum, right_ending_sum = right_result or (negative_inf, negative_inf)

            # Maximum path sum ending at the current node
            max_ending_at_curr = max(
                node_value,
                node_value + left_ending_sum,
                node_value + right_ending_sum,
            )

            # Maximum path sum in the subtree rooted at the current node
            max_in_subtree = max(
                left_path_sum,
                right_path_sum,
                max_ending_at_curr,
                node_value + left_ending_sum + right_ending_sum,  # Path through this node
            )

            return max_in_subtree, max_ending_at_curr

        # Compute the largest path sum using post-order traversal
        return self.post_order_dfs_with_result_compute(_compute_max_path_sum)[0]

    def vertical_order_traversal(self, yield_value: bool = True) -> Iterator[List[Union['BinaryTree[T]', Any]]]:
        """
        Perform vertical order traversal of the binary tree.

        Args:
            yield_value (bool): If True, yields the node values instead of the nodes themselves. Defaults to True.

        Yields:
            List[Union[BinaryTree[T], Any]]: A list of node values or nodes in each vertical column, ordered left to right.

        Example:
        # Example 1: Basic binary tree
        >>> # Tree Structure:
        >>> #      3
        >>> #     / \
        >>> #    9  20
        >>> #       / \
        >>> #      15  7
        >>> tree = BinaryTree(
        ...     value=3,
        ...     left=BinaryTree(value=9),
        ...     right=BinaryTree(
        ...         value=20,
        ...         left=BinaryTree(value=15),
        ...         right=BinaryTree(value=7)
        ...     )
        ... )
        >>> list(tree.vertical_order_traversal(yield_value=True))
        [[9], [3, 15], [20], [7]]

        # Example 2: Binary tree with overlapping columns
        >>> # Tree Structure:
        >>> #      1
        >>> #     / \
        >>> #    2   3
        >>> #   / \ / \
        >>> #  4  5 6  7
        >>> tree_with_overlap = BinaryTree(
        ...     value=1,
        ...     left=BinaryTree(
        ...         value=2,
        ...         left=BinaryTree(value=4),
        ...         right=BinaryTree(value=5)
        ...     ),
        ...     right=BinaryTree(
        ...         value=3,
        ...         left=BinaryTree(value=6),
        ...         right=BinaryTree(value=7)
        ...     )
        ... )
        >>> list(tree_with_overlap.vertical_order_traversal(yield_value=True))
        [[4], [2], [1, 5, 6], [3], [7]]

        # Example 3: Complex binary tree with multiple levels
        >>> # Tree Structure:
        >>> #              10
        >>> #           /      \
        >>> #         5         20
        >>> #       /  \       /  \
        >>> #      3    7    15   25
        >>> #     / \         \
        >>> #    2   4        17
        >>> complex_tree = BinaryTree(
        ...     value=10,
        ...     left=BinaryTree(
        ...         value=5,
        ...         left=BinaryTree(
        ...             value=3,
        ...             left=BinaryTree(value=2),
        ...             right=BinaryTree(value=4)
        ...         ),
        ...         right=BinaryTree(value=7)
        ...     ),
        ...     right=BinaryTree(
        ...         value=20,
        ...         left=BinaryTree(
        ...             value=15,
        ...             right=BinaryTree(value=17)
        ...         ),
        ...         right=BinaryTree(value=25)
        ...     )
        ... )
        >>> list(complex_tree.vertical_order_traversal(yield_value=True))
        [[2], [3], [5, 4], [10, 7, 15], [20, 17], [25]]
        """
        vertical_order_dict = defaultdict(list)

        def _vertical_order_state_handler(_, prev_state, is_left):
            if prev_state is None:
                return 0
            return prev_state - 1 if is_left else prev_state + 1

        for node, vertical_order in self.bfs(
                yield_value=False,
                decodable=False,
                allow_tailing_nones=False,
                state_handler=_vertical_order_state_handler
        ):
            vertical_order_dict[vertical_order].append(node.value if yield_value else node)

        yield from (v for _, v in sorted(vertical_order_dict.items()))

    def lowest_common_ancestor(self, p: 'BinaryTree[T]', q: 'BinaryTree[T]') -> 'BinaryTree[T]':
        """
        Finds the lowest common ancestor (LCA) of two nodes `p` and `q` in the binary tree.
        Only returns None if both `p` and `q` are not found in the tree.

        The lowest common ancestor of two nodes `p` and `q` is defined as the lowest node in the tree
        that has both `p` and `q` as descendants (where we allow a node to be a descendant of itself).

        This implementation uses a post-order traversal to compute the LCA efficiently.

        Args:
            p (BinaryTree[T]): The first node for which to find the LCA.
            q (BinaryTree[T]): The second node for which to find the LCA.

        Returns:
            BinaryTree[T]: The LCA node of `p` and `q`.

        Examples:
            # Example 1: Full binary tree
            >>> #       3
            >>> #      / \
            >>> #     5   1
            >>> #    / \ / \
            >>> #   6  2 0  8
            >>> #     / \
            >>> #    7   4
            >>> node6 = BinaryTree(6)
            >>> node7 = BinaryTree(7)
            >>> node4 = BinaryTree(4)
            >>> node2 = BinaryTree(2, node7, node4)
            >>> node5 = BinaryTree(5, node6, node2)
            >>> node0 = BinaryTree(0)
            >>> node8 = BinaryTree(8)
            >>> node1 = BinaryTree(1, node0, node8)
            >>> root = BinaryTree(3, node5, node1)
            >>> root.lowest_common_ancestor(node5, node1).value
            3
            >>> root.lowest_common_ancestor(node5, node4).value
            5

            # Example 2: Skewed tree (right-leaning)
            >>> #  1
            >>> #   \
            >>> #    2
            >>> #     \
            >>> #      3
            >>> node3 = BinaryTree(3)
            >>> node2 = BinaryTree(2, None, node3)
            >>> root = BinaryTree(1, None, node2)
            >>> root.lowest_common_ancestor(node2, node3).value
            2

            # Example 3: Single-node tree
            >>> root = BinaryTree(42)
            >>> root.lowest_common_ancestor(root, root).value
            42

            # Example 4: Left-heavy tree
            >>> #      5
            >>> #     /
            >>> #    3
            >>> #   /
            >>> #  1
            >>> node1 = BinaryTree(1)
            >>> node3 = BinaryTree(3, node1, None)
            >>> root = BinaryTree(5, node3, None)
            >>> root.lowest_common_ancestor(node1, node3).value
            3
        """

        # This implementation uses a post-order traversal to compute the LCA efficiently, leveraging two
        # callback functions:
        #  1. `early_termination_at_parent_node`: Stops the traversal early if `p` or `q` is encountered.
        #  2. `compute_lca_at_parent_node`: Determines the LCA based on results from the left and right subtrees.

        # The following implements this pseudo logic
        # function lowestCommonAncestor(root, p, q):
        #     if root == p or root == q:
        #         return root
        #     if root.left is not null:
        #       left  = lowestCommonAncestor(root.left,  p, q)
        #     if root.right is not null:
        #       right = lowestCommonAncestor(root.right, p, q)
        #
        #     if left != null and right != null:
        #         return root
        #
        #     return left or right

        def early_termination_at_parent_node(parent_node: 'BinaryTree[T]'):
            if parent_node == p or parent_node == q:
                return parent_node

        def compute_lca_at_parent_node(
                parent_node: 'BinaryTree[T]',
                left_result: 'BinaryTree[T]',
                right_result: 'BinaryTree[T]'
        ):
            if left_result is not None and right_result is not None:
                return parent_node

            return left_result or right_result

        return self.post_order_dfs_with_result_compute(
            compute_lca_at_parent_node,
            pass_parent_node_value=False,
            early_termination_at_parent_node=early_termination_at_parent_node
        )

    def lowest_common_ancestor2(self, p: 'BinaryTree[T]', q: 'BinaryTree[T]') -> Optional['BinaryTree[T]']:
        """
        Finds the lowest common ancestor (LCA) of two nodes `p` and `q` in the binary tree.

        If either `p` or `q` does not exist in the tree, returns `None`.

        Args:
            p (BinaryTree[T]): The first node for which to find the LCA.
            q (BinaryTree[T]): The second node for which to find the LCA.

        Returns:
            Optional[BinaryTree[T]]: The LCA node of `p` and `q`, or `None` if either is not in the tree.

        Examples:
            # Example 1: Full binary tree
            >>> #       3
            >>> #      / \
            >>> #     5   1
            >>> #    / \ / \
            >>> #   6  2 0  8
            >>> #     / \
            >>> #    7   4
            >>> node6 = BinaryTree(6)
            >>> node7 = BinaryTree(7)
            >>> node4 = BinaryTree(4)
            >>> node2 = BinaryTree(2, node7, node4)
            >>> node5 = BinaryTree(5, node6, node2)
            >>> node0 = BinaryTree(0)
            >>> node8 = BinaryTree(8)
            >>> node1 = BinaryTree(1, node0, node8)
            >>> root = BinaryTree(3, node5, node1)
            >>> root.lowest_common_ancestor2(node5, node1).value
            3
            >>> root.lowest_common_ancestor2(node5, node4).value
            5

            # Example 2: Skewed tree (right-leaning)
            >>> #  1
            >>> #   \
            >>> #    2
            >>> #     \
            >>> #      3
            >>> node3 = BinaryTree(3)
            >>> node2 = BinaryTree(2, None, node3)
            >>> root = BinaryTree(1, None, node2)
            >>> root.lowest_common_ancestor2(node2, node3).value
            2

            # Example 3: Single-node tree
            >>> root = BinaryTree(42)
            >>> root.lowest_common_ancestor2(root, root).value
            42

            # Example 4: Left-heavy tree
            >>> #      5
            >>> #     /
            >>> #    3
            >>> #   /
            >>> #  1
            >>> node1 = BinaryTree(1)
            >>> node3 = BinaryTree(3, node1, None)
            >>> root = BinaryTree(5, node3, None)
            >>> root.lowest_common_ancestor2(node1, node3).value
            3

            # Example 5: One node does not exist
            >>> #       3
            >>> #      / \
            >>> #     5   1
            >>> node5 = BinaryTree(5)
            >>> node1 = BinaryTree(1)
            >>> root = BinaryTree(3, node5, node1)
            >>> non_existent_node = BinaryTree(10)  # Node not part of the tree
            >>> root.lowest_common_ancestor2(node5, non_existent_node) is None
            True

            # Example 6: Both nodes do not exist
            >>> non_existent_node1 = BinaryTree(100)
            >>> non_existent_node2 = BinaryTree(200)
            >>> root.lowest_common_ancestor2(non_existent_node1, non_existent_node2) is None
            True

            # Example 7: Root node as LCA
            >>> #       3
            >>> #      / \
            >>> #     5   1
            >>> root.lowest_common_ancestor2(node5, node1).value
            3
        """

        def compute_lca_at_parent_node(
                parent_node: 'BinaryTree[T]',
                left_result: Tuple[Optional['BinaryTree[T]'], bool, bool],
                right_result: Tuple[Optional['BinaryTree[T]'], bool, bool]
        ) -> Tuple[Optional['BinaryTree[T]'], bool, bool]:
            """
            Computes the LCA at the current node and tracks the presence of `p` and `q`.

            Args:
                parent_node: The current node being processed.
                left_result: Results from the left subtree (LCA, has_p, has_q).
                right_result: Results from the right subtree (LCA, has_p, has_q).

            Returns:
                Tuple:
                    - The LCA node (or `None` if not found yet).
                    - Whether `p` was found in the subtree rooted at this node.
                    - Whether `q` was found in the subtree rooted at this node.
            """
            # Extract results from left and right subtrees
            left_lca, left_has_p, left_has_q = left_result or (None, False, False)
            right_lca, right_has_p, right_has_q = right_result or (None, False, False)

            # Check if the current node is `p` or `q`
            current_has_p = parent_node == p
            current_has_q = parent_node == q

            # Aggregate whether `p` and `q` are found
            has_p = current_has_p or left_has_p or right_has_p
            has_q = current_has_q or left_has_q or right_has_q

            # Determine the LCA
            if current_has_p or current_has_q:
                # If the current node is one of the targets, it could be the LCA
                return parent_node, has_p, has_q
            if left_lca and right_lca:
                # If both subtrees return non-null LCAs, the current node is the LCA
                return parent_node, has_p, has_q
            if left_lca:
                return left_lca, has_p, has_q
            if right_lca:
                return right_lca, has_p, has_q

            # If no LCA is found, return None
            return None, has_p, has_q

        # Perform post-order DFS to compute the LCA and track presence of `p` and `q`
        lca, found_p, found_q = self.post_order_dfs_with_result_compute(
            compute_lca_at_parent_node,
            pass_parent_node_value=False
        )

        # If both `p` and `q` are found, return the LCA; otherwise, return None
        return lca if found_p and found_q else None

    # region BST related

    def is_binary_search_tree(self):
        """
        Checks if the binary tree is a valid Binary Search Tree (BST).
        This version leverates `depth_first_search` for the recursion.

        A binary tree is a valid BST if:
        - The left subtree of a node contains only nodes with keys less than the node's key.
        - The right subtree of a node contains only nodes with keys greater than the node's key.
        - Both the left and right subtrees must also be valid BSTs.

        Returns:
            bool: True if the tree is a valid BST, False otherwise.

        Examples:
            # Example 1: Valid BST
            >>> # Construct the following tree:
            >>> #      2
            >>> #     / \
            >>> #    1   3
            >>> left = BinaryTree(1,None,None)
            >>> right = BinaryTree(3,None,None)
            >>> root = BinaryTree(2,left,right)
            >>> root.is_binary_search_tree()
            True

            # Example 2: Invalid BST
            >>> # Construct the following tree:
            >>> #      5
            >>> #     / \
            >>> #    1   4
            >>> #       / \
            >>> #      3   6
            >>> left = BinaryTree(1,None,None)
            >>> right_left = BinaryTree(3,None,None)
            >>> right_right = BinaryTree(6,None,None)
            >>> right = BinaryTree(4,right_left,right_right)
            >>> root = BinaryTree(5,left,right)
            >>> root.is_binary_search_tree()
            False

            # Example 3: Invalid BST [5,4,6,null,null,3,7]
            >>> # Construct the following tree:
            >>> #      5
            >>> #     / \
            >>> #    4   6
            >>> #       / \
            >>> #      3   7
            >>> left = BinaryTree(4,None,None)
            >>> right_left = BinaryTree(3,None,None)
            >>> right_right = BinaryTree(7,None,None)
            >>> right = BinaryTree(6,right_left,right_right)
            >>> root = BinaryTree(5,left,right)
            >>> root.is_binary_search_tree()
            False

            # Construct the following tree:
            >>> #            10
            >>> #           /  \
            >>> #          5    15
            >>> #         / \   / \
            >>> #        2   8 12  20
            >>>
            >>> left_left = BinaryTree(2,None,None)
            >>> left_right = BinaryTree(8,None,None)
            >>> right_left = BinaryTree(12,None,None)
            >>> right_right = BinaryTree(20,None,None)
            >>> left = BinaryTree(5,left_left,left_right)
            >>> right = BinaryTree(15,right_left,right_right)
            >>> root = BinaryTree(10,left,right)
            >>> root.is_binary_search_tree()
            True

        Notes:
            - This implementation uses depth-first search (DFS) to verify the BST properties.
            - Time Complexity: O(n), where n is the number of nodes in the tree.
            - Space Complexity: O(h), where h is the height of the tree, due to the recursion stack.

        """

        def _test_bst_at_parent_node(parent_node_value, left_result, right_result):
            if left_result is None:
                is_left_child_bst_compliant = True
                left_min_value = parent_node_value
            else:
                is_left_child_bst_compliant, left_min_value, left_max_value = left_result
                is_left_child_bst_compliant = is_left_child_bst_compliant and left_max_value < parent_node_value

            if right_result is None:
                is_right_child_bst_compliant = True
                right_max_value = parent_node_value
            else:
                is_right_child_bst_compliant, right_min_value, right_max_value = right_result
                is_right_child_bst_compliant = is_right_child_bst_compliant and right_min_value > parent_node_value

            return (
                (is_left_child_bst_compliant and is_right_child_bst_compliant),
                left_min_value,
                right_max_value
            )

        return self.post_order_dfs_with_result_compute(_test_bst_at_parent_node)[0]

    def iter_binary_search_tree(self, yield_value: bool = True):
        """
        Iterates over the elements of the binary search tree (BST) in in-order traversal.

        This method generates the values of the BST in ascending order using a generator.
        It leverages depth-first search (DFS) to perform an in-order traversal.

        Args:
            yield_value (bool, optional): If True, yields the value of each node.
                                          If False, yields the nodes themselves. Defaults to True.


        Yields:
            T: The next value in the in-order traversal of the BST.

        Examples:
            >>> # Example 1: Valid BST
            >>> # Construct the following tree:
            >>> #      4
            >>> #     / \
            >>> #    2   6
            >>> #   / \\ / \
            >>> #  1  3 5  7
            >>> node1 = BinaryTree(1,None,None)
            >>> node3 = BinaryTree(3,None,None)
            >>> node5 = BinaryTree(5,None,None)
            >>> node7 = BinaryTree(7,None,None)
            >>> node2 = BinaryTree(2,node1,node3)
            >>> node6 = BinaryTree(6,node5,node7)
            >>> root = BinaryTree(4,node2,node6)
            >>> list(root.iter_binary_search_tree())
            [1, 2, 3, 4, 5, 6, 7]

            >>> # Example 2: Single-node BST
            >>> root = BinaryTree(1,None,None)
            >>> list(root.iter_binary_search_tree())
            [1]

            >>> # Example 3: Empty tree
            >>> root = None
            >>> if root:
            ...     list(root.iter_binary_search_tree())
            ... else:
            ...     []
            []

        Notes:
            - This implementation assumes the binary tree is a valid BST.
            - Time Complexity: O(n), where n is the number of nodes in the tree.
            - Space Complexity: O(h), where h is the height of the tree, due to the recursion stack.
        """

        return self.in_order_dfs(yield_value=yield_value)

    def binary_search_tree_to_circular_doubly_linked_list_in_place(self):
        """
        Converts a binary search tree (BST) into a circular doubly linked list in-place.

        The in-order traversal of the BST is used to link the nodes such that:
        - Each node's left pointer points to its predecessor in the in-order traversal.
        - Each node's right pointer points to its successor in the in-order traversal.
        - The first and last nodes are linked to form a circular doubly linked list.

        Returns:
            BinaryTree[T]: The first node in the circular doubly linked list.

        Examples:
            >>> # Example 1: Full binary tree
            >>> # Construct the following tree:
            >>> #      4
            >>> #     / \
            >>> #    2   6
            >>> #   / \\ / \
            >>> #  1  3 5  7
            >>> node1 = BinaryTree(1,None,None)
            >>> node3 = BinaryTree(3,None,None)
            >>> node5 = BinaryTree(5,None,None)
            >>> node7 = BinaryTree(7,None,None)
            >>> node2 = BinaryTree(2,node1,node3)
            >>> node6 = BinaryTree(6,node5,node7)
            >>> root = BinaryTree(4,node2,node6)
            >>> first_node = root.binary_search_tree_to_circular_doubly_linked_list_in_place()
            >>> # Traverse the circular doubly linked list starting from the first node
            >>> result = []
            >>> current = first_node
            >>> for _ in range(7):  # Stop after visiting 7 nodes to avoid infinite loop
            ...     result.append(current.value)
            ...     current = current.right
            >>> result
            [1, 2, 3, 4, 5, 6, 7]
            >>> # Check backward traversal
            >>> result = []
            >>> for _ in range(7):  # Stop after visiting 7 nodes to avoid infinite loop
            ...     current = current.left
            ...     result.append(current.value)
            >>> result.reverse()
            >>> result
            [1, 2, 3, 4, 5, 6, 7]

            >>> # Example 2: Single-node binary tree
            >>> root = BinaryTree(42,None,None)
            >>> first_node = root.binary_search_tree_to_circular_doubly_linked_list_in_place()
            >>> first_node.value
            42
            >>> first_node.right == first_node
            True
            >>> first_node.left == first_node
            True

            >>> # Example 3: Binary tree with only left children
            >>> # Construct the following tree:
            >>> #      3
            >>> #     /
            >>> #    2
            >>> #   /
            >>> #  1
            >>> node1 = BinaryTree(1,None,None)
            >>> node2 = BinaryTree(2,node1,None)
            >>> root = BinaryTree(3,node2,None)
            >>> first_node = root.binary_search_tree_to_circular_doubly_linked_list_in_place()
            >>> result = []
            >>> current = first_node
            >>> for _ in range(3):  # Stop after visiting 3 nodes to avoid infinite loop
            ...     result.append(current.value)
            ...     current = current.right
            >>> result
            [1, 2, 3]
            >>> # Check backward traversal
            >>> result = []
            >>> for _ in range(3):  # Stop after visiting 3 nodes to avoid infinite loop
            ...     current = current.left
            ...     result.append(current.value)
            >>> result.reverse()
            >>> result
            [1, 2, 3]

        Notes:
            - The method assumes the binary tree is a valid binary search tree (BST).
            - The conversion is performed in-place, modifying the node pointers directly.
            - Time Complexity: O(n), where n is the number of nodes in the BST.
            - Space Complexity: O(h), where h is the height of the tree, due to the recursion stack during in-order traversal.
        """
        prev_node = first_node = None
        for node in self.in_order_dfs(yield_value=False):
            if not first_node:
                prev_node = first_node = node
            else:
                # prev_node has already been visited, so its right pointer won't be used again in traversal
                prev_node.right = node
                # similarly because left child has been visited, the left pointer won't be needed again in traversal
                node.left = prev_node
                prev_node = node

        first_node.left, prev_node.right = prev_node, first_node

        return first_node

    def add_value_to_binary_search_tree(self, value: T):
        """
        Adds a value to the binary search tree (BST) in its appropriate position.

        This method inserts a new value into the BST following the BST property:
        - If the value is less than the current node's value, it goes to the left subtree.
        - If the value is greater than the current node's value, it goes to the right subtree.
        - Duplicate values are not added to the BST.

        Args:
            value (T): The value to be added to the binary search tree.

        Examples:
            >>> # Example 1: Adding to an empty binary tree
            >>> root = BinaryTree(10,None,None)
            >>> root.add_value_to_binary_search_tree(5)
            >>> root.add_value_to_binary_search_tree(15)
            >>> root.add_value_to_binary_search_tree(12)
            >>> root.add_value_to_binary_search_tree(17)
            >>> list(root.iter_binary_search_tree())
            [5, 10, 12, 15, 17]

            >>> # Example 2: Adding duplicate values
            >>> root = BinaryTree(20,None,None)
            >>> root.add_value_to_binary_search_tree(10)
            >>> root.add_value_to_binary_search_tree(30)
            >>> root.add_value_to_binary_search_tree(10)  # Duplicate value, should not be added
            >>> list(root.iter_binary_search_tree())
            [10, 20, 30]

            >>> # Example 3: Adding multiple values to a single-node tree
            >>> root = BinaryTree(50,None,None)
            >>> values_to_add = [25, 75, 10, 30, 60, 80]
            >>> for value in values_to_add:
            ...     root.add_value_to_binary_search_tree(value)
            >>> list(root.iter_binary_search_tree())
            [10, 25, 30, 50, 60, 75, 80]

        Notes:
            - The method assumes the binary tree is a valid binary search tree (BST).
            - Time Complexity: O(h), where h is the height of the BST.
            - Space Complexity: O(h), where h is the height of the BST, due to recursion.
        """

        def _dfs(node: BinaryTree):
            if value < node.value:
                if not node.left:
                    node.left = BinaryTree(value, None, None)
                else:
                    _dfs(node.left)
            elif value > node.value:
                if not node.right:
                    node.right = BinaryTree(value, None, None)
                else:
                    _dfs(node.right)

        _dfs(self)

    @classmethod
    def sequence_to_binary_search_tree(cls, seq: Iterable[T]) -> 'BinaryTree[T]':
        """
        Creates a binary search tree (BST) from a sequence of values.

        This method takes an iterable sequence of values and constructs a BST by adding
        each value to the tree in the order they appear in the sequence. The first value
        in the sequence becomes the root of the tree.

        Args:
            seq (Iterable[T]): The sequence of values to construct the BST.

        Returns:
            Optional[BinaryTree[T]]: The root of the created binary search tree,
            or None if the sequence is empty.

        Examples:
            >>> # Example 1: Creating a BST from a list of values
            >>> seq = [10, 5, 15, 3, 7, 12, 18]
            >>> root = BinaryTree.sequence_to_binary_search_tree(seq)
            >>> list(root.iter_binary_search_tree())
            [3, 5, 7, 10, 12, 15, 18]

            >>> # Example 2: Creating a BST from a sorted sequence
            >>> seq = [1, 2, 3, 4, 5]
            >>> root = BinaryTree.sequence_to_binary_search_tree(seq)
            >>> list(root.iter_binary_search_tree())
            [1, 2, 3, 4, 5]

            >>> # Example 3: Creating a BST from a single-element sequence
            >>> seq = [42]
            >>> root = BinaryTree.sequence_to_binary_search_tree(seq)
            >>> list(root.iter_binary_search_tree())
            [42]

            >>> # Example 4: Creating a BST from an empty sequence
            >>> seq = []
            >>> root = BinaryTree.sequence_to_binary_search_tree(seq)
            >>> root is None
            True

        Notes:
            - The method assumes the input sequence contains unique values for a valid BST.
            - Time Complexity: O(n * h), where n is the number of elements in the sequence,
              and h is the height of the BST during insertion.
            - Space Complexity: O(h), where h is the height of the BST, due to recursion
              during insertion.
        """
        it = iter(seq)
        try:
            first_value = next(it)
        except StopIteration:
            return None

        root = BinaryTree(first_value, None, None)
        for value in it:
            root.add_value_to_binary_search_tree(value)
        return root

    @classmethod
    def sorted_array_to_binary_search_tree(cls, arr: List[T]) -> Optional['BinaryTree[T]']:
        """
        Converts a sorted array into a height-balanced binary search tree (BST).

        This method uses the `binary_post_order_result_compute` function to construct a BST
        in O(n) time, ensuring the tree is height-balanced. The middle element of the array
        (or subarray) is chosen as the root node.

        Args:
            arr (List[T]): The sorted array of values to construct the BST.

        Returns:
            Optional[BinaryTree[T]]: The root of the created BST, or None if the array is empty.

        Examples:
            # Example 1: Creating a balanced BST from a sorted array
            >>> arr = [1, 2, 3, 4, 5, 6, 7]
            >>> root = BinaryTree.sorted_array_to_binary_search_tree(arr)
            >>> list(root.iter_binary_search_tree())
            [1, 2, 3, 4, 5, 6, 7]

            # Example 2: Creating a BST from an empty array
            >>> arr = []
            >>> root = BinaryTree.sorted_array_to_binary_search_tree(arr)
            >>> root is None
            True

            # Example 3: Single-element array
            >>> arr = [42]
            >>> root = BinaryTree.sorted_array_to_binary_search_tree(arr)
            >>> list(root.iter_binary_search_tree())
            [42]

        Notes:
            - This method assumes the input array is sorted in ascending order.
            - The resulting BST is height-balanced, meaning the depth of the two subtrees
              of every node never differs by more than 1.
            - Time Complexity: O(n), where n is the size of the array.
            - Space Complexity: O(log n), due to recursion stack during construction.
        """

        def _build_node(
                seq: List[T],
                mid_index: int,
                left: Optional['BinaryTree[T]'],
                right: Optional['BinaryTree[T]']
        ):
            # Construct a binary tree node using the middle element as the root
            return cls(seq[mid_index], left, right)

        # If the array is empty, return None
        if not arr:
            return None

        # Use `binary_post_order_result_compute` to construct the BST
        return binary_post_order_result_compute(arr, _build_node)

    # endregion
