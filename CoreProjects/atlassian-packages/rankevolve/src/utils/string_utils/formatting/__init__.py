"""
String formatting utilities.

This module provides various template formatting engines and managers:
- TemplateManager: Template resolution with hierarchical namespaces and versioning
- VariableLoader: Automatic variable detection and resolution
- Format modules: handlebars_format, jinja2_format, python_str_format, string_template_format
"""

from rankevolve.src.utils.string_utils.formatting.template_manager import (
    AmbiguousVariableError,
    CircularReferenceError,
    MaxDepthExceededError,
    TemplateManager,
    VariableLoader,
    VariableLoaderConfig,
)

__all__ = [
    "TemplateManager",
    "VariableLoader",
    "VariableLoaderConfig",
    "AmbiguousVariableError",
    "CircularReferenceError",
    "MaxDepthExceededError",
]
