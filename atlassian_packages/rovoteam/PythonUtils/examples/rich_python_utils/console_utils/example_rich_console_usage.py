"""
Comprehensive usage examples of rich_console_utils.py (Rich library-based utilities)

This demonstrates:
- Rich backtick highlighting (all variants)
- Rich message and pairs printing
- Rich-specific features (tables, syntax highlighting, markdown, JSON, panels)
- Progress bars with real work simulation
- Rich logger usage
- Custom color combinations
- Comparison with basics.py output

Prerequisites:
    rich (automatically installed with python_utils)

Usage:
    python example_rich_console_usage.py
"""

import sys
sys.path.insert(0, r'C:\Users\yxinl\OneDrive\Projects\PythonProjects\SciencePythonUtils\src')

import time
import logging
from python_utils.console_utils.rich_console_utils import (
    # Backtick highlighting
    cprint, hprint, eprint, wprint,
    # Message printing
    cprint_message, hprint_message, eprint_message, wprint_message,
    # Pairs printing
    cprint_pairs, hprint_pairs, eprint_pairs, wprint_pairs,
    # Pair string parsing
    color_print_pair_str, hprint_message_pair_str,
    # Logging utilities
    log_pairs, info_print, debug_print,
    # Section formatting
    hprint_section_title, hprint_section_separator,
    # Panel printing
    cprint_panel, hprint_panel, eprint_panel, wprint_panel,
    # Rich features
    print_table, print_syntax, print_markdown, print_json, progress_bar,
    # Utilities
    print_attrs, retrieve_and_print_attrs,
    # Logger
    get_rich_logger,
    # Console
    console,
)


def demo_backtick_highlighting():
    """Demonstrate Rich backtick highlighting."""
    console.print("\n" + "="*80, style="bold")
    console.print("1. BACKTICK-BASED HIGHLIGHTING (Rich Version)", style="bold cyan")
    console.print("="*80 + "\n", style="bold")

    console.print("[bold]Highlight Print (hprint) - Cyan highlights:[/bold]")
    hprint("Processing file `data.csv` with `1000` rows")
    hprint("Model accuracy: `95.5%` on validation set")
    hprint("Use ``double backticks`` to escape: ``literal backticks``\n")

    console.print("[bold]Error Print (eprint) - Red highlights:[/bold]")
    eprint("Error in function `process_data()` at line `42`")
    eprint("Failed to load configuration from `config.json`\n")

    console.print("[bold]Warning Print (wprint) - Yellow highlights:[/bold]")
    wprint("Function `old_api()` is deprecated, use `new_api()` instead")
    wprint("Low memory: only `256MB` available\n")

    console.print("[bold]Custom Print (cprint) - Custom colors:[/bold]")
    cprint("Custom `green` highlighted text", color="green")
    cprint("Custom `magenta` highlighted text", color="magenta")
    cprint("Custom `bold blue` highlighted text", color="bold blue")


def demo_message_printing():
    """Demonstrate Rich message printing."""
    console.print("\n" + "="*80, style="bold")
    console.print("2. MESSAGE PRINTING (Rich Version)", style="bold cyan")
    console.print("="*80 + "\n", style="bold")

    console.print("[bold]Highlight messages:[/bold]")
    hprint_message(title="Status", content="Processing")
    hprint_message(title="Progress", content="50% complete")
    hprint_message(title="Result", content="Success")

    console.print("\n[bold]Error messages:[/bold]")
    eprint_message(title="Error", content="File not found")
    eprint_message(title="Critical", content="Database connection failed")

    console.print("\n[bold]Warning messages:[/bold]")
    wprint_message(title="Warning", content="Low disk space")
    wprint_message(title="Deprecation", content="API version 1.0 will be removed")

    console.print("\n[bold]Custom colored messages:[/bold]")
    cprint_message("Info", "Blue message", title_color="blue", content_color="white")
    cprint_message("Success", "Green message", title_color="green", content_color="white")


