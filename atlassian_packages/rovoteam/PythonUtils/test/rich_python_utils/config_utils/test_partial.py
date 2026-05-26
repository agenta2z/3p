"""Tests for _partial_: true instantiation."""

import functools

from omegaconf import OmegaConf

from python_utils.config_utils import instantiate

from test_helpers import SimpleAttrs

_MOD = "test_helpers"


class TestPartial:
    def test_partial_returns_functools_partial(self):
        cfg = OmegaConf.create({
            "_target_": f"{_MOD}.SimpleAttrs",
            "_partial_": True,
            "name": "baked",
        })
        result = instantiate(cfg)
        assert isinstance(result, functools.partial)

    def test_partial_call_with_remaining_args(self):
        cfg = OmegaConf.create({
            "_target_": f"{_MOD}.SimpleAttrs",
            "_partial_": True,
            "name": "baked",
        })
        factory = instantiate(cfg)
        obj = factory(count=42)
        assert isinstance(obj, SimpleAttrs)
        assert obj.name == "baked" and obj.count == 42

    def test_partial_preserves_provided_args(self):
        cfg = OmegaConf.create({
            "_target_": f"{_MOD}.SimpleAttrs",
            "_partial_": True,
            "name": "fixed",
            "count": 10,
        })
        factory = instantiate(cfg)
        obj = factory()  # all args provided via partial
        assert obj.name == "fixed" and obj.count == 10
