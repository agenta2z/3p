import warnings
from enum import Enum
from functools import partial, reduce
from typing import Union, Mapping, Iterable, List, Optional, Callable

from attr import attrs, attrib
from python_utils.common_utils.function_helper import get_relevant_named_args
from python_utils.common_utils.typing_helper import solve_nested_singleton_tuple_list, is_str
from python_utils.nlp_utils.common import Languages
from python_utils.string_utils.prefix_suffix import remove_common_prefix_suffix, remove_prefix_suffix
from python_utils.nlp_utils.punctuations import remove_acronym_periods_and_spaces, remove_punctuation_except_for_hyphen
from python_utils.string_utils.tokenization import tokenize
import re

try:
    from unidecode import unidecode
except Exception as err:
    warnings.warn(f"unable to load module 'unidecode' due to error '{err}'")

PREDEFINED_FUZZINESS_MAP = {
    Languages.English: {
        'the': 'de',
        'ich': 'ik',
        'key': 'ki',
        'ore': 'or',
        'sch': 'sc',
        'syd': 'si',
        'buy': 'bai',
        'guy': 'gai',
        'kro': 'kra',
        'cro': 'kra',
        'lob': 'lab',
        'cha': 'tra',
        'che': 'tre',
        'ah': 'a',
        'ar': 'a',
        'gh': 'g',
        'ee': 'i',
        'kw': 'w',
        'nn': 'n',
        'ng': 'n',
        'kn': 'n',
        'or': 'o',
        'sp': 'p',
        'ze': 's',
        'ce': 's',
        'sh': 's',
        'oo': 'u',
        'ho': 'fo',
        'en': 'in',
        'em': 'in',
        'ev': 'iv',
        'ga': 'ka',
        'ro': 'no',
        'ci': 'si',
        'e': 'a',
        'p': 'b',
        't': 'd',
        'v': 'f',
        'y': 'i',
        'c': 'k',
        'g': 'k',
        'q': 'k',
        'm': 'n',
        'l': 'n',
        'x': 's',
        'z': 's'
    }
}


def fuzz(s: str, fuzziness_map=Languages.English):
    if isinstance(fuzziness_map, str):
        fuzziness_map = PREDEFINED_FUZZINESS_MAP[fuzziness_map]
    for c1, c2 in fuzziness_map.items():
        s = s.replace(c1, c2)
    return s


def remove_common_tokens(*strings, tokenizer=None):
    strings = solve_nested_singleton_tuple_list(strings, atom_types=str)
    tokens = [
        tokenize(_s, tokenizer=tokenizer)
        for _s in strings
    ]
    common_tokens = reduce(
        lambda x, y: x & y,
        (set(_tokens) for _tokens in tokens)
    )

    return [
        ' '.join(_s for _s in _tokens if _s not in common_tokens)
        for _tokens in tokens
    ]


