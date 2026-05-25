"""Map helper utilities — extracted functions."""

from enum import Enum
from typing import (
    Any,
    Callable,
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

from rankevolve.src.utils.common_utils.typing_helper import iterable__


class map_as_callable:
    """
    Wrapper to make a mapping callable for attribute access.

    Examples:
        >>> m = map_as_callable({'a': 1, 'b': 2})
        >>> m('a')
        1
        >>> m.a
        1
    """

    def __init__(self, mapping: Mapping):
        self._mapping = mapping

    def __call__(self, key, default=None):
        return self._mapping.get(key, default)

    def __getattr__(self, key):
        if key.startswith("_"):
            return super().__getattribute__(key)
        return self._mapping.get(key)

    def __getitem__(self, key):
        return self._mapping[key]

    def get(self, key, default=None):
        return self._mapping.get(key, default)


def _get_key_val_tuple(obj, ignore_none_values=False, ignore_empty_values=False):
    """Helper to extract key-value tuples from various object types."""
    try:
        import attr

        if attr.has(obj):
            return attr.asdict(obj).items()
    except ImportError:
        pass

    if isinstance(obj, Mapping):
        return obj.items()
    elif hasattr(obj, "__dict__"):
        return obj.__dict__.items()
    elif hasattr(obj, "_asdict"):  # namedtuple
        return obj._asdict().items()
    else:
        return []


def dict_(
    obj: Any = None,
    ignore_none_values: bool = False,
    ignore_empty_values: bool = False,
    **kwargs,
) -> Dict:
    """
    Convert an object to a dictionary.

    Args:
        obj: Object to convert.
        ignore_none_values: Whether to ignore None values.
        ignore_empty_values: Whether to ignore empty values.
        **kwargs: Additional key-value pairs to include.

    Returns:
        Dictionary representation of the object.

    Examples:
        >>> dict_({'a': 1, 'b': None}, ignore_none_values=True)
        {'a': 1}
        >>> dict_(None)
        {}
    """
    if obj is None:
        result = {}
    elif isinstance(obj, dict):
        result = obj.copy()
    else:
        try:
            result = dict(
                _get_key_val_tuple(obj, ignore_none_values, ignore_empty_values)
            )
        except (TypeError, ValueError):
            result = {}

    result.update(kwargs)

    if ignore_none_values:
        result = {k: v for k, v in result.items() if v is not None}

    if ignore_empty_values:
        result = {
            k: v
            for k, v in result.items()
            if v is not None and v != "" and v != [] and v != {}
        }

    return result


def _get_(obj, key, default=None):
    """Helper for get_ function."""
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    elif hasattr(obj, key):
        return getattr(obj, key, default)
    elif hasattr(obj, "__getitem__"):
        try:
            return obj[key]
        except (KeyError, IndexError, TypeError):
            return default
    return default


def get_(obj: Any, key: Union[str, Callable], default: Any = None) -> Any:
    """
    Get a value from an object by key, attribute, or callable.

    Args:
        obj: Object to get value from.
        key: Key, attribute name, or callable to extract value.
        default: Default value if key not found.

    Returns:
        The extracted value or default.

    Examples:
        >>> get_({'a': 1}, 'a')
        1
        >>> get_({'a': 1}, 'b', default=2)
        2
    """
    if callable(key):
        try:
            return key(obj)
        except Exception:
            return default
    elif isinstance(key, str) and "." in key:
        # Handle dot notation
        parts = key.split(".")
        for part in parts:
            obj = _get_(obj, part, default)
            if obj is default:
                return default
        return obj
    else:
        return _get_(obj, key, default)


def get__(
    obj: Any,
    keys: Union[str, Sequence[str]],
    default: Any = None,
) -> Any:
    """
    Get a value from an object using a sequence of keys.

    Args:
        obj: Object to get value from.
        keys: Sequence of keys to traverse.
        default: Default value if not found.

    Returns:
        The extracted value or default.
    """
    if isinstance(keys, str):
        keys = [keys]

    from rankevolve.src.utils.common_utils.iter_helper import flatten_iter

    keys = list(flatten_iter(keys, non_atom_types=(List,)))

    for key in keys:
        obj = _get_(obj, key, default)
        if obj is default:
            return default
    return obj


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
    1. Navigate to a space using ``space_key`` (optional hierarchical path)
    2. Lookup ``item_key`` in that space with fallback to ``default_item_key``

    Args:
        d: The mapping (dict) to look up values in.
        space_key: Optional hierarchical namespace key (e.g., "plan/main").
            If provided and exists as a key in ``d``, the corresponding sub-mapping
            is used for the item lookup. If ``None`` or empty, the root ``d`` is used.
        item_key: The key to look up within the resolved space.
        default_item_key: Fallback key if ``item_key`` is not found. Defaults to
            ``"default"``. Set to ``None`` to disable fallback.

    Returns:
        The resolved value, or ``None`` if not found.

    Examples:
        >>> templates = {"plan": {"initial": "Plan initial", "default": "Plan default"}}
        >>> get_by_spaced_key(templates, "plan", "initial")
        'Plan initial'
        >>> get_by_spaced_key(templates, "plan", "missing")
        'Plan default'
        >>> get_by_spaced_key(templates, "plan", "missing", default_item_key=None) is None
        True
        >>> get_by_spaced_key(templates, None, "plan")
        {'initial': 'Plan initial', 'default': 'Plan default'}
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

    # Step 2: Lookup item with fallback to default
    value = None
    if template_space is not None and item_key is not None:
        # Try item_key first
        value = _get_(template_space, item_key)
        # If not found and we have a fallback, try default_item_key
        if value is None and default_item_key and item_key != default_item_key:
            value = _get_(template_space, default_item_key)

    return value


def split_dict(
    d: Dict,
    keys: Iterable = None,
    key_filter: Callable = None,
    reverse: bool = False,
) -> Tuple[Dict, Dict]:
    """
    Split a dictionary into two based on keys or a filter.

    Args:
        d: Dictionary to split.
        keys: Keys to include in the first dict (or exclude if reverse=True).
        key_filter: Function to filter keys for first dict.
        reverse: If True and keys is provided, the first dict gets items whose
            keys are NOT in `keys`, and the second dict gets items whose keys
            ARE in `keys`. Defaults to False.

    Returns:
        Tuple of (matched dict, unmatched dict).
    """
    if keys is not None:
        keys = set(keys) if keys else set()
        if reverse:
            matched = {k: v for k, v in d.items() if k not in keys}
            unmatched = {k: v for k, v in d.items() if k in keys}
        else:
            matched = {k: v for k, v in d.items() if k in keys}
            unmatched = {k: v for k, v in d.items() if k not in keys}
    elif key_filter is not None:
        matched = {k: v for k, v in d.items() if key_filter(k)}
        unmatched = {k: v for k, v in d.items() if not key_filter(k)}
    else:
        matched = d.copy()
        unmatched = {}
    return matched, unmatched


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
    mappings: Iterable[Mapping],
    use_tqdm: bool = False,
    recursive: bool = False,
    concatenate_lists: bool = False,
    union_sets: bool = False,
    sum_counters: bool = False,
) -> Dict:
    """
    Merge multiple mappings into one.

    Args:
        mappings: Iterable of mappings to merge.
        use_tqdm: Whether to show progress bar.
        recursive: If True, recursively merge nested dicts instead of
            overriding. When False (default), behaves like dict.update().
        concatenate_lists: If True (requires recursive=True), concatenate
            list values instead of overriding.
        union_sets: If True (requires recursive=True), union set values
            instead of overriding.
        sum_counters: If True (requires recursive=True), sum numeric values
            instead of overriding.

    Returns:
        Merged dictionary.

    Examples:
        >>> merge_mappings([{'a': 1}, {'b': 2}])
        {'a': 1, 'b': 2}
        >>> merge_mappings([{'a': [1]}, {'a': [2]}], recursive=True, concatenate_lists=True)
        {'a': [1, 2]}
        >>> merge_mappings([{'x': {'a': 1}}, {'x': {'b': 2}}], recursive=True)
        {'x': {'a': 1, 'b': 2}}
    """
    result: Dict = {}
    for mapping in mappings:
        if recursive:
            result = _deep_merge_two(
                result,
                dict(mapping),
                concatenate_lists=concatenate_lists,
                union_sets=union_sets,
                sum_counters=sum_counters,
            )
        else:
            result.update(mapping)
    return result


