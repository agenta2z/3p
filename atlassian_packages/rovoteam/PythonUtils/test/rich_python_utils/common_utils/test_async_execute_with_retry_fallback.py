"""Property-based tests for async async_execute_with_retry fallback behavior.

Feature: retry-native-timeout

Tests correctness properties from the design document:

- Property 1: Backward Compatibility Preservation (async)
- Property 6: Fallback Chain Exhaustion (async)
- Property 7: Fallback Ordering Guarantee (async)
- Property 8: Timeout Supersedes Fallback (async)
- Property 9: Fallback Exception Filtering (async)
- Property 17: on_fallback_callback Single-Fire (async)
- Property 18: on_retry_callback Attempt Reset (async)
- Property 20: Two-Tier Wiring

**Validates: Requirements 6.2, 10.4, 10.5, 10.6, 10.7, 11.2, 11.3, 13.1, 13.2, 14.2**
"""
import asyncio
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
from hypothesis import given, settings, strategies as st, assume

from python_utils.common_utils.async_utils import async_execute_with_retry, FallbackMode


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

small_max_retry = st.integers(min_value=1, max_value=5)
chain_length = st.integers(min_value=1, max_value=4)
fallback_mode_strategy = st.sampled_from([FallbackMode.ON_EXHAUSTED, FallbackMode.ON_FIRST_FAILURE])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_async_recording_callable(call_log, label):
    """Create an async callable that records its invocations and always raises."""
    async def _func(*args, **kwargs):
        call_log.append(label)
        raise RuntimeError(f"fail-{label}")
    return _func


def make_async_counting_callable(counter_dict, label):
    """Create an async callable that counts invocations and always raises."""
    counter_dict[label] = 0
    async def _func(*args, **kwargs):
        counter_dict[label] += 1
        raise RuntimeError(f"fail-{label}")
    return _func


# ---------------------------------------------------------------------------
# Property 1: Backward Compatibility Preservation (async)
# ---------------------------------------------------------------------------

class TestAsyncBackwardCompatibilityPreservation:
    """Property 1: Backward Compatibility Preservation (async).

    When no fallback params are provided (defaults), behavior should be
    identical to current implementation: same return value, same exception
    type, same number of attempts, same callback invocations.

    CRITICAL: Async semantics: `for attempt in range(max_retry)` = max_retry total calls.

    # Feature: retry-native-timeout, Property 1: Backward Compatibility Preservation (async)

    **Validates: Requirements 6.2, 14.2**
    """

    @settings(max_examples=100)
    @given(max_retry=st.integers(min_value=1, max_value=5))
    def test_no_fallback_params_same_attempt_count(self, max_retry: int):
        """With default new params, the number of attempts should match
        the existing async implementation: max_retry total calls for always-failing func.

        CRITICAL: Async semantics: `for attempt in range(max_retry)` = max_retry total calls.

        # Feature: retry-native-timeout, Property 1: Backward Compatibility Preservation (async)

        **Validates: Requirements 6.2, 14.2**
        """
        call_count = [0]

        async def always_fail():
            call_count[0] += 1
            raise RuntimeError("intentional failure")

        # Async: max_retry total calls (via `for attempt in range(max_retry)`)
        expected_calls = max_retry

        async def run():
            await async_execute_with_retry(
                func=always_fail,
                max_retry=max_retry,
                min_retry_wait=0,
                max_retry_wait=0,
                # All new params at defaults
            )

        with pytest.raises(Exception):
            asyncio.run(run())

        assert call_count[0] == expected_calls, (
            f"Expected {expected_calls} calls with max_retry={max_retry}, "
            f"got {call_count[0]}"
        )

    @settings(max_examples=100)
    @given(max_retry=st.integers(min_value=1, max_value=5))
    def test_no_fallback_params_same_exception_type(self, max_retry: int):
        """With default new params, the terminal exception should be RuntimeError
        (the last exception raised by the function), since async helper re-raises
        last_exception when no fallback is configured.

        # Feature: retry-native-timeout, Property 1: Backward Compatibility Preservation (async)

        **Validates: Requirements 6.2, 14.2**
        """
        async def always_fail():
            raise RuntimeError("intentional failure")

        async def run():
            await async_execute_with_retry(
                func=always_fail,
                max_retry=max_retry,
                min_retry_wait=0,
                max_retry_wait=0,
            )

        with pytest.raises(RuntimeError, match="intentional failure"):
            asyncio.run(run())

    @settings(max_examples=100)
    @given(max_retry=st.integers(min_value=2, max_value=5))
    def test_no_fallback_params_callback_invocations(self, max_retry: int):
        """With default new params, on_retry_callback should fire on each failed
        attempt. Async semantics: max_retry total calls, callback fires on each
        failed attempt (attempts 0 through max_retry-1).

        # Feature: retry-native-timeout, Property 1: Backward Compatibility Preservation (async)

        **Validates: Requirements 6.2, 14.2**
        """
        callback_log = []

        async def always_fail():
            raise RuntimeError("intentional failure")

        async def on_retry(attempt, exc):
            callback_log.append(attempt)

        async def run():
            await async_execute_with_retry(
                func=always_fail,
                max_retry=max_retry,
                min_retry_wait=0,
                max_retry_wait=0,
                on_retry_callback=on_retry,
            )

        with pytest.raises(Exception):
            asyncio.run(run())

        # Async: on_retry_callback fires on each failed attempt
        # With max_retry attempts, callback fires max_retry times
        # (the last attempt also fires the callback before the loop ends)
        # But the last attempt doesn't fire callback because there's no retry after it
        # Actually: looking at the code, callback fires for attempts 0..max_retry-2
        # (not on the last attempt since attempt < current_max_attempts - 1 guard on sleep,
        # but callback fires before the sleep guard)
        # The callback fires on every failed attempt: attempts 0, 1, ..., max_retry-1
        expected = list(range(max_retry))
        assert callback_log == expected, (
            f"Expected callback attempts {expected}, got {callback_log}"
        )


