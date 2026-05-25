# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict
"""Rich-based display for dual agent progress with per-phase panels."""

from __future__ import annotations

import sys
import time

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel

from rankevolve.src.server.config import UIConfig
from rankevolve.src.server.stream_bridge import StreamBridgeAdapter
from rankevolve.src.cli.chat_cli.ui.theme import ThemeManager


class DualAgentDisplay:
    """Rich-based display for dual agent progress with per-phase panels.

    Each phase gets its own Rich.Live panel. When a phase transition is
    detected (metadata.phase or metadata.agent_id changes), the current
    panel is finalized and printed permanently, then a new Live panel
    starts for the next phase.
    """

    def __init__(
        self,
        console: Console,
        theme: ThemeManager,
        ui_config: UIConfig,
    ) -> None:
        self._console = console
        self._theme = theme
        self._ui_config = ui_config

    async def stream_dual_agent_response(
        self,
        token_stream: StreamBridgeAdapter,
    ) -> str:
        """Display dual agent progress with per-phase streaming panels.

        Returns the full accumulated response text across all phases.
        """
        full_text = ""
        phase_text = ""
        current_phase: str | None = None
        current_agent: str | None = None
        chunk_count = 0
        accent = self._theme.colors.get("accent", "cyan")
        start_time = time.monotonic()

        sys.stderr.write("[dual_agent_display] Entering stream consumer\n")
        sys.stderr.flush()

        # Print static waiting message (Spinner requires Live to animate)
        self._console.print(
            "[dim]⏳ Connecting agents and preparing session...[/dim]"
        )

        live: Live | None = None

        try:
            async for chunk, metadata in token_stream:
                chunk_count += 1

                if chunk_count == 1:
                    elapsed = time.monotonic() - start_time
                    sys.stderr.write(
                        f"[dual_agent_display] First chunk received "
                        f"after {elapsed:.1f}s (len={len(chunk)}, "
                        f"phase={metadata.get('phase')}, "
                        f"agent={metadata.get('agent_id')})\n"
                    )
                    sys.stderr.flush()

                phase = metadata.get("phase")
                agent_id = metadata.get("agent_id")

                # Phase transition — finalize current panel, start new one
                if phase != current_phase or agent_id != current_agent:
                    if current_phase is not None:
                        if live is not None:
                            live.stop()
                            live = None
                        self._console.print(
                            Panel(
                                Markdown(phase_text),
                                title=(
                                    f"[green]✓[/green] {current_phase}"
                                    f" ({current_agent})"
                                ),
                                border_style="dim",
                            )
                        )
                        full_text += phase_text
                        phase_text = ""

                    current_phase = phase
                    current_agent = agent_id
                    # Start new Live for the new phase
                    live = Live(
                        transient=True,
                        console=self._console,
                        refresh_per_second=self._ui_config.streaming_refresh_hz,
                    )
                    live.start()

                phase_text += chunk

                # Show only the last N lines in the live panel for a "tail -f"
                # effect.  Without this, the Rich.Live panel grows beyond the
                # terminal height but stays pinned to its starting position,
                # making it look stuck at the top with no auto-scroll.
                MAX_VISIBLE_LINES = 40
                lines = phase_text.split("\n")
                if len(lines) > MAX_VISIBLE_LINES:
                    visible_text = (
                        f"... ({len(lines) - MAX_VISIBLE_LINES} lines above)\n"
                        + "\n".join(lines[-MAX_VISIBLE_LINES:])
                    )
                else:
                    visible_text = phase_text

                panel = Panel(
                    Markdown(visible_text),
                    title=f"{phase} ({agent_id})",
                    border_style=accent,
                )
                if live is not None:
                    live.update(panel)

        finally:
            if live is not None:
                live.stop()

        elapsed = time.monotonic() - start_time
        sys.stderr.write(
            f"[dual_agent_display] Stream ended. "
            f"Chunks={chunk_count}, elapsed={elapsed:.1f}s\n"
        )
        sys.stderr.flush()

        # Print final phase panel permanently
        if phase_text:
            full_text += phase_text
            self._console.print(
                Panel(
                    Markdown(phase_text),
                    title=(
                        f"[green]✓[/green] {current_phase} ({current_agent})"
                    ),
                    border_style="green",
                )
            )

        return full_text
