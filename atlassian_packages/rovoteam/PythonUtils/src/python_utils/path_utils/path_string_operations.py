from functools import partial
from os import path
from typing import Tuple, Union, Callable, Any
import glob
from python_utils.string_utils.comparison import string_check
from python_utils.string_utils.prefix_suffix import add_suffix, get_next_numbered_string, add_prefix
from python_utils.datetime_utils.common import timestamp


def path_endswith_sep(pathstr: str) -> bool:
    """
    Checks if the provided path string ends with the path separator.

    Args:
        pathstr: The path string to check.

    Returns:
        True if the path string ends with the path separator, False otherwise.

    Example:
        >>> print(path_endswith_sep('path/to/dir/'))
        True
        >>> print(path_endswith_sep('path/to/dir'))
        False
    """
    return pathstr.endswith(path.sep)


def path_ends_with(pathstr: str, s: str) -> bool:
    """
    Checks if the provided path string ends with the provided string `s`, ignoring any trailing path separators.

    Args:
        pathstr: The path string to check.
        s: The string to check if `pathstr` ends with.

    Returns:
        True if the path string, disregarding any trailing path separators, ends with `s`, False otherwise.

    Example:
        >>> print(path_ends_with('path/to/dir/', 'dir'))
        True
        >>> print(path_ends_with('path/to/dir', 'dir'))
        True
        >>> print(path_ends_with('path/to/dir', 'to'))
        False
    """
    if path_endswith_sep(pathstr):
        pathstr = pathstr[: -len(path.sep)]
    return pathstr.endswith(s)


def abspath_(pathstr: str) -> str:
    """
    Returns the absolute path of the input path string. If the input path starts with "~", it is expanded
    to the full user directory path. This function differs from `path.abspath` in that it performs this
    expansion.

    Args:
        pathstr: The path string to convert to an absolute path.

    Returns:
        The absolute path corresponding to the input path string.

    Example:
        >>> print(abspath_('~/documents'))
        >>> print(abspath_('./documents'))
    """
    return path.expanduser(pathstr) if pathstr[0] == '~' else path.abspath(pathstr)


def get_main_name(pathstr: str) -> str:
    """
    Gets the main file name from the path string.

    Args:
        pathstr: the path string.

    Examples:
        >>> get_main_name('a/b/c.d')
        'c'

    """
    return path.splitext(path.basename(pathstr))[0]


def get_ext_name(pathstr: str, includes_dot: bool = True) -> str:
    """
    Gets the extension file name from the path string.

    Args:
        pathstr: the path string.
        includes_dot: True to include the dot in the extension name, e.g. '.csv';
        otherwise, no dot, e.g. 'csv'.

    Examples:
        >>> get_ext_name('a/b/c.d')
        '.d'
        >>> get_ext_name('a/b/c.d', includes_dot=False)
        'd'
    """
    ext_name = path.splitext(path.basename(pathstr))[1]
    return ext_name if includes_dot else ext_name[1:]


def get_main_name_ext_name(pathstr: str, ext_name_includes_dot: bool = True) -> Tuple[str, str]:
    """
    Gets both the main & extension file name from the path string at the same time.

    Args:
        pathstr: the path string.
        ext_name_includes_dot: True to include the dot in the extension name, e.g. '.csv';
            otherwise, no dot, e.g. 'csv'.

    Returns: the main & extension file name.

    """
    out = path.splitext(path.basename(pathstr))
    if ext_name_includes_dot:
        return out
    else:
        return out[0], out[1][1:]


def make_ext_name(ext_name: str):
    """
    Ensures the extension name `ext_name` starts with a dot.
    If `ext_name` is None or empty, then `None` is returned.

    Examples:
        >>> make_ext_name('csv')
        '.csv'
    """
    if ext_name:
        return '.' + ext_name if ext_name[0] != '.' else ext_name


