# Plan: Inner BTA YAML Configuration — `test_role_setup_inner_bta_through_yaml`

> **Date**: 2026-04-14  
> **Author**: Rovo Dev  
> **Status**: Draft — awaiting approval

---

## 1. Executive Summary

The current `test_role_setup.py` hardcodes all inner BTA parameters directly in Python (preamble
names, worker types, template paths, aggregator type, concurrency settings, etc.). This plan
introduces a **YAML-driven initialization** for the inner BTA pipeline, using the existing
`python_utils.config_utils` infrastructure (OmegaConf + Hydra-style instantiation).

A new test script `test_role_setup_inner_bta_through_yaml.py` will:
1. Accept a YAML config file path (and an outer breakdown file + subtask index) as CLI arguments
2. Load and instantiate the inner BTA entirely from the YAML definition
3. Run the inner BTA (breakdown → workers → aggregator) identically to the current hardcoded version

This enables reuse, experimentation, and variant configurations without touching Python code.

---

## 2. Background: What Gets Hardcoded Today

The function `_build_inner_bta()` in `executor.py` has the following signature and hardcoded values:

```python
def _build_inner_bta(
    sub_query: str,                           # runtime — subtask description
    index: int,                               # runtime — subtask index
    tm: Any,                                  # runtime — TemplateManager
    rovo_kwargs: dict,                        # runtime — RovoChat auth kwargs
    inner_breakdown_preamble: str,            # ← passed in by caller (should be in config)
    inner_research_preamble: str,             # ← passed in by caller (should be in config)
    inner_synthesis_instructions: str,        # ← passed in by caller (should be in config)
    max_inner_facets: int,                    # ← passed in by caller (should be in config)
    aggregator_type: str,                     # ← passed in by caller (should be in config)
    aggregator_working_dir: Optional[str],    # ← passed in by caller (should be in config)
    streaming_cache_dir: Optional[str],       # runtime — workspace-specific
    breakdown_only: bool = False,             # runtime — mode flag
    workspace_root: Optional[str] = None,    # runtime — workspace-specific
    inferencer_logger: Optional[Any] = None, # runtime — workspace-specific
    templates_root: Optional[Path] = None,   # runtime — environment-specific
    role_name: str = "",                      # runtime — from role document
    role_doc_path: str = "",                  # runtime — from role document
    available_tools_text: str = "",           # runtime — from role document
)
```

**Hardcoded INSIDE the function body** (currently not passable as params):

| What | Current Hardcoded Value | Plan |
|------|------------------------|------|
| Worker: yolo | `yolo=True` | Keep hardcoded (always needed) |
| Worker: debug_mode | `debug_mode=True` | Keep hardcoded |
| Template root space (breakdown) | `"task_breakdown"` | Config via `InnerBTABreakdownConfig` |
| Template root space (workers) | `"deep_research"` | Config via `WorkerPreambleConfig` |
| Template key | `"initial"` | Config via `InnerBTABreakdownConfig` |
| Worker dispatch keys | `"skill_tool_creation_research"`, `"skill_tool_creation_investigation"` | Config via `workers` list |
| Worker type per preamble | auto-detect via file existence | Config via `WorkerPreambleConfig.type` |
| `group_max_concurrency` | `{"skill_tool_creation_research": 3, "skill_tool_creation_investigation": 2}` | Config via `InnerBTAConfig` |
| `max_concurrency` | `None` | Config via `InnerBTAConfig` |
| `expand_todos` per worker | `True` for research, `False` for investigation | Config via `WorkerPreambleConfig` |
| `output_path` | `f"skill_tool_spec_worker_{index}.md"` | Config via `InnerBTAConfig` |
| `__default__` fallback worker | uses research factory | Config (optional) |
| BTA name | `f"inner_bta_{index}"` | Config via `InnerBTAConfig.bta_name` |

**Passed-in params that should move to YAML config** (currently in `build_subtask_breakdown_only` caller):

