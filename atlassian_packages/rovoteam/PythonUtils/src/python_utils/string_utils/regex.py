import re
from re import *
from typing import Iterator, Union, Iterable

from attr import attrs, attrib

from python_utils.common_utils.iter_helper import product_
from python_utils.common_utils.typing_helper import all_str


def iter_matches(
        pattern,
        string: str,
        start_pos: int = 0,
        strip: bool = True,
        return_match_obj: bool = False
) -> Iterator[Union[str, Match]]:
    """
    Iterates through regex matches in the input string.

    Args:
        pattern: the regex pattern.
        string: match the pattern with this target string.
        start_pos: starting position in `string` for the regex match.
        strip: True to strip each matched string; effective if `return_match_obj` is False.
        return_match_obj: True to return the original regex match object.

    Returns:
        iterator: an iterator going through regex matches in the input string.

    Examples:
        >>> list(iter_matches(r'[A-Z]+', 'First Second Third'))
        ['F', 'S', 'T']
        >>> list(iter_matches(r'[A-Za-z]+', 'First Second Third'))
        ['First', 'Second', 'Third']
        >>> list(iter_matches(r'[A-Za-z]+', 'First Second Third', start_pos=6))
        ['Second', 'Third']
        >>> list(iter_matches(r'[A-Za-z]+\\s?', 'First Second Third', strip=False))
        ['First ', 'Second ', 'Third']
        >>> list(iter_matches(
        ...     r'[A-Za-z]+',
        ...     'First Second Third',
        ...     start_pos=6,
        ...     return_match_obj=True)
        ... )
        [<re.Match object; span=(6, 12), match='Second'>, <re.Match object; span=(13, 18), match='Third'>]
    """

    def _process_match(m):
        if return_match_obj:
            return m
        else:
            out = m.group(0)
            return out.strip() if strip else out

    if start_pos == 0:
        for match in finditer(pattern=pattern, string=string):
            yield _process_match(match)
    else:
        if isinstance(pattern, str):
            # the build-in `re.finditer` method also first compile the pattern string
            pattern = compile(pattern)

        match = pattern.search(string, pos=start_pos)  # ! supports search start position
        while match:
            match_end = match.end()
            yield _process_match(match)
            match = pattern.search(string, pos=match_end)


def get_tail_match_pattern(pattern: Union[str, Pattern]):
    if isinstance(pattern, str):
        return fr'{pattern}(?!.*{pattern})'
    elif isinstance(pattern, Pattern):
        return compile(
            fr'{pattern.pattern}(?!.*{pattern.pattern})',
            flags=pattern.flags
        )
    else:
        raise ValueError(f"unexpected regular expression pattern type {type(pattern)}")


def search_last(pattern, string: str, flags=0):
    search(get_tail_match_pattern(pattern), string=string, flags=flags)


def sub_first(pattern, repl, string, flags=0):
    return sub(
        pattern=pattern,
        repl=repl,
        string=string,
        count=1,
        flags=flags
    )


def sub_last(pattern, repl, string, flags=0):
    return sub(
        pattern=get_tail_match_pattern(pattern),
        repl=repl,
        string=string,
        flags=flags
    )


def regex_extract_all_groups(
        s: str,
        pattern: Union[str, Pattern],
        ignore_empty_matches: bool = True,
        flags: int = 0
):
    """
    Extracts all groups matching the given regular expression pattern from the input string.

    Args:
        s: The input string to extract groups from.
        pattern: The regular expression pattern to match.
        ignore_empty_matches: True to ignore empty matches.
        flags: flags: Optional flags to modify the behavior of the regular expression engine.

    Returns:
        List[str]: A list of strings representing all groups matching the pattern.

    Examples:
        >>> regex_extract_all_groups('song by artist', r'(.+) by (.+)')
        ['song', 'artist']
        >>> regex_extract_all_groups('song by ', r'(.+) by (.*)')
        ['song']
        >>> regex_extract_all_groups('song by ', r'(.+) by (.*)', ignore_empty_matches=False)
        ['song', '']
        >>> regex_extract_all_groups('foo123bar', r'([a-zA-Z]+)(\\d+)([a-zA-Z]+)')
        ['foo', '123', 'bar']
        >>> regex_extract_all_groups('apple,orange,banana', r'(?:([^,]*),)+')
        ['orange']
        >>> import re
        >>> regex_extract_all_groups('foo123bar', r'([a-z]+)(\\d+)([a-z]+)', flags=re.IGNORECASE)
        ['foo', '123', 'bar']
    """
    m = search(pattern, s, flags=flags)
    if m is not None:
        if ignore_empty_matches:
            return list(x for x in m.groups() if x)
        else:
            return list(m.groups())


