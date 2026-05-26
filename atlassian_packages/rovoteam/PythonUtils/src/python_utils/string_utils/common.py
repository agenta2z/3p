from enum import Enum
from typing import Iterable, Optional, Union, Tuple, List
import random
import string

from python_utils.common_objects.search_fallback_options import SearchFallbackOptions
from python_utils.common_utils.iter_helper import iter_, iter__
from python_utils.common_utils.typing_helper import solve_nested_singleton_tuple_list


class OccurrenceOptions(str, Enum):
    First = 'first'
    Last = 'last'
    All = 'all'


def random_string(length: int = 8, characters: Optional[str] = None) -> str:
    """
    Generates a random string of specified length.

    Args:
        length: The length of the random string to generate (default: 8).
        characters: The character set to use for generating the random string.
                   If None (default), uses alphanumeric characters (letters + digits).

    Returns:
        str: A randomly generated string of the specified length.

    Examples:
        >>> len(random_string())
        8
        >>> len(random_string(16))
        16
        >>> result = random_string(4, string.ascii_lowercase)
        >>> len(result) == 4 and all(c in string.ascii_lowercase for c in result)
        True
    """
    if characters is None:
        characters = string.ascii_letters + string.digits

    return ''.join(random.choices(characters, k=length))


def startswith_any(s: str, targets: Union[str, Iterable[str]]):
    """
    Checks if a string `s` starts with any of the target substrings specified
    in the `targets` iterable.

    Examples:
        >>> startswith_any("hello world", ["hello", "hi"])
        True
        >>> startswith_any("hello world", ["world", "foo"])
        False
        >>> startswith_any("hello world", "hello")
        True
    """
    return any(not target or s.startswith(target) for target in iter__(targets))


def endswith_any(s: str, targets: Union[str, Iterable[str]]):
    """
    Checks if a string `s` ends with any of the target substrings specified
    in the `targets` iterable.

    Examples:
        >>> endswith_any("hello world", ["world", "earth"])
        True
        >>> endswith_any("hello world", ["hello", "foo"])
        False
        >>> endswith_any("hello world", "world")
        True
    """
    return any(not target or s.endswith(target) for target in iter__(targets))


def contains_any(s: str, targets: Iterable[str], ignore_empty: bool = True) -> bool:
    """
    Checks if a string `s` contains any of the target substrings specified in the `targets` iterable.

    If the `ignore_empty` parameter is set to True (which is the default),
    the function will ignore any empty or None values in the targets iterable
    when checking for substrings. If `ignore_empty` is set to False,
    the function will include empty or None values in the check.

    The function returns True if any of the target substrings are found in the string s,
    and False otherwise.

    Examples:
        >>> contains_any("hello world", ["hello", "foo"])
        True
        >>> contains_any("hello world", ["foo", "bar"])
        False
        >>> contains_any("hello world", ["", "foo"], ignore_empty=True)
        False
    """
    if ignore_empty:
        return any(target in s for target in iter__(targets) if target)
    else:
        return any(target in s for target in iter__(targets) if target is not None)


def contains_all(s: str, targets: Iterable[str]) -> bool:
    """
    Checks if string `s` contains all of the target substrings.

    Examples:
        >>> contains_all("hello world", ["hello", "world"])
        True
        >>> contains_all("hello world", ["hello", "foo"])
        False
    """
    return all(target in s for target in iter__(targets) if target)


def contains_any_all(s: str, targets: Iterable[Union[Iterable[str], str]]):
    """
    Checks if string `s` contains all substrings from any of the target groups.

    Examples:
        >>> contains_any_all("hello world", [["hello", "world"], ["foo", "bar"]])
        True
        >>> contains_any_all("hello world", [["foo", "bar"], ["baz", "qux"]])
        False
    """
    return any(
        (contains_all(s, target)) for target in iter__(targets) if target
    )


def find_all(s: str, substr: str) -> Iterable[int]:
    """
    Finds all occurrences of a substring in a string.

    Args:
        s: The string to search in.
        substr: The substring to find.

    Yields:
        int: The index of each occurrence of the substring.

    Examples:
        >>> list(find_all("hello hello hello", "hello"))
        [0, 6, 12]
        >>> list(find_all("abcabc", "bc"))
        [1, 4]
        >>> list(find_all("hello", "xyz"))
        []
    """
    i = s.find(substr)
    while i != -1:
        yield i
        i = s.find(substr, i + 1)


