"""Stub for console_utils — replaces Rich/colorama/Textual dependency chain."""

__backend__ = "stub"


def hprint_message(*args, **kwargs):
    """Print with optional header formatting. Stub: falls through to print()."""
    print(*args)


def hprint(*args, **kwargs):
    """Print with optional formatting. Stub: falls through to print()."""
    print(*args)
