import ast
import json
import os
import sys
from argparse import ArgumentParser, Namespace
from functools import partial
from os import path
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple, Union

from python_utils.common_utils import all_of_same_type
from python_utils.common_utils.environment_helper import is_ipython, path_import
from python_utils.common_utils.slot_tuple import NamedTuple
from python_utils.common_utils.typing_helper import (
    bool_,
    element_type,
    map_iterable_elements,
    nonstr_iterable,
)
from python_utils.common_utils.arg_utils.arg_naming import (
    solve_arg_full_and_short_name,
    solve_parameter_info,
)
from python_utils.console_utils import hprint_message
from python_utils.string_utils.parsing import (
    parse_with_predefined_convert,
    PreDefinedArgConverters,
)

DEFAULT_VERBOSE = False


class ArgInfo(NamedTuple):
    """
    Used for argument definition in `get_parsed_args`.
    """

    __slots__ = ("full_name", "short_name", "default_value", "description", "converter")

    def __init__(
        self,
        full_name: str = "",
        short_name: str = "",
        default_value=None,
        description: str = "",
        converter=None,
    ):
        self.full_name = full_name
        self.short_name = short_name
        self.default_value = default_value
        self.description = description
        self.converter = converter


ARG_INFO = Union[str, Tuple, ArgInfo]


def dict_to_namespace(d, recursive=True):
    """
    Converts a dictionary to a Namespace object.

    Args:
        d: the dictionary to convert.
        recursive: True to convert recursively,
            i.e. any Mapping inside the Mapping will also be converted into a Namespace;
            otherwise only convert the top-level key/values in the dictionary to a Namespace.

    Returns: a Namespace object converted from the input dictionary.

    """
    if recursive:
        return Namespace(
            **{
                k: (
                    dict_to_namespace(v, recursive=True)
                    if isinstance(v, Mapping)
                    else v
                )
                for k, v in d.items()
            }
        )
    else:
        return Namespace(**d)


def has_argument(arg_parser: ArgumentParser, arg_name: str) -> bool:
    """
    Check if an ArgumentParser already has an argument with the specified name.

    Args:
        arg_parser (ArgumentParser): The argument parser to search in.
        arg_name (str): The name of the argument to search for.

    Returns:
        bool: True if the argument exists, False otherwise.

    >>> parser = ArgumentParser()
    >>> assert parser.add_argument('--arg1', help='First argument', type=int, default=0)
    >>> has_argument(parser, 'arg1')
    True
    >>> has_argument(parser, 'arg2')
    False
    """
    return any(action.dest == arg_name for action in arg_parser._actions)


def update_argument_default(
    arg_parser: ArgumentParser,
    arg_name: str,
    arg_default_value: Any,
    set_required_to_false_if_default_value_is_not_none: bool = True,
    verbose: bool = DEFAULT_VERBOSE,
) -> bool:
    """
    Update the default value of an existing argument in the ArgumentParser.
    If the argument with the specified name does not exist, do nothing.

    Args:
        arg_parser: The argument parser containing the argument.
        arg_name: The name of the argument to update.
        arg_default_value: The new default value for the argument.
        verbose: If True, print debug messages. Defaults to the value of DEFAULT_VERBOSE.

    Returns:
        bool: True if the argument default value was updated, False otherwise.


    >>> parser = ArgumentParser()
    >>> _ = parser.add_argument('--arg1', help='First argument', type=int, default=0)
    >>> has_argument(parser, 'arg1')
    True
    >>> parser.get_default('arg1')
    0
    >>> update_argument_default(parser, 'arg1', 10)
    True
    >>> parser.get_default('arg1')
    10
    >>> update_argument_default(parser, 'arg2', "new value")
    False
    >>> has_argument(parser, 'arg2')
    False
    """
    for action in arg_parser._actions:
        if action.dest == arg_name:
            needs_update_default_value = action.default != arg_default_value
            if verbose:
                hprint_message(
                    "action.default",
                    action.default,
                    "action.required ",
                    action.required,
                    "arg_default_value",
                    arg_default_value,
                    "needs_update_default_value",
                    needs_update_default_value,
                    title=f"default value update for {arg_name}",
                )
            if needs_update_default_value:
                action.default = arg_default_value
                if (
                    set_required_to_false_if_default_value_is_not_none
                    and arg_default_value is not None
                ):
                    action.required = False
            return True
    return False


