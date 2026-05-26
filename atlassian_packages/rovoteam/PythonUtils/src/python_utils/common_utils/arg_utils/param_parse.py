from enum import Enum
from inspect import isclass, Parameter
from typing import Any, Dict, List, Mapping, Sequence, Union

# Sentinel value for required parameters in Mapping format
REQUIRED = Parameter.empty


def solve_params(params: Union[Sequence, Mapping[str, Any]]) -> List[Parameter]:
    """
    Convert parameter specifications into inspect.Parameter objects.

    This utility function provides a flexible way to define function parameters using
    various shorthand notations, which are then normalized into Parameter objects.

    Args:
        params: Parameter specifications. Can be:
            - Sequence: Each element can be:
                - Parameter: Used as-is (full control over parameter configuration)
                - str: Parameter name only (required parameter, no default, no annotation)
                - 2-tuple (name, default): Optional parameter with default value
                - 3-tuple (name, default, annotation): Optional parameter with default value
                  and type annotation/converter/validator callable
            - Mapping[str, Any]: Keys are parameter names, values are defaults (or REQUIRED for required)

    Returns:
        List of inspect.Parameter objects with kind=POSITIONAL_OR_KEYWORD

    Notes:
        - The third element in a 3-tuple is stored in the Parameter's annotation field.
          This can be a type (e.g., int, str), a converter function, or a validator,
          depending on your use case.
        - All generated parameters use POSITIONAL_OR_KEYWORD kind by default.
        - For more control over parameter kind or other attributes, pass a Parameter
          object directly.

    Examples:
        >>> # Required parameters
        >>> solve_params(['name', 'age'])
        [<Parameter "name">, <Parameter "age">]

        >>> # Optional parameters with defaults
        >>> solve_params([('count', 0), ('enabled', True)])
        [<Parameter "count=0">, <Parameter "enabled=True">]

        >>> # With type annotations
        >>> solve_params([('count', 0, int), ('ratio', 0.5, float)])
        [<Parameter "count: int = 0">, <Parameter "ratio: float = 0.5">]

        >>> # With converter/validator callables
        >>> solve_params([('port', 8080, int), ('name', '', str.strip)])
        [<Parameter "port: int = 8080">, <Parameter "name: <method 'strip' of 'str' objects> = ''">]

        >>> # Mixed specifications
        >>> solve_params(['required_arg', ('optional_arg', 'default'), ('typed_arg', 0, int)])
        [<Parameter "required_arg">, <Parameter "optional_arg='default'">, <Parameter "typed_arg: int = 0">]

        >>> # Using mapping format (simple defaults, REQUIRED for required params)
        >>> solve_params({'name': REQUIRED, 'age': 25, 'city': 'Default', 'config': None})
        [<Parameter "name">, <Parameter "age=25">, <Parameter "city='Default'">, <Parameter "config=None">]

        >>> # Using mapping format with tuple values (defaults + annotations)
        >>> solve_params({'name': REQUIRED, 'age': (25, int), 'temperature': (0.7, float), 'config': (None, dict)})
        [<Parameter "name">, <Parameter "age: int = 25">, <Parameter "temperature: float = 0.7">, <Parameter "config: dict = None">]

    Raises:
        ValueError: If a tuple/list has length other than 2 or 3, or if an element
                   is not a Parameter, str, tuple, or list.
    """
    # Handle Mapping input
    if isinstance(params, Mapping):
        out = []
        for param_name, value in params.items():
            if value is REQUIRED:
                # Required parameter (no default)
                out.append(Parameter(param_name, Parameter.POSITIONAL_OR_KEYWORD))
            elif isinstance(value, (tuple, list)):
                # Handle tuple/list values for more complex parameter specifications
                if len(value) == 1:
                    # 1-tuple: (default_value,)
                    default_value = value[0]
                    out.append(
                        Parameter(
                            param_name,
                            Parameter.POSITIONAL_OR_KEYWORD,
                            default=default_value,
                        )
                    )
                elif len(value) == 2:
                    # 2-tuple: (default_value, annotation)
                    default_value, annotation = value
                    out.append(
                        Parameter(
                            param_name,
                            Parameter.POSITIONAL_OR_KEYWORD,
                            default=default_value,
                            annotation=annotation,
                        )
                    )
                else:
                    raise ValueError(
                        f"Tuple/list value for '{param_name}' must have 1 or 2 elements, got {len(value)}"
                    )
            else:
                # Simple default value
                out.append(
                    Parameter(
                        param_name, Parameter.POSITIONAL_OR_KEYWORD, default=value
                    )
                )
        return out

    # Handle Sequence input (original logic)
    out = []
    for param in params:
        if isinstance(param, Parameter):
            out.append(param)
        elif isinstance(param, str):
            out.append(Parameter(param, Parameter.POSITIONAL_OR_KEYWORD))
        elif isinstance(param, (tuple, list)):
            if len(param) == 2:
                name, default = param
                out.append(
                    Parameter(name, Parameter.POSITIONAL_OR_KEYWORD, default=default)
                )
            elif len(param) == 3:
                name, default, type_or_converter_or_validator = param
                out.append(
                    Parameter(
                        name,
                        Parameter.POSITIONAL_OR_KEYWORD,
                        default=default,
                        annotation=type_or_converter_or_validator,
                    )
                )
            else:
                raise ValueError(f"Tuple must have 2 or 3 elements, got {len(param)}")
        else:
            raise ValueError(f"Unknown param type: {type(param)}")

    return out


