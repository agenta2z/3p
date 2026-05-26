"""`openteam-mcp` CLI entry point. Calls bootstrap before any openteam.* import."""
from __future__ import annotations

from openteam.bootstrap import ensure_siblings_on_path
ensure_siblings_on_path(strict=True)

import logging  # noqa: E402

import typer  # noqa: E402

app = typer.Typer(add_completion=False, help="OpenTeam MCP server.")


@app.command("run")
def run(
    transport: str = typer.Option("stdio", help="stdio | http"),
    port: int = typer.Option(8765, help="Port (http transport only)"),
    tools: str = typer.Option("", help="Comma-separated subset of tool names; default = all"),
    log_level: str = typer.Option("INFO"),
) -> None:
    """Run the OpenTeam MCP server."""
    logging.basicConfig(level=log_level.upper())
    from openteam.mcp_server.server import create_openteam_server
    names = [t.strip() for t in tools.split(",") if t.strip()] or None
    server = create_openteam_server(tool_names=names)
    if transport == "stdio":
        server.run(transport="stdio")
    elif transport == "http":
        server.run(transport="http", port=port)
    else:
        raise typer.BadParameter(f"unknown transport: {transport}")


if __name__ == "__main__":
    app()
