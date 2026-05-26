class NamedTuple:
    """
    Allows retrieving a value from a Namedtuple class by index,
    and use `len` to get the number of slots.
    
    Examples:
        >>> class Example(NamedTuple):
        ...     __slots__ = ('full_name', 'short_name')
        ...
        ...     def __init__(self, full_name='', short_name=''):
        ...        self.full_name = full_name
        ...        self.short_name = short_name
        ...
        >>> a = Example('united states', 'us')
        >>> a[0]
        'united states'
        >>> len(a)
        2
    """

    def __getitem__(self, item):
        _attr = self.__slots__[item]
        if isinstance(_attr, str):
            return getattr(self, _attr)
        else:
            # `_attr` might be a slice
            return tuple(getattr(self, x) for x in _attr)

    def __len__(self):
        return len(self.__slots__)
