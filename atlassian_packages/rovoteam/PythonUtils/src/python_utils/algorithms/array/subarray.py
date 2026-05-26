from collections import defaultdict
from math import inf
from typing import Iterable, TypeVar, List, Dict

from typing import Sequence, Union, Tuple

T = TypeVar('T')


def prefix_sum(arr: Sequence[T], zero: T = 0) -> List[T]:
    """Compute prefix sums of the input array.

    Args:
        arr (Sequence[T]): Input sequence of type T (e.g., list of integers).
        zero (T): The zero value for type T (e.g., 0 if T is `int`).

    Returns:
        List[T]: A list where the i-th element is the sum of arr[0] through arr[i].

    Example:
        >>> prefix_sum([1, 2, 3])
        [1, 3, 6]
        >>> prefix_sum([])
        []
        >>> prefix_sum([5])
        [5]
    """
    prefix_sums = []
    current_sum = zero
    for item in arr:
        current_sum += item
        prefix_sums.append(current_sum)
    return prefix_sums


def prefix_sum_2d(matrix: Sequence[Sequence[T]], zero: T = 0) -> List[List[T]]:
    """Compute 2D prefix sums of the input matrix.

    Args:
        matrix (Sequence[Sequence[T]]): Input 2D sequence (e.g., list of lists of integers).
        zero (T): The zero value for type T (e.g., 0 if T is `int`).

    Returns:
        List[List[T]]: A 2D list where the element at (i, j) is the sum of all elements in the submatrix
                       from (0, 0) to (i, j).

    Example:
        >>> prefix_sum_2d([[1, 2], [3, 4]])
        [[1, 3], [4, 10]]
        >>> prefix_sum_2d([])
        []
        >>> prefix_sum_2d([[5]])
        [[5]]
    """
    if not matrix:
        return []

    rows = len(matrix)
    cols = len(matrix[0])
    prefix_sums = [[zero] * cols for _ in range(rows)]

    for i in range(rows):
        for j in range(cols):
            prefix_sums[i][j] = matrix[i][j]
            if i > 0:
                prefix_sums[i][j] += prefix_sums[i - 1][j]
                if j > 0:
                    prefix_sums[i][j] += prefix_sums[i][j - 1]
                    prefix_sums[i][j] -= prefix_sums[i - 1][j - 1]
            elif j > 0:
                prefix_sums[i][j] += prefix_sums[i][j - 1]

    return prefix_sums



def max_subarray_sum(arr: Sequence[T], zero: T = 0) -> T:
    """
    Finds the maximum sum of a subarray using a recursive approach.

    This function employs a recursive strategy to determine the maximum sum of a subarray. The approach
    can be generalized to solve other similar problems.

    Conceptually, the array is treated as a linear tree where the last element serves as the root. The recursion processes each element by returning
    two key values:
        - **Optimal Value (i.e. Sum for this problem) by Any Descendants**: The maximum subarray value found among all possible
          subarrays ending before the current element.
        - **Optimal Value (i.e. Sum for this problem) Ending at the Current Element**: The maximum subarray value that includes the
          "current element", potentially extending a subarray from its immediate predecessor.

    Args:
        arr (Sequence): The input array of type T (e.g., an array of integers).
        zero (T): The zero value for type T (e.g., 0 if T is `int`).

    Returns:
        T: The maximum sum of any subarray in the array.

    Example:
        >>> max_subarray_sum4([-2, 1, -3, 4, -1, 2, 1, -5, 4])
        6
        >>> max_subarray_sum4([1, -2, 3, 4])
        7
        >>> max_subarray_sum4([-1, -2, -3])
        0
        >>> max_subarray_sum4((1, 2, 3))
        6

    Notes:
        Time Complexity: O(n) where n is end_index + 1
        - Each recursive call processes one element exactly once
        - Total n recursive calls for array of length n
        - No element is processed more than once
        - Each operation within function (comparison, addition) is O(1)

        Space Complexity: O(n)
        - Recursive call stack grows linearly with input size
        - Each recursive call stores:
            * Local variables (constant space)
            * Return address
            * Parameters
        - Maximum stack depth = n (one frame per element)
    """

    def dfs(_arr: Sequence, end_index: int):
        if end_index < 0:
            return 0
        if end_index == 0:
            return _arr[0]

        (
            _max_subarray_sum,  # optimal value by any descendants
            _max_sub_sum_ending_at_child  # optimal value involving an immediate child
        ) = dfs(_arr, end_index - 1)

        _max_sub_sum_ending_here = max(
            _max_sub_sum_ending_at_child + _arr[end_index],
            _arr[end_index],
            zero
        )
        return max(_max_subarray_sum, _max_sub_sum_ending_here), _max_sub_sum_ending_here

    return dfs(arr, len(arr) - 1)[0]


