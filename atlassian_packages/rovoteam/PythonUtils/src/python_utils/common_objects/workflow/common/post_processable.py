from abc import ABC

from attr import attrs, attrib


@attrs(slots=False)
class PostProcessable(ABC):
    """
    Base class for enabling post-processing hooks in a workflow.

    Attributes:
        enable_optional_post_process (bool):
            If True, enables the optional post-processing hook.

    Note:
        To customize the behavior of post-processing, override the `_post_process`, `_optional_post_process`,
        and/or `post_process` methods in subclasses. These methods are called in sequence to modify or inspect
        the result of each step in a workflow.

        - `_post_process`: Used for mandatory post-processing immediately after a step.
        - `_optional_post_process`: Invoked after `_post_process` if `enable_optional_post_process` is True.
        - `post_process`: Combines both `_post_process` and `_optional_post_process` and serves as a single
          entry point for custom post-processing logic.
    """
    enable_optional_post_process = attrib(type=bool, default=False)

    def _post_process(self, result, *args, **kwargs):
        """
        Hook for processing the result immediately after a step.

        Args:
            result (Any): The result returned by the step.
            *args: Positional arguments passed to the workflow's run method.
            **kwargs: Keyword arguments passed to the workflow's run method.

        Returns:
            Optional[Any]: The modified result. Return None to keep the original result.
        """
        return result

    def _optional_post_process(self, result, *args, **kwargs):
        """
        Optional hook for additional processing after `_post_process`.

        Args:
            result (Any): The result after `_post_process`.
            *args: Positional arguments passed to the workflow's run method.
            **kwargs: Keyword arguments passed to the workflow's run method.

        Returns:
            Optional[Any]: The modified result. Return None to keep the original result.
        """
        return result

    def post_process(self, result, *args, **kwargs):
        """
        Combines the mandatory and optional post-processing hooks.

        Args:
            result (Any): The result from a workflow step.
            *args: Positional arguments passed to the workflow's run method.
            **kwargs: Keyword arguments passed to the workflow's run method.

        Returns:
            Any: The final result after applying `_post_process` and `_optional_post_process`.

        Note:
            You can override this method in a subclass to completely redefine the
            post-processing logic. By default, this method calls `_post_process`
            followed by `_optional_post_process`.
        """
        result = self._post_process(result, *args, **kwargs)
        if self._optional_post_process:
            return self._optional_post_process(result, *args, **kwargs)
