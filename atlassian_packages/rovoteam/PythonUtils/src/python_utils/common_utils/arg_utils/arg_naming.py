import enum
import re
from pydoc import locate
from typing import Iterator, Iterable, Union, Callable, Tuple, List, Mapping

from python_utils.common_utils.map_helper import get__, get_keys
from python_utils.common_utils.typing_helper import make_set_, is_str
from python_utils.string_utils.misc import get_human_int_str
from python_utils.string_utils.prefix_suffix import solve_name_conflict
from python_utils.nlp_utils.punctuations import remove_punctuation_except_for_hyphen
from python_utils.string_utils.split import birsplit


def solve_arg_full_and_short_name(
        arg_name_str: str,
        arg_short_name_deduplication: set,
        short_full_name_sep: str = '/',
        default_arg_full_name_short_name_map: Mapping[str, str] = None
):
    arg_full_name, arg_short_name = birsplit(arg_name_str, short_full_name_sep)
    if (
            (not arg_short_name) and
            default_arg_full_name_short_name_map and
            (arg_full_name in default_arg_full_name_short_name_map)
    ):
        arg_short_name = default_arg_full_name_short_name_map[arg_full_name]

    if arg_short_name:
        # `arg_short_name` is specified;
        # the we only need to solve the name conflict if any
        arg_short_name = solve_name_conflict(
            name=arg_short_name,
            existing_names=arg_short_name_deduplication
        )
    else:
        # automatically generates the short argument name;
        # `get_short_name` includes the name conflict solution
        arg_short_name = get_short_name(
            full_name=arg_full_name,
            current_short_names=arg_short_name_deduplication
        )
    return arg_full_name, arg_short_name


def get_short_name(
        full_name: str,
        name_parts_sep: str = r'_|\-',
        current_short_names: Iterable[str] = None,
        conflict_solving_suffix_sep='',
        conflict_solving_name_suffix_gen: Union[Iterator, str, Callable[[int], str]] = None
):
    """
    Gets short argument name for a full argument name, using the first letters of the name parts.
    This function also try to solve short name conflict if `current_short_names` is provided.

    Args:
        full_name: the full argument name.
        name_parts_sep: the separator to separate name parts;
            for example, in 'arg_name', '_' is the separator,
            and 'arg' and 'name' are the name parts.
        current_short_names: a collection current short names already in use.
        conflict_solving_suffix_sep:
            the separator to insert between the name and the conflict-solving suffix.
        conflict_solving_name_suffix_gen:
            optionally provides a generator of conflict-solving name suffixes;
            see `solve_name_conflict`.

    Returns: a short argument name for the full name;
        if `full_name` is empty, then an empty string is returned.

    Examples:
        >>> get_short_name('arg_name')
        'an'
        >>> get_short_name('arg-name')
        'an'
        >>> get_short_name('arg-name', current_short_names=['an'])
        'an1'
        >>> get_short_name(
        ...     'arg-name',
        ...     current_short_names=['an', 'an-1'],
        ...     conflict_solving_suffix_sep='-'
        ... )
        'an-2'
    """
    current_short_names = make_set_(current_short_names)
    if full_name:
        try:
            short_name = ''.join(part[0] for part in re.split(name_parts_sep, full_name))
        except:
            return ''
        return solve_name_conflict(
            name=short_name,
            existing_names=current_short_names,
            suffix_sep=conflict_solving_suffix_sep,
            suffix_gen=conflict_solving_name_suffix_gen
        )
    else:
        return ''


