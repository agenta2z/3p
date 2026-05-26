import logging
import sys
import time
from typing import Tuple, List, Optional, Dict, Any

from python_utils.common_utils.typing_helper import solve_key_value_pairs, is_none_or_empty_str, is_str, bool_, is_basic_type, is_class
from python_utils.external.colorama import Fore, Style
from python_utils.external.colorama import (
    init as colorama_init,
)

colorama_init()

# Cursor control detection for colorama backend
# Note: Colorama has a bug on Windows where it cannot properly handle cursor control
# escape codes like '\033[K' (clear line). It tries to convert them to Win32 API calls
# but throws AttributeError: 'str' object has no attribute 'encode_tokens'.
# Therefore, we disable cursor control entirely on Windows for the colorama backend.
_CURSOR_CONTROL_SUPPORTED = False

if sys.platform == 'win32':
    # Disable cursor control on Windows due to colorama library bug
    _CURSOR_CONTROL_SUPPORTED = False
else:
    # On Unix-like systems, check if we're in a real terminal
    _CURSOR_CONTROL_SUPPORTED = sys.stdout.isatty()

# Detect if we're in PyCharm or other limited terminal
import os
if os.getenv('PYCHARM_HOSTED') or 'PYCHARM' in os.getenv('TERMINAL_EMULATOR', ''):
    _CURSOR_CONTROL_SUPPORTED = False

# Track displayed messages for in-place updates
_displayed_messages: Dict[str, Dict[str, Any]] = {}
# Format: {message_id: {'text': str, 'line_count': int, 'timestamp': float}}

HPRINT_TITLE_COLOR = Fore.CYAN
HPRINT_HEADER_OR_HIGHLIGHT_COLOR = Fore.LIGHTCYAN_EX
HPRINT_MESSAGE_BODY_COLOR = Fore.WHITE

EPRINT_TITLE_COLOR = Fore.RED
EPRINT_HEADER_OR_HIGHLIGHT_COLOR = Fore.LIGHTRED_EX  # Bright red/orange title for critical errors
EPRINT_MESSAGE_BODY_COLOR = Fore.LIGHTYELLOW_EX  # Bright yellow message for visibility

WPRINT_TITLE_COLOR = Fore.MAGENTA
WPRINT_HEADER_OR_HIGHLIGHT_COLOR = Fore.LIGHTMAGENTA_EX  # Bright pink/magenta title for warnings
WPRINT_MESSAGE_BODY_COLOR = Fore.YELLOW  # Regular yellow (appears brownish/olive, distinct from error's bright yellow)


