"""
Tests for pattern protection utility in string_sanitization module.

This module tests the apply_with_pattern_protection function which protects
specified patterns (like code blocks) during string operations.
"""

import pytest
import re
from python_utils.string_utils.string_sanitization import (
    apply_with_pattern_protection,
    _get_restore_content
)


class TestGetRestoreContent:
    """Tests for the _get_restore_content helper function."""

    def test_restore_full_match_with_none(self):
        """Test restoring full match when restore_group is None."""
        entry = {
            "full_match": "```python\ncode```",
            "groups": ("python", "code")
        }
        result = _get_restore_content(entry, None)
        assert result == "```python\ncode```"

    def test_restore_full_match_with_zero(self):
        """Test restoring full match when restore_group is 0."""
        entry = {
            "full_match": "```python\ncode```",
            "groups": ("python", "code")
        }
        result = _get_restore_content(entry, 0)
        assert result == "```python\ncode```"

    def test_restore_first_group(self):
        """Test restoring first capture group."""
        entry = {
            "full_match": "```python\ncode```",
            "groups": ("python", "code")
        }
        result = _get_restore_content(entry, 1)
        assert result == "python"

    def test_restore_last_group_with_negative_index(self):
        """Test restoring last group using -1."""
        entry = {
            "full_match": "```python\ncode```",
            "groups": ("python", "code")
        }
        result = _get_restore_content(entry, -1)
        assert result == "code"

    def test_restore_multiple_groups(self):
        """Test joining multiple groups."""
        entry = {
            "full_match": "```python\ncode```",
            "groups": ("python", "code")
        }
        result = _get_restore_content(entry, [1, 2])
        assert result == "pythoncode"

    def test_restore_invalid_index_fallback(self):
        """Test that invalid indices fall back to full match."""
        entry = {
            "full_match": "```python\ncode```",
            "groups": ("python", "code")
        }
        result = _get_restore_content(entry, 10)
        assert result == "```python\ncode```"

    def test_restore_no_groups(self):
        """Test handling entries with no capture groups."""
        entry = {
            "full_match": "```code```",
            "groups": ()
        }
        result = _get_restore_content(entry, 1)
        assert result == "```code```"

    def test_restore_optional_group_none(self):
        """Test handling None values in groups (optional groups)."""
        entry = {
            "full_match": "```\ncode```",
            "groups": (None, "code")
        }
        result = _get_restore_content(entry, 1)
        assert result == ""
        result = _get_restore_content(entry, 2)
        assert result == "code"


