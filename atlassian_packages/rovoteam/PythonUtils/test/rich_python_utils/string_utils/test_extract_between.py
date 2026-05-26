"""
Comprehensive tests for the extract_between function.

This test suite covers all features of extract_between including:
- Basic extraction with single delimiters
- Multiple delimiter options
- First vs last occurrence extraction
- Edge cases and error handling
- Return matching index functionality
"""

import pytest
from python_utils.string_utils.common import extract_between


class TestBasicExtraction:
    """Test basic extraction functionality."""

    def test_simple_extraction(self):
        """Test basic extraction between two delimiters."""
        result = extract_between("Hello [world] test", "[", "]")
        assert result == "world"

    def test_extraction_with_keep_delimiters(self):
        """Test keeping delimiters in the result."""
        result = extract_between(
            "Hello [world] test",
            "[", "]",
            keep_search1=True,
            keep_search2=True
        )
        assert result == "[world]"

    def test_extraction_keep_search1_only(self):
        """Test keeping only the start delimiter."""
        result = extract_between(
            "Hello [world] test",
            "[", "]",
            keep_search1=True,
            keep_search2=False
        )
        assert result == "[world"

    def test_extraction_keep_search2_only(self):
        """Test keeping only the end delimiter."""
        result = extract_between(
            "Hello [world] test",
            "[", "]",
            keep_search1=False,
            keep_search2=True
        )
        assert result == "world]"


class TestMultipleDelimiters:
    """Test extraction with multiple delimiter options."""

    def test_multiple_search1_first_match(self):
        """Test that first matching search1 delimiter is used."""
        result = extract_between(
            "abc startX content endX rest",
            ["startY", "startX"],
            "endX"
        )
        assert result == " content "

    def test_multiple_search2_first_match(self):
        """Test that first matching search2 delimiter is used."""
        result = extract_between(
            "start content endX more endY",
            "start",
            ["endY", "endX"]
        )
        assert result == " content endX more "

    def test_parallel_delimiters(self):
        """Test parallel delimiter lists where search1 index determines search2."""
        # When startX is found (index 1), use endX (index 1)
        result = extract_between(
            "abc startX hello endX 999 endY",
            ["startY", "startX"],
            ["endY", "endX"]
        )
        assert result == " hello "


class TestFirstVsLastOccurrence:
    """Test first vs last occurrence extraction."""

    def test_first_occurrence_default(self):
        """Test that first occurrence is used by default."""
        text = "start first end middle start second end"
        result = extract_between(text, "start", "end")
        assert result == " first "

    def test_last_occurrence_search1(self):
        """Test using last occurrence of search1."""
        text = "start first end middle start second end"
        result = extract_between(
            text, "start", "end",
            search1_use_last_occurrence=True
        )
        assert result == " second "

    def test_last_occurrence_search2(self):
        """Test using last occurrence of search2."""
        text = "start content end1 more end2"
        result = extract_between(
            text, "start", "end",
            search2_use_last_occurrence=True
        )
        assert result == " content end1 more "

    def test_last_occurrence_both(self):
        """Test using last occurrence for both delimiters."""
        text = "<tag>first</tag> middle <tag>second</tag>"
        result = extract_between(
            text, "<tag>", "</tag>",
            search1_use_last_occurrence=True,
            search2_use_last_occurrence=True
        )
        assert result == "second"

    def test_reflection_response_use_case(self):
        """Test the actual use case from agent reflection responses."""
        # This simulates the real-world scenario where reflection contains
        # an example DirectResponse, and the improved response contains the actual one
        text = """<Reflection>
Example: <DirectResponse>First response</DirectResponse>
</Reflection>
<ImprovedResponse>
<DirectResponse>Second response</DirectResponse>
</ImprovedResponse>"""

        # With first occurrence (default) - gets the example
        result_first = extract_between(text, "<DirectResponse>", "</DirectResponse>")
        assert result_first == "First response"

        # With last occurrence - gets the actual improved response
        result_last = extract_between(
            text, "<DirectResponse>", "</DirectResponse>",
            search1_use_last_occurrence=True,
            search2_use_last_occurrence=True
        )
        assert result_last == "Second response"