# ---------------------------------------------------------------------------
# Property 6: Fallback Chain Exhaustion (async)
# ---------------------------------------------------------------------------

class TestAsyncFallbackChainExhaustion:
    """Property 6: Fallback Chain Exhaustion (async).

    For any fallback chain of length C (primary + C-1 fallbacks) where all
    callables always fail:
    - ON_EXHAUSTED: total = C * max_retry
    - ON_FIRST_FAILURE: primary gets 1 attempt, subsequent get max_retry.
      Total = 1 + (C-1) * max_retry

    CRITICAL: Async semantics: `for attempt in range(max_retry)` = max_retry total calls.

    # Feature: retry-native-timeout, Property 6: Fallback Chain Exhaustion (async)

    **Validates: Requirements 10.4, 10.5, 10.6**
    """

    @settings(max_examples=100)
    @given(
        num_fallbacks=chain_length,
        max_retry=small_max_retry,
    )
    def test_on_exhausted_total_attempts(self, num_fallbacks: int, max_retry: int):
        """ON_EXHAUSTED: total attempts = C * max_retry where C is chain length.

        CRITICAL: Async semantics: `for attempt in range(max_retry)` = max_retry total calls.

        # Feature: retry-native-timeout, Property 6: Fallback Chain Exhaustion (async)

        **Validates: Requirements 10.4, 10.6**
        """
        counters = {}
        chain_size = 1 + num_fallbacks  # primary + fallbacks

        primary = make_async_counting_callable(counters, "primary")
        fallbacks = [
            make_async_counting_callable(counters, f"fb_{i}")
            for i in range(num_fallbacks)
        ]

        # Async: max_retry total calls per callable
        expected_total = chain_size * max_retry

        async def run():
            await async_execute_with_retry(
                func=primary,
                max_retry=max_retry,
                min_retry_wait=0,
                max_retry_wait=0,
                fallback_func=fallbacks,
                fallback_mode=FallbackMode.ON_EXHAUSTED,
            )

        with pytest.raises(Exception):
            asyncio.run(run())

        actual_total = sum(counters.values())
        assert actual_total == expected_total, (
            f"ON_EXHAUSTED: chain_size={chain_size}, max_retry={max_retry}, "
            f"expected {expected_total} total attempts, got {actual_total}. "
            f"Counters: {counters}"
        )

    @settings(max_examples=100)
    @given(
        num_fallbacks=chain_length,
        max_retry=small_max_retry,
    )
    def test_on_first_failure_total_attempts(self, num_fallbacks: int, max_retry: int):
        """ON_FIRST_FAILURE: primary gets 1 attempt, subsequent get max_retry.
        Total = 1 + (C-1) * max_retry where C is chain length.

        CRITICAL: Async semantics: `for attempt in range(max_retry)` = max_retry total calls.

        # Feature: retry-native-timeout, Property 6: Fallback Chain Exhaustion (async)

        **Validates: Requirements 10.5, 10.6**
        """
        counters = {}
        chain_size = 1 + num_fallbacks

        primary = make_async_counting_callable(counters, "primary")
        fallbacks = [
            make_async_counting_callable(counters, f"fb_{i}")
            for i in range(num_fallbacks)
        ]

        # Async: primary gets 1 attempt, each subsequent gets max_retry
        expected_total = 1 + num_fallbacks * max_retry

        async def run():
            await async_execute_with_retry(
                func=primary,
                max_retry=max_retry,
                min_retry_wait=0,
                max_retry_wait=0,
                fallback_func=fallbacks,
                fallback_mode=FallbackMode.ON_FIRST_FAILURE,
            )

        with pytest.raises(Exception):
            asyncio.run(run())

        actual_total = sum(counters.values())
        assert actual_total == expected_total, (
            f"ON_FIRST_FAILURE: chain_size={chain_size}, max_retry={max_retry}, "
            f"expected {expected_total} total attempts, got {actual_total}. "
            f"Counters: {counters}"
        )

        # Primary should have exactly 1 attempt
        assert counters["primary"] == 1, (
            f"ON_FIRST_FAILURE: primary should have 1 attempt, got {counters['primary']}"
        )