| Param | Currently Set By | Move to Config |
|-------|-----------------|----------------|
| `inner_breakdown_preamble` | `executor.py` caller | ✅ `InnerBTABreakdownConfig.preamble` |
| `inner_research_preamble` | `executor.py` caller | ✅ `InnerBTABreakdownConfig.research_preamble` |
| `inner_synthesis_instructions` | `executor.py` caller | ✅ `InnerBTAConfig.synthesis_instructions` |
| `max_inner_facets` | CLI arg / caller | ✅ `InnerBTAConfig.max_facets` |
| `aggregator_type` | hardcoded `"rovodev"` | ✅ `InnerBTAConfig.aggregator_type` |

---

## 3. Config System Overview (PythonUtils + AgentFoundation)

The `python_utils.config_utils` system provides a **generic, non-hacky** mechanism already
used throughout AgentFoundation (e.g., `load_inferencer()`, `yaml/inferencers/*.yaml`):

| API | Description |
|-----|-------------|
| `load_config(path, overrides=None)` | Loads YAML with OmegaConf, eagerly resolves all interpolations |
| `instantiate(cfg, **kwargs)` | Recursively instantiates Python objects from `_target_` alias + kwargs |
| `@register(alias, category)` | Decorator: maps short name → full import path in global registry |
| `${path:relative/path}` | Custom resolver: resolves paths relative to YAML file |
| `${oc.env:ENV_VAR}` | Custom resolver: injects environment variables |

**Two-step pattern (used identically across the codebase):**
```python
# 1. Register at module import time (via @register decorator)
@register("InnerBTAConfig", category="inner_bta")
@attrs.define
class InnerBTAConfig:
    max_facets: int = attrs.field(default=6)
    ...

# 2. Load YAML → OmegaConf dict
cfg = load_config("path/to/inner_bta_skill_tool.yaml")

# 3. Instantiate → InnerBTAConfig (with nested objects resolved automatically)
config = instantiate(cfg)
```

**Key behaviors:**
- `instantiate()` recursively walks nested dicts/lists — any nested dict with `_target_`
  is also instantiated. Workers list (`list[WorkerPreambleConfig]`) is handled automatically.
- String shorthand: `_target_: InnerBTAConfig` (alias) → resolved via registry → full import path
- `@register` must run (module must be imported) before `instantiate()` is called
- attrs classes work natively — `instantiate()` filters `init=False` attrs fields automatically

**AgentFoundation precedent** — the same pattern with a convenience loader:
```python
# agent_foundation.common.configs.factories
def load_inferencer(name_or_path):
    """Resolve 'conversational' → yaml/inferencers/conversational.yaml → load → instantiate"""
    ...
```

We will follow this exact same pattern for `load_inner_bta_config(name_or_path)`.

---

## 4. Architecture: What We Are Building

```
test_role_setup_inner_bta_through_yaml.py
        │  CLI args: --yaml-config, --breakdown-file, --subtask-index, ...
        │
        ▼
┌──────────────────────────────────────────────────────────┐
│  inner_bta_skill_tool.yaml                               │
│                                                          │
│  _target_: InnerBTAConfig                                │
│  max_facets: 6                                           │
│  aggregator_type: rovodev                                │
│  group_max_concurrency:                                  │
│    skill_tool_creation_research: 3                       │
│    skill_tool_creation_investigation: 2                  │
│  breakdown:                                              │
│    _target_: InnerBTABreakdownConfig                     │
│    preamble: skill_tool_creation                         │
│  workers:                                                │
│    - _target_: WorkerPreambleConfig                      │
│      preamble: skill_tool_creation_research              │
│      type: rovochat                                      │
│    - _target_: WorkerPreambleConfig                      │
│      preamble: skill_tool_creation_investigation         │
│      type: rovodev                                       │
└──────────────────────────────────────────────────────────┘
        │  load_config() + instantiate()
        ▼
┌──────────────────────────────────────────────────────────┐
│  build_inner_bta_from_config(config, **runtime_args)     │
│  (new thin wrapper in executor.py)                       │
│                                                          │
│  Translates InnerBTAConfig fields → calls _build_inner_bta()
└──────────────────────────────────────────────────────────┘
        │
        ▼
  BreakdownThenAggregateInferencer (same as current)
```

