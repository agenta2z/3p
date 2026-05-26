# 🚨 Runaway Incident Postmortem (2026-05-20)

## TL;DR

A combination of **3 cascading bugs** caused the orchestrator to create **896,692 empty
`epic_monitor_AI-236_round_NN/` directories** in 28 minutes (~534 dirs/sec) before being
manually killed. Five defenses are now in place to make this impossible.

---

## What happened (timeline)

| Time (UTC) | Event |
|---|---|
| 05:00:37 | Orchestrator launched (`run.py --epic-url …`) |
| 05:00:37 | First `MonitorEpicTask` dequeued, dispatched to worker 0 |
| 05:00:37 | Lazy import `from agent_foundation.inferencer.cli ...` raised `ModuleNotFoundError` (Bug #1) |
| 05:00:37 | Handler exception propagated to `_dispatch()`, caught at `_worker()` |
| 05:00:37 | `_safety_reenqueue_on_error()` called with `task.delay_seconds == 0` (Bug #2) |
| 05:00:37 | New `MonitorEpicTask` enqueued with `delay=0` (no min-gap floor enforced because kickoff exemption fired) |
| 05:00:37 | Worker 0 immediately picks up the new task → crash → re-enqueue → tight loop |
| 05:00:37 | RunWorkspace created `epic_monitor_AI-236_round_01/` (empty: nothing written because crash happened before output capture) |
| 05:00:37 - 05:28:37 | Tight loop runs ~534 iterations/sec, creating one new round_NN dir each iteration |
| 05:28:37 | User manually killed (orchestrator + 4 stale workers) — 896,692 dirs created |

---

## Root cause: 3 cascading bugs

### Bug #1: Missing PYTHONPATH for `agent_foundation`
The lazy import of `RovoDevCliInferencer` in `tasks._run_inferencer` failed every call
because `agent_foundation` lives at `/Users/tchen7/MyProjects/CoreProjects/AgentFoundation/src`
and was not on `sys.path`. The orchestrator started successfully (lazy import was deferred),
then failed at the first call.

**Fix:** `run.py` now pre-extends `sys.path` with all 4 internal package roots before any
module is imported.

### Bug #2: Safety re-enqueue used `task.delay_seconds` instead of `steady_state_delay_seconds`
The `MonitorEpicTask` was created with `delay_seconds=0` (kickoff) and `steady_state_delay_seconds=600`.
On crash, `_safety_reenqueue_on_error` should have used the steady-state delay (600s = 10 min),
but it copied `task.delay_seconds` (=0). This meant the new task was eligible for immediate execution.

**Fix:** `_safety_reenqueue_on_error` now uses `steady_state_delay_seconds` explicitly.

### Bug #3: No defense against tight crash loops
Even if Bug #2 were fixed, a slow crash loop (e.g. once every 10 min) would still accumulate
hundreds of empty round dirs over a long run. There was no upper bound on crashes.

**Fix:** Three new defenses (G-1a, G-1b, G-3) cap crash rate and disk usage.

---

## The 2 defenses (revised 2026-05-20 after user feedback — simpler is better)

The earlier 3-layer count-based design (rapid breaker, per-task lifetime cap,
global lifetime cap → shutdown) was effective but BRITTLE. A transient infra
outage (e.g. Jira down for 30 min) would exhaust the 20-per-task budget within
a few hours and require a human restart. That made the orchestrator NOT
self-healing — which is the opposite of what an "always-on" monitor should be.

We replaced it with one time-based defense + the disk backstop:

| # | Defense | Effect | Threshold |
|---|---|---|---|
| **D1** | Min-gap floor on EVERY crash-path re-enqueue | `max(steady_state, 300s)` — bounds re-enqueue rate, self-healing | 300s (5 min) |
| **D2** | Disk hard cap (RunWorkspace) | Quarantine excess call dirs to a single shared dir | 1000 call dirs |

### Combined effect (worst-case projections)

| Scenario | Without fixes | With fixes |
|---|---|---|
| Tight crash loop (every <1s) | **896,692 dirs / 28 min** (observed) | **1 dir / 5 min** = max 288/day per task |
| Slow crash loop (every 10 min) | ~144 dirs / 24h | unchanged (already > floor) |
| Multiple slow loops across many issues | Could still grow | Bounded per-task; combined still grows but capped by D2 |
| 30-min Jira outage (transient) | OK — recovers | OK — re-enqueues every 5 min, **self-heals when Jira returns** ✅ |
| Determinstic broken-dep crash (PYTHONPATH missing) | OK — recovers | **Tries forever** (every 5 min); humans see logs + D2 caps disk at 1000 |
| 30-day persistent broken-dep crash | 288 × 30 = 8640 dirs | **D2 caps at 1000** → quarantine kicks in around day 3.5 |

### Why this is better than the 3-layer design

- ✅ **Self-healing** — no human restart needed for transient outages
- ✅ **Simpler** — one constant (300s), one rule, ~30 fewer lines of code
- ✅ **Fewer state variables** — no `_crash_history`, `_lifetime_crashes_per_task`, `_lifetime_crashes_global`
- ✅ **Less to test** — 3 tests instead of 5
- ✅ **No "fail loud and stop"** semantic that requires human intervention

---

## How to verify the defenses

```bash
cd /Users/tchen7/MyProjects/CoreProjects/OpenTeam && \
  PYTHONPATH=test:/Users/tchen7/MyProjects/CoreProjects/AgentFoundation/src:/Users/tchen7/MyProjects/CoreProjects/PythonUtils/src:/Users/tchen7/MyProjects/CoreProjects/ScienceModelingTools/src:/Users/tchen7/MyProjects/CoreProjects/SciencePythonUtils/src \
  /opt/homebrew/anaconda3/bin/python -m pytest \
  test/openteam/use_cases/proposal_implementation/test_orchestrator_smoke.py -v
```

Expected: **12 passed**. If any of `test_defense_*` fail, a defense has regressed.

---

## What to do if a re-occurrence happens

1. **Stop the orchestrator immediately:** `pkill -9 -f use_cases.proposal_implementation.run`
2. **Check disk:** `du -sh /Users/tchen7/MyProjects/CoreProjects/OpenTeam/test/openteam/use_cases/proposal_implementation/_runtime/`
3. **Find the runaway run dir:** `find _runtime -maxdepth 2 -type d | head`
4. **Delete via `rm -rf <run_dir>`** (will take 5-30 min for >100K dirs)
5. **Inspect the latest few round dirs** — if they're empty, the failure is happening BEFORE
   output capture (likely an import or auth error). Check the orchestrator's stderr.
6. **Run the smoke tests** — they should still pass; if not, identify which defense regressed.

---

## Open follow-ups (not yet implemented)

- **Bound `_crash_history` deque size** — currently grows unbounded if breaker keeps tripping (minor memory leak).
- **Add a `--max-crashes-per-task` and `--max-crashes-global` CLI** for tuning per-run.
- **Persist crash history across restarts** — currently lost on restart, so the per-task cap resets.
- **Emit a Slack/Email alert when G-1b shutdown fires** — currently only logged.
