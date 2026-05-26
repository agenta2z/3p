import itertools
import uuid
import warnings
from itertools import zip_longest, chain, product, islice, repeat
from typing import Iterator, Union, Tuple, List, Type, Iterable, Callable, Optional, Mapping, Sequence, Set, Dict, Any
import random

from python_utils.common_utils.array_helper import split_list
from python_utils.common_utils.typing_helper import iterable__, sliceable


# region Essential Iter Helpers
def _get_non_atom_types(
        non_atom_types: Union[Tuple[Type, ...], List[Type], Type],
        always_consider_iterator_as_non_atom: bool = True
) -> Union[Iterable[Type], Type]:
    """
    Internal function. Used by `iter_`.

    Adds `Iterator` type to the type list `non_atom_types`
    when `always_consider_iterator_as_non_atom` is set True.

    If `always_consider_iterator_as_non_atom` is set False,
    this function takes no action, and `non_atom_types` is returned.

    Examples:
        >>> _get_non_atom_types(
        ...     non_atom_types=(list, tuple),
        ...     always_consider_iterator_as_non_atom=True
        ... )
        (typing.Iterator, <class 'list'>, <class 'tuple'>)

        >>> _get_non_atom_types(
        ...     non_atom_types=(list, tuple),
        ...     always_consider_iterator_as_non_atom=False
        ... )
        (<class 'list'>, <class 'tuple'>)

    """
    if always_consider_iterator_as_non_atom:
        if isinstance(non_atom_types, (list, tuple)):
            if Iterator not in non_atom_types:
                return (Iterator, *non_atom_types)
        elif non_atom_types is not Iterator:
            return Iterator, non_atom_types
    return non_atom_types


def in__(
        x,
        collection,
        atom_types=(str,)
):
    """
    Checks if an element `x` is in `collection`, treating certain types as atomic.

    If `collection` is an instance of a type specified in `atom_types`, or is not iterable,
    it is treated as an atomic value, and the function returns `x == collection`.
    Otherwise, it checks if `x` is in `collection` using the `in` operator.

    Args:
        x: The element to check for membership.
        collection: The collection or atomic value to check against.
                    If `collection` is `None`, returns `False`.
        atom_types (tuple, optional): A tuple of types to treat as atomic (non-iterable). Defaults to `(str,)`.

    Returns:
        bool: `True` if `x` is in `collection` or equal to `collection` (when treated as atomic), `False` otherwise.

    Examples:
        >>> in__(1, [1, 2, 3])
        True
        >>> in__(4, [1, 2, 3])
        False
        >>> in__('a', 'abc')
        False
        >>> in__('abc', 'abc')
        True
        >>> in__('a', ['a', 'b', 'c'])
        True
        >>> in__(None, [None, 1, 2])
        True
        >>> in__(None, [1, 2, 3])
        False
        >>> in__(1, None)
        False
        >>> in__(None, None)
        False
        >>> in__('apple', {'apple', 'banana', 'cherry'})
        True
        >>> in__('grape', {'apple', 'banana', 'cherry'})
        False
        >>> in__(1, 1)
        True
        >>> in__(1, 2)
        False
        >>> in__('a', 'a')
        True
        >>> in__('a', 'abc', atom_types=())
        True
        >>> in__('a', 'abc', atom_types=None)
        True
        >>> in__(1, 1.0)
        True
    """
    if collection is None:
        return False
    else:
        if isinstance(collection, Iterator) or iterable__(collection, atom_types=atom_types):
            return x in collection
        else:
            return x == collection


def iter_(
        _it,
        non_atom_types=(list, tuple),
        infinitely_yield_atom: bool = False,
        iter_none: bool = False,
        always_consider_iterator_as_non_atom: bool = True
) -> Iterator:
    """
    Get an iterator for an iterable object, whose type must be one of `non_atom_types`;
    otherwise the function yields the object itself.

    If `always_consider_iterator_as_non_atom` is set True,
    then an object of :type:`Iterator` will always be considered as a non-atomic iterable type,
    even it is not specified in `non_atom_types`.

    In many use cases, an python iterable type, such as a string,
    cannot be treated as an iterable.

    Args:
        _it: the object to iterate through; it will only be considered as an iterable
            if its type is one of the types specified by `non_atom_types`,
            or if it is an :type:`Iterator` object and
            `always_consider_iterator_as_non_atom` is set True.
        non_atom_types: constraints the types that are considered as being iterable;
            all other types are not considered as being iterable,
            except for an :type:`Iterator` object
            if `always_consider_iterator_as_non_atom` is set True.
        infinitely_yield_atom: if `_it` is an atom, then yield it infinitely;
            this option is useful when combining `iter_` with `zip`.
        iter_none: True to still yield `_it` if it is None.
        always_consider_iterator_as_non_atom: True to always consider an :type:`Iterator` object
            as an iterable, regardless of `non_atom_types`.

    Returns: an iterator iterating through `_it` if it is iterable and whose type is
        one of `non_atom_types`, or an :type:`Iterator` if `always_consider_iterator_as_non_atom`
        is set True; otherwise an iterator only yielding `_it` itself.

    Examples:
        >>> list(iter_(0))
        [0]
        >>> list(iter_('123'))
        ['123']
        >>> list(iter_('123', non_atom_types=(str, )))
        ['1', '2', '3']
        >>> list(iter_(None))
        []
        >>> list(iter_(None, iter_none=True))
        [None]
        >>> list(iter_((1, 2, None)))
        [1, 2, None]
        >>> list(iter_({1, 2, None}))
        [{None, 1, 2}]
        >>> list(zip([1,2,3], iter_(0, infinitely_yield_atom=True)))
        [(1, 0), (2, 0), (3, 0)]
    """
    non_atom_types = _get_non_atom_types(
        non_atom_types,
        always_consider_iterator_as_non_atom
    )
    if _it is not None:
        if isinstance(_it, non_atom_types):
            yield from _it
        elif infinitely_yield_atom:
            while True:
                yield _it
        else:
            yield _it
    elif iter_none:
        if infinitely_yield_atom:
            while True:
                yield _it
        else:
            yield _it


def iter__(
        _it,
        atom_types=(str,),
        infinitely_yield_atom: bool = False,
        iter_none: bool = False
) -> Iterator:
    """
    Get an iterator for an iterable object which is not of `atom_types`;
    otherwise yield the object itself.

    Args:
        _it: the object to iterate through.
        atom_types: if `_it` is of `atom_types`, then it is treated as a non-iterable;
            by default we treat a string object as non-iterable.
        infinitely_yield_atom: if `_it` is an atom, then yield it infinitely;
            this option is useful when combining `iter_` with `zip_longest`.
        iter_none: True to still yield `_it` if it is None.

    Returns: an iterator iterating through `_it` if it is iterable and not of `atom_types`;
        otherwise an iterator yielding `_it` itself.

    Examples:
        >>> list(iter__(0))
        [0]
        >>> list(iter__('123'))
        ['123']
        >>> list(iter__('123', atom_types=None))
        ['1', '2', '3']
        >>> list(iter__(None))
        []
        >>> list(iter__((1, 2, None)))
        [1, 2, None]
        >>> list(iter__(None, iter_none=True))
        [None]
        >>> from itertools import zip_longest
        >>> list(zip([1,2,3], iter__(0, infinitely_yield_atom=True)))
        [(1, 0), (2, 0), (3, 0)]

    """
    if _it is not None:
        if iterable__(_it, atom_types=atom_types):
            yield from _it
        elif infinitely_yield_atom:
            while True:
                yield _it
        else:
            yield _it
    elif iter_none:
        if infinitely_yield_atom:
            while True:
                yield _it
        else:
            yield _it


