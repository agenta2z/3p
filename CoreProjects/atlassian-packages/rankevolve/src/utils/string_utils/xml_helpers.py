"""
XML helper utilities.

Extracted from science_python_utils.string_utils.xml_helpers for the
agentic_foundation migration.

Functions:
    - xml_format: Formats content with XML tags
    - unescape_xml: Reverts XML/HTML escape sequences to real characters
    - mapping_to_xml: Converts dictionaries/sequences to XML strings
"""

import html
import re
from collections.abc import Sequence
from typing import Any, Dict, Iterable, List, Mapping, Optional, Union
from xml.dom.minidom import parseString
from xml.etree.ElementTree import Element, fromstring, SubElement, tostring
from xml.sax import saxutils

from rankevolve.src.utils.common_utils import dict_


def _remove_first_line(text, lstrip=True, return_empty_for_single_line=True):
    """
    Remove the first line from text.

    Inlined helper to avoid dependency on science_python_utils.string_utils.
    """
    idx = text.find("\n")
    if idx == -1:
        return "" if return_empty_for_single_line else text
    result = text[idx + 1 :]
    return (
        result.lstrip()
        if lstrip is True
        else (result.lstrip(lstrip) if lstrip else result)
    )


def xml_format(tag: str, content: str, sep: str = "") -> str:
    """
    Formats the given content with the specified XML tag.

    Args:
        tag (str): The XML tag to be used.
        content (str): The content to be wrapped inside the XML tag.
        sep (str, optional): A separator to be added before and after the content. Defaults to ''.

    Returns:
        str: A string formatted as an XML element.

    Examples:
        >>> xml_format('greeting', 'Hello, world!')
        '<greeting>Hello, world!</greeting>'

        >>> xml_format('item', 'Apple', sep='\\n')
        '<item>\\nApple\\n</item>'
    """
    return f"<{tag}>{sep}{content}{sep}</{tag}>"


def unescape_xml(s: str, unescape_for_html: bool = False) -> str:
    """
    Reverts XML or HTML escape sequences in a string to their corresponding real characters.

    Depending on the `unescape_for_html` flag, this function either handles
    predefined XML entities or leverages HTML unescaping to handle a broader
    range of entities, including both named and numeric character references.

    Args:
        s (str): The string containing XML or HTML escape sequences.
        unescape_for_html (bool):
            - If `False` (default), handles only standard XML entities (`&amp;`, `&lt;`, `&gt;`, `&quot;`, `&apos;`).
            - If `True`, uses HTML unescaping to handle a wider range of entities, including HTML-specific ones.

    Returns:
        str: The unescaped string with real characters.

    Examples:
        >>> # Example 1: Handling Standard Named Entities
        >>> escaped_str1 = "Hello &amp; Welcome &lt;User&gt;!"
        >>> unescape_xml(escaped_str1)
        'Hello & Welcome <User>!'

        >>> # Example 2: Handling All Standard Named Entities
        >>> escaped_str2 = "She said, &quot;It&apos;s a great day!&quot;"
        >>> unescape_xml(escaped_str2)
        'She said, "It\\'s a great day!"'

        >>> # Example 3: Handling Numeric Character References (Decimal)
        >>> escaped_str3 = "Unicode character: &#169;"
        >>> unescape_xml(escaped_str3)
        'Unicode character: ©'

        >>> # Example 4: Handling Numeric Character References (Hexadecimal)
        >>> escaped_str4 = "Smiley face: &#x1F600;"
        >>> unescape_xml(escaped_str4)
        'Smiley face: 😀'

        >>> # Example 5: Mixed Entities
        >>> escaped_str5 = "Price is 100 &amp; tax is &#x20AC;."
        >>> unescape_xml(escaped_str5)
        'Price is 100 & tax is €.'

        >>> # Example 6: Invalid Numeric Reference (Handled Gracefully)
        >>> escaped_str6 = "Invalid reference: &#xZZZ; &unknown;"
        >>> unescape_xml(escaped_str6)
        'Invalid reference: &#xZZZ; &unknown;'

        >>> # Example 7: No Entities
        >>> escaped_str7 = "Just a regular string without entities."
        >>> unescape_xml(escaped_str7)
        'Just a regular string without entities.'

        >>> # Example 8: Mixed Case Hexadecimal Reference
        >>> escaped_str8 = "Hex case insensitive: &#X1f600; and &#x1F600;"
        >>> unescape_xml(escaped_str8)
        'Hex case insensitive: 😀 and 😀'

        >>> # Example 9: Multiple Same Entities
        >>> escaped_str9 = "Repeat: &amp;&amp;&amp; &lt;&lt;&lt;"
        >>> unescape_xml(escaped_str9)
        'Repeat: &&& <<<'

        >>> # Example 10: Adjacent Entities
        >>> escaped_str10 = "Adjacent entities: &amp;&lt;&gt;&quot;&apos;"
        >>> unescape_xml(escaped_str10)
        'Adjacent entities: &<>"\\''
    """
    # First, unescape the standard named entities
    if unescape_for_html:
        unescaped = html.unescape(s)
    else:
        unescaped = saxutils.unescape(s, entities={"&apos;": "'", "&quot;": '"'})

    # Define a regex pattern to find numeric character references
    # This includes both decimal (e.g., &#38;) and hexadecimal (e.g., &#x26;)
    numeric_entity_pattern = re.compile(r"&#([xX]?)([0-9a-fA-F]+);")

    # Function to replace each numeric entity with the corresponding character
    def replace_numeric_entity(match):
        is_hex, num = match.groups()
        try:
            if is_hex.lower() == "x":
                return chr(int(num, 16))
            else:
                return chr(int(num))
        except (ValueError, OverflowError):
            # If conversion fails, return the original string
            return match.group(0)

    # Replace all numeric character references in the string
    unescaped = numeric_entity_pattern.sub(replace_numeric_entity, unescaped)

    return unescaped


