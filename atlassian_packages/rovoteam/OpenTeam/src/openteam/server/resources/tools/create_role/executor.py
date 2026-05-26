"""Pipeline wiring for the create_role tool.

Builds a ``BreakdownThenAggregateInferencer`` that uses RovoChatInferencer
for all three stages (breakdown, workers, aggregation).

All three phases use **generic** prompt templates from ``prompt_templates/``,
with domain-specific context injected via ``_variables/`` (predefined variables)
or kwargs overrides:

- **Breakdown**: ``task_breakdown/main/initial.jinja2`` — generic decomposition.
  ``task_preamble`` explicitly loaded from ``_variables/task_preamble/create_role.jinja2``
  (create-role-specific context).
- **Worker**: ``deep_research/main/initial.jinja2`` — generic deep research.
  ``task_preamble`` explicitly loaded from ``_variables/task_preamble/create_role.jinja2``
  (role-specific source guidance).
- **Aggregation**: ``plan/main/initial.jinja2`` — generic structured document.
  ``task_instructions`` resolved from ``aggregation/create_role.jinja2``
  via ``template_master_version="aggregation"`` + ``template_version="create_role"``.

A single ``TemplateManager`` is rooted at ``prompt_templates/`` with
``active_template_root_space`` switching between phases.

Usage::

    from openteam.server.resources.tools.create_role import build_create_role_inferencer

    inferencer = build_create_role_inferencer(
        cloud_id="my-cloud-id",
        uct_token="my-uct-token",
    )
    result = inferencer.infer("Senior Backend Engineer focused on microservices")
    # Or async:
    # result = await inferencer.ainfer("Senior Backend Engineer ...")
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, List, Optional

from attr import attrib, attrs

from agent_foundation.common.inferencers.agentic_inferencers.external.rovochat.rovochat_inferencer import (
    RovoChatInferencer,
)
from agent_foundation.common.inferencers.agentic_inferencers.flow_inferencers.breakdown_then_aggregate_inferencer import (
    BreakdownThenAggregateInferencer,
)
from agent_foundation.common.inferencers.inferencer_base import InferencerBase
from agent_foundation.common.inferencers.agentic_inferencers.external.rovodev.rovodev_cli_inferencer import (
    RovoDevCliInferencer,
)
from agent_foundation.common.response_parsers import extract_delimited
from python_utils.string_utils.formatting.template_manager import TemplateManager

_logger = logging.getLogger(__name__)

# Root of all prompt templates.
# Layout:
#   prompt_templates/.variables.yaml                     (employee persona)
#   prompt_templates/task_breakdown/main/initial.jinja2   (generic breakdown)
#   prompt_templates/deep_research/main/initial.jinja2    (generic deep research)
#   prompt_templates/plan/main/initial.jinja2             (generic structured document)
_PROMPT_TEMPLATES_ROOT = (
    Path(__file__).resolve().parent.parent.parent / "prompt_templates"
)

# AgentFoundation fallback templates root (for multi-root TemplateManager).
import agent_foundation.resources as _af_res
_AF_TEMPLATES_ROOT = Path(_af_res.__file__).parent / "prompt_templates"


def _load_variable_file(space: str, var_name: str, variant: str = "create_role") -> str:
    """Read a ``_variables/`` template file by variant name.

    E.g., _load_variable_file("task_breakdown", "task_preamble", "create_role")
    reads ``task_breakdown/main/_variables/task_preamble/create_role.jinja2``.
    """
    path = (
        _PROMPT_TEMPLATES_ROOT / space / "main" / "_variables"
        / var_name / f"{variant}.jinja2"
    )
    if not path.is_file():
        raise FileNotFoundError(f"Variable template not found: {path}")
    return path.read_text(encoding="utf-8")


# ROLE_SYNTHESIS_INSTRUCTIONS constant REMOVED — canonical content now lives
# at plan/main/_variables/task_instructions/aggregation/create_role.jinja2
# (resolved via template_master_version="aggregation" + template_version="create_role")


# ---------------------------------------------------------------------------
# Breakdown response parser
# ---------------------------------------------------------------------------


def parse_breakdown_response(raw_output: str) -> List[str]:
    """Parse the JSON decomposition from the breakdown inferencer's output.

    The breakdown template produces a ``<Response>`` block containing a
    JSON object with a ``subtasks`` array (unified format matching
    ``task_breakdown``).  Each subtask has a ``description`` and ``todos``
    list.  This parser extracts a self-contained research query string
    for each subtask by combining them.

    Falls back to ``parse_numbered_list`` if JSON extraction fails.
    """
    from agent_foundation.common.inferencers.agentic_inferencers.flow_inferencers.breakdown_then_aggregate_inferencer import (
        parse_numbered_list,
    )

    # 1. Extract <Response> content
    response_text = extract_delimited(str(raw_output))

    # 2. Try to extract JSON from ```json ... ``` code fence
    json_match = re.search(
        r"```json[^\n{]*(\{[\s\S]*\})\s*```", response_text
    )
    if not json_match:
        # No code fence — maybe the whole response is JSON?
        json_match = re.search(
            r"\{[\s\S]*\"subtasks\"[\s\S]*\}", response_text
        )
        if json_match:
            json_str = json_match.group(0)
        else:
            _logger.warning(
                "No JSON found in breakdown response, falling back to numbered list"
            )
            return parse_numbered_list(response_text)
    else:
        json_str = json_match.group(1)

    # 3. Parse JSON
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        _logger.warning("JSON parse failed (%s), falling back to numbered list", e)
        return parse_numbered_list(response_text)

    # 4. Extract subtasks → sub-query strings for workers
    subtasks = data.get("subtasks") or []
    if not subtasks:
        _logger.warning("No subtasks in JSON, falling back to numbered list")
        return parse_numbered_list(response_text)

    queries = []
    for subtask in subtasks:
        desc = subtask.get("description", "")
        todos = subtask.get("todos") or []
        # Build a self-contained research query for the worker
        if todos:
            details = "\n".join(f"- {t}" for t in todos)
            query = f"{desc}\n\nSpecific areas to investigate:\n{details}"
        else:
            query = desc
        if query.strip():
            queries.append(query.strip())

    if not queries:
        _logger.warning("Empty subtask descriptions, falling back to numbered list")
        return parse_numbered_list(response_text)

    _logger.info("Parsed %d research subtasks from breakdown response", len(queries))
    return queries


def _build_template_manager(
    templates_dir: Optional[str] = None,
) -> TemplateManager:
    """Create a ``TemplateManager`` rooted at the ``prompt_templates/`` directory.

    The TemplateManager uses a 2-element root list:
    1. OpenTeam root (override + all _variables/)
    2. AgentFoundation root (fallback wrappers only)

    The single TemplateManager serves all phases via
    ``active_template_root_space`` switching:

    - ``task_breakdown`` — generic task decomposition
    - ``deep_research`` — generic deep research
    - ``plan`` — generic structured document creation

    The root ``.variables.yaml`` defines the OpenTeam employee persona,
    auto-injected into ``{{ employee }}`` across all templates.
    """
    root = templates_dir or str(_PROMPT_TEMPLATES_ROOT)
    return TemplateManager(
        templates=[root, str(_AF_TEMPLATES_ROOT)],
        active_template_type="main",
        predefined_variables=True,
        cross_root_variable_lookup=True,  # Refactor 17
        enable_templated_feed=True,  # Required for wrapper variable resolution
    )


# ---------------------------------------------------------------------------
# PromptWrapperInferencer removed — template rendering now built into InferencerBase.
# Use template_manager, template_key, template_root_space, template_extra_feed
# directly on any inferencer.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# RovoChat factory
# ---------------------------------------------------------------------------


def _make_rovochat(
    cloud_id: str = "",
    uct_token: Optional[str] = None,
    email: Optional[str] = None,
    api_token: Optional[str] = None,
    base_url: Optional[str] = None,
    agent_named_id: Optional[str] = None,
    cache_folder: Optional[str] = None,
) -> RovoChatInferencer:
    """Create a fresh ``RovoChatInferencer``.

    Called once per worker to ensure conversation isolation (each worker
    gets its own RovoChat conversation).

    Supports two auth modes:
    - UCT: pass ``uct_token``
    - Basic Auth: pass ``email`` + ``api_token`` (gateway auto-detected
      for ``.atlassian.net`` URLs; ``cloud_id`` is optional in this mode)
    """
    kwargs: dict[str, Any] = dict(
        cloud_id=cloud_id or "",
        base_url=base_url or "",
        agent_named_id=agent_named_id or "",
        auto_continue=True,
        max_continuations=5,
        auto_resume=False,
    )
    if cache_folder:
        kwargs["cache_folder"] = cache_folder
    if uct_token:
        kwargs["uct_token"] = uct_token
    elif email and api_token:
        kwargs["email"] = email
        kwargs["api_token"] = api_token
    return RovoChatInferencer(**kwargs)


# ---------------------------------------------------------------------------
# Main factory
# ---------------------------------------------------------------------------


def build_create_role_inferencer(
    cloud_id: str = "",
    uct_token: Optional[str] = None,
    email: Optional[str] = None,
    api_token: Optional[str] = None,
    base_url: Optional[str] = None,
    agent_named_id: Optional[str] = None,
    max_facets: int = 8,
    checkpoint_dir: Optional[str] = None,
    templates_dir: Optional[str] = None,
    aggregator_type: str = "rovochat",
    aggregator_working_dir: Optional[str] = None,
    workspace: Optional[Any] = None,
) -> BreakdownThenAggregateInferencer:
    """Build a ``BreakdownThenAggregateInferencer`` wired for role creation.

    The pipeline uses three generic templates with domain-specific context:

    1. **Breakdown** — ``task_breakdown/main/initial.jinja2`` decomposes the
       role description into research subtasks. ``task_preamble`` auto-resolved
       with create-role-specific dimensions.
    2. **Workers** — ``deep_research/main/initial.jinja2`` researches one
       facet each (parallel). ``task_preamble`` explicitly loaded from
       ``_variables/task_preamble/create_role.jinja2`` (role-specific source guidance).
    3. **Aggregator** — ``plan/main/initial.jinja2`` synthesizes all research
       into a role responsibility document. ``task_instructions`` resolved
       from ``aggregation/create_role.jinja2`` via master_version mechanism.

    A single ``TemplateManager`` is rooted at ``prompt_templates/`` with
    ``active_template_root_space`` switching between phases.

    Args:
        cloud_id: Atlassian Cloud ID. Required for UCT auth; optional for
            Basic Auth gateway mode.
        uct_token: UCT authentication token.
        email: Email for Basic Auth (alternative to UCT).
        api_token: API token for Basic Auth (alternative to UCT).
        base_url: RovoChat API base URL override.
        agent_named_id: Route to a specific Rovo agent.
        max_facets: Maximum number of research sub-queries (caps breakdown).
        checkpoint_dir: Directory for saving intermediate results (enables
            resuming failed runs).
        templates_dir: Override path to the ``prompt_templates/`` root
            directory.  Defaults to the built-in templates.

    Returns:
        A configured ``BreakdownThenAggregateInferencer`` ready to call
        ``infer(role_description)`` or ``await ainfer(role_description)``.
    """
    tm = _build_template_manager(templates_dir)

    # Normalize workspace convenience inputs.
    # Accept:
    #   * ``workspace=None``
    #   * ``workspace="/path"`` shorthand → InferencerWorkspace(root="/path")
    #   * ``workspace=InferencerWorkspace(...)`` explicit form
    from agent_foundation.common.inferencers.inferencer_workspace import (
        InferencerWorkspace,
    )
    if isinstance(workspace, str):
        workspace = InferencerWorkspace(root=workspace)

    # Build runtime directories from workspace.root (if available)
    import os as _os
    streaming_cache_dir: Optional[str] = None
    workspace_root = workspace.root if workspace is not None else None
    if workspace_root:
        streaming_cache_dir = _os.path.join(workspace_root, "_runtime", "inferencer_cache")
        _os.makedirs(streaming_cache_dir, exist_ok=True)
        _os.makedirs(_os.path.join(workspace_root, "_runtime", "tmp_output_files"), exist_ok=True)

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

    # 1. Breakdown inferencer — uses generic task_breakdown template
    #    task_preamble explicitly loaded from _variables/task_preamble/create_role.jinja2
    breakdown_preamble = _load_variable_file("task_breakdown", "task_preamble", "create_role")
    breakdown_inf = _make_rovochat(**rovo_kwargs)
    breakdown_inf.template_manager = tm
    breakdown_inf.template_key = "initial"
    breakdown_inf.template_root_space = "task_breakdown"
    breakdown_inf.template_extra_feed = {"task_preamble": breakdown_preamble}
    breakdown_inf.debug_mode = True

    # 2. Worker factory — uses generic deep_research template
    #    task_preamble explicitly loaded from _variables/task_preamble/create_role.jinja2
    #    Creates a fresh RovoChat per sub-query for conversation isolation
    worker_preamble = _load_variable_file("deep_research", "task_preamble", "create_role")
    def worker_factory(sub_query: str, index: int):
        _logger.info("Creating worker %d for sub-query: %.80s...", index, sub_query)
        # output_path is relative — BTA assigns child workspace in
        # _build_diamond_graph, then resolve_output_path() resolves to
        # workspace_root/children/worker_N/outputs/facet_N.md
        worker_inf = _make_rovochat(**rovo_kwargs)
        worker_inf.template_manager = tm
        worker_inf.template_key = "initial"
        worker_inf.template_root_space = "deep_research"
        worker_inf.template_extra_feed = {"task_preamble": worker_preamble}
        worker_inf.debug_mode = True
        worker_inf.output_path = f"facet_{index}.md"
        return worker_inf

    # 3. Aggregator inferencer — uses modern BTA template path
    #    (inject_upstream_artifacts_to_aggregator=True is the BTA default).
    #    Template infrastructure wired here; BTA handles worker result injection.
    if aggregator_type == "rovodev":
        rovodev_kwargs = dict(
            target_path=aggregator_working_dir or ".",
            yolo=True,
        )
        if streaming_cache_dir:
            rovodev_kwargs["cache_folder"] = streaming_cache_dir
        aggregator_inf = RovoDevCliInferencer(**rovodev_kwargs)
        aggregator_inf.debug_mode = True
    else:
        aggregator_inf = _make_rovochat(**rovo_kwargs)
        aggregator_inf.debug_mode = True

    # Wire template infrastructure for aggregator.
    # master_version="aggregation" → search inside aggregation/ subdir
    # task_instructions="create_role" → select aggregation/create_role.jinja2
    # task_preamble and task_response_format use None → fall back to
    # aggregation/default.jinja2 via template_version (set by SLOT_DEFAULTS)
    #
    # NOTE: we do NOT set template_version here — SLOT_DEFAULTS already sets
    # it to "aggregation" and re-applies during BTA execution. Setting it
    # to "create_role" would be overridden. Instead, we use an explicit
    # per-variable override for task_instructions.
    aggregator_inf.template_manager = tm
    aggregator_inf.template_key = "initial"
    aggregator_inf.template_root_space = "plan"
    aggregator_inf.template_master_version = "aggregation"
    aggregator_inf.template_variables = {
        "task_preamble": None,
        "task_instructions": "create_role",
        "task_response_format": None,
    }

    # 4. Wire the BTA pipeline
    #    CRITICAL: max_concurrency MUST be None when using an aggregator.
    #    See BTA source lines 99-138 for the deadlock warning.
    #    No aggregator_prompt_builder — modern BTA path handles worker injection
    #    via inject_upstream_artifacts_to_aggregator=True (default).
    return BreakdownThenAggregateInferencer(
        breakdown_inferencer=breakdown_inf,
        breakdown_parser=parse_breakdown_response,
        worker_factory=worker_factory,
        aggregator_inferencer=aggregator_inf,
        max_breakdown=max_facets,
        max_concurrency=None,
        workspace=workspace,
    )


# ---------------------------------------------------------------------------
# Generic executor entry point — called by ToolDispatcher
# ---------------------------------------------------------------------------

async def execute(
    arguments: dict,
    session_context: dict,
) -> "ToolExecutionResult":
    """Generic entry point for ToolDispatcher.

    Implementation: thin shim over `/task`'s `_run_topology()`. Loads the existing
    `create_role_bta.yaml` and applies runtime overrides to swap RovoChat/RovoDevCLI
    leaves to ClaudeCodeCli (so it works on machines without the Atlassian CLIs).
    Equivalent to `/task --agent-config <create_role_bta.yaml> "<role_description>"`
    plus the leaf-swap overrides.

    The original YAML is unchanged; environments with RovoChat/RovoDevCLI installed
    can still use it directly via `load_config + instantiate` (see
    `test_create_role_through_yaml.py`).

    Arguments (from LLM tool call):
        role_description (str, required): High-level description of the role.
        --max-facets (int, optional): Max research facets (default 8).

    session_context keys used:
        working_dir (per-task subdir from dispatcher), task_id, interactive.
    """
    from agent_foundation.common.inferencers.agentic_inferencers.conversational.protocols import (
        ToolExecutionResult,
    )
    from openteam.server.resources.tools.task.executor import (
        _run_topology, _resolve_workspace,
    )

    role_description = arguments.get("role_description", "")
    max_facets = int(arguments.get("max_facets", 8))

    yaml_path = Path(__file__).parent / "create_role_bta.yaml"

    # Pre-allocate workspace via shared allocator (closes literal-task_id collision bug).
    from openteam.server.resources.tools._shared.workspace_allocator import (
        allocate_tool_workspace,
    )
    _sr = (session_context or {}).get("session_root", "")
    if _sr:
        _tasks_base = Path(_sr) / "tasks"
        _tasks_base.mkdir(parents=True, exist_ok=True)
        workspace = allocate_tool_workspace("create_role", base_dir=_tasks_base)
    else:
        workspace = allocate_tool_workspace("create_role", base_dir=None)
    session_context = {**session_context, "working_dir": str(workspace)}

    overrides: dict = {
        "max_breakdown": max_facets,
    }

    # Delegate to /task's core. Respects session_context["working_dir"] (already
    # set above to the pre-allocated dir), attaches WebSocketGraphReporter, runs,
    # normalizes result.
    result = await _run_topology(
        source=("file", yaml_path),
        request=role_description,
        overrides=overrides,
        session_context=session_context,
    )

    # Re-key context_updates to the original schema so downstream LLM context +
    # the dispatcher's UI hooks (which key on `role_document_path` first) work
    # bit-for-bit identically to the pre-shim implementation.
    ctx = dict(result.context_updates) if result.context_updates else {}
    ws = ctx.get("workspace_path")
    if ws:
        ctx["role_document_working_dir"] = ws
    # /task's _discover_artifacts emits `doc_path` for outputs/role_document.md.
    # Mirror it as `role_document_path`. Also fall back to workspace-root alt path.
    if "doc_path" in ctx:
        ctx["role_document_path"] = ctx["doc_path"]
    elif ws:
        alt = Path(ws) / "role_document.md"
        if alt.is_file():
            ctx["role_document_path"] = str(alt)

    return ToolExecutionResult(
        result=str(result.result),
        context_updates=ctx,
    )
