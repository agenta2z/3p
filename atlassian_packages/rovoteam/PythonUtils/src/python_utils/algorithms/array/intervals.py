from typing import Sequence, Tuple, TypeVar, List
import heapq

T = TypeVar('T')


def has_overlap(intervals: Sequence[Tuple[T, T]]):
    """
    Checks if any intervals in a given sequence overlap.

    This function determines if there is any overlap among the intervals in the input
    sequence. An interval is represented as a tuple `(start, end)` where `start < end`.
    The intervals are sorted by their start time before checking for overlaps.

    Args:
        intervals (Sequence[Tuple[T, T]]): A sequence of intervals, where each interval
            is represented as a tuple `(start, end)`.

    Returns:
        bool: True if any intervals overlap, False otherwise.

    Notes:
        - The input intervals must satisfy the condition `start < end` for all intervals.
        - The function does not modify the original list; it works on a sorted copy.
        - Time Complexity: Sorting the intervals takes O(n log n), and checking for overlaps takes O(n).
          Overall time complexity is O(n log n).
        - Space Complexity: Sorting creates a new list, so the space complexity is O(n).

    Examples:
        >>> has_overlap([(1, 3), (2, 4), (5, 6)])
        True
        >>> has_overlap([(1, 2), (3, 4), (5, 6)])
        False
        >>> has_overlap([(1, 5), (2, 3), (6, 8)])
        True
        >>> has_overlap([])
        False
        >>> has_overlap([(1, 2)])
        False
    """
    intervals = sorted(intervals)
    for i in range(1, len(intervals)):
        interval = intervals[i]
        prev_interval = intervals[i - 1]
        if interval[0] < prev_interval[1]:
            return True
    return False


def merge_intervals(intervals: List[List[int]]) -> List[List[int]]:
    """
    Merges overlapping intervals.

    Args:
        intervals (List[List[int]]): A list of intervals, where each interval
            is represented as [start, end].

    Returns:
        List[List[int]]: A list of merged non-overlapping intervals.

    Examples:
        >>> merge_intervals([[1,3],[2,6],[8,10],[15,18]])
        [[1, 6], [8, 10], [15, 18]]
        >>> merge_intervals([[1,4],[4,5]])
        [[1, 5]]
        >>> merge_intervals([[1,4],[5,6]])
        [[1, 4], [5, 6]]

    Notes:
        - The input intervals must satisfy the condition `start <= end` for all intervals.
        - The function modifies the original list, sorting it by start times.
        - Time Complexity: O(n log n), due to sorting.
        - Space Complexity: O(n), for the output list.
    """
    if not intervals:
        return []

    # Sort intervals based on the start time
    intervals = sorted(intervals)

    merged = [intervals[0]]  # Initialize with the first interval

    for current in intervals[1:]:
        prev = merged[-1]
        if current[0] <= prev[1]:  # Overlapping intervals
            prev[1] = max(prev[1], current[1])  # Merge intervals
        else:
            merged.append(current)  # No overlap, add the interval

    return merged


def count_max_overlap(intervals: Sequence[Tuple[T, T]]) -> int:
    """
    Counts the maximum number of overlapping intervals.

    This function determines the maximum number of overlapping intervals
    (e.g., the number of conference rooms required for the given intervals).
    It uses a min-heap to track the earliest ending intervals and updates
    the heap as new intervals start.

    Args:
        intervals (Sequence[Tuple[T, T]]): A sequence of intervals, where each interval
            is represented as a tuple `(start, end)`.

    Returns:
        int: The maximum number of overlapping intervals.

    Examples:
        >>> count_max_overlap([(0, 30), (5, 10), (15, 20)])
        2
        >>> count_max_overlap([(7, 10), (2, 4)])
        1
        >>> count_max_overlap([(1, 5), (2, 6), (3, 7)])
        3
        >>> count_max_overlap([(1, 2)])
        1
        >>> count_max_overlap([])
        0

    Notes:
        - The input intervals must satisfy the condition `start < end` for all intervals.
        - The function does not modify the original list; it works on a sorted copy.
        - Time Complexity: O(n log n), where n is the number of intervals (due to sorting
          and heap operations).
        - Space Complexity: O(n), due to the heap storing end times of intervals.
    """
    if not intervals:
        return 0

    # Sort by start time
    intervals = sorted(intervals)

    # Min-heap to track end times of overlapping intervals
    active_meetings = []
    max_overlap = 0

    for start, end in intervals:
        # Remove intervals that have ended
        while active_meetings and active_meetings[0] <= start:
            heapq.heappop(active_meetings)

        # Add the new meeting's end time
        heapq.heappush(active_meetings, end)

        # Update max overlap
        max_overlap = max(max_overlap, len(active_meetings))

    return max_overlap