import logging
import time
import traceback as _traceback_mod
import warnings
from abc import ABC
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple, Union

from attr import attrib, attrs
from rankevolve.src.utils.common_objects.identifiable import Identifiable
from rankevolve.src.utils.common_utils import iter_, of_type_any
from rankevolve.src.utils.common_utils.function_helper import get_relevant_named_args

LoggerType = Union[Callable[[dict], Any], logging.Logger]


def _level_print(message: str, level: int = logging.INFO):
    """Print a log message with color based on log level.

    Uses the active console_utils backend (Rich or colorama) for coloring.
    Falls back to plain ``print`` when neither backend is available.
    """
    try:
        from rankevolve.src.utils.console_utils import __backend__

        if __backend__ == "rich":
            from rich.markup import escape as _rich_escape
            from rankevolve.src.utils.console_utils import console as _console

            _escaped = _rich_escape(message)
            if level >= logging.ERROR:
                _console.print(_escaped, style="error")
            elif level >= logging.WARNING:
                _console.print(_escaped, style="warning")
            elif level >= logging.INFO:
                _console.print(_escaped, style="info")
            else:
                _console.print(_escaped, style="dim")
        else:
            try:
                from colorama import Fore, Style

                if level >= logging.ERROR:
                    print(f"{Fore.RED}{message}{Style.RESET_ALL}")
                elif level >= logging.WARNING:
                    print(f"{Fore.YELLOW}{message}{Style.RESET_ALL}")
                elif level >= logging.INFO:
                    print(f"{Fore.CYAN}{message}{Style.RESET_ALL}")
                else:
                    print(f"{Fore.LIGHTBLACK_EX}{message}{Style.RESET_ALL}")
            except ImportError:
                print(message)
    except ImportError:
        print(message)


class _ColoredLogFormatter(logging.Formatter):
    """Logging formatter that adds level-based ANSI colors via console_utils."""

    def format(self, record):
        message = super().format(record)
        try:
            from rankevolve.src.utils.console_utils import __backend__

            if __backend__ == "rich":
                # Rich console handles its own coloring; use plain text here
                # since RichHandler should be used instead for Rich coloring.
                # For StreamHandler, fall through to colorama/ANSI.
                pass
            from colorama import Fore, Style

            if record.levelno >= logging.ERROR:
                return f"{Fore.RED}{message}{Style.RESET_ALL}"
            elif record.levelno >= logging.WARNING:
                return f"{Fore.YELLOW}{message}{Style.RESET_ALL}"
            elif record.levelno >= logging.INFO:
                return f"{Fore.CYAN}{message}{Style.RESET_ALL}"
            else:
                return f"{Fore.LIGHTBLACK_EX}{message}{Style.RESET_ALL}"
        except ImportError:
            return message


DEFAULT_LOG_TYPE = "Message"
LOG_TYPE_PARENT_CHILD_DEBUGGABLE_LINK = "ParentChildDebuggableLink"
EXCEPTION_LOG_ITEM_KEY = "__exception__"


@attrs
class LoggerConfig:
    """
    Configuration for an individual logger's filtering and behavior.

    Can be associated with a logger in two ways:
        1. By name via ``logger_configs`` dict::

            logger_configs={'console': LoggerConfig(enabled_log_types={'Error'})}

        2. Inline as a ``(logger, LoggerConfig)`` tuple::

            logger=(print, (file_logger, LoggerConfig()))

    Attributes:
        enabled_log_types (set, optional):
            Whitelist of log types this logger handles. ``None`` means all types enabled.
        disabled_log_types (set, optional):
            Blacklist of log types this logger should skip. ``None`` means no types disabled.
        show_logger_name (bool):
            If True, include the logger's name in log output (e.g. ``[console]``).
        pass_output (bool):
            If True and the logger is callable, its return value becomes
            "processed data" available to downstream loggers.
        use_processed (bool):
            If True and processed data exists from an upstream logger,
            this logger receives the processed data instead of the original log item.
        pass_item_key_as (str, optional):
            If set, Debuggable injects the log_data item field name (``'item'``)
            as this kwarg when calling the logger.  E.g.
            ``pass_item_key_as='parts_key_path_root'`` adds
            ``parts_key_path_root='item'`` to the logger call, so ``write_json``
            knows to prefix ``parts_key_paths`` with ``'item.'``.
        max_message_length (int, optional):
            Maximum character length for log messages sent to this logger.
            Passed as ``max_message_length`` kwarg to callable loggers.
            ``None`` means no limit.
        max_message_length_by_log_type (dict, optional):
            Per-log-type maximum message length overrides.
            The strictest limit (between this and ``max_message_length``) wins.
    """

    enabled_log_types: Optional[Set[str]] = attrib(default=None, kw_only=True)
    disabled_log_types: Optional[Set[str]] = attrib(default=None, kw_only=True)
    show_logger_name: bool = attrib(default=False, kw_only=True)
    pass_output: bool = attrib(default=False, kw_only=True)
    use_processed: bool = attrib(default=False, kw_only=True)
    pass_item_key_as: Optional[str] = attrib(default=None, kw_only=True)
    max_message_length: Optional[int] = attrib(default=None, kw_only=True)
    max_message_length_by_log_type: Optional[Dict[str, int]] = attrib(
        default=None, kw_only=True
    )

    def get_max_message_length(self, log_type: str) -> Optional[int]:
        """Resolve the effective max message length for a log type.

        Returns the strictest (smallest positive) limit from
        ``max_message_length`` and ``max_message_length_by_log_type``,
        or ``None`` if no limit applies.
        """
        candidates = []
        if self.max_message_length and self.max_message_length > 0:
            candidates.append(self.max_message_length)
        if self.max_message_length_by_log_type:
            per_type = self.max_message_length_by_log_type.get(log_type)
            if per_type and per_type > 0:
                candidates.append(per_type)
        return min(candidates) if candidates else None