def join_(*strs, sep: str = '', last_sep: str = None, ignore_none_or_empty=True) -> str:
    """
    Join multiple strings with a specified separator and an optional last separator.

    Args:
        strs: Multiple string arguments to join.
        sep (str): Separator used to join the strings. Defaults to ''.
        last_sep (str): Separator used before the last string. Defaults to None.
        ignore_none_or_empty (bool): If True, ignore None or empty strings. Defaults to True.

    Returns:
        str: The joined string.

    Examples:
        >>> join_('apple', 'banana', 'cherry', sep=', ')
        'apple, banana, cherry'

        >>> join_('apple', None, 'cherry', sep=', ', ignore_none_or_empty=True)
        'apple, cherry'

        >>> join_('apple', '', 'cherry', sep=', ', ignore_none_or_empty=True)
        'apple, cherry'

        >>> join_('apple', '', 'cherry', sep=', ', ignore_none_or_empty=False)
        'apple, , cherry'

        >>> join_('apple', 'banana', 'cherry', sep=', ', last_sep=' and ')
        'apple, banana and cherry'

        >>> join_('apple', None, 'cherry', sep=', ', last_sep=' and ', ignore_none_or_empty=True)
        'apple and cherry'

        >>> join_('apple', None, 'cherry', sep=', ', last_sep=' and ', ignore_none_or_empty=False)
        'apple,  and cherry'
    """
    strs = solve_nested_singleton_tuple_list(strs)
    if not strs:
        return ''

    if len(strs) == 1:
        if strs[0] is not None:
            return f'{strs[0]}'
        else:
            return ''
    else:
        if last_sep is not None and last_sep != sep:
            last_str = strs[-1]
            strs = strs[:-1]
        else:
            last_str = None

        if ignore_none_or_empty:
            joint_str = sep.join((
                f'{x}' for x in strs
                if x is not None and x != ''
            ))
        else:
            joint_str = sep.join((
                ('' if x is None else f'{x}') for x in strs
            ))

        if (
                (last_str is not None) and
                (not ignore_none_or_empty or last_str)
        ):
            return joint_str + last_sep + last_str
        else:
            return joint_str


def count_uppercase(s):
    """
    Counts the number of uppercase characters in a string.

    Examples:
        >>> count_uppercase("Hello World")
        2
        >>> count_uppercase("HELLO")
        5
        >>> count_uppercase("hello")
        0
    """
    return sum(1 for c in s if c.isupper())


def count_lowercase(s):
    """
    Counts the number of lowercase characters in a string.

    Examples:
        >>> count_lowercase("Hello World")
        8
        >>> count_lowercase("hello")
        5
        >>> count_lowercase("HELLO")
        0
    """
    return sum(1 for c in s if c.islower())


def cut_before_first(
        text: str,
        target: str,
        keep_target: bool,
        lstrip: Union[str, bool] = True,
        return_empty_if_target_not_found: bool = False
) -> str:
    """
    Cuts the text before the first occurrence of a target string.

    Args:
        text (str): The input string.
        target (str): The target substring to cut before.
        keep_target (bool): If True, the target is included in the result.
                            If False, the target is excluded from the result.
        lstrip (Union[str, bool]): Specifies characters to remove from the left of the result.
                                   If True, removes leading whitespace. If a string, removes specified characters.
        return_empty_if_target_not_found (bool): Returns an empty string if the target is not found.

    Returns:
        str: The text after the first occurrence of the target, optionally including the target
             and with leading characters stripped as specified.

    Examples:
        >>> text = "This is a sample text with target word in it."

        # Basic usage, cutting before " is" and excluding the target
        >>> cut_before_first(text, " is", keep_target=False)
        'a sample text with target word in it.'

        # Including the target "target" in the result
        >>> cut_before_first(text, "target", keep_target=True)
        'target word in it.'

        # Excluding the target "target" in the result
        >>> cut_before_first(text, "target", keep_target=False)
        'word in it.'

        # Target not found in text; returns the original text
        >>> cut_before_first(text, "not_in_text", keep_target=True)
        'This is a sample text with target word in it.'

        # Stripping specific leading characters after cutting
        >>> cut_before_first("$$$Hello, World!", "Hello", keep_target=True, lstrip='$')
        'Hello, World!'

        # Stripping whitespace only after cutting
        >>> cut_before_first("    Text with spaces before target.", "with", keep_target=True, lstrip=True)
        'with spaces before target.'

    """
    # Find the position of the target string
    position = text.find(target)

    # If the target is not found, return the original text
    if position != -1:
        # Cut text starting from the target position (keeping or excluding target)
        text = text[position if keep_target else position + len(target):]
    elif return_empty_if_target_not_found:
        return ''

    # Apply lstrip as specified
    return strip_(text, lstrip=lstrip, rstrip=False)


