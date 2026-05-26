from collections.abc import Mapping
from typing import Hashable, Sequence

def build_trie(
        sequences: Sequence[Sequence[Hashable]],
        null_leaf: bool = True,
        eos_label: Hashable = chr(31)
) -> Mapping:
    """
    Builds a Trie (prefix tree) from a sequence of sequences, where each sequence
    represents a path in the Trie. The Trie is represented as a nested dictionary.
    Optionally, the leaves of the Trie can be set to `None` or represented as
    empty dictionaries.

    Args:
        sequences (Sequence[Sequence[Hashable]]): A collection of sequences, where
            each sequence is a list (or iterable) of hashable elements. Each sequence
            defines a path in the Trie.
        null_leaf (bool, optional): If True, leaves of the Trie are set to `None`,
            reducing unnecessary empty nodes. If False, leaves are represented as
            dictionaries with the `eos_label` indicating the end of a sequence.
            Defaults to True.
        eos_label (Hashable, optional): A special symbol used to indicate the end of
            a sequence in the Trie. Defaults to the ASCII Unit Separator (`chr(31)`).

    Returns:
        Mapping: A nested dictionary representing the Trie structure. Each key
        corresponds to a node, and its value is either `None` (if it's a leaf
        and `null_leaf` is True) or a dictionary representing the children nodes.

    Examples:
        >>> build_trie([], null_leaf=True) == {}
        True

        >>> sequences = [["a", "b", "c"], ["a", "d"], ["x", "y"]]
        >>> trie = build_trie(sequences)
        >>> trie == {
        ...     "a": {
        ...         "b": {"c": None},
        ...         "d": None
        ...     },
        ...     "x": {
        ...         "y": None
        ...     }
        ... }
        True

        >>> sequences = [["cat"], ["car"], ["dog", "bark"], ["cat", "meow"]]
        >>> trie = build_trie(sequences)
        >>> trie == {
        ...     "cat": {
        ...         "\x1f": None,
        ...         "meow": None
        ...     },
        ...     "car": None,
        ...     "dog": {
        ...         "bark": None
        ...     }
        ... }
        True

        >>> sequences = ["oath", "pea", "eat", "rain"]
        >>> trie = build_trie(sequences)
        >>> trie == {
        ...     'o': {'a': {'t': {'h': None}}},
        ...     'p': {'e': {'a': None}},
        ...     'e': {'a': {'t': None}},
        ...     'r': {'a': {'i': {'n': None}}}
        ... }
        True

        >>> sequences = [["a", "b"], ["a", "c"]]
        >>> build_trie(sequences, null_leaf=False) == {
        ...     "a": {
        ...         "b": {'\x1f': None},
        ...         "c": {'\x1f': None}
        ...     }
        ... }
        True

        >>> sequences = [["cat"], ["car"], ["dog", "bark"], ["cat", "meow"]]
        >>> trie = build_trie(sequences, null_leaf=False)
        >>> trie == {
        ...     "cat": {
        ...         "\x1f": None,
        ...         "meow": {"\x1f": None}
        ...     },
        ...     "car": {"\x1f": None},
        ...     "dog": {
        ...         "bark": {"\x1f": None}
        ...     }
        ... }
        True
    """
    root = {}
    if null_leaf:
        # Build the Trie with `None` as the leaf value
        for seq in sequences:
            curr = root
            _x = None  # tracking the previous element in `seq` in order to reduce unnecessary empty leaf mappings
            _met_pre_existing_none = False
            for x in seq:
                if _x is not None:
                    if curr[_x] is None:
                        # extending the trie and assigning a new mapping as a new layer in the trie
                        if _met_pre_existing_none:
                            # the branch to extend pre-exists before the current `seq`
                            curr[_x] = {eos_label: None}
                            _met_pre_existing_none = False
                        else:
                            # the branch to extend was just created when iterating the last element of `seq`
                            curr[_x] = {}
                    curr = curr[_x]

                if x in curr:
                    if curr[x] is None:
                        # matches a pre-existing None value, meaning we could be extending an existing branch
                        _met_pre_existing_none = True
                else:
                    # extending the trie, but mark it as None for now to reduce empty leaf nodes;
                    # we will create a new layer if `seq` still has more to process
                    curr[x] = None

                _x = x

            if _x is not None and curr[_x] is not None and eos_label not in curr[_x]:
                # the current `seq` partial overlaps with a pre-existing branch in trie, adds `seq` to trie
                curr[_x][eos_label] = None
    else:
        # Build the Trie with empty dictionaries as leaf values
        for seq in sequences:
            curr = root
            for x in seq:
                # Add a new dictionary for the current element if not present
                if x not in curr:
                    curr[x] = {}
                curr = curr[x]
            curr[eos_label] = None
    return root
