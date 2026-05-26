from typing import Callable, List, Sequence, Any, Tuple, Union, Iterator, Optional, Iterable, Type

from python_utils.common_objects.search_fallback_options import SearchFallbackOptions
from python_utils.common_utils.misc import distribute_by_weights, split_int, split_float


# region List Conversion

def list_(
        obj: Any,
        list_type: Type = list,
        non_atom_types: tuple = (tuple, set),
        iter_none: bool = False,
        always_consider_iterator_as_non_atom: bool = True
) -> list:
    """
    Converts an object to a list, avoiding unnecessary copies if already a list.

    This function intelligently converts objects to lists by leveraging `iter_()` from iter_helper
    to handle atomicity. If the object is already an instance of `list_type`, it returns the
    same object (no copy). Otherwise, it converts using `iter_()` which respects `non_atom_types`.

    Behavior:
    - **obj is instance of list_type**: Returns obj unchanged (no copy, same object)
    - **obj is non-atomic** (type in non_atom_types): Unpacks elements into new list
    - **obj is atomic**: Creates list with single element [obj]
    - **obj is None and iter_none=False**: Returns empty list []
    - **obj is None and iter_none=True**: Returns [None]

    Args:
        obj (Any): The object to convert to a list.
        list_type (Type, optional): The type to check for list identity. If obj is already
            this type, return it unchanged. Defaults to list.
        non_atom_types (tuple, optional): Types to treat as non-atomic (iterable).
            Elements of these types will be unpacked. Defaults to (tuple, set).
            Note: list is intentionally excluded to enable the identity check.
        iter_none (bool, optional): If True, treats None as [None]. If False, returns [].
            Defaults to False.
        always_consider_iterator_as_non_atom (bool, optional): If True, any Iterator/Iterable
            is treated as non-atomic. Defaults to True.

    Returns:
        list: The resulting list. Either the same obj (if already list_type) or a new list.

    Examples:
        # Identity: list input returns same object
        >>> my_list = [1, 2, 3]
        >>> result = list_(my_list)
        >>> result is my_list
        True

        # Convert tuple to list (non-atomic by default)
        >>> list_((1, 2, 3))
        [1, 2, 3]

        # Convert set to list (non-atomic by default)
        >>> sorted(list_({3, 1, 2}))
        [1, 2, 3]

        # Atomic types create single-element list
        >>> list_(5)
        [5]
        >>> list_('hello')
        ['hello']

        # None handling
        >>> list_(None)
        []
        >>> list_(None, iter_none=True)
        [None]

        # Control atomicity
        >>> list_((1, 2, 3), non_atom_types=())  # Treat tuple as atomic
        [(1, 2, 3)]
        >>> list_((1, 2, 3), non_atom_types=(tuple,))  # Treat tuple as non-atomic
        [1, 2, 3]

        # Custom list type
        >>> my_list = [1, 2, 3]
        >>> list_(my_list, list_type=list) is my_list
        True

    Notes:
        - **Performance**: When obj is already a list, no copy is made (returns same object).
        - **Atomicity**: Determined by `iter_()` using `non_atom_types`.
        - **list excluded from non_atom_types**: By default, list is NOT in non_atom_types
          to enable the identity optimization. If you want to copy a list, use `list(obj)`.
        - **Consistency**: Uses `iter_()` from iter_helper for consistent atomicity handling.
        - Time Complexity: O(1) if already list, O(n) otherwise where n is element count.
        - Space Complexity: O(1) if already list, O(n) for new list.
    """
    from python_utils.common_utils.iter_helper import iter_
    if isinstance(obj, list_type):
        return obj
    return list(iter_(
        obj,
        non_atom_types=non_atom_types,
        iter_none=iter_none,
        always_consider_iterator_as_non_atom=always_consider_iterator_as_non_atom
    ))


def list__(
        obj: Any,
        list_type: Type = list,
        atom_types: tuple = (str,),
        iter_none: bool = False
) -> list:
    """
    Converts an object to a list using atom_types approach, avoiding unnecessary copies.

    This function is similar to `list_()` but uses the `iter__()` approach where you specify
    which types are ATOMIC (non-iterable) rather than which are non-atomic. This is often
    more convenient when you want most iterables unpacked except specific types like strings.

    Behavior:
    - **obj is instance of list_type**: Returns obj unchanged (no copy, same object)
    - **obj is NOT in atom_types and is iterable**: Unpacks elements into new list
    - **obj is in atom_types**: Creates list with single element [obj]
    - **obj is None and iter_none=False**: Returns empty list []
    - **obj is None and iter_none=True**: Returns [None]

    Args:
        obj (Any): The object to convert to a list.
        list_type (Type, optional): The type to check for list identity. If obj is already
            this type, return it unchanged. Defaults to list.
        atom_types (tuple, optional): Types to treat as atomic (non-iterable).
            These types will NOT be unpacked. Defaults to (str,).
        iter_none (bool, optional): If True, treats None as [None]. If False, returns [].
            Defaults to False.

    Returns:
        list: The resulting list. Either the same obj (if already list_type) or a new list.

    Examples:
        # Identity: list input returns same object
        >>> my_list = [1, 2, 3]
        >>> result = list__(my_list)
        >>> result is my_list
        True

        # String is atomic by default (not unpacked)
        >>> list__('hello')
        ['hello']

        # String unpacked when removed from atom_types
        >>> list__('hello', atom_types=())
        ['h', 'e', 'l', 'l', 'o']

        # Iterables unpacked
        >>> list__((1, 2, 3))
        [1, 2, 3]
        >>> sorted(list__({3, 1, 2}))
        [1, 2, 3]

        # Atomic types
        >>> list__(5)
        [5]
        >>> list__(None)
        []
        >>> list__(None, iter_none=True)
        [None]

        # Custom atom types
        >>> list__((1, 2, 3), atom_types=(tuple,))
        [(1, 2, 3)]
        >>> list__((1, 2, 3), atom_types=(str,))
        [1, 2, 3]

    Notes:
        - **Performance**: When obj is already a list, no copy is made (returns same object).
        - **Atomicity**: Determined by `iter__()` using `atom_types` (inverse of `list_()`).
        - **Default behavior**: Strings are atomic by default, so they won't be unpacked to chars.
        - **list excluded from atom_types**: List is NOT atomic by default to enable identity check.
        - **Consistency**: Uses `iter__()` from iter_helper for consistent atomicity handling.
        - **Use case**: Prefer `list__()` when it's easier to specify what NOT to unpack.
        - Time Complexity: O(1) if already list, O(n) otherwise where n is element count.
        - Space Complexity: O(1) if already list, O(n) for new list.
    """
    from python_utils.common_utils.iter_helper import iter__
    if isinstance(obj, list_type):
        return obj
    return list(iter__(obj, atom_types=atom_types, iter_none=iter_none))