def _build_xml_element(
    elem: Element,
    data: Union[Dict[str, Any], List[Any], Any],
    item_tag: Union[str, Mapping[str, str]],
) -> None:
    """
    Recursively builds XML elements from Python data structures.

    This is a private helper function used by _mapping_to_xml() to construct
    the actual XML element tree from dictionaries, lists, and primitive values.

    Args:
        elem: The parent XML Element to add children to
        data: The data to convert (dict, list, or primitive value)
        item_tag: Tag name(s) to use for list items. Can be:
            - str: A single tag name used for all list items (e.g., "item")
            - Mapping: A dict mapping parent tag names to their item tags
                      (e.g., {"children": "child", "books": "book"})

    Returns:
        None. Modifies elem in-place by adding child elements.

    Note:
        This function is called recursively to handle nested data structures.
        It's used internally by _mapping_to_xml() and should not be called directly.
    """
    if isinstance(data, dict):
        # Process dictionary: each key becomes a child element tag
        for key, value in data.items():
            sub_elem = SubElement(elem, key)
            _build_xml_element(sub_elem, value, item_tag)
    elif isinstance(data, list):
        # Process list: create multiple child elements with the same tag (item_tag)
        if isinstance(item_tag, Mapping):
            if elem is None or elem.tag not in item_tag:
                _item_tag = item_tag.get("default", "item")
            else:
                _item_tag = item_tag[elem.tag]
        else:
            _item_tag = item_tag

        for item in data:
            item_elem = SubElement(elem, _item_tag)
            _build_xml_element(item_elem, item, item_tag)
    else:
        # Base case: primitive value becomes text content
        elem.text = str(data)


