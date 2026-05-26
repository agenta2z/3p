#!/usr/bin/env python3
"""
TemplateManager Integration with Predefined Variables
======================================================

Demonstrates the simplest way to use automatic variable resolution
with TemplateManager's predefined_variables parameter.

Run this example:
    PYTHONPATH=src python examples/python_utils/string_utils/formatting/template_manager/variable_examples/02_template_manager_integration.py
"""

from pathlib import Path

from python_utils.string_utils.formatting.template_manager import (
    TemplateManager,
    VariableLoader,
    VariableLoaderConfig,
)


def get_mock_templates_dir() -> Path:
    """Get the path to the mock_templates directory."""
    return Path(__file__).parent / "mock_templates"


def main():
    template_dir = get_mock_templates_dir()

    # =================================================================
    # CORE CODE
    # =================================================================

    # Option 1: Automatic (simplest)
    tm_auto = TemplateManager(
        templates=str(template_dir),
        predefined_variables=True,
    )
    result_auto = tm_auto(
        template_key="main",
        active_template_root_space="assistant_agent",
        active_template_type="chat",
        task_description="Help user with Python.",
    )

    # Option 2: Custom VariableLoader
    config = VariableLoaderConfig(enable_overrides=True)
    custom_loader = VariableLoader(template_dir=str(template_dir), config=config)
    tm_custom = TemplateManager(
        templates=str(template_dir),
        predefined_variables=custom_loader,
    )

    # Option 3: Static mapping
    tm_static = TemplateManager(
        default_template="{{header}}\n{{content}}\n{{footer}}",
        predefined_variables={
            "header": "=== START ===",
            "footer": "=== END ===",
        },
    )
    result_static = tm_static(content="Hello, World!")

    # Option 4: Skip predefined for single call
    result_skip = tm_auto(
        template_key="main",
        active_template_root_space="assistant_agent",
        active_template_type="chat",
        skip_predefined=True,
        mindset="Custom mindset",
        notes_core_values="Custom values",
        task_description="Manual test",
    )

    # =================================================================
    # OUTPUT
    # =================================================================

    print("=" * 70)
    print("TemplateManager Integration")
    print("=" * 70)

    print("\n[1] predefined_variables=True (simplest)")
    print("-" * 50)
    print("    tm = TemplateManager(")
    print("        templates='/templates',")
    print("        predefined_variables=True,")
    print("    )")
    print("    result = tm(template_key='main', user_arg='value')")
    print()
    print(f"    Result preview: {result_auto[:80]}...")

    print("\n[2] predefined_variables options")
    print("-" * 50)
    print("    True           -> Auto-create VariableLoader")
    print("    VariableLoader -> Custom configuration")
    print("    dict           -> Static values")
    print("    None/False     -> Disabled")

    print("\n[3] Static mapping example")
    print("-" * 50)
    print("    tm = TemplateManager(")
    print("        default_template='{{header}}\\n{{content}}\\n{{footer}}',")
    print("        predefined_variables={'header': '...', 'footer': '...'},")
    print("    )")
    print()
    print(f"    Result:\n{result_static}")

    print("\n[4] Override priority")
    print("-" * 50)
    print("    Highest -> Lowest:")
    print("    1. **kwargs (user arguments)")
    print("    2. feed dict")
    print("    3. predefined variables")

    print("\n[5] skip_predefined option")
    print("-" * 50)
    print("    result = tm(template_key, skip_predefined=True, **manual_vars)")
    print("    (Skips predefined resolution for this call)")

    print("\n" + "=" * 70)
    print("QUICK REFERENCE")
    print("=" * 70)
    print("""
    # Simplest setup
    tm = TemplateManager(
        templates="/templates",
        predefined_variables=True,
    )

    # Variables auto-resolved from _variables/ folders
    result = tm(
        template_key="agent/type/Template",
        active_template_root_space="agent",
        active_template_type="type",
        user_input="custom value",  # Overrides predefined
    )

    # Skip predefined for one call
    result = tm(template_key, skip_predefined=True, **all_vars_manually)
""")


if __name__ == "__main__":
    main()
