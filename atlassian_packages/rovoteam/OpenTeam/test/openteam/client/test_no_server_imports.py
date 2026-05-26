"""CI preflight (I14): no module under ``openteam.client.*`` imports ``openteam.server.*``.

Enforces the architectural one-way import direction that pre-positions for a
future ``openteam-sdk`` PyPI extraction. The only allowed reverse is
``openteam.server._register`` importing schema constants from
``openteam.client.discovery``.

This is an AST scan — does NOT actually execute the imports.
"""
from __future__ import annotations

import ast
from pathlib import Path

import openteam.client

_CLIENT_PACKAGE_ROOT = Path(openteam.client.__file__).parent
_FORBIDDEN_PREFIX = "openteam.server"
_ALLOWED_EXCEPTIONS: set[str] = set()  # none — strictly enforced for client/


def _iter_client_py_files() -> list[Path]:
    return sorted(_CLIENT_PACKAGE_ROOT.rglob("*.py"))


def _imports_from_file(path: Path) -> set[str]:
    """Return the set of top-level module names imported by ``path``."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                out.add(node.module)
    return out


def test_client_package_exists():
    assert _CLIENT_PACKAGE_ROOT.is_dir(), (
        f"openteam.client package not found at {_CLIENT_PACKAGE_ROOT}"
    )


def test_no_client_module_imports_server():
    """Every .py under openteam.client must NOT import openteam.server.*."""
    offenders: list[tuple[Path, str]] = []
    for py_file in _iter_client_py_files():
        if py_file.name == "__pycache__":
            continue
        imported = _imports_from_file(py_file)
        for name in imported:
            if name == _FORBIDDEN_PREFIX or name.startswith(_FORBIDDEN_PREFIX + "."):
                if name in _ALLOWED_EXCEPTIONS:
                    continue
                offenders.append((py_file, name))
    assert not offenders, (
        "openteam.client modules MUST NOT import openteam.server.*; offenders:\n"
        + "\n".join(f"  {p}: imports {n}" for p, n in offenders)
    )
