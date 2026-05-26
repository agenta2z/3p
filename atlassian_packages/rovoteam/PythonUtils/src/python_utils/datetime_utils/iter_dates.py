import calendar
import datetime
import sys
from datetime import datetime, timedelta
from typing import Union, Mapping, List, Tuple, Iterator, Iterable

from python_utils.common_utils import iter_
from python_utils.datetime_utils.common import solve_datetime


def solve_start_date_with_days_delta(
        start_date: Union[datetime, str, Mapping, List, Tuple],
        end_date_inclusive: Union[datetime, str, Mapping, List, Tuple] = None,
        end_date_exclusive: Union[datetime, str, Mapping, List, Tuple] = None,
        days_delta=None,
        date_str_format: str = '%m/%d/%Y',
        return_days_delta=False,
        solve_negative_days_delta: bool = True
):
    start_date = solve_datetime(start_date, datetime_str_format=date_str_format)

    if days_delta != float('-inf') and days_delta != float('-inf'):
        if end_date_inclusive is not None:
            if end_date_exclusive is not None:
                raise ValueError(
                    "can only specify one of 'end_date_inclusive' and 'end_date_exclusive'"
                )
            days_delta = (
                    solve_datetime(
                        end_date_inclusive,
                        datetime_str_format=date_str_format
                    ) - start_date
            ).days
            if days_delta < 0:
                days_delta -= 1
            else:
                days_delta += 1
        elif end_date_exclusive is not None:
            days_delta = (
                    solve_datetime(
                        end_date_exclusive,
                        datetime_str_format=date_str_format
                    ) - start_date
            ).days

        if days_delta is not None and solve_negative_days_delta and days_delta < 0:
            start_date = start_date + timedelta(days=days_delta + 1)
            days_delta = -days_delta

    if return_days_delta:
        return start_date, days_delta
    else:
        return start_date


def is_partial_or_single_batch(
        num_days: int,
        end_date_inclusive: Union[datetime, str],
        batch_size: Union[int, str, Iterable[int]] = "monthly",
        date_str_format: str = "%m/%d/%Y",
) -> bool:
    """
    Determine if the number of days can be considered as a single or partial batch for the given
    batch size and end date.

    Args:
        num_days: An integer specifying the total number of days to check.
        end_date_inclusive: A datetime object or a string representing the end date (inclusive) for
            the sequence of date ranges.
        batch_size: A value or sequence of values specifying the size of each batch of date ranges.
            It can be an integer, a string (e.g., 'monthly' or 'biweekly'), or an iterable of
            integers. Defaults to 'monthly'.
        date_str_format: A string specifying the format of the `end_date_inclusive` argument when
            it is provided as a string. Defaults to '%m/%d/%Y'.

    Returns:
        A boolean value indicating if the number of days can be considered as a single or partial
        batch for the given batch size and end date.

    Examples:
        >>> is_partial_or_single_batch(10, datetime(2023, 5, 20), batch_size='monthly')
        True
        >>> is_partial_or_single_batch(32, datetime(2023, 5, 20), batch_size='monthly')
        False
        >>> is_partial_or_single_batch(12, datetime(2023, 5, 20), batch_size='biweekly')
        True
        >>> is_partial_or_single_batch(16, datetime(2023, 5, 20), batch_size='biweekly')
        False
        >>> is_partial_or_single_batch(10, datetime(2023, 5, 20), batch_size=20)
        True
    """
    if batch_size == "monthly":
        if num_days <= 28:
            return True
        elif num_days > 31:
            return False
        else:
            if isinstance(end_date_inclusive, str):
                end_date_inclusive = datetime.strptime(end_date_inclusive, date_str_format)

            if num_days <= end_date_inclusive.day:
                return True
            return (end_date_inclusive - timedelta(days=num_days)).day != 1

    elif batch_size == "biweekly":
        if num_days <= 13:
            return True
        elif num_days > 15:
            return False
        elif end_date_inclusive.day > 15:
            return True
        else:
            if isinstance(end_date_inclusive, str):
                end_date_inclusive = datetime.strptime(end_date_inclusive, date_str_format)
            if num_days <= end_date_inclusive.day:
                return True
            else:
                return (end_date_inclusive - timedelta(days=num_days)).day != 16
    elif isinstance(batch_size, int):
        return num_days <= batch_size


