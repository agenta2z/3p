from typing import Sequence, Callable, Any


def binary_search(
        seq: Sequence,
        branching_left_cond: Callable[[Any, Any], bool],
        left: int = None,
        right: int = None,
        branching_left_include_mid: bool = True,
):
    """
    Performs a binary search on a sequence to find an element satisfying a condition.

    This function applies binary search on a sequence (`seq`) and uses a branching condition
    (`branching_left_cond`) to decide whether to continue searching on the left or right side.
    It returns the index of the element where the search terminates.

    Args:
        seq (Sequence): The sequence of elements to search. Must be indexable.
        branching_left_cond (Callable[[Any, Any], bool]):
            A callable condition that takes two elements, `seq[mid-1]` and `seq[mid]`, and returns
            `True` if the search should branch left, otherwise `False` to branch right.
        left (int, optional): The leftmost index for the search range. Defaults to 0.
        right (int, optional): The rightmost index for the search range. Defaults to len(seq) - 1.
        branching_left_include_mid (bool, optional): Determines whether the branching to the left includes mid itself;
            mid is also calculated in slightly different way.
            - If `True`, `mid = (left + right) // 2`, and the left branch includes `mid`.
            - If `False`, `mid = (left + right + 1) // 2`, and the right branch includes `mid`.
            Defaults to `True`.

    Returns:
        int: The index of the element where the search terminates.

    Examples:
        # Example 1: Finding the maximum (peak) in a unimodal sequence
        >>> seq = [1, 3, 8, 12, 4, 2]
        >>> branching_left_cond = lambda _curr, _next: _curr > _next
        >>> binary_search(seq, branching_left_cond)
        3

        # Example 2: Index of the last element, as condition never branches left
        >>> seq = [1, 2, 3, 4, 5, 6, 7, 8]
        >>> binary_search(seq, branching_left_cond)
        7

        Example 3: Finding a local minimum
        >>> seq = [9, 7, 3, 1, 2, 6]
        >>> branching_left_cond = lambda _curr, _next: _curr < _next
        >>> binary_search(seq, branching_left_cond)
        3

        # Example 4: Largest element <= target in a sorted sequence
        >>> seq = [1, 3, 5, 7, 9]
        >>> target = 5
        >>> binary_search(seq, lambda _curr, _next: _next > target)
        2
        >>> target = 6
        >>> binary_search(seq, lambda _curr, _next: _next > target)
        2
        >>> target = 10
        >>> binary_search(seq, lambda _curr, _next: _next > target)
        4

    Notes:
        - The `seq` must have at least one element; otherwise, the behavior is undefined.
        - The function assumes the branching condition is correctly defined for the input sequence.

    Complexity:
        - Time Complexity: O(log n), where `n` is the length of `seq`.
        - Space Complexity: O(log n) due to recursive calls (can be optimized with iteration).

    """
    if left is None:
        left = 0
    if right is None:
        right = len(seq) - 1

    if branching_left_include_mid:
        while left < right:
            mid = (left + right) // 2
            if branching_left_cond(seq[mid], seq[mid + 1]):
                right = mid
            else:
                left = mid + 1
    else:
        while left < right:
            mid = (left + right + 1) // 2
            if branching_left_cond(seq[mid - 1], seq[mid]):
                right = mid - 1
            else:
                left = mid

    return left


