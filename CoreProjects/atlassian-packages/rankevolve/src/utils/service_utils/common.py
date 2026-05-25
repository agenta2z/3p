from typing import Any, Callable, Dict, Mapping, Optional, Sequence, Union

from rankevolve.src.utils.common_utils.arg_utils.param_parse import solve_args_with_params


def generate_response(
    request_data: Dict[str, Any],
    params: Union[Sequence, Mapping[str, Any]],
    generate_response_func: Callable,
    response_func: Optional[Callable] = None,
    include_params_in_response: bool = False,
    raise_exception: bool = False,
    response_field_name="result",
    success_flag_field_name="success",
    params_field_name="params",
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
            Defaults to False.
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
        KeyError: If a required parameter is missing from request_data (when raise_exception=True
            or during parameter extraction)
        ValueError: If type conversion/validation fails during parameter processing
        Exception: Any exception from generate_response_func (when raise_exception=True)
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
    all_params = {**extracted_params, **additional_kwargs}

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
        success_flag_field_name: success,
    }

    if include_params_in_response:
        response_data[params_field_name] = all_params

    # Return formatted response or raw dict
    if response_func is None:
        return response_data
    return response_func(response_data)