def tuple_(
        x,
        size_or_default_values: Union[int, Sequence] = None,
        non_atom_types=(list, tuple),
        cutoff: bool = False
):
    """
    Convert the input into a tuple with a specified size or default values.

    Args:
        x: The input object to be converted into a tuple.
        size_or_default_values (Union[int, Sequence], optional):
            Either an integer specifying the desired size of the tuple or a sequence of default values
            to fill the tuple if its length is less than the length of the defaults. Defaults to None.
        non_atom_types (tuple, optional):
            Tuple of non-atomic types. Defaults to (list, tuple).
        cutoff (bool, optional):
            If True, truncates the input tuple to match the specified size or default values.
            If False, raises a ValueError if the input tuple is longer than the specified size. Defaults to False.

    Returns:
        tuple: The converted tuple.

    Raises:
        ValueError:
            If the input does not match the expected size or default values,
            or if 'size_or_default_values' is not of type int, Sequence, or None.

    Examples:
        >>> tuple_("hello")
        ('hello',)

        >>> tuple_([1, 2, 3], 5)
        (1, 2, 3, None, None)

        >>> tuple_((1, 2, 3, 4), 2)
        Traceback (most recent call last):
            ...
        ValueError: expected maximum tuple length 2; got 4

        >>> tuple_((1, 2, 3, 4), 2, cutoff=True)
        (1, 2)

        >>> tuple_((1, 2), (3, 4, 5))
        (1, 2, 5)

        >>> tuple_([1, 2, 3], (4, 5, 6), cutoff=True)
        (1, 2, 3)

        >>> tuple_((1, 2, 3), 5, cutoff=True)
        (1, 2, 3, None, None)
    """
    if isinstance(size_or_default_values, int):
        if not isinstance(x, non_atom_types):
            return x, *([None] * (size_or_default_values - 1))

        if not isinstance(x, tuple):
            x = tuple(x)
        if len(x) == size_or_default_values:
            return x
        elif len(x) > size_or_default_values:
            if cutoff:
                return x[:size_or_default_values]
            else:
                raise ValueError(f'expected maximum tuple length {size_or_default_values}; got {len(x)}')
        else:
            return x + (None,) * (size_or_default_values - len(x))
    elif size_or_default_values is None:
        if not isinstance(x, non_atom_types):
            return x,
        elif not isinstance(x, tuple):
            return tuple(x)
        else:
            return x
    elif isinstance(size_or_default_values, Sequence):
        if not isinstance(x, tuple):
            x = tuple(x)
        len_defaults = len(size_or_default_values)
        if len(x) == len_defaults:
            return x
        elif len(x) > len_defaults:
            if cutoff:
                return x[:size_or_default_values]
            else:
                raise ValueError(f'expected maximum tuple length {size_or_default_values}; got {len(x)}')
        else:
            return x + tuple(size_or_default_values[len(x):])
    else:
        raise ValueError(f"'defaults' can only be an integer, a Sequence, or None, got '{size_or_default_values}'")


def dedup_iter(iterable: Iterable, key: Union[str, Callable, None] = None):
    """
    Yields unique elements from an iterable, based on their value or a specified key.

    Uniqueness can be based directly on the elements' values, or on a key extracted either as a specified
    attribute or through a callable function.

    Args:
        iterable (Iterable): The collection of elements to process.
        key (Union[str, Callable, None], optional): A string indicating an attribute name of objects
            in the iterable, or a callable that extracts a hashable key from each element.
            If None, elements are assumed to be directly hashable and are used as their own key.

    Yields:
        Iterator of unique elements based on the specified or default key.

    Examples:
        >>> list(dedup_iter("banana"))
        ['b', 'a', 'n']
        >>> list(dedup_iter([1, 2, 2, 3, 2, 1]))
        [1, 2, 3]
        >>> list(dedup_iter([1, 2, 2, 3, 3, 3, 4]))
        [1, 2, 3, 4]
        >>> list(dedup_iter([{'id': 1}, {'id': 2}, {'id': 1}], key='id'))
        [{'id': 1}, {'id': 2}]
        >>> list(dedup_iter([{'id': 1}, {'id': 2}, {'id': 1}], key=lambda x: x['id']))
        [{'id': 1}, {'id': 2}]
    """
    if key is None:
        if isinstance(iterable, Set):
            yield from iterable
        if isinstance(iterable, Dict):
            yield from iterable.keys()
        else:
            seen = set()
            for x in iterable:
                if x not in seen:
                    yield x
                    seen.add(x)
    else:
        from python_utils.common_utils import get_
        seen = set()
        for item in iterable:
            _key = get_(item, key)
            if _key not in seen:
                seen.add(_key)
                yield item


