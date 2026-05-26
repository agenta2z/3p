"""
Argument registrar for handling argument registration with ArgumentParser.
"""

from argparse import ArgumentParser
from functools import partial
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from python_utils.common_utils.typing_helper import (
    bool_,
    element_type,
    map_iterable_elements,
    nonstr_iterable,
)
from python_utils.string_utils.parsing import (
    parse_with_predefined_convert,
    PreDefinedArgConverters,
)


def _default_converter_multiple_values(x, ctype, vtype, converter):
    """
    Default converter for container types (list, tuple, set).

    Handles both iterable and single-value inputs, converting elements
    to the appropriate type.

    Args:
        x: Input value (iterable or single)
        ctype: Container type (list, tuple, or set)
        vtype: Element type
        converter: Optional converter for elements

    Returns:
        Container of converted values
    """
    if converter is None:
        if nonstr_iterable(x):
            return ctype(map_iterable_elements(x, vtype))
        else:
            return ctype([vtype(x)])
    else:
        if nonstr_iterable(x):
            return ctype(map_iterable_elements(x, vtype))
        else:
            return ctype([converter(x)])


class ArgumentRegistrar:
    """
    Handles argument registration with ArgumentParser.

    Responsibilities:
    - Register arguments with proper types and defaults
    - Handle boolean flag arguments (store_true for False defaults)
    - Track converters for post-parse processing
    - Manage name deduplication
    - Handle exposed_args (hidden args feature)
    - Handle required_args (required argument group)
    - IPython detection (skip required in IPython)
    """

    def __init__(
        self,
        parser: ArgumentParser,
        replace_double_underscore_with_dash: bool = True,
        exposed_args: Optional[List[str]] = None,
        required_args: Optional[List[str]] = None,
        is_ipython: bool = False,
    ):
        """
        Initialize the argument registrar.

        Args:
            parser: ArgumentParser instance to register arguments with
            replace_double_underscore_with_dash: If True, replace '__' with '-' in CLI names
            exposed_args: If provided, only these args are shown; others are hidden
            required_args: List of argument names that are required
            is_ipython: If True, skip required_args enforcement (IPython compatibility)
        """
        self.parser = parser
        self.replace_double_underscore_with_dash = replace_double_underscore_with_dash
        self.exposed_args = set(exposed_args) if exposed_args else None
        self.required_args = set(required_args) if required_args else None
        self.is_ipython = is_ipython

        # Tracking state
        self.converters: Dict[str, Callable] = {}
        self.full_name_set: Set[str] = set()
        self.short_name_set: Set[str] = set()
        self.sanitized_to_original_map: Dict[str, str] = {}
        self.hidden_args: List[Tuple[str, Any]] = []

        # Create required argument group if needed
        self._required_group = None
        if not is_ipython and required_args:
            self._required_group = parser.add_argument_group("required arguments")

    def _get_cli_name(self, full_name: str) -> str:
        """Convert argument name to CLI format."""
        if self.replace_double_underscore_with_dash:
            return full_name.replace("__", "-")
        return full_name

    def _build_description(
        self, description: str, default_value: Any, is_required: bool
    ) -> str:
        """Build argument description with default value info."""
        if is_required:
            return description
        if description:
            default_str = (
                f"'{default_value}'" if isinstance(default_value, str) else f"{default_value}"
            )
            return f"{description}; the default value is {default_str}"
        return description

    def _is_required(self, full_name: str) -> bool:
        """Check if argument should be marked as required."""
        if self.is_ipython:
            return False
        return self.required_args is not None and full_name in self.required_args

    def _is_hidden(self, full_name: str) -> bool:
        """Check if argument should be hidden (exposed_args feature)."""
        return self.exposed_args is not None and full_name not in self.exposed_args

    def register_argument(
        self,
        full_name: str,
        short_name: str,
        default_value: Any,
        description: str = "",
        converter: Optional[Callable] = None,
    ) -> bool:
        """
        Register a single argument with the parser.

        Args:
            full_name: Full argument name
            short_name: Short argument name
            default_value: Default value (used for type inference)
            description: Argument description
            converter: Optional converter function

        Returns:
            True if registered, False if duplicate
        """
        # Skip if already registered
        if full_name in self.full_name_set:
            return False

        # Handle hidden args (exposed_args feature)
        if self._is_hidden(full_name):
            self.hidden_args.append((full_name, default_value))
            self.full_name_set.add(full_name)
            return True

        is_required = self._is_required(full_name)
        cli_name = self._get_cli_name(full_name)
        desc = self._build_description(description, default_value, is_required)

        # Try to update existing argument default first
        if self._update_existing_argument(full_name, default_value):
            self.full_name_set.add(full_name)
            if converter is not None:
                self._register_converter(full_name, default_value, converter)
            return True

        # Register new argument
        if converter is not None:
            self._register_with_converter(
                full_name, short_name, cli_name, default_value, desc, converter, is_required
            )
        else:
            self._register_without_converter(
                full_name, short_name, cli_name, default_value, desc, is_required
            )

        self.full_name_set.add(full_name)
        self.short_name_set.add(short_name)
        return True

    def _update_existing_argument(self, full_name: str, default_value: Any) -> bool:
        """
        Try to update an existing argument's default value.

        Args:
            full_name: Argument name
            default_value: New default value

        Returns:
            True if argument existed and was updated
        """
        from python_utils.common_utils.arg_utils.arg_parse import update_argument_default

        return update_argument_default(
            arg_parser=self.parser,
            arg_name=full_name,
            arg_default_value=default_value,
        )

    def _register_converter(
        self, full_name: str, default_value: Any, converter: Callable
    ) -> None:
        """Register converter for an argument."""
        # Handle PreDefinedArgConverters enum
        if isinstance(converter, PreDefinedArgConverters):
            converter = partial(parse_with_predefined_convert, converter=converter)

        if not callable(converter):
            raise ValueError(f"converter must be a callable; got '{converter}'")

        if isinstance(default_value, (tuple, list, set)):
            self.converters[full_name] = partial(
                _default_converter_multiple_values,
                ctype=type(default_value),
                vtype=element_type(default_value),
                converter=converter,
            )
        else:
            self.converters[full_name] = converter

    def _register_with_converter(
        self,
        full_name: str,
        short_name: str,
        cli_name: str,
        default_value: Any,
        description: str,
        converter: Callable,
        is_required: bool,
    ) -> None:
        """Register argument with a custom converter."""
        # Register the converter
        self._register_converter(full_name, default_value, converter)

        # Add argument to parser (as string type, converter applied post-parse)
        target_group = self._required_group if is_required else self.parser

        if is_required:
            target_group.add_argument(
                "-" + short_name,
                "--" + cli_name,
                help=description,
                type=str,
                required=True,
            )
        else:
            self.parser.add_argument(
                "-" + short_name,
                "--" + cli_name,
                help=description,
                default=default_value,
                type=str,
            )

    def _register_without_converter(
        self,
        full_name: str,
        short_name: str,
        cli_name: str,
        default_value: Any,
        description: str,
        is_required: bool,
    ) -> None:
        """Register argument without a custom converter (type inference from default)."""
        arg_value_type = type(default_value)

        # Boolean False -> store_true action
        if arg_value_type is bool and not default_value:
            self.parser.add_argument(
                "-" + short_name,
                "--" + cli_name,
                help=description,
                required=False,
                action="store_true",
            )
            return

        # Register type-based converters
        if arg_value_type in (int, float):
            self.converters[full_name] = arg_value_type
        elif arg_value_type is bool:
            # Boolean True -> bool_ converter
            self.converters[full_name] = bool_
        elif arg_value_type in (tuple, list, set):
            self.converters[full_name] = partial(
                _default_converter_multiple_values,
                ctype=type(default_value),
                vtype=element_type(default_value),
                converter=None,
            )

        # Add argument to parser
        target_group = self._required_group if is_required else self.parser

        if is_required:
            target_group.add_argument(
                "-" + short_name,
                "--" + cli_name,
                help=description,
                required=True,
            )
        else:
            self.parser.add_argument(
                "-" + short_name,
                "--" + cli_name,
                help=description,
                default=default_value,
            )
