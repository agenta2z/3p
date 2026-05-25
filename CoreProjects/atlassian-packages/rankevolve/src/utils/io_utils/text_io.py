"""
Full text_io implementation with read_all / read_all_text / read_all_ / read_all_text_.

Migrated from SciencePythonUtils with inlined dependencies to avoid external imports.
"""

import fnmatch
from os import listdir, path
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Mapping,
    Optional,
    Union,
)

# Inlined from science_python_utils.path_utils.path_listing
NOEXT_PATTERN = "NOEXT"


def get_main_name(pathstr: str) -> str:
    """Extract filename without extension: 'a/b/c.d' -> 'c'"""
    return path.splitext(path.basename(pathstr))[0]


def read_all(
    file_path: str,
    encoding: Optional[str] = None,
    file_patterns: Union[str, List[str], None] = None,
    keep_extension: bool = True,
    key_sep: str = "/",
    allow_reading_from_folder: bool = True,
    recursive_levels: Optional[int] = 0,
    collect_subdir_files_in_one_mapping: bool = False,
    read_file_method: Callable = None,
    version_parent_folders: Union[str, List[str], None] = None,
) -> Union[Any, Dict[str, Any]]:
    """
    Reads from either a single file or multiple files in a directory (optionally filtering by file name patterns),
    and optionally processes file content with a custom function.

    - If `file_path` is a **file**, returns that file's content.
      * If `read_file_method` is `None`, the file is read as **plain text** (string).
      * Otherwise, calls `read_file_method(file_object)` and returns the result (could be any type).
    - If `file_path` is a **directory**, returns a dictionary of `{filename: content_or_result}`,
      either in a **flat** structure or a **nested** structure (depending on `collect_subdir_files_in_one_mapping`).
      * If `read_file_method` is `None`, each file's content is read as text (string).
      * Otherwise, each file is opened and passed to `read_file_method(file_object)`.
      * `recursive_levels` controls how deep we descend into subdirectories.
      * `file_patterns` may filter out certain files (e.g., `"*.txt|*.md"`).
      * `keep_extension=False` removes the extension from the dictionary keys (if flat structure) or partial names (if nested).

    Args:
        file_path (str):
            The path to a file or a directory.
        encoding (Optional[str]):
            The encoding to use when reading files. Defaults to `None`,
            which uses the system default encoding.
        file_patterns (Union[str, List[str], None]):
            A single string or list of file name patterns (e.g., "*.txt", "*.md").

            - If a **single string** is provided, you can separate multiple patterns with a
              vertical bar (`|`), for example `"*.txt|*.md"`.
            - If a **list** of patterns is provided (e.g. `["*.txt", "*.md"]`),
              each pattern is tested individually.
            - If `"NOEXT"` is included, that matches files with **no dot** in their name.
            - If `None`, all files in the directory are included.
        keep_extension (bool):
            If reading from a directory, whether to keep file extensions in
            the dictionary keys. Defaults to `True`.
        key_sep (str):
            The string used to separate directory components in the dictionary keys.
            Defaults to `'/'`. May be one or more characters (e.g. `'->'`).
        allow_reading_from_folder (bool):
            If `False`, raises a `ValueError` when a directory path is provided.
            Defaults to `True`.
        recursive_levels (Union[int, None]):
            Maximum depth of subdirectory recursion:
              * 0 or None => no recursion (default),
              * a positive integer => that many levels,
              * -1 => infinite recursion.
        collect_subdir_files_in_one_mapping (bool):
            If `False` (default), returns a **flat** dict like
            `{"folder/file.txt": content, "topfile.txt": ...}`.
            If `True`, returns a **nested** structure:
            `{"folder": {"file.txt": content}, "topfile.txt": ...}`.
        read_file_method (Callable, optional):
            A function to process file content. It receives an **open file object** and
            must return the processed result (any type). If `None`, files are read as plain text.
        version_parent_folders (Union[str, List[str], None]):
            Optional folder name(s) to designate as "version parent folders". When specified,
            any child folders under these parents are treated as "version folders" whose files
            are returned as a list of version dicts: `[{"version": filename, "content": file_content}, ...]`.
            - Only works with `collect_subdir_files_in_one_mapping=True`.
            - Version folders can ONLY contain files (no subdirectories), otherwise raises `ValueError`.
            - Respects the `keep_extension` parameter for version names.

    Returns:
        Union[Any, Dict[str, Any]]:
            - If `file_path` is a single file:
              * If `read_file_method` is `None`, returns a string (the file's text).
              * Otherwise, returns whatever `read_file_method(file_object)` produces.
            - If `file_path` is a directory:
              * Returns a dictionary whose values are either file text (if `read_file_method=None`)
                or the return values of `read_file_method(file_object)` (any type).
              * The dictionary may be flat or nested, depending on `collect_subdir_files_in_one_mapping`.

    Raises:
        ValueError:
            - If `file_path` does not exist or is neither a valid file nor a valid directory.
            - If `allow_reading_from_folder=False` and `file_path` is a directory.
    """
    if not path.exists(file_path):
        raise ValueError(f"The path does not exist: {file_path}")

    # 1) Single file => return its contents
    if path.isfile(file_path):
        with open(file_path, encoding=encoding) as f:
            return f.read() if read_file_method is None else read_file_method(f)

    # 2) If it's a directory, check permission
    if path.isdir(file_path):
        if not allow_reading_from_folder:
            raise ValueError(
                "The path is a directory, but allow_reading_from_folder=False."
            )
    else:
        # If it's neither a file nor directory
        raise ValueError(
            f"The path is neither a valid file nor a directory: {file_path}"
        )

    # Convert single string pattern => list
    if isinstance(file_patterns, str):
        patterns_list = file_patterns.split("|")
    else:
        patterns_list = file_patterns  # could be a list or None

    # Convert version_parent_folders to a set for efficient lookup
    if version_parent_folders is None:
        version_parents_set = set()
    elif isinstance(version_parent_folders, str):
        version_parents_set = {version_parent_folders}
    else:
        version_parents_set = set(version_parent_folders)

    def _file_matches_patterns(filename: str) -> bool:
        if patterns_list is None:
            return True  # no filtering
        return any(
            (
                "." not in filename
                if pattern == NOEXT_PATTERN
                else fnmatch.fnmatch(filename, pattern)
            )
            for pattern in patterns_list
        )

    def _read_with_last_subdir_files_in_mapping(
        current_dir: str, current_level: int, prefix: str
    ) -> Dict[str, Union[str, Dict, List[Dict[str, str]]]]:
        """
        Recursively build a **multi-mapping** dictionary where each subdirectory
        becomes its own top-level key. For example, if `rel_dir='sub1'`, any
        direct files in `sub1` are stored under the `'sub1'` key, and a subfolder
        `sub2` becomes `'sub1/sub2'` (and so on).

        If current folder is a version parent folder, child folders are treated as
        version folders with files returned as list of version dicts.
        """

        container: Dict[str, Union[str, Dict, List[Dict[str, str]]]] = {}
        direct_files: Dict[str, str] = {}

        # Check if current folder is a version parent
        current_folder_basename = path.basename(current_dir)
        is_version_parent = current_folder_basename in version_parents_set

        for item in listdir(current_dir):
            full_path = path.join(current_dir, item)

            # Check if subdirectory & recursion allowed
            if path.isdir(full_path) and (
                recursive_levels == -1
                or (recursive_levels and current_level < recursive_levels)
            ):
                # Build the subdirectory's relative path
                sub_rel_dir = f"{prefix}{key_sep}{item}" if prefix else item

                # Handle version parent folders differently
                if is_version_parent:
                    # Check if this child folder contains only files (versioned attribute)
                    child_items = listdir(full_path)
                    has_subdirs = any(
                        path.isdir(path.join(full_path, child_item))
                        for child_item in child_items
                    )

                    # If folder contains ONLY files, treat as versioned attribute folder
                    if not has_subdirs and child_items:
                        # Each file becomes a version
                        version_list = []

                        for version_file in child_items:
                            version_file_path = path.join(full_path, version_file)

                            if path.isfile(version_file_path) and _file_matches_patterns(
                                version_file
                            ):
                                # Version name is the filename (with or without extension)
                                version_name = (
                                    version_file
                                    if keep_extension
                                    else get_main_name(version_file)
                                )
                                # Content is the file content (string)
                                version_content = _read_file(version_file_path)

                                version_list.append(
                                    {
                                        "version": version_name,
                                        "content": version_content,
                                    }
                                )

                        # Store the versioned attribute in direct_files
                        direct_files[item] = version_list
                    else:
                        # Has subdirectories or is empty - recurse normally
                        sub_result = _read_with_last_subdir_files_in_mapping(
                            full_path, current_level + 1, sub_rel_dir
                        )
                        for k, v in sub_result.items():
                            container[k] = v
                else:
                    # Normal subdirectory - recurse
                    sub_result = _read_with_last_subdir_files_in_mapping(
                        full_path, current_level + 1, sub_rel_dir
                    )

                    # Merge subdirectory results
                    for k, v in sub_result.items():
                        container[k] = v

            elif path.isfile(full_path):
                # It's a file => read if it matches patterns
                if _file_matches_patterns(item):
                    # Possibly remove extension
                    file_key = item if keep_extension else get_main_name(item)
                    direct_files[file_key] = _read_file(full_path)

        # Store direct files for current directory
        if direct_files:
            if prefix:
                container[prefix] = direct_files
            else:
                # top-level => merge directly
                for fname, content in direct_files.items():
                    container[fname] = content

        return container

    def _read_with_subdir_files_flat(
        current_dir: str, current_level: int, prefix: str = ""
    ) -> Dict[str, str]:
        """
        Build a **flat** dictionary structure:
        { "subdir/file.ext": content, "top.txt": content, ... }
        """
        result: Dict[str, str] = {}
        for filename in listdir(current_dir):
            full_path = path.join(current_dir, filename)
            rel_key = f"{prefix}{filename}" if prefix else filename

            if path.isdir(full_path):
                # Recurse deeper if allowed
                if recursive_levels == -1 or (
                    recursive_levels and current_level < recursive_levels
                ):
                    sub_result = _read_with_subdir_files_flat(
                        full_path, current_level + 1, prefix=rel_key + key_sep
                    )
                    result.update(sub_result)
            else:
                # It's a file
                if _file_matches_patterns(filename):
                    if keep_extension:
                        dict_key = rel_key
                    else:
                        # e.g., "level1/sub.txt" => "level1/sub"
                        if key_sep in rel_key:
                            # split on the last slash
                            slash_idx = rel_key.rindex(key_sep)
                            folder_part = rel_key[:slash_idx]
                            file_part = rel_key[slash_idx + len(key_sep) :]
                            dict_key = f"{folder_part}{key_sep}{get_main_name(file_part)}"
                        else:
                            dict_key = get_main_name(rel_key)
                    result[dict_key] = _read_file(full_path)
        return result

    def _read_file(fp: str) -> str:
        """Helper to read a file's content with the given encoding."""
        with open(fp, encoding=encoding) as f:
            return f.read() if read_file_method is None else read_file_method(f)

    # 3) If we're dealing with a directory
    if collect_subdir_files_in_one_mapping:
        # Return a nested dictionary structure
        return _read_with_last_subdir_files_in_mapping(file_path, 0, prefix="")
    else:
        # Return a flat dictionary with optional prefix
        return _read_with_subdir_files_flat(file_path, 0, prefix="")


