import hashlib
import logging
import os
import re
import shutil
import unicodedata
from enum import IntEnum
from os import path
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union, Iterator

_logger = logging.getLogger(__name__)

NOEXT_PATTERN = 'NOEXT'


class FullPathMode(IntEnum):
    RelativePath = 0
    FullPath = 1
    BaseName = 2
    FullPathRelativePathTuple = 3


def sort_paths(
        paths: List[str],
        sort: Union[bool, str],
        sort_by_basename: bool = False
) -> List[str]:
    """
    Sorts a list of file paths according to the specified criteria: alphabetically, by base name,
    or by numerical indices extracted from the paths.

    Args:
        paths: A list of file paths to be sorted.
        sort: Determines the sorting criteria. If True or 'alphabetic', sorts paths alphabetically.
              If 'index', sorts paths based on numerical indices found in the paths or filenames.
        sort_by_basename: If True, sorts by the base name (filename) of each path.
                          If False, sorts by the entire path.

    Returns:
        The list of paths sorted according to the specified criteria.

    Examples:
        >>> paths = ["file3.txt", "file1.txt", "file2.txt"]
        >>> sort_paths(paths, sort=True)
        ['file1.txt', 'file2.txt', 'file3.txt']

        >>> paths = ["/path/to/file3.txt", "/path/to/file1.txt", "/path/to/file2.txt"]
        >>> sort_paths(paths, sort='alphabetic', sort_by_basename=True)
        ['/path/to/file1.txt', '/path/to/file2.txt', '/path/to/file3.txt']

        >>> paths = ["/path/to/file3_3.txt", "/path/to/file1_1.txt", "/path/to/file2_2.txt"]
        >>> sort_paths(paths, sort='index')
        ['/path/to/file1_1.txt', '/path/to/file2_2.txt', '/path/to/file3_3.txt']

        Note: For 'index' sorting, the function expects to find numerical indices in the paths or filenames.
              It sorts based on the first numerical index found in each path or filename.
    """
    if sort_by_basename:
        if sort is True or sort == 'alphabetic':
            return sorted(paths, key=lambda x: path.basename(x))
        elif sort == 'index':
            return sorted(paths, key=lambda x: int(re.search(r'[0-9]+', path.basename(x)).group()))
    else:
        if sort is True or sort == 'alphabetic':
            return sorted(paths)
        elif sort == 'index':
            return sorted(paths, key=lambda x: int(re.search(r'[0-9]+', x).group()))
    return paths


def iter_files_by_pattern(dir_or_dirs: str, pattern: str = '*', full_path: Union[FullPathMode, bool] = True,
                          recursive=True):
    """
    Iterate through the paths or file names of all files in a folder at path `dir_path` of a specified `pattern`.
    :param dir_or_dirs: the path to the folder.
    :param pattern: only iterate through files of this pattern, e.g. '*.json'; a pattern starts with `**/` indicates to recursively search all sub folders.
    :param full_path: `True` if the full path to each file should be returned; otherwise, only the file name will be returned.
    :param recursive: `True` if recursively searching all sub folders, equivalent to adding prefix `**/` in front of `pattern`; `False` has no actual effect.
    :return: an iterator that returns each file of the specified pattern in a folder at path `dir_path`.
    """

    def _iter_files(dir_path):
        nonlocal pattern
        if path.isdir(dir_path):
            if recursive and not pattern.startswith('**/'):
                pattern = '**/' + pattern
            if full_path is True or full_path == FullPathMode.FullPath:
                p = Path(path.abspath(dir_path))
                for f in p.glob(pattern):
                    if path.isfile(f):
                        yield str(f)
            elif full_path is False or full_path == FullPathMode.BaseName:
                p = Path(path.abspath(dir_path))
                for f in p.glob(pattern):
                    if path.isfile(f):
                        yield path.basename(f)
            elif full_path == FullPathMode.RelativePath:
                dir_path = path.abspath(dir_path)
                len_dir_path = len(dir_path)
                p = Path(path.abspath(dir_path))
                for f in p.glob(pattern):
                    if path.isfile(f):
                        f = str(f)
                        yield f[len_dir_path + 1:] if f[len_dir_path] == os.sep else f[len_dir_path:]
            elif full_path == FullPathMode.FullPathRelativePathTuple:
                dir_path = path.abspath(dir_path)
                len_dir_path = len(dir_path)
                p = Path(path.abspath(dir_path))
                for f in p.glob(pattern):
                    if path.isfile(f):
                        f = str(f)
                        yield (f, f[len_dir_path + 1:]) if f[len_dir_path] == os.sep else (f, f[len_dir_path:])

    if isinstance(dir_or_dirs, str):
        yield from _iter_files(dir_or_dirs)
    else:
        for dir_path in dir_or_dirs:
            yield from _iter_files(dir_path)


