"""Property-based tests for sync execute_with_retry fallback behavior.

Feature: retry-native-timeout

Tests correctness properties from the design document:

- Property 1: Backward Compatibility Preservation (sync)
- Property 6: Fallback Chain Exhaustion (sync)
- Property 7: Fallback Ordering Guarantee (sync)
- Property 8: Timeout Supersedes Fallback (sync)
- Property 9: Fallback Exception Filtering (sync)
- Property 17: on_fallback_callback Single-Fire
- Property 18: on_retry_callback Attempt Reset
- Property 19: Input Validation

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

from python_utils.common_utils.function_helper import execute_with_retry, FallbackMode


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

small_max_retry = st.integers(min_value=1, max_value=5)
chain_length = st.integers(min_value=1, max_value=4)
fallback_mode_strategy = st.sampled_from([FallbackMode.ON_EXHAUSTED, FallbackMode.ON_FIRST_FAILURE])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_recording_callable(call_log, label):
    """Create a callable that records its invocations and always raises."""
    def _func(*args, **kwargs):
        call_log.append(label)
        raise RuntimeError(f"fail-{label}")
    return _func


def make_counting_callable(counter_dict, label):
    """Create a callable that counts invocations and always raises."""
    counter_dict[label] = 0
    def _func(*args, **kwargs):
        counter_dict[label] += 1
        raise RuntimeError(f"fail-{label}")
    return _func


# ---------------------------------------------------------------------------
# Property 1: Backward Compatibility Preservation (sync)
# ---------------------------------------------------------------------------

class TestBackwardCompatibilityPreservation:
    """Property 1: Backward Compatibility Preservation (sync).

    When no fallback params are provided (defaults), behavior should be
    identical to current implementation: same return value, same exception
    type, same number of attempts, same callback invocations.

    # Feature: retry-native-timeout, Property 1: Backward Compatibility Preservation (sync)

    **Validates: Requirements 6.2, 14.2**
    """

    @settings(max_examples=100)
    @given(max_retry=st.integers(min_value=2, max_value=5))
    def test_no_fallback_params_same_attempt_count(self, max_retry: int):
        """With default new params, the number of attempts should match
        the existing implementation: 1 + max_retry calls for always-failing func.
        Uses max_retry >= 2 to avoid the fast path (max_retry <= 1 bypasses retry loop).

        # Feature: retry-native-timeout, Property 1: Backward Compatibility Preservation (sync)

        **Validates: Requirements 6.2, 14.2**
        """
        call_count = [0]

        def always_fail():
            call_count[0] += 1
            raise RuntimeError("intentional failure")

        # Expected: 1 initial + max_retry retries = 1 + max_retry total calls
        expected_calls = 1 + max_retry

        with pytest.raises(Exception):
            execute_with_retry(
                func=always_fail,
                max_retry=max_retry,
                min_retry_wait=0,
                max_retry_wait=0,
                # All new params at defaults
            )

        assert call_count[0] == expected_calls, (
            f"Expected {expected_calls} calls with max_retry={max_retry}, "
            f"got {call_count[0]}"
        )

    @settings(max_examples=100)
    @given(max_retry=st.integers(min_value=2, max_value=5))
    def test_no_fallback_params_same_exception_type(self, max_retry: int):
        """With default new params and max_retry >= 2 (enters retry loop),
        the terminal exception should be the generic 'All retries failed'
        Exception (not TimeoutError, not last_exception directly).

        # Feature: retry-native-timeout, Property 1: Backward Compatibility Preservation (sync)

        **Validates: Requirements 6.2, 14.2**
        """
        def always_fail():
            raise RuntimeError("intentional failure")

        with pytest.raises(Exception, match="All retries failed"):
            execute_with_retry(
                func=always_fail,
                max_retry=max_retry,
                min_retry_wait=0,
                max_retry_wait=0,
            )

    @settings(max_examples=100)
    @given(max_retry=st.integers(min_value=2, max_value=5))
    def test_no_fallback_params_callback_invocations(self, max_retry: int):
        """With default new params and max_retry >= 2 (enters retry loop),
        on_retry_callback should fire max_retry times (once per retry,
        not on the initial attempt).

        # Feature: retry-native-timeout, Property 1: Backward Compatibility Preservation (sync)

        **Validates: Requirements 6.2, 14.2**
        """
        callback_log = []

        def always_fail():
            raise RuntimeError("intentional failure")

        def on_retry(attempt, exc):
            callback_log.append(attempt)

        with pytest.raises(Exception):
            execute_with_retry(
                func=always_fail,
                max_retry=max_retry,
                min_retry_wait=0,
                max_retry_wait=0,
                on_retry_callback=on_retry,
            )

        # on_retry_callback fires for each retry (not the initial attempt)
        # attempts go 0, 1, ..., max_retry-1
        assert callback_log == list(range(max_retry)), (
            f"Expected callback attempts {list(range(max_retry))}, got {callback_log}"
        )


# ---------------------------------------------------------------------------
# Property 6: Fallback Chain Exhaustion (sync)
# ---------------------------------------------------------------------------

class TestFallbackChainExhaustion:
    """Property 6: Fallback Chain Exhaustion (sync).

    For any fallback chain of length C (primary + C-1 fallbacks) where all
    callables always fail:
    - ON_EXHAUSTED: total = C * (1 + max_retry)
    - ON_FIRST_FAILURE: primary gets 1 attempt, subsequent get (1 + max_retry).
      Total = 1 + (C-1) * (1 + max_retry)

    Sync semantics: while True + attempts >= max_retry: break = initial + max_retry calls.

    # Feature: retry-native-timeout, Property 6: Fallback Chain Exhaustion (sync)

    **Validates: Requirements 10.4, 10.5, 10.6**
    """

    @settings(max_examples=100)
    @given(
        num_fallbacks=chain_length,
        max_retry=small_max_retry,
    )
    def test_on_exhausted_total_attempts(self, num_fallbacks: int, max_retry: int):
        """ON_EXHAUSTED: total attempts = C * (1 + max_retry) where C is chain length.

        # Feature: retry-native-timeout, Property 6: Fallback Chain Exhaustion (sync)

        **Validates: Requirements 10.4, 10.6**
        """
        counters = {}
        chain_size = 1 + num_fallbacks  # primary + fallbacks

        primary = make_counting_callable(counters, "primary")
        fallbacks = [
            make_counting_callable(counters, f"fb_{i}")
            for i in range(num_fallbacks)
        ]

        expected_total = chain_size * (1 + max_retry)

        with pytest.raises(Exception):
            execute_with_retry(
                func=primary,
                max_retry=max_retry,
                min_retry_wait=0,
                max_retry_wait=0,
                fallback_func=fallbacks,
                fallback_mode=FallbackMode.ON_EXHAUSTED,
            )

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
        """ON_FIRST_FAILURE: primary gets 1 attempt, subsequent get (1 + max_retry).
        Total = 1 + (C-1) * (1 + max_retry) where C is chain length.

        # Feature: retry-native-timeout, Property 6: Fallback Chain Exhaustion (sync)

        **Validates: Requirements 10.5, 10.6**
        """
        counters = {}
        chain_size = 1 + num_fallbacks

        primary = make_counting_callable(counters, "primary")
        fallbacks = [
            make_counting_callable(counters, f"fb_{i}")
            for i in range(num_fallbacks)
        ]

        expected_total = 1 + num_fallbacks * (1 + max_retry)

        with pytest.raises(Exception):
            execute_with_retry(
                func=primary,
                max_retry=max_retry,
                min_retry_wait=0,
                max_retry_wait=0,
                fallback_func=fallbacks,
                fallback_mode=FallbackMode.ON_FIRST_FAILURE,
            )

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
# Property 7: Fallback Ordering Guarantee (sync)
# ---------------------------------------------------------------------------

class TestFallbackOrderingGuarantee:
    """Property 7: Fallback Ordering Guarantee (sync).

    For any fallback chain [func, fb_0, fb_1, ..., fb_n], the Retry_Helper
    SHALL invoke callables strictly in order. It SHALL never skip a callable
    or reorder them.

    # Feature: retry-native-timeout, Property 7: Fallback Ordering Guarantee (sync)

    **Validates: Requirements 10.7**
    """

    @settings(max_examples=100)
    @given(
        num_fallbacks=chain_length,
        mode=fallback_mode_strategy,
    )
    def test_invocation_order_is_strict(self, num_fallbacks: int, mode: FallbackMode):
        """Callables are invoked in strict chain order: primary, fb_0, fb_1, ...

        # Feature: retry-native-timeout, Property 7: Fallback Ordering Guarantee (sync)

        **Validates: Requirements 10.7**
        """
        call_log = []

        primary = make_recording_callable(call_log, "primary")
        fallbacks = [
            make_recording_callable(call_log, f"fb_{i}")
            for i in range(num_fallbacks)
        ]

        with pytest.raises(Exception):
            execute_with_retry(
                func=primary,
                max_retry=1,
                min_retry_wait=0,
                max_retry_wait=0,
                fallback_func=fallbacks,
                fallback_mode=mode,
            )

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

        # Feature: retry-native-timeout, Property 7: Fallback Ordering Guarantee (sync)

        **Validates: Requirements 10.7**
        """
        counters = {}

        primary = make_counting_callable(counters, "primary")
        fallbacks = [
            make_counting_callable(counters, f"fb_{i}")
            for i in range(num_fallbacks)
        ]

        with pytest.raises(Exception):
            execute_with_retry(
                func=primary,
                max_retry=1,
                min_retry_wait=0,
                max_retry_wait=0,
                fallback_func=fallbacks,
                fallback_mode=mode,
            )

        for label in ["primary"] + [f"fb_{i}" for i in range(num_fallbacks)]:
            assert counters[label] >= 1, (
                f"Callable '{label}' was never invoked. Counters: {counters}"
            )


