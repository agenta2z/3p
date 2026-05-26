#!/bin/bash
# Interactive Mode Demo for get_parsed_args
#
# This script demonstrates the interactive argument collection feature.
# When you run this, you'll be prompted to enter values for each argument
# interactively instead of passing them via command-line arguments.
#
# Usage:
#   ./run_interactive_demo.sh
#
# Optional Dependencies (for better experience):
#   - questionary: Rich terminal prompts
#       pip install questionary
#   - ipywidgets: Jupyter notebook widgets (for notebook usage)
#       pip install ipywidgets

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/../../../.."

# Set PYTHONPATH to include src directory
export PYTHONPATH=src

EXAMPLES_DIR="examples/rich_python_utils/common_utils/arg_utils"

echo ""
echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║                                                                      ║"
echo "║              Interactive Mode Demo for get_parsed_args               ║"
echo "║                                                                      ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""
echo "This demo shows how to use interactive argument collection."
echo "You'll be prompted for values instead of using CLI arguments."
echo ""
echo "For best experience, install questionary:"
echo "  pip install questionary"
echo ""
echo "For Jupyter notebooks, install ipywidgets:"
echo "  pip install ipywidgets"
echo ""
echo "Press Ctrl+C at any time to exit."
echo ""

# Check if questionary is installed
if python3 -c "import questionary" 2>/dev/null; then
    echo "✓ questionary is installed - you'll get rich terminal prompts"
else
    echo "ℹ questionary not found - using basic input() prompts"
    echo "  Install with: pip install questionary"
fi

echo ""
echo "============================================================"
echo "  STARTING: Interactive Mode Tutorial"
echo "============================================================"

# Run the interactive example
python3 "$EXAMPLES_DIR/example_interactive.py"

EXIT_CODE=$?

echo ""
echo "============================================================"
echo "  Demo Complete!"
echo "============================================================"
echo ""
echo "Next steps:"
echo "  - Try using interactive=True in your own scripts"
echo "  - Use with Jupyter notebooks for widget-based config"
echo "  - Combine with preset files for better defaults"
echo ""
echo "See also:"
echo "  - example_basic_usage.py - Learn the input formats"
echo "  - example_presets.py - Configuration file system"
echo "  - example_type_handling.py - Data type handling"
echo ""

exit $EXIT_CODE
