#!/usr/bin/env python3
"""
Example 01: FileBasedVariableManager Basic Usage
=================================================

Demonstrates basic usage of FileBasedVariableManager:
- Dict-like access: manager['key'], manager.get('key', default)
- Underscore inference: config_timeout -> config/timeout.txt
- Iteration and membership testing

Run this example:
    PYTHONPATH=src python examples/python_utils/common_objects/variable_manager/file_based_variable_manager/01_basic_usage.py
"""

from pathlib import Path

from python_utils.common_objects import (
    FileBasedVariableManager,
    KeyDiscoveryMode,
)


def get_mock_variables_dir() -> Path:
    """Get the path to the mock_variables directory."""
    return Path(__file__).parent / "mock_variables"


def main():
    base_dir = get_mock_variables_dir()

    # =================================================================
    # CORE CODE
    # =================================================================

    # 1. Basic creation
    manager = FileBasedVariableManager(base_path=str(base_dir))

    # 2. Dict-like access
    db_host = manager["database_host"]
    db_port = manager["database_port"]
    app_name = manager.get("app_name")
    missing = manager.get("missing", "default")

    # 3. Underscore split inference: config_timeout -> config/timeout.txt
    timeout = manager["config_timeout"]
    retries = manager["config_retries"]
    debug = manager["config_debug"]

    # 4. Iteration and membership (with EAGER mode)
    manager_eager = FileBasedVariableManager(
        base_path=str(base_dir),
        key_discovery_mode=KeyDiscoveryMode.EAGER,
    )
    has_host = "database_host" in manager_eager
    has_missing = "missing_key" in manager_eager
    key_count = len(manager_eager)

    # =================================================================
    # OUTPUT
    # =================================================================

    print("=" * 70)
    print("FileBasedVariableManager Basic Usage")
    print("=" * 70)

    print("\n[1] Basic creation and dict-like access")
    print("-" * 50)
    print(f"    manager = FileBasedVariableManager(base_path='{base_dir}')")
    print()
    print(f"    manager['database_host']          -> {db_host!r}")
    print(f"    manager['database_port']          -> {db_port!r}")
    print(f"    manager.get('app_name')           -> {app_name!r}")
    print(f"    manager.get('missing', 'default') -> {missing!r}")

    print("\n[2] Underscore split inference")
    print("-" * 50)
    print("    'config_timeout' -> config/timeout.txt")
    print("    'config_retries' -> config/retries.txt")
    print()
    print(f"    manager['config_timeout'] -> {timeout!r}")
    print(f"    manager['config_retries'] -> {retries!r}")
    print(f"    manager['config_debug']   -> {debug!r}")

    print("\n[3] Iteration and membership (KeyDiscoveryMode.EAGER)")
    print("-" * 50)
    print(f"    'database_host' in manager -> {has_host}")
    print(f"    'missing_key' in manager   -> {has_missing}")
    print(f"    len(manager)               -> {key_count}")

    print("\n" + "=" * 70)
    print("QUICK REFERENCE")
    print("=" * 70)
    print("""
    from python_utils.common_objects import FileBasedVariableManager

    manager = FileBasedVariableManager(base_path="/config")

    # Dict-like access
    value = manager['key']
    value = manager.get('key', 'default')
    'key' in manager

    # Iteration
    for key in manager:
        print(key, manager[key])
""")


if __name__ == "__main__":
    main()
