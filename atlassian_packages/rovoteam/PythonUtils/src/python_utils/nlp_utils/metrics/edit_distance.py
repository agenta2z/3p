import copy
import warnings

from attr import attrs, attrib

from python_utils.common_utils.iter_helper import max_len__
from python_utils.common_utils.map_helper import get_
from python_utils.common_utils.typing_helper import is_str
from python_utils.nlp_utils.common import Languages
from python_utils.string_utils.common import startswith_any, endswith_any, contains_any
from python_utils.nlp_utils.string_sanitization import string_sanitize, StringSanitizationOptions, StringSanitizationConfig, remove_common_tokens_except_for_sub_tokens
from python_utils.string_utils.tokenization import tokenize

try:
    from Levenshtein import distance
except:
    warnings.warn("failed to import 'Levenshtein'")
from typing import Callable, Union, Iterable, Tuple, Any


def regular_normalized_edit_distance(s1: str, s2: str) -> float:
    """
    Calculates the normalized edit distance (Levenshtein distance) between two strings.

    The normalized edit distance is calculated as the Levenshtein distance divided by the
    length of the longest string. The result is a float value between 0 and 1, where 0
    means the strings are identical, and 1 means they have no common characters.

    Args:
        s1: The first string to compare.
        s2: The second string to compare.

    Returns:
        A float representing the normalized edit distance between the two input strings.

    Examples:
        >>> regular_normalized_edit_distance("kitten", "sitting")
        0.42857142857142855
        >>> regular_normalized_edit_distance("hello", "hello")
        0.0
        >>> regular_normalized_edit_distance("example", "exemplar")
        0.375
    """
    return distance(s1, s2) / max(len(s1), len(s2))


def regular_edit_distance_based_similarity(s1: str, s2: str) -> float:
    """
    Calculates the similarity between two strings based on their normalized edit distance
    (Levenshtein distance).

    The similarity score is calculated as 1 minus the normalized edit distance, resulting
    in a float value between 0 and 1, where 0 means the strings have no common characters,
    and 1 means they are identical.

    Args:
        s1: The first string to compare.
        s2: The second string to compare.

    Returns:
        A float representing the similarity between the two input strings.

    Examples:
        >>> regular_edit_distance_based_similarity("kitten", "sitting")
        0.5714285714285714
        >>> regular_edit_distance_based_similarity("hello", "hello")
        1.0
        >>> regular_edit_distance_based_similarity("example", "exemplar")
        0.625
    """
    return 1 - regular_normalized_edit_distance(s1, s2)


def equals_in_tokens(
        str1: str,
        str2: str,
        tokenizer=None
) -> bool:
    return (
            str1 == str2 or
            sorted(tokenize(str1, tokenizer)) == sorted(tokenize(str2, tokenizer))
    )


def _upweight_first_last_chrs(
        s: str,
        upweight_first_chr: Union[int, bool],
        upweight_last_chr: Union[int, bool]
) -> str:
    if upweight_first_chr:
        if isinstance(upweight_first_chr, bool) or upweight_first_chr == 1:
            s = s[0] + s
        elif isinstance(upweight_first_chr, int):
            s = ''.join([s[0]] * (upweight_first_chr - 1)) + s

    if upweight_last_chr:
        if isinstance(upweight_last_chr, bool) or upweight_last_chr == 1:
            s = s + s[-1]
        elif isinstance(upweight_last_chr, int):
            s = s + ''.join([s[0]] * (upweight_last_chr - 1))

    return s


PreDefinedStartComparisonWeights = {
    Languages.English: (
        (
            (('a', 'e', 'i', 'o', 'u'), None),
            1.2,
            3
        ),
        (
            ('a', 'i'),
            1.2,
            3
        ),
        (
            ('i', 'o'),
            1.2,
            3
        ),
        (
            ('i', 'u'),
            1.2,
            3
        ),
    )
}

PreDefinedEndComparisonWeights = {
    Languages.English: (
        (
            (('a', 'e', 'i', 'o', 'u'), None),
            1.1,
            3
        ),
        (
            ('a', 'i'),
            1.1,
            3
        ),
        (
            ('i', 'o'),
            1.1,
            3
        ),
        (
            ('i', 'u'),
            1.1,
            3
        ),
    )
}


