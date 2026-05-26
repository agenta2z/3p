import re
import unicodedata
from typing import List, Mapping, Callable, Any, Union, Iterable, Dict, Optional

from python_utils.common_utils import process
from python_utils.common_utils.iter_helper import update_values
from python_utils.string_utils.common import strip_


def remove_accents(s: str) -> str:
    nfkd_form = unicodedata.normalize('NFKD', s)
    only_ascii = nfkd_form.encode('ASCII', 'ignore')
    return only_ascii.decode('utf-8')


def remove_trailing_bracketed_strings(s: str) -> str:
    """
    Remove all trailing bracketed contents from the input string.

    This function removes all trailing bracketed contents from the input string using a single
    regular expression pattern. It can handle multiple consecutive bracketed contents.

    Args:
        s (str): The input string from which to remove trailing bracketed contents.

    Returns:
        str: The input string with all trailing bracketed contents removed.

    Examples:
        >>> remove_trailing_bracketed_strings("Example string (2021) (v1.0) (beta)")
        'Example string'
        >>> remove_trailing_bracketed_strings("Another example (123) (ABC)")
        'Another example'
        >>> remove_trailing_bracketed_strings("Another example (123)")
        'Another example'
        >>> remove_trailing_bracketed_strings("No brackets here")
        'No brackets here'
    """
    year_pattern = r'(\s\([^()]*\))+$'
    return re.sub(year_pattern, '', s).strip()


def extract_trailing_bracketed_strings(s: str) -> List[str]:
    """
    Extract all trailing bracketed contents from the input string.

    This function extracts all trailing bracketed contents from the input string using a single
    regular expression pattern. It can handle multiple consecutive bracketed contents.

    Args:
        s: The input string from which to extract trailing bracketed contents.

    Returns: A list of extracted trailing bracketed contents, in the order they appear.

    Examples:
        >>> extract_trailing_bracketed_strings("Example string (2021) (v1.0) (beta)")
        ['2021', 'v1.0', 'beta']
        >>> extract_trailing_bracketed_strings("Another example (123) (ABC)")
        ['123', 'ABC']
        >>> extract_trailing_bracketed_strings("No brackets here")
        []
    """
    pattern = r'(?<=\s)\([^()]*\)$'
    bracketed_strings = []
    s = s.strip()

    while re.search(pattern, s):
        match = re.search(pattern, s)
        bracketed_string = match.group().strip()[1:-1]
        if bracketed_string:
            bracketed_strings.append(bracketed_string)
        start, end = match.span()
        s = s[:start].rstrip()

    return list(reversed(bracketed_strings))


# region common string processing

def process_string(s: str, processors: Mapping = None, **kwargs) -> Union[str, Any]:
    """
    Apply string processing functions to the input string.

    Args:
        s (str): The input string to be processed.
        processors (Mapping, optional): A dictionary mapping processor names to functions. Defaults to None.
        **kwargs: Keyword arguments where the key is the processor name and the value is either True, False,
            a dictionary of processor arguments, or directly the arguments.

    Returns:
        Union[str, Any]: The processed string or result of processing.

    Example:
        >>> s = "   Hello, World!   "
        >>> process_string(s, strip=True)
        'Hello, World!'
        >>> process_string(s, strip=True, lower=True)
        'hello, world!'
        >>> s = "   Hello, World!   xxx"
        >>> process_string(s, rstrip=' x')
        '   Hello, World!'
        >>> process_string(s, rstrip=' x', extract_between_={'search1': 'll', 'search2': 'or'})
        'o, W'
        >>> process_string(s, isdigit=True)
        False
        >>> s = "zgchen-pod-stjdp                                                        1/1     Running                  0               9d"
        >>> process_string(s, split=True)
        ['zgchen-pod-stjdp', '1/1', 'Running', '0', '9d']
        >>> fields=['name', 'ready', 'status', 'restarts', 'age']
        >>> process_string(s, split=True, zip=[fields, '#output'], dict=True)
        {'name': 'zgchen-pod-stjdp', 'ready': '1/1', 'status': 'Running', 'restarts': '0', 'age': '9d'}
    """
    import python_utils.string_utils as str_utils
    return process(
        obj=s,
        modules=[str, str_utils],
        processors=processors,
        **kwargs
    )



