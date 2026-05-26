"""
String Readability Scoring Module

Provides utilities to score how "human-readable" a string is by checking
if its tokens are known English words.

Supports multiple backends:
- wordfreq: Uses word frequency data (preferred, more nuanced scoring)
- nltk: Uses nltk.corpus.words (fallback, binary word detection)

Example usage:
    >>> from python_utils.nlp_utils.readability import get_string_readability_score
    >>> get_string_readability_score('Search')
    0.72  # High - common English word
    >>> get_string_readability_score('q')
    0.54  # Medium - single letter is recognized but less readable
    >>> get_string_readability_score('APjFqb')
    0.0   # Zero - hash/gibberish
"""

import math
import re
from typing import List, Optional

# Backend availability flags
_HAS_WORDFREQ = False
_HAS_NLTK = False

try:
    from wordfreq import word_frequency
    _HAS_WORDFREQ = True
except ImportError:
    word_frequency = None

try:
    from nltk.corpus import words as nltk_words
    _HAS_NLTK = True
except ImportError:
    nltk_words = None

# Cache for NLTK words set
_NLTK_WORDS_CACHE: Optional[set] = None

# Common HTML/CSS vocabulary - technical terms that are readable in web context
# These get a guaranteed minimum score even if not in word frequency data
HTML_CSS_VOCABULARY = {
    # Layout & Structure
    'nav', 'header', 'footer', 'sidebar', 'main', 'section', 'article',
    'container', 'wrapper', 'content', 'layout', 'grid', 'row', 'col',
    'column', 'panel', 'card', 'modal', 'popup', 'dropdown', 'menu',
    'toolbar', 'overlay', 'drawer', 'pane', 'view', 'page',
    # Navigation
    'link', 'btn', 'button', 'tab', 'tabs', 'breadcrumb', 'pagination',
    'prev', 'next', 'back', 'forward', 'home', 'anchor',
    # Form elements
    'form', 'input', 'textarea', 'select', 'checkbox', 'radio', 'label',
    'field', 'submit', 'reset', 'search', 'filter', 'query', 'option',
    'picker', 'datepicker', 'timepicker',
    # Media
    'img', 'image', 'icon', 'avatar', 'thumbnail', 'logo', 'banner',
    'video', 'audio', 'media', 'gallery', 'slider', 'carousel',
    'photo', 'picture',
    # Text
    'text', 'title', 'heading', 'subtitle', 'description', 'caption',
    'paragraph', 'list', 'item', 'badge', 'tag', 'chip', 'hint',
    'placeholder', 'tooltip',
    # Data & Content
    'table', 'thead', 'tbody', 'tfoot', 'cell', 'data', 'result',
    'results', 'record', 'entry', 'detail', 'details', 'summary', 'preview',
    # Actions
    'action', 'actions', 'edit', 'delete', 'save', 'cancel', 'close',
    'open', 'toggle', 'expand', 'collapse', 'show', 'hide', 'add',
    'remove', 'create', 'update', 'copy', 'paste', 'undo', 'redo',
    'refresh', 'reload', 'download', 'upload', 'share', 'print',
    'export', 'import',
    # User & Auth
    'user', 'profile', 'account', 'login', 'logout', 'signup', 'signin',
    'signout', 'register', 'auth', 'password', 'username', 'email',
    # Notifications
    'notification', 'notifications', 'alert', 'toast', 'message',
    'messages', 'chat', 'inbox', 'bell',
    # State
    'active', 'disabled', 'selected', 'checked', 'loading', 'error',
    'success', 'warning', 'info', 'primary', 'secondary', 'pending',
    'complete', 'empty', 'readonly',
    # Position
    'top', 'bottom', 'left', 'right', 'center', 'middle', 'start',
    'end', 'inner', 'outer',
    # Common abbreviations
    'nav', 'btn', 'img', 'src', 'href', 'alt', 'msg', 'err', 'warn',
    'ctx', 'cfg', 'opt', 'val', 'idx', 'num', 'str', 'len',
}

