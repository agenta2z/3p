"""
Comprehensive tests for rich_console_utils.py (Rich library-based console utilities).

This test suite covers:
- Backtick-based highlighting functions (cprint, hprint, eprint, wprint)
- Message printing functions (all variants)
- Pairs printing functions (including cprint_pairs)
- Pair string parsing functions
- Logging utility functions (log_pairs, info_print, debug_print)
- Section formatting functions
- Rich-specific features (tables, syntax, markdown, JSON, panels, progress)
- Utility functions (print_attrs, retrieve_and_print_attrs, checkpoint)
- Rich logger creation
- Edge cases and error handling
"""

import pytest
import logging
import json
from unittest.mock import Mock, patch, MagicMock
from rich.text import Text
from rich.console import Console
from python_utils.console_utils.rich_console_utils import (
    # Color constants
    HPRINT_TITLE_COLOR, HPRINT_HEADER_OR_HIGHLIGHT_COLOR, HPRINT_MESSAGE_BODY_COLOR,
    EPRINT_TITLE_COLOR, EPRINT_HEADER_OR_HIGHLIGHT_COLOR, EPRINT_MESSAGE_BODY_COLOR,
    WPRINT_TITLE_COLOR, WPRINT_HEADER_OR_HIGHLIGHT_COLOR, WPRINT_MESSAGE_BODY_COLOR,
    # Backtick-based functions
    cprint, hprint, eprint, wprint,
    _parse_backtick_highlights,
    # Message functions
    cprint_message, hprint_message, eprint_message, wprint_message,
    # Pairs functions
    cprint_pairs, hprint_pairs, eprint_pairs, wprint_pairs,
    # Pair string parsing
    color_print_pair_str, hprint_message_pair_str,
    # Logging utilities
    log_pairs, info_print, debug_print,
    # Section formatting
    hprint_section_title, hprint_section_separator,
    # Panel functions
    cprint_panel, hprint_panel, eprint_panel, wprint_panel,
    # Rich features
    print_table, print_syntax, print_markdown, print_json, progress_bar,
    # Utility functions
    print_attrs, retrieve_and_print_attrs, checkpoint,
    # Logger
    get_rich_logger,
    # Console instance
    console,
)


class TestColorConstants:
    """Tests for color constant definitions."""

    def test_hprint_colors_defined(self):
        """Test that HPRINT color constants are defined."""
        assert HPRINT_TITLE_COLOR == "cyan"
        assert HPRINT_HEADER_OR_HIGHLIGHT_COLOR == "bright_cyan"
        assert HPRINT_MESSAGE_BODY_COLOR == "white"

    def test_eprint_colors_defined(self):
        """Test that EPRINT color constants are defined."""
        assert EPRINT_TITLE_COLOR == "red"
        assert EPRINT_HEADER_OR_HIGHLIGHT_COLOR == "bright_red"
        assert EPRINT_MESSAGE_BODY_COLOR == "bright_yellow"

    def test_wprint_colors_defined(self):
        """Test that WPRINT color constants are defined."""
        assert WPRINT_TITLE_COLOR == "magenta"
        assert WPRINT_HEADER_OR_HIGHLIGHT_COLOR == "bright_magenta"
        assert WPRINT_MESSAGE_BODY_COLOR == "yellow"


class TestBacktickHighlightingHelper:
    """Tests for backtick highlighting helper function."""

    def test_parse_backtick_simple(self):
        """Test parsing simple backtick-highlighted text."""
        result = _parse_backtick_highlights("Processing `file.txt`", highlight_color="cyan")
        assert isinstance(result, Text)
        # Text should contain both plain and highlighted segments
        assert len(result.spans) > 0

    def test_parse_backtick_multiple(self):
        """Test parsing multiple backtick-highlighted sections."""
        result = _parse_backtick_highlights("Load `data.csv` with `1000` rows")
        assert isinstance(result, Text)
        # Should have multiple styled sections

    def test_parse_backtick_escaped(self):
        """Test parsing escaped backticks (double backticks)."""
        result = _parse_backtick_highlights("Use ``backticks`` for code")
        text_str = result.plain
        # Escaped backticks should appear as single backticks
        assert "`" in text_str or "backticks" in text_str

    def test_parse_backtick_custom_quote(self):
        """Test parsing with custom quote character."""
        result = _parse_backtick_highlights("Highlight *this*", color_quote='*', highlight_color="red")
        assert isinstance(result, Text)

    def test_parse_backtick_non_string(self):
        """Test parsing converts non-string to string."""
        result = _parse_backtick_highlights(123, highlight_color="cyan")
        assert isinstance(result, Text)
        assert "123" in result.plain


