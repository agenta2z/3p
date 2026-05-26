import glob
import os
import shutil
from os import path
from typing import Union, List, Optional, Sequence
from python_utils.console_utils import hprint_pairs, hprint
from python_utils.path_utils.messages import msg_skip_non_local_dir, msg_create_dir, msg_arg_not_a_dir, msg_clear_dir
from python_utils.path_utils.path_listing import iter_files_by_pattern
from python_utils.path_utils.path_string_operations import abspath_
import platform
import re


def resolve_path_(
        path_str: str,
        try_glob: bool = True,
        always_return_abs_path: bool = True,
        unpack_single_result: bool = True
) -> Optional[Union[List[str], str]]:
    """
    Resolves a given path string, attempting to match the path directly or using glob patterns.

    Args:
        path_str (str): The file or directory path to resolve.
        try_glob (bool, optional): Whether to attempt glob pattern matching if the path does not exist.
            Defaults to True.
        always_return_abs_path (bool, optional): If True, always returns the absolute path of the matched file(s).
            Defaults to True.
        unpack_single_result (bool, optional): If True, returns a single result directly (not in a list)
            when only one match is found. Defaults to True.

    Returns:
        Optional[Union[List[str], str]]:
            - If the path exists, returns the path string (absolute if `return_abs_path` is True).
            - If glob matching is enabled and results are found, returns a list of matching paths.
            - If no match is found, returns None.

    Example:
        >>> # Create example files in the current folder for testing
        >>> with open('test_file_1.txt', 'w') as f:
        ...     f.write('Test content 1')
        14
        >>> with open('test_file_2.txt', 'w') as f:
        ...     f.write('Test content 2')
        14

        >>> # Test resolving a direct path
        >>> resolve_path_('test_file_1.txt', always_return_abs_path=False)
        'test_file_1.txt'

        >>> # Test resolving using glob patterns
        >>> resolve_path_('test_file_*.txt', try_glob=True, always_return_abs_path=False)
        ['test_file_1.txt', 'test_file_2.txt']

        >>> # Test resolving a nonexistent path
        >>> resolve_path_('nonexistent_file.txt')

        >>> # Cleanup the created files after the test (optional in real testing environments)
        >>> os.remove('test_file_1.txt')
        >>> os.remove('test_file_2.txt')
    """
    abs_path_str = path.abspath(path_str) if always_return_abs_path else path_str

    if path.exists(abs_path_str):
        return abs_path_str if always_return_abs_path else path_str

    if try_glob:
        try:
            globs = glob.glob(abs_path_str)
            if globs:
                if unpack_single_result and len(globs) == 1:
                    return globs[0]
                return globs
        except:
            pass

    return None  # Return None if no matches are found


def resolve_path(
        path_str: str,
        path_name: str = None,
        __file__: str = None,
        always_return_abs_path: bool = True,
        unpack_single_result: bool = True
) -> Optional[Union[List[str], str]]:
    """
    Resolves the given path string to an existing path.

    Args:
        path_str (str): The path string to resolve. This can be a direct file path or a glob pattern.
        path_name (str, optional): A name for the path, used in error messages. Useful for clarity when
            resolving multiple paths. Defaults to None.
        __file__ (str, optional): The file path to use for resolving relative paths. If provided, the function
            will attempt to resolve `path_str` relative to the directory containing this file. Defaults to None.
        always_return_abs_path (bool, optional): If True, returns the absolute path of the resolved file(s).
            Defaults to True.
        unpack_single_result (bool, optional): If True, returns a single result (not in a list) when only one
            match is found. Defaults to True.

    Returns:
        str: The resolved path.

    Raises:
        ValueError: If the path cannot be resolved.

    Examples:
        >>> import os
        >>> with open('test_file.txt', 'w') as f:
        ...     f.write('dummy content')
        13

        >>> resolve_path('test_file.txt', always_return_abs_path=False)
        'test_file.txt'
        >>> resolve_path('test_file.txt', always_return_abs_path=True)  # doctest: +ELLIPSIS
        '...test_file.txt'
        >>> resolve_path('nonexistent_file.txt')
        Traceback (most recent call last):
        ...
        ValueError: path 'nonexistent_file.txt' cannot be resolved
        >>> os.remove('test_file.txt')
    """
    resolved_path = resolve_path_(
        path_str=path_str,
        always_return_abs_path=always_return_abs_path,
        unpack_single_result=unpack_single_result
    )

    if resolved_path:
        return resolved_path

    if __file__:
        _path_str = path.join(path.dirname(__file__), path_str)
        if path.exists(_path_str):
            return abspath_(_path_str) if always_return_abs_path else _path_str

    if path_name:
        raise ValueError(f"path '{path_str}' for '{path_name}' cannot be resolved")
    else:
        raise ValueError(f"path '{path_str}' cannot be resolved")