def get_paths_by_pattern(
        dir_or_dirs: Union[str, Iterator],
        pattern: str = '*',
        full_path: Union[FullPathMode, bool] = True,
        recursive=True,
        sort=False,
        sort_use_basename=False,
        path_filter='file'
):
    """
    Retrieves paths matching a given pattern within specified directory or directories,
    with options for full or relative paths, recursion, sorting, and filtering by file or directory.

    Args:
        dir_or_dirs: A single directory path or an iterator of directory paths to search within.
        pattern: Pattern to match the files or directories against, using Unix shell-style wildcards.
                 Defaults to '*', matching everything. Prepending with '**/' searches recursively,
                 similar to setting `recursive=True`.
        full_path: Determines the format of the returned paths. When True (default), returns full paths.
                   If False, returns only base names. Can also be an instance of FullPathMode for more options.
        recursive: If True, searches directories recursively. Equivalent to patterns starting with '**/'. Defaults to True.
        sort: If True, returns sorted list of paths. Defaults to False.
        sort_use_basename: If True and `sort` is also True, sorts the paths by their base names. Defaults to False.
        path_filter: Specifies whether to filter for 'file' or 'directory', or a custom function for filtering.
                     Defaults to 'file', filtering for files only.

    Returns:
        A list of paths matching the specified pattern and filters, formatted according to `full_path`.

    Examples:
        Suppose we have a directory structure as follows, and `dir_or_dirs` is set to '/path/to/directory':
        /path/to/directory/
        ├── file1.txt
        ├── file2.json
        └── subdirectory/
            └── file3.txt

        get_paths_by_pattern('/path/to/directory', '*.txt')
        # Returns ['/path/to/directory/file1.txt', '/path/to/directory/subdirectory/file3.txt']
        # if `recursive=True` and `full_path=True`.

        get_paths_by_pattern('/path/to/directory', '*.txt', full_path=False)
        # Returns ['file1.txt'] if `recursive=False`.

        get_paths_by_pattern(['/path/to/directory1', '/path/to/directory2'], '*.json', sort=True)
        # Returns sorted list of .json files from both directories if they exist.
    """

    if isinstance(path_filter, str):
        path_filter = getattr(path, f'is{path_filter}', None)

    def _proc1(f, len_dir_path):
        f = str(f)
        return f[len_dir_path + 1:] if f[len_dir_path] == os.sep else f[len_dir_path:]

    def _proc2(f, len_dir_path):
        f = str(f)
        return (f, f[len_dir_path + 1:]) if f[len_dir_path] == os.sep else (f, f[len_dir_path:])

    def _get_files(dir_path):
        nonlocal pattern
        if path.isdir(dir_path):
            if recursive and not pattern.startswith('**/'):
                pattern = '**/' + pattern

            if full_path is True or full_path == FullPathMode.FullPath:
                p = Path(path.abspath(dir_path))
                results = [str(f) for f in p.glob(pattern) if ((not path_filter) or path_filter(f))]
            elif full_path is False or full_path == FullPathMode.BaseName:
                p = Path(dir_path)
                results = [path.basename(f) for f in p.glob(pattern) if ((not path_filter) or path_filter(f))]
            elif full_path == FullPathMode.RelativePath:
                dir_path = path.abspath(dir_path)
                p = Path(dir_path)
                len_dir_path = len(dir_path)
                results = [_proc1(f, len_dir_path) for f in p.glob(pattern) if ((not path_filter) or path_filter(f))]
            elif full_path == FullPathMode.FullPathRelativePathTuple:
                dir_path = path.abspath(dir_path)
                p = Path(dir_path)
                len_dir_path = len(dir_path)
                results = [_proc2(f, len_dir_path) for f in p.glob(pattern) if ((not path_filter) or path_filter(f))]
            return sort_paths(results, sort=sort, sort_by_basename=sort_use_basename)
        else:
            return []

    return (
        _get_files(dir_or_dirs)
        if isinstance(dir_or_dirs, str)
        else sum([_get_files(dir_path) for dir_path in dir_or_dirs], [])
    )


