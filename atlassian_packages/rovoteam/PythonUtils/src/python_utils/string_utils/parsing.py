import ast
from enum import Enum
from functools import partial
from typing import List, Tuple, Callable, Optional, Mapping, Union

from python_utils.common_utils.iter_helper import zip_longest__
from python_utils.string_utils.misc import get_domain_from_name


def parse_as_bins(s: str, boundary_type: Callable = int, sep=',') -> List[Tuple[int, int]]:
    """
    Parses a string a sequence of bins.
    Args:
        s: the string that represents bins of boundaries of the specified `boundary_type`;
            for example, '1,2,3,4' represents bins (1,2), (2,3) and (3,4) with integer boundaries;
            if `s` is empty, then an empty list will be returned.
        boundary_type: the type of bin boundaries, typically int, float, etc, but can be any
            callable to convert strings to boundaries.
        sep: the separator between bin boundaries in the string.

    Returns: a sequence of bins with integer boundaries represented by 2-tuples.

    Examples:
        >>> parse_as_bins('1,2,3,4')
        [(1, 2), (2, 3), (3, 4)]
        >>> parse_as_bins('1,2,3,4', boundary_type=float)
        [(1.0, 2.0), (2.0, 3.0), (3.0, 4.0)]

    """
    if s:
        bins = s.split(sep)
        return [
            (boundary_type(bins[i]), boundary_type(bins[i + 1]))
            for i in range(len(bins) - 1)
        ]
    else:
        return []


class PreDefinedArgConverters(int, Enum):
    CommaSeparatedIntegers = 0
    CommaSeparatedNumbers = 1
    CommaSeparatedIntegerBins = 2
    CommaSeparatedNumberBins = 3


PREDEFINED_ARG_CONVERTERS = {
    PreDefinedArgConverters.CommaSeparatedIntegers: lambda x: list(map(int, x.split(','))),
    PreDefinedArgConverters.CommaSeparatedNumbers: lambda x: list(map(float, x.split(','))),
    PreDefinedArgConverters.CommaSeparatedIntegerBins: parse_as_bins,
    PreDefinedArgConverters.CommaSeparatedNumberBins: partial(parse_as_bins, boundary_type=float)
}


def parse_with_predefined_convert(s: str, converter: PreDefinedArgConverters):
    """
    Converts the string `s` with a pre-defined converter.

    The converter must be one of the :class:`PreDefinedArgConverters` enum and must be
    registered in map `PREDEFINED_ARG_CONVERTERS`.

    Examples:
        >>> parse_with_predefined_convert('1,2,3,4', PreDefinedArgConverters.CommaSeparatedIntegers)
        [1, 2, 3, 4]
        >>> parse_with_predefined_convert('1,2,3,4', PreDefinedArgConverters.CommaSeparatedNumbers)
        [1.0, 2.0, 3.0, 4.0]
        >>> parse_with_predefined_convert('1,2,3,4', PreDefinedArgConverters.CommaSeparatedIntegerBins)
        [(1, 2), (2, 3), (3, 4)]
        >>> parse_with_predefined_convert('1,2,3,4', PreDefinedArgConverters.CommaSeparatedNumberBins)
        [(1.0, 2.0), (2.0, 3.0), (3.0, 4.0)]

    """
    if converter not in PREDEFINED_ARG_CONVERTERS:
        raise ValueError(f'{converter} is not a pre-defined converter')
    return PREDEFINED_ARG_CONVERTERS[converter](s)


