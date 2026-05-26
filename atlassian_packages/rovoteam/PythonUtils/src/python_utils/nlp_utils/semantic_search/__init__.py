"""
Shared text search utilities for keyword and term-overlap scoring.

Provides a simple tokenizer and a generic term-overlap search function
used by file-based services (FileRetrievalService, FileGraphService)
for development-purpose text matching.

Usage:
    from python_utils.nlp_utils.semantic_search import (
        tokenize,
        term_overlap_search,
    )

    tokens = tokenize("Hello, World!")  # ["hello", "world"]

    results = term_overlap_search(
        items=my_items,
        query_tokens=tokenize("search query"),
        text_fn=lambda item: item.text,
        id_fn=lambda item: item.id,
        top_k=5,
    )
"""

from typing import Callable, List, Tuple, TypeVar

T = TypeVar("T")

# ── Stemmer setup ─────────────────────────────────────────────────────────────
# Try NLTK PorterStemmer (pure Python, no NLTK data downloads needed).
# Fall back to a simple suffix stripper when nltk is unavailable.

_DOUBLE_CONSONANT_ENDINGS = frozenset("bdgmnprst")

try:
    from nltk.stem import PorterStemmer as _PorterStemmer

    _porter = _PorterStemmer()

    def _stem_word(word: str) -> str:
        return _porter.stem(word)

except ImportError:

    def _stem_word(word: str) -> str:  # type: ignore[misc]
        """Minimal suffix stripper when nltk is unavailable."""
        if len(word) <= 3:
            return word
        if word.endswith("ing") and len(word) > 5:
            stem = word[:-3]
            # Double-consonant reduction: "shopping" → "shopp" → "shop"
            if (
                len(stem) >= 2
                and stem[-1] == stem[-2]
                and stem[-1] in _DOUBLE_CONSONANT_ENDINGS
            ):
                stem = stem[:-1]
            # Re-add 'e' for CVC pattern: "pricing" → "pric" → "price"
            elif len(stem) >= 2 and stem[-1] not in "aeiou" and stem[-2] in "aeiou":
                stem = stem + "e"
            return stem
        if word.endswith("ied") and len(word) > 4:
            return word[:-3] + "y"
        if word.endswith("ies") and len(word) > 4:
            return word[:-3] + "y"
        if word.endswith("ed") and len(word) > 4:
            stem = word[:-2]
            # Double-consonant reduction: "shopped" → "shopp" → "shop"
            if (
                len(stem) >= 2
                and stem[-1] == stem[-2]
                and stem[-1] in _DOUBLE_CONSONANT_ENDINGS
            ):
                stem = stem[:-1]
            return stem
        if word.endswith("es") and len(word) > 4:
            pre = word[:-2]
            if pre.endswith(("ch", "sh", "x", "z", "ss")):
                return pre
            return word[:-1]
        if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
            return word[:-1]
        return word


def tokenize(text: str, stem: bool = False) -> List[str]:
    """Tokenize text into lowercase alphanumeric words.

    Splits on whitespace and strips non-alphanumeric characters from each
    token. Empty tokens are discarded.

    Args:
        text: The text to tokenize.
        stem: If True, apply stemming to each token.

    Returns:
        A list of lowercase token strings.
    """
    tokens = []
    for word in text.lower().split():
        cleaned = "".join(ch for ch in word if ch.isalnum())
        if cleaned:
            tokens.append(_stem_word(cleaned) if stem else cleaned)
    return tokens


def term_overlap_search(
    items: List[T],
    query_tokens: List[str],
    text_fn: Callable[[T], str],
    id_fn: Callable[[T], str],
    top_k: int = 5,
    stem: bool = False,
) -> List[Tuple[T, float]]:
    """Score items by term overlap with pre-tokenized query.

    Computes: score = |query_terms ∩ item_terms| / |query_terms|

    Scores are naturally in [0.0, 1.0]. Zero-score items are excluded.
    Results are sorted by score descending, then by id_fn(item) for
    determinism.

    Args:
        items: Candidate items to score.
        query_tokens: Pre-tokenized query terms (caller handles tokenization).
        text_fn: Extracts searchable text from an item.
        id_fn: Extracts a sort-tiebreak ID from an item.
        top_k: Maximum results to return.
        stem: If True, apply stemming when tokenizing item text.

    Returns:
        Sorted list of (item, score) tuples, at most top_k.
    """
    query_terms = set(query_tokens)
    if not query_terms:
        return []
    num_query_terms = len(query_terms)

    scored: List[Tuple[T, float]] = []
    for item in items:
        item_terms = set(tokenize(text_fn(item), stem=stem))
        overlap = len(query_terms & item_terms)
        score = overlap / num_query_terms
        if score > 0.0:
            scored.append((item, score))

    scored.sort(key=lambda x: (-x[1], id_fn(x[0])))
    return scored[:top_k]