def update_values(
        update_func: Callable[[Any], Any],
        obj: Any,
        atom_types: Tuple[Type, ...] = (str,),
        inplace: bool = True,
        _obj_cache: Optional[Dict[int, Any]] = None
) -> Any:
    """
    Recursively iterates through non-atom values in an object and applies an update function.
    
    This function traverses nested data structures (lists, tuples, dicts, sets, etc.) and applies
    the update_func to atomic values (leaf nodes). Non-atomic structures are recursively processed.
    For mutable types (dict, list), updates can be done in-place for better performance.
    
    Args:
        update_func: A callable that takes an atomic value and returns the updated value.
        obj: The object to process. Can be any type including nested structures.
        atom_types: A tuple of types to treat as atomic (non-iterable). These types will be
                   passed directly to update_func rather than being recursively processed.
                   Defaults to (str,) since strings are iterable but usually treated as atoms.
        inplace: If True, modifies mutable objects (dict, list) in-place for better performance.
                If False, creates new objects. Defaults to True.
        _obj_cache: Internal parameter to handle circular references. Do not use directly.
    
    Returns:
        The updated object with the same structure as the input, but with atomic values
        transformed by update_func. If inplace=True and obj is mutable, returns the same
        object (modified). Otherwise returns a new object.
    
    Examples:
        # Update all numbers in a nested structure
        >>> update_values(lambda x: x * 2 if isinstance(x, (int, float)) else x, [1, [2, 3], {'a': 4}])
        [2, [4, 6], {'a': 8}]
        
        # Convert all strings to uppercase
        >>> update_values(str.upper, {'name': 'alice', 'items': ['apple', 'banana']})
        {'name': 'ALICE', 'items': ['APPLE', 'BANANA']}
        
        # Update nested dictionaries
        >>> data = {'a': 1, 'b': {'c': 2, 'd': [3, 4]}}
        >>> update_values(lambda x: x + 10 if isinstance(x, int) else x, data)
        {'a': 11, 'b': {'c': 12, 'd': [13, 14]}}
        
        # In-place update (default)
        >>> data = {'a': 1, 'b': [2, 3]}
        >>> result = update_values(lambda x: x * 2 if isinstance(x, int) else x, data)
        >>> result is data  # Same object
        True
        >>> data
        {'a': 2, 'b': [4, 6]}
        
        # Non-in-place update
        >>> data = {'a': 1, 'b': [2, 3]}
        >>> result = update_values(lambda x: x * 2 if isinstance(x, int) else x, data, inplace=False)
        >>> result is data  # Different object
        False
        >>> data  # Original unchanged
        {'a': 1, 'b': [2, 3]}
        >>> result
        {'a': 2, 'b': [4, 6]}
        
        # Handle tuples (converted to lists by default)
        >>> update_values(lambda x: x * 2 if isinstance(x, int) else x, (1, 2, (3, 4)))
        [2, 4, [6, 8]]
        
        # Handle sets (converted to lists)
        >>> result = update_values(lambda x: x + 1 if isinstance(x, int) else x, {1, 2, 3})
        >>> sorted(result)
        [2, 3, 4]
        
        # Treat strings as atoms (default behavior)
        >>> update_values(str.upper, ['hello', 'world'])
        ['HELLO', 'WORLD']
        
        # Process strings as iterables by excluding from atom_types
        >>> update_values(str.upper, ['hello'], atom_types=())
        [['H', 'E', 'L', 'L', 'O']]
        
        # Handle None values
        >>> update_values(lambda x: 'null' if x is None else x, [1, None, [2, None]])
        [1, 'null', [2, 'null']]
        
        # Complex nested structure
        >>> data = {
        ...     'users': [
        ...         {'name': 'alice', 'age': 30},
        ...         {'name': 'bob', 'age': 25}
        ...     ],
        ...     'count': 2
        ... }
        >>> update_values(
        ...     lambda x: x.upper() if isinstance(x, str) else x * 2 if isinstance(x, int) else x,
        ...     data
        ... )
        {'users': [{'name': 'ALICE', 'age': 60}, {'name': 'BOB', 'age': 50}], 'count': 4}
    """
    # Initialize cache for circular reference detection
    if _obj_cache is None:
        _obj_cache = {}
    
    obj_id = id(obj)
    
    # Handle circular references
    if obj_id in _obj_cache:
        return _obj_cache[obj_id]
    
    # Check if obj is an atom type - apply update_func directly
    if obj is None or isinstance(obj, atom_types):
        return update_func(obj)
    
    # Check if obj is a basic immutable type (not iterable in a meaningful way)
    if isinstance(obj, (int, float, bool, complex, bytes)):
        return update_func(obj)
    
    # Special case: single-character strings should be treated as atoms
    # to avoid infinite recursion when atom_types doesn't include str
    if isinstance(obj, str) and len(obj) <= 1:
        return update_func(obj)
    
    # Handle dict types - update in-place if possible
    if isinstance(obj, dict):
        if inplace:
            # Update in-place for better performance
            _obj_cache[obj_id] = obj
            for key in list(obj.keys()):  # Use list() to avoid RuntimeError during iteration
                obj[key] = update_values(update_func, obj[key], atom_types, inplace, _obj_cache)
            return obj
        else:
            # Create new dict
            result = {}
            _obj_cache[obj_id] = result
            for key, value in obj.items():
                result[key] = update_values(update_func, value, atom_types, inplace, _obj_cache)
            return result
    
    # Handle other Mapping types (OrderedDict, etc.) - create new since we can't assume mutability
    if isinstance(obj, Mapping):
        result = {}
        _obj_cache[obj_id] = result
        for key, value in obj.items():
            result[key] = update_values(update_func, value, atom_types, inplace, _obj_cache)
        return result
    
    # Handle list types - update in-place if possible
    if isinstance(obj, list):
        if inplace:
            # Update in-place for better performance
            _obj_cache[obj_id] = obj
            for i in range(len(obj)):
                obj[i] = update_values(update_func, obj[i], atom_types, inplace, _obj_cache)
            return obj
        else:
            # Create new list
            result = []
            _obj_cache[obj_id] = result
            for item in obj:
                result.append(update_values(update_func, item, atom_types, inplace, _obj_cache))
            return result
    
    # Handle other Sequence types (tuple) and other iterables (set, etc.) - always create new
    if isinstance(obj, (Sequence, Set)) or (hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes))):
        result_list = []
        _obj_cache[obj_id] = result_list
        for item in obj:
            result_list.append(update_values(update_func, item, atom_types, inplace, _obj_cache))
        return result_list
    
    # For any other type, treat as atom and apply update_func
    return update_func(obj)


# endregion

# region Iterable Information
def is_homogeneous_iterable(items: Iterable) -> bool:
    """
    Determines if all elements in an iterable are of the same type.

    Args:
        items (Iterable): An iterable (list, tuple, set, generator, etc.) of elements.

    Returns:
        bool: True if all elements are of the same type, or the iterable is empty; False otherwise.

    Examples:
        >>> is_homogeneous_iterable([1, 2, 3])
        True
        >>> is_homogeneous_iterable([1, '2', 3])
        False
        >>> is_homogeneous_iterable(iter([1.0, 2.0, 3.0]))
        True
        >>> is_homogeneous_iterable([])
        True
        >>> is_homogeneous_iterable(['hello', 'world', 'test'])
        True
        >>> is_homogeneous_iterable(iter(['hello', 'world', 3]))
        False
        >>> is_homogeneous_iterable(iter([1, 2, 3, 4.5]))
        False
        >>> is_homogeneous_iterable(iter([{'a': 1}, {'b': 2}]))
        True
        >>> is_homogeneous_iterable(iter([1, 2, [3]]))
        False
    """
    _iter = iter(items)
    try:
        first_type = type(next(_iter))
    except StopIteration:
        return True
    return all(isinstance(item, first_type) for item in _iter)


def len_(x, non_atom_types=(List, Tuple, Set)):
    """
    Compute a custom length of `x` based on the given non-atomic types.

    This function treats `None` as having length 0.
    If `x` is an instance of one of the specified `non_atom_types` (e.g., list, tuple, set)
    and it has a `__len__` method, return its length. Otherwise, treat it as an atomic value
    and return 1.

    Args:
        x (Any): The object whose length is to be determined.
        non_atom_types (tuple): A tuple of types that, if `x` is an instance of one of them,
            `len(x)` is returned. Defaults to (List, Tuple, Set).

    Returns:
        int: The computed length.

    Examples:
        >>> len_(None)
        0
        >>> len_([1, 2, 3])
        3
        >>> len_((1, 2))
        2
        >>> len_({1, 2, 3})
        3
        >>> len_("hello")
        1
        >>> len_(42)
        1
    """
    if x is None:
        return 0
    return len(x) if isinstance(x, non_atom_types) and hasattr(x, '__len__') else 1


def len__(x, atom_types=(str,)):
    """
    Compute a custom length of `x` based on the given atomic types.

    This function treats `None` as having length 0.
    If `x` is an instance of one of the specified `atom_types` (e.g., str)
    or does not have a `__len__` method at all, it returns 1. Otherwise, it returns `len(x)`.

    Args:
        x (Any): The object whose length is to be determined.
        atom_types (tuple): A tuple of types that are considered atomic. Defaults to (str,).

    Returns:
        int: The computed length.

    Examples:
        >>> len__(None)
        0
        >>> len__("hello")
        1
        >>> len__([1, 2, 3])
        3
        >>> len__({1, 2})
        2
        >>> class NoLen:
        ...     pass
        >>> obj = NoLen()
        >>> len__(obj)
        1
        >>> len__(42)  # int has no __len__
        1
    """
    if x is None:
        return 0
    return 1 if isinstance(x, atom_types) or (not hasattr(x, '__len__')) else len(x)


def max_len__(x, atom_types=(str,), default=0):
    if x is None:
        return default
    return max(len(_x) for _x in iter__(x, atom_types=atom_types))


def min_len__(x, atom_types=(str,), default=0):
    if x is None:
        return default
    return min(len(_x) for _x in iter__(x, atom_types=atom_types))


# endregion

