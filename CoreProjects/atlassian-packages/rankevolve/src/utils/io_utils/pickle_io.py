# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.

"""Pickle I/O utilities with parts-mode support for artifact-aware serialization.

Ported from RichPythonUtils with import paths updated to rankevolve.
"""

import gzip
import json
import os
import pickle
import sys
from typing import Any, Dict, List, Optional, Union


# ---------------------------------------------------------------------------
# Private helpers for enable_parts mode
# ---------------------------------------------------------------------------

def _get_field(data, field_name, is_dict):
    """Get a field value from data, handling dicts, __slots__, and regular objects."""
    if is_dict:
        return data[field_name]
    return getattr(data, field_name)


def _set_field(data, field_name, value, is_dict):
    """Set a field value on data, handling dicts, __slots__, and regular objects."""
    if is_dict:
        data[field_name] = value
    elif hasattr(type(data), '__slots__'):
        object.__setattr__(data, field_name, value)
    else:
        setattr(data, field_name, value)


def _get_field_names(data):
    """Get field names from data, handling dicts, __slots__, and regular objects."""
    if isinstance(data, dict):
        return list(data.keys())
    # Prefer __dict__ (covers attrs slots=False, regular classes).
    # Only fall back to __slots__ scanning for true __slots__-only classes.
    if hasattr(data, '__dict__'):
        return list(vars(data).keys())
    obj_type = type(data)
    if hasattr(obj_type, '__slots__'):
        names = []
        for cls in obj_type.__mro__:
            if '__slots__' in cls.__dict__:
                names.extend(cls.__dict__['__slots__'])
        return names
    return []


def _resolve_part_filename(field_name, ext):
    """Resolve the filename and type string for a part based on its ext metadata."""
    if ext in ('.html', '.txt'):
        return f"{field_name}{ext}", 'text'
    return f"{field_name}.pkl", 'pickle'


def _write_manifest(dir_path, main_file, parts):
    """Write a versioned manifest.json to the parts directory."""
    manifest = {
        "version": 1,
        "main_file": main_file,
        "parts": parts,
    }
    manifest_path = os.path.join(dir_path, "manifest.json")
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)


def _collect_artifact_fields(data, artifact_types=None, path_prefix=""):
    """Collect fields to extract based on artifact metadata.

    Uses deep recursive scanning (walks into nested dicts, lists, and typed
    objects) to find fields matching target types anywhere in the object tree.
    At each nesting level, checks ``type(obj).__artifact_types__`` for
    additional metadata (handles Pattern B where the state class, not the
    Workflow class, has the decorator).

    Args:
        data: The object to scan.
        artifact_types: Explicit list of artifact type entries
            (list of dicts with 'target_type', 'ext', 'subfolder' keys).
            Used for plain dicts that have no class-level metadata.
        path_prefix: Dotted path prefix for nested fields.

    Returns:
        List of tuples: (dotted_key_path, value, ext, subfolder)
    """
    results = []

    # Build the type_map: {target_type: {'ext': ..., 'subfolder': ...}}
    type_map = {}
    # From class-level __artifact_types__
    cls_entries = getattr(type(data), '__artifact_types__', None)
    if cls_entries:
        for entry in cls_entries:
            tt = entry['target_type']
            if tt not in type_map:
                type_map[tt] = entry
    # From explicit artifact_types parameter
    if artifact_types:
        for entry in artifact_types:
            tt = entry['target_type']
            if tt not in type_map:
                type_map[tt] = entry

    # Also collect __artifacts__ (field-level decorators)
    field_artifacts = getattr(type(data), '__artifacts__', None)

    if not type_map and not field_artifacts:
        # No metadata at this level — but still recurse into children
        # to find metadata at deeper levels (Pattern B)
        is_dict = isinstance(data, dict)
        field_names = _get_field_names(data) if not isinstance(data, (list, tuple)) else []

        if isinstance(data, dict):
            for key, val in data.items():
                if val is None:
                    continue
                child_path = f"{path_prefix}.{key}" if path_prefix else key
                results.extend(_collect_artifact_fields(val, artifact_types, child_path))
        elif isinstance(data, (list, tuple)):
            for i, val in enumerate(data):
                if val is None:
                    continue
                child_path = f"{path_prefix}.{i}" if path_prefix else str(i)
                results.extend(_collect_artifact_fields(val, artifact_types, child_path))
        elif field_names:
            for name in field_names:
                val = getattr(data, name, None)
                if val is None:
                    continue
                child_path = f"{path_prefix}.{name}" if path_prefix else name
                results.extend(_collect_artifact_fields(val, artifact_types, child_path))
        return results

    # Process __artifacts__ (explicit field-level extraction)
    if field_artifacts:
        is_dict = isinstance(data, dict)
        for artifact in field_artifacts:
            key = artifact.key
            ext = artifact.ext
            subfolder = artifact.subfolder
            # Navigate dotted key path
            parts = key.split('.')
            val = data
            for part in parts:
                if val is None:
                    break
                if isinstance(val, dict):
                    val = val.get(part)
                else:
                    val = getattr(val, part, None)
            if val is not None:
                full_path = f"{path_prefix}.{key}" if path_prefix else key
                results.append((full_path, val, ext, subfolder))

    # Process type_map — deep scan into children
    if type_map:
        is_dict = isinstance(data, dict)
        field_names = _get_field_names(data) if not isinstance(data, (list, tuple)) else []

        if isinstance(data, dict):
            for key, val in data.items():
                if val is None:
                    continue
                child_path = f"{path_prefix}.{key}" if path_prefix else key
                # Check if this value matches a target type
                matched = False
                for target_type, entry in type_map.items():
                    if isinstance(val, target_type):
                        results.append((
                            child_path, val,
                            entry.get('ext'), entry.get('subfolder')
                        ))
                        matched = True
                        break
                if not matched:
                    # Recurse deeper
                    results.extend(_collect_artifact_fields(val, artifact_types, child_path))
        elif isinstance(data, (list, tuple)):
            for i, val in enumerate(data):
                if val is None:
                    continue
                child_path = f"{path_prefix}.{i}" if path_prefix else str(i)
                matched = False
                for target_type, entry in type_map.items():
                    if isinstance(val, target_type):
                        results.append((
                            child_path, val,
                            entry.get('ext'), entry.get('subfolder')
                        ))
                        matched = True
                        break
                if not matched:
                    results.extend(_collect_artifact_fields(val, artifact_types, child_path))
        elif field_names:
            for name in field_names:
                val = getattr(data, name, None)
                if val is None:
                    continue
                child_path = f"{path_prefix}.{name}" if path_prefix else name
                matched = False
                for target_type, entry in type_map.items():
                    if isinstance(val, target_type):
                        results.append((
                            child_path, val,
                            entry.get('ext'), entry.get('subfolder')
                        ))
                        matched = True
                        break
                if not matched:
                    results.extend(_collect_artifact_fields(val, artifact_types, child_path))

    return results


