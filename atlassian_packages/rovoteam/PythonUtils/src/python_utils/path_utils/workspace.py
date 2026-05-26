"""MergedSpace — multi-root path management with priority-ordered overlay.

Provides unified file search, path resolution, and write-target selection
across multiple root directories.  Reads use first-match-wins semantics;
writes target a single configurable root (default ``roots[0]``).

Use cases: workspace dirs (local override on shared base), resource overlays
(user dir on system dir), package-resource layering, generic priority-ordered
file lookup.

NOT used to refactor TemplateManager / FileBasedVariableManager — both have
domain-tuned multi-source machinery that is intentionally not generalised here.
"""

import os
from pathlib import Path
from typing import List, Optional, Sequence, Tuple, Union

from attr import attrib, attrs


@attrs
class MergedSpace:
    """Multiple root paths viewed as one logical space.

    Reads: first-match-wins across roots in priority order.
    Writes: targeted at a single configurable root (default = roots[0]).
    """

    _input_roots: Union[str, Path, Sequence[Union[str, Path]]] = attrib()
    _write_root_index: int = attrib(default=0)

    # Set in __attrs_post_init__
    _roots: List[Path] = attrib(init=False, default=None)
    _write_root: Path = attrib(init=False, default=None)

    def __attrs_post_init__(self):
        # 1. Normalize to list if single str/Path
        raw = self._input_roots
        if isinstance(raw, (str, Path)):
            raw = [raw]
        else:
            raw = list(raw)

        # 2. Resolve to absolute paths
        resolved = [Path(r).resolve() for r in raw]

        # 3. Deduplicate preserving first occurrence
        seen = []
        for r in resolved:
            if r not in seen:
                seen.append(r)

        # 4. Validate non-empty
        if not seen:
            raise ValueError("MergedSpace requires at least one root path")

        # 5. Validate write_root_index in bounds
        if not (0 <= self._write_root_index < len(seen)):
            raise IndexError(
                f"write_root_index {self._write_root_index} out of range "
                f"for {len(seen)} root(s)"
            )

        # 6. Store
        self._roots = seen
        self._write_root = seen[self._write_root_index]

    # -- Properties --

    @property
    def roots(self) -> List[Path]:
        """Copy of root paths in priority order."""
        return list(self._roots)

    @property
    def write_root(self) -> Path:
        """The root designated for write operations."""
        return self._write_root

    # -- Path safety --

    @staticmethod
    def _validate_relative(relative: Union[str, Path]) -> Path:
        """Reject absolute paths and ``..`` traversal.

        Returns the validated ``Path`` object for convenience.
        """
        p = Path(relative)
        if p.is_absolute():
            raise ValueError(f"Expected relative path, got absolute: {relative!r}")
        if ".." in p.parts:
            raise ValueError(f"Path traversal not allowed: {relative!r}")
        return p

    # -- Read operations --

    def find(self, relative: Union[str, Path]) -> Optional[Path]:
        """First match across roots.  ``None`` if missing everywhere."""
        rel = self._validate_relative(relative)
        for root in self._roots:
            candidate = root / rel
            if candidate.exists():
                return candidate
        return None

    def find_all(self, relative: Union[str, Path]) -> List[Path]:
        """All matches in priority order."""
        rel = self._validate_relative(relative)
        results = []
        for root in self._roots:
            candidate = root / rel
            if candidate.exists():
                results.append(candidate)
        return results

    def exists(self, relative: Union[str, Path]) -> bool:
        """``True`` if :meth:`find` returns non-``None``."""
        return self.find(relative) is not None

    # -- Write operations --

    def write_path(self, relative: Union[str, Path]) -> Path:
        """Path under write root for writing.  Does not create parent dirs."""
        rel = self._validate_relative(relative)
        return self._write_root / rel

    def ensure_write_dir(self, relative: Union[str, Path] = "") -> Path:
        """Ensure directory exists under write root; return absolute path.

        Raises :class:`FileNotFoundError` if the write root itself does not
        exist on disk.
        """
        rel = self._validate_relative(relative) if relative else Path()
        if not self._write_root.exists():
            raise FileNotFoundError(
                f"Write root does not exist on disk: {self._write_root}"
            )
        target = self._write_root / rel
        os.makedirs(target, exist_ok=True)
        return target

    # -- Glob --

    def glob(
        self,
        pattern: str,
        *,
        relative_subdir: Union[str, Path] = "",
        allow_duplicates: bool = False,
    ) -> List[Tuple[Path, Path]]:
        """Glob across all roots, return ``(absolute_path, relative_path)`` tuples.

        Default: deduplicate by relative path, keeping highest-priority match.
        With ``allow_duplicates=True``: return all matches in priority order.
        With ``relative_subdir``: scope search to ``<root>/<relative_subdir>/``.
        """
        # Validate relative_subdir if provided
        if relative_subdir:
            self._validate_relative(relative_subdir)

        subdir = Path(relative_subdir) if relative_subdir else Path()
        results: List[Tuple[Path, Path]] = []
        seen_rels: set = set()

        for root in self._roots:
            search_base = root / subdir
            if not search_base.is_dir():
                continue
            for abs_path in sorted(search_base.glob(pattern)):
                rel_path = abs_path.relative_to(search_base)
                if allow_duplicates:
                    results.append((abs_path, rel_path))
                else:
                    if rel_path not in seen_rels:
                        seen_rels.add(rel_path)
                        results.append((abs_path, rel_path))

        return results

    # -- Immutable extension --

    def with_added_root(
        self,
        root: Union[str, Path],
        *,
        priority: str = "lowest",
    ) -> "MergedSpace":
        """Return NEW ``MergedSpace`` with *root* added at given priority.

        Idempotent — adding an existing root returns a same-shaped instance.
        Original instance is NOT modified.

        Args:
            root: Directory path to add.
            priority: ``"lowest"`` (append, default) or ``"highest"`` (prepend).
        """
        if priority not in ("lowest", "highest"):
            raise ValueError(
                f"priority must be 'lowest' or 'highest', got {priority!r}"
            )

        new_root = Path(root).resolve()

        # Idempotent: if already present, return equivalent instance
        if new_root in self._roots:
            return MergedSpace(self._roots, write_root_index=self._write_root_index)

        if priority == "lowest":
            new_roots = list(self._roots) + [new_root]
        else:  # "highest"
            new_roots = [new_root] + list(self._roots)

        return MergedSpace(new_roots, write_root_index=self._write_root_index)

    # -- Subspace --

    def subspace(self, subdirectory: Union[str, Path]) -> "MergedSpace":
        """New ``MergedSpace`` with roots joined by *subdirectory*."""
        sub = Path(subdirectory)
        new_roots = [r / sub for r in self._roots]
        return MergedSpace(new_roots, write_root_index=self._write_root_index)

    # -- Relative path computation --

    def relative_to(self, absolute_path: Union[str, Path]) -> Path:
        """Relative path w.r.t. highest-priority matching root.

        Raises :class:`ValueError` if no root is a parent of *absolute_path*.
        """
        abs_p = Path(absolute_path).resolve()
        for root in self._roots:
            try:
                return abs_p.relative_to(root)
            except ValueError:
                continue
        raise ValueError(
            f"Path {absolute_path!r} is not under any root: "
            f"{[str(r) for r in self._roots]}"
        )