def _solve_preset(preset_path):
    def _inner_solve_preset_path(preset_path):
        if not path.isfile(preset_path):
            _preset_path = f"{preset_path}.json"
            if path.isfile(_preset_path):
                return _preset_path, False
            else:
                _preset_path = f"{preset_path}.py"
                if path.isfile(_preset_path):
                    return _preset_path, True
                else:
                    return None, False
        else:
            return preset_path, preset_path.endswith(".py")

    _preset_path, is_python = _inner_solve_preset_path(preset_path)
    if _preset_path is not None:
        preset_path = _preset_path
        preset_keys = None
    else:
        preset_keys = path.basename(preset_path).split(":")
        preset_path = path.dirname(preset_path)
        preset_path, is_python = _inner_solve_preset_path(preset_path)
    return preset_path, preset_keys, is_python


def _proc_arg_val(arg_val, c, force_parse_boolstr):
    if isinstance(arg_val, str):
        if c is not None:
            attr_pairs = []
            for attr_name in dir(c):
                if attr_name[0] != "_":
                    attr_pairs.append((attr_name, str(getattr(c, attr_name))))
            attr_pairs.sort(key=lambda x: (len(x), x), reverse=True)
            for attr_name, attr_val in attr_pairs:
                arg_val = arg_val.replace(f"${attr_name}", attr_val)
        for attr_name, attr_val in sorted(
            os.environ.items(), key=lambda x: (len(x), x), reverse=True
        ):
            arg_val = arg_val.replace(f"${attr_name}", attr_val)
        if arg_val == "none" or arg_val == "null":
            arg_val = None
        elif force_parse_boolstr:
            if arg_val.lower() == "false":
                arg_val = False
            elif arg_val.lower() == "true":
                arg_val = True
    return arg_val


def sanitize_arg_name(arg_name: str):
    return arg_name.replace("-", "_")


def get_seen_actions(arg_parser: ArgumentParser, argv: List[str] = None) -> List[str]:
    """
    Returns a list of argument names that have been specified in the command line.

    Args:
        arg_parser: An ArgumentParser instance.
        argv: A list of command-line arguments. If not provided, sys.argv is used.

    Returns:
        A list of specified argument names (destinations) in the command line.

    Create a parser and define arguments:

    Example:
        >>> from argparse import ArgumentParser
        >>> parser = ArgumentParser()
        >>> assert parser.add_argument('-a', '--arg1', help='First argument', type=int, default=0)
        >>> assert parser.add_argument('-bb', '--arg2', help='Second argument', type=str, default="")
        >>> assert parser.add_argument('-cc', '--arg3', help='Third argument', type=str, default="")
        >>> example_argv = ['script_name', '--arg1', '5', '--arg3', 'hello']
        >>> get_seen_actions(parser, example_argv)
        ['arg1', 'arg3']
        >>> example_argv = ['script_name', '-a', '5', '-bb', 'hello']
        >>> get_seen_actions(parser, example_argv)
        ['arg1', 'arg2']
    """
    argv = argv or sys.argv
    specified_options = set(arg for arg in argv[1:] if arg.startswith("-"))
    seen_actions = [
        action.dest
        for action in arg_parser._actions
        if any(
            option_string in specified_options
            for option_string in action.option_strings
        )
    ]
    return seen_actions


def get_unseen_actions(arg_parser, argv: List[str] = None):
    """
    Get a list of argument names (destinations) that are not specified in the given argv list.

    Args:
        arg_parser (ArgumentParser): An argparse.ArgumentParser object containing the arguments.
        argv (List[str], optional): A list of command line arguments. Defaults to sys.argv.

    Returns:
        List[str]: A list of the names of the arguments that were not specified in the command line.

    Example:
        >>> from argparse import ArgumentParser
        >>> parser = ArgumentParser()
        >>> assert parser.add_argument('-a', '--arg1', help='First argument', type=int, default=0)
        >>> assert parser.add_argument('-b', '--arg2', help='Second argument', type=str, default="")
        >>> assert parser.add_argument('-c', '--arg3', help='Third argument', type=str, default="")
        >>> argv = ['script_name.py', '--arg1', '42', '-c', 'value']
        >>> get_unseen_actions(parser, argv)
        ['arg2']
    """
    from argparse import _HelpAction

    argv = argv or sys.argv
    specified_options = set(arg for arg in argv[1:] if arg.startswith("-"))
    unseen_actions = [
        action.dest
        for action in arg_parser._actions
        if not any(
            option_string in specified_options
            for option_string in action.option_strings
        )
        and not isinstance(action, _HelpAction)
    ]
    return unseen_actions


