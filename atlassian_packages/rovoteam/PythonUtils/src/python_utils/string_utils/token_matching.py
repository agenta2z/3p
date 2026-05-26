import re
from typing import Union, Iterable, Tuple, Mapping

import python_utils.string_utils.regex as rex
from python_utils.common_utils.iter_helper import iter__
from python_utils.common_utils.set_helper import compare_sets
from python_utils.nlp_utils.common import Languages
from python_utils.string_utils.inflection import (
    get_token_inflection_regex,
    _construct_regex_from_token_tup
)


def solve_conflict_keywords_config(
        conflict_keywords: Union[Iterable[Tuple], Mapping[Languages, Iterable[Tuple]]],
        language: Languages = Languages.English,
        always_include_en: bool = True
) -> Mapping:
    """
    Solve the conflict keywords configuration.

    This function takes a conflict_keywords input and resolves it based on the provided language
    and `always_include_en` options. It returns the conflict keywords for the specified language
    and, if `always_include_en` is True, includes the English conflict keywords as well.

    Args:
        conflict_keywords: A mapping from languages to conflict keywords setup or an iterable of tuples.
        language: The language of the text. Default is English.
        always_include_en: If True, always include the English conflict keywords.

    Returns:
        Mapping: The resolved conflict keywords for the specified language and the English language
                 if always_include_en is True.

    Examples:
        >>> conflict_keywords = {
        ...     Languages.English: [('red', 'blue'), (('car', 'vehicle'), 'plane')],
        ...     Languages.Spanish: [('rojo', 'azul'), (('coche', 'vehículo'), 'avión')]
        ... }
        >>> solve_conflict_keywords_config(conflict_keywords, Languages.Spanish, always_include_en=True)
        [('rojo', 'azul'), (('coche', 'vehículo'), 'avión'), ('red', 'blue'), (('car', 'vehicle'), 'plane')]

        >>> solve_conflict_keywords_config(conflict_keywords, Languages.Spanish, always_include_en=False)
        [('rojo', 'azul'), (('coche', 'vehículo'), 'avión')]

        >>> solve_conflict_keywords_config(conflict_keywords, Languages.English, always_include_en=True)
        [('red', 'blue'), (('car', 'vehicle'), 'plane')]
    """
    if isinstance(conflict_keywords, Mapping):
        if language is None:
            language = Languages.English
        if language not in conflict_keywords:
            raise ValueError(f"language '{language}' is not supported")
        _conflict_keywords = conflict_keywords[language]
        if always_include_en and language != Languages.English:
            _conflict_keywords = [*_conflict_keywords, *conflict_keywords[Languages.English]]
        conflict_keywords = _conflict_keywords
    elif language is not None:
        if (not always_include_en) and language != Languages.English:
            raise ValueError(f"specified language '{language}', "
                             f"then 'conflict_keywords' must be a mapping from languages to "
                             f"conflict keywords setup")
    return conflict_keywords


def has_conflict_keywords_allowing_shared_keywords(
        str1,
        str2,
        conflict_keywords: Iterable[Tuple],
        optional_space=False,
        token_augmentation=False,
        allows_add: bool = True,
        allows_drop: bool = True,
        language: Union[str, Languages] = Languages.English,
        always_include_en=True
):
    """
    Check if two strings have conflicting keywords, allowing for shared keywords.

    Args:
        str1: First string to compare.
        str2: Second string to compare.
        conflict_keywords: Configuration for conflict keywords.
        optional_space: If True, spaces in tokens are optional.
        token_augmentation: If True, match token inflections.
        allows_add: If True, allows adding keywords.
        allows_drop: If True, allows dropping keywords.
        language: The language of the text.
        always_include_en: If True, always include English conflict keywords.

    Returns:
        bool: True if conflict keywords are found.
    """
    if str1 and str2:
        conflict_keywords = solve_conflict_keywords_config(
            conflict_keywords=conflict_keywords,
            language=language,
            always_include_en=always_include_en
        )

        hit_kws1, hit_kws2 = set(), set()
        for conflict_keywords_groups in conflict_keywords:
            for keywords_groups in conflict_keywords_groups:
                kw_group_regex = _construct_regex_from_token_tup(
                    keywords_groups,
                    add_word_boundary=True,
                    optional_space=optional_space,
                    token_augmentation=token_augmentation,
                    language=language
                )
                if re.search(kw_group_regex, str1) is not None:
                    hit_kws1.update(keywords_groups)
                if re.search(kw_group_regex, str2) is not None:
                    hit_kws2.update(keywords_groups)

        if compare_sets(
                hit_kws1,
                hit_kws2,
                allows_add=allows_add,
                allows_drop=allows_drop
        ):
            return True

    elif str1:
        return not allows_drop
    elif str2:
        return not allows_add
    return False


