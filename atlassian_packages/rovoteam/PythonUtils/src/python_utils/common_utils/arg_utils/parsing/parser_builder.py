"""
Argument parser builder - orchestrator for the parsing process.
"""

import ast
import sys
from argparse import ArgumentParser, Namespace
from os import path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from python_utils.common_utils.environment_helper import is_ipython
from python_utils.common_utils.arg_utils.arg_naming import (
    solve_arg_full_and_short_name,
    solve_parameter_info,
)
from python_utils.common_utils.arg_utils.arg_parse import (
    sanitize_arg_name,
    get_seen_actions,
)
from python_utils.console_utils import hprint_message

from .preset_loader import PresetLoaderRegistry
from .argument_registrar import ArgumentRegistrar
from .value_converter import ValueConverter
from .validator import ArgumentValidator


class ArgumentParserBuilder:
    """
    Main orchestrator that coordinates all parsing components.

    Provides the same functionality as the original get_parsed_args function
    but with a modular, testable architecture.
    """

    def __init__(
        self,
        preset_root: Optional[str] = None,
        preset: Optional[Union[Dict[str, Any], str]] = None,
        short_full_name_sep: str = "/",
        return_seen_args: bool = False,
        default_value_prefix: str = "default_",
        exposed_args: Optional[List[str]] = None,
        required_args: Optional[List[str]] = None,
        non_empty_args: Optional[List[str]] = None,
        constants: Optional[Any] = None,
        force_parse_boolstr: bool = True,
        verbose: bool = True,
        argv: Optional[List[str]] = None,
        arg_parser: Optional[ArgumentParser] = None,
        replace_double_underscore_with_dash: bool = True,
        interactive: bool = False,
    ):
        """
        Initialize the argument parser builder.

        All parameters match the original get_parsed_args function.
        """
        self.preset_root = preset_root
        self.preset = preset
        self.short_full_name_sep = short_full_name_sep
        self.return_seen_args = return_seen_args
        self.default_value_prefix = default_value_prefix
        self.exposed_args = exposed_args
        self.required_args = required_args
        self.non_empty_args = non_empty_args
        self.constants = constants
        self.force_parse_boolstr = force_parse_boolstr
        self.verbose = verbose
        self.replace_double_underscore_with_dash = replace_double_underscore_with_dash
        self.interactive = interactive

        # Handle argv
        self.argv = argv or sys.argv
        self._argv = self._process_argv()

        # Initialize parser
        self.parser = arg_parser if arg_parser is not None else ArgumentParser()

        # Initialize components
        self.preset_loader = PresetLoaderRegistry()
        self._is_ipython = is_ipython()

    def _process_argv(self) -> List[str]:
        """
        Process argv to handle special cases.

        - PyCharm docrunner: use argv[2:] instead of argv[1:]
        - CLI 'preset' keyword: extract preset from argv

        Returns:
            Processed argument list
        """
        # Handle PyCharm docrunner
        if "pycharm/docrunner.py" in self.argv[0]:
            _argv = self.argv[2:]
        else:
            _argv = self.argv[1:]

        # Handle CLI 'preset' keyword: script.py preset "{'key': 'val'}"
        if _argv and _argv[0] == "preset":
            self.preset = ast.literal_eval(_argv[1])
            _argv = _argv[2:]

        return _argv

    def _load_preset(self) -> Optional[Dict[str, Any]]:
        """
        Load preset if specified.

        Returns:
            Preset dictionary, or None if no preset
        """
        if self.preset is None:
            return None

        if isinstance(self.preset, dict):
            return self.preset

        if isinstance(self.preset, str):
            return self.preset_loader.load_preset(
                preset_path=self.preset,
                preset_root=self.preset_root,
            )

        # List/tuple preset - return as-is for recursive handling
        if isinstance(self.preset, (list, tuple)):
            return self.preset

        return None

    def _handle_verbose_start(self) -> None:
        """Print verbose output at start of parsing."""
        if self.verbose:
            hprint_message(
                "arg_parser._actions",
                self.parser._actions,
                "num_existing_args",
                len(self.parser._actions),
                title=f"using arg_parser of type {type(self.parser)}",
            )

    def _handle_verbose_end(self, args: Namespace) -> None:
        """Print verbose output at end of parsing."""
        if self.verbose:
            import __main__

            if hasattr(__main__, "__file__"):
                hprint_message(path.basename(__main__.__file__), args.__dict__)
            else:
                hprint_message(str(__main__), args.__dict__)

    def build(
        self, *arg_info_objs, **kwargs
    ) -> Union[Namespace, Tuple[Namespace, List[str]], List]:
        """
        Build and parse arguments.

        Args:
            *arg_info_objs: Argument definition objects
            **kwargs: Default values as named arguments (default_xxx pattern)

        Returns:
            Namespace with parsed arguments, or tuple (Namespace, seen_args)
            if return_seen_args is True, or list if preset is a list
        """
        # Load preset
        preset_dict = self._load_preset()

        # Handle list preset - recursive calls
        if isinstance(preset_dict, (list, tuple)):
            return self._handle_list_preset(preset_dict, arg_info_objs, kwargs)

        # Print verbose start
        self._handle_verbose_start()

        # Initialize registrar
        registrar = ArgumentRegistrar(
            parser=self.parser,
            replace_double_underscore_with_dash=self.replace_double_underscore_with_dash,
            exposed_args=self.exposed_args,
            required_args=self.required_args,
            is_ipython=self._is_ipython,
        )

        # Process argument definitions
        self._process_arg_info_objs(arg_info_objs, kwargs, preset_dict, registrar)

        # Process ad-hoc arguments from preset
        if preset_dict:
            self._process_preset_adhoc_args(kwargs, preset_dict, registrar)

        # Process default_xxx kwargs
        self._process_default_kwargs(kwargs, registrar)

        # Parse arguments
        args = self.parser.parse_args(self._argv)

        # Inject hidden args (exposed_args feature)
        self._inject_hidden_args(args, registrar)

        # Convert values
        converter = ValueConverter(
            converters=registrar.converters,
            sanitized_to_original_map=registrar.sanitized_to_original_map,
            constants=self.constants,
            force_parse_boolstr=self.force_parse_boolstr,
        )
        args = converter.convert_all(args)

        # Validate
        validator = ArgumentValidator(non_empty_args=self.non_empty_args)
        validator.validate(args)

        # Interactive mode: collect values interactively
        if self.interactive:
            args = self._collect_interactive(args, registrar, preset_dict)

        # Print verbose end
        self._handle_verbose_end(args)

        # Return with seen args if requested
        if self.return_seen_args:
            return args, get_seen_actions(self.parser, self.argv)
        return args

    def _handle_list_preset(
        self,
        preset_list: Union[List, Tuple],
        arg_info_objs: tuple,
        kwargs: dict,
    ) -> List:
        """
        Handle list preset by making recursive calls.

        Args:
            preset_list: List of preset configurations
            arg_info_objs: Argument definitions
            kwargs: Default values

        Returns:
            List of Namespace objects
        """
        results = []
        for _preset in preset_list:
            builder = ArgumentParserBuilder(
                preset_root=self.preset_root,
                preset=_preset,
                short_full_name_sep=self.short_full_name_sep,
                return_seen_args=self.return_seen_args,
                default_value_prefix=self.default_value_prefix,
                exposed_args=self.exposed_args,
                required_args=self.required_args,
                non_empty_args=self.non_empty_args,
                constants=self.constants,
                force_parse_boolstr=self.force_parse_boolstr,
                verbose=self.verbose,
                argv=self.argv,
                arg_parser=None,  # Fresh parser for each
                replace_double_underscore_with_dash=self.replace_double_underscore_with_dash,
            )
            results.append(builder.build(*arg_info_objs, **kwargs.copy()))
        return results

    def _process_arg_info_objs(
        self,
        arg_info_objs: tuple,
        kwargs: dict,
        preset_dict: Optional[Dict[str, Any]],
        registrar: ArgumentRegistrar,
    ) -> None:
        """
        Process argument definition objects.

        Args:
            arg_info_objs: Argument definitions
            kwargs: Default values
            preset_dict: Loaded preset dictionary
            registrar: ArgumentRegistrar instance
        """
        for arg_info_obj in arg_info_objs:
            # Solve parameter info
            arg_full_name, arg_short_name, default_value, converter, description = (
                solve_parameter_info(
                    parameter_info=arg_info_obj,
                    arg_short_name_deduplication=registrar.short_name_set,
                    short_full_name_sep=self.short_full_name_sep,
                )
            )

            # Handle sanitized names
            sanitized_arg_name = sanitize_arg_name(arg_full_name)
            if sanitized_arg_name != arg_full_name:
                if sanitized_arg_name not in registrar.sanitized_to_original_map:
                    registrar.sanitized_to_original_map[sanitized_arg_name] = arg_full_name
                else:
                    raise ValueError(
                        f"argument name '{arg_full_name}' conflicts with "
                        f"an existing argument name "
                        f"'{registrar.sanitized_to_original_map[sanitized_arg_name]}'"
                    )

            # Override 1: from kwargs (default_xxx or direct name)
            default_value_override = kwargs.get(
                arg_full_name,
                kwargs.pop(self.default_value_prefix + arg_full_name, None),
            )
            if default_value_override is not None:
                default_value = default_value_override

            # Override 2: from preset (highest priority)
            if preset_dict is not None:
                default_value_override = preset_dict.get(
                    arg_full_name,
                    preset_dict.get(self.default_value_prefix + arg_full_name, None),
                )
                if default_value_override is not None:
                    default_value = default_value_override

            # Register the argument
            registrar.register_argument(
                full_name=arg_full_name,
                short_name=arg_short_name,
                default_value=default_value,
                description=description or "",
                converter=converter,
            )

    def _process_preset_adhoc_args(
        self,
        kwargs: dict,
        preset_dict: Dict[str, Any],
        registrar: ArgumentRegistrar,
    ) -> None:
        """
        Process ad-hoc arguments from preset dictionary.

        These are arguments defined in the preset but not in arg_info_objs.

        Args:
            kwargs: Default values
            preset_dict: Loaded preset dictionary
            registrar: ArgumentRegistrar instance
        """
        for arg_full_name, default_value in preset_dict.items():
            # Strip default_value_prefix if present
            if arg_full_name.startswith(self.default_value_prefix):
                arg_full_name = arg_full_name[len(self.default_value_prefix):]

            # Solve name
            arg_full_name, arg_short_name = solve_arg_full_and_short_name(
                arg_name_str=arg_full_name,
                arg_short_name_deduplication=registrar.short_name_set,
                short_full_name_sep=self.short_full_name_sep,
            )

            if arg_full_name:
                # Override from kwargs if preset value is None
                if default_value is None:
                    default_value = kwargs.get(
                        arg_full_name,
                        kwargs.pop(self.default_value_prefix + arg_full_name, None),
                    )

                registrar.register_argument(
                    full_name=arg_full_name,
                    short_name=arg_short_name,
                    default_value=default_value,
                    description="",
                    converter=None,
                )

    def _process_default_kwargs(
        self,
        kwargs: dict,
        registrar: ArgumentRegistrar,
    ) -> None:
        """
        Process default_xxx kwargs as ad-hoc arguments.

        Args:
            kwargs: Default values
            registrar: ArgumentRegistrar instance
        """
        for arg_full_name, default_value in list(kwargs.items()):
            if arg_full_name.startswith(self.default_value_prefix):
                arg_full_name = arg_full_name[len(self.default_value_prefix):]

                arg_full_name, arg_short_name = solve_arg_full_and_short_name(
                    arg_name_str=arg_full_name,
                    arg_short_name_deduplication=registrar.short_name_set,
                    short_full_name_sep=self.short_full_name_sep,
                )

                if arg_full_name:
                    registrar.register_argument(
                        full_name=arg_full_name,
                        short_name=arg_short_name,
                        default_value=default_value,
                        description="",
                        converter=None,
                    )

    def _inject_hidden_args(
        self,
        args: Namespace,
        registrar: ArgumentRegistrar,
    ) -> None:
        """
        Inject hidden arguments after parsing (exposed_args feature).

        Args:
            args: Parsed namespace
            registrar: ArgumentRegistrar instance
        """
        if registrar.hidden_args:
            # Create a temporary converter for processing hidden arg values
            converter = ValueConverter(
                converters={},
                constants=self.constants,
                force_parse_boolstr=self.force_parse_boolstr,
            )

            for arg_full_name, arg_val in registrar.hidden_args:
                processed_val = converter._process_arg_val(arg_val)
                setattr(args, arg_full_name, processed_val)

    def _collect_interactive(
        self,
        args: Namespace,
        registrar: ArgumentRegistrar,
        preset_dict: Optional[Dict[str, Any]],
    ) -> Namespace:
        """
        Collect argument values interactively.

        Args:
            args: Current parsed arguments namespace
            registrar: ArgumentRegistrar instance with registered arguments
            preset_dict: Loaded preset dictionary

        Returns:
            Updated namespace with interactively collected values
        """
        from .interactive import InteractiveCollector

        # Build argument definitions list from registrar
        arg_definitions = []
        for action in self.parser._actions:
            # Skip help and special actions
            if action.dest in ('help', '_help', 'version'):
                continue

            # Get the full name (without -- prefix)
            arg_name = action.dest

            # Get default value and description
            default_value = getattr(args, arg_name, action.default)
            description = action.help or ""

            arg_definitions.append((arg_name, default_value, description))

        # Create collector and collect values
        collector = InteractiveCollector(use_widgets=True)
        collected_values = collector.collect_arguments(
            arg_definitions=arg_definitions,
            preset_values=preset_dict,
        )

        # Merge collected values back into args namespace
        for arg_name, value in collected_values.items():
            setattr(args, arg_name, value)

        return args
