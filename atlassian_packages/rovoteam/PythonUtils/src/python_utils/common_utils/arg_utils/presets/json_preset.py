"""
JSON preset loader implementation.
"""

import json
from os import path
from typing import Any, Dict, List, Optional, Tuple

from .base import PresetLoader


class JsonPresetLoader(PresetLoader):
    """
    Loader for JSON preset files.

    Supports:
    - Loading .json files
    - Auto-detection of .json extension
    - Key extraction from nested structures
    """

    @property
    def supported_extensions(self) -> Tuple[str, ...]:
        return (".json",)

    def can_handle(self, file_path: str) -> bool:
        """Check if this loader can handle the given file path."""
        return self.resolve_path(file_path) is not None

    def resolve_path(self, file_path: str) -> Optional[str]:
        """
        Resolve the actual file path, adding .json extension if needed.

        Args:
            file_path: Path to the preset file

        Returns:
            Resolved path if file exists, None otherwise
        """
        # Check if path already has .json extension and exists
        if file_path.endswith(".json") and path.isfile(file_path):
            return file_path

        # Check if file exists as-is (might be a JSON file without extension)
        if path.isfile(file_path) and not file_path.endswith(".py"):
            # Only handle if it's not a Python file
            return file_path

        # Try adding .json extension
        json_path = f"{file_path}.json"
        if path.isfile(json_path):
            return json_path

        return None

    def load(self, file_path: str, keys: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Load preset from JSON file.

        Args:
            file_path: Path to the JSON file
            keys: Optional keys to extract from nested preset structure

        Returns:
            Dictionary of preset values

        Raises:
            FileNotFoundError: If the file does not exist
            json.JSONDecodeError: If the file is not valid JSON
        """
        resolved = self.resolve_path(file_path)
        if resolved is None:
            raise FileNotFoundError(f"JSON preset not found: {file_path}")

        with open(resolved, "r", encoding="utf-8") as f:
            data = json.load(f)

        if keys:
            # Extract only specified keys from the loaded data
            result = {}
            for key in keys:
                if key in data:
                    if isinstance(data[key], dict):
                        result.update(data[key])
                    else:
                        result[key] = data[key]
            return result

        return data
