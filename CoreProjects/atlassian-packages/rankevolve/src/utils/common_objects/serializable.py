"""Serializable mixin providing pluggable serialization support.

Provides a Serializable abstract mixin class that enables consistent
serialization across different classes with format flexibility (JSON, YAML, pickle).
"""

import base64
import dataclasses
import json
import pickle
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Union


class SerializationMode(Enum):
    """Options for automatic serialization mode selection."""

    PREFER_CLEAR_TEXT = "prefer_clear_text"
    """Try dict/JSON first, fall back to pickle if not possible."""

    PREFER_BINARY = "prefer_binary"
    """Always use pickle (binary) serialization."""


FIELD_TYPE = "_type"
FIELD_MODULE = "_module"
FIELD_SERIALIZATION = "_serialization"
FIELD_DATA = "_data"
FIELD_PICKLE_DATA = "_pickle_data"

SERIALIZATION_DICT = "dict"
SERIALIZATION_PICKLE = "pickle"


class Serializable:
    """Mixin providing pluggable serialization support with auto-detection.

    Auto-detects if class is suitable for dict/JSON serialization (dataclass, attrs, etc.)
    Falls back to pickle for complex objects.

    Attributes:
        auto_mode: Controls automatic serialization behavior.
    """

    auto_mode: SerializationMode = SerializationMode.PREFER_CLEAR_TEXT

    def _to_dict_auto(self) -> Dict[str, Any]:
        """Auto-convert to dict using attrs/dataclass introspection.

        Returns:
            Dict representation of the object.

        Raises:
            TypeError: If object cannot be converted to dict.
        """
        try:
            import attr

            if attr.has(type(self)):
                return attr.asdict(self)
        except ImportError:
            pass

        if dataclasses.is_dataclass(self):
            return dataclasses.asdict(self)

        if hasattr(self, "__dict__"):
            return dict(self.__dict__)

        raise TypeError(f"Cannot convert {type(self).__name__} to dict")

    def to_serializable_obj(
        self, mode: str = "auto", _output_format: Optional[str] = None
    ) -> Union[Dict[str, Any], "Serializable"]:
        """Convert to serializable Python object.

        Args:
            mode: 'auto', 'dict', or 'pickle'.
            _output_format: Target output format for early conflict detection.

        Returns:
            Dict with metadata or self for pickle fallback.
        """
        if mode == "pickle":
            return self

        prefer_clear = self.auto_mode == SerializationMode.PREFER_CLEAR_TEXT
        if mode in ("dict", "auto") and prefer_clear:
            try:
                data = self._to_dict_auto()
                return {
                    FIELD_TYPE: type(self).__name__,
                    FIELD_MODULE: type(self).__module__,
                    FIELD_SERIALIZATION: SERIALIZATION_DICT,
                    FIELD_DATA: data,
                }
            except TypeError as e:
                if mode == "dict":
                    raise TypeError(
                        f"Cannot serialize {type(self).__name__} as dict: {e}. "
                        f"Use mode='auto' or 'pickle'."
                    ) from e
                if _output_format in ("json", "yaml"):
                    raise TypeError(
                        f"Cannot serialize {type(self).__name__} to {_output_format}: "
                        f"object requires pickle but output_format='{_output_format}'."
                    ) from e

        return self

    @classmethod
    def from_serializable_obj(cls, obj: Dict[str, Any], **context) -> "Serializable":
        """Create instance from serializable Python object."""
        serialization = obj.get(FIELD_SERIALIZATION, SERIALIZATION_PICKLE)

        if serialization == SERIALIZATION_DICT and FIELD_DATA in obj:
            data = obj[FIELD_DATA]
            if dataclasses.is_dataclass(cls):
                return cls(**data)
            try:
                import attr

                if attr.has(cls):
                    return cls(**data)
            except ImportError:
                pass
            try:
                return cls(**data)
            except TypeError:
                instance = object.__new__(cls)
                instance.__dict__.update(data)
                return instance

        if FIELD_PICKLE_DATA in obj:
            try:
                pickle_bytes = base64.b64decode(obj[FIELD_PICKLE_DATA])
                return pickle.loads(pickle_bytes)
            except (pickle.UnpicklingError, TypeError) as e:
                raise TypeError(
                    f"Cannot deserialize {obj.get(FIELD_TYPE, 'unknown')}: {e}."
                ) from e

        raise ValueError(
            f"Invalid serializable object format. Expected '{FIELD_DATA}' or "
            f"'{FIELD_PICKLE_DATA}' key."
        )

    def serialize(
        self,
        output_format: str = "json",
        path: Optional[Union[str, Path]] = None,
        serializable_obj_mode: str = "auto",
        **kwargs,
    ) -> str:
        """Serialize to specified format ('json', 'yaml', or 'pickle')."""
        if output_format not in ("json", "yaml", "pickle"):
            raise ValueError(f"Unsupported format: {output_format}")

        effective_mode = (
            "pickle" if output_format == "pickle" else serializable_obj_mode
        )
        obj = self.to_serializable_obj(
            mode=effective_mode, _output_format=output_format
        )

        if obj is self:
            from rankevolve.src.utils.io_utils.pickle_io import pickle_save

            if path:
                pickle_save(self, str(path))
            pickle_bytes = pickle_save(self, None)
            return base64.b64encode(pickle_bytes).decode("ascii")

        if output_format == "json":
            result = json.dumps(obj, indent=kwargs.get("indent", 2), default=str)
            if path:
                Path(path).write_text(result, encoding="utf-8")
        elif output_format == "yaml":
            import yaml

            result = yaml.dump(obj, **kwargs)
            if path:
                Path(path).write_text(result, encoding="utf-8")
        elif output_format == "pickle":
            from rankevolve.src.utils.io_utils.pickle_io import pickle_save

            if path:
                pickle_save(obj, str(path))
            pickle_bytes = pickle_save(obj, None)
            return base64.b64encode(pickle_bytes).decode("ascii")

        return result

    @classmethod
    def deserialize(
        cls, source: Union[str, Path, bytes], output_format: str = "json", **context
    ) -> "Serializable":
        """Deserialize from file path or string."""
        if output_format not in ("json", "yaml", "pickle"):
            raise ValueError(f"Unsupported format: {output_format}")

        if output_format == "pickle":
            if isinstance(source, bytes):
                return pickle.loads(source)
            path_obj = Path(source) if isinstance(source, str) else source
            if path_obj.exists():
                return pickle.loads(path_obj.read_bytes())
            return pickle.loads(base64.b64decode(source))

        path_obj = Path(source) if isinstance(source, str) else source
        if isinstance(path_obj, Path) and path_obj.exists():
            content = path_obj.read_text(encoding="utf-8")
        else:
            content = str(source)

        if output_format == "json":
            obj = json.loads(content)
        elif output_format == "yaml":
            import yaml

            obj = yaml.safe_load(content)

        return cls.from_serializable_obj(obj, **context)
