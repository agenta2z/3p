"""
Template Manager module.

This module provides:
- TemplateManager: Template resolution and formatting with hierarchical namespaces
- VariableLoader: Automatic variable detection and resolution from _variables/ folders
- VariableLoaderConfig: Configuration for VariableLoader

Example (simple - with predefined_variables integration):
    >>> from python_utils.string_utils.formatting.template_manager import (
    ...     TemplateManager,
    ... )
    >>>
    >>> # Create manager with automatic variable resolution
    >>> manager = TemplateManager(
    ...     templates="/path/to/templates",
    ...     predefined_variables=True,  # Auto-creates VariableLoader
    ... )
    >>>
    >>> # Variables are automatically resolved and merged with user args
    >>> result = manager(
    ...     "action_agent/main/MyTemplate",
    ...     active_template_root_space="action_agent",
    ...     active_template_type="main",
    ...     user_input="data",  # User args override predefined
    ... )

Example (manual - with explicit VariableLoader):
    >>> from python_utils.string_utils.formatting.template_manager import (
    ...     TemplateManager,
    ...     VariableLoader,
    ...     VariableLoaderConfig,
    ... )
    >>>
    >>> # Create managers
    >>> loader = VariableLoader(template_dir="/path/to/templates")
    >>> manager = TemplateManager(templates="/path/to/templates")
    >>>
    >>> # Get raw template and resolve variables
    >>> template_content = manager.get_raw_template("action_agent/main/MyTemplate")
    >>> variables = loader.resolve_from_template(
    ...     template_content,
    ...     template_root_space="action_agent",
    ...     template_type="main",
    ... )
    >>>
    >>> # Render template with resolved variables
    >>> result = manager("action_agent/main/MyTemplate", **variables, user_input="data")
"""

from python_utils.string_utils.formatting.template_manager.template_manager import (
    TemplateManager,
    TemplateRootPriority,
)
from python_utils.string_utils.formatting.template_manager.sop_manager import (
    SOP,
    SOPManager,
    SOPPhase,
    SOPSubsection,
)
from python_utils.string_utils.formatting.template_manager.variable_manager import (
    AmbiguousVariableError,
    CircularReferenceError,
    MaxDepthExceededError,
    VariableLoader,
    VariableLoaderConfig,
)

__all__ = [
    "TemplateManager",
    "TemplateRootPriority",
    "VariableLoader",
    "VariableLoaderConfig",
    "AmbiguousVariableError",
    "CircularReferenceError",
    "MaxDepthExceededError",
    "SOP",
    "SOPManager",
    "SOPPhase",
    "SOPSubsection",
]
