"""
Exceptions for variable management.

This module provides exception classes for variable resolution errors.
"""

from typing import List


class AmbiguousVariableError(Exception):
    """Raised when multiple variable file paths match a variable name."""

    def __init__(self, variable_name: str, matching_paths: List[str]):
        self.variable_name = variable_name
        self.matching_paths = matching_paths
        paths_str = ", ".join(matching_paths)
        super().__init__(
            f"Ambiguous variable '{variable_name}': multiple paths found [{paths_str}]"
        )


class CircularReferenceError(Exception):
    """Raised when circular variable references are detected."""

    def __init__(self, resolution_stack: List[str], current_ref: str):
        self.resolution_stack = resolution_stack
        self.current_ref = current_ref
        chain = " -> ".join(resolution_stack + [current_ref])
        super().__init__(f"Circular variable reference detected: {chain}")


class MaxDepthExceededError(Exception):
    """Raised when variable resolution exceeds maximum recursion depth."""

    def __init__(self, resolution_stack: List[str], max_depth: int):
        self.resolution_stack = resolution_stack
        self.max_depth = max_depth
        recent = resolution_stack[-5:] if len(resolution_stack) > 5 else resolution_stack
        chain = " -> ".join(recent)
        super().__init__(
            f"Max recursion depth ({max_depth}) exceeded. Recent: {chain}"
        )
