"""
Example: Interactive Mode for get_parsed_args

This example demonstrates the interactive argument collection feature.
Interactive mode allows you to collect argument values through prompts
instead of command-line arguments.

Features:
- Jupyter/IPython: Interactive widgets (ipywidgets)
- Terminal with questionary: Rich terminal prompts with validation
- Terminal fallback: Basic input() prompts

Run with:
    python example_interactive.py
"""

import sys
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


def example_basic_interactive():
    """Basic interactive mode example"""
    print_header("EXAMPLE 1: Basic Interactive Mode")

    print("""
WHAT THIS DOES:
    When interactive=True, get_parsed_args will prompt you interactively
    for each argument value instead of reading from command-line arguments.

    This is useful for:
    - Jupyter notebooks where CLI arguments aren't natural
    - Scripts where you want guided configuration
    - Exploratory data analysis sessions

CODE:
    args = get_parsed_args(
        ("learning_rate/lr", 0.001, "Learning rate for optimizer"),
        ("batch_size/bs", 32, "Training batch size"),
        ("epochs/e", 100, "Number of training epochs"),
        ("model_name/m", "transformer", "Model architecture"),
        ("debug/d", False, "Enable debug mode"),
        interactive=True,
        verbose=False,
    )

EXPECTED BEHAVIOR:
    You'll see prompts for each argument with their default values.
    - For Jupyter: Interactive widgets with checkboxes, text fields, etc.
    - For terminal (with questionary): Rich colored prompts
    - For terminal (basic): Simple input() prompts

    Just press Enter to accept the default, or type a new value.
""")

    pause()

    print("\nRUNNING INTERACTIVE COLLECTION:\n")

    args = get_parsed_args(
        ("learning_rate/lr", 0.001, "Learning rate for optimizer"),
        ("batch_size/bs", 32, "Training batch size"),
        ("epochs/e", 100, "Number of training epochs"),
        ("model_name/m", "transformer", "Model architecture"),
        ("debug/d", False, "Enable debug mode"),
        interactive=True,
        verbose=False,
        argv=["script"],  # Prevent CLI parsing
    )

    print("\n" + "=" * 70)
    print("COLLECTED VALUES:")
    print("=" * 70)
    print(f"  learning_rate: {args.learning_rate}")
    print(f"  batch_size: {args.batch_size}")
    print(f"  epochs: {args.epochs}")
    print(f"  model_name: {args.model_name}")
    print(f"  debug: {args.debug}")
    print("=" * 70)

    pause()


def example_interactive_with_types():
    """Interactive mode with different data types"""
    print_header("EXAMPLE 2: Interactive Mode with Various Types")

    print("""
WHAT THIS DOES:
    Interactive mode supports all argument types:
    - Booleans: Checkbox/confirm prompts
    - Numbers: Validated numeric input
    - Strings: Text input
    - Lists: Parsed from string representation
    - Dicts: Parsed from string representation

CODE:
    args = get_parsed_args(
        ("layers", [128, 256, 512], "Hidden layer sizes"),
        ("dropout_rates", [0.1, 0.2, 0.3], "Dropout rates per layer"),
        ("config", {'lr': 0.001, 'momentum': 0.9}, "Optimizer config"),
        ("dataset_path", "/data/train", "Path to training data"),
        ("use_gpu", True, "Enable GPU acceleration"),
        interactive=True,
        verbose=False,
    )

EXPECTED BEHAVIOR:
    - Lists and dicts are shown as strings, you can edit them
    - Validation ensures proper Python literal syntax
    - Booleans show as yes/no or checkbox
""")

    pause()

    print("\nRUNNING INTERACTIVE COLLECTION:\n")

    args = get_parsed_args(
        ("layers", [128, 256, 512], "Hidden layer sizes"),
        ("dropout_rates", [0.1, 0.2, 0.3], "Dropout rates per layer"),
        ("config", {'lr': 0.001, 'momentum': 0.9}, "Optimizer config"),
        ("dataset_path", "/data/train", "Path to training data"),
        ("use_gpu", True, "Enable GPU acceleration"),
        interactive=True,
        verbose=False,
        argv=["script"],
    )

    print("\n" + "=" * 70)
    print("COLLECTED VALUES:")
    print("=" * 70)
    print(f"  layers: {args.layers}")
    print(f"  dropout_rates: {args.dropout_rates}")
    print(f"  config: {args.config}")
    print(f"  dataset_path: {args.dataset_path}")
    print(f"  use_gpu: {args.use_gpu}")
    print("=" * 70)

    pause()