def max_subarray_sum2(arr: Iterable[T], zero: T = 0) -> T:
    """
    Finds the maximum sum of a subarray using dynamic programming based on `max_subarray_sum`.
    This is a generalized approach that can apply to other problems.


    Args:
        arr (Sequence): The input array of type T (e.g., an array of integers).
        zero (T): The zero value for type T (e.g., 0 if T is `int`).

    Examples:
        >>> max_subarray_sum4([-2, 1, -3, 4, -1, 2, 1, -5, 4])
        6
        >>> max_subarray_sum4([1, -2, 3, 4])
        7
        >>> max_subarray_sum4([-1, -2, -3])
        0
        >>> max_subarray_sum4((1, 2, 3))
        6
        >>> max_subarray_sum4(())
        0
    """
    # initialize for the first element
    it = iter(arr)
    try:
        x = next(it)
    except StopIteration:
        return zero  # empty sequence

    _max_sum = [max(x, zero)]
    _max_sum_ending_at_last_position = [max(x, zero)]

    for x in it:  # iterate through remaining elements
        _max_sum_ending_at_last_position.append(
            max(
                _max_sum_ending_at_last_position[-1] + x,
                x,
                zero
            )
        )
        _max_sum.append(max(_max_sum[-1], _max_sum_ending_at_last_position[-1]))

    return _max_sum[-1]


def max_subarray_sum3(arr: Sequence[T], zero: T = 0) -> Tuple[T, int, int]:
    """
    Finds the maximum sum of a subarray and its corresponding start and end indices.

    This function identifies the contiguous subarray within a given sequence `arr`
    that has the largest sum. In addition to the maximum sum, it also returns the
    starting and ending indices of this subarray. If all elements are negative or
    the array is empty, the function returns the `zero` value along with `-1` for
    both start and end indices, indicating that no valid subarray exists.

    This is a simple extension of `max_subarray_sum2`.

    Args:
        arr (Sequence[T]): The input sequence of elements of type `T` (e.g.,
            a list or tuple of integers).
        zero (T, optional): The zero value for type `T` (e.g., `0` if `T` is `int`).
            Defaults to `0`.

    Returns:
        Tuple[T, int, int]: A tuple containing three elements:
            - The maximum sum of any contiguous subarray in `arr`.
            - The starting index of the subarray that yields the maximum sum.
            - The ending index of the subarray that yields the maximum sum.
            If the array is empty or all elements are negative, returns `(zero, -1, -1)`.

    Examples:
        >>> max_subarray_sum3([-2, 1, -3, 4, -1, 2, 1, -5, 4])
        (6, 3, 6)
        >>> max_subarray_sum3([1, -2, 3, 4])
        (7, 2, 3)
        >>> max_subarray_sum3([-1, -2, -3])
        (0, -1, -1)
        >>> max_subarray_sum3((1, 2, 3))
        (6, 0, 2)
        >>> max_subarray_sum3(())
        (0, -1, -1)

    Notes:
        - **Algorithmic Approach**: Utilizes a dynamic programming technique to
          iterate through the sequence while keeping track of the maximum sum
          ending at the current position and the overall maximum sum found so far.
        - **Indices Tracking**: Maintains the start and end indices of the subarray
          that contributes to the maximum sum by updating them whenever a new maximum
          is found.
        - **Time Complexity**: O(n), where n is the length of the input sequence.
          Each element is processed exactly once.
        - **Space Complexity**: O(n), due to the storage of intermediate sums and
          indices in the `max_sum` and `max_sum_ending_at_last_position` lists.
        - **Edge Cases**:
            - If the input sequence is empty, the function returns `(zero, -1, -1)`.
            - If all elements in the sequence are negative, it returns `(zero, -1, -1)`
              assuming `zero` is the preferred non-negative default.
    """
    # initialize for the first element
    empty = (zero, -1, -1)
    if not arr:
        return empty

    i = 0
    first = (arr[i], i, i)
    max_sum = [max(first, empty)]
    max_sum_ending_at_last_position = [max(first, empty)]

    for i in range(1, len(arr)):  # iterate through remaining elements
        _max_sum_ending_at_last_position = max_sum_ending_at_last_position[-1]
        max_sum_ending_at_last_position.append(
            max(
                (_max_sum_ending_at_last_position[0] + arr[i], _max_sum_ending_at_last_position[1], i),
                (arr[i], i, i),
                empty
            )
        )
        max_sum.append(max(max_sum[-1], max_sum_ending_at_last_position[-1]))

    return max_sum[-1]


