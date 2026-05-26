from enum import Enum


class StepResultSaveOptions(str, Enum):
    """
    Enumeration to specify when to save step results.

    Attributes:
        NoSave (str): Do not save the result of the step.
        Always (str): Always save the result after the step completes successfully.
        OnError (str): Save the result only if the step raises an error.
        SkipResumable (str): Save only if the worker does NOT manage its own
            resume (i.e., ``worker_manages_resume`` is False on the node).
            Resumable workers (e.g., PTI, nested BTA) handle their own
            persistence internally.
    """
    NoSave = 'no_save'
    Always = 'always'
    OnError = 'on_error'
    SkipResumable = 'skip_resumable'


class ResumeMode(str, Enum):
    """Controls whether a node loads saved results on resume.

    Attributes:
        Never (str): Never load saved results — always execute.
        Always (str): Load saved result and skip execution if it exists.
        SkipResumable (str): Load and skip only if the worker does NOT manage
            its own resume (``worker_manages_resume`` is False). Resumable
            workers are re-invoked so they can resume from their own internal
            checkpoints.
    """
    Never = 'never'
    Always = 'always'
    SkipResumable = 'skip_resumable'