def _get_parsed_args_legacy(
    *arg_info_objs,
    preset_root: str = None,
    preset: [Union[Dict[str, Any], str]] = None,
    short_full_name_sep="/",
    return_seen_args=False,
    default_value_prefix: str = "default_",
    exposed_args: List[str] = None,
    required_args=None,
    non_empty_args=None,
    constants=None,
    force_parse_boolstr=True,
    verbose: bool = True,
    argv: List[str] = None,
    arg_parser: ArgumentParser = None,
    replace_double_underscore_with_dash: bool = True,
    **kwargs,
):
    """
    Parses terminal argument input. Suitable for both simple and complicated argument parsing. Also supports list and dictionary parsing.
    The argument priority is terminal input > preset > default values.

    Args:
        arg_info_objs: argument definition objects; define the argument name, default value, description, and value conversion. It can be
            1) just the argument name;
                you can specify both the full name and the short name in a single name string
                with the `short_full_name_sep` as the separator;
                for example, by default `short_full_name_sep` is '/',
                    then you can specify an argument name as 'para_1/p1' or 'learning_rate/lr';
            2) a 2-tuple for the argument name (supports short name specification)
                and the default value;
            3) a 3-tuple for the argument name (supports short name specification),
                the default value, and a description;
            4) a 3-tuple for the argument name (supports short name specification),
                the default value, and a converter;
            5) a 4-tuple for the argument name (supports short name specification),
                the default value, the description and the converter;
            6) a 5-tuple for the full argument name, the short argument name, the default value,
                the description and the converter;
            7) a :class:`ArgInfo` object, which is itself a :class:`namedtuple` of size 5.

            The argument type is inferred from the default value.
                1) If the default value is list, tuple, or set,
                    the inferred argument type is the same container,
                    and it will enforce the element type by the type
                    of the first element in the default value;
                    for example, if the default value is `[1, "2", "3", "4"]`,
                        the inferred type is a list of integers,
                        regardless of the string values in the list;
                        if then the terminal input is `["1", "2", "3", "4"]`,
                        it will still be recognized as a list of integers.
                2) Otherwise, the inferred type is just the the type of the default value.
                3) to change the above typing inference behavior,
                    provide a `converter` for the argument in the `arg_info_objs`.
        preset_root: the path to the directory that stores presets of arguments.
        preset: the path/name of the preset relative to `preset_root`;
            1) a preset is a json/python file with predefined argument values;
                if `preset_root` is specified,
                then `preset` should be relative to the `preset_root`;
            2) the values from the `preset` will be used
                as the default values of corresponding arguments,
                and they are the highest-priority default values,
                overriding those specified by `default_xxx` arguments;
            3) the values in `preset` will be added to the returned argumetns
                even if they are not specified by any `arg_info_objs` or any `default_xxx` argument.
        short_full_name_sep: optional; the separator used to separate fullname and shortname
            in the `arg_info_objs`; the default is '/'.
        return_seen_args: optional; True to return the names of the arguments
            actually specified in the terminal..
        default_value_prefix: any named argument starting with this prefix will be treated
            as the default value for an argument of the same name without the prefix;
            the default is 'default_';
            for example, `default_learning_rate` indicates
                there is an argument named `learning_rate`,
                and the value of `default_learning_rate` is the default value for that argument;
                the argument need not be already specified in the `arg_info_objs`;
            for example, with 'default_' as the `default_value_prefix`,
                this function automatically adds the 'xxx'
                of any such parameter `default_xxx` found in `kwargs` to the recognized arguments.
        replace_double_underscore_with_dash: if True, replace dual underscores '__' in argument names with dashes '-' for command-line arguments.
        kwargs: specify the default values as named arguments.

    Returns:
        just the parsed arguments if `return_seen_args` is False;
        otherwise, a tuple, the first being the parsed args,
         and the second being the names of specified args.

    Examples:
        Simple argument parsing setup.
        ------------------------------
        By simply specifying the default values,
        it tells the function there should be three terminal arguments `para1`, `para2` and `para3`,
        and it hints the function that `para1` is of type `int`,
        `para2` is of type `str`, and `para3` is of type `list`.
        >>> get_parsed_args(default_para1=1, default_para2='value', default_para3=[1, 2, 3, 4])
        Namespace(para1=1, para2='value', para3=[1, 2, 3, 4])

        We may specify the argument in the command line such as the following,
            1) set arguments `--para1 2 --para2 3 --para3 '[4,5,6,7]'`,
                and the parsed argument will be Namespace(para1=1, para2='3', para3=[4, 5, 6, 7]);
            2) set arguments `--para1 2 --para2 3 --para3 5`
                and the parsed argument will be Namespace(para1=1, para2='3', para3=[5]);
            3) the short names for these arguments are automatically generated as 'p', 'p1', 'p2',
                so we can specify `-p 2 -p1 3 -p2 5`.


        Simple argument parsing setup without default values (not recommended).
        -----------------------------------------------------------------------
        If no default values are needed, we could just specify the names;
        NOTE without default values, there is no way to infer the type of each argument,
            unless it can be recognized as list, a tuple, a set or a dictionary;
            all other arguments will be of string type.
        >>> get_parsed_args('para1', 'para2', 'para3')
        Namespace(para1='', para2='', para3='')

        We may specify the argument in the command line such as the following,
            1) try `--para1 2 --para2 3 --para3 '[4,5,6,7]'`, or `--p 2 --p1 3 --p2 '[4,5,6,7]'`
                and we will have Namespace(para1='2', para2='3', para3=[4,5,6,7]).
            2) try `--para1 2 --para2 3 --para3 5` and `-p 2 --p1 3 --p2 5`,
                and we will have Namespace(para1='2', para2='3', para3='5').


        Use 2-tuples to setup argument parsing.
        ---------------------------------------
        We can provide argument info tuples, where every tuple is a 2-tuple,
            1) the first being the name in the format of `fullname/shortname`,
                or just the `fullname`, and
            2) the second being the default value.

        If the 'shortname' is not specified, the default is to use the first letter
            of the 'parts' of the full name as the short name.
        If the duplicate short name is found, an incremental number
            will be appended to the end to solve the name conflict.
        In the following, the last short name is not specified, so we automatically generate
            its short name by connecting the first letter of 'parts' of the full name, i.e. 'pil'.
        >>> get_parsed_args(
        ...    ('para1_is_int/p', 1),
        ...    ('para2_is_str/p', 'value'),
        ...    ('para3_is_list', [1, 2, 3, 4])
        ... )
        Namespace(para1_is_int=1, para2_is_str='value', para3_is_list=[1, 2, 3, 4])

        We may specify the argument in the command line such as the following,
            1) set arguments by short names `-p 2 -p1 3 -pil '[4,5,6,7]'`.
            2) set arguments by full names `--para1_is_int 2 --para2_is_str 3 -para3_is_list '[4,5,6,7]'`.


        Use more explicit ArgInfo namedtuple to setup argument parsing.
        ---------------------------------------------------------------
        >>> get_parsed_args(ArgInfo(full_name='para1_is_int', short_name='p', default_value=1),
        ...      ArgInfo(full_name='para2_is_str', short_name='p', default_value='value'),
        ...      ArgInfo(full_name='para3_is_list', default_value=[1, 2, 3, 4])
        ... )
        Namespace(para1_is_int=1, para2_is_str='value', para3_is_list=[1, 2, 3, 4])

        We can again try `-p 2 -p1 3 -pil '[4,5,6,7]'`
            or `--para1_is_int 2 --para2_is_str 3 --para3_is_list '[4,5,6,7]'`.


        Use converters.
        ---------------
        >>> get_parsed_args(ArgInfo(full_name='para1_is_int', short_name='p', default_value=1),
        ...     ArgInfo(full_name='para2_is_str', short_name='p', default_value='value', converter=lambda x: '_' + x.upper()),
        ...     ArgInfo(full_name='para3_is_list', default_value=[1, 2, 3, 4], converter=lambda x: x ** 2),
        ...     ArgInfo(full_name='para4_is_dict', default_value={'a': 1, 'b': 2}, converter=lambda k, v: (k, k + str(v))))
        Namespace(para1_is_int=1, para2_is_str='_VALUE', para3_is_list=[1, 2, 3, 4], para4_is_dict={'a': 'a1', 'b': 'b2'})

        We can try `-p 2 -p1 3 -pil '[4,5,6,7]' -pid "{'a':2, 'b':3}"`
            or `--para1_is_int 2 --para2_is_str 3 --para3_is_list '[4,5,6,7]' --para3_is_dict "{'a':2, 'b':3}"`.

    """

    # region pre-process the preset
    # The actual python script arguments generally starts with index 1;
    # In case of doc test with PyCharm, the actual argument starts with index 2.
    argv = argv or sys.argv
    _argv = argv[2:] if "pycharm/docrunner.py" in argv[0] else argv[1:]

    if _argv and _argv[0] == "preset":
        preset = ast.literal_eval(_argv[1])
        _argv = _argv[2:]

    if isinstance(preset, str):
        _preset = {}
        for preset_path in preset.split(","):
            _preset_path, preset_keys, is_python = _solve_preset(preset_path)
            if _preset_path is None:
                preset_path, preset_keys, is_python = _solve_preset(
                    path.join(preset_root, preset_path)
                )
            else:
                preset_path = _preset_path

            if preset_path is not None:
                if is_python:
                    preset_obj = {
                        k: (dict_to_namespace(v) if isinstance(v, Mapping) else v)
                        for k, v in path_import(
                            path.abspath(preset_path)
                        ).config.items()
                    }
                else:
                    preset_obj = json.load(open(preset_path))
                if preset_keys is None:
                    _preset.update(preset_obj)
                else:
                    for preset_key in preset_keys:
                        _preset.update(preset_obj[preset_key])
        preset = _preset
    elif isinstance(preset, (tuple, list)):
        return [
            get_parsed_args(
                arg_info_objs=arg_info_objs,
                preset_root=preset_root,
                preset=_preset,
                short_full_name_sep=short_full_name_sep,
                return_seen_args=return_seen_args,
                default_value_prefix=default_value_prefix,
                **kwargs,
            )
            for _preset in preset
        ]

    # endregion

    if arg_parser is None:
        arg_parser = ArgumentParser()
    if verbose:
        hprint_message(
            "arg_parser._actions",
            arg_parser._actions,
            "num_existing_args",
            len(arg_parser._actions),
            title=f"using arg_parser of type {type(arg_parser)}",
        )
    arg_full_name_deduplication = set()
    arg_short_name_deduplication = set()
    sanitized_arg_full_name_to_original_arg_full_name_map = {}
    converters = {}
    _is_ipython = is_ipython()

    def _default_converter_multiple_values(x, ctype, vtype, converter):
        if converter is None:
            if nonstr_iterable(x):
                return ctype(map_iterable_elements(x, vtype))
            else:
                return ctype([vtype(x)])
        else:
            if nonstr_iterable(x):
                return ctype(map_iterable_elements(x, vtype))
            else:
                return ctype([converter(x)])

    if exposed_args:
        hidden_args = []
    if not _is_ipython and required_args:
        arg_parser_required_group = arg_parser.add_argument_group("required arguments")

    def _add_arg():
        nonlocal converter
        if (
            exposed_args and arg_full_name not in exposed_args
        ):  # we hide non-exposed args
            hidden_args.append((arg_full_name, default_value))
        else:
            _description = description if description else ""
            disable_default_value = False
            if not _is_ipython and (
                required_args is not None and arg_full_name in required_args
            ):
                disable_default_value = True
            elif _description:
                _description += f"; the default value is " + (
                    f"'{default_value}'"
                    if isinstance(default_value, str)
                    else f"{default_value}"
                )

            if converter is not None:
                # if the converter is specified, then we leave the argument string parsing to the converter

                if isinstance(converter, PreDefinedArgConverters):
                    converter = partial(
                        parse_with_predefined_convert, converter=converter
                    )
                if not callable(converter):
                    raise ValueError(f"converter must be a callable; got '{converter}'")

                if not update_argument_default(
                    arg_parser=arg_parser,
                    arg_name=arg_full_name,
                    arg_default_value=default_value,
                ):
                    arg_full_name_for_cli = (
                        arg_full_name.replace("__", "-")
                        if replace_double_underscore_with_dash
                        else arg_full_name
                    )
                    if disable_default_value:
                        arg_parser_required_group.add_argument(
                            "-" + arg_short_name,
                            "--" + arg_full_name_for_cli,
                            help=_description,
                            type=str,
                            required=True,
                        )
                    else:
                        arg_parser.add_argument(
                            "-" + arg_short_name,
                            "--" + arg_full_name_for_cli,
                            help=_description,
                            default=default_value,
                            type=str,
                        )

                if isinstance(default_value, (tuple, list, set)):
                    converters[arg_full_name] = partial(
                        _default_converter_multiple_values,
                        ctype=type(default_value),
                        vtype=element_type(default_value),
                        converter=converter,
                    )
                else:
                    converters[arg_full_name] = converter
            else:
                # otherwise, we run the default argument parsing

                if not update_argument_default(
                    arg_parser=arg_parser,
                    arg_name=arg_full_name,
                    arg_default_value=default_value,
                ):
                    arg_value_type = type(default_value)
                    if arg_value_type is bool and not default_value:
                        # ! Boolean flag is used if the default value is `False`
                        arg_full_name_for_cli = (
                            arg_full_name.replace("__", "-")
                            if replace_double_underscore_with_dash
                            else arg_full_name
                        )
                        arg_parser.add_argument(
                            "-" + arg_short_name,
                            "--" + arg_full_name_for_cli,
                            help=_description,
                            required=False,
                            action="store_true",
                        )
                    else:
                        if arg_value_type in (int, float):
                            converters[arg_full_name] = arg_value_type
                        elif arg_value_type is bool:
                            converters[arg_full_name] = bool_
                        elif arg_value_type in (tuple, list, set):
                            converters[arg_full_name] = partial(
                                _default_converter_multiple_values,
                                ctype=type(default_value),
                                vtype=element_type(default_value),
                                converter=None,
                            )
                        arg_full_name_for_cli = (
                            arg_full_name.replace("__", "-")
                            if replace_double_underscore_with_dash
                            else arg_full_name
                        )
                        if disable_default_value:
                            arg_parser_required_group.add_argument(
                                "-" + arg_short_name,
                                "--" + arg_full_name_for_cli,
                                help=_description,
                                required=True,
                            )
                        else:
                            arg_parser.add_argument(
                                "-" + arg_short_name,
                                "--" + arg_full_name_for_cli,
                                help=_description,
                                default=default_value,
                            )
            arg_full_name_deduplication.add(arg_full_name)

    # region process argument definition tuples
    converter = None
    for arg_info_obj in arg_info_objs:
        arg_full_name, arg_short_name, default_value, converter, description = (
            solve_parameter_info(
                parameter_info=arg_info_obj,
                arg_short_name_deduplication=arg_short_name_deduplication,
                short_full_name_sep=short_full_name_sep,
            )
        )

        sanitized_arg_name = sanitize_arg_name(arg_full_name)
        if sanitized_arg_name != arg_full_name:
            if (
                sanitized_arg_name
                not in sanitized_arg_full_name_to_original_arg_full_name_map
            ):
                sanitized_arg_full_name_to_original_arg_full_name_map[
                    sanitized_arg_name
                ] = arg_full_name
            else:
                raise ValueError(
                    f"argument name '{arg_full_name}' conflicts with "
                    f"an existing argument name "
                    f"'{sanitized_arg_full_name_to_original_arg_full_name_map[sanitized_arg_name]}'"
                )

        # default value overrides 1 - from the extra named arguments `kwargs`
        default_value_override = kwargs.get(
            arg_full_name, kwargs.pop(default_value_prefix + arg_full_name, None)
        )
        if default_value_override is not None:
            default_value = default_value_override

        # default value overrides 2 - from a preset dictionary; this has the highest priority
        if preset is not None:
            default_value_override = preset.get(
                arg_full_name, preset.get(default_value_prefix + arg_full_name, None)
            )
            if default_value_override is not None:
                default_value = default_value_override
        _add_arg()

    # endregion

    # region adds ad-hoc defined arguments
    description = ""
    if preset is not None:
        for arg_full_name, default_value in preset.items():
            if arg_full_name.startswith(default_value_prefix):
                arg_full_name = arg_full_name[len(default_value_prefix) :]
            arg_full_name, arg_short_name = solve_arg_full_and_short_name(
                arg_name_str=arg_full_name,
                arg_short_name_deduplication=arg_short_name_deduplication,
                short_full_name_sep=short_full_name_sep,
            )
            if arg_full_name:
                if default_value is None:
                    default_value = kwargs.get(
                        arg_full_name,
                        kwargs.pop(default_value_prefix + arg_full_name, None),
                    )
                _add_arg()

    for arg_full_name, default_value in kwargs.items():
        if arg_full_name.startswith(default_value_prefix):
            arg_full_name = arg_full_name[len(default_value_prefix) :]
            arg_full_name, arg_short_name = solve_arg_full_and_short_name(
                arg_name_str=arg_full_name,
                arg_short_name_deduplication=arg_short_name_deduplication,
                short_full_name_sep=short_full_name_sep,
            )
            if arg_full_name:
                _add_arg()
    # endregion

    # region argument value conversion
    args = arg_parser.parse_args(_argv)
    if exposed_args and hidden_args:
        for arg_full_name, arg_val in hidden_args:
            setattr(
                args,
                arg_full_name,
                _proc_arg_val(arg_val, constants, force_parse_boolstr),
            )

    for arg_full_name, arg_val in vars(args).items():
        ori_arg_name = sanitized_arg_full_name_to_original_arg_full_name_map.get(
            arg_full_name, arg_full_name
        )
        if isinstance(arg_val, str):
            _arg_val = arg_val.strip()
            if _arg_val:
                arg_val = _arg_val
            if (
                arg_val and arg_val[0] in ("'", '"') and arg_val[-1] in ("'", '"')
            ):  # 'de-quote' the argument string
                arg_val = arg_val[1:-1]
            if (
                len(arg_val) >= 2 and arg_val[0] == "(" and arg_val[-1] == ")"
            ):  # a tuple
                arg_val = ast.literal_eval(arg_val)
                converter: Optional[Callable] = converters.get(ori_arg_name, None)
                if converter is not None:
                    arg_val = converter(arg_val)
            elif len(arg_val) >= 2 and (
                arg_val[0] == "[" and arg_val[-1] == "]"
            ):  # a list
                arg_val = ast.literal_eval(arg_val)
                converter: Optional[Callable] = converters.get(ori_arg_name, None)
                if converter is not None:
                    arg_val = converter(arg_val)
            elif len(arg_val) >= 2 and (
                arg_val[0] == "{" and arg_val[-1] == "}"
            ):  # a dictionary
                arg_val = ast.literal_eval(arg_val)
                converter: Optional[Callable] = converters.get(ori_arg_name, None)
                if converter is not None:
                    arg_val = dict(converter(k, v) for k, v in arg_val.items())
            elif ori_arg_name in converters:
                arg_val = converters[ori_arg_name](arg_val)
        elif ori_arg_name in converters:
            converter: Optional[Callable] = converters.get(ori_arg_name, None)
            if isinstance(arg_val, (list, set, tuple)):
                arg_val = converter(arg_val)
            elif isinstance(arg_val, dict):
                arg_val = dict(converter(k, v) for k, v in arg_val.items())
            else:
                arg_val = converter(arg_val)

        setattr(
            args, arg_full_name, _proc_arg_val(arg_val, constants, force_parse_boolstr)
        )

    # endregion

    # if preset_path:
    #     setattr(args, 'preset', preset_path)

    if non_empty_args:
        for arg_full_name in non_empty_args:
            arg_val = getattr(args, arg_full_name)
            if not isinstance(arg_val, bool) and not bool(arg_val):
                raise ValueError(f"the argument `{arg_full_name}` is empty")

    if verbose:
        import __main__

        if hasattr(__main__, "__file__"):
            hprint_message(path.basename(__main__.__file__), args.__dict__)
        else:
            hprint_message(str(__main__), args.__dict__)

    if return_seen_args:
        return args, get_seen_actions(arg_parser)
    else:
        return args


