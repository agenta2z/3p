"""
Comprehensive tests for basics.py (Colorama-based console utilities).

This test suite covers:
- Color constants definition
- Backtick-based highlighting functions (cprint, hprint, eprint, wprint)
- Message printing functions (single and pairs)
- Section formatting functions
- Utility functions (print_attrs, retrieve_and_print_attrs)
- Logger integration
- String getter functions
- Edge cases and error handling
"""

import pytest
import logging
from io import StringIO
from unittest.mock import Mock, patch
from python_utils.console_utils.colorama_console_utils import (
    # Color constants
    HPRINT_TITLE_COLOR, HPRINT_HEADER_OR_HIGHLIGHT_COLOR, HPRINT_MESSAGE_BODY_COLOR,
    EPRINT_TITLE_COLOR, EPRINT_HEADER_OR_HIGHLIGHT_COLOR, EPRINT_MESSAGE_BODY_COLOR,
    WPRINT_TITLE_COLOR, WPRINT_HEADER_OR_HIGHLIGHT_COLOR, WPRINT_MESSAGE_BODY_COLOR,
    # Backtick-based functions
    cprint, hprint, eprint, wprint,
    # Message functions
    cprint_message, hprint_message, eprint_message, wprint_message,
    # Pairs functions
    cprint_pairs, hprint_pairs, eprint_pairs, wprint_pairs,
    # Section formatting
    hprint_section_title, hprint_section_separator,
    get_hprint_section_title_str, get_hprint_section_separator,
    # String getters
    get_hprint_message_str, get_eprint_message_str, get_wprint_message_str,
    get_cprint_titled_message_str,
    # Utility functions
    print_attrs, retrieve_and_print_attrs,
    color_print_pair_str, hprint_message_pair_str,
    # Helper
    get_titled_message_str,
)
from python_utils.external.colorama import Fore, Style


class TestColorConstants:
    """Tests for color constant definitions."""

    def test_hprint_colors_defined(self):
        """Test that HPRINT color constants are defined."""
        assert HPRINT_TITLE_COLOR == Fore.CYAN
        assert HPRINT_HEADER_OR_HIGHLIGHT_COLOR == Fore.LIGHTCYAN_EX
        assert HPRINT_MESSAGE_BODY_COLOR == Fore.WHITE

    def test_eprint_colors_defined(self):
        """Test that EPRINT color constants are defined."""
        assert EPRINT_TITLE_COLOR == Fore.RED
        assert EPRINT_HEADER_OR_HIGHLIGHT_COLOR == Fore.LIGHTRED_EX  # Bright red/orange for critical errors
        assert EPRINT_MESSAGE_BODY_COLOR == Fore.LIGHTYELLOW_EX  # Bright yellow message for visibility

    def test_wprint_colors_defined(self):
        """Test that WPRINT color constants are defined."""
        assert WPRINT_TITLE_COLOR == Fore.MAGENTA
        assert WPRINT_HEADER_OR_HIGHLIGHT_COLOR == Fore.LIGHTMAGENTA_EX  # Bright pink/magenta
        assert WPRINT_MESSAGE_BODY_COLOR == Fore.YELLOW  # Regular yellow (brownish/olive, distinct from error)


class TestBacktickHighlighting:
    """Tests for backtick-based highlighting functions."""

    def test_hprint_basic(self, capsys):
        """Test basic hprint with backtick highlights."""
        hprint("Processing `file.txt`", end='')
        captured = capsys.readouterr()
        assert "Processing" in captured.out
        assert "file.txt" in captured.out
        assert Fore.LIGHTCYAN_EX in captured.out

    def test_hprint_multiple_highlights(self, capsys):
        """Test hprint with multiple highlighted sections."""
        hprint("Load `data.csv` with `1000` rows", end='')
        captured = capsys.readouterr()
        assert "data.csv" in captured.out
        assert "1000" in captured.out
        assert captured.out.count(Fore.LIGHTCYAN_EX) >= 2

    def test_hprint_escaped_backticks(self, capsys):
        """Test hprint with escaped backticks (double backticks)."""
        hprint("Use ``backticks`` for code", end='')
        captured = capsys.readouterr()
        assert "backticks" in captured.out
        # Escaped backticks should appear as literal backticks
        assert "`" in captured.out

    def test_eprint_basic(self, capsys):
        """Test basic eprint with bright red/orange highlights (matches eprint_message title)."""
        eprint("Error in `function()`", end='')
        captured = capsys.readouterr()
        assert "Error in" in captured.out
        assert "function()" in captured.out
        assert Fore.LIGHTRED_EX in captured.out  # Uses EPRINT_TITLE_COLOR

    def test_wprint_basic(self, capsys):
        """Test wprint with bright pink/magenta highlights (matches wprint_message title)."""
        wprint("Warning: `deprecated`", end='')
        captured = capsys.readouterr()
        assert "Warning:" in captured.out
        assert "deprecated" in captured.out
        assert Fore.LIGHTMAGENTA_EX in captured.out  # Uses WPRINT_TITLE_COLOR

    def test_cprint_custom_color(self, capsys):
        """Test cprint with custom color."""
        cprint("Custom `highlight`", color=Fore.GREEN, end='')
        captured = capsys.readouterr()
        assert "Custom" in captured.out
        assert "highlight" in captured.out
        assert Fore.GREEN in captured.out


