# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict

"""Config loading, alias resolution, attrs preprocessing, and Hydra instantiation.

This module is the core of the config_utils package.  The public functions are
``load_config``, ``merge_configs``, and ``instantiate``.
"""

from __future__ import annotations

import copy
import importlib
import inspect
import logging
from pathlib import Path
from typing import Any

from rankevolve.src.utils.config_utils._registry import (
    _registry,
    resolve_target,
)
from rankevolve.src.utils.config_utils._resolvers import (
    _current_config_dir,
    ensure_resolvers,
)

_logger: logging.Logger = logging.getLogger(__name__)

_IMPORT_KEY = "_import_"
_IMPORT_SHARED_KEY = "_import_shared_"
_FACTORY_MARKER = "_factory_"


class _ImportFactory:
    """Lazy factory: re-instantiates from resolved config on each call.

    Created by ``_filter_attrs_keys()`` for ``_import_`` configs inside
    ``*_factory`` fields.  Exposes ``template_extra_feed`` dict so that
    ``_for_each_child_inferencer`` duck-typing picks it up for propagation.
    """

    def __init__(self, config_dict: dict[str, Any], injectables: dict[str, Any] | None = None) -> None:
        self._config_dict = config_dict
        self._injectables = injectables or {}
        self.template_extra_feed: dict[str, Any] = {}

    def __call__(self, **_kwargs: Any) -> Any:
        from omegaconf import OmegaConf

        config = copy.deepcopy(self._config_dict)
        for k, v in self._injectables.items():
            injectable_key = f"_{k}"
            if injectable_key in config:
                config[injectable_key] = copy.deepcopy(v)
        instance = instantiate(OmegaConf.create(config))
        if self.template_extra_feed and hasattr(instance, "template_extra_feed"):
            instance.template_extra_feed.update(self.template_extra_feed)
        return instance

    def __repr__(self) -> str:
        target = self._config_dict.get("_target_", "?")
        return f"_ImportFactory({target})"


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge *overrides* into *base*, returning a new dict."""
    result = dict(base)
    for k, v in overrides.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def _resolve_import_(node: Any, current_yaml_dir: Path) -> Any:
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

def load_config(path: str, overrides: dict[str, Any] | None = None) -> Any:
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
        cfg = OmegaConf.create(container)
        if overrides:
            # Convert dotted override keys to nested dicts so that
            # OmegaConf.merge treats them as nested paths.
            # e.g., {"workspace.root": "/tmp"} → {"workspace": {"root": "/tmp"}}
            nested_overrides: dict[str, Any] = {}
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


def merge_configs(*configs: Any) -> Any:
    """Merge multiple configs (dicts or ``DictConfig``).  Later configs win."""
    from omegaconf import OmegaConf

    return OmegaConf.merge(*configs)


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------

def instantiate(config: Any, _convert_: str = "all", **kwargs: Any) -> Any:
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
    for field_name, child_key, raw_config, injectables in factory_configs:
        _apply_import_factory(result, field_name, child_key, raw_config, injectables)
    return result


def _apply_import_factory(
    obj: Any,
    field_name: str,
    child_key: str | None,
    raw_config: dict[str, Any],
    injectables: dict[str, Any] | None = None,
) -> None:
    """Replace a Hydra-created partial with an ``_ImportFactory``."""
    container = getattr(obj, field_name, None)
    if container is None:
        return
    factory = _ImportFactory(raw_config, injectables=injectables)
    if child_key is None:
        setattr(obj, field_name, factory)
    elif isinstance(container, dict):
        container[child_key] = factory


# ---------------------------------------------------------------------------
# Internal: single-pass tree walk
# ---------------------------------------------------------------------------

def _resolve_and_preprocess(config: Any) -> tuple[Any, list[tuple[Any, ...]]]:
    """Convert to plain dict, walk the tree, convert back to ``DictConfig``.

    Returns ``(DictConfig, factory_configs)`` where *factory_configs* is a
    list of ``(field_name, child_key, raw_config)`` tuples recorded by
    ``_filter_attrs_keys`` for ``_import_`` entries inside ``*_factory``
    fields.  The caller replaces the corresponding Hydra-created partials
    with ``_ImportFactory`` objects after instantiation.
    """
    from omegaconf import OmegaConf

    raw = OmegaConf.to_container(config, resolve=False)
    factory_configs: list[tuple[Any, ...]] = []
    _walk(raw, _factory_configs=factory_configs)
    return OmegaConf.create(raw), factory_configs


_HYDRA_KEYS = {"_target_", "_recursive_", "_convert_", "_partial_", "_args_"}
# Keys starting with _ that are data (not injection sources) — preserved as-is.
_DATA_KEYS = {"__default__"}


def _walk(
    node: Any,
    _injectables: dict[str, Any] | None = None,
    _factory_configs: list[tuple[Any, ...]] | None = None,
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

    3. **Recursion** — recurse into all values with inherited injectables.
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
        cls = None
        if "_target_" in node and isinstance(node["_target_"], str):
            target = node["_target_"]
            if not target.startswith("${"):
                node["_target_"] = resolve_target(target)
                cls = _import_target(node["_target_"])
                if cls is not None:
                    _filter_attrs_keys(node, cls, _factory_configs, local_injectables)

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

        # 2. String shorthand expansion
        for key, val in list(node.items()):
            if key.startswith("_"):
                continue  # skip Hydra keys (_target_, _recursive_, etc.)
            if isinstance(val, str) and val in _registry:
                node[key] = {"_target_": resolve_target(val)}

        # 3. Recurse (injectables propagate to children)
        for v in node.values():
            _walk(v, _injectables=local_injectables, _factory_configs=_factory_configs)

    elif isinstance(node, list):
        for item in node:
            _walk(item, _injectables=_injectables, _factory_configs=_factory_configs)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _import_target(target_path: str) -> type | None:
    """Import and return the class/callable at *target_path*.

    Returns ``None`` on import failure — Hydra will give its own error later.
    """
    try:
        module_path, _, attr_name = target_path.rpartition(".")
        module = importlib.import_module(module_path)
        return getattr(module, attr_name, None)
    except (ImportError, ModuleNotFoundError):
        return None


def _filter_attrs_keys(
    node: dict[str, Any],
    cls: type,
    _factory_configs: list[tuple[Any, ...]] | None = None,
    _injectables: dict[str, Any] | None = None,
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
    # Dicts tagged with _factory_ (from _import_) get the marker stripped,
    # _partial_: true injected (so Hydra creates a functools.partial), and
    # the raw config recorded for post-Hydra replacement with _ImportFactory.
    # Untagged dicts simply get _partial_: true.
    for a in attr.fields(cls):
        if not a.name.endswith("_factory") or a.name not in node:
            continue
        val = node[a.name]
        if not isinstance(val, dict):
            continue
        if "_target_" in val:
            # Single factory: worker_factory: {_target_: RovoChat, ...}
            if _FACTORY_MARKER in val:
                raw = dict(val)
                del raw[_FACTORY_MARKER]
                del val[_FACTORY_MARKER]
                if _factory_configs is not None:
                    _factory_configs.append((a.name, None, raw, _injectables or {}))
            val["_partial_"] = True
        else:
            # Dict of factories: worker_factory: {type1: {_target_: ...}, ...}
            for k, v in list(val.items()):
                if k.startswith("_") and k not in _DATA_KEYS:
                    continue  # skip Hydra/injectable keys but NOT data keys like __default__
                if isinstance(v, dict) and "_target_" in v:
                    if _FACTORY_MARKER in v:
                        raw = dict(v)
                        del raw[_FACTORY_MARKER]
                        del v[_FACTORY_MARKER]
                        if _factory_configs is not None:
                            _factory_configs.append((a.name, k, raw, _injectables or {}))
                    v["_partial_"] = True
