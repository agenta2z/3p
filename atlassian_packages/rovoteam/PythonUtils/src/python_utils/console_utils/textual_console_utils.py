"""
Textual-based interactive TUI utility module.

Provides interactive terminal user interfaces for prompts, data display,
progress tracking, and more using the Textual framework.

Author: Science Python Utils
Date: 2025-01-15
"""

from typing import List, Optional, Callable, Any, Dict, Union
from textual.app import App, ComposeResult
from textual.widgets import (
    Header,
    Footer,
    DataTable,
    Static,
    Button,
    Input,
    Label,
    ProgressBar,
    Log,
    Placeholder,
    Select,
)
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.screen import Screen
from textual import events
from textual.binding import Binding
from rich.text import Text
from rich.panel import Panel
import asyncio
from datetime import datetime

# Color constants for consistency with basics.py
# These match the colorama-based colors used in basics.py
HPRINT_TITLE_COLOR = "cyan"
HPRINT_HEADER_OR_HIGHLIGHT_COLOR = "bright_cyan"
HPRINT_MESSAGE_BODY_COLOR = "white"

EPRINT_TITLE_COLOR = "red"
EPRINT_HEADER_OR_HIGHLIGHT_COLOR = "bright_red"
EPRINT_MESSAGE_BODY_COLOR = "bright_yellow"

WPRINT_TITLE_COLOR = "magenta"
WPRINT_HEADER_OR_HIGHLIGHT_COLOR = "bright_magenta"
WPRINT_MESSAGE_BODY_COLOR = "yellow"

# region Prompt Utilities

class ConfirmScreen(Screen):
    """Screen for yes/no confirmation prompts."""

    BINDINGS = [
        ("y", "confirm", "Yes"),
        ("n", "deny", "No"),
        ("escape", "deny", "Cancel"),
    ]

    def __init__(self, message: str, default: bool = False):
        super().__init__()
        self.message = message
        self.result = default

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static(f"\n{self.message}\n", id="prompt-message"),
            Horizontal(
                Button("Yes (y)", variant="success", id="yes-btn"),
                Button("No (n)", variant="error", id="no-btn"),
            ),
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "yes-btn":
            self.result = True
            self.app.exit(self.result)
        else:
            self.result = False
            self.app.exit(self.result)

    def action_confirm(self) -> None:
        self.result = True
        self.app.exit(self.result)

    def action_deny(self) -> None:
        self.result = False
        self.app.exit(self.result)


class ConfirmApp(App):
    """App for confirmation prompts."""

    def __init__(self, message: str, default: bool = False):
        super().__init__()
        self.message = message
        self.default = default

    def on_mount(self) -> None:
        self.push_screen(ConfirmScreen(self.message, self.default))


def prompt_confirm(message: str, default: bool = False) -> bool:
    """
    Interactive yes/no confirmation prompt.

    Example:
        >>> if prompt_confirm("Delete this file?"):
        ...     # Delete the file
        ...     pass

    Args:
        message: The confirmation message to display
        default: Default value if user cancels

    Returns:
        True if user confirmed, False otherwise
    """
    app = ConfirmApp(message, default)
    result = app.run()
    return result if result is not None else default


