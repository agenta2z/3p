import copy
from collections import defaultdict
from contextlib import contextmanager
from enum import Enum
from functools import partial
from itertools import islice
from typing import (
    Any,
    Callable,
    Counter,
    Dict,
    Iterable,
    Iterator,
    List,
    Mapping,
    Optional,
    Sequence,
    Set,
    Tuple,
    Type,
    Union,
)

from python_utils.common_utils import unpack_single_value
from python_utils.common_utils.iter_helper import (
    flatten_iter,
    iter_,
    product__,
    tqdm_wrap,
)
from python_utils.common_utils.typing_helper import (
    is_basic_type,
    is_named_tuple,
    is_str,
    iterable__,
    nonstr_iterable,
    solve_key_value_pairs,
)
from python_utils.string_utils.prefix_suffix import (
    add_prefix_suffix,
    remove_prefix_suffix,
)


# region MISSING sentinel


class _MISSING_TYPE:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self):
        return '<MISSING>'

    def __bool__(self):
        return False


MISSING = _MISSING_TYPE()

# endregion


class map_as_callable:
    """
    Encapsulates a mapping (e.g., dictionary) into a callable object.

    Attributes:
        mapping (dict): The mapping used for key-value lookup.
        default: The default value to return if the key is not found.

    Methods:
        __call__(key):
            Returns the value associated with the key or the default value if the key is not found.

    Examples:
        >>> mapping = {'a': 1, 'b': 2, 'c': 3}
        >>> callable_mapping = map_as_callable(mapping, default="Not Found")
        >>> callable_mapping('a')
        1
        >>> callable_mapping('d')
        'Not Found'
        >>> callable_mapping('b')
        2
    """

    def __init__(self, mapping: Mapping, default=None):
        """
        Initializes the MapAsCallable object.

        Args:
            mapping (Mapping): The mapping to use as a callable.
            default: The default value to return if the key is not found.
        """
        self.mapping = mapping
        self.default = default

    def __call__(self, key):
        """
        Makes the object callable, performing key lookup in the mapping.

        Args:
            key: The key to look up in the mapping.

        Returns:
            The value associated with the key, or the default value if the key is not found.
        """
        return self.mapping.get(key, self.default)


def dict_(
    seq: Union[Sequence, Mapping],
    ignore_none_keys: bool = True,
    ignore_none_values: bool = False,
    keys_to_remove: Union[Iterable, Callable] = None,
    key_transformation: Union[Callable, Mapping] = None,
    **kwargs,
) -> dict:
    """
    Converts a sequence, mapping, or an attrs class instance to a dictionary, with options
    for key deletion, ignoring None keys/values, and key transformation.

    This function processes an input (sequence, mapping, or attrs class) and applies optional
    filters, transformations, and updates to generate a dictionary. It supports:
    1. Ignoring entries with None keys or values (before or after transformation).
    2. Deleting specified keys via a list or callable.
    3. Applying transformations to keys using a callable or mapping.

    Args:
        seq (Union[Sequence, Mapping, attr.s]): The input to convert to a dictionary.
        ignore_none_keys (bool, optional): If True, ignore entries where the key is None,
            including after key transformation. Defaults to True.
        ignore_none_values (bool, optional): If True, ignore entries where the value is None.
            Defaults to False.
        keys_to_remove (Union[Iterable, Callable], optional): Keys to remove from the resulting
            dictionary. Can be a list of keys or a function that returns True for keys to delete.
            Defaults to None.
        key_transformation (Union[Callable, Mapping], optional): A function or mapping to
            transform dictionary keys. Defaults to None.
        **kwargs: Additional key-value pairs to add to the resulting dictionary.

    Returns:
        dict: A processed dictionary with specified transformations and filters applied.

    Examples:
        # Ignore None keys (before and after transformation)
        >>> dict_({None: 1, 'a': 2, 'b': 3}, ignore_none_keys=True)
        {'a': 2, 'b': 3}

        >>> dict_({None: 1, 'a': 2, 'b': 3}, ignore_none_keys=False)
        {None: 1, 'a': 2, 'b': 3}

        # Ignore None keys after transformation
        >>> dict_({'a': 1, 'b': 2, None: 3}, ignore_none_keys=True, key_transformation=str.upper)
        {'A': 1, 'B': 2}

        # Using an attrs class instance with specified key deletion
        >>> import attr
        >>> @attr.s(slots=True)
        ... class CommonLlmInferenceArgs:
        ...     temperature: float = attr.ib(default=0.1)
        ...     max_tokens: int = attr.ib(default=500)
        ...     top_p: float = attr.ib(default=0.9)
        ...     top_k: int = attr.ib(default=50)
        ...     stop_sequences: List[str] = attr.ib(default=[])
        >>> args = CommonLlmInferenceArgs(
        ...     temperature=0.7,
        ...     max_tokens=150,
        ...     top_p=0.95,
        ...     top_k=40,
        ...     stop_sequences=['\\n', '']
        ... )
        >>> dict_(args, keys_to_remove=['top_p'])
        {'temperature': 0.7, 'max_tokens': 150, 'top_k': 40, 'stop_sequences': ['\\n', '']}

        # Ignore None values
        >>> dict_({'a': 1, 'b': 2, 'c': None}, ignore_none_values=True)
        {'a': 1, 'b': 2}

        # Combine ignore_none_keys, ignore_none_values, and transformation
        >>> dict_({None: 1, 'a': None, 'b': 2}, ignore_none_keys=True, ignore_none_values=True, key_transformation=str.upper)
        {'B': 2}

        # Apply key transformation using a mapping
        >>> dict_({'a': 1, 'b': 2, 'c': 3}, key_transformation={'a': 'alpha', 'b': 'beta', 'c': 'gamma'})
        {'alpha': 1, 'beta': 2, 'gamma': 3}

        # Mapping a key to None to remove
        >>> dict_({'a': 1, 'b': 2, 'c': 3}, key_transformation={'a': 'alpha', 'b': 'beta', 'c': None})
        {'alpha': 1, 'beta': 2}
    """
    if not seq:
        d = dict()
    elif isinstance(seq, Mapping):
        d = dict(seq)
    elif hasattr(seq, "to_dict") and callable(seq.to_dict):
        d = seq.to_dict()
    else:
        import attr

        if attr.has(type(seq)):
            d = attr.asdict(seq)
        else:
            d = dict(seq)

    d.update(kwargs)

    # Apply key transformation
    if key_transformation:
        if isinstance(key_transformation, Mapping):
            key_transformation = map_as_callable(key_transformation)

        if ignore_none_keys:
            _d = {}
            for k, v in d.items():
                try:
                    _k = key_transformation(k)
                except Exception as err:
                    if k is None:
                        _k = None
                    else:
                        raise err
                _d[_k] = v
            d = _d
        else:
            d = {key_transformation(k): v for k, v in d.items()}

    # Filter output dict by null values and `keys_to_remove`
    if keys_to_remove:
        if callable(keys_to_remove):
            d = {
                k: v
                for k, v in d.items()
                if (
                    (ignore_none_keys is False or k is not None)
                    and (ignore_none_values is False or v is not None)
                    and (not keys_to_remove(k))
                )
            }
        else:
            d = {
                k: v
                for k, v in d.items()
                if (
                    (ignore_none_keys is False or k is not None)
                    and (ignore_none_values is False or v is not None)
                    and (k not in keys_to_remove)
                )
            }
    else:
        if ignore_none_keys:
            if ignore_none_values:
                d = {k: v for k, v in d.items() if k is not None and v is not None}
            else:
                d = {k: v for k, v in d.items() if k is not None}
        elif ignore_none_values:
            d = {k: v for k, v in d.items() if v is not None}

    return d


def dict__(
    obj: Any,
    recursive: bool = True,
    fallback: Union[Callable, None, str] = str,
    _obj_cache: Dict[int, Any] = None
) -> Any:
    """
    Recursively converts any Python object to a dictionary, handling various types and
    supporting circular references.

    Args:
        obj: The object to convert to a dictionary.
        recursive: If True, recursively convert nested objects.
        fallback: Behavior for non-convertible objects:
            - Callable (e.g., str): Call fallback(obj) and return result (default)
            - None: Raise TypeError for non-convertible objects
            - 'skip': Return None for non-convertible objects
        _obj_cache: Internal parameter to keep track of already processed objects to handle circular references.

    Returns:
        A dictionary representation of the object.
    
    Raises:
        TypeError: If fallback=None and object cannot be converted to dict.

    Example:
        # Basic types
        >>> dict__(42)
        42
        >>> dict__("hello")
        'hello'
        >>> dict__(True)
        True

        # List of basic types
        >>> dict__([1, 2, 3])
        [1, 2, 3]

        # Nested list
        >>> dict__([1, [2, [3, 4]]])
        [1, [2, [3, 4]]]

        # Dictionary
        >>> dict__({'a': 1, 'b': 2})
        {'a': 1, 'b': 2}

        # Set (converted to list)
        >>> dict__({1, 2, 3})
        [1, 2, 3]

        # Tuple (converted to list)
        >>> dict__((1, 2, 3))
        [1, 2, 3]

        # Named tuple
        >>> from collections import namedtuple
        >>> Point = namedtuple('Point', ['x', 'y'])
        >>> p = Point(10, 20)
        >>> dict__(p)
        {'x': 10, 'y': 20}

        # Nested dictionary
        >>> nested_dict = {'a': 1, 'b': {'c': 2, 'd': {'e': 3}}}
        >>> dict__(nested_dict)
        {'a': 1, 'b': {'c': 2, 'd': {'e': 3}}}

        # Nested dictionary with recursive=False
        >>> dict__(nested_dict, recursive=False)
        {'a': 1, 'b': {'c': 2, 'd': {'e': 3}}}

        # Object with __dict__
        >>> class Person:
        ...     def __init__(self, name, age):
        ...         self.name = name
        ...         self.age = age
        >>> alice = Person("Alice", 30)
        >>> dict__(alice)
        {'name': 'Alice', 'age': 30}

        # Object with __slots__
        >>> class SlottedPerson:
        ...     __slots__ = ['name', 'age']
        ...     def __init__(self, name, age):
        ...         self.name = name
        ...         self.age = age
        >>> bob = SlottedPerson("Bob", 25)
        >>> dict__(bob)
        {'name': 'Bob', 'age': 25}

        # attrs class
        >>> import attr
        >>> @attr.s
        ... class Product:
        ...     name = attr.ib()
        ...     price = attr.ib()
        >>> prod = Product(name="Widget", price=19.99)
        >>> dict__(prod)
        {'name': 'Widget', 'price': 19.99}

        # Object with custom iterable
        >>> class CustomIterable:
        ...     def __init__(self, items):
        ...         self.items = items
        ...     def __iter__(self):
        ...         return iter(self.items)
        >>> ci = CustomIterable([1, 2, 3])
        >>> dict__(ci)
        [1, 2, 3]

        # Object with properties
        >>> class WithProperties:
        ...     def __init__(self):
        ...         self._value = 10
        ...     @property
        ...     def value(self):
        ...         return self._value
        >>> wp = WithProperties()
        >>> dict__(wp)
        {'_value': 10}

        # Object with reference to another object
        >>> class Node:
        ...     def __init__(self, value):
        ...         self.value = value
        ...         self.next = None
        >>> node1 = Node(1)
        >>> node2 = Node(2)
        >>> node1.next = node2 # Circular reference
        >>> result = dict__(node1)
        >>> result
        {'value': 1, 'next': {'value': 2, 'next': None}}

        # Complex object with nested structures
        >>> class Company:
        ...     def __init__(self, name, employees):
        ...         self.name = name
        ...         self.employees = employees
        >>> company = Company("TechCorp", [alice, bob])
        >>> dict__(company)
        {'name': 'TechCorp', 'employees': [{'name': 'Alice', 'age': 30}, {'name': 'Bob', 'age': 25}]}

        # Object with a list of dictionaries
        >>> data = {'items': [{'id': 1}, {'id': 2}]}
        >>> dict__(data)
        {'items': [{'id': 1}, {'id': 2}]}

        # Object with a list of dictionaries and recursive=False
        >>> dict__(data, recursive=False)
        {'items': [{'id': 1}, {'id': 2}]}
    """
    # Base cases for basic types
    if is_basic_type(obj):
        return obj

    # Handle Enums
    if isinstance(obj, Enum):
        return str(obj)

    # Handle bytes
    if isinstance(obj, bytes):
        return obj.decode(errors="replace")

    if _obj_cache is None:
        _obj_cache = {}
    obj_id = id(obj)

    # Handle circular references
    if obj_id in _obj_cache:
        return _obj_cache[obj_id]

    # Handle named tuples
    if is_named_tuple(obj):
        result = _obj_cache[obj_id] = {}
        if recursive:
            for key in obj._fields:
                value = getattr(obj, key)
                result[key] = dict__(value, fallback=fallback, _obj_cache=_obj_cache)
        else:
            for key in obj._fields:
                result[key] = getattr(obj, key)
        return result

    # Handle mappings (e.g., dict)
    if isinstance(obj, Mapping):
        key_values = []
        all_keys_str = True
        if recursive:
            for k, v in obj.items():
                key = dict__(k, fallback=fallback, _obj_cache=_obj_cache)
                value = dict__(v, fallback=fallback, _obj_cache=_obj_cache)
                key_values.append((key, value))
                if not isinstance(key, str):
                    all_keys_str = False
        else:
            for key, value in obj.items():
                key_values.append((key, value))
                if not isinstance(key, str):
                    all_keys_str = False

        if all_keys_str:
            result = dict(key_values)
        else:
            result = [{"key": key, "value": value} for key, value in key_values]
        _obj_cache[obj_id] = result
        return result

    # Handle sequences
    if isinstance(obj, Sequence) or iterable__(obj):
        if recursive:
            result = [
                dict__(item, recursive=True, fallback=fallback, _obj_cache=_obj_cache) for item in obj
            ]
        else:
            result = list(obj)
        _obj_cache[obj_id] = result
        return result

    # Handle attrs instances
    try:
        import attr

        if attr.has(obj):
            try:
                result = attr.asdict(obj)
            except RecursionError:
                # Circular references in attrs objects (e.g. graph nodes with next/previous)
                result = repr(obj)
                _obj_cache[obj_id] = result
                return result
            if recursive:
                # Use a fresh cache for the intermediate attr.asdict() dict to avoid
                # stale _obj_cache entries: the intermediate dict can be GC'd after
                # reassignment, and Python may reuse its memory address for the next
                # attr.asdict() call, causing id() collisions in the shared cache.
                result = dict__(result, recursive=True, fallback=fallback, _obj_cache={})
            _obj_cache[obj_id] = result
            return result
    except ImportError:
        pass

    # Handle objects with __dict__
    if hasattr(obj, "__dict__"):
        result = vars(obj)
        if recursive:
            result = dict__(result, recursive=True, fallback=fallback, _obj_cache=_obj_cache)
        _obj_cache[obj_id] = result
        return result

    # Handle objects with __slots__
    if hasattr(obj, "__slots__"):
        result = _obj_cache[obj_id] = {}
        if recursive:
            for slot in obj.__slots__:
                value = getattr(obj, slot, None)
                result[slot] = dict__(value, fallback=fallback, _obj_cache=_obj_cache)
        else:
            for slot in obj.__slots__:
                result[slot] = getattr(obj, slot, None)
        return result

    # Fallback for non-convertible objects
    if fallback is None:
        raise TypeError(f"Cannot convert {type(obj).__name__} to dict")
    elif fallback == 'skip':
        return None
    elif callable(fallback):
        return fallback(obj)
    else:
        return str(obj)


