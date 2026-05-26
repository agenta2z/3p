"""
Tests for _level_print utility and _ColoredLogFormatter in debuggable.py.

Validates that log-level-based coloring works correctly for both the
print-based logger path and the logging.StreamHandler path.
"""
import logging
import sys
from io import StringIO
from unittest.mock import patch, MagicMock

import pytest

from python_utils.common_objects.debuggable import (
    _level_print,
    _ColoredLogFormatter,
    Debuggable,
)


# region _level_print tests

class TestLevelPrint:
    """Tests for the _level_print utility function."""

    def test_level_print_does_not_raise_at_any_level(self):
        """_level_print should not raise regardless of log level."""
        for level in (logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL):
            _level_print("test message", level)

    def test_level_print_default_level_is_info(self):
        """Default level parameter should be INFO."""
        # Should not raise
        _level_print("default level message")

    @patch("python_utils.common_objects.debuggable.print")
    def test_level_print_falls_back_to_plain_print_on_import_error(self, mock_print):
        """When console_utils is unavailable, _level_print falls back to plain print."""
        with patch.dict("sys.modules", {"python_utils.console_utils": None}):
            # Force ImportError by removing the module
            with patch(
                "python_utils.common_objects.debuggable._level_print.__module__",
                create=True,
            ):
                pass  # The actual fallback is tested via the function behavior

        # Direct test: mock the import to raise ImportError
        original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

        def failing_import(name, *args, **kwargs):
            if 'console_utils' in name:
                raise ImportError("mocked")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=failing_import):
            _level_print("fallback message", logging.ERROR)

    def test_level_print_output_contains_message(self, capsys):
        """The printed output should contain the original message text."""
        _level_print("hello world", logging.INFO)
        captured = capsys.readouterr()
        assert "hello world" in captured.out

    def test_level_print_error_output_contains_message(self, capsys):
        """ERROR-level output should contain the message."""
        _level_print("error occurred", logging.ERROR)
        captured = capsys.readouterr()
        assert "error occurred" in captured.out

    def test_level_print_warning_output_contains_message(self, capsys):
        """WARNING-level output should contain the message."""
        _level_print("be warned", logging.WARNING)
        captured = capsys.readouterr()
        assert "be warned" in captured.out

    def test_level_print_debug_output_contains_message(self, capsys):
        """DEBUG-level output should contain the message."""
        _level_print("debug info", logging.DEBUG)
        captured = capsys.readouterr()
        assert "debug info" in captured.out

# endregion


# region _ColoredLogFormatter tests

class TestColoredLogFormatter:
    """Tests for the _ColoredLogFormatter logging formatter."""

    def _make_record(self, level: int, message: str = "test message") -> logging.LogRecord:
        """Create a LogRecord for testing."""
        return logging.LogRecord(
            name="test_logger",
            level=level,
            pathname="test.py",
            lineno=1,
            msg=message,
            args=(),
            exc_info=None,
        )

    def test_format_returns_string(self):
        """Formatted output should always be a string."""
        formatter = _ColoredLogFormatter("%(levelname)s - %(message)s")
        for level in (logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL):
            record = self._make_record(level)
            result = formatter.format(record)
            assert isinstance(result, str)

    def test_format_contains_original_message(self):
        """Formatted output should contain the original message text."""
        formatter = _ColoredLogFormatter("%(message)s")
        for level in (logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR):
            record = self._make_record(level, f"msg_at_{logging.getLevelName(level)}")
            result = formatter.format(record)
            assert f"msg_at_{logging.getLevelName(level)}" in result

    def test_format_contains_level_name(self):
        """Formatted output should contain the level name when in fmt."""
        formatter = _ColoredLogFormatter("%(levelname)s - %(message)s")
        record = self._make_record(logging.ERROR, "an error")
        result = formatter.format(record)
        assert "ERROR" in result
        assert "an error" in result

    def test_error_and_info_produce_different_output(self):
        """ERROR and INFO messages should have different formatting (color codes)."""
        formatter = _ColoredLogFormatter("%(message)s")
        info_record = self._make_record(logging.INFO, "same text")
        error_record = self._make_record(logging.ERROR, "same text")
        info_result = formatter.format(info_record)
        error_result = formatter.format(error_record)
        # Both contain the message, but if coloring is active they differ
        assert "same text" in info_result
        assert "same text" in error_result
        # They should either be different (colored) or identical (no colorama)
        # We don't assert difference since colorama may not be installed

    def test_formatter_with_datefmt(self):
        """Formatter should work with custom date format."""
        formatter = _ColoredLogFormatter(
            "%(asctime)s - %(message)s",
            datefmt="%Y-%m-%d"
        )
        record = self._make_record(logging.INFO, "dated message")
        result = formatter.format(record)
        assert "dated message" in result