def iter_all_sub_dirs(dir_path: str):
    """
    Iterate through all subdirectories of a given directory.

    This will yield nested subdirectories. The `os.walk` is a built-in Python function
    that generates a file and directory tree by walking through a given directory and
    all of its subdirectories, including nested subdirectories.

    Args:
        dir_path: Path to the parent directory containing the subdirectories.

    Returns:
        An iterator yielding the subdirectories within the given parent directory.
    """
    return map(lambda x: x[0], os.walk(dir_path))


def get_all_sub_dirs(dir_path: str) -> List[str]:
    """
    Get all subdirectories of a given directory.

    This will return nested subdirectories. The `os.walk` is a built-in Python function
    that generates a file and directory tree by walking through a given directory and
    all of its subdirectories, including nested subdirectories.

    Args:
        dir_path: Path to the parent directory containing the subdirectories.

    Returns:
        A list of subdirectories within the given parent directory.
    """
    return [x[0] for x in os.walk(dir_path)]


def get_files_by_pattern(
        dir_or_dirs: Union[str, Iterator],
        pattern: str = '*',
        full_path: Union[FullPathMode, bool] = True,
        recursive=True,
        sort: bool = False,
        sort_use_basename: bool = False
):
    """
    Get the paths or file names of all files from one or more directories matching a given pattern. By default
      - It returns **full paths** (`full_path=True`) to all files in the specified folder(s).
      - It **recursively** searches subfolders (`recursive=True`).
      - It returns **unsorted** results (`sort=False`).
      - The `pattern` default is "*" to match all files.

    For more control over how paths are returned, you can set `full_path` to:
      - `True` or `FullPathMode.FullPath`: return full (absolute) paths (the default).
      - `False` or `FullPathMode.BaseName`: return only the basename (e.g., "file.txt").
      - `FullPathMode.RelativePath`: return paths relative to the directory.
      - `FullPathMode.FullPathRelativePathTuple`: return a tuple `(full_path, relative_path)`.

    Likewise, you can specify:
      - `pattern`: a glob pattern like `*.txt` or `**/*.txt`.
      - `recursive=False`: to only search the top-level folder (no subfolders).
      - `sort=True` and `sort_use_basename=True`: to sort results by basename.
      - `sort=True` and `sort_use_basename=False`: to sort results by the full path string.

    Args:
        dir_or_dirs (Union[str, Iterator]):
            One directory path (str) or multiple directory paths (an iterator) in which to search.
        pattern (str):
            A glob pattern to match files, e.g. "*.json" or "**/*.txt".
            - Prefix with `**/` or set `recursive=True` to search subfolders recursively.
            Default is "*", which matches all files.
        full_path (Union[FullPathMode, bool]):
            Controls how file paths are returned:
              * `True` or `FullPathMode.FullPath` => full absolute paths (default).
              * `False` or `FullPathMode.BaseName` => just the file name without directories.
              * `FullPathMode.RelativePath` => relative path from the directory.
              * `FullPathMode.FullPathRelativePathTuple` => tuple of `(absolute_path, relative_path)`.
        recursive (bool):
            If True, recursively search subfolders (equivalent to prefixing pattern with `**/`).
            Default is True.
        sort (bool):
            If True, sort the returned results. Default is False.
        sort_use_basename (bool):
            If True, sort by the basename of each file rather than the full path. Default is False.

    Returns:
        List:
            A list of file paths (or file names, or tuple variants) matching `pattern`
            found in the specified directory or directories.

    Examples:
        >>> import tempfile

        1) Find all files (full paths) in a single directory** (default behavior):
        >>> with tempfile.TemporaryDirectory() as tmp_dir:
        ...     f1 = path.join(tmp_dir, "test1.txt")
        ...     f2 = path.join(tmp_dir, "test2.md")
        ...     fd1 = open(f1, 'w')
        ...     _ = fd1.write("some text")         # Suppress integer output
        ...     _ = fd1.close()
        ...     fd2 = open(f2, 'w')
        ...     _ = fd2.write("markdown content")  # Suppress integer output
        ...     _ = fd2.close()
        ...
        ...     # Retrieve all files with full absolute paths
        ...     files = get_files_by_pattern(tmp_dir)
        ...     sorted_files = sorted(files)
        ...     sorted_files
        ['...test1.txt', '...test2.md']

        2) Return only basenames:
        >>> with tempfile.TemporaryDirectory() as tmp_dir:
        ...     f1 = os.path.join(tmp_dir, "image1.png")
        ...     fd = open(f1, 'w')
        ...     _ = fd.write("PNG data")
        ...     _ = fd.close()
        ...     get_files_by_pattern(tmp_dir, full_path=False)
        ['image1.png']

        3) Search only top-level (non-recursive) for '*.txt' files, sorted by path:
        >>> with tempfile.TemporaryDirectory() as tmp_dir:
        ...     sub_dir = os.path.join(tmp_dir, "sub")
        ...     os.mkdir(sub_dir)
        ...     f1 = path.join(tmp_dir, "doc1.txt")
        ...     f2 = path.join(sub_dir, "doc2.txt")
        ...     with open(f1, 'w') as fd1:
        ...         _ = fd1.write("doc1 content")
        ...     with open(f2, 'w') as fd2:
        ...         _ = fd2.write("doc2 content")
        ...
        ...     # Only match top-level .txt (doc1.txt). doc2.txt is in sub/, so won't be found.
        ...     files = get_files_by_pattern(tmp_dir, pattern="*.txt", recursive=False, sort=True)
        ...     [os.path.basename(fp) for fp in files]
        ['doc1.txt']

        4) Use relative paths:
        >>> # Suppose FullPathMode is an Enum or a placeholder
        >>> with tempfile.TemporaryDirectory() as tmp_dir:
        ...     f1 = os.path.join(tmp_dir, "alpha.txt")
        ...     with open(f1, 'w') as fd:
        ...         _ = fd.write("alpha content")
        ...     get_files_by_pattern(tmp_dir, full_path=FullPathMode.FullPathRelativePathTuple)
        [('...alpha.txt', 'alpha.txt')]

        5) Multiple directories:
        >>> with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
        ...     f1 = path.join(tmp1, "a.txt")
        ...     f2 = path.join(tmp2, "b.txt")
        ...     open(f1, 'w').close()
        ...     open(f2, 'w').close()
        ...
        ...     # Provide an iterator of directories
        ...     files = get_files_by_pattern([tmp1, tmp2], pattern="*.txt", sort=True)
        ...     [os.path.basename(fp) for fp in files]
        ['a.txt', 'b.txt']

        6) Retrieve files **without any extension** using "NOEXT":
        >>> with tempfile.TemporaryDirectory() as tmp_dir:
        ...     noext = os.path.join(tmp_dir, "myfile")   # no dot here
        ...     hasext = os.path.join(tmp_dir, "example.md")
        ...     _ = open(noext, 'w').write("no extension content")
        ...     _ = open(hasext, 'w').write("markdown content")
        ...
        ...     files_noext = get_files_by_pattern(tmp_dir, pattern=NOEXT_PATTERN)
        ...     [os.path.basename(fp) for fp in files_noext]
        ['myfile']
    """

    noext_mode = (pattern == NOEXT_PATTERN)
    if noext_mode:
        pattern = '*'

    def _process_glob(glob_results):
        if noext_mode:
            return [
                f
                for f in glob_results
                if f.is_file() and '.' not in f.name
            ]
        else:
            return glob_results

    def _proc1(f, len_dir_path):
        # Process the file path to return the relative path
        f = str(f)
        return f[len_dir_path + 1:] if f[len_dir_path] == os.sep else f[len_dir_path:]

    def _proc2(f, len_dir_path):
        # Process the file path to return a tuple of full path and relative path
        f = str(f)
        return (f, f[len_dir_path + 1:]) if f[len_dir_path] == os.sep else (f, f[len_dir_path:])

    def _get_files(dir_path):
        nonlocal pattern

        if path.isdir(dir_path):
            if recursive and not pattern.startswith('**/'):
                pattern = '**/' + pattern

            if full_path is True or full_path == FullPathMode.FullPath:
                # Get files with full path
                p = Path(path.abspath(dir_path))
                results = [str(f) for f in _process_glob(p.glob(pattern)) if path.isfile(f)]
            elif full_path is False or full_path == FullPathMode.BaseName:
                # Get files with basename only
                p = Path(dir_path)
                results = [path.basename(f) for f in _process_glob(p.glob(pattern)) if path.isfile(f)]
            elif full_path == FullPathMode.RelativePath:
                # Get files with relative path
                dir_path = path.abspath(dir_path)
                p = Path(dir_path)
                len_dir_path = len(dir_path)
                results = [_proc1(f, len_dir_path) for f in _process_glob(p.glob(pattern)) if path.isfile(f)]
            elif full_path == FullPathMode.FullPathRelativePathTuple:
                # Get files with a tuple of full path and relative path
                dir_path = path.abspath(dir_path)
                p = Path(dir_path)
                len_dir_path = len(dir_path)
                results = [_proc2(f, len_dir_path) for f in _process_glob(p.glob(pattern)) if path.isfile(f)]
            return sort_paths(results, sort=sort, sort_by_basename=sort_use_basename)
        else:
            return []

    # Handle single directory and multiple directories cases
    return (
        _get_files(dir_or_dirs)
        if isinstance(dir_or_dirs, str)
        else sum([_get_files(dir_path) for dir_path in dir_or_dirs], [])
    )


