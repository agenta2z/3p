"""
Example: Using Presets with get_parsed_args

This interactive example demonstrates the preset system:
- JSON preset files
- Python preset files
- Dict presets
- Priority: CLI > Preset > Default
- Key extraction from nested configs

Run with:
    python example_presets.py
"""

import json
import os
import sys
import tempfile

from resolve_path import resolve_path
resolve_path()  # Add project src to sys.path

from python_utils.common_utils.arg_utils.arg_parse import get_parsed_args


def pause():
    """Wait for user to press Enter."""
    input("\n[Press Enter to continue...]\n")


def print_header(title):
    """Print a formatted section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def example_dict_preset():
    """Using a dictionary as preset"""
    print_header("DICT PRESET: Inline configuration")

    print("""
WHAT THIS DOES:
    The simplest preset type is a Python dictionary passed directly.
    Values in the preset OVERRIDE the defaults.

CODE:
    preset = {
        "learning_rate": 0.01,    # Override default 0.001
        "batch_size": 128,        # Override default 32
        "optimizer": "adam",      # NEW argument (ad-hoc)
    }

    args = get_parsed_args(
        default_learning_rate=0.001,  # DEFAULT: 0.001
        default_batch_size=32,        # DEFAULT: 32
        default_epochs=100,           # DEFAULT: 100 (not in preset)
        preset=preset,
    )

EXPECTED BEHAVIOR:
    - learning_rate: 0.001 -> 0.01 (OVERRIDDEN by preset)
    - batch_size: 32 -> 128 (OVERRIDDEN by preset)
    - epochs: 100 (UNCHANGED, not in preset)
    - optimizer: "adam" (NEW, added by preset)
""")

    pause()
    print("RUNNING NOW...")
    print("-" * 40)

    preset = {
        "learning_rate": 0.01,
        "batch_size": 128,
        "optimizer": "adam",
    }

    args = get_parsed_args(
        default_learning_rate=0.001,
        default_batch_size=32,
        default_epochs=100,
        preset=preset,
        argv=["script"],
        verbose=False,
    )

    print(f"""
RESULT:
    args.learning_rate = {args.learning_rate}
        Was: 0.001, Preset set: 0.01 -> OVERRIDDEN

    args.batch_size    = {args.batch_size}
        Was: 32, Preset set: 128 -> OVERRIDDEN

    args.epochs        = {args.epochs}
        Was: 100, Not in preset -> UNCHANGED

    args.optimizer     = '{args.optimizer}'
        Not in defaults, Preset added -> NEW (ad-hoc argument)

OBSERVATION:
    Preset values override defaults. Arguments in preset but not in
    defaults are added as "ad-hoc" arguments automatically.
""")
    return args


def example_json_preset():
    """Using a JSON preset file"""
    print_header("JSON PRESET FILE: External configuration")

    print("""
WHAT THIS DOES:
    Load configuration from a JSON file. This is useful for:
    - Sharing configurations across scripts
    - Version-controlling your configurations
    - Separating code from configuration

    We'll create a temporary JSON file to demonstrate.
""")

    # Create a temporary JSON preset
    preset_data = {
        "learning_rate": 0.005,
        "batch_size": 64,
        "model_name": "resnet50",
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as f:
        json.dump(preset_data, f, indent=2)
        preset_path = f.name

    print(f"""
JSON FILE CONTENTS:
{json.dumps(preset_data, indent=4)}

CODE:
    args = get_parsed_args(
        default_learning_rate=0.001,  # DEFAULT: 0.001
        default_batch_size=32,        # DEFAULT: 32
        default_epochs=100,           # DEFAULT: 100
        preset="{os.path.basename(preset_path)}",  # Load from JSON
    )

EXPECTED BEHAVIOR:
    - learning_rate: 0.001 -> 0.005 (from JSON)
    - batch_size: 32 -> 64 (from JSON)
    - epochs: 100 (not in JSON, uses default)
    - model_name: "resnet50" (ad-hoc from JSON)
""")

    pause()
    print("RUNNING NOW...")
    print("-" * 40)

    try:
        args = get_parsed_args(
            default_learning_rate=0.001,
            default_batch_size=32,
            default_epochs=100,
            preset=preset_path,
            argv=["script"],
            verbose=False,
        )

        print(f"""
