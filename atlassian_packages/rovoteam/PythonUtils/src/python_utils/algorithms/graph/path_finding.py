from collections import deque
from collections.abc import Callable
from typing import List, Dict, Tuple, Sequence, TypeVar, Iterable, Set, Union, Mapping, Any, Hashable

from python_utils.algorithms.tree.trie import build_trie
from python_utils.string_utils import join_

T = TypeVar('T')


def shortest_circular_path(graph: List[List[int]]) -> int:
    """
    Solves the Travelling Salesman Problem (TSP) using dynamic programming with bitmasking,
    utilizing a dictionary to store DP states to optimize space.

    Args:
        graph (List[List[int]]): A 2D list representing the distances between cities.
            - `graph[i][j]` is the cost to travel from city `i` to city `j`.
            - It is assumed that `graph[i][i] = 0` for all `i`.
            - The matrix should be square and of size `n x n`, where `n` is the number of cities.

    Returns:
        int: The minimal total cost to visit all cities exactly once and return to the starting city.

    Examples:
        >>> graph = [
        ...     [0, 10, 15, 20],
        ...     [10, 0, 35, 25],
        ...     [15, 35, 0, 30],
        ...     [20, 25, 30, 0]
        ... ]
        >>> shortest_circular_path(graph)
        80

        Explanation:
            The optimal tour is 0 -> 1 -> 3 -> 2 -> 0 with total cost 10 + 25 + 30 + 15 = 80.

    Notes:
        **Problem Statement**:
            - Given a list of cities and the distances between each pair of cities, find the shortest possible route
              that visits each city exactly once and returns to the origin city.

        **Dynamic Programming Approach with Dictionary**:
            - **State Representation**:
                - We represent the set of visited cities using a bitmask (integer).
                - Each city corresponds to a bit in the mask; if the bit is set, the city has been visited.
            - **DP Dictionary**:
                - We use a dictionary `dp` where each key is a tuple `(mask, u)`, and the value is the minimal cost to reach city `u` with visited cities represented by `mask`.
            - **Recursive Formula**:
                - For each city `u` and for each subset of cities `mask` that includes `u`:
                    ```python
                    dp[(mask, u)] = min(
                        dp[(prev_mask, v)] + graph[v][u]
                        for all v where v != u and (prev_mask, v) in dp
                    )
                    ```
                    - `prev_mask` is `mask` with the bit corresponding to city `u` turned off.
            - **Base Case**:
                - `dp[(1 << start, start)] = 0`, where `start` is the starting city (assumed to be city `0`).
            - **Final Answer**:
                - The minimal cost to complete the tour is:
                    ```python
                    min(dp[(full_mask, u)] + graph[u][start] for u in range(n) if u != start and (full_mask, u) in dp)
                    ```
                    - `full_mask` represents the set where all cities have been visited.

        **Advantages of Using a Dictionary**:
            - **Space Optimization**:
                - We only store the states that are actually computed.
                - This can save memory when many states are not reachable or can be pruned.
            - **Flexibility**:
                - Easier to implement pruning strategies and custom logic.

        **Time Complexity**:
            - **O(n^2 * 2^n)** in the worst case.
                - The number of states remains the same as before.
                - However, practical performance may improve due to reduced memory overhead and possible pruning.

        **Space Complexity**:
            - **O(n * 2^n)** in the worst case.
                - Using a dictionary does not change the theoretical space complexity, but it can reduce actual memory usage.

        **Constraints**:
            - The number of cities `n` should be at least `2`.
            - The graph must be symmetric if the distances are bidirectional.
            - All distances should be non-negative integers.

    """
    n = len(graph)
    if n == 0:
        return 0

    dp: Dict[Tuple[int, int], int] = {}
    start = 0  # starting city
    initial_mask = 1 << start
    # Base case: starting at start vertex `start` with only `start` visited
    # In this case the distance is 0 because `start` is already visited
    dp[(initial_mask, start)] = 0

    # Iterate over all masks from 1 to full_mask
    full_mask = (1 << n) - 1  # All cities have been visited when mask == full_mask

    for mask in range(1, full_mask + 1):  # iterates through all induced subgraphs
        for u in range(n):  # trying out each of the vertex on the subgraph as start vertex
            if not (mask & (1 << u)):
                continue
            prev_mask = mask ^ (1 << u)  # xor operator to remove vertex u from mask to obtain the prev_mask

            for v in range(n):  # try to find the minimal cost to reach vertex u from any vertex other v in the subgraph
                if v == u or not (mask & (1 << v)):
                    continue
                if (prev_mask, v) in dp:
                    # `prev_mask` must be a smaller integer than `mask`,
                    # and therefore `(prev_mask, v)` should have been computed in previous iterations
                    # if there is `v` is connected to prev_mask
                    new_cost = dp[(prev_mask, v)] + graph[v][u]
                    if ((mask, u) not in dp) or (new_cost < dp[(mask, u)]):
                        dp[(mask, u)] = new_cost

    # Find the minimal cost to complete the tour and return to the starting city
    min_cost = float('inf')
    for u in range(n):
        if u == start or (full_mask, u) not in dp:
            continue
        cost = dp[(full_mask, u)] + graph[u][start]  # Add cost to return to start
        if cost < min_cost:
            min_cost = cost

    return int(min_cost)


