"""IO utilities — JSON and pickle serialization with typed round-tripping.

JSON I/O (``json_io``)
======================

Write-side
----------
``jsonfy(obj, ...)``
    Convert any Python object (attrs, dataclass, namedtuple, dict, …) to a
    JSON-serializable dict.  Optionally extracts large values into companion
    ``.parts/`` files and embeds ``__parts_file__`` reference markers.

``write_json(obj, file_path, ...)``
    ``jsonfy`` + write to a single file.  Supports ``append``, ``subfolder``,
    ``space`` namespacing, and all ``jsonfy`` keyword arguments.

``write_json_objs(iter, output_path, ...)``
    Stream an iterable of JSON objects to a JSONL file, one per line.

``JsonLogger(**kwargs)``
    Callable wrapper around ``write_json`` for use as a Debuggable logger.

Decorator helpers for declaring which fields should be extracted to parts:

``artifact_field(key, *, type, alias, group)``
    Class decorator marking a named field for parts extraction.

``artifact_type(target_type, *, type, alias, group)``
    Class decorator marking all fields of a given *type* for automatic
    parts extraction during ``jsonfy``.

``get_key_paths_for_artifacts(*classes, groups, recursive)``
    Build a ``PartsKeyPath`` list from ``@artifact_field`` metadata.

Read-side
---------
``dejsonfy(data, target_type=None, target=None, type_file=None, ...)``
    Reconstruct a typed Python object from a JSON-serializable value.
    Inverse of ``jsonfy`` / ``dict__``.  Handles attrs classes, dataclasses,
    namedtuples, ``__slots__`` objects, enums, ``Optional``/``Union``,
    ``List``/``Dict``/``Set``/``Tuple`` generics, and ``bytes``.

    Type resolution sources (checked in order):

    1. **Inline metadata** — ``__type__`` / ``__module__`` keys embedded by
       ``jsonfy(save_type=True)`` or ``jsonfy(save_type='inline')``.
    2. **Companion type file** — a ``.types.json`` sidecar written by
       ``jsonfy(save_type='separate')``, passed via ``type_file=``.
    3. **Explicit** ``target_type`` — the caller supplies the expected type.

``resolve_json_parts(obj, source_path, parts_suffix='.parts')``
    Walk a dict and replace ``__parts_file__`` reference markers with the
    actual file content from the adjacent ``.parts/`` directory.  Read-side
    counterpart to ``jsonfy``'s parts extraction.

``iter_json_objs(json_input, *, resolve_parts=False, ...)``
    Iterate JSON objects from a JSONL file, a directory of JSON files, a
    list of file paths, or any line-iterable.  When ``resolve_parts=True``,
    parts references are resolved automatically.

``iter_all_json_objs_from_all_sub_dirs(input_path_or_paths, ...)``
    Recursively collect JSON files from nested subdirectories and iterate
    their objects.

``JsonLogReader(file_path, *, resolve_parts=True, ...)``
    Reusable iterable reader for JSON log files; counterpart to
    ``JsonLogger``.  Each ``for obj in reader`` creates a fresh iterator.

``read_json(json_text_or_file)``
    Load a JSON file or parse a JSON string (auto-detected).

``read_jsonl(jsonl_text_or_file)``
    Load all objects from a JSONL file or parse a multi-line JSONL string.

``read_single_line_json_file(json_input)``
    Read a whole-file JSON document (not line-delimited).

Round-trip examples
-------------------
Typed round-trip (attrs / dataclass)::

    from rankevolve.src.utils.io_utils import jsonfy, dejsonfy

    data  = jsonfy(my_attrs_obj)
    clone = dejsonfy(data, target_type=type(my_attrs_obj))

Write with parts, then read back::

    from rankevolve.src.utils.io_utils import (
        write_json, iter_json_objs, dejsonfy, PartsKeyPath,
    )

    write_json(obj, 'log.jsonl',
               parts_key_paths=[PartsKeyPath('body', ext='.html')],
               parts_min_size=0)

    for raw in iter_json_objs('log.jsonl', resolve_parts=True):
        restored = dejsonfy(raw, target_type=MyClass)

Inline type metadata (no explicit target_type needed)::

    data  = jsonfy(my_obj, save_type=True)   # embeds __type__/__module__
    clone = dejsonfy(data)                    # auto-resolves type

Pickle I/O (``pickle_io``)
==========================
``pickle_save(obj, path)`` / ``pickle_load(path)``
    Convenience wrappers around Python's ``pickle`` module.
"""

from .json_io import (
    artifact_field,
    artifact_type,
    dejsonfy,
    get_key_paths_for_artifacts,
    iter_all_json_objs_from_all_sub_dirs,
    iter_json_objs,
    JsonLogReader,
    JsonLogger,
    jsonfy,
    PartsKeyPath,
    read_json,
    read_jsonl,
    read_single_line_json_file,
    resolve_json_parts,
    write_json,
    write_json_objs,
)
from .pickle_io import pickle_load, pickle_save