def read_all_text(
    file_path: str,
    encoding: Optional[str] = None,
    file_patterns: Union[str, List[str], None] = None,
    keep_extension: bool = True,
    key_sep: str = "/",
    allow_reading_from_folder: bool = True,
    recursive_levels: Optional[int] = 0,
    collect_subdir_files_in_one_mapping: bool = False,
    version_parent_folders: Union[str, List[str], None] = None,
) -> Union[str, Dict[str, Union[str, Dict]]]:
    """
    Reads plain-text content from a file or multiple files in a directory.

    This is a convenience wrapper around `read_all(...)` with `read_file_method=None`,
    ensuring all files are read as text. It supports optional file-pattern filtering,
    recursive directory traversal, and nested vs. flat dictionary output.

    Args:
        file_path (str):
            Path to a single file or directory.
        encoding (Optional[str]):
            File encoding (defaults to system's default).
        file_patterns (Union[str, List[str], None]):
            Glob patterns for filtering filenames (e.g., "*.txt|*.md").
            If `None`, all files are included.
        keep_extension (bool):
            Whether to keep file extensions in dictionary keys when reading a directory.
            Defaults to `True`.
        key_sep (str):
            The string used to separate directory components in the dictionary keys.
            Defaults to `'/'`. May be one or more characters (e.g. `'->'`).
        allow_reading_from_folder (bool):
            If `False`, raises a `ValueError` if `file_path` is a directory.
            Defaults to `True`.
        recursive_levels (Union[int, None]):
            Maximum depth of subdirectory recursion:
              * 0 or None => no recursion (default),
              * a positive integer => that many levels,
              * -1 => infinite recursion.
        collect_subdir_files_in_one_mapping (bool):
            If `False`, creates a flat dict (`"subdir/file.ext": content`).
            If `True`, returns nested dicts for subdirectories.
        version_parent_folders (Union[str, List[str], None]):
            Optional folder name(s) to designate as "version parent folders".

    Returns:
        Union[str, Dict[str, Union[str, Dict]]]:
            - `str` if reading a single file,
            - `Dict` of file-name→string-content otherwise.

    Raises:
        ValueError: If the path doesn't exist or `allow_reading_from_folder=False` on a directory.

    See Also:
        `read_all(...)` for a more general function that supports custom file-reading methods.
    """
    return read_all(
        file_path=file_path,
        encoding=encoding,
        file_patterns=file_patterns,
        keep_extension=keep_extension,
        key_sep=key_sep,
        allow_reading_from_folder=allow_reading_from_folder,
        recursive_levels=recursive_levels,
        collect_subdir_files_in_one_mapping=collect_subdir_files_in_one_mapping,
        read_file_method=None,
        version_parent_folders=version_parent_folders,
    )


