import re
from typing import Optional

from python_utils.common_utils.set_helper import compare_sets, set_one_contains_the_other
from python_utils.nlp_utils.common import Languages
from python_utils.nlp_utils.metrics.edit_distance import EditDistanceOptions, edit_distance
from python_utils.nlp_utils.punctuations import remove_acronym_periods_and_spaces
from python_utils.nlp_utils.string_sanitization import remove_common_tokens_except_for_sub_tokens
from python_utils.string_utils.regex import get_regex_match_group_indexes, iter_matches

_NUMBERS_REGEX_EN = '(?P<n100>100th|100|a hundred|one hundred|hundred|hundreds|hundredth)|' \
                    '(?P<n1000>1000th|1000|one thousand|a thousand|thousand|thousands|thousandth)|' \
                    '(?P<n11>(?:11|eleven)(?:th)?)|' \
                    '(?P<n12>twelve|twelfth|12(?:th)?)|' \
                    '(?P<n13>(?:thirteen|13)(?:th)?)|' \
                    '(?P<n14>(?:fourteen|14)(?:th)?)|' \
                    '(?P<n15>(?:fifteen|15)(?:th)?)|' \
                    '(?P<n16>(?:sixteen|16)(?:th)?)|' \
                    '(?P<n17>(?:seventeen|17)(?:th)?)|' \
                    '(?P<n18>(?:eighteen|18)(?:th)?)|' \
                    '(?P<n19>(?:nineteen|19)(?:th)?)|' \
                    '(?P<n10>(?:10|ten)(?:th)?)|' \
                    '(?P<n20>20(?:th)?|twent(?:y|ies|ieth))|' \
                    '(?P<n30>30(?:th)?|thirt(?:y|ies|ieth))|' \
                    '(?P<n40>40(?:th)?|(?:fort|fourt)(?:y|ies|ieth))|' \
                    '(?P<n50>50(?:th)?|fift(?:y|ies|ieth))|' \
                    '(?P<n60>60(?:th)?|sixt(?:y|ies|ieth))|' \
                    '(?P<n70>70(?:th)?|sevent(?:y|ies|ieth))|' \
                    '(?P<n80>80(?:th)?|eight(?:y|ies|ieth))|' \
                    '(?P<n90>90(?:th)?|ninet(?:y|ies|ieth))|' \
                    '(?P<n1>1st|1|one|first)|' \
                    '(?P<n2>2nd|2|two|second)|' \
                    '(?P<n3>3rd|3|three|third)|' \
                    '(?P<n4>4th|4|four(?:th)?)|' \
                    '(?P<n5>5th|5|five|fifth)|' \
                    '(?P<n6>(?:6|six)(?:th)?)|' \
                    '(?P<n7>(?:7|seven)(?:th)?)|' \
                    '(?P<n8>8th|8|eight(?:h)?)|' \
                    '(?P<n9>9th|9|nine|ninth)'

