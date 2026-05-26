import json
from ast import literal_eval
from collections.abc import Iterator
from typing import Mapping, Callable, Union, List, Tuple, ClassVar, Any, Optional, Set, Iterable, Sequence, TypeVar, \
    _BaseGenericAlias, Type, Dict


# region type checking

def is_str(_obj) -> bool:
    """
    Convenience function to check if an object is a string.

    Examples:
        >>> assert not is_str(None)
        >>> assert is_str('')
        >>> assert is_str('1')
        >>> assert not is_str(1)

    """
    return isinstance(_obj, str)


def is_none_or_empty_str(_obj) -> bool:
    """
    Checks if an object is None or an empty string.

    Examples:
        >>> assert is_none_or_empty_str(None)
        >>> assert is_none_or_empty_str('')
        >>> assert not is_none_or_empty_str('1')
        >>> assert not is_none_or_empty_str(1)

    """
    return _obj is None or (isinstance(_obj, str) and _obj == '')


def str_eq(s1, s2) -> bool:
    """
    Checks if two strings equal each other. `None` is considered equal to an empty string.

    Examples:
        >>> assert str_eq(None, None)
        >>> assert str_eq('', None)
        >>> assert str_eq(None, '')
        >>> assert str_eq('1', '1')
        >>> assert not str_eq('1', None)
        >>> assert not str_eq('1', 1)
    """
    if s1 is None:
        return is_none_or_empty_str(s2)
    if s2 is None:
        return is_none_or_empty_str(s1)
    return isinstance(s1, str) and isinstance(s2, str) and s1 == s2


def is_class(_obj) -> bool:
    """
    Check whether an object is a class.

    Examples:
        >>> assert not is_class(1)
        >>> assert is_class(int)
        >>> assert not is_class(List)
    """
    return isinstance(_obj, type)


def is_class_(_obj) -> bool:
    """
    Check whether an object is a class/type or a tuple/list of classes.

    Examples:
        >>> assert not is_class_((1, 2))
        >>> assert is_class_((list, int))
        >>> assert not is_class_((List, Tuple))
    """
    from python_utils.common_utils.iter_helper import iter_
    return all(isinstance(x, type) for x in iter_(_obj, non_atom_types=(tuple, list)))


TypeOrGenericAlias = Union[type, _BaseGenericAlias]


def is_class_or_type(_obj) -> bool:
    """
    Check whether an object is a class/type.

    Examples:
        >>> assert not is_class_or_type(1)
        >>> assert is_class_or_type(int)
        >>> assert is_class_or_type(List)
    """
    return isinstance(_obj, TypeOrGenericAlias)


def is_class_or_type_(_obj) -> bool:
    """
    Check whether an object is a class/type or a tuple/list of classes/types.

    Examples:
        >>> assert not is_class_or_type_((1, 2))
        >>> assert is_class_or_type_((List, Tuple))
    """
    from python_utils.common_utils.iter_helper import iter_
    return all(isinstance(x, TypeOrGenericAlias) for x in iter_(_obj, non_atom_types=(tuple, list)))


def is_basic_type(_obj) -> bool:
    """
    Check whether an object is None, or a python int/float/str/bool.

    Examples:
        >>> assert is_basic_type(1)
        >>> assert not is_basic_type([])
    """
    if _obj is None:
        return True
    return isinstance(_obj, (int, float, str, bool))


def is_basic_type_iterable(_obj, iterable_type=(list, tuple, set)):
    """
    Check whether an object is an iterable of python int/float/str/bool.
    If `iterable_type` is specified, then the iterable object itself must be of the specified type.

    Examples:
        >>> assert not is_basic_type_iterable(1)
        >>> assert is_basic_type_iterable([1,2,3,4])
        >>> assert is_basic_type_iterable(['1','2','3','4'])
        >>> assert not is_basic_type_iterable(['1','2','3','4'], iterable_type=tuple)
    """
    if iterable_type is None:
        return iterable__(_obj) and all(is_basic_type(x) for x in _obj)
    else:
        return isinstance(_obj, iterable_type) and all(is_basic_type(x) for x in _obj)


def is_basic_type_or_basic_type_iterable(_obj, iterable_type=(list, tuple, set)):
    """
    Check whether an object is a python int/float/str/bool,
    of if the object is an iterable of python int/float/str/bool.

    See Also :func:`is_basic_type` and :func:`is_basic_type_iterable`.

    """
    return is_basic_type(_obj) or is_basic_type_iterable(_obj, iterable_type=iterable_type)