class TestApplyWithPatternProtection:
    """Tests for the apply_with_pattern_protection main function."""

    def test_basic_protection_full_match(self):
        """Test basic pattern protection with full match restoration."""
        text = "Value is ```python\nx=5```"
        operation = lambda s: {"data": s}
        result = apply_with_pattern_protection(
            text=text,
            operation=operation,
            protection_patterns=r'```([a-z]+)\n(.*?)```',
            restore_group=None
        )
        assert result == {'data': 'Value is ```python\nx=5```'}

    def test_protection_extract_code_only(self):
        """Test extracting only code content (last group)."""
        text = "Value is ```python\nx=5```"
        operation = lambda s: {"data": s}
        result = apply_with_pattern_protection(
            text=text,
            operation=operation,
            protection_patterns=r'```([a-z]+)\n(.*?)```',
            restore_group=-1
        )
        assert result == {'data': 'Value is x=5'}

    def test_protection_extract_language_only(self):
        """Test extracting only language identifier (first group)."""
        text = "Value is ```python\nx=5```"
        operation = lambda s: {"data": s}
        result = apply_with_pattern_protection(
            text=text,
            operation=operation,
            protection_patterns=r'```([a-z]+)\n(.*?)```',
            restore_group=1
        )
        assert result == {'data': 'Value is python'}

    def test_html_code_block_with_special_chars(self):
        """Test protecting HTML code blocks with XML-breaking characters."""
        html_code = '<div class="test">Hello & Goodbye</div>'
        text = f"Example: ```html\n{html_code}```"
        operation = lambda s: {"content": s}
        result = apply_with_pattern_protection(
            text=text,
            operation=operation,
            protection_patterns=r'```([a-z]+)\n(.*?)```',
            restore_group=-1
        )
        assert result == {'content': f'Example: {html_code}'}
        assert '&' in result['content']
        assert '<div' in result['content']

    def test_markdown_code_block(self):
        """Test protecting markdown code blocks."""
        md_code = "# Title\n* Item 1 & 2\n<tag>text</tag>"
        text = f"Doc: ```markdown\n{md_code}```"
        operation = lambda s: {"doc": s}
        result = apply_with_pattern_protection(
            text=text,
            operation=operation,
            protection_patterns=r'```([a-z]+)\n(.*?)```',
            restore_group=-1
        )
        assert result == {'doc': f'Doc: {md_code}'}

    def test_python_code_with_operators(self):
        """Test protecting Python code with XML-breaking operators."""
        py_code = "x = 5 & 3  # Bitwise AND\ny = 10 < 20"
        text = f"Code: ```python\n{py_code}```"
        operation = lambda s: {"code": s}
        result = apply_with_pattern_protection(
            text=text,
            operation=operation,
            protection_patterns=r'```([a-z]+)\n(.*?)```',
            restore_group=-1
        )
        assert '&' in result['code']
        assert '<' in result['code']

    def test_multiple_code_blocks(self):
        """Test protecting multiple code blocks in the same text."""
        text = "First: ```py\na=1``` and second: ```js\nb=2```"
        operation = lambda s: {"data": s}
        result = apply_with_pattern_protection(
            text=text,
            operation=operation,
            protection_patterns=r'```([a-z]+)\n(.*?)```',
            restore_group=-1
        )
        assert result == {'data': 'First: a=1 and second: b=2'}

    def test_multiple_patterns(self):
        """Test using multiple protection patterns."""
        text = "Code: ```python\nx=1``` and math: $$E=mc^2$$"
        operation = lambda s: {"content": s}
        result = apply_with_pattern_protection(
            text=text,
            operation=operation,
            protection_patterns=[
                r'```([a-z]+)\n(.*?)```',  # Code blocks
                r'\$\$(.*?)\$\$'            # LaTeX
            ],
            restore_group=-1
        )
        assert result == {'content': 'Code: x=1 and math: E=mc^2'}

    def test_nested_structures(self):
        """Test restoration in nested data structures."""
        def parse_to_nested(s):
            return {"outer": {"inner": [s, s.upper()]}}

        text = "Value: ```js\ncode```"
        result = apply_with_pattern_protection(
            text=text,
            operation=parse_to_nested,
            protection_patterns=r'```([a-z]+)\n(.*?)```',
            restore_group=-1
        )
        # After upper(), 'code' becomes 'CODE', and 'Value:' part is already uppercase in second element
        assert result == {'outer': {'inner': ['Value: code', 'VALUE: code']}}

    def test_custom_placeholders(self):
        """Test using custom placeholder prefix and suffix."""
        text = "Code: ```py\ntest```"
        operation = lambda s: {"data": s}
        result = apply_with_pattern_protection(
            text=text,
            operation=operation,
            protection_patterns=r'```([a-z]+)\n(.*?)```',
            placeholder_prefix="<<<SAFE_",
            placeholder_suffix="_SAFE>>>",
            restore_group=-1
        )
        assert result == {'data': 'Code: test'}

    def test_no_restoration(self):
        """Test keeping placeholders without restoration."""
        text = "Code: ```py\ntest```"
        operation = lambda s: {"data": s}
        result = apply_with_pattern_protection(
            text=text,
            operation=operation,
            protection_patterns=r'```([a-z]+)\n(.*?)```',
            restore_in_result=False
        )
        assert 'PROTECTED' in result['data']
        assert '```' not in result['data']

    def test_join_multiple_groups(self):
        """Test joining multiple capture groups."""
        text = "First: ```py\na=1``` and second: ```js\nb=2```"
        operation = lambda s: {"data": s}
        result = apply_with_pattern_protection(
            text=text,
            operation=operation,
            protection_patterns=r'```([a-z]+)\n(.*?)```',
            restore_group=[1, 2]  # Join language + code
        )
        assert result == {'data': 'First: pya=1 and second: jsb=2'}

    def test_javascript_code_block(self):
        """Test protecting JavaScript code blocks."""
        js_code = "const x = a && b || c;\nif (x < 10) { }"
        text = f"JS: ```javascript\n{js_code}```"
        operation = lambda s: {"script": s}
        result = apply_with_pattern_protection(
            text=text,
            operation=operation,
            protection_patterns=r'```([a-z]+)\n(.*?)```',
            restore_group=-1
        )
        assert '&&' in result['script']
        assert '<' in result['script']

    def test_xml_code_block(self):
        """Test protecting XML code blocks."""
        xml_code = '<?xml version="1.0"?>\n<data><item>test & value</item></data>'
        text = f"Example: ```xml\n{xml_code}```"
        operation = lambda s: {"example": s}
        result = apply_with_pattern_protection(
            text=text,
            operation=operation,
            protection_patterns=r'```([a-z]+)\n(.*?)```',
            restore_group=-1
        )
        assert '<?xml' in result['example']
        assert '&' in result['example']

    def test_sql_code_block(self):
        """Test protecting SQL code blocks."""
        sql_code = "SELECT * FROM users WHERE age > 18 AND name <> 'admin'"
        text = f"Query: ```sql\n{sql_code}```"
        operation = lambda s: {"query": s}
        result = apply_with_pattern_protection(
            text=text,
            operation=operation,
            protection_patterns=r'```([a-z]+)\n(.*?)```',
            restore_group=-1
        )
        assert '<>' in result['query']
        assert '>' in result['query']

    def test_empty_code_block(self):
        """Test handling empty code blocks."""
        text = "Empty: ```python\n```"
        operation = lambda s: {"data": s}
        result = apply_with_pattern_protection(
            text=text,
            operation=operation,
            protection_patterns=r'```([a-z]+)\n(.*?)```',
            restore_group=-1
        )
        assert result == {'data': 'Empty: '}

    def test_code_block_without_language(self):
        """Test code blocks without language specifier."""
        text = "Code: ```\nsome code\n```"
        operation = lambda s: {"data": s}
        # Pattern allows optional language
        result = apply_with_pattern_protection(
            text=text,
            operation=operation,
            protection_patterns=r'```([a-z]*)\n(.*?)```',
            restore_group=-1
        )
        # The pattern captures the trailing newline before ```
        assert result == {'data': 'Code: some code\n'}

    def test_multiline_code_block(self):
        """Test code blocks with multiple lines."""
        code = "def hello():\n    print('world')\n    return True"
        text = f"Function: ```python\n{code}```"
        operation = lambda s: {"func": s}
        result = apply_with_pattern_protection(
            text=text,
            operation=operation,
            protection_patterns=r'```([a-z]+)\n(.*?)```',
            restore_group=-1
        )
        assert result['func'] == f'Function: {code}'
        assert 'def hello' in result['func']

    def test_compiled_pattern(self):
        """Test using pre-compiled regex patterns."""
        text = "Code: ```py\ntest```"
        operation = lambda s: {"data": s}
        compiled_pattern = re.compile(r'```([a-z]+)\n(.*?)```', re.DOTALL)
        result = apply_with_pattern_protection(
            text=text,
            operation=operation,
            protection_patterns=compiled_pattern,
            restore_group=-1
        )
        assert result == {'data': 'Code: test'}

    def test_mixed_string_and_compiled_patterns(self):
        """Test using both string and compiled patterns."""
        text = "Code: ```py\nx=1``` and $$math$$"
        operation = lambda s: {"data": s}
        result = apply_with_pattern_protection(
            text=text,
            operation=operation,
            protection_patterns=[
                r'```([a-z]+)\n(.*?)```',
                re.compile(r'\$\$(.*?)\$\$')
            ],
            restore_group=-1
        )
        assert result == {'data': 'Code: x=1 and math'}


