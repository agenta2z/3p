import re
from typing import Union

from python_utils.nlp_utils.common import Languages


def get_token_inflection_regex(
        token: str,
        optional_space=True,
        augmentation=True,
        language: Union[str, Languages] = Languages.English,
) -> str:
    """
    Generate a regex pattern that matches the input token and its inflections.

    Args:
        token: The input token for which the regex pattern is generated.
        optional_space: If True, spaces in the token are replaced with optional spaces.
        augmentation: If True, the regex pattern will match the token's inflections.
        language: The language of the token.

    Returns:
        str: A regex pattern that matches the input token and its inflections.

    Examples:
        >>> get_token_inflection_regex("dog")
        "(?:dog(?:'s)?)|(?:dogs'?)|(?:dogg?est)|(?:dogg?er'?s?)|(?:dogg?or(?:'?s?)?)|(?:dogg?ing)|(?:dogness)"

        >>> get_token_inflection_regex("dog", optional_space=False, augmentation=False)
        'dog'

        >>> get_token_inflection_regex("box", optional_space=False, augmentation=True)
        "(?:box(?:'s)?)|(?:boxs'?)|(?:boxx?est)|(?:boxx?er'?s?)|(?:boxx?or(?:'?s?)?)|(?:boxx?ing)|(?:boxness)"

        >>> get_token_inflection_regex("run", augmentation=True)
        "(?:run(?:'s)?)|(?:runs'?)|(?:runn?est)|(?:runn?er'?s?)|(?:runn?or(?:'?s?)?)|(?:runn?ing)|(?:runness)"

    Raises:
        ValueError: If the provided language is not supported.

    """

    token = re.escape(token)
    if optional_space:
        token = token.replace(' ', r's?')  # `re.escape` already adds a '\' before space
    if augmentation:
        group = []
        if language == Languages.English:  # TODO support other languages
            if token[-1] == 's':
                group.append(f'(?:{token})')
                group.append(f"(?:{token}'?)")  # Xs'
            else:
                group.append(f"(?:{token}(?:'s)?)")  # X's
                group.append(f"(?:{token}s'?)")  # Xs'

            if 'a' <= token[-1] <= 'z':
                if token[-1] in ('s', 'h'):
                    group.append(f"(?:{token}es'?)")  # Xses, Xhes, Xses', Xhes'
                if token[-1] == 'y':
                    group.append(f"(?:{token[:-1]}ies'?)")  # Xies, Xies'
                if len(token) > 2 and token not in ('off',):
                    if not token.endswith('est'):
                        group.append(f'(?:{token}{token[-1]}?est)')  # Xest
                        if token[-1] == 'y':
                            group.append(f'(?:{token[:-1]}iest)')  # Xiest
                    if not token.endswith('er'):
                        group.append(f"(?:{token}{token[-1]}?er'?s?)")  # Xer, Xers, Xer's
                        if token[-1] == 'y':
                            group.append(f"(?:{token[:-1]}ier'?s?)")  # Xiers, Xier's
                    if not token.endswith('or'):
                        group.append(f"(?:{token}{token[-1]}?or(?:'?s?)?)")  # Xor, Xors, Xor's
                    if not token.endswith('ing'):
                        group.append(f'(?:{token}{token[-1]}?ing)')  # Xing
                    if not token.endswith('ness'):
                        group.append(f'(?:{token}ness)')  # Xness
                        if token[-1] == 'y':
                            group.append(f'(?:{token[:-1]}iness)')  # Xiness
        else:
            raise ValueError(f"language '{language}' is not supported")

        return '|'.join(group)
    else:
        return token


def _construct_regex_from_token_tup(
        tokens,
        add_word_boundary=True,
        optional_space=True,
        token_augmentation=True,
        language='en'
):
    """
    Construct a regex pattern from a tuple of tokens.

    This is an internal helper function that builds a regex pattern from tokens,
    optionally adding word boundaries and inflection patterns.

    Args:
        tokens: A sequence of tokens. Each token can be a string or a sequence of strings
            (for alternatives).
        add_word_boundary: If True, adds word boundary patterns to the regex.
        optional_space: If True, spaces in tokens are replaced with optional space patterns.
        token_augmentation: If True, adds inflection patterns for each token.
        language: The language for inflection patterns. Currently only 'en' is supported.

    Returns:
        str: A regex pattern string.

    Examples:
        >>> pattern = _construct_regex_from_token_tup(["hello"], add_word_boundary=False, token_augmentation=False)
        >>> "hello" in pattern
        True

        >>> pattern = _construct_regex_from_token_tup(["cat", "dog"], add_word_boundary=False, token_augmentation=False)
        >>> "cat" in pattern and "dog" in pattern
        True
    """
    regex = []
    for token in tokens:
        if isinstance(token, str):
            token_regex = get_token_inflection_regex(
                token,
                optional_space=optional_space,
                augmentation=token_augmentation,
                language='en'
            )
            regex.append(f'({token_regex})')
        else:
            group = []
            for _token in token:
                token_regex = get_token_inflection_regex(
                    _token,
                    optional_space=optional_space,
                    augmentation=token_augmentation,
                    language='en'
                )
                group.append(f'(?:{token_regex})')
            regex.append(f"({'|'.join(group)})")

    regex = '|'.join(regex)
    if add_word_boundary:
        return fr'(?:\b|^)({regex})(?:\b|\s|$)'
    else:
        return regex
