"""
Abstract base class for preset loaders.

Preset loaders handle loading argument presets from different file formats.
New formats (YAML, TOML, etc.) can be added by implementing this interface.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple


class PresetLoader(ABC):
    """
    Abstract base class for preset file loaders.

    Implementations should handle:
    - File extension detection
    - File loading and parsing
    - Optional key extraction from nested structures
    """

    @property
    @abstractmethod
    def supported_extensions(self) -> Tuple[str, ...]:
        """
        Return tuple of supported file extensions.

        Returns:
            Tuple of extensions including the dot, e.g., ('.json',)
        """
        pass

    @abstractmethod
    def can_handle(self, file_path: str) -> bool:
        """
        Check if this loader can handle the given file path.

        Should check if the file exists with any supported extension.

        Args:
            file_path: Path to the preset file (may or may not include extension)

        Returns:
            True if this loader can handle the file
        """
        pass

    @abstractmethod
    def resolve_path(self, file_path: str) -> Optional[str]:
        """
        Resolve the actual file path, adding extension if needed.

        Args:
            file_path: Path to the preset file (may or may not include extension)

        Returns:
            Resolved path if file exists, None otherwise
        """
        pass

    @abstractmethod
    def load(self, file_path: str, keys: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Load preset from the file.

        Args:
            file_path: Path to the preset file
            keys: Optional keys to extract from nested preset structure.
                  If provided, only these keys' values are merged into result.

        Returns:
            Dictionary of preset values

        Raises:
            FileNotFoundError: If the file does not exist
            ValueError: If the file format is invalid
        """
        pass
