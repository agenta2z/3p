"""
Test repeat and retry functionality in WorkGraphNode.

This test suite verifies the repeat/retry attributes in WorkGraphNode:
max_repeat, repeat_condition, output_validator, fallback_result, etc.
"""
import pytest

from python_utils.common_objects.workflow.workgraph import WorkGraphNode


class TestWorkGraphNodeRepeatRetryAttributes:
    """Test repeat/retry attribute defaults and custom values."""

    def test_default_values(self):
        """Test that default repeat/retry values are set correctly."""
        node = WorkGraphNode(lambda x: x)

        assert node.max_repeat == 1
        assert node.repeat_condition is None
        assert node.fallback_result is None
        assert node.min_repeat_wait == 0
        assert node.max_repeat_wait == 0
        assert node.retry_on_exceptions is None
        assert node.output_validator is None

    def test_custom_values(self):
        """Test that custom repeat/retry values can be set."""
        def my_condition():
            return True

        def my_validator(r):
            return r > 0

        node = WorkGraphNode(
            lambda x: x,
            max_repeat=5,
            repeat_condition=my_condition,
            fallback_result="fallback",
            min_repeat_wait=0.1,
            max_repeat_wait=0.5,
            retry_on_exceptions=[ValueError],
            output_validator=my_validator
        )

        assert node.max_repeat == 5
        assert node.repeat_condition is my_condition
        assert node.fallback_result == "fallback"
        assert node.min_repeat_wait == 0.1
        assert node.max_repeat_wait == 0.5
        assert node.retry_on_exceptions == [ValueError]
        assert node.output_validator is my_validator


class TestWorkGraphNodeRepeatRetryExecution:
    """Test repeat/retry execution behavior."""

    def test_simple_execution_no_repeat(self):
        """Test simple execution without repeat configuration."""
        node = WorkGraphNode(lambda x: x + 1)
        result = node.run(5)
        assert result == 6

    def test_retry_on_validation_failure(self):
        """Test that validation failure triggers retry."""
        counter = [0]

        def increment_func(x):
            counter[0] += 1
            return x + counter[0]

        def valid_when_ge_10(r):
            return r >= 10

        node = WorkGraphNode(
            increment_func,
            max_repeat=10,
            output_validator=valid_when_ge_10
        )

        result = node.run(5)
        # 5+1=6, 5+2=7, 5+3=8, 5+4=9, 5+5=10 (valid)
        assert result == 10
        assert counter[0] == 5

    def test_repeat_condition_as_guard(self):
        """Test repeat_condition as a guard that can skip execution."""
        executed = [False]

        def my_func(x):
            executed[0] = True
            return x

        node = WorkGraphNode(
            my_func,
            repeat_condition=lambda *args, **kwargs: False,  # Never execute (must accept func args)
            fallback_result="skipped"
        )

        result = node.run(5)
        assert result == "skipped"
        assert executed[0] is False

    def test_max_repeat_limits_retries(self):
        """Test that max_repeat limits the number of retry attempts.

        Note: max_repeat=3 means 3 retries after initial attempt = 4 total executions.
        This matches the semantics of execute_with_retry's max_retry parameter.
        """
        counter = [0]

        def always_fail_validation(x):
            counter[0] += 1
            return x

        def never_valid(r):
            return False

        node = WorkGraphNode(
            always_fail_validation,
            max_repeat=3,
            output_validator=never_valid,
            fallback_result="max_reached"
        )

        result = node.run(5)
        assert result == "max_reached"
        # max_repeat=3 means 3 retries + 1 initial = 4 total executions
        assert counter[0] == 4


class TestWorkGraphNodeRetryOnException:
    """Test retry on exception functionality."""

    def test_retry_on_specific_exception(self):
        """Test that specific exceptions trigger retry."""
        counter = [0]

        def fail_twice_then_succeed(x):
            counter[0] += 1
            if counter[0] < 3:
                raise ValueError("Temporary error")
            return x + 10

        node = WorkGraphNode(
            fail_twice_then_succeed,
            max_repeat=5,
            retry_on_exceptions=[ValueError]
        )

        result = node.run(5)
        assert result == 15
        assert counter[0] == 3

    def test_non_matching_exception_not_retried(self):
        """Test that non-matching exceptions are not retried."""
        def raise_type_error(x):
            raise TypeError("Not retryable")

        node = WorkGraphNode(
            raise_type_error,
            max_repeat=5,
            retry_on_exceptions=[ValueError]  # Only retry ValueError
        )

        with pytest.raises(TypeError):
            node.run(5)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
