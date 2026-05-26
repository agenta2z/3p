"""
Configuration classes for variable management.

This module provides configuration dataclasses for FileBasedVariableManager.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Union


class VariableSyntax(StrEnum):
    """Syntax for variable references in content.

    Defines how variable placeholders are parsed from content.
    """

    HANDLEBARS = "handlebars"  # {{var}}
    JINJA2 = "jinja2"  # {{ var }}
    PYTHON_FORMAT = "python"  # {var}
    TEMPLATE = "template"  # $var or ${var}


# Type for custom variable extractors
VariableExtractor = Callable[[str], Set[str]]
"""Callable that extracts variable names from content string.

Args:
    content: The content string to extract variables from.

Returns:
    Set of variable names found in the content.
"""

# Type for pattern-based syntax mapping
VariableSyntaxMapping = Dict[str, Optional[Union["VariableSyntax", VariableExtractor]]]
"""Mapping from file patterns to variable syntax.

Example:
    {"*.hbs": VariableSyntax.HANDLEBARS, "*.j2": VariableSyntax.JINJA2, "*.txt": None}
"""

# Type for content loaders
ContentLoader = Callable[[Path], Any]
"""Callable that loads a file and returns parsed content.

Default behavior (no loader): file.read_text() -> str.
JSON loader: json.load() -> dict.
YAML loader: yaml.safe_load() -> dict.
"""


@dataclass
class VariableManagerConfig:
    """Configuration for variable managers.

    Attributes:
        variables_folder_name: Subfolder name for variables.
            Default: "" (empty = files directly in base_path, no subfolder)

        variable_syntax: Syntax for parsing variable references. Can be:
            - VariableSyntax enum: Use this syntax for all files
            - Custom callable: (str) -> Set[str] for custom extraction
            - Dict[pattern, syntax]: Map file patterns to different syntaxes
              e.g., {"*.hbs": HANDLEBARS, "*.j2": JINJA2, "*.txt": None}
            - None: Pure text mode - no composition, variable files treated as raw text
            Default: VariableSyntax.HANDLEBARS

        enable_overrides: Enable .override files for development.
            When True, looks for {name}.override.{ext} files first.
            Default: False

        override_suffix: Suffix for override files.
            Default: ".override"

        cache_content: Cache file content in memory.
            Default: True

        file_extensions: Extensions to check in priority order.
            Default: [".hbs", ".j2", ".txt", ""]

        max_recursion_depth: Maximum depth for variable composition.
            Prevents infinite loops in variable-to-variable references.
            Default: 50

        compose_on_access: Whether to resolve nested variable references
            when using dict-like access (manager["key"] or manager.get("key")).
            When True, variables containing {{other_var}} will be composed.
            When False, raw content is returned.
            Default: True
    """

    variables_folder_name: str = ""
    variable_syntax: Optional[
        Union[VariableSyntax, VariableExtractor, VariableSyntaxMapping]
    ] = VariableSyntax.HANDLEBARS
    enable_overrides: bool = False
    override_suffix: str = ".override"
    cache_content: bool = True
    file_extensions: List[str] = field(
        default_factory=lambda: [".hbs", ".j2", ".jinja2", ".jinja", ".txt", ""]
    )
    max_recursion_depth: int = 50
    compose_on_access: bool = True
    cross_space_root: Optional[str] = None  # Path for cross-space variable fallback
    # Extension-based content loaders. Maps file extension -> loader function.
    # When a file's extension matches, the loader is called instead of read_text().
    # Default: {} (all files read as text -- preserves existing behavior).
    content_loaders: Dict[str, ContentLoader] = field(default_factory=dict)
    # When True, if multiple cascade levels return dict values for the same
    # variable, deep-merge them (child wins on conflict). When False, first-match
    # wins. Only applies to dict-typed values from content_loaders.
    # Default: False (preserves existing first-match behavior).
    merge_structured_values: bool = False
    # Filename patterns for per-directory config files.
    # When set, _find_variable_file also checks <cascade>/<name>/<pattern>.
    # Supports exact names ("tool.json") and globs ("tool.*", "*.json").
    # Patterns are checked in order -- first match wins.
    # Default: [] (disabled -- preserves existing name-based file discovery).
    directory_config_filename_patterns: List[str] = field(default_factory=list)
    # Filename patterns for parent-level default config.
    # When set, used as the "global" fallback at each cascade level.
    # E.g., ["global.json"] or ["global.*"].
    # Default: [] (disabled).
    global_config_filename_patterns: List[str] = field(default_factory=list)


# --- Built-in content loaders ---


def json_content_loader(path: Path) -> dict:
    """Load a JSON file as a dict."""
    import json

    with open(path) as f:
        return json.load(f)


def yaml_content_loader(path: Path) -> dict:
    """Load a YAML file as a dict."""
    import yaml

    with open(path) as f:
        return yaml.safe_load(f) or {}
