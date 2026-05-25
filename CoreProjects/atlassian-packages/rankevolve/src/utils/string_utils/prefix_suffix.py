"""String utils prefix/suffix functions — extracted add_prefix only."""

from typing import Any, Optional


def add_prefix(
    s: str, prefix: Any, sep: Optional[str] = "_", avoid_repeat: bool = False
) -> str:
    """
    Adds a prefix to the beginning of the current string.

    Args:
        s: the current string.
        prefix: the prefix; if this argument is not a string,
            it will be converted to string by `str(prefix)`.
        sep: when non-empty, this is the separator between the prefix and the current string;
            this argument is ignored if the prefix already ends with this separator.
        avoid_repeat: True if not adding the prefix if `s` already starts with the prefix.

    Returns: if `prefix` is not empty, then a new string with the current string plus the prefix;
        otherwise the input string `s` itself.

    Examples:
        >>> assert add_prefix('', prefix='global', sep='_') == ''
        >>> assert add_prefix('name', prefix='global', sep='_') == 'global_name'
        >>> assert add_prefix('name', prefix='global_', sep='_') == 'global_name'
        >>> assert add_prefix('name', prefix='', sep='_') == 'name'
        >>> assert add_prefix('name', prefix=None, sep='_') == 'name'
        >>> assert add_prefix('name', prefix='global', sep='') == 'globalname'
        >>> assert add_prefix('name', prefix='global_', sep=None) == 'global_name'
        >>> assert add_prefix('global_name', prefix='global', sep='_', avoid_repeat=True) == 'global_name'
        >>> assert add_prefix('global_name', prefix='global', sep='_', avoid_repeat=False) == 'global_global_name'
    """
    if s and prefix is not None and prefix != "":
        prefix = str(prefix)
        if sep and not prefix.endswith(sep):
            prefix += sep
        if not (avoid_repeat and s.startswith(prefix)):
            return prefix + s
    return s
