#!/bin/bash
# get_parsed_args Interactive Examples Runner
#
# Usage:
#   ./run_examples.sh              - Show menu
#   ./run_examples.sh basic        - Run basic usage tutorial
#   ./run_examples.sh types        - Run type handling tutorial
#   ./run_examples.sh presets      - Run presets tutorial
#   ./run_examples.sh all          - Run all tutorials

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/../../../.."
export PYTHONPATH=src
EXAMPLES_DIR="examples/rich_python_utils/common_utils/arg_utils"

run_basic() {
    echo ""
    echo "============================================================"
    echo "  STARTING: Basic Usage Tutorial"
    echo "============================================================"
    python3 "$EXAMPLES_DIR/example_basic_usage.py"
}

run_types() {
    echo ""
    echo "============================================================"
    echo "  STARTING: Type Handling Tutorial"
    echo "============================================================"
    python3 "$EXAMPLES_DIR/example_type_handling.py"
}

run_presets() {
    echo ""
    echo "============================================================"
    echo "  STARTING: Presets Tutorial"
    echo "============================================================"
    python3 "$EXAMPLES_DIR/example_presets.py"
}

run_all() {
    echo "Running all tutorials..."
    run_basic
    echo ""
    run_types
    echo ""
    run_presets
    echo ""
    echo "ALL TUTORIALS COMPLETE!"
}

show_menu() {
    echo ""
    echo "============================================================"
    echo "  GET_PARSED_ARGS INTERACTIVE TUTORIALS"
    echo "============================================================"
    echo ""
    echo "Choose a tutorial to run:"
    echo ""
    echo "  1. Basic Usage    - Learn the different input formats"
    echo "  2. Type Handling  - Boolean, list, dict, tuple handling"
    echo "  3. Presets        - Configuration file system"
    echo "  4. All Tutorials  - Run all tutorials in sequence"
    echo "  5. Exit"
    echo ""
    printf "Enter choice (1-5): "
    read choice
    case "$choice" in
        1) run_basic ;;
        2) run_types ;;
        3) run_presets ;;
        4) run_all ;;
        5) exit 0 ;;
        *) echo "Invalid choice"; show_menu ;;
    esac
}

case "${1:-menu}" in
    basic) run_basic ;;
    types) run_types ;;
    presets) run_presets ;;
    all) run_all ;;
    help|--help|-h)
        echo "Usage: ./run_examples.sh [basic|types|presets|all|help]"
        ;;
    *) show_menu ;;
esac