def _get_start_comparison_weight(str1: str, str2: str, conflict_config):
    # Loop through the conflict configuration tuples:
    # - (_start1, _start2) are the substrings to compare at the start of the strings
    # - _weight is the weight associated with the matching substrings
    # - _range is the optional maximum range to compare at the start of the strings
    for (_start1, _start2), _weight, _range in conflict_config:
        if _range is not None:
            #  If the range is specified, the function checks if `str1` starts with the first
            #  substring and `str2` does not, and if `str2` starts with the second substring and
            #  `str1` does not, up to the specified range.
            _range = max(max_len__(_start1), max_len__(_start2), _range)
            if (
                    _start2 and
                    contains_any(str1[:_range], _start1) and
                    not contains_any(str2[:_range], _start1) and
                    (
                            not _start2 or
                            (
                                    contains_any(str2[:_range], _start2) and
                                    not contains_any(str1[:_range], _start2)
                            )
                    )
            ):
                return _weight
        else:
            # If the range is not specified, the function only checks if `str1` starts with the
            # first substring and `str2` does not, and if `str2` starts with the second substring
            # and `str1` does not. If a match is found, the weight associated with the matching
            # tuple is returned.
            if (
                    _start2 and
                    startswith_any(str1, _start1) and
                    not startswith_any(str2, _start1) and
                    (
                            not _start2 or
                            (
                                    startswith_any(str2, _start2) and
                                    not startswith_any(str1, _start2)
                            )
                    )
            ):
                return _weight


def get_start_comparison_weight(str1, str2, conflict_config) -> float:
    result = _get_start_comparison_weight(str1=str1, str2=str2, conflict_config=conflict_config)
    if result is None:
        result = _get_start_comparison_weight(str1=str2, str2=str1, conflict_config=conflict_config)
    if result is None:
        return 1.0
    return result


def _get_end_comparison_weight(str1, str2, conflict_config):
    for (_end1, _end2), _weight, _range in conflict_config:
        if _range is not None:
            _range = max(max_len__(_end1), max_len__(_end2), _range)
            if (
                    _end2 and
                    contains_any(str1[-_range:], _end1) and
                    not contains_any(str2[-_range:], _end1) and
                    (
                            not _end2 or
                            (
                                    contains_any(str2[-_range:], _end2) and
                                    not contains_any(str1[-_range:], _end2)
                            )
                    )
            ):
                return _weight
        else:
            if (
                    _end2 and
                    endswith_any(str1, _end1) and
                    not endswith_any(str2, _end1) and
                    (
                            not _end2 or
                            (
                                    endswith_any(str2, _end2) and
                                    not endswith_any(str1, _end2)
                            )
                    )
            ):
                return _weight


def get_end_comparison_weight(str1, str2, conflict_config):
    result = _get_end_comparison_weight(str1=str1, str2=str2, conflict_config=conflict_config)
    if result is None:
        result = _get_end_comparison_weight(str1=str2, str2=str1, conflict_config=conflict_config)
    if result is None:
        return 1.0
    return result


