from enum import Enum
from functools import partial
from typing import Union, Iterable, Callable, Optional
from python_utils.common_utils.iter_helper import unzip
from python_utils.common_utils.map_helper import get_
from python_utils.common_utils.typing_helper import iterable
import heapq
from collections import Counter

class SortOptions(str, Enum):
    NoSorting = 'none',
    Descending = 'desc'
    Ascending = 'asc'


def _get_sort_key(key: Union[str, Iterable[str], Callable]) -> Optional[Callable]:
    """
    Internal function for solving sorting key.

    When the sorting key is string, or a sequence of strings,
    then we assume the objects to sort contain fields/values associated with the specified string
    keys, and we construct a callable to use in the `sorted` function as the sorting key.

    If `key` is None, then None is returned.

    """
    if key is None:
        return None
    elif isinstance(key, str):
        return partial(get_, key1=key)
    elif iterable(key) and isinstance(next(iter(key)), str):
        return lambda x: tuple(get_(x, _key) for _key in key)
    elif callable(key):
        return key
    else:
        raise ValueError("the sorting 'key' must be a callable, "
                         "or a string, "
                         "or a list/tuple of strings; "
                         f"got '{key}'")


def sorted_(
        _iterable,
        key: Union[str, Iterable[str], Callable] = None,
        reverse: bool = False,
        no_sort_if_key_is_none: bool = False,
        sort_option: Union[str, SortOptions] = None
):
    """
    Performs the same sorting operation as the system function `sorted`,
    but provides additional options to tweak some minor behaviors.

    This function also supports using string(s) as strong key(s).

    When `key` is a string, or a list/tuple of strings,
    then we assume the objects to sort contain fields/values associated with the specified string
    keys, and we construct a callable to use in the `sorted` function as the sorting key.

    Args:
        _iterable: the iterable to sort.
        key: the sorting key; can be a string, a sequence of strings, or a callable.
        reverse: True to sort the iterable in the descending order.
        no_sort_if_key_is_none: True to perform no sorting if `key` is set None, instead of
            the default behavior of sorting in the ascending order.
        sort_option: one convenient option to control whether we perform no soring,
            or sort in the ascending order, or sort in the descending order; 
            the purpose is to use one argument to control this frequently used behavior option 
            instead of using two arguments from `reverse` and `no_sort_if_key_is_none`.
            If specified, this parameter has higher priority.

    Returns: a new list containing all items from the iterable in a sorted order.

    Examples:
        >>> sorted_([4, 5, 2, 1, 3])
        [1, 2, 3, 4, 5]
        >>> sorted_([4, 5, 2, 1, 3], reverse=True)
        [5, 4, 3, 2, 1]
        >>> sorted_([4, 5, 2, 1, 3], sort_option=SortOptions.Descending)
        [5, 4, 3, 2, 1]
        >>> sorted_([4, 5, 2, 1, 3], no_sort_if_key_is_none=True)
        [4, 5, 2, 1, 3]
        >>> sorted_([4, 5, 2, 1, 3], sort_option=SortOptions.NoSorting)
        [4, 5, 2, 1, 3]
        >>> sorted_(
        ...     [{'k': 2, 'v': 'b'}, {'k': 1 , 'v': 'c'}, {'k': 3 , 'v': 'a'}],
        ...     key='k'
        ... )
        [{'k': 1, 'v': 'c'}, {'k': 2, 'v': 'b'}, {'k': 3, 'v': 'a'}]
        >>> sorted_(
        ...     [{'k': 2, 'v': 'b'}, {'k': 1 , 'v': 'c'}, {'k': 3 , 'v': 'a'}],
        ...     key='v',
        ...     reverse=True
        ... )
        [{'k': 1, 'v': 'c'}, {'k': 2, 'v': 'b'}, {'k': 3, 'v': 'a'}]
        >>> sorted_(
        ...     [{'k': 2, 'v': 'b'}, {'k': 1 , 'v': 'c'}, {'k': 3 , 'v': 'a'}],
        ...     key=('v', 'a')
        ... )
        [{'k': 3, 'v': 'a'}, {'k': 2, 'v': 'b'}, {'k': 1, 'v': 'c'}]

    """
    if sort_option is not None:
        if sort_option == SortOptions.NoSorting:
            if reverse:
                raise ValueError("'reverse is set True' but 'sort_option' "
                                 "asks for no sorting")
            return _iterable
        elif sort_option == SortOptions.Ascending:
            if reverse:
                raise ValueError("'reverse is set True' but 'sort_option' "
                                 "asks for soring in the ascending order")
            reverse = False
        elif sort_option == SortOptions.Descending:
            reverse = True

    if key is None:
        if no_sort_if_key_is_none:
            return _iterable
        else:
            return sorted(_iterable, reverse=reverse)
    else:
        key = _get_sort_key(key)
        return sorted(_iterable, key=_get_sort_key(key), reverse=reverse)