# endregion

# region Searching and Indexing

def index_of_last_non_null(seq: Sequence) -> int:
    """
    Finds the index of the last non-null (non-None) element in a sequence.

    Args:
        seq (Sequence): The input sequence to search.

    Returns:
        int: The index of the last non-null element, or -1 if no such element exists.

    Examples:
        >>> index_of_last_non_null([None, 2, None, 4, None])
        3
        >>> index_of_last_non_null([None, None, None])
        -1
        >>> index_of_last_non_null([1, 2, 3])
        2
        >>> index_of_last_non_null([])
        -1
    """
    for i in range(len(seq) - 1, -1, -1):
        if seq[i] is not None:
            return i
    return -1


def index_(
        seq: Sequence,
        x: Union[Callable[[Any], bool], Any],
        start: int = 0,
        end: int = None,
        raise_error: bool = False
) -> int:
    """
    Return the index of the first occurrence of an element in a sequence, or match a predicate.

    This function can operate in two modes:
    1. **Direct value match**: If `x` is not callable, it searches for `x` in `seq`.
    2. **Predicate match**: If `x` is a callable (i.e., `lambda item: condition(item)`), it
       returns the index of the first element in `seq` for which the predicate returns True.

    The search is performed from index `start` up to (but not including) `stop`.
    If `stop` is None, the search proceeds until the end of the sequence.

    If no match is found:
        - By default, the function returns `-1`.
        - If `raise_error=True`, it raises a `ValueError`.

    Args:
        seq (Sequence):
            The sequence to search in.
        x (Union[Callable[[Any], bool], Any]):
            The value to look for, or a predicate function that returns True for the desired element.
        start (int, optional):
            The starting index to search from. Defaults to 0.
        end (int, optional):
            The ending index (exclusive) to search up to. Defaults to None (search until the end).
        raise_error (bool, optional):
            If True, raise a ValueError instead of returning `-1` when no match is found.
            Defaults to False.

    Returns:
        int:
            - The index of the first matching element within `[start, stop)`.
            - `-1` if no match is found and `raise_error=False`.
            - Raises ValueError if no match is found and `raise_error=True`.

    Examples:
        >>> lst = [10, 20, 30, 40, 50]

        # 1) Searching for a direct value
        >>> index_(lst, 30)
        2

        # 2) Searching with a predicate (lambda) that checks a condition
        >>> index_(lst, lambda item: item > 25)
        2

        # 3) Value not found: returns -1
        >>> index_(lst, 60)
        -1

        # 4) Restricting the search range via 'start'
        >>> index_(lst, 30, start=3)
        -1

        # 5) Restricting the search range via 'start' and 'stop'
        >>> index_(lst, lambda item: item % 20 == 0, start=1, end=4)
        1

        # 6) If 'stop' < 'start', the search range is empty
        >>> index_(lst, 30, start=5, end=3)
        -1

        # 7) Searching an empty sequence
        >>> index_([], 10)
        -1

        # 8) Using 'raise_error=True' to raise ValueError if not found
        >>> try:
        ...     index_(lst, 60, raise_error=True)
        ... except ValueError as e:
        ...     print("ValueError was raised!")
        ValueError was raised!
    """
    if not seq:
        if raise_error:
            raise ValueError("No matching element found (sequence is empty).")
        return -1

    if end is None:
        end = len(seq)

    # Predicate search
    if callable(x):
        for i in range(start, end):
            if x(seq[i]):
                return i
        if raise_error:
            raise ValueError("No matching element found (predicate).")
        return -1

    # Direct value search
    else:
        if raise_error:
            # Let the built-in list.index(...) raise a ValueError automatically if not found.
            return seq.index(x, start, end)
        else:
            # Catch ValueError and return -1 if not found.
            try:
                return seq.index(x, start, end)
            except ValueError:
                return -1


