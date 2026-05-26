import copy
import enum
import os
from itertools import product
from pathlib import Path
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
from python_utils.common_utils.key_helper import (
    create_3component_key,
    create_spaced_key,
    resolve_spaced_key_to_tuple,
)
from python_utils.common_utils.map_helper import get_by_spaced_key
from python_utils.io_utils.text_io import read_all_text_
from python_utils.string_utils.formatting.handlebars_format import (
    extract_variables as handlebars_extract_variables,
    format_template as handlebars_template_format,
)
from python_utils.string_utils.formatting.jinja2_format import (
    extract_variables as jinja2_extract_variables,
    format_template as jinjia_template_format,
)

if TYPE_CHECKING:
    from .variable_manager import VariableLoader


# Extensions checked when resolving variable files (priority order).
_VARIABLE_FILE_EXTENSIONS: tuple = (".jinja2", ".jinja", ".j2", ".hbs", ".txt", "")


def _find_in_variable_folder(folder: Path, name: Optional[str]) -> Optional[Path]:
    """Look up ``<name>.<ext>`` or ``.config.yaml[<name>] -> <value>.<ext>``
    inside a single variable folder.

    Mirrors :meth:`FileBasedVariableManager._find_in_variable_folder` but as
    a standalone helper used by the simple, no-VariableLoader path of
    :meth:`TemplateManager.load_variable`.

    Resolution order:
      1. ``<folder>/<name><ext>``        (direct file)
      2. ``<folder>/.config.yaml[<name>] -> <folder>/<value><ext>``  (alias map)

    No default fallback (caller's responsibility -- e.g., Pass 2 calls this
    helper with ``name="default"``).

    Returns ``None`` if ``name`` is empty, the folder does not exist, or no
    matching file is found.
    """
    if not name or not folder.is_dir():
        return None

    # 1. Direct file <name>.<ext>
    for ext in _VARIABLE_FILE_EXTENSIONS:
        direct_path = folder / f"{name}{ext}"
        if direct_path.is_file():
            return direct_path

    # 2. .config.yaml alias map
    config_file = folder / ".config.yaml"
    if config_file.is_file():
        try:
            import yaml

            data = yaml.safe_load(config_file.read_text(encoding="utf-8"))
        except Exception:
            data = None
        if isinstance(data, dict) and data.get(name) is not None:
            alias = str(data[name])
            # Path-traversal guard: alias must be a bare filename stem,
            # not a relative path like "../../etc/passwd".
            if "/" not in alias and "\\" not in alias:
                for ext in _VARIABLE_FILE_EXTENSIONS:
                    alias_path = folder / f"{alias}{ext}"
                    if alias_path.is_file():
                        return alias_path

    return None


def _set_nested_key(
    target: dict,
    key: str,
    value: Any,
    overwrite: bool = True,
    strict: bool = False,
) -> None:
    """Canonical helper to assign ``value`` into ``target`` under ``key``,
    auto-nesting dotted keys into nested dicts.

    A flat key (``"foo"``) is stored as ``target["foo"] = value``.
    A dotted key (``"foo.bar.baz"``) is stored as
    ``target["foo"]["bar"]["baz"] = value``, creating intermediate dicts as needed.

    This is the single source of truth for translating dotted-key variable
    names (e.g. ``context.user_request_with_task_preamble``) into the nested
    structure that Jinja2's attribute access (``{{ context.user_request_with_task_preamble }}``)
    can resolve. All call sites in this module (``load_variables``,
    ``__call__`` predefined-vars merge, cross-root fallback mechanisms) MUST
    use this helper to keep dotted-key semantics consistent.

    Args:
        target: The dict to mutate.
        key: Variable name. May be flat (``"foo"``) or dotted (``"a.b.c"``).
        value: Value to assign at the final segment.
        overwrite: If ``True`` (default), replace any existing value at the
            final segment. If ``False``, only set when the final segment is
            absent (used by lower-priority fallback sources like sibling-root
            YAML sidecars).
        strict: If ``True``, raise ``AssertionError`` when a dotted key would
            shadow a non-dict intermediate segment (used by ``load_variables``
            where caller mixing flat+nested keys with shared prefixes is a
            programming error). If ``False`` (default), silently replace the
            non-dict intermediate with a fresh dict so the assignment succeeds.
    """
    if "." not in key:
        if overwrite or key not in target:
            target[key] = value
        return
    parts = key.split(".")
    d = target
    for part in parts[:-1]:
        nxt = d.get(part)
        if not isinstance(nxt, dict):
            if strict and nxt is not None:
                raise AssertionError(
                    f"_set_nested_key: cannot nest key {key!r}; segment "
                    f"{part!r} is bound to a non-dict ({type(nxt).__name__}). "
                    f"Don't mix flat and nested keys that share a prefix."
                )
            nxt = {}
            d[part] = nxt
        d = nxt
    last = parts[-1]
    if overwrite or last not in d:
        d[last] = value