@attrs(slots=True)
class EditDistanceOptions:
    """
    A class to configure various options for weighting the edit distance (Levenshtein distance)
    between two strings.

    Attributes:
        no_distance_for_empty_str1: If True, returns 0 as the edit distance
            when the first string is empty.
        no_distance_for_empty_str2: If True, returns 0 as the edit distance
            when the second string is empty.
        min_length_for_distance: Returns 0 as the edit distance when both strings
            have a length less than the given value.
        min_length_for_distance_for_str1: Returns 0 as the edit distance when the first
            string has a length less than the given value.
        min_length_for_distance_for_str2: Returns 0 as the edit distance when the second
            string has a length less than the given value.
        weight_distance_if_strs_have_common_start: If set to a non-zero float value,
            weights the edit distance when the input strings have a common starting substring.
        str_common_start_size: The size of the common starting substring
            required to enable weighting by `weight_distance_if_strs_have_common_start`.
        weight_distance_if_str1_is_substr: If set to a non-zero float value, weights the
            edit distance when the first string is a substring of the second string.
        weight_distance_if_str2_is_substr: If set to a non-zero float value, weights the
            edit distance when the second string is a substring of the first string.
        min_str_length_to_enable_substr_weight: The minimum length of the input strings required
            to enable weighting by `weight_distance_if_str1_is_substr`
            and `weight_distance_if_str2_is_substr`.

        weight_distance_for_short_strs: If set to a non-zero float value, weights the edit distance
            for short input strings.
        max_str_length_to_enable_short_str_weight: The maximum length of the input strings required
            to enable weighting by `weight_distance_for_short_strs`.
        requires_same_first_chr_to_enable_short_str_weight: If True, requires the first characters
            of the input strings to be the same to enable weighting
            by `weight_distance_for_short_strs`.
    """

    no_distance_for_empty_str1 = attrib(type=bool, default=False)
    no_distance_for_empty_str2 = attrib(type=bool, default=False)
    min_length_for_distance = attrib(type=Union[int, bool], default=False)
    min_length_for_distance_for_str1 = attrib(type=Union[int, bool], default=False)
    min_length_for_distance_for_str2 = attrib(type=Union[int, bool], default=False)
    weight_distance_if_strs_have_common_start = attrib(type=Union[bool, float], default=False)
    str_common_start_size = attrib(type=int, default=3)
    min_str_common_start_to_enable_soft_weight = attrib(type=int, default=2)
    min_str_start_similarity_to_enable_soft_weight = attrib(type=float, default=0.55)
    weight_distance_if_str1_is_substr = attrib(type=Union[bool, float], default=False)
    weight_distance_if_str2_is_substr = attrib(type=Union[bool, float], default=False)
    weight_distance_if_str1_heads_str2 = attrib(type=Union[bool, float], default=False)
    weight_distance_if_str2_heads_str1 = attrib(type=Union[bool, float], default=False)
    weight_distance_if_str1_first_token_is_sub_str = attrib(type=Union[bool, float], default=False)
    weight_distance_if_str2_first_token_is_sub_str = attrib(type=Union[bool, float], default=False)
    min_str_length_to_enable_substr_weight = attrib(type=int, default=3)
    weight_distance_by_comparing_start = attrib(type=Iterable[Tuple[Tuple, float]], default=None)
    weight_distance_by_comparing_end = attrib(type=Iterable[Tuple[Tuple, float]], default=None)

    # region edit distance tweak for short strs
    weight_distance_for_short_strs = attrib(type=Union[bool, float], default=False)
    max_str_length_to_enable_short_str_weight = attrib(type=str, default=3)
    requires_same_first_chr_to_enable_short_str_weight = attrib(type=bool, default=True)

    # endregion

    def __attrs_post_init__(self):
        if isinstance(self.weight_distance_by_comparing_start, str):
            self.weight_distance_by_comparing_start = get_(
                PreDefinedStartComparisonWeights,
                key1=self.weight_distance_by_comparing_start,
                key2=Languages.English,  # falls back to English
                raise_key_error=True,
            )
        if isinstance(self.weight_distance_by_comparing_end, str):
            self.weight_distance_by_comparing_end = get_(
                PreDefinedEndComparisonWeights,
                key1=self.weight_distance_by_comparing_end,
                key2=Languages.English,  # falls back to English
                raise_key_error=True,
            )

    def edit_distance_for_empty_or_short_strs(
            self, str1: str, str2: str, normalized: bool
    ) -> Union[float, int]:
        """
        Computes the edit distance for empty or short input strings
        based on the class attribute settings.

        Args:
            str1: The first input string.
            str2: The second input string.
            normalized: If True, returns the normalized edit distance (a float between 0 and 1);
                              otherwise, returns the raw edit distance (an integer).

        Returns:
            The edit distance for empty or short input strings,
            based on the class attribute settings.

        Example:
            >>> options = EditDistanceOptions(
            ...    no_distance_for_empty_str1=True,
            ...    min_length_for_distance_for_str1=3,
            ... )

            # Use the `edit_distance_for_empty_or_short_strs` method with empty strings
            >>> str1 = ""
            >>> str2 = ""
            >>> options.edit_distance_for_empty_or_short_strs(str1, str2, normalized=True)
            0.0

            # Use the `edit_distance_for_empty_or_short_strs` method with short strings
            >>> str1 = "ab"
            >>> str2 = "cd"
            >>> options.edit_distance_for_empty_or_short_strs(str1, str2, normalized=True)
            0.0

            >>> str1 = "abc"
            >>> str2 = "ab"
            >>> options.edit_distance_for_empty_or_short_strs(str1, str2, normalized=True)

        """
        if not str1:
            if str2:
                if self.no_distance_for_empty_str1:
                    return 0.0 if normalized else 0
                else:
                    return 1.0 if normalized else len(str2)
            else:
                return 0.0 if normalized else 0
        elif not str2:
            if self.no_distance_for_empty_str2:
                return 0.0 if normalized else 0
            else:
                return 1.0 if normalized else len(str1)

        if (
                (
                        self.min_length_for_distance
                        and (len(str1) < self.min_length_for_distance)
                        and (len(str2) < self.min_length_for_distance)
                )
                or (
                self.min_length_for_distance_for_str1
                and len(str1) < self.min_length_for_distance_for_str1
        )
                or (
                self.min_length_for_distance_for_str2
                and len(str2) < self.min_length_for_distance_for_str2
        )
        ):
            return 0.0 if normalized else 0

    def weight_edit_distance(self, str1: str, str2: str, edit_distance: float) -> float:
        """
        Applies the configured weights to the given edit distance between two input strings.

        Args:
            str1: The first input string.
            str2: The second input string.
            edit_distance: The computed edit distance between str1 and str2.

        Returns:
            The weighted edit distance as a float.

        Examples:
            >>> options = EditDistanceOptions(
            ...    weight_distance_if_strs_have_common_start=0.5,
            ...    str_common_start_size=2,
            ...    weight_distance_if_str1_is_substr=0.25,
            ...    weight_distance_if_str2_is_substr=0.25,
            ...    min_str_length_to_enable_substr_weight=3,
            ...    weight_distance_for_short_strs=0.75,
            ...    max_str_length_to_enable_short_str_weight=3,
            ...    requires_same_first_chr_to_enable_short_str_weight=False,
            ... )

            >>> str1 = "apple"
            >>> str2 = "applet"
            >>> edit_distance = 1  # Assuming the edit distance between str1 and str2 is 1
            >>> options.weight_edit_distance(str1, str2, edit_distance)
            0.125

            >>> str1 = "apple"
            >>> str2 = "orange"
            >>> edit_distance = 5  # Assuming the edit distance between str1 and str2 is 5
            >>> options.weight_edit_distance(str1, str2, edit_distance)
            5

            >>> str1 = "cat"
            >>> str2 = "hat"
            >>> edit_distance = 1  # Assuming the edit distance between str1 and str2 is 1
            >>> options.weight_edit_distance(str1, str2, edit_distance)
            0.75
        """
        str_common_start_size = max(1, self.str_common_start_size)
        str1_in_str2, str2_in_str1 = (str1 in str2), (str2 in str1)

        if (
                self.weight_distance_if_strs_have_common_start and
                not (str1_in_str2 or str2_in_str1) and
                len(str1) > str_common_start_size and
                len(str2) > str_common_start_size
        ):
            str1_start = str1.replace(" ", "")[:str_common_start_size]
            str2_start = str2.replace(" ", "")[:str_common_start_size]
            if self.min_str_start_similarity_to_enable_soft_weight is None:
                strs_have_common_start = (str1_start == str2_start)
                if strs_have_common_start:
                    edit_distance *= self.weight_distance_if_strs_have_common_start
            elif (
                    str1[:self.min_str_common_start_to_enable_soft_weight] ==
                    str2[:self.min_str_common_start_to_enable_soft_weight]
            ):
                strs_have_common_start = regular_edit_distance_based_similarity(
                    str1_start, str2_start
                )
                if (
                        strs_have_common_start >
                        self.min_str_start_similarity_to_enable_soft_weight
                ):
                    edit_distance *= 1 - (
                            (1 - self.weight_distance_if_strs_have_common_start)
                            * strs_have_common_start
                    )

        if (
                self.min_str_length_to_enable_substr_weight is None
                or min(len(str1), len(str2)) >= self.min_str_length_to_enable_substr_weight
        ):
            if self.weight_distance_if_str1_heads_str2 and str2.startswith(str1):
                edit_distance *= self.weight_distance_if_str2_heads_str1
            elif self.weight_distance_if_str1_is_substr and str1_in_str2:
                edit_distance *= self.weight_distance_if_str1_is_substr
            elif self.weight_distance_if_str1_first_token_is_sub_str:
                str1_first_token = str1.split()[0]
                if (
                        self.min_str_length_to_enable_substr_weight is None
                        or len(str1_first_token) >= self.min_str_length_to_enable_substr_weight
                ) and str1_first_token in str2:
                    edit_distance *= self.weight_distance_if_str1_first_token_is_sub_str

            if self.weight_distance_if_str2_heads_str1 and str1.startswith(str2):
                edit_distance *= self.weight_distance_if_str1_heads_str2
            elif self.weight_distance_if_str2_is_substr and str2_in_str1:
                edit_distance *= self.weight_distance_if_str2_is_substr
            elif self.weight_distance_if_str2_first_token_is_sub_str:
                str2_first_token = str2.split()[0]
                if (
                        self.min_str_length_to_enable_substr_weight is None
                        or len(str2_first_token) >= self.min_str_length_to_enable_substr_weight
                ) and str2_first_token in str1:
                    edit_distance *= self.weight_distance_if_str2_first_token_is_sub_str

        if self.weight_distance_by_comparing_start:
            edit_distance *= get_start_comparison_weight(
                str1=str1, str2=str2, conflict_config=self.weight_distance_by_comparing_start
            )

        if self.weight_distance_by_comparing_end:
            edit_distance *= get_end_comparison_weight(
                str1=str1, str2=str2, conflict_config=self.weight_distance_by_comparing_end
            )

        if (
                self.weight_distance_for_short_strs
                and (
                (not self.requires_same_first_chr_to_enable_short_str_weight) or str1[0] == str2[0]
        )
                and len(str1) <= self.max_str_length_to_enable_short_str_weight
                and len(str2) <= self.max_str_length_to_enable_short_str_weight
        ):
            edit_distance = edit_distance * self.weight_distance_for_short_strs

        return edit_distance


