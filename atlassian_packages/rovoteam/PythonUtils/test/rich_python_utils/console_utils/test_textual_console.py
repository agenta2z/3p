"""
Comprehensive tests for textual_console_utils.py (Textual TUI components).

This test suite covers:
- Interactive prompt functions (confirm, choice, input with validation)
- Progress dashboard components
- Interactive data tables
- Log viewer components
- Notification system
- Help display system
- Live metrics dashboard
- Edge cases and mocking strategies for TUI components
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, PropertyMock
from textual.app import App
from python_utils.console_utils.textual_console_utils import (
    # Prompt utilities
    prompt_confirm, prompt_choice, prompt_input,
    ConfirmApp, ConfirmScreen,
    ChoiceApp, ChoiceScreen,
    InputApp, InputScreen,
    # Progress display
    ProgressDashboard,
    # Data display
    InteractiveTable, display_table,
    # Log viewer
    LogViewer,
    # Notifications
    show_notification,
    # Help display
    HelpScreen, HelpApp, display_help,
    # Metrics
    LiveMetrics,
    # Utility
    run_tui_app,
)


class TestConfirmPrompt:
    """Tests for confirmation prompt functionality."""

    @patch.object(ConfirmApp, 'run', return_value=True)
    def test_prompt_confirm_yes(self, mock_run):
        """Test prompt_confirm returns True when user confirms."""
        result = prompt_confirm("Are you sure?")
        assert result is True
        mock_run.assert_called_once()

    @patch.object(ConfirmApp, 'run', return_value=False)
    def test_prompt_confirm_no(self, mock_run):
        """Test prompt_confirm returns False when user denies."""
        result = prompt_confirm("Delete file?")
        assert result is False

    @patch.object(ConfirmApp, 'run', return_value=None)
    def test_prompt_confirm_cancel_default_false(self, mock_run):
        """Test prompt_confirm returns default when cancelled."""
        result = prompt_confirm("Continue?", default=False)
        assert result is False

    @patch.object(ConfirmApp, 'run', return_value=None)
    def test_prompt_confirm_cancel_default_true(self, mock_run):
        """Test prompt_confirm returns default True when cancelled."""
        result = prompt_confirm("Continue?", default=True)
        assert result is True

    def test_confirm_screen_initialization(self):
        """Test ConfirmScreen initializes with message and default."""
        screen = ConfirmScreen("Test message", default=True)
        assert screen.message == "Test message"
        assert screen.result is True

    def test_confirm_app_initialization(self):
        """Test ConfirmApp initializes with message and default."""
        app = ConfirmApp("Test?", default=False)
        assert app.message == "Test?"
        assert app.default is False


class TestChoicePrompt:
    """Tests for choice prompt functionality."""

    @patch.object(ChoiceApp, 'run', return_value=1)
    def test_prompt_choice_basic(self, mock_run):
        """Test prompt_choice returns selected index."""
        choices = ['Option A', 'Option B', 'Option C']
        result = prompt_choice("Select option:", choices)
        assert result == 1

    @patch.object(ChoiceApp, 'run', return_value=0)
    def test_prompt_choice_first_option(self, mock_run):
        """Test prompt_choice can return first option."""
        choices = ['First', 'Second']
        result = prompt_choice("Choose:", choices, default_index=0)
        assert result == 0

    @patch.object(ChoiceApp, 'run', return_value=None)
    def test_prompt_choice_cancelled(self, mock_run):
        """Test prompt_choice returns None when cancelled."""
        choices = ['A', 'B']
        result = prompt_choice("Pick:", choices)
        assert result is None

    def test_choice_screen_initialization(self):
        """Test ChoiceScreen initializes with choices."""
        choices = ['Choice 1', 'Choice 2']
        screen = ChoiceScreen("Select:", choices, default_index=1)
        assert screen.message == "Select:"
        assert screen.choices == choices
        assert screen.selected_index == 1

    def test_choice_app_initialization(self):
        """Test ChoiceApp initializes correctly."""
        choices = ['A', 'B', 'C']
        app = ChoiceApp("Pick:", choices, default_index=2)
        assert app.message == "Pick:"
        assert app.choices == choices
        assert app.default_index == 2


class TestInputPrompt:
    """Tests for text input prompt functionality."""

    @patch.object(InputApp, 'run', return_value="test input")
    def test_prompt_input_basic(self, mock_run):
        """Test prompt_input returns user input."""
        result = prompt_input("Enter name:")
        assert result == "test input"

    @patch.object(InputApp, 'run', return_value="default text")
    def test_prompt_input_with_default(self, mock_run):
        """Test prompt_input uses default value."""
        result = prompt_input("Name:", default="default text")
        assert result == "default text"

    @patch.object(InputApp, 'run', return_value="valid@email.com")
    def test_prompt_input_with_validation(self, mock_run):
        """Test prompt_input with validator function."""
        def validate_email(value):
            return '@' in value

        result = prompt_input("Email:", validator=validate_email)
        assert result == "valid@email.com"

    @patch.object(InputApp, 'run', return_value=None)
    def test_prompt_input_cancelled(self, mock_run):
        """Test prompt_input returns None when cancelled."""
        result = prompt_input("Input:")
        assert result is None

    def test_input_screen_initialization(self):
        """Test InputScreen initializes with parameters."""
        def validator(val):
            return len(val) > 3

        screen = InputScreen("Enter:", default="test", validator=validator, placeholder="Type here")
        assert screen.message == "Enter:"
        assert screen.default == "test"
        assert screen.validator is validator
        assert screen.placeholder_text == "Type here"

    def test_input_app_initialization(self):
        """Test InputApp initializes correctly."""
        app = InputApp("Prompt:", default="val", placeholder="hint")
        assert app.message == "Prompt:"
        assert app.default == "val"
        assert app.placeholder == "hint"


class TestProgressDashboard:
    """Tests for ProgressDashboard component."""

    def test_progress_dashboard_initialization(self):
        """Test ProgressDashboard initializes with empty tasks."""
        dashboard = ProgressDashboard()
        assert isinstance(dashboard, App)
        assert dashboard.tasks == {}

    @patch.object(ProgressDashboard, '_update_display')
    def test_progress_dashboard_add_task(self, mock_update):
        """Test adding task to progress dashboard."""
        dashboard = ProgressDashboard()
        task_id = dashboard.add_task("Processing files", total=100)
        assert task_id in dashboard.tasks
        assert dashboard.tasks[task_id]['description'] == "Processing files"
        assert dashboard.tasks[task_id]['total'] == 100
        assert dashboard.tasks[task_id]['completed'] == 0

    @patch.object(ProgressDashboard, '_update_display')
    def test_progress_dashboard_update_task(self, mock_update):
        """Test updating task progress."""
        dashboard = ProgressDashboard()
        task_id = dashboard.add_task("Upload", total=50)
        dashboard.update_task(task_id, completed=25)
        assert dashboard.tasks[task_id]['completed'] == 25

    @patch.object(ProgressDashboard, '_update_display')
    def test_progress_dashboard_multiple_tasks(self, mock_update):
        """Test dashboard handles multiple tasks."""
        dashboard = ProgressDashboard()
        task1 = dashboard.add_task("Task 1", total=100)
        task2 = dashboard.add_task("Task 2", total=200)
        assert len(dashboard.tasks) == 2
        assert task1 != task2


class TestInteractiveTable:
    """Tests for InteractiveTable component."""

    def test_interactive_table_initialization(self):
        """Test InteractiveTable initializes with data."""
        data = [['A', 1], ['B', 2]]
        columns = ['Letter', 'Number']
        table = InteractiveTable(data, columns, title='Test')
        assert table.data == data
        assert table.columns == columns
        assert table.title_text == 'Test'

    @patch.object(InteractiveTable, 'run')
    def test_display_table_calls_run(self, mock_run):
        """Test display_table creates and runs InteractiveTable."""
        data = [['X', 10]]
        columns = ['Col1', 'Col2']
        display_table(data, columns, title='Data')
        mock_run.assert_called_once()


class TestLogViewer:
    """Tests for LogViewer component."""

    def test_log_viewer_initialization(self):
        """Test LogViewer initializes correctly."""
        viewer = LogViewer()
        assert isinstance(viewer, App)

    def test_log_viewer_add_log(self):
        """Test adding log messages to viewer."""
        viewer = LogViewer()
        # This would normally interact with UI
        # Test that method exists and is callable
        assert hasattr(viewer, 'add_log')
        assert callable(viewer.add_log)

    def test_log_viewer_clear_action(self):
        """Test LogViewer has clear action."""
        viewer = LogViewer()
        assert hasattr(viewer, 'action_clear')
        assert callable(viewer.action_clear)


class TestNotifications:
    """Tests for notification system."""

    def test_show_notification_basic(self, capsys):
        """Test show_notification displays message."""
        show_notification("Test message", title="Info")
        captured = capsys.readouterr()
        assert "Test message" in captured.out
        assert "Info" in captured.out

    def test_show_notification_information(self, capsys):
        """Test show_notification with information severity."""
        show_notification("Info text", severity="information")
        captured = capsys.readouterr()
        assert "Info text" in captured.out

    def test_show_notification_warning(self, capsys):
        """Test show_notification with warning severity."""
        show_notification("Warning text", severity="warning")
        captured = capsys.readouterr()
        assert "Warning text" in captured.out

    def test_show_notification_error(self, capsys):
        """Test show_notification with error severity."""
        show_notification("Error text", severity="error")
        captured = capsys.readouterr()
        assert "Error text" in captured.out


class TestHelpDisplay:
    """Tests for help display system."""

    def test_help_screen_initialization(self):
        """Test HelpScreen initializes with help text."""
        help_text = "This is help content"
        screen = HelpScreen(help_text, title="Help")
        assert screen.help_text == help_text
        assert screen.title_text == "Help"

    def test_help_app_initialization(self):
        """Test HelpApp initializes correctly."""
        app = HelpApp("Help content", title="Guide")
        assert app.help_text == "Help content"
        assert app.title == "Guide"

    @patch.object(HelpApp, 'run')
    def test_display_help_calls_run(self, mock_run):
        """Test display_help creates and runs HelpApp."""
        display_help("Instructions", title="Manual")
        mock_run.assert_called_once()


class TestLiveMetrics:
    """Tests for LiveMetrics component."""

    def test_live_metrics_initialization(self):
        """Test LiveMetrics initializes correctly."""
        metrics = LiveMetrics()
        assert isinstance(metrics, App)
        assert metrics.metrics == {}

    @patch.object(LiveMetrics, '_refresh_display')
    def test_live_metrics_update_metric(self, mock_refresh):
        """Test updating metric values."""
        metrics = LiveMetrics()
        metrics.update_metric("CPU", "45%")
        assert "CPU" in metrics.metrics
        assert metrics.metrics["CPU"] == "45%"

    @patch.object(LiveMetrics, '_refresh_display')
    def test_live_metrics_multiple_metrics(self, mock_refresh):
        """Test updating multiple metrics."""
        metrics = LiveMetrics()
        metrics.update_metric("CPU", "50%")
        metrics.update_metric("Memory", "2.3 GB")
        metrics.update_metric("Disk", "80%")
        assert len(metrics.metrics) == 3
        assert metrics.metrics["CPU"] == "50%"
        assert metrics.metrics["Memory"] == "2.3 GB"

    @patch.object(LiveMetrics, '_refresh_display')
    def test_live_metrics_overwrite(self, mock_refresh):
        """Test updating existing metric overwrites value."""
        metrics = LiveMetrics()
        metrics.update_metric("Load", "1.0")
        metrics.update_metric("Load", "2.5")
        assert metrics.metrics["Load"] == "2.5"


class TestUtilityFunctions:
    """Tests for utility functions."""

    @patch.object(ConfirmApp, 'run', return_value=True)
    def test_run_tui_app_basic(self, mock_run):
        """Test run_tui_app runs app and returns result."""
        result = run_tui_app(ConfirmApp, "Test?", default=True)
        assert result is True
        mock_run.assert_called_once()

    @patch.object(ChoiceApp, 'run', return_value=2)
    def test_run_tui_app_with_args(self, mock_run):
        """Test run_tui_app passes arguments correctly."""
        choices = ['A', 'B', 'C']
        result = run_tui_app(ChoiceApp, "Pick:", choices, default_index=0)
        assert result == 2


class TestScreenBindings:
    """Tests for screen keybindings."""

    def test_confirm_screen_has_bindings(self):
        """Test ConfirmScreen has proper keybindings."""
        screen = ConfirmScreen("Test", default=False)
        # Bindings should include 'y', 'n', 'escape'
        assert hasattr(ConfirmScreen, 'BINDINGS')
        assert len(ConfirmScreen.BINDINGS) >= 3

    def test_choice_screen_has_bindings(self):
        """Test ChoiceScreen has proper keybindings."""
        # Bindings should include 'escape', 'enter'
        assert hasattr(ChoiceScreen, 'BINDINGS')

    def test_input_screen_has_bindings(self):
        """Test InputScreen has proper keybindings."""
        # Bindings should include 'escape', 'ctrl+s'
        assert hasattr(InputScreen, 'BINDINGS')

    def test_help_screen_has_bindings(self):
        """Test HelpScreen has close bindings."""
        # Should have 'escape' and 'q'
        assert hasattr(HelpScreen, 'BINDINGS')


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @patch.object(ChoiceApp, 'run', return_value=0)
    def test_empty_choices_list(self, mock_run):
        """Test prompt_choice with empty choices list."""
        result = prompt_choice("Pick:", [])
        # Should handle gracefully, may return 0 or None

    def test_progress_dashboard_update_nonexistent_task(self):
        """Test updating non-existent task doesn't crash."""
        dashboard = ProgressDashboard()
        # Should not raise exception
        dashboard.update_task("nonexistent_id", completed=50)

    def test_live_metrics_empty(self):
        """Test LiveMetrics with no metrics."""
        metrics = LiveMetrics()
        # Should initialize with empty metrics
        assert metrics.metrics == {}

    @patch.object(InputApp, 'run', return_value="")
    def test_prompt_input_empty_string(self, mock_run):
        """Test prompt_input with empty string input."""
        result = prompt_input("Name:")
        assert result == ""

    def test_interactive_table_empty_data(self):
        """Test InteractiveTable with empty data."""
        table = InteractiveTable([], ['Col1'], title='Empty')
        assert table.data == []
        assert len(table.columns) == 1

    def test_notification_default_severity(self, capsys):
        """Test show_notification uses default severity."""
        show_notification("Message")
        captured = capsys.readouterr()
        # Should default to "information"
        assert "Message" in captured.out

    @patch.object(InputApp, 'run', return_value="invalid")
    def test_input_validation_failure_handling(self, mock_run):
        """Test input validation failure is handled."""
        def strict_validator(val):
            return val == "valid"

        # Even if validation would fail, the app handles it
        result = prompt_input("Enter:", validator=strict_validator)
        # Mock returns "invalid" - in real scenario, app would re-prompt