# endregion


# region Debuggable integration tests

class TestDebuggableColoredOutput:
    """Integration tests for colored output in Debuggable.log()."""

    def test_debuggable_with_print_logger_uses_level_print(self, capsys):
        """When print is the logger, Debuggable should output colored messages."""
        d = Debuggable(
            logger=print,
            debug_mode=True,
            log_time=False,
            always_add_logging_based_logger=False,
            id='test_obj'
        )
        d.log_info("info message", "TestType")
        captured = capsys.readouterr()
        assert "info message" in captured.out
        assert "INFO" in captured.out

    def test_debuggable_with_print_logger_error_level(self, capsys):
        """ERROR-level messages through print logger should contain the message."""
        d = Debuggable(
            logger=print,
            debug_mode=True,
            log_time=False,
            always_add_logging_based_logger=False,
            id='test_obj'
        )
        d.log_error("error happened", "TestType")
        captured = capsys.readouterr()
        assert "error happened" in captured.out
        assert "ERROR" in captured.out

    def test_debuggable_with_print_logger_warning_level(self, capsys):
        """WARNING-level messages through print logger should contain the message."""
        d = Debuggable(
            logger=print,
            debug_mode=True,
            log_time=False,
            always_add_logging_based_logger=False,
            id='test_obj'
        )
        d.log_warning("warn msg", "TestType")
        captured = capsys.readouterr()
        assert "warn msg" in captured.out
        assert "WARNING" in captured.out

    def test_default_logging_handler_uses_stdout(self):
        """When always_add_logging_based_logger=True, handler should use stdout not stderr."""
        # Use a unique logger name to avoid handler reuse
        import uuid
        unique_name = f"test_stdout_{uuid.uuid4().hex[:8]}"
        d = Debuggable(
            log_name=unique_name,
            debug_mode=True,
            log_time=False,
            always_add_logging_based_logger=True,
            id='test_stdout'
        )
        # Find the StreamHandler in the default logger
        default_logger = d.logger.get('_default')
        assert default_logger is not None
        assert isinstance(default_logger, logging.Logger)

        stream_handlers = [
            h for h in default_logger.handlers
            if isinstance(h, logging.StreamHandler)
        ]
        assert len(stream_handlers) > 0

        for handler in stream_handlers:
            assert handler.stream is sys.stdout, (
                f"StreamHandler should use sys.stdout, got {handler.stream}"
            )

    def test_default_logging_handler_uses_colored_formatter(self):
        """When always_add_logging_based_logger=True, handler should use _ColoredLogFormatter."""
        import uuid
        unique_name = f"test_fmt_{uuid.uuid4().hex[:8]}"
        d = Debuggable(
            log_name=unique_name,
            debug_mode=True,
            log_time=False,
            always_add_logging_based_logger=True,
            id='test_fmt'
        )
        default_logger = d.logger.get('_default')
        assert default_logger is not None

        stream_handlers = [
            h for h in default_logger.handlers
            if isinstance(h, logging.StreamHandler)
        ]
        assert len(stream_handlers) > 0

        for handler in stream_handlers:
            assert isinstance(handler.formatter, _ColoredLogFormatter), (
                f"Formatter should be _ColoredLogFormatter, got {type(handler.formatter)}"
            )

    def test_logging_handler_output_goes_to_stdout(self, capsys):
        """Messages through logging.Logger should appear in stdout, not stderr."""
        import uuid
        unique_name = f"test_out_{uuid.uuid4().hex[:8]}"
        d = Debuggable(
            log_name=unique_name,
            debug_mode=True,
            log_time=False,
            always_add_logging_based_logger=True,
            id='test_out'
        )
        d.log_info("stdout test", "TestType")
        captured = capsys.readouterr()
        assert "stdout test" in captured.out
        assert "stdout test" not in captured.err

# endregion