RESULT:
    args.learning_rate = {args.learning_rate}
        Was: 0.001, JSON set: 0.005 -> OVERRIDDEN

    args.batch_size    = {args.batch_size}
        Was: 32, JSON set: 64 -> OVERRIDDEN

    args.epochs        = {args.epochs}
        Was: 100, Not in JSON -> UNCHANGED

    args.model_name    = '{args.model_name}'
        Not in defaults, JSON added -> NEW (ad-hoc)

OBSERVATION:
    JSON files work exactly like dict presets, but are loaded from disk.
""")
    finally:
        os.unlink(preset_path)

    return args


def example_priority():
    """Demonstrating priority: CLI > preset > default"""
    print_header("PRIORITY: CLI > Preset > Default")

    print("""
WHAT THIS DOES:
    This is the most important concept! When the same argument is set
    in multiple places, the PRIORITY order determines the final value:

    1. CLI (highest)    - Command-line arguments always win
    2. Preset (middle)  - Preset overrides defaults
    3. Default (lowest) - Used when nothing else is set

CODE:
    preset = {"learning_rate": 0.01, "batch_size": 64}

    args = get_parsed_args(
        default_learning_rate=0.001,  # DEFAULT
        default_batch_size=32,        # DEFAULT
        default_epochs=100,           # DEFAULT
        preset=preset,                # PRESET overrides learning_rate, batch_size
        argv=["script", "--learning_rate", "0.1"],  # CLI overrides learning_rate
    )

EXPECTED BEHAVIOR:
    - learning_rate: CLI=0.1 > Preset=0.01 > Default=0.001
      Final: 0.1 (CLI wins!)

    - batch_size: Preset=64 > Default=32
      Final: 64 (Preset wins, no CLI)

    - epochs: Default=100
      Final: 100 (nothing else set)
""")

    pause()
    print("RUNNING NOW...")
    print("-" * 40)

    preset = {"learning_rate": 0.01, "batch_size": 64}

    args = get_parsed_args(
        default_learning_rate=0.001,
        default_batch_size=32,
        default_epochs=100,
        preset=preset,
        argv=["script", "--learning_rate", "0.1"],
        verbose=False,
    )

    print(f"""
PRIORITY RESOLUTION:

    learning_rate:
        Default = 0.001
        Preset  = 0.01   (overrides default)
        CLI     = 0.1    (overrides preset!)
        -----------------------
        FINAL   = {args.learning_rate}  <- CLI WINS!

    batch_size:
        Default = 32
        Preset  = 64     (overrides default)
        CLI     = (none)
        -----------------------
        FINAL   = {args.batch_size}  <- PRESET WINS!

    epochs:
        Default = 100
        Preset  = (none)
        CLI     = (none)
        -----------------------
        FINAL   = {args.epochs}  <- DEFAULT USED!

OBSERVATION:
    This priority system lets you have sensible defaults, override them
    with configuration files (presets), and still allow command-line
    overrides for one-off experiments.
""")
    return args


def example_key_extraction():
    """Using preset with key extraction"""
    print_header("KEY EXTRACTION: preset:key syntax")

    print("""
WHAT THIS DOES:
    JSON files can contain multiple configurations. Use the :key syntax
    to extract a specific nested configuration.

    Example: You have configs for "small", "medium", "large" models in
    one JSON file. Select which one to use with preset:key syntax.
""")

    # Create a preset with multiple configurations
    preset_data = {
        "small": {
            "hidden_size": 128,
            "num_layers": 2,
            "dropout": 0.1,
        },
        "medium": {
            "hidden_size": 256,
            "num_layers": 4,
            "dropout": 0.2,
        },
        "large": {
            "hidden_size": 512,
            "num_layers": 8,
            "dropout": 0.3,
        },
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as f:
        json.dump(preset_data, f, indent=2)
        preset_path = f.name

    print(f"""
JSON FILE CONTENTS (multiple configs):
{json.dumps(preset_data, indent=4)}

CODE:
    # Extract only the "medium" configuration
    args = get_parsed_args(
        default_hidden_size=64,
        default_num_layers=1,
        preset="{os.path.basename(preset_path)}:medium",  # Note the :medium!
    )

EXPECTED BEHAVIOR:
    Only the "medium" config is applied:
    - hidden_size: 64 -> 256
    - num_layers: 1 -> 4
    - dropout: (new) -> 0.2
