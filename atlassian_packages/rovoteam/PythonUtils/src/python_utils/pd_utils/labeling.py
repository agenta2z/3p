from typing import List

import numpy as np
import pandas as pd


def add_bin_col(
        df,
        src_col: str,
        bins: List,
        labels: List = None,
        output_col: str = None,
        add_left_inf: bool = True,
        add_right_inf: bool = True,
        right: bool = False
):
    """
    Adds a new column to a dataframe. The new column is a binned version of an existing column
    based on specified bin intervals and labels.

    Args:
        df: The dataframe to be processed.
        src_col: The column name from the dataframe to be binned.
        bins: The bin intervals to be applied to the column.
        labels: The labels for the bins. If not provided, bin values are used as labels.
        output_col: The name of the new column. If not provided, the source column name is used.
        add_left_inf: Whether to add -infinity to the left end of bin intervals. Default is True.
        add_right_inf: Whether to add infinity to the right end of bin intervals. Default is True.
        right: Whether the intervals include the right or the left bin edge. Default is False.

    Returns:
        The processed dataframe with the new binned column.

    Examples:
        >>> df = pd.DataFrame({'age': [18, 22, 45, 67, 31, 34, 56, 100]})
        >>> bins = [20, 30, 40, 50, 60, 70]
        >>> add_bin_col(df, 'age', bins, output_col='age_group', right=True)
           age age_group
        0   18        19
        1   22        20
        2   45        40
        3   67        60
        4   31        30
        5   34        30
        6   56        50
        7  100        70
    """
    if labels is None:
        labels = bins
    if output_col is None:
        output_col = src_col

    if add_left_inf:
        if bins[0] != -np.inf:
            bins = [-np.inf, *bins]
        if right and len(labels) == len(bins) - 1:
            if isinstance(labels[0], int):
                labels = [labels[0] - 1, *labels]
            else:
                raise ValueError(
                    f"cannot automatically assign a label for the '-inf' to {labels[0]} bin"
                )
    if add_right_inf:
        if bins[-1] != np.inf:
            bins = [*bins, np.inf]
        if (not right) and len(labels) == len(bins) - 1:
            if isinstance(labels[-1], int):
                labels = [*labels, labels[-1] + 1]
            else:
                raise ValueError(
                    f"cannot automatically assign a label for the {labels[-1]} to 'inf' bin"
                )

    df[output_col] = pd.cut(df[src_col], bins=bins, labels=labels, right=right)
    return df
