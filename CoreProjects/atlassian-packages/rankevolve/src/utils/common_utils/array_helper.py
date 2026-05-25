"""Array helper utilities — extracted functions."""

from typing import Any, Callable, Iterator, List, Optional, Sequence, Tuple, Union

from rankevolve.src.utils.common_objects.search_fallback_options import SearchFallbackOptions
from rankevolve.src.utils.common_utils.misc import distribute_by_weights


def index_(
    seq: Sequence,
    item: Any,
    start: int = 0,
    end: int = None,
    key: Callable = None,
    default: int = -1,
) -> int:
    """
    Find index of item in sequence.

    Args:
        seq: Sequence to search.
        item: Item to find.
        start: Start index.
        end: End index.
        key: Function to extract comparison key.
        default: Default if not found.

    Returns:
        Index of item or default.
    """
    if end is None:
        end = len(seq)

    if key is not None:
        for i in range(start, end):
            if key(seq[i]) == item:
                return i
    else:
        try:
            return seq.index(item, start, end)
        except ValueError:
            for i in range(start, end):
                if seq[i] == item:
                    return i

    return default


def index__(
    seq: Sequence,
    item: Any,
    start: int = 0,
    end: int = None,
    key: Callable = None,
    default: int = -1,
    fallback: SearchFallbackOptions = SearchFallbackOptions.ReturnDefault,
) -> int:
    """
    Find index with fallback options.

    Args:
        seq: Sequence to search.
        item: Item to find.
        start: Start index.
        end: End index.
        key: Function to extract comparison key.
        default: Default if not found.
        fallback: How to handle not found.

    Returns:
        Index of item based on fallback option.
    """
    idx = index_(seq, item, start, end, key, default=-1)

    if idx != -1:
        return idx

    if fallback == SearchFallbackOptions.ReturnDefault:
        return default
    elif fallback == SearchFallbackOptions.RaiseError:
        raise ValueError(f"Item {item} not found in sequence")
    elif fallback == SearchFallbackOptions.ReturnFirst:
        return start if len(seq) > start else default
    elif fallback == SearchFallbackOptions.ReturnLast:
        end_idx = end if end is not None else len(seq)
        return end_idx - 1 if end_idx > start else default
    else:
        return default


def _iter_split_list(
    data: Sequence,
    num_splits: int = None,
    split_size: int = None,
) -> Iterator[List]:
    """
    Internal iterator for splitting a list.

    Args:
        data: Sequence to split.
        num_splits: Number of splits.
        split_size: Size of each split.

    Yields:
        List chunks.
    """
    n = len(data)

    if num_splits is not None:
        # Split into num_splits parts
        base_size = n // num_splits
        remainder = n % num_splits
        start = 0
        for i in range(num_splits):
            size = base_size + (1 if i < remainder else 0)
            if size > 0:
                yield list(data[start : start + size])
            start += size
    elif split_size is not None:
        # Split into chunks of split_size
        for i in range(0, n, split_size):
            yield list(data[i : i + split_size])
    else:
        yield list(data)


def _iter_weighted_split_list(
    data: Sequence,
    weights: List[float],
) -> Iterator[List]:
    """
    Internal iterator for weighted splitting.

    Args:
        data: Sequence to split.
        weights: Weights for each split.

    Yields:
        List chunks based on weights.
    """
    n = len(data)
    sizes = distribute_by_weights(n, weights)

    start = 0
    for size in sizes:
        if size > 0:
            yield list(data[start : start + size])
        start += size


def iter_split_list(
    data: Sequence,
    num_splits: int = None,
    split_size: int = None,
    weights: List[float] = None,
) -> Iterator[List]:
    """
    Iterate over splits of a sequence.

    Args:
        data: Sequence to split.
        num_splits: Number of splits.
        split_size: Size of each split.
        weights: Weights for each split.

    Yields:
        List chunks.
    """
    if weights is not None:
        yield from _iter_weighted_split_list(data, weights)
    else:
        yield from _iter_split_list(data, num_splits, split_size)


def split_list(
    data: Sequence,
    num_splits: int = None,
    split_size: int = None,
    weights: List[float] = None,
) -> List[List]:
    """
    Split a sequence into parts.

    Args:
        data: Sequence to split.
        num_splits: Number of splits.
        split_size: Size of each split.
        weights: Weights for each split.

    Returns:
        List of list chunks.

    Examples:
        >>> split_list([1, 2, 3, 4, 5], num_splits=2)
        [[1, 2, 3], [4, 5]]
        >>> split_list([1, 2, 3, 4, 5], split_size=2)
        [[1, 2], [3, 4], [5]]
    """
    return list(iter_split_list(data, num_splits, split_size, weights))
