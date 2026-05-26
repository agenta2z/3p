from typing import Callable, Union, Optional, Sequence, Type


def getattr_or_new(obj, name: str, default_factory: Optional[Callable]=None):
    """
    Retrieves an attribute from an object if it exists; otherwise, creates it with a value
    provided by a default factory, sets it on the object, and returns it.

    Args:
        obj (object): The object to retrieve or set the attribute on.
        name (str): The name of the attribute to retrieve or create.
        default_factory (Callable, optional): A callable that returns the default value to set
            if the attribute does not exist. If `None`, the default value will be `None`.

    Returns:
        Any: The existing attribute value if it exists, or the new value created by `default_factory`.

    Examples:
        >>> class Example:
        ...     pass
        >>> example = Example()

        # Attribute doesn't exist; creates and returns it using default_factory
        >>> queue = getattr_or_new(example, '_queue', list)
        >>> queue
        []

        # Attribute now exists; retrieves it
        >>> queue.append(1)
        >>> getattr_or_new(example, '_queue', list)
        [1]

        # Attribute doesn't exist; creates with default_factory as None
        >>> setattr(example, '_value', None)
        >>> value = getattr_or_new(example, '_missing_attr', None)
        >>> value is None
        True
    """
    if not hasattr(obj, name):
        value = default_factory() if default_factory is not None else None
        setattr(obj, name, value)
        return value
    return getattr(obj, name)


def getattr_(_o, name, default):
    """
    Safely retrieves an attribute from an object. If the attribute does not exist or its value is falsy,
    the provided default value is returned.

    Args:
        _o (object): The object to retrieve the attribute from.
        name (str): The name of the attribute to retrieve.
        default (Any): The default value to return if the attribute is not found or is falsy.

    Returns:
        Any: The value of the attribute, or the default value if the attribute is not found or is falsy.

    Notes:
        - Unlike the built-in `getattr`, which only returns the default value when the attribute does not exist,
          `getattr_` also returns the default value when the attribute exists but evaluates to `False`
          (e.g., `None`, `0`, `False`, `''`).

        - Use `getattr` if you need to distinguish between a missing attribute and an attribute with a falsy value.
          Use `getattr_` when you want to handle both cases the same way.

    Examples:
        >>> class Example:
        ...     attr = "value"
        >>> example = Example()
        >>> getattr_(example, "attr", "default")
        'value'
        >>> getattr_(example, "missing_attr", "default")
        'default'
        >>> class ExampleWithFalsy:
        ...     attr = 0
        >>> example_falsy = ExampleWithFalsy()
        >>> getattr_(example_falsy, "attr", "default")
        'default'
        >>> getattr(example_falsy, "attr", "default")  # Standard getattr behavior
        0
    """
    return getattr(_o, name, None) or default


def getattr__(_o, name, default, transform: Union[Callable, str] = None, null_set=None):
    """
    Retrieves an attribute from an object with additional functionality for transformations
    and handling null-like values.

    Args:
        _o (object): The object to retrieve the attribute from.
        name (str): The name of the attribute to retrieve.
        default (Any): The default value to return if the attribute is not found, is falsy,
            or is part of `null_set`.
        transform (Union[Callable, str], optional): A transformation to apply to the value
            of the attribute if it exists. If a callable, it is called with the attribute's value.
            If a string, it is formatted with the attribute's value. Defaults to None.
        null_set (set, optional): A set of values to treat as "null" or equivalent to "not found".
            If the attribute's value is in this set, the `default` value is returned. Defaults to None.

    Returns:
        Any: The transformed or original value of the attribute, or the default value if the attribute
        is not found, is falsy, or is in `null_set`.

    Notes:
        - This function extends `getattr_` by allowing transformations on the attribute's value
          and the ability to handle custom "null" values via the `null_set` argument.

    Examples:
        >>> class Example:
        ...     attr = "value"
        ...     attr_none = None
        ...     attr_null = "null_value"
        >>> example = Example()

        # Basic usage (falls back to `getattr_`)
        >>> getattr__(example, "attr", "default")
        'value'
        >>> getattr__(example, "missing_attr", "default")
        'default'

        # Using a callable transform
        >>> getattr__(example, "attr", "default", transform=lambda x: x.upper())
        'VALUE'

        # Using a string transform
        >>> getattr__(example, "attr", "default", transform="Transformed: {}")
        'Transformed: value'

        # Handling null-like values
        >>> getattr__(example, "attr_null", "default", null_set={"null_value"})
        'default'
        >>> getattr__(example, "attr_none", "default", null_set={None})
        'default'

        # Combined usage
        >>> getattr__(example, "attr_null", "default", transform="Transformed: {}", null_set={"null_value"})
        'default'
    """
    if not null_set and transform is None:
        return getattr_(_o, name, default)

    _o = getattr(_o, name, None)
    return (
        transform.format(_o) if (
                transform and isinstance(transform, str)
        )
        else (
            transform(_o)
            if callable(transform)
            else _o
        )
    ) if (
            _o and (not null_set or _o not in null_set)
    ) else default


