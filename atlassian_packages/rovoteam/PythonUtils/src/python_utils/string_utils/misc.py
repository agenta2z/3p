from collections import defaultdict
from typing import Optional, Iterable, Callable, Tuple, List, Union, Mapping
from python_utils.string_utils.common import OccurrenceOptions
from python_utils.string_utils.regex import sub_last, sub_first, sub
import re


def get_human_int_str(
        num: int,
        num_digits: int = 3,
        magnitude_letters=('K', 'M', 'B', 'T')
) -> str:
    """
    Gets a concise human-readable string to represent an integer, usually large integer.
    The representation has a float number part with at most `num_digits` digits,
        followed by a magnitude letttr like K, M, B, T;
        for example, '1.82M'.

    Examples:
        >>> get_human_int_str(1000000)
        '1M'
        >>> get_human_int_str(1621)
        '1.62K'
        >>> get_human_int_str(28234231, num_digits=4, magnitude_letters=('k', 'm', 'b', 't'))
        '28.23m'
    """
    num = int(num)
    num = float(f'{{:.{num_digits}g}}'.format(num))
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0
    return '{}{}'.format(
        '{:f}'.format(num).rstrip('0').rstrip('.'), ['', *magnitude_letters][magnitude]
    )


def adjust_num_in_str(
        string: str,
        adjust: int = 1,
        occurrence: OccurrenceOptions = OccurrenceOptions.Last
):
    """
    Adjusts numbers in the string by the quantity specified in argument `adjust`.

    Args:
        string: the string.
        adjust: the adjustment to the number(s).
        occurrence: indicates whether we adjust
            the first number, last number or all numbers in the string.

    Returns: the string with numbers in it adjusted.

    Examples:
        >>> adjust_num_in_str('v1.1')
        'v1.2'
        >>> adjust_num_in_str('v1.1', occurrence=OccurrenceOptions.First)
        'v2.1'
        >>> adjust_num_in_str('v1.1', occurrence=OccurrenceOptions.All)
        'v2.2'
        >>> adjust_num_in_str('v1.1', adjust=-1)
        'v1.0'
        >>> adjust_num_in_str('v001')
        'v002'
        >>> adjust_num_in_str('v999')
        'v1000'

    """
    if occurrence == occurrence.Last:
        return sub_last(
            pattern='[0-9]+',
            repl=lambda x: '{{:0{}d}}'.format(len(x.group(0))).format(int(x.group(0)) + adjust),
            string=string
        )
    elif occurrence == occurrence.First:
        return sub_first(
            pattern='[0-9]+',
            repl=lambda x: '{{:0{}d}}'.format(len(x.group(0))).format(int(x.group(0)) + adjust),
            string=string
        )
    else:
        return sub(
            pattern='[0-9]+',
            repl=lambda x: '{{:0{}d}}'.format(len(x.group(0))).format(int(x.group(0)) + adjust),
            string=string
        )


def increment_num_in_str(s: str, occurrence: OccurrenceOptions = OccurrenceOptions.Last):
    """
    Increments the number(s) in the string by 1.

    This is a convenience wrapper around `adjust_num_in_str` with `adjust=1`.

    Args:
        s: The string containing numbers to increment.
        occurrence: Indicates whether to increment the first, last, or all numbers.

    Returns:
        str: The string with numbers incremented by 1.

    Examples:
        >>> increment_num_in_str('v1.0')
        'v1.1'
        >>> increment_num_in_str('file_001')
        'file_002'
        >>> increment_num_in_str('v1.0', occurrence=OccurrenceOptions.First)
        'v2.0'
    """
    return adjust_num_in_str(s, adjust=1, occurrence=occurrence)


def get_domain_from_name(name: str, domain_separator: str = '.') -> Optional[str]:
    """
    Extracts the domain (the substring before the first occurrence of the domain separator) from a given name.

    If the name contains the domain separator, this function returns the part of the name before the separator.
    If the separator is not found, the function returns None. This function is particularly useful for parsing
    names that follow a domain-based notation (e.g., domain-specific language terms, hierarchical identifiers).

    Args:
        name: The string from which to extract the domain.
        domain_separator: The character used to separate the domain from the rest of the string. Defaults to '.'.

    Returns:
        The domain extracted from the name if the separator is present; otherwise, None.

    Examples:
        >>> get_domain_from_name('subdomain.domain.com')
        'subdomain'

        >>> get_domain_from_name('domain.com', domain_separator='.')
        'domain'

        >>> get_domain_from_name('singleword')

        >>> get_domain_from_name('namespace::classname', domain_separator='::')
        'namespace'
    """
    if name:
        function_name_splits = name.split(domain_separator, maxsplit=1)
        if len(function_name_splits) == 2:
            return function_name_splits[0]


