"""
Rich-based console utility module.

A modern replacement for console_util.py using the Rich library.
Provides colored console output, tables, progress bars, and more.

Author: Science Python Utils
Date: 2025-01-15
"""

import logging
import time
import sys
from typing import Any, List, Tuple, Optional, Dict, Union
from contextlib import contextmanager
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
from rich.logging import RichHandler
from rich.text import Text
from rich.theme import Theme
from rich import print as rprint
from rich.pretty import Pretty
import json

# Detect cursor control support
_CURSOR_CONTROL_SUPPORTED = False
if sys.platform == 'win32':
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        _CURSOR_CONTROL_SUPPORTED = True
    except Exception:
        pass
else:
    _CURSOR_CONTROL_SUPPORTED = sys.stdout.isatty()

# Detect if we're in PyCharm or other limited terminal
import os
if os.getenv('PYCHARM_HOSTED') or 'PYCHARM' in os.getenv('TERMINAL_EMULATOR', ''):
    _CURSOR_CONTROL_SUPPORTED = False

# Track displayed messages for in-place updates
_displayed_messages: Dict[str, Dict[str, Any]] = {}
# Format: {message_id: {'text': str, 'line_count': int, 'timestamp': float}}

# Enable ANSI color support on Windows
try:
    from python_utils.console_utils.enable_windows_ansi import enable_windows_ansi_support
    enable_windows_ansi_support()
except ImportError:
    pass  # Module not available, colors may not work on Windows console

# Define custom theme matching original console_util colors from basics.py
CUSTOM_THEME = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "red",
    "success": "bold green",
    "highlight": "bright_cyan",
    "title": "cyan",
    "content": "white",
    "key": "bright_cyan",
    "value": "white",
})

# Global console instance
# force_terminal=True ensures colors are always output (useful for Windows terminals)
# legacy_windows=False uses modern ANSI codes instead of legacy Windows API
console = Console(theme=CUSTOM_THEME, force_terminal=True, legacy_windows=False)

# Color constants for backward compatibility with basics.py
HPRINT_TITLE_COLOR = "cyan"
HPRINT_HEADER_OR_HIGHLIGHT_COLOR = "bright_cyan"
HPRINT_MESSAGE_BODY_COLOR = "white"

EPRINT_TITLE_COLOR = "red"
EPRINT_HEADER_OR_HIGHLIGHT_COLOR = "bright_red"
EPRINT_MESSAGE_BODY_COLOR = "bright_yellow"

WPRINT_TITLE_COLOR = "magenta"
WPRINT_HEADER_OR_HIGHLIGHT_COLOR = "bright_magenta"
WPRINT_MESSAGE_BODY_COLOR = "yellow"

# region Helper Functions

def _format_content(content: Any, replacement_for_empty: str = "n/a") -> str:
    """Format content for display, handling None and empty values."""
    if content is None or content == "":
        return replacement_for_empty
    if not isinstance(content, str):
        return str(content)
    return content


def _count_lines(text: str) -> int:
    """
    Count the number of visual lines that text occupies in the terminal.

    This correctly handles trailing newlines from print(). The text "Status: OK\n"
    occupies 1 visual line, but "Title\n\nContent\n\n" occupies 4 visual lines
    (blank, Title, blank, Content).

    Args:
        text: Text to count lines in

    Returns:
        Number of visual lines in the terminal
    """
    if not text:
        return 0

    # Split by newline to get all segments
    segments = text.split('\n')

    # If text ends with \n, the last segment will be empty and shouldn't be counted
    # (it represents the cursor position after the final newline, not a visual line)
    if segments and segments[-1] == '':
        return len(segments) - 1

    return len(segments)


def _clear_previous_lines(line_count: int):
    """
    Clear N previous lines using ANSI escape codes or Rich control (if supported).

    Args:
        line_count: Number of lines to clear
    """
    if line_count > 0 and _CURSOR_CONTROL_SUPPORTED:
        # Use Rich's console control for clearing lines
        from rich.control import Control

        # Move cursor up and clear lines
        for _ in range(line_count):
            console.file.write('\033[F')  # Move cursor up one line
            console.file.write('\033[K')  # Clear line from cursor to end
        console.file.flush()


def clear_message(message_id: str):
    """
    Clear a tracked message by ID and remove from tracking.

    Args:
        message_id: The ID of the message to clear
    """
    if message_id in _displayed_messages:
        info = _displayed_messages[message_id]
        _clear_previous_lines(info['line_count'])
        del _displayed_messages[message_id]


