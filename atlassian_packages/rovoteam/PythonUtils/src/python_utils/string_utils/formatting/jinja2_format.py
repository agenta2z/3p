import re
from typing import Mapping, Callable, Dict, Optional, Any, List, Union, Tuple, Set

from jinja2 import Template, meta, Environment, ChainableUndefined

from python_utils.common_utils import dict_


def get_common_helpers() -> Dict[str, Callable]:
    """
    Returns a dictionary of common helper functions for Jinja2 templates.
    """

    from python_utils.datetime_utils.common import current_date_time_string, current_date_string, \
        current_time_string
    return {
        'currentDateTime': current_date_time_string,
        'currentDate': current_date_string,
        'currentTime': current_time_string
    }


def compile_template(
        template: str,
        return_variables: bool = False,
        required_variables: Optional[Union[Set[str], List[str]]] = None
) -> Union[Template, Tuple[Template, Set[str]]]:
    """
    Compile a Jinja2 template string and optionally return variables found in it.
    Can also validate that required variables are present in the template.

    Args:
        template (str): Jinja2 template string
        return_variables (bool): If True, return tuple of (Template, variables_found)
        required_variables (Optional[Union[Set[str], List[str]]]): Set or list of variable
            names that must be present in the template. If provided, will raise
            TemplateValidationError if any required variables are missing.

    Returns:
        Template: Compiled Jinja2 Template object (if return_variables=False)
        Tuple[Template, Set[str]]: (Template, variables_found) if return_variables=True

    Raises:
        TemplateValidationError: If required_variables is provided and some required
            variables are not found in the template.

    Examples:
        >>> template_str = "Hello {{ name }}! You are {{ age }} years old."
        >>>
        >>> # Just compile the template
        >>> compiled = compile_template(template_str)
        >>> print(type(compiled))
        <class 'jinja2.environment.Template'>

        >>> # Get compiled template and variables
        >>> compiled, vars_found = compile_template(template_str, return_variables=True)
        >>> print(vars_found)
        {'name', 'age'}

        >>> # Validate required variables (success case)
        >>> compiled = compile_template(template_str, required_variables=['name', 'age'])
        >>> print(type(compiled))
        <class 'jinja2.environment.Template'>

        >>> # Validate required variables with return_variables
        >>> required_variables = {'name', 'age'}
        >>> compiled, vars_found = compile_template(
        ...     template_str,
        ...     return_variables=True,
        ... )
        >>> print(vars_found == required_variables)
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
    # Compile with ChainableUndefined so chained attribute access on
    # undefined variables (e.g., {{ notes.local_search_efficiency }})
    # silently renders empty instead of raising UndefinedError.
    _env = Environment(undefined=ChainableUndefined)
    jinja_template = _env.from_string(template)

    # Only parse template for variables if we need them
    if return_variables or required_variables is not None:
        env = Environment()
        ast = env.parse(template)
        variables_found = meta.find_undeclared_variables(ast)

        # Validate required variables if provided
        if required_variables is not None:
            required_set = set(required_variables) if not isinstance(required_variables, set) else required_variables
            missing_variables = required_set - variables_found

            if missing_variables:
                raise ValueError(
                    f"Missing required variables in template: {missing_variables}"
                )

        if return_variables:
            return jinja_template, variables_found

    return jinja_template


def extract_variables(template: str) -> Set[str]:
    """Extract variable names from a Jinja2 template string.

    Uses Jinja2's AST parser to find undeclared variables.
    Returns empty set for non-template strings or invalid syntax.

    Args:
        template: A Jinja2 template string.

    Returns:
        Set of variable names found in the template.

    Examples:
        >>> sorted(extract_variables("Hello {{ name }}!"))
        ['name']
        >>> sorted(extract_variables("{{ a }} and {{ b }}"))
        ['a', 'b']
        >>> sorted(extract_variables("No variables here"))
        []
    """
    try:
        env = Environment()
        ast = env.parse(template)
        return meta.find_undeclared_variables(ast)
    except Exception:
        return set()


def format_template(
        template: str,
        feed: Optional[Mapping[str, Any]] = None,
        post_process: Optional[Callable[[str], str]] = None,
        helpers: Optional[Mapping[str, Callable]] = None,
        use_builtin_common_helpers: bool = True,
        **default_feed
) -> str:
    """
    Renders a Jinja2 template string with provided context and optional built-in/common helpers.

    Args:
        template (str): The Jinja2 template string (with {{...}} or {%...%} placeholders).
        feed (Optional[Mapping[str, Any]]): A mapping of variables for the template context.
            These will be merged with any kwargs provided (with feed taking precedence).
        post_process (Optional[Callable[[str], str]]): A function to post-process the rendered
            string (e.g. unescaping HTML entities).
        helpers (Optional[Mapping[str, Callable]]): Additional custom helper functions (or
            “globals”) to make available in the template.
        use_builtin_common_helpers (bool): Whether to add default date/time helpers
            (e.g. currentDateTime). Defaults to True.
        **default_feed: Default feed. Any default values will be overwritten by values in `feed`.

    Returns:
        str: The rendered template with placeholders replaced by corresponding values.

    Examples:
        Basic variable substitution:
        >>> format_template("Hello, {{ name }}!", name="Alice")
        'Hello, Alice!'

        Numeric values:
        >>> format_template("You have {{ count }} new messages.", count=5)
        'You have 5 new messages.'

        Decimal values:
        >>> format_template("Temperature is {{ temp }} degrees.", temp=22.5)
        'Temperature is 22.5 degrees.'

        Conditional rendering:
        >>> format_template("{% if is_member %}Welcome, member!{% else %}Welcome, guest!{% endif %}", is_member=True)
        'Welcome, member!'
        >>> format_template("{% if is_member %}Welcome, member!{% else %}Welcome, guest!{% endif %}", is_member=False)
        'Welcome, guest!'

        Using currentDateTime helper:
        >>> bool(re.match(r'<CurrentDate>\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}</CurrentDate>',
        ...     format_template("<CurrentDate>{{ currentDateTime() }}</CurrentDate>")))
        True

        Using currentDateTime with formatting:
        >>> bool(re.match(r'<CurrentDate>\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}',
        ...     format_template("<CurrentDate>{{ currentDateTime('iso') }}</CurrentDate>")))
        True

        Using currentDate:
        >>> bool(re.match(r'^Date: \\d{4}-\\d{2}-\\d{2}$',
        ...     format_template("Date: {{ currentDate() }}")))
        True

        Using currentDate with a custom format:
        >>> bool(re.match(r'^Date: \\d{2}/\\d{2}/\\d{4}$',
        ...     format_template("Date: {{ currentDate('%m/%d/%Y') }}")))
        True

        Using currentTime:
        >>> bool(re.match(r'^Time: \\d{2}:\\d{2}:\\d{2}$',
        ...     format_template("Time: {{ currentTime() }}")))
        True

        Using currentTime with a custom format:
        >>> bool(re.match(r'^Time: \\d{2}:\\d{2} (AM|PM)$',
        ...     format_template("Time: {{ currentTime('%I:%M %p') }}")))
        True

        Using custom helpers:
        >>> custom_helpers = {"upper": lambda text: text.upper()}
        >>> format_template("{{ upper(name) }}", helpers=custom_helpers, name="john")
        'JOHN'

        Merging feed and kwargs (feed has precedence):
        >>> format_template("{{ name }} is {{ age }}", feed={"name": "Bob", "age": 30}, name="Alice")
        'Bob is 30'
        >>> format_template("{{ name }} is {{ age }}", feed={"age": 30}, name="Alice")
        'Alice is 30'

        Using pandas Series:
        >>> import pandas as pd
        >>> series = pd.Series({'name': 'Bob', 'age': 25})
        >>> format_template("Hello {{ name }}! You are {{ age }} years old.", feed=series)
        'Hello Bob! You are 25 years old.'

        Using pandas DataFrame row:
        >>> import pandas as pd
        >>> df = pd.DataFrame({'name': ['Alice', 'Bob'], 'age': [30, 25]})
        >>> row = df.iloc[0]
        >>> format_template("Hello {{ name }}! You are {{ age }} years old.", feed=row)
        'Hello Alice! You are 30 years old.'
    """
    # 1. Gather the context (merge kwargs + feed).
    context = dict_(default_feed)
    if feed is not None:
        context.update(feed)  # feed takes precedence

    # 2. Optionally add built-in helpers to the context
    if use_builtin_common_helpers:
        context.update(get_common_helpers())

    # 3. Optionally add custom helpers
    if helpers:
        context.update(helpers)

    # 4. Create and render the template
    jinja_template = compile_template(template)
    result = jinja_template.render(**context)

    # 5. Apply post-processing if provided
    if post_process:
        result = post_process(result)

    return result


def validate_table_and_compile_template(
        data_frame: Any,
        prompt: str,
        get_colnames: Optional[Callable[[Any], List[str]]] = None,
) -> Tuple[Template, Any, List[str], List[str]]:
    """
    Utility function to validate data frame columns against Jinja2 template variables
    and return compiled template with dataframe.

    Args:
        data_frame: Any data frame object (pandas, spark, etc.)
        prompt: Jinja2 template string
        get_colnames: Optional function to extract column names from data_frame.
                     If None, assumes data_frame has .columns attribute (like pandas)

    Returns:
        Tuple containing:
        - compiled Jinja2 Template object
        - original data frame
        - list of required variables found in template
        - list of missing columns (empty if all found)

    Raises:
        ValueError: If template compilation fails
    """

    # Extract Jinja2 variables from the template
    try:
        env = Environment()
        ast = env.parse(prompt)
        required_variables = list(meta.find_undeclared_variables(ast))
    except Exception as e:
        raise ValueError(f"Failed to parse Jinja2 template: {str(e)}")

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

    # Compile the Jinja2 template
    try:
        template = Template(prompt)
    except Exception as e:
        raise ValueError(f"Failed to compile Jinja2 template: {str(e)}")

    return template, data_frame, required_variables, missing_columns