def solve_parameter_info(
        parameter_info,
        arg_short_name_deduplication: set,
        short_full_name_sep: str = '/',
        default_converter=None,
        default_arg_full_name_short_name_map=None,
        no_default_value_or_description: bool = False,
        allows_sub_parameters: bool = False
):
    """
    Solving the `parameter_info` for parameter 1) full name, 2) short name, 3) default value,
    4) converter/formatter and 5) description.
    """

    arg_full_name = arg_short_name = converter = None
    if is_str(parameter_info):
        arg_full_name = parameter_info
        if not no_default_value_or_description:
            default_value = description = ''
    elif hasattr(parameter_info, '__len__') and hasattr(parameter_info, '__getitem__'):
        if allows_sub_parameters and (not no_default_value_or_description):
            raise ValueError("Sub-parameters are only allowed "
                             "when 'no_default_value_or_description' is True.")
        if (
                allows_sub_parameters and
                len(parameter_info) >= 2 and
                any(
                    isinstance(sub_parameter_info, (list, tuple))
                    for sub_parameter_info in parameter_info
                )
        ):
            return [
                solve_parameter_info(
                    parameter_info=sub_parameter_info,
                    arg_short_name_deduplication=arg_short_name_deduplication,
                    short_full_name_sep=short_full_name_sep,
                    default_converter=default_converter,
                    default_arg_full_name_short_name_map=default_arg_full_name_short_name_map,
                    no_default_value_or_description=True,
                    allows_sub_parameters=True
                )
                for sub_parameter_info in parameter_info
            ]
        elif no_default_value_or_description and len(parameter_info) >= 3:
            arg_full_name, arg_short_name, converter = parameter_info[:3]
        elif (not no_default_value_or_description) and len(parameter_info) >= 5:
            arg_full_name, arg_short_name, default_value, description, converter = parameter_info[:5]
        elif len(parameter_info) == 1:
            arg_full_name = parameter_info[0]
            if not no_default_value_or_description:
                default_value = description = ''
        elif len(parameter_info) == 2:
            if no_default_value_or_description:
                if is_str(parameter_info[1]):
                    arg_full_name, arg_short_name = parameter_info
                    converter = locate(arg_short_name)  # in case the 'arg_short_name' is actually a converter
                    if converter is not None:
                        arg_short_name = None
                else:
                    arg_full_name, converter = parameter_info
            else:
                arg_full_name, default_value = parameter_info
                description = ''
        elif len(parameter_info) == 3:
            if is_str(parameter_info[2]):
                arg_full_name, default_value, description = parameter_info
                converter = locate(description)  # in case the 'description' is actually a converter
                if converter is not None:
                    description = ''
            else:
                arg_full_name, default_value, converter = parameter_info
                description = ''
        elif len(parameter_info) == 4:
            arg_full_name, default_value, description, converter = parameter_info
            if is_str(converter):
                converter = locate(converter)

    if not arg_full_name:
        raise ValueError(f"The specify object '{parameter_info}' "
                         f"cannot be solved as a parameter.")

    if arg_short_name:
        arg_short_name = solve_name_conflict(
            name=arg_short_name,
            existing_names=arg_short_name_deduplication
        )
    else:
        if not (arg_full_name.startswith('lit:') or arg_full_name.startswith('val:')):
            arg_full_name, arg_short_name = solve_arg_full_and_short_name(
                arg_full_name,
                arg_short_name_deduplication=arg_short_name_deduplication,
                short_full_name_sep=short_full_name_sep,
                default_arg_full_name_short_name_map=default_arg_full_name_short_name_map
            )
    if not converter:
        converter = default_converter

    if no_default_value_or_description:
        return arg_full_name, arg_short_name, converter
    else:
        return arg_full_name, arg_short_name, default_value, converter, description


