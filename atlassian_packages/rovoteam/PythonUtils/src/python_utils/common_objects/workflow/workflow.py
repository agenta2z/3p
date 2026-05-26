import glob
import importlib
import json
import os
import pickle
import re
import shutil
from abc import ABC
from datetime import datetime, timezone
from enum import Enum, StrEnum
from typing import Any, Dict, List, Optional, Sequence, Callable, Union

from attr import attrs, attrib

from python_utils.common_objects.workflow.common.exceptions import (
    WorkflowAborted,
    ExpansionConfigError,
    ExpansionReplayError,
    ExpansionLimitExceeded,
)
from python_utils.common_objects.workflow.common.expansion import (
    ExpansionResult,
    ExpansionRecord,
)
from python_utils.common_objects.workflow.common.step_result_save_options import (
    StepResultSaveOptions
)
from python_utils.common_objects.workflow.common.step_wrapper import StepWrapper
from python_utils.common_objects.workflow.common.result_pass_down_mode import ResultPassDownMode
from python_utils.common_objects.workflow.common.worknode_base import WorkNodeBase
from python_utils.common_utils.async_utils import call_maybe_async
from python_utils.io_utils.artifact import artifact_type
from python_utils.io_utils.pickle_io import _get_field_names


class WorkflowLogTypes(StrEnum):
    StepError = 'WorkflowStepError'
    CheckpointWarning = 'WorkflowCheckpointWarning'
    ExpansionWarning = 'WorkflowExpansionWarning'


# Forward reference: CheckpointState is defined after Workflow to avoid circular dependency.
# It is only used in jsonfy mode.
CheckpointState = None  # replaced below after Workflow class definition


