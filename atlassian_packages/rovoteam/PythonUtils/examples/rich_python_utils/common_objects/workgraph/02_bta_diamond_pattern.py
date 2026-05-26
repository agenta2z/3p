"""
Example 2: Breakdown-Then-Aggregate diamond pattern

Demonstrates the most common agent workflow shape — a planner expands
into a fan-out of parallel workers whose results converge on an
aggregator. This is the generalized BTA (BreakdownThenAggregate)
pattern expressible purely via the DynamicExpansion primitive.

Topology produced at runtime:

        ┌──────────┐
        │ planner  │              (breaks down task into N subtasks)
        └────┬─────┘
             │  (emits subgraph; insert mode wires leaves to aggregator)
             ▼
    ┌────────┼────────┐
    ▼        ▼        ▼
┌──────┐ ┌──────┐ ┌──────┐      (parallel workers, one per subtask)
│ w_0  │ │ w_1  │ │ w_2  │
└──┬───┘ └──┬───┘ └──┬───┘
   │        │        │
   └────────┼────────┘
            ▼
       ┌──────────┐
       │aggregator│              (multi-parent: waits for all workers)
       └──────────┘

The planner's STATIC graph has only [planner → aggregator]. The workers
appear at runtime via insert-mode expansion between planner and aggregator.

Run: python 02_bta_diamond_pattern.py
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

class SavingNode(WorkGraphNode):
    def __init__(self, save_dir=None, **kwargs):
        super().__init__(**kwargs)
        self._save_dir = save_dir

    def _get_result_path(self, name, *args, **kwargs) -> str:
        os.makedirs(self._save_dir, exist_ok=True)
        return os.path.join(self._save_dir, f"{name}.pkl")


def _make(name, fn, save_dir):
    return SavingNode(
        name=name, value=fn, save_dir=save_dir,
        result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
    )


def aggregate(*worker_results):
    """Aggregator — multi-parent node that merges all worker outputs."""
    return "AGG[" + " | ".join(str(r) for r in worker_results) + "]"


def build_graph(save_dir):
    # Static graph: planner → aggregator
    aggregator = _make("aggregator", aggregate, save_dir)

    def planner_fn(task):
        # At runtime: break down the task into N subtasks
        subtasks = [f"{task}:part_{i}" for i in range(3)]

        # Build a subgraph with one worker per subtask
        worker_nodes = []
        for i, sub in enumerate(subtasks):
            w = _make(f"w_{i}", lambda x, s=sub: f"worker({s})", save_dir)
            worker_nodes.append(w)

        # Return expansion: workers inserted between planner and aggregator.
        # attach_mode='insert' (default) rewires planner's existing downstream
        # so each worker leaf feeds the aggregator.
        return GraphExpansionResult(
            result=task,                           # passed to each worker
            subgraph=SubgraphSpec(
                nodes=worker_nodes,
                entry_nodes=worker_nodes,          # all workers are entry points
            ),
            attach_mode='insert',                  # ← preserves aggregator downstream
        )

    planner = _make("planner", planner_fn, save_dir)
    planner.add_next(aggregator)                   # static edge

    return WorkGraph(
        start_nodes=[planner],
        max_expansion_depth=1,
        max_total_nodes=50,
    ), planner, aggregator


# =============================================================
# DRIVER
# =============================================================

def main():
    tmp = Path(tempfile.mkdtemp(prefix="wg_example02_"))
    observations = {}
    try:
        graph, planner, aggregator = build_graph(str(tmp))
        observations["planner_next_before"] = [n.name for n in (planner.next or [])]
        observations["aggregator_previous_before"] = [
            n.name for n in (aggregator.previous or [])
        ]
        observations["result"] = graph.run("TASK")
        observations["planner_next_after"] = [n.name for n in (planner.next or [])]
        observations["aggregator_previous_after"] = [
            n.name for n in (aggregator.previous or [])
        ]
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
    banner("Static graph (before expansion)")
    print(f"  planner.next:      {obs['planner_next_before']}")
    print(f"  aggregator.prev:   {obs['aggregator_previous_before']}")
    print("")
    print("  ┌─────────┐     ┌────────────┐")
    print("  │ planner │ ──► │ aggregator │")
    print("  └─────────┘     └────────────┘")

    banner("Runtime graph (after planner fired, insert mode applied)")
    print(f"  planner.next:      {obs['planner_next_after']}")
    print(f"  aggregator.prev:   {obs['aggregator_previous_after']}")
    print("")
    print("  ┌─────────┐")
    print("  │ planner │")
    print("  └────┬────┘")
    print("       ├─► w_0 ─┐")
    print("       ├─► w_1 ─┼─► ┌────────────┐")
    print("       └─► w_2 ─┘   │ aggregator │")
    print("                    └────────────┘")
    print("")
    print("  Notice: aggregator's previous list grew from [planner] to")
    print("  [w_0, w_1, w_2] — multi-parent fan-in reconfigured cleanly.")

    banner("Final result")
    print(f"  {obs['result']!r}")

    print("\n✓ observed expected behavior:")
    print("  - planner expanded into N workers at runtime")
    print("  - insert mode preserved the static aggregator downstream")
    print("  - aggregator saw all 3 workers as parents and merged their outputs")
    print("  - this is the BTA pattern implemented purely with DynamicExpansion")


if __name__ == "__main__":
    main()
