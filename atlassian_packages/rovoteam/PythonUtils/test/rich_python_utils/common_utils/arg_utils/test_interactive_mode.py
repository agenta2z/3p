"""
Test interactive mode functionality for get_parsed_args.
"""

import os
import sys
from unittest.mock import patch, MagicMock
import pytest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../../src'))

from python_utils.common_utils.arg_utils.arg_parse import get_parsed_args
from python_utils.common_utils.arg_utils.parsing.interactive import (
    InteractiveCollector,
    is_jupyter,
    is_ipython_terminal,
)


class TestInteractiveDetection:
    """Test environment detection functions."""

    def test_is_jupyter_not_in_jupyter(self):
        """Test is_jupyter returns False when not in Jupyter."""
        # In a normal test environment, should return False
        assert is_jupyter() is False

    def test_is_ipython_terminal_not_in_ipython(self):
        """Test is_ipython_terminal returns False when not in IPython."""
        # In a normal test environment, should return False
        assert is_ipython_terminal() is False


class TestInteractiveCollectorBasic:
    """Test basic InteractiveCollector functionality."""

    def test_collector_initialization(self):
        """Test collector initializes correctly."""
        collector = InteractiveCollector(use_widgets=False)
        assert collector.use_widgets is False
        # In normal environment, should not detect IPython
        assert collector.is_ipython is False

    @patch('builtins.input')
    def test_collect_simple_string(self, mock_input):
        """Test collecting a simple string argument."""
        mock_input.return_value = "test_value"

        collector = InteractiveCollector(use_widgets=False)
        arg_definitions = [("arg_name", "default", "Description")]

        result = collector.collect_arguments(arg_definitions)

        assert "arg_name" in result
        assert result["arg_name"] == "test_value"

    @patch('builtins.input')
    def test_collect_with_default_value(self, mock_input):
        """Test that pressing Enter uses default value."""
        mock_input.return_value = ""  # User presses Enter

        collector = InteractiveCollector(use_widgets=False)
        arg_definitions = [("arg_name", "default_value", "Description")]

        result = collector.collect_arguments(arg_definitions)

        assert result["arg_name"] == "default_value"

    @patch('builtins.input')
    def test_collect_boolean_true(self, mock_input):
        """Test collecting boolean true value."""
        mock_input.return_value = "true"

        collector = InteractiveCollector(use_widgets=False)
        arg_definitions = [("debug", False, "Debug mode")]

        result = collector.collect_arguments(arg_definitions)

        assert result["debug"] is True

    @patch('builtins.input')
    def test_collect_boolean_false(self, mock_input):
        """Test collecting boolean false value."""
        mock_input.return_value = "false"

        collector = InteractiveCollector(use_widgets=False)
        arg_definitions = [("debug", True, "Debug mode")]

        result = collector.collect_arguments(arg_definitions)

        assert result["debug"] is False

    @patch('builtins.input')
    def test_collect_integer(self, mock_input):
        """Test collecting integer value."""
        mock_input.return_value = "42"

        collector = InteractiveCollector(use_widgets=False)
        arg_definitions = [("count", 10, "Count value")]

        result = collector.collect_arguments(arg_definitions)

        assert result["count"] == 42

    @patch('builtins.input')
    def test_collect_float(self, mock_input):
        """Test collecting float value."""
        mock_input.return_value = "3.14"

        collector = InteractiveCollector(use_widgets=False)
        arg_definitions = [("rate", 1.0, "Learning rate")]

        result = collector.collect_arguments(arg_definitions)

        assert result["rate"] == 3.14

    @patch('builtins.input')
    def test_collect_list(self, mock_input):
        """Test collecting list value."""
        mock_input.return_value = "[1, 2, 3, 4]"

        collector = InteractiveCollector(use_widgets=False)
        arg_definitions = [("layers", [128, 256], "Layer sizes")]

        result = collector.collect_arguments(arg_definitions)

        assert result["layers"] == [1, 2, 3, 4]

    @patch('builtins.input')
    def test_collect_dict(self, mock_input):
        """Test collecting dict value."""
        mock_input.return_value = "{'key': 'value', 'num': 42}"

        collector = InteractiveCollector(use_widgets=False)
        arg_definitions = [("config", {}, "Configuration")]

        result = collector.collect_arguments(arg_definitions)

        assert result["config"] == {'key': 'value', 'num': 42}

    @patch('builtins.input')
    def test_collect_invalid_integer_uses_default(self, mock_input):
        """Test that invalid integer input uses default."""
        mock_input.return_value = "not_a_number"

        collector = InteractiveCollector(use_widgets=False)
        arg_definitions = [("count", 10, "Count value")]

        result = collector.collect_arguments(arg_definitions)

        # Should fall back to default when parsing fails
        assert result["count"] == 10

    @patch('builtins.input')
    def test_collect_multiple_arguments(self, mock_input):
        """Test collecting multiple arguments."""
        # Return different values for each call to input()
        mock_input.side_effect = ["value1", "42", "true"]

        collector = InteractiveCollector(use_widgets=False)
        arg_definitions = [
            ("arg1", "default1", "First argument"),
            ("arg2", 10, "Second argument"),
            ("arg3", False, "Third argument"),
        ]

        result = collector.collect_arguments(arg_definitions)

        assert result["arg1"] == "value1"
        assert result["arg2"] == 42
        assert result["arg3"] is True


