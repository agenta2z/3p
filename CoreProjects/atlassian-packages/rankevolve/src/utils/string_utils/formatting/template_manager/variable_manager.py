"""
Template Variable Manager for Template Variable Resolution.

This module provides template-specific wrappers around the generic
FileBasedVariableManager from common_objects.

The TemplateVariableManager (aliased as VariableLoader for backward compatibility)
provides template-specific parameter names and defaults:
- `template_dir` instead of `base_path`
- `template_root_space` instead of `variable_root_space`
- `template_type` instead of `variable_type`
- `variables_folder_name` defaults to `"_variables"` instead of `""`

Key features (inherited from FileBasedVariableManager):
- Auto-detection of variables from template content
- Cascading resolution (template-type -> template_root_space -> global)
- Scope modifiers: ^{{var}} (global), .{{var}} (current level), {{var}}? (optional)
- Variable-to-variable composition with circular reference detection
- Version support with override files for development
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

# Import from common_objects
from rankevolve.src.utils.common_objects.variable_manager import (
    FileBasedVariableManager,
    KeyDiscoveryMode,
    VariableManagerConfig,
    VariableSyntax,
    VariableExtractor,
    VariableSyntaxMapping,
)

# Re-export exceptions for backward compatibility
from rankevolve.src.utils.common_objects.variable_manager import (
    AmbiguousVariableError,
    CircularReferenceError,
    MaxDepthExceededError,
)


@dataclass
class TemplateVariableLoaderConfig(VariableManagerConfig):
    """Template-specific configuration.

    Extends VariableManagerConfig with template-specific defaults:
    - variables_folder_name defaults to "_variables" instead of ""

    Attributes:
        variables_folder_name: Subfolder name for variables.
            Default: "_variables" (template convention)

        All other attributes are inherited from VariableManagerConfig.
    """

    variables_folder_name: str = "_variables"


# Backward compatibility alias
VariableLoaderConfig = TemplateVariableLoaderConfig


class TemplateVariableManager(FileBasedVariableManager):
    """Template-specific variable manager with renamed parameters.

    This is a thin wrapper around FileBasedVariableManager that provides
    template-specific parameter names for better API clarity in template contexts:
    - `template_dir` instead of `base_path`
    - `template_root_space` instead of `variable_root_space`
    - `template_type` instead of `variable_type`
    - `variables_folder_name` defaults to `"_variables"`

    All features are inherited from FileBasedVariableManager.

    Example:
        >>> loader = TemplateVariableManager(template_dir="/path/to/templates")
        >>> variables = loader.resolve_from_template(
        ...     template_content,
        ...     template_root_space="action_agent",
        ...     template_type="main",
        ... )
        >>> # variables = {"notes_mindset": "resolved content", ...}
    """

    def __init__(
        self,
        template_dir: str,
        config: Optional[TemplateVariableLoaderConfig] = None,
        key_discovery_mode: KeyDiscoveryMode = KeyDiscoveryMode.LAZY,
    ):
        """Initialize TemplateVariableManager.

        Args:
            template_dir: Root directory containing templates and _variables folders.
            config: Configuration options (uses TemplateVariableLoaderConfig defaults).
            key_discovery_mode: When to discover available keys.
        """
        config = config or TemplateVariableLoaderConfig()
        super().__init__(
            base_path=template_dir,
            config=config,
            key_discovery_mode=key_discovery_mode,
        )
        self.template_dir = Path(template_dir)

    def resolve_from_template(
        self,
        template_content: str,
        template_root_space: str,
        template_type: str,
        version: str = "",
    ) -> Dict[str, str]:
        """Auto-detect and resolve all variables from template content.

        This is a convenience method that wraps resolve_from_content with
        template-specific parameter names.

        Args:
            template_content: Raw template content to scan.
            template_root_space: Root space name (e.g., "action_agent").
            template_type: Template type (e.g., "main").
            version: Version suffix for variable resolution (default: "").

        Returns:
            Dictionary mapping variable names to resolved content.
            Only includes variables that were successfully resolved.
        """
        return self.resolve_from_content(
            content=template_content,
            variable_root_space=template_root_space,
            variable_type=template_type,
            version=version,
        )


# Backward compatibility alias
VariableLoader = TemplateVariableManager
