"""
Interactive TUI examples using textual_console_utils.py (Textual framework)

This demonstrates:
- Interactive prompts (confirm, choice, input with validation)
- Progress dashboards with live updates
- Interactive data tables
- Log viewer with streaming
- Help display system
- Live metrics dashboard
- Notification system
- Complete TUI application example

Prerequisites:
    textual (automatically installed with python_utils)

Usage:
    python example_textual_console_usage.py

Note: This example contains interactive components that require user input.
      Some demonstrations are commented out to allow non-interactive running.
      Uncomment sections to try interactive features.
"""

import time
from python_utils.console_utils.textual_console_utils import (
    # Prompts
    prompt_confirm, prompt_choice, prompt_input,
    # Progress
    ProgressDashboard,
    # Data display
    display_table,
    # Log viewer
    LogViewer,
    # Notifications
    show_notification,
    # Help
    display_help,
    # Metrics
    LiveMetrics,
)
from python_utils.console_utils.rich_console_utils import (
    console, hprint_section_title, cprint_panel
)


def demo_interactive_prompts():
    """Demonstrate interactive prompts (commented out to avoid blocking)."""
    hprint_section_title("Interactive Prompts")

    console.print("[bold]Examples of interactive prompts:[/bold]\n")

    console.print("[cyan]1. Confirmation Prompt:[/cyan]")
    console.print("   [dim]# result = prompt_confirm('Delete this file?')[/dim]")
    console.print("   [dim]# if result:[/dim]")
    console.print("   [dim]#     print('File deleted')[/dim]\n")

    # UNCOMMENT TO TRY:
    # result = prompt_confirm("Do you want to continue?")
    # console.print(f"User responded: {result}\n")

    console.print("[cyan]2. Choice Prompt:[/cyan]")
    console.print("   [dim]# choices = ['Option A', 'Option B', 'Option C'][/dim]")
    console.print("   [dim]# selected = prompt_choice('Select an option:', choices)[/dim]")
    console.print("   [dim]# print(f'You selected: {choices[selected]}')[/dim]\n")

    # UNCOMMENT TO TRY:
    # choices = ['Python', 'JavaScript', 'Java', 'C++', 'Go']
    # selected = prompt_choice("Choose your favorite language:", choices)
    # if selected is not None:
    #     console.print(f"You selected: {choices[selected]}\n")

    console.print("[cyan]3. Text Input Prompt with Validation:[/cyan]")
    console.print("   [dim]# def validate_email(value):[/dim]")
    console.print("   [dim]#     return '@' in value[/dim]")
    console.print("   [dim]# email = prompt_input('Enter email:', validator=validate_email)[/dim]\n")

    # UNCOMMENT TO TRY:
    # def validate_number(value):
    #     try:
    #         int(value)
    #         return True
    #     except:
    #         return False
    #
    # number = prompt_input(
    #     "Enter a number:",
    #     validator=validate_number,
    #     placeholder="Type a number..."
    # )
    # if number:
    #     console.print(f"You entered: {number}\n")

    console.print("[green]✓ Uncomment the code above to try interactive prompts![/green]\n")


def demo_notifications():
    """Demonstrate notification system."""
    hprint_section_title("Notifications")

    console.print("[bold]Notification examples:[/bold]\n")

    console.print("[cyan]Information notification:[/cyan]")
    show_notification("Task completed successfully!", title="Information", severity="information")

    console.print("\n[cyan]Warning notification:[/cyan]")
    show_notification("Low disk space detected", title="Warning", severity="warning")

    console.print("\n[cyan]Error notification:[/cyan]")
    show_notification("Connection to database failed", title="Error", severity="error")

    console.print("\n[green]✓ Notifications displayed using Rich panels[/green]\n")