# region Zipping Helpers
def zip_(*iterables, non_atom_types=(list, tuple), iter_none: bool = True):
    """
    Custom zip function that handles iterables and non-iterable types, including None values.
    This function extends the behavior of the built-in zip function to work with non-iterable
    types and to optionally handle None values in a specific way.

    Args:
        *iterables: Variable length argument list of iterables or non-iterables to be zipped.
        non_atom_types (tuple, optional): A tuple of types that are considered non-atomic (iterables). Defaults to (list, tuple).
        iter_none (bool, optional): If True, includes None values in the zipped output. If False, skips None values. Defaults to True.

    Examples:
        >>> list(zip__('12', '34'))
        [('12', '34')]
        >>> list(zip__(0, 1, 2))
        [(0, 1, 2)]
        >>> list(zip__(0, [1,2,3], [5,6,7,8]))
        [(0, 1, 5), (0, 2, 6), (0, 3, 7)]
        >>> list(zip__([1,2,3], None))
        [(1, None), (2, None), (3, None)]
        >>> list(zip__([1,2,3], None, [5,6,7,8]))
        [(1, None, 5), (2, None, 6), (3, None, 7)]
        >>> list(zip__([1,2,3], None, [5,6,7,8], iter_none=False))
        []
        >>> list(zip__(None, None, None))
        [(None, None, None)]
        >>> list(zip__(None, None, None, iter_none=False))
        []

    """
    if any(isinstance(x, non_atom_types) for x in iterables):
        yield from zip(
            *(
                iter_(x, non_atom_types=non_atom_types, infinitely_yield_atom=True, iter_none=iter_none)
                for x in iterables
            )
        )
    elif iter_none or any(x is not None for x in iterables):
        yield iterables


def zip__(*iterables, atom_types=(str,), iter_none: bool = True):
    """
    Custom zip function that allows zipping None or atomic types (of `atom_types`) with iterables.
    This function extends the behavior of the built-in zip function to handle None values and
    atomic types (like strings) along with iterables.

    Args:
        *iterables: Variable length argument list of iterables, None, or atomic types to be zipped.
        atom_types (tuple, optional): A tuple of types that are considered atomic (non-iterable). Defaults to (str,).
        iter_none (bool, optional): If True, includes None values in the zipped output. If False, skips None values. Defaults to True.

    Yields:
        tuple: Tuples containing the zipped elements from the provided iterables, None, or atomic types.

    Examples:
        >>> list(zip__('12', '34'))
        [('12', '34')]
        >>> list(zip__(0, 1, 2))
        [(0, 1, 2)]
        >>> list(zip__(0, [1,2,3], [5,6,7,8]))
        [(0, 1, 5), (0, 2, 6), (0, 3, 7)]
        >>> list(zip__([1,2,3], None))
        [(1, None), (2, None), (3, None)]
        >>> list(zip__([1,2,3], None, [5,6,7,8]))
        [(1, None, 5), (2, None, 6), (3, None, 7)]
        >>> list(zip__([1,2,3], None, [5,6,7,8], iter_none=False))
        []
        >>> list(zip__(None, None, None))
        [(None, None, None)]
        >>> list(zip__(None, None, None, iter_none=False))
        []
    """
    if any(iterable__(x, atom_types=atom_types) for x in iterables):
        yield from zip(
            *(
                iter__(x, atom_types=atom_types, infinitely_yield_atom=True, iter_none=iter_none)
                for x in iterables
            )
        )
    elif iter_none or any(x is not None for x in iterables):
        yield iterables


def zip_longest__(
        *iterables,
        atom_types=(str,),
        fill_none_by_previous_values: Union[bool, Tuple[bool], List[bool]] = True
):
    """
    Allows zipping atoms with iterables.

    Instead of using None as a placeholder when one interable is shorter,
    this function can use the last available value at the same position;
    set `fill_none_by_previous_values` to True or False
    to enable/disable this behavior for all dimensions,
    or a list of True/False values to control the behavior for each dimension.

    Examples:
        >>> list(zip_longest__(1, None))
        [(1, None)]
        >>> list(zip_longest__([1, 2, 3], None))
        [(1, None), (2, None), (3, None)]
        >>> list(zip_longest__(0, [1, 2, 3], [5, 6, 7, 8]))
        [(0, 1, 5), (0, 2, 6), (0, 3, 7), (0, 3, 8)]
        >>> list(zip_longest__([1, 2, 3], None, [5, 6, 7, 8]))
        [(1, None, 5), (2, None, 6), (3, None, 7), (3, None, 8)]
        >>> list(zip_longest__(0, [1, 2, 3], [5, 6, 7, 8], fill_none_by_previous_values=False))
        [(0, 1, 5), (None, 2, 6), (None, 3, 7), (None, None, 8)]
        >>> list(
        ...   zip_longest__(
        ...      0, [1, 2, 3], [5, 6, 7, 8],
        ...      fill_none_by_previous_values=[True, False, False, False]
        ...   )
        ... )
        [(0, 1, 5), (0, 2, 6), (0, 3, 7), (0, None, 8)]
    """
    zip_obj = zip_longest(*(iter__(x, atom_types=atom_types) for x in iterables))

    if not fill_none_by_previous_values:
        yield from zip_obj
    else:
        _items = next(zip_obj)
        yield _items

        if isinstance(fill_none_by_previous_values, (list, tuple)):
            for items in zip_obj:
                _items = tuple(
                    (x if (x is not None or not _fill_none) else y)
                    for x, y, _fill_none in zip(items, _items, fill_none_by_previous_values)
                )
                yield _items
        elif fill_none_by_previous_values is True:
            for items in zip_obj:
                _items = tuple(
                    (x if x is not None else y)
                    for x, y in zip(items, _items)
                )
                yield _items


def unzip(
        tuples: Iterable[Tuple],
        idx: Optional[Union[int, Iterable[int]]] = None
) -> Union[Tuple, Iterable[Tuple]]:
    """
    Unzips a sequence of tuples to a tuple of sequences.
    Can choose to optionally return the sequence at one or more specified index(es).

    Examples:
        >>> zipped_seq = [(1, -1), (2, -2), (3, -3), (4, -4), (5, -5)]
        >>> list(unzip(zipped_seq))
        [(1, 2, 3, 4, 5), (-1, -2, -3, -4, -5)]
        >>> list(unzip(zipped_seq, idx=1))
        [-1, -2, -3, -4, -5]
    """
    if idx is None:
        return zip(*tuples)
    elif idx == 0:
        return next(zip(*tuples))
    elif type(idx) is int:
        return tuple(zip(*tuples))[idx]
    else:
        unzips = tuple(zip(*tuples))
        return (unzips[_idx] for _idx in idx)


# endregion

# region Product Iterators

def product_(*iterables, non_atom_types=(list, tuple, set), ignore_none=False):
    """
    Cartesian product of input iterables like `product`, but any one of `iterables` of `atom_types`
    will be treated as non-iterable, and any None value in `iterables` can be ignored
    if `ignore_none` is set True.

    Examples:
        >>> list(product_([1,2], 3))
        [(1, 3), (2, 3)]
        >>> list(product_([1,2], None, 3))
        [(1, None, 3), (2, None, 3)]
        >>> list(product_([1,2], None, 3, ignore_none=True))
        [(1, 3), (2, 3)]

    """
    if ignore_none:
        yield from product(
            *(iter_(x, non_atom_types=non_atom_types) for x in iterables if x is not None)
        )
    else:
        yield from product(
            *(iter_(x, non_atom_types=non_atom_types, iter_none=True) for x in iterables)
        )


def product__(*iterables, atom_types=(str,), ignore_none=False):
    """
    Cartesian product of input iterables like `product`, but any one of `iterables` of `atom_types`
    will be treated as non-iterable, and any None value in `iterables` can be ignored
    if `ignore_none` is set True.

    Examples:
        >>> list(product__([1,2], 3))
        [(1, 3), (2, 3)]
        >>> list(product__([1,2], None, 3))
        [(1, None, 3), (2, None, 3)]
        >>> list(product__([1,2], None, 3, ignore_none=True))
        [(1, 3), (2, 3)]

    """
    if ignore_none:
        yield from product(
            *(iter__(x, atom_types=atom_types) for x in iterables if x is not None)
        )
    else:
        yield from product(
            *(iter__(x, atom_types=atom_types, iter_none=True) for x in iterables)
        )


# endregion

# region Chain Iterators