def max_subarray_sum4(arr: Iterable[T], zero: T = 0) -> T:
    """Find maximum subarray sum using Kadane's algorithm.
    This is a specialized algorithm.

    Implements Kadane's algorithm to find the maximum sum of any contiguous
    subarray within the input iterable. This is an iterative solution that
    maintains running sums and updates the maximum seen so far.

    Args:
        arr: An iterable of values of type T (e.g., an array of integers).
        zero (T): The zero value for type T (e.g., 0 if T is `int`).

    Returns:
        float: Maximum sum of any contiguous subarray.

    Examples:
        >>> max_subarray_sum4([-2, 1, -3, 4, -1, 2, 1, -5, 4])
        6
        >>> max_subarray_sum4([1, -2, 3, 4])
        7
        >>> max_subarray_sum4([-1, -2, -3])
        0
        >>> max_subarray_sum4((1, 2, 3))
        6

    Notes:
        Time Complexity: O(n) where n is length of arr
        - Single pass through array
        - Each element processed exactly once
        - Operations per element:
            * Addition (O(1))
            * Two comparisons (O(1))
            * Max calculation (O(1))

        Space Complexity: O(1)
        - Only stores two variables regardless of input size:
            * curr_sum: tracks current subarray sum
            * max_sum: tracks maximum sum seen
        - No additional data structures created
        - No recursion stack

        Mathematical Proof of Correctness:
            Let the sequence of input values be a_1, a_2, ..., a_n. Define
            S(i, j) = a_i + a_{i+1} + ... + a_j as the sum of the subarray
            from index i to index j (1 ≤ i ≤ j ≤ n).

            Our goal is to show this algorithm returns:
                max(0, max{ S(i, j) : 1 ≤ i ≤ j ≤ n }).

            **Algorithm Recap**:
            We maintain two variables:
              - curr_sum: the best subarray sum ending exactly at the
                current element, but if it ever drops below 0, we reset it
                to 0.
              - max_sum: the maximum of all curr_sum values seen so far
                (also never below 0).

            **Base Case (no elements processed)**:
              - Before any iteration, curr_sum = 0 and max_sum = 0.
              - Interpreting an empty subarray yields sum 0.

            **Inductive Hypothesis**:
              Suppose that after processing the (i-1)-th element (for 1 ≤ i ≤ n),
              max_sum is:
                  max(0, max{ S(p, q) : 1 ≤ p ≤ q ≤ i-1 }),
              and curr_sum is:
                  max(0, max{ S(k, i-1) : 1 ≤ k ≤ i-1 }),
              specifically the best subarray sum ending at (i-1), but reset
              to 0 if that sum is negative.

            **Inductive Step (process the i-th element)**:
              - Let a_i be the i-th element. We set:
                    curr_sum = curr_sum + a_i
                If curr_sum < 0, then curr_sum := 0. Thus:
                  curr_sum = max(0, max{ S(k, i-1) } + a_i ).

              - The newly updated curr_sum is then the maximum sum
                for a subarray ending exactly at index i (bounded below by 0).
              - We update:
                    max_sum = max(max_sum, curr_sum).
                By the inductive hypothesis, max_sum was the best subarray
                sum through (i-1). Now we take the maximum of that and
                the new best ending at i.

              Therefore, after including a_i, max_sum is:
                max(0, max{ S(p, q) : 1 ≤ p ≤ q ≤ i }).

            **Termination**:
              After we finish processing a_n, max_sum holds:
                max(0, max{ S(i, j) : 1 ≤ i ≤ j ≤ n }).
              If all sums are negative, resetting curr_sum to 0 at each step
              ensures max_sum remains 0. Otherwise, it becomes the maximum
              positive subarray sum discovered.

            This completes the induction and proves that the final value
            of max_sum is indeed the maximum over all contiguous subarray
            sums (constrained not to fall below zero), achieving the
            desired correctness.
    """
    curr_sum = max_sum = zero

    for item in arr:
        curr_sum += item
        if curr_sum < zero:
            curr_sum = zero
        max_sum = max(max_sum, curr_sum)

    return max_sum


