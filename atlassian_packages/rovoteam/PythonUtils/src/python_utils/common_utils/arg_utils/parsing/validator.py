"""
Argument validator for validating parsed arguments.
"""

from argparse import Namespace
from typing import Iterable, Optional


class ArgumentValidator:
    """
    Validates parsed arguments.

    Currently supports:
    - non_empty_args validation (ensuring certain arguments are not empty)
    """

    def __init__(self, non_empty_args: Optional[Iterable[str]] = None):
        """
        Initialize the validator.

        Args:
            non_empty_args: Iterable of argument names that must not be empty
        """
        self.non_empty_args = set(non_empty_args) if non_empty_args else set()

    def validate(self, args: Namespace) -> None:
        """
        Validate all constraints on the parsed arguments.

        Args:
            args: Parsed argument namespace

        Raises:
            ValueError: If validation fails
        """
        self._validate_non_empty(args)

    def _validate_non_empty(self, args: Namespace) -> None:
        """
        Validate that non_empty_args are not empty.

        Boolean values are exempt from this check (False is considered valid).

        Args:
            args: Parsed argument namespace

        Raises:
            ValueError: If a required argument is empty
        """
        for arg_name in self.non_empty_args:
            arg_val = getattr(args, arg_name, None)
            # Boolean values are exempt from non-empty check
            if not isinstance(arg_val, bool) and not bool(arg_val):
                raise ValueError(f"the argument `{arg_name}` is empty")
