from enum import Enum
from typing import Tuple, Optional, Union

from dataclasses import dataclass
import re


class CompareMethod(str, Enum):
    ExactMatch = 'exact_match'
    Contains = 'contains'
    StartsWith = 'starts_with'
    EndsWith = 'ends_with'
    LowerLexicalOrder = '<'
    HigherLexicalOrder = '>'


@dataclass
class CompareOption:
    compare_method: CompareMethod = CompareMethod.ExactMatch
    is_regular_expression: bool = False
    case_sensitive: bool = True
    ignore_null: bool = False
    negation: bool = False
    other_options: Optional[str] = None


def solve_compare_option(
        s: str,
        contains_indicator='*',
        starts_with_indicator='^',
        ends_with_indicator='$',
        lower_lexical_order_indicator='<',
        higher_lexical_order_indicator='>',
        regular_expression_indicator='@',
        negation_indicators='!~',
        case_insensitive_indicator='/',
        ignore_null_indicator='?',
        space_as_option_break=True,
        option_at_start=True,
        option_at_end=False,
        other_option_indicators=None,
        return_none_if_no_option_available: bool = False,
        compile_regex: bool = False
) -> Tuple[Optional[CompareOption], Union[str, re.Pattern]]:
    """
    Solves a string comparison directive and optionally compiles regex patterns.

    This function parses a string directive to extract comparison options and the pattern.
    When `compile_regex=True` and the pattern is a regular expression, it returns a
    compiled `re.Pattern` object instead of a string for better performance.

    Args:
        s: The string directive to parse (e.g., '@[0-9]+', '*hello', '^start')
        contains_indicator: Character indicating contains matching (default: '*')
        starts_with_indicator: Character indicating starts with matching (default: '^')
        ends_with_indicator: Character indicating ends with matching (default: '$')
        lower_lexical_order_indicator: Character for lexical < comparison (default: '<')
        higher_lexical_order_indicator: Character for lexical > comparison (default: '>')
        regular_expression_indicator: Character indicating regex pattern (default: '@')
        negation_indicators: Characters indicating negation (default: '!~')
        case_insensitive_indicator: Character for case insensitive matching (default: '/')
        ignore_null_indicator: Character for null handling (default: '?')
        space_as_option_break: Whether space breaks option parsing (default: True)
        option_at_start: Parse options from start of string (default: True)
        option_at_end: Parse options from end of string (default: False)
        other_option_indicators: Additional option indicators (default: None)
        return_none_if_no_option_available: Return None if no options found (default: False)
        compile_regex: Pre-compile regex patterns for performance (default: False)

    Returns:
        A tuple of (CompareOption, pattern) where pattern is either a string or
        re.Pattern object if compile_regex=True and the pattern is a regex.

    Examples:
        # Basic string matching without compilation
        >>> option, pattern = solve_compare_option('hello')
        >>> isinstance(pattern, str)
        True
        >>> option.compare_method.value
        'exact_match'

        # Contains matching
        >>> option, pattern = solve_compare_option('*world')
        >>> isinstance(pattern, str) and pattern == 'world'
        True
        >>> option.compare_method.value
        'contains'

        # Starts with matching
        >>> option, pattern = solve_compare_option('^prefix')
        >>> isinstance(pattern, str) and pattern == 'prefix'
        True
        >>> option.compare_method.value
        'starts_with'

        # Ends with matching
        >>> option, pattern = solve_compare_option('$suffix')
        >>> isinstance(pattern, str) and pattern == 'suffix'
        True
        >>> option.compare_method.value
        'ends_with'

        # Regex exact match without compilation
        >>> option, pattern = solve_compare_option('@[0-9]+')
        >>> isinstance(pattern, str) and pattern == '[0-9]+'
        True
        >>> option.is_regular_expression
        True

        # Regex exact match WITH compilation
        >>> option, pattern = solve_compare_option('@[0-9]+', compile_regex=True)
        >>> isinstance(pattern, re.Pattern)
        True
        >>> option.is_regular_expression
        True
        >>> pattern.pattern
        '[0-9]+'

        # Regex starts with without compilation
        >>> option, pattern = solve_compare_option('@^[a-z]+')
        >>> isinstance(pattern, str) and pattern == '[a-z]+'
        True
        >>> option.compare_method.value
        'starts_with'
        >>> option.is_regular_expression
        True

        # Regex starts with WITH compilation (adds ^ anchor)
        >>> option, pattern = solve_compare_option('@^[a-z]+', compile_regex=True)
        >>> isinstance(pattern, re.Pattern)
        True
        >>> pattern.pattern
        '^[a-z]+'

        # Regex ends with without compilation
        >>> option, pattern = solve_compare_option('@$[0-9]+')
        >>> isinstance(pattern, str) and pattern == '[0-9]+'
        True
        >>> option.compare_method.value
        'ends_with'

        # Regex ends with WITH compilation (adds $ anchor)
        >>> option, pattern = solve_compare_option('@$[0-9]+', compile_regex=True)
        >>> isinstance(pattern, re.Pattern)
        True
        >>> pattern.pattern
        '[0-9]+$'

        # Negation with regex exact match
        >>> option, pattern = solve_compare_option('!@[0-9]+', compile_regex=True)
        >>> isinstance(pattern, re.Pattern)
        True
        >>> option.negation
        True
        >>> option.is_regular_expression
        True

        # Negation with regex starts with
        >>> option, pattern = solve_compare_option('!@^[a-z]+', compile_regex=True)
        >>> isinstance(pattern, re.Pattern)
        True
        >>> option.negation
        True
        >>> option.compare_method.value
        'starts_with'
        >>> pattern.pattern
        '^[a-z]+'

        # Negation with regex ends with
        >>> option, pattern = solve_compare_option('!@$[0-9]+', compile_regex=True)
        >>> isinstance(pattern, re.Pattern)
        True
        >>> option.negation
        True
        >>> pattern.pattern
        '[0-9]+$'

        # Case insensitive regex
        >>> option, pattern = solve_compare_option('/@[a-z]+', compile_regex=True)
        >>> isinstance(pattern, re.Pattern)
        True
        >>> option.case_sensitive
        False
        >>> pattern.flags & re.IGNORECASE != 0
        True

        # Case insensitive with negation
        >>> option, pattern = solve_compare_option('/!@[a-z]+', compile_regex=True)
        >>> isinstance(pattern, re.Pattern)
        True
        >>> option.case_sensitive
        False
        >>> option.negation
        True

        # Case insensitive regex starts with
        >>> option, pattern = solve_compare_option('/@^[a-z]+', compile_regex=True)
        >>> isinstance(pattern, re.Pattern)
        True
        >>> option.case_sensitive
        False
        >>> option.compare_method.value
        'starts_with'
        >>> pattern.pattern
        '^[a-z]+'

        # Multiple operators: negation + case insensitive + regex starts with
        >>> option, pattern = solve_compare_option('!/^@[a-z]+', compile_regex=True)
        >>> isinstance(pattern, re.Pattern)
        True
        >>> option.negation and not option.case_sensitive
        True
        >>> option.compare_method.value
        'starts_with'

        # Non-regex patterns remain strings even with compile_regex=True
        >>> option, pattern = solve_compare_option('*hello', compile_regex=True)
        >>> isinstance(pattern, str) and pattern == 'hello'
        True
        >>> option.is_regular_expression
        False

        # Contains with regex (*@) - without compilation
        >>> option, pattern = solve_compare_option('*@ view|body|presentation', compile_regex=False)
        >>> isinstance(pattern, str)
        True
        >>> pattern
        'view|body|presentation'
        >>> option.compare_method.value
        'contains'
        >>> option.is_regular_expression
        True

        # Contains with regex (*@) - with compilation
        >>> option, pattern = solve_compare_option('*@ view|body|presentation', compile_regex=True)
        >>> isinstance(pattern, re.Pattern)
        True
        >>> pattern.pattern
        'view|body|presentation'
        >>> option.compare_method.value
        'contains'

        # Space as separator
        >>> option, pattern = solve_compare_option('@ [0-9]+', compile_regex=True)
        >>> isinstance(pattern, re.Pattern)
        True
        >>> pattern.pattern
        '[0-9]+'

        # Invalid regex gracefully falls back to string
        >>> option, pattern = solve_compare_option('@[invalid(regex', compile_regex=True)
        >>> isinstance(pattern, str)
        True
        >>> option.is_regular_expression
        True

        # Empty pattern edge cases
        >>> option, pattern = solve_compare_option('*')
        >>> pattern
        ''
        >>> option.compare_method.value
        'contains'
        >>> option, pattern = solve_compare_option('^')
        >>> pattern
        ''
        >>> option.compare_method.value
        'starts_with'
        >>> option, pattern = solve_compare_option('$')
        >>> pattern
        ''
        >>> option.compare_method.value
        'ends_with'
        >>> option, pattern = solve_compare_option('!*')
        >>> pattern
        ''
        >>> option.compare_method.value
        'contains'
        >>> option.negation
        True

    See Also:
        :func:`string_compare`: Use the returned option and pattern for comparison
        :func:`string_check`: Convenience function that combines both operations
    """
    negation = ignore_null = is_regular_expression = False
    case_sensitive = True
    compare_method = CompareMethod.ExactMatch
    other_options = []

    def _get_options():
        nonlocal i, compare_method, is_regular_expression, case_sensitive, ignore_null, negation
        last_processed_i = -1
        for i in idxes:
            c = s[i]
            if negation_indicators and c in negation_indicators:
                negation = (not negation)
                last_processed_i = i
            elif contains_indicator and c == contains_indicator:
                compare_method = CompareMethod.Contains
                last_processed_i = i
            elif starts_with_indicator and c == starts_with_indicator:
                compare_method = CompareMethod.StartsWith
                last_processed_i = i
            elif ends_with_indicator and c == ends_with_indicator:
                compare_method = CompareMethod.EndsWith
                last_processed_i = i
            elif lower_lexical_order_indicator and c == lower_lexical_order_indicator:
                compare_method = CompareMethod.LowerLexicalOrder
                last_processed_i = i
            elif higher_lexical_order_indicator and c == higher_lexical_order_indicator:
                compare_method = CompareMethod.HigherLexicalOrder
                last_processed_i = i
            elif regular_expression_indicator and c == regular_expression_indicator:
                is_regular_expression = True
                last_processed_i = i
            elif case_insensitive_indicator and c == case_insensitive_indicator:
                case_sensitive = False
                last_processed_i = i
            elif ignore_null_indicator and c == ignore_null_indicator:
                ignore_null = True
                last_processed_i = i
            elif other_option_indicators and c in other_option_indicators:
                other_options.append(c)
                last_processed_i = i
            else:
                break
        return last_processed_i

    has_option_at_end = has_option_at_start = False
    if option_at_end:
        i = len(s) - 1
        idxes = reversed(range(len(s)))
        last_i = _get_options()
        if last_i != -1:
            s = s[:last_i]  # Slice up to (not including) the last processed option
        has_option_at_end = (last_i != -1)
        if space_as_option_break:
            s = s.rstrip()
    if option_at_start:
        i = 0
        idxes = range(len(s))
        last_i = _get_options()
        s = s[(last_i + 1):]  # Slice from position after last processed option
        has_option_at_start = (last_i != -1)
        if space_as_option_break:
            s = s.lstrip()

    if not (has_option_at_start or has_option_at_end) and return_none_if_no_option_available:
        return None, s
    else:
        compare_option = CompareOption(
            compare_method=compare_method,
            is_regular_expression=is_regular_expression,
            case_sensitive=case_sensitive,
            ignore_null=ignore_null,
            negation=negation,
            other_options=(''.join(other_options) if other_options else None)
        )

        # Compile regex pattern if requested and return it instead of string
        pattern_result = s
        if compile_regex and is_regular_expression and s:
            try:
                # Build the regex pattern with appropriate flags and anchors
                pattern = s
                if compare_method == CompareMethod.StartsWith:
                    pattern = f'^{pattern}'
                elif compare_method == CompareMethod.EndsWith:
                    pattern = f'{pattern}$'
                # For ExactMatch, we don't add anchors here because
                # string_compare will use fullmatch which handles it

                flags = 0 if case_sensitive else re.IGNORECASE
                pattern_result = re.compile(pattern, flags)
            except re.error:
                # If compilation fails, return the string pattern
                # string_compare will handle runtime compilation
                pattern_result = s

        return compare_option, pattern_result