def demo_pairs_printing():
    """Demonstrate Rich pairs printing."""
    console.print("\n" + "="*80, style="bold")
    console.print("3. KEY-VALUE PAIRS PRINTING (Rich Version)", style="bold cyan")
    console.print("="*80 + "\n", style="bold")

    console.print("[bold]Simple pairs:[/bold]")
    hprint_pairs('name', 'model.pt', 'size', '100MB', 'accuracy', 0.95)

    console.print("\n[bold]Pairs with title:[/bold]")
    hprint_pairs(
        'epoch', 10,
        'loss', 0.05,
        'accuracy', 0.95,
        title='Training Results'
    )

    console.print("[bold]Pairs with title and comment:[/bold]")
    hprint_pairs(
        'learning_rate', 0.001,
        'batch_size', 32,
        'optimizer', 'Adam',
        title='Hyperparameters',
        comment='Best configuration from grid search'
    )

    console.print("\n[bold]Error pairs:[/bold]")
    eprint_pairs(
        'error_code', 404,
        'error_type', 'NotFoundError',
        'file', 'data.csv',
        title='Error Details'
    )

    console.print("\n[bold]Warning pairs:[/bold]")
    wprint_pairs(
        'memory_usage', '85%',
        'disk_space', '90%',
        'cpu_temp', '75°C',
        title='System Warnings',
        comment='Resource usage is high'
    )

    console.print("\n[bold]Custom colored pairs:[/bold]")
    cprint_pairs(
        'metric1', 'value1',
        'metric2', 'value2',
        'metric3', 'value3',
        first_color='green',
        second_color='yellow',
        title='Custom Colors',
        title_color='magenta'
    )


def demo_pair_string_parsing():
    """Demonstrate pair string parsing utilities."""
    console.print("\n" + "="*80, style="bold")
    console.print("3B. PAIR STRING PARSING (Delimited Strings)", style="bold cyan")
    console.print("="*80 + "\n", style="bold")

    console.print("[bold]color_print_pair_str - Parse colon-separated pairs:[/bold]")
    color_print_pair_str("name:model.pt,size:100MB,accuracy:0.95")

    console.print("\n[bold]color_print_pair_str with custom delimiters:[/bold]")
    color_print_pair_str("host=localhost;port=8080;protocol=https", pair_delimiter=';', kv_delimiter='=')

    console.print("\n[bold]hprint_message_pair_str - Parse with hprint colors:[/bold]")
    hprint_message_pair_str("epoch:10,loss:0.05,accuracy:0.95,val_loss:0.08")

    console.print("\n[bold]Custom colored pair strings:[/bold]")
    color_print_pair_str(
        "status:running,health:good,uptime:99.9%",
        key_color="green",
        value_color="yellow"
    )


def demo_section_separators():
    """Demonstrate section separator functions."""
    console.print("\n" + "="*80, style="bold")
    console.print("3C. SECTION SEPARATORS", style="bold cyan")
    console.print("="*80 + "\n", style="bold")

    console.print("[bold]Highlight section with separator:[/bold]")
    hprint_section_title("Processing Phase 1")
    hprint_pairs('files', 100, 'size', '1.5GB')
    hprint_section_separator()

    console.print("[bold]Error section with separator:[/bold]")
    from python_utils.console_utils.rich_console_utils import eprint_section_separator
    eprint_pairs(
        'error_count', 5,
        'critical', 2,
        'warnings', 3,
        title='Error Summary'
    )
    # Note: eprint_pairs already adds separator, but we can add extra ones
    console.print("[dim]eprint_section_separator() called:[/dim]")
    eprint_section_separator()

    console.print("[bold]Warning section with separator:[/bold]")
    from python_utils.console_utils.rich_console_utils import wprint_section_separator
    wprint_pairs(
        'memory', '85%',
        'disk', '90%',
        title='Resource Warnings'
    )
    console.print("[dim]wprint_section_separator() called:[/dim]")
    wprint_section_separator()