def example_interactive_with_preset():
    """Interactive mode combined with presets"""
    print_header("EXAMPLE 3: Interactive Mode with Preset")

    print("""
WHAT THIS DOES:
    You can combine interactive mode with presets!
    Preset values become the defaults shown in the interactive prompts.

    Priority: User input > Preset values > Default values

CODE:
    preset = {
        "learning_rate": 0.01,  # Override default
        "batch_size": 64,       # Override default
    }

    args = get_parsed_args(
        ("learning_rate", 0.001, "Learning rate"),
        ("batch_size", 32, "Batch size"),
        ("epochs", 100, "Number of epochs"),
        preset=preset,
        interactive=True,
        verbose=False,
    )

EXPECTED BEHAVIOR:
    - learning_rate will show 0.01 as default (from preset)
    - batch_size will show 64 as default (from preset)
    - epochs will show 100 as default (from code)
""")

    pause()

    print("\nRUNNING INTERACTIVE COLLECTION WITH PRESET:\n")

    preset = {
        "learning_rate": 0.01,
        "batch_size": 64,
    }

    args = get_parsed_args(
        ("learning_rate", 0.001, "Learning rate"),
        ("batch_size", 32, "Batch size"),
        ("epochs", 100, "Number of epochs"),
        preset=preset,
        interactive=True,
        verbose=False,
        argv=["script"],
    )

    print("\n" + "=" * 70)
    print("COLLECTED VALUES:")
    print("=" * 70)
    print(f"  learning_rate: {args.learning_rate}")
    print(f"  batch_size: {args.batch_size}")
    print(f"  epochs: {args.epochs}")
    print("=" * 70)

    pause()


def example_jupyter_usage():
    """Example for Jupyter notebooks"""
    print_header("EXAMPLE 4: Usage in Jupyter Notebooks")

    print("""
WHAT THIS DOES:
    In Jupyter notebooks, interactive mode automatically uses ipywidgets
    to create a nice UI with:
    - Text fields for strings and numbers
    - Checkboxes for booleans
    - Info tooltips for descriptions
    - A submit button to apply configuration

JUPYTER CODE:
    from python_utils.common_utils.arg_utils.arg_parse import get_parsed_args

    # In a Jupyter cell:
    args = get_parsed_args(
        ("learning_rate", 0.001, "Learning rate for optimizer"),
        ("batch_size", 32, "Training batch size"),
        ("model_name", "resnet50", "Model architecture to use"),
        ("use_pretrained", True, "Use pretrained weights"),
        interactive=True,
    )

    # The widgets will appear in the notebook
    # After you configure and click submit, the values are available:
    print(f"Training with lr={args.learning_rate}, batch={args.batch_size}")

TERMINAL EQUIVALENT:
    When running in a terminal (like now), you get text-based prompts instead.
    Try installing questionary for a better terminal experience:
        pip install questionary
""")

    pause()


def main():
    """Run all examples"""
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║              Interactive Mode Examples for get_parsed_args           ║
║                                                                      ║
║  This tutorial demonstrates how to use interactive argument          ║
║  collection instead of command-line arguments.                       ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝

NOTE: Interactive mode requires user input. Each example will prompt you
      for values. Just press Enter to use the default values shown.

RECOMMENDED: Install questionary for better terminal experience:
      pip install questionary

FOR JUPYTER: Install ipywidgets for interactive widgets:
      pip install ipywidgets
""")

    pause()

    # Run examples
    example_basic_interactive()
    example_interactive_with_types()
    example_interactive_with_preset()
    example_jupyter_usage()

    print_header("TUTORIAL COMPLETE")
    print("""
You've seen how to use interactive mode with get_parsed_args!

KEY TAKEAWAYS:
  1. Add interactive=True to enable interactive collection
  2. Works in Jupyter (ipywidgets) and terminal (questionary or input)
  3. Supports all data types: strings, numbers, bools, lists, dicts
  4. Combines with presets for better defaults
  5. Great for notebooks and exploratory scripts

NEXT STEPS:
  - Try it in your own scripts
  - Use with Jupyter notebooks for interactive configuration
  - Combine with preset files for common configurations

For more examples, check out:
  - example_basic_usage.py
  - example_presets.py
  - example_type_handling.py
""")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTutorial interrupted by user.")
        sys.exit(0)
