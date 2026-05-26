from typing import Iterator, Iterable, Callable, Union, Optional, Any, List, Tuple

from python_utils.common_utils.iter_helper import iter__, iter_
from python_utils.common_utils.typing_helper import solve_nested_singleton_tuple_list
from python_utils.string_utils.tokenization import tokenize


def add_prefix(s: str, prefix: Any, sep: Optional[str] = '_', avoid_repeat: bool = False) -> str:
    """
    Adds a prefix to the beginning of the current string.
    Args:
        s: the current string.
        prefix: the prefix; if this argument is not a string,
            it will be converted to string by `str(prefix)`.
        sep: whne non-empty, this is the separator between the prefix and the current string;
            this argument is ignored if the prefix already ends with this separator.
        avoid_repeat: True if not adding the prefix if `s` already starts with the prefix.

    Returns: if `prefix` is not emtpy, then a new string with the current string plus the suffix;
        otherwise the input string `s` itself.

    Examples:
        >>> assert add_prefix('', prefix='global', sep='_') == ''
        >>> assert add_prefix('name', prefix='global', sep='_') == 'global_name'
        >>> assert add_prefix('name', prefix='global_', sep='_') == 'global_name'
        >>> assert add_prefix('name', prefix='', sep='_') == 'name'
        >>> assert add_prefix('name', prefix=None, sep='_') == 'name'
        >>> assert add_prefix('name', prefix='global', sep='') == 'globalname'
        >>> assert add_prefix('name', prefix='global_', sep=None) == 'global_name'
        >>> assert add_prefix('global_name', prefix='global', sep='_', avoid_repeat=True) == 'global_name'
        >>> assert add_prefix('global_name', prefix='global', sep='_', avoid_repeat=False) == 'global_global_name'
    """
    if s and prefix is not None and prefix != '':
        prefix = str(prefix)
        if sep and not prefix.endswith(sep):
            prefix += sep
        if not (avoid_repeat and s.startswith(prefix)):
            return prefix + s
    return s


def add_suffix(s: str, suffix: Any, sep: Optional[str] = '_', avoid_repeat: bool = False) -> str:
    """
    Adds a suffix to the end of the current string.
    Args:
        s: the current string.
        suffix: the suffix; if this argument is not a string,
            it will be converted to string by `str(suffix)`.
        sep: when non-empty, this is the separator between the current string and the suffix;
            this argument is ignored if the suffix already starts with this separator.
        avoid_repeat: True if not adding the suffix if `s` already ends with the suffix.

    Returns: if `suffix` is not emtpy, then a new string with the current string plus the suffix;
        otherwise the input string `s` itself.

    Examples:
        >>> assert add_suffix('', suffix=1, sep='-') == ''
        >>> assert add_suffix('name', suffix=1, sep='-') == 'name-1'
        >>> assert add_suffix('name', suffix='-1', sep='-') == 'name-1'
        >>> assert add_suffix('name', suffix='', sep='_') == 'name'
        >>> assert add_suffix('name', suffix=None, sep='_') == 'name'
        >>> assert add_suffix('name', suffix='1', sep='') == 'name1'
        >>> assert add_suffix('name', suffix='-1', sep=None) == 'name-1'
        >>> assert add_suffix('name1', suffix='1', sep='', avoid_repeat=True) == 'name1'
        >>> assert add_suffix('name-1', suffix='-1', sep=None, avoid_repeat=False) == 'name-1-1'
    """
    if s and suffix is not None and suffix != '':
        suffix = str(suffix)
        if sep and not suffix.startswith(sep):
            suffix = sep + suffix
        if not (avoid_repeat and s.endswith(suffix)):
            return s + suffix
    return s


