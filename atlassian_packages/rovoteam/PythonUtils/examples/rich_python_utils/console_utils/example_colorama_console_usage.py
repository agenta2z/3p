"""
Simple usage examples of basics.py (Colorama-based console utilities)

This demonstrates:
- Backtick-based highlighting (hprint, eprint, wprint, cprint)
- Message printing (single and pairs)
- Section titles and separators
- Logger integration
- Attribute printing
- Pair string parsing
- Color customization

Prerequisites:
    colorama (automatically installed with python_utils)

Usage:
    python example_basics_usage.py
"""

import logging

from resolve_path import resolve_path
resolve_path()  # Add project src to sys.path

from python_utils.console_utils.colorama_console_utils import (
    # Backtick highlighting
    hprint, eprint, wprint, cprint,
    # Message printing
    hprint_message, eprint_message, wprint_message, cprint_message,
    # Pairs printing
    hprint_pairs, eprint_pairs, wprint_pairs, cprint_pairs,
    # Section formatting
    hprint_section_title, hprint_section_separator,
    # Pair string parsing
    color_print_pair_str, hprint_message_pair_str,
    # Utilities
    print_attrs, retrieve_and_print_attrs,
    # Color constants
    HPRINT_TITLE_COLOR, EPRINT_MESSAGE_BODY_COLOR, WPRINT_MESSAGE_BODY_COLOR,
)
from python_utils.external.colorama import Fore


def demo_backtick_highlighting():
    """Demonstrate backtick-based text highlighting."""
    print("\n" + "="*80)
    print("1. BACKTICK-BASED HIGHLIGHTING")
    print("="*80 + "\n")

    print("Highlight Print (hprint) - Cyan highlights:")
    hprint("Processing file `data.csv` with `1000` rows")
    hprint("Model accuracy: `95.5%` on validation set")
    hprint("Use ``double backticks`` to escape literal backticks\n")

    print("Error Print (eprint) - Red/Magenta highlights:")
    eprint("Error in function `process_data()` at line `42`")
    eprint("Failed to load configuration from `config.json`\n")

    print("Warning Print (wprint) - Yellow highlights:")
    wprint("Function `old_api()` is deprecated, use `new_api()` instead")
    wprint("Low memory: only `256MB` available\n")

    print("Custom Print (cprint) - Custom color highlights:")
    cprint("Custom `green` highlighted text", color=Fore.GREEN)
    cprint("Custom `magenta` highlighted text", color=Fore.MAGENTA)


def demo_message_printing():
    """Demonstrate single message printing."""
    print("\n" + "="*80)
    print("2. SINGLE MESSAGE PRINTING")
    print("="*80 + "\n")

    print("Highlight messages:")
    hprint_message(title="Status", content="Processing")
    hprint_message(title="Progress", content="50% complete")
    hprint_message(title="Result", content="Success")

    print("\nError messages:")
    eprint_message(title="Error", content="File not found")
    eprint_message(title="Critical", content="Database connection failed")

    print("\nWarning messages:")
    wprint_message(title="Warning", content="Low disk space")
    wprint_message(title="Deprecation", content="API version 1.0 will be removed")

    print("\nCustom colored messages:")
    cprint_message("Custom", "Green message", title_color=Fore.GREEN, content_color=Fore.WHITE)


def demo_pairs_printing():
    """Demonstrate key-value pairs printing."""
    print("\n" + "="*80)
    print("3. KEY-VALUE PAIRS PRINTING")
    print("="*80 + "\n")

    print("Simple pairs (no title):")
    hprint_pairs('name', 'model.pt', 'size', '100MB', 'accuracy', 0.95)

    print("\nPairs with title:")
    hprint_pairs(
        'epoch', 10,
        'loss', 0.05,
        'accuracy', 0.95,
        title='Training Results'
    )

    print("Pairs with title and comment:")
    hprint_pairs(
        'learning_rate', 0.001,
        'batch_size', 32,
        'optimizer', 'Adam',
        title='Hyperparameters',
        comment='Best configuration found during grid search'
    )

    print("\nError pairs:")
    eprint_pairs(
        'error_code', 404,
        'error_type', 'NotFound',
        'file', 'missing.txt'
    )

    print("\nWarning pairs:")
    wprint_pairs(
        'warning_code', 'W001',
        'severity', 'Medium',
        'action', 'Update dependencies'
    )

    print("\nCustom colored pairs:")
    cprint_pairs(
        'metric1', 'value1',
        'metric2', 'value2',
        first_color=Fore.GREEN,
        second_color=Fore.YELLOW,
        title='Custom Colors'
    )


def demo_section_formatting():
    """Demonstrate section titles and separators."""
    print("\n" + "="*80)
    print("4. SECTION FORMATTING")
    print("="*80 + "\n")

    hprint_section_title("Data Processing Pipeline")
    print("Step 1: Load data from disk")
    print("Step 2: Clean and preprocess")
    print("Step 3: Feature engineering")

    hprint_section_separator()

    hprint_section_title("Model Training")
    print("Training on 10,000 samples...")
    print("Validation accuracy: 94.2%")

    hprint_section_separator()


def demo_logger_integration():
    """Demonstrate logger integration."""
    print("\n" + "="*80)
    print("5. LOGGER INTEGRATION")
    print("="*80 + "\n")

    # Setup logger
    logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
    logger = logging.getLogger(__name__)

    print("Messages are printed AND logged:")
    hprint_message(title="Info", content="Processing started", logger=logger)
    eprint_message(title="Error", content="Connection timeout", logger=logger)
    wprint_message(title="Warning", content="Retry in 5 seconds", logger=logger)

    print("\nPairs are also logged:")
    hprint_pairs(
        'files_processed', 150,
        'files_failed', 3,
        'success_rate', '98%',
        title='Processing Summary',
        logger=logger
    )


