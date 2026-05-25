"""WorkNodeBase — base class for workflow nodes.

Ported from RichPythonUtils with adaptations:
- CRITICAL: Removed ``logger`` attrib declaration and hprint_message default.
  Relies entirely on Debuggable's logger to avoid attrs diamond conflict.
- Inlined ``is_class_or_type_`` and ``TypeOrGenericAlias`` (were not found in
  the original source, so we provide minimal implementations).
"""

import logging
import types
from abc import ABC
from enum import IntEnum
from typing import Any, Callable, Mapping, Optional, Sequence, Set, Tuple, Union

from attr import attrib, attrs
from rich_python_utils.common_objects.debuggable import Debuggable
from rankevolve.src.utils.common_objects.serializable import (
    Serializable,
    SerializationMode,
)
from rankevolve.src.utils.common_objects.workflow.common.post_processable import (
    PostProcessable,
)
from rankevolve.src.utils.common_objects.workflow.common.result_pass_down_mode import (
    ResultPassDownMode,
)
from rankevolve.src.utils.common_objects.workflow.common.resumable import Resumable

# ---------------------------------------------------------------------------
# Inlined typing helpers (originally from rich_python_utils.common_utils)
# ---------------------------------------------------------------------------
TypeOrGenericAlias = Union[type, "types.GenericAlias"]


def is_class_or_type_(obj) -> bool:
    """Return True if *obj* is a class (type) or a generic alias like list[int]."""
    if isinstance(obj, type):
        return True
    # Python 3.9+ generic aliases (list[int], dict[str, Any], etc.)
    if isinstance(obj, (getattr(types, "GenericAlias", type(None)),)):
        return True
    # typing module generics
    origin = getattr(obj, "__origin__", None)
    return origin is not None


class WorkGraphStopFlags(IntEnum):
    Continue = 0
    Terminate = 1
    AbstainResult = 2

    @staticmethod
    def is_input_single_stop_flag(*args, **kwargs) -> bool:
        return (
            (not kwargs)
            and (len(args) == 1)
            and isinstance(args[0], WorkGraphStopFlags)
        )

    @staticmethod
    def result_has_stop_flag(result) -> bool:
        return (
            isinstance(result, tuple)
            and len(result) >= 2
            and isinstance(result[0], WorkGraphStopFlags)
        )

    @staticmethod
    def remove_stop_flag_from_result(result):
        if WorkGraphStopFlags.result_has_stop_flag(result):
            if len(result) == 1:
                return None
            elif len(result) == 2:
                return result[0]
            else:
                return result[1:]
        return result

    @staticmethod
    def separate_stop_flag_from_result(
        result,
    ) -> Union[Tuple["WorkGraphStopFlags", None], Tuple["WorkGraphStopFlags", ...]]:
        if WorkGraphStopFlags.result_has_stop_flag(result):
            stop_flag = result[0]
            if len(result) == 1:
                return stop_flag, None
            elif len(result) == 2:
                return result
            else:
                return stop_flag, result[1:]
        else:
            return WorkGraphStopFlags.Continue, result


@attrs(slots=True)
class NextNodesSelector:
    """Special return value that tells WorkGraph which downstream nodes to run."""

    include_self: bool = attrib(default=False)
    include_others: Union[bool, Set[str]] = attrib(default=True)
    result: Any = attrib(default=None)


def get_args_for_downstream(
    result,
    mode: Union[str, ResultPassDownMode, Callable],
    args: Sequence,
    kwargs: Mapping,
):
    """Prepare arguments for downstream steps based on the result pass-down mode."""
    if callable(mode):
        result_tuple = mode(result, *args, **kwargs)
        if result_tuple is None:
            return args, kwargs
        return result_tuple

    if isinstance(mode, str):
        mode = str(mode)
        if mode in kwargs:
            kwargs = dict(kwargs)
            kwargs[mode] = result
        else:
            kwargs = {str(mode): result, **kwargs}
        return args, kwargs

    elif mode == ResultPassDownMode.NoPassDown:
        return args, kwargs
    elif mode == ResultPassDownMode.ResultAsFirstArg:
        return (result, *args[1:]), kwargs
    elif mode == ResultPassDownMode.ResultAsLeadingArgs:
        if isinstance(result, tuple):
            return (*result, *args), kwargs
        else:
            return (result, *args), kwargs
    else:
        valid_modes = [m for m in ResultPassDownMode]
        raise ValueError(
            f"Invalid mode: {mode}. Expected one of {valid_modes}, a string key, or a callable."
        )