class TestRealWorldScenarios:
    """Tests for real-world usage scenarios."""

    def test_xml_parsing_with_code_blocks(self):
        """Simulate XML parsing with embedded code blocks."""
        # This will be tested when integrated with xml_to_dict
        pass

    def test_json_parsing_with_latex(self):
        """Test JSON parsing with LaTeX equations."""
        import json
        json_text = '{"equation": "Solve $$E=mc^2$$ for m"}'
        result = apply_with_pattern_protection(
            text=json_text,
            operation=json.loads,
            protection_patterns=r'\$\$(.*?)\$\$',
            restore_group=-1
        )
        assert result == {"equation": "Solve E=mc^2 for m"}

    def test_multiple_languages_in_one_text(self):
        """Test text with code blocks in multiple languages."""
        text = """
        Python: ```python
x = [1, 2, 3]
y = x if x else []
```
        JavaScript: ```javascript
const arr = [1, 2, 3];
const y = arr || [];
```
        HTML: ```html
<div class="container">
    <p>Hello & Welcome</p>
</div>
```
        """
        operation = lambda s: {"content": s}
        result = apply_with_pattern_protection(
            text=text,
            operation=operation,
            protection_patterns=r'```([a-z]+)\n(.*?)```',
            restore_group=None  # Keep full markdown
        )
        # Check all code blocks are preserved
        assert '```python' in result['content']
        assert '```javascript' in result['content']
        assert '```html' in result['content']
        assert '&' in result['content']
        assert '||' in result['content']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