def max_subarray_product(arr: Sequence[T], infinity: T = inf) -> T:
    """
    Find the contiguous subarray within an array which has the largest product with the recursion appraoch.
    The recursion technique is the same as `max_subarray_sum`.

    Unlike the `max_subarray_sum` function, it maintains both the maximum and minimum products ending at the current element
    to account for the effect of negative numbers flipping the sign of the product.

    Examples:
        >>> max_subarray_product([2, 3, -2, 4, -1])
        48

        >>> max_subarray_product([-2, -3, -4])
        12

        >>> max_subarray_product([-2, 6, -3, -10, 0, 2])
        180

        >>> max_subarray_product([-1,-3, -10, 0, 60])
        60

        >>> max_subarray_product([])
        -inf
    """

    def dfs(_arr, end_index):
        if end_index < 0:
            return -infinity, None, None
        if end_index == 0:
            return arr[0], arr[0], arr[0]

        (
            _max_subarray_prod,  # optimal value by any descendants
            _max_sub_prod_ending_at_child,  # optimal value involving an immediate child
            _min_sub_prod_ending_at_child  # optimal value involving an immediate child
        ) = dfs(_arr, end_index - 1)

        _max_sub_prod_ending_here = max(
            _max_sub_prod_ending_at_child * _arr[end_index],
            _min_sub_prod_ending_at_child * _arr[end_index],
            _arr[end_index]
        )
        _min_sub_prod_ending_here = min(
            _max_sub_prod_ending_at_child * _arr[end_index],
            _min_sub_prod_ending_at_child * _arr[end_index],
            _arr[end_index]
        )
        return (
            max(_max_subarray_prod, _max_sub_prod_ending_here),
            _max_sub_prod_ending_here,
            _min_sub_prod_ending_here
        )

    return dfs(arr, len(arr) - 1)[0]


def max_subarray_product2(arr: Iterable[T], infinity: T = inf) -> T:
    """
    Find the contiguous subarray within an array which has the largest product with the recursion appraoch.
    The recursion pattern is the same as `max_subarray_sum`.
    The key difference is we need to maintain two optimal values involving the immediate child.

    Examples:
        >>> max_subarray_product2([2, 3, -2, 4, -1])
        48

        >>> max_subarray_product2([-2, -3, -4])
        12

        >>> max_subarray_product2([-2, 6, -3, -10, 0, 2])
        180

        >>> max_subarray_product2([-1,-3, -10, 0, 60])
        60

        >>> max_subarray_product2([])
        -inf
    """
    # initialize for the first element
    it = iter(arr)
    try:
        x = next(it)
    except StopIteration:
        return -infinity  # empty sequence
    _max_prod = [x]
    _max_prod_ending_at_last_position = [x]
    _min_prod_ending_at_last_position = [x]

    for x in it:  # iterate through remaining elements
        max_min_candidates = (
            _max_prod_ending_at_last_position[-1] * x,
            _min_prod_ending_at_last_position[-1] * x,
            x
        )
        _max_prod_ending_at_last_position.append(
            max(max_min_candidates)
        )
        _min_prod_ending_at_last_position.append(
            min(max_min_candidates)
        )
        _max_prod.append(
            max(
                _max_prod[-1],
                _max_prod_ending_at_last_position[-1]
            )
        )

    return _max_prod[-1]


def max_subarray_product3(arr: Sequence[T], infinity: T = inf) -> Tuple[T, int, int]:
    """
    Finds the contiguous subarray within an array that has the largest product and returns
    the product along with the starting and ending indices of that subarray.

    This function employs is a simple extension on top of `max_subarray_product3` to also track the starting index
    and ending index of the subarray.

    Args:
        arr (Sequence[T]): The input array of type T (e.g., a list of integers or floats).
        infinity (T, optional): A value representing infinity. Defaults to `math.inf`.
                                 Used as the return value for empty input arrays.

    Returns:
        Tuple[T, int, int]:
            - **max_product** (*T*): The maximum product of any contiguous subarray.
            - **start_index** (*int*): The starting index of the subarray achieving the maximum product.
            - **end_index** (*int*): The ending index of the subarray achieving the maximum product.

    Examples:
        >>> max_subarray_product3([2, 3, -2, 4, -1])
        (48, 0, 4)

        >>> max_subarray_product3([-2, -3, -4])
        (12, 1, 2)

        >>> max_subarray_product3([-2, 6, -3, -10, 0, 2])
        (180, 1, 3)

        >>> max_subarray_product3([-1, -3, -10, 0, 60])
        (60, 4, 4)

        >>> max_subarray_product3([])
        (-inf, -1, -1)

    Notes:
        - **Handling Empty Input**: If the input array is empty, the function returns a tuple with
          `-infinity` as the maximum product and `-1` for both start and end indices, indicating
          that no valid subarray exists.

        - **Negative Numbers**: The function correctly handles negative numbers by keeping track
          of both the maximum and minimum products at each step. This ensures that a negative number
          can potentially turn a previously minimum product into a maximum when multiplied.

        - **Single Element Arrays**: If the array contains only one element, the function returns
          that element as the maximum product with both start and end indices pointing to its position.

        - **Zero Handling**: Encountering a zero resets the current subarray product calculations,
          as any product multiplied by zero becomes zero. The function considers starting a new subarray
          after a zero.

    Complexity:
        - **Time Complexity**: O(n), where n is the length of the input array.
            - The function makes a single pass through the array.
            - Each element is processed exactly once with constant time operations.

        - **Space Complexity**: O(n)
            - The function maintains three lists to store tuples representing the maximum products,
              maximum products ending at the last position, and minimum products ending at the last position.
            - Each list grows linearly with the size of the input array.

    """
    # initialize for the first element
    if not arr:
        return -infinity, -1, -1  # empty sequence

    i = 0
    max_prod = [(arr[i], i, i)]
    max_prod_ending_at_last_position = [(arr[i], i, i)]
    min_prod_ending_at_last_position = [(arr[0], i, i)]

    for i in range(1, len(arr)):  # iterate through remaining elements
        x = arr[i]
        _max_prod_ending_at_last_position = max_prod_ending_at_last_position[-1]
        _min_prod_ending_at_last_position = min_prod_ending_at_last_position[-1]
        max_min_candidates = (
            (_max_prod_ending_at_last_position[0] * x, _max_prod_ending_at_last_position[1], i),
            (_min_prod_ending_at_last_position[0] * x, _min_prod_ending_at_last_position[1], i),
            (x, i, i)
        )
        max_prod_ending_at_last_position.append(
            max(max_min_candidates)
        )
        min_prod_ending_at_last_position.append(
            min(max_min_candidates)
        )
        max_prod.append(
            max(
                max_prod[-1],
                max_prod_ending_at_last_position[-1]
            )
        )

    return max_prod[-1]


