from datetime import datetime
from typing import Iterable, List
from typing import Union, Callable

import pandas as pd
from pandas import DataFrame

from python_utils.common_utils import iter_, zip__
from python_utils.pd_utils.selection import select_range_inclusive
from python_utils.string_utils.date_and_time import minus_n_days
from python_utils.datetime_utils.iter_dates import iter_date_ranges_by_end_date


def add_pct_change_columns(
        df: DataFrame,
        colnames: Union[List[str], str],
        output_colname_suffix: str = '_pct_change',
        output_colnames: Union[List[str], str] = None,
        multiply100: bool = False,
        inplace: bool = False
) -> DataFrame:
    """
    Calculate the percentage change for the specified columns of a pandas DataFrame.
    If `multiply100` is True, the changes are expressed in percent (i.e., value multiplied by 100).

    Args:
        df: The original pandas DataFrame.
        colnames: The column(s) for which to calculate the percentage change.
        output_colname_suffix: Suffix to add to the original column names to create the output
                               column names. Only used if `output_colnames` is not provided.
                               Default is '_pct_change'.
        output_colnames: Names of the output columns. If provided, these names are used instead
                         of creating names based on the original column names. Default is None.
        multiply100: Whether to multiply the calculated percentage change by 100. Default is False.
        inplace: Whether to modify the original DataFrame. If False, return a new DataFrame with
                 the percentage change columns added. Default is False.

    Returns:
        A pandas DataFrame with the percentage change columns added.

    Example:
        >>> df = DataFrame({
        ...    'A': [1, 2, 3, 4, 5, 6],
        ...    'B': [10, 15, 20, 25, 30, 35],
        ...    'C': [100, 200, 300, 400, 500, 600]
        ... })
        >>> print(df)
           A   B    C
        0  1  10  100
        1  2  15  200
        2  3  20  300
        3  4  25  400
        4  5  30  500
        5  6  35  600
        >>> df_new = add_pct_change_columns(df, ['A', 'B'], multiply100=True)
        >>> print(df_new)
           A   B    C  A_pct_change  B_pct_change
        0  1  10  100           NaN           NaN
        1  2  15  200    100.000000     50.000000
        2  3  20  300     50.000000     33.333333
        3  4  25  400     33.333333     25.000000
        4  5  30  500     25.000000     20.000000
        5  6  35  600     20.000000     16.666667
    """
    if not inplace:
        df = df.copy()

    if output_colnames:
        for colname, output_colname in zip__(colnames, output_colnames):
            if multiply100:
                df[output_colname] = df[colname].pct_change() * 100
            else:
                df[output_colname] = df[colname].pct_change()
    else:
        for colname in iter_(colnames):
            output_colname = colname
            if output_colname_suffix:
                output_colname += output_colname_suffix
            if multiply100:
                df[output_colname] = df[colname].pct_change() * 100
            else:
                df[output_colname] = df[colname].pct_change()

    return df


def get_first_last_row_pct_change(
        df: DataFrame,
        colnames: Union[List[str], str],
        multiply100: bool = False,
        only_return_last_row: bool = True
):
    """
    Calculate the percentage change between the first and the last row of the specified columns
    in a pandas DataFrame.

    Args:
        df: The original pandas DataFrame.
        colnames: The column(s) for which to calculate the percentage change.
        multiply100: Whether to multiply the calculated percentage change by 100. Default is False.
        only_return_last_row: Whether to return only the last row with the calculated percentage
                              change. If False, returns both the first and the last row. Default is True.

    Returns:
        A pandas DataFrame with the first and/or last row(s) and the calculated percentage change
        for the specified columns.

    Example:
        >>> df = DataFrame({
        ...    'A': [1, 2, 3, 4, 5, 6],
        ...    'B': [10, 15, 20, 25, 30, 35],
        ...    'C': [100, 200, 300, 400, 500, 600]
        ... })
        >>> print(df)
           A   B    C
        0  1  10  100
        1  2  15  200
        2  3  20  300
        3  4  25  400
        4  5  30  500
        5  6  35  600
        >>> df_change = get_first_last_row_pct_change(df, ['A', 'B'], multiply100=True)
        >>> print(df_change)
           A   B    C  A_pct_change  B_pct_change
        5  6  35  600         500.0         250.0
    """
    df_first_last_row = add_pct_change_columns(
        df=df.iloc[[0, -1]].copy(),
        colnames=colnames,
        multiply100=multiply100,
        inplace=True
    )

    if only_return_last_row:
        return df_first_last_row.tail(1).copy()
    else:
        return df_first_last_row