# region python function call parsing
def split_function_calls(
        input_string: str,
        separator: str = ';',
        quotes: Tuple = ('"', "'"),
        left_brackets: Tuple = ('(', '[', '{'),
        right_brackets: Tuple = (')', ']', '}'),
        escape: str = '\\'
) -> List[str]:
    """
    Splits a string containing multiple function calls separated by a specified character,
    considering nested structures and quoted strings.

    Args:
        input_string: The string to split.
        separator: The character used to separate function calls. Default is ';'.
        quotes: A tuple of characters used for quoting strings. Default is ('"', "'").
        left_brackets: A tuple of characters used as left brackets. Default is ('(', '[', '{').
        right_brackets: A tuple of characters used as right brackets. Default is (')', ']', '}').
        escape: The escape character used to ignore separators within quotes. Default is '\\'.

    Returns:
        list: A list of individual function call strings.

    Examples:
        >>> split_function_calls('a.b.c(c=["abc", ["def;gh", 13]]); a.b(c=["15", ["12"]])')
        ['a.b.c(c=["abc", ["def;gh", 13]])', 'a.b(c=["15", ["12"]])']

        >>> split_function_calls('func1(arg1=5); func2(arg2="text; more text")')
        ['func1(arg1=5)', 'func2(arg2="text; more text")']

        >>> split_function_calls('func("a;b;c"); another_func(1, 2, 3)')
        ['func("a;b;c")', 'another_func(1, 2, 3)']

        >>> split_function_calls('func1(arg1=5) | func2(arg2="text \\"|\\", more text")', separator='|')
        ['func1(arg1=5)', 'func2(arg2="text "|", more text")']

        >>> split_function_calls('call1(); call2({a: "value; still value"}); call3([])')
        ['call1()', 'call2({a: "value; still value"})', 'call3([])']

        >>> split_function_calls('nested("a; b", {key: [1; 2]}); another_call("test; case")')
        ['nested("a; b", {key: [1; 2]})', 'another_call("test; case")']

        >>> split_function_calls('escape_char("some \\"quoted\\" text; and more"); simple_call()')
        ['escape_char("some "quoted" text; and more")', 'simple_call()']

        >>> split_function_calls('mismatch_brackets(func1(arg=[1, 2, 3); func2())')
        ['mismatch_brackets(func1(arg=[1, 2, 3); func2())']

        >>> split_function_calls('empty_brackets(call()); no_args_call(); mixed_brackets(func({key: "value"})[0])')
        ['empty_brackets(call())', 'no_args_call()', 'mixed_brackets(func({key: "value"})[0])']
    """

    function_calls = []
    bracket_stack = []
    current_call = []
    in_quote = False
    quote_char = ''

    for char in input_string:
        if char in quotes:
            if not in_quote:
                in_quote = True
                quote_char = char
            elif char == quote_char and current_call[-1] != escape:
                in_quote = False

        if not in_quote:
            if char in left_brackets:
                bracket_stack.append(char)
            elif char in right_brackets:
                if len(bracket_stack) == 0:
                    raise ValueError("Unmatched closing bracket")
                bracket_stack.pop()

        if char == separator and not bracket_stack and not in_quote:
            function_calls.append(''.join(current_call).strip())
            current_call = []
        else:
            current_call.append(char)

    if current_call:
        function_calls.append(''.join(current_call).strip())

    return function_calls


def _parse_function_call(invocation_string: str, return_dict: bool = False, return_domain: bool = False, verbose=False):
    try:
        # Parse the string into an AST node
        node = ast.parse(invocation_string, mode='eval')

        if isinstance(node, ast.Expression) and isinstance(node.body, ast.Call):
            call_node = node.body

            # Function to recursively extract function name
            def extract_function_name(node):
                if isinstance(node, ast.Attribute):
                    return extract_function_name(node.value) + '.' + node.attr
                elif isinstance(node, ast.Name):
                    return node.id

            # Extract function name
            function_name = extract_function_name(call_node.func)

            # Extract arguments
            args_dict = {}
            for arg in call_node.args:
                # This handles unnamed arguments
                args_dict[f'arg{len(args_dict) + 1}'] = ast.literal_eval(arg)

            for keyword in call_node.keywords:
                # This handles named arguments
                args_dict[keyword.arg] = ast.literal_eval(keyword.value)
        else:
            function_name, args_dict = None, None
    except Exception as e:
        function_name, args_dict = None, None
        if verbose:
            print(f"Error parsing `{invocation_string}` with exception `{e}`")

    if return_dict:
        parsed_funtion_call = {
            'name': function_name,
            'args': args_dict
        }
        if return_domain:
            parsed_funtion_call['domain'] = get_domain_from_name(function_name, domain_separator='.')
        return parsed_funtion_call
    else:
        if return_domain:
            return function_name, args_dict, get_domain_from_name(function_name, domain_separator='.')
        else:
            return function_name, args_dict