def iter_dates(
        start_date: Union[datetime, str, Mapping, List, Tuple],
        end_date_inclusive: Union[datetime, str, Mapping, List, Tuple] = None,
        end_date_exclusive: Union[datetime, str, Mapping, List, Tuple] = None,
        days_delta=None,
        date_str_format: str = '%m/%d/%Y',
        always_forward_iter_if_possible: bool = True,
        output_date_str_format: Union[str, bool] = None
) -> Iterator[datetime]:
    """
    Iterates `datetime` objects starting from the `start_date` (always inclusive);
        the end date is specified by one of
        `end_date_inclusive` or `end_date_exclusive` or `days_delta`.

    Args:
        start_date: iterate `datetime` objects starting from this date;
                always inclusive regardless of other parameters.
            can specify an object solvable by the `solve_datetime` function.
        end_date_inclusive: if specified, iterate until this date;
            can specify an object solvable by the `solve_datetime` function.
        end_date_exclusive: if specified, iterate until the day before this date.
            can specify an object solvable by the `solve_datetime` function.
        days_delta: if specified, iterate this number of days until 'start_date + days_delta';
            can be a negative integer and then we iterate this number of days before `start_date`;
            not effective if one of `end_date_inclusive` or `end_date_exclusive` is specified.
        date_str_format: specifies a string format for `start_date`, `end_date_inclusive`
            and `end_date_exclusive` if strings are provided for these arguments.
        always_forward_iter_if_possible: controls the iteration behavior when `end_date_inclusive`
            or `end_date_exclusive` is before `start_date`, or when `days_delta` is negative.
            When this is True, the iteration always starts with the first date of the iteration
            time window; if this is set False, we start with the last date of the iteration time
            window if `start_date` is actually the last day.
        output_date_str_format: specify True to format output date using the same format string as
            `date_str_format`; or specify another format string for each output date; or specify
            None to return the datetime object.

    Examples:
        >>> list(iter_dates(
        ...    start_date= '07/10/2022',
        ...    days_delta= 3,
        ...    output_date_str_format = True
        ... ))
        ['07/10/2022', '07/11/2022', '07/12/2022']

        >>> list(iter_dates(
        ...    start_date = '07/10/2022',
        ...    days_delta = -3,
        ...    output_date_str_format = True
        ... ))
        ['07/08/2022', '07/09/2022', '07/10/2022']

        >>> list(iter_dates(
        ...    start_date = '07/10/2022',
        ...    days_delta = -3,
        ...    always_forward_iter_if_possible = False,
        ...    output_date_str_format = True
        ... ))
        ['07/10/2022', '07/09/2022', '07/08/2022']

        >>> list(iter_dates(
        ...    start_date='07/10/2022',
        ...    end_date_inclusive = '07/13/2022',
        ...    output_date_str_format=True
        ... ))
        ['07/10/2022', '07/11/2022', '07/12/2022', '07/13/2022']

        >>> list(iter_dates(
        ...    start_date='07/10/2022',
        ...    end_date_exclusive = '07/13/2022',
        ...    output_date_str_format=True
        ... ))
        ['07/10/2022', '07/11/2022', '07/12/2022']

        >>> list(iter_dates(
        ...    start_date='07/13/2022',
        ...    end_date_inclusive = '07/10/2022',
        ...    always_forward_iter_if_possible = False,
        ...    output_date_str_format=True
        ... ))
        ['07/13/2022', '07/12/2022', '07/11/2022', '07/10/2022']

        >>> list(iter_dates(
        ...    start_date='07/13/2022',
        ...    end_date_exclusive = '07/10/2022',
        ...    always_forward_iter_if_possible = False,
        ...    output_date_str_format=True
        ... ))
        ['07/13/2022', '07/12/2022', '07/11/2022']

        >>> from itertools import islice
        >>> list(islice(iter_dates(
        ...    start_date='07/10/2022',
        ...    days_delta = float('inf'),
        ...    output_date_str_format=True
        ... ), 3))
        ['07/10/2022', '07/11/2022', '07/12/2022']

        >>> from itertools import islice
        >>> list(islice(iter_dates(
        ...    start_date='07/10/2022',
        ...    days_delta = float('-inf'),
        ...    output_date_str_format=True
        ... ), 3))
        ['07/10/2022', '07/09/2022', '07/08/2022']

    Returns: an iterator of datetime objects.

    """
    start_date, days_delta = solve_start_date_with_days_delta(
        start_date=start_date,
        end_date_inclusive=end_date_inclusive,
        end_date_exclusive=end_date_exclusive,
        days_delta=days_delta,
        date_str_format=date_str_format,
        return_days_delta=True,
        solve_negative_days_delta=always_forward_iter_if_possible
    )

    if output_date_str_format is True:
        output_date_str_format = date_str_format

    def _day():
        return day.strftime(output_date_str_format) if output_date_str_format else day

    day = start_date
    yield _day()

    if days_delta == float('inf'):
        while True:
            day = day + timedelta(days=1)
            yield _day()
    elif days_delta == float('-inf'):
        while True:
            day = day + timedelta(days=-1)
            yield _day()
    elif days_delta > 0:
        for i in range(1, days_delta):
            day = day + timedelta(days=1)
            yield _day()
    elif days_delta < 0:
        for i in range(1, abs(days_delta)):
            day = day + timedelta(days=-1)
            yield _day()


