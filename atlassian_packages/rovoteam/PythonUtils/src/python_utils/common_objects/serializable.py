"""
Serializable mixin providing pluggable serialization support.

This module provides a Serializable abstract mixin class that enables consistent
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
    
    PREFER_CLEAR_TEXT = 'prefer_clear_text'
    """Try dict/JSON first, fall back to pickle if not possible."""
    
    PREFER_BINARY = 'prefer_binary'
    """Always use pickle (binary) serialization."""


# Constants for serializable object field names
FIELD_TYPE = '_type'           # Class name
FIELD_MODULE = '_module'       # Module path
FIELD_SERIALIZATION = '_serialization'  # Serialization method used
FIELD_DATA = '_data'           # Dict data (when serialization='dict')
FIELD_PICKLE_DATA = '_pickle_data'  # Base64 pickle (when serialization='pickle')

# Serialization method values
SERIALIZATION_DICT = 'dict'
SERIALIZATION_PICKLE = 'pickle'


class Serializable:
    """Mixin providing pluggable serialization support with auto-detection.
    
    This is a concrete class with intelligent default serialization:
    - Auto-detects if class is suitable for dict/JSON serialization (dataclass, attrs, etc.)
    - Falls back to pickle for complex objects
    - Subclasses can override for custom serialization logic
    
    Attributes:
        auto_mode: Controls automatic serialization behavior.
            - SerializationMode.PREFER_CLEAR_TEXT (default): Try dict first, pickle fallback
            - SerializationMode.PREFER_BINARY: Always use pickle
    
    Auto-detection (when PREFER_CLEAR_TEXT):
    - Uses dict__(obj, fallback=None) which handles dataclass, attrs, __dict__, __slots__
    - Falls back to pickle if dict__ raises TypeError
    """
    
    # Class attribute to control serialization preference
    auto_mode: SerializationMode = SerializationMode.PREFER_CLEAR_TEXT
    
    def _to_dict_auto(self) -> Dict[str, Any]:
        """Auto-convert to dict using existing dict__ utility.
        
        Leverages python_utils.common_utils.map_helper.dict__ which handles:
        - Dataclasses
        - Attrs classes
        - Named tuples
        - Objects with __dict__
        - Objects with __slots__
        - Circular references
        
        Uses fallback=None to raise TypeError for non-convertible objects,
        allowing the caller to fall back to pickle serialization.
        
        Returns:
            Dict representation of the object.
            
        Raises:
            TypeError: If object cannot be converted to dict.
        """
        from python_utils.common_utils.map_helper import dict__
        return dict__(self, recursive=True, fallback=None)

    def to_serializable_obj(
        self, 
        mode: str = 'auto',
        _output_format: Optional[str] = None
    ) -> Union[Dict[str, Any], 'Serializable']:
        """Convert to serializable Python object.
        
        Args:
            mode: Serialization mode:
                - 'auto': Auto-detect best method (dict if possible, else return self for pickle)
                - 'dict': Force dict-based serialization (raises if not possible)
                - 'pickle': Return self (the object itself is the serializable form)
            _output_format: (Private) Target output format for early conflict detection.
                If 'json' or 'yaml' and dict conversion fails, raises TypeError.
        
        Returns:
            - Dict with '_data' key if dict serialization succeeds
            - self if pickle fallback is needed (mode='auto' or 'pickle')
            
        Raises:
            TypeError: If mode='dict' and object cannot be converted to dict
            TypeError: If _output_format is 'json'/'yaml' but object can only be pickled
        """
        # For pickle mode, return self directly
        if mode == 'pickle':
            return self
        
        # Try dict-based serialization (dict__ raises TypeError if not possible)
        prefer_clear = self.auto_mode == SerializationMode.PREFER_CLEAR_TEXT
        if mode in ('dict', 'auto') and prefer_clear:
            try:
                data = self._to_dict_auto()
                return {
                    FIELD_TYPE: type(self).__name__,
                    FIELD_MODULE: type(self).__module__,
                    FIELD_SERIALIZATION: SERIALIZATION_DICT,
                    FIELD_DATA: data
                }
            except TypeError as e:
                if mode == 'dict':
                    raise TypeError(
                        f"Cannot serialize {type(self).__name__} as dict: {e}. "
                        f"Use mode='auto' or 'pickle'."
                    ) from e
                # Check for conflict with output format
                if _output_format in ('json', 'yaml'):
                    raise TypeError(
                        f"Cannot serialize {type(self).__name__} to {_output_format}: "
                        f"object requires pickle but output_format='{_output_format}'. "
                        f"Use output_format='pickle' instead."
                    ) from e
                # Fall through to pickle fallback for auto mode
        
        # Fall back to returning self for pickle serialization
        return self

    @classmethod
    def from_serializable_obj(
        cls, 
        obj: Dict[str, Any], 
        **context
    ) -> 'Serializable':
        """Create instance from serializable Python object.
        
        Auto-detects serialization method from dict structure:
        - '_data' key: dict-based reconstruction
        - '_pickle_data' key: pickle-based reconstruction
        
        Override in subclasses for custom dict-based deserialization.
        
        Args:
            obj: The serializable object (dict)
            **context: Additional context needed for reconstruction
                (e.g., action_executor, action_metadata)
                
        Returns:
            Reconstructed instance
            
        Raises:
            TypeError: If object cannot be deserialized
            ValueError: If dict format is invalid
        """
        serialization = obj.get(FIELD_SERIALIZATION, SERIALIZATION_PICKLE)
        
        if serialization == SERIALIZATION_DICT and FIELD_DATA in obj:
            # Dict-based reconstruction
            data = obj[FIELD_DATA]
            
            # Try dataclass reconstruction
            if dataclasses.is_dataclass(cls):
                return cls(**data)
            
            # Try attrs reconstruction
            try:
                import attr
                if attr.has(cls):
                    return cls(**data)
            except ImportError:
                pass
            
            # Try generic __init__ with dict
            try:
                return cls(**data)
            except TypeError:
                # Fall back to creating instance and setting __dict__
                instance = object.__new__(cls)
                instance.__dict__.update(data)
                return instance
        
        if FIELD_PICKLE_DATA in obj:
            try:
                pickle_bytes = base64.b64decode(obj[FIELD_PICKLE_DATA])
                return pickle.loads(pickle_bytes)
            except (pickle.UnpicklingError, TypeError) as e:
                raise TypeError(
                    f"Cannot deserialize {obj.get(FIELD_TYPE, 'unknown')}: {e}. "
                    f"Override from_serializable_obj() for custom deserialization."
                ) from e
        
        raise ValueError(
            f"Invalid serializable object format. Expected '{FIELD_DATA}' or '{FIELD_PICKLE_DATA}' key "
            f"or override from_serializable_obj() for custom format."
        )

    def serialize(
        self, 
        output_format: str = 'json', 
        path: Optional[Union[str, Path]] = None, 
        serializable_obj_mode: str = 'auto',
        **kwargs
    ) -> str:
        """Serialize to specified format.
        
        Consistent flow for all formats:
        1. Call to_serializable_obj() with output_format for early conflict detection
        2. If result is self (not a dict), use pickle
        3. Otherwise encode dict to target format
        
        Args:
            output_format: Output format ('json', 'yaml', or 'pickle')
            path: Optional file path to write result
            serializable_obj_mode: Mode for to_serializable_obj ('auto', 'dict', 'pickle')
                  For output_format='pickle', mode is automatically set to 'pickle'
            **kwargs: Format-specific options (e.g., indent for JSON)
            
        Returns:
            Serialized string (or base64 for pickle)
            
        Raises:
            ValueError: If output_format is not supported
            TypeError: If output_format requires dict but object can only be pickled
        """
        # Validate format early
        if output_format not in ('json', 'yaml', 'pickle'):
            raise ValueError(
                f"Unsupported format: {output_format}. Supported: 'json', 'yaml', 'pickle'"
            )
        
        # For pickle format, force pickle mode
        effective_mode = 'pickle' if output_format == 'pickle' else serializable_obj_mode
        
        # Get serializable object with output_format for conflict detection
        obj = self.to_serializable_obj(
            mode=effective_mode,
            _output_format=output_format
        )
        
        # If obj is self (not a dict), use pickle
        if obj is self:
            from python_utils.io_utils.pickle_io import pickle_save
            # pickle_save returns bytes if path is None
            if path:
                pickle_save(self, str(path))
                # Read back and encode for return value
                pickle_bytes = pickle_save(self, None)
            else:
                pickle_bytes = pickle_save(self, None)
            return base64.b64encode(pickle_bytes).decode('ascii')
        
        # obj is a dict, encode to requested format
        if output_format == 'json':
            result = json.dumps(obj, indent=kwargs.get('indent', 2), default=str)
            if path:
                Path(path).write_text(result, encoding='utf-8')
        elif output_format == 'yaml':
            import yaml
            result = yaml.dump(obj, **kwargs)
            if path:
                Path(path).write_text(result, encoding='utf-8')
        elif output_format == 'pickle':
            # Dict can also be pickled
            from python_utils.io_utils.pickle_io import pickle_save
            if path:
                pickle_save(obj, str(path))
            pickle_bytes = pickle_save(obj, None)
            return base64.b64encode(pickle_bytes).decode('ascii')
        
        return result

    @classmethod
    def deserialize(
        cls, 
        source: Union[str, Path, bytes], 
        output_format: str = 'json', 
        **context
    ) -> 'Serializable':
        """Deserialize from file path or string.
        
        Args:
            source: File path, serialized string, or bytes
            output_format: Input format ('json', 'yaml', or 'pickle')
            **context: Additional context for reconstruction
            
        Returns:
            Reconstructed instance
            
        Raises:
            ValueError: If format is not supported
        """
        # Validate format early
        if output_format not in ('json', 'yaml', 'pickle'):
            raise ValueError(
                f"Unsupported format: {output_format}. Supported: 'json', 'yaml', 'pickle'"
            )
        
        if output_format == 'pickle':
            if isinstance(source, bytes):
                return pickle.loads(source)
            path_obj = Path(source) if isinstance(source, str) else source
            if path_obj.exists():
                return pickle.loads(path_obj.read_bytes())
            # Assume base64-encoded string
            return pickle.loads(base64.b64decode(source))
        
        # Try to interpret as file path first
        path_obj = Path(source) if isinstance(source, str) else source
        
        if isinstance(path_obj, Path) and path_obj.exists():
            content = path_obj.read_text(encoding='utf-8')
        else:
            content = str(source)
        
        if output_format == 'json':
            obj = json.loads(content)
        elif output_format == 'yaml':
            import yaml
            obj = yaml.safe_load(content)
        
        return cls.from_serializable_obj(obj, **context)