def has_single_key(d: Mapping, key: Any = None) -> bool:
    """
    Checks if a dictionary has only one key, and optionally if it matches a specified key.

    Args:
        d (Mapping): The dictionary to check.
        key (Any, optional): If provided, checks if the single key in the dictionary matches this key.

    Returns:
        bool: True if the dictionary has only one key and, if `key` is provided, it matches that key. False otherwise.

    Examples:
        >>> has_single_key({'name': 'Alice'})
        True

        >>> has_single_key({'name': 'Alice', 'age': 30})
        False

        >>> has_single_key({'name': 'Alice'}, key='name')
        True

        >>> has_single_key({'name': 'Alice'}, key='age')
        False

        >>> has_single_key({})
        False
    """
    is_single_key_dict = isinstance(d, Mapping) and len(d) == 1
    if key is None:
        return is_single_key_dict
    else:
        return is_single_key_dict and next(iter(d.keys())) == key


def split_dict(
    d: Dict, keys: Sequence = None, reverse: bool = False
) -> Tuple[Dict, Dict]:
    """
    Split the dictionary `d` into two dictionaries (d1, d2) based on a sequence of keys.

    By default (reverse=False):
      - d1 will contain all items from `d` whose keys are in `keys`.
      - d2 will contain all remaining items.

    If reverse=True, the behavior is inverted:
      - d1 will contain all items from `d` whose keys are *not* in `keys`.
      - d2 will contain all items from `d` whose keys are in `keys`.

    Args:
        d (Dict):
            The input dictionary to be split.
        keys (Sequence, optional):
            The set of keys used for splitting. Defaults to None (which is treated as empty).
        reverse (bool, optional):
            If True, invert which items go into the first dictionary. Defaults to False.

    Returns:
        Tuple[Dict, Dict]:
            A tuple (d1, d2) of two dictionaries, partitioned by membership in `keys`.

    Examples:
        >>> d = {'a': 1, 'b': 2, 'c': 3}
        >>> split_dict(d, keys=['a', 'c'])
        ({'a': 1, 'c': 3}, {'b': 2})

        >>> split_dict(d, keys=['a', 'c'], reverse=True)
        ({'b': 2}, {'a': 1, 'c': 3})
    """
    if keys is None:
        keys = []

    if not reverse:
        d1 = {k: v for k, v in d.items() if k in keys}
        d2 = {k: v for k, v in d.items() if k not in keys}
    else:
        d1 = {k: v for k, v in d.items() if k not in keys}
        d2 = {k: v for k, v in d.items() if k in keys}

    return d1, d2


@contextmanager
def temporary_value(d: Dict, key: Any, value: Any):
    _replace = False
    _old_value = None

    try:
        if key in d:
            _replace = True
            _old_value = d[key]
            d[key] = value
        else:
            d[key] = value
        yield
    finally:
        if _replace:
            d[key] = _old_value
        else:
            del d[key]


@contextmanager
def use_namespace(
    d: Dict, namespace, sep="_", namespace_essential_keys: Iterable[str] = None
):
    """

    Args:
        d:
        namespace:
        sep:

    Returns:
    Examples:
        >>> d = {'key1': 1, 'key2': 2, 'key3': 3, 'x_key1': -1, 'x_key3': -3}
        >>> with use_namespace(d, 'x'):
        ...    print(d)
        {'key1': -1, 'key2': 2, 'key3': -3}
        >>> with use_namespace(d, 'x', namespace_essential_keys=(['key2', 'key4'])):
        ...    print(d)
        {'key1': -1, 'key3': -3, 'key2': None, 'key4': None}

        >>> print(d)
        {'x_key1': -1, 'key1': 1, 'x_key3': -3, 'key3': 3, 'key2': 2}

    """
    if sep and namespace[-1] != sep:
        namespace += sep
    _changed_key_values = {}
    _delete = set()
    _update = {}
    try:
        for k, v in d.items():
            if k.startswith(namespace):
                _changed_key_values[k] = v
                _k = k[len(namespace) :]
                if _k in d:
                    _changed_key_values[_k] = d[_k]
                _update[_k] = v
                _delete.add(k)
        for k in iter_(namespace_essential_keys):
            if k in d:
                _changed_key_values[k] = d[k]
                _delete.add(k)
            _update[k] = None

        for k in _delete:
            del d[k]
        d.update(_update)
        _update = tuple(_update.keys())
        yield
    finally:
        for k in _update:
            del d[k]
        d.update(_changed_key_values)


def _exchange_values(d: Dict, key_map: Tuple, tmp_keys: set):
    for k1, k2 in key_map:
        if k1 not in d:
            d[k1] = None
            tmp_keys.add(k1)
        if k2 not in d:
            d[k2] = None
            tmp_keys.add(k2)
        d[k1], d[k2] = d[k2], d[k1]


@contextmanager
def key_value_exchanged(d: Dict, *key_map):
    """

    Args:
        d:
        *key_map:

    Returns:

    Examples:
        >>> d = {'key1': 1, 'key2': 2, 'key3': 3}
        >>> with key_value_exchanged(d, {'key1': 'key3'}):
        ...    print(d)
        {'key1': 3, 'key2': 2, 'key3': 1}
        >>> print(d)
        {'key1': 1, 'key2': 2, 'key3': 3}
        >>> with key_value_exchanged(d, {'key1': 'key4'}):
        ...    print(d)
        {'key1': None, 'key2': 2, 'key3': 3, 'key4': 1}
        >>> print(d)
        {'key1': 1, 'key2': 2, 'key3': 3}
        >>> with key_value_exchanged(d, {'key1': 'key4'}):
        ...    d['key4'] = 4
        ...    print(d)
        {'key1': None, 'key2': 2, 'key3': 3, 'key4': 4}
        >>> print(d)
        {'key1': 4, 'key2': 2, 'key3': 3}
        >>> d = {'key1': 1, 'key2': 2, 'key3': 3}
        >>> with key_value_exchanged(d, {'key1': 'key4'}):
        ...    d['key1'] = 4
        ...    print(d)
        {'key1': 4, 'key2': 2, 'key3': 3, 'key4': 1}
        >>> print(d)
        {'key1': 1, 'key2': 2, 'key3': 3, 'key4': 4}
    """
    key_map = tuple(solve_key_value_pairs(*key_map))
    tmp_keys = set()
    try:
        _exchange_values(d=d, key_map=key_map, tmp_keys=tmp_keys)
        yield
    finally:
        for k1, k2 in key_map:
            d[k1], d[k2] = d[k2], d[k1]
        for k in tmp_keys:
            if d[k] is None:
                del d[k]


def key_prefix_removed(d: Dict, prefix: str, prefix_sep: str = "_"):
    """
    A context manager that temporarily removes the specified prefixes from keys  of the dictionary.
    Args:
        d:
        prefix:
        prefix_sep:
    Returns:

    Examples:
        >>> d = {'key1': 1, 'new_key1': 2, 'new_key2': 3}
        >>> with key_prefix_removed(d, 'new'):
        ...    print(d)
        {'key1': 2, 'new_key1': 1, 'new_key2': None, 'key2': 3}
        >>> print(d)
        {'key1': 1, 'new_key1': 2, 'new_key2': 3}
        >>> with key_prefix_removed(d, 'new'):
        ...    d['key1'] = 4
        ...    print(d)
        {'key1': 4, 'new_key1': 1, 'new_key2': None, 'key2': 3}
        >>> print(d)
        {'key1': 1, 'new_key1': 4, 'new_key2': 3}
        >>> d = {'key1': 1, 'new_key1': 2, 'new_key2': 3}
        >>> with key_prefix_removed(d, 'new'):
        ...    d['new_key2'] = 4
        ...    print(d)
        {'key1': 2, 'new_key1': 1, 'new_key2': 4, 'key2': 3}
        >>> print(d)
        {'key1': 1, 'new_key1': 2, 'new_key2': 3, 'key2': 4}
    """
    key_map = {
        remove_prefix_suffix(k, prefixes=prefix, sep=prefix_sep): k
        for k in d
        if k.startswith(prefix)
    }
    return key_value_exchanged(d, key_map)


def get_category_dict(
    arr: Iterable, categorization: Union[Callable, str] = len
) -> Dict[Any, List]:
    """
    Categorizes an iterable into a category dictionary.
    Args:
        arr: the iterable.
        categorization: an attribute of each element of `arr` whose value can be used as the
            category label, or a function to extract a category label from each element of `arr`.

    Returns: a dictionary mapping category labels to elements under the category.

    Examples:
        >>> get_category_dict([(1, 2), (3, 4), (5, 6, 7)])
        defaultdict(<class 'list'>, {2: [(1, 2), (3, 4)], 3: [(5, 6, 7)]})

    """
    categories = defaultdict(list)
    for x in arr:
        categories[
            getattr(x, categorization) if is_str(categorization) else categorization(x)
        ].append(x)
    return categories


def get_keys(d: Union[Mapping, Any]) -> Iterable:
    """
    Gets keys from an object. If the object is a Mapping, we return its keys,
    otherwise we return the keys of `__dict__` of that object.

    Examples:
        >>> args = { 'arg1': '1', 'arg2': '2' }
        >>> tuple(get_keys(args))
        ('arg1', 'arg2')
        >>> from argparse import Namespace
        >>> args = Namespace(**args)
        >>> tuple(get_keys(args))
        ('arg1', 'arg2')
    """

    if isinstance(d, Mapping):
        return d.keys()
    else:
        return d.__dict__.keys()


# region value fetching
def _get_(d: Union[Mapping, Any], key: Union[Callable, Any]):
    if callable(key):
        return key(d)
    else:
        if isinstance(d, Mapping):
            if key in d:
                return d[key]
            elif isinstance(key, Enum):
                key = key.value
                return d[key]
        elif isinstance(d, Sequence):
            if isinstance(key, Enum) and isinstance(key.value, int):
                return d[key.value]
            elif isinstance(key, int):
                return d[key]

        if isinstance(key, Enum):
            key = f"{key}"
        return getattr(d, key)


def get_(
    d: Union[Mapping, Sequence, Any],
    key1: Union[Callable, Any],
    key2: Union[Callable, Any] = None,
    default: Any = None,
    raise_key_error: bool = False,
) -> Any:
    """
    Fetches a value from a mapping, a sequence, or an attribute from an object, with two possible keys `key1`
    or `key2`. This function first tries `key1`, and if unsuccessful, tries `key2`. The keys can be
    either direct references in the mapping/object or callable functions that process the mapping/object.

    Args:
        d (Union[Mapping, Sequence, Any]): The mapping to retrieve a value from, or a sequence to retrieve an item from, or an object to retrieve an attribute from.
        key1 (Union[Callable, Any]): The first key or a callable to try.
        key2 (Union[Callable, Any], optional): The alternative or fallback key or a callable to try.
        default (Any, optional): Returns this default value if both `key1` and `key2` do not exist, and `raise_key_error` is set to False.
        raise_key_error (bool, optional): True to raise a KeyError if both `key1` or `key2` do not exist, and in this case the `default` will be ignored.

    Returns:
        Any: A value retrieved from the mapping, sequence, or object by `key1` or `key2`, or the default if both fail.

    Examples:
        >>> d = {'a': 1, 'b': 2, 'c': 3}
        >>> get_(d, 'a', 'b')
        1
        >>> get_(d, 'x', 'y', default=0)
        0
        >>> get_(d, lambda x: x.get('a') * 2, 'b')
        2
        >>> get_(d, lambda x: x['z'], lambda x: x.get('b') * 2, default=-1)
        4
        >>> get_([10, 20, 30], 1)
        20
        >>> get_([10, 20, 30], 3, default=99)
        99
        >>> get_([10, 20, 30], '1', raise_key_error=True)
        Traceback (most recent call last):
            ...
        KeyError: "Key '1' is not valid"

        # Property access examples
        >>> class MyClass:
        ...     def __init__(self, val):
        ...         self._value = val
        ...     @property
        ...     def value(self):
        ...         return self._value
        ...     @property
        ...     def doubled(self):
        ...         return self._value * 2
        >>> obj = MyClass(42)
        >>> get_(obj, 'value')
        42
        >>> get_(obj, 'missing_attr', 'value')
        42
        >>> get_(obj, 'missing', 'doubled')
        84
        >>> get_(obj, 'nonexistent', default='default_value')
        'default_value'
        >>> get_(obj, lambda o: o.value + 10, 'doubled')
        52
    """
    if d is None:
        return default

    try:
        return _get_(d, key1)
    except (KeyError, AttributeError, IndexError):
        if key2 is not None:
            try:
                return _get_(d, key2)
            except (KeyError, AttributeError, IndexError):
                pass

    if raise_key_error:
        if key2 is not None:
            raise KeyError(f"Neither key '{key1}' nor key '{key2}' are valid")
        else:
            raise KeyError(f"Key '{key1}' is not valid")
    return default


def _get__for_mapping(d, keys, default, raise_key_error, return_hit_key):
    # `non_atom_types` cannot have "Tuple", because a "Tuple" object can also be a key
    for key in flatten_iter(keys, non_atom_types=(List,)):
        if key in d:
            value = d[key]
            if return_hit_key:
                return key, value
            else:
                return value
        elif isinstance(key, Enum) and key.value in d:
            key = key.value
            value = d[key]
            if return_hit_key:
                return key, value
            else:
                return value

    if raise_key_error:
        raise KeyError(f"None of the keys '{keys}' exist")

    if return_hit_key:
        return key, default
    else:
        return default


def _get__for_non_mapping(d, keys, default, raise_key_error, return_hit_key):
    for key in flatten_iter(keys, non_atom_types=(List,)):
        if isinstance(d, Sequence):
            if isinstance(key, Enum) and isinstance(key.value, int):
                key = key.value
                try:
                    value = d[key]
                except IndexError:
                    continue
                if return_hit_key:
                    return key, value
                else:
                    return value
            elif isinstance(key, int):
                try:
                    value = d[key]
                except IndexError:
                    continue
                if return_hit_key:
                    return key, value
                else:
                    return value
        else:
            if isinstance(key, Enum) and isinstance(key.value, str):
                key = key.value
            if hasattr(d, key):
                value = getattr(d, key)
                if return_hit_key:
                    return key, value
                else:
                    return value
    if raise_key_error:
        raise KeyError(f"None of the keys '{keys}' are valid")
    return default


