"""
Example 6: Nested expansion — emitted steps that themselves emit more steps

Demonstrates: dynamic expansion can recurse. A top-level planner emits
a second-level planner among its new_steps; when that second planner
runs, IT returns another ExpansionResult, which gets spliced in turn.

Scenario:
  outer_plan  emits  [mid_plan, finalize]
  mid_plan    emits  [leaf_a, leaf_b]  (at runtime, after mid_plan runs)

Final steps list: [outer_plan, mid_plan, leaf_a, leaf_b, finalize]

Run: python 06_nested_expansion.py
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


def leaf_a(prev):
    return f"{prev}|leaf_a"


def leaf_b(prev):
    return f"{prev}|leaf_b"


def mid_plan(prev):
    """Second-level planner: itself returns an ExpansionResult."""
    return ExpansionResult(
        result=f"{prev}|mid",
        new_steps=[
            StepWrapper(leaf_a, name="leaf_a"),
            StepWrapper(leaf_b, name="leaf_b"),
        ],
    )


def outer_plan(prev):
    """Top-level planner: emits mid_plan (itself an emitter!) + finalize."""
    return ExpansionResult(
        result=f"{prev}|outer",
        new_steps=[
            StepWrapper(mid_plan, name="mid_plan"),
            StepWrapper(lambda x: f"DONE({x})", name="finalize"),
        ],
    )


def build_workflow(save_dir):
    return ExampleWorkflow(
        steps=[StepWrapper(outer_plan, name="outer_plan")],
        save_dir=save_dir,
        result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
        max_expansion_events=5,
        max_total_steps=20,
    )


# =============================================================
# DRIVER
# =============================================================

def main():
    tmp = Path(tempfile.mkdtemp(prefix="example06_"))
    observations = {}
    try:
        wf = build_workflow(str(tmp))
        observations["steps_before"] = [s.name for s in wf._steps]
        observations["final_result"] = wf.run("init")
        observations["steps_after"] = [
            getattr(s, "name", "<anon>") for s in wf._steps
        ]
        observations["expansion_count"] = wf._expansion_count
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
    banner("Before any execution")
    print(f"  steps: {obs['steps_before']}")
    print("  (one step — just the outer planner)")

    banner("After execution (two expansions fired)")
    print(f"  steps: {obs['steps_after']}")
    print(f"  expansion events: {obs['expansion_count']}")

    banner("Expansion timeline")
    print("  T0  _steps = [outer_plan]")
    print("  T1  outer_plan runs:")
    print("        → ExpansionResult(new_steps=[mid_plan, finalize])")
    print("      _steps = [outer_plan, mid_plan, finalize]")
    print("")
    print("  T2  mid_plan runs (on the SAME run):")
    print("        → ExpansionResult(new_steps=[leaf_a, leaf_b])")
    print("      _steps = [outer_plan, mid_plan, leaf_a, leaf_b, finalize]")
    print("")
    print("  T3–T5  leaf_a, leaf_b, finalize run in order")

    banner("Final result")
    print(f"  {obs['final_result']!r}")

    print("\n✓ observed expected behavior:")
    print("  - a dynamically emitted step ALSO returned ExpansionResult")
    print("  - second-level expansion spliced in before the next sibling")
    print("  - recursion works; max_expansion_events caps it at 5")


if __name__ == "__main__":
    main()
