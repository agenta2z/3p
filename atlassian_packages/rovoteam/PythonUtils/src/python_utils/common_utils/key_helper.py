from typing import Any, Mapping, Optional, Sequence, Tuple


def create_spaced_key(
    main_key: str,
    root_space: Optional[str] = None,
    sep: str = "/",
) -> str:
    """
    Create a hierarchical key from 2 components: root_space + main_key.

    This function creates a 2-component key where root_space is optional.

    Args:
        main_key: The main key component (required)
        root_space: Optional root/namespace prefix
        sep: String to join components (default: "/")

    Returns:
        The combined key (main_key if no root_space, otherwise root_space + sep + main_key)

    Examples:
        >>> # Basic usage with root_space
        >>> create_spaced_key("components", "template_space")
        'template_space/components'

        >>> # No root_space, just main_key
        >>> create_spaced_key("components")
        'components'

        >>> # Custom separator
        >>> create_spaced_key("item", "namespace", sep=".")
        'namespace.item'

        >>> # Empty root_space treated as None
        >>> create_spaced_key("components", "")
        'components'
    """
    # Handle empty root_space as None
    if not root_space:
        return main_key

    return f"{root_space}{sep}{main_key}"


def resolve_spaced_key_to_tuple(
    key: Optional[Any],
    sep: str = "/",
    default_item_key: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Resolve a hierarchical key into a (space_key, item_key) tuple.

    This function handles three input formats:
    1. None -> Returns (None, default_item_key)
    2. Sequence (non-string) -> Converts to (space_key, item_key) tuple
    3. String -> Splits using separator to get (space_key, item_key)

    Args:
        key: The key to resolve (can be None, string, or sequence)
        sep: Separator for splitting string keys (default: "/")
        default_item_key: Default item key to use when key is None

    Returns:
        Tuple of (space_key, item_key) where space_key can be None

    Examples:
        >>> # None input with default
        >>> resolve_spaced_key_to_tuple(None, default_item_key="default")
        (None, 'default')

        >>> # String with separator
        >>> resolve_spaced_key_to_tuple("space1/space2/item")
        ('space1/space2', 'item')

        >>> # String without separator
        >>> resolve_spaced_key_to_tuple("item")
        (None, 'item')

        >>> # Sequence with 2 elements
        >>> resolve_spaced_key_to_tuple(("space", "item"))
        ('space', 'item')

        >>> # Sequence with more than 2 elements (joins all but last)
        >>> resolve_spaced_key_to_tuple(["space1", "space2", "item"])
        ('space1/space2', 'item')

        >>> # Custom separator
        >>> resolve_spaced_key_to_tuple("namespace.item", sep=".")
        ('namespace', 'item')
    """
    from python_utils.string_utils import split_

    # Case 1: None input
    if not key:
        return (None, default_item_key)

    # Case 2: Sequence (non-string) input
    if (not isinstance(key, str)) and isinstance(key, Sequence):
        key_parts = key
        if len(key_parts) > 2:
            # Join all but the last element as space_key
            space_key = sep.join(key_parts[:-1])
            item_key = key_parts[-1]
            return (space_key, item_key)
        elif len(key_parts) == 2:
            return (key_parts[0], key_parts[1])
        elif len(key_parts) == 1:
            return (None, key_parts[0])
        else:
            return (None, default_item_key)

    # Case 3: String input - split from right using split_
    key_parts = split_(
        key,
        sep=sep,
        maxsplit=1,
        remove_empty_split=True,
        rsplit_mode=True,
    )

    if len(key_parts) == 2:
        return (key_parts[0], key_parts[1])
    elif len(key_parts) == 1:
        return (None, key_parts[0])
    else:
        return (None, default_item_key)


def create_3component_key(
    main_key: Optional[str],
    root_space: Optional[str] = None,
    suffix: Optional[str] = None,
    sep: str = "/",
) -> Optional[str]:
    """
    Create a hierarchical key from up to 3 components: root_space + main_key + suffix.

    This function implements a 3-component hierarchical key mechanism where each component
    is optional. The resulting key combines these components with a separator.

    Args:
        main_key: The middle component, can be multi-level (e.g., "sub1/sub2/action")
        root_space: Optional root/base level prefix
        suffix: Optional type/variant suffix
        sep: String to join components (default: "/")

    Returns:
        The combined hierarchical key, or None if all components are None/empty

    Component Structure:
        [root_space] / [main_key] / [suffix]
             ↓            ↓            ↓
        Component 1  Component 2  Component 3
        (optional)   (optional,   (optional)
                     multi-level)

    Examples:
        >>> # All three components
        >>> create_3component_key("action_agent", "root", "main")
        'root/action_agent/main'

        >>> # Two components: root + key
        >>> create_3component_key("action_agent", root_space="root")
        'root/action_agent'

        >>> # Two components: key + suffix
        >>> create_3component_key("action_agent", suffix="main")
        'action_agent/main'

        >>> # One component: just key
        >>> create_3component_key("action_agent")
        'action_agent'

        >>> # One component: just root
        >>> create_3component_key(None, root_space="root")
        'root'

        >>> # One component: just suffix
        >>> create_3component_key(None, suffix="main")
        'main'

        >>> # Multi-level middle component
        >>> create_3component_key("sub1/sub2/action", "root", "main")
        'root/sub1/sub2/action/main'

        >>> # All None/empty
        >>> create_3component_key(None)

        >>> # Custom separator
        >>> create_3component_key("action_agent", "root", "main", sep=".")
        'root.action_agent.main'

        >>> # Empty strings treated as None
        >>> create_3component_key("", root_space="", suffix="")

        >>> # Only root and suffix (skipping middle)
        >>> create_3component_key(None, root_space="root", suffix="main")
        'root/main'
    """
    # When main_key is provided
    if main_key:
        # Build: root_space + main_key + suffix
        if root_space:
            result_key = root_space + sep + main_key
        else:
            result_key = main_key

        if suffix:
            result_key = result_key + sep + suffix

        return result_key

    # When main_key is NOT provided
    else:
        # Build: root_space + suffix (skipping middle component)
        if root_space:
            result_key = root_space
        else:
            result_key = None

        if result_key:
            if suffix:
                result_key = result_key + sep + suffix
        else:
            if suffix:
                result_key = suffix

        return result_key
