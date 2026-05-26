from os import path
import os
from typing import Optional, Tuple, Callable, Any
import shutil
import hashlib
import json
from python_utils.common_utils.iter_helper import tqdm_wrap
from python_utils.console_utils import hprint_message
from python_utils.path_utils.common import ensure_parent_dir_existence
from python_utils.path_utils.path_with_date_time_info import add_date_time_to_path
from python_utils.datetime_utils.common import solve_date_time_format_by_granularity

DEFAULT_ENCODING = 'utf-8'

def _solve_paras_from_io_mode(
        file: str,
        mode: str,
        use_tqdm: bool,
        description: Optional[str],
        verbose: bool
) -> Tuple[bool, str, bool]:
    """
     Solves arguments for `open_`. This function disables the tqdm wrap for writing
     (because tqdm does not support that), generates the `description` for the tqdm progress bar
     if it is not specified, and determines if the IO operation requires the existence
     of the parent path.

     Args:
         file: The file path to be opened.
         mode: The file access mode, such as 'r', 'w', 'a', 'x', etc.
         use_tqdm: A flag indicating whether to use tqdm for progress display.
             Disabled for writing modes.
         description: A description for the tqdm progress bar.
             If not provided, it will be generated.
         verbose: A flag indicating whether to display tqdm progress bar or not.

     Returns:
         tuple: A tuple containing the modified values of `use_tqdm`, `description`,
         and a boolean indicating whether the
         parent path needs to exist for the specified IO operation.

     Examples:
         >>> import tempfile
         >>> test_file = tempfile.NamedTemporaryFile(delete=False)
         >>> assert test_file.write(b"Test content")
         >>> test_file.close()

         >>> mode = "r"
         >>> use_tqdm = True
         >>> description = None
         >>> verbose = True
         >>> x = _solve_paras_from_io_mode(test_file.name, mode, use_tqdm, description, verbose)
         >>> assert x[0] and not x[2]
         >>> assert x[1].startswith('read from file ')

         >>> mode = "w"
         >>> x = _solve_paras_from_io_mode(test_file.name, mode, use_tqdm, description, verbose)
         >>> assert not x[0] and x[2]
         >>> assert x[1].startswith('overwrite file ')

     """
    need_dir_exist = False
    if description is None and (use_tqdm or verbose):
        binary = 'binary ' if 'b' in mode else ''
        if 'r' in mode:
            description = f'read from {binary}file {file}'
        elif 'w' in mode:
            if path.exists(file):
                description = f'overwrite {binary}file {file}'
            else:
                description = f'write to {binary}file {file}'
            need_dir_exist = True
            use_tqdm = False
        elif 'a' in mode:
            description = f'append to {binary}file {file}'
            need_dir_exist = True
            use_tqdm = False
        elif 'x' in mode:
            description = f'write to {binary}file {file}'
            need_dir_exist = True
            use_tqdm = False
    else:
        need_dir_exist = 'w' in mode or 'a' in mode or 'x' in mode
    return use_tqdm, description, need_dir_exist


def file_to_dir(file_path: str, default_filename: str = 'default') -> None:
    """
    Convert a file to a directory by moving the file content to a default filename within the directory.
    
    If the file_path points to an existing regular file, this function:
    1. Temporarily renames the file to a backup
    2. Creates a directory with the original file name
    3. Moves the backed-up file into the new directory with the specified default filename
    
    If the file_path is already a directory or doesn't exist, this function does nothing.
    
    Args:
        file_path: Path to the file to convert to a directory.
        default_filename: The filename to use for the original file content within the new directory.
                         Defaults to 'default'.
    
    Examples:
        >>> import tempfile
        >>> import os
        >>> # Create a temporary file
        >>> temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
        >>> temp_file.write(b"existing content")
        16
        >>> temp_file.close()
        >>> original_path = temp_file.name
        >>> # Convert file to directory
        >>> file_to_dir(original_path, 'original.txt')
        >>> # Check that it's now a directory
        >>> assert os.path.isdir(original_path)
        >>> # Check that the original content is preserved
        >>> assert os.path.exists(os.path.join(original_path, 'original.txt'))
        >>> with open(os.path.join(original_path, 'original.txt'), 'rb') as f:
        ...     assert f.read() == b"existing content"
    """
    # Only proceed if file_path exists as a regular file
    if not (path.exists(file_path) and path.isfile(file_path)):
        return
    
    # Temporarily rename the file
    temp_backup = file_path + '.tmp_backup'
    os.rename(file_path, temp_backup)
    
    # Create directory with the original file name
    os.makedirs(file_path, exist_ok=True)
    
    # Move the backed up file to the default filename
    default_file_path = path.join(file_path, default_filename)
    os.rename(temp_backup, default_file_path)


