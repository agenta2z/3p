"""
File-based variable manager implementation.

This module provides FileBasedVariableManager, a full-featured implementation
of VariableManager that loads variables from files on the filesystem.
"""

import fnmatch
import logging
import re
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Mapping, Optional, Set, Tuple

from rankevolve.src.utils.common_objects.variable_manager.base import VariableManager
from rankevolve.src.utils.common_objects.variable_manager.config import (
    VariableManagerConfig,
    VariableSyntax,
)
from rankevolve.src.utils.common_objects.variable_manager.exceptions import (
    AmbiguousVariableError,
    CircularReferenceError,
    MaxDepthExceededError,
)

logger = logging.getLogger(__name__)


# Back-compat for prompt-template variant directory renames. Persisted
# state may carry pre-rename `version` (== template_version) values; this
# map rewrites them at the resolver-folder lookup. Defense-in-depth —
# the primary normalization happens at the tool_executor input boundary
# (`_normalize_template_version` in src/server/tool_executor.py).
_TEMPLATE_VERSION_RENAMES: Dict[str, str] = {
    "submission_script_generator": "experiment_runner_creation",
    "experiment_launcher_maker": "experiment_runner_creation",
}
_LOGGED_LEGACY_RENAMES: Set[str] = set()


class KeyDiscoveryMode(Enum):
    """Mode for discovering available variable keys.

    Controls when the filesystem is scanned to discover available variable names.
    """

    LAZY = "lazy"
    """Discover keys only when __iter__ or __len__ is called (default)."""

    EAGER = "eager"
    """Discover keys immediately on initialization."""