def _get_parsed_args(
    *arg_info_objs,
    preset_root: str = None,
    preset: Optional[Union[Dict[str, Any], str]] = None,
    short_full_name_sep="/",
    return_seen_args=False,
    default_value_prefix: str = "default_",
    exposed_args: List[str] = None,
    required_args=None,
    non_empty_args=None,
    constants=None,
    force_parse_boolstr=True,
    verbose: bool = True,
    argv: List[str] = None,
    arg_parser: ArgumentParser = None,
    replace_double_underscore_with_dash: bool = True,
    interactive: bool = False,
    **kwargs,
):
    """
    New modular implementation using ArgumentParserBuilder.

    This implementation decomposes the parsing logic into separate components
    for better maintainability and extensibility.
    """
    from .parsing.parser_builder import ArgumentParserBuilder

    builder = ArgumentParserBuilder(
        preset_root=preset_root,
        preset=preset,
        short_full_name_sep=short_full_name_sep,
        return_seen_args=return_seen_args,
        default_value_prefix=default_value_prefix,
        exposed_args=exposed_args,
        required_args=required_args,
        non_empty_args=non_empty_args,
        constants=constants,
        force_parse_boolstr=force_parse_boolstr,
        verbose=verbose,
        argv=argv,
        arg_parser=arg_parser,
        replace_double_underscore_with_dash=replace_double_underscore_with_dash,
        interactive=interactive,
    )

    return builder.build(*arg_info_objs, **kwargs)