class ChoiceScreen(Screen):
    """Screen for multiple choice selection."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("enter", "select", "Select"),
    ]

    def __init__(self, message: str, choices: List[str], default_index: int = 0):
        super().__init__()
        self.message = message
        self.choices = choices
        self.selected_index = default_index
        self.result = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static(f"\n{self.message}\n", id="choice-message"),
            Select(
                options=[(choice, i) for i, choice in enumerate(self.choices)],
                value=self.selected_index,
                id="choice-select",
            ),
            Button("Select", variant="primary", id="select-btn"),
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "select-btn":
            select = self.query_one("#choice-select", Select)
            self.result = select.value
            self.app.exit(self.result)

    def action_select(self) -> None:
        select = self.query_one("#choice-select", Select)
        self.result = select.value
        self.app.exit(self.result)

    def action_cancel(self) -> None:
        self.app.exit(None)


class ChoiceApp(App):
    """App for choice prompts."""

    def __init__(self, message: str, choices: List[str], default_index: int = 0):
        super().__init__()
        self.message = message
        self.choices = choices
        self.default_index = default_index

    def on_mount(self) -> None:
        self.push_screen(ChoiceScreen(self.message, self.choices, self.default_index))


def prompt_choice(
    message: str,
    choices: List[str],
    default_index: int = 0
) -> Optional[int]:
    """
    Interactive multiple choice prompt.

    Example:
        >>> choices = ['Option A', 'Option B', 'Option C']
        >>> index = prompt_choice("Select an option:", choices)
        >>> if index is not None:
        ...     print(f"Selected: {choices[index]}")

    Args:
        message: The prompt message
        choices: List of choice strings
        default_index: Default selected index

    Returns:
        Index of selected choice, or None if cancelled
    """
    app = ChoiceApp(message, choices, default_index)
    return app.run()


class InputScreen(Screen):
    """Screen for text input with validation."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("ctrl+s", "submit", "Submit"),
    ]

    def __init__(
        self,
        message: str,
        default: str = "",
        validator: Optional[Callable[[str], bool]] = None,
        placeholder: str = "",
    ):
        super().__init__()
        self.message = message
        self.default = default
        self.validator = validator
        self.placeholder_text = placeholder
        self.result = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static(f"\n{self.message}\n", id="input-message"),
            Input(
                value=self.default,
                placeholder=self.placeholder_text,
                id="text-input",
            ),
            Static("", id="validation-message"),
            Button("Submit (Ctrl+S)", variant="primary", id="submit-btn"),
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "submit-btn":
            self.do_submit()

    def action_submit(self) -> None:
        self.do_submit()

    def action_cancel(self) -> None:
        self.app.exit(None)

    def do_submit(self) -> None:
        input_widget = self.query_one("#text-input", Input)
        value = input_widget.value

        # Validate if validator provided
        if self.validator is not None:
            if not self.validator(value):
                validation_msg = self.query_one("#validation-message", Static)
                validation_msg.update("[red]Invalid input. Please try again.[/red]")
                return

        self.result = value
        self.app.exit(self.result)


class InputApp(App):
    """App for text input prompts."""

    def __init__(
        self,
        message: str,
        default: str = "",
        validator: Optional[Callable[[str], bool]] = None,
        placeholder: str = "",
    ):
        super().__init__()
        self.message = message
        self.default = default
        self.validator = validator
        self.placeholder = placeholder

    def on_mount(self) -> None:
        self.push_screen(
            InputScreen(self.message, self.default, self.validator, self.placeholder)
        )


def prompt_input(
    message: str,
    default: str = "",
    validator: Optional[Callable[[str], bool]] = None,
    placeholder: str = "",
) -> Optional[str]:
    """
    Interactive text input prompt with optional validation.

    Example:
        >>> def validate_email(value):
        ...     return '@' in value
        >>> email = prompt_input(
        ...     "Enter your email:",
        ...     validator=validate_email,
        ...     placeholder="user@example.com"
        ... )

    Args:
        message: The input prompt message
        default: Default value
        validator: Optional validation function
        placeholder: Placeholder text

    Returns:
        User input string, or None if cancelled
    """
    app = InputApp(message, default, validator, placeholder)
    return app.run()

# endregion

# region Progress Display

