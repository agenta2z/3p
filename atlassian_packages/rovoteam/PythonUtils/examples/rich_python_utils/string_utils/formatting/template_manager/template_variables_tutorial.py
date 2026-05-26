#!/usr/bin/env python3
"""
Template Variables Tutorial
===========================

This tutorial demonstrates how to use the VariableLoader class for automatic
variable detection and resolution in templates.

Key Features:
- Auto-detection of variables from template content
- Cascading resolution (template-type → agent → global)
- Scope modifiers: ^{{var}} (global), .{{var}} (current level), {{var}}? (optional)
- Variable-to-variable composition with circular reference detection
- Single underscore separator with file-existence inference

Directory Structure:
    templates/
    ├── _variables/                         # Global variables
    │   ├── mindset.hbs                     # {{mindset}}
    │   └── notes/
    │       ├── core_values.hbs             # {{notes_core_values}}
    │       └── guidelines.hbs              # {{notes_guidelines}}
    ├── my_agent/
    │   ├── _variables/                     # Agent-level variables
    │   │   └── notes/
    │   │       └── core_values.hbs         # Overrides global
    │   └── main/
    │       ├── _variables/                 # Template-type level variables
    │       │   └── notes/
    │       │       └── local.hbs           # {{notes_local}}
    │       └── prompt.hbs                  # Template file

Usage:
    python template_variables_tutorial.py
"""

import tempfile
from pathlib import Path

from python_utils.string_utils.formatting.template_manager import (
    VariableLoader,
    VariableLoaderConfig,
    TemplateManager,
)


def create_sample_structure(base_dir: Path) -> None:
    """Create a sample template directory structure for demonstration."""

    # Global _variables
    global_vars = base_dir / "_variables"
    global_vars.mkdir(parents=True)

    # Global mindset (flat file, no underscore)
    (global_vars / "mindset.hbs").write_text(
        "You are a helpful AI assistant.\n"
        "Think step by step and be thorough.\n"
    )

    # Global notes/core_values (categorized with underscore inference)
    notes_dir = global_vars / "notes"
    notes_dir.mkdir()

    (notes_dir / "core_values.hbs").write_text(
        "CORE VALUES:\n"
        "- Accuracy: Always verify information\n"
        "- Clarity: Explain complex topics simply\n"
    )

    (notes_dir / "guidelines.hbs").write_text(
        "GUIDELINES:\n"
        "- Be concise and direct\n"
        "- Provide examples when helpful\n"
    )

    # Composed variable that references other variables
    (notes_dir / "composed.hbs").write_text(
        "=== Composed Notes ===\n"
        "{{mindset}}\n"
        "\n"
        "{{notes_core_values}}\n"
        "=== End ===\n"
    )

    # Agent-level _variables (overrides global)
    agent_vars = base_dir / "my_agent" / "_variables" / "notes"
    agent_vars.mkdir(parents=True)

    (agent_vars / "core_values.hbs").write_text(
        "AGENT-SPECIFIC CORE VALUES:\n"
        "- Focus: Stay on task\n"
        "- Speed: Respond quickly\n"
    )

    # Template-type level _variables
    template_type_vars = base_dir / "my_agent" / "main" / "_variables" / "notes"
    template_type_vars.mkdir(parents=True)

    (template_type_vars / "local.hbs").write_text(
        "LOCAL CONTEXT:\n"
        "- This is specific to the main template type\n"
    )

    # Sample template file
    template_dir = base_dir / "my_agent" / "main"
    (template_dir / "prompt.hbs").write_text(
        "# System Prompt\n"
        "\n"
        "{{mindset}}\n"
        "\n"
        "{{notes_core_values}}\n"
        "\n"
        "{{notes_guidelines}}\n"
        "\n"
        "{{notes_local}}\n"
        "\n"
        "## User Input\n"
        "{{user_input}}\n"
    )


def demo_basic_resolution():
    """Demonstrate basic variable resolution with cascading."""
    print("=" * 60)
    print("DEMO: Basic Variable Resolution")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        create_sample_structure(base_dir)

        loader = VariableLoader(template_dir=str(base_dir))

        # Simple template with variables
        template = "{{mindset}} and {{notes_core_values}}"

        # Resolve with unknown agent (falls back to global)
        print("\n1. Resolving for unknown_agent (uses global):")
        variables = loader.resolve_from_template(
            template, template_root_space="unknown_agent", template_type="main"
        )
        for name, content in variables.items():
            print(f"   {name}: {content[:50]}...")

        # Resolve with my_agent (uses agent-level override)
        print("\n2. Resolving for my_agent (uses agent-level):")
        variables = loader.resolve_from_template(
            template, template_root_space="my_agent", template_type="main"
        )
        for name, content in variables.items():
            print(f"   {name}: {content[:50]}...")