def element_type(_container, atom_types=(str,), key=0):
    """
    Gets the type of an atomic element in the provided object container.
    The container may be nested, and we use `key` to
        recursively retrieve an atomic element inside container.

    When using this function, we usually assuem the elements in the container are of the same type,
    so the retrieved element type can represent the type of all elements in the container.

    Args:
        _container: the container holding values.
        atom_types: the types that should be treated as an atomic object.
        key: the key used to recursively retrieve the inside containers.
    Returns:
        the type of atomic element in the container.

    Examples:
        >>> assert element_type(((True, False), (True, False))) is bool
        >>> assert element_type([[['a', [0, 1, 2]], 'c']]) is str
        >>> assert element_type(['a', [0, 1, 2], 'c'], key=1) is int
    """

    try:
        while not isinstance(_container, atom_types):
            _container = _container[key]
    except:
        pass
    return type(_container)


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
    By default, the `atom_types` conssits of the string type.

    Examples:
        >>> assert iterable__('123', atom_types=None)
        >>> assert not iterable__('123')
        >>> assert iterable__((1, 2 ,3))
        >>> assert not iterable__((1, 2, 3), atom_types=(tuple,str))
    """
    return (
        # _obj is not any of atom_types if atom_types is specified
            (not (atom_types and isinstance(_obj, atom_types)))
            # and _obj itself is iterable
            and iterable(_obj)
    )


def nonstr_iterable(_obj) -> bool:
    """
    Checks whether the object is an iterable but is not a string.
    Equivalent to `iterable__(x, atom_types=(str,))`.

    >>> assert not nonstr_iterable('123')
    >>> assert nonstr_iterable([1,2,3])
    """
    return (not is_str(_obj)) and iterable(_obj)


def is_named_tuple(obj) -> bool:
    return isinstance(obj, tuple) and hasattr(obj, '_fields')


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
    if not hasattr(_obj, '__getitem__'):
        return False
    try:
        _obj[0:1]
    except:
        return False
    return True


def of_type_all(_it, _type):
    """
    Checks if every element in the iterable is of the specified type.

    If the input is directly of the specified type (not iterable), it returns True.
    If the input is not iterable and not of the specified type, it returns False.

    Args:
        _it: The input object, which can be an iterable or a single object.
        _type: The type to check against.

    Returns:
        bool: True if all elements (or the object itself) are of the specified type, False otherwise.

    Examples:
        >>> of_type_all([1, 2, 3], int)
        True
        >>> of_type_all([1, 2, '3'], int)
        False
        >>> of_type_all(['a', 'b', 'c'], str)
        True
        >>> of_type_all([], int)  # An empty list always returns True
        True
        >>> of_type_all(42, int)  # Single object check
        True
        >>> of_type_all(42, str)  # Single object check
        False
        >>> of_type_all(None, type(None))  # None is of type NoneType
        True
    """
    if isinstance(_it, _type):
        return True
    if iterable(_it):
        return all(isinstance(item, _type) for item in _it)
    return False


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
        >>> of_type_any(None, type(None))  # None is of type NoneType
        True
    """
    if isinstance(_it, _type):
        return True
    if iterable(_it):
        return any(isinstance(item, _type) for item in _it)
    return False


def all_str(_it):
    """
    Checks if every iterated object is a python string.

    Examples:
        >>> assert all_str(['1', '2', '3'])
        >>> assert not all_str([1, 2, '3'])
    """
    return of_type_all(_it, str)


# endregion

# region type conversion
def str_(x) -> str:
    """
    Converting an object to string using format.

    This function is particularly helpful for str Enum objects,
    returning the literal string value of the Enum.

    Examples:
        >>> from enum import Enum
        >>> class Opt(str, Enum):
        ...   A = 'a'
        ...   B = 'b'
        >>> print(str(Opt.A))
        Opt.A
        >>> print(str_(Opt.A))
        a

    """
    return '{}'.format(x)


def make_list(
        _x,
        atom_types=(str,),
        str_sep=None,
        ignore_none: bool = False,
        list_factory: Union[Type, Callable[[Optional[Iterable]], List]] = list
) -> List:
    """
    Converts an input object into a list based on the specified conditions.

    The function attempts to handle various input types and conditions:
    - If the input object (`_x`) is considered atomic (any type in `atom_types`),
      it is wrapped in a single-element list.
    - If `_x` is an iterable (but not atomic), it is converted to a list.
    - If `_x` is already of the type created by `list_factory`, it is returned as is.

    Special handling is provided for strings when `str_sep` is specified:
    - If `str_sep` is `True`, the string is split by whitespace into substrings,
      stripped of leading and trailing spaces.
    - If `str_sep` is any other value, the string is split by `str_sep`, and
      empty splits are ignored while substrings are stripped of leading and
      trailing spaces.

    Additional considerations:
    - If `ignore_none` is `True` and `_x` is `None`, the function returns `None`.
    - The `list_factory` parameter allows customization of the container type
      (default is Python's built-in `list`).

    Args:
        _x: The input object to be converted to a list.
        atom_types (tuple, optional): A tuple of types that are treated as atomic
            and not iterable. Defaults to `(str,)`.
        str_sep (Union[None, bool, str], optional): Determines how to handle strings:
            - `None` or `False`: Strings are treated as atomic and not split.
            - `True`: Strings are split by whitespace.
            - Any other string: Strings are split by the specified delimiter.
            Defaults to `None`.
        ignore_none (bool, optional): If `True`, returns `None` when `_x` is `None`.
            Defaults to `False`.
        list_factory (Union[Type, Callable[[Optional[Iterable]], List]], optional): A callable used to create the list.
            Defaults to the built-in `list`.

    Returns:
        List: A list representation of `_x`, or `None` if `ignore_none` is `True` and `_x` is `None`.

    Examples:
        >>> assert make_list(None) == [None]
        >>> assert make_list(None, ignore_none=True) is None
        >>> assert make_list(3) == [3]
        >>> assert make_list((1, 2, 3)) == [1, 2, 3]
        >>> assert make_list({1, 2, 3}) == [1, 2, 3]
        >>> assert make_list('123') == ['123']
        >>> assert make_list(('123', '456')) == ['123', '456']
        >>> assert make_list('123', atom_types=None) == ['1', '2', '3']
        >>> assert make_list('1 2 3', str_sep=True) == ['1', '2', '3']
        >>> assert make_list('1,2,3', str_sep=',') == ['1', '2', '3']
        >>> from collections import deque
        >>> assert make_list(3, list_factory=deque) == deque([3])

    Notes:
        - If `_x` is a string and `str_sep` is not specified, it is treated as atomic.
        - The `atom_types` parameter determines which types are not treated as iterable.
    """

    if (
            (str_sep is not None) and
            (str_sep is not False) and
            isinstance(_x, str)
    ):
        if str_sep is True:
            _x = _x.split()
        else:
            _x = (__x.strip() for __x in _x.split(str_sep))
        return list_factory(filter(None, _x))

    if ignore_none and _x is None:
        return None

    if is_class_or_type(list_factory) and isinstance(_x, list_factory):
        return _x
    if iterable__(_x, atom_types=atom_types):
        return list_factory(_x)
    else:
        _list = list_factory()
        _list.append(_x)
        return _list


