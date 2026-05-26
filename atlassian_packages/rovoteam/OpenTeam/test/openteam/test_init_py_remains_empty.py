"""TIER-1 CI pillar guard: critical __init__.py files must stay empty.

Bootstrap MUST run before any sibling-repo import. Code added to
openteam/__init__.py or openteam/server/__init__.py could transitively
import from agent_foundation BEFORE bootstrap runs, silently breaking
every console script.
"""
from __future__ import annotations

from pathlib import Path

_SRC_DIR = Path(__file__).resolve().parents[2] / "src"

_GUARDED_INIT_FILES = [
    "openteam/__init__.py",
    "openteam/server/__init__.py",
]


def _is_empty_or_whitespace(path: Path) -> bool:
    content = path.read_text(encoding="utf-8")
    return content.strip() == ""


class TestInitPyRemainsEmpty:
    def test_critical_init_py_files_empty(self):
        """Package-root __init__.py files that must stay empty for bootstrap safety."""
        violations = []
        for rel in _GUARDED_INIT_FILES:
            p = _SRC_DIR / rel
            if not p.exists():
                continue
            if not _is_empty_or_whitespace(p):
                violations.append(f"  {rel}: {p.read_text(encoding='utf-8')!r}")

        assert violations == [], (
            "These __init__.py files must be empty (bootstrap depends on it):\n"
            + "\n".join(violations)
        )
