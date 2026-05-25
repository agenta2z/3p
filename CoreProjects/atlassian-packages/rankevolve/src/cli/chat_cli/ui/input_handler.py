# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict

from __future__ import annotations

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.keys import Keys

from rankevolve.src.cli.chat_cli.ui.theme import ThemeManager


class InputHandler:
    """Handles multi-line user input via prompt-toolkit."""

    def __init__(self, theme: ThemeManager) -> None:
        self.theme = theme
        self.bindings = KeyBindings()
        self._setup_bindings()
        self.session: PromptSession[str] = PromptSession(
            key_bindings=self.bindings,
            multiline=True,
            prompt_continuation="... ",
        )

    def _setup_bindings(self) -> None:
        @self.bindings.add(Keys.Enter, eager=True)
        def handle_enter(event: KeyPressEvent) -> None:
            """Enter submits the input."""
            buf = event.current_buffer
            buf.validate_and_handle()

        @self.bindings.add(Keys.Escape, Keys.Enter)
        def handle_escape_enter(event: KeyPressEvent) -> None:
            """Escape+Enter inserts a newline."""
            event.current_buffer.insert_text("\n")

        @self.bindings.add("c-o")
        def handle_ctrl_o(event: KeyPressEvent) -> None:
            """Ctrl+O inserts a newline (alternative)."""
            event.current_buffer.insert_text("\n")

    async def get_input(self) -> str | None:
        """
        Get user input. Returns None on Ctrl+C / Ctrl+D (exit signal).
        """
        try:
            prompt_text = HTML(
                f'<style fg="{self.theme.input_prompt_color}">'
                f"{self.theme.input_prompt}</style>"
            )
            text: str = await self.session.prompt_async(
                prompt_text,
            )
            return text.strip() if text else None
        except (EOFError, KeyboardInterrupt):
            return None
