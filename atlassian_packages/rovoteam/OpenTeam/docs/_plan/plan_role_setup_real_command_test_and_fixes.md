# Plan: Test Real `/role_setup` Command + Conflict-Aware Aggregator (Fix Worker Deliverable Conflicts)

**Date:** 2026-04-19  
**Last Updated:** 2026-04-19 19:20 (Issue #2 CLOSED confirmed by diagnostics; E2E run `_runtime/20260419_184628` in progress at 34 min — inner BTA aggregators now running, outer workers still active)

**Context:** Following the successful manual run of `test_role_setup_through_yaml.py` at `_runtime/20260419_140325`, issues need addressing:

1. **Test the real `/role_setup` command** (not just the BTA bypass) — **TODO**
2. ~~**Fix `group_max_concurrency` not honored** in BTA~~ — **✅ CLOSED: Was not a bug** (see Issue #2)
3. **Fix worker deliverable conflicts** during `promote_worker_deliverables` — **TODO (Track A)**

## Progress Summary (as of 2026-04-19 19:00)

### ✅ Completed Work

| Item | Status | Details |
|---|---|---|
| `test_role_setup_through_yaml.py` E2E run | ✅ Succeeded | `_runtime/20260419_140325` — 59.2 min, all 4 subtasks + aggregator |
| `test_role_setup_inner_bta_through_yaml.py` | ✅ Working | Multiple subtasks verified (1, 2, 3) |
| `_configure_child_workspace` logger list fix | ✅ Fixed | `breakdown_then_aggregate_inferencer.py` |
| `build_subtask_breakdown_only` JSON decode fix | ✅ Fixed | `executor.py` |
| `_finalize_response` recursive copytree | ✅ Fixed | `shutil.copytree` replaces flat loop |
| `_finalize_response` pipeline report guard | ✅ Fixed | `copied_any_deliverable` flag |
| `use_final_deliverables_folder=True` in executor | ✅ Fixed | `executor.py` `InferencerWorkspace` |
| `workspace.root` override (dot-notation) | ✅ Fixed | `test_role_setup_inner_bta_through_yaml.py` |
| `role_setup.yaml` — outer BTA yaml | ✅ Created | Full outer BTA with `skill_tool_creation` + `skill_tool_association` workers |
| `role_setup_skill_tool_creation.yaml` | ✅ Created | Inner BTA yaml (renamed from `inner_bta_skill_tool_creation.yaml`) |
| `_import_` key support in `load_config` | ✅ Implemented | PythonUtils `_instantiate.py` — yaml file composition |
| `_deep_merge` for yaml overrides | ✅ Implemented | PythonUtils `_instantiate.py` |
| `group_max_concurrency` in `role_setup.yaml` | ✅ Configured | `skill_tool_creation: 2, skill_tool_association: 1` |
| Diagnostic logs in `workgraph.py` | ✅ Added | Semaphore creation (line ~1810), selection (line ~750), acquire/release (line ~829/927) |
| Issue #2 root cause investigation | ✅ RESOLVED | Semaphore IS working; `children/` dirs scaffolded before acquire |
| `skill_tool_association` worker + yaml | ✅ Created | `skill_tool_association.jinja2` + yaml entry + `promote_worker_deliverables: true` |
| `group_conflicts_by_parent` helper design | ✅ Designed | In plan Component 0 |
| Outer equivalence tests | ✅ 174/174 passing | `test_outer_bta_yaml_equivalence.py` |
| Conflict-aware aggregator plan | ✅ Fully designed | Component 0-6, Track A A0-A8 |

### ⏳ In Progress

| Item | Status |
|---|---|
| E2E run `_runtime/20260419_184628` | ⏳ Running (34+ min, 171 releases, inner BTA aggregators now streaming — outer workers completing) |

### 📋 TODO (Not Started)

| Item | Priority | Track |
|---|---|---|
| Generic `find_conflicting_and_agreed_files` + `safe_copy_per_file` in PythonUtils | High | Track A (A0) |
| BTA wrapper + `make_conflict_aware_prompt_builder` | High | Track A (A4-A5) |
| `_finalize_response` → `safe_copy_per_file` refactor | High | Track A (A5.1) |
| `role_setup_report.jinja2` rewrite as conflict resolver | High | Track A (A6) |
| `/create_role` test alignment (src/ yaml + `execute()`) | Medium | Phase A |
| `/role_setup` yaml promotion to src/ + executor refactor | Medium | Phase B |

---

## Issue 1: Align Tests With Real `/role_setup` Command (And Same For `/create_role`)

### Discovery — Critical Findings

**Finding 1: Yaml duplication & drift**
- `/create_role` has TWO copies of `create_role_bta.yaml`:
  - **`src/.../create_role/create_role_bta.yaml`** ← formal/production (loaded by `executor.execute()` at runtime), **timestamp Apr 17, 14:19**, 76 lines
  - **`test/.../create_role/yaml_configs/create_role_bta.yaml`** ← test duplicate, **timestamp Apr 15, 14:36**, 74 lines
- They differ by 2 lines: src/ version has `output_path: "breakdown_output.md"` on the breakdown_inferencer (a deliberate enhancement made in src/ but never propagated to test/).
- **The src/ version is the formal, more recent, authoritative file.** The test/ version is stale.

**Finding 2: Test bypasses `execute()`**
- `test_create_role_through_yaml.py` loads the test/ yaml directly via `load_config()` + `instantiate()` + `bta.ainfer()`, completely bypassing `executor.execute()` (the real entry point that MCP uses)
- `test_create_role_bta_yaml_equivalence.py` also references the test/ yaml at line 36
- Result: **Neither test validates the real `/create_role` command path.** They could pass while the real command silently breaks.

**Finding 3: `/role_setup` is structurally different**
- `src/.../role_setup/` has `tool.json` ✅ but **NO yaml** (executor.py is fully programmatic, not yaml-driven)
- All `role_setup` yamls live ONLY in `test/.../role_setup/yaml_configs/` — they have NEVER been promoted to src/
- The real `/role_setup` slash command runs a completely different code path than our yaml-driven test

### Approach: Use src/ As the Single Source of Truth

For BOTH `/create_role` and `/role_setup`, the formal yaml(s) live in **`src/`** alongside the executor. Tests load FROM src/ — no duplicate test copies. Tests invoke `executor.execute()` directly to validate the full real command path.

### Proposed Fix — Phase A: `/create_role` Cleanup + True E2E Test (Low Risk)

**Goal:** Make `test_create_role_through_yaml.py` a real end-to-end test that invokes `executor.execute()` directly (not just `bta.ainfer()`), so it validates the FULL `/create_role` command path that MCP uses.

#### What `executor.execute()` Adds Over Bare BTA Call

The current test only exercises `load_config() → instantiate() → bta.ainfer()`. The real `execute()` ALSO does:

| Layer | What | Currently Tested? |
|---|---|---|
| 1. Argument parsing from MCP-style dict | Reads `role_description`, `--max-facets` | ❌ |
| 2. Workspace resolution from `session_context["working_dir"]` | Server-managed per-task dir | ❌ |
| 3. YAML loading from `Path(__file__).parent` | Loads src/ formal yaml | ✅ (but loads test/ yaml) |
| 4. Override construction (workspace_root, max_breakdown, _template_manager.templates) | Builds dict for load_config | ❌ (test does it differently) |
| 5. Template path resolution (absolute prompt_templates path) | Avoids CWD-related issues | ❌ |
| 6. WebSocketGraphReporter attachment | UI graph visualization for task panel | ❌ |
| 7. BTA inference | The actual `await inferencer.ainfer()` | ✅ |
| 8. Context updates (`role_document_path`, `role_document_working_dir`) | For downstream MCP messaging | ❌ |
| 9. ToolExecutionResult wrapping | Return shape MCP expects | ❌ |

**Result:** The current test would pass even if layers 1, 2, 4, 5, 6, 8, 9 broke — silently leaving `/create_role` non-functional in production.

#### Phase A Steps

| Step | Action | File |
|---|---|---|
| A1 | Update equivalence test `_YAML_PATH` to load `src/.../create_role_bta.yaml` | `test/.../test_create_role_bta_yaml_equivalence.py` line 36 |
| A2 | Run equivalence test against src/ yaml — verify all assertions pass (the only diff is `output_path: "breakdown_output.md"` addition; assertions should be unaffected) | (test run) |
| A3 | **Refactor `test_create_role_through_yaml.py` to call `execute()` directly** instead of `load_config() + bta.ainfer()`. Build `arguments` and `session_context` dicts in the test, pass them to `execute()`, assert on `ToolExecutionResult` shape | `test/.../test_create_role_through_yaml.py` |
| A4 | Run the refactored test end-to-end against a small role description — verify it produces the role document AND the `context_updates` returned correctly | (test run) |
| A5 | **Delete `test/.../create_role/yaml_configs/create_role_bta.yaml`** (no longer referenced after A1 and A3) | (file deletion) |
| A6 | (Optional) Rename `test_create_role_through_yaml.py` → `test_create_role_e2e.py` to reflect its new role as true end-to-end test | (file rename) |

#### Refactored Test Pattern

```python
# test_create_role_through_yaml.py (refactored)

import asyncio
import os
from pathlib import Path
from openteam.server.resources.tools.create_role.executor import execute

async def main(role_description: str, working_dir: Path, max_facets: int = 4):
    arguments = {
        "role_description": role_description,
        "--max-facets": max_facets,
    }
    session_context = {
        "working_dir": str(working_dir),
        "interactive": None,           # No UI in tests
        "task_id": "test-task-001",
        "cloud_id": os.environ.get("CLOUD_ID"),
        "uct_token": os.environ.get("UCT_TOKEN"),
        "email": os.environ.get("EMAIL"),
    }
    result = await execute(arguments, session_context)
    print(f"Result: {result.result[:200]}")
    print(f"Context updates: {result.context_updates}")
    
    # Validate the real command path produces correct outputs
    doc_path = result.context_updates.get("role_document_path")
    assert doc_path and Path(doc_path).exists(), f"role_document_path missing or not found: {doc_path}"
    print(f"✅ Real /create_role command path validated. Document: {doc_path}")
```

### Proposed Fix — Phase B: `/role_setup` Promotion + True E2E Test (Medium-High Risk)

**Goal:** Promote the proven yaml-driven pipeline (from our `_runtime/20260419_140325` successful run) into `src/`, refactor `executor.execute()` to use it, and update `test_role_setup_through_yaml.py` to call `execute()` directly so it becomes a real end-to-end test of `/role_setup`.

#### Current State
- `src/.../role_setup/` has `tool.json` and a 1203-line programmatic `executor.py` — NO yaml
- All yamls live ONLY in `test/.../role_setup/yaml_configs/`
- Real `/role_setup` slash command runs the programmatic executor — **completely different from what we've been testing**

#### Phase B Steps

| Step | Action | File |
|---|---|---|
| B1 | Copy `test/.../role_setup/yaml_configs/role_setup.yaml` → `src/.../role_setup/role_setup.yaml` | (file move) |
| B2 | Copy `test/.../role_setup/yaml_configs/role_setup_skill_tool_creation.yaml` → `src/.../role_setup/role_setup_skill_tool_creation.yaml` | (file move) |
| B3 | **Refactor `src/.../role_setup/executor.py:execute()`** to use yaml-driven BTA, mirroring `create_role` executor pattern. Replace the 915-line programmatic BTA with `load_config(Path(__file__).parent / "role_setup.yaml")` + `instantiate(cfg)` + `await bta.ainfer(role_doc_text)`. Build `overrides` dict for `workspace_root`, `max_breakdown` (from `--max-facets`), `worker_factory.skill_tool_creation.max_breakdown` (from `--max-inner-facets`), and `_template_manager.templates`. Attach WebSocketGraphReporter for UI. Build `context_updates` for downstream MCP messaging. Wrap result in `ToolExecutionResult`. | `src/.../role_setup/executor.py` |
| B4 | **Refactor `test_role_setup_through_yaml.py` to call `execute()` directly** with `arguments` + `session_context` dicts (same pattern as Phase A3). Validates the FULL `/role_setup` command path. | `test/.../test_role_setup_through_yaml.py` |
| B5 | Run the refactored test end-to-end — verify outputs match the proven `_runtime/20260419_140325` reference run | (test run) |
| B6 | Update `test_outer_bta_yaml_equivalence.py` to load src/ yaml | `test/.../test_outer_bta_yaml_equivalence.py` |
| B7 | Update `test_inner_bta_yaml_equivalence.py` to load src/ yaml | `test/.../test_inner_bta_yaml_equivalence.py` |
| B8 | Update `test_role_setup_inner_bta_through_yaml.py` default `--yaml-config` to src/ yaml. Optionally also refactor it to call `execute()` (or a smaller internal entry point if needed for the inner-only test scope) | `test/.../test_role_setup_inner_bta_through_yaml.py` |
| B9 | **Delete `test/.../role_setup/yaml_configs/`** dir entirely (after all tests updated and passing) | (dir deletion) |
| B10 | (Optional) Rename `test_role_setup_through_yaml.py` → `test_role_setup_e2e.py` for clarity | (file rename) |

#### Refactored `executor.execute()` Pattern (B3)

```python
# src/.../role_setup/executor.py (refactored, mirrors create_role pattern)

async def execute(
    arguments: dict,
    session_context: dict,
) -> "ToolExecutionResult":
    """Real /role_setup entry point — yaml-driven outer BTA pipeline."""
    from agent_foundation.common.inferencers.agentic_inferencers.conversational.protocols import (
        ToolExecutionResult,
    )
    import agent_foundation.common.configs.registered_targets  # noqa: register BTA targets
    from python_utils.config_utils import load_config, instantiate

    role_document_path = arguments.get("role_document_path", "")
    max_facets = int(arguments.get("--max-facets", arguments.get("max_facets", 8)))
    max_inner_facets = int(arguments.get("--max-inner-facets", arguments.get("max_inner_facets", 5)))
    
    working_dir = session_context.get("working_dir")
    yaml_path = Path(__file__).parent / "role_setup.yaml"
    
    overrides: dict = {
        "max_breakdown": max_facets,
        "worker_factory.skill_tool_creation.max_breakdown": max_inner_facets,
        "_template_manager.templates": str(
            Path(__file__).resolve().parent.parent.parent / "prompt_templates"
        ),
    }
    # NOTE on override key choice: "workspace.root" (dot-notation) is REQUIRED here
    # because role_setup.yaml has a `workspace:` field with `use_final_deliverables_folder: false`
    # that must be preserved. Using "workspace_root" (BTA's convenience attr) would NOT touch
    # the yaml's `workspace:` field — and InferencerBase line 153 sets `self._workspace = self.workspace`
    # FIRST, so the convenience attr would be ignored. Dot-notation overrides into the existing
    # `workspace:` field, preserving `use_final_deliverables_folder` while patching the root path.
    # (For comparison: create_role uses "workspace_root" because its yaml has NO `workspace:` field
    # and the convenience attr is the only path.)
    if working_dir:
        overrides["workspace.root"] = str(working_dir)
    
    cfg = load_config(str(yaml_path), overrides=overrides)
    inferencer = instantiate(cfg)
    
    # WebSocketGraphReporter attachment
    interactive = session_context.get("interactive")
    task_id = session_context.get("task_id", "")
    if interactive is not None and task_id:
        from agent_foundation.ui.graph_interactive_adapter import WebSocketGraphReporter
        inferencer.graph_reporter = WebSocketGraphReporter(interactive, task_id)
    
    # Read role document content (RovoDevCLI breakdown will read this via local file access too)
    role_doc_text = Path(role_document_path).read_text() if role_document_path else ""
    
    result_text = await inferencer.ainfer(role_doc_text)
    
    # Build context_updates with paths to deliverables
    context_updates = {}
    if working_dir:
        context_updates["role_setup_working_dir"] = str(working_dir)
        report_path = Path(working_dir) / "outputs" / "role_setup_report.md"
        if report_path.exists():
            context_updates["role_setup_report_path"] = str(report_path)
        # Also surface skills/tools/association deliverables
        skills_dir = Path(working_dir) / "outputs" / "skills"
        tools_dir = Path(working_dir) / "outputs" / "tools"
        if skills_dir.exists():
            context_updates["skills_dir"] = str(skills_dir)
        if tools_dir.exists():
            context_updates["tools_dir"] = str(tools_dir)
        association_path = Path(working_dir) / "outputs" / "role_tool_association.json"
        if association_path.exists():
            context_updates["role_tool_association_path"] = str(association_path)
    
    return ToolExecutionResult(
        result=str(result_text),
        context_updates=context_updates,
    )
```

#### Risk Mitigation for Phase B

The current `role_setup` `executor.py` is 1203 lines with multiple test-script-only modes (`--breakdown-only`, `--subtask-breakdown-only`, `--run-subtask`). These were used by `test_role_setup.py` (programmatic test) and `test_role_setup_inner_bta_through_yaml.py`.

**Strategy options:**

1. **Hard cutover (cleanest):** Replace `execute()` with yaml-driven version. Move the granular test helpers (`build_subtask_breakdown_only`, `build_run_subtask`) into a separate `_test_helpers.py` module within `src/` (or move to test/ entirely). Update `test_role_setup.py` and `test_role_setup_inner_bta_through_yaml.py` to import from the helper module.

2. **Coexistence (safer for transition):** Add yaml-driven path as a NEW `execute_yaml()` function alongside existing `execute()`. Switch `tool.json` to point to `execute_yaml()`. Keep `execute()` for the existing modes until they're migrated.

**Recommendation:** Strategy 1 (hard cutover) — cleaner long-term, smaller maintenance burden. Pre-condition: all existing test-mode usages identified and migrated to helper module.

### Validation

After Phase A:
1. `test_create_role_through_yaml.py` passes loading from src/ yaml
2. `test_create_role_bta_yaml_equivalence.py` passes against src/ yaml
3. No reference to `test/.../yaml_configs/create_role_bta.yaml` remains anywhere

After Phase B:
1. `/role_setup` invoked via MCP runs the yaml-driven pipeline
2. Output structure matches the proven `_runtime/20260419_140325` reference run
3. All test scripts updated and passing
4. No reference to `test/.../role_setup/yaml_configs/` remains

---

## Issue 2: `group_max_concurrency` — ✅ RESOLVED (Not a Bug)

> **STATUS: CLOSED.** Empirically verified 2026-04-19 via diagnostic run `_runtime/20260419_183553`.
>
> **Finding:** The semaphore IS working correctly. `children/` directories are scaffolded BEFORE semaphore acquire (BTA creates dirs upfront during graph construction). Directory existing ≠ worker running. Verified timeline:
> - `18:38:24` worker_1 acquired `skill_tool_creation` (slot 1/2)
> - `18:38:24` worker_2 acquired `skill_tool_creation` (slot 2/2) ← limit reached
> - `18:38:24` worker_3 BLOCKED (still "acquiring...")
> - `18:43:10` worker_3 acquired ← **4 min 46 sec later**, after a slot freed up ✅
>
> `group_max_concurrency: skill_tool_creation: 2` is honored. No fix needed.
> Track B steps (B1-B6) and Track C (QueuedExecutorBase refactor) are **FULLY CANCELLED**.
> Issue moved to `docs/_issues/resolved/`.

## Original Issue 2 Analysis (HISTORICAL — kept for reference) in BTA

### Verification Status (from independent investigation)

The mechanism IS structurally correct in isolation. All these were independently verified to work:

| Component | Status | Evidence |
|---|---|---|
| BTA inherits `group_max_concurrency` field from `WorkGraph` | ✅ | attrs hierarchy confirmed |
| YAML instantiation sets `bta.group_max_concurrency` correctly | ✅ | Live test: `{'skill_tool_creation': 2, 'skill_tool_association': 1}` |
| Worker nodes get correct `group=` value | ✅ | Live test: worker_1, 2, 3 all show `group='skill_tool_creation'` |
| `WorkGraph._arun()` creates per-group semaphores | ✅ | workgraph.py line 1799 |
| `WorkGraphNode.arun()` acquires/releases semaphore | ✅ | workgraph.py lines 823-917 |
| Test script uses async path (`bta.ainfer() → _ainfer → WorkGraph._arun`) | ✅ | Code trace |
| Standalone semaphore test passes (Semaphore A=2, B=1 enforced) | ✅ | Tested in isolation |

**Yet in the actual BTA run, `group_max_concurrency` was NOT honored** — all 4 workers spawned within ~90 seconds (timestamps 14:09:12 to 14:10:46).

### This Is a Debugging Task, Not a Direct Code Fix

The code is correct in every component examined in isolation. We need **runtime data** to identify the exact failure point. Two diagnostic logs needed:

1. **`workgraph.py:1799`** — log semaphore creation:
   ```python
   _logger.info(
       "WorkGraph._arun creating semaphores: group_max_concurrency=%s, max_concurrency=%s",
       self.group_max_concurrency, self.max_concurrency,
   )
   ```

2. **`workgraph.py:743-749`** — log semaphore SELECTION (this is where `node.group` is mapped to a specific semaphore from the dict; if the lookup is wrong, the bug is here):
   ```python
   if isinstance(_semaphore_or_map, dict):
       semaphore = _semaphore_or_map.get(self.group) or _semaphore_or_map.get(None)
       _logger.info(
           "Node %s: group=%r, dict_keys=%s, selected_semaphore=%s",
           self.name, self.group, list(_semaphore_or_map.keys()),
           id(semaphore) if semaphore else None,
       )
   else:
       semaphore = _semaphore_or_map
   ```

3. **`workgraph.py:823`** — log acquire/release timing (reveals if blocking actually happens):
   ```python
   _logger.info(
       "Node %s (group=%s) calling acquire on semaphore id=%s",
       self.name, self.group, id(semaphore) if semaphore else None,
   )
   await semaphore.acquire()
   _logger.info("Node %s acquired", self.name)
   ```

**After adding these logs, re-run with `--max-facets 4 --log-level INFO`. The logs will reveal:**
- Whether the semaphore dict was created with the right keys
- Whether nodes are looking up the right semaphore
- Whether acquire is being called at all (or blocked)
- Whether all nodes acquire near-simultaneously (suggests the dict isn't being looked up correctly)

### What We Know (Verified by Live Code Inspection)

**MRO chain DOES correctly reach `WorkGraph.__attrs_post_init__`.** Verified empirically:
```
BTA MRO: ['BreakdownThenAggregateInferencer', 'InferencerBase', 'WorkGraph', ...]
```
With cooperative `super().__attrs_post_init__()` calls, the chain DOES reach `WorkGraph.__attrs_post_init__`. However, that method only does `start_node.set_parent_debuggable(self)` — it has NOTHING to do with semaphores or concurrency.

**`group_max_concurrency` IS correctly set on the BTA instance** — it's an attrs field, set by the constructor BEFORE `__attrs_post_init__` runs.

**An earlier hypothesis (now disproven)** suggested the MRO was broken. That was wrong — verified the MRO chain works correctly. The actual root cause remains unknown and must be determined by runtime diagnostic logs.

### Possible Root Causes (All UNVERIFIED — Diagnostic Logs Required)

The following hypotheses must each be confirmed or eliminated by diagnostic data — DO NOT apply fixes based on guesses:

1. **Semaphore dict is built with WRONG keys** at line 1799 (e.g., `None` keys, or keys don't match `node.group` values)
2. **Semaphore dict IS correct, but nodes look up wrong key** in `WorkGraphNode.arun` (e.g., `node.group` is `None` at lookup time despite being set at construction)
3. **Semaphores are correctly created and looked up, but `acquire()` is short-circuited** somewhere (e.g., a `return` before line 823 due to `is_loaded_from_saved_result` check)
4. **Semaphores ARE acquired correctly, but in a DIFFERENT event loop** than the worker tasks run in (cross-loop bug — `Semaphore` doesn't synchronize across loops)
5. **The `group_max_concurrency` dict is mutated/reset between `__init__` and `_arun`** by some intermediate code path (e.g., a `_configure_child_workspace` that creates a fresh BTA without grouping)
6. **The semaphore IS being acquired but ALL workers acquire near-simultaneously** because the fan-out at `gather()` time spawns all worker tasks before any of them reach the `acquire()` line — the `acquire()` IS blocking the actual work, but observers see all "spawned"

### Disproven Hypotheses (Do NOT pursue)

- ❌ **MRO is broken — `WorkGraph.__attrs_post_init__` is never called.**
  Verified empirically: `BTA.__mro__ = [BTA, InferencerBase, WorkGraph, ...]` and `WorkGraph.__attrs_post_init__` calls `super().__attrs_post_init__()` cooperatively. Combined with `InferencerBase.__attrs_post_init__()` calling `super()`, the chain DOES reach `WorkGraph.__attrs_post_init__`. Furthermore, `WorkGraph.__attrs_post_init__` only does `start_node.set_parent_debuggable(self)` — it does NOT initialize `group_max_concurrency` or any other concurrency state. So even if it were skipped, that would not cause the bug. **Adding `WorkGraph.__attrs_post_init__(self)` to BTA's `__attrs_post_init__` would be a no-op fix and should NOT be applied.**

### Implementation Steps — ✅ COMPLETED

1. **Diagnostic logs added** — `workgraph.py` (semaphore creation ~line 1810, selection ~line 750, acquire/release ~line 829/927). Used `self.log_info()` (not `_logger` which doesn't exist in workgraph.py — a bug in the original diagnostic log code that was caught and fixed before the successful diagnostic run).
2. **Re-run small E2E** (`--max-facets 4 --max-inner-facets 1` to keep workers shallow). Capture log output.
3. **Inspect the logs** — match runtime data against the 6 hypotheses above. Eliminate hypotheses that don't fit.
4. **Apply targeted fix** based on the surviving hypothesis (likely 1-3 lines of code).
5. **Add unit test** — assert that BTA with `group_max_concurrency` set actually limits worker concurrency at runtime (use a synthetic concurrent-task test pattern with timestamps).
6. **Re-run E2E** — verify the timestamps confirm proper concurrency limiting.

### When to Escalate to Bigger Refactor

ONLY if diagnostics reveal a structural problem (e.g., asyncio.Semaphore truly cannot work in BTA's nested-loop architecture), THEN consider the bigger initiative documented separately ("Unified Sync/Async QueuedExecutor"). That initiative is documented later in this plan as a **separate, decoupled enhancement** — not blocking the immediate fix.

---

## Issue 3: Worker Deliverable Conflicts During Promotion

> **NOTE — ORGANIZATIONAL CONSOLIDATION:** Issue #3 is **subsumed by Issue #4** (the conflict-aware aggregator design). The evidence section below is retained for context, but the **primary action plan, design, and implementation steps have all moved to Issue #4 and Track A in the Implementation Order table**. Do NOT implement anything from Issue #3 in isolation. Specifically:
>
> - The "Recommended Fix Combination" subsection below ("Apply Fix 3A + 3D + 3C") is **HISTORICAL** — it was the pre-Issue-#4 plan. It is now **superseded by Track A steps A1-A8** in the Implementation Order. Do NOT follow the historical recommendation.
> - The "Concrete Evidence" subsection IS still useful as background motivation for Issue #4.
> - Specific Fix 3A (conflict logging) is fully absorbed into Issue #4 Component 1 (full conflict detection); Fix 3D (association prompt) is preserved as Track A Step A1; Fix 3C (subtask scope) is preserved as Track A Step A3.

### Concrete Evidence (from `_runtime/20260419_140325`)

| File | worker_0 | worker_1 | worker_3 | Root (last wins) |
|---|---|---|---|---|
| `skills/email-distribution/SKILL.md` | 12.7KB (short) | 26.1KB | 26.1KB | 26.1KB |
| `skills/program-analytics/SKILL.md` | 15.6KB (short) | 31.7KB | 31.7KB | 31.7KB |

**Critical insight:** Worker_0 produced INCOMPLETE versions (small file size). Workers 1 and 3 produced COMPLETE versions. The "last writer wins" was correct THIS time (worker_3 = full content), but **non-deterministic** — if worker_0 had run last, the final deliverable would have been the incomplete version.

### Root Cause

`promote_worker_deliverables` uses `shutil.copytree(src, deliverables_dst, dirs_exist_ok=True)` which:
- ✅ Creates new dirs / merges existing dirs (correct)
- ❌ **OVERWRITES files with same name** (silent data loss)

In the actual run, all 4 outer workers produced overlapping files:

| File | worker_0 | worker_1 | worker_2 | worker_3 |
|---|---|---|---|---|
| `skills/cicd-pipeline-monitoring/SKILL.md` | ✅ | ✅ | ✅ | ✅ |
| `skills/program-analytics/SKILL.md` | ✅ | ✅ | ❌ | ✅ |
| `skills/email-distribution/SKILL.md` | ✅ | ✅ | ❌ | ✅ |
| `skills/capacity-planning-and-scheduling/SKILL.md` | ✅ | ✅ | ✅ | ✅ |
| `tools/cicd_metrics/{tool.json,executor.py}` | ✅ | ✅ | ✅ | ✅ |
| `tools/program_analytics_compute/{tool.json,executor.py}` | ❌ | ✅ | ❌ | ✅ |
| `role_tool_association.json` | ❌ MISSING from ALL workers ❌ |

**Each successive worker's copy overwrote the previous worker's version.** The final root has worker_3's versions (last in alphabetical sort order).

### Why This Happened (Design Issue)

Each `skill_tool_creation` outer worker is supposed to handle a **different** subtask (e.g., one creates `cicd_metrics`, another creates `program_analytics_compute`). But the LLM-generated subtasks ALL produced overlapping deliverables — each worker's inner BTA created the SAME set of skills.

This is a **prompt design issue** combined with a **silent overwrite issue**:
- **Prompt issue:** The breakdown isn't producing sufficiently distinct subtasks; each subtask LLM ends up creating the same broad set of skills
- **Code issue:** Even if subtasks WERE distinct, identical filename collisions would silently overwrite

### Missing `role_tool_association.json`

Critical: **No `role_tool_association.json` was found anywhere in the run** — not in any worker's outputs/, not in root.

Possible causes:
1. The association worker's prompt doesn't trigger `create_file` for the JSON
2. The prompt fix to switch from `--output-file` to `outputs/role_tool_association.json` was misinterpreted by the LLM
3. The worker wrote the JSON but to a different path

### Proposed Fixes

**Fix 3A (Code): Detect & log conflicts in `promote_worker_deliverables`**

Modify `_finalize_response` in `breakdown_then_aggregate_inferencer.py`:

```python
if self.promote_worker_deliverables and self._workspace is not None:
    children_dir = self._workspace.children_dir
    if os.path.isdir(children_dir):
        for child_name in sorted(os.listdir(children_dir)):
            if not child_name.startswith("worker_"):
                continue
            child_root = os.path.join(children_dir, child_name)
            child_fd = os.path.join(child_root, "outputs", "final_deliverables")
            child_out = os.path.join(child_root, "outputs")
            src = child_fd if os.path.isdir(child_fd) else child_out
            if not (os.path.isdir(src) and os.listdir(src)):
                continue
            # Detect conflicts BEFORE overwriting
            conflicts = []
            for root, dirs, files in os.walk(src):
                rel = os.path.relpath(root, src)
                for f in files:
                    dst_file = os.path.join(deliverables_dst, rel, f)
                    if os.path.exists(dst_file):
                        conflicts.append(os.path.join(rel, f))
            if conflicts:
                _logger.warning(
                    "Worker %s deliverables conflict with existing files: %s",
                    child_name, conflicts,
                )
            shutil.copytree(src, deliverables_dst, dirs_exist_ok=True)
            ...
```

**Fix 3B (Code): Per-worker namespacing option**

Add new BTA attr `worker_deliverables_namespace: bool = False`. When true, each worker's deliverables go under a subdir named after the worker:

```python
dst_for_this_worker = os.path.join(deliverables_dst, child_name)
shutil.copytree(src, dst_for_this_worker, dirs_exist_ok=False)
```

But this creates a different problem — the canonical `skills/<name>/SKILL.md` structure becomes `worker_0/skills/<name>/SKILL.md`, which may not match downstream expectations. **Not recommended for `role_setup` use case.**

**Fix 3C (Prompt): Make subtask deliverables truly distinct**

Update outer breakdown prompt (`role_setup.jinja2`) to explicitly instruct each subtask to produce **only its specific deliverables**, not duplicate work. Example:

```
For each skill_tool_creation subtask, produce ONLY the skills and tools that
your subtask is specifically about. Do NOT produce skills or tools that other
subtasks will produce. Each skill/tool should be created by exactly ONE subtask.
```

This requires the breakdown LLM to clearly partition responsibilities AND each inner BTA to respect that scope.

**Fix 3D (Prompt): Fix the missing `role_tool_association.json`**

Verify the association prompt explicitly tells the LLM to use `create_file outputs/role_tool_association.json` (not `--output-file` or other paths). Re-test with smaller scope to confirm the JSON is produced.

### Recommended Fix Combination

For immediate impact:
1. **Apply Fix 3A** (conflict detection logging) — minimal, helps debug future runs
2. **Apply Fix 3D** (verify association prompt) — fix the missing JSON
3. **Apply Fix 3C** (prompt for distinct subtasks) — eliminate root cause of overlapping deliverables

Skip Fix 3B (namespacing) — adds complexity without solving the right problem.

---

## Issue 2 — Solution: Unified Sync/Async `QueuedExecutorBase` (Option 3)

### Decision

Instead of:
1. ❌ Patching `asyncio.Semaphore` (fragile — known cross-loop/cancellation issues)
2. ❌ Building a standalone `AsyncQueuedExecutor` (works but creates parallel hierarchies)

**We refactor `QueuedExecutorBase` in `mp_utils/queued_executor.py` to support both sync (Thread/Process) AND async (asyncio) backends with per-group concurrency limits.** This gives us a single unified API that handles all concurrency scenarios — current and future.

### Why This Is the Right Long-Term Investment

| Benefit | Impact |
|---|---|
| **Eliminates entire class of asyncio.Semaphore bugs** | Fixes BTA `group_max_concurrency` bug at root |
| **Single unified abstraction for sync + async + multi-backend (Thread/Process/asyncio)** | Reduces cognitive load; one API to learn |
| **Per-group concurrency** native to the base class | Solves not just BTA but any future use case (research workers, batch HTTP, file ops) |
| **Reuses existing `Task`/`TaskState`/`TaskStatus` types** | No data structure duplication |
| **Reuses existing `QueueServiceBase` abstraction** | `Redis`, `thread_queue`, `email_queue`, `storage_based` queues all work for both sync and async |
| **Reuses existing `run_async()` dynamic-task generation logic** | Router/wrapper modes work for both backends |
| **Adds observability** | Pool size = guaranteed max concurrent, queue depth = pending |
| **Cancellation-safe** | Consumer dies cleanly; no counter leaks |
| **FIFO ordering within group** | Predictable execution order |

### Refactor Plan for `QueuedExecutorBase`

#### Step 1: Generalize the base class

Add new attributes (backward-compatible defaults):

```python
@attrs(slots=False)
class QueuedExecutorBase(ABC):
    # ... existing attrs ...
    num_workers: int = attrib(default=1)
    
    # NEW: per-group concurrency limits
    group_max_concurrency: Dict[Hashable, int] = attrib(factory=dict)
    
    # NEW: default group when Task.group is not set
    default_group: Hashable = attrib(default=None)
```

#### Step 2: Add async-friendly hooks to the abstract base

The current abstract methods (`_create_worker`, `_start_worker`, `_join_worker`, `_is_worker_alive`) assume sync semantics (return `Thread`/`Process`). Generalize:

```python
class QueuedExecutorBase(ABC):
    @abstractmethod
    def _create_worker(self, worker_id: int, group: Hashable, active_flag: list) -> Any:
        """Create a worker. May be Thread/Process/asyncio.Task/coroutine."""
    
    @abstractmethod
    def _start_worker(self, worker: Any) -> None:
        """Start worker. For asyncio, this is a no-op (Task auto-starts)."""
    
    @abstractmethod
    def _join_worker(self, worker: Any, timeout: float) -> Any:
        """Wait for worker. May return awaitable for async backends."""
    
    @abstractmethod
    def _is_worker_alive(self, worker: Any) -> bool:
        """Check if worker is still active."""
    
    # NEW: Allow async run() override
    # NOTE on relationship to existing run_async(): `run_async` (line 463 of
    # current queued_executor.py) is a sync method that returns when async tasks
    # complete via run_in_executor. It is NOT a coroutine; callers can't `await`
    # it. We add `arun()` as a coroutine method that callers CAN await directly,
    # enabling native asyncio integration. `run_async` is preserved unchanged for
    # backward compat. Existing callers continue using `run_async`; new callers
    # in async contexts (like BTA's _arun) use `arun`.
    #
    # For async subclasses, an `async_submit(task)` API is provided to
    # submit tasks before/during arun(). The base default wraps sync run()
    # ONLY when no async-specific override exists. The default is intentionally
    # limited — true async backends MUST override arun() to gain real async
    # concurrency (the wrapper is for sync-backend interop only).
    async def arun(self, active_flag: Optional[list] = None) -> List[TaskState]:
        """Async version of run(). Default impl wraps sync run() in executor.
        Override in async subclasses for native asyncio support.

        Subclasses overriding this MUST preserve the (active_flag) signature
        to satisfy LSP. Use submit()/async_submit() to enqueue tasks separately."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.run, active_flag)
```

#### Step 3: Per-group concurrency support in `_worker_loop()`

Modify `_worker_loop` to track which group a worker is dedicated to. The loop pulls only from that group's queue:

```python
def _worker_loop(self, worker_id: int, group: Hashable, active_flag: list):
    """Worker loop bound to a specific group's queue."""
    queue_id = self._queue_id_for_group(group)  # NEW: per-group queue routing
    while active_flag[0]:
        task = self.input_queue_service.get(queue_id, timeout=self.poll_interval)
        if task is None:
            continue
        state = self._execute_task(worker_id, task)
        self.output_queue_service.put(self.output_queue_id, state)
```

#### Step 4: Worker spawning with per-group counts

In `start()`, spawn workers per group:

```python
def start(self, active_flag=None) -> list:
    # If group_max_concurrency is set, spawn workers per group
    if self.group_max_concurrency:
        for group, max_conc in self.group_max_concurrency.items():
            for i in range(max_conc):
                self._workers.append(
                    self._create_worker(len(self._workers), group, active_flag)
                )
        # Default group workers
        if self.default_group is not None:
            for i in range(self.num_workers):
                self._workers.append(
                    self._create_worker(len(self._workers), self.default_group, active_flag)
                )
    else:
        # Backward-compatible: single pool with num_workers
        for i in range(self.num_workers):
            self._workers.append(
                self._create_worker(len(self._workers), None, active_flag)
            )
    
    for w in self._workers:
        self._start_worker(w)
    return active_flag
```

#### Step 5: Submit routes to correct group queue

```python
def submit(self, task: Task) -> str:
    group = getattr(task, "group", self.default_group)
    queue_id = self._queue_id_for_group(group)
    self.input_queue_service.put(queue_id, task)
    return task.task_id
```

#### Step 6: Add `Task.group: Hashable` field

In `task.py`:
```python
@attrs
class Task:
    # ... existing fields ...
    group: Optional[Hashable] = attrib(default=None)
```

#### Step 7: Create new `AsyncQueuedExecutor` subclass

```python
@attrs(slots=False)
class AsyncQueuedExecutor(QueuedExecutorBase):
    """Async-native queued executor using asyncio.Task as workers.
    
    Each worker is an asyncio.Task that pulls from an asyncio.Queue.
    Per-group concurrency is enforced by the number of consumer tasks
    spawned per group.
    """
    
    # Override: workers are coroutine tasks, queue is asyncio.Queue
    _async_queues: Dict[Hashable, asyncio.Queue] = attrib(factory=dict, init=False)
    
    def _create_worker(self, worker_id: int, group: Hashable, active_flag: list):
        """Create an asyncio.Task as the consumer."""
        if group not in self._async_queues:
            self._async_queues[group] = asyncio.Queue()
        return asyncio.create_task(
            self._async_worker_loop(worker_id, group, active_flag)
        )
    
    def _start_worker(self, worker: asyncio.Task) -> None:
        """No-op — asyncio.Task starts automatically."""
        pass
    
    def _join_worker(self, worker: asyncio.Task, timeout: float):
        """Return an awaitable that completes when worker finishes."""
        return asyncio.wait_for(worker, timeout=timeout)
    
    def _is_worker_alive(self, worker: asyncio.Task) -> bool:
        return not worker.done()
    
    async def _async_worker_loop(self, worker_id: int, group: Hashable, active_flag: list):
        """Async consumer loop: pulls from group queue, executes async/sync callable."""
        queue = self._async_queues[group]
        while active_flag[0]:
            try:
                task: Optional[Task] = await asyncio.wait_for(
                    queue.get(), timeout=self.poll_interval
                )
            except asyncio.TimeoutError:
                continue
            
            if task is None:  # Sentinel
                queue.task_done()
                return
            
            state = TaskState(task_id=task.task_id, status=TaskStatus.RUNNING)
            try:
                if asyncio.iscoroutinefunction(task.callable):
                    state.result = await task.callable(*task.args, **(task.kwargs or {}))
                else:
                    state.result = task.callable(*task.args, **(task.kwargs or {}))
                state.status = TaskStatus.SUCCESS
            except asyncio.CancelledError:
                state.status = TaskStatus.CANCELLED
                raise
            except Exception as e:
                state.exception = e
                state.status = TaskStatus.FAILED
            finally:
                self.output_queue_service.put(self.output_queue_id, state)
                queue.task_done()
    
    async def arun(self, active_flag: Optional[list] = None) -> List[TaskState]:
        """Run queued tasks to completion using asyncio-native execution.

        LSP-compliant signature matching base class. Tasks must be submitted via
        async_submit(task) BEFORE calling arun(). After all tasks are submitted,
        arun() spawns consumer workers per group, processes the queue, and returns
        results once all workers complete (sentinel-based shutdown).
        """
        if active_flag is None:
            active_flag = [True]
        # Spawn workers per group (consumers)
        await self.async_start(active_flag)
        # Send sentinels — one per worker per group
        for group, max_conc in self.group_max_concurrency.items():
            for _ in range(max_conc):
                await self._async_queues[group].put(None)
        # Wait for all workers
        await asyncio.gather(*self._workers, return_exceptions=True)
        # Collect results
        return self._collect_results()

    async def async_submit(self, task: Task) -> str:
        """Async-compatible submission. Routes task to its group's queue."""
        group = getattr(task, "group", self.default_group)
        queue = self._async_queues.setdefault(group, asyncio.Queue())
        await queue.put(task)
        return task.task_id
```

#### Step 8: Backward Compatibility

All existing usage of `QueuedThreadPoolExecutor` / `QueuedProcessPoolExecutor` / `SingleThreadExecutor` continues to work unchanged:
- `group_max_concurrency` defaults to `{}` (empty dict, no grouping)
- `Task.group` defaults to `None`
- Old code path (`num_workers` only) remains the primary code path when no grouping is configured

#### Step 9: Comprehensive Tests

Create `tests/mp_utils/test_async_queued_executor.py` with:

| Test Group | Test Cases |
|---|---|
| **Basic execution** | Single async task succeeds; sync task succeeds; mixed sync/async tasks; empty task list; one task per group |
| **Concurrency limits** | Single group with N=2 limit (verify max 2 concurrent via timestamps); multi-group with different limits (3 + 2); ungrouped uses default |
| **Pool semantics** | Verify exactly N consumer tasks spawned per group; no extra; workers exit cleanly on sentinel |
| **Result handling** | Results returned in original task order; FIFO within group; mixed group results interleaved correctly |
| **Error handling** | Task raises exception → state.status = FAILED, others continue; exception in one group doesn't stop other groups |
| **Cancellation** | Cancel pool → all in-flight tasks marked CANCELLED, results recorded, workers exit |
| **Backpressure** | Bounded queue (`maxsize=N`) → producer blocks when queue full |
| **Loop binding** | Queue + workers bound to active loop → no cross-loop bugs |
| **Backward compat** | Existing `QueuedThreadPoolExecutor` tests still pass with no changes |
| **Refactored base class** | `group_max_concurrency` defaults work; per-group worker spawning correct |
| **Integration** | `AsyncQueuedExecutor` can replace asyncio.Semaphore in a small WorkGraph-like demo, and concurrency IS enforced |

Target: **40-50 unit tests** for the async executor + **5-10 regression tests** for refactored base class.

---

## Issue 4: BTA Aggregator Becomes Conflict Resolver, Not Just Reporter

### Current State (From Reference Run `_runtime/20260419_140325`)

The current outer aggregator (RovoDevCLI with `role_setup_report.jinja2`) only **writes a synthesis report** — it does NOT see worker deliverables, does NOT resolve conflicts, and does NOT integrate overlapping content. Meanwhile, `promote_worker_deliverables: true` does a blind `shutil.copytree` for each worker in alphabetical order — **last writer wins**.

**Concrete evidence of the problem:**
- 4 workers each produced ~10 files (5 skills + 4 tool files + executor.py per tool)
- Total: 40+ files across worker outputs, but really only ~10 unique deliverables
- Many files have IDENTICAL content across workers (no real conflict)
- Some files have DIFFERENT content (real semantic conflicts):
  - `skills/email-distribution/SKILL.md`: worker_0=12.7KB (incomplete) vs worker_1/3=26.1KB (complete)
  - `skills/program-analytics/SKILL.md`: worker_0=15.6KB (incomplete) vs worker_1/3=31.7KB (complete)
- The aggregator never sees ANY of this — it just writes a generic report
- Final root deliverable is determined non-deterministically by alphabetical worker iteration order

### The Architecture Insight

**Code is good at:** comparing file content (hash-based, fast, free, deterministic)
**LLM is good at:** semantic merging of conflicting documents (smart, expensive, targeted)

**Currently we use neither well:** Code blindly copies (last-writer-wins), LLM never sees the deliverables.

### CRITICAL Architectural Note: Sequencing

**Verified empirically in `breakdown_then_aggregate_inferencer.py`:**
```python
# Inside _ainfer / _infer methods (multiple call sites; pinned by function name not line):
result = WorkGraph._run(self, inference_input, **kwargs)  # workers + aggregator
self._finalize_response(result)                           # POST-aggregator
```

The aggregator runs **inside** `WorkGraph._run()` as a graph node — it completes BEFORE `_finalize_response` runs. Therefore conflict detection MUST happen **before** the aggregator runs, not in `_finalize_response`. The correct integration point is the `aggregator_prompt_builder` hook (BTA `attrib(default=None)` near top of class), which is invoked inside `_make_agg_fn()` (look for the function definition in BTA module) AFTER all workers complete but BEFORE the aggregator inferencer runs.

> **Note on line references:** Line numbers in this plan are approximate at the time of writing and may drift as code changes. When implementing, locate code by function/method name (e.g., `_make_agg_fn`, `_finalize_response`, `_build_agg_input`) rather than line numbers.

### Proposed Design: Hybrid Conflict-Aware Promotion (Revised — Correct Sequencing)

```
┌─────────────────────────────────────────────────────────────────┐
│ WorkGraph._run() / _arun() — graph executes:                     │
│                                                                  │
│ 1. Workers run in parallel → write to children/worker_*/outputs/ │
│                                                                  │
│ 2. aggregator_prompt_builder() invoked (BEFORE aggregator)       │
│    BTA hook — perfect injection point for conflict detection:    │
│    a) Walk all worker outputs                                    │
│    b) Compute canonical-form SHA-256 per file                    │
│    c) Categorize: agreed (single hash) vs conflict (multi-hash)  │
│    d) Auto-promote agreed files to deliverables_dst              │
│    e) Build aggregator input dict with conflict manifest:        │
│       {                                                          │
│         worker_summaries: [...],                                 │
│         deliverables_promoted: [{path, sha256, source_workers}],│
│         deliverables_with_conflicts: [{path, candidates: [...]}],│
│         deliverables_dst: "<abs path>"                           │
│       }                                                          │
│                                                                  │
│ 3. Aggregator (RovoDevCLI) runs with that input:                 │
│    - For each conflict, read all worker versions                 │
│    - Synthesize integrated/best version                          │
│    - Write merged version via create_file to deliverables_dst    │
│    - Write synthesis report to deliverables_dst/report.md        │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ _finalize_response() — runs AFTER graph completes:               │
│                                                                  │
│ - Aggregator's output dir already contains: agreed files +       │
│   merged versions of conflicts + report                          │
│ - Existing recursive copytree behavior unchanged for             │
│   `last_writer_wins` mode (backward compat)                      │
│ - For `delegate_to_aggregator` mode: agreed files were already   │
│   promoted at step 2(d); aggregator wrote merged conflicts.      │
│   _finalize_response just copies report + leftovers if any.      │
└─────────────────────────────────────────────────────────────────┘
```

**Why this is correct:**
- `aggregator_prompt_builder` is invoked at the right moment in the BTA flow (line 806 inside `_make_agg_fn`)
- It can synchronously walk worker outputs because all workers have completed before it runs
- It can mutate the destination directory (auto-promote) and inject paths into the aggregator's prompt
- The aggregator then runs with full context AND has filesystem access (RovoDevCLI `yolo: true`) to read/merge conflict candidates

### Why This Is the Right Design

| Property | Benefit |
|---|---|
| Code does deterministic work (hash + copy) | Fast, free, reliable, no LLM cost |
| LLM does semantic merging only | Targeted to actual conflicts |
| No wasted LLM tokens on files that already agree | Significant cost reduction (most files match) |
| Deterministic non-conflicting deliverables | No more "last writer wins" non-determinism |
| Aggregator gets structured signal (paths + sizes) | Can be opinionated about better version |
| Report is a side-effect of conflict resolution | Aggregator does merge AND report in one pass |
| Failure-tolerant | If aggregator fails, agreed files are already in place |
| Generic mechanism | Useful beyond `role_setup` for any conflict-prone BTA |

### Implementation Details

#### Component 0: Generic Multi-Root File Diff Helper (NEW — Foundation)

**ARCHITECTURAL UPGRADE:** Instead of building conflict detection inside BTA, extract it as a **generic, reusable utility** in PythonUtils. This is genuinely better engineering — the helper has zero BTA dependencies, is trivially testable as a pure function over directories, and can be used by any project that needs to merge multi-source file trees (backup tools, data dedup, parallel build artifact merging, etc.).

**Location:** `/Users/tchen7/MyProjects/CoreProjects/PythonUtils/src/python_utils/path_utils/path_listing.py` (extends the existing 545-line module that already has `sort_paths`, `FullPathMode`, etc. — natural fit, no new module needed).

**API:**

```python
class FileCandidate(NamedTuple):
    """One candidate version of a file from a specific root."""
    root: str               # The root path this file came from
    abs_path: str           # Absolute path to the file
    rel_path: str           # Path relative to its root (for matching across roots)
    size: int               # Size in bytes
    content_hash: str       # SHA-256 of canonical-normalized content


class MultiRootDiff(NamedTuple):
    """Categorization of files across multiple roots."""
    agreed: Dict[str, List[FileCandidate]]      # Same content_hash → safe to copy any
    conflicting: Dict[str, List[FileCandidate]] # Different content_hashes → need resolution
    unique: Dict[str, FileCandidate]            # Only one root has this file


def canonicalize_text(content: bytes, *, max_normalize_size: int = 10*1024*1024) -> bytes:
    """Normalize text for stable hashing: line endings, trailing whitespace, NFC unicode.
    Binary files (UnicodeDecodeError) and huge files bypass normalization."""

def hash_file_canonical(path: str, *, normalize: bool = True) -> str:
    """SHA-256 of file content, optionally canonical-normalized."""

def find_conflicting_and_agreed_files(
    roots: Iterable[str],
    *,
    relative_to: Optional[Dict[str, str]] = None,
    file_filter: Optional[Callable[[str], bool]] = None,
    normalize_text: bool = True,
) -> MultiRootDiff:
    """Recursively compare files across multiple root paths.
    Returns categorization: agreed (identical), conflicting (different), unique (only one)."""

def safe_copy_per_file(
    diff: MultiRootDiff,
    dest: str,
    *,
    skip_existing: bool = True,
    conflict_fallback: Literal["skip", "largest", "first"] = "skip",
) -> Dict[str, List[str]]:
    """Per-file copy based on diff categorization. NEVER overwrites existing files when
    skip_existing=True (this is the key safety property — aggregator's merged versions
    are protected). Returns counts per category for logging/observability."""


def group_conflicts_by_parent(
    diff: MultiRootDiff,
    *,
    parent_depth: int = 2,
) -> Dict[str, List[Dict[str, Any]]]:
    """Group conflicting files by their parent directory at given depth.

    Useful for semantic context: when an aggregator merges multiple files belonging
    to the same logical unit (e.g., `tools/cicd_pipeline_status/tool.json` AND
    `tools/cicd_pipeline_status/executor.py`), it benefits from seeing them
    together to maintain consistency (matching tool name in tool.json with
    function name in executor.py).

    Args:
        diff: Result from find_conflicting_and_agreed_files().
        parent_depth: How many path segments from the start define the "parent"
                      group key. E.g., depth=2 groups `tools/cicd_pipeline_status/tool.json`
                      and `tools/cicd_pipeline_status/executor.py` under
                      `tools/cicd_pipeline_status/`. depth=1 groups by top-level
                      directory only (`tools/`, `skills/`, etc.).

    Returns:
        Dict mapping parent_path → list of {path, candidates} dicts.
        Files whose path has fewer segments than parent_depth use their full
        rel_path as the key (degenerate group of one).

    Example return:
        {
            "tools/cicd_pipeline_status": [
                {"path": "tools/cicd_pipeline_status/tool.json", "candidates": [...]},
                {"path": "tools/cicd_pipeline_status/executor.py", "candidates": [...]},
            ],
            "skills/cicd-monitoring": [
                {"path": "skills/cicd-monitoring/SKILL.md", "candidates": [...]},
            ],
        }
    """
    # ~10 lines: split each rel_path on os.sep, take first parent_depth segments
    # as group key, append {path, candidates} to that group's list.
```

**Key safety property:** `safe_copy_per_file(skip_existing=True)` **NEVER overwrites existing files**. This eliminates the data-loss risk that motivated the prior plan's special-case `A5.1` step. With this helper, `_finalize_response` can be SIMPLER and SAFER than the original `shutil.copytree` — no special-casing for `delegate_to_aggregator` mode needed.

#### Component 1: BTA Wrapper Around the Generic Helper

BTA's conflict detection becomes a thin wrapper around the generic helper:

**Architectural correction:** Conflict detection must run BEFORE the aggregator inferencer. The `BreakdownThenAggregateInferencer` exposes an `aggregator_prompt_builder` callable hook (line 160) that is invoked inside `_make_agg_fn()` AFTER all workers complete but BEFORE the aggregator runs. This is the correct integration point.

The conflict detection now uses the generic `find_conflicting_and_agreed_files` helper from `python_utils.path_utils.path_listing` (Component 0). The BTA-specific layer just constructs the worker root list and calls the helper.

```python
import hashlib
import unicodedata
from typing import Dict, List, Tuple


# --- Canonical normalization (Flaw B fix) ---

def _canonicalize_text(content: bytes) -> bytes:
    """Normalize text content for stable hashing.

    Handles common LLM-induced byte-level variations that don't affect semantic
    meaning:
    - Decode as UTF-8 (silently ignoring decode errors → fall back to raw bytes)
    - Normalize line endings: CRLF → LF, CR → LF
    - Normalize trailing whitespace: rstrip per-line, single trailing newline
    - Unicode NFC normalization (combine accents to canonical form)

    Binary files (UnicodeDecodeError) bypass normalization and hash raw bytes.
    """
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return content  # Binary file — hash raw bytes
    # Line ending normalization
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Per-line trailing whitespace strip + single trailing newline
    lines = [line.rstrip() for line in text.split("\n")]
    text = "\n".join(lines).rstrip("\n") + "\n"
    # Unicode normalization
    text = unicodedata.normalize("NFC", text)
    return text.encode("utf-8")


def _sha256_of_file_canonical(path: str) -> str:
    """Compute SHA-256 of canonical-normalized file content.

    Reads the entire file (necessary for normalization) so this is NOT suitable
    for arbitrarily large files. For deliverables (typically <100KB), this is fine.
    For larger files, fall back to raw streaming hash if size > 10MB.
    """
    size = os.path.getsize(path)
    h = hashlib.sha256()
    if size > 10 * 1024 * 1024:
        # Large file — stream raw bytes (no normalization)
        with open(path, "rb") as f:
            while chunk := f.read(64 * 1024):
                h.update(chunk)
        return h.hexdigest()
    with open(path, "rb") as f:
        h.update(_canonicalize_text(f.read()))
    return h.hexdigest()


def _detect_conflicts_and_promote(
    deliverables_dst: str,
    children_dir: str,
    candidate_subdirs: Tuple[str, ...] = ("outputs/final_deliverables", "outputs"),
) -> Tuple[List[Dict], Dict[str, List[Dict]]]:
    """Detect deliverable conflicts across workers and auto-promote agreed files.
    
    Walks each worker's output directory (preferring final_deliverables/, falling
    back to outputs/), builds a content-keyed map of files, then categorizes each
    file as either "agreed" (single hash across all workers that have it) or
    "conflicting" (multiple hashes).
    
    Agreed files are immediately copied to deliverables_dst.
    Conflicting files are NOT copied — instead, paths to all worker versions
    are returned in a structured manifest for the aggregator to resolve.
    
    Args:
        deliverables_dst: Destination dir for promoted deliverables
            (typically <workspace>/outputs/final_deliverables/ or outputs/)
        children_dir: Workers' parent dir (typically <workspace>/children/)
        candidate_subdirs: Subdirs within each worker to look for deliverables.
            Tried in order; first existing one wins.
    
    Returns:
        deliverables_promoted: List of dicts with {path, size, source_workers, sha256}
        deliverables_with_conflicts: Dict from rel_path → list of {worker, abs_path, size, sha256}
    """
    # Step 1: Build content-keyed map of all candidate files across workers
    file_map: Dict[str, List[Dict]] = {}  # rel_path → [{worker, abs_path, size, sha256}, ...]
    
    for worker_name in sorted(os.listdir(children_dir)):
        worker_dir = os.path.join(children_dir, worker_name)
        if not os.path.isdir(worker_dir):
            continue
        # Find this worker's deliverables root
        worker_outputs = None
        for sub in candidate_subdirs:
            candidate = os.path.join(worker_dir, sub)
            if os.path.isdir(candidate) and os.listdir(candidate):
                worker_outputs = candidate
                break
        if worker_outputs is None:
            continue
        
        for root_dir, dirs, files in os.walk(worker_outputs):
            for fname in files:
                abs_path = os.path.join(root_dir, fname)
                rel_path = os.path.relpath(abs_path, worker_outputs)
                size = os.path.getsize(abs_path)
                sha = _sha256_of_file_canonical(abs_path)
                file_map.setdefault(rel_path, []).append({
                    "worker": worker_name,
                    "abs_path": abs_path,
                    "size": size,
                    "sha256": sha,
                })
    
    # Step 2: Categorize and act
    deliverables_promoted: List[Dict] = []
    deliverables_with_conflicts: Dict[str, List[Dict]] = {}
    
    for rel_path, instances in sorted(file_map.items()):
        unique_hashes = {inst["sha256"] for inst in instances}
        
        if len(unique_hashes) == 1:
            # All workers agree (or only one worker had it) → auto-promote
            src = instances[0]["abs_path"]
            dst = os.path.join(deliverables_dst, rel_path)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            deliverables_promoted.append({
                "path": rel_path,
                "size": instances[0]["size"],
                "sha256": instances[0]["sha256"],
                "source_workers": [inst["worker"] for inst in instances],
            })
            _logger.info(
                "Auto-promoted %s (%d bytes, agreed by %d worker(s))",
                rel_path, instances[0]["size"], len(instances)
            )
        else:
            # Conflict — defer to aggregator
            deliverables_with_conflicts[rel_path] = instances
            _logger.warning(
                "Conflict detected on %s — %d distinct versions across %d worker(s)",
                rel_path, len(unique_hashes), len(instances)
            )
    
    return deliverables_promoted, deliverables_with_conflicts
```

#### Component 2: Wire to BTA via `aggregator_prompt_builder` Hook (Flaw A Fix)

The conflict detector is invoked from a custom `aggregator_prompt_builder` callable that the BTA passes via the existing hook (line 160). This callable runs at the right time in the BTA flow (inside `_make_agg_fn` at line 806, AFTER all workers complete, BEFORE the aggregator runs).

Two integration approaches — both are valid; pick based on yaml ergonomics:

**Approach A: Yaml configures a callable factory**

Add to `role_setup.yaml`:
```yaml
aggregator_prompt_builder:
  _target_: agent_foundation.common.inferencers.agentic_inferencers.flow_inferencers.\
    breakdown_then_aggregate_inferencer.make_conflict_aware_prompt_builder
  conflict_resolution_mode: delegate_to_aggregator   # or: last_writer_wins
  candidate_subdirs: ["outputs/final_deliverables", "outputs"]
```

The `make_conflict_aware_prompt_builder()` factory returns a closure with the right signature for `aggregator_prompt_builder`:

```python
# In breakdown_then_aggregate_inferencer.py (or new helpers module)

def make_conflict_aware_prompt_builder(
    conflict_resolution_mode: str = "delegate_to_aggregator",
    candidate_subdirs: Tuple[str, ...] = ("outputs/final_deliverables", "outputs"),
    deliverables_subdir: str = "final_deliverables",
):
    """Factory: returns an aggregator_prompt_builder callable that detects conflicts.

    The returned callable matches the BTA's ACTUAL hook signature (verified
    in breakdown_then_aggregate_inferencer.py:756-768):

        (worker_results, original_query=..., worker_output_paths=...) -> dict_or_str

    Note: the hook does NOT receive the bta instance or workspace. We derive
    `children_dir` and `deliverables_dst` from the worker_output_paths (which
    look like `<workspace_root>/children/<worker_name>/outputs/<file>`).

    On invocation it:
    1. Derives `children_dir` from the first worker_output_path (parent of parent
       of the worker's output file = `<children_dir>/<worker>/`).
    2. Walks all worker outputs under children_dir.
    3. Computes canonical-form SHA-256 per file.
    4. Categorizes: agreed (single hash) vs conflict (multi-hash).
    5. If mode == 'delegate_to_aggregator': auto-promotes agreed files NOW;
       returns dict with deliverables_promoted + deliverables_with_conflicts +
       deliverables_dst → aggregator template renders conflict resolution prompt.
    6. If mode == 'last_writer_wins': skip conflict detection; return the
       traditional worker_summaries text; existing _finalize_response copytree
       behavior takes over (backward compat).
    """
    def _builder(worker_results, original_query=None, worker_output_paths=None):
        # last_writer_wins → traditional behavior, return text only
        if conflict_resolution_mode == "last_writer_wins":
            parts = [f"### Result {i+1}\n{r}" for i, r in enumerate(worker_results)]
            return "\n\n".join(parts)

        # Derive children_dir and workspace root from worker_output_paths
        if not worker_output_paths or not any(worker_output_paths):
            # No paths → can't detect conflicts; degrade gracefully to text mode
            parts = [f"### Result {i+1}\n{r}" for i, r in enumerate(worker_results)]
            return "\n\n".join(parts)

        # First valid path: <ws_root>/children/<worker>/outputs/<file>
        first_path = next(p for p in worker_output_paths if p)
        # Walk up to <ws_root>/children
        children_dir = os.path.dirname(  # → children/<worker>/outputs
            os.path.dirname(  # → children/<worker>
                os.path.dirname(os.path.abspath(first_path))  # → children/<worker> (or deeper if file is nested)
            )
        )
        # Robust traversal: walk up until we find a dir literally named "children"
        cur = os.path.abspath(first_path)
        while cur and os.path.basename(cur) != "children":
            parent = os.path.dirname(cur)
            if parent == cur:
                cur = None
                break
            cur = parent
        if cur is None:
            # Fallback: use derived children_dir
            cur = children_dir
        children_dir = cur
        ws_root = os.path.dirname(children_dir)
        # Mirror BTA._finalize_response: deliverables_dst is final_deliverables/ if
        # workspace has it, else outputs/
        if os.path.isdir(os.path.join(ws_root, "outputs", deliverables_subdir)):
            deliverables_dst = os.path.join(ws_root, "outputs", deliverables_subdir)
        else:
            deliverables_dst = os.path.join(ws_root, "outputs")
        os.makedirs(deliverables_dst, exist_ok=True)

        promoted, conflicts = _detect_conflicts_and_promote(
            deliverables_dst, children_dir, candidate_subdirs
        )
        return {
            "worker_summaries": [str(r) for r in worker_results],
            "deliverables_promoted": promoted,
            "deliverables_with_conflicts": [
                {"path": rp, "candidates": cands}
                for rp, cands in conflicts.items()
            ],
            "deliverables_dst": deliverables_dst,
        }
    return _builder
```

**RESOLVED — String rendering is required.** Verified via `inferencer_base.py:_build_template_feed`: the aggregator's `ainfer(X)` flows through `_render_prompt(X)` which calls `_build_template_feed(X)`, and that sets `feed["input"] = X`. So **whatever `prompt_builder` returns becomes `{{ input }}` in the jinja template** — NOT a set of top-level template variables. A dict return would render as `str(dict)` (Python repr) inside `{{ input }}`, which is unusable as a prompt.

**Therefore the closure MUST return a fully-rendered prompt STRING.** Two implementation options:

**Option 1 (RECOMMENDED — explicit):** Have the closure render its own jinja template (or string-format) into a string before returning:

```python
# Inside the closure, after computing promoted/conflicts:
prompt_text = (
    f"## Worker Summaries\n\n" + "\n\n".join(f"### Result {i+1}\n{r}" for i, r in enumerate(worker_results))
    + f"\n\n## Auto-Promoted Deliverables ({len(promoted)})\n"
    + "\n".join(f"- {p['path']} (sha256={p['sha256'][:8]}, from {', '.join(p['source_workers'])})" for p in promoted)
    + f"\n\n## Conflicts To Resolve ({len(conflicts)})\n"
    + "\n".join(_format_conflict(rp, cands) for rp, cands in conflicts.items())
    + f"\n\n## Deliverables Destination\n{deliverables_dst}\n"
)
return prompt_text
```

**Option 2 (alternative — template-driven):** Mutate `agg_inf.template_extra_feed` BEFORE returning so structured fields are available as top-level template vars:

```python
# Side effect: inject manifest into aggregator's extra feed
# Requires capturing agg_inf in the closure (extend factory signature)
agg_inf.template_extra_feed.update({
    "deliverables_promoted": promoted,
    "deliverables_with_conflicts": conflicts,
    "deliverables_dst": deliverables_dst,
})
# Then return the worker_summaries text as before
return "\n\n".join(f"### Result {i+1}\n{r}" for i, r in enumerate(worker_results))
```

**REVISED RECOMMENDATION: Option 2 (template_extra_feed mutation).**

**Rationale (correcting earlier recommendation):**
- **Option 1 forces the template to parse a flat string** via `{{ input }}` — clumsy, hard to maintain, no jinja2 control structures over structured data.
- **Option 2 makes individual variables (`{{ deliverables_with_conflicts }}`, `{{ deliverables_promoted }}`, `{{ deliverables_dst }}`) directly available** in the jinja template — clean, idiomatic, supports `{% for %}` loops over structured lists.
- The original concern with Option 2 was "leaks state by capturing `agg_inf`" — but capturing `agg_inf` ALSO solves the path-derivation fragility (Issue C from feedback): we get `bta` access via `agg_inf._bta` or by capturing `bta` in the factory directly. Two birds, one stone.

**Implementation:**

The factory captures both `bta` and resolves `agg_inf` lazily (since the aggregator inferencer isn't always available at factory construction time). Use a registration hook OR a getter callback:

```python
def make_conflict_aware_prompt_builder(
    conflict_resolution_mode: str = "delegate_to_aggregator",
    candidate_subdirs: Tuple[str, ...] = ("outputs/final_deliverables", "outputs"),
):
    """Factory: returns an aggregator_prompt_builder callable that detects conflicts
    and injects structured manifest into the aggregator's template_extra_feed.

    For Option 2 to work cleanly, the BTA hook signature must be extended to pass
    `bta` instance to the prompt_builder — this is a 1-line BTA change documented
    in step A4.1 below. Once `bta` is available, we get both:
      - bta._workspace.children_dir / deliverables_dir (no path reverse-engineering)
      - bta._aggregator_inferencer.template_extra_feed (target for injection)
    """
    def _builder(bta, worker_results, original_query=None, worker_output_paths=None):
        if conflict_resolution_mode == "last_writer_wins":
            return "\n\n".join(f"### Result {i+1}\n{r}" for i, r in enumerate(worker_results))

        # Option 2: clean access via bta instance (no path reverse-engineering)
        children_dir = str(bta._workspace.children_dir)
        deliverables_dst = (
            bta._workspace.deliverables_dir
            or str(bta._workspace.outputs_dir)
        )
        os.makedirs(deliverables_dst, exist_ok=True)

        promoted, conflicts = _detect_conflicts_and_promote(
            deliverables_dst, children_dir, candidate_subdirs
        )

        # Option 2 mechanics: inject structured manifest into aggregator's feed
        agg_inf = bta._aggregator_inferencer  # accessor: see step A4.1
        flat_conflicts = [
            {"path": rp, "candidates": cands}
            for rp, cands in conflicts.items()
        ]
        # Level 2: group conflicts by parent dir for semantic coherence.
        # Aggregator merging multiple files of the same logical unit (e.g., tool.json
        # + executor.py for one tool) needs them grouped together for consistency.
        from python_utils.path_utils.path_listing import group_conflicts_by_parent
        conflicts_grouped = group_conflicts_by_parent(diff, parent_depth=2)
        agg_inf.template_extra_feed.update({
            "deliverables_promoted": promoted,
            "deliverables_with_conflicts": flat_conflicts,             # Level 1: flat list
            "conflicts_grouped_by_parent": conflicts_grouped,          # Level 2: by parent dir
            "deliverables_dst": deliverables_dst,
            "worker_summaries": [str(r) for r in worker_results],
        })

        # Return value goes to {{ input }} — provide concise text summary
        return (
            f"Conflict-aware aggregation manifest injected into template feed. "
            f"{len(promoted)} auto-promoted, {len(conflicts)} conflicts to resolve."
        )
    return _builder
```

**Companion BTA change (Step A4.1):**

The current `aggregator_prompt_builder` hook signature in BTA is `(worker_results, original_query, worker_output_paths)`. Extend it to also pass `bta`:
```python
# In _make_agg_fn, when calling self.aggregator_prompt_builder:
agg_input = self.aggregator_prompt_builder(
    self,                          # NEW: bta instance — needed for Option 2
    worker_results,
    original_query=original_query,
    worker_output_paths=worker_output_paths,
)
```
This is backward-compatible if existing callers add `*args, **kwargs` or accept the new positional arg. Default `aggregator_prompt_builder` (when None) is unaffected.

**Implication for Component 3:** The template stays as-is — individual variables (`{{ deliverables_promoted }}`, `{{ deliverables_with_conflicts }}`, `{{ deliverables_dst }}`, `{{ worker_summaries }}`) ARE available because Option 2 injects them into `template_extra_feed`. **No template rewrite needed.**

**Approach B: Yaml field on BTA itself**

Add `conflict_resolution_mode` directly as a BTA attr; the BTA's default `aggregator_prompt_builder` (when None) constructs a wrapper internally based on this mode. Less explicit but requires no yaml changes for users who don't need conflict resolution.

**Recommendation:** Approach A — explicit, composable, no implicit BTA behavior changes, easy to test in isolation.

#### Component 3: Refactored Aggregator Prompt (`role_setup_report.jinja2`)

```jinja2
You are the FINAL synthesis stage of a parallel workflow. {{ worker_summaries | length }} workers
ran in parallel and produced deliverables. The BTA framework has already detected which deliverables
are AGREED across workers (auto-promoted to the root deliverables) and which have CONFLICTING versions
that need YOUR resolution.

# Your Two Tasks

## Task 1: Resolve Conflicting Deliverables ({{ deliverables_with_conflicts | length }} conflicts in {{ conflicts_grouped_by_parent | length }} logical groups)

{% if deliverables_with_conflicts %}
Conflicts are presented BELOW grouped by their parent directory (e.g., all files for one
tool grouped together). When merging multiple files for the same logical unit, you MUST
maintain CROSS-FILE CONSISTENCY (e.g., the tool name in `tool.json` must match the
function/class name referenced in `executor.py`).

For each conflict below, you must:
1. Read all worker versions from the local file system using `read_file`
2. Compare them — note which is most complete, which has best structure, which has best examples
3. Synthesize a single integrated, best version that incorporates the best parts of each
   (do NOT just pick one — actively merge content where each version contributes value)
4. Write the integrated version using `create_file` to the absolute path:
   `{{ deliverables_dst }}/<path>` where `<path>` is the rel_path shown in each conflict

### Conflicts to Resolve (grouped by parent)

{% for parent, group in conflicts_grouped_by_parent.items() %}
#### Group: `{{ parent }}/` ({{ group | length }} conflicting file{% if group | length != 1 %}s{% endif %})

{% if group | length > 1 %}
> ⚠️ **Cross-file consistency required:** All {{ group | length }} files in this group belong to
> the same logical unit. Ensure consistent naming, references, and structure across them.
{% endif %}

{% for conflict in group %}
**`{{ conflict.path }}`** — {{ conflict.candidates | length }} worker versions:
{% for c in conflict.candidates %}
- {{ c.worker }} (size: {{ c.size }} bytes, sha256: {{ c.sha256[:8] }}...): `{{ c.abs_path }}`
{% endfor %}

Output: `{{ deliverables_dst }}/{{ conflict.path }}`

{% endfor %}
{% endfor %}
{% else %}
No conflicts detected — all worker deliverables agreed and have been auto-promoted by the framework.
Proceed directly to Task 2.
{% endif %}

## Task 2: Generate Synthesis Report

Write a markdown report using `create_file` to:
`{{ deliverables_dst }}/role_setup_report.md`

The report MUST contain these sections:

### Section 1: Auto-Promoted Deliverables ({{ deliverables_promoted | length }} files)

The following deliverables had identical content across all workers and have been automatically
promoted to the final deliverables folder by the BTA framework. No aggregator action was required:

{% for d in deliverables_promoted %}
- `{{ d.path }}` ({{ d.size }} bytes, sha256: {{ d.sha256[:8] }}..., agreed by: {{ d.source_workers | join(', ') }})
{% endfor %}

### Section 2: Conflicts Resolved by Aggregator ({{ deliverables_with_conflicts | length }} files)

{% if deliverables_with_conflicts %}
For each conflict below, briefly explain:
- Which worker version(s) you used as the base
- What additional content you incorporated from other versions  
- Any contradictions between versions and how you resolved them
- Any signals (size, structure, completeness) that informed your decision

{% for conflict in deliverables_with_conflicts %}
**`{{ conflict.path }}`**: [Your explanation here]
{% endfor %}
{% else %}
No conflicts required resolution.
{% endif %}

### Section 3: Coverage & Gaps

Summarize what the role now has after this setup run:
- Skills produced and their purpose
- Tools produced and their purpose  
- Any gaps you noticed in coverage
- Any recommendations for follow-up work

### Section 4: Worker Contribution Summary

Briefly describe what each worker contributed:
{% for summary in worker_summaries %}
- Worker {{ loop.index0 }}: {{ summary[:200] }}{% if summary | length > 200 %}...{% endif %}
{% endfor %}
```

#### Component 4: Worker Prompt — Scope Discipline (BEST-EFFORT prevention; NOT primary fix)

**Honest framing:** LLMs ignore prompts ~30-50% of the time. Worker scope discipline is a useful **best-effort prevention layer** that reduces conflict frequency, but it is NOT the primary defense — the primary defense is the conflict resolver in Components 1-3 (which works deterministically regardless of LLM behavior). Even with perfect scope adherence, identical-content overlaps are still possible (e.g., when subtask scopes legitimately reference the same shared skill); the conflict resolver handles those auto-promotions transparently.

**Original section follows:**

In `skill_tool_creation.jinja2`, add a strong scope-discipline section near the top:

```jinja2
## ⚠️ YOUR ASSIGNED SCOPE FOR THIS WORKER

You are responsible for producing skills and tools related ONLY to:

> {{ subtask_description }}

**Critical rules:**
1. **Stay within your scope.** Do NOT produce SKILL.md or tool.json files for skills/tools 
   outside this scope, even if your research uncovers them.
2. **Other workers handle other scopes** — duplicating their work creates conflicts that
   waste effort and may produce incomplete versions that lose to better versions in conflict
   resolution.
3. **Out-of-scope discoveries:** If your research reveals a skill/tool that would be useful
   but is outside your assigned scope:
   - Do NOT write a SKILL.md / tool.json / executor.py for it
   - DO mention it in your `<Response>` text as: 
     "DISCOVERED OUT OF SCOPE: <name> — <one-line description>"
   - The aggregator will surface these in the report's "Gaps" section

The outer breakdown determines scope assignments — they are NON-OVERLAPPING by design.
Trust the breakdown's assignment and focus on producing high-quality, complete deliverables
within your scope.
```

#### Component 5: Outer Breakdown Prompt — Non-Overlapping Subtasks

In `role_setup.jinja2` (task_breakdown), add:

```jinja2
## ⚠️ Subtask Scope Discipline

When decomposing the role responsibilities into subtasks for parallel execution:

1. **Each subtask MUST have a NON-OVERLAPPING scope.** Two subtasks should never both claim
   responsibility for the same skill or tool. Overlap creates duplicate deliverables that
   waste worker effort and produce conflicting versions.

2. **Each subtask MUST have a clear, specific scope statement** (a phrase like
   "CI/CD pipeline monitoring" or "Stakeholder email distribution") that the worker can
   use to decide what's in scope vs out of scope.

3. **Use the `task_preamble` to dispatch:**
   - `skill_tool_creation` — for subtasks that produce new skills/tools (most subtasks)
   - `skill_tool_association` — for the single mandatory subtask that maps existing tools to the role

4. **Avoid "general" or "miscellaneous" subtasks** — they encourage workers to produce
   anything they find. Be specific.

Examples of GOOD non-overlapping subtask scopes:
- "CI/CD pipeline monitoring (Bamboo + GitHub Actions)"
- "Stakeholder communication via calendar and email"  
- "Capacity planning and program-level scheduling"
- "Risk and dependency tracking"

Examples of BAD overlapping subtask scopes:
- "Engineering tooling" + "DevOps automation" (overlap on CI/CD)
- "Reports" + "Analytics" (overlap on data visualization)
- "General automation" (too vague — workers will produce everything)
```

#### Component 6: Generic Mechanism — Conflict Resolution Modes

To keep this **generic** (not hardcoded to `role_setup`), expose conflict resolution behavior via yaml:

```yaml
# In role_setup.yaml or any BTA yaml that uses promote_worker_deliverables
promote_worker_deliverables: true
conflict_resolution_mode: "delegate_to_aggregator"  # SHIPPED MODES (initial impl):
  # - "last_writer_wins" (current behavior, preserved for backward compat)
  # - "delegate_to_aggregator" (NEW — pass conflict manifest to aggregator)
  # - "fail_fast" (raise on first conflict — useful for strict pipelines)
  # FUTURE MODES (documented design only — NOT in initial impl, build only when needed; YAGNI):
  # - "prefer_largest" (heuristic — pick largest file size; speculative)
  # - "prefer_first" (alphabetical worker order; speculative)
  # - "merge_via_aggregator_for_text_only" (skip binary; speculative)
```

This makes the BTA itself a **conflict-aware** orchestrator with pluggable resolution strategies. `role_setup` and any future BTA can opt in to delegation.

### Implementation Steps

| Step | Action | Files | Complexity |
|---|---|---|---|
| 4-1 | Add `_canonicalize_text`, `_sha256_of_file_canonical`, and `_detect_conflicts_and_promote` helpers | `breakdown_then_aggregate_inferencer.py` | Medium |
| 4-2 | Add `conflict_resolution_mode: str = "last_writer_wins"` attr to BTA | `breakdown_then_aggregate_inferencer.py` | Low |
| 4-3 | Wire conflict detection via `aggregator_prompt_builder` hook (NOT `_finalize_response`; that runs AFTER aggregator) — use `make_conflict_aware_prompt_builder` factory; the closure derives `children_dir`/`deliverables_dst` from `worker_output_paths[0]` | `breakdown_then_aggregate_inferencer.py` + `role_setup.yaml` | Medium |
| 4-4 | Verify aggregator (RovoDevCLI) accepts dict input from `_build_agg_input`; if not, render manifest to string in the closure | `breakdown_then_aggregate_inferencer.py` (RovoDevCLI input handling check) | Medium |
| 4-5 | Refactor `role_setup_report.jinja2` to be conflict resolver + report writer | `role_setup_report.jinja2` (implementation) | Medium |
| 4-6 | Add scope discipline section to `skill_tool_creation.jinja2` (worker prompt) | `skill_tool_creation.jinja2` | Low |
| 4-7 | Add scope discipline section to `role_setup.jinja2` (outer breakdown prompt) | `role_setup.jinja2` (task_breakdown) | Low |
| 4-8 | Update `role_setup.yaml` to set `conflict_resolution_mode: "delegate_to_aggregator"` | `role_setup.yaml` | Low |
| 4-9 | Add unit tests for `_detect_conflicts_and_promote` (matching, conflicting, missing, nested dirs, multi-worker) | `tests/.../test_conflict_detection.py` | Medium |
| 4-10 | E2E run with new mode — verify aggregator only resolves real conflicts, report explains decisions | (run only) | Medium |

### Risk & Rollback

**Risks:**
- Hash-based comparison only catches BYTE-IDENTICAL content. Minor whitespace differences (e.g., trailing newline) would be flagged as conflicts. Mitigate with optional content normalization (e.g., strip trailing whitespace per line before hashing).
- The aggregator must reliably write to absolute paths via `create_file` — current prompts assume relative paths.
- If the aggregator fails to resolve a conflict, the file is missing from final outputs (vs. last-writer-wins which always produces SOMETHING).

**Mitigation:** 
- The `conflict_resolution_mode` enum gives operators a knob to fall back to old behavior if new mode is unstable.
- Add a "best-effort fallback" — if aggregator fails on a conflict, copy the largest worker version (heuristic) as a safety net before erroring.
- Preserve worker output dirs (don't delete) so users can manually inspect/recover.

### Long-Term Vision

This pattern (BTA as conflict-aware orchestrator + LLM as targeted resolver) generalizes to:
- **Multi-author document collaboration** (parallel writers + aggregator merger)
- **Code generation** (parallel implementations of subsystems + aggregator integrator)
- **Research synthesis** (parallel researchers + aggregator who reconciles findings)
- **Any "fan-out, fan-in" pattern** where workers produce structured outputs

It's a foundational improvement to the BTA framework, not a one-off `role_setup` feature.

---

## Implementation Order

### Recommended sequence (smallest blast radius first → biggest)

| Step | Issue | Action | Files | Complexity | Risk |
|---|---|---|---|---|---|
| **Track A: Quick wins (Issue #4 prevention + Issue #3 fixes)** | | | | | |
| **A1** | #3D | Verify/fix association worker prompt's `create_file outputs/role_tool_association.json` instruction (note: missing JSON in `_runtime/20260419_140325` is EXPECTED — that run predates the association worker yaml; verify the prompt is correct anyway for future runs) | `skill_tool_association.jinja2` | Low | Low |
| **A2** | #4-6 | Add scope discipline section to `skill_tool_creation.jinja2` (worker prompt) — root cause prevention for conflicts | `skill_tool_creation.jinja2` | Low | Low |
| **A3** | #4-7 | Add scope discipline section to `role_setup.jinja2` (outer breakdown prompt) — non-overlapping subtasks | `role_setup.jinja2` (task_breakdown) | Medium | Low |
| **A0** | #4-0 (FOUNDATION) | **Build the generic helpers in PythonUtils** at `path_utils/path_listing.py`: `find_conflicting_and_agreed_files`, `safe_copy_per_file`, `canonicalize_text`, `hash_file_canonical`, `group_conflicts_by_parent` (Level 2 semantic grouping for related-file context), plus `FileCandidate` and `MultiRootDiff` NamedTuples. Pure functions, zero BTA dependencies. | `python_utils/path_utils/path_listing.py` | Medium | Low |
| **A0.1** | #4-0 (tests) | Comprehensive unit tests for ALL generic helpers: agreed/conflicting/unique categorization, normalization edge cases (CRLF, trailing whitespace, NFC unicode), binary-file bypass, large-file size threshold, `skip_existing` protection, fallback policies, AND `group_conflicts_by_parent` (depth=1 vs 2, single-segment paths, mixed-depth groups) | `python_utils/tests/path_utils/test_path_listing_diff.py` | Medium | Low |
| **A4** | #4-1, #4-2 | Add BTA-specific wrapper around the generic helper + `make_conflict_aware_prompt_builder` factory. The wrapper just constructs the worker root list (`children/worker_*/outputs/final_deliverables` falling back to `children/worker_*/outputs`) and calls `find_conflicting_and_agreed_files`. | `breakdown_then_aggregate_inferencer.py` | Low | Low |
| **A4.1** | #4 (Option 2 enabler) | Extend BTA's `aggregator_prompt_builder` hook signature to pass `bta` instance: `(bta, worker_results, original_query=, worker_output_paths=)`. Backward-compat: existing builders use `*args, **kwargs` or update signature. Required so `make_conflict_aware_prompt_builder` can clean-access `bta._workspace` and `bta._aggregator_inferencer.template_extra_feed` (Option 2). | `breakdown_then_aggregate_inferencer.py` | Low | Low |
| **A5** | #4-3, #4-4 | Wire `make_conflict_aware_prompt_builder` to the BTA via `aggregator_prompt_builder` hook. The factory returns a closure that calls the BTA wrapper, then mutates `bta._aggregator_inferencer.template_extra_feed` (Option 2) so the aggregator's template gets `{{ deliverables_promoted }}`, `{{ deliverables_with_conflicts }}`, `{{ deliverables_dst }}`, `{{ worker_summaries }}` as top-level vars. | `breakdown_then_aggregate_inferencer.py` + `role_setup.yaml` | Medium | Medium |
| **A5.1** | #4 (REPLACES old A5.1 — now SIMPLER) | Refactor `_finalize_response` to use `safe_copy_per_file(diff, deliverables_dst, skip_existing=True, conflict_fallback="largest")` INSTEAD of `shutil.copytree`. **No special-casing for `delegate_to_aggregator` mode needed** — `skip_existing=True` generically protects whatever the aggregator wrote (merged conflict resolutions). The `conflict_fallback="largest"` handles the aggregator-failed-to-write regression case (replaces the old A7.1 fallback). One unified, simpler, safer code path. | `breakdown_then_aggregate_inferencer.py` | Low | Low |
| **A6** | #4-5 | Refactor `role_setup_report.jinja2` to be conflict resolver + report writer. Template uses individual variables (`{{ deliverables_with_conflicts }}`, `{{ deliverables_promoted }}`, `{{ deliverables_dst }}`, `{{ worker_summaries }}`) — Option 2 injects these into `template_extra_feed` so they're directly available. | `role_setup_report.jinja2` (implementation) | Medium | Low |
| **A7** | #4-8 | Update `role_setup.yaml` to set `conflict_resolution_mode: "delegate_to_aggregator"` | `role_setup.yaml` | Low | Low |
| **A8** | #4-9 | Integration tests for BTA wrapper + `_finalize_response` end-to-end flow with `safe_copy_per_file`: assert no overwrites of pre-existing dest files, conflict_fallback="largest" copies largest candidate, deliverable promotion structure correct. (Generic helper tests are in A0.1; this is the BTA integration layer.) | `tests/.../test_conflict_aware_aggregator.py` | Medium | Low |
| ~~**Track B: Issue #2 — diagnostic-first**~~ ✅ COMPLETED — Issue #2 CLOSED, no fix needed | | | | | |
| ~~**B1**~~ | ~~#2~~ | ~~Add diagnostic log at semaphore CREATION~~ | ~~`workgraph.py`~~ | ~~Low~~ | ~~Low~~ |
| ~~**B1.5**~~ | ~~#2~~  | ~~Add diagnostic log at semaphore SELECTION~~ | ~~`workgraph.py`~~ | ~~Low~~ | ~~Low~~ |
| ~~**B2**~~ | ~~#2~~ | ~~Add diagnostic log at acquire/release~~ | ~~`workgraph.py`~~ | ~~Low~~ | ~~Low~~ |
| ~~**B3**~~ | ~~#2~~ | ~~Re-run small E2E~~ | ~~(run only)~~ | ~~Low~~ | ~~Low~~ |
| ~~**B4**~~ | ~~#2~~ | ~~Decision point: Inspect log output~~ | ~~(analysis)~~ | ~~—~~ | ~~—~~ |
| ~~**B5**~~ | ~~#2~~ | ~~Apply targeted fix~~ | ~~targeted~~ | ~~Low-Medium~~ | ~~Low-Medium~~ |
| ~~**B6**~~ | ~~#2~~ | ~~Re-run small E2E to verify~~ | ~~(run only)~~ | ~~Low~~ | ~~Low~~ |
| ~~**Track C: Unified executor (CANCELLED — Issue #2 closed, no bug found)**~~ | | | | | |
| ~~**C0**~~ | ~~#2~~ | ~~Gate condition~~ | ~~—~~ | ~~—~~ | ~~—~~ |
| ~~**C1**~~ | ~~#2 (conditional)~~ | ~~Add `group: Hashable` field to `Task`~~ | ~~`task.py`~~ | ~~Low~~ | ~~Low~~ |
| ~~**C2**~~ | ~~#2 (conditional)~~ | ~~Refactor `QueuedExecutorBase`~~ | ~~`queued_executor.py`~~ | ~~Medium~~ | ~~Medium~~ |
| ~~**C3**~~ | ~~#2 (conditional)~~ | ~~Update existing executor subclasses~~ | ~~`queued_executor.py`~~ | ~~Medium~~ | ~~Medium~~ |
| ~~**C4**~~ | ~~#2 (conditional)~~ | ~~Create `AsyncQueuedExecutor` subclass~~ | ~~`queued_executor.py`~~ | ~~High~~ | ~~Medium~~ |
| ~~**C5**~~ | ~~#2 (conditional)~~ | ~~Comprehensive tests~~ | ~~`tests/mp_utils/...`~~ | ~~High~~ | ~~Low~~ |
| ~~**C6**~~ | ~~#2 (conditional)~~ | ~~Run all PythonUtils tests~~ | ~~(test run)~~ | ~~Low~~ | ~~Medium~~ |
| ~~**C7**~~ | ~~#2 (conditional)~~ | ~~Refactor `WorkGraph._arun()` and `WorkGraphNode.arun()` to use `AsyncQueuedExecutor`~~ | ~~`workgraph.py`~~ | ~~High~~ | ~~High~~ |
| ~~**C8**~~ | ~~#2 (conditional)~~ | ~~Run all AgentFoundation BTA tests~~ | ~~(test run)~~ | ~~Medium~~ | ~~High~~ |
| **13** | All | **Re-run small E2E** (`--max-facets 4`) — verify (a) `group_max_concurrency` is now honored, (b) Track A fixes work | (run only) | Medium | Medium |
| **14** | #1 (Phase A) | Update `test_create_role_bta_yaml_equivalence.py` to load src/ yaml | `test/.../test_create_role_bta_yaml_equivalence.py` | Low | Low |
| **15** | #1 (Phase A) | Refactor `test_create_role_through_yaml.py` to call `execute()` directly | `test/.../test_create_role_through_yaml.py` | Medium | Low |
| **16** | #1 (Phase A) | Run E2E refactored test, verify outputs match | (run only) | Medium | Low |
| **17** | #1 (Phase A) | Delete `test/.../yaml_configs/create_role_bta.yaml` | (file deletion) | Low | Low |
| **18** | #1 (Phase B) | Copy yamls from `test/.../yaml_configs/` → `src/.../role_setup/` | `src/.../role_setup/role_setup.yaml`, `role_setup_skill_tool_creation.yaml` | Low | Low |
| **19** | #1 (Phase B) | Refactor `executor.py:execute()` to be yaml-driven (mirroring create_role pattern) | `src/.../role_setup/executor.py` | High | High |
| **20** | #1 (Phase B) | Refactor `test_role_setup_through_yaml.py` to call `execute()` directly | `test/.../test_role_setup_through_yaml.py` | Medium | Low |
| **21** | #1 (Phase B) | Update equivalence + inner tests to load src/ yaml | various test files | Low | Low |
| **22** | #1 (Phase B) | Delete `test/.../role_setup/yaml_configs/` | (dir deletion) | Low | Low |
| **23** | All | **Final full E2E run** — verify all fixes integrated, no regressions | (run only) | High | Medium |

### Why this order?

**Phase 1: Quick wins on Issue #3 (Steps 1-3)** — Apply the conflict logging + prompt fixes first. Zero code risk; pure observability + LLM behavior improvements.

~~**Phase 2 (Track B): Diagnostic-first for Issue #2**~~ — ✅ **COMPLETED & CLOSED.** Diagnostic logs were added to `workgraph.py`. Run `_runtime/20260419_183553` confirmed semaphore IS working correctly — worker_3 blocked for 4m46s as expected. No fix needed.

~~**Phase 3 (Track C, CONDITIONAL): Integrate executor into BTA**~~ — ✅ **CANCELLED.** Issue #2 was not a bug; Track C design is dead code.

**Phase 4: Validate with E2E (Step 13)** — ⏳ **IN PROGRESS** — Run `_runtime/20260419_184628` is at 34+ min, inner BTA aggregators streaming. Concurrency confirmed working (worker_3 blocked 4m46s, then acquired correctly). Expected completion: ~10-20 more min.

**Phase 5: Test alignment (Steps 14-22)** — `/create_role` first (Phase A — proves pattern), then `/role_setup` (Phase B — applies same pattern + executor refactor). Both phases now use src/ yaml + `execute()` invocation.

**Phase 6: Final integration gate (Step 23)** — Full `--max-facets 4` end-to-end with all changes. Compare output structure to `_runtime/20260419_140325` reference. No regressions.

### Estimated Effort (Updated 2026-04-19)

> **Note:** Issue #2 (Track B + C) is CLOSED — those steps are cancelled. Effective remaining work is Track A (A0-A8) + Phase A + Phase B.

| Phase | Steps | Effort |
|---|---|---|
| Phase 1 (quick wins) | 1-3 | 1-2 hours |
| Phase 2 (executor build + tests) | 4-9 | 1-2 days |
| Phase 3 (BTA integration) | 10-12 | 0.5-1 day |
| Phase 4 (validation) | 13 | 30-60 min E2E run |
| Phase 5 (test alignment) | 14-22 | 1 day |
| Phase 6 (final E2E) | 23 | 30-60 min |
| **Total** | **23 steps** | **3-5 days** |

---

## Verification Plan

### After Fix #2 (group_max_concurrency) — ✅ COMPLETED

```bash
# Run small E2E with --max-facets 4
# Check inner stream timestamps — should show 2 workers start, then after ~10 min the 3rd starts
WS=$(ls -dt _runtime/*/ | head -1)
for outer in worker_0 worker_1 worker_2 worker_3; do
  earliest=$(find "$WS/children/$outer/children/" -name "stream_*.txt" -exec ls -lT {} \; | awk '{print $6,$7,$8,$9}' | sort | head -1)
  echo "  $outer: $earliest"
done
# Expected: pairs of timestamps separated by ~10+ min, NOT all within 90 sec
```

### After Fix #3A (conflict detection)

Re-run E2E and check log for `WARNING ... deliverables conflict`. Should report which workers produced overlapping files.

### After Fix #3C (distinct subtasks)

Compare each worker's `final_deliverables/` count — should be DIFFERENT (each worker produces unique files), not all producing the same overlapping set.

### After Fix #1 (real command test)

Verify the refactored `test_role_setup_through_yaml.py` (now calling `execute()` directly per Phase B Step B4) produces equivalent output to the prior yaml-driven test, but additionally exercises:
- Auth setup that `executor.execute()` does
- Workspace creation that `executor.execute()` does
- Any post-processing that `executor.execute()` does

---

## Open Questions

1. ~~Does `WorkGraph.__attrs_post_init__()` actually do anything important?~~ **ANSWERED:** It only sets `parent_debuggable` on start_nodes — has no concurrency state. Verified empirically. Question removed.
2. ~~Does `executor.execute()` for `role_setup` actually wrap the BTA call, or does it do something else entirely?~~ **ANSWERED:** Verified at `executor.py:1167` — `execute()` calls `build_role_setup_inferencer()` (line 651) which programmatically constructs the BTA. It IS a BTA wrapper, just programmatic (not yaml-driven). Phase B refactors this to load `role_setup.yaml` instead.
3. For Fix 3C: how to enforce subtask distinctness without overly constraining the LLM's planning?
4. ~~Is the missing `role_tool_association.json` due to prompt ambiguity OR due to the association worker not actually running?~~ **ANSWERED:** The reference run `_runtime/20260419_140325` predates the `skill_tool_association` worker factory addition to the yaml. No association worker ever ran in that run. Missing JSON is expected, not a bug. (The prompt should still be verified for future runs — see Step A1.)

---

## Files to Create/Modify

### Modify
- `/Users/tchen7/MyProjects/CoreProjects/AgentFoundation/src/agent_foundation/common/inferencers/agentic_inferencers/flow_inferencers/breakdown_then_aggregate_inferencer.py`
  - **Add diagnostic logs only** (do NOT modify `__attrs_post_init__`); see Issue #2 "Disproven Hypotheses" — the MRO fix would be a no-op
  - `_finalize_response` (around line 1097): add conflict detection logging
- `/Users/tchen7/MyProjects/CoreProjects/PythonUtils/src/python_utils/common_objects/workflow/workgraph.py`
  - Line 1798: add diagnostic log
- `/Users/tchen7/MyProjects/CoreProjects/OpenTeam/src/openteam/server/resources/prompt_templates/task_breakdown/main/_variables/task_preamble/role_setup.jinja2`
  - Add explicit instruction for distinct subtask deliverables
- `/Users/tchen7/MyProjects/CoreProjects/OpenTeam/src/openteam/server/resources/prompt_templates/implementation/main/_variables/task_instructions/skill_tool_association.jinja2`
  - Verify `create_file outputs/role_tool_association.json` instruction is unambiguous

### Create
- (Refactor existing) `/Users/tchen7/MyProjects/CoreProjects/OpenTeam/test/openteam/resources/tools/role_setup/test_role_setup_through_yaml.py` to call `execute()` directly (Phase B Step B4) — do NOT create a separate `test_role_setup_real_command.py`; the refactored test IS the real-command test
- `/Users/tchen7/MyProjects/CoreProjects/AgentFoundation/tests/test_bta_group_max_concurrency.py` (or similar location)
