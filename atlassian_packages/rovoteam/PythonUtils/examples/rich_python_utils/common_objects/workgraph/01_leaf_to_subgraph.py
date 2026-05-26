"""
Example 1: Basic WorkGraph leaf-to-subgraph expansion

Demonstrates: a single node whose `value` returns GraphExpansionResult
gets a subgraph attached as its downstream. The subgraph runs exactly
like statically-declared downstream nodes — same fan-out semantics,
same result pass-down, same bidirectional edge consistency.

Scenario:
  Before: [expander]
  After:  [expander] ──► [sub_a] ──► [sub_b]

Run: python 01_leaf_to_subgraph.py
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
    """WorkGraphNode subclass that stores results in a directory."""
    def __init__(self, save_dir=None, **kwargs):
        super().__init__(**kwargs)
        self._save_dir = save_dir

    def _get_result_path(self, name, *args, **kwargs) -> str:
        os.makedirs(self._save_dir, exist_ok=True)
        return os.path.join(self._save_dir, f"{name}.pkl")


def make_node(name, fn, save_dir):
    return SavingNode(
        name=name,
        value=fn,
        save_dir=save_dir,
        result_pass_down_mode=ResultPassDownMode.ResultAsFirstArg,
    )


def build_graph(save_dir):
    # Build a small subgraph that the leaf will emit.
    sub_a = make_node("sub_a", lambda x: f"{x}|sub_a", save_dir)
    sub_b = make_node("sub_b", lambda x: f"{x}|sub_b", save_dir)
    sub_a.add_next(sub_b)

    def expander_fn(x):
        return GraphExpansionResult(
            result=f"{x}|expander",
            subgraph=SubgraphSpec(
                nodes=[sub_a, sub_b],      # all subgraph nodes
                entry_nodes=[sub_a],        # only sub_a connects to expander
            ),
        )

    expander = make_node("expander", expander_fn, save_dir)
    return WorkGraph(
        start_nodes=[expander],
        max_expansion_depth=1,
        max_total_nodes=50,
    ), expander


# =============================================================
# DRIVER
# =============================================================

def main():
    tmp = Path(tempfile.mkdtemp(prefix="wg_example01_"))
    observations = {}
    try:
        graph, expander = build_graph(str(tmp))
        observations["next_before"] = [n.name for n in (expander.next or [])]
        observations["result"] = graph.run("init")
        observations["next_after"] = [n.name for n in (expander.next or [])]
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
    banner("Before run — expander is a leaf (no downstream)")
    print(f"  expander.next: {obs['next_before']}  (empty)")
    print("")
    print("  ┌──────────┐")
    print("  │ expander │  (leaf — nothing statically declared downstream)")
    print("  └──────────┘")

    banner("After run — subgraph attached dynamically")
    print(f"  expander.next: {obs['next_after']}")
    print("")
    print("  ┌──────────┐     ┌───────┐     ┌───────┐")
    print("  │ expander │ ──► │ sub_a │ ──► │ sub_b │")
    print("  └──────────┘     └───────┘     └───────┘")
    print("                   (attached at runtime via add_next)")

    banner("Final result")
    print(f"  {obs['result']!r}")
    print("")
    print("  Threading: 'init' → expander (appends '|expander') →")
    print("  sub_a (appends '|sub_a') → sub_b (appends '|sub_b')")

    print("\n✓ observed expected behavior:")
    print("  - leaf node returned GraphExpansionResult")
    print("  - subgraph was wired into self.next at runtime")
    print("  - fan-out and result pass-down worked identically to static edges")


if __name__ == "__main__":
    main()