class TestReturnMatchingIndex:
    """Test return_matching_search1_index functionality."""

    def test_return_matching_index(self):
        """Test returning the matching search1 index."""
        text = "abc startX content endX"
        result, idx = extract_between(
            text,
            ["startY", "startX"],
            "endX",
            return_matching_search1_index=True
        )
        assert result == " content "
        assert idx == 1  # startX is at index 1

    def test_return_matching_index_first_delimiter(self):
        """Test index when first delimiter matches."""
        text = "abc startY content endY"
        result, idx = extract_between(
            text,
            ["startY", "startX"],
            "endY",
            return_matching_search1_index=True
        )
        assert result == " content "
        assert idx == 0  # startY is at index 0

    def test_return_matching_index_not_found(self):
        """Test index when no delimiter is found."""
        text = "abc content xyz"
        result, idx = extract_between(
            text,
            ["startY", "startX"],
            "endX",
            allow_search1_not_found=True,
            allow_search2_not_found=True,
            return_matching_search1_index=True
        )
        assert result == "abc content xyz"
        assert idx == -1  # No match


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_delimiter_not_found_returns_none(self):
        """Test that None is returned when delimiter is not found."""
        result = extract_between("Hello world", "[", "]")
        assert result is None

    def test_allow_search1_not_found(self):
        """Test extraction from beginning when search1 not found."""
        result = extract_between(
            "Hello world] test",
            "[", "]",
            allow_search1_not_found=True
        )
        assert result == "Hello world"

    def test_allow_search2_not_found(self):
        """Test extraction to end when search2 not found."""
        result = extract_between(
            "Hello [world and more",
            "[", "]",
            allow_search2_not_found=True
        )
        assert result == "world and more"

    def test_allow_both_not_found(self):
        """Test extraction of entire string when both not found."""
        result = extract_between(
            "Hello world",
            "[", "]",
            allow_search1_not_found=True,
            allow_search2_not_found=True
        )
        assert result == "Hello world"

    def test_empty_string(self):
        """Test extraction from empty string."""
        result = extract_between("", "[", "]")
        assert result is None

    def test_empty_result(self):
        """Test extraction when content between delimiters is empty."""
        result = extract_between("Hello [] world", "[", "]")
        assert result == ""

    def test_nested_delimiters(self):
        """Test extraction with nested delimiters (takes first end)."""
        result = extract_between("start outer start inner end end", "start", "end")
        assert result == " outer start inner "

    def test_delimiter_at_string_boundaries(self):
        """Test delimiters at start and end of string."""
        result = extract_between("[content]", "[", "]")
        assert result == "content"


class TestXMLUseCases:
    """Test XML-specific use cases."""

    def test_xml_tag_extraction(self):
        """Test extracting content from XML tags."""
        result = extract_between(
            "<response>Hello world</response>",
            "<response>", "</response>"
        )
        assert result == "Hello world"

    def test_multiple_xml_tags_first(self):
        """Test extracting first XML tag content."""
        text = "<tag>first</tag><tag>second</tag>"
        result = extract_between(text, "<tag>", "</tag>")
        assert result == "first"

    def test_multiple_xml_tags_last(self):
        """Test extracting last XML tag content."""
        text = "<tag>first</tag><tag>second</tag>"
        result = extract_between(
            text, "<tag>", "</tag>",
            search1_use_last_occurrence=True,
            search2_use_last_occurrence=True
        )
        assert result == "second"

    def test_xml_with_attributes(self):
        """Test extraction with XML tags containing attributes."""
        result = extract_between(
            '<div class="content">Hello</div>',
            '<div class="content">', '</div>'
        )
        assert result == "Hello"


