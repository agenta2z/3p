"""Importable test classes for config_utils unit tests.

Hydra's ``_target_`` needs importable dotted paths, so these MUST live in a
regular Python module — not in ``conftest.py`` (which pytest doesn't make
importable).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from attr import attrib, attrs


# ---------------------------------------------------------------------------
# attrs test classes
# ---------------------------------------------------------------------------

@attrs
class SimpleAttrs:
    name: str = attrib(default="")
    count: int = attrib(default=0)


@attrs
class AttrsWithUnderscore:
    """``_secret`` → init param is ``secret`` (attrs auto-strips leading ``_``)."""
    _secret: str = attrib(default=None)


@attrs
class AttrsWithAlias:
    """``_internal`` with explicit ``alias='public_name'``."""
    _internal: str = attrib(default=None, alias="public_name")


@attrs
class AttrsWithInitFalse:
    """``_cache`` has ``init=False`` — should be filtered from YAML."""
    name: str = attrib(default="")
    _cache: dict = attrib(factory=dict, init=False)


@attrs(slots=True)
class SlottedAttrs:
    value: float = attrib(default=0.0)


@attrs(slots=False)
class UnslottedAttrs:
    value: float = attrib(default=0.0)


@attrs
class AttrsWithConverter:
    data: dict = attrib(default=None, converter=lambda x: dict(x) if x else {})


@attrs
class AttrsWithPostInit:
    name: str = attrib(default="")
    _computed: str = attrib(init=False, default="")

    def __attrs_post_init__(self):
        self._computed = f"computed_{self.name}"


@attrs
class AttrsKwOnly:
    name: str = attrib(default="", kw_only=True)
    value: int = attrib(default=0, kw_only=True)


@attrs
class ParentAttrs:
    """Parent with a nested attrs child."""
    child: Optional[Any] = attrib(default=None)
    label: str = attrib(default="")


@attrs
class AttrsWithCallable:
    """Has a callable field that defaults to None — should be safe to omit."""
    name: str = attrib(default="")
    processor: Optional[Any] = attrib(default=None)


@attrs
class AttrsWithFactory:
    """Has a ``*_factory`` field for testing _ImportFactory / auto-partial."""
    name: str = attrib(default="")
    worker_factory: Any = attrib(default=None)


@attrs
class InnerWorker:
    """Simple worker instantiated by factory tests."""
    model: str = attrib(default="default")
    child: Any = attrib(default=None)


# ---------------------------------------------------------------------------
# dataclass test classes
# ---------------------------------------------------------------------------

@dataclass
class SimpleDataclass:
    x: int = 0
    y: int = 0


@dataclass
class DataclassWithNested:
    point: Optional[Any] = None
    label: str = ""


# ---------------------------------------------------------------------------
# Plain class
# ---------------------------------------------------------------------------

class PlainClass:
    def __init__(self, name: str = "", value: int = 0):
        self.name = name
        self.value = value


# ---------------------------------------------------------------------------
# Factory function (callable target)
# ---------------------------------------------------------------------------

def create_simple(name: str = "default", count: int = 1) -> SimpleAttrs:
    return SimpleAttrs(name=name, count=count)


# ---------------------------------------------------------------------------
# Pydantic test classes
# ---------------------------------------------------------------------------

try:
    from pydantic import BaseModel, field_validator

    class SimplePydantic(BaseModel):
        name: str = ""
        value: int = 0

    class ValidatedPydantic(BaseModel):
        score: int = 0

        @field_validator("score")
        @classmethod
        def score_must_be_positive(cls, v):
            if v < 0:
                raise ValueError("score must be non-negative")
            return v

except ImportError:
    pass  # Pydantic not installed — tests will be skipped