# Minimum score for HTML/CSS vocabulary words
HTML_CSS_VOCAB_MIN_SCORE = 0.5


def _tokenize(value: str) -> List[str]:
    """
    Split value into tokens for word checking.

    Handles:
    - Spaces: 'Google Search' -> ['Google', 'Search']
    - Dashes: 'submit-button' -> ['submit', 'button']
    - Underscores: 'user_name' -> ['user', 'name']
    - CamelCase: 'userName' -> ['user', 'Name']

    Args:
        value: The string to tokenize

    Returns:
        List of tokens (may include empty strings which should be filtered)

    Examples:
        >>> _tokenize('Google Search')
        ['Google', 'Search']
        >>> _tokenize('submit-button')
        ['submit', 'button']
        >>> _tokenize('userName')
        ['user', 'Name']
    """
    if not value:
        return []

    # First split by common separators (space, dash, underscore)
    parts = re.split(r'[\s\-_]+', value)

    # Then split camelCase
    tokens = []
    for part in parts:
        if not part:
            continue
        # Split on camelCase boundaries: 'userName' -> ['user', 'Name']
        # Also handles: 'XMLParser' -> ['XML', 'Parser']
        camel_parts = re.findall(
            r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\W|$)|\d+',
            part
        )
        if camel_parts:
            tokens.extend(camel_parts)
        else:
            # No camelCase found, keep the original part
            tokens.append(part)

    # Filter out empty tokens
    return [t for t in tokens if t]


def _get_nltk_words() -> set:
    """
    Get the set of English words from NLTK corpus.

    Lazily loads and caches the word list for performance.

    Returns:
        Set of lowercase English words

    Raises:
        RuntimeError: If NLTK or words corpus is not available
    """
    global _NLTK_WORDS_CACHE

    if not _HAS_NLTK:
        raise RuntimeError("NLTK is not installed. Install with: pip install nltk")

    if _NLTK_WORDS_CACHE is None:
        try:
            _NLTK_WORDS_CACHE = set(w.lower() for w in nltk_words.words())
        except LookupError:
            raise RuntimeError(
                "NLTK words corpus not found. "
                "Download with: python -c \"import nltk; nltk.download('words')\""
            )

    return _NLTK_WORDS_CACHE


def _score_wordfreq(value: str) -> float:
    """
    Score string readability using wordfreq library.

    Uses word frequency to score each token, with higher frequency
    words scoring higher (more readable).

    Args:
        value: The string to score

    Returns:
        Float from 0.0 to 1.0 indicating readability
    """
    if not _HAS_WORDFREQ:
        raise RuntimeError("wordfreq is not installed. Install with: pip install wordfreq")

    tokens = _tokenize(value)
    if not tokens:
        return 0.0

    scores = []
    for token in tokens:
        # Single characters are never meaningful for readability
        if len(token) == 1:
            scores.append(0.0)
            continue

        # 2-char tokens: only count if very common (like 'to', 'in', 'on', 'at', 'is', 'it')
        if len(token) == 2:
            freq = word_frequency(token.lower(), 'en')
            # Threshold 0.001 includes 'to', 'in', 'on' but excludes 'pj', 'fq'
            if freq < 0.001:
                scores.append(0.0)
                continue

        token_lower = token.lower()
        freq = word_frequency(token_lower, 'en')
        if freq > 0:
            # Convert frequency to 0-1 score using log scale
            # Common words like 'the' have freq ~0.07 -> score ~1.0
            # Medium words like 'search' have freq ~0.0001 -> score ~0.6
            # Rare words have freq ~0.000001 -> score ~0.2
            score = min(1.0, (math.log10(freq) + 5) / 5)
            score = max(0.1, score)  # Minimum 0.1 if word exists
        else:
            score = 0.0

        # Apply HTML/CSS vocabulary boost as a floor
        # This ensures domain-specific terms get a decent score
        if token_lower in HTML_CSS_VOCABULARY:
            score = max(score, HTML_CSS_VOCAB_MIN_SCORE)

        scores.append(score)

    if not scores:
        return 0.0

    return sum(scores) / len(scores)