def cut_after_last(
        text: str,
        target: str,
        keep_target: bool = False,
        rstrip: Union[str, bool] = True,
        return_empty_if_target_not_found: bool = False
) -> str:
    """
    Cuts the text after the last occurrence of a target string.

    Args:
        text (str): The input string.
        target (str): The target substring to cut after.
        keep_target (bool): If True, the target is included in the result.
                            If False, the target is excluded from the result.
        rstrip (Union[str, bool]): Specifies characters to remove from the right of the result.
                                   If True, removes trailing whitespace. If a string, removes specified characters.
        return_empty_if_target_not_found (bool): Returns an empty string if the target is not found.

    Returns:
        str: The text up to the last occurrence of the target, optionally including the target
             and with trailing characters stripped as specified.

    Examples:
        >>> text = "This is a sample text with target word in it and another target here."

        # Basic usage, cutting after the last "target" and including the target
        >>> cut_after_last(text, "target", keep_target=True)
        'This is a sample text with target word in it and another target'

        # Cutting after the last "target" and excluding the target
        >>> cut_after_last(text, "target", keep_target=False)
        'This is a sample text with target word in it and another'

        # Target not found in text; returns the original text
        >>> cut_after_last(text, "not_in_text", keep_target=True)
        'This is a sample text with target word in it and another target here.'

        # Cutting after " in" and excluding it, followed by stripping whitespace
        >>> cut_after_last("This is a sample text with target word in it ", " in", keep_target=False, rstrip=True)
        'This is a sample text with target word'

        # Cutting after "target" and stripping specific characters
        >>> cut_after_last("Hello! World!!!", "Hello!", keep_target=True, rstrip="!")
        'Hello'
    """
    # Find the position of the last occurrence of the target string
    position = text.rfind(target)

    # If the target is not found, return the original text
    if position != -1:
        # Cut text up to the target position (keeping or excluding target)
        text = text[:position + (len(target) if keep_target else 0)]
    elif return_empty_if_target_not_found:
        return ''

    # Apply rstrip as specified
    return strip_(text, lstrip=False, rstrip=rstrip)


def remove_first_line(
        text: str,
        lstrip: Union[str, bool] = True,
        return_empty_for_single_line: bool = True
) -> str:
    """
    Removes the first line from a multi-line string using cut_before_first.

    Args:
        text (str): The input string with multiple lines.
        lstrip (Union[str, bool]): Specifies characters to remove from the start of the result.
                                   If True, removes leading whitespace. If a string, removes specified characters.
        return_empty_for_single_line (bool): If True, and there is only one line in text, then returns an empty string.

    Returns:
        str: The string without the first line, optionally stripped of leading characters.

    Examples:
        >>> text = "First line\\nSecond line\\nThird line"
        >>> remove_first_line(text)
        'Second line\\nThird line'

        >>> remove_first_line("   First line\\nSecond line\\nThird line", lstrip=True)
        'Second line\\nThird line'

        >>> remove_first_line("$$$First line\\nSecond line\\nThird line", lstrip="$")
        'Second line\\nThird line'

        >>> remove_first_line("Single line")
        ''

        >>> remove_first_line("Single line", return_empty_for_single_line=False)
        'Single line'
    """
    return cut_before_first(
        text, "\n",
        keep_target=False,
        lstrip=lstrip,
        return_empty_if_target_not_found=return_empty_for_single_line
    )


def remove_last_line(
        text: str,
        rstrip: Union[str, bool] = True,
        return_empty_for_single_line: bool = True
) -> str:
    """
    Removes the last line from a multi-line string using cut_after_last.

    Args:
        text (str): The input string with multiple lines.
        rstrip (Union[str, bool]): Specifies characters to remove from the end of the result.
                                   If True, removes trailing whitespace. If a string, removes specified characters.
        return_empty_for_single_line (bool): If True, and there is only one line in text, then returns an empty string.

    Returns:
        str: The string without the last line, optionally stripped of trailing characters.

    Examples:
        >>> text = "First line\\nSecond line\\nThird line"
        >>> remove_last_line(text)
        'First line\\nSecond line'

        >>> remove_last_line("First line\\nSecond line\\n   Third line   ", rstrip=True)
        'First line\\nSecond line'

        >>> remove_last_line("First line\\nSecond line!\\nThird line!!!", rstrip="!")
        'First line\\nSecond line'

        >>> remove_last_line("Single line")
        ''

        >>> remove_last_line("Single line", return_empty_for_single_line=False)
        'Single line'
    """
    return cut_after_last(
        text, "\n",
        keep_target=False,
        rstrip=rstrip,
        return_empty_if_target_not_found=return_empty_for_single_line
    )