def dedup_chain(*_its: Iterable):
    """Chains multiple iterables, returning each item once in order of first occurrence.

    Args:
        *_its: One or more iterables to chain together.

    Returns:
        An iterator that yields deduplicated items from all input iterables in sequence.

    Examples:
        >>> from itertools import repeat
        >>> list(dedup_chain([1,2,2], repeat(2, 3), [2,3,4]))
        [1, 2, 3, 4]
    """
    return dedup_iter(chain(*_its))


def chain__(*_its, atom_types=(str,), iter_none=False):
    return chain(iter__(_it, atom_types=atom_types, iter_none=iter_none) for _it in _its)


def flatten_iter(
        x: Iterable,
        non_atom_types=(list, tuple),
        always_consider_iterator_as_non_atom: bool = True,
        sort: Callable[[Iterable], Iterable] = None,
        ignore_none: bool = False
) -> Iterator:
    """
    Flattens a nested iterable (one level deep) into a flat generator, yielding elements one by one.
    Handles nesting by recursively yielding from any sub-iterable that is considered
    non-atomic according to the given types. An optional sorting function can be applied
    to each iterable before flattening.

    Args:
        x: The iterable to flatten. Can contain nested iterables.
        non_atom_types: A tuple of types to consider as non-atomic.
            These are types that should be flattened.
        always_consider_iterator_as_non_atom: If True, any iterator type is considered non-atomic by default.
            If False, only the types specified in non_atom_types are considered.
        sort: A function to sort each iterable before flattening. It should take an iterable
            and return an iterable sorted in the desired order. If None, no sorting is applied.
        ignore_none: If True, `None` values will be excluded from the flattened results.

    Yields:
        Elements of `x`, flattened for one level. If `sort` is provided, elements
        from each sub-iterable are sorted before yielding. If `ignore_none` is True,
        `None` values are skipped.

    Examples:
        Flatten a simple nested list:
        >>> list(flatten_iter([1, 2, [3, 4], (5, 6)]))
        [1, 2, 3, 4, 5, 6]

        Flatten while ignoring `None` values:
        >>> list(flatten_iter([1, None, [2, None, 3], (4, 5)], ignore_none=True))
        [1, 2, 3, 4, 5]

        Flatten a deeply nested list (only one level deep):
        >>> list(flatten_iter([1, [2, [3, 4]], 5]))
        [1, 2, [3, 4], 5]

        Specify `non_atom_types` to flatten only tuples:
        >>> list(flatten_iter((1, (2, [3, 4], 5), 6), non_atom_types=(tuple,)))
        [1, 2, [3, 4], 5, 6]

        Apply sorting to sub-iterables:
        >>> list(flatten_iter([1, [3, 2], (5, 4)], sort=sorted))
        [1, 2, 3, 4, 5]

        Handle single values:
        >>> list(flatten_iter(42))
        [42]
        >>> list(flatten_iter(None))
        [None]
        >>> list(flatten_iter((None, 42), ignore_none=True))
        [42]
    """
    non_atom_types = _get_non_atom_types(non_atom_types, always_consider_iterator_as_non_atom)
    if x is None:
        if not ignore_none:
            yield None
    elif isinstance(x, non_atom_types):
        for _x in x:
            if _x is None:
                if not ignore_none:
                    yield None
            elif isinstance(_x, non_atom_types):
                if ignore_none:
                    if sort is None:
                        yield from (__x for __x in _x if __x is not None)
                    else:
                        yield from sort((__x for __x in _x if __x is not None))
                else:
                    if sort is None:
                        yield from _x
                    else:
                        yield from sort(_x)
            else:
                yield _x
    else:
        yield x


def concat(
        x: Iterable,
        non_atom_types=(list, tuple),
        always_consider_iterator_as_non_atom: bool = True,
        sort: Callable[[Iterable], Iterable] = None
):
    return list(flatten_iter(x, non_atom_types, always_consider_iterator_as_non_atom, sort))


# endregion

# region Group Iterators
def get_groups(
        iterable: Iterable[Any],
        group_key: Union[str, Callable],
) -> List[Union[Any, List]]:
    """
    Groups items in the provided iterable based on a specified key and returns these groups as a list.
    Each group contains items that share the same value for the specified group key. This function
    is particularly useful for organizing collections of items based on shared characteristics,
    where each group can be a single item or a list of items sharing the same key value.

    Args:
        iterable (Iterable): The iterable to process, where each element is an item to be grouped.
        group_key (Union[str, Callable]): A key function or attribute used to group items within the iterable.

    Returns:
        List[Union[Any, List]]: A list of groups, where each group can be a single item or a list of items that share the same key value.

    Examples:
        >>> people = [{'name': 'Alice', 'group': 'admin'}, {'name': 'Charlie', 'group': 'user'}, {'name': 'Bob', 'group': 'admin'}]
        >>> groups = get_groups(people, group_key='group')
        >>> for group in groups:
        ...     print(group)
        [{'name': 'Alice', 'group': 'admin'}, {'name': 'Bob', 'group': 'admin'}]
        {'name': 'Charlie', 'group': 'user'}

        >>> numbers = [{'value': 10, 'category': 'even'}, {'value': 15, 'category': 'odd'}, {'value': 20, 'category': 'even'}]
        >>> number_groups = get_groups(numbers, group_key='category')
        >>> for group in number_groups:
        ...     print(group)
        [{'value': 10, 'category': 'even'}, {'value': 20, 'category': 'even'}]
        {'value': 15, 'category': 'odd'}

        >>> tasks = [{'task': 'Email', 'priority': 'High'}, {'task': 'Call', 'priority': 'Medium'}, {'task': 'Report', 'priority': 'High'}]
        >>> task_groups = get_groups(tasks, group_key='priority')
        >>> for group in task_groups:
        ...     print(group)
        [{'task': 'Email', 'priority': 'High'}, {'task': 'Report', 'priority': 'High'}]
        {'task': 'Call', 'priority': 'Medium'}
    """
    from python_utils.common_utils import get_
    # Initialize variables to store item order and key to index mapping

    items: List = []
    key_to_chunk_map: Dict[Any, int] = {}
    for item in iterable:
        # Determine the key for uniquely identifying each data item within each iterable
        _key = get_(item, group_key)
        if _key not in key_to_chunk_map:
            if isinstance(item, list):
                items.append([item])
            else:
                items.append(item)
            key_to_chunk_map[_key] = len(items) - 1
        else:
            master_item_index = key_to_chunk_map[_key]
            master_item = items[master_item_index]
            if isinstance(master_item, list):
                master_item.append(item)
            else:
                items[master_item_index] = [master_item, item]

    return items


