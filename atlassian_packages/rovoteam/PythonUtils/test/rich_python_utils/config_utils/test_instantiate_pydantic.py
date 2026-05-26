"""Tests for Pydantic BaseModel instantiation."""

import pytest
from omegaconf import OmegaConf

from python_utils.config_utils import instantiate

from test_helpers import SimplePydantic, ValidatedPydantic, ParentAttrs

_MOD = "test_helpers"


class TestPydantic:
    def test_from_target(self):
        cfg = OmegaConf.create({"_target_": f"{_MOD}.SimplePydantic", "name": "hi", "value": 5})
        obj = instantiate(cfg)
        assert isinstance(obj, SimplePydantic)
        assert obj.name == "hi" and obj.value == 5

    def test_with_validators(self):
        cfg = OmegaConf.create({"_target_": f"{_MOD}.ValidatedPydantic", "score": 10})
        obj = instantiate(cfg)
        assert obj.score == 10

        cfg_bad = OmegaConf.create({"_target_": f"{_MOD}.ValidatedPydantic", "score": -1})
        with pytest.raises(Exception):  # Pydantic ValidationError
            instantiate(cfg_bad)

    def test_nested_in_attrs(self):
        cfg = OmegaConf.create({
            "_target_": f"{_MOD}.ParentAttrs",
            "child": {"_target_": f"{_MOD}.SimplePydantic", "name": "pyd", "value": 7},
            "label": "mixed",
        })
        obj = instantiate(cfg)
        assert isinstance(obj.child, SimplePydantic)
        assert obj.child.name == "pyd"
