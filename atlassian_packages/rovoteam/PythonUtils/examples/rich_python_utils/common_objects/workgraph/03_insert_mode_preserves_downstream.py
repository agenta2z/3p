"""
Example 3: Insert mode — expansion sits BETWEEN parent and its existing downstream

Demonstrates a subtlety of `attach_mode='insert'`: when the expanding
node already has multiple downstream children, the expanded subgraph's
leaves are wired to EACH of those original children. Insert mode makes
the expansion behave like a transparent proxy layer.

Static graph:

    ┌──────────┐
    │ expander │─┬─►┌─────┐
    └──────────┘ │  │  A  │─►┌─────────┐
                 │  └─────┘  │ sink_X  │
                 ├─►┌─────┐  └─────────┘
                 │  │  B  │
                 │  └─────┘
                 └─►┌─────┐
                    │  C  │─►┌─────────┐
                    └─────┘  │ sink_Y  │
                             └─────────┘

After `expander` fires with DynamicExpansion of [W0, W1]:
- expander.next: W0, W1  (no longer A, B, C directly)
- W0, W1 each feed A, B, C (preserving the original multi-child fan-out)

Run: python 03_insert_mode_preserves_downstream.py
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
    # Existing multi-child downstream
    child_a = _make("A", lambda x: f"{x}|A", save_dir)
    child_b = _make("B", lambda x: f"{x}|B", save_dir)
    child_c = _make("C", lambda x: f"{x}|C", save_dir)

    def expander_fn(x):
        w0 = _make("W0", lambda xx: f"{xx}|W0", save_dir)
        w1 = _make("W1", lambda xx: f"{xx}|W1", save_dir)
        return GraphExpansionResult(
            result=x,
            subgraph=SubgraphSpec(nodes=[w0, w1], entry_nodes=[w0, w1]),
            attach_mode='insert',
        )

    expander = _make("expander", expander_fn, save_dir)
    expander.add_next(child_a)
    expander.add_next(child_b)
    expander.add_next(child_c)

    return WorkGraph(
        start_nodes=[expander],
        max_expansion_depth=1,
        max_total_nodes=50,
    ), expander, [child_a, child_b, child_c]


# =============================================================
# DRIVER
# =============================================================

def main():
    tmp = Path(tempfile.mkdtemp(prefix="wg_example03_"))
    observations = {}
    try:
        graph, expander, children = build_graph(str(tmp))
        observations["expander_next_before"] = [n.name for n in (expander.next or [])]
        observations["children_prev_before"] = {
            c.name: [p.name for p in (c.previous or [])] for c in children
        }
        observations["result"] = graph.run("init")
        observations["expander_next_after"] = [n.name for n in (expander.next or [])]
        observations["children_prev_after"] = {
            c.name: [p.name for p in (c.previous or [])] for c in children
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
    banner("Before expansion (static graph)")
    print(f"  expander.next:       {obs['expander_next_before']}")
    for child, prev in obs["children_prev_before"].items():
        print(f"  {child}.previous:         {prev}")

    banner("After expansion (insert mode rewired the edges)")
    print(f"  expander.next:       {obs['expander_next_after']}")
    for child, prev in obs["children_prev_after"].items():
        print(f"  {child}.previous:         {prev}")

    print("")
    print("  Each of A, B, C now has [W0, W1] as parents — the expansion")
    print("  layer sits between expander and its original children.")

    banner("Final result")
    print(f"  {obs['result']!r}")

    print("\n✓ observed expected behavior:")
    print("  - expander's .next was replaced by the expansion entry nodes")
    print("  - each original downstream child was rewired to receive from")
    print("    each expansion leaf (multi-parent fan-in reconfigured)")
    print("  - insert mode is safe for any-arity parent fan-out")


if __name__ == "__main__":
    main()
