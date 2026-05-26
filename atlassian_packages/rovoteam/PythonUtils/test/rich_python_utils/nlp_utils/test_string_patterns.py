"""
Unit Tests for String Pattern Detection Module

Tests the pattern detection functions that identify dynamic/personalized
content in strings - dates, times, counts, currency, etc.

These patterns are used to detect unstable attribute values that should
not be used in XPath selectors or other stable identifiers.
"""

import sys
from pathlib import Path

# Configuration
PIVOT_FOLDER_NAME = 'test'

# Get absolute path to this file
current_file = Path(__file__).resolve()

# Navigate up to find the pivot folder (test directory)
current_path = current_file.parent
while current_path.name != PIVOT_FOLDER_NAME and current_path.parent != current_path:
    current_path = current_path.parent

if current_path.name != PIVOT_FOLDER_NAME:
    raise RuntimeError(f"Could not find '{PIVOT_FOLDER_NAME}' folder in path hierarchy")

# Project root is parent of test/ directory
project_root = current_path.parent

# Add src directory to path
src_dir = project_root / "src"
if src_dir.exists() and str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

import pytest
from python_utils.nlp_utils.string_patterns import (
    contains_dynamic_content,
    contains_date,
    contains_time,
    contains_count_with_unit,
    contains_currency,
    contains_numeric_range,
    contains_percentage,
    get_dynamic_content_matches,
)


# =============================================================================
# Test Date Detection
# =============================================================================

class TestContainsDate:
    """Tests for date pattern detection."""

    def test_abbreviated_day_names_detected(self):
        """Abbreviated day names should be detected."""
        assert contains_date("Mon") is True
        assert contains_date("Tue, Jan 6") is True
        assert contains_date("Wed - Fri") is True
        assert contains_date("Sat") is True
        assert contains_date("Sun") is True

    def test_full_day_names_detected(self):
        """Full day names should be detected."""
        assert contains_date("Monday") is True
        assert contains_date("Tuesday meeting") is True
        assert contains_date("Every Wednesday") is True

    def test_abbreviated_month_names_detected(self):
        """Abbreviated month names should be detected."""
        assert contains_date("Jan 6") is True
        assert contains_date("Feb 14") is True
        assert contains_date("Dec 25") is True
        assert contains_date("Mar - Apr") is True

    def test_full_month_names_detected(self):
        """Full month names should be detected."""
        assert contains_date("January") is True
        assert contains_date("February 14th") is True
        assert contains_date("December holidays") is True

    def test_date_formats_detected(self):
        """Various date formats should be detected."""
        # MM/DD/YYYY
        assert contains_date("01/06/2024") is True
        assert contains_date("Check-in: 12/25/2024") is True
        # YYYY-MM-DD (ISO)
        assert contains_date("2024-01-06") is True
        # DD.MM.YYYY (European)
        assert contains_date("06.01.2024") is True
        # Day Month format
        assert contains_date("6 Jan") is True
        assert contains_date("25 Dec") is True

    def test_static_labels_not_detected(self):
        """Static labels without dates should not be detected."""
        assert contains_date("Where to?") is False
        assert contains_date("Search") is False
        assert contains_date("Select dates") is False
        assert contains_date("Check availability") is False
        assert contains_date("Book now") is False


# =============================================================================
# Test Time Detection
# =============================================================================

class TestContainsTime:
    """Tests for time pattern detection."""

    def test_12_hour_format_detected(self):
        """12-hour time format should be detected."""
        assert contains_time("10:30 AM") is True
        assert contains_time("2:00 pm") is True
        assert contains_time("12:00 PM") is True
        assert contains_time("Departure at 8:45 AM") is True

    def test_24_hour_format_detected(self):
        """24-hour time format should be detected."""
        assert contains_time("14:30") is True
        assert contains_time("08:00") is True
        assert contains_time("Flight at 23:59") is True

    def test_time_with_seconds_detected(self):
        """Time with seconds should be detected."""
        assert contains_time("14:30:00") is True
        assert contains_time("08:00:30") is True

    def test_hour_only_with_ampm_detected(self):
        """Hour with AM/PM (without minutes) should be detected."""
        assert contains_time("10 AM") is True
        assert contains_time("2 pm") is True

    def test_static_labels_not_detected(self):
        """Static labels without times should not be detected."""
        assert contains_time("Select time") is False
        assert contains_time("Time zone") is False
        assert contains_time("Check-in time") is False


# =============================================================================
# Test Count + Unit Detection
# =============================================================================