---

## 5. Design Decisions & Critical Thinking

### 5.1 Thin Config vs Fat Config

**Option A — Thin config** (preferred): YAML defines only *intent* (preamble names, worker types,
concurrency). Python builder (`build_inner_bta_from_config`) still creates all inferencer
instances, template managers, etc.

**Option B — Fat config**: YAML directly instantiates every inferencer object via `_target_`.
Requires registering RovoDevCliInferencer, RovoChatInferencer, TemplateManager, BTA, worker
factory lambdas — extremely verbose and fragile for this use case.

**Decision**: **Option A**. YAML defines what, Python handles how. Keeps YAML readable and
avoids registering every internal class.

### 5.2 Config Class Design

We define three new **attrs dataclass** config objects:
- `WorkerPreambleConfig` — one entry per worker preamble type (preamble name + inferencer type)
- `InnerBTABreakdownConfig` — breakdown phase settings (preamble, template root space, key)
- `InnerBTAConfig` — top-level container with all configurable fields

All registered with `@register(...)` so YAML can reference them via `_target_`.

### 5.3 Runtime Args vs YAML Args

**In YAML** (static, reusable across runs):
- `max_facets`, `aggregator_type`, `group_max_concurrency`
- `breakdown.preamble`, `breakdown.template_root_space`
- Worker preamble names and types
- `bta_name` template (with `{index}` placeholder)

**As CLI args** (runtime-specific):
- `--breakdown-file` — outer breakdown file
- `--subtask-index` — which outer subtask
- `--workspace` — output workspace root
- `--email` / `--api-token` / `--uct-token` — auth credentials
- `--templates-root` — templates directory (default: relative to test script)

### 5.4 Reuse of `_build_inner_bta()`

We do NOT duplicate `_build_inner_bta()`. We add a thin wrapper:
```python
def build_inner_bta_from_config(config: InnerBTAConfig, sub_query, index, **runtime_args):
    return _build_inner_bta(
        sub_query=sub_query,
        index=index,
        max_inner_facets=config.max_facets,
        aggregator_type=config.aggregator_type,
        inner_breakdown_preamble=config.breakdown.preamble,
        group_max_concurrency=config.group_max_concurrency,
        ...
    )
```

### 5.5 Worker Type Override

The existing worker factory auto-detects worker type by checking if a preamble file exists under
`"deep_research"` template space. YAML config adds explicit `type: rovochat` / `type: rovodev`
per worker, bypassing auto-detection when set. `type: auto` (default) preserves existing behavior.

### 5.6 Backward Compatibility

`test_role_setup.py` is NOT modified. It continues to work as before. The new script is purely
additive — a parallel entry point using the YAML path.

---

## 6. Files to Create / Modify

### 6.1 NEW: `inner_bta_config.py`

**Path**: `src/openteam/server/resources/tools/role_setup/inner_bta_config.py`

> **Registration**: `@register()` decorators fire at module import time. `load_inner_bta_config()`
> handles this automatically via a self-import. The test script just calls:
> `config = load_inner_bta_config("skill_tool")` — no manual import or instantiate() needed.