class TestAlternativeDelimiters:
    """Test extraction with alternative delimiter formats."""

    def test_structured_vs_direct_response(self):
        """Test choosing between StructuredResponse and DirectResponse."""
        # DirectResponse case
        text = "Thought: analyzing <DirectResponse>Hello</DirectResponse>"
        result, idx = extract_between(
            text,
            ("<DirectResponse>", "<StructuredResponse>"),
            ("</DirectResponse>", "</StructuredResponse>"),
            return_matching_search1_index=True
        )
        assert result == "Hello"
        assert idx == 0  # DirectResponse is first in the tuple

        # StructuredResponse case
        text = "Thought: analyzing <StructuredResponse><Answer>42</Answer></StructuredResponse>"
        result, idx = extract_between(
            text,
            ("<DirectResponse>", "<StructuredResponse>"),
            ("</DirectResponse>", "</StructuredResponse>"),
            return_matching_search1_index=True
        )
        assert result == "<Answer>42</Answer>"
        assert idx == 1  # StructuredResponse is second in the tuple


class TestComplexScenarios:
    """Test complex real-world scenarios."""

    def test_agent_reflection_full_scenario(self):
        """Test the full agent reflection response parsing scenario."""
        text = """
Thought: The user is greeting me.

<Reflection>
Let me review my response:
1. I used <DirectResponse>Example greeting</DirectResponse> format
2. This is correct for simple greetings
</Reflection>

<ImprovedResponse>
Thought: The user said "hello".

<DirectResponse>Hello! I'm here to help you with tasks like finding information online.</DirectResponse>
</ImprovedResponse>
"""
        # Extract the actual improved response (last occurrence)
        result = extract_between(
            text,
            "<DirectResponse>", "</DirectResponse>",
            search1_use_last_occurrence=True,
            search2_use_last_occurrence=True
        )
        assert "Hello! I'm here to help you" in result
        assert "Example greeting" not in result

    def test_multiple_nested_tags(self):
        """Test extraction with multiple levels of nested tags."""
        text = "<outer><inner>content</inner></outer>"

        # Extract outer content
        outer = extract_between(text, "<outer>", "</outer>")
        assert outer == "<inner>content</inner>"

        # Extract inner content
        inner = extract_between(outer, "<inner>", "</inner>")
        assert inner == "content"

    def test_whitespace_handling(self):
        """Test that whitespace is preserved in extraction."""
        text = "start   content with spaces   end"
        result = extract_between(text, "start", "end")
        assert result == "   content with spaces   "


class TestPerformance:
    """Test performance-related scenarios."""

    def test_large_text_first_occurrence(self):
        """Test extraction from large text using first occurrence."""
        # Create large text with tag at beginning
        large_text = "<tag>target</tag>" + "filler " * 10000
        result = extract_between(large_text, "<tag>", "</tag>")
        assert result == "target"

    def test_large_text_last_occurrence(self):
        """Test extraction from large text using last occurrence."""
        # Create large text with tag at end
        large_text = "filler " * 10000 + "<tag>target</tag>"
        result = extract_between(
            large_text, "<tag>", "</tag>",
            search1_use_last_occurrence=True,
            search2_use_last_occurrence=True
        )
        assert result == "target"


class TestRegressions:
    """Test for potential regressions and bug fixes."""

    def test_rfind_with_start_position(self):
        """Test that rfind correctly uses start position."""
        # When using last occurrence with a start position,
        # should find last occurrence AFTER start position
        text = "start content1 end middle start content2 end"
        result = extract_between(
            text, "start", "end",
            search1_use_last_occurrence=True,
            search2_use_last_occurrence=True
        )
        assert result == " content2 "

    def test_empty_delimiter_list(self):
        """Test behavior with empty delimiter options."""
        # Empty search1 should start from beginning
        result = extract_between(
            "content end",
            [], "end",
            allow_search1_not_found=True
        )
        assert result == "content "

        # Empty search2 should go to end
        result = extract_between(
            "start content",
            "start", [],
            allow_search2_not_found=True
        )
        assert result == " content"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
