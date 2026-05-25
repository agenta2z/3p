from enum import IntEnum


class ResultPassDownMode(IntEnum):
    """Enum to define modes of passing results between workflow steps or nodes.

    Attributes:
        NoPassDown: Do not pass the result to the downstream step.
        ResultAsFirstArg: Pass the result as the first positional argument.
        ResultAsLeadingArgs: If result is a tuple, splat in front of args; otherwise insert first.
    """

    NoPassDown = 0
    ResultAsFirstArg = 1
    ResultAsLeadingArgs = 2
