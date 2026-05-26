from typing import Any, Callable, Dict, Mapping, Optional, Sequence, Union

from python_utils.common_utils.arg_utils.param_parse import (
    solve_args_with_params,
)


def generate_response(
    request_data: Dict[str, Any],
    params: Union[Sequence, Mapping[str, Any]],
    generate_response_func: Callable,
    response_func: Optional[Callable] = None,
    include_params_in_response: bool = False,
    raise_exception: bool = False,
    response_field_name='result',
    success_flag_field_name='success',
    params_field_name='params',
) -> Any:
    """
    Generic function to process request data and generate a response with parameter validation.

    This function handles parameter extraction, validation, type conversion, and response
    formatting. It uses solve_args_with_params internally to process parameters according
    to their specifications, then calls the provided generation function with the validated
    parameters.

    Args:
        request_data (Dict[str, Any]): The incoming request data as a dictionary containing
            parameter values to be validated and passed to the generation function.
        params (Union[Sequence, Mapping[str, Any]]): Parameter specifications defining how
            to extract and validate parameters from request_data. Can be:
            - Sequence: Each element can be:
                - str: Required parameter (no default)
                - (name, default): Optional parameter with default value
                - (name, default, annotation): Parameter with type/enum/validator
            - Mapping[str, Any]: Dictionary where keys are parameter names and values are
                defaults (all parameters are optional in this format)
        generate_response_func (Callable): Function to call with the extracted and validated
            parameters. This function will receive all validated parameters plus any
            additional kwargs from request_data.
        response_func (Optional[Callable], optional): Function to format the final response.
            If None, returns a dictionary with result, success flag, and optionally params.
            Defaults to None.
        include_params_in_response (bool, optional): Whether to include all parameters used
            in the response dictionary. Defaults to False.
        raise_exception (bool, optional): Whether to raise exceptions from generate_response_func.
            If False, catches exceptions and returns them in the response with success=False.
            Note: typo in parameter name is kept for backward compatibility. Defaults to False.
        response_field_name (str, optional): Key name for the generated result in the response
            dictionary. Defaults to 'result'.
        success_flag_field_name (str, optional): Key name for the success flag in the response
            dictionary. Defaults to 'success'.
        params_field_name (str, optional): Key name for the parameters in the response dictionary
            (only used when include_params_in_response=True). Defaults to 'params'.

    Returns:
        Any: Response formatted by response_func if provided, otherwise a dictionary containing:
            - {response_field_name}: The result from generate_response_func
            - {success_flag_name}: Boolean indicating success/failure
            - {params_field_name}: All parameters used (only if include_params_in_response=True)

    Raises:
        KeyError: If a required parameter is missing from request_data (when raise_excption=True
            or during parameter extraction)
        ValueError: If type conversion/validation fails during parameter processing
        Exception: Any exception from generate_response_func (when raise_excption=True)

    Examples:
        Simple usage with required and optional parameters:

        >>> def my_func(prompt, model='default', temperature=0.7):
        ...     return f"Prompt: {prompt}, Model: {model}, Temp: {temperature}"
        >>>
        >>> params = [
        ...     'prompt',  # Required parameter
        ...     ('model', 'claude-sonnet'),  # Optional with default
        ...     ('temperature', 0.7, float),  # Optional with type conversion
        ... ]
        >>>
        >>> response = generate_response(
        ...     request_data={'prompt': 'Hello', 'temperature': '0.9'},
        ...     params=params,
        ...     generate_response_func=my_func
        ... )
        >>>
        >>> response['success']
        True
        >>> response['result']
        'Prompt: Hello, Model: claude-sonnet, Temp: 0.9'

        Using enum for automatic type conversion:

        >>> from enum import Enum
        >>>
        >>> class ModelType(Enum):
        ...     FAST = 'fast'
        ...     ACCURATE = 'accurate'
        >>>
        >>> def process(prompt, model_type=ModelType.FAST):
        ...     return f"{prompt} using {model_type.value}"
        >>>
        >>> params = [
        ...     'prompt',
        ...     ('model_type', 'fast', ModelType),  # Automatic enum conversion
        ... ]
        >>>
        >>> response = generate_response(
        ...     request_data={'prompt': 'Test', 'model_type': 'accurate'},
        ...     params=params,
        ...     generate_response_func=process
        ... )
        >>>
        >>> response['success']
        True
        >>> 'accurate' in response['result']
        True

        Custom response formatter:

        >>> def json_formatter(data):
        ...     return {'json_response': data, 'formatted': True}
        >>>
        >>> response = generate_response(
        ...     request_data={'prompt': 'Hello'},
        ...     params=['prompt'],
        ...     generate_response_func=lambda prompt: f"Got: {prompt}",
        ...     response_func=json_formatter
        ... )
        >>>
        >>> response['formatted']
        True
        >>> 'Got: Hello' in response['json_response']['result']
        True

        Including parameters in response:

        >>> response = generate_response(
        ...     request_data={'prompt': 'Test', 'temperature': 0.8},
        ...     params=['prompt', ('temperature', 0.7)],
        ...     generate_response_func=lambda **kwargs: "Generated",
        ...     include_params_in_response=True
        ... )
        >>>
        >>> response['params']['prompt']
        'Test'
        >>> response['params']['temperature']
        0.8

        Handling additional parameters as kwargs:

        >>> def flexible_func(prompt, **kwargs):
        ...     extra = kwargs.get('extra_param', 'none')
        ...     return f"Prompt: {prompt}, Extra: {extra}"
        >>>
        >>> response = generate_response(
        ...     request_data={'prompt': 'Hi', 'extra_param': 'value', 'other': 123},
        ...     params=['prompt'],
        ...     generate_response_func=flexible_func
        ... )
        >>>
        >>> response['success']
        True
        >>> 'Extra: value' in response['result']
        True

        Error handling with raise_excption=False (default):

        >>> def failing_func(prompt):
        ...     raise ValueError("Something went wrong")
        >>>
        >>> response = generate_response(
        ...     request_data={'prompt': 'Test'},
        ...     params=['prompt'],
        ...     generate_response_func=failing_func,
        ...     raise_excption=False
        ... )
        >>>
        >>> response['success']
        False
        >>> 'Something went wrong' in response['result']
        True

        Custom field names:

        >>> response = generate_response(
        ...     request_data={'prompt': 'Hello'},
        ...     params=['prompt'],
        ...     generate_response_func=lambda prompt: f"Echo: {prompt}",
        ...     response_field_name='output',
        ...     success_flag_field_name='ok'
        ... )
        >>>
        >>> response['ok']
        True
        >>> response['output']
        'Echo: Hello'

        Using mapping format for params:

        >>> params_dict = {
        ...     'prompt': None,  # Required (None as default means required)
        ...     'model': 'default-model',
        ...     'temperature': 0.7
        ... }
        >>>
        >>> def simple_gen(prompt, model, temperature):
        ...     return f"{prompt} [{model}] @ {temperature}"
        >>>
        >>> response = generate_response(
        ...     request_data={'prompt': 'Test'},
        ...     params=params_dict,
        ...     generate_response_func=simple_gen
        ... )
        >>>
        >>> response['success']
        True
        >>> 'default-model' in response['result']
        True
    """
    # Use solve_args_with_params to handle all parameter processing
    # This automatically handles:
    # - Parameter extraction with defaults
    # - Type conversion/validation via annotations
    # - Automatic enum detection and conversion
    # - Required parameter validation (raises KeyError if missing)
    extracted_params = solve_args_with_params(request_data, params)

    # Extract any additional parameters for **kwargs
    # Use extracted_params keys directly since it already contains the processed parameter names
    additional_kwargs = {
        k: v for k, v in request_data.items() if k not in extracted_params
    }

    # Call the generate function with the extracted parameters plus any additional kwargs
    all_params = {
        **extracted_params,
        **additional_kwargs
    }

    if raise_exception:
        generated_result = generate_response_func(**all_params)
        success = True
    else:
        try:
            generated_result = generate_response_func(**all_params)
            success = True
        except Exception as err:
            generated_result = str(err)
            success = False

    # Build response with all parameters used
    response_data = {
        response_field_name: generated_result,
        success_flag_field_name: success
    }

    if include_params_in_response:
        response_data[params_field_name] = all_params

    # Return formatted response or raw dict
    if response_func is None:
        return response_data
    return response_func(response_data)