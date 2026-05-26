"""
Example: Type Handling in get_parsed_args

This interactive example demonstrates how different Python types are handled:
- Boolean flags
- Lists with element type preservation
- Dictionaries from command line
- Tuples

Run with:
    python example_type_handling.py
"""

import os
import subprocess
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


def example_boolean_false_default():
    """Boolean with False default becomes a flag"""
    print_header("BOOLEAN FLAGS: False default -> store_true")

    print("""
WHAT THIS DOES:
    When a boolean argument has a default of False, it becomes a FLAG.
    Just including --debug on the command line sets it to True.
    You don't need to write --debug True.

CODE:
    args = get_parsed_args(
        default_debug=False,      # Flag: --debug to enable
        default_dry_run=False,    # Flag: --dry_run to enable
    )

EXPECTED BEHAVIOR:
    - Without --debug: debug=False (the default)
    - With --debug: debug=True (flag activates it)
""")

    pause()
    print("TEST 1: Without flags (defaults)")
    print("-" * 40)

    args1 = get_parsed_args(
        default_debug=False,
        default_dry_run=False,
        argv=["script"],  # No flags
        verbose=False,
    )

    print(f"""
RESULT (no flags):
    args.debug   = {args1.debug}  <- default False
    args.dry_run = {args1.dry_run}  <- default False
""")

    pause()
    print("TEST 2: With --debug flag")
    print("-" * 40)

    args2 = get_parsed_args(
        default_debug=False,
        default_dry_run=False,
        argv=["script", "--debug"],  # Only debug flag
        verbose=False,
    )

    print(f"""
RESULT (with --debug):
    args.debug   = {args2.debug}  <- CHANGED to True by flag!
    args.dry_run = {args2.dry_run}  <- still False (no flag)

OBSERVATION:
    Notice you don't write --debug True, just --debug.
    This is the "store_true" action in argparse.
""")
    return args2


def example_boolean_true_default():
    """Boolean with True default needs explicit value"""
    print_header("BOOLEAN VALUES: True default -> needs explicit value")

    print("""
WHAT THIS DOES:
    When a boolean argument has a default of True, it works differently.
    You need to pass an explicit value: --verbose false

CODE:
    args = get_parsed_args(
        default_verbose=True,     # Default is True
        default_validate=True,    # Default is True
    )

EXPECTED BEHAVIOR:
    - Without argument: verbose=True (the default)
    - With --verbose false: verbose=False (explicitly set)
    - Accepts: true/false, True/False, 1/0, yes/no
""")

    pause()
    print("TEST 1: Without arguments (defaults)")
    print("-" * 40)

    args1 = get_parsed_args(
        default_verbose=True,
        default_validate=True,
        argv=["script"],
        verbose=False,
    )

    print(f"""
RESULT (defaults):
    args.verbose  = {args1.verbose}  <- default True
    args.validate = {args1.validate}  <- default True
""")

    pause()
    print("TEST 2: Setting --verbose false")
    print("-" * 40)

    args2 = get_parsed_args(
        default_verbose=True,
        default_validate=True,
        argv=["script", "--verbose", "false"],
        verbose=False,
    )

    print(f"""
RESULT (with --verbose false):
    args.verbose  = {args2.verbose}  <- CHANGED to False!
    args.validate = {args2.validate}  <- still True

OBSERVATION:
    For True defaults, you must provide the value: --verbose false
    Accepted values: true/false, True/False, 1/0, yes/no
""")
    return args2


def example_list_handling():
    """List handling with element type inference"""
    print_header("LIST HANDLING: Element type inference")

    print("""
WHAT THIS DOES:
    Lists preserve the element type from the default value.
    The type of the FIRST element determines the type for all elements.

CODE:
    args = get_parsed_args(
        default_layers=[128, 256, 512],    # List of ints
        default_ratios=[0.1, 0.2, 0.3],    # List of floats
        default_names=["a", "b", "c"],     # List of strings
    )

EXPECTED BEHAVIOR:
    - layers: parsed as integers
    - ratios: parsed as floats
    - names: parsed as strings
""")

    pause()
    print("TEST 1: Default list values")
    print("-" * 40)

    args1 = get_parsed_args(
        default_layers=[128, 256, 512],
        default_ratios=[0.1, 0.2, 0.3],
        default_names=["train", "val", "test"],
        argv=["script"],
        verbose=False,
    )

    print(f"""
RESULT (defaults):
    args.layers = {args1.layers}
        Element type: {type(args1.layers[0]).__name__}

    args.ratios = {args1.ratios}
        Element type: {type(args1.ratios[0]).__name__}

    args.names  = {args1.names}
        Element type: {type(args1.names[0]).__name__}
""")

    pause()
    print("TEST 2: Override with CLI list")
    print("-" * 40)

    args2 = get_parsed_args(
        default_layers=[128, 256, 512],
        default_ratios=[0.1, 0.2, 0.3],
        argv=["script", "--layers", "[64, 128, 256, 512]"],
        verbose=False,
    )

    print(f"""
RESULT (with --layers "[64, 128, 256, 512]"):
    args.layers = {args2.layers}
        Element type: {type(args2.layers[0]).__name__}

OBSERVATION:
    Pass lists as JSON-like strings: --layers "[64, 128, 256]"
    Elements are automatically converted to the inferred type.
""")
    return args2