def read_all_(
    file_path_or_content: Union[str, Mapping[Any, str]],
    encoding: Optional[str] = None,
    file_patterns: Union[str, List[str], None] = None,
    keep_extension: bool = True,
    key_sep: str = "/",
    allow_reading_from_folder: bool = True,
    recursive_levels: Optional[int] = 0,
    collect_subdir_files_in_one_mapping: bool = False,
    read_file_method: Callable = None,
    version_parent_folders: Union[str, List[str], None] = None,
) -> Union[Any, Dict[str, Any]]:
    """
    Reads content from a file/directory or returns raw text, now allowing **nested dictionaries**.

    This function can handle:
      * A **file path** (read as text or with a custom `read_file_method`).
      * A **directory path** (returns a dict of `{filename: file_content}` if `allow_reading_from_folder=True`).
      * **Raw text** (simply returned if the path doesn't exist).
      * A **mapping/dict**, where each key→value pair is processed by the same rules:
        - If the value is a **string**, we check if it's a file/directory path or raw text.
        - If the value is another **dict**, we recursively call `read_all_` on that sub-dict.

    Args:
        file_path_or_content (Union[str, Mapping[Any, str]]):
            A file/directory path or string, or a dict mapping keys to paths/strings.
        encoding (Optional[str]):
            The encoding to use when reading files. Defaults to system's default.
        file_patterns (Union[str, List[str], None]):
            Glob patterns (e.g. `"*.txt|*.md"` or `["*.txt", "*.md"]`) to filter filenames.
            If `None`, all files are included.
        keep_extension (bool):
            If reading a directory, whether to keep file extensions in the dictionary keys. Defaults to True.
        key_sep (str):
            The string used to separate directory components in the dictionary keys.
            Defaults to `'/'`. May be one or more characters (e.g. `'->'`).
        allow_reading_from_folder (bool):
            If `False`, raises `ValueError` when given a directory path. Defaults to True.
        recursive_levels (Union[int, None]):
            Maximum depth of subdirectory recursion:
              * 0 or None => no recursion (default),
              * a positive integer => that many levels,
              * -1 => infinite recursion.
        collect_subdir_files_in_one_mapping (bool):
            * `False` => produce a **flat** dict of `"subdir/file.ext" → content`.
            * `True` => produce a **nested** dict with subfolders as subdicts.
        read_file_method (Callable, optional):
            A custom function `(file_obj) -> Any`. If `None`, reads plain text. Otherwise,
            this function can parse JSON, CSV, etc.
        version_parent_folders (Union[str, List[str], None]):
            Optional folder name(s) to designate as "version parent folders".

    Returns:
        Union[Any, Dict[str, Any]]:
            * **Any** if `file_path_or_content` is a **single file** or **raw text** (the return might
              be a `str` or any custom type from `read_file_method`).
            * **Dict[str, Any]** if input is a **directory** or a **mapping** of items.

    Notes:
        1. If the input string is not a mapping **and** exists on disk:
           - If it's a file, return its content (plain text or custom).
           - If it's a directory & `allow_reading_from_folder=True`, return a dict of `{filename: content}`.
           - If it's a directory & `allow_reading_from_folder=False`, raise `ValueError`.
        2. If the input string is not a mapping and does **not** exist on disk:
           - Return it directly (raw text).
        3. If the input **is** a mapping (e.g., dict):
           - Recursively apply these rules to each value.

    See Also:
        :func:`read_all` – The core function for reading a **single** file or directory path.
        :func:`read_all_text_` – A convenience wrapper for plain-text reading of arbitrary inputs.
    """

    def _read_all_from_file_path_or_content(_file_path_or_content):
        if path.exists(_file_path_or_content):
            return read_all(
                _file_path_or_content,
                encoding=encoding,
                file_patterns=file_patterns,
                keep_extension=keep_extension,
                key_sep=key_sep,
                allow_reading_from_folder=allow_reading_from_folder,
                recursive_levels=recursive_levels,
                collect_subdir_files_in_one_mapping=collect_subdir_files_in_one_mapping,
                read_file_method=read_file_method,
                version_parent_folders=version_parent_folders,
            )

        return _file_path_or_content

    if isinstance(file_path_or_content, Mapping):
        return {
            text_key: (
                _read_all_from_file_path_or_content(text_item)
                if isinstance(text_item, str)
                else read_all_(
                    text_item,
                    encoding=encoding,
                    file_patterns=file_patterns,
                    keep_extension=keep_extension,
                    key_sep=key_sep,
                    allow_reading_from_folder=allow_reading_from_folder,
                    recursive_levels=recursive_levels,
                    collect_subdir_files_in_one_mapping=collect_subdir_files_in_one_mapping,
                    read_file_method=read_file_method,
                    version_parent_folders=version_parent_folders,
                )
            )
            for text_key, text_item in file_path_or_content.items()
        }
    else:
        return _read_all_from_file_path_or_content(file_path_or_content)