def parse_function_call(invocation_string: str, separator: Optional[str] = None, return_dict: bool = False, return_domain: bool = False, verbose: bool = False):
    """
    Parses one or multiple function call strings. When a separator is provided, it splits
    the string based on the separator and parses each function call individually. The function
    extracts the function name (including namespaced functions) and arguments as a dictionary,
    using ast.literal_eval to parse the argument values.

    Args:
        invocation_string: A string representing one or more function calls.
        separator: A character used to separate multiple function calls.
            Defaults to None, meaning the string is treated as a single function call.

    Returns:
        If no separator is provided:
            tuple: A tuple containing the function name and a dictionary of arguments.
        If a separator is provided:
            list: A list of tuples, each containing the function name and a dictionary of arguments.

    Examples:
        # Single function call
        >>> parse_function_call('a.b(c=["15", ["12"]])')
        ('a.b', {'c': ['15', ['12']]})
        >>> parse_function_call('a.b(c=["15", ["12"]])', separator=';')
        [('a.b', {'c': ['15', ['12']]})]
        >>> parse_function_call('a.b(c=["15", ["12"]]);', separator=';')
        [('a.b', {'c': ['15', ['12']]})]

        # Single function call with complex arguments
        >>> parse_function_call('a.b.c(c=["abc", ["def;gh", 13]])')
        ('a.b.c', {'c': ['abc', ['def;gh', 13]]})
        >>> parse_function_call('a.b.c(c=["abc", ["def;gh", 13]])', separator='|')
        [('a.b.c', {'c': ['abc', ['def;gh', 13]]})]

        # Single function call with named arguments
        >>> parse_function_call("calculate_area(length=10, width=5)")
        ('calculate_area', {'length': 10, 'width': 5})

        # Multiple function calls separated by a semicolon
        >>> parse_function_call('func1(arg1="val1"); func2(arg2="val2")', separator=';')
        [('func1', {'arg1': 'val1'}), ('func2', {'arg2': 'val2'})]

        # Multiple function calls with complex and nested arguments
        >>> parse_function_call("funcA(x=1, y=[2, 3]); funcB(a='abc', b={'key': 'value'})", separator=';')
        [('funcA', {'x': 1, 'y': [2, 3]}), ('funcB', {'a': 'abc', 'b': {'key': 'value'}})]

        # Returns diectionary
        >>> parse_function_call('AlarmsApi.createAlarm(time="nine am", date="tomorrow", targetDeviceId="lights")', return_dict=True, return_domain=True)
        {'name': 'AlarmsApi.createAlarm', 'args': {'time': 'nine am', 'date': 'tomorrow', 'targetDeviceId': 'lights'}, 'domain': 'AlarmsApi'}
    """
    if separator:
        return [
            _parse_function_call(x, return_dict=return_dict, return_domain=return_domain, verbose=verbose)
            for x in split_function_calls(invocation_string, separator)
        ]
    else:
        return _parse_function_call(invocation_string, return_dict=return_dict, return_domain=return_domain, verbose=verbose)


