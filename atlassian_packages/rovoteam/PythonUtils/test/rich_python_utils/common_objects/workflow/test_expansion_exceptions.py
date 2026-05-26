"""Tests for expansion exception hierarchy (Task 12.2).

Validates: Requirements 36.1, 36.2, 36.3, 36.4
"""
import pytest

from python_utils.common_objects.workflow.common.exceptions import (
    ExpansionError,
    ExpansionConfigError,
    ExpansionReplayError,
    ExpansionLimitExceeded,
)


class TestExpansionExceptionHierarchy:
    """All three concrete exceptions inherit from ExpansionError."""

    def test_expansion_config_error_inherits_from_expansion_error(self):
        assert issubclass(ExpansionConfigError, ExpansionError)

    def test_expansion_replay_error_inherits_from_expansion_error(self):
        assert issubclass(ExpansionReplayError, ExpansionError)

    def test_expansion_limit_exceeded_inherits_from_expansion_error(self):
        assert issubclass(ExpansionLimitExceeded, ExpansionError)

    def test_all_inherit_from_exception(self):
        for cls in (ExpansionError, ExpansionConfigError, ExpansionReplayError, ExpansionLimitExceeded):
            assert issubclass(cls, Exception)


class TestExpansionErrorCatchAll:
    """``except ExpansionError`` catches all three subtypes."""

    def test_except_catches_config_error(self):
        with pytest.raises(ExpansionError):
            raise ExpansionConfigError("bad config")

    def test_except_catches_replay_error(self):
        with pytest.raises(ExpansionError):
            raise ExpansionReplayError("replay failed")

    def test_except_catches_limit_exceeded(self):
        with pytest.raises(ExpansionError):
            raise ExpansionLimitExceeded("limit hit")

    def test_message_preserved(self):
        msg = "something went wrong"
        for cls in (ExpansionConfigError, ExpansionReplayError, ExpansionLimitExceeded):
            exc = cls(msg)
            assert str(exc) == msg
