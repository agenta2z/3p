import re
from collections.abc import Mapping
from typing import Callable, Dict, Optional, Tuple, Set, Union

# pybars is NOT available at Meta - wrap import in try/except
try:
    from pybars import Compiler
    PYBARS_AVAILABLE = True
except ImportError:
    PYBARS_AVAILABLE = False
    Compiler = None


def _current_date_time_string(options=None, format_str: str = None):
    from rankevolve.src.utils.datetime_utils.common import current_date_time_string
    return current_date_time_string(format_str)


def _current_date_string(options=None, format_str: str = None):
    from rankevolve.src.utils.datetime_utils.common import current_date_string
    return current_date_string(format_str)


def _current_time_string(options=None, format_str: str = None):
    from rankevolve.src.utils.datetime_utils.common import current_time_string
    return current_time_string(format_str)


def get_common_helpers() -> Dict[str, Callable]:
    """
    Returns a dictionary of common helper functions for Handlebars templates.

    Returns:
        Dict[str, Callable]: Dictionary mapping helper names to functions
    """
    return {
        'currentDateTime': _current_date_time_string,
        'currentDate': _current_date_string,
        'currentTime': _current_time_string
    }


def compile_template(
        template: str,
        return_variables: bool = False
) -> Union[object, Tuple[object, Set[str]]]:
    """
    Compile a Handlebars template string and optionally return variables found in it.

    Args:
        template (str): Handlebars template string
        return_variables (bool): If True, return tuple of (compiled_template, variables_found)

    Returns:
        object: Compiled Handlebars template object (if return_variables=False)
        Tuple[object, Set[str]]: (compiled_template, variables_found) if return_variables=True

    Raises:
        ImportError: If pybars is not available at Meta.

    Example:
        >>> template_str = "Hello {{name}}! You are {{age}} years old."
        >>>
        >>> # Just compile the template
        >>> compiled = compile_template(template_str)
        >>> callable(compiled)
        True

        >>> # Get compiled template and variables
        >>> compiled, vars_found = compile_template(template_str, return_variables=True)
        >>> sorted(vars_found)
        ['age', 'name']
    """
    if not PYBARS_AVAILABLE:
        raise ImportError(
            "pybars3 is required for Handlebars templates. "
            "This package is not available at Meta."
        )

    compiler = Compiler()
    handlebars_template = compiler.compile(template)

    if return_variables:
        variables_found = extract_variables(template)
        return handlebars_template, variables_found
    else:
        return handlebars_template


def extract_variables(template: str) -> Set[str]:
    """
    Extract variable names from a Handlebars template string.

    This function uses regex patterns to find Handlebars variable references
    and helper calls, extracting the variable names used.

    Args:
        template (str): Handlebars template string

    Returns:
        Set[str]: Set of variable names found in the template
    """
    variables = set()

    # Pattern for simple variables: {{variable}}
    simple_var_pattern = r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\s*\}\}'

    # Pattern for block helpers: {{#if variable}} or {{#each items}}
    block_helper_pattern = r'\{\{\s*#\s*\w+\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)'

    # Pattern for inline helpers with variables: {{helper variable}}
    inline_helper_pattern = r'\{\{\s*\w+\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)'

    # Find simple variables
    for match in re.finditer(simple_var_pattern, template):
        var_name = match.group(1).split('.')[0]  # Get root variable name
        # Skip built-in helpers
        if var_name not in ['currentDateTime', 'currentDate', 'currentTime']:
            variables.add(var_name)

    # Find variables in block helpers
    for match in re.finditer(block_helper_pattern, template):
        var_name = match.group(1).split('.')[0]
        variables.add(var_name)

    # Find variables in inline helpers (excluding the helper name itself)
    for match in re.finditer(inline_helper_pattern, template):
        var_name = match.group(1).split('.')[0]

    return variables