def subarray_sum_equals_k(arr: Sequence[T], k: T) -> Sequence[Tuple[int, int]]:
    """
    Finds all continuous subarrays within the given array whose sum equals the target value `k`.

    The function treats the input array as a linear structure and uses a recursive depth-first search
    approach to identify all subarrays that sum to `k`. Each subarray is represented by a tuple
    containing its start and end indices (both inclusive).

    The recursion involves two main checks:
        - **Elements from any descendants satisfying the sum requirement**: Identifies subarrays
          that sum to `k` within the descendants of the current element.
        - **Elements involving the immediate child satisfying the sum requirement**: Identifies
          subarrays that include the current element and satisfy the sum requirement.

    Args:
        arr (Sequence[T]): The input array of integers.
        k (T): The target sum.

    Returns:
        Sequence[Tuple[int, int]]: A sequence of tuples where each tuple contains the start and
        end indices of a subarray that sums to `k`.

    Examples:
        Basic Cases:
            >>> subarray_sum_equals_k([1, 2, 3], 3)
            [(0, 1), (2, 2)]

            >>> subarray_sum_equals_k([1, 1, 1], 2)
            [(0, 1), (1, 2)]

        Including Negative Numbers and Zero:
            >>> subarray_sum_equals_k([1, -1, 0], 0)
            [(0, 1), (0, 2), (2, 2)]

            >>> subarray_sum_equals_k([3, 4, 7, 2, -3, 1, 4, 2], 7)
            [(0, 1), (2, 2), (2, 5), (5, 7)]

        Edge Cases:
            >>> subarray_sum_equals_k([1], 0)
            []

            >>> subarray_sum_equals_k([0, 0, 0, 0], 0)
            [(0, 0), (0, 1), (1, 1), (0, 2), (1, 2), (2, 2), (0, 3), (1, 3), (2, 3), (3, 3)]

            >>> subarray_sum_equals_k([-1, -1, 1], 0)
            [(1, 2)]

            >>> subarray_sum_equals_k([5, -1, 5], 5)
            [(0, 0), (2, 2)]

        Additional Test Cases:
            >>> subarray_sum_equals_k([2, 4, 6, 10], 16)
            [(2, 3)]

            >>> subarray_sum_equals_k([1, 2, 1, 2, 1], 3)
            [(0, 1), (1, 2), (2, 3), (3, 4)]

            >>> subarray_sum_equals_k([], 0)
            []

            >>> subarray_sum_equals_k([1, -1, 1, -1], 0)
            [(0, 1), (1, 2), (0, 3), (2, 3)]

            >>> subarray_sum_equals_k([1000000, -1000000], 0)
            [(0, 1)]

    Note:
        - The function assumes that the input array contains numerical values that support addition.
        - The returned indices are zero-based and inclusive, meaning both start and end indices
          are part of the subarray.
        - If no such subarrays exist, the function returns an empty list.

        - **Time Complexity**:
            - The function operates with a **quadratic time complexity** of **O(n^2)**.
              Consider an array [a, b, c, d]. The recursive calls can be visualized as a tree:
                dfs(3, k)
                ├── dfs(2, k)
                │   ├── dfs(1, k)
                │   │   ├── dfs(0, k)
                │   │   └── dfs2(0, k - b)
                │   └── dfs2(1, k - c)
                │       ├── dfs2(0, k - c - b)
                │       └── ...
                ├── dfs2(2, k - d)
                │   ├── dfs2(1, k - d - c)
                │   └── ...
              We can see every dfs call needs to call dfs2 that goes through the reamining part of the sequence.
              There are `n` dfs calls, and hence the time complexity is O(n^2).

        - **Space Complexity**:
            - The space complexity is also **O(n^2)**.
            - This arises from storing all valid subarrays that sum to `k`, which can be up to O(n^2) in the worst case
              (e.g., when every possible subarray sums to `k`).
            - Additionally, the recursion stack may consume space proportional to the depth of the recursion, which is O(n),
              but this is dominated by the space required to store the subarrays.
    """

    def dfs(_arr, _end_index, _k):
        # all sub arrays of _arr[0 ... _end_index] equals _k
        if _end_index < 0:
            return []
        if _end_index == 0:
            return [(0, 0)] if _arr[0] == _k else []

        prev_equals_k = dfs(_arr, _end_index - 1, _k)
        prev_equals_k_minus_current = dfs2(_arr, _end_index - 1, _k - arr[_end_index])
        current = [(_end_index, _end_index)] if _arr[_end_index] == _k else []
        return prev_equals_k + prev_equals_k_minus_current + current

    def dfs2(_arr, _end_index, _k):
        # all tailing sub arrays of _arr[0 ... _end_index] equals _k
        if _end_index < 0:
            return []
        if _end_index == 0:
            return [(0, _end_index + 1)] if _arr[0] == _k else []

        prev_tailing_sub_arrays_equals_k_minus_current = dfs2(_arr, _end_index - 1, _k - arr[_end_index])
        prev_tailing_sub_arrays_equals_k_minus_current = [
            (x[0], _end_index + 1) for x in prev_tailing_sub_arrays_equals_k_minus_current
        ]
        if arr[_end_index] == _k:
            return prev_tailing_sub_arrays_equals_k_minus_current + [(_end_index, _end_index + 1)]
        else:
            return prev_tailing_sub_arrays_equals_k_minus_current

    return dfs(arr, len(arr) - 1, k)


