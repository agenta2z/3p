"""TIER-1: verify the openteam_task 'mode' Literal stays in sync with tool.json flags."""
from __future__ import annotations

import json
import typing
from pathlib import Path

from openteam.mcp_server.server import _WRAPPERS

_TASK_TOOL_JSON = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "openteam"
    / "server"
    / "resources"
    / "tools"
    / "task"
    / "tool.json"
)


def _get_mode_literals() -> set[str]:
    """Extract the Literal values from the 'mode' parameter of openteam_task."""
    hints = typing.get_type_hints(_WRAPPERS["openteam_task"])
    mode_type = hints["mode"]

    # Unwrap typing.Literal[...] -> args
    args = typing.get_args(mode_type)
    assert args, f"Could not extract Literal args from mode type: {mode_type}"
    return set(args)


def _get_tool_json_flag_names() -> set[str]:
    """Find the 4 mutex flag-type params in task/tool.json (plan, execute, full, confirm)."""
    tool_json = json.loads(_TASK_TOOL_JSON.read_text())
    flags = set()
    for p in tool_json.get("parameters", []):
        if p.get("type") == "flag" and p["name"].lstrip("-") in {
            "plan", "execute", "full", "confirm",
        }:
            flags.add(p["name"].lstrip("-"))
    return flags


class TestModeEnumComplete:
    def test_mode_literal_values(self):
        assert _get_mode_literals() == {"plan", "execute", "full", "confirm"}

    def test_mode_matches_tool_json_flags(self):
        mode_values = _get_mode_literals()
        flag_names = _get_tool_json_flag_names()
        assert mode_values == flag_names, (
            f"Mode Literal values {sorted(mode_values)} do not match "
            f"tool.json flag params {sorted(flag_names)}"
        )
