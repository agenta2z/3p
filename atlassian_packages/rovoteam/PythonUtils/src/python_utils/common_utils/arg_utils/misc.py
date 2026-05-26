import argparse
import dataclasses
from copy import copy
from typing import Any, Dict, Iterable, Type, Union

from python_utils.string_utils.prefix_suffix import add_prefix


def update_args(args: argparse.Namespace, **kwargs):
    """
    Create a copy of `args`, and then update it with named args from `kwargs`.

    Examples:
        >>> parser = argparse.ArgumentParser(description='test')
        ... parser.add_argument('--test', default='test', help='test')
        ... args = parser.parse_args()
        ... assert str(update_args(args, arg1='a', arg2='b')) == "Namespace(test='test', arg1='a', arg2='b')"
    """
    args = copy(args)
    if len(kwargs) == 0:
        return args
    for k, v in kwargs.items():
        if v is not None:
            setattr(args, k, v)
    return args


def extract_args_by_prefix(
    args: Union[argparse.Namespace, Dict[str, Any]],
    prefix: str,
    sep: str = "_",
    return_dict: bool = True,
    remove_prefix: bool = False,
    exclude: Iterable[str] = None,
) -> Union[Dict[str, Any], argparse.Namespace]:
    """
    Extracts a subset of key-value pairs from the input args by a common prefix.

    Args:
        args: An argparse.Namespace object or a dictionary containing key-value pairs.
        prefix: The prefix string to filter the keys in the args.
        sep: The separator string used between the prefix and the rest of the key. Defaults to '_'.
        return_dict: If True, returns the extracted key-value pairs as a dictionary.
                     If False, returns a new argparse.Namespace object with the extracted attributes.
        remove_prefix: If True, the prefix and separator will be removed from the extracted keys.
                       Defaults to False.
        exclude: Specify a set of keys to ignore; the keys in `args` with these specified names
            will be ignored.

    Returns:
        A dictionary or an argparse.Namespace object containing the key-value pairs with keys
        that have the specified prefix.

    Raises:
        ValueError: If the provided args is not an argparse.Namespace or a dictionary.

    Examples:
        >>> args = argparse.Namespace(inference_param1=1, inference_param2=2, other_param=3)
        >>> extract_args_by_prefix(args, prefix='inference', return_dict=True)
        {'inference_param1': 1, 'inference_param2': 2}
        >>> extract_args_by_prefix(args, prefix='inference', return_dict=True, remove_prefix=True)
        {'param1': 1, 'param2': 2}
    """
    if not prefix.endswith(sep):
        prefix += sep
    if isinstance(args, argparse.Namespace):
        args_dict = vars(args)
    elif isinstance(args, dict):
        args_dict = args
    else:
        raise ValueError("args must be an argparse.Namespace or a dictionary")

    extracted_args = {
        (key[len(prefix) :] if remove_prefix else key): value
        for key, value in args_dict.items()
        if key.startswith(prefix) and (exclude is None or key not in exclude)
    }

    if return_dict:
        return extracted_args
    else:
        return argparse.Namespace(**extracted_args)


def args_to_data_class(args, data_class_type: Type, arg_prefix: str = None, **kwargs):
    data_class_fields = {}
    for _field in dataclasses.fields(data_class_type):
        _field_name = _field.name

        _field_name_with_prefix = add_prefix(_field_name, arg_prefix)
        if hasattr(args, _field_name_with_prefix):
            if _field_name in kwargs:
                data_class_fields[_field_name] = kwargs[_field_name]
            else:
                data_class_fields[_field_name] = getattr(args, _field_name_with_prefix)
        elif _field_name in kwargs:
            data_class_fields[_field_name] = kwargs[_field_name]
    return data_class_type(**data_class_fields)


