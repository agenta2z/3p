# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict

"""RankEvolve CLI client — thin queue-based client for the agent server."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from rich.console import Console

from agent_foundation.ui.interactive_base import (
    InteractionFlags,
)
from rankevolve.src.cli.chat_cli.ui.chat_display import ChatDisplay
from rankevolve.src.cli.chat_cli.ui.input_handler import InputHandler
from rankevolve.src.cli.chat_cli.ui.theme import ThemeManager
from rankevolve.src.server.shared_loader import load_theme, load_welcome_message
from rankevolve.src.utils.service_utils.client.queue_client_base import (
    QueueClientBase,
)

logger = logging.getLogger(__name__)


class RankEvolveCLIClient(QueueClientBase):
    """Queue-based CLI client for the RankEvolve agent server.

    Connects to a running server via its queue root path.
    Uses existing prompt-toolkit InputHandler and Rich display widgets.
    """

    def __init__(
        self,
        queue_root_path: str,
        session_id: str | None = None,
    ) -> None:
        super().__init__(
            queue_root_path=queue_root_path,
            session_id=session_id,
            session_type="cli",
        )
        self._console = Console()

    async def run(self) -> None:
        """Main REPL loop."""
        # Setup display
        theme_data = load_theme("default")
        theme = ThemeManager(theme_data)
        display = ChatDisplay(self._console, theme)

        welcome = load_welcome_message()
        display.render_welcome(welcome)

        # Query initial config
        self.send_message("config_query")

        input_handler = InputHandler()

        try:
            while True:
                user_input = await input_handler.get_input()

                if user_input is None:
                    self._console.print("\n[dim]Goodbye![/dim]")
                    break

                if not user_input:
                    continue

                # Determine message type
                if user_input.startswith("/"):
                    msg_type = "slash_command"
                else:
                    msg_type = "chat_message"

                self.send_message(msg_type, user_input)

                # Poll for responses
                await self._poll_responses(display)

        except KeyboardInterrupt:
            self._console.print("\n[dim]Goodbye![/dim]")
        finally:
            self.close()

    async def _poll_responses(self, display: Any) -> None:
        """Poll response queue and render to display."""
        while True:
            self._maybe_send_heartbeat()

            resp = await self.poll_one_response()
            if resp is None:
                if not self.is_server_alive():
                    self._console.print(
                        "[red]Server appears to be down. "
                        "Check the server process.[/red]"
                    )
                    break
                await asyncio.sleep(0.05)
                continue

            msg_type = resp.get("type", "")
            flag = resp.get("flag", "")

            if msg_type == "token_batch":
                for token in resp.get("tokens", []):
                    content = token.get("content", "")
                    self._console.print(content, end="")

            elif msg_type == "stream_end":
                self._console.print()  # newline after stream
                break

            elif msg_type == "command_response":
                message = resp.get("message", "")
                if message:
                    self._console.print(f"[dim]{message}[/dim]")
                if resp.get("config_changed"):
                    config = resp.get("updated_config", {})
                    for key, value in config.items():
                        self._console.print(f"[dim]{key}: {value}[/dim]")
                break

            elif msg_type == "config_update":
                config = resp.get("config", {})
                parts = []
                for key, value in config.items():
                    if value:
                        parts.append(f"{key}: {value}")
                if parts:
                    self._console.print(f"[dim]{' | '.join(parts)}[/dim]")

            elif msg_type == "task_status":
                status = resp.get("status", "")
                self._console.print(f"[dim]Task: {status}[/dim]")
                if status == "completed":
                    break

            elif msg_type == "error":
                self._console.print(f"[red]Error: {resp.get('message', '')}[/red]")
                break

            elif msg_type == "pending_input":
                content = resp.get("response", "")
                if content:
                    self._console.print(content)
                user_input = await asyncio.to_thread(input, "> ")
                # Use raw queue put — QueueInteractive._postprocess_input
                # expects {"user_input": ..., "session_id": ...} format
                self._queue_service.put(self._input_queue_id, {
                    "user_input": user_input,
                    "session_id": self._session_id,
                })

            elif flag and str(flag) == str(InteractionFlags.TurnCompleted):
                break

            elif msg_type == "pong":
                continue
