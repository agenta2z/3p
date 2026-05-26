"""Generic tool.json-driven CLI scaffold.

Builds an argparse parser from a tool's tool.json file, then invokes the
tool's execute() function. Identical behavior across all tools that follow
the (executor, tool.json) pattern: task, role_setup, create_role.

Usage from a tool's cli.py::

    from openteam.server.services.tool_cli import run_cli
    from .executor import execute

    _TOOL_JSON = Path(__file__).parent / "tool.json"

    def main(argv=None):
        return run_cli(_TOOL_JSON, execute, argv=argv,
                       mutually_exclusive_groups=[{"--plan", "--execute", "--full", "--confirm"}])
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

ExecuteFn = Callable[[dict, dict], Awaitable[Any]]


def build_parser(
    tool_json_path: Path,
    *,
    mutually_exclusive_groups: Optional[list[set[str]]] = None,
) -> argparse.ArgumentParser:
    """Build an argparse parser from a tool.json file.

    ``mutually_exclusive_groups`` is a list of sets — each set names flags
    that can't appear together (e.g., ``{"--plan", "--execute", "--full"}``).
    """
    spec = json.loads(tool_json_path.read_text(encoding="utf-8"))
    p = argparse.ArgumentParser(
        prog=spec.get("name", "tool"),
        description=spec.get("description", ""),
        epilog="Examples:\n  " + "\n  ".join(spec.get("examples", [])) if spec.get("examples") else None,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    mutex_sets = mutually_exclusive_groups or []
    mutex_groups: dict[str, argparse._MutuallyExclusiveGroup] = {}
    for i, group in enumerate(mutex_sets):
        mg = p.add_mutually_exclusive_group()
        for flag in group:
            mutex_groups[flag] = mg

    for param in spec.get("parameters", []):
        name = param["name"]
        target: Any = mutex_groups.get(name, p)
        kwargs: dict[str, Any] = {}
        if param.get("description"):
            kwargs["help"] = param["description"]
        if param.get("choices"):
            kwargs["choices"] = param["choices"]

        ptype = param.get("type", "string")
        is_positional = param.get("positional", False)

        if ptype == "flag":
            kwargs["action"] = "store_true"
            kwargs["default"] = False
            target.add_argument(name, **kwargs)
        elif ptype == "int":
            kwargs["type"] = int
            if param.get("default") is not None:
                kwargs["default"] = param["default"]
            p.add_argument(name, **kwargs)
        elif ptype == "path":
            kwargs["type"] = str
            p.add_argument(name, **kwargs)
        elif param.get("repeatable"):
            kwargs["action"] = "append"
            p.add_argument(name, **kwargs)
        elif is_positional:
            if not param.get("required", False):
                kwargs["nargs"] = "?"
            p.add_argument(name, **kwargs)
        else:
            if param.get("default") is not None:
                kwargs["default"] = param["default"]
            p.add_argument(name, **kwargs)

    return p


def run_cli(
    tool_json_path: Path,
    execute_fn: ExecuteFn,
    *,
    argv: Optional[list[str]] = None,
    mutually_exclusive_groups: Optional[list[set[str]]] = None,
) -> int:
    """Build parser, parse args, run the executor, print results."""
    parser = build_parser(tool_json_path, mutually_exclusive_groups=mutually_exclusive_groups)
    ns = parser.parse_args(argv)

    arguments: dict[str, Any] = {}
    for k, v in vars(ns).items():
        if v is None or v is False:
            continue
        # CANONICAL CONVENTION (Option D, 2026-05-18):
        # `arguments` dict keys are ALWAYS underscored, matching Python/argparse
        # convention. CLI users still type --foo-bar (Unix dash form); argparse
        # already normalizes to foo_bar in `vars(ns)`. The slash dispatcher
        # (_parse_slash_args) also normalizes to underscores. Executors read
        # arguments["foo_bar"] (underscore) — single source of truth.
        # Defensive `.replace("-","_")` covers any edge case (e.g., dest with
        # explicit dash override) so the invariant holds unconditionally.
        arguments[k.replace("-", "_")] = v

    # v6 unified frontend session protocol: when the parent (TUI / MCP wrapper)
    # set OPENTEAM_SESSION_ID + OPENTEAM_SERVER_DIR, populate session_context
    # so tools land their workspaces under the right session dir. Empty dict
    # (Path A fallback) when no frontend context is present — today's CLI
    # behavior preserved.
    from openteam.server.services.frontend_context import build_frontend_session_context
    try:
        session_context: dict[str, Any] = build_frontend_session_context()
    except RuntimeError as e:
        # I9 fail-fast: Server Mode + missing session is a hard error.
        print(f"[cli] {e}", file=sys.stderr)
        return 2

    try:
        result = asyncio.run(execute_fn(arguments, session_context))
    except KeyboardInterrupt:
        print("\n[cli] cancelled", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"[cli] error: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    if hasattr(result, "result") and hasattr(result, "context_updates"):
        print(result.result or "", flush=True)
        ctx = result.context_updates or {}
    elif isinstance(result, dict):
        print(result.get("result") or result.get("text") or "", flush=True)
        ctx = result.get("context_updates") or {}
    else:
        print(str(result), flush=True)
        ctx = {}

    for key, value in sorted(ctx.items()):
        if (key.endswith("_path") or key.endswith("_dir")) and isinstance(value, str) and value:
            print(f"[{key}] {value}", file=sys.stderr)
    return 0