def remove_common_tokens_except_for_sub_tokens(
        str1: Union[str, Iterable[str]],
        str2: Union[str, Iterable[str]],
        tokenizer: Optional[Callable] = None
):
    """
    Removes tokens that appear in both input strings, except for those tokens that are sub-tokens
    of some other tokens, and returns two strings with common tokens removed.
    Tokens are obtained by calling the :func:`tokenize` function given the tokenizer.

    Args:
        str1: The first string or iterable of tokens.
        str2: The second string or iterable of tokens.
        tokenizer: An optional argument specifying the tokenizer to use to
            tokenize the input strings. See also :func:`tokenize` function.

    Returns:
        A tuple of two strings with overlapping tokens removed.

    Examples:
        >>> remove_common_tokens_except_for_sub_tokens('seven eighty eight', 'seventy eight')
        ('seven eighty', 'seventy eight')
        >>> remove_common_tokens_except_for_sub_tokens('seven eighty eight', 'seventy eighty eight')
        ('seven eight', 'seventy eight')
        >>> remove_common_tokens_except_for_sub_tokens('apple pie', 'apple crisp')
        ('pie', 'crisp')
        >>> remove_common_tokens_except_for_sub_tokens('pie', 'apple crisp and sweet')
        ('pie', 'apple crisp and sweet')
    """
    if not str1 or not str2:
        return str1, str2
    str1_tokens = tuple(tokenize(str1, tokenizer=tokenizer) if isinstance(str1, str) else str1)
    str2_tokens = tuple(tokenize(str2, tokenizer=tokenizer) if isinstance(str2, str) else str2)
    str1_tokens_set = set(str1_tokens)
    str2_tokens_set = set(str2_tokens)

    def _clean_tokens(tokens, output_tokens, the_other_token_set):
        for x in tokens:
            if (
                    x not in output_tokens and
                    (
                            x not in the_other_token_set or
                            any((x in y and x != y) for y in the_other_token_set)
                    )
            ):
                output_tokens.append(x)

    str1_tokens_cleaned = []
    _clean_tokens(
        tokens=str1_tokens,
        output_tokens=str1_tokens_cleaned,
        the_other_token_set=str2_tokens_set
    )
    str2_tokens_cleaned = []
    _clean_tokens(
        tokens=str2_tokens,
        output_tokens=str2_tokens_cleaned,
        the_other_token_set=str1_tokens_set
    )

    return (
        ' '.join(str1_tokens_cleaned),
        ' '.join(str2_tokens_cleaned),
    )


class StringSanitizationOptions(int, Enum):
    REMOVE_ACRONYMS_PERIODS_AND_SPACES = 0
    REMOVE_CASES = 1
    REMOVE_COMMON_PREFIX = 2
    REMOVE_COMMON_SUFFIX = 3
    REMOVE_PUNCTUATIONS_EXCEPT_FOR_HYPHEN = 4
    REMOVE_SPACES = 5
    REPLACEMENT = 6
    MAKE_FUZZY = 7
    SORT_TOKENS = 8
    SORT_TOKENS_REVERSED = 9
    SORT_TOKENS_BOTH_ORDERS = 10
    REMOVE_COMMON_TOKENS = 11
    REMOVE_PREFIX = 12
    REMOVE_SUFFIX = 13
    UNIDECODE = 14


@attrs(slots=True)
class StringSanitizationConfig:
    actions = attrib(type=Iterable[StringSanitizationOptions], default=None)
    prefixes_to_sanitize = attrib(type=List[str], default=None)
    suffixes_to_sanitize = attrib(type=List[str], default=None)
    common_prefixes_to_sanitize = attrib(type=List[str], default=None)
    common_suffixes_to_sanitize = attrib(type=List[str], default=None)
    replacements = attrib(type=List[Mapping[str, str]], default=None)


def _lower(x: str):
    return x.lower()


def _remove_spaces(x: str):
    return ''.join(x.split())


def _replace_method(x, replacement: Mapping):
    for k, v in replacement.items():
        x = re.sub(k, v, x)
    return x


def _sort_tokens(x: str, tokenizer=None, reverse=False):
    return ' '.join(sorted(tokenize(x, tokenizer=tokenizer), reverse=reverse))


