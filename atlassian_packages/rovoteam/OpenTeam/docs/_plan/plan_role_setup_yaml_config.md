# Plan: YAML-Driven Inner BTA for role_setup

> **Date**: 2026-04-14  
> **Author**: Claude Code  
> **Status**: Draft — awaiting approval  
> **Related**: `plan_create_role_tool.md` (predecessor — the create_role tool that role_setup extends)

---

## 1. Executive Summary

Convert the **inner BTA (BreakdownThenAggregateInferencer)** in the `role_setup` tool
from fully hardcoded Python construction to **YAML-config-driven initialization**, using
the `_target_` / `instantiate()` pattern established in PythonUtils and demonstrated
in the AgentFoundation examples.

**Scope**: Create a new test file `test_role_setup_inner_bta_through_yaml.py` alongside
the existing `test_role_setup.py` (which remains untouched). The new test proves that an
inner BTA pipeline can be assembled entirely from a YAML config file + `load_config()` /
`instantiate()`, producing the same runtime object graph as the hardcoded builder.

**Non-scope**: The *outer* BTA (role-level breakdown → N inner BTAs) is not converted in
this iteration. Outer-level orchestration still uses Python wiring. Template `.jinja2`
content stays as-is.

---

## 2. Why YAML-Driven?

| Concern | Hardcoded (current) | YAML-driven (target) |
|---------|---------------------|----------------------|
| **Reconfigurability** | Must edit `executor.py` to change concurrency, swap inferencers, adjust templates | Edit YAML; no Python changes |
| **Readability** | 200+ lines of nested builder code in `_build_inner_bta()` | Single YAML file declares the full pipeline |
| **Reusability** | Factory function tightly coupled to role_setup | Same YAML pattern works for any BTA-based tool |
| **Experimentation** | CLI flags for every knob; grows unwieldy | Override individual YAML keys at load time |
| **Testing** | Mock the builder; hard to test composition in isolation | Load YAML with test overrides; instantiate; assert shape |

---

## 3. Current Architecture (What We're Wrapping)

### 3.1 Inner BTA Pipeline (per skill/tool creation subtask)

```
                    ┌─────────────────────────────┐
                    │  Inner BTA                  │
                    │  (BreakdownThenAggregate-    │
                    │   Inferencer)                │
                    │                             │
                    │  ┌───────────────────────┐  │
                    │  │ Breakdown Inferencer   │  │
                    │  │ (RovoDevCliInferencer) │  │   Decomposes skill/tool
                    │  └───────────┬───────────┘  │   creation into facets
                    │              │               │
                    │   ┌──────────┴──────────┐   │
                    │   ▼                     ▼   │
                    │ ┌──────────┐ ┌────────────┐ │
                    │ │ Research │ │Investigation│ │   Heterogeneous workers:
                    │ │ Worker   │ │ Worker      │ │   dispatched by task_preamble
                    │ │(RovoChat)│ │(RovoDevCli) │ │   arg from breakdown output
                    │ └────┬─────┘ └──────┬─────┘ │
                    │      └──────┬───────┘       │
                    │             ▼               │
                    │  ┌───────────────────────┐  │
                    │  │ Aggregator Inferencer  │  │   Synthesizes research into
                    │  │ (RovoChat or RovoDev)  │  │   implementable tool spec
                    │  └───────────────────────┘  │
                    └─────────────────────────────┘
```

### 3.2 Hardcoded Elements in `_build_inner_bta()` (executor.py lines 448-634)

| Element | Current Value | Where Hardcoded |
|---------|---------------|-----------------|
| Breakdown inferencer type | `RovoDevCliInferencer` | `_build_inner_bta()` line ~480 |
| Breakdown inferencer flags | `yolo=True, debug_mode=True` | Same function |
| Worker dispatch field | `task_type_arg_name="task_preamble"` | Line ~600 |
| Research worker type | `RovoChatInferencer` (via `_make_rovochat`) | `research_factory()` closure |
| Investigation worker type | `RovoDevCliInferencer` | `investigation_factory()` closure |
| Research concurrency | `"skill_tool_creation_research": 3` | `group_max_concurrency` dict |
| Investigation concurrency | `"skill_tool_creation_investigation": 2` | Same dict |
| Max inner facets | Passed as param, default 5 | `max_breakdown=max_inner_facets` |
| Template variant names | `"skill_tool_creation"`, `"skill_tool_creation_research"`, etc. | Multiple `_load_variable_file` calls |
| Aggregator type | `"rovochat"` or `"rovodev"` (string switch) | if/else in builder |
| Aggregator prompt builder | Custom closure with hardcoded section headers | `_build_agg_input()` |
| Worker query field selection | `("description", "todos")` | `_DEFAULT_WORKER_QUERY_FIELDS` |

