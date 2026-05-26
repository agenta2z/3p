"""
Test TOML preset loading functionality.
"""

import os
import sys
import tempfile
import pytest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../../src'))

from python_utils.common_utils.arg_utils.arg_parse import get_parsed_args


class TestTomlPresets:
    """Test TOML preset functionality."""

    def test_toml_preset_basic(self):
        """Test loading a basic TOML preset."""
        toml_content = """
learning_rate = 0.01
batch_size = 64
model_name = "resnet50"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write(toml_content)
            toml_file = f.name

        try:
            args = get_parsed_args(
                ("learning_rate", 0.001),
                ("batch_size", 32),
                ("epochs", 100),
                preset=toml_file,
                argv=["script"],
                verbose=False,
            )

            assert args.learning_rate == 0.01  # From TOML
            assert args.batch_size == 64  # From TOML
            assert args.epochs == 100  # From default
            assert args.model_name == "resnet50"  # From TOML (ad-hoc)
        finally:
            os.unlink(toml_file)

    def test_toml_preset_nested(self):
        """Test loading nested TOML structures (tables)."""
        toml_content = """
[model]
hidden_size = 256
num_layers = 4
activation = "relu"

[training]
learning_rate = 0.01
batch_size = 64
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write(toml_content)
            toml_file = f.name

        try:
            # Load entire file
            args = get_parsed_args(
                preset=toml_file,
                argv=["script"],
                verbose=False,
            )

            # Nested tables should become dict attributes
            assert hasattr(args, 'model')
            assert hasattr(args, 'training')
            # Access as dict (TOML loader returns dicts)
            assert args.model['hidden_size'] == 256
            assert args.model['num_layers'] == 4
            assert args.training['learning_rate'] == 0.01
        finally:
            os.unlink(toml_file)

    def test_toml_preset_key_extraction(self):
        """Test key extraction from nested TOML."""
        toml_content = """
[small]
hidden_size = 128
num_layers = 2

[medium]
hidden_size = 256
num_layers = 4

[large]
hidden_size = 512
num_layers = 8
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write(toml_content)
            toml_file = f.name

        try:
            # Extract 'medium' config
            args = get_parsed_args(
                preset=f"{toml_file}:medium",
                argv=["script"],
                verbose=False,
            )

            assert args.hidden_size == 256
            assert args.num_layers == 4
            assert not hasattr(args, 'small')
            assert not hasattr(args, 'large')
        finally:
            os.unlink(toml_file)

    def test_toml_preset_lists_and_types(self):
        """Test TOML with various data types."""
        toml_content = """
layers = [64, 128, 256, 512]
dropout_rates = [0.1, 0.2, 0.3]
names = ["train", "val", "test"]
enabled = true
debug = false

[config]
lr = 0.001
momentum = 0.9
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write(toml_content)
            toml_file = f.name

        try:
            args = get_parsed_args(
                preset=toml_file,
                argv=["script"],
                verbose=False,
            )

            assert args.layers == [64, 128, 256, 512]
            assert args.dropout_rates == [0.1, 0.2, 0.3]
            assert args.names == ['train', 'val', 'test']
            # Access nested table values
            assert args.config['lr'] == 0.001
            assert args.config['momentum'] == 0.9
            assert args.enabled is True
            assert args.debug is False
        finally:
            os.unlink(toml_file)

    def test_toml_cli_override(self):
        """Test that CLI arguments override TOML preset values."""
        toml_content = """
learning_rate = 0.01
batch_size = 64
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write(toml_content)
            toml_file = f.name

        try:
            args = get_parsed_args(
                ("learning_rate", 0.001),
                ("batch_size", 32),
                preset=toml_file,
                argv=["script", "--learning_rate", "0.1"],
                verbose=False,
            )

            assert args.learning_rate == 0.1  # CLI override
            assert args.batch_size == 64  # From TOML
        finally:
            os.unlink(toml_file)

    def test_toml_missing_file(self):
        """Test error handling for missing TOML file."""
        with pytest.raises(FileNotFoundError):
            get_parsed_args(
                preset="nonexistent.toml",
                argv=["script"],
                verbose=False,
            )

    def test_toml_auto_extension(self):
        """Test automatic .toml extension detection."""
        toml_content = """
learning_rate = 0.01
batch_size = 64
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write(toml_content)
            toml_file = f.name

        try:
            # Remove extension from path
            base_path = toml_file[:-5] if toml_file.endswith('.toml') else toml_file

            args = get_parsed_args(
                ("learning_rate", 0.001),
                preset=base_path,  # No extension
                argv=["script"],
                verbose=False,
            )

            assert args.learning_rate == 0.01
        finally:
            os.unlink(toml_file)

    def test_toml_datetime_types(self):
        """Test TOML datetime types (unique to TOML)."""
        toml_content = """
timestamp = 2024-01-15T10:30:00
date_only = 2024-01-15
time_only = 10:30:00
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write(toml_content)
            toml_file = f.name

        try:
            args = get_parsed_args(
                preset=toml_file,
                argv=["script"],
                verbose=False,
            )

            # TOML parses these as datetime objects
            import datetime
            assert isinstance(args.timestamp, datetime.datetime)
            assert isinstance(args.date_only, datetime.date)
            assert isinstance(args.time_only, datetime.time)
        finally:
            os.unlink(toml_file)


if __name__ == "__main__":
    # Run tests
    import subprocess
    subprocess.run([sys.executable, "-m", "pytest", __file__, "-v"])