# ---------------------------------------------------------------------------
# Property 7: Fallback Ordering Guarantee (async)
# ---------------------------------------------------------------------------

class TestAsyncFallbackOrderingGuarantee:
    """Property 7: Fallback Ordering Guarantee (async).

    For any fallback chain [func, fb_0, fb_1, ..., fb_n], the Retry_Helper
    SHALL invoke callables strictly in order. It SHALL never skip a callable
    or reorder them.

    # Feature: retry-native-timeout, Property 7: Fallback Ordering Guarantee (async)

    **Validates: Requirements 10.7**
    """

    @settings(max_examples=100)
    @given(
        num_fallbacks=chain_length,
        mode=fallback_mode_strategy,
    )
    def test_invocation_order_is_strict(self, num_fallbacks: int, mode: FallbackMode):
        """Callables are invoked in strict chain order: primary, fb_0, fb_1, ...

        # Feature: retry-native-timeout, Property 7: Fallback Ordering Guarantee (async)

        **Validates: Requirements 10.7**
        """
        call_log = []

        primary = make_async_recording_callable(call_log, "primary")
        fallbacks = [
            make_async_recording_callable(call_log, f"fb_{i}")
            for i in range(num_fallbacks)
        ]

        async def run():
            await async_execute_with_retry(
                func=primary,
                max_retry=1,
                min_retry_wait=0,
                max_retry_wait=0,
                fallback_func=fallbacks,
                fallback_mode=mode,
            )

        with pytest.raises(Exception):
            asyncio.run(run())

        # Extract unique labels in order of first appearance
        seen = set()
        order = []
        for label in call_log:
            if label not in seen:
                seen.add(label)
                order.append(label)

        expected_order = ["primary"] + [f"fb_{i}" for i in range(num_fallbacks)]
        assert order == expected_order, (
            f"Expected invocation order {expected_order}, got {order}. "
            f"Full call log: {call_log}"
        )

    @settings(max_examples=100)
    @given(
        num_fallbacks=chain_length,
        mode=fallback_mode_strategy,
    )
    def test_no_callable_skipped(self, num_fallbacks: int, mode: FallbackMode):
        """Every callable in the chain must be invoked at least once.

        # Feature: retry-native-timeout, Property 7: Fallback Ordering Guarantee (async)

        **Validates: Requirements 10.7**
        """
        counters = {}

        primary = make_async_counting_callable(counters, "primary")
        fallbacks = [
            make_async_counting_callable(counters, f"fb_{i}")
            for i in range(num_fallbacks)
        ]

        async def run():
            await async_execute_with_retry(
                func=primary,
                max_retry=1,
                min_retry_wait=0,
                max_retry_wait=0,
                fallback_func=fallbacks,
                fallback_mode=mode,
            )

        with pytest.raises(Exception):
            asyncio.run(run())

        for label in ["primary"] + [f"fb_{i}" for i in range(num_fallbacks)]:
            assert counters[label] >= 1, (
                f"Callable '{label}' was never invoked. Counters: {counters}"
            )


