from collections import deque
from enum import StrEnum
import json
from typing import Any, Callable, Set

from python_utils.string_utils.xml_helpers import xml_format


class KeyValueStringFormat(StrEnum):
    XML = "xml"
    JSON = "json"
    YAML = "yaml"
    HTML = "html"
    TSV = "tsv"
    CSV = "csv"
    MARKDOWN = "markdown"
    INI = "ini"
    Other = "other"


def format_key_value(value: str, key: str, format_type: KeyValueStringFormat = KeyValueStringFormat.YAML) -> str:
    """
    Formats a key-value pair according to the specified format type.

    Args:
        key (str): The key or title.
        value (str): The value associated with the key.
        format_type (KeyValueStringFormat): The format type, which can be one of XML, JSON, YAML, HTML, TSV, CSV, MARKDOWN, or INI. Defaults to YAML.

    Returns:
        str: A formatted string based on the format type.

    Raises:
        ValueError: If an unsupported format type is provided.

    Examples:
        >>> format_key_value("Alice","user_name",KeyValueStringFormat.JSON)
        '{"user_name": "Alice"}'

        >>> format_key_value("Alice","user_name",KeyValueStringFormat.XML)
        '<user_name>Alice</user_name>'

        >>> format_key_value("Alice","user_name",KeyValueStringFormat.YAML)
        'user_name: Alice'

        >>> format_key_value("Alice","user_name",KeyValueStringFormat.HTML)
        '<div><strong>user_name</strong>: Alice</div>'

        >>> format_key_value("Alice","user_name",KeyValueStringFormat.CSV)
        'user_name,Alice'

        >>> format_key_value("Alice","user_name",KeyValueStringFormat.TSV)
        'user_name\\tAlice'

        >>> format_key_value("Alice","user_name",KeyValueStringFormat.MARKDOWN)
        '**user_name**: Alice'

        >>> format_key_value("Alice","user_name",KeyValueStringFormat.INI)
        'user_name = Alice'
    """
    if format_type == KeyValueStringFormat.XML:
        return xml_format(tag=key, content=value)
    elif format_type == KeyValueStringFormat.JSON:
        return json.dumps({key: value})
    elif format_type == KeyValueStringFormat.YAML:
        return f"{key}: {value}"
    elif format_type == KeyValueStringFormat.HTML:
        return f"<div><strong>{key}</strong>: {value}</div>"
    elif format_type == KeyValueStringFormat.CSV:
        return f"{key},{value}"
    elif format_type == KeyValueStringFormat.TSV:
        return f"{key}\t{value}"
    elif format_type == KeyValueStringFormat.MARKDOWN:
        return f"**{key}**: {value}"
    elif format_type == KeyValueStringFormat.INI:
        return f"{key} = {value}"
    else:
        raise ValueError("Unsupported format type. Choose a valid FormatType.")


def resolve_templated_feed(
    feed: dict[str, Any],
    extract_variables: Callable[[str], Set[str]],
    render_template: Callable[[str, dict], str],
) -> dict[str, Any]:
    """Resolve feed values that reference other feed keys via template placeholders.

    Uses DAG topological sort (Kahn's algorithm):
    1. Extract variable references from each string feed value
    2. Build dependency graph (edges: value -> referenced feed keys)
    3. Topological sort -- cycles detected as nodes with remaining in-degree
    4. Resolve in topological order using the pluggable renderer

    Engine-independent: works with Jinja2, Handlebars, or any template engine
    by accepting pluggable extract_variables and render_template callables.

    Args:
        feed: Dict of key -> value. String values may contain template placeholders.
        extract_variables: Extracts variable names from a template string.
        render_template: Renders a template string with a context dict.
            Should use the same environment as the main template for consistency.

    Returns:
        New dict with all inter-feed template references resolved.

    Raises:
        ValueError: If circular dependencies exist between feed values.

    Examples:
        >>> from jinja2 import Environment, meta, Template
        >>> def _extract(tmpl):
        ...     try:
        ...         ast = Environment().parse(tmpl)
        ...         return meta.find_undeclared_variables(ast)
        ...     except Exception:
        ...         return set()
        >>> def _render(tmpl, ctx):
        ...     return Template(tmpl).render(**ctx)

        Simple resolution:
        >>> resolve_templated_feed(
        ...     {"greeting": "Hello {{ name }}!", "name": "Alice"},
        ...     _extract, _render)
        {'name': 'Alice', 'greeting': 'Hello Alice!'}

        Chained resolution:
        >>> resolve_templated_feed(
        ...     {"a": "{{ b }}-{{ c }}", "b": "{{ c }}+1", "c": "base"},
        ...     _extract, _render)
        {'c': 'base', 'b': 'base+1', 'a': 'base+1-base'}

        Cycle detection:
        >>> resolve_templated_feed(
        ...     {"a": "{{ b }}", "b": "{{ a }}"},
        ...     _extract, _render)
        Traceback (most recent call last):
            ...
        ValueError: Circular dependency in templated feed values: {'a': ['b'], 'b': ['a']}.

        Non-string values are passed through:
        >>> result = resolve_templated_feed(
        ...     {"data": {"role": "engineer"}, "msg": "Role: {{ data.role }}"},
        ...     _extract, _render)
        >>> result["msg"]
        'Role: engineer'
    """
    feed_keys = set(feed.keys())
    resolved: dict[str, Any] = {}
    deps_map: dict[str, set[str]] = {}
    templates: dict[str, str] = {}

    # Phase 1: Classify -- extract dependencies, separate pure vs templated
    for key, value in feed.items():
        if not isinstance(value, str):
            resolved[key] = value
            continue
        referenced = extract_variables(value)
        feed_deps = referenced & feed_keys
        feed_deps.discard(key)
        if not feed_deps:
            # No inter-feed dependencies.  Still render through the
            # template engine so that Jinja2 control structures ({% if %})
            # and undefined-variable conditionals evaluate correctly
            # (e.g., {% if session_root_path %} hides when absent).
            if "{%" in value or "{{" in value:
                try:
                    resolved[key] = render_template(value, {**feed, **resolved})
                except Exception:
                    resolved[key] = value
            else:
                resolved[key] = value
        else:
            deps_map[key] = feed_deps
            templates[key] = value

    if not deps_map:
        return resolved

    # Phase 2: Build in-degree + reverse adjacency for Kahn's algorithm
    in_degree: dict[str, int] = {}
    dependents: dict[str, set[str]] = {}
    for key, deps in deps_map.items():
        unresolved = deps - set(resolved.keys())
        in_degree[key] = len(unresolved)
        for dep in deps:
            dependents.setdefault(dep, set()).add(key)

    # Phase 3: Seed queue with zero-in-degree nodes
    queue: deque[str] = deque(k for k, deg in in_degree.items() if deg == 0)

    # Phase 4: Process in topological order
    while queue:
        key = queue.popleft()
        rendered = render_template(templates[key], resolved)
        resolved[key] = rendered
        for dependent in dependents.get(key, set()):
            if dependent in in_degree:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

    # Phase 5: Cycle detection
    unresolved = {k for k, deg in in_degree.items() if deg > 0}
    if unresolved:
        cycle_info = {k: sorted(deps_map[k]) for k in sorted(unresolved)}
        raise ValueError(
            f"Circular dependency in templated feed values: {cycle_info}."
        )

    return resolved
