# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.

"""
JSON I/O utilities — JsonLogger, JsonLogReader, write_json, read_json,
jsonfy, dejsonfy, iter_json_objs, and friends.

Migrated from science_python_utils.io_utils.json_io.
"""

import copy
import enum
import json
import os
import shutil
import sys
import uuid
from datetime import datetime
from itertools import chain, islice
from os import path
from pathlib import Path
from typing import (
    Any as TypingAny,
    Callable,
    Dict,
    Iterable,
    Iterator,
    List,
    Mapping,
    Optional,
    Sequence,
    Type,
    Union,
)

from rankevolve.src.utils.common_objects.partial import Partial
from rankevolve.src.utils.common_utils.function_helper import get_relevant_named_args
from rankevolve.src.utils.common_utils.iter_helper import iter__, tqdm_wrap
from rankevolve.src.utils.common_utils.map_helper import (
    delete_at_path,
    dict__,
    get_at_path,
    has_path,
    obj_walk_through,
    set_at_path,
)
from rankevolve.src.utils.io_utils.text_io import read_all_text

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_ENCODING = "utf-8"
DEFAULT_JSON_FILE_PATTERN = "*.json*"

# ---------------------------------------------------------------------------
# Inlined path helpers (from science_python_utils.path_utils)
# ---------------------------------------------------------------------------


def _resolve_ext(ext, sep="."):
    """Normalize a file extension to include the leading dot.

    Returns the input unchanged if it already starts with ``'.'``,
    otherwise prepends one.  ``None`` and empty strings pass through.

    Examples:
        >>> _resolve_ext('.html')
        '.html'
        >>> _resolve_ext('html')
        '.html'
        >>> _resolve_ext(None) is None
        True
    """
    if not ext:
        return ext
    return ext if ext[0] == sep else sep + ext


# ---------------------------------------------------------------------------
# _default_space_handler (inlined from science_python_utils.io_utils.common)
# ---------------------------------------------------------------------------


def _default_space_handler(file: str, space: Optional[str]) -> str:
    """Default space handler: treats *file* as directory, *space* as filename.

    If *file* already exists as a regular file, moves it to ``file/default``
    so the path can serve as a directory.

    Args:
        file: The base path (treated as a directory/folder).
        space: The space identifier (treated as the actual filename).
               If None or empty, defaults to ``'default'``.

    Returns:
        The joined path with file as folder and space as filename.
    """
    if not space:
        space = "default"

    # Convert file to directory if it currently exists as a regular file
    if os.path.isfile(file):
        bak = file + ".bak"
        os.rename(file, bak)
        os.makedirs(file, exist_ok=True)
        os.rename(bak, os.path.join(file, "default"))

    os.makedirs(file, exist_ok=True)
    return path.join(file, space)


# ---------------------------------------------------------------------------
# _eprint_message (inlined from science_python_utils.console_utils)
# ---------------------------------------------------------------------------


def _eprint_message(label, value):
    """Print a label: value message to stderr."""
    print(f"{label}: {value}", file=sys.stderr)


# ---------------------------------------------------------------------------
# _read_text_or_file (inlined from science_python_utils.io_utils.common)
# ---------------------------------------------------------------------------


def _read_text_or_file(text_or_file, read_text_func, read_file_func):
    """Dispatch to read_text_func or read_file_func based on input type."""
    if not isinstance(text_or_file, str):
        return text_or_file
    if os.path.exists(text_or_file):
        return read_file_func(text_or_file)
    else:
        return read_text_func(text_or_file)


# ---------------------------------------------------------------------------
# _get_input_file_stream (inlined from science_python_utils.io_utils.text_io)
# ---------------------------------------------------------------------------


def _get_input_file_stream(file, encoding, top, use_tqdm, display_msg, verbose):
    """Open a file or wrap an iterable as a line stream with optional tqdm."""
    if isinstance(file, str):
        fin = open(file, encoding=encoding or DEFAULT_ENCODING)
    else:
        fin = file
        if hasattr(file, "name"):
            file = file.name
        else:
            file = "an iterator"

    desc = display_msg.format(file) if display_msg else None
    if verbose and desc and not use_tqdm:
        _eprint_message("reading", desc)

    return tqdm_wrap(
        (islice(fin, top) if top else fin),
        use_tqdm=use_tqdm,
        desc=desc,
    ), fin


# ---------------------------------------------------------------------------
# _get_files_by_pattern (simplified inline from path_listing)
# ---------------------------------------------------------------------------


def _get_files_by_pattern(dir_path, pattern, full_path=True, recursive=True, sort=False):
    """Find files matching *pattern* under *dir_path*.

    Returns absolute paths when *full_path* is True (default).
    """
    p = Path(dir_path)
    glob_pattern = f"**/{pattern}" if recursive else pattern
    results = [str(f) for f in p.glob(glob_pattern) if f.is_file()]
    if full_path:
        results = [str(Path(f).resolve()) for f in results]
    if sort:
        results = sorted(results)
    return results


# ---------------------------------------------------------------------------
# _get_sorted_files_from_all_sub_dirs (simplified inline from path_listing)
# ---------------------------------------------------------------------------


def _get_sorted_files_from_all_sub_dirs(dir_path, pattern):
    """Collect files matching *pattern* from every sub-directory, sorted."""
    all_sub_dirs = [x[0] for x in os.walk(dir_path)]
    all_files = []
    for sub_dir in all_sub_dirs:
        all_files.extend(
            _get_files_by_pattern(sub_dir, pattern, full_path=True, recursive=False)
        )
    return sorted(all_files)


# ---------------------------------------------------------------------------
# Enums (StrEnum where available, str+Enum fallback)
# ---------------------------------------------------------------------------

try:
    from enum import StrEnum

    class JsonConverter(StrEnum):
        DICT = "dict"
        DICT_NON_RECURSIVE = "dict_non_recursive"
        STR = "str"
        NONE = "none"

    class PartsReplacementMode(StrEnum):
        REMOVE = "remove"
        TRUNCATE = "truncate"
        ABSOLUTE_PATH = "absolute_path"
        RELATIVE_PATH = "relative_path"
        FILENAME_ONLY = "filename_only"
        REFERENCE = "reference"

    class SpaceExtMode(StrEnum):
        NONE = "none"
        MOVE = "move"
        ADD = "add"

except ImportError:
    from enum import Enum

    class JsonConverter(str, Enum):
        DICT = "dict"
        DICT_NON_RECURSIVE = "dict_non_recursive"
        STR = "str"
        NONE = "none"

    class PartsReplacementMode(str, Enum):
        REMOVE = "remove"
        TRUNCATE = "truncate"
        ABSOLUTE_PATH = "absolute_path"
        RELATIVE_PATH = "relative_path"
        FILENAME_ONLY = "filename_only"
        REFERENCE = "reference"

    class SpaceExtMode(str, Enum):
        NONE = "none"
        MOVE = "move"
        ADD = "add"


# ---------------------------------------------------------------------------
# Artifact decorators (canonical home: artifact.py; re-exported here for
# backward compatibility)
# ---------------------------------------------------------------------------

from rankevolve.src.utils.io_utils.artifact import (
    PartsKeyPath,
    artifact_field,
    artifact_type,
    get_key_paths_for_artifacts,
)


# ---------------------------------------------------------------------------
# JsonLogger
# ---------------------------------------------------------------------------


class JsonLogger(Partial):
    """Callable wrapper around :func:`write_json` for use as a Debuggable logger.

    Replaces ``functools.partial(write_json, file_path=..., append=True)`` with
    parameter-mapping support.  Currently maps:

        group               →  subfolder
        max_message_length  →  leaf_as_parts_if_exceeding_size

    Attributes:
        file_path: Exposed for external discovery of the log path.

    Examples:
        >>> logger = JsonLogger(file_path='logs/session.jsonl', append=True)
        >>> logger                                            # doctest: +ELLIPSIS
        JsonLogger(file_path='logs/session.jsonl', append=True)
    """

    _PARAM_MAP = {
        "group": "subfolder",
        "max_message_length": "leaf_as_parts_if_exceeding_size",
    }

    _FIRST_ARG_VALUES_TO_PARAM_MAP = {"type": "parts_subfolder"}

    def __init__(self, **kwargs):
        super().__init__(write_json, **kwargs)

    @property
    def file_path(self):
        return self._kwargs.get("file_path")

    def __repr__(self):
        params = ", ".join(f"{k}={v!r}" for k, v in self._kwargs.items())
        return f"JsonLogger({params})" if params else "JsonLogger()"


# ---------------------------------------------------------------------------
# JsonLogReader
# ---------------------------------------------------------------------------