def hasattr_(_o, name) -> bool:
    return bool(getattr(_o, name, None))


def hasattr__(_o, name, null_set=None):
    if not null_set:
        return hasattr_(_o, name)

    _o = getattr(_o, name, None)
    return _o and _o not in null_set


def setattr_if_none_or_empty(obj, attr: str, val) -> None:
    """
    The same as the build-in function `setattr`,
    with the difference that this function only set the attribute
    if it is None or does not currently exist in the object.

    Args:
        obj: the object to set the attribute.
        attr: the name of the attribute to set.
        val: the value to set for the specified attribute.

    Examples:
        >>> class Point:
        ...     def __init__(self, x, y):
        ...         self.x, self.y = x, y
        >>> p = Point(1, None)
        >>> setattr_if_none_or_empty(p, 'x', 10)
        >>> setattr_if_none_or_empty(p, 'y', 10)
        >>> assert p.x == 1
        >>> assert p.y == 10

    """
    if not getattr(obj, attr, None):
        setattr(obj, attr, val)


def setattr_if_none_or_empty_(obj, attr: str, get_val: Callable) -> None:
    """
    The same as `setattr_if_none_or_empty`,
        but the "value" is a callable `get_val`.
    If the attribute to set is None or does not currently exist in the object,
        then the callable `get_val` is executed to compute the actual value to set.

    The purpose is avoid unnecessary computation of the value.
    Sometime the value is expensive to compute,
    and here we only compute the value if the attribute
    to set does not currently exists_path or has a `None` value.

    Examples:
        >>> class Point:
        ...     def __init__(self, x, y):
        ...         self.x, self.y = x, y
        >>> from math import factorial
        >>> p = Point(1, None)
        >>> get_val = lambda: factorial(10)
        >>> setattr_if_none_or_empty_(p, 'x', get_val)  # get_val will NOT be computed in this line
        >>> setattr_if_none_or_empty_(p, 'y', get_val)  # get_val will be computed in this line
        >>> assert p.x == 1
        >>> assert p.y == get_val()
    """

    if not getattr(obj, attr, None):
        setattr(obj, attr, get_val())


def copy_attrs_from(
    target_instance,
    source_instance,
    target_class: Type = None,
    exclude: Sequence[str] = None,
    include_non_init: bool = False
):
    """
    Copy attribute values from one attrs instance to another.

    Args:
        target_instance: The instance to copy attributes to
        source_instance: The instance to copy attributes from
        target_class: The attrs class to use for determining which attributes to copy.
            If None, uses target_instance.__class__
        exclude: List of attribute names to exclude from copying
        include_non_init: If True, also copies attributes with init=False. Default is False.

    Returns:
        The target_instance with copied attributes

    Examples:
        >>> from attr import attrs, attrib
        >>> @attrs
        ... class Config:
        ...     debug: bool = attrib(default=False)
        ...     log_level: int = attrib(default=20)
        ...     id: str = attrib(default="default_id")
        ...     _internal: int = attrib(default=0, init=False)

        >>> source = Config(debug=True, log_level=10, id="source_id")
        >>> source._internal = 42
        >>> target = Config()

        # Copy all attributes except 'id'
        >>> copy_attrs_from(target, source, exclude=['id'])
        Config(debug=True, log_level=10, id='default_id', _internal=0)
        >>> target.debug
        True
        >>> target.log_level
        10
        >>> target.id
        'default_id'

        # Copy including non-init attributes
        >>> target2 = Config()
        >>> copy_attrs_from(target2, source, include_non_init=True)
        Config(debug=True, log_level=10, id='source_id', _internal=42)
        >>> target2._internal
        42
    """
    import attr

    if target_class is None:
        target_class = target_instance.__class__

    if exclude is None:
        exclude = []

    # Get all attrs fields for the target class
    fields = attr.fields(target_class)

    for field in fields:
        # Skip excluded attributes
        if field.name in exclude:
            continue

        # Skip non-init fields unless explicitly requested
        if not field.init and not include_non_init:
            continue

        # Copy the attribute value if it exists in the source instance
        if hasattr(source_instance, field.name):
            setattr(target_instance, field.name, getattr(source_instance, field.name))

    return target_instance
