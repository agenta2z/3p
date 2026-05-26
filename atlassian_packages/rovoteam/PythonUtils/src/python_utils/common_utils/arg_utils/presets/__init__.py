"""
Preset loader implementations for different file formats.

Supports:
- JSON presets (.json)
- Python presets (.py with config dict)
- Extensible for YAML, TOML, etc.
"""

from .base import PresetLoader
from .json_preset import JsonPresetLoader
from .python_preset import PythonPresetLoader

__all__ = [
    "PresetLoader",
    "JsonPresetLoader",
    "PythonPresetLoader",
]
