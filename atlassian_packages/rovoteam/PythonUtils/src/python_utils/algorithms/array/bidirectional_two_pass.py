from typing import Sequence, List


def product_except_self(nums):
    """
    Calculate the product of all elements except the current index for each element in the array.
    The solution is implemented in O(n) time complexity without using division operations.
    It uses two passes: one to compute the cumulative product of elements to the left of each index,
    and another to compute the cumulative product of elements to the right.

    Args:
        nums (List[int]): A list of integers where 2 <= len(nums) <= 1000 and -20 <= nums[i] <= 20.

    Returns:
        List[int]: A list where each element is the product of all elements in `nums` except `nums[i]`.

    Notes:
        Time Complexity: O(n) - The function makes two passes through the input list (left-to-right and right-to-left).
        Space Complexity: O(n) - The function uses an output array of size n to store the results.
                               While the output array is part of the required return value,
                               it still constitutes O(n) auxiliary space during computation.

    Examples:
        >>> product_except_self([1, 2, 4, 6])
        [48, 24, 12, 8]
        >>> product_except_self([-1, 0, 1, 2, 3])
        [0, -6, 0, 0, 0]
        >>> product_except_self([2, 3])
        [3, 2]
        >>> product_except_self([5, -2, 3])
        [-6, 15, -10]
    """
    n = len(nums)
    output = [1] * n  # Initialize the output array

    # Compute left product for each index
    left_product = 1
    for i in range(n):
        output[i] = left_product
        left_product *= nums[i]

    # Compute right product for each index and multiply
    right_product = 1
    for i in range(n - 1, -1, -1):
        output[i] *= right_product
        right_product *= nums[i]

    return output


def find_equilibrium_indexes(arr: Sequence) -> List[int]:
    """
    Identifies all equilibrium indices in the given array.

    An **equilibrium index** is an index `i` such that the sum of elements
    to the left of `i` is equal to the sum of elements to the right of `i`.
    If no such index exists, the function returns an empty list.

    The function iterates through the array, maintaining the cumulative sum of
    elements on the left and right of the current index to determine equilibrium points.

    Args:
        arr (Sequence): A sequence of numerical values (integers or floats).

    Returns:
        List[int]: A list of all equilibrium indices. The list is empty if no equilibrium index exists.

    Examples:
        Basic Cases:
        >>> find_equilibrium_indexes([1, 3, 5, 2, 2])
        [2]

        >>> find_equilibrium_indexes([2, 4, 2])
        [1]

        No Equilibrium Index:
        >>> find_equilibrium_indexes([1, 2, 3])
        []

        Multiple Equilibrium Indices:
        >>> find_equilibrium_indexes([0, -1, 1, 0])
        [0, 3]

        Single Element Array:
        >>> find_equilibrium_indexes([10])
        [0]

        Empty Array:
        >>> find_equilibrium_indexes([])
        []

        Including Negative Numbers:
        >>> find_equilibrium_indexes([-7, 1, 5, 2, -4, 3, 0])
        [3, 6]

        All Elements Zero:
        >>> find_equilibrium_indexes([0, 0, 0, 0])
        [0, 1, 2, 3]
    """
    right_sum = sum(arr)
    left_sum = 0
    equilibrium_indexes = []

    for i, num in enumerate(arr):
        right_sum -= num
        if left_sum == right_sum:
            equilibrium_indexes.append(i)
        left_sum += num
    return equilibrium_indexes