def _solve_key_value_pairs(*args) -> List[Tuple[str, Any]]:
    """
    Convert variable arguments to list of (key, value) tuples.

    Supports two formats:
    - Tuples: func(('key1', 'val1'), ('key2', 'val2'))
    - Flat args: func('key1', 'val1', 'key2', 'val2')
    """
    if not args:
        return []

    # Check if first arg is a tuple/list
    if isinstance(args[0], (tuple, list)):
        return list(args)

    # Otherwise, pair up sequential arguments
    pairs = []
    for i in range(0, len(args), 2):
        if i + 1 < len(args):
            pairs.append((str(args[i]), args[i + 1]))
        else:
            pairs.append((str(args[i]), ""))
    return pairs

# endregion

# region Backtick Highlighting Helper

def _parse_backtick_highlights(
    text: str,
    color_quote: str = '`',
    highlight_color: str = "cyan",
    bk_color: str = "white",
) -> Text:
    """
    Parse text and create Rich Text object with backtick-highlighted sections.

    Args:
        text: The text to parse
        color_quote: The character used to mark highlights (default: backtick)
        highlight_color: Rich color/style for highlighted text
        bk_color: Rich color/style for non-highlighted (background) text

    Returns:
        Rich Text object with styled highlights
    """
    if not isinstance(text, str):
        text = str(text)

    result = Text()
    color_start = True
    prev_color_quote = False
    current_segment = []

    for c in text:
        if c == color_quote:
            if prev_color_quote:
                # Escaped quote (two consecutive quotes)
                current_segment.append(color_quote)
                prev_color_quote = False
                color_start = True
            elif color_start:
                # Start of highlight - flush any accumulated text first
                if current_segment:
                    result.append(''.join(current_segment), style=bk_color)
                    current_segment = []
                prev_color_quote = True
                color_start = False
            else:
                # End of highlight - flush highlighted text
                if current_segment:
                    result.append(''.join(current_segment), style=highlight_color)
                    current_segment = []
                color_start = True
        else:
            if prev_color_quote:
                # We had a single quote, so we're starting a highlight
                prev_color_quote = False
            current_segment.append(c)

    # Flush any remaining text
    if current_segment:
        style = bk_color if color_start else highlight_color
        result.append(''.join(current_segment), style=style)

    return result

# endregion

# region Backtick-Based Highlighting Functions

def cprint(
    text: str,
    color_quote: str = '`',
    color: str = "cyan",
    bk_color: str = "white",
    end: str = '\n'
):
    """
    Print text with custom color highlighting for sections enclosed in quotes.

    Use two consecutive quotes to escape the quote character.

    Examples:
        >>> cprint("Process `complete`")  # 'complete' is highlighted in cyan
        >>> cprint("File ``test.py`` processed", color_quote='`')  # Literal backticks

    Args:
        text: The text to print
        color_quote: Character marking highlight boundaries (default: backtick)
        color: Rich color/style for highlighted sections
        bk_color: Rich color/style for non-highlighted (background) text
        end: String appended after text (default: newline)
    """
    rich_text = _parse_backtick_highlights(text, color_quote, color, bk_color)
    console.print(rich_text, end=end)


def hprint(text: str, color_quote: str = '`', end: str = '\n'):
    """
    Highlight-print text with cyan highlighting for backtick-enclosed sections.

    Examples:
        >>> hprint("Processing file `data.csv` with `1000` rows")
        >>> hprint("Use ``backticks`` for literal backticks")

    Args:
        text: The text to print
        color_quote: Character marking highlight boundaries (default: backtick)
        end: String appended after text (default: newline)
    """
    cprint(text, color_quote=color_quote, color=HPRINT_HEADER_OR_HIGHLIGHT_COLOR,
           bk_color=HPRINT_MESSAGE_BODY_COLOR, end=end)


def eprint(text: str, color_quote: str = '`', end: str = '\n'):
    """
    Error-print text with red highlighting for backtick-enclosed sections.

    Examples:
        >>> eprint("Error: file `missing.txt` not found")

    Args:
        text: The text to print
        color_quote: Character marking highlight boundaries (default: backtick)
        end: String appended after text (default: newline)
    """
    cprint(text, color_quote=color_quote, color=EPRINT_HEADER_OR_HIGHLIGHT_COLOR,
           bk_color=EPRINT_MESSAGE_BODY_COLOR, end=end)


def wprint(text: str, color_quote: str = '`', end: str = '\n'):
    """
    Warning-print text with yellow highlighting for backtick-enclosed sections.

    Examples:
        >>> wprint("Warning: `deprecated` function used")

    Args:
        text: The text to print
        color_quote: Character marking highlight boundaries (default: backtick)
        end: String appended after text (default: newline)
    """
    cprint(text, color_quote=color_quote, color=WPRINT_HEADER_OR_HIGHLIGHT_COLOR,
           bk_color=WPRINT_MESSAGE_BODY_COLOR, end=end)

