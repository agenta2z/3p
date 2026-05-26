import logging
from abc import ABC
from enum import IntEnum
from typing import Union, Any, Optional, Callable, Sequence, Mapping, Tuple, Set

from attr import attrs, attrib

from python_utils.common_utils import is_class_or_type_, TypeOrGenericAlias
from python_utils.common_objects.debuggable import Debuggable
from python_utils.common_objects.serializable import Serializable, SerializationMode
from python_utils.common_objects.workflow.common.post_processable import PostProcessable
from python_utils.common_objects.workflow.common.result_pass_down_mode import ResultPassDownMode

from python_utils.common_objects.workflow.common.resumable import Resumable
from python_utils.console_utils import hprint_message


class WorkGraphStopFlags(IntEnum):
    Continue = 0
    Terminate = 1
    AbstainResult = 2

    @staticmethod
    def is_input_single_stop_flag(*args, **kwargs) -> bool:
        return (not kwargs) and (len(args) == 1) and isinstance(args[0], WorkGraphStopFlags)

    @staticmethod
    def result_has_stop_flag(result) -> bool:
        return isinstance(result, tuple) and len(result) >= 2 and isinstance(result[0], WorkGraphStopFlags)

    @staticmethod
    def remove_stop_flag_from_result(result):
        # assuming the result is (stop_flag, ...)
        if WorkGraphStopFlags.result_has_stop_flag(result):
            if len(result) == 1:
                return None
            elif len(result) == 2:
                return result[0]
            else:
                return result[1:]
        return result

    @staticmethod
    def separate_stop_flag_from_result(result) -> Union[
        Tuple['WorkGraphStopFlags', None],
        Tuple['WorkGraphStopFlags', ...]
    ]:
        if WorkGraphStopFlags.result_has_stop_flag(result):
            # assuming the result is (stop_flag, ...)
            stop_flag = result[0]
            if len(result) == 1:
                return stop_flag, None
            elif len(result) == 2:
                return result
            else:
                return stop_flag, result[1:]
        else:
            # otherwise, we return the `Continue` flag by default
            return WorkGraphStopFlags.Continue, result


@attrs(slots=True)
class NextNodesSelector:
    """
    Special return value that tells WorkGraph which downstream nodes to run.

    This enables continuous monitoring patterns where a monitor node can:
    1. Re-run itself (self-loop) by setting include_self=True
    2. Selectively run downstream nodes
    3. Pass a result to downstream nodes

    For self-loops to work correctly, the monitor node must have an explicit
    self-edge in the graph structure via `monitor.add_next(monitor)`.

    Attributes:
        include_self: If True, the node will re-execute after downstream completes (self-loop).
                      The self-edge must exist in node.next for this to take effect.
        include_others: Controls which non-self downstream nodes execute:
            - True: Run all downstream nodes (default)
            - False: Run no downstream nodes (except self if include_self=True)
            - Set[str]: Run only nodes with these names
        result: The actual result to pass to downstream nodes.

    Example:
        >>> # Monitor that re-checks after all downstream actions complete
        >>> def monitor_condition():
        ...     if condition_still_holds():
        ...         return NextNodesSelector(include_self=True, include_others=True, result=status)
        ...     else:
        ...         return final_result  # Normal return stops the loop

        >>> # Only run specific downstream nodes
        >>> NextNodesSelector(include_self=True, include_others={'action1', 'action3'}, result=status)

        >>> # Run self only, skip all other downstream nodes
        >>> NextNodesSelector(include_self=True, include_others=False, result=status)
    """
    include_self: bool = attrib(default=False)
    include_others: Union[bool, Set[str]] = attrib(default=True)
    result: Any = attrib(default=None)


def get_args_for_downstream(result, mode: Union[str, ResultPassDownMode, Callable], args: Sequence, kwargs: Mapping):
    """
    Prepare arguments for downstream steps based on the result pass-down mode.

    Args:
        result: The output from the current step.
        mode (Union[str, ResultPassDownMode, Callable]):
            - If a ResultPassDownMode enum: controls positional pass-down behavior.
            - If a string: injects the result into kwargs under this key (overwriting existing key),
              and returns original args unchanged.
            - If a callable: custom merge function with signature (result, args, kwargs) -> Optional[(args, kwargs)].
              Provides full control over how results are passed to downstream nodes.
              - If returns (args, kwargs) tuple: use the returned values.
              - If returns None: use original args/kwargs (allows in-place modification).
        args (Sequence): Original positional arguments.
        kwargs (Mapping): Original keyword arguments.

    Returns:
        Tuple[Sequence, Mapping]: Updated positional and keyword arguments.

    Examples:
        >>> # Callable mode: custom merger that accumulates results
        >>> def accumulate_results(result, args, kwargs):
        ...     current = kwargs.get('all_results', [])
        ...     return args, {**kwargs, 'all_results': current + [result]}
        >>> get_args_for_downstream({'data': 1}, accumulate_results, (), {})
        ((), {'all_results': [{'data': 1}]})

        >>> # Callable mode: extract specific field from result
        >>> def extract_action_results(result, args, kwargs):
        ...     if isinstance(result, dict) and 'action_results' in result:
        ...         return args, {**kwargs, 'previous_action_results': result['action_results']}
        ...     return args, kwargs
        >>> get_args_for_downstream({'action_results': 'data'}, extract_action_results, (), {})
        ((), {'previous_action_results': 'data'})

        >>> # Callable mode: in-place modification (returns None)
        >>> def append_to_list(result, args, kwargs):
        ...     if 'results' in kwargs:
        ...         kwargs['results'].append(result)
        >>> results_list = []
        >>> get_args_for_downstream('item1', append_to_list, (), {'results': results_list})
        ((), {'results': ['item1']})
    """

    # Handle callable mode first - provides maximum flexibility
    if callable(mode):
        result_tuple = mode(result, *args, **kwargs)
        # If callable returns None, use original args/kwargs (may have been mutated)
        if result_tuple is None:
            return args, kwargs
        # Otherwise use the returned tuple
        return result_tuple

    # Handle string mode - inject result as named kwarg
    if isinstance(mode, str):
        mode = str(mode)
        if mode in kwargs:
            kwargs = dict(kwargs)
            kwargs[mode] = result
        else:
            kwargs = {str(mode): result, **kwargs}
        return args, kwargs

    # Handle enum modes - positional argument manipulation
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
        raise ValueError(f"Invalid mode: {mode}. Expected one of {valid_modes}, a string key, or a callable.")


