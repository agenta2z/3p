from collections import deque
from typing import Sequence, List, Callable, Iterator, Iterable


def next_larger_in_time_series(time_series: Sequence, return_num_steps_forward: bool = False) -> List[int]:
    """
    Finds the next larger value in a time series and optionally calculates the steps to it.

    This function takes a sequence of numerical values (`time_series`) and returns a list
    where each element at index `i` indicates either:
      - The number of steps required to find a larger value after `i` (if `return_num_steps_forward` is True), or
      - The index of the next larger value after `i` (if `return_num_steps_forward` is False).

    If no larger value exists for a given index, the corresponding output is `0` (or `-1` if `return_num_steps_forward` is False).

    Args:
        time_series (Sequence): A sequence of values representing the time series.
        return_num_steps_forward (bool, optional):
            If True, the output indicates the number of steps forward to the next larger value.
            If False, the output indicates the index of the next larger value.
            Default is False.

    Returns:
        List[int]: A list where each element represents either the number of steps to a larger value
                   or the index of the next larger value, depending on the value of `return_num_steps_forward`.
                   If no such value exists, the corresponding element is `0` or `-1` (based on the mode).

    Examples:
        Example 1 (default mode: return index of the next larger value):
        >>> next_larger_in_time_series([73, 74, 75, 71, 69, 72, 76, 73])
        [1, 2, 6, 5, 5, 6, -1, -1]

        Example 2 (return number of steps forward):
        >>> next_larger_in_time_series([73, 74, 75, 71, 69, 72, 76, 73], return_num_steps_forward=True)
        [1, 1, 4, 2, 1, 1, -1, -1]

        Example 3 (default mode):
        >>> next_larger_in_time_series([30, 40, 50, 60])
        [1, 2, 3, -1]

        Example 4 (return number of steps forward):
        >>> next_larger_in_time_series([30, 40, 50, 60], return_num_steps_forward=True)
        [1, 1, 1, -1]

        Example 5 (all decreasing values):
        >>> next_larger_in_time_series([100, 90, 80, 70])
        [-1, -1, -1, -1]

        Example 6 (return number of steps forward for all decreasing values):
        >>> next_larger_in_time_series([100, 90, 80, 70], return_num_steps_forward=True)
        [-1, -1, -1, -1]

    Notes:
        - If the time series is empty, the function returns an empty list.
        - The algorithm uses a monotonic stack to maintain indices of elements
          in decreasing order, ensuring efficient processing.
        - The `return_num_steps_forward` parameter controls the type of result provided.

    Complexity:
        - Time Complexity: O(n), where `n` is the length of the input time series.
          Each index is pushed and popped from the stack at most once.
        - Space Complexity: O(n), for the stack used to store indices.
    """
    n = len(time_series)
    result = [-1] * n  # Initialize result array with -1 for indices or 0 for step counts
    stack = []  # Monotonic stack to store indices

    for i, value in enumerate(time_series):
        # Process elements in the stack if the current value is greater
        while stack and time_series[stack[-1]] < value:
            prev_index = stack.pop()
            if return_num_steps_forward:
                result[prev_index] = i - prev_index  # Calculate steps
            else:
                result[prev_index] = i  # Record index of the next larger value
        stack.append(i)  # Push the current index to the stack

    return result


def find_all_historical_larger(arr: List[int], compare: Callable[[int, int], bool], reverse: bool = True) -> List[int]:
    """
    Finds indices of elements in `arr` that are 'historically larger' based on a comparison function.

    Args:
        arr (List[int]): List of integers to process.
        compare (Callable[[int, int], bool]): Comparison function (e.g., lambda a, b: a > b).
        reverse (bool, optional): If True, traverses from right to left (e.g., ocean view).
                                  If False, traverses from left to right. Defaults to True.

    Returns:
        List[int]: List of indices where the condition holds, sorted in increasing order.

    Examples:
        >>> find_all_historical_larger([4, 2, 3, 1], lambda x, y: x > y, True)
        [0, 2, 3]

        >>> find_all_historical_larger([4, 3, 2, 1], lambda x, y: x > y, True)
        [0, 1, 2, 3]

        >>> find_all_historical_larger([1, 3, 2, 4], lambda x, y: x > y, False)
        [0, 1, 3]

        >>> find_all_historical_larger([5, 1, 2, 3, 4], lambda x, y: x > y, True)
        [0, 4]

        >>> find_all_historical_larger([5, 1, 2, 3, 4], lambda x, y: x > y, False)
        [0]
    """
    n = len(arr)
    result = []
    max_seen = float('-inf')  # Track max value seen so far

    # Determine iteration order
    indices = range(n - 1, -1, -1) if reverse else range(n)

    for i in indices:
        if compare(arr[i], max_seen):
            result.append(i)
            max_seen = arr[i]

    return result[::-1] if reverse else result  # Maintain increasing index order


