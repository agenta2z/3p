from typing import Sequence, TypeVar
from python_utils.common_utils.array_helper import reverse_in_place

"""
The most efficient algorithm for permutation generation without considering lexicographical order is Heap's algorithm https://en.wikipedia.org/wiki/Heap%27s_algorithm,
We do not include it here as it is a very specialized algorithm.

Python has a build-in function `itertools.permutations` for permutation, and it is based on the same logic as `next_lexicographic_permutation` below.
"""

T = TypeVar('T')

def iter_permutation_recursive(seq: Sequence[T]):
    """
    Generate all permutations of a sequence using recursion.

    Args:
        seq (Sequence[T]): The sequence to generate permutations for.

    Yields:
        Generator[Sequence[T], None, None]: Each permutation as a sequence.

    Examples:
        >>> list(iter_permutation_recursive([1, 2, 3]))
        [[1, 2, 3], [1, 3, 2], [2, 1, 3], [2, 3, 1], [3, 1, 2], [3, 2, 1]]

        >>> list(iter_permutation_recursive(['a', 'b']))
        [['a', 'b'], ['b', 'a']]

        >>> list(iter_permutation_recursive([]))
        [[]]

        >>> list(iter_permutation_recursive([42]))
        [[42]]


    Notes:
        - **Recursion**: all permutations can be grouped by its first element (to be exact the first element's index in the original input sequence).
          Once we fix the first element, tha group's permutations are permutations of remaining elements.

        - **Time Complexity**: O(n^2) for one permutation.
          There would be n recursive calls for one permutation, and at each call `seq[:i] + seq[i+1:]` takes O(n) time to create the sequence.

        - **Space Complexity**: O(n^2)
          The recursive call stack requires O(n) space, and concatenating slices of the sequence (e.g., `seq[:i] + seq[i+1:]`) at each level also requires O(n) space. Combined, this results in a total space complexity of O(n^2).

          Additionally, the generator itself does not hold all permutations in memory, making it more memory-efficient than returning a complete list of permutations.
    """
    # Base case: if the list has only one element or is empty, yield it as the only permutation
    if len(seq) <= 1:
        yield seq
    else:
        # Recursive case: find permutations for the rest of the list
        for i in range(len(seq)):
            # Remove the current element from the list
            current = seq[i]
            remaining = seq[:i] + seq[i + 1:]

            # Generate all permutations of the remaining elements
            for perm in iter_permutation_recursive(remaining):
                yield [current] + perm

