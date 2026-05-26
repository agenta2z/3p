# Plan: Outer BTA YAML Config (`role_setup.yaml`) + File Composition Support

**Status:** Draft  
**Date:** 2026-04-19  
**Goal:** Create `role_setup.yaml` as the full outer BTA config that composes with
`inner_bta_skill_tool_creation.yaml` via a file-reference mechanism, making the
entire nested BTA declaratively configurable — no Python executor needed for
standard runs.

---

## 1. Context & Intent

The current `role_setup` tool is fully wired in Python (`executor.py` +
`test_role_setup.py`). The inner BTA was recently converted to a standalone yaml
(`inner_bta_skill_tool_creation.yaml`) and works correctly end-to-end.

The intent is to:
1. Create `role_setup.yaml` — the outer BTA config (breakdown → N inner BTAs → outer aggregation)
2. Support **file composition** in the yaml config system so that `role_setup.yaml`
   can reference `inner_bta_skill_tool_creation.yaml` by path instead of inlining
   all inner BTA config
3. Create `test_role_setup_through_yaml.py` — the yaml-driven E2E test script that
   mirrors `test_role_setup_inner_bta_through_yaml.py` but for the full outer BTA

---

## 2. Current Architecture (Python path)

```
role_doc.md
    │
    ▼
Outer BTA (build_run_subtask in executor.py)
    ├── Breakdown:  RovoDevCLI  (task_breakdown/main, preamble=role_setup)
    │               → subtasks[] with task_preamble per subtask
    │
    ├── Worker 0:   Inner BTA (_build_inner_bta, subtask 0)
    │               ├── Inner Breakdown (RovoDevCLI)
    │               ├── Workers (RovoChat research + RovoDevCLI investigation)
    │               └── Inner Aggregator (RovoDevCLI → skills/, tools/)
    │
    ├── Worker 1:   Inner BTA (subtask 1) — same structure
    │   ...
    ├── Worker N:   Inner BTA (subtask N)
    │
    └── Outer Aggregator: RovoDevCLI
                    → role_setup_report.md (synthesis of all inner specs)
```

**Key parameters passed to `_build_inner_bta`:**
- `sub_query` — subtask description (from outer breakdown)
- `index` — worker position (0-based)
- `role_doc_path` — path to role_document.md (passed to inner workers)
- `available_tools_text` — list of existing skills/tools (injected into inner prompts)
- `max_inner_facets` — max inner research facets (default 5)
- `aggregator_type` — "rovodev" (RovoDevCLI)
- `inferencer_logger` — "auto"

---

## 3. What Needs to be Built

### 3a. File Composition + Partial Factory Support in `load_config` (PythonUtils)

**Problem 1:** The yaml config system does not support referencing another yaml
file from within a yaml config. `worker_factory` entries must be fully inlined.

**Problem 2 (Critical — missed in initial plan):** The BTA `worker_factory` protocol
requires each factory entry to be either:
- A `Callable(sub_query, index) -> Inferencer` — called with sub_query + index
- A `functools.partial` — called with NO args → returns fresh Inferencer instance