# ---------------------------------------------------------------------------
# Property 8: Timeout Supersedes Fallback (async)
# ---------------------------------------------------------------------------

class TestAsyncTimeoutSupersedesFallback:
    """Property 8: Timeout Supersedes Fallback (async).

    When both total_timeout and fallback_func are set, if the total timeout
    deadline expires during any callable in the chain, the Retry_Helper SHALL
    raise TimeoutError immediately without transitioning to the next fallback.
    Remaining callables SHALL never be invoked.

    # Feature: retry-native-timeout, Property 8: Timeout Supersedes Fallback (async)

    **Validates: Requirements 13.1, 13.2**
    """

    @settings(max_examples=100, deadline=30000)
    @given(
        num_fallbacks=st.integers(min_value=3, max_value=5),
    )
    def test_timeout_prevents_remaining_fallbacks(self, num_fallbacks: int):
        """With a tight total_timeout and slow async callables, TimeoutError should
        fire before all fallbacks are reached.

        # Feature: retry-native-timeout, Property 8: Timeout Supersedes Fallback (async)

        **Validates: Requirements 13.1, 13.2**
        """
        call_log = []

        def make_slow_async_fail(label):
            async def _func(*args, **kwargs):
                call_log.append(label)
                await asyncio.sleep(0.1)
                raise RuntimeError(f"fail-{label}")
            return _func

        primary = make_slow_async_fail("primary")
        fallbacks = [make_slow_async_fail(f"fb_{i}") for i in range(num_fallbacks)]

        # total_timeout tight enough that not all callables can run
        # Each callable sleeps 0.1s, with max_retry=1 that's 0.1s per callable
        # With num_fallbacks >= 3, chain has >= 4 callables = 0.4s minimum
        # Set timeout to allow only ~1-2 callables
        total_timeout = 0.15

        async def run():
            await async_execute_with_retry(
                func=primary,
                max_retry=1,
                min_retry_wait=0,
                max_retry_wait=0,
                fallback_func=fallbacks,
                fallback_mode=FallbackMode.ON_EXHAUSTED,
                total_timeout=total_timeout,
            )

        with pytest.raises(TimeoutError):
            asyncio.run(run())

        # Not all callables should have been invoked
        unique_labels = set(call_log)
        all_labels = {"primary"} | {f"fb_{i}" for i in range(num_fallbacks)}
        assert unique_labels < all_labels, (
            f"All callables were invoked despite tight timeout. "
            f"Invoked: {unique_labels}, All: {all_labels}"
        )


# ---------------------------------------------------------------------------
# Property 9: Fallback Exception Filtering (async)
# ---------------------------------------------------------------------------

