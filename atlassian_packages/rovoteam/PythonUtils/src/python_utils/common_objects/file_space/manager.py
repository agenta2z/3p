"""FileSpaceManager — canonical file-space resolver with cascade + master_version.

Treats the filesystem as a hierarchical dict:
  {root}/{space}/{type}/{subfolder}/{name}/{master_version}/{version}.ext -> content

Supports multi-root interleaving, version fallback (version -> default),
master_version subdirectory scoping, .config.yaml LOCAL-only aliases,
and pluggable FieldBackend chain for future YAML/JSON backends.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, List, Optional, Sequence, Tuple, Union

from ._cascade import build_cascade_folders
from .backends.file_backend import FileBackend
from .backends.protocol import FieldBackend
from .resolved_content import ResolvedContent

Parser = Callable[[Any], Any]
logger = logging.getLogger(__name__)


class FileSpaceManager:
    """Cascade resolver for hierarchical file-based dicts.

    Both ``TemplateManager`` and ``FileBasedVariableManager`` delegate
    cascade + folder-search + version-search to this class.
    """

    def __init__(
        self,
        roots: List[Union[str, Path]],
        reserved_subfolder_canonical: str = "variables",
        reserved_subfolder_prefixes: Sequence[str] = ("_", "."),
        file_extensions: Sequence[str] = (".jinja2", ".jinja", ".j2", ".hbs", ".txt", ""),
        enable_overrides: bool = False,
        override_suffix: str = ".override",
        backends: Optional[Sequence[FieldBackend]] = None,
        encoding: str = "utf-8",
    ):
        self.roots = [Path(r) for r in roots]
        self.reserved_subfolder_canonical = reserved_subfolder_canonical
        self.reserved_subfolder_prefixes = tuple(reserved_subfolder_prefixes)
        self.file_extensions = tuple(file_extensions)
        self.enable_overrides = enable_overrides
        self.override_suffix = override_suffix
        self.encoding = encoding

        if backends is not None:
            self.backends: List[FieldBackend] = list(backends)
        else:
            self.backends = [
                FileBackend(
                    file_extensions=self.file_extensions,
                    enable_overrides=self.enable_overrides,
                    override_suffix=self.override_suffix,
                    encoding=self.encoding,
                )
            ]

    # --- Low-level primitives ---

    def build_cascade(self, space: str = "", type_: str = "") -> List[Path]:
        """Build cascade folder list (most-specific -> general, interleaved across roots).

        Returns folders WITHOUT name/version.
        """
        return build_cascade_folders(
            roots=self.roots,
            space=space,
            type_=type_,
            subfolder_canonical=self.reserved_subfolder_canonical,
            subfolder_prefixes=self.reserved_subfolder_prefixes,
        )

    def find_in_folder(self, folder: Path, name: Optional[str]) -> Optional[Path]:
        """Find a file by name inside a single folder. Returns Path or None.

        Delegates to the first backend (FileBackend) for the actual lookup.
        """
        if not name or not folder.is_dir():
            return None
        for backend in self.backends:
            resolved = backend.resolve(folder=folder, name=name, encoding=self.encoding)
            if resolved is not None:
                return resolved.path
        return None

    # --- High-level resolve ---

    def resolve(
        self,
        *,
        space: str = "",
        type_: str = "",
        name: str,
        version: str = "",
        master_version: Optional[str] = None,
    ) -> Optional[ResolvedContent]:
        """Full cascade + master + version + backend resolution.

        Search order (version specificity beats proximity — separated passes):

        When master_version is set:
          Pass 1: {cascade}/{name}/{master_version}/{version}.ext  (all levels)
          Pass 2: {cascade}/{name}/{master_version}/default.ext    (all levels)
          NO flat fallback.

        When master_version is None:
          Pass 1: {cascade}/{name}/{version}.ext                   (all levels)
            + Constraint H subdir fallback: if flat miss AND {name}/{version}/
              is a directory, try {name}/{version}/default.ext
          Pass 2: {cascade}/{name}/default.ext                     (all levels)
        """
        cascade = self.build_cascade(space, type_)

        if master_version:
            search_folders = [c / name / master_version for c in cascade]
        else:
            search_folders = [c / name for c in cascade]

        # Pass 1: version-specific across ALL cascade levels
        if version:
            for folder in search_folders:
                for backend in self.backends:
                    hit = backend.resolve(
                        folder=folder, name=version, encoding=self.encoding
                    )
                    if hit is not None:
                        return hit

                # Constraint H: subdirectory fallback (backward-compat)
                # Only when master_version is None — if version names a
                # directory (e.g., after migrating aggregation.jinja2 to
                # aggregation/default.jinja2), look inside it.
                if master_version is None:
                    subdir = folder / version
                    if subdir.is_dir():
                        for backend in self.backends:
                            hit = backend.resolve(
                                folder=subdir, name="default", encoding=self.encoding
                            )
                            if hit is not None:
                                return hit

        # Pass 2: default fallback across ALL cascade levels
        for folder in search_folders:
            for backend in self.backends:
                hit = backend.resolve(
                    folder=folder, name="default", encoding=self.encoding
                )
                if hit is not None:
                    return hit

        return None

    def read(self, resolved: ResolvedContent, parser: Optional[Parser] = None) -> Any:
        """Convenience: read content from a ResolvedContent."""
        return resolved.read(parser=parser)

    # --- Diagnostics ---

    def explain(
        self,
        *,
        space: str = "",
        type_: str = "",
        name: str,
        version: str = "",
        master_version: Optional[str] = None,
    ) -> List[Tuple[str, str, bool]]:
        """Return a list of (cascade_level_desc, search_uri, found) tuples.

        Traces every location that ``resolve()`` would check, in order.
        """
        cascade = self.build_cascade(space, type_)
        trace: List[Tuple[str, str, bool]] = []

        if master_version:
            search_folders = [c / name / master_version for c in cascade]
        else:
            search_folders = [c / name for c in cascade]

        def _check(folder: Path, check_name: str, level_desc: str) -> None:
            for backend in self.backends:
                hit = backend.resolve(
                    folder=folder, name=check_name, encoding=self.encoding
                )
                uri = f"file://{folder}/{check_name}"
                found = hit is not None
                trace.append((level_desc, uri, found))

        # Pass 1: version-specific
        if version:
            for i, folder in enumerate(search_folders):
                _check(folder, version, f"Pass1[{i}] {folder}")
                if master_version is None:
                    subdir = folder / version
                    if subdir.is_dir():
                        _check(subdir, "default", f"Pass1[{i}].subdir {subdir}")

        # Pass 2: default
        for i, folder in enumerate(search_folders):
            _check(folder, "default", f"Pass2[{i}] {folder}")

        return trace
