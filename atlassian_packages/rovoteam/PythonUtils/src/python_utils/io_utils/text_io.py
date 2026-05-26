import fnmatch
import random
from itertools import islice
from os import listdir, path
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Iterator,
    List,
    Mapping,
    Optional,
    Union,
)

from python_utils.common_utils.iter_helper import chunk_iter, tqdm_wrap, with_names
from python_utils.common_utils.typing_helper import str2val_
from python_utils.io_utils.common import open_, DEFAULT_ENCODING
from python_utils.path_utils.path_listing import NOEXT_PATTERN, sort_paths
from python_utils.path_utils.path_string_operations import (
    get_main_name,
    make_ext_name,
)
from python_utils.string_utils.common import strip_


# region reading
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
              * If `read_file_method` is `None`, returns a string (the file’s text).
              * Otherwise, returns whatever `read_file_method(file_object)` produces.
            - If `file_path` is a directory:
              * Returns a dictionary whose values are either file text (if `read_file_method=None`)
                or the return values of `read_file_method(file_object)` (any type).
              * The dictionary may be flat or nested, depending on `collect_subdir_files_in_one_mapping`.

    Raises:
        ValueError:
            - If `file_path` does not exist or is neither a valid file nor a valid directory.
            - If `allow_reading_from_folder=False` and `file_path` is a directory.

    Examples:
        1) Reading a single file:
        >>> import os
        >>> import tempfile
        >>> with tempfile.NamedTemporaryFile("w+", encoding="utf-8", delete=False) as temp_file:
        ...     _ = temp_file.write("Hello, temporary world!")
        ...     temp_file_path = temp_file.name
        >>> read_all(temp_file_path, encoding="utf-8")
        'Hello, temporary world!'
        >>> os.remove(temp_file_path)  # Clean up

        2) Reading all files in a directory:
        >>> with tempfile.TemporaryDirectory() as tmp_dir:
        ...     file1 = os.path.join(tmp_dir, "example1.txt")
        ...     file2 = os.path.join(tmp_dir, "example2.md")
        ...     with open(file1, "w", encoding="utf-8") as f1:
        ...         _ = f1.write("Content of file1")
        ...     with open(file2, "w", encoding="utf-8") as f2:
        ...         _ = f2.write("Content of file2")
        ...
        ...     assert read_all(tmp_dir) == {'example1.txt': 'Content of file1', 'example2.md': 'Content of file2'}

        3) Filtering by file name patterns with a single string:
        >>> with tempfile.TemporaryDirectory() as tmp_dir:
        ...     txt_file = os.path.join(tmp_dir, "doc1.txt")
        ...     md_file  = os.path.join(tmp_dir, "doc2.md")
        ...     png_file = os.path.join(tmp_dir, "image.png")
        ...     with open(txt_file, "w", encoding="utf-8") as f:
        ...         _ = f.write("TXT content")
        ...     with open(md_file, "w", encoding="utf-8") as f:
        ...         _ = f.write("MD content")
        ...     with open(png_file, "w", encoding="utf-8") as f:
        ...         _ = f.write("PNG content")
        ...
        ...     # Filter by *.txt or *.md (pipe-separated)
        ...     assert read_all(tmp_dir, file_patterns="*.txt|*.md") == {'doc1.txt': 'TXT content', 'doc2.md': 'MD content'}

        4) Removing file extensions from dictionary keys:
        >>> with tempfile.TemporaryDirectory() as tmp_dir:
        ...     file1 = os.path.join(tmp_dir, "report.txt")
        ...     file2 = os.path.join(tmp_dir, "notes.md")
        ...     with open(file1, "w", encoding="utf-8") as f:
        ...         _ = f.write("Text content")
        ...     with open(file2, "w", encoding="utf-8") as f:
        ...         _ = f.write("Markdown content")
        ...
        ...     assert read_all(tmp_dir, file_patterns="*.txt|*.md", keep_extension=False) == {'notes': 'Markdown content', 'report': 'Text content'}

        5) Filtering only files **without** any extension (using `NOEXT_PATTERN`):
        >>> from python_utils.path_utils.path_listing import NOEXT_PATTERN
        >>> with tempfile.TemporaryDirectory() as tmp_dir:
        ...     no_ext_file = os.path.join(tmp_dir, "no_extension")
        ...     txt_file    = os.path.join(tmp_dir, "some.txt")
        ...     with open(no_ext_file, "w", encoding="utf-8") as f:
        ...         _ = f.write("No extension content")
        ...     with open(txt_file, "w", encoding="utf-8") as f:
        ...         _ = f.write("Has extension content")
        ...
        ...     assert read_all(tmp_dir, file_patterns=NOEXT_PATTERN) == {'no_extension': 'No extension content'}

        6) Recursively read files up to 1 level deep:
        >>> with tempfile.TemporaryDirectory() as tmp_dir:
        ...     # Create a subdirectory
        ...     sub_dir = os.path.join(tmp_dir, "level1")
        ...     os.mkdir(sub_dir)
        ...
        ...     # File in the main directory
        ...     top_file = os.path.join(tmp_dir, "top.txt")
        ...     with open(top_file, "w", encoding="utf-8") as f:
        ...         _ = f.write("Top-level file content")
        ...
        ...     # File inside level1 subdirectory
        ...     sub_file = os.path.join(sub_dir, "sub.txt")
        ...     with open(sub_file, "w", encoding="utf-8") as f:
        ...         _ = f.write("Subdirectory file content")
        ...
        ...     # By default, we don't recurse into subdirectories:
        ...     assert read_all(tmp_dir, keep_extension=False) == {'top': 'Top-level file content'}
        ...     # With recursive_levels=1, we read one level deep:
        ...     assert read_all(tmp_dir, recursive_levels=1, keep_extension=False) == {'level1/sub': 'Subdirectory file content', 'top': 'Top-level file content'}


        7) Nested structure with subdirectories (collect_subdir_files_in_one_mapping=True):
        >>> with tempfile.TemporaryDirectory() as tmp_dir:
        ...     sub_dir = os.path.join(tmp_dir, "level1")
        ...     os.mkdir(sub_dir)
        ...
        ...     top_file = os.path.join(tmp_dir, "top.txt")
        ...     with open(top_file, "w", encoding="utf-8") as f:
        ...         _ = f.write("Top-level file content")
        ...
        ...     sub_file = os.path.join(sub_dir, "sub.txt")
        ...     with open(sub_file, "w", encoding="utf-8") as f:
        ...         _ = f.write("Subdirectory file content")
        ...
        ...     assert read_all(tmp_dir, recursive_levels=1, keep_extension=False, collect_subdir_files_in_one_mapping=True) == {'level1': {'sub': 'Subdirectory file content'}, 'top': 'Top-level file content'}

        8) Recursively read **3 levels** (flat) with multiple files at each level:
        >>> with tempfile.TemporaryDirectory() as tmp_dir:
        ...     lvl1 = os.path.join(tmp_dir, "level1")
        ...     lvl2 = os.path.join(lvl1, "level2")
        ...     lvl3 = os.path.join(lvl2, "level3")
        ...     os.mkdir(lvl1)
        ...     os.mkdir(lvl2)
        ...     os.mkdir(lvl3)
        ...
        ...     # Create multiple files at each level
        ...     files = [
        ...         (tmp_dir, "topA.txt",  "Top-level A"),
        ...         (tmp_dir, "topB.txt",  "Top-level B"),
        ...         (lvl1,    "f1a.txt",   "First-level A"),
        ...         (lvl1,    "f1b.txt",   "First-level B"),
        ...         (lvl2,    "f2a.txt",   "Second-level A"),
        ...         (lvl2,    "f2b.txt",   "Second-level B"),
        ...         (lvl3,    "f3a.txt",   "Third-level A"),
        ...         (lvl3,    "f3b.txt",   "Third-level B"),
        ...     ]
        ...     for d, fname, content in files:
        ...         with open(os.path.join(d, fname), "w", encoding="utf-8") as fp:
        ...             _ = fp.write(content)
        ...
        ...     read_all(tmp_dir, recursive_levels=3, keep_extension=False)
        ...     read_all(
        ...             tmp_dir, recursive_levels=3, keep_extension=False, collect_subdir_files_in_one_mapping=True
        ...     )
        {'level1/level2/f2a': 'Second-level A', 'level1/level2/f2b': 'Second-level B', 'level1/level2/level3/f3b': 'Third-level B', 'level1/level2/level3/f3a': 'Third-level A', 'level1/f1b': 'First-level B', 'level1/f1a': 'First-level A', 'topB': 'Top-level B', 'topA': 'Top-level A'}
        {'level1/level2/level3': {'f3b': 'Third-level B', 'f3a': 'Third-level A'}, 'level1/level2': {'f2a': 'Second-level A', 'f2b': 'Second-level B'}, 'level1': {'f1b': 'First-level B', 'f1a': 'First-level A'}, 'topB': 'Top-level B', 'topA': 'Top-level A'}

        9) Reading JSON files with a custom `read_file_method`:
        >>> import json
        >>> def read_json(file_obj):
        ...     return json.load(file_obj)
        ...
        >>> with tempfile.TemporaryDirectory() as tmp_dir:
        ...     j1 = os.path.join(tmp_dir, "data1.json")
        ...     j2 = os.path.join(tmp_dir, "data2.json")
        ...     with open(j1, "w", encoding="utf-8") as f1:
        ...         _ = f1.write('{\"key\": \"value1\"}')
        ...     with open(j2, "w", encoding="utf-8") as f2:
        ...         _ = f2.write('{\"other\": 42}')
        ...
        ...     # Now read them as JSON objects instead of raw text
        ...     results = read_all(tmp_dir, file_patterns=\"*.json\", read_file_method=read_json)
        ...     assert sorted(results.items()) == [('data1.json', {'key': 'value1'}), ('data2.json', {'other': 42})]

        10) Using a custom key separator:
        >>> with tempfile.TemporaryDirectory() as tmp_dir:
        ...     level1 = os.path.join(tmp_dir, "folderA")
        ...     os.mkdir(level1)
        ...     f_top = os.path.join(tmp_dir, "top.txt")
        ...     with open(f_top, "w") as ft: _ = ft.write("Top content")
        ...     f_sub = os.path.join(level1, "sub.txt")
        ...     with open(f_sub, "w") as fs: _ = fs.write("Sub content")
        ...
        ...     # We'll use " -> " as our separator:
        ...     assert read_all(tmp_dir, recursive_levels=1, key_sep=" -> ") == {'folderA -> sub.txt': 'Sub content', 'top.txt': 'Top content'}

        11) Deeper subfolders with `recursive_levels` set to -1:
        >>> with tempfile.TemporaryDirectory() as tmp_dir:
        ...     sub1 = os.path.join(tmp_dir, "sub1")
        ...     sub2 = os.path.join(sub1, "sub2")
        ...     sub3 = os.path.join(sub2, "sub3")
        ...     os.makedirs(sub3)
        ...     _ = open(os.path.join(sub1,"fileA.txt"), "w").write("Sub1 A")
        ...     _ = open(os.path.join(sub2,"fileB.txt"), "w").write("Sub2 B")
        ...     _ = open(os.path.join(sub2,"fileC.txt"), "w").write("Sub2 C")
        ...     _ = open(os.path.join(sub3,"fileD.txt"), "w").write("Sub3 D")
        ...
        ...     # If recursive_levels=1, we read 'sub1/fileA.txt' but do NOT descend into 'sub2'.
        ...     # So 'sub2' is NOT shown as a key, because it's neither a file nor fully read.
        ...     assert read_all(tmp_dir, recursive_levels=-1, keep_extension=False) == {'sub1/fileA': 'Sub1 A', 'sub1/sub2/fileB': 'Sub2 B', 'sub1/sub2/fileC': 'Sub2 C', 'sub1/sub2/sub3/fileD': 'Sub3 D'}
        ...     assert read_all(tmp_dir, recursive_levels=-1, keep_extension=False, collect_subdir_files_in_one_mapping=True) == {'sub1/sub2/sub3': {'fileD': 'Sub3 D'}, 'sub1/sub2': {'fileB': 'Sub2 B', 'fileC': 'Sub2 C'}, 'sub1': {'fileA': 'Sub1 A'}}

        12) Versioned folders with version_parent_folders:
        >>> with tempfile.TemporaryDirectory() as tmp_dir:
        ...     # Create structure with version parent folder containing both versioned attributes and direct files
        ...     level3_dir = os.path.join(tmp_dir, "level3")
        ...     attr1_dir = os.path.join(level3_dir, "attr1")
        ...     attr2_dir = os.path.join(level3_dir, "attr2")
        ...     os.makedirs(attr1_dir)
        ...     os.makedirs(attr2_dir)
        ...
        ...     # Add version files directly under attr1 (v1.txt, v2.txt)
        ...     with open(os.path.join(attr1_dir, "v1.txt"), "w") as f:
        ...         _ = f.write("v1 content")
        ...     with open(os.path.join(attr1_dir, "v2.txt"), "w") as f:
        ...         _ = f.write("v2 content")
        ...
        ...     # Add version files directly under attr2 (v1.txt)
        ...     with open(os.path.join(attr2_dir, "v1.txt"), "w") as f:
        ...         _ = f.write("v1 data")
        ...
        ...     # Add direct files in level3
        ...     with open(os.path.join(level3_dir, "readme.txt"), "w") as f:
        ...         _ = f.write("Readme content")
        ...     with open(os.path.join(level3_dir, "info.txt"), "w") as f:
        ...         _ = f.write("Info content")
        ...
        ...     # Read with version_parent_folders="level3" and keep_extension=False
        ...     result = read_all(
        ...         tmp_dir,
        ...         recursive_levels=-1,
        ...         collect_subdir_files_in_one_mapping=True,
        ...         version_parent_folders="level3",
        ...         keep_extension=False
        ...     )
        ...
        ...     # Verify structure: direct files are strings, versioned attributes are lists
        ...     print(f"level3 keys: {sorted(result['level3'].keys())}")
        ...     print(f"attr1 type: {type(result['level3']['attr1'])}")
        ...     print(f"attr1 content: {result['level3']['attr1']}")
        ...     print(f"attr2 type: {type(result['level3']['attr2'])}")
        ...     print(f"attr2 content: {result['level3']['attr2']}")
        ...     print(f"readme type: {type(result['level3']['readme'])}")
        ...     print(f"readme content: {result['level3']['readme']}")
        ...     print(f"info type: {type(result['level3']['info'])}")
        ...     print(f"info content: {result['level3']['info']}")
        level3 keys: ['attr1', 'attr2', 'info', 'readme']
        attr1 type: <class 'list'>
        attr1 content: [{'version': 'v1', 'content': 'v1 content'}, {'version': 'v2', 'content': 'v2 content'}]
        attr2 type: <class 'list'>
        attr2 content: [{'version': 'v1', 'content': 'v1 data'}]
        readme type: <class 'str'>
        readme content: Readme content
        info type: <class 'str'>
        info content: Info content
    """
    if not path.exists(file_path):
        raise ValueError(f"The path does not exist: {file_path}")

    # 1) Single file => return its contents
    if path.isfile(file_path):
        with open(file_path, encoding=encoding) as f:
            return f.read()

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
                        path.isdir(path.join(full_path, item)) for item in child_items
                    )

                    # If folder contains ONLY files, treat as versioned attribute folder
                    if not has_subdirs and child_items:
                        # Each file becomes a version
                        version_list = []

                        for version_file in child_items:
                            version_file_path = path.join(full_path, version_file)

                            if path.isfile(
                                version_file_path
                            ) and _file_matches_patterns(version_file):
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
                            file_part = rel_key[slash_idx + 1 :]
                            dict_key = (
                                f"{folder_part}{key_sep}{get_main_name(file_part)}"
                            )
                        else:
                            dict_key = get_main_name(rel_key)
                    result[dict_key] = _read_file(full_path)
        return result

    def _read_file(fp: str) -> str:
        """Helper to read a file’s content with the given encoding."""
        with open(fp, encoding=encoding) as f:
            return f.read() if read_file_method is None else read_file_method(f)

    # 3) If we’re dealing with a directory
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
            File encoding (defaults to system’s default).
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

    Returns:
        Union[str, Dict[str, Union[str, Dict]]]:
            - `str` if reading a single file,
            - `Dict` of file-name→string-content otherwise.

    Raises:
        ValueError: If the path doesn’t exist or `allow_reading_from_folder=False` on a directory.

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
       * **Raw text** (simply returned if the path doesn’t exist).
       * A **mapping/dict**, where each key→value pair is processed by the same rules:
         - If the value is a **string**, we check if it’s a file/directory path or raw text.
         - If the value is another **dict**, we recursively call `read_all_` on that sub-dict.

     Args:
         file_path_or_content (Union[str, Mapping[Any, str]]):
             A file/directory path or string, or a dict mapping keys to paths/strings.
         encoding (Optional[str]):
             The encoding to use when reading files. Defaults to system’s default.
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

     Returns:
         Union[Any, Dict[str, Any]]:
             * **Any** if `file_path_or_content` is a **single file** or **raw text** (the return might
               be a `str` or any custom type from `read_file_method`).
             * **Dict[str, Any]** if input is a **directory** or a **mapping** of items.

     Notes:
         1. If the input string is not a mapping **and** exists on disk:
            - If it’s a file, return its content (plain text or custom).
            - If it’s a directory & `allow_reading_from_folder=True`, return a dict of `{filename: content}`.
            - If it’s a directory & `allow_reading_from_folder=False`, raise `ValueError`.
         2. If the input string is not a mapping and does **not** exist on disk:
            - Return it directly (raw text).
         3. If the input **is** a mapping (e.g., dict):
            - Recursively apply these rules to each value.

     Examples:
         1) Single file path:
         >>> import tempfile, os
         >>> with tempfile.NamedTemporaryFile("w+", encoding="utf-8", delete=False) as temp_file:
         ...     _ = temp_file.write("Hello from temp file!")
         ...     temp_file_path = temp_file.name
         ...
         >>> read_all_(temp_file_path, encoding="utf-8")
         'Hello from temp file!'
         >>> os.remove(temp_file_path)

         2) Raw text (not an existing file/directory):
         >>> read_all_("Hello directly!")
         'Hello directly!'

         3) Directory path → dictionary of filename→content:
         >>> with tempfile.TemporaryDirectory() as tmp_dir:
         ...     f1 = os.path.join(tmp_dir, "file1.txt")
         ...     with open(f1, "w", encoding="utf-8") as fd1:
         ...         _ = fd1.write("Text file content")
         ...
         ...     read_all_(tmp_dir)  # doctest: +ELLIPSIS
         {'file1.txt': 'Text file content'}

         4) Disallow reading from a directory:
         >>> with tempfile.TemporaryDirectory() as tmp_dir:
         ...     try:
         ...         read_all_(tmp_dir, allow_reading_from_folder=False)
         ...     except ValueError as e:
         ...         print(e)
         The path is a directory, but allow_reading_from_folder=False.

         5) Dictionary input (mapping keys → file paths or raw text):
         >>> with tempfile.TemporaryDirectory() as tmp_dir:
         ...     example_file = os.path.join(tmp_dir, "example_file.txt")
         ...     with open(example_file, "w", encoding="utf-8") as fd:
         ...         _ = fd.write("Hello from mapped file!")
         ...
         ...     inputs = {
         ...         "intro": "Hello raw text!",
         ...         "file_example": example_file
         ...     }
         ...
         ...     read_all_(inputs, encoding="utf-8")
         {'intro': 'Hello raw text!', 'file_example': 'Hello from mapped file!'}

         6) Dictionary with nested sub-dicts:
         >>> data_map = {
         ...     "raw_text": "This is raw text",
         ...     "sub_data": {
         ...         "path_or_text": "Nonexistent path => raw text",
         ...         "more": {
         ...             "even_deeper": "Hello deeper!"
         ...         }
         ...     }
         ... }
         >>> read_all_(data_map)
         {'raw_text': 'This is raw text', 'sub_data': {'path_or_text': 'Nonexistent path => raw text', 'more': {'even_deeper': 'Hello deeper!'}}}

         7) Mixed dictionary with subdirectory, missing file, and raw text:
         >>> with tempfile.TemporaryDirectory() as tmp_dir:
         ...     # Create a subfolder and a file inside it
         ...     sub = os.path.join(tmp_dir, "subdir")
         ...     os.mkdir(sub)
         ...     nested_file = os.path.join(sub, "nested.txt")
         ...     with open(nested_file, "w", encoding="utf-8") as nf:
         ...         _ = nf.write("Nested content")
         ...
         ...     # Non-existent file path
         ...     missing_file = os.path.join(tmp_dir, "no_such_file.txt")
         ...
         ...     # Mix them in a dictionary
         ...     complex_input = {
         ...         "raw_text": "Some raw string",
         ...         "dir_here": tmp_dir,
         ...         "nonexistent": missing_file,
         ...         "sub_folder": sub
         ...     }
         ...
         ...     # We'll read up to 1 level into directories
         ...     read_all_(
         ...         complex_input,
         ...         recursive_levels=1,
         ...         keep_extension=False
         ...     )
         {'raw_text': 'Some raw string', 'dir_here': {'subdir/nested': 'Nested content'}, 'nonexistent': '...no_such_file.txt', 'sub_folder': {'nested': 'Nested content'}}

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
            Encoding for reading files. Defaults to system’s default.
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


def write_all_text(
    text: str, file_path: str, encoding: Optional[str] = None, create_dir: bool = True
) -> None:
    """
    Writes the given text to a file, replacing any existing content.
    Args:
        text (str): the text to write to the file.
        file_path (str): the path to the file.
        encoding (Optional[str]): the encoding to use when writing to the file.
        create_dir (bool): If True, creates the parent directory if it does not exist.

    Returns:
        None
    """
    with open_(file_path, mode="w", encoding=encoding, create_dir=create_dir) as f:
        f.write(text)


def _iter_all_lines(
    file_path: str,
    use_tqdm: bool = False,
    description: str = None,
    lstrip: bool = False,
    rstrip: bool = True,
    encoding: str = None,
    parse: Union[str, Callable] = False,
    sample_rate: float = 1.0,
    verbose: bool = __debug__,
):
    """
    Iterates through all lines of a file, applying optional transformations
    such as stripping leading/trailing characters, parsing, and sampling.

    Args:
        file_path: The file path to be read.
        use_tqdm: A flag indicating whether to use tqdm for progress display. Defaults to False.
        description: A description for the tqdm progress bar.
            If not provided, it will be generated.
        lstrip: A flag indicating whether to remove leading characters from the left side of each line.
        rstrip: A flag indicating whether to remove trailing characters from the right side of each line.
        encoding: The encoding to be used for opening the file.
        parse: A callable or string that specifies the parsing function to apply to each line.
            If set to True, the default `str2val_` function is used.
            Defaults to False (no parsing).
        sample_rate: A float in the range [0, 1] specifying the probability of including each line in the output.
            Defaults to 1.0 (all lines are included).
        verbose: A flag indicating whether to display tqdm progress bar or not. Defaults to __debug__.

    Yields:
        The modified lines after applying the specified transformations.

    Examples:
        >>> import tempfile
        >>> test_file = tempfile.NamedTemporaryFile(delete=False)
        >>> assert test_file.write(b"   Line 1   \\n   Line 2   \\n   Line 3   ")
        >>> test_file.close()

        >>> list(_iter_all_lines(test_file.name,
        ...    lstrip=True,
        ...    rstrip=True,
        ...    use_tqdm=False,
        ...    verbose=False
        ... ))
        ['Line 1', 'Line 2', 'Line 3']

        >>> x = list(_iter_all_lines(test_file.name,
        ...    lstrip=True,
        ...    rstrip=True,
        ...    sample_rate=0.5,
        ...    use_tqdm=False,
        ...    verbose=False
        ... ))
        >>> assert len(x) <= 3
    """
    assert isinstance(sample_rate, float)
    assert 0.0 <= sample_rate <= 1.0

    description = (description or "read from file at {path}").format(path=file_path)

    if parse is False:
        with open_(
            file_path,
            "r",
            encoding=encoding,
            use_tqdm=use_tqdm,
            description=description,
            verbose=verbose,
        ) as fin:
            yield from (
                strip_(line, lstrip=lstrip, rstrip=rstrip)
                for line in fin
                if (sample_rate == 1.0 or random.uniform(0, 1) < sample_rate)
            )
    else:
        if parse is True:
            parse = str2val_
        with open_(
            file_path,
            "r",
            encoding=encoding,
            use_tqdm=use_tqdm,
            description=description,
            verbose=verbose,
        ) as fin:
            yield from (
                parse(strip_(line, lstrip=lstrip, rstrip=rstrip))
                for line in fin
                if (sample_rate == 1.0 or random.uniform(0, 1) < sample_rate)
            )


def iter_all_lines(
    file_path: Union[str, Iterable[str]],
    use_tqdm: bool = False,
    description: str = None,
    lstrip: bool = False,
    rstrip: bool = True,
    encoding: str = None,
    parse: Union[str, Callable] = False,
    sample_rate: float = 1.0,
    sort_path: Union[str, bool] = False,
    sort_by_basename: bool = False,
    verbose: bool = __debug__,
):
    """
    Iterates through all lines of a file or multiple files, applying optional transformations such as
    stripping leading/trailing characters, parsing, and sampling.

    Args:
        file_path: One or more file paths to read.
        use_tqdm: True if using tqdm to display progress; otherwise False.
        description: The message to display with the tqdm; the message can be a format pattern of a single
            parameter 'path', e.g., 'read from file at {path}'.
        lstrip: True if the spaces at the beginning of each read line should be stripped; otherwise False.
        rstrip: True if the spaces at the end of each read line should be stripped; otherwise False.
        encoding: Specifies encoding for the file, e.g., 'utf-8'.
        parse: True to parse each line as its most likely value, e.g., '2.178' to float 2.178,
            '[1,2,3,4]' to list [1,2,3,4]; or specify a customized callable for the string parsing.
        sample_rate: Randomly samples a ratio of lines and skips the others.
        sort_path: True to sort `file_path` if `file_path` contains multiple paths.
            See `sort_paths` function.
        sort_by_basename: True to sort the `file_path` using path base name
            rather than the whole path string. See `sort_paths` function.
        verbose: True if details of the execution should be printed on the terminal.

    Yields:
        The modified lines after applying the specified transformations.

    Examples:
        >>> import tempfile
        >>> test_file = tempfile.NamedTemporaryFile(delete=False)
        >>> assert test_file.write(b"   Line 1   \\n   Line 2   \\n   Line 3   ")
        >>> test_file.close()

        >>> list(iter_all_lines(test_file.name,
        ...    lstrip=True,
        ...    rstrip=True,
        ...    use_tqdm=False,
        ...    verbose=False
        ... ))
        ['Line 1', 'Line 2', 'Line 3']

        >>> test_file2 = tempfile.NamedTemporaryFile(delete=False)
        >>> assert test_file2.write(b"   Line 4   \\n   Line 5   \\n   Line 6   ")
        >>> test_file2.close()

        >>> list(iter_all_lines([test_file.name, test_file2.name],
        ...    lstrip=True,
        ...    rstrip=True,
        ...    use_tqdm=False,
        ...    verbose=False
        ... ))
        ['Line 1', 'Line 2', 'Line 3', 'Line 4', 'Line 5', 'Line 6']
    """
    if isinstance(file_path, str):
        yield from _iter_all_lines(
            file_path=file_path,
            use_tqdm=use_tqdm,
            description=description,
            lstrip=lstrip,
            rstrip=rstrip,
            encoding=encoding,
            parse=parse,
            sample_rate=sample_rate,
            verbose=verbose,
        )
    else:
        file_path = sort_paths(
            file_path, sort=sort_path, sort_by_basename=sort_by_basename
        )
        for _file_path in file_path:
            yield from _iter_all_lines(
                file_path=_file_path,
                use_tqdm=use_tqdm,
                description=description,
                lstrip=lstrip,
                rstrip=rstrip,
                encoding=encoding,
                parse=parse,
                sample_rate=sample_rate,
                verbose=verbose,
            )


def read_all_lines(
    file_path: Union[str, Iterable[str]],
    use_tqdm: bool = False,
    description: str = None,
    lstrip: bool = False,
    rstrip: bool = True,
    encoding: str = None,
    parse: Union[str, Callable] = False,
    sample_rate: float = 1.0,
    sort_path: Union[str, bool] = False,
    sort_by_basename: bool = False,
    verbose: bool = __debug__,
):
    """
    Works in the same way as :func:`iter_all_lines` but returns everything all at once.
    """

    return list(
        iter_all_lines(
            file_path=file_path,
            use_tqdm=use_tqdm,
            description=description,
            lstrip=lstrip,
            rstrip=rstrip,
            encoding=encoding,
            parse=parse,
            sample_rate=sample_rate,
            sort_path=sort_path,
            sort_by_basename=sort_by_basename,
            verbose=verbose,
        )
    )


# endregion


def iter_all_lines_from_all_files(
    input_paths,
    sample_rate=1.0,
    lstrip=False,
    rstrip=True,
    use_tqdm=False,
    tqdm_msg=None,
    verbose=__debug__,
    sort=False,
    sort_by_basename=False,
):
    """
    Iterates through all lines of a collection of input paths,
    with the options to sort input files, sub-sample lines,
    and strip the whitespaces at the start or the end of each line.
    """
    if isinstance(input_paths, str):
        input_paths = (input_paths,)
    else:
        input_paths = sort_paths(
            input_paths, sort=sort, sort_by_basename=sort_by_basename
        )
    if sample_rate >= 1.0:
        for file in input_paths:
            with open_(
                file, use_tqdm=use_tqdm, description=tqdm_msg, verbose=verbose
            ) as f:
                yield from (strip_(line, lstrip=lstrip, rstrip=rstrip) for line in f)
    else:
        for file in input_paths:
            with open_(
                file, use_tqdm=use_tqdm, description=tqdm_msg, verbose=verbose
            ) as f:
                for line in f:
                    if random.uniform(0, 1) < sample_rate:
                        yield strip_(line, lstrip=lstrip, rstrip=rstrip)


def read_all_lines_from_all_files(input_path, *args, **kwargs):
    return list(iter_all_lines_from_all_files(input_path, *args, **kwargs))


def _get_input_file_stream(
    file: Union[str, Iterable, Iterator],
    encoding: str,
    top: int,
    use_tqdm: bool,
    display_msg: str,
    verbose: bool,
):
    # Check if 'file' is a file path (string) or a file-like object
    if isinstance(file, str):
        # If it's a file path, open the file with the given encoding
        # Default to utf-8 to avoid Windows charmap encoding issues
        fin = open(file, encoding=encoding or DEFAULT_ENCODING)
    else:
        # If it's a file-like object, use it as is
        fin = file
        # Try to get the file name, if available, or set it ot 'an iterator' as a fallback
        if hasattr(file, "name"):
            file = file.name
        else:
            file = "an iterator"

    # Wrap the file stream with tqdm for progress display,
    # and use 'islice' to limit the number of lines read if 'top' is specified
    return tqdm_wrap(
        (islice(fin, top) if top else fin),
        use_tqdm=use_tqdm,
        tqdm_msg=display_msg.format(file) if display_msg else None,
        verbose=verbose,
    ), fin


# region write lines
def write_all_lines_to_stream(
    fout,
    iterable: Iterator[str],
    to_str: Callable[[Any], str] = None,
    remove_blank_lines: bool = False,
    avoid_repeated_new_line: bool = True,
):
    """
    Writes all lines from an iterable to a given output stream.

    Args:
        fout: The output stream to write to.
        iterable: An iterable of strings to be written to the stream.
        to_str: A function to convert items in the iterable to strings. If not provided, `str()` is used.
        remove_blank_lines: If True, blank lines will not be written to the output.
        avoid_repeated_new_line: If True, avoids writing an extra newline if the text already ends with one.

    Example:
        >>> from tempfile import NamedTemporaryFile
        >>> with NamedTemporaryFile("w+", encoding="utf-8") as temp_file:
        ...     write_all_lines_to_stream(temp_file, ['Line 1', 'Line 2', ''], remove_blank_lines=True)
        ...     temp_file.seek(0)
        ...     print(temp_file.read())
        0
        Line 1
        Line 2
        <BLANKLINE>
    """

    def _write_text(text):
        if len(text) == 0:
            if not remove_blank_lines:
                fout.write("\n")
        else:
            fout.write(text)
            if not avoid_repeated_new_line or text[-1] != "\n":
                fout.write("\n")

    if to_str is None:
        to_str = str

    for item in iterable:
        _write_text(to_str(item))

    fout.flush()


def write_all_lines(
    iterable: Iterator,
    output_path: str,
    to_str: Callable = None,
    use_tqdm: bool = False,
    display_msg: str = None,
    append: bool = False,
    encoding: str = None,
    verbose: bool = __debug__,
    create_dir: bool = True,
    remove_blank_lines: bool = False,
    avoid_repeated_new_line: bool = True,
    chunk_size: int = None,
    chunk_name_format: str = "part_{:05}",
    chunked_file_ext_name: str = ".txt",
):
    """
    Writes all lines from an iterable to a file. If chunk size is provided, it splits the iterable into chunks
    and writes each chunk to a separate file.

    Args:
        iterable: An iterable of strings.
        output_path: The path where to write the output.
        to_str: A function to convert items in iterable to string. If not provided, str() is used.
        use_tqdm: If True, tqdm progress bar is displayed.
        display_msg: The message to display in the tqdm progress bar.
        append: If True, data is appended to existing files. Otherwise, it overwrites any existing files.
        encoding: The encoding of the output file(s).
        verbose: If True, additional progress details are displayed.
        create_dir: If True, creates the parent directory if it does not exist.
        remove_blank_lines: If True, blank lines will not be written.
        avoid_repeated_new_line: If True, avoids writing a new line if the text already ends with a new line.
        chunk_size: If provided, splits the iterable into chunks of this size and writes each chunk to a separate file.
        chunk_name_format: The format of the chunk file names.
        chunked_file_ext_name: The extension name for the chunked files.

    Example:
        >>> import os
        >>> from tempfile import NamedTemporaryFile
        >>> with NamedTemporaryFile("w+", encoding="utf-8", delete=False) as temp_file:
        ...     temp_file_path = temp_file.name
        >>> write_all_lines(['Line 1', 'Line 2', ''], temp_file_path)
        overwrite file ...
        >>> with open(temp_file_path, 'r', encoding="utf-8") as f:
        ...     print(f.read())
        Line 1
        Line 2
        ...

        >>> os.remove(temp_file_path)  # Clean up the temporary file after testing
    """
    iterable = tqdm_wrap(
        iterable, use_tqdm=use_tqdm, tqdm_msg=display_msg, verbose=verbose
    )
    if chunk_size is None:
        with open_(
            output_path,
            "a+" if append else "w+",
            encoding=encoding,
            create_dir=create_dir,
            verbose=verbose,
        ) as wf:
            write_all_lines_to_stream(
                fout=wf,
                iterable=iterable,
                to_str=to_str,
                remove_blank_lines=remove_blank_lines,
                avoid_repeated_new_line=avoid_repeated_new_line,
            )
            wf.flush()
    else:
        chunked_file_ext_name = make_ext_name(chunked_file_ext_name)
        if path.isfile(output_path):
            output_path, _chunked_file_ext_name = path.splitext(output_path)
            if not chunked_file_ext_name:
                chunked_file_ext_name = _chunked_file_ext_name
            _chunked_file_main_name = path.basename(output_path)
            if _chunked_file_main_name:
                chunk_name_format = _chunked_file_main_name + "-" + chunk_name_format
            output_path = path.dirname(output_path)

        for chunk_name, chunk in with_names(
            chunk_iter(iterable, chunk_size=chunk_size),
            name_format=chunk_name_format,
            name_suffix=chunked_file_ext_name,
        ):
            with open_(
                path.join(output_path, chunk_name),
                "a+" if append else "w+",
                encoding=encoding,
                create_dir=create_dir,
                verbose=verbose,
            ) as wf:
                write_all_lines_to_stream(
                    fout=wf,
                    iterable=chunk,
                    to_str=to_str,
                    remove_blank_lines=remove_blank_lines,
                    avoid_repeated_new_line=avoid_repeated_new_line,
                )
                wf.flush()


# endregion