def demo_help_display():
    """Demonstrate help display system (commented out to avoid blocking)."""
    hprint_section_title("Help Display System")

    console.print("[bold]Help display example:[/bold]\n")

    help_text = """## Application Help

### Commands
- Press 'q' or 'escape' to quit
- Press 's' to search
- Press 'h' for help
- Press 'r' to refresh

### Features
- Interactive navigation with arrow keys
- Keyboard shortcuts for common actions
- Real-time updates and monitoring

### Tips
- Use Ctrl+C to interrupt long operations
- Check the status bar for current mode
- Hover over items for tooltips
"""

    console.print("[dim]Help text content:[/dim]")
    console.print(help_text)

    console.print("\n[yellow]To display interactive help:[/yellow]")
    console.print("[dim]# display_help(help_text, title='Application Guide')[/dim]")

    # UNCOMMENT TO TRY:
    # display_help(help_text, title="Application Guide")

    console.print("\n[green]✓ Uncomment to launch interactive help viewer[/green]\n")


def demo_data_table():
    """Demonstrate interactive data table (commented out to avoid blocking)."""
    hprint_section_title("Interactive Data Tables")

    console.print("[bold]Interactive table example:[/bold]\n")

    # Sample data
    data = [
        ['Alice', 30, 95.5, 'Engineering'],
        ['Bob', 25, 87.3, 'Marketing'],
        ['Charlie', 35, 92.1, 'Sales'],
        ['Diana', 28, 88.9, 'Engineering'],
        ['Eve', 32, 91.2, 'HR'],
        ['Frank', 29, 85.7, 'Marketing'],
    ]
    columns = ['Name', 'Age', 'Score', 'Department']

    console.print("[dim]Sample data (6 rows, 4 columns):[/dim]")
    from rich.table import Table
    preview_table = Table(title="Employee Data")
    for col in columns:
        preview_table.add_column(col, style="cyan")
    for row in data[:3]:  # Show first 3 rows
        preview_table.add_row(*[str(cell) for cell in row])
    console.print(preview_table)

    console.print("\n[yellow]To display interactive table:[/yellow]")
    console.print("[dim]# display_table(data, columns, title='Employee Data')[/dim]")

    # UNCOMMENT TO TRY:
    # display_table(data, columns, title='Employee Data')

    console.print("\n[green]✓ Uncomment to launch interactive table with search & navigation[/green]\n")


def demo_progress_dashboard_code():
    """Demonstrate progress dashboard code (non-interactive)."""
    hprint_section_title("Progress Dashboard")

    console.print("[bold]Progress dashboard example code:[/bold]\n")

    code = '''# Create progress dashboard
dashboard = ProgressDashboard()

# Add tasks
task1 = dashboard.add_task("Downloading files", total=100)
task2 = dashboard.add_task("Processing data", total=50)
task3 = dashboard.add_task("Uploading results", total=75)

# Update progress (in your application loop)
dashboard.update_task(task1, completed=50)
dashboard.update_task(task2, completed=25)
dashboard.update_task(task3, completed=10)

# Run the dashboard
dashboard.run()
'''

    from python_utils.console_utils.rich_console_utils import print_syntax
    print_syntax(code, language='python')

    console.print("\n[green]✓ Dashboard tracks multiple concurrent tasks with live updates[/green]\n")


def demo_log_viewer_code():
    """Demonstrate log viewer code (non-interactive)."""
    hprint_section_title("Log Viewer")

    console.print("[bold]Log viewer example code:[/bold]\n")

    code = '''# Create log viewer
viewer = LogViewer()

# Add log messages (can be called from anywhere)
viewer.add_log("Application started")
viewer.add_log("Loading configuration...")
viewer.add_log("Connected to database")
viewer.add_log("Processing 1000 records")
viewer.add_log("Task completed successfully")

# Run the viewer (displays logs in real-time)
viewer.run()
'''

    from python_utils.console_utils.rich_console_utils import print_syntax
    print_syntax(code, language='python')

    console.print("\n[green]✓ Log viewer supports auto-scroll and clear operations[/green]\n")


