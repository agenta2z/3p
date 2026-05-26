"""
Interactive argument collection for get_parsed_args.

Provides interactive prompts for setting argument values in both
Jupyter notebooks (with widgets) and terminal environments.
"""

from typing import Any, Dict, List, Optional, Tuple
from argparse import Namespace
import sys


def is_jupyter() -> bool:
    """
    Detect if running in Jupyter/IPython environment.

    Returns:
        True if running in Jupyter/IPython, False otherwise
    """
    try:
        # Check if IPython is available and active
        from IPython import get_ipython
        ipython = get_ipython()
        if ipython is None:
            return False

        # Check if it's a Jupyter kernel
        return 'IPKernelApp' in ipython.config
    except (ImportError, AttributeError):
        return False


def is_ipython_terminal() -> bool:
    """
    Detect if running in IPython terminal (not Jupyter notebook).

    Returns:
        True if running in IPython terminal, False otherwise
    """
    try:
        from IPython import get_ipython
        ipython = get_ipython()
        if ipython is None:
            return False

        # IPython terminal, not Jupyter
        return 'TerminalInteractiveShell' in str(type(ipython))
    except (ImportError, AttributeError):
        return False


class InteractiveCollector:
    """
    Collects argument values interactively.

    Supports both Jupyter notebook (with ipywidgets) and terminal modes.
    """

    def __init__(self, use_widgets: bool = True):
        """
        Initialize interactive collector.

        Args:
            use_widgets: Try to use ipywidgets in Jupyter (default: True)
        """
        self.use_widgets = use_widgets and is_jupyter()
        self.is_ipython = is_ipython_terminal()

    def collect_arguments(
        self,
        arg_definitions: List[Tuple[str, Any, str]],
        preset_values: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Collect argument values interactively.

        Args:
            arg_definitions: List of (name, default_value, description) tuples
            preset_values: Optional preset values to show as defaults

        Returns:
            Dictionary of collected argument values
        """
        if self.use_widgets:
            return self._collect_with_widgets(arg_definitions, preset_values)
        else:
            return self._collect_with_terminal(arg_definitions, preset_values)

    def _collect_with_widgets(
        self,
        arg_definitions: List[Tuple[str, Any, str]],
        preset_values: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Collect arguments using Jupyter widgets.

        Args:
            arg_definitions: List of (name, default_value, description) tuples
            preset_values: Optional preset values

        Returns:
            Dictionary of collected values
        """
        try:
            import ipywidgets as widgets
            from IPython.display import display, HTML
        except ImportError:
            # Fall back to terminal mode if widgets not available
            return self._collect_with_terminal(arg_definitions, preset_values)

        preset_values = preset_values or {}
        collected = {}
        widget_list = []

        display(HTML("<h3>Configure Arguments</h3>"))

        for name, default_value, description in arg_definitions:
            # Get the effective default (preset overrides default)
            effective_default = preset_values.get(name, default_value)

            # Create appropriate widget based on type
            if isinstance(effective_default, bool):
                widget = widgets.Checkbox(
                    value=effective_default,
                    description=f"{name}:",
                    style={'description_width': '150px'},
                )
            elif isinstance(effective_default, (int, float)):
                widget = widgets.FloatText(
                    value=float(effective_default),
                    description=f"{name}:",
                    style={'description_width': '150px'},
                )
            elif isinstance(effective_default, (list, tuple)):
                widget = widgets.Text(
                    value=str(effective_default),
                    description=f"{name}:",
                    style={'description_width': '150px'},
                    placeholder="[item1, item2, ...]"
                )
            elif isinstance(effective_default, dict):
                widget = widgets.Text(
                    value=str(effective_default),
                    description=f"{name}:",
                    style={'description_width': '150px'},
                    placeholder="{'key': 'value', ...}"
                )
            else:
                widget = widgets.Text(
                    value=str(effective_default) if effective_default is not None else "",
                    description=f"{name}:",
                    style={'description_width': '150px'},
                )

            # Add description tooltip if available
            if description:
                label = widgets.Label(
                    value=f"ℹ️  {description}",
                    layout=widgets.Layout(margin='0 0 5px 20px')
                )
                widget_list.append(widgets.VBox([widget, label]))
            else:
                widget_list.append(widget)

            collected[name] = widget

        # Display all widgets
        display(widgets.VBox(widget_list))

        # Add a submit button
        submit_button = widgets.Button(
            description='Apply Configuration',
            button_style='success',
            icon='check'
        )

        result_output = widgets.Output()

        def on_submit(b):
            with result_output:
                result_output.clear_output()
                print("✓ Configuration applied!")

        submit_button.on_click(on_submit)
        display(widgets.HBox([submit_button, result_output]))

        # Return a proxy object that reads widget values when accessed
        class WidgetProxy:
            def __init__(self, widgets_dict, arg_defs):
                self._widgets = widgets_dict
                self._arg_defs = {name: (default, desc) for name, default, desc in arg_defs}

            def get_values(self) -> Dict[str, Any]:
                result = {}
                for name, widget in self._widgets.items():
                    default_value = self._arg_defs[name][0]
                    value = widget.value

                    # Parse string values for collections
                    if isinstance(default_value, (list, tuple, dict)) and isinstance(value, str):
                        try:
                            import ast
                            parsed = ast.literal_eval(value)
                            # Convert back to original type
                            if isinstance(default_value, tuple):
                                value = tuple(parsed) if isinstance(parsed, (list, tuple)) else parsed
                            else:
                                value = parsed
                        except (ValueError, SyntaxError):
                            # Keep as string if parsing fails
                            pass

                    result[name] = value
                return result

        return WidgetProxy(collected, arg_definitions).get_values()

    def _collect_with_terminal(
        self,
        arg_definitions: List[Tuple[str, Any, str]],
        preset_values: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Collect arguments using terminal input prompts.

        Uses questionary for better UX if available, falls back to input().

        Args:
            arg_definitions: List of (name, default_value, description) tuples
            preset_values: Optional preset values

        Returns:
            Dictionary of collected values
        """
        preset_values = preset_values or {}

        # Try to use questionary for better UX
        try:
            import questionary
            return self._collect_with_questionary(arg_definitions, preset_values)
        except ImportError:
            # Fall back to basic input()
            return self._collect_with_input(arg_definitions, preset_values)

    def _collect_with_questionary(
        self,
        arg_definitions: List[Tuple[str, Any, str]],
        preset_values: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Collect arguments using questionary for rich terminal prompts.

        Args:
            arg_definitions: List of (name, default_value, description) tuples
            preset_values: Preset values

        Returns:
            Dictionary of collected values
        """
        import questionary
        from questionary import Style

        # Custom style
        custom_style = Style([
            ('qmark', 'fg:#5f87ff bold'),
            ('question', 'bold'),
            ('answer', 'fg:#00ff00 bold'),
            ('pointer', 'fg:#5f87ff bold'),
            ('selected', 'fg:#00ff00'),
        ])

        collected = {}

        print("\n" + "=" * 70)
        print("  Interactive Argument Configuration")
        print("=" * 70)
        print()

        for name, default_value, description in arg_definitions:
            # Get the effective default (preset overrides default)
            effective_default = preset_values.get(name, default_value)

            # Build message
            message = f"{name}"
            if description:
                message += f" ({description})"

            # Create appropriate prompt based on type
            if isinstance(effective_default, bool):
                answer = questionary.confirm(
                    message,
                    default=effective_default,
                    style=custom_style
                ).ask()
                collected[name] = answer

            elif isinstance(effective_default, (int, float)):
                def validate_number(text):
                    if not text:
                        return True  # Allow empty for default
                    try:
                        if isinstance(effective_default, int):
                            int(text)
                        else:
                            float(text)
                        return True
                    except ValueError:
                        return f"Please enter a valid {'integer' if isinstance(effective_default, int) else 'number'}"

                answer = questionary.text(
                    message,
                    default=str(effective_default) if effective_default is not None else "",
                    validate=validate_number,
                    style=custom_style
                ).ask()

                if answer:
                    collected[name] = int(answer) if isinstance(effective_default, int) else float(answer)
                else:
                    collected[name] = effective_default

            elif isinstance(effective_default, (list, tuple, dict)):
                def validate_collection(text):
                    if not text:
                        return True  # Allow empty for default
                    try:
                        import ast
                        ast.literal_eval(text)
                        return True
                    except (ValueError, SyntaxError):
                        return "Please enter a valid Python literal (list, tuple, or dict)"

                answer = questionary.text(
                    message,
                    default=str(effective_default),
                    validate=validate_collection,
                    style=custom_style
                ).ask()

                if answer:
                    import ast
                    parsed = ast.literal_eval(answer)
                    # Convert to original type
                    if isinstance(effective_default, tuple):
                        collected[name] = tuple(parsed) if isinstance(parsed, (list, tuple)) else parsed
                    else:
                        collected[name] = parsed
                else:
                    collected[name] = effective_default

            else:
                # String or other types
                answer = questionary.text(
                    message,
                    default=str(effective_default) if effective_default is not None else "",
                    style=custom_style
                ).ask()
                collected[name] = answer if answer else effective_default

        print("\n" + "=" * 70)
        print("  ✓ Configuration complete!")
        print("=" * 70 + "\n")

        return collected

    def _collect_with_input(
        self,
        arg_definitions: List[Tuple[str, Any, str]],
        preset_values: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Collect arguments using basic input() prompts.

        Fallback when questionary is not available.

        Args:
            arg_definitions: List of (name, default_value, description) tuples
            preset_values: Preset values

        Returns:
            Dictionary of collected values
        """
        collected = {}

        print("\n" + "=" * 70)
        print("  Interactive Argument Configuration")
        print("=" * 70)
        print("Press Enter to accept default value, or type a new value.\n")

        for name, default_value, description in arg_definitions:
            # Get the effective default (preset overrides default)
            effective_default = preset_values.get(name, default_value)

            # Build prompt
            if description:
                print(f"\n{name}: {description}")

            prompt = f"  {name}"
            if effective_default is not None:
                prompt += f" [{effective_default}]"
            prompt += ": "

            # Get user input
            user_input = input(prompt).strip()

            # Use default if empty
            if not user_input:
                collected[name] = effective_default
                continue

            # Parse input based on default type
            if isinstance(effective_default, bool):
                # Parse boolean
                collected[name] = user_input.lower() in ('true', 't', 'yes', 'y', '1')
            elif isinstance(effective_default, int):
                try:
                    collected[name] = int(user_input)
                except ValueError:
                    print(f"  ⚠️  Invalid integer, using default: {effective_default}")
                    collected[name] = effective_default
            elif isinstance(effective_default, float):
                try:
                    collected[name] = float(user_input)
                except ValueError:
                    print(f"  ⚠️  Invalid float, using default: {effective_default}")
                    collected[name] = effective_default
            elif isinstance(effective_default, (list, tuple, dict)):
                # Parse collection types
                try:
                    import ast
                    parsed = ast.literal_eval(user_input)
                    # Convert to original type
                    if isinstance(effective_default, tuple):
                        collected[name] = tuple(parsed) if isinstance(parsed, (list, tuple)) else parsed
                    else:
                        collected[name] = parsed
                except (ValueError, SyntaxError) as e:
                    print(f"  ⚠️  Invalid format, using default: {effective_default}")
                    collected[name] = effective_default
            else:
                # String or other types
                collected[name] = user_input

        print("\n" + "=" * 70)
        print("  ✓ Configuration complete!")
        print("=" * 70 + "\n")

        return collected