def _get_date_range(
        num_days_backward,
        end_date_inclusive,
        yield_start_date,
        format_output_date_as_string,
        date_str_format
):
    _end_date_inclusive = (
        end_date_inclusive.strftime(date_str_format)
        if format_output_date_as_string
        else end_date_inclusive
    )
    if yield_start_date:
        start_date_inclusive = end_date_inclusive - timedelta(days=num_days_backward - 1)
        _start_date_inclusive = (
            start_date_inclusive.strftime(date_str_format)
            if format_output_date_as_string
            else start_date_inclusive
        )
        return _start_date_inclusive, _end_date_inclusive
    else:
        return num_days_backward, _end_date_inclusive


def iter_monthly_num_days_backward(
        end_date_inclusive: Union[datetime, str],
        date_str_format: str = '%m/%d/%Y',
        max_num_months: int = None,
        max_num_days: int = None,
        partial_first_month: bool = True,
        partial_last_month: bool = True,
        return_end_date: bool = False,
        format_output_date_as_string: bool = True,
        yield_start_date: bool = False,
        biweekly: bool = False
) -> Iterable[Union[int, Tuple[int, Union[datetime, str]]]]:
    """
    This function generates the number of days in each month, starting from the month of the
    `end_date_inclusive` argument and working backwards in time. The number of months generated
    is equal to the `max_num_months` argument if it is provided. Also the function stops generating
    once the total number of days generated reaches the `max_num_days` if it is provided.


    Args:
        end_date_inclusive: A datetime object or a string in the format
            specified by date_str_format that represents the end date (inclusive) from which to
            start generating the number of days for each month.
        date_str_format: A string that specifies the format of the end_date_inclusive
            argument when it is provided as a string. Defaults to '%m/%d/%Y'.
        max_num_months: An integer that specifies the number of months to generate backwards
            from the end_date_inclusive. If not provided, all months will be generated backwards
            from the end_date_inclusive.
        max_num_days: An integer that specifies the maximum number of days to generate
            backwards from the `end_date_inclusive`. If not provided, all months will be generated
            backwards from the `end_date_inclusive`.
        partial_first_month: True to generate a partial number of days for the first month,
            if the time period indicates a partial first month. For example,
            if `end_date_inclusive` is '02/15/2023' and `max_num_days` is 365, then the first
            month in the time period is Feb 2023, and it has a partial number of days '15' if
            this argument is True, or '28' days of a full month if this argument is False.
        partial_last_month: True to generate a partial number of days for Feb 2023,
            if the time period indicates a partial last month. For example,
            if `end_date_inclusive` is '02/15/2023' and `max_num_days` is 365, then the last
            month in the time period is Jan 2022, and it has a partial number of days '13' if
            this argument is True, or '31' days of a full Jan 2022 month if this argument is False.
        return_end_date: True to yield the end date corresponding to each returned number of days.
        format_output_date_as_string: format the ouput end date as string.
        biweekly: A boolean flag that indicates whether the function should generate the
                    number of days biweekly (every two weeks) instead of the whole month.
        ...
    Returns:
        An iterable that generates the number of days in each month, working backwards from the
        `end_date_inclusive` date until either `max_num_months` months have been generated or the
        total number of days generated reaches `max_num_days`. Optionally generates the end date
        corresponding to each number of days if `return_end_date` is set True.

    Raises:
        ValueError: If `end_date_inclusive` argument is not a valid datetime object or string in
            the format specified by `date_str_format`.
        ValueError: If `max_num_months` argument is not a positive integer.
        ValueError: If `max_num_days` argument is not a positive integer.

    Example usage:

    # Example 1: Generate the number of days for each month backwards from the end of 2023 for 3 months
    >>> from datetime import datetime
    >>> list(iter_monthly_num_days_backward(datetime(2023, 12, 31), max_num_months=3))
    [31, 30, 31]

    # Example 2: Generate the number of days for each month backwards from the end of 2023 for all months
    >>> list(iter_monthly_num_days_backward(datetime(2023, 12, 31), max_num_months=12))
    [31, 30, 31, 30, 31, 31, 30, 31, 30, 31, 28, 31]

    # Example 3: Generate the number of days for each month backwards from a string date
    >>> list(iter_monthly_num_days_backward('06/01/2022', date_str_format='%m/%d/%Y', max_num_months=6))
    [1, 31, 30, 31, 28, 31]

    # Example 4: Generate the number of days for each month backwards from a date until 365 days have been generated
    >>> list(iter_monthly_num_days_backward(datetime(2023, 2, 15), max_num_days=411))
    [15, 31, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31, 28, 31]

    # Example 5: Generate the number of days for each month backwards from a string date;
    # also yields end date corresponding to each number of days.
    >>> from datetime import datetime
    >>> list(iter_monthly_num_days_backward(
    ...    '06/01/2022',
    ...    date_str_format='%m/%d/%Y',
    ...    max_num_months=6,
    ...    return_end_date=True,
    ... ))
    [(1, '06/01/2022'), (31, '05/31/2022'), (30, '04/30/2022'), (31, '03/31/2022'), (28, '02/28/2022'), (31, '01/31/2022')]

    # Example 6: Generate the number of days biweekly for each month backwards from a date
    >>> list(iter_monthly_num_days_backward(
    ...    datetime(2023, 2, 15),
    ...    max_num_days=46,
    ...    biweekly=True)
    ... )
    [15, 16, 15]
    >>> list(iter_monthly_num_days_backward(
    ...    datetime(2023, 2, 15),
    ...    max_num_days=46,
    ...    biweekly=True,
    ...    return_end_date=True)
    ... )
    [(15, '02/15/2023'), (16, '01/31/2023'), (15, '01/15/2023')]

    """

    if isinstance(end_date_inclusive, str):
        end_date_inclusive = datetime.strptime(end_date_inclusive, date_str_format)

    if max_num_months is None:
        max_num_months = sys.maxsize
    if max_num_days is None:
        max_num_days = sys.maxsize

    if max_num_months < 0:
        raise ValueError("'max_num_months' must be a positive integer")
    if max_num_days < 0:
        raise ValueError("'max_num_days' must be a positive integer")

    num_days_last_month = (end_date_inclusive - datetime(
        year=end_date_inclusive.year,
        month=end_date_inclusive.month,
        day=1
    )).days + 1

    if partial_last_month:
        if biweekly and num_days_last_month > 15:
            month_base_date = 16
        else:
            month_base_date = 1
            max_num_months -= 1

        num_days = (end_date_inclusive - datetime(
            year=end_date_inclusive.year,
            month=end_date_inclusive.month,
            day=month_base_date
        )).days + 1

        num_days = min(max_num_days, num_days)

        if return_end_date:
            yield _get_date_range(
                num_days_backward=num_days,
                end_date_inclusive=end_date_inclusive,
                yield_start_date=yield_start_date,
                format_output_date_as_string=format_output_date_as_string,
                date_str_format=date_str_format
            )
        else:
            yield num_days
        num_days_last_month -= num_days
        end_date_inclusive -= timedelta(days=num_days)
        max_num_days -= num_days

    if not max_num_days or not max_num_months:
        return

    if 0 < num_days_last_month <= 15 and biweekly:
        if return_end_date:
            end_date_inclusive_mid_month = datetime(
                year=end_date_inclusive.year,
                month=end_date_inclusive.month,
                day=num_days_last_month
            )
            yield _get_date_range(
                num_days_backward=num_days_last_month,
                end_date_inclusive=end_date_inclusive_mid_month,
                yield_start_date=yield_start_date,
                format_output_date_as_string=format_output_date_as_string,
                date_str_format=date_str_format
            )
        else:
            yield num_days_last_month
        end_date_inclusive -= timedelta(days=num_days_last_month)
        max_num_days -= num_days_last_month
        max_num_months -= 1

    while max_num_months and max_num_days:
        num_days_in_month = calendar.monthrange(end_date_inclusive.year, end_date_inclusive.month)[1]
        num_days = (num_days_in_month - 15) if biweekly else num_days_in_month

        if partial_first_month:
            num_days = min(max_num_days, num_days)
        if return_end_date:
            yield _get_date_range(
                num_days_backward=num_days,
                end_date_inclusive=end_date_inclusive,
                yield_start_date=yield_start_date,
                format_output_date_as_string=format_output_date_as_string,
                date_str_format=date_str_format
            )
        else:
            yield num_days
        max_num_days -= num_days
        end_date_inclusive -= timedelta(days=num_days)

        if biweekly:
            num_days = 15
            if partial_first_month:
                num_days = min(max_num_days, num_days)
            if return_end_date:
                yield _get_date_range(
                    num_days_backward=num_days,
                    end_date_inclusive=end_date_inclusive,
                    yield_start_date=yield_start_date,
                    format_output_date_as_string=format_output_date_as_string,
                    date_str_format=date_str_format
                )
            else:
                yield num_days
            max_num_days -= num_days
            end_date_inclusive -= timedelta(days=num_days)

        max_num_months -= 1


