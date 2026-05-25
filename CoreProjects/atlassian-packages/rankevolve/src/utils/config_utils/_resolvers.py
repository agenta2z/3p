# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict

"""Custom OmegaConf resolvers for YAML config loading.

``_current_config_dir`` lives here (not in ``_instantiate.py``) to keep the
import graph one-directional: ``_instantiate.py`` → ``_resolvers.py``.
"""

from __future__ import annotations

from contextvars import ContextVar

# Set by load_config() before YAML loading; read by the ${path:...} resolver.
_current_config_dir: ContextVar[str] = ContextVar("_current_config_dir", default=".")

_registered: bool = False


def ensure_resolvers() -> None:
    """Register custom OmegaConf resolvers.  Idempotent — safe to call repeatedly."""
    global _registered
    if _registered:
        return

    from pathlib import Path

    from omegaconf import OmegaConf

    def _path_resolver(relative: str) -> str:
        """``${path:relative/dir}`` — resolve relative to the YAML file's parent."""
        base = Path(_current_config_dir.get())
        return str((base / relative).resolve())

    OmegaConf.register_new_resolver("path", _path_resolver, replace=True)
    _registered = True