def process_lines(
        line_iter: Union[str, Iterable[str]],
        processors: Mapping = None,
        ignore_empty_lines: bool = True,
        ignore_empty_output: bool = True,
        **kwargs
) -> Union[str, Any]:
    for line in line_iter.split('\n') if isinstance(line_iter, str) else line_iter:
        if not line and ignore_empty_lines:
            continue
        item = process_string(line, processors=processors, **kwargs)
        if not item and ignore_empty_output:
            continue
        yield item
# endregion


# region pattern protection utility

def _get_restore_content(
    registry_entry: Dict[str, Any],
    restore_group: Union[None, int, List[int]]
) -> str:
    """
    Extract content to restore based on restore_group parameter.

    Args:
        registry_entry: Dict with "full_match" and "groups"
        restore_group:
            - None or 0: restore full match
            - Positive int (1, 2, ...): restore nth capture group
            - Negative int (-1, -2, ...): restore from end (-1 = last group)
            - List of ints: join multiple groups

    Returns:
        String content to restore

    Examples:
        Setup test data (simulating a regex match for pattern r'```([a-z]+)\\n(.*?)```')
        >>> entry = {
        ...     "full_match": "```python\\nprint('hello')```",
        ...     "groups": ("python", "print('hello')")
        ... }

        Example 1: Restore full match (default for markdown preservation)
        >>> _get_restore_content(entry, None)
        "```python\\nprint('hello')```"
        >>> _get_restore_content(entry, 0)
        "```python\\nprint('hello')```"

        Example 2: Restore first capture group (language identifier)
        >>> _get_restore_content(entry, 1)
        'python'

        Example 3: Restore last capture group (code content)
        >>> _get_restore_content(entry, -1)
        "print('hello')"
        >>> _get_restore_content(entry, 2)
        "print('hello')"

        Example 4: Join multiple groups
        >>> _get_restore_content(entry, [1, 2])
        "pythonprint('hello')"

        Example 5: Join with custom order
        >>> entry2 = {
        ...     "full_match": "$$[eq1]E=mc^2$$",
        ...     "groups": ("eq1", "E=mc^2")
        ... }
        >>> _get_restore_content(entry2, [2, 1])
        'E=mc^2eq1'
        >>> _get_restore_content(entry2, [1])
        'eq1'

        Example 6: Handle negative indices
        >>> entry3 = {
        ...     "full_match": "<tag a='1' b='2'>content</tag>",
        ...     "groups": ("1", "2", "content")
        ... }
        >>> _get_restore_content(entry3, -1)
        'content'
        >>> _get_restore_content(entry3, -2)
        '2'
        >>> _get_restore_content(entry3, [-1, -2])
        'content2'

        Example 7: Invalid index falls back to full match
        >>> _get_restore_content(entry, 10)
        "```python\\nprint('hello')```"
        >>> _get_restore_content(entry, -10)
        "```python\\nprint('hello')```"

        Example 8: No capture groups
        >>> entry_no_groups = {
        ...     "full_match": "```code```",
        ...     "groups": ()
        ... }
        >>> _get_restore_content(entry_no_groups, 1)
        '```code```'
        >>> _get_restore_content(entry_no_groups, -1)
        '```code```'

        Example 9: Handle None in groups (optional groups)
        >>> entry_optional = {
        ...     "full_match": "```\\ncode```",
        ...     "groups": (None, "code")
        ... }
        >>> _get_restore_content(entry_optional, 1)
        ''
        >>> _get_restore_content(entry_optional, 2)
        'code'
        >>> _get_restore_content(entry_optional, [1, 2])
        'code'
    """
    full_match = registry_entry["full_match"]
    groups = registry_entry["groups"]

    # Full match
    if restore_group is None or restore_group == 0:
        return full_match

    # No capture groups - fallback to full match
    if not groups:
        return full_match

    # Multiple groups - join them
    if isinstance(restore_group, list):
        parts = []
        for idx in restore_group:
            # Convert to 1-based index
            actual_idx = idx if idx > 0 else len(groups) + idx + 1
            if 1 <= actual_idx <= len(groups):
                group_content = groups[actual_idx - 1]
                parts.append(group_content if group_content is not None else '')
        return ''.join(parts)

    # Single group
    actual_idx = restore_group if restore_group > 0 else len(groups) + restore_group + 1

    # Validate index
    if 1 <= actual_idx <= len(groups):
        group_content = groups[actual_idx - 1]
        return group_content if group_content is not None else ''

    # Fallback to full match if index invalid
    return full_match