@attrs(slots=False)
class Debuggable(Identifiable, ABC):
    """
    A base class to provide debug logging capabilities for derived classes.

    Attributes:
        debug_mode (bool):
            Enables debug mode with additional error checking and logging.
            When True, `debug_mode_log_level` is used as the logging threshold, otherwise `log_level` is used.
        logger (Union[Callable, logging.Logger, Sequence, Dict[str, ...]], optional):
            The logger (or collection of loggers) used for logging. Accepts multiple formats:
              - A callable that accepts a single dictionary,
              - An instance of `logging.Logger`,
              - A sequence of the above,
              - A dict mapping logger names to logger objects: ``{'console': print, 'file': write_json}``,
              - A ``(logger, LoggerConfig)`` tuple for inline per-logger configuration,
              - Or `None` (in which case a default logger is created).
            Internally normalized to a dict ``{name: logger_object}``.
        always_add_logging_based_logger (bool):
            If True, ensures a standard logging-based logger is always attached, even if a custom (non-`logging.Logger`)
            logger is provided. Defaults to True.
        log_level (int):
            The logging level to use when `debug_mode` is disabled. Defaults to `logging.INFO`.
        debug_mode_log_level (int):
            The logging level to use when `debug_mode` is enabled. Defaults to `logging.DEBUG`.
        log_time (Union[bool, str]):
            Whether to include timestamps in log messages, and the format to use.
            - If `True`, defaults to `'%Y-%m-%d %H:%M:%S'`.
            - If a string, uses it as `strftime` format (e.g. `'%H:%M:%S'`).
            - If `False`, timestamps are omitted.
        log_name (str):
            The name for the logger. If not set, it defaults to the class name (`self.__class__.__name__`).
        default_log_type (str):
            The default log category/type to use when the `log_type` argument isn't provided to `log`.
            Defaults to 'Message'.
        warning_raiser (Callable):
            A callable (e.g., `warnings.warn`) that handles warnings whenever a WARNING-level log is triggered.
            Defaults to `warnings.warn`.
        console_display_rate_limit (float):
            Rate limit for console display in seconds. If > 0, limits how often messages with the same
            message_id are displayed to the console. Does not affect backend logging. Defaults to 0.0 (no limit).
        logging_rate_limit (float):
            Rate limit for backend logging in seconds. If > 0, limits how often messages with the same
            message_id are logged to non-console loggers (e.g., logging.Logger, write_json). Defaults to 0.0 (no limit).
        enable_console_update (bool):
            If True, enables in-place console updates for messages with message_id tracking.
            Works with console_utils functions (hprint_message, hprint_pairs, etc.). Defaults to False.
        default_message_id_gen (Callable, optional):
            Custom callable for generating message_id when not explicitly provided.
            Called as: default_message_id_gen(self, log_item, log_type, log_level).
            If None, message_id is auto-generated from log_type and log_level.
        console_loggers_or_logger_types (tuple):
            Tuple of logger objects or types that should be considered console loggers.
            Console loggers are subject to console_display_rate_limit.
            Default: (print,). Can include objects (print, pprint.pprint) or types (logging.Logger).
        logger_configs (Dict[str, LoggerConfig], optional):
            Per-logger configuration keyed by logger name. Each ``LoggerConfig`` can specify
            ``enabled_log_types``, ``disabled_log_types``, and ``show_logger_name``.
            Alternative to inline ``(logger, LoggerConfig)`` tuples. Defaults to None.
        enabled_log_types (Set[str], optional):
            Instance-level whitelist of log types. If set, only these log types are emitted.
            ``None`` means all types enabled. An empty ``set()`` silences all logs.
        disabled_log_types (Set[str], optional):
            Instance-level blacklist of log types. These types are suppressed.
            ``None`` means no types disabled.
        id (str, optional):
            Inherited from Identifiable. Unique identifier for this instance.
            Auto-generated if None. Format: `{ClassName}_{uuid}` (e.g., "Agent_a3f2b1c4").

    Examples:
        Basic usage:
        >>> class MyDebuggable(Debuggable):
        ...     def do_stuff(self):
        ...         self.log("Doing stuff...")
        ...
        >>> obj = MyDebuggable(debug_mode=True, logger=print, always_add_logging_based_logger=False, log_time=False)
        >>> obj.do_stuff()
        MyDebuggable_... - MyDebuggable - INFO - Message: Doing stuff...
    """

    debug_mode: bool = attrib(default=False, kw_only=True)
    logger: Optional[Optional[Union[Sequence[LoggerType], LoggerType]]] = attrib(
        default=None, kw_only=True
    )
    always_add_logging_based_logger: bool = attrib(default=True, kw_only=True)
    log_level: int = attrib(default=logging.INFO, kw_only=True)
    debug_mode_log_level: int = attrib(
        default=logging.DEBUG, kw_only=True
    )  # Log levels >= DEBUG
    log_time: Union[bool, str] = attrib(
        default=True, kw_only=True
    )  # Include timestamps in logs
    log_name: str = attrib(default=None, kw_only=True)  # Name for the logger
    default_log_type: str = attrib(default=DEFAULT_LOG_TYPE, kw_only=True)
    warning_raiser: Callable = attrib(default=warnings.warn, kw_only=True)
    parent_debuggables: List[Union[str, Any]] = attrib(default=None, kw_only=True)
    only_keep_parent_debuggable_ids: bool = attrib(default=None, kw_only=True)

    # Rate limiting and console update features
    console_display_rate_limit: float = attrib(
        default=0.0, kw_only=True
    )  # seconds (0 = no limit)
    logging_rate_limit: float = attrib(
        default=0.0, kw_only=True
    )  # seconds (0 = no limit)
    enable_console_update: bool = attrib(
        default=False, kw_only=True
    )  # Enable in-place console updates
    default_message_id_gen: Optional[Callable] = attrib(
        default=None, kw_only=True
    )  # Custom message_id generator
    console_loggers_or_logger_types: tuple = attrib(
        default=(print,), kw_only=True
    )  # Loggers/types considered console output

    # Per-logger configuration, keyed by logger name
    logger_configs: Optional[Dict[str, LoggerConfig]] = attrib(
        default=None, kw_only=True
    )

    # Log type filtering (instance-level gate, applies before per-logger checks)
    enabled_log_types: Optional[Set[str]] = attrib(default=None, kw_only=True)
    disabled_log_types: Optional[Set[str]] = attrib(default=None, kw_only=True)

    # Exception auto-extraction: True (default extractor), False (disabled), or callable(exception) -> dict
    auto_extract_info_from_exception: Union[bool, Callable] = attrib(
        default=True, kw_only=True
    )

    # Internal tracking (not user-configurable)
    _last_console_display_time: Dict[str, float] = attrib(factory=dict, init=False)
    _last_logging_time: Dict[str, float] = attrib(factory=dict, init=False)
    _resolved_logger_configs: Dict[str, Optional[LoggerConfig]] = attrib(
        factory=dict, init=False
    )
    _console_suppression_counts: Dict[str, int] = attrib(factory=dict, init=False)
    _backend_suppression_counts: Dict[str, int] = attrib(factory=dict, init=False)

    _copy_debuggable_config_from: Optional["Debuggable"] = attrib(
        default=None, kw_only=True, alias="copy_debuggable_config_from"
    )

    NON_CONFIG_ATTR_NAMES = (
        "id",
        "_raw_id",
        "parent_debuggables",
        "log_name",
        "_copy_debuggable_config_from",
        "_last_console_display_time",
        "_last_logging_time",
        "_resolved_logger_configs",
        "_console_suppression_counts",
        "_backend_suppression_counts",
    )

    @staticmethod
    def _is_inline_config_pair(entry) -> bool:
        """Check if an entry is a (logger, LoggerConfig) inline pair."""
        return (
            isinstance(entry, (tuple, list))
            and len(entry) == 2
            and isinstance(entry[1], LoggerConfig)
        )

    @staticmethod
    def _auto_logger_name(logger, index: int) -> str:
        """Generate an automatic name for an unnamed logger."""
        if logger is print:
            return "print"
        if isinstance(logger, logging.Logger):
            return logger.name
        if callable(logger):
            name = getattr(logger, "__name__", None)
            if name and name != "<lambda>":
                return name
        return f"logger_{index}"

    def _normalize_loggers(self):
        """
        Normalize ``self.logger`` into a dict ``{name: logger_object}`` and
        build ``self._resolved_logger_configs`` from inline configs and ``logger_configs``.
        """
        logger_dict = {}
        inline_configs = {}
        index = 0

        def _add_entry(name, logger_obj, config):
            nonlocal index
            # Resolve duplicate names
            original_name = name
            while name in logger_dict:
                index += 1
                name = f"{original_name}_{index}"
            logger_dict[name] = logger_obj
            if config is not None:
                inline_configs[name] = config
            index += 1

        if self.logger is not None:
            if isinstance(self.logger, dict):
                # Dict format: {name: logger} or {name: (logger, LoggerConfig)}
                for name, entry in self.logger.items():
                    if self._is_inline_config_pair(entry):
                        _add_entry(name, entry[0], entry[1])
                    else:
                        _add_entry(name, entry, None)
            elif self._is_inline_config_pair(self.logger):
                # Single (logger, LoggerConfig) pair passed as logger
                name = self._auto_logger_name(self.logger[0], index)
                _add_entry(name, self.logger[0], self.logger[1])
            else:
                # Single logger or tuple of loggers (may contain inline pairs)
                for entry in iter_(self.logger):
                    if self._is_inline_config_pair(entry):
                        name = self._auto_logger_name(entry[0], index)
                        _add_entry(name, entry[0], entry[1])
                    else:
                        name = self._auto_logger_name(entry, index)
                        _add_entry(name, entry, None)

        self.logger = logger_dict

        # Build resolved logger configs: logger_configs dict first, then inline overrides
        self._resolved_logger_configs = {}
        if self.logger_configs:
            self._resolved_logger_configs.update(self.logger_configs)
        # Inline configs take priority
        self._resolved_logger_configs.update(inline_configs)

    def __attrs_post_init__(self):
        # Call parent __attrs_post_init__ to initialize id
        super().__attrs_post_init__()

        # Set log_name first (needed for both copy and normal paths)
        if self.log_name is None:
            self.log_name = self.__class__.__name__

        # If copying from another Debuggable, copy all config attributes and skip the rest
        if self._copy_debuggable_config_from is not None:
            from science_python_utils.common_utils.attr_helper import copy_attrs_from

            copy_attrs_from(
                target_instance=self,
                source_instance=self._copy_debuggable_config_from,
                target_class=Debuggable,
                exclude=list(self.NON_CONFIG_ATTR_NAMES),
            )
            # Clear the reference to avoid circular references and save memory
            self._copy_debuggable_config_from = None
            return  # Skip the rest of initialization

        # Normal initialization path (when not copying from another debuggable)
        if self.log_time is True:
            self.log_time = "%Y-%m-%d %H:%M:%S"

        # Check if logger input already contains a logging.Logger
        has_logging_based_logger = False
        if self.logger is not None:
            if isinstance(self.logger, dict):
                has_logging_based_logger = any(
                    isinstance(
                        v[0] if self._is_inline_config_pair(v) else v, logging.Logger
                    )
                    for v in self.logger.values()
                )
            else:
                has_logging_based_logger = of_type_any(self.logger, logging.Logger)

        # Normalize loggers into dict format before potentially adding default logger
        self._normalize_loggers()

        if not self.logger or (
            self.always_add_logging_based_logger and not has_logging_based_logger
        ):
            # Configure a default logger if none is provided
            default_logging_based_logger = logging.getLogger(self.log_name)

            if (
                not default_logging_based_logger.handlers
            ):  # Avoid adding multiple handlers
                import sys

                handler = logging.StreamHandler(sys.stdout)

                # Set formatter based on the log_time attribute
                if self.log_time:
                    formatter = _ColoredLogFormatter(
                        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                        datefmt=self.log_time,
                    )
                else:
                    formatter = _ColoredLogFormatter(
                        fmt="%(name)s - %(levelname)s - %(message)s"
                    )

                handler.setFormatter(formatter)
                default_logging_based_logger.addHandler(handler)
                default_logging_based_logger.setLevel(
                    logging.DEBUG
                )  # Set to DEBUG to capture all levels
            self.logger["_default"] = default_logging_based_logger

    def copy_logging_config(self, another_debuggable: "Debuggable"):
        """
        Copy logging-related configuration from another Debuggable instance.
        """
        from science_python_utils.common_utils.attr_helper import copy_attrs_from

        copy_attrs_from(
            target_instance=self,
            source_instance=another_debuggable,
            target_class=Debuggable,
            exclude=Debuggable.NON_CONFIG_ATTR_NAMES,
        )

    def _generate_message_id(
        self,
        log_item: Any,
        log_type: str,
        log_level: int,
        explicit_id: Optional[str] = None,
    ) -> str:
        """
        Generate a message_id using 3-tier priority logic.

        Args:
            log_item: The item being logged
            log_type: The log type/category
            log_level: The logging level
            explicit_id: Explicitly provided message_id (highest priority)

        Returns:
            A string message_id

        Priority:
            1. Return explicit_id if provided
            2. Call default_message_id_gen(self, log_item, log_type, log_level) if provided
            3. Auto-generate from {self.id}_{log_type}_{log_level}
        """
        # Tier 1: Explicit message_id (highest priority)
        if explicit_id is not None:
            return explicit_id

        # Tier 2: Custom generator callback
        if self.default_message_id_gen is not None and callable(
            self.default_message_id_gen
        ):
            return self.default_message_id_gen(self, log_item, log_type, log_level)

        # Tier 3: Auto-generate from log_type and log_level
        return f"{self.id}_{log_type}_{logging.getLevelName(log_level)}"

    def _should_display_to_console(self, message_id: str) -> bool:
        """
        Check if enough time has passed to display this message to the console.

        Args:
            message_id: The unique identifier for this message

        Returns:
            True if the message should be displayed, False if rate-limited
        """
        if self.console_display_rate_limit <= 0:
            return True  # No rate limiting

        current_time = time.time()
        last_display_time = self._last_console_display_time.get(message_id, 0)

        if current_time - last_display_time >= self.console_display_rate_limit:
            self._last_console_display_time[message_id] = current_time
            return True

        self._console_suppression_counts[message_id] = (
            self._console_suppression_counts.get(message_id, 0) + 1
        )
        return False

    def _should_log_to_backend(self, message_id: str) -> bool:
        """
        Check if enough time has passed to log this message to backend loggers.

        Args:
            message_id: The unique identifier for this message

        Returns:
            True if the message should be logged, False if rate-limited
        """
        if self.logging_rate_limit <= 0:
            return True  # No rate limiting

        current_time = time.time()
        last_logging_time = self._last_logging_time.get(message_id, 0)

        if current_time - last_logging_time >= self.logging_rate_limit:
            self._last_logging_time[message_id] = current_time
            return True

        self._backend_suppression_counts[message_id] = (
            self._backend_suppression_counts.get(message_id, 0) + 1
        )
        return False

    def _is_console_logger(self, logger) -> bool:
        """
        Determine if a logger outputs to console.

        Args:
            logger: The logger to check

        Returns:
            True if the logger outputs to console (stdout/stderr), False otherwise
        """
        import pprint as pprint_module
        import sys

        # print and pprint always output to console
        if logger is print or logger is pprint_module.pprint:
            return True

        # Check if it's a console_utils function
        try:
            from rankevolve.src.utils.console_utils import (
                eprint_message,
                eprint_pairs,
                hprint_message,
                hprint_pairs,
                wprint_message,
                wprint_pairs,
            )

            console_utils_functions = {
                hprint_message,
                eprint_message,
                wprint_message,
                hprint_pairs,
                eprint_pairs,
                wprint_pairs,
            }
            if logger in console_utils_functions:
                return True
        except ImportError:
            pass

        # Check if logging.Logger has console handlers
        if isinstance(logger, logging.Logger):
            for handler in logger.handlers:
                if isinstance(handler, logging.StreamHandler):
                    # Check if stream is stdout or stderr
                    stream = getattr(handler, "stream", None)
                    if stream in (sys.stdout, sys.stderr):
                        return True

        # Additionally check console_loggers_or_logger_types attribute
        for item in self.console_loggers_or_logger_types:
            # Check if logger is the exact object
            if logger is item:
                return True
            # Check if item is a type and logger is an instance of it
            if isinstance(item, type) and isinstance(logger, item):
                return True

        # Other callables (like write_json) are not console loggers
        return False

    def _is_log_type_enabled(
        self, log_type: str, logger_config: Optional[LoggerConfig] = None
    ) -> bool:
        """
        Check if a log type is enabled, applying instance-level and per-logger filtering.

        Two gates are applied in order:
            - Gate 1 (instance-level): ``enabled_log_types`` whitelist, then ``disabled_log_types`` blacklist.
            - Gate 2 (per-logger): same logic from ``LoggerConfig`` fields, if provided.

        Returns:
            True if both gates pass (the log type should be emitted).
        """
        # Gate 1: Instance-level
        if (
            self.enabled_log_types is not None
            and log_type not in self.enabled_log_types
        ):
            return False
        if self.disabled_log_types is not None and log_type in self.disabled_log_types:
            return False

        # Gate 2: Per-logger
        if logger_config is not None:
            if (
                logger_config.enabled_log_types is not None
                and log_type not in logger_config.enabled_log_types
            ):
                return False
            if (
                logger_config.disabled_log_types is not None
                and log_type in logger_config.disabled_log_types
            ):
                return False

        return True

    def log(
        self,
        log_item: Any,
        log_type: str = None,
        log_level: Optional[int] = None,
        message_id: Optional[str] = None,
        **kwargs,
    ):
        """
        Logs a message or data based on the provided type and item.

        Args:
            log_type (str): The type/category of the log (e.g., "INFO", "ERROR").
            log_item (Any, optional): The item or message to log. Can be a string or structured data.
            log_level (int, optional): The logging level to use for this message. If not provided, uses log_level.
            message_id (str, optional): Unique identifier for this message. Used for rate limiting and console updates.
                If not provided, will use default_message_id_gen if set, otherwise auto-generates from log_type and log_level.

        Examples:
            >>> import sys
            >>> sys.stderr = sys.stdout
            >>> from science_python_utils.common_utils import dict__
            >>> import logging
            >>> from dataclasses import dataclass

            >>> @dataclass
            ... class LogItem:
            ...     key1: str
            ...     key2: int

            >>> class ExampleDebuggable(Debuggable):
            ...     def do_something(self):
            ...         self.log({"key1": "value1", "key2": 42}, log_type="DATA", log_level=logging.INFO)
            ...
            ...     def log_object(self):
            ...         log_item = LogItem(key1="value1", key2=42)
            ...         self.log(log_item, log_type="DATA", log_level=logging.INFO)

            >>> example = ExampleDebuggable(debug_mode=True, log_time=False)
            >>> example.do_something()
            ExampleDebuggable - INFO - ExampleDebuggable_... - ExampleDebuggable - DATA: {'key1': 'value1', 'key2': 42}

            >>> example.log_object()
            ExampleDebuggable - INFO - ExampleDebuggable_... - ExampleDebuggable - DATA: {'key1': 'value1', 'key2': 42}

            Example with `write_json` logger:
            >>> import tempfile
            >>> from science_python_utils.io_utils.json_io import write_json
            >>> def write_json_logger(log_data):
            ...     tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
            ...     tmp_name = tmp_file.name
            ...     write_json(log_data, tmp_name)
            ...     with open(tmp_name, 'r') as f:
            ...         print(f.read())  # Ensure doctest captures this output
            ...     tmp_file.close()
            ...     os.unlink(tmp_name)

            >>> class JSONExample(Debuggable):
            ...     pass

            >>> json_example = JSONExample(logger=write_json_logger, log_time=False, always_add_logging_based_logger=False)
            >>> json_example.log({"key1": "value1", "key2": 42}, "key-value")
            overwrite file ...
            {"level": 20, "name": "JSONExample", "id": "JSONExample_...", "type": "key-value", "item": {"key1": "value1", "key2": 42}}

            Example with logger that supports 'space' parameter:
            >>> def space_aware_logger(log_data, space=None):
            ...     print(f"[Space: {space}] {log_data['type']}: {log_data['item']}")

            >>> class SpaceExample(Debuggable):
            ...     pass

            >>> space_example = SpaceExample(logger=space_aware_logger, log_time=False, always_add_logging_based_logger=False, id="MySpace")
            >>> space_example.log("Processing data", "Task")
            [Space: MySpace] Task: Processing data
        """
        if log_level is None:
            log_level = self.log_level

        # Auto-extract info from Exception objects
        if self.auto_extract_info_from_exception:
            exc = None
            if isinstance(log_item, BaseException):
                exc = log_item
            elif isinstance(log_item, dict) and EXCEPTION_LOG_ITEM_KEY in log_item:
                exc = log_item.pop(EXCEPTION_LOG_ITEM_KEY)

            if exc is not None:
                if log_level < logging.ERROR:
                    warnings.warn(
                        f"Logging exception {type(exc).__name__} at "
                        f"{logging.getLevelName(log_level)} level (expected ERROR or higher)"
                    )
                if callable(self.auto_extract_info_from_exception):
                    extracted = self.auto_extract_info_from_exception(exc)
                else:
                    # Default extraction: exception type, message, and traceback
                    tb_text = _traceback_mod.format_exc()
                    if tb_text.strip() == "NoneType: None":
                        tb_text = "".join(
                            _traceback_mod.format_exception(
                                type(exc), exc, exc.__traceback__
                            )
                        )
                    extracted = {
                        "exception_type": type(exc).__name__,
                        "message": str(exc),
                        "traceback": tb_text,
                    }
                if isinstance(log_item, dict):
                    # Merge extracted info into existing dict (don't overwrite caller's keys)
                    for k, v in extracted.items():
                        log_item.setdefault(k, v)
                else:
                    log_item = extracted

        if not log_type:
            log_type = self.default_log_type

        # Generate message_id early for rate limiting checks
        generated_message_id = self._generate_message_id(
            log_item, log_type, log_level, message_id
        )

        # Determine whether to log based on debug_mode and log_level
        threshold = self.debug_mode_log_level if self.debug_mode else self.log_level
        should_log = log_level >= threshold

        if not should_log:
            return

        # Instance-level log type filter (early return)
        if not self._is_log_type_enabled(log_type):
            return

        processed = None  # Pipeline: processed data from upstream logger

        for _logger_name, _logger in self.logger.items():
            try:
                # Look up per-logger config
                logger_config = (
                    self._resolved_logger_configs.get(_logger_name)
                    if self._resolved_logger_configs
                    else None
                )

                # Per-logger log type filter
                if logger_config is not None and not self._is_log_type_enabled(
                    log_type, logger_config
                ):
                    continue

                # Determine if this is a console logger
                is_console_logger = self._is_console_logger(_logger)

                # Check rate limits
                if is_console_logger and not self._should_display_to_console(
                    generated_message_id
                ):
                    continue
                elif not is_console_logger and not self._should_log_to_backend(
                    generated_message_id
                ):
                    continue

                # Pipeline: determine effective log_item for this logger
                _use_processed = (
                    logger_config is not None
                    and logger_config.use_processed
                    and processed is not None
                )
                effective_log_item = processed if _use_processed else log_item
                display_item = effective_log_item

                # Apply truncation for console loggers (print, logging.Logger)
                if is_console_logger and logger_config is not None:
                    _max_len = logger_config.get_max_message_length(log_type)
                    if _max_len is not None:
                        display_str = (
                            str(display_item)
                            if not isinstance(display_item, str)
                            else display_item
                        )
                        if len(display_str) > _max_len:
                            display_item = (
                                display_str[:_max_len]
                                + f"... [{len(display_str)} chars]"
                            )

                # Determine logger name display
                show_name = (
                    logger_config.show_logger_name
                    if logger_config is not None
                    else False
                )

                if _logger is print:
                    # Check for console suppression count
                    console_suppressed = self._console_suppression_counts.get(
                        generated_message_id, 0
                    )
                    suppression_suffix = (
                        f" [{console_suppressed} suppressed]"
                        if console_suppressed > 0
                        else ""
                    )
                    if console_suppressed > 0:
                        self._console_suppression_counts[generated_message_id] = 0

                    if self.log_time:
                        time_str = datetime.now().strftime(self.log_time)
                        if show_name:
                            message = f"{self.id} - {time_str} - {self.log_name} [{_logger_name}] - {logging.getLevelName(log_level)} - {log_type}: {display_item}{suppression_suffix}"
                        else:
                            message = f"{self.id} - {time_str} - {self.log_name} - {logging.getLevelName(log_level)} - {log_type}: {display_item}{suppression_suffix}"
                    else:
                        if show_name:
                            message = f"{self.id} - {self.log_name} [{_logger_name}] - {logging.getLevelName(log_level)} - {log_type}: {display_item}{suppression_suffix}"
                        else:
                            message = f"{self.id} - {self.log_name} - {logging.getLevelName(log_level)} - {log_type}: {display_item}{suppression_suffix}"
                    _level_print(message, log_level)

                    if log_level == logging.WARNING and self.warning_raiser is not None:
                        self.warning_raiser(message)
                elif isinstance(_logger, logging.Logger):
                    # Check for suppression count based on logger type
                    if is_console_logger:
                        suppressed = self._console_suppression_counts.get(
                            generated_message_id, 0
                        )
                        suppression_suffix = (
                            f" [{suppressed} suppressed]" if suppressed > 0 else ""
                        )
                        if suppressed > 0:
                            self._console_suppression_counts[generated_message_id] = 0
                    else:
                        suppressed = self._backend_suppression_counts.get(
                            generated_message_id, 0
                        )
                        suppression_suffix = (
                            f" [{suppressed} suppressed]" if suppressed > 0 else ""
                        )
                        if suppressed > 0:
                            self._backend_suppression_counts[generated_message_id] = 0

                    if show_name:
                        message = f"{self.id} - {self.log_name} [{_logger_name}] - {log_type}: {display_item}{suppression_suffix}"
                    else:
                        message = f"{self.id} - {self.log_name} - {log_type}: {display_item}{suppression_suffix}"
                    _logger.log(log_level, message)

                    if log_level == logging.WARNING and self.warning_raiser is not None:
                        self.warning_raiser(message)
                elif callable(_logger):
                    # Use the callable logger
                    log_data = {
                        "level": log_level,
                        "name": self.log_name,
                        "id": self.id,
                        "type": log_type,
                        "item": display_item,
                    }
                    if self.log_time:
                        log_data["time"] = datetime.now().strftime(self.log_time)

                    # Add suppression count based on logger type
                    if is_console_logger:
                        console_suppressed = self._console_suppression_counts.get(
                            generated_message_id, 0
                        )
                        if console_suppressed > 0:
                            log_data["suppressed_count"] = console_suppressed
                            self._console_suppression_counts[generated_message_id] = 0
                    else:
                        backend_suppressed = self._backend_suppression_counts.get(
                            generated_message_id, 0
                        )
                        if backend_suppressed > 0:
                            log_data["suppressed_count"] = backend_suppressed
                            self._backend_suppression_counts[generated_message_id] = 0

                    # Add logger name if configured
                    if show_name:
                        log_data["logger_name"] = _logger_name

                    # Add parent debuggable IDs if they exist
                    parent_ids = self.get_parent_debuggable_ids()
                    if parent_ids:
                        log_data["parent_ids"] = parent_ids

                    # Build candidate kwargs for callable logger
                    candidate_kwargs = {"space": self.id}

                    # Console update params (conditional)
                    if self.enable_console_update:
                        candidate_kwargs["message_id"] = generated_message_id
                        candidate_kwargs["update_previous"] = True

                    # Inject item key name if configured
                    if logger_config is not None and logger_config.pass_item_key_as:
                        candidate_kwargs[logger_config.pass_item_key_as] = "item"

                    # Inject max_message_length if configured
                    if logger_config is not None:
                        _max_len = logger_config.get_max_message_length(log_type)
                        if _max_len is not None:
                            candidate_kwargs["max_message_length"] = _max_len

                    # Forward any extra kwargs to callable loggers (e.g. parts extraction params)
                    candidate_kwargs.update(kwargs)

                    # Exclude params already baked into functools.partial to avoid duplicate keyword TypeError
                    _partial_keywords = (
                        list(getattr(_logger, "keywords", {}).keys()) or None
                    )

                    # Filter to only params the logger accepts (or pass all if logger has **kwargs)
                    _filtered_kwargs = get_relevant_named_args(
                        _logger,
                        all_named_args_relevant_if_func_support_named_args=True,
                        exclusion=_partial_keywords,
                        **candidate_kwargs,
                    )

                    result = (
                        _logger(log_data, **_filtered_kwargs)
                        if _filtered_kwargs
                        else _logger(log_data)
                    )

                    # Pipeline: capture output for downstream loggers
                    if (
                        logger_config is not None
                        and logger_config.pass_output
                        and result is not None
                    ):
                        processed = result

                    if log_level == logging.WARNING and self.warning_raiser is not None:
                        message = (
                            f"{self.id} - {self.log_name} - {log_type}: {display_item}"
                        )
                        self.warning_raiser(message)
                else:
                    raise TypeError(
                        "Logger must be a callable or an instance of logging.Logger"
                    )
            except Exception as e:
                # Fallback for logging errors — guard the error handler
                # itself against secondary failures (e.g. BrokenPipeError
                # when the stdout pipe is dead from a broken tee/pipe).
                if self.debug_mode:
                    try:
                        print(
                            f"Logging failed for logger"
                            f" '{_logger_name}': {e}"
                        )
                    except Exception:
                        pass

    # region Convenience Logging Methods
    def log_info(
        self,
        log_item: Any,
        log_type: str = None,
        message_id: Optional[str] = None,
        **kwargs,
    ):
        """Logs a message with INFO level."""
        self.log(
            log_item, log_type, log_level=logging.INFO, message_id=message_id, **kwargs
        )

    def log_debug(
        self,
        log_item: Any,
        log_type: str = None,
        message_id: Optional[str] = None,
        **kwargs,
    ):
        """Logs a message with DEBUG level."""
        self.log(
            log_item, log_type, log_level=logging.DEBUG, message_id=message_id, **kwargs
        )

    def log_warning(
        self,
        log_item: Any,
        log_type: str = None,
        message_id: Optional[str] = None,
        **kwargs,
    ):
        """Logs a message with WARNING level."""
        self.log(
            log_item,
            log_type,
            log_level=logging.WARNING,
            message_id=message_id,
            **kwargs,
        )

    def log_error(
        self,
        log_item: Any,
        log_type: str = None,
        message_id: Optional[str] = None,
        **kwargs,
    ):
        """Logs a message with ERROR level."""
        self.log(
            log_item, log_type, log_level=logging.ERROR, message_id=message_id, **kwargs
        )

    def log_critical(
        self,
        log_item: Any,
        log_type: str = None,
        message_id: Optional[str] = None,
        **kwargs,
    ):
        """Logs a message with CRITICAL level."""
        self.log(
            log_item,
            log_type,
            log_level=logging.CRITICAL,
            message_id=message_id,
            **kwargs,
        )

    # logging.Logger-compatible aliases
    # These allow Debuggable to be used interchangeably with logging.Logger
    # for simple log calls like logger.debug("message") or logger.info("message").
    def debug(self, msg, *args, **kwargs):
        """Alias for log_debug, compatible with logging.Logger.debug()."""
        self.log_debug(msg % args if args else msg)

    def info(self, msg, *args, **kwargs):
        """Alias for log_info, compatible with logging.Logger.info()."""
        self.log_info(msg % args if args else msg)

    def warning(self, msg, *args, **kwargs):
        """Alias for log_warning, compatible with logging.Logger.warning()."""
        self.log_warning(msg % args if args else msg)

    def error(self, msg, *args, **kwargs):
        """Alias for log_error, compatible with logging.Logger.error()."""
        self.log_error(msg % args if args else msg)

    def critical(self, msg, *args, **kwargs):
        """Alias for log_critical, compatible with logging.Logger.critical()."""
        self.log_critical(msg % args if args else msg)

    # endregion

    def enable_debug_mode(self):
        """Enables debug mode."""
        self.debug_mode = True
        self.log("Debug mode enabled.", "DEBUG", log_level=logging.DEBUG)

    def disable_debug_mode(self):
        """Disables debug mode."""
        self.log("Debug mode disabled.", "DEBUG", log_level=logging.DEBUG)
        self.debug_mode = False

    # region Debuggable Graph Implementation

    def set_parent_debuggable(self, parent_debuggable: Union[str, "Debuggable"]):
        """
        Set a parent debuggable object, establishing a hierarchical relationship.

        Args:
            parent_debuggable: Either a Debuggable instance or a string ID of a parent

        Example:
            >>> parent = Debuggable()
            >>> child = Debuggable()
            >>> child.set_parent_debuggable(parent)
            >>> child.set_parent_debuggable("parent_id_string")
        """
        if self.parent_debuggables is None:
            self.parent_debuggables = []

        # Extract the ID to check for duplicates
        if isinstance(parent_debuggable, str):
            parent_id = parent_debuggable
            to_append = parent_debuggable
        elif isinstance(parent_debuggable, Debuggable):
            # It's a Debuggable instance
            parent_id = parent_debuggable.id
            to_append = (
                parent_id if self.only_keep_parent_debuggable_ids else parent_debuggable
            )
        else:
            raise TypeError(
                "parent_debuggable must be a string or a Debuggable instance"
            )

        # Check if already exists (avoid duplicates)
        existing_ids = self.get_parent_debuggable_ids()
        if parent_id not in existing_ids:
            self.parent_debuggables.append(to_append)

            # Log the parent-child relationship to ensure it's captured in logs
            # This is critical for log-based graph reconstruction
            # Even if this Debuggable never logs business data, this relationship will be recorded
            self.log_info(
                f"Parent '{parent_id}' linked to child '{self.id}'",
                LOG_TYPE_PARENT_CHILD_DEBUGGABLE_LINK,
            )

    def get_parent_debuggable_ids(self) -> Sequence[str]:
        """
        Get the IDs of all parent debuggable objects.

        Returns:
            A sequence of parent debuggable IDs as strings

        Example:
            >>> parent = Debugger()
            >>> child = Debugger(parent_debuggables=[parent, "other_id"])
            >>> ids = child.get_parent_debuggable_ids()
            >>> len(ids)
            2
        """
        if not self.parent_debuggables:
            return []

        return [
            debuggable.id if isinstance(debuggable, Debuggable) else str(debuggable)
            for debuggable in self.parent_debuggables
        ]

    # endregion


class Debugger(Debuggable):
    """
    A concrete implementation of Debuggable with no additional functionality.

    This class can be instantiated directly and used for debugging purposes
    without needing to create a custom subclass.

    Example:
        >>> debugger = Debugger(debug_mode=True)
        >>> debugger.log("Test message")
    """

    pass
