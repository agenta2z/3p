import logging
import os
from abc import ABC
from enum import Enum
from os import path
from typing import Union, Any

from attr import attrs, attrib
from attr.validators import in_

from python_utils.common_objects.workflow.common.step_result_save_options import \
    StepResultSaveOptions
from python_utils.io_utils.pickle_io import pickle_save, pickle_load

logger = logging.getLogger(__name__)


class CheckpointMode(str, Enum):
    PICKLE = 'pickle'
    JSONFY = 'jsonfy'


def _ensure_parts_dir(file_path):
    """Strip .pkl/.json extension to get the directory path for parts mode."""
    base, ext = os.path.splitext(file_path)
    if ext in ('.pkl', '.json'):
        return base
    return file_path


def _ensure_json_extension(file_path):
    """Ensure the path has a .json extension."""
    base, ext = os.path.splitext(file_path)
    if ext != '.json':
        return file_path + '.json'
    return file_path


@attrs(slots=False)
class Resumable(ABC):
    """
    Base class for workflows that support saving and resuming.

    Attributes:
        enable_result_save (Union[StepResultSaveOptions, bool, str]): Enables/disables result saving.
            Supported options:
                - StepResultSaveOptions.NoSave
                - StepResultSaveOptions.Always
                - StepResultSaveOptions.OnError
                - True (equivalent to StepResultSaveOptions.Always)
                - False (equivalent to StepResultSaveOptions.NoSave)
        resume_with_saved_results (bool): If True, resumes the workflow using saved results.
        checkpoint_mode (str): Checkpoint serialization mode ('pickle' or 'jsonfy').
    """
    enable_result_save = attrib(
        type=Union[StepResultSaveOptions, bool, str],
        default=False
    )
    resume_with_saved_results = attrib(type=bool, default=False)
    checkpoint_mode = attrib(
        type=str,
        default='pickle',
        validator=in_(['pickle', 'jsonfy'])
    )
    _result_root_override = attrib(default=None, init=False, repr=False)

    def _resolve_result_path(self, result_id: Any, *args, **kwargs) -> str:
        """Wraps _get_result_path and applies _result_root_override when set.

        When _result_root_override is None, returns the original path.
        When set, returns os.path.join(_result_root_override, basename(original_path)).
        """
        original_path = self._get_result_path(result_id, *args, **kwargs)
        if self._result_root_override is not None:
            return os.path.join(self._result_root_override, os.path.basename(original_path))
        return original_path

    def _save_result(self, result, output_path: str):
        """
        Saves the result to a path, dispatching by checkpoint_mode.

        Args:
            result (Any): The result object to save.
            output_path (str): The path where the result will be saved.
        """
        if self.checkpoint_mode == 'jsonfy':
            self._save_result_jsonfy(result, output_path)
        else:
            dir_path = _ensure_parts_dir(output_path)
            artifact_types = getattr(type(self), '__artifact_types__', None)
            pickle_save(
                result, dir_path, enable_parts=True,
                artifact_types=artifact_types,
                verbose=getattr(self, 'verbose', False)
            )

    def _load_result(self, result_id: Any, result_path_or_preloaded_result: Union[str, Any]):
        """
        Loads a previously saved step result from a path, or can also pass in a preloaded result object.

        Args:
            result_id (Any): The identifier for the step.
            result_path_or_preloaded_result (Union[str, Any]): Path or preloaded result object.

        Returns:
            Any: The loaded result.
        """
        if isinstance(result_path_or_preloaded_result, str):
            if self.checkpoint_mode == 'jsonfy':
                return self._load_result_jsonfy(result_path_or_preloaded_result)
            dir_path = _ensure_parts_dir(result_path_or_preloaded_result)
            # Try parts directory first
            if os.path.isdir(dir_path) and os.path.exists(os.path.join(dir_path, "main.pkl")):
                return pickle_load(dir_path, enable_parts=True)
            # Backward compat: try loading as plain pickle file
            return pickle_load(result_path_or_preloaded_result)
        else:
            return result_path_or_preloaded_result

    def _exists_result(self, result_id: Any, result_path: str) -> Union[bool, Any]:
        """
        Checks whether a step result exists at the given path.

        Args:
            result_id (Any): The index of the step to check.
            result_path (str): The file path to check for the step result.

        Returns:
            Union[bool, Any]: Returns True if the result exists, False otherwise.
                Subclasses can override this to implement custom existence checks or return preloaded results.
        """
        if self.checkpoint_mode == 'jsonfy':
            return os.path.exists(_ensure_json_extension(result_path))
        dir_path = _ensure_parts_dir(result_path)
        if os.path.isdir(dir_path) and os.path.exists(os.path.join(dir_path, "main.pkl")):
            return True
        return path.exists(result_path)  # backward compat

    def _get_result_path(self, result_id: Any, *args, **kwargs) -> str:
        """
        Abstract method to define the path for saving/loading results.

        Args:
            result_id (Any): The identifier for the result.
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            str: The path for saving/loading the result.
        """
        raise NotImplementedError

    # --- Jsonfy helpers ---

    def _save_result_jsonfy(self, result, output_path: str):
        """Save result via jsonfy serialization (write_json calls jsonfy internally)."""
        from python_utils.io_utils.json_io import write_json
        json_path = _ensure_json_extension(output_path)
        write_json(result, json_path, save_type='separate')

    def _load_result_jsonfy(self, result_path: str):
        """Load result from jsonfy-serialized checkpoint."""
        from python_utils.io_utils.json_io import read_json, resolve_json_parts, dejsonfy
        json_path = _ensure_json_extension(result_path)
        data = read_json(json_path)

        # Resolve parts references (pass the json file path, not parts dir)
        data = resolve_json_parts(data, json_path)

        # Try type-aware reconstruction via .types.json
        types_file = json_path + '.types.json'
        if os.path.exists(types_file):
            try:
                return dejsonfy(data, type_file=types_file)
            except Exception as e:
                logger.warning(
                    f"Failed to reconstruct typed object from {types_file}: {e}. "
                    f"Falling back to raw dict."
                )
                return data
        else:
            logger.warning(
                f"No .types.json found at {types_file}. Returning raw dict."
            )
            return data