class TestInteractiveWithPresets:
    """Test interactive mode combined with presets."""

    @patch('builtins.input')
    def test_preset_overrides_default(self, mock_input):
        """Test that preset values are shown as defaults."""
        mock_input.return_value = ""  # User accepts preset value

        collector = InteractiveCollector(use_widgets=False)
        arg_definitions = [("learning_rate", 0.001, "Learning rate")]
        preset_values = {"learning_rate": 0.01}

        result = collector.collect_arguments(arg_definitions, preset_values)

        # Should use preset value when user presses Enter
        assert result["learning_rate"] == 0.01

    @patch('builtins.input')
    def test_user_input_overrides_preset(self, mock_input):
        """Test that user input overrides preset values."""
        mock_input.return_value = "0.1"

        collector = InteractiveCollector(use_widgets=False)
        arg_definitions = [("learning_rate", 0.001, "Learning rate")]
        preset_values = {"learning_rate": 0.01}

        result = collector.collect_arguments(arg_definitions, preset_values)

        # User input should override preset
        assert result["learning_rate"] == 0.1


class TestGetParsedArgsInteractive:
    """Test get_parsed_args with interactive mode."""

    @patch('builtins.input')
    def test_basic_interactive_mode(self, mock_input):
        """Test basic interactive mode with get_parsed_args."""
        mock_input.side_effect = ["0.01", "64"]

        args = get_parsed_args(
            ("learning_rate", 0.001, "Learning rate"),
            ("batch_size", 32, "Batch size"),
            interactive=True,
            verbose=False,
            argv=["script"],
        )

        assert args.learning_rate == 0.01
        assert args.batch_size == 64

    @patch('builtins.input')
    def test_interactive_with_default_kwargs(self, mock_input):
        """Test interactive mode with default_xxx kwargs."""
        mock_input.side_effect = ["", ""]  # Accept all defaults

        args = get_parsed_args(
            default_learning_rate=0.001,
            default_batch_size=32,
            interactive=True,
            verbose=False,
            argv=["script"],
        )

        assert args.learning_rate == 0.001
        assert args.batch_size == 32

    @patch('builtins.input')
    def test_interactive_with_preset(self, mock_input):
        """Test interactive mode combined with preset."""
        mock_input.side_effect = ["", "128"]  # Accept first, override second

        preset = {
            "learning_rate": 0.01,
            "batch_size": 64,
        }

        args = get_parsed_args(
            ("learning_rate", 0.001, "Learning rate"),
            ("batch_size", 32, "Batch size"),
            preset=preset,
            interactive=True,
            verbose=False,
            argv=["script"],
        )

        assert args.learning_rate == 0.01  # From preset
        assert args.batch_size == 128  # User override

    @patch('builtins.input')
    def test_interactive_with_various_types(self, mock_input):
        """Test interactive mode with various data types."""
        mock_input.side_effect = [
            "true",  # boolean
            "100",  # integer
            "0.5",  # float
            "[64, 128, 256]",  # list
            "test_model",  # string
        ]

        args = get_parsed_args(
            ("debug", False, "Debug mode"),
            ("epochs", 50, "Number of epochs"),
            ("dropout", 0.1, "Dropout rate"),
            ("layers", [128, 256], "Layer sizes"),
            ("model_name", "default", "Model name"),
            interactive=True,
            verbose=False,
            argv=["script"],
        )

        assert args.debug is True
        assert args.epochs == 100
        assert args.dropout == 0.5
        assert args.layers == [64, 128, 256]
        assert args.model_name == "test_model"

    @patch('builtins.input')
    def test_interactive_empty_responses_use_defaults(self, mock_input):
        """Test that empty responses use default values."""
        mock_input.side_effect = ["", "", "", ""]

        args = get_parsed_args(
            ("arg1", "default1", "Argument 1"),
            ("arg2", 42, "Argument 2"),
            ("arg3", False, "Argument 3"),
            ("arg4", [1, 2, 3], "Argument 4"),
            interactive=True,
            verbose=False,
            argv=["script"],
        )

        assert args.arg1 == "default1"
        assert args.arg2 == 42
        assert args.arg3 is False
        assert args.arg4 == [1, 2, 3]

    @patch('builtins.input')
    def test_interactive_with_arginfo_tuples(self, mock_input):
        """Test interactive mode with 3-tuple ArgInfo format."""
        mock_input.side_effect = ["0.01"]

        args = get_parsed_args(
            ("learning_rate/lr", 0.001, "Learning rate for optimizer"),
            interactive=True,
            verbose=False,
            argv=["script"],
        )

        assert args.learning_rate == 0.01

    @patch('builtins.input')
    def test_interactive_preserves_non_interactive_args(self, mock_input):
        """Test that non-interactive args still work."""
        # The interactive collector will be called for all registered args
        mock_input.side_effect = [""]

        args = get_parsed_args(
            ("learning_rate", 0.001, "Learning rate"),
            interactive=True,
            verbose=False,
            argv=["script"],
        )

        assert hasattr(args, 'learning_rate')


