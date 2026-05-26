"""
Console Utilities Package

Automatically selects the best available implementation:
- Tries Rich-based implementation first (rich_console_utils)
- Falls back to colorama-based implementation (colorama_console_utils)
- Textual features are optional (requires textual package)

This design allows minimal dependencies (colorama only) with optional
enhanced features (Rich formatting, Textual interactive TUI).

Usage:
    # Core functions work with both backends
    from python_utils.console_utils import hprint_message, hprint_pairs
    hprint_message('Processing', 'file.csv')
    hprint_pairs('metric1', 100, 'metric2', 200, title='Results')

    # Rich-specific features (only available with Rich)
    from python_utils.console_utils import print_table, console
    if print_table is not None:
        print_table(data, title='Results')

    # Textual-based interactive TUI (only available with Textual)
    from python_utils.console_utils import prompt_confirm
    if prompt_confirm is not None:
        if prompt_confirm('Delete file?'):
            # do something
            pass

    # Check which backend is active
    from python_utils.console_utils import __backend__, __has_textual__
    print(f"Using backend: {__backend__}")
    print(f"Textual available: {__has_textual__}")

Backend Selection:
    # Force a specific backend by setting environment variable BEFORE import
    import os
    os.environ['CONSOLE_UTILS_BACKEND'] = 'colorama'  # or 'rich'
    from python_utils.console_utils import hprint_message

Author: Science Python Utils
Date: 2025-01-15
"""

import os as _os

# Check if user wants to force a specific backend
_FORCE_BACKEND = _os.getenv('CONSOLE_UTILS_BACKEND', '').lower()

# Try Rich implementation first (unless colorama is forced), fall back to colorama
_skip_rich = (_FORCE_BACKEND == 'colorama')

try:
    if _skip_rich:
        raise ImportError("Rich backend skipped by CONSOLE_UTILS_BACKEND=colorama")
    from .rich_console_utils import (
        # Message printing
        hprint_message,
        eprint_message,
        wprint_message,
        cprint_message,

        # Pairs printing
        hprint_pairs,
        eprint_pairs,
        wprint_pairs,
        cprint_pairs,

        # Section formatting
        hprint_section_title,
        cprint_section_separator,
        hprint_section_separator,
        eprint_section_separator,
        wprint_section_separator,

        # Panel printing
        cprint_panel,
        hprint_panel,
        eprint_panel,
        wprint_panel,

        # Rich-specific features
        print_table,
        print_syntax,
        print_markdown,
        print_json,
        progress_bar,
        get_rich_logger,

        # Utilities
        print_attrs,
        retrieve_and_print_attrs,
        checkpoint,
        clear_message,  # Message tracking utility

        # Console instance
        console,

        # Internal capability flags
        _CURSOR_CONTROL_SUPPORTED,
    )

    _BACKEND = "rich"

except ImportError as e:
    # Fall back to colorama implementation
    import warnings
    warnings.warn(
        f"Rich library not available ({e}), falling back to colorama-based console utils. "
        "Install 'rich' for enhanced formatting features.",
        ImportWarning
    )

    from .colorama_console_utils import (
        # Message printing
        hprint_message,
        eprint_message,
        wprint_message,
        cprint_message,

        # Pairs printing
        hprint_pairs,
        eprint_pairs,
        wprint_pairs,
        cprint_pairs,

        # Section formatting
        hprint_section_title,
        hprint_section_separator,

        # Utilities
        print_attrs,
        retrieve_and_print_attrs,
        checkpoint,
        clear_message,  # Message tracking utility

        # Internal capability flags
        _CURSOR_CONTROL_SUPPORTED,
    )

    # Import colorama-specific functions for compatibility
    try:
        from .colorama_console_utils import (
            eprint_section_separator,
            wprint_section_separator,
            cprint_section_separator,
        )
    except ImportError:
        # If these don't exist in colorama version, create stubs
        def eprint_section_separator():
            print()

        def wprint_section_separator():
            print()

        def cprint_section_separator(title_color=None, title_style=None):
            print()

    _BACKEND = "colorama"

    # Rich-specific features are not available
    print_table = None
    print_syntax = None
    print_markdown = None
    print_json = None
    progress_bar = None
    get_rich_logger = None
    cprint_panel = None
    hprint_panel = None
    eprint_panel = None
    wprint_panel = None
    console = None

# Optional Textual interactive features
try:
    from .textual_console_utils import (
        # Prompts
        prompt_confirm,
        prompt_choice,
        prompt_input,

        # Display
        display_table,
        display_help,
        show_notification,

        # Apps (for advanced usage)
        ProgressDashboard,
        InteractiveTable,
        LogViewer,
        LiveMetrics,
    )
    _HAS_TEXTUAL = True

except ImportError as e:
    import warnings
    warnings.warn(
        f"Textual library not available ({e}). "
        "Install 'textual' for interactive TUI features.",
        ImportWarning
    )

    _HAS_TEXTUAL = False

    # Textual features not available
    prompt_confirm = None
    prompt_choice = None
    prompt_input = None
    display_table = None
    display_help = None
    show_notification = None
    ProgressDashboard = None
    InteractiveTable = None
    LogViewer = None
    LiveMetrics = None

# Export backend info for debugging/feature detection
__backend__ = _BACKEND
__has_textual__ = _HAS_TEXTUAL
__version__ = '1.0.0'

# Backward compatibility aliases
hprint = hprint_message
eprint = eprint_message
wprint = wprint_message
cprint = cprint_message

__all__ = [
    # Core functions (available in both backends)
    'hprint_message',
    'eprint_message',
    'wprint_message',
    'cprint_message',
    'hprint_pairs',
    'eprint_pairs',
    'wprint_pairs',
    'cprint_pairs',
    'hprint_section_title',
    'hprint_section_separator',
    'eprint_section_separator',
    'wprint_section_separator',
    'print_attrs',
    'retrieve_and_print_attrs',
    'checkpoint',
    'clear_message',  # Message tracking utility

    # Backward compatibility aliases
    'hprint',
    'eprint',
    'wprint',
    'cprint',

    # Rich-specific (None if Rich not available)
    'cprint_section_separator',
    'cprint_panel',
    'hprint_panel',
    'eprint_panel',
    'wprint_panel',
    'print_table',
    'print_syntax',
    'print_markdown',
    'print_json',
    'progress_bar',
    'get_rich_logger',
    'console',

    # Textual-specific (None if Textual not available)
    'prompt_confirm',
    'prompt_choice',
    'prompt_input',
    'display_table',
    'display_help',
    'show_notification',
    'ProgressDashboard',
    'InteractiveTable',
    'LogViewer',
    'LiveMetrics',

    # Metadata
    '__backend__',
    '__has_textual__',
    '__version__',

    # Internal capability flags
    '_CURSOR_CONTROL_SUPPORTED',

    # Backend selection utilities
    'get_available_backends',
    'get_current_backend',
]


# Backend selection utility functions
def get_available_backends():
    """
    Get list of available console backends.

    Returns:
        list: Available backends ('rich', 'colorama')
    """
    backends = ['colorama']  # colorama is always available (required dependency)
    try:
        import rich
        backends.insert(0, 'rich')  # rich is preferred if available
    except ImportError:
        pass
    return backends


def get_current_backend():
    """
    Get the currently active backend.

    Returns:
        str: Current backend name ('rich' or 'colorama')
    """
    return __backend__
