"""Shared fixtures for OpenTeam tests."""
from __future__ import annotations

import pytest


@pytest.fixture
def standalone_workspace(tmp_path, monkeypatch):
    """Set OPENTEAM_RUNTIME_DIR to a hermetic per-test tmp dir.

    Use this fixture in any test that triggers workspace allocation
    to avoid polluting the repo's _runtime/ or leaking test artifacts
    into test/.../_runtime/ directories.
    """
    monkeypatch.setenv("OPENTEAM_RUNTIME_DIR", str(tmp_path))
    return tmp_path