def index__(
        seq: Sequence[Any],
        search: Union[Any, Callable[[Any], bool], Iterable[Any]],
        start: int = 0,
        end: int = None,
        return_at_first_match: bool = True,
        search_fallback_option: Union[str, SearchFallbackOptions] = SearchFallbackOptions.RaiseError,
        non_atom_types: tuple = (list,)
) -> Union[int, List[int]]:
    """
    Find the index or indices of an element, contiguous sub-sequence, or predicate match within a sequence.

    This function searches the slice ``seq[start:end]`` (with ``end`` defaulting to ``len(seq)`` if not provided)
    for a target specified by ``search``. The target can be provided as an atomic value, a callable predicate,
    or as an iterable (of a type in ``non_atom_types``) representing a contiguous sub-sequence.

    There are three search modes:

    1. **Predicate search:**
       If ``search`` is callable, each element in ``seq[start:end]`` is passed to ``search(element)``.
       All indices where the predicate returns True are considered matches.

    2. **Atomic search:**
       If ``search`` is a single value (or an iterable whose type is *not* in ``non_atom_types``),
       the function compares elements using equality (``==``) to find matches.

    3. **Sub-sequence search:**
       If ``search`` is an iterable whose type is in ``non_atom_types``, it is treated as a contiguous
       sub-sequence. The function searches for all starting indices where that sub-sequence occurs within ``seq``.

    The parameter ``return_at_first_match`` controls the return type:

      - If ``True``, the function returns a single index:
          - For multi-element targets (i.e. when ``search`` is of a type in ``non_atom_types``), the smallest index
            at which any element of the target appears is returned.
          - For atomic or predicate searches, the index of the first match is returned.

      - If ``False``, the function returns a list of all matching indices.

    The behavior when no match is found is determined by ``search_fallback_option``:

      - ``"raise_error"`` (or ``SearchFallbackOptions.RaiseError``):
           Raise a ``ValueError``.
      - ``"empty"`` (or ``SearchFallbackOptions.Empty``):
           Return ``-1`` in single-index mode or an empty list in list mode.
      - ``"eos"`` (or ``SearchFallbackOptions.EOS``):
           Return ``len(seq)`` in single-index mode or a list containing ``len(seq)`` in list mode.

    Args:
        seq (Sequence[Any]): The sequence to search within.
        search (Union[Any, Callable[[Any], bool], Iterable[Any]]):
            The target to find. This may be:
              - An atomic value for equality comparison,
              - A callable predicate that returns True for desired elements, or
              - An iterable (of a type in ``non_atom_types``) representing a contiguous sub-sequence.
        start (int, optional): The starting index for the search. Defaults to 0.
        end (int, optional): The ending index (exclusive) for the search. Defaults to None, which is interpreted as ``len(seq)``.
        return_at_first_match (bool, optional):
            - If True, return a single index (the earliest match).
            - If False, return a list of all matching indices.
            Defaults to True.
        search_fallback_option (Union[str, SearchFallbackOptions], optional):
            Specifies the fallback behavior if no match is found:
              - ``"raise_error"`` or ``SearchFallbackOptions.RaiseError``: raise a ``ValueError``.
              - ``"empty"`` or ``SearchFallbackOptions.Empty``: return ``-1`` (or an empty list) as appropriate.
              - ``"eos"`` or ``SearchFallbackOptions.EOS``: return ``len(seq)`` (or a list containing ``len(seq)``).
            Defaults to ``SearchFallbackOptions.RaiseError``.
        non_atom_types (tuple, optional):
            A tuple of types to treat as non-atomic (i.e. sequences) during the search.
            For example, if ``non_atom_types=(list,)``, then lists are treated as contiguous sub-sequences.
            Types not in this tuple are considered atomic.
            Defaults to ``(list,)``.

    Returns:
        Union[int, List[int]]:
            - If ``return_at_first_match`` is True, returns a single index (int) corresponding to the first match.
            - Otherwise, returns a list of all matching indices.

    Raises:
        ValueError: If no match is found and ``search_fallback_option`` is set to raise an error.

    Notes:
        - The search is limited to the slice ``seq[start:end]``.
        - In predicate search mode, each element in the slice is evaluated by the predicate.
        - In atomic search mode, elements are compared using ``==``.
        - In sub-sequence search mode, if ``search`` is of a type in ``non_atom_types``,
          the function looks for contiguous occurrences.
        - When ``return_at_first_match`` is True for a multi-element target,
          the function returns the smallest index where any element of the target is found, not necessarily a contiguous match.

    Examples:
        # 1) Atomic search for a single element.
        >>> index__([1, 2, 3, 4, 5], 3, return_at_first_match=True)
        2
        >>> index__([1, 2, 3, 4, 5], 3, return_at_first_match=False)
        [2]

        # 2) Predicate search.
        >>> index__([1, 2, 3, 4, 5], lambda x: x > 3, return_at_first_match=True)
        3
        >>> index__([1, 2, 3, 4, 5], lambda x: x > 3, return_at_first_match=False)
        [3, 4]

        # 3) Sub-sequence search: locate the contiguous sub-list [3, 4].
        >>> index__([1, 2, 3, 4, 5], [3, 4], return_at_first_match=True)
        2
        >>> index__([1, 2, 3, 4, 5], [3, 4], return_at_first_match=False)
        [2, 3]

        # 4) Restricting the search range using 'start' and 'end'.
        >>> index__([1, 2, 3, 4, 5], [3, 4], start=1, end=3)
        [2]
        >>> index__([1, 2, 3, 4, 5], [3, 4], start=0, end=2, search_fallback_option=SearchFallbackOptions.Empty)
        []

        # 5) Fallback behavior.
        >>> index__([1, 2, 3], 9, search_fallback_option="eos")
        [3]
        >>> index__([1, 2, 3], 9, search_fallback_option="empty")
        []
    """
    if end is None:
        end = len(seq)
    else:
        end = min(end, len(seq))

    def _fallback_single() -> int:
        if search_fallback_option == SearchFallbackOptions.RaiseError:
            raise ValueError(f"{search} not found in sequence.")
        elif search_fallback_option == SearchFallbackOptions.EOS:
            return len(seq)
        else:
            return -1

    def _fallback_list() -> List[int]:
        if search_fallback_option == SearchFallbackOptions.RaiseError:
            raise ValueError(f"{search} not found in sequence.")
        elif search_fallback_option == SearchFallbackOptions.EOS:
            return [len(seq)]
        else:
            return []

    if return_at_first_match:
        if isinstance(search, non_atom_types):
            # For multi-element searches treated as non-atomic, check each element.
            best_idx = None
            for search_item in search:
                idx = index_(seq, search_item, start=start, end=end, raise_error=False)
                if idx != -1:
                    if best_idx is None or idx < best_idx:
                        best_idx = idx
            if best_idx is not None:
                return best_idx
        else:
            idx = index_(seq, search, start=start, end=end, raise_error=False)
            if idx != -1:
                return idx

        return _fallback_single()
    else:
        # Predicate search
        if callable(search):
            indexes = [i for i in range(start, end) if search(seq[i])]
        elif isinstance(search, non_atom_types):
            indexes = [i for i in range(start, end) if seq[i] in search]
        else:
            indexes = [i for i in range(start, end) if search == seq[i]]

        if indexes:
            return indexes
        return _fallback_list()


# endregion

# region Array Manipulation