def add_prefix_suffix(
        s: str,
        prefix: str,
        suffix: str,
        sep: Optional[str] = '_',
        sep_for_prefix: Optional[str] = None,
        sep_for_suffix: Optional[str] = None,
        avoid_repeat: bool = False
):
    """
    Adds a prefix/suffix to the beginning/end of the current string.
    This is a convenience function first calling :func:`add_prefix`
    and then calling :func:`add_suffix` for its implementation.

    Args:
        s: the current string.
        prefix: the prefix to add to the current string.
        suffix: the suffix to add to the current string.
        sep: the default separator to use for both prefix and suffix if not specified separately.
        sep_for_prefix: the separator to use specifically for the prefix.
        sep_for_suffix: the separator to use specifically for the suffix.
        avoid_repeat: True if not adding the prefix/suffix if `s` already starts/ends with it.

    Returns: a new string with the current string plus the prefix and the suffix.

    See Also:
        1. :func:`add_prefix`
        2. :func:`add_suffix`

    Examples:
        >>> assert add_prefix_suffix('name', prefix='global', suffix='1', sep='_') == 'global_name_1'
        >>> assert add_prefix_suffix('name', prefix='global_', suffix='_1', sep='_') == 'global_name_1'
        >>> assert add_prefix_suffix('name', prefix='', suffix='', sep='_') == 'name'
        >>> assert add_prefix_suffix('name', prefix=None, suffix=None, sep='_') == 'name'
        >>> assert add_prefix_suffix('name', prefix='global', suffix='1', sep='') == 'globalname1'
        >>> assert add_prefix_suffix('name', prefix='global_', suffix='_1', sep=None) == 'global_name_1'
        >>> assert add_prefix_suffix('name', prefix='global', suffix='1', sep='-', avoid_repeat=True) == 'global-name-1'
        >>> assert add_prefix_suffix('global_name_1', prefix='global', suffix='1', sep='_', avoid_repeat=False) == 'global_global_name_1_1'
    """
    return add_suffix(
        add_prefix(
            s,
            prefix,
            sep=(sep_for_prefix or sep),
            avoid_repeat=avoid_repeat
        ),
        suffix,
        sep=(sep_for_suffix or sep),
        avoid_repeat=avoid_repeat
    )


def replace_prefix(
        s: str,
        prefix_to_replace: str,
        replacement: str,
        sep='_'
) -> str:
    if sep and (not prefix_to_replace.endswith(sep)):
        prefix_to_replace = prefix_to_replace + sep

    if s.startswith(prefix_to_replace):
        if sep and (not replacement.endswith(sep)):
            replacement = replacement + sep
        return replacement + s[len(prefix_to_replace):]
    else:
        return s


def replace_suffix(
        s: str,
        suffix_to_replace: str,
        replacement: str,
        sep='_'
) -> str:
    if sep and (not suffix_to_replace.startswith(sep)):
        suffix_to_replace = sep + suffix_to_replace

    if s.endswith(suffix_to_replace):
        if sep and (not replacement.startswith(sep)):
            replacement = sep + replacement
        return s[:-len(suffix_to_replace)] + replacement
    else:
        return s


def remove_suffix(text: str, suffix: str) -> str:
    if text.endswith(suffix):
        return text[: -len(suffix)]
    return text


def remove_prefix(text: str, prefix: str) -> str:
    if text.startswith(prefix):
        return text[len(prefix):]
    return text


def remove_any_prefix(text: str, prefixes: Iterable[str], return_match_index: bool = False) -> Union[str, Tuple[str, int]]:
    for i, prefix in enumerate(iter_(prefixes)):
        if text.startswith(prefix):
            text_without_prefix = text[len(prefix):]
            if return_match_index:
                return text_without_prefix, i
            else:
                return text_without_prefix
    if return_match_index:
        return text, -1
    else:
        return text