def make_tuple(
        _x,
        atom_types=(str,),
        str_sep=None,
        ignore_none: bool = False,
        tuple_factory: Union[Type, Callable[[Iterable], Tuple]] = tuple
):
    """
    Converts an input object into a tuple based on the specified conditions.

    - If `_x` is a string and `str_sep` is specified, splits the string into substrings.
    - If `_x` is iterable (but not atomic), converts it to a tuple.
    - If `_x` is already a tuple, it is returned as is.
    - Otherwise, wraps `_x` in a single-element tuple.

    Args:
        _x: The input object to be converted to a tuple.
        atom_types (tuple, optional): A tuple of types that are treated as atomic
            and not iterable. Defaults to `(str,)`.
        str_sep (Union[None, bool, str], optional): Determines how to handle strings:
            - `None` or `False`: Strings are treated as atomic and not split.
            - `True`: Strings are split by whitespace.
            - Any other string: Strings are split by the specified delimiter.
            Defaults to `None`.
        ignore_none (bool, optional): If `True`, returns `None` when `_x` is `None`.
            Defaults to `False`.
        tuple_factory (Union[Type, Callable[[Iterable], Tuple]], optional): A callable used to create the tuple.
            Defaults to Python's built-in `tuple`.

    Returns:
        tuple: A tuple representation of `_x`, or `None` if `ignore_none` is `True`
        and `_x` is `None`.

    Examples:
        >>> assert make_tuple(None) == (None,)
        >>> assert make_tuple(None, ignore_none=True) is None
        >>> assert make_tuple(3) == (3,)
        >>> assert make_tuple((1, 2, 3)) == (1, 2, 3)
        >>> assert make_tuple({1, 2, 3}) == (1, 2, 3)
        >>> assert make_tuple('123') == ('123',)
        >>> assert make_tuple(('123', '456')) == ('123', '456')
        >>> assert make_tuple('123', atom_types=None) == ('1', '2', '3')
        >>> assert make_tuple('1 2 3', str_sep=True) == ('1', '2', '3')
        >>> assert make_tuple('1,2,3', str_sep=',') == ('1', '2', '3')
        >>> from collections import namedtuple
        >>> custom_tuple = namedtuple('CustomTuple', 'values')
        >>> assert make_tuple(3, tuple_factory=custom_tuple) == custom_tuple((3,))
    """
    if (
            (str_sep is not None) and
            (str_sep is not False) and
            isinstance(_x, str)
    ):
        if str_sep is True:
            _x = _x.split()
        else:
            _x = (__x.strip() for __x in _x.split(str_sep))
        return tuple_factory(filter(None, _x))

    if ignore_none and _x is None:
        return None

    if is_class_or_type(tuple_factory) and isinstance(_x, tuple_factory):
        return _x
    if iterable__(_x, atom_types=atom_types):
        return tuple_factory(_x)
    else:
        return tuple_factory((_x,))


def make_set(
        _x,
        atom_types=(str,),
        str_sep=None,
        ignore_none: bool = False,
        set_factory: Union[Type, Callable[[Iterable], Set]] = set
):
    """
    Converts an input object into a set based on the specified conditions.

    - If `_x` is a string and `str_sep` is specified, splits the string into substrings.
    - If `_x` is iterable (but not atomic), converts it to a set.
    - If `_x` is already a set, it is returned as is.
    - Otherwise, wraps `_x` in a single-element set.

    Args:
        _x: The input object to be converted to a set.
        atom_types (tuple, optional): A tuple of types that are treated as atomic
            and not iterable. Defaults to `(str,)`.
        str_sep (Union[None, bool, str], optional): Determines how to handle strings:
            - `None` or `False`: Strings are treated as atomic and not split.
            - `True`: Strings are split by whitespace.
            - Any other string: Strings are split by the specified delimiter.
            Defaults to `None`.
        ignore_none (bool, optional): If `True`, returns `None` when `_x` is `None`.
            Defaults to `False`.
        set_factory (Union[Type, Callable[[Iterable], Set]], optional): A callable used to create the set.
            Defaults to Python's built-in `set`.

    Returns:
        set: A set representation of `_x`, or `None` if `ignore_none` is `True`
        and `_x` is `None`.

    Examples:
        >>> assert make_set(None) == {None}
        >>> assert make_set(None, ignore_none=True) is None
        >>> assert make_set(3) == {3}
        >>> assert make_set((1, 2, 3)) == {1, 2, 3}
        >>> assert make_set({1, 2, 3}) == {1, 2, 3}
        >>> assert make_set('123') == {'123'}
        >>> assert make_set(('123', '456')) == {'123', '456'}
        >>> assert make_set(('123', '123')) == {'123'}
        >>> assert make_set('123', atom_types=None) == {'1', '2', '3'}
        >>> assert make_set('1 2 3', str_sep=True) == {'1', '2', '3'}
        >>> assert make_set('1,2,3', str_sep=',') == {'1', '2', '3'}
        >>> from collections import Counter
        >>> assert make_set([1, 1, 2], set_factory=Counter) == Counter({1: 2, 2: 1})
    """
    if (
            (str_sep is not None) and
            (str_sep is not False) and
            isinstance(_x, str)
    ):
        if str_sep is True:
            _x = _x.split()
        else:
            _x = (__x.strip() for __x in _x.split(str_sep))
        return set_factory(filter(None, _x))

    if ignore_none and _x is None:
        return None

    if is_class_or_type(set_factory) and isinstance(_x, set_factory):
        return _x
    if iterable__(_x, atom_types=atom_types):
        return set_factory(_x)
    else:
        return set_factory((_x,))


