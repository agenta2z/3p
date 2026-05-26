"""LazyConfigFactory — re-instantiate from stored config on each call.

The canonical mechanism for ``*_factory``-suffix attrs fields. Each call
deep-copies the captured raw config dict, re-applies parent injectables,
and re-runs ``instantiate()``, producing a completely fresh sub-tree with
NO shared inner instances across calls.

Subsumes the older ``_ImportFactory`` (which is now a deprecated alias).

Recognition contract: orchestrators detect factory-shaped callables via
``isinstance(x, (functools.partial, LazyConfigFactory))``. Both types
satisfy the "fully bound, call with no args" semantic.
"""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict, Optional

_logger = logging.getLogger(__name__)


class LazyConfigFactory:
    """Lazy factory that re-instantiates from stored YAML/dict config on each call.

    Each ``__call__`` deep-copies the captured config dict, re-applies
    shared parent injectables (e.g., ``_template_manager``), and re-runs
    ``instantiate()`` to produce a completely fresh sub-tree.

    Attributes:
        template_extra_feed: Public dict for ``_for_each_child_inferencer``
            duck-typing compatibility. When populated before calling the
            factory, the resulting instance receives the values via
            ``instance.template_extra_feed.update(...)``.
    """

    __slots__ = ("_config_dict", "_injectables", "template_extra_feed")

    def __init__(
        self,
        config_dict: Dict[str, Any],
        injectables: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not isinstance(config_dict, dict):
            raise TypeError(
                f"LazyConfigFactory.config_dict must be a dict, "
                f"got {type(config_dict).__name__}"
            )
        self._config_dict = config_dict
        self._injectables = injectables or {}
        self.template_extra_feed: dict = {}

    def __call__(self) -> Any:
        """Instantiate a fresh sub-tree from the captured config.

        Strict no-args signature. Passing positional or keyword args raises
        TypeError — factories are fully bound, and accepting kwargs would
        silently mask caller bugs.
        """
        from python_utils.config_utils._instantiate import instantiate
        from omegaconf import OmegaConf

        config = copy.deepcopy(self._config_dict)
        for k, v in self._injectables.items():
            injectable_key = f"_{k}"
            if injectable_key not in config:
                config[injectable_key] = copy.deepcopy(v)
        instance = instantiate(OmegaConf.create(config))
        if self.template_extra_feed and hasattr(instance, "template_extra_feed"):
            instance.template_extra_feed.update(self.template_extra_feed)
        return instance

    @property
    def target(self) -> str:
        """Return the ``_target_`` string from the captured config."""
        return self._config_dict.get("_target_", "<unknown>")

    def __repr__(self) -> str:
        return f"LazyConfigFactory(target={self.target!r})"
