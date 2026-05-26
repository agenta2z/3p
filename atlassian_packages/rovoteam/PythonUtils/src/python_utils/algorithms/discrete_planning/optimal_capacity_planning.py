from collections.abc import Sequence
from math import inf
from typing import List, Union, Iterable
from numbers import Number


def full_capacity_dispatch_min_worker(
        workload: int,
        worker_capacities: Sequence[int],
        return_worker_indexes: bool = False
):
    """
    Calculates the minimum number of workers required to handle a given workload,
    where each worker has a capacity from a given set of capacities.
    Each worker can handle up to their capacity, and workers must work at full capacity.

    Args:
        workload (int): The total workload that needs to be handled.
        worker_capacities (Sequence[int]): A sequence of worker capacities.
        return_worker_indexes (bool, optional): If True, returns a tuple containing the minimum number
            of workers and a tuple of worker indexes used to achieve the workload.
            Defaults to False.

    Returns:
        Union[int, Tuple[int, Optional[Tuple[int, ...]]]]:
            - If `return_worker_indexes` is False:
                - **int**: The minimum number of workers needed to handle the workload.
                  Returns -1 if it's not possible to handle the workload with the given capacities.
            - If `return_worker_indexes` is True:
                - **Tuple[int, Optional[Tuple[int, ...]]]:**
                    - **min_workers** (*int*): The minimum number of workers needed.
                    - **worker_indexes** (*Optional[Tuple[int, ...]]*): A tuple containing the indexes
                      of the workers used to achieve the workload. Returns `None` if it's not possible.

    Examples:
        >>> full_capacity_dispatch_min_worker(7, [2, 3])
        3
        >>> full_capacity_dispatch_min_worker(10, [3, 5])
        2
        >>> full_capacity_dispatch_min_worker(1, [2, 3])
        -1
        >>> full_capacity_dispatch_min_worker(0, [1, 2, 3])
        -1
        >>> full_capacity_dispatch_min_worker(5, [5])
        1

        # Using return_worker_indexes=True
        >>> full_capacity_dispatch_min_worker(7, [2, 3], return_worker_indexes=True)
        (3, (1, 0, 0))
        >>> full_capacity_dispatch_min_worker(10, [3, 5], return_worker_indexes=True)
        (2, (1, 1))
        >>> full_capacity_dispatch_min_worker(1, [2, 3], return_worker_indexes=True)
        (-1, None)
        >>> full_capacity_dispatch_min_worker(5, [5], return_worker_indexes=True)
        (1, (0,))

    Notes:
        **Dynamic Programming Explanation**
            - **Problem Statement**:
                - This problem is exactly the same classic coin-exchange problem in the form of workload dispatching.
                - Given a total workload and a set of worker capacities,
                  determine the minimum number of workers needed to fully handle the workload.
                - Each worker can handle up to their maximum capacity, and workers must work at full capacity.

            - **State Definition**:
                - `dp[i]` represents the minimum number of workers required to handle a workload of `i`.

            - **Recursive Formula**:
                - For each workload amount `i` from `1` to `workload`:
                    dp[i] = min(dp[i], dp[i - c] + 1) for all c in max_worker_capacities where c <= i

                - We update `dp[i]` by considering each capacity `c` that can contribute to the current workload `i`.
                - If a worker with capacity `c` can be used, we check if using it results in a smaller number of workers.

        **Time Complexity**
            - O(W * n), where `W` is the `workload` and `n` is the number of worker capacities.
                - We iterate over each workload amount from `1` to `W`.
                - For each amount, we iterate over all worker capacities.
                - This results in a total of `W * n` iterations.

        **Space Complexity**:
            - O(W), where `W` is the `workload`.
                - We use a one-dimensional DP array of size `workload + 1`.
    """

    dp = [inf] * (workload + 1)
    dp[0] = 0
    if return_worker_indexes:
        workers = [() for _ in range(workload + 1)]
        for i in range(workload + 1):
            min_dispatch = inf
            this_workers = ()
            for worker_index, c in enumerate(worker_capacities):
                if i == c:
                    min_dispatch = 1
                    this_workers = (worker_index,)
                    break
                elif i > c:
                    dispatch_if_c_is_chosen = dp[i - c] + 1
                    if dispatch_if_c_is_chosen < min_dispatch:
                        min_dispatch = dispatch_if_c_is_chosen
                        this_workers = (*workers[i - c], worker_index)

            dp[i] = min_dispatch
            workers[i] = this_workers

        return (-1, None) if dp[-1] is inf else (dp[-1], workers[-1])
    else:
        for i in range(workload + 1):
            min_dispatch = inf
            for c in worker_capacities:
                if i == c:
                    min_dispatch = 1
                    break
                elif i > c:
                    min_dispatch = min(dp[i - c] + 1, min_dispatch)

            dp[i] = min_dispatch

        return -1 if dp[-1] is inf else dp[-1]