def add_to_main_name(path_str: str, prefix: str = '', suffix: str = '') -> str:
    """
    Add prefix and/or suffix to the main part of a file path.

    Args:
        path_str: The file path string.
        prefix: The prefix to add to the main part of the file name. Defaults to ''.
        suffix: The suffix to add to the main part of the file name. Defaults to ''.

    Returns:
        The modified file path with the added prefix and/or suffix.

    Examples:
        >>> add_to_main_name('/path/to/file.txt', 'pre_', '_suf')
        '/path/to/pre_file_suf.txt'

        >>> add_to_main_name('/path/to/another/file', prefix='new_', suffix='.bak')
        '/path/to/another/new_file.bak'

        >>> add_to_main_name('document.docx', suffix='_backup')
        'document_backup.docx'
    """
    dir_name = path.dirname(path_str)
    base_name = path.basename(path_str)
    path_splits = path.splitext(base_name)
    return path.join(dir_name, str(prefix) + path_splits[0] + str(suffix) + path_splits[1])


def replace_ext_name(pathstr: str, ext_name_replacement):
    """

    Args:
        pathstr:
        ext_name_replacement:

    Returns:

    Examples:
        >>> replace_ext_name('a/b/c/d.csv', 'json')
        'a/b/c/d.json'
    """
    out = path.splitext(pathstr)
    return out[0] + make_ext_name(ext_name_replacement)


def path_or_name_with_timestamp(
        path_or_name: str,
        extname: str = None,
        timestamp_scale=100,
        timestamp_sep='_',
        extname_sep='.'
):
    """
    Appends a timestamp to the end of a path or name.
    
    Args:
        path_or_name: the path or name to attach the timestamp;
            if this ends with either `path.sep` or `path.altsep` (i.e. usually '/' or '\'), 
            then it will be treated as you want to get a name under a directory, 
            and an underscore `timestampe_sep` will be placed in the front of the timestamp.
        extname: the extension name, if necessary.
        timestamp_scale: a timestamp is `time() * timestamp_scale`.
        timestamp_sep: the separator between the name and the timestamp.
        extname_sep: the separator for the extension name.
    
    Returns:
         the name or path with timestamp attached.

    Examples:
        >>> path_or_name_with_timestamp('a/b/c/d') # get something like 'a/b/c/d_166106610267'
        >>> path_or_name_with_timestamp('a/b/c/d/') # get something like 'a/b/c/d/166106610267'

    """

    if extname:
        if extname[0] == extname_sep:
            extname = extname[1:]
        if path_or_name[-1] in (path.sep, path.altsep):
            return f'{path_or_name}{timestamp(scale=timestamp_scale)}{extname_sep}{extname}'
        else:
            return f'{path_or_name}{timestamp_sep}' \
                   f'{timestamp(scale=timestamp_scale)}{extname_sep}{extname}'
    else:
        if path_or_name[-1] in (path.sep, path.altsep):
            return f'{path_or_name}{timestamp(scale=timestamp_scale)}'
        else:
            return f'{path_or_name}{timestamp_sep}{timestamp(scale=timestamp_scale)}'


def get_shortest_prefix(pathstr: str, cond: Union[str, Callable]):
    """
    Extracts the shortest prefix satisfying a condition from a path string.
    Args:
        pathstr: the path string.
        cond: can be a string-checking pattern (see :func:`string_check`),
            or a callable returning a Boolean value indicating whether a path prefix
            satistying a condition.

    Returns: the shortest prefix satisfying a condition from the provided path string.

    Examples:
        >>> get_shortest_prefix('{year}/{month}/{day}/{hour}/{locale}', '* {day}')
        '{year}/{month}/{day}'
        >>> get_shortest_prefix('{year}/{month}/{day}/{hour}/{locale}', '* {year}')
        '{year}'
    """
    if isinstance(cond, str):
        cond = partial(string_check, pattern=cond)

    prefix = pathstr
    while prefix and cond(prefix):
        pathstr = prefix
        prefix = path.dirname(pathstr)

    return pathstr