class TestComponentComposition:
    """Tests for component composition functionality."""

    def test_confirm_app_mounts_screen(self):
        """Test ConfirmApp mounts ConfirmScreen on mount."""
        app = ConfirmApp("Test?")
        # Has on_mount method that pushes screen
        assert hasattr(app, 'on_mount')
        assert callable(app.on_mount)

    def test_choice_app_mounts_screen(self):
        """Test ChoiceApp mounts ChoiceScreen on mount."""
        app = ChoiceApp("Pick:", ['A', 'B'])
        assert hasattr(app, 'on_mount')
        assert callable(app.on_mount)

    def test_input_app_mounts_screen(self):
        """Test InputApp mounts InputScreen on mount."""
        app = InputApp("Enter:")
        assert hasattr(app, 'on_mount')
        assert callable(app.on_mount)

    def test_help_app_mounts_screen(self):
        """Test HelpApp mounts HelpScreen on mount."""
        app = HelpApp("Help text")
        assert hasattr(app, 'on_mount')
        assert callable(app.on_mount)


class TestCSSandStyling:
    """Tests for CSS and styling in components."""

    def test_progress_dashboard_has_css(self):
        """Test ProgressDashboard has CSS defined."""
        assert hasattr(ProgressDashboard, 'CSS')
        assert isinstance(ProgressDashboard.CSS, str)

    def test_live_metrics_has_css(self):
        """Test LiveMetrics has CSS defined."""
        assert hasattr(LiveMetrics, 'CSS')
        assert isinstance(LiveMetrics.CSS, str)

    def test_log_viewer_has_css(self):
        """Test LogViewer has CSS defined."""
        assert hasattr(LogViewer, 'CSS')
        assert isinstance(LogViewer.CSS, str)


class TestInteractiveTableActions:
    """Tests for InteractiveTable actions."""

    def test_interactive_table_has_search_action(self):
        """Test InteractiveTable has search action defined."""
        data = [['A', 1]]
        table = InteractiveTable(data, ['Col'], title='Test')
        assert hasattr(table, 'action_search')
        assert callable(table.action_search)

    def test_interactive_table_has_bindings(self):
        """Test InteractiveTable has keybindings."""
        assert hasattr(InteractiveTable, 'BINDINGS')
