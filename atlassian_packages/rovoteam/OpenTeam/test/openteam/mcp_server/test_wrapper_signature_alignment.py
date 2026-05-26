"""TIER-1 CI preflight: wrapper function signatures stay aligned with tool.json schemas."""
from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from openteam.mcp_server.server import _WRAPPERS

# Locate the tool.json directory relative to the project source tree.
_TOOLS_DIR = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "openteam"
    / "server"
    / "resources"
    / "tools"
)

# Parameters intentionally omitted or collapsed in the wrapper layer.
_EXCEPTION_PARAMS = {
    "openteam_task": {"mode", "in_place"},
}


def _tool_dir_name(wrapper_name: str) -> str:
    """Map wrapper name -> tool directory name (strip 'openteam_' prefix)."""
    return wrapper_name.removeprefix("openteam_")


def _load_tool_json(wrapper_name: str) -> dict:
    tool_name = _tool_dir_name(wrapper_name)
    path = _TOOLS_DIR / tool_name / "tool.json"
    assert path.exists(), f"tool.json not found: {path}"
    return json.loads(path.read_text())


def _tool_json_param_names(tool_json: dict) -> dict[str, bool]:
    """Return {python_name: required} for each tool.json parameter."""
    result = {}
    for p in tool_json.get("parameters", []):
        raw_name = p["name"].lstrip("-").replace("-", "_")
        required = p.get("required", False)
        result[raw_name] = required
    return result


@pytest.mark.parametrize("wrapper_name", list(_WRAPPERS.keys()))
class TestWrapperSignatureAlignment:
    def test_wrapper_params_map_to_tool_json(self, wrapper_name: str):
        """Every wrapper param (minus exceptions) must exist in tool.json."""
        sig = inspect.signature(_WRAPPERS[wrapper_name])
        tool_json = _load_tool_json(wrapper_name)
        tj_params = _tool_json_param_names(tool_json)
        exceptions = _EXCEPTION_PARAMS.get(wrapper_name, set())

        for param_name in sig.parameters:
            if param_name in exceptions:
                continue
            assert param_name in tj_params, (
                f"Wrapper param '{param_name}' for {wrapper_name} "
                f"has no matching tool.json parameter. "
                f"tool.json params: {sorted(tj_params)}"
            )

    def test_required_tool_json_params_have_wrapper_param(self, wrapper_name: str):
        """Every required tool.json parameter must have a wrapper parameter."""
        sig = inspect.signature(_WRAPPERS[wrapper_name])
        tool_json = _load_tool_json(wrapper_name)
        tj_params = _tool_json_param_names(tool_json)
        exceptions = _EXCEPTION_PARAMS.get(wrapper_name, set())
        wrapper_params = set(sig.parameters.keys())

        for tj_name, required in tj_params.items():
            if not required:
                continue
            if tj_name in exceptions:
                continue
            assert tj_name in wrapper_params, (
                f"Required tool.json param '{tj_name}' for {wrapper_name} "
                f"has no wrapper parameter. "
                f"Wrapper params: {sorted(wrapper_params)}"
            )
