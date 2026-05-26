from typing import List, Union, Any, Tuple
from os import environ


def resolve_environ(varname: str) -> str:
    """Resolves an environment variable to its value, or returns the variable name if not set.

    This function checks if the variable name starts with a '$' symbol. If so, it removes the '$'
    and attempts to retrieve the value of the corresponding environment variable. If the
    environment variable does not exist, it returns the provided variable name as-is.

    Args:
        varname (str): The name of the environment variable to resolve, potentially prefixed with '$'.

    Returns:
        str: The value of the environment variable if it exists; otherwise, the `varname` itself.

    Examples:
        Basic usage with an existing variable:
        >>> environ['TEST_VAR'] = 'test_value'
        >>> resolve_environ('$TEST_VAR')
        'test_value'

        Without the `$` prefix for an existing variable:
        >>> resolve_environ('TEST_VAR')
        'test_value'

        When the environment variable does not exist:
        >>> resolve_environ('$NON_EXISTENT_VAR')
        '$NON_EXISTENT_VAR'
        >>> resolve_environ('NON_EXISTENT_VAR')
        'NON_EXISTENT_VAR'

        Using a literal `$` that isn’t an environment variable:
        >>> resolve_environ('$LITERAL_DOLLAR')
        '$LITERAL_DOLLAR'

        Clean-up:
        >>> del environ['TEST_VAR']
    """
    if not varname:
        return  ''
    _varname = varname[1:] if varname[0] == '$' else varname
    return environ.get(_varname, varname)


def split_int(_int, num_parts: int, partial: int, return_range: bool = False) -> Union[
    int, Tuple[int, Tuple[float, float]]]:
    """
    Splits an integer into approximately equal parts and returns the specified partial value. Optionally returns the range of the split.

    Parameters:
    _int (int): The integer to be split.
    num_parts (int): Number of parts to split the integer into.
    partial (int): The index of the partial value to extract.
    return_range (bool): If True, returns the range of the partial split as a tuple of floats.

    Returns:
    Union[int, Tuple[int, Tuple[float, float]]]: The specified partial value, optionally with the range of the split.

    Example:
    >>> split_int(9, 3, 2)
    3
    >>> split_int(9, 3, 2, return_range=True)
    (3, (0.6666666666666666, 1.0))
    >>> split_int(20, 4, 3)
    5
    >>> split_int(20, 4, 3, return_range=True)
    (5, (0.75, 1.0))
    >>> split_int(10, 2, 0)
    5
    >>> split_int(10, 2, 0, return_range=True)
    (5, (0.0, 0.5))
    """
    _split = _int // num_parts

    if partial == num_parts - 1:
        _last_split = _int - _split * partial
        if return_range:
            _ratio = _split * partial / _int
            _range = (_ratio, 1.0)
            return _last_split, _range
        return _last_split
    else:
        if return_range:
            _ratio = _split / _int
            _range = (_ratio * partial, _ratio * (partial + 1))
            return _split, _range
        return _split


def split_float(_float: float, num_parts: int, partial: int, return_range: bool = False) -> Union[
    float, Tuple[float, Tuple[float, float]]]:
    """
    Splits a float into approximately equal parts and returns the specified partial value. Optionally returns the range of the split.

    Parameters:
    _float (float): The float to be split.
    num_parts (int): Number of parts to split the float into.
    partial (int): The index of the partial value to extract.
    return_range (bool): If True, returns the range of the partial split as a tuple of floats.

    Returns:
    Union[float, Tuple[float, Tuple[float, float]]]: The specified partial value, optionally with the range of the split.

    Example:
    >>> split_float(9.0, 3, 2)
    3.0
    >>> split_float(9.0, 3, 2, return_range=True)
    (3.0, (0.6666666666666666, 1.0))
    >>> split_float(20.0, 4, 3)
    5.0
    >>> split_float(20.0, 4, 3, return_range=True)
    (5.0, (0.75, 1.0))
    >>> split_float(10.0, 2, 0)
    5.0
    >>> split_float(10.0, 2, 0, return_range=True)
    (5.0, (0.0, 0.5))
    """
    _split = _float / num_parts

    if partial == num_parts - 1:
        _last_split = _float - _split * partial
        if return_range:
            _ratio = _split * partial / _float
            _range = (_ratio, 1.0)
            return _last_split, _range
        return _last_split
    else:
        if return_range:
            _ratio = _split / _float
            _range = (_ratio * partial, _ratio * (partial + 1))
            return _split, _range
        return _split


