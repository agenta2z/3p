import html
import re
from collections.abc import Sequence
from typing import Any, Dict, Union, List, Mapping, Iterable, Optional
from xml.dom.minidom import parseString
from xml.etree.ElementTree import Element, fromstring, tostring, SubElement
from xml.sax import saxutils

from python_utils.common_utils import dict_
from python_utils.string_utils import remove_first_line
from python_utils.string_utils.string_sanitization import apply_with_pattern_protection


def xml_format(tag: str, content: str, sep: str = '') -> str:
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
    return f'<{tag}>{sep}{content}{sep}</{tag}>'


def unwrap_xml_simple(xml_string: str) -> str:
    """
    Removes the outermost root tag from an XML string, returning only the inner XML content.

    Args:
        xml_string (str): The XML string to unwrap.

    Returns:
        str: The XML string without the outermost root tags.
    """
    # Find the first and last angle brackets of the root element
    start = xml_string.find('>') + 1
    end = xml_string.rfind('<')

    # Extract and return the content between these brackets
    return xml_string[start:end].strip()


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
    numeric_entity_pattern = re.compile(r'&#([xX]?)([0-9a-fA-F]+);')

    # Function to replace each numeric entity with the corresponding character
    def replace_numeric_entity(match):
        is_hex, num = match.groups()
        try:
            if is_hex.lower() == 'x':
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
        item_tag: Union[str, Mapping[str, str]]
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
        # Example: {"name": "John", "age": 30} creates <name>John</name> and <age>30</age>
        for key, value in data.items():
            sub_elem = SubElement(elem, key)
            _build_xml_element(sub_elem, value, item_tag)  # Recursively process the value
    elif isinstance(data, list):
        # Process list: create multiple child elements with the same tag (item_tag)
        # Determine which item tag to use based on configuration
        if isinstance(item_tag, Mapping):
            # item_tag is a dict mapping parent tags to their item tags
            # Example: {"children": "child", "books": "book"}
            if elem is None or elem.tag not in item_tag:
                # Parent tag not in mapping, use default or 'item'
                _item_tag = item_tag.get('default', 'item')
            else:
                # Parent tag found in mapping, use the specified item tag
                _item_tag = item_tag[elem.tag]
        else:
            # item_tag is a simple string, use it for all lists
            _item_tag = item_tag

        # Create a child element for each item in the list
        # Example: ["apple", "banana"] -> <item>apple</item><item>banana</item>
        for item in data:
            item_elem = SubElement(elem, _item_tag)
            _build_xml_element(item_elem, item, item_tag)  # Recursively process the item
    else:
        # Base case: primitive value (string, int, etc.) becomes text content
        # Example: "John" -> element.text = "John"
        elem.text = str(data)