@attrs(slots=False)
class WorkNodeBase(Serializable, Debuggable, Resumable, PostProcessable, ABC):
    """Base class for nodes in a workflow.

    CRITICAL: Does NOT declare its own ``logger`` attrib. Debuggable's
    ``logger`` attribute is inherited and used directly.  The original
    RichPythonUtils version declared a duplicate ``logger`` here which
    caused attrs diamond conflicts in subclasses that also inherit
    Debuggable (like DualInferencer via InferencerBase).
    """

    auto_mode: SerializationMode = SerializationMode.PREFER_CLEAR_TEXT

    name = attrib(type=str, default=None)
    result_pass_down_mode = attrib(
        type=Union[str, ResultPassDownMode, Callable, Any],
        default=ResultPassDownMode.NoPassDown,
    )
    unpack_single_result = attrib(type=Union[bool, TypeOrGenericAlias], default=True)
    ignore_stop_flag_from_saved_results = attrib(type=bool, default=True)

    def __attrs_post_init__(self):
        """Ensure parent classes' __attrs_post_init__ methods are called."""
        super().__attrs_post_init__()

    def _get_args_for_downstream(self, result, args: Sequence, kwargs: Mapping):
        return get_args_for_downstream(result, self.result_pass_down_mode, args, kwargs)

    def __call__(self, *args, **kwargs):
        return self.run(*args, **kwargs)

    def _run(self, *args, **kwargs):
        raise NotImplementedError

    def load_result(self, *args, **kwargs) -> Tuple[bool, Any]:
        if self.resume_with_saved_results:
            result_path = self._resolve_result_path(self.name, *args, **kwargs)
            if self._exists_result(self.name, result_path):
                result = self._load_result(self.name, result_path)
                if self.ignore_stop_flag_from_saved_results:
                    result = WorkGraphStopFlags.remove_stop_flag_from_result(result)
                return True, result
        return False, None

    def run(self, *args, _output: list = None, **kwargs):
        result = self._run(*args, **kwargs)
        stop_flag, result = WorkGraphStopFlags.separate_stop_flag_from_result(result)

        if (
            (self.unpack_single_result is True and isinstance(result, (list, tuple)))
            or (
                is_class_or_type_(self.unpack_single_result)
                and isinstance(result, self.unpack_single_result)
            )
        ) and len(result) == 1:
            result = result[0]

        if _output is not None:
            _output.append(result)
            return stop_flag
        else:
            if stop_flag == WorkGraphStopFlags.Continue:
                return result
            else:
                return stop_flag, result

    async def _arun(self, *args, **kwargs):
        """Async implementation — override in subclasses."""
        raise NotImplementedError

    async def arun(
        self, *args, _output: list = None, _output_idx: tuple = None, **kwargs
    ):
        """Async entry point. Mirrors run() but calls await self._arun()."""
        result = await self._arun(*args, **kwargs)
        stop_flag, result = WorkGraphStopFlags.separate_stop_flag_from_result(result)

        if (
            (self.unpack_single_result is True and isinstance(result, (list, tuple)))
            or (
                is_class_or_type_(self.unpack_single_result)
                and isinstance(result, self.unpack_single_result)
            )
        ) and len(result) == 1:
            result = result[0]

        if _output_idx is not None:
            output_list, idx = _output_idx
            output_list[idx] = result
            return stop_flag
        elif _output is not None:
            _output.append(result)
            return stop_flag
        else:
            if stop_flag == WorkGraphStopFlags.Continue:
                return result
            else:
                return stop_flag, result