def demo_scope_modifiers():
    """Demonstrate scope modifiers (^, ?, .)."""
    print("\n" + "=" * 60)
    print("DEMO: Scope Modifiers")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        create_sample_structure(base_dir)

        loader = VariableLoader(template_dir=str(base_dir))

        # Global scope modifier (^)
        print("\n1. Global scope modifier ^{{var}}:")
        template = "^{{notes_core_values}}"
        variables = loader.resolve_from_template(
            template, template_root_space="my_agent", template_type="main"
        )
        print(f"   Uses global despite agent override existing:")
        print(f"   {variables.get('notes_core_values', 'NOT FOUND')[:60]}...")

        # Optional modifier (?)
        print("\n2. Optional modifier {{var}}?:")
        template = "{{nonexistent_var}}?"
        variables = loader.resolve_from_template(
            template, template_root_space="my_agent", template_type="main"
        )
        print(f"   Non-existent optional returns empty: '{variables.get('nonexistent_var', 'KEY NOT FOUND')}'")

        # Combined modifiers
        print("\n3. Combined modifiers ^{{var}}?:")
        template = "^{{notes_core_values}}?"
        variables = loader.resolve_from_template(
            template, template_root_space="my_agent", template_type="main"
        )
        print(f"   Global + optional: {variables.get('notes_core_values', 'NOT FOUND')[:40]}...")


def demo_composition():
    """Demonstrate variable-to-variable composition."""
    print("\n" + "=" * 60)
    print("DEMO: Variable Composition")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        create_sample_structure(base_dir)

        loader = VariableLoader(template_dir=str(base_dir))

        # Resolve composed variable (references other variables)
        template = "{{notes_composed}}"
        variables = loader.resolve_from_template(
            template, template_root_space="unknown_agent", template_type="main"
        )

        print("\nnotes_composed content (fully resolved):")
        print("-" * 40)
        print(variables.get("notes_composed", "NOT FOUND"))


def demo_underscore_inference():
    """Demonstrate underscore split inference."""
    print("\n" + "=" * 60)
    print("DEMO: Underscore Split Inference")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        create_sample_structure(base_dir)

        loader = VariableLoader(template_dir=str(base_dir))

        print("\n1. Variable name: notes_core_values")
        print("   Paths tried: notes/core_values.hbs, notes_core_values.hbs")
        print("   Found: notes/core_values.hbs (first existing path wins)")

        # Show the splits that would be generated
        splits = loader._generate_underscore_splits("my_app_settings")
        print("\n2. Variable name: my_app_settings")
        print(f"   Paths tried: {splits}")


def demo_integration_with_template_manager():
    """Demonstrate integration with TemplateManager."""
    print("\n" + "=" * 60)
    print("DEMO: Integration with TemplateManager")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        create_sample_structure(base_dir)

        # Create both loader and manager
        loader = VariableLoader(template_dir=str(base_dir))
        manager = TemplateManager(templates=str(base_dir))

        # Get raw template content
        raw_content = manager.get_raw_template("my_agent/main/prompt")

        print("\n1. Raw template content:")
        print("-" * 40)
        print(raw_content[:200] + "..." if len(raw_content) > 200 else raw_content)

        # Resolve variables from template
        variables = loader.resolve_from_template(
            raw_content,
            template_root_space="my_agent",
            template_type="main",
        )

        print("\n2. Resolved variables:")
        print("-" * 40)
        for name in variables:
            print(f"   - {name}")

        # Render with resolved variables + user input
        result = manager(
            "my_agent/main/prompt",
            **variables,
            user_input="What is the capital of France?",
        )

        print("\n3. Final rendered output:")
        print("-" * 40)
        print(result)


def demo_config_options():
    """Demonstrate configuration options."""
    print("\n" + "=" * 60)
    print("DEMO: Configuration Options")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)

        # Create override file
        vars_dir = base_dir / "_variables"
        vars_dir.mkdir()
        (vars_dir / "test.hbs").write_text("BASE content")
        (vars_dir / "test.override.hbs").write_text("OVERRIDE content")

        # Default config (overrides disabled)
        print("\n1. Default config (overrides disabled):")
        loader = VariableLoader(template_dir=str(base_dir))
        variables = loader.resolve_from_template(
            "{{test}}", template_root_space="test", template_type="main"
        )
        print(f"   Content: {variables.get('test', 'NOT FOUND')}")

        # With overrides enabled
        print("\n2. With overrides enabled:")
        config = VariableLoaderConfig(enable_overrides=True)
        loader = VariableLoader(template_dir=str(base_dir), config=config)
        variables = loader.resolve_from_template(
            "{{test}}", template_root_space="test", template_type="main"
        )
        print(f"   Content: {variables.get('test', 'NOT FOUND')}")


def main():
    """Run all demos."""
    print("\n" + "#" * 60)
    print("# Template Variables Tutorial")
    print("#" * 60)

    demo_basic_resolution()
    demo_scope_modifiers()
    demo_composition()
    demo_underscore_inference()
    demo_config_options()
    demo_integration_with_template_manager()

    print("\n" + "#" * 60)
    print("# Tutorial Complete!")
    print("#" * 60 + "\n")


if __name__ == "__main__":
    main()
