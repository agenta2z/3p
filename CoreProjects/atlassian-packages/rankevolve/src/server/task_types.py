# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict

"""Task execution mode types for the chat CLI /task command."""

from __future__ import annotations

from enum import Enum


class TaskMode(Enum):
    """Execution mode for the /task dual-inferencer workflow."""

    PLAN_ONLY = "plan"
    FULL_WORKFLOW = "full"
    EXECUTE_ONLY = "execute"
    PLAN_THEN_CONFIRM = "confirm"
