import re
import string
from typing import Mapping, Callable, Dict, Optional, Any, List, Union, Tuple, Set

from rankevolve.src.utils.common_utils import dict_


def get_common_helpers() -> Dict[str, Any]:
    """
    Returns a dictionary of common helper values for Python str.format templates.

    Unlike Handlebars/Jinja2, Python's str.format doesn't support calling functions
    directly in the template. These helpers return pre-computed values that can be
    used as variables in templates.

    Returns:
        Dict[str, Any]: Dictionary mapping helper names to values
    """
    from rankevolve.src.utils.datetime_utils.common import (
        current_date_time_string,
        current_date_string,
        current_time_string
    )
    return {
        'currentDateTime': current_date_time_string(),
        'currentDate': current_date_string(),
        'currentTime': current_time_string()
    }


def extract_variables(template: str) -> Set[str]:
    """
    Extract variable names from a Python str.format template string.

    This function parses the template to find all field names used in
    format placeholders like {name}, {name.attr}, {name[0]}, {name!r}, {name:spec}.

    Args:
        template (str): Python format string

    Returns:
        Set[str]: Set of variable names found in the template

    Examples:
        >>> sorted(extract_variables("Hello {name}!"))
        ['name']

        >>> sorted(extract_variables("{name} is {age} years old."))
        ['age', 'name']

        >>> sorted(extract_variables("{user.name} at {user.email}"))
        ['user']

        >>> sorted(extract_variables("{count:03d} items at ${price:.2f}"))
        ['count', 'price']

        >>> sorted(extract_variables("{name!r} and {value!s}"))
        ['name', 'value']

        >>> sorted(extract_variables("No variables here"))
        []

        >>> sorted(extract_variables("Escaped {{braces}} and {real}"))
        ['real']
    """
    variables = set()
    formatter = string.Formatter()

    try:
        for _, field_name, _, _ in formatter.parse(template):
            if field_name is not None and field_name != '':
                # Extract the root variable name (before any . or [ accessor)
                # field_name could be "name", "name.attr", "name[0]", etc.
                root_name = field_name.split('.')[0].split('[')[0]
                # Skip positional arguments (numeric indices)
                if root_name and not root_name.isdigit():
                    variables.add(root_name)
    except (ValueError, IndexError):
        # If parsing fails, fall back to regex
        # Pattern matches {name}, {name.attr}, {name[0]}, {name:spec}, {name!conv}
        pattern = r'\{([a-zA-Z_][a-zA-Z0-9_]*)(?:[.\[]|[!:}])'
        for match in re.finditer(pattern, template):
            variables.add(match.group(1))

    return variables


def compile_template(
        template: str,
        return_variables: bool = False,
        required_variables: Optional[Union[Set[str], List[str]]] = None
) -> Union[str, Tuple[str, Set[str]]]:
    """
    Validate a Python str.format template string and optionally return variables found in it.

    Note: Unlike Jinja2/Handlebars, Python str.format templates don't need compilation.
    This function validates the template syntax and extracts variable names.

    Args:
        template (str): Python format string
        return_variables (bool): If True, return tuple of (template, variables_found)
        required_variables (Optional[Union[Set[str], List[str]]]): Set or list of variable
            names that must be present in the template. If provided, will raise
            ValueError if any required variables are missing.

    Returns:
        str: The validated template string (if return_variables=False)
        Tuple[str, Set[str]]: (template, variables_found) if return_variables=True

    Raises:
        ValueError: If required_variables is provided and some required
            variables are not found in the template, or if template syntax is invalid.

    Examples:
        >>> template_str = "Hello {name}! You are {age} years old."
        >>>
        >>> # Just validate the template
        >>> compiled = compile_template(template_str)
        >>> compiled == template_str
        True

        >>> # Get template and variables
        >>> compiled, vars_found = compile_template(template_str, return_variables=True)
        >>> sorted(vars_found)
        ['age', 'name']

        >>> # Validate required variables (success case)
        >>> compiled = compile_template(template_str, required_variables=['name', 'age'])
        >>> compiled == template_str
        True

        >>> # Validation failure case
        >>> try:
        ...     compile_template(template_str, required_variables=['name', 'age', 'email'])
        ... except ValueError as e:
        ...     print(f"Validation failed: {e}")
        Validation failed: Missing required variables in template: {'email'}

        >>> # Empty template with required variables
        >>> try:
        ...     compile_template("Static text only", required_variables=['name'])
        ... except ValueError as e:
        ...     print(f"Validation failed: {e}")
        Validation failed: Missing required variables in template: {'name'}
    """
    # Validate template syntax by attempting to parse it
    variables_found = extract_variables(template)

    # Validate required variables if provided
    if required_variables is not None:
        required_set = set(required_variables) if not isinstance(required_variables, set) else required_variables
        missing_variables = required_set - variables_found

        if missing_variables:
            raise ValueError(
                f"Missing required variables in template: {missing_variables}"
            )

    if return_variables:
        return template, variables_found

    return template


