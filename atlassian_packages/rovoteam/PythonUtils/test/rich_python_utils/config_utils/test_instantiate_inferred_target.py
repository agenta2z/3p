"""Tests for D2: Optional _target_ via parent-type inference.

Verifies that nested YAML blocks without _target_ can infer their target
from the parent field's declared type or the parent class's
__yaml_default_nested__ ClassVar.
"""

import abc
from typing import ClassVar, Optional, Union

import pytest
from omegaconf import OmegaConf

from python_utils.config_utils import (
    MissingTargetError,
    instantiate,
    register_alias,
)


# ---------------------------------------------------------------------------
# Synthetic classes for testing D2 inference
# ---------------------------------------------------------------------------


class ConcreteChild:
    """A simple concrete class used as a field type."""

    def __init__(self, value: str = "default"):
        self.value = value


class AnotherConcrete:
    """Another concrete class — used to test Union ambiguity."""

    def __init__(self, value: str = "other"):
        self.value = value


class AbstractBase(abc.ABC):
    """An abstract base class — not eligible for type-based inference."""

    @abc.abstractmethod
    def do_something(self) -> None: ...


class ConcreteFromABC(AbstractBase):
    """Concrete subclass of AbstractBase."""

    def __init__(self, value: str = "abc-child"):
        self.value = value

    def do_something(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Parent classes with various field type annotations
# ---------------------------------------------------------------------------


class ParentWithConcreteField:
    """Parent whose field is typed as a single concrete class."""

    def __init__(self, child: ConcreteChild = None):
        self.child = child


class ParentWithOptionalField:
    """Parent whose field is Optional[ConcreteChild]."""

    def __init__(self, child: Optional[ConcreteChild] = None):
        self.child = child


class ParentWithUnionField:
    """Parent whose field is Union[ConcreteChild, AnotherConcrete]."""

    def __init__(self, child: Union[ConcreteChild, AnotherConcrete] = None):
        self.child = child


class ParentWithABCField:
    """Parent whose field is typed as an ABC."""

    def __init__(self, child: AbstractBase = None):
        self.child = child


class ParentWithYamlDefaultNested:
    """Parent with __yaml_default_nested__ mapping."""

    __yaml_default_nested__: ClassVar[dict[str, str]] = {
        "child": "NestedAlias",
    }

    def __init__(self, child: AbstractBase = None):
        """Note: field type is ABC, but __yaml_default_nested__ takes precedence."""
        self.child = child


class ParentWithBothInferenceOptions:
    """Parent with __yaml_default_nested__ AND a concrete field type.

    __yaml_default_nested__ should win over type-based inference.
    """

    __yaml_default_nested__: ClassVar[dict[str, str]] = {
        "child": "NestedAlias",
    }

    def __init__(self, child: ConcreteChild = None):
        self.child = child


_MOD = __name__


def _fqn(cls: type) -> str:
    return f"{_MOD}.{cls.__name__}"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestYamlDefaultNestedWinsOverTypeBased:
    """__yaml_default_nested__ has highest precedence over type-based inference."""

    def test_nested_alias_wins(self):
        # Register the parent and the nested alias target
        register_alias("ParentBoth", _fqn(ParentWithBothInferenceOptions))
        register_alias("NestedAlias", _fqn(ConcreteChild))

        cfg = OmegaConf.create({
            "_target_": "ParentBoth",
            "child": {
                # No _target_ — should be inferred via __yaml_default_nested__
                "value": "from-nested-alias",
            },
        })
        obj = instantiate(cfg)
        assert isinstance(obj, ParentWithBothInferenceOptions)
        assert isinstance(obj.child, ConcreteChild)
        assert obj.child.value == "from-nested-alias"


class TestConcreteTypedFieldInferred:
    """A field typed as a single concrete class gets _target_ inferred."""

    def test_concrete_field_inferred(self):
        register_alias("ParentConcrete", _fqn(ParentWithConcreteField))

        cfg = OmegaConf.create({
            "_target_": "ParentConcrete",
            "child": {
                # No _target_ — should be inferred from field type ConcreteChild
                "value": "inferred",
            },
        })
        obj = instantiate(cfg)
        assert isinstance(obj, ParentWithConcreteField)
        assert isinstance(obj.child, ConcreteChild)
        assert obj.child.value == "inferred"


class TestOptionalUnwrapsAndInfers:
    """Optional[ConcreteChild] unwraps to ConcreteChild and infers."""

    def test_optional_unwraps(self):
        register_alias("ParentOptional", _fqn(ParentWithOptionalField))

        cfg = OmegaConf.create({
            "_target_": "ParentOptional",
            "child": {
                "value": "optional-unwrapped",
            },
        })
        obj = instantiate(cfg)
        assert isinstance(obj, ParentWithOptionalField)
        assert isinstance(obj.child, ConcreteChild)
        assert obj.child.value == "optional-unwrapped"


class TestUnionNotEligible:
    """Union[A, B] is not eligible for type-based inference."""

    def test_union_not_inferred(self):
        register_alias("ParentUnion", _fqn(ParentWithUnionField))

        cfg = OmegaConf.create({
            "_target_": "ParentUnion",
            "child": {
                "value": "ambiguous",
            },
        })
        # Without _target_ and Union type, Hydra should fail because
        # _target_ cannot be inferred. The child dict will be passed
        # as a plain dict (no _target_ injected).
        obj = instantiate(cfg)
        # Hydra passes the child as a plain dict when no _target_ is present
        assert isinstance(obj.child, dict)
        assert obj.child["value"] == "ambiguous"


class TestABCFieldNotEligible:
    """ABC-typed field is not eligible for type-based inference."""

    def test_abc_not_inferred(self):
        register_alias("ParentABC", _fqn(ParentWithABCField))

        cfg = OmegaConf.create({
            "_target_": "ParentABC",
            "child": {
                "value": "abc-typed",
            },
        })
        # ABC type → not eligible for inference → child stays as plain dict
        obj = instantiate(cfg)
        assert isinstance(obj.child, dict)
        assert obj.child["value"] == "abc-typed"


class TestExplicitTargetFastPath:
    """When _target_ is already present, inference is skipped entirely."""

    def test_explicit_target_unchanged(self):
        register_alias("ParentConcrete", _fqn(ParentWithConcreteField))
        register_alias("AnotherAlias", _fqn(AnotherConcrete))

        cfg = OmegaConf.create({
            "_target_": "ParentConcrete",
            "child": {
                "_target_": "AnotherAlias",  # Explicit — should NOT be overridden
                "value": "explicit",
            },
        })
        obj = instantiate(cfg)
        assert isinstance(obj, ParentWithConcreteField)
        # Even though field type is ConcreteChild, explicit _target_ wins
        assert isinstance(obj.child, AnotherConcrete)
        assert obj.child.value == "explicit"


class TestYamlDefaultNestedWithABCField:
    """__yaml_default_nested__ works even when the field type is an ABC."""

    def test_nested_default_overrides_abc_type(self):
        register_alias("ParentNested", _fqn(ParentWithYamlDefaultNested))
        register_alias("NestedAlias", _fqn(ConcreteFromABC))

        cfg = OmegaConf.create({
            "_target_": "ParentNested",
            "child": {
                "value": "nested-override",
            },
        })
        obj = instantiate(cfg)
        assert isinstance(obj, ParentWithYamlDefaultNested)
        assert isinstance(obj.child, ConcreteFromABC)
        assert obj.child.value == "nested-override"
