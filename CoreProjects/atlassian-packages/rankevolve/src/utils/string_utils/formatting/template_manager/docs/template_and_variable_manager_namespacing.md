# Template & Variable Manager Namespacing Architecture

> **Location**: `rankevolve/src/utils/string_utils/formatting/template_manager/`
> **Last Updated**: 2026-03-23
> **Status**: Living document — covers current architecture + planned improvements

---

## Table of Contents

1. [Overview](#1-overview)
2. [Three-Layer Architecture](#2-three-layer-architecture)
3. [Template Namespacing (TemplateManager)](#3-template-namespacing-templatemanager)
4. [File-Based Variable Cascade (System A)](#4-file-based-variable-cascade-system-a)
5. [Override/Sidecar/Alias Layer (System B)](#5-overridesidecaralias-layer-system-b)
6. [How the Two Systems Coexist](#6-how-the-two-systems-coexist)
7. [Current Scoping Gap & Design](#7-current-scoping-gap--design)
8. [Spacing Layers: Concrete Examples](#8-spacing-layers-concrete-examples)
9. [Template Directory Layout](#9-template-directory-layout)

---

## 1. Overview

The template and variable management system provides **hierarchical namespacing with cascading resolution** for prompt templates and their variables. It consists of three layers:

| Layer | Class | File | Responsibility |
|-------|-------|------|---------------|
| **Template Rendering** | `TemplateManager` | `template_manager.py` | Template selection, versioning, multi-level fallback, rendering |
| **Template Variables** | `TemplateVariableManager` (alias: `VariableLoader`) | `variable_manager.py` | Thin wrapper with template-specific parameter names |
| **Variable Resolution** | `FileBasedVariableManager` | `common_objects/variable_manager/file_based.py` | File-based cascade, override/alias layer, composition |

The `FileBasedVariableManager` hosts **two separate variable resolution systems**:

- **System A: File-Based Cascade** — Resolves variables from `_variables/` folders on disk. Space-aware via parameters passed per call. Used by `TemplateManager.__call__()`.
- **System B: Override/Sidecar/Alias Layer** — Loads structured data from YAML sidecars, supports runtime overrides and alias mappings. Currently **NOT space-aware** (flat dicts). Used by `JinjaPromptRenderer`.

---

## 2. Three-Layer Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        TemplateManager                           │
│  • Template key resolution with root_space + type                │
│  • Multi-level fallback (6 levels)                               │
│  • Template versioning (e.g., "enterprise", "v2")                │
│  • Predefined variable integration via _variable_loader          │
│  • switch() creates shallow copy (shares _variable_loader)       │
├──────────────────────────────────────────────────────────────────┤
│               TemplateVariableManager (VariableLoader)           │
│  • Thin wrapper: template_dir → base_path,                       │
│    template_root_space → variable_root_space, etc.               │
│  • variables_folder_name defaults to "_variables"                │
│  • resolve_from_template() → resolve_from_content()              │
├──────────────────────────────────────────────────────────────────┤
│                   FileBasedVariableManager                       │
│                                                                  │
│  ┌─────────────────────────┐  ┌──────────────────────────────┐  │
│  │   System A: File-Based  │  │  System B: Override/Sidecar  │  │
│  │   Cascade Resolution    │  │  /Alias Layer                │  │
│  │                         │  │                              │  │
│  │  • resolve_from_content │  │  • load_yaml_sidecar()       │  │
│  │  • _get_cascade_paths() │  │  • set() / clear()           │  │
│  │  • _resolve_variable()  │  │  • get_effective_value()     │  │
│  │  • _find_variable_file()│  │  • get_all_variables()       │  │
│  │                         │  │                              │  │
│  │  SPACE-AWARE ✅          │  │  NOT SPACE-AWARE ❌           │  │
│  │  (via parameters)       │  │  (flat dicts)                │  │
│  └─────────────────────────┘  └──────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 3. Template Namespacing (TemplateManager)

### 3.1 Namespace Dimensions

Templates are addressed using three namespace dimensions:

| Dimension | Attribute | Example | Role |
|-----------|----------|---------|------|
| **Root Space** | `active_template_root_space` | `"action_agent"` | Top-level agent/domain grouping |
| **Space Key** | Embedded in `template_key` | `"plan"`, `"analysis"` | Template category |
| **Type** | `active_template_type` | `"main"`, `"backup1"` | Variant within a category |

A fully qualified template key resolves to:
```
{root_space} / {space_key} / {type} / {template_name}
```

### 3.2 Template Resolution: Multi-Level Fallback

When `TemplateManager.__call__()` looks up a template, it tries progressively less-specific paths:

```
Example: root_space="root", type="main", key="action_agent/sub_space/BrowseLink"

Level 0: root/action_agent/sub_space/main/BrowseLink          ← exact match
Level 1: root/action_agent/main/default                       ← parent space traversal
Level 2: root/main/default                                    ← drop unresolved space
Level 3: main/default                                         ← drop root space
Level 4: default                                              ← global default key
Level 5: self.default_template                                ← system fallback
```

At **every level**, version-based fallback is also applied:
```
BrowseLink.enterprise  →  BrowseLink  →  default.enterprise  →  default
```

### 3.3 The `switch()` Method

Creates a **shallow copy** of the TemplateManager with different settings:

```python
new_manager = manager.switch(
    active_template_type="backup1",
    active_template_root_space="different_agent",
    template_version="enterprise",
)
```

**Critical**: `copy.copy(self)` means the new instance **shares the same `_variable_loader` reference**. Only if `predefined_variables=` is explicitly passed to `switch()` does it create a new loader.

### 3.4 Predefined Variable Integration

In `__call__()` (lines 1131-1149), the TemplateManager passes space context to the variable loader:

```python
predefined_vars = self._variable_loader.resolve_from_template(
    template_content=raw_template,
    template_root_space=active_template_root_space or "",  # Space context
    template_type=active_template_type or "main",          # Type context
    version=self.template_version,                         # Version context
)
```

Variable merge order (lowest to highest priority):
```
predefined_vars  <  feed  <  kwargs
```

---

## 4. File-Based Variable Cascade (System A)

### 4.1 How Cascade Resolution Works

System A resolves variables from **files on disk** using a cascading search path. Space and type are passed as **parameters per call**, not stored as instance state.

**Entry point**: `resolve_from_content(content, variable_root_space, variable_type, version)`

For `variable_name="task_preamble_understand_codebase"`, `root_space="plan"`, `type="main"`:

```
Step 1: Underscore split inference
  "task_preamble_understand_codebase" generates:
  - "task_preamble/understand_codebase"  (folder-based)
  - "task_preamble_understand_codebase"  (flat file)

Step 2: Cascade path search (most specific → global)
  {base_path}/plan/main/_variables/task_preamble/understand_codebase.*
  {base_path}/plan/_variables/task_preamble/understand_codebase.*
  {base_path}/_variables/task_preamble/understand_codebase.*

Step 3: File extension fallback (per path)
  .hbs → .j2 → .txt → (bare)

Step 4: Version-aware resolution (if template_version set)
  task_preamble/understand_codebase.enterprise.override  →  ...override  →
  task_preamble/understand_codebase.enterprise  →  task_preamble/understand_codebase
```

### 4.2 Scope Modifiers

In Handlebars/Jinja2 syntax, variable references can use scope modifiers:

| Modifier | Syntax | Behavior |
|----------|--------|----------|
| None | `{{variable}}` | Normal cascade (type → space → global) |
| `^` | `^{{variable}}` | Global only — skip cascade |
| `.` | `.{{variable}}` | Current level only — no fallback |
| `?` | `{{variable}}?` | Optional — return empty string if not found |

### 4.3 Variable Composition

Variables can reference other variables. Resolution is recursive with circular reference detection:

```
_variables/notes_mindset.hbs:
  "Base mindset: {{core_values}}"

_variables/core_values.hbs:
  "{{safety_guidelines}} and {{quality_standards}}"
```

Circular references raise `CircularReferenceError`. Max depth: 50 (configurable).

---

## 5. Override/Sidecar/Alias Layer (System B)

### 5.1 The Three Flat Dicts

System B provides an **in-memory variable layer** that sits alongside file-based resolution:

```python
# Initialized lazily via _init_override_layer()
_yaml_sidecar: Dict[str, object] = {}    # Structured data from .variables.yaml
_aliases: Dict[str, str] = {}             # Alias mappings (e.g., strategy → employee.mindset)
_overrides: Dict[str, object] = {}        # Runtime overrides (highest priority)
```

### 5.2 YAML Sidecar Loading

`load_yaml_sidecar(yaml_path)` loads a `.variables.yaml` file:

```yaml
# .initial.variables.yaml
employee:
  name: RankEvolve
  role: an AI scientist and engineer
  mindset:
    paradigm_shifting_innovation: |
      - Challenge every assumption...
    incremental_improvement: |
      - Start with profiling...

__alias__:
  strategy: employee.mindset    # Maps "strategy" → "employee.mindset"
```

Processing:
1. Extracts `__alias__` section → stores in `_aliases`
2. Stores remaining data in `_yaml_sidecar` (as nested dict)

### 5.3 The `set()` Method (with Alias + Sub-Key Resolution)

```python
def set(self, key: str, value: object, override: bool = True) -> None:
```

**Step 1**: Resolve alias — `set("strategy", ...)` → resolves to `"employee.mindset"`

**Step 2**: Sub-key selection — If the alias target is a dict in `_yaml_sidecar` and `value` matches a sub-key:
```python
set("strategy", "paradigm_shifting_innovation")
# → employee.mindset is a dict → "paradigm_shifting_innovation" IS a sub-key
# → stores _overrides["employee.mindset"] = full mindset text
```

**Step 3**: Raw value storage — If `value` does NOT match a sub-key:
```python
set("strategy", "custom edited text...")
# → "custom edited text..." is NOT a sub-key → falls through
# → stores _overrides["employee.mindset"] = "custom edited text..."
```

### 5.4 Resolution Priority

`get_effective_value(key)` resolves with this priority:
```
_overrides  >  _yaml_sidecar  >  file-based (System A)
```

`get_all_variables()` merges by deep-copying `_yaml_sidecar` and applying `_overrides` on top (using `set_at_path()` for dot-notation paths like `employee.mindset`).

### 5.5 Current Callers

| Caller | File | Methods Used |
|--------|------|-------------|
| `JinjaPromptRenderer.variable_manager` | `prompt_rendering.py:97-126` | `load_yaml_sidecar()` at creation |
| `JinjaPromptRenderer.template_variables` | `prompt_rendering.py:128-165` | `get_all_variables()`, checks `_overrides` |
| `ConversationalInferencer` (planned) | `conversational_inferencer.py` | `set()`, `get_effective_value()` |

---

## 6. How the Two Systems Coexist

### 6.1 Different Callers, No Collision (Current State)

| Path | System Used | Variable Manager Instance | Scoping |
|------|------------|--------------------------|---------|
| **TemplateManager** → `_variable_loader.resolve_from_template()` | System A (file cascade) | ONE shared `_variable_loader` | ✅ Space-aware via parameters |
| **JinjaPromptRenderer** → `vm.get_all_variables()` | System B (sidecar/overrides) | ONE per renderer | ✅ Isolated per renderer instance |
| **JinjaPromptRenderer** → `vm.set()` | System B (overrides) | Same per-renderer instance | ✅ Isolated per renderer instance |

**Key insight**: These two systems never collide in the current code because:

1. **System A** is used by `TemplateManager.__call__()`, which passes `(root_space, type)` as parameters per call. It **never touches** `_overrides`, `_aliases`, or `_yaml_sidecar`.

2. **System B** is used by `JinjaPromptRenderer`, which creates its **own** `FileBasedVariableManager` instance per renderer. Each conversation template gets an isolated variable manager.

### 6.2 Why There's No Cross-Contamination

```
ConversationalInferencer (conversation/main/initial.jinja2)
  └─ prompt_renderer: JinjaPromptRenderer          ← OWN instance
       └─ _variable_manager: FileBasedVariableManager  ← OWN instance
            ├─ _yaml_sidecar  ← from .initial.variables.yaml
            ├─ _aliases        ← from __alias__ in that YAML
            └─ _overrides      ← isolated to this renderer

DualInferencerBridge (plan/main/initial.jinja2)
  └─ plan_inferencer (uses TemplateManager path)
       └─ _variable_loader: TemplateVariableManager     ← SHARED across spaces
            └─ resolve_from_template(root_space, type)   ← System A only
            └─ _overrides, _aliases, _yaml_sidecar       ← exist but UNUSED
```

---

## 7. Current Scoping Gap & Design

### 7.1 The Gap

System B's `_overrides`, `_aliases`, and `_yaml_sidecar` are **flat dicts with no space dimension**:

```python
# Current: flat (no scoping)
_yaml_sidecar = {"employee": {"name": "RankEvolve", ...}}
_aliases = {"strategy": "employee.mindset"}
_overrides = {"employee.mindset": "selected strategy text"}
```

If someone called `load_yaml_sidecar()` or `set()` on the shared `_variable_loader` for **multiple spaces**, the data would collide:

```python
# Hypothetical collision scenario
vm.load_yaml_sidecar("plan/main/.initial.variables.yaml")    # Writes to flat _yaml_sidecar
vm.load_yaml_sidecar("impl/main/.initial.variables.yaml")    # OVERWRITES the same flat dict!

vm.set("strategy", "paradigm_shifting", root_space="plan")   # ← no space param exists!
vm.set("strategy", "efficiency", root_space="impl")           # ← OVERWRITES same override!
```

### 7.2 Why It Doesn't Bite Today

1. **JinjaPromptRenderer** creates its own `FileBasedVariableManager` per renderer → isolation via separate instances
2. **TemplateManager** uses System A (`resolve_from_template()`) which **never touches** System B dicts
3. **No code** currently calls `set()` or `load_yaml_sidecar()` on a shared `_variable_loader`

### 7.3 Design: Space-Aware Override/Sidecar/Alias Layer

To make System B fully space-aware, matching System A's cascade model:

#### Internal Structure Change

```python
# Proposed: scoped by (root_space, type) tuple
_scoped_yaml_sidecars: Dict[Tuple[str, str], Dict[str, object]] = {}
_scoped_aliases: Dict[Tuple[str, str], Dict[str, str]] = {}
_scoped_overrides: Dict[Tuple[str, str], Dict[str, object]] = {}
# Default scope ("", "") = global — backward compatible
```

#### Method Signature Changes (Backward-Compatible)

All System B methods gain optional `variable_root_space` and `variable_type` keyword parameters:

```python
def load_yaml_sidecar(self, yaml_path, *,
                       variable_root_space: str = "",
                       variable_type: str = "") -> Dict: ...

def set(self, key: str, value: object, *,
        variable_root_space: str = "",
        variable_type: str = "",
        override: bool = True) -> None: ...

def get_effective_value(self, key: str, default: object = None, *,
                        variable_root_space: str = "",
                        variable_type: str = "",
                        skip_overrides: bool = False) -> object: ...

def get_all_variables(self, *,
                      variable_root_space: str = "",
                      variable_type: str = "") -> Dict[str, object]: ...

def clear(self, key: str, *,
          variable_root_space: str = "",
          variable_type: str = "") -> None: ...
```

#### Cascade Resolution for System B

Matching System A's `_get_cascade_paths()` logic:

```python
def _cascade_scopes(self, root_space: str, vtype: str) -> list[tuple[str, str]]:
    """Generate scope cascade order (most specific → global)."""
    scopes = []
    if root_space and vtype:
        scopes.append((root_space, vtype))   # e.g., ("plan", "main")
    if root_space:
        scopes.append((root_space, ""))       # e.g., ("plan", "")
    scopes.append(("", ""))                   # global
    return scopes
```

For `get_effective_value("strategy", variable_root_space="plan", variable_type="main")`:
```
1. Check _scoped_overrides[("plan", "main")]     ← most specific
2. Check _scoped_overrides[("plan", "")]          ← space-level
3. Check _scoped_overrides[("", "")]              ← global
4. Check _scoped_yaml_sidecars[("plan", "main")]
5. Check _scoped_yaml_sidecars[("plan", "")]
6. Check _scoped_yaml_sidecars[("", "")]
7. File-based resolution (System A — already space-aware)
```

#### Backward Compatibility

Properties provide access to global-scope dicts for existing code:

```python
@property
def _overrides(self) -> Dict[str, object]:
    """Backward compat: returns global scope overrides."""
    self._init_override_layer()
    return self._scoped_overrides.setdefault(("", ""), {})

@property
def _aliases(self) -> Dict[str, str]:
    """Backward compat: returns global scope aliases."""
    self._init_override_layer()
    return self._scoped_aliases.setdefault(("", ""), {})

@property
def _yaml_sidecar(self) -> Dict[str, object]:
    """Backward compat: returns global scope yaml sidecar."""
    self._init_override_layer()
    return self._scoped_yaml_sidecars.setdefault(("", ""), {})
```

Existing code that calls `set("strategy", value)` without scope parameters operates on `("", "")` (global) — **identical behavior to today**.

---

## 8. Spacing Layers: Concrete Examples

The system supports **four distinct spacing dimensions**, each with cascade fallback. This section walks through every dimension with concrete, real examples from the codebase.

### 8.1 Spacing Dimensions Summary

| Dimension | Where Used | Examples | Cascade Direction |
|-----------|-----------|---------|-------------------|
| **Root Space** | `active_template_root_space` | `"action_agent"`, `""` (global) | root_space → global |
| **Space Key** | Embedded in `template_key` | `"plan"`, `"conversation"`, `"analysis"` | parent_space/child → parent → global |
| **Type** | `active_template_type` | `"main"`, `"backup1"`, `"experimental"` | type → global |
| **Version** | `template_version` | `"enterprise"`, `"v2"`, `""` (default) | versioned → unversioned |

### 8.2 Layer 1: Space Key (Template Category)

The space key is the **template category** — the top-level folder under `prompt_templates/`. This is the most commonly used spacing dimension.

**Existing spaces in the codebase:**
```
prompt_templates/
├── analysis/          ← space_key = "analysis"
├── conversation/      ← space_key = "conversation"
├── deep_research/     ← space_key = "deep_research"
├── implementation/    ← space_key = "implementation"
├── individual_proposal/
├── plan/              ← space_key = "plan"
├── task_breakdown/
├── unified_proposal/
└── welcome_message/
```

**Resolution example:**
```python
manager = TemplateManager(templates="/path/to/prompt_templates", active_template_type="main")

# Resolves to: plan/main/initial.jinja2
result = manager("plan/initial", target_path="/data/users/...")

# Resolves to: analysis/main/followup.jinja2
result = manager("analysis/followup", round_number=3)
```

**Cascade behavior for nested spaces:**
```
Template key: "plan/sub_experiment/initial"

Lookup order:
  1. plan/sub_experiment/main/initial    ← exact
  2. plan/main/default                   ← parent space fallback
  3. main/default                        ← drop space entirely
  4. default                             ← global
  5. self.default_template               ← system fallback
```

### 8.3 Layer 2: Type (Variant Within a Category)

The type is a **variant selector** within a space. Currently all spaces use `"main"`, but the architecture supports multiple types like `"backup1"`, `"experimental"`, etc.

**Current layout (single type per space):**
```
plan/
└── main/               ← type = "main"
    ├── initial.jinja2
    ├── followup.jinja2
    └── review.jinja2
```

**Hypothetical multi-type layout:**
```
plan/
├── main/               ← type = "main" (production)
│   ├── initial.jinja2
│   ├── followup.jinja2
│   └── review.jinja2
├── concise/            ← type = "concise" (shorter prompts)
│   ├── initial.jinja2
│   └── followup.jinja2   # review.jinja2 absent → falls back to main/
└── experimental/       ← type = "experimental" (A/B testing)
    └── initial.jinja2     # followup + review absent → falls back
```

**Resolution example with type cascade:**
```python
manager = TemplateManager(
    templates="/path/to/prompt_templates",
    active_template_type="concise",
)

# Has concise/initial.jinja2 → uses it
result = manager("plan/initial")

# No concise/review.jinja2 → falls back through:
#   plan/concise/review  ✗
#   plan/main/review     ✗  (main is not automatically tried — type is fixed)
#   plan/review          ✗
#   review               ✗
#   default_template     ← system fallback
result = manager("plan/review")

# To get main's review, use switch():
main_manager = manager.switch(active_template_type="main")
result = main_manager("plan/review")  # → plan/main/review.jinja2
```

### 8.4 Layer 3: Root Space (Agent/Domain Grouping)

The root space is a **top-level namespace prefix** for multi-agent or multi-domain deployments. It prepends to the full key.

**Resolution example:**
```python
manager = TemplateManager(
    templates="/path/to/prompt_templates",
    active_template_root_space="action_agent",
    active_template_type="main",
)

# Full key construction: root_space / space_key / type / template_name
# → action_agent / plan / main / initial

# Lookup order:
#   1. action_agent/plan/main/initial     ← root_space + space + type
#   2. action_agent/plan/main/default     ← default name at same level
#   3. action_agent/main/default          ← drop space, keep root + type
#   4. plan/main/initial                  ← drop root_space
#   5. main/default                       ← drop space
#   6. default                            ← global
result = manager("plan/initial")
```

**Hypothetical multi-agent directory layout:**
```
prompt_templates/
├── _variables/                         # Global variables
├── action_agent/                       # root_space = "action_agent"
│   └── plan/
│       └── main/
│           └── initial.jinja2          # Agent-specific plan template
├── plan/
│   └── main/
│       └── initial.jinja2              # Default plan template (fallback)
└── conversation/
    └── main/
        └── initial.jinja2
```

### 8.5 Layer 4: Version (Deployment Variant)

Versioning is a **construction-time** decision that adds a suffix to template names during lookup. It enables A/B testing, regional variants, and deployment-level customization.

**Resolution example with versioning:**
```python
manager = TemplateManager(
    templates="/path/to/prompt_templates",
    active_template_type="main",
    template_version="enterprise",        # Version suffix
    template_version_sep=".",             # Separator (default ".")
)

# For template key "plan/initial", lookup order at EACH cascade level:
#   plan/main/initial.enterprise    ← versioned name (try first)
#   plan/main/initial               ← unversioned fallback
#   plan/main/default.enterprise    ← versioned default
#   plan/main/default               ← unversioned default
#   ... (continue cascade levels)
result = manager("plan/initial")
```

**Directory layout with versions:**
```
plan/main/
├── initial.jinja2                  # Default (unversioned)
├── initial.enterprise.jinja2       # Enterprise variant
├── initial.v2.jinja2               # V2 variant
├── followup.jinja2                 # No versioned variants
└── review.jinja2
```

**Switching versions at runtime:**
```python
# Production
prod_manager = TemplateManager(templates=path, template_version="")

# Enterprise deployment
enterprise_manager = prod_manager.switch(template_version="enterprise")

# A/B test variant
test_manager = prod_manager.switch(template_version="v2")
```

### 8.6 Variable Spacing: File-Based Cascade (System A)

Variables follow the **same spacing model** as templates, using `_variables/` folders at each level.

**Concrete cascade for `{{task_preamble_understand_codebase}}` in `plan/main/initial.jinja2`:**

```
Template rendering call:
  manager("plan/initial", active_template_type="main")
  → _variable_loader.resolve_from_template(raw, root_space="", type="main")

Variable "task_preamble_understand_codebase" underscore-splits to:
  - task_preamble/understand_codebase  (folder path)
  - task_preamble_understand_codebase  (flat file)

Cascade search order:
  1. plan/main/_variables/task_preamble/understand_codebase.j2     ← FOUND ✅
     (this is where generic.j2 lives, resolved via .config.yaml → default)
  2. plan/_variables/task_preamble/understand_codebase.*           ← not checked (found above)
  3. _variables/task_preamble/understand_codebase.*                ← not checked
```

**With versioning (template_version="modeling"):**
```
Cascade search order (at each path level):
  1a. plan/main/_variables/task_preamble/understand_codebase.modeling.override
  1b. plan/main/_variables/task_preamble/understand_codebase.override
  1c. plan/main/_variables/task_preamble/understand_codebase.modeling
  1d. plan/main/_variables/task_preamble/understand_codebase/modeling/  ← folder variant
  1e. plan/main/_variables/task_preamble/understand_codebase.*         ← unversioned
  (if none found, move to next cascade level)
  2a. plan/_variables/task_preamble/understand_codebase.modeling.override
  ...
  3a. _variables/task_preamble/understand_codebase.*
```

**Real example with .config.yaml:**
```
plan/main/_variables/task_preamble/understand_codebase/
├── generic.j2           # General codebase investigation preamble
├── modeling.j2          # Modeling-specific preamble
└── .config.yaml         # {"default": "generic"} → generic.j2 is the default
```

When `version=""` → resolves to `generic.j2` (via .config.yaml default).
When `version="modeling"` → resolves to `modeling.j2` (folder-based version match).

### 8.7 Variable Spacing: Override/Sidecar/Alias Layer (System B) — Current Gap

**System B does NOT support spacing.** All three dicts are flat:

```python
# Current: YAML sidecar from conversation/main/.initial.variables.yaml
_yaml_sidecar = {
    "employee": {
        "name": "RankEvolve",
        "mindset": {"paradigm_shifting_innovation": "...", ...}
    }
}
_aliases = {"strategy": "employee.mindset"}
_overrides = {}  # Populated by set("strategy", "paradigm_shifting_innovation")
```

**What SHOULD work but DOESN'T with a shared variable manager:**
```python
# Hypothetical: load different sidecars for different spaces
vm.load_yaml_sidecar("conversation/main/.initial.variables.yaml")
# _yaml_sidecar = {employee: {name: "RankEvolve", ...}}

vm.load_yaml_sidecar("plan/main/.initial.variables.yaml")
# _yaml_sidecar OVERWRITES! Previous conversation data is LOST.

# Hypothetical: set overrides for different spaces
vm.set("strategy", "paradigm_shifting")    # For conversation space
vm.set("strategy", "efficiency")            # OVERWRITES! Conversation value is LOST.
```

**What the proposed scoped design enables:**
```python
# Each space loads its own sidecar into its own scope
vm.load_yaml_sidecar("conversation/main/.initial.variables.yaml",
                      variable_root_space="conversation", variable_type="main")
vm.load_yaml_sidecar("plan/main/.initial.variables.yaml",
                      variable_root_space="plan", variable_type="main")
# Both coexist: _scoped_yaml_sidecars[("conversation", "main")] and [("plan", "main")]

# Overrides are scoped independently
vm.set("strategy", "paradigm_shifting",
       variable_root_space="conversation", variable_type="main")
vm.set("strategy", "efficiency",
       variable_root_space="plan", variable_type="main")
# Both coexist: _scoped_overrides[("conversation", "main")] and [("plan", "main")]

# Resolution cascades through scopes
vm.get_effective_value("strategy",
                       variable_root_space="conversation", variable_type="main")
# → checks ("conversation", "main") → ("conversation", "") → ("", "") → file-based
```

### 8.8 Complete Spacing Matrix

| Layer | Template Resolution | Variable File Cascade (System A) | Override/Sidecar/Alias (System B) |
|-------|--------------------|---------------------------------|----------------------------------|
| **Root Space** | ✅ Prepends to key | ✅ `{root_space}/{type}/_variables/` | ❌ Flat (proposed: scoped) |
| **Space Key** | ✅ Part of key, parent fallback | ✅ Part of cascade path | ❌ Not applicable |
| **Type** | ✅ Appended to space | ✅ `{root_space}/{type}/_variables/` | ❌ Flat (proposed: scoped) |
| **Version** | ✅ Name suffix fallback | ✅ File suffix + folder variant | ❌ Not applicable |
| **Scope modifiers** | N/A | ✅ `^` global, `.` local, `?` optional | ❌ Not applicable |

---

## 9. Template Directory Layout

```
prompt_templates/
├── _variables/                          # Global variables (shared by all)
│   └── employee/
├── analysis/main/
│   ├── _variables/analysis_request/     # analysis-specific variables
│   ├── initial.jinja2
│   ├── followup.jinja2
│   └── review.jinja2
├── conversation/main/
│   ├── _variables/
│   │   ├── workflow/sop.md
│   │   └── workflow_description/default.jinja2
│   ├── .initial.variables.yaml          # YAML sidecar (System B)
│   ├── .initial.config.yaml             # Rendering config
│   └── initial.jinja2
├── deep_research/main/
│   ├── initial.jinja2, followup.jinja2, review.jinja2
├── implementation/main/
│   ├── _variables/task_preamble/understand_codebase/
│   ├── initial.jinja2, followup.jinja2, review.jinja2
├── individual_proposal/main/
│   ├── initial.jinja2, followup.jinja2, review.jinja2
├── plan/main/
│   ├── _variables/task_preamble/understand_codebase/
│   │   ├── generic.j2
│   │   ├── modeling.j2
│   │   └── .config.yaml
│   ├── initial.jinja2, followup.jinja2, review.jinja2
├── task_breakdown/main/
│   ├── initial.jinja2, followup.jinja2, review.jinja2
├── unified_proposal/main/
│   ├── initial.jinja2, followup.jinja2, review.jinja2
└── welcome_message/
    └── default.md
```

**Naming Conventions**:
- `_variables/` — Variable files folder (System A reads from here)
- `.initial.variables.yaml` — YAML sidecar for `initial.jinja2` (System B loads this)
- `.initial.config.yaml` — Rendering config for `initial.jinja2`
- `.config.yaml` — Folder-level config (specifies default file in multi-file folders)
- `_archive/` — Archived templates (ignored by resolution)

---

## Appendix A: Configuration Reference

### VariableManagerConfig

```python
@dataclass
class VariableManagerConfig:
    variables_folder_name: str = ""                    # Subfolder for variables
    variable_syntax: VariableSyntax = HANDLEBARS       # Parsing syntax
    enable_overrides: bool = False                     # .override files
    override_suffix: str = ".override"
    cache_content: bool = True                         # In-memory caching
    file_extensions: List[str] = [".hbs", ".j2", ".txt", ""]
    max_recursion_depth: int = 50                      # Composition depth limit
    compose_on_access: bool = True                     # Auto-resolve nested refs
```

### TemplateVariableLoaderConfig (extends VariableManagerConfig)

```python
@dataclass
class TemplateVariableLoaderConfig(VariableManagerConfig):
    variables_folder_name: str = "_variables"          # Template convention
```

## Appendix B: Error Types

| Error | Trigger | Resolution |
|-------|---------|------------|
| `AmbiguousVariableError` | Multiple matching files at same cascade level | Remove duplicate, or use more specific path |
| `CircularReferenceError` | Variable references itself in composition chain | Break the cycle |
| `MaxDepthExceededError` | Composition exceeds 50 levels | Simplify variable nesting |

## Appendix C: Public API

```python
# Template Manager
from rankevolve.src.utils.string_utils.formatting.template_manager import (
    TemplateManager,        # Main template renderer
    VariableLoader,         # Alias for TemplateVariableManager
    VariableLoaderConfig,   # Alias for TemplateVariableLoaderConfig
)

# Variable Manager (lower-level)
from rankevolve.src.utils.common_objects.variable_manager import (
    VariableManager,           # Abstract base (Mapping interface)
    FileBasedVariableManager,  # Full implementation
    KeyDiscoveryMode,          # LAZY or EAGER
    VariableManagerConfig,     # Configuration
    VariableSyntax,            # HANDLEBARS, JINJA2, PYTHON_FORMAT, TEMPLATE
)
```
