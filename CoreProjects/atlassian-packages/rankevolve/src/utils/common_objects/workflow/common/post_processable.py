from abc import ABC

from attr import attrib, attrs


@attrs(slots=False)
class PostProcessable(ABC):
    """Base class for enabling post-processing hooks in a workflow.

    Attributes:
        enable_optional_post_process: If True, enables the optional post-processing hook.
    """

    enable_optional_post_process = attrib(type=bool, default=False)

    def _post_process(self, result, *args, **kwargs):
        """Hook for processing the result immediately after a step."""
        return result

    def _optional_post_process(self, result, *args, **kwargs):
        """Optional hook for additional processing after _post_process."""
        return result

    def post_process(self, result, *args, **kwargs):
        """Combines the mandatory and optional post-processing hooks."""
        result = self._post_process(result, *args, **kwargs)
        if self._optional_post_process:
            return self._optional_post_process(result, *args, **kwargs)
