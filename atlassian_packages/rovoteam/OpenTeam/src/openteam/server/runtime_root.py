"""Runtime root resolution (Round-8 / I21).

The CLI flag ``--runtime-root`` does NOT bypass
:func:`openteam.server.resources.tools._shared.workspace_allocator.find_runtime_root`.
It **sets** ``OPENTEAM_RUNTIME_DIR`` at parse time, then delegates to the
shared resolver. One source of truth: every code path that asks "what's
the runtime root?" eventually reads the env var via ``find_runtime_root``.

This eliminates the bug surface where a CLI flag could disagree with code
that reads the env var directly (same pattern Jupyter uses for
``--notebook-dir``).
"""
from __future__ import annotations

import enum
import os
from pathlib import Path
from typing import Optional, Union

# Re-export for callers that want resolution-only without env-var side effects.
from openteam.server.resources.tools._shared.workspace_allocator import find_runtime_root  # noqa: F401


class RuntimeRoot(str, enum.Enum):
    """Enum aliases for common runtime-root choices.

    Each enum value resolves to a deterministic ``Path``. No 4-tier fallback
    happens INSIDE these values — the fallback chain is reserved for
    :attr:`AUTO`.
    """

    AUTO = "auto"               # Use find_runtime_root() 4-tier resolution.
    REPO_ROOT = "repo-root"     # Force walk-up to a src/ ancestor; fail loud.
    USER_HOME = "user-home"     # ~/.openteam/_runtime (pip-install default).


def resolve_runtime_root(spec: Union[RuntimeRoot, str, None]) -> Path:
    """Resolve a ``--runtime-root`` spec to an absolute ``Path``.

    Accepts:
        - :class:`RuntimeRoot` enum value (preferred)
        - String matching an enum value: ``"auto"``, ``"repo-root"``, ``"user-home"``
        - String with absolute or relative path (relative resolved against CWD
          per Unix convention)
        - ``None`` (treated as :attr:`RuntimeRoot.AUTO`)

    Returns an absolute Path. Does NOT touch the filesystem (no mkdir).

    Raises:
        ValueError: ``REPO_ROOT`` chosen but no ``src/`` ancestor found.
    """
    if spec is None or spec == RuntimeRoot.AUTO or spec == "auto":
        return find_runtime_root()

    if spec == RuntimeRoot.USER_HOME or spec == "user-home":
        return Path.home() / ".openteam" / "_runtime"

    if spec == RuntimeRoot.REPO_ROOT or spec == "repo-root":
        # Walk up from __file__ once. NO 4-tier fallback — fail loud if not
        # found. The point of explicit repo-root is to surface the case where
        # a pip-installed user passes it accidentally.
        for ancestor in Path(__file__).resolve().parents:
            if ancestor.name == "src":
                return ancestor.parent / "_runtime"
        cwd = Path.cwd().resolve()
        for ancestor in [cwd, *cwd.parents]:
            if ancestor.name == "src":
                return ancestor.parent / "_runtime"
            if (ancestor / "src").is_dir() and (ancestor / "pyproject.toml").is_file():
                return ancestor / "_runtime"
        raise ValueError(
            "--runtime-root repo-root: no src/ ancestor found from __file__ or CWD. "
            "Use --runtime-root user-home, an absolute path, or omit the flag."
        )

    # Treat as a literal path (absolute or relative-to-CWD per Unix convention).
    return Path(spec).expanduser().resolve()


def apply_runtime_root(spec: Union[RuntimeRoot, str, None]) -> Path:
    """Resolve AND set ``OPENTEAM_RUNTIME_DIR`` (single source of truth — I21).

    Call this ONCE at CLI parse time. Subsequent ``find_runtime_root()``
    calls anywhere in the same process will return the same Path because
    they all consult the env var tier first.

    Returns the resolved absolute Path (for the caller's convenience).
    """
    resolved = resolve_runtime_root(spec)
    os.environ["OPENTEAM_RUNTIME_DIR"] = str(resolved)
    return resolved
