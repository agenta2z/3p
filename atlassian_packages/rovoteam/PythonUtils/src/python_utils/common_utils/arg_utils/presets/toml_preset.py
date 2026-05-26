"""
TOML preset loader for get_parsed_args.

Loads preset configurations from TOML files (.toml).
"""

from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import os
import sys

from .base import PresetLoader


class TomlPresetLoader(PresetLoader):
    """
    Loads presets from TOML files.

    Supports:
    - .toml extension
    - Automatic extension detection
    - Key extraction from nested structures
    - Uses tomllib (Python 3.11+) or tomli (fallback)

    Example TOML file:
        learning_rate = 0.01
        batch_size = 64

        [model]
        name = "resnet50"
        layers = [64, 128, 256]

        [training]
        epochs = 100
        optimizer = "adam"
    """

    @property
    def supported_extensions(self) -> Tuple[str, ...]:
        """Returns supported file extensions."""
        return ('.toml',)

    def can_handle(self, file_path: str) -> bool:
        """
        Check if this loader can handle the given file path.

        Args:
            file_path: Path to the preset file

        Returns:
            True if file has .toml extension
        """
        return file_path.endswith('.toml')

    def resolve_path(self, file_path: str) -> Optional[str]:
        """
        Resolve the preset file path, trying .toml extension if needed.

        Args:
            file_path: Path to the preset file (may or may not have extension)

        Returns:
            Resolved absolute path, or None if file not found
        """
        # Try as-is first
        if os.path.exists(file_path):
            return os.path.abspath(file_path)

        # If no extension, try adding .toml
        if not file_path.endswith('.toml'):
            candidate = file_path + '.toml'
            if os.path.exists(candidate):
                return os.path.abspath(candidate)

        return None

    def load(self, file_path: str, keys: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Load preset from TOML file.

        Args:
            file_path: Path to the TOML file
            keys: Optional list of keys to extract from nested structure

        Returns:
            Dictionary of preset values

        Raises:
            FileNotFoundError: If file doesn't exist
            ImportError: If neither tomllib nor tomli is available
            TOMLDecodeError: If TOML file is malformed
        """
        # Try to import TOML library (tomllib for Python 3.11+, tomli for older)
        try:
            if sys.version_info >= (3, 11):
                import tomllib
            else:
                try:
                    import tomli as tomllib
                except ImportError:
                    raise ImportError(
                        "TOML support requires 'tomli' for Python < 3.11. "
                        "Install it with: pip install tomli"
                    )
        except ImportError as e:
            raise ImportError(
                "TOML preset support requires tomllib (Python 3.11+) or tomli. "
                "Install tomli with: pip install tomli"
            ) from e

        resolved = self.resolve_path(file_path)
        if resolved is None:
            raise FileNotFoundError(f"TOML preset file not found: {file_path}")

        # Load TOML file (binary mode required)
        with open(resolved, 'rb') as f:
            try:
                data = tomllib.load(f)
            except Exception as e:
                raise ValueError(f"Invalid TOML file {file_path}: {e}")

        if data is None:
            return {}

        if not isinstance(data, dict):
            raise ValueError(f"TOML file must contain a table/dict, got {type(data).__name__}")

        # Extract nested keys if specified
        if keys:
            for key in keys:
                if not isinstance(data, dict):
                    raise ValueError(
                        f"Cannot extract key '{key}' from non-dict value "
                        f"(type: {type(data).__name__})"
                    )
                if key not in data:
                    raise KeyError(f"Key '{key}' not found in TOML preset")
                data = data[key]

            # Final result should be a dict
            if not isinstance(data, dict):
                raise ValueError(
                    f"Extracted value must be a dictionary, got {type(data).__name__}"
                )

        return data