_NUMBERS_REGEX_DE = '(?P<n11>(?:11|elf)(?:te)?)|' \
                    '(?P<n12>(?:12|zwölf|zwolf)(?:tel)?)|' \
                    '(?P<n13>(?:13|dreizehn)(?:te)?)|' \
                    '(?P<n14>(?:14|vierzehn)(?:te)?)|' \
                    '(?P<n15>(?:15|fünfzehn|funfzehn)(?:ten)?)|' \
                    '(?P<n16>(?:16|sechzehn)(?:ter)?)|' \
                    '(?P<n17>(?:17|siebzehn)(?:ter)?)|' \
                    '(?P<n18>(?:18|achtzehn)(?:ter)?)|' \
                    '(?P<n19>(?:19|neunzehn)(?:ten)?)|' \
                    '(?P<n10>(?:10|zehn)(?:tel)?)|' \
                    r'(?P<n20>(?:20|zwanzig)(?:er\s?jahre|er|ste|ster|sten)?)|' \
                    r'(?P<n30>(?:30|dreißig|dreibig)(?:er\s?jahre|er|ste|ster|sten)?)|' \
                    r'(?P<n40>(?:40|vierzig)(?:er\s?jahre|er|ste|ster|sten)?)|' \
                    r'(?P<n50>(?:50|fünfzig|funfzig)(?:er\s?jahre|er|ste|ster|sten)?)|' \
                    r'(?P<n60>(?:60|sechzig)(?:er\s?jahre|er|ste|ster|sten)?)|' \
                    r'(?P<n70>(?:70|siebzig)(?:er\s?jahre|er|ste|ster|sten)?)|' \
                    r'(?P<n80>(?:80|achtzig)(?:er\s?jahre|er|ste|ster|sten)?)|' \
                    r'(?P<n90>(?:90|neunzig)(?:er\s?jahre|er|ste|ster|sten)?)|' \
                    '(?P<n1>1st|1|eines|erste)|' \
                    '(?P<n2>2nd|2|zwei|zweite)|' \
                    '(?P<n3>3rd|3|drei|dritte)|' \
                    '(?P<n4>4th|(?:4|vier)(?:te|ter)?)|' \
                    '(?P<n5>5th|(?:5|fünf|funf)(?:te|ter)?)|' \
                    '(?P<n6>6th|(?:6|sechs)(?:te|ter)?)|' \
                    '(?P<n7>7th|(?:7|sieben)(?:te|ter)?)|siebte' \
                    '(?P<n8>8th|(?:8|acht)(?:e|te|ter)?)|' \
                    '(?P<n9>9th|(?:9|neun)(?:e|te|ter)?)|' \
                    '(?P<n100>100th|100|einhundert|hundert|hunderte|hunderter|hundertstel)|' \
                    '(?P<n1000>1000th|1000|tausend|tausende|tausender|tausendstel)'