def make_list_(
        _x: Any,
        non_atom_types=(tuple, set),
        list_factory: Union[Type, Callable[[Optional[Iterable]], List]] = list
) -> List[Any]:
    """
    Converts the input object `_x` into a list using the specified conditions.

    - If `_x` is an instance of `non_atom_types` (tuple or set by default), it is
      converted into a list using `list_factory`.
    - If `_x` is already a list, it is returned as is.
    - Otherwise, `_x` is wrapped into a single-element list.

    Args:
        _x (Any): The input object to be converted.
        non_atom_types (tuple, optional): A tuple of types that should be treated as non-atomic
            and converted into a list. Defaults to `(tuple, set)`.
        list_factory (Callable[[Optional[Iterable]], List]], optional): A callable used to create the list.
            Defaults to Python's built-in `list`.

    Returns:
        List[Any]: A list representation of `_x`.

    Examples:
        >>> assert make_list_(3) == [3]
        >>> assert make_list_((1, 2, 3)) == [1, 2, 3]
        >>> assert make_list_({1, 2, 3}) == [1, 2, 3]
        >>> assert make_list_('123', non_atom_types=(str, tuple, set)) == ['1', '2', '3']
        >>> from collections import deque
        >>> assert make_list_(3, list_factory=deque) == deque([3])
    """
    if is_class_or_type(list_factory) and isinstance(_x, list_factory):
        return _x
    elif isinstance(_x, non_atom_types):
        return list_factory(_x)
    else:
        _list = list_factory()
        _list.append(_x)
        return _list


def make_list_if_not_none_(
        _x: Any,
        non_atom_types: Tuple[type, ...] = (tuple, set),
        list_factory: Union[Type, Callable[[Optional[Iterable]], List]] = list
) -> Optional[List[Any]]:
    """
    Converts the input object `_x` into a list, unless `_x` is `None`.

    - If `_x` is `None`, the function returns `None`.
    - Otherwise, the function delegates to :func:`make_list_` to convert `_x` into a list.

    Args:
        _x (Any): The input object to be converted.
        non_atom_types (tuple, optional): A tuple of types that should be treated as non-atomic
            and converted into a list. Defaults to `(tuple, set)`.
        list_factory (Callable[[Optional[Iterable]], List]], optional): A callable used to create the list.
            Defaults to Python's built-in `list`.

    Returns:
        Optional[List[Any]]: A list representation of `_x`, or `None` if `_x` is `None`.

    Examples:
        >>> make_list_if_not_none_(None)
        >>> make_list_if_not_none_(('a', 'b'))
        ['a', 'b']
        >>> make_list_if_not_none_({'a', 'b'}) in [['a', 'b'], ['b', 'a']]
        True
        >>> make_list_if_not_none_('a')
        ['a']
        >>> from collections import deque
        >>> assert make_list_if_not_none_(3, list_factory=deque) == deque([3])
    """
    if _x is None:
        return None
    return make_list_(_x, non_atom_types=non_atom_types, list_factory=list_factory)


def make_tuple_(
        _x,
        non_atom_types=(list, set),
        tuple_factory: Union[Type, Callable[[Iterable], Tuple]] = tuple
) -> Tuple:
    """
    Converts the input object `_x` into a tuple based on the specified conditions.

    - If `_x` is an instance of `non_atom_types` (list or set by default), it is
      converted into a tuple using `tuple_factory`.
    - If `_x` is already a tuple, it is returned as is.
    - Otherwise, `_x` is wrapped into a single-element tuple.

    Args:
        _x: The input object to be converted to a tuple.
        non_atom_types (tuple, optional): A tuple of types that should be treated as non-atomic
            and converted into a tuple. Defaults to `(list, set)`.
        tuple_factory (Union[Type, Callable[[Iterable], Tuple]], optional): A callable used to create the tuple.
            Defaults to Python's built-in `tuple`.

    Returns:
        tuple: A tuple representation of `_x`.

    Examples:
        >>> assert make_tuple_(3) == (3,)
        >>> assert make_tuple_([1, 2, 3]) == (1, 2, 3)
        >>> assert make_tuple_({1, 2, 3}) == (1, 2, 3)
        >>> assert make_tuple_('123', non_atom_types=(str, list, set)) == ('1', '2', '3')
        >>> from collections import namedtuple
        >>> custom_tuple = namedtuple('CustomTuple', 'values')
        >>> assert make_tuple_(3, tuple_factory=custom_tuple) == custom_tuple((3,))
    """
    if is_class_or_type(tuple_factory) and isinstance(_x, tuple_factory):
        return _x

    if isinstance(_x, non_atom_types):
        return tuple_factory(_x)
    else:
        return tuple_factory((_x,))


def make_set_(
        _x,
        non_atom_types=(tuple, list),
        set_factory: Union[Type, Callable[[Iterable], Set]] = set
) -> Set:
    """
    Converts the input object `_x` into a set based on the specified conditions.

    - If `_x` is an instance of `non_atom_types` (list or tuple by default), it is
      converted into a set using `set_factory`.
    - If `_x` is already a set, it is returned as is.
    - Otherwise, `_x` is wrapped into a single-element set.

    Args:
        _x: The input object to be converted to a set.
        non_atom_types (tuple, optional): A tuple of types that should be treated as non-atomic
            and converted into a set. Defaults to `(tuple, list)`.
        set_factory (Union[Type, Callable[[Iterable], Set]], optional): A callable used to create the set.
            Defaults to Python's built-in `set`.

    Returns:
        set: A set representation of `_x`.

    Examples:
        >>> assert make_set_(3) == {3}
        >>> assert make_set_([1, 2, 3]) == {1, 2, 3}
        >>> assert make_set_([1, 2, 2]) == {1, 2}
        >>> assert make_set_({1, 2, 3}) == {1, 2, 3}
        >>> assert make_set_('123', non_atom_types=(str, list, set)) == {'1', '2', '3'}
        >>> from collections import Counter
        >>> assert make_set_([1, 1, 2], set_factory=Counter) == Counter({1: 2, 2: 1})
    """
    if is_class_or_type(set_factory) and isinstance(_x, set_factory):
        return _x

    if isinstance(_x, non_atom_types):
        return set_factory(_x)
    else:
        return set_factory((_x,))


