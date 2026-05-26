"""Pipeline wiring for the project_onboarding tool.

Builds a **nested** ``BreakdownThenAggregateInferencer`` (two-level BTA)
that onboards an AI employee to a project by analyzing the project document,
identifying required skills/tools, and creating missing capabilities.

Reuses the inner BTA pipeline from ``role_setup`` (skill/tool creation,
research, investigation) via YAML ``_import_``. The outer breakdown uses
a project-specific task preamble; the aggregator produces a Project
Onboarding Report.

Usage::

    from openteam.server.resources.tools.project_onboarding import executor
    # Called via ToolDispatcher — see execute() below.
"""

import logging
import os
from pathlib import Path
from typing import Any, Optional

_logger = logging.getLogger(__name__)

_APP_TOOLS_DIR = Path(__file__).resolve().parent.parent.parent / "tools"
_APP_SKILLS_DIR = Path(__file__).resolve().parent.parent.parent / "skills"


def _scan_role_setup_artifacts(role_setup_path: str) -> dict[str, Any]:
    """Scan a role_setup output directory for pre-onboarding artifacts.

    Returns a dict with:
        role_name, role_doc_path, role_setup_path,
        existing_skills (list of names), existing_tools (list of names),
        role_context (summary string for the preamble template)
    """
    root = Path(role_setup_path).resolve()
    result: dict[str, Any] = {
        "role_setup_path": str(root),
        "role_name": "",
        "role_doc_path": "",
        "existing_skills": [],
        "existing_tools": [],
    }

    # Find role document (role_document.md or role_setup_report.md)
    for candidate in ("role_document.md", "role_setup_report.md"):
        doc_path = root / candidate
        if not doc_path.exists():
            doc_path = root / "outputs" / candidate
        if doc_path.exists():
            result["role_doc_path"] = str(doc_path)
            text = doc_path.read_text(encoding="utf-8")
            result["role_name"] = text.split("\n")[0].strip("# ").strip()
            break

    # Scan existing skills
    skills_dir = root / "skills"
    if not skills_dir.exists():
        skills_dir = root / "outputs" / "skills"
    if not skills_dir.exists():
        skills_dir = root / "outputs" / "final_deliverables" / "skills"
    if skills_dir.exists():
        result["existing_skills"] = sorted(
            d.name for d in skills_dir.iterdir() if d.is_dir()
        )

    # Scan existing tools
    tools_dir = root / "tools"
    if not tools_dir.exists():
        tools_dir = root / "outputs" / "tools"
    if not tools_dir.exists():
        tools_dir = root / "outputs" / "final_deliverables" / "tools"
    if tools_dir.exists():
        result["existing_tools"] = sorted(
            d.name for d in tools_dir.iterdir() if d.is_dir()
        )

    # Build role context summary
    parts = []
    if result["role_name"]:
        parts.append(f"Role: {result['role_name']}")
    if result["role_doc_path"]:
        parts.append(f"Role document: {result['role_doc_path']}")
    if result["existing_skills"]:
        parts.append(
            f"Existing skills ({len(result['existing_skills'])}): "
            + ", ".join(result["existing_skills"])
        )
    if result["existing_tools"]:
        parts.append(
            f"Existing tools ({len(result['existing_tools'])}): "
            + ", ".join(result["existing_tools"])
        )
    parts.append(f"Full role setup artifacts at: {root}")
    result["role_context"] = "\n".join(parts)

    _logger.info(
        "[project_onboarding] Scanned role_setup: role=%s, %d skills, %d tools",
        result["role_name"],
        len(result["existing_skills"]),
        len(result["existing_tools"]),
    )
    return result