def reverse_in_place(arr: Sequence, start: int = 0, end: int = None):
    """
    Reverses a portion of a sequence in-place.

    This function modifies the given sequence by reversing the elements between the specified indices.
    The reversal happens in-place, meaning no additional data structures are used.

    Args:
        arr (Sequence): The sequence to reverse. Must be mutable (e.g., a list).
        start (int): The starting index of the portion to reverse (inclusive). Defaults to 0.
        end (int): The ending index of the portion to reverse (inclusive). Defaults to the last index.

    Raises:
        ValueError: If `start` or `end` indices are out of bounds or invalid.

    Examples:
        Example 1: Reverse entire list
        >>> arr = [1, 2, 3, 4, 5]
        >>> reverse_in_place(arr)
        >>> arr
        [5, 4, 3, 2, 1]

        Example 2: Reverse a portion of the list
        >>> arr = [1, 2, 3, 4, 5]
        >>> reverse_in_place(arr, 1, 3)
        >>> arr
        [1, 4, 3, 2, 5]

        Example 3: Reverse a single element (no change)
        >>> arr = [1, 2, 3]
        >>> reverse_in_place(arr, 1, 1)
        >>> arr
        [1, 2, 3]

        Example 4: Reverse an empty list
        >>> arr = []
        >>> reverse_in_place(arr)
        []

        Example 5: Handle out-of-bound indices
        >>> arr = [1, 2, 3, 4, 5]
        >>> reverse_in_place(arr, 0, len(arr) - 1)
        >>> arr
        [5, 4, 3, 2, 1]

    Notes:
        - The input sequence `arr` must be mutable (e.g., lists). Immutable sequences like tuples will raise an error.
        - The indices must be valid; otherwise, the function will not perform any operation.
        - Time Complexity: O(n), where n is the number of elements to reverse.
        - Space Complexity: O(1), as the operation is performed in-place.
    """
    if not arr:
        return arr

    if end is None:
        end = len(arr) - 1  # Default to the last index (inclusive)
    if start < 0 or end >= len(arr) or start > end:
        raise ValueError("Invalid indices: start and end must be within bounds and start <= end.")

    while start < end:
        arr[start], arr[end] = arr[end], arr[start]
        start += 1
        end -= 1


def append_(
        item: Any,
        arr: Any = None,
        non_atom_types: tuple = (list, tuple),
        always_consider_iterator_as_non_atom: bool = True
) -> List:
    """
    Appends or extends an item to a collection, intelligently handling various input types.

    This utility function handles the common pattern of building lists incrementally. It smartly
    determines whether to extend (unpack elements) or append (add as single item) based on atomicity,
    and whether the collection supports in-place extension.

    Behavior based on `arr` type:
    - **arr is None**: Creates and returns a new list from `item`'s elements
    - **arr has callable `extend` method** (e.g., list): Extends `arr` in-place with `item`'s
      elements and returns the same `arr` object
    - **arr lacks `extend`** (e.g., tuple, str, int): Treats `arr` as atomic, creates new list
      `[arr, *item_elements]`

    The `item` is processed by `iter_()` from iter_helper to determine atomicity:
    - **Non-atomic items** (types in `non_atom_types`): Elements are unpacked and added individually
    - **Atomic items** (other types): Added as a single element

    Args:
        item (Any): The item to append/extend. Can be atomic (int, str) or non-atomic (list, tuple).
        arr (Any, optional): The collection to append to. Typically a List, but accepts any type.
            Defaults to None.
        non_atom_types (tuple, optional): Types whose elements should be unpacked when extending.
            Defaults to (list, tuple).
        always_consider_iterator_as_non_atom (bool, optional): If True, any Iterator/Iterable
            is treated as non-atomic and its elements are unpacked. Defaults to True.

    Returns:
        List: A list containing the result.
            - If `arr` is None: new list from `item`'s elements
            - If `arr` has `extend`: same `arr` object (mutated in-place)
            - If `arr` lacks `extend`: new list `[arr, *item_elements]`

    Examples:
        # Append atomic item to None (create new list)
        >>> append_(5, None)
        [5]

        # Append atomic item to existing list
        >>> my_list = [1, 2, 3]
        >>> result = append_(4, my_list)
        >>> result
        [1, 2, 3, 4]
        >>> my_list is result
        True

        # Extend with non-atomic item (list)
        >>> my_list = [1, 2, 3]
        >>> append_([4, 5], my_list)
        [1, 2, 3, 4, 5]

        # Extend with tuple (non-atomic by default)
        >>> my_list = [1, 2, 3]
        >>> append_((4, 5, 6), my_list)
        [1, 2, 3, 4, 5, 6]

        # Append string as atomic (not in non_atom_types by default)
        >>> append_('hello', [1, 2])
        [1, 2, 'hello']

        # Using default parameter (arr=None)
        >>> append_('hello')
        ['hello']

        # Chain multiple appends starting from None
        >>> result = append_(1, None)
        >>> result = append_(2, result)
        >>> result = append_(3, result)
        >>> result
        [1, 2, 3]

        # Mixed atomic and non-atomic chaining
        >>> result = append_(1, None)
        >>> result = append_([2, 3], result)
        >>> result = append_(4, result)
        >>> result
        [1, 2, 3, 4]

        # Control non-atomic types - treat list as atomic
        >>> append_([1, 2], None, non_atom_types=())
        [[1, 2]]

        # Control non-atomic types - treat list as non-atomic
        >>> append_([1, 2], None, non_atom_types=(list,))
        [1, 2]

        # Edge case: arr is tuple (no extend) - treated as atomic
        >>> append_(4, (1, 2, 3))
        [(1, 2, 3), 4]

        # Edge case: arr is string (no extend) - treated as atomic
        >>> append_([2, 3], 'hello')
        ['hello', 2, 3]

        # Edge case: arr is int - treated as atomic
        >>> append_(4, 5)
        [5, 4]

    Notes:
        - **In-place mutation**: If `arr` has a callable `extend` method (like list), it is
          mutated in-place and the same object is returned.
        - **New list creation**: If `arr` is None or lacks `extend`, a new list is created.
        - **Atomicity of `item`**: Determined by `iter_()` from iter_helper based on `non_atom_types`.
          - Non-atomic items (list, tuple by default): elements are unpacked
          - Atomic items (str, int, etc.): added as single element
        - **Atomicity of `arr`**: If `arr` lacks `extend`, it's treated as atomic and becomes
          the first element of the returned list.
        - **Strings**: Treated as atomic by default (not in `non_atom_types`), so `append_('x', ['a'])`
          gives `['a', 'x']`, not `['a', ...'x']`.
        - **Consistency**: Uses `iter_()` from iter_helper for atomicity handling, ensuring
          consistent behavior across the codebase.
        - **Time Complexity**: O(1) for atomic `item`, O(n) for non-atomic `item` where n is length.
        - **Space Complexity**: O(1) when extending existing list, O(n) when creating new list.
    """
    from python_utils.common_utils.iter_helper import iter_
    it = iter_(
        item,
        non_atom_types=non_atom_types,
        iter_none=False,
        always_consider_iterator_as_non_atom=always_consider_iterator_as_non_atom
    )
    if arr is None:
        return list(it)

    if hasattr(arr, 'extend') and callable(arr.extend):
        arr.extend(it)
        return arr
    else:
        return [arr, *it]