def iter_date_ranges_by_end_date(
        num_days: int,
        end_date_inclusive: Union[datetime, str],
        batch_size: Union[int, str, Iterable[int]] = 'monthly',
        date_str_format: str = '%m/%d/%Y',
        yield_start_date: bool = False,
        format_output_date_as_string: bool = True
) -> Iterator[Tuple[Union[int, datetime, str], Union[datetime, str]]]:
    """

    This function generates a sequence of (batch_num_days, batch_end_date_inclusive) tuples, where
    the sum of the 'batch_num_days' values equals the `num_days` argument, and the
    'batch_end_date_inclusive' values are spaced backwards in time according to `num_days`,
    `end_date_inclusive` and `batch_size`. The function allows for a fixed batch size
    (provided as an int or iterable of ints), or monthly batches (i.e., batches where each one
    represents a whole month).

    Args:
        num_days: An integer that specifies the total number of days to be generated.
        end_date_inclusive: A datetime object or a string in the
            format specified by date_str_format that represents the end date (inclusive) for the
            sequence of date ranges to be generated.
        batch_size (Union[int, str, Iterable[int]], optional): A value or sequence of values that
            specifies the size of each batch of date ranges to be generated. If 'monthly', each
            batch will be equal to the number of days in each month starting from the month of the
            `end_date_inclusive` argument and working backwards in time until the required number
            of days is generated (see also `iter_monthly_num_days_backward`).
            If an integer is provided, it represents the size of each batch
            (in days). If an iterable is provided, it specifies the number of days in each batch in
            sequence; and if the sum of `batch_size` is less than `num_days`, then the last number
            in `batch_size` will be used to exhaust the remaining `num_days`.
        date_str_format: A string that specifies the format of the
            `end_date_inclusive` argument when it is provided as a string. Defaults to '%m/%d/%Y'.
        format_output_date_as_string (bool, optional): A boolean that specifies whether the
            end_date_inclusive values returned should be formatted as strings (using the
            `date_str_format` argument).

    Returns:
        An iterator that yields (batch_num_days, batch_end_date_inclusive) tuples until the
        required number of days is generated.

    Examples:
        # Example 1: Generate 90 days in monthly batches starting from end of 2023
        >>> from datetime import datetime
        >>> list(iter_date_ranges_by_end_date(90, datetime(2023, 12, 31), batch_size='monthly'))
        [(31, '12/31/2023'), (30, '11/30/2023'), (29, '10/31/2023')]

        # Example 2: Generate 50 days in batches of 15, 10, and 15 days starting from end of 2023;
        # the sum of `batch_size` (which is 40) is less than `num_days` (which is 50),
        # and in this case the last number '15' in `batch_size` is used to exhaust the remaining
        # `num_days`.
        >>> list(iter_date_ranges_by_end_date(50, datetime(2023, 12, 31), batch_size=[15, 10, 15]))
        [(15, '12/31/2023'), (10, '12/16/2023'), (15, '12/06/2023'), (10, '11/21/2023')]

        # Example 3: Generate 45 days in batches of 20, 10, and 5 days starting from end of 2023;
        # the sum of `batch_size` (which is 35) is less than `num_days` (which is 45),
        # and in this case the last number '5' in `batch_size` is used to exhaust the remaining
        # `num_days`.
        >>> list(iter_date_ranges_by_end_date(45, datetime(2023, 12, 31), batch_size=[20, 10, 5]))
        [(20, '12/31/2023'), (10, '12/11/2023'), (5, '12/01/2023'), (5, '11/26/2023'), (5, '11/21/2023')]

        # Example 4: Generate 46 days in biweekly batches (every two weeks) starting from February 15, 2023
        >>> list(iter_date_ranges_by_end_date(46, datetime(2023, 2, 15), batch_size='biweekly'))
        [(15, '02/15/2023'), (16, '01/31/2023'), (15, '01/15/2023')]

    """
    if isinstance(end_date_inclusive, str):
        end_date_inclusive = datetime.strptime(end_date_inclusive, date_str_format)

    if isinstance(batch_size, str):
        if batch_size in 'monthly':
            yield from iter_monthly_num_days_backward(
                end_date_inclusive=end_date_inclusive,
                date_str_format=date_str_format,
                max_num_days=num_days,
                partial_first_month=True,
                partial_last_month=True,
                return_end_date=True,
                yield_start_date=yield_start_date,
                format_output_date_as_string=format_output_date_as_string
            )
        elif batch_size == 'biweekly':
            yield from iter_monthly_num_days_backward(
                end_date_inclusive=end_date_inclusive,
                date_str_format=date_str_format,
                max_num_days=num_days,
                partial_first_month=True,
                partial_last_month=True,
                return_end_date=True,
                yield_start_date=yield_start_date,
                format_output_date_as_string=format_output_date_as_string,
                biweekly=True
            )
        else:
            raise ValueError(f"'{batch_size}' is not a valid batch size option")
    else:
        if isinstance(batch_size, int) and batch_size <= 0:
            raise ValueError("'batch_size' must be a positive integer")
        batch_size = iter_(batch_size, infinitely_yield_atom=True)
        while num_days > 0:
            _batch_size: int = next(batch_size)
            _batch_size = min(num_days, _batch_size)

            yield _get_date_range(
                num_days_backward=_batch_size,
                end_date_inclusive=end_date_inclusive,
                yield_start_date=yield_start_date,
                format_output_date_as_string=format_output_date_as_string,
                date_str_format=date_str_format
            )
            num_days -= _batch_size
            end_date_inclusive -= timedelta(days=_batch_size)
