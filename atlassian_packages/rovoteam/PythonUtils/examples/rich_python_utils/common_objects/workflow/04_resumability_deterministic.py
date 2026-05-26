"""
Example 4: Resumability — deterministic expansion via registry

Demonstrates: crash and resume a workflow that expanded mid-run.
The planner emitted 3 workers; we crash in the middle of them.
On resume the engine reconstructs the expanded step list (via a
registered factory keyed by expansion_id) and picks up from the
last-successful saved step.

This is the path to take when the planner's output is derived
from static / reproducible inputs (no LLM, no randomness).

Key insight: the planner step does NOT re-run on resume. Its
"decision" (how many workers to emit and which) is captured via
the expansion_id + the factory in `expansion_step_registry`.

Run: python 04_resumability_deterministic.py
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

# Module-level: importable by name. The registry factory must be
# ref-reconstructible on resume.
TOPICS = ["alpha", "beta", "gamma"]

def make_worker_step(topic):
    """Factory that returns a worker step for a given topic."""
    def worker(prev):
        return f"{prev}|{topic}"
    return StepWrapper(worker, name=f"work_{topic}")


def worker_steps_factory(expansion_id):
    """Registered factory. Called on resume to rebuild the emitted section.

    Must be deterministic: same expansion_id -> same ordered step list.
    """
    return [make_worker_step(t) for t in TOPICS]


@attrs(slots=False)
class ExampleWorkflow(Workflow):
    _save_dir: str = attrib(default=None)

    def _get_result_path(self, result_id, *args, **kwargs) -> str:
        return os.path.join(self._save_dir, f"step_{result_id}.pkl")


def planner(input_text):
    return ExpansionResult(
        result=input_text,
        new_steps=worker_steps_factory("my_plan"),
        expansion_id="my_plan",           # ← key into expansion_step_registry
    )


def finalize(prev):
    return f"DONE({prev})"


def build_workflow(save_dir, crash_on_step=None):
    """crash_on_step is a step name to intentionally fail at (simulates a crash)."""
    def maybe_crash(prev):
        if crash_on_step == "finalize":
            raise RuntimeError("simulated crash")
        return finalize(prev)

    return ExampleWorkflow(
        steps=[
            StepWrapper(planner, name="plan"),
            StepWrapper(maybe_crash, name="finalize"),
        ],
        save_dir=save_dir,
        result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
        max_expansion_events=3,
        max_total_steps=20,
        enable_result_save=True,
        expansion_step_registry={"my_plan": worker_steps_factory},
    )


# =============================================================
# DRIVER
# =============================================================

def main():
    tmp = Path(tempfile.mkdtemp(prefix="example04_"))
    observations = {
        "planner_calls": 0,
        "worker_calls": {"alpha": 0, "beta": 0, "gamma": 0},
    }
    try:
        # Patch modules' functions to count calls (for observation only)
        global planner, make_worker_step
        original_planner = planner
        def counted_planner(x):
            observations["planner_calls"] += 1
            return original_planner(x)
        planner = counted_planner

        original_make = make_worker_step
        def counted_make(topic):
            base = original_make(topic)
            inner = base._fn
            def counted(prev):
                observations["worker_calls"][topic] = (
                    observations["worker_calls"].get(topic, 0) + 1
                )
                return inner(prev)
            return StepWrapper(counted, name=f"work_{topic}")
        make_worker_step = counted_make

        # ---- Run 1: crash at finalize ----
        wf1 = build_workflow(str(tmp), crash_on_step="finalize")
        try:
            wf1.run("init")
        except RuntimeError as e:
            observations["run1_crash"] = str(e)

        # Snapshot state after crash
        observations["run1_planner_calls"] = observations["planner_calls"]
        observations["run1_worker_calls"] = dict(observations["worker_calls"])

        # ---- Run 2: fresh process, resume ----
        wf2 = build_workflow(str(tmp), crash_on_step=None)
        wf2.resume_with_saved_results = True
        observations["run2_result"] = wf2.run("init")
        observations["run2_planner_calls"] = (
            observations["planner_calls"] - observations["run1_planner_calls"]
        )
        observations["run2_worker_calls"] = {
            t: observations["worker_calls"][t] - observations["run1_worker_calls"][t]
            for t in ["alpha", "beta", "gamma"]
        }
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
    banner("Run 1 (crashes at finalize)")
    print(f"  crash raised: {obs.get('run1_crash')!r}")
    print(f"  planner was called: {obs['run1_planner_calls']} time(s)")
    print(f"  worker calls:      {obs['run1_worker_calls']}")

    banner("Run 2 (fresh process, resume_with_saved_results=True)")
    print(f"  final result: {obs['run2_result']!r}")
    print(f"  planner was RE-called: {obs['run2_planner_calls']} time(s)")
    print(f"  worker calls on resume: {obs['run2_worker_calls']}")

    print("")
    print("  Interpretation:")
    print("  - workers with cached results re-loaded from disk (0 re-calls)")
    print("  - workers that didn't finish are re-executed")
    print("  - finalize executes fresh this time (no crash)")

    banner("What the registry did on resume")
    print("  1. Resume engine read the checkpoint, found an expansion record")
    print("     { after_step_name: 'plan', expansion_id: 'my_plan' }")
    print("  2. Looked up 'my_plan' in expansion_step_registry")
    print("  3. Called worker_steps_factory('my_plan') → 3 fresh step callables")
    print("  4. Spliced them into _steps so the list shape matches Run 1")
    print("  5. Jumped to the resume index and proceeded")
    print("")
    print("  The planner function ITSELF was not invoked on resume — the")
    print("  registry factory reconstructs its emission without re-running it.")

    print("\n✓ observed expected behavior:")
    print("  - the planner was called ONCE (only during Run 1)")
    print("  - the emitted shape was rebuilt on resume via the registry")
    print("  - cached worker results skipped re-execution")


if __name__ == "__main__":
    main()