def demo_rich_panels():
    """Demonstrate Rich panels."""
    console.print("\n" + "="*80, style="bold")
    console.print("4. RICH PANELS (Bordered Content)", style="bold cyan")
    console.print("="*80 + "\n", style="bold")

    console.print("[bold]Highlight panel (hprint_panel):[/bold]")
    hprint_panel(
        "This is an information panel with cyan borders.\nYou can add multiple lines and formatting.",
        title="Information"
    )

    console.print("\n[bold]Error panel (eprint_panel):[/bold]")
    eprint_panel(
        "This is an error panel with red borders.\nUse for critical errors!",
        title="Error"
    )

    console.print("\n[bold]Warning panel (wprint_panel):[/bold]")
    wprint_panel(
        "This is a warning panel with magenta borders.\nIdeal for warnings and deprecation notices.",
        title="Warning"
    )

    console.print("\n[bold]Custom panel (cprint_panel):[/bold]")
    cprint_panel(
        "This is a custom panel with green borders.\nPerfect for success messages!",
        title="Success",
        border_style="green"
    )


def demo_rich_tables():
    """Demonstrate Rich tables."""
    console.print("\n" + "="*80, style="bold")
    console.print("5. RICH TABLES (Formatted Data Display)", style="bold cyan")
    console.print("="*80 + "\n", style="bold")

    # Example 1: Simple table
    console.print("[bold]Simple data table:[/bold]")
    data1 = [
        {'name': 'Alice', 'age': 30, 'score': 95.5},
        {'name': 'Bob', 'age': 25, 'score': 87.3},
        {'name': 'Charlie', 'age': 35, 'score': 92.1},
    ]
    print_table(data1, title='Student Scores')

    # Example 2: Table with custom columns
    console.print("\n[bold]Table with selected columns:[/bold]")
    data2 = [
        {'model': 'ResNet50', 'params': '25M', 'accuracy': 0.95, 'speed': 'fast'},
        {'model': 'VGG16', 'params': '138M', 'accuracy': 0.92, 'speed': 'slow'},
        {'model': 'EfficientNet', 'params': '5M', 'accuracy': 0.96, 'speed': 'fast'},
    ]
    print_table(data2, columns=['model', 'accuracy', 'speed'], title='Model Comparison')

    # Example 3: Metrics table
    console.print("\n[bold]Training metrics table:[/bold]")
    metrics = [
        {'epoch': 1, 'loss': 0.95, 'accuracy': 0.65, 'val_loss': 0.88},
        {'epoch': 2, 'loss': 0.65, 'accuracy': 0.78, 'val_loss': 0.72},
        {'epoch': 3, 'loss': 0.45, 'accuracy': 0.85, 'val_loss': 0.58},
        {'epoch': 4, 'loss': 0.32, 'accuracy': 0.91, 'val_loss': 0.49},
        {'epoch': 5, 'loss': 0.25, 'accuracy': 0.94, 'val_loss': 0.44},
    ]
    print_table(metrics, title='Training Progress', show_lines=True)


def demo_syntax_highlighting():
    """Demonstrate syntax highlighting."""
    console.print("\n" + "="*80, style="bold")
    console.print("6. SYNTAX HIGHLIGHTING (Code Display)", style="bold cyan")
    console.print("="*80 + "\n", style="bold")

    # Python code
    python_code = '''def fibonacci(n):
    """Calculate nth Fibonacci number."""
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

# Calculate first 10 Fibonacci numbers
for i in range(10):
    print(f"F({i}) = {fibonacci(i)}")'''

    console.print("[bold]Python code with syntax highlighting:[/bold]")
    print_syntax(python_code, language='python', theme='monokai')

    # JSON code
    json_code = '''{
    "name": "MyProject",
    "version": "1.0.0",
    "dependencies": {
        "rich": "^13.0.0",
        "textual": "^0.40.0"
    }
}'''

    console.print("\n[bold]JSON code with syntax highlighting:[/bold]")
    print_syntax(json_code, language='json', theme='monokai')


def demo_markdown_rendering():
    """Demonstrate markdown rendering."""
    console.print("\n" + "="*80, style="bold")
    console.print("7. MARKDOWN RENDERING", style="bold cyan")
    console.print("="*80 + "\n", style="bold")

    markdown_text = """# Project Documentation

## Features

This project includes:

- **Rich console utilities** for beautiful terminal output
- *Syntax highlighting* for code blocks
- `Inline code` formatting
- Tables, panels, and progress bars

## Installation

```bash
pip install science-python-utils
```

## Quick Start

1. Import the utilities
2. Use the print functions
3. Enjoy beautiful output!

> **Note:** Rich provides much better formatting than standard print!
"""

    console.print("[bold]Rendered markdown:[/bold]\n")
    print_markdown(markdown_text)