def string_compare(src: str, trg: Union[str, re.Pattern], option: CompareOption) -> bool:
    """
    Compare a source string against a target pattern using specified comparison options.

    This function supports both string patterns and pre-compiled regex patterns for
    efficient matching operations.

    Special handling for empty patterns:
    - Contains method with empty pattern: Always returns True (every string contains empty string)
    - StartsWith method with empty pattern: Always returns True (every string starts with empty string)
    - EndsWith method with empty pattern: Always returns True (every string ends with empty string)
    - ExactMatch method with empty pattern: Returns True only if src is also empty

    Args:
        src: The source string to check
        trg: The target pattern (either a string or compiled re.Pattern)
        option: CompareOption specifying how to perform the comparison

    Returns:
        True if the comparison succeeds (respecting negation), False otherwise

    Examples:
        # Basic string exact match
        >>> from rich_python_utils.string_utils.comparison import CompareOption, CompareMethod
        >>> opt = CompareOption(compare_method=CompareMethod.ExactMatch)
        >>> string_compare('hello', 'hello', opt)
        True
        >>> string_compare('hello', 'world', opt)
        False

        # Contains matching
        >>> opt = CompareOption(compare_method=CompareMethod.Contains)
        >>> string_compare('hello world', 'world', opt)
        True
        >>> string_compare('hello world', 'xyz', opt)
        False

        # Starts with matching
        >>> opt = CompareOption(compare_method=CompareMethod.StartsWith)
        >>> string_compare('hello world', 'hello', opt)
        True
        >>> string_compare('hello world', 'world', opt)
        False

        # Ends with matching
        >>> opt = CompareOption(compare_method=CompareMethod.EndsWith)
        >>> string_compare('hello world', 'world', opt)
        True
        >>> string_compare('hello world', 'hello', opt)
        False

        # Negation
        >>> opt = CompareOption(compare_method=CompareMethod.ExactMatch, negation=True)
        >>> string_compare('hello', 'world', opt)
        True
        >>> string_compare('hello', 'hello', opt)
        False

        # Case insensitive
        >>> opt = CompareOption(compare_method=CompareMethod.ExactMatch, case_sensitive=False)
        >>> string_compare('HELLO', 'hello', opt)
        True
        >>> string_compare('HeLLo', 'hello', opt)
        True

        # Regex with string pattern (runtime compilation)
        >>> opt = CompareOption(is_regular_expression=True, compare_method=CompareMethod.ExactMatch)
        >>> string_compare('12345', r'[0-9]+', opt)
        True
        >>> string_compare('abc', r'[0-9]+', opt)
        False

        # Regex with compiled pattern (no runtime compilation)
        >>> import re
        >>> compiled = re.compile(r'[0-9]+')
        >>> opt = CompareOption(is_regular_expression=True, compare_method=CompareMethod.ExactMatch)
        >>> string_compare('12345', compiled, opt)
        True
        >>> string_compare('abc', compiled, opt)
        False

        # Regex starts with using compiled pattern
        >>> compiled = re.compile(r'^[a-z]+')
        >>> opt = CompareOption(is_regular_expression=True, compare_method=CompareMethod.StartsWith)
        >>> string_compare('abc123', compiled, opt)
        True
        >>> string_compare('123abc', compiled, opt)
        False

        # Regex ends with using compiled pattern
        >>> compiled = re.compile(r'[0-9]+$')
        >>> opt = CompareOption(is_regular_expression=True, compare_method=CompareMethod.EndsWith)
        >>> string_compare('abc123', compiled, opt)
        True
        >>> string_compare('123abc', compiled, opt)
        False

        # Case insensitive regex with compiled pattern
        >>> compiled = re.compile(r'[a-z]+', re.IGNORECASE)
        >>> opt = CompareOption(is_regular_expression=True, case_sensitive=False)
        >>> string_compare('ABC', compiled, opt)
        True
        >>> string_compare('123', compiled, opt)
        False

        # Negation with regex
        >>> compiled = re.compile(r'[0-9]+')
        >>> opt = CompareOption(is_regular_expression=True, negation=True)
        >>> string_compare('abc', compiled, opt)
        True
        >>> string_compare('123', compiled, opt)
        False

        # Integration with solve_compare_option - exact match
        >>> opt, pat = solve_compare_option('@[0-9]+', compile_regex=True)
        >>> string_compare('12345', pat, opt)
        True
        >>> string_compare('abc', pat, opt)
        False

        # Integration with solve_compare_option - starts with
        >>> opt, pat = solve_compare_option('@^[a-z]+', compile_regex=True)
        >>> string_compare('abc123', pat, opt)
        True
        >>> string_compare('123abc', pat, opt)
        False

        # Integration with solve_compare_option - ends with
        >>> opt, pat = solve_compare_option('@$[0-9]+', compile_regex=True)
        >>> string_compare('abc123', pat, opt)
        True
        >>> string_compare('123abc', pat, opt)
        False

        # Integration with solve_compare_option - negation
        >>> opt, pat = solve_compare_option('!@[0-9]+', compile_regex=True)
        >>> string_compare('abc', pat, opt)
        True
        >>> string_compare('123', pat, opt)
        False

        # Integration with solve_compare_option - case insensitive
        >>> opt, pat = solve_compare_option('/@[a-z]+', compile_regex=True)
        >>> string_compare('ABC', pat, opt)
        True
        >>> string_compare('123', pat, opt)
        False

        # Integration with solve_compare_option - complex combination
        >>> opt, pat = solve_compare_option('!/^@[a-z]+', compile_regex=True)
        >>> string_compare('123', pat, opt)
        True
        >>> string_compare('abc', pat, opt)
        False

        # Empty pattern edge cases
        >>> opt = CompareOption(compare_method=CompareMethod.Contains)
        >>> string_compare('', '', opt)  # empty contains empty
        True
        >>> string_compare('hello', '', opt)  # any string contains empty
        True
        >>> opt = CompareOption(compare_method=CompareMethod.StartsWith)
        >>> string_compare('', '', opt)  # empty starts with empty
        True
        >>> string_compare('hello', '', opt)  # any string starts with empty
        True
        >>> opt = CompareOption(compare_method=CompareMethod.EndsWith)
        >>> string_compare('', '', opt)  # empty ends with empty
        True
        >>> string_compare('hello', '', opt)  # any string ends with empty
        True
        >>> opt = CompareOption(compare_method=CompareMethod.ExactMatch)
        >>> string_compare('', '', opt)  # empty exactly matches empty
        True
        >>> string_compare('hello', '', opt)  # non-empty doesn't exactly match empty
        False
        >>> opt = CompareOption(compare_method=CompareMethod.Contains, negation=True)
        >>> string_compare('hello', '', opt)  # negation of "contains empty" is False
        False
        >>> string_compare('', '', opt)  # negation of "contains empty" is False even for empty string
        False

        # Null handling
        >>> opt = CompareOption(ignore_null=True)
        >>> string_compare(None, 'test', opt)
        True
        >>> opt = CompareOption(ignore_null=False)
        >>> string_compare(None, 'test', opt)
        False

    See Also:
        :func:`solve_compare_option`: Parse string directives into options
        :func:`string_check`: Convenience function combining both operations
    """
    if src is None:
        return option.ignore_null

    # Special handling for empty string patterns (not regex):
    # - Contains/StartsWith/EndsWith with empty pattern should return True
    #   (every string contains/starts-with/ends-with an empty string)
    # - ExactMatch uses normal comparison (handled below)
    if isinstance(trg, str) and not option.is_regular_expression and trg == '':
        if option.compare_method in (CompareMethod.Contains, CompareMethod.StartsWith, CompareMethod.EndsWith):
            result = True
            return result != option.negation

    # Handle compiled regex patterns
    if isinstance(trg, re.Pattern):
        if option.compare_method == CompareMethod.ExactMatch:
            result = trg.fullmatch(src) is not None
        else:
            # For StartsWith/EndsWith/Contains, the pattern should already have
            # the appropriate anchors (added during compilation)
            result = trg.search(src) is not None
    elif option.is_regular_expression:
        # Runtime regex compilation (original behavior for string patterns)
        if option.compare_method == CompareMethod.ExactMatch:
            result = (
                    re.fullmatch(trg, src, (0 if option.case_sensitive else re.IGNORECASE))
                    is not None
            )
        else:
            if option.compare_method == CompareMethod.StartsWith:
                trg = f'^{trg}'
            elif option.compare_method == CompareMethod.EndsWith:
                trg = f'{trg}$'
            elif option.compare_method == CompareMethod.Contains:
                # No modification needed - search() naturally does contains matching
                pass
            else:
                raise ValueError(
                    f"regular expression does not support method {option.compare_method}"
                )
            result = (
                # ! must use `search` rather than `match`,
                # because `re.match` only matches from the beginning of the string
                    re.search(trg, src, (0 if option.case_sensitive else re.IGNORECASE))
                    is not None
            )
    else:
        if not option.case_sensitive:
            src = src.lower()
            trg = trg.lower()
        if option.compare_method == CompareMethod.ExactMatch:
            result = (src == trg)
        elif option.compare_method == CompareMethod.Contains:
            result = (trg in src)
        elif option.compare_method == CompareMethod.StartsWith:
            result = (src.startswith(trg))
        elif option.compare_method == CompareMethod.EndsWith:
            result = (src.endswith(trg))
        elif option.compare_method == CompareMethod.LowerLexicalOrder:
            result = (src < trg)
        elif option.compare_method == CompareMethod.HigherLexicalOrder:
            result = (src > trg)
        else:
            result = (src == trg)

    return result != option.negation


