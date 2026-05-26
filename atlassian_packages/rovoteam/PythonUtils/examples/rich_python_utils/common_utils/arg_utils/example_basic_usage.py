"""
Example: Basic Usage of get_parsed_args

This interactive example demonstrates the different input formats for defining arguments.
Each example explains what will happen, shows the code, and lets you observe the result.

Run with:
    python example_basic_usage.py
"""

import os
import subprocess
import sys

from resolve_path import resolve_path
resolve_path()  # Add project src to sys.path

from python_utils.common_utils.arg_utils.arg_parse import (
    get_parsed_args,
    ArgInfo,
)


def pause():
    """Wait for user to press Enter."""
    input("\n[Press Enter to continue...]\n")


def print_header(title):
    """Print a formatted section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def example_format_1_kwargs():
    """Format 1: Using default_xxx kwargs (simplest)"""
    print_header("FORMAT 1: default_xxx keyword arguments")

    print("""
WHAT THIS DOES:
    The simplest way to define arguments is using keyword arguments with the
    'default_' prefix. The function strips this prefix to create the argument name.

CODE:
    args = get_parsed_args(
        default_learning_rate=0.001,
        default_batch_size=32,
        default_model_name="transformer",
    )

EXPECTED BEHAVIOR:
    - 'default_learning_rate' becomes argument 'learning_rate' with default 0.001
    - 'default_batch_size' becomes argument 'batch_size' with default 32
    - 'default_model_name' becomes argument 'model_name' with default "transformer"
    - Short names are auto-generated: 'lr', 'bs', 'mn'
""")

    pause()

    # Get script path for subprocess demonstration
    script_path = os.path.abspath(__file__)
    project_root = os.path.dirname(script_path)
    for _ in range(4):
        project_root = os.path.dirname(project_root)

    # Create demo script
    demo_code = '''
import sys
sys.path.insert(0, "src")
from python_utils.common_utils.arg_utils.arg_parse import get_parsed_args

args = get_parsed_args(
    default_learning_rate=0.001,
    default_batch_size=32,
    default_model_name="transformer",
    verbose=False,
)
print(f"  learning_rate = {args.learning_rate}")
print(f"  batch_size    = {args.batch_size}")
print(f"  model_name    = {args.model_name}")
'''

    print("TEST 1: Running with NO arguments (uses defaults)")
    print("-" * 60)
    result = subprocess.run([sys.executable, "-c", demo_code], cwd=project_root, capture_output=True, text=True)
    print(result.stdout)

    pause()
    print("\nTEST 2: Running with --learning_rate 0.05")
    print("-" * 60)
    result = subprocess.run([sys.executable, "-c", demo_code, "--learning_rate", "0.05"], cwd=project_root, capture_output=True, text=True)
    print(result.stdout)
    print("OBSERVATION: learning_rate changed from 0.001 to 0.05 (CLI override!)")

    pause()
    print("\nTEST 3: Running with --learning_rate 0.05 --batch_size 128")
    print("-" * 60)
    result = subprocess.run([sys.executable, "-c", demo_code, "--learning_rate", "0.05", "--batch_size", "128"], cwd=project_root, capture_output=True, text=True)
    print(result.stdout)
    print("OBSERVATION: Both values overridden by CLI!")



def example_format_2_tuples():
    """Format 2: Using 2-tuples (name, default)"""
    print_header("FORMAT 2: 2-tuples (name, default_value)")

    print("""
WHAT THIS DOES:
    You can define arguments as positional tuples. This allows you to specify
    custom short names using the 'full_name/short_name' syntax.

CODE:
    args = get_parsed_args(
        ("learning_rate/lr", 0.001),   # explicit short name 'lr'
        ("batch_size/bs", 32),          # explicit short name 'bs'
        ("model_name", "transformer"),  # auto short name 'mn'
    )

EXPECTED BEHAVIOR:
    - 'learning_rate' with short name 'lr' (explicitly set)
    - 'batch_size' with short name 'bs' (explicitly set)
    - 'model_name' with auto-generated short name 'mn'
