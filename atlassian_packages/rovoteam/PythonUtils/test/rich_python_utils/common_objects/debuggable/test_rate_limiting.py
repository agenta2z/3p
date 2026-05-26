"""
Tests for Debuggable rate limiting and console update features.
"""

import time
import logging
import pytest
from python_utils.common_objects.debuggable import Debuggable, Debugger


class TestMessageIdGeneration:
    """Tests for the 3-tier message_id generation logic."""

    def test_explicit_message_id_has_priority(self):
        """Explicit message_id should be used when provided."""
        debuggable = Debugger(logger=print, always_add_logging_based_logger=False)
        message_id = debuggable._generate_message_id(
            log_item="test",
            log_type="Message",
            log_level=logging.INFO,
            explicit_id="my_custom_id"
        )
        assert message_id == "my_custom_id"

    def test_custom_generator_used_when_no_explicit_id(self):
        """Custom generator should be called when no explicit_id provided."""
        def custom_gen(self, log_item, log_type, log_level):
            return f"custom_{log_type}"

        debuggable = Debugger(
            logger=print,
            always_add_logging_based_logger=False,
            default_message_id_gen=custom_gen
        )
        message_id = debuggable._generate_message_id(
            log_item="test",
            log_type="Training",
            log_level=logging.INFO,
            explicit_id=None
        )
        assert message_id == "custom_Training"

    def test_auto_generation_when_no_generator(self):
        """Auto-generated ID should include debuggable id, log_type, and log_level."""
        debuggable = Debugger(
            logger=print,
            always_add_logging_based_logger=False,
            id="test_debuggable"
        )
        message_id = debuggable._generate_message_id(
            log_item="test",
            log_type="Progress",
            log_level=logging.INFO,
            explicit_id=None
        )
        assert message_id == "test_debuggable_Progress_INFO"

    def test_explicit_id_overrides_custom_generator(self):
        """Explicit ID should override even when custom generator is set."""
        def custom_gen(self, log_item, log_type, log_level):
            return "should_not_be_used"

        debuggable = Debugger(
            logger=print,
            always_add_logging_based_logger=False,
            default_message_id_gen=custom_gen
        )
        message_id = debuggable._generate_message_id(
            log_item="test",
            log_type="Message",
            log_level=logging.INFO,
            explicit_id="explicit_wins"
        )
        assert message_id == "explicit_wins"


class TestConsoleRateLimiting:
    """Tests for console display rate limiting."""

    def test_no_rate_limit_when_zero(self):
        """All messages should be allowed when rate limit is 0."""
        debuggable = Debugger(
            logger=print,
            always_add_logging_based_logger=False,
            console_display_rate_limit=0.0
        )
        assert debuggable._should_display_to_console("test_id") is True
        assert debuggable._should_display_to_console("test_id") is True
        assert debuggable._should_display_to_console("test_id") is True

    def test_rate_limiting_blocks_rapid_messages(self):
        """Rapid messages with same ID should be blocked."""
        debuggable = Debugger(
            logger=print,
            always_add_logging_based_logger=False,
            console_display_rate_limit=0.5
        )
        # First message should pass
        assert debuggable._should_display_to_console("test_id") is True
        # Immediate second message should be blocked
        assert debuggable._should_display_to_console("test_id") is False

    def test_rate_limiting_allows_after_interval(self):
        """Message should be allowed after rate limit interval passes."""
        debuggable = Debugger(
            logger=print,
            always_add_logging_based_logger=False,
            console_display_rate_limit=0.1
        )
        assert debuggable._should_display_to_console("test_id") is True
        time.sleep(0.15)
        assert debuggable._should_display_to_console("test_id") is True

    def test_different_message_ids_have_independent_limits(self):
        """Different message IDs should have independent rate limits."""
        debuggable = Debugger(
            logger=print,
            always_add_logging_based_logger=False,
            console_display_rate_limit=0.5
        )
        assert debuggable._should_display_to_console("id_a") is True
        assert debuggable._should_display_to_console("id_b") is True
        # Now both should be blocked
        assert debuggable._should_display_to_console("id_a") is False
        assert debuggable._should_display_to_console("id_b") is False


class TestBackendRateLimiting:
    """Tests for backend logging rate limiting."""

    def test_no_rate_limit_when_zero(self):
        """All messages should be logged when rate limit is 0."""
        debuggable = Debugger(
            logger=print,
            always_add_logging_based_logger=False,
            logging_rate_limit=0.0
        )
        assert debuggable._should_log_to_backend("test_id") is True
        assert debuggable._should_log_to_backend("test_id") is True

    def test_rate_limiting_blocks_rapid_messages(self):
        """Rapid messages with same ID should be blocked."""
        debuggable = Debugger(
            logger=print,
            always_add_logging_based_logger=False,
            logging_rate_limit=0.5
        )
        assert debuggable._should_log_to_backend("test_id") is True
        assert debuggable._should_log_to_backend("test_id") is False


