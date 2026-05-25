"""Workflow — sequential step orchestrator with loop-resume support.

Ported from RichPythonUtils with all imports updated to rankevolve paths.
"""

import glob
import json
import os
import pickle
import re
import shutil
from abc import ABC
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, Optional, Sequence, Union

from attr import attrib, attrs
from rankevolve.src.utils.common_objects.workflow.common.exceptions import (
    WorkflowAborted,
)
from rankevolve.src.utils.common_objects.workflow.common.result_pass_down_mode import (
    ResultPassDownMode,
)
from rankevolve.src.utils.common_objects.workflow.common.step_result_save_options import (
    StepResultSaveOptions,
)
from rankevolve.src.utils.common_objects.workflow.common.worknode_base import (
    WorkNodeBase,
)
from rankevolve.src.utils.common_utils.async_utils import call_maybe_async
from rankevolve.src.utils.io_utils.artifact import artifact_type
from rankevolve.src.utils.io_utils.pickle_io import _get_field_names


# Forward reference: CheckpointState is defined after Workflow to avoid circular dependency.
CheckpointState = None  # replaced below after Workflow class definition


@attrs(slots=False)
class Workflow(WorkNodeBase, ABC):
    """Orchestrates a sequence of computational steps with support for
    resuming, saving, and post-processing.

    Supports:
    1. Executing a predefined sequence of steps (callables).
    2. Optional hooks for processing results after each step.
    3. Saving and loading intermediate step results to facilitate resuming.
    4. Configurable loop-back with checkpoint-based resume.
    """

    _steps = attrib(type=Sequence[Callable], default=None)
    _state = attrib(default=None, init=False)
    max_loop_iterations = attrib(type=int, default=10)

    # ------------------------------------------------------------------
    # State & step hooks (override in subclasses)
    # ------------------------------------------------------------------

    def _init_state(self) -> dict:
        """Initialize flow state. Override for custom initial state."""
        return {}

    def _get_step_name(self, step, index) -> Optional[str]:
        """Get step name via per-step attribute pattern."""
        return getattr(step, "name", None)

    def _update_state(self, state, result, step, step_name, step_index) -> dict:
        """Update state after a step completes.

        Delegates to a per-step ``update_state`` attribute if present.
        """
        updater = getattr(step, "update_state", None)
        if updater is not None:
            updated = updater(state, result)
            if updated is not None:
                return updated
        return state

    def _on_step_complete(self, result, step_name, step_index, state, *args, **kwargs):
        """Hook called after a step completes (only on non-loop-back iterations)."""
        return None

    def _default_error_handler(
        self, error, step_result_so_far, state, step_name, step_index
    ):
        """Default error handler — re-raises."""
        raise error

    def _handle_abort(self, abort_exc, step_result, state):
        """Handle a WorkflowAborted exception.

        Default: return *step_result*. Subclasses override to build a
        richer partial result from *abort_exc* and *state*.
        """
        return step_result

    def _resolve_step_index(self, target, steps) -> int:
        """Resolve a *loop_back_to* target (name or int) to a step index."""
        if isinstance(target, int):
            return target
        for idx, step in enumerate(steps):
            if getattr(step, "name", None) == target:
                return idx
        raise ValueError(f"Loop target step '{target}' not found")

    # ------------------------------------------------------------------
    # Loop + resume checkpoint helpers
    # ------------------------------------------------------------------

    def _has_loop_steps(self) -> bool:
        """Detect if any step uses loop_back_to."""
        return any(
            getattr(s, "loop_back_to", None) is not None for s in (self._steps or ())
        )

    @staticmethod
    def _make_seq_result_id(step_name_or_index, exec_seq) -> str:
        """Return a unique result ID with a sequence number suffix."""
        return f"{step_name_or_index}___seq{exec_seq}"

    def _save_checkpoint(self, checkpoint_dict, *args, **kwargs):
        """Save a workflow checkpoint."""
        checkpoint_path = self._resolve_result_path("__wf_checkpoint__", *args, **kwargs)
        self._save_result(checkpoint_dict, output_path=checkpoint_path)

    def _try_load_checkpoint(self, *args, **kwargs) -> Optional[dict]:
        """Try loading a checkpoint. Returns None on any failure."""
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
            return ckpt
        except Exception:
            return None

    def _save_loop_checkpoint(
        self, step_index, next_step_index, last_saved_result_id, state, *args, **kwargs
    ):
        """Save a loop checkpoint after the loop decision is resolved.

        Shared by both _run() and _arun() to avoid duplication.
        """
        # Setup child workflows before saving so they have inherited config
        self._setup_child_workflows(state, *args, **kwargs)

        # Validate serializability on first checkpoint only.
        if not getattr(self, "_state_picklability_verified", False):
            if self.checkpoint_mode == 'jsonfy':
                try:
                    from rankevolve.src.utils.io_utils.json_io import jsonfy
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
            "version": 1,
            "exec_seq": self._exec_seq,
            "step_index": step_index,
            "result_id": last_saved_result_id,
            "next_step_index": next_step_index,
            "loop_counts": dict(self._loop_counts),
            "state": state,
        }

        if self.checkpoint_mode == 'jsonfy' and CheckpointState is not None:
            checkpoint_dict = CheckpointState(**checkpoint_dict)

        self._save_checkpoint(checkpoint_dict, *args, **kwargs)

    # ------------------------------------------------------------------
    # Step-in-progress marker (pre-execution crash detection)
    # ------------------------------------------------------------------

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
        except OSError:
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

    def _get_step_identifier(self, step: Callable, index: int) -> Dict[str, Any]:
        """Get serializable identifier for a step callable."""
        identifier = {
            "index": index,
            "name": None,
            "module": None,
            "ref": None,
        }
        if hasattr(step, "__name__"):
            identifier["name"] = step.__name__
        if hasattr(step, "__module__"):
            identifier["module"] = step.__module__
        if identifier["name"] and identifier["module"]:
            identifier["ref"] = f"{identifier['module']}.{identifier['name']}"
        return identifier

    def to_serializable_obj(
        self, mode: str = "auto", _output_format: Optional[str] = None
    ) -> Dict[str, Any]:
        """Serialize Workflow to dict."""
        result_pass_down_mode_str = self.result_pass_down_mode
        if isinstance(self.result_pass_down_mode, ResultPassDownMode):
            result_pass_down_mode_str = self.result_pass_down_mode.value
        elif callable(self.result_pass_down_mode):
            if hasattr(self.result_pass_down_mode, "__name__"):
                result_pass_down_mode_str = (
                    f"callable:{self.result_pass_down_mode.__module__}."
                    f"{self.result_pass_down_mode.__name__}"
                )
            else:
                result_pass_down_mode_str = None

        step_identifiers = []
        if self._steps:
            for i, step in enumerate(self._steps):
                step_identifiers.append(self._get_step_identifier(step, i))

        return {
            "_type": type(self).__name__,
            "_module": type(self).__module__,
            "version": "1.0",
            "name": self.name,
            "steps": step_identifiers,
            "config": {
                "enable_result_save": (
                    self.enable_result_save.value
                    if isinstance(self.enable_result_save, StepResultSaveOptions)
                    else self.enable_result_save
                ),
                "resume_with_saved_results": self.resume_with_saved_results,
                "result_pass_down_mode": result_pass_down_mode_str,
                "enable_optional_post_process": self.enable_optional_post_process,
            },
        }

    # ------------------------------------------------------------------
    # Child Workflow discovery and setup (recursive resume)
    # ------------------------------------------------------------------

    def _find_child_workflows_in(self, source):
        """Find child Workflow instances in a source object using artifact metadata."""
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
        """Discover and configure child Workflow instances for recursive resume."""
        if state is None:
            return

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

    @staticmethod
    def _glob_seq_results(step_result_path):
        """Find ___seqN results for a step, matching file, directory, and jsonfy formats.

        Returns the path of the highest-numbered seq result, or None if none found.
        """
        base_dir = os.path.dirname(step_result_path)
        base_name_parts = os.path.basename(step_result_path).rsplit('.', 1)
        stem = base_name_parts[0]

        # Try file pattern first (legacy: step_name___seq1.pkl)
        pattern = os.path.join(base_dir, f"{stem}___seq*")
        if len(base_name_parts) > 1:
            pattern += f".{base_name_parts[1]}"
        matches = glob.glob(pattern)
        # Filter out .json files from the file pattern
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
    # Shared resume logic (backward scan)
    # ------------------------------------------------------------------

    def _backward_scan_resume(self, _has_loops, *args, **kwargs):
        """Backward scan for saved step results. Returns (start_step_i, step_result)."""
        saved_step_results_back_search_start_index = (
            self.resume_with_saved_results
            if isinstance(self.resume_with_saved_results, int)
            else len(self._steps) - 1
        )

        start_step_i = -1
        step_result = None
        step_result_path = None
        exists_step_result_or_preloaded_step_result = None

        for i in range(saved_step_results_back_search_start_index, -1, -1):
            result_id = self._get_step_name(self._steps[i], i) or i
            step_result_path = self._resolve_result_path(result_id, *args, **kwargs)
            exists_step_result_or_preloaded_step_result = self._exists_result(
                result_id=result_id, result_path=step_result_path
            )

            if _has_loops and not (
                exists_step_result_or_preloaded_step_result is not None
                and exists_step_result_or_preloaded_step_result is not False
            ):
                seq_path = Workflow._glob_seq_results(step_result_path)
                if seq_path is not None:
                    step_result_path = seq_path
                    exists_step_result_or_preloaded_step_result = True

            if (
                exists_step_result_or_preloaded_step_result is not None
                and exists_step_result_or_preloaded_step_result is not False
            ):
                self.log_info((f"step {i} result exists", True))
                start_step_i = i
                break
            else:
                self.log_info((f"step {i} result exists", False))

        if start_step_i != -1:
            step_result = self._load_result(
                result_id=start_step_i,
                result_path_or_preloaded_result=(
                    step_result_path
                    if isinstance(exists_step_result_or_preloaded_step_result, bool)
                    else exists_step_result_or_preloaded_step_result
                ),
            )

        return start_step_i, step_result

    # ------------------------------------------------------------------
    # Sync _run
    # ------------------------------------------------------------------

    def _run(self, *args, **kwargs):
        if not self._steps:
            return

        _has_loops = self._has_loop_steps()

        # Setup child workflows for recursive resume
        self._setup_child_workflows(self._state, *args, **kwargs)

        start_step_i = -1
        step_result = None
        prev_step_result = None
        _checkpoint = None
        _checkpoint_state = None
        _checkpoint_next_i = None

        if self.resume_with_saved_results is not False:
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
                        "Checkpoint result file not found, falling back to backward scan"
                    )
                    _checkpoint = None

            if _checkpoint is not None:
                start_step_i = _checkpoint["step_index"]
                self._loop_counts = _checkpoint.get("loop_counts", {})
                self._exec_seq = _checkpoint.get("exec_seq", 0)
                _checkpoint_state = _checkpoint.get("state")
                _checkpoint_next_i = _checkpoint["next_step_index"]
            else:
                start_step_i, step_result = self._backward_scan_resume(
                    _has_loops, *args, **kwargs
                )

        # --- State initialization ---
        _uses_state = any(
            getattr(s, "update_state", None) is not None
            or getattr(s, "receives_state", False)
            for s in self._steps
        )
        if _checkpoint_state is not None:
            state = _checkpoint_state
        else:
            state = self._init_state() if _uses_state else None
        self._state = state

        # Setup child workflows after state initialization
        self._setup_child_workflows(state, *args, **kwargs)

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

        try:
            while i < len(self._steps):
                this_step = self._steps[i]
                step_name = self._get_step_name(this_step, i)

                # Write pre-execution marker before running step
                if _has_loops:
                    self._step_attempt_counts[i] = (
                        self._step_attempt_counts.get(i, 0) + 1
                    )
                    self._save_step_in_progress_marker(
                        i, step_name, state, *args, **kwargs
                    )

                try:
                    if i > 0:
                        prev_step_result = step_result
                        nargs, nkwargs = self._get_args_for_downstream(
                            prev_step_result, args, kwargs
                        )
                        step_result = this_step(*nargs, **nkwargs)
                    else:
                        step_result = this_step(*args, **kwargs)

                except Exception as err:
                    error_handler = getattr(this_step, "error_handler", None)
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
                        self.log_error(
                            {
                                "step_failed": i,
                                "result_save_on_error_enabled": result_save_on_error_enabled,
                            }
                        )
                        if i > 0 and result_save_on_error_enabled:
                            self._save_result(
                                prev_step_result,
                                output_path=self._resolve_result_path(
                                    step_name or i, *args, **kwargs
                                ),
                            )
                        raise err

                _step_result = self._post_process(step_result, *args, **kwargs)
                if _step_result is not None:
                    step_result = _step_result

                if getattr(
                    this_step,
                    "enable_optional_post_process",
                    self.enable_optional_post_process,
                ):
                    _step_result = self._optional_post_process(
                        step_result, *args, **kwargs
                    )
                    if _step_result is not None:
                        step_result = _step_result

                if state is not None:
                    state = self._update_state(
                        state, step_result, this_step, step_name, i
                    )
                    self._state = state

                enable_result_save = getattr(
                    this_step, "enable_result_save", self.enable_result_save
                )
                if (
                    enable_result_save is True
                    or enable_result_save == StepResultSaveOptions.Always
                ):
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

                loop_back_to = getattr(this_step, "loop_back_to", None)
                if loop_back_to is not None:
                    loop_condition = getattr(this_step, "loop_condition", None)
                    should_loop = (
                        loop_condition(state, step_result) if loop_condition else False
                    )
                    if should_loop:
                        max_iters = getattr(
                            this_step, "max_loop_iterations", self.max_loop_iterations
                        )
                        count = self._loop_counts.get(i, 0)
                        if count < max_iters:
                            self._loop_counts[i] = count + 1
                            target_i = self._resolve_step_index(
                                loop_back_to, self._steps
                            )
                            if _has_loops and _last_saved_result_id is not None:
                                self._save_loop_checkpoint(
                                    i,
                                    target_i,
                                    _last_saved_result_id,
                                    state,
                                    *args,
                                    **kwargs,
                                )
                            if _has_loops:
                                self._clear_step_in_progress_marker(
                                    *args, **kwargs
                                )
                                self._step_was_previously_attempted = False
                                self._previous_attempt_info = None
                            i = target_i
                            continue
                        else:
                            on_exhausted = getattr(this_step, "on_loop_exhausted", None)
                            if on_exhausted:
                                on_exhausted(state, step_result)

                self._on_step_complete(
                    step_result, step_name, i, state, *args, **kwargs
                )

                if _has_loops and _last_saved_result_id is not None:
                    self._save_loop_checkpoint(
                        i, i + 1, _last_saved_result_id, state, *args, **kwargs
                    )
                if _has_loops:
                    self._clear_step_in_progress_marker(*args, **kwargs)
                    self._step_was_previously_attempted = False
                    self._previous_attempt_info = None

                i += 1

        except WorkflowAborted as exc:
            return self._handle_abort(exc, step_result, state)

        return step_result

    # ------------------------------------------------------------------
    # Async _arun
    # ------------------------------------------------------------------

    async def _arun(self, *args, **kwargs):
        if not self._steps:
            return

        _has_loops = self._has_loop_steps()

        # Setup child workflows for recursive resume
        self._setup_child_workflows(self._state, *args, **kwargs)

        start_step_i = -1
        step_result = None
        prev_step_result = None
        _checkpoint = None
        _checkpoint_state = None
        _checkpoint_next_i = None

        if self.resume_with_saved_results is not False:
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
                        "Checkpoint result file not found, falling back to backward scan"
                    )
                    _checkpoint = None

            if _checkpoint is not None:
                start_step_i = _checkpoint["step_index"]
                self._loop_counts = _checkpoint.get("loop_counts", {})
                self._exec_seq = _checkpoint.get("exec_seq", 0)
                _checkpoint_state = _checkpoint.get("state")
                _checkpoint_next_i = _checkpoint["next_step_index"]
            else:
                start_step_i, step_result = self._backward_scan_resume(
                    _has_loops, *args, **kwargs
                )

        # --- State initialization ---
        _uses_state = any(
            getattr(s, "update_state", None) is not None
            or getattr(s, "receives_state", False)
            for s in self._steps
        )
        if _checkpoint_state is not None:
            state = _checkpoint_state
        else:
            state = self._init_state() if _uses_state else None
        self._state = state

        # Setup child workflows after state initialization
        self._setup_child_workflows(state, *args, **kwargs)

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

        try:
            while i < len(self._steps):
                this_step = self._steps[i]
                step_name = self._get_step_name(this_step, i)

                # Write pre-execution marker before running step
                if _has_loops:
                    self._step_attempt_counts[i] = (
                        self._step_attempt_counts.get(i, 0) + 1
                    )
                    self._save_step_in_progress_marker(
                        i, step_name, state, *args, **kwargs
                    )

                try:
                    if i > 0:
                        prev_step_result = step_result
                        nargs, nkwargs = self._get_args_for_downstream(
                            prev_step_result, args, kwargs
                        )
                        step_result = await call_maybe_async(
                            this_step, *nargs, **nkwargs
                        )
                    else:
                        step_result = await call_maybe_async(this_step, *args, **kwargs)

                except Exception as err:
                    error_handler = getattr(this_step, "error_handler", None)
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
                        self.log_error(
                            {
                                "step_failed": i,
                                "result_save_on_error_enabled": result_save_on_error_enabled,
                            }
                        )
                        if i > 0 and result_save_on_error_enabled:
                            self._save_result(
                                prev_step_result,
                                output_path=self._resolve_result_path(
                                    step_name or i, *args, **kwargs
                                ),
                            )
                        raise err

                _step_result = await call_maybe_async(
                    self._post_process, step_result, *args, **kwargs
                )
                if _step_result is not None:
                    step_result = _step_result

                if getattr(
                    this_step,
                    "enable_optional_post_process",
                    self.enable_optional_post_process,
                ):
                    _step_result = await call_maybe_async(
                        self._optional_post_process, step_result, *args, **kwargs
                    )
                    if _step_result is not None:
                        step_result = _step_result

                if state is not None:
                    state = await call_maybe_async(
                        self._update_state,
                        state,
                        step_result,
                        this_step,
                        step_name,
                        i,
                    )
                    self._state = state

                enable_result_save = getattr(
                    this_step, "enable_result_save", self.enable_result_save
                )
                if (
                    enable_result_save is True
                    or enable_result_save == StepResultSaveOptions.Always
                ):
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

                loop_back_to = getattr(this_step, "loop_back_to", None)
                if loop_back_to is not None:
                    loop_condition = getattr(this_step, "loop_condition", None)
                    should_loop = (
                        await call_maybe_async(loop_condition, state, step_result)
                        if loop_condition
                        else False
                    )
                    if should_loop:
                        max_iters = getattr(
                            this_step, "max_loop_iterations", self.max_loop_iterations
                        )
                        count = self._loop_counts.get(i, 0)
                        if count < max_iters:
                            self._loop_counts[i] = count + 1
                            target_i = self._resolve_step_index(
                                loop_back_to, self._steps
                            )
                            if _has_loops and _last_saved_result_id is not None:
                                self._save_loop_checkpoint(
                                    i,
                                    target_i,
                                    _last_saved_result_id,
                                    state,
                                    *args,
                                    **kwargs,
                                )
                            if _has_loops:
                                self._clear_step_in_progress_marker(
                                    *args, **kwargs
                                )
                                self._step_was_previously_attempted = False
                                self._previous_attempt_info = None
                            i = target_i
                            continue
                        else:
                            on_exhausted = getattr(this_step, "on_loop_exhausted", None)
                            if on_exhausted:
                                await call_maybe_async(on_exhausted, state, step_result)

                await call_maybe_async(
                    self._on_step_complete,
                    step_result,
                    step_name,
                    i,
                    state,
                    *args,
                    **kwargs,
                )

                if _has_loops and _last_saved_result_id is not None:
                    self._save_loop_checkpoint(
                        i, i + 1, _last_saved_result_id, state, *args, **kwargs
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


# Update the module-level forward reference used by _try_load_checkpoint and _save_loop_checkpoint.
globals()['CheckpointState'] = CheckpointState