def get__(
    d: Union[Mapping, Sequence, Any],
    *keys,
    default=None,
    raise_key_error: bool = False,
    return_hit_key: bool = False,
):
    """
    Fetches value from a mapping, a sequence, or an attribute from an object,
    with multiple possible keys specified in `keys`. This function tries
    the specified keys in order.

    Args:
        d (Union[Mapping, Sequence, Any]): The mapping to retrieve a value from, the sequence to retrieve an item from, or the object to retrieve an attribute from.
        keys: The keys to try.
        default (Any, optional): Returns this default value if all `keys` do not exist in the mapping, sequence, or object, and `raise_key_error` is set to False.
        raise_key_error (bool, optional): True to raise a KeyError if all `keys` do not exist, and in this case the `default` will be ignored.
        return_hit_key (bool, optional): If True, returns a tuple (key, value) where key is the key or attribute that resulted in a successful value retrieval.

    Returns:
        Any: A value retrieved from the mapping, sequence, or object by one of the `keys`, or the default if none found.
        If `return_hit_key` is True, returns a tuple of (key, value).

    Examples:
        Example 1: Using a dictionary to retrieve a value by key
        >>> data = {'name': 'Alice', 'age': 30}
        >>> get__(data, 'name')
        'Alice'

        Example 2: Using the same dictionary, trying multiple keys where one exists
        >>> get__(data, 'gender', 'age')
        30
        >>> get__(data, ['gender', 'age'])
        30
        >>> get__(data, ['gender', 'age'], return_hit_key=True)
        ('age', 30)
        >>> get__(data, ('gender', 'age'), raise_key_error=True)
        Traceback (most recent call last):
        ...
        KeyError: "None of the keys '[('gender', 'age')]' exist"

        Example 3: Using default value when none of the keys are present
        >>> get__(data, 'gender', default='Unknown')
        'Unknown'

        Example 4: Raising a KeyError when keys are not found, and raise_key_error is True
        >>> get__(data, 'gender', raise_key_error=True)
        Traceback (most recent call last):
        ...
        KeyError: "None of the keys '['gender']' exist"

        Example 5: Fetching an attribute from an object
        >>> class Person:
        ...     def __init__(self, name, age):
        ...         self.name = name
        ...         self.age = age
        ...
        >>> person = Person('Bob', 40)
        >>> get__(person, 'name')
        'Bob'

        Example 6: Using multiple keys to fetch the first existing attribute from an object
        >>> get__(person, 'gender', 'age')
        40
        >>> get__(person, ['gender', 'age'])
        40
        >>> get__(person, ['gender', 'age'], return_hit_key=True)
        ('age', 40)
        >>> get__(person, ('gender', 'age'))
        Traceback (most recent call last):
        ...
        TypeError: attribute name must be string, not 'tuple'


        Example 7: Using a list to retrieve a value by index
        >>> data = [10, 20, 30]
        >>> get__(data, 1)
        20

        Example 8: Using the same list, trying multiple keys where one exists
        >>> get__(data, 3, 2)
        30
        >>> get__(data, [3, 2])
        30
        >>> get__(data, [3, 2], return_hit_key=True)
        (2, 30)
        >>> get__(data, ('3', '2'), raise_key_error=True)
        Traceback (most recent call last):
        ...
        KeyError: "None of the keys '[('3', '2')]' are valid"

        Example 9: Using default value when none of the keys are present in the list
        >>> get__(data, 3, default=99)
        99

    """
    keys = list(keys)
    if isinstance(d, Mapping):
        return _get__for_mapping(d, keys, default, raise_key_error, return_hit_key)
    else:
        return _get__for_non_mapping(d, keys, default, raise_key_error, return_hit_key)


def _get_multiple(
    d: Union[Mapping, Sequence, Any], keys, default=None, raise_key_error: bool = False
):
    result = {}
    if isinstance(d, Mapping):
        for key in keys:
            if isinstance(key, Sequence):
                _key, value = _get__for_mapping(d, key, default, raise_key_error, True)
                result[_key] = value
            else:
                if key in d:
                    result[key] = d[key]
                elif raise_key_error:
                    raise KeyError(f"Key '{key}' is not valid")
                else:
                    result[key] = default
    else:
        if isinstance(d, Sequence):
            all_keys_int = True
            for key in keys:
                if isinstance(key, Sequence):
                    _key, value = _get__for_non_mapping(
                        d, key, default, raise_key_error, True
                    )
                    result[_key] = value
                    if not isinstance(_key, int):
                        all_keys_int = False
                else:
                    if isinstance(key, int):
                        try:
                            result[key] = d[key]
                        except IndexError:
                            raise KeyError(f"Key '{key}' is not valid")
                    else:
                        all_keys_int = False
                        if hasattr(d, key):
                            result[key] = getattr(d, key)
                        elif raise_key_error:
                            raise KeyError(f"Key '{key}' is not valid")
                        else:
                            result[key] = default
            if all_keys_int:
                result = list(result.values())
        else:
            for key in keys:
                if isinstance(key, Sequence):
                    _key, value = _get__for_non_mapping(
                        d, key, default, raise_key_error, True
                    )
                    result[_key] = value
                else:
                    if hasattr(d, key):
                        result[key] = getattr(d, key)
                    elif raise_key_error:
                        raise KeyError(f"Key '{key}' is not valid")
                    else:
                        result[key] = default
    return result


def get_multiple(
    d: Union[Mapping, Sequence, Any],
    *keys,
    default=None,
    raise_key_error: bool = False,
    unpack_result_for_single_key: bool = True,
):
    """
    Retrieves values from a mapping, sequence, or object attributes based on given keys. This function
    can fetch values for multiple keys and optionally unpack the result if only one key is provided.
    If a key is not found, it can return a default value or raise an error.

    Args:
        d (Union[Mapping, Sequence, Any]): The mapping, sequence, or object from which to retrieve values.
        *keys: A variable number of keys or attributes to attempt to retrieve.
        default (Any, optional): The default value to return if a key is not found and `raise_key_error` is False.
        raise_key_error (bool, optional): If True, raises a KeyError when none of the keys are found. Default is False.
        unpack_result_for_single_key (bool, optional): If True and only one key is provided, returns the value directly
            rather than in a dictionary. Default is True.

    Returns:
        Any: If `unpack_result_for_single_key` is True and one key is given, returns the single value directly.
        Otherwise, returns a dictionary of keys and their corresponding values. If keys are not found,
        it returns the `default` value or raises a KeyError based on `raise_key_error`.

    Examples:
        >>> d = {'key1': 1, 'key2': 2, 'key3': 3}
        >>> get_multiple(d, 'key1')
        1
        >>> get_multiple(d, 'key1', unpack_result_for_single_key=False)
        {'key1': 1}
        >>> get_multiple(d, 'key1', 'key2')
        {'key1': 1, 'key2': 2}
        >>> get_multiple(d, 'key4', default='Not found')
        'Not found'
        >>> get_multiple(d, 'key1', 'key4', default='Not found')
        {'key1': 1, 'key4': 'Not found'}
        >>> get_multiple(d, 'key4', raise_key_error=True)
        Traceback (most recent call last):
        ...
        KeyError: "None of the keys '['key4']' exist"

        >>> data = [10, 20, 30]
        >>> get_multiple(data, 1)
        20
        >>> get_multiple(data, 1, 2)
        [20, 30]
    """
    if unpack_result_for_single_key and len(keys) == 1:
        return get__(d, keys[0], default=default, raise_key_error=raise_key_error)
    return _get_multiple(
        d=d, keys=keys, default=default, raise_key_error=raise_key_error
    )


def _get_by_index(
    d: Union[Mapping, Any],
    index: Union[int, Any],
    default: Any = None,
    raise_key_error: bool = False,
) -> Any:
    try:
        return d[index]
    except IndexError as err:
        if raise_key_error:
            raise err
        return default


def get_by_index_or_key(
    d: Union[Mapping, Any],
    index_or_key: Union[int, Any],
    default: Any = None,
    raise_key_error: bool = False,
    indexed_types: Union[Type, Tuple[Type, ...]] = None,
) -> Any:
    """
    Retrieves a value from a given data structure by index or key. This function is flexible
    and can handle various types of data structures such as lists, tuples, dictionaries, or
    other types specified in `indexed_types`.

    Args:
        d: The input data structure, which can be a list, tuple, dictionary, or any other type
           that supports indexing.
        index_or_key: The index (if `d` is a sequence) or key (if `d` is a mapping) used to retrieve the value.
        default: The default value to return if the index or key is not found and `raise_key_error` is False.
        raise_key_error: If True, raises a KeyError when the specified index or key is not found
                         instead of returning `default`.
        indexed_types: Optional tuple of additional types that support indexing to be handled by the function.

    Returns:
        The retrieved value from the input data structure. If the index or key is not found,
        it returns `default` unless `raise_key_error` is set to True, in which case a KeyError is raised.

    Examples:
        >>> get_by_index_or_key([1, 2, 3, 4], 0)
        1
        >>> get_by_index_or_key((10, 20, 30), 1)
        20
        >>> d = {'key1': 1, 'key2': 2, 'key3': 3}
        >>> get_by_index_or_key(d, 'key1')
        1
        >>> get_by_index_or_key(d, 'key4', default='Not Found')
        'Not Found'
        >>> get_by_index_or_key(d, 'key4', raise_key_error=True)
        Traceback (most recent call last):
        ...
        KeyError: "None of the keys '['key4']' exist"
        >>> get_by_index_or_key('hello', 0)
        'h'
        >>> get_by_index_or_key('hello', 5, default='Not in range')
        'Not in range'
    """
    if isinstance(d, Sequence) or (
        bool(indexed_types) and isinstance(d, indexed_types)
    ):
        return _get_by_index(
            d=d, index=index_or_key, default=default, raise_key_error=raise_key_error
        )
    else:
        return get_multiple(
            d, index_or_key, default=default, raise_key_error=raise_key_error
        )


def get_multiple_by_indexes_or_keys(
    d: Union[Mapping, Any],
    *indexes_or_keys: Union[int, Any],
    default: Any = None,
    raise_key_error: bool = False,
    unpack_result_for_single_key: bool = True,
    indexed_types: Union[Type, Tuple[Type]] = None,
) -> Any:
    """
    Retrieves values from a given data structure by multiple indexes or keys, handling both collections
    and objects with attribute access. This function is capable of returning multiple values and can handle
    errors or return a default value if specified keys or indexes are not found.

    Args:
        d: The input data structure, which can be a list, tuple, dictionary, or any other type that supports indexing.
        *indexes_or_keys: Variable number of indexes or keys used to retrieve the values.
        default: The default value to return if an index or key is not found and `raise_key_error` is False.
        raise_key_error: If True, a KeyError or IndexError will be raised for the first missing index or key.
        unpack_result_for_single_key: If True and there is only one index_or_key, return the value directly
                                      rather than in a collection.
        indexed_types: Optional tuple of additional types that support indexing, to handle custom or less common types.

    Returns:
        If `unpack_result_for_single_key` is True and only one index_or_key is specified, the single value directly.
        Otherwise, returns a list, tuple, or dictionary (depending on the type of `d`) containing the retrieved values.
        If an index or key is not found, it returns `default` for that position unless `raise_key_error` is True.

    Examples:
        >>> get_multiple_by_indexes_or_keys([1, 2, 3, 4], 0, 3)
        [1, 4]
        >>> get_multiple_by_indexes_or_keys((10, 20, 30, 40), 1, 3)
        (20, 40)
        >>> d = {'key1': 1, 'key2': 2, 'key3': 3}
        >>> get_multiple_by_indexes_or_keys(d, 'key1', 'key2')
        {'key1': 1, 'key2': 2}
        >>> get_multiple_by_indexes_or_keys(d, 'key4', default='Not Found')
        'Not Found'
        >>> get_multiple_by_indexes_or_keys(d, 'key1', 'key4', default='Not Found')
        {'key1': 1, 'key4': 'Not Found'}
        >>> get_multiple_by_indexes_or_keys('hello', 0, 4)
        ['h', 'o']
        >>> get_multiple_by_indexes_or_keys('hello', 0, 5, default='Not in range')
        ['h', 'Not in range']
        >>> get_multiple_by_indexes_or_keys([1, 2, 3], 0, raise_key_error=True)
        1
    """
    if unpack_result_for_single_key and len(indexes_or_keys) == 1:
        return get_by_index_or_key(
            d=d,
            index_or_key=indexes_or_keys[0],
            default=default,
            raise_key_error=raise_key_error,
        )
    elif isinstance(d, tuple) or (
        indexed_types is not None and isinstance(d, indexed_types)
    ):
        return tuple(
            _get_by_index(d, i, default=default, raise_key_error=raise_key_error)
            for i in indexes_or_keys
        )
    elif isinstance(d, Sequence):
        return [
            _get_by_index(d, i, default=default, raise_key_error=raise_key_error)
            for i in indexes_or_keys
        ]
    else:
        return _get_multiple(
            d=d, keys=indexes_or_keys, default=default, raise_key_error=raise_key_error
        )


def get_by_spaced_key(
    d: Mapping,
    space_key: Optional[str] = None,
    item_key: Optional[str] = None,
    default_item_key: Optional[str] = "default",
) -> Optional[Any]:
    """
    Resolves a hierarchical/spaced key in a nested mapping structure and retrieves
    a value with optional fallback to a default key.

    This function performs 2-level lookup in a nested dictionary:
    1. Navigate to a space using `space_key` (optional hierarchical path)
    2. Lookup `item_key` in that space with fallback to `default_item_key`

    Args:
        d: The mapping to search in
        space_key: Optional hierarchical key to navigate to a subspace (e.g., "action_agent/main")
        item_key: The key to look for in the space (e.g., "BrowseLink")
        default_item_key: Fallback key to use if item_key not found (default: "default")

    Returns:
        The value found, or None if not found

    Examples:
        Basic usage with space_key:
        >>> templates = {
        ...     "action_agent/main": {
        ...         "BrowseLink": "Template for BrowseLink",
        ...         "default": "Default main template"
        ...     }
        ... }
        >>> get_by_spaced_key(templates, "action_agent/main", "BrowseLink")
        'Template for BrowseLink'

        Fallback to default when item not found:
        >>> get_by_spaced_key(templates, "action_agent/main", "Unknown")
        'Default main template'

        No space_key, search at root level:
        >>> templates = {
        ...     "BrowseLink": "Root template",
        ...     "default": "Root default"
        ... }
        >>> get_by_spaced_key(templates, None, "BrowseLink")
        'Root template'

        Only space_key provided (no item_key):
        >>> get_by_spaced_key(templates, "action_agent/main", None)

        No space_key, item_key not found:
        >>> templates = {"default": "Root default"}
        >>> get_by_spaced_key(templates, None, "Missing")
        'Root default'
    """
    # Step 1: Determine the template space
    if space_key:
        if space_key in d:
            template_space: Optional[Mapping] = d[space_key]
        else:
            template_space = None
    else:
        # Use root level
        template_space = d

    # Step 2: Lookup item with fallback to default using get__
    value = None
    if template_space is not None and item_key is not None:
        # Use get__ for fallback logic
        if default_item_key and item_key != default_item_key:
            value = get__(template_space, item_key, default_item_key, default=None)
        else:
            value = get__(template_space, item_key, default=None)

    return value