def format_template(
        template: str,
        feed: Optional[Mapping] = None,
        post_process: Optional[Callable[[str], str]] = None,
        helpers: Optional[Mapping[str, Callable]] = None,
        use_builtin_common_helpers: bool = True,
        **default_feed
) -> str:
    """
    Renders a Handlebars template string with provided context and helpers.

    This function compiles and renders a Handlebars template, supporting both
    built-in and custom helper functions. It can process variable context from
    multiple sources (feed mapping and kwargs) and supports post-processing of
    the rendered output.

    Args:
        template (str): The Handlebars template string.
        feed (Optional[Mapping]): A mapping of variables to include in the template context.
            These will be merged with any kwargs provided.
        post_process (Optional[Callable[[str], str]]): A function to process the rendered
            template before returning. Useful for unescaping HTML entities or other
            transformations.
        helpers (Optional[Mapping[str, Callable]]): Custom helper functions to register
            with the Handlebars compiler.
        use_builtin_common_helpers (bool): Whether to include built-in helpers like
            'currentDateTime'. Defaults to True.
        **default_feed: Default feed. Any default values will be overwritten by values in `feed`.

    Returns:
        str: The rendered template with all placeholders replaced.

    Raises:
        ImportError: If pybars is not available at Meta.

    Examples:
        Basic variable substitution:
        >>> format_template("Hello, {{name}}!", name="Alice")
        'Hello, Alice!'

        Numeric values:
        >>> format_template("You have {{count}} new messages.", count=5)
        'You have 5 new messages.'

        Decimal values:
        >>> format_template("Temperature is {{temp}} degrees.", temp=22.5)
        'Temperature is 22.5 degrees.'

        Conditional rendering:
        >>> format_template("{{#if is_member}}Welcome, member!{{else}}Welcome, guest!{{/if}}", is_member=True)
        'Welcome, member!'
        >>> format_template("{{#if is_member}}Welcome, member!{{else}}Welcome, guest!{{/if}}", is_member=False)
        'Welcome, guest!'

        Using the currentDateTime helper:
        >>> import re
        >>> bool(re.match(r'<CurrentDate>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}</CurrentDate>',
        ...     format_template("<CurrentDate>{{currentDateTime}}</CurrentDate>")))
        True

        Using currentDateTime with formatting:
        >>> bool(re.match(r'<CurrentDate>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}',
        ...     format_template("<CurrentDate>{{currentDateTime 'iso'}}</CurrentDate>")))
        True

        Using currentDate:
        >>> bool(re.match(r'^Date: \\d{4}-\\d{2}-\\d{2}$',
        ...     format_template("Date: {{currentDate}}")))
        True

        Using currentDate with a custom format:
        >>> bool(re.match(r'^Date: \\d{2}/\\d{2}/\\d{4}$',
        ...     format_template("Date: {{currentDate '%m/%d/%Y'}}")))
        True

        Using currentTime:
        >>> bool(re.match(r'^Time: \\d{2}:\\d{2}:\\d{2}$',
        ...     format_template("Time: {{currentTime}}")))
        True

        Using currentTime with a custom format:
        >>> bool(re.match(r'^Time: \\d{2}:\\d{2} (AM|PM)$',
        ...     format_template("Time: {{currentTime '%I:%M %p'}}")))
        True

        Using custom helpers:
        >>> format_template("{{upper name}}", helpers={"upper": lambda options, text: text.upper()}, name="john")
        'JOHN'

        Using both feed and default feed by named args (feed take precedence):
        >>> format_template("{{name}} is {{age}}", feed={"name": "Bob", "age": 30}, name="Alice")
        'Bob is 30'
        >>> format_template("{{name}} is {{age}}", feed={"age": 30}, name="Alice")
        'Alice is 30'
    """
    if not PYBARS_AVAILABLE:
        raise ImportError(
            "pybars3 is required for Handlebars templates. "
            "This package is not available at Meta."
        )

    # Compile the template with Handlebars
    compiler = Compiler()

    # Prepare helpers
    if use_builtin_common_helpers:
        all_helpers = get_common_helpers()
    else:
        all_helpers = {}

    if helpers:
        if isinstance(helpers, Mapping):
            all_helpers.update(helpers)
        else:
            raise ValueError(
                "'helpers' must be a mapping from helper names to callable HandleBar-compliant helper functions"
            )

    # Compile template
    handlebars_template = compiler.compile(template)

    # Prepare context by combining feed and kwargs

    context = default_feed
    if feed:
        if isinstance(feed, Mapping):
            context.update(feed)
        else:
            raise ValueError("'feed' must be a mapping")

    # Render template with context and helpers
    format_result = handlebars_template(context, helpers=all_helpers)

    # Apply post-processing if provided
    if post_process is not None:
        format_result = post_process(format_result)

    return format_result
