#!/usr/bin/env python3
"""
Example 04: Variable Composition
================================

Demonstrates how variables can reference other variables:
- Simple composition: {{connection_string}} contains {{host}}, {{port}}
- Multi-level: {{full_config}} references {{connection_string}}
- Circular reference detection

Directory structure:
    mock_variables/
    ├── database_host.txt       <- 'localhost'
    ├── database_port.txt       <- '5432'
    ├── database.txt            <- 'mydb'
    ├── connection_string.txt   <- 'postgresql://{{database_host}}:{{database_port}}/{{database}}'
    ├── full_config.txt         <- 'Connection: {{connection_string}}\nTimeout: 30s'
    └── circular/
        ├── a.txt               <- 'A references {{circular_b}}'
        └── b.txt               <- 'B references {{circular_a}}'

Run this example:
    PYTHONPATH=src python examples/python_utils/common_objects/variable_manager/file_based_variable_manager/04_variable_composition.py
"""

from pathlib import Path

from python_utils.common_objects import (
    FileBasedVariableManager,
    CircularReferenceError,
)


def get_mock_variables_dir() -> Path:
    return Path(__file__).parent / "mock_variables"


def main():
    base_dir = get_mock_variables_dir()

    # =================================================================
    # CORE CODE
    # =================================================================

    manager = FileBasedVariableManager(base_path=str(base_dir))

    # Simple composition
    simple = manager.resolve_from_content("{{connection_string}}")

    # Multi-level composition
    multi = manager.resolve_from_content("{{full_config}}")

    # Circular reference detection
    circular_error = None
    try:
        manager.resolve_from_content("{{circular_a}}")
    except CircularReferenceError as e:
        circular_error = e

    # =================================================================
    # OUTPUT
    # =================================================================

    print("=" * 70)
    print("Variable Composition")
    print("=" * 70)

    print("\n[1] Variable files")
    print("-" * 50)
    print("    database_host.txt     -> 'localhost'")
    print("    database_port.txt     -> '5432'")
    print("    database.txt          -> 'mydb'")
    print("    connection_string.txt -> 'postgresql://{{database_host}}:{{database_port}}/{{database}}'")
    print("    full_config.txt       -> 'Connection: {{connection_string}}\\nTimeout: 30s\\n...'")

    print("\n[2] Simple composition: {{connection_string}}")
    print("-" * 50)
    print(f"    Result: {simple.get('connection_string', '')!r}")

    print("\n[3] Multi-level composition: {{full_config}}")
    print("-" * 50)
    result = multi.get('full_config', '')
    for line in result.strip().split('\n'):
        print(f"    {line}")

    print("\n[4] Circular reference detection")
    print("-" * 50)
    print("    circular/a.txt -> 'A references {{circular_b}}'")
    print("    circular/b.txt -> 'B references {{circular_a}}'")
    print()
    if circular_error:
        print(f"    CircularReferenceError raised!")
        print(f"    {circular_error}")

    print("\n" + "=" * 70)
    print("QUICK REFERENCE")
    print("=" * 70)
    print("""
    # Composition happens in resolve_from_content()
    vars = manager.resolve_from_content("{{composed_var}}")

    # Variable files can contain {{other_var}} references
    # connection.txt: "postgresql://{{host}}:{{port}}/{{db}}"

    # Scope modifiers work in composition too
    # config.txt: "Host: ^{{global_host}}, Local: .{{local}}"

    # Circular references raise CircularReferenceError
    from python_utils.common_objects import CircularReferenceError
""")


if __name__ == "__main__":
    main()