def demo_live_metrics_code():
    """Demonstrate live metrics code (non-interactive)."""
    hprint_section_title("Live Metrics Dashboard")

    console.print("[bold]Live metrics example code:[/bold]\n")

    code = '''# Create metrics dashboard
metrics = LiveMetrics()

# Update metrics (in your monitoring loop)
metrics.update_metric("CPU Usage", "45%")
metrics.update_metric("Memory", "2.3 / 8 GB")
metrics.update_metric("Disk", "120 / 500 GB")
metrics.update_metric("Network In", "1.2 MB/s")
metrics.update_metric("Network Out", "0.8 MB/s")
metrics.update_metric("Active Connections", "127")

# Metrics auto-refresh on updates
# Run the dashboard
metrics.run()
'''

    from python_utils.console_utils.rich_console_utils import print_syntax
    print_syntax(code, language='python')

    console.print("\n[green]✓ Metrics update in real-time as values change[/green]\n")


def demo_complete_tui_app():
    """Demonstrate a complete TUI application example."""
    hprint_section_title("Complete TUI Application")

    console.print("[bold]Full application example:[/bold]\n")

    code = '''from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Button
from textual.containers import Container, Vertical
from python_utils.console_utils.textual_console_utils import (
    prompt_confirm, prompt_choice
)

class MyApp(App):
    """A complete TUI application."""

    CSS = """
    Screen {
        background: $surface;
    }

    #main-container {
        padding: 1;
        border: solid $primary;
        height: 100%;
    }

    Button {
        margin: 1;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("h", "help", "Help"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static("Welcome to My Application!", id="welcome"),
            Button("Start Task", variant="success", id="start-btn"),
            Button("Settings", variant="primary", id="settings-btn"),
            Button("Exit", variant="error", id="exit-btn"),
            id="main-container"
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start-btn":
            self.notify("Task started!")
        elif event.button.id == "exit-btn":
            self.exit()

    def action_help(self) -> None:
        self.notify("Help: Press 'q' to quit")

if __name__ == "__main__":
    app = MyApp()
    app.run()
'''

    from python_utils.console_utils.rich_console_utils import print_syntax
    print_syntax(code, language='python')

    console.print("\n[green]✓ Complete TUI apps can combine all components![/green]\n")


def demo_practical_workflows():
    """Demonstrate practical workflow examples."""
    hprint_section_title("Practical Workflows")

    console.print("[bold]1. Configuration Wizard Workflow:[/bold]\n")

    workflow1 = '''# Interactive configuration wizard
print("Setting up application configuration...")

# Step 1: Choose environment
env_choices = ['Development', 'Staging', 'Production']
env = prompt_choice("Select environment:", env_choices)

# Step 2: Confirm database settings
use_db = prompt_confirm("Enable database connection?")

if use_db:
    # Step 3: Enter database details
    def validate_port(val):
        try:
            return 1 <= int(val) <= 65535
        except:
            return False

    db_host = prompt_input("Database host:", default="localhost")
    db_port = prompt_input("Database port:", validator=validate_port, default="5432")

# Step 4: Confirm and save
if prompt_confirm("Save configuration?"):
    print("Configuration saved!")
'''

    from python_utils.console_utils.rich_console_utils import print_syntax
    print_syntax(workflow1, language='python')

    console.print("\n[bold]2. Monitoring Dashboard Workflow:[/bold]\n")

    workflow2 = '''# Real-time monitoring dashboard
import asyncio

metrics = LiveMetrics()

async def update_metrics():
    """Simulate real-time metric updates."""
    while True:
        # Update system metrics
        cpu = get_cpu_usage()
        mem = get_memory_usage()
        disk = get_disk_usage()

        metrics.update_metric("CPU", f"{cpu}%")
        metrics.update_metric("Memory", f"{mem} GB")
        metrics.update_metric("Disk", f"{disk}%")

        await asyncio.sleep(1)

# Run dashboard with live updates
asyncio.run(update_metrics())
'''

    print_syntax(workflow2, language='python')

    console.print("\n[green]✓ Workflows combine multiple components for complete UX[/green]\n")


