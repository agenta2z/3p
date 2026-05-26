"""
Example 3: Splice mode — pure planner step (emitter result not saved)

Demonstrates: an emitter step that acts as a PURE PLANNER — it has no
result of its own worth saving as a workflow artifact. mode='splice' tells
the engine to skip saving the emitter's result; the first emitted step
receives the emitter's ORIGINAL input (not the emitter's return value).

Contrast with the default 'follow' mode (Example 1) where the emitter's
result is saved as a normal step result and passed downstream.

Use splice when: the planner is just a routing/breakdown helper and
producing a saved artifact for it would be noise in the checkpoint dir.

Run: python 03_splice_mode_pure_planner.py
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


def worker(original_input):
    return f"worker-processed:{original_input}"


def pure_planner(original_input):
    """A splice-mode planner: doesn't compute a usable result, only structure."""
    return ExpansionResult(
        result=None,                                   # no result — splice mode ignores it
        new_steps=[StepWrapper(worker, name="worker")],
        mode='splice',                                 # ← the key detail
    )


def build_workflow(save_dir):
    return ExampleWorkflow(
        steps=[StepWrapper(pure_planner, name="planner")],
        save_dir=save_dir,
        result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
        max_expansion_events=3,
        max_total_steps=20,
        enable_result_save=True,                       # so we can inspect saved files
    )


# =============================================================
# DRIVER
# =============================================================

def main():
    tmp = Path(tempfile.mkdtemp(prefix="example03_"))
    observations = {}
    try:
        wf = build_workflow(str(tmp))
        observations["final_result"] = wf.run("ORIGINAL-INPUT")
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
    banner("Final result")
    print(f"  {obs['final_result']!r}")
    print("")
    print("  Notice: 'worker' received 'ORIGINAL-INPUT' (the planner's")
    print("  input) — NOT the planner's return value. Under splice mode,")
    print("  the first emitted step picks up where the planner started.")

    banner("Follow vs. splice mode — side by side")
    print("  FOLLOW (default)      SPLICE")
    print("  ──────────────        ──────")
    print("  planner runs          planner runs")
    print("  planner result SAVED  planner result NOT saved")
    print("  planner.result →      original input →")
    print("    emitted[0]            emitted[0]")

    print("\n✓ observed expected behavior:")
    print("  - emitter's return value was discarded (splice)")
    print("  - first emitted step received the emitter's ORIGINAL input")
    print("  - no artifact file was created for the planner")


if __name__ == "__main__":
    main()