# endregion

# region Basic Message Printing

def hprint_message(
    *msg_pairs,
    title: str = "",
    content: str = "",
    message_id: Optional[str] = None,
    update_previous: bool = False,
    logger: Optional[logging.Logger] = None,
    replacement_for_empty_content: str = "n/a",
    **kwargs
):
    """
    Highlight-print one or more messages (cyan/white theme).

    Delegates to cprint_message with highlight-specific color parameters.

    Compatible with original console_util.hprint_message API.

    Examples:
        >>> hprint_message(title='Status', content='Processing')
        >>> hprint_message('metric1', 100, 'metric2', 200)
        >>> hprint_message(
        ...     'file', 'data.csv',
        ...     'rows', 1000,
        ...     title='Data Loading'
        ... )
        >>> # Update in place
        >>> hprint_message(title='Status', content='Step 1/5', message_id='progress')
        >>> hprint_message(title='Status', content='Step 2/5', message_id='progress', update_previous=True)

    Args:
        *msg_pairs: Variable arguments as key-value pairs
        title: Section title (displayed in bold cyan)
        content: Content or comment for the section
        message_id: Optional unique identifier for this message.
                   If provided with update_previous=True, will update
                   the previous message with this ID in place.
        update_previous: If True and message_id is provided and exists,
                        overwrites the previous message instead of
                        printing a new line.
        logger: Optional logger to also log the message
        replacement_for_empty_content: Text to show for empty values
    """
    cprint_message(
        *msg_pairs,
        title=title,
        content=content,
        message_id=message_id,
        update_previous=update_previous,
        title_color=HPRINT_HEADER_OR_HIGHLIGHT_COLOR,
        content_color=HPRINT_MESSAGE_BODY_COLOR,
        logger=logger,
        log_method=logger.info if logger else None,
        replacement_for_empty_content=replacement_for_empty_content,
        **kwargs
    )


def eprint_message(
    *msg_pairs,
    title: str = "",
    content: str = "",
    logger: Optional[logging.Logger] = None,
    replacement_for_empty_content: str = "n/a",
    **kwargs
):
    """
    Error-print messages (red/bright_yellow theme).

    Delegates to cprint_message with error-specific color parameters.

    Examples:
        >>> eprint_message(title='Error', content='File not found')
        >>> eprint_message('error_code', 404, 'reason', 'Not found')
    """
    cprint_message(
        *msg_pairs,
        title=title,
        content=content,
        title_color=EPRINT_HEADER_OR_HIGHLIGHT_COLOR,
        content_color=EPRINT_MESSAGE_BODY_COLOR,
        logger=logger,
        log_method=logger.error if logger else None,
        replacement_for_empty_content=replacement_for_empty_content,
        **kwargs
    )


def wprint_message(
    *msg_pairs,
    title: str = "",
    content: str = "",
    logger: Optional[logging.Logger] = None,
    replacement_for_empty_content: str = "n/a",
    **kwargs
):
    """
    Warning-print messages (magenta/yellow theme).

    Delegates to cprint_message with warning-specific color parameters.

    Examples:
        >>> wprint_message(title='Warning', content='Deprecated function')
    """
    cprint_message(
        *msg_pairs,
        title=title,
        content=content,
        title_color=WPRINT_HEADER_OR_HIGHLIGHT_COLOR,
        content_color=WPRINT_MESSAGE_BODY_COLOR,
        logger=logger,
        log_method=logger.warning if logger else None,
        replacement_for_empty_content=replacement_for_empty_content,
        **kwargs
    )