def get_function_names(
        invocation_string: str,
        separator: Optional[str] = None,
        simple_name_extraction_on_parsing_failure: bool = False,
        quotes: Tuple = ('"', "'"),
        left_brackets: Tuple = ('(', '[', '{'),
        right_brackets: Tuple = (')', ']', '}'),
        escape: str = '\\'
) -> Union[str, List[str]]:
    """
    Extracts the function names from a string containing one or multiple function calls.

    Args:
        invocation_string: The string containing function call(s).
        separator: The character used to separate multiple function calls. If None, assumes a single function call.
        simple_name_extraction_on_parsing_failure: If True, uses a simple split method to extract function names on parsing failure.
        quotes: A tuple of characters used for quoting strings. Default is ('"', "'").
        left_brackets: A tuple of characters used as left brackets. Default is ('(', '[', '{').
        right_brackets: A tuple of characters used as right brackets. Default is (')', ']', '}').
        escape: The escape character used to ignore separators within quotes. Default is '\\'.

    Returns:
        A string if there's only one function call or a list of strings if there are multiple function calls.

    Examples:
        >>> get_function_names('func1()')
        'func1'

        >>> get_function_names('func1(arg1=5)')
        'func1'

        >>> get_function_names('func1(arg1=5); func2(arg2="text")')
        'func1'

        >>> get_function_names('func1(arg1=5); func2(arg2="text")', separator=';')
        ['func1', 'func2']

        >>> get_function_names('func1(arg1=5) | func2(arg2="text")', separator='|')
        ['func1', 'func2']

        >>> get_function_names('singleCall()')
        'singleCall'

        >>> get_function_names('call1(); call2({a: "va;lue"}); call3([";;;"])', separator=';')
        ['call1', 'call2', 'call3']

        >>> get_function_names('complexCall(arg=[1, {2:";"}, 3:{4:"a;b"}]); anotherCall(arg="te;st")', separator=';')
        ['complexCall', 'anotherCall']

        >>> get_function_names('invalidSyntax call1(arg1=5); call2(arg2="text")', separator=';', simple_name_extraction_on_parsing_failure=True)
        ['invalidSyntax call1', 'call2']
    """
    primary_left_bracket = left_brackets[0] if left_brackets else '('
    if separator:
        try:
            return [
                x.split('(', maxsplit=1)[0].strip()
                for x in split_function_calls(
                    invocation_string,
                    separator=separator,
                    quotes=quotes,
                    left_brackets=left_brackets,
                    right_brackets=right_brackets,
                    escape=escape
                )
            ]
        except:
            if simple_name_extraction_on_parsing_failure:
                return [
                    invocation_string_split.split(primary_left_bracket, maxsplit=1)[0]
                    for invocation_string_split
                    in invocation_string.split(separator)
                ]
    else:
        return invocation_string.split(primary_left_bracket, maxsplit=1)[0].strip()


def _get_unit_parsed_func_call_name_and_args(unit_func_call):
    if isinstance(unit_func_call, Mapping):
        if 'domain' in unit_func_call:
            return unit_func_call['name'], unit_func_call['args'], unit_func_call['domain']
        else:
            return unit_func_call['name'], unit_func_call['args'], None
    else:
        if len(unit_func_call) == 2:
            return unit_func_call[0], unit_func_call[1], None
        else:
            return unit_func_call


