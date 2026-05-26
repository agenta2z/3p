#!/usr/bin/env python3
"""
Template Variable Manager Examples
==================================

This folder contains simplified examples for the template-specific wrapper.

For comprehensive feature documentation, see:
    examples/python_utils/common_objects/variable_manager/file_based_variable_manager/

These examples focus on:
1. TemplateVariableManager (alias: VariableLoader) - the thin wrapper
2. Integration with TemplateManager (predefined_variables=True)

Run examples:
    PYTHONPATH=src python examples/python_utils/string_utils/formatting/template_manager/variable_examples/01_template_variable_manager.py
    PYTHONPATH=src python examples/python_utils/string_utils/formatting/template_manager/variable_examples/02_template_manager_integration.py
"""

from pathlib import Path

from python_utils.string_utils.formatting.template_manager import (
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

    # TemplateVariableManager (alias: VariableLoader) is a thin wrapper
    # around FileBasedVariableManager with template-specific defaults:
    #   - template_dir instead of base_path
    #   - template_root_space instead of variable_root_space
    #   - template_type instead of variable_type
    #   - variables_folder_name defaults to "_variables"

    # Create loader
    loader = VariableLoader(template_dir=str(template_dir))

    # Resolve variables from template content
    template_content = "{{mindset}} {{notes_core_values}}"
    variables = loader.resolve_from_template(
        template_content,
        template_root_space="assistant_agent",
        template_type="chat",
    )

    # With custom config
    config = VariableLoaderConfig(enable_overrides=True)
    loader_custom = VariableLoader(template_dir=str(template_dir), config=config)

    # =================================================================
    # OUTPUT
    # =================================================================

    print("=" * 70)
    print("TemplateVariableManager (VariableLoader)")
    print("=" * 70)

    print("\n[1] Template-specific wrapper")
    print("-" * 50)
    print("    VariableLoader = TemplateVariableManager (alias)")
    print()
    print("    Differences from FileBasedVariableManager:")
    print("      - template_dir -> base_path")
    print("      - template_root_space -> variable_root_space")
    print("      - template_type -> variable_type")
    print("      - variables_folder_name defaults to '_variables'")

    print("\n[2] Basic usage")
    print("-" * 50)
    print("    loader = VariableLoader(template_dir='/templates')")
    print()
    print("    variables = loader.resolve_from_template(")
    print("        template_content,")
    print("        template_root_space='assistant_agent',")
    print("        template_type='chat',")
    print("    )")
    print()
    print(f"    Resolved: {list(variables.keys())}")

    print("\n[3] Directory structure")
    print("-" * 50)
    print("    templates/")
    print("    ├── _variables/              <- Global (variables_folder_name)")
    print("    │   └── mindset.hbs")
    print("    └── assistant_agent/")
    print("        ├── _variables/          <- Agent level")
    print("        │   └── notes/core_values.hbs")
    print("        └── chat/")
    print("            └── _variables/      <- Template-type level")

    print("\n" + "=" * 70)
    print("QUICK REFERENCE")
    print("=" * 70)
    print("""
    from python_utils.string_utils.formatting.template_manager import (
        VariableLoader,
        VariableLoaderConfig,
    )

    # Create loader
    loader = VariableLoader(template_dir="/templates")

    # Resolve variables
    variables = loader.resolve_from_template(
        template_content="{{var1}} {{var2}}",
        template_root_space="my_agent",
        template_type="main",
    )

    # For detailed feature docs (cascade, scope modifiers, composition):
    # See: common_objects/variable_manager/file_based_variable_manager/
""")


if __name__ == "__main__":
    main()