class JsonLogReader:
    """Iterable reader for JSON log files, counterpart to :class:`JsonLogger`.

    Wraps :func:`iter_json_objs` with baked-in parameters for convenient
    repeated reading.  Defaults differ from ``iter_json_objs`` to suit
    log-reading workflows: ``resolve_parts=True``, ``use_tqdm=False``,
    ``verbose=False``.

    Each call to ``iter()`` / ``for obj in reader`` creates a fresh iterator
    over the file.

    Examples:
        >>> reader = JsonLogReader(file_path='logs/session.jsonl')
        >>> for obj in reader:
        ...     print(obj.get('type'))
    """

    def __init__(
        self,
        file_path: str,
        resolve_parts: bool = True,
        parts_suffix: str = ".parts",
        selection=None,
        result_type=dict,
        encoding: str = None,
        ignore_error: bool = False,
        top: int = None,
        verbose: bool = False,
        use_tqdm: bool = False,
        json_file_pattern: str = None,
    ):
        self._file_path = file_path
        self._kwargs = dict(
            resolve_parts=resolve_parts,
            parts_suffix=parts_suffix,
            selection=selection,
            result_type=result_type,
            encoding=encoding,
            ignore_error=ignore_error,
            top=top,
            verbose=verbose,
            use_tqdm=use_tqdm,
        )
        if json_file_pattern is not None:
            self._kwargs["json_file_pattern"] = json_file_pattern

    @property
    def file_path(self):
        """The log file path, mirroring :attr:`JsonLogger.file_path`."""
        return self._file_path

    def __iter__(self):
        return iter_json_objs(self._file_path, **self._kwargs)

    def __repr__(self):
        params = ", ".join(f"{k}={v!r}" for k, v in self._kwargs.items())
        fp = f"file_path={self._file_path!r}"
        inner = f"{fp}, {params}" if params else fp
        return f"JsonLogReader({inner})"


# ---------------------------------------------------------------------------
# Parts extraction helpers
# ---------------------------------------------------------------------------


def _normalize_extract_path_entry(entry):
    """Normalizes an extract path entry into (path_str, ext_override, name_alias, entry_subfolder).

    Accepts:
        - 'item'                                          → ('item', None, None, None)
        - ('body_html', '.html')                          → ('body_html', '.html', None, None)
        - ('body_html', '.html', 'BodyHtml')              → ('body_html', '.html', 'BodyHtml', None)
        - ('body_html', '.html', None, 'ui_source/html')  → ('body_html', '.html', None, 'ui_source/html')
        - PartsKeyPath('body_html', ext='.html')          → ('body_html', '.html', None, None)
    """
    if isinstance(entry, PartsKeyPath):
        return entry.key, entry.ext, entry.alias, entry.subfolder
    if isinstance(entry, (list, tuple)):
        path_str = str(entry[0])
        ext_override = entry[1] if len(entry) > 1 else None
        name_alias = entry[2] if len(entry) > 2 else None
        entry_subfolder = (
            str(entry[3]) if len(entry) > 3 and entry[3] is not None else None
        )
        return path_str, ext_override, name_alias, entry_subfolder
    return str(entry), None, None, None


def _detect_extension(value):
    """Auto-detect file extension based on value content."""
    if isinstance(value, str):
        stripped = value.strip()
        if stripped[:5].lower() == "<html" or stripped[:5].lower() == "<!doc":
            return ".html"
        return ".txt"
    return ".json"


def _serialize_value(value, ensure_ascii=False):
    """Serialize a value to string for writing to a parts file."""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=ensure_ascii, indent=2)


# ---------------------------------------------------------------------------
# Parts resolution (read-side)
# ---------------------------------------------------------------------------


def _resolve_parts_references(obj, parts_dir):
    """Recursively walk a dict tree and replace __parts_file__ reference markers
    with the loaded file content.

    Only works with REFERENCE replacement mode markers:
        {"__parts_file__": "filename.txt", "__value_type__": "str"|"json"}
    """
    if isinstance(obj, dict):
        if "__parts_file__" in obj and "__value_type__" in obj:
            parts_file = path.join(parts_dir, obj["__parts_file__"])
            if path.isfile(parts_file):
                with open(parts_file, "r", encoding="utf-8") as f:
                    content = f.read()
                if obj["__value_type__"] == "json":
                    return json.loads(content)
                return content
            return obj
        return {k: _resolve_parts_references(v, parts_dir) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_resolve_parts_references(item, parts_dir) for item in obj]
    return obj


def resolve_json_parts(
    obj,
    source_path: str,
    parts_suffix: str = ".parts",
):
    """Resolve ``__parts_file__`` reference markers in a JSON object by loading
    the referenced file content from the adjacent parts directory.

    This is the read-side counterpart to ``jsonfy()`` with parts extraction.

    Args:
        obj: A JSON-serializable object (typically a dict) potentially containing
            parts reference markers.
        source_path (str): Path to the source JSON file. The parts directory is located
            at ``source_path + parts_suffix``.
        parts_suffix (str): Suffix used to locate the parts directory. Default is '.parts'.

    Returns:
        The object with all parts references resolved (file contents loaded in-place).
        If the parts directory does not exist, returns obj unchanged.
    """
    if isinstance(obj, dict) and isinstance(source_path, str):
        parts_dir = source_path + parts_suffix
        if path.isdir(parts_dir):
            return _resolve_parts_references(obj, parts_dir)
    return obj


# ---------------------------------------------------------------------------
# Type-resolution helpers (read-side)
# ---------------------------------------------------------------------------


def _get_origin(tp):
    """Extract the generic origin of a type (e.g., ``List[int]`` → ``list``)."""
    try:
        from typing import get_origin
        result = get_origin(tp)
        if result is not None:
            return result
    except ImportError:
        pass
    return getattr(tp, "__origin__", None)


def _get_type_args(tp):
    """Extract generic type arguments (e.g., ``List[int]`` → ``(int,)``)."""
    try:
        from typing import get_args
        result = get_args(tp)
        if result:
            return result
    except ImportError:
        pass
    return getattr(tp, "__args__", ())


def _unwrap_optional(tp):
    """Detect ``Optional[T]`` (i.e., ``Union[T, None]``) and unwrap it.

    Returns:
        ``(True, T)`` if *tp* is ``Optional[T]``, otherwise ``(False, tp)``.
    """
    args = _get_type_args(tp)
    if _get_origin(tp) is Union and len(args) == 2 and type(None) in args:
        inner = args[0] if args[1] is type(None) else args[1]
        return (True, inner)
    return (False, tp)


def _dejsonfy_enum(value, enum_type):
    """Reconstruct an enum member from its string representation."""
    if not isinstance(value, str):
        return value
    try:
        return enum_type(value)
    except (ValueError, KeyError):
        pass
    try:
        return enum_type[value]
    except (KeyError, ValueError):
        pass
    if "." in value:
        try:
            return enum_type[value.rsplit(".", 1)[-1]]
        except (KeyError, ValueError):
            pass
    for member in enum_type:
        if str(member) == value:
            return member
    return value


def _dejsonfy_sequence(data, element_type, container, _type_map=None, _path="", _allowed_modules=None):
    """Reconstruct a sequence (list, tuple, set) with typed elements."""
    if not isinstance(data, (list, tuple)):
        return data
    if element_type is not None:
        results = [
            dejsonfy(
                item, target_type=element_type, _type_map=_type_map,
                _path=(_path + ".*") if _path else "*", _allowed_modules=_allowed_modules,
            )
            for item in data
        ]
    else:
        results = list(data)
    return container(results)


def _dejsonfy_positional_tuple(data, type_args, _type_map=None, _path="", _allowed_modules=None):
    """Reconstruct a heterogeneous Tuple[A, B, C] with positional types."""
    if not isinstance(data, (list, tuple)):
        return data
    n = min(len(data), len(type_args))
    results = [
        dejsonfy(
            data[i], target_type=type_args[i], _type_map=_type_map,
            _path=_path, _allowed_modules=_allowed_modules,
        )
        for i in range(n)
    ]
    return tuple(results)


def _dejsonfy_mapping(data, key_type, value_type, target_type, _type_map=None, _path="", _allowed_modules=None):
    """Reconstruct a dict, including non-string-key reversal from list-of-pairs."""
    origin = _get_origin(target_type)
    if isinstance(data, list) and (origin is dict or target_type is dict):
        if data and all(isinstance(item, dict) and "key" in item and "value" in item for item in data):
            result = {}
            for item in data:
                k = dejsonfy(
                    item["key"], target_type=key_type, _type_map=_type_map,
                    _path=_path, _allowed_modules=_allowed_modules,
                ) if key_type else item["key"]
                v = dejsonfy(
                    item["value"], target_type=value_type, _type_map=_type_map,
                    _path=(_path + ".*") if _path else "*", _allowed_modules=_allowed_modules,
                ) if value_type else item["value"]
                result[k] = v
            return result
    if not isinstance(data, dict):
        return data
    need_key_reconstruction = (
        key_type is not None and key_type is not str
        and isinstance(key_type, type) and key_type not in (int, float, bool, type(None))
    )
    need_value_reconstruction = (
        value_type is not None
        and value_type not in (str, int, float, bool, type(None))
    )
    if need_key_reconstruction or need_value_reconstruction:
        result = {}
        for k, v in data.items():
            new_k = dejsonfy(
                k, target_type=key_type, _type_map=_type_map,
                _path=_path, _allowed_modules=_allowed_modules,
            ) if need_key_reconstruction else k
            new_v = dejsonfy(
                v, target_type=value_type, _type_map=_type_map,
                _path=(_path + "." + k) if _path else k, _allowed_modules=_allowed_modules,
            ) if need_value_reconstruction else v
            result[new_k] = new_v
        return result
    return dict(data)