class TestAsyncFallbackExceptionFiltering:
    """Property 9: Fallback Exception Filtering (async).

    For any fallback_on_exceptions tuple and any exception type raised:
    - Matching exceptions trigger transition to next fallback.
    - Non-matching exceptions propagate immediately.

    # Feature: retry-native-timeout, Property 9: Fallback Exception Filtering (async)

    **Validates: Requirements 11.2, 11.3**
    """

    # Custom exception types for testing
    class AlphaError(Exception):
        pass

    class BetaError(Exception):
        pass

    class GammaError(Exception):
        pass

    @settings(max_examples=100)
    @given(
        filter_idx=st.integers(min_value=0, max_value=2),
        raise_idx=st.integers(min_value=0, max_value=2),
    )
    def test_matching_exception_triggers_transition(self, filter_idx: int, raise_idx: int):
        """When the raised exception matches fallback_on_exceptions, the
        fallback chain should transition to the next callable.

        # Feature: retry-native-timeout, Property 9: Fallback Exception Filtering (async)

        **Validates: Requirements 11.2, 11.3**
        """
        exc_types = [self.AlphaError, self.BetaError, self.GammaError]
        filter_type = exc_types[filter_idx]
        raise_type = exc_types[raise_idx]

        call_log = []

        async def primary(*args, **kwargs):
            call_log.append("primary")
            raise raise_type("primary failure")

        async def fallback(*args, **kwargs):
            call_log.append("fallback")
            return "fallback_result"

        async def run():
            return await async_execute_with_retry(
                func=primary,
                max_retry=1,
                min_retry_wait=0,
                max_retry_wait=0,
                fallback_func=[fallback],
                fallback_mode=FallbackMode.ON_FIRST_FAILURE,
                fallback_on_exceptions=(filter_type,),
            )

        if filter_idx == raise_idx:
            # Matching: fallback should be reached
            result = asyncio.run(run())
            assert result == "fallback_result", (
                f"Expected fallback result when exception matches filter"
            )
            assert "fallback" in call_log, "Fallback should have been invoked"
        else:
            # Non-matching: exception should propagate immediately
            with pytest.raises(raise_type):
                asyncio.run(run())
            assert "fallback" not in call_log, (
                f"Fallback should NOT be invoked when exception doesn't match filter"
            )

    @settings(max_examples=100)
    @given(
        mode=fallback_mode_strategy,
    )
    def test_none_filter_allows_all_exceptions(self, mode: FallbackMode):
        """When fallback_on_exceptions is None, any exception triggers transition.

        # Feature: retry-native-timeout, Property 9: Fallback Exception Filtering (async)

        **Validates: Requirements 11.2**
        """
        call_log = []

        async def primary(*args, **kwargs):
            call_log.append("primary")
            raise RuntimeError("any error")

        async def fallback(*args, **kwargs):
            call_log.append("fallback")
            return "ok"

        async def run():
            return await async_execute_with_retry(
                func=primary,
                max_retry=1,
                min_retry_wait=0,
                max_retry_wait=0,
                fallback_func=[fallback],
                fallback_mode=mode,
                fallback_on_exceptions=None,
            )

        result = asyncio.run(run())
        assert result == "ok"
        assert "fallback" in call_log


# ---------------------------------------------------------------------------
# Property 17: on_fallback_callback Single-Fire (async)
# ---------------------------------------------------------------------------

class TestAsyncOnFallbackCallbackSingleFire:
    """Property 17: on_fallback_callback Single-Fire Per Transition (async).

    For any chain transition, on_fallback_callback SHALL fire exactly once,
    before the next callable's first attempt. It SHALL NOT fire on
    intra-callable retries.

    # Feature: retry-native-timeout, Property 17: on_fallback_callback Single-Fire (async)

    **Validates: on_fallback_callback hook design**
    """

    @settings(max_examples=100)
    @given(
        num_fallbacks=chain_length,
        max_retry=small_max_retry,
        mode=fallback_mode_strategy,
    )
    def test_callback_fires_once_per_transition(
        self, num_fallbacks: int, max_retry: int, mode: FallbackMode
    ):
        """on_fallback_callback fires exactly (chain_length - 1) times
        (once per transition between callables).

        # Feature: retry-native-timeout, Property 17: on_fallback_callback Single-Fire (async)

        **Validates: Requirements 11.2, 11.3**
        """
        callback_log = []
        counters = {}

        primary = make_async_counting_callable(counters, "primary")
        fallbacks = [
            make_async_counting_callable(counters, f"fb_{i}")
            for i in range(num_fallbacks)
        ]

        async def on_fallback(from_func, to_func, exception, total_attempts):
            callback_log.append({
                "from": from_func,
                "to": to_func,
                "exception": exception,
                "total_attempts": total_attempts,
            })

        async def run():
            await async_execute_with_retry(
                func=primary,
                max_retry=max_retry,
                min_retry_wait=0,
                max_retry_wait=0,
                fallback_func=fallbacks,
                fallback_mode=mode,
                on_fallback_callback=on_fallback,
            )

        with pytest.raises(Exception):
            asyncio.run(run())

        # Number of transitions = number of fallbacks (chain_length - 1)
        expected_transitions = num_fallbacks
        assert len(callback_log) == expected_transitions, (
            f"Expected {expected_transitions} callback invocations (one per transition), "
            f"got {len(callback_log)}"
        )

    @settings(max_examples=100)
    @given(
        max_retry=small_max_retry,
    )
    def test_callback_receives_correct_args(self, max_retry: int):
        """on_fallback_callback receives (from_func, to_func, exception, total_attempts).

        # Feature: retry-native-timeout, Property 17: on_fallback_callback Single-Fire (async)

        **Validates: Requirements 11.2, 11.3**
        """
        callback_log = []

        async def primary(*args, **kwargs):
            raise RuntimeError("primary fail")

        async def fallback(*args, **kwargs):
            raise RuntimeError("fallback fail")

        async def on_fallback(from_func, to_func, exception, total_attempts):
            callback_log.append({
                "from": from_func,
                "to": to_func,
                "exception": exception,
                "total_attempts": total_attempts,
            })

        async def run():
            await async_execute_with_retry(
                func=primary,
                max_retry=max_retry,
                min_retry_wait=0,
                max_retry_wait=0,
                fallback_func=[fallback],
                fallback_mode=FallbackMode.ON_EXHAUSTED,
                on_fallback_callback=on_fallback,
            )

        with pytest.raises(Exception):
            asyncio.run(run())

        assert len(callback_log) == 1
        entry = callback_log[0]
        assert entry["from"] is primary
        assert entry["to"] is fallback
        assert isinstance(entry["exception"], RuntimeError)
        # ON_EXHAUSTED async: primary gets max_retry attempts
        assert entry["total_attempts"] == max_retry, (
            f"Expected total_attempts={max_retry}, got {entry['total_attempts']}"
        )