def cut(
        s: str,
        cut_before_first: str = None,
        cut_before_last: str = None,
        cut_after_first: str = None,
        cut_after_last: str = None,
        keep_cut_before: bool = False,
        keep_cut_after: bool = False
) -> str:
    """
    Cuts parts of a string based on specified substrings, with options to retain or exclude
    the specified cut points.

    Args:
        s (str): The original string to cut.
        cut_before_first (str, optional): Substring before which the cut will be made starting from the first occurrence.
        cut_before_last (str, optional): Substring before which the cut will be made starting from the last occurrence.
        cut_after_first (str, optional): Substring after which the cut will be made starting from the first occurrence.
        cut_after_last (str, optional): Substring after which the cut will be made starting from the last occurrence.
        keep_cut_before (bool, optional): Whether to keep the substring specified by cut_before_* in the result. Defaults to False.
        keep_cut_after (bool, optional): Whether to keep the substring specified by cut_after_* in the result. Defaults to False.

    Returns:
        str: The modified string after applying the cuts.

    Examples:
        >>> cut("hello world example", cut_before_first="hello", keep_cut_before=True)
        'hello world example'

        >>> cut("hello world example", cut_before_first="hello")
        ' world example'

        >>> cut("hello world example", cut_after_first="world")
        'hello '

        >>> cut("hello world example", cut_after_last="world", keep_cut_after=True)
        'hello world'

        >>> cut("hello world example", cut_before_last="world", keep_cut_before=True, cut_after_first="hello", keep_cut_after=False)
        'world example'

        >>> cut("bla bla bla <Decision> my decision </Decision> bla bla bla", cut_after_first="</Decision>", keep_cut_after=True)
        'bla bla bla <Decision> my decision </Decision>'
    """
    if cut_before_first is not None:
        pos = s.find(cut_before_first)
        if pos != -1:
            s = s[(pos + (0 if keep_cut_before else len(cut_before_first))):]

    if cut_before_last is not None:
        pos = s.rfind(cut_before_last)
        if pos != -1:
            s = s[(pos + (0 if keep_cut_before else len(cut_before_last))):]

    if cut_after_first is not None:
        pos = s.find(cut_after_first)
        if pos != -1:
            s = s[:(pos + (len(cut_after_first) if keep_cut_after else 0))]

    if cut_after_last is not None:
        pos = s.rfind(cut_after_last)
        if pos != -1:
            s = s[:(pos + (len(cut_after_last) if keep_cut_after else 0))]

    return s


def strip_(s: str, lstrip: Union[str, bool] = True, rstrip: Union[str, bool] = True) -> str:
    """
    This function `strip_` is a flexible string manipulation function that allows selective removal of leading (left) and/or
    trailing (right) characters from a given string `s`. The user can specify which sides to strip and which characters to remove.

    Args:
        s (str): The input string from which characters will be removed.
        lstrip (Union[str, bool]): A boolean flag indicating whether to remove leading characters from the left side of the string.
            If a string is provided, it removes characters specified in the string.
        rstrip (Union[str, bool]): A boolean flag indicating whether to remove trailing characters from the right side of the string.
            If a string is provided, it removes characters specified in the string.

    Returns:
        str: The modified string after removing the specified characters from the selected sides.

    Examples:
        >>> input_str = "   Hello, World!   "
        >>> strip_(input_str, lstrip=True, rstrip=True)
        'Hello, World!'

        >>> input_str = "   Hello, World!   "
        >>> strip_(input_str, lstrip=True, rstrip=False)
        'Hello, World!   '

        >>> input_str = "xxHello, World!xx"
        >>> strip_(input_str, lstrip='x', rstrip='x')
        'Hello, World!'
    """
    if s:
        if lstrip is True:
            s = s.lstrip()
        elif isinstance(lstrip, str) and len(lstrip) > 0:
            s = s.lstrip(lstrip)

        if rstrip is True:
            s = s.rstrip()
        elif isinstance(rstrip, str) and len(rstrip) > 0:
            s = s.rstrip(rstrip)

    return s


