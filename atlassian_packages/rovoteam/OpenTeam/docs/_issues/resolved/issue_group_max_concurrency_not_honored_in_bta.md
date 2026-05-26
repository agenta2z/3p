# Issue: `group_max_concurrency` Not Honored in BTA Live Runs

**Status:** Unresolved
**Discovered:** 2026-04-19
**Severity:** Medium (functional but resource-intensive)
**Affected:** `BreakdownThenAggregateInferencer` outer BTA with `group_max_concurrency` set in YAML

---

## Symptom

When running the outer BTA (`role_setup.yaml`) with:
```yaml
group_max_concurrency:
  skill_tool_creation: 2      # max 2 inner BTAs run concurrently
  skill_tool_association: 1   # only 1 association subtask ever exists
```

All 4 outer workers (3 `skill_tool_creation` + 1 `skill_tool_association`) ran **concurrently** instead of being limited to 2 creation workers at a time.

### Evidence from live run `_runtime/20260419_140325`

Inner stream start timestamps for each outer worker:
- `worker_0` (association): 14:10:04
- `worker_1` (creation): 14:10:46
- `worker_2` (creation): 14:09:40
- `worker_3` (creation): 14:09:12

All 4 outer workers' inner streams started within ~94 seconds of each other → all 4 ran in parallel. Expected: only 2 `skill_tool_creation` workers should run concurrently, with the 3rd waiting until one of the first two finishes.

---

## Root Cause Analysis (Partial)

### What was verified ✅

1. **YAML correctly sets `group_max_concurrency`** on the outer BTA:
   ```python
   bta.group_max_concurrency  # → {'skill_tool_creation': 2, 'skill_tool_association': 1}
   bta.max_concurrency         # → None
   ```

2. **`worker_group` is correctly assigned** to each `WorkGraphNode`:
   ```
   worker_0: group='skill_tool_association'
   worker_1: group='skill_tool_creation'
   worker_2: group='skill_tool_creation'
   worker_3: group='skill_tool_creation'
   ```

3. **Semaphore mechanism works in isolation** (verified with synthetic test):
   ```python
   wg = WorkGraph(start_nodes=nodes, group_max_concurrency={'A': 2, 'B': 1})
   asyncio.run(wg._arun())
   # Result: Max concurrent A: 2 (expected: 2) ✅
   #         Max concurrent B: 1 (expected: 1) ✅
   ```

4. **BTA correctly invokes `WorkGraph._arun(self, ...)`** at lines 1280, 1313, 1424 of `breakdown_then_aggregate_inferencer.py`.

5. **`WorkGraph._arun()` correctly creates per-group semaphores** at lines 1798-1810 of `workgraph.py`.

6. **`WorkGraphNode._arun()` correctly selects the group's semaphore** at lines 745-748 and acquires/releases it at lines 822-823 / 915-916.

### What's NOT explained ❌

Despite all the above being correct in isolation, the live BTA run shows all 4 workers running concurrently. The semaphore appears not to be enforced in the live BTA execution path.

### Hypotheses (not yet verified)

1. **Race condition in semaphore creation** — the semaphore dict might be recreated on each call, losing state across nodes
2. **Different code path** — perhaps the BTA hits a sync `_run` path that doesn't have semaphore support, despite calling `WorkGraph._arun`
3. **Worker function awaits something that releases the semaphore early** — `async_worker_fn` (line 654) calls `await w.ainfer(q)`, which is a long-running async call. If somehow the semaphore is released before this completes, the limit wouldn't be enforced.
4. **`__attrs_post_init__` issue** — perhaps `group_max_concurrency` doesn't propagate from the BTA's attrs init to the WorkGraph parent's runtime state
5. **Multiple WorkGraph instances** — if BTA creates a fresh WorkGraph per `_ainfer` call, the semaphore state from one call doesn't carry over

---

## Reproduction

```bash
source ~/.zshrc && cd /Users/tchen7/MyProjects/CoreProjects/OpenTeam

PYTHON=/opt/homebrew/anaconda3/bin/python
PP="src:../AgentFoundation/src:../PythonUtils/src"
LOG="/tmp/role_setup_outer_yaml_$(date +%H%M%S).log"

PYTHONPATH="$PP" $PYTHON -m test.openteam.resources.tools.role_setup.test_role_setup_through_yaml \
  -r "test/openteam/resources/tools/create_role/_runtime/20260415_153712/outputs/role_document.md" \
  --max-facets 4 \
  --max-inner-facets 3 \
  --log-level INFO \
  > "$LOG" 2>&1 &
```