# ---------------------------------------------------------------------------
# Property 8: Timeout Supersedes Fallback (sync)
# ---------------------------------------------------------------------------

class TestTimeoutSupersedesFallback:
    """Property 8: Timeout Supersedes Fallback (sync).

    When both total_timeout and fallback_func are set, if the total timeout
    deadline expires during any callable in the chain, the Retry_Helper SHALL
    raise TimeoutError immediately without transitioning to the next fallback.
    Remaining callables SHALL never be invoked.

    # Feature: retry-native-timeout, Property 8: Timeout Supersedes Fallback (sync)

    **Validates: Requirements 13.1, 13.2**
    """

    @settings(max_examples=100, deadline=30000)
    @given(
        num_fallbacks=st.integers(min_value=2, max_value=4),
    )
    def test_timeout_prevents_remaining_fallbacks(self, num_fallbacks: int):
        """With a tight total_timeout and slow callables, TimeoutError should
        fire before all fallbacks are reached.

        # Feature: retry-native-timeout, Property 8: Timeout Supersedes Fallback (sync)

        **Validates: Requirements 13.1, 13.2**
        """
        call_log = []

        def slow_fail(label):
            def _func():
                call_log.append(label)
                time.sleep(0.05)
                raise RuntimeError(f"fail-{label}")
            return _func

        primary = slow_fail("primary")
        fallbacks = [slow_fail(f"fb_{i}") for i in range(num_fallbacks)]

        # total_timeout tight enough that not all callables can run
        # Each callable sleeps 0.05s, with max_retry=1 that's 2 * 0.05 = 0.1s per callable
        # Set timeout to allow only ~1 callable
        total_timeout = 0.08

        with pytest.raises(TimeoutError):
            execute_with_retry(
                func=primary,
                max_retry=1,
                min_retry_wait=0,
                max_retry_wait=0,
                fallback_func=fallbacks,
                fallback_mode=FallbackMode.ON_EXHAUSTED,
                total_timeout=total_timeout,
            )

        # Not all callables should have been invoked
        unique_labels = set(call_log)
        all_labels = {"primary"} | {f"fb_{i}" for i in range(num_fallbacks)}
        assert unique_labels < all_labels, (
            f"All callables were invoked despite tight timeout. "
            f"Invoked: {unique_labels}, All: {all_labels}"
        )