class ProgressDashboard(App):
    """
    Interactive dashboard for tracking multiple progress tasks.

    Example:
        >>> dashboard = ProgressDashboard()
        >>> task1 = dashboard.add_task("Processing files", total=100)
        >>> task2 = dashboard.add_task("Uploading data", total=50)
        >>> # Update progress
        >>> dashboard.update_task(task1, completed=50)
    """

    CSS = f"""
    #progress-container {{
        padding: 1;
        height: 100%;
    }}
    .progress-item {{
        margin: 1;
        padding: 1;
        border: solid {HPRINT_TITLE_COLOR};
    }}
    """

    def __init__(self):
        super().__init__()
        self.tasks: Dict[str, Dict[str, Any]] = {}

    def compose(self) -> ComposeResult:
        yield Header()
        yield ScrollableContainer(id="progress-container")
        yield Footer()

    def add_task(self, description: str, total: int = 100) -> str:
        """Add a new progress task."""
        task_id = f"task_{len(self.tasks)}"
        self.tasks[task_id] = {
            "description": description,
            "total": total,
            "completed": 0,
        }
        self._update_display()
        return task_id

    def update_task(self, task_id: str, completed: int) -> None:
        """Update task progress."""
        if task_id in self.tasks:
            self.tasks[task_id]["completed"] = completed
            self._update_display()

    def _update_display(self) -> None:
        """Refresh the progress display."""
        container = self.query_one("#progress-container")
        container.remove_children()

        for task_id, task in self.tasks.items():
            progress = (task["completed"] / task["total"]) * 100 if task["total"] > 0 else 0
            widget = Static(
                f"{task['description']}: {task['completed']}/{task['total']} ({progress:.1f}%)",
                classes="progress-item",
            )
            container.mount(widget)

# endregion

# region Data Display

class InteractiveTable(App):
    """
    Interactive scrollable and searchable data table.

    Example:
        >>> data = [
        ...     ['Alice', 30, 95.5],
        ...     ['Bob', 25, 87.3],
        ...     ['Charlie', 35, 92.1],
        ... ]
        >>> columns = ['Name', 'Age', 'Score']
        >>> table = InteractiveTable(data, columns, title='Results')
        >>> table.run()
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("s", "search", "Search"),
    ]

    def __init__(
        self,
        data: List[List[Any]],
        columns: List[str],
        title: str = "Data Table",
    ):
        super().__init__()
        self.data = data
        self.columns = columns
        self.title_text = title

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(f"\n{self.title_text}\n", id="table-title")
        yield DataTable(id="data-table")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns(*self.columns)
        for row in self.data:
            table.add_row(*[str(cell) for cell in row])

    def action_search(self) -> None:
        """Implement search functionality (placeholder)."""
        pass


def display_table(
    data: List[List[Any]],
    columns: List[str],
    title: str = "Data Table",
) -> None:
    """
    Display interactive data table.

    Example:
        >>> data = [['A', 1], ['B', 2], ['C', 3]]
        >>> display_table(data, ['Letter', 'Number'], title='Simple Table')
    """
    app = InteractiveTable(data, columns, title)
    app.run()

# endregion

# region Log Viewer

class LogViewer(App):
    """
    Live log streaming viewer.

    Example:
        >>> viewer = LogViewer()
        >>> viewer.add_log("Application started")
        >>> viewer.add_log("Processing data...")
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("c", "clear", "Clear"),
    ]

    CSS = f"""
    #log-container {{
        height: 100%;
        border: solid {HPRINT_TITLE_COLOR};
    }}
    """

    def compose(self) -> ComposeResult:
        yield Header()
        yield Log(id="log-container", auto_scroll=True)
        yield Footer()

    def add_log(self, message: str) -> None:
        """Add a log message."""
        log = self.query_one(Log)
        timestamp = datetime.now().strftime("%H:%M:%S")
        log.write_line(f"[{timestamp}] {message}")

    def action_clear(self) -> None:
        """Clear all logs."""
        log = self.query_one(Log)
        log.clear()

# endregion

# region Notifications

