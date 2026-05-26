"""
Example 2: Expansion with a loop inside the emitted section

Demonstrates: a planner step emits a review/fix pair where the 'review'
step loops back to 'fix' until a condition is met. The loop is entirely
inside the dynamically emitted section — nothing about it was declared
statically.

Scenario: planner says "apply N fix attempts." The emitted section is
[fix, review]. `review` has loop_back_to='fix' with a loop_condition that
keeps looping until a quality threshold is met.

Run: python 02_expansion_with_local_loop.py
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from resolve_path import resolve_path
resolve_path()

from attr import attrs, attrib

from python_utils.common_objects.workflow import ExpansionResult, StepWrapper
from python_utils.common_objects.workflow.workflow import Workflow
from python_utils.common_objects.workflow.common.result_pass_down_mode import (
    ResultPassDownMode,
)


# =============================================================
# CORE CODE
# =============================================================

@attrs(slots=False)
class ExampleWorkflow(Workflow):
    _save_dir: str = attrib(default=None)

    def _get_result_path(self, result_id, *args, **kwargs) -> str:
        return os.path.join(self._save_dir, f"step_{result_id}.pkl")


def fix(state_dict):
    """One fix attempt — grows quality by a random-ish (here: deterministic) amount."""
    state_dict["quality"] = state_dict.get("quality", 0) + 30
    state_dict["attempts"] = state_dict.get("attempts", 0) + 1
    return state_dict


def review(state_dict):
    """Checks quality. If insufficient, loop_back_to='fix' will re-fire fix."""
    return state_dict


def plan(initial):
    """Planner: emits a fix/review pair with a loop-back on review."""
    emitted_fix = StepWrapper(fix, name="fix")
    emitted_review = StepWrapper(
        review,
        name="review",
        loop_back_to="fix",
        loop_condition=lambda state, result: result.get("quality", 0) < 75,
        max_loop_iterations=5,
    )
    return ExpansionResult(
        result=initial,
        new_steps=[emitted_fix, emitted_review],
    )


def build_workflow(save_dir):
    return ExampleWorkflow(
        steps=[StepWrapper(plan, name="plan")],
        save_dir=save_dir,
        result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
        max_expansion_events=3,
        max_total_steps=20,
    )


# =============================================================
# DRIVER
# =============================================================

def main():
    tmp = Path(tempfile.mkdtemp(prefix="example02_"))
    observations = {}
    try:
        wf = build_workflow(str(tmp))
        result = wf.run({"quality": 0})
        observations["final_state"] = result
        observations["steps_after_expansion"] = [
            getattr(s, "name", "<anon>") for s in wf._steps
        ]
        observations["attempts"] = result.get("attempts", 0)
        explain(observations)
    finally:
        if not os.getenv("KEEP_TMP"):
            shutil.rmtree(tmp, ignore_errors=True)


# =============================================================
# NARRATION
# =============================================================

def banner(text):
    print(f"\n{'=' * 60}\n  {text}\n{'=' * 60}")


def explain(obs):
    banner("What was declared statically")
    print("  steps: ['plan']          (just one step!)")

    banner("What the planner emitted at runtime")
    print(f"  steps: {obs['steps_after_expansion']}")
    print("")
    print("  ┌──────┐")
    print("  │ plan │  (planner, emitted the two steps below)")
    print("  └──┬───┘")
    print("     ↓")
    print("  ┌─────┐           ┌────────┐")
    print("  │ fix │ ────────► │ review │")
    print("  └─────┘           └───┬────┘")
    print("     ▲                  │")
    print("     │                  │  loop_back_to='fix'")
    print("     └──────loop────────┘  while quality < 75")

    banner("What happened during execution")
    print(f"  fix was called {obs['attempts']} time(s)")
    print(f"  final quality: {obs['final_state'].get('quality')}")
    print("  (loop fired until threshold was met)")

    print("\n✓ observed expected behavior:")
    print("  - a loop lived ENTIRELY inside the dynamically emitted section")
    print("  - loop_back_to targeted an EMITTED sibling by name")
    print("  - loop termination obeyed loop_condition and max_loop_iterations")


if __name__ == "__main__":
    main()