def camel_to_snake_case(camel_str):
    """Converts a CamelCase string to snake_case, including cases with consecutive uppercase letters.

    Args:
        camel_str (str): The CamelCase string to be converted.

    Returns:
        str: The converted snake_case string.

    Example:
        >>> camel_to_snake_case("Type")
        'type'
        >>> camel_to_snake_case("TYPE")
        'type'
        >>> camel_to_snake_case("InputText")
        'input_text'
        >>> camel_to_snake_case("ExampleString")
        'example_string'
        >>> camel_to_snake_case("GPUFrequency")
        'gpu_frequency'
        >>> camel_to_snake_case("HTTPServerError")
        'http_server_error'
        >>> camel_to_snake_case("http_server_error")
        'http_server_error'
    """
    # Match uppercase sequences followed by lowercase letters, adding underscores
    snake_str = re.sub(r'(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])', '_', camel_str).lower()
    return snake_str


def snake_to_camel_case(snake_str):
    """Converts a snake_case string to CamelCase.

    Args:
        snake_str (str): The snake_case string to be converted.

    Returns:
        str: The converted CamelCase string.

    Example:
        >>> snake_to_camel_case("input_text")
        'InputText'
        >>> snake_to_camel_case("example_string")
        'ExampleString'
        >>> snake_to_camel_case("ExampleString")
        'ExampleString'
    """
    camel_str = ''.join((word[0].upper() + word[1:]) for word in snake_str.split('_'))
    return camel_str


def get_processed_strings_and_map(
        strs: Iterable[str],
        str_proc: Callable,
        filter: Callable = None,
        keep_the_identical_in_map: bool = False,
        allow_duplicates_in_map: bool = False,
        **kwargs
) -> Tuple[List[str], Union[Mapping[str, str], Mapping[str, List[str]]]]:
    """
    Applies string processing function `str_proc` to `strs`, returns the processed strings
        and an map between processed strings and the original strings.
    If `filter` is specified, a processed string needs to pass the filter to return.

    Args:
        strs: the input strings.
        str_proc: the string processing function.
        filter: a processed string is returned if it passes this filter function
                (i.e. the function returns True).
        keep_the_identical_in_map: True to keep all processed string to
                original string mapping even if they are identical.
        allow_duplicates_in_map: True to allow one-to-many processed string
                to original string mapping;
            in this case the it is a mapping between the processed string
                and a list of original strings.
        **kwargs: named arguments for `str_proc`.

    Returns: the list of processed strings, and a processed string to original string mapping
            (can be one-one mapping or one-to-many mapping dependent on `allow_duplicates_in_map`)

    Examples:
        >>> strs = ['Hello', 'World', 'HELLO']
        >>> processed, mapping = get_processed_strings_and_map(strs, str.lower)
        >>> processed
        ['hello', 'world', 'hello']
        >>> mapping
        {'hello': 'HELLO', 'world': 'World'}

        >>> processed, mapping = get_processed_strings_and_map(
        ...     strs, str.lower, keep_the_identical_in_map=True
        ... )
        >>> 'hello' in mapping
        True

        >>> processed, mapping = get_processed_strings_and_map(
        ...     strs, str.lower, allow_duplicates_in_map=True
        ... )
        >>> mapping['hello']
        ['Hello', 'HELLO']
    """

    processed_strs = []
    process_str_to_original_str_map = defaultdict(list) if allow_duplicates_in_map else {}
    for s in strs:
        s_processed = str_proc(s, **kwargs)
        if filter is None or filter(s):
            processed_strs.append(s_processed)
            if keep_the_identical_in_map or s_processed != s:
                if allow_duplicates_in_map:
                    process_str_to_original_str_map[s_processed].append(s)
                else:
                    process_str_to_original_str_map[s_processed] = s
    return processed_strs, process_str_to_original_str_map
