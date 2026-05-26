# FileBasedVariableManager Examples

Comprehensive examples for `FileBasedVariableManager` from `python_utils.common_objects`.

## Overview

`FileBasedVariableManager` is a file-based key-value store with:
- **Dict-like access**: `manager['key']`, `manager.get('key', default)`
- **Underscore inference**: `config_timeout` → `config/timeout.txt`
- **Class-level cascade**: Set default `variable_root_space` and `variable_type` at init
- **Cascade resolution**: `variable_type/` > `variable_root_space/` > global
- **Scope modifiers**: `^{{var}}` (global), `.{{var}}` (current), `{{var}}?` (optional)
- **Variable composition**: Variables can reference other variables (enabled by default)
- **Configurable syntax**: Handlebars, Jinja2, Python format, Template, or custom
- **Version/override support**: `var.production.txt`, `var.override.txt`

## Directory Structure

```
file_based_variable_manager/
├── 01_basic_usage.py
├── 02_cascade_and_composition.py
├── 03_scope_modifiers.py
├── 04_variable_composition.py
├── 05_syntax_options.py
├── 06_version_and_overrides.py
├── README.md
└── mock_variables/              <- Persistent test data
    ├── database_host.txt        <- 'localhost'
    ├── database_port.txt        <- '5432'
    ├── database.txt             <- 'mydb'
    ├── app_name.txt             <- 'MyApp'
    ├── log_level.txt            <- 'INFO'
    ├── greeting.txt             <- 'Hello from global'
    ├── connection_string.txt    <- 'postgresql://{{database_host}}:...'
    ├── full_config.txt          <- 'Connection: {{connection_string}}...'
    ├── api_url.txt              <- 'http://localhost:8000'
    ├── api_url.production.txt   <- 'https://api.example.com'
    ├── api_url.override.txt     <- 'http://localhost:9000'
    ├── config/
    │   ├── timeout.txt          <- '30'
    │   ├── retries.txt          <- '3'
    │   └── debug.txt            <- 'true'
    ├── production/
    │   ├── database_host.txt    <- 'prod-db.example.com'
    │   ├── database_port.txt    <- '5433'
    │   ├── log_level.txt        <- 'WARNING'
    │   └── api/
    │       ├── database_host.txt <- 'prod-api-db.example.com'
    │       └── log_level.txt     <- 'ERROR'
    ├── staging/
    │   ├── database_host.txt    <- 'staging-db.example.com'
    │   └── log_level.txt        <- 'DEBUG'
    ├── myspace/
    │   ├── greeting.txt         <- 'Hello from myspace'
    │   └── local_only.txt       <- 'Only in myspace'
    ├── circular/
    │   ├── a.txt                <- 'A references {{circular_b}}'
    │   └── b.txt                <- 'B references {{circular_a}}'
    └── message_*.{hbs,j2,py,tpl} <- Syntax examples
```

## Examples

| File | Topic | Key Concepts |
|------|-------|--------------|
| `01_basic_usage.py` | Basic usage | Dict access, underscore inference, iteration |
| `02_cascade_and_composition.py` | Cascade & composition | Class-level cascade, `cascade` param, `compose` param |
| `03_scope_modifiers.py` | Scope control | `^{{var}}`, `.{{var}}`, `{{var}}?` |
| `04_variable_composition.py` | Composition | Variables referencing variables, circular detection |
| `05_syntax_options.py` | Syntax options | VariableSyntax enum, pattern mapping |
| `06_version_and_overrides.py` | Versions/overrides | `.production.txt`, `.override.txt` |

## Running Examples

```bash
# From SciencePythonUtils root directory
PYTHONPATH=src python examples/python_utils/common_objects/variable_manager/file_based_variable_manager/01_basic_usage.py
PYTHONPATH=src python examples/python_utils/common_objects/variable_manager/file_based_variable_manager/02_cascade_and_composition.py
PYTHONPATH=src python examples/python_utils/common_objects/variable_manager/file_based_variable_manager/03_scope_modifiers.py
PYTHONPATH=src python examples/python_utils/common_objects/variable_manager/file_based_variable_manager/04_variable_composition.py
PYTHONPATH=src python examples/python_utils/common_objects/variable_manager/file_based_variable_manager/05_syntax_options.py
PYTHONPATH=src python examples/python_utils/common_objects/variable_manager/file_based_variable_manager/06_version_and_overrides.py
```

## Quick Reference

```python
from python_utils.common_objects import (
    FileBasedVariableManager,
    VariableManagerConfig,
    VariableSyntax,
    KeyDiscoveryMode,
)

# Basic usage (global only, composition enabled by default)
manager = FileBasedVariableManager(base_path="/config")
value = manager['database_host']
value = manager.get('database_port', '5432')

# Class-level cascade (used by [] and get())
manager = FileBasedVariableManager(
    base_path="/config",
    variable_root_space="production",
    variable_type="api",
)
value = manager['database_host']  # Uses production/api cascade

# Method-level control
manager.get("key", cascade=False)  # Global only, ignore class settings
manager.get("key", variable_root_space="staging")  # Override class setting
manager.get("key", compose=False)  # Raw content, no composition

# resolve_from_content for template strings
vars = manager.resolve_from_content(
    content="{{var1}} {{var2}}",
    variable_root_space="production",
    variable_type="api",
    version="v2",
)

# With configuration
config = VariableManagerConfig(
    variable_syntax=VariableSyntax.JINJA2,
    enable_overrides=True,
    compose_on_access=True,  # Default: composition enabled for [] and get()
)
manager = FileBasedVariableManager(base_path="/config", config=config)
```

## Template-Specific Usage

For template contexts, use `TemplateVariableManager` (alias: `VariableLoader`) which provides:
- Renamed parameters: `template_dir`, `template_root_space`, `template_type`
- Default `variables_folder_name="_variables"`

See: `examples/python_utils/string_utils/formatting/template_manager/`