class TemplateRootPriority(enum.Enum):
    """Priority when adding a template root to an existing TemplateManager.

    Used with :meth:`TemplateManager.add_template_root` to control how
    templates from the new root are merged with existing templates.
    """

    LOWEST = "lowest"  # Fill in missing keys only (default/fallback templates)
    HIGHEST = "highest"  # Override existing keys (forced overrides)


class _OriginTaggedStr(str):
    """A string that remembers which template root it came from.

    Used for variable isolation in multi-root TemplateManager: each template
    carries its origin root path so the correct VariableLoader is selected.

    WARNING: String operations (strip, +, slicing, f-strings) return plain str,
    silently losing origin info. Only use this for values that pass through
    lookup chains without transformation (which the current code does).
    """

    __slots__ = ("_origin_root",)

    def __new__(cls, value, origin_root=None):
        instance = super().__new__(cls, value)
        instance._origin_root = origin_root
        return instance

    def __reduce__(self):
        return (_OriginTaggedStr, (str(self), self._origin_root))


@attrs
class TemplateManager:
    """
    Template management system with hierarchical namespace and versioning support.

    TemplateManager provides flexible template resolution with:
    - Hierarchical namespaces (root_space/type/template_key)
    - Multi-level fallback for template lookup
    - Multi-root support with first-write-wins priority and variable isolation
    - Template versioning for deployment-level customization
    - Component/partial support with version combinations

    Attributes:
        default_template: Fallback template when no match is found.
        templates: Template source - a directory path, a dict mapping, or a
            **list** of these for multi-root overlay. When a list is provided,
            sources are deep-merged with first-write-wins priority: earlier
            entries (overrides) take precedence over later entries (defaults).
            Each template remembers its origin root for variable isolation.
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

    Multi-Root Overlay (templates as list):
        Pass a list of template sources to ``templates`` for layered resolution.
        Templates are deep-merged with first-write-wins priority, and each
        template's origin root is tracked for variable isolation.

        Example:
            >>> manager = TemplateManager(
            ...     templates=[
            ...         "/path/to/custom_templates",   # checked first (overrides)
            ...         "/path/to/default_templates",   # checked second (base)
            ...     ],
            ...     predefined_variables=True,
            ... )
            >>> # If custom_templates has "agent/main/BrowseLink" but not
            >>> # "agent/main/Search", BrowseLink comes from custom and
            >>> # Search comes from default — each using their own _variables/.

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
    templates: Optional[Union[str, Mapping, List[Union[str, Mapping]]]] = attrib(
        default=None
    )
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
    default_template_key: str = attrib(default="")
    # When True (and ``predefined_variables=True``), variable resolution at
    # render time falls back across ALL roots' VariableLoaders in priority
    # order: origin root's loader is highest priority; remaining loaders
    # iterated in ``_original_templates_paths`` order fill keys not resolved
    # by origin. When False (default), each template's variables are resolved
    # ONLY by the loader for its origin root (strict per-root isolation,
    # preserved for backward compatibility). The flag has no effect when
    # ``predefined_variables=False`` or when ``predefined_variables`` is a
    # static Mapping/VariableLoader (those code paths don't use per-root
    # loaders). See Refactor 17.
    cross_root_variable_lookup: bool = attrib(default=False)

    # Internal tracking for idempotent add_template_root calls
    _injected_roots: set = attrib(factory=set, init=False, repr=False)

    def __attrs_post_init__(self):
        """
        Post-initialization hook that loads templates from disk (if they're file paths)
        and possibly merges in template components.

        Raises:
            ValueError: if `template_components` is `True` or a string but `templates`
                        isn't a string, making path construction impossible.
        """
        # Smart path resolution: if templates is a relative path that doesn't
        # exist, try resolving via PROMPT_TEMPLATES_ROOT env var.
        if (
            self.templates is not None
            and isinstance(self.templates, str)
            and not Path(self.templates).is_absolute()
            and not Path(self.templates).is_dir()
        ):
            env_root = os.environ.get("PROMPT_TEMPLATES_ROOT", "")
            if env_root:
                resolved = Path(env_root) / self.templates
                if resolved.is_dir():
                    self.templates = str(resolved.resolve())

        # Normalize templates into a list for uniform processing.
        # Accepts: str, Mapping, List[Union[str, Mapping]], or None.
        if self.templates is not None and not isinstance(self.templates, list):
            templates_sources = [self.templates]
        else:
            templates_sources = self.templates or []

        # Store original path strings for VariableLoader initialization
        self._original_templates_paths: List[str] = [
            src for src in templates_sources if isinstance(src, str)
        ]
        self._original_templates_path: Optional[str] = (
            self._original_templates_paths[0]
            if self._original_templates_paths
            else None
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

        # Load each template source and deep-merge with first-write-wins priority.
        # Earlier sources (overrides) take priority over later sources (defaults).
        merged_templates: Dict = {}
        for source in templates_sources:
            loaded = read_all_text_(
                source,
                encoding=self.template_encoding,
                keep_extension=False,
                key_sep=self.template_key_parts_sep,
                recursive_levels=-1,
                collect_subdir_files_in_one_mapping=True,
                version_parent_folders=self.template_components_key,
                file_patterns=self.template_file_patterns,
            )
            if isinstance(loaded, str):
                # Single file resolved to text — use as default_template
                if not self.default_template:
                    self.default_template = loaded
            elif isinstance(loaded, dict):
                origin_root = source if isinstance(source, str) else None
                for space_key, space_value in loaded.items():
                    if space_key not in merged_templates:
                        # First source to claim this space key wins
                        if origin_root and isinstance(space_value, dict):
                            merged_templates[space_key] = {
                                k: (
                                    _OriginTaggedStr(v, origin_root=origin_root)
                                    if isinstance(v, str)
                                    else v
                                )
                                for k, v in space_value.items()
                            }
                        else:
                            merged_templates[space_key] = space_value
                    elif isinstance(merged_templates[space_key], dict) and isinstance(
                        space_value, dict
                    ):
                        # Deep merge: fill in missing template keys from
                        # lower-priority source
                        for tmpl_name, tmpl_content in space_value.items():
                            if tmpl_name not in merged_templates[space_key]:
                                if origin_root and isinstance(tmpl_content, str):
                                    merged_templates[space_key][tmpl_name] = (
                                        _OriginTaggedStr(
                                            tmpl_content, origin_root=origin_root
                                        )
                                    )
                                else:
                                    merged_templates[space_key][tmpl_name] = (
                                        tmpl_content
                                    )

        self.templates = merged_templates if merged_templates else None

        # Extract default template from merged dict
        if self.templates and isinstance(self.templates, dict):
            if self.default_template_name in self.templates:
                if not self.default_template:
                    self.default_template = self.templates[
                        self.default_template_name
                    ]
                del self.templates[self.default_template_name]

        if not self.default_template and not self.templates:
            raise ValueError("No templates were provided.")

        # Initialize FileSpaceManager for variable cascade resolution.
        # This replaces the inline cascade + _find_in_variable_folder duplication.
        # Only created when filesystem roots exist (not for in-memory dict templates).
        from python_utils.common_objects.file_space import FileSpaceManager

        self._file_space = FileSpaceManager(
            roots=self._original_templates_paths,
            reserved_subfolder_canonical="variables",
            reserved_subfolder_prefixes=("_", "."),
            file_extensions=_VARIABLE_FILE_EXTENSIONS,
        ) if self._original_templates_paths else None

        # Initialize predefined_variables handling
        self._variable_loader = None
        self._variable_loaders_by_root: Dict = {}
        self._static_predefined_vars = None

        # Auto-init variable loaders whenever template roots contain _variables/
        # or .variables.yaml, regardless of predefined_variables flag.
        # This enables composition ({{ X }} refs inside variable files) via
        # load_variables() without requiring predefined_variables=True.
        # Loader creation is cheap (no I/O until queried).
        self._init_variable_loaders()
        if self.predefined_variables is True:
            pass  # loaders already initialized above
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

    def _add_variable_loader_for_root(self, tmpl_path: str) -> None:
        """Create and register a VariableLoader for a single root path.

        Skips silently if the root has no ``_variables/`` directory or
        ``.variables.yaml`` sidecar.
        """
        from pathlib import Path as _Path

        has_vars_dir = (_Path(tmpl_path) / "_variables").is_dir()
        has_vars_yaml = (_Path(tmpl_path) / ".variables.yaml").is_file()
        if not has_vars_dir and not has_vars_yaml:
            return

        try:
            from .variable_manager import VariableLoader
        except ImportError:
            return  # VariableLoader not available — skip silently

        config_kwargs = {}
        if self.cross_space_root:
            from .variable_manager import VariableLoaderConfig

            config_kwargs["config"] = VariableLoaderConfig(
                cross_space_root=self.cross_space_root
            )
        loader = VariableLoader(template_dir=tmpl_path, **config_kwargs)
        root_yaml = _Path(tmpl_path) / ".variables.yaml"
        if root_yaml.is_file():
            loader.load_yaml_sidecar(root_yaml)
        if self.cross_space_root:
            cross_yaml = _Path(self.cross_space_root) / ".variables.yaml"
            if cross_yaml.is_file():
                loader.load_yaml_sidecar(cross_yaml)
        self._variable_loaders_by_root[tmpl_path] = loader

    def _init_variable_loaders(self):
        """Build per-root VariableLoaders from _original_templates_paths.

        Creates one VariableLoader per template root that has a ``_variables/``
        directory or a ``.variables.yaml`` sidecar.  Each loader is isolated to
        its own root, with an optional shared ``cross_space_root`` fallback.

        Sets ``_variable_loaders_by_root`` (origin-keyed dict) and
        ``_variable_loader`` (backward-compat reference to the first loader).
        """
        try:
            from .variable_manager import VariableLoader  # noqa: F401
        except ImportError:
            raise NotImplementedError(
                "VariableLoader is not available in the migrated environment. "
                "Pass predefined_variables as a dict or False instead."
            )

        self._variable_loaders_by_root = {}

        for tmpl_path in self._original_templates_paths:
            self._add_variable_loader_for_root(tmpl_path)

        # Backward compat: _variable_loader points to the first loader
        self._variable_loader = (
            next(iter(self._variable_loaders_by_root.values()), None)
            if self._variable_loaders_by_root
            else None
        )

        if not self._variable_loaders_by_root and not self._original_templates_paths:
            raise ValueError(
                "predefined_variables=True requires templates to be a path string, "
                "not a dict or other type"
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
            _copy._variable_loaders_by_root = {}
            _copy._static_predefined_vars = None

            if predefined_variables is True:
                _copy._init_variable_loaders()
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

    @property
    def template_roots(self) -> List[str]:
        """Return a copy of the original template source paths (read-only)."""
        return list(self._original_templates_paths)

    def _find_version_only_across_roots(
        self,
        var_name: str,
        version: str,
        root_space: str,
        type_: str,
    ) -> Optional[str]:
        """Cross-root Pass-1 (version-only) variable search.

        Iterates ``_variable_loaders_by_root`` entries in
        ``_original_templates_paths`` priority order. For each loader,
        searches its cascade for an EXACT version match — never default
        fallback. Returns the file content of the first hit, or None if
        no root has the variable defined at the requested version.

        Used by ``cross_root_variable_lookup=True`` to make exact-version
        matches in higher-priority roots win over default-fallback
        matches in the origin root.

        Note: this method does NOT use ``master_version`` — it is called
        from ``__call__()`` (predefined-variable auto-discovery) which
        passes ``self.template_version``, not a per-inferencer master.
        The ``master_version`` threading happens at the ``load_variables()``
        → ``_cascade_load_variable_path()`` layer instead.
        """
        if not version or not self._variable_loaders_by_root:
            return None
        for tmpl_path in self._original_templates_paths:
            loader = self._variable_loaders_by_root.get(tmpl_path)
            if loader is None:
                continue
            cascade_paths = loader._get_cascade_paths(
                variable_root_space=root_space,
                variable_type=type_,
            )
            possible_paths = loader._generate_underscore_splits(var_name)
            for cascade_path in cascade_paths:
                for path_variant in possible_paths:
                    folder = cascade_path / path_variant
                    hit = self._file_space.find_in_folder(folder, version) if self._file_space else None
                    if hit is not None:
                        try:
                            return hit.read_text(encoding=self.template_encoding)
                        except Exception:
                            continue
        return None

    def _cascade_load_variable_path(
        self,
        var_name: str,
        version: str,
        root_space: str,
        tmpl_type: str,
        master_version: Optional[str] = None,
    ) -> "Tuple[Optional[str], Optional[Path]]":
        """Resolve one variable using cascading paths across all roots.

        Delegates to ``FileSpaceManager.resolve()`` for cascade + version +
        master_version resolution, then returns ``(content, file_path)``
        or ``(None, None)`` if not found.
        """
        if self._file_space is None:
            return (None, None)
        resolved = self._file_space.resolve(
            space=root_space,
            type_=tmpl_type,
            name=var_name,
            version=version,
            master_version=master_version,
        )
        if resolved is None:
            return (None, None)
        return (resolved.read(), resolved.path)

        return (None, None)

    def _cascade_load_variable(
        self,
        var_name: str,
        version: str,
        root_space: str,
        tmpl_type: str,
        master_version: Optional[str] = None,
    ) -> Optional[str]:
        """Backward-compatible wrapper. Returns raw file content WITHOUT
        composition. Use ``load_variables()`` if you need ``{{ X }}``
        references inside the content to be resolved.
        """
        content, _ = self._cascade_load_variable_path(
            var_name, version, root_space, tmpl_type, master_version
        )
        return content

    def _loader_for_path(self, file_path: "Path") -> "Optional[Any]":
        """Find the VariableLoader whose template root is an ancestor of
        ``file_path``. Returns None if no loader exists.
        """
        if not self._variable_loaders_by_root:
            return None
        fp = str(file_path.resolve())
        best_root = None
        for root in self._variable_loaders_by_root:
            rp = str(Path(root).resolve())
            if fp.startswith(rp) and (
                best_root is None or len(root) > len(best_root)
            ):
                best_root = root
        return self._variable_loaders_by_root.get(best_root) if best_root else None

    def load_variables(
        self,
        variable_specs: Dict[str, Any],
        root_space: Optional[str] = None,
        default_version: str = "",
        master_version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Batch-load template variables with cascade resolution.

        Unified API that combines per-variable version selection,
        ``@``-strict mode, ``=``-literal mode, and fallback-to-literal
        with cascading file resolution (space/type → space → global).

        Args:
            variable_specs: Dict mapping variable names to version specs.

                **Key format** — plain or dot-separated:

                - ``"task_preamble"`` — flat key, result is
                  ``{"task_preamble": "<content>"}``
                - ``"notes.local_search_efficiency"`` — dot key, splits
                  into ``var_name="notes"`` + ``version="local_search_efficiency"``,
                  result is nested: ``{"notes": {"local_search_efficiency": "<content>"}}``
                  for Jinja2 ``{{ notes.local_search_efficiency }}`` access.

                **Value conventions** (prefix semantics):

                - ``"aggregation"`` — try file, fall back to literal string
                - ``"@aggregation"`` — strict: raise if file not found
                - ``"=literal text"`` — force literal, skip file lookup
                - ``None`` / ``""`` — for dot keys, version is derived from
                  the dot suffix; for plain keys, uses *default_version*
                - Non-string value — pass through unchanged

            root_space: Template root space (e.g. ``"plan"``).
                Defaults to ``active_template_root_space``.
            default_version: Fallback version for plain-key specs with
                ``None`` or empty values.

        Returns:
            Dict mapping variable names to resolved content.
            Dot keys produce nested dicts.
        """
        if root_space is None:
            root_space = self.active_template_root_space or ""
        tmpl_type = self.active_template_type or "main"

        result: Dict[str, Any] = {}

        def _store_nested(parts: List[str], content: Any) -> None:
            """Store ``content`` at ``result[parts[0]][parts[1]]...[parts[-1]]``.

            Thin adapter around the module-level ``_set_nested_key`` helper
            that converts the list-of-parts signature used here into the
            dotted-key signature the canonical helper expects. Uses
            ``strict=True`` because mixing flat and nested keys with shared
            prefixes inside a single ``load_variables`` call is a caller
            programming error and should fail loudly.
            """
            _set_nested_key(result, ".".join(parts), content, strict=True)

        def _load_and_compose(var_dir: str, version: str) -> Optional[str]:
            """Load variable via cascade and compose nested {{ X }} refs."""
            content, file_path = self._cascade_load_variable_path(
                var_dir, version, root_space, tmpl_type, master_version
            )
            if content is not None and file_path is not None:
                loader = self._loader_for_path(file_path)
                if loader is not None:
                    try:
                        content = loader._resolve_content(
                            content,
                            variable_root_space=root_space,
                            variable_type=tmpl_type,
                            version=version,
                            resolution_stack=[],
                            current_file_path=file_path,
                        )
                    except Exception:
                        pass  # degrade gracefully; return raw content
            return content

        for raw_key, spec in variable_specs.items():
            # Dot-key: ALL dots become path separators; LAST segment is file stem.
            #   "notes.local_search_efficiency"
            #     → var_dir="notes", file_stem="local_search_efficiency"
            #   "instructions.behavior.file_reading_fallback"
            #     → var_dir="instructions/behavior", file_stem="file_reading_fallback"
            if "." in raw_key:
                parts = raw_key.split(".")
                var_dir = "/".join(parts[:-1])
                file_stem = parts[-1]
                nested_path = parts
            else:
                var_dir = raw_key
                file_stem = None
                nested_path = [raw_key]

            value = spec

            # Distinguish None (caller didn't specify, use default) from
            # "" (caller EXPLICITLY chose empty, respect their intent).
            # ``not value`` conflates these; checking ``is None`` does not.
            if value is None:
                value = file_stem if file_stem else default_version
            if value is None or value == "":
                if value == "":
                    # Caller explicitly suppressed this variable.
                    _store_nested(nested_path, "")
                    continue
                # Truly unspecified: fall back to default.jinja2 cascade.
                loaded = _load_and_compose(var_dir, "default")
                _store_nested(nested_path, loaded if loaded is not None else "")
                continue

            # Non-string pass-through
            if not isinstance(value, str):
                _store_nested(nested_path, value)
                continue

            # @-prefix: strict file lookup (raise if not found)
            if value.startswith("@"):
                version = value[1:]
                loaded = _load_and_compose(var_dir, version)
                if loaded is None:
                    raise FileNotFoundError(
                        f"load_variables: no variable file for "
                        f"@{version} (var={var_dir}, space={root_space})"
                    )
                _store_nested(nested_path, loaded)
                continue

            # =-prefix: force literal value
            if value.startswith("="):
                _store_nested(nested_path, value[1:])
                continue

            # Default: try file, fall back to literal string
            loaded = _load_and_compose(var_dir, value)
            _store_nested(nested_path, loaded if loaded is not None else value)

        return result

    def add_template_root(
        self,
        source: Union[str, Mapping],
        priority: TemplateRootPriority = TemplateRootPriority.LOWEST,
    ) -> None:
        """Add a template source after construction.

        Merges templates from *source* into this manager's template store.
        Intended for construction-time use (e.g., in a subclass
        ``__attrs_post_init__``) before concurrent rendering begins.

        Args:
            source: A directory path or dict mapping to merge in.
            priority: ``LOWEST`` fills in missing keys only (default/fallback
                templates).  ``HIGHEST`` overrides existing keys.

        The call is **idempotent**: adding the same *source* twice is a no-op.
        Dict sources are accepted but receive no origin tagging or
        VariableLoader (same as dict sources in the constructor).
        """
        if not isinstance(priority, TemplateRootPriority):
            raise ValueError(
                f"priority must be a TemplateRootPriority, got {priority!r}"
            )

        # Idempotent: skip if already injected
        source_key = source if isinstance(source, str) else id(source)
        if source_key in self._injected_roots:
            return

        # Load the source using the same parameters as __attrs_post_init__
        loaded = read_all_text_(
            source,
            encoding=self.template_encoding,
            keep_extension=False,
            key_sep=self.template_key_parts_sep,
            recursive_levels=-1,
            collect_subdir_files_in_one_mapping=True,
            version_parent_folders=self.template_components_key,
            file_patterns=self.template_file_patterns,
        )

        if isinstance(loaded, str):
            # Single file resolved to text — use as default_template if unset
            if not self.default_template:
                self.default_template = loaded
            self._injected_roots = set(self._injected_roots)  # copy-on-write
            self._injected_roots.add(source_key)
            return

        if not isinstance(loaded, dict):
            return

        is_highest = priority is TemplateRootPriority.HIGHEST
        origin_root = source if isinstance(source, str) else None

        # --- Copy-on-write: isolate from switch() shallow copies ---
        # One-level deep copy of templates dict (inner space dicts are also copied)
        if self.templates is None:
            self.templates = {}
        else:
            self.templates = {
                k: (dict(v) if isinstance(v, dict) else v)
                for k, v in self.templates.items()
            }
        self._original_templates_paths = list(self._original_templates_paths)
        self._injected_roots = set(self._injected_roots)
        self._variable_loaders_by_root = dict(self._variable_loaders_by_root)

        # --- Merge templates ---
        for space_key, space_value in loaded.items():
            if not isinstance(space_value, dict):
                # Non-dict top-level value (rare — e.g., bare default string)
                if is_highest or space_key not in self.templates:
                    self.templates[space_key] = space_value
                continue

            if space_key not in self.templates:
                self.templates[space_key] = {}

            target = self.templates[space_key]
            if not isinstance(target, dict):
                if is_highest:
                    self.templates[space_key] = {}
                    target = self.templates[space_key]
                else:
                    continue

            for tmpl_name, tmpl_content in space_value.items():
                if is_highest or tmpl_name not in target:
                    target[tmpl_name] = (
                        _OriginTaggedStr(tmpl_content, origin_root=origin_root)
                        if origin_root and isinstance(tmpl_content, str)
                        else tmpl_content
                    )

        # --- Update root tracking ---
        if isinstance(source, str):
            if is_highest:
                self._original_templates_paths.insert(0, source)
                self._original_templates_path = source
            else:
                self._original_templates_paths.append(source)
                # LOWEST: don't change _original_templates_path (singular)

        # --- Create VariableLoader for new root if applicable ---
        if self.predefined_variables is True and isinstance(source, str):
            self._add_variable_loader_for_root(source)
            # For LOWEST, don't update _variable_loader (keep highest-priority loader)
            if is_highest and source in self._variable_loaders_by_root:
                self._variable_loader = self._variable_loaders_by_root[source]

        self._injected_roots.add(source_key)

    def get_raw_template(
        self,
        template_key: str = None,
        active_template_type: str = None,
        active_template_root_space: str = None,
        master_version: str = None,
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
            if master_version:
                mv_space_key = (
                    f"{resolved_space_key}{self.template_key_parts_sep}{master_version}"
                    if resolved_space_key
                    else master_version
                )
                result, _ = self._try_versioned_and_unversioned_lookup(
                    mv_space_key, item_key
                )
                if result is not None:
                    return result
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

    def _resolve_templated_feed(
        self,
        merged_feed: dict,
        root_space: str = "",
        tmpl_type: str = "main",
    ) -> dict:
        """Resolve feed values that reference other feed values via template syntax.

        Delegates to the engine-independent resolve_templated_feed utility for
        top-level values, then:

        1. **Re-composes wrapper variables** from raw source files. Wrapper
           variables (e.g. ``context.user_request_with_task_preamble``) are
           composed during auto-discovery, which resolves inner ``{{ X }}``
           references using default versions. If the caller provided explicit
           top-level values (e.g., ``task_preamble`` via ``load_variables``
           with ``master_version``), the composed wrapper is stale — its inner
           references were baked in with the wrong values. Re-loading the raw
           file and re-rendering it against the resolved feed fixes this.

        2. **Recursively renders** remaining ``{{ }}`` references in nested
           dict/list string values against the resolved top-level feed.
        """
        extractor = self.template_variable_extractor
        formatter = self.template_formatter
        if extractor is None or formatter is None:
            return merged_feed

        from python_utils.string_utils.formatting.common import (
            resolve_templated_feed,
        )

        resolved = resolve_templated_feed(
            merged_feed,
            extract_variables=extractor,
            render_template=lambda tmpl, ctx: formatter(tmpl, feed=ctx),
        )

        # Step 1: Re-compose wrapper variables from raw source files.
        # Auto-discovery resolves {{ task_preamble }} inside wrappers using
        # the TemplateManager's version (typically empty → default.jinja2),
        # baking in stale content. The caller's explicit load_variables()
        # result provides the correct value at the top level, but the wrapper
        # has it baked in as literal text. Re-loading the raw wrapper file
        # and re-rendering against the resolved feed (which has the caller's
        # values) produces the correct output.
        if hasattr(self, "_file_space") and self._file_space is not None:
            cascade = self._file_space.build_cascade(root_space, tmpl_type)
            for key, val in resolved.items():
                if not isinstance(val, dict):
                    continue
                for subkey, subval in list(val.items()):
                    if not isinstance(subval, str):
                        continue
                    for cascade_folder in cascade:
                        folder = cascade_folder / key
                        raw_path = self._file_space.find_in_folder(folder, subkey)
                        if raw_path is not None:
                            raw_content = raw_path.read_text(
                                encoding=self.template_encoding
                            )
                            if extractor(raw_content):
                                try:
                                    val[subkey] = formatter(
                                        raw_content, feed=resolved
                                    )
                                except Exception:
                                    pass
                            break

        # Step 2: Recursive pass — render remaining {{ }} references in
        # nested dicts/lists against the resolved top-level feed.
        def _walk(node):
            if isinstance(node, dict):
                return {k: _walk(v) for k, v in node.items()}
            if isinstance(node, list):
                return [_walk(v) for v in node]
            if isinstance(node, str) and extractor(node):
                try:
                    return formatter(node, feed=resolved)
                except Exception:
                    return node
            return node

        # Only walk container values (dicts/lists). Top-level strings are
        # already handled by resolve_templated_feed above.
        return {
            k: _walk(v) if isinstance(v, (dict, list)) else v
            for k, v in resolved.items()
        }

    def __call__(
        self,
        template_key: Any = None,
        feed: Mapping = None,
        post_process: Callable[[str], str] = None,
        formatter: Callable = None,
        active_template_type: str = None,
        active_template_root_space: str = None,
        skip_predefined: bool = False,
        master_version: str = None,
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
            ...         template_formatter=jinjia_template_format,
            ...         template_file_patterns=None,
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
            ...         template_formatter=jinjia_template_format,
            ...         template_file_patterns=None,
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
        # Fallback to default_template_key when caller passes empty/None key
        if not template_key and self.default_template_key:
            template_key = self.default_template_key

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

        # Save original values before fallback may mutate them.
        # Used for variable cascade parameters (backward compat).
        _orig_root_space = active_template_root_space
        _orig_type = active_template_type

        def _resolve_template_space_key_with_root_space_and_type(main_space_key):
            return create_3component_key(
                main_key=main_space_key,
                root_space=active_template_root_space,
                suffix=active_template_type,
                sep=self.template_key_parts_sep,
            )

        def _try_get_template(main_space_key, item_key):
            """Helper to resolve and get template with current state."""
            resolved_space_key = _resolve_template_space_key_with_root_space_and_type(
                main_space_key
            )
            if master_version:
                mv_space_key = (
                    f"{resolved_space_key}{self.template_key_parts_sep}{master_version}"
                    if resolved_space_key
                    else master_version
                )
                result = self._try_versioned_and_unversioned_lookup(
                    mv_space_key, item_key
                )
                if result[0] is not None:
                    return result
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

        # Resolve predefined variables AFTER template resolution so we use the
        # actual resolved template (avoiding divergent fallback chains between
        # get_raw_template and __call__) and can pick the correct per-root
        # VariableLoader via _OriginTaggedStr origin.
        predefined_vars = {}
        if not skip_predefined:
            if self._variable_loader is not None or self._variable_loaders_by_root:
                # Pick the right loader based on template origin (variable isolation).
                origin = getattr(template, "_origin_root", None)
                loader = (
                    self._variable_loaders_by_root.get(origin, self._variable_loader)
                    if origin
                    else self._variable_loader
                )
                if loader:
                    _flat_predefined = loader.resolve_from_template(
                        template_content=template,
                        template_root_space=_orig_root_space or "",
                        template_type=_orig_type or "main",
                        version=self.template_version,
                    )
                    # Also include YAML sidecar variables (loaded via load_yaml_sidecar).
                    # These have lower priority than file-based resolved vars.
                    yaml_vars = loader.get_all_variables(
                        variable_root_space=_orig_root_space or "",
                        variable_type=_orig_type or "main",
                    )
                    if yaml_vars:
                        _flat_predefined = {**yaml_vars, **_flat_predefined}
                    # Re-nest dotted keys (e.g. "context.user_request_with_task_preamble")
                    # into nested dicts so Jinja2's attribute access resolves correctly.
                    # Without this, {{ context.foo }} silently returns Undefined.
                    predefined_vars = {}
                    for _k, _v in _flat_predefined.items():
                        _set_nested_key(predefined_vars, _k, _v)

                    # Refactor 17: cross-root variable fallback.
                    # When enabled, two complementary mechanisms ensure that
                    # an exact-version match in any root wins over a
                    # default-fallback match in the origin root:
                    #
                    # (A) For each detected variable, scan all roots'
                    #     loaders in priority order for an EXACT version
                    #     match (no default fallback). The first hit wins
                    #     and overrides whatever origin's resolve_from_template
                    #     returned (which may have been a default fallback).
                    #
                    # (B) For variables NOT detected in origin's resolve
                    #     (e.g., variables nested under
                    #     ``<root>/<space>/<type>/_variables/`` not at the
                    #     loader's top-level cascade path): use
                    #     ``_cascade_load_variable`` to fill them. Yaml
                    #     sidecar variables from other roots also fill
                    #     remaining gaps.
                    if (
                        self.cross_root_variable_lookup
                        and self._variable_loaders_by_root
                    ):
                        try:
                            extractor = loader._get_variable_extractor(
                                file_path=None
                            )
                        except Exception:  # pragma: no cover — defensive
                            extractor = None
                        var_names: set = set()
                        if extractor is not None:
                            try:
                                var_names = set(extractor(str(template)))
                            except Exception:  # pragma: no cover — defensive
                                var_names = set()
                        var_names.update(predefined_vars.keys())

                        # Mechanism (A): version-only scan in priority order.
                        # For each detected variable, iterate roots' loaders
                        # in priority order. For each loader, ask whether it
                        # has a Pass-1 (exact version) match for the variable
                        # in its cascade — by reaching into ``_find_variable_file``
                        # via the loader's internals. First version-match wins.
                        if self.template_version:
                            for var_name in var_names:
                                priority_value = (
                                    self._find_version_only_across_roots(
                                        var_name=var_name,
                                        version=self.template_version,
                                        root_space=_orig_root_space or "",
                                        type_=_orig_type or "main",
                                    )
                                )
                                if priority_value is not None:
                                    _set_nested_key(
                                        predefined_vars, var_name, priority_value,
                                    )

                        # Mechanism (B): fill keys still missing via
                        # cascade resolution (try file, skip if not found)
                        # AND yaml sidecars.
                        _fb_version = self.template_version
                        if _fb_version:
                            _fb_type = _orig_type or "main"
                            _fb_space = _orig_root_space or ""
                            for var_name in var_names:
                                # Skip if already set (flat OR nested form)
                                if var_name in predefined_vars:
                                    continue
                                if "." in var_name:
                                    parts = var_name.split(".")
                                    cur = predefined_vars.get(parts[0])
                                    already_set = False
                                    for part in parts[1:]:
                                        if not isinstance(cur, dict):
                                            already_set = False
                                            break
                                        if part not in cur:
                                            already_set = False
                                            break
                                        cur = cur[part]
                                        already_set = True
                                    if already_set:
                                        continue
                                fallback = self._cascade_load_variable(
                                    var_name, _fb_version,
                                    _fb_space, _fb_type,
                                )
                                if fallback is not None:
                                    _set_nested_key(
                                        predefined_vars, var_name, fallback,
                                    )

                        # Yaml sidecar variables from other roots fill gaps.
                        for tmpl_path in self._original_templates_paths:
                            other_loader = self._variable_loaders_by_root.get(
                                tmpl_path
                            )
                            if other_loader is None or other_loader is loader:
                                continue
                            other_yaml_vars = other_loader.get_all_variables(
                                variable_root_space=_orig_root_space or "",
                                variable_type=_orig_type or "main",
                            )
                            for k, v in other_yaml_vars.items():
                                _set_nested_key(
                                    predefined_vars, k, v, overwrite=False,
                                )
            elif self._static_predefined_vars is not None:
                predefined_vars = dict(self._static_predefined_vars)

        # Merge: predefined (lowest) < feed < kwargs (highest)
        merged_kwargs = {**predefined_vars}
        if feed:
            merged_kwargs.update(feed)
        merged_kwargs.update(kwargs)
        kwargs = merged_kwargs
        feed = None

        # Resolve templated feed values if enabled
        if self.enable_templated_feed:
            kwargs = self._resolve_templated_feed(
                kwargs,
                root_space=_orig_root_space or "",
                tmpl_type=_orig_type or "main",
            )

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