# ---------------------------------------------------------------------------
# Property 9: Fallback Exception Filtering (sync)
# ---------------------------------------------------------------------------

class TestFallbackExceptionFiltering:
    """Property 9: Fallback Exception Filtering (sync).

    For any fallback_on_exceptions tuple and any exception type raised:
    - Matching exceptions trigger transition to next fallback.
    - Non-matching exceptions propagate immediately.

    # Feature: retry-native-timeout, Property 9: Fallback Exception Filtering (sync)

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

        # Feature: retry-native-timeout, Property 9: Fallback Exception Filtering (sync)

        **Validates: Requirements 11.2, 11.3**
        """
        exc_types = [self.AlphaError, self.BetaError, self.GammaError]
        filter_type = exc_types[filter_idx]
        raise_type = exc_types[raise_idx]

        call_log = []

        def primary():
            call_log.append("primary")
            raise raise_type("primary failure")

        def fallback():
            call_log.append("fallback")
            return "fallback_result"

        if filter_idx == raise_idx:
            # Matching: fallback should be reached
            result = execute_with_retry(
                func=primary,
                max_retry=1,
                min_retry_wait=0,
                max_retry_wait=0,
                fallback_func=[fallback],
                fallback_mode=FallbackMode.ON_FIRST_FAILURE,
                fallback_on_exceptions=(filter_type,),
            )
            assert result == "fallback_result", (
                f"Expected fallback result when exception matches filter"
            )
            assert "fallback" in call_log, "Fallback should have been invoked"
        else:
            # Non-matching: exception should propagate immediately
            with pytest.raises(raise_type):
                execute_with_retry(
                    func=primary,
                    max_retry=1,
                    min_retry_wait=0,
                    max_retry_wait=0,
                    fallback_func=[fallback],
                    fallback_mode=FallbackMode.ON_FIRST_FAILURE,
                    fallback_on_exceptions=(filter_type,),
                )
            assert "fallback" not in call_log, (
                f"Fallback should NOT be invoked when exception doesn't match filter"
            )

    @settings(max_examples=100)
    @given(
        mode=fallback_mode_strategy,
    )
    def test_none_filter_allows_all_exceptions(self, mode: FallbackMode):
        """When fallback_on_exceptions is None, any exception triggers transition.

        # Feature: retry-native-timeout, Property 9: Fallback Exception Filtering (sync)

        **Validates: Requirements 11.2**
        """
        call_log = []

        def primary():
            call_log.append("primary")
            raise RuntimeError("any error")

        def fallback():
            call_log.append("fallback")
            return "ok"

        result = execute_with_retry(
            func=primary,
            max_retry=1,
            min_retry_wait=0,
            max_retry_wait=0,
            fallback_func=[fallback],
            fallback_mode=mode,
            fallback_on_exceptions=None,
        )
        assert result == "ok"
        assert "fallback" in call_log


