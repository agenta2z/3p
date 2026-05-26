from python_utils.algorithms.array.bidirectional_two_pass import product_except_self, find_equilibrium_indexes
from python_utils.algorithms.array.binary_search import (
    binary_search,
    binary_search_sorted_array_greater_than_or_equal_to_target,
    binary_search_sorted_array_less_than_or_equal_to_target,
    binary_post_order_result_compute, find_a_local_maximum,
    find_a_local_minimum
)
from python_utils.algorithms.array.intervals import has_overlap, merge_intervals, count_max_overlap
from python_utils.algorithms.array.paired_elements import make_valid_by_minimum_removal, \
    make_valid_by_minimum_add
from python_utils.algorithms.array.streaming import reservoir_sample
from python_utils.algorithms.array.subarray import max_subarray_sum4, longest_consecutive_increasing, \
    max_subarray_product
from python_utils.algorithms.array.time_series import next_larger_in_time_series, find_all_historical_larger, \
    MovingAverage, find_right_side_max, find_left_side_max

"""
Using stack for pair matching or comparison
"""
make_valid_by_minimum_removal  # use a stack to record invalid indices and then have another pass to remove them
make_valid_by_minimum_add  # use a stack; handle case when there is open right
next_larger_in_time_series  # b > a is a pairwise relation, so we can use stack

"""
Bidirectional 2pass
"""
product_except_self  # in-place get left products of the whole array in one iteration, then iterate back from the right
find_equilibrium_indexes  # in-place get array sum in first iteration, then iterate again

"""
Binary Search
"""
binary_search  # Generic method; two variants: branching left includes mid or not
binary_post_order_result_compute  # Generic method; result compute includes `seq`, `mid_index`, `left_result` and `right_result`
binary_search_sorted_array_greater_than_or_equal_to_target  # Use `binary_search` method; branching left includes mid, and cond is "target <= mid"
binary_search_sorted_array_less_than_or_equal_to_target  # Use `binary_search` method; branching left excludes mid, and cond is "target < mid"
find_a_local_maximum  # Use `binary_search` method; branching left includes mid, and cond is "curr > mid"
find_a_local_minimum  # Use `binary_search` method; branching left includes mid, and cond is "curr < mid"

"""
Streaming Data Analysis
"""
next_larger_in_time_series  # from left to right, suitable for streaming data
reservoir_sample  # a sampling technique for streaming data
MovingAverage  # use a queue; can take an iterator, so suitable for streaming data; remember to handle initial cases

"""
Time Series Analysis
"""
longest_consecutive_increasing # simple scan through the sequence
next_larger_in_time_series  # b > a is a pairwise relation, so we can use stack
find_right_side_max  # one pass from the right
find_left_side_max  # one pass from the left
find_all_historical_larger  # simple intuitive algorithm; iterate from the right
MovingAverage  # use a queue; can take an iterator, so suitable for streaming data; remember to handle initial cases

"""
Subarray
"""
max_subarray_product # DP
max_subarray_sum4  # Kadane's algorithm; keep sequentially adding values, reset to 0 when negative; keep tracking `max_sum`


"""
Intervals
"""
has_overlap  # sort the interval array first, then sequentially check
merge_intervals  # sort the interval array first, then sequentially merge
count_max_overlap  # sort the interval array first, then use a heap to track the earliest conflicting time (the earliest ending time in the heap)
