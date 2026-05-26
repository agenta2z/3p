"""Property-based and timed integration tests for sync execute_with_retry timeout behavior.

Feature: retry-native-timeout

Tests correctness properties from the design document:

- Property 2: Total Timeout Monotonic Bound (sync) — timed integration tests
- Property 4: Sync Per-Attempt Timeout Rejection
- Property 5: Error Normalization Invariant (sync total timeout)

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 5.1**
"""
import sys
import time
from pathlib import Path

# Setup import paths
_current_file = Path(__file__).resolve()
_test_dir = _current_file.parent
while _test_dir.name != "test" and _test_dir.parent != _test_dir:
    _test_dir = _test_dir.parent
_project_root = _test_dir.parent
_src_dir = _project_root / "src"
if _src_dir.exists() and str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

import pytest
from hypothesis import given, settings, strategies as st

from python_utils.common_utils.function_helper import execute_with_retry


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Positive floats for attempt_timeout — any positive value should trigger rejection
positive_float_strategy = st.floats(
    min_value=1e-6, max_value=1e6,
    allow_nan=False, allow_infinity=False,
)

# Very small total_timeout values that will expire before the function completes
small_timeout_strategy = st.floats(
    min_value=0.001, max_value=0.05,
    allow_nan=False, allow_infinity=False,
)


# ---------------------------------------------------------------------------
# Property 4: Sync Per-Attempt Timeout Rejection
# ---------------------------------------------------------------------------

class TestSyncPerAttemptTimeoutRejection:
    """Property 4: Sync Per-Attempt Timeout Rejection.

    For any non-None value of attempt_timeout passed to the sync
    execute_with_retry, the function SHALL raise NotImplementedError
    before executing any attempt. A side-effect-recording function
    passed as func SHALL never be invoked.

    # Feature: retry-native-timeout, Property 4: Sync Per-Attempt Timeout Rejection

    **Validates: Requirements 4.1, 4.2**
    """

    @settings(max_examples=100)
    @given(attempt_timeout=positive_float_strategy)
    def test_attempt_timeout_raises_not_implemented(self, attempt_timeout: float):
        """For any positive float attempt_timeout, execute_with_retry SHALL
        raise NotImplementedError immediately, before any attempt is made.

        # Feature: retry-native-timeout, Property 4: Sync Per-Attempt Timeout Rejection

        **Validates: Requirements 4.1, 4.2**
        """
        call_log = []

        def recording_func():
            call_log.append("called")
            return "should_not_reach"

        with pytest.raises(NotImplementedError) as exc_info:
            execute_with_retry(
                func=recording_func,
                max_retry=3,
                attempt_timeout=attempt_timeout,
            )

        # The function must never have been called
        assert len(call_log) == 0, (
            f"func was called {len(call_log)} time(s) despite attempt_timeout={attempt_timeout}; "
            "NotImplementedError should be raised before any attempt"
        )

        # The error message should mention sync and async alternatives
        assert "sync" in str(exc_info.value).lower() or "async" in str(exc_info.value).lower(), (
            f"NotImplementedError message should reference sync/async: {exc_info.value}"
        )


# ---------------------------------------------------------------------------
# Property 5: Error Normalization Invariant (sync total timeout)
# ---------------------------------------------------------------------------

class TestSyncErrorNormalizationInvariant:
    """Property 5: Error Normalization Invariant (sync total timeout).

    For any timeout scenario where total_timeout expires in the sync
    execute_with_retry, the exception raised SHALL be an instance of
    the built-in TimeoutError.

    # Feature: retry-native-timeout, Property 5: Error Normalization Invariant (sync total)

    **Validates: Requirements 3.1, 3.2, 5.1**
    """

    @settings(max_examples=100, deadline=30000)
    @given(
        total_timeout=small_timeout_strategy,
    )
    def test_total_timeout_raises_builtin_timeout_error(
        self, total_timeout: float
    ):
        """When total_timeout expires, the raised exception SHALL be the
        built-in TimeoutError (not asyncio.TimeoutError or any other type).

        We use a function that always raises (so the retry loop keeps retrying
        until the deadline expires), with many retries and zero wait between them.

        # Feature: retry-native-timeout, Property 5: Error Normalization Invariant (sync total)

        **Validates: Requirements 3.1, 3.2, 5.1**
        """
        call_count = [0]

        def always_fail():
            call_count[0] += 1
            # Small sleep to ensure time passes toward the deadline
            time.sleep(0.005)
            raise RuntimeError("intentional failure")

        with pytest.raises(TimeoutError) as exc_info:
            execute_with_retry(
                func=always_fail,
                max_retry=1000,
                min_retry_wait=0,
                max_retry_wait=0,
                total_timeout=total_timeout,
            )

        # Verify it is exactly the built-in TimeoutError
        raised = exc_info.value
        assert isinstance(raised, TimeoutError), (
            f"Expected built-in TimeoutError, got {type(raised).__name__}"
        )

        # Verify it is NOT asyncio.TimeoutError (which is a subclass of TimeoutError
        # in Python 3.11+, but we want the plain built-in one)
        import asyncio
        assert type(raised) is TimeoutError, (
            f"Expected exactly TimeoutError, got {type(raised).__name__}; "
            "asyncio.TimeoutError should not escape the retry helper boundary"
        )