def divide_(x, y, default: Any = 0):
    """
    Divides x by y, returning a default value if y is zero.

    Args:
        x (float or int): The numerator.
        y (float or int): The denominator.
        default (Any): The value to return if y is zero. Defaults to 0.

    Returns:
        float or Any: The result of the division, or the default value if y is zero.

    Examples:
        >>> divide_(10, 2)
        5.0

        >>> divide_(10, 0)
        0

        >>> divide_(10, 0, default='undefined')
        'undefined'

        >>> divide_(10, 5)
        2.0
    """
    if y == 0:
        return default

    return x / y


def distribute_by_weights(
        total: Union[int, float],
        weights: List[Union[int, float]],
        incremental: bool = False
) -> List[float]:
    """
    Distributes a total number based on given weights, with an option for incremental distribution.

    Args:
        total (int or float): The total number to be distributed.
        weights (list of int or float): The weights for distribution.
        incremental (bool): If True, return incremental sums; otherwise, return distributed values.

    Returns:
        list of float: The distributed values based on the weights, either as individual values or incremental sums.

    Examples:
        >>> distribute_by_weights(10, [1, 2, 3])
        [1.6666666666666665, 3.333333333333333, 5.0]

        >>> distribute_by_weights(10, [1, 2, 3], incremental=True)
        [1.6666666666666665, 5.0, 10.0]
    """
    # Calculate the sum of the weights
    total_weight = sum(weights)

    # Calculate the proportion of each weight
    proportions = [weight / total_weight for weight in weights]

    # Distribute the total based on the proportions
    distributed_values = [total * proportion for proportion in proportions]

    if incremental:
        # Calculate incremental sums
        incremental_values = []
        cumulative_sum = 0
        for value in distributed_values[:-1]:
            cumulative_sum += value
            incremental_values.append(cumulative_sum)
        incremental_values.append(float(total))
        return incremental_values

    return distributed_values


def is_close(x, y, tolerance=0.0001, is_tolerance_ratio: bool = True):
    """
    Checks if two numbers are considered close given the tolerance.
    The `tolerance` can be a ratio or abosoute value,
        set `is_tolerance_ratio` to change the behavior.

    Examples:
        >>> assert is_close(10001, 10000)
        >>> assert not is_close(10001, 10000, is_tolerance_ratio=False)
        >>> assert is_close(0.321457, 0.321466)
        >>> assert not is_close(0.321457, 0.321466, tolerance=0.000001)

    """
    if is_tolerance_ratio:
        return abs(x / y - 1) < tolerance
    else:
        return abs(x - y) < tolerance


def is_negligible(x, y, tolerance=0.001):
    return abs(x / y) < tolerance


def binary_min(x) -> int:
    """
    Returns a binary value indicating whether all elements in the input are greater than or equal to 1.

    This function checks if all elements in the input `x` are greater than or equal to 1.
    If all elements meet this condition, the function returns 1.
    Otherwise, it returns 0.

    Args:
        x (iterable): A list or other iterable of numerical values.

    Returns:
        int: 1 if all elements in `x` are greater than or equal to 1, otherwise 0.

    Examples:
        >>> binary_min([0, 1, 2])
        0

        >>> binary_min([1, 2, 3])
        1

        >>> binary_min([2, 3, 4])
        1

        >>> binary_min([0, 0, 0])
        0

        >>> binary_min([1])
        1

        >>> binary_min([0.5, 1.5, 2.5])
        0

        >>> binary_min([1.0, 2.0, 3.0])
        1
    """
    return int(all(_x >= 1 for _x in x))


def binary_max(x) -> int:
    """
    Returns the maximum value from the input and checks if it is binary (0 or 1).

    This function computes the maximum value of the input `x` using the `max` function.
    If the maximum value is greater than 1, a `ValueError` is raised.
    If the maximum value is less than 1, the function returns 0.
    Otherwise, it returns the maximum value.

    Args:
        x (iterable): A list or other iterable of numerical values.

    Returns:
        int: The maximum value if it is 0 or 1. Returns 0 if the maximum is less than 1.

    Raises:
        ValueError: If the maximum value is greater than 1.

    Examples:
        >>> binary_max([0, 1, 2])
        1

        >>> binary_max([2, 3, 4])
        1

        >>> binary_max([0, 0, 0])
        0

        >>> binary_max([1])
        1

        >>> binary_max([0.5, 1.5, 2.5])
        1

        >>> binary_max([0.5, 0.6, 0.7])
        0

        >>> binary_max([0.0, 1.0])
        1
    """
    return int(any(_x >= 1 for _x in x))