def flatten_iter_groups(
        iterable: Iterable,
        group_key: Union[str, Callable],
        sort: Callable[[Iterable], Iterable] = None
) -> Iterator:
    """
    Groups items in the provided iterable based on a specified key and yields these groups.
    Each group contains items that share the same value for the specified key,
    optionally sorted within each group if a sort function is provided. The groups are
    returned as a flattened sequence. This is useful for processing collections of
    data items that need to be organized and optionally ordered by a specific attribute.

    Args:
        iterable (Iterable): The iterable to process.
        group_key (Union[str, Callable]): A key function or attribute name used to group
            items within the iterable.
        sort (Callable[[Iterable], Iterable], optional): A function to sort each group of items
            before yielding. It should take an iterable and return it sorted in the desired order.
            If None, no sorting is applied.

    Yields:
        Iterable: Groups of items where each group consists of items having the same key value.
                  The groups are yielded as a flattened sequence. If sort is not None, items
                  within each group are yielded in sorted order.

    Examples:
        >>> from functools import partial
        >>> from python_utils.common_utils.sorting_helper import sorted_
        >>> people = [{'name': 'Bob', 'group': 'admin'}, {'name': 'Charlie', 'group': 'user'}, {'name': 'Alice', 'group': 'admin'}]
        >>> list(flatten_iter_groups(people, group_key='group'))
        [{'name': 'Bob', 'group': 'admin'}, {'name': 'Alice', 'group': 'admin'}, {'name': 'Charlie', 'group': 'user'}]
        >>> list(flatten_iter_groups(people, group_key='group', sort=partial(sorted_, key='name')))
        [{'name': 'Alice', 'group': 'admin'}, {'name': 'Bob', 'group': 'admin'}, {'name': 'Charlie', 'group': 'user'}]

        >>> transactions = [{'id': 1, 'category': 'food'}, {'id': 2, 'category': 'utilities'}, {'id': 3, 'category': 'food'}]
        >>> list(flatten_iter_groups(transactions, group_key='category', sort=lambda x: sorted(x, key=lambda y: y['id'])))
        [{'id': 1, 'category': 'food'}, {'id': 3, 'category': 'food'}, {'id': 2, 'category': 'utilities'}]

        >>> tasks = [{'task': 'Email', 'priority': 'High'}, {'task': 'Call', 'priority': 'Medium'}, {'task': 'Report', 'priority': 'High'}]
        >>> list(flatten_iter_groups(tasks, group_key='priority'))
        [{'task': 'Email', 'priority': 'High'}, {'task': 'Report', 'priority': 'High'}, {'task': 'Call', 'priority': 'Medium'}]
    """
    if group_key is not None:
        iterable = get_groups(iterable, group_key)
    yield from flatten_iter(iterable, sort=sort)


# endregion

# region Filter Iterators
def filter_(_filter, _it):
    if callable(_filter):
        return filter(_filter, _it)
    else:
        yield from (x for x in _it if x in _filter)


def filter_by_head_element(_filter, _it):
    if not _filter:
        return _it
    if callable(_filter):
        return filter(lambda x: _filter(next(iter(x))), _it)
    else:
        return (x for x in _it if next(iter(x)) in _filter)


def filter_tuples_by_head_element(_filter, _it):
    """
    Filter an iterable of tuples based on the head element (first element) of each tuple.

    Args:
        _filter: A filter condition. It can be None, a callable, or an iterable.
            - If None, the input iterable (_it) is returned unmodified.
            - If callable, it should accept the head element and return a boolean value.
            - If iterable, it should contain elements to be matched with the head element.
        _it: An iterable of tuples to be filtered.

    Returns:
        An iterable of tuples filtered based on the head element according to the given filter.

    Examples:
        >>> input_tuples = [(1, 'apple'), (2, 'banana'), (3, 'cherry')]
        >>> list(filter_tuples_by_head_element(lambda x: x % 2 == 0, input_tuples))
        [(2, 'banana')]

        >>> list(filter_tuples_by_head_element([2, 3], input_tuples))
        [(2, 'banana'), (3, 'cherry')]

        >>> list(filter_tuples_by_head_element(None, input_tuples))
        [(1, 'apple'), (2, 'banana'), (3, 'cherry')]
    """
    if not _filter:
        return _it
    if callable(_filter):
        return filter(lambda x: _filter(x[0]), _it)
    else:
        return (x for x in _it if x[0] in _filter)


# endregion

# region Extraction Iterators

def first(x, cond: Callable = None):
    """
    Returns the first element of an iterable that meets a condition. If no condition
    is specified, returns the first element of the iterable.

    Args:
        x: An iterable from which the element is returned.
        cond : A callable that takes an element of the iterable and returns
                a boolean. If this callable returns True for an element, that
                element is returned.

    Returns:
        The first element that satisfies the condition or the first element if no condition is provided.

    Examples:
        >>> first([1, 2, 3, 4], lambda x: x > 2)
        3
        >>> first([1, 2, 3, 4])
        1
    """
    if cond is None:
        for _x in x:
            return _x
    else:
        for _x in x:
            if cond(_x):
                return _x
    raise StopIteration


def first_(x, non_atom_types=(List, Tuple), cond: Callable = None):
    """
    Returns the first element of a sequence or the sequence itself if it is not a list or tuple.
    If a condition is specified, it returns the first element that meets the condition.

    Args:
        x: A sequence or any object.
        non_atom_types: Types that are considered non-atomic, typically list and tuple.
        cond: A callable to evaluate each element of the sequence.

    Returns:
        The first element that satisfies the condition, the first element if no condition is provided,
        or the object itself if it is not a list or tuple.

    Examples:
        >>> first_([1, 2, 3], cond=lambda x: x > 1)
        2
        >>> first_([1, 2, 3])
        1
        >>> first_('hello')
        'hello'
    """
    if isinstance(x, non_atom_types):
        if cond is None:
            for _x in x:
                return _x
        else:
            for _x in x:
                if cond(_x):
                    return _x
    else:
        return x


def first__(x, atom_types=str, cond: Callable = None):
    """
    Returns the first element of a sequence or the sequence itself if it's of an atomic type
    or does not support item access. If a condition is specified, it returns the first element that meets the condition.

    Args:
        x: A sequence or any object.
        atom_types: Types that are considered atomic, typically string.
        cond: A callable to evaluate each element of the sequence.

    Returns:
        The first element that satisfies the condition, the first element if no condition is provided,
        or the object itself if it is of an atomic type or does not support item access.

    Examples:
        >>> first__([1, 2, 3], cond=lambda x: x > 2)
        3
        >>> first__([1, 2, 3])
        1
        >>> first__('hello')
        'hello'
    """
    if isinstance(x, atom_types) or (not hasattr(x, '__getitem__')):
        return x
    elif cond is None:
        for _x in x:
            return _x
    else:
        for _x in x:
            if cond(_x):
                return _x


def last(x, cond: Callable = None):
    """
    Returns the last element of an iterable that meets a condition. If no condition
    is specified, returns the last element of the iterable.

    Args:
        x: An iterable from which the element is returned.
        cond: A callable that takes an element of the iterable and returns
              a boolean. If this callable returns True for an element, that
              element is considered for being the last one returned.

    Returns:
        The last element that satisfies the condition or the last element if no condition is provided.

    Examples:
        >>> last([1, 2, 3, 4], lambda x: x < 4)
        3
        >>> last([1, 2, 3, 4])
        4
    """
    if isinstance(x, Sequence):
        for i in range(len(x) - 1, -1, -1):
            if cond is None or cond(x[i]):
                return x[i]
    else:
        result = None
        for _x in x:
            if cond is None or cond(_x):
                result = _x
        return result


def last_(x, non_atom_types=(list, tuple), cond: Callable = None):
    """
    Returns the last element of a sequence or the sequence itself if it is not a list or tuple.
    If a condition is specified, it returns the last element that meets the condition.

    Args:
        x: A sequence or any object.
        non_atom_types: Types that are considered non-atomic, typically list and tuple.
        cond: A callable to evaluate each element of the sequence.

    Returns:
        The last element that satisfies the condition, the last element if no condition is provided,
        or the object itself if it is not a list or tuple.

    Examples:
        >>> last_([1, 2, 3, 4], cond=lambda x: x % 2 == 1)
        3
        >>> last_([1, 2, 3, 4])
        4
        >>> last_('hello')
        'hello'
    """
    if isinstance(x, non_atom_types):
        if isinstance(x, Sequence):
            for i in range(len(x) - 1, -1, -1):
                if cond is None or cond(x[i]):
                    return x[i]
        else:
            result = None
            for _x in x:
                if cond is None or cond(_x):
                    result = _x
            return result
    else:
        return x


