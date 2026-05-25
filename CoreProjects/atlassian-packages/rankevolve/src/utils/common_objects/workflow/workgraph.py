# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.

import asyncio
import os
import tempfile
import uuid
from queue import Queue
from typing import Any, Callable, Dict, List, Optional, Set, TYPE_CHECKING, Union

from attr import attrib, attrs

if TYPE_CHECKING:
    from rankevolve.src.utils.mp_utils.queued_executor import QueuedExecutorBase

from rankevolve.src.utils.algorithms.graph.dag import DirectedAcyclicGraph
from rankevolve.src.utils.algorithms.graph.node import Node
from rich_python_utils.common_objects.debuggable import Debuggable
from rankevolve.src.utils.common_objects.workflow.common.result_pass_down_mode import (
    ResultPassDownMode,
)
from rankevolve.src.utils.common_objects.workflow.common.step_result_save_options import (
    StepResultSaveOptions,
)
from rankevolve.src.utils.common_objects.workflow.common.worknode_base import (
    NextNodesSelector,
    WorkGraphStopFlags,
    WorkNodeBase,
)
from rankevolve.src.utils.common_utils import flatten_iter, get_relevant_args


def _getattr_or_new(obj, name, default_factory=None):
    """Get attribute or create with factory if missing."""
    if not hasattr(obj, name):
        value = default_factory() if default_factory is not None else None
        setattr(obj, name, value)
        return value
    return getattr(obj, name)


from rankevolve.src.utils.common_utils.async_utils import (
    async_execute_with_retry,
    call_maybe_async,
)