def cprint_message(
    *msg_pairs,
    title: str = "",
    content: str = "",
    message_id: Optional[str] = None,
    update_previous: bool = False,
    title_color: str = "cyan",
    content_color: str = "white",
    logger: Optional[logging.Logger] = None,
    log_method: Optional[callable] = None,
    replacement_for_empty_content: str = "n/a",
    **kwargs
):
    """
    Custom-color print message with support for both single messages and key-value pairs.

    Examples:
        >>> cprint_message('Status', 'Running', title_color='green', content_color='white')
        >>> cprint_message('metric1', 100, 'metric2', 200, title='Results', title_color='cyan')
        >>> cprint_message('Status', 'Processing', message_id='status', update_previous=True)

    Args:
        *msg_pairs: Variable arguments as key-value pairs
        title: Message title or label
        content: Content or comment for the message
        message_id: Optional unique identifier for this message
        update_previous: If True and message_id exists, update in place
        title_color: Color for title/keys
        content_color: Color for content/values
        logger: Optional logger to also log the message
        log_method: Optional specific log method to use (e.g., logger.error, logger.warning)
        replacement_for_empty_content: Text to show for empty values
    """
    # Check if this is an update operation
    # Only update in place if terminal supports cursor control
    should_update_in_place = (
        message_id and
        update_previous and
        message_id in _displayed_messages and
        _CURSOR_CONTROL_SUPPORTED
    )

    if should_update_in_place:
        # Clear previous lines before printing update
        prev_info = _displayed_messages[message_id]
        _clear_previous_lines(prev_info['line_count'])

    # Capture output to count lines - use a StringIO buffer for Rich console
    from io import StringIO
    from rich.console import Console as RichConsole
    captured_output = StringIO()
    capture_console = RichConsole(file=captured_output, force_terminal=False, width=console.width)

    try:
        if msg_pairs:
            # If msg_pairs provided, use cprint_pairs (which handles message tracking itself)
            cprint_pairs(
                *msg_pairs,
                title=title,
                comment=content,
                first_color=title_color,
                second_color=content_color,
                title_color=title_color,
                title_style="bold",
                title_decoration="====",
                logger=logger,
                replacement_for_empty_content=replacement_for_empty_content,
                message_id=message_id,
                update_previous=update_previous,
                **kwargs
            )
            # cprint_pairs handles message tracking, so we return early
            return
        else:
            # Single message - use capture console
            formatted_content = _format_content(content, replacement_for_empty_content)

            if title:
                text = Text()
                text.append(title, style=title_color)
                if formatted_content:
                    text.append(": ", style="white")
                    text.append(formatted_content, style=content_color)
                capture_console.print(text)
                console.print(text)
            elif formatted_content:
                capture_console.print(formatted_content, style=content_color)
                console.print(formatted_content, style=content_color)

            # Log to logger if provided
            if logger is not None:
                log_msg = f"{title}: {formatted_content}" if title else formatted_content
                if log_method:
                    log_method(log_msg)
                else:
                    logger.info(log_msg)

            # Get captured output
            output_text = captured_output.getvalue()
            line_count = _count_lines(output_text)

    except Exception:
        # Fallback: estimate line count
        output_text = ""
        line_count = 1

    # Track for future updates if message_id provided
    if message_id:
        _displayed_messages[message_id] = {
            'text': output_text,
            'line_count': line_count,
            'timestamp': time.time()
        }

# endregion

# region Pairs Printing

def hprint_pairs(
    *args,
    title: Optional[str] = None,
    comment: Optional[str] = None,
    sep: str = "\t",
    logger: Optional[logging.Logger] = None,
    replacement_for_empty_content: str = "n/a",
    output_title_and_contents: Optional[List] = None,
    message_id: Optional[str] = None,
    update_previous: bool = False,
    section_separator: str = "----",
    **kwargs
):
    """
    Print multiple key-value pairs with optional section title.

    Examples:
        >>> hprint_pairs('name', 'model.pt', 'size', '100MB', 'accuracy', 0.95)
        >>> hprint_pairs(
        ...     'epoch', 10,
        ...     'loss', 0.05,
        ...     title='Training Results'
        ... )
        >>> # Update in place
        >>> hprint_pairs('epoch', 1, 'loss', 0.5, title='Training', message_id='train')
        >>> hprint_pairs('epoch', 2, 'loss', 0.3, title='Training', message_id='train', update_previous=True)
    """
    cprint_pairs(
        *args,
        title=title,
        comment=comment,
        first_color=HPRINT_HEADER_OR_HIGHLIGHT_COLOR,
        second_color=HPRINT_MESSAGE_BODY_COLOR,
        title_color=HPRINT_TITLE_COLOR,
        title_style="bold",
        title_decoration="====",
        sep=sep,
        logger=logger,
        replacement_for_empty_content=replacement_for_empty_content,
        output_title_and_contents=output_title_and_contents,
        message_id=message_id,
        update_previous=update_previous,
        section_separator=section_separator,
        **kwargs
    )


