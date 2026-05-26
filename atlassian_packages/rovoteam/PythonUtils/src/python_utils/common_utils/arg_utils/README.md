# get_parsed_args - Simplified Argument Parsing

A powerful wrapper around Python's `argparse` that reduces boilerplate and provides advanced features like presets, type inference, and flexible argument definitions.

## Table of Contents

- [Quick Start](#quick-start)
- [Input Formats](#input-formats)
- [Type Handling](#type-handling)
- [Presets System](#presets-system)
- [Priority Order](#priority-order)
- [Advanced Features](#advanced-features)
- [Examples](#examples)
- [API Reference](#api-reference)
- [Migration Guide](#migration-guide)

## Quick Start

```python
from python_utils.common_utils.arg_utils.arg_parse import get_parsed_args

# Simplest usage - just add default_ prefix
args = get_parsed_args(
    default_learning_rate=0.001,
    default_batch_size=32,
    default_model_name="transformer",
)

# Use the parsed arguments
print(f"Training with lr={args.learning_rate}, batch_size={args.batch_size}")
```

Run your script:
```bash
python train.py                              # Uses defaults
python train.py --learning_rate 0.01         # Override specific values
python train.py -lr 0.01 -bs 64              # Use short names
```

## Input Formats

`get_parsed_args` supports 7 different input formats for maximum flexibility:

### Format 1: default_xxx kwargs (Simplest)

```python
args = get_parsed_args(
    default_learning_rate=0.001,
    default_batch_size=32,
)
# Creates: --learning_rate (short: -lr), --batch_size (short: -bs)
```

### Format 2: 2-tuples (name, default)

```python
args = get_parsed_args(
    ("learning_rate", 0.001),
    ("batch_size", 32),
)
```

### Format 3: 2-tuples with custom short names

```python
args = get_parsed_args(
    ("learning_rate/lr", 0.001),  # Explicit short name
    ("batch_size/bs", 32),
)
```

### Format 4: 3-tuples with description

```python
args = get_parsed_args(
    ("learning_rate/lr", 0.001, "Learning rate for optimizer"),
    ("batch_size/bs", 32, "Training batch size"),
)
```

### Format 5: 4-tuples with converter function

```python
args = get_parsed_args(
    ("learning_rate/lr", 0.001, "Learning rate", float),
    ("batch_size/bs", 32, "Batch size", int),
)
```

### Format 6: 5-tuples with type

```python
args = get_parsed_args(
    ("learning_rate/lr", 0.001, "Learning rate", None, float),
    ("layers/l", [128, 256], "Layer sizes", None, list),
)
```

### Format 7: ArgInfo namedtuple (Most Explicit)

```python
from python_utils.common_utils.arg_utils.arg_parse import ArgInfo

args = get_parsed_args(
    ArgInfo(
        full_name="learning_rate",
        short_name="lr",
        default_value=0.001,
        description="Learning rate for optimizer",
    ),
    ArgInfo(
        full_name="batch_size",
        short_name="bs",
        default_value=32,
        description="Training batch size",
    ),
)
```

## Type Handling

Type inference is automatic based on default values:

### Boolean Flags

```python
args = get_parsed_args(
    default_debug=False,    # Becomes a flag: --debug (no value needed)
    default_verbose=True,   # Requires explicit value: --verbose false
)

# Usage:
# python script.py --debug              -> debug=True
# python script.py --verbose false      -> verbose=False
```

### Lists

Element type is inferred from the first element:

```python
args = get_parsed_args(
    default_layers=[128, 256, 512],     # List of ints
    default_ratios=[0.1, 0.2, 0.3],     # List of floats
    default_names=['train', 'val'],     # List of strings
)

# Usage:
# python script.py --layers "[64, 128, 256]"
```

### Dictionaries

```python
args = get_parsed_args(
    default_config={'lr': 0.001, 'momentum': 0.9},
)

# Usage:
# python script.py --config "{'lr': 0.01, 'momentum': 0.95}"
```

### Tuples

```python
args = get_parsed_args(
    default_input_shape=(224, 224, 3),
    default_kernel_size=(3, 3),
)

# Usage:
# python script.py --input_shape "(128, 128, 1)"
```

## Presets System

Presets allow you to store configurations separately from code and share them across scripts.

### Dict Preset

```python
preset = {
    "learning_rate": 0.01,
    "batch_size": 64,
    "optimizer": "adam",
}

args = get_parsed_args(
    default_learning_rate=0.001,
    default_batch_size=32,
    preset=preset,
)
# learning_rate=0.01 (from preset), batch_size=64 (from preset)
```

### JSON Preset File

```python
# config.json:
# {
#   "learning_rate": 0.01,
#   "batch_size": 64,
#   "model_name": "resnet50"
# }

args = get_parsed_args(
    default_learning_rate=0.001,
    default_batch_size=32,
    preset="config.json",
)

# Or from command line:
# python script.py --preset config.json
```

### Python Preset File

```python
# config.py:
# config = {
#     "learning_rate": 0.01,
#     "batch_size": 64,
#     "nested_config": {
#         "hidden_size": 256,
#         "num_layers": 4,
#     }
# }

args = get_parsed_args(
    default_learning_rate=0.001,
    preset="config.py",
)
# Nested dicts are converted to Namespace objects
# Access: args.nested_config.hidden_size
```

### YAML Preset File

```python
# config.yaml:
# learning_rate: 0.01
# batch_size: 64
# model:
#   name: resnet50
#   layers: [64, 128, 256]
# training:
#   epochs: 100
#   optimizer: adam

args = get_parsed_args(
    default_learning_rate=0.001,
    default_batch_size=32,
    preset="config.yaml",
)

# Or use .yml extension
# preset="config.yml"
```

### TOML Preset File

```python
# config.toml:
# learning_rate = 0.01
# batch_size = 64
#
# [model]
# name = "resnet50"
# layers = [64, 128, 256]
#
# [training]
# epochs = 100
# optimizer = "adam"

args = get_parsed_args(
    default_learning_rate=0.001,
    default_batch_size=32,
    preset="config.toml",
)

# TOML tables (sections) become nested dicts
# args.model['name'] == 'resnet50'
# args.training['epochs'] == 100
```

### Key Extraction

Extract specific configurations from nested presets:

```python
# config.json:
# {
#   "small": {"hidden_size": 128, "num_layers": 2},
#   "medium": {"hidden_size": 256, "num_layers": 4},
#   "large": {"hidden_size": 512, "num_layers": 8}
# }

args = get_parsed_args(preset="config.json:medium")
# Extracts only the "medium" configuration
# args.hidden_size = 256, args.num_layers = 4
```

### Multiple Presets

Combine multiple preset files (later presets override earlier ones):

```python
args = get_parsed_args(
    preset="base_config.json,experiment_config.json",
)
```

## Priority Order

When the same argument is defined in multiple places, the priority order (highest to lowest) is:

1. **CLI arguments** - `python script.py --learning_rate 0.1`
2. **Preset values** - From JSON/Python files or dict
3. **Default values** - Specified in `get_parsed_args()`

Example:

```python
# Default: learning_rate=0.001
# Preset: learning_rate=0.01
# CLI: --learning_rate 0.1

# Result: learning_rate=0.1 (CLI wins)
```

## Advanced Features

### Required Arguments

```python
args = get_parsed_args(
    ("model_path", None, "Path to model"),
    ("dataset_path", None, "Path to dataset"),
    required_args=["model_path", "dataset_path"],
)
# These arguments MUST be provided via CLI or preset
```

### Non-Empty Validation

```python
args = get_parsed_args(
    default_model_path="",
    default_dataset_path="",
    non_empty_args=["model_path", "dataset_path"],
)
# Validates that these arguments are not empty strings
# Boolean arguments are exempt from this check
```

### Hidden Arguments (exposed_args)

Create internal arguments that aren't shown in `--help`:

```python
args = get_parsed_args(
    default_public_arg="value",
    default_internal_arg="hidden",
    exposed_args=["public_arg"],  # Only this shows in --help
)
```

### Return Seen Arguments

Get a list of arguments that were actually specified:

```python
args, seen = get_parsed_args(
    default_learning_rate=0.001,
    default_batch_size=32,
    return_seen_args=True,
)
# If user ran: python script.py --learning_rate 0.01
# seen = ['learning_rate']
```

### Interactive Mode

Collect argument values interactively instead of from command-line:

```python
args = get_parsed_args(
    ("learning_rate/lr", 0.001, "Learning rate for optimizer"),
    ("batch_size/bs", 32, "Training batch size"),
    ("model_name/m", "transformer", "Model architecture"),
    ("debug/d", False, "Enable debug mode"),
    interactive=True,
)
```

**Features:**
- **Jupyter notebooks**: Interactive widgets (requires `ipywidgets`)
- **Terminal with questionary**: Rich prompts with validation
- **Terminal fallback**: Basic `input()` prompts

**Installation:**
```bash
# For Jupyter widgets
pip install ipywidgets

# For better terminal experience
pip install questionary
```

**Use Cases:**
- Jupyter notebooks where CLI arguments aren't natural
- Scripts that need guided configuration
- Exploratory data analysis sessions
- Training scripts with many hyperparameters

**Combined with Presets:**
```python
preset = {"learning_rate": 0.01, "batch_size": 64}

args = get_parsed_args(
    ("learning_rate", 0.001, "Learning rate"),
    ("batch_size", 32, "Batch size"),
    preset=preset,
    interactive=True,
)
# Interactive prompts will show preset values as defaults
```

### Variable Substitution

Use variables from environment or constants:

```python
import os
os.environ['DATA_ROOT'] = '/data'

args = get_parsed_args(
    default_data_path="$DATA_ROOT/train",
    constants={'PROJECT': '/home/user/project'},
    default_output_path="$PROJECT/output",
)
# args.data_path = '/data/train'
# args.output_path = '/home/user/project/output'
```

### Preset Root Directory

Specify a root directory for preset file resolution:

```python
args = get_parsed_args(
    preset="configs/experiment.json",
    preset_root="/home/user/project",
)
# Looks for: /home/user/project/configs/experiment.json
```

### Underscore to Dash Conversion

```python
args = get_parsed_args(
    default_learning_rate=0.001,
    double_underscore_to_dash=True,
)
# Converts: learning__rate -> learning-rate in CLI
```

## Examples

### Simple Training Script

```python
from python_utils.common_utils.arg_utils.arg_parse import get_parsed_args

args = get_parsed_args(
    ("learning_rate/lr", 0.001, "Learning rate"),
    ("batch_size/bs", 32, "Batch size"),
    ("epochs/e", 100, "Number of epochs"),
    ("model_name/m", "transformer", "Model architecture"),
    ("debug/d", False, "Enable debug mode"),
)

print(f"Training {args.model_name}")
print(f"  LR: {args.learning_rate}, Batch: {args.batch_size}, Epochs: {args.epochs}")
print(f"  Debug: {args.debug}")
```

### Using Presets

```python
args = get_parsed_args(
    ("learning_rate/lr", 0.001, "Learning rate"),
    ("batch_size/bs", 32, "Batch size"),
    preset="configs/base.json",  # Load from file
)

# Or from CLI:
# python train.py --preset configs/base.json --learning_rate 0.01
```

### Configuration Management

```python
# configs/small.json (or small.yaml, or small.toml)
# {"hidden_size": 128, "num_layers": 2, "num_heads": 4}

# configs/medium.json (or medium.yaml, or medium.toml)
# {"hidden_size": 256, "num_layers": 4, "num_heads": 8}

# configs/large.json (or large.yaml, or large.toml)
# {"hidden_size": 512, "num_layers": 8, "num_heads": 16}

args = get_parsed_args(
    default_hidden_size=128,
    default_num_layers=2,
    default_num_heads=4,
)

# Usage with JSON:
# python train.py --preset configs/medium.json
#
# Usage with YAML:
# python train.py --preset configs/medium.yaml
# python train.py --preset configs/large.yml --learning_rate 0.001
#
# Usage with TOML:
# python train.py --preset configs/medium.toml
```

## API Reference

### get_parsed_args()

```python
def get_parsed_args(
    *arg_info_objs,
    legacy: bool = False,
    preset: Optional[Union[str, Dict]] = None,
    preset_root: Optional[str] = None,
    argv: Optional[List[str]] = None,
    return_seen_args: bool = False,
    exposed_args: Optional[List[str]] = None,
    required_args: Optional[List[str]] = None,
    non_empty_args: Optional[List[str]] = None,
    constants: Optional[Dict] = None,
    short_name_separator: str = "/",
    double_underscore_to_dash: bool = False,
    interactive: bool = False,
    verbose: bool = True,
    **kwargs
) -> Union[Namespace, Tuple[Namespace, List[str]]]:
```

**Parameters:**

- `*arg_info_objs`: Variable number of argument definitions (see Input Formats)
- `legacy` (bool): Use legacy implementation (for backward compatibility)
- `preset` (str|dict): Preset file path or dictionary
- `preset_root` (str): Root directory for resolving preset files
- `argv` (list): Custom argument list (default: sys.argv)
- `return_seen_args` (bool): Return list of arguments that were specified
- `exposed_args` (list): Arguments to show in --help (hides others)
- `required_args` (list): Arguments that must be provided
- `non_empty_args` (list): Arguments that cannot be empty
- `constants` (dict): Constants for variable substitution
- `short_name_separator` (str): Separator for full_name/short_name syntax
- `double_underscore_to_dash` (bool): Convert __ to - in argument names
- `interactive` (bool): Enable interactive mode for collecting argument values
- `verbose` (bool): Print parsed arguments
- `**kwargs`: Additional default_xxx arguments

**Returns:**

- `Namespace`: Parsed arguments object
- `Tuple[Namespace, List[str]]`: If `return_seen_args=True`, returns (args, seen_args)

## Migration Guide

### From Legacy Implementation

The new modular implementation is 100% backward compatible. If you encounter any issues, you can temporarily use the legacy implementation:

```python
args = get_parsed_args(
    default_learning_rate=0.001,
    legacy=True,  # Use old implementation
)
```

### Future Extensions

The new architecture supports extensions through the preset loader registry:

- **YAML presets**: ✅ Supported (.yaml and .yml files)
- **TOML presets**: ✅ Supported (.toml files, requires tomllib/tomli)
- **Interactive mode**: ✅ Supported (ipywidgets for Jupyter, questionary for terminal)

To extend with custom preset loaders:

```python
from python_utils.common_utils.arg_utils.presets.base import PresetLoader
from python_utils.common_utils.arg_utils.parsing.preset_loader import PresetLoaderRegistry


# Example custom INI loader
class IniPresetLoader(PresetLoader):
    @property
    def supported_extensions(self):
        return ('.ini', '.cfg')

    def can_handle(self, file_path: str) -> bool:
        return any(file_path.endswith(ext) for ext in self.supported_extensions)

    def resolve_path(self, file_path: str):
        # Implementation...
        pass

    def load(self, file_path: str, keys=None):
        # Implementation...
        pass


# Register the custom loader
registry = PresetLoaderRegistry()
registry.register(IniPresetLoader())
```

## See Also

- [Example Scripts](../../../../examples/python_utils/common_utils/arg_utils/) - Interactive tutorials and demos
- [Unit Tests](../../../../test/python_utils/common_utils/arg_utils/) - Comprehensive test coverage
- [Argument Naming](arg_naming.py) - Short name generation logic

## Contributing

When adding new features to `get_parsed_args`:

1. Add the feature to the new modular implementation
2. Update backward compatibility tests
3. Add examples to the interactive tutorials
4. Update this README

The modular architecture is organized as:

- `parsing/parser_builder.py` - Main orchestrator
- `parsing/argument_registrar.py` - Argument registration
- `parsing/value_converter.py` - Type conversion and validation
- `parsing/preset_loader.py` - Preset loading registry
- `presets/` - Individual preset loader implementations