def get_sorted_files_from_all_sub_dirs(dir_path: str, pattern: str, full_path: bool = True):
    """
    Get sorted files from all subdirectories (including nested subdirectories)
    of a given directory and matching a specified pattern.

    Args:
        dir_path: Path to the parent directory containing the subdirectories.
        pattern: Search for files of this pattern, e.g., '*.json'.
        full_path (optional): If True, the full path to each file should be returned; otherwise,
                              only the file name will be returned. Default is True.

    Returns:
        A sorted list of file paths of the specified file name pattern in all subdirectories of
        the given parent directory.

    """
    files = []
    sub_dirs = get_all_sub_dirs(dir_path)
    sub_dirs.sort()
    for sub_dir in sub_dirs:
        sub_dir_files = get_files_by_pattern(
            dir_or_dirs=sub_dir,
            pattern=pattern,
            full_path=full_path,
            recursive=False
        )
        sub_dir_files.sort()
        files.extend(sub_dir_files)
    return files


# ---------------------------------------------------------------------------
# Multi-root file diffing and conflict detection
# ---------------------------------------------------------------------------

from typing import NamedTuple


class FileCandidate(NamedTuple):
    """One root's version of a file."""
    root_name: str
    abs_path: str
    size: int
    sha256: str


class MultiRootDiff(NamedTuple):
    """Result of comparing files across multiple root directories."""
    agreed: List[Dict[str, Any]]
    conflicts: Dict[str, List[Dict[str, Any]]]


