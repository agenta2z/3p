"""Custom OmegaConf resolvers for YAML config loading.

``_current_config_dir`` lives here (not in ``_instantiate.py``) to keep the
import graph one-directional: ``_instantiate.py`` → ``_resolvers.py``.
"""

from __future__ import annotations

import importlib
from contextvars import ContextVar
from pathlib import Path

# Set by load_config() before YAML loading; read by the ${path:...} resolver.
_current_config_dir: ContextVar[str] = ContextVar("_current_config_dir", default=".")

_registered: bool = False


def _modpath_resolver(dotted: str) -> str:
    """``${modpath:agent_foundation.resources.prompt_templates}``
    → absolute path to that package's directory on disk.

    Splits on '.', imports all-but-last as a module, joins the last
    segment as a subdirectory of the module's parent.
    """
    parts = dotted.rsplit(".", 1)
    if len(parts) == 2:
        module_path, leaf = parts
        mod = importlib.import_module(module_path)
        return str(Path(mod.__file__).parent / leaf)
    else:
        mod = importlib.import_module(dotted)
        return str(Path(mod.__file__).parent)


def ensure_resolvers() -> None:
    """Register custom OmegaConf resolvers.  Idempotent — safe to call repeatedly."""
    global _registered
    if _registered:
        return

    from omegaconf import OmegaConf

    def _path_resolver(relative: str) -> str:
        """``${path:relative/dir}`` — resolve relative to the YAML file's parent."""
        base = Path(_current_config_dir.get())
        return str((base / relative).resolve())

    OmegaConf.register_new_resolver("path", _path_resolver, replace=True)
    OmegaConf.register_new_resolver("modpath", _modpath_resolver, replace=True)
    _registered = True
