"""
Backward compatibility tests for get_parsed_args.

Tests that the new modular implementation produces identical results
to the legacy implementation across all input formats and features.
"""

import pytest
from argparse import Namespace

from python_utils.common_utils.arg_utils.arg_parse import (
    get_parsed_args,
    ArgInfo,
)


class TestBackwardCompatibility:
    """Test that new and legacy implementations produce identical results."""

    def _compare_implementations(self, **kwargs):
        """
        Helper to compare new vs legacy implementation results.

        Returns tuple of (new_result, legacy_result, match)
        """
        # Get argv from kwargs or default
        argv = kwargs.pop("argv", ["test"])
        verbose = kwargs.pop("verbose", False)

        # Run new implementation
        new_result = get_parsed_args(
            **kwargs, argv=argv, verbose=verbose, legacy=False
        )

        # Run legacy implementation
        legacy_result = get_parsed_args(
            **kwargs, argv=argv, verbose=verbose, legacy=True
        )

        # Compare
        if isinstance(new_result, tuple):
            # return_seen_args=True case
            match = (
                vars(new_result[0]) == vars(legacy_result[0])
                and new_result[1] == legacy_result[1]
            )
        elif isinstance(new_result, list):
            # List preset case
            match = all(
                vars(n) == vars(l) for n, l in zip(new_result, legacy_result)
            )
        else:
            match = vars(new_result) == vars(legacy_result)

        return new_result, legacy_result, match

    # Format 1: String names only
    def test_format_1_string_names(self):
        """Test format 1: just argument names as strings."""
        new, legacy, match = self._compare_implementations(
            default_para1=1,
            default_para2="value",
            default_para3=[1, 2, 3],
        )
        assert match, f"Mismatch: new={vars(new)}, legacy={vars(legacy)}"

    # Format 2: 2-tuple (name, default)
    def test_format_2_tuple_with_default(self):
        """Test format 2: 2-tuple with name and default value."""
        new_result = get_parsed_args(
            ("para1", 1),
            ("para2", "value"),
            argv=["test"],
            verbose=False,
            legacy=False,
        )
        legacy_result = get_parsed_args(
            ("para1", 1),
            ("para2", "value"),
            argv=["test"],
            verbose=False,
            legacy=True,
        )
        assert vars(new_result) == vars(legacy_result)

    # Format 3: 3-tuple with description
    def test_format_3_tuple_with_description(self):
        """Test format 3: 3-tuple with name, default, and description."""
        new_result = get_parsed_args(
            ("para1", 1, "First parameter"),
            ("para2", "value", "Second parameter"),
            argv=["test"],
            verbose=False,
            legacy=False,
        )
        legacy_result = get_parsed_args(
            ("para1", 1, "First parameter"),
            ("para2", "value", "Second parameter"),
            argv=["test"],
            verbose=False,
            legacy=True,
        )
        assert vars(new_result) == vars(legacy_result)

    # Format 4: 3-tuple with converter
    def test_format_4_tuple_with_converter(self):
        """Test format 4: 3-tuple with name, default, and converter."""
        converter = lambda x: int(x) * 2
        new_result = get_parsed_args(
            ("para1", 1, converter),
            argv=["test"],
            verbose=False,
            legacy=False,
        )
        legacy_result = get_parsed_args(
            ("para1", 1, converter),
            argv=["test"],
            verbose=False,
            legacy=True,
        )
        assert vars(new_result) == vars(legacy_result)

    # Format 5: 4-tuple with description and converter
    def test_format_5_full_tuple(self):
        """Test format 5: 4-tuple with name, default, description, and converter."""
        converter = lambda x: str(x).upper()
        new_result = get_parsed_args(
            ("para1", "value", "A parameter", converter),
            argv=["test"],
            verbose=False,
            legacy=False,
        )
        legacy_result = get_parsed_args(
            ("para1", "value", "A parameter", converter),
            argv=["test"],
            verbose=False,
            legacy=True,
        )
        assert vars(new_result) == vars(legacy_result)

    # Format 6: 5-tuple with explicit short name
    def test_format_6_explicit_short_name(self):
        """Test format 6: 5-tuple with full name, short name, default, description, converter."""
        new_result = get_parsed_args(
            ("full_name", "f", 42, "A parameter", None),
            argv=["test"],
            verbose=False,
            legacy=False,
        )
        legacy_result = get_parsed_args(
            ("full_name", "f", 42, "A parameter", None),
            argv=["test"],
            verbose=False,
            legacy=True,
        )
        assert vars(new_result) == vars(legacy_result)

    # Format 7: ArgInfo namedtuple
    def test_format_7_arginfo(self):
        """Test format 7: ArgInfo namedtuple."""
        new_result = get_parsed_args(
            ArgInfo(full_name="para1", short_name="p", default_value=1),
            ArgInfo(full_name="para2", default_value="value"),
            argv=["test"],
            verbose=False,
            legacy=False,
        )
        legacy_result = get_parsed_args(
            ArgInfo(full_name="para1", short_name="p", default_value=1),
            ArgInfo(full_name="para2", default_value="value"),
            argv=["test"],
            verbose=False,
            legacy=True,
        )
        assert vars(new_result) == vars(legacy_result)

    # Boolean handling
    def test_boolean_false_default(self):
        """Test boolean with False default uses store_true action."""
        # Test that passing the flag sets it to True
        new_result = get_parsed_args(
            default_flag=False,
            argv=["test", "--flag"],
            verbose=False,
            legacy=False,
        )
        legacy_result = get_parsed_args(
            default_flag=False,
            argv=["test", "--flag"],
            verbose=False,
            legacy=True,
        )
        assert vars(new_result) == vars(legacy_result)
        assert new_result.flag == True

    def test_boolean_true_default(self):
        """Test boolean with True default."""
        new_result = get_parsed_args(
            default_flag=True,
            argv=["test"],
            verbose=False,
            legacy=False,
        )
        legacy_result = get_parsed_args(
            default_flag=True,
            argv=["test"],
            verbose=False,
            legacy=True,
        )
        assert vars(new_result) == vars(legacy_result)

    # List/tuple/set handling
    def test_list_default(self):
        """Test list default value with element type preservation."""
        new_result = get_parsed_args(
            default_nums=[1, 2, 3],
            argv=["test"],
            verbose=False,
            legacy=False,
        )
        legacy_result = get_parsed_args(
            default_nums=[1, 2, 3],
            argv=["test"],
            verbose=False,
            legacy=True,
        )
        assert vars(new_result) == vars(legacy_result)

    def test_list_from_cli(self):
        """Test parsing list from command line."""
        new_result = get_parsed_args(
            default_nums=[1, 2, 3],
            argv=["test", "--nums", "[4, 5, 6]"],
            verbose=False,
            legacy=False,
        )
        legacy_result = get_parsed_args(
            default_nums=[1, 2, 3],
            argv=["test", "--nums", "[4, 5, 6]"],
            verbose=False,
            legacy=True,
        )
        assert vars(new_result) == vars(legacy_result)
        assert new_result.nums == [4, 5, 6]

    # Dict handling
    def test_dict_from_cli(self):
        """Test parsing dict from command line."""
        new_result = get_parsed_args(
            default_config={"a": 1},
            argv=["test", "--config", "{'b': 2}"],
            verbose=False,
            legacy=False,
        )
        legacy_result = get_parsed_args(
            default_config={"a": 1},
            argv=["test", "--config", "{'b': 2}"],
            verbose=False,
            legacy=True,
        )
        assert vars(new_result) == vars(legacy_result)

    # return_seen_args
    def test_return_seen_args(self):
        """Test return_seen_args=True returns tuple.

        NOTE: The new implementation correctly uses the provided argv for
        get_seen_actions, while the legacy incorrectly uses sys.argv.
        This test verifies the new (correct) behavior.
        """
        new_result = get_parsed_args(
            default_para1=1,
            default_para2="value",
            return_seen_args=True,
            argv=["test", "--para1", "2"],
            verbose=False,
            legacy=False,
        )
        assert isinstance(new_result, tuple)
        assert new_result[1] == ["para1"]  # Correctly identifies seen args from provided argv

    # Short name with separator
    def test_short_name_separator(self):
        """Test short name specification with separator."""
        new_result = get_parsed_args(
            ("learning_rate/lr", 0.001),
            argv=["test", "-lr", "0.01"],
            verbose=False,
            legacy=False,
        )
        legacy_result = get_parsed_args(
            ("learning_rate/lr", 0.001),
            argv=["test", "-lr", "0.01"],
            verbose=False,
            legacy=True,
        )
        assert vars(new_result) == vars(legacy_result)

    # non_empty_args validation
    def test_non_empty_args_valid(self):
        """Test non_empty_args with valid value."""
        new_result = get_parsed_args(
            default_name="test",
            non_empty_args=["name"],
            argv=["test"],
            verbose=False,
            legacy=False,
        )
        legacy_result = get_parsed_args(
            default_name="test",
            non_empty_args=["name"],
            argv=["test"],
            verbose=False,
            legacy=True,
        )
        assert vars(new_result) == vars(legacy_result)

    def test_non_empty_args_invalid(self):
        """Test non_empty_args raises error for empty value."""
        with pytest.raises(ValueError, match="is empty"):
            get_parsed_args(
                default_name="",
                non_empty_args=["name"],
                argv=["test"],
                verbose=False,
                legacy=False,
            )

    # Preset as dict
    def test_preset_dict(self):
        """Test preset as dictionary.

        NOTE: The new implementation correctly follows the documented priority
        (preset > kwargs), while the legacy has a bug where kwargs can override
        preset for ad-hoc arguments. This test verifies the new (correct) behavior.
        """
        preset = {"para1": 100, "para2": "preset_value"}
        new_result = get_parsed_args(
            default_para1=1,
            default_para2="default",
            preset=preset,
            argv=["test"],
            verbose=False,
            legacy=False,
        )
        # New implementation correctly applies preset values (preset > kwargs)
        assert new_result.para1 == 100
        assert new_result.para2 == "preset_value"

    # Double underscore to dash
    def test_double_underscore_to_dash(self):
        """Test that __ is converted to - in CLI names."""
        new_result = get_parsed_args(
            default_config__path="default",
            argv=["test", "--config-path", "custom"],
            verbose=False,
            legacy=False,
        )
        legacy_result = get_parsed_args(
            default_config__path="default",
            argv=["test", "--config-path", "custom"],
            verbose=False,
            legacy=True,
        )
        assert vars(new_result) == vars(legacy_result)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