def _mapping_to_xml(
    d: Union[Mapping, Sequence[Mapping], Any, Sequence[Any]],
    root_tag: str = None,
    item_tag: Union[str, Mapping[str, str]] = "item",
    include_root: bool = True,
    include_xml_declaration: bool = False,
    indent: str = "    ",
) -> str:
    """
    Internal implementation for mapping_to_xml.

    Converts a dictionary or sequence of dictionaries to an XML string.
    """
    # Handle the case where input is a sequence (list) of items
    if isinstance(d, Sequence) and not isinstance(d, (str, bytes)):
        if root_tag is None or not include_root:
            return "\n".join(
                (
                    _mapping_to_xml(
                        _d,
                        item_tag=item_tag,
                        include_xml_declaration=(
                            include_xml_declaration if i == 0 else False
                        ),
                    )
                    for i, _d in enumerate(d)
                )
            )
        else:
            # Ensure all items in the sequence are Mappings
            d = [(_d if isinstance(_d, Mapping) else dict_(_d)) for _d in d]
            return _mapping_to_xml(
                {root_tag: d},
                root_tag=None,
                item_tag=item_tag,
                include_root=False,
                include_xml_declaration=include_xml_declaration,
            )
    # Handle non-Mapping input by attempting conversion to dict
    elif not isinstance(d, Mapping):
        try:
            d = dict_(d)
        except (TypeError, AttributeError, ValueError) as e:
            raise ValueError(
                f"Cannot convert input of type '{type(d).__name__}' to a dictionary for XML conversion. "
                f"Expected a Mapping, Sequence of Mappings, or an attrs class instance. "
                f"Original error: {e}"
            ) from e

    # Handle cases where no root tag is specified or root should not be included
    if root_tag is None or not include_root:
        if len(d) == 1:
            root_tag, d = next(iter(d.items()))
            include_root = True
        else:
            return "\n".join(
                (
                    _mapping_to_xml(
                        {k: v},
                        item_tag=item_tag,
                        include_xml_declaration=(
                            include_xml_declaration if i == 0 else False
                        ),
                    )
                    for i, (k, v) in enumerate(d.items())
                )
            )

    # Create the root element with the determined root tag
    root = Element(root_tag)
    data_to_build = d
    _build_xml_element(root, data_to_build, item_tag)

    # Convert to XML string and format with proper indentation
    formatted_xml = tostring(root)
    formatted_xml = parseString(formatted_xml).toprettyxml(indent=indent)
    if not include_xml_declaration:
        formatted_xml = _remove_first_line(formatted_xml, lstrip=True)

    return formatted_xml.rstrip("\n")


def mapping_to_xml(
    d: Union[Mapping, Sequence[Mapping], Any, Sequence[Any]],
    root_tag: str = None,
    item_tag: Union[str, Mapping[str, str]] = "item",
    include_root: bool = True,
    include_xml_declaration: bool = False,
    indent: str = "    ",
    unescape: bool = False,
) -> str:
    """
    Converts a dictionary or a sequence of dictionaries to an XML string.

    Args:
        d (Union[Mapping, Sequence[Mapping]]): The dictionary or sequence of dictionaries to convert.
                                               Nested dictionaries, lists, or simple data types are supported.
        root_tag (str): The root tag name for the XML. If None, the root tag will be excluded from the output.
        item_tag (Union[str, Mapping[str, str]]): Tag name for list items. Can be a string (applies globally)
                                                  or a mapping (applies per parent tag). Defaults to "item".
        include_root (bool): If True, includes the root element in the XML output. Defaults to True.
                             If root_tag is None, include_root is automatically set to False.
        include_xml_declaration (bool): If True, includes the XML declaration (<?xml version="1.0" ?>)
                                        at the beginning. Defaults to False.
        indent (str): The string used for indentation in the XML output. Defaults to 4 spaces.
        unescape (bool): If True, unescapes the XML entities for HTML output. Defaults to False.

    Returns:
        str: XML string representation of the dictionary or sequence of dictionaries.

    Example:
        >>> example_dict = {"name": "John"}
        >>> print(mapping_to_xml(example_dict, include_root=False, indent="    ", include_xml_declaration=True))
        <?xml version="1.0" ?>
        <name>John</name>

        >>> example_dict = {"name": "John & Jane"}
        >>> print(mapping_to_xml(example_dict, root_tag="person", indent="    ", unescape=True))
        <person>
            <name>John & Jane</name>
        </person>
    """
    if not item_tag:
        item_tag = "item"
    if not isinstance(item_tag, (Mapping, str)):
        raise TypeError("'item_tag' must be an instance of 'Mapping' or 'str'")

    xml_string = _mapping_to_xml(
        d=d,
        root_tag=root_tag,
        item_tag=item_tag,
        include_root=include_root,
        include_xml_declaration=include_xml_declaration,
        indent=indent,
    )
    if unescape:
        xml_string = unescape_xml(xml_string, unescape_for_html=True)
    return xml_string