When `_from_file` loads `inner_bta_skill_tool_creation.yaml` and `instantiate()`
fully constructs a `BreakdownThenAggregateInferencer`, the result is a fully
instantiated object — NOT a callable factory. The outer BTA then tries to call
`worker(sub_query=..., index=...)` on it → crash (BTA.__init__ doesn't accept those args).

**Solution: `_from_file` key only — `_partial` is NOT needed**

#### Why `_partial` is not needed — `_walk()` auto-partial mechanism

`_instantiate.py` lines 292-309 already handle this:

```python
# Auto-partial for *_factory fields: inject _partial_: true into child
# configs so Hydra produces functools.partial callables.
# Single factory: worker_factory: {_target_: RovoChat, ...}
val["_partial_"] = True
# Dict of factories: worker_factory: {type1: {_target_: ...}, ...}
for v in val.values():
    v["_partial_"] = True
```

`_walk()` automatically injects `_partial_: True` (Hydra's partial key) into ANY
field ending with `_factory`. So when `role_setup.yaml` defines:

```yaml
worker_factory:
  skill_tool_creation:
    _target_: BTA
    ...inner BTA config...
```

`_walk()` injects `_partial_: True` → Hydra produces `functools.partial(BreakdownThenAggregateInferencer, ...)`.
The outer BTA calls `factory()` (no args) → fresh inner BTA instance each time. ✅

This is proven by `create_role_bta.yaml` (homogeneous single factory) and
`inner_bta_skill_tool_creation.yaml` (heterogeneous dict of factories) — both use
only `_target_` and rely on auto-partial injection. No `_partial: true` needed.

**Per-worker workspace:** `_configure_child_workspace()` overwrites `_workspace`
AFTER `factory()` creates the instance — each inner BTA gets a unique workspace. ✅

#### `_from_file: "path/to/other.yaml"`
Still needed for file composition — to avoid inlining 80+ lines of inner BTA config
into `role_setup.yaml`. When `_walk()` encounters a node with `_from_file`, it:
1. Resolves the path relative to the current yaml's directory
2. Loads the referenced yaml via `OmegaConf.load()`
3. Deep-merges any sibling keys as overrides onto the loaded config
4. Replaces the node with the merged config dict (which still has `_target_: BTA`)
5. `_walk()` then applies auto-partial to it normally (since it's under `worker_factory`)

**Example usage in `role_setup.yaml`:**
```yaml
worker_factory:
  skill_tool_creation:
    _from_file: "inner_bta_skill_tool_creation.yaml"   # ← load inner BTA config
    # Override on top of referenced file:
    workspace:
      _target_: InferencerWorkspace
      use_final_deliverables_folder: true
  __default__: skill_tool_creation
```

`_walk()` sees `worker_factory.skill_tool_creation` has `_target_: BTA` (from the
loaded file) → injects `_partial_: True` → Hydra produces
`functools.partial(BreakdownThenAggregateInferencer, ...)`. ✅

**Implementation in `_instantiate.py` (integrated best of both plans):**
```python
_FROM_FILE_KEY = "_from_file"

def _deep_merge(base: dict, overrides: dict) -> dict:
    """Recursively merge overrides into base dict."""
    result = dict(base)
    for k, v in overrides.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result

def _resolve_from_file(node, current_yaml_dir: Path):
    """Resolve _from_file references recursively before instantiation.

    Handles dicts, lists, and scalars. Uses .resolve() for robust path handling.
    Merges sibling keys as deep overrides onto the referenced file's config.
    Recurses into the merged result so nested _from_file refs are resolved too.
    """
    if isinstance(node, list):
        return [_resolve_from_file(item, current_yaml_dir) for item in node]
    if not isinstance(node, dict):
        return node
    if _FROM_FILE_KEY in node:
        ref_path = (current_yaml_dir / node[_FROM_FILE_KEY]).resolve()
        if not ref_path.exists():
            raise FileNotFoundError(f"_from_file: referenced yaml not found: {ref_path}")
        ref_cfg = OmegaConf.to_container(OmegaConf.load(str(ref_path)), resolve=False)
        # Deep-merge sibling keys as overrides onto the referenced config
        overrides = {k: v for k, v in node.items() if k != _FROM_FILE_KEY}
        merged = _deep_merge(ref_cfg, overrides)
        # Recurse: resolve any _from_file refs in the merged result
        return _resolve_from_file(merged, ref_path.parent)
    return {k: _resolve_from_file(v, current_yaml_dir) for k, v in node.items()}
```

In `load_config()`, inject after `OmegaConf.load()`, before OmegaConf resolution:
```python
cfg = OmegaConf.load(path)
# Resolve _from_file references before OmegaConf resolution
container = OmegaConf.to_container(cfg, resolve=False)  # resolve=False is critical
container = _resolve_from_file(container, Path(path).resolve().parent)
cfg = OmegaConf.create(container)
# ... rest of existing load_config() logic
```

**Files to modify:**
- `PythonUtils/src/python_utils/config_utils/_instantiate.py`
  - Add `_resolve_from_file()` + `_deep_merge()` functions
  - Call `_resolve_from_file()` in `load_config()` after `OmegaConf.load()`

**Tests to add:**
- `PythonUtils/tests/config_utils/test_from_file_composition.py`
  - Test `_from_file` resolves relative paths correctly (including `../`)
  - Test sibling override keys are deep-merged on top of referenced file
  - Test nested `_from_file` (A references B which references C)
  - Test list nodes are recursed into correctly
  - Test missing file raises `FileNotFoundError` with clear message
  - Test `_from_file` node under `worker_factory` gets auto-partialed by `_walk()`

---

### 3b. `role_setup.yaml` — Outer BTA Config

**File:** `test/openteam/resources/tools/role_setup/yaml_configs/role_setup.yaml`

```yaml
# Outer BTA for role_setup: breakdown role_document → N inner BTAs → synthesis
_target_: BTA
_logger: auto
_debug_mode: true
_template_manager:
  _target_: TemplateManager
  templates: prompt_templates
  active_template_type: main
  predefined_variables: true
  default_template_key: initial
  enable_templated_feed: true
  # ⚠️ _-prefix keys auto-inject into all children (breakdown, workers, aggregator)
  # Monitor for conflicts with inner BTA's own template_manager

name: outer_bta

workspace:
  _target_: InferencerWorkspace
  # root is set at runtime via load_config overrides: {"workspace.root": str(workspace_root)}
  use_final_deliverables_folder: false   # Outer report goes to outputs/ directly

# --- Outer Breakdown ---
# Decomposes role_document.md into skill/tool creation subtasks
# Uses RovoDevCLI for local file access to role_document.md
breakdown_inferencer:
  _target_: RovoDevCLI
  yolo: true
  debug_mode: true
  template_root_space: task_breakdown
  template_variables:
    task_preamble: role_setup

breakdown_format: json_subtasks
max_breakdown: 8   # Max outer subtasks (skills/tools to create); matches programmatic default

# --- Outer Workers ---
# Each outer worker IS a full inner BTA (composed via _from_file)
# _walk() auto-injects _partial_: True since field ends with _factory
# → produces functools.partial(BTA, ...) → factory() gives fresh inner BTA per subtask
worker_factory:
  skill_tool_creation:
    _from_file: "inner_bta_skill_tool_creation.yaml"
    # Override: inner deliverables go to final_deliverables/
    workspace:
      _target_: InferencerWorkspace
      use_final_deliverables_folder: true
    # workspace.root set per-worker by _configure_child_workspace() after factory()
  __default__: skill_tool_creation

# --- Outer Aggregator ---
# Synthesizes all N inner BTA specs into role_setup_report.md
# Uses RovoDevCLI: can read inner worker output files via file paths (has_local_access=True)
aggregator_inferencer:
  _target_: RovoDevCLI
  yolo: true
  debug_mode: true
  template_root_space: implementation
  template_variables:
    task_instructions: role_setup_report
    task_preamble: ""

output_path: "role_setup_report.md"
```

**Key design decisions:**
1. **Outer breakdown: `RovoDevCLI`** — needs local file access to read `role_document.md` for context
2. **Outer aggregator: `RovoDevCLI`** — can read inner worker output files via file paths in InferenceInput (`has_local_access=True`), better synthesis quality
3. `_from_file: "inner_bta_skill_tool_creation.yaml"` — file composition without inlining 80+ lines
4. `use_final_deliverables_folder: false` at outer level → report goes to `outputs/`
5. `use_final_deliverables_folder: true` override in worker_factory → inner `skills/`, `tools/` go to `final_deliverables/`
6. `__default__: skill_tool_creation` — all outer subtasks use same inner BTA; future-proof for heterogeneous types
7. `_template_manager` with `_-prefix` auto-injection — ⚠️ needs monitoring for inner BTA conflicts

**Note:** `role_setup_report.jinja2` already exists (confirmed at `executor.py` line 689) — no need to create.

---

### 3c. New Prompt Template: `role_setup_report.jinja2`

**File:**
`src/openteam/server/resources/prompt_templates/implementation/main/_variables/task_instructions/role_setup_report.jinja2`

This replaces the Python-built `outer_agg_prompt_builder`. It receives:
- `{{ input }}` — concatenated inner BTA specs (file paths or inline text)
- Task: synthesize into a final role setup report

Content:
```
You are synthesizing {{ n_specs }} skill/tool specifications created for this role into
a comprehensive Role Setup Report.

## Your Task

Read each specification below and produce a unified implementation summary covering:
1. All skills created (name, purpose, key capabilities)
2. All tools created (name, purpose, API/auth requirements)
3. Integration guide — how skills and tools work together
4. Deployment checklist

## Specifications to Synthesize

{{ input }}

## Output

Write the Role Setup Report to `outputs/role_setup_report.md`. This is a summary
document (not a deliverable), so write it to `artifacts/role_setup_report.md`.
```

---

### 3d. `test_role_setup_through_yaml.py` — Outer BTA yaml-driven test script

**File:** `test/openteam/resources/tools/role_setup/test_role_setup_through_yaml.py`

Mirrors `test_role_setup_inner_bta_through_yaml.py` but for the full outer BTA:

```python
@click.command()
@click.option("-r", "--role-document", required=True)
@click.option("--yaml-config", default="yaml_configs/role_setup.yaml")
@click.option("--max-facets", default=None, type=int)
@click.option("--max-inner-facets", default=None, type=int)
@click.option("--log-level", default="INFO")
# ... auth kwargs
def main(role_document, yaml_config, max_facets, max_inner_facets, log_level, ...):
    workspace = _make_workspace(...)
    overrides = {
        "workspace.root": str(workspace),
    }
    if max_facets:
        overrides["max_breakdown"] = max_facets
    # max_inner_facets needs to patch the nested worker_factory config:
    if max_inner_facets:
        overrides["worker_factory.skill_tool_creation.max_breakdown"] = max_inner_facets

    cfg = load_config(yaml_config, overrides=overrides)
    bta = instantiate(cfg)

    # Run full outer BTA
    result = asyncio.run(bta.ainfer(inference_input=role_doc_text))
    ...
```

---

### 3e. Equivalence Test

**File:** `test/openteam/resources/tools/role_setup/test_outer_bta_yaml_equivalence.py`

Verifies:
- `bta._target_` == `BreakdownThenAggregateInferencer`
- `bta.breakdown_inferencer` is `RovoDevCliInferencer`
- `bta.worker_factory["skill_tool_creation"]` is `BreakdownThenAggregateInferencer` (inner BTA!)
- Inner BTA's `aggregator_inferencer` is `RovoDevCliInferencer`
- Inner BTA's `_workspace.use_final_deliverables_folder == True`
- `bta.max_breakdown == 8`

---

## 4. Implementation Order

| Step | What | File(s) | Complexity |
|------|------|---------|------------|
| 1 | Add `_from_file` to `load_config` | `PythonUtils/_instantiate.py` | Medium |
| 2 | Add `_from_file` unit tests | `PythonUtils/tests/` | Low |
| 3 | Create `role_setup.yaml` | `yaml_configs/role_setup.yaml` | Low |
| 4 | Create `role_setup_report.jinja2` | `prompt_templates/implementation/...` | Low |
| 5 | Create `test_role_setup_through_yaml.py` | `test/.../role_setup/` | Medium |
| 6 | Create equivalence test | `test/.../role_setup/` | Low |
| 7 | E2E test run | Manual | — |

---

## 5. Key Design Decisions & Tradeoffs

### Why `_from_file` instead of OmegaConf defaults?

OmegaConf's `defaults:` list (Hydra-style) requires a search path and config groups
— too heavy for our single-file `load_config` pattern. `_from_file` is simpler:
load one yaml, reference another by relative path, merge with sibling overrides.
This matches the existing `${path:...}` resolver pattern.

### Why is `__default__` sufficient for outer worker routing?

The outer breakdown assigns `task_preamble` per subtask (e.g., `skill_tool_creation`,
`skill_tool_creation_advanced`). In the current design, all subtasks use the same
inner BTA config — just different `sub_query` inputs. If future subtask types need
different inner BTA configs, add them as named entries in `worker_factory` with
different `_from_file` references.

### Dot-notation overrides for nested `_from_file` configs

When `test_role_setup_through_yaml.py` passes:
```python
overrides={"worker_factory.skill_tool_creation.max_breakdown": 3}
```
The `_from_file` resolution happens BEFORE OmegaConf merge, so the override
correctly patches the resolved inner config. This must be guaranteed in the
`_from_file` implementation order (resolve first, then merge overrides).

### Outer aggregator prompt building

The Python path uses a dynamic `outer_agg_prompt_builder` that constructs prompt
text from worker results (file paths or inline text). For the yaml path, the
aggregator prompt is built by the BTA's standard `aggregator_prompt_builder`
mechanism. This works when `has_local_access=True` (RovoDevCLI aggregator can
read worker output files directly via file paths in InferenceInput).

---

## 6. Files Summary

### New files
| File | Purpose |
|------|---------|
| `PythonUtils/src/.../config_utils/_instantiate.py` | Add `_from_file` support |
| `test/.../role_setup/yaml_configs/role_setup.yaml` | Outer BTA config |
| `src/.../prompt_templates/.../role_setup_report.jinja2` | Outer aggregator template |
| `test/.../role_setup/test_role_setup_through_yaml.py` | E2E yaml-driven test |
| `test/.../role_setup/test_outer_bta_yaml_equivalence.py` | Structural tests |

### Modified files
| File | Change |
|------|--------|
| `PythonUtils/src/.../config_utils/_instantiate.py` | Add `_resolve_from_file()` |

---

## 7. Open Questions

1. **Deep merge vs shallow merge for `_from_file` overrides?** — Should sibling
   override keys do a deep merge into the referenced config, or a shallow
   `dict.update()`? Deep merge is safer for nested configs.

2. **Relative path base for `_from_file`?** — Should it be relative to:
   (a) the yaml file containing the `_from_file` reference, or
   (b) the cwd at load time? → **Recommend (a)** for portability.

3. **Should `_from_file` support URL/absolute paths?** — Not needed now; add later.

4. **Outer aggregator prompt template vs dynamic builder?** — The Python path
   uses a rich dynamic prompt that injects role_doc excerpt and available_tools_text.
   The yaml path needs this injected differently (via `inference_input` preprocessing).
   May need a new BTA feature: `aggregator_input_preprocessor` hook.
