"""Fixtures for openteam.client tests — registry isolation."""
from __future__ import annotations

import pytest


@pytest.fixture
def isolated_registry(tmp_path, monkeypatch):
    """Redirect ``DISCOVERY_DIR()`` to a per-test tmp dir via env var.

    Tests use this fixture so concurrent CI workers can't see each other's
    registry files. Works because ``DISCOVERY_DIR()`` reads the env var on
    every call (not at import time).
    """
    reg = tmp_path / "registry"
    reg.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("OPENTEAM_REGISTRY_DIR", str(reg))
    return reg