def subarray_sum_equals_k_2(seq: Iterable[T], k: T) -> Sequence[Tuple[int, int]]:
    """
    Finds all continuous subarrays within the given array whose sum equals the target value `k`.

    This is the Prefix Sum algorithm, which is a more specialized approach.

    Examples:
        Basic Cases:
            >>> subarray_sum_equals_k_2([1, 2, 3], 3)
            [(0, 1), (2, 2)]

            >>> subarray_sum_equals_k_2([1, 1, 1], 2)
            [(0, 1), (1, 2)]

        Including Negative Numbers and Zero:
            >>> subarray_sum_equals_k_2([1, -1, 0], 0)
            [(0, 1), (0, 2), (2, 2)]

            >>> subarray_sum_equals_k_2([3, 4, 7, 2, -3, 1, 4, 2], 7)
            [(0, 1), (2, 2), (2, 5), (5, 7)]

        Edge Cases:
            >>> subarray_sum_equals_k_2([1], 0)
            []

            >>> subarray_sum_equals_k_2([0, 0, 0, 0], 0)
            [(0, 0), (0, 1), (1, 1), (0, 2), (1, 2), (2, 2), (0, 3), (1, 3), (2, 3), (3, 3)]

            >>> subarray_sum_equals_k_2([-1, -1, 1], 0)
            [(1, 2)]

            >>> subarray_sum_equals_k_2([5, -1, 5], 5)
            [(0, 0), (2, 2)]

        Additional Test Cases:
            >>> subarray_sum_equals_k_2([2, 4, 6, 10], 16)
            [(2, 3)]

            >>> subarray_sum_equals_k_2([1, 2, 1, 2, 1], 3)
            [(0, 1), (1, 2), (2, 3), (3, 4)]

            >>> subarray_sum_equals_k_2([], 0)
            []

            >>> subarray_sum_equals_k_2([1, -1, 1, -1], 0)
            [(0, 1), (1, 2), (0, 3), (2, 3)]

            >>> subarray_sum_equals_k_2([1000000, -1000000], 0)
            [(0, 1)]
    """
    result: List[Tuple[int, int]] = []
    cum_sum: T = 0
    sum_to_indices: Dict[T, List[int]] = defaultdict(list)
    sum_to_indices[0].append(-1)  # To handle sub arrays starting at index 0

    for i, num in enumerate(seq):
        cum_sum += num

        if (cum_sum - k) in sum_to_indices:
            start_indices = sum_to_indices[cum_sum - k]
            for start_index in start_indices:
                result.append((start_index + 1, i))

        sum_to_indices[cum_sum].append(i)

    return result


