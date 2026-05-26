"""
Preset loader registry for managing multiple preset format handlers.
"""

from os import path
from typing import Any, Dict, List, Optional, Tuple

from python_utils.common_utils.arg_utils.presets.base import PresetLoader
from python_utils.common_utils.arg_utils.presets.json_preset import JsonPresetLoader
from python_utils.common_utils.arg_utils.presets.python_preset import PythonPresetLoader
from python_utils.common_utils.arg_utils.presets.yaml_preset import YamlPresetLoader
from python_utils.common_utils.arg_utils.presets.toml_preset import TomlPresetLoader


class PresetLoaderRegistry:
    """
    Registry for preset loaders.

    Manages multiple preset format handlers and provides a unified interface
    for loading presets from different file formats.

    Supports:
    - Multiple preset formats (JSON, YAML, TOML, Python, extensible)
    - Comma-separated multiple presets
    - Key extraction with ':' syntax (e.g., "preset:key1:key2")
    - preset_root resolution
    """

    def __init__(self):
        """Initialize with default loaders (JSON, YAML, TOML, and Python)."""
        self._loaders: List[PresetLoader] = []
        # Register default loaders - Python first since .py detection is stricter
        self.register(PythonPresetLoader())
        self.register(YamlPresetLoader())
        self.register(TomlPresetLoader())
        self.register(JsonPresetLoader())

    def register(self, loader: PresetLoader) -> None:
        """
        Register a new preset loader.

        Args:
            loader: PresetLoader instance to register
        """
        self._loaders.append(loader)

    def get_loader(self, file_path: str) -> Optional[PresetLoader]:
        """
        Get appropriate loader for the given file path.

        Args:
            file_path: Path to the preset file

        Returns:
            PresetLoader that can handle the file, or None if no loader found
        """
        # First, try loaders that can handle the path as-is (based on extension)
        for loader in self._loaders:
            if loader.can_handle(file_path):
                return loader

        # If no loader found by extension, try resolve_path on each loader
        # This handles cases where the path has no extension
        for loader in self._loaders:
            if loader.resolve_path(file_path) is not None:
                return loader

        return None

    def _parse_preset_path(self, preset_path: str) -> Tuple[str, Optional[List[str]]]:
        """
        Parse preset path to extract file path and optional keys.

        Supports ':' syntax for key extraction:
        - "path/preset" -> ("path/preset", None)
        - "path/preset:key1" -> ("path/preset", ["key1"])
        - "path/preset:key1:key2" -> ("path/preset", ["key1", "key2"])

        Note: Keys are extracted from the basename, so "path/preset:key1:key2"
        parses the basename "preset:key1:key2" to get keys.

        Args:
            preset_path: Preset path potentially containing key specifications

        Returns:
            Tuple of (file_path, keys)
        """
        basename = path.basename(preset_path)
        parts = basename.split(":")

        if len(parts) > 1:
            # Has keys - reconstruct the path with just the filename
            dir_part = path.dirname(preset_path)
            file_name = parts[0]
            keys = parts[1:]
            if dir_part:
                return path.join(dir_part, file_name), keys
            return file_name, keys

        return preset_path, None

    def load_preset(
        self,
        preset_path: str,
        preset_root: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Load preset(s) from path.

        Supports:
        - Single preset path
        - Comma-separated multiple presets (merged in order)
        - Key extraction with ':' syntax
        - preset_root resolution

        Args:
            preset_path: Path to preset file(s), potentially comma-separated
            preset_root: Optional root directory for resolving relative paths

        Returns:
            Dictionary of merged preset values

        Raises:
            ValueError: If no loader can handle the preset
            FileNotFoundError: If the preset file does not exist
        """
        result = {}

        for single_path in preset_path.split(","):
            single_path = single_path.strip()
            if not single_path:
                continue

            file_path, keys = self._parse_preset_path(single_path)

            # Try to find a loader for the path
            loader = self.get_loader(file_path)

            # If not found and preset_root is specified, try with preset_root
            if loader is None and preset_root:
                full_path = path.join(preset_root, file_path)
                loader = self.get_loader(full_path)
                if loader is not None:
                    file_path = full_path

            if loader is None:
                raise ValueError(
                    f"No loader found for preset: {single_path}. "
                    f"Checked paths: {file_path}"
                    + (f", {path.join(preset_root, file_path)}" if preset_root else "")
                )

            # Load and merge
            preset_data = loader.load(file_path, keys)
            result.update(preset_data)

        return result
