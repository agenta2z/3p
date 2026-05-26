from collections import defaultdict
from typing import Union, Callable

from python_utils.common_utils.map_helper import get_category_dict
from python_utils.common_utils.set_helper import is_subset


def build_ladder(arr):
    # TODO
    pass


def build_ladder_simple(
        arr,
        connection_func: Callable,
        order_label: Union[str, Callable],
        order_label_sort_key=None,
        order_label_sort_reverse=False
):
    """
    Builds a ladder where the next level only connects to
    the last node in the previous level. The results are represented by a sequence of lists.

    Examples:
        >>> build_ladder_simple(
        ...   [(1, 2, 3), (1, 2), (2, 3), (3,)],
        ...   connection_func=is_subset,
        ...   order_label=len,
        ...   order_label_sort_reverse=True
        ... )
        [[(1, 2, 3)], [(1, 2), (2, 3)], [(3,)]]

    """

    orders = get_category_dict(arr, categorization=order_label)
    ladder = [
        orders[order_key]
        for order_key
        in sorted(orders.keys(), key=order_label_sort_key, reverse=order_label_sort_reverse)
    ]
    for i in range(1, len(ladder)):
        last_branch_of_the_previous_level = ladder[i - 1][-1]
        for branch in ladder[i]:
            if not connection_func(branch, last_branch_of_the_previous_level):
                raise ValueError(f"branch of level {i} does not connect to "
                                 f"the last branch of the previous level; "
                                 f"if you intend to build a full multi-branch ladder, "
                                 f"use function 'build_ladder' instead")
    return ladder