### 3.3 Template Variables Rendered Before Inference

The executor pre-renders Jinja2 templates with these variables before passing to inferencers:

| Variable | Source | Used In |
|----------|--------|---------|
| `{{ role_name }}` | First line of role document | breakdown preamble, research preamble |
| `{{ role_doc_path }}` | Resolved path to `.md` file | breakdown preamble, investigation preamble |
| `{{ available_tools_skills }}` | Registry scan of `_APP_TOOLS_DIR` + `_APP_SKILLS_DIR` | breakdown preamble |

---

## 4. Target YAML Schema Design

### 4.1 Design Principles

1. **Follow the established `_target_` pattern** from PythonUtils/AgentFoundation examples
2. **Nested composition**: Inner objects (breakdown, workers, aggregator) each have their own `_target_`
3. **Heterogeneous worker factory as a dict**: Map task_preamble values → worker configs
4. **Template references as paths**: Not embedded content — point to `.jinja2` files
5. **Override-friendly**: `load_config(path, overrides={...})` can tweak any field

### 4.2 Proposed YAML Structure

```yaml
# inner_bta_skill_tool_creation.yaml
# ---
# Defines one inner BTA pipeline for creating a single skill/tool.
# Used by role_setup's outer BTA as the worker_factory for each subtask.

_target_: BreakdownThenAggregateInferencer

# --- Breakdown Phase ---
breakdown_inferencer:
  _target_: RovoDevCliInferencer
  yolo: true
  debug_mode: true
  # Working dir, cache, and logger are injected at runtime

max_breakdown: 5

# --- Worker Phase ---
task_type_arg_name: task_preamble

# Heterogeneous worker factory: keys are task_preamble values from breakdown output
worker_factory:
  skill_tool_creation_research:
    _target_: RovoChatInferencer
    # Auth fields (cloud_id, uct_token, etc.) injected via overrides at runtime
  skill_tool_creation_investigation:
    _target_: RovoDevCliInferencer
    yolo: true
    debug_mode: true
  __default__: skill_tool_creation_research   # fallback to research factory

group_max_concurrency:
  skill_tool_creation_research: 3
  skill_tool_creation_investigation: 2

# --- Aggregation Phase ---
aggregator_inferencer:
  _target_: RovoChatInferencer
  # Auth injected at runtime

# --- Template References ---
# These are NOT constructor params of BTA — they're metadata consumed by
# the test harness / builder to pre-render Jinja2 templates before wiring.
templates:
  breakdown_preamble:
    space: task_breakdown
    variable: task_preamble
    variant: skill_tool_creation
  research_preamble:
    space: deep_research
    variable: task_preamble
    variant: skill_tool_creation_research
  investigation_preamble:
    space: deep_research
    variable: task_preamble
    variant: skill_tool_creation_investigation
  aggregation_instructions:
    space: implementation
    variable: task_instructions
    variant: skill_tool_creation

# --- Workspace ---
# workspace_root is injected at runtime (test creates timestamped dir)
```

### 4.3 Key Design Decisions

#### Decision 1: Worker factory as dict-of-configs (not callables)

**Problem**: `BreakdownThenAggregateInferencer.worker_factory` accepts either a callable
`(sub_query, index) -> InferencerBase` or a dict `{type_name: callable}` for heterogeneous
workers. Callables can't be serialized to YAML.

**Solution**: In the YAML, `worker_factory` is a dict of `_target_` configs. The test
harness converts each config into a factory callable:

```python
def _make_factory_from_config(worker_cfg, runtime_overrides):
    """Convert a _target_ config dict into a worker_factory callable."""
    def factory(sub_query, index):
        merged = OmegaConf.merge(worker_cfg, runtime_overrides)
        return instantiate(merged)
    return factory
```

This preserves the existing BTA contract while making worker types YAML-configurable.

#### Decision 2: Templates as metadata, not constructor params

**Problem**: BTA doesn't have template fields — templates are loaded and pre-rendered
*before* constructing inferencers. They're not part of the BTA object graph.