def find_right_side_max(arr: List[int]) -> List[int]:
    """
    Finds the index of the rightmost maximum value for each element in the list.

    Args:
        arr (List[int]): The input list of numbers.

    Returns:
        List[int]: A list where each index `i` contains the index of the maximum value
                   from `arr[i:]` (including `i`).

    Notes:
        - **Time Complexity**: O(n) (Single pass from right to left).
        - **Space Complexity**: O(n) (Stores indices).

    Example:
        >>> find_right_side_max([2, 7, 3, 6])
        [1, 1, 3, 3]

        >>> find_right_side_max([9, 1, 4, 2, 5])
        [0, 4, 4, 4, 4]

        # Since 4 is the max at every position rightward
        >>> find_right_side_max([1, 2, 3, 4])
        [3, 3, 3, 3]

        # Each element is its own max to the right
        >>> find_right_side_max([5, 4, 3, 2, 1])
        [0, 1, 2, 3, 4]
    """
    n = len(arr)
    if n == 0:
        return []

    max_index = [0] * n
    max_index[-1] = n - 1  # Last element is its own max

    for i in range(n - 2, -1, -1):
        if arr[i] > arr[max_index[i + 1]]:
            max_index[i] = i  # Current element is the new max
        else:
            max_index[i] = max_index[i + 1]  # Keep the rightmost max index

    return max_index


def find_left_side_max(arr: List[int]) -> List[int]:
    """
    Finds the index of the leftmost maximum value for each element in the list.

    Args:
        arr (List[int]): The input list of numbers.

    Returns:
        List[int]: A list where each index `i` contains the index of the maximum value
                   from `arr[:i+1]` (including `i`).

    Notes:
        - **Time Complexity**: O(n) (Single pass from left to right).
        - **Space Complexity**: O(n) (Stores indices).

    Example:
        >>> find_left_side_max([2, 7, 3, 6])
        [0, 1, 1, 1]

        >>> find_left_side_max([9, 1, 4, 2, 5])
        [0, 0, 0, 0, 0]

        # Since each number is increasing, the max is always itself
        >>> find_left_side_max([1, 2, 3, 4])
        [0, 1, 2, 3]

        # Since each number is decreasing, the leftmost max is always the first element
        >>> find_left_side_max([5, 4, 3, 2, 1])
        [0, 0, 0, 0, 0]
    """
    n = len(arr)
    if n == 0:
        return []

    max_index = [0] * n
    max_index[0] = 0  # The first element is its own max

    for i in range(1, n):
        if arr[i] > arr[max_index[i - 1]]:
            max_index[i] = i  # Update max index if current element is greater
        else:
            max_index[i] = max_index[i - 1]  # Keep the leftmost max index

    return max_index


class MovingAverage:
    """
    A class that computes the moving average from an iterable with a fixed window size.
    Implements an iterator that yields the moving average at each step.

    Args:
        size (int): The size of the moving window.
        iterable (Iterable[int]): The data stream or list to process.

    Attributes:
        window_size (int): The maximum size of the moving window.
        queue (deque): A queue to store the last `size` elements.
        _window_sum (float): The sum of the elements in the current window.

    Example:
        >>> list(MovingAverage(3, [1, 10, 3, 5]))
        [1.0, 5.5, 4.666666666666667, 6.0]

        >>> list(MovingAverage(2, [1, 10, 3, 5]))
        [1.0, 5.5, 6.5, 4.0]
    """

    def __init__(self, size: int, iterable: Iterable[int]):
        """
        Initializes the MovingAverage iterator with the given window size and iterable.

        Args:
            size (int): The number of elements in the sliding window.
            iterable (Iterable[int]): The input data stream.
        """
        self.window_size = size
        self.queue = deque()
        self._window_sum = 0
        self.iterable = iter(iterable)  # Convert iterable to iterator

    def __iter__(self) -> Iterator[float]:
        """
        Makes the class an iterator.

        Returns:
            Iterator[float]: Yields the moving average at each step.
        """
        return self

    def __next__(self) -> float:
        """
        Processes the next value from the iterable and returns the moving average.

        Returns:
            float: The current moving average.

        Raises:
            StopIteration: If the iterable is exhausted.
        """
        val = next(self.iterable)  # Get the next value from the iterable

        self.queue.append(val)
        self._window_sum += val

        # Remove the oldest value if we exceed window size
        if len(self.queue) > self.window_size:
            self._window_sum -= self.queue.popleft()

        # Compute the moving average
        return self._window_sum / len(self.queue)