def grid_search(
        grid: Sequence[Sequence[T]],
        query: Sequence[T],
        visited: List[Tuple[int, int]] = None,
        return_visited: bool = False
) -> Union[
    bool,
    Tuple[bool, List[Tuple[int, int]]]
]:
    """
    Determines if the `query` sequence exists in the `grid` by constructing it from sequentially adjacent cells.
    Adjacent cells are horizontally or vertically neighboring. The same cell may not be used more than once.

    Args:
        grid (Sequence[Sequence[T]]): 2D grid of elements.
        query (Sequence[T]): The sequence to search for in the grid.
        return_visited (bool): True to return visisted indices in the grid.
        visited (List): Pass in existing visited flags to block some cells from the grid.

    Returns:
        bool: True if the query exists in the grid, False otherwise.

    Examples:
        >>> grid1 = [
        ...     ["A","B","C","E"],
        ...     ["S","F","C","S"],
        ...     ["A","D","E","E"]
        ... ]
        >>> grid_search(grid1,"ABCCED")
        True
        >>> grid_search(grid1,"SEE")
        True
        >>> grid_search(grid1,"ABCB")
        False
        >>> grid2 = [
        ...     ["a","a","a","a"],
        ...     ["a","a","a","a"],
        ...     ["a","a","a","a"]
        ... ]
        >>> grid_search(grid2,"aaaaa")
        True
        >>> grid_search([],"A")
        False
        >>> grid_search([[]],"")
        True
    """
    if not query:
        if return_visited:
            return True, []
        else:
            return True

    grid_height = len(grid)
    if not grid_height:
        if return_visited:
            return False, []
        else:
            return False
    grid_width = len(grid[0])
    query_length = len(query)

    def dfs(i, j, k, _visited):
        if grid[i][j] == query[k]:
            _visited.append((i, j))
            k += 1
            if k == query_length:
                return True
            else:
                result = (
                        (
                                i > 0
                                and (i - 1, j) not in _visited
                                and dfs(i - 1, j, k, _visited)
                        ) or
                        (
                                i < grid_height - 1
                                and (i + 1, j) not in _visited
                                and dfs(i + 1, j, k, _visited)
                        ) or
                        (
                                j > 0
                                and (i, j - 1) not in _visited
                                and dfs(i, j - 1, k, _visited)
                        ) or
                        (
                                j < grid_width - 1
                                and (i, j + 1) not in _visited
                                and dfs(i, j + 1, k, _visited)
                        )
                )
                if not result:
                    # in depth-first search, visited flag set needs to roll back when the branch fails
                    _visited.pop()
                    return False
                else:
                    return True
        else:
            return False

    if not visited:
        visited = []
    for i in range(grid_height):
        for j in range(grid_width):
            if dfs(i, j, 0, visited):
                if return_visited:
                    return True, visited
                else:
                    return True
    if return_visited:
        return False, visited
    else:
        return False