**Solution**: The `templates:` section in YAML is metadata. The test harness reads it to
know *which* template files to load and render, then injects the rendered strings into
inferencer configs via `template_extra_feed` or preamble params. This keeps template
management decoupled from object instantiation.

#### Decision 3: Runtime injection via OmegaConf overrides

**Problem**: Auth credentials (`cloud_id`, `uct_token`, etc.), workspace paths, and cache
directories are only known at runtime. They can't be baked into YAML.

**Solution**: The YAML defines the *shape* and *defaults*. Runtime values are injected via
`load_config(path, overrides={...})` or `OmegaConf.merge()`:

```python
cfg = load_config("inner_bta_skill_tool_creation.yaml", overrides={
    "breakdown_inferencer.cache_folder": streaming_cache_dir,
    "breakdown_inferencer.working_dir": workspace_root,
    "worker_factory.skill_tool_creation_research.cloud_id": cloud_id,
    "worker_factory.skill_tool_creation_research.uct_token": uct_token,
    ...
})
```

#### Decision 4: Aggregator prompt builder stays in Python

**Problem**: The aggregator prompt builder is a complex closure that:
- Iterates over worker results
- Checks for file paths vs inline content
- Renders a TemplateManager prompt with dynamic sections

This logic is procedural and stateful — not suitable for YAML declaration.

**Solution**: The YAML config references which aggregation template to use (via `templates.aggregation_instructions`), but the prompt builder function itself remains in Python. The test harness reads the template reference from YAML and constructs the prompt builder accordingly.

#### Decision 5: `__default__` key for fallback worker dispatch

Following the existing executor pattern where `__default__` maps to the research factory,
the YAML uses `__default__: skill_tool_creation_research` as a string reference to another
key in the same `worker_factory` dict.

---

## 5. File Structure

### 5.1 New Files

```
test/openteam/resources/tools/role_setup/
├── test_role_setup.py                          # EXISTING — untouched
├── test_role_setup_inner_bta_through_yaml.py   # NEW — YAML-driven test
└── yaml_configs/                               # NEW — YAML config directory
    └── inner_bta_skill_tool_creation.yaml      # NEW — inner BTA config
```

### 5.2 File Responsibilities

| File | Purpose |
|------|---------|
| `inner_bta_skill_tool_creation.yaml` | Declarative definition of the inner BTA pipeline |
| `test_role_setup_inner_bta_through_yaml.py` | CLI test that loads YAML, injects runtime params, builds BTA, runs inference |

---

## 6. Detailed Implementation Plan

### Step 1: Create the YAML config file

**File**: `test/.../role_setup/yaml_configs/inner_bta_skill_tool_creation.yaml`

Contents as shown in Section 4.2. This is the declarative "source of truth" for the
inner BTA pipeline shape.

**Verification**: Load with `load_config()` and confirm OmegaConf parses without errors.

### Step 2: Create the YAML-driven test file

**File**: `test/.../role_setup/test_role_setup_inner_bta_through_yaml.py`

This file must:

#### 2a. YAML Loading Layer

```python
def load_inner_bta_config(
    yaml_path: str,
    runtime_overrides: dict | None = None,
) -> DictConfig:
    """Load inner BTA YAML config with optional runtime overrides."""
    cfg = load_config(yaml_path)
    if runtime_overrides:
        cfg = OmegaConf.merge(cfg, OmegaConf.create(runtime_overrides))
    return cfg
```

#### 2b. Factory Conversion Layer

Convert YAML worker configs into callable factories that BTA expects:

```python
def build_worker_factories_from_config(
    worker_factory_cfg: DictConfig,
    default_key: str | None = None,
    runtime_overrides: dict | None = None,
) -> dict[str, Callable]:
    """Convert worker_factory YAML dict into {type_name: callable} dict."""
    factories = {}
    for type_name, worker_cfg in worker_factory_cfg.items():
        if type_name == "__default__":
            continue
        if isinstance(worker_cfg, str):
            # String shorthand — resolve later
            continue

        def _make_factory(cfg):
            def factory(sub_query, index):
                return instantiate(cfg)
            return factory

        factories[type_name] = _make_factory(worker_cfg)

    # Handle __default__
    if default_key and default_key in factories:
        factories["__default__"] = factories[default_key]

    return factories
```

#### 2c. Template Resolution Layer

Read template references from YAML and render with Jinja2 variables:

```python
def resolve_templates(
    templates_cfg: DictConfig,
    templates_root: Path,
    render_vars: dict,
) -> dict[str, str]:
    """Load and render templates referenced in YAML config."""
    rendered = {}
    for key, ref in templates_cfg.items():
        jinja_path = (
            templates_root / ref.space / "main" / "_variables"
            / ref.variable / f"{ref.variant}.jinja2"
        )
        raw = jinja_path.read_text(encoding="utf-8")
        rendered[key] = Template(raw).render(**render_vars)
    return rendered
```

#### 2d. BTA Assembly

Combine everything into a functioning BTA:

```python
def build_inner_bta_from_yaml(
    yaml_path: str,
    role_document_path: str,
    rovo_kwargs: dict,
    workspace_root: str,
    streaming_cache_dir: str,
    templates_root: Path,
    max_inner_facets: int = 5,
    aggregator_type: str = "rovochat",
    inferencer_logger=None,
) -> tuple[BreakdownThenAggregateInferencer, str]:
    """Build an inner BTA from YAML config + runtime params."""

    # 1. Load YAML
    cfg = load_inner_bta_config(yaml_path, runtime_overrides={
        "max_breakdown": max_inner_facets,
    })

    # 2. Resolve templates
    role_doc_text = Path(role_document_path).read_text()
    role_name = role_doc_text.split("\n")[0].strip("# ").strip()
    templates = resolve_templates(cfg.templates, templates_root, {
        "role_name": role_name,
        "role_doc_path": str(Path(role_document_path).resolve()),
        "available_tools_skills": format_available_tools_and_skills(...),
    })

    # 3. Build breakdown inferencer from YAML _target_
    breakdown_cfg = OmegaConf.merge(cfg.breakdown_inferencer, {
        "cache_folder": streaming_cache_dir,
        "working_dir": workspace_root,
    })
    breakdown_inf = instantiate(breakdown_cfg)

    # 4. Build worker factories from YAML
    worker_factories = build_worker_factories_from_config(
        cfg.worker_factory,
        default_key=cfg.worker_factory.get("__default__"),
        runtime_overrides=rovo_kwargs,
    )

    # 5. Build aggregator from YAML _target_
    aggregator_cfg = OmegaConf.merge(cfg.aggregator_inferencer, rovo_kwargs)
    aggregator_inf = instantiate(aggregator_cfg)

    # 6. Build aggregator prompt builder (stays Python — uses template ref from YAML)
    agg_instructions = templates["aggregation_instructions"]
    def aggregator_prompt_builder(worker_results, original_query, **kw):
        # ... same logic as executor._build_agg_input() ...
        pass

    # 7. Assemble BTA
    bta = BreakdownThenAggregateInferencer(
        breakdown_inferencer=breakdown_inf,
        worker_factory=worker_factories,
        aggregator_inferencer=aggregator_inf,
        aggregator_prompt_builder=aggregator_prompt_builder,
        max_breakdown=cfg.max_breakdown,
        task_type_arg_name=cfg.task_type_arg_name,
        group_max_concurrency=dict(cfg.group_max_concurrency),
        workspace_root=workspace_root,
    )

    return bta, role_name
```

#### 2e. CLI Entry Point

Mirror the existing `test_role_setup.py` CLI but with YAML-specific options:

```python
@click.command()
@click.option("--role-document", required=True, type=click.Path(exists=True))
@click.option("--yaml-config", default=None, type=click.Path(exists=True),
              help="Path to inner BTA YAML config. Default: yaml_configs/inner_bta_skill_tool_creation.yaml")
@click.option("--config-overrides", default=None, type=str,
              help="JSON string of OmegaConf overrides to apply to YAML config")
# ... standard auth options (cloud-id, uct-token, email, api-token, base-url) ...
# ... standard run options (max-inner-facets, aggregator-type, output-dir) ...
@click.option("--breakdown-file", default=None, type=click.Path(),
              help="Path to outer breakdown output (to select a specific subtask)")
@click.option("--subtask-index", default=1, type=int,
              help="1-based subtask index from outer breakdown")
@click.option("--breakdown-only", is_flag=True, default=False,
              help="Run only the inner breakdown step")
def main(...):
    """Run the inner BTA for a single skill/tool creation subtask, loaded from YAML config."""
```

### Step 3: Verification Checklist

Before considering the implementation complete, verify:

- [ ] `load_config("inner_bta_skill_tool_creation.yaml")` parses without OmegaConf errors
- [ ] `instantiate(cfg.breakdown_inferencer)` produces a `RovoDevCliInferencer` with correct flags
- [ ] `instantiate(cfg.worker_factory.skill_tool_creation_research)` produces a `RovoChatInferencer`
- [ ] `instantiate(cfg.worker_factory.skill_tool_creation_investigation)` produces a `RovoDevCliInferencer`
- [ ] `instantiate(cfg.aggregator_inferencer)` produces a `RovoChatInferencer`
- [ ] Worker factory dict properly dispatches by `task_preamble` value
- [ ] `__default__` fallback resolves to research factory
- [ ] Template paths in YAML correctly resolve to existing `.jinja2` files
- [ ] Runtime overrides (auth, workspace, cache) merge correctly
- [ ] `--config-overrides '{"max_breakdown": 3}'` works from CLI
- [ ] Full E2E run with `--breakdown-only` produces valid inner breakdown output
- [ ] Full E2E run (breakdown + workers + aggregation) matches behavior of hardcoded `_build_inner_bta()`

---

## 7. Critical Considerations & Risks

### 7.1 Registration: Classes Must Be Registered

For `_target_: RovoDevCliInferencer` to work with `instantiate()`, the class must be
either:

(a) **Registered via `@register()` decorator** — preferred if classes are in AgentFoundation  
(b) **Referenced by full import path** — e.g., `_target_: agent_foundation.common.inferencers.agentic_inferencers.external.rovodev.rovodev_cli_inferencer.RovoDevCliInferencer`

**Current state**: Need to verify whether `RovoDevCliInferencer`, `RovoChatInferencer`,
and `BreakdownThenAggregateInferencer` are registered in the config_utils registry.

**Action**: Check `@register` decorators on these classes. If not registered, either:
- Add `register_class()` calls in the test's setup, or
- Use full import paths in YAML (verbose but works without modifying AgentFoundation)

### 7.2 Attrs Underscore Stripping

`RovoDevCliInferencer` and other classes use `@attrs` with underscore-prefixed private
fields (e.g., `_call_count`). The `instantiate()` function auto-strips leading underscores
for YAML keys. This means:
- YAML `secret_key` → Python `_secret_key` (correct)
- YAML `yolo` → Python `yolo` (correct — no underscore)

**Risk**: If a class has both `_foo` and `foo` fields, name collision. Unlikely but worth
checking.

### 7.3 Worker Factory Lifecycle

Each worker must be a **fresh instance** (new conversation per facet for RovoChat,
fresh session for RovoDevCli). The factory callable must create a new instance each
time — not reuse the same one.

**Mitigation**: The `_make_factory()` closure calls `instantiate(cfg)` on each invocation,
which creates a new object. OmegaConf configs are immutable, so this is safe.

### 7.4 Aggregator Prompt Builder Complexity

