"""Root conftest.py — delegates to openteam.bootstrap for sibling sys.path."""
import sys
from pathlib import Path

# Step 1: openteam itself must be importable so we can call bootstrap.
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Step 2: bootstrap adds AgentFoundation/src + PythonUtils/src.
from openteam.bootstrap import ensure_siblings_on_path  # noqa: E402
ensure_siblings_on_path()