def string_sanitize(
        *strings: str,
        config: Union[Iterable[StringSanitizationOptions], StringSanitizationConfig],
        tokenizer=None,
        language: Languages = Languages.English,
        # region sanitization methods
        remove_acronym_periods_and_spaces_method=remove_acronym_periods_and_spaces,
        remove_case_method=_lower,
        remove_prefix_suffix_method=remove_prefix_suffix,
        remove_common_prefix_suffix_method=remove_common_prefix_suffix,
        remove_punctuation_except_for_hyphen_method=remove_punctuation_except_for_hyphen,
        remove_spaces_method=_remove_spaces,
        replace_method=_replace_method,
        sort_tokens_method=_sort_tokens,
        make_fuzzy_method=fuzz,
        remove_common_tokens_method=remove_common_tokens,
        # endregion
        unpack_single_result=True,
        return_intermediate_results_before_actions=None,
        **kwargs
):
    """

    Sanitizes input strings according to a set of sanitization options.

    Args:
        *strings: A list of input strings to sanitize.
        config: An iterable of StringSanitizationOptions or a StringSanitizationConfig object
            specifying the sanitization options.
        tokenizer: An argument used by the :func:`tokenize` to split strings into tokens.
        language: A Languages enum indicating the language of the texts of the input strings.
        remove_acronym_periods_and_spaces_method: The method to use for removing spaces and periods
            for acronyms.
        remove_case_method: The method to use for removing character case.
        remove_prefix_suffix_method: The method to use for removing specified prefixes and suffixes.
        remove_common_prefix_suffix_method: The method to use for removing common prefixes and suffixes.
        remove_punctuation_except_for_hyphen_method: The method to use for removing punctuations
            except for hyphens.
        remove_spaces_method: The method to use for removing spaces.
        replace_method: The method to use for replacing substrings.
        sort_tokens_method: The method to use for sorting tokens.
        make_fuzzy_method: The method to use for creating fuzzy string representations.
        remove_common_tokens_method: The method to use for removing common tokens.
        unpack_single_result: A boolean indicating whether to flatten the result list if it contains
            a single result.
        return_intermediate_results_before_actions: An iterable of StringSanitizationOptions
            indicating which intermediate results to return before
            performing all sanitization actions.
        **kwargs: Additional named arguments to pass to each sanitization methods.

    Returns:
        A list of sanitized strings.

    Examples:
        >>> strs = (
        ...     'play one a. b. c. two', 'play CNN one two',
        ...     "play joe's two one f.m. two", "play beyoncé"
        ... )

        >>> string_sanitize(
        ...   strs,
        ...   config=[
        ...      StringSanitizationOptions.UNIDECODE,
        ...      StringSanitizationOptions.REMOVE_ACRONYMS_PERIODS_AND_SPACES,
        ...      StringSanitizationOptions.REMOVE_CASES
        ...   ]
        ... )
        ['play one abc two', 'play cnn one two', "play joe's two one fm two", 'play beyonce']

        >>> string_sanitize(
        ...   *strs,
        ...   config=[
        ...      StringSanitizationOptions.UNIDECODE,
        ...      StringSanitizationOptions.REMOVE_ACRONYMS_PERIODS_AND_SPACES,
        ...      StringSanitizationOptions.REMOVE_CASES,
        ...      StringSanitizationOptions.REMOVE_COMMON_PREFIX,
        ...      StringSanitizationOptions.REMOVE_COMMON_SUFFIX,
        ...      StringSanitizationOptions.REMOVE_PUNCTUATIONS_EXCEPT_FOR_HYPHEN,
        ...      StringSanitizationOptions.MAKE_FUZZY,
        ...   ]
        ... )
        ['ona abk dwo', 'kn ona dwo', 'joas dwo ona fn dwo', 'baions']

        >>> string_sanitize(
        ...   *strs,
        ...   config=[
        ...      StringSanitizationOptions.REMOVE_ACRONYMS_PERIODS_AND_SPACES,
        ...      StringSanitizationOptions.REMOVE_CASES,
        ...      StringSanitizationOptions.REMOVE_COMMON_TOKENS,
        ...   ]
        ... )
        ['one abc two', 'cnn one two', "joe's two one fm two", 'beyoncé']
    """
    strings = solve_nested_singleton_tuple_list(strings, atom_types=str)
    if tokenizer is not None:
        strings = (' '.join(tokenize(s, tokenizer)) for s in strings)

    replacement_idx = 0

    if config and not isinstance(config, StringSanitizationConfig):
        config = StringSanitizationConfig(actions=config)
    if 'prefixes' in kwargs:
        if not config.prefixes_to_sanitize:
            config.prefixes_to_sanitize = kwargs['prefixes']
        if not config.common_prefixes_to_sanitize:
            config.common_prefixes_to_sanitize = kwargs['prefixes']
        del kwargs['prefixes']
    if 'suffixes' in kwargs:
        if not config.suffixes_to_sanitize:
            config.suffixes_to_sanitize = kwargs['suffixes']
        if not config.common_suffixes_to_sanitize:
            config.common_suffixes_to_sanitize = kwargs['suffixes']
        del kwargs['suffixes']

    actions = tuple(config.actions) if config.actions else ()

    intermediate_results = {}

    def _add_intermediate_results():
        if (
                return_intermediate_results_before_actions and
                action in return_intermediate_results_before_actions
        ):
            nonlocal strings
            strings = list(strings)
            intermediate_results[action] = strings

    for i, action in enumerate(actions):
        _add_intermediate_results()
        if action == StringSanitizationOptions.REMOVE_ACRONYMS_PERIODS_AND_SPACES:
            strings = map(
                partial(
                    remove_acronym_periods_and_spaces_method,
                    **get_relevant_named_args(remove_acronym_periods_and_spaces_method, **kwargs)
                ),
                strings
            )
        elif action == StringSanitizationOptions.REMOVE_CASES:
            strings = map(remove_case_method, strings)
        elif action == StringSanitizationOptions.REMOVE_PREFIX:
            strings = (
                remove_prefix_suffix_method(
                    s,
                    prefixes=config.prefixes_to_sanitize,
                    suffixes=None,
                ) for s in strings
            )
        elif action == StringSanitizationOptions.REMOVE_SUFFIX:
            strings = (
                remove_prefix_suffix_method(
                    s,
                    prefixes=None,
                    suffixes=config.suffixes_to_sanitize,
                ) for s in strings
            )
        elif action == StringSanitizationOptions.REMOVE_COMMON_PREFIX:
            strings = remove_common_prefix_suffix_method(
                *strings,
                prefixes=config.common_prefixes_to_sanitize,
                suffixes=None,
                remove_prefix=True,
                remove_suffix=False,
                **get_relevant_named_args(remove_common_prefix_suffix_method, **kwargs)
            )
        elif action == StringSanitizationOptions.REMOVE_COMMON_SUFFIX:
            strings = remove_common_prefix_suffix_method(
                *strings,
                prefixes=None,
                suffixes=config.common_suffixes_to_sanitize,
                remove_prefix=False,
                remove_suffix=True,
                **get_relevant_named_args(remove_common_prefix_suffix_method, **kwargs)
            )
        elif action == StringSanitizationOptions.REMOVE_PUNCTUATIONS_EXCEPT_FOR_HYPHEN:
            strings = map(
                partial(
                    remove_punctuation_except_for_hyphen_method,
                    **get_relevant_named_args(remove_punctuation_except_for_hyphen_method, **kwargs)
                ),
                strings
            )
        elif action == StringSanitizationOptions.REMOVE_SPACES:
            strings = map(remove_spaces_method, strings)
        elif action == StringSanitizationOptions.REPLACEMENT:
            strings = map(
                partial(replace_method, replacement=config.replacements[replacement_idx]), strings
            )
            replacement_idx += 1
        elif action == StringSanitizationOptions.MAKE_FUZZY:
            strings = (make_fuzzy_method(s, language) for s in strings)
        elif action == StringSanitizationOptions.REMOVE_COMMON_TOKENS:
            strings = remove_common_tokens_method(strings)
        elif action == StringSanitizationOptions.SORT_TOKENS:
            strings = map(partial(sort_tokens_method, reverse=False), strings)
        elif action == StringSanitizationOptions.SORT_TOKENS_REVERSED:
            strings = map(partial(sort_tokens_method, reverse=True), strings)
        elif action == StringSanitizationOptions.SORT_TOKENS_BOTH_ORDERS:
            if i == len(actions) - 1:
                return (
                    list(
                        map(partial(sort_tokens_method, reverse=False), strings)
                    ),
                    list(
                        map(partial(sort_tokens_method, reverse=True), strings)
                    )
                )
            else:
                raise ValueError(f"'{action}' can only the be last sanitization action")
        elif action == StringSanitizationOptions.UNIDECODE:
            strings = map(unidecode, strings)

    strings = list(strings)
    if unpack_single_result and len(strings) == 1:
        strings = strings[0]
    if return_intermediate_results_before_actions:
        return strings, intermediate_results
    else:
        return strings