def remove_prefix_suffix(
        s: str,
        prefixes: Iterable[str] = None,
        suffixes: Iterable[str] = None,
        sep: str = ' '
) -> str:
    """
    Removes the longest matching prefix and suffix from the string `s`.

    Args:
        s: The input string to romove prefixes/suffixes from.
        prefixes: A sequence of prefixes to remove from `s`. The prefixes will be sorted in the
            decreasing order of length and the function checks if each prefix exists at the
            beginning of the string `s`. If the prefix is found, then it is removed from the
            the start of string `s`. It repeats this process until no more matching prefixes
            can be found.
        suffixes: A sequence of suffixes to remove from `s`. The suffixes will be sorted in the
            decreasing order of length and the function checks if each suffix exists at the
            end of the string `s`. If the suffix is found, then it is removed from the
            end of string `s`. It repeats this process until no more matching suffixes can be found.
        sep: The separator between a prefix/suffix and the remaining part of string `s`.

    Returns: The resulting string after removing the prefixes and suffixes.

    Examples:
        >>> remove_prefix_suffix(
        ...   'turn on the light',
        ...   prefixes=['turn', 'turn on'],
        ...   suffixes=None,
        ...   sep=' '
        ... )
        'the light'

        >>> remove_prefix_suffix(
        ...   'the quick brown fox',
        ...   prefixes= ["the", "quick", "the quick"],
        ...   suffixes=["fox"],
        ...   sep=' '
        ... )
        'brown'

        >>> remove_prefix_suffix(
        ...   'the quick brown fox',
        ...   prefixes= ["the", "quick", "the quick"],
        ...   suffixes=["fox"],
        ...   sep='-'
        ... )
        'the quick brown fox'

        >>> remove_prefix_suffix(
        ...   'the-quick brown-fox',
        ...   prefixes= ["the", "quick", "the quick"],
        ...   suffixes=["fox"],
        ...   sep='-'
        ... )
        'quick brown'
    """

    if prefixes:
        if not isinstance(prefixes, str):
            prefixes = sorted(prefixes, key=lambda x: len(x), reverse=True)
        prefix_removed = True
        while prefix_removed:
            prefix_removed = False
            for _prefix in iter__(prefixes):
                if _prefix:
                    if not _prefix.endswith(sep):
                        _prefix += sep
                    if s.startswith(_prefix):
                        s = s[len(_prefix):]
                        prefix_removed = True
    if suffixes:
        if not isinstance(suffixes, str):
            suffixes = sorted(suffixes, key=lambda x: len(x), reverse=True)
        suffix_removed = True
        while suffix_removed:
            suffix_removed = False
            for _suffix in iter__(suffixes):
                if _suffix:
                    if not _suffix.startswith(sep):
                        _suffix = sep + _suffix
                    if s.endswith(_suffix):
                        s = s[: -len(_suffix)]
                        suffix_removed = True

    return s


def _get_token_index_after_common_prefix(tks):
    """
    Returns the index of the last token in the common prefix of a list of tokens.

    Examples:
        >>> _get_token_index_after_common_prefix(
        ...     [['turn', 'on', 'the', 'light'], ['turn', 'on', 'the', 'lamp']]
        ... )
        3
    """
    i = 0
    min_tk_len = min(len(x) for x in tks)
    while i < min_tk_len:
        if any((tks[j][i] != tks[0][i]) for j in range(1, len(tks))):
            break
        i += 1
    return i


def _get_token_index_before_common_suffix(tks):
    """
    Returns the index of the first token in the common suffix of a list of tokens.

    Examples:
        >>> _get_token_index_before_common_suffix(
        ...    [['turn', 'on', 'the', 'light'], ['turn', 'off', 'the', 'light']]
        ... )
        -3
    """
    i = -1
    min_tk_len = min(len(x) for x in tks)
    while i > -min_tk_len - 1:
        if any((tks[j][i] != tks[0][i]) for j in range(1, len(tks))):
            break
        i -= 1
    return i


def remove_common_specified_prefix(
        *strings: str,
        prefixes: Iterable[str],
        sep: str = ' '
) -> List[str]:
    """
    Removes the common prefixes specified in `prefixes` from the input `strings`.

    Args:
        *strings: The input strings to process.
        prefixes: A collection of common prefixes to remove.
        sep: The separator between a prefix and the remaining part of the string.

    Returns: A list of strings with common prefixes specified in `prefixes` removed.


    Returns: the `strings` with common prefixes specified in `prefixes` removed.

    Examples:
        >>> remove_common_specified_prefix(
        ...     "turn on lights", "turn on fan",
        ...     prefixes=['turn', 'turn on', 'play']
        ... )
        ['lights', 'fan']

        >>> remove_common_specified_prefix(
        ...     'turn on the light',
        ...     'turn on the lamp',
        ...     prefixes=['turn']
        ... )
        ['on the light', 'on the lamp']

        >>> remove_common_specified_prefix(
        ...     'turn on the light',
        ...     'turn on the lamp',
        ...     prefixes=['light']
        ... )
        ['turn on the light', 'turn on the lamp']

    """

    if prefixes:
        if isinstance(prefixes, str):
            prefixes = (prefixes,)
        else:
            prefixes = sorted(prefixes, key=lambda x: len(x), reverse=True)
        len_sep = len(sep)
        for prefix in prefixes:
            if all(s.startswith(prefix + sep) for s in strings):
                strings = [s[(len(prefix)) + len_sep:] for s in strings]

    return list(strings)