def index__(
        s: str,
        search: Union[str, Iterable[str]],
        start: int = 0,
        end: int = None,
        return_at_first_match: bool = True,
        return_end: bool = False,
        search_fallback_option: Union[str, SearchFallbackOptions] = SearchFallbackOptions.RaiseError
) -> Union[int, List[int]]:
    """
    Find the index or indices of a substring or an ordered sequence of substrings within a string.

    The search is performed on the slice ``s[start:end]`` (with ``end`` defaulting to ``len(s)`` if not provided).
    The function supports two modes for each type of search target:

      1. **Single substring (atomic) search:**
         If ``search`` is a string, the function searches for occurrences of that substring within ``s``.
         - When ``return_at_first_match`` is True, only the first occurrence is returned.
         - When False, all occurrences are returned.

      2. **Iterable search:**
         If ``search`` is an iterable of substrings, then:
         - With ``return_at_first_match=True``, the function returns the earliest occurrence among the substrings.
         - With ``return_at_first_match=False``, it returns all occurrences (found independently for each substring)
           in a combined, sorted list.

    In both modes, if ``return_end`` is True, the function returns a tuple (or a list of tuples) of the form
    ``(start_index, end_index)``, where ``end_index`` is the index immediately after the matched substring.
    Otherwise, only the start index (or list of start indexes) is returned.

    The fallback behavior when no match is found is controlled by ``search_fallback_option``:

      - ``SearchFallbackOptions.RaiseError``: raises a ``ValueError``.
      - ``SearchFallbackOptions.Empty``: returns ``-1`` (or ``(-1, -1)``) in single-match mode or an empty list in list mode.
      - ``SearchFallbackOptions.EOS``: returns ``len(s)`` (or ``(len(s), len(s))``) in single-match mode or a list
        containing ``len(s)`` (or ``[(len(s), len(s))]``) in list mode.

    Args:
        s (str): The string to search within.
        search (Union[str, Iterable[str]]):
            The target substring or an iterable of substrings to find.
        start (int, optional): The starting index for the search. Defaults to 0.
        end (int, optional): The ending index (exclusive) for the search. Defaults to None, interpreted as ``len(s)``.
        return_at_first_match (bool, optional):
            - If True, return only the earliest matching index.
            - If False, return all matching indices.
            Defaults to False.
        return_end (bool, optional):
            - If True, return a tuple (or list of tuples) of ``(start_index, end_index)``.
            - If False, return only the start index (or list of start indexes).
            Defaults to False.
        search_fallback_option (Union[str, SearchFallbackOptions], optional):
            The fallback behavior if no match is found:
              - ``SearchFallbackOptions.RaiseError``: raise a ValueError.
              - ``SearchFallbackOptions.Empty``: return -1 (or (-1, -1)) in single-match mode or an empty list in list mode.
              - ``SearchFallbackOptions.EOS``: return len(s) (or (len(s), len(s))) in single-match mode or a list containing len(s) (or [(len(s), len(s))]) in list mode.
            Defaults to ``SearchFallbackOptions.RaiseError``.

    Returns:
        Union[int, List[int], Tuple[int, int], List[Tuple[int, int]]]:
            - If ``return_at_first_match`` is True, returns a single index (or tuple) for the earliest match.
            - Otherwise, returns a list of all matching indices (or tuples if ``return_end`` is True).

    Raises:
        ValueError: If no match is found and ``search_fallback_option`` is set to ``SearchFallbackOptions.RaiseError``.

    Notes:
        - For a single substring, the function uses ``s.find()``.
        - For iterable searches with ``return_at_first_match=False``, each substring is searched independently;
          the results are merged and sorted by index.
        - Fallback behavior is applied uniformly if no match is found.

    Examples:
        Single Substring Search:
        >>> index__("hello world", "world")
        6

        Sequential Substrings Search:
        >>> index__("find the needle in the haystack", ["the", "needle"], return_end=True)
        (5, 8)

        Fallback Options:
        >>> index__("hello world", "bye", search_fallback_option='eos')
        11

        >>> index__("hello world", "bye", search_fallback_option=SearchFallbackOptions.Empty)
        -1

        Handling Iterables:
        >>> index__("looking for multiple words in a sentence", ["multiple", "words"], return_end=True)
        (12, 20)

        >>> index__("phrase with missing parts", ["missing", "parts"], search_fallback_option=SearchFallbackOptions.EOS, return_end=True)
        (12, 19)

        >>> index__("no such substrings", ["no", "such", "substrings"], search_fallback_option=SearchFallbackOptions.Empty)
        0

        >>> index__("hello world", "o", return_at_first_match=False, search_fallback_option=SearchFallbackOptions.EOS)
        [4, 7]

        >>> index__("hello world", "bye", return_at_first_match=False, search_fallback_option=SearchFallbackOptions.Empty)
        []
    """

    if end is None:
        end = len(s)
    else:
        end = min(end, len(s))

    def _find_all_occurrences(sub: str) -> List[int]:
        """Helper: return a list of all start indices of 'sub' in s[start:end]."""
        indices = []
        pos = start
        while True:
            idx = s.find(sub, pos, end)
            if idx == -1:
                break
            indices.append(idx)
            pos = idx + 1
        return indices

    def _fallback_single() -> int:
        if search_fallback_option == SearchFallbackOptions.RaiseError:
            raise ValueError(f"{search} not found in string.")
        elif search_fallback_option == SearchFallbackOptions.EOS:
            return len(s)
        else:
            return -1

    def _fallback_tuple() -> Tuple[int, int]:
        if search_fallback_option == SearchFallbackOptions.RaiseError:
            raise ValueError(f"{search} not found in string.")
        elif search_fallback_option == SearchFallbackOptions.EOS:
            return len(s), len(s)
        else:
            return -1, -1

    def _fallback_list() -> List:
        if search_fallback_option == SearchFallbackOptions.RaiseError:
            raise ValueError(f"{search} not found in string.")
        elif search_fallback_option == SearchFallbackOptions.EOS:
            return [len(s)] if not return_end else [(len(s), len(s))]
        else:
            return []  # empty list fallback

    if isinstance(search, str):
        if return_at_first_match:
            idx = s.find(search, start, end)
            if idx == -1:
                return _fallback_tuple() if return_end else _fallback_single()
            return (idx, idx + len(search)) if return_end else idx
        else:
            indices = _find_all_occurrences(search)
            if not indices:
                return _fallback_list()
            return [(i, i + len(search)) for i in indices] if return_end else indices
    else:
        if return_at_first_match:
            best_idx = None
            best_result = None
            for sub in search:
                idx = s.find(sub, start, end)
                if idx != -1 and (best_idx is None or idx < best_idx):
                    best_idx = idx
                    best_result = (idx, idx + len(sub))
            if best_idx is not None:
                return best_result if return_end else best_idx
            else:
                return _fallback_tuple() if return_end else _fallback_single()
        else:
            results = []
            for sub in search:
                occ = _find_all_occurrences(sub)
                if return_end:
                    occ = [(i, i + len(sub)) for i in occ]
                results.extend(occ)

            if not results:
                return _fallback_list()

            return sorted(results)


