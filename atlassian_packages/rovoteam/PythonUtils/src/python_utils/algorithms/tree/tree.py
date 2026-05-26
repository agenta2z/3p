from collections import deque
from typing import Any, Callable, List, Union, Optional

from python_utils.algorithms.graph.node import Node
from python_utils.algorithms.tree.traversal import bfs_traversal
from python_utils.string_utils import join_


class Tree(Node):
    def encode(
            self,
            null_flag: Any,
            value_encoder: Callable = None,
            encode_as_string_sep: str = chr(31)
    ) -> Union[List, str]:
        """
        Encodes the tree into a string or list representation.

        This method serializes the tree into a sequence of tokens using a breadth-first traversal.
        For each node, it records the node's value and the number of children.
        If a node is None, it appends the `null_flag`.

        Parameters:
            null_flag (Any): A marker used to represent null (missing) nodes.
            value_encoder (Callable): A function to encode node values.
                Defaults to None.
            encode_as_string_sep (str): Separator used to join tokens into a string.
                If `None` or empty, tokens are returned as a list.
                Defaults to `','`.

        Returns:
            Union[List, str]: The encoded representation of the tree,
                either as a list of tokens or a joined string.

        Example:
            # Create a sample tree:
            >>> #        1
            >>> #      / | \
            >>> #     2  3  4
            >>> node2 = Tree(None, 2)
            >>> node3 = Tree(None, 3)
            >>> node4 = Tree(None, 4)
            >>> root = Tree([node2, node3, node4], 1)
            >>> root.encode_with_existence_flags(null_flag='null', value_encoder=str, encode_as_string_sep=',')
            '1,3,2,0,3,0,4,0'

            # More complex example:
            >>> null_flag = 'null'
            >>> separator = ','
            >>> value_encoder = str
            >>> # Tree Structure:
            >>> #        10
            >>> #       /  \
            >>> #      20  30
            >>> #     /   /  \
            >>> #    40  50  60
            >>> #            /
            >>> #           70
            >>> node70 = Tree([], 70)
            >>> node60 = Tree([node70], 60)
            >>> node50 = Tree([], 50)
            >>> node40 = Tree([], 40)
            >>> node20 = Tree([node40], 20)
            >>> node30 = Tree([node50, node60], 30)
            >>> root = Tree([node20, node30], 10)
            >>> root.encode_with_existence_flags(null_flag, value_encoder, separator)
            '10,2,20,1,30,2,40,0,50,0,60,1,70,0'
        """
        tokens = []
        queue = deque([self])

        while queue:
            node = queue.popleft()
            if node is None:
                tokens.append(null_flag)
            else:
                # Encode the node's value
                tokens.append(value_encoder(node.value))
                # Record the number of children
                if node.next:
                    tokens.append(len(node.next))
                    queue.extend(node.next)
                else:
                    tokens.append(0)

        if encode_as_string_sep:
            return join_(tokens, sep=encode_as_string_sep)
        else:
            return tokens

    @classmethod
    def decode(
            cls,
            encoding: Union[str, List[str]],
            null_flag: Any,
            value_decoder: Callable = None,
            encode_as_string_sep: str = chr(31)
    ) -> 'Tree':
        """
        Decodes the encoded data back into a Tree.

        This method reconstructs the tree from the encoded representation produced by the `encode` method.
        It uses a breadth-first traversal to parse the tokens and rebuild the tree.

        Parameters:
            encoding (Union[str, List[str]]): The encoded tree data, either as a string or list of tokens.
            null_flag (Any): The marker used to represent null (missing) nodes in the encoding.
            value_decoder (Callable): A function to decode node values from their encoded representation.
                Defaults to None.
            encode_as_string_sep (str): Separator used if encoding is a string.
                Defaults to `','`.

        Returns:
            Optional[Tree]: The reconstructed tree.

        Examples:
            # Decoding the simple tree example:
            >>> encoding = '1,3,2,0,3,0,4,0'
            >>> null_flag = 'null'
            >>> value_decoder = int
            >>> root = Tree.decode_with_existence_flags(encoding, null_flag, value_decoder, ',')
            >>> root.value
            1
            >>> [child.value for child in root.next]
            [2, 3, 4]

            # Decoding the complex tree example:
            >>> encoding = '10,2,20,1,30,2,40,0,50,0,60,1,70,0'
            >>> null_flag = 'null'
            >>> value_decoder = int
            >>> root = Tree.decode_with_existence_flags(encoding, null_flag, value_decoder, ',')
            >>> root.value
            10
            >>> [child.value for child in root.next]
            [20, 30]
            >>> root.next[0].next[0].value
            40
            >>> root.next[1].next[0].value
            50
            >>> root.next[1].next[1].next[0].value
            70
        """
        if isinstance(encoding, str):
            tokens = encoding.split(encode_as_string_sep)
        else:
            tokens = encoding

        index = 0
        if index >= len(tokens):
            return Tree(None, None)  # Empty encoding, return None

        token = tokens[index]
        index += 1

        if token == null_flag:
            return Tree(None, None)
        else:
            value = value_decoder(token)
            if index >= len(tokens):
                raise ValueError("Incomplete encoding: expected number of children.")
            num_children_token = tokens[index]
            index += 1
            num_children = int(num_children_token)
            root = cls([], value)
            queue = deque()
            queue.append((root, num_children))

        while queue:
            node, num_children = queue.popleft()
            children = []
            for _ in range(num_children):
                if index >= len(tokens):
                    raise ValueError("Incomplete encoding: expected node value or null flag.")
                token = tokens[index]
                index += 1
                if token == str(null_flag):
                    child = None
                else:
                    value = value_decoder(token)
                    if index >= len(tokens):
                        raise ValueError("Incomplete encoding: expected number of children.")
                    num_children_token = tokens[index]
                    index += 1
                    child_num_children = int(num_children_token)
                    child = cls([], value)
                    queue.append((child, child_num_children))
                children.append(child)
            node.next = children

        return root

    def num_nodes(self) -> int:
        """Returns the total number of nodes in the tree rooted at this node.

        Uses :func:`bfs_traversal` to count all reachable nodes.

        Returns:
            int: The total node count (including this node).

        Examples:
            >>> root = Tree("A")
            >>> root.add_next(Tree("B"))
            >>> root.add_next(Tree("C"))
            >>> root.next[0].add_next(Tree("D"))
            >>> root.num_nodes()
            4
            >>> Tree("solo").num_nodes()
            1
        """
        return sum(1 for _ in bfs_traversal(self))