def edit_distance_marginal_case(str1: str, str2: str, normalized: bool = True) -> float:
    """
    Computes the edit distance for marginal cases when either of the input strings is empty.

    Args:
        str1: The first input string.
        str2: The second input string.
        normalized: If True, returns the normalized edit distance (a float between 0 and 1);
                    otherwise, returns the raw edit distance (an integer).

    Returns:
        The edit distance as a float or an integer, depending on the value of `normalized`.

    Examples:
        >>> str1 = ""
        >>> str2 = ""
        >>> edit_distance_marginal_case(str1, str2, normalized=True)
        0.0

        >>> str1 = ""
        >>> str2 = "apple"
        >>> edit_distance_marginal_case(str1, str2, normalized=True)
        1.0

        >>> str1 = "apple"
        >>> str2 = ""
        >>> edit_distance_marginal_case(str1, str2, normalized=True)
        1.0

        >>> str1 = "apple"
        >>> str2 = ""
        >>> edit_distance_marginal_case(str1, str2, normalized=False)
        5
    """
    if not str1:
        if str2:
            return 1.0 if normalized else len(str2)
        else:
            return 0.0 if normalized else 0
    elif not str2:
        return 1.0 if normalized else len(str1)


def _edit_distance(
        str1: str,
        str2: str,
        normalized: bool = True,
        consider_sorted_tokens: Union[bool, Callable] = False,
        consider_same_num_tokens: Union[bool, Callable] = False,
        options: EditDistanceOptions = None,
        sanitization_config:
        Union[Iterable[StringSanitizationOptions], StringSanitizationConfig] = None,
        tokenizer: Union[None, str, Callable, Any] = None,
        **str_sanitization_kwargs
) -> float:
    # region STEP1: dealing with marginal cases
    # Check for empty or short strings, and handle them using either the provided
    # `EditDistanceOptions` or the `edit_distance_marginal_case` function.
    edit_dist = None
    if options:
        edit_dist = options.edit_distance_for_empty_or_short_strs(
            str1=str1, str2=str2, normalized=normalized
        )
    else:
        edit_dist = edit_distance_marginal_case(str1, str2, normalized=normalized)
    # endregion

    if edit_dist is None:
        # region STEP2: process arguments
        # Sanitize the input strings using the provided sanitization configuration
        # and tokenizer. If necessary, save intermediate results for further processing.
        if sanitization_config:
            sanitized_strs, intermediate_results = string_sanitize(
                str1, str2,
                config=sanitization_config,
                tokenizer=tokenizer,
                return_intermediate_results_before_actions=[
                    StringSanitizationOptions.MAKE_FUZZY,
                    StringSanitizationOptions.REMOVE_SPACES
                ],
                **str_sanitization_kwargs
            )

            if not sanitized_strs[0] or not sanitized_strs[1]:
                intermediate_results = None
            else:
                str1, str2 = sanitized_strs
        else:
            intermediate_results = None

        # endregion

        # region STEP3: regular edit distance
        # Calculate the edit distance between the sanitized strings, either
        # normalized or raw, depending on the value of `normalized`.
        edit_dist = distance(str1, str2)
        if normalized:
            edit_dist = edit_dist / max(len(str1), len(str2))
        # endregion

        # If spaces were removed during sanitization, restore them
        # for tokenization purposes.
        if (
                intermediate_results is not None and
                StringSanitizationOptions.REMOVE_SPACES in intermediate_results
        ):
            # restores spaces in `str1` and `str2` in order to tokenize
            str1, str2 = intermediate_results[StringSanitizationOptions.REMOVE_SPACES]
            con = ''
        else:
            con = ' '

        # Considers edit distances after 1) sorting tokens or 2) disregarding additional characters
        # in the longer string.
        if consider_sorted_tokens or consider_same_num_tokens:
            tokens1 = list(tokenize(str1, tokenizer))
            tokens2 = list(tokenize(str2, tokenizer))

            # Helper function to update the edit distance based on sorted tokens
            # or same number of tokens.
            def _update_edit_dist(reduce_method):
                nonlocal edit_dist
                str1 = con.join(sorted(tokens1))
                str2 = con.join(sorted(tokens2))

                edit_dist2 = distance(str1, str2)
                if normalized:
                    edit_dist2 = edit_dist2 / max(len(str1), len(str2))

                str1 = con.join(sorted(tokens1, reverse=True))
                str2 = con.join(sorted(tokens2, reverse=True))
                edit_dist3 = distance(str1, str2)
                if normalized:
                    edit_dist3 = edit_dist3 / max(len(str1), len(str2))

                # Update the edit distance using the provided reduce method
                # (min, max, average, or custom function).
                if callable(reduce_method):
                    edit_dist = reduce_method(
                        (edit_dist, edit_dist2, edit_dist3)
                    )

            # Update the edit distance considering sorted tokens, if requested.
            if consider_sorted_tokens:
                _update_edit_dist(consider_sorted_tokens)

            # Update the edit distance considering the same number of tokens, if requested.
            if consider_same_num_tokens:
                min_token_len = min(len(tokens1), len(tokens2))
                tokens1 = tokens1[:min_token_len]
                tokens2 = tokens2[:min_token_len]
                if sum(map(len, tokens1)) >= 3 and sum(map(len, tokens2)) >= 3:
                    _update_edit_dist(consider_same_num_tokens)

        # Apply any additional weighting to the edit distance using the provided
        # `EditDistanceOptions`, if available.
        if options:
            edit_dist = options.weight_edit_distance(
                str1=str1, str2=str2, edit_distance=edit_dist
            )

    return edit_dist


