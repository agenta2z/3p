import re
from functools import partial
from typing import Union

import string
from python_utils.string_utils.regex import iter_matches

REGEX_ACRONYM_WITH_PERIODS = re.compile(r'(((\w\.)+)($|\s))+')
REGEX_MATCH_ALL_PUNCTUATION_WITH_EXCEPTION = r'[^\w\s{}]'
REGEX_MATCH_ALL_PUNCTUATION_EXCEPT_FOR_HYPHEN = r'[^\w\s\-]'
REGEX_MATCH_ALL_PUNCTUATION_EXCEPT_FOR_HYPHEN_AND_UNDERSCORE = r'[^\w\s\-\_]'

def remove_acronym_periods_and_spaces(
        text: str,
        acronym_pattern: Union[str, re.Match] = REGEX_ACRONYM_WITH_PERIODS,
        upper_case_acronyms: bool = False
) -> str:
    """
    Removes periods and spaces in acronyms. For example,
        "play c. n. n. news --> play cnn news"
        "play w. a.m. c. --> play wamc"

    Args:
        text: The input text string to process with possible acronyms in it.
        acronym_pattern: A regex pattern to recognize acronyms with periods and spaces.
            Defaults to the pre-defined `REGEX_ACRONYM_WITH_PERIODS` pattern.
        upper_case_acronyms: Whether to make acronyms upper case.

    Returns:
        str: A copy of the input string with periods and spaces in the acronyms removed.

    Examples:
        >>> remove_acronym_periods_and_spaces(
        ...    'play c. n. n. news'
        ... )
        'play cnn news'
        >>> remove_acronym_periods_and_spaces(
        ...    'play w. a.m. c.'
        ... )
        'play wamc'
        >>> remove_acronym_periods_and_spaces(
        ...    'play c. n. n. news',
        ...    upper_case_acronyms=True
        ... )
        'play CNN news'
        >>> remove_acronym_periods_and_spaces('The U.N. has 193 member states')
        'The UN has 193 member states'
        >>> remove_acronym_periods_and_spaces('play music')
        'play music'
    """
    if '.' not in text:
        return text
    out = []
    start = 0
    for match in iter_matches(pattern=acronym_pattern, string=text, return_match_obj=True):
        match_start, match_end = match.start(), match.end()
        if start != match_start:
            out.append(text[start:match_start])
        acronym: str = match.group(0)
        _acronym = acronym.replace('.', '').replace(' ', '')
        if upper_case_acronyms:
            _acronym = _acronym.upper()
        if acronym[-1] == ' ':
            _acronym += ' '

        out.append(_acronym)
        start = match_end

    if start == 0:
        return text
    else:
        if start < len(text):
            out.append(text[start:])

        return ''.join(out)


def remove_acronym_periods_and_spaces_udf(
        text,
        acronym_pattern=REGEX_ACRONYM_WITH_PERIODS,
        upper_case_acronyms=False
):
    from pyspark.sql.functions import udf
    from pyspark.sql.types import StringType
    return udf(
        partial(
            remove_acronym_periods_and_spaces,
            acronym_pattern=acronym_pattern,
            upper_case_acronyms=upper_case_acronyms
        ),
        returnType=StringType()
    )(text)


def remove_punctuation(text: str, exception=None) -> str:
    text = re.sub(
        pattern=REGEX_MATCH_ALL_PUNCTUATION_WITH_EXCEPTION.format(
            re.escape(exception)
            if exception
            else ''
        ),
        repl='', string=text
    )
    return re.sub(pattern=r'\s+', repl=' ', string=text).strip()


def remove_punctuation_except_for_hyphen(text: str) -> str:
    """
    Removes all punctuation from the input string except for the hyphen (-) character.

    Args:
        text: The input text to remove punctuation from.

    Returns:
        A new string with all punctuation except for hyphens removed.

    Examples:
        >>> remove_punctuation_except_for_hyphen(
        ...     'Hello, world! How are you doing?'
        ... )
        'Hello world How are you doing'

        >>> remove_punctuation_except_for_hyphen(
        ...     'This is a test-string. It has punctuation, comma, full-stop, and hyphen- too.'
        ... )
        'This is a test-string It has punctuation comma full-stop and hyphen- too'

        >>> remove_punctuation_except_for_hyphen(
        ...     'This sentence has only hyp-hens'
        ... )
        'This sentence has only hyp-hens'
    """
    text = re.sub(
        pattern=REGEX_MATCH_ALL_PUNCTUATION_EXCEPT_FOR_HYPHEN,
        repl='',
        string=text
    )
    return re.sub(pattern=r'\s+', repl=' ', string=text).strip()


def remove_punctuation_except_for_hyphen_and_underscore(text: str) -> str:
    text = re.sub(
        pattern=REGEX_MATCH_ALL_PUNCTUATION_EXCEPT_FOR_HYPHEN_AND_UNDERSCORE,
        repl='',
        string=text
    )
    return re.sub(pattern=r'\s+', repl=' ', string=text).strip()


def contains_punctuation(s: str, exclusion=None):
    if not exclusion:
        return any(c in string.punctuation for c in s)
    else:
        return any((c in string.punctuation and c not in exclusion) for c in s)