def eprint_pairs(
    *args,
    title: Optional[str] = None,
    comment: Optional[str] = None,
    sep: str = "\t",
    logger: Optional[logging.Logger] = None,
    replacement_for_empty_content: str = "n/a",
    output_title_and_contents: Optional[List] = None,
    message_id: Optional[str] = None,
    update_previous: bool = False,
    section_separator: str = "----",
    **kwargs
):
    """
    Error-print multiple key-value pairs.

    Delegates to cprint_pairs with error-specific color parameters.
    """
    cprint_pairs(
        *args,
        title=title,
        comment=comment,
        first_color=EPRINT_HEADER_OR_HIGHLIGHT_COLOR,
        second_color=EPRINT_MESSAGE_BODY_COLOR,
        title_color=EPRINT_TITLE_COLOR,
        title_style="bold",
        title_decoration="====",
        sep=sep,
        logger=logger,
        replacement_for_empty_content=replacement_for_empty_content,
        output_title_and_contents=output_title_and_contents,
        message_id=message_id,
        update_previous=update_previous,
        section_separator=section_separator,
        **kwargs
    )


def wprint_pairs(
    *args,
    title: Optional[str] = None,
    comment: Optional[str] = None,
    sep: str = "\t",
    logger: Optional[logging.Logger] = None,
    replacement_for_empty_content: str = "n/a",
    output_title_and_contents: Optional[List] = None,
    message_id: Optional[str] = None,
    update_previous: bool = False,
    section_separator: str = "----",
    **kwargs
):
    """
    Warning-print multiple key-value pairs.

    Delegates to cprint_pairs with warning-specific color parameters.
    """
    cprint_pairs(
        *args,
        title=title,
        comment=comment,
        first_color=WPRINT_HEADER_OR_HIGHLIGHT_COLOR,
        second_color=WPRINT_MESSAGE_BODY_COLOR,
        title_color=WPRINT_TITLE_COLOR,
        title_style="bold",
        title_decoration="====",
        sep=sep,
        logger=logger,
        replacement_for_empty_content=replacement_for_empty_content,
        output_title_and_contents=output_title_and_contents,
        message_id=message_id,
        update_previous=update_previous,
        section_separator=section_separator,
        **kwargs
    )


def cprint_pairs(
    *args,
    title: Optional[str] = None,
    comment: Optional[str] = None,
    first_color: str = "cyan",
    second_color: str = "white",
    title_color: str = "bold yellow",
    title_style: str = "bold",
    title_decoration: str = "====",
    sep: str = "\t",
    logger: Optional[logging.Logger] = None,
    replacement_for_empty_content: str = "n/a",
    output_title_and_contents: Optional[List] = None,
    message_id: Optional[str] = None,
    update_previous: bool = False,
    section_separator: str = "----",
    **kwargs
):
    """
    Generic colored pairs printing with customizable colors.

    Compatible with basics.py cprint_pairs API.

    Examples:
        >>> cprint_pairs('key1', 'val1', 'key2', 'val2',
        ...              first_color='green', second_color='white')
        >>> cprint_pairs(
        ...     'name', 'model.pt',
        ...     'size', '100MB',
        ...     title='Model Info',
        ...     title_color='magenta'
        ... )
        >>> cprint_pairs(
        ...     'epoch', 1,
        ...     'loss', 0.5,
        ...     title='Training',
        ...     section_separator='='*40
        ... )

    Args:
        *args: Variable arguments as key-value pairs
        title: Optional section title
        comment: Optional comment text
        first_color: Color for keys
        second_color: Color for values
        title_color: Color for section title
        title_style: Style for section title
        title_decoration: Decoration around title
        sep: Separator between pairs
        logger: Optional logger for logging
        replacement_for_empty_content: Text for empty values
        output_title_and_contents: Optional list to collect output data
        message_id: Optional unique identifier for this message for tracking
        update_previous: If True and message_id exists, update previous message in place
        section_separator: Separator text to display after pairs (default: "----")
    """
    # Check if this is an update operation
    should_update_in_place = (
        message_id and
        update_previous and
        message_id in _displayed_messages and
        _CURSOR_CONTROL_SUPPORTED
    )

    if should_update_in_place:
        # Clear previous lines before printing update
        prev_info = _displayed_messages[message_id]
        _clear_previous_lines(prev_info['line_count'])

    # Capture output to count lines
    from io import StringIO
    from rich.console import Console as RichConsole
    captured_output = StringIO()
    capture_console = RichConsole(file=captured_output, force_terminal=False, width=console.width)

    pairs = _solve_key_value_pairs(*args)

    # Print section title if provided
    if title:
        # Use Text object for better formatting control
        title_text = Text()
        title_text.append(f"\n{title_decoration}{title}{title_decoration}\n", style=title_color)
        capture_console.print(title_text)
        console.print(title_text)
        if comment:
            capture_console.print(f"  {comment}", style="dim")
            console.print(f"  {comment}", style="dim")

    # Print key-value pairs
    parts = []
    for key, value in pairs:
        formatted_value = _format_content(value, replacement_for_empty_content)
        text = Text()
        text.append(str(key), style=first_color)
        text.append(": ", style="white")
        text.append(formatted_value, style=second_color)
        parts.append(text)

    # Join with separator
    for i, part in enumerate(parts):
        if i > 0:
            capture_console.print(sep, end="")
            console.print(sep, end="")
        capture_console.print(part, end="")
        console.print(part, end="")
    capture_console.print()  # New line at end
    console.print()  # New line at end

    # Add ending separator if title was provided (to match basics.py behavior)
    if title:
        # Capture separator output - must match what cprint_section_separator outputs
        # cprint_section_separator prints "\n{separator_text}\n" plus an extra newline from console.print()
        sep_text = f"\n{section_separator}\n"
        capture_console.print(sep_text)  # Don't use end="" - let it add the newline like console.print() does
        cprint_section_separator(title_color=title_color, title_style=title_style, separator_text=section_separator)

    # Add to output list if provided
    if output_title_and_contents is not None:
        keys, values = zip(*pairs) if pairs else ([], [])
        if title:
            output_title_and_contents.append((title, *values))
        else:
            output_title_and_contents.append(values)

    # Log if logger provided
    if logger is not None:
        log_parts = [f"{k}: {_format_content(v, replacement_for_empty_content)}" for k, v in pairs]
        log_msg = sep.join(log_parts)
        if title:
            log_msg = f"[{title}] {log_msg}"
        logger.info(log_msg)

    # Track for future updates if message_id provided
    if message_id:
        output_text = captured_output.getvalue()
        line_count = _count_lines(output_text)
        _displayed_messages[message_id] = {
            'text': output_text,
            'line_count': line_count,
            'timestamp': time.time()
        }

