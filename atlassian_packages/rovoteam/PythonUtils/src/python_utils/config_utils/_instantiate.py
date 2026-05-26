"""Config loading, alias resolution, attrs preprocessing, and Hydra instantiation.

This module is the core of the config_utils package.  The public functions are
``load_config``, ``merge_configs``, and ``instantiate``.
"""

from __future__ import annotations

import abc
import copy
import functools
import importlib
import inspect
import logging
import typing
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from python_utils.config_utils._registry import (
    _alias_alternatives,
    _registry,
    AliasResolutionError,
    MissingTargetError,
    resolve_target,
)
from python_utils.config_utils._resolvers import (
    _current_config_dir,
    ensure_resolvers,
)

_logger = logging.getLogger(__name__)

_IMPORT_KEY = "_import_"
_IMPORT_SHARED_KEY = "_import_shared_"
_FACTORY_MARKER = "_factory_"


from python_utils.config_utils._lazy_config_factory import LazyConfigFactory


class _ImportFactory(LazyConfigFactory):
    """Deprecated alias for ``LazyConfigFactory``.

    Kept for backward compatibility with ``_import_:``-tagged YAML factories.
    Use ``LazyConfigFactory`` directly in new code.
    """

    def __init__(self, config_dict: dict, injectables: dict | None = None) -> None:
        import warnings
        warnings.warn(
            "_ImportFactory is deprecated; use LazyConfigFactory instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(config_dict=config_dict, injectables=injectables)


def _deep_merge(base: dict, overrides: dict) -> dict:
    """Recursively merge *overrides* into *base*, returning a new dict."""
    result = dict(base)
    for k, v in overrides.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


# ---------------------------------------------------------------------------
# `_inherits_` directive — deep-copy + override-merge from another node
# ---------------------------------------------------------------------------
#
# Convention: a dict containing ``_inherits_: <dotted-path>`` is replaced by
# ``deep_copy(source_at_path)`` deep-merged with the dict's other keys
# (current keys win). Each occurrence produces a fresh deep copy, so
# instantiation through Hydra produces distinct Python instances.
#
# This is at the same architectural layer as ``_resolve_import_``: a
# load-time pre-processing step on the plain-dict container, run before
# ``OmegaConf.create(container)`` in ``load_config``.

_INHERITS_KEY = "_inherits_"


def _resolve_path_in_root(root_container, path_str):
    """Look up a dotted path inside ``root_container``.

    Supports list indices via integer segments (e.g.,
    ``"flow_configs.0.initial_inferencer"``). The target node must be a
    dict. Raises ``TypeError`` for non-string paths or non-dict targets,
    ``ValueError`` for missing segments.
    """
    if not isinstance(path_str, str):
        raise TypeError(
            f"{_INHERITS_KEY} must be a string path; got "
            f"{type(path_str).__name__}: {path_str!r}"
        )
    if not path_str:
        raise ValueError(f"{_INHERITS_KEY} path must not be empty")
    parts = path_str.split(".")
    cursor = root_container
    for i, segment in enumerate(parts):
        try:
            if isinstance(cursor, list):
                idx = int(segment)
                cursor = cursor[idx]
            elif isinstance(cursor, dict):
                cursor = cursor[segment]
            else:
                raise ValueError(
                    f"cannot traverse {type(cursor).__name__} at segment "
                    f"{i} ({'.'.join(parts[: i + 1])!r})"
                )
        except (KeyError, IndexError, ValueError) as exc:
            raise ValueError(
                f"{_INHERITS_KEY}: failed to resolve path {path_str!r} at "
                f"segment {i} ({'.'.join(parts[: i + 1])!r}): {exc}"
            ) from exc
    if not isinstance(cursor, dict):
        raise TypeError(
            f"{_INHERITS_KEY}: target at {path_str!r} must be a dict; got "
            f"{type(cursor).__name__}"
        )
    return cursor


def _resolve_inherits_(node, root_container, _resolution_stack=None):
    """Resolve ``_inherits_`` directives via deep-copy + override-merge.

    Each dict containing ``_inherits_: <path>`` is replaced with:
      1. ``copy.deepcopy`` of the resolved source node at ``<path>``.
      2. Recursively resolved (so chained ``_inherits_`` chains complete
         depth-first; cycles are detected via the ``_resolution_stack``).
      3. Merged with the current dict's other keys via ``_deep_merge``
         (current dict's keys win; lists are replaced wholesale).
      4. The ``_inherits_`` key stripped.

    Single-inheritance only — the directive value must be a string path.
    Lists/multiple bases are not supported (raises ``TypeError`` via
    ``_resolve_path_in_root``).

    Cycles raise ``ValueError`` with the path chain (e.g., ``a -> b -> a``).

    Note on OmegaConf interpolations inside the source: the deep-copied
    interpolation strings still resolve against the root config when
    ``OmegaConf.resolve`` runs (absolute, root-relative). For
    sibling-aware references after inheritance, source nodes should use
    ``${.field}`` (relative) instead of ``${field}`` (absolute).
    """
    import copy as _copy

    if _resolution_stack is None:
        _resolution_stack = []

    if isinstance(node, list):
        return [
            _resolve_inherits_(item, root_container, _resolution_stack)
            for item in node
        ]
    if not isinstance(node, dict):
        return node

    if _INHERITS_KEY in node:
        path = node[_INHERITS_KEY]
        if path in _resolution_stack:
            chain = " -> ".join(_resolution_stack + [str(path)])
            raise ValueError(f"{_INHERITS_KEY} cycle: {chain}")
        # Validate type and look up source
        source = _resolve_path_in_root(root_container, path)
        # Deepcopy first so recursive resolution doesn't mutate the root.
        source_copy = _copy.deepcopy(source)
        # Resolve any _inherits_ chain on the source (depth-first).
        source_resolved = _resolve_inherits_(
            source_copy, root_container, _resolution_stack + [path]
        )
        # Merge current dict's other keys on top — current keys win.
        # Recursively resolve _inherits_ inside the override values too.
        overrides = {k: v for k, v in node.items() if k != _INHERITS_KEY}
        overrides_resolved = {
            k: _resolve_inherits_(v, root_container, _resolution_stack)
            for k, v in overrides.items()
        }
        return _deep_merge(source_resolved, overrides_resolved)

    # No directive at this level; recurse into children.
    return {
        k: _resolve_inherits_(v, root_container, _resolution_stack)
        for k, v in node.items()
    }


def _resolve_import_(node, current_yaml_dir: Path):
    """Resolve ``_import_`` and ``_import_shared_`` references in a raw config dict tree.

    ``_import_shared_``
        Shared (eager) semantics — the referenced YAML is loaded,
        sibling keys are deep-merged as overrides, and the merged dict
        is returned directly.  Hydra instantiates it **once**.

    ``_import_``
        Factory (lazy) semantics — same merge behaviour, but the merged
        dict is tagged with ``_factory_: true``.  Later,
        ``_filter_attrs_keys`` converts tagged dicts inside
        ``*_factory`` fields into ``_ImportFactory`` callables so that
        each factory invocation creates a **fresh** instance.

    Both variants recurse into the merged result so nested references
    are resolved.
    """
    if isinstance(node, list):
        return [_resolve_import_(item, current_yaml_dir) for item in node]
    if not isinstance(node, dict):
        return node

    import_key: str | None = None
    if _IMPORT_KEY in node:
        import_key = _IMPORT_KEY
    elif _IMPORT_SHARED_KEY in node:
        import_key = _IMPORT_SHARED_KEY

    if import_key is not None:
        ref_path = (current_yaml_dir / node[import_key]).resolve()
        if not ref_path.exists():
            raise FileNotFoundError(
                f"{import_key}: referenced yaml not found: {ref_path}"
            )
        from omegaconf import OmegaConf

        ref_cfg = OmegaConf.to_container(
            OmegaConf.load(str(ref_path)), resolve=False
        )
        overrides = {k: v for k, v in node.items() if k != import_key}
        merged = _deep_merge(ref_cfg, overrides)
        merged = _resolve_import_(merged, ref_path.parent)

        if import_key == _IMPORT_KEY:
            merged[_FACTORY_MARKER] = True
        return merged

    return {k: _resolve_import_(v, current_yaml_dir) for k, v in node.items()}


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def load_config(path: str, overrides: Optional[Dict[str, Any]] = None):
    """Load a YAML file into an OmegaConf ``DictConfig``.

    Parameters
    ----------
    path : str
        Path to the YAML file.
    overrides : dict, optional
        Key-value overrides merged on top of the loaded config via
        ``OmegaConf.merge``.

    Notes
    -----
    * Sets ``_current_config_dir`` (a ``ContextVar``) so that the
      ``${path:...}`` resolver can resolve paths relative to the YAML file.
    * Calls ``OmegaConf.resolve(cfg)`` **eagerly** so that the ``ContextVar``
      can be safely reset in ``finally``.  This means **all** interpolations
      (including ``${oc.env:...}``) are captured at load time.
    """
    from omegaconf import OmegaConf

    ensure_resolvers()
    token = _current_config_dir.set(str(Path(path).resolve().parent))
    try:
        cfg = OmegaConf.load(path)
        # Resolve _import_ references before overrides merge so that
        # dot-notation overrides can patch into the expanded config.
        container = OmegaConf.to_container(cfg, resolve=False)
        container = _resolve_import_(container, Path(path).resolve().parent)
        # Resolve _inherits_ directives (deep-copy + override-merge from
        # another node within the same container). Runs after _import_ so
        # _inherits_ can reference imported nodes; runs before
        # OmegaConf.create so OmegaConf interpolations inside copied nodes
        # resolve naturally during the OmegaConf.resolve step below.
        container = _resolve_inherits_(container, container)
        cfg = OmegaConf.create(container)
        if overrides:
            # Convert dotted override keys to nested dicts so that
            # OmegaConf.merge treats them as nested paths.
            # e.g., {"workspace.root": "/tmp"} → {"workspace": {"root": "/tmp"}}
            nested_overrides = {}
            for key, val in overrides.items():
                parts = key.split(".")
                d = nested_overrides
                for part in parts[:-1]:
                    d = d.setdefault(part, {})
                d[parts[-1]] = val
            cfg = OmegaConf.merge(cfg, nested_overrides)
        # Eagerly resolve while the ContextVar is set.
        OmegaConf.resolve(cfg)
        return cfg
    finally:
        _current_config_dir.reset(token)


def merge_configs(*configs):
    """Merge multiple configs (dicts or ``DictConfig``).  Later configs win."""
    from omegaconf import OmegaConf

    return OmegaConf.merge(*configs)


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------

def instantiate(config, _convert_: str = "all", **kwargs) -> Any:
    """Instantiate a Python object from *config* using Hydra.

    This is a thin wrapper around ``hydra.utils.instantiate`` that first:
    1. Resolves target aliases → full import paths.
    2. Expands string shorthand (``field: Alias`` → ``field: {_target_: ...}``).
    3. Filters invalid attrs keys (``init=False`` fields) with a warning.
    4. After Hydra instantiation, replaces ``functools.partial`` entries
       that originated from ``_import_`` with ``_ImportFactory`` callables
       so each factory invocation creates a fresh instance tree.

    Parameters
    ----------
    config : DictConfig or dict
        Configuration with ``_target_`` keys.
    _convert_ : str
        Hydra's ``_convert_`` parameter.  ``"all"`` (default) converts
        ``DictConfig``/``ListConfig`` to native Python types — **load-bearing**
        for attrs converters like ``dict_()``.
    **kwargs
        Extra keyword arguments forwarded to ``hydra.utils.instantiate``.
    """
    from hydra.utils import instantiate as _hydra_instantiate

    ensure_resolvers()
    config, factory_configs = _resolve_and_preprocess(config)
    result = _hydra_instantiate(config, _convert_=_convert_, **kwargs)
    for owner_path, field_name, child_key, raw_config, injectables in factory_configs:
        _apply_lazy_factory(result, owner_path, field_name, child_key, raw_config, injectables)
    return result


def _apply_lazy_factory(root, owner_path, field_name, child_key, raw_config, injectables=None):
    """Replace a Hydra-created partial with a ``LazyConfigFactory``.

    Navigates the instantiated object tree via *owner_path* (a dot-separated
    string of attr names recorded during ``_walk``) to find the object that
    owns *field_name*, then replaces the partial at that location.

    Deterministic — no heuristic search, no false positives.
    """
    obj = root
    if owner_path:
        for part in owner_path.split("."):
            obj = getattr(obj, part, None)
            if obj is None:
                return
    container = getattr(obj, field_name, None)
    if container is None:
        return
    factory = LazyConfigFactory(raw_config, injectables=injectables)
    if child_key is None:
        setattr(obj, field_name, factory)
    elif isinstance(container, dict):
        container[child_key] = factory


# ---------------------------------------------------------------------------
# Internal: single-pass tree walk
# ---------------------------------------------------------------------------

def _resolve_and_preprocess(config):
    """Convert to plain dict, walk the tree, convert back to ``DictConfig``.

    Returns ``(DictConfig, factory_configs)`` where *factory_configs* is a
    list of ``(field_name, child_key, raw_config)`` tuples recorded by
    ``_filter_attrs_keys`` for ``_import_`` entries inside ``*_factory``
    fields.  The caller replaces the corresponding Hydra-created partials
    with ``_ImportFactory`` objects after instantiation.
    """
    from omegaconf import OmegaConf

    raw = OmegaConf.to_container(config, resolve=False)
    factory_configs: List[tuple] = []
    _walk(raw, _factory_configs=factory_configs)
    return OmegaConf.create(raw), factory_configs


_HYDRA_KEYS = {"_target_", "_recursive_", "_convert_", "_partial_", "_args_"}
# Keys starting with _ that are data (not injection sources) — preserved as-is.
_DATA_KEYS = {"__default__"}


def _walk(
    node: Any,
    _injectables: Optional[Dict[str, Any]] = None,
    _factory_configs: Optional[List[tuple]] = None,
    _expected_cls: Optional[type] = None,
    _owner_path: str = "",
) -> None:
    """Recursively process a mutable dict/list tree.

    For each dict node, five things happen in order:

    0. **Injectable collection** — keys starting with ``_`` (but not Hydra
       reserved keys) are collected as injectable defaults.  These propagate
       down to descendant ``_target_`` nodes: if a child class has a matching
       constructor param (without the ``_`` prefix) and doesn't already set it,
       the value is auto-injected.  E.g., ``_template_manager`` at the parent
       level auto-injects as ``template_manager`` into children that accept it.

    1. **Alias resolution** — if ``_target_`` is present and is a plain string
       (not an interpolation), resolve it via the registry.  Then import the
       target class and, for ``@attrs`` classes, filter out keys that are not
       valid ``__init__`` parameters.  Also auto-injects ``_partial_: true``
       for attrs fields ending in ``_factory``.

    1b. **Auto-injection** — for ``_target_`` nodes, inject inherited
        ``_``-prefixed values from ancestors if the class accepts the param
        and the node doesn't already set it.  Values are deep-copied to
        avoid shared mutation across siblings.

    2. **String shorthand expansion** — for any non-Hydra key whose value is a
       plain string matching a registered alias, expand it into
       ``{"_target_": resolved_path}``.

    3. **Recursion** — recurse into all values with inherited injectables
       and parent field type context (``_expected_cls``).

    Parameters
    ----------
    _expected_cls : type or None
        The parent field's declared type, used by D2 inference to infer
        ``_target_`` when absent.  ``None`` at the root level.
    """
    if _injectables is None:
        _injectables = {}

    if isinstance(node, dict):
        # 0. Collect _-prefixed keys as injectable defaults (inherit from parent).
        #    Keys that are injectable sources (not actual attrs field names) are
        #    removed from node so Hydra doesn't pass them as kwargs.
        #    Keys that ARE attrs field names (e.g., _cache with init=False) are
        #    left for _filter_attrs_keys to handle normally.
        local_injectables = dict(_injectables)
        injectable_source_keys = []
        for k, v in node.items():
            if k.startswith("_") and k not in _HYDRA_KEYS and k not in _DATA_KEYS:
                local_injectables[k.lstrip("_")] = v
                injectable_source_keys.append(k)
        # Defer removal until after _filter_attrs_keys — it needs to see
        # attrs field names like _cache to strip them with a warning.
        # We remove only keys that _filter_attrs_keys did NOT handle
        # (i.e., non-field injection sources).

        # 1. Resolve _target_ alias + attrs preprocessing
        #    D2: If _target_ is absent, try to infer it from parent field type.
        cls = None
        if "_target_" not in node:
            inferred = _infer_target(_expected_cls, node)
            if inferred is not None:
                node["_target_"] = inferred

        if "_target_" in node and isinstance(node["_target_"], str):
            target = node["_target_"]
            if not target.startswith("${"):
                node["_target_"] = resolve_target(target)
                # D1 structural dispatch: if the original target was a
                # registered alias with alternatives, pick the right
                # candidate based on which unique fields appear in the node.
                if target in _registry:
                    node["_target_"] = _dispatch_alias(
                        target, node["_target_"], node
                    )
                cls = _import_target(node["_target_"])
                if cls is not None:
                    _filter_attrs_keys(node, cls, _factory_configs, local_injectables, _owner_path=_owner_path)

        # 1a. Remove injectable source keys that survived _filter_attrs_keys.
        #     _filter_attrs_keys already removed _-prefixed keys that ARE attrs
        #     fields (e.g., _cache with init=False). What remains are pure
        #     injection sources (e.g., _template_manager) — remove them so
        #     Hydra doesn't pass them as constructor kwargs.
        for k in injectable_source_keys:
            if k in node:
                del node[k]

        # 1b. Auto-inject: for _target_ nodes, inject inherited _-prefixed
        #     values if the class accepts the param and node doesn't set it.
        if cls is not None and local_injectables:
            try:
                valid_params = set(inspect.signature(cls).parameters.keys())
            except (ValueError, TypeError):
                valid_params = set()
            for param_name, value in local_injectables.items():
                if param_name in valid_params and param_name not in node:
                    node[param_name] = copy.deepcopy(value)

        # 1c. Strip _factory_ markers not consumed by _filter_attrs_keys.
        #     (_import_ outside a *_factory field degrades to shared semantics.)
        node.pop(_FACTORY_MARKER, None)

        # 1d. Slot-based role defaults — class-declared template defaults for
        #     specific slot fields. Skips entirely if the node opts out via
        #     ``_disable_slot_defaults_: true``. Each entry in the class's
        #     ``SLOT_DEFAULTS`` ClassVar is a (slot_path, defaults_obj) pair;
        #     ``slot_path`` may be a dotted path with ``*`` wildcards for
        #     list-element walks (e.g. ``"flow_configs.*.followup_inferencer"``).
        #     ``defaults_obj`` is duck-typed via ``apply_to(node, parent_node=)``.
        #     Note: the opt-out key was already stripped from ``node`` by the
        #     underscore-prefix collection above (step 0/1a) and survives in
        #     ``local_injectables`` under its un-prefixed name.
        if cls is not None and not local_injectables.get(
            "disable_slot_defaults_", False
        ):
            for slot_path, defaults_obj in _collect_slot_defaults(cls).items():
                _apply_at_path(node, slot_path.split("."), defaults_obj, parent_node=node)

        # 2. String shorthand expansion
        for key, val in list(node.items()):
            if key.startswith("_"):
                continue  # skip Hydra keys (_target_, _recursive_, etc.)
            if isinstance(val, str) and val in _registry:
                node[key] = {"_target_": resolve_target(val)}

        # 3. Recurse (injectables + field type context propagate to children)
        #    Build parent's field-type map once so children can infer _target_.
        #    Use cls.__init__ for get_type_hints because plain classes store
        #    annotations on __init__, not on the class itself.
        field_types: Dict[str, Any] = {}
        if cls is not None:
            try:
                field_types = typing.get_type_hints(cls.__init__, include_extras=False)
            except Exception:
                try:
                    field_types = typing.get_type_hints(cls, include_extras=False)
                except Exception:
                    _logger.debug(
                        "D2: typing.get_type_hints failed for %s — "
                        "nested _target_ inference disabled for its children.",
                        cls.__name__ if hasattr(cls, "__name__") else cls,
                    )
                    field_types = {}
        for key, v in node.items():
            # D2: For dict children without _target_, check __yaml_default_nested__
            # on the parent class first (highest precedence), then fall back to
            # type-based inference via _expected_cls.
            child_expected_cls = field_types.get(key)
            if (
                cls is not None
                and isinstance(v, dict)
                and "_target_" not in v
            ):
                nested_alias = _check_yaml_default_nested(cls, key)
                if nested_alias is not None:
                    v["_target_"] = nested_alias
            child_path = f"{_owner_path}.{key}" if _owner_path else key
            _walk(
                v,
                _injectables=local_injectables,
                _factory_configs=_factory_configs,
                _expected_cls=child_expected_cls,
                _owner_path=child_path,
            )

    elif isinstance(node, list):
        for item in node:
            _walk(item, _injectables=_injectables, _factory_configs=_factory_configs, _expected_cls=None, _owner_path=_owner_path)


# ---------------------------------------------------------------------------
# D2: Optional _target_ inference from parent field type
# ---------------------------------------------------------------------------

def _infer_target(
    _expected_cls: Optional[type],
    node: dict,
    path_for_error: str = "",
) -> Optional[str]:
    """Infer ``_target_`` from parent field type when not explicitly provided.

    Precedence (highest first):

    1. Parent class's ``__yaml_default_nested__`` ClassVar — explicit opt-in
       mapping of field names to alias strings.
    2. Parent field's declared type — only a single concrete non-abstract
       class is eligible.  ``Optional[X]`` unwraps to ``X``.
       ``Union[A, B]``, ``List[...]``, ABCs, and Protocols are NOT eligible.
    3. Return ``None`` — Hydra raises its normal missing-``_target_`` error.
    """
    if _expected_cls is None:
        return None

    # The node must look like a config dict (has non-Hydra keys) but lack _target_.
    # Pure scalar or empty dicts are not candidates for inference.
    if not isinstance(node, dict) or "_target_" in node:
        return None

    # Unwrap Optional[X] and check for Union/generic types.
    concrete = _unwrap_to_concrete(_expected_cls)
    if concrete is None:
        return None

    # For type-based inference: only single concrete non-abstract class.
    if _is_abstract_or_protocol(concrete):
        return None

    # Build the full import path for the concrete class.
    try:
        fqn = f"{concrete.__module__}.{concrete.__qualname__}"
        # Verify it's importable (no nested classes with dots in qualname).
        if concrete.__qualname__ != concrete.__name__:
            return None
        fqn = f"{concrete.__module__}.{concrete.__name__}"
    except (AttributeError, TypeError):
        return None

    return fqn


def _check_yaml_default_nested(
    parent_cls: Optional[type],
    field_name: str,
) -> Optional[str]:
    """Check parent class's ``__yaml_default_nested__`` for a field mapping.

    Returns the alias string if found, ``None`` otherwise.
    """
    if parent_cls is None:
        return None
    defaults = getattr(parent_cls, "__yaml_default_nested__", None)
    if defaults and isinstance(defaults, dict):
        return defaults.get(field_name)
    return None


def _unwrap_to_concrete(tp: Any) -> Optional[type]:
    """Unwrap ``Optional[X]`` to ``X``.  Return ``None`` for non-eligible types.

    Eligible: a single concrete class (not generic, not ABC, not Protocol).
    Not eligible: ``Union[A, B]``, ``List[...]``, ``Dict[...]``, ABCs, Protocols,
    ``None``, non-type objects, ``typing.Any``.
    """
    # Reject typing.Any explicitly (it's a type in Python 3.11+)
    if tp is typing.Any:
        return None

    origin = typing.get_origin(tp)

    # Handle Optional[X] = Union[X, None] and Union[A, B, ...]
    # Also handle PEP-604 syntax (X | None) which uses types.UnionType in 3.10+
    _is_union = origin is Union
    if not _is_union:
        try:
            import types as _types
            _is_union = isinstance(tp, _types.UnionType)
        except AttributeError:
            pass  # Python < 3.10, no UnionType
    if _is_union:
        args = [a for a in typing.get_args(tp) if a is not type(None)]
        if len(args) == 1:
            # Optional[X] → unwrap to X
            return _unwrap_to_concrete(args[0])
        # Union[A, B] → not eligible
        return None

    # Handle generic types like List[...], Dict[...], Set[...], etc.
    if origin is not None:
        return None

    # Must be an actual class
    if not isinstance(tp, type):
        return None

    return tp


def _is_abstract_or_protocol(cls: type) -> bool:
    """Return True if *cls* is abstract (has unimplemented abstract methods)
    or is a Protocol."""
    # Check for ABC with abstract methods
    if inspect.isabstract(cls):
        return True
    # Check for Protocol — runtime_checkable or not
    if _is_protocol(cls):
        return True
    return False


def _is_protocol(cls: type) -> bool:
    """Check if *cls* is a typing.Protocol subclass."""
    # Python 3.8+: Protocol classes have _is_protocol attribute
    return getattr(cls, "_is_protocol", False)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _import_target(target_path: str) -> Optional[type]:
    """Import and return the class/callable at *target_path*.

    Returns ``None`` on import failure — Hydra will give its own error later.
    """
    try:
        module_path, _, attr_name = target_path.rpartition(".")
        module = importlib.import_module(module_path)
        return getattr(module, attr_name, None)
    except (ImportError, ModuleNotFoundError):
        return None


def _accepted_param_names(cls: type) -> set[str]:
    """Return the set of ``__init__`` parameter names for *cls*, excluding ``self``."""
    try:
        params = inspect.signature(cls.__init__).parameters
    except (ValueError, TypeError):
        return set()
    return {name for name in params if name != "self"}


# ---------------------------------------------------------------------------
# Slot-based role defaults (consumed by step 1d in _walk)
#
# Each orchestrator class may declare a ``SLOT_DEFAULTS: dict[str, Any]``
# ClassVar mapping a slot path to a defaults object. The defaults object is
# duck-typed: ``_walk`` calls ``defaults_obj.apply_to(node, parent_node=...)``
# on the resolved leaf node. The actual ``InferencerTemplateDefaults`` class
# lives in ``AgentFoundation.common.inferencers.template_defaults`` — this
# module knows nothing about it, keeping ``python_utils`` independent of
# downstream packages.
#
# Slot path syntax:
#   "aggregator_inferencer"                       — direct child slot
#   "flow_configs.*.followup_inferencer"          — list-element wildcard
#
# Wrapping descent: a child node whose target class declares
# ``_TEMPLATE_TRANSPARENT_SLOTS`` (a list of slot names) is treated as a
# transparent wrapper; the parent's defaults pass through to those inner
# slots instead of being applied to the wrapper itself.
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=None)
def _collect_slot_defaults(cls: Any) -> Dict[str, Any]:
    """Walk MRO base→subclass; later (subclass) entries replace earlier per-slot.

    Atomic-bundle semantics: no per-key merge across MRO; the bundle IS the
    unit. Returns a flat ``{slot_path: defaults_obj}`` dict. Returns an empty
    dict for non-class targets (functions, callables) since only classes
    declare ``SLOT_DEFAULTS``.
    """
    mro = getattr(cls, "__mro__", None)
    if mro is None:
        return {}
    merged: Dict[str, Any] = {}
    for base in reversed(mro):
        decl = base.__dict__.get("SLOT_DEFAULTS")
        if decl:
            merged.update(decl)
    return merged