def solve_args_with_params(
    raw_args_dict: Mapping[str, Any], params: Union[Sequence, Mapping[str, Any]]
) -> Dict[str, Any]:
    """
    Process raw arguments using parameter specifications with automatic type conversion.

    Validates, converts, and filters arguments based on parameter definitions. Automatically
    detects and converts Enum types from annotations, along with other type converters.

    Args:
        raw_args_dict: Dictionary of raw argument names and values (e.g., from argparse.Namespace,
                      request parameters, or config files)
        params: Parameter specifications (same format as solve_params). Defines expected
               parameters, their defaults, and type converters/validators/enums

    Returns:
        Dictionary of processed arguments with:
        - Only parameters defined in params
        - Default values applied for missing optional parameters
        - Type conversion/validation applied via annotation callables
        - Automatic enum conversion when annotation is an Enum class

    Notes:
        - Required parameters (no default) must be present in raw_args_dict
        - Enum classes are automatically detected from annotations and converted
        - For Enum annotations, accepts both enum values and enum instances
        - Other callables in annotations are applied as converters/validators

    Examples:
        >>> from enum import Enum
        >>> class Color(Enum):
        ...     RED = 'red'
        ...     BLUE = 'blue'
        ...     GREEN = 'green'

        >>> # Basic usage with defaults
        >>> raw = {'name': 'Alice', 'extra': 'ignored'}
        >>> solve_args_with_params(raw, ['name', ('age', 25)])
        {'name': 'Alice', 'age': 25}

        >>> # With type conversion
        >>> raw = {'count': '42', 'ratio': '0.5'}
        >>> solve_args_with_params(raw, [('count', 0, int), ('ratio', 0.0, float)])
        {'count': 42, 'ratio': 0.5}

        >>> # With automatic enum conversion
        >>> raw = {'color': 'red', 'size': 10}
        >>> solve_args_with_params(raw, [('color', 'blue', Color), ('size', 0, int)])
        {'color': <Color.RED: 'red'>, 'size': 10}

        >>> # Enum already as instance (passthrough)
        >>> raw = {'color': Color.BLUE}
        >>> solve_args_with_params(raw, [('color', 'red', Color)])
        {'color': <Color.BLUE: 'blue'>}

        >>> # With validator callable
        >>> def validate_positive(x):
        ...     x = int(x)
        ...     if x <= 0:
        ...         raise ValueError("Must be positive")
        ...     return x
        >>> raw = {'count': '5'}
        >>> solve_args_with_params(raw, [('count', 1, validate_positive)])
        {'count': 5}

        >>> # Mixed: enum, type conversion, and defaults
        >>> raw = {'mode': 'train', 'epochs': '100'}
        >>> class Mode(Enum):
        ...     TRAIN = 'train'
        ...     EVAL = 'eval'
        >>> solve_args_with_params(
        ...     raw,
        ...     [('mode', 'train', Mode), ('epochs', 10, int), ('verbose', True)]
        ... )
        {'mode': <Mode.TRAIN: 'train'>, 'epochs': 100, 'verbose': True}

    Raises:
        KeyError: If a required parameter is missing from raw_args_dict
        ValueError: If type conversion/validation fails or invalid enum value provided
    """
    # Convert params to Parameter objects
    param_list = solve_params(params)

    # Build result dictionary
    result = {}

    for param in param_list:
        param_name = param.name

        # Check if argument is provided
        if param_name in raw_args_dict:
            value = raw_args_dict[param_name]

            # Apply type conversion/validation if annotation exists
            if param.annotation != Parameter.empty and param.annotation is not None:
                annotation = param.annotation

                # Check if annotation is an Enum class
                if isclass(annotation) and issubclass(annotation, Enum):
                    try:
                        # If already an enum instance of the correct type, use as-is;
                        # otherwise convert value to enum
                        if not isinstance(value, annotation):
                            value = annotation(value)
                    except (ValueError, KeyError) as e:
                        valid_values = [e.value for e in annotation]
                        raise ValueError(
                            f"Invalid enum value for '{param_name}': {value}. "
                            f"Valid values: {valid_values}"
                        ) from e
                else:
                    # Apply as a regular converter/validator callable
                    try:
                        value = annotation(value)
                    except Exception as e:
                        raise ValueError(
                            f"Type conversion failed for parameter '{param_name}': {e}"
                        ) from e

            result[param_name] = value

        elif param.default != Parameter.empty:
            # Use default value for optional parameters
            result[param_name] = param.default

        else:
            # Required parameter is missing
            raise KeyError(
                f"Required parameter '{param_name}' is missing from raw_args_dict"
            )

    return result