def get_values_by_path(
    data,
    key_path,
    return_path: bool = True,
    return_single_value: bool = False,
    unpack_result_for_single_value: bool = True,
):
    """
    Retrieves values from a nested dictionary by following a specified key path provided as a list of keys,
    using an iterative approach with a stack. This function handles lists within the nested structure by
    retrieving values for each list element.

    Args:
        data: The nested dictionary or JSON-like object from which to retrieve values.
        key_path: The list of keys that define the path to the desired value. If a key within the path
            points to a list, the function processes each item in the list.
        return_path: If True, returns tuples with keys representing the full path to the value
            and the value itself. If False, returns only the values. Defaults to True.
        return_single_value: If True, returns at most one value (i.e. the first retrieved value). Defaults to False.
        unpack_result_for_single_value: If True and the result is a single value, unpacks the value
            from the list. Defaults to True.

    Returns:
        List of tuples: Each tuple contains a key representing the full path to the value (concatenated with '.' and indexed
                        with '-n' for list elements), and the value itself. If a key points to a list, keys are like "a.b.c-1.d",
                        "a.b.c-2.d", etc.

    Example:
        >>> data = {
        ...     'a': {
        ...         'b': {
        ...             'c': [
        ...                 {'d': 'value1'},
        ...                 {'d': 'value2'}
        ...             ]
        ...         }
        ...     }
        ... }
        >>> get_values_by_path(data, ['a', 'b', 'c', 'd'])
        [('a.b.c-0.d', 'value1'), ('a.b.c-1.d', 'value2')]
        >>> get_values_by_path(data, ['a', 'b', 'c', '*'])
        [('a.b.c-0', ['value1']), ('a.b.c-1', ['value2'])]

        >>> data = {
        ...    'a': {
        ...        'b': {
        ...            'c': [
        ...                {'d': 'value1', 'e': [1, 2, {'f': 'deep'}]},
        ...                {'d': 'value2'}
        ...            ]
        ...        },
        ...        'x': {
        ...            'y': [10, 20, 30]
        ...        }
        ...    }
        ... }
        >>> get_values_by_path(data, ['a', 'b', 'c', 1, 'd'], unpack_result_for_single_value=False)
        [('a.b.c-1.d', 'value2')]
        >>> get_values_by_path(data, ['a', 'b', 'c', 'd'], unpack_result_for_single_value=False)
        [('a.b.c-0.d', 'value1'), ('a.b.c-1.d', 'value2')]
        >>> get_values_by_path(data, ['a', 'b', 'c', 'e', 'f'])
        ('a.b.c-0.e-2.f', 'deep')
        >>> get_values_by_path(data, ['a', 'x', 'y'])
        ('a.x.y', [10, 20, 30])
        >>> get_values_by_path(data, ['a', 'x', 'y', [0, 2]])
        [('a.x.y-0', 10), ('a.x.y-2', 30)]
    """
    # Stack to hold the items to process (dictionary, remaining keys, path)
    stack = [(data, key_path, "")]
    results = []

    while stack:
        current_data, keys, current_path = stack.pop()
        if not keys:
            if return_path:
                if return_single_value:
                    return current_path, current_data
                else:
                    results.append((current_path, current_data))
            else:
                if return_single_value:
                    return current_data
                else:
                    results.append(current_data)
            continue

        if isinstance(current_data, Sequence):
            if isinstance(keys[0], int):
                index = keys[0]
                new_keys = keys[1:]
                if index < len(current_data):
                    indexed_path = f"{current_path}-{index}"
                    stack.append((current_data[index], new_keys, indexed_path))
            elif (
                keys[0] is not None
                and isinstance(keys[0], Sequence)
                and all(isinstance(_key, int) for _key in keys[0])
            ):
                key = keys[0]
                new_keys = keys[1:]
                for _index in range(len(key) - 1, -1, -1):
                    index = key[_index]
                    if index < len(current_data):
                        indexed_path = f"{current_path}-{index}"
                        stack.append((current_data[index], new_keys, indexed_path))
            elif keys[0] == "*":
                new_keys = keys[1:]
                for index in range(len(current_data) - 1, -1, -1):
                    item = current_data[index]
                    indexed_path = f"{current_path}-{index}"
                    stack.append((list(item.values()), new_keys, indexed_path))
            else:
                for index in range(len(current_data) - 1, -1, -1):
                    item = current_data[index]
                    indexed_path = f"{current_path}-{index}"
                    stack.append((item, keys, indexed_path))
        else:
            key = keys[0]
            new_keys = keys[1:]
            try:
                new_data = get_multiple_by_indexes_or_keys(
                    current_data, *iter_(key, non_atom_types=List), raise_key_error=True
                )
            except:
                continue
            new_path = f"{current_path}.{key}" if current_path else key
            stack.append((new_data, new_keys, new_path))

    if unpack_result_for_single_value:
        return unpack_single_value(results)
    else:
        return results


def get_value_by_path(data, key_path, return_path: bool = False):
    """
    Retrieves a single value from a nested dictionary by following a specified key path.

    This is a convenience function that wraps `get_values_by_path` to return only the first
    matching value found along the specified path. It's particularly useful when you expect
    to find exactly one value or only care about the first match in cases where multiple
    values might exist.

    Args:
        data: The nested dictionary, list, or JSON-like object from which to retrieve the value.
              Can be a dictionary, list, or any combination of nested structures.
        key_path (list): The list of keys that define the path to the desired value. If a key within
                        the path points to a list, the function processes the first matching item.
                        Special values:
                        - int: Index into a list/array
                        - '*': Wildcard to extract values from the first list item
                        - list of ints: Multiple indices (returns value from first valid index)
        return_path (bool, optional): If True, returns a tuple (path_string, value) where path_string
                                    represents the full path to the value. If False, returns only the value.
                                    Defaults to False.

    Returns:
        Union[Any, Tuple[str, Any], None]:
            - If return_path=False: The first value found at the specified path, or None if not found
            - If return_path=True: Tuple (path_string, value) or None if not found

            Path strings are formatted as "key1.key2.key3-index.key4" where:
            - '.' separates dictionary keys
            - '-index' indicates list indexing (e.g., '-0', '-1', '-2')

    Examples:
        Basic nested dictionary access:
        >>> data = {
        ...     'user': {
        ...         'profile': {
        ...             'name': 'John Doe',
        ...             'email': 'john@example.com',
        ...             'age': 30
        ...         }
        ...     }
        ... }
        >>> get_value_by_path(data, ['user', 'profile', 'name'])
        'John Doe'

        >>> get_value_by_path(data, ['user', 'profile', 'email'])
        'john@example.com'

        >>> get_value_by_path(data, ['user', 'profile', 'name'], return_path=True)
        ('user.profile.name', 'John Doe')

        Accessing values in arrays (returns first match):
        >>> data = {
        ...     'users': [
        ...         {'name': 'Alice', 'age': 25, 'role': 'admin'},
        ...         {'name': 'Bob', 'age': 30, 'role': 'user'},
        ...         {'name': 'Charlie', 'age': 35, 'role': 'user'}
        ...     ]
        ... }
        >>> get_value_by_path(data, ['users', 'name'])
        'Alice'

        >>> get_value_by_path(data, ['users', 'role'])
        'admin'

        >>> get_value_by_path(data, ['users', 'name'], return_path=True)
        ('users-0.name', 'Alice')

        Specific array index access:
        >>> get_value_by_path(data, ['users', 1, 'name'])
        'Bob'

        >>> get_value_by_path(data, ['users', 2, 'age'])
        35

        >>> get_value_by_path(data, ['users', 0, 'role'], return_path=True)
        ('users-0.role', 'admin')

        Multiple indices (returns first valid):
        >>> get_value_by_path(data, ['users', [1, 2], 'name'])
        'Bob'

        >>> get_value_by_path(data, ['users', [5, 1, 0], 'name'])  # Index 5 invalid, returns index 1
        'Bob'

        Complex nested structures:
        >>> data = {
        ...     'company': {
        ...         'departments': [
        ...             {
        ...                 'name': 'Engineering',
        ...                 'manager': {'name': 'Sarah', 'level': 'senior'},
        ...                 'teams': [
        ...                     {'name': 'Backend', 'lead': 'Mike'},
        ...                     {'name': 'Frontend', 'lead': 'Anna'}
        ...                 ]
        ...             },
        ...             {
        ...                 'name': 'Marketing',
        ...                 'manager': {'name': 'David', 'level': 'junior'},
        ...                 'teams': [
        ...                     {'name': 'Digital', 'lead': 'Lisa'}
        ...                 ]
        ...             }
        ...         ]
        ...     }
        ... }
        >>> get_value_by_path(data, ['company', 'departments', 'name'])
        'Engineering'

        >>> get_value_by_path(data, ['company', 'departments', 0, 'manager', 'name'])
        'Sarah'

        >>> get_value_by_path(data, ['company', 'departments', 1, 'teams', 'lead'])
        'Lisa'

        >>> get_value_by_path(data, ['company', 'departments', 'teams', 'name'])
        'Backend'

        Using wildcard '*' (extracts from first item):
        >>> data = {
        ...     'products': [
        ...         {'name': 'laptop', 'specs': {'cpu': 'i7', 'ram': '16GB'}},
        ...         {'name': 'phone', 'specs': {'cpu': 'A15', 'ram': '8GB'}}
        ...     ]
        ... }
        >>> get_value_by_path(data, ['products', '*'])
        ['laptop', {'cpu': 'i7', 'ram': '16GB'}]

        Deeply nested access:
        >>> data = {
        ...     'api': {
        ...         'v1': {
        ...             'endpoints': [
        ...                 {
        ...                     'path': '/users',
        ...                     'methods': ['GET', 'POST'],
        ...                     'auth': {'required': True, 'type': 'bearer'}
        ...                 }
        ...             ]
        ...         }
        ...     }
        ... }
        >>> get_value_by_path(data, ['api', 'v1', 'endpoints', 'auth', 'type'])
        'bearer'

        >>> get_value_by_path(data, ['api', 'v1', 'endpoints', 0, 'methods'])
        ['GET', 'POST']

        Handling missing keys:
        >>> get_value_by_path(data, ['api', 'v2', 'endpoints'])  # v2 doesn't exist

        >>> get_value_by_path(data, ['api', 'v1', 'nonexistent'])

        >>> get_value_by_path(data, ['api', 'v1', 'endpoints', 'nonexistent'])

        Working with mixed data types:
        >>> data = {
        ...     'config': {
        ...         'database': {
        ...             'connections': [
        ...                 {'name': 'primary', 'host': 'db1.example.com', 'port': 5432},
        ...                 {'name': 'replica', 'host': 'db2.example.com', 'port': 5432}
        ...             ],
        ...             'pool_size': 10,
        ...             'timeout': 30.5
        ...         }
        ...     }
        ... }
        >>> get_value_by_path(data, ['config', 'database', 'pool_size'])
        10

        >>> get_value_by_path(data, ['config', 'database', 'timeout'])
        30.5

        >>> get_value_by_path(data, ['config', 'database', 'connections', 'host'])
        'db1.example.com'

        >>> get_value_by_path(data, ['config', 'database', 'connections', 1, 'name'])
        'replica'

        Real-world API response example:
        >>> api_response = {
        ...     'status': 'success',
        ...     'data': {
        ...         'user': {
        ...             'id': 123,
        ...             'profile': {
        ...                 'personal': {
        ...                     'firstName': 'John',
        ...                     'lastName': 'Doe',
        ...                     'email': 'john.doe@example.com'
        ...                 },
        ...                 'settings': {
        ...                     'theme': 'dark',
        ...                     'notifications': {
        ...                         'email': True,
        ...                         'push': False,
        ...                         'sms': True
        ...                     }
        ...                 }
        ...             },
        ...             'posts': [
        ...                 {'id': 1, 'title': 'Hello World', 'published': True},
        ...                 {'id': 2, 'title': 'Draft Post', 'published': False}
        ...             ]
        ...         }
        ...     }
        ... }
        >>> # Extract user email
        >>> get_value_by_path(api_response, ['data', 'user', 'profile', 'personal', 'email'])
        'john.doe@example.com'

        >>> # Extract theme preference
        >>> get_value_by_path(api_response, ['data', 'user', 'profile', 'settings', 'theme'])
        'dark'

        >>> # Extract first post title
        >>> get_value_by_path(api_response, ['data', 'user', 'posts', 'title'])
        'Hello World'

        >>> # Extract specific post
        >>> get_value_by_path(api_response, ['data', 'user', 'posts', 1, 'published'])
        False

        >>> # Check notification setting
        >>> get_value_by_path(api_response, ['data', 'user', 'profile', 'settings', 'notifications', 'push'])
        False

        Edge cases:
        >>> # Empty data
        >>> get_value_by_path({}, ['key'])

        >>> # Empty path
        >>> get_value_by_path({'key': 'value'}, [])
        {'key': 'value'}

        >>> # None values
        >>> data_with_none = {'a': None, 'b': {'c': None}}
        >>> get_value_by_path(data_with_none, ['a'])

        >>> get_value_by_path(data_with_none, ['b', 'c'])

        >>> # Boolean values
        >>> bool_data = {'settings': {'enabled': False, 'debug': True}}
        >>> get_value_by_path(bool_data, ['settings', 'enabled'])
        False

        >>> get_value_by_path(bool_data, ['settings', 'debug'])
        True

        Array bounds handling:
        >>> small_array = {'items': [{'name': 'first'}]}
        >>> get_value_by_path(small_array, ['items', 0, 'name'])
        'first'

        >>> get_value_by_path(small_array, ['items', 5, 'name'])  # Index out of bounds

        >>> get_value_by_path(small_array, ['items', [5, 0], 'name'])  # Falls back to valid index
        'first'

        Type consistency examples:
        >>> numeric_data = {
        ...     'stats': {
        ...         'count': 42,
        ...         'average': 3.14159,
        ...         'rates': [0.1, 0.2, 0.3]
        ...     }
        ... }
        >>> get_value_by_path(numeric_data, ['stats', 'count'])
        42

        >>> get_value_by_path(numeric_data, ['stats', 'average'])
        3.14159

        >>> get_value_by_path(numeric_data, ['stats', 'rates'])
        [0.1, 0.2, 0.3]

        >>> get_value_by_path(numeric_data, ['stats', 'rates', 1])
        0.2
    """
    return get_values_by_path(
        data=data, key_path=key_path, return_path=return_path, return_single_value=True
    )


