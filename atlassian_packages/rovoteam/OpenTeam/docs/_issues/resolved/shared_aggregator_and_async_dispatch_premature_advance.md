# Issue: Shared Aggregator Instance + Async Dispatch Premature Advancement

**Date:** 2026-04-19 to 2026-04-22  
**Resolved:** 2026-04-22  
**Severity:** Critical (data loss + broken UX)  
**Status:** ✅ Resolved  

---

## Summary

A cluster of five interconnected issues in the BTA (BreakdownThenAggregate) pipeline and the conversational inferencer's agentic loop, causing: deliverable files being overwritten with garbage, inner BTA template resolution failing, node statuses stuck on "Pending/Running", and the LLM prematurely declaring "Phase 1 complete!" while background tasks were still running.

---

## Issue 1: Shared `aggregator_inferencer` Instance (Concurrency Bug)

**Root cause:** When `_import_` in YAML resolved to a merged dict, Hydra instantiated it ONCE and baked the single `aggregator_inferencer` instance into `functools.partial`'s keywords. All concurrent inner BTA workers shared the same object. When workers ran in parallel, they raced to overwrite `aggregator_inferencer._workspace`, causing `_finalize_response` to copy deliverables from the wrong workspace.

**Evidence:** `id(worker_1.aggregator_inferencer) == id(worker_2.aggregator_inferencer)` — confirmed empirically.

**Fix:** Introduced `_ImportFactory` class in `_instantiate.py`. `_import_` now marks the config with `_factory_: true`. After Hydra instantiation, `_apply_import_factory()` replaces the partial with an `_ImportFactory` that re-instantiates from raw config on each call. Also renamed old behavior to `_import_shared_`.

**Files:** `PythonUtils/src/python_utils/config_utils/_instantiate.py`

## Issue 2: `_finalize_output` Overwriting Aggregator Deliverables

**Root cause:** After BTA's `_finalize_response` copied the 50KB deliverable via `shutil.copytree`, control returned to `_ainfer_single` which called `self._finalize_output(result)`. Since BTA has `template_manager` set but `has_local_access = False`, `_finalize_output` wrote `extract_delimited(str(result))` — a 2.8KB summary — to the same `outputs/role_document.md`, overwriting the correct 50KB file.

**Evidence:** `outputs/role_document.md` = 2,831 bytes vs `children/aggregator/outputs/role_document.md` = 50,357 bytes.

**Fix:** Added `_deliverables_copied` flag in `_finalize_response`. Overrode `_finalize_output` in BTA to skip when flag is set.

**Files:** `AgentFoundation/.../breakdown_then_aggregate_inferencer.py`

## Issue 3: Inner BTA Template Manager Not Resolving

**Root cause:** `_ImportFactory` stored the inner BTA's raw config with `_template_manager.templates: "prompt_templates"` (relative path from YAML). The outer executor overrode `_template_manager.templates` to an absolute path, but the override only applied to the ROOT config, not the inner config nested under `worker_factory.skill_tool_creation`. When `_ImportFactory.__call__` later instantiated, the TemplateManager couldn't find the directory → `templates=None` → `_prepare_input` returned `"prompt_templates"` as the literal prompt text → the breakdown inferencer received this garbage string.

**Evidence:** `inner.template_manager.templates = None`, `inner.template_manager.default_template = "prompt_templates"`.

**Fix:** `_ImportFactory` captures outer-scope injectables during creation. In `__call__`, outer injectables override inner config's `_`-prefixed keys before re-instantiation.

**Files:** `PythonUtils/src/python_utils/config_utils/_instantiate.py`

## Issue 4: Stale Node Status ("Running"/"Pending" on Completed Nodes)

**Root cause:** Two contributing factors:
1. **RAF batching bug:** The `setTasks` updater closure in `useGraphState.js` read `pendingUpdates.current` lazily. The synchronous code after `setTasks(...)` cleared the array before React processed the updater — updates silently lost.
2. **Missing reconciliation:** No mechanism to correct stale statuses after all nodes completed.

