from os import path, PathLike

from python_utils.common_utils.iter_helper import product__
from python_utils.common_utils.typing_helper import str_


def join_(*path_parts, ignore_empty=True):
    """
    Joins `path_parts` into a path. This method allows a path part be an iterable, and will output
    a Cartesian-product join of the path parts. None-string path parts will be converted to string.

    Set `ignore_empty` True to ignore empty path parts in `path_parts`,
    such as None or empty string.

    Examples:
        >>> assert join_('root', 'a', 'b') == path.join('root', 'a', 'b')
        >>> assert join_('root', '', 'b') == path.join('root', 'b')
        >>> assert join_('root', None, 'b') == path.join('root', 'b')
        >>> assert join_('root', 1, True) == path.join('root', '1', 'True')
        >>> assert join_('root', ['a', 'b'], 'c') == [
        ...    path.join('root', 'a', 'c'), path.join('root', 'b', 'c')
        ... ]

    """
    if not ignore_empty and None in path_parts:
        raise ValueError(f"one of the path parts is None; got '{path_parts}'")

    out = [
        path.join(
            *(
                filter(bool, map(str_, _path_parts))
                if ignore_empty
                else map(str_, _path_parts)
            )
        )
        for _path_parts in product__(
            *path_parts,
            atom_types=(str, bytes, PathLike),
            ignore_none=True
        )
    ]

    return out[0] if len(out) == 1 else out

