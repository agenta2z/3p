from collections import defaultdict
from typing import Iterable

from python_utils.string_utils import join_


def group_by_anagram(iterables: Iterable[Iterable]):
    """
    Groups iterables (e.g., strings, lists of characters) into sublists where each sublist
    contains elements that are anagrams of each other.

    An anagram is defined as two or more items having the same elements in any order.
    For example, ["act", "cat"] are anagrams because they share the same characters.

    Args:
        iterables (Iterable[Iterable]): An iterable of iterables (e.g., a list of strings or a list of lists of characters).

    Returns:
        Tuple[List[Iterable]]: A tuple containing groups of anagrams as lists.

    Notes:
        - **Time Complexity**: \(O(n \cdot k \log k)\), where \(n\) is the number of iterables, and \(k\) is the average length of each iterable.
          Sorting each iterable dominates the runtime.
        - **Space Complexity**: \(O(n \cdot k)\), where \(n\) is the number of iterables, and \(k\) is the average length of each iterable.
          The space is used for the dictionary keys, grouped anagrams, and sorting operations.

    Examples:
        >>> group_by_anagram(["act", "cat", "stop", "tops", "pots", "hat"])
        (['act', 'cat'], ['stop', 'tops', 'pots'], ['hat'])

        >>> group_by_anagram(["listen", "silent", "enlist", "inlets", "hello"])
        (['listen', 'silent', 'enlist', 'inlets'], ['hello'])

        >>> group_by_anagram([""])
        ([''],)

        >>> group_by_anagram(["a", "b", "c", "a"])
        (['a', 'a'], ['b'], ['c'])

        >>> group_by_anagram(["123", "231", "312", "234"])
        (['123', '231', '312'], ['234'])
    """
    anagram_map = defaultdict(list)

    for iterable in iterables:
        sorted_iterable = sorted(iterable)
        sorted_iterable_str = join_(*sorted_iterable, sep='\n')
        anagram_map[sorted_iterable_str].append(iterable)

    return tuple(anagram_map.values())