def _dejsonfy_structured(data, target_type, target=None, _type_map=None, _path="", _allowed_modules=None):
    """Reconstruct an attrs class or dataclass from a dict."""
    import attr
    import dataclasses

    if not isinstance(data, dict):
        return data

    if attr.has(target_type):
        field_names = [f.name for f in attr.fields(target_type)]
    elif dataclasses.is_dataclass(target_type):
        field_names = [f.name for f in dataclasses.fields(target_type)]
    else:
        return data

    try:
        import typing
        hints = typing.get_type_hints(target_type)
    except Exception:
        hints = getattr(target_type, "__annotations__", {})

    if attr.has(target_type):
        for f in attr.fields(target_type):
            if f.type is not None and f.name not in hints:
                hints[f.name] = f.type

    kwargs = {}
    for name in field_names:
        if name not in data:
            continue
        field_type = hints.get(name)
        child_path = (_path + "." + name) if _path else name
        value = dejsonfy(
            data[name], target_type=field_type, _type_map=_type_map,
            _path=child_path, _allowed_modules=_allowed_modules,
        )
        if target is not None:
            setattr(target, name, value)
        else:
            kwargs[name] = value

    if target is not None:
        return target
    return target_type(**kwargs)


def _dejsonfy_namedtuple(data, target_type, _type_map=None, _path="", _allowed_modules=None):
    """Reconstruct a namedtuple from a dict."""
    if not isinstance(data, dict):
        return data
    field_names = target_type._fields
    hints = getattr(target_type, "__annotations__", {})
    filtered = {}
    for name in field_names:
        if name not in data:
            continue
        field_type = hints.get(name)
        child_path = (_path + "." + name) if _path else name
        filtered[name] = dejsonfy(
            data[name], target_type=field_type, _type_map=_type_map,
            _path=child_path, _allowed_modules=_allowed_modules,
        )
    return target_type(**filtered)


def _dejsonfy_plain_object(data, target_type, target=None, _type_map=None, _path="", _allowed_modules=None):
    """Reconstruct a plain class from a dict using __init__ kwargs."""
    if not isinstance(data, dict):
        return data
    if target is not None:
        for k, v in data.items():
            setattr(target, k, v)
        return target
    relevant = get_relevant_named_args(target_type.__init__, **data)
    return target_type(**relevant)


def _dejsonfy_slots(data, target_type, target=None, _type_map=None, _path="", _allowed_modules=None):
    """Reconstruct a __slots__-based object."""
    if not isinstance(data, dict):
        return data
    all_slots = []
    for cls in target_type.__mro__:
        if "__slots__" in cls.__dict__:
            all_slots.extend(cls.__dict__["__slots__"])
    try:
        import typing
        hints = typing.get_type_hints(target_type)
    except Exception:
        hints = getattr(target_type, "__annotations__", {})

    if target is None:
        obj = target_type.__new__(target_type)
    else:
        obj = target

    for slot in all_slots:
        if slot not in data:
            continue
        slot_type = hints.get(slot)
        child_path = (_path + "." + slot) if _path else slot
        value = dejsonfy(
            data[slot], target_type=slot_type, _type_map=_type_map,
            _path=child_path, _allowed_modules=_allowed_modules,
        )
        setattr(obj, slot, value)
    return obj


# ---------------------------------------------------------------------------
# Type metadata helpers
# ---------------------------------------------------------------------------


def _is_typed_object(obj):
    """Check if obj is a non-primitive typed object."""
    import attr
    import dataclasses
    if obj is None or isinstance(obj, (int, float, str, bool, bytes)):
        return False
    if isinstance(obj, enum.Enum):
        return False
    if isinstance(obj, dict):
        return False
    if isinstance(obj, tuple) and hasattr(type(obj), "_fields"):
        return True
    if isinstance(obj, (list, tuple, set)):
        return False
    if attr.has(type(obj)):
        return True
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return True
    if hasattr(obj, "__slots__") or hasattr(obj, "__dict__"):
        return True
    return False


def _inject_type_metadata(original_obj, converted):
    """Embed __type__/__module__ metadata into converted dicts from typed objects."""
    import attr
    import dataclasses

    if _is_typed_object(original_obj) and isinstance(converted, dict):
        converted["__type__"] = type(original_obj).__qualname__
        converted["__module__"] = type(original_obj).__module__

        obj_type = type(original_obj)
        field_names = []
        if attr.has(obj_type):
            field_names = [f.name for f in attr.fields(obj_type)]
        elif dataclasses.is_dataclass(obj_type):
            field_names = [f.name for f in dataclasses.fields(obj_type)]
        elif isinstance(original_obj, tuple) and hasattr(obj_type, "_fields"):
            field_names = list(obj_type._fields)
        elif hasattr(obj_type, "__slots__"):
            field_names = []
            for cls in obj_type.__mro__:
                if "__slots__" in cls.__dict__:
                    field_names.extend(cls.__dict__["__slots__"])
        elif hasattr(original_obj, "__dict__"):
            field_names = list(vars(original_obj).keys())

        for name in field_names:
            if name in converted:
                orig_val = getattr(original_obj, name, None)
                _inject_type_metadata(orig_val, converted[name])

    elif isinstance(original_obj, (list, tuple, set)) and isinstance(converted, list):
        orig_list = list(original_obj)
        for i in range(min(len(orig_list), len(converted))):
            _inject_type_metadata(orig_list[i], converted[i])

    elif isinstance(original_obj, dict) and isinstance(converted, list):
        if converted and all(isinstance(item, dict) and "key" in item and "value" in item for item in converted):
            orig_values = list(original_obj.values())
            for i, item in enumerate(converted):
                if i < len(orig_values):
                    _inject_type_metadata(orig_values[i], item.get("value"))

    elif isinstance(original_obj, dict) and isinstance(converted, dict):
        for k, v in original_obj.items():
            str_k = str(k)
            if str_k in converted:
                _inject_type_metadata(v, converted[str_k])


def _collect_type_metadata(original_obj, converted, path_str=""):
    """Collect path-based type map from parallel walk of original and converted objects."""
    import attr
    import dataclasses

    result = {}

    if _is_typed_object(original_obj) and isinstance(converted, dict):
        result[path_str] = {
            "__type__": type(original_obj).__qualname__,
            "__module__": type(original_obj).__module__,
        }

        obj_type = type(original_obj)
        field_names = []
        if attr.has(obj_type):
            field_names = [f.name for f in attr.fields(obj_type)]
        elif dataclasses.is_dataclass(obj_type):
            field_names = [f.name for f in dataclasses.fields(obj_type)]
        elif isinstance(original_obj, tuple) and hasattr(obj_type, "_fields"):
            field_names = list(obj_type._fields)
        elif hasattr(obj_type, "__slots__"):
            field_names = []
            for cls in obj_type.__mro__:
                if "__slots__" in cls.__dict__:
                    field_names.extend(cls.__dict__["__slots__"])
        elif hasattr(original_obj, "__dict__"):
            field_names = list(vars(original_obj).keys())

        for name in field_names:
            if name in converted:
                child_path = (path_str + "." + name) if path_str else name
                orig_val = getattr(original_obj, name, None)
                result.update(_collect_type_metadata(orig_val, converted[name], child_path))

    elif isinstance(original_obj, (list, tuple, set)) and isinstance(converted, list):
        orig_list = list(original_obj)
        wildcard_path = (path_str + ".*") if path_str else "*"
        for i in range(min(len(orig_list), len(converted))):
            result.update(_collect_type_metadata(orig_list[i], converted[i], wildcard_path))

    elif isinstance(original_obj, dict) and isinstance(converted, dict):
        for k, v in original_obj.items():
            str_k = str(k)
            if str_k in converted:
                child_path = (path_str + "." + str_k) if path_str else str_k
                result.update(_collect_type_metadata(v, converted[str_k], child_path))

    return result


def _collect_type_driven_parts(original_obj, converted, type_map, path_str=""):
    """Walk original object tree and collect key paths matching types in type_map."""
    import attr
    import dataclasses

    results = []

    if path_str:
        for target_type, config in type_map.items():
            if isinstance(original_obj, target_type):
                entry = PartsKeyPath(
                    key=path_str,
                    ext=config.get("ext") if isinstance(config, dict) else getattr(config, "ext", None),
                    alias=config.get("alias") if isinstance(config, dict) else getattr(config, "alias", None),
                    subfolder=config.get("subfolder") if isinstance(config, dict) else getattr(config, "subfolder", None),
                )
                results.append(entry)
                return results

    if _is_typed_object(original_obj) and isinstance(converted, dict):
        obj_type = type(original_obj)
        field_names = []
        if attr.has(obj_type):
            field_names = [f.name for f in attr.fields(obj_type)]
        elif dataclasses.is_dataclass(obj_type):
            field_names = [f.name for f in dataclasses.fields(obj_type)]
        elif isinstance(original_obj, tuple) and hasattr(obj_type, "_fields"):
            field_names = list(obj_type._fields)
        elif hasattr(obj_type, "__slots__"):
            field_names = []
            for cls in obj_type.__mro__:
                if "__slots__" in cls.__dict__:
                    field_names.extend(cls.__dict__["__slots__"])
        elif hasattr(original_obj, "__dict__"):
            field_names = list(vars(original_obj).keys())

        for name in field_names:
            if name not in converted:
                continue
            orig_val = getattr(original_obj, name, None)
            if orig_val is None:
                continue
            child_path = (path_str + "." + name) if path_str else name
            results.extend(_collect_type_driven_parts(orig_val, converted[name], type_map, child_path))

    elif isinstance(original_obj, (list, tuple, set)) and isinstance(converted, list):
        orig_list = list(original_obj)
        for i in range(min(len(orig_list), len(converted))):
            child_path = (path_str + "." + str(i)) if path_str else str(i)
            results.extend(_collect_type_driven_parts(orig_list[i], converted[i], type_map, child_path))

    elif isinstance(original_obj, dict) and isinstance(converted, dict):
        for k in original_obj:
            str_k = str(k)
            if str_k in converted:
                child_path = (path_str + "." + str_k) if path_str else str_k
                results.extend(_collect_type_driven_parts(original_obj[k], converted[str_k], type_map, child_path))

    return results