""")

    pause()
    print("RUNNING NOW with :medium key...")
    print("-" * 40)

    try:
        args = get_parsed_args(
            default_hidden_size=64,
            default_num_layers=1,
            preset=f"{preset_path}:medium",
            argv=["script"],
            verbose=False,
        )

        print(f"""
RESULT (extracted "medium" config):
    args.hidden_size = {args.hidden_size}
        Was: 64, medium.hidden_size = 256 -> OVERRIDDEN

    args.num_layers  = {args.num_layers}
        Was: 1, medium.num_layers = 4 -> OVERRIDDEN

    args.dropout     = {args.dropout}
        Not in defaults, medium.dropout = 0.2 -> NEW

OBSERVATION:
    The :key syntax extracts nested configs. You can chain keys:
    preset.json:models:transformer:small
""")
    finally:
        os.unlink(preset_path)

    return args


def example_python_preset():
    """Using a Python preset file"""
    print_header("PYTHON PRESET FILE: Code as configuration")

    print("""
WHAT THIS DOES:
    Python files can be used as presets. The file must define a
    variable called 'config' which is a dictionary.

    This is powerful because you can compute values dynamically!
""")

    # Create a temporary Python preset
    preset_code = '''
# This is a Python preset file
# It must define a 'config' dictionary

import math

config = {
    "learning_rate": 0.001,
    "batch_size": 32,
    "model_config": {
        "hidden_size": 256,
        "num_heads": 8,
    },
    # You can compute values!
    "warmup_steps": 1000,
}
'''

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False
    ) as f:
        f.write(preset_code)
        preset_path = f.name

    print(f"""
PYTHON FILE CONTENTS:
{preset_code}

CODE:
    args = get_parsed_args(
        default_epochs=100,
        preset="{os.path.basename(preset_path)}",  # .py file
    )

EXPECTED BEHAVIOR:
    - Nested dicts become Namespace objects (dot access)
    - args.model_config.hidden_size works!
""")

    pause()
    print("RUNNING NOW...")
    print("-" * 40)

    try:
        args = get_parsed_args(
            default_epochs=100,
            preset=preset_path,
            argv=["script"],
            verbose=False,
        )

        print(f"""
RESULT:
    args.learning_rate = {args.learning_rate}
    args.batch_size    = {args.batch_size}
    args.warmup_steps  = {args.warmup_steps}
    args.epochs        = {args.epochs} (from default)

    args.model_config  = {args.model_config}
        Type: {type(args.model_config).__name__}

    args.model_config.hidden_size = {args.model_config.hidden_size}
    args.model_config.num_heads   = {args.model_config.num_heads}

OBSERVATION:
    Nested dicts are converted to Namespace objects for dot access.
    Python presets can include imports and computed values!
""")
    finally:
        os.unlink(preset_path)

    return args


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("       GET_PARSED_ARGS: PRESETS INTERACTIVE TUTORIAL")
    print("=" * 70)
    print("""
Welcome! This tutorial demonstrates the preset system, which lets you
manage configurations separate from your code.

PRESETS allow you to:
  - Store configurations in files (JSON or Python)
  - Override defaults without changing code
  - Share configurations across scripts
  - Still allow CLI overrides for experiments

PRIORITY ORDER (highest to lowest):
  1. CLI arguments      (--learning_rate 0.1)
  2. Preset values      (from JSON/Python/dict)
  3. Default values     (default_learning_rate=0.001)

Let's begin!
""")

    pause()

    example_dict_preset()
    pause()

    example_json_preset()
    pause()

    example_priority()
    pause()

    example_key_extraction()
    pause()

    example_python_preset()

    print_header("TUTORIAL COMPLETE!")
    print("""
KEY TAKEAWAYS:

  1. DICT PRESET: Pass a dictionary directly
     preset={"learning_rate": 0.01}

  2. JSON PRESET: Load from file
     preset="config.json"

  3. PYTHON PRESET: Use .py files with 'config' dict
     preset="config.py"

  4. PRIORITY: CLI > Preset > Default
     CLI always wins, then preset, then default

  5. KEY EXTRACTION: Use :key syntax for nested configs
     preset="config.json:medium"

  6. AD-HOC ARGUMENTS: Preset can add new arguments
     Anything in preset but not in defaults is added

TRY THESE COMMANDS:
  Create a config.json file and run:
  python example_presets.py --preset config.json
  python example_presets.py --preset config.json --learning_rate 0.1
""")