# endregion

# region Section Formatting

def hprint_section_title(title: str, decoration: str = "===="):
    """
    Print a section title with decoration.

    Example:
        >>> hprint_section_title('Data Processing')

        ====Data Processing====
    """
    console.print(f"\n[{HPRINT_TITLE_COLOR}]{decoration}{title}{decoration}[/]\n")


def cprint_section_separator(title_color: str = "cyan", title_style: str = "bold", separator_text: str = "----"):
    """
    Print a section separator line with custom color.

    Args:
        title_color: Color for the separator line
        title_style: Style for the separator (e.g., "bold")
        separator_text: The separator text to display (default: "----")

    Example:
        >>> cprint_section_separator(title_color="green")
        >>> cprint_section_separator(separator_text="="*40)
    """
    console.print(f"\n[{title_style} {title_color}]{separator_text}[/]\n")


def hprint_section_separator():
    """Print a section separator line with highlight (cyan) color."""
    cprint_section_separator(title_color=HPRINT_TITLE_COLOR, title_style="bold")


def eprint_section_separator():
    """Print an error section separator line with error (red) color."""
    cprint_section_separator(title_color=EPRINT_TITLE_COLOR, title_style="bold")


def wprint_section_separator():
    """Print a warning section separator line with warning (magenta) color."""
    cprint_section_separator(title_color=WPRINT_TITLE_COLOR, title_style="bold")


def cprint_panel(
    content: str,
    title: Optional[str] = None,
    border_style: str = "cyan",
    padding: Tuple[int, int] = (1, 2),
):
    """
    Print content in a bordered panel with custom border style (Rich-specific feature).

    Example:
        >>> cprint_panel('Processing complete!', title='Success', border_style='green')
    """
    panel = Panel(
        content,
        title=title,
        border_style=border_style,
        padding=padding,
    )
    console.print(panel)


def hprint_panel(
    content: str,
    title: Optional[str] = None,
    padding: Tuple[int, int] = (1, 2),
):
    """
    Print content in a bordered panel with highlight (cyan) border style.

    Example:
        >>> hprint_panel('Processing complete!', title='Info')
    """
    cprint_panel(content, title=title, border_style=HPRINT_TITLE_COLOR, padding=padding)


def eprint_panel(
    content: str,
    title: Optional[str] = None,
    padding: Tuple[int, int] = (1, 2),
):
    """
    Print content in a bordered panel with error (red) border style.

    Example:
        >>> eprint_panel('Operation failed!', title='Error')
    """
    cprint_panel(content, title=title, border_style=EPRINT_TITLE_COLOR, padding=padding)


def wprint_panel(
    content: str,
    title: Optional[str] = None,
    padding: Tuple[int, int] = (1, 2),
):
    """
    Print content in a bordered panel with warning (magenta) border style.

    Example:
        >>> wprint_panel('Low memory warning!', title='Warning')
    """
    cprint_panel(content, title=title, border_style=WPRINT_TITLE_COLOR, padding=padding)