class FileBasedVariableManager(VariableManager):
    """Full-featured file-based variable manager.

    Loads and resolves variables from files on the filesystem. Supports:

    - **Underscore split inference**: `notes_safety` → `notes/safety.hbs`
    - **Slash-path syntax**: `{{a/b/c}}` → `_variables/a/b/c.<ext>` (bypasses
      underscore inference; useful for cross-namespace composition)
    - **Sibling-first lookup**: bare `{{var}}` referenced from inside
      another variable file resolves to the same-directory sibling
      `<var>.<ext>` BEFORE the cascade is searched. Lets composers use
      terse `{{generic}}` for "the generic.<ext> next to me" instead of
      the verbose `{{X/Y/generic}}` slash form, AND keeps that meaning
      stable even when a same-named global `_variables/<var>.<ext>` is
      later added. Matches the "closest match wins" convention used by
      C `#include "x.h"`, JS `require('./x')`, Markdown `[link](./y.md)`,
      and Sphinx `:doc:` references. To force global lookup explicitly,
      use the `^{{var}}` scope modifier or the `enable_overrides` /
      `template_version` mechanisms.
    - **Multiple extension support**: `.hbs`, `.j2`, `.txt`, bare files
    - **Content caching**: Avoid re-reading unchanged files
    - **Cascade resolution**: `variable_type` → `variable_root_space` → global
    - **Scope modifiers**: `^{{var}}` (global), `.{{var}}` (current), `{{var}}?` (optional)
    - **Composition**: Variables can reference other variables
    - **Configurable syntax**: Handlebars, Jinja2, Python format, Template, or custom
    - **Flexible key discovery**: Lazy (on-demand) or eager (upfront)

    Example:
        >>> from rankevolve.src.utils.common_objects.variable_manager import (
        ...     FileBasedVariableManager,
        ...     VariableManagerConfig,
        ... )
        >>>
        >>> # Simple dict-like access
        >>> manager = FileBasedVariableManager(base_path="/config")
        >>> value = manager['database_host']
        >>> value = manager.get('database_port', '5432')
        >>>
        >>> # With cascade resolution
        >>> vars = manager.resolve_from_content(
        ...     "{{mindset}} and {{notes_safety}}",
        ...     variable_root_space="my_agent",
        ...     variable_type="main",
        ... )
    """

    # Regex pattern for variable references (Handlebars-style by default)
    # Group 1: scope modifier (^ or .)
    # Group 2: variable name (without braces)
    # Group 3: optional marker (?)
    VARIABLE_PATTERN = re.compile(r"(\^|\.)?\{\{([^}]+)\}\}(\?)?")

    def __init__(
        self,
        base_path: str,
        config: Optional[VariableManagerConfig] = None,
        key_discovery_mode: KeyDiscoveryMode = KeyDiscoveryMode.LAZY,
        variable_root_space: str = "",
        variable_type: str = "",
    ):
        """Initialize FileBasedVariableManager.

        Args:
            base_path: Root directory for variable resolution.
            config: Configuration options (uses defaults if not provided).
            key_discovery_mode: When to discover available keys.
            variable_root_space: Default root space for cascade resolution.
                E.g., "production" searches production/ before global.
            variable_type: Default variable type for cascade resolution.
                E.g., "api" searches {space}/api/ before {space}/.
        """
        self.base_path = Path(base_path)
        self.config = config or VariableManagerConfig()
        self.key_discovery_mode = key_discovery_mode
        self.variable_root_space = variable_root_space
        self.variable_type = variable_type
        self._content_cache: Dict[str, Any] = {}
        self._discovered_keys: Optional[Set[str]] = None

        # Eager mode: discover keys immediately
        if key_discovery_mode == KeyDiscoveryMode.EAGER:
            self._discover_keys()

    # region Public API

    def get_variable(
        self,
        name: str,
        compose: Optional[bool] = None,
        variable_root_space: str = "",
        variable_type: str = "",
        version: str = "",
    ) -> Optional[Any]:
        """Get a single variable by name.

        Args:
            name: The variable name to look up.
            compose: Whether to resolve nested variable references in the content.
                If None, uses config.compose_on_access (default True).
            variable_root_space: Root space for cascade resolution (used during composition).
            variable_type: Variable type for cascade resolution (used during composition).
            version: Version suffix for variable resolution.

        Returns:
            The variable content (str for text files, dict for structured files),
            or None if not found.
        """
        # Determine whether to compose
        should_compose = (
            compose if compose is not None else self.config.compose_on_access
        )

        # Get cascade paths for file lookup
        cascade_paths = self._get_cascade_paths(variable_root_space, variable_type)

        # Merge mode: collect dict values from all cascade levels + global config,
        # deep-merge them (most general first, most specific last — child wins).
        if self.config.merge_structured_values:
            layers: list = []  # collected from most general to most specific

            # Check global config at each cascade level (parent defaults)
            if self.config.global_config_filename_patterns:
                for cascade_path in reversed(cascade_paths):  # global first
                    match = self._match_filename_patterns(
                        cascade_path,
                        self.config.global_config_filename_patterns,
                    )
                    if match is not None:
                        gc = self._read_file_content(match)
                        if isinstance(gc, dict):
                            layers.append(gc)

            # Check variable-specific file at each cascade level
            for cascade_path in reversed(cascade_paths):  # global first
                file_path, _ = self._find_variable_file(
                    name, [cascade_path], version=version
                )
                if file_path is not None:
                    vc = self._read_file_content(file_path)
                    if isinstance(vc, dict):
                        layers.append(vc)
                    elif isinstance(vc, str):
                        # Str value in merge path — apply composition if enabled
                        if should_compose:
                            extractor = self._get_variable_extractor(file_path)
                            if extractor is not None:
                                vc = self._resolve_content(
                                    vc,
                                    variable_root_space,
                                    variable_type,
                                    version,
                                    [name],
                                    file_path,
                                )
                        return vc

            if layers:
                from rankevolve.src.utils.common_utils.map_helper import _deep_merge_two

                result: dict = {}
                for layer in layers:
                    result = _deep_merge_two(result, layer)
                return result
            return None

        # Standard mode: first-match wins (existing behavior)
        file_path, _ = self._find_variable_file(name, cascade_paths, version=version)

        if file_path is None:
            return None

        content = self._read_file_content(file_path)

        # Structured content (dict from content_loaders) bypasses composition
        if not isinstance(content, str):
            return content

        # Resolve nested variables if composition is enabled
        if should_compose:
            extractor = self._get_variable_extractor(file_path)
            if extractor is not None:
                content = self._resolve_content(
                    content,
                    variable_root_space,
                    variable_type,
                    version,
                    resolution_stack=[name],
                    current_file_path=file_path,
                )

        return content

    def resolve_variables(self, names: List[str]) -> Dict[str, Any]:
        """Resolve multiple variables at once.

        Args:
            names: List of variable names to resolve.

        Returns:
            Dictionary mapping variable names to their resolved content.
            Variables that are not found are omitted from the result.
        """
        result = {}
        for name in names:
            value = self.get_variable(name)
            if value is not None:
                result[name] = value
        return result

    def resolve_from_content(
        self,
        content: str,
        variable_root_space: str = "",
        variable_type: str = "",
        version: str = "",
    ) -> Dict[str, Any]:
        """Auto-detect and resolve all variables from content.

        Scans the content for variable references based on the configured syntax,
        resolves those that have matching files, and returns a dictionary
        of variable names to resolved content.

        Args:
            content: Content string containing variable references.
            variable_root_space: Root space for cascade resolution.
            variable_type: Variable type for cascade resolution.
            version: Version suffix for variable resolution.

        Returns:
            Dictionary mapping variable names to resolved content.
            Only includes variables that were successfully resolved.
        """
        resolved_variables: Dict[str, str] = {}

        # Get variable extractor based on config
        extractor = self._get_variable_extractor()
        if extractor is None:
            # Pure text mode - no composition
            return resolved_variables

        # Check if we should use the Handlebars pattern (supports scope modifiers)
        syntax = self.config.variable_syntax
        use_handlebars_pattern = (
            syntax == VariableSyntax.HANDLEBARS
            or syntax == VariableSyntax.JINJA2  # JINJA2 uses same {{}} pattern
        )

        if use_handlebars_pattern:
            # Use built-in pattern matching for scope modifiers support
            for match in self.VARIABLE_PATTERN.finditer(content):
                scope = match.group(1)
                var_name = match.group(2).strip()
                is_optional = match.group(3) == "?"

                # Skip partials (Handlebars-specific)
                if var_name.startswith(">"):
                    continue

                # Skip if already resolved
                if var_name in resolved_variables:
                    continue

                resolved = self._resolve_variable(
                    var_name,
                    variable_root_space,
                    variable_type,
                    version,
                    scope,
                    is_optional,
                    resolution_stack=[],
                    current_level_path=None,
                )

                if resolved is not None:
                    resolved_variables[var_name] = resolved
        else:
            # Use extractor for other syntaxes (no scope modifier support)
            var_names = extractor(content)
            for var_name in var_names:
                if var_name in resolved_variables:
                    continue

                resolved = self._resolve_variable(
                    var_name,
                    variable_root_space,
                    variable_type,
                    version,
                    scope=None,  # No scope modifiers for other syntaxes
                    is_optional=False,
                    resolution_stack=[],
                    current_level_path=None,
                )

                if resolved is not None:
                    resolved_variables[var_name] = resolved

        return resolved_variables

    def reload(self) -> None:
        """Clear all caches. Call this for hot-reload during development."""
        self.clear_cache()
        self._discovered_keys = None

    def clear_cache(self) -> None:
        """Clear the content cache."""
        self._content_cache.clear()

    # endregion

    # region Mapping Interface

    def __getitem__(self, key: str) -> str:
        """Get variable content by name.

        Uses class-level variable_root_space and variable_type for cascade,
        and config.compose_on_access for composition.
        For explicit control, use get() or get_variable() instead.

        Raises:
            KeyError: If the variable is not found.
        """
        value = self.get_variable(
            key,
            compose=self.config.compose_on_access,
            variable_root_space=self.variable_root_space,
            variable_type=self.variable_type,
        )
        if value is None:
            raise KeyError(key)
        return value

    def get(
        self,
        key: str,
        default: Optional[str] = None,
        *,
        compose: Optional[bool] = None,
        cascade: bool = True,
        variable_root_space: Optional[str] = None,
        variable_type: Optional[str] = None,
        version: str = "",
    ) -> Optional[str]:
        """Get variable content by name with a default value.

        Args:
            key: The variable name to look up.
            default: Value to return if variable is not found.
            compose: Whether to resolve nested variable references.
                If None, uses config.compose_on_access (default True).
            cascade: Whether to use cascade resolution.
                If True, uses class-level variable_root_space and variable_type.
                If False, searches global only.
            variable_root_space: Override class-level root space.
                Only used when cascade=True.
            variable_type: Override class-level variable type.
                Only used when cascade=True.
            version: Version suffix for variable resolution.

        Returns:
            The variable content, or default if not found.
        """
        # Determine cascade parameters
        if cascade:
            space = (
                variable_root_space
                if variable_root_space is not None
                else self.variable_root_space
            )
            vtype = variable_type if variable_type is not None else self.variable_type
        else:
            space = ""
            vtype = ""

        value = self.get_variable(
            key,
            compose=compose,
            variable_root_space=space,
            variable_type=vtype,
            version=version,
        )
        return value if value is not None else default

    def __iter__(self) -> Iterator[str]:
        """Iterate over available variable names."""
        if self._discovered_keys is None:
            self._discover_keys()
        return iter(self._discovered_keys)

    def __len__(self) -> int:
        """Return the number of available variables."""
        if self._discovered_keys is None:
            self._discover_keys()
        return len(self._discovered_keys)

    # endregion

    # region Key Discovery

    def _discover_keys(self) -> None:
        """Scan filesystem to discover available variable names."""
        keys: Set[str] = set()

        # Determine the variables folder path
        vars_folder = self.config.variables_folder_name
        if vars_folder:
            base = self.base_path / vars_folder
        else:
            base = self.base_path

        if not base.exists():
            self._discovered_keys = keys
            return

        # Walk the directory tree
        for ext in self.config.file_extensions:
            if ext:
                pattern = f"**/*{ext}"
            else:
                pattern = "**/*"

            for file_path in base.glob(pattern):
                if file_path.is_file():
                    # Convert file path to variable name
                    rel_path = file_path.relative_to(base)
                    # Remove extension
                    name = str(rel_path)
                    for e in self.config.file_extensions:
                        if e and name.endswith(e):
                            name = name[: -len(e)]
                            break
                    # Skip override files
                    if self.config.override_suffix in name:
                        continue
                    # Convert path separators to underscores
                    name = name.replace("/", "_").replace("\\", "_")
                    keys.add(name)

        self._discovered_keys = keys

    # endregion

    # region Underscore Splits

    def _generate_underscore_splits(self, name: str) -> List[str]:
        """Generate all possible path splits for a variable name with underscores.

        Args:
            name: Variable name (e.g., "notes_mindset" or "my_app_settings")

        Returns:
            List of possible paths (e.g., ["notes/mindset", "notes_mindset"])
        """
        if "_" not in name:
            return [name]  # Flat file only

        splits = []
        parts = name.split("_")

        # Generate all possible split points
        # For "a_b_c", generate: "a/b_c", "a_b/c", "a_b_c"
        for i in range(1, len(parts)):
            folder = "_".join(parts[:i])
            file_name = "_".join(parts[i:])
            splits.append(f"{folder}/{file_name}")

        # Also try as flat file
        splits.append(name)

        return splits

    # endregion

    # region Cascade Resolution

    def _get_cascade_paths(
        self,
        variable_root_space: str,
        variable_type: str,
        scope: Optional[str] = None,
        current_level_path: Optional[Path] = None,
    ) -> List[Path]:
        """Get the cascade paths for variable resolution.

        Args:
            variable_root_space: Root space name (e.g., "my_agent")
            variable_type: Variable type (e.g., "main")
            scope: Scope modifier (None for cascade, "^" for global, "." for current)
            current_level_path: Path of the file containing the reference (for "." scope)

        Returns:
            List of paths to check, in priority order
        """
        vars_folder = self.config.variables_folder_name

        # Build the base path with optional subfolder
        def get_vars_path(parent: Path) -> Path:
            if vars_folder:
                return parent / vars_folder
            return parent

        if scope == "^":
            # Global only
            return [get_vars_path(self.base_path)]

        if scope == ".":
            # Current level only
            if current_level_path:
                # Find the _variables folder at the same level
                parent = current_level_path.parent
                while parent != self.base_path.parent:
                    vars_path = get_vars_path(parent)
                    if vars_path.exists():
                        return [vars_path]
                    parent = parent.parent
            # If current_level_path not provided, use variable_type level
            if variable_type and variable_root_space:
                return [
                    get_vars_path(self.base_path / variable_root_space / variable_type)
                ]
            elif variable_root_space:
                return [get_vars_path(self.base_path / variable_root_space)]
            return [get_vars_path(self.base_path)]

        # Default: cascade (variable_type -> variable_root_space -> global -> cross-space)
        paths = []
        if variable_type and variable_root_space:
            paths.append(
                get_vars_path(self.base_path / variable_root_space / variable_type)
            )
        if variable_root_space:
            paths.append(get_vars_path(self.base_path / variable_root_space))
        paths.append(get_vars_path(self.base_path))

        # Cross-space fallback: check a parent/shared root directory
        cross_space = self.config.cross_space_root
        if cross_space:
            cross_path = Path(cross_space)
            if cross_path != self.base_path and cross_path.is_dir():
                paths.append(get_vars_path(cross_path))

        return paths

    # endregion

    # region File Resolution

    def _match_filename_patterns(
        self, directory: Path, patterns: List[str]
    ) -> Optional[Path]:
        """Find first file in directory matching any pattern (in order).

        Supports exact names (``"tool.json"``) and globs (``"tool.*"``).
        Patterns are checked in priority order — first match wins.
        """
        children = sorted(directory.iterdir())
        for pattern in patterns:
            for child in children:
                if child.is_file() and fnmatch.fnmatch(child.name, pattern):
                    return child
        return None

    def _find_variable_file(
        self,
        variable_name: str,
        cascade_paths: List[Path],
        version: str = "",
    ) -> Tuple[Optional[Path], Optional[str]]:
        """Find the variable file for a given variable name.

        Args:
            variable_name: Variable name (e.g., "notes_mindset")
            cascade_paths: List of folders to search
            version: Version suffix (e.g., "enterprise")

        Returns:
            Tuple of (file_path, resolved_name) or (None, None) if not found
        """
        # Direct slash-path syntax: {{a/b/c}} bypasses underscore-split
        # inference and resolves the literal path under each cascade root.
        # Honors the same version + override + extension + folder-default
        # mechanisms as the underscore-split path, just without ambiguity.
        if "/" in variable_name:
            for cascade_path in cascade_paths:
                versioned_variants: List[str] = []
                if version and self.config.enable_overrides:
                    versioned_variants.append(
                        f"{variable_name}.{version}{self.config.override_suffix}"
                    )
                if self.config.enable_overrides:
                    versioned_variants.append(
                        f"{variable_name}{self.config.override_suffix}"
                    )
                if version:
                    versioned_variants.append(f"{variable_name}.{version}")
                versioned_variants.append(variable_name)
                for file_variant in versioned_variants:
                    for ext in self.config.file_extensions:
                        file_path = cascade_path / f"{file_variant}{ext}"
                        if file_path.exists() and file_path.is_file():
                            return file_path, variable_name
                target_dir = cascade_path / variable_name
                if target_dir.is_dir():
                    resolved = self._resolve_variable_folder(target_dir)
                    if resolved is not None:
                        return resolved, variable_name
            return None, None

        possible_paths = self._generate_underscore_splits(variable_name)

        for cascade_path in cascade_paths:
            matches_at_level = []

            # Directory config discovery: check <cascade>/<name>/<pattern>
            # Returns immediately if found (avoids false AmbiguousVariableError
            # when a flat file with the same name also exists).
            if self.config.directory_config_filename_patterns:
                dir_path = cascade_path / variable_name
                if dir_path.is_dir():
                    match = self._match_filename_patterns(
                        dir_path,
                        self.config.directory_config_filename_patterns,
                    )
                    if match is not None:
                        return (match, variable_name)

            for path_variant in possible_paths:
                # Build version resolution order — split into versioned and unversioned
                versioned_variants = []
                if version and self.config.enable_overrides:
                    versioned_variants.append(
                        f"{path_variant}.{version}{self.config.override_suffix}"
                    )
                if self.config.enable_overrides:
                    versioned_variants.append(
                        f"{path_variant}{self.config.override_suffix}"
                    )
                if version:
                    versioned_variants.append(f"{path_variant}.{version}")

                # Phase 1: Check versioned file variants (including overrides)
                found_for_this_variant = False
                for file_variant in versioned_variants:
                    for ext in self.config.file_extensions:
                        file_path = cascade_path / f"{file_variant}{ext}"
                        if file_path.exists():
                            matches_at_level.append((file_path, variable_name))
                            found_for_this_variant = True
                            break
                    if found_for_this_variant:
                        break

                # Phase 2: Folder-based fallback for versioned variables.
                # Apply back-compat rename map (defense-in-depth — primary
                # normalization happens at the tool_executor input boundary;
                # this catches any caller path that bypasses tool_executor).
                if not found_for_this_variant and version:
                    effective_version = _TEMPLATE_VERSION_RENAMES.get(version, version)
                    if (
                        effective_version != version
                        and version not in _LOGGED_LEGACY_RENAMES
                    ):
                        _LOGGED_LEGACY_RENAMES.add(version)
                        logger.info(
                            "template_version %r renamed to %r at resolver layer; "
                            "please update persisted state.",
                            version,
                            effective_version,
                        )
                    folder_path = cascade_path / path_variant / effective_version
                    if folder_path.is_dir():
                        resolved = self._resolve_variable_folder(folder_path)
                        if resolved is not None:
                            matches_at_level.append((resolved, variable_name))
                            found_for_this_variant = True

                # Phase 3: Unversioned file fallback
                if not found_for_this_variant:
                    for ext in self.config.file_extensions:
                        file_path = cascade_path / f"{path_variant}{ext}"
                        if file_path.exists():
                            matches_at_level.append((file_path, variable_name))
                            found_for_this_variant = True
                            break

                if found_for_this_variant:
                    break

            # Check ambiguity at this cascade level
            if len(matches_at_level) > 1:
                raise AmbiguousVariableError(
                    variable_name, [str(m[0]) for m in matches_at_level]
                )
            if len(matches_at_level) == 1:
                return matches_at_level[0]

        return None, None

    def _resolve_variable_folder(self, folder_path: Path) -> Optional[Path]:
        """Resolve a variable from a folder containing variant files.

        Resolution order:
        1. A file named "default" (with any configured extension)
        2. A .config.yaml file with a "default" key naming the file
        3. If exactly one content file exists, use it (unambiguous)
        4. Otherwise raise AmbiguousVariableError
        """
        # 1. Check for "default" named file
        for ext in self.config.file_extensions:
            default_file = folder_path / f"default{ext}"
            if default_file.is_file():
                return default_file

        # 2. Check for .config.yaml with "default" key
        config_file = folder_path / ".config.yaml"
        if config_file.is_file():
            import yaml

            try:
                config_data = yaml.safe_load(config_file.read_text(encoding="utf-8"))
            except Exception:
                config_data = None
            if isinstance(config_data, dict) and "default" in config_data:
                default_name = config_data["default"]
                for ext in self.config.file_extensions:
                    target = folder_path / f"{default_name}{ext}"
                    if target.is_file():
                        return target

        # 3. Collect all content files (exclude dotfiles like .config.yaml)
        content_files = [
            f
            for f in folder_path.iterdir()
            if f.is_file() and not f.name.startswith(".")
        ]
        if len(content_files) == 1:
            return content_files[0]
        if len(content_files) > 1:
            raise AmbiguousVariableError(
                str(folder_path.name),
                [str(f) for f in content_files],
            )

        # Empty folder
        return None

    def _read_file_content(self, file_path: Path) -> str:
        """Read file content with optional caching.

        If file_path is a directory, looks for .config.yaml with a 'default'
        key and resolves to the default variant file within the directory.
        """
        # Handle directory-type variables (variant directories)
        if file_path.is_dir():
            config_file = file_path / ".config.yaml"
            if config_file.is_file():
                try:
                    import yaml

                    with open(config_file) as f:
                        config = yaml.safe_load(f) or {}
                    default_variant = config.get("default", "")
                    if default_variant:
                        # Search for the default variant in subdirectories
                        for sub in sorted(file_path.iterdir()):
                            if sub.is_dir():
                                candidate = sub / f"{default_variant}.j2"
                                if candidate.is_file():
                                    file_path = candidate
                                    break
                                candidate = sub / f"{default_variant}.jinja2"
                                if candidate.is_file():
                                    file_path = candidate
                                    break
                except Exception:
                    pass
            # If still a directory after resolution, return empty
            if file_path.is_dir():
                return ""

        path_str = str(file_path)

        if self.config.cache_content and path_str in self._content_cache:
            return self._content_cache[path_str]

        # Dispatch to extension-based loader if configured
        loader = self.config.content_loaders.get(file_path.suffix)
        if loader is not None:
            content = loader(file_path)
        else:
            content = file_path.read_text(encoding="utf-8")

        if self.config.cache_content:
            self._content_cache[path_str] = content

        return content

    # endregion

    # region Variable Resolution

    def _resolve_variable(
        self,
        variable_name: str,
        variable_root_space: str,
        variable_type: str,
        version: str,
        scope: Optional[str],
        is_optional: bool,
        resolution_stack: List[str],
        current_level_path: Optional[Path] = None,
    ) -> Optional[str]:
        """Resolve a single variable.

        Args:
            variable_name: Variable name to resolve
            variable_root_space: Root space name (e.g., "my_agent")
            variable_type: Variable type
            version: Version suffix
            scope: Scope modifier (None, "^", or ".")
            is_optional: Whether the variable is optional
            resolution_stack: Current resolution stack for circular detection
            current_level_path: Path of the file containing the reference.
                Used by `.` scope (walk-up to find `_variables/` ancestor)
                AND by sibling-first lookup (look for same-directory
                sibling BEFORE cascade for unscoped non-slash bare names).
                Always set when called via `_resolve_content` recursion;
                None for top-level `resolve_from_content` calls.

        Returns:
            Resolved content or None if not found
        """
        # Trim whitespace from variable name
        variable_name = variable_name.strip()

        # Skip Handlebars partials
        if variable_name.startswith(">"):
            return None

        # Check for circular references
        if variable_name in resolution_stack:
            raise CircularReferenceError(resolution_stack, variable_name)

        # Check max depth
        if len(resolution_stack) > self.config.max_recursion_depth:
            raise MaxDepthExceededError(
                resolution_stack, self.config.max_recursion_depth
            )

        # Get cascade paths based on scope
        cascade_paths = self._get_cascade_paths(
            variable_root_space, variable_type, scope, current_level_path
        )

        # Sibling-first: for an UNSCOPED, NON-SLASH bare variable name
        # referenced from inside another variable file, the same-directory
        # sibling wins over the cascade.  This lets a composer at
        # ``_variables/X/Y/composer.jinja2`` use the terse ``{{generic}}``
        # to mean "the generic.<ext> file next to me", and the meaning
        # stays stable even if a global ``_variables/generic.<ext>`` is
        # later added.
        #
        # Rationale (vs cascade-first):
        #   * Locality intuition matches every relative-import convention
        #     (C ``#include "x.h"``, JS ``require('./x')``, Markdown
        #     ``[link](./y.md)``, Sphinx ``:doc:``): closest match wins.
        #   * Surprise-resistant: adding a global ``_variables/<name>.<ext>``
        #     does NOT silently re-route every nested ``{{name}}``
        #     reference whose author meant the local one.
        #   * Preserves "more specific wins" — siblings of the current file
        #     are even more specific than the deepest cascade level.
        #   * The author's intent when writing the terse bare name (instead
        #     of the verbose ``{{X/Y/name}}`` slash form) is clearly the
        #     local file.
        #
        # Triggers only when ALL hold:
        #   - we have a referencing-file path (current_level_path set;
        #     None for top-level resolve_from_content calls)
        #   - no scope modifier (^ / . keep their existing semantics)
        #   - no slash in the name (slash refs go through the slash
        #     branch in _find_variable_file and never need sibling lookup)
        #
        # Override use case: if you genuinely need a global-level override
        # of all same-named siblings, use the explicit override mechanism
        # (``enable_overrides`` + ``*.override.<ext>``) or
        # ``template_version`` — NOT accidental name-collision shadowing.
        file_path: Optional[Path] = None
        if (
            current_level_path is not None
            and scope is None
            and "/" not in variable_name
        ):
            sibling_dir = current_level_path.parent
            for ext in self.config.file_extensions:
                candidate = sibling_dir / f"{variable_name}{ext}"
                if candidate.is_file():
                    file_path = candidate
                    break

        # Cascade lookup if sibling-first didn't match (or was skipped
        # because of scope / slash / no current_level_path).
        if file_path is None:
            file_path, _ = self._find_variable_file(
                variable_name, cascade_paths, version
            )

        if file_path is None:
            return "" if is_optional else None

        # Read content
        content = self._read_file_content(file_path)

        # Structured content (dict from content_loaders) bypasses composition
        if not isinstance(content, str):
            return content

        # Check if composition is enabled
        extractor = self._get_variable_extractor(file_path)
        if extractor is None:
            # Pure text mode - return content as-is
            return content

        # Recursively resolve any variable references in the content
        new_stack = resolution_stack + [variable_name]
        content = self._resolve_content(
            content, variable_root_space, variable_type, version, new_stack, file_path
        )

        return content

    def _resolve_content(
        self,
        content: str,
        variable_root_space: str,
        variable_type: str,
        version: str,
        resolution_stack: List[str],
        current_file_path: Optional[Path] = None,
    ) -> str:
        """Resolve all variable references in content.

        Args:
            content: Content with variable references
            variable_root_space: Root space name (e.g., "my_agent")
            variable_type: Variable type
            version: Version suffix
            resolution_stack: Current resolution stack
            current_file_path: Path of the file containing the content

        Returns:
            Content with variables resolved
        """
        # Check if we should use the Handlebars pattern (supports scope modifiers)
        syntax = self.config.variable_syntax
        use_handlebars_pattern = (
            syntax == VariableSyntax.HANDLEBARS
            or syntax == VariableSyntax.JINJA2  # JINJA2 uses same {{}} pattern
        )

        if use_handlebars_pattern:
            # Use built-in pattern matching for scope modifiers support
            def replace_match(match: re.Match) -> str:
                scope = match.group(1)  # ^ or . or None
                var_name = match.group(2)  # variable name
                is_optional = match.group(3) == "?"

                resolved = self._resolve_variable(
                    var_name,
                    variable_root_space,
                    variable_type,
                    version,
                    scope,
                    is_optional,
                    resolution_stack,
                    current_file_path,
                )

                if resolved is not None:
                    return resolved

                # Not resolved - strip modifier or leave as-is
                if scope:
                    # Strip the modifier, leave for template engine
                    return f"{{{{{var_name}}}}}"
                if is_optional:
                    return ""
                # Leave as-is for template engine
                return match.group(0)

            return self.VARIABLE_PATTERN.sub(replace_match, content)
        else:
            # Use extractor and formatter for other syntaxes
            extractor = self._get_variable_extractor(current_file_path)
            formatter = self._get_variable_formatter(current_file_path)

            if extractor is None or formatter is None:
                # Pure text mode or no formatter available
                return content

            # Extract variable names from content
            var_names = extractor(content)
            if not var_names:
                return content

            # Resolve each variable
            resolved_vars: Dict[str, str] = {}
            for var_name in var_names:
                resolved = self._resolve_variable(
                    var_name,
                    variable_root_space,
                    variable_type,
                    version,
                    scope=None,  # No scope modifiers for other syntaxes
                    is_optional=False,
                    resolution_stack=resolution_stack,
                    current_level_path=current_file_path,
                )
                if resolved is not None:
                    resolved_vars[var_name] = resolved

            # Use the formatter to substitute variables
            if resolved_vars:
                try:
                    return formatter(content, resolved_vars)
                except Exception:
                    # If formatting fails, return content as-is
                    return content

            return content

    # endregion

    # region Formatter Integration

    def _get_variable_extractor(
        self, file_path: Optional[Path] = None
    ) -> Optional[Callable[[str], Set[str]]]:
        """Get the variable extraction function based on config and file path.

        Args:
            file_path: Path to the variable file (used for pattern matching).

        Returns:
            Callable that extracts variable names from content string,
            or None if no composition (pure text mode).
        """
        syntax = self.config.variable_syntax

        # None = pure text mode, no composition
        if syntax is None:
            return None

        # If it's a mapping, find matching pattern
        if isinstance(syntax, dict) and file_path is not None:
            matched_syntax = None
            for pattern, pattern_syntax in syntax.items():
                if fnmatch.fnmatch(file_path.name, pattern):
                    matched_syntax = pattern_syntax
                    break

            if matched_syntax is None:
                # No pattern matched - use pure text mode
                return None

            syntax = matched_syntax

        # If it's still None after mapping lookup
        if syntax is None:
            return None

        # If it's a callable, use it directly
        if callable(syntax):
            return syntax

        # Otherwise, look up the predefined extractor
        # Import here to avoid circular dependencies
        try:
            from rankevolve.src.utils.string_utils.formatting import handlebars_format

            extractors = {
                VariableSyntax.HANDLEBARS: handlebars_format.extract_variables,
            }

            # Try to import other formatters
            try:
                from rankevolve.src.utils.string_utils.formatting import jinja2_format

                extractors[VariableSyntax.JINJA2] = jinja2_format.extract_variables
            except ImportError:
                pass

            try:
                from rankevolve.src.utils.string_utils.formatting import (
                    python_str_format,
                )

                extractors[VariableSyntax.PYTHON_FORMAT] = (
                    python_str_format.extract_variables
                )
            except ImportError:
                pass

            try:
                from rankevolve.src.utils.string_utils.formatting import (
                    string_template_format,
                )

                extractors[VariableSyntax.TEMPLATE] = (
                    string_template_format.extract_variables
                )
            except ImportError:
                pass

            return extractors.get(syntax)

        except ImportError:
            # Fallback: return None (pure text mode) if formatters not available
            return None

    def _get_variable_formatter(
        self, file_path: Optional[Path] = None
    ) -> Optional[Callable[[str, Mapping[str, str]], str]]:
        """Get the variable formatting function based on config and file path.

        Args:
            file_path: Path to the variable file (used for pattern matching).

        Returns:
            Callable that formats a template string with a dict of values,
            or None if no composition (pure text mode).
        """
        syntax = self.config.variable_syntax

        # None = pure text mode, no composition
        if syntax is None:
            return None

        # If it's a mapping, find matching pattern
        if isinstance(syntax, dict) and file_path is not None:
            matched_syntax = None
            for pattern, pattern_syntax in syntax.items():
                if fnmatch.fnmatch(file_path.name, pattern):
                    matched_syntax = pattern_syntax
                    break

            if matched_syntax is None:
                return None

            syntax = matched_syntax

        if syntax is None:
            return None

        # If it's a callable, we can't format - return None
        if callable(syntax):
            return None

        # Otherwise, look up the predefined formatter
        try:
            from rankevolve.src.utils.string_utils.formatting import handlebars_format

            formatters: Dict[
                VariableSyntax, Callable[[str, Mapping[str, str]], str]
            ] = {
                VariableSyntax.HANDLEBARS: lambda t,
                v: handlebars_format.format_template(t, v),
            }

            try:
                from rankevolve.src.utils.string_utils.formatting import jinja2_format

                formatters[VariableSyntax.JINJA2] = (
                    lambda t, v: jinja2_format.format_template(t, v)
                )
            except ImportError:
                pass

            try:
                from rankevolve.src.utils.string_utils.formatting import (
                    python_str_format,
                )

                formatters[VariableSyntax.PYTHON_FORMAT] = (
                    lambda t, v: python_str_format.format_template(t, v)
                )
            except ImportError:
                pass

            try:
                from rankevolve.src.utils.string_utils.formatting import (
                    string_template_format,
                )

                formatters[VariableSyntax.TEMPLATE] = (
                    lambda t, v: string_template_format.format_template(t, v)
                )
            except ImportError:
                pass

            return formatters.get(syntax)

        except ImportError:
            return None

    # endregion

    # region Override & Alias API

    def _init_override_layer(self) -> None:
        """Initialize scoped override/alias state if not already done."""
        if not hasattr(self, "_scoped_overrides"):
            self._scoped_overrides: Dict[Tuple[str, str], Dict[str, object]] = {}
        if not hasattr(self, "_scoped_aliases"):
            self._scoped_aliases: Dict[Tuple[str, str], Dict[str, str]] = {}
        if not hasattr(self, "_scoped_yaml_sidecars"):
            self._scoped_yaml_sidecars: Dict[Tuple[str, str], Dict[str, object]] = {}

    def _cascade_scopes(
        self,
        root_space: str,
        vtype: str,
    ) -> List[Tuple[str, str]]:
        """Generate scope cascade order matching System A's _get_cascade_paths() logic.

        Returns scopes from most-specific to least-specific (global).
        """
        scopes: List[Tuple[str, str]] = []
        if root_space and vtype:
            scopes.append((root_space, vtype))
        if root_space:
            scopes.append((root_space, ""))
        scopes.append(("", ""))
        return scopes

    def _resolve_alias_cascaded(
        self,
        key: str,
        root_space: str,
        vtype: str,
    ) -> str:
        """Resolve alias by cascading through scoped alias dicts."""
        self._init_override_layer()
        for scope in self._cascade_scopes(root_space, vtype):
            aliases = self._scoped_aliases.get(scope, {})
            if key in aliases:
                return aliases[key]
        return key

    # -- Backward-compatible properties for external callers --
    # These return the global scope ("", "") dict. Used by
    # prompt_rendering.py:144 (`hasattr(vm, '_overrides') and vm._overrides`)

    @property
    def _overrides(self) -> Dict[str, object]:
        """Backward compat: returns global scope overrides dict."""
        self._init_override_layer()
        return self._scoped_overrides.setdefault(("", ""), {})

    @property
    def _aliases(self) -> Dict[str, str]:
        """Backward compat: returns global scope aliases dict."""
        self._init_override_layer()
        return self._scoped_aliases.setdefault(("", ""), {})

    @property
    def _yaml_sidecar(self) -> Dict[str, object]:
        """Backward compat: returns global scope yaml sidecar dict."""
        self._init_override_layer()
        return self._scoped_yaml_sidecars.setdefault(("", ""), {})

    # -- Public API --

    def load_yaml_sidecar(
        self,
        yaml_path,
        *,
        variable_root_space: str = "",
        variable_type: str = "",
    ) -> Dict:
        """Load variables from a YAML sidecar file into a scoped layer.

        Processes __alias__ entries and stores the rest as variables.

        Args:
            yaml_path: Path to the .variables.yaml file.
            variable_root_space: Scope root space (default "" = global).
            variable_type: Scope type (default "" = global).

        Returns:
            The loaded YAML dict (without __alias__ key).
        """
        import yaml

        self._init_override_layer()
        path = Path(yaml_path) if not isinstance(yaml_path, Path) else yaml_path
        if not path.is_file():
            return {}

        with open(path) as f:
            data = yaml.safe_load(f) or {}

        scope = (variable_root_space, variable_type)

        # Extract and process __alias__ entries into scoped dict
        if "__alias__" in data:
            scoped_aliases = self._scoped_aliases.setdefault(scope, {})
            for alias_name, target_path in data["__alias__"].items():
                scoped_aliases[alias_name] = target_path
            del data["__alias__"]

        self._scoped_yaml_sidecars.setdefault(scope, {}).update(data)
        return data

    @property
    def aliases(self) -> Dict[str, str]:
        """Return the merged alias registry (global first, specific wins)."""
        self._init_override_layer()
        merged: Dict[str, str] = {}
        # Merge all scopes — later entries override earlier
        for scope in sorted(self._scoped_aliases.keys()):
            merged.update(self._scoped_aliases[scope])
        return merged

    def set(
        self,
        key: str,
        value: object,
        *,
        variable_root_space: str = "",
        variable_type: str = "",
        override: bool = True,
    ) -> None:
        """Set a variable value with alias and fuzzy path resolution.

        Args:
            key: Variable name. Alias-resolved (cascaded), then fuzzy underscore
                 matching is applied against the yaml_sidecar data.
            value: Value to set. For alias targets that are dicts, if value
                   matches a sub-key, the sub-key's value is selected.
            variable_root_space: Scope root space (default "" = global).
            variable_type: Scope type (default "" = global).
            override: If True (default), overrides existing or creates new.
                      If False, raises KeyError if variable already exists.
        """
        from rankevolve.src.utils.common_utils.map_helper import (
            get_at_path,
            has_path,
            resolve_fuzzy_path,
        )

        self._init_override_layer()
        scope = (variable_root_space, variable_type)

        # Step 1: Cascade-resolve alias
        resolved_path = self._resolve_alias_cascaded(
            key, variable_root_space, variable_type
        )

        # Step 2: If alias target is a dict and value is a sub-key, select sub-value
        # Cascade through yaml sidecars to find the target dict
        if resolved_path != key:
            for s in self._cascade_scopes(variable_root_space, variable_type):
                sidecar = self._scoped_yaml_sidecars.get(s, {})
                if has_path(sidecar, resolved_path):
                    target = get_at_path(sidecar, resolved_path)
                    if (
                        isinstance(target, dict)
                        and isinstance(value, str)
                        and value in target
                    ):
                        actual_value = target[value]
                        scoped_overrides = self._scoped_overrides.setdefault(scope, {})
                        if not override and resolved_path in scoped_overrides:
                            raise KeyError(f"Variable {resolved_path!r} already set")
                        scoped_overrides[resolved_path] = actual_value
                        return
                    break  # Found the target (not a sub-key match) — stop cascading

        # Step 3: Try fuzzy underscore path resolution against yaml sidecars
        if "_" in resolved_path:
            for s in self._cascade_scopes(variable_root_space, variable_type):
                sidecar = self._scoped_yaml_sidecars.get(s, {})
                fuzzy_match = resolve_fuzzy_path(
                    sidecar, resolved_path, path_part_sep="_"
                )
                if fuzzy_match:
                    resolved_path = fuzzy_match
                    break

        # Step 4: Check override=False guard
        scoped_overrides = self._scoped_overrides.setdefault(scope, {})
        if not override and resolved_path in scoped_overrides:
            raise KeyError(f"Variable {resolved_path!r} already set")

        # Step 5: Store the override in the correct scope
        scoped_overrides[resolved_path] = value

    def clear(
        self,
        key: str,
        *,
        variable_root_space: str = "",
        variable_type: str = "",
    ) -> None:
        """Remove a set/overridden variable, reverting to source value."""
        self._init_override_layer()
        resolved_path = self._resolve_alias_cascaded(
            key, variable_root_space, variable_type
        )
        scope = (variable_root_space, variable_type)
        scoped_overrides = self._scoped_overrides.get(scope, {})
        scoped_overrides.pop(resolved_path, None)

    def clear_all(self) -> None:
        """Remove all set/overridden variables across ALL scopes."""
        self._init_override_layer()
        self._scoped_overrides.clear()

    def get_effective_value(
        self,
        key: str,
        default: object = None,
        *,
        variable_root_space: str = "",
        variable_type: str = "",
        skip_overrides: bool = False,
    ) -> object:
        """Get the effective value for a key, checking overrides first.

        Resolution priority (per cascade scope):
          overrides > yaml_sidecar > file-based.

        Args:
            key: Variable name (alias-resolved, fuzzy matched).
            default: Default value if not found anywhere.
            variable_root_space: Scope root space (default "" = global).
            variable_type: Scope type (default "" = global).
            skip_overrides: If True, skip overrides and return the source value.
                Useful for getting original content for UI display.

        Returns:
            The effective value.
        """
        from rankevolve.src.utils.common_utils.map_helper import (
            get_at_path,
            has_path,
            resolve_fuzzy_path,
        )

        self._init_override_layer()

        # Cascade-resolve alias
        resolved = self._resolve_alias_cascaded(key, variable_root_space, variable_type)

        # Cascade through scopes
        for scope in self._cascade_scopes(variable_root_space, variable_type):
            # Check overrides (highest priority)
            if not skip_overrides:
                scoped_overrides = self._scoped_overrides.get(scope, {})
                if resolved in scoped_overrides:
                    return scoped_overrides[resolved]

            # Check yaml_sidecar
            sidecar = self._scoped_yaml_sidecars.get(scope, {})
            if "." in resolved:
                if has_path(sidecar, resolved):
                    return get_at_path(sidecar, resolved)
            if resolved in sidecar:
                return sidecar[resolved]

            # Try fuzzy resolution against this scope's sidecar
            if "_" in resolved:
                fuzzy = resolve_fuzzy_path(sidecar, resolved, path_part_sep="_")
                if fuzzy:
                    return get_at_path(sidecar, fuzzy)

        # Fall back to file-based resolution (System A — already space-aware)
        file_value = self.get_variable(key)
        if file_value is not None:
            return file_value

        return default

    def get_all_variables(
        self,
        *,
        variable_root_space: str = "",
        variable_type: str = "",
    ) -> Dict[str, object]:
        """Get all variables as a nested dict, with overrides applied.

        Merges yaml sidecars across cascade scopes (global first, specific wins),
        then applies overrides on top.

        Args:
            variable_root_space: Scope root space (default "" = global).
            variable_type: Scope type (default "" = global).
        """
        from copy import deepcopy

        from rankevolve.src.utils.common_utils.map_helper import set_at_path

        self._init_override_layer()

        # Merge yaml sidecars: global first, then more specific scopes on top
        result: Dict[str, object] = {}
        for scope in reversed(self._cascade_scopes(variable_root_space, variable_type)):
            sidecar = self._scoped_yaml_sidecars.get(scope, {})
            if sidecar:
                sidecar_copy = deepcopy(sidecar)
                for k, v in sidecar_copy.items():
                    if (
                        k in result
                        and isinstance(result[k], dict)
                        and isinstance(v, dict)
                    ):
                        # Deep merge nested dicts
                        result[k] = {**result[k], **v}
                    else:
                        result[k] = v

        # Apply overrides: global first, then more specific scopes on top
        for scope in reversed(self._cascade_scopes(variable_root_space, variable_type)):
            scoped_overrides = self._scoped_overrides.get(scope, {})
            for path, value in scoped_overrides.items():
                if "." in path:
                    set_at_path(result, path, value)
                else:
                    result[path] = value

        return result

    # endregion
