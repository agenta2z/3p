"""
Integration tests for xml_to_dict with code block protection.

This module tests the xml_to_dict function's ability to handle XML containing
code blocks in various programming languages with special characters that would
normally break XML parsing.
"""

import pytest
from python_utils.string_utils.xml_helpers import xml_to_dict


class TestXMLCodeBlockIntegration:
    """Integration tests for XML parsing with embedded code blocks."""

    def test_python_code_with_bitwise_operators(self):
        """Test XML containing Python code with bitwise operators (&, |, <, >)."""
        xml = '''
        <tutorial>
            <title>Python Bitwise Operations</title>
            <example>```python
x = 5 & 3  # Bitwise AND
y = 10 | 2  # Bitwise OR
z = 8 >> 1  # Right shift
w = 4 << 1  # Left shift
result = x < y and y > z
```</example>
        </tutorial>
        '''
        result = xml_to_dict(xml)
        assert 'tutorial' in result
        assert 'example' in result['tutorial']
        assert '```python' in result['tutorial']['example']
        assert '&' in result['tutorial']['example']
        assert '|' in result['tutorial']['example']
        assert '<' in result['tutorial']['example']
        assert '>' in result['tutorial']['example']

    def test_python_code_extract_content_only(self):
        """Test extracting only code content without markdown syntax."""
        xml = '''
        <tutorial>
            <example>```python
x = 5 & 3
y = 10 < 20
```</example>
        </tutorial>
        '''
        result = xml_to_dict(xml, code_block_restore_group=-1)
        code = result['tutorial']['example']
        assert 'x = 5 & 3' in code
        assert '```' not in code
        assert 'python' not in code or code.startswith('x')

    def test_html_code_block(self):
        """Test XML containing HTML code blocks."""
        xml = '''
        <documentation>
            <html_example>```html
<div class="container">
    <p>Hello & Goodbye</p>
    <span>Price: $5 < $10</span>
</div>
```</html_example>
        </documentation>
        '''
        result = xml_to_dict(xml, code_block_restore_group=-1)
        html_code = result['documentation']['html_example']
        assert '<div class="container">' in html_code
        assert '&' in html_code
        assert '<' in html_code

    def test_javascript_code_block(self):
        """Test XML containing JavaScript code."""
        xml = '''
        <guide>
            <js_example>```javascript
const x = a && b || c;
if (x < 10 && y > 5) {
    console.log("test & result");
}
```</js_example>
        </guide>
        '''
        result = xml_to_dict(xml, code_block_restore_group=-1)
        js_code = result['guide']['js_example']
        assert '&&' in js_code
        assert '||' in js_code
        assert '<' in js_code
        assert '>' in js_code

    def test_xml_code_block_inception(self):
        """Test XML containing XML code (meta!)."""
        xml = '''
        <example>
            <xml_code>```xml
<?xml version="1.0"?>
<data>
    <item value="5 & 3">test</item>
    <condition>x < 10</condition>
</data>
```</xml_code>
        </example>
        '''
        result = xml_to_dict(xml, code_block_restore_group=-1)
        xml_code = result['example']['xml_code']
        assert '<?xml version="1.0"?>' in xml_code
        assert '&' in xml_code
        assert '<data>' in xml_code

    def test_sql_code_block(self):
        """Test XML containing SQL code."""
        xml = '''
        <database>
            <query>```sql
SELECT * FROM users
WHERE age > 18 AND age < 65
  AND status <> 'inactive'
  AND created_at >= '2023-01-01'
```</query>
        </database>
        '''
        result = xml_to_dict(xml, code_block_restore_group=-1)
        sql_code = result['database']['query']
        assert '>' in sql_code
        assert '<' in sql_code
        assert '<>' in sql_code

    def test_multiple_code_blocks_different_languages(self):
        """Test XML with multiple code blocks in different languages."""
        xml = '''
        <tutorial>
            <python_example>```python
x = 5 & 3
print(f"Result: {x}")
```</python_example>
            <javascript_example>```javascript
const x = a && b;
console.log(`Result: ${x}`);
```</javascript_example>
            <html_example>```html
<div class="result">
    <p>Value: 5 < 10 & true</p>
</div>
```</html_example>
        </tutorial>
        '''
        result = xml_to_dict(xml, code_block_restore_group=-1)
        assert '&' in result['tutorial']['python_example']
        assert '&&' in result['tutorial']['javascript_example']
        assert '<div' in result['tutorial']['html_example']

    def test_markdown_code_block(self):
        """Test XML containing markdown with special characters."""
        xml = '''
        <document>
            <markdown>```markdown
# Title

* Item 1 & 2
* 5 < 10 && true
* <tag>content</tag>

[Link](http://example.com?param=1&other=2)
```</markdown>
        </document>
        '''
        result = xml_to_dict(xml, code_block_restore_group=-1)
        md_code = result['document']['markdown']
        assert '&' in md_code
        assert '<tag>' in md_code
        assert '&&' in md_code

    def test_code_block_with_nested_xml(self):
        """Test code block containing nested XML structure."""
        xml = '''
        <example>
            <description>How to parse XML</description>
            <code>```python
xml_string = "<root><item>Value & Test</item></root>"
result = parse_xml(xml_string)
if result['item'] < 10:
    process(result)
```</code>
        </example>
        '''
        result = xml_to_dict(xml)
        assert '<root>' in result['example']['code']
        assert '&' in result['example']['code']
        assert '<' in result['example']['code']

    def test_protection_disabled_with_lenient_parsing(self):
        """Verify that lenient parsing handles special chars when protection is disabled."""
        xml = '''
        <test>
            <code>```python
x = 5 & 3
```</code>
        </test>
        '''
        # With protection disabled but lenient parsing enabled (default),
        # the & gets auto-escaped and parsing succeeds
        result = xml_to_dict(xml, protect_code_blocks=False, lenient_parsing=True)
        assert 'test' in result
        # The code block markers become XML tags/content since not protected
        # This demonstrates why protection is useful

    def test_code_block_preserve_full_markdown_default(self):
        """Test that default behavior preserves full markdown syntax."""
        xml = '''
        <example>
            <code>```python
x = 5
```</code>
        </example>
        '''
        result = xml_to_dict(xml)
        assert '```python' in result['example']['code']
        assert '```' in result['example']['code']

    def test_code_block_extract_language_only(self):
        """Test extracting only the language identifier."""
        xml = '''
        <example>
            <code>```python
x = 5
```</code>
        </example>
        '''
        result = xml_to_dict(xml, code_block_restore_group=1)
        assert result['example']['code'] == 'python'

    def test_code_block_no_language_specifier(self):
        """Test code blocks without language specifier."""
        xml = '''
        <example>
            <code>```
generic code here
x = 5 & 3
```</code>
        </example>
        '''
        result = xml_to_dict(xml, code_block_restore_group=-1)
        assert 'generic code' in result['example']['code']
        assert '&' in result['example']['code']

    def test_multiline_code_with_complex_content(self):
        """Test multiline code blocks with complex content."""
        xml = '''
        <tutorial>
            <example>```python
def process_data(x, y):
    """Process data with special chars."""
    result = x & y  # Bitwise AND
    if result < 10:
        return f"<result>{result}</result>"
    return None

# Test cases:
# 1. x = 5 & 3 -> 1
# 2. 10 < 20 -> True
```</example>
        </tutorial>
        '''
        result = xml_to_dict(xml, code_block_restore_group=-1)
        code = result['tutorial']['example']
        assert 'def process_data' in code
        assert '&' in code
        assert '<result>' in code
        assert '10 < 20' in code

    def test_empty_code_block(self):
        """Test handling of empty code blocks."""
        xml = '''
        <example>
            <code>```python
```</code>
        </example>
        '''
        result = xml_to_dict(xml, code_block_restore_group=-1)
        # Empty code block should result in empty or whitespace string
        assert result['example']['code'].strip() == ''

    def test_custom_code_block_pattern(self):
        """Test using custom code block patterns."""
        xml = '''
        <example>
            <code>~~~python
x = 5 & 3
~~~</code>
        </example>
        '''
        result = xml_to_dict(
            xml,
            code_block_patterns=r'~~~([a-z]+)\n(.*?)~~~',
            code_block_restore_group=-1
        )
        assert 'x = 5 & 3' in result['example']['code']

    def test_deeply_nested_xml_with_code_blocks(self):
        """Test deeply nested XML structure with code blocks."""
        xml = '''
        <course>
            <module>
                <lesson>
                    <topic>
                        <example>```python
x = 5 & 3
y = 10 < 20
```</example>
                    </topic>
                </lesson>
            </module>
        </course>
        '''
        result = xml_to_dict(xml, code_block_restore_group=-1)
        code = result['course']['module']['lesson']['topic']['example']
        assert 'x = 5 & 3' in code
        assert 'y = 10 < 20' in code

    def test_mixed_content_with_and_without_code_blocks(self):
        """Test XML with some elements having code blocks and others not."""
        xml = '''
        <documentation>
            <description>This is a tutorial</description>
            <code_example>```python
x = 5 & 3
```</code_example>
            <note>Remember to test your code</note>
            <another_code>```javascript
const y = a && b;
```</another_code>
        </documentation>
        '''
        result = xml_to_dict(xml, code_block_restore_group=-1)
        assert result['documentation']['description'] == 'This is a tutorial'
        assert '&' in result['documentation']['code_example']
        assert result['documentation']['note'] == 'Remember to test your code'
        assert '&&' in result['documentation']['another_code']


