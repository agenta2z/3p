"""
Test YAML preset loading functionality.
"""

import os
import sys
import tempfile
import pytest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../../src'))

from python_utils.common_utils.arg_utils.arg_parse import get_parsed_args


class TestYamlPresets:
    """Test YAML preset functionality."""

    def test_yaml_preset_basic(self):
        """Test loading a basic YAML preset."""
        yaml_content = """
learning_rate: 0.01
batch_size: 64
model_name: resnet50
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            yaml_file = f.name

        try:
            args = get_parsed_args(
                ("learning_rate", 0.001),
                ("batch_size", 32),
                ("epochs", 100),
                preset=yaml_file,
                argv=["script"],
                verbose=False,
            )

            assert args.learning_rate == 0.01  # From YAML
            assert args.batch_size == 64  # From YAML
            assert args.epochs == 100  # From default
            assert args.model_name == "resnet50"  # From YAML (ad-hoc)
        finally:
            os.unlink(yaml_file)

    def test_yaml_preset_yml_extension(self):
        """Test loading YAML with .yml extension."""
        yaml_content = """
learning_rate: 0.005
batch_size: 128
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(yaml_content)
            yaml_file = f.name

        try:
            args = get_parsed_args(
                ("learning_rate", 0.001),
                ("batch_size", 32),
                preset=yaml_file,
                argv=["script"],
                verbose=False,
            )

            assert args.learning_rate == 0.005
            assert args.batch_size == 128
        finally:
            os.unlink(yaml_file)

    def test_yaml_preset_nested(self):
        """Test loading nested YAML structures."""
        yaml_content = """
model:
  hidden_size: 256
  num_layers: 4
  activation: relu
training:
  learning_rate: 0.01
  batch_size: 64
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            yaml_file = f.name

        try:
            # Load entire file
            args = get_parsed_args(
                preset=yaml_file,
                argv=["script"],
                verbose=False,
            )

            # Nested dicts should become Namespace objects or remain as dicts
            assert hasattr(args, 'model')
            assert hasattr(args, 'training')
            # Access as dict (YAML loader returns dicts, not Namespace by default)
            assert args.model['hidden_size'] == 256
            assert args.model['num_layers'] == 4
            assert args.training['learning_rate'] == 0.01
        finally:
            os.unlink(yaml_file)

    def test_yaml_preset_key_extraction(self):
        """Test key extraction from nested YAML."""
        yaml_content = """
small:
  hidden_size: 128
  num_layers: 2
medium:
  hidden_size: 256
  num_layers: 4
large:
  hidden_size: 512
  num_layers: 8
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            yaml_file = f.name

        try:
            # Extract 'medium' config
            args = get_parsed_args(
                preset=f"{yaml_file}:medium",
                argv=["script"],
                verbose=False,
            )

            assert args.hidden_size == 256
            assert args.num_layers == 4
            assert not hasattr(args, 'small')
            assert not hasattr(args, 'large')
        finally:
            os.unlink(yaml_file)

    def test_yaml_preset_lists_and_types(self):
        """Test YAML with various data types."""
        yaml_content = """
layers: [64, 128, 256, 512]
dropout_rates: [0.1, 0.2, 0.3]
names: [train, val, test]
config:
  lr: 0.001
  momentum: 0.9
enabled: true
debug: false
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            yaml_file = f.name

        try:
            args = get_parsed_args(
                preset=yaml_file,
                argv=["script"],
                verbose=False,
            )

            assert args.layers == [64, 128, 256, 512]
            assert args.dropout_rates == [0.1, 0.2, 0.3]
            assert args.names == ['train', 'val', 'test']
            # Access nested dict values
            assert args.config['lr'] == 0.001
            assert args.config['momentum'] == 0.9
            assert args.enabled is True
            assert args.debug is False
        finally:
            os.unlink(yaml_file)

    def test_yaml_cli_override(self):
        """Test that CLI arguments override YAML preset values."""
        yaml_content = """
learning_rate: 0.01
batch_size: 64
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            yaml_file = f.name

        try:
            args = get_parsed_args(
                ("learning_rate", 0.001),
                ("batch_size", 32),
                preset=yaml_file,
                argv=["script", "--learning_rate", "0.1"],
                verbose=False,
            )

            assert args.learning_rate == 0.1  # CLI override
            assert args.batch_size == 64  # From YAML
        finally:
            os.unlink(yaml_file)

    def test_yaml_missing_file(self):
        """Test error handling for missing YAML file."""
        with pytest.raises(FileNotFoundError):
            get_parsed_args(
                preset="nonexistent.yaml",
                argv=["script"],
                verbose=False,
            )

    def test_yaml_auto_extension(self):
        """Test automatic .yaml extension detection."""
        yaml_content = """
learning_rate: 0.01
batch_size: 64
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            yaml_file = f.name

        try:
            # Remove extension from path
            base_path = yaml_file[:-5] if yaml_file.endswith('.yaml') else yaml_file

            args = get_parsed_args(
                ("learning_rate", 0.001),
                preset=base_path,  # No extension
                argv=["script"],
                verbose=False,
            )

            assert args.learning_rate == 0.01
        finally:
            os.unlink(yaml_file)


if __name__ == "__main__":
    # Run tests
    import subprocess
    subprocess.run([sys.executable, "-m", "pytest", __file__, "-v"])
