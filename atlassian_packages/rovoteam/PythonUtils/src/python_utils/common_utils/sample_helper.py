import random
from collections import Counter
from typing import Union, Dict, List, Optional, Iterable, Sequence, Set


def check_and_decrement_count(elem, counts: Union[Counter, Dict]) -> bool:
    """
    Checks if the given element exists in the Counter and has a non-zero count. If so,
    decrements the count by one and returns True. Otherwise, returns False.

    Args:
        elem: The element to check in the Counter.
        counts (Counter): A Counter object containing element counts.

    Returns:
        bool: True if the element exists with a non-zero count and the count was decremented,
              False otherwise.

    Examples:
        >>> counts = Counter(['apple', 'banana', 'apple', 'cherry'])
        >>> check_and_decrement_count('apple', counts)
        True
        >>> counts['apple']
        1

        >>> check_and_decrement_count('banana', counts)
        True
        >>> counts['banana']
        0

        >>> check_and_decrement_count('grape', counts)
        False
    """
    if elem in counts and counts[elem] > 0:
        counts[elem] -= 1
        return True
    return False


def filter_elements_by_counts(input_list: List, counts: Union[Counter, Dict], update_counts: bool = False, return_indexes:bool = False) -> List:
    """
    Filters elements from the input list based on their counts in a provided Counter or Dictionary.
    Elements are removed from the input list if their count in the Counter/Dictionary is non-zero.
    Each occurrence of an element in the input list decrements its count in the Counter/Dictionary.

    Args:
        input_list: The list of elements to be filtered.
        counts: A Counter or Dictionary containing element counts.
        update_counts: True to update the `counts` in place.
            If an element existing in the `counts` is removed from `input_list`,
            then its count is reduced by 1 in place.
        return_indexes: True to return indexes of the elements passing the filter.

    Returns:
        A list of elements from the input list with elements removed according to the provided counts.

    Examples:
        >>> counts = Counter(['apple', 'banana', 'apple'])
        >>> input_list = ['apple', 'banana', 'cherry', 'apple']
        >>> filter_elements_by_counts(input_list, counts)
        ['cherry']

        >>> counts = {'apple': 1, 'banana': 0, 'cherry': 2}
        >>> input_list = ['apple', 'banana', 'cherry', 'apple', 'cherry']
        >>> filter_elements_by_counts(input_list, counts)
        ['banana', 'apple']

    """
    if not update_counts:
        counts = counts.copy()

    if return_indexes:
        return [i for i, elem in enumerate(input_list) if not check_and_decrement_count(elem, counts)]
    else:
        return [elem for elem in input_list if not check_and_decrement_count(elem, counts)]


def ordered_sample(input_list: List, sample_size: Optional[int], must_keep: Optional[Union[Sequence, Set]] = None) -> List:
    """
    Samples elements from a list, keeping the original order, and ensuring certain specified elements are included.
    If `must_keep` is not empty, these elements are included first, and additional elements are randomly sampled from the remaining list.

    Args:
        input_list: The list from which to sample.
        sample_size: The number of elements to sample.
        must_keep (List, optional): Elements that must be included in the sample. Defaults to None.

    Returns:
        A list containing the sampled elements, preserving the original order.

    Raises:
        ValueError: If the sample size is larger than the list size.

    Examples:
        >>> input_list = ['apple', 'banana', 'cherry', 'date', 'elderberry', 'fig']
        >>> ordered_sample(input_list, 3, must_keep=['banana', 'fig'])
        ['apple', 'banana', 'fig']

        >>> ordered_sample(input_list, 5)
        ['apple', 'banana', 'cherry', 'date', 'elderberry']
    """

    if not sample_size:
        if must_keep:
            sample_size = len(must_keep)
        else:
            return []
        additional_sample_size = 0
    else:
        if sample_size > len(input_list):
            raise ValueError("Sample size cannot be larger than the list size.")
        additional_sample_size = sample_size - len(must_keep)

    if must_keep:
        must_keep_counts = Counter(must_keep)
        out = []
        if additional_sample_size:
            remaining_list_indexes = filter_elements_by_counts(input_list, must_keep_counts, update_counts=False, return_indexes=True)
            additional_samples_indexes = set(random.sample(remaining_list_indexes, additional_sample_size))
            for i, elem in enumerate(input_list):
                if check_and_decrement_count(elem, counts=must_keep_counts) or i in additional_samples_indexes:
                    out.append(elem)
                if len(out) == sample_size:
                    break
        else:
            for i, elem in enumerate(input_list):
                if check_and_decrement_count(elem, counts=must_keep_counts):
                    out.append(elem)
                if len(out) == sample_size:
                    break
        return out
    else:
        return [input_list[i] for i in sorted(random.sample(range(len(input_list)), sample_size))]

