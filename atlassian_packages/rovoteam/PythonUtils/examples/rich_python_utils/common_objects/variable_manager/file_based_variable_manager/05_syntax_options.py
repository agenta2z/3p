#!/usr/bin/env python3
"""
Example 05: Syntax Options
==========================

Demonstrates different VariableSyntax options:
- HANDLEBARS: {{var}}
- JINJA2: {{ var }} (with spaces)
- PYTHON_FORMAT: {var}
- TEMPLATE: $var or ${var}
- None: Pure text (no composition)
- Pattern mapping: Different syntax per file extension

Directory structure:
    mock_variables/
    ├── greeting.txt     <- 'Hello from global'
    ├── app_name.txt     <- 'MyApp'
    ├── message_hbs.hbs  <- '{{greeting}}, {{app_name}}!'
    ├── message_j2.j2    <- '{{ greeting }}, {{ app_name }}!'
    ├── message_py.py    <- '{greeting}, {app_name}!'
    └── message_tpl.tpl  <- '$greeting, ${app_name}!'

Run this example:
    PYTHONPATH=src python examples/python_utils/common_objects/variable_manager/file_based_variable_manager/05_syntax_options.py
"""

from pathlib import Path

from python_utils.common_objects import (
    FileBasedVariableManager,
    VariableManagerConfig,
    VariableSyntax,
)


def get_mock_variables_dir() -> Path:
    return Path(__file__).parent / "mock_variables"


def main():
    base_dir = get_mock_variables_dir()

    # =================================================================
    # CORE CODE
    # =================================================================

    # Default: Handlebars syntax (file_extensions: .hbs, .j2, .txt, "")
    manager_hbs = FileBasedVariableManager(base_path=str(base_dir))
    result_hbs = manager_hbs.resolve_from_content("{{message_hbs}}")

    # Jinja2 syntax
    config_j2 = VariableManagerConfig(variable_syntax=VariableSyntax.JINJA2)
    manager_j2 = FileBasedVariableManager(base_path=str(base_dir), config=config_j2)
    result_j2 = manager_j2.resolve_from_content("{{ message_j2 }}")

    # Python format syntax - need to add .py to file_extensions
    config_py = VariableManagerConfig(
        variable_syntax=VariableSyntax.PYTHON_FORMAT,
        file_extensions=[".py", ".txt", ""],  # Add .py
    )
    manager_py = FileBasedVariableManager(base_path=str(base_dir), config=config_py)
    result_py = manager_py.resolve_from_content("{message_py}")

    # Template syntax ($var) - need to add .tpl to file_extensions
    config_tpl = VariableManagerConfig(
        variable_syntax=VariableSyntax.TEMPLATE,
        file_extensions=[".tpl", ".txt", ""],  # Add .tpl
    )
    manager_tpl = FileBasedVariableManager(base_path=str(base_dir), config=config_tpl)
    result_tpl = manager_tpl.resolve_from_content("$message_tpl")

    # Pure text mode (no composition)
    config_pure = VariableManagerConfig(variable_syntax=None)
    manager_pure = FileBasedVariableManager(base_path=str(base_dir), config=config_pure)
    result_pure = manager_pure["message_hbs"]

    # Pattern-based syntax mapping
    config_pattern = VariableManagerConfig(
        variable_syntax={
            "*.hbs": VariableSyntax.HANDLEBARS,
            "*.j2": VariableSyntax.JINJA2,
            "*.txt": None,  # Pure text
        }
    )

    # =================================================================
    # OUTPUT
    # =================================================================

    print("=" * 70)
    print("Syntax Options")
    print("=" * 70)

    print("\n[1] Available VariableSyntax options")
    print("-" * 50)
    print("    HANDLEBARS    -> {{var}}")
    print("    JINJA2        -> {{ var }}")
    print("    PYTHON_FORMAT -> {var}")
    print("    TEMPLATE      -> $var or ${var}")
    print("    None          -> Pure text (no composition)")

    print("\n[2] Syntax examples")
    print("-" * 50)
    print(f"    HANDLEBARS:    {result_hbs.get('message_hbs', '')!r}")
    print(f"    JINJA2:        {result_j2.get('message_j2', '')!r}")
    print(f"    PYTHON_FORMAT: {result_py.get('message_py', '')!r}")
    print(f"    TEMPLATE:      {result_tpl.get('message_tpl', '')!r}")

    print("\n[3] file_extensions config")
    print("-" * 50)
    print("    Default: ['.hbs', '.j2', '.txt', '']")
    print("    For .py files: file_extensions=['.py', '.txt', '']")
    print("    For .tpl files: file_extensions=['.tpl', '.txt', '']")

    print("\n[4] Pure text mode (variable_syntax=None)")
    print("-" * 50)
    print(f"    Raw: {result_pure!r}")
    print("    (No composition - {{var}} stays as-is)")

    print("\n[5] Pattern-based syntax mapping")
    print("-" * 50)
    print("    config = VariableManagerConfig(")
    print("        variable_syntax={")
    print("            '*.hbs': VariableSyntax.HANDLEBARS,")
    print("            '*.j2': VariableSyntax.JINJA2,")
    print("            '*.txt': None,")
    print("        }")
    print("    )")

    print("\n" + "=" * 70)
    print("QUICK REFERENCE")
    print("=" * 70)
    print("""
    from python_utils.common_objects import (
        VariableManagerConfig,
        VariableSyntax,
    )

    # Single syntax for all files
    config = VariableManagerConfig(variable_syntax=VariableSyntax.JINJA2)

    # With custom file extensions
    config = VariableManagerConfig(
        variable_syntax=VariableSyntax.PYTHON_FORMAT,
        file_extensions=[".py", ".txt", ""],
    )

    # Pure text mode (no composition)
    config = VariableManagerConfig(variable_syntax=None)

    # Pattern-based mapping
    config = VariableManagerConfig(
        variable_syntax={
            "*.hbs": VariableSyntax.HANDLEBARS,
            "*.j2": VariableSyntax.JINJA2,
            "*.txt": None,
        }
    )

    manager = FileBasedVariableManager(base_path="/config", config=config)
""")


if __name__ == "__main__":
    main()
