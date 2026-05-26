"""Test-local conftest — ensures `test/openteam` (the demo namespace) wins
over `src/openteam` (the production namespace) when running pytest, so
`openteam.use_cases.proposal_implementation` resolves correctly.
"""

from __future__ import annotations

import sys
from pathlib import Path

_TEST_ROOT = Path(__file__).resolve().parents[3]   # .../OpenTeam/test
# Ensure test/ wins regardless of pre-existing entries (insert at index 0).
while str(_TEST_ROOT) in sys.path:
    sys.path.remove(str(_TEST_ROOT))
sys.path.insert(0, str(_TEST_ROOT))

# Drop any cached `openteam` modules from the src/ tree that might have been
# imported by the root conftest. This forces re-import from test/openteam.
for _mod in list(sys.modules):
    if _mod == "openteam" or _mod.startswith("openteam."):
        # Only purge if it came from src/, not test/
        m = sys.modules[_mod]
        f = getattr(m, "__file__", None) or ""
        if "/OpenTeam/src/" in f:
            del sys.modules[_mod]