The current `_build_agg_input()` closure in `executor.py` is ~60 lines of procedural
logic. It cannot be expressed in YAML. The test file must replicate this logic (or import
it from executor.py if it's factored out).

**Options**:
- (a) **Import from executor**: `from openteam.server.resources.tools.role_setup.executor import _build_agg_input_factory` — cleanest, but couples test to executor internals
- (b) **Duplicate the logic**: Copy the prompt builder into the test — decoupled but duplicated
- (c) **Reference a registered callable**: Register the prompt builder and reference by name in YAML

**Recommendation**: Option (a) — import from executor. The prompt builder is stable logic
that belongs with the tool, not the test. If executor doesn't export it cleanly, refactor
a small helper.

### 7.5 Partial Instantiation

`BreakdownThenAggregateInferencer` itself cannot be directly `instantiate()`-d from the
YAML because:
- `worker_factory` needs to be a callable dict (not a config dict)
- `aggregator_prompt_builder` is a Python function
- `inferencer_logger` is a runtime object

**Solution**: The YAML is loaded and used as a *structured config* rather than directly
instantiated as a single `instantiate(cfg)` call. Individual sub-components (breakdown
inferencer, workers, aggregator) are instantiated from their YAML sub-trees, then
assembled in Python. This is a **partial instantiation** pattern — the YAML drives
component configs, Python drives assembly.

This is the pragmatic middle ground. Full end-to-end `instantiate()` of a BTA would
require custom resolvers for callables, which adds complexity without proportional benefit.

### 7.6 Comparison with Existing Patterns

| Pattern | AgentFoundation Examples | This Plan |
|---------|--------------------------|-----------|
| Simple composition | `_target_: ReviewerInferencer` with nested `_target_: MockLLM` | Same for breakdown/aggregator inferencers |
| List composition | `steps: [- _target_: MockLLM, ...]` | Not used (workers are dict-based, not list-based) |
| Shorthand | `base: MockLLM` | Possible for `__default__` reference |
| Runtime overrides | `load_config(path, overrides={...})` | Auth, workspace, cache injected this way |
| **New: heterogeneous dict** | Not in examples | `worker_factory: {type1: {_target_: ...}, type2: {_target_: ...}}` |
| **New: metadata section** | Not in examples | `templates:` section for Jinja2 references |

---

## 8. Implementation Order

| Step | Description | Files | Effort | Dependencies |
|------|-------------|-------|--------|-------------|
| 1 | Verify class registration in config_utils registry | Check AgentFoundation source | Small | None |
| 2 | Create YAML config file | `yaml_configs/inner_bta_skill_tool_creation.yaml` | Small | Step 1 (need to know if full paths or aliases) |
| 3 | Create test file — YAML loading + factory conversion layers | `test_role_setup_inner_bta_through_yaml.py` | Medium | Step 2 |
| 4 | Create test file — BTA assembly from YAML | Same file | Medium | Step 3 |
| 5 | Create test file — CLI entry point | Same file | Small | Step 4 |
| 6 | Create `__init__.py` in `yaml_configs/` if needed | `yaml_configs/__init__.py` | Trivial | None |
| 7 | Manual E2E verification — breakdown-only mode | Run test | Manual | Steps 1-5 + auth credentials |
| 8 | Manual E2E verification — full pipeline | Run test | Manual | Step 7 |
| 9 | Compare outputs: YAML-driven vs hardcoded builder | Diff outputs | Manual | Step 8 |

---

## 9. Example CLI Usage

```bash
# Basic: run inner BTA from YAML with a specific subtask from outer breakdown
python -m test.openteam.resources.tools.role_setup.test_role_setup_inner_bta_through_yaml \
    --role-document /path/to/program_manager_role.md \
    --breakdown-file /path/to/outer_breakdown_result.json \
    --subtask-index 1 \
    --uct-token "$ROVOCHAT_UCT_TOKEN" \
    --cloud-id "$ROVOCHAT_CLOUD_ID"

# Custom YAML config with overrides
python -m test.openteam.resources.tools.role_setup.test_role_setup_inner_bta_through_yaml \
    --role-document /path/to/role.md \
    --yaml-config ./my_custom_inner_bta.yaml \
    --config-overrides '{"max_breakdown": 3, "group_max_concurrency": {"skill_tool_creation_research": 1}}' \
    --breakdown-only \
    --cloud-id "$ROVOCHAT_CLOUD_ID" \
    --uct-token "$ROVOCHAT_UCT_TOKEN"

# Breakdown-only (no workers, no aggregation)
python -m test.openteam.resources.tools.role_setup.test_role_setup_inner_bta_through_yaml \
    --role-document /path/to/role.md \
    --breakdown-file /path/to/breakdown.json \
    --subtask-index 2 \
    --breakdown-only \
    --cloud-id "$ROVOCHAT_CLOUD_ID" \
    --uct-token "$ROVOCHAT_UCT_TOKEN"
```

---

## 10. Open Questions

1. **Class registration**: Are `RovoDevCliInferencer`, `RovoChatInferencer`, and
   `BreakdownThenAggregateInferencer` already registered with `@register()` in
   AgentFoundation? If not, should we register them there or use full import paths
   in the YAML?

2. **Aggregator prompt builder reuse**: Should we import `_build_agg_input` from
   executor.py, or duplicate it? Importing is cleaner but creates a dependency on
   the executor's internal API.

3. **Scope of "through YAML"**: Should the test support *all* modes of the existing
   test (resume, inner-research-only, subtask-breakdown-only, etc.), or focus on the
   core path (breakdown + workers + aggregation)?  
   → **Recommendation**: Start with core path + breakdown-only. Other modes are
   incremental additions.

4. **Future: outer BTA from YAML too?** If inner BTA from YAML works well, should
   the outer BTA (role-level breakdown → N inner BTAs) also be YAML-driven?  
   → **Deferred** — the outer BTA's worker_factory creates *inner BTAs*, which adds
   another layer of nesting. Worth exploring after this iteration proves the pattern.