def regexp_remove_many(s: str, *removals: Union[str, Pattern], flags: int = 0) -> str:
    """
    Removes all occurrences of multiple regular expression patterns from the input string.

    Args:
        s: The input string to remove patterns from.
        *removals: A sequence of regular expression patterns to remove.
        flags: flags: Optional flags to modify the behavior of the regular expression engine.

    Returns:
        str: A new string with all occurrences of the given patterns removed.

    Examples:
        >>> regexp_remove_many('The quick brown fox jumps over the lazy dog', 'brown', r'\\s\\w{3}\\s')
        'The quick jumps overlazy dog'
        >>> regexp_remove_many('1 2 3 4 5', r'\\d\\s')
        '5'
        >>> regexp_remove_many('Hello, World!', r'[,!]')
        'Hello World'
        >>> regexp_remove_many('i am single', r'\\ssingle$')
        'i am'
        >>> regexp_remove_many('i am a single person', r'\\ssingle$')
        'i am a single person'
        >>> import re
        >>> regexp_remove_many(
        ...    'thang you [Explicit]',
        ...    r'[0-9]+\\.[0-9]+', r'\\.\\.\\.', r'\\s\\-\\s(.+)\\.com',
        ...    r'\\s\\(.*\\)$', r'\\s\\[explicit\\]',
        ...    flags=re.IGNORECASE
        ... )
        'thang you'
    """
    for pattern in removals:
        s = sub(pattern, '', s, flags=flags)
    return s


def get_regex_match_group_indexes(
        pattern: Union[str, Pattern],
        string: str,
        start_group_index: int = 0,
        start_pos: int = 0
) -> set:
    """
    Returns a set of group indexes of the regex matches in the `string`.
    If `start_group_index` is not 0,
        then the returned group index is adjusted according to the `start_group_index`.

    Args:
        string: the string to match with the regex pattern.
        pattern: the regex pattern.
        start_group_index: only consider matched groups of index equal to or higher than this value.
        start_pos: starting position in `string` for the regex match.

    Returns: a set of group indexes of the regex matches in the `string`.

    Examples:
        >>> pattern = r'(zero)|(one)|(two)|(three)|(four)|(five)'
        >>> string = 'one oh one two four'
        >>> get_regex_match_group_indexes(pattern, string)
        {1, 2, 4}
        >>> get_regex_match_group_indexes(pattern, string, start_pos=8)
        {2, 4}
        >>> pattern = r'(.+)\\s\\((zero)|(one)|(two)|(three)|(four)|(five)\\)'
        >>> string = 'number (one oh one two four)'
        >>> get_regex_match_group_indexes(pattern, string, start_group_index=1)
        {1, 2, 4}

    """

    def _get_match_idx(_m):
        _groups = _m.groups()[start_group_index:]
        for i, x in enumerate(_groups):
            if x is not None:
                if x.strip() != _m.group(0).strip():
                    raise ValueError(
                        f"inconsistent match value found; expect {x.strip()}; "
                        f"got {_m.group(0).strip()}; "
                        f"pattern '{pattern}'; "
                        f"string '{string}'"
                    )
                return i
        raise ValueError(
            f"unable to find match {_m.group(0).strip()} in {_groups}; "
            f"pattern '{pattern}'; "
            f"string '{string}'"
        )

    return set(
        _get_match_idx(m)
        for m in iter_matches(
            pattern=pattern,
            string=string,
            start_pos=start_pos,
            return_match_obj=True
        )
    )


def get_contains_whole_word_regex(word: Union[str, Iterable[str]], escape: bool = True, additional_seps: str = '_') -> str:
    """
    Generate a regular expression to match a given word or any word from a sequence
    as a whole word in a string. This function constructs a regex pattern that matches
    'word' or any word in a sequence as a separate, whole word. It can optionally escape
    special regex characters in the words to treat them as literal strings. The function
    also supports specifying additional characters that should be considered as word
    boundaries, in addition to the standard word boundary '\\b'.

    Args:
        word: The word (or sequence of words) to create a regex pattern for.
        escape: If True (default), special regex characters in 'word' are escaped.
                If False, 'word' is treated as a raw regex pattern.
        additional_seps: Additional characters to be considered as
                whole word separators. Defaults to '_-'.

    Returns:
        str: A string containing the regex pattern.

    Raises:
        ValueError: If 'word' is neither a string nor a sequence of strings.

    Examples:
        >>> print(get_contains_whole_word_regex('cafe'))
        (?:(?<=_)|\\b)cafe(?:(?=_)|\\b)
        >>> print(get_contains_whole_word_regex('cafe', additional_seps=''))
        \\bcafe\\b
        >>> print(get_contains_whole_word_regex(['foo', 'bar'], additional_seps=''))
        \\b(foo|bar)\\b
    """
    if additional_seps:
        whole_word_prefix_suffix_with_additional_seps = '|'.join(re.escape(x) for x in additional_seps)
        whole_word_prefix = rf'(?:(?<={whole_word_prefix_suffix_with_additional_seps})|\b)'
        whole_word_suffix = rf'(?:(?={whole_word_prefix_suffix_with_additional_seps})|\b)'
    else:
        whole_word_prefix = whole_word_suffix = r'\b'
    if not word:
        raise ValueError(f"`word` must be a non-empty string, or a list of non-empty strings; got '{word}'")
    if isinstance(word, str):
        return whole_word_prefix + (re.escape(word) if escape else word) + whole_word_suffix
    else:
        non_empty_words = []
        for _word in word:
            if not _word:
                raise ValueError(f"`word` must be a non-empty string, or a list of non-empty strings; got '{word}'")
            else:
                non_empty_words.append(_word)
        try:
            if escape:
                return rf"{whole_word_prefix}(" + '|'.join(re.escape(_word) for _word in non_empty_words) + rf"){whole_word_suffix}"
            else:
                return rf"{whole_word_prefix}(" + '|'.join(non_empty_words) + rf"){whole_word_suffix}"
        except:
            raise ValueError(f"{word} is neither a string, nor a sequence of strings to search as a whole word")