@attrs(slots=False)
class Workflow(WorkNodeBase, ABC):
    """
    Orchestrates a sequence of computational steps with support for resuming, saving, and post-processing.

    This workflow supports:
        1. Executing a predefined sequence of steps (callabless).
        2. Optional hooks for processing results after each step.
        3. Saving and loading intermediate step results to facilitate resuming workflows.
        4. Configurable behavior for saving step results based on predefined options.

    Attributes:
        _steps (Sequence[Callable]):
            The steps to be executed, defined as callables.
        enable_optional_post_process (bool):
            If True, enables the `_optional_post_process` hook after each step, provided the step allows it.
        enable_result_save (Union[python_utils.common_objects.workflow.common.step_result_save_options.StepResultSaveOptions, bool, str]):
            Determines when to save step results. Supported values:
                - `StepResultSaveOptions.NoSave`
                - `StepResultSaveOptions.Always`
                - `StepResultSaveOptions.OnError`
                - True (equivalent to StepResultSaveOptions.Always)
                - False (equivalent to StepResultSaveOptions.NoSave)
        resume_with_saved_results (Union[bool, int]):
            Configures workflow resumption:
                - `False`: Runs the workflow from the beginning.
                - `True`: Resumes from the last successfully saved step.
                - `int`: Resumes from the specified step index.
        result_pass_down_mode (Union[str, python_utils.common_objects.workflow.common.result_pass_down_mode.ResultPassDownMode, Any]):
            The mode for passing results to downstream nodes. Defaults to `NoPassDown`.
            - If a ResultPassDownMode enum: controls positional pass-down behavior.
            - If a string: injects the result into kwargs under this key (overwriting existing key).
        logger (Optional[Union[Callable, logging.Logger]]):
            A logger for workflow-related messages.

    Methods:
        run(*args, **kwargs):
            Executes all steps in the workflow in sequence. Resumes from a saved step if configured to do so.

    Example:
        >>> import os
        >>> import shutil
        >>> from enum import Enum
        >>> from abc import ABC
        >>> from typing import Callable, Iterable, Union, Any
        >>> from attr import attrs, attrib

        >>> class StepResultSaveOptions(str, Enum):
        ...     NoSave = 'no_save'
        ...     Always = 'always'
        ...     OnError = 'on_error'

        >>> @attrs(slots=False)
        ... class MyWorkflow(Workflow):
        ...     def _get_result_path(self, result_id, *args, **kwargs) -> str:
        ...         # Save step results in a fixed directory for testing
        ...         return os.path.join('workflow_test_steps', f'step_{result_id}.pkl')
        ...
        ...     def _post_process(self, result, *args, **kwargs):
        ...         # Example post-processing: print the step result
        ...         print(f"Post-step processing result: {result}")
        ...         return result
        ...
        ...     def _optional_post_process(self, result, *args, **kwargs):
        ...         # Example optional post-processing: log the step result
        ...         print(f"Optional post-step processing result: {result}")
        ...         return result
        ...
        ...     def __attrs_post_init__(self):
        ...         super().__attrs_post_init__()
        ...         # Ensure the test directory exists
        ...         os.makedirs('workflow_test_steps', exist_ok=True)
        ...
        ...     def __del__(self):
        ...         # Clean up the test directory upon deletion
        ...         shutil.rmtree('workflow_test_steps', ignore_errors=True)

        # Define steps
        >>> def step0(x):
        ...     return x + 1
        ...
        >>> def step1(x):
        ...     return x * 2
        ...

        # Instantiate the workflow with steps and configurations
        >>> w = MyWorkflow(
        ...     steps=[step0, step1],
        ...     result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
        ...     enable_result_save=StepResultSaveOptions.Always,
        ...     resume_with_saved_results=False,
        ...     debug_mode=True
        ... )
        >>> result = w.run(5)
        Post-step processing result: 6
        Optional post-step processing result: 6
        Post-step processing result: 12
        Optional post-step processing result: 12
        >>> result
        12

        # Simulate resuming from a saved step
        # Create a new workflow instance with the same steps and configurations
        >>> w_resume = MyWorkflow(
        ...     steps=[step0, step1],
        ...     result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
        ...     enable_result_save=StepResultSaveOptions.Always,
        ...     logger=print,
        ...     resume_with_saved_results=True  # Resume from the last saved step
        ... )
        >>> resumed_result = w_resume.run(5)
        {'level': 20, 'name': 'MyWorkflow', 'type': 'WorkflowMessage', 'item': ['step 1 result exists', True], 'time': ...
        >>> resumed_result
        12

        >>> del w_resume
    """
    _steps = attrib(type=Sequence[Callable], default=None)
    _state = attrib(default=None, init=False)
    max_loop_iterations = attrib(type=int, default=10)
    max_expansion_events = attrib(type=int, default=0)
    max_total_steps = attrib(type=int, default=100)
    expansion_step_registry = attrib(type=Optional[Dict[str, Callable]], default=None)

    # ------------------------------------------------------------------
    # State & step hooks (override in subclasses)
    # ------------------------------------------------------------------

    def _init_state(self) -> dict:
        """Initialize flow state. Override for custom initial state."""
        return {}

    def _get_step_name(self, step, index) -> Optional[str]:
        """Get step name via per-step attribute pattern."""
        return getattr(step, 'name', None)

    def _update_state(self, state, result, step, step_name, step_index) -> dict:
        """Update state after a step completes.

        Delegates to a per-step ``update_state`` attribute if present.
        """
        updater = getattr(step, 'update_state', None)
        if updater is not None:
            updated = updater(state, result)
            if updated is not None:
                return updated
        return state

    def _on_step_complete(self, result, step_name, step_index, state,
                          *args, **kwargs):
        """Hook called after a step completes (only on non-loop-back iterations).

        Default is a no-op.  Subclasses override for per-step dispatch.
        """
        return None

    def _default_error_handler(self, error, step_result_so_far, state,
                               step_name, step_index):
        """Default error handler — re-raises, preserving current behaviour."""
        raise error

    def _handle_abort(self, abort_exc, step_result, state):
        """Handle a :class:`WorkflowAborted` exception.

        Default: return *step_result*.  Subclasses override to build a
        richer partial result from *abort_exc* and *state*.
        """
        return step_result

    def _resolve_step_index(self, target, steps) -> int:
        """Resolve a *loop_back_to* target (name or int) to a step index."""
        if isinstance(target, int):
            return target
        for idx, step in enumerate(steps):
            if getattr(step, 'name', None) == target:
                return idx
        raise ValueError(f"Loop target step '{target}' not found")

    # ------------------------------------------------------------------
    # Dynamic expansion methods
    # ------------------------------------------------------------------

    def _reset_expansion_state(self):
        """Reset per-run expansion state. Called at top of _run/_arun.

        Prevents cross-run leaks when the same Workflow instance is run
        multiple times (C2 fix).
        """
        self._expansion_count = 0
        self._expansion_records: List[ExpansionRecord] = []
        self._expansion_active = False

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

    def _get_loop_count_key(self, step, step_index):
        """Return name-based key when expansion active, index-based otherwise.

        Assigns synthetic name ``__step_{index}__`` for unnamed steps when
        expansion is active (Req 31).
        """
        if self._expansion_active:
            name = getattr(step, 'name', None)
            if name is None:
                name = f"__step_{step_index}__"
            return name
        return step_index

    def _migrate_loop_counts_to_names(self):
        """Migrate int-keyed ``_loop_counts`` to name-keyed using current ``_steps``.

        Called when the first expansion occurs to switch from index-based to
        name-based loop count tracking (Req 31, Req 34.2).
        """
        if not self._loop_counts:
            return
        new_counts = {}
        for key, value in self._loop_counts.items():
            if isinstance(key, int) and 0 <= key < len(self._steps):
                step = self._steps[key]
                name = getattr(step, 'name', None)
                if name is None:
                    name = f"__step_{key}__"
                new_counts[name] = value
            else:
                # Keep non-int or out-of-range keys as-is
                new_counts[key] = value
        self._loop_counts = new_counts

    def _resolve_integer_loop_back_to_targets(self):
        """Resolve integer loop_back_to targets to step names on first expansion.

        When expansion shifts indices, integer-based loop_back_to targets would
        point at wrong steps. This method resolves all existing integer targets
        to their corresponding step names. If the target step has no name, a
        synthetic name is assigned (Req 37.1).
        """
        if not self._steps:
            return
        # Convert _steps to list if tuple so we can mutate StepWrapper attributes
        if isinstance(self._steps, tuple):
            self._steps = list(self._steps)

        for step in self._steps:
            loop_back_to = getattr(step, 'loop_back_to', None)
            if loop_back_to is not None and isinstance(loop_back_to, int):
                if 0 <= loop_back_to < len(self._steps):
                    target_step = self._steps[loop_back_to]
                    target_name = getattr(target_step, 'name', None)
                    if target_name is None:
                        # Assign synthetic name to unnamed target step
                        target_name = f"__step_{loop_back_to}__"
                        if isinstance(target_step, StepWrapper):
                            target_step.name = target_name
                        elif hasattr(target_step, 'name'):
                            target_step.name = target_name
                    # Update loop_back_to to use name instead of index
                    if isinstance(step, StepWrapper):
                        step.loop_back_to = target_name
                    elif hasattr(step, 'loop_back_to'):
                        step.loop_back_to = target_name

    def _handle_expansion(self, step_index, expansion_result, state,
                          orig_args=None, orig_kwargs=None):
        """Process an ExpansionResult: validate, insert steps, record.

        Args:
            step_index: Index of the step that returned the ExpansionResult.
            expansion_result: The ExpansionResult returned by the step.
            state: Current workflow state dict.
            orig_args: Original positional args to the emitter step (for splice mode).
            orig_kwargs: Original keyword args to the emitter step (for splice mode).

        Returns:
            The ``expansion_result.result`` (the step's actual output).
        """
        new_steps = expansion_result.new_steps

        # Empty/None new_steps is a no-op (Req 9.1)
        if not new_steps:
            return expansion_result.result

        # Check max_expansion_events limit (Req 6.1, 6.2)
        if self._expansion_count >= self.max_expansion_events:
            self.log_warning(
                f"Expansion limit reached ({self.max_expansion_events}). "
                f"Ignoring expansion at step index {step_index}.",
                log_type=WorkflowLogTypes.ExpansionWarning,
            )
            return expansion_result.result

        # Validate all new_steps are callable (Req 9.4)
        for idx, s in enumerate(new_steps):
            if not callable(s):
                raise TypeError(
                    f"new_steps[{idx}] is not callable: {s!r}"
                )

        # Check max_total_steps limit (Req 6.3, 6.4)
        new_total = len(self._steps) + len(new_steps)
        if new_total > self.max_total_steps:
            raise ExpansionLimitExceeded(
                f"Inserting {len(new_steps)} steps would bring total to "
                f"{new_total}, exceeding max_total_steps={self.max_total_steps}."
            )

        # Check name uniqueness (Req 2.3)
        existing_names = set()
        for s in self._steps:
            n = getattr(s, 'name', None)
            if n is not None:
                existing_names.add(n)
        for s in new_steps:
            n = getattr(s, 'name', None)
            if n is not None:
                if n in existing_names:
                    raise ValueError(
                        f"Duplicate step name in expansion: {n!r}"
                    )
                existing_names.add(n)

        # Validate seed factory if provided (Req 25.4)
        factory_module = None
        factory_qualname = None
        if expansion_result.reconstruct_from_seed is not None:
            self._validate_seed_factory(expansion_result.reconstruct_from_seed)
            factory_module = expansion_result.reconstruct_from_seed.__module__
            factory_qualname = expansion_result.reconstruct_from_seed.__qualname__

        # Convert _steps to list if tuple so we can mutate it
        if isinstance(self._steps, tuple):
            self._steps = list(self._steps)

        # Wrap plain callables in StepWrapper for synthetic name tracking (S4 fix)
        wrapped_steps = []
        for idx, s in enumerate(new_steps):
            if not isinstance(s, StepWrapper) and not hasattr(s, 'name'):
                synthetic_name = f"__expanded_{self._expansion_count}_{idx}__"
                s = StepWrapper(s, name=synthetic_name)
            wrapped_steps.append(s)

        # Insert new_steps at step_index + 1 (Req 2.1)
        insert_pos = step_index + 1
        for idx, s in enumerate(wrapped_steps):
            self._steps.insert(insert_pos + idx, s)

        # Get the expanding step's name for the record (S1 fix: use name, not index)
        expanding_step = self._steps[step_index]
        expanding_step_name = getattr(expanding_step, 'name', None) or str(step_index)

        # Create ExpansionRecord
        record = ExpansionRecord(
            after_step_name=expanding_step_name,
            expansion_id=expansion_result.expansion_id,
            num_steps=len(wrapped_steps),
            seed=expansion_result.seed,
            factory_module=factory_module,
            factory_qualname=factory_qualname,
        )
        self._expansion_records.append(record)

        # Switch to name-based loop counts on first expansion (Req 31)
        if not self._expansion_active:
            self._migration_needed = True
            self._migrate_loop_counts_to_names()
            self._resolve_integer_loop_back_to_targets()  # Req 37
            self._expansion_active = True

        # Update expansion count and state (Req 7.3)
        self._expansion_count += 1
        if state is not None:
            state["__expansion_count"] = self._expansion_count

        # Handle splice mode (Req 26): store original args for first expanded step
        if expansion_result.mode == 'splice':
            self._splice_orig_args = orig_args
            self._splice_orig_kwargs = orig_kwargs
            self._splice_step_index = step_index + 1  # first expanded step

        return expansion_result.result

    def _reconstruct_expansions(self, checkpoint, *args, **kwargs):
        """Reconstruct expanded steps from checkpoint expansion records.

        Priority order:
        1. Seed-based: import factory by factory_ref, call factory(seed)
        2. Registry-based: look up expansion_id in expansion_step_registry
        3. Error: raise indicating reconstruction method required

        Raises:
            ExpansionReplayError: if seed-based reconstruction fails.
            TypeError: if no reconstruction method succeeds.
        """
        expansions = checkpoint.get("expansions")
        if not expansions:
            return

        # Convert _steps to list if tuple
        if isinstance(self._steps, tuple):
            self._steps = list(self._steps)

        for rec_data in expansions:
            # Support both dict and ExpansionRecord
            if isinstance(rec_data, dict):
                after_step_name = rec_data.get("after_step_name")
                expansion_id = rec_data.get("expansion_id")
                num_steps = rec_data.get("num_steps", 0)
                seed = rec_data.get("seed")
                factory_module = rec_data.get("factory_module")
                factory_qualname = rec_data.get("factory_qualname")
            else:
                after_step_name = rec_data.after_step_name
                expansion_id = rec_data.expansion_id
                num_steps = rec_data.num_steps
                seed = rec_data.seed
                factory_module = rec_data.factory_module
                factory_qualname = rec_data.factory_qualname

            # Resolve insertion point by step NAME (S1 fix)
            insert_after_idx = None
            for idx, step in enumerate(self._steps):
                name = getattr(step, 'name', None)
                if name == after_step_name:
                    insert_after_idx = idx
                    break
            # Fallback: try parsing as int index if name lookup fails
            if insert_after_idx is None:
                try:
                    insert_after_idx = int(after_step_name)
                except (ValueError, TypeError):
                    raise ExpansionReplayError(
                        f"Cannot find step named {after_step_name!r} for "
                        f"expansion reconstruction."
                    )

            reconstructed_steps = None

            # Priority 1: Seed-based reconstruction
            if seed is not None and factory_module and factory_qualname:
                try:
                    mod = importlib.import_module(factory_module)
                    # Navigate dotted qualname (e.g., "Class.method")
                    obj = mod
                    for part in factory_qualname.split('.'):
                        obj = getattr(obj, part)
                    factory_fn = obj
                    reconstructed_steps = factory_fn(seed)
                except Exception as e:
                    raise ExpansionReplayError(
                        f"Seed-based reconstruction failed for expansion "
                        f"after step {after_step_name!r} "
                        f"(factory={factory_module}.{factory_qualname}): {e}"
                    ) from e

            # Priority 2: Registry-based reconstruction
            if reconstructed_steps is None and expansion_id is not None:
                if self.expansion_step_registry and expansion_id in self.expansion_step_registry:
                    factory = self.expansion_step_registry[expansion_id]
                    reconstructed_steps = factory(expansion_id)

            # No reconstruction method available
            if reconstructed_steps is None:
                raise TypeError(
                    f"Cannot reconstruct expansion after step {after_step_name!r} "
                    f"(expansion_id={expansion_id!r}). Provide an "
                    f"expansion_step_registry or seed-based reconstruction."
                )

            # Wrap plain callables in StepWrapper (S4 fix)
            wrapped = []
            for idx, s in enumerate(reconstructed_steps):
                if not isinstance(s, StepWrapper) and not hasattr(s, 'name'):
                    synthetic_name = f"__reconstructed_{expansion_id or after_step_name}_{idx}__"
                    s = StepWrapper(s, name=synthetic_name)
                wrapped.append(s)

            # Insert at correct position
            insert_pos = insert_after_idx + 1
            for idx, s in enumerate(wrapped):
                self._steps.insert(insert_pos + idx, s)

            # Rebuild the ExpansionRecord for tracking
            record = ExpansionRecord(
                after_step_name=after_step_name,
                expansion_id=expansion_id,
                num_steps=len(wrapped),
                seed=seed,
                factory_module=factory_module,
                factory_qualname=factory_qualname,
            )
            self._expansion_records.append(record)

        # Mark expansion as active since we reconstructed
        self._expansion_active = True

    # ------------------------------------------------------------------
    # Loop + resume checkpoint helpers
    # ------------------------------------------------------------------

    def _has_loop_steps(self) -> bool:
        """Detect if any step uses loop_back_to or expansion is enabled (Req 32)."""
        if self.max_expansion_events > 0:
            return True
        return any(
            getattr(s, 'loop_back_to', None) is not None
            for s in (self._steps or ())
        )

    @staticmethod
    def _make_seq_result_id(step_name_or_index, exec_seq) -> str:
        """Return a unique result ID with a sequence number suffix."""
        return f"{step_name_or_index}___seq{exec_seq}"

    def _save_checkpoint(self, checkpoint_dict, *args, **kwargs):
        """Save a workflow checkpoint, delegating to _save_result for subclass compat."""
        checkpoint_path = self._resolve_result_path("__wf_checkpoint__", *args, **kwargs)
        self._save_result(checkpoint_dict, output_path=checkpoint_path)

    def _try_load_checkpoint(self, *args, **kwargs) -> Optional[dict]:
        """Try loading a checkpoint. Returns None on any failure (falls back to backward scan)."""
        try:
            ckpt_id = "__wf_checkpoint__"
            ckpt_path = self._resolve_result_path(ckpt_id, *args, **kwargs)
            exists = self._exists_result(result_id=ckpt_id, result_path=ckpt_path)
            if not exists:
                return None
            ckpt = self._load_result(
                result_id=ckpt_id,
                result_path_or_preloaded_result=(
                    ckpt_path if isinstance(exists, bool) else exists
                ),
            )
            # Handle CheckpointState wrapper (jsonfy mode)
            if CheckpointState is not None and isinstance(ckpt, CheckpointState):
                ckpt = {
                    "version": ckpt.version,
                    "exec_seq": ckpt.exec_seq,
                    "step_index": ckpt.step_index,
                    "result_id": ckpt.result_id,
                    "next_step_index": ckpt.next_step_index,
                    "loop_counts": ckpt.loop_counts,
                    "state": ckpt.state,
                    "expansions": getattr(ckpt, 'expansions', []),
                }
            if not isinstance(ckpt, dict) or "next_step_index" not in ckpt:
                return None
            # Normalize loop_counts: jsonfy converts int-keyed dicts to
            # [{key: k, value: v}, ...] lists; convert back to dict.
            lc = ckpt.get("loop_counts", {})
            if isinstance(lc, list):
                ckpt["loop_counts"] = {
                    item["key"]: item["value"]
                    for item in lc
                    if isinstance(item, dict) and "key" in item
                }
            # Re-setup child workflows after loading
            ckpt_state = ckpt.get("state")
            if ckpt_state is not None:
                self._setup_child_workflows(ckpt_state, *args, **kwargs)
            # Reconstruct expanded steps from checkpoint (v1→v2 migration: defaults to empty)
            self._reconstruct_expansions(ckpt, *args, **kwargs)
            # Req 26.5: Restore splice state from checkpoint if present
            if "splice_step_index" in ckpt:
                self._splice_orig_args = ckpt.get("splice_orig_args")
                self._splice_orig_kwargs = ckpt.get("splice_orig_kwargs")
                self._splice_step_index = ckpt["splice_step_index"]
            return ckpt
        except Exception:
            return None

    def _save_loop_checkpoint(self, step_index, next_step_index,
                              last_saved_result_id, state, *args, **kwargs):
        """Save a loop checkpoint after the loop decision is resolved.

        Shared by both _run() and _arun() to avoid duplication.
        """
        # Setup child workflows before saving so they have inherited config
        self._setup_child_workflows(state, *args, **kwargs)

        # Validate serializability on first checkpoint only.
        if not getattr(self, '_state_picklability_verified', False):
            if self.checkpoint_mode == 'jsonfy':
                try:
                    from python_utils.io_utils.json_io import jsonfy
                    jsonfy(state)
                except Exception as e:
                    raise TypeError(
                        f"Workflow state is not jsonfy-serializable and cannot be "
                        f"checkpointed. Either make state serializable, use "
                        f"checkpoint_mode='pickle', or set enable_result_save=False. "
                        f"Original error: {e}"
                    ) from e
            else:
                try:
                    pickle.dumps(state)
                except Exception as e:
                    raise TypeError(
                        f"Workflow state is not picklable and cannot be checkpointed "
                        f"for loop resume. Either make state picklable or set "
                        f"enable_result_save=False. Original error: {e}"
                    ) from e
            self._state_picklability_verified = True

        checkpoint_dict = {
            "version": 2 if self._expansion_records else 1,
            "exec_seq": self._exec_seq,
            "step_index": step_index,
            "result_id": last_saved_result_id,
            "next_step_index": next_step_index,
            "loop_counts": dict(self._loop_counts),
            "state": state,
            "expansions": [vars(r) for r in self._expansion_records],
        }

        # Req 26.5: Persist splice state for checkpoint/resume
        _splice_args = getattr(self, '_splice_orig_args', None)
        _splice_kwargs = getattr(self, '_splice_orig_kwargs', None)
        _splice_idx = getattr(self, '_splice_step_index', None)
        if _splice_idx is not None:
            # Validate serializability of splice args
            if self.checkpoint_mode == 'jsonfy':
                try:
                    from python_utils.io_utils.json_io import jsonfy
                    jsonfy(_splice_args)
                    jsonfy(_splice_kwargs)
                except Exception as e:
                    raise TypeError(
                        f"Splice mode original args/kwargs are not jsonfy-serializable "
                        f"and cannot be checkpointed. Original error: {e}"
                    ) from e
            else:
                try:
                    pickle.dumps(_splice_args)
                    pickle.dumps(_splice_kwargs)
                except Exception as e:
                    raise TypeError(
                        f"Splice mode original args/kwargs are not picklable "
                        f"and cannot be checkpointed. Original error: {e}"
                    ) from e
            checkpoint_dict["splice_orig_args"] = _splice_args
            checkpoint_dict["splice_orig_kwargs"] = _splice_kwargs
            checkpoint_dict["splice_step_index"] = _splice_idx

        if self.checkpoint_mode == 'jsonfy' and CheckpointState is not None:
            checkpoint_dict = CheckpointState(**checkpoint_dict)

        self._save_checkpoint(checkpoint_dict, *args, **kwargs)

    def _save_step_in_progress_marker(
        self, step_index, step_name, state, *args, **kwargs
    ):
        """Write a pre-execution marker before running a step.

        The marker is a lightweight JSON file placed alongside the checkpoint.
        If the process crashes mid-step, the marker persists on disk, allowing
        the next resume to detect that the step was attempted but never finished.
        """
        try:
            checkpoint_path = self._resolve_result_path(
                "__wf_checkpoint__", *args, **kwargs
            )
            if not checkpoint_path:
                return
            marker_path = os.path.join(
                os.path.dirname(checkpoint_path),
                "__wf_step_in_progress__.json",
            )
            os.makedirs(os.path.dirname(marker_path), exist_ok=True)
            marker = {
                "step_index": step_index,
                "step_name": step_name,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "attempt": self._step_attempt_counts.get(step_index, 0),
            }
            with open(marker_path, "w") as f:
                json.dump(marker, f, indent=2)
        except Exception:
            pass  # Non-fatal: marker is best-effort

    def _clear_step_in_progress_marker(self, *args, **kwargs):
        """Remove the pre-execution marker after successful step completion."""
        try:
            checkpoint_path = self._resolve_result_path(
                "__wf_checkpoint__", *args, **kwargs
            )
            if not checkpoint_path:
                return
            marker_path = os.path.join(
                os.path.dirname(checkpoint_path),
                "__wf_step_in_progress__.json",
            )
            os.remove(marker_path)
        except Exception:
            pass

    def _load_step_in_progress_marker(self, *args, **kwargs) -> Optional[dict]:
        """Load the pre-execution marker on resume.

        Returns:
            Marker dict with step_index, step_name, started_at, attempt;
            or None if no marker exists.
        """
        try:
            checkpoint_path = self._resolve_result_path(
                "__wf_checkpoint__", *args, **kwargs
            )
            if not checkpoint_path:
                return None
            marker_path = os.path.join(
                os.path.dirname(checkpoint_path),
                "__wf_step_in_progress__.json",
            )
            if os.path.isfile(marker_path):
                with open(marker_path) as f:
                    return json.load(f)
        except Exception:
            pass
        return None

    @staticmethod
    def _glob_seq_results(step_result_path):
        """Find ___seqN results for a step, matching file, directory, and jsonfy formats.

        Returns the path of the highest-numbered seq result, or None if none found.
        Handles:
        - Legacy .pkl files (step_name___seq1.pkl)
        - Parts directories (step_name___seq1/ with main.pkl)
        - Jsonfy .json files (step_name___seq1.pkl.json)
        """
        base_dir = os.path.dirname(step_result_path)
        base_name_parts = os.path.basename(step_result_path).rsplit('.', 1)
        stem = base_name_parts[0]

        # Try file pattern first (legacy: step_name___seq1.pkl)
        pattern = os.path.join(base_dir, f"{stem}___seq*")
        if len(base_name_parts) > 1:
            pattern += f".{base_name_parts[1]}"
        matches = glob.glob(pattern)
        # Filter out .json files from the file pattern (they need separate handling)
        matches = [m for m in matches if not m.endswith('.json')]

        if not matches:
            # Try directory pattern (parts mode: step_name___seq1/)
            dir_pattern = os.path.join(base_dir, f"{stem}___seq*")
            matches = [
                m for m in glob.glob(dir_pattern)
                if os.path.isdir(m) and os.path.exists(
                    os.path.join(m, "main.pkl")
                )
            ]

        if not matches:
            # Try jsonfy pattern (step_name___seq1.pkl.json)
            json_pattern = os.path.join(base_dir, f"{stem}___seq*")
            if len(base_name_parts) > 1:
                json_pattern += f".{base_name_parts[1]}.json"
            else:
                json_pattern += ".json"
            matches = [m for m in glob.glob(json_pattern) if os.path.isfile(m)]

        if not matches:
            return None

        matches.sort(
            key=lambda p: int(re.search(r'___seq(\d+)', p).group(1))
        )
        return matches[-1]

    # ------------------------------------------------------------------
    # Child Workflow discovery and setup (recursive resume)
    # ------------------------------------------------------------------

    def _find_child_workflows_in(self, source):
        """Find child Workflow instances in a source object using artifact metadata.

        Checks both type(self).__artifact_types__ (Pattern A: decorator on
        parent Workflow class) and type(source).__artifact_types__ (Pattern B:
        decorator on state class), merging and deduplicating.

        Returns:
            dict: {field_name: (workflow_instance, artifact_entry)}
        """
        if source is None:
            return {}

        # Merge artifact_types from both self and source
        all_entries = []
        for cls in [type(self), type(source)]:
            entries = getattr(cls, '__artifact_types__', None)
            if entries:
                all_entries.extend(entries)
        if not all_entries:
            return {}

        # Deduplicate by target_type
        seen_types = set()
        unique_entries = []
        for entry in all_entries:
            tt = entry['target_type']
            if tt not in seen_types:
                seen_types.add(tt)
                unique_entries.append(entry)

        children = {}
        for entry in unique_entries:
            target_type = entry['target_type']
            if not (isinstance(target_type, type) and issubclass(target_type, Workflow)):
                continue
            if isinstance(source, dict):
                for key, val in source.items():
                    if isinstance(val, target_type):
                        children[key] = (val, entry)
            else:
                for attr_name in _get_field_names(source):
                    val = getattr(source, attr_name, None)
                    if isinstance(val, target_type):
                        children[attr_name] = (val, entry)
        return children

    def _setup_child_workflows(self, state, *args, **kwargs):
        """Discover and configure child Workflow instances for recursive resume.

        Scans both direct attributes of self and the state object for child
        Workflows. For each child, sets _result_root_override and propagates
        checkpoint settings.
        """
        if state is None:
            return

        # Check if either self or state has artifact metadata
        has_metadata = (
            getattr(type(self), '__artifact_types__', None) or
            getattr(type(state), '__artifact_types__', None)
        )
        if not has_metadata:
            return

        parent_result_dir = os.path.dirname(
            self._resolve_result_path("__wf_checkpoint__", *args, **kwargs)
        )

        all_children = {}
        all_children.update(self._find_child_workflows_in(self))
        all_children.update(self._find_child_workflows_in(state))

        for attr_name, (child, entry) in all_children.items():
            subfolder = entry.get('subfolder')
            if subfolder:
                child_dir = os.path.join(parent_result_dir, subfolder, attr_name)
            else:
                child_dir = os.path.join(parent_result_dir, attr_name)
            os.makedirs(child_dir, exist_ok=True)
            child._result_root_override = child_dir
            child.enable_result_save = self.enable_result_save
            child.resume_with_saved_results = self.resume_with_saved_results
            child.checkpoint_mode = self.checkpoint_mode

    def _get_step_identifier(self, step: Callable, index: int) -> Dict[str, Any]:
        """Get serializable identifier for a step callable.
        
        Args:
            step: The callable step function
            index: The index of the step in the sequence
            
        Returns:
            Dict containing step identifier information
        """
        identifier = {
            'index': index,
            'name': None,
            'module': None,
            'ref': None,
        }
        
        if hasattr(step, '__name__'):
            identifier['name'] = step.__name__
        if hasattr(step, '__module__'):
            identifier['module'] = step.__module__
        if identifier['name'] and identifier['module']:
            identifier['ref'] = f"{identifier['module']}.{identifier['name']}"
        
        return identifier

    def to_serializable_obj(
        self, 
        mode: str = 'auto',
        _output_format: Optional[str] = None
    ) -> Dict[str, Any]:
        """Serialize Workflow to dict.
        
        Serializes step configuration and stores step identifiers that can
        be resolved during deserialization. Dynamically added steps are marked
        with ``"expanded": True`` and their ``expansion_id``.
        
        Args:
            mode: Serialization mode ('auto', 'dict', 'pickle')
            _output_format: Target output format for conflict detection
            
        Returns:
            Dict containing workflow configuration and step identifiers.
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

        # Build a set of expanded step indices and their expansion_ids
        # from _expansion_records so we can mark them in the serialized output.
        expanded_indices: Dict[int, Optional[str]] = {}
        expansion_records = getattr(self, '_expansion_records', None) or []
        if expansion_records and self._steps:
            for record in expansion_records:
                # Find the step that triggered the expansion by name
                after_name = record.after_step_name
                after_idx = None
                for idx, step in enumerate(self._steps):
                    if getattr(step, 'name', None) == after_name:
                        after_idx = idx
                        break
                if after_idx is None:
                    # Fallback: try parsing as int index
                    try:
                        after_idx = int(after_name)
                    except (ValueError, TypeError):
                        continue
                # Mark the inserted steps (after_idx+1 .. after_idx+num_steps)
                for offset in range(record.num_steps):
                    expanded_indices[after_idx + 1 + offset] = record.expansion_id

        # Serialize step identifiers
        step_identifiers = []
        if self._steps:
            for i, step in enumerate(self._steps):
                ident = self._get_step_identifier(step, i)
                if i in expanded_indices:
                    ident['expanded'] = True
                    ident['expansion_id'] = expanded_indices[i]
                step_identifiers.append(ident)

        result = {
            '_type': type(self).__name__,
            '_module': type(self).__module__,
            'version': '1.0',
            'name': self.name,
            'steps': step_identifiers,
            'config': {
                'enable_result_save': (
                    self.enable_result_save.value 
                    if isinstance(self.enable_result_save, StepResultSaveOptions) 
                    else self.enable_result_save
                ),
                'resume_with_saved_results': self.resume_with_saved_results,
                'result_pass_down_mode': result_pass_down_mode_str,
                'enable_optional_post_process': self.enable_optional_post_process,
            }
        }

        # Include expansion_records in the serialized output when present
        if expansion_records:
            result['expansion_records'] = [vars(r) for r in expansion_records]

        return result

    def _run(self, *args, **kwargs):
        # Reset per-run expansion state (C2 fix: prevents cross-run leaks)
        self._reset_expansion_state()

        # If no steps are defined, simply return as there's nothing to run.
        if not self._steps:
            return

        # Setup child workflows for recursive resume
        self._setup_child_workflows(self._state, *args, **kwargs)

        # Detect if any step uses loop_back_to — needed by both resume and save blocks.
        _has_loops = self._has_loop_steps()

        # Determine the starting step index for execution. By default, start from -1,
        # which means no steps have been completed and we start from the first step (index 0).
        # If resuming is enabled, we try to find the latest completed step result to resume from.
        start_step_i = -1
        step_result = None
        prev_step_result = None
        _checkpoint = None
        _checkpoint_state = None
        _checkpoint_next_i = None

        # Check if we should resume from a previously saved step result.
        # resume_with_saved_results can be:
        #   - False: Do not resume, run from the beginning.
        #   - True: Resume from the last saved step result.
        #   - int: Resume from the specific step index given.
        if self.resume_with_saved_results is not False:
            # Try checkpoint-based resume for auto-resume with loops
            if _has_loops and self.resume_with_saved_results is True:
                _checkpoint = self._try_load_checkpoint(*args, **kwargs)

            if _checkpoint is not None:
                # --- Checkpoint-based resume ---
                try:
                    _ckpt_result_id = _checkpoint["result_id"]
                    step_result = self._load_result(
                        result_id=_ckpt_result_id,
                        result_path_or_preloaded_result=self._resolve_result_path(
                            _ckpt_result_id, *args, **kwargs
                        ),
                    )
                except Exception:
                    self.log_warning(
                        "Checkpoint result file not found, falling back to backward scan",
                        log_type=WorkflowLogTypes.CheckpointWarning,
                    )
                    _checkpoint = None

            if _checkpoint is not None:
                start_step_i = _checkpoint["step_index"]
                self._loop_counts = _checkpoint.get("loop_counts", {})
                self._exec_seq = _checkpoint.get("exec_seq", 0)
                _checkpoint_state = _checkpoint.get("state")
                _checkpoint_next_i = _checkpoint["next_step_index"]
            else:
                # --- Existing backward scan (unchanged) ---
                saved_step_results_back_search_start_index = (
                    self.resume_with_saved_results
                    if isinstance(self.resume_with_saved_results, int)
                    else len(self._steps) - 1
                )

                for i in range(saved_step_results_back_search_start_index, -1, -1):
                    result_id = self._get_step_name(self._steps[i], i) or i
                    step_result_path = self._resolve_result_path(result_id, *args, **kwargs)
                    exists_step_result_or_preloaded_step_result = self._exists_result(
                        result_id=result_id, result_path=step_result_path
                    )

                    # Glob fallback for ___seqN results when loops are active
                    if _has_loops and not (
                        exists_step_result_or_preloaded_step_result is not None
                        and exists_step_result_or_preloaded_step_result is not False
                    ):
                        seq_path = self._glob_seq_results(step_result_path)
                        if seq_path is not None:
                            step_result_path = seq_path
                            exists_step_result_or_preloaded_step_result = True

                    if (
                            exists_step_result_or_preloaded_step_result is not None and
                            exists_step_result_or_preloaded_step_result is not False
                    ):
                        self.log_info((f'step {i} result exists', True))
                        start_step_i = i
                        break
                    else:
                        self.log_info((f'step {i} result exists', False))

                # Load the found result
                if start_step_i != -1:
                    step_result = self._load_result(
                        result_id=start_step_i,
                        result_path_or_preloaded_result=(
                            step_result_path if
                            isinstance(exists_step_result_or_preloaded_step_result, bool)
                            else exists_step_result_or_preloaded_step_result
                        )
                    )

        # --- State initialization ---
        _uses_state = any(
            getattr(s, 'update_state', None) is not None
            or getattr(s, 'receives_state', False)
            for s in self._steps
        )
        if _checkpoint_state is not None:
            state = _checkpoint_state
        else:
            state = self._init_state() if _uses_state else None
        self._state = state

        # Initialize loop-resume tracking variables.
        # These must be set BEFORE the while loop to avoid NameError.
        if _checkpoint is None:
            self._exec_seq = 0
            self._loop_counts = {}
        self._state_picklability_verified = False
        _last_saved_result_id = None

        # Step-in-progress tracking.
        # _step_attempt_counts accumulates across resume cycles (must persist
        # if already populated from a prior run's marker), while the per-run
        # flags are always reset so each run starts without stale state.
        if not hasattr(self, "_step_attempt_counts"):
            self._step_attempt_counts = {}
        self._step_was_previously_attempted = False
        self._previous_attempt_info = None

        # Determine starting step index.
        if _checkpoint_next_i is not None:
            i = _checkpoint_next_i
        else:
            i = start_step_i + 1

        # Detect partial step execution from prior run
        if _has_loops and _checkpoint is not None:
            marker = self._load_step_in_progress_marker(*args, **kwargs)
            if marker and marker.get("step_index") == i:
                self._step_attempt_counts[i] = marker.get("attempt", 1)
                self._step_was_previously_attempted = True
                self._previous_attempt_info = marker

        try:  # OUTER try: catches WorkflowAborted → _handle_abort
            _splice_mode = False  # Req 26: set True when emitter uses splice mode

            while i < len(self._steps):
                this_step = self._steps[i]
                step_name = self._get_step_name(this_step, i)

                # Write pre-execution marker before running step.
                # Only write when result saving is enabled — if checkpointing
                # is disabled, no markers should be written to disk.
                if _has_loops:
                    self._step_attempt_counts[i] = (
                        self._step_attempt_counts.get(i, 0) + 1
                    )
                    if self.enable_result_save and self.enable_result_save is not False:
                        self._save_step_in_progress_marker(
                            i, step_name, state, *args, **kwargs
                        )

                try:  # INNER try: per-step error handling
                    # Handle input arguments to the step:
                    # Req 26.4: Splice mode — first expanded step receives emitter's original input
                    _splice_step_idx = getattr(self, '_splice_step_index', None)
                    if _splice_step_idx is not None and i == _splice_step_idx:
                        _s_args = self._splice_orig_args or args
                        _s_kwargs = self._splice_orig_kwargs or kwargs
                        step_result = this_step(*_s_args, **_s_kwargs)
                        # Clean up splice state after first expanded step executes
                        del self._splice_orig_args
                        del self._splice_orig_kwargs
                        del self._splice_step_index
                    elif i > 0:
                        prev_step_result = step_result
                        nargs, nkwargs = self._get_args_for_downstream(
                            prev_step_result, args, kwargs
                        )
                        step_result = this_step(*nargs, **nkwargs)
                    else:
                        # For the very first step (i=0), there's no previous result.
                        step_result = this_step(*args, **kwargs)

                except WorkflowAborted:
                    # WorkflowAborted is a control-flow signal (e.g. consensus
                    # reached), not an error. Let it propagate directly to the
                    # outer handler instead of being logged as WorkflowStepError.
                    raise
                except Exception as err:
                    error_handler = getattr(this_step, 'error_handler', None)
                    if error_handler is not None:
                        step_result = error_handler(
                            err, step_result, state, step_name, i
                        )
                    else:
                        result_save_on_error_enabled = (
                            i > 0
                            and (not isinstance(self.enable_result_save, bool))
                            and self.enable_result_save == StepResultSaveOptions.OnError
                        )

                        self.log_error({
                            'step_failed': i,
                            'step_name': step_name,
                            'result_save_on_error_enabled': result_save_on_error_enabled,
                            'exception_type': type(err).__name__,
                            'exception_message': str(err),
                        }, log_type=WorkflowLogTypes.StepError)

                        if i > 0 and result_save_on_error_enabled:
                            self._save_result(
                                prev_step_result,
                                output_path=self._resolve_result_path(
                                    step_name or i, *args, **kwargs
                                ),
                            )
                        raise err

                # Expansion check: after step execution, BEFORE _post_process (Req 35)
                if isinstance(step_result, ExpansionResult):
                    # Req 27: Forbidden combination check
                    if getattr(this_step, 'loop_back_to', None) is not None:
                        raise ExpansionConfigError(
                            f"Step '{step_name}' has loop_back_to set and returned ExpansionResult. "
                            "This combination is forbidden."
                        )
                    actual_result = step_result.result
                    _splice_mode = step_result.mode == 'splice'
                    self._handle_expansion(i, step_result, state,
                                           orig_args=(nargs if i > 0 else args),
                                           orig_kwargs=(nkwargs if i > 0 else kwargs))
                    step_result = actual_result

                # After the step executes successfully, run the mandatory _post_process hook.
                _step_result = self._post_process(step_result, *args, **kwargs)
                if _step_result is not None:
                    step_result = _step_result

                # If optional post-processing is enabled both on the workflow and on this step,
                # run the _optional_post_process hook next.
                if getattr(this_step, 'enable_optional_post_process',
                           self.enable_optional_post_process):
                    _step_result = self._optional_post_process(
                        step_result, *args, **kwargs
                    )
                    if _step_result is not None:
                        step_result = _step_result

                # Update flow state (no-op when state is None).
                if state is not None:
                    state = self._update_state(
                        state, step_result, this_step, step_name, i
                    )
                    self._state = state

                # Save result based on the configured saving options.
                # Req 26: Skip result save for emitter step when splice mode is active
                enable_result_save = getattr(
                    this_step, 'enable_result_save', self.enable_result_save
                )
                if _splice_mode:
                    _splice_mode = False  # Reset after skipping save for emitter
                elif (enable_result_save is True
                        or enable_result_save == StepResultSaveOptions.Always):
                    if _has_loops:
                        self._exec_seq += 1
                        _current_result_id = self._make_seq_result_id(
                            step_name or i, self._exec_seq
                        )
                    else:
                        _current_result_id = step_name or i
                    self._save_result(
                        step_result,
                        output_path=self._resolve_result_path(
                            _current_result_id, *args, **kwargs
                        ),
                    )
                    _last_saved_result_id = _current_result_id

                # Loop check — only evaluated when the step has loop_back_to.
                loop_back_to = getattr(this_step, 'loop_back_to', None)
                if loop_back_to is not None:
                    loop_condition = getattr(this_step, 'loop_condition', None)
                    should_loop = (
                        loop_condition(state, step_result)
                        if loop_condition else False
                    )
                    if should_loop:
                        max_iters = getattr(
                            this_step, 'max_loop_iterations',
                            self.max_loop_iterations,
                        )
                        _lc_key = self._get_loop_count_key(this_step, i)
                        count = self._loop_counts.get(_lc_key, 0)
                        if count < max_iters:
                            self._loop_counts[_lc_key] = count + 1
                            target_i = self._resolve_step_index(
                                loop_back_to, self._steps
                            )
                            # Checkpoint: looping back
                            if _has_loops and _last_saved_result_id is not None:
                                self._save_loop_checkpoint(
                                    i, target_i, _last_saved_result_id,
                                    state, *args, **kwargs
                                )
                            if _has_loops:
                                self._clear_step_in_progress_marker(
                                    *args, **kwargs
                                )
                                self._step_was_previously_attempted = False
                                self._previous_attempt_info = None
                            i = target_i
                            continue  # jump back, skip _on_step_complete
                        else:
                            # Loop exhausted — invoke handler if present.
                            on_exhausted = getattr(
                                this_step, 'on_loop_exhausted', None
                            )
                            if on_exhausted:
                                on_exhausted(state, step_result)

                # Step-complete hook (only fires when NOT looping back).
                self._on_step_complete(
                    step_result, step_name, i, state, *args, **kwargs
                )

                # Checkpoint: advancing to next step
                if _has_loops and _last_saved_result_id is not None:
                    self._save_loop_checkpoint(
                        i, i + 1, _last_saved_result_id,
                        state, *args, **kwargs
                    )
                if _has_loops:
                    self._clear_step_in_progress_marker(*args, **kwargs)
                    self._step_was_previously_attempted = False
                    self._previous_attempt_info = None

                i += 1

        except WorkflowAborted as exc:
            return self._handle_abort(exc, step_result, state)

        # After completing all steps, return the final result of the last step.
        return step_result

    async def _arun(self, *args, **kwargs):
        # Reset per-run expansion state (C2 fix: prevents cross-run leaks)
        self._reset_expansion_state()

        # If no steps are defined, simply return as there's nothing to run.
        if not self._steps:
            return

        # Setup child workflows for recursive resume
        self._setup_child_workflows(self._state, *args, **kwargs)

        # Detect if any step uses loop_back_to — needed by both resume and save blocks.
        _has_loops = self._has_loop_steps()

        start_step_i = -1
        step_result = None
        prev_step_result = None
        _checkpoint = None
        _checkpoint_state = None
        _checkpoint_next_i = None

        if self.resume_with_saved_results is not False:
            # Try checkpoint-based resume for auto-resume with loops
            if _has_loops and self.resume_with_saved_results is True:
                _checkpoint = self._try_load_checkpoint(*args, **kwargs)

            if _checkpoint is not None:
                try:
                    _ckpt_result_id = _checkpoint["result_id"]
                    step_result = self._load_result(
                        result_id=_ckpt_result_id,
                        result_path_or_preloaded_result=self._resolve_result_path(
                            _ckpt_result_id, *args, **kwargs
                        ),
                    )
                except Exception:
                    self.log_warning(
                        "Checkpoint result file not found, falling back to backward scan",
                        log_type=WorkflowLogTypes.CheckpointWarning,
                    )
                    _checkpoint = None

            if _checkpoint is not None:
                start_step_i = _checkpoint["step_index"]
                self._loop_counts = _checkpoint.get("loop_counts", {})
                self._exec_seq = _checkpoint.get("exec_seq", 0)
                _checkpoint_state = _checkpoint.get("state")
                _checkpoint_next_i = _checkpoint["next_step_index"]
            else:
                # --- Existing backward scan (unchanged) ---
                saved_step_results_back_search_start_index = (
                    self.resume_with_saved_results
                    if isinstance(self.resume_with_saved_results, int)
                    else len(self._steps) - 1
                )

                for i in range(saved_step_results_back_search_start_index, -1, -1):
                    result_id = self._get_step_name(self._steps[i], i) or i
                    step_result_path = self._resolve_result_path(result_id, *args, **kwargs)
                    exists_step_result_or_preloaded_step_result = self._exists_result(
                        result_id=result_id, result_path=step_result_path
                    )

                    # Glob fallback for ___seqN results when loops are active
                    if _has_loops and not (
                        exists_step_result_or_preloaded_step_result is not None
                        and exists_step_result_or_preloaded_step_result is not False
                    ):
                        seq_path = self._glob_seq_results(step_result_path)
                        if seq_path is not None:
                            step_result_path = seq_path
                            exists_step_result_or_preloaded_step_result = True

                    if (
                            exists_step_result_or_preloaded_step_result is not None and
                            exists_step_result_or_preloaded_step_result is not False
                    ):
                        self.log_info((f'step {i} result exists', True))
                        start_step_i = i
                        break
                    else:
                        self.log_info((f'step {i} result exists', False))

                # Load the found result
                if start_step_i != -1:
                    step_result = self._load_result(
                        result_id=start_step_i,
                        result_path_or_preloaded_result=(
                            step_result_path if
                            isinstance(exists_step_result_or_preloaded_step_result, bool)
                            else exists_step_result_or_preloaded_step_result
                        )
                    )

        # --- State initialization ---
        _uses_state = any(
            getattr(s, 'update_state', None) is not None
            or getattr(s, 'receives_state', False)
            for s in self._steps
        )
        if _checkpoint_state is not None:
            state = _checkpoint_state
        else:
            state = self._init_state() if _uses_state else None
        self._state = state

        # Initialize loop-resume tracking variables.
        if _checkpoint is None:
            self._exec_seq = 0
            self._loop_counts = {}
        self._state_picklability_verified = False
        _last_saved_result_id = None

        # Step-in-progress tracking.
        # _step_attempt_counts accumulates across resume cycles (must persist
        # if already populated from a prior run's marker), while the per-run
        # flags are always reset so each run starts without stale state.
        if not hasattr(self, "_step_attempt_counts"):
            self._step_attempt_counts = {}
        self._step_was_previously_attempted = False
        self._previous_attempt_info = None

        # Determine starting step index.
        if _checkpoint_next_i is not None:
            i = _checkpoint_next_i
        else:
            i = start_step_i + 1

        # Detect partial step execution from prior run
        if _has_loops and _checkpoint is not None:
            marker = self._load_step_in_progress_marker(*args, **kwargs)
            if marker and marker.get("step_index") == i:
                self._step_attempt_counts[i] = marker.get("attempt", 1)
                self._step_was_previously_attempted = True
                self._previous_attempt_info = marker

        try:  # OUTER try: catches WorkflowAborted → _handle_abort
            _splice_mode = False  # Req 26: set True when emitter uses splice mode

            while i < len(self._steps):
                this_step = self._steps[i]
                step_name = self._get_step_name(this_step, i)

                # Write pre-execution marker before running step.
                # Only write when result saving is enabled — if checkpointing
                # is disabled, no markers should be written to disk.
                if _has_loops:
                    self._step_attempt_counts[i] = (
                        self._step_attempt_counts.get(i, 0) + 1
                    )
                    if self.enable_result_save and self.enable_result_save is not False:
                        self._save_step_in_progress_marker(
                            i, step_name, state, *args, **kwargs
                        )

                try:  # INNER try: per-step error handling
                    # Req 26.4: Splice mode — first expanded step receives emitter's original input
                    _splice_step_idx = getattr(self, '_splice_step_index', None)
                    if _splice_step_idx is not None and i == _splice_step_idx:
                        _s_args = self._splice_orig_args or args
                        _s_kwargs = self._splice_orig_kwargs or kwargs
                        step_result = await call_maybe_async(this_step, *_s_args, **_s_kwargs)
                        # Clean up splice state after first expanded step executes
                        del self._splice_orig_args
                        del self._splice_orig_kwargs
                        del self._splice_step_index
                    elif i > 0:
                        prev_step_result = step_result
                        nargs, nkwargs = self._get_args_for_downstream(
                            prev_step_result, args, kwargs
                        )
                        step_result = await call_maybe_async(this_step, *nargs, **nkwargs)
                    else:
                        step_result = await call_maybe_async(this_step, *args, **kwargs)

                except WorkflowAborted:
                    # WorkflowAborted is a control-flow signal (e.g. consensus
                    # reached), not an error. Let it propagate directly to the
                    # outer handler instead of being logged as WorkflowStepError.
                    raise
                except Exception as err:
                    error_handler = getattr(this_step, 'error_handler', None)
                    if error_handler is not None:
                        step_result = await call_maybe_async(
                            error_handler, err, step_result, state, step_name, i
                        )
                    else:
                        result_save_on_error_enabled = (
                            i > 0
                            and (not isinstance(self.enable_result_save, bool))
                            and self.enable_result_save == StepResultSaveOptions.OnError
                        )

                        self.log_error({
                            'step_failed': i,
                            'step_name': step_name,
                            'result_save_on_error_enabled': result_save_on_error_enabled,
                            'exception_type': type(err).__name__,
                            'exception_message': str(err),
                        }, log_type=WorkflowLogTypes.StepError)

                        if i > 0 and result_save_on_error_enabled:
                            self._save_result(
                                prev_step_result,
                                output_path=self._resolve_result_path(
                                    step_name or i, *args, **kwargs
                                ),
                            )
                        raise err

                # Expansion check: after step execution, BEFORE _post_process (Req 35)
                if isinstance(step_result, ExpansionResult):
                    # Req 27: Forbidden combination check
                    if getattr(this_step, 'loop_back_to', None) is not None:
                        raise ExpansionConfigError(
                            f"Step '{step_name}' has loop_back_to set and returned ExpansionResult. "
                            "This combination is forbidden."
                        )
                    actual_result = step_result.result
                    _splice_mode = step_result.mode == 'splice'
                    self._handle_expansion(i, step_result, state,
                                           orig_args=(nargs if i > 0 else args),
                                           orig_kwargs=(nkwargs if i > 0 else kwargs))
                    step_result = actual_result

                # Post-process hooks
                _step_result = await call_maybe_async(self._post_process, step_result, *args, **kwargs)
                if _step_result is not None:
                    step_result = _step_result

                if getattr(this_step, 'enable_optional_post_process',
                           self.enable_optional_post_process):
                    _step_result = await call_maybe_async(
                        self._optional_post_process, step_result, *args, **kwargs
                    )
                    if _step_result is not None:
                        step_result = _step_result

                # Update flow state (no-op when state is None).
                if state is not None:
                    state = await call_maybe_async(
                        self._update_state, state, step_result, this_step, step_name, i
                    )
                    self._state = state

                # Save result based on the configured saving options.
                # Req 26: Skip result save for emitter step when splice mode is active
                enable_result_save = getattr(
                    this_step, 'enable_result_save', self.enable_result_save
                )
                if _splice_mode:
                    _splice_mode = False  # Reset after skipping save for emitter
                elif (enable_result_save is True
                        or enable_result_save == StepResultSaveOptions.Always):
                    if _has_loops:
                        self._exec_seq += 1
                        _current_result_id = self._make_seq_result_id(
                            step_name or i, self._exec_seq
                        )
                    else:
                        _current_result_id = step_name or i
                    self._save_result(
                        step_result,
                        output_path=self._resolve_result_path(
                            _current_result_id, *args, **kwargs
                        ),
                    )
                    _last_saved_result_id = _current_result_id

                # Loop check — only evaluated when the step has loop_back_to.
                loop_back_to = getattr(this_step, 'loop_back_to', None)
                if loop_back_to is not None:
                    loop_condition = getattr(this_step, 'loop_condition', None)
                    should_loop = (
                        await call_maybe_async(loop_condition, state, step_result)
                        if loop_condition else False
                    )
                    if should_loop:
                        max_iters = getattr(
                            this_step, 'max_loop_iterations',
                            self.max_loop_iterations,
                        )
                        _lc_key = self._get_loop_count_key(this_step, i)
                        count = self._loop_counts.get(_lc_key, 0)
                        if count < max_iters:
                            self._loop_counts[_lc_key] = count + 1
                            target_i = self._resolve_step_index(
                                loop_back_to, self._steps
                            )
                            # Checkpoint: looping back
                            if _has_loops and _last_saved_result_id is not None:
                                self._save_loop_checkpoint(
                                    i, target_i, _last_saved_result_id,
                                    state, *args, **kwargs
                                )
                            if _has_loops:
                                self._clear_step_in_progress_marker(
                                    *args, **kwargs
                                )
                                self._step_was_previously_attempted = False
                                self._previous_attempt_info = None
                            i = target_i
                            continue  # jump back, skip _on_step_complete
                        else:
                            on_exhausted = getattr(
                                this_step, 'on_loop_exhausted', None
                            )
                            if on_exhausted:
                                await call_maybe_async(on_exhausted, state, step_result)

                # Step-complete hook (only fires when NOT looping back).
                await call_maybe_async(
                    self._on_step_complete, step_result, step_name, i, state, *args, **kwargs
                )

                # Checkpoint: advancing to next step
                if _has_loops and _last_saved_result_id is not None:
                    self._save_loop_checkpoint(
                        i, i + 1, _last_saved_result_id,
                        state, *args, **kwargs
                    )
                if _has_loops:
                    self._clear_step_in_progress_marker(*args, **kwargs)
                    self._step_was_previously_attempted = False
                    self._previous_attempt_info = None

                i += 1

        except WorkflowAborted as exc:
            return await call_maybe_async(self._handle_abort, exc, step_result, state)

        return step_result


# --- CheckpointState (jsonfy-mode only) ---
# Defined after Workflow to use it as @artifact_type target.

@artifact_type(Workflow, type='json', group='workflows')
@attrs(slots=False)
class CheckpointState:
    """Wrapper for checkpoint state dict with artifact metadata for jsonfy mode.

    Only instantiated when checkpoint_mode='jsonfy'; pickle mode saves
    raw dicts directly via pickle_save(..., enable_parts=True).
    """
    version = attrib(default=1)
    exec_seq = attrib(default=0)
    step_index = attrib(default=0)
    result_id = attrib(default=None)
    next_step_index = attrib(default=0)
    loop_counts = attrib(factory=dict)
    state = attrib(default=None)
    expansions = attrib(factory=list)


# Update the module-level forward reference used by _try_load_checkpoint and _save_loop_checkpoint.
# This replaces the None sentinel defined at the top of the module.
globals()['CheckpointState'] = CheckpointState

