#!/usr/bin/env python3
"""
Example 03: Scope Modifiers
===========================

Demonstrates scope modifiers that control resolution behavior:
- ^{{var}} - Force global scope (skip cascade)
- .{{var}} - Current level only (no fallback)
- {{var}}? - Optional (empty string if not found)
- Combinations: ^{{var}}?, .{{var}}?

Directory structure:
    mock_variables/
    ├── greeting.txt      <- 'Hello from global'
    ├── shared.txt        <- 'Shared global value'
    └── myspace/
        ├── greeting.txt  <- 'Hello from myspace'
        └── local_only.txt <- 'Only in myspace'

Run this example:
    PYTHONPATH=src python examples/python_utils/common_objects/variable_manager/file_based_variable_manager/03_scope_modifiers.py
"""

from pathlib import Path

from python_utils.common_objects import FileBasedVariableManager


def get_mock_variables_dir() -> Path:
    return Path(__file__).parent / "mock_variables"


def main():
    base_dir = get_mock_variables_dir()

    # =================================================================
    # CORE CODE
    # =================================================================

    manager = FileBasedVariableManager(base_path=str(base_dir))

    # Normal cascade: space overrides global
    normal = manager.resolve_from_content(
        "{{greeting}}",
        variable_root_space="myspace",
    )

    # Global scope (^): skip cascade, use global directly
    global_scope = manager.resolve_from_content(
        "^{{greeting}}",
        variable_root_space="myspace",
    )

    # Current level (.): only look in current space
    current_level = manager.resolve_from_content(
        ".{{local_only}}",
        variable_root_space="myspace",
    )

    # Current level with missing var
    current_missing = manager.resolve_from_content(
        ".{{shared}}",  # shared.txt only at global
        variable_root_space="myspace",
    )

    # Optional (?): empty string if not found
    optional_found = manager.resolve_from_content(
        "{{greeting}}?",
        variable_root_space="myspace",
    )
    optional_missing = manager.resolve_from_content(
        "{{nonexistent}}?",
        variable_root_space="myspace",
    )

    # Combined: global + optional
    global_optional = manager.resolve_from_content(
        "^{{nonexistent}}?",
        variable_root_space="myspace",
    )

    # =================================================================
    # OUTPUT
    # =================================================================

    print("=" * 70)
    print("Scope Modifiers")
    print("=" * 70)

    print("\n[1] Directory structure")
    print("-" * 50)
    print("    mock_variables/")
    print("    ├── greeting.txt   -> 'Hello from global'")
    print("    ├── shared.txt     -> 'Shared global value'")
    print("    └── myspace/")
    print("        ├── greeting.txt  -> 'Hello from myspace'")
    print("        └── local_only.txt -> 'Only in myspace'")

    print("\n[2] Normal cascade: {{greeting}}")
    print("-" * 50)
    print(f"    Result: {normal.get('greeting', '<not found>')!r}")
    print("    (Space level overrides global)")

    print("\n[3] Global scope: ^{{greeting}}")
    print("-" * 50)
    print(f"    Result: {global_scope.get('greeting', '<not found>')!r}")
    print("    (Skips space, goes directly to global)")

    print("\n[4] Current level only: .{{var}}")
    print("-" * 50)
    print(f"    .{{{{local_only}}}} -> {current_level.get('local_only', '<not found>')!r}")
    print(f"    .{{{{shared}}}}     -> {current_missing.get('shared', '<not in result>')!r}")
    print("    (No fallback to global)")

    print("\n[5] Optional modifier: {{var}}?")
    print("-" * 50)
    print(f"    {{{{greeting}}}}?    -> {optional_found.get('greeting', '<not found>')!r}")
    print(f"    {{{{nonexistent}}}}? -> {optional_missing.get('nonexistent', '<empty>')!r}")

    print("\n[6] Combined: ^{{var}}?")
    print("-" * 50)
    print(f"    ^{{{{nonexistent}}}}? -> {global_optional.get('nonexistent', '<empty>')!r}")

    print("\n" + "=" * 70)
    print("QUICK REFERENCE")
    print("=" * 70)
    print("""
    | Syntax      | Meaning                              |
    |-------------|--------------------------------------|
    | {{var}}     | Cascade: type > space > global       |
    | ^{{var}}    | Global only (skip cascade)           |
    | .{{var}}    | Current level only (no fallback)     |
    | {{var}}?    | Optional (empty if not found)        |
    | ^{{var}}?   | Global + optional                    |
    | .{{var}}?   | Current level + optional             |
""")


if __name__ == "__main__":
    main()