def get_parsed_args(
    *arg_info_objs,
    preset_root: str = None,
    preset: Optional[Union[Dict[str, Any], str]] = None,
    short_full_name_sep="/",
    return_seen_args=False,
    default_value_prefix: str = "default_",
    exposed_args: List[str] = None,
    required_args=None,
    non_empty_args=None,
    constants=None,
    force_parse_boolstr=True,
    verbose: bool = True,
    argv: List[str] = None,
    arg_parser: ArgumentParser = None,
    replace_double_underscore_with_dash: bool = True,
    interactive: bool = False,
    legacy: bool = False,
    **kwargs,
):
    """
    Parses terminal argument input. Suitable for both simple and complicated argument parsing.
    Also supports list and dictionary parsing.
    The argument priority is terminal input > preset > default values.

    This is the master function that delegates to either the legacy implementation
    or the new modular implementation based on the `legacy` parameter.

    Args:
        arg_info_objs: argument definition objects; define the argument name, default value,
            description, and value conversion. Supports 7 formats:
            1) just the argument name
            2) a 2-tuple (name, default_value)
            3) a 3-tuple (name, default_value, description)
            4) a 3-tuple (name, default_value, converter)
            5) a 4-tuple (name, default_value, description, converter)
            6) a 5-tuple (full_name, short_name, default_value, description, converter)
            7) an ArgInfo namedtuple
        preset_root: the path to the directory that stores presets of arguments.
        preset: the path/name of the preset relative to `preset_root`.
        short_full_name_sep: separator for fullname/shortname in arg names (default: '/').
        return_seen_args: True to return names of arguments specified in terminal.
        default_value_prefix: prefix for default value kwargs (default: 'default_').
        exposed_args: if provided, only these args are shown; others are hidden.
        required_args: list of argument names that are required.
        non_empty_args: list of argument names that must not be empty.
        constants: object for variable substitution ($varname).
        force_parse_boolstr: parse "true"/"false" strings as booleans.
        verbose: print debug output.
        argv: custom argv list.
        arg_parser: use existing ArgumentParser instance.
        replace_double_underscore_with_dash: replace '__' with '-' in CLI names.
        interactive: enable interactive mode for collecting argument values.
        legacy: If True, use original implementation. Default False (new modular impl).
        kwargs: default values as named arguments (default_xxx pattern).

    Returns:
        Namespace with parsed arguments, or tuple (Namespace, seen_args) if return_seen_args=True.

    Examples:
        >>> get_parsed_args(default_para1=1, default_para2='value', default_para3=[1, 2, 3, 4])
        Namespace(para1=1, para2='value', para3=[1, 2, 3, 4])
    """
    if legacy:
        return _get_parsed_args_legacy(
            *arg_info_objs,
            preset_root=preset_root,
            preset=preset,
            short_full_name_sep=short_full_name_sep,
            return_seen_args=return_seen_args,
            default_value_prefix=default_value_prefix,
            exposed_args=exposed_args,
            required_args=required_args,
            non_empty_args=non_empty_args,
            constants=constants,
            force_parse_boolstr=force_parse_boolstr,
            verbose=verbose,
            argv=argv,
            arg_parser=arg_parser,
            replace_double_underscore_with_dash=replace_double_underscore_with_dash,
            **kwargs,
        )
    else:
        return _get_parsed_args(
            *arg_info_objs,
            preset_root=preset_root,
            preset=preset,
            short_full_name_sep=short_full_name_sep,
            return_seen_args=return_seen_args,
            default_value_prefix=default_value_prefix,
            exposed_args=exposed_args,
            required_args=required_args,
            non_empty_args=non_empty_args,
            constants=constants,
            force_parse_boolstr=force_parse_boolstr,
            verbose=verbose,
            argv=argv,
            arg_parser=arg_parser,
            replace_double_underscore_with_dash=replace_double_underscore_with_dash,
            interactive=interactive,
            **kwargs,
        )


