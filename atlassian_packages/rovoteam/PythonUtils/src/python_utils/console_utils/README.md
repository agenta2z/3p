# Console Utils - Modern Console Output & TUI

Modern console utilities for Python with automatic fallback between **Rich**, **Textual**, and **colorama** frameworks.

## Overview

This package provides three complementary implementations with automatic selection:

1. **`rich_console_utils.py`** - Rich-based console formatting (enhanced features)
2. **`textual_console_utils.py`** - Textual-based interactive TUI components
3. **`colorama_console_utils.py`** - Colorama-based fallback (minimal dependencies)

The package **automatically selects** the best available implementation:
- **First choice**: Rich (if installed)
- **Fallback**: colorama (if Rich unavailable)
- **Optional**: Textual (for interactive TUI features)

## What's New 🎉

**In-Place Message Updates** - Prevent console flooding in training loops and progress tracking:
- ✨ **`message_id`** parameter - Track messages by unique ID
- ✨ **`update_previous`** parameter - Update messages in place instead of printing new lines
- ✨ **Custom section separators** - Customize the separator line with `section_separator` parameter
- ✨ **Vertical/spaced layouts** - Use `sep='\n'` or `sep='\n\n'` for different visual layouts
- 📚 **10 comprehensive examples** - See [example_pairs_update.py](#examples)

Perfect for:
- Training loops with live metrics updates
- System monitoring dashboards
- Multi-metric progress tracking
- Status changes with color coding

```python
# Before: Console flooding with 100 lines
for epoch in range(1, 101):
    hprint_pairs('epoch', epoch, 'loss', loss, title='Training')

# After: Single line that updates in place
for epoch in range(1, 101):
    hprint_pairs('epoch', epoch, 'loss', loss,
                 title='Training', message_id='train', update_previous=True)
```

## Installation

### Minimal Installation (colorama only)
```bash
pip install colorama
```

### Full Installation (recommended)
```bash
pip install rich textual colorama
```

### Optional Dependencies
```bash
# Rich only (enhanced formatting)
pip install rich

# Textual only (interactive TUI)
pip install textual

# Both (full features)
pip install rich textual
```

## Quick Start

### Simple Import (Automatic Fallback)

```python
from python_utils.console_utils import (
    hprint_message,
    eprint_message,
    wprint_message,
    hprint_pairs,
    print_table,  # None if Rich not available
    prompt_confirm,  # None if Textual not available
)

# Core functions work with any backend
hprint_message('Status', 'Processing')
hprint_pairs('epoch', 10, 'loss', 0.05, title='Training')

# Check feature availability
if print_table is not None:
    data = [{'name': 'Alice', 'score': 95}]
    print_table(data, title='Results')
else:
    print("Rich not available, using basic output")

if prompt_confirm is not None:
    if prompt_confirm("Continue?"):
        # do something
        pass
```

### Feature Detection

```python
from python_utils.console_utils import __backend__, __has_textual__

print(f"Backend: {__backend__}")  # "rich" or "colorama"
print(f"Textual available: {__has_textual__}")  # True or False

# Conditional feature usage
if __backend__ == "rich":
    from python_utils.console_utils import print_syntax

    print_syntax(code, language='python')
```

### Direct Module Import (Specify Backend)

```python
# Use Rich directly
from python_utils.console_utils import rich_console_utils as rcu

rcu.hprint_message('Status', 'Processing')
rcu.print_table(data, title='Results')

# Use colorama directly
from python_utils.console_utils import colorama_console_utils as ccu

ccu.hprint_message('Status', 'Processing')

# Use Textual directly
from python_utils.console_utils import textual_console_utils as tcu

if tcu.prompt_confirm("Continue?"):
    pass
```

## Core Features (All Backends)

These functions work identically with both Rich and colorama backends:

### Message Printing

```python
from python_utils.console_utils import (
    hprint_message,  # Highlight/info messages (cyan)
    eprint_message,  # Error messages (red)
    wprint_message,  # Warning messages (magenta)
    cprint_message,  # Custom colored messages
)

# Single message
hprint_message(title='Status', content='Processing')
eprint_message(title='Error', content='File not found')
wprint_message(title='Warning', content='Low memory')

# Multiple key-value pairs
hprint_message(
    'epoch', 10,
    'loss', 0.05,
    'accuracy', 0.95,
    title='Training Results'
)
```

### Pairs Printing

```python
from python_utils.console_utils import (
    hprint_pairs,  # Info pairs
    eprint_pairs,  # Error pairs
    wprint_pairs,  # Warning pairs
    cprint_pairs,  # Custom colored pairs
)

hprint_pairs(
    'name', 'model.pt',
    'size', '100MB',
    'accuracy', 0.95,
    title='Model Info'
)

eprint_pairs(
    'error_type', 'ValueError',
    'line', 42,
    'file', 'main.py',
    title='Exception Details'
)
```

### In-Place Message Updates (NEW)

Prevent console flooding by updating messages in place - perfect for training loops and progress tracking:

```python
from python_utils.console_utils import hprint_pairs

# Training loop example - updates same message instead of flooding console
for epoch in range(1, 101):
    hprint_pairs(
        'epoch', epoch,
        'loss', f'{1.0 / epoch:.4f}',
        'accuracy', f'{0.7 + epoch * 0.002:.2%}',
        title='Training Progress',
        message_id='training',  # Track this message by ID
        update_previous=True  # Update in place (not new line)
    )
    time.sleep(0.1)

# System monitoring - continuous status updates
while monitoring:
    hprint_pairs(
        'CPU', f'{cpu_usage}%',
        'Memory', f'{mem_usage}%',
        'Disk I/O', f'{disk_io} MB/s',
        title='System Resources',
        message_id='system',
        update_previous=True
    )
    time.sleep(1)
```

**Key Parameters:**
- `message_id` (str): Unique identifier to track this message
- `update_previous` (bool): If True, updates the previous message with same ID in place
- Works with: `hprint_pairs`, `eprint_pairs`, `wprint_pairs`, `cprint_pairs`, `hprint_message`

**Multiple Independent Trackers:**

```python
# Track different processes independently
for step in range(10):
    # Update Model A metrics
    hprint_pairs(
        'step', step,
        'loss', f'{loss_a:.3f}',
        title='Model A',
        message_id='model_a',
        update_previous=True
    )

    # Update Model B metrics (separate tracker)
    hprint_pairs(
        'step', step,
        'loss', f'{loss_b:.3f}',
        title='Model B',
        message_id='model_b',
        update_previous=True
    )
```

**Status Changes with Color:**

```python
# Update same message with different colors for status changes
hprint_pairs('status', 'Running', 'phase', 'Processing',
             title='Job Status', message_id='job', update_previous=False)

wprint_pairs('status', 'Warning', 'phase', 'Retry',
             title='Job Status', message_id='job', update_previous=True)

eprint_pairs('status', 'Failed', 'phase', 'Error',
             title='Job Status', message_id='job', update_previous=True)

hprint_pairs('status', 'Complete', 'phase', 'Done',
             title='Job Status', message_id='job', update_previous=True)
```

### Custom Section Separators (NEW)

Customize the separator line that appears after pairs with a title:

```python
# Default separator (----)
hprint_pairs('name', 'model.pt', 'size', '100MB', title='Model Info')

# Custom separator with equals
hprint_pairs(
    'epoch', 10,
    'loss', 0.05,
    title='Training Results',
    section_separator='='*40
)

# Custom pattern
hprint_pairs(
    'metric', 'value',
    title='Results',
    section_separator='-='*20
)

# No separator (empty string)
hprint_pairs(
    'key', 'value',
    title='Data',
    section_separator=''
)
```

### Vertical/Spaced Layouts (NEW)

Use newline separators for different layout styles:

```python
# Vertical layout - each pair on its own line
hprint_pairs(
    'batch', 5,
    'samples_processed', 160,
    'current_loss', 0.042,
    'throughput', '640 samples/sec',
    title='Batch Processing',
    sep='\n',                    # Newline separator
    message_id='batch',
    update_previous=True
)

# Spaced layout - blank lines between pairs
hprint_pairs(
    'checkpoint', 3,
    'model_saved', 'model_v3.pt',
    'accuracy', '89.5%',
    'size', '200 MB',
    title='Model Checkpoints',
    sep='\n\n',                  # Double newline for spacing
    message_id='checkpoint',
    update_previous=True
)
```

### Section Formatting

```python
from python_utils.console_utils import (
    hprint_section_title,
    hprint_section_separator,
    eprint_section_separator,
    wprint_section_separator,
    cprint_section_separator,
)

hprint_section_title('Data Processing Pipeline')
hprint_message('Step 1', 'Load data')
hprint_message('Step 2', 'Process data')
hprint_section_separator()
```

### Utilities

```python
from python_utils.console_utils import (
    print_attrs,
    retrieve_and_print_attrs,
    checkpoint,
)

# Print object attributes
print_attrs(my_object)

# Interactive checkpoint
checkpoint()  # Prompts user to continue
```

## Rich-Specific Features

These features are only available when Rich is installed (set to `None` if unavailable):

### Panel Printing

```python
from python_utils.console_utils import (
    cprint_panel,  # Custom colored panel
    hprint_panel,  # Cyan panel (info)
    eprint_panel,  # Red panel (error)
    wprint_panel,  # Magenta panel (warning)
)

# Check availability
if cprint_panel is not None:
    hprint_panel("Important message!", title="Notice")
    eprint_panel("Critical error occurred", title="Error")
    wprint_panel("Resource usage high", title="Warning")

    # Custom colors
    cprint_panel("Success!", title="Done", border_style="green")
```

### Tables

```python
from python_utils.console_utils import print_table

if print_table is not None:
    data = [
        {'name': 'Alice', 'age': 30, 'score': 95.5},
        {'name': 'Bob', 'age': 25, 'score': 87.3},
    ]
    print_table(data, title='Results', show_lines=True)
```

### Syntax Highlighting

```python
from python_utils.console_utils import print_syntax

if print_syntax is not None:
    code = '''
    def hello():
        print("Hello, World!")
    '''
    print_syntax(code, language='python', theme='monokai')
```

### Markdown Rendering

```python
from python_utils.console_utils import print_markdown

if print_markdown is not None:
    markdown = """
    # Project Status

    ## Completed
    - [x] Data collection
    - [x] Model training

    ## In Progress
    - [ ] Deployment
    """
    print_markdown(markdown)
```

### JSON Pretty Printing

```python
from python_utils.console_utils import print_json

if print_json is not None:
    data = {
        "model": "XGBoost",
        "metrics": {"accuracy": 0.95, "f1": 0.93}
    }
    print_json(data)
```

### Progress Bars

```python
from python_utils.console_utils import progress_bar

if progress_bar is not None:
    with progress_bar("Processing files") as progress:
        task = progress.add_task("Working...", total=100)
        for i in range(100):
            # do work
            progress.update(task, advance=1)
```

### Rich Logger

```python
from python_utils.console_utils import get_rich_logger

if get_rich_logger is not None:
    logger = get_rich_logger("my_app")
    logger.info("Application started")
    logger.error("Something went wrong")
```

### Console Instance

```python
from python_utils.console_utils import console

if console is not None:
    console.print("[bold green]Success![/bold green]")
    console.print("Rich markup supported")
```

## Textual-Specific Features (Interactive TUI)

These features are only available when Textual is installed (set to `None` if unavailable):

### Confirmation Prompts

```python
from python_utils.console_utils import prompt_confirm

if prompt_confirm is not None:
    if prompt_confirm("Delete this file?"):
        # delete file
        print("File deleted")
```

### Multiple Choice

```python
from python_utils.console_utils import prompt_choice

if prompt_choice is not None:
    choices = ['Python', 'JavaScript', 'Java', 'C++']
    index = prompt_choice("Choose your favorite language:", choices)
    if index is not None:
        print(f"You selected: {choices[index]}")
```

### Text Input with Validation

```python
from python_utils.console_utils import prompt_input

if prompt_input is not None:
    def validate_email(value):
        return '@' in value


    email = prompt_input(
        "Enter your email:",
        validator=validate_email,
        placeholder="user@example.com"
    )
```

### Interactive Table

```python
from python_utils.console_utils import display_table

if display_table is not None:
    data = [
        ['Alice', 30, 95.5],
        ['Bob', 25, 87.3],
    ]
    columns = ['Name', 'Age', 'Score']
    display_table(data, columns, title='Employee Data')
```

### Notifications

```python
from python_utils.console_utils import show_notification

if show_notification is not None:
    show_notification("Task completed!", title="Success", severity="information")
    show_notification("Low disk space", title="Warning", severity="warning")
    show_notification("Connection failed", title="Error", severity="error")
```

### Advanced TUI Apps

```python
from python_utils.console_utils import (
    ProgressDashboard,
    LogViewer,
    LiveMetrics,
    InteractiveTable,
)

# Multi-task progress tracking
if ProgressDashboard is not None:
    dashboard = ProgressDashboard()
    task1 = dashboard.add_task("Download", total=100)
    task2 = dashboard.add_task("Process", total=50)
    dashboard.run()

# Live log streaming
if LogViewer is not None:
    viewer = LogViewer()
    viewer.add_log("Application started")
    viewer.run()

# Real-time metrics
if LiveMetrics is not None:
    metrics = LiveMetrics()
    metrics.update_metric("CPU", "45%")
    metrics.run()
```

## API Reference

### Message Functions (All Backends)

- `hprint_message(*msg_pairs, title='', content='', message_id=None, update_previous=False, logger=None)` - Info messages (cyan)
- `eprint_message(*msg_pairs, title='', content='', logger=None)` - Error messages (red)
- `wprint_message(*msg_pairs, title='', content='', logger=None)` - Warning messages (magenta)
- `cprint_message(title, content, message_id=None, update_previous=False, title_color, content_color, logger=None)` - Custom colors

**New Parameters:**
- `message_id` (str, optional): Unique identifier to track this message for in-place updates
- `update_previous` (bool): If True, updates the previous message with same ID instead of printing new line

### Pairs Functions (All Backends)

- `hprint_pairs(*args, title=None, comment=None, sep='\t', message_id=None, update_previous=False, section_separator='----', logger=None)` - Info pairs
- `eprint_pairs(*args, title=None, comment=None, sep='\t', message_id=None, update_previous=False, section_separator='----', logger=None)` - Error pairs
- `wprint_pairs(*args, title=None, comment=None, sep='\t', message_id=None, update_previous=False, section_separator='----', logger=None)` - Warning pairs
- `cprint_pairs(*args, title=None, first_color, second_color, title_color, message_id=None, update_previous=False, section_separator='----', ...)` - Custom pairs

**New Parameters:**
- `message_id` (str, optional): Unique identifier to track this message for in-place updates
- `update_previous` (bool): If True, updates the previous message with same ID instead of printing new line
- `section_separator` (str): Custom separator text after pairs (default: '----')
- `sep` (str): Separator between pairs - use '\n' for vertical layout, '\n\n' for spaced layout

### Section Functions (All Backends)

- `hprint_section_title(title)` - Section header with decoration
- `hprint_section_separator()` - Cyan separator line
- `eprint_section_separator()` - Red separator line
- `wprint_section_separator()` - Magenta separator line
- `cprint_section_separator(title_color, title_style, separator_text='----')` - Custom separator

### Panel Functions (Rich Only)

- `cprint_panel(content, title=None, border_style='cyan', padding=(1,2))` - Custom panel
- `hprint_panel(content, title=None, padding=(1,2))` - Cyan panel
- `eprint_panel(content, title=None, padding=(1,2))` - Red panel
- `wprint_panel(content, title=None, padding=(1,2))` - Magenta panel

### Rich Display Functions (Rich Only)

- `print_table(data, title=None, columns=None, show_lines=False)` - Pretty tables
- `print_syntax(code, language='python', theme='monokai')` - Syntax highlighting
- `print_markdown(markdown_text)` - Render markdown
- `print_json(data, indent=2)` - Pretty JSON
- `progress_bar(description, total=None)` - Progress tracking (context manager)

### Textual Prompt Functions (Textual Only)

- `prompt_confirm(message, default=False)` - Yes/no confirmation
- `prompt_choice(message, choices, default_index=0)` - Multiple choice
- `prompt_input(message, default='', validator=None, placeholder='')` - Text input

### Textual Display Functions (Textual Only)

- `display_table(data, columns, title='Data Table')` - Interactive table
- `display_help(help_text, title='Help')` - Help viewer
- `show_notification(message, title, severity)` - Notifications

### Utility Functions (All Backends)

- `print_attrs(obj, exclude_private=True)` - Print object attributes
- `retrieve_and_print_attrs(obj, *attr_names)` - Get and print specific attributes
- `checkpoint(prompt)` - Interactive confirmation checkpoint
- `get_rich_logger(name, level=logging.INFO)` - Rich-enabled logger (Rich only)

### Special Exports

- `console` - Rich Console instance (Rich only, `None` if unavailable)
- `__backend__` - Current backend: `"rich"` or `"colorama"`
- `__has_textual__` - Boolean: Textual availability
- `__version__` - Package version

## Color Scheme

### Standard Colors (All Backends)

| Type | Title Color | Content Color | Usage |
|------|------------|---------------|-------|
| **Highlight (hprint)** | Cyan | White | Info, status, general messages |
| **Error (eprint)** | Red | Bright Yellow | Errors, exceptions |
| **Warning (wprint)** | Magenta | Yellow | Warnings, notices |
| **Custom (cprint)** | User-defined | User-defined | Custom coloring |

### Color Constants (for custom use)

```python
from python_utils.console_utils.rich_console_utils import (
    HPRINT_TITLE_COLOR,  # "cyan"
    HPRINT_HEADER_OR_HIGHLIGHT_COLOR,  # "bright_cyan"
    HPRINT_MESSAGE_BODY_COLOR,  # "white"

    EPRINT_TITLE_COLOR,  # "red"
    EPRINT_HEADER_OR_HIGHLIGHT_COLOR,  # "bright_red"
    EPRINT_MESSAGE_BODY_COLOR,  # "bright_yellow"

    WPRINT_TITLE_COLOR,  # "magenta"
    WPRINT_HEADER_OR_HIGHLIGHT_COLOR,  # "bright_magenta"
    WPRINT_MESSAGE_BODY_COLOR,  # "yellow"
)
```

## Examples

Run the example scripts to see all features in action:

```bash
# Message tracking and in-place updates (NEW - 10 examples)
python examples/python_utils/console_utils/example_pairs_update.py

# Rich console features
python examples/python_utils/console_utils/example_rich_console_usage.py

# Textual TUI features
python examples/python_utils/console_utils/example_textual_console_usage.py

# Colorama/basics features
python examples/python_utils/console_utils/example_basics_usage.py
```

**example_pairs_update.py** - Comprehensive demonstration of message tracking features:
1. Training loop metrics
2. System resource monitoring
3. Multiple independent metric sets
4. Error and warning tracking
5. Many key-value pairs
6. Custom section separators
7. Newline separators (vertical layout)
8. No title (inline updates)
9. Mixed print types (status changes)
10. Double newline separators (spaced layout)

## Migration Guide

### From colorama_console_utils to Rich

No code changes needed! The API is identical:

```python
# Old (colorama)
from python_utils.console_utils import colorama_console_utils as ccu

ccu.hprint_message('status', 'running')

# New (Rich, with automatic fallback)
from python_utils.console_utils import hprint_message

hprint_message('status', 'running')  # Works identically!
```

### Adding Enhanced Features

```python
from python_utils.console_utils import print_table, print_syntax

# Add tables (with fallback check)
if print_table is not None:
    print_table(results, title='Results')
else:
    # Fallback to basic printing
    for row in results:
        print(row)

# Add syntax highlighting (with fallback check)
if print_syntax is not None:
    print_syntax(code, language='python')
else:
    print(code)
```

### Adding Interactive Prompts

```python
from python_utils.console_utils import prompt_confirm

# Before: manual input()
user_input = input("Continue? (y/n): ")
if user_input.lower() == 'y':
# continue

# After: interactive prompt (with fallback)
if prompt_confirm is not None:
    if prompt_confirm("Continue?"):
# continue
else:
    # Fallback to input()
    user_input = input("Continue? (y/n): ")
    if user_input.lower() == 'y':
# continue
```

## Backend Detection Pattern

Best practice for handling optional features:

```python
from python_utils.console_utils import (
    __backend__,
    __has_textual__,
    print_table,
    prompt_confirm,
)

# Check backend
if __backend__ == "rich":
    print("Using Rich backend with enhanced features")
    print_table(data, title="Results")
else:
    print("Using colorama backend (basic features)")
    for row in data:
        print(row)

# Check Textual availability
if __has_textual__:
    if prompt_confirm("Continue?"):
        pass
else:
    # Fallback to basic input
    response = input("Continue? (y/n): ")
```

## Thread Safety

All modules are thread-safe and can be used in:
- Multiprocessing contexts
- Spark distributed computing
- Async applications
- Concurrent operations

## Performance

- **Rich**: Minimal overhead, optimized for console output
- **colorama**: Lightweight, fastest option
- **Textual**: Efficient async rendering, suitable for real-time displays
- **Progress bars**: Non-blocking, update in background

## Dependencies

### Required
- `colorama >= 0.4.0` - Cross-platform colored terminal output

### Optional
- `rich >= 13.0.0` - Enhanced console formatting (recommended)
- `textual >= 0.40.0` - Interactive TUI framework (optional)

## Testing

Run the test suite:

```bash
# All tests
python -m pytest test/python_utils/console_utils/

# Specific tests - Cross-implementation
python test/python_utils/console_utils/test_colorama_console_utils.py
python test/python_utils/console_utils/test_fallback_mechanism.py

# Rich implementation tests
python test/python_utils/console_utils/test_rich_console.py
python test/python_utils/console_utils/test_rich_bk_color.py
python test/python_utils/console_utils/test_rich_colors_simple.py
python test/python_utils/console_utils/test_rich_message_refactoring.py
python test/python_utils/console_utils/test_rich_new_demos.py
python test/python_utils/console_utils/test_rich_panels.py
python test/python_utils/console_utils/test_rich_section_separator_refactoring.py

# Textual implementation tests
python test/python_utils/console_utils/test_textual_console.py
python test/python_utils/console_utils/test_textual_css_color_fixes.py
```

### Test Coverage

**Core Features (All Backends):**
- ✅ Module imports and fallback mechanism
- ✅ Message printing (hprint, eprint, wprint, cprint)
- ✅ Key-value pairs printing
- ✅ **In-place message updates** (message_id, update_previous) - NEW
- ✅ **Custom section separators** (section_separator parameter) - NEW
- ✅ **Vertical/spaced layouts** (sep='\n', sep='\n\n') - NEW
- ✅ Section formatting (titles, separators)
- ✅ Color constants and bk_color parameter
- ✅ Utility functions (print_attrs, checkpoint)
- ✅ Backward compatibility with colorama implementation

**Rich-Specific Features:**
- ✅ Panel functions (cprint_panel, hprint_panel, eprint_panel, wprint_panel)
- ✅ Tables (print_table)
- ✅ Syntax highlighting (print_syntax)
- ✅ Markdown rendering (print_markdown)
- ✅ JSON pretty printing (print_json)
- ✅ Progress bars (progress_bar)
- ✅ Rich logger (get_rich_logger)
- ✅ CSS color constant integration

**Textual-Specific Features:**
- ✅ Interactive prompts (prompt_confirm, prompt_choice, prompt_input)
- ✅ Display components (display_table, display_help, show_notification)
- ✅ Advanced apps (ProgressDashboard, LogViewer, LiveMetrics, InteractiveTable)

## Advantages Over Colorama-Only

| Feature | colorama_console_utils | rich_console_utils (Enhanced) |
|---------|----------------------|------------------------------|
| **Color support** | 16 ANSI colors | 16.7M colors (true color) |
| **Tables** | Manual formatting required | Auto-formatted with borders |
| **Progress bars** | Not available | Built-in with ETA & stats |
| **Syntax highlighting** | Not available | 500+ languages supported |
| **Markdown** | Not available | Full markdown rendering |
| **Panels** | Not available | Bordered panels with styles |
| **Interactive prompts** | Basic input() | Rich TUI dialogs (Textual) |
| **JSON** | Basic print | Syntax-highlighted pretty print |
| **Code size** | ~850 lines | ~680 lines (cleaner) |
| **Maintenance** | Custom code | Community-supported libraries |
| **Performance** | Good | Excellent with caching |
| **Cross-platform** | Good | Excellent |
| **Dependencies** | colorama only | Rich + Textual (optional) |
| **Fallback** | N/A | Auto-fallback to colorama |

## Version History

**1.0.0** - Initial release (2025-01-15)
- Rich-based console utilities
- Textual-based interactive TUI
- Colorama fallback support
- Automatic backend selection
- Feature detection API

## License

Same as SciencePythonUtils package

## Authors

Science Python Utils Team

---

## Quick Reference Card

### Import Patterns

```python
# Automatic selection (recommended)
from python_utils.console_utils import (
    hprint_message, hprint_pairs,
    eprint_message, wprint_message,
    print_table, prompt_confirm,
    __backend__, __has_textual__,
)

# Specific backend
from python_utils.console_utils import rich_console_utils as rcu
from python_utils.console_utils import colorama_console_utils as ccu
from python_utils.console_utils import textual_console_utils as tcu
```

### Common Operations

```python
# Messages
hprint_message('key', 'value')
eprint_message('error', 'message')
wprint_message('warning', 'message')

# Pairs
hprint_pairs('k1', 'v1', 'k2', 'v2', title='Title')

# Sections
hprint_section_title('Section Name')
hprint_section_separator()

# Tables (Rich only)
if print_table: print_table(data, title='Results')

# Panels (Rich only)
if hprint_panel: hprint_panel("Message", title="Info")

# Prompts (Textual only)
if prompt_confirm: result = prompt_confirm("Continue?")
```

### Feature Detection

```python
# Check backend
print(f"Backend: {__backend__}")  # "rich" or "colorama"

# Check features
if print_table is not None:
    # Use Rich features
    pass

if __has_textual__:
    # Use Textual features
    pass
```