def max_value_given_capacity(
        capacity: int,
        item_weights: Sequence[int],
        item_values: Sequence[Number]
) -> Number:
    """
    Calculates the maximum total value of items that can be placed into a knapsack of given capacity,
    where each item has a specific weight and value.

    Args:
        capacity (int): The maximum capacity of the knapsack.
        item_weights (Sequence[int]): A sequence of item weights.
        item_values (Sequence[Number]): A sequence of item values corresponding to each item.

    Returns:
        Number: The maximum total value achievable within the given capacity.

    Examples:
        >>> max_value_given_capacity(5,[2, 3, 4, 5],[3, 4, 5, 6])
        7
        >>> max_value_given_capacity(5,[1, 2, 3],[6, 10, 12])
        22
        >>> max_value_given_capacity(4,[1, 4, 3, 1],[1500, 3000, 2000, 1800])
        3800
        >>> max_value_given_capacity(5, [2, 3, 4], [3, 4, 5])
        7
        >>> max_value_given_capacity(10, [5, 4, 6, 3], [10, 40, 30, 50])
        90
        >>> max_value_given_capacity(7, [1, 3, 4, 5], [1, 4, 5, 7])
        9
        >>> max_value_given_capacity(0, [1, 2, 3], [10, 20, 30])
        0
        >>> max_value_given_capacity(5, [6, 7, 8], [10, 20, 30])
        0

    Notes:
        **Problem Statement**:
            - Given a set of items, each with a weight and a value, determine the items to include in a knapsack
              so that the total weight does not exceed the knapsack capacity and the total value is maximized.
            - This is the classic **0/1 Knapsack Problem** where items cannot be divided.

        **Dynamic Programming Explanation**:
            - **State Definition**:
                - Let `value[i][c]` represent the maximum value that can be achieved using the first `i` items
                  with a capacity of `c`.
            - **Recursive Formula**:
                - If `item_weights[i - 1] <= c`:
                    ```python
                    value[i][c] = max(
                        value[i - 1][c],
                        value[i - 1][c - item_weights[i - 1]] + item_values[i - 1]
                    )
                    ```
                    - **Include the item**: Add the item's value to the optimal value of the remaining capacity.
                    - **Exclude the item**: Carry forward the optimal value without the current item.
                - Else:
                    ```python
                    value[i][c] = value[i - 1][c]
                    ```
                    - The item cannot be included as it exceeds the current capacity `c`.
            - **Base Cases**:
                - `value[0][c] = 0` for all capacities `c` (no items means zero value).
                - `value[i][0] = 0` for all items `i` (zero capacity means zero value).
            - **Dynamic Programming Pattern**:
                - The problem exhibits **optimal substructure** and **overlapping subproblems**.
                - We build up the solution by solving smaller subproblems and storing their results.

        **Time Complexity**:
            - **O(n * capacity)**, where `n` is the number of items.
                - We fill a table of size `(n + 1) * (capacity + 1)`.
            - Efficient for moderate values of `capacity` and `n`.

        **Space Complexity**:
            - **O(n * capacity)**, due to the 2D DP table `value`.

        **Constraints**:
            - `capacity` must be a non-negative integer.
            - Lengths of `item_weights` and `item_values` must be equal.
            - `item_weights` and `item_values` must contain non-negative numbers.

    """
    num_items = len(item_weights)
    value = [[0] * (capacity + 1) for _ in range(num_items + 1)]

    for i in range(1, num_items + 1):
        item_weight = item_weights[i - 1]
        item_value = item_values[i - 1]
        for c in range(1, capacity + 1):
            if c >= item_weight:
                value[i][c] = max(
                    value[i - 1][c],
                    value[i - 1][c - item_weight] + item_value
                )
            else:
                value[i][c] = value[i - 1][c]

    return value[num_items][capacity]


