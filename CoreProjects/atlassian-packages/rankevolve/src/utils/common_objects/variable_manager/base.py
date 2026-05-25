"""
Abstract base class for variable managers.

This module provides the VariableManager ABC that defines the interface
for all variable manager implementations.
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any, Dict, List, Optional


class VariableManager(Mapping, ABC):
    """Abstract base class for variable managers.

    Implements Python's Mapping interface for dict-like access to variables.
    Subclasses must implement the abstract methods to provide variable resolution.

    Example:
        >>> class MyManager(VariableManager):
        ...     def get_variable(self, name): ...
        ...     def resolve_variables(self, names): ...
        ...     def resolve_from_content(self, content, ...): ...
        ...     def __iter__(self): ...
        ...     def __len__(self): ...
        >>>
        >>> manager = MyManager()
        >>> value = manager['my_var']  # Dict-like access
        >>> value = manager.get('my_var', 'default')
        >>> 'my_var' in manager  # Check existence
        >>> for name in manager:  # Iterate over variable names
        ...     print(name, manager[name])
    """

    @abstractmethod
    def get_variable(self, name: str) -> Optional[Any]:
        """Get a single variable by name.

        Args:
            name: The variable name to look up.

        Returns:
            The variable content (str for text files, dict for structured files),
            or None if not found.
        """
        pass

    @abstractmethod
    def resolve_variables(self, names: List[str]) -> Dict[str, Any]:
        """Resolve multiple variables at once.

        Args:
            names: List of variable names to resolve.

        Returns:
            Dictionary mapping variable names to their resolved content.
            Variables that are not found are omitted from the result.
        """
        pass

    @abstractmethod
    def resolve_from_content(
        self,
        content: str,
        variable_root_space: str = "",
        variable_type: str = "",
    ) -> Dict[str, Any]:
        """Auto-detect and resolve variables from content.

        Extracts variable references from the content string based on the
        configured syntax, then resolves each variable using cascade resolution.

        Args:
            content: The content string containing variable references.
            variable_root_space: Root space for cascade resolution (optional).
            variable_type: Variable type for cascade resolution (optional).

        Returns:
            Dictionary mapping variable names to their resolved content.
        """
        pass

    # Mapping interface implementation

    def __getitem__(self, key: str) -> Any:
        """Get variable content by name.

        Raises:
            KeyError: If the variable is not found.
        """
        value = self.get_variable(key)
        if value is None:
            raise KeyError(key)
        return value

    def __contains__(self, key: object) -> bool:
        """Check if a variable exists."""
        if not isinstance(key, str):
            return False
        return self.get_variable(key) is not None

    @abstractmethod
    def __iter__(self):
        """Iterate over available variable names."""
        pass

    @abstractmethod
    def __len__(self) -> int:
        """Return the number of available variables."""
        pass
