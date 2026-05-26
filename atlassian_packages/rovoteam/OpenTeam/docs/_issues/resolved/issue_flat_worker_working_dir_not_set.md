# Issue: Flat (Non-BTA) Worker Working Directory Not Set to Child Workspace

**Discovered:** 2026-04-19  
**Run:** `_runtime/20260419_184628`  
**Worker:** `worker_0` (skill_tool_association — flat RovoDevCLI, not an inner BTA)  
**Severity:** Medium — file writes go to wrong location; content is correct but mis-placed

---

## Symptom

`role_tool_association.json` (14KB, high-quality content) was written to:
```
/Users/tchen7/MyProjects/CoreProjects/OpenTeam/outputs/role_tool_association.json
```

Instead of:
```
_runtime/20260419_184628/children/worker_0/outputs/role_tool_association.json
```

The file content is correct — the LLM did the right work. But the working directory was wrong so file reads/writes went to the project root instead of the child workspace.

---

## Root Cause

`_configure_child_workspace` in `breakdown_then_aggregate_inferencer.py` sets `working_dir` for child workers. However, for **flat single-inferencer workers** (non-BTA, e.g., `RovoDevCliInferencer` used for `skill_tool_association`), the `working_dir` is not set to the child workspace root.

The raw_output log confirms:
```
Working in /Users/tchen7/MyProjects/CoreProjects/OpenTeam   ← PROJECT ROOT (wrong)
```

For inner BTA workers, `_configure_child_workspace` recursively configures the child BTA which sets its own workspace. For flat workers, this recursive path doesn't apply — the flat worker's `working_dir` is never patched to point to the child workspace.

---

## Evidence

```
InferenceArgs resume file shows no working_dir override.
raw_output first line: "Working in /Users/tchen7/MyProjects/CoreProjects/OpenTeam"
role_tool_association.json found at: OpenTeam/outputs/  (project root)
worker_0/outputs/ directory: empty
```

---

## Impact

- File content is correct but at wrong path
- `promote_worker_deliverables` copies from `children/worker_0/outputs/` → finds nothing → nothing promoted
- `role_tool_association.json` ends up at project root, not in BTA's final outputs
- This will affect the conflict-aware aggregator (Component 2) which looks in child workspace outputs

---

## Why `working_dir = worker_ws.root` Is The Correct Fix

**`working_dir` controls the CWD when acli starts** (line 333: `cwd=self.working_dir`). When the LLM writes `outputs/role_tool_association.json` (a relative path), it resolves relative to CWD:
- CWD = project root → writes to `OpenTeam/outputs/role_tool_association.json` ❌ (current behavior)
- CWD = `children/worker_0/` → writes to `children/worker_0/outputs/role_tool_association.json` ✅ (desired)

**The codebase is still accessible** — with `yolo: true`, the agent can read any file via ABSOLUTE paths. The aggregator already works this way: its `working_dir = children/aggregator/` but it still reads source files with absolute paths. Setting `worker_ws.root` as the worker's `working_dir` is exactly the same pattern.

**Verified pattern:** BTA already does this for the aggregator (lines 1012-1016):
```python
self._configure_child_workspace(agg_inf, agg_ws)
if hasattr(agg_inf, "working_dir"):
    agg_inf.working_dir = str(agg_ws.root)
```

The fix mirrors this exactly — add the same two lines for workers at line 748:

```python
# Line 748 area in breakdown_then_aggregate_inferencer.py
self._configure_child_workspace(worker, worker_ws)
if hasattr(worker, "working_dir"):          # NEW — mirror aggregator pattern (lines 1015-1016)
    worker.working_dir = str(worker_ws.root)
```

This is a **one-line fix** that mirrors the existing aggregator pattern exactly.

---

## Verification

After fix: `_runtime/.../children/worker_0/outputs/role_tool_association.json` should exist.  
`Working in` line in raw_output should show `children/worker_0/` path (not project root).

---

## Resolution (2026-04-19 20:34)

**Fix applied** to `breakdown_then_aggregate_inferencer.py:747-755`:

```python
self._configure_child_workspace(worker, worker_ws)
# Mirror aggregator pattern (lines ~1015-1016): set working_dir
# for terminal-based inferencers (e.g., RovoDevCliInferencer,
# ClaudeCodeCliInferencer) so relative file writes resolve to the
# worker's child workspace, not the parent process CWD. API-based
# inferencers (RovoChat, BTA) lack `working_dir` and are skipped
# by hasattr — keeping this fix safe and future-proof.
if hasattr(worker, "working_dir"):
    worker.working_dir = str(worker_ws.root)
```

**Tests:** 91/91 pass (test_role_setup_through_yaml + test_outer_bta_yaml_equivalence + related).

**Will be verified:** On next E2E run, worker_0 (skill_tool_association) should write `role_tool_association.json` to `_runtime/<ts>/children/worker_0/outputs/` instead of project root.