def edit_distance(
        str1: str,
        str2: str,
        return_ratio=True,
        consider_sorted_tokens: Union[bool, Callable] = False,
        consider_same_num_tokens: Union[bool, Callable] = False,
        consider_non_overlap_tokens: Union[bool, Callable] = False,
        options: EditDistanceOptions = None,
        sanitization_config: Union[Iterable[StringSanitizationOptions], StringSanitizationConfig] = None,
        tokenizer: Union[None, str, Callable, Any] = None,
        **str_sanitization_kwargs
) -> float:
    """
    Computes the edit distance (Levenshtein distance) between two strings;
    can return the similarity ratio or the edit distance itself.

    The function can be customized with various options like token sorting,
    token count consideration, and sanitization configurations.
    The edit distance can be further customized using the options parameter.

    Args:
        str1: The first string to compare.
        str2: The second string to compare.
        return_ratio: If True, returns the similarity ratio (1 - normalized edit distance).
            If False, returns the raw edit distance.
        consider_sorted_tokens: If True, then the edit distance after sorting the tokens in the
            input strings is also considered. If set to a function, it's used to combine the edit
            distances of the original strings and the sorted-token strings.
        consider_same_num_tokens: If True, the edit distance disregards additional characters in
            the longer string. If set to a function, it's used to combine the edit distances
            of the original strings and the edit distance that disregards additional characters
            from the longer string.
        consider_non_overlap_tokens: If True, then edit distance after removing the overlapping
            tokens between the two input strings is also considered. If set to a function,
            it's used to combine the edit distances of the original strings and the strings with
            overlapping tokens removed.
        options: An instance of `EditDistanceOptions` to for additional edit distance
            weighting options.
        sanitization_config: A list of `StringSanitizationOptions` or a `StringSanitizationConfig`
            instance to configure the sanitization of the input strings. See also the
            :func:`string_sanitize` function.
        tokenizer: A tokenizer to be used for tokenization when needed. See also the
            :func:`tokenize` function.
        **str_sanitization_kwargs: Additional named arguments for string sanitization.

    Returns:
        The similarity ratio (1 - normalized edit distance) if `return_ratio` is True,
        or the raw edit distance if `return_ratio` is False.

    Examples:
        >>> str1 = "kitten"
        >>> str2 = "sitting"
        >>> edit_distance(str1, str2)
        0.5714285714285714

        >>> str1 = "ten nights turn on"
        >>> str2 = "turn on den light"
        >>> edit_distance(
        ...    str1,
        ...    str2,
        ...    consider_sorted_tokens=True,
        ...    consider_same_num_tokens=True,
        ...    min_length=2,
        ...    sanitization_config=[
        ...        StringSanitizationOptions.REMOVE_ACRONYMS_PERIODS_AND_SPACES,
        ...        StringSanitizationOptions.REMOVE_PUNCTUATIONS_EXCEPT_FOR_HYPHEN,
        ...        StringSanitizationOptions.MAKE_FUZZY,
        ...        StringSanitizationOptions.REMOVE_SPACES
        ...    ],
        ...    return_ratio=True
        ... )
        0.9285714285714286

        >>> str1 = "turn off my lights to white"
        >>> str2 = "turn all of my lights to white"
        >>> edit_distance(
        ...    str1,
        ...    str2,
        ...    consider_sorted_tokens=True,
        ...    consider_same_num_tokens=True,
        ...    min_length=2,
        ...    sanitization_config=[
        ...        StringSanitizationOptions.REMOVE_COMMON_PREFIX,
        ...        StringSanitizationOptions.REMOVE_ACRONYMS_PERIODS_AND_SPACES,
        ...        StringSanitizationOptions.REMOVE_PUNCTUATIONS_EXCEPT_FOR_HYPHEN,
        ...        StringSanitizationOptions.MAKE_FUZZY,
        ...        StringSanitizationOptions.REMOVE_SPACES
        ...    ],
        ...    return_ratio=True
        ... )
        0.7894736842105263
    """
    if 'sanitization_actions' in str_sanitization_kwargs:
        raise ValueError("'sanitization_actions' is no longer supported; "
                         "use 'sanitization_config' instead")

    # region STEP1: process arguments
    edit_dist = edit_distance_marginal_case(str1, str2, normalized=return_ratio)
    if edit_dist is None:
        if sanitization_config and not isinstance(sanitization_config, StringSanitizationConfig):
            sanitization_config = StringSanitizationConfig(actions=sanitization_config)

        if consider_sorted_tokens is True:
            consider_sorted_tokens = min
        elif consider_sorted_tokens is False:
            consider_sorted_tokens = None
        if consider_same_num_tokens is True:
            consider_same_num_tokens = min
        elif consider_same_num_tokens is False:
            consider_same_num_tokens = None
        if consider_non_overlap_tokens is True:
            consider_non_overlap_tokens = min
        elif consider_non_overlap_tokens is False:
            consider_non_overlap_tokens = None

        edit_dist = _edit_distance(
            str1=str1,
            str2=str2,
            normalized=return_ratio,
            consider_sorted_tokens=consider_sorted_tokens,
            consider_same_num_tokens=consider_same_num_tokens,
            options=options,
            sanitization_config=sanitization_config,
            tokenizer=tokenizer,
            **str_sanitization_kwargs
        )
        if consider_non_overlap_tokens:
            str1, str2 = remove_common_tokens_except_for_sub_tokens(str1, str2, tokenizer=tokenizer)
            if str1 and str2:
                edit_dist2 = _edit_distance(
                    str1=str1,
                    str2=str2,
                    normalized=return_ratio,
                    consider_sorted_tokens=consider_sorted_tokens,
                    consider_same_num_tokens=consider_same_num_tokens,
                    options=options,
                    sanitization_config=sanitization_config,
                    tokenizer=tokenizer,
                    **str_sanitization_kwargs
                )
                edit_dist = consider_non_overlap_tokens(edit_dist, edit_dist2)

    return 1.0 - edit_dist if return_ratio else edit_dist
