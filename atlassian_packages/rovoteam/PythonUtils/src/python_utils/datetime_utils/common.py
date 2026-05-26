import random
from datetime import datetime, timedelta
from time import sleep, time
from typing import Union, Mapping, List, Tuple


def random_sleep(min_sleep, max_sleep):
    """
    Sleeps for a random duration between min_sleep and max_sleep.

    The function determines the sleep duration based on the following logic:
    1. If `max_sleep` is greater than 0:
        - If `max_sleep` is equal to `min_sleep`, the function sleeps exactly for `max_sleep` seconds.
        - If `max_sleep` is greater than `min_sleep`, the function sleeps for a random duration uniformly chosen between `min_sleep` and `max_sleep` seconds.
    2. If `max_sleep` is not greater than 0:
        - If `min_sleep` is greater than 0, the function sleeps exactly for `min_sleep` seconds.

    Args:
        min_sleep (float): Minimum sleep time in seconds.
        max_sleep (float): Maximum sleep time in seconds.

    Returns:
        None

    Examples:
        >>> start = time()
        >>> random_sleep(1, 2)
        >>> end = time()
        >>> 1 <= end - start <= 2.1
        True

        >>> start = time()
        >>> random_sleep(2, 2)
        >>> end = time()
        >>> abs(end - start - 2) < 0.1
        True

        >>> start = time()
        >>> random_sleep(2, 0)
        >>> end = time()
        >>> abs(end - start - 2) < 0.1
        True
    """
    if max_sleep > 0:
        if max_sleep == min_sleep:
            sleep(max_sleep)
        else:
            wait_time = random.uniform(min_sleep, max_sleep)
            sleep(wait_time)
    else:
        if min_sleep > 0:
            sleep(min_sleep)





def timestamp(scale=100) -> str:
    return str(int(time() * scale))


def solve_datetime(
        _dt_obj: Union[datetime, str, Mapping, List, Tuple],
        datetime_str_format: str = '%m/%d/%Y',
        delta: Union[int, Mapping, List, Tuple, timedelta] = None,
) -> datetime:
    """
    Solves the input object as a `datetime` object.
        For example, a string '10/30/2021' (with `datetime_str_format` '%m/%d/%Y'),
        or a dictionary `{"year": 2021, "month": 10, "day":30}`, or a tuple `(2021, 10, 30)`,
        will be solved as `datetime(year=2021, month=10, day=30)`.
    Args:
        _dt_obj: the input object to solve as a `datetime`; current support
            1. a string (format defined by the other parameter `datetime_str_format`);
            2. an iterable (e.g. tuple, list) that can be used as
        datetime_str_format: specifies a string format to solve a string object as a `datetime`.
        delta: adds this timedelta to the created `datetime` object;
            can specify an integer, which is `timedelta` in days;
            can specify a dictionary `{"days":7, "hours":3}`
                with keys being the parameter names of the `timedelta` object.

    Returns: the created `datetime` object solved from the input and optionally the time delta.

    """
    from python_utils.common_utils import solve_obj
    _dt_obj = solve_obj(
        _dt_obj, obj_type=datetime, str2obj=datetime.strptime, str_format=datetime_str_format
    )
    if delta is None:
        return _dt_obj
    else:
        return _dt_obj + solve_obj(delta, obj_type=timedelta)