def _write_type_file(type_map, data_file_path, type_file_path=None):
    """Write type map to a .types.json companion file."""
    if type_file_path is None:
        type_file_path = data_file_path + ".types.json"
    os.makedirs(os.path.dirname(type_file_path) or ".", exist_ok=True)
    with open(type_file_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(type_map, indent=2))
    return type_file_path


def _read_type_file(type_file):
    """Read and parse a .types.json file. Returns empty dict on failure."""
    try:
        with open(type_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError, TypeError):
        return {}


def _import_type(qualname, module_name, allowed_modules=None):
    """Securely resolve a class from inline type metadata."""
    import importlib

    mod = None
    if module_name in sys.modules:
        mod = sys.modules[module_name]
    elif allowed_modules and module_name in allowed_modules:
        try:
            mod = importlib.import_module(module_name)
        except ImportError:
            return None
    else:
        return None

    try:
        result = mod
        for part in qualname.split("."):
            result = getattr(result, part)
        return result
    except AttributeError:
        return None


def _is_inline_metadata(data, allowed_modules=None):
    """Detect inline type metadata in a dict. Returns resolved type or None."""
    if not isinstance(data, dict):
        return None
    if "__type__" not in data or "__module__" not in data:
        return None

    resolved = _import_type(data["__type__"], data["__module__"], allowed_modules)
    if resolved is None:
        return None

    import attr
    import dataclasses

    remaining_keys = set(data.keys()) - {"__type__", "__module__"}
    field_names = set()
    try:
        if attr.has(resolved):
            field_names = {f.name for f in attr.fields(resolved)}
        elif dataclasses.is_dataclass(resolved):
            field_names = {f.name for f in dataclasses.fields(resolved)}
        elif hasattr(resolved, "_fields"):
            field_names = set(resolved._fields)
        elif hasattr(resolved, "__slots__"):
            for cls in resolved.__mro__:
                if "__slots__" in cls.__dict__:
                    field_names.update(cls.__dict__["__slots__"])
        elif hasattr(resolved, "__init__"):
            import inspect
            try:
                sig = inspect.signature(resolved.__init__)
                field_names = {p for p in sig.parameters if p != "self"}
            except (ValueError, TypeError):
                pass
    except Exception:
        pass

    if field_names and not remaining_keys.intersection(field_names):
        return None

    return resolved


# ---------------------------------------------------------------------------
# dejsonfy
# ---------------------------------------------------------------------------


def dejsonfy(
    data,
    target_type=None,
    target=None,
    type_file=None,
    _allowed_modules=None,
    _type_map=None,
    _path="",
):
    """Reconstruct a typed Python object from a JSON-serializable value.

    Args:
        data: A JSON-serializable value (dict, list, str, int, float, bool, None)
              typically produced by jsonfy() or dict__().
        target_type: The Python type to reconstruct into.
        target: An existing object to restore attributes onto.
        type_file: Path to a .types.json companion file for type resolution.
        _allowed_modules: Set of module names allowed for dynamic import.
        _type_map: Internal — pre-loaded type map from type_file.
        _path: Internal — current dotted path for type_file lookups.

    Returns:
        An instance of target_type with fields populated from data,
        the mutated target object (if target was provided),
        or data unchanged for basic types / when no type can be resolved.
    """
    import attr
    import dataclasses

    if _path == "" and target_type is not None and target is not None:
        raise ValueError(
            "target_type and target are mutually exclusive; provide one or the other"
        )

    if target is not None:
        target_type = type(target)

    if data is None:
        return None

    if isinstance(data, dict) and "__type__" in data and "__module__" in data:
        resolved = _is_inline_metadata(data, _allowed_modules)
        if resolved is not None:
            data = {k: v for k, v in data.items() if k not in ("__type__", "__module__")}
            if target_type is None:
                target_type = resolved

    if type_file is not None and _type_map is None:
        _type_map = _read_type_file(type_file)

    if target_type is None and _type_map:
        type_info = _type_map.get(_path)
        if type_info is None:
            parts = _path.split(".")
            for i in range(len(parts) - 1, -1, -1):
                trial = ".".join(parts[:i] + ["*"] * (len(parts) - i))
                type_info = _type_map.get(trial)
                if type_info is not None:
                    break
        if type_info is not None:
            resolved = _import_type(
                type_info.get("__type__", ""),
                type_info.get("__module__", ""),
                _allowed_modules,
            )
            if resolved is not None:
                target_type = resolved

    if target_type is None or target_type is TypingAny:
        return data

    if isinstance(data, (int, float, str, bool)) and not isinstance(data, enum.Enum):
        if not (isinstance(target_type, type) and issubclass(target_type, enum.Enum)):
            if target_type is not bytes:
                return data

    if isinstance(target_type, type) and target_type is bytes:
        if isinstance(data, str):
            return data.encode()
        return data

    is_opt, inner_type = _unwrap_optional(target_type)
    if is_opt:
        return dejsonfy(
            data, target_type=inner_type, _type_map=_type_map,
            _path=_path, _allowed_modules=_allowed_modules,
        )

    origin = _get_origin(target_type)
    args = _get_type_args(target_type)
    if origin is Union:
        for union_type in args:
            if union_type is type(None):
                continue
            try:
                result = dejsonfy(
                    data, target_type=union_type, _type_map=_type_map,
                    _path=_path, _allowed_modules=_allowed_modules,
                )
                return result
            except Exception:
                continue
        return data

    if isinstance(target_type, type) and issubclass(target_type, enum.Enum):
        return _dejsonfy_enum(data, target_type)

    if origin is list or (isinstance(target_type, type) and target_type is list):
        element_type = args[0] if args else None
        return _dejsonfy_sequence(
            data, element_type, list, _type_map=_type_map,
            _path=_path, _allowed_modules=_allowed_modules,
        )

    if origin is tuple or (isinstance(target_type, type) and target_type is tuple):
        if args:
            if len(args) == 2 and args[1] is Ellipsis:
                return _dejsonfy_sequence(
                    data, args[0], tuple, _type_map=_type_map,
                    _path=_path, _allowed_modules=_allowed_modules,
                )
            elif Ellipsis not in args:
                return _dejsonfy_positional_tuple(
                    data, args, _type_map=_type_map,
                    _path=_path, _allowed_modules=_allowed_modules,
                )
        if isinstance(data, (list, tuple)):
            return tuple(data)
        return data

    if origin is set or (isinstance(target_type, type) and target_type is set):
        element_type = args[0] if args else None
        return _dejsonfy_sequence(
            data, element_type, set, _type_map=_type_map,
            _path=_path, _allowed_modules=_allowed_modules,
        )

    if origin is dict or (isinstance(target_type, type) and target_type is dict):
        key_type = args[0] if len(args) >= 1 else None
        value_type = args[1] if len(args) >= 2 else None
        return _dejsonfy_mapping(
            data, key_type, value_type, target_type,
            _type_map=_type_map, _path=_path, _allowed_modules=_allowed_modules,
        )

    try:
        if attr.has(target_type):
            return _dejsonfy_structured(
                data, target_type, target=target,
                _type_map=_type_map, _path=_path, _allowed_modules=_allowed_modules,
            )
    except Exception:
        pass

    try:
        if dataclasses.is_dataclass(target_type) and isinstance(target_type, type):
            return _dejsonfy_structured(
                data, target_type, target=target,
                _type_map=_type_map, _path=_path, _allowed_modules=_allowed_modules,
            )
    except Exception:
        pass

    if isinstance(target_type, type) and issubclass(target_type, tuple) and hasattr(target_type, "_fields"):
        return _dejsonfy_namedtuple(
            data, target_type, _type_map=_type_map,
            _path=_path, _allowed_modules=_allowed_modules,
        )

    if isinstance(target_type, type) and hasattr(target_type, "__slots__"):
        return _dejsonfy_slots(
            data, target_type, target=target,
            _type_map=_type_map, _path=_path, _allowed_modules=_allowed_modules,
        )

    if isinstance(target_type, type) and isinstance(data, dict):
        return _dejsonfy_plain_object(
            data, target_type, target=target,
            _type_map=_type_map, _path=_path, _allowed_modules=_allowed_modules,
        )

    return data


# ---------------------------------------------------------------------------
# Read-side JSON iteration
# ---------------------------------------------------------------------------


