"""
Value converter for post-parse argument processing.
"""

import ast
import os
from argparse import Namespace
from typing import Any, Callable, Dict, Optional


class ValueConverter:
    """
    Handles post-parse value conversion for parsed arguments.

    Responsibilities:
    - Parse strings as tuples/lists/dicts via ast.literal_eval
    - Apply registered converters
    - Variable substitution ($varname from constants/env)
    - Boolean string parsing ("true"/"false")
    - "none"/"null" to None conversion
    """

    def __init__(
        self,
        converters: Dict[str, Callable],
        sanitized_to_original_map: Optional[Dict[str, str]] = None,
        constants: Optional[Any] = None,
        force_parse_boolstr: bool = True,
    ):
        """
        Initialize the value converter.

        Args:
            converters: Dictionary mapping argument names to converter functions
            sanitized_to_original_map: Mapping from sanitized names to original names
            constants: Optional object for variable substitution ($varname)
            force_parse_boolstr: If True, parse "true"/"false" strings as booleans
        """
        self.converters = converters
        self.sanitized_to_original_map = sanitized_to_original_map or {}
        self.constants = constants
        self.force_parse_boolstr = force_parse_boolstr

    def convert_all(self, args: Namespace) -> Namespace:
        """
        Convert all argument values in the namespace.

        Args:
            args: Parsed argument namespace

        Returns:
            Namespace with converted values
        """
        for arg_name, arg_val in vars(args).items():
            original_name = self.sanitized_to_original_map.get(arg_name, arg_name)
            converted = self._convert_value(arg_name, original_name, arg_val)
            setattr(args, arg_name, converted)
        return args

    def _convert_value(self, arg_name: str, original_name: str, arg_val: Any) -> Any:
        """
        Convert a single argument value.

        Args:
            arg_name: The argument name (potentially sanitized)
            original_name: The original argument name (for converter lookup)
            arg_val: The argument value to convert

        Returns:
            Converted value
        """
        if isinstance(arg_val, str):
            return self._convert_string_value(arg_val, original_name)
        elif original_name in self.converters:
            return self._apply_converter_to_nonstring(arg_val, original_name)
        return arg_val

    def _convert_string_value(self, arg_val: str, original_name: str) -> Any:
        """
        Convert a string argument value.

        Handles:
        - Stripping whitespace
        - De-quoting (removing surrounding quotes)
        - Parsing as tuple/list/dict via ast.literal_eval
        - Applying converters
        - Variable substitution and special string handling

        Args:
            arg_val: String value to convert
            original_name: Original argument name for converter lookup

        Returns:
            Converted value
        """
        # Strip whitespace
        stripped = arg_val.strip()
        if stripped:
            arg_val = stripped

        # De-quote: remove surrounding quotes
        if arg_val and arg_val[0] in ("'", '"') and arg_val[-1] in ("'", '"'):
            arg_val = arg_val[1:-1]

        # Parse tuple
        if len(arg_val) >= 2 and arg_val[0] == "(" and arg_val[-1] == ")":
            arg_val = ast.literal_eval(arg_val)
            converter = self.converters.get(original_name)
            if converter is not None:
                arg_val = converter(arg_val)

        # Parse list
        elif len(arg_val) >= 2 and arg_val[0] == "[" and arg_val[-1] == "]":
            arg_val = ast.literal_eval(arg_val)
            converter = self.converters.get(original_name)
            if converter is not None:
                arg_val = converter(arg_val)

        # Parse dict
        elif len(arg_val) >= 2 and arg_val[0] == "{" and arg_val[-1] == "}":
            arg_val = ast.literal_eval(arg_val)
            converter = self.converters.get(original_name)
            if converter is not None:
                # Dict converter takes (k, v) and returns (k, v)
                arg_val = dict(converter(k, v) for k, v in arg_val.items())

        # Apply converter to plain string
        elif original_name in self.converters:
            arg_val = self.converters[original_name](arg_val)

        # Apply variable substitution and special handling
        return self._process_arg_val(arg_val)

    def _apply_converter_to_nonstring(self, arg_val: Any, original_name: str) -> Any:
        """
        Apply converter to non-string value.

        Args:
            arg_val: Non-string value to convert
            original_name: Argument name for converter lookup

        Returns:
            Converted value
        """
        converter = self.converters.get(original_name)
        if converter is None:
            return arg_val

        if isinstance(arg_val, (list, set, tuple)):
            arg_val = converter(arg_val)
        elif isinstance(arg_val, dict):
            # Dict converter takes (k, v) and returns (k, v)
            arg_val = dict(converter(k, v) for k, v in arg_val.items())
        else:
            arg_val = converter(arg_val)

        return arg_val

    def _process_arg_val(self, arg_val: Any) -> Any:
        """
        Process argument value for variable substitution and special handling.

        Handles:
        - Variable substitution: $varname from constants or os.environ
        - "none"/"null" to None conversion
        - Boolean string parsing when force_parse_boolstr is True

        Args:
            arg_val: Value to process

        Returns:
            Processed value
        """
        if not isinstance(arg_val, str):
            return arg_val

        # Variable substitution from constants
        if self.constants is not None:
            attr_pairs = []
            for attr_name in dir(self.constants):
                if attr_name[0] != "_":
                    attr_pairs.append((attr_name, str(getattr(self.constants, attr_name))))
            # Sort by length descending to replace longer names first
            attr_pairs.sort(key=lambda x: (len(x[0]), x[0]), reverse=True)
            for attr_name, attr_val in attr_pairs:
                arg_val = arg_val.replace(f"${attr_name}", attr_val)

        # Variable substitution from environment
        for attr_name, attr_val in sorted(
            os.environ.items(), key=lambda x: (len(x[0]), x[0]), reverse=True
        ):
            arg_val = arg_val.replace(f"${attr_name}", attr_val)

        # "none" or "null" -> None
        if arg_val == "none" or arg_val == "null":
            return None

        # Boolean string parsing
        if self.force_parse_boolstr:
            if arg_val.lower() == "false":
                return False
            elif arg_val.lower() == "true":
                return True

        return arg_val