def grid_search_trie(
        grid: Sequence[Sequence[T]],
        trie: Mapping,
        visited: List[Tuple[int, int]] = None,
        concat: Callable[[Sequence[T]], Any] = None,
        eos_label: Hashable = chr(31)
) -> Sequence[Sequence[T]]:
    """
    Searches for all sequences from a Trie (prefix tree) within a 2D grid. The function
    traverses the grid in a depth-first search (DFS) manner to match sequences stored
    in the Trie.

    Args:
        grid (Sequence[Sequence[T]]): A 2D grid where each cell contains a hashable element.
        trie (Mapping): A nested dictionary (Trie) representing sequences to search for.
        visited (List[Tuple[int, int]], optional): A list of coordinates to track visited cells
            during traversal. Defaults to an empty list if not provided.
        concat (Callable[[Sequence[T]], Any], optional): A function to combine matched sequences
            into a desired format. If None, the default behavior joins elements as a string.
        eos_label (Hashable, optional): A special symbol used in the Trie to mark the end of a
            valid sequence. Defaults to the ASCII Unit Separator (`chr(31)`).

    Returns:
        Sequence[Sequence[T]]: A list of matched sequences found in the grid.

    Examples:
        >>> board = [["o", "a", "a", "n"],
        ...          ["e", "t", "a", "e"],
        ...          ["i", "h", "k", "r"],
        ...          ["i", "f", "l", "v"]]
        >>> trie = build_trie([["o", "a", "t", "h"], ["e", "a", "t"], ["r", "a", "i", "n"]])
        >>> sorted(grid_search_trie(board, trie))
        ['eat', 'oath']

        >>> board = [["a", "b", "c"],
        ...          ["d", "e", "f"],
        ...          ["g", "h", "i"]]
        >>> trie = build_trie([["a", "b", "e", "i"], ["h", "g"]])
        >>> sorted(grid_search_trie(board, trie))
        ['hg']

        >>> board = [["a", "b"],
        ...          ["c", "d"]]
        >>> trie = build_trie([["a", "d"], ["b", "c"]])
        >>> grid_search_trie(board, trie)
        []
    """
    if not trie:
        return []
    grid_height = len(grid)
    if not grid_height:
        return []
    grid_width = len(grid[0])

    results = []

    def _add_result(result):
        if concat is None:
            this_result = join_(*result, sep='')
        else:
            this_result = concat(tuple(result))
        if this_result not in results:
            results.append(this_result)

    def dfs(i, j, _trie, _visited):
        for k, _child_trie in _trie.items():
            if k == eos_label:
                _add_result((grid[i][j] for i, j in _visited))
            elif grid[i][j] == k:
                _visited.append((i, j))
                if not _child_trie:
                    _add_result((grid[i][j] for i, j in _visited))
                else:
                    if (
                            i > 0
                            and (i - 1, j) not in _visited
                    ):
                        dfs(i - 1, j, _child_trie, _visited)

                    if (
                            i < grid_height - 1
                            and (i + 1, j) not in _visited
                    ):
                        dfs(i + 1, j, _child_trie, _visited)

                    if (
                            j > 0
                            and (i, j - 1) not in _visited
                    ):
                        dfs(i, j - 1, _child_trie, _visited)

                    if (
                            j < grid_width - 1
                            and (i, j + 1) not in _visited
                    ):
                        dfs(i, j + 1, _child_trie, _visited)
                _visited.pop()

    if visited is None:
        visited = []
    for i in range(grid_height):
        for j in range(grid_width):
            dfs(i, j, trie, visited)

    return results


def grid_search_multiple(
        grid: Sequence[Sequence[T]],
        queries: Sequence[Sequence[T]],
        visited: List[Tuple[int, int]] = None,
        eos_label: Hashable = chr(31)
) -> Sequence[Sequence[T]]:
    """
    Searches for multiple sequences in a 2D grid by building a Trie from the given queries
    and using it to perform the search. Combines `build_trie` and `grid_search_trie` for convenience.

    Args:
        grid (Sequence[Sequence[T]]): A 2D grid where each cell contains a hashable element.
        queries (Sequence[Sequence[T]]): A list of sequences to search for in the grid.
        visited (List[Tuple[int, int]], optional): A list of coordinates to track visited cells
            during traversal. Defaults to an empty list if not provided.
        eos_label (Hashable, optional): A special symbol used in the Trie to mark the end of a
            valid sequence. Defaults to the ASCII Unit Separator (`chr(31)`).

    Returns:
        Sequence[Sequence[T]]: A list of matched sequences found in the grid.

    Examples:
        >>> board1 = [["o", "a", "a", "n"],
        ...           ["e", "t", "a", "e"],
        ...           ["i", "h", "k", "r"],
        ...           ["i", "f", "l", "v"]]
        >>> words1 = ["oath", "pea", "eat", "rain"]
        >>> sorted(grid_search_multiple(board1, words1))
        ['eat', 'oath']

        >>> board2 = [["a", "b"],
        ...           ["c", "d"]]
        >>> words2 = ["abcb"]
        >>> grid_search_multiple(board2, words2)
        []

        >>> board3 = [["a", "a", "a"],
        ...           ["a", "b", "a"],
        ...           ["a", "a", "a"]]
        >>> words3 = ["baa", "baaa"]
        >>> sorted(grid_search_multiple(board3, words3))
        ['baa', 'baaa']

        >>> board4 = [["h", "e", "l", "l", "o"],
        ...           ["w", "o", "r", "l", "d"]]
        >>> words4 = ["hello", "world", "hell"]
        >>> sorted(grid_search_multiple(board4, words4))
        ['hell', 'hello', 'world']
    """
    trie = build_trie(queries, null_leaf=True, eos_label=eos_label)
    return grid_search_trie(grid, trie, visited)
