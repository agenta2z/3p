"""Typing helper utilities — extracted functions."""

from typing import Iterable, Iterator, List, Sequence, Tuple, Union


def iterable(_obj) -> bool:
    """
    Check whether an object can be iterated over.

    Examples:
        >>> assert iterable([1, 2, 3, 4])
        >>> assert iterable(iter(range(5)))
        >>> assert iterable('123')
        >>> assert not iterable(123)
    """
    if isinstance(_obj, (Iterable, Iterator, Sequence)):
        return True

    try:
        iter(_obj)
    except TypeError:
        return False
    return True


def iterable__(_obj, atom_types=(str,)):
    """
    A variant of `iterable` that considers types in `atom_types` as non-iterable.
    Returns `True` if the type of `obj` is not in the `atom_types`, and it is iterable.
    By default, the `atom_types` consists of the string type.

    Examples:
        >>> assert iterable__('123', atom_types=None)
        >>> assert not iterable__('123')
        >>> assert iterable__((1, 2, 3))
        >>> assert not iterable__((1, 2, 3), atom_types=(tuple, str))
    """
    return (
        # _obj is not any of atom_types if atom_types is specified
        (not (atom_types and isinstance(_obj, atom_types)))
        # and _obj itself is iterable
        and iterable(_obj)
    )


def of_type_any(_it, _type):
    """
    Checks if any element in the iterable is of the specified type.

    If the input is directly of the specified type (not iterable), it returns True.
    If the input is not iterable and not of the specified type, it returns False.

    Args:
        _it: The input object, which can be an iterable or a single object.
        _type: The type to check against.

    Returns:
        bool: True if at least one element (or the object itself) is of the specified type, False otherwise.

    Examples:
        >>> of_type_any([1, 2, 3], int)
        True
        >>> of_type_any([1, 2, '3'], str)
        True
        >>> of_type_any([1, 2, '3'], float)
        False
        >>> of_type_any([], int)  # An empty list always returns False
        False
        >>> of_type_any(42, int)  # Single object check
        True
        >>> of_type_any(42, str)  # Single object check
        False
    """
    if isinstance(_it, _type):
        return True
    if iterable(_it):
        return any(isinstance(item, _type) for item in _it)
    return False


def sliceable(_obj):
    """
    Checks whether an object can be sliced.

    Examples:
        >>> sliceable(2)
        False
        >>> sliceable(None)
        False
        >>> sliceable((1, 2, 3))
        True
        >>> sliceable('abc')
        True
        >>> sliceable([])
        True
    """
    if _obj is None:
        return False
    if not hasattr(_obj, "__getitem__"):
        return False
    try:
        _obj[0:1]
    except:
        return False
    return True


def solve_nested_singleton_tuple_list(x, atom_types=(str,)) -> Union[Tuple, List]:
    """
    Resolving nested singleton list/tuple. For example, resolving `[[0,1,2]]` as `[0,1,2]`.

    Examples:
        >>> solve_nested_singleton_tuple_list([[0, 1, 2]])
        [0, 1, 2]
        >>> solve_nested_singleton_tuple_list([[[0, 1, 2]]])
        [0, 1, 2]
        >>> solve_nested_singleton_tuple_list([0, 1, 2])
        [0, 1, 2]
        >>> solve_nested_singleton_tuple_list([([0, 1, 2],)])
        [0, 1, 2]
    """

    while isinstance(x, (list, tuple)):
        if len(x) == 1:
            x = x[0]
        else:
            return x

    # unpacks the element `x` as a tuple if it is considered iterable
    if iterable__(x, atom_types):
        return tuple(x)

    # otherwise, returns `x` as a singleton tuple
    return (x,)


def is_basic_type(_obj) -> bool:
    """
    Check whether an object is None, or a python int/float/str/bool.

    Examples:
        >>> is_basic_type(None)
        True
        >>> is_basic_type(42)
        True
        >>> is_basic_type("hello")
        True
        >>> is_basic_type([1, 2])
        False
    """
    if _obj is None:
        return True
    return isinstance(_obj, (int, float, str, bool))


def is_named_tuple(obj) -> bool:
    """
    Check whether an object is a named tuple.

    Examples:
        >>> from collections import namedtuple
        >>> Point = namedtuple('Point', ['x', 'y'])
        >>> is_named_tuple(Point(1, 2))
        True
        >>> is_named_tuple((1, 2))
        False
    """
    return isinstance(obj, tuple) and hasattr(obj, '_fields')
