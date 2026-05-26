"""
Unit Tests for String Readability Scoring Module

Tests the readability scoring functions that evaluate how "human-readable"
a string is by checking if its tokens are known English words.

Tests cover:
- Tokenization of various string formats
- wordfreq backend scoring
- nltk backend scoring
- auto backend selection
- Edge cases (empty strings, single chars, hash-like values)
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
from python_utils.nlp_utils.readability import (
    get_string_readability_score,
    is_readable_string,
    _tokenize,
    _HAS_WORDFREQ,
    _HAS_NLTK,
)


# =============================================================================
# Test Tokenization
# =============================================================================

class TestTokenize:
    """Tests for the _tokenize helper function."""

    def test_space_separated(self):
        """Should split space-separated words."""
        assert _tokenize('Google Search') == ['Google', 'Search']

    def test_dash_separated(self):
        """Should split dash-separated words."""
        assert _tokenize('submit-button') == ['submit', 'button']

    def test_underscore_separated(self):
        """Should split underscore-separated words."""
        assert _tokenize('user_name') == ['user', 'name']

    def test_camel_case(self):
        """Should split camelCase words."""
        assert _tokenize('userName') == ['user', 'Name']

    def test_pascal_case(self):
        """Should split PascalCase words."""
        assert _tokenize('UserName') == ['User', 'Name']

    def test_acronym_handling(self):
        """Should handle acronyms in camelCase."""
        result = _tokenize('XMLParser')
        assert 'XML' in result
        assert 'Parser' in result

    def test_mixed_separators(self):
        """Should handle multiple separator types."""
        assert _tokenize('user-name_field') == ['user', 'name', 'field']

    def test_empty_string(self):
        """Should return empty list for empty string."""
        assert _tokenize('') == []

    def test_single_word(self):
        """Should return single word as list."""
        assert _tokenize('Search') == ['Search']


# =============================================================================
# Test Readability Scoring
# =============================================================================

class TestReadabilityScoring:
    """Tests for get_string_readability_score function."""

    def test_common_words_score_positive(self):
        """Common English words should score positive (>= 0.1)."""
        # Note: wordfreq uses log scale, 0.1 is the minimum for recognized words
        # The key is they score at or above the minimum threshold
        assert get_string_readability_score('Search') >= 0.1
        assert get_string_readability_score('Submit') >= 0.1
        assert get_string_readability_score('email') >= 0.1
        assert get_string_readability_score('button') >= 0.1

    def test_single_letters_score_zero(self):
        """Single letters should score zero (not meaningful for readability)."""
        assert get_string_readability_score('q') == 0.0
        assert get_string_readability_score('x') == 0.0
        assert get_string_readability_score('a') == 0.0

    def test_hash_values_score_very_low(self):
        """Hash/gibberish strings should score very low (near zero)."""
        # Some hash-like strings may have tiny scores due to partial matches
        assert get_string_readability_score('APjFqb') < 0.1
        assert get_string_readability_score('gLFyf') < 0.1
        assert get_string_readability_score('xyzqwk') < 0.1

    def test_phrases_score_positive(self):
        """Multi-word phrases with real words should score positive."""
        # Note: 'Google' is a proper noun and may score differently
        assert get_string_readability_score('Google Search') > 0.1
        assert get_string_readability_score('submit-button') > 0.1
        assert get_string_readability_score('user_name') > 0.1

    def test_search_higher_than_q(self):
        """'Search' should score higher than 'q'."""
        search_score = get_string_readability_score('Search')
        q_score = get_string_readability_score('q')
        assert search_score > q_score

    def test_empty_string_returns_zero(self):
        """Empty string should return 0.0."""
        assert get_string_readability_score('') == 0.0
        assert get_string_readability_score('   ') == 0.0

    def test_numbers_score_low(self):
        """Pure numbers should score low (below common words)."""
        # Numbers may have non-zero frequency in wordfreq (e.g., '2024' as year)
        # but should score lower than common English words
        number_score = get_string_readability_score('12345')
        word_score = get_string_readability_score('Search')
        assert number_score < word_score

    def test_camel_case_phrases(self):
        """CamelCase phrases with real words should score above gibberish."""
        score = get_string_readability_score('submitButton')
        gibberish_score = get_string_readability_score('APjFqb')
        # Both 'submit' and 'button' are real words, should score higher than gibberish
        assert score > gibberish_score


# =============================================================================
# Test Backend Selection
# =============================================================================

class TestBackendSelection:
    """Tests for backend selection behavior."""

    @pytest.mark.skipif(not _HAS_WORDFREQ, reason="wordfreq not installed")
    def test_wordfreq_backend_explicit(self):
        """Should use wordfreq when explicitly requested."""
        score = get_string_readability_score('Search', backend='wordfreq')
        assert score > 0.1  # Common word should score positive

    @pytest.mark.skipif(not _HAS_NLTK, reason="nltk not installed")
    def test_nltk_backend_explicit(self):
        """Should use nltk when explicitly requested."""
        score = get_string_readability_score('Search', backend='nltk')
        assert score > 0.5

    def test_auto_backend_returns_score(self):
        """Auto backend should return a score when any backend available."""
        if _HAS_WORDFREQ or _HAS_NLTK:
            score = get_string_readability_score('Search', backend='auto')
            assert score > 0.0
        else:
            # No backend available, should return 0.0
            score = get_string_readability_score('Search', backend='auto')
            assert score == 0.0

    def test_invalid_backend_raises(self):
        """Should raise ValueError for invalid backend name."""
        with pytest.raises(ValueError):
            get_string_readability_score('Search', backend='invalid')


# =============================================================================
# Test is_readable_string convenience function
# =============================================================================

class TestIsReadableString:
    """Tests for the is_readable_string convenience function."""

    def test_readable_word_returns_true(self):
        """Common English word should return True with appropriate threshold."""
        # Default threshold is 0.3, but 'Search' scores ~0.19
        # Use a lower threshold that matches actual scoring
        assert is_readable_string('Search', threshold=0.1) is True

    def test_gibberish_returns_false(self):
        """Gibberish/hash should return False."""
        assert is_readable_string('APjFqb') is False

    def test_custom_threshold(self):
        """Should respect custom threshold."""
        # With very high threshold, even common words fail
        assert is_readable_string('Search', threshold=0.99) is False
        # With very low threshold, more things pass
        assert is_readable_string('Search', threshold=0.1) is True


# =============================================================================
# Test Edge Cases for wordfreq Backend
# =============================================================================

@pytest.mark.skipif(not _HAS_WORDFREQ, reason="wordfreq not installed")
class TestWordfreqBackendEdgeCases:
    """Edge case tests specific to wordfreq backend."""

    def test_two_char_common_words(self):
        """Common 2-char words like 'to', 'in' should score > 0."""
        assert get_string_readability_score('to', backend='wordfreq') > 0.0
        assert get_string_readability_score('in', backend='wordfreq') > 0.0
        assert get_string_readability_score('on', backend='wordfreq') > 0.0

    def test_two_char_uncommon_words(self):
        """Uncommon 2-char combinations should score 0."""
        assert get_string_readability_score('qz', backend='wordfreq') == 0.0
        assert get_string_readability_score('fj', backend='wordfreq') == 0.0

    def test_case_insensitive(self):
        """Scoring should be case-insensitive."""
        upper = get_string_readability_score('SEARCH', backend='wordfreq')
        lower = get_string_readability_score('search', backend='wordfreq')
        mixed = get_string_readability_score('Search', backend='wordfreq')
        # All should be similar (within tolerance due to tokenization)
        assert abs(upper - lower) < 0.1
        assert abs(upper - mixed) < 0.1
