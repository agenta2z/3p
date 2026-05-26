from typing import Iterable, Callable, Mapping
import heapq


def top_k_similar(query, values: Iterable, key: Callable = None, top: int = 1, scorer: Callable = None, score_threshold=None):
    """
    Finds the top-k similar values to a query from a given iterable of values.

    Args:
        query: The query value to find similarities for.
        values: An iterable of values to compare against the query.
        key: A function to extract a comparable value from each element in 'values'. Defaults to None.
        top: Number of top similar values to return. Defaults to 1.
        scorer: A function to compute the similarity score between two values.
                If None, defaults to Levenshtein ratio for string comparison. Defaults to None.
        score_threshold: If provided, only values with similarity scores greater than this threshold will be considered. Defaults to None.

    Returns:
        A list of top-k similar values to the query.

    Examples:
        >>> query = 'apple'
        >>> fruits = ['banana', 'pineapple', 'apple pie', 'applesauce', 'grape']
        >>> top_k_similar(query, fruits)
        ['pineapple']
    """
    if scorer is None:
        from Levenshtein import ratio
        scorer = lambda x, y: ratio(str(x), str(y))
    if key is None:
        scored_x = []
        for value in values:
            score = scorer(query, value)
            if score_threshold is None or score > score_threshold:
                scored_x.append((score, value))
    else:
        scored_x = []
        for value in values:
            score = scorer(query, key(value))
            if score_threshold is None or score > score_threshold:
                scored_x.append((score, value))
    return [_x for _, _x in heapq.nlargest(top, scored_x)]


def retrieve(
        key,
        d: Mapping,
        top: int = 1,
        scorer: Callable = None,
        only_run_retriever_if_key_not_exist: bool = True,
        score_threshold=None,
        return_key: bool = False
):
    """
    Retrieves values from a mapping based on a query key, optionally finding similar keys.

    Args:
        key: The query key to retrieve values for.
        d: The mapping to retrieve values from.
        top: Number of top similar keys to consider if the key is not found. Defaults to 1.
        scorer: A function to compute the similarity score between two keys.
            If None, defaults to Levenshtein ratio for string comparison. Defaults to None.
        only_run_retriever_if_key_not_exist: If True and key exists in d and top is 1, the function returns the value directly without running the retriever. Defaults to True.
        score_threshold: If provided, only keys with similarity scores greater than this threshold will be considered. Defaults to None.
        return_key: If True, returns the key along with the value(s). Defaults to False.

    Returns:
        If return_key is False:
            If top is 1 and only_run_retriever_if_key_not_exist is True and key exists in d, returns the value corresponding to the key.
            If top is 1 or greater, returns a list of values corresponding to the top similar keys found.
        If return_key is True:
            If top is 1 and only_run_retriever_if_key_not_exist is True and key exists in d, returns a tuple of (key, value).
            If top is 1 or greater, returns a list of tuples containing (key, value) pairs corresponding to the top similar keys found.

    Examples:
        >>> d = {'apple': 10, 'banana': 20, 'pineapple': 15, 'applesauce': 5}
        >>> retrieve('apple', d)
        10
        >>> retrieve('appl', d, return_key=True)
        ('apple', 10)
        >>> retrieve('appl', d, top=2)
        [10, 15]

    """
    if scorer is None:
        from Levenshtein import ratio
        scorer = ratio

    if only_run_retriever_if_key_not_exist and key in d and top == 1:
        if return_key:
            return key, d[key]
        else:
            return d[key]
    else:
        if top == 1:
            _key = max(d, key=lambda x: scorer(key, x))
            if return_key:
                return _key, d[_key]
            else:
                return d[_key]
        else:
            if return_key:
                return [
                    (_key, d[_key])
                    for _key
                    in top_k_similar(key, d, top=top, scorer=scorer, score_threshold=score_threshold)
                ]
            else:
                return [
                    d[_key]
                    for _key
                    in top_k_similar(key, d, top=top, scorer=scorer, score_threshold=score_threshold)
                ]