def iter_all_json_strs(json_obj_iter, process_func=None, indent=None, ensure_ascii=False, **kwargs):
    """Convert JSON objects to JSON strings via json.dumps."""
    if process_func:
        for json_obj in json_obj_iter:
            try:
                yield json.dumps(process_func(json_obj), indent=indent, ensure_ascii=ensure_ascii, **kwargs)
            except Exception as ex:
                print(json_obj)
                raise ex
    else:
        for json_obj in json_obj_iter:
            try:
                yield json.dumps(json_obj, indent=indent, ensure_ascii=ensure_ascii, **kwargs)
            except Exception as ex:
                print(json_obj)
                raise ex


def _iter_json_objs(
    json_input: Union[str, Iterable, Iterator],
    use_tqdm: bool = True,
    disp_msg: str = None,
    verbose: bool = __debug__,
    encoding: str = DEFAULT_ENCODING,
    ignore_error: bool = False,
    top: int = None,
    selection: Union[str, Iterable[str]] = None,
    result_type: Union[str, Type] = dict,
    json_file_pattern: str = DEFAULT_JSON_FILE_PATTERN,
    resolve_parts: bool = False,
    parts_suffix: str = ".parts",
) -> Iterator[Dict]:
    """Iterates over JSON objects from various input sources.

    Args:
        json_input: The JSON input source — file path, directory path,
            or an iterable/iterator of JSON strings.
        use_tqdm: Whether to display a progress bar. Default is True.
        disp_msg: A message to display with the progress bar.
        verbose: Whether to print verbose messages. Default is __debug__.
        encoding: The encoding of the input file. Default is DEFAULT_ENCODING.
        ignore_error: Whether to ignore errors during JSON parsing.
        top: Maximum number of JSON objects to read.
        selection: A subset of JSON keys to include in the output.
        result_type: The type of the result — dict, list, or tuple.
        json_file_pattern: File pattern for JSON files in a directory.
        resolve_parts: If True, resolve '__parts_file__' reference markers.
        parts_suffix: Suffix for the parts directory. Default is '.parts'.

    Yields:
        The next JSON object parsed from the input source.
    """

    def _process_json_obj(json_obj):
        if selection:
            if result_type is dict or result_type == "dict":
                json_obj = {k: json_obj[k] for k in iter__(selection)}
            elif (
                (result_type is list)
                or (result_type is tuple)
                or result_type == "list"
                or result_type == "tuple"
            ):
                json_obj = result_type(json_obj[k] for k in iter__(selection))
        elif (
            (result_type is list)
            or (result_type is tuple)
            or result_type == "list"
            or result_type == "tuple"
        ):
            json_obj = result_type(json_obj.values())
        return json_obj

    def _maybe_resolve_parts(json_obj, source_file):
        if resolve_parts:
            return resolve_json_parts(json_obj, source_file, parts_suffix=parts_suffix)
        return json_obj

    def _iter_single_input(json_input):
        if not (
            (result_type is dict)
            or (result_type is list)
            or (result_type is tuple)
            or result_type in ("dict", "list", "tuple")
        ):
            raise ValueError("'result_type' must be one of dict, list or tuple")

        line_iter, fin = _get_input_file_stream(
            file=json_input,
            encoding=encoding,
            top=top,
            use_tqdm=use_tqdm,
            display_msg=disp_msg or "read json object from {}",
            verbose=verbose,
        )
        try_parse_as_single_line = False
        _source_file = json_input if isinstance(json_input, str) else None
        for line in line_iter:
            if line:
                try:
                    try:
                        json_obj = json.loads(line)
                    except json.decoder.JSONDecodeError:
                        try_parse_as_single_line = True
                        break

                    yield _process_json_obj(_maybe_resolve_parts(json_obj, _source_file))
                except Exception as ex:
                    if ignore_error is True:
                        print(line)
                        print(ex)
                    elif ignore_error == "silent":
                        continue
                    else:
                        print(line)
                        raise ex

        if try_parse_as_single_line:
            try:
                json_obj = read_single_line_json_file(json_input)
                if isinstance(json_obj, dict):
                    yield _process_json_obj(_maybe_resolve_parts(json_obj, _source_file))
                else:
                    json_objs = json_obj
                    for json_obj in json_objs:
                        yield _process_json_obj(_maybe_resolve_parts(json_obj, _source_file))
            except Exception:
                pass

        if hasattr(fin, "close"):
            fin.close()

    if isinstance(json_input, str):
        if path.isfile(json_input):
            yield from _iter_single_input(json_input)
        else:
            for _json_input in _get_files_by_pattern(
                json_input,
                pattern=json_file_pattern,
                full_path=True,
                recursive=False,
                sort=True,
            ):
                try:
                    yield from _iter_single_input(_json_input)
                except Exception as ex:
                    if verbose:
                        _eprint_message("reading JSON file failed", _json_input)
                    raise ex
    else:
        try:
            yield from _iter_single_input(json_input)
        except Exception as ex:
            if verbose:
                _eprint_message("reading JSON file failed", json_input)
            raise ex

def read_single_line_json_file(json_input: Union[str, Iterable, Iterator]):
    """Read JSON from a single file or multiple files.

    Args:
        json_input: A path to a file, an iterable of file paths,
            or an iterator yielding lines of JSON.

    Returns:
        A JSON object or list of JSON objects read from the input file(s).
    """
    if isinstance(json_input, str):
        return json.loads(read_all_text(json_input))
    else:
        out = []
        for _input_path in json_input:
            loaded_jobj_or_jobj_list = json.loads(read_all_text(_input_path))
            if isinstance(loaded_jobj_or_jobj_list, Mapping):
                out.append(loaded_jobj_or_jobj_list)
            else:
                out.extend(loaded_jobj_or_jobj_list)
        return out


def read_json(json_text_or_file):
    """Read JSON from a file path or parse a JSON string.
    Counterpart to write_json. Auto-detects file vs string.
    """
    if not isinstance(json_text_or_file, str):
        return json_text_or_file
    if os.path.isfile(json_text_or_file):
        with open(json_text_or_file, encoding="utf-8") as f:
            return json.load(f)
    return json.loads(json_text_or_file)


def read_jsonl(jsonl_text_or_file: str):
    """Read JSONL from text or file."""
    return _read_text_or_file(
        text_or_file=jsonl_text_or_file,
        read_text_func=lambda text: [json.loads(line) for line in text.split("\n") if line],
        read_file_func=lambda fp: list(iter_json_objs(fp)),
    )


def iter_json_objs(
    json_input: Union[str, Iterable, Iterator],
    use_tqdm: bool = True,
    disp_msg: str = None,
    verbose: bool = __debug__,
    encoding: str = DEFAULT_ENCODING,
    ignore_error: bool = False,
    top: int = None,
    selection: Union[str, Iterable[str]] = None,
    result_type: Union[str, Type] = dict,
    return_input_source_and_index_for_each_json_obj: bool = False,
    json_file_pattern: str = DEFAULT_JSON_FILE_PATTERN,
    resolve_parts: bool = False,
    parts_suffix: str = ".parts",
) -> Iterator[Dict]:
    """Iterate through all JSON objects in a file, directory, or iterable.

    Args:
        json_input: Path to a JSON file, a directory containing JSON files,
            or an iterable/iterator of JSON strings.
        use_tqdm: If True, use tqdm to display reading progress.
        disp_msg: Message to display with the progress bar.
        verbose: If True, print the disp_msg regardless of use_tqdm.
        encoding: File encoding. Default is DEFAULT_ENCODING.
        ignore_error: If True, ignore errors when parsing JSON objects.
        top: Maximum number of JSON objects to read.
        selection: One or more keys to select fields from the returned JSON objects.
        result_type: The type of the result — dict, list, or tuple.
        return_input_source_and_index_for_each_json_obj: If True, return
            (json_obj, input_source, index) tuples.
        json_file_pattern: File pattern when searching directories.
        resolve_parts: If True, resolve '__parts_file__' reference markers.
        parts_suffix: Suffix for the parts directory.

    Yields:
        The next JSON object parsed from the input source. If
        return_input_source_and_index_for_each_json_obj is True, yields
        a tuple of (json_obj, input_source, index).
    """
    if isinstance(json_input, (tuple, list, set)):
        if return_input_source_and_index_for_each_json_obj:
            for _json_input in json_input:
                for jobj_index, jobj in enumerate(
                    _iter_json_objs(
                        json_input=_json_input,
                        use_tqdm=use_tqdm,
                        disp_msg=disp_msg,
                        verbose=verbose,
                        encoding=encoding,
                        ignore_error=ignore_error,
                        top=top,
                        selection=selection,
                        result_type=result_type,
                        json_file_pattern=json_file_pattern,
                        resolve_parts=resolve_parts,
                        parts_suffix=parts_suffix,
                    )
                ):
                    yield jobj, _json_input, jobj_index
        else:
            for _json_input in json_input:
                yield from _iter_json_objs(
                    json_input=_json_input,
                    use_tqdm=use_tqdm,
                    disp_msg=disp_msg,
                    verbose=verbose,
                    encoding=encoding,
                    ignore_error=ignore_error,
                    top=top,
                    selection=selection,
                    result_type=result_type,
                    json_file_pattern=json_file_pattern,
                    resolve_parts=resolve_parts,
                    parts_suffix=parts_suffix,
                )
    else:
        if return_input_source_and_index_for_each_json_obj:
            for jobj_index, jobj in enumerate(
                _iter_json_objs(
                    json_input=json_input,
                    use_tqdm=use_tqdm,
                    disp_msg=disp_msg,
                    verbose=verbose,
                    encoding=encoding,
                    ignore_error=ignore_error,
                    top=top,
                    selection=selection,
                    result_type=result_type,
                    json_file_pattern=json_file_pattern,
                    resolve_parts=resolve_parts,
                    parts_suffix=parts_suffix,
                )
            ):
                yield jobj, json_input, jobj_index
        else:
            yield from _iter_json_objs(
                json_input=json_input,
                use_tqdm=use_tqdm,
                disp_msg=disp_msg,
                verbose=verbose,
                encoding=encoding,
                ignore_error=ignore_error,
                top=top,
                selection=selection,
                result_type=result_type,
                json_file_pattern=json_file_pattern,
                resolve_parts=resolve_parts,
                parts_suffix=parts_suffix,
            )