def get_args(preset=None, argv=None, **kwargs) -> Namespace:
    """
    Parses command-line arguments based on provided default values and optional presets.
    Supports complex data types and overrides defaults with preset values.

    Args:
        preset: Path to a JSON file or a dictionary containing preset values.
            Preset values override default values specified in the function call.
        argv: List of argument strings typically passed from the command line.
            If None, the function will take the arguments from sys.argv.
        **kwargs: Dynamic argument definitions where each argument name should be prefixed with 'default_',
            e.g., default_integer=42. The value defines the default and infers the data type.

    Returns:
        Namespace containing the parsed arguments.

    Examples:
        >>> test_args = '--integer 100 --list 10 20 30'.split()
        >>> get_args(
        ...     preset={'integer': 99, 'string': 'preset_hello'},
        ...     default_integer=42,
        ...     default_string='hello',
        ...     default_list=[1, 2, 3],
        ...     default_tuple=(4, 5, 5.5),
        ...     default_dictionary={'key': 'value'},
        ...     argv=test_args  # simulate command-line args
        ... )
        Namespace(integer=100, string='preset_hello', list=[10, 20, 30], tuple=(4, 5, 5.5), dictionary={'key': 'value'})
    """
    parser = ArgumentParser()

    # Extract defaults from kwargs using 'default_' prefix
    defaults = {
        key[8:]: value for key, value in kwargs.items() if key.startswith("default_")
    }

    # Load preset if provided
    presets = {}
    if preset:
        if isinstance(preset, str) and os.path.exists(preset):
            with open(preset, "r") as file:
                presets = json.load(file)
        elif isinstance(preset, dict):
            presets = preset

    # Update defaults with presets
    combined_defaults = {**defaults, **presets}

    # Add arguments based on their types and homogeneity
    for arg, value in combined_defaults.items():
        if isinstance(value, list) and all_of_same_type(value):
            parser.add_argument(
                f"--{arg}",
                nargs="*",
                type=type(value[0]) if value else str,
                default=value,
            )
        elif isinstance(value, tuple) and all_of_same_type(value):
            parser.add_argument(
                f"--{arg}",
                nargs="*",
                type=type(value[0]) if value else str,
                default=list(value),
                action=lambda x: tuple(x),
            )
        else:
            parser.add_argument(
                f"--{arg}",
                type=json.loads
                if isinstance(value, str)
                and (value.startswith("[") or value.startswith("{"))
                else type(value),
                default=value,
            )

    # Use actual command-line arguments if argv is None
    if argv is None:
        argv = sys.argv[1:]

    # Parse arguments
    args = parser.parse_args(argv)

    # Convert JSON strings back to complex types if necessary
    for arg, value in vars(args).items():
        if isinstance(value, str) and (value.startswith("{") or value.startswith("[")):
            setattr(args, arg, json.loads(value))

    return args