def dedup_sequence(arr: Sequence) -> list:
    """
    Removes duplicate elements from a list while maintaining the original order.

    Args:
        arr (Sequence): A list of elements from which duplicates are to be removed.

    Returns:
        list: A list with duplicates removed, keeping only the first occurrence of each element.

    Examples:
        >>> dedup_sequence([1, 2, 2, 3, 4, 4, 5])
        [1, 2, 3, 4, 5]
        >>> dedup_sequence(['a', 'b', 'a', 'c', 'b'])
        ['a', 'b', 'c']
        >>> dedup_sequence([1, 2, 3])
        [1, 2, 3]
    """
    seen = set()
    result = []
    for item in arr:
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result


def extend_to_size_by_last_element(_list: List, size: int):
    """
    Extends a list to a specified size by repeating the last element, if needed.

    Args:
        _list (list): The original list to extend.
        size (int): The desired size of the list.

    Returns:
        list: The extended list. If the original list is smaller than the desired size,
              it repeats the last element to extend it. If it's already the required size,
              the original list is returned unchanged.

    Raises:
        IndexError: If the input list is empty and cannot be extended.

    Examples:
        >>> extend_to_size_by_last_element([1, 2, 3], 5)
        [1, 2, 3, 3, 3]
        >>> extend_to_size_by_last_element(['a'], 3)
        ['a', 'a', 'a']
        >>> extend_to_size_by_last_element([1, 2], 2)
        [1, 2]
        >>> extend_to_size_by_last_element([], 3)
        Traceback (most recent call last):
            ...
        IndexError: list index out of range
    """
    list_len = len(_list)
    if list_len < size:
        _list = _list + ([_list[-1]] * (size - list_len))
    return _list


# endregion

# region Array Query and Comparison

def unpack_single_value(arr: Sequence):
    """Unpacks a single-element array or returns the array unchanged.

    Takes a list or tuple and returns the single element if the container has
    exactly one item. Returns None for empty or None containers, and returns
    the original container for multi-element containers.

    Args:
        arr (Union[List, Tuple]): The list or tuple to unpack. Can be None.

    Returns:
        Any: The single element if arr has length 1, None if arr is None or empty,
        or the original arr if it has multiple elements.

    Examples:
        >>> unpack_single_value([42])
        42
        >>> unpack_single_value(('hello',))
        'hello'
        >>> unpack_single_value([1, 2, 3])
        [1, 2, 3]
        >>> unpack_single_value([])
        >>> unpack_single_value(None)
        >>> unpack_single_value(['single'])
        'single'
    """
    if arr is None or len(arr) == 0:
        return None
    elif len(arr) == 1:
        return arr[0]
    else:
        return arr


def all_equal(arr: Union[List, Tuple], value=None):
    """
    Checks if all elements of a list or a tuple are equal, or equal to a provided value.

    If the input is empty, the function returns True.

    Args:
        arr: The list or tuple to be checked.
        value: An optional value to which all elements of the list or tuple should be compared.

    Returns:
        True if all elements in the list or tuple are equal, or equal to the provided value,
        False otherwise.

    Example:
        >>> all_equal([1, 1, 1, 1])
        True

        >>> all_equal((1, 2, 3, 4))
        False

        >>> all_equal([])
        True

        >>> all_equal([2, 2, 2], 2)
        True

        >>> all_equal((1, 2, 3, 4), 2)
        False
    """
    if not arr:
        return True
    if value is None:
        if len(arr) == 1:
            return True
        else:
            return all(arr[0] == arr[i] for i in range(1, len(arr)))
    else:
        if len(arr) == 1:
            return arr[0] == value
        else:
            return all(arr[i] == value for i in range(len(arr)))


# endregion

# region Array Splitting and Partitioning

def split_half(arr: Union[List, Tuple]):
    """
    Splits a list or a tuple into two halves.

    If the input has an odd number of elements, the extra element is added to the second half.

    Args:
        arr: The list or tuple to be split.

    Returns:
        A tuple of two lists or tuples, each representing a half of the input.

    Example:
        >>> split_half([1, 2, 3, 4, 5])
        ([1, 2], [3, 4, 5])

        >>> split_half((1, 2, 3, 4, 5, 6))
        ((1, 2, 3), (4, 5, 6))
    """
    split_pos = len(arr) // 2
    return arr[:split_pos], arr[split_pos:]