def format_template(
        template: str,
        feed: Optional[Mapping[str, Any]] = None,
        post_process: Optional[Callable[[str], str]] = None,
        helpers: Optional[Mapping[str, Any]] = None,
        use_builtin_common_helpers: bool = True,
        **default_feed
) -> str:
    """
    Renders a Python str.format template string with provided context.

    Args:
        template (str): The Python format string (with {variable} placeholders).
        feed (Optional[Mapping[str, Any]]): A mapping of variables for the template context.
            These will be merged with any kwargs provided (with feed taking precedence).
        post_process (Optional[Callable[[str], str]]): A function to post-process the rendered
            string (e.g. unescaping HTML entities).
        helpers (Optional[Mapping[str, Any]]): Additional values to make available in the template.
            Note: Unlike Jinja2/Handlebars, these must be pre-computed values, not callables.
        use_builtin_common_helpers (bool): Whether to add default date/time values
            (e.g. currentDateTime). Defaults to True.
        **default_feed: Default feed. Any default values will be overwritten by values in `feed`.

    Returns:
        str: The rendered template with placeholders replaced by corresponding values.

    Examples:
        Basic variable substitution:
        >>> format_template("Hello, {name}!", name="Alice")
        'Hello, Alice!'

        Numeric values:
        >>> format_template("You have {count} new messages.", count=5)
        'You have 5 new messages.'

        Decimal values:
        >>> format_template("Temperature is {temp} degrees.", temp=22.5)
        'Temperature is 22.5 degrees.'

        Format specifiers:
        >>> format_template("Price: ${price:.2f}", price=19.5)
        'Price: $19.50'

        >>> format_template("Count: {count:05d}", count=42)
        'Count: 00042'

        Using currentDateTime helper:
        >>> import re
        >>> bool(re.match(r'<CurrentDate>\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}</CurrentDate>',
        ...     format_template("<CurrentDate>{currentDateTime}</CurrentDate>")))
        True

        Using currentDate:
        >>> bool(re.match(r'^Date: \\d{4}-\\d{2}-\\d{2}$',
        ...     format_template("Date: {currentDate}")))
        True

        Using currentTime:
        >>> bool(re.match(r'^Time: \\d{2}:\\d{2}:\\d{2}$',
        ...     format_template("Time: {currentTime}")))
        True

        Using custom helpers (pre-computed values):
        >>> format_template("{greeting} {name}!", helpers={"greeting": "Welcome"}, name="john")
        'Welcome john!'

        Merging feed and kwargs (feed has precedence):
        >>> format_template("{name} is {age}", feed={"name": "Bob", "age": 30}, name="Alice")
        'Bob is 30'
        >>> format_template("{name} is {age}", feed={"age": 30}, name="Alice")
        'Alice is 30'

        Using pandas Series:
        >>> import pandas as pd
        >>> series = pd.Series({'name': 'Bob', 'age': 25})
        >>> format_template("Hello {name}! You are {age} years old.", feed=series)
        'Hello Bob! You are 25 years old.'

        Using pandas DataFrame row:
        >>> import pandas as pd
        >>> df = pd.DataFrame({'name': ['Alice', 'Bob'], 'age': [30, 25]})
        >>> row = df.iloc[0]
        >>> format_template("Hello {name}! You are {age} years old.", feed=row)
        'Hello Alice! You are 30 years old.'
    """
    # 1. Gather the context (merge kwargs + feed).
    context = dict_(default_feed)

    # 2. Optionally add built-in helpers to the context
    if use_builtin_common_helpers:
        context.update(get_common_helpers())

    # 3. Optionally add custom helpers
    if helpers:
        context.update(helpers)

    # 4. Add feed last so it takes precedence
    if feed is not None:
        context.update(feed)

    # 5. Render the template using str.format
    result = template.format(**context)

    # 6. Apply post-processing if provided
    if post_process:
        result = post_process(result)

    return result


def validate_table_and_compile_template(
        data_frame: Any,
        prompt: str,
        get_colnames: Optional[Callable[[Any], List[str]]] = None,
) -> Tuple[str, Any, List[str], List[str]]:
    """
    Utility function to validate data frame columns against Python str.format template variables
    and return validated template with dataframe.

    Args:
        data_frame: Any data frame object (pandas, spark, etc.)
        prompt: Python format string
        get_colnames: Optional function to extract column names from data_frame.
                     If None, assumes data_frame has .columns attribute (like pandas)

    Returns:
        Tuple containing:
        - validated template string
        - original data frame
        - list of required variables found in template
        - list of missing columns (empty if all found)

    Raises:
        ValueError: If template parsing fails or column names cannot be extracted

    Examples:
        >>> import pandas as pd
        >>> df = pd.DataFrame({'name': ['Alice', 'Bob'], 'age': [30, 25]})
        >>> template, _, required, missing = validate_table_and_compile_template(
        ...     df, "Hello {name}! You are {age} years old.")
        >>> sorted(required)
        ['age', 'name']
        >>> missing
        []

        >>> template, _, required, missing = validate_table_and_compile_template(
        ...     df, "{name} - {email}")
        >>> 'email' in missing
        True
    """
    # Extract variables from the template
    try:
        required_variables = list(extract_variables(prompt))
    except Exception as e:
        raise ValueError(f"Failed to parse Python format template: {str(e)}")

    # Get column names from data frame
    if get_colnames is not None:
        try:
            columns = get_colnames(data_frame)
        except Exception as e:
            raise ValueError(f"Failed to get column names using provided function: {str(e)}")
    else:
        # Default: assume pandas-like interface
        try:
            columns = list(data_frame.columns)
        except AttributeError:
            raise ValueError("Data frame does not have .columns attribute. Please provide get_colnames function.")

    # Check if required variables exist as columns in the dataframe
    missing_columns = []
    found_columns = []

    for var in required_variables:
        if var in columns:
            found_columns.append(var)
        else:
            missing_columns.append(var)

    return prompt, data_frame, required_variables, missing_columns