""")

    pause()
    print("RUNNING NOW...")
    print("-" * 40)

    args = get_parsed_args(
        ("learning_rate/lr", 0.001),
        ("batch_size/bs", 32),
        ("model_name", "transformer"),
        verbose=False,
    )

    print(f"""
RESULT:
    args.learning_rate = {args.learning_rate}
    args.batch_size    = {args.batch_size}
    args.model_name    = '{args.model_name}'

OBSERVATION:
    Same result as Format 1, but now you can use short names on command line:
    python example_basic_usage.py -lr 0.01 -bs 64
""")
    return args


def example_format_3_with_description():
    """Format 3: Using 3-tuples (name, default, description)"""
    print_header("FORMAT 3: 3-tuples (name, default, description)")

    print("""
WHAT THIS DOES:
    Add a description as the third element. This description appears in --help.

CODE:
    args = get_parsed_args(
        ("learning_rate/lr", 0.001, "Learning rate for optimizer"),
        ("batch_size/bs", 32, "Training batch size"),
        ("epochs/e", 100, "Number of training epochs"),
    )

EXPECTED BEHAVIOR:
    - Same as Format 2, but with help text for each argument
    - Run with --help to see the descriptions
""")

    pause()
    print("RUNNING NOW...")
    print("-" * 40)

    args = get_parsed_args(
        ("learning_rate/lr", 0.001, "Learning rate for optimizer"),
        ("batch_size/bs", 32, "Training batch size"),
        ("epochs/e", 100, "Number of training epochs"),
        verbose=False,
    )

    print(f"""
RESULT:
    args.learning_rate = {args.learning_rate}
    args.batch_size    = {args.batch_size}
    args.epochs        = {args.epochs}

OBSERVATION:
    Try running: python example_basic_usage.py --help
    to see the descriptions in the help text.
""")
    return args


def example_format_7_arginfo():
    """Format 7: Using ArgInfo namedtuple (most explicit)"""
    print_header("FORMAT 7: ArgInfo namedtuple (most explicit)")

    print("""
WHAT THIS DOES:
    The ArgInfo namedtuple provides the most explicit way to define arguments.
    All fields are named, making the code self-documenting.

CODE:
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

EXPECTED BEHAVIOR:
    - Complete control over all argument properties
    - Recommended for complex configurations
""")

    pause()
    print("RUNNING NOW...")
    print("-" * 40)

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
        ArgInfo(
            full_name="model_name",
            default_value="transformer",
        ),
        verbose=False,
    )

    print(f"""
RESULT:
    args.learning_rate = {args.learning_rate}
    args.batch_size    = {args.batch_size}
    args.model_name    = '{args.model_name}'

OBSERVATION:
    ArgInfo is best for production code where clarity is important.
""")
    return args


def example_cli_override():
    """Demonstrate CLI override of defaults"""
    print_header("CLI OVERRIDE DEMO")

    print("""
WHAT THIS DOES:
    This demonstrates how command-line arguments override defaults.
    We'll simulate passing --learning_rate 0.05 --batch_size 128

CODE:
    args = get_parsed_args(
        default_learning_rate=0.001,  # DEFAULT: 0.001
        default_batch_size=32,        # DEFAULT: 32
        default_epochs=100,           # DEFAULT: 100 (not overridden)
        argv=["script", "--learning_rate", "0.05", "--batch_size", "128"],
    )

EXPECTED BEHAVIOR:
    - learning_rate: 0.001 -> 0.05 (OVERRIDDEN by CLI)
    - batch_size: 32 -> 128 (OVERRIDDEN by CLI)
    - epochs: 100 (UNCHANGED, no CLI override)
""")

    pause()
    print("RUNNING NOW...")
    print("-" * 40)

    args = get_parsed_args(
        default_learning_rate=0.001,
        default_batch_size=32,
        default_epochs=100,
        argv=["script", "--learning_rate", "0.05", "--batch_size", "128"],
        verbose=False,
    )

    print(f"""
