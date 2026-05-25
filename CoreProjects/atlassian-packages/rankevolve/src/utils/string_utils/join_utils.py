"""Join utilities — extracted join_ only."""

from typing import Any, Iterable, Optional

from rankevolve.src.utils.common_utils.typing_helper import solve_nested_singleton_tuple_list


def join_(
    strs: Iterable[Any],
    sep: str = "\n",
    empty_str_sub: Optional[str] = None,
    none_str_sub: Optional[str] = None,
    keep_empty_str: bool = True,
    keep_none: bool = True,
    prefix: str = None,
    suffix: str = None,
    item_prefix: str = None,
    item_suffix: str = None,
) -> str:
    """
    Joins a collection of strings with a separator.

    Args:
        strs: The strings to join.
        sep: The separator between strings.
        empty_str_sub: Substitute empty strings with this value.
        none_str_sub: Substitute None values with this value.
        keep_empty_str: Whether to keep empty strings in the result.
        keep_none: Whether to keep None values in the result.
        prefix: Prefix to add to the entire result.
        suffix: Suffix to add to the entire result.
        item_prefix: Prefix to add to each item.
        item_suffix: Suffix to add to each item.

    Returns:
        The joined string.

    Examples:
        >>> join_(['a', 'b', 'c'])
        'a\\nb\\nc'
        >>> join_(['a', 'b', 'c'], sep=', ')
        'a, b, c'
        >>> join_(['a', '', 'c'], keep_empty_str=False)
        'a\\nc'
        >>> join_(['a', None, 'c'], keep_none=False)
        'a\\nc'
        >>> join_(['a', 'b'], prefix='[', suffix=']')
        '[a\\nb]'
        >>> join_(['a', 'b'], item_prefix='- ')
        '- a\\n- b'
    """
    strs = solve_nested_singleton_tuple_list(strs)

    result_parts = []
    for s in strs:
        if s is None:
            if not keep_none:
                continue
            if none_str_sub is not None:
                s = none_str_sub
            else:
                s = ""
        else:
            s = str(s)
            if s == "":
                if not keep_empty_str:
                    continue
                if empty_str_sub is not None:
                    s = empty_str_sub

        if item_prefix:
            s = item_prefix + s
        if item_suffix:
            s = s + item_suffix

        result_parts.append(s)

    result = sep.join(result_parts)

    if prefix:
        result = prefix + result
    if suffix:
        result = result + suffix

    return result