@attrs(slots=False)
class WorkNodeBase(Serializable, Debuggable, Resumable, PostProcessable, ABC):
    """
    Base class for nodes in a workflow, providing common attribute definitions and functionality.

    Attributes:
        name (str): The name of this work node. Can be used for identification of this node.
        result_pass_down_mode (Union[str, python_utils.common_objects.workflow.common.result_pass_down_mode.ResultPassDownMode, Callable, Any]):
            The mode for passing results to downstream nodes. Defaults to `NoPassDown`.
            - If a ResultPassDownMode enum: controls positional pass-down behavior.
            - If a string: injects the result into kwargs under this key (overwriting existing key).
            - If a callable: custom merge function (result, args, kwargs) -> Optional[(args, kwargs)].
              Returns (args, kwargs) tuple to replace, or None to keep original (allows in-place modification).
        ignore_stop_flag_from_saved_results (bool): If True, ignores the stop flag from previously saved results
            when resuming execution. Defaults to `True`.
        logger (Optional[Union[Callable[[dict], Any], logging.Logger]]):
            Logger for debugging or workflow messages. Defaults to `hprint_message`.
    """
    # Set default serialization mode to prefer clear text (JSON/YAML)
    auto_mode: SerializationMode = SerializationMode.PREFER_CLEAR_TEXT
    
    name = attrib(type=str, default=None)
    result_pass_down_mode = attrib(type=Union[str, ResultPassDownMode, Callable, Any], default=ResultPassDownMode.NoPassDown)
    unpack_single_result = attrib(type=Union[bool, TypeOrGenericAlias], default=True)
    ignore_stop_flag_from_saved_results = attrib(type=bool, default=True)

    def __attrs_post_init__(self):
        """Ensure parent classes' __attrs_post_init__ methods are called."""
        super().__attrs_post_init__()

    def _get_args_for_downstream(self, result, args: Sequence, kwargs: Mapping):
        """
        Wrapper to prepare arguments for downstream nodes.

        Args:
            result: Output from the current node.
            args (Sequence): Positional arguments.
            kwargs (Mapping): Keyword arguments.

        Returns:
            Tuple[Sequence, Mapping]: Updated arguments for downstream nodes.
        """
        return get_args_for_downstream(result, self.result_pass_down_mode, args, kwargs)

    def __call__(self, *args, **kwargs):
        return self.run(*args, **kwargs)

    def _run(self, *args, **kwargs):
        raise NotImplementedError

    def load_result(self, *args, **kwargs) -> Tuple[bool, Any]:
        from python_utils.common_objects.workflow.common.step_result_save_options import ResumeMode

        resume = self.resume_with_saved_results
        # Backward compat: bool → ResumeMode
        if resume is True:
            resume = ResumeMode.Always
        elif resume is False or resume is None:
            return False, None

        if resume == ResumeMode.Never:
            return False, None

        if resume == ResumeMode.SkipResumable:
            if getattr(self, "worker_manages_resume", False):
                return False, None

        # Always or SkipResumable (non-resumable worker): try loading checkpoint
        try:
            result_path = self._resolve_result_path(self.name, *args, **kwargs)
            if self._exists_result(self.name, result_path):
                result = self._load_result(self.name, result_path)
                if self.ignore_stop_flag_from_saved_results:
                    result = WorkGraphStopFlags.remove_stop_flag_from_result(result)
                return True, result
        except NotImplementedError:
            pass

        return False, None

    def run(self, *args, _output: list = None, **kwargs):
        result = self._run(*args, **kwargs)
        stop_flag, result = WorkGraphStopFlags.separate_stop_flag_from_result(result)

        # region try unpacking singleton result
        if (
                (
                        (
                                self.unpack_single_result is True
                                and isinstance(result, (list, tuple))
                        ) or
                        (
                                is_class_or_type_(self.unpack_single_result)
                                and isinstance(result, self.unpack_single_result)
                        )
                ) and len(result) == 1

        ):
            result = result[0]
        # endregion

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

    async def arun(self, *args, _output: list = None, _output_idx: tuple = None, **kwargs):
        """Async entry point. Mirrors run() but calls await self._arun()."""
        result = await self._arun(*args, **kwargs)
        stop_flag, result = WorkGraphStopFlags.separate_stop_flag_from_result(result)

        # region try unpacking singleton result
        if (
                (
                        (
                                self.unpack_single_result is True
                                and isinstance(result, (list, tuple))
                        ) or
                        (
                                is_class_or_type_(self.unpack_single_result)
                                and isinstance(result, self.unpack_single_result)
                        )
                ) and len(result) == 1

        ):
            result = result[0]
        # endregion

        if _output_idx is not None:
            # Indexed insertion for deterministic output ordering in WorkGraph._arun()
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