def example_dict_handling():
    """Dict parsing from command line"""
    print_header("DICT HANDLING: JSON-like syntax")

    print("""
WHAT THIS DOES:
    Dictionaries can be passed as JSON-like strings on the command line.
    Use single quotes inside the string for dict values.

CODE:
    args = get_parsed_args(
        default_config={{"learning_rate": 0.001, "batch_size": 32}},
    )

    # CLI: --config "{{'lr': 0.01, 'momentum': 0.9}}"

EXPECTED BEHAVIOR:
    - Dicts are parsed using Python's ast.literal_eval
    - Nested dicts are supported
""")

    pause()
    print("TEST 1: Default dict value")
    print("-" * 40)

    args1 = get_parsed_args(
        default_config={"learning_rate": 0.001, "batch_size": 32},
        argv=["script"],
        verbose=False,
    )

    print(f"""
RESULT (default):
    args.config = {args1.config}
    Type: {type(args1.config).__name__}
""")

    pause()
    print("TEST 2: Override with CLI dict")
    print("-" * 40)

    args2 = get_parsed_args(
        default_config={"learning_rate": 0.001, "batch_size": 32},
        argv=["script", "--config", "{'lr': 0.01, 'momentum': 0.9}"],
        verbose=False,
    )

    print(f"""
RESULT (with --config "{{'lr': 0.01, 'momentum': 0.9}}"):
    args.config = {args2.config}
    Type: {type(args2.config).__name__}

OBSERVATION:
    The dict completely replaces the default.
    Use single quotes for keys/values inside the JSON-like string.
""")
    return args2


def example_tuple_handling():
    """Tuple parsing from command line"""
    print_header("TUPLE HANDLING: Immutable sequences")

    print("""
WHAT THIS DOES:
    Tuples work similarly to lists but remain as tuples after parsing.
    Useful for shapes, coordinates, and immutable sequences.

CODE:
    args = get_parsed_args(
        default_input_shape=(224, 224, 3),
        default_kernel_size=(3, 3),
    )

    # CLI: --input_shape "(128, 128, 1)"

EXPECTED BEHAVIOR:
    - Parsed value is a tuple, not a list
    - Elements are converted to appropriate types
""")

    pause()
    print("TEST 1: Default tuple values")
    print("-" * 40)

    args1 = get_parsed_args(
        default_input_shape=(224, 224, 3),
        default_kernel_size=(3, 3),
        argv=["script"],
        verbose=False,
    )

    print(f"""
RESULT (defaults):
    args.input_shape = {args1.input_shape}
        Type: {type(args1.input_shape).__name__}

    args.kernel_size = {args1.kernel_size}
        Type: {type(args1.kernel_size).__name__}
""")

    pause()
    print("TEST 2: Override with CLI tuple")
    print("-" * 40)

    args2 = get_parsed_args(
        default_input_shape=(224, 224, 3),
        default_kernel_size=(3, 3),
        argv=["script", "--input_shape", "(128, 128, 1)"],
        verbose=False,
    )

    print(f"""
RESULT (with --input_shape "(128, 128, 1)"):
    args.input_shape = {args2.input_shape}
        Type: {type(args2.input_shape).__name__}

OBSERVATION:
    The result is still a tuple (not converted to list).
    This is important when you need immutable sequences.
""")
    return args2