def add_path_suffix(pathstr: str, suffix: Any, sep: str = '-') -> str:
    if path_endswith_sep(pathstr):
        ends_with_path_sep = True
        pathstr = pathstr[:-len(path.sep)]
    else:
        ends_with_path_sep = False
    pathstr = add_suffix(pathstr, suffix=suffix, sep=sep)
    if ends_with_path_sep:
        pathstr += path.sep
    return pathstr


def add_ending_path_sep(pathstr: str):
    return pathstr if path_endswith_sep(pathstr) else (pathstr + path.sep)


def remove_ending_path_sep(pathstr: str):
    return pathstr[:-len(path.sep)] if path_endswith_sep(pathstr) else pathstr


def has_ending_path_sep(pathstr: str) -> bool:
    return path_endswith_sep(pathstr)


def solve_root_path(pathstr, default_basename):
    if not has_ending_path_sep(pathstr):
        root_path = path.dirname(default_basename)
    else:
        root_path = pathstr
        pathstr = path.join(root_path, default_basename)
    return root_path, pathstr


def path_ends_with(pathstr: str, s: str):
    if path_endswith_sep(pathstr):
        pathstr = pathstr[:-len(path.sep)]
    return pathstr.endswith(s)


def append_to_main_name(path_str: str, main_name_suffix: str):
    """
    Appends a suffix to the main name of a path.
    For example, `append_to_main_name('../test.csv', '_fixed')` renames the path as `../test_fixed.csv` (appending suffix `_fixed` to the main name `test` of this path).
    :param path_str: appends the suffix to the main name of this path.
    :param main_name_suffix: the suffix to append to the main name of the provided path.
    :return: a new path string with the suffix appended to the main name.
    """
    path_splits = path.splitext(path_str)
    return path_splits[0] + str(main_name_suffix) + path_splits[1]


def append_timestamp(path_str: str, timestamp_scale=100):
    return append_to_main_name(path_str, '_' + timestamp(scale=timestamp_scale))


def get_next_numbered_path(root_path, prefix: str = 'part_', default:str='0000') -> str:
    """
    Generates the next path in a sequence by finding the existing parts in a directory
    and determining the next numbered part. Raises an error if the output path does not exist.

    Args:
        root_path (str): The directory path where the parts are stored.
        prefix (str): The prefix used for the numbered parts. Defaults to 'part_'.

    Returns:
        str: The next numbered path, e.g., '/path/to/dir/part_0004'.

    Raises:
        ValueError: If the output path does not exist or if no files matching the prefix are found.

    Examples:
        >>> import tempfile
        >>> import os
        >>> with tempfile.TemporaryDirectory() as temp_dir:
        ...     open(os.path.join(temp_dir, 'part_0001'), 'w').close()
        ...     open(os.path.join(temp_dir, 'part_0002'), 'w').close()
        ...     get_next_numbered_path(temp_dir).endswith('part_0003')
        True

        >>> with tempfile.TemporaryDirectory() as temp_dir:
        ...     open(os.path.join(temp_dir, 'image_0010'), 'w').close()
        ...     open(os.path.join(temp_dir, 'image_0015'), 'w').close()
        ...     open(os.path.join(temp_dir, 'image_0014'), 'w').close()
        ...     get_next_numbered_path(temp_dir, prefix='image_').endswith('image_0016')
        True

        >>> with tempfile.TemporaryDirectory() as temp_dir:
        ...     non_existent_dir = os.path.join(temp_dir, 'non_existent_dir')
        ...     os.mkdir(non_existent_dir)
        ...     get_next_numbered_path(non_existent_dir, prefix='part').endswith('part0000')
        True
    """
    if not path.exists(root_path):
        raise ValueError(f"Path {root_path} does not exist for resuming the evaluation.")

    existing_parts = [get_main_name(x) for x in glob.glob(path.join(root_path, f'{prefix}*'))]

    if not existing_parts:
        return path.join(root_path, add_prefix(default, prefix=prefix, sep='', avoid_repeat=True))

    next_part = get_next_numbered_string(existing_parts)

    return path.join(root_path, next_part)
