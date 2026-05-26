# Workflow dynamic expansion — examples

These examples demonstrate the `Workflow` dynamic-expansion capability: a step
can decide at runtime to append more steps to the sequence, and the engine
will execute them as if they had been declared statically.

Each example is self-contained. Run any of them with:

```
python 0N_<name>.py
```

Each writes its checkpoint files to a fresh temp directory that is cleaned up
on exit (set `KEEP_TMP=1` to keep it for inspection).

## Examples

| # | File | What it demonstrates |
|---|---|---|
| 1 | [01_basic_expansion.py](01_basic_expansion.py) | A planner step emits N worker steps; the workflow list grows from 2 → 5 at runtime. |
| 2 | [02_expansion_with_local_loop.py](02_expansion_with_local_loop.py) | Emitted steps include `loop_back_to` — a loop lives entirely inside the dynamically emitted section. |
| 3 | [03_splice_mode_pure_planner.py](03_splice_mode_pure_planner.py) | `mode='splice'` — the planner is a pure routing step; its return value is not saved and the first emitted step gets the planner's original input. |
| 4 | [04_resumability_deterministic.py](04_resumability_deterministic.py) | Crash + resume. An `expansion_step_registry` keyed by `expansion_id` reconstructs the emitted shape without re-running the planner. |
| 5 | [05_resumability_undeterministic_llm.py](05_resumability_undeterministic_llm.py) | **The headline capability.** An LLM-driven planner: the LLM fires exactly once across Run 1 + Run 2 (resume). Uses `seed + reconstruct_from_seed`. |
| 6 | [06_nested_expansion.py](06_nested_expansion.py) | An emitted step can itself return `ExpansionResult` — recursive expansion. |

## Mental model

```
  Normal step returns X          →  X flows to next step
  Step returns ExpansionResult(  →  result flows to next step,
      result=X, new_steps=[A,B])      and [A,B] are spliced in
                                      right after the current step
```

## Opt-in

Dynamic expansion is **opt-in**: pass `max_expansion_events=N` (with `N > 0`)
to the `Workflow` constructor. With the default `max_expansion_events=0`,
returning an `ExpansionResult` is silently treated as a no-op (plus a
warning) — existing workflows are unaffected.

## Determinism modes

- **Deterministic** (no `seed`): planner is a pure function of its inputs.
  On resume, either `expansion_id` + `expansion_step_registry` rebuild the
  emitted list, or the planner itself re-runs (pure → same output).
- **Undeterministic** (`seed + reconstruct_from_seed` provided): use this for
  LLM-driven / time-based / randomized planners. The seed is persisted; on
  resume, the factory is called with the seed — the planner's body is never
  re-invoked. `reconstruct_from_seed` must be a module-level function
  (not a lambda or closure) so it can be imported by qualified name.
