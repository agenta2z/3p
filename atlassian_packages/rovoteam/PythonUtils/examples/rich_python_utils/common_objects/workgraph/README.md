# WorkGraph dynamic expansion — examples

These examples demonstrate the `WorkGraph` dynamic-expansion capability: a
leaf node can decide at runtime to attach a subgraph as its downstream,
and the engine will execute the subgraph as if it had been declared
statically.

Each example is self-contained. Run any of them with:

```
python 0N_<name>.py
```

Each writes its checkpoint files to a fresh temp directory that is cleaned
up on exit (set `KEEP_TMP=1` to keep it for inspection).

## Examples

| # | File | What it demonstrates |
|---|---|---|
| 1 | [01_leaf_to_subgraph.py](01_leaf_to_subgraph.py) | Single leaf node emits a chain `sub_a → sub_b`; the subgraph is attached via `add_next()` at runtime. |
| 2 | [02_bta_diamond_pattern.py](02_bta_diamond_pattern.py) | The **breakdown-then-aggregate** pattern: planner → N workers → aggregator, where the workers are emitted dynamically via insert mode. |
| 3 | [03_insert_mode_preserves_downstream.py](03_insert_mode_preserves_downstream.py) | `attach_mode='insert'` with multiple existing downstream children. Each expansion leaf wires to every original child — multi-parent fan-in reconfigures cleanly. |
| 4 | [04_resumability_mid_subgraph.py](04_resumability_mid_subgraph.py) | Crash partway through expanded workers. Resume reconstructs the subgraph from `__graph_expansion__<name>` + `subgraph_registry`. |
| 5 | [05_undeterministic_llm_breakdown.py](05_undeterministic_llm_breakdown.py) | **The headline capability.** An LLM-driven planner: the LLM fires exactly once across Run 1 + Run 2. Uses `seed + reconstruct_from_seed`. |
| 6 | [06_nested_subgraph_expansion.py](06_nested_subgraph_expansion.py) | An emitted node can itself emit more nodes — nested expansion with `_expansion_depth` safety. |

## Mental model

```
  Normal node returns X            →  X flows to downstream per result_pass_down_mode
  Node returns GraphExpansionResult(→  result flows to (existing + new) downstream,
      result=X,                         the subgraph is attached to self.next via add_next()
      subgraph=SubgraphSpec(nodes,      right before fan-out
                            entry_nodes),
      attach_mode='insert')
```

## Key constructor parameters

```python
WorkGraph(
    start_nodes=[...],
    max_expansion_depth=N,     # N=0 disables expansion. Cap chained-nesting depth.
    max_total_nodes=M,          # hard cap on total reachable nodes (default 200).
    subgraph_registry={...},    # expansion_id → factory, for resume-time reconstruction.
)
```

## SubgraphSpec

```python
SubgraphSpec(
    nodes=[n0, n1, n2],          # every node in the subgraph
    entry_nodes=[n0, n1],        # subset — these attach to the expanding leaf's `next`
)
```

Internal edges inside `nodes` are preserved exactly as-built. `entry_nodes`
declares how the subgraph connects to the outside.

## Determinism modes

- **Deterministic**: no `seed`. On resume, either `expansion_id + subgraph_registry`
  rebuilds the subgraph, or the emitter re-runs (pure function → same output).
- **Undeterministic** (`seed + reconstruct_from_seed`): for LLM-driven /
  time-based / randomized emitters. Seed is persisted; on resume, the factory
  is called with the seed. Emitter body is NEVER re-invoked.
  `reconstruct_from_seed` must be a module-level function so it can be
  imported by qualified name.

## Persistence layout (what gets written to disk)

For each expanding node N:
```
<save_dir>/
├── N/                                  # N's result (like any other node)
│   ├── main.pkl
│   └── manifest.json
├── __graph_expansion__N/               # N's expansion record
│   ├── main.pkl                        # holds (expansion_id, seed, factory_ref, ...)
│   └── manifest.json
├── <expanded_1>/                       # expanded children's per-node results
├── <expanded_2>/
└── ...
```

On resume, `WorkGraph._reconstruct_graph_expansions()` (called before any
node executes) BFS-walks the graph; for every node with a persisted
`__graph_expansion__<name>` record, it invokes the factory to rebuild the
attached subgraph before execution begins.