Then check inner stream start timestamps:
```bash
WS=$(ls -dt /Users/tchen7/MyProjects/CoreProjects/OpenTeam/test/openteam/resources/tools/role_setup/_runtime/*/ | head -1)
for outer in worker_0 worker_1 worker_2 worker_3; do
  earliest=$(find "$WS/children/$outer/children/" -name "stream_*.txt" -exec ls -lT {} \; 2>/dev/null | awk '{print $6, $7, $8, $9}' | sort | head -1)
  echo "  $outer: $earliest"
done
```

If all 4 timestamps are within ~2 minutes of each other → bug is reproduced.

---

## Impact

- **Functional:** All deliverables are produced correctly; the run completes successfully
- **Resource:** 4× concurrent inner BTAs each spawn 15-23 inner workers → ~70 concurrent acli/RovoChat processes simultaneously
- **Quota:** Higher API rate limit pressure; risk of throttling
- **Cost:** No saving from concurrency limits — full parallel cost
- **Determinism:** No effect on output quality (all workers complete eventually)

---

## Suggested Investigation Steps

1. **Add diagnostic logging** at `workgraph.py:1798`:
   ```python
   _logger.info("WorkGraph._arun creating semaphore: group_max_concurrency=%s, max_concurrency=%s",
                self.group_max_concurrency, self.max_concurrency)
   ```

2. **Add diagnostic logging** at `workgraph.py:822` (just before semaphore acquire):
   ```python
   if semaphore:
       _logger.info("Node %s (group=%s) acquiring semaphore", self.name, self.group)
       await semaphore.acquire()
       _logger.info("Node %s acquired semaphore", self.name)
   ```

3. **Re-run** and inspect log to confirm:
   - Is the semaphore dict actually `{'skill_tool_creation': Semaphore(2), 'skill_tool_association': Semaphore(1)}`?
   - Are nodes attempting to acquire? Are they being granted immediately?
   - Are they holding the semaphore for the full duration of `await w.ainfer(q)`?

4. **Check `__attrs_post_init__`** of BTA — verify that `group_max_concurrency` is properly inherited by the WorkGraph base class.

5. **Check if `_run` (sync) vs `_arun` (async) is the actual code path** — add a log at the very start of each.

---

## Workaround

Set `max_concurrency: 2` (global) instead of `group_max_concurrency` — this should be honored if the global semaphore path works. However, this conflates groups (creation + association share the same limit) and may interact poorly with the aggregator (per the docstring at lines 102-118 of `breakdown_then_aggregate_inferencer.py`).

Alternative: accept the over-concurrency for now since it works correctly, just uses more resources than intended.

---

## Related Code Locations

- `/Users/tchen7/MyProjects/CoreProjects/AgentFoundation/src/agent_foundation/common/inferencers/agentic_inferencers/flow_inferencers/breakdown_then_aggregate_inferencer.py`
  - Lines 692-693: `worker_group = task_type if isinstance(self.worker_factory, dict) else None`
  - Line 717: `group=worker_group` passed to `WorkGraphNode`
  - Line 1424: `await WorkGraph._arun(self, inference_input, **kwargs)`

- `/Users/tchen7/MyProjects/CoreProjects/PythonUtils/src/python_utils/common_objects/workflow/workgraph.py`
  - Line 1200: `group_max_concurrency: Optional[Dict[str, int]] = attrib(default=None, kw_only=True)`
  - Lines 1798-1810: per-group semaphore creation in `WorkGraph._arun()`
  - Lines 745-748: per-group semaphore selection in `WorkGraphNode._arun()`
  - Lines 822-823, 915-916: semaphore acquire/release in `WorkGraphNode._arun()`

---

## Notes

The same `group_max_concurrency` mechanism is used in the **inner** BTA (`role_setup_skill_tool_creation.yaml`):
```yaml
group_max_concurrency:
  skill_tool_creation_research: 3
  skill_tool_creation_investigation: 2
```

Whether the inner BTA also fails to honor this should be verified — but past inner BTA runs DID appear to limit concurrency correctly (research workers in batches of 3). This may indicate the issue is specific to the **outer** BTA (which has BTAs as workers, not flat inferencers), or it may be that the inner BTA also doesn't honor the limit but it's less observable.
