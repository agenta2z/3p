"""Property-based tests for rate limiting suppression counter accuracy.

**Feature: session-logging-improvements, Property 5: Suppression Counter Accuracy**
**Validates: Requirements 8.1, 8.2, 8.3, 8.4**

For any sequence of log calls where K out of N calls are suppressed by rate limiting,
the next non-suppressed call SHALL report suppressed_count = K. After reporting, the
counter SHALL reset to zero. Console and backend suppression counters SHALL be tracked
independently.
"""
import time
from unittest.mock import MagicMock

import pytest
from hypothesis import given, strategies as st, settings, assume

from python_utils.common_objects.debuggable import Debuggable


class ConcreteDebuggable(Debuggable):
    """Concrete subclass for testing since Debuggable is abstract via Identifiable."""
    pass


# Strategies
suppression_count_st = st.integers(min_value=1, max_value=20)
rate_limit_st = st.floats(min_value=0.5, max_value=5.0, allow_nan=False, allow_infinity=False)


def _make_backend_debuggable(rate_limit: float):
    """Create a Debuggable with a callable backend logger and a backend rate limit."""
    captured = []

    def backend_logger(log_data, **kwargs):
        captured.append(dict(log_data))

    obj = ConcreteDebuggable(
        logger=backend_logger,
        always_add_logging_based_logger=False,
        logging_rate_limit=rate_limit,
        log_time=False,
    )
    return obj, captured


def _make_console_debuggable(rate_limit: float):
    """Create a Debuggable with a callable console logger and a console rate limit.
    
    The callable is registered as a console logger via console_loggers_or_logger_types,
    so it uses _console_suppression_counts. The callable logger path adds
    suppressed_count to the log_data dict.
    """
    captured = []

    def console_callable(log_data, **kwargs):
        captured.append(dict(log_data))

    obj = ConcreteDebuggable(
        logger=console_callable,
        always_add_logging_based_logger=False,
        console_display_rate_limit=rate_limit,
        console_loggers_or_logger_types=(console_callable,),
        log_time=False,
    )
    return obj, captured


# **Feature: session-logging-improvements, Property 5: Suppression Counter Accuracy**
# **Validates: Requirements 8.1, 8.2**
@settings(max_examples=50, deadline=None)
@given(num_suppressed=suppression_count_st)
def test_backend_suppression_count_accuracy(num_suppressed: int):
    """Property: For any sequence of K suppressed backend log calls, the next
    non-suppressed call SHALL include suppressed_count = K, then reset to zero.

    We use a large rate limit and manipulate _last_logging_time to control
    exactly which calls are suppressed vs allowed.
    """
    rate_limit = 1000.0  # Very large so all rapid calls are suppressed
    obj, captured = _make_backend_debuggable(rate_limit)

    msg_id = "test_msg"

    # First call goes through (sets the baseline time)
    obj.log("first", log_type="Test", message_id=msg_id)
    assert len(captured) == 1
    assert 'suppressed_count' not in captured[0]

    # Make num_suppressed calls that will be suppressed (rate limit blocks them)
    for _ in range(num_suppressed):
        obj.log("suppressed", log_type="Test", message_id=msg_id)

    # Only the first call should have gone through
    assert len(captured) == 1

    # Now allow the next call by resetting the last logging time to the past
    obj._last_logging_time[msg_id] = 0

    # This call should go through and report the suppression count
    obj.log("after_suppression", log_type="Test", message_id=msg_id)
    assert len(captured) == 2
    assert captured[1]['suppressed_count'] == num_suppressed

    # Counter should be reset: next allowed call should have no suppressed_count
    obj._last_logging_time[msg_id] = 0
    obj.log("clean", log_type="Test", message_id=msg_id)
    assert len(captured) == 3
    assert 'suppressed_count' not in captured[2]