```python
from __future__ import annotations
from typing import Optional, Dict, List
import attrs
from python_utils.config_utils import register


@register("WorkerPreambleConfig", category="inner_bta")
@attrs.define
class WorkerPreambleConfig:
    """Config for a single worker preamble type in the inner BTA."""
    preamble: str = attrs.field()
    type: str = attrs.field(default="auto")     # "rovodev" | "rovochat" | "auto"
    expand_todos: Optional[bool] = attrs.field(default=None)
    # None = use default per type (True for rovochat, False for rovodev)
    template_root_space: str = attrs.field(default="deep_research")
    # Template namespace used to locate preamble files for this worker type


@register("InnerBTABreakdownConfig", category="inner_bta")
@attrs.define
class InnerBTABreakdownConfig:
    """Config for the inner BTA breakdown phase."""
    preamble: str = attrs.field(default="skill_tool_creation")
    research_preamble: str = attrs.field(default="skill_tool_creation")
    # research_preamble: fallback preamble for workers not in the workers list
    template_root_space: str = attrs.field(default="task_breakdown")
    template_key: str = attrs.field(default="initial")


@register("InnerBTAConfig", category="inner_bta")
@attrs.define
class InnerBTAConfig:
    """Top-level config for the inner BTA pipeline."""
    max_facets: int = attrs.field(default=6)
    aggregator_type: str = attrs.field(default="rovodev")   # "rovodev" | "rovochat"
    group_max_concurrency: Dict[str, int] = attrs.field(factory=dict)
    max_concurrency: Optional[int] = attrs.field(default=None)
    bta_name: str = attrs.field(default="inner_bta_{index}")  # {index} substituted at runtime
    output_path_template: str = attrs.field(default="skill_tool_spec_worker_{index}.md")
    synthesis_instructions: str = attrs.field(default="")
    # synthesis_instructions: custom instructions for the aggregator; if empty, uses default
    breakdown: InnerBTABreakdownConfig = attrs.field(factory=InnerBTABreakdownConfig)
    workers: List[WorkerPreambleConfig] = attrs.field(factory=list)
    # workers: if empty → auto-detection via file existence (existing executor.py behavior)
    default_worker_type: str = attrs.field(default="rovochat")
    # default_worker_type: fallback type for preambles not listed in workers


def load_inner_bta_config(name_or_path: str) -> InnerBTAConfig:
    """Load an InnerBTAConfig from a named config or an explicit file path.

    Following the same pattern as agent_foundation's load_inferencer():

    Examples:
        load_inner_bta_config("skill_tool")
        # → resolves to configs/inner_bta_skill_tool.yaml relative to this file

        load_inner_bta_config("/absolute/path/to/my_config.yaml")
        # → loads directly from the given path

        load_inner_bta_config("../custom_bta.yaml")
        # → resolves relative to this file's directory
    """
    # Import self to ensure @register decorators have fired
    import openteam.server.resources.tools.role_setup.inner_bta_config  # noqa: F401

    path = Path(name_or_path)
    if not path.suffix:
        # Treat as a short name: "skill_tool" → configs/inner_bta_skill_tool.yaml
        yaml_path = Path(__file__).parent / "configs" / f"inner_bta_{name_or_path}.yaml"
    elif path.is_absolute():
        yaml_path = path
    else:
        # Relative path: resolve relative to this file's directory
        yaml_path = Path(__file__).parent / path

    if not yaml_path.exists():
        raise FileNotFoundError(f"InnerBTAConfig YAML not found: {yaml_path}")

    cfg = load_config(str(yaml_path))
    return instantiate(cfg)
```

### 6.2 NEW: `inner_bta_skill_tool.yaml`

**Path**: `src/openteam/server/resources/tools/role_setup/configs/inner_bta_skill_tool.yaml`

