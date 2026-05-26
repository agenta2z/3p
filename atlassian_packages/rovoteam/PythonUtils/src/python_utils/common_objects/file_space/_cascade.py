"""Cascade path builder for FileSpaceManager.

Builds the priority-ordered list of folders to search, interleaving
multiple roots at each cascade level.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Sequence


def build_cascade_folders(
    roots: List[Path],
    space: str = "",
    type_: str = "",
    subfolder_canonical: str = "variables",
    subfolder_prefixes: Sequence[str] = ("_", "."),
) -> List[Path]:
    """Build cascade folder list (most-specific -> general, interleaved across roots).

    Returns folders WITHOUT name/version — caller appends those.

    Cascade order (for each root in priority order, interleaved by level):
      Level 1: {root}/{space}/{type_}/{subfolder}/   (most specific)
      Level 2: {root}/{space}/{subfolder}/           (space-level)
      Level 3: {root}/{subfolder}/                   (global / cross-space)

    The subfolder is resolved via ``subfolder_canonical`` + prefix list:
    tries ``_variables``, then ``.variables`` (configurable). First existing wins
    per cascade level. If neither exists, the path is still included (the
    file-finding step will simply not find anything there).

    Cross-space is naturally supported: Level 3 is visible to all spaces.

    Edge cases:
      - space="" skips Level 2
      - type_="" makes Level 1 = space-level (same as Level 2 if space is set)
      - subfolder_canonical="" omits subfolder entirely
    """
    folders: List[Path] = []
    seen: set = set()

    def _resolve_subfolder(parent: Path) -> Path:
        """Find the actual subfolder directory under parent."""
        if not subfolder_canonical:
            return parent
        for prefix in subfolder_prefixes:
            candidate = parent / f"{prefix}{subfolder_canonical}"
            if candidate.is_dir():
                return candidate
        return parent / f"{subfolder_prefixes[0]}{subfolder_canonical}" if subfolder_prefixes else parent / subfolder_canonical

    def _add(path: Path) -> None:
        key = str(path)
        if key not in seen:
            seen.add(key)
            folders.append(path)

    # Level 1: space/type/subfolder (most specific)
    for root in roots:
        base = root
        if space:
            base = base / space
        if type_:
            base = base / type_
        if subfolder_canonical:
            _add(_resolve_subfolder(base))
        else:
            _add(base)

    # Level 2: space/subfolder (space-level) — only if space is set AND type_ is set
    # (otherwise Level 1 already covered this)
    if space and type_:
        for root in roots:
            base = root / space
            if subfolder_canonical:
                _add(_resolve_subfolder(base))
            else:
                _add(base)

    # Level 3: subfolder (global / cross-space)
    for root in roots:
        if subfolder_canonical:
            _add(_resolve_subfolder(root))
        else:
            _add(root)

    return folders
