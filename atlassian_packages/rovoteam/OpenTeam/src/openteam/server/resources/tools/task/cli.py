"""Standalone CLI for the task executor.

Driven entirely by tool.json so the CLI and slash-command formats stay in
sync. Adding a flag to tool.json makes it appear in both --help and /task.

Usage::

    python -m openteam.server.resources.tools.task "Build auth system" --plan
    python -m openteam.server.resources.tools.task "Write docs" --agent-config breakdown-multiflow-plan
    python -m openteam.server.resources.tools.task "Refactor API" --model opus
"""
from openteam.bootstrap import ensure_siblings_on_path
ensure_siblings_on_path()

from pathlib import Path  # noqa: E402

from openteam.server.services.tool_cli import run_cli  # noqa: E402
from .executor import execute  # noqa: E402

_TOOL_JSON = Path(__file__).parent / "tool.json"
_MODE_MUTEX = [{"--plan", "--execute", "--full", "--confirm"}]


def main(argv=None) -> int:
    return run_cli(_TOOL_JSON, execute, argv=argv, mutually_exclusive_groups=_MODE_MUTEX)


if __name__ == "__main__":
    raise SystemExit(main())
