"""
Example 1: Basic Workflow expansion (deterministic, follow mode)

Demonstrates: a planner step emits N worker steps at runtime; the emitted
section executes right after the planner, feeding into any steps that were
originally queued after it.

Scenario: a static 2-step workflow [plan, finalize] becomes a 5-step workflow
[plan, work_A, work_B, work_C, finalize] because `plan` returns an
ExpansionResult whose `new_steps` gets spliced in.

Run: python 01_basic_expansion.py
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

# Ensure the example prints unicode box-drawing chars on Windows terminals.
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


# =======================================================================
# CORE CODE — the pattern to copy
# =======================================================================

@attrs(slots=False)
class ExampleWorkflow(Workflow):
    """Minimal concrete Workflow that stores step results in a directory."""
    _save_dir: str = attrib(default=None)

    def _get_result_path(self, result_id, *args, **kwargs) -> str:
        return os.path.join(self._save_dir, f"step_{result_id}.pkl")


def worker(topic, prev_result=None):
    """A "worker" step — in real code this might call an API, tool, model."""
    return f"{prev_result or 'init'}|{topic}"


def plan(input_text):
    """The planner. Emits N worker steps based on a (here: hardcoded) breakdown.

    In deterministic mode we re-run this on resume to rebuild the exact same
    new_steps; the function must be a pure function of its inputs.
    """
    topics = ["summarize", "extract", "verify"]   # in real code: break down `input_text`
    new_steps = [
        StepWrapper(lambda prev, t=topic: worker(t, prev), name=f"work_{topic}")
        for topic in topics
    ]
    return ExpansionResult(
        result=input_text,            # passed to first emitted step
        new_steps=new_steps,
    )


def finalize(prev_result):
    return f"DONE({prev_result})"


def build_workflow(save_dir):
    return ExampleWorkflow(
        steps=[
            StepWrapper(plan, name="plan"),
            StepWrapper(finalize, name="finalize"),
        ],
        save_dir=save_dir,
        result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
        max_expansion_events=3,            # opt-in gate: >0 enables expansion
        max_total_steps=20,                # hard cap against runaway emission
    )


# =======================================================================
# DRIVER — runs the example, captures results for narration
# =======================================================================

def main():
    tmp = Path(tempfile.mkdtemp(prefix="example01_"))
    observations = {}
    try:
        wf = build_workflow(str(tmp))
        observations["steps_before_run"] = [s.name for s in wf._steps]
        observations["final_result"] = wf.run("initial text")
        observations["steps_after_expansion"] = [
            getattr(s, "name", "<anon>") for s in wf._steps
        ]
        observations["expansion_count"] = wf._expansion_count
        explain(observations)
    finally:
        if not os.getenv("KEEP_TMP"):
            shutil.rmtree(tmp, ignore_errors=True)


# =======================================================================
# NARRATION — all print/logging isolated here
# =======================================================================

def banner(text):
    print(f"\n{'=' * 60}\n  {text}\n{'=' * 60}")


def explain(obs):
    banner("Before run: static workflow had 2 steps")
    print(f"  steps: {obs['steps_before_run']}")
    print("  (just 'plan' and 'finalize' — nothing else was declared)")

    banner("After run: planner emitted 3 workers; list grew to 5 steps")
    print(f"  steps: {obs['steps_after_expansion']}")
    print(f"  expansion events: {obs['expansion_count']}")
    print("  ┌─────────┐")
    print("  │  plan   │  ← returned ExpansionResult(new_steps=[work_*])")
    print("  └────┬────┘")
    print("       ├── work_summarize  ← spliced in")
    print("       ├── work_extract    ← spliced in")
    print("       ├── work_verify     ← spliced in")
    print("       ↓")
    print("  ┌──────────┐")
    print("  │ finalize │  ← was step 2, now step 5, still runs last")
    print("  └──────────┘")

    banner("Final result (threaded through every step)")
    print(f"  {obs['final_result']!r}")

    print("\n✓ observed expected behavior:")
    print("  - planner emitted steps at runtime")
    print("  - emitted section inserted BETWEEN planner and finalize (order preserved)")
    print("  - result chain threaded cleanly through all 5 steps")


if __name__ == "__main__":
    main()