def print_basic_path_info(*path_or_paths):
    for item in path_or_paths:
        if isinstance(item, str):
            hprint_pairs(("path", item), ("is file", path.isfile(item)), ("exists_path", path.exists(item)))
        else:
            hprint_pairs((item[0], item[1]), ("is file", path.isfile(item[1])), ("exists_path", path.exists(item[1])))


def paths_in_same_directory(paths: Sequence[str]) -> bool:
    """
    Checks if all given paths are under the same directory.

    Args:
        paths (List[str]): A list of file or directory paths to check.

    Returns:
        bool: True if all paths are in the same directory, False otherwise.

    Raises:
        ValueError: If the list of paths is empty.

    Example:
        >>> paths_in_same_directory(['/home/user/file1.txt', '/home/user/file2.txt'])
        True

        >>> paths_in_same_directory(['/home/user/file1.txt', '/home/user/docs/file2.txt'])
        False

        >>> paths_in_same_directory([])
        Traceback (most recent call last):
        ...
        ValueError: List of paths is empty
    """
    if not paths:
        raise ValueError("List of paths is empty")

    # Get the directory of the first path
    first_dir = path.dirname(path.abspath(paths[0]))

    # Check if all other paths share the same directory
    return all(path.dirname(path.abspath(p)) == first_dir for p in paths)


def get_directory_if_paths_in_same_directory(paths: Sequence[str]) -> bool:
    """
    Checks if all given paths are under the same directory and returns the directory if they are.

    Args:
        paths (Sequence[str]): A sequence of file or directory paths to check.

    Returns:
        Optional[str]: The directory path if all paths are in the same directory, None otherwise.

    Raises:
        ValueError: If the list of paths is empty.

    Example:
        >>> # Paths in the same directory
        >>> get_directory_if_paths_in_same_directory(['/home/user/file1.txt', '/home/user/file2.txt'])
        '/home/user'

        >>> # Paths in different directories
        >>> get_directory_if_paths_in_same_directory(['/home/user/file1.txt', '/home/user/docs/file2.txt'])

        >>> # Empty list of paths
        >>> get_directory_if_paths_in_same_directory([])
        Traceback (most recent call last):
        ...
        ValueError: List of paths is empty
    """
    if not paths:
        raise ValueError("List of paths is empty")

    # Get the directory of the first path
    first_dir = path.dirname(path.abspath(paths[0]))

    # Check if all other paths share the same directory
    if all(path.dirname(path.abspath(p)) == first_dir for p in paths):
        return first_dir


def ensure_parent_dir_existence(*dir_path_or_paths, clear_dir=False, verbose=__debug__):
    ensure_dir_existence(*(path.dirname(p) for p in dir_path_or_paths), clear_dir=clear_dir, verbose=verbose)
    return dir_path_or_paths[0] if len(dir_path_or_paths) == 1 else dir_path_or_paths