def merge_list_valued_mappings(
    mappings: Iterable[Mapping[Any, List]],
) -> Dict[Any, List]:
    """
    Merge mappings where values are lists.

    Args:
        mappings: Iterable of mappings with list values.

    Returns:
        Merged dictionary with concatenated lists.
    """
    result = {}
    for mapping in mappings:
        for key, value in mapping.items():
            if key not in result:
                result[key] = []
            if isinstance(value, list):
                result[key].extend(value)
            else:
                result[key].append(value)
    return result


def merge_set_valued_mappings(
    mappings: Iterable[Mapping[Any, set]],
) -> Dict[Any, set]:
    """
    Merge mappings where values are sets.

    Args:
        mappings: Iterable of mappings with set values.

    Returns:
        Merged dictionary with unioned sets.
    """
    result = {}
    for mapping in mappings:
        for key, value in mapping.items():
            if key not in result:
                result[key] = set()
            if isinstance(value, set):
                result[key].update(value)
            else:
                result[key].add(value)
    return result


def merge_counter_valued_mappings(
    mappings: Iterable[Mapping[Any, int]],
) -> Dict[Any, int]:
    """
    Merge mappings where values are counts.

    Args:
        mappings: Iterable of mappings with int values.

    Returns:
        Merged dictionary with summed counts.
    """
    result = {}
    for mapping in mappings:
        for key, value in mapping.items():
            if key not in result:
                result[key] = 0
            result[key] += value
    return result