@attrs(slots=False)
class WorkGraphNode(Node, WorkNodeBase):
    """
    Represents a node in a workflow graph that can process inputs and produce outputs,
    optionally saving and resuming results between runs.

    Each WorkGraphNode:
    - Can have multiple upstream (`previous`) and downstream (`next`) nodes.
    - Merges inputs from its upstream nodes before processing, if necessary.
    - Executes its core logic in `__call__`, which must be implemented by subclasses.
    - Supports optional post-processing hooks (`_post_process` and `_optional_post_process`).
    - Can save results to disk and resume from saved results if configured.

    Attributes:
        next (Sequence[WorkGraphNode]): Downstream nodes that receive this node's output.
        previous (Sequence[WorkGraphNode]): Upstream nodes whose outputs serve as this node's inputs.
        resume_with_saved_results (bool): If True, resumes the workflow using saved results.
        result_pass_down_mode (Union[str, rankevolve.src.utils.common_objects.workflow.common.result_pass_down_mode.ResultPassDownMode, Callable, Any]):
            The mode for passing results to downstream nodes. Defaults to `NoPassDown`.
            - If a ResultPassDownMode enum: controls positional pass-down behavior.
            - If a string: injects the result into kwargs under this key (overwriting existing key).
            - If a callable: custom merge function (result, args, kwargs) -> Optional[(args, kwargs)].
              Returns (args, kwargs) tuple to replace, or None to keep original (allows in-place modification).
        logger (Callable[[dict], Any] or logging.Logger): A logging function or logger instance for debugging messages.
        ignore_stop_flag_from_saved_results (bool): If True, ignores the stop flag from previously saved results
            when resuming execution. Defaults to `True`.
        max_repeat (int): Maximum number of times to execute the node. Defaults to 1.
        repeat_condition (Optional[Callable[..., bool]]): Guard callable checked before each execution.
            If it returns False, execution stops and returns fallback_result. Defaults to None.
        fallback_result (Any): Value to return when repeat_condition is False or all retries fail. Defaults to None.
        min_repeat_wait (float): Minimum wait time between repeats in seconds. Defaults to 0.
        max_repeat_wait (float): Maximum wait time between repeats in seconds. Defaults to 0.
        retry_on_exceptions (Optional[List[type]]): Exception types to retry on. Defaults to None (retry on all).
        output_validator (Optional[Callable[..., bool]]): Post-check callable to validate output.
            Returns True if valid, False triggers retry. Defaults to None.

    Note:
        To customize the behavior of a WorkGraphNode, override the private functions in the subclass:
        - `_merge_upstream_inputs`: Customizes how inputs from upstream nodes are merged.
        - `_merge_downstream_results`: Customizes how outputs for downstream nodes are merged.
        - `_get_args_for_downstream`: Customizes arguments passed to downstream nodes.
        - `_get_result_path`: Customizes the path used for saving results.

    Example:
        Define a subclass of WorkGraphNode that simply increments an input integer, and show how to run it.
        We will also demonstrate creating a small workflow graph of three nodes that each increment the value
        and show saving and resuming from temporary files.

        >>> import os, tempfile
        >>> from typing import Any

        # The first argument is passed to the WorkGraphNode's value
        >>> test_node = WorkGraphNode(len)
        >>> assert test_node.value is len

        # Test customized WorkGraphNode
        # Note: Don't use @attrs on the subclass when defining a custom __init__
        >>> class IncrementNode(WorkGraphNode):
        ...     def __init__(self, **kwargs):
        ...         # Pass the lambda as the value argument to the parent constructor
        ...         super().__init__(value=lambda x: x + 1, **kwargs)
        ...
        ...     def _get_result_path(self, name: str, *args, **kwargs) -> str:
        ...         # Save results in a temporary file based on the node's name.
        ...         return os.path.join(tempfile.gettempdir(), f"{name}_result.pkl")

        # Example 1: Run a single node without saving results
        >>> node_no_save = IncrementNode(name="increment_no_save", enable_result_save=False)
        >>> result = node_no_save.run(5)
        >>> result
        6

        # Example 2: Run a single node with result saving enabled
        >>> node_save = IncrementNode(name="increment_save", enable_result_save=True)
        >>> saved_result = node_save.run(10)
        >>> saved_result
        11

        # Running again with resume_with_saved_results will load the saved result instead of recomputing
        >>> node_save_again = IncrementNode(name="increment_save", enable_result_save=True, resume_with_saved_results=True)
        >>> resumed_result = node_save_again.run(10)
        >>> resumed_result
        11

        # Clean up created temp files for single node examples
        >>> os.remove(node_save._get_result_path(node_save.name))

        # Example 3: Creating a small graph of three nodes that each increment the input
        # We'll connect them in a chain: node1 -> node2 -> node3
        >>> node1 = IncrementNode(name="node1", enable_result_save=True, result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg)
        >>> node2 = IncrementNode(name="node2", enable_result_save=True, previous=[node1], result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg)
        >>> node3 = IncrementNode(name="node3", enable_result_save=True, previous=[node2], result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg)

        # Set 'next' pointers to form the chain
        >>> node1.next = [node2]
        >>> node2.next = [node3]

        # Run the first node in the chain
        # The result flows from node1 to node2, then node2 to node3
        >>> final_result = node1.run(0)
        >>> final_result
        3

        # At this point, all three nodes have saved their results.
        # If we run node1 again with resume_with_saved_results = True,
        # node1 and downstream nodes will load saved results rather than recomputing.
        >>> node1_resume = IncrementNode(name="node1", enable_result_save=True, resume_with_saved_results=True, result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg)
        >>> node2_resume = IncrementNode(name="node2", enable_result_save=True, resume_with_saved_results=True, previous=[node1_resume], result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg)
        >>> node3_resume = IncrementNode(name="node3", enable_result_save=True, resume_with_saved_results=True, previous=[node2_resume], result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg)

        >>> node1_resume.next = [node2_resume]
        >>> node2_resume.next = [node3_resume]

        # Running again should load saved results from all nodes, returning the same final result without recomputation
        >>> final_resumed_result = node1_resume.run(0)
        >>> final_resumed_result
        3

        # Clean up created temp files for graph example
        >>> os.remove(node1._get_result_path(node1.name))
        >>> os.remove(node2._get_result_path(node2.name))
        >>> os.remove(node3._get_result_path(node3.name))

        # Demonstrate passing in `WorkGraphStopFlags.AbstainResult` flag to downstream.
        # Only the first downstream node executes as the stop flag will be True.
        >>> node1 = WorkGraphNode(name="root_node", value=lambda x: x + 2, result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg)
        >>> node2 = WorkGraphNode(
        ...     name="threshold_checker1",
        ...     value=lambda x: (WorkGraphStopFlags.AbstainResult if x >= 5 else WorkGraphStopFlags.Continue, x + 1)
        ... )
        >>> node3 = WorkGraphNode(
        ...     name="threshold_checker2",
        ...     value=lambda x: (WorkGraphStopFlags.AbstainResult if x >= 5 else WorkGraphStopFlags.Continue, x + 2)
        ... )
        >>> node1.add_next(node2)
        >>> node1.add_next(node3)
        >>> node1.run(3)
        6

        # Both downstream node execute as the stop flag will be False.
        >>> node1.run(1)
        (4, 5)
    """

    pass_abstain_result_flag_downstream = attrib(type=bool, default=True)
    remove_abstain_result_flag_from_upstream_input = attrib(type=bool, default=False)

    # Repeat/retry configuration
    max_repeat: int = attrib(default=1, kw_only=True)
    repeat_condition: Optional[Callable[..., bool]] = attrib(default=None, kw_only=True)
    fallback_result: Any = attrib(default=None, kw_only=True)
    min_repeat_wait: float = attrib(default=0, kw_only=True)
    max_repeat_wait: float = attrib(default=0, kw_only=True)
    retry_on_exceptions: Optional[List[type]] = attrib(default=None, kw_only=True)
    output_validator: Optional[Callable[..., bool]] = attrib(default=None, kw_only=True)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if isinstance(self.value, Debuggable):
            self.value.set_parent_debuggable(self)

    def _post_adding_next_process(self, next_node):
        from rich_python_utils.common_objects.debuggable import Debuggable

        if isinstance(next_node, Debuggable):
            next_node.set_parent_debuggable(self)

    def _get_fallback_result(self, *args, **kwargs) -> Any:
        """
        Get the fallback result when repeat_condition is False or retries exhausted.

        Default implementation checks kwargs for 'fallback_result' to allow
        dynamic override, falling back to self.fallback_result.

        Args:
            *args: Arguments passed to the node's run method.
            **kwargs: Keyword arguments passed to the node's run method.

        Returns:
            The fallback result.
        """
        return kwargs.get("fallback_result", self.fallback_result)

    def _get_value_reference(self) -> Optional[str]:
        """Get serializable reference for callable value.

        Returns:
            A string reference in the format 'module.name' if the callable has
            __module__ and __name__ attributes, otherwise None.
        """
        if self.value is None:
            return None
        if hasattr(self.value, "__module__") and hasattr(self.value, "__name__"):
            return f"{self.value.__module__}.{self.value.__name__}"
        return None  # Non-serializable callable

    def to_serializable_obj(
        self, mode: str = "auto", _output_format: Optional[str] = None
    ) -> Dict[str, Any]:
        """Serialize WorkGraphNode to dict.

        Serializes node configuration including name, connections, and settings.
        Callable values are stored as references when possible.

        Args:
            mode: Serialization mode ('auto', 'dict', 'pickle')
            _output_format: Target output format for conflict detection

        Returns:
            Dict containing node configuration and connections.
        """
        # Get result_pass_down_mode as string for serialization
        result_pass_down_mode_str = self.result_pass_down_mode
        if isinstance(self.result_pass_down_mode, ResultPassDownMode):
            result_pass_down_mode_str = self.result_pass_down_mode.value
        elif callable(self.result_pass_down_mode):
            # For callable mode, store reference if possible
            if hasattr(self.result_pass_down_mode, "__name__"):
                result_pass_down_mode_str = f"callable:{self.result_pass_down_mode.__module__}.{self.result_pass_down_mode.__name__}"
            else:
                result_pass_down_mode_str = None  # Non-serializable callable

        return {
            "_type": type(self).__name__,
            "_module": type(self).__module__,
            "name": self.name,
            "value_ref": self._get_value_reference(),
            "next_names": [n.name for n in (self.next or [])],
            "previous_names": [n.name for n in (self.previous or [])],
            "config": {
                "max_repeat": self.max_repeat,
                "min_repeat_wait": self.min_repeat_wait,
                "max_repeat_wait": self.max_repeat_wait,
                "enable_result_save": (
                    self.enable_result_save.value
                    if isinstance(self.enable_result_save, StepResultSaveOptions)
                    else self.enable_result_save
                ),
                "result_pass_down_mode": result_pass_down_mode_str,
                "pass_abstain_result_flag_downstream": self.pass_abstain_result_flag_downstream,
                "remove_abstain_result_flag_from_upstream_input": self.remove_abstain_result_flag_from_upstream_input,
            },
        }

    def _merge_upstream_inputs(self, inputs):
        args_list = []  # Explicit list variable
        kwargs = {}
        for _input in inputs:
            if isinstance(_input, tuple) and len(_input) == 2:
                _args, _kwargs = _input
                args_list.extend(_args)
                kwargs.update(_kwargs)
        return args_list, kwargs  # Return list directly - NO tuple conversion

    def _merge_downstream_results(self, *outputs):
        outputs = tuple(flatten_iter(outputs))
        if len(outputs) == 1:
            return outputs[0]
        else:
            return outputs

    # =========================================================================
    # Self-loop memoization helpers
    # =========================================================================

    def _loop_state_id(self):
        """Result ID for the loop state marker."""
        return f"{self.name}___loop_state"

    def _loop_iter_id(self, iteration):
        """Result ID for a per-iteration result."""
        return f"{self.name}___iter{iteration}"

    def _save_loop_iteration(
        self,
        iteration,
        result,
        next_args,
        next_kwargs,
        resolve_args=(),
        resolve_kwargs=None,
    ):
        """Save per-iteration data using existing Resumable infrastructure."""
        iter_data = {
            "result": result,
            "next_args": next_args,
            "next_kwargs": next_kwargs,
        }
        result_path = self._resolve_result_path(
            self._loop_iter_id(iteration), *resolve_args, **(resolve_kwargs or {})
        )
        self._save_result(iter_data, result_path)

    def _save_loop_state(
        self, last_completed_iteration, completed, resolve_args=(), resolve_kwargs=None
    ):
        """Save loop state marker."""
        state = {
            "last_completed_iteration": last_completed_iteration,
            "completed": completed,
        }
        result_path = self._resolve_result_path(
            self._loop_state_id(), *resolve_args, **(resolve_kwargs or {})
        )
        self._save_result(state, result_path)

    def _load_loop_state(self, resolve_args=(), resolve_kwargs=None):
        """Load loop state marker. Returns None if no loop state exists."""
        result_path = self._resolve_result_path(
            self._loop_state_id(), *resolve_args, **(resolve_kwargs or {})
        )
        if self._exists_result(self._loop_state_id(), result_path):
            return self._load_result(self._loop_state_id(), result_path)
        return None

    def _load_loop_iteration(self, iteration, resolve_args=(), resolve_kwargs=None):
        """Load per-iteration data."""
        result_path = self._resolve_result_path(
            self._loop_iter_id(iteration), *resolve_args, **(resolve_kwargs or {})
        )
        return self._load_result(self._loop_iter_id(iteration), result_path)

    # =========================================================================

    def _handle_next_nodes_selector(self, result) -> tuple:
        """
        Handle NextNodesSelector return value.

        Extracts the include_self, include_others, and actual result from
        a NextNodesSelector object. If the result is not a NextNodesSelector,
        returns default values (no self-loop, all downstream nodes).

        Args:
            result: The result returned from node execution, potentially a NextNodesSelector.

        Returns:
            Tuple of (include_self, include_others, actual_result)
        """
        if isinstance(result, NextNodesSelector):
            return (result.include_self, result.include_others, result.result)
        else:
            return (False, True, result)  # Default: no self-loop, all downstream

    def _select_downstream_nodes(self, include_others, include_self: bool) -> list:
        """
        Select which downstream nodes to execute based on include_others and include_self.

        The self-edge (if present in self.next) is only included when include_self=True.
        This is used by the recursive execution in _run().

        Args:
            include_others: Controls which non-self downstream nodes execute:
                - True: Run all downstream nodes
                - False: Run no downstream nodes
                - Set[str]: Run only nodes with these names
            include_self: If True and self-edge exists, include self in returned nodes.

        Returns:
            List of downstream nodes to execute.
        """
        if not self.next:
            return []

        nodes = []
        for node in self.next:
            if node is self:
                # Self-edge: only include if include_self=True
                if include_self:
                    nodes.append(node)
            elif include_others is True:
                nodes.append(node)
            elif include_others is False:
                pass  # Skip non-self nodes
            elif (
                isinstance(include_others, set)
                and getattr(node, "name", None) in include_others
            ):
                nodes.append(node)

        return nodes

    def _run(self, *args, **kwargs):
        stop_flag = WorkGraphStopFlags.Continue

        # region Process a special scenario when input is the AbstainResult flag
        # This flag must be passed down so
        is_input_single_stop_flag = WorkGraphStopFlags.is_input_single_stop_flag(
            *args, **kwargs
        )
        if is_input_single_stop_flag:
            if not self.pass_abstain_result_flag_downstream:
                raise ValueError(
                    "`pass_abstain_result_flag_downstream` is set False, "
                    "but downstream nodes still receive AbstainResult flag"
                )
            stop_flag = args[0]
            if stop_flag != WorkGraphStopFlags.AbstainResult:
                raise ValueError(
                    f"Only AbstainResult flag allowed to pass downstream; got '{stop_flag}'"
                )
        # endregion

        # region Track execution depth for debugging
        # _graph_depth: incremented when calling downstream nodes via node.run()
        #               This tracks how deep we are in the graph traversal (parent → child → grandchild)
        # Note: Self-loop iteration is tracked separately via iteration_count (iterative, not recursive)
        graph_depth = kwargs.pop("_graph_depth", 0)
        # endregion

        # region If there are multiple previous nodes, we need to collect all their outputs before proceeding.
        # NOTE: Exclude self from parent count - self-edges shouldn't block initial execution
        # A self-edge (monitor.add_next(monitor)) adds self to both next AND previous,
        # but the self-loop only provides input AFTER the node executes, not before.
        # Self-loop iterations bypass this entirely via the iterative while loop (no recursive node.run()).
        num_real_parents = sum(1 for p in (self.previous or []) if p is not self)
        if num_real_parents > 1:
            queue: Queue = _getattr_or_new(self, "_queue", default_factory=Queue)
            if is_input_single_stop_flag:
                queue.put(stop_flag)
            else:
                queue.put((args, kwargs))

            # Wait until we have received inputs from all real previous nodes (excluding self)
            if queue.qsize() < num_real_parents:
                return  # Not all inputs are ready yet, wait until next call

            # Retrieve all inputs from the queue
            inputs = [queue.get() for _ in range(num_real_parents)]
            if self.remove_abstain_result_flag_from_upstream_input:
                inputs = list(
                    filter(lambda x: x != WorkGraphStopFlags.AbstainResult, inputs)
                )
            args, kwargs = self._merge_upstream_inputs(inputs)

            # Reset stop_flag if we have valid inputs after filtering AbstainResult.
            # This fixes the race condition where the last caller with AbstainResult
            # would prevent execution even when other parents provided valid inputs.
            # We check `inputs` (not `args or kwargs`) because a valid call with
            # empty args should still execute - Case: parent calls with ([], {}).
            if inputs:
                stop_flag = WorkGraphStopFlags.Continue

        # endregion

        # Check once if self-edge exists (used for iterative self-loop)
        has_self_edge = self in (self.next or [])

        # Log if self-loop node has result saving enabled (iteration-aware memoization active)
        if has_self_edge and (
            self.enable_result_save is True
            or self.enable_result_save == StepResultSaveOptions.Always
        ):
            self.log_debug(
                {
                    "node_name": self.name,
                    "enable_result_save": self.enable_result_save,
                },
                "SelfLoopWithMemoization",
                message=(
                    f"Node '{self.name}' has a self-edge with iteration-aware memoization active."
                ),
            )

        # Store original args for potential self-loop (needed for NoPassDown mode)
        # This must be captured AFTER multi-parent merge so self-loops receive the
        # correctly merged args, not just one parent's args
        original_args, original_kwargs = args, kwargs

        result = None
        # Default values for NextNodesSelector - will be updated if node returns NextNodesSelector
        include_self = False
        include_others = True

        # =========================================================================
        # ITERATIVE SELF-LOOP: Wrap main execution in while True to avoid recursion
        # When include_self=True (continuous monitoring), we loop back via `continue`
        # instead of recursive node.run() calls which would cause stack overflow.
        # =========================================================================
        self_loop_iteration = 0

        # Self-loop resume check: if interrupted mid-loop, resume from last completed iteration
        if (
            has_self_edge
            and self.resume_with_saved_results
            and (
                self.enable_result_save is True
                or self.enable_result_save == StepResultSaveOptions.Always
            )
        ):
            loop_state = self._load_loop_state(resolve_args=args, resolve_kwargs=kwargs)
            if loop_state is not None and not loop_state["completed"]:
                last_iter = loop_state["last_completed_iteration"]
                self_loop_iteration = (
                    last_iter  # will be incremented to last_iter+1 at while-loop start
                )
                iter_data = self._load_loop_iteration(
                    last_iter, resolve_args=args, resolve_kwargs=kwargs
                )
                if self.result_pass_down_mode != ResultPassDownMode.NoPassDown:
                    args, kwargs = iter_data["next_args"], iter_data["next_kwargs"]
        while True:
            self_loop_iteration += 1

            # Log execution depth info
            self.log_debug(
                {
                    "node_name": self.name,
                    "graph_depth": graph_depth,
                    "self_loop_iteration": self_loop_iteration,
                    "is_self_loop": has_self_edge and self_loop_iteration > 1,
                },
                "NodeExecution",
            )

            if stop_flag == WorkGraphStopFlags.Continue:
                # Check if result already exists and can be loaded, or execute the node's core logic to get result
                # NOTE: this is pre-order execution
                #       (parent executes first, propagating the result to downstream nodes)
                is_loaded_from_saved_result, result = self.load_result(*args, **kwargs)
                if not is_loaded_from_saved_result:
                    try:
                        # Execute the core logic.
                        rel_args, rel_kwargs = get_relevant_args(
                            func=self.value,
                            all_var_args_relevant_if_func_support_var_args=True,
                            all_named_args_relevant_if_func_support_named_args=True,
                            args=args,
                            **kwargs,
                        )

                        # Use execute_with_retry to support repeat/retry functionality
                        from rankevolve.src.utils.common_utils.function_helper import (
                            execute_with_retry,
                        )

                        result = execute_with_retry(
                            func=self.value,
                            max_retry=self.max_repeat,
                            min_retry_wait=self.min_repeat_wait,
                            max_retry_wait=self.max_repeat_wait,
                            retry_on_exceptions=self.retry_on_exceptions,
                            output_validator=self.output_validator,
                            pre_condition=self.repeat_condition,
                            args=rel_args,
                            kwargs=rel_kwargs,
                            default_return_or_raise=self._get_fallback_result(
                                *args, **kwargs
                            ),
                        )
                    except Exception as err:
                        import traceback

                        self.log_error(
                            {
                                "name": self.name,
                                "executor": self.value,
                                "args": args,
                                "kwargs": kwargs,
                                "exception_type": type(err).__name__,
                                "exception_message": str(err),
                                "traceback": traceback.format_exc(),
                            },
                            "NodeExecutionFailed",
                        )

                        raise err

                    # Handle NextNodesSelector return value first
                    include_self, include_others, result = (
                        self._handle_next_nodes_selector(result)
                    )

                    stop_flag, result = (
                        WorkGraphStopFlags.separate_stop_flag_from_result(result)
                    )

                    # After the core logic executes successfully, run the mandatory _post_process hook.
                    _result = self._post_process(result, *args, **kwargs)
                    if _result is not None:
                        result = _result

                    # If optional post-processing is enabled, apply it
                    if self.enable_optional_post_process:
                        _result = self._optional_post_process(result, *args, **kwargs)
                        if _result is not None:
                            result = _result

                    # Save results if configured to do so
                    # For self-loop nodes, skip primary key save during iteration
                    # (would overwrite prematurely). Per-iteration save happens below.
                    if (
                        self.enable_result_save is True
                        or self.enable_result_save == StepResultSaveOptions.Always
                    ):
                        if not has_self_edge:
                            result_path = self._get_result_path(
                                self.name, *args, **kwargs
                            )
                            self._save_result(result, result_path)

            # Propagate the result to downstream nodes if any.
            if self.next:
                if stop_flag == WorkGraphStopFlags.Continue:
                    nargs, nkwargs = self._get_args_for_downstream(result, args, kwargs)
                    # EXCLUDE SELF from downstream nodes - self-loop is handled via while loop
                    nodes_to_run = self._select_downstream_nodes(
                        include_others, include_self=False
                    )
                else:
                    # For stop flags, we still notify all downstream nodes (not filtered)
                    # but exclude self since self-loop shouldn't run on stop flags
                    nodes_to_run = [n for n in self.next if n is not self]

                downstream_results = []
                for node in nodes_to_run:  # type: WorkGraphNode
                    # NOTE: if the down stream node has multiple previous nodes,
                    #       then it might return None because not all inputs are ready
                    if stop_flag == WorkGraphStopFlags.Continue:
                        stop_flag = node.run(
                            *nargs,
                            **nkwargs,
                            _output=downstream_results,
                            _graph_depth=graph_depth + 1,
                        )
                    elif stop_flag == WorkGraphStopFlags.AbstainResult:
                        # Notify downstream nodes that this node abstained from contributing
                        # This notification is necessary for multi-parent nodes to handle correctly
                        node.run(stop_flag)
                    elif stop_flag == WorkGraphStopFlags.Terminate:
                        break

                # The AbstainResult flag only impacts sibling nodes,
                # and needs to reset to avoid impacting other nodes
                if stop_flag == WorkGraphStopFlags.AbstainResult:
                    stop_flag = WorkGraphStopFlags.Continue

                # Merge multiple downstream outputs
                if downstream_results:
                    result = self._merge_downstream_results(downstream_results)

                # Per-iteration save for self-loop nodes
                if (
                    has_self_edge
                    and not is_loaded_from_saved_result
                    and (
                        self.enable_result_save is True
                        or self.enable_result_save == StepResultSaveOptions.Always
                    )
                    and stop_flag == WorkGraphStopFlags.Continue
                ):
                    if self.result_pass_down_mode == ResultPassDownMode.NoPassDown:
                        _loop_next_args = original_args
                        _loop_next_kwargs = original_kwargs
                    else:
                        _loop_next_args = nargs
                        _loop_next_kwargs = nkwargs
                    self._save_loop_iteration(
                        self_loop_iteration,
                        result,
                        _loop_next_args,
                        _loop_next_kwargs,
                        resolve_args=args,
                        resolve_kwargs=kwargs,
                    )

            # =========================================================================
            # SELF-LOOP HANDLING: Check if we should loop back (instead of recursion)
            # Conditions for self-loop:
            # 1. include_self=True (node returned NextNodesSelector with include_self=True)
            # 2. has_self_edge (self is in self.next - configured at graph construction)
            # 3. stop_flag == Continue (no Terminate or error occurred)
            # =========================================================================
            if (
                include_self
                and has_self_edge
                and stop_flag == WorkGraphStopFlags.Continue
            ):
                # Prepare args for next iteration based on result_pass_down_mode
                if self.result_pass_down_mode == ResultPassDownMode.NoPassDown:
                    args, kwargs = original_args, dict(original_kwargs)
                else:
                    args, kwargs = nargs, dict(nkwargs)
                # Reset for next iteration - we'll get fresh values from next execution
                include_self = False
                include_others = True

                # Save partial loop state before continuing
                if (
                    self.enable_result_save is True
                    or self.enable_result_save == StepResultSaveOptions.Always
                ):
                    self._save_loop_state(
                        self_loop_iteration,
                        completed=False,
                        resolve_args=args,
                        resolve_kwargs=kwargs,
                    )

                self.log_debug(
                    {
                        "node_name": self.name,
                        "graph_depth": graph_depth,
                        "completed_iteration": self_loop_iteration,
                        "next_iteration": self_loop_iteration + 1,
                    },
                    "SelfLoopContinue",
                )
                continue  # Loop back to re-execute this node (replaces recursive call)
            else:
                if has_self_edge and self_loop_iteration > 1:
                    self.log_debug(
                        {
                            "node_name": self.name,
                            "graph_depth": graph_depth,
                            "total_iterations": self_loop_iteration,
                            "exit_reason": "include_self=False"
                            if not include_self
                            else f"stop_flag={stop_flag}",
                        },
                        "SelfLoopExit",
                    )
                # Save final result and completion marker for self-loop nodes
                if has_self_edge and (
                    self.enable_result_save is True
                    or self.enable_result_save == StepResultSaveOptions.Always
                ):
                    result_path = self._get_result_path(self.name, *args, **kwargs)
                    self._save_result(result, result_path)
                    self._save_loop_state(
                        self_loop_iteration,
                        completed=True,
                        resolve_args=args,
                        resolve_kwargs=kwargs,
                    )
                break  # Exit while loop - no self-loop or stopped

        if stop_flag == WorkGraphStopFlags.Continue:
            return result
        else:
            return (
                stop_flag,
                result,
            )  # pop `WorkGraphStopFlags.Terminate` to stop the entire graph

    async def _arun(self, *args, **kwargs):
        """Async implementation mirroring _run() for WorkGraphNode.

        Uses asyncio.Queue for multi-parent input collection, async_execute_with_retry
        for node execution, call_maybe_async for hooks, and asyncio.gather() for
        concurrent downstream fan-out.

        Known concurrency semantic difference from _run():
        - In sync _run(), downstream nodes execute sequentially in a for-loop, so if one
          downstream node returns Terminate, subsequent siblings are skipped immediately.
          In async _arun(), all downstream nodes launch concurrently via asyncio.gather(),
          so one sibling's Terminate flag cannot prevent other already-launched siblings
          from executing. This is an intentional tradeoff: the async path prioritizes
          throughput over strict sequential stop-flag propagation between siblings.
          The Terminate flag is still respected at the WorkGraph level and within each
          branch. Only the inter-sibling sequential ordering is relaxed.
          If strict sync-equivalent ordering is needed, use max_concurrency=1 on WorkGraph.
        """
        stop_flag = WorkGraphStopFlags.Continue

        # region Process a special scenario when input is the AbstainResult flag
        is_input_single_stop_flag = WorkGraphStopFlags.is_input_single_stop_flag(
            *args, **kwargs
        )
        if is_input_single_stop_flag:
            if not self.pass_abstain_result_flag_downstream:
                raise ValueError(
                    "`pass_abstain_result_flag_downstream` is set False, "
                    "but downstream nodes still receive AbstainResult flag"
                )
            stop_flag = args[0]
            if stop_flag != WorkGraphStopFlags.AbstainResult:
                raise ValueError(
                    f"Only AbstainResult flag allowed to pass downstream; got '{stop_flag}'"
                )
        # endregion

        # region Track execution depth for debugging
        graph_depth = kwargs.pop("_graph_depth", 0)
        # endregion

        # Pop _semaphore early so it doesn't leak into get_relevant_args or node execution
        semaphore = kwargs.pop("_semaphore", None)

        # region Multi-parent input collection using asyncio.Queue
        num_real_parents = sum(1 for p in (self.previous or []) if p is not self)
        if num_real_parents > 1:
            aqueue: asyncio.Queue = _getattr_or_new(
                self, "_aqueue", default_factory=asyncio.Queue
            )
            if is_input_single_stop_flag:
                await aqueue.put(stop_flag)
            else:
                await aqueue.put((args, kwargs))

            if aqueue.qsize() < num_real_parents:
                return  # Not all inputs are ready yet

            inputs = [aqueue.get_nowait() for _ in range(num_real_parents)]
            if self.remove_abstain_result_flag_from_upstream_input:
                inputs = list(
                    filter(lambda x: x != WorkGraphStopFlags.AbstainResult, inputs)
                )
            args, kwargs = self._merge_upstream_inputs(inputs)

            if inputs:
                stop_flag = WorkGraphStopFlags.Continue
        # endregion

        # Check once if self-edge exists (used for iterative self-loop)
        has_self_edge = self in (self.next or [])

        # Log if self-loop node has result saving enabled (iteration-aware memoization active)
        if has_self_edge and (
            self.enable_result_save is True
            or self.enable_result_save == StepResultSaveOptions.Always
        ):
            self.log_debug(
                {
                    "node_name": self.name,
                    "enable_result_save": self.enable_result_save,
                },
                "SelfLoopWithMemoization",
                message=(
                    f"Node '{self.name}' has a self-edge with iteration-aware memoization active."
                ),
            )

        # Store original args for potential self-loop (needed for NoPassDown mode)
        original_args, original_kwargs = args, kwargs

        result = None
        include_self = False
        include_others = True

        # =========================================================================
        # ITERATIVE SELF-LOOP (async): Wrap main execution in while True
        # Same pattern as sync _run() — avoids recursion for self-loop nodes.
        # =========================================================================
        self_loop_iteration = 0

        # Self-loop resume check: if interrupted mid-loop, resume from last completed iteration
        if (
            has_self_edge
            and self.resume_with_saved_results
            and (
                self.enable_result_save is True
                or self.enable_result_save == StepResultSaveOptions.Always
            )
        ):
            loop_state = self._load_loop_state(resolve_args=args, resolve_kwargs=kwargs)
            if loop_state is not None and not loop_state["completed"]:
                last_iter = loop_state["last_completed_iteration"]
                self_loop_iteration = (
                    last_iter  # will be incremented to last_iter+1 at while-loop start
                )
                iter_data = self._load_loop_iteration(
                    last_iter, resolve_args=args, resolve_kwargs=kwargs
                )
                if self.result_pass_down_mode != ResultPassDownMode.NoPassDown:
                    args, kwargs = iter_data["next_args"], iter_data["next_kwargs"]
        while True:
            self_loop_iteration += 1

            self.log_debug(
                {
                    "node_name": self.name,
                    "graph_depth": graph_depth,
                    "self_loop_iteration": self_loop_iteration,
                    "is_self_loop": has_self_edge and self_loop_iteration > 1,
                },
                "NodeExecution",
            )

            if stop_flag == WorkGraphStopFlags.Continue:
                is_loaded_from_saved_result, result = self.load_result(*args, **kwargs)
                if not is_loaded_from_saved_result:
                    try:
                        rel_args, rel_kwargs = get_relevant_args(
                            func=self.value,
                            all_var_args_relevant_if_func_support_var_args=True,
                            all_named_args_relevant_if_func_support_named_args=True,
                            args=args,
                            **kwargs,
                        )

                        result = await async_execute_with_retry(
                            func=self.value,
                            max_retry=self.max_repeat,
                            min_retry_wait=self.min_repeat_wait,
                            max_retry_wait=self.max_repeat_wait,
                            retry_on_exceptions=self.retry_on_exceptions,
                            output_validator=self.output_validator,
                            pre_condition=self.repeat_condition,
                            args=rel_args,
                            kwargs=rel_kwargs,
                            default_return_or_raise=self._get_fallback_result(
                                *args, **kwargs
                            ),
                        )
                    except Exception as err:
                        import traceback

                        self.log_error(
                            {
                                "name": self.name,
                                "executor": self.value,
                                "args": args,
                                "kwargs": kwargs,
                                "exception_type": type(err).__name__,
                                "exception_message": str(err),
                                "traceback": traceback.format_exc(),
                            },
                            "NodeExecutionFailed",
                        )
                        raise err

                    # Handle NextNodesSelector return value
                    include_self, include_others, result = (
                        self._handle_next_nodes_selector(result)
                    )

                    stop_flag, result = (
                        WorkGraphStopFlags.separate_stop_flag_from_result(result)
                    )

                    # Post-process hooks via call_maybe_async
                    _result = await call_maybe_async(
                        self._post_process, result, *args, **kwargs
                    )
                    if _result is not None:
                        result = _result

                    if self.enable_optional_post_process:
                        _result = await call_maybe_async(
                            self._optional_post_process, result, *args, **kwargs
                        )
                        if _result is not None:
                            result = _result

                    # Save results if configured
                    # For self-loop nodes, skip primary key save during iteration
                    if (
                        self.enable_result_save is True
                        or self.enable_result_save == StepResultSaveOptions.Always
                    ):
                        if not has_self_edge:
                            result_path = self._get_result_path(
                                self.name, *args, **kwargs
                            )
                            self._save_result(result, result_path)

            # Propagate the result to downstream nodes concurrently
            if self.next:
                if stop_flag == WorkGraphStopFlags.Continue:
                    nargs, nkwargs = self._get_args_for_downstream(result, args, kwargs)
                    nodes_to_run = self._select_downstream_nodes(
                        include_others, include_self=False
                    )
                else:
                    nodes_to_run = [n for n in self.next if n is not self]

                # Concurrent downstream fan-out via asyncio.gather with indexed insertion
                # for deterministic result ordering (matching sync path's sequential order).
                _DS_EMPTY = object()  # sentinel to distinguish "no result" from None
                downstream_results = [_DS_EMPTY] * len(nodes_to_run)
                tasks = []
                for idx, node in enumerate(nodes_to_run):
                    if stop_flag == WorkGraphStopFlags.Continue:
                        # Capture loop variables explicitly to avoid closure-over-loop-variable bug
                        nargs_copy = tuple(nargs)
                        nkwargs_copy = dict(nkwargs)
                        if semaphore:

                            async def _run_ds(i, n, a, kw, sem):
                                async with sem:
                                    return await n.arun(
                                        *a,
                                        _output_idx=(downstream_results, i),
                                        _graph_depth=graph_depth + 1,
                                        _semaphore=sem,
                                        **kw,
                                    )

                            tasks.append(
                                _run_ds(idx, node, nargs_copy, nkwargs_copy, semaphore)
                            )
                        else:

                            async def _run_ds(i, n, a, kw):
                                return await n.arun(
                                    *a,
                                    _output_idx=(downstream_results, i),
                                    _graph_depth=graph_depth + 1,
                                    **kw,
                                )

                            tasks.append(_run_ds(idx, node, nargs_copy, nkwargs_copy))
                    elif stop_flag == WorkGraphStopFlags.AbstainResult:
                        # Notify downstream nodes of abstention
                        tasks.append(node.arun(stop_flag))
                    elif stop_flag == WorkGraphStopFlags.Terminate:
                        break

                if tasks:
                    await asyncio.gather(*tasks)

                # The AbstainResult flag only impacts sibling nodes,
                # and needs to reset to avoid impacting other nodes
                if stop_flag == WorkGraphStopFlags.AbstainResult:
                    stop_flag = WorkGraphStopFlags.Continue

                # Merge downstream outputs — filter unset sentinel slots but
                # preserve legitimate None results (e.g., multi-parent nodes
                # returning None when not all parents have sent input yet).
                # This matches the sync _run() path which does NOT filter None.
                downstream_results = [
                    r for r in downstream_results if r is not _DS_EMPTY
                ]
                if downstream_results:
                    result = self._merge_downstream_results(downstream_results)

                # Per-iteration save for self-loop nodes
                if (
                    has_self_edge
                    and not is_loaded_from_saved_result
                    and (
                        self.enable_result_save is True
                        or self.enable_result_save == StepResultSaveOptions.Always
                    )
                    and stop_flag == WorkGraphStopFlags.Continue
                ):
                    if self.result_pass_down_mode == ResultPassDownMode.NoPassDown:
                        _loop_next_args = original_args
                        _loop_next_kwargs = original_kwargs
                    else:
                        _loop_next_args = nargs
                        _loop_next_kwargs = nkwargs
                    self._save_loop_iteration(
                        self_loop_iteration,
                        result,
                        _loop_next_args,
                        _loop_next_kwargs,
                        resolve_args=args,
                        resolve_kwargs=kwargs,
                    )

            # =========================================================================
            # SELF-LOOP HANDLING (async): Same iterative pattern as sync _run()
            # =========================================================================
            if (
                include_self
                and has_self_edge
                and stop_flag == WorkGraphStopFlags.Continue
            ):
                if self.result_pass_down_mode == ResultPassDownMode.NoPassDown:
                    args, kwargs = original_args, dict(original_kwargs)
                else:
                    args, kwargs = nargs, dict(nkwargs)
                include_self = False
                include_others = True

                # Save partial loop state before continuing
                if (
                    self.enable_result_save is True
                    or self.enable_result_save == StepResultSaveOptions.Always
                ):
                    self._save_loop_state(
                        self_loop_iteration,
                        completed=False,
                        resolve_args=args,
                        resolve_kwargs=kwargs,
                    )

                self.log_debug(
                    {
                        "node_name": self.name,
                        "graph_depth": graph_depth,
                        "completed_iteration": self_loop_iteration,
                        "next_iteration": self_loop_iteration + 1,
                    },
                    "SelfLoopContinue",
                )
                continue
            else:
                if has_self_edge and self_loop_iteration > 1:
                    self.log_debug(
                        {
                            "node_name": self.name,
                            "graph_depth": graph_depth,
                            "total_iterations": self_loop_iteration,
                            "exit_reason": "include_self=False"
                            if not include_self
                            else f"stop_flag={stop_flag}",
                        },
                        "SelfLoopExit",
                    )
                # Save final result and completion marker for self-loop nodes
                if has_self_edge and (
                    self.enable_result_save is True
                    or self.enable_result_save == StepResultSaveOptions.Always
                ):
                    result_path = self._get_result_path(self.name, *args, **kwargs)
                    self._save_result(result, result_path)
                    self._save_loop_state(
                        self_loop_iteration,
                        completed=True,
                        resolve_args=args,
                        resolve_kwargs=kwargs,
                    )
                break

        if stop_flag == WorkGraphStopFlags.Continue:
            return result
        else:
            return stop_flag, result