def run_cli_demos():
    """Run actual CLI demonstrations using subprocess."""
    print_header("LIVE CLI DEMONSTRATIONS")

    print("""
Now let's run REAL command-line examples with different types!
""")

    # Get the project root
    script_path = os.path.abspath(__file__)
    project_root = os.path.dirname(script_path)
    for _ in range(4):
        project_root = os.path.dirname(project_root)

    # Create a mini demo script
    demo_script = '''
import sys
sys.path.insert(0, "src")
from python_utils.common_utils.arg_utils.arg_parse import get_parsed_args

args = get_parsed_args(
    default_debug=False,
    default_verbose=True,
    default_layers=[128, 256],
    default_config={"lr": 0.001},
    default_shape=(224, 224),
    verbose=False,
)
print(f"  debug   = {args.debug} (type: {type(args.debug).__name__})")
print(f"  verbose = {args.verbose} (type: {type(args.verbose).__name__})")
print(f"  layers  = {args.layers} (type: {type(args.layers).__name__})")
print(f"  config  = {args.config} (type: {type(args.config).__name__})")
print(f"  shape   = {args.shape} (type: {type(args.shape).__name__})")
'''

    demos = [
        {
            "title": "Demo 1: No arguments (defaults)",
            "args": [],
            "expected": "debug=False, verbose=True, layers=[128,256], etc."
        },
        {
            "title": "Demo 2: Boolean flag --debug",
            "args": ["--debug"],
            "expected": "debug becomes True (just include the flag, no value)"
        },
        {
            "title": "Demo 3: Boolean value --verbose false",
            "args": ["--verbose", "false"],
            "expected": "verbose becomes False (must provide explicit value)"
        },
        {
            "title": "Demo 4: List --layers \"[64, 128, 256, 512]\"",
            "args": ["--layers", "[64, 128, 256, 512]"],
            "expected": "layers becomes [64, 128, 256, 512] (parsed as list of ints)"
        },
        {
            "title": "Demo 5: Dict --config \"{'lr': 0.01, 'momentum': 0.9}\"",
            "args": ["--config", "{'lr': 0.01, 'momentum': 0.9}"],
            "expected": "config becomes {'lr': 0.01, 'momentum': 0.9}"
        },
        {
            "title": "Demo 6: Tuple --shape \"(128, 128, 3)\"",
            "args": ["--shape", "(128, 128, 3)"],
            "expected": "shape becomes (128, 128, 3) (stays as tuple)"
        },
    ]

    for demo in demos:
        pause()
        print(f"\n{demo['title']}")
        print("-" * 50)

        cmd_display = " ".join(demo["args"]) if demo["args"] else "(no arguments)"
        print(f"COMMAND: python script.py {cmd_display}")
        print(f"EXPECTED: {demo['expected']}")
        print(f"\nRUNNING...")
        print("-" * 30)

        cmd = [sys.executable, "-c", demo_script] + demo["args"]
        result = subprocess.run(
            cmd,
            cwd=project_root,
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            print("RESULT:")
            print(result.stdout)
        else:
            print(f"ERROR: {result.stderr}")

    print_header("CLI DEMOS COMPLETE!")
    print("""
You've now seen how different types are handled from the command line!

Key syntax:
  --debug              (flag, no value)
  --verbose false      (boolean with value)
  --layers "[1,2,3]"   (list as string)
  --config "{'a': 1}"  (dict as string)
  --shape "(1,2,3)"    (tuple as string)
""")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("       GET_PARSED_ARGS: TYPE HANDLING INTERACTIVE TUTORIAL")
    print("=" * 70)
    print("""
Welcome! This tutorial demonstrates how get_parsed_args handles different
Python types. Type inference is automatic based on default values.

Each section will show:
  1. WHAT the code does
  2. The CODE being executed
  3. EXPECTED BEHAVIOR
  4. Multiple TESTS to demonstrate the behavior
  5. OBSERVATIONS for you to verify

Let's begin!
""")

    pause()

    example_boolean_false_default()
    pause()

    example_boolean_true_default()
    pause()

    example_list_handling()
    pause()

    example_dict_handling()
    pause()

    example_tuple_handling()

    print_header("TUTORIAL COMPLETE!")
    print("""
KEY TAKEAWAYS:

  1. BOOLEAN (False default): Becomes a flag
     --debug  (no value needed, sets to True)

  2. BOOLEAN (True default): Needs explicit value
     --verbose false  (must provide the value)

  3. LISTS: Element type from first element
     --layers "[64, 128, 256]"  (JSON-like syntax)

  4. DICTS: JSON-like syntax with single quotes
     --config "{'lr': 0.01, 'bs': 64}"

  5. TUPLES: Same as lists, but stays tuple
     --shape "(224, 224, 3)"
""")

    pause()
    run_cli_demos()