async def execute(
    arguments: dict,
    session_context: dict,
) -> "ToolExecutionResult":
    """Generic entry point for ToolDispatcher — yaml-driven outer BTA pipeline.

    Arguments (from LLM tool call):
        project_document_path (str, required): Path to the project description document.
        --role-setup-path (str, optional): Path to the role_setup output directory
            containing pre-onboarding role artifacts (role doc, skills/, tools/, etc.).
        --artifacts-path (str, optional): Path to additional project/team artifacts directory.
        --max-facets (int, optional): Max outer facets (default 8).
        --max-inner-facets (int, optional): Max inner facets (default 5).

    session_context keys used:
        cloud_id, uct_token, email, working_dir, interactive, task_id
    """
    from agent_foundation.common.inferencers.agentic_inferencers.conversational.protocols import (
        ToolExecutionResult,
    )
    import agent_foundation.common.configs.registered_targets  # noqa: F401
    from python_utils.config_utils import load_config, instantiate

    from openteam.server.resources.tools.role_setup.executor import (
        format_available_tools_and_skills,
    )

    project_document_path = arguments.get("project_document_path", "")
    role_setup_path = arguments.get("role_setup_path", "")
    artifacts_path = arguments.get("artifacts_path", "")
    max_facets = int(arguments.get("max_facets", 8))
    max_inner_facets = int(
        arguments.get("max_inner_facets", 5)
    )

    # Allocate workspace via shared allocator (closes security bug: slash-path
    # previously set working_dir to src/openteam/server/ → outputs in source tree).
    from openteam.server.resources.tools._shared.workspace_allocator import (
        allocate_tool_workspace,
    )
    _sr = (session_context or {}).get("session_root", "")
    if _sr:
        _tasks_base = Path(_sr) / "tasks"
        _tasks_base.mkdir(parents=True, exist_ok=True)
        workspace = allocate_tool_workspace("project_onboarding", base_dir=_tasks_base)
    else:
        workspace = allocate_tool_workspace("project_onboarding", base_dir=None)

    yaml_path = Path(__file__).parent / "project_onboarding.yaml"

    overrides: dict = {
        "max_breakdown": max_facets,
        "worker_factory.skill_tool_creation.max_breakdown": max_inner_facets,
        "_template_manager.templates": str(
            Path(__file__).resolve().parent.parent.parent / "prompt_templates"
        ),
        "workspace.root": str(workspace),
    }

    cfg = load_config(str(yaml_path), overrides=overrides)
    inferencer = instantiate(cfg)

    try:
        from agent_foundation.ui.graph_reporter_factory import make_graph_reporter
        task_id = session_context.get("task_id", "")
        inferencer.graph_reporter = make_graph_reporter(session_context, task_id)
        if inferencer.graph_reporter is not None:
            _logger.info("[project_onboarding] graph_reporter attached: %s",
                         type(inferencer.graph_reporter).__name__)
    except Exception as exc:
        _logger.warning("[project_onboarding] graph_reporter attach failed: %s", exc)

    # Read project document
    project_doc_text = (
        Path(project_document_path).read_text(encoding="utf-8")
        if project_document_path
        else ""
    )
    project_name = (
        project_doc_text.split("\n")[0].strip("# ").strip()
        if project_doc_text
        else ""
    )
    project_doc_path = (
        str(Path(project_document_path).resolve())
        if project_document_path
        else ""
    )

    # Scan role_setup artifacts (optional — provides pre-onboarding context)
    role_artifacts: dict[str, Any] = {}
    if role_setup_path:
        role_artifacts = _scan_role_setup_artifacts(role_setup_path)

    role_name = role_artifacts.get("role_name", "")
    role_doc_path = role_artifacts.get("role_doc_path", "")

    # Resolve artifacts path
    resolved_artifacts_path = ""
    if artifacts_path:
        resolved_artifacts_path = str(Path(artifacts_path).resolve())

    available_tools_text = format_available_tools_and_skills(
        extra_tool_dirs=[_APP_TOOLS_DIR], extra_skill_dirs=[_APP_SKILLS_DIR]
    )

    # Inject runtime context into breakdown + worker partials
    extra_feed: dict[str, Any] = {
        "project_name": project_name,
        "project_doc_path": project_doc_path,
        "available_tools_skills": available_tools_text,
        # Inner templates (skill_tool_creation.jinja2 etc.) reference {{ role_name }}
        # and {{ role_doc_path }}. When role_setup artifacts are provided, use the
        # real role values; otherwise alias the project values so inner templates
        # still render.
        "role_name": role_name or project_name,
        "role_doc_path": role_doc_path or project_doc_path,
    }
    if resolved_artifacts_path:
        extra_feed["artifacts_path"] = resolved_artifacts_path
    if role_artifacts.get("role_context"):
        extra_feed["role_context"] = role_artifacts["role_context"]
    if role_artifacts.get("role_setup_path"):
        extra_feed["role_setup_path"] = role_artifacts["role_setup_path"]
    inferencer.template_extra_feed.update(extra_feed)

    result_text = await inferencer.ainfer(project_doc_text)

    context_updates: dict[str, str] = {}
    if working_dir:
        context_updates["project_onboarding_working_dir"] = str(working_dir)
        report_path = Path(working_dir) / "outputs" / "project_onboarding_report.md"
        if report_path.exists():
            context_updates["project_onboarding_report_path"] = str(report_path)
        skills_dir = Path(working_dir) / "outputs" / "skills"
        tools_dir = Path(working_dir) / "outputs" / "tools"
        knowledge_dir = Path(working_dir) / "outputs" / "knowledge"
        if skills_dir.exists():
            context_updates["skills_dir"] = str(skills_dir)
        if tools_dir.exists():
            context_updates["tools_dir"] = str(tools_dir)
        if knowledge_dir.exists():
            context_updates["knowledge_dir"] = str(knowledge_dir)
        association_path = (
            Path(working_dir) / "outputs" / "role_tool_association.json"
        )
        if association_path.exists():
            context_updates["role_tool_association_path"] = str(association_path)

    return ToolExecutionResult(
        result=str(result_text),
        context_updates=context_updates,
    )