def _default_space_handler(file: str, space: Optional[str]) -> str:
    """
    Default space handler that joins file (as folder) and space (as filename).
    
    Handles edge cases:
    - If space is None or empty, uses 'default' as the space name
    - If file exists as a file (not directory), moves it to the default space
      within a newly created directory
    
    Args:
        file: The base path (treated as a directory/folder).
        space: The space identifier (treated as the actual filename).
               If None or empty, defaults to 'default'.
    
    Returns:
        The joined path with file as folder and space as filename.
    
    Examples:
        >>> _default_space_handler("/data/logs", "experiment1.json")
        '/data/logs/experiment1.json'
        >>> _default_space_handler("output", "results.txt")
        'output/results.txt'
        
        >>> _default_space_handler("output", None)
        'output/default'
        >>> _default_space_handler("output", "")
        'output/default'
        
        >>> import tempfile
        >>> import os
        >>> # Test when file exists as a file
        >>> temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
        >>> temp_file.write(b"existing content")
        16
        >>> temp_file.close()
        >>> result = _default_space_handler(temp_file.name, "new_space.txt")
        >>> # Original file should be moved to default space
        >>> assert os.path.isdir(temp_file.name)
        >>> assert os.path.exists(os.path.join(temp_file.name, "default"))
        >>> # New space file path should be returned
        >>> assert result == os.path.join(temp_file.name, "new_space.txt")
    """
    # Handle None or empty space
    if not space:
        space = 'default'
    
    # Convert file to directory if needed
    file_to_dir(file, default_filename='default')
    
    return path.join(file, space)


def _default_space_handler_with_space_hash(file: str, space: Optional[str]) -> str:
    """
    Space handler that hashes the space identifier to create a safe filename,
    and maintains a meta.json file for space-to-hash mapping.
    
    This is useful when the space identifier contains special characters that
    are not filesystem-safe, or when you want consistent short filenames.
    
    Handles edge cases:
    - If space is None or empty, uses 'default' as the space name
    - If file exists as a file (not directory), moves it to the default space
      within a newly created directory
    
    Args:
        file: The base path (treated as a directory/folder).
        space: The space identifier (will be hashed to create filename).
               If None or empty, defaults to 'default'.
    
    Returns:
        The joined path with file as folder and hashed space as filename.
    
    Examples:
        >>> import tempfile
        >>> import json
        >>> temp_dir = tempfile.mkdtemp()
        >>> result = _default_space_handler_with_space_hash(temp_dir, "my/special:space*name")
        >>> # The result should be a hashed filename
        >>> assert result.startswith(temp_dir)
        >>> # Check that meta.json was created
        >>> meta_path = path.join(temp_dir, "meta.json")
        >>> assert path.exists(meta_path)
        >>> with open(meta_path, 'r') as f:
        ...     meta = json.load(f)
        >>> assert "my/special:space*name" in meta
    """
    # Handle None or empty space
    if not space:
        space = 'default'
    
    # Convert file to directory if needed
    file_to_dir(file, default_filename='default')
    
    # Create hash of the space identifier
    space_hash = hashlib.sha256(space.encode('utf-8')).hexdigest()[:16]
    
    # Ensure the directory exists
    os.makedirs(file, exist_ok=True)
    
    # Path to the meta.json file
    meta_path = path.join(file, "meta.json")
    
    # Load or create the metadata mapping
    if path.exists(meta_path):
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = json.load(f)
    else:
        meta = {}
    
    # Update the mapping if this space isn't already recorded
    if space not in meta:
        meta[space] = space_hash
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
    
    # Return the path with hashed filename
    return path.join(file, space_hash)


