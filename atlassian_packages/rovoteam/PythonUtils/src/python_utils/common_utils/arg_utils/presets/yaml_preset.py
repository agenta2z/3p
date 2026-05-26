"""
YAML preset loader for get_parsed_args.

Loads preset configurations from YAML files (.yaml, .yml).
"""

from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import os

from .base import PresetLoader


class YamlPresetLoader(PresetLoader):
    """
    Loads presets from YAML files.

    Supports:
    - .yaml and .yml extensions
    - Automatic extension detection
    - Key extraction from nested structures
    - Safe YAML loading

    Example YAML file:
        learning_rate: 0.01
        batch_size: 64
        model:
            name: resnet50
            layers: [64, 128, 256]
    """

    @property
    def supported_extensions(self) -> Tuple[str, ...]:
        """Returns supported file extensions."""
        return ('.yaml', '.yml')

    def can_handle(self, file_path: str) -> bool:
        """
        Check if this loader can handle the given file path.

        Args:
            file_path: Path to the preset file

        Returns:
            True if file has .yaml or .yml extension
        """
        return any(file_path.endswith(ext) for ext in self.supported_extensions)

    def resolve_path(self, file_path: str) -> Optional[str]:
        """
        Resolve the preset file path, trying different extensions if needed.

        Args:
            file_path: Path to the preset file (may or may not have extension)

        Returns:
            Resolved absolute path, or None if file not found
        """
        # Try as-is first
        if os.path.exists(file_path):
            return os.path.abspath(file_path)

        # If no extension, try adding .yaml and .yml
        if not any(file_path.endswith(ext) for ext in self.supported_extensions):
            for ext in self.supported_extensions:
                candidate = file_path + ext
                if os.path.exists(candidate):
                    return os.path.abspath(candidate)

        return None

    def load(self, file_path: str, keys: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Load preset from YAML file.

        Args:
            file_path: Path to the YAML file
            keys: Optional list of keys to extract from nested structure

        Returns:
            Dictionary of preset values

        Raises:
            FileNotFoundError: If file doesn't exist
            ImportError: If PyYAML is not installed
            yaml.YAMLError: If YAML file is malformed
        """
        try:
            import yaml
        except ImportError:
            raise ImportError(
                "PyYAML is required for YAML preset support. "
                "Install it with: pip install pyyaml"
            )

        resolved = self.resolve_path(file_path)
        if resolved is None:
            raise FileNotFoundError(f"YAML preset file not found: {file_path}")

        # Load YAML file
        with open(resolved, 'r') as f:
            try:
                data = yaml.safe_load(f)
            except yaml.YAMLError as e:
                raise ValueError(f"Invalid YAML file {file_path}: {e}")

        if data is None:
            return {}

        if not isinstance(data, dict):
            raise ValueError(f"YAML file must contain a dictionary, got {type(data).__name__}")

        # Extract nested keys if specified
        if keys:
            for key in keys:
                if not isinstance(data, dict):
                    raise ValueError(
                        f"Cannot extract key '{key}' from non-dict value "
                        f"(type: {type(data).__name__})"
                    )
                if key not in data:
                    raise KeyError(f"Key '{key}' not found in YAML preset")
                data = data[key]

            # Final result should be a dict
            if not isinstance(data, dict):
                raise ValueError(
                    f"Extracted value must be a dictionary, got {type(data).__name__}"
                )

        return data