# ---------------------------------------------------------------------------
# Subdirectory batch readers
# ---------------------------------------------------------------------------


def _iter_all_json_objs_from_all_sub_dirs(
    input_path: str,
    pattern: str = DEFAULT_JSON_FILE_PATTERN,
    use_tqdm: bool = False,
    display_msg: str = None,
    verbose: bool = __debug__,
    encoding: str = DEFAULT_ENCODING,
    ignore_error: bool = False,
    top: int = None,
    selection: Union[str, Iterable[str]] = None,
    result_type: Union[str, Type] = dict,
    return_input_source_and_index_for_each_json_obj: bool = False,
    resolve_parts: bool = False,
    parts_suffix: str = ".parts",
) -> Iterator[Dict]:
    """Iterate through all JSON objects from all subdirectories of a given directory."""
    if path.isfile(input_path):
        all_files = [input_path]
    else:
        all_files = _get_sorted_files_from_all_sub_dirs(dir_path=input_path, pattern=pattern)

    yield from iter_json_objs(
        json_input=all_files,
        use_tqdm=use_tqdm,
        disp_msg=display_msg,
        verbose=verbose,
        encoding=encoding,
        ignore_error=ignore_error,
        top=top,
        selection=selection,
        result_type=result_type,
        return_input_source_and_index_for_each_json_obj=return_input_source_and_index_for_each_json_obj,
        resolve_parts=resolve_parts,
        parts_suffix=parts_suffix,
    )


def iter_all_json_objs_from_all_sub_dirs(
    input_path_or_paths: Union[str, Iterable[str]],
    pattern: str = DEFAULT_JSON_FILE_PATTERN,
    use_tqdm: bool = False,
    display_msg: str = None,
    verbose: bool = __debug__,
    encoding: str = DEFAULT_ENCODING,
    ignore_error: bool = False,
    top: int = None,
    top_per_input_path: int = None,
    selection: Union[str, Iterable[str]] = None,
    result_type: Union[str, Type] = dict,
    return_input_source_and_index_for_each_json_obj: bool = False,
    resolve_parts: bool = False,
    parts_suffix: str = ".parts",
) -> Iterator[Dict]:
    """Iterate through all JSON objects from all subdirectories of given directories.

    Args:
        input_path_or_paths: Path to the parent directory or a list of paths.
        pattern: File pattern to match. Default is '*.json*'.
        use_tqdm: If True, use tqdm to display reading progress.
        display_msg: Message to display for this reading.
        verbose: If True, print out the display_msg.
        encoding: File encoding.
        ignore_error: If True, ignore JSON decoding errors.
        top: Total number of JSON objects to read from all input files.
        top_per_input_path: Number of JSON objects to read from each input path.
        selection: Keys to select fields from the returned json objs.
        result_type: Can be dict, list or tuple.
        return_input_source_and_index_for_each_json_obj: If True, return
            (json_obj, input_source, index) tuples.
        resolve_parts: If True, resolve '__parts_file__' reference markers.
        parts_suffix: Suffix for the parts directory.

    Returns:
        An iterator yielding JSON objects from all subdirectories.
    """
    if isinstance(input_path_or_paths, str):
        return _iter_all_json_objs_from_all_sub_dirs(
            input_path=input_path_or_paths,
            pattern=pattern,
            use_tqdm=use_tqdm,
            display_msg=display_msg,
            verbose=verbose,
            encoding=encoding,
            ignore_error=ignore_error,
            top=top,
            selection=selection,
            result_type=result_type,
            return_input_source_and_index_for_each_json_obj=return_input_source_and_index_for_each_json_obj,
            resolve_parts=resolve_parts,
            parts_suffix=parts_suffix,
        )
    else:
        _it = chain(
            *(
                _iter_all_json_objs_from_all_sub_dirs(
                    input_path=input_path,
                    pattern=pattern,
                    use_tqdm=use_tqdm,
                    display_msg=display_msg,
                    verbose=verbose,
                    encoding=encoding,
                    ignore_error=ignore_error,
                    top=top_per_input_path,
                    selection=selection,
                    result_type=result_type,
                    return_input_source_and_index_for_each_json_obj=return_input_source_and_index_for_each_json_obj,
                    resolve_parts=resolve_parts,
                    parts_suffix=parts_suffix,
                )
                for input_path in input_path_or_paths
            )
        )
        if top:
            _it = islice(_it, top)
        return _it


# ---------------------------------------------------------------------------
# jsonfy
# ---------------------------------------------------------------------------