def last__(x, atom_types=(str,), cond: Callable = None):
    """
    Returns the last element of a sequence or the sequence itself if it's of an atomic type
    or does not support item access. If a condition is specified, it returns the last element that meets the condition.

    Args:
        x: A sequence or any object.
        atom_types: Types that are considered atomic, typically string.
        cond: A callable to evaluate each element of the sequence.

    Returns:
        The last element that satisfies the condition, the last element if no condition is provided,
        or the object itself if it is of an atomic type or does not support item access.

    Examples:
        >>> last__([1, 2, 3, 4], cond=lambda x: x > 1)
        4
        >>> last__([1, 2, 3, 4])
        4
        >>> last__('hello')
        'hello'
    """
    if isinstance(x, atom_types) or (not hasattr(x, '__getitem__')):
        return x
    elif isinstance(x, Sequence):
        for i in range(len(x) - 1, -1, -1):
            if cond is None or cond(x[i]):
                return x[i]
    else:
        result = None
        for _x in x:
            if cond is None or cond(_x):
                result = _x
        return result


def head(iterable: Iterable, cond: Callable) -> Iterator:
    """
    Yields elements from the beginning of an iterable until a condition is met.

    Args:
        iterable: An iterable from which elements are yielded.
        cond: A callable that takes an element of the iterable and returns
                a boolean. If this callable returns True for an element, the iteration
                will break after yielding that element.

    Yields:
        Elements from the iterable until the condition is satisfied.

    Examples:
        >>> list(head([1, 2, 3, 4, 5], lambda x: x >= 3))
        [1, 2, 3]
    """
    for x in iterable:
        yield x
        if cond(x):
            break


def tail(iterable: Iterable, cond: Callable, keep_first_match: bool = False) -> Iterator:
    """
    Yields elements from an iterable starting from the element just after a condition is first met.
    Optionally includes the element that satisfies the condition as the first element in the output.

    Args:
        iterable: An iterable from which elements are yielded.
        cond: A callable that takes an element of the iterable and returns
              a boolean. When this callable returns True for the first time,
              the function begins to yield every subsequent element.
        keep_first_match (bool, optional): If True, includes the element that satisfies the condition
                                           as the first element in the output. Defaults to False.

    Yields:
        Elements from the iterable, starting from the element after the condition is first met,
        or including it if `keep_first_match` is True.

    Examples:
        >>> list(tail([1, 2, 3, 4, 5], cond=lambda x: x >= 3))
        [4, 5]
        >>> list(tail([1, 2, 3, 4, 5], cond=lambda x: x >= 3, keep_first_match=True))
        [3, 4, 5]
        >>> list(tail([1, 2, 3, 4, 5], cond=lambda x: x == 5))
        []
        >>> list(tail([1, 2, 3, 4, 5], cond=lambda x: x == 5, keep_first_match=True))
        [5]
    """
    start_yield = False
    for x in iterable:
        if not start_yield:
            if cond(x):
                start_yield = True
                if keep_first_match:
                    yield x
        else:
            yield x


# endregion

# region Chunking Iterators
def chunk_iter(
        it: Union[Iterator, Iterable],
        chunk_size: int,
        item_weight_func: Callable[[Any], int] = None,
        as_list: bool = False
) -> Union[Iterator[Iterator], Iterator[List]]:
    """
    Returns an iterator that iterates through chunks of the provided iterator or iterable,
    with optional weighting of items.

    Args:
        it (Union[Iterator, Iterable]): The iterator or iterable to chunk.
        chunk_size (int): The maximum size or weight limit for each chunk.
        item_weight_func (Callable[[Any], int], optional): Function to determine the weight of each item.
            If None, each item is considered to have a weight of 1. Defaults to None.
        as_list (bool, optional): If True, returns each chunk as a list. If False, returns an iterator of iterators. Defaults to False.

    Yields:
        Union[Iterator, List]: An iterator that iterates through chunks of the provided iterator.

    Examples:
        # Example without item weights
        >>> numbers = range(10)
        >>> chunked_iter = chunk_iter(numbers, 3)
        >>> print([list(x) for x in chunked_iter])
        [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9]]

        # Example with item weights (increasing weights)
        >>> weighted_chunked_iter = chunk_iter(numbers, 5, item_weight_func=lambda x: x + 1)
        >>> print([list(x) for x in weighted_chunked_iter])
        [[0, 1], [2], [3], [4], [5], [6], [7], [8], [9]]

        # Example with fixed item weights
        >>> constant_weight_iter = chunk_iter(numbers, 5, item_weight_func=lambda x: 2)
        >>> print([list(x) for x in constant_weight_iter])
        [[0, 1], [2, 3], [4, 5], [6, 7], [8, 9]]

        # Example as lists, no weights
        >>> list(chunk_iter(numbers, 3, as_list=True))
        [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9]]
    """
    if item_weight_func is None:
        it = iter(it)
        if as_list:
            while True:
                cur = list(islice(it, chunk_size))
                if not cur:
                    break
                yield cur
        else:
            while True:
                cur_it = islice(it, chunk_size)
                try:
                    first = next(cur_it)
                except StopIteration:
                    break
                yield chain((first,), cur_it)
    else:
        chunk = []
        chunk_weight = 0
        for item in it:
            item_weight = item_weight_func(item)
            next_chunk_weight = chunk_weight + item_weight
            if next_chunk_weight < chunk_size:
                chunk.append(item)
                chunk_weight = next_chunk_weight
            elif next_chunk_weight == chunk_size:
                chunk.append(item)
                yield chunk if as_list else iter(chunk)
                chunk = []
                chunk_weight = 0
            else:
                yield chunk if as_list else iter(chunk)
                chunk = [item]
                chunk_weight = item_weight
        if chunk:
            yield chunk if as_list else iter(chunk)


