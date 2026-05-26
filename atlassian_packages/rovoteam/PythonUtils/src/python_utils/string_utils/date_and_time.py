from time import strptime, strftime
from datetime import timedelta, datetime
from typing import Union


def reformat_datetime_str(datetime_string, src_format='%m/%d/%Y', dst_format='%y%m%d') -> str:
    """
    Reformats the datetime string from the source format to the destination format.

    Args:
        datetime_string: the datetime string.
        src_format: the current format of the datetime string.
        dst_format: the target format of the datetime string.

    Returns: the reformated datetime string.

    Examples:
        >>> reformat_datetime_str('09/17/2022')
        '220917'
    """
    return strftime(
        dst_format,
        strptime(datetime_string, src_format),
    )


def minus_n_days(date: Union[datetime, str], n: int, date_str_format: str = '%m/%d/%Y') \
        -> Union[datetime, str]:
    """
    Subtract 'n' days from the provided date.

    If the input date is a string, the output will be a string in the same format. If the input date is a
    datetime object, the output will be a datetime object.

    Args:
        date: The input date which could be a string or a datetime object.
        n: The number of days to be subtracted from the date.
        date_str_format: The format of the date string if the date is provided as a string.
            Defaults to '%m/%d/%Y' (American date format - Month/Day/Year).

    Returns:
        The date obtained by subtracting 'n' days from the input date.
            The output type depends on the input date's type.

    Examples:
        >>> minus_n_days('12/31/2023', 1)
        '12/30/2023'
        >>> minus_n_days(datetime(2023, 12, 31), 1)
        datetime.datetime(2023, 12, 30, 0, 0)
        >>> minus_n_days('12/31/2023', 1, '%m/%d/%Y')
        '12/30/2023'
    """
    if isinstance(date, str):
        date = datetime.strptime(date, date_str_format)
        new_date = date - timedelta(days=n)
        new_date_string = new_date.strftime(date_str_format)
        return new_date_string
    else:
        return date - timedelta(days=n)


def add_n_days(date: Union[datetime, str], n: int, date_str_format: str = '%m/%d/%Y') \
        -> Union[datetime, str]:
    """
    Add 'n' days to the provided date.

    If the input date is a string, the output will be a string in the same format. If the input date is a
    datetime object, the output will be a datetime object.

    Args:
        date: The input date which could be a string or a datetime object.
        n: The number of days to be added to the date.
        date_str_format: The format of the date string if the date is provided as a string.
            Defaults to '%m/%d/%Y' (American date format - Month/Day/Year).

    Returns:
        The date obtained by adding 'n' days to the input date.
        The output type depends on the input date's type.

    Examples:
        >>> add_n_days('06/01/2023', 10)
        '06/11/2023'
        >>> add_n_days(datetime(2023, 6, 1), 10)
        datetime.datetime(2023, 6, 11, 0, 0)
        >>> add_n_days('01/06/2023', 10, '%d/%m/%Y')
        '11/06/2023'
    """
    if isinstance(date, str):
        date = datetime.strptime(date, date_str_format)
        new_date = date + timedelta(days=n)
        new_date_string = new_date.strftime(date_str_format)
        return new_date_string
    else:
        return date + timedelta(days=n)