```yaml
# Inner BTA configuration for skill/tool creation (Program Manager role setup)
# Used by test_role_setup_inner_bta_through_yaml.py
#
# IMPORTANT: The module openteam.server.resources.tools.role_setup.inner_bta_config
# must be imported before instantiate() is called to register the _target_ aliases.

_target_: InnerBTAConfig

# How many research/investigation facets to break down into (max)
max_facets: 6

# Aggregator: "rovodev" uses RovoDevCliInferencer (local agent)
# "rovochat" uses RovoChatInferencer (Atlassian Rovo knowledge API)
aggregator_type: rovodev

# Max concurrent workers per group (controls API rate limiting)
group_max_concurrency:
  skill_tool_creation_research: 3
  skill_tool_creation_investigation: 2

# Global max concurrency across all workers (null = unlimited)
max_concurrency: null

# BTA name template — {index} is substituted at runtime with the subtask index
bta_name: "inner_bta_{index}"

# Output file name template — {index} substituted at runtime
output_path_template: "skill_tool_spec_worker_{index}.md"

# synthesis_instructions: extra instructions for aggregator (empty = use default from executor)
synthesis_instructions: ""

# Fallback worker type when a preamble is not listed in workers below
default_worker_type: rovochat

# Breakdown phase configuration
breakdown:
  _target_: InnerBTABreakdownConfig
  preamble: skill_tool_creation           # Breakdown preamble template name
  research_preamble: skill_tool_creation  # Fallback research preamble for unlisted workers
  template_root_space: task_breakdown     # Template namespace for breakdown
  template_key: initial                   # Template variant key

# Worker definitions — one entry per preamble type
# type: "rovochat"       → uses RovoChatInferencer (Rovo knowledge API)
# type: "rovodev"        → uses RovoDevCliInferencer (local agent via acli)
# type: "auto"           → auto-detects based on template file existence
# expand_todos: null     → use per-type default (True for rovochat, False for rovodev)
# template_root_space    → template namespace for this worker (default: "deep_research")
workers:
  - _target_: WorkerPreambleConfig
    preamble: skill_tool_creation_research
    type: rovochat
    expand_todos: true
    template_root_space: deep_research

  - _target_: WorkerPreambleConfig
    preamble: skill_tool_creation_investigation
    type: rovodev
    expand_todos: false
    template_root_space: deep_research
```

### 6.3 MODIFY: `executor.py` — add params + new function

**Location**: `src/openteam/server/resources/tools/role_setup/executor.py`

**Change 1**: Add new optional params to `_build_inner_bta()`:
```python
def _build_inner_bta(
    ...,                                            # existing params unchanged
    bta_name_override: str | None = None,           # NEW: override f"inner_bta_{index}"
    output_path_override: str | None = None,        # NEW: override f"skill_tool_spec_worker_{index}.md"
    override_worker_configs: list | None = None,    # NEW: list of WorkerPreambleConfig
    default_worker_type: str = "rovochat",          # NEW: fallback type for unlisted preambles
    group_max_concurrency_override: dict | None = None,  # NEW: override hardcoded concurrency
    max_concurrency_override: int | None = None,    # NEW: override hardcoded None
    synthesis_instructions_override: str = "",      # NEW: extra instructions for aggregator
) -> BreakdownThenAggregateInferencer:
    ...
    # Worker factory checks override_worker_configs before auto-detection
    # bta_kwargs uses overrides when provided, falls back to hardcoded defaults
```

No behavior change when all new params use their defaults.

**Change 2**: New `build_inner_bta_from_config()` function (add to executor.py, ~50 lines):
```python
def build_inner_bta_from_config(
    config: "InnerBTAConfig",
    sub_query: str,
    index: int,
    tm,
    rovo_kwargs: dict,
    workspace_root: str | None,
    streaming_cache_dir: str | None,
    inferencer_logger,
    templates_root,
    role_name: str = "",
    role_doc_path: str = "",
    available_tools_text: str = "",
    breakdown_only: bool = False,
    aggregator_working_dir: str | None = None,
):
    """Translate InnerBTAConfig + runtime args into _build_inner_bta() call."""
    return _build_inner_bta(
        sub_query=sub_query,
        index=index,
        tm=tm,
        rovo_kwargs=rovo_kwargs,
        # Configurable params from InnerBTAConfig:
        inner_breakdown_preamble=config.breakdown.preamble,
        inner_research_preamble=config.breakdown.research_preamble,
        inner_synthesis_instructions=config.synthesis_instructions or None,
        max_inner_facets=config.max_facets,
        aggregator_type=config.aggregator_type,
        aggregator_working_dir=aggregator_working_dir,
        # New override params:
        bta_name_override=config.bta_name.replace("{index}", str(index)),
        output_path_override=config.output_path_template.replace("{index}", str(index)),
        override_worker_configs=config.workers or None,
        default_worker_type=config.default_worker_type,
        group_max_concurrency_override=config.group_max_concurrency or None,
        max_concurrency_override=config.max_concurrency,
        synthesis_instructions_override=config.synthesis_instructions or "",
        # Runtime params (passed through unchanged):
        streaming_cache_dir=streaming_cache_dir,
        breakdown_only=breakdown_only,
        workspace_root=workspace_root,
        inferencer_logger=inferencer_logger,
        templates_root=templates_root,
        role_name=role_name,
        role_doc_path=role_doc_path,
        available_tools_text=available_tools_text,
    )
```