def contains_whole_word(
        s: str,
        word: Union[str, Iterable[str]],
        ignore_case: bool = False,
        escape: bool = True,
        additional_whole_word_seps: str = '_'
) -> bool:
    """
    Check if a given word or any word from a sequence is present as a whole word in a string.

    This function uses regular expressions to determine if 'word' or any word in a sequence
    exists as a separate, whole word within the string 's'. It considers word boundaries and
    optionally additional specified characters as word separators to ensure that the match
    is for a whole word and not part of another word. The function can optionally escape special
    regex characters in the words and perform case-insensitive searches.

    Args:
        s: The string to be searched in.
        word: The word (or sequence of words) to search for as a whole word in 's'.
        ignore_case: If True, the search is case-insensitive. Defaults to False.
        escape: If True (default), special regex characters in 'word' are escaped.
                If False, 'word' is treated as a raw regex pattern.
        additional_whole_word_seps: Additional characters to be considered as
                whole word separators alongside the standard word boundary '\\b'. Defaults to '_'.

    Returns:
        bool: True if 'word' or any word from the sequence is found as a whole word in 's', False otherwise.

    Examples:
        >>> contains_whole_word('', 'cafe')
        False
        >>> contains_whole_word('jazz cafe', 'cafe')
        True
        >>> contains_whole_word('jazz "cafe"', 'cafe')
        True
        >>> contains_whole_word('play full house', 'full')
        True
        >>> contains_whole_word('joey badass', 'joey badass')
        True
        >>> contains_whole_word('joey badass', 'joey bada')
        False
        >>> contains_whole_word('what does the fox say', 'the fox what does the fox say')
        False
        >>> contains_whole_word('Jazz Cafe', 'cafe', ignore_case=True)
        True
        >>> contains_whole_word('JAZZ CAFE', 'cafe', ignore_case=True)
        True
        >>> contains_whole_word('Jazz Cafe', 'cafe', ignore_case=False)
        False
        >>> contains_whole_word('She\\'s SELLS sea SHELLS', ['she\\'s', 'sea\\'s'], ignore_case=True)
        True
        >>> contains_whole_word('Shee SELLS sea SHELLS', ['she.', 'sea\\'s'], escape=True, ignore_case=True)
        False
        >>> contains_whole_word('Shee SELLS sea SHELLS', ['she.', 'sea\\'s'], escape=False, ignore_case=True)
        True
        >>> contains_whole_word('Shee SELLS sea SHELLS', 'ea', escape=True, ignore_case=True)
        False
        >>> contains_whole_word('Shee SELLS sea SHELLS', 'ea', escape=True, ignore_case=True, additional_whole_word_seps='s')
        True
    """
    flags = re.IGNORECASE if ignore_case else 0
    pattern = get_contains_whole_word_regex(word, escape=escape, additional_seps=additional_whole_word_seps)
    if re.search(pattern, s, flags) is not None:
        return True
    return False


@attrs(slots=True)
class RegexFactoryItem:
    main_pattern = attrib(type=Union[str, Iterable[str]])
    pattern_prefix = attrib(type=Union[str, Iterable[str]], default=None)
    pattern_suffix = attrib(type=Union[str, Iterable[str]], default=None)

    def __str__(self):
        out = []
        for _pattern_prefix, _pattern, _pattern_suffix in product_(
                self.pattern_prefix,
                self.main_pattern,
                self.pattern_suffix
        ):
            if not _pattern:
                raise ValueError("the main pattern cannot be empty")
            _pattern = f"(?:{_pattern_prefix or ''}{_pattern}{_pattern_suffix or ''})"
            if _pattern not in out:
                out.append(_pattern)

        return '|'.join(out)