def binary_search_sorted_array_greater_than_or_equal_to_target(
        seq: Sequence,
        target,
        left: int = None,
        right: int = None
):
    """
    Performs a binary search on a sorted array to find the smallest index where the value is greater than or equal to the target.

    This function applies binary search on a sequence (`seq`) to locate the smallest index `i` such that
    `seq[i] >= target`. It assumes that `seq` is sorted in non-decreasing order.
    If the `target` is less than the smallest element in the array or greater than the largest element, the function returns `-1`.

    Args:
        seq (Sequence): The sorted array to search. Must be sorted in non-decreasing order.
        target (Any): The target value to search for in the array.
        left (int, optional): The leftmost index for the search range. Defaults to 0.
        right (int, optional): The rightmost index for the search range. Defaults to len(seq) - 1.

    Returns:
        int: The smallest index `i` where `seq[i] >= target`, or `-1` if no such index exists.

    Examples:
        # Example 1: General cases
        >>> seq = [1, 3, 6, 10, 15]
        >>> # Finding the first index where the value meets or exceeds the target
        >>> binary_search_sorted_array_greater_than_or_equal_to_target(seq, 6)
        2
        >>> # Target smaller than all elements
        >>> binary_search_sorted_array_greater_than_or_equal_to_target(seq, 0)
        0
        >>> # Target exactly matches an element
        >>> binary_search_sorted_array_greater_than_or_equal_to_target(seq, 10)
        3
        >>> # Target larger than all elements
        >>> binary_search_sorted_array_greater_than_or_equal_to_target(seq, 20)
        -1

        # Example 2: Empty sequence
        >>> seq = []
        >>> binary_search_sorted_array_greater_than_or_equal_to_target(seq, 5)
        -1

        # Example 3: Single element sequence
        >>> seq = [5]
        >>> binary_search_sorted_array_greater_than_or_equal_to_target(seq, 5)
        0
        >>> binary_search_sorted_array_greater_than_or_equal_to_target(seq, 4)
        0

        >>> binary_search_sorted_array_greater_than_or_equal_to_target(seq, 6)
        -1

        # Example 4: Repeated elements in the sequence
        >>> seq = [1, 1, 1, 1, 1]
        >>> binary_search_sorted_array_greater_than_or_equal_to_target(seq, 1)
        0
        >>> binary_search_sorted_array_greater_than_or_equal_to_target(seq, 2)
        -1

    Notes:
        - The function assumes that the sequence is sorted in non-decreasing order.
        - If the target is outside the range of the sequence, it returns `-1`.

    Complexity:
        - Time Complexity: O(log n), where `n` is the length of `seq`.
        - Space Complexity: O(1), as it uses an iterative approach.
    """
    if (not seq) or (target > seq[-1]):
        return -1

    return binary_search(
        seq=seq,
        branching_left_cond=lambda _mid, _: target <= _mid,
        left=left,
        right=right
    )

def binary_search_sorted_array_less_than_or_equal_to_target(
        seq: Sequence,
        target: Any,
        left: int = None,
        right: int = None
) -> int:
    """
    Performs a binary search on a sorted array to find the largest index where the value is less than or equal to the target.

    This function applies binary search on a sequence (`seq`) to locate the smallest index `i` such that
    `seq[i] <= target`. It assumes that `seq` is sorted in non-decreasing order.
    If the `target` is smaller than the smallest element in the array, the function returns `-1`.

    Args:
        seq (Sequence): The sorted array to search. Must be sorted in non-decreasing order.
        target (Any): The target value to search for in the array.
        left (int, optional): The leftmost index for the search range. Defaults to 0.
        right (int, optional): The rightmost index for the search range. Defaults to len(seq) - 1.

    Returns:
        int: The largest index `i` where `seq[i] <= target`, or `-1` if no such index exists.

    Examples:
        # Example 1: General cases
        >>> seq = [1, 3, 6, 10, 15]
        >>> # Finding the largest index where the value is less than or equal to the target
        >>> binary_search_sorted_array_less_than_or_equal_to_target(seq, 6)
        2
        >>> # Target smaller than all elements
        >>> binary_search_sorted_array_less_than_or_equal_to_target(seq, 0)
        -1
        >>> # Target exactly matches an element
        >>> binary_search_sorted_array_less_than_or_equal_to_target(seq, 10)
        3
        >>> # Target larger than all elements
        >>> binary_search_sorted_array_less_than_or_equal_to_target(seq, 20)
        4

        # Example 2: Empty sequence
        >>> seq = []
        >>> binary_search_sorted_array_less_than_or_equal_to_target(seq, 5)
        -1

        # Example 3: Single element sequence
        >>> seq = [5]
        >>> binary_search_sorted_array_less_than_or_equal_to_target(seq, 5)
        0
        >>> binary_search_sorted_array_less_than_or_equal_to_target(seq, 4)
        -1
        >>> binary_search_sorted_array_less_than_or_equal_to_target(seq, 6)
        0

        # Example 4: Repeated elements in the sequence
        >>> seq = [1, 1, 1, 1, 1]
        >>> binary_search_sorted_array_less_than_or_equal_to_target(seq, 1)
        4
        >>> binary_search_sorted_array_less_than_or_equal_to_target(seq, 2)
        4

    Notes:
        - The function assumes that the sequence is sorted in non-decreasing order.
        - If the target is smaller than all elements, it returns `-1`.

    Complexity:
        - Time Complexity: O(log n), where `n` is the length of `seq`.
        - Space Complexity: O(1), as it uses an iterative approach.
    """
    if not seq or target < seq[0]:
        return -1

    return binary_search(
        seq=seq,
        branching_left_cond=lambda _, _mid: target < _mid,
        left=left,
        right=right,
        branching_left_include_mid=False
    )