def remove_common_specified_suffix(
        *strings: str,
        suffixes: Iterable[str],
        sep: str = ' '
) -> List[str]:
    """
    Removes common suffixes specified in `suffixes` from input `strings`.

    Args:
        *strings: Input strings to process.
        suffixes: Collection of common suffixes to remove.
        sep: Separator between a suffix and the remaining part of the string.

    Returns: A list of strings with common suffixes specified in `suffixes` removed.

    Examples:
        >>> remove_common_specified_suffix(
        ...     "lights turned on", "fan turned on",
        ...     suffixes=['turned on', 'start playing', 'on']
        ... )
        ['lights', 'fan']

        >>> remove_common_specified_suffix(
        ...     'the light turned on',
        ...     'the lamp turned on',
        ...     suffixes=['turned on']
        ... )
        ['the light', 'the lamp']

        >>> remove_common_specified_suffix(
        ...     'the light turned on',
        ...     'the lamp turned on',
        ...     suffixes=['light']
        ... )
        ['the light turned on', 'the lamp turned on']
    """
    if suffixes:
        if isinstance(suffixes, str):
            suffixes = (suffixes,)
        else:
            suffixes = sorted(suffixes, key=lambda x: len(x), reverse=True)

        len_sep = len(sep)
        for suffix in suffixes:
            if all(s.endswith(sep + suffix) for s in strings):
                strings = [s[:-(len(suffix) + len_sep)] for s in strings]

    return list(strings)


def remove_common_prefix_suffix(
        *strings: str,
        tokenizer: Optional[Union[Callable, str]] = None,
        prefixes: Iterable[str] = None,
        suffixes: Iterable[str] = None,
        remove_prefix: bool = True,
        remove_suffix: bool = False
) -> List[str]:
    """
    Remove common prefixes/suffixes from string instances.

    Args:
        *strings: The string instances to process.
        tokenizer: The tokenizer used to split the input strings.
        prefixes: A collection of common prefixes to remove. If this is not specified,
            then the function tries to remove the longest common prefixes from the strings.
        suffixes: A collection of common suffixes to remove. If this is not specified,
            then the function tries to remove the longest common suffixes from the strings.
        remove_prefix: A flag indicating whether to remove common prefixes.
            Setting this to False will disable removing `prefixes` from `strings` even if they
            are specified.
        remove_suffix: A flag indicating whether to remove common suffixes.
            Setting this to False will disable removing `suffixes` from `strings` even if they
            are specified.
    Returns: strings with common prefixes/suffixes removed.

    Examples:
        >>> remove_common_prefix_suffix('play music', 'play songs')
        ['music', 'songs']
        >>> remove_common_prefix_suffix('play the music', 'play the songs')
        ['music', 'songs']
        >>> remove_common_prefix_suffix(
        ...    'start the car', 'start the engine', 'start the vehicle',
        ...    remove_prefix=False, remove_suffix=True
        ... )
        ['start the car', 'start the engine', 'start the vehicle']
        >>> remove_common_prefix_suffix(
        ...    'start the car', 'start the car', 'start the car',
        ...    remove_prefix=False, remove_suffix=True
        ... )
        ['', '', '']
        >>> remove_common_prefix_suffix('abcd', 'abef', tokenizer=list)
        ['c d', 'e f']
        >>> remove_common_prefix_suffix('turn on light', 'turn on the lamp', prefixes=['play'])
        ['turn on light', 'turn on the lamp']
        >>> remove_common_prefix_suffix('turn on light', 'turn on the lamp', prefixes=['turn'])
        ['on light', 'on the lamp']
        >>> remove_common_prefix_suffix('turn on light', 'turn on the lamp', prefixes=['turn on'])
        ['light', 'the lamp']
    """
    strings = solve_nested_singleton_tuple_list(strings, atom_types=str)
    if remove_prefix and remove_suffix:
        if prefixes is None:
            tks = [tokenize(s, tokenizer) for s in strings]
            i = _get_token_index_after_common_prefix(tks)
            if suffixes is None:
                j = _get_token_index_before_common_suffix(tks)
                strings = (' '.join(x[i:(len(x) + j + 1)]) for x in tks)
            else:
                strings = remove_common_specified_suffix(
                    *(' '.join(x[i:]) for x in tks),
                    suffixes=suffixes
                )
        else:
            if suffixes is None:
                tks = [tokenize(s, tokenizer) for s in strings]
                j = _get_token_index_before_common_suffix(tks)
                strings = (' '.join(x[:(len(x) + j + 1)]) for x in tks)
            else:
                if tokenizer is not None:
                    strings = (' '.join(tokenize(s, tokenizer)) for s in strings)

            strings = remove_common_specified_prefix(*strings, prefixes=prefixes)
            if suffixes is not None:
                strings = remove_common_specified_suffix(*strings, suffixes=suffixes)
    elif remove_prefix:
        if prefixes is None:
            tks = [tokenize(s, tokenizer) for s in strings]
            i = _get_token_index_after_common_prefix(tks)
            strings = (' '.join(x[i:]) for x in tks)
        else:
            if tokenizer is not None:
                strings = (' '.join(tokenize(s, tokenizer)) for s in strings)

            strings = remove_common_specified_prefix(*strings, prefixes=prefixes)
    elif remove_suffix:
        if suffixes is None:
            tks = [tokenize(s, tokenizer) for s in strings]
            j = _get_token_index_before_common_suffix(tks)
            strings = (' '.join(x[:(len(x) + j + 1)]) for x in tks)
        else:
            if tokenizer is not None:
                strings = (' '.join(tokenize(s, tokenizer)) for s in strings)

            strings = remove_common_specified_suffix(*strings, suffixes=suffixes)

    return list(strings)