def next_lexicographic_permutation(seq: Sequence[T], in_place: bool = False) -> Sequence[T]:
    """
    Generates the next lexicographic permutation of a given sequence.

    The algorithm modifies the sequence to the next permutation in lexicographic order.
    If the sequence is the last permutation (sorted in descending order), the function returns the first permutation
    (sorted in ascending order). This algorithm uses an efficient in-place approach.

    Args:
        seq (Sequence[T]): The input sequence to find the next permutation.
        in_place (bool): If True, modifies the sequence in place. Defaults to False.

    Returns:
        Sequence[T]: The next permutation in lexicographic order. If no further permutations exist,
        returns the first permutation in lexicographic order.

    Examples:
        Example 1: Sequence is in descending order
        >>> seq = [3, 2, 1]
        >>> next_lexicographic_permutation(seq)
        [1, 2, 3]

        Example 2: Regular case
        >>> seq = [1, 2, 3]
        >>> next_lexicographic_permutation(seq)
        [1, 3, 2]

        Example 3: Single element
        >>> seq = [1]
        >>> next_lexicographic_permutation(seq)
        [1]

        Example 4: Sequence with repeated elements
        >>> seq = [1, 2, 2]
        >>> next_lexicographic_permutation(seq)
        [2, 1, 2]

        Example 5: In-place modification
        >>> seq = [1, 2, 3]
        >>> next_lexicographic_permutation(seq, in_place=True)
        [1, 3, 2]
        >>> seq  # The original sequence is modified
        [1, 3, 2]

    Notes:
        - The time complexity of this algorithm is O(n), where n is the length of the sequence.
        - The space complexity is O(1) when `in_place=True`, as no additional data structures are used.
    """
    if not seq:
        return []

    # NOTE: the descending order is the highest lexicographic order.

    # region STEP1: finds the first decreasing element from the right side view;
    # for example, given sequence [2, 4, 3, 5, 1, 0], then '3' is the first decreasing element from the right side view.

    # Intuition: the descending order is the highest lexicographic order,
    # and whatever operation done within the descending tail of the sequence will decrease its lexicographic order ([5, 1, 0] in the above example).
    # Therefore, a greedy approach would be looking at the first element before the descending tail.
    i = len(seq) - 2
    while i >= 0 and seq[i] >= seq[i + 1]:
        i -= 1

    if i == -1:  # the full sequence is in sorted (descending), the just reverse the whole sequence
        return seq[::-1]

    pivot = seq[i]  # we call this "first decreasing element from the right side view" as the pivot element

    # Proof that the best option we have is to increase seq[i].
    # - A swap must happen to increase the sequence order.
    # - The swap cannot happen only within the descending tail, as discussed above.
    # - The swap cannot affect any element on the left side of seq[i], which would lead to either higher or lower order than swapping seq[i] and seq[j].

    # endregion

    # region STEP2: find the minimum element larger than "pivot" from the right side of the "pivot"
    j = len(seq) - 1
    while seq[j] <= pivot:
        j -= 1
    # endregion

    # region STEP3: swapping the "pivot" seq[i] with seq[j], which is the minimum element larger than "pivot" from the right side of "pivot"
    if not in_place:
        seq = seq[:]
    seq[i], seq[j] = seq[j], seq[i]

    # Proof: if we are to swap seq[i] with another element to derive a new permutation, then there is no better strategy than swapping "... seq[i] ... seq[j] ..." as "... seq[j] ... seq[i] ...".
    # - First, seq[i] cannot swap with another element with the same value, otherwise the resulting sequence is the same, and hence no lexicographic order increase.
    # - Second, seq[i] cannot swap with any elements from the right side of it other than seq[j].
    #   We can prove by contradiction and say seq[j0] is such an element where j0 > i.
    #   - If seq[j0] < seq[j], then we must have seq[j0] < seq[i] < seq[j],
    #     (it cannot be seq[i] < seq[j0] < seq[j] because seq[j] is the minimum element larger than seq[i] from the right side of seq[i]),
    #     then the swap would lead to an even smaller lexicographic order.
    #   - Otherwise, if seq[j0] > seq[j], then obviously swapping seq[i] and seq[j0] leads to a permutation with even higher lexicographic order.
    # - Third, seq[i] cannot swap with any elements from the left side of seq[i].
    #   We can similarly prove by contradiction and say seq[i0] is such an element where i0 < i,
    #   The swap would result in
    #   - We cannot have seq[i0] > seq[i], because the swap would even lead to a smaller lexicographic order by promoting seq[i] to an even smaller index.
    #   - We cannot have seq[i0] < seq[i], because the resulting sequence "... seq[i] ... seq[i0] ... seq[j] ..." obviously has higher lexicographic order than "... seq[i0] ... seq[j] ... seq[i] ...".
    # Therefore swapping seq[i] and seq[j] is the best operation if we want to swap[i] to achieve higher lexicographic order.
    # endregion

    # region STEP4: reverse the post-swap subsequence starting at i+1
    # After swap, the sequence seq[i+1:] is still in descending order (easy proof by contradiction; suppose not, then seq[j] is not the min element larger than seq[i]).
    # seq[i] has just been elevated to a higher order, than reversing seq[i + 1:] resets it to the lowest lexicographic order for that tail.
    reverse_in_place(seq, start=i + 1)
    # endregion

    return seq