# **Feature: session-logging-improvements, Property 5: Suppression Counter Accuracy**
# **Validates: Requirements 8.3, 8.4**
@settings(max_examples=50, deadline=None)
@given(num_suppressed=suppression_count_st)
def test_console_suppression_count_accuracy(num_suppressed: int):
    """Property: For any sequence of K suppressed console log calls, the next
    non-suppressed call SHALL include suppressed_count = K, then reset.
    
    Uses a callable console logger which receives suppressed_count in the log_data dict.
    """
    rate_limit = 1000.0
    obj, captured = _make_console_debuggable(rate_limit)

    msg_id = "test_msg"

    # First call goes through
    obj.log("first", log_type="Test", message_id=msg_id)
    assert len(captured) == 1
    assert 'suppressed_count' not in captured[0]

    # Make num_suppressed calls that will be suppressed
    for _ in range(num_suppressed):
        obj.log("suppressed", log_type="Test", message_id=msg_id)

    assert len(captured) == 1

    # Allow the next call
    obj._last_console_display_time[msg_id] = 0

    obj.log("after_suppression", log_type="Test", message_id=msg_id)
    assert len(captured) == 2
    assert captured[1]['suppressed_count'] == num_suppressed

    # Counter should be reset
    obj._last_console_display_time[msg_id] = 0
    obj.log("clean", log_type="Test", message_id=msg_id)
    assert len(captured) == 3
    assert 'suppressed_count' not in captured[2]


# **Feature: session-logging-improvements, Property 5: Suppression Counter Accuracy**
# **Validates: Requirements 8.1, 8.2, 8.3, 8.4**
@settings(max_examples=50, deadline=None)
@given(
    backend_suppressed=suppression_count_st,
    console_suppressed=suppression_count_st,
)
def test_console_and_backend_counters_are_independent(
    backend_suppressed: int, console_suppressed: int
):
    """Property: Console and backend suppression counters SHALL be tracked
    independently. Different suppression counts on each path should be
    reported correctly without interference.
    """
    backend_captured = []
    console_captured = []

    def backend_logger(log_data, **kwargs):
        backend_captured.append(dict(log_data))

    def console_logger(log_data, **kwargs):
        console_captured.append(dict(log_data))

    obj = ConcreteDebuggable(
        logger={'backend': backend_logger, 'console': console_logger},
        always_add_logging_based_logger=False,
        logging_rate_limit=1000.0,
        console_display_rate_limit=1000.0,
        console_loggers_or_logger_types=(console_logger,),
        log_time=False,
    )

    msg_id = "test_msg"

    # First call goes through on both paths
    obj.log("first", log_type="Test", message_id=msg_id)
    assert len(backend_captured) == 1
    assert len(console_captured) == 1

    # Suppress different counts on each path by manipulating times independently
    # First, suppress backend_suppressed calls on backend only
    # (allow console but block backend)
    for _ in range(backend_suppressed):
        # Both are rate-limited, so both get suppressed
        obj.log("suppressed", log_type="Test", message_id=msg_id)

    # At this point, both counters have backend_suppressed suppressions
    # Now suppress additional (console_suppressed - backend_suppressed) on console only
    # by allowing backend through but keeping console blocked
    # Actually, since both rate limits are the same (1000s), both paths suppress equally.
    # To test independence, let's reset them separately.

    # Reset backend time to allow backend through, keep console blocked
    obj._last_logging_time[msg_id] = 0

    # But console is still blocked, so the next log will:
    # - go through on backend (with backend_suppressed count)
    # - be suppressed on console (incrementing console counter)
    obj.log("backend_through", log_type="Test", message_id=msg_id)

    assert len(backend_captured) == 2
    assert backend_captured[1]['suppressed_count'] == backend_suppressed
    # Console should still be at 1 (blocked)
    assert len(console_captured) == 1

    # Now reset console time to allow console through
    obj._last_console_display_time[msg_id] = 0
    # Also reset backend time so backend goes through too
    obj._last_logging_time[msg_id] = 0

    obj.log("both_through", log_type="Test", message_id=msg_id)

    assert len(console_captured) == 2
    # Console was suppressed for: backend_suppressed (from the shared loop) + 1 (from the backend_through call)
    expected_console_suppressed = backend_suppressed + 1
    assert console_captured[1]['suppressed_count'] == expected_console_suppressed

    # Backend should have no suppression count (was just reset)
    assert len(backend_captured) == 3
    assert 'suppressed_count' not in backend_captured[2]
