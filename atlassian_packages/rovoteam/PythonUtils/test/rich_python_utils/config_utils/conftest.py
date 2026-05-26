"""Shared fixtures for config_utils tests."""

import sys
from pathlib import Path

import pytest

# Make test_helpers importable by its simple name from this directory.
_THIS_DIR = Path(__file__).parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from python_utils.config_utils._registry import _reset_registry


@pytest.fixture(autouse=True)
def clean_registry():
    """Reset the global registry before and after each test."""
    _reset_registry()
    yield
    _reset_registry()