def demo_json_printing():
    """Demonstrate JSON pretty-printing."""
    console.print("\n" + "="*80, style="bold")
    console.print("8. JSON PRETTY-PRINTING", style="bold cyan")
    console.print("="*80 + "\n", style="bold")

    # Example 1: Dictionary
    console.print("[bold]Dictionary as JSON:[/bold]")
    data_dict = {
        'project': 'SciencePythonUtils',
        'version': '1.0.0',
        'features': ['console_utils', 'io_utils', 'service_utils'],
        'config': {
            'debug': False,
            'log_level': 'INFO',
            'max_workers': 4
        }
    }
    print_json(data_dict)

    # Example 2: List
    console.print("\n[bold]List as JSON:[/bold]")
    data_list = [
        {'id': 1, 'name': 'Item 1', 'active': True},
        {'id': 2, 'name': 'Item 2', 'active': False},
        {'id': 3, 'name': 'Item 3', 'active': True}
    ]
    print_json(data_list)


def demo_progress_bars():
    """Demonstrate progress bars."""
    console.print("\n" + "="*80, style="bold")
    console.print("9. PROGRESS BARS (Live Updates)", style="bold cyan")
    console.print("="*80 + "\n", style="bold")

    console.print("[bold]Processing multiple tasks with progress tracking:[/bold]\n")

    with progress_bar("Overall Progress") as progress:
        # Task 1: Download files
        download_task = progress.add_task("[cyan]Downloading files...", total=100)
        for i in range(100):
            time.sleep(0.01)  # Simulate work
            progress.update(download_task, advance=1)

        # Task 2: Process data
        process_task = progress.add_task("[green]Processing data...", total=50)
        for i in range(50):
            time.sleep(0.02)  # Simulate work
            progress.update(process_task, advance=1)

        # Task 3: Upload results
        upload_task = progress.add_task("[magenta]Uploading results...", total=75)
        for i in range(75):
            time.sleep(0.01)  # Simulate work
            progress.update(upload_task, advance=1)

    console.print("\n[bold green]✓ All tasks completed![/bold green]")


def demo_logging_utilities():
    """Demonstrate logging utilities."""
    console.print("\n" + "="*80, style="bold")
    console.print("10. LOGGING UTILITIES", style="bold cyan")
    console.print("="*80 + "\n", style="bold")

    # Create Rich logger
    logger = get_rich_logger('demo_logger', level=logging.DEBUG)

    console.print("[bold]Rich logger with beautiful formatting:[/bold]")
    logger.debug("Debug message - detailed information")
    logger.info("Info message - general information")
    logger.warning("Warning message - something to watch")
    logger.error("Error message - something went wrong")

    console.print("\n[bold]Log pairs utility:[/bold]")
    log_pairs(logger.info, ('metric1', 100), ('metric2', 200), ('metric3', 300))

    console.print("\n[bold]Tagged prints (info_print, debug_print):[/bold]")
    info_print("DataProcessor", "Processing started")
    info_print("ModelTrainer", "Training epoch 1")
    debug_print("ConfigLoader", "Config loaded from file")
    debug_print("DatabaseConn", "Connected to database")


def demo_attribute_printing():
    """Demonstrate attribute printing."""
    console.print("\n" + "="*80, style="bold")
    console.print("11. ATTRIBUTE PRINTING", style="bold cyan")
    console.print("="*80 + "\n", style="bold")

    class NetworkConfig:
        def __init__(self):
            self.host = "localhost"
            self.port = 8080
            self.protocol = "https"
            self.timeout = 30
            self.max_retries = 3
            self._api_key = "secret123"  # Private

        def connect(self):
            """Connection method."""
            pass

    config = NetworkConfig()

    console.print("[bold]Print all public attributes:[/bold]")
    print_attrs(config)

    console.print("\n[bold]Retrieve specific attributes:[/bold]")
    host, port, protocol = retrieve_and_print_attrs(config, 'host', 'port', 'protocol')
    console.print(f"\n[green]Retrieved:[/green] {host}:{port} using {protocol}")