def time_series_stats(
        df,
        windows: Iterable[int],
        stat_cols: Iterable[str],
        cols_to_add_as_pct_change: Iterable[str] = None,
        cols_to_overwrite_as_pct_change: Iterable[str] = None,
        added_pct_change_col_suffix: str = '_pct_change',
        stats: Iterable[str] = ('min', 'max', 'median', 'mean', 'std'),
        pct_change_multiply_100: bool = False,
        concat_source_data: bool = True
):
    """
    Generate statistics and percentage change features for a DataFrame along a rolling window.

    Args:
        df: The original DataFrame.
        windows: The window sizes for rolling operations.
        stat_cols: Columns on which to compute statistics.
        cols_to_add_as_pct_change (optional): Columns for which to add percentage change as new columns.
        cols_to_overwrite_as_pct_change (optional): Columns to overwrite with their percentage change.
        added_pct_change_col_suffix: A name suffix for the columns added by `cols_to_overwrite_as_pct_change`.
        stats (optional): The statistic types to compute. Default is 'min', 'max', 'median', 'mean', 'std'.
        pct_change_multiply_100: True the multiply the percentage change by 100.
        concat_source_data: True to concat with the source data (after "pct_change").

    Returns:
        DataFrame with original data and new features.

    Example:
        >>> df = pd.DataFrame({
        ...     'A': range(10),
        ...     'B': range(10, 20),
        ...     'C': range(20, 30),
        ... })
        >>> time_series_stats(df, [3], ['A', 'B'], ['C'])
           A_min_3  A_max_3  A_median_3  ...  B_median_3  B_mean_3  B_std_3
        0      NaN      NaN         NaN  ...         NaN       NaN      NaN
        1      NaN      NaN         NaN  ...         NaN       NaN      NaN
        2      0.0      2.0         1.0  ...        11.0      11.0      1.0
        3      1.0      3.0         2.0  ...        12.0      12.0      1.0
        4      2.0      4.0         3.0  ...        13.0      13.0      1.0
        5      3.0      5.0         4.0  ...        14.0      14.0      1.0
        6      4.0      6.0         5.0  ...        15.0      15.0      1.0
        7      5.0      7.0         6.0  ...        16.0      16.0      1.0
        8      6.0      8.0         7.0  ...        17.0      17.0      1.0
        9      7.0      9.0         8.0  ...        18.0      18.0      1.0
        <BLANKLINE>
        [10 rows x 10 columns]
    """

    stats = list(stats)

    if cols_to_add_as_pct_change:
        if pct_change_multiply_100:
            df_pct_change = df[list(cols_to_add_as_pct_change)].pct_change() * 100
        else:
            df_pct_change = df[list(cols_to_add_as_pct_change)].pct_change()
        df_pct_change.columns = [col + added_pct_change_col_suffix for col in df_pct_change.columns]
        df = pd.concat([df, df_pct_change], axis=1)

    if cols_to_overwrite_as_pct_change:
        if pct_change_multiply_100:
            df[list(cols_to_overwrite_as_pct_change)] = df[list(cols_to_overwrite_as_pct_change)].pct_change() * 100
        else:
            df[list(cols_to_overwrite_as_pct_change)] = df[list(cols_to_overwrite_as_pct_change)].pct_change()

    if concat_source_data:
        results = [df]
    else:
        results = []
    for window in windows:
        df_stats = df[stat_cols].rolling(window).agg(
            {stat_col: stats for stat_col in stat_cols}
        )
        df_stats.columns = [f'{col[0]}_{col[1]}_{window}' for col in df_stats.columns]
        results.append(df_stats)

    return pd.concat(results, axis=1)


def eval_change_by_weeks(
        df: DataFrame,
        end_date_inclusive: Union[str, datetime],
        num_days_backward: int,
        compare_change_func: Callable[[DataFrame], DataFrame],
        interval_num_weeks: int = 1,
        date_colname='Date',
        date_str_format='%Y-%m-%d',
        compare_with_the_end_of_the_previous_week: bool = False
):
    """
    Given a dataframe with a date column in ascending order,
    but not every date has data (e.g. a stock market dataframe),
    evaluate changes between every n week,
    where n is specified by `interval_num_weeks`.

    When the dataframe has missing dates (e.g. stock market closes on weekends and holidays),
    we cannot simply collapse the dataframe by every n * 7 days.
    In this case, we have to select
    We have to select data based on the weekly start date and end date, make comparison,
    and concat each week's change evaluation back to a complete dataframe.


   Args:
        df: A DataFrame with a date column, which may have missing dates.
        end_date_inclusive: The end date of the range to consider, inclusive. Can be a string or a datetime.
        num_days_backward: The number of days backward from the end_date_inclusive to consider.
        compare_change_func: A function that takes a DataFrame and returns a DataFrame. Used to calculate the
            changes to evaluate.
        interval_num_weeks: The interval, in weeks, at which to evaluate changes.
        date_colname: The name of the date column in df. Defaults to 'Date'.
        date_str_format: The format of the date strings in the date column of df. Defaults to '%Y-%m-%d'.
        compare_with_the_end_of_the_previous_week: Whether to compare with the end of the previous week.
            Defaults to False.

    Returns:
        A DataFrame obtained by concatenating the DataFrames returned by applying compare_change_func
        to the relevant subsets of df.

    Returns:

    """
    out = []
    for start_date, end_date in iter_date_ranges_by_end_date(
            num_days=num_days_backward,
            end_date_inclusive=end_date_inclusive,
            batch_size=7 * interval_num_weeks,
            date_str_format=date_str_format,
            yield_start_date=True
    ):
        df_week = select_range_inclusive(
            df,
            date_colname,
            start=(
                minus_n_days(start_date, 3, date_str_format=date_str_format)
                if compare_with_the_end_of_the_previous_week
                else start_date
            ),
            end=end_date
        )

        if len(df_week):
            if compare_change_func:
                out.append(compare_change_func(df_week))
            else:
                out.append(df_week)

    return pd.concat(out[::-1])