def _add_count(result: Dict, items, count: int = 1):
    """Helper to add counts to result dict."""
    if iterable__(items):
        for item in items:
            _add_count(result, item, count)
    else:
        if items not in result:
            result[items] = 0
        result[items] += count


def count_or_accumulate(
    items: Iterable,
    count_each: int = 1,
) -> Dict:
    """
    Count occurrences of items.

    Args:
        items: Items to count.
        count_each: Count to add for each item.

    Returns:
        Dictionary of item counts.
    """
    result = {}
    for item in items:
        _add_count(result, item, count_each)
    return result


def sum_dicts(*dicts) -> Dict:
    """
    Sum multiple dictionaries with numeric values.

    Args:
        *dicts: Dictionaries to sum.

    Returns:
        Dictionary with summed values.
    """
    return count_or_accumulate([d for d in dicts if d], count_each=1)


# ---------------------------------------------------------------------------
# MISSING sentinel
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# dict__ — deep object-to-dict conversion
# ---------------------------------------------------------------------------


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
        _obj_cache: Internal parameter to keep track of already processed objects
            to handle circular references.

    Returns:
        A dictionary representation of the object.

    Raises:
        TypeError: If fallback=None and object cannot be converted to dict.

    Examples:
        >>> dict__(42)
        42
        >>> dict__("hello")
        'hello'
        >>> dict__({'a': 1, 'b': 2})
        {'a': 1, 'b': 2}
    """
    from rankevolve.src.utils.common_utils.typing_helper import is_basic_type, is_named_tuple

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
                result = repr(obj)
                _obj_cache[obj_id] = result
                return result
            if recursive:
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


# ---------------------------------------------------------------------------
# Key path operations
# ---------------------------------------------------------------------------


def parse_key_path(path, sep='.', escape_char='\\'):
    """
    Parses a dot-separated key path string into a list of keys.
    Supports escaped separators for keys that contain the separator character.
    If `path` is already a list or tuple, returns it as a list unchanged.

    Args:
        path: A dot-separated string path (e.g. "a.b.c") or a list/tuple of keys.
        sep: The separator character. Defaults to '.'.
        escape_char: The escape character for literal separators in key names.

    Returns:
        A list of string keys.

    Examples:
        >>> parse_key_path('a.b.c')
        ['a', 'b', 'c']
        >>> parse_key_path('a')
        ['a']
        >>> parse_key_path(['a', 'b', 'c'])
        ['a', 'b', 'c']
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

    Args:
        data: A nested dict/list structure.
        path: A dot-separated string path or a list/tuple of keys.

    Returns:
        True if the path exists (even if the value is None), False otherwise.

    Examples:
        >>> has_path({'a': {'b': 1}}, 'a.b')
        True
        >>> has_path({'a': {'b': 1}}, 'a.c')
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

    Args:
        data: A nested dict/list structure.
        path: A dot-separated string path or a list/tuple of keys.
        default: Value to return if the path is missing.
            If not provided (MISSING), raises KeyError on missing path.

    Returns:
        The value at the path, or `default` if the path is missing.

    Examples:
        >>> get_at_path({'a': {'b': 1}}, 'a.b')
        1
        >>> get_at_path({'a': {'b': 1}}, 'a.c', default='nope')
        'nope'
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

    Examples:
        >>> d = {'a': {'b': 1}}
        >>> set_at_path(d, 'a.b', 2)
        >>> d
        {'a': {'b': 2}}
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

    Examples:
        >>> d = {'a': {'b': 1, 'c': 2}}
        >>> delete_at_path(d, 'a.b')
        >>> d
        {'a': {'c': 2}}
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