def max_value_given_capacity_recursive(
        capacity: Number,
        item_weights: Sequence[Number],
        item_values: Sequence[Number]
) -> Number:
    """
    Solves the 0/1 Knapsack Problem using a recursive approach.

    Args:
        capacity (Number): Maximum capacity of the knapsack.
        item_weights (Sequence[Number]): Sequence of item weights.
        item_values (Sequence[Number]): Corresponding sequence of item values.

    Returns:
        Number: The maximum value achievable with the given weights and capacity.

    Examples:
        >>> max_value_given_capacity_recursive(5, [2, 3, 4, 5], [3, 4, 5, 6])
        7
        >>> max_value_given_capacity_recursive(5, [1, 2, 3], [6, 10, 12])
        22
        >>> max_value_given_capacity_recursive(4, [1, 4, 3, 1], [1500, 3000, 2000, 1800])
        3800
        >>> max_value_given_capacity_recursive(5, [2, 3, 4], [3, 4, 5])
        7
        >>> max_value_given_capacity_recursive(10, [5, 4, 6, 3], [10, 40, 30, 50])
        90
        >>> max_value_given_capacity_recursive(7, [1, 3, 4, 5], [1, 4, 5, 7])
        9
        >>> max_value_given_capacity_recursive(0, [1, 2, 3], [10, 20, 30])
        0
        >>> max_value_given_capacity_recursive(5, [6, 7, 8], [10, 20, 30])
        0

    Notes:
        - This is a basic recursive implementation without memoization.
        - **Time Complexity**: O(2^n), where `n` is the number of items.
            - Each item has two possibilities: include it or exclude it.
            - This leads to exponential growth in the number of recursive calls.
        - **Space Complexity**: O(n)
            - The maximum depth of the recursion tree is `n`.
            - Each recursive call adds a new layer to the call stack.

        **Dynamic Programming Explanation**:
            - Although this function uses recursion without memoization, it mirrors the decision-making process of the dynamic programming approach.
            - **State Definition**:
                - Let `dp[i][w]` represent the maximum value that can be achieved with the first `i` items and a capacity of `w`.
            - **Recursive Formula**:
                1. If `item_weights[i - 1] <= w`:
                    ```python
                    dp[i][w] = max(
                        dp[i - 1][w],  # Exclude the item
                        dp[i - 1][w - item_weights[i - 1]] + item_values[i - 1]  # Include the item
                    )
                    ```
                    - **Include the item**: Gain value `item_values[i - 1]` and reduce capacity by `item_weights[i - 1]`.
                    - **Exclude the item**: Keep the previous maximum value without including the current item.
                2. Else:
                    ```python
                    dp[i][w] = dp[i - 1][w]
                    ```
                    - The item cannot be included because it exceeds the current capacity `w`.
            - **Base Cases**:
                - `dp[0][w] = 0` for all capacities `w` (no items means zero value).
                - `dp[i][0] = 0` for all items `i` (zero capacity means zero value).

    """
    return _knapsack_recursion_helper(capacity, item_weights, item_values, len(item_weights))


def _knapsack_recursion_helper(
        capacity: Number,
        item_weights: Sequence[Number],
        item_values: Sequence[Number],
        n: int
) -> int:
    # Base Case: No items left or capacity is 0
    if n == 0 or capacity == 0:
        return 0

    # If weight of the nth item is more than the capacity W, it cannot be included
    if item_weights[n - 1] > capacity:
        return _knapsack_recursion_helper(capacity, item_weights, item_values, n - 1)
    else:
        # Return the maximum of two cases:
        # 1. nth item included
        # 2. nth item not included
        included = item_values[n - 1] + _knapsack_recursion_helper(
            capacity - item_weights[n - 1],
            item_weights,
            item_values,
            n - 1
        )
        excluded = _knapsack_recursion_helper(capacity, item_weights, item_values, n - 1)
        return max(included, excluded)
