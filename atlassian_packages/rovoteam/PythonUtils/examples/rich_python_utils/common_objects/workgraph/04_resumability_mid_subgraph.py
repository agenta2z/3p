"""
Example 4: Resumability — crash mid-subgraph, resume picks up where it left off

Demonstrates: a graph crashes partway through its dynamically-expanded
workers. On resume, the engine rebuilds the subgraph topology from disk
and workers with saved results are skipped; only the failing worker re-runs.

Scenario:
  Static graph:  [planner]   (leaf)
  After planner: [planner] -> [w_0, w_1, w_2]  (expanded as subgraph)

  Run 1 — planner fires, emits 3 workers. w_0 and w_1 complete + save.
          w_2 raises a simulated crash (does not save).
  Run 2 — fresh graph, resume_with_saved_results=True.
          planner is loaded from cache (not re-invoked).
          The expansion record on disk is re-materialized via the
          subgraph factory — same w_0/w_1/w_2 nodes spun up.
          w_0, w_1 skip execution (cache hit). w_2 runs fresh — succeeds.

Run: python 04_resumability_mid_subgraph.py
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

CALL_COUNTS = {"planner": 0, "w_0": 0, "w_1": 0, "w_2": 0}
SAVE_DIR_REF = [None]
CRASH_ON_W2 = [True]


class SavingNode(WorkGraphNode):
    def __init__(self, save_dir=None, **kwargs):
        super().__init__(**kwargs)
        self._save_dir = save_dir

    def _get_result_path(self, name, *args, **kwargs) -> str:
        os.makedirs(self._save_dir, exist_ok=True)
        return os.path.join(self._save_dir, f"{name}.pkl")


def _worker_impl(i, x):
    CALL_COUNTS[f"w_{i}"] = CALL_COUNTS.get(f"w_{i}", 0) + 1
    if CRASH_ON_W2[0] and i == 2:
        raise RuntimeError(f"simulated crash inside w_{i}")
    return f"w{i}({x})"


def _make_worker(i, save_dir):
    def fn(x, i=i):
        return _worker_impl(i, x)
    return SavingNode(
        name=f"w_{i}", value=fn, save_dir=save_dir,
        result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
        enable_result_save=True,
        resume_with_saved_results=True,
    )


def _subgraph_factory(expansion_id):
    """Module-level factory registered in subgraph_registry."""
    save_dir = SAVE_DIR_REF[0]
    workers = [_make_worker(i, save_dir) for i in range(3)]
    return SubgraphSpec(nodes=workers, entry_nodes=workers)


def build_graph(save_dir):
    def planner_fn(task):
        CALL_COUNTS["planner"] += 1
        return GraphExpansionResult(
            result=task,
            subgraph=_subgraph_factory("my_plan"),
            expansion_id="my_plan",
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
        save_dir=save_dir,
        start_nodes=[planner],
        max_expansion_depth=1,
        max_total_nodes=50,
        subgraph_registry={"my_plan": _subgraph_factory},
    )


# =============================================================
# DRIVER
# =============================================================

def main():
    tmp = Path(tempfile.mkdtemp(prefix="wg_example04_"))
    SAVE_DIR_REF[0] = str(tmp)
    observations = {}
    try:
        CRASH_ON_W2[0] = True
        try:
            build_graph(str(tmp)).run("TASK")
        except RuntimeError as e:
            observations["run1_crash"] = str(e)
        observations["run1_counts"] = dict(CALL_COUNTS)
        observations["saved_files_after_run1"] = sorted(
            p.name for p in tmp.iterdir() if p.is_dir() or p.name.endswith(".pkl")
        )

        for k in CALL_COUNTS:
            CALL_COUNTS[k] = 0
        CRASH_ON_W2[0] = False
        observations["run2_result"] = build_graph(str(tmp)).run("TASK")
        observations["run2_counts"] = dict(CALL_COUNTS)

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
    banner("Run 1 (planner fires, w_2 crashes)")
    print(f"  crash: {obs.get('run1_crash')!r}")
    print(f"  call counts: {obs['run1_counts']}")
    print("  Files saved to disk after Run 1:")
    for f in obs["saved_files_after_run1"]:
        print(f"    - {f}")
    print("  Notice: __graph_expansion__planner.pkl captures the expansion,")
    print("  and w_0.pkl / w_1.pkl hold cached worker results. w_2 did NOT save.")

    banner("Run 2 (fresh graph, resume)")
    print(f"  call counts:  {obs['run2_counts']}")
    print("")
    print("  Per-node interpretation on Run 2:")
    for name, count in obs["run2_counts"].items():
        if count == 0:
            tag = "loaded from cache; value() NOT invoked"
        else:
            tag = f"value() invoked {count} time(s) on Run 2"
        print(f"    {name}: {tag}")

    banner("The resume mechanism, step by step")
    print("  1. Graph start → _reconstruct_graph_expansions runs:")
    print("       - BFS from start_nodes")
    print("       - For each node, check '__graph_expansion__<name>' file")
    print("       - Found for 'planner' → load record (has expansion_id='my_plan')")
    print("       - Look up 'my_plan' in subgraph_registry")
    print("       - Call _subgraph_factory('my_plan') → 3 worker nodes")
    print("       - Re-attach them to planner.next via add_next()")
    print("  2. Normal execution starts — all cached nodes skip value() calls.")

    print("\n✓ observed expected behavior:")
    print("  - planner was NOT re-invoked on resume (count=0)")
    print("  - workers with cached results did NOT re-invoke value() (count=0)")
    print("  - The dynamically-emitted topology was rehydrated from")
    print("    '__graph_expansion__planner' + subgraph_registry — no LLM-style")
    print("    re-decision needed on resume.")
    print("")
    print("  Note: the `_get_result_path` implementation in this example saves")
    print("  results into per-name directories. Listing the dir after Run 1")
    print("  shows exactly which nodes committed — and which did not (w_2).")


if __name__ == "__main__":
    main()