def _navigate_to_parent(data, dotted_path):
    """Navigate to the parent of a dotted key path, returning (parent, final_key, is_dict).

    For a path like 'state.planner', navigates to data['state'] (or data.state)
    and returns (data['state'], 'planner', is_dict_of_parent).
    For a simple path like 'planner', returns (data, 'planner', is_dict).
    """
    parts = dotted_path.split('.')
    current = data
    for part in parts[:-1]:
        if isinstance(current, dict):
            current = current[part]
        elif isinstance(current, (list, tuple)):
            current = current[int(part)]
        else:
            current = getattr(current, part)
    return current, parts[-1], isinstance(current, dict)


def _save_parts(data, dir_path, artifact_types=None):
    """Save an object with artifact-aware parts extraction.

    Returns None. Writes main.pkl, part files, and manifest.json to dir_path.
    """
    os.makedirs(dir_path, exist_ok=True)

    # Collect artifact fields via deep scanning
    collected = _collect_artifact_fields(data, artifact_types)

    if not collected:
        # Graceful degradation: no artifacts found, save entire object as main.pkl
        main_path = os.path.join(dir_path, "main.pkl")
        with open(main_path, 'wb') as f:
            pickle.dump(data, f)
            f.flush()
        _write_manifest(dir_path, "main.pkl", [])
        return

    # Save originals and null fields for main pickle (try/finally for mutation safety)
    originals = []  # list of (parent, key, is_dict, original_value)
    try:
        for dotted_path, val, ext, subfolder in collected:
            parent, key, is_dict = _navigate_to_parent(data, dotted_path)
            original = _get_field(parent, key, is_dict)
            originals.append((parent, key, is_dict, original))
            _set_field(parent, key, None, is_dict)

        # Pickle the lightweight main object (with artifact fields set to None)
        main_path = os.path.join(dir_path, "main.pkl")
        with open(main_path, 'wb') as f:
            pickle.dump(data, f)
            f.flush()
    finally:
        # Restore all original values
        for parent, key, is_dict, original in originals:
            _set_field(parent, key, original, is_dict)

    # Save each part to its own file
    manifest_parts = []
    for dotted_path, val, ext, subfolder in collected:
        # Use full dotted path (dots → __) to avoid filename collisions
        safe_name = dotted_path.replace('.', '__')
        filename, type_str = _resolve_part_filename(safe_name, ext)

        # Handle subfolder grouping
        if subfolder:
            part_dir = os.path.join(dir_path, subfolder)
            os.makedirs(part_dir, exist_ok=True)
            rel_path = os.path.join(subfolder, filename)
        else:
            rel_path = filename

        part_path = os.path.join(dir_path, rel_path)

        if type_str == 'text':
            with open(part_path, 'w', encoding='utf-8') as f:
                f.write(str(val))
        else:
            with open(part_path, 'wb') as f:
                pickle.dump(val, f)
                f.flush()

        manifest_parts.append({
            "field": dotted_path,
            "file": rel_path,
            "type": type_str,
            "original_type": type(val).__qualname__,
        })

    _write_manifest(dir_path, "main.pkl", manifest_parts)