def exists_subarray_modular_by_k(seq: Iterable[int], k: int, min_subarray_size: int = 2) -> bool:
    """
    Checks if there exists a subarray of at least `min_subarray_size` whose sum is divisible by `k`.

    Args:
        seq (Iterable[int]): The input sequence of integers.
        k (int): The divisor to check divisibility.
        min_subarray_size (int, optional): The minimum size of the subarray. Must be a positive number. Defaults to 2.

    Returns:
        bool: True if such a subarray exists, False otherwise.

    Examples:
        >>> exists_subarray_modular_by_k([23, 2, 4, 6, 7], 6)
        True
        >>> exists_subarray_modular_by_k([23, 2, 6, 4, 7], 13)
        False
        >>> exists_subarray_modular_by_k([1, 2, 3], 3, min_subarray_size=1)
        True
        >>> exists_subarray_modular_by_k([1, 2, 3], 5, min_subarray_size=1)
        False
        >>> exists_subarray_modular_by_k([1, 2, 3, 4, 5], 5)
        True

    Notes:
        - Time Complexity: O(n), where n is the length of `arr`, since we iterate through the array once.
        - Space Complexity: O(k), where k is the divisor, for storing the modular records.

    """
    if min_subarray_size <= 0:
        raise ValueError("'min_subarray_size' must be greater than 0.")
    if min_subarray_size == 1:
        return any(x % k == 0 for x in seq)

    mod_k_record = {0: -1}  # Maps remainder mod k to its first occurrence index
    prefix_sum = 0

    for i, x in enumerate(seq):
        prefix_sum += x
        mod_k = prefix_sum % k

        if mod_k in mod_k_record:
            if mod_k_record[mod_k] < i - min_subarray_size + 1:
                return True
        else:
            mod_k_record[mod_k] = i  # Store the first occurrence index of this remainder

    return False