# ---------------------------------------------------------------------------
# Object walk-through
# ---------------------------------------------------------------------------


def _resolve_annotation_type(annotation) -> Optional[Type]:
    """Unwrap ``Optional[X]`` / ``Union[X, None]`` to the base concrete type."""
    origin = getattr(annotation, '__origin__', None)
    if origin is Union:
        args = [a for a in annotation.__args__ if a is not type(None)]
        return args[0] if len(args) == 1 else None
    return annotation if isinstance(annotation, type) else None


def _iter_fields(obj) -> Iterator[Tuple[str, Any]]:
    """Yield ``(field_name, value_or_type)`` pairs for *obj*.

    - **type/class**: yields ``(name, annotation_type)`` from ``__annotations__``.
    - **dict**: yields ``(key, value)`` pairs.
    - **list/tuple**: yields ``(str(index), element)`` pairs.
    - **attrs instance**: yields ``(attr.name, value)`` via ``attr.fields`` + ``getattr``.
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

    Args:
        obj: An instance (dict, list, attrs object, etc.) or a **type** to
            introspect via annotations.
        should_recurse: Optional callable ``(path, child) -> bool``.  Called
            before descending into each child node.

    Yields:
        Tuple[List[str], Any]: ``(path, node)`` where *path* is a list of
        string keys.

    Examples:
        >>> list(obj_walk_through({'a': {'b': 1}}))
        [(['a'], {'b': 1}), (['a', 'b'], 1)]
    """
    if _prefix is None:
        _prefix = []
    if _visited is None:
        _visited = set()

    is_type = isinstance(obj, type)
    obj_id = id(obj)
    if is_type:
        if obj_id in _visited:
            return
        _visited = _visited | {obj_id}

    for key, child in _iter_fields(obj):
        child_path = _prefix + [key]
        yield child_path, child
        if not isinstance(child, (str, int, float, bool, type(None), bytes)):
            if should_recurse is not None and not should_recurse(child_path, child):
                continue
            yield from obj_walk_through(child, should_recurse, _prefix=child_path, _visited=_visited)


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
    # Generate all possible split point combinations
    # Each split point between parts[i] and parts[i+1] is either a "." (split) or "_" (merge)
    candidates = []
    for mask in range(1 << (n - 1)):
        segments = [parts[0]]
        for i in range(1, n):
            if mask & (1 << (i - 1)):
                # Split at this point (use ".")
                segments.append(parts[i])
            else:
                # Merge with previous (use "_")
                segments[-1] = segments[-1] + "_" + parts[i]
        candidates.append(".".join(segments))

    # Sort by number of dots (depth)
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
        # No separator in key — check as-is
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

    Examples:
        >>> data = {"employee": {"mindset": "think big"}}
        >>> get_at_path_fuzzy(data, "employee_mindset")
        'think big'
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

    Examples:
        >>> data = {"employee": {"mindset": "old"}}
        >>> set_at_path_fuzzy(data, "employee_mindset", "new")
        >>> data["employee"]["mindset"]
        'new'
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