def _load_parts(dir_path):
    """Load an object from a pickle-parts directory.

    Reads main.pkl, manifest.json, and all part files. Restores
    part values onto the main object.
    """
    manifest_path = os.path.join(dir_path, "manifest.json")
    main_path = os.path.join(dir_path, "main.pkl")

    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    with open(main_path, 'rb') as f:
        obj = pickle.load(f)

    parts = manifest.get("parts", [])
    if not parts:
        return obj

    for part_info in parts:
        dotted_path = part_info["field"]
        rel_path = part_info["file"]
        type_str = part_info["type"]

        part_path = os.path.join(dir_path, rel_path)
        if not os.path.exists(part_path):
            raise FileNotFoundError(
                f"Part file not found: {part_path} (field: {dotted_path})"
            )

        if type_str == 'text':
            with open(part_path, 'r', encoding='utf-8') as f:
                val = f.read()
        else:
            with open(part_path, 'rb') as f:
                val = pickle.load(f)

        # Navigate to parent and set the field
        parent, key, is_dict = _navigate_to_parent(obj, dotted_path)
        _set_field(parent, key, val, is_dict)

    return obj


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def pickle_load(source: Union[str, bytes], compressed: bool = False, encoding=None,
                enable_parts: bool = False):
    """Load a Python object from a pickle file, bytes, or parts directory.

    When ``enable_parts=True``, ``source`` is treated as a directory path
    containing ``main.pkl`` and ``manifest.json`` (produced by
    ``pickle_save(..., enable_parts=True)``).  Parts are loaded and
    reassembled into the original object.

    Args:
        source: The file path to the pickle file, or pickle bytes to load.
        compressed: If True, interpret the file/bytes as compressed with gzip.
        encoding: The encoding to use when loading the pickle file in Python 3.
        enable_parts: If True, treat source as a parts directory.

    Returns:
        The Python object stored in the pickle file or bytes.
    """
    if enable_parts:
        if isinstance(source, bytes):
            raise ValueError(
                "pickle_load with enable_parts=True requires a directory path, not bytes"
            )
        return _load_parts(source)

    if isinstance(source, bytes):
        if compressed:
            source = gzip.decompress(source)
        return pickle.loads(source)

    with open(source, 'rb') if not compressed else gzip.open(source, 'rb') as f:
        if encoding is None or sys.version_info < (3, 0):
            return pickle.load(f)
        else:
            return pickle.load(f, encoding=encoding)


def pickle_save(data, file_path: Optional[str] = None, compressed: bool = False,
                ensure_dir_exists=True, verbose: bool = __debug__,
                enable_parts: bool = False,
                artifact_types: Optional[List[Dict[str, Any]]] = None) -> Optional[bytes]:
    """Save a Python object to a pickle file, return bytes, or save as parts.

    When ``enable_parts=True``, ``file_path`` is treated as a directory path.
    The object is inspected for ``__artifact_types__`` and ``__artifacts__``
    metadata (and/or the explicit ``artifact_types`` parameter).  Matching
    fields are extracted to separate files.  A ``main.pkl`` (with extracted
    fields set to None) and ``manifest.json`` are written.

    Args:
        data: The Python object to save.
        file_path: The path where the pickle file will be saved.
            When enable_parts=True, treated as a directory path.
        compressed: If True, save in gzip-compressed format.
        ensure_dir_exists: If True, create the parent directory if needed.
        verbose: If True, print debug information when creating directories.
        enable_parts: If True, save in parts mode (directory with
            main.pkl + manifest.json + part files).
        artifact_types: Explicit artifact type entries for objects
            without class-level metadata.

    Returns:
        None if file_path is provided or enable_parts=True,
        bytes if file_path is None and enable_parts=False.
    """
    if enable_parts:
        if file_path is None:
            raise ValueError(
                "pickle_save with enable_parts=True requires a directory path, not None"
            )
        _save_parts(data, file_path, artifact_types=artifact_types)
        return None

    if file_path is None:
        if compressed:
            return gzip.compress(pickle.dumps(data))
        return pickle.dumps(data)

    if ensure_dir_exists:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'wb+') if not compressed else gzip.open(file_path, 'wb+') as f:
        pickle.dump(data, f)
        f.flush()
        f.close()
    return None