def index_pair(
        s: str,
        search1: str,
        search2: str,
        start: int = 0,
        search_fallback_option: Union[str, SearchFallbackOptions] = SearchFallbackOptions.RaiseError
) -> Tuple[int, int]:
    """
    Finds the indices in the string `s` marking the end of the first occurrence of `search1` and the start of the
    subsequent occurrence of `search2`. The function provides flexible handling for cases where `search2` is not found.

    Args:
        s: The string to search within.
        search1: The substring whose end marks the starting index of the result.
        search2: The substring whose start marks the ending index of the result.
        start: The index in `s` to start the search from. Defaults to 0.
        search_fallback_option: Determines the behavior when either `search1` or `search2` is not found:
            - SearchFallbackOptions.EOS: If `search1` or `search2` is not found, return the end of the string (`len(s)`)
              as the respective index.
            - SearchFallbackOptions.Empty: If `search1` or `search2` is not found, return the start index or the last valid
              search position as the respective index.
            - SearchFallbackOptions.RaiseError: Raise a ValueError if either `search1` or `search2` is not found. This is
              the default behavior.
    Returns:
        A tuple of two integers (start, end) representing the indices in `s`. The start index is at the end of the
        first occurrence of `search1`, and the end index is at the start of the subsequent occurrence of `search2`.

    Raises:
        ValueError: If either `search1` is not found in `s`, or `search2` is not found and `search_fallback_option`
                    is set to raise an error.

    Examples:
        >>> s = "This string is a sample string for testing."
        >>> index_pair(s, "is", "sample")
        (4, 17)

        >>> index_pair(s, "sample", "string", 10)
        (23, 24)

        >>> index_pair(s, "This", "not found", search_fallback_option=SearchFallbackOptions.EOS)
        (4, 43)

        >>> index_pair(s, "not there", "string", search_fallback_option=SearchFallbackOptions.Empty)
        (43, 43)

        >>> index_pair(s, "is", "not found", search_fallback_option=SearchFallbackOptions.RaiseError)
        Traceback (most recent call last):
            ...
        ValueError: not found not found in string.
    """
    try:
        _, start = index__(s, search1, start, return_end=True)
    except ValueError as e:
        if search_fallback_option == SearchFallbackOptions.RaiseError.RaiseError.value:
            raise e
        else:
            start = len(s)
            return start, start

    try:
        end = index__(s, search2, start)
    except ValueError as e:
        if search_fallback_option == SearchFallbackOptions.RaiseError.EOS.value:
            end = len(s)
        elif search_fallback_option == SearchFallbackOptions.RaiseError.Empty.value:
            end = start
        else:
            raise e
    return start, end