def get_values_by_path_hierarchical(data, key_path):
    """
    Retrieves and preserves the nested structure of values from a dictionary based on a given key path.
    Handles nested lists by maintaining the full structure.

    Args:
        data: The nested dictionary or JSON-like object from which to retrieve values.
        key_path: The list of keys that define the path to the desired value. If a key within the path
                  points to a list, the function maintains the list structure in the output.

    Returns:
        A dictionary reflecting the nested structure of the data up to the last key in the path,
        preserving the structure even if the final value is within a list.

    Example:
        >>> data = {
        ... 'a': {
        ...        'b': {
        ...            'c': [
        ...                {'d': 'value1'},
        ...                {'d': 'value2'}
        ...            ]
        ...        }
        ...    }
        ... }
        >>> get_values_by_path_hierarchical(data, ['a', 'b', 'c', 'd'])
        {'a': {'b': {'c': [{'d': 'value1'}, {'d': 'value2'}]}}}
        >>> get_values_by_path_hierarchical(data, ['a', 'b', 'c', '*'])
        {'a': {'b': {'c': [['value1'], ['value2']]}}}

        >>> data = {
        ...    'a': {
        ...        'b': {
        ...            'c': [
        ...                {'d': {'e': 'value1'}},
        ...                {'d': {'e': 'value2'}}
        ...            ],
        ...            'f': {
        ...                'g': [
        ...                    {'h': 'value3'},
        ...                    {'h': 'value4'}
        ...                ],
        ...                'i': 'value5'
        ...            }
        ...        }
        ...    },
        ...    'j': {
        ...        'k': [
        ...            {'l': 'value6'},
        ...            {'m': {'n': 'value7'}}
        ...        ]
        ...    }
        ... }
        >>> get_values_by_path_hierarchical(data, ['a', 'b', 'c', 'd', 'e'])
        {'a': {'b': {'c': [{'d': {'e': 'value1'}}, {'d': {'e': 'value2'}}]}}}
        >>> get_values_by_path_hierarchical(data, ['a', 'b', 'f', 'g', 'h'])
        {'a': {'b': {'f': {'g': [{'h': 'value3'}, {'h': 'value4'}]}}}}
        >>> get_values_by_path_hierarchical(data, ['j', 'k'])
        {'j': {'k': [{'l': 'value6'}, {'m': {'n': 'value7'}}]}}
    """

    def recursive_get(sub_data, path):
        # Base case: if the path is empty, return the sub_data
        if not path:
            return sub_data

        if isinstance(sub_data, Sequence):
            if isinstance(path[0], int):
                return recursive_get(sub_data[path[0]], path[1:])
            elif (
                path[0] is not None
                and isinstance(path[0], Sequence)
                and all(isinstance(index, int) for index in path[0])
            ):
                next_path = path[1:]
                return [
                    recursive_get(sub_data[i], next_path)
                    for i in path[0]
                    if i < len(sub_data)
                ]
            elif path[0] == "*":
                next_path = path[1:]
                return [
                    recursive_get(list(item.values()), next_path) for item in sub_data
                ]
            else:
                return [recursive_get(item, path) for item in sub_data]
        else:
            key = path[0]
            next_path = path[1:]
            return {
                key: recursive_get(value, next_path)
                for key, value in get_multiple(
                    sub_data,
                    key,
                    raise_key_error=True,
                    unpack_result_for_single_key=False,
                ).items()
            }

    # Start the recursive processing
    return recursive_get(data, key_path)


# endregion


class KeyRequirement(int, Enum):
    NoRequirement = 0
    ExistingKey = 1
    NewKey = 2


def _check_key_for_mapping(
    d: Mapping,
    key,
    key_requirement: KeyRequirement = KeyRequirement.NoRequirement,
    raise_key_error: bool = False,
):
    if key_requirement == KeyRequirement.ExistingKey and key not in d:
        if raise_key_error:
            if len(d) < 100:
                raise ValueError(
                    f"key '{key}' does not exist in the mapping; "
                    f"the current keys of the mapping are '{tuple(d)}'"
                )
            else:
                raise ValueError(
                    f"key '{key}' does not exist in the mapping; "
                    f"the top 100 keys of the mapping are '{tuple(islice(d, 100))}'"
                )
        else:
            return False
    elif key_requirement == KeyRequirement.NewKey and key in d:
        if raise_key_error:
            raise ValueError(f"key '{key}' already exists in the mapping")
        else:
            return False
    return True


def _check_key_for_obj(
    d: Mapping,
    key,
    key_requirement: KeyRequirement = KeyRequirement.NoRequirement,
    raise_key_error: bool = False,
):
    if key_requirement == KeyRequirement.ExistingKey and not hasattr(d, key):
        if raise_key_error:
            raise ValueError(f"key '{key}' does not exist in object {d}")
        else:
            return False
    elif key_requirement == KeyRequirement.NewKey and hasattr(d, key):
        if raise_key_error:
            raise ValueError(f"key '{key}' already exists in the object {d}")
        else:
            return False
    return True


def set_(
    d: Union[Dict, Any],
    key,
    value,
    key_requirement: KeyRequirement = KeyRequirement.NoRequirement,
    raise_key_error: bool = False,
):
    if isinstance(d, Dict):
        if _check_key_for_mapping(
            d=d,
            key=key,
            key_requirement=key_requirement,
            raise_key_error=raise_key_error,
        ):
            d[key] = value
    else:
        if _check_key_for_obj(
            d=d,
            key=key,
            key_requirement=key_requirement,
            raise_key_error=raise_key_error,
        ):
            setattr(d, key, value)


def set__(
    d: Union[Dict, Any],
    keys_and_values: Mapping,
    key_requirement: KeyRequirement = KeyRequirement.NoRequirement,
    raise_key_error: bool = False,
):
    if isinstance(d, Dict):
        for key, value in keys_and_values.items():
            if _check_key_for_mapping(
                d=d,
                key=key,
                key_requirement=key_requirement,
                raise_key_error=raise_key_error,
            ):
                d[key] = value
    else:
        for key, value in keys_and_values.items():
            if _check_key_for_obj(
                d=d,
                key=key,
                key_requirement=key_requirement,
                raise_key_error=raise_key_error,
            ):
                d[key] = value


def promote_keys(d: dict, keys_to_promote: Iterable, in_place: bool = True):
    """
    Promotes the specified keys to the beginning of the dictionary, optionally in-place.
    The order of the keys in `keys_to_promote` will be maintained in the resulting dictionary.

    Args:
        d: The input dictionary.
        keys_to_promote: An iterable of keys to promote to the beginning of the dictionary.
        in_place: If True, the input dictionary is modified in-place. If False, a new
            dictionary is created and returned.

    Returns:
        The dictionary with the specified keys promoted to the beginning.

    Examples:
        >>> d = {'a': 1, 'b': 2, 'c': 3, 'd': 4}
        >>> d2 = promote_keys(d, ['c', 'a'], in_place=False)
        >>> print(d)
        {'a': 1, 'b': 2, 'c': 3, 'd': 4}
        >>> print(d2)
        {'c': 3, 'a': 1, 'b': 2, 'd': 4}

        >>> d = {'x': 10, 'y': 20, 'z': 30}
        >>> d2 = promote_keys(d, ['y'], in_place=True)
        >>> print(d)
        {'y': 20, 'x': 10, 'z': 30}
        >>> print(d2)
        {'y': 20, 'x': 10, 'z': 30}
    """
    keys_to_demote = filter(lambda x: x not in keys_to_promote, d.keys())
    if in_place:
        keys_to_demote = tuple(keys_to_demote)
        for k in keys_to_promote:
            if k in d:
                v = d[k]
                del d[k]
                d[k] = v
        for k in keys_to_demote:
            v = d[k]
            del d[k]
            d[k] = v
        return d
    else:
        new_dict = {}
        for k in keys_to_promote:
            if k in d:
                new_dict[k] = d[k]
        for k in keys_to_demote:
            new_dict[k] = d[k]
        return new_dict


def kvswap(d: Mapping, allows_duplicate_values: bool = False):
    """
    Swaps the key and values in a mapping.
    This requires the values being qualified as keys (e.g. float numbers cannot be keys).

    If `allows_duplicate_values` is False, then the values must be distinct for the key-value
    swaping to succeed; otherwise, keys of the same values will be collected into lists in the
    returned key-value swaped dictionary.

    Examples:
        >>> kvswap({1: 2, 3: 4})
        {2: 1, 4: 3}
        >>> kvswap({1: ['a', 'b'], 3: ['c', 'd']})
        {('a', 'b'): 1, ('c', 'd'): 3}
        >>> kvswap({1: 2, 3: 2, 4: 5}, allows_duplicate_values=True)
        {2: [1, 3], 5: 4}
    """
    if allows_duplicate_values:
        out = {}
        for k, v in d.items():
            if isinstance(v, list):
                v = tuple(v)
            if v in out:
                _k = out[v]
                if isinstance(_k, list):
                    _k.append(k)
                else:
                    out[v] = [_k, k]
            else:
                out[v] = k
        return out
    else:
        return {(tuple(v) if isinstance(v, list) else v): k for k, v in d.items()}


def join_mapping_by_values(
    d1: Mapping,
    d2: Mapping,
    allows_duplicate_values: bool = False,
    keep_original_value_for_mis_join: bool = False,
):
    """
    Joins the keys of two mappings through the values.
    For example, if one mapping is `{'a': 'b'}`, and the other mapping is `{'c': 'b'}`,
    then the joined mapping is `{'a': 'c'}`.

    Args:
        d1: the first mapping.
        d2: the second mapping.
        allows_duplicate_values: True to allow keys for the same values in `d2`
            being collected into lists; for example, joining `{'a': 'b'}`, `{'c': 'b', 'd': 'b'}`
            gets `{'a': ['c', 'd']}` if this parameter is set True.
        keep_original_value_for_mis_join: True to use the original value of `d1` if a value of `d1`
            cannot be found in the values of `d2`; otherwise, keys in `d1` will be dropped if their
            values cannot be found in the values of `d2`; for example, joining `{'a': 'b'}`,
            `{'c': 'd'}` gets `{'a': 'b'}` if this parameter is set True, but gets `{}` if
            this parameter is set False.

    Returns: a mapping from keys of `d1` to the keys of `d2`,
        joined by the values of the two mappings.

    Examples:
        >>> join_mapping_by_values(
        ...   d1={1: 2, 3: 4, 5: 6, 7: 8},
        ...   d2={-2: 2, -4: 4, -6: 6}
        ... )
        {1: -2, 3: -4, 5: -6}
        >>> join_mapping_by_values(
        ...   d1={1: 2, 3: 4, 5: 6, 7: 8},
        ...   d2={-2: 2, -4: 4, -6: 6},
        ...   keep_original_value_for_mis_join=True
        ... )
        {1: -2, 3: -4, 5: -6, 7: 8}
        >>> join_mapping_by_values(
        ...   d1={1: 2, 3: 4, 5: 6, 7: 8},
        ...   d2={-2: 2, -4: 4, -6: 6, -7: 6},
        ...   allows_duplicate_values=True,
        ...   keep_original_value_for_mis_join=True
        ... )
        {1: -2, 3: -4, 5: [-6, -7], 7: 8}
        >>> join_mapping_by_values(
        ...   d1={1: [2, 3], 3: [4, 5], 6: 7},
        ...   d2={-1: [2, 3], -3: [4, 5], -6: 6}
        ... )
        {1: -1, 3: -3}
        >>> join_mapping_by_values(
        ...   d1={1: [2, 3], 3: [4, 5], 6: 7},
        ...   d2={-1: [2, 3], -3: [4, 5], -6: 6},
        ...   keep_original_value_for_mis_join=True
        ... )
        {1: -1, 3: -3, 6: 7}
    """
    d2 = kvswap(d2, allows_duplicate_values=allows_duplicate_values)
    out = {}
    for k, v in d1.items():
        if isinstance(v, list):
            v = tuple(v)

        if v in d2:
            out[k] = d2[v]
        elif keep_original_value_for_mis_join:
            out[k] = v
    return out


# region naming


def update_map_with_prefix_suffix(
    d: Mapping[str, Any],
    d2: Mapping[str, Any],
    prefix: str = None,
    suffix: str = None,
    sep: str = "_",
    avoid_repeat: bool = True,
) -> Mapping[str, Any]:
    """
    Updates the first mapping with the second mapping, applying an optional prefix and/or suffix to the keys of the second mapping.

    Args:
        d (Mapping[str, Any]): The original dictionary to be updated.
        d2 (Mapping[str, Any]): The dictionary whose keys and values will be used to update the original dictionary.
        prefix (str, optional): A string to prepend to the keys of d2 before updating d. Default is None.
        suffix (str, optional): A string to append to the keys of d2 before updating d. Default is None.
        sep (str, optional): Separator between the key and the prefix/suffix. Default is '_'.
        avoid_repeat (bool, optional): Avoids repeating the prefix/suffix if it already exists. Default is True.

    Returns:
        Mapping[str, Any]: The updated dictionary.

    Examples:
        >>> d = {'a': 1, 'b': 2}
        >>> d2 = {'x': 10, 'y': 20}
        >>> update_map_with_prefix_suffix(d, d2)
        {'a': 1, 'b': 2, 'x': 10, 'y': 20}

        >>> update_map_with_prefix_suffix(d, d2, prefix='pre')
        {'a': 1, 'b': 2, 'pre_x': 10, 'pre_y': 20}

        >>> update_map_with_prefix_suffix(d, d2, suffix='suf')
        {'a': 1, 'b': 2, 'x_suf': 10, 'y_suf': 20}

        >>> update_map_with_prefix_suffix(d, d2, prefix='pre', suffix='suf')
        {'a': 1, 'b': 2, 'pre_x_suf': 10, 'pre_y_suf': 20}

        >>> update_map_with_prefix_suffix(d, d2, prefix='pre', suffix='suf', sep='-', avoid_repeat=False)
        {'a': 1, 'b': 2, 'pre-x-suf': 10, 'pre-y-suf': 20}

        >>> d = {}
        >>> update_map_with_prefix_suffix(d, d2, prefix='pre', suffix='suf')
        {'pre_x_suf': 10, 'pre_y_suf': 20}

        >>> update_map_with_prefix_suffix(d, {'x_suf': 10}, suffix='suf', avoid_repeat=False)
        {'x_suf_suf': 10}
    """
    result = dict(d)  # Create a copy of the original dictionary
    for key, value in d2.items():
        new_key = add_prefix_suffix(
            key, prefix=prefix, suffix=suffix, sep=sep, avoid_repeat=avoid_repeat
        )
        result[new_key] = value
    return result


def add_key_prefix_suffix(
    d: Mapping[str, Any],
    prefix: str = None,
    suffix: str = None,
    sep: str = "_",
    avoid_repeat: bool = False,
) -> dict:
    """
    Returns a new dictionary with the same key-value pairs as the input dictionary `d`,
    but with optional prefix and/or suffix added to each key.

    Args:
        d (Mapping[str, Any]): The input dictionary whose keys will be modified.
        prefix (str, optional): A string to prepend to each key. Default is None.
        suffix (str, optional): A string to append to each key. Default is None.
        sep (str, optional): Separator between the key and the prefix/suffix. Default is '_'.
        avoid_repeat (bool, optional): Avoids repeating the prefix/suffix if it already exists. Default is False.

    Returns:
        dict: A new dictionary with modified keys.

    Examples:
        >>> d = {'a': 1, 'b': 2}
        >>> add_key_prefix_suffix(d, prefix='pre')
        {'pre_a': 1, 'pre_b': 2}

        >>> add_key_prefix_suffix(d, suffix='suf')
        {'a_suf': 1, 'b_suf': 2}

        >>> add_key_prefix_suffix(d, prefix='pre', suffix='suf')
        {'pre_a_suf': 1, 'pre_b_suf': 2}

        >>> add_key_prefix_suffix(d, prefix='pre', suffix='suf', sep='-')
        {'pre-a-suf': 1, 'pre-b-suf': 2}

        >>> d = {'pre_a_suf': 3}
        >>> add_key_prefix_suffix(d, prefix='pre', suffix='suf', avoid_repeat=True)
        {'pre_a_suf': 3}

        >>> d = {'pre_a': 3}
        >>> add_key_prefix_suffix(d, prefix='pre', suffix='suf', avoid_repeat=False)
        {'pre_pre_a_suf': 3}
    """
    return {
        add_prefix_suffix(
            key, prefix=prefix, suffix=suffix, sep=sep, avoid_repeat=avoid_repeat
        ): value
        for key, value in d.items()
    }


