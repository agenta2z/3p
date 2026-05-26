# Plan: Generic YAML-Driven BTA Pipeline + role_setup Test

## Context

The `role_setup` tool builds a nested BTA pipeline with ~200 lines of hardcoded Python. The goal is to enable **any** complex inferencer pipeline to be defined via YAML and instantiated with `load_config()` + `instantiate()`.

**User requirement**: No custom YAML parsing. Worker configs in YAML look **identical** to regular inferencer configs.

---

## Existing Infrastructure

- `load_config()` + `instantiate()` — generic YAML → object pipeline (PythonUtils)
- `load_inferencer('conversational')` — convenience loader (AgentFoundation)
- `_filter_attrs_keys()` — strips invalid YAML keys for attrs classes during `_walk()`
- Existing YAML configs: `claude_api.yaml`, `conversational.yaml`, `dual.yaml`

---

## Core Design: Auto-Partial Factory Fields

### Convention

Fields named `*_factory` on attrs classes are automatically treated as factories by config_utils. Child configs with `_target_:` get `_partial_: true` auto-injected, producing `functools.partial` callables that create fresh instances on each call.

### YAML

```yaml
_target_: BTA

# =====================================================================
# Shared config (auto-injected into all children via _-prefix convention)
# =====================================================================
_template_manager:
  _target_: TemplateManager
  templates: prompt_templates  # resolved via PROMPT_TEMPLATES_ROOT env var
  active_template_type: main
  predefined_variables: true
  default_template_key: initial
  enable_templated_feed: true

# =====================================================================
# Pipeline: inferencers
# =====================================================================

# --- Breakdown ---
breakdown_inferencer:
  _target_: RovoDevCLI
  yolo: true
  debug_mode: true
  template_root_space: task_breakdown
  template_variables:
    task_preamble: skill_tool_creation

# --- Workers (auto-partialed: each call creates a fresh instance) ---
worker_factory:
  skill_tool_creation_research:
    _target_: RovoChat
    auto_continue: true
    max_continuations: 5
    template_root_space: deep_research
    template_variables:
      task_preamble: skill_tool_creation_research

  skill_tool_creation_investigation:
    _target_: RovoDevCLI
    yolo: true
    debug_mode: true
    template_root_space: deep_research
    template_variables:
      task_preamble: skill_tool_creation_investigation

  __default__: skill_tool_creation_research

# --- Aggregator ---
aggregator_inferencer:
  _target_: RovoChat
  auto_continue: true
  max_continuations: 5
  template_root_space: implementation
  output_path: "skill_tool_spec.md"
  template_variables:
    task_instructions: skill_tool_creation
    task_preamble: skill_tool_creation

# =====================================================================
# Pipeline: settings
# =====================================================================
breakdown_format: json_subtasks
worker_query_fields:
  - description
  - todos
max_breakdown: 5
task_type_arg_name: task_preamble
expand_todos_to_workers: true
debug_mode: true
group_max_concurrency:
  skill_tool_creation_research: 3
  skill_tool_creation_investigation: 2
```

**How `_template_manager` auto-injection works:**
1. `_walk()` encounters BTA dict → collects `_template_manager` as injectable (`template_manager` key)
2. Recurses into `breakdown_inferencer` → RovoDevCLI has `template_manager` param, not explicitly set → auto-injected
3. Recurses into `worker_factory` → propagates injectables → each worker child gets `template_manager` auto-injected
4. Explicit values always win — if a child sets its own `template_manager`, auto-injection is skipped
5. Both approaches work together: `_template_manager` for auto-injection, `${_tm}` for explicit references

**What's in YAML vs runtime:**

| Component | In YAML ✓ | Runtime only |
|-----------|-----------|-------------|
| TemplateManager (path + config) | ✓ via `_template_manager` auto-injection | — |
| template_key, template_root_space | ✓ plain strings | — |
| template_extra_feed (rendered preambles) | — | Set post-instantiation (Jinja2 needs role_name, role_doc_path) |
| Auth (cloud_id, uct_token) | — | Via `load_config` overrides |
| workspace_root, cache_folder | — | Via `load_config` overrides |

Worker configs (`skill_tool_creation_research`, `skill_tool_creation_investigation`) are **identical** to regular inferencer configs. No metadata, no wrappers.

### How It Works

**Step 1 — config_utils auto-partial** (`_filter_attrs_keys`):

```python
# After existing filtering logic:
for a in attr.fields(cls):
    if a.name.endswith('_factory') and a.name in node:
        val = node[a.name]
        if not isinstance(val, dict):
            continue
        if "_target_" in val:
            # Single factory (e.g., worker_factory: {_target_: RovoChat, ...})
            # → produces functools.partial(RovoChat, ...)
            val["_partial_"] = True
        else:
            # Dict of factories (e.g., worker_factory: {research: {_target_: ...}, ...})
            # → produces {research: functools.partial(...), ...}
            for k, v in val.items():
                if k.startswith("_"):
                    continue  # skip __default__
                if isinstance(v, dict) and "_target_" in v:
                    v["_partial_"] = True
```