# endregion

# region Rich-Specific Features

def print_table(
    data: List[Dict[str, Any]],
    title: Optional[str] = None,
    columns: Optional[List[str]] = None,
    show_header: bool = True,
    show_lines: bool = False,
):
    """
    Print data as a formatted table (Rich-specific feature).

    Example:
        >>> data = [
        ...     {'name': 'Alice', 'age': 30, 'score': 95.5},
        ...     {'name': 'Bob', 'age': 25, 'score': 87.3},
        ... ]
        >>> print_table(data, title='Results')
    """
    if not data:
        console.print("[dim]No data to display[/dim]")
        return

    # Determine columns
    if columns is None:
        columns = list(data[0].keys())

    # Create table
    table = Table(title=title, show_header=show_header, show_lines=show_lines)

    # Add columns
    for col in columns:
        table.add_column(col, style="cyan")

    # Add rows
    for row in data:
        table.add_row(*[str(row.get(col, "")) for col in columns])

    console.print(table)


def print_syntax(
    code: str,
    language: str = "python",
    theme: str = "monokai",
    line_numbers: bool = True,
):
    """
    Print syntax-highlighted code.

    Example:
        >>> code = 'def hello():\\n    print("Hello, world!")'
        >>> print_syntax(code, language='python')
    """
    syntax = Syntax(code, language, theme=theme, line_numbers=line_numbers)
    console.print(syntax)


def print_markdown(markdown_text: str):
    """
    Render and print markdown text.

    Example:
        >>> md = "# Title\\n\\n**Bold** and *italic*"
        >>> print_markdown(md)
    """
    md = Markdown(markdown_text)
    console.print(md)


def print_json(data: Union[Dict, List, str], indent: int = 2):
    """
    Pretty-print JSON data.

    Example:
        >>> data = {'name': 'test', 'values': [1, 2, 3]}
        >>> print_json(data)
    """
    if isinstance(data, str):
        data = json.loads(data)
    console.print_json(data=data, indent=indent)


@contextmanager
def progress_bar(description: str = "Processing...", total: Optional[int] = None):
    """
    Context manager for progress bar.

    Example:
        >>> with progress_bar("Processing files", total=100) as progress:
        ...     task = progress.add_task(description, total=total)
        ...     for i in range(100):
        ...         # do work
        ...         progress.update(task, advance=1)
    """
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        yield progress

# endregion

# region Logger Integration