@attrs(slots=False)
class WorkGraph(DirectedAcyclicGraph, WorkNodeBase):
    """
    Represents a Directed Acyclic Graph (DAG) of `WorkGraphNode` instances and orchestrates
    their execution. It supports saving results for each node execution and resuming from
    previously saved results to skip redundant computations.

    This class:
    - Executes all `start_nodes` in sequence when `run` is called.
    - Attempts to resume execution if `resume_with_saved_results` is True by loading
      previously saved results for nodes.
    - If a node execution raises an exception and `enable_result_save` is set to
      `StepResultSaveOptions.OnError`, it saves the results obtained so far before re-raising the error.
    - If `enable_result_save` is set to `StepResultSaveOptions.Always` or `True`, it saves the result
      of each successfully executed node.
    - After executing all `start_nodes`, the aggregated results are passed to `post_process` for
      optional final modifications.

    Attributes:
        enable_result_save (Union[StepResultSaveOptions, bool, str]):
            Determines when to save node results. Can be `NoSave`, `Always`, `OnError`,
            True (equivalent to `Always`), or False (equivalent to `NoSave`).
        resume_with_saved_results (bool):
            If True, attempts to load previously saved results for nodes, skipping their execution if available.

    Note:
        - The actual skipping of node execution when `resume_with_saved_results` is True is handled by each node.
        - The `WorkGraph` simply orchestrates node execution and handles saving/error scenarios at a high level.

    Example:
        >>> from typing import Any, Callable
        >>> from enum import Enum
        >>> from attr import attrs, attrib

        >>> # Assume we have a simple WorkGraphNode class that just returns its input incremented by 1.
        >>> # Note: Don't use @attrs on the subclass when defining a custom __init__
        >>> class IncrementNode(WorkGraphNode):
        ...     def __init__(self, **kwargs):
        ...         # Pass the lambda as the value argument to the parent constructor
        ...         super().__init__(value=lambda x: x + 1, **kwargs)
        ...
        ...     def _get_result_path(self, name: str, *args, **kwargs) -> str:
        ...         # For demonstration purposes, use a temporary file path.
        ...         return os.path.join(tempfile.gettempdir(), f"{name}_result.pkl")

        >>> @attrs(slots=False)
        ... class MyWorkGraph(WorkGraph):
        ...     def _get_result_path(self, result_id, *args, **kwargs) -> str:
        ...         # Provide a stable location for saving/loading results.
        ...         return os.path.join(tempfile.gettempdir(), f"workgraph_{result_id}_result.pkl")

        # Example 1: Running a simple graph with a single start node
        >>> node = IncrementNode(name="increment_node", enable_result_save=False)
        >>> graph = MyWorkGraph(start_nodes=[node], enable_result_save=False, resume_with_saved_results=False)
        >>> graph.run(5)  # node.run(5) -> 6, no saving performed
        6

        # Example 2: Enable always saving results and run again
        >>> node_save = IncrementNode(name="increment_save_node", enable_result_save=StepResultSaveOptions.Always)
        >>> graph_save = MyWorkGraph(start_nodes=[node_save], enable_result_save=StepResultSaveOptions.Always, resume_with_saved_results=False)
        >>> graph_save.run(10)  # node_save.run(10) -> 11, result saved
        11

        # If we run again with resume enabled, it should skip execution and load the saved result directly
        >>> graph_resume = MyWorkGraph(start_nodes=[node_save], enable_result_save=StepResultSaveOptions.Always, resume_with_saved_results=True)
        >>> graph_resume.run(10)
        11

        # Example 3: OnError saving - If the node raises an exception, partial results will be saved
        >>> def failing_value(x):
        ...     if x == 0:
        ...         raise ValueError("Test error")
        ...     return x + 1
        ...
        >>> class FailingNode(WorkGraphNode):
        ...     def __init__(self, **kwargs):
        ...         # Pass the function as the value argument to the parent constructor
        ...         super().__init__(value=failing_value, **kwargs)
        ...
        ...     def _get_result_path(self, name: str, *args, **kwargs) -> str:
        ...         return os.path.join(tempfile.gettempdir(), f"{name}_failing_result.pkl")

        # Create a graph with two nodes: first increments, second fails on input 0
        >>> node_ok = IncrementNode(name="ok_node", result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg, enable_result_save=StepResultSaveOptions.OnError, logger=print)
        >>> node_fail = FailingNode(name="fail_node", enable_result_save=StepResultSaveOptions.OnError, logger=print)
        >>> node_ok.add_next(node_fail)
        >>> graph_on_error = MyWorkGraph(start_nodes=[node_ok], enable_result_save=StepResultSaveOptions.OnError, resume_with_saved_results=False, logger=print)

        >>> try:
        ...     graph_on_error.run(0) # doctest: +ELLIPSIS
        ... except ValueError:
        ...     print("Caught ValueError and partial results should be saved")
        2

        # Running with argument -1 will cause fail_node to raise ValueError (node_fail will receive 0 as its input for `failing_value`)
        >>> try:
        ...     graph_on_error.run(-1) # doctest: +ELLIPSIS
        ... except ValueError:
        ...     print("Caught ValueError and partial results should be saved")
        FailingNode_...
        Caught ValueError and partial results should be saved

        # Example 4: Multiple start nodes
        # We'll define two increment nodes as separate start nodes. The graph will run both
        # and return their results as a list, which the `post_process` can then handle.
        >>> node_a = IncrementNode(name="increment_a", enable_result_save=False)
        >>> node_b = IncrementNode(name="increment_b", enable_result_save=False)

        # Create a graph with two start nodes and a custom post_process that sums their outputs.
        >>> class SummationGraph(MyWorkGraph):
        ...     def post_process(self, results, *args, **kwargs):
        ...         # results will be a list of outputs from both start nodes
        ...         return sum(results)

        >>> graph_multi_start = SummationGraph(start_nodes=[node_a, node_b], enable_result_save=False, resume_with_saved_results=False)
        >>> # Running the graph with input 5 for both nodes:
        >>> # node_a.run(5) -> 6
        >>> # node_b.run(5) -> 6
        >>> # post_process([6, 6]) -> 12
        >>> graph_multi_start.run(5)
        12

        >>> class SummationNode(WorkGraphNode):
        ...     def __init__(self, **kwargs):
        ...         # Pass the lambda as the value argument to the parent constructor
        ...         # The value function for SummationNode will sum all provided positional arguments.
        ...         super().__init__(value=lambda *args: sum(args), **kwargs)
        ...
        ...     def _get_result_path(self, name: str, *args, **kwargs) -> str:
        ...         return os.path.join(tempfile.gettempdir(), f"{name}_sum_result.pkl")

        >>> # Define two start nodes that increment the input
        >>> node_a = IncrementNode(
        ...     name="increment_a",
        ...     result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        ... )
        >>> node_b = IncrementNode(
        ...     name="increment_b",
        ...     result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg
        ... )

        >>> # Define a second-layer node that sums the outputs of node_a and node_b
        >>> node_sum = SummationNode(name="sum_node")

        # Link the start nodes to the summation node
        >>> node_a.add_next(node_sum)
        >>> node_b.add_next(node_sum)

        # Create a graph with two start nodes and one second-layer node.
        # The graph runs the start nodes, then the summation node will automatically run
        # when both its upstream nodes have finished.
        >>> graph_two_layers = MyWorkGraph(start_nodes=[node_a, node_b])

        # Running the graph with input 5:
        # node_a.run(5) -> 6
        # node_b.run(5) -> 6
        # node_sum receives [6, 6] and returns 12
        >>> graph_two_layers.run(5)
        12

        # Demonstrate passing in `WorkGraphStopFlags.AbstainResult` flag to downstream.
        >>> node1 = WorkGraphNode(name="double_node", value=lambda x: x * 2, result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg)
        >>> node2 = WorkGraphNode(
        ...     name="threshold_checker1",
        ...     value=lambda x: (WorkGraphStopFlags.AbstainResult if x >= 10 else WorkGraphStopFlags.Continue, x)
        ... )
        >>> node3 = WorkGraphNode(
        ...     name="threshold_checker2",
        ...     value=lambda x: (WorkGraphStopFlags.AbstainResult if x >= 10 else WorkGraphStopFlags.Continue, x)
        ... )
        >>> node1.add_next(node2)
        >>> node1.add_next(node3)
        >>> graph = WorkGraph(start_nodes=[node1], enable_result_save=False)
        >>> graph.run(5)
        10

        >>> graph.run(4)
        (8, 8)
    """

    # Optional executor for queue-based parallel execution (Phase 4)
    # When set, _run() delegates to executor.run_async() instead of recursive execution
    # Use wrapper mode (threads) or router mode (multi-processing)
    executor: Optional["QueuedExecutorBase"] = attrib(default=None, kw_only=True)

    # Optional concurrency limit for async execution path (_arun).
    # When set, creates an asyncio.Semaphore(max_concurrency) to limit concurrent node execution.
    # Ignored by the sync _run() path.
    max_concurrency: Optional[int] = attrib(default=None, kw_only=True)

    # When True, run()/__call__() delegates to _arun() for parallel start node
    # execution via asyncio.gather(). This lets callers get async parallelism
    # without changing their call site from run() to arun().
    use_async: bool = attrib(default=False, kw_only=True)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        for start_node in self.start_nodes:
            if isinstance(start_node, Debuggable):
                start_node.set_parent_debuggable(self)

    def _post_process(self, result, *args, **kwargs):
        return tuple(x for x in result if x is not None)

    def to_serializable_obj(
        self, mode: str = "auto", _output_format: Optional[str] = None
    ) -> Dict[str, Any]:
        """Serialize WorkGraph to dict with circular reference handling.

        Traverses the graph starting from start_nodes and serializes all
        reachable nodes, handling circular references by tracking visited nodes.

        Args:
            mode: Serialization mode ('auto', 'dict', 'pickle')
            _output_format: Target output format for conflict detection

        Returns:
            Dict containing graph structure with version, start_node_names,
            nodes list, and config.
        """
        visited = set()
        nodes_data = []

        def serialize_node(node):
            if node.name in visited:
                return
            visited.add(node.name)
            nodes_data.append(node.to_serializable_obj())
            for child in node.next or []:
                serialize_node(child)

        for start_node in self.start_nodes:
            serialize_node(start_node)

        return {
            "_type": type(self).__name__,
            "_module": type(self).__module__,
            "version": "1.0",
            "start_node_names": [n.name for n in self.start_nodes],
            "nodes": nodes_data,
            "config": {
                "enable_result_save": (
                    self.enable_result_save.value
                    if isinstance(self.enable_result_save, StepResultSaveOptions)
                    else self.enable_result_save
                ),
                "resume_with_saved_results": self.resume_with_saved_results,
            },
        }

    def _clear_all_node_queues(self):
        """
        Clear queues on all nodes for fresh execution.

        This ensures that stale queue items from previous runs (e.g., after Terminate)
        don't corrupt subsequent executions when the graph is reused.
        Clears both sync _queue (stdlib Queue) and async _aqueue (asyncio.Queue).
        """
        visited = set()

        def clear_node(node):
            if id(node) in visited:
                return
            visited.add(id(node))
            if hasattr(node, "_queue"):
                # Clear the queue by replacing it
                from queue import Queue

                node._queue = Queue()
            if hasattr(node, "_aqueue"):
                # asyncio.Queue has no .clear() method, so replace with a new instance
                node._aqueue = asyncio.Queue()
            for child in node.next or []:
                clear_node(child)

        for start_node in self.start_nodes:
            clear_node(start_node)

    def _all_nodes(self) -> List["WorkGraphNode"]:
        """Get all nodes reachable from start_nodes via DFS."""
        visited = set()
        nodes = []

        def collect(node):
            if id(node) in visited:
                return
            visited.add(id(node))
            nodes.append(node)
            for child in node.next or []:
                collect(child)

        for start_node in self.start_nodes:
            collect(start_node)
        return nodes

    # =========================================================================
    # Phase 4: Queue-Based Execution Support
    # =========================================================================

    def _create_wrapper_callable(
        self,
        node: "WorkGraphNode",
        upstream_inputs: Dict[str, List],
        failed_parents: Dict[str, Set[str]],
    ) -> Callable:
        """
        Create a wrapper callable for wrapper mode (threads).

        The wrapper executes the node and returns (result, next_tasks) tuple.
        Used with executor.run_async(router=None) for thread-based executors.

        Args:
            node: The node to wrap
            upstream_inputs: Shared dict for collecting multi-parent inputs
            failed_parents: Shared dict for tracking failed parent nodes

        Returns:
            Callable that returns (result, next_tasks) tuple
        """
        from rankevolve.src.utils.mp_utils.task import Task

        def wrapper(*args, **kwargs):
            # Execute the node's value function
            from rankevolve.src.utils.common_utils import get_relevant_args
            from rankevolve.src.utils.common_utils.function_helper import (
                execute_with_retry,
            )

            rel_args, rel_kwargs = get_relevant_args(
                func=node.value,
                all_var_args_relevant_if_func_support_var_args=True,
                all_named_args_relevant_if_func_support_named_args=True,
                args=args,
                **kwargs,
            )

            result = execute_with_retry(
                func=node.value,
                max_retry=node.max_repeat,
                min_retry_wait=node.min_repeat_wait,
                max_retry_wait=node.max_repeat_wait,
                retry_on_exceptions=node.retry_on_exceptions,
                output_validator=node.output_validator,
                pre_condition=node.repeat_condition,
                args=rel_args,
                kwargs=rel_kwargs,
                default_return_or_raise=node._get_fallback_result(*args, **kwargs),
            )

            # Handle NextNodesSelector
            include_self, include_others, actual_result = (
                node._handle_next_nodes_selector(result)
            )

            # Get downstream nodes
            downstream = node._select_downstream_nodes(include_others, include_self)

            # Build next tasks
            next_tasks = []
            for downstream_node in downstream:
                if downstream_node is node:
                    # SELF-EDGE: Use node's result_pass_down_mode
                    if node.result_pass_down_mode == ResultPassDownMode.NoPassDown:
                        self_args, self_kwargs = args, dict(kwargs)
                    else:
                        self_args, self_kwargs = node._get_args_for_downstream(
                            actual_result, args, kwargs
                        )

                    new_task_id = f"{node.name}::selfloop::{uuid.uuid4().hex[:8]}"
                    task = Task(
                        callable=self._create_wrapper_callable(
                            node, upstream_inputs, failed_parents
                        ),
                        args=self_args,
                        kwargs=self_kwargs,
                        task_id=new_task_id,
                    )
                    next_tasks.append(task)
                else:
                    # Regular downstream node
                    num_parents = len(
                        [
                            p
                            for p in (downstream_node.previous or [])
                            if p is not downstream_node
                        ]
                    )
                    nargs, nkwargs = node._get_args_for_downstream(
                        actual_result, args, kwargs
                    )

                    if num_parents <= 1:
                        # Single parent - create task immediately
                        new_task_id = f"{downstream_node.name}::{uuid.uuid4().hex[:8]}"
                        task = Task(
                            callable=self._create_wrapper_callable(
                                downstream_node, upstream_inputs, failed_parents
                            ),
                            args=nargs,
                            kwargs=nkwargs,
                            task_id=new_task_id,
                        )
                        next_tasks.append(task)
                    else:
                        # Multi-parent - collect input and check if all parents done
                        downstream_name = downstream_node.name
                        if downstream_name not in upstream_inputs:
                            upstream_inputs[downstream_name] = []

                        upstream_inputs[downstream_name].append((nargs, nkwargs))

                        # Check if all parents accounted for (success + failure)
                        successful = len(upstream_inputs[downstream_name])
                        failed = len(failed_parents.get(downstream_name, set()))

                        if successful + failed >= num_parents:
                            # All parents accounted for - merge inputs and create task
                            merged_args, merged_kwargs = (
                                downstream_node._merge_upstream_inputs(
                                    upstream_inputs[downstream_name]
                                )
                            )

                            # Clear for potential re-execution
                            upstream_inputs[downstream_name] = []
                            if downstream_name in failed_parents:
                                failed_parents[downstream_name] = set()

                            new_task_id = f"{downstream_name}::{uuid.uuid4().hex[:8]}"
                            task = Task(
                                callable=self._create_wrapper_callable(
                                    downstream_node, upstream_inputs, failed_parents
                                ),
                                args=merged_args,
                                kwargs=merged_kwargs,
                                task_id=new_task_id,
                            )
                            next_tasks.append(task)

            return (actual_result, next_tasks)

        return wrapper

    def _create_initial_tasks_wrapped(
        self,
        upstream_inputs: Dict[str, List],
        failed_parents: Dict[str, Set[str]],
        *args,
        **kwargs,
    ) -> List:
        """
        Create initial tasks with wrapper callables (for wrapper mode).

        Args:
            upstream_inputs: Shared dict for collecting multi-parent inputs
            failed_parents: Shared dict for tracking failed parent nodes
            *args: Arguments to pass to start nodes
            **kwargs: Keyword arguments to pass to start nodes

        Returns:
            List of Task objects for start nodes
        """
        from rankevolve.src.utils.mp_utils.task import Task

        tasks = []
        for node in self.start_nodes:
            wrapper = self._create_wrapper_callable(
                node, upstream_inputs, failed_parents
            )
            task = Task(
                callable=wrapper,
                task_id=node.name,
                args=args,
                kwargs=kwargs,
                name=node.name,
            )
            tasks.append(task)
        return tasks

    def _create_router(self) -> Callable:
        """
        Create router for multi-processing mode.

        The router runs in the MAIN PROCESS and has access to:
        - Graph structure (node_map)
        - Shared upstream_inputs dict for multi-parent handling
        - Shared failed_parents dict for tracking parent failures (on_error='skip')
        - TaskState.input_args/input_kwargs for NoPassDown self-edges
        - task_to_node mapping for safe task_id → node_name resolution

        This solves the pickling problem - closures stay in main process,
        only raw functions cross the process boundary.

        Returns:
            Router callback that receives (task_id, result, task_state) -> List[Task]
        """
        from rankevolve.src.utils.mp_utils.task import Task, TaskState, TaskStatus

        node_map = {n.name: n for n in self._all_nodes()}
        upstream_inputs: Dict[str, List] = {}  # Lives in main process
        failed_parents: Dict[str, Set[str]] = {}  # Lives in main process
        task_to_node: Dict[str, str] = {}  # task_id -> node_name mapping

        def router(task_id: str, result: Any, task_state: TaskState) -> List:
            # Extract node name from task_id using "::" delimiter
            # Format: "node_name::uuid" (e.g., "my_node::abc123")
            node_name = task_to_node.get(task_id) or task_id.rsplit("::", 1)[0]
            node = node_map[node_name]

            # ============================================================
            # HANDLE FAILURE FIRST (before _handle_next_nodes_selector)
            # ============================================================
            if task_state.status == TaskStatus.FAILED:
                next_tasks = []

                # Track this parent as failed for all its downstream nodes
                for downstream_node in node.next or []:
                    if downstream_node is node:
                        continue  # Skip self-edge - failed node won't loop

                    dn_name = downstream_node.name
                    num_parents = len(
                        [
                            p
                            for p in (downstream_node.previous or [])
                            if p is not downstream_node
                        ]
                    )

                    # Track this parent as failed
                    if dn_name not in failed_parents:
                        failed_parents[dn_name] = set()
                    failed_parents[dn_name].add(node.name)

                    # Check if all parents are now accounted for (success OR failure)
                    successful = len(upstream_inputs.get(dn_name, []))
                    failed = len(failed_parents.get(dn_name, set()))

                    if successful + failed >= num_parents:
                        if successful > 0:
                            # At least one parent succeeded - run with partial inputs
                            merged_args, merged_kwargs = (
                                downstream_node._merge_upstream_inputs(
                                    upstream_inputs[dn_name]
                                )
                            )
                            new_task_id = f"{dn_name}::{uuid.uuid4().hex[:8]}"
                            task_to_node[new_task_id] = dn_name
                            task = Task(
                                callable=downstream_node.value,
                                args=merged_args,
                                kwargs=merged_kwargs,
                                task_id=new_task_id,
                            )
                            next_tasks.append(task)
                        # else: All parents failed - skip downstream entirely

                        # Clear for next wave
                        upstream_inputs[dn_name] = []
                        failed_parents[dn_name] = set()

                return next_tasks  # May be empty if no downstream ready yet

            # ============================================================
            # NORMAL SUCCESS PATH
            # ============================================================

            # Handle NextNodesSelector
            include_self, include_others, actual_result = (
                node._handle_next_nodes_selector(result)
            )

            # Get downstream nodes
            downstream = node._select_downstream_nodes(include_others, include_self)

            # Build next tasks with multi-parent handling
            next_tasks = []
            for downstream_node in downstream:
                if downstream_node is node:
                    # SELF-EDGE: Use input_args from TaskState for NoPassDown mode
                    if node.result_pass_down_mode == ResultPassDownMode.NoPassDown:
                        self_args = task_state.input_args
                        self_kwargs = task_state.input_kwargs
                    else:
                        self_args, self_kwargs = node._get_args_for_downstream(
                            actual_result,
                            task_state.input_args,
                            task_state.input_kwargs,
                        )

                    new_task_id = f"{node.name}::selfloop::{uuid.uuid4().hex[:8]}"
                    task_to_node[new_task_id] = node.name
                    task = Task(
                        callable=node.value,  # Raw function - same node!
                        args=self_args,
                        kwargs=self_kwargs,
                        task_id=new_task_id,
                    )
                    next_tasks.append(task)
                else:
                    # Regular downstream node
                    num_parents = len(
                        [
                            p
                            for p in (downstream_node.previous or [])
                            if p is not downstream_node
                        ]
                    )
                    nargs, nkwargs = node._get_args_for_downstream(
                        actual_result, task_state.input_args, task_state.input_kwargs
                    )

                    if num_parents <= 1:
                        # Single parent - create task immediately
                        new_task_id = f"{downstream_node.name}::{uuid.uuid4().hex[:8]}"
                        task_to_node[new_task_id] = downstream_node.name
                        task = Task(
                            callable=downstream_node.value,  # Raw function!
                            args=nargs,
                            kwargs=nkwargs,
                            task_id=new_task_id,
                        )
                        next_tasks.append(task)
                    else:
                        # Multi-parent - collect input and check if all parents done
                        downstream_name = downstream_node.name
                        if downstream_name not in upstream_inputs:
                            upstream_inputs[downstream_name] = []

                        upstream_inputs[downstream_name].append((nargs, nkwargs))

                        # Check if all parents accounted for (success + failure)
                        successful = len(upstream_inputs[downstream_name])
                        failed = len(failed_parents.get(downstream_name, set()))

                        if successful + failed >= num_parents:
                            # All parents accounted for - merge inputs and create task
                            merged_args, merged_kwargs = (
                                downstream_node._merge_upstream_inputs(
                                    upstream_inputs[downstream_name]
                                )
                            )

                            # Clear for potential re-execution (next wave)
                            upstream_inputs[downstream_name] = []
                            if downstream_name in failed_parents:
                                failed_parents[downstream_name] = set()

                            new_task_id = f"{downstream_name}::{uuid.uuid4().hex[:8]}"
                            task_to_node[new_task_id] = downstream_name
                            task = Task(
                                callable=downstream_node.value,
                                args=merged_args,
                                kwargs=merged_kwargs,
                                task_id=new_task_id,
                            )
                            next_tasks.append(task)
                        else:
                            # Waiting for other parents - mark as "not a leaf"
                            # by adding None marker (run_async will filter it out)
                            if None not in next_tasks:
                                next_tasks.append(None)

            return next_tasks

        return router

    def _create_initial_tasks_raw(self, *args, **kwargs) -> List:
        """
        Create initial tasks with raw node.value (for router mode).

        Used with executor.run_async(router=...) for multi-processing.
        Tasks use raw functions that must be picklable.

        Args:
            *args: Arguments to pass to start nodes
            **kwargs: Keyword arguments to pass to start nodes

        Returns:
            List of Task objects for start nodes
        """
        from rankevolve.src.utils.mp_utils.task import Task

        return [
            Task(
                callable=node.value,  # Raw function - must be picklable!
                task_id=node.name,
                args=args,
                kwargs=kwargs,
                name=node.name,
            )
            for node in self.start_nodes
        ]

    def _run(self, *args, **kwargs):
        """
        Executes the graph in a depth-first manner, for each node in the `start_nodes`, and managing
        execution/saving/resumption of results as needed.

        If an executor is configured, delegates to executor.run_async() instead of
        recursive execution. Uses wrapper mode for thread-based executors and
        router mode for process-based executors.

        Args:
            *args: Positional arguments to be passed to the start nodes.
            **kwargs: Keyword arguments to be passed to the start nodes.

        Returns:
            Processed results after running the graph and applying the `post_process` method.
        """
        # =====================================================================
        # Delegate to async path if use_async is enabled
        # =====================================================================
        if self.use_async:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop is not None and loop.is_running():
                # Already inside an event loop (e.g. Jupyter, nested async) —
                # create a new thread to run the async path to avoid deadlock.
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor(1) as pool:
                    return pool.submit(
                        asyncio.run, self._arun(*args, **kwargs)
                    ).result()
            else:
                return asyncio.run(self._arun(*args, **kwargs))

        # =====================================================================
        # Phase 4: Delegate to executor if configured
        # =====================================================================
        if self.executor is not None:
            # Always use router mode because:
            # - ThreadQueueService uses multiprocessing.Manager which requires pickling
            # - Router mode uses raw node.value functions (must be picklable)
            # - Router runs in main process, so it can have closures/graph references
            #
            # Note: Wrapper mode (_create_wrapper_callable) creates closures which
            # can't be pickled. It would only work with a queue service that uses
            # regular queue.Queue (not multiprocessing-based).
            router = self._create_router()
            tasks = self._create_initial_tasks_raw(*args, **kwargs)
            result = self.executor.run_async(tasks, router=router)

            # Apply post_process to executor result
            if isinstance(result, tuple):
                return self.post_process(list(result), *args, **kwargs)
            else:
                return self.post_process([result], *args, **kwargs)

        # =====================================================================
        # Original recursive execution (when executor is None)
        # =====================================================================

        # Clear all node queues to ensure fresh execution state
        # This prevents stale items from previous runs (e.g., after Terminate) from corrupting this run
        self._clear_all_node_queues()

        output = []
        is_loaded_from_saved_results = []
        stop_flag = WorkGraphStopFlags.Continue
        for node in self.start_nodes:  # type: WorkGraphNode
            # If resuming and result already exists, load it and skip execution
            is_loaded_from_saved_result, result = node.load_result(*args, **kwargs)
            is_loaded_from_saved_results.append(is_loaded_from_saved_result)

            if not is_loaded_from_saved_result:
                try:
                    # Run the node if no saved result was loaded.
                    # NOTE: every node is an entry point to the graph,
                    #       and it will automatically execute its downstream nodes layer by layer
                    if stop_flag == WorkGraphStopFlags.Continue:
                        stop_flag = node.run(*args, **kwargs, _output=output)
                    elif stop_flag == WorkGraphStopFlags.AbstainResult:
                        node.run(stop_flag)
                    elif stop_flag == WorkGraphStopFlags.Terminate:
                        break
                except Exception as err:
                    if self.enable_result_save == StepResultSaveOptions.OnError:
                        # On error, if OnError saving is enabled, save partial results
                        for (
                            prev_result,
                            prev_is_loaded_from_saved_result,
                            prev_node,
                        ) in zip(
                            output, is_loaded_from_saved_results, self.start_nodes
                        ):  # type: WorkGraphNode
                            if (
                                prev_node.enable_result_save
                                == StepResultSaveOptions.OnError
                                and not prev_is_loaded_from_saved_result
                            ):
                                prev_node._save_result(
                                    prev_result,
                                    output_path=prev_node._get_result_path(
                                        prev_node.name, *args, **kwargs
                                    ),
                                )
                    raise err

        result = self.post_process(output, *args, **kwargs)
        if (
            self.enable_result_save is True
            or self.enable_result_save == StepResultSaveOptions.Always
        ):
            # If Always saving is enabled, save the result of this node
            result_path = self._get_result_path(self.name, *args, **kwargs)
            self._save_result(result, output_path=result_path)
        return result

    async def _arun(self, *args, **kwargs):
        """Async implementation mirroring _run() for WorkGraph.

        Uses asyncio.gather() for concurrent start node execution,
        asyncio.Event for Terminate flag propagation, and asyncio.Semaphore
        for max_concurrency limiting.

        Known concurrency semantic differences from _run():
        - AbstainResult between start nodes: all start nodes launch concurrently,
          so B never sees A's AbstainResult.
        - Error-path side effects: with return_exceptions=True, all start nodes
          run to completion regardless of failures.
        - Executor is ignored in async path (uses native asyncio concurrency).
        """
        # Clear all node queues for fresh execution
        self._clear_all_node_queues()

        _EMPTY = object()  # Sentinel — distinguishes "no result" from "result is None"

        # Pre-allocate with sentinel for deterministic ordering
        output = [_EMPTY] * len(self.start_nodes)
        node_info = [None] * len(self.start_nodes)  # [(node, is_loaded), ...]

        terminate_event = asyncio.Event()
        semaphore = (
            asyncio.Semaphore(self.max_concurrency) if self.max_concurrency else None
        )

        async def _run_start_node(idx, node):
            is_loaded, result = node.load_result(*args, **kwargs)
            node_info[idx] = (node, is_loaded)
            if is_loaded:
                # Match sync behavior: loaded results are NOT added to output
                return WorkGraphStopFlags.Continue
            if terminate_event.is_set():
                return WorkGraphStopFlags.Continue
            if semaphore:
                async with semaphore:
                    flag = await node.arun(
                        *args, **kwargs, _output_idx=(output, idx), _semaphore=semaphore
                    )
            else:
                flag = await node.arun(*args, **kwargs, _output_idx=(output, idx))
            if flag == WorkGraphStopFlags.Terminate:
                terminate_event.set()
            return flag

        tasks = [_run_start_node(i, node) for i, node in enumerate(self.start_nodes)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Post-filter: separate successes from exceptions
        exceptions = [
            (i, r) for i, r in enumerate(results) if isinstance(r, BaseException)
        ]

        if exceptions:
            if self.enable_result_save == StepResultSaveOptions.OnError:
                # Per-node save — mirrors sync _run() exactly
                for info, result_val in zip(node_info, output):
                    if info is None:
                        continue
                    node, is_loaded = info
                    if (
                        node.enable_result_save == StepResultSaveOptions.OnError
                        and not is_loaded
                        and result_val is not _EMPTY
                    ):
                        node._save_result(
                            result_val,
                            output_path=node._get_result_path(
                                node.name, *args, **kwargs
                            ),
                        )
            raise exceptions[0][1]

        # Filter out sentinel slots (loaded or skipped nodes)
        output = [r for r in output if r is not _EMPTY]

        # Post-process: call _post_process and _optional_post_process separately
        # via call_maybe_async (NOT through the chaining post_process() method)
        _result = await call_maybe_async(self._post_process, output, *args, **kwargs)
        if _result is not None:
            output = _result
        if self.enable_optional_post_process:
            _result = await call_maybe_async(
                self._optional_post_process, output, *args, **kwargs
            )
            if _result is not None:
                output = _result

        result = output

        # Always-save: same sync save as _run()
        if (
            self.enable_result_save is True
            or self.enable_result_save == StepResultSaveOptions.Always
        ):
            result_path = self._get_result_path(self.name, *args, **kwargs)
            self._save_result(result, output_path=result_path)

        return result
