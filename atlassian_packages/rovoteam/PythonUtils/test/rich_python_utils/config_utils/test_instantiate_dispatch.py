"""Tests for D1 structural dispatch: multi-class alias resolution.

Registers a synthetic alias with two candidate classes having disjoint unique
fields, then verifies dispatch selects the correct candidate based on which
unique fields appear in the YAML config node.
"""

import logging

import pytest
from omegaconf import OmegaConf

from python_utils.config_utils import (
    AliasResolutionError,
    instantiate,
    register_alias,
)


# ---------------------------------------------------------------------------
# Synthetic candidate classes with disjoint unique fields
# ---------------------------------------------------------------------------

class CandidateA:
    """Has unique field ``alpha`` (not on B) plus shared ``name``."""

    def __init__(self, name: str = "", alpha: str = ""):
        self.name = name
        self.alpha = alpha


class CandidateB:
    """Has unique field ``beta`` (not on A) plus shared ``name``."""

    def __init__(self, name: str = "", beta: str = ""):
        self.name = name
        self.beta = beta


_MOD = __name__  # test_instantiate_dispatch (importable via conftest sys.path)
_FQN_A = f"{_MOD}.CandidateA"
_FQN_B = f"{_MOD}.CandidateB"


def _register_multi_alias():
    """Register alias 'Multi' with CandidateA as primary and CandidateB as alternative."""
    register_alias("Multi", _FQN_A, alternatives=[_FQN_B])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDispatchSelectsCandidateA:
    def test_alpha_field_dispatches_to_a(self):
        _register_multi_alias()
        cfg = OmegaConf.create({
            "_target_": "Multi",
            "name": "test",
            "alpha": "unique-to-a",
        })
        obj = instantiate(cfg)
        assert isinstance(obj, CandidateA)
        assert obj.name == "test"
        assert obj.alpha == "unique-to-a"


class TestDispatchSelectsCandidateB:
    def test_beta_field_dispatches_to_b(self):
        _register_multi_alias()
        cfg = OmegaConf.create({
            "_target_": "Multi",
            "name": "test",
            "beta": "unique-to-b",
        })
        obj = instantiate(cfg)
        assert isinstance(obj, CandidateB)
        assert obj.name == "test"
        assert obj.beta == "unique-to-b"


class TestDispatchDefaultsOnNoMatch:
    def test_shared_fields_only_defaults_to_primary(self, caplog):
        _register_multi_alias()
        cfg = OmegaConf.create({
            "_target_": "Multi",
            "name": "shared-only",
        })
        with caplog.at_level(logging.INFO):
            obj = instantiate(cfg)
        assert isinstance(obj, CandidateA)  # primary = default
        assert obj.name == "shared-only"
        assert "default" in caplog.text or "no differentiator" in caplog.text


class TestDispatchAmbiguousRaises:
    def test_both_unique_fields_raises(self):
        _register_multi_alias()
        cfg = OmegaConf.create({
            "_target_": "Multi",
            "name": "ambiguous",
            "alpha": "a-val",
            "beta": "b-val",
        })
        with pytest.raises(AliasResolutionError, match="ambiguous"):
            instantiate(cfg)


class TestNoAlternativesPassthrough:
    """Alias without alternatives behaves exactly as before."""

    def test_plain_alias_no_dispatch(self):
        register_alias("PlainA", _FQN_A)
        cfg = OmegaConf.create({
            "_target_": "PlainA",
            "name": "plain",
        })
        obj = instantiate(cfg)
        assert isinstance(obj, CandidateA)
        assert obj.name == "plain"
