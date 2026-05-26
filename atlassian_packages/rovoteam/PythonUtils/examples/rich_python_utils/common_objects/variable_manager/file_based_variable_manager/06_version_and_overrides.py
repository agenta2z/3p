#!/usr/bin/env python3
"""
Example 06: Version and Overrides
=================================

Demonstrates version suffixes and override files:
- Version suffixes: api_url.production.txt, api_url.staging.txt
- Override files: api_url.override.txt (for local development)
- Resolution order: versioned-override > override > versioned > base

Directory structure:
    mock_variables/
    ├── api_url.txt                     <- 'http://localhost:8000'
    ├── api_url.production.txt          <- 'https://api.example.com'
    ├── api_url.staging.txt             <- 'https://staging-api.example.com'
    ├── api_url.override.txt            <- 'http://localhost:9000'
    └── api_url.production.override.txt <- 'https://api-dev.example.com'

Run this example:
    PYTHONPATH=src python examples/python_utils/common_objects/variable_manager/file_based_variable_manager/06_version_and_overrides.py
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

    # Without overrides (default)
    config_no_override = VariableManagerConfig(enable_overrides=False)
    manager_no_override = FileBasedVariableManager(
        base_path=str(base_dir),
        config=config_no_override,
    )

    base_result = manager_no_override.resolve_from_content("{{api_url}}")
    prod_result = manager_no_override.resolve_from_content(
        "{{api_url}}",
        version="production",
    )
    staging_result = manager_no_override.resolve_from_content(
        "{{api_url}}",
        version="staging",
    )

    # With overrides enabled
    config_override = VariableManagerConfig(enable_overrides=True)
    manager_override = FileBasedVariableManager(
        base_path=str(base_dir),
        config=config_override,
    )

    override_result = manager_override.resolve_from_content("{{api_url}}")
    prod_override_result = manager_override.resolve_from_content(
        "{{api_url}}",
        version="production",
    )

    # =================================================================
    # OUTPUT
    # =================================================================

    print("=" * 70)
    print("Version and Overrides")
    print("=" * 70)

    print("\n[1] Variable files")
    print("-" * 50)
    print("    api_url.txt                     -> 'http://localhost:8000'")
    print("    api_url.production.txt          -> 'https://api.example.com'")
    print("    api_url.staging.txt             -> 'https://staging-api.example.com'")
    print("    api_url.override.txt            -> 'http://localhost:9000'")
    print("    api_url.production.override.txt -> 'https://api-dev.example.com'")

    print("\n[2] Without overrides (enable_overrides=False)")
    print("-" * 50)
    print(f"    Base:       {base_result.get('api_url', '')!r}")
    print(f"    Production: {prod_result.get('api_url', '')!r}")
    print(f"    Staging:    {staging_result.get('api_url', '')!r}")

    print("\n[3] With overrides (enable_overrides=True)")
    print("-" * 50)
    print(f"    Base + override:       {override_result.get('api_url', '')!r}")
    print(f"    Production + override: {prod_override_result.get('api_url', '')!r}")

    print("\n[4] Resolution order (highest priority first)")
    print("-" * 50)
    print("    1. var.{version}.override.txt")
    print("    2. var.override.txt")
    print("    3. var.{version}.txt")
    print("    4. var.txt (base)")

    print("\n" + "=" * 70)
    print("QUICK REFERENCE")
    print("=" * 70)
    print("""
    # Enable overrides for development
    config = VariableManagerConfig(enable_overrides=True)
    manager = FileBasedVariableManager(base_path="/config", config=config)

    # Resolve with version
    vars = manager.resolve_from_content(
        content="{{api_url}}",
        version="production",
    )

    # File naming convention:
    #   {name}.txt                    - Base
    #   {name}.{version}.txt          - Version-specific
    #   {name}.override.txt           - Override (dev)
    #   {name}.{version}.override.txt - Versioned override

    # Custom override suffix
    config = VariableManagerConfig(
        enable_overrides=True,
        override_suffix=".local",
    )
""")


if __name__ == "__main__":
    main()
