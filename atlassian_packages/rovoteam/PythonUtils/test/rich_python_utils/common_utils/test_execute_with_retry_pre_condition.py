"""
Test pre_condition parameter in execute_with_retry.

This test suite verifies the pre_condition guard functionality added to execute_with_retry.
"""
import pytest

from python_utils.common_utils.function_helper import execute_with_retry


class TestExecuteWithRetryPreCondition:
    """Test pre_condition parameter in execute_with_retry."""

    def test_pre_condition_false_returns_default(self):
        """Test that pre_condition=False returns default_return_or_raise."""
        result = execute_with_retry(
            func=lambda: 42,
            max_retry=3,
            pre_condition=lambda: False,
            default_return_or_raise="skipped"
        )
        assert result == "skipped"

    def test_pre_condition_true_executes_function(self):
        """Test that pre_condition=True executes the function."""
        result = execute_with_retry(
            func=lambda: 42,
            max_retry=3,
            pre_condition=lambda: True,
        )
        assert result == 42

    def test_pre_condition_none_executes_normally(self):
        """Test that pre_condition=None (default) executes normally."""
        result = execute_with_retry(
            func=lambda: 42,
            max_retry=3,
        )
        assert result == 42

    def test_pre_condition_with_validator_retry_until_success(self):
        """Test pre_condition as guard combined with validator for retry-until-success."""
        counter = [0]

        def increment():
            counter[0] += 1
            return counter[0]

        def allow_execution():
            return counter[0] < 5  # Guard: allow up to 5 attempts

        def valid_result(r):
            return r >= 3  # Post-check: valid when result >= 3

        result = execute_with_retry(
            func=increment,
            max_retry=10,
            pre_condition=allow_execution,
            output_validator=valid_result
        )
        assert result == 3
        assert counter[0] == 3

    def test_pre_condition_stops_before_validation_success(self):
        """Test that pre_condition can stop execution before validator succeeds."""
        counter = [0]

        def increment():
            counter[0] += 1
            return counter[0]

        def allow_execution():
            return counter[0] < 2  # Only allow 2 attempts

        def valid_result(r):
            return r >= 5  # Needs 5 to succeed (won't be reached)

        result = execute_with_retry(
            func=increment,
            max_retry=10,
            pre_condition=allow_execution,
            output_validator=valid_result,
            default_return_or_raise="stopped_early"
        )
        # pre_condition stops after 2 attempts (counter=2)
        assert result == "stopped_early"
        assert counter[0] == 2

    def test_pre_condition_single_execution_false(self):
        """Test pre_condition with max_retry=1 when condition is False."""
        result = execute_with_retry(
            func=lambda: 42,
            max_retry=1,
            pre_condition=lambda: False,
            default_return_or_raise="skipped"
        )
        assert result == "skipped"

    def test_pre_condition_single_execution_true(self):
        """Test pre_condition with max_retry=1 when condition is True."""
        result = execute_with_retry(
            func=lambda: 42,
            max_retry=1,
            pre_condition=lambda: True,
        )
        assert result == 42

    def test_pre_condition_receives_args_kwargs(self):
        """Test that pre_condition receives the same args/kwargs as function."""
        received_args = []

        def capture_args(*args, **kwargs):
            received_args.append((args, kwargs))
            return True

        execute_with_retry(
            func=lambda x, y, **kw: x + y,  # Accept **kwargs
            max_retry=1,
            pre_condition=capture_args,
            args=[1, 2],
            kwargs={'extra': 'value'}
        )

        assert len(received_args) == 1
        assert received_args[0] == ((1, 2), {'extra': 'value'})


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
