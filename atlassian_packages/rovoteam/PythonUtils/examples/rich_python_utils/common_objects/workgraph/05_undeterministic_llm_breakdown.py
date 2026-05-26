"""
Example 5: WorkGraph undeterministic expansion — the LLM-once guarantee

This is the HEADLINE example for WorkGraph dynamic expansion.

Demonstrates: a planner node whose expansion is derived from an LLM
(non-deterministic) call can be resumed WITHOUT re-calling the LLM.

Mechanism: the planner returns a GraphExpansionResult carrying
  (seed, reconstruct_from_seed=<module-level factory>)

The seed — the LLM's raw output, whatever it was — is persisted alongside
the expansion marker. On resume, the engine imports the factory by its
qualified name and calls `factory(seed)` to rebuild the same SubgraphSpec.
The planner's value() is never re-invoked on resume.

Run: python 05_undeterministic_llm_breakdown.py
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

from python_utils.common_objects.workflow import (
    GraphExpansionResult, SubgraphSpec,
)
from python_utils.common_objects.workflow.workgraph import WorkGraphNode, WorkGraph
from python_utils.common_objects.workflow.common.result_pass_down_mode import (
    ResultPassDownMode,
)


# =============================================================
# CORE CODE
# =============================================================

LLM_CALL_COUNT = [0]
SAVE_DIR_REF = [None]

def mock_llm_breakdown(task):
    """Mock LLM — non-deterministic: second call returns different values."""
    LLM_CALL_COUNT[0] += 1
    if LLM_CALL_COUNT[0] == 1:
        return ["summarize", "extract", "verify"]
    return ["DIFFERENT", "ANSWER", "ON", "RESUME"]      # if called on resume, we'd see drift


class SavingNode(WorkGraphNode):
    def __init__(self, save_dir=None, **kwargs):
        super().__init__(**kwargs)
        self._save_dir = save_dir

    def _get_result_path(self, name, *args, **kwargs) -> str:
        os.makedirs(self._save_dir, exist_ok=True)
        return os.path.join(self._save_dir, f"{name}.pkl")


def _make_worker(topic):
    save_dir = SAVE_DIR_REF[0]
    return SavingNode(
        name=f"w_{topic}",
        value=lambda x, t=topic: f"{x}|{t}",
        save_dir=save_dir,
        result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
        enable_result_save=True,
        resume_with_saved_results=True,
    )


def _seed_factory(seed):
    """Module-level factory — ref-importable. Called on resume with the saved seed."""
    workers = [_make_worker(topic) for topic in seed]
    return SubgraphSpec(nodes=workers, entry_nodes=workers)


def build_graph(save_dir):
    def planner_fn(task):
        topics = mock_llm_breakdown(task)              # LLM call (Run 1 only)
        return GraphExpansionResult(
            result=task,
            subgraph=_seed_factory(topics),
            seed=topics,                                # ← the frozen LLM output
            reconstruct_from_seed=_seed_factory,        # ← module-level factory
        )

    planner = SavingNode(
        name="planner", value=planner_fn, save_dir=save_dir,
        result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
        enable_result_save=True, resume_with_saved_results=True,
    )

    class GraphWithSave(WorkGraph):
        def __init__(self, save_dir, **kw):
            super().__init__(**kw)
            self._save_dir = save_dir
        def _get_result_path(self, name, *args, **kwargs):
            os.makedirs(self._save_dir, exist_ok=True)
            return os.path.join(self._save_dir, f"{name}.pkl")

    return GraphWithSave(
        save_dir=save_dir, start_nodes=[planner],
        max_expansion_depth=1, max_total_nodes=50,
    )


# =============================================================
# DRIVER
# =============================================================

def main():
    tmp = Path(tempfile.mkdtemp(prefix="wg_example05_"))
    SAVE_DIR_REF[0] = str(tmp)
    observations = {}
    try:
        build_graph(str(tmp)).run("analyze this report")
        observations["llm_calls_after_run1"] = LLM_CALL_COUNT[0]

        # Run 2: resume
        build_graph(str(tmp)).run("analyze this report")
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
    run1 = obs["llm_calls_after_run1"]
    run2 = obs["llm_calls_after_run2"]
    delta = run2 - run1

    banner("LLM call counts")
    print(f"  after Run 1: {run1}")
    print(f"  after Run 2 (resume): {run2}")
    print(f"  delta on resume: {delta}")
    print("")
    if delta == 0:
        print("  ✓ LLM was NOT called during resume (guarantee holds)")
    else:
        print(f"  ✗ LLM was called {delta} extra time(s) on resume — BUG")

    banner("The mechanism in one page")
    print("")
    print("  Run 1:")
    print("    planner.value()  →  mock_llm_breakdown(task)   ← LLM CALL")
    print("                        return GraphExpansionResult(")
    print("                            seed=topics,")
    print("                            reconstruct_from_seed=_seed_factory,")
    print("                            ...)")
    print("    engine persists:")
    print("      __graph_expansion__planner/  holds (seed, factory ref)")
    print("      planner/                     holds planner's result")
    print("      w_summarize/, w_extract/, w_verify/  hold worker results")
    print("")
    print("  Run 2 (fresh Python process):")
    print("    graph._reconstruct_graph_expansions():")
    print("       1. BFS from planner")
    print("       2. Find __graph_expansion__planner → load record")
    print("       3. record has factory_module + factory_qualname + seed")
    print("       4. importlib.import_module(factory_module)")
    print("          → attrgetter(factory_qualname)(module)  → _seed_factory")
    print("       5. call _seed_factory(seed)  →  SubgraphSpec of 3 workers")
    print("       6. re-attach workers to planner.next")
    print("    graph proceeds: every node finds its cached .pkl → skips")
    print("    mock_llm_breakdown is NEVER called")

    banner("If we HAD re-called the LLM...")
    print("")
    print(f"  mock_llm_breakdown returns different topics on call #{run1+1}+.")
    print("  Had resume re-invoked the planner, the topics would have been")
    print("  ['DIFFERENT', 'ANSWER', 'ON', 'RESUME'] — 4 topics, not 3 —")
    print("  and the expanded graph shape would have diverged, orphaning")
    print("  w_summarize/, w_extract/, w_verify/ caches.")
    print("  The seed-based resume makes this impossible.")

    print("\n✓ observed expected behavior:")
    print(f"  - LLM was called {run2} time(s) total across Run 1 + Run 2")
    print("  - resume rebuilt the dynamic subgraph purely from persisted data")
    print("  - no wasted LLM tokens; no drift; no re-decision")


if __name__ == "__main__":
    main()