def get_iter(
        input_path_or_iterable: Union[str, Iterable],
        default_iterator: Optional[Callable] = None
) -> Iterable:
    """
    Obtain an iterator from the given input, which can be either a file path (string) or an iterable object.

    If `input_path_or_iterable` is a string and `default_iterator` is None, a built-in JSON iterator function
    (`iter_json_objs`) is used to read items from the specified file. If `default_iterator` is provided, it is called
    with the file path to produce the iterator.

    If `input_path_or_iterable` is already an iterable (e.g., a list), it is returned as is.

    Args:
        input_path_or_iterable (Union[str, Iterable]):
            The input to convert into an iterator. Can be:
            - A string representing a file path.
            - An iterable object.
        default_iterator (Optional[Callable[[str], Iterable]]):
            An optional function that, given a file path string, returns an iterator. If None and the input is a string,
            a default JSON iterator function is used.

    Returns:
        Iterable: An iterator derived from the input.

    Raises:
        ValueError: If the function cannot produce an iterator from the given input (e.g., if the `default_iterator`
                    does not return an iterable or the file format is unsupported).

    Examples:
        >>> import os, tempfile
        >>> from typing import List
        >>> from python_utils.io_utils.json_io import iter_json_objs

        >>> # Example with a file path and the default json iterator
        >>> with tempfile.NamedTemporaryFile('w', delete=False, suffix='.json') as tmp:
        ...     _ = tmp.write('[1, 2, 3]\\n[4, 5, 6]')
        ...     tmp_path = tmp.name
        >>> for item in get_iter(tmp_path):
        ...     print(item)
        [1, 2, 3]
        [4, 5, 6]
        >>> os.remove(tmp_path)

        >>> # Example with a custom iterator function
        >>> def custom_iterator(path: str):
        ...     # Custom logic: iterate over lines in the file
        ...     with open(path, 'r') as f:
        ...         for line in f:
        ...             yield line.strip()

        >>> with tempfile.NamedTemporaryFile('w', delete=False, suffix='.txt') as tmp:
        ...     _ = tmp.write('line1\\nline2\\nline3')
        ...     tmp_path2 = tmp.name
        >>> for line in get_iter(tmp_path2, custom_iterator):
        ...     print(line)
        line1
        line2
        line3
        >>> os.remove(tmp_path2)

        >>> # Example with an iterable object
        >>> data = [1, 2, 3, 4]
        >>> for item in get_iter(data):
        ...     print(item)
        1
        2
        3
        4
    """
    if isinstance(input_path_or_iterable, str):
        if default_iterator is None:
            from python_utils.io_utils.json_io import iter_json_objs
            return iter_json_objs(input_path_or_iterable)
        else:
            _iterable = default_iterator(input_path_or_iterable)
    else:
        _iterable = input_path_or_iterable

    if iterable(_iterable):
        return _iterable
    else:
        raise ValueError(f"Unable to obtain data iter from '{input_path_or_iterable}'")


def enumerate_(_x):
    try:
        return enumerate(_x)
    except:
        return enumerate((_x,))


_STRS_TRUE = {'true', 'yes', 'y', 'ok', '1'}
_STRS_FALSE = {'false', 'no', 'n', '0'}


def str2bool(s: str) -> Optional[bool]:
    """
    Converts a string to a boolean value.

    Args:
        s: The input string.

    Returns:
        The boolean value corresponding to the input string.
        If the string is one of 'true', 'yes', 'y', 'ok', or '1' (case-insensitive),
        the function returns True. Otherwise, it returns False.

    Examples:
        >>> str2bool("True")
        True

        >>> str2bool("No")
        False
    """
    s_lower = s.lower()
    if s_lower in _STRS_TRUE:
        return True
    elif s_lower in _STRS_FALSE:
        return False


def bool_(x) -> Optional[bool]:
    """
    Converts a value to a boolean.

    Args:
        x: The input value. It can be of any type.

    Returns:
        The boolean value corresponding to the input.
        If the input is a string, it will be converted using `str2bool()`.
        Otherwise, the input will be cast to a boolean.

    Examples:
        >>> bool_("yes")
        True

        >>> bool_(0)
        False
    """
    if isinstance(x, str):
        return str2bool(x)
    else:
        return bool(x)


# Type mapping for parsing type specification strings
TYPE_STR_TO_TYPE: Dict[str, Optional[type]] = {
    'str': str,
    'int': int,
    'float': float,
    'bool': bool,
    'any': None,  # None means no type coercion
}


def parse_type_string(type_str: str) -> Tuple[type, ...]:
    """
    Parse a type specification string into a tuple of Python types.

    Supports union types via pipe syntax: 'float|int' means try float first, then int.
    Types are tried in the order specified during coercion operations.

    Args:
        type_str: Type specification string (e.g., 'float', 'float|int', 'str|int|float')

    Returns:
        Tuple of Python types in order. Empty tuple if 'any' or if all types are invalid.

    Examples:
        >>> parse_type_string('float')
        (<class 'float'>,)
        >>> parse_type_string('float|int')
        (<class 'float'>, <class 'int'>)
        >>> parse_type_string('str|int|float')
        (<class 'str'>, <class 'int'>, <class 'float'>)
        >>> parse_type_string('any')
        ()
        >>> parse_type_string('')
        ()
        >>> parse_type_string('float|any|int')  # 'any' is skipped
        (<class 'float'>, <class 'int'>)
    """
    if not type_str:
        return ()

    types = []
    for part in type_str.split('|'):
        part = part.strip().lower()
        if part in TYPE_STR_TO_TYPE:
            py_type = TYPE_STR_TO_TYPE[part]
            if py_type is not None:
                types.append(py_type)
        # Skip unknown types silently

    return tuple(types)


