from collections.abc import Callable
from numbers import Number
from typing import Sequence, List

from typing_extensions import TypeVar

T = TypeVar('T')


def optimal_binary_merge(
        seq: Sequence[T],
        merger: Callable[[T, T], T], merge_cost: Callable[[T, T], Number],
        merge_invariant_given_range: bool = True
) -> Number:
    """
    Calculates the minimum total cost of merging a sequence of elements into a single element,
    where each merge operation has an associated cost determined by a given `merge_cost` function.

    Args:
        seq (Sequence[T]): The sequence of elements to be merged.
        merger (Callable[[T, T], T]): A function that merges two elements into one.
        merge_cost (Callable[[T, T], Number]): A function that returns the cost of merging two elements.
        merge_invariant_given_range (bool, optional): Indicates whether the merger function is invariant
            over the same range of elements. If `True` (default), the merger results for the same range
            are assumed to be identical, and the merger function may be called fewer times for optimization.
            If `False`, the merger function is called every time a new minimum cost is found.

    Returns:
        Number: The minimum total cost to merge the entire sequence into a single element.

    Examples:
        # Example 1: Optimal File Merge Pattern with merge_invariant_given_range = True
        # The optimal merge, (20+30)+(10+30)
        >>> files = [20, 30, 10, 30]
        >>> def merge_files(x, y):
        ...     return x + y
        >>> def merge_cost(x, y):
        ...     return x + y
        >>> optimal_binary_merge(files, merge_files, merge_cost)
        180

        # Example 2: Custom Merge with Different Costs, merge_invariant_given_range = False
        >>> seq = ['A', 'B', 'C']
        >>> def merge_strings(x, y):
        ...     return x + y
        >>> def merge_cost_strings(x, y):
        ...     return len(x) + len(y)
        >>> optimal_binary_merge(seq, merge_strings, merge_cost_strings, merge_invariant_given_range=False)
        5

    Notes:
        **Problem Statement**:
            - This problem is the generalization of the matrix multiplication chain problem.
            - This function generalizes the classic **Matrix Chain Multiplication** and **Optimal Merge Pattern** problems.
            - It finds the sequence of merges that results in the minimum total cost to merge the entire sequence
              into one element, where each merge has an associated cost.

        **Dynamic Programming Explanation**:
            - **State Definition**:
                - `dp[i][j]` represents the minimum total cost to merge elements from index `i` to `j` into a single element.
                - `merge_output[i][j]` stores the result of merging elements from index `i` to `j`.

            - **Recursive Formula**:
                - For all `i` and `j` such that `0 <= i < j < n`:
                    ```python
                    dp[i][j] = min(
                        dp[i][k] + dp[k + 1][j] + merge_cost(merge_output[i][k], merge_output[k + 1][j])
                        for k in range(i, j)
                    )
                    ```
                - We consider all possible partitions `k` between `i` and `j` and choose the one that minimizes the total cost.

            - **Base Cases**:
                - For all `i`, `dp[i][i] = 0` (cost to merge a single element is zero).
                - `merge_output[i][i] = seq[i]`.

        **Parameter Explanation**:
            - **merge_invariant_given_range**:
                - If `merge_invariant_given_range` is `True` (default), it assumes that the merger function `merger`
                  will produce the same result for the same range of elements, even if called multiple times.
                  This allows for optimization by not recomputing the merged result if it has already been computed
                  for that range.
                - If `False`, the merger function is called every time a new minimum cost is found, which is necessary
                  if the merger function depends on the specific sequence of merges or has side effects.

        **Time Complexity**:
            - O(n^3), where `n` is the length of the input sequence.
                - There are `O(n^2)` subproblems.
                - For each subproblem, we iterate over `k` from `i` to `j - 1`, resulting in `O(n)` time per subproblem.

        **Space Complexity**:
            - O(n^2).
                - We use two 2D arrays `dp` and `merge_output`, each of size `n x n`.

        **Constraints**:
            - The sequence `seq` must have at least one element.
            - The `merger` and `merge_cost` functions must be defined for all combinations of elements in `seq`.

    """
    n = len(seq)
    if n == 0:
        raise ValueError("Sequence must contain at least one element.")

    # Initialize DP tables
    dp: List[List[Number]] = [[0 if i == j else float('inf') for j in range(n)] for i in range(n)]
    merge_output: List[List[T]] = [[None for _ in range(n)] for _ in range(n)]

    # Initialize total[i][i]
    for i in range(n):
        merge_output[i][i] = seq[i]

    # Build the tables dp[][] and total[][] in bottom-up manner
    for L in range(2, n + 1):  # L is the merge chain length, minimum 2, and maximum n
        for i in range(n - L + 1):  # `i` is the inclusive left boundary index and can move up to n-L
            j = i + L - 1  # `j` is the inclusive right boundary index
            merge_output[i][j] = None  # Initialize total[i][j]
            for k in range(i, j):
                # Compute cost of splitting at position k
                left_merge = merge_output[i][k]
                right_merge = merge_output[k + 1][j]
                cost = dp[i][k] + dp[k + 1][j] + merge_cost(left_merge, right_merge)
                if cost < dp[i][j]:
                    dp[i][j] = cost
                    # Merge the elements to update merge_output[i][j]
                    if (not merge_invariant_given_range) or (merge_output[i][j] is None):
                        merge_output[i][j] = merger(left_merge, right_merge)

    return dp[0][n - 1]