def remove_all_prefix_tokens(s: str, prefixes: Iterable[str], token_sep: str = ' ') -> str:
    """
    Removes all prefix tokens from the input string.
    For example, suppose input string is 'the my songs', and `prefixes` is `['a', 'the', 'my']`,
        the returned string is 'songs' with  prefixes 'the', 'my' removed.

    Args:
        s: the input string.
        prefixes: the prefixes to remove.
        token_sep: the token separator; default is a single space

    Returns: a copyt oof the input string with

    """
    while True:
        no_replacement = True
        for prefix in prefixes:
            if s.startswith(prefix + token_sep):
                s = s[len(prefix) + len(token_sep):]
                no_replacement = False
        if no_replacement:
            break
    return s


def remove_all_suffix_tokens(s: str, suffixes: Iterable[str], token_sep: str = ' ') -> str:
    while True:
        no_replacement = True
        for suffix in suffixes:
            if s.endswith(token_sep + suffix):
                s = s[: (-len(suffix) - len(token_sep))]
                no_replacement = False
        if no_replacement:
            break
    return s


def solve_name_conflict(
        name: str,
        existing_names: Union[set, Iterable],
        always_with_suffix: bool = False,
        suffix_sep: str = '',
        suffix_gen: Union[Iterator, str, Callable[[int], str]] = None,
        update_current_names: bool = True
) -> str:
    """
    Solves name conflict by appending a suffix
    if the name already exists in the provided `existing_names`.

    Examples:
    >>> solve_name_conflict(name='para', existing_names={'para', 'para1', 'para2', 'para3'})
    'para4'
    >>> def example_suffix_gen():
    ...     for x in range(1, 5):
    ...         yield 'i' * x
    >>> solve_name_conflict(name='para', existing_names={'para', 'para_i', 'para_ii', 'para_iii'}, suffix_sep='_', suffix_gen=example_suffix_gen())
    'para_iiii'

    Args:
        name: he name to solve conflict.
        existing_names: the set of all existing names.
        always_with_suffix: True if the resolved name should always have the suffix;
            False if we also test whether `name` itself without the suffix.
        suffix_sep: the separator to insert between the name and the suffix.
        suffix_gen: optionally provides a generator of name suffixes;
            it can be 1) a string pattern;
            2) a callable that takes an integer and returns a name;
            3) an iterator of strings;
            if not provided, the suffix will be number index starting at 1.
        update_current_names: True to add the returned name to `current_names`;
            this only works if `current_names` passed into this function is a set.

    Returns: the solved name with a possible suffix to avoid name conflict.

    """

    if not isinstance(existing_names, set):
        existing_names = set(existing_names)
        update_current_names = False

    if suffix_gen is None:
        _name = name
        if always_with_suffix:
            name = add_suffix(_name, 1, sep=suffix_sep)
            _name_index = 2
        else:
            _name_index = 1

        while name in existing_names:
            name = add_suffix(_name, _name_index, sep=suffix_sep)
            _name_index += 1

    elif isinstance(suffix_gen, str):
        _name = name
        if always_with_suffix:
            name = add_suffix(_name, suffix_gen.format(1), sep=suffix_sep)
            _name_index = 2
        else:
            _name_index = 1

        while name in existing_names:
            name = add_suffix(_name, suffix_gen.format(_name_index), sep=suffix_sep)
            _name_index += 1
    elif callable(suffix_gen):
        _name = name
        if always_with_suffix:
            name = add_suffix(_name, suffix_gen(1), sep=suffix_sep)
            _name_index = 2
        else:
            _name_index = 1

        while name in existing_names:
            name = add_suffix(_name, suffix_gen(_name_index), sep=suffix_sep)
            _name_index += 1
    else:
        _name = name
        suffix_gen = iter(suffix_gen)
        if always_with_suffix:
            name = add_suffix(_name, str(next(suffix_gen)), sep=suffix_sep)
        while name in existing_names:
            name = add_suffix(_name, str(next(suffix_gen)), sep=suffix_sep)

    if update_current_names:
        existing_names.add(name)
    return name


