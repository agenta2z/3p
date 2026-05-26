# Template Variable Examples

Simplified examples for template-specific variable management.

## Overview

`VariableLoader` (alias for `TemplateVariableManager`) is a thin wrapper around
`FileBasedVariableManager` with template-specific defaults:

| TemplateVariableManager | FileBasedVariableManager |
|-------------------------|--------------------------|
| `template_dir` | `base_path` |
| `template_root_space` | `variable_root_space` |
| `template_type` | `variable_type` |
| `variables_folder_name="_variables"` | `variables_folder_name=""` |

## Examples

| File | Description |
|------|-------------|
| `01_template_variable_manager.py` | Basic VariableLoader usage |
| `02_template_manager_integration.py` | TemplateManager with predefined_variables |

## Running Examples

```bash
PYTHONPATH=src python examples/python_utils/string_utils/formatting/template_manager/variable_examples/01_template_variable_manager.py
PYTHONPATH=src python examples/python_utils/string_utils/formatting/template_manager/variable_examples/02_template_manager_integration.py
```

## For Detailed Feature Documentation

All features (cascade resolution, scope modifiers, composition, syntax options, etc.)
are documented in the `FileBasedVariableManager` examples:

```
examples/python_utils/common_objects/variable_manager/file_based_variable_manager/
├── 01_basic_usage.py          # Dict-like access, underscore inference
├── 02_cascade_resolution.py   # Space/type hierarchy
├── 03_scope_modifiers.py      # ^, ., ? modifiers
├── 04_variable_composition.py # Variables referencing variables
├── 05_syntax_options.py       # VariableSyntax, pattern mapping
└── 06_version_and_overrides.py # Version suffixes, .override files
```

## Quick Reference

```python
from python_utils.string_utils.formatting.template_manager import (
    TemplateManager,
    VariableLoader,
)

# Simplest: automatic variable resolution
tm = TemplateManager(
    templates="/templates",
    predefined_variables=True,
)
result = tm(
    template_key="agent/type/Template",
    active_template_root_space="agent",
    active_template_type="type",
    user_input="value",
)

# Manual: explicit VariableLoader
loader = VariableLoader(template_dir="/templates")
variables = loader.resolve_from_template(
    template_content,
    template_root_space="agent",
    template_type="type",
)
```

## Directory Structure

```
templates/
├── _variables/              <- Global variables
│   ├── mindset.hbs
│   └── notes/
│       └── core_values.hbs
├── assistant_agent/
│   ├── _variables/          <- Agent-level variables
│   │   └── notes/
│   │       └── core_values.hbs  <- Overrides global
│   └── chat/
│       ├── _variables/      <- Template-type level
│       └── main.hbs
└── code_agent/
    └── ...
```
