from typing import Iterable, Set


def is_subset(x: Iterable, y: Iterable):
    return set(x).issubset(set(y))


def remove_duplication(arr: Iterable):
    if isinstance(arr, set):
        return arr
    seen = set()
    out = filter(lambda x: x not in seen and not seen.add(x), arr)
    if isinstance(arr, tuple):
        return tuple(out)
    else:
        return list(out)


def get_items_with_multiple_occurrences(arr: Iterable) -> set:
    visited = set()
    duplicates = set()
    for x in arr:
        if x in visited:
            duplicates.add(x)
        else:
            visited.add(x)
    return duplicates


def compare_sets(
        set1: Set,
        set2: Set,
        allows_add: bool = False,
        allows_drop: bool = False
) -> bool:
    """
    Compares two sets `set1` and `set2`.

    When `allows_add` and `allows_drop` are both set False,
    then this function returns True if the two sets are different,

    When `allows_add` is set True,
    then this function returns True if the two sets are different
        and `set1` is not a subset of `set2`.

    When `allows_drop` is set True,
    then this function returns True if the two sets are different
        and `set2` is not a subset of `set1`.

    When both `allows_add` and `allows_drop` are set True,
    then this function returns True if the two sets are different
        and `set1`/`set2` is not a subset of the other.

    Args:
        set1: The first set to compare.
        set2: The second set to compare.
        allows_add: Whether to allow addition of elements.
        allows_drop: Whether to allow drop of elements.

    Returns: True if the two sets are different based on the specified conditions, False otherwise.

    Examples:
        # Example 1: compare two sets that are different
        >>> set1 = {1, 2, 3}
        >>> set2 = {2, 3, 4}
        >>> compare_sets(set1, set2)
        True

        # Example 2: compare two sets that are different
        >>> set1 = {1, 2, 3}
        >>> set2 = {2, 3, 1}
        >>> compare_sets(set1, set2)
        False

        # Example 3: compare two sets that are different but `set1` is a subset of `set2`
        >>> set1 = {1, 2}
        >>> set2 = {1, 2, 3, 4}
        >>> compare_sets(set1, set2)
        True
        >>> compare_sets(set1, set2, allows_add=True)
        False

        # Example 4: compare two sets that are different but `set2` is a subset of `set1`
        >>> set1 = {1, 2, 3, 4}
        >>> set2 = {1, 2}
        >>> compare_sets(set1, set2)
        True
        >>> compare_sets(set1, set2, allows_drop=True)
        False

    """
    len_set1, len_set2 = len(set1), len(set2)
    if len_set1 == 0 and len_set2 == 0:
        return False

    if not allows_add and not allows_drop:
        # if we do not allow element addition or drop, then directly compares the two sets
        return set1 != set2
    else:
        overlap = set1 & set2
        overlap_same_as_set1 = (len(overlap) == len_set1)
        overlap_same_as_set2 = (len(overlap) == len_set2)
        return not (  # one set must be a subset of the other
                (overlap_same_as_set1 or overlap_same_as_set2) and
                # either we allow addition, or there is no addition
                (allows_add or not (overlap_same_as_set1 and len_set2 > len_set1)) and
                # either we allow drop, or there is no drop
                (allows_drop or not (overlap_same_as_set2 and len_set2 < len_set1))
        )


def set_one_contains_the_other(set1: Set, set2: Set) -> bool:
    """
    Returns True if `set1` is a proper subset or superset of `set2`.
    """
    overlap = set1 & set2
    return (
            (len(overlap) == len(set2) and len(set2) < len(set1)) or
            (len(overlap) == len(set1) and len(set2) > len(set1))
    )
