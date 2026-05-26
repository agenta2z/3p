class HybridSetAndDict:
    """
    A hybrid data structure that treats keys with None values like a set
    and keys with non-None values like a dictionary.

    - If you do ``hybrid[key] = None``, then ``key`` is effectively stored
      in the internal *set* portion.
    - If you do ``hybrid[key] = value`` (where ``value`` is not None), it is
      stored in the internal *dict* portion.
    - Checking membership with ``key in hybrid`` looks in both.
    - Getting ``hybrid[key]`` returns ``True`` (or ``None`` if ``set_portion_value``
      is set to ``None``) if ``key`` is in the set portion, otherwise it returns
      the value from the dict portion.
    - Deleting a key (``del hybrid[key]``) removes it from whichever portion
      it resides in.

    This structure can be useful when you want to handle presence/absence
    for certain keys as a set, while also storing additional data for other keys
    in a dictionary.

    Args:
        set_class (type, optional): A callable (like ``set``) used to create
            the internal set for None-valued keys. Defaults to the built-in ``set``.
        dict_class (type, optional): A callable (like ``dict``) used to create
            the internal dict for non-None-valued keys. Defaults to the built-in ``dict``.
        set_portion_value: The value returned when accessing a key in the set
            portion. Defaults to ``True`` so that ``if hybrid[key]`` passes.
            Set to ``None`` if you prefer sentinel/existence-check semantics.

    Examples:
        >>> from pprint import pprint
        >>> hsd = HybridSetAndDict()
        >>> hsd["apple"] = None          # 'apple' goes to the set portion
        >>> "apple" in hsd
        True

        >>> hsd["banana"] = "yellow"    # 'banana' goes to the dict portion
        >>> "banana" in hsd
        True
        >>> hsd["banana"]
        'yellow'

        >>> hsd["apple"]
        True

        >>> len(hsd)
        2

        >>> sorted(hsd.items())         # show all (key, value) pairs
        [('apple', True), ('banana', 'yellow')]
        >>> "apple" in hsd
        True

        >>> # Remove 'apple' from the structure
        >>> del hsd["apple"]
        >>> "apple" in hsd
        False

        >>> # Using get() behaves like dict.get(): returns True if set-portion,
        >>> # or the stored value, or a default if not found at all.
        >>> hsd.get("banana")
        'yellow'
        >>> hsd.get("mango", default="Not Found")
        'Not Found'

        >>> # Using set() to add keys flexibly
        >>> hsd2 = HybridSetAndDict()
        >>> hsd2.set(key="dark_mode")                  # set-portion
        >>> hsd2.set(key="rate_limit", value=100)      # dict-portion
        >>> hsd2.set(keys=["verbose", "debug"])         # multiple set-portion keys
        >>> hsd2["dark_mode"]
        True
        >>> hsd2["rate_limit"]
        100
        >>> "verbose" in hsd2 and "debug" in hsd2
        True
    """

    def __init__(self, set_class=set, dict_class=dict, set_portion_value=True):
        # Internal storage
        self._none_keys = set_class()  # for keys whose value is None
        self._values = dict_class()        # for keys with non-None values
        self._set_portion_value = set_portion_value

    def __setitem__(self, key, value):
        """Set the value for `key`. If value is None, store `key` in the _none_keys set."""
        if value is None:
            # Remove from dict if present
            if key in self._values:
                del self._values[key]
            # Add to set
            self._none_keys.add(key)
        else:
            # Remove from set if present
            if key in self._none_keys:
                self._none_keys.remove(key)
            self._values[key] = value

    def __getitem__(self, key):
        """Get the value for `key`. Returns ``set_portion_value`` if key is in the set portion."""
        if key in self._none_keys:
            return self._set_portion_value
        return self._values[key]  # May raise KeyError if not present

    def __delitem__(self, key):
        """Delete `key` from this structure (set or dict). Raises KeyError if not found."""
        if key in self._none_keys:
            self._none_keys.remove(key)
        else:
            del self._values[key]

    def __contains__(self, key):
        """Check if `key` is in the set or dict portion."""
        return key in self._none_keys or key in self._values

    def __len__(self):
        """Number of total keys (set + dict)."""
        return len(self._none_keys) + len(self._values)

    def set(self, *, key=None, value=None, keys=None):
        """Flexible setter for adding keys and values.

        Args:
            key: A single key to add.
            value: The value for ``key``. If omitted (None), the key is added
                to the set portion.
            keys: An iterable of keys to add to the set portion (no values).
                Cannot be combined with ``key`` or ``value``.

        Raises:
            ValueError: If both ``key`` and ``keys`` are provided, or if
                ``value`` is provided with ``keys``, or if neither ``key``
                nor ``keys`` is provided.
        """
        if key is not None and keys is not None:
            raise ValueError("Cannot specify both 'key' and 'keys'.")
        if keys is not None and value is not None:
            raise ValueError("Cannot specify 'value' with 'keys'.")
        if key is None and keys is None:
            raise ValueError("Must specify either 'key' or 'keys'.")

        if keys is not None:
            for k in keys:
                self[k] = None
        else:
            self[key] = value

    def items(self):
        """Iterate over (key, value) pairs. The set-portion keys yield (key, ``set_portion_value``)."""
        for k in self._none_keys:
            yield (k, self._set_portion_value)
        for k, v in self._values.items():
            yield (k, v)

    def keys(self):
        """Iterate over all keys (from the set portion and the dict portion)."""
        yield from self._none_keys
        yield from self._values.keys()

    def values(self):
        """Iterate over all values. The set-portion keys yield ``set_portion_value``."""
        for _ in self._none_keys:
            yield self._set_portion_value
        yield from self._values.values()

    def get(self, key, default=None):
        """Like dict.get(): Returns ``set_portion_value`` if key is in the set portion, else the dict value or `default`."""
        if key in self._none_keys:
            return self._set_portion_value
        return self._values.get(key, default)

    def __repr__(self):
        """String representation combining set-portion and dict-portion into a single dict-like view."""
        combined = dict(self.items())
        return f"{self.__class__.__name__}({combined})"