def solve_date_time_format_by_granularity(
        granularity: str,
        date_format: str = '%Y%m%d',
        time_format: str = '%H%M%S'
) -> Tuple[str, str]:
    """
    This function solves the date and time format based on the given granularity.
    Args:
        granularity: Can be one of "year", "month", "day", "hour", "minute", "second".
        date_format: If provided, will be used as the base date format.
        time_format: If provided, will be used as the base time format.
    Returns:
        Tuple[str, str]: The solved date and time format.
    Examples:
        >>> solve_date_time_format_by_granularity('year', '%Y-%m-%d', '%H:%M:%S')
        ('%Y', '')
        >>> solve_date_time_format_by_granularity('month', '%Y-%m-%d', '%H:%M:%S')
        ('%Y-%m', '')
        >>> solve_date_time_format_by_granularity('day', '%Y-%m-%d', '%H:%M:%S')
        ('%Y-%m-%d', '')
        >>> solve_date_time_format_by_granularity('hour', '%Y-%m-%d', '%H:%M:%S')
        ('%Y-%m-%d', '%H')
        >>> solve_date_time_format_by_granularity('minute', '%Y-%m-%d', '%H:%M:%S')
        ('%Y-%m-%d', '%H:%M')
        >>> solve_date_time_format_by_granularity('second', '%Y-%m-%d', '%H:%M:%S')
        ('%Y-%m-%d', '%H:%M:%S')
        >>> solve_date_time_format_by_granularity('day', '%d/%m/%Y', '%H-%M-%S')
        ('%d/%m/%Y', '')
        >>> solve_date_time_format_by_granularity('month', '%d/%m/%Y', '%H-%M-%S')
        ('%m/%Y', '')
        >>> solve_date_time_format_by_granularity('year', '%d/%m/%Y', '%H-%M-%S')
        ('%Y', '')
        >>> solve_date_time_format_by_granularity('minute', '%d/%m/%Y', '%M/%H/%S')
        ('%d/%m/%Y', '%M/%H')
    """

    # Define the formats for date and time elements
    formats = ['year', 'month', 'day', 'hour', 'minute', 'second']
    format_codes = {
        'year': '%Y',
        'month': '%m',
        'day': '%d',
        'hour': '%H',
        'minute': '%M',
        'second': '%S'
    }

    # Identify the separators by replacing format elements with empty string
    date_separator = date_format
    time_separator = time_format
    for code in format_codes.values():
        date_separator = date_separator.replace(code, '')
        time_separator = time_separator.replace(code, '')

    # Initialize the new format strings
    new_date_format = date_format
    new_time_format = time_format

    # Iterate over the formats in order
    for format in formats:
        if format_codes[format] in date_format and formats.index(format) > formats.index(granularity):
            new_date_format = new_date_format.replace(format_codes[format], '')
        if format_codes[format] in time_format and formats.index(format) > formats.index(granularity):
            new_time_format = new_time_format.replace(format_codes[format], '')

    # Remove extra separators
    new_date_format = new_date_format.strip(date_separator).replace(date_separator * 2, date_separator)
    new_time_format = new_time_format.strip(time_separator).replace(time_separator * 2, time_separator)

    return new_date_format, new_time_format


def current_date_time_string(format_str=None):
    """
    Helper function to get current date/time with optional formatting.

    Args:
        format_str: Optional format string for datetime.strftime
                    Supported special formats:
                    - 'iso': ISO 8601 format (2025-02-19T14:30:49.123456)
                    - 'date': Date only (2025-02-19)
                    - 'time': Time only (14:30:49)
                    - 'full': Verbose format (Wednesday, February 19, 2025 at 14:30:49)
                    Or use any valid strftime format string like '%Y/%m/%d'

    Returns:
        str: Formatted date/time string
    """
    now = datetime.now()

    # Handle special format strings
    if format_str == 'iso':
        return now.isoformat()
    elif format_str == 'date':
        return now.strftime('%Y-%m-%d')
    elif format_str == 'time':
        return now.strftime('%H:%M:%S')
    elif format_str == 'full':
        return now.strftime('%A, %B %d, %Y at %H:%M:%S')
    elif format_str:
        # Use custom format string
        try:
            return now.strftime(format_str)
        except ValueError:
            # Fallback if format string is invalid
            return now.strftime("%Y-%m-%d %H:%M:%S")

    # Default format
    return now.strftime("%Y-%m-%d %H:%M:%S")


def current_date_string(format_str=None):
    """
    Return the current date in a chosen format.
    Defaults to '%Y-%m-%d' if no format_str is provided.
    """
    now = datetime.now()
    fmt = format_str or '%Y-%m-%d'
    try:
        return now.strftime(fmt)
    except ValueError:
        return now.strftime('%Y-%m-%d')  # fallback


def current_time_string(format_str=None):
    """
    Return the current time in a chosen format.
    Defaults to '%H:%M:%S' if no format_str is provided.
    """
    now = datetime.now()
    fmt = format_str or '%H:%M:%S'
    try:
        return now.strftime(fmt)
    except ValueError:
        return now.strftime('%H:%M:%S')  # fallback