def apply_with_pattern_protection(
    text: str,
    operation: Callable[[str], Any],
    protection_patterns: Union[str, re.Pattern, List[Union[str, re.Pattern]]],
    placeholder_prefix: str = "__PROTECTED_",
    placeholder_suffix: str = "__",
    restore_in_result: bool = True,
    restore_group: Union[None, int, List[int]] = -1,
    restore_func: Optional[Callable[[Callable[[Any], Any], Any], Any]] = None
) -> Any:
    """
    Apply an operation on text with pattern-based protection and restoration.

    This utility protects specified patterns (e.g., code blocks, equations) by replacing them
    with placeholders before applying an operation, then restores the original content afterward.
    Useful for parsing operations that might be disrupted by special content.

    Args:
        text: Input string to process
        operation: Function to apply on the protected text (e.g., xml_to_dict, json.loads)
        protection_patterns: Regex pattern(s) to protect. Must have at least one capture group.
            - Single pattern: r'```([a-z]*)\\n(.*?)```'
            - Multiple patterns: [r'pattern1', r'pattern2']
            - Compiled patterns: [re.compile(r'...', re.DOTALL)]
        placeholder_prefix: Start of placeholder string (default: "__PROTECTED_")
        placeholder_suffix: End of placeholder string (default: "__")
        restore_in_result: Whether to restore protected content after operation (default: True)
        restore_group: Which capture group(s) to restore (default: -1 = last group)
            - None or 0: restore full match
            - Positive int (1, 2, ...): restore nth group
            - Negative int (-1, -2, ...): restore from end
            - List of ints: join multiple groups
        restore_func: Custom function for traversing and restoring the result.
            Signature: (update_func, obj) -> obj
            Default: uses update_values from iter_helper

    Returns:
        Result of the operation with protected patterns restored

    Examples:
        Example 1: Basic pattern protection
        >>> text = "Value is ```python\\nx=5```"
        >>> operation = lambda s: {"data": s}
        >>> result = apply_with_pattern_protection(
        ...     text=text,
        ...     operation=operation,
        ...     protection_patterns=r'```([a-z]+)\\n(.*?)```',
        ...     restore_group=None  # Restore full match
        ... )
        >>> result
        {'data': 'Value is ```python\\nx=5```'}

        Example 2: Extract only code content (not markdown syntax)
        >>> result = apply_with_pattern_protection(
        ...     text=text,
        ...     operation=operation,
        ...     protection_patterns=r'```([a-z]+)\\n(.*?)```',
        ...     restore_group=-1  # Restore last group (code content)
        ... )
        >>> result
        {'data': 'Value is x=5'}

        Example 3: Extract only language identifier
        >>> result = apply_with_pattern_protection(
        ...     text=text,
        ...     operation=operation,
        ...     protection_patterns=r'```([a-z]+)\\n(.*?)```',
        ...     restore_group=1  # Restore first group (language)
        ... )
        >>> result
        {'data': 'Value is python'}

        Example 4: Multiple patterns
        >>> text2 = "Code: ```python\\nx=1``` and math: $$E=mc^2$$"
        >>> result = apply_with_pattern_protection(
        ...     text=text2,
        ...     operation=operation,
        ...     protection_patterns=[
        ...         r'```([a-z]+)\\n(.*?)```',  # Code blocks
        ...         r'\\$\\$(.*?)\\$\\$'        # LaTeX
        ...     ],
        ...     restore_group=-1
        ... )
        >>> result
        {'data': 'Code: x=1 and math: E=mc^2'}

        Example 5: Nested structures
        >>> def parse_to_nested(s):
        ...     return {"outer": {"inner": [s, s.upper()]}}
        >>> result = apply_with_pattern_protection(
        ...     text="Value: ```js\\ncode```",
        ...     operation=parse_to_nested,
        ...     protection_patterns=r'```([a-z]+)\\n(.*?)```',
        ...     restore_group=-1
        ... )
        >>> result
        {'outer': {'inner': ['Value: code', 'VALUE: code']}}

        Example 6: Custom placeholders
        >>> result = apply_with_pattern_protection(
        ...     text="Code: ```py\\ntest```",
        ...     operation=operation,
        ...     protection_patterns=r'```([a-z]+)\\n(.*?)```',
        ...     placeholder_prefix="<<<SAFE_",
        ...     placeholder_suffix="_SAFE>>>",
        ...     restore_group=-1
        ... )
        >>> result
        {'data': 'Code: test'}

        Example 7: No restoration (keep placeholders for debugging)
        >>> result = apply_with_pattern_protection(
        ...     text="Code: ```py\\ntest```",
        ...     operation=operation,
        ...     protection_patterns=r'```([a-z]+)\\n(.*?)```',
        ...     restore_in_result=False
        ... )
        >>> 'PROTECTED' in result['data']
        True

        Example 8: Multiple code blocks
        >>> text3 = "First: ```py\\na=1``` and second: ```js\\nb=2```"
        >>> result = apply_with_pattern_protection(
        ...     text=text3,
        ...     operation=operation,
        ...     protection_patterns=r'```([a-z]+)\\n(.*?)```',
        ...     restore_group=[1, 2]  # Join language + code
        ... )
        >>> result
        {'data': 'First: pya=1 and second: jsb=2'}

        Example 9: Protect HTML code blocks (with XML-breaking characters)
        >>> html_text = "Example: ```html\\n<div class=\\"test\\">Hello & Goodbye</div>```"
        >>> result = apply_with_pattern_protection(
        ...     text=html_text,
        ...     operation=operation,
        ...     protection_patterns=r'```([a-z]+)\\n(.*?)```',
        ...     restore_group=None  # Keep full markdown
        ... )
        >>> '<div' in result['data']
        True
        >>> '&' in result['data']
        True

        Example 10: Protect markdown with special characters
        >>> md_text = "Doc: ```markdown\\n# Title\\n* Item 1 & 2\\n<tag>text</tag>```"
        >>> result = apply_with_pattern_protection(
        ...     text=md_text,
        ...     operation=operation,
        ...     protection_patterns=r'```([a-z]+)\\n(.*?)```',
        ...     restore_group=-1  # Just content
        ... )
        >>> result
        {'data': 'Doc: # Title\\n* Item 1 & 2\\n<tag>text</tag>'}

        Example 11: Protect Python code with operators
        >>> py_text = "Code: ```python\\nx = 5 & 3  # Bitwise AND\\ny = 10 < 20```"
        >>> result = apply_with_pattern_protection(
        ...     text=py_text,
        ...     operation=operation,
        ...     protection_patterns=r'```([a-z]+)\\n(.*?)```',
        ...     restore_group=-1
        ... )
        >>> '&' in result['data'] and '<' in result['data']
        True

    Notes:
        - Patterns are processed in order; earlier patterns match first
        - Each pattern should have at least one capture group for flexible restoration
        - The restore_func allows custom traversal for special data structures (numpy, pandas, etc.)
        - Placeholders are unique and sequential: __PROTECTED_0__, __PROTECTED_1__, etc.
    """
    # Convert patterns to list
    if isinstance(protection_patterns, (str, re.Pattern)):
        protection_patterns = [protection_patterns]

    # Compile all patterns
    compiled_patterns = []
    for pattern in protection_patterns:
        if isinstance(pattern, str):
            compiled_patterns.append(re.compile(pattern, re.DOTALL))
        elif isinstance(pattern, re.Pattern):
            compiled_patterns.append(pattern)
        else:
            raise TypeError(f"Pattern must be str or re.Pattern, got {type(pattern)}")

    # Phase 1: Protection - replace matches with placeholders
    registry: Dict[str, Dict[str, Any]] = {}
    counter = 0
    protected_text = text

    for pattern_idx, pattern in enumerate(compiled_patterns):
        # Find all matches
        matches = list(pattern.finditer(protected_text))

        # Process in reverse order to maintain string positions
        for match in reversed(matches):
            placeholder = f"{placeholder_prefix}{counter}{placeholder_suffix}"
            registry[placeholder] = {
                "full_match": match.group(0),
                "groups": match.groups(),
                "pattern_idx": pattern_idx
            }

            # Replace match with placeholder
            start, end = match.span()
            protected_text = protected_text[:start] + placeholder + protected_text[end:]
            counter += 1

    # Phase 2: Operation - apply the operation on protected text
    result = operation(protected_text)

    # Phase 3: Restoration - restore placeholders in the result
    if not restore_in_result:
        return result

    # Create the update function that restores placeholders
    def _restore_placeholder(value: Any) -> Any:
        """Replace placeholders in string values with original content."""
        if not isinstance(value, str):
            return value

        restored = value
        for placeholder, entry in registry.items():
            if placeholder in restored:
                content = _get_restore_content(entry, restore_group)
                restored = restored.replace(placeholder, content)
        return restored

    # Use provided restore_func or default to update_values
    if restore_func is None:
        final_result = update_values(_restore_placeholder, result)
    else:
        final_result = restore_func(_restore_placeholder, result)

    return final_result

# endregion