def extract_between(
        s: str,
        search1: Union[str, List[str], Tuple[str, ...]],
        search2: Union[str, List[str], Tuple[str, ...]],
        allow_search1_not_found: bool = False,
        allow_search2_not_found: bool = False,
        keep_search1: bool = False,
        keep_search2: bool = False,
        return_matching_search1_index: bool = False,
        search1_use_last_occurrence: bool = False,
        search2_use_last_occurrence: bool = False
) -> Union[Optional[str], Tuple[Optional[str], int]]:
    """
    Extracts a substring from the string `s`, located between one or more possible
    `search1` delimiters and one or more possible `search2` delimiters. Optionally
    returns the index in `search1` that was matched.

    **How it works**:
      1. `search1` can be a single string or a list/tuple of strings. The function looks
         for each possible delimiter in order and uses the **first** one found (or **last**
         if `search1_use_last_occurrence=True`). If none is found, it either returns `None`
         (if `allow_search1_not_found=False`) or starts at index 0 (if `allow_search1_not_found=True`).
      2. `search2` can be a single string or a list/tuple of strings. Similarly, the function
         uses the **first** match found after the `search1` start position (or **last** if
         `search2_use_last_occurrence=True`). If none is found, it either returns `None`
         (if `allow_search2_not_found=False`) or uses the end of the string
         (if `allow_search2_not_found=True`).
      3. If both `search1` and `search2` are lists/tuples, and `search1` was found at index
         `i`, then the function attempts to use `search2[i]` for the end delimiter. It then
         checks if `search2[i]` itself is a nested list/tuple; if so, it iterates that set
         of possible delimiters in order.
      4. By default, the function returns a **string** (or `None` if not found). If
         `return_matching_search1_index=True`, it returns a **tuple** of:
         `(extracted_substring_or_None, matched_search1_index_or_-1)`.

    Args:
        s (str):
            The string from which to extract the substring.

        search1 (Union[str, List[str], Tuple[str, ...]]):
            One or more substrings that can mark where extraction should start.
            - If a single string, only that delimiter is checked.
            - If a list/tuple, each is tried in order until the first match is found.
            - If empty, extraction starts from index 0.

        search2 (Union[str, List[str], Tuple[str, ...]]):
            One or more substrings that can mark where extraction should end.
            - If a single string, only that delimiter is checked.
            - If a list/tuple, each is tried in order until the first match is found.
            - If empty, extraction ends at the end of `s`.

        allow_search1_not_found (bool):
            - If `True`, allows extraction to start at index 0 if no `search1` is found.
            - If `False`, returns `None` (or `(None, -1)`) if no `search1` is found.

        allow_search2_not_found (bool):
            - If `True`, allows extraction to end at the end of `s` if no `search2` is found.
            - If `False`, returns `None` (or `(None, matched_search1_index)`) if no `search2` is found.

        keep_search1 (bool):
            - If `True`, includes the matched `search1` in the extracted substring.
            - If `False`, starts the result immediately after `search1`.

        keep_search2 (bool):
            - If `True`, includes the matched `search2` in the extracted substring.
            - If `False`, ends the result right before `search2`.

        return_matching_search1_index (bool):
            - If `False`, the function returns a string or `None`.
            - If `True`, the function returns a tuple `(result, matched_index)`, where
              `matched_index` is the index of the matched `search1` in its list/tuple, or
              `-1` if none was matched (i.e., if search1 was not found and
              `allow_search1_not_found=True`).

        search1_use_last_occurrence (bool):
            - If `False` (default), uses str.find() to locate the first occurrence of `search1`.
            - If `True`, uses str.rfind() to locate the last occurrence of `search1`.

        search2_use_last_occurrence (bool):
            - If `False` (default), uses str.find() to locate the first occurrence of `search2`
              after the `search1` position.
            - If `True`, uses str.rfind() to locate the last occurrence of `search2` after
              the `search1` position.

    Returns:
        Union[Optional[str], Tuple[Optional[str], int]]:
            - If `return_matching_search1_index=False`, returns either the extracted
              substring (str) or `None`.
            - If `return_matching_search1_index=True`, returns a tuple of the extracted
              substring (or `None`) and the matched `search1` index (or `-1` if not matched).

    Examples:
        # Single search1 & search2, substring in the middle
        >>> extract_between("Hello world, this is an example.", "Hello ", ", this")
        'world'

        # Keep the search1 delimiter in the result
        >>> extract_between("Hello world, this is an example.", "Hello ", ", this", keep_search1=True)
        'Hello world'

        # Keep the search2 delimiter in the result
        >>> extract_between("Hello world, this is an example.", "Hello ", ", this", keep_search2=True)
        'world, this'

        # Keep both delimiters
        >>> extract_between("Find the middle word!", "Find the ", " word", keep_search1=True, keep_search2=True)
        'Find the middle word'

        # If search1 is not found, but allowed, start from the beginning
        >>> extract_between("Only one marker here!", ["missing"], "marker", allow_search1_not_found=True)
        'Only one '

        # If search2 is not found, but allowed, end at the string's end
        >>> extract_between("Start marker but no end", "Start ", ["missing"], allow_search2_not_found=True)
        'marker but no end'

        # If neither start nor end is found, returns None
        >>> extract_between("Neither start nor end", "absent", "nonexistent") is None
        True

        # Multiple possible search1 delimiters (picks the FIRST found)
        >>> extract_between("abc startX def 123 startY 456", ["startX", "startY"], "123")
        ' def '
        >>> extract_between("abc startX def 123 startY 456", ["startY", "startX"], "123") is None
        True

        # Demonstrating parallel lists for search1/search2
        >>> extract_between("abc startX hello endX 999 endY", ["startY", "startX"], ["endY", "endX"])
        ' hello '
        >>> extract_between("abc startX hello endX 999 endY", ["startY", "startX"], ["endY", None])
        ' hello endX 999 endY'

        # Returning the matched search1 index
        >>> extract_between("abc startX def 123 startY 456", ["startX", "startY"], "123", return_matching_search1_index=True)
        (' def ', 0)
        >>> extract_between("abc startX hello endX 999 endY", ["startY", "startX"], ["endY", None], return_matching_search1_index=True)
        (' hello endX 999 endY', 1)
    """
    # region STEP1: find search1
    start_index = matched_search1_index = -1
    if search1:
        for matched_search1_index, _search1 in enumerate(iter_(search1, non_atom_types=(List, Tuple))):
            if _search1:
                if search1_use_last_occurrence:
                    sep_start_index = s.rfind(_search1)
                else:
                    sep_start_index = s.find(_search1)
                if sep_start_index != -1:
                    start_index = (
                        sep_start_index
                        if keep_search1
                        else sep_start_index + len(_search1)
                    )
                    break

        # If no match found at all
        if start_index == -1:
            if not allow_search1_not_found:
                if return_matching_search1_index:
                    return None, -1
                else:
                    return None
            matched_search1_index = -1
            start_index = 0  # Start from beginning
    else:
        # No search1 given, start from beginning
        start_index = 0
    # endregion

    # region STEP2: find search2

    # If we matched search1 at a certain index, and search2 is a list/tuple, pick the parallel search2
    if matched_search1_index != -1 and isinstance(search2, (List, Tuple)) and len(search2) > matched_search1_index:
        search2 = search2[matched_search1_index]

    if search2:
        end_index = -1
        for _search2 in iter_(search2, non_atom_types=(List, Tuple)):
            if _search2:
                if search2_use_last_occurrence:
                    sep_end_index = s.rfind(_search2, start_index)
                else:
                    sep_end_index = s.find(_search2, start_index)
                if sep_end_index != -1:
                    end_index = (
                        sep_end_index + len(_search2)
                        if keep_search2
                        else sep_end_index
                    )
                    break

        # No search2 given, end at string's end
        if end_index == -1:
            if not allow_search2_not_found:
                if return_matching_search1_index:
                    return None, matched_search1_index
                else:
                    return None
            end_index = len(s)  # End at string's end if allowed
    else:
        end_index = len(s)
    # endregion

    # Return the substring between the calculated start and end indices
    if return_matching_search1_index:
        return s[start_index:end_index], matched_search1_index
    else:
        return s[start_index:end_index]