# endregion

# region sub-mapping


def sub_map(
    d: Mapping, sub_keys: Iterable, excluded_keys: Union[Set, Iterable, Mapping] = None
) -> dict:
    """
    Create a new dictionary containing a subset of key-value pairs from the input dictionary,
    optionally excluding specified keys.

    Args:
        d (Mapping): The input dictionary.
        sub_keys (Iterable): An iterable containing the keys to include in the output dictionary.
        excluded_keys (Union[Set, Iterable, Mapping], optional):
            An iterable or mapping containing keys to exclude from the output dictionary. Defaults to None.

    Returns:
        dict: A new dictionary containing the selected key-value pairs.

    Examples:
        >>> d = {'a': 1, 'b': 2, 'c': 3, 'd': 4}
        >>> sub_map(d, ['a', 'c'])
        {'a': 1, 'c': 3}

        >>> sub_map(d, ['a', 'b', 'e'])
        {'a': 1, 'b': 2}

        >>> sub_map(d, ['a', 'c'], excluded_keys=['c'])
        {'a': 1}
    """
    if not excluded_keys:
        return {key: d[key] for key in sub_keys if key in d}
    else:
        return {
            key: d[key] for key in sub_keys if key in d and key not in excluded_keys
        }


def sub_map_by_prefix(prefix: str, d: Mapping, remove_prefix: bool = True):
    """
    Create a new dictionary containing key-value pairs from the input dictionary where the keys
    start with the given prefix. Optionally remove the prefix from the keys in the output dictionary.

    Args:
        prefix (str): The prefix to filter keys in the input dictionary.
        d (Mapping): The input dictionary.
        remove_prefix (bool, optional): Whether to remove the prefix from the keys in the output dictionary. Defaults to True.

    Returns:
        dict: A new dictionary containing the selected key-value pairs with keys optionally having the prefix removed.

    Examples:
        >>> d = {'pre_a': 1, 'pre_b': 2, 'c': 3, 'pre_d': 4}
        >>> sub_map_by_prefix('pre_', d)
        {'a': 1, 'b': 2, 'd': 4}

        >>> sub_map_by_prefix('pre_', d, remove_prefix=False)
        {'pre_a': 1, 'pre_b': 2, 'pre_d': 4}

        >>> d = {'prefix_key1': 'value1', 'prefix_key2': 'value2', 'other_key': 'value3'}
        >>> sub_map_by_prefix('prefix_', d)
        {'key1': 'value1', 'key2': 'value2'}

        >>> sub_map_by_prefix('prefix_', d, remove_prefix=False)
        {'prefix_key1': 'value1', 'prefix_key2': 'value2'}
    """
    if remove_prefix:
        return {
            k[len(prefix) :]: d[k] for k in filter(lambda k: k.startswith(prefix), d)
        }
    else:
        return {k: d[k] for k in filter(lambda k: k.startswith(prefix), d)}


MAPPING_KEY_OR_CONVERSION = Union[
    str,
    Iterable[str],
    Callable[[Mapping], Mapping],
    Mapping[str, Callable[[Mapping], Any]],
]

MAPPING_KEYS_OR_CONVERSIONS = Union[
    MAPPING_KEY_OR_CONVERSION,
    Sequence[MAPPING_KEY_OR_CONVERSION],
]


def convert_map(
    d: Mapping,
    conversions: MAPPING_KEYS_OR_CONVERSIONS,
    unpack_single_value: bool = False,
    **extra_keys_and_values_or_kwargs,
):
    """
    Apply a series of transformations to the input dictionary `d`. The transformations can include:
    - Selecting specific keys from the dictionary.
    - Applying a callable to transform the dictionary.
    - Using a mapping of keys to callables to transform specific values.

    Args:
        d (Mapping): The input dictionary to be transformed.
        conversions (MAPPING_KEYS_OR_CONVERSIONS): A single key, a callable, or a mapping of keys to callables
            that define the transformations. Can also be an iterable of these.
        unpack_single_value (bool, optional): If True and the result contains only one item,
            return the value directly instead of a dictionary. Defaults to False.
        **extra_keys_and_values_or_kwargs: Additional key-value pairs to include in the output dictionary.

    Returns:
        dict: A new dictionary with the applied transformations or a single value if `unpack_single_value` is True.

    Examples:
        >>> d = {'a': 1, 'b': 2, 'c': 3, 'd': 4}
        >>> convert_map(d, ['a', 'c'])
        {'a': 1, 'c': 3}

        >>> convert_map(d, {'a': lambda d: d['a'] * 10, 'b': lambda d: d['b'] + 5})
        {'a': 10, 'b': 7}

        >>> convert_map(d, lambda d: {k: v * 2 for k, v in d.items()})
        {'a': 2, 'b': 4, 'c': 6, 'd': 8}

        >>> convert_map(d, [
        ...     'a',
        ...     {'b': lambda d: d['b'] + 1},
        ...     lambda d: {'c': d['c'] * 2}
        ... ])
        {'a': 1, 'b': 3, 'c': 6}

        >>> convert_map(d, 'a', unpack_single_value=True)
        1

        >>> convert_map(d, 'default', default=5)
        {'default': 5}

        >>> convert_map(d, ['a', 'e'], e=10)
        {'a': 1, 'e': 10}

        >>> # Example with extra_keys_and_values_or_kwargs
        >>> convert_map(d, ['a', 'e'], e=100, f=200)
        {'a': 1, 'e': 100}

        >>> # Example with extra_keys_and_values_or_kwargs and function transformation
        >>> convert_map(d, {'a': lambda d: d['a'] * 2, 'b': lambda d, e: d['b'] + e(d), 'c': lambda d, g: d['c'] + g}, e=lambda d: d['b'] + 50, g=300)
        {'a': 2, 'b': 54, 'c': 303}

        >>> # Example with missing key in `d` but present in extra_keys_and_values_or_kwargs
        >>> convert_map(d, 'f', f=500)
        {'f': 500}

        >>> # Example with both `d` and extra_keys_and_values_or_kwargs keys
        >>> convert_map(d, ['a', 'b', 'h'], h=700)
        {'a': 1, 'b': 2, 'h': 700}
    """
    from python_utils.common_utils import get_relevant_named_args

    result = {}

    if isinstance(conversions, (str, Mapping, Callable)):
        conversions = [conversions]

    for conversion in conversions:
        if isinstance(conversion, str):
            if conversion in d:
                result[conversion] = d[conversion]
            elif conversion in extra_keys_and_values_or_kwargs:
                result[conversion] = extra_keys_and_values_or_kwargs[conversion]
        elif callable(conversion):
            result.update(conversion(d, **extra_keys_and_values_or_kwargs))
        elif isinstance(conversion, Mapping):
            for key, func in conversion.items():
                result[key] = func(
                    d,
                    **get_relevant_named_args(func, **extra_keys_and_values_or_kwargs),
                )

    if len(result) == 1 and unpack_single_value:
        return next(iter(result.values()))
    return result


# endregion


# region map explosion
def explode_map(
    d: Mapping,
    keys: Iterable = None,
    explosion_method: Callable = product__,
    mapping_class: type = dict,
    **explosion_kwargs,
) -> Iterator[Mapping]:
    """
    Explodes a mapping into multiple mappings by applying a specified Cartesian product method
    on the values of selected keys. This function is useful when you have a dictionary where
    some values are iterables, and you want to create new dictionaries for each combination of
    the values of the selected keys.

    Args:
        d (Mapping): The input dictionary.
        keys (Iterable, optional): The keys whose values will be exploded. Defaults to None (all keys will be exploded).
        explosion_method (Callable, optional): The method to use for exploding the values. Defaults to product__.
        mapping_class (type, optional): The class to use for the output mappings. Defaults to dict.
        **explosion_kwargs: Additional keyword arguments to pass to the explosion method.

    Yields:
        Mapping: New mappings with the same keys but with values taken from the exploded values.

    Examples:
        >>> from python_utils.common_utils.iter_helper import zip__, zip_, zip_longest__
        >>> from itertools import product
        >>> def product__(*iterables, atom_types=(str,), ignore_none=False):
        ...     if ignore_none:
        ...         yield from product(*(iter(x) for x in iterables if x is not None))
        ...     else:
        ...         yield from product(*(iter(x) for x in iterables))
        >>> d = {'a': [1, 2]}
        >>> list(explode_map(d))
        [{'a': 1}, {'a': 2}]
        >>> list(explode_map(d, mapping_class=tuple))
        [(('a', 1),), (('a', 2),)]
        >>> list(explode_map(d, mapping_class=tuple, explosion_method=zip__))
        [(('a', 1),), (('a', 2),)]

        >>> d = {'a': [1, 2], 'b': [3, 4]}
        >>> list(explode_map(d))
        [{'a': 1, 'b': 3}, {'a': 1, 'b': 4}, {'a': 2, 'b': 3}, {'a': 2, 'b': 4}]
        >>> list(explode_map(d, mapping_class=tuple))
        [(('a', 1), ('b', 3)), (('a', 1), ('b', 4)), (('a', 2), ('b', 3)), (('a', 2), ('b', 4))]
        >>> list(explode_map(d, mapping_class=tuple, explosion_method=zip__))
        [(('a', 1), ('b', 3)), (('a', 2), ('b', 4))]

        >>> d = {'a': [1, 2], 'b': [3, 4]}
        >>> list(explode_map(d, keys=['b']))
        [{'b': 3, 'a': [1, 2]}, {'b': 4, 'a': [1, 2]}]

        >>> d = {'a': [1, 2], 'b': 3}
        >>> list(explode_map(d))
        [{'a': 1, 'b': 3}, {'a': 2, 'b': 3}]

        >>> d = {'a': [1, 2], 'b': '34'}
        >>> list(explode_map(d))
        [{'a': 1, 'b': '34'}, {'a': 2, 'b': '34'}]

        >>> d = {'a': [1, 2], 'b': ['x', 'y']}
        >>> list(explode_map(d, explosion_method=zip__))
        [{'a': 1, 'b': 'x'}, {'a': 2, 'b': 'y'}]

        >>> d = {'a': set([1, 2]), 'b': set([1, 2, 3])}
        >>> list(explode_map(d, explosion_method=zip_))
        [{'a': {1, 2}, 'b': {1, 2, 3}}]

        >>> d = {'a': set([1, 2]), 'b': set([1, 2, 3])}
        >>> list(explode_map(d, explosion_method=zip_, non_atom_types=(set, )))
        [{'a': 1, 'b': 1}, {'a': 2, 'b': 2}]

        >>> d = {'a': set([1, 2]), 'b': set([1, 2, 3])}
        >>> list(explode_map(d, explosion_method=zip_longest__, atom_types=(str, )))
        [{'a': 1, 'b': 1}, {'a': 2, 'b': 2}, {'a': 2, 'b': 3}]

        >>> d = {'a': set([1, 2]), 'b': set([1, 2, 3])}
        >>> list(explode_map(d, atom_types=(str, )))
        [{'a': 1, 'b': 1}, {'a': 1, 'b': 2}, {'a': 1, 'b': 3}, {'a': 2, 'b': 1}, {'a': 2, 'b': 2}, {'a': 2, 'b': 3}]

        >>> d = {'a': [1, 2], 'b': [3, 4], 'c': 5}
        >>> list(explode_map(d, keys=['a', 'b']))
        [{'a': 1, 'b': 3, 'c': 5}, {'a': 1, 'b': 4, 'c': 5}, {'a': 2, 'b': 3, 'c': 5}, {'a': 2, 'b': 4, 'c': 5}]

        >>> d = {'a': [1, 2], 'b': [3, 4], 'c': [5, 6]}
        >>> list(explode_map(d, keys=['a', 'c']))
        [{'a': 1, 'c': 5, 'b': [3, 4]}, {'a': 1, 'c': 6, 'b': [3, 4]}, {'a': 2, 'c': 5, 'b': [3, 4]}, {'a': 2, 'c': 6, 'b': [3, 4]}]
    """
    if not keys:
        keys = tuple(d.keys())
        for values in explosion_method(*d.values(), **explosion_kwargs):
            yield mapping_class(zip(keys, values))
    else:
        keys_to_explode = set(keys)
        static_items = {k: v for k, v in d.items() if k not in keys_to_explode}
        dynamic_items = {k: v for k, v in d.items() if k in keys_to_explode}

        for values in explosion_method(*dynamic_items.values(), **explosion_kwargs):
            exploded_part = dict(zip(dynamic_items.keys(), values))
            yield mapping_class({**exploded_part, **static_items})


explode_map_as_tuples = partial(explode_map, mapping_class=tuple)


# endregion

# region mapping merge


def _deep_merge_two(base: Dict, override: Dict, **kwargs) -> Dict:
    """Recursively merge *override* into *base* (returns a new dict).

    Behavior per value type when both dicts share a key:
      - dict + dict:  recurse (always, when recursive=True)
      - list + list:  concatenate if concatenate_lists=True, else override wins
      - set  + set:   union if union_sets=True, else override wins
      - int  + int:   sum if sum_counters=True, else override wins
      - otherwise:    override wins
    """
    concatenate_lists = kwargs.get("concatenate_lists", False)
    union_sets = kwargs.get("union_sets", False)
    sum_counters = kwargs.get("sum_counters", False)

    result = dict(base)
    for key, override_val in override.items():
        if key in result:
            base_val = result[key]
            if isinstance(base_val, dict) and isinstance(override_val, dict):
                result[key] = _deep_merge_two(base_val, override_val, **kwargs)
            elif concatenate_lists and isinstance(base_val, list) and isinstance(override_val, list):
                result[key] = base_val + override_val
            elif union_sets and isinstance(base_val, set) and isinstance(override_val, set):
                result[key] = base_val | override_val
            elif sum_counters and isinstance(base_val, (int, float)) and isinstance(override_val, (int, float)):
                result[key] = base_val + override_val
            else:
                result[key] = override_val
        else:
            result[key] = override_val
    return result