_NUMBERS_REGEX_ES = r'(?P<n11>(?:(?:la|los|de)\s)?(?:(?:11|once)|(?:(?:undécim|undecim)(?:a|o)?)))|' \
                    r'(?P<n12>(?:(?:la|los|de)\s)?(?:(?:12|doce)|(?:(?:duodécim|duodecim|doceav|dozav)(?:a|o)?)))|' \
                    r'(?P<n13>(?:(?:la|los|de)\s)?(?:(?:13|trece)|(?:(?:decimotercer|decimoterci)(?:a|o)?)))|' \
                    r'(?P<n14>(?:(?:la|los|de)\s)?(?:(?:14|catorce)|(?:decimocuart(?:a|o)?)))|' \
                    r'(?P<n15>(?:(?:la|los|de)\s)?(?:(?:15|quince)|(?:decimoquint(?:a|o)?)))|' \
                    r'(?P<n16>(?:(?:la|los|de)\s)?(?:(?:16|dieciséis|dieciseis)|(?:(?:decimosext|dieciseisav)(?:a|o)?)))|' \
                    r'(?P<n17>(?:(?:la|los|de)\s)?(?:(?:17|diecisiete)|(?:(?:decimoséptim|decimoseptim)(?:a|o)?)))|' \
                    r'(?P<n18>(?:(?:la|los|de)\s)?(?:(?:18|dieciocho)|(?:decimoctav(?:a|o)?)))|' \
                    r'(?P<n19>(?:(?:la|los|de)\s)?(?:(?:19|diecinueve)|(?:decimonoven(?:a|o)?)))|' \
                    r'(?P<n10>(?:(?:la|los|de)\s)?(?:(?:10|decena|diez|decenas)|(?:(?:décim|decim|decenas|decen)(?:a|o)?)))|' \
                    r'(?P<n20>(?:(?:la|los|de)\s)?(?:(?:20|veinte)|(?:(?:vigésim|vigesim)(?:a|o)?)))|' \
                    r'(?P<n30>(?:(?:la|los|de)\s)?(?:(?:30|treinta)|(?:(?:trigésim|trigesim|treint)(?:a|o)?)))|' \
                    r'(?P<n40>(?:(?:la|los|de)\s)?(?:(?:40|cuarenta)|(?:(?:cuadragésim|cuadragesim|cuarent)(?:a|o)?)))|' \
                    r'(?P<n50>(?:(?:la|los|de)\s)?(?:(?:50|cincuenta)|(?:(?:quincuagésim|quincuagesim|cincuent)(?:a|o)?)))|' \
                    r'(?P<n60>(?:(?:la|los|de)\s)?(?:(?:60|sesenta)|(?:(?:sexagésim|sexagesim|sesentav|sesent)(?:a|o)?)))|' \
                    r'(?P<n70>(?:(?:la|los|de)\s)?(?:(?:70|setenta)|(?:(?:septuagésim|septuagesim|setentav|setent)(?:a|o)?)))|' \
                    r'(?P<n80>(?:(?:la|los|de)\s)?(?:(?:80|ochenta)|(?:(?:diecioch|ochent)(?:a|o)?)))|' \
                    r'(?P<n90>(?:(?:la|los|de)\s)?(?:(?:90|noventa)|(?:(?:nonagésim|nonagesim|novent)(?:a|o)?)))|' \
                    r'(?P<n1>(?:(?:la|los|de)\s)?(?:(?:1st|1|una|uno|unos)|(?:primer(?:a|o)?)))|' \
                    r'(?P<n2>(?:(?:la|los|de)\s)?(?:(?:2nd|2|dos)|(?:segund(?:a|o)?)))|' \
                    r'(?P<n3>(?:(?:la|los|de)\s)?(?:(?:3rd|3|tres)|(?:(?:tercer|terci)(?:a|o)?)))|' \
                    r'(?P<n4>(?:(?:la|los|de)\s)?(?:(?:4th|4|cuatro)|(?:cuart(?:a|o)?)))|' \
                    r'(?P<n5>(?:(?:la|los|de)\s)?(?:(?:5th|5|cinco)|(?:quint(?:a|o)?)))|' \
                    r'(?P<n6>(?:(?:la|los|de)\s)?(?:(?:6th|6|seis)|(?:sext(?:a|o)?)))|' \
                    r'(?P<n7>(?:(?:la|los|de)\s)?(?:(?:7th|7|siete)|(?:(?:séptim|septim)(?:a|o)?)))|' \
                    r'(?P<n8>(?:(?:la|los|de)\s)?(?:(?:8th|8|ocho)|(?:(?:octov|octav)(?:a|o)?)))|' \
                    r'(?P<n9>(?:(?:la|los|de)\s)?(?:(?:9th|9|nueve)|(?:noven(?:a|o)?)))|' \
                    r'(?P<n100>(?:(?:la|los|de)\s)?(?:(?:100th|100|ciento|cien|cientos)|(?:(?:centésim|centesim)(?:a|o)?)))|' \
                    r'(?P<n1000>(?:(?:la|los|de)\s)?(?:(?:1000th|1000|mil|miles)|(?:(?:milésim|milesim)(?:a|o)?)))'

_NUMBERS_COMPLIED_REGEX_EN = re.compile(fr'\b({_NUMBERS_REGEX_EN})\b')
_NUMBERS_COMPLIED_REGEX_DE = re.compile(fr'\b({_NUMBERS_REGEX_DE})\b')
_NUMBERS_COMPLIED_REGEX_ES = re.compile(fr'\b({_NUMBERS_REGEX_ES})\b')

NUMBERS_REGEX = {
    Languages.English: _NUMBERS_REGEX_EN,
    Languages.German: _NUMBERS_REGEX_DE,
    Languages.Spanish: _NUMBERS_REGEX_ES
}
NUMBERS_REGEX_COMPILED = {
    Languages.English: _NUMBERS_COMPLIED_REGEX_EN,
    Languages.German: _NUMBERS_COMPLIED_REGEX_DE,
    Languages.Spanish: _NUMBERS_COMPLIED_REGEX_ES
}