This handles both:
- **Single factory**: `worker_factory: {_target_: RovoChat}` → `functools.partial(RovoChat, ...)`
- **Dict of factories**: `worker_factory: {research: {_target_: RovoChat}, ...}` → `{research: functools.partial(...), ...}`

Runs **before** recursion in `_walk()`, so Hydra sees `_partial_: true` when processing children.

**Step 2 — After instantiate()**:

```python
bta.worker_factory = {
    "skill_tool_creation_research": functools.partial(RovoChatInferencer, auto_continue=True, ...),
    "skill_tool_creation_investigation": functools.partial(RovoDevCliInferencer, yolo=True, ...),
    "__default__": "skill_tool_creation_research",  # string ref
}
```

**Step 3 — BTA creates workers by calling partials**:

```python
# BTA._build_diamond_graph:
if isinstance(factory_entry, functools.partial):
    worker = factory_entry()  # fresh instance, no sub_query/index args
elif isinstance(factory_entry, dict) and "factory" in factory_entry:
    worker = factory_entry["factory"](sub_query=query_str, index=i)  # legacy format
elif callable(factory_entry):
    worker = factory_entry(sub_query=query_str, index=i)  # legacy callable
```

**Step 4 — __default__ string resolution**:
```python
if isinstance(factory_entry, str):
    factory_entry = self.worker_factory.get(factory_entry)
```

---

## Test Script

```python
# 1. Overrides (auth + workspace — the only runtime values)
overrides = {
    "worker_factory.skill_tool_creation_research.cloud_id": cloud_id,
    "worker_factory.skill_tool_creation_research.uct_token": uct_token,
    "aggregator_inferencer.cloud_id": cloud_id,
    "aggregator_inferencer.uct_token": uct_token,
    "workspace_root": str(workspace),
    "breakdown_inferencer.cache_folder": streaming_cache_dir,
}

# 2. Load + instantiate
#    - config_utils auto-injects _template_manager into all children
#    - config_utils auto-partials worker_factory children
#    - TemplateManager path resolved via ${path:...}
cfg = load_config(yaml_config, overrides=overrides)
bta = instantiate(cfg)

# 3. Minimal runtime injection: role_name + role_doc_path
#    These are Jinja2 vars inside preamble template files ({{ role_name }}, etc.)
#    Resolved by TemplateManager's enable_templated_feed: true at render time.
#    Must be in the feed for each inferencer that uses preambles.
#
#    Injected via overrides (baked into partials for workers):
import functools
role_context = {"role_name": role_name, "role_doc_path": str(Path(role_document).resolve()),
                "available_tools_skills": format_available_tools_and_skills(...)}

bta.breakdown_inferencer.template_extra_feed.update(role_context)

for key, factory in bta.worker_factory.items():
    if isinstance(factory, functools.partial):
        existing_feed = factory.keywords.get("template_extra_feed", {})
        bta.worker_factory[key] = functools.partial(
            factory.func,
            **{**factory.keywords, "template_extra_feed": {**existing_feed, **role_context}}
        )

# 4. Run
subtask_desc = extract_subtask(breakdown_file, subtask_index)
result = _run_async_with_forced_cleanup(bta.ainfer(subtask_desc))
```

**What comes from where:**
- **YAML**: TemplateManager (auto-injected, with `enable_templated_feed: true`), template_key (via `default_template_key`), template_root_space, template_variables (variant selectors for preambles + instructions), output_path, all inferencer configs, BTA structure
- **Overrides**: auth credentials, workspace_root, cache_folder
- **Runtime injection**: `role_name`, `role_doc_path`, `available_tools_skills` via `template_extra_feed` — these are Jinja2 vars inside preamble template files, resolved at render time by `enable_templated_feed: true`

---

## Registration Requirements

| Class | Current State | Action |
|-------|--------------|--------|
| `RovoDevCliInferencer` | `RovoDevCLI` ✓ | None |
| `RovoChatInferencer` | **Not registered** | Add `RovoChat` alias |
| `BreakdownThenAggregateInferencer` | **Not registered** | Add `BTA` alias |
| `TemplateManager` | **Not registered** | Add `TemplateManager` alias |
| ~~`InnerBreakdownParser`~~ | Not needed | BTA built-in `breakdown_format: json_subtasks` |
| ~~`TemplateAggregatorPromptBuilder`~~ | Not needed | Aggregator uses template_manager directly |

---

## Files to Create/Modify

### Step 1: config_utils — two enhancements
**File**: `CoreProjects/PythonUtils/src/python_utils/config_utils/_instantiate.py`