def merge_mappings(
    mappings: Iterable[Union[Dict, Mapping]],
    in_place: bool = False,
    use_tqdm: bool = False,
    tqdm_msg: str = None,
    recursive: bool = False,
    concatenate_lists: bool = False,
    union_sets: bool = False,
    sum_counters: bool = False,
) -> Mapping:
    """
    Merges multiple mappings into one.

    Args:
        mappings: An iterator of dictionaries or mappings to merge.
                  If `in_place` is True, the first mapping must be writable.
        in_place: If True, modifies and returns the first mapping in `mappings`;
                  otherwise, returns a new dictionary with merged data.
        use_tqdm: If True, wraps the iterator with tqdm for progress display.
        tqdm_msg: Optional message for tqdm progress bar.
        recursive: If True, recursively merge nested dicts instead of
            overriding. When False (default), behaves like dict.update().
        concatenate_lists: If True (requires recursive=True), concatenate
            list values instead of overriding.
        union_sets: If True (requires recursive=True), union set values
            instead of overriding.
        sum_counters: If True (requires recursive=True), sum numeric values
            instead of overriding.

    Returns:
        A merged mapping, either modifying the first dictionary in `mappings`
        if `in_place` is True, or returning a new dictionary.

    Examples:
        >>> merge_mappings(iter([{1: 'a'}, {2: 'b'}, {3: 'c'}]))
        {1: 'a', 2: 'b', 3: 'c'}

        >>> merge_mappings(iter([{1: 'x', 2: 'y'}, {2: 'z', 3: 'w'}]))
        {1: 'x', 2: 'z', 3: 'w'}

        >>> d1 = {1: 'alpha'}
        >>> merge_mappings(iter([d1, {2: 'beta'}]), in_place=True)
        {1: 'alpha', 2: 'beta'}
        >>> d1  # Should be modified when in_place=True
        {1: 'alpha', 2: 'beta'}

        >>> d1 = {1: 'foo'}
        >>> merge_mappings(iter([d1, {1: 'bar'}]), in_place=False)
        {1: 'bar'}
        >>> d1  # Should remain unchanged
        {1: 'foo'}

        >>> merge_mappings([{'a': [1]}, {'a': [2]}], recursive=True, concatenate_lists=True)
        {'a': [1, 2]}

        >>> merge_mappings([{'x': {'a': 1}}, {'x': {'b': 2}}], recursive=True)
        {'x': {'a': 1, 'b': 2}}
    """
    mappings = iter(mappings)
    if use_tqdm:
        mappings = tqdm_wrap(mappings, use_tqdm=use_tqdm, tqdm_msg=tqdm_msg)
    d = next(mappings)

    if not in_place:
        d = dict(d)

    for _d in mappings:
        if recursive:
            d = _deep_merge_two(
                d,
                dict(_d),
                concatenate_lists=concatenate_lists,
                union_sets=union_sets,
                sum_counters=sum_counters,
            )
        else:
            d.update(_d)
    return d


def merge_list_valued_mappings(
    mappings: Iterator[Mapping[Any, List]],
    in_place: bool = False,
    non_atom_types: Tuple[type, ...] = (List, Tuple, Set),
):
    """
    Merges mappings with lists as their values. Lists with the same key will be merged into a single list.
    Non-atomic types can be specified to ensure that these types are merged appropriately.

    Args:
        mappings (Iterator[Mapping[Any, List]]): The mappings to merge.
        in_place (bool, optional): True if the merge results are saved in-place in the first dictionary
                                   of `mappings` and returned; False if creating a new dictionary to store
                                   the merge results. Defaults to False.
        non_atom_types (tuple, optional): A tuple of types that are considered non-atomic (iterables).
                                          Defaults to (List, Tuple, Set).

    Returns:
        Mapping[Any, List]: A dictionary of merged lists; either the first mapping of `mappings` if `in_place`
                            is True, or otherwise a new dictionary object.

    Raises:
        ValueError: If the first mapping appears twice and `in_place` is set to True.

    Examples:
        >>> mappings = [
        ...     {'a': [1, 2], 'b': [3]},
        ...     {'a': [3, 4], 'b': [4, 5], 'c': [6]},
        ...     {'a': [5], 'c': [7, 8]}
        ... ]
        >>> merge_list_valued_mappings(iter(mappings))
        defaultdict(<class 'list'>, {'a': [1, 2, 3, 4, 5], 'b': [3, 4, 5], 'c': [6, 7, 8]})

        >>> merge_list_valued_mappings(iter(mappings), in_place=True)
        {'a': [1, 2, 3, 4, 5], 'b': [3, 4, 5], 'c': [6, 7, 8]}

        >>> mappings = [
        ...     {'a': [1], 'b': [2]},
        ...     {'a': [3], 'b': [4]},
        ...     {'a': [5], 'c': [6]}
        ... ]
        >>> merge_list_valued_mappings(iter(mappings))
        defaultdict(<class 'list'>, {'a': [1, 3, 5], 'b': [2, 4], 'c': [6]})

        >>> mappings = [
        ...     {'a': [1, 2]},
        ...     {'a': [3, 4]},
        ...     {'b': [5, 6]}
        ... ]
        >>> merge_list_valued_mappings(iter(mappings), in_place=True)
        {'a': [1, 2, 3, 4], 'b': [5, 6]}

        >>> mappings = [
        ...     {'a': (1, 2), 'b': [3]},
        ...     {'a': (3, 4), 'b': [4, 5], 'c': [6]},
        ...     {'a': (5,), 'c': [7, 8]}
        ... ]
        >>> merge_list_valued_mappings(iter(mappings), non_atom_types=(List, Tuple))
        defaultdict(<class 'list'>, {'a': [1, 2, 3, 4, 5], 'b': [3, 4, 5], 'c': [6, 7, 8]})

        >>> mappings = [
        ...     {'a': [1], 'b': [2]},
        ...     {'a': [3], 'b': [4], 'c': {5}},
        ...     {'a': [6], 'c': {7, 8}}
        ... ]
        >>> merge_list_valued_mappings(iter(mappings), non_atom_types=(List, Set))
        defaultdict(<class 'list'>, {'a': [1, 3, 6], 'b': [2, 4], 'c': [5, 8, 7]})

        >>> mappings = [
        ...     {'a': [1], 'b': [2]},
        ...     {'a': [3], 'b': [4], 'c': {5}},
        ...     {'a': [6], 'c': {7, 8}}
        ... ]
        >>> merge_list_valued_mappings(iter(mappings), non_atom_types=(List, ))
        defaultdict(<class 'list'>, {'a': [1, 3, 6], 'b': [2, 4], 'c': [{5}, {8, 7}]})
    """
    output_dict = None if in_place else defaultdict(list)
    for d in mappings:
        if output_dict is None:
            output_dict = defaultdict(list, d)
        else:
            if d is output_dict:
                raise ValueError(
                    "the first mapping appears twice "
                    "and 'in_place' is set True; "
                    "in this case we have lost the original data "
                    "in the first dictionary "
                    "and hence the merge cannot proceed"
                )
            for k, v in d.items():
                if isinstance(v, non_atom_types):
                    output_dict[k].extend(v)
                else:
                    output_dict[k].append(v)
    return output_dict if not in_place else dict(output_dict)


def merge_set_valued_mappings(
    mappings: Iterator[Mapping[Any, Set]], in_place: bool = False
):
    """
    Merges mappings with sets as their values.
    Sets with the same key will be merged as a single set.

    Args:
        mappings: The mappings to merge.
        in_place: True if the merge results are saved in-place
            in the first dictionary of `mappings` and returned;
            False if creating a new dictionary to store the merge results.

    Returns: a dictionary of merged sets; either the first mapping of `mappings`
        if `in_place` is True, or otherwise a new dictionary object.
    """
    output_dict = None if in_place else defaultdict(set)
    for d in mappings:
        if output_dict is None:
            output_dict = defaultdict(set, d)
        else:
            if d is output_dict:
                raise ValueError(
                    "the first mapping appears twice "
                    "and 'in_place' is set True; "
                    "in this case we have lost the original data "
                    "in the first dictionary "
                    "and hence the merge cannot proceed"
                )
            for k, v in d.items():
                output_dict[k] = output_dict[k].union(v)
    return output_dict


def merge_counter_valued_mappings(
    mappings: Iterator[Mapping[Any, Counter]], in_place: bool = False
):
    """
    Merges mappings with counters as their values.
    Counters with the same key will be merged as a single Counter.

    Args:
        mappings: The mappings to merge.
        in_place: True if the merge results are saved in-place
            in the first dictionary of `mappings` and returned;
            False if creating a new dictionary to store the merge results.

    Returns: a dictionary of merged counters; either the first mapping of `mappings`
        if `in_place` is True, or otherwise a new dictionary object.

    """
    output_dict = None if in_place else {}
    for d in mappings:
        if output_dict is None:
            output_dict = d
        else:
            if d is output_dict:
                raise ValueError(
                    "the first mapping appears twice "
                    "and 'in_place' is set True; "
                    "in this case we have lost the original data "
                    "in the first dictionary "
                    "and hence the merge cannot proceed"
                )
            for k, v in d.items():
                if k in output_dict:
                    output_dict[k] += v
                else:
                    output_dict[k] = v
    return output_dict


# endregion


# region counting
def _add_count(count_dict, k, v):
    if k in count_dict:
        if hasattr(v, "__add__") or hasattr(v, "__iadd__"):
            count_dict[k] += v
        elif hasattr(v, "__or__") or hasattr(v, "__ior__"):
            count_dict[k] |= v
        elif isinstance(v, dict):
            count_or_accumulate(count_dict[k], v)
    else:
        # ! have to make deep copy here
        # ! to avoid the potential error caused by a `v` being used in two counters
        count_dict[k] = copy.deepcopy(v)


def count_or_accumulate(count_dict: dict, items: Union[dict, Iterator[Any], Any]):
    if items is not None:
        if isinstance(items, dict):
            for k, v in items.items():
                _add_count(count_dict, k, v)
        elif isinstance(items, (list, tuple)) and isinstance(items[0], dict):
            if len(items) == 4:
                _items, accu_keys, weight_key, extra_count_field = items
            elif len(items) == 3:
                _items, accu_keys, weight_key = items
                if isinstance(weight_key, bool):
                    weight_key = None
                    extra_count_field = "count"
                else:
                    extra_count_field = False
            elif len(items) == 2:
                _items, accu_keys = items
                weight_key = None
                extra_count_field = False
            else:
                raise ValueError("unsupported format of add-up items")

            if weight_key == "none":
                weight_key = None

            if extra_count_field is not False and extra_count_field in accu_keys:
                raise ValueError(
                    "the extra counting field should not be in the accumulation keys"
                )

            if weight_key is None:
                for k in accu_keys:
                    _add_count(count_dict, k, _items[k])
            else:
                weight = _items[weight_key]
                for k in accu_keys:
                    if k == weight_key:
                        _add_count(count_dict, k, weight)
                    else:
                        _add_count(count_dict, k, _items[k] * weight)

            if extra_count_field:
                if extra_count_field in count_dict:
                    count_dict[extra_count_field] += 1
                else:
                    count_dict[extra_count_field] = 1

        elif nonstr_iterable(items):
            for item in items:
                if item in count_dict:
                    count_dict[item] += 1
                else:
                    count_dict[item] = 1
        elif items in count_dict:
            count_dict[items] += 1
        else:
            count_dict[items] = 1
    return count_dict


def sum_dicts(count_dicts, in_place=False):
    if isinstance(count_dicts, dict):
        return count_dicts
    if len(count_dicts) == 1:
        return count_dicts[0]
    base_count_dict = count_dicts[0] if in_place else dict(count_dicts[0])
    for i in range(1, len(count_dicts)):
        count_or_accumulate(base_count_dict, count_dicts[i])

    return base_count_dict


# endregion


# region nested path operations


def parse_key_path(path, sep='.', escape_char='\\'):
    """
    Parses a dot-separated key path string into a list of keys.
    Supports escaped separators for keys that contain the separator character.
    If `path` is already a list or tuple, returns it as a list unchanged.

    Args:
        path: A dot-separated string path (e.g. "a.b.c") or a list/tuple of keys.
        sep: The separator character. Defaults to '.'.
        escape_char: The escape character for literal separators in key names.
            Defaults to '\\'.

    Returns:
        A list of string keys.

    Examples:
        >>> parse_key_path('a.b.c')
        ['a', 'b', 'c']
        >>> parse_key_path('a')
        ['a']
        >>> parse_key_path(['a', 'b', 'c'])
        ['a', 'b', 'c']
        >>> parse_key_path(('x', 'y'))
        ['x', 'y']
        >>> parse_key_path('key\\\\.with\\\\.dots.normal')
        ['key.with.dots', 'normal']
        >>> parse_key_path('a/b/c', sep='/')
        ['a', 'b', 'c']
        >>> parse_key_path('')
        ['']
    """
    if isinstance(path, (list, tuple)):
        return list(path)

    keys = []
    current = []
    i = 0
    while i < len(path):
        if path[i] == escape_char and i + 1 < len(path) and path[i + 1] == sep:
            current.append(sep)
            i += 2
        elif path[i] == sep:
            keys.append(''.join(current))
            current = []
            i += 1
        else:
            current.append(path[i])
            i += 1
    keys.append(''.join(current))
    return keys


def has_path(data, path) -> bool:
    """
    Checks whether a nested path exists in the data structure.
    Distinguishes between "value is None" (returns True) and "path missing" (returns False).

    Args:
        data: A nested dict/list structure.
        path: A dot-separated string path or a list/tuple of keys.

    Returns:
        True if the path exists (even if the value is None), False otherwise.

    Examples:
        >>> has_path({'a': {'b': 1}}, 'a.b')
        True
        >>> has_path({'a': {'b': None}}, 'a.b')
        True
        >>> has_path({'a': {'b': 1}}, 'a.c')
        False
        >>> has_path({'a': {'b': 1}}, 'x')
        False
        >>> has_path({'a': [10, 20, 30]}, ['a', 1])
        True
        >>> has_path({'a': [10, 20]}, ['a', 5])
        False
        >>> has_path({}, 'a.b')
        False
    """
    keys = parse_key_path(path)
    current = data
    for key in keys:
        if isinstance(current, dict):
            if key not in current:
                return False
            current = current[key]
        elif isinstance(current, (list, tuple)):
            try:
                idx = int(key)
            except (ValueError, TypeError):
                return False
            if 0 <= idx < len(current):
                current = current[idx]
            else:
                return False
        else:
            return False
    return True


def _walk_to_parent(data, keys):
    """
    Walks the nested structure to the parent of the final key.
    Returns (parent, final_key). Raises KeyError if any intermediate key is missing.
    """
    current = data
    for key in keys[:-1]:
        if isinstance(current, dict):
            if key not in current:
                raise KeyError(f"Intermediate key {key!r} not found in path")
            current = current[key]
        elif isinstance(current, (list, tuple)):
            try:
                idx = int(key)
            except (ValueError, TypeError):
                raise KeyError(f"Cannot use key {key!r} to index a list/tuple")
            if 0 <= idx < len(current):
                current = current[idx]
            else:
                raise KeyError(f"Index {idx} out of range for list of length {len(current)}")
        else:
            raise KeyError(f"Cannot traverse into {type(current).__name__} with key {key!r}")
    final_key = keys[-1]
    if isinstance(current, (list, tuple)):
        try:
            final_key = int(final_key)
        except (ValueError, TypeError):
            raise KeyError(f"Cannot use key {final_key!r} to index a list/tuple")
    return current, final_key