### 6.4 NEW: `test_role_setup_inner_bta_through_yaml.py`

**Path**: `test/openteam/resources/tools/role_setup/test_role_setup_inner_bta_through_yaml.py`

**CLI interface:**
```
Options:
  --yaml-config        PATH    Path to InnerBTAConfig YAML file  [required]
  --breakdown-file     PATH    Outer breakdown output.md file    [required]
  --subtask-index      INT     Which outer subtask to run (1-based, default 1)
  --role-document      PATH    Role document for context         [required]
  --workspace          PATH    Output workspace root (auto-generated if omitted)
  --email              TEXT    Jira email for RovoChat auth
  --api-token          TEXT    Jira API token for RovoChat auth
  --uct-token          TEXT    UCT token (alternative auth)
  --templates-root     PATH    Templates directory (default: auto-detected)
  --disable-aggregator BOOL    Skip inner aggregation phase
  --log-level          TEXT    Logging level [default: INFO]
```

**Execution flow:**
```python
1. Parse CLI args (click)
2. config = load_inner_bta_config(yaml_config)
   # → handles registration + load_config + instantiate automatically
   # → returns InnerBTAConfig with all nested objects (breakdown, workers) resolved
3. Extract subtask description from breakdown_file (same as test_role_setup.py)
4. Create workspace, logger, streaming_cache_dir (same as test_role_setup.py)
5. Build tm, rovo_kwargs from auth args (same as test_role_setup.py)
6. bta = build_inner_bta_from_config(config, sub_query, index, ...)
7. Apply disable_aggregator if set: bta.disable_aggregator = True
8. _run_async_with_forced_cleanup(bta.ainfer(sub_query))
9. Print summary: workspace path, elapsed time, outputs
```

---

## 7. Implementation Steps (Ordered)

| Step | Task | File | Complexity | Notes |
|------|------|------|-----------|-------|
| 1 | Create `inner_bta_config.py` with 3 attrs config classes + `@register()` decorators | New file | Low | Must be imported before `instantiate()` |
| 2 | Create `configs/inner_bta_skill_tool.yaml` YAML definition | New file | Low | Include all fields with comments |
| 3 | Verify YAML round-trip: `load_config` + `instantiate` → `InnerBTAConfig` | pytest / manual | Low | Check all field values, nested objects, list items |
| 4 | Add 7 new optional params to `_build_inner_bta()` with defaults matching current behavior | executor.py | Medium | Must be backward-compatible — existing callers unaffected |
| 5 | Update worker factory inside `_build_inner_bta()` to use `override_worker_configs` and `default_worker_type` | executor.py | Medium | Keep auto-detection as fallback when `override_worker_configs=None` |
| 6 | Update `bta_kwargs` assembly inside `_build_inner_bta()` to use override params | executor.py | Low | `group_max_concurrency_override`, `bta_name_override`, `output_path_override` |
| 7 | Add `build_inner_bta_from_config()` to `executor.py` | executor.py | Low | Thin wrapper translating `InnerBTAConfig` to `_build_inner_bta()` |
| 8 | Create `test_role_setup_inner_bta_through_yaml.py` CLI script | New file | Medium | Mirror `test_role_setup.py` structure; use `build_inner_bta_from_config` |
| 9 | Integration test: verify YAML-driven run produces identical workspace structure | Manual / CI | Low | Compare outputs from subtask 2 vs hardcoded run |

