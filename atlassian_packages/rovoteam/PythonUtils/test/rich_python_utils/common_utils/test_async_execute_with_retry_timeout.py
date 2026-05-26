"""Property-based and timed integration tests for async_execute_with_retry timeout behavior.

Feature: retry-native-timeout

Tests correctness properties from the design document:

- Property 2: Total Timeout Monotonic Bound (async) — timed integration tests
- Property 3: Per-Attempt Timeout Bound (async) — timed integration tests
- Property 5: Error Normalization Invariant (async) — generate timeout scenarios,
  verify built-in TimeoutError (not asyncio.TimeoutError) raised

**Validates: Requirements 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 5.2, 5.3, 13.3, 13.4**
"""
import asyncio
import sys
import time
from pathlib import Path

# Setup import paths — same pattern as sync timeout test file
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

from python_utils.common_utils.async_utils import async_execute_with_retry


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Very small total_timeout values that will expire before the function completes
small_total_timeout_strategy = st.floats(
    min_value=0.01, max_value=0.1,
    allow_nan=False, allow_infinity=False,
)

# Small per-attempt timeout values
small_attempt_timeout_strategy = st.floats(
    min_value=0.01, max_value=0.1,
    allow_nan=False, allow_infinity=False,
)


# ---------------------------------------------------------------------------
# Property 5: Error Normalization Invariant (async)
# ---------------------------------------------------------------------------

class TestAsyncErrorNormalizationInvariant:
    """Property 5: Error Normalization Invariant (async).

    For any timeout scenario (per-attempt expiry, total timeout expiry),
    the exception raised to the caller SHALL be an instance of the built-in
    TimeoutError (i.e., type(e) is TimeoutError). No asyncio.TimeoutError
    SHALL escape the Retry_Helper boundary.

    # Feature: retry-native-timeout, Property 5: Error Normalization Invariant (async)

    **Validates: Requirements 1.1, 1.2, 1.3, 2.1, 2.2, 5.2, 5.3**
    """

    @settings(max_examples=100, deadline=30000)
    @given(total_timeout=small_total_timeout_strategy)
    def test_total_timeout_raises_builtin_timeout_error(self, total_timeout: float):
        """When total_timeout expires in async_execute_with_retry, the raised
        exception SHALL be the built-in TimeoutError (not asyncio.TimeoutError).

        Uses an async func that always fails after a short sleep, with many
        retries and zero wait so the deadline is hit between attempts.

        # Feature: retry-native-timeout, Property 5: Error Normalization Invariant (async)

        **Validates: Requirements 2.1, 2.2, 5.2, 5.3**
        """

        async def always_fail():
            await asyncio.sleep(0.005)
            raise RuntimeError("intentional failure")

        async def run():
            await async_execute_with_retry(
                func=always_fail,
                max_retry=1000,
                min_retry_wait=0,
                max_retry_wait=0,
                total_timeout=total_timeout,
            )

        with pytest.raises(TimeoutError) as exc_info:
            asyncio.run(run())

        raised = exc_info.value
        # Must be exactly built-in TimeoutError, not asyncio.TimeoutError
        assert type(raised) is TimeoutError, (
            f"Expected exactly built-in TimeoutError, got {type(raised).__name__}; "
            "asyncio.TimeoutError should not escape the retry helper boundary"
        )

    @settings(max_examples=100, deadline=30000)
    @given(attempt_timeout=small_attempt_timeout_strategy)
    def test_attempt_timeout_raises_builtin_timeout_error(self, attempt_timeout: float):
        """When attempt_timeout expires on every attempt and retries are exhausted,
        the raised exception SHALL be the built-in TimeoutError (not asyncio.TimeoutError).

        Uses an async func that sleeps longer than the attempt_timeout, so every
        attempt is killed by asyncio.wait_for. After max_retry exhaustion, the
        normalized TimeoutError should be raised.

        # Feature: retry-native-timeout, Property 5: Error Normalization Invariant (async)

        **Validates: Requirements 1.1, 1.2, 5.2, 5.3**
        """

        async def slow_func():
            # Sleep much longer than any attempt_timeout we generate
            await asyncio.sleep(10.0)
            return "should_not_reach"

        async def run():
            await async_execute_with_retry(
                func=slow_func,
                max_retry=2,
                min_retry_wait=0,
                max_retry_wait=0,
                attempt_timeout=attempt_timeout,
            )

        with pytest.raises(TimeoutError) as exc_info:
            asyncio.run(run())

        raised = exc_info.value
        # Must be exactly built-in TimeoutError, not asyncio.TimeoutError
        assert type(raised) is TimeoutError, (
            f"Expected exactly built-in TimeoutError, got {type(raised).__name__}; "
            "asyncio.TimeoutError should not escape the retry helper boundary"
        )

    @settings(max_examples=100, deadline=30000)
    @given(
        total_timeout=small_total_timeout_strategy,
        attempt_timeout=small_attempt_timeout_strategy,
    )
    def test_both_timeouts_raise_builtin_timeout_error(
        self, total_timeout: float, attempt_timeout: float
    ):
        """When both attempt_timeout and total_timeout are set and the function
        always times out, the raised exception SHALL be the built-in TimeoutError
        regardless of which timeout fires first.

        # Feature: retry-native-timeout, Property 5: Error Normalization Invariant (async)

        **Validates: Requirements 1.1, 1.3, 2.1, 2.2, 5.2, 5.3**
        """

        async def slow_func():
            await asyncio.sleep(10.0)
            return "should_not_reach"

        async def run():
            await async_execute_with_retry(
                func=slow_func,
                max_retry=1000,
                min_retry_wait=0,
                max_retry_wait=0,
                total_timeout=total_timeout,
                attempt_timeout=attempt_timeout,
            )

        with pytest.raises(TimeoutError) as exc_info:
            asyncio.run(run())

        raised = exc_info.value
        # Must be exactly built-in TimeoutError, not asyncio.TimeoutError
        assert type(raised) is TimeoutError, (
            f"Expected exactly built-in TimeoutError, got {type(raised).__name__}; "
            "asyncio.TimeoutError should not escape the retry helper boundary"
        )