def args2str(
        args,
        active_parameter_infos: Union[Tuple, List] = None,
        default_arg_full_name_short_name_map: dict = None,
        default_value_formatter: Callable = None,
        name_val_delimiter='_',
        name_parts_delimiter='-',
        prefix: str = None,
        suffix: str = None,
        extension_name=None,
        use_full_name: bool = False,
        strings_for_null: Iterable[str] = None
) -> str:
    """
    Generates a string description for the given arguments.
    This string representation can be used in file names or field names
    for quick identification of major argument setup.

    Args:
        args: the arguments.
        active_parameter_infos: provides a sequence of parameter information objects indicating
        indicating what parameters should be included in the string representation, and provides
        parameter full name, short name and value formatting function. Can be:
            1) a three-tuple of the 'full name', the 'short name' and the 'value formatter';
                the 'short name' for an argument will appear in the string representation;
                the 'value format' should be a callable;
                for example, if `('learning_rate', 'lr', lambda x: str(x*100000))` is provided,
                    and `args.learning_rate` is `1e-4`, and `name_val_delimiter` is '_',
                    then string for this argument is `lr_10`;
            2) a two-tuple of the 'full name' and the 'short name',
                or a two-tuple of the 'full name' and the 'value formatter';
            3) just the 'full name'.

            In the second case or the third case, when the 'short name' or the 'value formatter'
            is missing, the `default_arg_full_name_short_name_map` and `default_value_formatter`
            will apply to provide the default 'short name' or the default 'value formatter'.
        default_arg_full_name_short_name_map: an optional mapping
            from an argument full name to its default short name;
            if this argument is provided,
                then the short named need not be provided in `active_parameter_infos`;
            if a short name is still provided in `active_parameter_infos`,
                then it overrides the short name in this dictionary.
        default_value_formatter: an optional function that serves as the default value formatter;
            if this parameter is not set,
            the internal default value formatter will be used as the default.
        name_val_delimiter: the delimiter between the short name and the value.
        name_parts_delimiter: the delimiter between the string of different arguments.
        prefix: adds this prefix string to the argument string.
        suffix: adds this suffix string to the argument string.
        extension_name: add this extension name
            to the end of the final argument string, after the `suffix`;
            this is convenient when using this method to return a file name.
        use_full_name: True to use parameter full name rather than short name
            in the returned string representation.
        strings_for_null: provides extra strings to represnet a null value; by default only 'None'
            represents a null value; other common string representaetions for a null value includes
            'null', 'n/a', etc.

    Returns:
        the argument string description.

    Examples:
        >>> from python_utils.common_utils.arg_utils.arg_parse import get_parsed_args
        >>> args = get_parsed_args(
        ...   default_batch_size=512,
        ...   default_dimension=100,
        ...   default_learning_rate=1e-4
        ... )
        >>> args2str(
        ...   args,
        ...   active_parameter_infos=[('learning_rate', 'lr', lambda x: str(int(x*100000)))]
        ... )
        'lr_10'

        >>> args2str(
        ...   args,
        ...   active_parameter_infos=[
        ...      ('dimension', 'd'),
        ...      ('learning_rate', 'lr', lambda x: str(int(x*100000)))
        ...   ]
        ... )
        'd_100-lr_10'

        >>> args2str(
        ...   args,
        ...   active_parameter_infos=[
        ...      'batch_size',
        ...      ('dimension', 'd'),
        ...      ('learning_rate', 'lr', lambda x: str(int(x*100000)))
        ...   ]
        ... )
        'bs_512-d_100-lr_10'

        >>> args2str(
        ...   args,
        ...   active_parameter_infos=[
        ...       ['batch_size', ('dimension', 'd')],
        ...       ('learning_rate', 'lr', lambda x: str(int(x*100000)))
        ...   ]
        ... )
        'bs_512_d_100-lr_10'

        >>> args2str(
        ...   args,
        ...   active_parameter_infos=[
        ...       [('batch_size', 'b'), ('dimension', 'd')],
        ...       ('learning_rate', 'lr', lambda x: str(int(x*100000)))
        ...   ]
        ... )
        'b_512_d_100-lr_10'

        >>> from datetime import datetime
        >>> from enum import Enum
        >>> class UtteranceIndexSignalLevel(str, Enum):
        ...   Utterance = 'utterance'

        >>> agg_name = None
        >>> job_name = 'personalized'
        >>> args2str(
        ...     args={
        ...         'utt_stats': datetime.now(),
        ...         'signal_level': UtteranceIndexSignalLevel.Utterance,
        ...         'sample_ratio': None
        ...     },
        ...     active_parameter_infos=(
        ...         f'lit:{agg_name}',
        ...         f'lit:{job_name}',
        ...         (
        ...             ('utt_stats', lambda x: x.strftime('%y%m%d')),
        ...             'lit:30days',
        ...             'signal_level'
        ...         ),
        ...         ('sample_ratio', lambda x: x * 10000),
        ...         f"lit:with_uid" if True else None
        ...     ),
        ...     use_full_name=True
        ... )
        'personalized-utt_stats_221020_30days_signal_level_utterance-with_uid'

    """
    _DIRECTIVE_VAL_ONLY = 'val:'
    _DIRECTIVE_LITERAL = 'lit:'

    if not active_parameter_infos:
        active_parameter_infos = get_keys(args)

    arg_short_name_deduplication = set()

    def _default_value_format(val):
        if val is None:
            return ''
        if isinstance(val, str):
            if isinstance(val, enum.Enum):
                return f'{val}'
            else:
                return remove_punctuation_except_for_hyphen(val)
        val_type = type(val)
        if val_type is float:
            return get_human_int_str(int(val * 1000000))
        elif val_type is int:
            return get_human_int_str(val)
        elif val_type is bool:
            return int(val)
        elif val_type in (list, tuple):
            return '_'.join((str(_default_value_format(x)) for x in val))
        else:
            return get_short_name(full_name=str(val))

    def _is_null_name_part(name_part):
        return (
                (not bool(name_part)) or
                name_part == 'None' or
                name_part == 'n/a' or
                (strings_for_null is not None and name_part in strings_for_null)
        )

    def _get_name_part(arg_full_name, arg_short_name):
        if arg_full_name.startswith(_DIRECTIVE_VAL_ONLY):
            arg_full_name = arg_short_name[len(_DIRECTIVE_VAL_ONLY):]
            val_only = True
        else:
            val_only = False
        val = get__(args, arg_full_name)
        if val is not None:
            val = str(val_formatter(val))
            if val_only:
                return val

            arg_name = arg_full_name if use_full_name else arg_short_name
            if arg_name:
                return f'{arg_name}{name_val_delimiter}{val}' if val else arg_name
            elif val:
                return val
            else:
                raise ValueError(
                    f"For argument {arg_full_name}, both its short name and value is empty."
                )

    name_parts = [prefix] if prefix else []
    for para_info in active_parameter_infos:
        if not para_info:
            continue
        if is_str(para_info) and para_info.startswith(_DIRECTIVE_LITERAL):
            name_part = para_info[len(_DIRECTIVE_LITERAL):]
        else:
            solved_parameter_info = solve_parameter_info(
                para_info,
                arg_short_name_deduplication=arg_short_name_deduplication,
                default_converter=(
                    _default_value_format
                    if default_value_formatter is None
                    else default_value_formatter
                ),
                default_arg_full_name_short_name_map=default_arg_full_name_short_name_map,
                no_default_value_or_description=True,
                allows_sub_parameters=True
            )

            name_part = None
            if isinstance(solved_parameter_info[0], tuple):
                sub_name_parts = []
                for arg_full_name, arg_short_name, val_formatter in solved_parameter_info:
                    if arg_full_name.startswith(_DIRECTIVE_LITERAL):
                        name_part = arg_full_name[len(_DIRECTIVE_LITERAL):]
                    else:
                        name_part = _get_name_part(arg_full_name, arg_short_name)
                    if not _is_null_name_part(name_part):
                        sub_name_parts.append(name_part)
                if sub_name_parts:
                    name_part = name_val_delimiter.join(sub_name_parts)
            else:
                arg_full_name, arg_short_name, val_formatter = solved_parameter_info
                name_part = _get_name_part(arg_full_name, arg_short_name)

        if not _is_null_name_part(name_part):
            name_parts.append(name_part)

    if suffix:
        name_parts.append(suffix)

    main_name = name_parts_delimiter.join(name_parts)
    if extension_name:
        if extension_name[0] != '.':
            extension_name = '.' + extension_name
        return main_name + extension_name
    else:
        return main_name


