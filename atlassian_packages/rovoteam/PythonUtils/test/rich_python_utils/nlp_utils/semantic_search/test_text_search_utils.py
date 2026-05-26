"""
Unit tests for shared text search utilities (tokenize, term_overlap_search).
"""

import pytest

from python_utils.nlp_utils.semantic_search import tokenize, term_overlap_search, _stem_word


# ── tokenize tests ──────────────────────────────────────────────────────


class TestTokenize:
    """Tests for the tokenize function."""

    def test_simple_words(self):
        assert tokenize("hello world") == ["hello", "world"]

    def test_case_folding(self):
        assert tokenize("Hello WORLD") == ["hello", "world"]

    def test_punctuation_stripping(self):
        assert tokenize("hello, world!") == ["hello", "world"]

    def test_hyphenated_word_joined(self):
        # Hyphens are stripped, word becomes single token
        assert tokenize("hello-world") == ["helloworld"]

    def test_empty_string(self):
        assert tokenize("") == []

    def test_whitespace_only(self):
        assert tokenize("   ") == []

    def test_pure_punctuation(self):
        assert tokenize("!!! ??? ...") == []

    def test_numbers_preserved(self):
        assert tokenize("item42 price99") == ["item42", "price99"]

    def test_mixed_content(self):
        assert tokenize("Alice's 3-day trip!") == ["alices", "3day", "trip"]

    def test_tabs_and_newlines(self):
        assert tokenize("hello\tworld\nfoo") == ["hello", "world", "foo"]


# ── term_overlap_search tests ───────────────────────────────────────────


class TestTermOverlapSearch:
    """Tests for the term_overlap_search function."""

    def _make_items(self, texts):
        """Create simple (id, text) tuples for testing."""
        return [(f"item_{i}", text) for i, text in enumerate(texts)]

    def _text_fn(self, item):
        return item[1]

    def _id_fn(self, item):
        return item[0]

    def test_basic_match(self):
        items = self._make_items(["alice likes cats", "bob likes dogs"])
        results = term_overlap_search(
            items, ["alice"], self._text_fn, self._id_fn, top_k=5
        )
        assert len(results) == 1
        assert results[0][0][0] == "item_0"
        assert results[0][1] == 1.0  # 1/1 terms match

    def test_multi_term_scoring(self):
        items = self._make_items([
            "alice likes cats",       # 2/3 match (alice, likes)
            "alice likes dogs",       # 3/3 match (alice, likes, dogs)
            "bob likes dogs",         # 2/3 match (likes, dogs)
        ])
        results = term_overlap_search(
            items, ["alice", "likes", "dogs"], self._text_fn, self._id_fn, top_k=5
        )
        assert len(results) == 3
        assert results[0][0][0] == "item_1"  # 3/3
        assert results[0][1] == pytest.approx(1.0)
        # items 0 and 2 both score 2/3, sorted by id
        assert results[1][0][0] == "item_0"
        assert results[1][1] == pytest.approx(2 / 3)
        assert results[2][0][0] == "item_2"
        assert results[2][1] == pytest.approx(2 / 3)

    def test_zero_score_excluded(self):
        items = self._make_items(["alice", "bob"])
        results = term_overlap_search(
            items, ["charlie"], self._text_fn, self._id_fn, top_k=5
        )
        assert results == []

    def test_empty_items(self):
        results = term_overlap_search(
            [], ["alice"], self._text_fn, self._id_fn, top_k=5
        )
        assert results == []

    def test_empty_query_tokens(self):
        items = self._make_items(["alice"])
        results = term_overlap_search(
            items, [], self._text_fn, self._id_fn, top_k=5
        )
        assert results == []

    def test_top_k_limits_results(self):
        items = self._make_items([f"common word {i}" for i in range(10)])
        results = term_overlap_search(
            items, ["common"], self._text_fn, self._id_fn, top_k=3
        )
        assert len(results) == 3

    def test_deterministic_sort_by_id(self):
        """Items with equal scores should be sorted by id_fn for determinism."""
        items = self._make_items(["alice bob", "alice carol"])
        results = term_overlap_search(
            items, ["alice"], self._text_fn, self._id_fn, top_k=5
        )
        assert len(results) == 2
        # Both have score 0.5 (1/1 match), sorted by id
        assert results[0][0][0] == "item_0"
        assert results[1][0][0] == "item_1"


# ── Stemming tests ────────────────────────────────────────────────────────


class TestStemWord:
    """Tests for the _stem_word function."""

    def test_prices_to_price(self):
        assert _stem_word("prices") == _stem_word("price")

    def test_pricing_to_price(self):
        assert _stem_word("pricing") == _stem_word("price")

    def test_shopping_double_consonant(self):
        """Double-consonant reduction: shopping → shop."""
        result = _stem_word("shopping")
        assert result == "shop"

    def test_running_double_consonant(self):
        """Double-consonant reduction: running → run."""
        result = _stem_word("running")
        assert result == "run"

    def test_shopped_double_consonant(self):
        """Double-consonant reduction for -ed: shopped → shop."""
        result = _stem_word("shopped")
        assert result == "shop"

    def test_short_word_unchanged(self):
        assert _stem_word("cat") == "cat"

    def test_ied_suffix_stems(self):
        # "carried" should stem differently from the raw word
        assert _stem_word("carried") != "carried"

    def test_ies_suffix_stems(self):
        # "flies" should stem differently from the raw word
        assert _stem_word("flies") != "flies"


class TestTokenizeStemming:
    """Tests for tokenize with stem parameter."""

    def test_stem_disabled_by_default(self):
        assert tokenize("prices") == ["prices"]

    def test_stem_enabled(self):
        stemmed = tokenize("prices", stem=True)
        assert len(stemmed) == 1
        assert stemmed == tokenize("price", stem=True)

    def test_stem_multiple_words(self):
        stemmed = tokenize("shopping prices", stem=True)
        unstemmed = tokenize("shop price", stem=True)
        assert stemmed == unstemmed


class TestTermOverlapWithStemming:
    """Tests for term_overlap_search with stemming enabled."""

    def _make_items(self, texts):
        return [(f"item_{i}", text) for i, text in enumerate(texts)]

    def _text_fn(self, item):
        return item[1]

    def _id_fn(self, item):
        return item[0]

    def test_stemming_improves_match(self):
        """'prices' should match 'price comparison' when stem=True."""
        items = self._make_items(["price comparison tool", "color picker"])
        query_tokens = tokenize("best prices", stem=True)
        results = term_overlap_search(
            items, query_tokens, self._text_fn, self._id_fn,
            top_k=5, stem=True,
        )
        assert len(results) == 1
        assert results[0][0][0] == "item_0"

    def test_no_stemming_misses_match(self):
        """Without stemming, 'prices' does NOT match 'price'."""
        items = self._make_items(["price comparison tool", "color picker"])
        query_tokens = tokenize("best prices", stem=False)
        results = term_overlap_search(
            items, query_tokens, self._text_fn, self._id_fn,
            top_k=5, stem=False,
        )
        assert len(results) == 0