**Enhancement A: Auto-partial for `*_factory` fields** (~10 lines in `_filter_attrs_keys`):
Detect attrs fields ending in `_factory`, auto-inject `_partial_: true` into child dicts with `_target_`.

**Enhancement B: Auto-injection of `_`-prefixed keys** (~15 lines in `_walk`):
`_`-prefixed keys (e.g., `_template_manager`) propagate down the tree as "defaults". When a child dict has `_target_` and its class has a matching constructor param (without `_` prefix), the value is auto-injected — unless the child already sets it explicitly.

```python
def _walk(node, _injectable=None):
    if _injectable is None:
        _injectable = {}
    
    if isinstance(node, dict):
        # Collect _prefixed keys as injectable defaults (inherit from parent)
        local_injectable = dict(_injectable)
        hydra_keys = {"_target_", "_recursive_", "_convert_", "_partial_", "_args_"}
        for k, v in node.items():
            if k.startswith("_") and k not in hydra_keys:
                local_injectable[k.lstrip("_")] = v  # _template_manager → template_manager
        
        # Step 1: Resolve _target_ + attrs preprocessing
        if "_target_" in node:
            ...
            _filter_attrs_keys(node, cls)
            
            # Auto-inject: for each injectable, if child has matching param
            # and doesn't already set it, inject the value
            if cls is not None:
                valid_params = set(inspect.signature(cls).parameters.keys())
                for param_name, value in local_injectable.items():
                    if param_name in valid_params and param_name not in node:
                        node[param_name] = value
        
        # Step 3: Recurse (injectables propagate to children)
        for v in node.values():
            _walk(v, _injectable=local_injectable)
```

**Rules:**
- `_template_manager` at BTA level → auto-injected as `template_manager` into all descendants that accept it
- Explicit values always win (child already has `template_manager` → no injection)
- Only injects if the child class actually has the param (safe — no spurious injection)
- Works at any depth (propagates through dicts-of-dicts like worker_factory)
- Both `${_tm}` explicit references AND auto-injection work — user's choice per field

### Step 2: TemplateManager — 3 enhancements
**File**: `CoreProjects/PythonUtils/src/python_utils/string_utils/formatting/template_manager/template_manager.py`

**A. `default_template_key`** — new field + fallback in `__call__`:
```python
default_template_key: str = attrib(default="")

# In __call__:
if not template_key and self.default_template_key:
    template_key = self.default_template_key
```

**B. `load_variable()`** — helper for `template_variables` resolution:
```python
def load_variable(self, var_name, variant, root_space=None):
    """Load a specific variant of a predefined variable file."""
    root = self._resolve_templates_root(root_space)
    path = Path(root) / "_variables" / var_name / f"{variant}.jinja2"
    return path.read_text(encoding="utf-8") if path.is_file() else ""
```

**C. Smart path resolution** — resolve short `templates` paths via env var:
```python
# In __attrs_post_init__, when processing templates path:
if self.templates and isinstance(self.templates, str) and not Path(self.templates).is_absolute():
    # Try PROMPT_TEMPLATES_ROOT env var first
    root = os.environ.get("PROMPT_TEMPLATES_ROOT", "")
    if root:
        resolved = Path(root) / self.templates
        if resolved.is_dir():
            self.templates = str(resolved.resolve())
```
This allows `templates: prompt_templates` in YAML when `PROMPT_TEMPLATES_ROOT` is set (e.g., in `.env`).

### Step 2b: InferencerBase — add `template_variables` field
**File**: `CoreProjects/AgentFoundation/src/agent_foundation/common/inferencers/inferencer_base.py`

Add field and update `_build_feed()`:
```python
# New field (alongside template_extra_feed):
template_variables: dict = attrib(factory=dict)  # {var_name: variant_name}

# In _build_feed(), before merging template_extra_feed:
# Resolve template_variables: each value is a variant name →
# load from _variables/<var_name>/<variant>.jinja2 via the variable loader
if self.template_variables and self.template_manager:
    resolved = {}
    for var_name, variant in self.template_variables.items():
        if not variant:  # empty string = use default / skip
            resolved[var_name] = ""
        else:
            # Let TemplateManager's variable loader resolve the variant
            resolved[var_name] = self.template_manager.load_variable(
                var_name, variant, self.template_root_space
            )
    feed.update(resolved)
feed.update(self.template_extra_feed)  # explicit overrides win
```

This also requires a small helper on TemplateManager:
```python
def load_variable(self, var_name, variant, root_space=None):
    """Load a specific variant of a predefined variable file."""
    # Resolve _variables/<var_name>/<variant>.jinja2
    ...
```

### Step 3: Register RovoChat + BTA + TemplateManager aliases
**File**: `CoreProjects/AgentFoundation/src/agent_foundation/common/configs/registered_targets.py`

