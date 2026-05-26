"""
String Pattern Detection Module

Provides utilities to detect various patterns in strings that indicate
dynamic/personalized content. These patterns are useful for identifying
content that changes per user, session, or time - making them unsuitable
for stable identifiers like XPath selectors.

Categories of patterns detected:
- Dates: Day names, month names, date formats (MM/DD/YYYY, ISO, etc.)
- Times: Clock times with optional AM/PM
- Counts with units: "2 travelers", "1 room", "5 items"
- Currency/Prices: $299, EUR150, 299.99
- Numeric ranges: "6 - 8", "10-15"
- Percentages: "50%", "25% off"

Example usage:
    >>> from python_utils.nlp_utils.string_patterns import contains_dynamic_content
    >>> contains_dynamic_content("Where to?")
    False  # Static label
    >>> contains_dynamic_content("Dates, Tue, Jan 6 - Thu, Jan 8")
    True   # Contains dates
    >>> contains_dynamic_content("Travelers, 2 travelers, 1 room")
    True   # Contains counts with units
    >>> contains_dynamic_content("$299 per night")
    True   # Contains currency
"""

import re
from typing import List, Optional, Pattern, Tuple

# =============================================================================
# Date Patterns
# =============================================================================

# Day name patterns (abbreviated and full)
DAY_NAME_PATTERNS = [
    r'\b(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\b',                    # Abbreviated
    r'\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b',  # Full
]

# Month name patterns (abbreviated and full)
MONTH_NAME_PATTERNS = [
    r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b',  # Abbreviated
    r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\b',  # Full
]

# Date format patterns
DATE_FORMAT_PATTERNS = [
    r'\b\d{1,2}/\d{1,2}/\d{2,4}\b',      # MM/DD/YYYY or DD/MM/YYYY
    r'\b\d{1,2}-\d{1,2}-\d{2,4}\b',      # MM-DD-YYYY or DD-MM-YYYY
    r'\b\d{4}-\d{2}-\d{2}\b',            # ISO: YYYY-MM-DD
    r'\b\d{1,2}\.\d{1,2}\.\d{2,4}\b',    # DD.MM.YYYY (European)
    r'\b\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b',  # 6 Jan, 25 Dec
    r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}\b',  # Jan 6, Dec 25
]

# =============================================================================
# Time Patterns
# =============================================================================

TIME_PATTERNS = [
    r'\b\d{1,2}:\d{2}\s*(AM|PM|am|pm)\b',     # 10:30 AM, 2:00 pm
    r'\b\d{1,2}:\d{2}:\d{2}\b',               # 14:30:00 (with seconds)
    r'\b\d{1,2}:\d{2}\b',                      # 14:30 (24-hour without AM/PM)
    r'\b\d{1,2}\s*(AM|PM|am|pm)\b',           # 10 AM, 2 pm (without minutes)
]

# =============================================================================
# Count + Unit Patterns (Personalized quantities)
# =============================================================================

# Travel-related counts
TRAVEL_COUNT_PATTERNS = [
    r'\b\d+\s+(traveler|travelers)\b',
    r'\b\d+\s+(guest|guests)\b',
    r'\b\d+\s+(adult|adults)\b',
    r'\b\d+\s+(child|children)\b',
    r'\b\d+\s+(infant|infants)\b',
    r'\b\d+\s+(passenger|passengers)\b',
    r'\b\d+\s+(person|persons|people)\b',
    r'\b\d+\s+(room|rooms)\b',
    r'\b\d+\s+(night|nights)\b',
    r'\b\d+\s+(day|days)\b',
    r'\b\d+\s+(seat|seats)\b',
    r'\b\d+\s+(bag|bags|baggage)\b',
]

# Shopping/E-commerce counts
SHOPPING_COUNT_PATTERNS = [
    r'\b\d+\s+(item|items)\b',
    r'\b\d+\s+(product|products)\b',
    r'\b\d+\s+(result|results)\b',
    r'\b\d+\s+(match|matches)\b',
    r'\b\d+\s+(review|reviews)\b',
    r'\b\d+\s+(rating|ratings)\b',
    r'\b\d+\s+(star|stars)\b',
    r'\b\d+\s+(order|orders)\b',
    r'\b\d+\s+(listing|listings)\b',
]

