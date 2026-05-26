"""
Example 6: Nested WorkGraph expansion — expanded nodes that themselves expand

Demonstrates: an expanded subgraph can contain nodes that ALSO return
GraphExpansionResult. Nested expansion composes naturally; the
max_expansion_depth limit guards against runaway recursion.

Topology:
  T0:  [outer]
  T1:  outer runs → emits [mid]         (mid is an emitter node)
       [outer] ─► [mid]
  T2:  mid runs   → emits [leaf_a, leaf_b]
       [outer] ─► [mid] ─► [leaf_a]
                       └─► [leaf_b]

Each emitter must tolerate its own _expansion_depth + 1 being within the
graph's max_expansion_depth, or the nested expansion will be rejected.

Run: python 06_nested_subgraph_expansion.py
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


def build_graph(save_dir):
    def mid_fn(x):
        leaf_a = _make("leaf_a", lambda v: f"{v}|leaf_a", save_dir)
        leaf_b = _make("leaf_b", lambda v: f"{v}|leaf_b", save_dir)
        return GraphExpansionResult(
            result=f"{x}|mid",
            subgraph=SubgraphSpec(nodes=[leaf_a, leaf_b], entry_nodes=[leaf_a, leaf_b]),
        )

    def outer_fn(x):
        mid = _make("mid", mid_fn, save_dir)
        return GraphExpansionResult(
            result=f"{x}|outer",
            subgraph=SubgraphSpec(nodes=[mid], entry_nodes=[mid]),
        )

    outer = _make("outer", outer_fn, save_dir)
    return WorkGraph(
        start_nodes=[outer],
        max_expansion_depth=3,              # allows two levels of nesting
        max_total_nodes=50,
    ), outer


# =============================================================
# DRIVER
# =============================================================

def main():
    tmp = Path(tempfile.mkdtemp(prefix="wg_example06_"))
    observations = {}
    try:
        graph, outer = build_graph(str(tmp))
        observations["result"] = graph.run("init")
        observations["outer_next"] = [n.name for n in (outer.next or [])]
        if outer.next:
            mid = outer.next[0]
            observations["mid_next"] = [n.name for n in (mid.next or [])]
            observations["mid_depth"] = getattr(mid, "_expansion_depth", "?")
            if mid.next:
                leaf = mid.next[0]
                observations["leaf_depth"] = getattr(leaf, "_expansion_depth", "?")
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
    banner("Final topology (nested expansion fired)")
    print(f"  outer.next:   {obs['outer_next']}")
    print(f"  mid.next:     {obs.get('mid_next')}")
    print("")
    print("  ┌───────┐")
    print("  │ outer │  (depth 0 — static)")
    print("  └───┬───┘")
    print("      │  emitted [mid]")
    print("      ▼")
    print(f"  ┌─────┐   (_expansion_depth = {obs.get('mid_depth')})")
    print("  │ mid │")
    print("  └──┬──┘")
    print("     │ emitted [leaf_a, leaf_b]")
    print("     ├─► leaf_a")
    print(f"     │   (_expansion_depth = {obs.get('leaf_depth')})")
    print("     └─► leaf_b")

    banner("Result")
    print(f"  {obs['result']!r}")

    banner("Depth tracking")
    print("  _expansion_depth monotonically increases along the expansion")
    print("  ancestor chain. Every emitted node inherits _expansion_depth =")
    print("  parent._expansion_depth + 1. max_expansion_depth caps the total")
    print("  chain length — set to 3 here, reached depth 2.")

    print("\n✓ observed expected behavior:")
    print("  - a dynamically emitted node itself emitted more nodes")
    print("  - each generation inherited a deeper _expansion_depth")
    print("  - max_expansion_depth is the safety net against infinite nesting")


if __name__ == "__main__":
    main()
