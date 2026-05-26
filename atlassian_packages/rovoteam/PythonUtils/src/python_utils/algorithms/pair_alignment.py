from collections import Counter
from functools import partial
from itertools import chain
from itertools import product
from typing import Any, Iterator
from typing import Callable, Iterable, Union, Tuple, Mapping

from python_utils.nlp_utils.metrics.edit_distance import (
    EditDistanceOptions, edit_distance, regular_edit_distance_based_similarity
)
from python_utils.nlp_utils.string_sanitization import (
    StringSanitizationOptions, StringSanitizationConfig
)

"""
The type of a scored pair. A three-tuple consisting of 'score', 'source' and 'target'.
The `score` is not necessarily a numeric value.
"""
SCORED_PAIR = Tuple[
    Any,  # score
    Any,  # source
    Any  # target
]

SCORED_PAIR_POST_PROCESS_FUNC = Callable[[Iterable[SCORED_PAIR]], Iterable[SCORED_PAIR]]


def iter_best_scored_pairs_of_distinct_source(
        scored_pairs: Iterable[SCORED_PAIR],
        enabled_target_items: Union[Iterable, Mapping[Any, int]] = None,
        enabled_source_items: Iterable = None,
        include_all_tie_target_items: bool = True,
        reversed_sort_by_scores: bool = False,
        distinct_output_targets: bool = False,
        identity_score: Any = None
) -> Iterator[SCORED_PAIR]:
    """
    Iterates through the best scored pairs of distinct source items from a sequence of scored pairs.
    Each scored pair is a 3-tuple (score, source, target), see `SCORED_PAIRS`.
    The deduplication of source items is based on the pair scores.

    Args:
        scored_pairs: a seqeunce of 3-tuple objects, where each 3-tuple consists of the score,
            the source item, and the target item.
        enabled_target_items: if specified, then the target items of the returned scored pairs
            should only consist of these specified target items; one target item can be specified
            multiple times, or a counting dictionary can be used to specify how many times a target
            item should occur (when `include_tie_target_items` is False) or at least occur (when
            `include_tie_target_items` is True) in the returned scored pairs.
        enabled_source_items: if specified, then the source items of the returned scored pairs
            should only consist of these specified target items.
        include_all_tie_target_items: True to allow a target item to appear more than the specified
            number of occurrences in `enabled_target_items` if there are pairs with tied scores.
        reversed_sort_by_scores: True to sort the scored pairs by the scores in the reversed order.
        distinct_output_targets: True to ensure the targets in the output (score, source, target)
            scored pairs are distinct. This function `iter_best_scored_pairs_of_distinct_source`
            alreay ensures the uniqueness of sources in the output; setting this argument to True
            ensures the uniqueness of targets.
        identity_score: if specified, then scored pairs with this score will be considered as pairs
            with identical source/target items; if a target item is observed in these identity pairs,
            then non-identity pairs with this target item will be dropped.
    Returns: a iterator of scored pairs of distince source items.

    Examples:
        >>> list(iter_best_scored_pairs_of_distinct_source(
        ...   [
        ...      (0.3, 'ArtistName', 'ArtistName'),
        ...      (0.1, 'ArtistName', 'AlbumName'),
        ...      (0.2, 'SongName', 'AlbumName'),
        ...      (0.3, 'SongName', 'ArtistName')
        ...   ]
        ... ))
        [(0.1, 'ArtistName', 'AlbumName'), (0.2, 'SongName', 'AlbumName')]
        >>> list(iter_best_scored_pairs_of_distinct_source(
        ...   [
        ...      (0.3, 'ArtistName', 'AlbumName'),
        ...      (0.2, 'SongName', 'AlbumName'),
        ...      (0.3, 'SongName', 'ArtistName')
        ...   ]
        ... ))
        [(0.2, 'SongName', 'AlbumName'), (0.3, 'ArtistName', 'AlbumName')]
        >>> list(iter_best_scored_pairs_of_distinct_source(
        ...   [
        ...      (0.3, 'ArtistName', 'AlbumName'),
        ...      (0.2, 'SongName', 'AlbumName'),
        ...      (0.3, 'SongName', 'ArtistName')
        ...   ],
        ...   enabled_target_items=['AlbumName', 'ArtistName']
        ... ))
        [(0.2, 'SongName', 'AlbumName')]
        >>> list(iter_best_scored_pairs_of_distinct_source(
        ...   [
        ...      (0.3, 'ArtistName', 'ArtistName'),
        ...      (0.2, 'SongName', 'AlbumName'),
        ...      (0.3, 'SongName', 'ArtistName')
        ...   ],
        ...   enabled_target_items=['AlbumName', 'ArtistName']
        ... ))
        [(0.2, 'SongName', 'AlbumName'), (0.3, 'ArtistName', 'ArtistName')]
        >>> list(iter_best_scored_pairs_of_distinct_source(
        ...   [
        ...      (0.3, 'ArtistName', 'ArtistName'),
        ...      (0.1, 'ArtistName', 'AlbumName'),
        ...      (0.2, 'SongName', 'ArtistName'),
        ...      (0.3, 'AppName', 'ArtistName')
        ...   ],
        ...   enabled_target_items=['AlbumName', 'ArtistName', 'ArtistName']
        ... ))
        [(0.1, 'ArtistName', 'AlbumName'), (0.2, 'SongName', 'ArtistName'), (0.3, 'AppName', 'ArtistName')]
        >>> list(iter_best_scored_pairs_of_distinct_source(
        ...   [
        ...      (0.3, 'ArtistName', 'ArtistName'),
        ...      (0.1, 'ServiceName', 'AlbumName'),
        ...      (0.2, 'SongName', 'ArtistName'),
        ...      (0.2, 'AppName', 'ArtistName')
        ...   ],
        ...   enabled_target_items=['AlbumName', 'ArtistName']
        ... ))
        [(0.1, 'ServiceName', 'AlbumName'), (0.2, 'AppName', 'ArtistName'), (0.2, 'SongName', 'ArtistName')]
        >>> list(iter_best_scored_pairs_of_distinct_source(
        ...   [
        ...      (0.3, 'ArtistName', 'ArtistName'),
        ...      (0.1, 'ServiceName', 'AlbumName'),
        ...      (0.2, 'SongName', 'ArtistName'),
        ...      (0.2, 'AppName', 'ArtistName')
        ...   ],
        ...   enabled_target_items=['AlbumName', 'ArtistName'],
        ...   reversed_sort_by_scores=True,
        ... ))
        [(0.3, 'ArtistName', 'ArtistName'), (0.1, 'ServiceName', 'AlbumName')]
        >>> list(iter_best_scored_pairs_of_distinct_source(
        ...   [
        ...      (0.3, 'ArtistName', 'ArtistName'),
        ...      (0.1, 'ServiceName', 'AlbumName'),
        ...      (0.2, 'SongName', 'ArtistName'),
        ...      (0.2, 'AppName', 'ArtistName')
        ...   ],
        ...   enabled_target_items=['AlbumName', 'ArtistName'],
        ...   include_all_tie_target_items=False
        ... ))
        [(0.1, 'ServiceName', 'AlbumName'), (0.2, 'AppName', 'ArtistName')]
    """

    # Initialize `visited1` set to keep track of visited source items
    visited1 = set()
    if enabled_source_items is not None:
        enabled_source_items = set(enabled_source_items)

    # Define sort key based on whether `enabled_target_items` is provided
    if enabled_target_items is None:
        scored_pairs_sort_key = lambda x: (x[0], x[1], x[2])
    else:
        scored_pairs_sort_key = lambda x: (x[0], x[2], x[1])
        if not isinstance(enabled_target_items, Mapping):
            enabled_target_items = Counter(enabled_target_items)

    # Sort `scored_pairs` based on the sort key and reverse flag
    scored_pairs = sorted(
        scored_pairs,
        key=scored_pairs_sort_key,
        reverse=reversed_sort_by_scores
    )

    # If `identity_score` is provided, initialize visited2 set
    if distinct_output_targets or (identity_score is not None):
        visited2 = set()

    def _iter(_scored_pairs, use_visited2=False):
        returned_pair = None

        # Function to mark an item as visited
        def _mark_visit():
            visited1.add(item1)
            if use_visited2:
                visited2.add(item2)

        # Iterate over the `scored_pairs` and yield the best scored pairs
        for score, item1, item2 in _scored_pairs:
            if (
                    (
                            enabled_source_items is None or
                            item1 in enabled_source_items
                    ) and
                    (
                            item1 not in visited1
                    ) and
                    (
                            not (
                                    use_visited2 and
                                    item2 in visited2
                            )
                    )
            ):
                if enabled_target_items is None:
                    _mark_visit()
                    yield score, item1, item2
                else:
                    if item2 in enabled_target_items:
                        enabled_target_items[item2] -= 1
                        returned_pair = (score, item1, item2)
                        _mark_visit()
                        if enabled_target_items[item2] == 0:
                            del enabled_target_items[item2]
                        yield returned_pair
                    elif (
                            include_all_tie_target_items and
                            returned_pair is not None and
                            returned_pair[0] == score and
                            returned_pair[2] == item2
                    ):
                        returned_pair = (score, item1, item2)
                        _mark_visit()
                        yield returned_pair
                    elif len(enabled_target_items) == 0:
                        break

    if identity_score is None:
        return _iter(scored_pairs, use_visited2=distinct_output_targets)
    else:
        return chain(
            _iter(
                filter(lambda x: x[0] == identity_score, scored_pairs),
                use_visited2=True
            ),
            _iter(
                filter(lambda x: x[0] != identity_score and x[2] not in visited2, scored_pairs),
                use_visited2=distinct_output_targets
            )
        )