# General quantity patterns
GENERAL_COUNT_PATTERNS = [
    r'\b\d+\s+(message|messages)\b',
    r'\b\d+\s+(notification|notifications)\b',
    r'\b\d+\s+(comment|comments)\b',
    r'\b\d+\s+(reply|replies)\b',
    r'\b\d+\s+(like|likes)\b',
    r'\b\d+\s+(view|views)\b',
    r'\b\d+\s+(follower|followers)\b',
    r'\b\d+\s+(following)\b',
    r'\b\d+\s+(post|posts)\b',
    r'\b\d+\s+(photo|photos)\b',
    r'\b\d+\s+(video|videos)\b',
    r'\b\d+\s+(file|files)\b',
    r'\b\d+\s+(download|downloads)\b',
    r'\b\d+\s+(update|updates)\b',
    r'\b\d+\s+(hour|hours)\b',
    r'\b\d+\s+(minute|minutes|min|mins)\b',
    r'\b\d+\s+(second|seconds|sec|secs)\b',
    r'\b\d+\s+(week|weeks)\b',
    r'\b\d+\s+(month|months)\b',
    r'\b\d+\s+(year|years)\b',
]

# =============================================================================
# Currency/Price Patterns
# =============================================================================

CURRENCY_PATTERNS = [
    r'\$\d+(?:,\d{3})*(?:\.\d{2})?\b',       # $299, $1,299, $299.99
    r'€\d+(?:,\d{3})*(?:\.\d{2})?\b',        # EUR150, EUR1,500.00
    r'£\d+(?:,\d{3})*(?:\.\d{2})?\b',        # GBP99, GBP1,299.99
    r'¥\d+(?:,\d{3})*\b',                     # JPY/CNY
    r'₹\d+(?:,\d{3})*(?:\.\d{2})?\b',        # INR
    r'\b\d+(?:,\d{3})*\.\d{2}\b',             # 299.99 (decimal price without symbol)
    r'\bUSD\s*\d+(?:,\d{3})*(?:\.\d{2})?\b', # USD 299
    r'\bEUR\s*\d+(?:,\d{3})*(?:\.\d{2})?\b', # EUR 150
    r'\bGBP\s*\d+(?:,\d{3})*(?:\.\d{2})?\b', # GBP 99
]

# =============================================================================
# Numeric Range Patterns
# =============================================================================

RANGE_PATTERNS = [
    r'\b\d+\s*[-–—]\s*\d+\b',                 # 6-8, 10 - 15, 1–5
    r'\b\d+\s+to\s+\d+\b',                    # 6 to 8
    r'\b\d+\s*-\s*\d+\s*(night|nights|day|days|hour|hours)\b',  # 2-3 nights
]

# =============================================================================
# Percentage Patterns
# =============================================================================

PERCENTAGE_PATTERNS = [
    r'\b\d+(?:\.\d+)?%',                      # 50%, 25.5%
    r'\b\d+(?:\.\d+)?\s*percent\b',           # 50 percent
    r'\b\d+%\s*off\b',                        # 25% off
]

# =============================================================================
# Miscellaneous Dynamic Patterns
# =============================================================================

MISC_DYNAMIC_PATTERNS = [
    r'\b\d+\s*(?:mi|km|miles|kilometers)\s+away\b',  # Distance: "5 mi away"
    r'\bin\s+\d+\s*(min|minute|minutes|hour|hours)\b',  # "in 5 minutes"
    r'\b\d+\s*(min|minute|minutes)\s+ago\b',  # "5 minutes ago"
    r'\b\d+\s*(hour|hours)\s+ago\b',          # "2 hours ago"
    r'\b\d+\s*(day|days)\s+ago\b',            # "3 days ago"
    r'\blast\s+\d+\s*(day|days|week|weeks|month|months)\b',  # "last 7 days"
    r'\bnext\s+\d+\s*(day|days|week|weeks|month|months)\b',  # "next 30 days"
]

# =============================================================================
# Pattern Categories (for selective detection)
# =============================================================================

