from python_utils.algorithms.array.binary_search import binary_post_order_result_compute
from python_utils.algorithms.array.subarray import max_subarray_sum
from python_utils.algorithms.tree.binary_tree import BinaryTree

"""
In-Order Traversal
"""
BinaryTree.in_order_dfs
BinaryTree.iter_binary_search_tree # exactly same algorithm as in-order traversal
BinaryTree.binary_search_tree_to_circular_doubly_linked_list_in_place # a simple extension of in-order traversal

"""
Post-Order Traversal
"""
BinaryTree.post_order_dfs # Generic method
BinaryTree.post_order_dfs_with_result_compute # Generic method
BinaryTree.depth # using `post_order_dfs_with_result_compute`
BinaryTree.is_binary_search_tree # using `post_order_dfs_with_result_compute`
BinaryTree.lowest_common_ancestor # using `post_order_dfs_with_result_compute` with early termination
BinaryTree.lowest_common_ancestor2 # using `post_order_dfs_with_result_compute`

"""
Pre-Order Traversal
"""
BinaryTree.pre_order_dfs # Generic method
BinaryTree.pre_order_dfs_with_result_compute # Generic method
BinaryTree.longest_consecutive_sequence_pre_order_dfs # using `pre_order_dfs_with_result_compute` method
BinaryTree.add_value_to_binary_search_tree # for simplicity using a customized private _dfs

"""
BFS
"""
BinaryTree.bfs # Generic method
BinaryTree.level_bfs # Generic method
BinaryTree.decode_bfs # Generic method
BinaryTree.encode_with_existence_flags # using `bfs` method
BinaryTree.decode_with_existence_flags # using `decode_bfs` method
BinaryTree.vertical_order_traversal # using 'bfs' method, with state_handler
BinaryTree.right_side_view # using `level_bfs` method

"""
Solution by breaking down as left-tree, right-tree sub-problems, need to consider,
- left-tree optimal
- right-tree optimal
- left-three optimal "connected" wth root
- right-tree optimal "connected" with root
- leveraging generic post-order traversal method `post_order_dfs_with_result_compute`
"""
BinaryTree.diameter # using `post_order_dfs_with_result_compute`
BinaryTree.longest_consecutive_sequence # using `post_order_dfs_with_result_compute`
BinaryTree.largest_path_sum

"""
BST
"""
BinaryTree.is_binary_search_tree # using `post_order_dfs_with_result_compute`
BinaryTree.iter_binary_search_tree # exactly same algorithm as in-order traversal
BinaryTree.add_value_to_binary_search_tree # for simplicity using a customized private _dfs
BinaryTree.sequence_to_binary_search_tree # using `add_value_to_binary_search_tree`

# See Also
max_subarray_sum
binary_post_order_result_compute