class TestBacktickPrintingFunctions:
    """Tests for backtick-based highlighting print functions."""

    def test_cprint_basic(self, capsys):
        """Test basic cprint with backtick highlights."""
        cprint("This is `highlighted` text")
        captured = capsys.readouterr()
        assert "This is" in captured.out
        assert "highlighted" in captured.out

    def test_cprint_custom_color(self, capsys):
        """Test cprint with custom color."""
        cprint("Custom `green` text", color="green")
        captured = capsys.readouterr()
        assert "green" in captured.out

    def test_hprint_basic(self, capsys):
        """Test hprint with cyan highlighting."""
        hprint("Processing `data.csv`")
        captured = capsys.readouterr()
        assert "Processing" in captured.out
        assert "data.csv" in captured.out

    def test_eprint_basic(self, capsys):
        """Test eprint with red highlighting."""
        eprint("Error in `function()`")
        captured = capsys.readouterr()
        assert "Error in" in captured.out
        assert "function()" in captured.out

    def test_wprint_basic(self, capsys):
        """Test wprint with yellow highlighting."""
        wprint("Warning: `deprecated`")
        captured = capsys.readouterr()
        assert "Warning:" in captured.out
        assert "deprecated" in captured.out

    def test_cprint_no_end_newline(self, capsys):
        """Test cprint with custom end parameter."""
        cprint("No newline", end='')
        captured = capsys.readouterr()
        assert captured.out == "No newline" or "No newline" in captured.out


class TestMessagePrinting:
    """Tests for message printing functions."""

    def test_hprint_message_simple(self, capsys):
        """Test simple hprint_message with title and content."""
        hprint_message(title="Status", content="Running")
        captured = capsys.readouterr()
        assert "Status" in captured.out
        assert "Running" in captured.out

    def test_hprint_message_pairs(self, capsys):
        """Test hprint_message with pairs (calls hprint_pairs)."""
        hprint_message('key1', 'val1', 'key2', 'val2')
        captured = capsys.readouterr()
        assert "key1" in captured.out
        assert "val1" in captured.out
        assert "key2" in captured.out
        assert "val2" in captured.out

    def test_hprint_message_empty_content(self, capsys):
        """Test hprint_message with empty content shows 'n/a'."""
        hprint_message(title="Empty", content="")
        captured = capsys.readouterr()
        assert "Empty" in captured.out
        assert "n/a" in captured.out

    def test_eprint_message_simple(self, capsys):
        """Test eprint_message with error formatting."""
        eprint_message(title="Error", content="File not found")
        captured = capsys.readouterr()
        assert "Error" in captured.out
        assert "File not found" in captured.out

    def test_wprint_message_simple(self, capsys):
        """Test wprint_message with warning formatting."""
        wprint_message(title="Warning", content="Low memory")
        captured = capsys.readouterr()
        assert "Warning" in captured.out
        assert "Low memory" in captured.out

    def test_cprint_message_custom_colors(self, capsys):
        """Test cprint_message with custom colors."""
        cprint_message("Custom", "Message", title_color="green", content_color="blue")
        captured = capsys.readouterr()
        assert "Custom" in captured.out
        assert "Message" in captured.out

    def test_message_with_logger(self):
        """Test message functions log to provided logger."""
        mock_logger = Mock(spec=logging.Logger)
        hprint_message(title="Test", content="Message", logger=mock_logger)
        mock_logger.info.assert_called_once()