class TestInteractiveEdgeCases:
    """Test edge cases for interactive mode."""

    @patch('builtins.input')
    def test_invalid_list_syntax_uses_default(self, mock_input):
        """Test that invalid list syntax falls back to default."""
        mock_input.return_value = "[1, 2, invalid]"

        collector = InteractiveCollector(use_widgets=False)
        arg_definitions = [("layers", [128, 256], "Layer sizes")]

        result = collector.collect_arguments(arg_definitions)

        # Should use default when parsing fails
        assert result["layers"] == [128, 256]

    @patch('builtins.input')
    def test_invalid_dict_syntax_uses_default(self, mock_input):
        """Test that invalid dict syntax falls back to default."""
        mock_input.return_value = "{'key': invalid}"

        collector = InteractiveCollector(use_widgets=False)
        arg_definitions = [("config", {"default": "value"}, "Config")]

        result = collector.collect_arguments(arg_definitions)

        # Should use default when parsing fails
        assert result["config"] == {"default": "value"}

    @patch('builtins.input')
    def test_none_default_value(self, mock_input):
        """Test handling None as default value."""
        mock_input.return_value = "some_value"

        collector = InteractiveCollector(use_widgets=False)
        arg_definitions = [("optional_arg", None, "Optional argument")]

        result = collector.collect_arguments(arg_definitions)

        assert result["optional_arg"] == "some_value"

    @patch('builtins.input')
    def test_empty_description(self, mock_input):
        """Test handling empty description."""
        mock_input.return_value = "value"

        collector = InteractiveCollector(use_widgets=False)
        arg_definitions = [("arg", "default", "")]  # Empty description

        result = collector.collect_arguments(arg_definitions)

        assert result["arg"] == "value"

    @patch('builtins.input')
    def test_tuple_type(self, mock_input):
        """Test collecting tuple value."""
        mock_input.return_value = "(1, 2, 3)"

        collector = InteractiveCollector(use_widgets=False)
        arg_definitions = [("shape", (128, 128), "Shape")]

        result = collector.collect_arguments(arg_definitions)

        assert result["shape"] == (1, 2, 3)


if __name__ == "__main__":
    # Run tests
    import subprocess
    subprocess.run([sys.executable, "-m", "pytest", __file__, "-v"])
