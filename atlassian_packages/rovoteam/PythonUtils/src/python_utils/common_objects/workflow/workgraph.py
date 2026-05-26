import asyncio
import os
import tempfile
import uuid
from queue import Queue
from typing import Any, Callable, Dict, List, Optional, Set, TYPE_CHECKING, Union

from attr import attrs, attrib

if TYPE_CHECKING:
    from python_utils.mp_utils.queued_executor import QueuedExecutorBase

from python_utils.algorithms.graph.dag import DirectedAcyclicGraph
from python_utils.algorithms.graph.node import Node
from python_utils.common_objects.debuggable import Debuggable
from python_utils.common_objects.workflow.common.result_pass_down_mode import ResultPassDownMode
from python_utils.common_objects.workflow.common.step_result_save_options import (
    StepResultSaveOptions,
    ResumeMode,
)
from python_utils.common_objects.workflow.common.worknode_base import (
    WorkNodeBase, WorkGraphStopFlags, NextNodesSelector
)
from python_utils.common_objects.workflow.common.expansion import GraphExpansionResult, SubgraphSpec
from python_utils.common_objects.workflow.common.exceptions import (
    ExpansionConfigError, ExpansionLimitExceeded, ExpansionReplayError
)
from python_utils.common_utils import flatten_iter, len_, get_relevant_named_args, get_relevant_args
from python_utils.common_utils.attr_helper import getattr_or_new
from python_utils.common_utils.async_utils import call_maybe_async, async_execute_with_retry


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
        result_pass_down_mode (Union[str, python_utils.common_objects.workflow.common.result_pass_down_mode.ResultPassDownMode, Callable, Any]):
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
    # Optional group name for per-group concurrency limiting in WorkGraph.
    # Nodes in the same group share a semaphore when group_max_concurrency is set.
    group: Optional[str] = attrib(default=None, kw_only=True)
    # When True, the wrapped worker manages its own resume/checkpointing (e.g.,
    # PTI, nested BTA). Used by ResumeMode.SkipResumable and
    # StepResultSaveOptions.SkipResumable to decide whether to skip node-level
    # save/load and let the worker handle it internally.
    worker_manages_resume: bool = attrib(default=False, kw_only=True)
    # Optional callback for graph visualization — emits NodeStatusEvent on RUNNING/COMPLETED/ERROR.
    # Set via WorkGraph.set_graph_event_callback(). Must be an async coroutine function when used
    # in _arun() (async path). In _run() (sync path), async callbacks are skipped to avoid
    # unawaited coroutine leaks. BTA always uses _arun() (use_async=True).
    _graph_event_callback: Optional[Callable] = attrib(default=None, repr=False, kw_only=True)
    min_repeat_wait: float = attrib(default=0, kw_only=True)
    max_repeat_wait: float = attrib(default=0, kw_only=True)
    retry_on_exceptions: Optional[List[type]] = attrib(default=None, kw_only=True)
    output_validator: Optional[Callable[..., bool]] = attrib(default=None, kw_only=True)

    # Dynamic expansion attributes (Task 4.1)
    _expansion_depth = attrib(type=int, default=0, init=False, repr=False)
    _max_expansion_depth = attrib(type=int, default=0, init=False, repr=False)
    _max_total_nodes = attrib(type=int, default=200, init=False, repr=False)
    _expansion_applied = attrib(type=bool, default=False, init=False, repr=False)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if isinstance(self.value, Debuggable):
            self.value.set_parent_debuggable(self)

    def _should_save_result(self) -> bool:
        """Check if this node's result should be saved after execution.

        Handles ``StepResultSaveOptions.SkipResumable``: saves only when the
        wrapped worker does NOT manage its own checkpointing.
        Returns False if ``_get_result_path`` is not implemented (no checkpoint
        directory configured).
        """
        save = self.enable_result_save
        if save is True or save == StepResultSaveOptions.Always:
            return True
        if save == StepResultSaveOptions.SkipResumable:
            if self.worker_manages_resume:
                return False
            try:
                self._get_result_path(self.name)
                return True
            except NotImplementedError:
                return False
        return False

    def _post_adding_next_process(self, next_node):
        from python_utils.common_objects.debuggable import Debuggable
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
        return kwargs.get('fallback_result', self.fallback_result)

    def _get_value_reference(self) -> Optional[str]:
        """Get serializable reference for callable value.
        
        Returns:
            A string reference in the format 'module.name' if the callable has
            __module__ and __name__ attributes, otherwise None.
        """
        if self.value is None:
            return None
        if hasattr(self.value, '__module__') and hasattr(self.value, '__name__'):
            return f"{self.value.__module__}.{self.value.__name__}"
        return None  # Non-serializable callable

    def to_serializable_obj(
        self, 
        mode: str = 'auto',
        _output_format: Optional[str] = None
    ) -> Dict[str, Any]:
        """Serialize WorkGraphNode to dict.
        
        Serializes node configuration including name, connections, and settings.
        Callable values are stored as references when possible.
        Dynamically added nodes (expansion_depth > 0) are marked with
        ``"expanded": True`` and their ``expansion_id`` if available.
        
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
            if hasattr(self.result_pass_down_mode, '__name__'):
                result_pass_down_mode_str = f"callable:{self.result_pass_down_mode.__module__}.{self.result_pass_down_mode.__name__}"
            else:
                result_pass_down_mode_str = None  # Non-serializable callable
        
        obj = {
            '_type': type(self).__name__,
            '_module': type(self).__module__,
            'name': self.name,
            'value_ref': self._get_value_reference(),
            'next_names': [n.name for n in (self.next or [])],
            'previous_names': [n.name for n in (self.previous or [])],
            'config': {
                'max_repeat': self.max_repeat,
                'min_repeat_wait': self.min_repeat_wait,
                'max_repeat_wait': self.max_repeat_wait,
                'enable_result_save': (
                    self.enable_result_save.value 
                    if isinstance(self.enable_result_save, StepResultSaveOptions) 
                    else self.enable_result_save
                ),
                'result_pass_down_mode': result_pass_down_mode_str,
                'pass_abstain_result_flag_downstream': self.pass_abstain_result_flag_downstream,
                'remove_abstain_result_flag_from_upstream_input': self.remove_abstain_result_flag_from_upstream_input,
            }
        }

        # Mark dynamically added nodes (expansion_depth > 0)
        if self._expansion_depth > 0:
            obj['expanded'] = True
            obj['expansion_depth'] = self._expansion_depth

        return obj

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

    def _select_downstream_nodes(
        self,
        include_others,
        include_self: bool
    ) -> list:
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
            elif isinstance(include_others, set) and getattr(node, 'name', None) in include_others:
                nodes.append(node)

        return nodes

    # =========================================================================
    # Dynamic Expansion Methods (Tasks 4.2–4.5)
    # =========================================================================

    def _validate_seed_factory(self, fn):
        """Validate that *reconstruct_from_seed* is importable.

        Performs explicit ``hasattr(fn, '__qualname__')`` check before
        accessing ``fn.__qualname__``, to handle ``functools.partial``
        objects cleanly.

        Raises:
            ExpansionConfigError: for lambdas, closures, or objects
                missing ``__module__``/``__qualname__``.
        """
        if not hasattr(fn, '__qualname__'):
            raise ExpansionConfigError(
                f"reconstruct_from_seed {fn!r} has no __qualname__ attribute. "
                "It must be a module-level function (not a functools.partial, "
                "lambda, or closure)."
            )
        if not hasattr(fn, '__module__'):
            raise ExpansionConfigError(
                f"reconstruct_from_seed {fn!r} has no __module__ attribute. "
                "It must be a module-level function."
            )
        qualname = fn.__qualname__
        if '<lambda>' in qualname:
            raise ExpansionConfigError(
                f"reconstruct_from_seed must not be a lambda (got qualname={qualname!r}). "
                "Use a named module-level function instead."
            )
        if '<locals>' in qualname:
            raise ExpansionConfigError(
                f"reconstruct_from_seed must not be a closure (got qualname={qualname!r}). "
                "Use a named module-level function instead."
            )

    def _collect_all_graph_names(self):
        """Collect names of all nodes reachable via previous AND next links.

        BFS traversal starting from self, walking both previous and next edges.

        Returns:
            set: Set of node names reachable from self.
        """
        visited = set()
        queue = [self]
        names = set()
        while queue:
            node = queue.pop(0)
            node_id = id(node)
            if node_id in visited:
                continue
            visited.add(node_id)
            if node.name is not None:
                names.add(node.name)
            for neighbor in (node.next or []):
                if id(neighbor) not in visited:
                    queue.append(neighbor)
            for neighbor in (node.previous or []):
                if id(neighbor) not in visited:
                    queue.append(neighbor)
        return names

    def _validate_no_cycles(self, new_nodes):
        """DFS cycle detection on the subgraph's nodes, excluding self-loops.

        Walks ``next`` edges from each node in *new_nodes*. A back-edge to an
        ancestor in the current DFS path (that is not a self-loop) indicates a
        cycle.

        Args:
            new_nodes: List of WorkGraphNode instances to check.

        Raises:
            ValueError: If a cycle is detected among the new nodes.
        """
        node_ids = {id(n) for n in new_nodes}

        # States: 0 = unvisited, 1 = in-progress, 2 = done
        state = {id(n): 0 for n in new_nodes}

        def dfs(node):
            state[id(node)] = 1  # in-progress
            for child in (node.next or []):
                if child is node:
                    continue  # skip self-loops
                child_id = id(child)
                if child_id not in node_ids:
                    continue  # outside the subgraph
                if state[child_id] == 1:
                    raise ValueError(
                        f"Cycle detected in subgraph: node '{node.name}' -> '{child.name}' "
                        f"forms a back-edge."
                    )
                if state[child_id] == 0:
                    dfs(child)
            state[id(node)] = 2  # done

        for node in new_nodes:
            if state[id(node)] == 0:
                dfs(node)

    def _validate_no_cross_boundary_cycles(self, subgraph_nodes):
        """Post-wiring cycle check (S2 fix).

        After subgraph attachment (including insert mode), verify that no path
        from any subgraph leaf's downstream reaches back to the expanding node.
        Also verify that no path from the original downstream children reaches
        back to any node in the expanded subgraph, covering cycles that span
        the rewired topology.

        Args:
            subgraph_nodes: List of WorkGraphNode instances in the subgraph.

        Raises:
            ValueError: If a cross-boundary cycle is detected.
        """
        sg_node_ids = {id(n) for n in subgraph_nodes}
        expanding_node_id = id(self)

        # Find subgraph leaf nodes (nodes with no next within subgraph, excluding self-loops)
        leaf_nodes = []
        for sg_node in subgraph_nodes:
            has_internal_next = any(
                id(n) in sg_node_ids
                for n in (sg_node.next or [])
                if n is not sg_node
            )
            if not has_internal_next:
                leaf_nodes.append(sg_node)

        # Check 1: DFS from subgraph leaf nodes' downstream — no path should
        # reach back to the expanding node (excluding self-loops)
        for leaf in leaf_nodes:
            for downstream in (leaf.next or []):
                if downstream is leaf:
                    continue  # skip self-loops
                if id(downstream) in sg_node_ids:
                    continue  # still within subgraph
                # DFS from downstream, check if we reach expanding node
                visited = set()
                stack = [downstream]
                while stack:
                    node = stack.pop()
                    nid = id(node)
                    if nid == expanding_node_id:
                        raise ValueError(
                            f"Cross-boundary cycle detected: path from subgraph leaf "
                            f"'{leaf.name}' downstream reaches back to expanding node "
                            f"'{self.name}'."
                        )
                    if nid in visited:
                        continue
                    visited.add(nid)
                    for child in (node.next or []):
                        if child is node:
                            continue  # skip self-loops
                        if id(child) not in visited:
                            stack.append(child)

        # Check 2: DFS from original downstream children (non-subgraph next of
        # subgraph leaves) — no path should reach back to any subgraph node
        for leaf in leaf_nodes:
            for downstream in (leaf.next or []):
                if downstream is leaf:
                    continue
                if id(downstream) in sg_node_ids:
                    continue
                visited = set()
                stack = [downstream]
                while stack:
                    node = stack.pop()
                    nid = id(node)
                    if nid in sg_node_ids:
                        raise ValueError(
                            f"Cross-boundary cycle detected: path from downstream "
                            f"of subgraph leaf '{leaf.name}' reaches back to "
                            f"subgraph node '{node.name}'."
                        )
                    if nid in visited:
                        continue
                    visited.add(nid)
                    for child in (node.next or []):
                        if child is node:
                            continue
                        if id(child) not in visited:
                            stack.append(child)

    def _propagate_settings_to_subgraph(self, nodes):
        """Propagate execution settings and expansion depth to subgraph nodes.

        Propagates:
        - enable_result_save
        - resume_with_saved_results
        - checkpoint_mode (if present)
        - _graph_event_callback
        - _max_expansion_depth
        - _max_total_nodes
        - _expansion_depth (set to self._expansion_depth + 1)

        Args:
            nodes: List of WorkGraphNode instances in the subgraph.
        """
        child_depth = self._expansion_depth + 1
        for node in nodes:
            node.enable_result_save = self.enable_result_save
            node.resume_with_saved_results = self.resume_with_saved_results
            if hasattr(self, 'checkpoint_mode'):
                node.checkpoint_mode = self.checkpoint_mode
            node._graph_event_callback = self._graph_event_callback
            node._max_expansion_depth = self._max_expansion_depth
            node._max_total_nodes = self._max_total_nodes
            node._expansion_depth = child_depth

    def _handle_insert_mode(self, expansion_result):
        """Rewire topology for non-leaf insert mode (Req 33).

        1. Save original downstream children (excluding self-edge)
        2. Detach expanding node from original downstream (remove from self.next,
           remove self from child.previous)
        3. Attach subgraph entry nodes as new downstream via self.add_next()
        4. Find subgraph leaf nodes (nodes with no next within subgraph,
           excluding self-loops)
        5. Wire subgraph leaf nodes → original downstream children via leaf.add_next()
        """
        subgraph = expansion_result.subgraph

        # 1. Save original downstream children (excluding self-edge)
        original_downstream = [n for n in (self.next or []) if n is not self]

        # 2. Detach expanding node from original downstream
        for child in original_downstream:
            if child in self.next:
                self.next.remove(child)
            if self in (child.previous or []):
                child.previous.remove(self)

        # 3. Attach subgraph entry nodes as new downstream
        for entry_node in subgraph.entry_nodes:
            self.add_next(entry_node)

        # 4. Find subgraph leaf nodes (nodes with no next within subgraph,
        #    excluding self-loops)
        sg_node_ids = {id(n) for n in subgraph.nodes}
        leaf_nodes = []
        for sg_node in subgraph.nodes:
            has_internal_next = any(
                id(n) in sg_node_ids
                for n in (sg_node.next or [])
                if n is not sg_node
            )
            if not has_internal_next:
                leaf_nodes.append(sg_node)

        # 5. Wire subgraph leaf nodes → original downstream children
        for leaf in leaf_nodes:
            for child in original_downstream:
                leaf.add_next(child)

    def _handle_graph_expansion(self, expansion_result, *args, **kwargs):
        """Process a GraphExpansionResult: validate, attach subgraph, record.

        Handles:
        - Req 28: Self-loop detection — if _expansion_applied, skip re-expansion
        - Req 30: worker_manages_resume check → ExpansionConfigError
        - Req 25.4: Seed factory validation → ExpansionConfigError
        - Empty entry_nodes → no-op with warning
        - Expansion depth check → log warning and return result
        - Total nodes check → raise ExpansionLimitExceeded
        - Name uniqueness check → raise ValueError
        - Cycle detection → raise ValueError
        - Req 14.5: _get_result_path must be implemented
        - Req 14.1: Persist expansion record BEFORE mutating topology
        - Req 33: Insert mode for non-leaf nodes
        - Leaf node: add entry_nodes to self.next
        - Propagate settings and expansion depth to subgraph nodes
        - Set _expansion_applied = True

        Returns:
            The unwrapped result from expansion_result.result.
        """
        import logging
        logger = logging.getLogger(__name__)

        # Req 28: If already expanded (self-loop scenario), skip re-expansion
        if self._expansion_applied:
            logger.debug(
                "Node '%s': _expansion_applied is True, skipping re-expansion.",
                self.name,
            )
            return expansion_result.result

        # Req 30: Forbidden combination — worker_manages_resume + expansion
        if self.worker_manages_resume:
            raise ExpansionConfigError(
                f"Node '{self.name}' has worker_manages_resume=True and returned "
                "GraphExpansionResult. This combination is forbidden because the "
                "worker's internal checkpointing conflicts with expansion topology "
                "mutations."
            )

        # Req 25.4: Validate seed factory if provided
        if expansion_result.reconstruct_from_seed is not None:
            self._validate_seed_factory(expansion_result.reconstruct_from_seed)

        subgraph = expansion_result.subgraph
        entry_nodes = subgraph.entry_nodes

        # Handle empty entry_nodes as no-op
        if not entry_nodes:
            logger.warning(
                "Node '%s': GraphExpansionResult has empty entry_nodes. "
                "Treating as no-op.",
                self.name,
            )
            return expansion_result.result

        # Check expansion depth: _expansion_depth >= _max_expansion_depth → skip
        if self._expansion_depth >= self._max_expansion_depth:
            logger.warning(
                "Node '%s': expansion depth %d >= max_expansion_depth %d. "
                "Skipping expansion.",
                self.name,
                self._expansion_depth,
                self._max_expansion_depth,
            )
            return expansion_result.result

        # Check total nodes via _collect_all_graph_names
        existing_names = self._collect_all_graph_names()
        new_node_count = len(subgraph.nodes)
        total_after = len(existing_names) + new_node_count
        if total_after > self._max_total_nodes:
            raise ExpansionLimitExceeded(
                f"Attaching subgraph ({new_node_count} nodes) to node '{self.name}' "
                f"would result in {total_after} total nodes, exceeding "
                f"max_total_nodes={self._max_total_nodes}."
            )

        # Check name uniqueness
        new_names = {n.name for n in subgraph.nodes}
        conflicts = existing_names & new_names
        if conflicts:
            raise ValueError(
                f"Subgraph node names conflict with existing graph nodes: "
                f"{sorted(conflicts)}"
            )

        # Validate no cycles within the subgraph
        self._validate_no_cycles(subgraph.nodes)

        # Req 14.5: Check _get_result_path is implemented
        try:
            self._get_result_path("__test__")
        except NotImplementedError:
            raise ExpansionConfigError(
                f"Node '{self.name}' returned GraphExpansionResult but "
                "_get_result_path is not implemented. Expansion records "
                "require a result path for persistence."
            )

        # Req 14.1: Persist expansion record BEFORE mutating topology
        record_data = {
            'expanding_node': self.name,
            'expansion_id': expansion_result.expansion_id,
            'subgraph': subgraph.to_serializable_obj(),
        }
        if expansion_result.seed is not None:
            record_data['seed'] = expansion_result.seed
        if expansion_result.reconstruct_from_seed is not None:
            record_data['factory_module'] = expansion_result.reconstruct_from_seed.__module__
            record_data['factory_qualname'] = expansion_result.reconstruct_from_seed.__qualname__

        self._save_result(
            record_data,
            output_path=self._resolve_result_path(
                f"__graph_expansion__{self.name}", *args, **kwargs
            ),
        )

        # Determine if leaf or non-leaf
        non_self_next = [n for n in (self.next or []) if n is not self]
        if non_self_next:
            # Non-leaf → insert mode
            self._handle_insert_mode(expansion_result)
        else:
            # Leaf → attach entry_nodes directly
            for entry_node in entry_nodes:
                self.add_next(entry_node)

        # Post-wiring cross-boundary cycle check (S2 fix)
        self._validate_no_cross_boundary_cycles(subgraph.nodes)

        # Propagate settings and expansion depth to subgraph nodes
        self._propagate_settings_to_subgraph(subgraph.nodes)

        # Mark expansion as applied (Req 28 — self-loop won't re-expand)
        self._expansion_applied = True

        return expansion_result.result

    def _run(self, *args, **kwargs):
        self._expansion_applied = False
        stop_flag = WorkGraphStopFlags.Continue

        # region Process a special scenario when input is the AbstainResult flag
        # This flag must be passed down so
        is_input_single_stop_flag = WorkGraphStopFlags.is_input_single_stop_flag(*args, **kwargs)
        if is_input_single_stop_flag:
            if not self.pass_abstain_result_flag_downstream:
                raise ValueError(
                    "`pass_abstain_result_flag_downstream` is set False, "
                    "but downstream nodes still receive AbstainResult flag"
                )
            stop_flag = args[0]
            if stop_flag != WorkGraphStopFlags.AbstainResult:
                raise ValueError(f"Only AbstainResult flag allowed to pass downstream; got '{stop_flag}'")
        # endregion

        # region Track execution depth for debugging
        # _graph_depth: incremented when calling downstream nodes via node.run()
        #               This tracks how deep we are in the graph traversal (parent → child → grandchild)
        # Note: Self-loop iteration is tracked separately via iteration_count (iterative, not recursive)
        graph_depth = kwargs.pop('_graph_depth', 0)
        # endregion

        # region If there are multiple previous nodes, we need to collect all their outputs before proceeding.
        # NOTE: Exclude self from parent count - self-edges shouldn't block initial execution
        # A self-edge (monitor.add_next(monitor)) adds self to both next AND previous,
        # but the self-loop only provides input AFTER the node executes, not before.
        # Self-loop iterations bypass this entirely via the iterative while loop (no recursive node.run()).
        num_real_parents = sum(1 for p in (self.previous or []) if p is not self)
        if num_real_parents > 1:
            queue: Queue = getattr_or_new(self, '_queue', default_factory=Queue)
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

        # Warn if self-loop node has result saving enabled - this breaks self-loop on resume
        if has_self_edge and self._should_save_result():
            self.log_warning(
                {
                    'node_name': self.name,
                    'enable_result_save': self.enable_result_save,
                },
                'SelfLoopWithResultSave',
                message=(
                    f"Node '{self.name}' has a self-edge (self-loop) but enable_result_save is enabled. "
                    "If results are loaded from saved state, the self-loop will not continue because "
                    "include_self won't be set. Consider setting enable_result_save=False for self-loop nodes."
                )
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

        if (
            has_self_edge
            and self.resume_with_saved_results
            and self._should_save_result()
        ):
            loop_state = self._load_loop_state(resolve_args=args, resolve_kwargs=kwargs)
            if loop_state is not None and not loop_state["completed"]:
                last_iter = loop_state["last_completed_iteration"]
                self_loop_iteration = last_iter
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
                    'node_name': self.name,
                    'graph_depth': graph_depth,
                    'self_loop_iteration': self_loop_iteration,
                    'is_self_loop': has_self_edge and self_loop_iteration > 1,
                },
                'NodeExecution'
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
                            **kwargs
                        )

                        # Use execute_with_retry to support repeat/retry functionality
                        from python_utils.common_utils.function_helper import execute_with_retry
                        # Graph visualization: emit RUNNING status (sync path — skip async cb)
                        if self._graph_event_callback:
                            import inspect as _inspect
                            if not _inspect.iscoroutinefunction(self._graph_event_callback):
                                try:
                                    from agent_foundation.common.inferencers.graph_events import NodeStatusEvent, NodeStatus
                                    self._graph_event_callback(NodeStatusEvent(node_id=self.name, status=NodeStatus.RUNNING))
                                except Exception:
                                    pass
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
                            default_return_or_raise=self._get_fallback_result(*args, **kwargs),
                        )
                    except Exception as err:
                        import traceback
                        self.log_error(
                            {
                                'name': self.name,
                                'executor': self.value,
                                'args': args,
                                'kwargs': kwargs,
                                'exception_type': type(err).__name__,
                                'exception_message': str(err),
                                'traceback': traceback.format_exc()
                            },
                            'NodeExecutionFailed',
                        )

                        raise err

                    # Track whether stop_flag was already determined by expansion handling
                    _stop_flag_from_expansion = None
                    _expansion_include_self = None
                    _expansion_include_others = None

                    # Req 29: Stop-flag composition — detect (StopFlag, GraphExpansionResult) tuples
                    if (isinstance(result, tuple) and len(result) == 2
                            and isinstance(result[0], WorkGraphStopFlags)
                            and isinstance(result[1], GraphExpansionResult)):
                        _stop_flag_from_expansion = result[0]
                        expansion_result = result[1]
                        _expansion_include_self = expansion_result.include_self
                        _expansion_include_others = expansion_result.include_others
                        result = self._handle_graph_expansion(expansion_result, *args, **kwargs)
                    elif isinstance(result, GraphExpansionResult):
                        # Handle plain GraphExpansionResult before NextNodesSelector
                        _expansion_include_self = result.include_self
                        _expansion_include_others = result.include_others
                        result = self._handle_graph_expansion(result, *args, **kwargs)

                    # Handle NextNodesSelector return value
                    include_self, include_others, result = self._handle_next_nodes_selector(result)

                    # Req 23.3: GraphExpansionResult include_self/include_others take precedence
                    # Only override if GER explicitly set non-default values
                    if _expansion_include_self is not None and _expansion_include_self is not False:
                        include_self = _expansion_include_self
                    if _expansion_include_others is not None and _expansion_include_others is not True:
                        include_others = _expansion_include_others

                    # Stop-flag resolution: if expansion already determined the flag, use it;
                    # otherwise use the existing helper for non-expansion results.
                    if _stop_flag_from_expansion is not None:
                        stop_flag = _stop_flag_from_expansion
                    else:
                        stop_flag, result = WorkGraphStopFlags.separate_stop_flag_from_result(result)

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
                    if self._should_save_result():
                        result_path = self._get_result_path(self.name, *args, **kwargs)
                        self._save_result(result, result_path)

            # Propagate the result to downstream nodes if any.
            if self.next:
                if stop_flag == WorkGraphStopFlags.Continue:
                    nargs, nkwargs = self._get_args_for_downstream(result, args, kwargs)
                    # EXCLUDE SELF from downstream nodes - self-loop is handled via while loop
                    nodes_to_run = self._select_downstream_nodes(include_others, include_self=False)
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
                            *nargs, **nkwargs,
                            _output=downstream_results,
                            _graph_depth=graph_depth + 1
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

                downstream_results = [r for r in downstream_results if r is not _DS_EMPTY]
                if downstream_results:
                    result = self._merge_downstream_results(downstream_results)

                if (
                    has_self_edge
                    and not is_loaded_from_saved_result
                    and self._should_save_result()
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
            if include_self and has_self_edge and stop_flag == WorkGraphStopFlags.Continue:
                # Prepare args for next iteration based on result_pass_down_mode
                if self.result_pass_down_mode == ResultPassDownMode.NoPassDown:
                    args, kwargs = original_args, dict(original_kwargs)
                else:
                    args, kwargs = nargs, dict(nkwargs)
                # Reset for next iteration - we'll get fresh values from next execution
                include_self = False
                include_others = True

                if self._should_save_result():
                    self._save_loop_state(
                        self_loop_iteration,
                        completed=False,
                        resolve_args=args,
                        resolve_kwargs=kwargs,
                    )

                self.log_debug(
                    {
                        'node_name': self.name,
                        'graph_depth': graph_depth,
                        'completed_iteration': self_loop_iteration,
                        'next_iteration': self_loop_iteration + 1,
                    },
                    'SelfLoopContinue'
                )
                continue  # Loop back to re-execute this node (replaces recursive call)
            else:
                if has_self_edge and self_loop_iteration > 1:
                    self.log_debug(
                        {
                            'node_name': self.name,
                            'graph_depth': graph_depth,
                            'total_iterations': self_loop_iteration,
                            'exit_reason': 'include_self=False' if not include_self else f'stop_flag={stop_flag}',
                        },
                        'SelfLoopExit'
                    )
                if has_self_edge and self._should_save_result():
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
            return stop_flag, result  # pop `WorkGraphStopFlags.Terminate` to stop the entire graph

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
        self._expansion_applied = False
        stop_flag = WorkGraphStopFlags.Continue

        # region Process a special scenario when input is the AbstainResult flag
        is_input_single_stop_flag = WorkGraphStopFlags.is_input_single_stop_flag(*args, **kwargs)
        if is_input_single_stop_flag:
            if not self.pass_abstain_result_flag_downstream:
                raise ValueError(
                    "`pass_abstain_result_flag_downstream` is set False, "
                    "but downstream nodes still receive AbstainResult flag"
                )
            stop_flag = args[0]
            if stop_flag != WorkGraphStopFlags.AbstainResult:
                raise ValueError(f"Only AbstainResult flag allowed to pass downstream; got '{stop_flag}'")
        # endregion

        # region Track execution depth for debugging
        graph_depth = kwargs.pop('_graph_depth', 0)
        # endregion

        # Pop _semaphore early so it doesn't leak into get_relevant_args or node execution
        _semaphore_or_map = kwargs.pop('_semaphore', None)
        # Support per-group semaphores: if _semaphore is a dict, select by node.group
        if isinstance(_semaphore_or_map, dict):
            semaphore = _semaphore_or_map.get(self.group) or _semaphore_or_map.get(None)
            self.log_info(
                f"group={self.group!r}, dict_keys={list(_semaphore_or_map.keys())}, "
                f"selected_semaphore={id(semaphore) if semaphore else None}",
                "ConcurrencyDiag",
            )
        else:
            semaphore = _semaphore_or_map

        # region Multi-parent input collection using asyncio.Queue
        num_real_parents = sum(1 for p in (self.previous or []) if p is not self)
        if num_real_parents > 1:
            aqueue: asyncio.Queue = getattr_or_new(self, '_aqueue', default_factory=asyncio.Queue)
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

        # Warn if self-loop node has result saving enabled
        if has_self_edge and self._should_save_result():
            self.log_warning(
                {
                    'node_name': self.name,
                    'enable_result_save': self.enable_result_save,
                },
                'SelfLoopWithResultSave',
                message=(
                    f"Node '{self.name}' has a self-edge (self-loop) but enable_result_save is enabled. "
                    "If results are loaded from saved state, the self-loop will not continue because "
                    "include_self won't be set. Consider setting enable_result_save=False for self-loop nodes."
                )
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

        if (
            has_self_edge
            and self.resume_with_saved_results
            and self._should_save_result()
        ):
            loop_state = self._load_loop_state(resolve_args=args, resolve_kwargs=kwargs)
            if loop_state is not None and not loop_state["completed"]:
                last_iter = loop_state["last_completed_iteration"]
                self_loop_iteration = last_iter
                iter_data = self._load_loop_iteration(
                    last_iter, resolve_args=args, resolve_kwargs=kwargs
                )
                if self.result_pass_down_mode != ResultPassDownMode.NoPassDown:
                    args, kwargs = iter_data["next_args"], iter_data["next_kwargs"]

        while True:
            self_loop_iteration += 1

            self.log_debug(
                {
                    'node_name': self.name,
                    'graph_depth': graph_depth,
                    'self_loop_iteration': self_loop_iteration,
                    'is_self_loop': has_self_edge and self_loop_iteration > 1,
                },
                'NodeExecution'
            )

            if stop_flag == WorkGraphStopFlags.Continue:
                is_loaded_from_saved_result, result = self.load_result(*args, **kwargs)
                if not is_loaded_from_saved_result:
                    # Acquire semaphore for computation only (callee-side gating).
                    # Released before downstream propagation to avoid nested-lock
                    # deadlock in diamond graphs (fan-out → fan-in).
                    if semaphore:
                        self.log_info(
                            f"acquiring semaphore (group={self.group!r}, id={id(semaphore)})",
                            "ConcurrencyDiag",
                        )
                        await semaphore.acquire()
                        self.log_info("acquired semaphore", "ConcurrencyDiag")
                    try:
                        try:
                            rel_args, rel_kwargs = get_relevant_args(
                                func=self.value,
                                all_var_args_relevant_if_func_support_var_args=True,
                                all_named_args_relevant_if_func_support_named_args=True,
                                args=args,
                                **kwargs
                            )

                            # Graph visualization: emit RUNNING status (async path)
                            if self._graph_event_callback:
                                try:
                                    from agent_foundation.common.inferencers.graph_events import NodeStatusEvent, NodeStatus
                                    _cb_result = self._graph_event_callback(NodeStatusEvent(node_id=self.name, status=NodeStatus.RUNNING))
                                    if _cb_result is not None:
                                        import asyncio as _asyncio
                                        if _asyncio.iscoroutine(_cb_result):
                                            await _cb_result
                                except Exception:
                                    pass
                            # On retry, re-emit RUNNING so the UI doesn't stick on ERROR
                            async def _on_retry(attempt, exc):
                                if self._graph_event_callback:
                                    try:
                                        from agent_foundation.common.inferencers.graph_events import NodeStatusEvent, NodeStatus
                                        _r = self._graph_event_callback(NodeStatusEvent(node_id=self.name, status=NodeStatus.RUNNING))
                                        if _r is not None:
                                            import asyncio as _a
                                            if _a.iscoroutine(_r): await _r
                                    except Exception:
                                        pass

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
                                default_return_or_raise=self._get_fallback_result(*args, **kwargs),
                                on_retry_callback=_on_retry,
                            )
                            # Graph visualization: emit COMPLETED status after successful execution
                            if self._graph_event_callback:
                                try:
                                    from agent_foundation.common.inferencers.graph_events import NodeStatusEvent, NodeStatus
                                    _cb_result = self._graph_event_callback(NodeStatusEvent(node_id=self.name, status=NodeStatus.COMPLETED))
                                    if _cb_result is not None:
                                        import asyncio as _asyncio
                                        if _asyncio.iscoroutine(_cb_result):
                                            await _cb_result
                                except Exception as _e:
                                    import logging as _logging
                                    _logging.getLogger(__name__).warning(
                                        "Graph COMPLETED callback failed for %s: %s", self.name, _e
                                    )
                        except Exception as err:
                            import traceback
                            # Graph visualization: emit ERROR status
                            if self._graph_event_callback:
                                try:
                                    from agent_foundation.common.inferencers.graph_events import NodeStatusEvent, NodeStatus
                                    _cb_result = self._graph_event_callback(NodeStatusEvent(node_id=self.name, status=NodeStatus.ERROR, error=str(err)))
                                    if _cb_result is not None:
                                        import asyncio as _asyncio
                                        if _asyncio.iscoroutine(_cb_result):
                                            await _cb_result
                                except Exception:
                                    pass
                            self.log_error(
                                {
                                    'name': self.name,
                                    'executor': self.value,
                                    'args': args,
                                    'kwargs': kwargs,
                                    'exception_type': type(err).__name__,
                                    'exception_message': str(err),
                                    'traceback': traceback.format_exc()
                                },
                                'NodeExecutionFailed',
                            )
                            raise err

                        # Track whether stop_flag was already determined by expansion handling
                        _stop_flag_from_expansion = None
                        _expansion_include_self = None
                        _expansion_include_others = None

                        # Req 29: Stop-flag composition — detect (StopFlag, GraphExpansionResult) tuples
                        if (isinstance(result, tuple) and len(result) == 2
                                and isinstance(result[0], WorkGraphStopFlags)
                                and isinstance(result[1], GraphExpansionResult)):
                            _stop_flag_from_expansion = result[0]
                            expansion_result = result[1]
                            _expansion_include_self = expansion_result.include_self
                            _expansion_include_others = expansion_result.include_others
                            result = self._handle_graph_expansion(expansion_result, *args, **kwargs)
                        elif isinstance(result, GraphExpansionResult):
                            # Handle plain GraphExpansionResult before NextNodesSelector
                            _expansion_include_self = result.include_self
                            _expansion_include_others = result.include_others
                            result = self._handle_graph_expansion(result, *args, **kwargs)

                        # Handle NextNodesSelector return value
                        include_self, include_others, result = self._handle_next_nodes_selector(result)

                        # Req 23.3: GraphExpansionResult include_self/include_others take precedence
                        # Only override if GER explicitly set non-default values
                        if _expansion_include_self is not None and _expansion_include_self is not False:
                            include_self = _expansion_include_self
                        if _expansion_include_others is not None and _expansion_include_others is not True:
                            include_others = _expansion_include_others

                        # Stop-flag resolution: if expansion already determined the flag, use it;
                        # otherwise use the existing helper for non-expansion results.
                        if _stop_flag_from_expansion is not None:
                            stop_flag = _stop_flag_from_expansion
                        else:
                            stop_flag, result = WorkGraphStopFlags.separate_stop_flag_from_result(result)

                        # Post-process hooks via call_maybe_async
                        _result = await call_maybe_async(self._post_process, result, *args, **kwargs)
                        if _result is not None:
                            result = _result

                        if self.enable_optional_post_process:
                            _result = await call_maybe_async(self._optional_post_process, result, *args, **kwargs)
                            if _result is not None:
                                result = _result

                        # Save results if configured
                        if self._should_save_result():
                            result_path = self._get_result_path(self.name, *args, **kwargs)
                            self._save_result(result, result_path)
                    finally:
                        if semaphore:
                            self.log_info("releasing semaphore", "ConcurrencyDiag")
                            semaphore.release()

            # Propagate the result to downstream nodes concurrently
            if self.next:
                if stop_flag == WorkGraphStopFlags.Continue:
                    nargs, nkwargs = self._get_args_for_downstream(result, args, kwargs)
                    nodes_to_run = self._select_downstream_nodes(include_others, include_self=False)
                else:
                    nodes_to_run = [n for n in self.next if n is not self]

                # Concurrent downstream fan-out via asyncio.gather with indexed insertion
                # for deterministic result ordering (matching sync path's sequential order).
                _DS_EMPTY = object()
                downstream_results = [_DS_EMPTY] * len(nodes_to_run)
                tasks = []
                for idx, node in enumerate(nodes_to_run):
                    if stop_flag == WorkGraphStopFlags.Continue:
                        # Capture loop variables explicitly to avoid closure-over-loop-variable bug
                        nargs_copy = tuple(nargs)
                        nkwargs_copy = dict(nkwargs)
                        # Don't gate downstream propagation with the semaphore —
                        # each downstream node acquires it for its own computation
                        # inside its _arun(). This prevents nested-lock deadlock
                        # in diamond graphs.
                        async def _run_ds(i, n, a, kw):
                            return await n.arun(
                                *a,
                                _output_idx=(downstream_results, i),
                                _graph_depth=graph_depth + 1,
                                _semaphore=_semaphore_or_map,
                                **kw
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

                downstream_results = [r for r in downstream_results if r is not _DS_EMPTY]
                if downstream_results:
                    result = self._merge_downstream_results(downstream_results)

                if (
                    has_self_edge
                    and not is_loaded_from_saved_result
                    and self._should_save_result()
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
            if include_self and has_self_edge and stop_flag == WorkGraphStopFlags.Continue:
                if self.result_pass_down_mode == ResultPassDownMode.NoPassDown:
                    args, kwargs = original_args, dict(original_kwargs)
                else:
                    args, kwargs = nargs, dict(nkwargs)
                include_self = False
                include_others = True

                if self._should_save_result():
                    self._save_loop_state(
                        self_loop_iteration,
                        completed=False,
                        resolve_args=args,
                        resolve_kwargs=kwargs,
                    )

                self.log_debug(
                    {
                        'node_name': self.name,
                        'graph_depth': graph_depth,
                        'completed_iteration': self_loop_iteration,
                        'next_iteration': self_loop_iteration + 1,
                    },
                    'SelfLoopContinue'
                )
                continue
            else:
                if has_self_edge and self_loop_iteration > 1:
                    self.log_debug(
                        {
                            'node_name': self.name,
                            'graph_depth': graph_depth,
                            'total_iterations': self_loop_iteration,
                            'exit_reason': 'include_self=False' if not include_self else f'stop_flag={stop_flag}',
                        },
                        'SelfLoopExit'
                    )
                if has_self_edge and self._should_save_result():
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
    executor: Optional['QueuedExecutorBase'] = attrib(default=None, kw_only=True)
    use_async: bool = attrib(default=False, kw_only=True)

    # Optional concurrency limit for async execution path (_arun).
    # When set, creates an asyncio.Semaphore(max_concurrency) to limit concurrent node execution.
    # Ignored by the sync _run() path.
    max_concurrency: Optional[int] = attrib(default=None, kw_only=True)
    # Per-group concurrency limits. When set, creates per-group asyncio.Semaphores.
    # Nodes with a matching group name will use their group's semaphore.
    # Nodes without a group (group=None) use the global max_concurrency semaphore.
    # Example: {"research": 5, "investigation": 2}
    group_max_concurrency: Optional[Dict[str, int]] = attrib(default=None, kw_only=True)

    # Dynamic expansion configuration (Task 6.1)
    max_expansion_depth: int = attrib(default=0, kw_only=True)
    max_total_nodes: int = attrib(default=200, kw_only=True)
    subgraph_registry: Optional[Dict[str, Callable]] = attrib(default=None, kw_only=True)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        for start_node in self.start_nodes:
            if isinstance(start_node, Debuggable):
                start_node.set_parent_debuggable(self)
        # Propagate expansion settings to all reachable nodes via BFS
        self._propagate_expansion_settings()

    def _propagate_expansion_settings(self):
        """Propagate max_expansion_depth and max_total_nodes to all reachable nodes.

        BFS from start_nodes following 'next' edges to ensure every node in the
        graph has the correct expansion limits set.
        """
        from collections import deque
        visited = set()
        queue = deque(self.start_nodes)
        while queue:
            node = queue.popleft()
            node_id = id(node)
            if node_id in visited:
                continue
            visited.add(node_id)
            node._max_expansion_depth = self.max_expansion_depth
            node._max_total_nodes = self.max_total_nodes
            for child in (node.next or []):
                if id(child) not in visited:
                    queue.append(child)

    def _post_process(self, result, *args, **kwargs):
        return tuple(x for x in result if x is not None)

    def to_serializable_obj(
        self, 
        mode: str = 'auto',
        _output_format: Optional[str] = None
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
            for child in (node.next or []):
                serialize_node(child)
        
        for start_node in self.start_nodes:
            serialize_node(start_node)
        
        return {
            '_type': type(self).__name__,
            '_module': type(self).__module__,
            'version': '1.0',
            'start_node_names': [n.name for n in self.start_nodes],
            'nodes': nodes_data,
            'config': {
                'enable_result_save': (
                    self.enable_result_save.value 
                    if isinstance(self.enable_result_save, StepResultSaveOptions) 
                    else self.enable_result_save
                ),
                'resume_with_saved_results': self.resume_with_saved_results,
            }
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
            if hasattr(node, '_queue'):
                # Clear the queue by replacing it
                from queue import Queue
                node._queue = Queue()
            if hasattr(node, '_aqueue'):
                # asyncio.Queue has no .clear() method, so replace with a new instance
                node._aqueue = asyncio.Queue()
            for child in (node.next or []):
                clear_node(child)

        for start_node in self.start_nodes:
            clear_node(start_node)

    def set_graph_event_callback(self, callback: Callable) -> None:
        """Propagate graph event callback to all reachable WorkGraphNodes.

        Call this after building the graph (e.g., after _build_diamond_graph).
        The callback receives NodeStatusEvent objects and should be an async
        coroutine function when used in the async execution path (_arun).

        Example:
            async def _status_cb(event):
                await reporter.on_node_status(event.node_id, event.status)
            workgraph.set_graph_event_callback(_status_cb)
        """
        for node in self._all_nodes():
            node._graph_event_callback = callback

    def _all_nodes(self) -> List['WorkGraphNode']:
        """Get all nodes reachable from start_nodes via DFS."""
        visited = set()
        nodes = []

        def collect(node):
            if id(node) in visited:
                return
            visited.add(id(node))
            nodes.append(node)
            for child in (node.next or []):
                collect(child)

        for start_node in self.start_nodes:
            collect(start_node)
        return nodes

    # =========================================================================
    # Dynamic Expansion Reconstruction (Task 6.2)
    # =========================================================================

    def _reconstruct_graph_expansions(self, *args, **kwargs):
        """Reconstruct expanded subgraphs from persisted expansion records.

        Called during resume, BEFORE start_nodes execution begins.
        BFS from start_nodes following 'next' edges. For each node, checks
        for a persisted expansion record via ``_exists_result("__graph_expansion__{name}")``.

        Reconstruction priority per node:
        1. Seed-based: import factory by factory_ref, call factory(seed) → SubgraphSpec
        2. Registry-based: look up expansion_id in subgraph_registry, call factory(expansion_id)
        3. If neither available: raise ExpansionReplayError
           (dict form from to_serializable_obj is NOT sufficient — S6 fix)

        After reconstruction, re-attaches the subgraph via add_next(), propagates
        settings, and adds reconstructed nodes to the BFS queue for further traversal.
        """
        from collections import deque

        # Fast-path skip when expansion is disabled and no registry configured.
        if self.max_expansion_depth == 0 and self.subgraph_registry is None:
            return

        visited = set()
        queue = deque(self.start_nodes)

        while queue:
            node = queue.popleft()
            if id(node) in visited:
                continue
            visited.add(id(node))

            # Check for persisted expansion record
            result_id = f"__graph_expansion__{node.name}"
            try:
                result_path = node._resolve_result_path(result_id, *args, **kwargs)
                exists = node._exists_result(result_id=result_id, result_path=result_path)
            except (NotImplementedError, Exception):
                exists = None

            if exists is not None and exists is not False:
                # Load the expansion record
                record = node._load_result(
                    result_id=result_id,
                    result_path_or_preloaded_result=(
                        result_path if isinstance(exists, bool) else exists
                    ),
                )

                reconstructed_subgraph = None
                seed = record.get("seed")
                factory_module = record.get("factory_module")
                factory_qualname = record.get("factory_qualname")
                expansion_id = record.get("expansion_id")

                # Priority 1: Seed-based reconstruction
                if factory_module is not None and factory_qualname is not None:
                    try:
                        import importlib
                        import operator
                        module = importlib.import_module(factory_module)
                        factory = operator.attrgetter(factory_qualname)(module)
                        reconstructed_subgraph = factory(seed)
                    except (ImportError, AttributeError, Exception) as e:
                        raise ExpansionReplayError(
                            f"Failed to reconstruct graph expansion for node "
                            f"'{node.name}' from seed. Factory '{factory_module}.{factory_qualname}' "
                            f"could not be imported: {e}"
                        )

                # Priority 2: Registry-based
                if reconstructed_subgraph is None:
                    if (self.subgraph_registry is not None
                            and expansion_id is not None
                            and expansion_id in self.subgraph_registry):
                        factory = self.subgraph_registry[expansion_id]
                        reconstructed_subgraph = factory(expansion_id)

                # No fallback to pickle/dict — dict form is observability only (S6 fix)
                if reconstructed_subgraph is None:
                    raise ExpansionReplayError(
                        f"Cannot reconstruct graph expansion for node '{node.name}' "
                        f"(expansion_id='{expansion_id}'). Provide a seed-based "
                        f"reconstruct_from_seed or register a factory in subgraph_registry. "
                        f"The serialized dict form is for observability only and cannot "
                        f"reconstruct executable WorkGraphNode instances."
                    )

                # Re-attach subgraph to the node
                if isinstance(reconstructed_subgraph, SubgraphSpec):
                    was_insert_mode = record.get("was_insert_mode", False)
                    original_downstream_names = record.get("original_downstream_names", [])

                    if was_insert_mode and original_downstream_names:
                        # Insert-mode reconstruction: detach original downstream,
                        # attach subgraph entries, wire subgraph leaves to original downstream
                        original_downstream = [
                            n for n in (node.next or []) if n is not node
                            and n.name in original_downstream_names
                        ]
                        for child in original_downstream:
                            node.next.remove(child)
                            if node in (child.previous or []):
                                child.previous.remove(node)
                        for entry_node in reconstructed_subgraph.entry_nodes:
                            node.add_next(entry_node)
                        # Find subgraph leaves and wire to original downstream
                        sg_node_ids = {id(n) for n in reconstructed_subgraph.nodes}
                        for sg_node in reconstructed_subgraph.nodes:
                            has_internal_next = any(
                                id(n) in sg_node_ids for n in (sg_node.next or [])
                                if n is not sg_node
                            )
                            if not has_internal_next:
                                for child in original_downstream:
                                    sg_node.add_next(child)
                    else:
                        # Leaf-mode reconstruction: simply add entry nodes
                        for entry_node in reconstructed_subgraph.entry_nodes:
                            node.add_next(entry_node)

                    # Propagate settings
                    for sg_node in reconstructed_subgraph.nodes:
                        sg_node._expansion_depth = record.get("expansion_depth", 0) + 1
                        sg_node._max_expansion_depth = self.max_expansion_depth
                        sg_node._max_total_nodes = self.max_total_nodes
                    node._propagate_settings_to_subgraph(reconstructed_subgraph.nodes)
                    node._expansion_applied = True

                    # Add reconstructed nodes to traversal queue
                    for sg_node in reconstructed_subgraph.nodes:
                        queue.append(sg_node)
                else:
                    raise ExpansionReplayError(
                        f"Factory for expansion '{expansion_id}' returned "
                        f"{type(reconstructed_subgraph).__name__}, expected SubgraphSpec."
                    )

            # Continue BFS to downstream nodes
            for next_node in (node.next or []):
                if id(next_node) not in visited:
                    queue.append(next_node)

    # =========================================================================
    # Phase 4: Queue-Based Execution Support
    # =========================================================================

    def _create_wrapper_callable(
        self,
        node: 'WorkGraphNode',
        upstream_inputs: Dict[str, List],
        failed_parents: Dict[str, Set[str]]
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
        from python_utils.mp_utils.task import Task

        def wrapper(*args, **kwargs):
            # Execute the node's value function
            from python_utils.common_utils import get_relevant_args
            from python_utils.common_utils.function_helper import execute_with_retry

            rel_args, rel_kwargs = get_relevant_args(
                func=node.value,
                all_var_args_relevant_if_func_support_var_args=True,
                all_named_args_relevant_if_func_support_named_args=True,
                args=args,
                **kwargs
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

            # Handle GraphExpansionResult before NextNodesSelector
            if isinstance(result, GraphExpansionResult):
                expansion_result = result
                result = node._handle_graph_expansion(expansion_result, *args, **kwargs)

            # Handle NextNodesSelector
            include_self, include_others, actual_result = node._handle_next_nodes_selector(result)

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
                        callable=self._create_wrapper_callable(node, upstream_inputs, failed_parents),
                        args=self_args,
                        kwargs=self_kwargs,
                        task_id=new_task_id
                    )
                    next_tasks.append(task)
                else:
                    # Regular downstream node
                    num_parents = len_([p for p in (downstream_node.previous or []) if p is not downstream_node])
                    nargs, nkwargs = node._get_args_for_downstream(actual_result, args, kwargs)

                    if num_parents <= 1:
                        # Single parent - create task immediately
                        new_task_id = f"{downstream_node.name}::{uuid.uuid4().hex[:8]}"
                        task = Task(
                            callable=self._create_wrapper_callable(downstream_node, upstream_inputs, failed_parents),
                            args=nargs,
                            kwargs=nkwargs,
                            task_id=new_task_id
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
                            merged_args, merged_kwargs = downstream_node._merge_upstream_inputs(
                                upstream_inputs[downstream_name]
                            )

                            # Clear for potential re-execution
                            upstream_inputs[downstream_name] = []
                            if downstream_name in failed_parents:
                                failed_parents[downstream_name] = set()

                            new_task_id = f"{downstream_name}::{uuid.uuid4().hex[:8]}"
                            task = Task(
                                callable=self._create_wrapper_callable(downstream_node, upstream_inputs, failed_parents),
                                args=merged_args,
                                kwargs=merged_kwargs,
                                task_id=new_task_id
                            )
                            next_tasks.append(task)

            return (actual_result, next_tasks)

        return wrapper

    def _create_initial_tasks_wrapped(
        self,
        upstream_inputs: Dict[str, List],
        failed_parents: Dict[str, Set[str]],
        *args,
        **kwargs
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
        from python_utils.mp_utils.task import Task

        tasks = []
        for node in self.start_nodes:
            wrapper = self._create_wrapper_callable(node, upstream_inputs, failed_parents)
            task = Task(
                callable=wrapper,
                task_id=node.name,
                args=args,
                kwargs=kwargs,
                name=node.name
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
        from python_utils.mp_utils.task import Task, TaskState, TaskStatus

        node_map = {n.name: n for n in self._all_nodes()}
        upstream_inputs: Dict[str, List] = {}  # Lives in main process
        failed_parents: Dict[str, Set[str]] = {}  # Lives in main process
        task_to_node: Dict[str, str] = {}  # task_id -> node_name mapping

        def router(task_id: str, result: Any, task_state: TaskState) -> List:
            # Extract node name from task_id using "::" delimiter
            # Format: "node_name::uuid" (e.g., "my_node::abc123")
            node_name = task_to_node.get(task_id) or task_id.rsplit('::', 1)[0]
            node = node_map[node_name]

            # ============================================================
            # HANDLE FAILURE FIRST (before _handle_next_nodes_selector)
            # ============================================================
            if task_state.status == TaskStatus.FAILED:
                next_tasks = []

                # Track this parent as failed for all its downstream nodes
                for downstream_node in (node.next or []):
                    if downstream_node is node:
                        continue  # Skip self-edge - failed node won't loop

                    dn_name = downstream_node.name
                    num_parents = len_([p for p in (downstream_node.previous or []) if p is not downstream_node])

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
                            merged_args, merged_kwargs = downstream_node._merge_upstream_inputs(
                                upstream_inputs[dn_name]
                            )
                            new_task_id = f"{dn_name}::{uuid.uuid4().hex[:8]}"
                            task_to_node[new_task_id] = dn_name
                            task = Task(
                                callable=downstream_node.value,
                                args=merged_args,
                                kwargs=merged_kwargs,
                                task_id=new_task_id
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

            # Handle GraphExpansionResult before NextNodesSelector
            if isinstance(result, GraphExpansionResult):
                expansion_result = result
                result = node._handle_graph_expansion(expansion_result, *task_state.input_args, **task_state.input_kwargs)
                # Update node_map with newly added subgraph nodes
                for sg_node in expansion_result.subgraph.nodes:
                    node_map[sg_node.name] = sg_node

            # Handle NextNodesSelector
            include_self, include_others, actual_result = node._handle_next_nodes_selector(result)

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
                            actual_result, task_state.input_args, task_state.input_kwargs
                        )

                    new_task_id = f"{node.name}::selfloop::{uuid.uuid4().hex[:8]}"
                    task_to_node[new_task_id] = node.name
                    task = Task(
                        callable=node.value,  # Raw function - same node!
                        args=self_args,
                        kwargs=self_kwargs,
                        task_id=new_task_id
                    )
                    next_tasks.append(task)
                else:
                    # Regular downstream node
                    num_parents = len_([p for p in (downstream_node.previous or []) if p is not downstream_node])
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
                            task_id=new_task_id
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
                            merged_args, merged_kwargs = downstream_node._merge_upstream_inputs(
                                upstream_inputs[downstream_name]
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
                                task_id=new_task_id
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
        from python_utils.mp_utils.task import Task

        return [
            Task(
                callable=node.value,  # Raw function - must be picklable!
                task_id=node.name,
                args=args,
                kwargs=kwargs,
                name=node.name
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

        # Reconstruct graph expansions from persisted records when resuming
        if self.resume_with_saved_results is not False:
            self._reconstruct_graph_expansions(*args, **kwargs)

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
                        for prev_result, prev_is_loaded_from_saved_result, prev_node in zip(
                                output,
                                is_loaded_from_saved_results,
                                self.start_nodes
                        ):  # type: WorkGraphNode
                            if (
                                    prev_node.enable_result_save == StepResultSaveOptions.OnError
                                    and not prev_is_loaded_from_saved_result
                            ):
                                prev_node._save_result(
                                    prev_result,
                                    output_path=prev_node._get_result_path(
                                        prev_node.name, *args, **kwargs
                                    )
                                )
                    raise err

        result = self.post_process(output, *args, **kwargs)
        if (
                self.enable_result_save is True or
                self.enable_result_save == StepResultSaveOptions.Always
        ):
            # If Always saving is enabled, save the result of this node
            result_path = self._get_result_path(self.name, *args, **kwargs)
            self._save_result(
                result,
                output_path=result_path
            )
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

        # Reconstruct graph expansions from persisted records when resuming
        if self.resume_with_saved_results is not False:
            self._reconstruct_graph_expansions(*args, **kwargs)

        _EMPTY = object()  # Sentinel — distinguishes "no result" from "result is None"

        # Pre-allocate with sentinel for deterministic ordering
        output = [_EMPTY] * len(self.start_nodes)
        node_info = [None] * len(self.start_nodes)  # [(node, is_loaded), ...]

        terminate_event = asyncio.Event()
        # Build semaphore(s) for concurrency limiting
        self.log_info(
            f"WorkGraph._arun: group_max_concurrency={self.group_max_concurrency}, "
            f"max_concurrency={self.max_concurrency}, start_nodes={len(self.start_nodes)}",
            "ConcurrencyDiag",
        )
        if self.group_max_concurrency:
            # Per-group semaphores: dict mapping group_name -> Semaphore
            semaphore = {
                group_name: asyncio.Semaphore(limit)
                for group_name, limit in self.group_max_concurrency.items()
            }
            # Add global semaphore for ungrouped nodes (group=None)
            if self.max_concurrency:
                semaphore[None] = asyncio.Semaphore(self.max_concurrency)
        elif self.max_concurrency:
            semaphore = asyncio.Semaphore(self.max_concurrency)
        else:
            semaphore = None

        async def _run_start_node(idx, node):
            is_loaded, result = node.load_result(*args, **kwargs)
            node_info[idx] = (node, is_loaded)
            if is_loaded:
                # Match sync behavior: loaded results are NOT added to output
                return WorkGraphStopFlags.Continue
            if terminate_event.is_set():
                return WorkGraphStopFlags.Continue
            # Pass semaphore to the node so it can acquire/release around its
            # own computation only (callee-side gating). This avoids the nested
            # semaphore deadlock that occurs when the caller holds a slot while
            # the node's downstream propagation tries to acquire another slot.
            flag = await node.arun(
                *args, **kwargs,
                _output_idx=(output, idx),
                _semaphore=semaphore
            )
            if flag == WorkGraphStopFlags.Terminate:
                terminate_event.set()
            return flag

        tasks = [_run_start_node(i, node) for i, node in enumerate(self.start_nodes)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Post-filter: separate successes from exceptions
        exceptions = [(i, r) for i, r in enumerate(results) if isinstance(r, BaseException)]

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
                            output_path=node._get_result_path(node.name, *args, **kwargs)
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
            _result = await call_maybe_async(self._optional_post_process, output, *args, **kwargs)
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