def binary_post_order_result_compute(seq: Sequence, result_compute, *args, **kwargs):
    """
    Performs a post-order traversal on a sequence and computes results using a custom function.

    This function treats the input sequence (`seq`) as if it were a binary tree and traverses it
    in a post-order fashion. At each node, it applies the `result_compute` function, which can
    access the current element, the results of the left and right subtrees, and additional
    arguments.

    Args:
        seq (Sequence): The input sequence, treated as a binary tree structure for traversal.
        result_compute (Callable): A function with the following signature:
            `result_compute(seq: Sequence, mid_index: int, left_result: Any, right_result: Any, *args, **kwargs) -> Any`
            - `seq` (Sequence): The input sequence.
            - `mid_index` (int): The index of the current element in the sequence.
            - `left_result` (Any): The result from the left subtree traversal, or `None` if no left subtree exists.
            - `right_result` (Any): The result from the right subtree traversal, or `None` if no right subtree exists.
            - `*args` and `**kwargs`: Additional arguments passed to `result_compute`.
        *args: Additional positional arguments passed to `result_compute`.
        **kwargs: Additional keyword arguments passed to `result_compute`.

    Returns:
        Any: The computed result for the entire sequence based on the `result_compute` function.

    Examples:
        # Example 1: Compute the sum of all elements in the sequence
        >>> seq = [1, 2, 3, 4, 5]
        >>> def result_compute(seq, mid_index, left_result, right_result):
        ...     return seq[mid_index] + (left_result or 0) + (right_result or 0)
        >>> binary_post_order_result_compute(seq, result_compute)
        15

        # Example 2: Find the maximum value in the sequence
        >>> def result_compute(seq, mid_index, left_result, right_result):
        ...     return max(seq[mid_index], left_result or float('-inf'), right_result or float('-inf'))
        >>> binary_post_order_result_compute(seq, result_compute)
        5

        # Example 3: Collect indices in post-order traversal
        >>> def result_compute(seq, mid_index, left_result, right_result):
        ...     return (left_result or []) + (right_result or []) + [mid_index]
        >>> binary_post_order_result_compute(seq, result_compute)
        [1, 0, 4, 3, 2]

    Notes:
        - The sequence must have at least one element for meaningful results.
        - `result_compute` should handle `None` values for `left_result` and `right_result` gracefully.

    Complexity:
        - Time Complexity: O(n), where `n` is the length of `seq`, as each element is visited once.
        - Space Complexity: O(log n) for the recursive call stack (assuming a balanced binary tree structure).

    """

    def _dfs(start: int, end: int):
        if start > end:
            return None
        mid_index = (start + end) // 2
        left_result = _dfs(start, mid_index - 1)
        right_result = _dfs(mid_index + 1, end)
        return result_compute(
            seq,
            mid_index,
            left_result,
            right_result,
            *args,
            **kwargs
        )

    return _dfs(0, len(seq) - 1)


