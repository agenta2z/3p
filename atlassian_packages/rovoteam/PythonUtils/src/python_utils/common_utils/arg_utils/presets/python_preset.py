"""
Python preset loader implementation.

Loads Python files that define a `config` dictionary.
"""

from os import path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from .base import PresetLoader


class PythonPresetLoader(PresetLoader):
    """
    Loader for Python preset files.

    Python preset files should define a `config` dictionary at module level.
    Mapping values in the config are automatically converted to Namespace objects.

    Example preset file (my_preset.py):
        config = {
            'learning_rate': 0.001,
            'batch_size': 32,
            'model_config': {
                'hidden_size': 256,
                'num_layers': 3
            }
        }
    """

    @property
    def supported_extensions(self) -> Tuple[str, ...]:
        return (".py",)

    def can_handle(self, file_path: str) -> bool:
        """Check if this loader can handle the given file path."""
        return self.resolve_path(file_path) is not None

    def resolve_path(self, file_path: str) -> Optional[str]:
        """
        Resolve the actual file path, adding .py extension if needed.

        Args:
            file_path: Path to the preset file

        Returns:
            Resolved path if file exists, None otherwise
        """
        # Check if path already has .py extension and exists
        if file_path.endswith(".py") and path.isfile(file_path):
            return file_path

        # Try adding .py extension
        py_path = f"{file_path}.py"
        if path.isfile(py_path):
            return py_path

        return None

    def load(self, file_path: str, keys: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Load preset from Python file.

        The Python file must define a `config` dictionary at module level.
        Mapping values are converted to Namespace objects.

        Args:
            file_path: Path to the Python file
            keys: Optional keys to extract from nested preset structure

        Returns:
            Dictionary of preset values

        Raises:
            FileNotFoundError: If the file does not exist
            AttributeError: If the file does not define a `config` variable
        """
        # Import utilities - deferred to avoid circular imports
        from python_utils.common_utils.environment_helper import path_import
        from python_utils.common_utils.arg_utils.arg_parse import dict_to_namespace

        resolved = self.resolve_path(file_path)
        if resolved is None:
            raise FileNotFoundError(f"Python preset not found: {file_path}")

        # Import the module
        module = path_import(path.abspath(resolved))

        if not hasattr(module, "config"):
            raise AttributeError(
                f"Python preset file must define a 'config' dictionary: {resolved}"
            )

        # Convert Mapping values to Namespace
        data = {
            k: (dict_to_namespace(v) if isinstance(v, Mapping) else v)
            for k, v in module.config.items()
        }

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