**Fix:** 
- Captured `const updates = pendingUpdates.current` before the clear (RAF fix).
- Added `GraphReconcileEvent` emitted after `WorkGraph._arun()` completes. Frontend `handleGraphReconcile` corrects any stale statuses and logs gaps via `console.warn`.
- Added stream-based auto-correct: if a node receives streaming content but shows "pending", infer "running".

**Files:** `useGraphState.js`, `graph_events.py`, `graph_interactive_adapter.py`, `websocket_interactive.py`, `useManagerChat.js`, `breakdown_then_aggregate_inferencer.py`, `workgraph.py`

## Issue 5: Premature "Phase 1 Complete!" (Async Dispatch Agentic Loop Continuation)

**Root cause:** When the LLM called `/create-role`, the tool was dispatched fire-and-forget (returning "Tool launched asynchronously..."). The agentic loop continued to iteration #2, where the LLM saw the placeholder in conversation history, interpreted it as success, and generated "Phase 1 complete!" with a confirmation widget — while the task was still running.

**Evidence:** Turn session logs showed TWO `RovoDevCliInferencer` stream files: iteration #1 (correct tool call), iteration #2 (premature "Phase 1 complete!" 28 seconds later). The fire-and-forget architecture was correct (verified from April 20 session where it worked with zero-byte InferenceResponse), but the LLM's behavior was stochastic.

**Misdiagnosis chain:**
1. Initially attributed to fire-and-forget being broken → changed to await → broke the auto-advance mechanism entirely
2. Then attributed to missing SOP re-evaluation → added SOP re-eval in tool result → didn't fix because SOP nextstep guidance is rendered per-turn, not per-iteration
3. Finally traced to the correct root cause: the agentic loop's `content = _CONTINUE_AFTER_TOOLS` triggering iteration #2

**Fix:** Set `_async_tool_dispatched = True` in `_execute_tool_call` when fire-and-forget dispatches. In the agentic loop (all three tool execution paths), check the flag and return `AgenticResult` early instead of continuing. The auto-advance mechanism (task_completed → client synthetic message → new turn) handles Phase 1b correctly.

**RankEvolve reference:** RankEvolve solved a similar problem with a 2-second "ASYNC DEFENSE" sleep after tool dispatch, giving fast-completing tasks time to update `prior_context`. OpenTeam's tasks take 5-20 minutes, so sleep doesn't help. Our fix extends the pattern with an early-exit guard.

**Files:** `AgentFoundation/.../conversational/conversational_inferencer.py`

## Issue 6: Messy Breakdown Rendering

**Root cause:** `json.dumps(sub_queries, indent=2)` emitted the full verbose breakdown structure (descriptions, todos, args, priority scores) as the breakdown node's stream content.

**Fix:** Replaced with a clean numbered markdown summary.

**Files:** `AgentFoundation/.../breakdown_then_aggregate_inferencer.py`

---

## Timeline

| Date | Action | Outcome |
|------|--------|---------|
| Apr 19 | User reports deliverables not copying | Traced to shared `aggregator_inferencer` |
| Apr 20 | Implemented `_ImportFactory`, deliverable overwrite fix, template fix, reconcile, breakdown rendering | 5 fixes landed, 137 tests pass |
| Apr 21 | User reports premature "Phase 1 complete!" | Initially misdiagnosed as fire-and-forget being broken |
| Apr 21 | Changed to await-based dispatch | Broke auto-advance mechanism (no Phase 1b guidance) |
| Apr 22 | Traced session logs — discovered fire-and-forget was correct | Reverted await, found real root cause (agentic loop iteration #2) |
| Apr 22 | Implemented `_async_tool_dispatched` flag + early exit | Fixed premature advancement while preserving auto-advance |
