"""Iterator helper utilities — extracted functions."""

from typing import (
    Any,
    Callable,
    Iterable,
    Iterator,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
)

from rankevolve.src.utils.common_utils.typing_helper import iterable__, sliceable


def _get_non_atom_types(non_atom_types=None, atom_types=(str,)):
    """
    Helper to determine non-atom types for iteration.

    Args:
        non_atom_types: Explicitly specified non-atom types.
        atom_types: Types to treat as atoms (non-iterable).

    Returns:
        Tuple of non-atom types, or None if none specified.
    """
    if non_atom_types is not None:
        return non_atom_types
    if atom_types is None:
        return None
    # Cannot easily invert atom_types to non_atom_types, return None
    return None


def iter_(
    obj: Any,
    atom_types: Tuple = (str,),
    non_atom_types: Tuple = None,
    unpack_single: bool = True,
) -> Iterator:
    """
    Iterate over an object, treating atom_types as non-iterable.

    Args:
        obj: Object to iterate over.
        atom_types: Types to treat as atoms (non-iterable).
        non_atom_types: Types to treat as non-atoms (iterable).
        unpack_single: If True, unpack single-element sequences.

    Yields:
        Elements from the object.

    Examples:
        >>> list(iter_('abc'))
        ['abc']
        >>> list(iter_(['a', 'b']))
        ['a', 'b']
        >>> list(iter_(123))
        [123]
    """
    _non_atom_types = _get_non_atom_types(non_atom_types, atom_types)

    if _non_atom_types is not None:
        if isinstance(obj, _non_atom_types):
            yield from obj
        else:
            yield obj
    elif atom_types is not None:
        if isinstance(obj, atom_types):
            yield obj
        elif isinstance(obj, (Iterable, Iterator, Sequence)):
            yield from obj
        else:
            yield obj
    else:
        # Both None - try to iterate
        try:
            yield from obj
        except TypeError:
            yield obj


def iter__(
    obj: Any,
    atom_types: Tuple = (str,),
    non_atom_types: Tuple = None,
) -> Iterator:
    """
    Iterate over an object, treating atom_types as non-iterable.
    Variant of iter_ that always wraps non-iterables.

    Args:
        obj: Object to iterate over.
        atom_types: Types to treat as atoms (non-iterable).
        non_atom_types: Types to treat as non-atoms (iterable).

    Yields:
        Elements from the object.

    Examples:
        >>> list(iter__('abc'))
        ['abc']
        >>> list(iter__(['a', 'b']))
        ['a', 'b']
    """
    if iterable__(obj, atom_types):
        yield from obj
    else:
        yield obj


def flatten_iter(
    iterable_obj: Any,
    atom_types: Tuple = (str,),
    non_atom_types: Tuple = None,
    max_depth: int = -1,
    _current_depth: int = 0,
) -> Iterator:
    """
    Flatten a nested iterable structure.

    Args:
        iterable_obj: Object to flatten.
        atom_types: Types to treat as atoms (non-iterable).
        non_atom_types: Types to treat as non-atoms (iterable).
        max_depth: Maximum depth to flatten (-1 for unlimited).
        _current_depth: Internal tracking of current depth.

    Yields:
        Flattened elements.

    Examples:
        >>> list(flatten_iter([[1, 2], [3, [4, 5]]]))
        [1, 2, 3, 4, 5]
        >>> list(flatten_iter([[1, 2], [3, [4, 5]]], max_depth=1))
        [1, 2, 3, [4, 5]]
    """
    _non_atom_types = _get_non_atom_types(non_atom_types, atom_types)

    if max_depth >= 0 and _current_depth >= max_depth:
        yield iterable_obj
        return

    if _non_atom_types is not None:
        if isinstance(iterable_obj, _non_atom_types):
            for item in iterable_obj:
                yield from flatten_iter(
                    item, atom_types, non_atom_types, max_depth, _current_depth + 1
                )
        else:
            yield iterable_obj
    elif atom_types is not None:
        if isinstance(iterable_obj, atom_types):
            yield iterable_obj
        elif isinstance(iterable_obj, (Iterable, Iterator, Sequence)):
            for item in iterable_obj:
                yield from flatten_iter(
                    item, atom_types, non_atom_types, max_depth, _current_depth + 1
                )
        else:
            yield iterable_obj
    else:
        try:
            for item in iterable_obj:
                yield from flatten_iter(
                    item, atom_types, non_atom_types, max_depth, _current_depth + 1
                )
        except TypeError:
            yield iterable_obj


def tqdm_wrap(iterable_obj, use_tqdm=False, **tqdm_kwargs):
    """
    Optionally wrap an iterable with tqdm progress bar.

    Args:
        iterable_obj: Iterable to wrap.
        use_tqdm: Whether to use tqdm.
        **tqdm_kwargs: Arguments to pass to tqdm.

    Returns:
        The iterable, optionally wrapped with tqdm.
    """
    if use_tqdm:
        try:
            from tqdm import tqdm

            return tqdm(iterable_obj, **tqdm_kwargs)
        except ImportError:
            pass
    return iterable_obj


def split_iter(
    data: Any,
    num_splits: int = None,
    split_size: int = None,
    weights: List[float] = None,
    use_tqdm: bool = False,
) -> Iterator[List]:
    """
    Split an iterable into chunks.

    Args:
        data: Data to split.
        num_splits: Number of splits to create.
        split_size: Size of each split.
        weights: Weights for each split.
        use_tqdm: Whether to show progress.

    Yields:
        Chunks of data.
    """
    from rankevolve.src.utils.common_utils.array_helper import split_list

    if not sliceable(data):
        data = list(data)

    yield from split_list(
        data, num_splits=num_splits, split_size=split_size, weights=weights
    )