def demo_practical_workflow():
    """Demonstrate a practical workflow."""
    console.print("\n" + "="*80, style="bold")
    console.print("12. PRACTICAL WORKFLOW EXAMPLE", style="bold cyan")
    console.print("="*80 + "\n", style="bold")

    # Simulated ML training workflow
    hprint_section_title("Machine Learning Training Pipeline")

    # Step 1: Configuration
    hprint_panel(
        "Loading configuration from config.yaml\nValidating hyperparameters...",
        title="Configuration"
    )
    config_data = {
        'model': 'ResNet50',
        'batch_size': 32,
        'learning_rate': 0.001,
        'epochs': 10
    }
    print_json(config_data)

    hprint_section_separator()

    # Step 2: Data Loading
    console.print("\n[bold cyan]Loading Training Data[/bold cyan]")
    data_stats = [
        {'split': 'train', 'samples': 50000, 'classes': 10},
        {'split': 'validation', 'samples': 10000, 'classes': 10},
        {'split': 'test', 'samples': 10000, 'classes': 10},
    ]
    print_table(data_stats, title='Dataset Statistics')

    hprint_section_separator()

    # Step 3: Training
    console.print("\n[bold cyan]Training Progress[/bold cyan]")
    hprint_message(title="Epoch 1/10", content="Starting...")
    hprint_pairs('loss', 0.85, 'accuracy', 0.72, 'val_loss', 0.78)

    hprint_message(title="Epoch 5/10", content="Mid-point...")
    hprint_pairs('loss', 0.32, 'accuracy', 0.91, 'val_loss', 0.45)

    hprint_message(title="Epoch 10/10", content="Complete!")
    hprint_pairs('loss', 0.15, 'accuracy', 0.96, 'val_loss', 0.28)

    # Step 4: Results
    cprint_panel(
        "[bold green]Training completed successfully![/bold green]\n" +
        "Final accuracy: [cyan]96%[/cyan]\n" +
        "Model saved to: [yellow]checkpoints/model_best.pt[/yellow]",
        title="Success",
        border_style="green"
    )


def demo_comparison_with_basics():
    """Compare Rich output with basics.py output."""
    console.print("\n" + "="*80, style="bold")
    console.print("13. COMPARISON: Rich vs Colorama", style="bold cyan")
    console.print("="*80 + "\n", style="bold")

    console.print("[bold]Rich advantages:[/bold]")
    console.print("• Better color support and themes")
    console.print("• Tables, panels, and markdown rendering")
    console.print("• Syntax highlighting for code")
    console.print("• Advanced progress bars")
    console.print("• Better emoji and unicode support")
    console.print("• Automatic terminal width detection")

    console.print("\n[bold]When to use each:[/bold]")
    console.print("[cyan]basics.py (Colorama):[/cyan] Simple coloring, minimal dependencies")
    console.print("[cyan]rich_console_utils.py (Rich):[/cyan] Rich formatting, modern applications")


if __name__ == "__main__":
    console.print("\n[bold white on blue]" + " "*80 + "[/]")
    console.print("[bold white on blue]" + " "*22 + "RICH CONSOLE UTILS USAGE EXAMPLES" + " "*25 + "[/]")
    console.print("[bold white on blue]" + " "*80 + "[/]")

    demo_backtick_highlighting()
    demo_message_printing()
    demo_pairs_printing()
    demo_pair_string_parsing()
    demo_section_separators()
    demo_rich_panels()
    demo_rich_tables()
    demo_syntax_highlighting()
    demo_markdown_rendering()
    demo_json_printing()
    demo_progress_bars()
    demo_logging_utilities()
    demo_attribute_printing()
    demo_practical_workflow()
    demo_comparison_with_basics()

    console.print("\n" + "="*80, style="bold green")
    console.print("[bold green]✓ ALL EXAMPLES COMPLETED![/bold green]")
    console.print("="*80 + "\n", style="bold green")

    # Note: checkpoint() is commented out to avoid blocking
    # from python_utils.console_utils.rich_console_utils import checkpoint
    # checkpoint("Enter 'YES' to exit")