# ---------------------------------------------------------------------------
# Property 2: Total Timeout Monotonic Bound (sync) — Timed Integration Tests
# ---------------------------------------------------------------------------

class TestSyncTotalTimeoutMonotonicBound:
    """Property 2: Total Timeout Monotonic Bound (sync).

    For any positive total_timeout value and for any function and retry
    configuration, the sync Retry_Helper SHALL complete (return or raise)
    within total_timeout + max_single_attempt_duration wall-clock seconds
    (because in-progress sync calls cannot be interrupted).

    These are timed integration tests (not PBT) because wall-clock timing
    is not suitable for property-based testing.

    # Feature: retry-native-timeout, Property 2: Total Timeout Monotonic Bound (sync)

    **Validates: Requirements 3.1, 3.2, 3.3, 3.4**
    """

    TIMING_TOLERANCE = 0.3  # seconds — accounts for CI/scheduling jitter

    def test_sync_non_interruption(self):
        """Sync cannot interrupt in-progress calls. A func sleeping 2.0s with
        total_timeout=0.5 should still complete its first attempt. Elapsed
        should be in [2.0, 2.0 + tolerance] — the timeout fires between
        attempts, not mid-call.

        # Feature: retry-native-timeout, Property 2: Total Timeout Monotonic Bound (sync)

        **Validates: Requirements 3.1, 3.4**
        """
        call_count = [0]

        def slow_func():
            call_count[0] += 1
            time.sleep(2.0)
            raise RuntimeError("always fails")

        start = time.monotonic()
        with pytest.raises(TimeoutError):
            execute_with_retry(
                func=slow_func,
                max_retry=100,
                min_retry_wait=0,
                max_retry_wait=0,
                total_timeout=0.5,
            )
        elapsed = time.monotonic() - start

        # The first attempt runs to completion (2.0s) because sync can't interrupt.
        # After it finishes, the deadline (0.5s) has passed, so TimeoutError is raised.
        assert call_count[0] == 1, (
            f"Expected exactly 1 attempt (non-interrupted), got {call_count[0]}"
        )
        assert elapsed >= 2.0, (
            f"Elapsed {elapsed:.3f}s < 2.0s — sync call was interrupted mid-execution"
        )
        assert elapsed < 2.0 + self.TIMING_TOLERANCE, (
            f"Elapsed {elapsed:.3f}s exceeded upper bound of {2.0 + self.TIMING_TOLERANCE:.1f}s"
        )

    def test_timeout_between_attempts(self):
        """With total_timeout=0.3 and a func that fails quickly (raises
        immediately), max_retry=100, min_retry_wait=0.1 — the timeout should
        fire between attempts. Total elapsed should be in [0.3, 0.3 + tolerance].

        # Feature: retry-native-timeout, Property 2: Total Timeout Monotonic Bound (sync)

        **Validates: Requirements 3.1, 3.2**
        """
        call_count = [0]

        def fast_fail():
            call_count[0] += 1
            raise RuntimeError("instant failure")

        start = time.monotonic()
        with pytest.raises(TimeoutError):
            execute_with_retry(
                func=fast_fail,
                max_retry=100,
                min_retry_wait=0.1,
                max_retry_wait=0.1,
                total_timeout=0.3,
            )
        elapsed = time.monotonic() - start

        # Should timeout around 0.3s. With 0.1s sleep between attempts,
        # we expect ~3 attempts before the deadline.
        assert elapsed >= 0.3, (
            f"Elapsed {elapsed:.3f}s < 0.3s — timeout fired too early"
        )
        assert elapsed < 0.3 + self.TIMING_TOLERANCE, (
            f"Elapsed {elapsed:.3f}s exceeded upper bound of {0.3 + self.TIMING_TOLERANCE:.1f}s"
        )
        # At least 1 attempt must have been made
        assert call_count[0] >= 1, "Expected at least 1 attempt"

    def test_sleep_truncation(self):
        """With total_timeout=0.2, func that fails immediately, max_retry=100,
        min_retry_wait=0.5 — the sleep (0.5s) should be truncated to the
        remaining budget. Total time should be close to 0.2s, not 0.5s+.

        # Feature: retry-native-timeout, Property 2: Total Timeout Monotonic Bound (sync)

        **Validates: Requirements 3.2, 3.3**
        """
        call_count = [0]

        def instant_fail():
            call_count[0] += 1
            raise RuntimeError("instant failure")

        start = time.monotonic()
        with pytest.raises(TimeoutError):
            execute_with_retry(
                func=instant_fail,
                max_retry=100,
                min_retry_wait=0.5,
                max_retry_wait=0.5,
                total_timeout=0.2,
            )
        elapsed = time.monotonic() - start

        # The sleep (0.5s) should be truncated to remaining budget (~0.2s).
        # Total elapsed should be close to total_timeout, not min_retry_wait.
        assert elapsed < 0.5, (
            f"Elapsed {elapsed:.3f}s >= 0.5s — sleep was NOT truncated to remaining budget"
        )
        assert elapsed < 0.2 + self.TIMING_TOLERANCE, (
            f"Elapsed {elapsed:.3f}s exceeded upper bound of {0.2 + self.TIMING_TOLERANCE:.1f}s"
        )
        # At least 1 attempt must have been made
        assert call_count[0] >= 1, "Expected at least 1 attempt"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