def extract_multiple_between(s: str, start_tag: str, end_tag: str) -> List[str]:
    """
    Extracts substrings from a string `s` that are located between two substrings `start_tag` and `end_tag`.

    Args:
    s (str): The string from which to extract the substrings.
    start_tag (str): The substring after which the extraction should start.
    end_tag (str): The substring before which the extraction should end.

    Returns:
    List[str]: A list of extracted substrings.

    Examples:
    >>> extract_multiple_between("text <example>example1</example> text <example>example2</example>", "<example>", "</example>")
    ['example1', 'example2']
    >>> extract_multiple_between("No end substring here", "start", "end")
    []
    """
    substrings = []
    start_index = 0
    while True:
        start_index = s.find(start_tag, start_index)
        if start_index == -1:
            break
        end_index = s.find(end_tag, start_index)
        if end_index == -1:
            break
        substrings.append(s[(start_index + len(start_tag)): end_index])
        start_index = end_index + len(end_tag)
    return substrings


def extract_between_(
        s: str,
        search1,
        search2,
        start: int = 0,
        search_fallback_option: Union[str, SearchFallbackOptions] = SearchFallbackOptions.RaiseError
) -> str:
    """
    Extracts a substring from a given string, located between two specified substrings.

    This function identifies the segments of the string `s` that occur after `search1` and before `search2`,
    then returns the substring located between these segments. If `search2` is not found and
    `eos_fallback_for_search2` is true, it extracts until the end of the string `s`.

    Args:
        s: The string to extract from.
        search1: The substring after which extraction should start.
        search2: The substring before which extraction should end.
        start: The index to start the search from (defaults to 0).
        search_fallback_option: Determines the behavior when either `search1` or `search2` is not found:
            - SearchFallbackOptions.EOS: If `search1` or `search2` is not found, return the end of the string (`len(s)`)
              as the respective index.
            - SearchFallbackOptions.Empty: If `search1` or `search2` is not found, return the start index or the last valid
              search position as the respective index.
            - SearchFallbackOptions.RaiseError: Raise a ValueError if either `search1` or `search2` is not found. This is
              the default behavior.

    Returns:
        The extracted substring between `search1` and `search2`.

    Raises:
        ValueError: If either `search1` is not found in `s`, or `search2` is not found and `search_fallback_option`
                    is set to raise an error.


    Examples:
        >>> s = "This is a sample string for testing."
        >>> extract_between_(s, "This is", "string")
        ' a sample '

        >>> extract_between_(s, "sample", "testing", search_fallback_option=SearchFallbackOptions.EOS)
        ' string for '

        >>> extract_between_(s, "not found", "string")
        Traceback (most recent call last):
            ...
        ValueError: not found not found in string.

        >>> extract_between_(s, "This is", "not found", search_fallback_option='empty')
        ''
    """
    start_index, end_index = index_pair(s, search1, search2, start, search_fallback_option)
    return s[start_index:end_index]