def coerce_to_type(value: Any, type_tuple: Tuple[type, ...]) -> Any:
    """
    Coerce a value to one of the types in the tuple.

    Tries each type in order until successful. Returns the original value
    if the tuple is empty (no coercion) or if all conversions fail.

    Uses bool_() for boolean conversion to handle common string values like
    'true', 'yes', 'y', 'ok', '1' for True and 'false', 'no', 'n', '0' for False.

    Args:
        value: The value to coerce.
        type_tuple: Tuple of Python types to try, in order.

    Returns:
        The coerced value, or the original value if coercion fails.

    Examples:
        >>> coerce_to_type('2.5', (float,))
        2.5
        >>> coerce_to_type('2', (float, int))
        2.0
        >>> coerce_to_type(2, (float,))
        2.0
        >>> coerce_to_type('hello', (int,))  # Conversion fails, returns original
        'hello'
        >>> coerce_to_type('true', (bool,))
        True
        >>> coerce_to_type('yes', (bool,))
        True
        >>> coerce_to_type('1', (bool,))
        True
        >>> coerce_to_type('false', (bool,))
        False
        >>> coerce_to_type('no', (bool,))
        False
        >>> coerce_to_type('0', (bool,))
        False
        >>> coerce_to_type(42, ())  # Empty tuple, no coercion
        42
    """
    if not type_tuple:
        return value

    for target_type in type_tuple:
        try:
            if target_type == bool:
                # Use bool_() for boolean conversion to handle string values
                result = bool_(value)
                if result is not None:
                    return result
                # bool_() returns None for unrecognized strings, try next type
                continue
            else:
                return target_type(value)
        except (ValueError, TypeError):
            continue

    # All conversions failed, return original value
    return value


def map_iterable_elements(
        _iterable,
        _converter: Callable,
        atom_types=(str,)
):
    """
    Maps every elements in the provided iterable by applying the converter.
    Elements of type `atom_types` will not be treated as iterables.

    Examples:
        >>> map_iterable_elements([1, 2, 3], str)
        ['1', '2', '3']
        >>> map_iterable_elements('123', int)
        123
        >>> map_iterable_elements(
        ...    [{(1,2), (3,4)}, [[1, 2]], '123'], tuple, atom_types=(str, set)
        ... )
        [((1, 2), (3, 4)), [(1, 2)], ('1', '2', '3')]

    """
    try:
        if atom_types and isinstance(_iterable, atom_types):
            return _converter(_iterable)
        else:
            return type(_iterable)(
                map_iterable_elements(x, _converter, atom_types=atom_types)
                for x in _iterable
            )
    except:
        pass
    return _converter(_iterable)


def str2val_(s: str, str_format: Union[str, Callable[[str], str]] = None, success_label=False):
    """
    Parses a string as its likely equivalent value.
    Typically tries to convert to integers, floats, bools, lists, tuples, dictionaries.

    Args:
        s: the string to parse as a value.
        str_format: a formatting string,
            or a callable that takes a string and outputs a processed string.
        success_label: returns a tuple, with the first being the parsed value,
                and the second being a boolean value indicating if the the parse is successful.

    Returns: the parsed value if `success_label` is `False`,
        or a tuple with the second being the parse success flag if `success_label` is `True`.

    Examples:
        >>> assert str2val_('1') == 1
        >>> assert str2val_('2.554') == 2.554
        >>> assert str2val_("[1, 2, 'a', 'b', False]") == [1, 2, 'a', 'b', False]
        >>> assert str2val_("1, 2, 'a', 'b', False", str_format='[{}]') == [1, 2, 'a', 'b', False]
    """
    ss = s.strip()
    if not ss:
        return ss

    if str_format:
        if is_str(str_format):
            ss = str_format.format(ss)
        elif callable(str_format):
            ss = str_format(ss)
            if not is_str(ss):
                raise ValueError(f"'str_format' must outputs a string; got {ss}")
        else:
            raise ValueError("'str_format' must be a formatting string "
                             "or a callable that takes a string and outputs a processed string; "
                             f"got {str_format}")

    if success_label:
        def _literal_eval():
            try:
                return literal_eval(ss), True
            except:  # noqa: E722
                return s, False

        if ss[0] == '{':
            try:
                return json.loads(ss), True
            except:  # noqa: E722
                return _literal_eval()
        elif ss[0] == '[' or ss[0] == '(':
            return _literal_eval()
        else:
            try:
                return int(ss), True
            except:  # noqa: E722
                try:
                    return float(ss), True
                except:  # noqa: E722
                    sl = ss.lower()
                    if sl in _STRS_TRUE:
                        return True, True
                    elif sl in _STRS_FALSE:
                        return False, True
                    else:
                        try:
                            return literal_eval(ss), True
                        except:  # noqa: E722
                            return s, False
    else:
        def _literal_eval():
            try:
                return literal_eval(ss)
            except:  # noqa: E722
                return s

        if ss[0] == '{':
            try:
                return json.loads(ss)
            except:  # noqa: E722
                return _literal_eval()
        elif ss[0] == '[' or ss[0] == '(':
            return _literal_eval()
        else:
            try:
                return int(ss)
            except:  # noqa: E722
                try:
                    return float(ss)
                except:  # noqa: E722
                    sl = ss.lower()
                    if sl in _STRS_TRUE:
                        return True
                    elif sl in _STRS_FALSE:
                        return False
                    else:
                        try:
                            return literal_eval(ss)
                        except:  # noqa: E722
                            return s


