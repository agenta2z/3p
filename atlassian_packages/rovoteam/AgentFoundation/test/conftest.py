"""Pytest configuration for AgentFoundation tests."""

import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent

# Add AgentFoundation src
sys.path.insert(0, str(_ROOT / "src"))

# Add PythonUtils src (dependency)
_PYUTILS_SRC = _ROOT.parent / "PythonUtils" / "src"
if _PYUTILS_SRC.exists():
    sys.path.insert(0, str(_PYUTILS_SRC))
