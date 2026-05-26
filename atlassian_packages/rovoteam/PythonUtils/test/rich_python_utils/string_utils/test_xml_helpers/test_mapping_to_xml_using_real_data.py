import os
import pytest
from pathlib import Path

from python_utils.io_utils.pickle_io import pickle_load
from python_utils.string_utils.xml_helpers import mapping_to_xml


class TestMappingToXmlRealData:
    """Test mapping_to_xml function with real-world data loaded from pickle files."""

    def test_action_results_conversion(self):
        """
        Test converting real ActionResult data from pickle to XML format.

        This test loads actual data from a pickle file containing an ActionResult
        with markdown content and converts it to XML with specific parameters:
        - root_tag='ActionResults'
        - include_root=True
        - unescape=True

        The test validates the XML structure, content presence, and proper formatting.
        """
        # Get the path to the test data file
        test_dir = Path(__file__).parent
        pickle_file = test_dir / 'test_data' / 'test_mapping_to_xml_data1.pkl'

        # Load the real data from pickle
        _action_results = pickle_load(str(pickle_file))

        # Convert to XML with the specified parameters
        result_xml = mapping_to_xml(
            _action_results,
            root_tag='ActionResults',
            include_root=True,
            unescape=True
        )

        # Validate the result is a string
        assert isinstance(result_xml, str), "Result should be a string"

        # Validate root tag is present
        assert '<ActionResults>' in result_xml, "Should contain opening root tag <ActionResults>"
        assert '</ActionResults>' in result_xml, "Should contain closing root tag </ActionResults>"

        # Validate item tag is present (default 'item' for list elements)
        assert '<item>' in result_xml, "Should contain opening item tag <item>"
        assert '</item>' in result_xml, "Should contain closing item tag </item>"

        # Validate the ActionResult key from the dictionary is present
        assert '<ActionResult>' in result_xml, "Should contain opening tag <ActionResult>"
        assert '</ActionResult>' in result_xml, "Should contain closing tag </ActionResult>"

        # Validate some expected content from the markdown data
        assert 'Slack Channel Summary' in result_xml, "Should contain expected content from the data"
        assert 'seo-link-building-news-updates' in result_xml, "Should contain the Slack channel name"

        # Validate that content is present and XML is not empty
        assert len(result_xml) > 100, "XML output should have substantial content"

        # Validate proper XML structure (basic check - opening tags match closing tags)
        opening_tags = result_xml.count('<ActionResults>')
        closing_tags = result_xml.count('</ActionResults>')
        assert opening_tags == closing_tags == 1, "Root tags should be balanced"

        # With unescape=True, HTML entities should be unescaped
        # The original markdown contains ## headers which don't have HTML entities,
        # but if there were &amp; it should be converted to &
        # We just verify it's valid XML-like content
        assert not result_xml.startswith('<?xml'), "Should not have XML declaration by default"

        # Verify it starts with the root tag (possibly with whitespace)
        assert result_xml.strip().startswith('<ActionResults>'), "Should start with root tag"
        assert result_xml.strip().endswith('</ActionResults>'), "Should end with root tag"

    def test_invalid_input_type_raises_value_error(self):
        """
        Test that passing an invalid type (e.g., int, string) raises a helpful ValueError.

        This test verifies the error handling added to _mapping_to_xml which provides
        clear error messages when input cannot be converted to a dictionary.
        """
        # Test with integer
        with pytest.raises(ValueError) as exc_info:
            mapping_to_xml(12345)

        error_message = str(exc_info.value)
        assert "Cannot convert input of type 'int'" in error_message
        assert "Expected a Mapping, Sequence of Mappings, or an attrs class instance" in error_message

        # Test with plain string
        with pytest.raises(ValueError) as exc_info:
            mapping_to_xml("not a valid input")

        error_message = str(exc_info.value)
        assert "Cannot convert input of type 'str'" in error_message
        assert "Expected a Mapping, Sequence of Mappings, or an attrs class instance" in error_message

    def test_valid_attrs_class_conversion(self):
        """
        Test that attrs classes can be successfully converted to XML.

        This verifies that the error handling doesn't break valid attrs class conversions.
        """
        try:
            from attr import attrs, attrib

            @attrs
            class Person:
                name: str = attrib()
                age: int = attrib()

            person = Person(name="Alice", age=25)
            result = mapping_to_xml(person, root_tag="person")

            # Validate basic structure
            assert isinstance(result, str)
            assert '<person>' in result
            assert '</person>' in result
            assert '<name>Alice</name>' in result
            assert '<age>25</age>' in result
        except ImportError:
            # attrs not installed, skip this test
            pytest.skip("attrs library not installed")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