def sorted_with_transform(
        _iterable,
        key: Union[str, Iterable[str], Callable] = None,
        reverse: bool = False,
        element_transform: Callable = None,
        sort_before_transform: bool = True,
        no_sort_if_key_is_none: bool = False,
        sort_option: Union[str, SortOptions] = None
):
    """
    Sorts an iterable with optional element transformation, either before or after sorting.

    This function extends the functionality of `sorted_` by allowing for element-wise transformations.
    If `element_transform` is provided, it can be applied either before or after sorting.

    Parameters:
        _iterable (iterable): The input iterable to be sorted.
        key (Union[str, Iterable[str], Callable]): The sorting key; can be a string, a sequence of strings, or a callable.
        reverse (bool): If True, sorts in descending order. Defaults to False.
        element_transform (Callable, optional): A callable to transform elements. Defaults to None.
        sort_before_transform (bool): If True, applies `element_transform` after sorting. If False, applies it before sorting. Defaults to True.
        no_sort_if_key_is_none (bool): If True and `key` is None, returns the iterable without sorting. Defaults to False.
        sort_option (Union[str, SortOptions], optional): Controls sorting behavior (e.g., ascending, descending, or no sorting). Defaults to None.

    Returns:
        Union[list, map]: A sorted list or a transformed iterable (lazy if `element_transform` is provided).

    Examples:
        >>> sorted_with_transform([3, 1, 4, 1, 5])
        [1, 1, 3, 4, 5]

        >>> sorted_with_transform([3, 1, 4, 1, 5], reverse=True)
        [5, 4, 3, 1, 1]

        >>> sorted_with_transform([3, 1, 4, 1, 5], element_transform=lambda x: x**2)
        <map object at ...>
        >>> list(sorted_with_transform([3, 1, 4, 1, 5], element_transform=lambda x: x**2))
        [1, 1, 9, 16, 25]

        >>> sorted_with_transform([3, 1, 4, 1, 5], element_transform=lambda x: x**2, sort_before_transform=False)
        [1, 1, 9, 16, 25]

        >>> data = [{'value': 3}, {'value': 1}, {'value': 4}]
        >>> sorted_with_transform(data, key='value', element_transform=lambda x: x['value'])
        <map object at ...>
        >>> list(sorted_with_transform(data, key='value', element_transform=lambda x: x['value']))
        [1, 3, 4]

        >>> sorted_with_transform(data, no_sort_if_key_is_none=True)
        [{'value': 3}, {'value': 1}, {'value': 4}]
    """
    if element_transform is None:
        return sorted_(
            _iterable,
            key=key,
            reverse=reverse,
            no_sort_if_key_is_none=no_sort_if_key_is_none,
            sort_option=sort_option
        )
    else:
        if sort_before_transform:
            return map(
                element_transform,
                sorted_(
                    _iterable,
                    key=key,
                    reverse=reverse,
                    no_sort_if_key_is_none=no_sort_if_key_is_none,
                    sort_option=sort_option
                )
            )
        else:
            return sorted_(
                map(element_transform, _iterable),
                key=key,
                reverse=reverse,
                no_sort_if_key_is_none=no_sort_if_key_is_none,
                sort_option=sort_option
            )