class TestIsConsoleLogger:
    """Tests for console logger detection."""

    def test_print_is_console_logger(self):
        """print should be detected as console logger."""
        debuggable = Debugger(logger=print, always_add_logging_based_logger=False)
        assert debuggable._is_console_logger(print) is True

    def test_pprint_is_console_logger(self):
        """pprint.pprint should be detected as console logger."""
        import pprint
        debuggable = Debugger(logger=print, always_add_logging_based_logger=False)
        assert debuggable._is_console_logger(pprint.pprint) is True

    def test_callable_is_not_console_logger_by_default(self):
        """Regular callable should not be console logger by default."""
        def my_logger(data):
            pass
        debuggable = Debugger(logger=print, always_add_logging_based_logger=False)
        assert debuggable._is_console_logger(my_logger) is False

    def test_custom_console_logger_in_attribute(self):
        """Logger in console_loggers_or_logger_types should be detected."""
        def my_console_logger(data):
            pass

        debuggable = Debugger(
            logger=print,
            always_add_logging_based_logger=False,
            console_loggers_or_logger_types=(print, my_console_logger)
        )
        assert debuggable._is_console_logger(my_console_logger) is True

    def test_type_in_console_loggers_attribute(self):
        """Type in console_loggers_or_logger_types should match instances."""
        class MyConsoleLogger:
            def __call__(self, data):
                pass

        my_instance = MyConsoleLogger()
        debuggable = Debugger(
            logger=print,
            always_add_logging_based_logger=False,
            console_loggers_or_logger_types=(print, MyConsoleLogger)
        )
        assert debuggable._is_console_logger(my_instance) is True


class TestIntegratedRateLimiting:
    """Integration tests for rate limiting in log() method."""

    def test_console_rate_limiting_in_log(self):
        """Console rate limiting should work in log() method."""
        messages = []

        def capture_print(msg):
            messages.append(msg)

        # Create a custom class to use capture_print
        class TestDebug(Debuggable):
            pass

        debuggable = TestDebug(
            logger=capture_print,
            always_add_logging_based_logger=False,
            log_time=False,
            console_display_rate_limit=0.3,
            console_loggers_or_logger_types=(capture_print,)  # Mark as console logger
        )

        for i in range(5):
            debuggable.log_info(f"message_{i}")
            time.sleep(0.1)

        # Not all messages should have been captured due to rate limiting
        assert len(messages) < 5

    def test_backend_logging_rate_limiting(self):
        """Backend rate limiting should work for non-console loggers."""
        logged_items = []

        def backend_logger(log_data):
            logged_items.append(log_data)

        class TestDebug(Debuggable):
            pass

        debuggable = TestDebug(
            logger=backend_logger,
            always_add_logging_based_logger=False,
            log_time=False,
            logging_rate_limit=0.3
        )

        for i in range(5):
            debuggable.log_info(f"message_{i}")
            time.sleep(0.1)

        # Not all messages should have been logged due to rate limiting
        assert len(logged_items) < 5


class TestConsoleUpdate:
    """Tests for console update feature."""

    def test_console_update_passes_message_id(self):
        """When enable_console_update is True, message_id should be passed."""
        received_kwargs = {}

        def logger_with_message_id(log_data, message_id=None, update_previous=None, **kwargs):
            received_kwargs['message_id'] = message_id
            received_kwargs['update_previous'] = update_previous

        class TestDebug(Debuggable):
            pass

        debuggable = TestDebug(
            logger=logger_with_message_id,
            always_add_logging_based_logger=False,
            log_time=False,
            enable_console_update=True
        )

        debuggable.log_info("test message")

        assert received_kwargs['message_id'] is not None
        assert received_kwargs['update_previous'] is True

    def test_console_update_disabled_by_default(self):
        """When enable_console_update is False, params should not be passed."""
        received_kwargs = {}

        def logger_with_message_id(log_data, message_id=None, update_previous=None, **kwargs):
            received_kwargs['message_id'] = message_id
            received_kwargs['update_previous'] = update_previous

        class TestDebug(Debuggable):
            pass

        debuggable = TestDebug(
            logger=logger_with_message_id,
            always_add_logging_based_logger=False,
            log_time=False,
            enable_console_update=False  # Disabled
        )

        debuggable.log_info("test message")

        assert received_kwargs.get('message_id') is None
        assert received_kwargs.get('update_previous') is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