def show_notification(
    message: str,
    title: str = "Notification",
    severity: str = "information",
) -> None:
    """
    Show a notification message.

    Note: This is a simplified version. In a real Textual app,
    notifications would be shown within an existing app context.

    Example:
        >>> show_notification("Task completed!", title="Success", severity="information")

    Args:
        message: Notification message
        title: Notification title
        severity: One of 'information', 'warning', 'error'
    """
    # This would typically be implemented as part of a larger app
    # For now, we'll print a panel
    from rich.console import Console
    from rich.panel import Panel

    console = Console()

    style_map = {
        "information": HPRINT_TITLE_COLOR,
        "warning": WPRINT_TITLE_COLOR,
        "error": EPRINT_TITLE_COLOR,
    }
    style = style_map.get(severity, HPRINT_TITLE_COLOR)

    panel = Panel(
        message,
        title=title,
        border_style=style,
        padding=(1, 2),
    )
    console.print(panel)

# endregion

# region Help Display

class HelpScreen(Screen):
    """Interactive help display screen."""

    BINDINGS = [
        ("escape", "close", "Close"),
        ("q", "close", "Quit"),
    ]

    def __init__(self, help_text: str, title: str = "Help"):
        super().__init__()
        self.help_text = help_text
        self.title_text = title

    def compose(self) -> ComposeResult:
        yield Header()
        yield ScrollableContainer(
            Static(f"# {self.title_text}\n\n{self.help_text}", id="help-content"),
        )
        yield Footer()

    def action_close(self) -> None:
        self.app.pop_screen()


class HelpApp(App):
    """App for displaying help."""

    def __init__(self, help_text: str, title: str = "Help"):
        super().__init__()
        self.help_text = help_text
        self.title = title

    def on_mount(self) -> None:
        self.push_screen(HelpScreen(self.help_text, self.title))


def display_help(help_text: str, title: str = "Help") -> None:
    """
    Display interactive help panel.

    Example:
        >>> help_text = '''
        ... ## Commands
        ... - Press 'q' to quit
        ... - Press 's' to search
        ... - Press 'h' for help
        ... '''
        >>> display_help(help_text, title="Application Help")

    Args:
        help_text: Help text content (supports markdown)
        title: Help panel title
    """
    app = HelpApp(help_text, title)
    app.run()

# endregion

# region Metrics Display

class LiveMetrics(App):
    """
    Live metrics display that updates in real-time.

    Example:
        >>> metrics = LiveMetrics()
        >>> metrics.update_metric("CPU", "45%")
        >>> metrics.update_metric("Memory", "2.3 GB")
    """

    CSS = f"""
    #metrics-container {{
        padding: 1;
        border: solid {HPRINT_TITLE_COLOR};
        height: 100%;
    }}
    .metric-item {{
        margin: 1;
        padding: 1;
    }}
    """

    def __init__(self):
        super().__init__()
        self.metrics: Dict[str, str] = {}

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(id="metrics-container")
        yield Footer()

    def update_metric(self, name: str, value: str) -> None:
        """Update or add a metric."""
        self.metrics[name] = value
        self._refresh_display()

    def _refresh_display(self) -> None:
        """Refresh the metrics display."""
        container = self.query_one("#metrics-container")
        container.remove_children()

        for name, value in self.metrics.items():
            widget = Static(
                f"[{HPRINT_HEADER_OR_HIGHLIGHT_COLOR}]{name}:[/{HPRINT_HEADER_OR_HIGHLIGHT_COLOR}] [{HPRINT_MESSAGE_BODY_COLOR}]{value}[/{HPRINT_MESSAGE_BODY_COLOR}]",
                classes="metric-item",
            )
            container.mount(widget)

# endregion

# region Utility Functions

def run_tui_app(app_class: type, *args, **kwargs) -> Any:
    """
    Helper to run a Textual app and return its result.

    Example:
        >>> result = run_tui_app(ConfirmApp, "Are you sure?")
    """
    app = app_class(*args, **kwargs)
    return app.run()

# endregion