@attrs(slots=True)
class RegexFactory:
    patterns = attrib(type=Union[str, RegexFactoryItem, Iterable[Union[str, RegexFactoryItem]]])

    def __attrs_post_init__(self):
        patterns = []
        for _pattern in self.patterns:
            if isinstance(_pattern, (list, tuple)):
                if all_str(_pattern):
                    patterns.append(
                        RegexFactoryItem(main_pattern=_pattern)
                    )
                elif len(_pattern) == 2:
                    patterns.append(
                        RegexFactoryItem(
                            pattern_prefix=_pattern[0],
                            main_pattern=_pattern[1]
                        )
                    )
                elif len(_pattern) == 3:
                    patterns.append(
                        RegexFactoryItem(
                            pattern_prefix=_pattern[0],
                            main_pattern=_pattern[1],
                            pattern_suffix=_pattern[2]
                        )
                    )
            elif isinstance(_pattern, (str, RegexFactoryItem)):
                patterns.append(_pattern)
            else:
                raise ValueError(f"unsupported pattern '{_pattern}'")
        self.patterns = patterns

    def __str__(self):
        return '|'.join((
            f'(?:{_pattern})'
            for _pattern in self.patterns
        ))


def _get_whole_word_pattern(
        pattern, use_space_as_word_boundary, include_space_after=False, include_space_before=False
):
    if use_space_as_word_boundary:
        if include_space_before and include_space_after:
            return fr'(?:^|\s)(?:{pattern})(?:$|\s)'
        elif include_space_before:
            return fr'(?:^|\s)(?:{pattern})(?=$|\s)'
        elif include_space_after:
            return fr'(^|(?<=\s))(?:{pattern})(?:$|\s)'
        else:
            return fr'(^|(?<=\s))(?:{pattern})(?=$|\s)'
    else:
        if include_space_before and include_space_after:
            return fr'(?:^|\s)\b(?:{pattern})\b(?:$|\s)'
        elif include_space_before:
            return fr'(?:^|\s)\b(?:{pattern})\b'
        elif include_space_before:
            return fr'\b(?:{pattern})\b(?:$|\s)'
        else:
            return fr'\b(?:{pattern})\b'


def contains_as_whole_word(s: str, target: str, use_space_as_word_boundary=True):
    regex = _get_whole_word_pattern(
        re.escape(target),
        use_space_as_word_boundary,
        include_space_before=False,
        include_space_after=False,
    )
    return re.search(pattern=regex, string=s) is not None


def replace_by_whole_word(
        s: str,
        old: str,
        new: str,
        use_space_as_word_boundary=True,
        additional_whole_word_seps: str = '_"\'',
        include_space_after=False,
        include_space_before=False,
):
    """

    Args:
        s:
        old:
        new:
        use_space_as_word_boundary:
        include_space_after:
        include_space_before:

    Returns:

    Examples:
        >>> s = '3 a m'
        >>> replace_by_whole_word(s, 'a m', 'am')
        '3 am'

        >>> s = 'hello foo bar world'
        >>> replace_by_whole_word(s, 'foo bar', 'foobar')
        'hello foobar world'

        >>> s = 'the cat sat on the mat'
        >>> replace_by_whole_word(s, 'cat', 'dog')
        'the dog sat on the mat'
    """
    return re.sub(
        get_contains_whole_word_regex(
            old,
            use_space_as_word_boundary,
            additional_seps=additional_whole_word_seps
        ),
        new,
        s,
    )


def remove_by_whole_word(
        s: str,
        substr: str,
        use_space_as_word_boundary: bool = True,
        include_space_after: bool = False,
        include_space_before: bool = False,
) -> str:
    """
    Removes substring `substr` from the input string if it is a "whole word" in the input string
        (e.g. word boundary defined by '\b' in regular expression).
    For example, we can remove "play" as a whole word from "play taylor swift songs",
        but cannot remove it as a whole word from "show playboy on youtube".

    Args:
        s: the input string.
        substr: the substring to remove.
        use_space_as_word_boundary: True if only uee spaces and beginning and ending of strings
                as the word boundary;
            otherwise, use regular expression '\b' as word boundary.
        include_space_after: True to also remove any space before `substr` in the input string.
        include_space_before: True to also remove any space after `substr` in the input string.

    Returns: a copy of the input string with `substr` removed
        if it is found as a "whole word" in the input string.

    """
    return re.sub(
        _get_whole_word_pattern(
            (
                re.escape(substr)
                if isinstance(substr, str)
                else '|'.join(re.escape(_old) for _old in substr)
            ),
            use_space_as_word_boundary=use_space_as_word_boundary,
            include_space_before=include_space_before,
            include_space_after=include_space_after,
        ),
        '',
        s,
    )