def first_half(arr: Union[List, Tuple]):
    """
    Returns the first half of a list or a tuple.

    If the input has an odd number of elements, the extra element is not included in the returned half.

    Args:
        arr: The list or tuple to be halved.

    Returns:
        A list or tuple representing the first half of the input.

    Example:
        >>> first_half([1, 2, 3, 4, 5])
        [1, 2]

        >>> first_half((1, 2, 3, 4, 5, 6))
        (1, 2, 3)
    """
    return arr[:len(arr) // 2]


def second_half(arr: Union[List, Tuple]):
    """
    Returns the second half of a list or a tuple.

    If the input has an odd number of elements, the extra element is included in the returned half.

    Args:
        arr: The list or tuple to be halved.

    Returns:
        A list or tuple representing the second half of the input.

    Example:
        >>> second_half([1, 2, 3, 4, 5])
        [3, 4, 5]

        >>> second_half((1, 2, 3, 4, 5, 6))
        (4, 5, 6)
    """
    return arr[(len(arr) // 2):]


def _iter_split_list(list_to_split: List, num_splits: int) -> Iterator[List]:
    """
    Returns an iterator that iterates through even splits of the provided `list_to_split`.

    If the size of `list_to_split` is not dividable ty `num_splits`,
    then the last split will be larger or smaller than others in size.

    If the size of the `list_to_split` is smaller than or equal to `num_splits`,
        then singleton lists will be yielded and the total number of yielded splits
        is the same as the length of the `list_to_split`.

    Args:
        list_to_split: the list to split.
        num_splits: the number of splits to yield;

    Returns: an iterator that iterates through splits of the provided list; all splits are of
        the same size, except for the last split might be larger or smaller than others in size
        if the size of `list_to_split` is not dividable ty `num_splits`.

    Examples:
        >>> list(_iter_split_list([1, 2, 3, 4, 5], 1))
        [[1, 2, 3, 4, 5]]
        >>> list(_iter_split_list([1, 2, 3, 4, 5], 2))
        [[1, 2], [3, 4, 5]]
        >>> list(_iter_split_list([1, 2, 3, 4, 5], 3))
        [[1, 2], [3, 4], [5]]
        >>> list(_iter_split_list([1, 2, 3, 4, 5], 6))
        [[1], [2], [3], [4], [5]]
        >>> list(_iter_split_list([1, 2, 3, 4, 5], 7))
        [[1], [2], [3], [4], [5]]
    """
    if not (isinstance(num_splits, int) and num_splits >= 1):
        raise ValueError(f"'num_splits' can only be a positive integer; got {num_splits}")

    list_len = len(list_to_split)
    if list_len <= num_splits:
        for item in list_to_split:
            yield [item]
    else:
        list_len = len(list_to_split)
        chunk_size = int(list_len / num_splits)
        remainder = int(list_len - chunk_size * num_splits)

        if remainder > 1:
            begin, end = 0, chunk_size + 1
            for i in range(0, remainder - 1):
                yield list_to_split[begin:end]
                begin, end = end, end + chunk_size + 1
        else:
            begin, end = 0, chunk_size

        for i in range(remainder - 1, num_splits - 1):
            yield list_to_split[begin:end]
            begin, end = end, end + chunk_size
        if begin < list_len:
            yield list_to_split[begin:]


def _iter_weighted_split_list(list_to_split: List, weights: List[float]) -> Iterator[List]:
    """
    Returns an iterator that iterates through splits of the provided `list_to_split` based on specified weights.

    The weights determine the proportion of each split relative to the total sum of the weights.

    Args:
        list_to_split: The list to split.
        weights: A list of weights determining the proportion of each split.

    Returns:
        An iterator that iterates through splits of the provided list based on weights.

    Examples:
        >>> list(_iter_weighted_split_list([1, 2, 3, 4, 5], [1, 1, 1]))
        [[1], [2, 3], [4, 5]]

        >>> list(_iter_weighted_split_list([1, 2, 3, 4, 5], [1, 2, 1]))
        [[1], [2, 3], [4, 5]]

        >>> list(_iter_weighted_split_list([1, 2, 3, 4, 5], [1, 2]))
        [[1], [2, 3, 4, 5]]

        >>> list(_iter_weighted_split_list([1, 2, 3, 4, 5], [3, 1]))
        [[1, 2, 3], [4, 5]]
    """
    list_len = len(list_to_split)
    split_points = distribute_by_weights(list_len, weights, incremental=True)

    start = 0
    for end in split_points:
        end = int(end)
        yield list_to_split[start:end]
        start = end


def iter_split_list(
        list_to_split: List,
        num_splits_or_weights: Union[int, List[Union[float, int]]]
) -> Iterator[List]:
    """
    Returns an iterator that iterates through splits of the provided `list_to_split`.

    If an integer is provided, the list will be split into that number of even splits.
    If a list of weights is provided, the list will be split based on those weights.

    Args:
        list_to_split: The list to split.
        num_splits_or_weights: Either an integer specifying the number of splits or a list of weights.

    Returns:
        An iterator that iterates through splits of the provided list.

    Examples:
        >>> list(iter_split_list([1, 2, 3, 4, 5], 2))
        [[1, 2], [3, 4, 5]]
        >>> list(iter_split_list([1, 2, 3, 4, 5], [1, 1, 2]))
        [[1], [2], [3, 4, 5]]
    """
    if isinstance(num_splits_or_weights, int):
        return _iter_split_list(list_to_split, num_splits_or_weights)
    elif isinstance(num_splits_or_weights, List):
        return _iter_weighted_split_list(list_to_split, num_splits_or_weights)
    else:
        raise ValueError("num_splits_or_weights must be either an int or a list of ints/floats")


def split_list(
        list_to_split: List,
        num_splits_or_weights: Union[int, List[Union[float, int]]]
) -> List[List]:
    """
    See :func:`iter_split_list`.
    """
    return list(iter_split_list(list_to_split, num_splits_or_weights))


def resolve_partial(
        num_parts: int,
        partial: int,
        *items: Union[Sequence, int, float],
        master_item: Union[Sequence, int, float] = None
) -> Tuple[Union[Sequence, int, float], ...]:
    """
    Splits multiple sequences or numbers into parts with optional proportional control using a master item.

    This function has two modes of operation:
    1. Without master_item: Each item is split independently into num_parts
    2. With master_item: All items are split proportionally based on master_item's divisions

    Args:
        num_parts (int): Number of parts to split items into
        partial (int): Which part to return (0-based index)
        *items: Sequences or numbers to be split. Can be:
            - Lists/Tuples: Split by indexing
            - Integers: Split into smaller integers
            - Floats: Split into smaller floats
        master_item: Optional controlling item that determines split proportions for all other items.
            The method split the master item first, then other items are split based on the proportions of the master item.
            - If int/float: Used directly to calculate proportional ranges
            - If sequence: Its length is used to calculate proportional ranges
            When provided, returned tuple includes split master_item as first element

    Returns:
        Tuple containing split results:
        - Without master_item: (split_item1, split_item2, ...)
        - With master_item: (split_master, split_item1, split_item2, ...)

    Example:
        # Simple number splitting:
        >>> resolve_partial(3, 2, 9, 15.0)  # Split numbers into thirds
        (3, 5.0)
        >>> resolve_partial(4, 3, 16, 20.0)
        (4, 5.0)

        # Independent splitting (no master_item):
        >>> resolve_partial(3, 1, [1, 2, 3, 4, 5], ['a', 'b', 'c', 'd', 'e'])
        ([3, 4], ['c', 'd'])
        >>> resolve_partial(2, 0, [1, 2, 3, 4, 5, 6], ['a', 'b', 'c', 'd', 'e', 'f'])
        ([1, 2, 3], ['a', 'b', 'c'])

        # Proportional splitting with integer master_item:
        >>> resolve_partial(3, 2, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], 100, master_item=10)
        (4, [6, 7, 8, 9], 40)

        # Proportional splitting with sequence master_item:
        >>> resolve_partial(3, 2, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], 100, master_item=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
        ([6, 7, 8, 9], [6, 7, 8, 9], 40)
    """
    if num_parts > 1:
        if master_item is not None:
            out_items = [None] * (len(items) + 1)
            if isinstance(master_item, int):
                _split, _range = split_int(master_item, num_parts, partial, return_range=True)
            elif isinstance(master_item, float):
                if int(master_item) == master_item:
                    _split, _range = split_int(int(master_item), num_parts, partial, return_range=True)
                else:
                    _split, _range = split_float(master_item, num_parts, partial, return_range=True)
            else:
                len_master_item = len(master_item)
                _split, _range = split_int(len_master_item, num_parts, partial, return_range=True)
                _split = master_item[int(_range[0] * len_master_item): int(_range[1] * len_master_item)]
            out_items[0] = _split
            for i in range(len(items)):
                item = items[i]
                if isinstance(item, int):
                    out_items[i + 1] = int(item * _range[1]) - int(item * _range[0])
                elif isinstance(item, float):
                    if int(item) == item:
                        item = int(item)
                        out_items[i + 1] = float(int(item * _range[1]) - int(item * _range[0]))
                    else:
                        out_items[i + 1] = float((item * _range[1]) - (item * _range[0]))
                else:
                    len_item = len(item)
                    out_items[i + 1] = item[int(_range[0] * len_item): int(_range[1] * len_item)]
        else:
            out_items = [None] * len(items)
            for i in range(len(items)):
                item = items[i]
                if isinstance(item, int):
                    out_items[i] = split_int(item, num_parts, partial)
                elif isinstance(item, float):
                    if int(item) == item:
                        out_items[i] = float(split_int(int(item), num_parts, partial))
                    else:
                        out_items[i] = split_float(item, num_parts, partial)
                else:
                    out_items[i] = split_list(item, num_parts)[partial]

        items = tuple(out_items)
        return items
    else:
        return master_item, *items


# endregion

# region Windowing Operations

def moving_window_convert(
        arr: Sequence,
        converter: Callable[[Sequence, Sequence], Any] = None,
        hist_window_size: int = 20,
        future_window_size: int = 10,
        pre_hist_window_size: int = None,
        step_size: int = 1,
        allows_partial_future_window: bool = False
) -> List:
    """
    Convert an input list into a list of tuples, where each tuple contains the historical window,
    future window, and optionally, the pre-historical window.

    A converter function ban be applied to operate on the windows.

    Args:
        arr: Input list of numeric values.
        converter: Optional function to apply on the historical, future, and pre-historical windows.
        hist_window_size: Size of the historical window.
        future_window_size: Size of the future window.
        pre_hist_window_size: Optional size of the pre-historical window.
        step_size: Step size for moving the window.
        allows_partial_future_window: If True, allows the last historical window to have a
            partial future window.

    Returns:
        A list of tuples containing historical and future windows, and optionally,
        pre-historical windows.

    Examples:
        >>> arr = list(range(1, 101))
        >>> result = moving_window_convert(arr, hist_window_size=10, future_window_size=5)
        >>> print(result[0])  # First historical-future window pair
        ([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], [11, 12, 13, 14, 15])
        >>> print(result[-1])  # Last historical-future window pair
        ([86, 87, 88, 89, 90, 91, 92, 93, 94, 95], [96, 97, 98, 99, 100])
        >>> result_with_pre_hist = moving_window_convert(
        ...    arr,
        ...    hist_window_size=10,
        ...    future_window_size=5,
        ...    pre_hist_window_size=5
        ... )
        >>> print(result_with_pre_hist[0])  # First historical-future-pre-historical window tuple
        ([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], [11, 12, 13, 14, 15], [])
        >>> print(result_with_pre_hist[-1])  # Last historical-future-pre-historical window tuple
        ([86, 87, 88, 89, 90, 91, 92, 93, 94, 95], [96, 97, 98, 99, 100], [81, 82, 83, 84, 85])
        >>> result_with_pre_hist = moving_window_convert(
        ...    arr,
        ...    hist_window_size=10,
        ...    future_window_size=5,
        ...    pre_hist_window_size=5,
        ...    allows_partial_future_window=True
        ... )
        >>> print(result_with_pre_hist[-1])  # Last historical-future-pre-historical window tuple
        ([90, 91, 92, 93, 94, 95, 96, 97, 98, 99], [100], [85, 86, 87, 88, 89])
        >>> arr = list(range(1, 22))
        >>> result_with_pre_hist = moving_window_convert(
        ...    arr,
        ...    hist_window_size=20,
        ...    future_window_size=10,
        ...    pre_hist_window_size=10,
        ...    allows_partial_future_window=True
        ... )
        >>> print(result_with_pre_hist)
        [([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20], [21], [])]
        >>> result_with_pre_hist = moving_window_convert(
        ...    arr, hist_window_size=20,
        ...    future_window_size=10,
        ...    pre_hist_window_size=10,
        ...    allows_partial_future_window=False
        ... )
        >>> print(result_with_pre_hist)
        []
    """
    out = []
    arr_len = len(arr)
    total_window_size = hist_window_size + future_window_size

    end_i = (
        (arr_len - hist_window_size)
        if allows_partial_future_window else
        (arr_len - total_window_size + 1)
    )

    if pre_hist_window_size:
        for i in range(0, end_i, step_size):
            i0 = max(0, i - pre_hist_window_size)
            i2 = i + hist_window_size
            i3 = i + total_window_size
            window = (arr[i:i2], arr[i2:i3], arr[i0:i])
            if converter is None:
                out.append(window)
            else:
                out.append(converter(*window))
    else:
        for i in range(0, end_i, step_size):
            i2 = i + hist_window_size
            i3 = i + total_window_size
            window = (arr[i:i2], arr[i2:i3])
            if converter is None:
                out.append(window)
            else:
                out.append(converter(*window))
    return out


# endregion

# region Cartesian Product

def iter_cartesian_product(
        arr: Sequence[Any],
        arr_sort_func: Callable = None,
        bidirection_product: bool = False,
        include_self_product: bool = False
) -> Iterator[Tuple[Any, Any]]:
    """
    Computes the Cartesian product of elements in a sequence and returns an iterator.

    Args:
        arr: The input sequence.
        arr_sort_func: A function to sort the
            input sequence before computing the Cartesian product. Defaults to None.
        bidirection_product: If True, include both (a, b) and (b, a) in the result.
            Defaults to False.
        include_self_product: If True, include pairs with identical elements (a, a)
            in the result. Defaults to False.

    Returns: An iterator for the Cartesian product of the input sequence's elements.

    Examples:
        >>> input_arr = ["a", "b", "c"]
        >>> cart_product = iter_cartesian_product(input_arr, bidirection_product=False,
        ...                                      include_self_product=False)
        >>> list(cart_product)
        [('a', 'b'), ('a', 'c'), ('b', 'c')]

        >>> input_arr = ["a", "a", "b", "c"]
        >>> cart_product = iter_cartesian_product(input_arr, bidirection_product=False,
        ...                                      include_self_product=False)
        >>> list(cart_product)
        [('a', 'a'), ('a', 'b'), ('a', 'c'), ('a', 'b'), ('a', 'c'), ('b', 'c')]

        >>> input_arr = [1, 2, 3]
        >>> cart_product = iter_cartesian_product(input_arr, bidirection_product=True,
        ...                                      include_self_product=True)
        >>> list(cart_product)
        [(1, 1), (1, 2), (1, 3), (2, 1), (2, 2), (2, 3), (3, 1), (3, 2), (3, 3)]
    """
    if arr_sort_func is None:
        arr_sort_func = sorted
    arr = arr_sort_func(arr)

    if include_self_product:
        if bidirection_product:
            return ((arr[i], arr[j]) for i in range(len(arr)) for j in range(len(arr)))
        else:
            return ((arr[i], arr[j]) for i in range(len(arr)) for j in range(i, len(arr)))
    else:
        if bidirection_product:
            return ((arr[i], arr[j]) for i in range(len(arr)) for j in range(len(arr)) if i != j)
        else:
            return ((arr[i], arr[j]) for i in range(len(arr)) for j in range(i + 1, len(arr)))


def get_cartesian_product(
        arr: Sequence[Any],
        arr_sort_func: Callable = None,
        bidirection_product: bool = False,
        include_self_product: bool = False
) -> List[Tuple[Any, Any]]:
    """
    See `iter_cartesian_product`.
    """
    return list(iter_cartesian_product(
        arr,
        arr_sort_func=arr_sort_func,
        bidirection_product=bidirection_product,
        include_self_product=include_self_product
    ))


# endregion

# region CSV I/O

def save_to_csv(
        data: Sequence[Sequence],
        filename: str,
        delimiter: str = ',',
        header: Optional[List[str]] = None,
        **kwargs
) -> None:
    """Save data to a CSV file.

    Args:
        data (Sequence[Sequence]): The data to be written to the CSV file.
        filename (str): The filename of the CSV file.
        delimiter (str, optional): The character used to separate fields in the CSV file.
            Defaults to ','.
        header (Optional[List[str]], optional): The headers for the CSV file. Default is None.
        **kwargs: Additional keyword arguments to pass to the csv.writer.

    Returns:
        None

    Examples:
        >>> import tempfile
        >>> import os
        >>> import pathlib

        Test with default delimiter
        >>> data = [['John', 30], ['Alice', 25]]
        >>> headers = ['Name', 'Age']
        >>> with tempfile.TemporaryDirectory() as tmp_dir: # doctest: +SKIP
        ...     tmp_file = os.path.join(tmp_dir, 'test.csv')
        ...     save_to_csv(data, tmp_file, header=headers)
        ...     with open(tmp_file, 'r') as file:
        ...         content = file.read()
        ...     expected_content = "Name,Age\\nJohn,30\\nAlice,25\\n"
        ...     assert content == expected_content

        Test with semicolon delimiter
        >>> data = [['John', 30], ['Alice', 25]]
        >>> with tempfile.TemporaryDirectory() as tmp_dir: # doctest: +SKIP
        ...     tmp_file = os.path.join(tmp_dir, 'test.csv')
        ...     save_to_csv(data, tmp_file, delimiter=';', header=headers)
        ...     with open(tmp_file, 'r') as file:
        ...         content = file.read()
        ...     expected_content = "Name;Age\\nJohn;30\\nAlice;25\\n"
        ...     assert content == expected_content

        Test nested directory creation
        >>> data = [['John', 30], ['Alice', 25]]
        >>> with tempfile.TemporaryDirectory() as tmp_dir: # doctest: +SKIP
        ...     nested_dir = os.path.join(tmp_dir, 'nested', 'dirs')
        ...     tmp_file = os.path.join(nested_dir, 'test.csv')
        ...     save_to_csv(data, tmp_file, header=headers)
        ...     assert os.path.exists(tmp_file)
        ...     with open(tmp_file, 'r') as file:
        ...         content = file.read()
        ...     expected_content = "Name,Age\\nJohn,30\\nAlice,25\\n"
        ...     assert content == expected_content
    """
    import csv
    from os import path
    from python_utils.path_utils.common import ensure_dir_existence
    ensure_dir_existence(path.dirname(filename))
    with open(filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile, delimiter=delimiter, **kwargs)
        if header:
            writer.writerow(header)
        writer.writerows(data)

# endregion
