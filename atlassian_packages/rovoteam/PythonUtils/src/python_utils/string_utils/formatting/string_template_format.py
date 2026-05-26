import re
import string
from string import Template
from typing import Mapping, Callable, Dict, Optional, Any, List, Union, Tuple, Set

from python_utils.common_utils import dict_


class SafeTemplate(Template):
    """
    A Template subclass that provides safe_substitute by default and
    allows customization of the delimiter pattern if needed.
    """
    pass


def get_common_helpers() -> Dict[str, Any]:
    """
    Returns a dictionary of common helper values for string.Template templates.

    Since string.Template doesn't support calling functions directly in the template,
    these helpers return pre-computed values that can be used as variables.

    Returns:
        Dict[str, Any]: Dictionary mapping helper names to values
    """
    from python_utils.datetime_utils.common import (
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
    Extract variable names from a string.Template template string.

    This function parses the template to find all variable references using
    $variable or ${variable} syntax.

    Args:
        template (str): string.Template format string

    Returns:
        Set[str]: Set of variable names found in the template

    Examples:
        >>> sorted(extract_variables("Hello $name!"))
        ['name']

        >>> sorted(extract_variables("$name is $age years old."))
        ['age', 'name']

        >>> sorted(extract_variables("${name} at ${email}"))
        ['email', 'name']

        >>> sorted(extract_variables("Mixed $name and ${age} styles"))
        ['age', 'name']

        >>> sorted(extract_variables("No variables here"))
        []

        >>> sorted(extract_variables("Escaped $$dollar and $real"))
        ['real']

        >>> sorted(extract_variables("Price is $$100 for $item"))
        ['item']
    """
    variables = set()

    # Use Template's pattern to extract variables
    # The pattern matches: $$ (escaped), $identifier, ${identifier}, or invalid
    pattern = Template.pattern

    for match in pattern.finditer(template):
        # match.group('named') is for $identifier
        # match.group('braced') is for ${identifier}
        named = match.group('named')
        braced = match.group('braced')

        if named is not None:
            variables.add(named)
        elif braced is not None:
            variables.add(braced)
        # 'escaped' ($$) and 'invalid' are ignored

    return variables


def compile_template(
        template: str,
        return_variables: bool = False,
        required_variables: Optional[Union[Set[str], List[str]]] = None
) -> Union[Template, Tuple[Template, Set[str]]]:
    """
    Compile a string.Template template string and optionally return variables found in it.

    Args:
        template (str): string.Template format string (using $var or ${var} syntax)
        return_variables (bool): If True, return tuple of (Template, variables_found)
        required_variables (Optional[Union[Set[str], List[str]]]): Set or list of variable
            names that must be present in the template. If provided, will raise
            ValueError if any required variables are missing.

    Returns:
        Template: Compiled string.Template object (if return_variables=False)
        Tuple[Template, Set[str]]: (Template, variables_found) if return_variables=True

    Raises:
        ValueError: If required_variables is provided and some required
            variables are not found in the template, or if template syntax is invalid.

    Examples:
        >>> template_str = "Hello $name! You are $age years old."
        >>>
        >>> # Just compile the template
        >>> compiled = compile_template(template_str)
        >>> print(type(compiled))
        <class 'string.Template'>

        >>> # Get compiled template and variables
        >>> compiled, vars_found = compile_template(template_str, return_variables=True)
        >>> sorted(vars_found)
        ['age', 'name']

        >>> # Validate required variables (success case)
        >>> compiled = compile_template(template_str, required_variables=['name', 'age'])
        >>> print(type(compiled))
        <class 'string.Template'>

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
    # Compile the template
    try:
        template_obj = Template(template)
    except Exception as e:
        raise ValueError(f"Invalid template syntax: {str(e)}")

    # Extract variables if needed
    if return_variables or required_variables is not None:
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
            return template_obj, variables_found

    return template_obj


def format_template(
        template: str,
        feed: Optional[Mapping[str, Any]] = None,
        post_process: Optional[Callable[[str], str]] = None,
        helpers: Optional[Mapping[str, Any]] = None,
        use_builtin_common_helpers: bool = True,
        safe: bool = False,
        **default_feed
) -> str:
    """
    Renders a string.Template template string with provided context.

    This uses Python's string.Template class which is safer for user-provided
    templates as it only supports simple variable substitution (no expressions).

    Args:
        template (str): The string.Template format string (with $var or ${var} placeholders).
        feed (Optional[Mapping[str, Any]]): A mapping of variables for the template context.
            These will be merged with any kwargs provided (with feed taking precedence).
        post_process (Optional[Callable[[str], str]]): A function to post-process the rendered
            string.
        helpers (Optional[Mapping[str, Any]]): Additional values to make available in the template.
        use_builtin_common_helpers (bool): Whether to add default date/time values
            (e.g. currentDateTime). Defaults to True.
        safe (bool): If True, use safe_substitute() which leaves unmatched placeholders
            unchanged instead of raising KeyError. Defaults to False.
        **default_feed: Default feed. Any default values will be overwritten by values in `feed`.

    Returns:
        str: The rendered template with placeholders replaced by corresponding values.

    Examples:
        Basic variable substitution:
        >>> format_template("Hello, $name!", name="Alice")
        'Hello, Alice!'

        Using braced syntax:
        >>> format_template("Hello, ${name}!", name="Alice")
        'Hello, Alice!'

        Numeric values:
        >>> format_template("You have $count new messages.", count=5)
        'You have 5 new messages.'

        Decimal values:
        >>> format_template("Temperature is $temp degrees.", temp=22.5)
        'Temperature is 22.5 degrees.'

        Escaped dollar sign:
        >>> format_template("Price: $$$price", price=100)
        'Price: $100'

        Using currentDateTime helper:
        >>> import re
        >>> bool(re.match(r'<CurrentDate>\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}</CurrentDate>',
        ...     format_template("<CurrentDate>$currentDateTime</CurrentDate>")))
        True

        Using currentDate:
        >>> bool(re.match(r'^Date: \\d{4}-\\d{2}-\\d{2}$',
        ...     format_template("Date: $currentDate")))
        True

        Using currentTime:
        >>> bool(re.match(r'^Time: \\d{2}:\\d{2}:\\d{2}$',
        ...     format_template("Time: $currentTime")))
        True

        Using custom helpers:
        >>> format_template("$greeting $name!", helpers={"greeting": "Welcome"}, name="john")
        'Welcome john!'

        Merging feed and kwargs (feed has precedence):
        >>> format_template("$name is $age", feed={"name": "Bob", "age": 30}, name="Alice")
        'Bob is 30'
        >>> format_template("$name is $age", feed={"age": 30}, name="Alice")
        'Alice is 30'

        Safe mode (missing variables left unchanged):
        >>> format_template("Hello $name, your id is $id", safe=True, name="Alice")
        'Hello Alice, your id is $id'

        Using pandas Series:
        >>> import pandas as pd
        >>> series = pd.Series({'name': 'Bob', 'age': 25})
        >>> format_template("Hello $name! You are $age years old.", feed=series)
        'Hello Bob! You are 25 years old.'

        Using pandas DataFrame row:
        >>> import pandas as pd
        >>> df = pd.DataFrame({'name': ['Alice', 'Bob'], 'age': [30, 25]})
        >>> row = df.iloc[0]
        >>> format_template("Hello $name! You are $age years old.", feed=row)
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

    # 5. Render the template
    template_obj = Template(template)
    if safe:
        result = template_obj.safe_substitute(context)
    else:
        result = template_obj.substitute(context)

    # 6. Apply post-processing if provided
    if post_process:
        result = post_process(result)

    return result


def validate_table_and_compile_template(
        data_frame: Any,
        prompt: str,
        get_colnames: Optional[Callable[[Any], List[str]]] = None,
) -> Tuple[Template, Any, List[str], List[str]]:
    """
    Utility function to validate data frame columns against string.Template template variables
    and return compiled template with dataframe.

    Args:
        data_frame: Any data frame object (pandas, spark, etc.)
        prompt: string.Template format string
        get_colnames: Optional function to extract column names from data_frame.
                     If None, assumes data_frame has .columns attribute (like pandas)

    Returns:
        Tuple containing:
        - compiled string.Template object
        - original data frame
        - list of required variables found in template
        - list of missing columns (empty if all found)

    Raises:
        ValueError: If template parsing fails or column names cannot be extracted

    Examples:
        >>> import pandas as pd
        >>> df = pd.DataFrame({'name': ['Alice', 'Bob'], 'age': [30, 25]})
        >>> template, _, required, missing = validate_table_and_compile_template(
        ...     df, "Hello $name! You are $age years old.")
        >>> sorted(required)
        ['age', 'name']
        >>> missing
        []

        >>> template, _, required, missing = validate_table_and_compile_template(
        ...     df, "$name - $email")
        >>> 'email' in missing
        True
    """
    # Extract variables from the template
    try:
        required_variables = list(extract_variables(prompt))
    except Exception as e:
        raise ValueError(f"Failed to parse string.Template template: {str(e)}")

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

    # Compile the template
    try:
        template_obj = Template(prompt)
    except Exception as e:
        raise ValueError(f"Failed to compile string.Template template: {str(e)}")

    return template_obj, data_frame, required_variables, missing_columns
