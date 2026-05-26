"""Pipeline wiring for the role_setup tool.

Builds a **nested** ``BreakdownThenAggregateInferencer`` (two-level BTA):

Outer BTA — Role Setup:
  - **Breakdown**: Analyzes role document + available tools → identifies missing
    skills/tools as setup tasks. Uses ``role_setup`` task_preamble.
  - **Workers**: Each worker is an **inner BTA** that creates one skill/tool:
      - Inner Breakdown: decomposes skill/tool creation into research facets
      - Inner Workers: researches each facet via deep_research
      - Inner Aggregator: synthesizes → implementable tool specification
  - **Aggregator**: Synthesizes all tool specs → Role Setup Report.

Phases use **task_breakdown** and **deep_research** for decomposition and workers,
and **implementation/main** for both aggregators (prompt shell). Aggregation
**instructions** are not inlined: the prompt points at the on-disk
``_variables/task_instructions/*.jinja2`` files under **implementation** so local
agents read the full text from the path.

  - ``task_preamble/role_setup.jinja2`` — outer breakdown context
  - ``implementation/.../task_instructions/aggregation/role_setup.jinja2`` — outer aggregation (via master_version)
  - ``task_preamble/skill_tool_creation.jinja2`` — inner breakdown context
  - ``deep_research/.../task_preamble/skill_tool_creation_*.jinja2`` — inner workers
  - ``implementation/.../task_instructions/skill_tool_creation.jinja2`` — inner aggregation (by path)

Usage::

    from openteam.server.resources.tools.role_setup import build_role_setup_inferencer

    inferencer = build_role_setup_inferencer(
        role_document_path="/path/to/program_manager_role.md",
        cloud_id="my-cloud-id",
        uct_token="my-uct-token",
    )
    result = await inferencer.ainfer(role_document_text)
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Optional

from attr import attrib, attrs
from jinja2 import Template

from agent_foundation.common.inferencers.agentic_inferencers.flow_inferencers.breakdown_then_aggregate_inferencer import (
    BreakdownThenAggregateInferencer,
)
from agent_foundation.common.inferencers.inferencer_base import InferencerBase
from agent_foundation.common.inferencers.agentic_inferencers.external.rovodev.rovodev_cli_inferencer import (
    RovoDevCliInferencer,
)
from agent_foundation.common.response_parsers import extract_delimited
from python_utils.string_utils.formatting.template_manager import TemplateManager

# Reuse from create_role — shared infrastructure
from openteam.server.resources.tools.create_role.executor import (
    parse_breakdown_response,
    _build_template_manager,
    _make_rovochat,
)

_logger = logging.getLogger(__name__)

# Root of all prompt templates (shared with create_role).
_PROMPT_TEMPLATES_ROOT = (
    Path(__file__).resolve().parent.parent.parent / "prompt_templates"
)

# AgentFoundation fallback templates root (for multi-root TemplateManager).
import agent_foundation.resources as _af_res
_AF_TEMPLATES_ROOT = Path(_af_res.__file__).parent / "prompt_templates"

# Application-level resources directories (tools & skills moved from framework)
_APP_TOOLS_DIR = Path(__file__).resolve().parent.parent.parent / "tools"
_APP_SKILLS_DIR = Path(__file__).resolve().parent.parent.parent / "skills"


# ---------------------------------------------------------------------------
# Variable file loader
# ---------------------------------------------------------------------------


def _load_variable_file(
    space: str, var_name: str, variant: str = "default"
) -> str:
    """Read a ``_variables/`` template file by variant name.

    E.g., _load_variable_file("task_breakdown", "task_preamble", "role_setup")
    reads ``task_breakdown/main/_variables/task_preamble/role_setup.jinja2``.
    """
    path = (
        _PROMPT_TEMPLATES_ROOT
        / space
        / "main"
        / "_variables"
        / var_name
        / f"{variant}.jinja2"
    )
    if not path.is_file():
        raise FileNotFoundError(f"Variable template not found: {path}")
    return path.read_text(encoding="utf-8")


def _variable_file_path(
    templates_root: Path,
    space: str,
    var_name: str,
    variant: str,
) -> Path:
    """Absolute path to ``<space>/main/_variables/<var_name>/<variant>.jinja2``."""
    return (
        Path(templates_root).resolve()
        / space
        / "main"
        / "_variables"
        / var_name
        / f"{variant}.jinja2"
    )


def _aggregation_instructions_from_path(
    templates_root: Path,
    space: str,
    var_name: str,
    variant: str,
) -> str:
    """Prompt text that tells the agent to read aggregation rules from a file path.

    The aggregator prompt does **not** embed the contents of the variable file;
    local agents (e.g. RovoDevCli) open the path and follow the instructions there.
    """
    path = _variable_file_path(templates_root, space, var_name, variant)
    if not path.is_file():
        raise FileNotFoundError(f"Aggregation instructions template not found: {path}")
    return (
        "Read the complete aggregation instructions from this file on disk and follow "
        "them exactly (open and read the file; do not guess requirements from the path "
        "string alone):\n"
        f"`{path}`"
    )


def _render_variable_file(
    space: str, var_name: str, variant: str, **kwargs: Any
) -> str:
    """Load a ``_variables/`` template file and render its Jinja2 variables.

    The file may contain ``{{ var }}`` placeholders (e.g., ``{{ role_name }}``,
    ``{{ available_tools_skills }}``). Since we pass the rendered string as an
    extra_feed override (not through TemplateManager's auto-resolution), we
    must pre-render these variables ourselves.
    """
    raw = _load_variable_file(space, var_name, variant)
    return Template(raw).render(**kwargs)


# ---------------------------------------------------------------------------
# FeedOverridePromptWrapper removed — template rendering now built into InferencerBase
# Use template_manager, template_key, template_root_space, template_extra_feed
# directly on any inferencer.


# ---------------------------------------------------------------------------
# Available tools formatter
# ---------------------------------------------------------------------------


def format_available_tools_and_skills(
    tools_file: Optional[str] = None,
    extra_tool_dirs: Optional[list] = None,
    extra_skill_dirs: Optional[list] = None,
) -> str:
    """Format available tools and skills as a concise name + path listing.

    Only outputs tool/skill names and their definition file paths — the LLM
    can read the full definition if needed. This keeps prompt tokens minimal.

    If ``tools_file`` is provided, reads from that file verbatim.

    Args:
        tools_file: Path to a pre-formatted tools file (used as-is).
        extra_tool_dirs: Additional directories to scan for tool.json files.
        extra_skill_dirs: Additional directories to scan for SKILL.md files.
    """
    if tools_file:
        path = Path(tools_file)
        if path.is_file():
            return path.read_text(encoding="utf-8")
        _logger.warning("Tools file not found: %s — falling back to registries", tools_file)

    sections = []

    # --- Tools (name + path to tool.json) ---
    try:
        from agent_foundation.resources.tools.registry import load_all_tools

        tools = load_all_tools(extra_dirs=extra_tool_dirs)
    except ImportError:
        _logger.warning("Could not load tool registry")
        tools = {}

    if tools:
        # Group tools by parent directory to avoid repeating paths
        from collections import defaultdict
        groups: dict[str, list[str]] = defaultdict(list)
        for name, td in sorted(tools.items()):
            if td.source_path:
                parent = str(Path(td.source_path).parent.parent)
            else:
                parent = "(unknown)"
            groups[parent].append(name)

        lines = ["### Tools"]
        for root_path, tool_names in groups.items():
            lines.append(f"**{root_path}/**:")
            lines.append(", ".join(tool_names))
        sections.append("\n".join(lines))

    # --- Skills (name + path to SKILL.md) ---
    try:
        from agent_foundation.resources.skills.registry import load_all_skills

        skills = load_all_skills(extra_dirs=extra_skill_dirs)
    except ImportError:
        _logger.warning("Could not load skill registry")
        skills = {}

    if skills:
        from collections import defaultdict
        groups: dict[str, list[str]] = defaultdict(list)
        for name, si in sorted(skills.items()):
            if si.file_path:
                parent = str(Path(si.file_path).parent.parent)
            else:
                parent = "(unknown)"
            groups[parent].append(name)

        lines = ["### Skills"]
        for root_path, skill_names in groups.items():
            lines.append(f"**{root_path}/**:")
            lines.append(", ".join(skill_names))
        sections.append("\n".join(lines))

    if not sections:
        return "(No tools or skills currently registered)"

    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Breakdown-only builder (for step-by-step testing)
# ---------------------------------------------------------------------------


def build_breakdown_only(
    role_document_path: str,
    cloud_id: str = "",
    uct_token: Optional[str] = None,
    email: Optional[str] = None,
    api_token: Optional[str] = None,
    base_url: Optional[str] = None,
    agent_named_id: Optional[str] = None,
    templates_dir: Optional[str] = None,
    tools_file: Optional[str] = None,
    streaming_cache_dir: Optional[str] = None,
    workspace_root: Optional[str] = None,
    inferencer_logger: Optional[Any] = None,
) -> tuple:
    """Build only the outer breakdown inferencer for step-by-step testing.

    Returns:
        (breakdown_inferencer, inference_input) — call
        ``await breakdown_inf.ainfer(inference_input)`` to get the
        breakdown JSON with setup subtasks.
    """
    tm = _build_template_manager(templates_dir)

    # Read role document
    role_doc_path = str(Path(role_document_path).resolve())
    role_doc_text = Path(role_doc_path).read_text(encoding="utf-8")
    role_name = role_doc_text.split("\n")[0].strip("# ").strip()

    # Format available tools
    available_tools_text = format_available_tools_and_skills(
        tools_file, extra_tool_dirs=[_APP_TOOLS_DIR], extra_skill_dirs=[_APP_SKILLS_DIR]
    )

    # Pre-render the breakdown preamble (it has {{ role_name }}, etc.)
    outer_breakdown_preamble = _render_variable_file(
        "task_breakdown", "task_preamble", "role_setup",
        role_name=role_name,
        role_doc_path=role_doc_path,
        available_tools_skills=available_tools_text,
    )

    # Auth kwargs
    rovo_kwargs: dict[str, Any] = dict(
        cloud_id=cloud_id,
        uct_token=uct_token,
        email=email,
        api_token=api_token,
        base_url=base_url,
        agent_named_id=agent_named_id,
    )
    if streaming_cache_dir:
        rovo_kwargs["cache_folder"] = streaming_cache_dir

    # Build breakdown inferencer — uses RovoDevCliInferencer for local file access
    rovodev_kwargs: dict[str, Any] = dict(yolo=True, debug_mode=True)
    if workspace_root:
        rovodev_kwargs["target_path"] = workspace_root
    if inferencer_logger is not None:
        rovodev_kwargs["logger"] = inferencer_logger
    breakdown_inf = RovoDevCliInferencer(
        **rovodev_kwargs,
        template_manager=tm,
        template_key="initial",
        template_root_space="task_breakdown",
        template_extra_feed={"task_preamble": outer_breakdown_preamble},
    )

    # Wrap in BTA with breakdown_only=True for proper workspace/checkpoint support
    bta_kwargs: dict[str, Any] = dict(
        breakdown_inferencer=breakdown_inf,
        breakdown_parser=parse_breakdown_response,
        breakdown_only=True,
        worker_factory=lambda sub_query, index: None,  # unused in breakdown_only
        workspace_root=workspace_root,
        debug_mode=True,
    )
    if inferencer_logger is not None:
        bta_kwargs["logger"] = inferencer_logger
    bta = BreakdownThenAggregateInferencer(**bta_kwargs)

    # Inference input = role name only (becomes {{ input }} in the template).
    # The full document is referenced via {{ role_doc_path }} in the preamble —
    # RovoDevCliInferencer has local file access and will read it directly.
    inference_input = role_name

    _logger.info(
        "Breakdown-only built (via BTA): role=%s (%d chars), tools=%d chars",
        role_name, len(role_doc_text), len(available_tools_text),
    )

    return bta, inference_input


# ---------------------------------------------------------------------------
# Inner BTA factory (one per missing skill/tool)
# ---------------------------------------------------------------------------


_DEFAULT_WORKER_QUERY_FIELDS = ("description", "todos")


def parse_inner_breakdown_response(
    raw_output: str,
    worker_query_fields: tuple[str, ...] = _DEFAULT_WORKER_QUERY_FIELDS,
) -> list:
    """Parse inner BTA breakdown into structured sub_queries.

    Returns List[dict] with ``query`` and ``args`` keys so BTA can dispatch
    to heterogeneous worker factories via ``task_type_arg_name``.

    Args:
        raw_output: Raw LLM response with JSON subtasks.
        worker_query_fields: Which subtask fields to include in the worker query.
            Defaults to ("description", "todos"). Other useful fields:
            "scope", "priority", "priority_reason", "subtask_dependencies".
    """
    from agent_foundation.common.inferencers.agentic_inferencers.flow_inferencers.breakdown_then_aggregate_inferencer import (
        parse_numbered_list,
    )

    response_text = extract_delimited(str(raw_output))

    json_match = re.search(
        r"```json[^\n{]*(\{[\s\S]*\})\s*```", response_text
    )
    if not json_match:
        json_match = re.search(
            r'\{[\s\S]*"subtasks"[\s\S]*\}', response_text
        )
        if json_match:
            json_str = json_match.group(0)
        else:
            _logger.warning("No JSON in inner breakdown, falling back to numbered list")
            return parse_numbered_list(response_text)
    else:
        json_str = json_match.group(1)

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        _logger.warning("Inner JSON parse failed (%s), falling back", e)
        return parse_numbered_list(response_text)

    subtasks = data.get("subtasks") or []
    if not subtasks:
        return parse_numbered_list(response_text)

    queries = []
    for subtask in subtasks:
        desc = subtask.get("description", "")
        todos = subtask.get("todos") or []
        scope = subtask.get("scope", "")
        priority = subtask.get("priority", "")
        deps = subtask.get("subtask_dependencies") or []
        args = subtask.get("args", {})
        task_preamble = args.get("task_preamble", "skill_tool_creation_research")

        # Build markdown-structured query using selected fields
        parts = []
        if "description" in worker_query_fields and desc:
            parts.append(f"**Description**: {desc}")
        if "scope" in worker_query_fields and scope:
            parts.append(f"**Scope**: {scope}")
        if "priority" in worker_query_fields and priority:
            parts.append(f"**Priority**: {priority}")
        if "subtask_dependencies" in worker_query_fields and deps:
            parts.append(f"**Dependencies**: subtasks {', '.join(str(d) for d in deps)}")
        if "todos" in worker_query_fields and todos:
            todo_lines = "\n".join(f"- {t}" for t in todos)
            parts.append(f"**Todos**:\n{todo_lines}")
        query_text = "\n\n".join(parts)

        if query_text.strip():
            query_args = {"task_preamble": task_preamble}
            # Include todos and description in args for BTA's expand_todos feature
            if todos:
                query_args["todos"] = todos
            if desc:
                query_args["description"] = desc
            queries.append({
                "query": query_text.strip(),
                "args": query_args,
            })

    if not queries:
        return parse_numbered_list(response_text)

    research_count = sum(1 for q in queries if "research" in q["args"]["task_preamble"])
    investigation_count = sum(1 for q in queries if "investigation" in q["args"]["task_preamble"])
    _logger.info(
        "Parsed %d inner subtasks: %d research, %d investigation",
        len(queries), research_count, investigation_count,
    )
    return queries


def _build_inner_bta(
    sub_query: str,
    index: int,
    tm: Any,
    rovo_kwargs: dict,
    inner_breakdown_preamble: str,
    inner_research_preamble: str,
    inner_synthesis_instructions: str,
    max_inner_facets: int,
    aggregator_type: str,
    aggregator_working_dir: Optional[str],
    streaming_cache_dir: Optional[str],
    breakdown_only: bool = False,
    workspace_root: Optional[str] = None,
    inferencer_logger: Optional[Any] = None,
    templates_root: Optional[Path] = None,
    role_name: str = "",
    role_doc_path: str = "",
    available_tools_text: str = "",
) -> BreakdownThenAggregateInferencer:
    """Build an inner BTA for creating one skill/tool.

    The inner BTA follows the same pattern as create_role:
    - Breakdown: decompose skill/tool creation into research facets
    - Workers: research each facet (deep_research template)
    - Aggregator: synthesize into skill/tool spec (**implementation** prompt shell;
      instructions via on-disk path, not inlined).
    """
    if templates_root is None:
        templates_root = _PROMPT_TEMPLATES_ROOT
    _logger.info(
        "Building inner BTA (worker %d) for: %.80s...", index, sub_query
    )

    # Inner breakdown
    inner_rovo_kwargs = dict(rovo_kwargs)
    if streaming_cache_dir:
        inner_rovo_kwargs["cache_folder"] = streaming_cache_dir

    # Inner breakdown uses RovoDevCliInferencer for local file access
    rovodev_kwargs: dict[str, Any] = dict(yolo=True, debug_mode=True)
    if workspace_root:
        rovodev_kwargs["target_path"] = workspace_root
    if streaming_cache_dir:
        rovodev_kwargs["cache_folder"] = streaming_cache_dir
    if inferencer_logger is not None:
        rovodev_kwargs["logger"] = inferencer_logger
    breakdown_inf = RovoDevCliInferencer(
        **rovodev_kwargs,
        template_manager=tm,
        template_key="initial",
        template_root_space="task_breakdown",
        template_extra_feed={"task_preamble": inner_breakdown_preamble},
    )

    # Inner worker factories — heterogeneous dispatch via task_preamble
    def _make_worker(sub_query: str, index: int, preamble_name: str, use_rovodev: bool):
        """Create a worker inferencer with the right preamble and engine."""
        preamble_path = (
            templates_root / "deep_research" / "main" / "_variables"
            / "task_preamble" / f"{preamble_name}.jinja2"
        )
        if preamble_path.exists():
            worker_preamble = Template(preamble_path.read_text(encoding="utf-8")).render(role_name=role_name, role_doc_path=role_doc_path, available_tools_skills=available_tools_text)
        else:
            _logger.warning("Preamble %s not found, using default", preamble_name)
            worker_preamble = inner_research_preamble

        if use_rovodev:
            _logger.info("  Inner worker %d (INVESTIGATION/%s): %.60s...", index, preamble_name, sub_query)
            rovodev_worker_kwargs: dict[str, Any] = dict(yolo=True, debug_mode=True)
            if workspace_root:
                rovodev_worker_kwargs["target_path"] = workspace_root
            if streaming_cache_dir:
                rovodev_worker_kwargs["cache_folder"] = streaming_cache_dir
            if inferencer_logger is not None:
                rovodev_worker_kwargs["logger"] = inferencer_logger
            worker_inf = RovoDevCliInferencer(**rovodev_worker_kwargs)
        else:
            _logger.info("  Inner worker %d (RESEARCH/%s): %.60s...", index, preamble_name, sub_query)
            worker_inf = _make_rovochat(**inner_rovo_kwargs)
            worker_inf.debug_mode = True
            if inferencer_logger is not None:
                worker_inf.logger = inferencer_logger

        # Set template attrs directly on the worker inferencer
        worker_inf.template_manager = tm
        worker_inf.template_key = "initial"
        worker_inf.template_root_space = "deep_research"
        worker_inf.template_extra_feed = {"task_preamble": worker_preamble}
        worker_inf.output_path = f"facet_{index}.md"
        worker_inf.debug_mode = True
        return worker_inf

    def research_worker_factory(sub_query: str, index: int):
        return _make_worker(sub_query, index, "skill_tool_creation_research", use_rovodev=False)

    def investigation_worker_factory(sub_query: str, index: int):
        return _make_worker(sub_query, index, "skill_tool_creation_investigation", use_rovodev=True)

    inner_worker_factory = {
        "skill_tool_creation_research": {
            "factory": research_worker_factory,
            "expand_todos": True,  # RovoChat handles one focused query better
        },
        "skill_tool_creation_investigation": {
            "factory": investigation_worker_factory,
            "expand_todos": False,  # RovoDevCli can handle full todo lists
        },
        "__default__": {"factory": research_worker_factory, "expand_todos": True},
    }

    # Inner aggregator — uses modern BTA template path
    if aggregator_type == "rovodev":
        agg_kwargs = dict(
            target_path=aggregator_working_dir or ".",
            yolo=True,
        )
        if streaming_cache_dir:
            agg_kwargs["cache_folder"] = streaming_cache_dir
        if inferencer_logger is not None:
            agg_kwargs["logger"] = inferencer_logger
        inner_aggregator = RovoDevCliInferencer(**agg_kwargs)
    else:
        inner_aggregator = _make_rovochat(**inner_rovo_kwargs)

    # Wire template infrastructure for inner aggregator
    # NOTE: do NOT set template_version — SLOT_DEFAULTS sets it to "aggregation"
    # and re-applies during BTA execution. Use per-variable override instead.
    inner_aggregator.template_manager = tm
    inner_aggregator.template_key = "initial"
    inner_aggregator.template_root_space = "implementation"
    inner_aggregator.template_master_version = "aggregation"
    inner_aggregator.template_variables = {
        "task_preamble": None,
        "task_instructions": "role_setup",
        "task_response_format": None,
    }

    bta_kwargs: dict[str, Any] = dict(
        name=f"inner_bta_{index}",
        breakdown_inferencer=breakdown_inf,
        breakdown_parser=parse_inner_breakdown_response,
        worker_factory=inner_worker_factory,
        task_type_arg_name="task_preamble",
        group_max_concurrency={
            "skill_tool_creation_research": 3,
            "skill_tool_creation_investigation": 2,
        },
        aggregator_inferencer=inner_aggregator,
        max_breakdown=max_inner_facets,
        max_concurrency=None,
        breakdown_only=breakdown_only,
        debug_mode=True,
        # output_path enables _finalize_response to copy aggregator
        # deliverables (e.g. SKILL.md) from children/aggregator/outputs/
        # to the root workspace outputs/.
        output_path=f"skill_tool_spec_worker_{index}.md",
    )
    if workspace_root:
        # Use a full InferencerWorkspace (not bare workspace_root) so that
        # use_final_deliverables_folder=True is honoured — deliverables (skills/,
        # tools/) go to outputs/final_deliverables/ instead of outputs/ directly.
        from agent_foundation.common.inferencers.inferencer_workspace import (
            InferencerWorkspace,
        )
        bta_kwargs["workspace"] = InferencerWorkspace(
            root=workspace_root,
            use_final_deliverables_folder=True,
        )
    if inferencer_logger is not None:
        bta_kwargs["logger"] = inferencer_logger
    return BreakdownThenAggregateInferencer(**bta_kwargs)


# ---------------------------------------------------------------------------
# Main factory
# ---------------------------------------------------------------------------


def build_role_setup_inferencer(
    role_document_path: str,
    cloud_id: str = "",
    uct_token: Optional[str] = None,
    email: Optional[str] = None,
    api_token: Optional[str] = None,
    base_url: Optional[str] = None,
    agent_named_id: Optional[str] = None,
    max_facets: int = 8,
    max_inner_facets: int = 5,
    templates_dir: Optional[str] = None,
    aggregator_type: str = "rovochat",
    aggregator_working_dir: Optional[str] = None,
    workspace_root: Optional[str] = None,
    tools_file: Optional[str] = None,
) -> tuple:
    """Build a nested BTA inferencer for role setup.

    Returns:
        (outer_bta, inference_input) tuple.
    """
    tm = _build_template_manager(templates_dir)

    # Read role document
    role_doc_path = str(Path(role_document_path).resolve())
    role_doc_text = Path(role_doc_path).read_text(encoding="utf-8")
    role_name = role_doc_text.split("\n")[0].strip("# ").strip()

    # Format available tools
    available_tools_text = format_available_tools_and_skills(
        tools_file, extra_tool_dirs=[_APP_TOOLS_DIR], extra_skill_dirs=[_APP_SKILLS_DIR]
    )

    # Pre-render outer breakdown preamble (has {{ role_name }}, etc.)
    outer_breakdown_preamble = _render_variable_file(
        "task_breakdown", "task_preamble", "role_setup",
        role_name=role_name,
        role_doc_path=role_doc_path,
        available_tools_skills=available_tools_text,
    )
    templates_root_resolved = (
        Path(templates_dir).resolve() if templates_dir else _PROMPT_TEMPLATES_ROOT.resolve()
    )
    outer_synthesis_instructions = _aggregation_instructions_from_path(
        templates_root_resolved,
        "implementation",
        "task_instructions",
        "role_setup",
    )
    inner_breakdown_preamble = _load_variable_file(
        "task_breakdown", "task_preamble", "skill_tool_creation"
    )
    inner_research_preamble = _load_variable_file(
        "deep_research", "task_preamble", "skill_tool_creation"
    )
    inner_synthesis_instructions = _aggregation_instructions_from_path(
        templates_root_resolved,
        "implementation",
        "task_instructions",
        "skill_tool_creation",
    )

    # Format available tools
    available_tools_text = format_available_tools_and_skills(
        extra_tool_dirs=[_APP_TOOLS_DIR], extra_skill_dirs=[_APP_SKILLS_DIR]
    )

    # Build workspace directories
    streaming_cache_dir: Optional[str] = None
    if workspace_root:
        streaming_cache_dir = os.path.join(
            workspace_root, "_runtime", "inferencer_cache"
        )
        os.makedirs(streaming_cache_dir, exist_ok=True)
        os.makedirs(
            os.path.join(workspace_root, "_runtime", "tmp_output_files"),
            exist_ok=True,
        )

    # Common kwargs for _make_rovochat
    rovo_kwargs: dict[str, Any] = dict(
        cloud_id=cloud_id,
        uct_token=uct_token,
        email=email,
        api_token=api_token,
        base_url=base_url,
        agent_named_id=agent_named_id,
    )
    if streaming_cache_dir:
        rovo_kwargs["cache_folder"] = streaming_cache_dir

    # === Outer Breakdown ===
    # Input to the BTA will be: role_doc + available_tools
    # task_preamble is overridden with role_setup-specific context
    outer_breakdown = _make_rovochat(**rovo_kwargs)
    outer_breakdown.template_manager = tm
    outer_breakdown.template_key = "initial"
    outer_breakdown.template_root_space = "task_breakdown"
    outer_breakdown.template_extra_feed = {"task_preamble": outer_breakdown_preamble}

    # === Outer Worker Factory (returns inner BTAs) ===
    def outer_worker_factory(
        sub_query: str, index: int
    ) -> BreakdownThenAggregateInferencer:
        return _build_inner_bta(
            sub_query=sub_query,
            index=index,
            tm=tm,
            rovo_kwargs=rovo_kwargs,
            inner_breakdown_preamble=inner_breakdown_preamble,
            inner_research_preamble=inner_research_preamble,
            inner_synthesis_instructions=inner_synthesis_instructions,
            max_inner_facets=max_inner_facets,
            aggregator_type=aggregator_type,
            aggregator_working_dir=aggregator_working_dir,
            streaming_cache_dir=streaming_cache_dir,
            inferencer_logger="auto",
        )

    # === Outer Aggregator ===
    if aggregator_type == "rovodev":
        outer_agg_kwargs = dict(
            target_path=aggregator_working_dir or ".",
            yolo=True,
        )
        if streaming_cache_dir:
            outer_agg_kwargs["cache_folder"] = streaming_cache_dir
        # NOTE: build_role_setup_inferencer does not receive inferencer_logger
        # yet; when it does, add: outer_agg_kwargs["logger"] = inferencer_logger
        outer_aggregator = RovoDevCliInferencer(**outer_agg_kwargs)
    else:
        outer_aggregator = _make_rovochat(**rovo_kwargs)

    # Wire template infrastructure for outer aggregator
    # NOTE: do NOT set template_version — SLOT_DEFAULTS sets it to "aggregation"
    # and re-applies during BTA execution. Use per-variable override instead.
    outer_aggregator.template_manager = tm
    outer_aggregator.template_key = "initial"
    outer_aggregator.template_root_space = "plan"
    outer_aggregator.template_master_version = "aggregation"
    outer_aggregator.template_variables = {
        "task_preamble": None,
        "task_instructions": "role_setup",
        "task_response_format": None,
    }

    # Inference input = role doc text (becomes {{ input }} in the template).
    inference_input = role_doc_text

    # === Wire the outer BTA ===
    outer_bta = BreakdownThenAggregateInferencer(
        name="outer_bta",
        breakdown_inferencer=outer_breakdown,
        breakdown_parser=parse_breakdown_response,
        worker_factory=outer_worker_factory,
        aggregator_inferencer=outer_aggregator,
        max_breakdown=max_facets,
        max_concurrency=None,
        workspace_root=workspace_root,
    )

    _logger.info(
        "Nested BTA wired: outer max_facets=%d, inner max_facets=%d, "
        "role_doc=%d chars, available_tools=%d chars",
        max_facets,
        max_inner_facets,
        len(role_doc_text),
        len(available_tools_text),
    )

    return outer_bta, inference_input


def build_subtask_breakdown_only(
    breakdown_file: str,
    subtask_index: int,
    role_document_path: str,
    cloud_id: str = "",
    uct_token: Optional[str] = None,
    email: Optional[str] = None,
    api_token: Optional[str] = None,
    base_url: Optional[str] = None,
    agent_named_id: Optional[str] = None,
    templates_dir: Optional[str] = None,
    streaming_cache_dir: Optional[str] = None,
    workspace_root: Optional[str] = None,
    inferencer_logger: Optional[Any] = None,
) -> tuple:
    """Build an inner BTA in breakdown-only mode for a specific subtask.

    Reads the outer breakdown output, extracts the specified subtask,
    and builds an inner BTA that performs only the breakdown phase.
    The inner BTA uses the task_preamble from the subtask's args field.

    Args:
        breakdown_file: Path to the outer breakdown output (raw LLM response with JSON).
        subtask_index: 1-based index of the subtask to process.
        role_document_path: Path to the role document (for context).
        workspace_root: Path for inner BTA workspace.
        inferencer_logger: Logger for structured logging.
        Other args: Auth and config (passed through for template rendering).

    Returns:
        (inner_bta, inference_input) tuple.
    """
    import json as _json
    import re as _re

    # 1. Read and parse the outer breakdown output.
    # The checkpoint file is a JSON object with a "raw_output" key — decode it first
    # so that escaped sequences (\\n, \") are resolved before regex matching.
    _raw_file = Path(breakdown_file).read_text(encoding="utf-8")
    try:
        _parsed = _json.loads(_raw_file)
        breakdown_text = _parsed.get("raw_output", _raw_file) if isinstance(_parsed, dict) else _raw_file
    except _json.JSONDecodeError:
        breakdown_text = _raw_file

    # Extract JSON from <Response> tags or raw text
    subtasks = []
    response_match = _re.search(r"<Response>(.*?)</Response>", breakdown_text, _re.DOTALL)
    search_text = response_match.group(1) if response_match else breakdown_text
    json_match = _re.search(r"```json.*?\n(.*?)```", search_text, _re.DOTALL)
    if not json_match:
        json_match = _re.search(r'\{[^{}]*"subtasks"\s*:\s*\[.*?\]\s*[^{}]*\}', search_text, _re.DOTALL)
    if json_match:
        try:
            data = _json.loads(json_match.group(1) if "```" in json_match.group(0) else json_match.group(0))
            subtasks = data.get("subtasks", data.get("decomposed_subtasks", []))
        except _json.JSONDecodeError as e:
            _logger.warning("Failed to parse breakdown JSON: %s", e)

    if not subtasks:
        raise ValueError(f"No subtasks found in breakdown file: {breakdown_file}")

    if subtask_index < 1 or subtask_index > len(subtasks):
        raise ValueError(
            f"Subtask index {subtask_index} out of range (1-{len(subtasks)})"
        )

    subtask = subtasks[subtask_index - 1]
    subtask_desc = subtask.get("description", subtask.get("subtask", ""))
    subtask_args = subtask.get("args", {})
    task_preamble_name = subtask_args.get("task_preamble", "skill_tool_creation")

    # Compute context variables for template rendering
    role_doc_text = Path(role_document_path).read_text(encoding="utf-8")
    role_name = role_doc_text.split("\n")[0].strip("# ").strip()
    available_tools_text = format_available_tools_and_skills(
        extra_tool_dirs=[_APP_TOOLS_DIR], extra_skill_dirs=[_APP_SKILLS_DIR]
    )

    _logger.info(
        "Building inner BTA breakdown-only for subtask %d: task_preamble=%s, desc=%.80s...",
        subtask_index, task_preamble_name, subtask_desc,
    )

    # 2. Read the task_preamble template content
    templates_root = Path(templates_dir) if templates_dir else _PROMPT_TEMPLATES_ROOT
    preamble_path = (
        templates_root / "task_breakdown" / "main" / "_variables"
        / "task_preamble" / f"{task_preamble_name}.jinja2"
    )
    if not preamble_path.exists():
        _logger.warning(
            "Task preamble %s not found at %s, falling back to create_role",
            task_preamble_name, preamble_path,
        )
        preamble_path = preamble_path.parent / "create_role.jinja2"

    inner_breakdown_preamble = Template(
        preamble_path.read_text(encoding="utf-8")
    ).render(
        role_name=role_name,
        role_doc_path=str(Path(role_document_path).resolve()),
        available_tools_skills=available_tools_text,
    )

    # 3. Set up TemplateManager
    tm = TemplateManager(
        templates=[str(templates_root), str(_AF_TEMPLATES_ROOT)],
        active_template_type="main",
        predefined_variables=True,
        cross_root_variable_lookup=True,  # Refactor 17
        enable_templated_feed=True,
    )

    # 4. Build inner BTA with breakdown_only=True
    rovo_kwargs = dict(
        cloud_id=cloud_id,
        uct_token=uct_token,
        email=email,
        api_token=api_token,
        base_url=base_url,
        agent_named_id=agent_named_id,
    )

    inner_bta = _build_inner_bta(
        sub_query=subtask_desc,
        index=subtask_index - 1,
        tm=tm,
        rovo_kwargs=rovo_kwargs,
        inner_breakdown_preamble=inner_breakdown_preamble,
        inner_research_preamble=_render_variable_file(
            "deep_research", "task_preamble", "create_role",
            role_name=role_name,
            role_doc_path=str(Path(role_document_path).resolve()),
            available_tools_skills=available_tools_text,
        ),
        inner_synthesis_instructions=_aggregation_instructions_from_path(
            templates_root,
            "implementation",
            "task_instructions",
            "skill_tool_creation",
        ),
        max_inner_facets=8,
        aggregator_type="rovodev",
        aggregator_working_dir=workspace_root or ".",
        streaming_cache_dir=streaming_cache_dir,
        breakdown_only=True,
        workspace_root=workspace_root,
        inferencer_logger=inferencer_logger,
        templates_root=templates_root,
        role_name=role_name,
        role_doc_path=str(Path(role_document_path).resolve()),
        available_tools_text=available_tools_text,
    )

    _logger.info(
        "Subtask breakdown-only built: subtask=%d, preamble=%s, desc=%d chars",
        subtask_index, task_preamble_name, len(subtask_desc),
    )

    return inner_bta, subtask_desc


def build_inner_research_only(
    inner_breakdown_file: str,
    role_document_path: str,
    cloud_id: str = "",
    uct_token: Optional[str] = None,
    email: Optional[str] = None,
    api_token: Optional[str] = None,
    base_url: Optional[str] = None,
    agent_named_id: Optional[str] = None,
    templates_dir: Optional[str] = None,
    streaming_cache_dir: Optional[str] = None,
    workspace_root: Optional[str] = None,
    inferencer_logger: Optional[Any] = None,
) -> tuple:
    """Build an inner BTA that runs only the worker phase (skip breakdown, skip aggregation).

    Reads the inner breakdown output, parses subtasks, expands todos for research types,
    and builds a BTA with pre-parsed sub_queries. The BTA runs workers in parallel
    with per-group concurrency limits.

    Args:
        inner_breakdown_file: Path to inner breakdown output (LLM response with JSON subtasks).
        role_document_path: Path to the role document.
        workspace_root: Path for workspace.
        inferencer_logger: Logger for structured logging.

    Returns:
        (bta, sub_queries) tuple — call bta._build_diamond_graph(sub_queries) then bta._run().
    """
    from functools import partial

    # 1. Parse the inner breakdown
    inner_text = Path(inner_breakdown_file).read_text(encoding="utf-8")
    sub_queries = parse_inner_breakdown_response(inner_text)

    if not sub_queries:
        raise ValueError(f"No subtasks found in inner breakdown file: {inner_breakdown_file}")

    _logger.info("Parsed %d inner sub_queries from %s", len(sub_queries), inner_breakdown_file)

    # 2. Context variables for preamble rendering
    role_doc_text = Path(role_document_path).read_text(encoding="utf-8")
    role_name = role_doc_text.split("\n")[0].strip("# ").strip()
    role_doc_path_resolved = str(Path(role_document_path).resolve())
    available_tools_text = format_available_tools_and_skills(
        extra_tool_dirs=[_APP_TOOLS_DIR], extra_skill_dirs=[_APP_SKILLS_DIR]
    )

    # 3. Set up TemplateManager
    templates_root = Path(templates_dir) if templates_dir else _PROMPT_TEMPLATES_ROOT
    tm = TemplateManager(
        templates=[str(templates_root), str(_AF_TEMPLATES_ROOT)],
        active_template_type="main",
        predefined_variables=True,
        cross_root_variable_lookup=True,  # Refactor 17
        enable_templated_feed=True,
    )

    # 4. Build worker factories (same as _build_inner_bta)
    rovo_kwargs = dict(
        cloud_id=cloud_id, uct_token=uct_token, email=email,
        api_token=api_token, base_url=base_url, agent_named_id=agent_named_id,
    )

    def _make_worker(sub_query, index, preamble_name, use_rovodev):
        preamble_path = (
            templates_root / "deep_research" / "main" / "_variables"
            / "task_preamble" / f"{preamble_name}.jinja2"
        )
        if preamble_path.exists():
            worker_preamble = Template(preamble_path.read_text(encoding="utf-8")).render(
                role_name=role_name, role_doc_path=role_doc_path_resolved,
                available_tools_skills=available_tools_text,
            )
        else:
            _logger.warning("Preamble %s not found, using default", preamble_name)
            worker_preamble = ""

        if use_rovodev:
            _logger.info("  Worker %d (INVESTIGATION/%s): %.60s...", index, preamble_name, sub_query)
            rovodev_worker_kwargs: dict[str, Any] = dict(yolo=True, debug_mode=True)
            if workspace_root:
                rovodev_worker_kwargs["target_path"] = workspace_root
            if streaming_cache_dir:
                rovodev_worker_kwargs["cache_folder"] = streaming_cache_dir
            worker_inf = RovoDevCliInferencer(**rovodev_worker_kwargs)
        else:
            _logger.info("  Worker %d (RESEARCH/%s): %.60s...", index, preamble_name, sub_query)
            worker_inf = _make_rovochat(**rovo_kwargs)

        if inferencer_logger is not None:
            worker_inf.logger = inferencer_logger

        # Set template attrs directly on the worker inferencer
        worker_inf.template_manager = tm
        worker_inf.template_key = "initial"
        worker_inf.template_root_space = "deep_research"
        worker_inf.template_extra_feed = {"task_preamble": worker_preamble}
        worker_inf.output_path = f"facet_{index}.md"
        if inferencer_logger is not None:
            worker_inf.logger = inferencer_logger
        worker_inf.debug_mode = True
        return worker_inf

    def research_factory(sub_query, index):
        return _make_worker(sub_query, index, "skill_tool_creation_research", False)

    def investigation_factory(sub_query, index):
        return _make_worker(sub_query, index, "skill_tool_creation_investigation", True)

    worker_factory = {
        "skill_tool_creation_research": {"factory": research_factory, "expand_todos": True},
        "skill_tool_creation_investigation": {"factory": investigation_factory, "expand_todos": False},
        "__default__": {"factory": research_factory, "expand_todos": True},
    }

    # 5. Build a dummy aggregator (we just want workers)
    # Use a simple pass-through that collects all results
    def noop_aggregator(inference_input, **kwargs):
        return inference_input

    # 6. Build BTA — workers only (breakdown is pre-done, aggregation is noop)
    bta_breakdown_kwargs = dict(
        yolo=True,
        template_manager=tm,
        template_key="initial",
        template_root_space="task_breakdown",
    )
    if workspace_root:
        bta_breakdown_kwargs["target_path"] = workspace_root
    bta = BreakdownThenAggregateInferencer(
        breakdown_inferencer=RovoDevCliInferencer(**bta_breakdown_kwargs),
        breakdown_parser=parse_inner_breakdown_response,
        worker_factory=worker_factory,
        task_type_arg_name="task_preamble",
        group_max_concurrency={
            "skill_tool_creation_research": 3,
            "skill_tool_creation_investigation": 2,
        },
        max_concurrency=None,
        debug_mode=True,
    )
    if workspace_root:
        bta.workspace_root = workspace_root
    if inferencer_logger is not None:
        bta.logger = inferencer_logger

    _logger.info(
        "Inner research-only built: %d sub_queries, workspace=%s",
        len(sub_queries), workspace_root,
    )

    return bta, sub_queries


# ---------------------------------------------------------------------------
# Generic executor entry point — called by ToolDispatcher
# ---------------------------------------------------------------------------

async def execute(
    arguments: dict,
    session_context: dict,
) -> "ToolExecutionResult":
    """Generic entry point for ToolDispatcher.

    Implementation: thin shim over `/task`'s `_run_topology()`. Loads the existing
    `role_setup.yaml` (which `_import_`s `role_setup_skill_tool_creation.yaml`) and
    applies runtime overrides to swap the 7 RovoChat/RovoDevCLI leaves to ClaudeCodeCli
    (proven set from `test_role_setup_through_yaml_claude.py`). Domain-specific
    pre-processing (read role doc, extract role_name, enumerate registry tools/skills)
    is retained — those values flow into `template_extra_feed.*` via dotted-key
    override (verified in test_task_helpers.py::test_template_feed_via_override_reaches_inferencer).

    The original YAML is unchanged.

    Arguments (from LLM tool call):
        role_document_path (str, required): Path to the role responsibility document.
        --max-facets (int, optional): Max outer facets (default 8).
        --max-inner-facets (int, optional): Max inner facets (default 5).

    session_context keys used:
        working_dir (per-task subdir from dispatcher), task_id, interactive.
    """
    from agent_foundation.common.inferencers.agentic_inferencers.conversational.protocols import (
        ToolExecutionResult,
    )
    from openteam.server.resources.tools.task.executor import (
        _run_topology, _resolve_workspace,
    )

    role_document_path = arguments.get("role_document_path", "")
    max_facets = int(arguments.get("max_facets", 8))
    max_inner_facets = int(
        arguments.get("max_inner_facets", 5)
    )

    # Domain pre-processing — exactly as before, just hoisted.
    role_doc_text = Path(role_document_path).read_text(encoding="utf-8") if role_document_path else ""
    role_name = role_doc_text.split("\n")[0].strip("# ").strip() if role_doc_text else ""
    role_doc_abs = str(Path(role_document_path).resolve()) if role_document_path else ""
    available_tools_text = format_available_tools_and_skills(
        extra_tool_dirs=[_APP_TOOLS_DIR], extra_skill_dirs=[_APP_SKILLS_DIR]
    )

    yaml_path = Path(__file__).parent / "role_setup.yaml"
    templates_path = Path(__file__).resolve().parent.parent.parent / "prompt_templates"

    # Pre-allocate workspace via shared allocator (closes literal-task_id collision bug).
    from openteam.server.resources.tools._shared.workspace_allocator import (
        allocate_tool_workspace,
    )
    _sr = (session_context or {}).get("session_root", "")
    if _sr:
        _tasks_base = Path(_sr) / "tasks"
        _tasks_base.mkdir(parents=True, exist_ok=True)
        workspace = allocate_tool_workspace("role_setup", base_dir=_tasks_base)
    else:
        workspace = allocate_tool_workspace("role_setup", base_dir=None)
    session_context = {**session_context, "working_dir": str(workspace)}

    overrides: dict = {
        "max_breakdown": max_facets,
        "worker_factory.skill_tool_creation.max_breakdown": max_inner_facets,
        # NOTE: _template_manager.templates is NOT set here — the centralized
        # default in _run_topology() provides both roots [OS, AF]. Setting a
        # single-string override here would clobber the two-root list.
        # The inner BTA's _template_manager also needs both roots — patch it
        # to match the centralized default.
        "worker_factory.skill_tool_creation._template_manager.templates": [str(templates_path), str(_AF_TEMPLATES_ROOT)],
        # role_setup.yaml has a top-level `workspace:` (InferencerWorkspace) block;
        # set its `root` field. BTA:348-349 docs confirm `workspace` (object)
        # takes precedence over `workspace_root` (convenience shorthand).
        "workspace.root": str(workspace),
        # template_extra_feed via load-config-time injection (proven by
        # test_template_feed_via_override_reaches_inferencer). Replaces the
        # post-instantiate dict update from the prior implementation.
        "template_extra_feed.role_name": role_name,
        "template_extra_feed.role_doc_path": role_doc_abs,
        "template_extra_feed.available_tools_skills": available_tools_text,
    }

    # Delegate to /task's core. _run_topology respects session_context["working_dir"]
    # (we set it to the pre-allocated workspace above), wires WebSocketGraphReporter,
    # runs, normalizes result.
    result = await _run_topology(
        source=("file", yaml_path),
        request=f"Set up the role defined at: {role_doc_abs}",
        overrides=overrides,
        session_context=session_context,
    )

    # Re-key + augment context_updates to original schema. Adds role_setup-specific
    # artifact paths (skills/, tools/, role_tool_association.json) that /task's
    # generic _discover_artifacts doesn't surface.
    ctx = dict(result.context_updates) if result.context_updates else {}
    ws = ctx.get("workspace_path")
    if ws:
        ctx["role_setup_working_dir"] = ws
        report = Path(ws) / "outputs" / "role_setup_report.md"
        if report.is_file():
            ctx["role_setup_report_path"] = str(report)
        skills = Path(ws) / "outputs" / "skills"
        tools = Path(ws) / "outputs" / "tools"
        association = Path(ws) / "outputs" / "role_tool_association.json"
        if skills.is_dir():
            ctx["skills_dir"] = str(skills)
        if tools.is_dir():
            ctx["tools_dir"] = str(tools)
        if association.is_file():
            ctx["role_tool_association_path"] = str(association)

    return ToolExecutionResult(
        result=str(result.result),
        context_updates=ctx,
    )