class TestContainsCountWithUnit:
    """Tests for count + unit pattern detection."""

    def test_travel_counts_detected(self):
        """Travel-related counts should be detected."""
        assert contains_count_with_unit("2 travelers") is True
        assert contains_count_with_unit("1 traveler") is True
        assert contains_count_with_unit("3 guests") is True
        assert contains_count_with_unit("2 adults") is True
        assert contains_count_with_unit("1 child") is True
        assert contains_count_with_unit("2 children") is True
        assert contains_count_with_unit("1 room") is True
        assert contains_count_with_unit("3 rooms") is True
        assert contains_count_with_unit("5 nights") is True
        assert contains_count_with_unit("7 days") is True
        assert contains_count_with_unit("4 passengers") is True

    def test_shopping_counts_detected(self):
        """Shopping-related counts should be detected."""
        assert contains_count_with_unit("5 items") is True
        assert contains_count_with_unit("1 item in cart") is True
        assert contains_count_with_unit("100 results") is True
        assert contains_count_with_unit("25 reviews") is True
        assert contains_count_with_unit("4 stars") is True

    def test_general_counts_detected(self):
        """General counts should be detected."""
        assert contains_count_with_unit("10 messages") is True
        assert contains_count_with_unit("5 notifications") is True
        assert contains_count_with_unit("1000 followers") is True
        assert contains_count_with_unit("50 views") is True
        assert contains_count_with_unit("2 hours") is True
        assert contains_count_with_unit("30 minutes") is True

    def test_static_labels_not_detected(self):
        """Static labels without counts should not be detected."""
        assert contains_count_with_unit("Add travelers") is False
        assert contains_count_with_unit("Select room") is False
        assert contains_count_with_unit("View all items") is False
        assert contains_count_with_unit("Guests") is False


# =============================================================================
# Test Currency Detection
# =============================================================================

class TestContainsCurrency:
    """Tests for currency/price pattern detection."""

    def test_dollar_amounts_detected(self):
        """Dollar amounts should be detected."""
        assert contains_currency("$299") is True
        assert contains_currency("$1,299") is True
        assert contains_currency("$299.99") is True
        assert contains_currency("$1,299.99") is True
        assert contains_currency("Price: $50") is True

    def test_euro_amounts_detected(self):
        """Euro amounts should be detected."""
        assert contains_currency("EUR150") is True   # Code format (no space)
        assert contains_currency("EUR 150") is True  # With space
        assert contains_currency("EUR 150.00") is True

    def test_pound_amounts_detected(self):
        """Pound amounts should be detected."""
        assert contains_currency("GBP 99") is True
        assert contains_currency("GBP 99.99") is True

    def test_decimal_prices_detected(self):
        """Decimal prices (without currency symbol) should be detected."""
        assert contains_currency("299.99") is True
        assert contains_currency("Total: 1,299.00") is True

    def test_static_labels_not_detected(self):
        """Static labels without prices should not be detected."""
        assert contains_currency("View prices") is False
        assert contains_currency("Best deals") is False
        assert contains_currency("Price range") is False


# =============================================================================
# Test Numeric Range Detection
# =============================================================================

class TestContainsNumericRange:
    """Tests for numeric range pattern detection."""

    def test_dash_ranges_detected(self):
        """Dash-separated ranges should be detected."""
        assert contains_numeric_range("6-8") is True
        assert contains_numeric_range("10 - 15") is True
        assert contains_numeric_range("1-3 nights") is True

    def test_en_dash_ranges_detected(self):
        """En-dash ranges should be detected."""
        assert contains_numeric_range("6–8") is True

    def test_text_ranges_detected(self):
        """Text ranges (X to Y) should be detected."""
        assert contains_numeric_range("6 to 8") is True
        assert contains_numeric_range("10 to 20") is True

    def test_static_labels_not_detected(self):
        """Static labels without ranges should not be detected."""
        assert contains_numeric_range("Select dates") is False
        assert contains_numeric_range("Price range") is False


# =============================================================================
# Test Percentage Detection
# =============================================================================

class TestContainsPercentage:
    """Tests for percentage pattern detection."""

    def test_percentage_symbol_detected(self):
        """Percentage with % symbol should be detected."""
        assert contains_percentage("50%") is True
        assert contains_percentage("25% off") is True
        assert contains_percentage("Save 10%") is True
        assert contains_percentage("99.9%") is True

    def test_percentage_word_detected(self):
        """Percentage with word should be detected."""
        assert contains_percentage("50 percent") is True
        assert contains_percentage("25 percent off") is True

    def test_static_labels_not_detected(self):
        """Static labels without percentages should not be detected."""
        assert contains_percentage("Best deals") is False
        assert contains_percentage("Discount") is False


# =============================================================================
# Test Main Function: contains_dynamic_content
# =============================================================================