PATTERN_CATEGORIES = {
    'date': DAY_NAME_PATTERNS + MONTH_NAME_PATTERNS + DATE_FORMAT_PATTERNS,
    'time': TIME_PATTERNS,
    'travel_count': TRAVEL_COUNT_PATTERNS,
    'shopping_count': SHOPPING_COUNT_PATTERNS,
    'general_count': GENERAL_COUNT_PATTERNS,
    'currency': CURRENCY_PATTERNS,
    'range': RANGE_PATTERNS,
    'percentage': PERCENTAGE_PATTERNS,
    'misc': MISC_DYNAMIC_PATTERNS,
}

# All patterns combined
ALL_DYNAMIC_PATTERNS = (
    DAY_NAME_PATTERNS +
    MONTH_NAME_PATTERNS +
    DATE_FORMAT_PATTERNS +
    TIME_PATTERNS +
    TRAVEL_COUNT_PATTERNS +
    SHOPPING_COUNT_PATTERNS +
    GENERAL_COUNT_PATTERNS +
    CURRENCY_PATTERNS +
    RANGE_PATTERNS +
    PERCENTAGE_PATTERNS +
    MISC_DYNAMIC_PATTERNS
)

# =============================================================================
# Compiled Pattern Cache
# =============================================================================

_COMPILED_PATTERNS_CACHE: Optional[List[Pattern]] = None
_COMPILED_CATEGORY_CACHE: dict = {}


def _get_compiled_patterns() -> List[Pattern]:
    """Lazily compile all dynamic content patterns."""
    global _COMPILED_PATTERNS_CACHE
    if _COMPILED_PATTERNS_CACHE is None:
        _COMPILED_PATTERNS_CACHE = [
            re.compile(p, re.IGNORECASE) for p in ALL_DYNAMIC_PATTERNS
        ]
    return _COMPILED_PATTERNS_CACHE


def _get_compiled_category(category: str) -> List[Pattern]:
    """Lazily compile patterns for a specific category."""
    global _COMPILED_CATEGORY_CACHE
    if category not in _COMPILED_CATEGORY_CACHE:
        patterns = PATTERN_CATEGORIES.get(category, [])
        _COMPILED_CATEGORY_CACHE[category] = [
            re.compile(p, re.IGNORECASE) for p in patterns
        ]
    return _COMPILED_CATEGORY_CACHE[category]


# =============================================================================
# Detection Functions
# =============================================================================

def contains_date(value: str) -> bool:
    """
    Check if string contains date-related content.

    Detects:
    - Day names: Mon, Tuesday, etc.
    - Month names: Jan, February, etc.
    - Date formats: 01/06/2024, 2024-01-06, 6 Jan, etc.

    Args:
        value: The string to check

    Returns:
        True if value contains date patterns

    Examples:
        >>> contains_date("Tue, Jan 6")
        True
        >>> contains_date("Check-in: 01/15/2024")
        True
        >>> contains_date("Search flights")
        False
    """
    for pattern in _get_compiled_category('date'):
        if pattern.search(value):
            return True
    return False


def contains_time(value: str) -> bool:
    """
    Check if string contains time-related content.

    Detects:
    - Clock times: 10:30 AM, 14:00, 2 pm

    Args:
        value: The string to check

    Returns:
        True if value contains time patterns

    Examples:
        >>> contains_time("Departure: 10:30 AM")
        True
        >>> contains_time("Flight at 14:00")
        True
        >>> contains_time("Select time")
        False
    """
    for pattern in _get_compiled_category('time'):
        if pattern.search(value):
            return True
    return False


def contains_count_with_unit(value: str) -> bool:
    """
    Check if string contains count + unit patterns.

    Detects counts for travel, shopping, and general contexts:
    - Travel: "2 travelers", "1 room", "3 nights"
    - Shopping: "5 items", "10 results"
    - General: "3 messages", "100 followers"

    Args:
        value: The string to check

    Returns:
        True if value contains count + unit patterns

    Examples:
        >>> contains_count_with_unit("2 travelers, 1 room")
        True
        >>> contains_count_with_unit("5 items in cart")
        True
        >>> contains_count_with_unit("Add travelers")
        False
    """
    for category in ['travel_count', 'shopping_count', 'general_count']:
        for pattern in _get_compiled_category(category):
            if pattern.search(value):
                return True
    return False


