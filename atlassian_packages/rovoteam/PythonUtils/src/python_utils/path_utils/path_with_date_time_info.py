from datetime import datetime
from os import path
from typing import List, Mapping, Tuple, Union, Callable, Optional

import python_utils.datetime_utils
from python_utils.console_utils import hprint_message

from python_utils.datetime_utils.iter_dates import iter_dates
from python_utils.datetime_utils.common import solve_datetime


def add_date_time_to_path(
        original_path: str,
        date: Optional[datetime] = None,
        date_format: str = '%Y%m%d',
        time_format: str = '',
        unix_timestamp: bool = False,
        sep: str = '_'
) -> str:
    """
    Appends a date and optional time or Unix timestamp to a file or directory path.

    Args:
        original_path: Original file or directory path.
        date: Date to append. If None, uses the current date.
        date_format: Format for date string. Defaults to 'YYYYMMDD'.
        time_format: Format for time string. If empty, no time is appended.
        unix_timestamp: If True, appends Unix timestamp instead of date and time.
        sep: Separator to use between the original name and date or time string.

    Returns:
        Updated file or directory path with the date and optional time or Unix timestamp appended.

    Examples:
        >>> add_date_time_to_path('some_dir/file.txt')
        'some_dir/file_20230610.txt'
        >>> add_date_time_to_path('some_dir', date=datetime(2023, 6, 10), date_format='%Y-%m-%d', sep='-')
        'some_dir-2023-06-10'
        >>> add_date_time_to_path('some_dir', date=datetime(2023, 6, 10), date_format='%Y', sep='-')
        'some_dir-2023'
        >>> add_date_time_to_path('some_dir/', date=datetime(2023, 6, 10), date_format='%Y-%m-%d')
        'some_dir/2023-06-10'
        >>> add_date_time_to_path('some_dir/file.txt', date=datetime(2023, 6, 10, 12, 34, 56), time_format='%H%M%S')
        'some_dir/file_20230610_123456.txt'
        >>> add_date_time_to_path('some_dir/file.txt', date=datetime(2023, 6, 10, 12, 34, 56), unix_timestamp=True)
        'some_dir/file_1686425696.txt'
    """
    date = date or datetime.now()

    if unix_timestamp:
        date_str = str(int(date.timestamp()))
    else:
        date_str = date.strftime(date_format)
        if time_format:
            time_str = date.strftime(time_format)
            date_str += f'{sep}{time_str}'

    dir_name, base_name = path.split(original_path)
    base_name_main, ext = path.splitext(base_name)

    if base_name:
        # It's a file path
        new_base_name = f"{base_name_main}{sep}{date_str}{ext}"
    else:
        # It's a directory path
        new_base_name = date_str

    return path.join(dir_name, new_base_name)


def get_path_with_year_month_day(
        path_pattern: str,
        date: Union[datetime, str, Mapping, List, Tuple],
        end_date: Union[datetime, str, Mapping, List, Tuple] = None,
        date_str_format: str = "%m/%d/%Y",
        num_days_forward: int = None,
        num_days_backward: int = None,
        **kwargs,
) -> Union[str, List[str]]:
    """
    Gets one or more paths according to a string format pattern `path_pattern`
        like 's3://some_prefix/{year}/{month}/{day}/more_path_parts',
        and date range configuration of dates through other parameters.
    Argument `date` is required for at lest one string path.
    Specifies one of `end_date`, `num_days_forward` or `num_days_backward`
        to get a list of string paths.

    Args:
        path_pattern: a string format with three keys 'year', 'month' and 'day'.
        date: specifies a date for the path.
        end_date: if specified, will return a list of paths starting from using `date` (inclusive)
                until this `end_date` (inclusive).
        date_str_format: specifies a string format for `date`, `end_date`,
                if strings are provided for these arguments.
        num_days_forward: if specified, will return this number of paths
                with consecutive dates starting from using `date` (inclusive)
                until 'date + num_days_forward' (exclusive).
            not effective if `end_date` is specified.
        num_days_backward: if specified, will return this number of paths
                with consecutive dates starting from using 'date - num_days_backward' (exclusive)
                until `date` (inclusive).
            not effective if `end_date` is specified.
        **kwargs: any other keyed argument for the path string format pattern.

    Returns: a single path if none of `end_date`, `num_days_forward`
            or `num_days_backward` is specified;
    otherwise, a list of string paths according to the date range configuration.

    Examples:
        >>> print(get_path_with_year_month_day('s3://prefix/{year}/{month}/{day}/path', '12/31/2021'))
        s3://prefix/2021/12/31/path
        >>> print(get_path_with_year_month_day('s3://prefix/{year}/{month}/{day}/path', '12/31/2021', num_days_forward=3))
        ['s3://prefix/2021/12/31/path', 's3://prefix/2022/01/01/path', 's3://prefix/2022/01/02/path']
    """
    days_delta = None
    if num_days_forward is not None:
        if num_days_backward is not None:
            raise ValueError("cannot specify both 'num_days_forward' or 'num_days_backward'")
        if isinstance(num_days_forward, int) and num_days_forward > 0:
            days_delta = num_days_forward
        else:
            raise ValueError("parameter 'num_days_forward' must be a positive integer")
    elif num_days_backward is not None:
        if isinstance(num_days_backward, int) and num_days_backward > 0:
            days_delta = -num_days_backward
        else:
            raise ValueError("parameter 'num_days_back' must be a positive integer")

    if end_date is not None or days_delta is not None:
        out = []
        for dt_obj in iter_dates(
                start_date=date, end_date_inclusive=end_date, days_delta=days_delta
        ):
            out.append(
                path_pattern.format(
                    year=dt_obj.year, month=f"{dt_obj.month:02}", day=f"{dt_obj.day:02}", **kwargs
                )
            )
        return out
    else:
        dt_obj = solve_datetime(date, datetime_str_format=date_str_format)
        return path_pattern.format(
            year=dt_obj.year, month=f"{dt_obj.month:02}", day=f"{dt_obj.day:02}", **kwargs
        )


def next_available_path_with_year_month_day(
        path_pattern: str,
        start_date: Union[datetime, str, Mapping, List, Tuple],
        end_date: Union[datetime, str, Mapping, List, Tuple] = None,
        days_delta=None,
        date_str_format: str = '%m/%d/%Y',
        path_exists: Callable = path.exists,
        return_hit_date: bool = False,
        verbose: bool = False,
        **path_pattern_kwargs
):
    for date in python_utils.datetime_utils.iter_dates.iter_dates(
            start_date=start_date,
            end_date_inclusive=end_date,
            days_delta=days_delta,
            date_str_format=date_str_format,
            always_forward_iter_if_possible=False
    ):
        _path = path_pattern.format(
            year=date.year,
            month=f'{date.month:02}',
            day=f'{date.day:02}',
            **path_pattern_kwargs
        )
        if path_exists(_path):
            if verbose:
                hprint_message('path exists', _path)
            if return_hit_date:
                return _path, date
            else:
                return _path
        else:
            if verbose:
                hprint_message('path not exist', _path)
    if return_hit_date:
        return None, None
    else:
        return None