def canonicalize_text(content: bytes) -> bytes:
    """Normalize text for stable hashing (line endings, trailing whitespace, NFC).

    Binary files (UnicodeDecodeError) bypass normalization and return raw bytes.
    """
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return content
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    text = "\n".join(lines).rstrip("\n") + "\n"
    text = unicodedata.normalize("NFC", text)
    return text.encode("utf-8")


def hash_file_canonical(filepath: str, large_file_threshold: int = 10 * 1024 * 1024) -> str:
    """SHA-256 of canonical-normalized file content.

    Files larger than *large_file_threshold* are hashed raw (no normalization).
    """
    h = hashlib.sha256()
    size = os.path.getsize(filepath)
    if size > large_file_threshold:
        with open(filepath, "rb") as f:
            while chunk := f.read(64 * 1024):
                h.update(chunk)
        return h.hexdigest()
    with open(filepath, "rb") as f:
        h.update(canonicalize_text(f.read()))
    return h.hexdigest()


def find_conflicting_and_agreed_files(
    roots: List[str],
    root_names: Optional[List[str]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
    """Walk multiple root directories and categorize files as agreed or conflicting.

    For each relative path that appears under any root:
    - **Agreed**: all roots that have it produce the same canonical hash → returned
      in *agreed* list.
    - **Conflicting**: roots produce different hashes → returned in *conflicts* dict.

    Args:
        roots: List of directory paths to compare.
        root_names: Optional names for each root (for logging/reporting).
            Defaults to the directory basename.

    Returns:
        (agreed, conflicts) where:
        - agreed: list of ``{path, size, sha256, source_roots}``
        - conflicts: dict mapping ``rel_path → [{root_name, abs_path, size, sha256}, ...]``
    """
    if root_names is None:
        root_names = [os.path.basename(r) for r in roots]

    file_map: Dict[str, List[Dict[str, Any]]] = {}
    for root_dir, name in zip(roots, root_names):
        if not os.path.isdir(root_dir):
            continue
        for dirpath, dirs, files in os.walk(root_dir):
            for fname in files:
                abs_path = os.path.join(dirpath, fname)
                rel_path = os.path.relpath(abs_path, root_dir)
                size = os.path.getsize(abs_path)
                sha = hash_file_canonical(abs_path)
                file_map.setdefault(rel_path, []).append({
                    "root_name": name,
                    "abs_path": abs_path,
                    "size": size,
                    "sha256": sha,
                })

    agreed: List[Dict[str, Any]] = []
    conflicts: Dict[str, List[Dict[str, Any]]] = {}
    for rel_path, instances in sorted(file_map.items()):
        unique_hashes = {inst["sha256"] for inst in instances}
        if len(unique_hashes) == 1:
            agreed.append({
                "path": rel_path,
                "size": instances[0]["size"],
                "sha256": instances[0]["sha256"],
                "abs_path": instances[0]["abs_path"],
                "source_roots": [inst["root_name"] for inst in instances],
            })
        else:
            conflicts[rel_path] = instances
    return agreed, conflicts


def safe_copy_agreed(
    agreed: List[Dict[str, Any]],
    dest: str,
    skip_existing: bool = True,
) -> List[str]:
    """Copy agreed files to *dest*, optionally skipping files that already exist.

    Returns list of paths actually copied.
    """
    copied = []
    for entry in agreed:
        dst_path = os.path.join(dest, entry["path"])
        if skip_existing and os.path.exists(dst_path):
            continue
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        shutil.copy2(entry.get("abs_path", entry.get("source_abs_path", "")), dst_path)
        copied.append(entry["path"])
    return copied


def safe_copy_per_file(
    diff: Tuple[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]]],
    dest: str,
    skip_existing: bool = True,
    conflict_fallback: str = "largest",
) -> List[str]:
    """Copy files from a diff result to *dest* with conflict handling.

    For agreed files: copies to dest (skips if *skip_existing* and file exists).
    For conflicting files: applies *conflict_fallback* policy only if the file
    doesn't already exist at dest (i.e., the aggregator didn't write a merged version).

    Args:
        diff: Tuple of (agreed, conflicts) from ``find_conflicting_and_agreed_files``.
        dest: Destination directory.
        skip_existing: If True, never overwrite files already in dest.
        conflict_fallback: Policy for unresolved conflicts:
            - ``"largest"``: copy the largest candidate (heuristic: more complete).
            - ``"skip"``: don't copy anything for unresolved conflicts.

    Returns:
        List of relative paths actually copied.
    """
    agreed, conflicts = diff
    copied = safe_copy_agreed(agreed, dest, skip_existing=skip_existing)

    for rel_path, candidates in conflicts.items():
        dst_path = os.path.join(dest, rel_path)
        if skip_existing and os.path.exists(dst_path):
            continue
        if conflict_fallback == "largest":
            best = max(candidates, key=lambda c: c.get("size", 0))
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
            shutil.copy2(best["abs_path"], dst_path)
            copied.append(rel_path)
            _logger.warning(
                "Conflict fallback (largest): %s → copied from %s (%d bytes)",
                rel_path, best.get("root_name", "unknown"), best.get("size", 0),
            )
    return copied


def group_conflicts_by_parent(
    conflicts: Dict[str, List[Dict[str, Any]]],
    depth: int = 1,
) -> Dict[str, List[Dict[str, Any]]]:
    """Group conflicting files by their parent directory for semantic context.

    Args:
        conflicts: Dict from rel_path → list of candidates (from find_conflicting_and_agreed_files).
        depth: How many parent segments to group by (1 = immediate parent, 2 = grandparent/parent).

    Returns:
        Dict mapping parent_path → list of ``{path, candidates}`` dicts.
    """
    groups: Dict[str, list] = {}
    for rel_path, candidates in conflicts.items():
        parts = rel_path.replace("\\", "/").split("/")
        if len(parts) > depth:
            parent = "/".join(parts[:depth])
        else:
            parent = "."
        groups.setdefault(parent, []).append({"path": rel_path, "candidates": candidates})
    return groups