def iter_best_pairs_of_distinct_source(
        pairs: Iterable[Tuple[Any, Any]],
        score_func: Callable[[Any, Any], float],
        enabled_target_items: Union[Iterable, Mapping[Any, int]] = None,
        enabled_source_items: Iterable = None,
        include_all_tie_target_items: bool = True,
        reversed_sort_by_scores: bool = False,
        identity_score=None
) -> Iterator[Tuple[Any, Any, Any]]:
    return iter_best_scored_pairs_of_distinct_source(
        scored_pairs=map(lambda x: tuple((score_func(x[0], x[1]), x[0], x[1])), pairs),
        enabled_target_items=enabled_target_items,
        enabled_source_items=enabled_source_items,
        include_all_tie_target_items=include_all_tie_target_items,
        reversed_sort_by_scores=reversed_sort_by_scores,
        identity_score=identity_score
    )


def iter_aligned_pairs_by_edit_distance_with_distinct_source(
    x: Iterable[Any],
    y: Iterable[Any],
    x_str_getter: Callable[[Any], str] = None,
    y_str_getter: Callable[[Any], str] = None,
    enabled_target_items: Union[Iterable, Mapping[Any, int]] = None,
    enabled_source_items: Iterable = None,
    include_all_tie_target_items: bool = True,
    reversed_sort_by_scores: bool = True,
    identity_score: float = None,
    distinct_output_targets: bool = False,
    scored_pairs_post_process: SCORED_PAIR_POST_PROCESS_FUNC = None,
    use_fuzzy_edit_distance: bool = True,
    # region edit distance config
    sanitization_config: Union[
        Iterable[StringSanitizationOptions], StringSanitizationConfig
    ] = None,
    edit_distance_consider_sorted_tokens: Union[bool, Callable] = min,
    edit_distance_options: EditDistanceOptions = None,
    edit_distance_str_preprocess: Callable[[str, str], Tuple[str, str]] = None,
    **edit_distance_kwargs,
    # endregion
) -> Iterator[SCORED_PAIR]:
    """
    Aligns two sequences `x` and `y` by edit-distance based similarities between all possible pairs
    from `x` to `y`.

    The function first applies edit distance to score all possible pairs from `x` to `y`, by
    calling the :func:`edit_distance` function that provides fuzzy capability and customization.

    Then the function calls :func:`iter_best_scored_pairs_of_distinct_source` to align
    the edit-distance-scored pairs from `x` to `y` to find their best alignment.


    Args:
        x: An iterable of source items.
        y: An iterable of target items.
        x_str_getter: A callable that takes an item from x and returns a string representation.
        y_str_getter: A callable that takes an item from y and returns a string representation.
        enabled_target_items: see :func:`iter_best_scored_pairs_of_distinct_source`.
        enabled_source_items: see :func:`iter_best_scored_pairs_of_distinct_source`.
        include_all_tie_target_items: see :func:`iter_best_scored_pairs_of_distinct_source`.
        reversed_sort_by_scores: see :func:`iter_best_scored_pairs_of_distinct_source`.
        identity_score: see :func:`iter_best_scored_pairs_of_distinct_source`.
        distinct_output_targets: see :func:`iter_best_scored_pairs_of_distinct_source`.
        scored_pairs_post_process: provides an optional function tro post-process the
            edit-distance-scored pairs before performing alignment.
        use_fuzzy_edit_distance: True to enable fuzzy edit distance.
        sanitization_config: Configuration for string sanitization during edit distance calculation.
            See :func:`edit_distance`.
        edit_distance_consider_sorted_tokens: Strategy for considering sorted tokens during
            edit distance calculation. See :func:`edit_distance`.
        edit_distance_options: Options for edit distance calculation. See :func:`edit_distance`.
        **edit_distance_kwargs: Additional keyword arguments for edit distance calculation.
            See :func:`edit_distance`.

    Returns:
        An iterator of scored pairs of distinct source items based on edit distance.

    Examples:
        >>> x = ["ArtistName", "SongName", "AppName", "ServiceName"]
        >>> y = ["ArtistName", "AlbumName", "ArtistName"]

        # Basic usage
        >>> pairs = list(iter_aligned_pairs_by_edit_distance_with_distinct_source(x, y))

        # Using x_str_getter and y_str_getter
        >>> pairs = list(iter_aligned_pairs_by_edit_distance_with_distinct_source(
        ...     x, y, x_str_getter=lambda x: x.lower(), y_str_getter=lambda y: y.upper()))

        # Specifying enabled_target_items and enabled_source_items
        >>> pairs = list(iter_aligned_pairs_by_edit_distance_with_distinct_source(
        ...     x, y, enabled_target_items=["AlbumName", "ArtistName"],
        ...     enabled_source_items=["AppName", "ServiceName"]))

        # Customizing edit distance calculation
        >>> pairs = list(iter_aligned_pairs_by_edit_distance_with_distinct_source(
        ...     x, y, edit_distance_options=EditDistanceOptions()))
    """
    if use_fuzzy_edit_distance:
        scored_pairs = (
            (
                edit_distance(
                    (_x if x_str_getter is None else x_str_getter(_x)),
                    (_y if y_str_getter is None else y_str_getter(_y)),
                    consider_sorted_tokens=edit_distance_consider_sorted_tokens,
                    sanitization_config=sanitization_config,
                    options=edit_distance_options,
                    str_preprocess=edit_distance_str_preprocess,
                    **edit_distance_kwargs,
                ),
                _x,
                _y,
            )
            for _x, _y in product(x, y)
        )
    else:
        scored_pairs = (
            (
                regular_edit_distance_based_similarity(
                    (_x if x_str_getter is None else x_str_getter(_x)),
                    (_y if y_str_getter is None else y_str_getter(_y)),
                ),
                _x,
                _y,
            )
            for _x, _y in product(x, y)
        )
    if scored_pairs_post_process is not None:
        scored_pairs = scored_pairs_post_process(scored_pairs)

    best_scored_pairs_of_distinct_source = iter_best_scored_pairs_of_distinct_source(
        scored_pairs,
        enabled_target_items=enabled_target_items,
        enabled_source_items=enabled_source_items,
        include_all_tie_target_items=include_all_tie_target_items,
        reversed_sort_by_scores=reversed_sort_by_scores,
        distinct_output_targets=distinct_output_targets,
        identity_score=identity_score,
    )

    return best_scored_pairs_of_distinct_source