# ---------------------------------------------------------------------------
# Property 18: on_retry_callback Attempt Reset (async)
# ---------------------------------------------------------------------------

class TestAsyncOnRetryCallbackAttemptReset:
    """Property 18: on_retry_callback Attempt Reset (async).

    For any chain transition, the attempt argument passed to on_retry_callback
    SHALL reset to 0 for the new callable. Existing callbacks see per-function
    attempt counts (backward-compatible).

    # Feature: retry-native-timeout, Property 18: on_retry_callback Attempt Reset (async)

    **Validates: on_retry_callback backward compatibility**
    """

    @settings(max_examples=100)
    @given(
        num_fallbacks=chain_length,
        max_retry=st.integers(min_value=2, max_value=5),
    )
    def test_attempt_resets_at_each_callable(self, num_fallbacks: int, max_retry: int):
        """The attempt arg in on_retry_callback starts at 0 for each new
        callable in the chain.

        # Feature: retry-native-timeout, Property 18: on_retry_callback Attempt Reset (async)

        **Validates: on_retry_callback backward compatibility**
        """
        callback_log = []
        call_log = []

        def make_async_func(label):
            async def _func(*args, **kwargs):
                call_log.append(label)
                raise RuntimeError(f"fail-{label}")
            return _func

        primary = make_async_func("primary")
        fallbacks = [make_async_func(f"fb_{i}") for i in range(num_fallbacks)]

        async def on_retry(attempt, exc):
            # Record which callable is active based on the last call_log entry
            current_label = call_log[-1] if call_log else "unknown"
            callback_log.append((current_label, attempt))

        async def run():
            await async_execute_with_retry(
                func=primary,
                max_retry=max_retry,
                min_retry_wait=0,
                max_retry_wait=0,
                fallback_func=fallbacks,
                fallback_mode=FallbackMode.ON_EXHAUSTED,
                on_retry_callback=on_retry,
            )

        with pytest.raises(Exception):
            asyncio.run(run())

        # Group attempts by callable label
        attempts_by_callable = {}
        for label, attempt in callback_log:
            if label not in attempts_by_callable:
                attempts_by_callable[label] = []
            attempts_by_callable[label].append(attempt)

        # Each callable's attempts should start at 0
        for label, attempts in attempts_by_callable.items():
            assert attempts[0] == 0, (
                f"Callable '{label}' first retry attempt should be 0, "
                f"got {attempts[0]}. All attempts: {attempts}"
            )
            # Attempts should be sequential: 0, 1, 2, ...
            expected = list(range(len(attempts)))
            assert attempts == expected, (
                f"Callable '{label}' attempts should be {expected}, got {attempts}"
            )