def string_check(s: str, pattern: str, **kwargs) -> bool:
    """
    Quickly check if the string `s` matches the given `pattern`.

    The `pattern` uses a string directive.
    A string comparison directive is a fast way to specify a condition a string must satisfy.
    The currently supported directives include
    1) '* substr', the string must contain the specified substring;
    2) '^ substr', the string must start with the specified substring;
    3) '$ substr', the string must end with the specified substring;
    4) '@ regex', the string must match the specified regular expression; can combine with '^', '$', '*'
        for example, '@^' means the start of the string must match the regular expression,
        '*@' means the string contains a match for the regular expression;
    5) '! directive', negation of another directive, e.g. '!*substr' means the string must not
        contain the specified substring, or '!@$ regex' means the end of the string must not match
        the specified pattern.

    A space between the directive characters and the string is recommended,
    but optional in most cases. For example, we can specify '* substr' or '*substr'.

    See Also :func:`solve_compare_option` and :func:`string_compare`.

    Examples:
        >>> assert string_check('1456', '1456')  # exact match
        >>> assert string_check('123456', '*12')  # contains substring '12'
        >>> assert string_check('123456', '* 12')  # contains substring '12', can add a space
        >>> assert string_check('123456', '^ 12')  # starts with substring '12'
        >>> assert string_check('123456', '$ 56')  # ends with substring '56'
        >>> assert string_check('123456', '!* ab')  # not contains with substring 'ab'
        >>> assert string_check('123456', '@ [0-9]+')  # matches regular expression '[0-9]+'
        >>> assert string_check('ab123456', '@^ [a-z]+')  # start of string matches regular expression '[a-z]+'
        >>> assert string_check('123456ab', '@$ [a-z]+')  # end of string matches regular expression '[a-z]+'
        >>> assert string_check('123456', '!@$ [a-z]+')  # end of string does not match regular expression '[a-z]+'
        >>> assert string_check('p-workspace__primary_view_body', '*@ view|body|presentation', compile_regex=False)  # contains with regex alternation
        >>> assert string_check('p-workspace__primary_view_body', '*@ view|body|presentation', compile_regex=True)  # contains with regex alternation
        >>> assert not string_check('unrelated-class-name', '*@ view|body|presentation')  # does not contain any of the keywords
        >>> assert string_check('', '*')  # single '*' matches any string, including empty strings
        >>> assert string_check('hello', '*')  # single '*' matches any string
        >>> assert not string_check('hello', '!*')  # negation of '*' matches nothing
        >>> assert not string_check('', '!*')  # negation of '*' matches nothing
        >>> assert string_check('', '^')  # empty pattern with starts-with matches any string
        >>> assert string_check('hello', '^')  # any string starts with empty string
        >>> assert string_check('', '$')  # empty pattern with ends-with matches any string
        >>> assert string_check('hello', '$')  # any string ends with empty string
        >>> assert not string_check('hello', '!^')  # negation of "starts with empty" matches nothing
        >>> assert not string_check('hello', '!$')  # negation of "ends with empty" matches nothing
        >>> assert string_check('', '')  # empty string exactly matches empty string
        >>> assert not string_check('hello', '')  # non-empty string doesn't exactly match empty string

    Args:
        s: the string to check.
        pattern: a pattern in the format of a string directive.
        kwargs: the options for the string directive, passed to :func:`solve_compare_option`.

    Returns: a Boolean value indicating if the string `s` satisfies the specified `pattern`.

    """
    # Shortcut: A single '*' wildcard matches any string (including empty strings)
    # This is handled generically in string_compare, but we can short-circuit here for performance
    if pattern.strip() == '*':
        return True

    option, pattern = solve_compare_option(pattern, **kwargs)
    return string_compare(src=s, trg=pattern, option=option)