def _apply_at_path(
    current: Any,
    path_parts: List[str],
    defaults_obj: Any,
    parent_node: dict,
) -> None:
    """Walk ``path_parts`` through ``current``; at each terminal, apply
    ``defaults_obj`` (with wrapping descent if applicable).

    ``parent_node`` is the orchestrator node owning the slot — passed
    through to ``apply_to`` so conditional defaults can gate on parent flags.
    """
    if not path_parts:
        _apply_with_descent(current, defaults_obj, parent_node)
        return
    head, *rest = path_parts
    if head == "*":
        if isinstance(current, list):
            for item in current:
                _apply_at_path(item, rest, defaults_obj, parent_node)
    elif isinstance(current, dict) and head in current:
        _apply_at_path(current[head], rest, defaults_obj, parent_node)


def _apply_with_descent(
    node: Any,
    defaults_obj: Any,
    parent_node: dict,
) -> None:
    """Apply ``defaults_obj`` to ``node``. If ``node`` is a transparent
    wrapper (its target class declares ``_TEMPLATE_TRANSPARENT_SLOTS``),
    descend into each listed inner slot and apply there instead.
    """
    if not isinstance(node, dict):
        return
    transparent_slots: List[str] = []
    target = node.get("_target_")
    if isinstance(target, str):
        try:
            child_cls = _import_target(resolve_target(target))
        except Exception:
            child_cls = None
        if child_cls is not None:
            transparent_slots = list(
                getattr(child_cls, "_TEMPLATE_TRANSPARENT_SLOTS", []) or []
            )
    if transparent_slots:
        for slot in transparent_slots:
            inner = node.get(slot)
            if isinstance(inner, dict):
                _apply_with_descent(inner, defaults_obj, parent_node=node)
        # Don't apply to the wrapper itself — Hydra's _filter_attrs_keys
        # would drop unknown kwargs anyway, but skipping is cleaner.
        return
    if hasattr(defaults_obj, "apply_to"):
        defaults_obj.apply_to(node, parent_node=parent_node)