def contains_currency(value: str) -> bool:
    """
    Check if string contains currency/price patterns.

    Detects:
    - Symbol + amount: $299, EUR150, GBP99.99
    - Decimal prices: 299.99

    Args:
        value: The string to check

    Returns:
        True if value contains currency patterns

    Examples:
        >>> contains_currency("$299 per night")
        True
        >>> contains_currency("Total: EUR150.00")
        True
        >>> contains_currency("View prices")
        False
    """
    for pattern in _get_compiled_category('currency'):
        if pattern.search(value):
            return True
    return False


def contains_numeric_range(value: str) -> bool:
    """
    Check if string contains numeric range patterns.

    Detects:
    - Dash ranges: 6-8, 10 - 15
    - Text ranges: 6 to 8

    Args:
        value: The string to check

    Returns:
        True if value contains range patterns

    Examples:
        >>> contains_numeric_range("Jan 6 - Jan 8")
        True
        >>> contains_numeric_range("2-3 nights")
        True
        >>> contains_numeric_range("Select dates")
        False
    """
    for pattern in _get_compiled_category('range'):
        if pattern.search(value):
            return True
    return False


def contains_percentage(value: str) -> bool:
    """
    Check if string contains percentage patterns.

    Detects:
    - Percentages: 50%, 25.5%
    - Discount text: "25% off"

    Args:
        value: The string to check

    Returns:
        True if value contains percentage patterns

    Examples:
        >>> contains_percentage("50% off")
        True
        >>> contains_percentage("Save 25%")
        True
        >>> contains_percentage("Best deals")
        False
    """
    for pattern in _get_compiled_category('percentage'):
        if pattern.search(value):
            return True
    return False


def contains_dynamic_content(
    value: str,
    categories: Optional[List[str]] = None
) -> bool:
    """
    Check if string contains any dynamic/personalized content.

    This is the main function for detecting content that changes per user,
    session, or time. Such content is unsuitable for stable identifiers.

    Args:
        value: The string to check
        categories: Optional list of categories to check. If None, checks all.
                   Valid categories: 'date', 'time', 'travel_count',
                   'shopping_count', 'general_count', 'currency', 'range',
                   'percentage', 'misc'

    Returns:
        True if value contains dynamic content that should be avoided

    Examples:
        >>> contains_dynamic_content("Where to?")
        False  # Static label
        >>> contains_dynamic_content("Dates, Tue, Jan 6 - Thu, Jan 8")
        True   # Contains dates
        >>> contains_dynamic_content("Travelers, 2 travelers, 1 room")
        True   # Contains counts
        >>> contains_dynamic_content("$299 per night")
        True   # Contains currency
        >>> contains_dynamic_content("Search")
        False  # Static label

        # Check only specific categories
        >>> contains_dynamic_content("Jan 6", categories=['date'])
        True
        >>> contains_dynamic_content("Jan 6", categories=['currency'])
        False
    """
    if not value:
        return False

    if categories is None:
        # Check all patterns
        for pattern in _get_compiled_patterns():
            if pattern.search(value):
                return True
        return False
    else:
        # Check only specified categories
        for category in categories:
            for pattern in _get_compiled_category(category):
                if pattern.search(value):
                    return True
        return False


def get_dynamic_content_matches(value: str) -> List[Tuple[str, str]]:
    """
    Find all dynamic content matches in a string.

    Useful for debugging or understanding what patterns were detected.

    Args:
        value: The string to check

    Returns:
        List of (category, matched_text) tuples

    Examples:
        >>> get_dynamic_content_matches("Dates, Tue, Jan 6 - Thu, Jan 8")
        [('date', 'Tue'), ('date', 'Jan'), ('date', 'Jan'), ('range', '6 - ')]
    """
    matches = []
    for category, patterns in PATTERN_CATEGORIES.items():
        for pattern_str in patterns:
            pattern = re.compile(pattern_str, re.IGNORECASE)
            for match in pattern.finditer(value):
                matches.append((category, match.group()))
    return matches
