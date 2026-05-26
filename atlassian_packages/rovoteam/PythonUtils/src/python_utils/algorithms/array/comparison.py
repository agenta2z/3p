from typing import Sequence, List

def longest_common_subsequence(seq1: Sequence, seq2: Sequence) -> List:
    """
    Find the longest common subsequence (LCS) between two sequences.

    Args:
        seq1 (Sequence): The first sequence.
        seq2 (Sequence): The second sequence.

    Returns:
        List: The longest common subsequence as a list of elements.

    Examples:
        >>> longest_common_subsequence("", "ABC")
        []
        >>> longest_common_subsequence("AGGTAB", "GXTXAYB")
        ['G', 'T', 'A', 'B']
        >>> longest_common_subsequence([1, 2, 3, 4, 1], [3, 4, 1, 2, 1, 3])
        [3, 4, 1]
        >>> longest_common_subsequence(["apple", "orange", "banana"], ["orange", "apple", "banana"])
        ['orange', 'banana']

    Notes:
        Dynamic Programming Matrix Explanation:
        - Let `dp[i][j]` represent the length of the LCS of the prefixes `seq1[:i]` and `seq2[:j]`.
        - Recursive Formula:
            1. If `seq1[i-1] == seq2[j-1]`:
                dp[i][j] = dp[i-1][j-1] + 1
            2. Otherwise:
                dp[i][j] = max(dp[i-1][j], dp[i][j-1])
        - Base Cases:
            dp[i][0] = 0 for all `i` (empty prefix of `seq2`).
            dp[0][j] = 0 for all `j` (empty prefix of `seq1`).
    """
    m, n = len(seq1), len(seq2)

    # Create a 2D table to store lengths of LCS
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    # Fill the dp table
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if seq1[i - 1] == seq2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

    # Reconstruct the LCS from the dp table
    lcs = []
    i, j = m, n
    while i > 0 and j > 0:
        if seq1[i - 1] == seq2[j - 1]:
            lcs.append(seq1[i - 1])
            i -= 1
            j -= 1
        elif dp[i - 1][j] > dp[i][j - 1]:
            # `dp[i - 1][j] > dp[i][j - 1]`
            # means LCS of `seq1` at `i - 2` and LCS of `seq2` at `j - 1`
            # has longer LCS than the LCS of `seq1` at `i - 1` and LCS of `seq2` at `j - 2`.
            # This indicates dropping `seq1[i - 1]` (i.e. `i -= 1`) does not matter to the LCS,
            # or in other words `seq1[i - 1]` would not have a sequential match of seq2,
            # and hence we can drop it.
            i -= 1
        else:
            j -= 1

    # The lcs list contains the LCS in reverse order
    lcs.reverse()
    return lcs

def longest_common_consecutive_subsequence(seq1: Sequence, seq2: Sequence) -> List:
    """
    Find the longest common consecutive subsequence (LCCS) between two sequences.

    Args:
        seq1 (Sequence): The first sequence.
        seq2 (Sequence): The second sequence.

    Returns:
        List: The longest common consecutive subsequence as a list of elements.

    Examples:
        >>> longest_common_consecutive_subsequence("ABABC", "BABC")
        'BABC'
        >>> longest_common_consecutive_subsequence([1, 2, 3, 2, 1], [3, 2, 1, 2, 3])
        [1, 2, 3]
        >>> longest_common_consecutive_subsequence(["apple", "orange", "banana"], ["banana", "orange", "apple"])
        ['apple']

    Notes:
        Dynamic Programming Matrix Explanation:
            - Let `dp[i][j]` represent the length of the LCCS that ends at indices `i-1` in `seq1`
                and `j-1` in `seq2`.
            - Recursive Formula:
                1. If `seq1[i-1] == seq2[j-1]`:
                    dp[i][j] = dp[i-1][j-1] + 1
                2. Otherwise:
                    dp[i][j] = 0 (reset the chain on mismatch).
            - Base Cases:
                dp[i][0] = 0 for all `i` (empty prefix of `seq2`).
                dp[0][j] = 0 for all `j` (empty prefix of `seq1`).
        Dynamic Programming Pattern:
            To find "consecutive ..." using dynamic programming, the `dp` array usually represents "... ending at ...",
            other examples include the max-sub-array-sum problem.
    """
    m, n = len(seq1), len(seq2)
    max_len = 0  # Length of the longest common consecutive subsequence
    end_index = 0  # Ending index of the subsequence in seq1

    # Create a 2D table to store lengths of common suffixes
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    # Fill the dp table
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if seq1[i - 1] == seq2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
                if dp[i][j] > max_len:
                    max_len = dp[i][j]
                    end_index = i
            else:
                dp[i][j] = 0

    # Extract the longest common consecutive subsequence
    lccs = seq1[end_index - max_len:end_index]
    return lccs