"""FastMCP server exposing OpenTeam tools as in-process executor calls.

Pattern verified against acra-python/packages/mcp-atlassian-exp/src/atlassian_exp/main.py:
  - mcp = FastMCP("openteam")
  - mcp.add_tool(FunctionTool.from_function(wrapper))
"""
from __future__ import annotations
from typing import Any, Literal

from fastmcp import FastMCP
from fastmcp.tools import FunctionTool

from openteam.mcp_server.context import build_session_context
from openteam.mcp_server._helpers import to_dash_form, strip_unset, render_result


async def openteam_task(
    request: str,
    mode: Literal["plan", "execute", "full", "confirm"] = "full",
    agent_config: str = "breakdown-multiflow-plan-then-implement",
    model: Literal["opus[1m]", "opus", "sonnet", "haiku"] | None = None,
    override: list[str] | None = None,
    no_dual: bool = False,
    analysis: bool = False,
    multi_iter: bool = False,
    max_iterations: int = 3,
    resume: str | None = None,
    copy_workspace: bool = False,
    initial_plan: str | None = None,
) -> str:
    """Run an OpenTeam agent topology against a request.

    Long-running (typically 5-30 min). Subject to the MCP client's hardcoded
    295 s timeout. For long jobs prefer the /task slash command (subprocess,
    no MCP timeout).

    mode:
      - "plan"    : planner only.
      - "execute" : implementation only (needs initial_plan).
      - "full"    : plan-then-implement (default).
      - "confirm" : plan, wait for user confirmation, then implement.

    Workspace strategy:
      - default (copy_workspace=False): in-place.
      - copy_workspace=True: snapshot current dir into a new workspace.
    """
    if mode == "execute" and not initial_plan:
        raise ValueError(
            "openteam_task(mode='execute') requires initial_plan=<path>. "
            "Execute mode skips planning and runs implementation against an "
            "existing plan file."
        )

    from openteam.server.resources.tools.task.executor import execute as _exec

    mode_flags = {"plan": False, "execute": False, "full": False, "confirm": False}
    mode_flags[mode] = True

    raw = {
        "request": request, "agent_config": agent_config,
        **mode_flags,
        "model": model, "override": override,
        "no_dual": no_dual, "analysis": analysis,
        "multi_iter": multi_iter, "max_iterations": max_iterations,
        "resume": resume,
        "copy_workspace": copy_workspace,
        "initial_plan": initial_plan,
    }
    args = strip_unset(to_dash_form(raw))
    return render_result(await _exec(args, build_session_context()))


async def openteam_create_role(
    role_description: str,
    output_path: str | None = None,
    max_facets: int = 8,
) -> str:
    """Synthesize a role document from a free-form description."""
    from openteam.server.resources.tools.create_role.executor import execute as _exec
    args = strip_unset(to_dash_form({
        "role_description": role_description,
        "output_path": output_path,
        "max_facets": max_facets,
    }))
    return render_result(await _exec(args, build_session_context()))


async def openteam_role_setup(
    role_document_path: str,
    max_facets: int = 8,
    max_inner_facets: int = 5,
) -> str:
    """Decompose a role document into actionable setup steps."""
    from openteam.server.resources.tools.role_setup.executor import execute as _exec
    args = strip_unset(to_dash_form({
        "role_document_path": role_document_path,
        "max_facets": max_facets,
        "max_inner_facets": max_inner_facets,
    }))
    return render_result(await _exec(args, build_session_context()))


async def openteam_project_onboarding(
    project_document_path: str,
    role_setup_path: str | None = None,
    artifacts_path: str | None = None,
    max_facets: int = 8,
    max_inner_facets: int = 5,
) -> str:
    """Onboard an AI employee to a project."""
    from openteam.server.resources.tools.project_onboarding.executor import execute as _exec
    args = strip_unset(to_dash_form({
        "project_document_path": project_document_path,
        "role_setup_path": role_setup_path,
        "artifacts_path": artifacts_path,
        "max_facets": max_facets,
        "max_inner_facets": max_inner_facets,
    }))
    return render_result(await _exec(args, build_session_context()))


_WRAPPERS: dict[str, Any] = {
    "openteam_task":               openteam_task,
    "openteam_create_role":        openteam_create_role,
    "openteam_role_setup":         openteam_role_setup,
    "openteam_project_onboarding": openteam_project_onboarding,
}


def create_openteam_server(tool_names: list[str] | None = None) -> FastMCP:
    """Create and configure a FastMCP server for the OpenTeam tools."""
    mcp = FastMCP("openteam")
    enabled = set(tool_names) if tool_names else set(_WRAPPERS)
    invalid = enabled - set(_WRAPPERS)
    if invalid:
        raise ValueError(f"Unknown tool names: {sorted(invalid)}; available: {sorted(_WRAPPERS)}")
    for name, wrapper in _WRAPPERS.items():
        if name not in enabled:
            continue
        mcp.add_tool(FunctionTool.from_function(wrapper))
    return mcp
