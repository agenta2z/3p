"""Exceptions for the Workflow framework."""


class WorkflowAborted(Exception):
    """Raised by hooks or error handlers to abort the workflow gracefully.

    Attributes:
        step_name: Name of the step where abort was triggered.
        step_index: Index of the step where abort was triggered.
        partial_result: The result accumulated so far.
    """

    def __init__(
        self,
        message="Workflow aborted",
        step_name=None,
        step_index=None,
        partial_result=None,
    ):
        self.step_name = step_name
        self.step_index = step_index
        self.partial_result = partial_result
        super().__init__(message)