def solve_obj(
        _input: Union[str, Mapping, List, Tuple, Any],
        obj_type: ClassVar = None,
        str2obj: Callable = str2val_,
        str_format: str = None,
):
    """
    Solves a string, Mapping, list or tuple as an object.

    Args:
        _input: the input, must be a string, Mapping, list or tuple.
            1. if this is a string, then `str2obj` is used to convert the input.
            2. if this is a Mapping or a tuple or a list,
                then `obj_type` is used to create the object,
                assuming the mapping consists of named arguments for the `obj_type`,
                or the tuple/list consists of arguments for the `obj_type`;
            3. otherwise, try parsing the input as `obj_type`
                assuming it is the sole argument for `obj_type`.
        obj_type: a class variable used to create object from a Mapping, list, or tuple.
        str2obj: a callable to convert a string input as the object; by default we use `str2val_`.
        str_format: providers a format as the second argument of `str2obj` if necessary.

    Returns: the parsed object.

    Examples:
        >>> assert solve_obj('1') == 1
        >>> assert solve_obj('2.554') == 2.554
        >>> assert solve_obj("[1, 2, 'a', 'b', False]") == [1, 2, 'a', 'b', False]
        >>> assert solve_obj("1, 2, 'a', 'b', False", str_format='[{}]') == [1, 2, 'a', 'b', False]

        >>> class A:
        ...    __slots__ = ('a', 'b')
        ...    def __init__(self, a, b):
        ...        self.a = a
        ...        self.b = b
        >>> obj = solve_obj("(1,2)", A)
        >>> obj.a
        1
        >>> obj.b
        2
        >>> obj = solve_obj("{'a': 2, 'b': 1}", A)
        >>> obj.a
        2
        >>> obj.b
        1
    """
    _ori_input = _input
    if isinstance(_input, str):
        if str2obj is None:
            raise ValueError("'str2obj' must be provided to parse a string input")
        if not callable(str2obj):
            raise ValueError(f"'str2obj' must be a callable; got {type(str2obj)}")

        obj = str2obj(_input) if str_format is None else str2obj(_input, str_format)
        if obj_type is None or isinstance(obj, obj_type):
            return obj
        else:
            _input = obj

    if obj_type is None:
        raise ValueError("'obj_type' must be provided to parse a non-string input")
    if not callable(obj_type):
        raise ValueError(f"the 'obj_type' must be a callable; got {type(obj_type)}")
    if isinstance(_input, Mapping):
        return obj_type(**_input)
    elif isinstance(_input, (list, tuple)):
        return obj_type(*_input)
    elif is_class(obj_type) and isinstance(_input, obj_type):
        return _input
    else:
        try:
            return obj_type(_input)
        except:  # noqa: E722
            raise ValueError(f"cannot parse '{_ori_input}' as {obj_type}")


def extract_single_element_if_singleton(x: Sequence, atom_types=(str,)) -> Union[Tuple, List]:
    if (not isinstance(x, atom_types)) and isinstance(x, Sequence) and len(x) == 1:
        return x[0]
    return x


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
    return x,


def solve_atom(x, atom_types=(str,), raise_error_if_cannot_resolve_an_atom: bool = False):
    """
    Resolves an atomic object from the given input, potentially nested in singleton lists or tuples.

    Args:
        x (Any): The input object, potentially nested in singleton lists or tuples.
        atom_types (Tuple[type]): A tuple of types considered as atomic objects (default: (str,)).
        raise_error_if_cannot_resolve_an_atom (bool): If True, raises a ValueError when the function
            cannot resolve an atomic object from the input (default: False).

    Returns:
        Any: The resolved atomic object, or the original input if it cannot be resolved.

    Examples:
        >>> solve_atom([[[[1]]]])
        1
        >>> solve_atom((("a",)))
        'a'
        >>> solve_atom([[[1, 2]]])
        [1, 2]
        >>> solve_atom("abc", atom_types=(str,))
        'abc'
        >>> solve_atom("abc", atom_types=(int,))
        ('a', 'b', 'c')
    """
    _x = solve_nested_singleton_tuple_list(x, atom_types=atom_types)
    if isinstance(_x, (list, tuple)) and len(_x) == 1:
        return _x[0]
    else:
        if raise_error_if_cannot_resolve_an_atom:
            raise ValueError(f"cannot resolve an atomic object from '{x}'")
        else:
            return _x


def solve_key_value_pairs(*kvs, parse_seq_as_alternating_key_value: bool = True):
    """
    Solves the input argument(s) as a sequence of key-value pairs. The input can be
        1. a single Mapping; then it returns an iterator through the items in the mapping;
        2. a list/tuple of 2-tuples;
        3. a sequence of elements; if :param:`parse_seq_as_alternating_key_value` is True,
            then the item at the position of even index as the key,
            and the following item at the position of odd index as the value;
            otherwise each element in the sequence will be duplicated as a tuple.

    This function does not perform thorough error checking; and if all parsing fails,
    the original input is returned.

    Examples:
        >>> solve_key_value_pairs()
        ()
        >>> solve_key_value_pairs(None)
        ()
        >>> solve_key_value_pairs(())
        ()
        >>> solve_key_value_pairs('a')
        (('a', 'a'),)
        >>> solve_key_value_pairs({'a': 1, 'b': 2})
        dict_items([('a', 1), ('b', 2)])
        >>> solve_key_value_pairs([{'a': 1, 'b': 2}])
        dict_items([('a', 1), ('b', 2)])
        >>> solve_key_value_pairs(('a', 1), ('b', 2))
        (('a', 1), ('b', 2))
        >>> tuple(solve_key_value_pairs(
        ...   'a', 1,
        ...   'b', 2
        ... ))
        (('a', 1), ('b', 2))
        >>> tuple(solve_key_value_pairs(
        ...   'a', 1,
        ...   'b', 2,
        ...   parse_seq_as_alternating_key_value=False
        ... ))
        (('a', 'a'), (1, 1), ('b', 'b'), (2, 2))
    """
    if len(kvs) == 1:
        # when a single object is passed in
        if kvs[0] is None:
            return ()  # when a single None is passed in
        elif isinstance(kvs[0], Mapping):
            return kvs[0].items()  # when a single mapping is passed in
        elif iterable__(kvs[0]):
            return solve_key_value_pairs(
                *kvs[0],
                parse_seq_as_alternating_key_value=parse_seq_as_alternating_key_value
            )  # recursively resolve the single iterable object
        else:
            # resolve the single non-iterable object as a tuple
            return (kvs[0], kvs[0]),
    elif isinstance(kvs, (list, tuple)) and kvs:
        if isinstance(kvs[0], (list, tuple)) and len(kvs[0]) == 2:
            return kvs  # assume it is a list of 2-tuples
        else:
            if parse_seq_as_alternating_key_value:
                # assume it is a sequence of items, with the item at the even position as the key,
                # and the following item at the odd position as the value
                def _it(_kvs):
                    for i in range(0, len(_kvs), 2):
                        if i + 1 < len(_kvs):
                            yield _kvs[i], _kvs[i + 1]
                        else:
                            # Handle odd number of arguments - pair last key with empty string
                            yield _kvs[i], ""

                return _it(kvs)
            else:
                # otherwise, each element as both key and value
                return ((x, x) for x in kvs)

    return kvs