def subarray_modular_by_k(seq: Iterable[int], k: int) -> List[Tuple[int, int]]:
    """
    Finds all continuous subarrays within the given array whose sum is divisible by `k`.

    This function utilizes the Prefix Sum algorithm combined with a hash map to efficiently identify
    all subarrays where the sum of elements is divisible by the specified integer `k`. By tracking
    the frequency of prefix sums modulo `k`, it determines the start and end indices of valid subarrays.

    Args:
        seq (Iterable[int]): The input sequence of integers.
        k (int): The divisor to check divisibility of subarray sums.

    Returns:
        List[Tuple[int, int]]: A list of tuples where each tuple contains the start and end indices
                               of a subarray whose sum is divisible by `k`.

    Examples:
        Basic Cases:
        >>> subarray_modular_by_k([4, 5, 0, -2, -3, 1], 5)
        [(1, 1), (1, 2), (2, 2), (1, 4), (2, 4), (3, 4), (0, 5)]

        >>> subarray_modular_by_k([1, 2, 3], 3)
        [(0, 1), (0, 2), (2, 2)]

        Including Negative Numbers and Zero:
        >>> subarray_modular_by_k([1, -1, 0], 0)
        [(0, 1), (0, 2), (2, 2)]

        >>> subarray_modular_by_k([3, 4, 7, 2, -3, 1, 4, 2], 7)
        [(0, 1), (0, 2), (2, 2), (0, 5), (2, 5), (3, 5), (5, 7)]

        Edge Cases:
        >>> subarray_modular_by_k([1], 0)
        []

        >>> subarray_modular_by_k([0, 0, 0, 0], 0)
        [(0, 0), (0, 1), (1, 1), (0, 2), (1, 2), (2, 2), (0, 3), (1, 3), (2, 3), (3, 3)]

        >>> subarray_modular_by_k([-1, -1, 1], 0)
        [(1, 2)]

        >>> subarray_modular_by_k([5, -1, 5], 5)
        [(0, 0), (2, 2)]

        Additional Test Cases:
        >>> subarray_modular_by_k([2, 4, 6, 10], 4)
        [(1, 1), (0, 2), (1, 3), (2, 3)]

        >>> subarray_modular_by_k([1, 2, 1, 2, 1], 2)
        [(1, 1), (0, 2), (0, 3), (3, 3), (1, 4), (2, 4)]

        >>> subarray_modular_by_k([], 3)
        []

        >>> subarray_modular_by_k([1, -1, 1, -1], 2)
        [(0, 1), (1, 2), (0, 3), (2, 3)]

        >>> subarray_modular_by_k([1000000, -1000000], 1000000)
        [(0, 0), (0, 1), (1, 1)]

    Notes:
        - **Time Complexity**:
            - The function operates with a **linear time complexity** of **O(n)**,
              where `n` is the number of elements in the input array.
            - This efficiency is achieved by traversing the array only once and performing
              constant-time operations within each iteration.

        - **Space Complexity**:
            - The space complexity is **O(k)**, where `k` is the divisor.
            - This arises from storing the frequency of each modulo value in the `sum_to_indices` dictionary.
            - In the worst case, there can be up to `k` different modulo values.

        - **Edge Cases**:
            - **Empty Array**: Returns an empty list as there are no subarrays to evaluate.
            - **Single Element Array**: If the single element is divisible by `k`, returns a list with that index; otherwise, an empty list.
            - **All Elements Zero**: Every possible subarray sum is `0`, which is divisible by any non-zero `k`.
            - **Negative Numbers**: The function correctly handles negative numbers by utilizing Python's modulo operation behavior.
            - **k = 0**: When `k` is `0`, the function identifies subarrays with a sum of exactly `0`.

        - **Mathematical Insight**:
            - Two prefix sums with the same modulo `k` imply that the subarray between these two indices has a sum divisible by `k`.
            - The `sum_to_indices` dictionary keeps track of the list of indices where each prefix sum modulo `k` occurs, enabling efficient identification of valid subarrays.

        - **Constraints**:
            - The divisor `k` must be an integer. If `k` is `0`, the function specifically looks for subarrays with a sum of `0`.
            - The input array can contain positive, negative, and zero values.

    """
    if k == 0:
        # Handle the case where k is 0 separately to avoid division by zero
        # In this case, we're looking for subarrays with a sum exactly equal to 0
        return subarray_sum_equals_k_2(seq, 0)

    result: List[Tuple[int, int]] = []  # List to store the resulting subarrays
    cum_sum: int = 0  # Variable to store the cumulative sum of elements
    sum_to_indices: Dict[int, List[int]] = defaultdict(list)

    sum_to_indices[0].append(-1)  # To handle subarrays starting at index 0

    for i, num in enumerate(seq):
        cum_sum += num  # Update the cumulative sum with the current number

        mod = cum_sum % k  # Compute the modulo of the current prefix sum with k
        if mod in sum_to_indices:
            start_indices = sum_to_indices[mod]  # Retrieve all indices with the same modulo
            for start_index in start_indices:
                # Append the subarray indices (start_index + 1, current index)
                result.append((start_index + 1, i))

        # Add the current index to the list of indices for this modulo
        sum_to_indices[mod].append(i)

    return result


def longest_consecutive_increasing(nums: Sequence[T]) -> Tuple[int, int]:
    """
    Find the longest consecutive strictly increasing subsequence in a sequence of numbers.

    Args:
        nums (Sequence[Union[int, float]]): Input sequence of integers or floats.

    Returns:
        Tuple[int, int]:
            - **max_length** (*int*): The length of the longest consecutive increasing subsequence.
            - **start_index** (*int*): The starting index of the subsequence achieving the maximum length.

    Examples:
        >>> longest_consecutive_increasing([1, 3, 2, 4, 5, 7, 2, 3])
        (4, 2)
        >>> longest_consecutive_increasing([5, 4, 3, 2, 1])
        (1, 0)
        >>> longest_consecutive_increasing([])
        (0, 0)

    Notes:
        This problem can be solved in O(n) time by iterating through the sequence once. No DP is needed.

        **Algorithm**:
            - Initialize variables to keep track of the current subsequence length and its starting index.
            - Iterate through the sequence:
                - If the current element is greater than the previous element, increment the current length.
                - Otherwise, reset the current length to 1 and update the current starting index.
            - Update the maximum length and indices whenever a longer subsequence is found.

    """
    if not nums:
        return 0, 0

    start_index = start_index_for_max_increasing = 0
    end_index = cur_increasing = max_increasing = 1

    while end_index < len(nums):
        if nums[end_index] >= nums[end_index - 1]:
            end_index += 1
            cur_increasing += 1
        else:
            if cur_increasing > max_increasing:
                max_increasing = cur_increasing
                start_index_for_max_increasing = start_index

            start_index = end_index
            end_index += 1
            cur_increasing = 1

    return max_increasing, start_index_for_max_increasing