def get_at_path(data, path, default=MISSING):
    """
    Gets a value at a nested path in a dict/list structure.
    Accepts a dot-separated string or a list of keys.

    Args:
        data: A nested dict/list structure.
        path: A dot-separated string path or a list/tuple of keys.
        default: Value to return if the path is missing.
            If not provided (MISSING), raises KeyError on missing path.

    Returns:
        The value at the path, or `default` if the path is missing.

    Raises:
        KeyError: If the path is missing and no default is provided.

    Examples:
        >>> get_at_path({'a': {'b': 1}}, 'a.b')
        1
        >>> get_at_path({'a': {'b': None}}, 'a.b') is None
        True
        >>> get_at_path({'a': {'b': 1}}, 'a.c', default='nope')
        'nope'
        >>> get_at_path({'a': [10, 20]}, ['a', 0])
        10
        >>> get_at_path({'x': 1}, 'y', default=42)
        42
    """
    keys = parse_key_path(path)
    if not has_path(data, keys):
        if default is MISSING:
            raise KeyError(f"Path {path!r} not found in data")
        return default
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current[key]
        elif isinstance(current, (list, tuple)):
            current = current[int(key)]
        else:
            if default is MISSING:
                raise KeyError(f"Path {path!r} not found in data")
            return default
    return current


def set_at_path(data, path, value, create_intermediate=True):
    """
    Sets a value at a nested path in a dict structure (in-place mutation).

    Args:
        data: A nested dict/list structure.
        path: A dot-separated string path or a list/tuple of keys.
        value: The value to set.
        create_intermediate: If True, creates empty dicts for missing intermediate keys.

    Raises:
        KeyError: If an intermediate key is missing and `create_intermediate` is False.

    Examples:
        >>> d = {'a': {'b': 1}}
        >>> set_at_path(d, 'a.b', 2)
        >>> d
        {'a': {'b': 2}}
        >>> d = {'a': {}}
        >>> set_at_path(d, 'a.b.c', 3)
        >>> d
        {'a': {'b': {'c': 3}}}
        >>> d = {}
        >>> set_at_path(d, 'x.y', 5)
        >>> d
        {'x': {'y': 5}}
    """
    keys = parse_key_path(path)
    current = data
    for key in keys[:-1]:
        if isinstance(current, dict):
            if key not in current:
                if create_intermediate:
                    current[key] = {}
                else:
                    raise KeyError(f"Intermediate key {key!r} not found and create_intermediate is False")
            current = current[key]
        elif isinstance(current, (list, tuple)):
            idx = int(key)
            current = current[idx]
        else:
            raise KeyError(f"Cannot traverse into {type(current).__name__} with key {key!r}")
    final_key = keys[-1]
    if isinstance(current, dict):
        current[final_key] = value
    elif isinstance(current, list):
        current[int(final_key)] = value
    else:
        raise KeyError(f"Cannot set key {final_key!r} on {type(current).__name__}")


def delete_at_path(data, path):
    """
    Deletes a value at a nested path in a dict/list structure (in-place mutation).

    Args:
        data: A nested dict/list structure.
        path: A dot-separated string path or a list/tuple of keys.

    Raises:
        KeyError: If the path is not found.

    Examples:
        >>> d = {'a': {'b': 1, 'c': 2}}
        >>> delete_at_path(d, 'a.b')
        >>> d
        {'a': {'c': 2}}
        >>> d = {'a': [10, 20, 30]}
        >>> delete_at_path(d, ['a', 1])
        >>> d
        {'a': [10, 30]}
    """
    keys = parse_key_path(path)
    parent, final_key = _walk_to_parent(data, keys)
    if isinstance(parent, dict):
        if final_key not in parent:
            raise KeyError(f"Key {final_key!r} not found at end of path {path!r}")
        del parent[final_key]
    elif isinstance(parent, list):
        idx = int(final_key) if not isinstance(final_key, int) else final_key
        if idx < 0 or idx >= len(parent):
            raise KeyError(f"Index {idx} out of range for list of length {len(parent)}")
        del parent[idx]
    else:
        raise KeyError(f"Cannot delete from {type(parent).__name__}")


def pop_at_path(data, path, default=MISSING):
    """
    Removes and returns a value at a nested path.

    Args:
        data: A nested dict/list structure.
        path: A dot-separated string path or a list/tuple of keys.
        default: Value to return if the path is missing.
            If not provided (MISSING), raises KeyError on missing path.

    Returns:
        The removed value, or `default` if the path is missing.

    Raises:
        KeyError: If the path is missing and no default is provided.

    Examples:
        >>> d = {'a': {'b': 1, 'c': 2}}
        >>> pop_at_path(d, 'a.b')
        1
        >>> d
        {'a': {'c': 2}}
        >>> pop_at_path(d, 'a.x', default='gone')
        'gone'
    """
    keys = parse_key_path(path)
    if not has_path(data, keys):
        if default is MISSING:
            raise KeyError(f"Path {path!r} not found in data")
        return default
    parent, final_key = _walk_to_parent(data, keys)
    if isinstance(parent, dict):
        return parent.pop(final_key)
    elif isinstance(parent, list):
        idx = int(final_key) if not isinstance(final_key, int) else final_key
        return parent.pop(idx)
    else:
        raise KeyError(f"Cannot pop from {type(parent).__name__}")


def transform_at_path(data, path, func):
    """
    Applies a function to the value at a nested path and replaces it with the result.

    Args:
        data: A nested dict/list structure.
        path: A dot-separated string path or a list/tuple of keys.
        func: A callable that takes the current value and returns the new value.

    Returns:
        The new value (result of func).

    Raises:
        KeyError: If the path is not found.

    Examples:
        >>> d = {'a': {'b': 10}}
        >>> transform_at_path(d, 'a.b', lambda x: x * 2)
        20
        >>> d
        {'a': {'b': 20}}
    """
    keys = parse_key_path(path)
    parent, final_key = _walk_to_parent(data, keys)
    if isinstance(parent, dict):
        if final_key not in parent:
            raise KeyError(f"Key {final_key!r} not found at end of path {path!r}")
        new_value = func(parent[final_key])
        parent[final_key] = new_value
    elif isinstance(parent, list):
        idx = int(final_key) if not isinstance(final_key, int) else final_key
        new_value = func(parent[idx])
        parent[idx] = new_value
    else:
        raise KeyError(f"Cannot transform in {type(parent).__name__}")
    return new_value


# endregion

# region obj_walk_through


def _resolve_annotation_type(annotation) -> Optional[Type]:
    """Unwrap ``Optional[X]`` / ``Union[X, None]`` to the base concrete type.

    Returns the base type if *annotation* is a concrete class or a simple
    ``Optional`` wrapper, otherwise ``None``.
    """
    origin = getattr(annotation, '__origin__', None)
    if origin is Union:
        args = [a for a in annotation.__args__ if a is not type(None)]
        return args[0] if len(args) == 1 else None
    return annotation if isinstance(annotation, type) else None


def _iter_fields(obj) -> Iterator[Tuple[str, Any]]:
    """Yield ``(field_name, value_or_type)`` pairs for *obj*.

    - **type/class**: yields ``(name, annotation_type)`` from ``__annotations__``,
      with ``Optional``/``Union`` unwrapped to the base type.
    - **dict**: yields ``(key, value)`` pairs.
    - **list/tuple**: yields ``(str(index), element)`` pairs.
    - **attrs instance** (including ``slots=True``): yields ``(attr.name, value)``
      via ``attr.fields`` + ``getattr``.
    - **object with __dict__**: yields ``(key, value)`` from ``vars()``.
    """
    if isinstance(obj, type):
        annotations = getattr(obj, '__annotations__', {})
        for name, annotation in annotations.items():
            resolved = _resolve_annotation_type(annotation)
            if resolved is not None:
                yield name, resolved
    elif isinstance(obj, dict):
        yield from obj.items()
    elif isinstance(obj, (list, tuple)):
        for idx, value in enumerate(obj):
            yield str(idx), value
    else:
        try:
            import attr
            if attr.has(obj):
                for a in attr.fields(type(obj)):
                    yield a.name, getattr(obj, a.name)
                return
        except ImportError:
            pass
        if hasattr(obj, '__dict__'):
            yield from vars(obj).items()


def obj_walk_through(
    obj: Any,
    should_recurse: Optional[Callable[[List[str], Any], bool]] = None,
    _prefix: Optional[List[str]] = None,
    _visited: Optional[Set[int]] = None,
) -> Iterator[Tuple[List[str], Any]]:
    """Recursively yield ``(path, value_or_type)`` for all nodes in a structure.

    Works with both **instances** (walks actual values) and **types/classes**
    (walks ``__annotations__``).  Paths are lists of string keys compatible
    with :func:`get_at_path`, :func:`set_at_path`, :func:`delete_at_path`, etc.

    Args:
        obj: An instance (dict, list, attrs object, etc.) or a **type** to
            introspect via annotations.
        should_recurse: Optional callable ``(path, child) -> bool``.  Called
            before descending into each child node.  If it returns ``False``
            the child is still **yielded** but its subtree is **not explored**.
            When ``None`` (default), all non-basic-type children are explored.

    Yields:
        Tuple[List[str], Any]: ``(path, node)`` where *path* is a list of
        string keys and *node* is the value (instance mode) or the resolved
        type annotation (type mode).

    Examples:
        Instance walk::

            >>> list(obj_walk_through({'a': {'b': 1}}))
            [(['a'], {'b': 1}), (['a', 'b'], 1)]

        Type walk::

            >>> from attr import attrs, attrib
            >>> @attrs(slots=True)
            ... class Inner:
            ...     data: str = attrib(default='')
            >>> @attrs(slots=True)
            ... class Outer:
            ...     inner: Inner = attrib(factory=Inner)
            >>> list(obj_walk_through(Outer))
            [(['inner'], <class 'Inner'>), (['inner', 'data'], <class 'str'>)]

        List walk::

            >>> list(obj_walk_through([10, [20, 30]]))
            [(['0'], 10), (['1'], [20, 30]), (['1', '0'], 20), (['1', '1'], 30)]

        Controlled recursion::

            >>> list(obj_walk_through({'a': {'b': 1}}, should_recurse=lambda p, v: False))
            [(['a'], {'b': 1})]
    """
    if _prefix is None:
        _prefix = []
    if _visited is None:
        _visited = set()

    # Cycle guard for type walks: track ancestor types on the current path
    # so the same type at sibling paths (DAG) is still explored, but true
    # cycles (A → B → A) are stopped.
    is_type = isinstance(obj, type)
    obj_id = id(obj)
    if is_type:
        if obj_id in _visited:
            return
        _visited = _visited | {obj_id}  # copy — scoped to this branch

    for key, child in _iter_fields(obj):
        child_path = _prefix + [key]
        yield child_path, child
        # Recurse — skip basic types for performance
        if not isinstance(child, (str, int, float, bool, type(None), bytes)):
            if should_recurse is not None and not should_recurse(child_path, child):
                continue
            yield from obj_walk_through(child, should_recurse, _prefix=child_path, _visited=_visited)


# endregion


# region Fuzzy path resolution


def _generate_split_candidates(parts, longest_first=True):
    """Generate all possible dot-path candidates from a list of parts.

    For parts ["a", "b", "c"], generates:
    - "a.b.c" (all split — deepest)
    - "a.b_c" (merge last two)
    - "a_b.c" (merge first two)
    - "a_b_c" (no split — shallowest)

    Args:
        parts: List of string parts from splitting the key.
        longest_first: If True, deepest paths come first.

    Returns:
        List of dot-separated path strings.
    """
    if len(parts) <= 1:
        return ["_".join(parts)]

    n = len(parts)
    candidates = []
    for mask in range(1 << (n - 1)):
        segments = [parts[0]]
        for i in range(1, n):
            if mask & (1 << (i - 1)):
                segments.append(parts[i])
            else:
                segments[-1] = segments[-1] + "_" + parts[i]
        candidates.append(".".join(segments))

    candidates.sort(key=lambda c: c.count("."), reverse=longest_first)
    return candidates


def resolve_fuzzy_path(data, key, path_part_sep="_", longest_first=True):
    """Resolve a separator-delimited key to a dot-path in a nested dict.

    Tries all possible split points and returns the first matching path.

    Args:
        data: Nested dict to search.
        key: The key to resolve (e.g., "employee_mindset").
        path_part_sep: Separator in the key (default "_").
        longest_first: If True, tries deepest paths first.

    Returns:
        The resolved dot-path string, or None if no match found.

    Examples:
        >>> data = {"employee": {"mindset": {"paradigm": "..."}}}
        >>> resolve_fuzzy_path(data, "employee_mindset")
        'employee.mindset'
        >>> resolve_fuzzy_path(data, "employee_mindset_paradigm")
        'employee.mindset.paradigm'
    """
    parts = key.split(path_part_sep)
    if len(parts) <= 1:
        return key if has_path(data, key) else None

    for candidate in _generate_split_candidates(parts, longest_first=longest_first):
        if has_path(data, candidate):
            return candidate
    return None


def get_at_path_fuzzy(data, path, default=MISSING, path_part_sep="_", match_mode="longest"):
    """Get a value using fuzzy underscore-to-dot path resolution.

    Like get_at_path but tries all possible split points of an
    underscore-separated key to find a matching nested path.

    Args:
        data: Nested dict/list structure.
        path: An underscore-separated key (e.g., "employee_mindset").
        default: Value to return if no match found.
        path_part_sep: Separator in the path (default "_").
        match_mode: "longest" (deepest path first) or "shortest".

    Returns:
        The value at the resolved path, or default.
    """
    resolved = resolve_fuzzy_path(
        data, path, path_part_sep=path_part_sep,
        longest_first=(match_mode == "longest"),
    )
    if resolved is not None:
        return get_at_path(data, resolved, default=default)
    if default is MISSING:
        raise KeyError(f"No fuzzy match for {path!r} in data")
    return default


def set_at_path_fuzzy(data, path, value, path_part_sep="_", match_mode="longest", create_if_missing=True):
    """Set a value using fuzzy underscore-to-dot path resolution.

    Like set_at_path but resolves underscore-separated keys to nested paths.
    If no existing path matches and create_if_missing is True, sets as a
    top-level key.

    Args:
        data: Nested dict structure.
        path: An underscore-separated key (e.g., "employee_mindset").
        value: Value to set.
        path_part_sep: Separator in the path (default "_").
        match_mode: "longest" (deepest path first) or "shortest".
        create_if_missing: If True and no match found, create as top-level key.
    """
    resolved = resolve_fuzzy_path(
        data, path, path_part_sep=path_part_sep,
        longest_first=(match_mode == "longest"),
    )
    if resolved is not None:
        set_at_path(data, resolved, value)
    elif create_if_missing:
        data[path] = value
    else:
        raise KeyError(f"No fuzzy match for {path!r} in data")


# endregion