def jsonfy(
    obj,
    recursively_ensure_json_conversion: bool = True,
    converter: Union[JsonConverter, str, Callable, None] = None,
    parts_root_path: str = None,
    parts_key_paths=None,
    parts_min_size: int = 0,
    parts_mode: Union[PartsReplacementMode, str] = "reference",
    parts_suffix: str = ".parts",
    parts_preview_len: int = 200,
    parts_preview_with_path: bool = False,
    parts_path_as_url: bool = False,
    parts_file_namer: Callable = None,
    parts_subfolder: str = None,
    parts_group_by_key: bool = False,
    parts_key_path_root: str = None,
    artifacts_as_parts=None,
    leaf_as_parts_if_exceeding_size: int = None,
    is_artifact=False,
    overwrite: bool = True,
    ensure_ascii: bool = False,
    save_type: Union[None, bool, str] = None,
    type_file_path: str = None,
    parts_type_map: Dict[Type, Union[dict, "PartsKeyPath"]] = None,
):
    """Converts an object to a JSON-serializable form, optionally extracting
    large values into separate .parts/ files.

    This function performs two logical steps:

    1. **Conversion**: Converts the object to a dict/JSON-serializable form
       using the specified ``converter`` or the default ``dict__`` conversion.
    2. **Parts extraction** (optional): If ``parts_key_paths`` is set and
       ``parts_root_path`` is provided, extracts designated values into separate
       files under a ``.parts/`` directory adjacent to the target file.

    When ``parts_root_path`` is None, only conversion is performed — no files
    are written and parts extraction is skipped.

    Args:
        obj: The object to convert. Can be any Python object.
        recursively_ensure_json_conversion: If True, the object will be
            recursively converted via ``dict__``. Defaults to True.
        converter: Controls how the object is converted before serialization.
        parts_root_path: The resolved file path used to determine the
            ``.parts/`` directory location. When None, parts extraction
            is skipped. Defaults to None.
        parts_key_paths: Key paths to extract as separate files.
        parts_min_size: Minimum serialized size to trigger extraction. Defaults to 0.
        parts_mode: What replaces extracted values in the main dict. Defaults to 'reference'.
        parts_suffix: Suffix for the parts directory. Defaults to '.parts'.
        parts_preview_len: Max chars for inline preview in TRUNCATE mode. Defaults to 200.
        parts_preview_with_path: Include truncated preview after path. Defaults to False.
        parts_path_as_url: Prefix with file:///. Defaults to False.
        parts_file_namer: Custom namer for parts files.
        parts_subfolder: Subdirectory within the parts directory.
        parts_group_by_key: Organize parts into subdirs by key. Defaults to False.
        parts_key_path_root: Prefix for all key paths during extraction.
        artifacts_as_parts: Merge @artifact_field-decorated fields into parts_key_paths.
        leaf_as_parts_if_exceeding_size: Auto-extract leaf strings exceeding this size.
        is_artifact: Convenience shorthand for ``parts_key_paths='*'``.
        overwrite: If True, clears the parts directory before writing. Defaults to True.
        ensure_ascii: Passed to _serialize_value for parts content. Defaults to False.
        save_type: Controls type metadata embedding.
            None/False = no metadata, True/"inline" = embed __type__/__module__,
            "separate" = write companion .types.json file.
        type_file_path: Custom path for the .types.json file.
        parts_type_map: Dict mapping Python types to extraction config.

    Returns:
        The converted (and possibly parts-extracted) object, or None if obj was None.
    """
    if obj is None:
        return

    # Convenience shorthand: is_artifact → extract all fields
    if is_artifact and parts_key_paths is None:
        if is_artifact is True:
            parts_key_paths = "*"
        else:
            _check_val = (
                obj.get(parts_key_path_root)
                if parts_key_path_root and isinstance(obj, dict)
                else obj
            )
            if isinstance(_check_val, is_artifact):
                parts_key_paths = "*"

    # Capture original type/object before dict conversion
    _has_artifact_types = (
        hasattr(type(obj), "__artifact_types__")
        and type(obj).__artifact_types__
    )
    _original_type = type(obj) if (artifacts_as_parts or _has_artifact_types) else None
    _original_obj_for_type = obj if (save_type or parts_type_map or _has_artifact_types or artifacts_as_parts) else None

    if converter is not None:
        if callable(converter) and not isinstance(converter, (JsonConverter, str)):
            obj = converter(obj)
        elif converter in (JsonConverter.DICT, "dict"):
            if not isinstance(obj, Mapping):
                obj = dict__(obj, recursive=True)
        elif converter in (JsonConverter.DICT_NON_RECURSIVE, "dict_non_recursive"):
            if not isinstance(obj, Mapping):
                obj = dict__(obj, recursive=False)
        elif converter in (JsonConverter.STR, "str"):
            obj = str(obj)
        elif converter in (JsonConverter.NONE, "none"):
            pass
        else:
            raise ValueError(f"Unknown converter: {converter!r}")
    else:
        if not isinstance(obj, Mapping):
            obj = dict__(obj, recursive=recursively_ensure_json_conversion)

    # Merge artifact-decorated fields into parts_key_paths
    if artifacts_as_parts:
        groups = None if artifacts_as_parts is True else artifacts_as_parts

        _artifact_type = _original_type
        if parts_key_path_root and _original_obj_for_type is not None:
            _inner_orig = getattr(_original_obj_for_type, parts_key_path_root, None) if hasattr(_original_obj_for_type, parts_key_path_root) else None
            if _inner_orig is None and has_path(_original_obj_for_type, parts_key_path_root):
                _inner_orig = get_at_path(_original_obj_for_type, parts_key_path_root)
            if _inner_orig is not None:
                _artifact_type = type(_inner_orig)

        artifact_entries = get_key_paths_for_artifacts(_artifact_type, groups=groups)

        if artifact_entries:
            if parts_key_paths:
                explicit_keys = {
                    _normalize_extract_path_entry(e)[0] for e in parts_key_paths
                }
                artifact_entries = [
                    e for e in artifact_entries if e.key not in explicit_keys
                ]
            parts_key_paths = artifact_entries + (
                list(parts_key_paths) if parts_key_paths else []
            )

    # Build parts_type_map from @artifact_type decorators
    if _has_artifact_types and _original_obj_for_type is not None:
        _artifact_type_map = {}
        _artifact_type_cls = _original_type
        if parts_key_path_root:
            _inner_obj = getattr(_original_obj_for_type, parts_key_path_root, None) if hasattr(_original_obj_for_type, parts_key_path_root) else None
            if _inner_obj is not None and hasattr(type(_inner_obj), "__artifact_types__"):
                _artifact_type_cls = type(_inner_obj)
        for entry in getattr(_artifact_type_cls, "__artifact_types__", []):
            _artifact_type_map[entry["target_type"]] = {
                "ext": entry.get("ext"),
                "alias": entry.get("alias"),
                "subfolder": entry.get("subfolder"),
            }
        if _artifact_type_map:
            if parts_type_map:
                merged = dict(_artifact_type_map)
                merged.update(parts_type_map)
                parts_type_map = merged
            else:
                parts_type_map = _artifact_type_map

    # Inject or collect type metadata
    if save_type and _original_obj_for_type is not None:
        if save_type is True or save_type == "inline":
            _inject_type_metadata(_original_obj_for_type, obj)
        elif save_type == "separate" and (parts_root_path or type_file_path):
            _type_map = _collect_type_metadata(_original_obj_for_type, obj)
            _write_type_file(_type_map, parts_root_path, type_file_path)

    # Collect type-driven parts entries
    if parts_type_map and _original_obj_for_type is not None and isinstance(obj, dict):
        _walk_orig = _original_obj_for_type
        _walk_conv = obj
        if parts_key_path_root:
            _walk_orig = getattr(_original_obj_for_type, parts_key_path_root, None) if hasattr(_original_obj_for_type, parts_key_path_root) else None
            if _walk_orig is None:
                try:
                    _walk_orig = get_at_path(_original_obj_for_type, parts_key_path_root)
                except (KeyError, AttributeError, TypeError, IndexError):
                    _walk_orig = None
            _walk_conv = get_at_path(obj, parts_key_path_root) if has_path(obj, parts_key_path_root) else None
        if _walk_orig is not None and _walk_conv is not None:
            type_driven_entries = _collect_type_driven_parts(
                _walk_orig, _walk_conv, parts_type_map
            )
        else:
            type_driven_entries = []
        if type_driven_entries:
            if parts_key_paths:
                explicit_keys = {
                    _normalize_extract_path_entry(e)[0] for e in parts_key_paths
                }
                type_driven_entries = [
                    e for e in type_driven_entries if e.key not in explicit_keys
                ]
            parts_key_paths = (list(parts_key_paths) if parts_key_paths else []) + type_driven_entries

    # Ensure nested objects at parts_key_path_root are dict-converted
    if parts_key_path_root and parts_key_paths and isinstance(obj, dict):
        _inner = obj.get(parts_key_path_root)
        if _inner is not None and not isinstance(
            _inner, (dict, list, str, int, float, bool, type(None), bytes)
        ):
            obj = dict(obj)  # shallow copy to avoid mutating caller's dict
            obj[parts_key_path_root] = dict__(_inner, recursive=True)

    # Extract large values to .parts/ files (only when parts_root_path is set)
    _deepcopied = False
    if (
        parts_key_paths is not None
        and parts_root_path is not None
        and isinstance(obj, dict)
    ):
        # Expand wildcard
        if parts_key_paths == "*":
            if parts_key_path_root:
                _root_val = obj.get(parts_key_path_root)
                if isinstance(_root_val, dict):
                    parts_key_paths = list(_root_val.keys())
                elif _root_val is not None:
                    parts_key_paths = [parts_key_path_root]
                    parts_key_path_root = None
                else:
                    parts_key_paths = []
            else:
                parts_key_paths = list(obj.keys())

        obj = copy.deepcopy(obj)
        _deepcopied = True

        mode = PartsReplacementMode(parts_mode)
        base_parts_dir = parts_root_path + parts_suffix
        parts_dir = (
            os.path.join(base_parts_dir, parts_subfolder)
            if parts_subfolder
            else base_parts_dir
        )

        # Clear parts directory if overwriting
        if overwrite and os.path.isdir(parts_dir):
            shutil.rmtree(parts_dir)

        for entry in parts_key_paths:
            path_str, ext_override, name_alias, entry_subfolder = (
                _normalize_extract_path_entry(entry)
            )
            original_path_str = path_str

            # Apply root prefix for data access
            if parts_key_path_root:
                path_str = f"{parts_key_path_root}.{path_str}"

            if not has_path(obj, path_str):
                continue
            value = get_at_path(obj, path_str)
            if value is None:
                continue

            serialized = _serialize_value(value, ensure_ascii=ensure_ascii)
            if len(serialized) < parts_min_size:
                continue

            # Determine extension
            ext = (
                _resolve_ext(ext_override) if ext_override else _detect_extension(value)
            )

            # Build filename with timestamp+uuid for uniqueness
            file_stem = (
                name_alias if name_alias else original_path_str.replace(".", "__")
            )
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            uid = uuid.uuid4().hex[:8]
            name_hint = parts_file_namer(obj) if parts_file_namer is not None else None
            segments = [ts]
            if name_hint:
                segments.append(name_hint)
            if file_stem and file_stem != "item":
                segments.append(file_stem)
            segments.append(uid)
            filename = "_".join(segments) + ext

            # Write to parts file
            entry_dir = parts_dir
            if entry_subfolder:
                entry_dir = path.join(entry_dir, entry_subfolder)
            if parts_group_by_key:
                entry_dir = path.join(entry_dir, file_stem)
            os.makedirs(entry_dir, exist_ok=True)
            parts_file_path = path.join(entry_dir, filename)
            with open(parts_file_path, "w", encoding="utf-8") as pf:
                pf.write(serialized)

            # Path from parts_dir to the file
            rel_segments = []
            if entry_subfolder:
                rel_segments.append(entry_subfolder)
            if parts_group_by_key:
                rel_segments.append(file_stem)
            rel_segments.append(filename)
            rel_to_parts_dir = path.join(*rel_segments)

            # Replace value in obj based on mode
            if mode == PartsReplacementMode.REMOVE:
                delete_at_path(obj, path_str)
            elif mode == PartsReplacementMode.TRUNCATE:
                parts_ref = (
                    path.join(parts_subfolder, rel_to_parts_dir)
                    if parts_subfolder
                    else rel_to_parts_dir
                )
                truncated = (
                    serialized[:parts_preview_len] + f"...[truncated, see {parts_ref}]"
                )
                set_at_path(obj, path_str, truncated)
            elif mode in (
                PartsReplacementMode.ABSOLUTE_PATH,
                PartsReplacementMode.RELATIVE_PATH,
                PartsReplacementMode.FILENAME_ONLY,
            ):
                if mode == PartsReplacementMode.ABSOLUTE_PATH:
                    ref_path = path.abspath(parts_file_path)
                elif mode == PartsReplacementMode.RELATIVE_PATH:
                    base_parts_name = path.basename(base_parts_dir)
                    if parts_subfolder:
                        ref_path = path.join(
                            base_parts_name, parts_subfolder, rel_to_parts_dir
                        )
                    else:
                        ref_path = path.join(base_parts_name, rel_to_parts_dir)
                else:
                    ref_path = filename

                if parts_path_as_url:
                    ref_path = "file:///" + ref_path

                if parts_preview_with_path:
                    ref_path = (
                        ref_path + "\n---\n" + serialized[:parts_preview_len] + "..."
                    )

                set_at_path(obj, path_str, ref_path)
            else:
                # REFERENCE mode (default)
                value_type = "str" if isinstance(value, str) else "json"
                set_at_path(
                    obj,
                    path_str,
                    {
                        "__parts_file__": path.join(parts_subfolder, rel_to_parts_dir)
                        if parts_subfolder
                        else rel_to_parts_dir,
                        "__value_type__": value_type,
                    },
                )

    # Auto-extract oversized leaf string values
    if (
        leaf_as_parts_if_exceeding_size is not None
        and parts_root_path is not None
        and isinstance(obj, dict)
    ):
        if not _deepcopied:
            obj = copy.deepcopy(obj)

        mode = PartsReplacementMode(parts_mode)
        base_parts_dir = parts_root_path + parts_suffix
        _leaf_parts_dir = (
            os.path.join(base_parts_dir, parts_subfolder)
            if parts_subfolder
            else base_parts_dir
        )

        for key_path, value in obj_walk_through(obj):
            if not isinstance(value, str):
                continue
            if len(value) < leaf_as_parts_if_exceeding_size:
                continue

            path_str = ".".join(key_path)
            file_stem = path_str.replace(".", "__")

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            uid = uuid.uuid4().hex[:8]
            ext = _detect_extension(value)
            name_hint = parts_file_namer(obj) if parts_file_namer is not None else None
            segments = [ts]
            if name_hint:
                segments.append(name_hint)
            if file_stem and file_stem != "item":
                segments.append(file_stem)
            segments.append(uid)
            filename = "_".join(segments) + ext

            os.makedirs(_leaf_parts_dir, exist_ok=True)
            parts_file_path = path.join(_leaf_parts_dir, filename)
            with open(parts_file_path, "w", encoding="utf-8") as pf:
                pf.write(value)

            rel_to_parts_dir = filename

            if mode == PartsReplacementMode.REMOVE:
                delete_at_path(obj, path_str)
            elif mode == PartsReplacementMode.TRUNCATE:
                parts_ref = (
                    path.join(parts_subfolder, rel_to_parts_dir)
                    if parts_subfolder
                    else rel_to_parts_dir
                )
                truncated = (
                    value[:parts_preview_len] + f"...[truncated, see {parts_ref}]"
                )
                set_at_path(obj, path_str, truncated)
            elif mode in (
                PartsReplacementMode.ABSOLUTE_PATH,
                PartsReplacementMode.RELATIVE_PATH,
                PartsReplacementMode.FILENAME_ONLY,
            ):
                if mode == PartsReplacementMode.ABSOLUTE_PATH:
                    ref_path = path.abspath(parts_file_path)
                elif mode == PartsReplacementMode.RELATIVE_PATH:
                    base_parts_name = path.basename(base_parts_dir)
                    if parts_subfolder:
                        ref_path = path.join(
                            base_parts_name, parts_subfolder, rel_to_parts_dir
                        )
                    else:
                        ref_path = path.join(base_parts_name, rel_to_parts_dir)
                else:
                    ref_path = filename
                if parts_path_as_url:
                    ref_path = "file:///" + ref_path
                if parts_preview_with_path:
                    ref_path = ref_path + "\n---\n" + value[:parts_preview_len] + "..."
                set_at_path(obj, path_str, ref_path)
            else:
                set_at_path(
                    obj,
                    path_str,
                    {
                        "__parts_file__": path.join(parts_subfolder, rel_to_parts_dir)
                        if parts_subfolder
                        else rel_to_parts_dir,
                        "__value_type__": "str",
                    },
                )

    return obj