# Helper functions for message tracking and updating
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
    Clear N previous lines using ANSI escape codes (if supported).

    Args:
        line_count: Number of lines to clear
    """
    if line_count > 0 and _CURSOR_CONTROL_SUPPORTED:
        # Move cursor up N lines and clear each
        for _ in range(line_count):
            sys.stdout.write('\033[F')  # Move cursor up one line
            sys.stdout.write('\033[K')  # Clear line
        sys.stdout.flush()


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


# region non-colored messages
DEFAULT_TITLE_DECORATION = '===='


def get_title_with_decoration(title: str, title_decor: str = DEFAULT_TITLE_DECORATION) -> str:
    return f'{title_decor}{title}{title_decor}'


def get_titled_message_str(
        title: str,
        content: str = '',
        start: str = '',
        end: str = '\n',
        replacement_for_empty_content='n/a'
):
    """
    Gets string for a titled message.
    Args:
        title: the title text of the message.
        content: the content text of the message.
        start: adds this string to the start of the output (in front of the title).
        end: adds this string to the end of the output (right after the content).
        replacement_for_empty_content: replacement string to display for `content` if
            the `content` is empty.

    Returns: a titled message string.

    """
    if content is None or content == '':
        content = replacement_for_empty_content
    return (
        f'{start}{title}{end}'
        if (not content)
        else f'{start}{title}: {content}{end}'
    )


def get_pairs_message_str(
        *args,
        title=None,
        comment=None,
        sep='\t',
        start='',
        end='\n'
):
    return (
            (f'[{title}]{sep}' if title else '') +
            (f'[{comment}]{sep}' if comment else '') +
            sep.join(  # noqa: E126
                (
                    get_titled_message_str(
                        title=arg[0],
                        content=arg[1],
                        start=start,
                        end='',
                    )
                    for arg in args
                )
            )
            + end
    )


# endregion

# region colored messages
def get_cprint_titled_message_str(
        title: str,
        content: str = '',
        title_color=HPRINT_HEADER_OR_HIGHLIGHT_COLOR,
        content_color=HPRINT_MESSAGE_BODY_COLOR,
        start: str = '',
        end: str = '\n',
        replacement_for_empty_content='n/a'
) -> str:
    """
    Gets a colored titled message string for terminal print.
    Args:
        title: the title text of the message.
        content: the content text of the message.
        title_color: the title text color.
        content_color: the content text color.
        start: adds this string to the start of the output (in front of the title).
        end: adds this string to the end of the output (right after the content).
        replacement_for_empty_content: replacement string to display for `content` if
            the `content` is empty.

    Returns: a colored titled string for terminal print according to the arguments.

    """
    if is_none_or_empty_str(content):
        content = replacement_for_empty_content

    if content is not None and not is_str(content):
        # ! do the conversion first; string formatting does not support some classes
        content = str(content)

    return (
        f'{start}{title_color}{title}{Fore.WHITE}{end}'
        if (not content)
        else f'{start}{title_color}{title}: {content_color}{content}{Fore.WHITE}{end}'
    )


def get_cprint_section_title_str(
        title: str,
        title_color=HPRINT_TITLE_COLOR,
        title_style=Style.BOLD,
        title_decoration=DEFAULT_TITLE_DECORATION,
) -> str:
    return (
        f'\n{title_style}{title_color}'
        f'{get_title_with_decoration(title, title_decoration)}'
        f'{Style.RESET_ALL}{Fore.WHITE}\n\n'
        if title else ''
    )


def get_cprint_section_separator(
        title_color=HPRINT_TITLE_COLOR,
        title_style=Style.BOLD,
        separator_text='----'
):
    return (
        f'\n{title_style}{title_color}'
        f'\n{separator_text}'
        f'{Style.RESET_ALL}{Fore.WHITE}\n'
    )


def get_cprint_pairs_message_str(
        *args,
        title=None,
        comment=None,
        first_color=HPRINT_HEADER_OR_HIGHLIGHT_COLOR,
        second_color=HPRINT_MESSAGE_BODY_COLOR,
        title_color=HPRINT_TITLE_COLOR,
        title_style=Style.BOLD,
        title_decoration=DEFAULT_TITLE_DECORATION,
        sep='\t',
        start='',
        end='\n',
        replacement_for_empty_content='n/a',
        output_title_and_contents: List = None,
        section_separator='----'
):
    key_value_pairs = list(solve_key_value_pairs(args))
    if output_title_and_contents is not None:
        ks, vs = zip(*key_value_pairs)
        if title:
            output_title_and_contents.append(tuple((title, *vs)))
        else:
            output_title_and_contents.append(vs)

    return (
            get_cprint_section_title_str(
                title=title,
                title_color=title_color,
                title_style=title_style,
                title_decoration=title_decoration
            ) +
            (
                f'{comment}\n' if comment else ''
            ) +
            sep.join(
                (
                    get_cprint_titled_message_str(
                        title=k,
                        content=v,
                        title_color=first_color,
                        content_color=second_color,
                        start=start,
                        end='',
                        replacement_for_empty_content=replacement_for_empty_content
                    )
                    for k, v in key_value_pairs
                )
            )
            + (
                get_cprint_section_separator(title_color, title_style, section_separator)
                if title else ''
            )
            + end
    )


def get_pair_strs_for_color_print_and_regular_print(
        *args,
        first_color=HPRINT_HEADER_OR_HIGHLIGHT_COLOR,
        second_color=HPRINT_MESSAGE_BODY_COLOR,
        sep: str = ' ',
        end: str = '\n'
) -> Tuple[str, str]:
    # ! DEPRECATED
    # we will move to Universal Logging that support colored terminal print out and
    # message logging at the same time
    colored_strs, uncolored_strs = [], []
    for arg_idx, arg in enumerate(args):
        colored_strs.append(
            get_cprint_titled_message_str(
                title=arg[0],
                content=arg[1],
                title_color=first_color,
                content_color=second_color,
                end='',
            )
        )
        uncolored_strs.append(
            f'{arg[0]}: {arg[1]},' if arg_idx != len(args) - 1 else f'{arg[0]}: {arg[1]}'
        )

    return sep.join(colored_strs) + end, sep.join(uncolored_strs) + end


def _get_cprint_str(
        text: str,
        color_quote: str = '`',
        color: str = HPRINT_HEADER_OR_HIGHLIGHT_COLOR,
        bk_color: str = HPRINT_MESSAGE_BODY_COLOR,
        end: str = '\n',
):
    if not isinstance(text, str):
        text = str(text)
    output = [bk_color]
    color_start: bool = True
    prev_color_quote: bool = False
    for c in text:
        if c == color_quote:
            if prev_color_quote:
                output.append('`')
                prev_color_quote = False
                color_start = True
            elif color_start:
                prev_color_quote = True
                color_start = False
            else:
                output.append(bk_color)
                color_start = True
        else:
            if prev_color_quote:
                output.append(color)
            output.append(c)
            prev_color_quote = False
    if end is not None:
        output.append(end)
    output.append(Fore.WHITE)
    return ''.join(output)


# endregion

# region cprint
def cprint(text, color_place_holder='`', color=HPRINT_HEADER_OR_HIGHLIGHT_COLOR, bk_color=HPRINT_MESSAGE_BODY_COLOR, end='\n'):
    print(
        _get_cprint_str(
            text=text, color_quote=color_place_holder, color=color, bk_color=bk_color, end=end
        )
    )


def cprint_message(
        title, content='', title_color=HPRINT_HEADER_OR_HIGHLIGHT_COLOR, content_color=HPRINT_MESSAGE_BODY_COLOR, start='', end='\n', replacement_for_empty_content='n/a'
):
    print(get_cprint_titled_message_str(title, content, title_color, content_color, start, end, replacement_for_empty_content))


def cprint_pairs(
        *args,
        title=None,
        comment=None,
        first_color=HPRINT_HEADER_OR_HIGHLIGHT_COLOR,
        second_color=HPRINT_MESSAGE_BODY_COLOR,
        title_color=HPRINT_TITLE_COLOR,
        title_style=Style.BOLD,
        title_decoration=DEFAULT_TITLE_DECORATION,
        sep=' ',
        start='',
        end='\n',
        replacement_for_empty_content='n/a',
        logger: logging.Logger = None,
        output_title_and_contents: List = None,
        message_id: Optional[str] = None,
        update_previous: bool = False,
        section_separator='----'
):
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

    # Solve key-value pairs once for reuse
    key_value_pairs = list(solve_key_value_pairs(*args))

    # Get the message string to print and capture
    message_str = get_cprint_pairs_message_str(
        *args,
        title=title,
        comment=comment,
        first_color=first_color,
        second_color=second_color,
        title_color=title_color,
        title_style=title_style,
        title_decoration=title_decoration,
        sep=sep,
        start=start,
        end=end,
        replacement_for_empty_content=replacement_for_empty_content,
        output_title_and_contents=output_title_and_contents,
        section_separator=section_separator
    )

    # Print without adding extra newline (message_str already has end='\n' in it)
    print(message_str, end='')

    if logger is not None:
        logger.info(
            msg=get_pairs_message_str(
                *key_value_pairs,  # Pass solved pairs, not raw args
                title=title,
                comment=comment,
                sep=sep,
                start=start,
                end=end
            )
        )

    # Track for future updates if message_id provided
    if message_id:
        line_count = _count_lines(message_str)
        _displayed_messages[message_id] = {
            'text': message_str,
            'line_count': line_count,
            'timestamp': time.time()
        }


# endregion

# region hprint

def get_pairs_str_for_hprint_and_regular_print(
        *args, sep: str = ' ', end: str = '\n'
) -> Tuple[str, str]:
    return get_pair_strs_for_color_print_and_regular_print(
        *args,
        first_color=HPRINT_HEADER_OR_HIGHLIGHT_COLOR,
        second_color=HPRINT_MESSAGE_BODY_COLOR,
        sep=sep,
        end=end
    )


def hprint(msg, color_quote='`', end=''):
    """
    Print the message `msg`, highlighting texts enclosed
        by a pair of `color_quote`s (by default the backtick `) with the cyan color.
    Use two backticks '``' to escape the color quote.
    :param msg: the message to print.
    :param color_quote: the character used to mark the beginning
            and the end of each piece of texts to highlight.
    :param end: string appended at the end of the message, newline by default.
    """
    cprint(
        text=msg,
        color_place_holder=color_quote,
        color=HPRINT_HEADER_OR_HIGHLIGHT_COLOR,
        bk_color=HPRINT_MESSAGE_BODY_COLOR,
        end=end
    )


def get_hprint_section_title_str(title: str) -> str:
    return get_cprint_section_title_str(
        title=title,
        title_color=HPRINT_TITLE_COLOR,
        title_style=Style.BOLD,
        title_decoration=DEFAULT_TITLE_DECORATION
    )


def get_hprint_section_separator() -> str:
    return get_cprint_section_separator(
        title_color=HPRINT_TITLE_COLOR,
        title_style=Style.BOLD
    )


def hprint_section_title(title: str):
    print(get_hprint_section_title_str(title))


def hprint_section_separator():
    print(get_hprint_section_separator())


def cprint_section_separator(title_color=HPRINT_TITLE_COLOR, title_style=Style.BOLD, separator_text='----'):
    """Print a section separator line with custom color."""
    print(get_cprint_section_separator(title_color=title_color, title_style=title_style, separator_text=separator_text))


def eprint_section_separator():
    """Print an error section separator line with error (red) color."""
    print(get_cprint_section_separator(title_color=EPRINT_TITLE_COLOR, title_style=Style.BOLD))


def wprint_section_separator():
    """Print a warning section separator line with warning (magenta) color."""
    print(get_cprint_section_separator(title_color=WPRINT_TITLE_COLOR, title_style=Style.BOLD))


def get_hprint_message_str(title, content='', start='', end=''):
    return get_cprint_titled_message_str(
        title=title,
        content=content,
        title_color=HPRINT_HEADER_OR_HIGHLIGHT_COLOR,
        content_color=HPRINT_MESSAGE_BODY_COLOR,
        start=start,
        end=end,
    )


def hprint_pairs(
        *args,
        title=None,
        comment=None,
        sep=' ',
        start='',
        end='',
        logger: logging.Logger = None,
        replacement_for_empty_content='n/a',
        output_title_and_contents: List = None,
        message_id: Optional[str] = None,
        update_previous: bool = False,
        section_separator='----'
):
    cprint_pairs(
        *args,
        title=title,
        comment=comment,
        first_color=HPRINT_HEADER_OR_HIGHLIGHT_COLOR,
        second_color=HPRINT_MESSAGE_BODY_COLOR,
        title_color=HPRINT_TITLE_COLOR,
        title_style=Style.BOLD,
        sep=sep,
        start=start,
        end=end,
        replacement_for_empty_content=replacement_for_empty_content,
        logger=logger,
        output_title_and_contents=output_title_and_contents,
        message_id=message_id,
        update_previous=update_previous,
        section_separator=section_separator
    )


def hprint_message(
        *msg_pairs,
        title: str = '',
        content: str = '',
        message_id: Optional[str] = None,
        update_previous: bool = False,
        start: str = '',
        end: str = '',
        sep: str = '\n',
        logger: logging.Logger = None,
        replacement_for_empty_content: str = 'n/a',
        output_title_and_contents: List = None
):
    """
    Highlight-print one or more messages.

    If there is only one message to print, then specify `title` and `content`,
    and `title` will be highlighted. We may also specify both `title` and `content`
    as unnamed arguments.

    Examples:

        >>> hprint_message(title='title', content='this is a message')  # doctest: +SKIP
        title: this is a message
        >>> hprint_message('title', 'this is a message')  # doctest: +SKIP

    If there are multiple messages, specify them as a sequence of tuples;
    we can omit the tuple brackets for convenience.

    In this case, `title` can be used to specify a big title for all the messages,
    and `content` will be displayed as a piece of text following the title.

    Examples:
        >>> hprint_message(  # doctest: +SKIP
        ...   ('title1', 'this is message1'),
        ...   ('title2', 'this is message2'),
        ...   ('title3', 'this is message3')
        ... )

        >>> hprint_message(  # doctest: +SKIP
        ...   'title1', 'this is message1',
        ...   'title2', 'this is message2',
        ...   'title3', 'this is message3'
        ... )

        >>> hprint_message(  # doctest: +SKIP
        ...   'title1', 'this is message1',
        ...   'title2', 'this is message2',
        ...   'title3', 'this is message3',
        ...   title='Big Title',
        ...   content='This is a comment for the messages.'
        ... )

    A non-string `content` object will be converted to string.

    Examples:
        >>> hprint_message(  # doctest: +SKIP
        ...   'metric1', 1,
        ...   'metric2', 4,
        ...   'metric3', 23.45,
        ...   title='Performance Metrics',
        ...   content='All the performance metrics should be non-zero.'
        ... )

    Args:
        *msg_pairs: specify a sequence of tuples if we have more than one messages;
            if this is not a sequence of tuples, every two adjacent objects will be treated
            as a tuple.
        title: specify the title for a single message,
            or specify the big title for multiple messages.
        content: specify the content of a single message,
            or specify a comment for multiple messages.
        message_id: Optional unique identifier for this message.
                   If provided with update_previous=True, will update
                   the previous message with this ID in place.
        update_previous: If True and message_id is provided and exists,
                        overwrites the previous message instead of
                        printing a new line.
        start: this is added to the start of each message.
        end: this is added to the end of each message.
        logger: provide a logger to log the current message.

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

    # Capture output to count lines
    from io import StringIO
    old_stdout = sys.stdout
    sys.stdout = captured_output = StringIO()

    try:
        if msg_pairs:
            hprint_pairs(
                *solve_key_value_pairs(*msg_pairs),
                title=title,
                comment=content,
                sep=sep,
                start=start,
                end=end,
                replacement_for_empty_content=replacement_for_empty_content,
                logger=logger,
                output_title_and_contents=output_title_and_contents
            )
        else:
            if output_title_and_contents is not None:
                if title:
                    output_title_and_contents.append((title, content))
                else:
                    output_title_and_contents.append(content)
            print(
                get_cprint_titled_message_str(
                    title=title,
                    content=content,
                    title_color=HPRINT_HEADER_OR_HIGHLIGHT_COLOR,
                    content_color=HPRINT_MESSAGE_BODY_COLOR,
                    start=start,
                    end=end,
                    replacement_for_empty_content=replacement_for_empty_content)
            )
            if logger is not None:
                logger.info(
                    msg=get_titled_message_str(
                        title=title,
                        content=content,
                        start=start,
                        end=end,
                        replacement_for_empty_content=replacement_for_empty_content
                    )
                )

    finally:
        # Restore stdout and get captured output
        sys.stdout = old_stdout
        output_text = captured_output.getvalue()

        # Print the captured output to actual stdout
        print(output_text, end='')

        # Track for future updates if message_id provided
        if message_id:
            _displayed_messages[message_id] = {
                'text': output_text,
                'line_count': _count_lines(output_text),
                'timestamp': time.time()
            }


# endregion

# region eprint
def eprint(text, color_quote='`', end='\n'):
    """
    Print the message `msg` with the , highlighting texts enclosed
        by a pair of `color_quote`s (by default the backtick `) with the red color.
    :param msg: the message to print.
    :param color_quote: the character used to mark the beginning
            and the end of each piece of texts to highlight.
    :param end: string appended at the end of the message, newline by default.
    """
    cprint(
        text=text, color_place_holder=color_quote, color=EPRINT_HEADER_OR_HIGHLIGHT_COLOR, bk_color=EPRINT_MESSAGE_BODY_COLOR, end=end
    )


def get_eprint_message_str(title, content='', start='', end=''):
    return get_cprint_titled_message_str(
        title=title,
        content=content,
        title_color=EPRINT_HEADER_OR_HIGHLIGHT_COLOR,
        content_color=EPRINT_MESSAGE_BODY_COLOR,
        start=start,
        end=end,
    )


def eprint_pairs(
        *args,
        title=None,
        comment=None,
        sep=' ',
        start='',
        end='',
        logger: logging.Logger = None,
        replacement_for_empty_content='n/a',
        message_id: Optional[str] = None,
        update_previous: bool = False,
        section_separator='----'
):
    cprint_pairs(
        *args,
        title=title,
        comment=comment,
        first_color=EPRINT_HEADER_OR_HIGHLIGHT_COLOR,
        second_color=EPRINT_MESSAGE_BODY_COLOR,
        title_color=EPRINT_TITLE_COLOR,
        title_style=Style.BOLD,
        sep=sep,
        start=start,
        end=end,
        replacement_for_empty_content=replacement_for_empty_content,
        logger=logger,
        message_id=message_id,
        update_previous=update_previous,
        section_separator=section_separator
    )


def eprint_message(
        *msg_pairs,
        title='',
        content='',
        start='',
        end='',
        sep='\n',
        logger: logging.Logger = None,
        replacement_for_empty_content='n/a'
):
    if msg_pairs:
        eprint_pairs(
            *solve_key_value_pairs(*msg_pairs),
            title=title,
            comment=content,
            sep=sep,
            start=start,
            end=end,
            replacement_for_empty_content=replacement_for_empty_content,
            logger=logger
        )
    else:
        print(
            get_cprint_titled_message_str(
                title=title,
                content=content,
                title_color=EPRINT_HEADER_OR_HIGHLIGHT_COLOR,
                content_color=EPRINT_MESSAGE_BODY_COLOR,
                start=start,
                end=end,
                replacement_for_empty_content=replacement_for_empty_content)
        )
        if logger is not None:
            logger.error(
                msg=get_titled_message_str(
                    title=title,
                    content=content,
                    start=start,
                    end=end,
                    replacement_for_empty_content=replacement_for_empty_content
                )
            )


# endregion

# region wprint

def wprint(text, color_quote='`', end='\n'):
    """
    Print the message `msg` with the , highlighting texts enclosed
        by a pair of `color_quote`s (by default the backtick `) with bright pink/magenta color.
    :param msg: the message to print.
    :param color_quote: the character used to mark the beginning
            and the end of each piece of texts to highlight.
    :param end: string appended at the end of the message, newline by default.
    """
    cprint(
        text=text, color_place_holder=color_quote, color=WPRINT_HEADER_OR_HIGHLIGHT_COLOR, bk_color=WPRINT_MESSAGE_BODY_COLOR, end=end
    )


def get_wprint_message_str(title, content='', start='', end=''):
    return get_cprint_titled_message_str(
        title=title,
        content=content,
        title_color=WPRINT_HEADER_OR_HIGHLIGHT_COLOR,
        content_color=WPRINT_MESSAGE_BODY_COLOR,
        start=start,
        end=end,
    )


def wprint_pairs(
        *args,
        title=None,
        comment=None,
        sep=' ',
        start='',
        end='',
        logger: logging.Logger = None,
        replacement_for_empty_content='n/a',
        message_id: Optional[str] = None,
        update_previous: bool = False,
        section_separator='----'
):
    cprint_pairs(
        *args,
        title=title,
        comment=comment,
        first_color=WPRINT_HEADER_OR_HIGHLIGHT_COLOR,
        second_color=WPRINT_MESSAGE_BODY_COLOR,
        title_color=WPRINT_TITLE_COLOR,
        title_style=Style.BOLD,
        sep=sep,
        start=start,
        end=end,
        replacement_for_empty_content=replacement_for_empty_content,
        logger=logger,
        message_id=message_id,
        update_previous=update_previous,
        section_separator=section_separator
    )


def wprint_message(
        *msg_pairs,
        title='',
        content='',
        start='',
        end='',
        sep='\n',
        logger: logging.Logger = None,
        replacement_for_empty_content='n/a'
):
    if msg_pairs:
        wprint_pairs(
            *solve_key_value_pairs(*msg_pairs),
            title=title,
            comment=content,
            sep=sep,
            start=start,
            end=end,
            replacement_for_empty_content=replacement_for_empty_content,
            logger=logger
        )
    else:
        print(
            get_cprint_titled_message_str(
                title=title,
                content=content,
                title_color=WPRINT_HEADER_OR_HIGHLIGHT_COLOR,
                content_color=WPRINT_MESSAGE_BODY_COLOR,
                start=start,
                end=end,
                replacement_for_empty_content=replacement_for_empty_content)
        )
        if logger is not None:
            logger.warning(
                msg=get_titled_message_str(
                    title=title,
                    content=content,
                    start=start,
                    end=end,
                    replacement_for_empty_content=replacement_for_empty_content
                )
            )


# endregion


class flogger(object):
    def __init__(self, path, print_terminal=True):
        self.terminal = sys.stdout
        self.log = open(path, "w")
        self.print_to_terminal = print_terminal

    def write(self, message):
        if self.print_to_terminal:
            self.terminal.write(message)
        self.log.write(message)

    def flush(self):
        self.log.flush()
        pass

    def reset(self):
        self.flush()
        self.log.close()
        sys.stdout = self.terminal


def color_print_pair_str(
        pair_str: str,
        pair_delimiter=',',
        kv_delimiter=':',
        key_color=HPRINT_HEADER_OR_HIGHLIGHT_COLOR,
        value_color=HPRINT_MESSAGE_BODY_COLOR,
        end='\n',
):
    pairs = pair_str.split(pair_delimiter)
    pair_count = len(pairs)
    for i in range(pair_count):
        kv_str = pairs[i].strip()
        if len(kv_str) > 0:
            k, v = kv_str.split(kv_delimiter, maxsplit=2)
            cprint_message(k, v, key_color, value_color, end=', ' if i != pair_count - 1 else end)


def _get_print_tag_str(tag):
    if is_class(tag):
        return tag.__module__ + '.' + tag.__name__
    elif is_basic_type(tag):
        return str(tag)
    else:
        return tag.__class__


def retrieve_and_print_attrs(obj, *attr_names):
    num_attr_names = len(attr_names)
    attr_vals = [None] * num_attr_names
    for i in range(num_attr_names):
        attr_name = attr_names[i]
        attr_val = getattr(obj, attr_name)
        hprint_message(attr_name, attr_val)
        attr_vals[i] = attr_val
    return tuple(attr_vals)


def print_attrs(obj):
    for attr in dir(obj):
        if attr[0] != '_':
            attr_val = getattr(obj, attr)
            if not callable(attr_val):
                hprint_message(attr, attr_val)


def hprint_message_pair_str(pair_str, pair_delimiter=',', kv_delimiter=':'):
    color_print_pair_str(
        pair_str,
        pair_delimiter=pair_delimiter,
        kv_delimiter=kv_delimiter,
        key_color=HPRINT_HEADER_OR_HIGHLIGHT_COLOR,
        value_color=HPRINT_MESSAGE_BODY_COLOR,
    )


def log_pairs(logging_fun, *args):
    msg = ' '.join(str(arg_tup[0]) + ' ' + str(arg_tup[1]) for arg_tup in args)
    logging_fun(msg)


def info_print(tag, content):
    if not hasattr(tag, '_verbose') or getattr(tag, '_verbose') is True:
        cprint_message(_get_print_tag_str(tag), content, title_color=HPRINT_TITLE_COLOR)


def debug_print(tag, content):
    if not hasattr(tag, '_verbose') or getattr(tag, '_verbose') is True:
        cprint_message(_get_print_tag_str(tag), content, title_color=WPRINT_TITLE_COLOR)


def checkpoint():
    while True:
        msg = input("Enter 'YES' to continue\n")
        if msg == 'exit':
            exit()

        checkpoint = bool_(msg)
        if checkpoint is True:
            break
        elif checkpoint is False:
            exit()
        else:
            print(f"'{msg}' is an invalid input. Please try again.")
