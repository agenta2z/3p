import copy
from itertools import product
from typing import (
    Any,
    Callable,
    Dict,
    Iterator,
    List,
    Mapping,
    Optional,
    TYPE_CHECKING,
    Union,
)

from attr import attrib, attrs
from rankevolve.src.utils.common_utils.key_helper import (
    create_3component_key,
    create_spaced_key,
    resolve_spaced_key_to_tuple,
)
from rankevolve.src.utils.common_utils.map_helper import get_by_spaced_key
from rankevolve.src.utils.io_utils.text_io import read_all_text_
from rankevolve.src.utils.string_utils.formatting.handlebars_format import (
    extract_variables as handlebars_extract_variables,
    format_template as handlebars_template_format,
)
from rankevolve.src.utils.string_utils.formatting.jinja2_format import (
    extract_variables as jinja2_extract_variables,
    format_template as jinjia_template_format,
)

if TYPE_CHECKING:
    from .variable_manager import VariableLoader


@attrs
class TemplateManager:
    """
    Template management system with hierarchical namespace and versioning support.

    TemplateManager provides flexible template resolution with:
    - Hierarchical namespaces (root_space/type/template_key)
    - Multi-level fallback for template lookup
    - Template versioning for deployment-level customization
    - Component/partial support with version combinations

    Attributes:
        default_template: Fallback template when no match is found.
        templates: Template source - either a directory path or a dict mapping.
        active_template_type: Active template type namespace (e.g., "main", "reflection").
            Can be overridden at call time via __call__(active_template_type=...).
        active_template_root_space: Active root namespace (e.g., "action_agent").
            Can be overridden at call time via __call__(active_template_root_space=...).
        template_version: Deployment-level version suffix for templates.
            See "Template Versioning" section below.

    Template Versioning (template_version):
        The `template_version` attribute is designed as a **construction-time, one-time
        decision** for selecting between different prompt variants at the deployment or
        session level. Unlike `active_template_type` and `active_template_root_space`
        which can be overridden per-call, `template_version` is intentionally NOT
        exposed in __call__() parameters.

        Use cases:
        - **Enterprise vs Consumer**: Different prompts for enterprise customers vs
          end consumers (e.g., template_version="enterprise" or "end_customers")
        - **A/B Testing**: Deploy different prompt versions to different user segments
        - **Regional Variants**: Localized prompts (e.g., template_version="apac")

        How it works:
        - When template_version="end_customers" and looking for "BrowseLink":
          1. First tries "BrowseLink.end_customers" (versioned)
          2. Falls back to "BrowseLink" (unversioned) if not found
        - The version suffix separator is configurable via `template_version_sep`

        Example:
            >>> # Enterprise deployment
            >>> manager_enterprise = TemplateManager(
            ...     templates="path/to/templates/",
            ...     template_version="enterprise"
            ... )
            >>>
            >>> # Consumer deployment
            >>> manager_consumer = TemplateManager(
            ...     templates="path/to/templates/",
            ...     template_version="end_customers"
            ... )
            >>>
            >>> # Or use switch() to create a variant
            >>> manager_consumer = manager_enterprise.switch(template_version="end_customers")

        To change version at runtime, use switch() to create a new TemplateManager instance
        with the desired version, rather than modifying the existing instance.

    Methods:
        __call__: Resolve and format a template by key.
        switch: Create a copy with different active_template_type, active_template_root_space,
                or template_version settings.
    """

    ARG_NAME_TEMPLATE_KEY = "template_key"
    ARG_NAME_ACTIVE_TEMPLATE_TYPE = "active_template_type"
    ARG_NAME_ACTIVE_TEMPLATE_ROOT_SPACE = "active_template_root_space"

    BUILTIN_FILE_PATTERNS = {
        jinjia_template_format: ["*.j2", "*.jinja2", "*.jinja"],
        handlebars_template_format: ["*.hbs", "*.handlebars"],
    }

    BUILTIN_VARIABLE_EXTRACTORS = {
        jinjia_template_format: jinja2_extract_variables,
        handlebars_template_format: handlebars_extract_variables,
    }

    default_template: str = attrib(default="")
    templates: Optional[Union[str, Mapping]] = attrib(default=None)
    active_template_type: Optional[str] = attrib(default="main")
    active_template_root_space: Optional[str] = attrib(default=None)
    template_encoding: str = attrib(default="utf-8")
    default_template_name: str = attrib(default="default")
    template_version: str = attrib(default="")
    template_version_sep: str = attrib(default=".")
    template_components_key: str = attrib(default="components")
    template_key_parts_sep: str = attrib(default="/")
    template_formatter: Callable = attrib(default=jinjia_template_format)
    component_version_field: str = attrib(default="version")
    component_content_field: str = attrib(default="content")
    template_file_patterns: Union[str, List[str], None] = attrib(default="default")
    predefined_variables: Optional[Union[bool, "VariableLoader", Mapping]] = attrib(
        default=None
    )
    enable_templated_feed: bool = attrib(default=False)
    template_variable_extractor: Union[str, Callable, None] = attrib(default="default")
    cross_space_root: Optional[str] = attrib(default=None)

    def __attrs_post_init__(self):
        """
        Post-initialization hook that loads templates from disk (if they're file paths)
        and possibly merges in template components.

        Raises:
            ValueError: if `template_components` is `True` or a string but `templates`
                        isn't a string, making path construction impossible.
        """
        # Store the original templates path before processing for VariableLoader
        self._original_templates_path = (
            self.templates if isinstance(self.templates, str) else None
        )

        # Resolve template_file_patterns
        if self.template_file_patterns == "default":
            self.template_file_patterns = self.BUILTIN_FILE_PATTERNS.get(
                self.template_formatter
            )
        elif not self.template_file_patterns:
            self.template_file_patterns = None

        # Resolve template_variable_extractor
        if self.template_variable_extractor == "default":
            self.template_variable_extractor = self.BUILTIN_VARIABLE_EXTRACTORS.get(
                self.template_formatter
            )
        elif not self.template_variable_extractor:
            self.template_variable_extractor = None

        # If a default_template is provided, read it from disk if it's a path;
        # otherwise treat it as raw text.
        if self.default_template:
            self.default_template = read_all_text_(
                self.default_template,
                encoding=self.template_encoding,
                allow_reading_from_folder=False,
            )

        # Load the main templates if set (could be a path or a dict).
        if self.templates:
            self.templates: Dict = read_all_text_(
                self.templates,
                encoding=self.template_encoding,
                keep_extension=False,
                key_sep=self.template_key_parts_sep,
                recursive_levels=-1,
                collect_subdir_files_in_one_mapping=True,
                version_parent_folders=self.template_components_key,
                file_patterns=self.template_file_patterns,
            )

            if isinstance(self.templates, str):
                self.default_template = self.templates
                self.templates = None
            elif isinstance(self.templates, Dict):
                # If there's a 'default' key, use it as the default_template unless already set.
                if self.default_template_name in self.templates:
                    if not self.default_template:
                        self.default_template = self.templates[
                            self.default_template_name
                        ]
                    del self.templates[self.default_template_name]

        if not self.default_template and not self.templates:
            raise ValueError("No templates were provided.")

        # Initialize predefined_variables handling
        self._variable_loader = None
        self._static_predefined_vars = None

        if self.predefined_variables is True:
            # Auto-create VariableLoader using the original templates path
            try:
                from .variable_manager import VariableLoader
            except ImportError:
                raise NotImplementedError(
                    "VariableLoader is not available in the migrated environment. "
                    "Pass predefined_variables as a dict or False instead."
                )
            if self._original_templates_path:
                config_kwargs = {}
                if self.cross_space_root:
                    from .variable_manager import VariableLoaderConfig
                    config_kwargs["config"] = VariableLoaderConfig(
                        cross_space_root=self.cross_space_root
                    )
                self._variable_loader = VariableLoader(
                    template_dir=self._original_templates_path,
                    **config_kwargs,
                )
                # Load cross-space YAML sidecar if available
                if self.cross_space_root:
                    from pathlib import Path as _Path
                    cross_root = _Path(self.cross_space_root)
                    for yaml_candidate in [
                        cross_root / ".variables.yaml",
                    ]:
                        if yaml_candidate.is_file():
                            self._variable_loader.load_yaml_sidecar(yaml_candidate)
            else:
                raise ValueError(
                    "predefined_variables=True requires templates to be a path string, "
                    "not a dict or other type"
                )
        elif (
            self.predefined_variables is not None
            and self.predefined_variables is not False
        ):
            # Check if it's a VariableLoader instance or a Mapping
            try:
                from .variable_manager import VariableLoader
            except ImportError:
                raise NotImplementedError(
                    "VariableLoader is not available in the migrated environment. "
                    "Pass predefined_variables as a dict or False instead."
                )
            if isinstance(self.predefined_variables, VariableLoader):
                self._variable_loader = self.predefined_variables
            elif isinstance(self.predefined_variables, Mapping):
                self._static_predefined_vars = dict(self.predefined_variables)
            else:
                raise ValueError(
                    f"predefined_variables must be True, False, None, a VariableLoader, "
                    f"or a Mapping, got {type(self.predefined_variables).__name__}"
                )

    def switch(
        self,
        active_template_type: str = None,
        active_template_root_space: str = None,
        template_version: str = None,
        default_template_name: str = None,
        predefined_variables: Optional[Union[bool, "VariableLoader", Mapping]] = None,
    ):
        _copy: TemplateManager = copy.copy(self)
        if active_template_type is not None:
            if not active_template_type:
                active_template_type = None
            _copy.active_template_type = active_template_type
        if active_template_root_space is not None:
            if not active_template_root_space:
                active_template_root_space = None
            _copy.active_template_root_space = active_template_root_space
        if template_version is not None:
            _copy.template_version = template_version
        if default_template_name is not None:
            _copy.default_template_name = default_template_name

        # Handle predefined_variables override
        if predefined_variables is not None:
            _copy.predefined_variables = predefined_variables
            # Re-initialize the loader based on the new value
            _copy._variable_loader = None
            _copy._static_predefined_vars = None

            if predefined_variables is True:
                try:
                    from .variable_manager import VariableLoader
                except ImportError:
                    raise NotImplementedError(
                        "VariableLoader is not available in the migrated environment. "
                        "Pass predefined_variables as a dict or False instead."
                    )
                if self._original_templates_path:
                    _copy._variable_loader = VariableLoader(
                        template_dir=self._original_templates_path
                    )
                else:
                    raise ValueError(
                        "predefined_variables=True requires templates to be a path string"
                    )
            elif predefined_variables is not False:
                try:
                    from .variable_manager import VariableLoader
                except ImportError:
                    raise NotImplementedError(
                        "VariableLoader is not available in the migrated environment. "
                        "Pass predefined_variables as a dict or False instead."
                    )
                if isinstance(predefined_variables, VariableLoader):
                    _copy._variable_loader = predefined_variables
                elif isinstance(predefined_variables, Mapping):
                    _copy._static_predefined_vars = dict(predefined_variables)
                else:
                    raise ValueError(
                        f"predefined_variables must be True, False, None, a VariableLoader, "
                        f"or a Mapping, got {type(predefined_variables).__name__}"
                    )

        return _copy

    def get_raw_template(
        self,
        template_key: str = None,
        active_template_type: str = None,
        active_template_root_space: str = None,
    ) -> Optional[str]:
        """
        Return raw template content before rendering.

        This method resolves the template using the same lookup logic as __call__(),
        but returns the raw template string without any variable substitution.

        Args:
            template_key: Template key to lookup (e.g., "action_agent/main/MyTemplate")
            active_template_type: Override active_template_type for this lookup
            active_template_root_space: Override active_template_root_space for this lookup

        Returns:
            Raw template string, or None if not found

        Example:
            >>> manager = TemplateManager(templates="/path/to/templates")
            >>> raw_content = manager.get_raw_template("action_agent/main/MyTemplate")
            >>> # raw_content contains "{{notes_mindset}} and {{user_input}}"
        """
        # Use provided overrides or fall back to instance defaults
        _active_template_type = (
            active_template_type
            if active_template_type is not None
            else self.active_template_type
        )
        _active_template_root_space = (
            active_template_root_space
            if active_template_root_space is not None
            else self.active_template_root_space
        )

        template = self.default_template

        def _resolve_template_space_key_with_root_space_and_type(main_space_key):
            return create_3component_key(
                main_key=main_space_key,
                root_space=_active_template_root_space,
                suffix=_active_template_type,
                sep=self.template_key_parts_sep,
            )

        def _try_get_template(main_space_key, item_key):
            resolved_space_key = _resolve_template_space_key_with_root_space_and_type(
                main_space_key
            )
            result, _ = self._try_versioned_and_unversioned_lookup(
                resolved_space_key, item_key
            )
            return result

        if self.templates:
            unresolved_template_space_key, template_name = resolve_spaced_key_to_tuple(
                key=template_key,
                sep=self.template_key_parts_sep,
                default_item_key=self.default_template_name,
            )

            template = _try_get_template(unresolved_template_space_key, template_name)

            # Fallback through parent spaces
            if template is None and unresolved_template_space_key is not None:
                temp_space_key = unresolved_template_space_key
                while (
                    template is None and self.template_key_parts_sep in temp_space_key
                ):
                    temp_space_key = temp_space_key[
                        : temp_space_key.rfind(self.template_key_parts_sep)
                    ]
                    template = _try_get_template(temp_space_key, template_name)

            # Fallback: remove unresolved space
            if template is None:
                template = _try_get_template(None, template_name)

            # Fallback: use default_template
            if template is None:
                template = self.default_template

        return template

    def _is_component_versioned(self, component_value: Any) -> bool:
        """
        Check if a component value is a versioned component (list of version dicts).

        Args:
            component_value: The component value to check

        Returns:
            True if the component is versioned, False otherwise
        """
        return (
            isinstance(component_value, list)
            and len(component_value) > 0
            and isinstance(component_value[0], dict)
            and self.component_version_field in component_value[0]
            and self.component_content_field in component_value[0]
        )

    def _separate_versioned_components(
        self, template_components: Mapping[str, Any]
    ) -> tuple[Dict[str, List[Dict[str, Any]]], Dict[str, Any]]:
        """
        Separate template components into versioned and non-versioned components.

        Args:
            template_components: Dictionary of template components to separate

        Returns:
            A tuple of (versioned_components, non_versioned_components)
        """
        versioned_components: Dict[str, List[Dict[str, Any]]] = {}
        non_versioned_components: Dict[str, Any] = {}

        for key, value in template_components.items():
            if self._is_component_versioned(value):
                versioned_components[key] = value
            else:
                non_versioned_components[key] = value

        return versioned_components, non_versioned_components

    @staticmethod
    def _format_version_combination(
        template: str,
        formatter: Callable,
        component_names: List[str],
        version_combination: tuple,
        non_versioned_components: Dict[str, Any],
        kwargs: Dict[str, Any],
        feed: Optional[Mapping],
        post_process: Optional[Callable[[str], str]],
        component_content_field: str,
    ) -> str:
        """
        Static helper to format a single version combination.

        This is a static method so it can be pickled for multiprocessing.

        Args:
            template: Template string to format
            formatter: Formatting function to use
            component_names: List of versioned component names
            version_combination: Tuple of version dictionaries for this combination
            non_versioned_components: Dictionary of non-versioned component values
            kwargs: Additional keyword arguments
            feed: Feed mapping for template formatting
            post_process: Optional post-processing function
            component_content_field: Field name to extract content from version dicts

        Returns:
            Formatted template string
        """
        version_kwargs = {}
        for i, component_name in enumerate(component_names):
            version_dict = version_combination[i]
            version_kwargs[component_name] = version_dict[component_content_field]

        all_kwargs = {
            **non_versioned_components,
            **version_kwargs,
            **kwargs,
        }

        return formatter(template, feed=feed, post_process=post_process, **all_kwargs)

    @staticmethod
    def _generate_all_version_combinations(
        template: str,
        formatter: Callable,
        versioned_components: Dict[str, List[Dict[str, Any]]],
        non_versioned_components: Dict[str, Any],
        kwargs: Dict[str, Any],
        feed: Optional[Mapping],
        post_process: Optional[Callable[[str], str]],
        component_content_field: str,
    ) -> Iterator[str]:
        """
        Static generator for all version combinations.

        This is a static method so it can be pickled for multiprocessing.

        Args:
            template: Template string to format
            formatter: Formatting function to use
            versioned_components: Dictionary mapping component names to version lists
            non_versioned_components: Dictionary of non-versioned component values
            kwargs: Additional keyword arguments
            feed: Feed mapping for template formatting
            post_process: Optional post-processing function
            component_content_field: Field name to extract content from version dicts

        Yields:
            Formatted template strings for all version combinations
        """
        component_names = list(versioned_components.keys())
        version_lists = [versioned_components[name] for name in component_names]

        for version_combination in product(*version_lists):
            yield TemplateManager._format_version_combination(
                template=template,
                formatter=formatter,
                component_names=component_names,
                version_combination=version_combination,
                non_versioned_components=non_versioned_components,
                kwargs=kwargs,
                feed=feed,
                post_process=post_process,
                component_content_field=component_content_field,
            )

    def _get_template_and_components_key(self, template_space_key, template_name):
        # Use get_by_spaced_key to lookup the template value
        template_value = get_by_spaced_key(
            d=self.templates,
            space_key=template_space_key,
            item_key=template_name,
            default_item_key=self.default_template_name,
        )

        # Construct components path using create_spaced_key
        # Only construct if template_space_key exists in templates
        if not template_space_key:
            components_path = self.template_components_key
        elif template_space_key not in self.templates:
            components_path = None
        else:
            components_path = create_spaced_key(
                main_key=self.template_components_key,
                root_space=template_space_key,
                sep=self.template_key_parts_sep,
            )
        if not components_path:
            components_path = None

        return template_value, components_path

    def _get_template_without_default_fallback(self, template_space_key, template_name):
        """
        Lookup template WITHOUT falling back to default_template_name.

        This is used during version-based lookup to check if a specific template
        exists before trying the default fallback.

        Args:
            template_space_key: Space key for the template lookup
            template_name: Specific template name to find

        Returns:
            Tuple of (template, components_key) or (None, None) if not found
        """
        # Use get_by_spaced_key WITHOUT default_item_key to avoid premature fallback
        template_value = get_by_spaced_key(
            d=self.templates,
            space_key=template_space_key,
            item_key=template_name,
            default_item_key=None,  # No default fallback
        )

        # Only construct components_path if template was actually found
        if template_value is None:
            return None, None

        # Construct components path (same logic as _get_template_and_components_key)
        if not template_space_key:
            components_path = self.template_components_key
        elif template_space_key not in self.templates:
            components_path = None
        else:
            components_path = create_spaced_key(
                main_key=self.template_components_key,
                root_space=template_space_key,
                sep=self.template_key_parts_sep,
            )
        if not components_path:
            components_path = None

        return template_value, components_path

    def _try_versioned_and_unversioned_lookup(self, space_key: str, template_name: str):
        """
        Try to lookup template with version suffix first, then without.

        Applies version suffix using template_version_sep (default '.').
        This method is used at every fallback level to ensure versioned templates
        take priority over unversioned ones.

        Args:
            space_key: Hierarchical namespace key (e.g., "root/action_agent/main")
            template_name: Template name to lookup (e.g., "BrowseLink" or "default")

        Returns:
            Tuple of (template, components_key) or (None, None) if not found

        Example:
            If template_version="end_customers", template_name="BrowseLink":
            1. First tries: "BrowseLink.end_customers" (specific check, no default fallback)
            2. Then tries: "BrowseLink" (specific check, no default fallback)
            3. Only if both fail, allows default_template_name fallback
        """
        # If no version is set, use original behavior with built-in default fallback
        if not self.template_version:
            return self._get_template_and_components_key(space_key, template_name)

        # Version is set - try versioned then unversioned for specific template
        versioned_name = (
            f"{template_name}{self.template_version_sep}{self.template_version}"
        )
        template, components_key = self._get_template_without_default_fallback(
            space_key, versioned_name
        )
        if template is not None:
            return template, components_key

        # Try unversioned specific template (without default fallback)
        template, components_key = self._get_template_without_default_fallback(
            space_key, template_name
        )
        if template is not None:
            return template, components_key

        # Both failed - try versioned default with built-in unversioned default fallback
        # _get_template_and_components_key will try "default.version" first,
        # then automatically fall back to "default" via default_item_key parameter
        versioned_default_name = f"{self.default_template_name}{self.template_version_sep}{self.template_version}"
        return self._get_template_and_components_key(space_key, versioned_default_name)

    def _resolve_templated_feed(self, merged_feed: dict) -> dict:
        """Resolve feed values that reference other feed values via template syntax.

        Delegates to the engine-independent resolve_templated_feed utility,
        using this TemplateManager's configured extractor and formatter.
        """
        extractor = self.template_variable_extractor
        formatter = self.template_formatter
        if extractor is None or formatter is None:
            return merged_feed

        from rankevolve.src.utils.string_utils.formatting.common import (
            resolve_templated_feed,
        )

        return resolve_templated_feed(
            merged_feed,
            extract_variables=extractor,
            render_template=lambda tmpl, ctx: formatter(tmpl, feed=ctx),
        )

    def __call__(
        self,
        template_key: Any = None,
        feed: Mapping = None,
        post_process: Callable[[str], str] = None,
        formatter: Callable = None,
        active_template_type: str = None,
        active_template_root_space: str = None,
        skip_predefined: bool = False,
        **kwargs,
    ) -> Union[str, Iterator[str]]:
        """
        Renders the template identified by `template_key`, or uses the default template if
        `template_key` is not found in `self.templates`.

        Args:
            template_key (Any):
                A key to look up in `self.templates`. If not found or if `self.templates` is `None`,
                uses `self.default_template`.
            feed (Mapping, optional):
                Key-value pairs to pass into the template formatter. Overridden by `kwargs`.
            post_process (Callable[[str], str], optional):
                A function applied to the rendered string after placeholder substitution.
            formatter (Callable, optional):
                Overrides `self.template_formatter` if provided. Must accept:
                `(template_str, feed=None, post_process=None, **kwargs) -> str`.
            skip_predefined (bool, optional):
                If True, skip predefined variable resolution for this call. Defaults to False.
                Useful for performance or when you want to bypass predefined variables.
            **kwargs:
                Additional key-value pairs to pass to the formatter (overriding `feed`).

        Returns:
            str: The fully rendered template.

        Raises:
            ValueError: If no formatter is available (neither `template_formatter` nor `formatter`).

        Examples:
            >>> import tempfile, os

            1) Simple usage with an in-memory default template + two named templates:
            >>> manager = TemplateManager(
            ...     default_template="Hello, {{name}}!",
            ...     templates={
            ...         "greet": "Greetings, {{name}}!",
            ...         "farewell": "Goodbye, {{name}}."
            ...     },
            ...     template_formatter=jinjia_template_format,
            ...     active_template_type=None,
            ... )
            >>> # Render a named template
            >>> manager("greet", name="Bob")
            'Greetings, Bob!'

            >>> # Template key not found => fall back to default
            >>> manager("unknown", name="Alice")
            'Hello, Alice!'

            >>> # Use 'farewell' with a feed dict and no extra kwargs
            >>> manager("farewell", feed={"name": "Carol"})
            'Goodbye, Carol.'

            >>> # Provide a simple post_process to uppercase the output
            >>> manager("greet", name="Diana", post_process=str.upper)
            'GREETINGS, DIANA!'

            2) Multiple templates as separate files in a temporary directory:
            >>> with tempfile.TemporaryDirectory() as tmp_dir:
            ...     greet_path = os.path.join(tmp_dir, "greet.j2")
            ...     farewell_path = os.path.join(tmp_dir, "farewell.j2")
            ...
            ...     # Write a 'greet' template file
            ...     with open(greet_path, "w", encoding="utf-8") as gf:
            ...         _ = gf.write("Greetings, {{name}} from greet.j2!")
            ...
            ...     # Write a 'farewell' template file
            ...     with open(farewell_path, "w", encoding="utf-8") as ff:
            ...         _ = ff.write("Goodbye, {{name}} from farewell.j2!")
            ...
            ...     # Now build a dictionary mapping each key to the file path
            ...     templates_dict = {
            ...         "main": {"greet": greet_path, "farewell": farewell_path},
            ...     }
            ...
            ...     manager_files = TemplateManager(
            ...         default_template="Hello, {{name}} from default in memory!",
            ...         templates=templates_dict,
            ...         template_formatter=jinjia_template_format
            ...     )
            ...
            ...     # Render the greet template
            ...     print(manager_files("greet", name="Ed"))
            ...     # Render the farewell template
            ...     print(manager_files("farewell", name="Ed"))
            ...     # Key not in templates => fallback to default
            ...     print(manager_files("unknown", name="Zoe"))
            Greetings, Ed from greet.j2!
            Goodbye, Ed from farewell.j2!
            Hello, Zoe from default in memory!

            3) Sub-key fallback to a "level default" key:
            >>> # If 'parent/childNonExistent' is requested but doesn't exist,
            >>> # the manager looks for 'parent/default' (by replacing the last portion with 'default').
            >>> manager2 = TemplateManager(
            ...     default_template="Global default: Hello, {{name}}!",
            ...     templates={
            ...         "parent/main": {
            ...             "default": "Parent default: Hello, {{name}}!", "childA": "Child A: Hello, {{name}}!"
            ...         },
            ...     },
            ...     template_formatter=jinjia_template_format
            ... )
            >>> manager2("parent/childA", name="Alice")
            'Child A: Hello, Alice!'
            >>> # 'childNonExistent' not found => fallback to 'parent/default' if it exists
            >>> manager2("parent/childNonExistent", name="Bob")
            'Parent default: Hello, Bob!'
            >>> # If no slash or parent's default is absent => fallback to global default
            >>> manager2("someKey", name="Carol")
            'Global default: Hello, Carol!'

            4) Template components usage:
            >>> # A "main" template referencing partials: e.g. "{{> header}} Hello, {{name}}! {{> footer}}"
            >>> # In this manager, we store partials under "main/components" -> { "header": "...", "footer": "..." }
            >>> manager3 = TemplateManager(
            ...     templates={
            ...         "default": "Header:\\n{{header}}\\nHello, {{name}}!\\nFooter:\\n{{footer}}",
            ...         "components": {
            ...             "header": "[[[ This is HEADER partial ]]]",
            ...             "footer": "[[[ This is FOOTER partial ]]]"
            ...         }
            ...     },
            ...     template_formatter=jinjia_template_format,
            ...     active_template_type=None
            ... )
            >>> # When calling manager3("main"), the code sees 'main/components' in manager3.templates
            >>> manager3(name="Dora")
            'Header:\\n[[[ This is HEADER partial ]]]\\nHello, Dora!\\nFooter:\\n[[[ This is FOOTER partial ]]]'

            5) Template components usage with partials in a subdirectory:
            >>> # Suppose we have a "main" template plus components stored in a 'components' folder
            >>> # like this:
            >>> # main/default.j2  -> "Header: {{header}} \\nHello, {{name}}!\\n Footer: {{footer}}"
            >>> # main/components/header.j2 -> "[[[ This is HEADER partial ]]]"
            >>> # main/components/footer.j2 -> "[[[ This is FOOTER partial ]]]"
            ...
            >>> with tempfile.TemporaryDirectory() as tmp_dir:
            ...     # Create a subfolder named "components"
            ...     main_dir = os.path.join(tmp_dir, "main")
            ...     comp_dir = os.path.join(main_dir, "components")
            ...     os.mkdir(main_dir)
            ...     os.mkdir(comp_dir)
            ...
            ...     main_file = os.path.join(main_dir, "default.j2")
            ...     header_file = os.path.join(comp_dir, "header.j2")
            ...     footer_file = os.path.join(comp_dir, "footer.j2")
            ...
            ...     # Write main template
            ...     with open(main_file, "w", encoding="utf-8") as m:
            ...         _ = m.write("Header: {{header}}\\nHello, {{name}}!\\nFooter: {{footer}}")
            ...
            ...     # Write partial files
            ...     with open(header_file, "w", encoding="utf-8") as hf:
            ...         _ = hf.write("[[[ HEADER partial ]]]")
            ...     with open(footer_file, "w", encoding="utf-8") as ff:
            ...         _ = ff.write("[[[ FOOTER partial ]]]")
            ...
            ...     manager_comp = TemplateManager(
            ...         templates=tmp_dir,
            ...         template_formatter=jinjia_template_format
            ...     )
            ...
            ...     # Render "main", automatically loading partials under "main/components"
            ...     print(manager_comp(name="Dora"))
            Header: [[[ HEADER partial ]]]
            Hello, Dora!
            Footer: [[[ FOOTER partial ]]]

            6) Template components at a deeper level:
            >>> # Suppose we have multiple directory levels, with "sub1/sub2/main.j2"
            >>> # and partial files in "sub1/sub2/components/header.j2", etc.
            >>> with tempfile.TemporaryDirectory() as tmp_dir:
            ...     sub2_dir = os.path.join(tmp_dir, 'root', "sub1", "sub2", 'special')
            ...     os.makedirs(sub2_dir)
            ...
            ...     default_file = os.path.join(sub2_dir, "default.j2")
            ...     with open(default_file, "w", encoding="utf-8") as mf:
            ...         _ = mf.write("Default. Header: {{header}}\\nHello, {{name}}!\\nFooter: {{footer}}")
            ...     non_default_file = os.path.join(sub2_dir, "non_default.j2")
            ...     with open(default_file, "w", encoding="utf-8") as mf:
            ...         _ = mf.write("None Default. Header: {{header}}\\nHello, {{name}}!\\nFooter: {{footer}}")
            ...
            ...     comp_dir = os.path.join(sub2_dir, "components")
            ...     os.mkdir(comp_dir)
            ...     header_file = os.path.join(comp_dir, "header.j2")
            ...     footer_file = os.path.join(comp_dir, "footer.j2")
            ...     with open(header_file, "w", encoding="utf-8") as hf:
            ...         _ = hf.write("[[[ Deeper HEADER partial ]]]")
            ...     with open(footer_file, "w", encoding="utf-8") as ff:
            ...         _ = ff.write("[[[ Deeper FOOTER partial ]]]")
            ...
            ...     # The manager is pointed at the top directory tmp_dir,
            ...     # and it will load 'sub1/sub2/main.j2' plus 'sub1/sub2/components/...'
            ...     # into a dictionary with keys 'sub1/sub2/main' and 'sub1/sub2/main/components'...
            ...     manager_deep = TemplateManager(
            ...         templates=tmp_dir,
            ...         template_formatter=jinjia_template_format,
            ...         active_template_root_space='root',
            ...         active_template_type='special'
            ...     )
            ...
            ...     # The effective template key might become "sub1/sub2/main"
            ...     # so the partials are under "sub1/sub2/main/components".
            ...     print(manager_deep("sub1/sub2/non_default", name="Eve"))
            None Default. Header: [[[ Deeper HEADER partial ]]]
            Hello, Eve!
            Footer: [[[ Deeper FOOTER partial ]]]

            7) Versioned components: automatically iterating over component versions
            >>> # When components have multiple versions (from version_parent_folders in read_all),
            >>> # TemplateManager automatically generates all version combinations.
            >>> #
            >>> # Folder structure:
            >>> # templates/
            >>> #   main/
            >>> #     default.j2  -> "Hello {{name}}! Header: {{header}}, Footer: {{footer}}"
            >>> #     components/
            >>> #       header/
            >>> #         v1.txt -> "=== HEADER V1 ==="
            >>> #         v2.txt -> "=== HEADER V2 ==="
            >>> #       footer/
            >>> #         v1.txt -> "--- footer v1 ---"
            >>> # Result will be a dict where header and footer are versioned:
            >>> # {
            >>> #   "main": {...},
            >>> #   "main/components": {
            >>> #     "header": [{"version": "v1", "content": "=== HEADER V1 ==="}, {"version": "v2", "content": "=== HEADER V2 ==="}],
            >>> #     "footer": [{"version": "v1", "content": "--- footer v1 ---"}]
            >>> #   }
            >>> # }
            >>> # The TemplateManager returns an iterator yielding all combinations:
            >>> # - header=v1, footer=v1
            >>> # - header=v2, footer=v1
            >>> with tempfile.TemporaryDirectory() as tmp_dir:
            ...     main_dir = os.path.join(tmp_dir, "main")
            ...     comp_dir = os.path.join(main_dir, "components")
            ...     header_dir = os.path.join(comp_dir, "header")
            ...     footer_dir = os.path.join(comp_dir, "footer")
            ...     os.makedirs(header_dir)
            ...     os.makedirs(footer_dir)
            ...
            ...     # Create template
            ...     with open(os.path.join(main_dir, "default.j2"), "w") as f:
            ...         _ = f.write("Hello {{name}}! Header: {{header}}, Footer: {{footer}}")
            ...
            ...     # Create version files
            ...     with open(os.path.join(header_dir, "v1.txt"), "w") as f:
            ...         _ = f.write("=== HEADER V1 ===")
            ...     with open(os.path.join(header_dir, "v2.txt"), "w") as f:
            ...         _ = f.write("=== HEADER V2 ===")
            ...     with open(os.path.join(header_dir, "v3.txt"), "w") as f:
            ...         _ = f.write("=== HEADER V3 ===")
            ...     with open(os.path.join(footer_dir, "v1.txt"), "w") as f:
            ...         _ = f.write("--- footer v1 ---")
            ...     with open(os.path.join(footer_dir, "v2.txt"), "w") as f:
            ...         _ = f.write("--- footer v2 ---")
            ...
            ...     manager = TemplateManager(
            ...         templates=tmp_dir,
            ...         template_formatter=jinjia_template_format
            ...     )
            ...
            ...     # Returns an iterator over all version combinations
            ...     results = list(manager("main", name="Alice"))
            ...     print(f"Generated {len(results)} versions")
            ...     for i, result in enumerate(results):
            ...         print(f"Version {i+1}: {result}")
            Generated 6 versions
            Version 1: Hello Alice! Header: === HEADER V1 ===, Footer: --- footer v1 ---
            Version 2: Hello Alice! Header: === HEADER V2 ===, Footer: --- footer v1 ---
            Version 3: Hello Alice! Header: === HEADER V3 ===, Footer: --- footer v1 ---
            Version 4: Hello Alice! Header: === HEADER V1 ===, Footer: --- footer v2 ---
            Version 5: Hello Alice! Header: === HEADER V2 ===, Footer: --- footer v2 ---
            Version 6: Hello Alice! Header: === HEADER V3 ===, Footer: --- footer v2 ---

            8) Realistic folder structure:
            >>> # action_agent/
            >>> #   main/
            >>> #     BrowseLink
            >>> #     Search
            >>> #     default
            >>> #   reflection/
            >>> #     BrowseLink
            >>> #     Search
            >>> # reflection/
            >>> #   default
            >>>
            >>> with tempfile.TemporaryDirectory() as tmp_dir:
            ...     import os
            ...     action_agent_dir = os.path.join(tmp_dir, "action_agent")
            ...     os.mkdir(action_agent_dir)
            ...     main_dir = os.path.join(action_agent_dir, "main")
            ...     refl_dir = os.path.join(action_agent_dir, "reflection")
            ...     os.mkdir(main_dir)
            ...     os.mkdir(refl_dir)
            ...
            ...     # Write some example templates in 'main'
            ...     browse_main_path = os.path.join(main_dir, "BrowseLink")
            ...     search_main_path = os.path.join(main_dir, "Search")
            ...     default_main_path = os.path.join(main_dir, "default")
            ...     with open(browse_main_path, "w", encoding="utf-8") as f:
            ...         _ = f.write("Main BrowseLink: Hello, {{name}}!")
            ...     with open(search_main_path, "w", encoding="utf-8") as f:
            ...         _ = f.write("Main Search: Hello, {{name}}!")
            ...     with open(default_main_path, "w", encoding="utf-8") as f:
            ...         _ = f.write("Main default: Hello, {{name}}!")
            ...
            ...     # Write some templates in 'reflection'
            ...     browse_refl_path = os.path.join(refl_dir, "BrowseLink")
            ...     search_refl_path = os.path.join(refl_dir, "Search")
            ...     with open(browse_refl_path, "w", encoding="utf-8") as f:
            ...         _ = f.write("Reflection BrowseLink: Hello, {{name}}!")
            ...     with open(search_refl_path, "w", encoding="utf-8") as f:
            ...         _ = f.write("Reflection Search: Hello, {{name}}!")
            ...
            ...     # And a fallback reflection/default at top level:
            ...     reflection_root_dir = os.path.join(tmp_dir, "reflection")
            ...     os.mkdir(reflection_root_dir)
            ...     default_refl_top = os.path.join(reflection_root_dir, "default")
            ...     with open(default_refl_top, "w", encoding="utf-8") as f:
            ...         _ = f.write("Reflection top-level default: Hello, {{name}}!")
            ...
            ...     # Create a TemplateManager pointed at tmp_dir
            ...     manager_action = TemplateManager(
            ...         templates=tmp_dir,
            ...         template_formatter=jinjia_template_format
            ...     )
            ...
            ...     # Now let's render some of these keys
            ...     print(manager_action("action_agent/BrowseLink", name="Alice"))
            ...     print(manager_action("action_agent/Search", name="Bob"))
            ...     # If "action_agent/Unknown" doesn't exist, fallback to reflection/default in that subfolder
            ...     print(manager_action("action_agent/Unknown", name="Zack"))
            ...
            ...     # Copy the manager and set the active type as 'reflection'
            ...     manager_reflection = manager_action.switch(active_template_type="reflection")
            ...     print(manager_reflection("action_agent/BrowseLink", name="Alice"))
            ...     print(manager_reflection("action_agent/Search", name="Bob"))
            ...     print(manager_reflection("action_agent/Unknown", name="Zack"))
            Main BrowseLink: Hello, Alice!
            Main Search: Hello, Bob!
            Main default: Hello, Zack!
            Reflection BrowseLink: Hello, Alice!
            Reflection Search: Hello, Bob!
            Reflection top-level default: Hello, Zack!

            9) Template versioning: version-based fallback at every hierarchical level
            >>> # When template_version is set (e.g., "end_customers"), the manager tries
            >>> # versioned templates first (e.g., "BrowseLink.end_customers") before falling
            >>> # back to unversioned templates (e.g., "BrowseLink") at EVERY fallback level.
            >>> #
            >>> # Fallback sequence with template_version="end_customers":
            >>> # 1. root/action_agent/main/BrowseLink.end_customers (versioned)
            >>> # 2. root/action_agent/main/BrowseLink (unversioned)
            >>> # 3. root/action_agent/main/default.end_customers (versioned default)
            >>> # 4. root/action_agent/main/default (unversioned default)
            >>> # 5-12. Continue with parent spaces, root removal, type removal, etc.
            >>> #       Always trying versioned before unversioned at each level
            >>> # 13. System default_template object
            >>> #
            >>> manager_versioned = TemplateManager(
            ...     default_template="System default: Hello, {{name}}!",
            ...     templates={
            ...         "action_agent/main": {
            ...             "BrowseLink.end_customers": "Customer BrowseLink: Welcome, {{name}}!",
            ...             "BrowseLink": "Standard BrowseLink: Hello, {{name}}!",
            ...             "Search": "Standard Search: Hello, {{name}}!",
            ...             "default.end_customers": "Customer default: Welcome, {{name}}!",
            ...             "default": "Standard default: Hello, {{name}}!",
            ...         },
            ...     },
            ...     template_formatter=jinjia_template_format,
            ...     template_version="end_customers",
            ...     template_version_sep=".",  # Default separator
            ...     active_template_root_space=None,
            ...     active_template_type="main",
            ... )
            >>> # BrowseLink with version - finds versioned template immediately
            >>> manager_versioned("action_agent/BrowseLink", name="Alice")
            'Customer BrowseLink: Welcome, Alice!'
            >>> # Search without version - falls back to unversioned (no versioned Search exists)
            >>> manager_versioned("action_agent/Search", name="Bob")
            'Standard Search: Hello, Bob!'
            >>> # NonExistent - tries NonExistent.end_customers, then NonExistent,
            >>> # then default.end_customers (found!)
            >>> manager_versioned("action_agent/NonExistent", name="Carol")
            'Customer default: Welcome, Carol!'
            >>> # With empty version, behaves like standard lookup (backward compatible)
            >>> manager_no_version = manager_versioned.switch(template_version="")
            >>> manager_no_version("action_agent/BrowseLink", name="Dave")
            'Standard BrowseLink: Hello, Dave!'
            >>> # Custom version separator: use underscore instead of dot
            >>> manager_underscore = TemplateManager(
            ...     templates={
            ...         "main": {
            ...             "template_v2": "Version 2: Hello, {{name}}!",
            ...             "template": "Standard: Hello, {{name}}!",
            ...         }
            ...     },
            ...     template_formatter=jinjia_template_format,
            ...     template_version="v2",
            ...     template_version_sep="_",  # Use underscore
            ...     active_template_type="main",
            ... )
            >>> manager_underscore("template", name="Eve")
            'Version 2: Hello, Eve!'
        """
        template = self.default_template
        template_components = None

        if active_template_type is None:
            active_template_type = self.active_template_type
        elif not active_template_type:
            active_template_type = None

        if active_template_root_space is None:
            active_template_root_space = self.active_template_root_space
        elif not active_template_root_space:
            active_template_root_space = None

        # Resolve predefined variables if enabled and not skipped
        predefined_vars = {}
        if not skip_predefined:
            if self._variable_loader is not None:
                # Get raw template first to scan for variable references
                raw_template = self.get_raw_template(
                    template_key=template_key,
                    active_template_type=active_template_type,
                    active_template_root_space=active_template_root_space,
                )
                if raw_template:
                    predefined_vars = self._variable_loader.resolve_from_template(
                        template_content=raw_template,
                        template_root_space=active_template_root_space or "",
                        template_type=active_template_type or "main",
                        version=self.template_version,
                    )
                # Also include YAML sidecar variables (loaded via load_yaml_sidecar).
                # These have lower priority than file-based resolved vars.
                yaml_vars = self._variable_loader.get_all_variables(
                    variable_root_space=active_template_root_space or "",
                    variable_type=active_template_type or "main",
                )
                if yaml_vars:
                    predefined_vars = {**yaml_vars, **predefined_vars}
            elif self._static_predefined_vars is not None:
                predefined_vars = dict(self._static_predefined_vars)

        # Merge: predefined (lowest) < feed < kwargs (highest)
        merged_kwargs = {**predefined_vars}
        if feed:
            merged_kwargs.update(feed)
        merged_kwargs.update(kwargs)
        # Replace kwargs with merged, and clear feed since it's now in merged_kwargs
        kwargs = merged_kwargs
        feed = None

        # Resolve templated feed values if enabled
        if self.enable_templated_feed:
            kwargs = self._resolve_templated_feed(kwargs)

        def _resolve_template_space_key_with_root_space_and_type(main_space_key):
            return create_3component_key(
                main_key=main_space_key,
                root_space=active_template_root_space,
                suffix=active_template_type,
                sep=self.template_key_parts_sep,
            )

        def _try_get_template(main_space_key, item_key):
            """Helper to resolve and get template with current state"""
            resolved_space_key = _resolve_template_space_key_with_root_space_and_type(
                main_space_key
            )
            return self._try_versioned_and_unversioned_lookup(
                resolved_space_key, item_key
            )

        if self.templates:
            # Step 1: Parse the template_key into (space_key, item_key) tuple
            # Examples:
            #   "space1/space2/MyTemplate" -> ("space1/space2", "MyTemplate")
            #   "MyTemplate" -> (None, "MyTemplate")
            #   None -> (None, "default")
            unresolved_template_space_key, template_name = resolve_spaced_key_to_tuple(
                key=template_key,
                sep=self.template_key_parts_sep,
                default_item_key=self.default_template_name,
            )

            # Step 2: Try to get the template with the requested name at the requested space
            # This constructs the full key as: root_space/unresolved_space/type/template_name
            template, template_components_key = _try_get_template(
                unresolved_template_space_key, template_name
            )

            # region Multi-level Fallback Mechanism
            # If the specific template is not found, we progressively fall back through
            # multiple levels to find a suitable default template. The fallback hierarchy is:
            #
            # 1. Requested space + default template (progressively moving to parent spaces)
            # 2. Root-space + type + default template
            # 3. Type + default template (removing root-space)
            # 4. Global default template (removing type)
            # 5. System default template object
            #
            # Example with template_key="action_agent/sub_space/BrowseLink",
            #          active_template_root_space="root", active_template_type="main":
            #
            # Lookup attempt 1: "root/action_agent/sub_space/main/BrowseLink" (FAILED)
            # Fallback 1: "root/action_agent/sub_space/main/default" (FAILED, move to parent)
            # Fallback 2: "root/action_agent/main/default" (FAILED, move to parent)
            # Fallback 3: "root/main/default" (FAILED, remove unresolved space)
            # Fallback 4: "main/default" (FAILED, remove root space)
            # Fallback 5: "default" (FAILED, remove type)
            # Fallback 6: Use system default_template object

            def _fallback_search_for_template():
                nonlocal \
                    template, \
                    unresolved_template_space_key, \
                    template_components_key, \
                    active_template_root_space, \
                    active_template_type
                if template is None:
                    # Fallback Level 1: Search in progressively higher parent spaces
                    # Example: "a/b/c" -> "a/b" -> "a" -> None
                    if unresolved_template_space_key is not None:
                        while (
                            template is None
                            and self.template_key_parts_sep
                            in unresolved_template_space_key
                        ):
                            # Remove the last segment to move to parent space
                            # E.g., "action_agent/sub_space" becomes "action_agent"
                            unresolved_template_space_key = (
                                unresolved_template_space_key[
                                    : unresolved_template_space_key.rfind(
                                        self.template_key_parts_sep
                                    )
                                ]
                            )
                            template, template_components_key = _try_get_template(
                                unresolved_template_space_key, template_name
                            )

                # Fallback Level 2: Try root-space + type + default
                # Remove the unresolved space component, but keep root_space and type
                # E.g., "root/action_agent/main/default" becomes "root/main/default"
                if template is None and unresolved_template_space_key is not None:
                    unresolved_template_space_key = None
                    template, template_components_key = _try_get_template(
                        unresolved_template_space_key, template_name
                    )

                # Fallback Level 3: Try type + default
                # Remove the root_space component, but keep type
                # E.g., "root/main/default" becomes "main/default"
                if template is None and active_template_root_space is not None:
                    active_template_root_space = None
                    template, template_components_key = _try_get_template(
                        unresolved_template_space_key, template_name
                    )

                # Fallback Level 4: Try global default
                # Remove the type component, leaving just the default name
                # E.g., "main/default" becomes "default"
                if template is None and active_template_type is not None:
                    active_template_type = None
                    template, template_components_key = _try_get_template(
                        unresolved_template_space_key, template_name
                    )

            _fallback_search_for_template()
            if template is None:
                # Switch to fallback looking for "default" template instead of the specific name
                template_name = self.default_template_name
                _fallback_search_for_template()

            # Fallback Level 5: Use system default template object
            # If nothing is found in the template store, use the configured default_template
            if template is None:
                template = self.default_template
                template_components_key = self.template_components_key
            # endregion

            template_components = self.templates.get(template_components_key, None)

        formatter = formatter or self.template_formatter
        if not formatter:
            raise ValueError(
                "No template formatter provided. Please set `template_formatter` or pass `formatter`."
            )

        if template_components:
            if not isinstance(template_components, Mapping):
                raise ValueError("'template_components' must be a mapping")

            # Separate versioned and non-versioned components
            versioned_components, non_versioned_components = (
                self._separate_versioned_components(template_components)
            )

            # If there are versioned components, return an iterator over all combinations
            if versioned_components:
                return TemplateManager._generate_all_version_combinations(
                    template=template,
                    formatter=formatter,
                    versioned_components=versioned_components,
                    non_versioned_components=non_versioned_components,
                    kwargs=kwargs,
                    feed=feed,
                    post_process=post_process,
                    component_content_field=self.component_content_field,
                )
            else:
                # No versioned components, return single result
                return formatter(
                    template,
                    feed=feed,
                    post_process=post_process,
                    **template_components,
                    **kwargs,
                )
        else:
            return formatter(template, feed=feed, post_process=post_process, **kwargs)