class TestMessagePrinting:
    """Tests for message printing functions."""

    def test_hprint_message_simple(self, capsys):
        """Test simple hprint_message with title and content."""
        hprint_message(title="Status", content="Running")
        captured = capsys.readouterr()
        assert "Status" in captured.out
        assert "Running" in captured.out
        assert Fore.LIGHTCYAN_EX in captured.out

    def test_hprint_message_empty_content(self, capsys):
        """Test hprint_message with empty content shows 'n/a'."""
        hprint_message(title="Empty", content="")
        captured = capsys.readouterr()
        assert "Empty" in captured.out
        assert "n/a" in captured.out

    def test_hprint_message_custom_replacement(self, capsys):
        """Test hprint_message with custom empty content replacement."""
        hprint_message(title="Missing", content="", replacement_for_empty_content="<none>")
        captured = capsys.readouterr()
        assert "<none>" in captured.out

    def test_eprint_message_simple(self, capsys):
        """Test eprint_message with error colors."""
        eprint_message(title="Error", content="File not found")
        captured = capsys.readouterr()
        assert "Error" in captured.out
        assert "File not found" in captured.out
        assert Fore.LIGHTRED_EX in captured.out or Fore.LIGHTYELLOW_EX in captured.out  # Errors: bright red title, bright yellow message

    def test_wprint_message_simple(self, capsys):
        """Test wprint_message with warning colors."""
        wprint_message(title="Warning", content="Low memory")
        captured = capsys.readouterr()
        assert "Warning" in captured.out
        assert "Low memory" in captured.out
        assert Fore.LIGHTMAGENTA_EX in captured.out or Fore.YELLOW in captured.out  # Warnings: bright pink title, brownish message

    def test_cprint_message_custom_colors(self, capsys):
        """Test cprint_message with custom colors."""
        cprint_message("Custom", "Message", title_color=Fore.GREEN, content_color=Fore.BLUE)
        captured = capsys.readouterr()
        assert "Custom" in captured.out
        assert "Message" in captured.out
        assert Fore.GREEN in captured.out
        assert Fore.BLUE in captured.out


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
        assert "====" in captured.out

    def test_hprint_pairs_with_comment(self, capsys):
        """Test hprint_pairs with title and comment."""
        hprint_pairs('a', 1, title='Title', comment='This is a comment')
        captured = capsys.readouterr()
        assert "Title" in captured.out
        assert "This is a comment" in captured.out
        assert "a" in captured.out

    def test_hprint_pairs_tuple_format(self, capsys):
        """Test hprint_pairs with tuple format."""
        hprint_pairs(('key1', 'val1'), ('key2', 'val2'))
        captured = capsys.readouterr()
        assert "key1" in captured.out
        assert "val1" in captured.out
        assert "key2" in captured.out

    def test_eprint_pairs(self, capsys):
        """Test eprint_pairs with error colors."""
        eprint_pairs('error_code', 404, 'type', 'NotFound')
        captured = capsys.readouterr()
        assert "error_code" in captured.out
        assert "404" in captured.out
        assert "NotFound" in captured.out

    def test_wprint_pairs(self, capsys):
        """Test wprint_pairs with warning colors (fixed version)."""
        wprint_pairs('warning', 'W001', 'severity', 'medium')
        captured = capsys.readouterr()
        assert "warning" in captured.out
        assert "W001" in captured.out
        assert "medium" in captured.out
        assert Fore.YELLOW in captured.out  # Warning messages use regular yellow (brownish)

    def test_cprint_pairs_custom_colors(self, capsys):
        """Test cprint_pairs with custom colors."""
        cprint_pairs(
            'key', 'value',
            first_color=Fore.GREEN,
            second_color=Fore.BLUE
        )
        captured = capsys.readouterr()
        assert "key" in captured.out
        assert "value" in captured.out
        assert Fore.GREEN in captured.out
        assert Fore.BLUE in captured.out

    def test_pairs_output_collection(self):
        """Test output collection functionality in hprint_pairs."""
        output_list = []
        hprint_pairs('a', 1, 'b', 2, title='Test', output_title_and_contents=output_list)
        assert len(output_list) > 0
        # First entry should be the title row
        assert output_list[0][0] == 'Test'