def _mapping_to_xml(
        d: Union[Mapping, Sequence[Mapping], Any, Sequence[Any]],
        root_tag: str = None,
        item_tag: Union[str, Mapping[str, str]] = "item",
        include_root: bool = True,
        include_xml_declaration: bool = False,
        indent: str = "    "
) -> str:
    # Handle the case where input is a sequence (list) of items
    # Exclude str and bytes as they are sequences but not the type we want to process
    if isinstance(d, Sequence) and not isinstance(d, (str, bytes)):
        # Case 1: No root tag specified or root not wanted
        # Convert each item in the sequence to XML separately and join them with newlines
        # Example: [{"name": "John"}, {"age": 30}] -> "<name>John</name>\n<age>30</age>"
        if root_tag is None or not include_root:
            return '\n'.join(
                (
                    _mapping_to_xml(
                        _d,
                        item_tag=item_tag,
                        # Only include XML declaration for the first item to avoid duplication
                        include_xml_declaration=(
                            include_xml_declaration
                            if i == 0
                            else False
                        )
                    )
                    for i, _d in enumerate(d)
                )
            )
        # Case 2: Root tag specified and root wanted
        # Wrap the entire sequence under a root element with <item> tags for each element
        # Example: [{"name": "John"}, {"name": "Jane"}] with root_tag='people' ->
        # <people>
        #   <item><name>John</name></item>
        #   <item><name>Jane</name></item>
        # </people>
        else:
            # Ensure all items in the sequence are Mappings (convert if needed using dict_())
            d = [
                (_d if isinstance(_d, Mapping) else dict_(_d))
                for _d in d
            ]
            # Recursively process by wrapping sequence in a dict with root_tag as key
            # Set root_tag=None and include_root=False to avoid double-wrapping
            return _mapping_to_xml(
                {root_tag: d},
                root_tag=None,
                item_tag=item_tag,
                include_root=False,
                include_xml_declaration=include_xml_declaration
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
            # Special case: if dict has exactly one key-value pair, use that key as the root tag
            # Example: {"person": {"name": "John"}} -> <person><name>John</name></person>
            root_tag, d = next(iter(d.items()))  # Unpack the single key-value pair
            include_root = True  # Now we have a root tag, so include it
        else:
            # General case: dict has multiple key-value pairs, process each separately
            # Example: {"name": "John", "age": 30} -> "<name>John</name>\n<age>30</age>"
            return '\n'.join(
                (
                    # Recursively convert each key-value pair to XML
                    # Wrap each in its own dict so the key becomes the tag name
                    _mapping_to_xml(
                        {k: v},
                        item_tag=item_tag,
                        # Only include XML declaration on the first element to avoid duplication
                        include_xml_declaration=(
                            include_xml_declaration
                            if i == 0
                            else False
                        )
                    )
                    for i, (k, v) in enumerate(d.items())
                )
            )

    # Create the root element with the determined root tag
    root = Element(root_tag)
    data_to_build = d
    # Build the entire XML tree by recursively processing the data using the helper function
    _build_xml_element(root, data_to_build, item_tag)

    # Convert to XML string and format with proper indentation
    formatted_xml = tostring(root)  # Convert Element tree to bytes
    formatted_xml = parseString(formatted_xml).toprettyxml(indent=indent)  # Pretty-print with indentation
    if not include_xml_declaration:
        # Remove the XML declaration line (<?xml version="1.0" ?>)
        formatted_xml = remove_first_line(formatted_xml, lstrip=True)

    # Remove trailing newlines and return the formatted XML string
    return formatted_xml.rstrip('\n')


def mapping_to_xml(
        d: Union[Mapping, Sequence[Mapping], Any, Sequence[Any]],
        root_tag: str = None,
        item_tag: Union[str, Mapping[str, str]] = "item",
        include_root: bool = True,
        include_xml_declaration: bool = False,
        indent: str = "    ",
        unescape: bool = False
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
        include_xml_declaration (bool): If True, includes the XML declaration (<?xml version="1.0" ?>) at the beginning. Defaults to False.
        indent (str): The string used for indentation in the XML output. Defaults to 4 spaces.
        unescape (bool): If True, unescapes the XML entities for HTML output. Defaults to False.

    Returns:
        str: XML string representation of the dictionary or sequence of dictionaries.

    Example:
        Edge case: Empty dictionary without root tag
        >>> example_empty_dict = {}
        >>> print(mapping_to_xml(example_empty_dict, include_root=False))
        <BLANKLINE>

        Edge case single mapping
        >>> example_dict = {"name": "John"}
        >>> print(mapping_to_xml(example_dict, include_root=False, indent="    ", include_xml_declaration=True))
        <?xml version="1.0" ?>
        <name>John</name>

        Edge case with single mapping
        >>> example_dict = {"single": {"item": "value"}}
        >>> print(mapping_to_xml(example_dict, root_tag='root', include_root=True, indent="    "))
        <root>
            <single>
                <item>value</item>
            </single>
        </root>

        Simple example with unescaped XML
        >>> example_dict = {"name": "John & Jane"}
        >>> print(mapping_to_xml(example_dict, root_tag="person", indent="    ", unescape=True))
        <person>
            <name>John & Jane</name>
        </person>

        Example with escaped XML
        >>> print(mapping_to_xml(example_dict, root_tag="person", indent="    ", unescape=False))
        <person>
            <name>John &amp; Jane</name>
        </person>

        Example with a sequence of dictionaries, 'include_xml_declaration' set True, and using default item tag
        >>> example_dict = {
        ...     "person": {
        ...         "name": "John",
        ...         "age": 30,
        ...         "city": "New York",
        ...         "children": [
        ...             {"name": "Jane", "age": 10},
        ...             {"name": "Doe", "age": 5}
        ...         ]
        ...     }
        ... }
        >>> print(mapping_to_xml(example_dict, root_tag='root', indent="    ", include_xml_declaration=True))
        <?xml version="1.0" ?>
        <root>
            <person>
                <name>John</name>
                <age>30</age>
                <city>New York</city>
                <children>
                    <item>
                        <name>Jane</name>
                        <age>10</age>
                    </item>
                    <item>
                        <name>Doe</name>
                        <age>5</age>
                    </item>
                </children>
            </person>
        </root>

        Example without root and without declaration
        >>> print(mapping_to_xml(example_dict, indent="    "))
        <person>
            <name>John</name>
            <age>30</age>
            <city>New York</city>
            <children>
                <item>
                    <name>Jane</name>
                    <age>10</age>
                </item>
                <item>
                    <name>Doe</name>
                    <age>5</age>
                </item>
            </children>
        </person>

        Example with a sequence of dictionaries and no root
        >>> example_sequence = [
        ...     {"name": "John", "age": 30},
        ...     {"name": "Jane", "age": 25}
        ... ]
        >>> print(mapping_to_xml(example_sequence, include_root=False, indent="    "))
        <name>John</name>
        <age>30</age>
        <name>Jane</name>
        <age>25</age>
        >>> print(mapping_to_xml(example_sequence, include_root=False, indent="    ", include_xml_declaration=True))
        <?xml version="1.0" ?>
        <name>John</name>
        <age>30</age>
        <name>Jane</name>
        <age>25</age>

        Example with a sequence of dictionaries and a root tag
        >>> print(mapping_to_xml(example_sequence, root_tag='people', indent="    ", include_xml_declaration=True))
        <?xml version="1.0" ?>
        <people>
            <item>
                <name>John</name>
                <age>30</age>
            </item>
            <item>
                <name>Jane</name>
                <age>25</age>
            </item>
        </people>

        Example with a sequence of dictionaries and a root tag, and using customized item tag
        >>> print(mapping_to_xml(example_sequence, root_tag='people', item_tag='person', indent="    ", include_xml_declaration=True))
        <?xml version="1.0" ?>
        <people>
            <person>
                <name>John</name>
                <age>30</age>
            </person>
            <person>
                <name>Jane</name>
                <age>25</age>
            </person>
        </people>

        Example with a non-top-level sequence of dictionaries with different keys
        >>> example_sequence = {
        ...     'person': {
        ...         'name': 'John',
        ...         'age': '30',
        ...         'city': 'New York',
        ...         'children': {
        ...             'infants': [
        ...                 {'name': 'Baby Jane', 'age': '1'},
        ...                 {'name': 'Baby Emma', 'age': '0'}
        ...             ],
        ...             'toddlers': [
        ...                 {'name': 'Toddler Tim', 'age': '3'}
        ...             ],
        ...         }
        ...     }
        ... }
        >>> print(mapping_to_xml(example_sequence, indent="    "))
        <person>
            <name>John</name>
            <age>30</age>
            <city>New York</city>
            <children>
                <infants>
                    <item>
                        <name>Baby Jane</name>
                        <age>1</age>
                    </item>
                    <item>
                        <name>Baby Emma</name>
                        <age>0</age>
                    </item>
                </infants>
                <toddlers>
                    <item>
                        <name>Toddler Tim</name>
                        <age>3</age>
                    </item>
                </toddlers>
            </children>
        </person>

        Example with a non-top-level sequence of dictionaries with different keys, and using customized item tag
        >>> print(mapping_to_xml(example_sequence, item_tag={"infants": "infant", "toddlers": "toddler"}, indent="    "))
        <person>
            <name>John</name>
            <age>30</age>
            <city>New York</city>
            <children>
                <infants>
                    <infant>
                        <name>Baby Jane</name>
                        <age>1</age>
                    </infant>
                    <infant>
                        <name>Baby Emma</name>
                        <age>0</age>
                    </infant>
                </infants>
                <toddlers>
                    <toddler>
                        <name>Toddler Tim</name>
                        <age>3</age>
                    </toddler>
                </toddlers>
            </children>
        </person>

        Using an attrs class
        >>> from attr import attrs, attrib
        >>> @attrs
        ... class Person:
        ...     name: str = attrib()
        ...     age: int = attrib()
        ...     city: str = attrib()
        >>> person_instance = Person(name="John", age=30, city="New York")
        >>> print(mapping_to_xml(person_instance, root_tag="person", indent="    ", include_xml_declaration=False))
        <person>
            <name>John</name>
            <age>30</age>
            <city>New York</city>
        </person>
        >>> persons = [Person(name="John", age=30, city="New York"), Person(name="Jane", age=25, city="Los Angeles")]
        >>> print(mapping_to_xml(persons, indent="    ", include_xml_declaration=False))
        <name>John</name>
        <age>30</age>
        <city>New York</city>
        <name>Jane</name>
        <age>25</age>
        <city>Los Angeles</city>
        >>> print(mapping_to_xml(persons, root_tag='persons', indent="    ", include_xml_declaration=False))
        <persons>
            <item>
                <name>John</name>
                <age>30</age>
                <city>New York</city>
            </item>
            <item>
                <name>Jane</name>
                <age>25</age>
                <city>Los Angeles</city>
            </item>
        </persons>
    """
    if not item_tag:
        item_tag = 'item'
    if not isinstance(item_tag, (Mapping, str)):
        raise TypeError("'item_tag' must be an instance of 'Mapping' or 'str'")

    xml_string = _mapping_to_xml(
        d=d,
        root_tag=root_tag,
        item_tag=item_tag,
        include_root=include_root,
        include_xml_declaration=include_xml_declaration,
        indent=indent
    )
    if unescape:
        xml_string = unescape_xml(xml_string, unescape_for_html=True)
    return xml_string


def xml_to_dict(
        element: Union[Element, str],
        use_xmltodict: bool = False,
        allows_xml_lines_without_root: bool = False,
        merge_same_tag_elements_as_list: bool = True,
        always_interpret_children_as_list: Union[bool, Iterable[str]] = False,
        always_interpret_children_as_string: Iterable[str] = (),
        exclude_paths: Iterable[str] = None,
        current_path: str = "",
        use_lxml_parser: bool = False,
        lenient_parsing: bool = True,
        unescape: bool = False,
        dummy_root_tag='root',
        protect_code_blocks: bool = True,
        code_block_patterns: Union[str, List[str], List[re.Pattern]] = None,
        code_block_restore_group: Union[None, int, List[int]] = None
) -> Dict[str, Any]:
    """
    Parses an XML string or Element and converts it into a dictionary.
    Only texts between XML tags are converted to dictionary values with the tags as their keys. Attributes are ignored.
    Supports non-standard XML without a single root by wrapping it in a dummy root element.

    Args:
        element (Union[Element, str]): The XML element or string to parse. If a string is provided,
                                       it will be parsed into an Element first.
        use_xmltodict (bool): If True, uses the `xmltodict` library to parse the XML. Defaults to False.
        allows_xml_lines_without_root (bool): If True, wraps XML without a root in a dummy root tag for parsing.
        merge_same_tag_elements_as_list (bool): Merges elements with the same tag into a list.
        always_interpret_children_as_list (Union[bool, Iterable[str]]):
            - If True, the children of *every* element are returned as a list of dictionaries (even if no duplicate tags).
            - If given a list of tag names, only elements whose tag is in that list have their children returned as a list.
        always_interpret_children_as_string (Iterable[str]):
            - A list of tag names for which the function will **not** recursively parse child elements.
              Instead, it will treat **all** the element’s children (including text around them) as one single string.
              This is useful if you want to keep embedded markup or text together without further dict nesting.
        exclude_paths (Iterable[str]): A collection of paths to exclude from parsing, retaining only inner XML content string.
        current_path (str): assume the input `element` is under this "currrent" path when matching with `exclude_paths`.
        use_lxml_parser (bool): If True, uses the `lxml` library for XML parsing. Defaults to False.
                                When False, uses the built-in `xml.etree.ElementTree`.
        lenient_parsing (bool): If True, enables lenient parsing to handle malformed XML (e.g., unescaped special characters).
                                Defaults to True. More effective when `use_lxml_parser` is True; only tolerates unescaped '&' if `use_lxml_parser` is False.
        unescape (bool): If True, unescapes XML entities in the resulting dictionary's string values. Defaults to False.
        dummy_root_tag (str): Tag name for the dummy root when `allows_xml_lines_without_root` is True.
        protect_code_blocks (bool): If True, protects markdown fenced code blocks (```language\ncode```) from interfering with XML parsing.
                                     Defaults to True. Only applies when element is a string.
        code_block_patterns (Union[str, List[str], List[re.Pattern]]): Custom regex pattern(s) for code block protection.
                                                                         Default: r'```([a-zA-Z0-9_+-]*)\\n(.*?)```' (markdown fenced code blocks).
                                                                         Can be a single pattern or list of patterns.
        code_block_restore_group (Union[None, int, List[int]]): Which capture group(s) to restore after parsing.
                                                                  - None (default): restore full match (keep ```language\ncode```)
                                                                  - -1: restore last group (just code content)
                                                                  - 1: restore first group (language identifier)
                                                                  - [1, 2]: join multiple groups

    Returns:
        Dict[str, Any]: A dictionary representation of the XML data.

    Examples:
        >>> xml_data = '''
        ... <person>
        ...     <name>John</name>
        ...     <age>30</age>
        ...     <city>New York</city>
        ...     <children>
        ...         <child>
        ...             <name>Jane</name>
        ...             <age>10</age>
        ...         </child>
        ...         <child>
        ...             <name>Doe</name>
        ...             <age>5</age>
        ...         </child>
        ...     </children>
        ... </person>
        ... '''
        >>> xml_to_dict(xml_data)
        {'person': {'name': 'John', 'age': '30', 'city': 'New York', 'children': {'child': [{'name': 'Jane', 'age': '10'}, {'name': 'Doe', 'age': '5'}]}}}

        Example with different child types under children. You have the option not to merge elements of the same type as a list.
        >>> xml_data = '''
        ... <person>
        ...     <name>John</name>
        ...     <age>30</age>
        ...     <city>New York</city>
        ...     <children>
        ...         <infant>
        ...             <name>Baby Jane</name>
        ...             <age>1</age>
        ...         </infant>
        ...         <infant>
        ...             <name>Baby Emma</name>
        ...             <age>0</age>
        ...         </infant>
        ...         <toddler>
        ...             <name>Toddler Tim</name>
        ...             <age>3</age>
        ...         </toddler>
        ...         <child>
        ...             <name>Child Doe</name>
        ...             <age>5</age>
        ...         </child>
        ...     </children>
        ... </person>
        ... '''
        >>> xml_to_dict(xml_data)
        {'person': {'name': 'John', 'age': '30', 'city': 'New York', 'children': {'infant': [{'name': 'Baby Jane', 'age': '1'}, {'name': 'Baby Emma', 'age': '0'}], 'toddler': {'name': 'Toddler Tim', 'age': '3'}, 'child': {'name': 'Child Doe', 'age': '5'}}}}
        >>> xml_to_dict(xml_data, merge_same_tag_elements_as_list=False)
        {'person': {'name': 'John', 'age': '30', 'city': 'New York', 'children': [{'infant': {'name': 'Baby Jane', 'age': '1'}}, {'infant': {'name': 'Baby Emma', 'age': '0'}}, {'toddler': {'name': 'Toddler Tim', 'age': '3'}}, {'child': {'name': 'Child Doe', 'age': '5'}}]}}

        Non-standard XML with multiple root-level tags
        >>> xml_data = '''
        ... <name>John</name>
        ... <age>30</age>
        ... <city>New York</city>
        ... '''
        >>> xml_to_dict(xml_data, allows_xml_lines_without_root=True)
        {'name': 'John', 'age': '30', 'city': 'New York'}

        Example with `xmltodict`:
        >>> xml_to_dict(xml_data, allows_xml_lines_without_root=True, use_xmltodict=True, merge_same_tag_elements_as_list=False)
        {'name': 'John', 'age': '30', 'city': 'New York'}

        Complex XML with multiple root-level tags
        >>> xml_data = '''<NewTask>true</NewTask>
        ... <TaskStatus>Ongoing</TaskStatus>
        ... <InstantResponse>I found multiple ways to arrange a table at Happy Lamb Hot Pot Seattle. Let me help you proceed with the booking.</InstantResponse>
        ... <ImmediateNextActions>
        ... <AlternativeActions>
        ...  <Description>Access the restaurant's booking platform to make a reservation for 2 people at 12pm</Description>
        ...   <Action>
        ...    <Target>653</Target>
        ...    <Type>Interaction.Click</Type>
        ...   </Action>
        ...   <Action>
        ...    <Target>1894</Target>
        ...    <Type>Interaction.Click</Type>
        ...   </Action>
        ...  </AlternativeActions>
        ... </ImmediateNextActions>
        ... <PlannedActions>After accessing the booking platform, examine the webpage for available time slots and proceed with making the reservation for 2 people at 12pm.</PlannedActions>'''
        >>> xml_to_dict(xml_data, allows_xml_lines_without_root = True, merge_same_tag_elements_as_list=False)
        {'NewTask': 'true', 'TaskStatus': 'Ongoing', 'InstantResponse': 'I found multiple ways to arrange a table at Happy Lamb Hot Pot Seattle. Let me help you proceed with the booking.', 'ImmediateNextActions': {'AlternativeActions': [{'Description': "Access the restaurant's booking platform to make a reservation for 2 people at 12pm"}, {'Action': {'Target': '653', 'Type': 'Interaction.Click'}}, {'Action': {'Target': '1894', 'Type': 'Interaction.Click'}}]}, 'PlannedActions': 'After accessing the booking platform, examine the webpage for available time slots and proceed with making the reservation for 2 people at 12pm.'}

        Example with `xmltodict`:
        >>> xml_to_dict(xml_data, allows_xml_lines_without_root=True, use_xmltodict=True, merge_same_tag_elements_as_list=False)
        {'NewTask': 'true', 'TaskStatus': 'Ongoing', 'InstantResponse': 'I found multiple ways to arrange a table at Happy Lamb Hot Pot Seattle. Let me help you proceed with the booking.', 'ImmediateNextActions': {'AlternativeActions': {'Description': "Access the restaurant's booking platform to make a reservation for 2 people at 12pm", 'Action': [{'Target': '653', 'Type': 'Interaction.Click'}, {'Target': '1894', 'Type': 'Interaction.Click'}]}}, 'PlannedActions': 'After accessing the booking platform, examine the webpage for available time slots and proceed with making the reservation for 2 people at 12pm.'}

        Parse while excluding 'InstantResponse.Response.Answer'
        >>> xml_data = '''
        ... <InstantResponse>
        ...     <Response>
        ...         <Index>1</Index>
        ...         <Answer>
        ...             <h3>Dark Choco Nutty Frappuccino Recipe</h3>
        ...             <p>Here's how to order this chocolate cold drink:</p>
        ...             <ul>
        ...                 <li>Start with: Order a Mocha Frappuccino as your base drink</li>
        ...             </ul>
        ...         </Answer>
        ...     </Response>
        ... </InstantResponse>
        ... '''

        >>> xml_to_dict(xml_data, exclude_paths=["InstantResponse.Response.Answer"])
        {'InstantResponse': {'Response': {'Index': '1', 'Answer': "<h3>Dark Choco Nutty Frappuccino Recipe</h3>\\n            <p>Here's how to order this chocolate cold drink:</p>\\n            <ul>\\n                <li>Start with: Order a Mocha Frappuccino as your base drink</li>\\n            </ul>"}}}

        Example with lenient_parsing=False (default) and malformed XML
        >>> xml_data = '''
        ... <message>
        ...     Hello & Welcome <User>!
        ...     <details>Price is 100 & tax is €.</details>
        ... </message>
        ... '''

        Parsing with lenient_parsing=False will raise an error
        >>> try:
        ...     xml_to_dict(xml_data, use_lxml_parser=True, lenient_parsing=False)
        ... except Exception as e:
        ...     print(f"Error: {e}")
        Error: xmlParseEntityRef: no name, line 3, column 12 (<string>, line 3)

        Example with lenient_parsing=True and malformed XML
        >>> # Using lxml with lenient parsing
        >>> xml_to_dict(xml_data, use_lxml_parser=True, lenient_parsing=True)
        {'message': {'User': {'details': 'Price is 100  tax is €.', '#text': '!'}, '#text': 'Hello  Welcome'}}

        Another example with unescaped special characters
        >>> xml_data = '''
        ... <note>
        ...     <to>Tove &amp; Lena</to>
        ...     <from>Jani</from>
        ...     <heading>Reminder</heading>
        ...     <body>Don't forget me this weekend & see you soon!</body>
        ... </note>
        ... '''

        Parsing with lenient_parsing=False will fail
        >>> try:
        ...     xml_to_dict(xml_data, use_lxml_parser=False, lenient_parsing=False)
        ... except Exception as e:
        ...     print(f"Error: {e}")
        Error: not well-formed (invalid token): line 6, column 40

        Parsing with lenient_parsing=True succeeds
        >>> xml_to_dict(xml_data, use_lxml_parser=False, lenient_parsing=True)
        {'note': {'to': 'Tove & Lena', 'from': 'Jani', 'heading': 'Reminder', 'body': "Don't forget me this weekend & see you soon!"}}

        Example with unescape=False (default)
        >>> xml_data = '''
        ... <message>
        ...     Hello &amp; Welcome &lt;User&gt;!
        ...     <details>Price is 100 &amp; tax is &#x20AC;.</details>
        ... </message>
        ... '''
        >>> xml_to_dict(xml_data, use_lxml_parser=False)
        {'message': {'details': 'Price is 100 & tax is &#x20AC;.', '#text': 'Hello & Welcome <User>!'}}

        Example with unescape=True
        >>> xml_to_dict(xml_data, unescape=True)
        {'message': {'details': 'Price is 100 & tax is €.', '#text': 'Hello & Welcome <User>!'}}

        Parsing with unescape=True and lenient_parsing=True
        >>> xml_data = '''
        ... <note>
        ...     <to>Tove &amp; Lena</to>
        ...     <from>Jani</from>
        ...     <heading>Reminder</heading>
        ...     <body>Don't forget me this weekend &amp; see you soon!</body>
        ... </note>
        ... '''
        >>> xml_to_dict(xml_data, unescape=True)
        {'note': {'to': 'Tove & Lena', 'from': 'Jani', 'heading': 'Reminder', 'body': "Don't forget me this weekend & see you soon!"}}

        Parsing with unescape=True and lenient_parsing=True on malformed XML
        >>> xml_data = '''
        ... <data>
        ...     <value>10 &lt; 20</value>
        ...     <description>Temperature is &gt; 30°C</description>
        ... </data>
        ... '''
        >>> xml_to_dict(xml_data, use_lxml_parser=True, lenient_parsing=True, unescape=True)
        {'data': {'value': '10 < 20', 'description': 'Temperature is > 30°C'}}

        Example with `always_interpret_children_as_list` limited to a tag in a sequence.
        >>> xml_data = '''
        ... <library>
        ...     <name>City Library</name>
        ...     <books>
        ...         <book>
        ...             <title>The Great Gatsby</title>
        ...             <author>F. Scott Fitzgerald</author>
        ...         </book>
        ...         <book>
        ...             <title>1984</title>
        ...             <author>George Orwell</author>
        ...         </book>
        ...     </books>
        ... </library>
        ... '''
        >>> xml_to_dict(xml_data, always_interpret_children_as_list=True)
        {'library': [{'name': 'City Library'}, {'books': [{'book': [{'title': 'The Great Gatsby'}, {'author': 'F. Scott Fitzgerald'}]}, {'book': [{'title': '1984'}, {'author': 'George Orwell'}]}]}]}
        >>> xml_to_dict(xml_data, always_interpret_children_as_list=["books"])
        {'library': {'name': 'City Library', 'books': [{'book': {'title': 'The Great Gatsby', 'author': 'F. Scott Fitzgerald'}}, {'book': {'title': '1984', 'author': 'George Orwell'}}]}}

        # Treat an element's children as a single string
        >>> xml_to_dict(xml_data, always_interpret_children_as_list=["books"], always_interpret_children_as_string = ['book'])
        {'library': {'name': 'City Library', 'books': [{'book': '<title>The Great Gatsby</title>\\n            <author>F. Scott Fitzgerald</author>'}, {'book': '<title>1984</title>\\n            <author>George Orwell</author>'}]}}
        >>> xml_data = '''
        ... <article>
        ...   <title>New Discovery</title>
        ...   <body>This is the body. <b>It contains some bold text</b> plus more text.</body>
        ... </article>
        ... '''
        >>> xml_to_dict(xml_data, always_interpret_children_as_string=['body'])
        {'article': {'title': 'New Discovery', 'body': 'This is the body. <b>It contains some bold text</b> plus more text.'}}

        Example with code block protection (default behavior - preserves full markdown)
        >>> xml_with_code = '''
        ... <tutorial>
        ...     <title>Python Basics</title>
        ...     <example>```python
        ... x = 5 & 3  # Bitwise AND
        ... y = 10 < 20
        ... ```</example>
        ... </tutorial>
        ... '''
        >>> result = xml_to_dict(xml_with_code)
        >>> 'python' in result['tutorial']['example']
        True
        >>> '&' in result['tutorial']['example']
        True

        Example with code block protection (extract only code content)
        >>> result = xml_to_dict(xml_with_code, code_block_restore_group=-1)
        >>> result['tutorial']['example']
        'x = 5 & 3  # Bitwise AND\\ny = 10 < 20\\n'

        Example with HTML code blocks
        >>> xml_with_html = '''
        ... <documentation>
        ...     <html_example>```html
        ... <div class="container">
        ...     <p>Hello & Welcome</p>
        ... </div>
        ... ```</html_example>
        ... </documentation>
        ... '''
        >>> result = xml_to_dict(xml_with_html, code_block_restore_group=-1)
        >>> '<div' in result['documentation']['html_example']
        True

        Example with multiple code blocks
        >>> xml_multi_code = '''
        ... <guide>
        ...     <python>```python
        ... print("hello")
        ... ```</python>
        ...     <javascript>```javascript
        ... console.log("world");
        ... ```</javascript>
        ... </guide>
        ... '''
        >>> result = xml_to_dict(xml_multi_code, code_block_restore_group=-1)
        >>> 'print' in result['guide']['python']
        True
        >>> 'console.log' in result['guide']['javascript']
        True

        Example with code block protection disabled
        >>> try:
        ...     xml_to_dict(xml_with_code, protect_code_blocks=False)
        ... except Exception as e:
        ...     print("Parsing failed due to XML-breaking characters")
        Parsing failed due to XML-breaking characters

    Note:
        - When `use_xmltodict` is True, the parameters `merge_same_tag_elements_as_list` and `exclude_paths` are not supported.
        - When `use_lxml_parser` is True, ensure the `lxml` library is installed.
        - The `lenient_parsing` option is more effective when `use_lxml_parser` is True.
    """
    # Early return with code block protection if enabled and element is string
    if protect_code_blocks and isinstance(element, str):
        # Default pattern for markdown fenced code blocks
        if code_block_patterns is None:
            code_block_patterns = r'```([a-zA-Z0-9_+-]*)\n(.*?)```'

        # Default restore_group: None (preserve full markdown format)
        restore_group = code_block_restore_group if code_block_restore_group is not None else None

        # Define operation that performs XML parsing
        def xml_parse_operation(protected_str: str) -> Dict[str, Any]:
            # Call xml_to_dict recursively with protection disabled
            return xml_to_dict(
                element=protected_str,
                use_xmltodict=use_xmltodict,
                allows_xml_lines_without_root=allows_xml_lines_without_root,
                merge_same_tag_elements_as_list=merge_same_tag_elements_as_list,
                always_interpret_children_as_list=always_interpret_children_as_list,
                always_interpret_children_as_string=always_interpret_children_as_string,
                exclude_paths=exclude_paths,
                current_path=current_path,
                use_lxml_parser=use_lxml_parser,
                lenient_parsing=lenient_parsing,
                unescape=unescape,
                dummy_root_tag=dummy_root_tag,
                protect_code_blocks=False  # Disable protection to avoid infinite recursion
            )

        # Apply protection and parse
        return apply_with_pattern_protection(
            text=element,
            operation=xml_parse_operation,
            protection_patterns=code_block_patterns,
            restore_group=restore_group
        )

    # If not protecting or not a string, continue with original logic
    if use_lxml_parser:
        import lxml.etree as etree
        _XMLParser = etree.XMLParser
        _fromstring = etree.fromstring
        _tostring = etree.tostring
        _Element = etree._Element
    else:
        _fromstring = fromstring
        _tostring = tostring
        _Element = Element

    if allows_xml_lines_without_root and isinstance(element, str):
        element = f"<{dummy_root_tag}>{element}</{dummy_root_tag}>"
    else:
        allows_xml_lines_without_root = False

    # Use xmltodict if specified
    if use_xmltodict:
        if merge_same_tag_elements_as_list:
            raise ValueError(
                "Cannot set 'merge_same_tag_elements_as_list' as True when using xmltodict package"
            )
        if exclude_paths:
            raise ValueError(
                "Cannot set 'exclude_paths' when using xmltodict package"
            )
        import xmltodict
        result = xmltodict.parse(element)
        if allows_xml_lines_without_root:
            result = result[dummy_root_tag]
    else:
        if isinstance(element, str):
            if use_lxml_parser:
                parser = _XMLParser(recover=lenient_parsing)
                element = _fromstring(element, parser=parser)
            else:
                if lenient_parsing:
                    element = re.sub(r'&(?!\w+;)', '&amp;', element)
                element = _fromstring(element)

        def element_to_dict(elem: _Element, _path: str) -> Union[Dict[str, Any], str]:
            # Check if path matches any in exclude_paths
            if exclude_paths and _path in exclude_paths:
                # Extract only the inner content of the element as a raw string
                inner_content = ''.join(_tostring(child, encoding='unicode') for child in elem)
                return inner_content.strip()

            # Handle text-only elements
            text = elem.text.strip() if elem.text else ""
            if unescape:
                text = unescape_xml(text, unescape_for_html=True)

            if len(elem) == 0:
                return text

            # region create two conditional flags `_force_interpret_children_as_list` and `_has_duplicate_child_tags`
            if elem.tag in always_interpret_children_as_string:
                # We skip recursion for this element's children
                # Build a single string: possibly the text + child elements
                raw_pieces = []
                if elem.text:
                    raw_pieces.append(elem.text)
                for child in elem:
                    raw_pieces.append(_tostring(child, encoding='unicode'))
                # Combine and unescape if requested
                raw_xml = ''.join(raw_pieces).strip()
                return unescape_xml(raw_xml, unescape_for_html=True) if unescape else raw_xml

            _force_interpret_children_as_list = (
                    (always_interpret_children_as_list is True)
                    or (
                            isinstance(always_interpret_children_as_list, Iterable)
                            and (elem.tag is not None and elem.tag in always_interpret_children_as_list)
                    )

            )
            child_tags = [child.tag for child in elem]
            _has_duplicate_child_tags = len(child_tags) != len(set(child_tags))
            # endregion

            if (
                    _force_interpret_children_as_list or
                    (_has_duplicate_child_tags and (not merge_same_tag_elements_as_list))
            ):
                result = []
                for child in elem:
                    child_path = f"{_path}.{child.tag}" if _path else child.tag
                    child_data = element_to_dict(child, child_path)
                    result.append({child.tag: child_data})

                if text:
                    result.append({'#text': text})

                return result
            elif merge_same_tag_elements_as_list:
                # `_force_interpret_children_as_list` is False, and `merge_same_tag_elements_as_list` is True,
                # then merging same tags into lists
                result = {}
                for child in elem:
                    child_path = f"{_path}.{child.tag}" if _path else child.tag
                    child_data = element_to_dict(child, child_path)
                    if child.tag in result:
                        if isinstance(result[child.tag], list):
                            result[child.tag].append(child_data)
                        else:
                            result[child.tag] = [result[child.tag], child_data]
                    else:
                        result[child.tag] = child_data

                if text:
                    result['#text'] = text

                return result
            else:
                # `_force_interpret_children_as_list` and `merge_same_tag_elements_as_list`
                #  and `_has_duplicate_child_tags` are all False
                # Process children as dictionary since no duplicates
                result = {}
                for child in elem:
                    child_path = f"{_path}.{child.tag}" if _path else child.tag
                    result[child.tag] = element_to_dict(child, child_path)

                if text:
                    result['#text'] = text

                return result

        # Handle the root element
        if allows_xml_lines_without_root:
            result = element_to_dict(element, current_path)
        else:
            root_tag = element.tag
            full_path = f"{current_path}.{root_tag}" if current_path else root_tag
            result = {root_tag: element_to_dict(element, full_path)}

    return result