def read_all_text_(
    file_path_or_content: Union[str, Mapping[Any, str]],
    encoding: Optional[str] = None,
    file_patterns: Union[str, List[str], None] = None,
    keep_extension: bool = True,
    key_sep: str = "/",
    allow_reading_from_folder: bool = True,
    recursive_levels: Optional[int] = 0,
    collect_subdir_files_in_one_mapping: bool = False,
    version_parent_folders: Union[str, List[str], None] = None,
) -> Union[str, Dict[str, str], Dict[Any, str]]:
    """
    Reads content as **plain text** from a file/directory, raw string, or dictionary of such inputs.

    This is a convenience wrapper around :func:`read_all_` with ``read_file_method=None``, ensuring
    every file is opened and returned as **text** (a string). It can handle:

      - A single file path (returns file text),
      - A directory path (returns a dict of filename→text if `allow_reading_from_folder=True`),
      - A raw string (simply passed through if not on disk),
      - A dictionary mapping keys to any combination of file/directory paths or strings.

    All other arguments and behaviors (e.g., `recursive_levels`, `file_patterns`, nesting) match
    those of :func:`read_all_`.

    Args:
        file_path_or_content (Union[str, Mapping[Any, str]]):
            A path (file or directory), a string, or a dict of them.
        encoding (Optional[str]):
            Encoding for reading files. Defaults to system's default.
        file_patterns (Union[str, List[str], None]):
            Glob patterns for filtering filenames (`"*.txt|*.md"`, etc.).
        keep_extension (bool):
            Whether to keep file extensions in dictionary keys (when reading directories).
        key_sep (str):
            The string used to separate directory components in the dictionary keys.
            Defaults to `'/'`. May be one or more characters (e.g. `'->'`).
        allow_reading_from_folder (bool):
            If `False`, raises a `ValueError` if a directory path is given.
        recursive_levels (Union[int, None]):
            Maximum depth of subdirectory recursion:
              * 0 or None => no recursion (default),
              * a positive integer => that many levels,
              * -1 => infinite recursion.
        collect_subdir_files_in_one_mapping (bool):
            If `False`, produce a flat dict of `"subdir/file.ext": text`.
            If `True`, produce nested dicts for subfolders.
        version_parent_folders (Union[str, List[str], None]):
            Optional folder name(s) to designate as "version parent folders".

    Returns:
        Union[str, Dict[str, str], Dict[Any, str]]:
            A string if reading a single file or raw text, otherwise a dict of text content.

    See Also:
        :func:`read_all_` – The more general function allowing a custom `read_file_method`.
    """
    return read_all_(
        file_path_or_content=file_path_or_content,
        encoding=encoding,
        file_patterns=file_patterns,
        keep_extension=keep_extension,
        key_sep=key_sep,
        allow_reading_from_folder=allow_reading_from_folder,
        recursive_levels=recursive_levels,
        collect_subdir_files_in_one_mapping=collect_subdir_files_in_one_mapping,
        read_file_method=None,
        version_parent_folders=version_parent_folders,
    )
