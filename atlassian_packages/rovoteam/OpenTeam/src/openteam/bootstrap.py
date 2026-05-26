"""Ensure sibling repos AgentFoundation and PythonUtils are importable.

Both sibling repos lack pyproject.toml, so we cannot resolve them via pip;
we inject their src/ directories onto sys.path. Idempotent -- safe to call
repeatedly.

Callsites (all explicit):
  - openteam.mcp_server.cli       (entry: openteam-mcp, strict=True)
  - openteam.server.resources.tools.{task,create_role,role_setup,project_onboarding}.cli
  - conftest.py                   (root)
  - openteam.server.run_server    (replaces inline block)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_SIBLINGS = ("AgentFoundation/src", "PythonUtils/src")


def _find_siblings_root() -> Path | None:
    """Resolve the directory that contains AgentFoundation/ and PythonUtils/.

    Priority:
      1. OPENTEAM_SIBLINGS_ROOT env var.
      2. Walk up from the openteam package looking for the canonical layout.
      3. Return None.
    """
    env_override = os.environ.get("OPENTEAM_SIBLINGS_ROOT")
    if env_override:
        return Path(env_override).resolve()

    here = Path(__file__).resolve()
    openteam_src = here.parent.parent  # .../OpenTeam/src
    cursor = openteam_src.parent       # .../OpenTeam
    for _ in range(5):
        cursor = cursor.parent
        if (cursor / "AgentFoundation" / "src").is_dir() and \
           (cursor / "PythonUtils" / "src").is_dir():
            return cursor
    return None


def ensure_siblings_on_path(*, strict: bool = False) -> list[Path]:
    """Insert OpenTeam/src and each existing sibling src/ onto sys.path.

    Returns the list of paths actually inserted. Idempotent.

    strict=True raises FileNotFoundError instead of warning on failure.
    Use strict=True in production entry points (e.g. openteam-mcp).
    """
    import logging
    _logger = logging.getLogger(__name__)

    here = Path(__file__).resolve()
    openteam_src = here.parent.parent
    siblings_root = _find_siblings_root()

    inserted: list[Path] = []

    if openteam_src.is_dir() and str(openteam_src) not in sys.path:
        sys.path.insert(0, str(openteam_src))
        inserted.append(openteam_src)

    if siblings_root is None:
        msg = (
            "openteam.bootstrap: could not locate AgentFoundation/src + "
            "PythonUtils/src by walking up from %s. Set "
            "OPENTEAM_SIBLINGS_ROOT to the directory containing both "
            "sibling repos."
        )
        if strict:
            raise FileNotFoundError(msg % openteam_src)
        _logger.warning(msg, openteam_src)
        return inserted

    missing: list[str] = []
    for sib in _SIBLINGS:
        candidate = siblings_root / sib
        if not candidate.is_dir():
            missing.append(str(candidate))
            continue
        s = str(candidate)
        if s not in sys.path:
            sys.path.insert(0, s)
            inserted.append(candidate)

    if missing:
        msg = (
            "openteam.bootstrap: siblings_root=%s but the following "
            "expected dirs are missing: %s. Subsequent openteam.server.* "
            "imports may fail with ImportError."
        )
        if strict:
            raise FileNotFoundError(msg % (siblings_root, missing))
        _logger.warning(msg, siblings_root, missing)

    return inserted