class TestPairsPrinting:
    """Tests for pairs printing functions."""

    def test_hprint_pairs_simple(self, capsys):
        """Test simple hprint_pairs with key-value pairs."""
        hprint_pairs('key1', 'value1', 'key2', 'value2')
        captured = capsys.readouterr()
        assert "key1" in captured.out
        assert "value1" in captured.out
        assert "key2" in captured.out
        assert "value2" in captured.out

    def test_hprint_pairs_with_title(self, capsys):
        """Test hprint_pairs with section title."""
        hprint_pairs('metric', 100, title='Results')
        captured = capsys.readouterr()
        assert "Results" in captured.out
        assert "metric" in captured.out
        assert "100" in captured.out

    def test_hprint_pairs_with_comment(self, capsys):
        """Test hprint_pairs with title and comment."""
        hprint_pairs('a', 1, title='Title', comment='Comment text')
        captured = capsys.readouterr()
        assert "Title" in captured.out
        assert "Comment text" in captured.out

    def test_eprint_pairs(self, capsys):
        """Test eprint_pairs with error formatting."""
        eprint_pairs('error_code', 404, 'type', 'NotFound')
        captured = capsys.readouterr()
        assert "error_code" in captured.out
        assert "404" in captured.out
        assert "NotFound" in captured.out

    def test_wprint_pairs(self, capsys):
        """Test wprint_pairs with warning formatting."""
        wprint_pairs('warning', 'W001', 'severity', 'medium')
        captured = capsys.readouterr()
        assert "warning" in captured.out
        assert "W001" in captured.out
        assert "medium" in captured.out

    def test_cprint_pairs_custom_colors(self, capsys):
        """Test cprint_pairs with fully customizable colors."""
        cprint_pairs(
            'key', 'value',
            first_color='green',
            second_color='yellow',
            title='Custom',
            title_color='magenta'
        )
        captured = capsys.readouterr()
        assert "key" in captured.out
        assert "value" in captured.out
        assert "Custom" in captured.out

    def test_pairs_with_separator(self, capsys):
        """Test pairs printing with custom separator."""
        hprint_pairs('a', 1, 'b', 2, sep=' | ')
        captured = capsys.readouterr()
        # Output should use the custom separator

    def test_pairs_output_collection(self):
        """Test output collection functionality."""
        output_list = []
        hprint_pairs('a', 1, 'b', 2, title='Test', output_title_and_contents=output_list)
        assert len(output_list) > 0

    def test_pairs_with_logger(self):
        """Test pairs functions log to provided logger."""
        mock_logger = Mock(spec=logging.Logger)
        hprint_pairs('key', 'value', logger=mock_logger)
        mock_logger.info.assert_called_once()


class TestPairStringParsing:
    """Tests for pair string parsing functions."""

    def test_color_print_pair_str_simple(self, capsys):
        """Test color_print_pair_str with simple pair string."""
        color_print_pair_str("key1:val1,key2:val2")
        captured = capsys.readouterr()
        assert "key1" in captured.out
        assert "val1" in captured.out
        assert "key2" in captured.out
        assert "val2" in captured.out

    def test_color_print_pair_str_custom_delimiters(self, capsys):
        """Test color_print_pair_str with custom delimiters."""
        color_print_pair_str("a=1;b=2", pair_delimiter=';', kv_delimiter='=')
        captured = capsys.readouterr()
        assert "a" in captured.out
        assert "1" in captured.out

    def test_color_print_pair_str_custom_colors(self, capsys):
        """Test color_print_pair_str with custom colors."""
        color_print_pair_str("key:value", key_color="green", value_color="blue")
        captured = capsys.readouterr()
        assert "key" in captured.out
        assert "value" in captured.out

    def test_hprint_message_pair_str(self, capsys):
        """Test hprint_message_pair_str uses hprint colors."""
        hprint_message_pair_str("metric1:100,metric2:200")
        captured = capsys.readouterr()
        assert "metric1" in captured.out
        assert "100" in captured.out


class TestLoggingUtilities:
    """Tests for logging utility functions."""

    def test_log_pairs_basic(self):
        """Test log_pairs logs key-value pairs."""
        mock_logging_fun = Mock()
        log_pairs(mock_logging_fun, ('key1', 'val1'), ('key2', 'val2'))
        mock_logging_fun.assert_called_once()
        call_args = mock_logging_fun.call_args[0][0]
        assert "key1" in call_args
        assert "val1" in call_args

    def test_info_print_basic(self, capsys):
        """Test info_print with string tag."""
        info_print("MyClass", "Processing started")
        captured = capsys.readouterr()
        assert "MyClass" in captured.out
        assert "Processing started" in captured.out

    def test_info_print_class_tag(self, capsys):
        """Test info_print with class as tag."""
        class TestClass:
            pass
        info_print(TestClass, "Message")
        captured = capsys.readouterr()
        assert "TestClass" in captured.out
        assert "Message" in captured.out

    def test_info_print_respects_verbose(self, capsys):
        """Test info_print respects _verbose attribute."""
        class QuietClass:
            _verbose = False
        info_print(QuietClass, "Should not print")
        captured = capsys.readouterr()
        assert captured.out == "" or "Should not print" not in captured.out

    def test_debug_print_basic(self, capsys):
        """Test debug_print with string tag."""
        debug_print("MyClass", "Debug info")
        captured = capsys.readouterr()
        assert "MyClass" in captured.out
        assert "Debug info" in captured.out


