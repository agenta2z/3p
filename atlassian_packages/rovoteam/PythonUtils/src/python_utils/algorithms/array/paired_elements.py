from collections.abc import Sequence, Callable


def make_valid_by_minimum_removal(seq: Sequence, left, right, concat: Callable = None):
    """
    Removes the minimum number of invalid `left` and `right` elements from the input
    sequence to make it valid. A sequence is considered valid if every `left` element
    has a corresponding `right` element and vice versa, maintaining proper order.

    Optionally, a `concat` function can be provided to process the filtered elements.

    Args:
        seq (Sequence[T]): The input sequence containing elements to be validated.
        left (T): The element representing the opening symbol (e.g., '(').
        right (T): The element representing the closing symbol (e.g., ')').
        concat (Callable[[Sequence[T]], Any], optional): A function to concatenate
            the filtered elements into a desired format. If `None`, the function returns
            a string if `seq` is a string, or a list otherwise. Defaults to `None`.

    Returns:
        Union[List[T], str, Any]:
            - If `concat` is provided, returns the result of `concat` applied to the filtered sequence.
            - If `concat` is `None` and `seq` is a string, returns the concatenated string.
            - If `concat` is `None` and `seq` is not a string, returns a list of the filtered elements.

    Examples:
        >>> # Example 1: Removing invalid parentheses from a string without providing `concat`
        >>> s = "()())()"
        >>> make_valid_by_minimum_removal(s, '(', ')')
        '()()()'

        >>> # Example 2: Removing invalid parentheses from a string with `concat` as ''.join
        >>> s = "(a)())()"
        >>> make_valid_by_minimum_removal(s, '(', ')', concat=lambda x: ''.join(x))
        '(a)()()'

        >>> # Example 3: Removing invalid parentheses from a list of characters
        >>> seq = [')', '(', 'a', ')', '(', ')']
        >>> make_valid_by_minimum_removal(seq, '(', ')')
        ['(', 'a', ')', '(', ')']

        >>> # Example 4: Removing invalid angle brackets from a string
        >>> s = "<a><<b></>"
        >>> make_valid_by_minimum_removal(s, '<', '>')
        '<a><b></>'

        >>> # Example 5: Empty sequence
        >>> s = ""
        >>> make_valid_by_minimum_removal(s, '(', ')')
        ''

        >>> # Example 6: Sequence with no invalid parentheses
        >>> s = "(())()"
        >>> make_valid_by_minimum_removal(s, '(', ')')
        '(())()'

        >>> # Example 7: Sequence with all invalid parentheses
        >>> s = "(((("
        >>> make_valid_by_minimum_removal(s, '(', ')')
        ''

    Notes:
        - The function assumes that `left` and `right` are distinct elements.
        - It processes the sequence in a single pass to identify invalid elements.
        - The order of elements is preserved in the returned sequence.
        - The `concat` function allows flexibility in how the filtered elements are returned.
    """
    stack = []
    invalid_indexes = []

    for i, x in enumerate(seq):
        if x == left:
            stack.append(i)
        elif x == right:
            if stack:
                stack.pop()
            else:
                invalid_indexes.append(i)

    invalid_indexes = set(invalid_indexes + stack)
    output = (x  for i, x in enumerate(seq) if i not in invalid_indexes)
    if concat is not None:
        return concat(output)
    else:
        if isinstance(seq, str):
            return ''.join(output)
        else:
            return list(output)


def make_valid_by_minimum_add(seq: Sequence, left, right, concat: Callable = None):
    """
    Adds the minimal number of `left` and `right` elements to the input sequence
    to make it valid. A sequence is considered valid if every `left` element
    has a corresponding `right` element and vice versa, maintaining proper order.

    Optionally, a `concat` function can be provided to process the resulting elements.

    Args:
        seq (Sequence[T]): The input sequence containing elements to be validated.
        left (T): The element representing the opening symbol (e.g., '(').
        right (T): The element representing the closing symbol (e.g., ')').
        concat (Callable[[Sequence[T]], Any], optional): A function to process
            the final list of elements into a desired format. If `None`, the function
            returns a string if `seq` is a string, or a list otherwise. Defaults to `None`.

    Returns:
        Union[List[T], str, Any]:
            - If `concat` is provided, returns the result of `concat` applied to the final sequence.
            - If `concat` is `None` and `seq` is a string, returns the concatenated string.
            - If `concat` is `None` and `seq` is not a string, returns a list of the final elements.

    Examples:
        >>> # Example 1: Adding necessary parentheses to make a string valid
        >>> s = "())"
        >>> make_valid_by_minimum_add(s, '(', ')')
        '()()'

        >>> # Example 2: Sequence with already valid parentheses
        >>> s = "(())()"
        >>> make_valid_by_minimum_add(s, '(', ')')
        '(())()'

        >>> # Example 3: A list of characters
        >>> seq = [')', '(', 'a', ')', '(']
        >>> make_valid_by_minimum_add(seq, '(', ')')
        ['(', ')', '(', 'a', ')', '(', ')']

        >>> # Example 4: Using a concat function
        >>> s = "((("
        >>> make_valid_by_minimum_add(s, '(', ')', concat=lambda x: ''.join(x))
        '((()))'

    Notes:
        - The function assumes that `left` and `right` are distinct elements.
        - It processes the sequence in a single pass to determine how many extra
          `left` or `right` elements need to be added.
        - The order of original elements is preserved in the final sequence.
        - The `concat` function allows flexibility in how the final sequence is returned.
    """
    open_count = 0
    result = []

    # First pass: ensure that for every right symbol, there's a matching left symbol.
    for x in seq:
        if x == left:
            open_count += 1
            result.append(x)
        elif x == right:
            # If there's no matching left, add one before appending the right.
            if open_count == 0:
                result.append(left)
            else:
                open_count -= 1
            result.append(x)
        else:
            result.append(x)

    # If there are unmatched left symbols, add the corresponding right symbols.
    result.extend(right for _ in range(open_count))

    # Handle the output formatting via `concat` or default to str/list.
    if concat is not None:
        return concat(result)
    else:
        if isinstance(seq, str):
            return ''.join(result)
        else:
            return result