def ensure_dir_existence(
        *dir_path_or_paths,
        clear_dir=False,
        verbose=__debug__
) -> Union[str, List[str]]:
    """
    Creates a directory if the path does not exist. Optionally, set `clear_dir` to `True` to clear an existing directory.

import python_utils.path_utils.common    >>> import utix.pathex as pathx
    >>> import os
    >>> from python_utils.path_utils.common import print_basic_path_info
    >>> path1, path2 = 'test/_dir1', 'test/_dir2'
    >>> print_basic_path_info(path1)
    >>> print_basic_path_info(path2)

    Pass in a single path.
    ----------------------
    >>> ensure_dir_existence(path1)
    >>> os.remove(path1)

    Pass in multiple paths.
    -----------------------
    >>> ensure_dir_existence(path1, path2)
    >>> os.remove(path1)
    >>> os.remove(path2)

    Pass in multiple paths as a tuple.
    ----------------------------------
    >>> # this is useful when this method is composed with another function that returns multiple paths.
    >>> def foo():
    >>>     return path1, path2
    >>> ensure_dir_existence(foo())

    :param dir_path_or_paths: one or more paths to check.
    :param clear_dir: clear the directory if they exist.
    :return: the input directory paths; this function has guaranteed their existence.
    """
    if len(dir_path_or_paths) == 1 and not isinstance(dir_path_or_paths[0], str):
        dir_path_or_paths = dir_path_or_paths[0]

    for dir_path in dir_path_or_paths:
        if '://' in dir_path:
            msg_skip_non_local_dir(dir_path)
            continue
        if not path.exists(dir_path):
            if verbose:
                hprint(msg_create_dir(dir_path))
            os.umask(0)
            os.makedirs(dir_path, mode=0o777, exist_ok=True)
        elif not path.isdir(dir_path):
            raise ValueError(msg_arg_not_a_dir(path_str=dir_path, arg_name='dir_path_or_paths'))
        elif clear_dir is True:
            if verbose:
                hprint(msg_clear_dir(dir_path))
            shutil.rmtree(dir_path)
            os.umask(0)
            os.makedirs(dir_path, mode=0o777, exist_ok=True)
        elif isinstance(clear_dir, str) and bool(clear_dir):
            for file in iter_files_by_pattern(dir_or_dirs=dir_path, pattern=clear_dir, recursive=False):
                os.remove(file)

        if verbose:
            print_basic_path_info(dir_path)

    return dir_path_or_paths[0] if len(dir_path_or_paths) == 1 else dir_path_or_paths


def sanitize_filename(
        filename: str,
        invalid_character_replacement: str = '_',
        lstrip: bool = True,
        rstrip: bool = True,
        rstrip_dots: bool = False,
        max_filename_size: int = 254,
        for_url: bool = False
) -> str:
    """Sanitizes a filename for cross-platform compatibility by replacing
    or removing invalid characters, trimming spaces, and optionally removing
    trailing dots. Allows limiting filename length to a specified size.

    Args:
        filename (str): The filename string to sanitize.
        invalid_character_replacement (str, optional): The character to replace
            invalid characters with. Defaults to '_'.
        lstrip (bool, optional): Whether to strip leading spaces. Defaults to True.
        rstrip (bool, optional): Whether to strip trailing spaces. Defaults to True.
        rstrip_dots (bool, optional): Whether to strip trailing dots. Defaults to False.
        max_filename_size (int, optional): The maximum length for the filename.
            If 0 or negative integer, no limit is enforced other than the typical 255-character file
            system limit. Defaults to 255.
        for_url (bool, optional): Whether to sanitize filename to be URL-safe. Defaults to False.

    Returns:
        str: A sanitized filename safe to use across Windows, UNIX, and optionally URLs.

    Raises:
        ValueError: If the replacement character is an invalid filename character.

    Examples:
        >>> sanitize_filename("Invalid?Filename*Example.txt")
        'Invalid_Filename_Example.txt'

        >>> sanitize_filename("File with spaces...", for_url=True)
        'File_with_spaces'
    """
    # Define invalid characters for both Windows and UNIX-based systems
    invalid_chars = r'[<>:"/\\|?*\s]' if platform.system() == "Windows" else r'[/:]'
    # Additional restrictions for URL-safe filenames
    if for_url:
        invalid_chars = r'[^a-zA-Z0-9._-]'

    if lstrip:
        filename = filename.lstrip()
    if rstrip:
        filename = filename.rstrip()
    if rstrip_dots:
        filename = filename.rstrip('.')

    # Replace invalid characters with the specified replacement character
    sanitized_name = re.sub(invalid_chars, invalid_character_replacement, filename)

    # Limit the length to a specified number of characters
    return (
        sanitized_name[:max_filename_size]
        if 0 < max_filename_size < len(sanitized_name)
        else sanitized_name
    )


def resolve_ext(ext: str, sep='.') -> str:
    """Normalize a file extension to include the leading dot.

    Returns the input unchanged if it already starts with ``'.'``,
    otherwise prepends one.  ``None`` and empty strings pass through.

    Examples:
        >>> resolve_ext('.html')
        '.html'
        >>> resolve_ext('html')
        '.html'
        >>> resolve_ext(None) is None
        True
    """
    if not ext:
        return ext
    return ext if ext[0] == sep else sep + ext