def chunk_iters(
        iterables: Iterable[Iterable],
        chunk_size: int,
        group_key: Union[str, Callable] = None,
        group_sort: Callable[[Iterable], Iterable] = None,
        item_weight_func: Callable[[Any], int] = None,
        as_list: bool = False
) -> Union[Iterator[Iterator], Iterator[List]]:
    """
    Processes multiple iterables by optionally grouping and sorting items within each iterable based on a provided key,
    then flattening the grouped and sorted items, and finally chunking the resulting sequence into specified sizes.
    This method facilitates efficient batch processing of data, particularly when items need to be categorized or
    processed based on common attributes and possibly ordered within groups across different datasets.

    Args:
        iterables (Iterable[Iterable]): A collection of iterables where each iterable contains items to be grouped and chunked.
        chunk_size (int): The size of each chunk to be returned, measured in items or their weights.
        group_key (Union[str, Callable], optional): A function or attribute used to group items within each iterable.
            If None, no grouping is applied.
        group_sort (Callable[[Iterable], Iterable], optional): A function to sort each group of items
            before chunking. It should take an iterable and return it sorted in the desired order.
            If None, no sorting is applied within groups.
        item_weight_func (Callable[[Any], int], optional): Function to determine the weight of each item for chunking.
            If None, each item is considered to have a weight of 1.
        as_list (bool, optional): Determines if the chunks should be returned as lists (True) or iterators (False).

    Returns:
        Union[Iterator[Iterator], Iterator[List]]: An iterator over chunks, where each chunk is either an iterator or a list,
                                                   depending on the `as_list` parameter.

    Examples:
        # Example with grouping and sorting
        >>> iterables = [
        ...     [{'name': 'Alice', 'group': 'admin'}, {'name': 'Charlie', 'group': 'user'}, {'name': 'Bob', 'group': 'admin'}],
        ...     [{'name': 'Dave', 'group': 'admin'}, {'name': 'Eve', 'group': 'user'}]
        ... ]
        >>> result = chunk_iters(iterables, chunk_size=2, group_key='group', group_sort=lambda x: sorted(x, key=lambda y: y['name']), as_list=True)
        >>> for chunk in result:
        ...     print(chunk)
        [{'name': 'Alice', 'group': 'admin'}, {'name': 'Bob', 'group': 'admin'}]
        [{'name': 'Charlie', 'group': 'user'}, {'name': 'Dave', 'group': 'admin'}]
        [{'name': 'Eve', 'group': 'user'}]

        >>> numbers = [
        ...     [{'value': 20, 'mod': 0}, {'value': 10, 'mod': 0}, {'value': 15, 'mod': 1}],
        ...     [{'value': 25, 'mod': 1}, {'value': 30, 'mod': 0}]
        ... ]
        >>> number_chunks = chunk_iters(numbers, 3, group_key='mod', group_sort=lambda x: sorted(x, key=lambda y: y['value']), as_list=False)
        >>> for chunk in number_chunks:
        ...     print(list(chunk))
        [{'value': 10, 'mod': 0}, {'value': 20, 'mod': 0}, {'value': 15, 'mod': 1}]
        [{'value': 25, 'mod': 1}, {'value': 30, 'mod': 0}]
        >>> number_chunks = chunk_iters(numbers, 3, group_key='mod', as_list=False)
        >>> for chunk in number_chunks:
        ...     print(list(chunk))
        [{'value': 20, 'mod': 0}, {'value': 10, 'mod': 0}, {'value': 15, 'mod': 1}]
        [{'value': 25, 'mod': 1}, {'value': 30, 'mod': 0}]

        # Example with weight-based chunking
        >>> weights = [
        ...     [{'value': 5, 'weight': 2}, {'value': 10, 'weight': 3}, {'value': 3, 'weight': 1}],
        ...     [{'value': 2, 'weight': 2}, {'value': 1, 'weight': 1}]
        ... ]
        >>> weight_chunks = chunk_iters(weights, 4, item_weight_func=lambda x: x['weight'], as_list=True)
        >>> for chunk in weight_chunks:
        ...     print(chunk)
        [{'value': 5, 'weight': 2}]
        [{'value': 10, 'weight': 3}, {'value': 3, 'weight': 1}]
        [{'value': 2, 'weight': 2}, {'value': 1, 'weight': 1}]
    """
    if group_key:
        chunk = []
        chunk_weight = 0
        for iterable in iterables:
            grouped_iterable = get_groups(iterable, group_key)
            for group_or_item in grouped_iterable:
                if isinstance(group_or_item, list):
                    if item_weight_func is not None:
                        group_or_item_weight = sum(item_weight_func(x) for x in group_or_item)
                    else:
                        group_or_item_weight = len(group_or_item)

                    if chunk_weight + group_or_item_weight > chunk_size:
                        yield chunk
                        chunk = group_or_item.copy()
                        chunk_weight = group_or_item_weight
                    else:
                        if group_sort:
                            chunk.extend(group_sort(group_or_item))
                        else:
                            chunk.extend(group_or_item)
                        chunk_weight += group_or_item_weight
                        if len(chunk) == chunk_size:
                            yield chunk
                            chunk = []
                            chunk_weight = 0
                else:
                    group_or_item_weight = 1
                    if item_weight_func is not None:
                        group_or_item_weight = item_weight_func(group_or_item)

                    if chunk_weight + group_or_item_weight > chunk_size:
                        yield chunk
                        chunk = [group_or_item]
                        chunk_weight = group_or_item_weight
                    else:
                        chunk.append(group_or_item)
                        chunk_weight += group_or_item_weight
                        if len(chunk) == chunk_size:
                            yield chunk
                            chunk = []
                            chunk_weight = 0

        if chunk:
            yield chunk
    else:
        chained_iter = chain(*iterables)
        yield from chunk_iter(
            chained_iter,
            chunk_size=chunk_size,
            item_weight_func=item_weight_func,
            as_list=as_list
        )


# endregion

# region Misc
def get_by_indexes(x, *index):
    return tuple(x[i] for i in index)


def shuffle_together(*arrs: Iterable):
    """
    Randomly shuffles multiple iterables together so that elements at the same position
    of each iterable still correspond after shuffling.

    Args:
        *arrs: The iterables to shuffle together.

    Returns:
        Tuple[Iterable, ...]: The shuffled iterables, with their elements rearranged in the same order.

    Examples:
        >>> import random
        >>> random.seed(0)  # For reproducibility
        >>> shuffled = shuffle_together([1, 2, 3, 4], ['i', 'ii', 'iii', 'iv'])
        >>> shuffled[0]
        (3, 1, 2, 4)
        >>> shuffled[1]
        ('iii', 'i', 'ii', 'iv')

        >>> shuffled = shuffle_together([10, 20, 30], ['a', 'b', 'c'], [True, False, True])
        >>> shuffled[0]
        (10, 30, 20)
        >>> shuffled[1]
        ('a', 'c', 'b')
        >>> shuffled[2]
        (True, True, False)
    """
    tmp = list(zip(*arrs))
    random.shuffle(tmp)
    return tuple(zip(*tmp))


def split_iter(
        it: Union[Iterator, Iterable, List],
        num_splits: int,
        use_tqdm=False,
        tqdm_msg=None
) -> List[List]:
    """
    Splits the items read from an iterator into a list of lists, where each nested list is a split
    of the input iterator.

    See :func:`split_list`.

    """
    return split_list(
        list_to_split=it if sliceable(it) else list(tqdm_wrap(it, use_tqdm, tqdm_msg)),
        num_splits_or_weights=num_splits
    )


def all__(_it, cond: Callable, atom_types=(str,)):
    if isinstance(_it, atom_types):
        return cond(_it)
    else:
        return all(cond(item) for item in _it)


def get_item_if_singleton(x):
    """
    If the size of the input can be measured by `len`,
            and the input contains a single item, then returns the single item;
        in particular, if the input is a mapping and contains a single key/value pair,
            then the single value will be returned.
    Otherwise, returns the input object itself.
    """
    if isinstance(x, Mapping):
        return next(iter(x.values())) if len(x) == 1 else x
    elif hasattr(x, '__len__'):
        return x[0] if len(x) == 1 else x
    else:
        return x


def tqdm_wrap(
        _it: Union[Iterable, Iterator],
        use_tqdm: bool,
        tqdm_msg: str = None,
        verbose: bool = __debug__
) -> Union[Iterator, Iterable]:
    """
    Wraps an iterator/iterable in a tadm object to display iteration progress.
    Args:
        _it: the iterator/iterable.
        use_tqdm: True to enable the tqdm wrap.
        tqdm_msg: the tqdm description to display along with the progress.
        verbose: if tqdm package somehow fails to load, and this argument is set True,
            then `tqdm_msg` will still be printed.

    Returns: a tqdm wrap of the input iterator/iterable if the tqdm package loads successfully;
        otherwise the input iterator/iterable.

    """
    if isinstance(use_tqdm, str):
        tqdm_msg = use_tqdm
        use_tqdm = bool(use_tqdm)

    try:
        from tqdm import tqdm
    except Exception as error:
        warnings.warn(f"unable to load tqdm package; got error '{error}'")
        tqdm = None
        use_tqdm = False

    if use_tqdm:
        _it = tqdm(_it)
        if tqdm_msg and verbose:
            _it.set_description(tqdm_msg)
    elif tqdm_msg and verbose:
        print(tqdm_msg)
    return _it

# endregion


# region Naming Helpers

def with_uuid(it, prefix='', suffix=''):
    yield from ((prefix + str(uuid.uuid4()) + suffix, x) for x in it)


def with_names(it, name_format: str = None, name_prefix='', name_suffix=''):
    if name_format is None or name_format == 'uuid':
        return with_uuid(it=it, prefix=name_prefix, suffix=name_suffix)
    else:
        for i, x in enumerate(it):
            yield name_prefix + name_format.format(i) + name_suffix, x

# endregion
