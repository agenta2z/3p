# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.

"""Artifact metadata decorators and helpers for parts-based serialization.

These decorators annotate classes with metadata (``__artifacts__`` and
``__artifact_types__``) that is consumed by both ``pickle_save(enable_parts=True)``
and ``jsonfy``/``write_json`` to extract fields or typed objects into separate
artifact files during serialization.
"""

from typing import Type, Union, Sequence, Optional, Callable, List

from rankevolve.src.utils.common_utils.map_helper import obj_walk_through


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


class PartsKeyPath:
    """Describes a key path to extract as a separate parts file.

    Attributes:
        key: Dotted key path in the source dict (e.g. 'body_html' or 'response.content').
        ext: File extension override (e.g. '.html'). None to auto-detect.
        alias: Name alias used in the output filename instead of the key path.
        subfolder: Per-entry subdirectory between parts_subfolder and file_stem.
    """
    __slots__ = ('key', 'ext', 'alias', 'subfolder')

    def __init__(self, key: str, ext: str = None, alias: str = None, subfolder: str = None):
        self.key = key
        self.ext = ext
        self.alias = alias
        self.subfolder = subfolder

    def __repr__(self):
        fields = [repr(self.key)]
        if self.ext is not None:
            fields.append(f'ext={self.ext!r}')
        if self.alias is not None:
            fields.append(f'alias={self.alias!r}')
        if self.subfolder is not None:
            fields.append(f'subfolder={self.subfolder!r}')
        return f'PartsKeyPath({", ".join(fields)})'


def artifact_field(
    key: str,
    *,
    type: Optional[str] = None,
    alias: Optional[str] = None,
    group: Optional[str] = None,
) -> Callable[[Type], Type]:
    """Class decorator that marks a field as an artifact for parts extraction.

    Stack multiple decorators to mark multiple fields.  Apply **outside**
    ``@attrs`` so the metadata survives slot class creation::

        @artifact_field('body_html', type='html', group='ui_source')
        @artifact_field('cleaned_html', type='html', group='ui_source')
        @attrs(slots=True)
        class MyResult:
            body_html: str = attrib()
            cleaned_html: str = attrib()

    Args:
        key: Field name (or dotted key path) to extract.
        type: Content type (e.g. ``'html'``, ``'.html'``).  Mapped to
            :attr:`PartsKeyPath.ext` with automatic dot normalization.
        alias: Filename alias (replaces key in the output filename).
        group: Per-entry subdirectory.  Mapped to
            :attr:`PartsKeyPath.subfolder`.
    """

    def decorator(cls):
        if '__artifacts__' not in cls.__dict__:
            cls.__artifacts__ = []
        cls.__artifacts__.append(
            PartsKeyPath(key=key, ext=_resolve_ext(type), alias=alias, subfolder=group)
        )
        return cls

    return decorator


def artifact_type(
    target_type: Type,
    *,
    type: Optional[str] = None,
    alias: Optional[str] = None,
    group: Optional[str] = None,
) -> Callable[[Type], Type]:
    """Class decorator that marks a type for automatic parts extraction.

    Any field whose value is an instance of ``target_type`` will be
    extracted to a separate parts file during serialization.  Stack multiple
    decorators to register multiple types::

        @artifact_type(Workflow, type='json', group='workflows')
        @artifact_type(HtmlContent, type='html', group='html')
        @attrs(slots=False)
        class MyPipeline:
            name: str = attrib()
            pre: Workflow = attrib()
            main: Workflow = attrib()
            page: HtmlContent = attrib()

    Args:
        target_type: The Python type to match via ``isinstance``.
        type: Content type / file extension (e.g. ``'json'``, ``'.html'``).
            Mapped to :attr:`PartsKeyPath.ext` with automatic dot normalization.
        alias: Filename alias (replaces key in the output filename).
        group: Per-entry subdirectory.  Mapped to
            :attr:`PartsKeyPath.subfolder`.
    """

    def decorator(cls):
        if "__artifact_types__" not in cls.__dict__:
            cls.__artifact_types__ = []
        cls.__artifact_types__.append({
            "target_type": target_type,
            "ext": _resolve_ext(type),
            "alias": alias,
            "subfolder": group,
        })
        return cls

    return decorator


def get_key_paths_for_artifacts(
    *classes: Type,
    groups: Optional[Union[str, Sequence[str]]] = None,
    recursive: bool = False,
) -> List[PartsKeyPath]:
    """Build a :class:`PartsKeyPath` list from ``@artifact_field`` metadata.

    Reads ``__artifacts__`` from each class and returns a flat list of
    :class:`PartsKeyPath` entries suitable for ``parts_key_paths``.

    Args:
        *classes: One or more classes decorated with :func:`artifact_field`.
        groups: Optional group name or sequence of group names to include.
            When ``None`` (default), all artifact fields are returned.
            When specified, only entries whose ``subfolder`` matches
            one of the given groups are included.
        recursive: If ``True``, use :func:`obj_walk_through` to walk the
            class annotations and discover nested ``@artifact_field``-decorated
            classes.  Fields already marked as artifacts on the parent are
            **not** recursed into (their children are skipped).

    Returns:
        List[PartsKeyPath]: Combined artifact entries from all classes.

    Example::

        logger = JsonLogger(
            file_path='logs/session.jsonl',
            parts_key_paths=get_key_paths_for_artifacts(WebDriverActionResult),
        )

        # Only 'ui_source' group:
        get_key_paths_for_artifacts(WebDriverActionResult, groups=['ui_source'])

        # Recursive discovery of nested artifact classes:
        get_key_paths_for_artifacts(OuterResult, recursive=True)
    """
    result = []
    if recursive:
        for cls in classes:
            _collect_artifacts_recursive(cls, result)
    else:
        for cls in classes:
            result.extend(cls.__dict__.get('__artifacts__', []))
    if groups is not None:
        if isinstance(groups, str):
            groups = (groups,)
        allowed = set(groups)
        result = [e for e in result if e.subfolder in allowed]
    return result


def _collect_artifacts_recursive(cls: Type, result: List[PartsKeyPath]) -> None:
    """Collect artifact entries from *cls* and nested types via walk-through.

    Uses :func:`obj_walk_through` in type mode to discover nested classes
    with ``__artifacts__``.  If a field is itself marked as an artifact on its
    parent, its children are not recursed into (the parent artifact already
    covers that subtree).
    """
    # Direct artifacts from the root class
    direct = cls.__dict__.get('__artifacts__', [])
    result.extend(direct)

    # Artifact keys discovered so far — used by should_recurse to prune
    # subtrees whose root field is already an artifact.
    artifact_keys = {(e.key,) for e in direct}

    def _should_recurse(path, _child):
        return tuple(path) not in artifact_keys

    for path, field_type in obj_walk_through(cls, should_recurse=_should_recurse):
        path_tuple = tuple(path)
        # Skip nodes that are themselves artifacts on their parent
        if path_tuple in artifact_keys:
            continue
        if isinstance(field_type, type) and hasattr(field_type, '__artifacts__'):
            prefix = '.'.join(path)
            for entry in field_type.__artifacts__:
                result.append(PartsKeyPath(
                    key=f'{prefix}.{entry.key}',
                    ext=entry.ext,
                    alias=entry.alias,
                    subfolder=entry.subfolder,
                ))
                # Mark child artifact so its subtree is pruned too
                artifact_keys.add(path_tuple + (entry.key,))
