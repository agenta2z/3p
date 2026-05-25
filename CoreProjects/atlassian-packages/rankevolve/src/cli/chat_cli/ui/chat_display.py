# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict

from __future__ import annotations

from collections.abc import AsyncIterator

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner
from rich.text import Text

from rankevolve.src.server.config import UIConfig
from rankevolve.src.server.schema import ChatMessage
from rankevolve.src.cli.chat_cli.ui.theme import ThemeManager


class ChatDisplay:
    """Manages Rich terminal rendering for the chat conversation."""

    def __init__(
        self,
        console: Console,
        theme: ThemeManager,
        ui_config: UIConfig,
    ) -> None:
        self.console = console
        self.theme = theme
        self.ui_config = ui_config

    def render_message_panel(self, message: ChatMessage) -> Panel:
        """Render a single message as a bordered Rich Panel."""
        if message.role == "user":
            return Panel(
                Text(message.content),
                title=self.theme.user_icon,
                title_align="left",
                border_style=self.theme.user_border_color,
                width=self.ui_config.panel_width,
                padding=(0, 1),
            )
        else:
            return Panel(
                Markdown(message.content),
                title=self.theme.assistant_icon,
                title_align="left",
                border_style=self.theme.assistant_border_color,
                width=self.ui_config.panel_width,
                padding=(0, 1),
            )

    def render_welcome(self, welcome_md: str) -> None:
        """Print the welcome banner as rendered markdown."""
        self.console.print(Markdown(welcome_md))
        self.console.print()

    async def stream_assistant_response(
        self,
        token_iterator: AsyncIterator[str],
    ) -> str:
        """
        Stream tokens into a Rich Live panel, re-rendering markdown
        on each update.

        Flow:
        1. Show a Spinner before the first token arrives
        2. On each token, accumulate text and update the Live display
           with Panel(Markdown(accumulated))
        3. Rich's refresh_per_second throttles terminal redraws
        4. After streaming completes, Live exits (transient clears it),
           then we print the final panel permanently
        """
        accumulated = ""

        spinner_renderable = Spinner(
            self.theme.spinner_name,
            text="Thinking...",
            style=self.theme.assistant_border_color,
        )

        with Live(
            spinner_renderable,
            console=self.console,
            refresh_per_second=self.ui_config.streaming_refresh_hz,
            transient=True,
            vertical_overflow="visible",
        ) as live:
            async for token in token_iterator:
                accumulated += token
                panel = Panel(
                    Markdown(accumulated),
                    title=self.theme.assistant_icon,
                    title_align="left",
                    border_style=self.theme.assistant_border_color,
                    width=self.ui_config.panel_width,
                    padding=(0, 1),
                )
                live.update(panel)

        # Print the final panel permanently
        if accumulated:
            final_msg = ChatMessage(role="assistant", content=accumulated)
            self.console.print(self.render_message_panel(final_msg))

        return accumulated