def get_rich_logger(
    name: str,
    level: int = logging.INFO,
    show_time: bool = True,
    show_path: bool = False,
) -> logging.Logger:
    """
    Create a logger with Rich handler.

    Example:
        >>> logger = get_rich_logger('my_app')
        >>> logger.info('This is a log message')
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Remove existing handlers
    logger.handlers.clear()

    # Add Rich handler
    handler = RichHandler(
        console=console,
        show_time=show_time,
        show_path=show_path,
        rich_tracebacks=True,
    )
    logger.addHandler(handler)

    return logger

# endregion

# region Utility Functions

def print_attrs(obj, exclude_private: bool = True):
    """
    Print object attributes in a formatted way.

    Example:
        >>> class Config:
        ...     def __init__(self):
        ...         self.name = 'test'
        ...         self.value = 42
        >>> print_attrs(Config())
    """
    attrs = []
    for attr in dir(obj):
        if exclude_private and attr.startswith('_'):
            continue
        attr_val = getattr(obj, attr)
        if not callable(attr_val):
            attrs.append((attr, attr_val))

    if attrs:
        hprint_pairs(*[item for pair in attrs for item in pair], title=f"{obj.__class__.__name__} Attributes")


def retrieve_and_print_attrs(obj, *attr_names) -> Tuple:
    """
    Retrieve and print specific attributes from an object.

    Example:
        >>> config = Config()
        >>> name, value = retrieve_and_print_attrs(config, 'name', 'value')
    """
    attr_vals = []
    for attr_name in attr_names:
        attr_val = getattr(obj, attr_name)
        hprint_message(attr_name, attr_val)
        attr_vals.append(attr_val)
    return tuple(attr_vals)


def color_print_pair_str(
    pair_str: str,
    pair_delimiter: str = ',',
    kv_delimiter: str = ':',
    key_color: str = "cyan",
    value_color: str = "white",
    end: str = '\n',
):
    """
    Parse and print a delimited pair string with colors.

    Compatible with basics.py color_print_pair_str API.

    Example:
        >>> color_print_pair_str("name:model.pt,size:100MB,accuracy:0.95")
        >>> color_print_pair_str("a=1;b=2;c=3", pair_delimiter=';', kv_delimiter='=')

    Args:
        pair_str: String containing key-value pairs
        pair_delimiter: Character separating pairs (default: comma)
        kv_delimiter: Character separating keys and values (default: colon)
        key_color: Color for keys
        value_color: Color for values
        end: String appended at end
    """
    pairs = pair_str.split(pair_delimiter)
    pair_count = len(pairs)
    for i in range(pair_count):
        kv_str = pairs[i].strip()
        if len(kv_str) > 0:
            parts = kv_str.split(kv_delimiter, maxsplit=1)
            if len(parts) == 2:
                k, v = parts
                text = Text()
                text.append(k, style=key_color)
                text.append(": ", style="white")
                text.append(v, style=value_color)
                if i != pair_count - 1:
                    text.append(", ")
                console.print(text, end="" if i != pair_count - 1 else end)


def hprint_message_pair_str(
    pair_str: str,
    pair_delimiter: str = ',',
    kv_delimiter: str = ':'
):
    """
    Parse and print a delimited pair string using hprint colors.

    Compatible with basics.py hprint_message_pair_str API.

    Example:
        >>> hprint_message_pair_str("epoch:10,loss:0.05,accuracy:0.95")

    Args:
        pair_str: String containing key-value pairs
        pair_delimiter: Character separating pairs (default: comma)
        kv_delimiter: Character separating keys and values (default: colon)
    """
    color_print_pair_str(
        pair_str,
        pair_delimiter=pair_delimiter,
        kv_delimiter=kv_delimiter,
        key_color=HPRINT_HEADER_OR_HIGHLIGHT_COLOR,
        value_color=HPRINT_MESSAGE_BODY_COLOR,
    )


def log_pairs(logging_fun: callable, *args):
    """
    Log key-value pairs to a logging function.

    Compatible with basics.py log_pairs API.

    Example:
        >>> import logging
        >>> logger = logging.getLogger(__name__)
        >>> log_pairs(logger.info, ('metric1', 100), ('metric2', 200))

    Args:
        logging_fun: Logging function (e.g., logger.info, logger.debug)
        *args: Tuples of (key, value) pairs
    """
    msg = ' '.join(str(arg_tup[0]) + ' ' + str(arg_tup[1]) for arg_tup in args)
    logging_fun(msg)


def info_print(tag: Any, content: Any):
    """
    Print info message with tag prefix.

    Compatible with basics.py info_print API.

    Example:
        >>> info_print("MyClass", "Processing started")
        >>> info_print(MyClass, "Data loaded")

    Args:
        tag: Tag object (class, string, or any object)
        content: Message content
    """
    from python_utils.common_utils.typing_helper import is_class, is_basic_type

    # Determine tag string
    if is_class(tag):
        tag_str = tag.__module__ + '.' + tag.__name__
    elif is_basic_type(tag):
        tag_str = str(tag)
    else:
        tag_str = tag.__class__.__name__

    # Check verbose setting
    if not hasattr(tag, '_verbose') or getattr(tag, '_verbose') is True:
        text = Text()
        text.append(tag_str, style="cyan")
        text.append(": ", style="white")
        text.append(str(content), style="white")
        console.print(text)


def debug_print(tag: Any, content: Any):
    """
    Print debug message with tag prefix.

    Compatible with basics.py debug_print API.

    Example:
        >>> debug_print("MyClass", "Variable x = 42")

    Args:
        tag: Tag object (class, string, or any object)
        content: Message content
    """
    from python_utils.common_utils.typing_helper import is_class, is_basic_type

    # Determine tag string
    if is_class(tag):
        tag_str = tag.__module__ + '.' + tag.__name__
    elif is_basic_type(tag):
        tag_str = str(tag)
    else:
        tag_str = tag.__class__.__name__

    # Check verbose setting
    if not hasattr(tag, '_verbose') or getattr(tag, '_verbose') is True:
        text = Text()
        text.append(tag_str, style="yellow")
        text.append(": ", style="white")
        text.append(str(content), style="white")
        console.print(text)


def checkpoint(prompt: str = "Enter 'YES' to continue"):
    """
    Interactive checkpoint - waits for user confirmation.

    Example:
        >>> checkpoint()  # Pauses execution until user enters 'YES'
    """
    while True:
        msg = console.input(f"[yellow]{prompt}[/yellow]\n")
        if msg.upper() == 'YES':
            return True
        elif msg.lower() == 'exit':
            console.print("[red]Exiting...[/red]")
            exit()
        else:
            console.print(f"[dim]'{msg}' is invalid. Enter 'YES' to continue or 'exit' to quit.[/dim]")

# endregion