class TestCodeBlockEdgeCases:
    """Test edge cases and error conditions."""

    def test_code_block_with_quotes(self):
        """Test code blocks containing various quote types."""
        xml = '''
        <example>
            <code>```python
s = "Hello & 'world'"
t = '<tag attr="value">text</tag>'
```</code>
        </example>
        '''
        result = xml_to_dict(xml, code_block_restore_group=-1)
        assert '&' in result['example']['code']
        assert '<tag' in result['example']['code']
        assert '"' in result['example']['code']

    def test_code_block_with_cdata_like_content(self):
        """Test code blocks containing CDATA-like content."""
        xml = '''
        <example>
            <code>```javascript
const xml = "<![CDATA[some & data < here]]>";
if (x < 10 && y > 5) { }
```</code>
        </example>
        '''
        result = xml_to_dict(xml, code_block_restore_group=-1)
        assert 'CDATA' in result['example']['code']
        assert '&' in result['example']['code']

    def test_code_block_with_xml_declaration(self):
        """Test code blocks containing XML declarations."""
        xml = '''
        <example>
            <code>```xml
<?xml version="1.0" encoding="UTF-8"?>
<root attr="value & test">
    <item>5 < 10</item>
</root>
```</code>
        </example>
        '''
        result = xml_to_dict(xml, code_block_restore_group=-1)
        assert '<?xml' in result['example']['code']
        assert '&' in result['example']['code']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