class TestContainsDynamicContent:
    """Tests for the main dynamic content detection function."""

    def test_date_content_detected(self):
        """Date-containing strings should be detected."""
        assert contains_dynamic_content("Tue, Jan 6") is True
        assert contains_dynamic_content("Mon, Dec 25 - Fri, Dec 29") is True
        assert contains_dynamic_content("01/06/2024") is True
        assert contains_dynamic_content("2024-01-06") is True

    def test_time_content_detected(self):
        """Time-containing strings should be detected."""
        assert contains_dynamic_content("Departure: 10:30 AM") is True
        assert contains_dynamic_content("Arrival at 14:00") is True

    def test_count_content_detected(self):
        """Count-containing strings should be detected."""
        assert contains_dynamic_content("2 travelers") is True
        assert contains_dynamic_content("1 room") is True
        assert contains_dynamic_content("3 nights") is True
        assert contains_dynamic_content("5 guests") is True

    def test_currency_content_detected(self):
        """Currency-containing strings should be detected."""
        assert contains_dynamic_content("$299") is True
        assert contains_dynamic_content("Total: 150.00") is True

    def test_range_content_detected(self):
        """Range-containing strings should be detected."""
        assert contains_dynamic_content("Jan 6 - Jan 8") is True
        assert contains_dynamic_content("2-3 nights") is True

    def test_percentage_content_detected(self):
        """Percentage-containing strings should be detected."""
        assert contains_dynamic_content("50% off") is True
        assert contains_dynamic_content("Save 25%") is True

    def test_static_labels_not_detected(self):
        """Static labels should NOT be detected as dynamic."""
        assert contains_dynamic_content("Where to?") is False
        assert contains_dynamic_content("Search") is False
        assert contains_dynamic_content("Destinations") is False
        assert contains_dynamic_content("Check availability") is False
        assert contains_dynamic_content("Book now") is False
        assert contains_dynamic_content("Sign in") is False
        assert contains_dynamic_content("Create account") is False
        assert contains_dynamic_content("Add travelers") is False
        assert contains_dynamic_content("Select dates") is False
        assert contains_dynamic_content("View prices") is False

    def test_category_filtering(self):
        """Should be able to filter by specific categories."""
        # Date string - detected by date category
        assert contains_dynamic_content("Jan 6", categories=['date']) is True
        assert contains_dynamic_content("Jan 6", categories=['currency']) is False

        # Currency string - detected by currency category
        assert contains_dynamic_content("$299", categories=['currency']) is True
        assert contains_dynamic_content("$299", categories=['date']) is False

    def test_empty_string(self):
        """Empty string should return False."""
        assert contains_dynamic_content("") is False
        assert contains_dynamic_content(None) is False  # type: ignore


# =============================================================================
# Test Expedia-style Button Labels
# =============================================================================

class TestExpediaButtonLabels:
    """Tests specifically for Expedia-style button aria-labels."""

    def test_where_to_is_static(self):
        """'Where to?' button label should be static."""
        assert contains_dynamic_content("Where to?") is False

    def test_dates_button_is_dynamic(self):
        """Dates button with actual dates should be dynamic."""
        assert contains_dynamic_content("Dates, Tue, Jan 6 - Thu, Jan 8") is True

    def test_travelers_button_is_dynamic(self):
        """Travelers button with counts should be dynamic."""
        assert contains_dynamic_content("Travelers, 2 travelers, 1 room") is True

    def test_search_is_static(self):
        """Search button should be static."""
        assert contains_dynamic_content("Search") is False

    def test_flights_tab_is_static(self):
        """Flights tab label should be static."""
        assert contains_dynamic_content("Flights") is False

    def test_hotels_tab_is_static(self):
        """Hotels tab label should be static."""
        assert contains_dynamic_content("Hotels") is False


# =============================================================================
# Test Match Reporting
# =============================================================================

class TestGetDynamicContentMatches:
    """Tests for the match reporting function."""

    def test_returns_all_matches(self):
        """Should return all detected patterns with categories."""
        matches = get_dynamic_content_matches("Tue, Jan 6 - $299")
        # Should find at least day, month, and currency
        categories = [m[0] for m in matches]
        assert 'date' in categories
        assert 'currency' in categories

    def test_empty_for_static_content(self):
        """Should return empty list for static content."""
        matches = get_dynamic_content_matches("Search flights")
        assert len(matches) == 0

    def test_multiple_same_category(self):
        """Should find multiple matches in same category."""
        matches = get_dynamic_content_matches("Mon - Fri")
        date_matches = [m for m in matches if m[0] == 'date']
        assert len(date_matches) >= 2  # Mon and Fri


# =============================================================================
# Test Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_partial_word_not_matched(self):
        """Partial words should not trigger false positives."""
        # "Monday" contains "Mon" but we use word boundaries
        assert contains_date("Monetary") is False
        assert contains_date("Augment") is False  # Contains "Aug"

    def test_case_insensitive(self):
        """Detection should be case-insensitive."""
        assert contains_date("JAN 6") is True
        assert contains_date("jan 6") is True
        assert contains_time("10:30 am") is True
        assert contains_time("10:30 AM") is True

    def test_number_alone_not_detected(self):
        """Numbers alone (without units) should not be detected as counts."""
        # Note: This may trigger range detection if formatted as X-Y
        assert contains_count_with_unit("42") is False
        assert contains_count_with_unit("Select 2") is False

    def test_long_text_with_dynamic_content(self):
        """Should detect dynamic content in longer text."""
        long_text = (
            "Your trip from New York to Los Angeles on Tue, Jan 6 "
            "includes 2 travelers, 1 room for $299 per night"
        )
        assert contains_dynamic_content(long_text) is True