# ---------------------------------------------------------------------------
# Property 2: Total Timeout Monotonic Bound (async) — Timed Integration Tests
# ---------------------------------------------------------------------------

class TestAsyncTotalTimeoutMonotonicBound:
    """Property 2: Total Timeout Monotonic Bound (async).

    For any positive total_timeout value and for any function and retry
    configuration, the async Retry_Helper SHALL complete (return or raise)
    within total_timeout + epsilon wall-clock seconds (where epsilon accounts
    for scheduling jitter).

    These are timed integration tests (not PBT) because wall-clock timing
    is not suitable for property-based testing.

    # Feature: retry-native-timeout, Property 2: Total Timeout Monotonic Bound (async)

    **Validates: Requirements 2.1, 2.2, 2.3**
    """

    TIMING_TOLERANCE = 0.3  # seconds — accounts for CI/scheduling jitter

    def test_total_timeout_with_failing_func(self):
        """total_timeout=0.3 with async func that always fails after 0.01s sleep,
        max_retry=1000 → should timeout within [0.3, 0.3 + epsilon].

        # Feature: retry-native-timeout, Property 2: Total Timeout Monotonic Bound (async)

        **Validates: Requirements 2.1, 2.2**
        """
        call_count = [0]

        async def always_fail():
            call_count[0] += 1
            await asyncio.sleep(0.01)
            raise RuntimeError("intentional failure")

        async def run():
            await async_execute_with_retry(
                func=always_fail,
                max_retry=1000,
                min_retry_wait=0,
                max_retry_wait=0,
                total_timeout=0.3,
            )

        start = time.monotonic()
        with pytest.raises(TimeoutError):
            asyncio.run(run())
        elapsed = time.monotonic() - start

        assert elapsed >= 0.3, (
            f"Elapsed {elapsed:.3f}s < 0.3s — timeout fired too early"
        )
        assert elapsed < 0.3 + self.TIMING_TOLERANCE, (
            f"Elapsed {elapsed:.3f}s exceeded upper bound of "
            f"{0.3 + self.TIMING_TOLERANCE:.1f}s"
        )
        assert call_count[0] >= 1, "Expected at least 1 attempt"

    def test_sleep_truncation(self):
        """total_timeout=0.2 with async func that fails immediately,
        max_retry=1000, min_retry_wait=0.5 → sleep truncated, total close
        to 0.2s (not 0.5s+).

        # Feature: retry-native-timeout, Property 2: Total Timeout Monotonic Bound (async)

        **Validates: Requirements 2.2, 2.3**
        """
        call_count = [0]

        async def instant_fail():
            call_count[0] += 1
            raise RuntimeError("instant failure")

        async def run():
            await async_execute_with_retry(
                func=instant_fail,
                max_retry=1000,
                min_retry_wait=0.5,
                max_retry_wait=0.5,
                total_timeout=0.2,
            )

        start = time.monotonic()
        with pytest.raises(TimeoutError):
            asyncio.run(run())
        elapsed = time.monotonic() - start

        # Sleep (0.5s) should be truncated to remaining budget (~0.2s)
        assert elapsed < 0.5, (
            f"Elapsed {elapsed:.3f}s >= 0.5s — sleep was NOT truncated to remaining budget"
        )
        assert elapsed < 0.2 + self.TIMING_TOLERANCE, (
            f"Elapsed {elapsed:.3f}s exceeded upper bound of "
            f"{0.2 + self.TIMING_TOLERANCE:.1f}s"
        )
        assert call_count[0] >= 1, "Expected at least 1 attempt"


