#!/usr/bin/env python3
"""
Example 02: Cascade and Composition
====================================

Demonstrates two key features working together:

1. CASCADE RESOLUTION: More specific levels override less specific
   variable_type > variable_root_space > global

2. COMPOSITION: Variables can reference other variables
   connection_string.txt -> 'postgresql://{{database_host}}:{{database_port}}/{{database}}'

Both features can be configured at:
- Class level: FileBasedVariableManager(variable_root_space="production")
- Method level: manager.get("key", cascade=True, variable_root_space="staging")

Directory structure:
    mock_variables/
    ├── database_host.txt           <- 'localhost' (global)
    ├── database_port.txt           <- '5432'
    ├── connection_string.txt       <- 'postgresql://{{database_host}}:{{database_port}}/{{database}}'
    ├── production/
    │   ├── database_host.txt       <- 'prod-db.example.com' (space)
    │   ├── database_port.txt       <- '5433'
    │   └── api/
    │       └── database_host.txt   <- 'prod-api-db.example.com' (type)
    └── staging/
        └── database_host.txt       <- 'staging-db.example.com'

Run this example:
    PYTHONPATH=src python examples/python_utils/common_objects/variable_manager/file_based_variable_manager/02_cascade_and_composition.py
"""

from pathlib import Path

from python_utils.common_objects import (
    FileBasedVariableManager,
    VariableManagerConfig,
)


def get_mock_variables_dir() -> Path:
    return Path(__file__).parent / "mock_variables"


def main():
    base_dir = get_mock_variables_dir()

    # =================================================================
    # CORE CODE
    # =================================================================

    # --- Class-level cascade ---
    # No cascade (default)
    manager = FileBasedVariableManager(base_path=str(base_dir))
    host_global = manager["database_host"]

    # With class-level cascade
    manager_prod = FileBasedVariableManager(
        base_path=str(base_dir),
        variable_root_space="production",
    )
    host_prod = manager_prod["database_host"]

    # With class-level cascade + type
    manager_api = FileBasedVariableManager(
        base_path=str(base_dir),
        variable_root_space="production",
        variable_type="api",
    )
    host_api = manager_api["database_host"]

    # --- Method-level override ---
    # Override: cascade=False ignores class-level settings
    host_override_global = manager_prod.get("database_host", cascade=False)

    # Override: different space
    host_override_staging = manager_prod.get(
        "database_host", variable_root_space="staging"
    )

    # --- Composition ---
    # Default compose=True (from config.compose_on_access)
    conn_global = manager["connection_string"]
    conn_prod = manager_prod["connection_string"]

    # Explicit compose=False
    conn_raw = manager.get("connection_string", compose=False)

    # --- Config to disable composition ---
    config_no_compose = VariableManagerConfig(compose_on_access=False)
    manager_raw = FileBasedVariableManager(
        base_path=str(base_dir), config=config_no_compose
    )
    conn_via_config = manager_raw["connection_string"]

    # =================================================================
    # OUTPUT
    # =================================================================

    print("=" * 70)
    print("Cascade and Composition")
    print("=" * 70)

    print("\n" + "=" * 70)
    print("PART 1: CLASS-LEVEL CASCADE")
    print("=" * 70)

    print("\n[1] No cascade (default)")
    print("-" * 50)
    print("    manager = FileBasedVariableManager(base_path=...)")
    print(f"    manager['database_host'] = {host_global!r}")

    print("\n[2] With class-level variable_root_space")
    print("-" * 50)
    print("    manager_prod = FileBasedVariableManager(")
    print("        base_path=...,")
    print("        variable_root_space='production',")
    print("    )")
    print(f"    manager_prod['database_host'] = {host_prod!r}")

    print("\n[3] With class-level variable_root_space + variable_type")
    print("-" * 50)
    print("    manager_api = FileBasedVariableManager(")
    print("        base_path=...,")
    print("        variable_root_space='production',")
    print("        variable_type='api',")
    print("    )")
    print(f"    manager_api['database_host'] = {host_api!r}")

    print("\n" + "=" * 70)
    print("PART 2: METHOD-LEVEL OVERRIDE")
    print("=" * 70)

    print("\n[4] cascade=False (ignore class settings)")
    print("-" * 50)
    print(f"    manager_prod.get('database_host', cascade=False)")
    print(f"    -> {host_override_global!r}  (global)")

    print("\n[5] Override variable_root_space")
    print("-" * 50)
    print(f"    manager_prod.get('database_host', variable_root_space='staging')")
    print(f"    -> {host_override_staging!r}")

    print("\n" + "=" * 70)
    print("PART 3: COMPOSITION")
    print("=" * 70)

    print("\n[6] Composition uses cascade settings")
    print("-" * 50)
    print(f"    manager['connection_string']")
    print(f"    -> {conn_global!r}")
    print()
    print(f"    manager_prod['connection_string']")
    print(f"    -> {conn_prod!r}")

    print("\n[7] compose=False returns raw content")
    print("-" * 50)
    print(f"    manager.get('connection_string', compose=False)")
    print(f"    -> {conn_raw!r}")

    print("\n[8] Config compose_on_access=False")
    print("-" * 50)
    print("    config = VariableManagerConfig(compose_on_access=False)")
    print(f"    manager_raw['connection_string'] = {conn_via_config!r}")

    print("\n" + "=" * 70)
    print("QUICK REFERENCE")
    print("=" * 70)
    print("""
    # Class-level cascade (used by [] and get())
    manager = FileBasedVariableManager(
        base_path="/config",
        variable_root_space="production",
        variable_type="api",
    )
    manager["key"]  # Uses production/api cascade

    # Method-level control
    manager.get("key", cascade=False)  # Global only
    manager.get("key", variable_root_space="staging")  # Override space
    manager.get("key", compose=False)  # Raw content

    # Config-level composition control
    config = VariableManagerConfig(compose_on_access=False)
    manager = FileBasedVariableManager(base_path="...", config=config)
""")


if __name__ == "__main__":
    main()
