# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict

from __future__ import annotations

from rich.style import Style
from rich.theme import Theme as RichTheme


class ThemeManager:
    """Loads shared theme JSON and exposes Rich styles."""

    def __init__(self, theme_data: dict[str, object]) -> None:
        self.colors: dict[str, str] = theme_data.get("colors", {})  # pyre-ignore[8]
        self.symbols: dict[str, str] = theme_data.get("symbols", {})  # pyre-ignore[8]

    def get_rich_theme(self) -> RichTheme:
        return RichTheme(
            {
                "user.border": Style(
                    color=self.colors.get("user_panel_border", "#5f87ff")
                ),
                "assistant.border": Style(
                    color=self.colors.get("assistant_panel_border", "#5faf5f")
                ),
                "error": Style(color=self.colors.get("error_text", "#ff5f5f")),
                "spinner": Style(color=self.colors.get("spinner", "#ffaf00")),
            }
        )

    @property
    def user_border_color(self) -> str:
        return self.colors.get("user_panel_border", "#5f87ff")

    @property
    def assistant_border_color(self) -> str:
        return self.colors.get("assistant_panel_border", "#5faf5f")

    @property
    def user_icon(self) -> str:
        return self.symbols.get("user_icon", "You")

    @property
    def assistant_icon(self) -> str:
        return self.symbols.get("assistant_icon", "Assistant")

    @property
    def spinner_name(self) -> str:
        return self.symbols.get("thinking_spinner", "dots")

    @property
    def input_prompt(self) -> str:
        return self.symbols.get("input_prompt", "> ")

    @property
    def input_prompt_color(self) -> str:
        return self.colors.get("input_prompt", "#5f87ff")