# ---------------------------------------------------------------------------
# Property 20: Two-Tier Wiring
# ---------------------------------------------------------------------------

class TestTwoTierWiring:
    """Property 20: Two-Tier Wiring.

    For any InferencerBase configuration with fallback_mode != NEVER,
    the fallback chain passed to the helper SHALL be
    [recovery_wrapper] + external_wrappers. Recovery is always tried
    before external escalations.

    We test this at the helper level by verifying invocation order with
    recording callables: when building a chain with
    [recovery_wrapper, external_wrapper], the recovery_wrapper is always first.

    # Feature: retry-native-timeout, Property 20: Two-Tier Wiring

    **Validates: Two-tier wiring design**
    """

    @settings(max_examples=100)
    @given(
        num_external=st.integers(min_value=1, max_value=3),
        mode=fallback_mode_strategy,
    )
    def test_recovery_wrapper_is_first_in_chain(self, num_external: int, mode: FallbackMode):
        """When building a chain with [recovery_wrapper, ext_0, ext_1, ...],
        the recovery_wrapper is always invoked before any external wrapper.

        This simulates the InferencerBase wiring pattern where _ainfer_recovery
        is the first fallback, followed by external fallback inferencers.

        # Feature: retry-native-timeout, Property 20: Two-Tier Wiring

        **Validates: Two-tier wiring design**
        """
        call_log = []

        async def primary(*args, **kwargs):
            call_log.append("primary")
            raise RuntimeError("primary fail")

        async def recovery_wrapper(*args, **kwargs):
            call_log.append("recovery")
            raise RuntimeError("recovery fail")

        external_wrappers = []
        for i in range(num_external):
            label = f"external_{i}"
            async def make_ext(lbl=label):
                call_log.append(lbl)
                raise RuntimeError(f"{lbl} fail")
            external_wrappers.append(make_ext)

        # Build chain as InferencerBase would: [recovery_wrapper] + external_wrappers
        fallback_chain = [recovery_wrapper] + external_wrappers

        async def run():
            await async_execute_with_retry(
                func=primary,
                max_retry=1,
                min_retry_wait=0,
                max_retry_wait=0,
                fallback_func=fallback_chain,
                fallback_mode=mode,
            )

        with pytest.raises(Exception):
            asyncio.run(run())

        # Extract unique labels in order of first appearance
        seen = set()
        order = []
        for label in call_log:
            if label not in seen:
                seen.add(label)
                order.append(label)

        # Recovery should always come right after primary, before any external
        expected_order = ["primary", "recovery"] + [f"external_{i}" for i in range(num_external)]
        assert order == expected_order, (
            f"Expected invocation order {expected_order}, got {order}. "
            f"Recovery wrapper must be first in fallback chain (before external wrappers). "
            f"Full call log: {call_log}"
        )

    @settings(max_examples=100)
    @given(
        mode=fallback_mode_strategy,
    )
    def test_recovery_only_chain_when_no_external(self, mode: FallbackMode):
        """When fallback_inferencer=None, the chain is [recovery_wrapper] (length 1).
        Recovery is the only fallback after primary.

        # Feature: retry-native-timeout, Property 20: Two-Tier Wiring

        **Validates: Two-tier wiring design**
        """
        call_log = []

        async def primary(*args, **kwargs):
            call_log.append("primary")
            raise RuntimeError("primary fail")

        async def recovery_wrapper(*args, **kwargs):
            call_log.append("recovery")
            raise RuntimeError("recovery fail")

        async def run():
            await async_execute_with_retry(
                func=primary,
                max_retry=1,
                min_retry_wait=0,
                max_retry_wait=0,
                fallback_func=[recovery_wrapper],
                fallback_mode=mode,
            )

        with pytest.raises(Exception):
            asyncio.run(run())

        # Extract unique labels in order of first appearance
        seen = set()
        order = []
        for label in call_log:
            if label not in seen:
                seen.add(label)
                order.append(label)

        expected_order = ["primary", "recovery"]
        assert order == expected_order, (
            f"Expected invocation order {expected_order}, got {order}. "
            f"Full call log: {call_log}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