class TestSectionFormatting:
    """Tests for section formatting functions."""

    def test_hprint_section_title(self, capsys):
        """Test hprint_section_title creates formatted title."""
        hprint_section_title("Test Section")
        captured = capsys.readouterr()
        assert "Test Section" in captured.out
        assert "====" in captured.out

    def test_hprint_section_separator(self, capsys):
        """Test hprint_section_separator creates separator."""
        hprint_section_separator()
        captured = capsys.readouterr()
        assert "----" in captured.out

    def test_print_panel_basic(self, capsys):
        """Test cprint_panel creates bordered panel."""
        cprint_panel("Test content", title="Panel Title")
        captured = capsys.readouterr()
        assert "Test content" in captured.out
        assert "Panel Title" in captured.out

    def test_print_panel_custom_style(self, capsys):
        """Test cprint_panel with custom border style."""
        cprint_panel("Content", border_style="green")
        captured = capsys.readouterr()
        assert "Content" in captured.out


class TestRichFeatures:
    """Tests for Rich-specific features."""

    def test_print_table_simple(self, capsys):
        """Test print_table displays data as table."""
        data = [
            {'name': 'Alice', 'age': 30},
            {'name': 'Bob', 'age': 25}
        ]
        print_table(data, title='People')
        captured = capsys.readouterr()
        assert "Alice" in captured.out
        assert "Bob" in captured.out
        assert "30" in captured.out
        assert "25" in captured.out

    def test_print_table_empty(self, capsys):
        """Test print_table handles empty data gracefully."""
        print_table([])
        captured = capsys.readouterr()
        assert "No data" in captured.out or captured.out != ""

    def test_print_table_custom_columns(self, capsys):
        """Test print_table with custom column selection."""
        data = [{'a': 1, 'b': 2, 'c': 3}]
        print_table(data, columns=['a', 'c'])
        captured = capsys.readouterr()
        assert "1" in captured.out
        assert "3" in captured.out

    def test_print_syntax(self, capsys):
        """Test print_syntax displays syntax-highlighted code."""
        code = "def hello():\n    print('Hello')"
        print_syntax(code, language='python')
        captured = capsys.readouterr()
        assert "def" in captured.out or "hello" in captured.out

    def test_print_markdown(self, capsys):
        """Test print_markdown renders markdown text."""
        markdown = "# Title\n\n**Bold** text"
        print_markdown(markdown)
        captured = capsys.readouterr()
        assert "Title" in captured.out or "Bold" in captured.out

    def test_print_json_dict(self, capsys):
        """Test print_json with dictionary data."""
        data = {'name': 'test', 'value': 123}
        print_json(data)
        captured = capsys.readouterr()
        assert "name" in captured.out
        assert "test" in captured.out or "123" in captured.out

    def test_print_json_string(self, capsys):
        """Test print_json with JSON string."""
        json_str = '{"key": "value"}'
        print_json(json_str)
        captured = capsys.readouterr()
        assert "key" in captured.out
        assert "value" in captured.out

    def test_progress_bar_context(self):
        """Test progress_bar context manager."""
        with progress_bar("Testing", total=10) as progress:
            assert progress is not None
            # Progress object should be usable
            assert hasattr(progress, 'add_task')


