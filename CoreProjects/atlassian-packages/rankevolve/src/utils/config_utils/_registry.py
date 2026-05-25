# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict

"""Target alias registry for YAML-based object instantiation.

Maps short alias names to full Python import paths, enabling clean YAML configs:
    _target_: ClaudeAPI  →  resolves to full dotted import path

Registry is module-level global state. Use _reset_registry() in test fixtures.
"""

from __future__ import annotations

_registry: dict[str, str] = {}  # alias -> "module.ClassName"
_registry_by_category: dict[str, dict[str, str]] = {}  # category -> {alias -> "module.ClassName"}


def _make_import_path(cls: type) -> str:
    """Build importable dotted path from a class object.

    Uses ``__name__`` (not ``__qualname__``) because Hydra's import resolution
    cannot handle nested-class paths like ``module.Outer.Inner``.
    """
    if cls.__qualname__ != cls.__name__:
        raise ValueError(
            f"Cannot register nested class {cls.__qualname__!r}. "
            f"Only top-level module classes are supported."
        )
    return f"{cls.__module__}.{cls.__name__}"


def register(alias: str, category: str = "default"):  # pyre-ignore[3]: decorator factory return type complex
    """Decorator that registers a class under *alias*.

    Usage::

        @register('ClaudeAPI', category='inferencer')
        @attrs
        class ClaudeApiInferencer(InferencerBase):
            ...

    The class itself is returned unchanged.
    """
    if not isinstance(alias, str):
        raise TypeError(
            f"@register must be called with a string alias: "
            f"@register('Foo'), not @register.  Got {type(alias).__name__}."
        )

    def decorator(cls: type) -> type:
        _do_register(cls, alias, category)
        return cls

    return decorator


def register_class(cls: type, alias: str, category: str = "default") -> None:
    """Imperative registration (same effect as the ``@register`` decorator)."""
    _do_register(cls, alias, category)


def register_alias(alias: str, import_path: str, category: str = "default") -> None:
    """String-only registration — no class import needed.

    Preferred for bulk registration to avoid import cascades::

        register_alias('ClaudeAPI', 'agent_foundation...ClaudeApiInferencer', 'inferencer')
    """
    if alias in _registry and _registry[alias] != import_path:
        raise ValueError(
            f"Alias {alias!r} already registered to {_registry[alias]!r}, "
            f"cannot re-register to {import_path!r}"
        )
    _registry[alias] = import_path
    _registry_by_category.setdefault(category, {})[alias] = import_path


def _do_register(cls: type, alias: str, category: str) -> None:
    """Shared implementation for ``register()`` and ``register_class()``."""
    register_alias(alias, _make_import_path(cls), category)


def resolve_target(target: str) -> str:
    """Resolve *target* to a full import path.

    Resolution order:
    1. If it starts with ``${`` — OmegaConf interpolation, pass through.
    2. If it's a registered alias — return the registered import path.
    3. If it contains a dot — assume it's already a full import path.
    4. Otherwise — raise ``KeyError`` with a helpful message.
    """
    if target.startswith("${"):
        return target  # OmegaConf interpolation — let Hydra resolve it
    if target in _registry:
        return _registry[target]
    if "." in target:
        return target  # already a full import path
    raise KeyError(
        f"Unknown target alias: {target!r}. "
        f"Registered: {sorted(_registry.keys())}. "
        f"Ensure the registration module has been imported "
        f"(e.g., 'import rankevolve.src.agentic_foundation.common.configs')."
    )


def list_registered(category: str | None = None) -> dict[str, str]:
    """Return ``{alias: import_path}``, optionally filtered by *category*.

    Always returns ``dict[str, str]`` regardless of arguments.
    """
    if category:
        return dict(_registry_by_category.get(category, {}))
    return dict(_registry)


def _reset_registry() -> None:
    """Clear all registrations.  **For test fixtures only.**"""
    _registry.clear()
    _registry_by_category.clear()