```python
register_alias("RovoChat", f"{_P}.common.inferencers...RovoChatInferencer", "inferencer")
register_alias("BTA", f"{_P}.common.inferencers...BreakdownThenAggregateInferencer", "inferencer")
```

**File**: `CoreProjects/PythonUtils/src/python_utils/config_utils/_registry.py` (or registered_targets)
```python
register_alias("TemplateManager",
    "python_utils.string_utils.formatting.template_manager.template_manager.TemplateManager",
    "config")
```

### Step 3: BTA — 4 changes
**File**: `CoreProjects/AgentFoundation/src/.../breakdown_then_aggregate_inferencer.py`

**A. Built-in JSON subtask parser** — new fields + method:
```python
# New fields:
breakdown_format: str = attrib(default="auto", kw_only=True)  # "auto" | "json_subtasks" | "numbered_list"
worker_query_fields: tuple = attrib(default=("description", "todos"), kw_only=True)

# New method — consolidates create_role + role_setup parsing:
def _parse_json_subtasks(self, raw_output: str) -> list:
    """Parse JSON subtask format from task_breakdown template."""
    ...

# Updated parse logic (~line 664):
if self.breakdown_parser is not None:
    sub_queries = self.breakdown_parser(raw_output)
elif self.breakdown_format == "json_subtasks":
    sub_queries = self._parse_json_subtasks(raw_output)
elif self.breakdown_format == "numbered_list":
    sub_queries = parse_numbered_list(str(raw_output))
else:  # "auto" — existing behavior
    sub_queries = raw_output if isinstance(raw_output, list) else parse_numbered_list(str(raw_output))
```

**B. `expand_todos_to_workers` accepts `bool | dict`** (line 130):
```python
expand_todos_to_workers: Union[bool, dict] = attrib(default=False, kw_only=True)
```

**C. Handle `functools.partial` in factory calls** (~line 278):
```python
if isinstance(factory, functools.partial):
    worker = factory()
else:
    worker = factory(sub_query=query_str, index=i)
```

**D. `__default__` string resolution** (~lines 225, 269):
```python
if isinstance(factory_entry, str):
    factory_entry = self.worker_factory.get(factory_entry)
```

### Step 5: Create YAML config
**File**: `CoreProjects/OpenTeam/test/.../role_setup/yaml_configs/inner_bta_skill_tool_creation.yaml` (NEW)

### Step 6: Add `load_bta()` convenience loader
**File**: `CoreProjects/AgentFoundation/src/agent_foundation/common/configs/factories.py`

### Step 7: Create test CLI script
**File**: `CoreProjects/OpenTeam/test/.../role_setup/test_role_setup_inner_bta_through_yaml.py` (NEW)

---

## Implementation Order

| Step | Task | Depends On |
|------|------|------------|
| 1 | config_utils: auto-partial for `*_factory` + auto-injection of `_`-prefixed keys | — |
| 2a | TemplateManager: `default_template_key` + `load_variable()` helper | — |
| 2b | InferencerBase: `template_variables` field + resolve in `_build_feed()` | Step 2a |
| 3 | Register `RovoChat` + `BTA` + `TemplateManager` aliases | — |
| 4 | BTA: built-in `json_subtasks` parser + partial calling + `__default__` + `expand_todos` dict | — |
| 5 | YAML config file | Steps 1-4 |
| 6 | `load_bta()` in factories.py | — |
| 7 | Test CLI script | Steps 1-6 |

---

## Verification

**Unit (no auth):**
```python
import agent_foundation.common.configs.registered_targets
import openteam.server.resources.tools.role_setup.bta_yaml_support
from python_utils.config_utils import load_config, instantiate
import functools

cfg = load_config('.../inner_bta_skill_tool_creation.yaml')
bta = instantiate(cfg)

assert type(bta).__name__ == 'BreakdownThenAggregateInferencer'
assert isinstance(bta.worker_factory['skill_tool_creation_research'], functools.partial)
w1 = bta.worker_factory['skill_tool_creation_research']()
w2 = bta.worker_factory['skill_tool_creation_research']()
assert w1 is not w2  # fresh instances
assert type(w1).__name__ == 'RovoChatInferencer'
```

---

## Critical Files

| Role | Path |
|------|------|
| config_utils | `PythonUtils/src/python_utils/config_utils/_instantiate.py:176` |
| Registered targets | `AgentFoundation/src/agent_foundation/common/configs/registered_targets.py` |
| BTA class | `AgentFoundation/src/.../breakdown_then_aggregate_inferencer.py:73` |
| Factories | `AgentFoundation/src/agent_foundation/common/configs/factories.py` |
| executor.py (NOT modified) | `OpenTeam/src/.../role_setup/executor.py` |
| test_role_setup.py (NOT modified) | `OpenTeam/test/.../role_setup/test_role_setup.py` |
