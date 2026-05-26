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


class ExpansionError(Exception):
    """Base exception for all expansion-related errors."""
    pass


class ExpansionConfigError(ExpansionError):
    """Invalid expansion configuration detected at expansion time.

    Raised for:
    - loop_back_to + ExpansionResult (Req 27)
    - Non-importable reconstruct_from_seed (lambda/closure) (Req 25.4)
    - worker_manages_resume + GraphExpansionResult (Req 30)
    """
    pass


class ExpansionReplayError(ExpansionError):
    """Seed-based reconstruction failed on resume.

    Raised for:
    - Factory cannot be imported by qualified name (Req 25.5)
    - Seed cannot be deserialized (Req 25.5)
    """
    pass


class ExpansionLimitExceeded(ExpansionError):
    """Termination bound violated.

    Raised for:
    - max_expansion_events exceeded (Req 6.2) / max_expansion_depth exceeded (Req 16.2)
    - max_total_steps exceeded (Req 6.4)
    - max_total_nodes exceeded (Req 16.4)
    """
    pass