def demo_best_practices():
    """Show best practices for TUI development."""
    hprint_section_title("Best Practices")

    cprint_panel("""**TUI Development Best Practices:**

1. **User Feedback**
   - Always provide visual feedback for actions
   - Use notifications for confirmations
   - Show progress for long operations

2. **Keyboard Navigation**
   - Support common shortcuts (q=quit, h=help, etc.)
   - Implement escape for cancel operations
   - Use arrow keys for navigation

3. **Error Handling**
   - Validate user input before processing
   - Provide clear error messages
   - Allow users to retry failed operations

4. **Performance**
   - Update UI only when necessary
   - Use async operations for long tasks
   - Implement proper cleanup on exit

5. **Accessibility**
   - Use high-contrast colors
   - Provide keyboard alternatives for all actions
   - Include helpful tooltips and labels
""", title="Best Practices", border_style="cyan")

    console.print()


def demo_comparison_with_cli():
    """Compare TUI with traditional CLI."""
    hprint_section_title("TUI vs CLI Comparison")

    from rich.table import Table

    comparison = Table(title="TUI vs Traditional CLI")
    comparison.add_column("Feature", style="cyan", width=20)
    comparison.add_column("TUI (Textual)", style="green", width=30)
    comparison.add_column("CLI (argparse)", style="yellow", width=30)

    comparison.add_row(
        "User Interaction",
        "Interactive, real-time",
        "Command-line arguments"
    )
    comparison.add_row(
        "Visual Feedback",
        "Rich UI with colors/borders",
        "Plain text output"
    )
    comparison.add_row(
        "Data Display",
        "Tables, panels, dashboards",
        "Line-by-line text"
    )
    comparison.add_row(
        "User Guidance",
        "Interactive prompts, help",
        "Help text, man pages"
    )
    comparison.add_row(
        "Progress Tracking",
        "Live progress bars",
        "Percentage text updates"
    )
    comparison.add_row(
        "Error Handling",
        "In-place error messages",
        "Error text to stderr"
    )
    comparison.add_row(
        "Best For",
        "Interactive apps, dashboards",
        "Automation, scripting"
    )

    console.print(comparison)
    console.print()


if __name__ == "__main__":
    console.print("\n[bold white on magenta]" + " "*80 + "[/]")
    console.print("[bold white on magenta]" + " "*18 + "TEXTUAL CONSOLE UTILS USAGE EXAMPLES" + " "*26 + "[/]")
    console.print("[bold white on magenta]" + " "*80 + "[/]")

    # Non-interactive demos
    demo_notifications()
    demo_interactive_prompts()  # Shows code examples
    demo_help_display()  # Shows code examples
    demo_data_table()  # Shows preview
    demo_progress_dashboard_code()
    demo_log_viewer_code()
    demo_live_metrics_code()
    demo_complete_tui_app()
    demo_practical_workflows()
    demo_best_practices()
    demo_comparison_with_cli()

    console.print("=" * 80, style="bold green")
    console.print("[bold green]✓ ALL EXAMPLES COMPLETED![/bold green]", justify="center")
    console.print("=" * 80 + "\n", style="bold green")

    console.print("[bold yellow]To try interactive features:[/bold yellow]")
    console.print("  1. Edit this file and uncomment the interactive sections")
    console.print("  2. Run again to experience full TUI capabilities")
    console.print("  3. Use ESC or 'q' to exit interactive components\n")

    console.print("[bold cyan]Interactive demos available:[/bold cyan]")
    console.print("  • prompt_confirm() - Yes/No prompts")
    console.print("  • prompt_choice() - Multiple choice selection")
    console.print("  • prompt_input() - Text input with validation")
    console.print("  • display_table() - Interactive data tables")
    console.print("  • display_help() - Help viewer")
    console.print("  • ProgressDashboard() - Multi-task progress tracking")
    console.print("  • LogViewer() - Real-time log streaming")
    console.print("  • LiveMetrics() - Live metrics dashboard\n")