def sorted__(
        _iterable,
        key: Union[str, Iterable[str], Callable] = None,
        reverse: bool = False,
        return_tuple: bool = False,
        return_values: bool = True,
        return_indexes: bool = False
):
    """
    An enhanced alternative to the built-in `sorted` function.

    Provides additional capabilities:
    1. Supports sequence-based sorting keys.
    2. Allows returning indexes of original items using `return_indexes`.
    3. Can return a tuple instead of a list using `return_tuple`.

    Args:
        _iterable (Iterable): A sequence of objects to sort.
        key (Union[str, Iterable[str], Callable], optional):
            Sorting key, which can be:
            - A callable (like in the built-in `sorted`).
            - A sequence of values corresponding to sorting keys for `_iterable`.
            - A string or sequence of strings representing fields to extract for sorting.
        reverse (bool, optional): If True, sorts in descending order. Defaults to False.
        return_tuple (bool, optional): If True, returns the result as a tuple. Defaults to False.
        return_values (bool, optional): If True, includes the sorted values in the output. Defaults to True.
        return_indexes (Union[bool, str], optional):
            - If True, returns the indexes of the original items along with the sorted items.
            - If 'labels', returns positional ranks (labels) of items in the sorted order.
            Defaults to False.

    Returns:
        Union[list, tuple]:
            - A sorted list (default) or tuple (if `return_tuple=True`) of elements.
            - If `return_indexes=True`, returns a list/tuple of (item, index) pairs.
            - If `return_indexes='labels'`, returns a list/tuple of (item, label) pairs.

    Notes:
        - **Sequence-Based Keys**: Unlike the built-in `sorted`, `sorted__` allows passing a sequence of keys directly,
          simplifying sorting when keys are already computed.
        - **Returning Indexes**: You can track original indexes using `return_indexes=True` or return positional ranks
          using `return_indexes='labels'`.
        - **Tuple Output**: If `return_tuple=True`, the sorted result is returned as a tuple instead of a list.
        - **Stability**: Maintains stability by ensuring the original order of elements with duplicate keys.

    Examples:
        # Basic sorting:
        >>> sorted__([3, 1, 4, 1, 5], key=None)
        [1, 1, 3, 4, 5]

        # Descending sorting:
        >>> sorted__([3, 1, 4, 1, 5], key=None, reverse=True)
        [5, 4, 3, 1, 1]

        # Sorting with sequence-based keys:
        >>> sorted__([10, 20, 30], key=[3, 1, 2])
        [20, 30, 10]

        # Returning indexes:
        >>> sorted__([10, 20, 30], key=[3, 1, 2], return_indexes=True)
        [(20, 1), (30, 2), (10, 0)]

        # Returning positional ranks (labels):
        >>> sorted__([10, 20, 30], key=[3, 1, 2], return_indexes='labels')
        [(20, 2), (30, 0), (10, 1)]
        >>> sorted__([10, 20, 30], key=[3, 1, 2], return_indexes='labels', return_values=False)
        [2, 0, 1]

        # Returning as tuple:
        >>> sorted__([10, 20, 30], key=[3, 1, 2], return_tuple=True)
        (20, 30, 10)

        # Using a callable key:
        >>> sorted__([3, 1, 4, 1, 5], key=lambda x: -x)
        [5, 4, 3, 1, 1]

        # Handling stability with duplicate keys:
        >>> sorted__(['a', 'b', 'c'], key=[1, 2, 1])
        ['a', 'c', 'b']
    """

    if return_indexes is True:
        if callable(key):
            _key = lambda x: key(x[0])
        else:
            _key = key

        result = sorted__(
            ((x, i) for i, x in enumerate(_iterable)),
            key=_key,
            reverse=reverse,
            return_tuple=return_tuple,
            return_indexes=False
        )
        if return_values:
            return result
        else:
            if return_tuple:
                return tuple(index for _, index in result)
            else:
                return list(index for _, index in result)
    elif return_indexes == 'labels':
        sorted_tups = sorted__(
            ((x, i) for i, x in enumerate(_iterable)),
            key=key,
            reverse=reverse,
            return_tuple=True,
            return_indexes=False
        )
        labels = [0] * len(sorted_tups)
        for j, (x, i) in enumerate(sorted_tups):
            labels[i] = j
        if return_values:
            out = ((x, l) for (x, i), l in zip(sorted_tups, labels))
            return tuple(out) if return_tuple else list(out)
        else:
            return tuple(labels) if return_tuple else labels

    if callable(key):
        s = sorted(_iterable, key=key, reverse=reverse)
        return tuple(s) if return_tuple else s
    elif key is None:
        s = sorted(_iterable, reverse=reverse)
        return tuple(s) if return_tuple else s
    else:
        s = unzip(
            unzip(
                sorted(zip(key, enumerate(_iterable)), reverse=reverse),
                1
            ), 1
        )  # `enumerate(_iterable)` ensures the original order of the `_iterable` when keys are the same
        return s if return_tuple else list(s)


def topk_frequent(iterable, k):
    """
    Find the k most frequent elements in an iterable.

    Parameters:
        iterable (iterable): The input iterable (e.g., list, tuple) of elements.
        k (int): The number of top frequent elements to return.

    Returns:
        list: A list of the k most frequent elements, in descending order of frequency.

    Examples:
        >>> topk_frequent([1, 2, 2, 3, 3, 3], 2)
        [3, 2]

        >>> topk_frequent([7, 7, 7, 8, 8, 9], 1)
        [7]

        >>> topk_frequent(['apple', 'banana', 'apple', 'apple', 'banana', 'cherry'], 2)
        ['apple', 'banana']

        >>> topk_frequent([1], 1)
        [1]

        >>> topk_frequent([], 1)
        []
    """
    frequency_map = Counter(iterable)
    top_k = heapq.nlargest(k, frequency_map.keys(), key=frequency_map.get)
    return top_k