# ---------------------------------------------------------------------------
# Property 3: Per-Attempt Timeout Bound (async) — Timed Integration Tests
# ---------------------------------------------------------------------------

class TestAsyncPerAttemptTimeoutBound:
    """Property 3: Per-Attempt Timeout Bound (async).

    For any positive attempt_timeout value in the async Retry_Helper, no
    single attempt SHALL execute for longer than min(attempt_timeout,
    remaining_budget) + epsilon seconds.

    These are timed integration tests (not PBT) because wall-clock timing
    is not suitable for property-based testing.

    # Feature: retry-native-timeout, Property 3: Per-Attempt Timeout Bound (async)

    **Validates: Requirements 1.1, 1.3, 13.3, 13.4**
    """

    TIMING_TOLERANCE = 0.3  # seconds — accounts for CI/scheduling jitter

    def test_per_attempt_kills_slow_func(self):
        """attempt_timeout=0.1 with async func that sleeps 10s → each attempt
        should be killed at ~0.1s. With max_retry=3, total elapsed should be
        around 0.3s (3 attempts × 0.1s each), not 30s.

        # Feature: retry-native-timeout, Property 3: Per-Attempt Timeout Bound (async)

        **Validates: Requirements 1.1, 1.3**
        """
        attempt_starts: list[float] = []
        attempt_ends: list[float] = []

        async def slow_func():
            attempt_starts.append(time.monotonic())
            try:
                await asyncio.sleep(10.0)
            finally:
                attempt_ends.append(time.monotonic())
            return "should_not_reach"

        async def run():
            await async_execute_with_retry(
                func=slow_func,
                max_retry=3,
                min_retry_wait=0,
                max_retry_wait=0,
                attempt_timeout=0.1,
            )

        start = time.monotonic()
        with pytest.raises(TimeoutError):
            asyncio.run(run())
        elapsed = time.monotonic() - start

        # Each attempt should have been killed at ~0.1s
        for i in range(len(attempt_starts)):
            if i < len(attempt_ends):
                attempt_duration = attempt_ends[i] - attempt_starts[i]
                assert attempt_duration < 0.1 + self.TIMING_TOLERANCE, (
                    f"Attempt {i} ran for {attempt_duration:.3f}s, expected < "
                    f"{0.1 + self.TIMING_TOLERANCE:.1f}s"
                )

        # Total should be roughly 3 × 0.1s, not 3 × 10s
        assert elapsed < 3 * 0.1 + self.TIMING_TOLERANCE, (
            f"Total elapsed {elapsed:.3f}s exceeded expected bound of "
            f"{3 * 0.1 + self.TIMING_TOLERANCE:.1f}s"
        )

    def test_per_attempt_capped_by_remaining_budget(self):
        """attempt_timeout=0.05 with total_timeout=0.3 → effective per-attempt
        = min(0.05, remaining_budget). Each attempt should be killed at ~0.05s.
        Total should be bounded by total_timeout + epsilon.

        # Feature: retry-native-timeout, Property 3: Per-Attempt Timeout Bound (async)

        **Validates: Requirements 1.3, 13.3, 13.4**
        """
        attempt_starts: list[float] = []
        attempt_ends: list[float] = []

        async def slow_func():
            attempt_starts.append(time.monotonic())
            try:
                await asyncio.sleep(10.0)
            finally:
                attempt_ends.append(time.monotonic())
            return "should_not_reach"

        async def run():
            await async_execute_with_retry(
                func=slow_func,
                max_retry=1000,
                min_retry_wait=0,
                max_retry_wait=0,
                attempt_timeout=0.05,
                total_timeout=0.3,
            )

        start = time.monotonic()
        with pytest.raises(TimeoutError):
            asyncio.run(run())
        elapsed = time.monotonic() - start

        # Each attempt should be bounded by min(0.05, remaining)
        for i in range(len(attempt_starts)):
            if i < len(attempt_ends):
                attempt_duration = attempt_ends[i] - attempt_starts[i]
                assert attempt_duration < 0.05 + self.TIMING_TOLERANCE, (
                    f"Attempt {i} ran for {attempt_duration:.3f}s, expected < "
                    f"{0.05 + self.TIMING_TOLERANCE:.1f}s"
                )

        # Total should be bounded by total_timeout + epsilon
        assert elapsed < 0.3 + self.TIMING_TOLERANCE, (
            f"Total elapsed {elapsed:.3f}s exceeded upper bound of "
            f"{0.3 + self.TIMING_TOLERANCE:.1f}s"
        )
        # Should have made multiple attempts (0.3s / 0.05s ≈ 6)
        assert len(attempt_starts) >= 2, (
            f"Expected multiple attempts, got {len(attempt_starts)}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