def has_conflict_numbers(
        str1: str,
        str2: str,
        allows_add: bool = False,
        allows_drop: bool = False,
        edit_distance_threshold_to_ignore_conflict: Optional[float] = None,
        edit_distance_options: EditDistanceOptions = None,
        language: Languages = Languages.English,
        **kwargs
):
    """
    Checks whether there are conflicting numbers in two given strings `str1` and `str2`.

    Args:
        str1: The first string to check.
        str2: The second string to check.
        allows_add: Whether to allow addition of numbers in `str2`.
        allows_drop: Whether to allow drop of numbers in `str2`.
        edit_distance_threshold_to_ignore_conflict: If the edit distance between the numbers from the
            two strings are above this threshold, then this function ignores the number conflict
            and return False.
        edit_distance_options: The options for edit distance calculation.
        language: The language of the numbers.
        **kwargs: Any additional keyword arguments to be passed to the edit distance calculation.

    Returns:
        True if there are conflicting numbers in the two strings, False otherwise.


    Examples:
        >>> str1 = 'I need five pens and two pencils'
        >>> str2 = 'I want to buy two pencils and five pens'
        >>> has_conflict_numbers(str1, str2)
        False

        >>> str1 = 'I need five pens and two pencils'
        >>> str2 = 'I want to buy two pencils and four pens'
        >>> has_conflict_numbers(str1, str2)
        True

        >>> str1 = 'I need five pens and two pencils'
        >>> str2 = 'I want to buy two pencils and five pens and six erasers'
        >>> has_conflict_numbers(str1, str2)
        True

        >>> str1 = 'I need five pens and two pencils'
        >>> str2 = 'I want to buy two pencils and five pens and six erasers'
        >>> has_conflict_numbers(str1, str2, allows_add=True)
        False

        >>> str1 = 'I need five pens and two pencils'
        >>> str2 = 'I want to buy two pencils'
        >>> has_conflict_numbers(str1, str2)
        True

        >>> str1 = 'I need five pens and two pencils'
        >>> str2 = 'I want to buy two pencils'
        >>> has_conflict_numbers(str1, str2, allows_drop=True)
        False

        >>> str1 = 'play station one seventy eighty eight'
        >>> str2 = 'play station one seven eighty eight'
        >>> has_conflict_numbers(str1, str2, edit_distance_threshold_to_ignore_conflict=0.80)
        False

    """
    if language not in NUMBERS_REGEX_COMPILED:
        raise ValueError(f"language '{language}' is not supported yet")
    pattern = NUMBERS_REGEX_COMPILED[language]
    utt1_nums = get_regex_match_group_indexes(
        pattern=pattern,
        string=remove_acronym_periods_and_spaces(str1),
        start_group_index=1
    )
    utt2_nums = get_regex_match_group_indexes(
        pattern=pattern,
        string=remove_acronym_periods_and_spaces(str2),
        start_group_index=1
    )
    return (
            compare_sets(
                utt1_nums,
                utt2_nums,
                allows_add=allows_add,
                allows_drop=allows_drop
            ) and
            (
                    edit_distance_threshold_to_ignore_conflict is None or
                    edit_distance(
                        *remove_common_tokens_except_for_sub_tokens(
                            iter_matches(NUMBERS_REGEX_COMPILED[language], str1),
                            iter_matches(NUMBERS_REGEX_COMPILED[language], str2)
                        ),
                        options=edit_distance_options,
                        language=language,
                        **kwargs
                    ) <= edit_distance_threshold_to_ignore_conflict
            )
    )


def has_dropped_or_added_number(str1, str2):
    utt1_nums = get_regex_match_group_indexes(
        pattern=_NUMBERS_COMPLIED_REGEX_EN,
        string=remove_acronym_periods_and_spaces(str1),
        start_group_index=1
    )
    utt2_nums = get_regex_match_group_indexes(
        pattern=_NUMBERS_COMPLIED_REGEX_EN,
        string=remove_acronym_periods_and_spaces(str2),
        start_group_index=1
    )
    return set_one_contains_the_other(utt1_nums, utt2_nums)
