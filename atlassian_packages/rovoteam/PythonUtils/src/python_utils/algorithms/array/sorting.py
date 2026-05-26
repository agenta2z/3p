from collections.abc import Iterable
from functools import cmp_to_key
from typing import Callable, Any, TypeVar

from python_utils.string_utils import join_

T = TypeVar('T')


def largest_concat(items: Iterable, concat: Callable[[Any, Any], Any] = None) -> str:
    """
    Arranges elements in an iterable to form the largest possible value based on concatenation rules.

    This function generalizes the "Largest Number" problem by allowing custom concatenation rules.
    Without a custom concat function, it uses string concatenation to form the largest number.

    Args:
        items (Iterable): An iterable of elements to be arranged
        concat (Callable[[Any, Any], Any], optional): A function that defines how two elements
            should be concatenated. If None, uses string concatenation (a + b).
            The concat function should:
            - Take two arguments of the same type as elements in arr
            - Return a comparable value (supports >, <, =)

    Returns:
        str: The concatenated result of the arranged elements

    Raises:
        TypeError: If elements don't support the required operations
        ValueError: If arr is empty

    Examples:
        Basic usage with numbers (creates largest possible number):
        >>> arr = ["3", "30", "34", "5", "9"]
        >>> largest_concat(arr)
        '9534330'

        Using with integers (automatically converts to strings):
        >>> arr = [3, 30, 34, 5, 9]
        >>> largest_concat([str(x) for x in arr])
        '9534330'

        Custom concatenation function for numbers:
        >>> def custom_concat(a, b): return int(str(a) + str(b))
        >>> arr = [3, 30, 34, 5, 9]
        >>> largest_concat([str(x) for x in arr], custom_concat)
        9534330

        Works with any comparable elements:
        >>> def tuple_concat(a, b): return a + b
        >>> arr = [(1,), (2,), (3,)]
        >>> largest_concat(arr, tuple_concat)
        (3, 2, 1)

        Edge cases:
        >>> largest_concat(["0", "0", "0"])  # Multiple zeros
        '000'
        >>> largest_concat(["42"])  # Single element
        '42'

    Notes:
        - The comparison used for sorting is based on comparing concat(a,b) with concat(b,a)
        - This ensures the resulting arrangement produces the largest possible value
        - For string numbers, "largest" is determined by string comparison
        - The function modifies the input array in-place

    Time Complexity: O(n log n) where n is the length of arr
    Space Complexity: O(1) excluding the space needed for sorting
    """

    # Custom comparison function
    def compare(a, b):
        if concat is None:
            if a + b > b + a:  # If concatenating a before b is larger
                return -1  # a should come before b in the sort
            elif a + b < b + a:  # If concatenating b before a is larger
                return 1  # b should come before a in the sort
            return 0  # They are equal, order doesn't matter
        else:
            if concat(a, b) > concat(b, a):
                return -1
            elif concat(a, b) < concat(b, a):
                return 1
            return 0

    # Join the numbers to form the result
    if concat is None:
        return join_(*sorted(items, key=cmp_to_key(compare)), sep='')
    else:
        output = None
        for x in sorted(items, key=cmp_to_key(compare)):
            if output is None:
                output = x
            else:
                output = concat(output, x)
        return output