RESULT:
    args.learning_rate = {args.learning_rate}  (was 0.001, CLI set 0.05)
    args.batch_size    = {args.batch_size}  (was 32, CLI set 128)
    args.epochs        = {args.epochs}  (unchanged, default)

OBSERVATION:
    CLI arguments have HIGHER priority than defaults.
    Only the arguments you specify on CLI are changed.
""")
    return args


def run_cli_demos():
    """Run actual CLI demonstrations using subprocess."""
    print_header("LIVE CLI DEMONSTRATIONS")

    print("""
Now let's run REAL command-line examples! We'll execute this script
with different arguments and show you what happens.
""")

    # Get the script path and project root
    script_path = os.path.abspath(__file__)
    project_root = os.path.dirname(script_path)
    for _ in range(4):  # Go up to SciencePythonUtils root
        project_root = os.path.dirname(project_root)

    # Create a mini demo script
    demo_script = '''
import sys
sys.path.insert(0, "src")
from python_utils.common_utils.arg_utils.arg_parse import get_parsed_args

args = get_parsed_args(
    ("learning_rate/lr", 0.001),
    ("batch_size/bs", 32),
    ("model_name/mn", "transformer"),
    verbose=False,
)
print(f"  learning_rate = {args.learning_rate}")
print(f"  batch_size    = {args.batch_size}")
print(f"  model_name    = {args.model_name}")
'''

    demos = [
        {
            "title": "Demo 1: No arguments (use defaults)",
            "args": [],
            "expected": "All values use defaults: lr=0.001, bs=32, mn='transformer'"
        },
        {
            "title": "Demo 2: Override learning_rate with --learning_rate",
            "args": ["--learning_rate", "0.05"],
            "expected": "learning_rate changes to 0.05, others stay default"
        },
        {
            "title": "Demo 3: Use short names -lr and -bs",
            "args": ["-lr", "0.01", "-bs", "128"],
            "expected": "learning_rate=0.01, batch_size=128, model_name=default"
        },
        {
            "title": "Demo 4: Override all three arguments",
            "args": ["--learning_rate", "0.1", "--batch_size", "256", "--model_name", "resnet"],
            "expected": "All three values changed from CLI"
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

        # Run the demo
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
You've now seen how command-line arguments work in practice!

Remember:
  - Use --full_name VALUE for long names
  - Use -short VALUE for short names
  - CLI arguments ALWAYS override defaults
""")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("       GET_PARSED_ARGS: BASIC USAGE INTERACTIVE TUTORIAL")
    print("=" * 70)
    print("""
Welcome! This tutorial will walk you through the different ways to define
command-line arguments using get_parsed_args.

Each section will:
  1. Explain WHAT the code does
  2. Show the CODE being executed
  3. Describe the EXPECTED BEHAVIOR
  4. Run and show the RESULT
  5. Provide OBSERVATIONS for you to verify

Let's begin!
""")

    pause()

    example_format_1_kwargs()
    pause()

    example_format_2_tuples()
    pause()

    example_format_3_with_description()
    pause()

    example_format_7_arginfo()
    pause()

    example_cli_override()

    print_header("TUTORIAL COMPLETE!")
    print("""
KEY TAKEAWAYS:

  1. SIMPLEST: Use default_xxx kwargs for quick scripts
     get_parsed_args(default_learning_rate=0.001)

  2. WITH SHORT NAMES: Use tuples with name/short syntax
     get_parsed_args(("learning_rate/lr", 0.001))

  3. WITH DESCRIPTIONS: Add third element for help text
     get_parsed_args(("learning_rate/lr", 0.001, "The learning rate"))

  4. MOST EXPLICIT: Use ArgInfo for production code
     get_parsed_args(ArgInfo(full_name="learning_rate", ...))

  5. CLI PRIORITY: Command-line arguments override defaults
""")

    pause()
    run_cli_demos()
