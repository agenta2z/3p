"""StepWrapper — attach per-step attributes to any callable.

Bound methods don't support arbitrary attribute assignment.  This wrapper
class allows attaching attributes like ``name``, ``loop_back_to``,
``loop_condition``, ``update_state``, etc. to any callable so that
:class:`Workflow` can inspect them during execution.
"""


class StepWrapper:
    """Wraps a callable so per-step attributes can be attached.

    Example::

        step = StepWrapper(
            self._step_review_impl,
            name="review",
            loop_back_to="propose",
            loop_condition=lambda state, result: not state.get("done"),
        )
        step(some_arg)  # delegates to self._step_review_impl(some_arg)
    """

    def __init__(self, fn, **kwargs):
        self._fn = fn
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __call__(self, *args, **kwargs):
        return self._fn(*args, **kwargs)
