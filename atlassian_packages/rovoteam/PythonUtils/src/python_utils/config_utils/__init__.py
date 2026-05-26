"""config_utils — YAML-based object instantiation with Hydra + target alias registry.

Public API
----------
Config loading::

    cfg = load_config("path/to/config.yaml", overrides={"key": "value"})
    cfg = merge_configs(base_cfg, override_cfg)

Instantiation::

    obj = instantiate(cfg)  # resolves aliases, filters attrs keys, calls Hydra

Registry — decorator::

    @register('ClaudeAPI', category='inferencer')
    class ClaudeApiInferencer: ...

Registry — imperative::

    register_class(ClaudeApiInferencer, 'ClaudeAPI', category='inferencer')

Registry — string-only (no class import needed)::

    register_alias('ClaudeAPI', 'module.path.ClaudeApiInferencer', 'inferencer')

Discoverability::

    list_registered()                  # all aliases
    list_registered('inferencer')      # filtered by category
    resolve_target('ClaudeAPI')        # alias → full import path
"""

from python_utils.config_utils._registry import (
    AliasResolutionError,
    MissingTargetError,
    RegistryError,
    register,
    register_alias,
    register_class,
    resolve_target,
    list_registered,
    _reset_registry,
)

# Lazy — only imported when called, not at module load time.
# This keeps the package usable without hydra/omegaconf installed.


def load_config(path, overrides=None):
    from python_utils.config_utils._instantiate import load_config as _load
    return _load(path, overrides)


def merge_configs(*configs):
    from python_utils.config_utils._instantiate import merge_configs as _merge
    return _merge(*configs)


def instantiate(config, _convert_="all", **kwargs):
    from python_utils.config_utils._instantiate import instantiate as _inst
    return _inst(config, _convert_=_convert_, **kwargs)


__all__ = [
    # Config loading
    "load_config",
    "merge_configs",
    # Instantiation
    "instantiate",
    # Registry
    "register",
    "register_alias",
    "register_class",
    "resolve_target",
    "list_registered",
    "_reset_registry",
    # Exceptions
    "AliasResolutionError",
    "MissingTargetError",
    "RegistryError",
]