# ---------------------------------------------------------------------------
# Property 17: on_fallback_callback Single-Fire
# ---------------------------------------------------------------------------

class TestOnFallbackCallbackSingleFire:
    """Property 17: on_fallback_callback Single-Fire Per Transition.

    For any chain transition, on_fallback_callback SHALL fire exactly once,
    before the next callable's first attempt. It SHALL NOT fire on
    intra-callable retries.

    # Feature: retry-native-timeout, Property 17: on_fallback_callback Single-Fire

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

        # Feature: retry-native-timeout, Property 17: on_fallback_callback Single-Fire

        **Validates: Requirements 11.2, 11.3**
        """
        callback_log = []
        counters = {}

        primary = make_counting_callable(counters, "primary")
        fallbacks = [
            make_counting_callable(counters, f"fb_{i}")
            for i in range(num_fallbacks)
        ]

        def on_fallback(from_func, to_func, exception, total_attempts):
            callback_log.append({
                "from": from_func,
                "to": to_func,
                "exception": exception,
                "total_attempts": total_attempts,
            })

        with pytest.raises(Exception):
            execute_with_retry(
                func=primary,
                max_retry=max_retry,
                min_retry_wait=0,
                max_retry_wait=0,
                fallback_func=fallbacks,
                fallback_mode=mode,
                on_fallback_callback=on_fallback,
            )

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

        # Feature: retry-native-timeout, Property 17: on_fallback_callback Single-Fire

        **Validates: Requirements 11.2, 11.3**
        """
        callback_log = []

        def primary():
            raise RuntimeError("primary fail")

        def fallback():
            raise RuntimeError("fallback fail")

        def on_fallback(from_func, to_func, exception, total_attempts):
            callback_log.append({
                "from": from_func,
                "to": to_func,
                "exception": exception,
                "total_attempts": total_attempts,
            })

        with pytest.raises(Exception):
            execute_with_retry(
                func=primary,
                max_retry=max_retry,
                min_retry_wait=0,
                max_retry_wait=0,
                fallback_func=[fallback],
                fallback_mode=FallbackMode.ON_EXHAUSTED,
                on_fallback_callback=on_fallback,
            )

        assert len(callback_log) == 1
        entry = callback_log[0]
        assert entry["from"] is primary
        assert entry["to"] is fallback
        assert isinstance(entry["exception"], RuntimeError)
        # ON_EXHAUSTED: primary gets 1 + max_retry attempts
        assert entry["total_attempts"] == 1 + max_retry, (
            f"Expected total_attempts={1 + max_retry}, got {entry['total_attempts']}"
        )


# ---------------------------------------------------------------------------
# Property 18: on_retry_callback Attempt Reset
# ---------------------------------------------------------------------------

class TestOnRetryCallbackAttemptReset:
    """Property 18: on_retry_callback Attempt Reset.

    For any chain transition, the attempt argument passed to on_retry_callback
    SHALL reset to 0 for the new callable. Existing callbacks see per-function
    attempt counts (backward-compatible).

    # Feature: retry-native-timeout, Property 18: on_retry_callback Attempt Reset

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

        # Feature: retry-native-timeout, Property 18: on_retry_callback Attempt Reset

        **Validates: on_retry_callback backward compatibility**
        """
        callback_log = []
        call_log = []

        def make_func(label):
            def _func():
                call_log.append(label)
                raise RuntimeError(f"fail-{label}")
            return _func

        primary = make_func("primary")
        fallbacks = [make_func(f"fb_{i}") for i in range(num_fallbacks)]

        def on_retry(attempt, exc):
            # Record which callable is active based on the last call_log entry
            current_label = call_log[-1] if call_log else "unknown"
            callback_log.append((current_label, attempt))

        with pytest.raises(Exception):
            execute_with_retry(
                func=primary,
                max_retry=max_retry,
                min_retry_wait=0,
                max_retry_wait=0,
                fallback_func=fallbacks,
                fallback_mode=FallbackMode.ON_EXHAUSTED,
                on_retry_callback=on_retry,
            )

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
# Property 19: Input Validation
# ---------------------------------------------------------------------------

class TestInputValidation:
    """Property 19: Input Validation for Contradictory Configs.

    - fallback_func + NEVER mode → ValueError
    - non-NEVER mode + no fallback_func → ValueError
    - async fallback callable in sync helper → ValueError

    # Feature: retry-native-timeout, Property 19: Input Validation

    **Validates: Input validation requirements**
    """

    @settings(max_examples=100)
    @given(
        num_fallbacks=st.integers(min_value=1, max_value=4),
    )
    def test_fallback_func_with_never_mode_raises(self, num_fallbacks: int):
        """Providing fallback_func with fallback_mode=NEVER raises ValueError.

        # Feature: retry-native-timeout, Property 19: Input Validation

        **Validates: Input validation requirements**
        """
        fallbacks = [lambda: None for _ in range(num_fallbacks)]

        with pytest.raises(ValueError, match="fallback_func provided but fallback_mode is NEVER"):
            execute_with_retry(
                func=lambda: None,
                fallback_func=fallbacks,
                fallback_mode=FallbackMode.NEVER,
            )

    @settings(max_examples=100)
    @given(
        mode=fallback_mode_strategy,
    )
    def test_non_never_mode_without_fallback_raises(self, mode: FallbackMode):
        """Non-NEVER mode without fallback_func raises ValueError.

        # Feature: retry-native-timeout, Property 19: Input Validation

        **Validates: Input validation requirements**
        """
        with pytest.raises(ValueError, match="fallback_mode is not NEVER but no fallback_func"):
            execute_with_retry(
                func=lambda: None,
                fallback_mode=mode,
                fallback_func=None,
            )

    @settings(max_examples=100)
    @given(
        mode=fallback_mode_strategy,
    )
    def test_async_fallback_callable_raises(self, mode: FallbackMode):
        """Async fallback callable in sync helper raises ValueError.

        # Feature: retry-native-timeout, Property 19: Input Validation

        **Validates: Input validation requirements**
        """
        async def async_fallback():
            pass

        with pytest.raises(ValueError, match="Async fallback callable"):
            execute_with_retry(
                func=lambda: None,
                fallback_func=[async_fallback],
                fallback_mode=mode,
            )

    @settings(max_examples=100)
    @given(
        mode=fallback_mode_strategy,
    )
    def test_empty_list_fallback_with_non_never_raises(self, mode: FallbackMode):
        """Empty list fallback_func with non-NEVER mode raises ValueError
        (empty list is normalized to None, then validation catches it).

        # Feature: retry-native-timeout, Property 19: Input Validation

        **Validates: Input validation requirements**
        """
        with pytest.raises(ValueError, match="fallback_mode is not NEVER but no fallback_func"):
            execute_with_retry(
                func=lambda: None,
                fallback_func=[],
                fallback_mode=mode,
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