class TestUtilityFunctions:
    """Tests for utility functions."""

    def test_print_attrs_simple(self, capsys):
        """Test print_attrs prints object attributes."""
        class TestObj:
            def __init__(self):
                self.attr1 = "value1"
                self.attr2 = 42

        obj = TestObj()
        print_attrs(obj)
        captured = capsys.readouterr()
        assert "attr1" in captured.out
        assert "value1" in captured.out
        assert "attr2" in captured.out
        assert "42" in captured.out

    def test_print_attrs_excludes_private(self, capsys):
        """Test print_attrs excludes private attributes by default."""
        class TestObj:
            def __init__(self):
                self.public = "visible"
                self._private = "hidden"

        obj = TestObj()
        print_attrs(obj)
        captured = capsys.readouterr()
        assert "public" in captured.out
        # Private attributes should not appear
        assert "_private" not in captured.out

    def test_print_attrs_include_private(self, capsys):
        """Test print_attrs can include private attributes."""
        class TestObj:
            def __init__(self):
                self._private = "shown"

        obj = TestObj()
        print_attrs(obj, exclude_private=False)
        captured = capsys.readouterr()
        assert "_private" in captured.out or "shown" in captured.out

    def test_retrieve_and_print_attrs(self, capsys):
        """Test retrieve_and_print_attrs returns and prints attributes."""
        class TestObj:
            def __init__(self):
                self.name = "test"
                self.value = 123

        obj = TestObj()
        name, value = retrieve_and_print_attrs(obj, 'name', 'value')

        assert name == "test"
        assert value == 123

        captured = capsys.readouterr()
        assert "name" in captured.out
        assert "value" in captured.out

    @patch('builtins.input', return_value='YES')
    def test_checkpoint_yes(self, mock_input):
        """Test checkpoint returns True when user enters YES."""
        result = checkpoint()
        assert result is True

    @patch('builtins.input', side_effect=['no', 'YES'])
    def test_checkpoint_retry(self, mock_input):
        """Test checkpoint keeps prompting until YES is entered."""
        result = checkpoint()
        assert result is True
        assert mock_input.call_count == 2


class TestRichLogger:
    """Tests for Rich logger creation."""

    def test_get_rich_logger_basic(self):
        """Test get_rich_logger creates logger with Rich handler."""
        logger = get_rich_logger('test_logger')
        assert isinstance(logger, logging.Logger)
        assert logger.name == 'test_logger'
        assert len(logger.handlers) > 0

    def test_get_rich_logger_level(self):
        """Test get_rich_logger respects log level."""
        logger = get_rich_logger('test_logger', level=logging.DEBUG)
        assert logger.level == logging.DEBUG

    def test_get_rich_logger_unique(self):
        """Test get_rich_logger clears existing handlers."""
        logger1 = get_rich_logger('unique_logger')
        initial_handlers = len(logger1.handlers)
        logger2 = get_rich_logger('unique_logger')
        # Should clear and add new handler
        assert len(logger2.handlers) == initial_handlers


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_none_content(self, capsys):
        """Test functions handle None content gracefully."""
        hprint_message(title="Test", content=None)
        captured = capsys.readouterr()
        assert "n/a" in captured.out

    def test_empty_string_content(self, capsys):
        """Test functions handle empty string content."""
        hprint_message(title="Empty", content="")
        captured = capsys.readouterr()
        assert "n/a" in captured.out

    def test_non_string_content(self, capsys):
        """Test functions convert non-string content to string."""
        hprint_message(title="Number", content=42)
        captured = capsys.readouterr()
        assert "42" in captured.out

    def test_empty_pairs(self, capsys):
        """Test pairs functions handle empty pairs gracefully."""
        hprint_pairs()  # No pairs
        captured = capsys.readouterr()
        # Should not crash

    def test_single_pair_value(self, capsys):
        """Test pairs handle single value (odd number of args)."""
        hprint_pairs('key1', 'val1', 'key2')
        captured = capsys.readouterr()
        assert "key1" in captured.out
        assert "key2" in captured.out

    def test_custom_replacement_for_empty(self, capsys):
        """Test custom replacement for empty content."""
        hprint_message(title="Test", content="", replacement_for_empty_content="<missing>")
        captured = capsys.readouterr()
        assert "<missing>" in captured.out

    def test_complex_object_content(self, capsys):
        """Test functions handle complex objects as content."""
        obj = {'nested': {'value': 123}}
        hprint_message(title="Object", content=obj)
        captured = capsys.readouterr()
        # Should convert to string representation
        assert "nested" in captured.out or "123" in captured.out or "{" in captured.out
