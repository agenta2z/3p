from enum import IntEnum


class ResultPassDownMode(IntEnum):
    """
    Enum to define modes of passing results between workflow steps or nodes.

    Attributes:
        NoPassDown (int): Do not pass the result to the downstream step.
        ResultAsFirstArg (int): Pass the result of the previous step as the first positional argument (replacing the existing first positional argument).
        ResultAsLeadingArgs (int): If result is a tuple, splat it in front of existing positional args; otherwise insert as first positional arg.
    """
    NoPassDown = 0
    ResultAsFirstArg = 1
    ResultAsLeadingArgs = 2