def compare_function_calls(func_call: List[Union[Tuple, Mapping]], ref_func_call: List[Union[Tuple, Mapping]]):
    """

    Compares two sequences of function calls to determine their match in terms of invocation count,
    domain, function names, and arguments. It provides detailed accuracy metrics for comparison.

    The comparison includes overall invocation counts, domain accuracy, name accuracy, argument accuracy,
    and individual invocation accuracies. It examines the first and last function calls separately for
    more granular insight into the sequence alignment.

    Args:
        func_call: A sequence of function call information to be compared. Each entry is either a mapping
                   containing 'name', 'args', and optionally 'domain', or a tuple (name, args).
        ref_func_call: A reference sequence of function call information to compare against. It should
                       have the same structure as func_call.

    Returns:
        A tuple containing:
        - Overall comparison of invocation counts (total in func_call, total in ref_func_call, and if they match).
        - Accuracy metrics for the first function call (domain, name, args, and overall invocation accuracy).
        - Accuracy metrics for the last function call (domain, name, args, and overall invocation accuracy).
        - Aggregate accuracy metrics (domain, name, args, and invocation accuracy across all function calls).

    Examples:
        >>> func_call = [{'name': 'a.b', 'args': [1, 2], 'domain': 'a'}, {'name': 'c.d', 'args': [3], 'domain': 'c'}]
        >>> ref_func_call = [{'name': 'a.b', 'args': [1, 2], 'domain': 'a'}, {'name': 'c.d', 'args': [4], 'domain': 'c'}]
        >>> compare_function_calls(func_call, ref_func_call)
        ((1.0, 1.0, 0.5, 0.5), (2, 2, True), (True, True, True, True), (True, True, False, False))

        >>> func_call = [{'name': 'x.y', 'args': [5]}, {'name': 'z.w', 'args': [6, 7]}]
        >>> ref_func_call = [{'name': 'x.y', 'args': [5]}]
        >>> compare_function_calls(func_call, ref_func_call)
        ((1.0, 1.0, 1.0, 1.0), (2, 1, False), (True, True, True, True), (True, True, True, True))

        >>> func_call = None
        >>> ref_func_call = {'name': 'x.y', 'args': [5]}
        >>> compare_function_calls(func_call, ref_func_call)
        ((0.0, 0.0, 0.0, 0.0), (0, 1, False), (False, False, False, False), (False, False, False, False))

        >>> func_call = [{'name': 'x.y', 'args': [5]}, {'name': 'z.w', 'args': [6, 7]}]
        >>> ref_func_call = [{'name': None, 'args': None}]
        >>> compare_function_calls(func_call, ref_func_call)
        ((None, None, None, None), (1, 0, False), (None, None, None, None), (None, None, None, None))

    Note:
        - This function assumes that both func_call and ref_func_call have been preprocessed and are
          valid inputs.
        - It does not account for different orderings of function calls within the provided sequences.

    """
    num_invocations = num_ref_invocations = 0
    all_api_domain_accuracy = all_api_name_accuracy = all_api_args_accuracy = all_api_invocation_accuracy = 0
    first_api_domain_accuracy = first_api_name_accuracy = first_api_args_accuracy = first_api_invocation_accuracy = None
    last_api_domain_accuracy = last_api_name_accuracy = last_api_args_accuracy = last_api_invocation_accuracy = None

    for unit_call, unit_ref_func_call in zip_longest__(
            func_call,
            ref_func_call,
            atom_types=(Tuple, Mapping),
            fill_none_by_previous_values=False
    ):
        if unit_ref_func_call is None:
            if unit_call is not None:
                num_invocations += 1
            continue
        else:
            ref_name, ref_args, ref_domain = _get_unit_parsed_func_call_name_and_args(unit_ref_func_call)
            if ref_name is not None:
                num_ref_invocations += 1
                if unit_call is None:
                    last_api_domain_accuracy = last_api_name_accuracy = last_api_args_accuracy = last_api_invocation_accuracy = False
                else:
                    num_invocations += 1
                    name, args, domain = _get_unit_parsed_func_call_name_and_args(unit_call)

                    last_api_domain_accuracy = (ref_domain == domain)
                    last_api_name_accuracy = (last_api_domain_accuracy and (name == ref_name))
                    last_api_args_accuracy = (args == ref_args)
                    last_api_invocation_accuracy = (last_api_name_accuracy and last_api_args_accuracy)

                if first_api_domain_accuracy is None:
                    first_api_domain_accuracy = last_api_domain_accuracy
                if first_api_name_accuracy is None:
                    first_api_name_accuracy = last_api_name_accuracy
                if first_api_args_accuracy is None:
                    first_api_args_accuracy = last_api_args_accuracy
                if first_api_invocation_accuracy is None:
                    first_api_invocation_accuracy = last_api_invocation_accuracy

                all_api_domain_accuracy += int(last_api_domain_accuracy)
                all_api_name_accuracy += int(last_api_name_accuracy)
                all_api_args_accuracy += int(last_api_args_accuracy)
                all_api_invocation_accuracy += int(last_api_invocation_accuracy)
    return (
        (
            (all_api_domain_accuracy / num_ref_invocations, all_api_name_accuracy / num_ref_invocations, all_api_args_accuracy / num_ref_invocations, all_api_invocation_accuracy / num_ref_invocations)
            if num_ref_invocations != 0 else (None, None, None, None)
        ),
        (num_invocations, num_ref_invocations, num_invocations == num_ref_invocations),
        (first_api_domain_accuracy, first_api_name_accuracy, first_api_args_accuracy, first_api_invocation_accuracy),
        (last_api_domain_accuracy, last_api_name_accuracy, last_api_args_accuracy, last_api_invocation_accuracy)
    )
# endregion