def _dispatch_alias(alias: str, primary_fqn: str, node: dict) -> str:
    """Structural dispatch: pick the right candidate class for a multi-class alias.

    When ``register_alias(..., alternatives=[...])`` was used, this function
    inspects the YAML node's user-supplied keys and each candidate's
    ``__init__`` signature to find unique differentiator fields.

    Returns the FQN of the selected candidate (may be the primary or an
    alternative).

    Raises ``AliasResolutionError`` when ≥2 candidates match.
    """
    alts = _alias_alternatives.get(alias, ())
    if not alts:
        return primary_fqn

    candidates = [primary_fqn, *alts]
    # Dedupe in case alternatives includes the primary FQN
    seen = set()
    deduped = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            deduped.append(c)
    candidates = deduped

    user_keys = {k for k in node.keys() if not k.startswith("_")}

    accepted = {}
    for fqn in candidates:
        cls = _import_target(fqn)
        if cls is None:
            _logger.warning(
                "alias %r: alternative %r could not be imported — skipping.",
                alias, fqn,
            )
            continue
        accepted[fqn] = _accepted_param_names(cls)

    # Compute per-candidate unique fields (params accepted only by that candidate).
    unique: dict[str, set[str]] = {}
    for fqn, params in accepted.items():
        other = set().union(*(p for f, p in accepted.items() if f != fqn))
        unique[fqn] = params - other

    matched = [fqn for fqn, uniq in unique.items() if uniq & user_keys]

    if len(matched) == 1:
        return matched[0]
    if not matched:
        _logger.info(
            "alias %r → default %s (no differentiator field). "
            "Variants differentiated by: %s",
            alias, primary_fqn,
            {fqn: sorted(uniq) for fqn, uniq in unique.items() if uniq},
        )
        return primary_fqn
    raise AliasResolutionError(
        f"Alias {alias!r} is ambiguous — candidates: {matched}"
    )