def get_next_numbered_string(strings: Union[str, Iterable[str]]) -> str:
    """
    Generates the next string in a sequence by finding the string with the largest numeric suffix
    in the list and incrementing it. Raises an error if the prefixes are inconsistent.

    Args:
        strings (list of str): A list of strings with numeric suffixes, e.g., ['part_0001', 'part_0002'].

    Returns:
        str: The next string in the sequence with an incremented numeric suffix, e.g., 'part_0003'.

    Raises:
        ValueError: If the prefixes are inconsistent across the strings.

    Examples:
        >>> get_next_numbered_string(['part_0001', 'part_0002', 'part_0003'])
        'part_0004'

        >>> get_next_numbered_string(['image_0010', 'image_0015', 'image_0014'])
        'image_0016'

        >>> get_next_numbered_string(['file_001', 'file_003', 'file_002'])
        'file_004'

        >>> get_next_numbered_string(['part_001', 'section_002'])
        Traceback (most recent call last):
        ...
        ValueError: Inconsistent prefixes found in the list.
    """
    if not strings:
        raise ValueError("Input list is empty.")

    # Extract prefixes and numeric parts
    prefixes = []
    numbers = []
    length_of_number_part = None

    for s in iter__(strings):
        base_string = s.rstrip('0123456789')
        number_str = s[len(base_string):]

        if not number_str.isdigit():
            raise ValueError(f"Invalid numeric suffix in string: {s}")

        if length_of_number_part is None:
            length_of_number_part = len(number_str)
        elif len(number_str) != length_of_number_part:
            raise ValueError("Inconsistent number length in the list.")

        prefixes.append(base_string)
        numbers.append(int(number_str))

    # Check if all prefixes are the same
    if len(set(prefixes)) != 1:
        raise ValueError("Inconsistent prefixes found in the list.")

    # Find the maximum number and increment it
    max_number = max(numbers)
    next_number = max_number + 1

    # Format the new number with leading zeros to match the original length
    next_number_str = str(next_number).zfill(length_of_number_part)

    # Return the next numbered string
    return f"{prefixes[0]}{next_number_str}"
