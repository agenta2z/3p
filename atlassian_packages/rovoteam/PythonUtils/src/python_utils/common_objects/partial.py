"""
Enhanced ``functools.partial`` with parameter remapping.
"""
from collections.abc import Mapping


class Partial:
    """Callable wrapper that stores default kwargs and remaps parameter names.

    An enhanced ``functools.partial`` that supports declarative parameter
    renaming via :attr:`_PARAM_MAP` and value extraction from the first
    positional argument via :attr:`_FIRST_ARG_VALUES_TO_PARAM_MAP`.

    Subclasses override these class-level dicts to define mappings.
    The base class can also be used directly by passing ``param_map``
    and/or ``first_arg_values_to_param_map`` to the constructor.

    Merge priority (later wins):
        - Class-level defaults (``_PARAM_MAP``, ``_FIRST_ARG_VALUES_TO_PARAM_MAP``)
        - Constructor overrides (``param_map``, ``first_arg_values_to_param_map``)
        - Baked-in kwargs (constructor ``**kwargs``)
        - Call-time kwargs (``__call__(**kwargs)``)

    Attributes:
        func: The wrapped callable.
        keywords: A *copy* of the baked-in keyword arguments
            (``functools.partial``-compatible interface).

    Examples:
        Plain usage (no remapping, behaves like ``functools.partial``):

        >>> p = Partial(sorted, reverse=True)
        >>> p([3, 1, 2])
        [3, 2, 1]
        >>> p.keywords
        {'reverse': True}

        Ad-hoc remapping via constructor:

        >>> def greet(name, greeting='Hello'):
        ...     return f'{greeting}, {name}!'
        >>> p = Partial(greet, param_map={'salutation': 'greeting'})
        >>> p('World', salutation='Hi')
        'Hi, World!'

        Subclass with declarative mapping:

        >>> class MyPartial(Partial):
        ...     _PARAM_MAP = {'group': 'subfolder'}
        >>> p = MyPartial(lambda **kw: kw, file_path='log.json')
        >>> p(group='iter_01')
        {'file_path': 'log.json', 'subfolder': 'iter_01'}

        First-arg value extraction:

        >>> p = Partial(
        ...     lambda *a, **kw: kw,
        ...     first_arg_values_to_param_map={'type': 'log_type'},
        ... )
        >>> p({'type': 'Error', 'item': 'oops'})
        {'log_type': 'Error'}
    """

    _PARAM_MAP = {}
    _FIRST_ARG_VALUES_TO_PARAM_MAP = {}

    def __init__(self, func, *, param_map=None, first_arg_values_to_param_map=None, **kwargs):
        self._func = func
        self._kwargs = kwargs
        # Instance-level overrides class-level (later wins).
        if param_map is not None:
            self._param_map = {**self._PARAM_MAP, **param_map}
        else:
            self._param_map = self._PARAM_MAP

        if first_arg_values_to_param_map is not None:
            self._first_arg_values_to_param_map = {**self._FIRST_ARG_VALUES_TO_PARAM_MAP, **first_arg_values_to_param_map}
        else:
            self._first_arg_values_to_param_map = self._FIRST_ARG_VALUES_TO_PARAM_MAP

    @property
    def func(self):
        return self._func

    @property
    def keywords(self):
        """Baked-in keyword args (``functools.partial``-compatible interface)."""
        return dict(self._kwargs)

    def __call__(self, *args, **kwargs):
        # Apply parameter remapping on kwargs.
        for src, dst in self._param_map.items():
            if src in kwargs:
                if dst not in kwargs:
                    kwargs[dst] = kwargs.pop(src)
                else:
                    kwargs.pop(src)  # dst already present, discard src

        # Extract values from first positional arg (if it's a Mapping)
        # and inject as kwargs (only if not already present in kwargs).
        if args and self._first_arg_values_to_param_map:
            args0 = args[0]
            if isinstance(args0, Mapping):
                for src, dst in self._first_arg_values_to_param_map.items():
                    if src in args0 and dst not in kwargs:
                        kwargs[dst] = args0[src]

        # Merge baked-in defaults with call-time kwargs (call-time wins).
        merged = {**self._kwargs, **kwargs}
        return self._func(*args, **merged)

    def __repr__(self):
        func_name = getattr(self._func, '__name__', repr(self._func))
        cls_name = type(self).__name__
        params = ', '.join(f'{k}={v!r}' for k, v in self._kwargs.items())
        if params:
            return f'{cls_name}({func_name}, {params})'
        return f'{cls_name}({func_name})'