def _filter_attrs_keys(
    node: dict,
    cls: type,
    _factory_configs: Optional[List[tuple]] = None,
    _injectables: Optional[Dict[str, Any]] = None,
    _owner_path: str = "",
) -> None:
    """For ``@attrs`` classes, remove YAML keys that aren't valid ``__init__`` params.

    Uses ``inspect.signature(cls)`` which correctly handles:
    * Underscore stripping (``_secret_key`` → init param ``secret_key``)
    * Explicit aliases (``alias='reasoner'``)
    * ``init=False`` fields (excluded from signature)
    * ``kw_only=True`` fields
    * Inherited fields from the full MRO

    Also performs **auto-partial for factory fields**: attrs fields whose name
    ends with ``_factory`` get their ``_target_`` children auto-injected with
    ``_partial_: true``, so Hydra produces ``functools.partial`` callables
    that create fresh instances on each call.

    For ``_import_`` configs (tagged with ``_factory_: true``), the raw config
    is recorded in *_factory_configs* so the caller can replace the
    Hydra-created partial with an ``_ImportFactory`` after instantiation.

    Non-attrs classes (dataclasses, Pydantic, plain) are skipped — Hydra
    handles those natively.
    """
    try:
        import attr
    except ImportError:
        return

    if not attr.has(cls):
        return  # not an attrs class

    valid_params = set(inspect.signature(cls).parameters.keys())

    # Strip invalid keys.  Keys starting with "_" are preserved silently
    # UNLESS they match an attrs field name (e.g., _cache with init=False
    # should still be stripped).  Non-field _-prefixed keys serve as
    # injectable sources or OmegaConf interpolation anchors.
    all_field_names = {a.name for a in attr.fields(cls)}
    invalid = [
        k for k in node
        if k not in valid_params
        and k not in _HYDRA_KEYS
        and not (k.startswith("_") and k not in all_field_names)
    ]
    for k in invalid:
        _logger.warning(
            "Removing YAML key %r — not a valid __init__ param for %s. "
            "Valid params: %s",
            k,
            cls.__name__,
            sorted(valid_params),
        )
        del node[k]

    # Auto-partial / auto-factory for *_factory fields.
    # Auto-factory for *_factory fields: capture raw config and inject
    # _partial_: true so Hydra creates a functools.partial. Post-Hydra,
    # _apply_lazy_factory replaces the partial with a LazyConfigFactory
    # that deep-copies config and re-instantiates per call — producing
    # completely fresh sub-trees with NO shared inner instances.
    for a in attr.fields(cls):
        if not a.name.endswith("_factory") or a.name not in node:
            continue
        val = node[a.name]
        if not isinstance(val, dict):
            continue
        if "_target_" in val:
            # Single factory: worker_factory: {_target_: RovoChat, ...}
            raw = copy.deepcopy(val)
            if _FACTORY_MARKER in val:
                del raw[_FACTORY_MARKER]
                del val[_FACTORY_MARKER]
            if _factory_configs is not None:
                _factory_configs.append((_owner_path, a.name, None, raw, _injectables or {}))
            val["_partial_"] = True
        else:
            # Dict of factories: worker_factory: {type1: {_target_: ...}, ...}
            for k, v in list(val.items()):
                if k.startswith("_") and k not in _DATA_KEYS:
                    continue  # skip Hydra/injectable keys but NOT data keys like __default__
                if isinstance(v, dict) and "_target_" in v:
                    raw = copy.deepcopy(v)
                    if _FACTORY_MARKER in v:
                        del raw[_FACTORY_MARKER]
                        del v[_FACTORY_MARKER]
                    if _factory_configs is not None:
                        _factory_configs.append((_owner_path, a.name, k, raw, _injectables or {}))
                    v["_partial_"] = True