def get_arg_name(
        args=None,
        active_argname_info=None,
        name=None,
        name_prefix=None,
        name_suffix=None,
        name_val_delimiter='',
        name_parts_delimiter='-',
        **kwargs
):
    """
    A convenient function to construct a name either
        1) from the specified name parts `name`, `name_prefix`, `name_suffix`;
        2) or construct the name from the arguments, using the `arg2str` function.

    Args:
        args: provides the arguments, passed to `arg2str`.
        active_argname_info: provides the active arguments used in the name construction;
            passed to `arg2str`.
        name: manually specify the main name;
            if this is specified,
                then this function simply returns a concatenation
                of the 3-tuple (`name_prefix`, `name`, `name_suffix`),
                and the `args`, `active_argname_info`, `name_val_delimiter`, `kwargs` are ignored.
        name_prefix: provides the name prefix.
        name_suffix: provides the name suffix.
        name_val_delimiter: used to concatenate the name/value pair of each argument;
            passed to `arg2str`.
        name_parts_delimiter: used to concatenate name parts.
        kwargs: extra parameters to pass to the `arg2str`.
    Returns: a name,
        either a simple concatenation of (`name_prefix`, `name`, `name_suffix`)
            if `name` is specified,
        or constructed from the provided `args`.
    """
    return name_parts_delimiter.join((x for x in (name_prefix, name, name_suffix) if x)) if name \
        else (args2str(args=args,
                       active_parameter_infos=active_argname_info,
                       name_val_delimiter=name_val_delimiter,
                       prefix=name_prefix,
                       suffix=name_suffix,
                       **kwargs) if args is not None else name_parts_delimiter.join((name_prefix, name_suffix)))