def has_conflict_keywords(
        str1: str,
        str2: str,
        conflict_keywords: Iterable[Tuple],
        optional_space=True,
        token_augmentation=True,
        allows_add: bool = True,
        allows_drop: bool = True,
        language: Union[str, Languages] = Languages.English,
        always_include_en=True
) -> bool:
    """
    Check if two strings have conflicting keywords.

    Args:
        str1: First string to compare.
        str2: Second string to compare.
        conflict_keywords: Configuration for conflict keywords.
        optional_space: If True, spaces in tokens are optional.
        token_augmentation: If True, match token inflections.
        allows_add: If True, allows adding keywords.
        allows_drop: If True, allows dropping keywords.
        language: The language of the text.
        always_include_en: If True, always include English conflict keywords.

    Returns:
        bool: True if conflict keywords are found.
    """
    conflict_keywords = solve_conflict_keywords_config(
        conflict_keywords=conflict_keywords,
        language=language,
        always_include_en=always_include_en
    )
    if str1 and str2:
        for _conflict_tokens_tup in conflict_keywords:
            if not isinstance(_conflict_tokens_tup, (tuple, list)):
                raise ValueError(f"one set of conflict tokens must be stored "
                                 f"in a list or tuple; got {_conflict_tokens_tup}")
            token_tup_regex = _construct_regex_from_token_tup(
                _conflict_tokens_tup,
                add_word_boundary=True,
                optional_space=optional_space,
                token_augmentation=token_augmentation,
                language=language
            )
            token_group_indexes1 = rex.get_regex_match_group_indexes(
                pattern=token_tup_regex, string=str1, start_group_index=1
            )
            token_group_indexes2 = rex.get_regex_match_group_indexes(
                pattern=token_tup_regex, string=str2, start_group_index=1
            )

            if compare_sets(
                    token_group_indexes1,
                    token_group_indexes2,
                    allows_add=allows_add,
                    allows_drop=allows_drop
            ):
                return True
    elif str1:
        return not allows_drop
    elif str2:
        return not allows_add
    return False


def _has_token_drop(
        str1: str,
        str2: str,
        token: str,
        optional_space=True,
        augmentation=True,
        language='en'
):
    _tokens = token.split()
    for _token in _tokens:
        token_regex = get_token_inflection_regex(
            token=_token,
            optional_space=optional_space,
            augmentation=augmentation,
            language=language
        )

        token_match1 = re.search(pattern=token_regex, string=str1)
        token_match2 = re.search(pattern=token_regex, string=str2)
        if token_match1 is not None and token_match2 is None:
            return False
    return True


def has_token_drop(
        str1: str,
        str2: str,
        tokens=Iterable[Tuple],
        optional_space=True,
        augmentation=True,
        language='en'
) -> bool:
    """
    Check if the specified tokens are preserved (not dropped) between str1 and str2.

    This function returns True if any of the specified tokens are present in both
    str1 and str2, or if a token is absent from both strings. It returns False
    if a token is dropped (present in str1 but not in str2).

    Args:
        str1: The original string.
        str2: The modified string.
        tokens: Tokens to check for preservation.
        optional_space: If True, spaces in tokens are optional.
        augmentation: If True, match token inflections.
        language: The language of the text.

    Returns:
        bool: True if any token is preserved (not dropped), False if a drop is detected.

    Examples:
        >>> has_token_drop("the dog is running", "the is running", ["dog"], augmentation=False)
        False

        >>> has_token_drop("the dog is running", "the dog is running", ["dog"], augmentation=False)
        True

        >>> has_token_drop("hello world", "hello", ["world"], augmentation=False)
        False

        >>> has_token_drop("hello", "hello world", ["world"], augmentation=False)
        True
    """
    for token in iter__(tokens):
        if isinstance(token, str):
            if _has_token_drop(
                    str1,
                    str2,
                    token,
                    optional_space=optional_space,
                    augmentation=augmentation,
                    language=language
            ):
                return True
        else:
            for _token in token:
                if _has_token_drop(
                        str1,
                        str2,
                        _token,
                        optional_space=optional_space,
                        augmentation=augmentation,
                        language=language
                ):
                    return True

    return False


def has_token(
        s: str,
        tokens=Iterable[Tuple],
        optional_space=True,
        augmentation=True,
        language='en'
) -> bool:
    """
    Check if a string contains any of the specified tokens.

    Args:
        s: The string to check.
        tokens: Tokens to search for.
        optional_space: If True, spaces in tokens are optional.
        augmentation: If True, match token inflections.
        language: The language of the text.

    Returns:
        bool: True if any token is found in the string.

    Examples:
        >>> has_token("the dog is running", ["dog"], augmentation=False)
        True

        >>> has_token("the cat is sleeping", ["dog"], augmentation=False)
        False

        >>> has_token("I love dogs", ["dog"], augmentation=True)
        True

        >>> has_token("hello world", ["foo", "bar"], augmentation=False)
        False
    """
    def _has_token(_token):
        token_regex = get_token_inflection_regex(
            token=_token,
            optional_space=optional_space,
            augmentation=augmentation,
            language=language
        )

        return re.search(pattern=token_regex, string=s) is not None

    for token in iter__(tokens):
        if isinstance(token, str):
            if _has_token(token):
                return True
        else:
            for _token in token:
                if _has_token(_token):
                    return True

    return False