class TestLoggerIntegration:
    """Tests for logger integration."""

    def test_hprint_message_with_logger(self):
        """Test hprint_message logs to provided logger."""
        mock_logger = Mock(spec=logging.Logger)
        hprint_message(title="Test", content="Message", logger=mock_logger)
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args[1]['msg']
        assert "Test" in call_args
        assert "Message" in call_args

    def test_eprint_message_with_logger(self):
        """Test eprint_message logs error to logger."""
        mock_logger = Mock(spec=logging.Logger)
        eprint_message(title="Error", content="Failed", logger=mock_logger)
        mock_logger.error.assert_called_once()

    def test_wprint_message_with_logger(self):
        """Test wprint_message logs warning to logger."""
        mock_logger = Mock(spec=logging.Logger)
        wprint_message(title="Warning", content="Deprecated", logger=mock_logger)
        mock_logger.warning.assert_called_once()

    def test_hprint_pairs_with_logger(self):
        """Test hprint_pairs logs to provided logger."""
        mock_logger = Mock(spec=logging.Logger)
        hprint_pairs('key', 'value', logger=mock_logger)
        mock_logger.info.assert_called_once()


class TestSectionFormatting:
    """Tests for section formatting functions."""

    def test_hprint_section_title(self, capsys):
        """Test hprint_section_title creates formatted title."""
        hprint_section_title("Test Section")
        captured = capsys.readouterr()
        assert "Test Section" in captured.out
        assert "====" in captured.out
        assert Fore.CYAN in captured.out
        assert Style.BOLD in captured.out

    def test_hprint_section_separator(self, capsys):
        """Test hprint_section_separator creates separator."""
        hprint_section_separator()
        captured = capsys.readouterr()
        assert "----" in captured.out

    def test_get_hprint_section_title_str(self):
        """Test get_hprint_section_title_str returns formatted string."""
        result = get_hprint_section_title_str("Title")
        assert "Title" in result
        assert "====" in result
        assert Fore.CYAN in result

    def test_get_hprint_section_separator(self):
        """Test get_hprint_section_separator returns separator string."""
        result = get_hprint_section_separator()
        assert "----" in result


class TestStringGetters:
    """Tests for string getter functions."""

    def test_get_titled_message_str_simple(self):
        """Test get_titled_message_str with title and content."""
        result = get_titled_message_str("Title", "Content")
        assert "Title: Content" in result

    def test_get_titled_message_str_empty_content(self):
        """Test get_titled_message_str with empty content shows 'n/a'."""
        result = get_titled_message_str("Title", "")
        assert "n/a" in result

    def test_get_hprint_message_str(self):
        """Test get_hprint_message_str includes color codes."""
        result = get_hprint_message_str("Title", "Content")
        assert "Title" in result
        assert "Content" in result
        assert Fore.LIGHTCYAN_EX in result

    def test_get_eprint_message_str(self):
        """Test get_eprint_message_str includes error colors."""
        result = get_eprint_message_str("Error", "Message")
        assert "Error" in result
        assert "Message" in result
        assert Fore.LIGHTRED_EX in result or Fore.LIGHTYELLOW_EX in result  # Errors: bright red title, bright yellow message

    def test_get_wprint_message_str(self):
        """Test get_wprint_message_str includes warning colors."""
        result = get_wprint_message_str("Warning", "Message")
        assert "Warning" in result
        assert "Message" in result
        assert Fore.LIGHTMAGENTA_EX in result or Fore.YELLOW in result  # Warnings: bright pink title, brownish message

    def test_get_cprint_titled_message_str_custom_colors(self):
        """Test get_cprint_titled_message_str with custom colors."""
        result = get_cprint_titled_message_str(
            "Title", "Content",
            title_color=Fore.GREEN,
            content_color=Fore.BLUE
        )
        assert "Title" in result
        assert "Content" in result
        assert Fore.GREEN in result
        assert Fore.BLUE in result


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
        assert "b" in captured.out
        assert "2" in captured.out

    def test_hprint_message_pair_str(self, capsys):
        """Test hprint_message_pair_str uses hprint colors."""
        hprint_message_pair_str("metric1:100,metric2:200")
        captured = capsys.readouterr()
        assert "metric1" in captured.out
        assert "100" in captured.out
        assert Fore.LIGHTCYAN_EX in captured.out


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
        """Test print_attrs excludes private attributes."""
        class TestObj:
            def __init__(self):
                self.public = "visible"
                self._private = "hidden"

        obj = TestObj()
        print_attrs(obj)
        captured = capsys.readouterr()
        assert "public" in captured.out
        assert "_private" not in captured.out

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
        assert "test" in captured.out
        assert "value" in captured.out
        assert "123" in captured.out


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_none_content(self, capsys):
        """Test functions handle None content gracefully."""
        hprint_message(title="Test", content=None)
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
        # Should not crash, may produce empty or minimal output

    def test_odd_number_of_args(self, capsys):
        """Test pairs functions handle odd number of arguments."""
        # Should treat last arg as key with empty value
        hprint_pairs('key1', 'val1', 'key2')
        captured = capsys.readouterr()
        assert "key1" in captured.out
        assert "key2" in captured.out