# ---------------------------------------------------------------------------
# write_json
# ---------------------------------------------------------------------------


def write_json(
    obj,
    file_path: str,
    append: bool = False,
    indent=None,
    create_dir=True,
    encoding="utf-8",
    ensure_ascii: bool = False,
    subfolder: str = None,
    space_ext_mode: Union[SpaceExtMode, str, bool, None] = None,
    **kwargs,
):
    """Writes a JSON representation of an object to a file.

    Converts the object via :func:`jsonfy`, then writes to file.
    Any keyword arguments matching :func:`jsonfy` parameters are forwarded
    automatically.

    Args:
        obj: The object to write.
        file_path: Path to the output file.
        append: If True, data is appended. Defaults to False.
        indent: JSON indentation. Defaults to None.
        create_dir: If True, create parent directories. Defaults to True.
        encoding: File encoding. Defaults to 'utf-8'.
        ensure_ascii: If True, ensure ASCII-only output. Defaults to False.
        subfolder: Inserts a subdirectory between parent and filename.
        space_ext_mode: Controls how file extension interacts with the space
            parameter. See :class:`SpaceExtMode`.
        **kwargs: Forwarded to :func:`jsonfy` and ``json.dumps``.

    Returns:
        The converted object (post-jsonfy).
    """
    if obj is None:
        return

    if create_dir:
        parent = path.dirname(file_path)
        if parent:
            os.makedirs(parent, exist_ok=True)

    # Insert subfolder between parent dir and filename
    if subfolder is not None:
        parent, filename = path.dirname(file_path), path.basename(file_path)
        file_path = path.join(parent, subfolder, filename)

    # Resolve actual file path (accounts for space + space_ext_mode)
    _resolved_file_path = file_path
    space = kwargs.get("space")
    if space is not None and space_ext_mode not in (
        None,
        False,
        SpaceExtMode.NONE,
        "none",
    ):
        mode = (
            SpaceExtMode.MOVE
            if space_ext_mode is True
            else SpaceExtMode(space_ext_mode)
        )
        base, ext = os.path.splitext(file_path)
        if mode == SpaceExtMode.MOVE:
            _resolved_file_path = base
            space = space + ext
            kwargs["space"] = space
            file_path = _resolved_file_path
        elif mode == SpaceExtMode.ADD:
            space = space + ext
            kwargs["space"] = space
    if space is not None:
        space_handler = kwargs.get("space_handler", _default_space_handler)
        _resolved_file_path = space_handler(file_path, space)

    # Split kwargs: jsonfy params vs remaining (json.dumps params)
    jsonfy_kwargs, other_kwargs = get_relevant_named_args(
        jsonfy, return_other_args=True, **kwargs
    )

    # Convert and extract parts
    obj = jsonfy(
        obj,
        parts_root_path=_resolved_file_path,
        overwrite=not append,
        ensure_ascii=ensure_ascii,
        **jsonfy_kwargs,
    )

    # Write to file using standard open()
    os.makedirs(path.dirname(_resolved_file_path), exist_ok=True)
    with open(_resolved_file_path, "a" if append else "w", encoding=encoding) as fout:
        fout.write(json.dumps(obj, indent=indent, ensure_ascii=ensure_ascii))
        fout.write("\n")
        fout.flush()

    return obj


# ---------------------------------------------------------------------------
# write_json_objs
# ---------------------------------------------------------------------------


def write_json_objs(
    json_obj_iter,
    output_path,
    process_func=None,
    use_tqdm=False,
    disp_msg=None,
    append=False,
    encoding="utf-8",
    ensure_ascii=False,
    indent=None,
    verbose=__debug__,
    create_dir=True,
    **kwargs,
):
    """Write an iterable of JSON objects to a file, one per line.

    Simplified version — does not support chunked output or process-ID
    file naming. Those features can be added later by porting
    ``write_all_lines`` and its dependency chain.

    Args:
        json_obj_iter: Iterable of JSON-serializable objects.
        output_path: Path to the output file.
        process_func: Optional function to transform each object before writing.
        use_tqdm: If True, show progress bar.
        disp_msg: Message to display with the progress bar.
        append: If True, append to the file.
        encoding: File encoding.
        ensure_ascii: If True, ensure ASCII-only output.
        indent: JSON indentation.
        verbose: If True, print progress messages.
        create_dir: If True, create parent directories.
        **kwargs: Additional keyword arguments forwarded to json.dumps.
    """
    if create_dir:
        parent = path.dirname(output_path)
        if parent:
            os.makedirs(parent, exist_ok=True)

    if verbose and disp_msg:
        _eprint_message("write_json_objs", disp_msg)

    json_strs = iter_all_json_strs(
        json_obj_iter, process_func, indent=indent,
        ensure_ascii=ensure_ascii, **kwargs,
    )
    json_strs = tqdm_wrap(json_strs, use_tqdm=use_tqdm, desc=disp_msg)

    mode = "a" if append else "w"
    with open(output_path, mode, encoding=encoding) as fout:
        for json_str in json_strs:
            fout.write(json_str)
            fout.write("\n")
        fout.flush()