**Estimated total**: ~4-5 hours implementation + testing.

**Critical ordering constraint**: Step 1 (registration) must be complete before Step 3 (YAML round-trip test). Steps 4-6 must be done together (they're all changes to `_build_inner_bta`). Step 8 depends on Steps 4-7.

---

## 8. Verification Plan

### Unit verification (no auth needed):
```bash
# Verify YAML loads and instantiates correctly via convenience loader
python3 -c "
from openteam.server.resources.tools.role_setup.inner_bta_config import load_inner_bta_config

# Test short-name resolution
config = load_inner_bta_config('skill_tool')
print(type(config).__name__)           # InnerBTAConfig
print('max_facets:', config.max_facets)  # 6
print('aggregator:', config.aggregator_type)  # rovodev
print('bta_name:', config.bta_name)   # inner_bta_{index}
print('breakdown preamble:', config.breakdown.preamble)  # skill_tool_creation
print('workers:', [(w.preamble, w.type) for w in config.workers])
# [('skill_tool_creation_research', 'rovochat'), ('skill_tool_creation_investigation', 'rovodev')]

# Test absolute path resolution
config2 = load_inner_bta_config('/abs/path/to/custom_config.yaml')
"
```

### Integration test (auth needed):
```bash
PYTHONPATH="..." python -m test.openteam.resources.tools.role_setup.test_role_setup_inner_bta_through_yaml \
    --yaml-config src/openteam/server/resources/tools/role_setup/configs/inner_bta_skill_tool.yaml \
    --breakdown-file test/.../20260411_171252/artifacts/breakdown_output.md \
    --subtask-index 2 \
    --role-document test/.../program_manager_role.md \
    --email "$JIRA_EMAIL" \
    --api-token "$JIRA_API_TOKEN" \
    --log-level DEBUG
```

Expected: produces same workspace structure as `test_role_setup.py --run-subtask --subtask-index 2`.

---

## 9. Open Questions

1. **`templates_root` in YAML vs CLI**: Templates path is environment-specific. Recommend passing
   as CLI arg `--templates-root` with auto-detection default (relative to test script). Should
   it also be in YAML as an optional override? **Decision needed**.

2. **Auth in YAML**: RovoChat cloud_id and base_url are runtime/auth values. Keep auth as
   CLI-only for security reasons — never in YAML. **Resolved: CLI-only**.

3. **Multiple YAML variants**: One YAML per use-case (`inner_bta_skill_tool.yaml`,
   `inner_bta_research_report.yaml`) or single parameterizable YAML? Recommendation: one YAML
   per semantic use-case, named by purpose, stored in `configs/`. **Decision needed**.

4. **Config registry import**: Resolved by the `load_inner_bta_config()` convenience function,
   which does a self-import to ensure `@register()` has fired before `instantiate()` is called.
   The test script simply calls `load_inner_bta_config("skill_tool")` — no manual import needed.
   This mirrors exactly how `load_inferencer()` works in AgentFoundation. **Resolved: handled by convenience loader**.

5. **`synthesis_instructions` source**: Currently `inner_synthesis_instructions` is set by the
   caller in `build_subtask_breakdown_only()`. In the YAML path, it comes from
   `InnerBTAConfig.synthesis_instructions`. If empty string, should the builder fall back to the
   executor's default, or should it be a required field? Recommendation: optional with fallback
   to executor default. **Resolved: optional with fallback**.

6. **Backward compatibility of `_build_inner_bta()` signature**: Adding 7 new optional params
   with backward-compatible defaults means the function signature grows significantly. Consider
   whether to use a `**kwargs` approach or keep explicit params. Recommendation: keep explicit
   params for clarity and IDE support. **Decision needed**.

7. **`aggregator_working_dir` in YAML**: This is runtime-derived (workspace path). It should
   NOT be in YAML config. Confirmed: it's a runtime arg passed through `build_inner_bta_from_config`.
   **Resolved: runtime-only**.