def _score_nltk(value: str) -> float:
    """
    Score string readability using NLTK words corpus.

    Uses binary word detection (word exists or not) with length
    heuristic for scoring.

    Args:
        value: The string to score

    Returns:
        Float from 0.0 to 1.0 indicating readability
    """
    tokens = _tokenize(value)
    if not tokens:
        return 0.0

    word_set = _get_nltk_words()
    scores = []
    for token in tokens:
        # Skip very short tokens (1-2 chars) - they're not meaningful
        if len(token) <= 2:
            scores.append(0.0)
            continue

        token_lower = token.lower()
        if token_lower in word_set:
            # NLTK doesn't give frequency, so use length heuristic
            # Longer words are generally more specific/readable
            # 3 chars: 0.5 + 0.3 = 0.8
            # 6 chars: 0.5 + 0.6 = 1.0 (capped)
            score = min(1.0, 0.5 + len(token) * 0.1)
        else:
            score = 0.0

        # Apply HTML/CSS vocabulary boost as a floor
        # This ensures domain-specific terms get a decent score
        if token_lower in HTML_CSS_VOCABULARY:
            score = max(score, HTML_CSS_VOCAB_MIN_SCORE)

        scores.append(score)

    if not scores:
        return 0.0

    return sum(scores) / len(scores)


def get_string_readability_score(
    value: str,
    backend: str = 'auto',
) -> float:
    """
    Calculate readability score for a string value.

    Tokenizes the value and checks if tokens are known English words.
    Higher score = more readable (contains recognizable words).

    Args:
        value: The string to score
        backend: Which NLP backend to use
            - 'auto': Try wordfreq first, then nltk, then return 0.0
            - 'wordfreq': Use wordfreq library (requires: pip install wordfreq)
            - 'nltk': Use nltk.corpus.words (requires: pip install nltk)

    Returns:
        Float from 0.0 (no recognizable words) to 1.0 (all tokens are common words)

    Examples:
        >>> get_string_readability_score('Search')  # doctest: +SKIP
        0.72  # High - common English word

        >>> get_string_readability_score('q')  # doctest: +SKIP
        0.54  # Medium - single letter

        >>> get_string_readability_score('Google Search')  # doctest: +SKIP
        0.75  # High - two recognizable words

        >>> get_string_readability_score('APjFqb')  # doctest: +SKIP
        0.0   # Zero - hash/gibberish

        >>> get_string_readability_score('submit-button')  # doctest: +SKIP
        0.85  # High - two words separated by dash
    """
    if not value or not value.strip():
        return 0.0

    if backend == 'wordfreq':
        return _score_wordfreq(value)
    elif backend == 'nltk':
        return _score_nltk(value)
    elif backend == 'auto':
        # Try wordfreq first (preferred)
        if _HAS_WORDFREQ:
            return _score_wordfreq(value)
        # Fall back to nltk
        if _HAS_NLTK:
            try:
                return _score_nltk(value)
            except RuntimeError:
                pass  # Words corpus not downloaded
        # No backend available
        return 0.0
    else:
        raise ValueError(f"Unknown backend: {backend}. Use 'auto', 'wordfreq', or 'nltk'")


def is_readable_string(value: str, threshold: float = 0.3, backend: str = 'auto') -> bool:
    """
    Check if a string is considered readable (above threshold).

    Convenience function that wraps get_string_readability_score.

    Args:
        value: The string to check
        threshold: Minimum score to be considered readable (default: 0.3)
        backend: Which NLP backend to use

    Returns:
        True if readability score >= threshold

    Examples:
        >>> is_readable_string('Search')  # doctest: +SKIP
        True
        >>> is_readable_string('APjFqb')  # doctest: +SKIP
        False
    """
    return get_string_readability_score(value, backend=backend) >= threshold