# endregion

def all_of_same_type(items: Sequence[Any]) -> bool:
    """
    Checks if all elements in a sequence are of the same type.

    Args:
        items: The sequence of elements to check.

    Returns:
        True if all elements are of the same type or the sequence is empty; False otherwise.

    Examples:
        >>> all_of_same_type([1, 2, 3])
        True
        >>> all_of_same_type([1, '2', 3])
        False
        >>> all_of_same_type((1.0, 2.0, 3.0))
        True
        >>> all_of_same_type([])
        True
        >>> all_of_same_type(['hello', 'world', 'test'])
        True
        >>> all_of_same_type(['hello', 'world', 3])
        False
        >>> all_of_same_type([1, 2, 3, 4.5])
        False
        >>> all_of_same_type([{'a': 1}, {'b': 2}])
        True
        >>> all_of_same_type([1, 2, [3]])
        False
    """
    if not items:
        return True
    first_type = type(next(iter(items)))
    return all(isinstance(item, first_type) for item in items)


def create_child(
    parent,
    child_class,
    always_inherit: Sequence[str] = None,
    attr_name_mapping: dict[str, str] = None,
    **inherit_flags_and_kwargs
):
    """
    Create a child instance from a parent object with flexible attribute inheritance.

    This is a general utility that creates child instances while inheriting specified
    attributes from the parent. It separates inheritance flags (inherit_*) from
    constructor kwargs and applies attribute name mapping if needed.

    Args:
        parent: The parent object to inherit attributes from
        child_class: The class to instantiate for the child
        always_inherit: Sequence of attribute names to always inherit from parent
        attr_name_mapping: Optional dict to rename inherited attributes (e.g., {'full_path': 'parent_path'})
        **inherit_flags_and_kwargs: Mixed kwargs containing:
            - inherit_<attr_name>=bool flags for conditional inheritance
            - Other kwargs passed directly to child_class constructor

    Returns:
        Instance of child_class with inherited and provided attributes

    Examples:
        Basic inheritance with always_inherit:
        >>> class Config:
        ...     def __init__(self, name, version=None, debug=False):
        ...         self.name = name
        ...         self.version = version
        ...         self.debug = debug
        >>> parent_config = Config(name="parent", version="1.0", debug=True)
        >>> child_config = create_child(
        ...     parent_config, Config,
        ...     always_inherit=['version'],
        ...     name="child"
        ... )
        >>> child_config.name
        'child'
        >>> child_config.version
        '1.0'
        >>> child_config.debug
        False

        Conditional inheritance with inherit_* flags:
        >>> child_config2 = create_child(
        ...     parent_config, Config,
        ...     inherit_version=True,
        ...     inherit_debug=True,
        ...     name="child2"
        ... )
        >>> child_config2.version
        '1.0'
        >>> child_config2.debug
        True

        Attribute name mapping:
        >>> class Node:
        ...     def __init__(self, node_id, parent_id=None, path=None):
        ...         self.node_id = node_id
        ...         self.parent_id = parent_id
        ...         self.path = path if path else node_id
        ...         self.full_path = f"{parent_id}/{path}" if parent_id else path
        >>> parent_node = Node(node_id="root", path="root")
        >>> child_node = create_child(
        ...     parent_node, Node,
        ...     always_inherit=['full_path'],
        ...     attr_name_mapping={'full_path': 'parent_id'},
        ...     node_id="child",
        ...     path="child"
        ... )
        >>> child_node.parent_id
        'root'
        >>> child_node.full_path
        'root/child'

        Combined usage - always_inherit, inherit_* flags, and attr_name_mapping:
        >>> class Task:
        ...     def __init__(self, task_id, parent_task_id=None, config=None, priority=5):
        ...         self.task_id = task_id
        ...         self.parent_task_id = parent_task_id
        ...         self.config = config
        ...         self.priority = priority
        >>> parent_task = Task(task_id="main", config={"timeout": 30}, priority=10)
        >>> child_task = create_child(
        ...     parent_task, Task,
        ...     always_inherit=['task_id'],
        ...     attr_name_mapping={'task_id': 'parent_task_id'},
        ...     inherit_config=True,
        ...     task_id="subtask"
        ... )
        >>> child_task.task_id
        'subtask'
        >>> child_task.parent_task_id
        'main'
        >>> child_task.config
        {'timeout': 30}
        >>> child_task.priority
        5
    """
    # Collect all attribute names to inherit
    attrs_to_inherit = list(always_inherit) if always_inherit else []

    # Separate inherit_flags from regular kwargs and collect conditional attributes
    kwargs = {}

    for key, value in inherit_flags_and_kwargs.items():
        if key.startswith('inherit_'):
            # Extract attribute name and check if it's not already in kwargs
            attr_name = key[8:]  # Remove 'inherit_' prefix
            # Only inherit if the attribute is not explicitly provided in kwargs
            if value and attr_name not in inherit_flags_and_kwargs:
                attrs_to_inherit.append(attr_name)
        else:
            kwargs[key] = value

    # Get inherited attributes from parent using get_multiple
    if attrs_to_inherit:
        from python_utils.common_utils.map_helper import get_multiple
        inherited_attrs = get_multiple(
            parent,
            *attrs_to_inherit,
            unpack_result_for_single_key=False
        )
    else:
        inherited_attrs = {}

    # Apply attribute name mapping if provided
    if attr_name_mapping:
        for old_name, new_name in attr_name_mapping.items():
            if old_name in inherited_attrs:
                inherited_attrs[new_name] = inherited_attrs.pop(old_name)

    # Merge inherited attributes with provided kwargs
    child_kwargs: dict[str, Any] = {
        **inherited_attrs,
        **kwargs
    }

    return child_class(**child_kwargs)