class open_:
    """
    Provides more options for opening a file, including creating the parent directory, tqdm wrap,
        and enforced flusing upon exit.

    Args:
        file: The file path to be opened.
        mode: The file access mode, such as 'r', 'w', 'a', 'x', etc. Defaults to None.
        append: A flag indicating whether to open the file in append mode. If True, the file is
            opened in 'a+' mode. If False, the file is opened in 'w+' mode. Cannot be used with `mode`. Defaults to None.
        encoding: The encoding to be used for opening the file. Defaults to None.
        use_tqdm: A flag indicating whether to use tqdm for progress display. Disabled for writing modes.
            Defaults to False.
        description: A description for the tqdm progress bar. If not provided, it will be generated.
            Defaults to None.
        verbose: A flag indicating whether to display tqdm progress bar or not. Defaults to __debug__.
        create_dir: A flag indicating whether to create the parent directory if it does not exist.
            Defaults to True.
        space: Optional space identifier for organizing files. When provided, the space_handler
            is used to compute the final file path. With the default handler, space is treated
            as the actual filename. Defaults to None.
        space_handler: A callable that takes (file, space) and returns the final path.
            Defaults to _default_space_handler which treats file as a folder and space as the filename,
            joining them as path.join(file, space).
        *args: Additional positional arguments to be passed to the built-in `open` function.
        **kwargs: Additional keyword arguments to be passed to the built-in `open` function.

    Examples:
        >>> import tempfile
        >>> test_file = tempfile.NamedTemporaryFile(delete=False)
        >>> assert test_file.write(b"Test content")
        >>> test_file.close()

        >>> with open_(test_file.name, mode="r", use_tqdm=False, verbose=False) as f:
        ...     print(f.read())
        Test content

        >>> with open_(test_file.name, mode="r", use_tqdm=True, verbose=False) as f:
        ...     list(f)
        ['Test content']

        >>> with open_(test_file.name, append=True, verbose=False) as f:
        ...     assert f.write("Appended text")

        Using space parameter (file as folder, space as filename):
        >>> import os
        >>> temp_dir = tempfile.mkdtemp()
        >>> with open_(temp_dir, mode="w", space="test.txt", verbose=False) as f:
        ...     _ = f.write("Space test")
        >>> assert os.path.exists(os.path.join(temp_dir, "test.txt"))

        Using custom space_handler:
        >>> def custom_handler(file, space):
        ...     return os.path.join(file, "custom_subdir", space)
        >>> with open_(temp_dir, mode="w", space="test2.txt", space_handler=custom_handler, verbose=False) as f:
        ...     _ = f.write("Custom handler test")
        >>> assert os.path.exists(os.path.join(temp_dir, "custom_subdir", "test2.txt"))

    """

    def __init__(
            self,
            file: str,
            mode: str = None,
            append: Optional[bool] = None,
            encoding: str = DEFAULT_ENCODING,
            use_tqdm: bool = False,
            description: str = None,
            verbose: bool = __debug__,
            create_dir: bool = True,
            space: Optional[str] = None,
            space_handler: Optional[Callable[[str, str], str]] = None,
            *args, **kwargs
    ):
        # Apply space handler if space is provided
        if space is not None:
            if space_handler is None:
                space_handler = _default_space_handler
            file = space_handler(file, space)
        
        self._file = file

        if append is True:
            if mode is not None:
                raise ValueError('cannot specify `mode` and `append` at the same time')
            mode = 'a+'
        elif append is False:
            if mode is not None:
                raise ValueError('cannot specify `mode` and `append` at the same time')
            mode = 'w+'
        elif mode is None:
            mode = 'r'

        use_tqdm, description, need_dir_exist = _solve_paras_from_io_mode(
            file=file,
            mode=mode,
            use_tqdm=use_tqdm,
            description=description,
            verbose=verbose
        )

        if create_dir and need_dir_exist:
            os.makedirs(path.dirname(self._file), exist_ok=True)

        self._f = open(self._file, mode=mode, encoding=encoding, *args, **kwargs)
        self._f_with_tqdm_wrap = tqdm_wrap(
            self._f,
            use_tqdm=use_tqdm,
            tqdm_msg=description if verbose else None,
            verbose=verbose
        )

    def flush(self):
        self._f.flush()

    def __enter__(self):
        return self._f_with_tqdm_wrap

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self._f.flush()
        self._f.close()


def read_text_or_file(text_or_file: str, read_text_func: Callable[[str], Any], read_file_func: Callable[[str], Any]):
    if not isinstance(text_or_file, str):
        return text_or_file
    if path.exists(text_or_file):
        return read_file_func(text_or_file)
    else:
        return read_text_func(text_or_file)


def create_empty_file(file_path: str) -> None:
    """
    Create an empty file at the specified path.

    Args:
        file_path: The path where the empty file should be created.
    """
    with open(file_path, "w") as file:
        pass


def backup(
        input_path: str,
        backup_path: str,
        datetime_granularity: str = "day",
        date_format: str = '%Y%m%d',
        time_format: str = '',
        unix_timestamp: bool = False
) -> None:
    """
    Create a backup copy of the input file or directory with a date/time string appended to the backup path.

    Args:
        input_path: Path to the file or directory to backup.
        backup_path: Path where the backup will be created.
        date_format: Format for date string. Defaults to 'YYYYMMDD'.
        time_format: Format for time string. If empty, no time is appended.
        datetime_granularity: Granularity of the date/time string, e.g. "year", "month", "date", "hour". Default is "second".
        unix_timestamp: If True, append Unix timestamp instead of date and time. Default is False.

    Raises:
        FileNotFoundError: If the input file or directory does not exist.
    """

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"The input file or directory {input_path} does not exist.")

    # Get date and time format based on the granularity
    solved_date_format, solved_time_format = solve_date_time_format_by_granularity(
        datetime_granularity,
        date_format,
        time_format
    )

    # Get the backup path with date/time string appended
    backup_path_with_datetime = add_date_time_to_path(
        backup_path,
        date_format=solved_date_format,
        time_format=solved_time_format,
        unix_timestamp=unix_timestamp
    )

    ensure_parent_dir_existence(backup_path_with_datetime)

    if os.path.isdir(input_path):
        # Copy directory
        shutil.copytree(input_path, backup_path_with_datetime)
    else:
        # Copy file
        shutil.copy2(input_path, backup_path_with_datetime)

    hprint_message('backup created at', backup_path_with_datetime)