"""Standalone CLI for the project_onboarding executor."""
from openteam.bootstrap import ensure_siblings_on_path
ensure_siblings_on_path()

from pathlib import Path  # noqa: E402

from openteam.server.services.tool_cli import run_cli  # noqa: E402
from .executor import execute  # noqa: E402

_TOOL_JSON = Path(__file__).parent / "tool.json"


def main(argv=None) -> int:
    return run_cli(_TOOL_JSON, execute, argv=argv)


if __name__ == "__main__":
    raise SystemExit(main())
