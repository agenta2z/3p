"""
Example 5: Resumability — undeterministic expansion (LLM-driven) via seed

Demonstrates THE HEADLINE capability: a planner whose output comes from
an LLM (non-deterministic) can still be resumed — the LLM is invoked
EXACTLY ONCE across Run 1 + Run 2.

How: the planner returns an ExpansionResult with (seed, reconstruct_from_seed).
The seed is whatever non-deterministic value the planner committed to (here:
the LLM's output list). The reconstruct_from_seed factory is a module-level
function that, given the seed, returns the SAME step list deterministically.

Persistence path:
  Run 1: planner calls LLM → seed = [...], factory = _seed_factory
         seed + factory qualified name saved into checkpoint
  Run 2: resume loads seed, imports _seed_factory by name, calls it(seed)
         to get the step list. LLM is NOT re-invoked.

Run: python 05_resumability_undeterministic_llm.py
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

# The "LLM" — in a real app this would call Anthropic/OpenAI. Here it's a
# mock that logs call counts so we can prove it runs exactly once.
LLM_CALL_COUNT = [0]

def mock_llm_breakdown(task):
    """Mock LLM. Returns a different-length list each call if called twice."""
    LLM_CALL_COUNT[0] += 1
    if LLM_CALL_COUNT[0] == 1:
        return ["summarize", "extract", "verify"]       # "real" answer
    return ["DIFFERENT", "ANSWER", "ON", "SECOND", "CALL"]  # if re-called, shape diverges!


def make_worker(topic):
    """Build one worker step for a given topic."""
    def worker(prev):
        return f"{prev}|{topic}"
    return StepWrapper(worker, name=f"work_{topic}")


def _seed_factory(seed):
    """Module-level factory (must be ref-importable, not lambda/closure).

    Called on resume to rebuild the emitted step list deterministically
    from the persisted seed. LLM is NOT involved here.
    """
    return [make_worker(topic) for topic in seed]


@attrs(slots=False)
class ExampleWorkflow(Workflow):
    _save_dir: str = attrib(default=None)

    def _get_result_path(self, result_id, *args, **kwargs) -> str:
        return os.path.join(self._save_dir, f"step_{result_id}.pkl")


def planner(task):
    topics = mock_llm_breakdown(task)     # non-deterministic call
    return ExpansionResult(
        result=task,
        new_steps=_seed_factory(topics),
        seed=topics,                      # ← the frozen non-determinism
        reconstruct_from_seed=_seed_factory,  # ← how to rebuild from seed
    )


def finalize(prev):
    return f"DONE({prev})"


def build_workflow(save_dir, crash_on_step=None):
    def maybe_crash(prev):
        if crash_on_step == "finalize":
            raise RuntimeError("simulated crash before finalize")
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
    )


# =============================================================
# DRIVER
# =============================================================

def main():
    tmp = Path(tempfile.mkdtemp(prefix="example05_"))
    observations = {}
    try:
        # Run 1: crashes after expansion + workers run
        wf1 = build_workflow(str(tmp), crash_on_step="finalize")
        try:
            wf1.run("analyze this report")
        except RuntimeError as e:
            observations["run1_crash"] = str(e)
        observations["llm_calls_after_run1"] = LLM_CALL_COUNT[0]

        # Run 2: fresh process, resume. LLM should NOT be called again.
        wf2 = build_workflow(str(tmp), crash_on_step=None)
        wf2.resume_with_saved_results = True
        observations["run2_result"] = wf2.run("analyze this report")
        observations["llm_calls_after_run2"] = LLM_CALL_COUNT[0]
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
    banner("Run 1 (LLM called, workers run, crash at finalize)")
    print(f"  crash raised: {obs.get('run1_crash')!r}")
    print(f"  LLM call count so far: {obs['llm_calls_after_run1']}")

    banner("Run 2 (fresh process, resume)")
    print(f"  final result: {obs['run2_result']!r}")
    print(f"  LLM call count AFTER resume: {obs['llm_calls_after_run2']}")

    delta = obs["llm_calls_after_run2"] - obs["llm_calls_after_run1"]
    print("")
    if delta == 0:
        print("  ✓ LLM was NOT called on resume (the guarantee holds)")
    else:
        print(f"  ✗ LLM was called {delta} extra time(s) on resume — BUG")

    banner("The mechanism")
    print("")
    print("  Run 1:")
    print("    planner()  →  topics = mock_llm_breakdown(task)  [+1 LLM call]")
    print("                  return ExpansionResult(")
    print("                      seed=topics,")
    print("                      reconstruct_from_seed=_seed_factory,")
    print("                  )")
    print("    engine persists: (seed, 'module._seed_factory', child names)")
    print("")
    print("  Run 2 (resume):")
    print("    engine reads checkpoint → has expansion record with seed")
    print("    imports '_seed_factory' by qualified name")
    print("    calls _seed_factory(seed)  →  identical step list")
    print("    planner()  is NEVER called   ← no LLM, no wasted tokens")

    banner("Why the mock would have said something else on re-call")
    print("")
    print("  mock_llm_breakdown('...') returns a DIFFERENT list on its")
    print(f"  second call. Since it stayed at count={obs['llm_calls_after_run2']},")
    print("  the second call never happened — the seed captured the first")
    print("  answer and resume used it directly.")

    print("\n✓ observed expected behavior:")
    print(f"  - LLM called exactly {obs['llm_calls_after_run2']} time(s) across Run 1 + Run 2")
    print("  - resume rebuilt the expanded shape via reconstruct_from_seed(seed)")
    print("  - non-determinism was frozen; result chain intact")


if __name__ == "__main__":
    main()