def find_a_local_maximum(seq: Sequence[Any]) -> Any:
    """
    Finds a local maximum in a sequence.

    This function uses binary search to identify a local maximum in the sequence. A local maximum
    is an element `seq[i]` such that `seq[i] > seq[i+1]` (or `seq[i]` is the largest value in its neighborhood).

    Args:
        seq (Sequence[Any]): A sequence of comparable elements (e.g., integers, floats).
                             Must have at least one element.

    Returns:
        Any: A local maximum in the sequence.

    Examples:
        >>> find_a_local_maximum([1, 3, 8, 12, 4, 2])
        3

        >>> find_a_local_maximum([10, 20, 15, 2, 23, 90, 67])
        5

        >>> find_a_local_maximum([5])
        0

        >>> find_a_local_maximum([9, 7, 3, 2])
        0

    Notes:
        - If the sequence has multiple local maxima, the function may return any one of them.
        - The sequence must have at least one element; otherwise, the function raises an error.
        - A peak is defined locally, not globally.

    Complexity:
        - Time Complexity: O(log n), where `n` is the length of the sequence.
        - Space Complexity: O(log n) due to recursive calls.
    """
    return binary_search(seq, branching_left_cond=lambda _curr, _next: _curr > _next)


def find_a_local_minimum(seq: Sequence[Any]) -> Any:
    """
    Finds a local minimum in a sequence.

    This function uses binary search to identify a local minimum in the sequence. A local minimum
    is an element `seq[i]` such that `seq[i] < seq[i+1]` (or `seq[i]` is the smallest value in its neighborhood).

    Args:
        seq (Sequence[Any]): A sequence of comparable elements (e.g., integers, floats).
                             Must have at least one element.

    Returns:
        Any: A local minimum in the sequence.

    Examples:
        >>> find_a_local_minimum([9, 7, 3, 1, 2, 6])
        3

        >>> find_a_local_minimum([10, 20, 15, 2, 23, 90, 67])
        3

        >>> find_a_local_minimum([5])
        0

        >>> find_a_local_minimum([3, 8, 6, 7, 9])
        2

    Notes:
        - If the sequence has multiple local minima, the function may return any one of them.
        - The sequence must have at least one element; otherwise, the function raises an error.
        - A valley is defined locally, not globally.

    Complexity:
        - Time Complexity: O(log n), where `n` is the length of the sequence.
        - Space Complexity: O(log n) due to recursive calls.
    """
    return binary_search(seq, branching_left_cond=lambda _curr, _next: _curr < _next)


def find_closest_elements(arr: Sequence[int], k: int, x: int) -> Sequence[int]:
    """
    Find the k closest integers to x in a sorted array arr.

    Uses a binary search over the possible starting indices of the length-k window
    that minimizes the maximum distance to x.

    Args:
        arr (Sequence[int]): A sorted sequence of integers.
        k (int): Number of closest elements to return.
        x (int): Target integer to compare distances against.

    Returns:
        Sequence[int]: A list of the k closest integers to x, in sorted order.

    Examples:
        >>> find_closest_elements([1, 2, 3, 4, 5], 4, 3)
        [1, 2, 3, 4]
        >>> find_closest_elements([1, 1, 2, 3, 4, 5], 4, -1)
        [1, 1, 2, 3]
        >>> find_closest_elements([0, 5, 10], 2, 7)
        [5, 10]
        >>> find_closest_elements([], 0, 100)
        []
    """
    n = len(arr)
    # We search over start indices in [0, n-k] for the start index of the k closest elements
    # Define condition: True -> branch left, False -> branch right
    start = binary_search(
        seq=range(0, n - k + 1),
        branching_left_cond=lambda i, j: x <= (arr[i] + arr[i + k]) / 2,
        left=0,
        right=n - k
    )
    return arr[start:start + k]