def demo_pair_string_parsing():
    """Demonstrate parsing delimited pair strings."""
    print("\n" + "="*80)
    print("6. PAIR STRING PARSING")
    print("="*80 + "\n")

    print("Parse colon-comma delimited strings:")
    color_print_pair_str("name:model.pt,size:100MB,accuracy:0.95")

    print("\nParse with custom delimiters:")
    color_print_pair_str("a=1;b=2;c=3", pair_delimiter=';', kv_delimiter='=')

    print("\nHprint-styled pair strings:")
    hprint_message_pair_str("epoch:10,loss:0.05,accuracy:0.95")


def demo_attribute_printing():
    """Demonstrate object attribute printing."""
    print("\n" + "="*80)
    print("7. ATTRIBUTE PRINTING")
    print("="*80 + "\n")

    # Create example configuration object
    class ModelConfig:
        def __init__(self):
            self.model_name = "ResNet50"
            self.num_layers = 50
            self.pretrained = True
            self.learning_rate = 0.001
            self.batch_size = 32
            self._private_key = "hidden"  # Private attribute

        def train(self):
            """Training method (will not be printed)."""
            pass

    config = ModelConfig()

    print("Print all public attributes:")
    print_attrs(config)

    print("\nRetrieve and print specific attributes:")
    name, layers, lr = retrieve_and_print_attrs(config, 'model_name', 'num_layers', 'learning_rate')
    print(f"\nRetrieved values: name={name}, layers={layers}, lr={lr}")


def demo_output_collection():
    """Demonstrate collecting output for further processing."""
    print("\n" + "="*80)
    print("8. OUTPUT COLLECTION")
    print("="*80 + "\n")

    print("Collecting multiple metric runs:")
    results_table = []

    # Simulate three training runs
    for run_id in range(1, 4):
        hprint_pairs(
            'accuracy', 0.90 + run_id * 0.01,
            'precision', 0.88 + run_id * 0.02,
            'recall', 0.92 + run_id * 0.01,
            title=f'Run {run_id}',
            output_title_and_contents=results_table
        )

    print("\nCollected results table:")
    for row in results_table:
        print(row)


def demo_color_constants():
    """Demonstrate using color constants."""
    print("\n" + "="*80)
    print("9. COLOR CONSTANTS")
    print("="*80 + "\n")

    print(f"HPRINT_TITLE_COLOR: {HPRINT_TITLE_COLOR}YELLOW{Fore.RESET}")
    print(f"EPRINT_MESSAGE_COLOR: {EPRINT_MESSAGE_BODY_COLOR}RED{Fore.RESET}")
    print(f"WPRINT_MESSAGE_COLOR: {WPRINT_MESSAGE_BODY_COLOR}YELLOW{Fore.RESET}")

    print("\nUsing constants in custom prints:")
    cprint_message(
        "Custom Highlight",
        "Using HPRINT title color",
        title_color=HPRINT_TITLE_COLOR,
        content_color=Fore.WHITE
    )


def demo_practical_examples():
    """Demonstrate practical real-world usage."""
    print("\n" + "="*80)
    print("10. PRACTICAL EXAMPLES")
    print("="*80 + "\n")

    # Example 1: Progress reporting
    hprint_section_title("Data Processing")
    hprint_message(title="Loading", content="Reading from database...")
    hprint_pairs('rows_loaded', 10000, 'tables', 5, 'time', '2.3s')
    hprint_message(title="Status", content="Complete")

    hprint_section_separator()

    # Example 2: Error handling
    try:
        # Simulate error
        raise FileNotFoundError("config.yaml")
    except FileNotFoundError as e:
        eprint(f"Configuration error: `{str(e)}` not found")
        eprint_pairs(
            'error_type', 'FileNotFoundError',
            'file', 'config.yaml',
            'suggestion', 'Create default config',
            title='Error Details'
        )

    # Example 3: Metrics dashboard
    hprint_section_title("System Metrics")
    hprint_pairs('CPU', '45%', 'Memory', '2.3/8 GB', 'Disk', '120/500 GB')
    hprint_pairs('Network In', '1.2 MB/s', 'Network Out', '0.8 MB/s')

    # Example 4: Warning system
    hprint_section_title("Deprecation Warnings")
    wprint("Function `old_method()` will be removed in version `2.0`")
    wprint_message(title="Migration Guide", content="Use new_method() instead")


if __name__ == "__main__":
    print("\n" + "█"*80)
    print("█" + " "*78 + "█")
    print("█" + " "*20 + "BASICS.PY USAGE EXAMPLES" + " "*35 + "█")
    print("█" + " "*78 + "█")
    print("█"*80)

    demo_backtick_highlighting()
    demo_message_printing()
    demo_pairs_printing()
    demo_section_formatting()
    demo_logger_integration()
    demo_pair_string_parsing()
    demo_attribute_printing()
    demo_output_collection()
    demo_color_constants()
    demo_practical_examples()

    print("\n" + "="*80)
    print("ALL EXAMPLES COMPLETED!")
    print("="*80 + "\n")

    # Note: checkpoint() is commented out to avoid blocking
    # Uncomment to test interactive checkpoint:
    # from python_utils.console_utils import checkpoint
    # checkpoint("Enter 'YES' to exit")
