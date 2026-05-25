# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.

"""Server-layer tool executor for ConversationalInferencer.

SessionToolExecutor captures the RankEvolveSession and dispatches tool calls
to the appropriate bridge or session-state handler. Returns ToolExecutionResult
with result text and context_updates dict (propagated back to the inferencer's
prior_context).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, ClassVar

from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.conversational.protocols import (
    ToolExecutionResult,
)
from rankevolve.src.server.workflow_context import WorkflowPhaseRecord

logger = logging.getLogger(__name__)


# Pattern used to extract the codebase root from the session's
# ``workflow_target_path`` when SubmissionRunner substitutes
# ``${CODEBASE_ROOT}`` placeholders in launch.json.
#
# IMPORTANT: SubmissionRunner deliberately has NO built-in default — the
# right pattern is team / setup specific (e.g. ``**/fbcode``,
# ``**/fbsource/fbcode``, ``**/fbs_*/fbcode``). For now we hardcode here
# in the caller; a future UI override would replace this with a value
# threaded through the wire format (see plan: zazzy-noodling-puddle.md
# "Future scope" section).
#
# ``**/fbcode`` is the most universal choice — every Meta engineer has
# their checkout's fbcode tree at ``<root>/fbcode/`` regardless of
# whether ``<root>`` is named ``fbsource``, ``fbs_cfr_dev``,
# ``fbsource260327``, etc. Since ``fbcode`` is the buck cell name, the
# match is structurally guaranteed for any source-tree path.
_CODEBASE_ROOT_PATTERN: str = "**/fbcode"


# Back-compat: the prompt-template variant directory has been renamed
# twice. Original `submission_script_generator/` was first renamed to
# `experiment_launcher_maker/` (script's scope grew beyond submission to
# launch + monitor + retry + cleanup), then to `experiment_runner_creation/`
# (since it monitors the run too, "runner" captures lifecycle ownership
# better than "launcher"). Persisted queue entries / hub JSON / session_state
# may carry either legacy value; this map rewrites them at the input
# boundary so all downstream code (`is_non_sop_task` gate, completion-
# handler dispatch, resolver-folder lookup) sees only the current name.
# Logs once per process per legacy hit.
_TEMPLATE_VERSION_RENAMES: dict[str, str] = {
    "submission_script_generator": "experiment_runner_creation",
    "experiment_launcher_maker": "experiment_runner_creation",
}
_LOGGED_LEGACY_RENAMES: set[str] = set()


def _normalize_template_version(v: str) -> str:
    new = _TEMPLATE_VERSION_RENAMES.get(v)
    if new is not None and v != new:
        if v not in _LOGGED_LEGACY_RENAMES:
            _LOGGED_LEGACY_RENAMES.add(v)
            logger.info(
                "template_version / on_complete_handler %r renamed to %r; "
                "please update persisted state.",
                v,
                new,
            )
        return new
    return v


class SessionToolExecutor:
    """Server-layer tool executor. Captures session for bridge/state access.

    Returns ToolExecutionResult with result text + context_updates dict.
    context_updates are applied to the inferencer's prior_context after each call.
    """

    def __init__(
        self,
        session: Any,
        tasks_dir: Path | None = None,
        queue_service: Any = None,
        persist_callback: Callable[[Any], Awaitable[None]] | None = None,
    ) -> None:
        self._session = session
        # Round 9: per-session task workspace layout — derive from
        # ``self._session.session_tasks_dir`` at every read site (returns
        # ``<server>/sessions/<session_dir>/tasks/``). The legacy ``tasks_dir``
        # ctor param is accepted for backwards compat with older callers but
        # ignored — every consumer below uses session.session_tasks_dir.
        del tasks_dir  # noqa: F841 — drop reference to unused legacy plumbing
        self._queue_service = queue_service
        # persist_callback: async function that persists the session state to disk.
        # Wired by message_handlers.py's SessionToolExecutor construction sites
        # to wrap session_manager.persist_session_state in asyncio.to_thread.
        # Invoked after every task_queue mutation so on-disk state stays fresh
        # for restart-resume (Layer 1 of the resume plan).
        self._persist_callback = persist_callback
        # Registry of post-completion handlers for queued tasks.
        # Maps a stable string KEY (persisted on the queue entry as
        # entry["on_complete_handler"]) to a callable. Storing the key on
        # disk — not the callable itself — keeps the queue serializable: an
        # agent-server restart mid-PTI reloads the queue, re-registers the
        # dict in __init__, and any completed-but-unhandled entries can have
        # their hook fired on resume reconcile (see hub_state.py).
        self._completion_handlers: dict[
            str, Callable[[dict[str, Any]], Awaitable[None]]
        ] = {
            "experiment_runner_creation": self._setup_completion_hook,
        }

    async def _persist(self) -> None:
        """Trigger session-state persistence if the callback is wired.
        Catches and logs exceptions so a persist failure never breaks the queue."""
        if self._persist_callback is None:
            return
        try:
            await self._persist_callback(self._session)
        except Exception as e:
            logger.warning("persist_callback failed: %s", e)

    def _resolve_field_templates(
        self,
        tool_def: Any,
        args: dict[str, Any],
        workspace: Path,
    ) -> dict[str, Any]:
        """Resolve ``{{variable}}`` templates in tool definition fields.

        Template resolution is governed by **arg_template_rules** — a list of
        rules each specifying which fields and which variables participate.
        Rules are loaded from (in priority order):

        1. **Per-tool** ``tool_def.arg_template_rules`` — if present (even ``[]``),
           used as-is.  An empty list disables all template resolution.
        2. **Global** ``global.json`` → ``arg_template_rules`` — inherited when
           the per-tool value is ``None`` (field omitted from tool.json).

        Each rule is a dict ``{"field_pattern": "...", "arg_pattern": "..."}``.
        Patterns use the ``string_check`` DSL (e.g. ``$ _path`` = endsWith).

        Variables are collected from session context (lower priority) and tool
        args (higher priority). After substitution the result is checked as
        an absolute path, then as a path relative to *workspace*.

        Returns a dict containing two parallel keys per resolved field:
          * ``<fname>``         → str — the resolved path (always present once
            the template was applied; the path may or may not exist on disk).
            For the second-pass plain-relative-path branch, this resolves
            against ``workspace`` and is also always stored.
          * ``<fname>_exists``  → bool — True iff the resolved path exists.

        Always-storing the resolved path (Fix-RT) prevents silent omissions
        downstream: the auto-advance synthetic message can interpolate the
        canonical path and explicitly tell the LLM whether the artifact has
        been produced yet, instead of leaving consumers to guess from a
        missing key.
        """
        import dataclasses
        import re

        from rankevolve.src.utils.string_utils.comparison import string_check

        # Rules come from the tool_def, which already has cascade-resolved values
        # (global.json defaults merged into tool.json via FileBasedVariableManager).
        rules = tool_def.arg_template_rules or []

        if not rules:
            return {}

        # Fix-RT2: harden the variable-pool builder against non-path values.
        # session_context and args contain heterogeneous strings — workflow
        # descriptions, free-text prompts, JSON blobs — many of which are not
        # paths. Linux PATH_MAX is 4096 bytes; calling Path(v).is_file() on
        # longer values raises OSError([Errno 36] File name too long), which
        # propagates out of the function and gets swallowed by the outer
        # try/except, leaving phase_outputs.viewable_artifact_path empty —
        # cascading into a missing View button on the post-Phase confirmation
        # widget. The fix: never attempt is_file() on values that obviously
        # aren't paths, and catch OSError as a defense-in-depth.
        def _normalize(v: str) -> str:
            if len(v) > 4096 or "\n" in v or "\0" in v:
                return v
            try:
                p = Path(v)
                return str(p.parent) if p.is_file() else v
            except OSError:
                return v

        # Build full variable pool: session context (lower) + args (higher)
        all_vars: dict[str, str] = {}
        session_ctx = (
            self._session.session_context
            if hasattr(self._session, "session_context")
            else {}
        )
        for k, v in session_ctx.items():
            if isinstance(v, str) and v:
                all_vars[k] = _normalize(v)
        for k, v in args.items():
            if isinstance(v, str) and v:
                all_vars[k] = _normalize(v)

        _TEMPLATE_RE = re.compile(r"\{\{(\w+)\}\}")
        results: dict[str, Any] = {}

        def _safe_exists(path: Path) -> bool:
            """OSError-safe wrapper around Path.exists().

            Fix-RT2 defense-in-depth: even after _normalize, a templated
            field could plausibly resolve to a too-long path (e.g., if a
            template variable is itself huge). exists() is called from the
            _store helper — guard it so a single bad field can't poison the
            whole resolver.
            """
            try:
                return path.exists()
            except OSError:
                return False

        def _store(fname: str, path: Path) -> None:
            """Always store the resolved path + an _exists sibling (Fix-RT).

            WARN on miss so the "tool said it would produce X but it didn't
            yet exist" state is visible in logs.
            """
            exists = _safe_exists(path)
            results[fname] = str(path)
            results[f"{fname}_exists"] = exists
            if not exists:
                logger.warning(
                    "_resolve_field_templates: %s resolved to %s but file does "
                    "not exist (yet). Storing path; downstream can check "
                    "%s_exists=False.",
                    fname,
                    path,
                    fname,
                )

        for rule in rules:
            field_pat = rule.get("field_pattern", "")
            arg_pat = rule.get("arg_pattern", "")
            if not field_pat:
                continue

            # Filter variables matching arg_pattern
            eligible_vars = (
                {k: v for k, v in all_vars.items() if string_check(k, arg_pat)}
                if arg_pat
                else all_vars
            )

            # Resolve matching fields
            for fld in dataclasses.fields(tool_def):
                fname = fld.name
                if fname in results:
                    continue  # already resolved by a prior rule
                if not string_check(fname, field_pat):
                    continue
                template = getattr(tool_def, fname, "")
                if not template or "{{" not in template:
                    continue

                resolved = _TEMPLATE_RE.sub(
                    lambda m: eligible_vars.get(m.group(1), m.group(0)),
                    template,
                )

                # Path resolution: absolute paths win as-is even when the
                # file doesn't exist yet (the template told us where the
                # tool intends to put the artifact). Relative paths resolve
                # against the workspace.
                resolved_path = Path(resolved)
                if resolved_path.is_absolute():
                    _store(fname, resolved_path)
                else:
                    _store(fname, workspace / resolved)

            # Second pass: resolve plain relative paths (no {{}} templates)
            # against the workspace. E.g., "outputs/final_result.md" → workspace/outputs/final_result.md
            for fld in dataclasses.fields(tool_def):
                fname = fld.name
                if fname in results:
                    continue
                if not string_check(fname, field_pat):
                    continue
                value = getattr(tool_def, fname, "")
                if not value or "{{" in value:
                    continue  # empty or has templates (handled above)
                _store(fname, workspace / value)

        return results

    async def _exec_understand_codebase(
        self, arguments: dict[str, Any]
    ) -> ToolExecutionResult:
        """Translate understand_codebase args → task args, then delegate."""
        target = arguments.get("target", arguments.get("request", ""))
        arguments["request"] = target
        arguments["template_version"] = "understand_codebase"
        if arguments.pop("docs_only", None):
            arguments["no_planning"] = True
        if arguments.pop("investigation_only", None):
            arguments["no_implementation"] = True

        # J5: Auto-resume detection. If no explicit --resume passed AND a prior
        # completed task workspace for this target exists in the session,
        # auto-set resume_workspace so we short-circuit instead of running for
        # ~65 min again. Critical for both (a) post-restart session resume UX
        # and (b) fast-iteration testing of post-completion paths (auto-advance
        # widget). Escape hatch: --no-resume flag (parsed below).
        if (
            not arguments.get("resume")
            and not arguments.get("--resume")
            and not arguments.pop("no_resume", False)
            and not arguments.pop("no-resume", False)
        ):
            auto_resume_path = self._find_completed_prior_task(
                template_version="understand_codebase",
                target=target,
            )
            if auto_resume_path is not None:
                arguments["resume"] = str(auto_resume_path)
                logger.info(
                    "[J5 auto-resume] understand_codebase target=%s — "
                    "found completed prior workspace %s; resuming instead of "
                    "starting fresh.",
                    target,
                    auto_resume_path,
                )

        return await self._exec_task(arguments)

    def _find_completed_prior_task(
        self,
        template_version: str,
        target: str | None,
    ) -> Path | None:
        """Scan ``<session>/tasks/task_*/`` newest-first for a completed prior
        task whose request.txt exactly matches ``target``.

        Eligibility (all required):
          1. Directory name starts with ``task_`` (excludes ``research_``,
             ``submission_``, ``exp_``, etc.).
          2. ``request.txt`` exists AND its trimmed content equals ``target``.
          3. Completion markers: BOTH ``.plan_completed`` AND ``.impl_completed``
             present in either ``artifacts/`` (canonical) OR ``outputs/`` (legacy
             fallback) — mirrors ``InferencerWorkspace.has_marker``'s lookup.

        Returns the most-recent matching task path, or None.

        ``template_version`` is currently informational (logged for traceability)
        — the request.txt match is precise enough to scope to understand_codebase
        invocations because other tools store different content shapes.
        """
        if not target:
            return None
        try:
            tasks_dir = Path(self._session.session_tasks_dir)
        except Exception:
            return None
        if not tasks_dir.is_dir():
            return None

        target_norm = target.strip()

        try:
            candidates = sorted(
                (
                    d
                    for d in tasks_dir.iterdir()
                    if d.is_dir() and d.name.startswith("task_")
                ),
                key=lambda d: d.name,
                reverse=True,
            )
        except OSError as e:
            logger.warning(
                "[J5 auto-resume] failed to list tasks dir %s: %s",
                tasks_dir,
                e,
            )
            return None

        for cand in candidates:
            req_file = cand / "request.txt"
            if not req_file.is_file():
                continue
            try:
                req_content = req_file.read_text(encoding="utf-8").strip()
            except OSError:
                continue
            if req_content != target_norm:
                continue
            # Completion markers — canonical artifacts/ first, legacy outputs/ second.
            plan_done = (cand / "artifacts" / ".plan_completed").is_file() or (
                cand / "outputs" / ".plan_completed"
            ).is_file()
            impl_done = (
                (cand / "artifacts" / ".impl_completed").is_file()
                or (cand / "outputs" / ".impl_completed").is_file()
                # Belt-and-suspenders: tolerate the longer ".implementation_completed"
                # form some legacy tasks emit (different write path).
                or (cand / "artifacts" / ".implementation_completed").is_file()
                or (cand / "outputs" / ".implementation_completed").is_file()
            )
            if plan_done and impl_done:
                logger.info(
                    "[J5 auto-resume] match: tool=%s target=%s workspace=%s "
                    "(plan_done=%s impl_done=%s)",
                    template_version,
                    target_norm,
                    cand,
                    plan_done,
                    impl_done,
                )
                return cand
        return None

    async def __call__(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> ToolExecutionResult:
        # Dict-dispatch mirroring the `_completion_handlers` precedent.
        # All values are bound async methods returning ToolExecutionResult.
        executors: dict[
            str, Callable[[dict[str, Any]], Awaitable[ToolExecutionResult]]
        ] = {
            "task": self._exec_task,
            "understand_codebase": self._exec_understand_codebase,
            # Hub submission subprocess — see Section 5 of the design doc.
            # Sibling of _exec_task to avoid stacking PTI plumbing in one branch.
            "submission_run": self._exec_submission_run,
            "research_propose": self._exec_research_propose,
            "knowledge": self._exec_knowledge,
            "set_session_root": self._exec_set_session_root,
            "set_workflow_target_path": self._exec_set_workflow_target_path,
            "set_model": self._exec_set_model,
            "set_strategy": self._exec_set_strategy,
            "clear": self._exec_clear,
            "experiment_status": self._exec_experiment_status,
            # Round 10: /experiment orchestrator (Phase 2 of the
            # local-experiment plan). See ExperimentBridge for the
            # composition. Lazy-imported inside the executor below to
            # keep the :server_lib ↔ agentic_foundation cycle from
            # tightening.
            "experiment": self._exec_experiment,
            # Round 11: split orchestrator. /experiment now sequences
            # these two sub-commands. See
            # /home/zgchen/.claude/plans/humming-tinkering-wirth.md.
            "implement_hypothesis": self._exec_implement_hypothesis,
            "experiment_combos": self._exec_experiment_combos,
        }
        try:
            executor = executors.get(tool_name)
            if executor is None:
                return ToolExecutionResult(result=f"Unknown tool: {tool_name}")
            return await executor(arguments)
        except Exception as e:
            # Surface the failure to the LLM with an unmistakable sentinel
            # `[TOOL_FAILED]` so the agent CANNOT narrate it as success and
            # cannot silently continue the workflow. The previous
            # `f"Error executing {tool_name}: {e}"` text was too soft —
            # the LLM treated it as a normal tool result and went on to
            # claim the task had launched, leaving the user chasing a
            # phantom (verified failure mode in
            # ses-moc83zd4-3y9e_20260423_182003).
            #
            # Use logger.exception so the full traceback lands in the
            # server log even when the calling agent silently absorbs the
            # text result.
            logger.exception("Tool execution error for %s", tool_name)
            return ToolExecutionResult(
                result=(
                    f"[TOOL_FAILED] Tool '{tool_name}' did NOT execute.\n"
                    f"Reason: {type(e).__name__}: {e}\n"
                    f"DO NOT claim the tool was launched. Acknowledge the "
                    f"failure to the user, surface the reason, and ask "
                    f"whether to retry or diagnose."
                )
            )

    def _get_workflow_context_updates(self) -> dict[str, Any]:
        """Extract current workflow state for context_updates.

        P1: ships ``phase_outputs`` and ``completed_phases`` in addition to
        the 3 scalar keys. Without these, the agentic-loop's
        ``update_prior_context(**result.context_updates)`` after async tools
        complete refreshes the ``workflow_status`` STRING but leaves the
        ``phase_outputs`` DICT stale. The next ``_render_prompt`` then
        builds ``StateGraphTracker`` from the stale snapshot, and
        ``get_missing_outputs()`` falsely reports the phase's outputs as
        missing — which causes ``render_guidance`` to enter the
        "Phase X incomplete" branch instead of "available_next" — giving
        the LLM contradictory signals (status says complete, guidance says
        missing). Shipping the dict + list keys lets the snapshot stay in
        lockstep with the live workflow_context.
        """
        ctx = self._session.session_context
        return {
            "workflow_status": ctx.get("workflow_status", ""),
            "current_phase": ctx.get("current_phase", ""),
            "phase_status": ctx.get("phase_status", ""),
            "phase_outputs": dict(ctx.get("phase_outputs") or {}),
            "completed_phases": list(ctx.get("completed_phases") or []),
        }

    def _try_auto_complete_gate_dependencies(self, target_phase: str) -> None:
        """P3: Auto-complete dependency phases that genuinely don't require
        user interaction (no outputs, no tools, AND NO ``requires confirmation``).

        Phases with the ``requires_confirmation`` directive are LEFT
        UNCOMPLETED here — they MUST be confirmed by the user via the
        confirmation widget. The correct auto-completion path for those is
        ``conversational_inferencer.py:636-659``, gated on
        ``_confirmation_gate_passed=True`` set by
        ``ConfirmationHandler.handle_response`` when the user clicks Proceed.

        Replaces the duplicated auto-complete-gate blocks that previously
        lived inline in ``_exec_task`` and ``_exec_research_propose`` and
        used the false summary string ``"Confirmed by user"`` even when no
        user had actually confirmed. The honest summary string here makes
        the on-disk record truthful so future audits can distinguish
        REAL user confirmations (synced from
        ``message_handlers._completed_gate_phases``) from auto-traversed
        no-op gates.
        """
        wc = self._session.workflow_context
        try:
            ci = getattr(self._session, "conversation_inferencer", None)
            sop_obj = (
                ci.prior_context.get("_sop")
                if ci and hasattr(ci, "prior_context")
                else None
            )
            if not sop_obj:
                return
            phase_node = sop_obj.get_phase(target_phase)
            if not phase_node:
                return
            completed_ids = {r.phase for r in wc.completed_phases}
            for dep_id in phase_node.depends_on:
                if dep_id in completed_ids:
                    continue
                dep_node = sop_obj.get_phase(dep_id)
                if not (dep_node and not dep_node.outputs):
                    continue
                has_tools = any(
                    s.name.lower() in ("tools", "command")
                    for s in getattr(dep_node, "subsections", [])
                )
                if has_tools:
                    continue
                # P3: NEVER auto-complete a `requires confirmation` gate.
                requires_confirmation = "requires confirmation" in (
                    getattr(dep_node, "directives", []) or []
                )
                if requires_confirmation:
                    continue  # caller's P4 _check_confirmation_gates_satisfied handles refusal
                wc.complete_phase(
                    dep_id,
                    "Auto-completed (no outputs, no tools, no confirmation required)",
                )
        except Exception as e:
            logger.warning(
                "_try_auto_complete_gate_dependencies for %s failed: %s",
                target_phase,
                e,
            )

    def _check_confirmation_gates_satisfied(
        self, sop_phase: str
    ) -> "ToolExecutionResult | None":
        """P4: Refuse to start ``sop_phase`` if any dependency has the
        ``requires_confirmation`` directive AND is not in
        ``completed_phases``. Returns a ``[BLOCKED]`` ``ToolExecutionResult``
        that the LLM understands and reacts to by emitting a confirmation
        tool. Returns None when all gates are satisfied.

        Mirrors the established ``[TOOL_FAILED]`` sentinel pattern elsewhere
        in this class — the LLM is trained on prompts that recognize the
        ``[BLOCKED]`` prefix as a structured precondition failure rather
        than an unstructured tool error.

        Defense-in-depth: even after P3 makes the auto-complete-gate path
        honest (skipping ``requires_confirmation`` deps), nothing prevents
        the LLM from skipping the confirmation widget itself and emitting
        the next-phase tool directly. P4 catches that and forces the LLM to
        re-emit the correct widget.
        """
        ci = getattr(self._session, "conversation_inferencer", None)
        sop_obj = (
            ci.prior_context.get("_sop")
            if ci and hasattr(ci, "prior_context")
            else None
        )
        if not sop_obj:
            return None
        phase_node = sop_obj.get_phase(sop_phase)
        if not phase_node:
            return None
        completed_ids = {
            r.phase for r in self._session.workflow_context.completed_phases
        }
        unsatisfied: list[tuple[str, str]] = []
        for dep_id in phase_node.depends_on:
            if dep_id in completed_ids:
                continue
            dep_node = sop_obj.get_phase(dep_id)
            if dep_node and "requires confirmation" in (
                getattr(dep_node, "directives", []) or []
            ):
                unsatisfied.append((dep_id, dep_node.name or dep_id))
        if not unsatisfied:
            return None
        names = ", ".join(f"Phase {pid} ({pname})" for pid, pname in unsatisfied)
        logger.info(
            "[BLOCKED] Cannot start Phase %s: gating phase(s) require user "
            "confirmation: %s",
            sop_phase,
            names,
        )
        return ToolExecutionResult(
            result=(
                f"[BLOCKED] Cannot start Phase {sop_phase}: gating phase(s) "
                f"require user confirmation first: {names}. Emit a "
                f"`confirmation` conversation tool with the appropriate "
                f"`view` parameter (pointing to the prior phase's primary "
                f"output) to ask the user to approve before proceeding."
            )
        )

    # -- Task queue infrastructure -------------------------------------------

    @staticmethod
    def _build_hypothesis_task_query(
        hypothesis: dict[str, Any], workflow_target_path: str = ""
    ) -> str:
        """Build the /task request text from a selected hypothesis."""
        parts = [
            f"Implement hypothesis {hypothesis.get('id', '')}: {hypothesis.get('title', '')}"
        ]
        if workflow_target_path:
            parts.append(f"Target codebase: {workflow_target_path}")
        if hypothesis.get("problem"):
            parts.append(f"PROBLEM: {hypothesis['problem']}")
        if hypothesis.get("approach"):
            parts.append(f"APPROACH: {hypothesis['approach']}")
        if hypothesis.get("cross_refs"):
            parts.append(f"Cross-refs: {hypothesis['cross_refs']}")
        return "\n".join(parts)

    @staticmethod
    def _build_batch_task_query(
        hypotheses: list[dict[str, Any]],
        batch_info: dict[str, Any],
        workflow_target_path: str = "",
    ) -> str:
        """Build a combined /task prompt for multiple hypotheses in the same batch."""
        parts = [
            f"Implement the following hypotheses together "
            f"(Batch {batch_info.get('id', '?')}: {batch_info.get('label', '')}):"
        ]
        if workflow_target_path:
            parts.append(f"Target codebase: {workflow_target_path}")
        parts.append("")
        for hyp in hypotheses:
            parts.append(f"Hypothesis {hyp.get('id', '')}: {hyp.get('title', '')}")
            if hyp.get("problem"):
                parts.append(f"  PROBLEM: {hyp['problem']}")
            if hyp.get("approach"):
                parts.append(f"  APPROACH: {hyp['approach']}")
            if hyp.get("cross_refs"):
                parts.append(f"  Cross-refs: {hyp['cross_refs']}")
            parts.append("")
        parts.append("These hypotheses are in the same batch and may share code areas.")
        parts.append("Implement them cohesively.")
        return "\n".join(parts)

    async def create_experiment_hub(
        self,
        selected_details: list[dict[str, Any]],
        proposals_data: dict[str, Any],
        custom_queries: list[str] | None = None,
        group_by: str = "batch",
        initial_view: str | None = None,
        auto_implement: bool = True,
    ) -> str:
        """Create an Implementation Hub.

        Two operating modes (controlled by `auto_implement`):

        * `auto_implement=True` (default, back-compat) — "Path A":
          group hypotheses into batches, send initial multi-task
          notification with batch_queue + selection_snapshot, AND
          immediately enqueue one `/task` per batch. Implementations
          start running. Used by `proposal_selection.handle_response`
          (in-chat selection submit) — the user has already curated
          their selection and committed.

        * `auto_implement=False` — "Path B" (Phase 2b Hub-direct-open):
          create the Hub SHELL only. Send WS notification with
          selection_snapshot.selectedProposals pre-loaded BUT empty
          batch_queue, and SKIP the enqueue loop. The Hub's Selection
          view shows the pre-checked hypotheses; the user adjusts and
          submits there to start implementations. Used by
          `open_experiment_hub`.

        Returns the multi_task_id (always — both modes mint one).

        Args:
            selected_details: Full hypothesis dicts. In Path A these are
                the user's curated selections; in Path B these are the
                top-N pre-selected (user will adjust in Hub).
            proposals_data: Original proposals metadata (phases/batches structure).
            custom_queries: Optional custom queries from the user.
            group_by: Grouping mode — 'batch', 'all', or 'hypothesis'.
                Only consulted when `auto_implement=True`.
            initial_view: Optional Hub view to pre-select on creation
                ('selection' for the Hub's Selection view; falls back
                to Hub default when omitted). Used by Path B so the
                Hub-direct-open flow lands on Selection view where
                the user can adjust the pre-loaded top-N.
            auto_implement: When True (default), enqueue per-batch
                /task invocations to start implementations immediately.
                When False, create the Hub shell ONLY (no batches, no
                implementations) — the user starts implementations by
                submitting from the Hub Selection view.
        """
        import uuid as _uuid

        from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.conversational.handlers.proposal_selection import (
            _group_selected_by_batch,
        )

        wt = ""
        if hasattr(self._session.info, "workflow_target_path"):
            wt = self._session.info.workflow_target_path or ""

        # Group hypotheses based on mode. Path B (`auto_implement=False`)
        # skips grouping entirely — no batches will be enqueued, so the
        # WS event's batch_queue is empty and the Hub Progress view starts
        # blank. The user populates batches by submitting from the Hub
        # Selection view.
        if not auto_implement:
            groups: list[dict[str, Any]] = []
        elif group_by == "all":
            groups = [
                {
                    "batch_id": "all",
                    "batch_label": "All Selected",
                    "hypotheses": selected_details,
                }
            ]
        elif group_by == "hypothesis":
            groups = [
                {
                    "batch_id": h.get("id", ""),
                    "batch_label": h.get("title", "")[:40],
                    "hypotheses": [h],
                }
                for h in selected_details
            ]
        else:
            # Default: group by batch
            groups = _group_selected_by_batch(
                selected_details,
                proposals_data if isinstance(proposals_data, dict) else {},
            )

        multi_task_id = f"multi-{_uuid.uuid4().hex[:8]}"

        # Persist a chronological task_ref marker BEFORE the WS emit so a
        # crash in the window between persist and emit re-emerges the chip
        # at the right conversation position on resume (rather than at the
        # bottom via TASK_STATUS replay). Best-effort: chip-write failures
        # MUST NOT abort the task launch — chip placement is auxiliary UI
        # metadata. Failure here only affects resume positioning.
        if self._session.conversation:
            try:
                self._session.conversation.add_task_ref(
                    task_id=multi_task_id,
                    label="Experiment Hub",
                    tool_name="proposal_selection",
                    multi_task_id=multi_task_id,
                )
                await self._persist()
            except Exception as chip_err:
                logger.warning(
                    "add_task_ref failed for multi_task_id=%s — task will "
                    "still launch, chip placement may be missing on "
                    "resume: %s",
                    multi_task_id,
                    chip_err,
                )

        # Send initial multi-task notification
        interactive = getattr(self._session, "interactive", None)
        if interactive and hasattr(interactive, "_send_response"):
            import asyncio as _asyncio

            from agent_foundation.ui.interactive_base import (
                InteractionFlags,
            )

            await _asyncio.to_thread(
                interactive._send_response,
                {
                    "type": "task_status",
                    "task_id": multi_task_id,
                    "task_type": "multi",
                    "status": "starting",
                    "session_id": getattr(self._session.info, "session_id", ""),
                    "scenario": "implementation_hub",
                    # Mode-aware request label: implementation queueing mode
                    # vs preview / Selection-view mode.
                    "request": (
                        f"Implementation: {len(selected_details)} hypotheses "
                        f"in {len(groups)} {'batch' if group_by == 'batch' else 'group'}(s)"
                        if auto_implement
                        else f"Hub opened (preview): {len(selected_details)} "
                        f"hypotheses pre-selected — adjust + submit from "
                        f"Selection view to start implementations"
                    ),
                    # Path B (auto_implement=False) sends EMPTY batch_queue —
                    # nothing has been enqueued for implementation yet.
                    "batch_queue": [
                        {
                            "batch_id": bg["batch_id"],
                            "batch_label": bg["batch_label"],
                            "hypothesis_ids": [
                                h.get("id", "") for h in bg["hypotheses"]
                            ],
                            "status": "queued",
                        }
                        for bg in groups
                    ],
                    "selection_snapshot": {
                        "proposals": proposals_data
                        if isinstance(proposals_data, dict)
                        else {},
                        "selectedProposals": [
                            h.get("id", "") for h in selected_details
                        ],
                        "customQueries": custom_queries or [],
                    },
                    # Optional Hub-view pre-selection (set by
                    # `open_experiment_hub` for the Phase 2b Hub-direct-open
                    # path; absent for the standard `proposal_selection`
                    # submit path which falls back to the Hub's default
                    # initial view, typically Progress).
                    "metadata": (
                        {"initial_view": initial_view} if initial_view else {}
                    ),
                },
                InteractionFlags.MessageOnly,
            )

        # Store selected proposals in phase outputs
        wc = self._session.workflow_context
        wc.phase_outputs["research_proposals"] = selected_details

        # Set this hub as the active queue target
        wc.active_multi_task_id = multi_task_id

        # Enqueue one task per group — SKIPPED entirely in Path B
        # (`auto_implement=False`). User triggers implementations later
        # by submitting from the Hub Selection view.
        if auto_implement:
            for bg in groups:
                if group_by == "hypothesis" and len(bg["hypotheses"]) == 1:
                    query = SessionToolExecutor._build_hypothesis_task_query(
                        bg["hypotheses"][0], wt
                    )
                else:
                    query = SessionToolExecutor._build_batch_task_query(
                        bg["hypotheses"], bg, wt
                    )
                hyp_ids = ",".join(h.get("id", "") for h in bg["hypotheses"])
                await self.enqueue_and_maybe_execute(
                    tool_name="task",
                    request=query,
                    title=f"B{bg['batch_id']}: {hyp_ids}"
                    if group_by == "batch"
                    else hyp_ids,
                    args={
                        "request": query,
                        "template_version": "hypothesis_implementation",
                    },
                    hypothesis_id=hyp_ids,
                    phase="3",
                    multi_task_id=multi_task_id,
                    batch_id=bg.get("batch_id", "") if group_by == "batch" else "",
                    batch_label=bg.get("batch_label", "")
                    if group_by == "batch"
                    else "",
                )

            # Force a yield so _try_start_next_task() coroutines can execute.
            # Without this, all scheduled tasks pile up if the await inside
            # enqueue_and_maybe_execute() was skipped due to exception handling.
            import asyncio as _asyncio_yield

            await _asyncio_yield.sleep(0)

        # Persist now so the hub's existence (active_multi_task_id, all queued
        # entries with their batch_id/batch_label/multi_task_id metadata) is
        # captured on disk immediately. Without this, a server crash before
        # the next user message would lose the hub.
        await self._persist()

        return multi_task_id

    async def open_experiment_hub(
        self,
        *,
        proposals_data: dict[str, Any] | None,
        pre_select_top_n: int = 5,
        initial_view: str = "selection",
    ) -> str | None:
        """Open the Experiment Hub for this session, idempotently.

        Used by the `confirmation` widget when its
        `metadata.on_yes_action == "open_experiment_hub"` branch
        fires (Phase 2b "Go To Experiment Hub" path). Returns the
        `multi_task_id` (existing if a Hub already exists in this
        session, otherwise newly minted).

        Behavior:
          1. Idempotency guard: if `workflow_context.active_multi_task_id`
             is already set, emit a `task_status: focus` WS event for that
             tab and return that ID. NO duplicate hub created.
          2. Otherwise compute top-N globally-ranked hypotheses across
             all phases (sort by `rank` ascending; tiebreak by
             `len(source_workers)` descending then `id` lexical) and
             call `create_experiment_hub(top_n_details, proposals_data)`.
          3. The existing `task_status: starting` WS event fires inside
             `create_experiment_hub`; the React `useSessionManager`
             reducer auto-creates the Hub subtab. Pass-through
             `metadata.initial_view` so the reducer pre-selects the
             Selection view (not Progress) — user hasn't curated yet.

        Edge cases:
          * `proposals_data` missing/empty → log WARNING, return None
            (caller should surface a toast).
          * Fewer than `pre_select_top_n` proposals exist → take all
            available.
          * Tied ranks → secondary sort by `len(source_workers)` desc,
            then by `id` lexical for determinism.
        """
        wc = self._session.workflow_context

        # 1. Idempotency: focus existing Hub tab instead of creating a
        # second one. Mirrors the `task_status: starting` payload shape
        # but with `status: focus` so React's reducer focuses without
        # re-running the CREATE_MULTI_TASK branch.
        existing_mid = getattr(wc, "active_multi_task_id", None)
        if existing_mid:
            interactive = getattr(self._session, "interactive", None)
            if interactive and hasattr(interactive, "_send_response"):
                import asyncio as _asyncio

                from agent_foundation.ui.interactive_base import (
                    InteractionFlags,
                )

                try:
                    await _asyncio.to_thread(
                        interactive._send_response,
                        {
                            "type": "task_status",
                            "task_id": existing_mid,
                            "task_type": "multi",
                            "status": "focus",
                            "session_id": getattr(self._session.info, "session_id", ""),
                            "metadata": {"initial_view": initial_view},
                        },
                        InteractionFlags.MessageOnly,
                    )
                except Exception as emit_err:
                    logger.warning(
                        "open_experiment_hub: focus emit failed mid=%s: %s",
                        existing_mid,
                        emit_err,
                    )
            logger.info(
                "open_experiment_hub: focusing existing multi_task_id=%s "
                "(idempotency guard)",
                existing_mid,
            )
            return existing_mid

        # 2. Validate proposals_data shape; degrade gracefully if missing.
        if not isinstance(proposals_data, dict):
            logger.warning(
                "open_experiment_hub: proposals_data is %s, expected dict; "
                "Hub cannot be opened with selections",
                type(proposals_data).__name__,
            )
            return None
        phases = proposals_data.get("phases") or []
        if not isinstance(phases, list) or not phases:
            logger.warning(
                "open_experiment_hub: proposals_data has no `phases`; "
                "Hub cannot be opened with selections"
            )
            return None

        # 3. Flatten + sort globally by rank.
        all_proposals: list[dict[str, Any]] = []
        for ph in phases:
            if isinstance(ph, dict):
                for p in ph.get("proposals", []) or []:
                    if isinstance(p, dict) and p.get("id"):
                        all_proposals.append(p)
        if not all_proposals:
            logger.warning(
                "open_experiment_hub: no proposals across all phases; "
                "Hub cannot be opened with selections"
            )
            return None

        def _sort_key(p: dict[str, Any]) -> tuple[int, int, str]:
            # Lower rank = higher priority. Tiebreak: more source_workers
            # = better validated; then id lexical for determinism.
            rank = p.get("rank")
            try:
                rank_i = int(rank) if rank is not None else 9999
            except (TypeError, ValueError):
                rank_i = 9999
            workers = p.get("source_workers") or []
            # Negate workers count so descending sorts naturally as ascending.
            return (rank_i, -len(workers), str(p.get("id", "")))

        all_proposals.sort(key=_sort_key)
        n = max(1, int(pre_select_top_n))
        top_n = all_proposals[:n]
        logger.info(
            "open_experiment_hub: pre-selecting top-%d of %d proposals: %s",
            len(top_n),
            len(all_proposals),
            [p.get("id", "") for p in top_n],
        )

        # 4. Delegate to create_experiment_hub with `auto_implement=False`
        # (Path B contract: create the Hub SHELL only — pre-loaded with
        # top-N selections in selection_snapshot, but NO batches and NO
        # implementations queued). The user reviews + adjusts in the Hub
        # Selection view, then submits there to trigger implementations.
        # `initial_view` pass-through ensures the Hub opens on Selection.
        multi_task_id = await self.create_experiment_hub(
            selected_details=top_n,
            proposals_data=proposals_data,
            custom_queries=[],
            group_by="batch",
            initial_view=initial_view,
            auto_implement=False,
        )
        return multi_task_id

    async def add_to_experiment_hub(
        self,
        multi_task_id: str,
        request: str,
        title: str,
        batch_id: str = "",
        batch_label: str = "",
        hypothesis_id: str = "",
    ) -> str:
        """Add a /task to an existing experiment hub's queue.

        batch_id / batch_label / hypothesis_id: first-class metadata for the
        multi-round Selection View "add more hypotheses" flow. Without these,
        Layer 4 resume rehydration falls back to title-regex parsing.

        Returns the task_id for the new queue entry.
        """
        task_id = await self.enqueue_and_maybe_execute(
            tool_name="task",
            request=request,
            title=title,
            args={"request": request, "template_version": "hypothesis_implementation"},
            hypothesis_id=hypothesis_id,
            phase="3",
            multi_task_id=multi_task_id,
            batch_id=batch_id,
            batch_label=batch_label,
        )
        # Persist the new queue entry so a restart between this add and the next
        # user message won't lose it.
        await self._persist()
        return task_id

    async def setup_submission_script(
        self,
        multi_task_id: str,
        setup_id: str,
        setup_name: str,
        reference_scripts: list[str],
        library_template: str | None,
        reference_command: str,
        additional_instructions: str,
        selected_hypothesis_ids: list[str],
    ) -> str:
        """Enqueue a PTI task that generates a parameterized submission script.

        Inlines the user's reference materials (custom paths + optional
        library template) into the prompt and registers the
        ``experiment_runner_creation`` completion handler so the WebUI is
        notified when ``outputs/submit_v1.py`` and ``outputs/launch.json``
        are produced. Flag-name resolution happens upstream in the WebUI
        Submit modal (v2 contract) — the script receives canonical config
        field names verbatim, with no ID-to-name translation table.

        ``phase=""`` is critical: setup is NOT part of any hypothesis-
        implementation phase. Inheriting one would make ``is_phase_complete``
        in _try_start_next_task fire prematurely and confuse the SOP tracker.

        Returns the queue task_id (PTI subtab id from the frontend's
        perspective).
        """
        from rankevolve.src.server.submission_templates_loader import (
            _inline_script,
            _resolve_library_template,
        )

        refs_inlined: list[str] = []
        if library_template:
            for path in _resolve_library_template(library_template):
                refs_inlined.append(_inline_script(path))
        for path_str in reference_scripts or []:
            if not isinstance(path_str, str) or not path_str:
                continue
            refs_inlined.append(_inline_script(Path(path_str)))

        wt = ""
        if hasattr(self._session.info, "workflow_target_path"):
            wt = self._session.info.workflow_target_path or ""

        query = (
            f"Generate a parameterized submission setup for combo "
            f"'{setup_name}'.\n\n"
            f"Target codebase: {wt}\n"
            f"Hypotheses: {', '.join(selected_hypothesis_ids)}\n\n"
            f"## Output requirements (BOTH files required — completion hook "
            f"validates presence of each)\n"
            f"1. outputs/submit_v1.py — the submission entry point. "
            f"Importable as a fbcode module (NOT a standalone script — at "
            f"Meta, `python <path>` cannot resolve fbcode imports). "
            f"Accepts:\n"
            f"     --enable-flags enable_foo,enable_bar  (comma-separated\n"
            f"                              CONFIG FIELD NAMES already\n"
            f"                              resolved by the hub; build the\n"
            f"                              overrides dict directly as\n"
            f"                              {{name: True for name in\n"
            f"                              received_names}} — do NOT define\n"
            f"                              any HYPOTHESIS_FLAG_MAP table or\n"
            f"                              ID-to-name translation logic)\n"
            f"     --experiment-name <str>\n"
            f"     --app-layer-version <str>  REQUIRED — the fbpkg version\n"
            f"                              (e.g. fire-app:2941a32) the user\n"
            f"                              typed in the Submit Confirm modal.\n"
            f"                              Pass through to FBLearner as the\n"
            f"                              package_version for the relevant\n"
            f"                              fbpkg slot. Do NOT auto-detect for\n"
            f"                              the runner code path — the user\n"
            f"                              value is authoritative.\n"
            f"   Print the FBLearner flow URI on stdout as ONE LINE "
            f"prefixed:\n"
            f"     FLOW_URI: <url>\n"
            f"   And MAST job names when known:\n"
            f"     MAST_JOB: <job_name>\n"
            f"   IMPORTANT: use bare `print(...)` for these two contract "
            f"lines, NOT `logger.info(...)`. The runner regex anchors at "
            f"^FLOW_URI:/^MAST_JOB:; any logger prefix (timestamp, level) "
            f"breaks the match and the URL is silently lost.\n"
            f"   Exit 0 on success, 1 on failure.\n\n"
            f"2. outputs/launch.json — the launch invocation, structured "
            f"as:\n"
            f'     {{"launcher": "buck_run_auto",\n'
            f'      "script_args": ["--enable-flags", "${{ENABLE_FLAGS}}",\n'
            f'                       "--experiment-name", "${{EXP_NAME}}",\n'
            f'                       "--app-layer-version", "${{APP_LAYER_VERSION}}"],\n'
            f'      "cwd": "${{CODEBASE_ROOT}}"}}\n'
            f"   STRICT REQUIREMENTS (runner enforces and rejects "
            f"otherwise):\n"
            f"   - `launcher` MUST be present and set to the literal "
            f'string `"buck_run_auto"` — the only currently-registered '
            f"launcher. Setting it explicitly (rather than relying on the "
            f"runner's backward-compat default) makes the launch.json "
            f"self-documenting for anyone reading it later.\n"
            f"   - `script_args` MUST be a list of strings. The runner "
            f"dispatches via the `launcher` field; PTI does NOT choose a "
            f"wrapper command.\n"
            f"   - `cwd` is OPTIONAL; defaults to ${{CODEBASE_ROOT}}.\n"
            f"   - NO shell metacharacters anywhere in script_args (no "
            f"`;`, `|`, `&&`, `>`, backticks).\n"
            f"   - `script_args` MUST include "
            f'`"--app-layer-version", "${{APP_LAYER_VERSION}}"` (paired '
            f"tokens, in that order). Never bake a literal version into "
            f"`script_args` or the script body — the fbpkg version is "
            f"per-submission user input.\n"
            f"   The runner substitutes ${{ENABLE_FLAGS}}, ${{EXP_NAME}}, "
            f"${{APP_LAYER_VERSION}}, and ${{CODEBASE_ROOT}} at spawn time. "
            f"The script args you choose must match the CLI argparse you "
            f"defined in submit.py.\n\n"
            f"## User-provided reference command (authoritative for "
            f"launch.json)\n"
            f"{reference_command}\n\n"
            f"## Additional Instructions\n{additional_instructions}\n\n"
            f"## Reference Material\n\n" + "\n\n".join(refs_inlined)
        )

        task_id = await self.enqueue_and_maybe_execute(
            tool_name="task",
            request=query,
            title=f"Setup: {setup_name}",
            args={
                "request": query,
                "template_version": "experiment_runner_creation",
                # Echo setup_id back in the completion event so the WebUI
                # can route the result to the right hub_<mid>_setup.json.
                "setup_id": setup_id,
                "setup_name": setup_name,
            },
            phase="",  # NOT part of any SOP phase — see docstring
            multi_task_id=multi_task_id,
            batch_id="setup",
            batch_label=f"Setup: {setup_name}",
            on_complete_handler="experiment_runner_creation",
            # scope="hub_setup" routes the task_status events to the
            # session-level subtab branch in the WebUI reducer, NOT into
            # the hub's runQueue display. Setup tasks then appear as
            # their own sidebar entries (alongside Codebase Investigation
            # / Research & Proposal) instead of as `Bsetup` tiles inside
            # the Experiment Hub Progress tab. Backend completion routing
            # is unaffected — multi_task_id remains on the entry for the
            # _setup_completion_hook → _apply_setup_completed path.
            scope="hub_setup",
        )

        # Emit setup_task_started so the WebUI can populate
        # hub_<mid>_setup.json's setup.taskId BEFORE PTI completes.
        # Without this, setup.taskId would only get written at completion
        # (apply_setup_completed_event), and the SubmissionFooterBar's
        # State B "click to view progress" navigation would have nothing
        # to navigate to throughout the entire in_progress window.
        interactive = getattr(self._session, "interactive", None)
        if interactive and hasattr(interactive, "_send_response"):
            try:
                import asyncio as _asyncio_emit

                from agent_foundation.ui.interactive_base import (
                    InteractionFlags as _IF_emit,
                )

                started_event = {
                    "type": "setup_task_started",
                    "session_id": getattr(self._session.info, "session_id", ""),
                    "multi_task_id": multi_task_id,
                    "setup_id": setup_id,
                    "task_id": task_id,
                }
                await _asyncio_emit.to_thread(
                    interactive._send_response,
                    started_event,
                    _IF_emit.MessageOnly,
                )
            except Exception:
                # Best-effort — failure here only delays State B's "view
                # progress" navigation; the setup itself proceeds normally
                # and apply_setup_completed_event will eventually write
                # taskId at completion.
                pass

        await self._persist()
        return task_id

    async def _setup_completion_hook(self, entry: dict[str, Any]) -> None:
        """Post-PTI hook: validate outputs and emit ``setup_completed`` event.

        Validation rules (M1 fix from the design doc — "marking ready while
        launch.json is absent makes the very first Submit fail with 'PTI did
        not produce launch.json'"):
          1. ``outputs/submit_v*.py`` must exist (pick highest version).
          2. ``outputs/launch.json`` must exist, parse as JSON, and contain
             both ``cmd`` (list[str]) and ``cwd`` (str).

        On success the hook ships the script + launch CONTENT (not just
        paths) back to the WebUI via the response queue. WebUI is the SOLE
        writer of ``hub_<mid>_setup.json`` (single-writer invariant from
        Section 5) — it picks the next version number under its in-process
        lock and writes the canonical ``setup_scripts/<mid>/submit_v<n>.py``.
        Shipping content (not paths) eliminates the cross-process race
        between PTI Re-generate and drawer Save.

        On any validation failure the hook still emits ``setup_completed``
        but with ``status="error"`` and a specific message — the user gets a
        clear setup-time error instead of a confusing first-Submit failure.
        """
        import json as _json

        args = entry.get("args") or {}
        multi_task_id = entry.get("multi_task_id") or ""
        setup_id = (args.get("setup_id") if isinstance(args, dict) else None) or ""
        setup_name = (args.get("setup_name") if isinstance(args, dict) else None) or ""
        task_id = entry.get("task_id") or ""
        workspace_str = entry.get("workspace") or ""
        queue_status = entry.get("status") or ""

        # Defensive: PTI itself may have errored before producing outputs.
        # Surface that distinctly from "completed but missing files" so the
        # frontend can show "PTI failed" vs "PTI completed but produced no
        # script". Both ultimately mark the setup status='error'.
        if queue_status == "error":
            await self._emit_setup_completed(
                multi_task_id=multi_task_id,
                setup_id=setup_id,
                setup_name=setup_name,
                task_id=task_id,
                status="error",
                error=(entry.get("result_summary") or "Setup task failed")[:200],
                script_content=None,
                launch_content=None,
                script_basename=None,
            )
            return

        if not workspace_str:
            await self._emit_setup_completed(
                multi_task_id=multi_task_id,
                setup_id=setup_id,
                setup_name=setup_name,
                task_id=task_id,
                status="error",
                error="Setup completed without producing a workspace path",
                script_content=None,
                launch_content=None,
                script_basename=None,
            )
            return

        outputs_dir = Path(workspace_str) / "outputs"
        # Accept both `submit.py` (simple) and `submit_v<n>.py` (PTI may
        # iterate before settling on a final version). Sort puts
        # `submit.py` lexically BEFORE `submit_v*.py` (`.` 0x2e < `_`
        # 0x5f), so the versioned filename wins as tie-breaker — which
        # is the right semantics: a versioned filename is intentional
        # iteration. Two explicit globs (rather than `submit*.py`) keep
        # discovery anchored to the exact contract names so support
        # files like `submit_helpers.py` aren't accidentally picked up.
        candidates = sorted(
            list(outputs_dir.glob("submit.py")) + list(outputs_dir.glob("submit_v*.py"))
        )
        if not candidates:
            await self._emit_setup_completed(
                multi_task_id=multi_task_id,
                setup_id=setup_id,
                setup_name=setup_name,
                task_id=task_id,
                status="error",
                error="Setup completed but no script was produced",
                script_content=None,
                launch_content=None,
                script_basename=None,
            )
            return
        script_path = candidates[-1]

        launch_path = outputs_dir / "launch.json"
        if not launch_path.is_file():
            await self._emit_setup_completed(
                multi_task_id=multi_task_id,
                setup_id=setup_id,
                setup_name=setup_name,
                task_id=task_id,
                status="error",
                error=(
                    "Setup did not produce outputs/launch.json — script cannot "
                    "be launched"
                ),
                script_content=None,
                launch_content=None,
                script_basename=None,
            )
            return

        try:
            launch_text = launch_path.read_text(encoding="utf-8")
            launch_data = _json.loads(launch_text)
        except Exception as e:
            await self._emit_setup_completed(
                multi_task_id=multi_task_id,
                setup_id=setup_id,
                setup_name=setup_name,
                task_id=task_id,
                status="error",
                error=f"launch.json is not valid JSON: {e}"[:200],
                script_content=None,
                launch_content=None,
                script_basename=None,
            )
            return

        if not isinstance(launch_data, dict):
            await self._emit_setup_completed(
                multi_task_id=multi_task_id,
                setup_id=setup_id,
                setup_name=setup_name,
                task_id=task_id,
                status="error",
                error="launch.json must be a JSON object with `script_args` (list[str]) and optional `cwd` (str)",
                script_content=None,
                launch_content=None,
                script_basename=None,
            )
            return

        # Option 3 schema: launch.json carries `script_args` (the args
        # passed to the script via `buck run :auto-target -- *args`)
        # and optional `cwd` (defaults to the resolved codebase root).
        # The runner ALWAYS spawns via `buck run` against an
        # auto-installed BUCK target; PTI no longer chooses a wrapper.
        script_args = launch_data.get("script_args")
        cwd = launch_data.get("cwd")
        if script_args is None:
            # Soft-explain old schema for sessions migrating from v1.
            err = (
                "launch.json uses the old `cmd`/`cwd` schema. Re-generate "
                "the setup or edit launch.json via the script editor "
                "drawer to use the new schema: "
                '`{"script_args": [...], "cwd": "${CODEBASE_ROOT}"}`'
                if "cmd" in launch_data
                else "launch.json missing required `script_args` (list of strings)"
            )
            await self._emit_setup_completed(
                multi_task_id=multi_task_id,
                setup_id=setup_id,
                setup_name=setup_name,
                task_id=task_id,
                status="error",
                error=err,
                script_content=None,
                launch_content=None,
                script_basename=None,
            )
            return
        if not isinstance(script_args, list) or not all(
            isinstance(c, str) for c in script_args
        ):
            await self._emit_setup_completed(
                multi_task_id=multi_task_id,
                setup_id=setup_id,
                setup_name=setup_name,
                task_id=task_id,
                status="error",
                error="launch.json `script_args` must be a list of strings",
                script_content=None,
                launch_content=None,
                script_basename=None,
            )
            return
        if cwd is not None and (not isinstance(cwd, str) or not cwd):
            await self._emit_setup_completed(
                multi_task_id=multi_task_id,
                setup_id=setup_id,
                setup_name=setup_name,
                task_id=task_id,
                status="error",
                error="launch.json `cwd` (when present) must be a non-empty string",
                script_content=None,
                launch_content=None,
                script_basename=None,
            )
            return

        # Optional `launcher` field — defaults to buck_run_auto when
        # omitted (backward compat with v1-era launch.json files).
        # Validate against the registry so unknown launcher names fail
        # loudly here rather than at first Submit. Lazy-import to avoid
        # pulling submission_launcher into tool_executor's import chain
        # for non-submission-script tasks.
        launcher_field = launch_data.get("launcher")
        if launcher_field is not None:
            if not isinstance(launcher_field, str) or not launcher_field:
                await self._emit_setup_completed(
                    multi_task_id=multi_task_id,
                    setup_id=setup_id,
                    setup_name=setup_name,
                    task_id=task_id,
                    status="error",
                    error=(
                        "launch.json `launcher` (when present) must be a "
                        "non-empty string identifying a known launcher "
                        "(e.g. 'buck_run_auto')"
                    ),
                    script_content=None,
                    launch_content=None,
                    script_basename=None,
                )
                return
            from rankevolve.src.server.submission_launcher import known_launcher_names

            available = known_launcher_names()
            if launcher_field not in available:
                await self._emit_setup_completed(
                    multi_task_id=multi_task_id,
                    setup_id=setup_id,
                    setup_name=setup_name,
                    task_id=task_id,
                    status="error",
                    error=(
                        f"launch.json declares unknown launcher "
                        f"{launcher_field!r}. Available: {available}. "
                        "Re-generate the setup or fix via the editor drawer."
                    ),
                    script_content=None,
                    launch_content=None,
                    script_basename=None,
                )
                return

        try:
            script_content = script_path.read_text(encoding="utf-8")
        except Exception as e:
            await self._emit_setup_completed(
                multi_task_id=multi_task_id,
                setup_id=setup_id,
                setup_name=setup_name,
                task_id=task_id,
                status="error",
                error=f"Failed to read {script_path.name}: {e}"[:200],
                script_content=None,
                launch_content=None,
                script_basename=None,
            )
            return

        await self._emit_setup_completed(
            multi_task_id=multi_task_id,
            setup_id=setup_id,
            setup_name=setup_name,
            task_id=task_id,
            status="ready",
            error="",
            script_content=script_content,
            launch_content=launch_text,
            script_basename=script_path.name,
        )

    async def _emit_setup_completed(
        self,
        multi_task_id: str,
        setup_id: str,
        setup_name: str,
        task_id: str,
        status: str,
        error: str,
        script_content: str | None,
        launch_content: str | None,
        script_basename: str | None,
    ) -> None:
        """Push a ``setup_completed`` event onto the response queue.

        Wire-compatible with the response-queue pipeline that
        agent_service_bridge.poll_responses already consumes — same shape
        as task_status events. The WebUI's poll_responses extension
        (Step 4) routes this to the per-hub setup-state PATCH path.

        Sending CONTENT (not paths) is the enforcement of the single-writer
        invariant: WebUI picks ``submit_v<n+1>.py`` under its in-process
        lock and writes the canonical version. The agent server's task
        workspace remains transient/internal.
        """
        interactive = getattr(self._session, "interactive", None)
        if interactive is None or not hasattr(interactive, "_send_response"):
            logger.warning(
                "setup_completed: no interactive available for session %s; "
                "WebUI will only see the result on next reconcile",
                getattr(self._session.info, "session_id", ""),
            )
            return
        from agent_foundation.ui.interactive_base import (
            InteractionFlags,
        )

        payload: dict[str, Any] = {
            "type": "setup_completed",
            "session_id": getattr(self._session.info, "session_id", ""),
            "multi_task_id": multi_task_id,
            "setup_id": setup_id,
            "setup_name": setup_name,
            "task_id": task_id,
            "status": status,
            "error": error,
        }
        # Don't include `null` fields when the setup errored — keeps the
        # event compact and makes intent clear (no content available).
        if script_content is not None:
            payload["script_content"] = script_content
        if launch_content is not None:
            payload["launch_content"] = launch_content
        if script_basename is not None:
            payload["script_basename"] = script_basename
        try:
            import asyncio as _asyncio

            await _asyncio.to_thread(
                interactive._send_response,
                payload,
                InteractionFlags.MessageOnly,
            )
        except Exception as e:
            logger.error("Failed to emit setup_completed event: %s", e)

    async def run_submission_script(
        self,
        multi_task_id: str,
        submission_id: str,
        setup_id: str,
        script_path: str,
        launch_path: str,
        enable_flags: list[str],
        experiment_name: str,
        submission_label: str,
        app_layer_version: str = "",
        build_command: str = "",
    ) -> str:
        """Enqueue a submission_run task that spawns the user's submit_v<n>.py
        as a subprocess. Returns the queue task_id (used as the run task
        subtab id from the frontend's perspective).
        """
        args = {
            "submission_run": True,
            "submission_id": submission_id,
            "setup_id": setup_id,
            "script_path": script_path,
            # CRITICAL (M1 fix): the runner reads this to load launch.json
            # and build the buck command. Direct ``python <path>`` is
            # forbidden in fbcode (see fbsource/.claude/CLAUDE.md).
            "launch_path": launch_path,
            "enable_flags": list(enable_flags or []),
            # CRITICAL: substituted into launch.json's ${EXP_NAME}.
            # Without this, FBLearner job names collide across runs of
            # the same combo.
            "experiment_name": experiment_name,
            # Per-submission fbpkg version (e.g. "fire-app:2941a32"),
            # substituted into launch.json's ${APP_LAYER_VERSION}.
            # Empty if the user hasn't supplied one; the runner raises
            # LaunchValidationError if the placeholder is present.
            "app_layer_version": app_layer_version,
            # Auto-build recipe (the user's referenceCommand from the
            # SetupWizard). When app_layer_version is empty AND this is
            # non-empty, the runner runs the build first and captures
            # the resulting fbpkg version. When both are empty, the
            # runner raises LaunchValidationError as before.
            "build_command": build_command,
        }
        task_id = await self.enqueue_and_maybe_execute(
            tool_name="submission_run",
            request=f"Run {submission_label} via {Path(script_path).name}",
            title=f"Run: {submission_label}",
            args=args,
            multi_task_id=multi_task_id,
            batch_id="run",
            batch_label=submission_label,
            # phase="" is critical — submission runs are NOT part of any
            # hypothesis-implementation phase. Inheriting one would
            # trigger is_phase_complete prematurely.
            phase="",
        )
        await self._persist()
        return task_id

    async def _exec_submission_run(
        self,
        args: dict[str, Any],
        queue_task_id: str = "",
    ) -> ToolExecutionResult:
        """Execute a submission_run queue entry.

        Sibling to _exec_task — does NOT share its DualInferencerBridge /
        SOP plumbing. Builds a workspace under <tasks_dir>/<run_dir>/,
        emits a task_status:starting event so the WebUI's poll_responses
        attaches a WorkspaceStreamTailer to the cache dir, then runs
        SubmissionRunner.run() and finally emits the terminal status.
        """
        from rankevolve.src.server.submission_runner import (
            LaunchValidationError,
            SubmissionRunner,
        )

        submission_id = (args or {}).get("submission_id", "")
        setup_id = (args or {}).get("setup_id", "")
        script_path_str = (args or {}).get("script_path", "")
        launch_path_str = (args or {}).get("launch_path", "")
        enable_flags = (args or {}).get("enable_flags", []) or []
        experiment_name = (args or {}).get("experiment_name", "")
        app_layer_version = (args or {}).get("app_layer_version", "") or ""
        build_command = (args or {}).get("build_command", "") or ""

        if not script_path_str or not launch_path_str:
            return ToolExecutionResult(
                result="Error: submission_run requires script_path and launch_path"
            )

        import uuid as _uuid

        # Build a workspace for this run under tasks_dir. Mirrors the
        # tasks/<task_dir>/ layout DualInferencerBridge uses; the dir name
        # uses the queue task_id so .task_meta.json sidecar reconciliation
        # can map workspace dirs back to queue entries unambiguously.
        from datetime import datetime as _dt

        ts = _dt.now().strftime("%Y%m%d_%H%M%S")
        task_id_for_dir = queue_task_id or f"task-{_uuid.uuid4().hex[:8]}"
        # Round 9: per-session layout — workspace lives at
        # <server>/sessions/<session_dir>/tasks/submission_<ts>_<task_id>/.
        ws_root = self._session.session_tasks_dir
        workspace = Path(ws_root) / f"submission_{ts}_{task_id_for_dir}"
        workspace.mkdir(parents=True, exist_ok=True)

        # Sidecar for hub_state reconcile — same convention _exec_task uses.
        try:
            import json as _json

            entry = (
                self._session.workflow_context.get_entry(queue_task_id)
                if queue_task_id
                else None
            )
            # Round 9: persist session_id + session_dir as a direct FK so future
            # task→session lookups don't need to scan every session_state.json.
            _sess_logger = getattr(self._session, "session_logger", None)
            _session_dir_name = (
                _sess_logger.session_dir.name if _sess_logger is not None else ""
            )
            sidecar = {
                "task_id": queue_task_id,
                "multi_task_id": (entry or {}).get("multi_task_id", ""),
                "tool_name": "submission_run",
                "submission_id": submission_id,
                "setup_id": setup_id,
                "session_id": self._session.info.session_id,
                "session_dir": _session_dir_name,
            }
            (workspace / ".task_meta.json").write_text(
                _json.dumps(sidecar), encoding="utf-8"
            )
        except Exception as meta_err:
            logger.warning(
                "submission_run sidecar write failed for %s: %s",
                queue_task_id,
                meta_err,
            )

        # Persist workspace path on the queue entry so resume reconcile
        # can find it.
        if queue_task_id:
            self._session.workflow_context.update_entry(
                queue_task_id, workspace=str(workspace.absolute())
            )
            await self._persist()

        # Notify the frontend so a task subtab appears with the right
        # workspace. The WebUI's poll_responses sees ``status='starting'``
        # + ``workspace=…`` and attaches a WorkspaceStreamTailer to the
        # workspace's cache dir — exactly the same path PTI uses.
        interactive = getattr(self._session, "interactive", None)
        if interactive is not None and hasattr(interactive, "_send_response"):
            from agent_foundation.ui.interactive_base import (
                InteractionFlags,
            )

            try:
                import asyncio as _asyncio

                multi_task_id_val = (
                    (entry or {}).get("multi_task_id", "") if queue_task_id else ""
                )
                start_msg = {
                    "type": "task_status",
                    "session_id": getattr(self._session.info, "session_id", ""),
                    "task_id": queue_task_id or task_id_for_dir,
                    "status": "starting",
                    "request": f"Run: {submission_id}",
                    "workspace": str(workspace.absolute()),
                }
                if multi_task_id_val:
                    start_msg["multi_task_id"] = multi_task_id_val
                await _asyncio.to_thread(
                    interactive._send_response,
                    start_msg,
                    InteractionFlags.MessageOnly,
                )
            except Exception as e:
                logger.warning(
                    "submission_run: failed to send starting notification: %s",
                    e,
                )

        # Single-writer invariant: the agent server NEVER writes
        # hub_*_submissions.json. emit_event pushes onto the response
        # queue; agent_service_bridge.poll_responses applies under the
        # WebUI's per-hub asyncio.Lock.
        async def _emit_state(extra: dict[str, Any]) -> None:
            if interactive is None or not hasattr(interactive, "_send_response"):
                return
            from agent_foundation.ui.interactive_base import (
                InteractionFlags,
            )

            payload: dict[str, Any] = {
                "type": "submission_state",
                "session_id": getattr(self._session.info, "session_id", ""),
                "multi_task_id": (entry or {}).get("multi_task_id", "")
                if queue_task_id
                else "",
                "submission_id": submission_id,
                "setup_id": setup_id,
            }
            payload.update(extra)
            try:
                import asyncio as _asyncio

                await _asyncio.to_thread(
                    interactive._send_response,
                    payload,
                    InteractionFlags.MessageOnly,
                )
            except Exception as e:
                logger.warning(
                    "submission_run: failed to emit submission_state: %s",
                    e,
                )

        # Emit an initial 'running' marker so the run row in the Monitor
        # view doesn't sit on 'submitted' for the first 10-20s while buck
        # builds. The flowUri arrives later when the script prints it.
        import time as _time

        run_started_at = int(_time.time() * 1000)
        await _emit_state(
            {
                "status": "running",
                "runTaskId": queue_task_id or task_id_for_dir,
                "runStartedAt": run_started_at,
            }
        )

        # Read workflow_target_path from session-side state (set via
        # /set-workflow-target-path). Empty if unset — the runner will
        # surface a clear LaunchValidationError if the launch.json
        # actually uses ${CODEBASE_ROOT} but workflow_target_path is
        # missing. For v1-style launch.json with no placeholder, the
        # value is ignored entirely.
        workflow_target_path = (
            getattr(self._session.info, "workflow_target_path", "") or ""
        )

        runner = SubmissionRunner(
            workspace=workspace,
            script_path=Path(script_path_str),
            enable_flags=enable_flags,
            experiment_name=experiment_name,
            launch_path=Path(launch_path_str),
            emit_event=_emit_state,
            workflow_target_path=workflow_target_path,
            codebase_root_pattern=_CODEBASE_ROOT_PATTERN,
            app_layer_version=app_layer_version,
            build_command=build_command,
        )

        terminal_status = "completed"
        terminal_error = ""
        flow_uri: str | None = None
        mast_job: str | None = None
        final_metrics: dict[str, Any] = {}
        epoch_trajectory: list[dict[str, Any]] = []
        try:
            run_result = await runner.run()
            flow_uri = run_result.get("flow_uri")
            mast_job = run_result.get("mast_job")
            exit_code = run_result.get("exit_code")
            # Plan v7 C1: pulled from runner.run() — last STATUS:-derived
            # epoch row + full trajectory. Both are absent for FBLearner
            # runs that never emit STATUS lines; auto-analysis is gated
            # on `final_metrics` being non-empty.
            final_metrics = dict(run_result.get("final_metrics") or {})
            epoch_trajectory = list(run_result.get("epoch_trajectory") or [])
            if exit_code != 0:
                terminal_status = "error"
                terminal_error = f"Subprocess exited with code {exit_code}"
        except LaunchValidationError as ve:
            terminal_status = "error"
            terminal_error = str(ve)[:300]
            logger.warning("submission_run launch validation failed: %s", ve)
        except asyncio.CancelledError:
            # SubmissionRunner.run already invoked self.cancel() under
            # asyncio.shield in its except block — the subprocess is
            # gone. We do NOT emit a submission_state event here:
            # ownership of the cancelled-state event lives in
            # _handle_task_cancel_by_id's _post_cancel_cleanup so we
            # don't double-write the per-hub submissions file under the
            # WebUI's lock (the prior plan's dual-emit race). Re-raise
            # so the queue runner records the cancel.
            raise
        except Exception as e:
            terminal_status = "error"
            terminal_error = f"submission_run error: {e}"[:300]
            logger.error(
                "submission_run error for %s: %s",
                queue_task_id or "(no-id)",
                e,
                exc_info=True,
            )

        # Plan v7 C1: kick off post-completion auto-analysis when the run
        # succeeded AND the subprocess emitted STATUS: lines we could
        # parse into final_metrics. Failures here do NOT mark the
        # submission failed — the run itself was successful, the
        # analysis is an independent value-add. analysis_task_id (when
        # set) is shipped in the terminal submission_state below so the
        # UI's clickable Stepper (B4) knows where to navigate.
        analysis_task_id: str | None = None
        if terminal_status == "completed" and final_metrics:
            try:
                analysis_task_id = await self._run_submission_analysis(
                    submission_id=submission_id,
                    multi_task_id=(entry or {}).get("multi_task_id", "")
                    if queue_task_id
                    else "",
                    setup_id=setup_id,
                    enable_flags=list(enable_flags or []),
                    experiment_name=experiment_name,
                    final_metrics=final_metrics,
                    epoch_trajectory=epoch_trajectory,
                    interactive=interactive,
                    emit_state=_emit_state,
                )
            except Exception as e:
                logger.warning(
                    "submission_run: auto-analysis failed for %s: %s",
                    submission_id,
                    e,
                    exc_info=True,
                )
                analysis_task_id = None

        await _emit_state(
            {
                "status": terminal_status,
                "runFinishedAt": int(_time.time() * 1000),
                "flowUri": flow_uri,
                "mastJob": mast_job,
                "fblearnerError": terminal_error or None,
                # Backpointer used by JobMonitorView's clickable Stepper to
                # route Analyzing/Done step clicks into the analysis subtab.
                **({"analysisTaskId": analysis_task_id} if analysis_task_id else {}),
            }
        )

        # Notify the frontend's task subtab that the run finished so the
        # tailer is stopped and the subtab badge flips off the spinner.
        if interactive is not None and hasattr(interactive, "_send_response"):
            from agent_foundation.ui.interactive_base import (
                InteractionFlags,
            )

            try:
                import asyncio as _asyncio

                end_msg = {
                    "type": "task_status",
                    "session_id": getattr(self._session.info, "session_id", ""),
                    "task_id": queue_task_id or task_id_for_dir,
                    "status": "completed"
                    if terminal_status == "completed"
                    else "error",
                }
                if terminal_error:
                    end_msg["message"] = terminal_error
                multi_task_id_val = (
                    (entry or {}).get("multi_task_id", "") if queue_task_id else ""
                )
                if multi_task_id_val:
                    end_msg["multi_task_id"] = multi_task_id_val
                await _asyncio.to_thread(
                    interactive._send_response,
                    end_msg,
                    InteractionFlags.MessageOnly,
                )
            except Exception as e:
                logger.warning(
                    "submission_run: failed to send terminal task_status: %s",
                    e,
                )

        # Mark the queue entry. Distinct from _exec_task because the
        # outer _try_start_next_task wrapper expects either an explicit
        # mark_completed/mark_error here OR a still-non-terminal status
        # for the wrapper to default-mark. Doing it here keeps the
        # status accurate (e.g., 'cancelled' surfaces on resume).
        if queue_task_id:
            wc = self._session.workflow_context
            if terminal_status == "completed":
                wc.mark_completed(
                    queue_task_id, summary=f"Run completed for {submission_id}"
                )
            else:
                wc.mark_error(
                    queue_task_id,
                    error=terminal_error or terminal_status,
                )
            await self._persist()

        return ToolExecutionResult(
            result=(
                f"submission_run {terminal_status} for {submission_id} "
                f"(workspace={workspace})"
            ),
        )

    async def _run_submission_analysis(
        self,
        submission_id: str,
        multi_task_id: str,
        setup_id: str,
        enable_flags: list[str],
        experiment_name: str,
        final_metrics: dict[str, Any],
        epoch_trajectory: list[dict[str, Any]],
        interactive: Any,
        emit_state: Any,
    ) -> str | None:
        """Plan v7 C1: post-completion auto-analysis for one submission.

        Lifecycle (mirrors the JobMonitorView's Submitted → Running →
        Analyzing → Done framing on the run row):

          1. Mint analysis_task_id + create per-analysis workspace under
             session_tasks_dir/. The workspace receives a tailer-readable
             cache dir so the new task subtab streams content live.
          2. Emit submission_state{status:'analyzing', analysisTaskId} so
             the run row's lifecycle Stepper advances to step 2 BEFORE the
             analysis content is generated.
          3. Emit task_status{starting, scenario:'experiment_analysis'} so
             the WebUI's create-on-fly branch (useSessionManager.js:474)
             materializes a new analysis subtab attached to the same Hub.
          4. Generate analysis content: heuristic delta vs the active
             baseline submission for this hub (when one exists), assemble
             a markdown summary + verdict, write to outputs/analysis.md.
             TODO (v2): swap the heuristic body for DualInferencer-driven
             content using the combo_analysis prompt template.
          5. PATCH submission via submission_state event with
             analysisFile/analysisSummary/verdict/verdictLabel/deltaPct
             (all whitelisted in _MUTABLE_SUBMISSION_FIELDS).
          6. Emit task_status:completed for the analysis subtab so its
             chip flips off the spinner.

        Returns analysis_task_id on success, None on skip. Caller wraps
        in try/except so a failure here NEVER marks the underlying
        submission failed — analysis is independent value-add.
        """
        if not multi_task_id:
            # Standalone runs (no Hub) don't have a combo-vs-baseline
            # framing — auto-analysis would be meaningless.
            return None

        import json as _json
        import time as _time
        import uuid as _uuid
        from datetime import datetime as _dt
        from pathlib import Path

        from agent_foundation.ui.interactive_base import (
            InteractionFlags,
        )

        ts = _dt.now().strftime("%Y%m%d_%H%M%S")
        analysis_task_id = f"analysis_{submission_id}_{ts}_{_uuid.uuid4().hex[:6]}"

        ws_root = self._session.session_tasks_dir
        analysis_ws = Path(ws_root) / analysis_task_id
        outputs_dir = analysis_ws / "outputs"
        outputs_dir.mkdir(parents=True, exist_ok=True)
        cache_dir = analysis_ws / "_runtime" / "inferencer_cache" / "analysis"
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Step 2 — flip the run row's lifecycle Stepper to "Analyzing"
        # BEFORE any analysis work begins. analysisTaskId rides along so
        # the StepLabel onClick handler (B4) can route there immediately.
        await emit_state(
            {
                "status": "analyzing",
                "analysisTaskId": analysis_task_id,
            }
        )

        # Step 3 — create-on-fly subtab for the analysis. scenario routes
        # the WebUI to the experiment_analysis manifest (C3); workspace
        # gives the WorkspaceStreamTailer a target directory.
        session_id = getattr(self._session.info, "session_id", "")
        if interactive is not None and hasattr(interactive, "_send_response"):
            try:
                import asyncio as _asyncio

                start_msg = {
                    "type": "task_status",
                    "session_id": session_id,
                    "task_id": analysis_task_id,
                    "status": "starting",
                    "request": f"Analyze: {submission_id}",
                    "workspace": str(analysis_ws.absolute()),
                    "multi_task_id": multi_task_id,
                    "scope": "hub_setup",
                    "scenario": "experiment_analysis",
                    "tool_name": "analyze_experiment",
                }
                await _asyncio.to_thread(
                    interactive._send_response,
                    start_msg,
                    InteractionFlags.MessageOnly,
                )
            except Exception as e:
                logger.warning(
                    "auto-analyze: failed to send starting task_status: %s", e
                )

        # Step 4 — load the active baseline for this hub (if any) so we
        # can compute a real delta. The agent server intentionally does
        # NOT mutate hub_<mid>_submissions.json (single-writer invariant
        # at hub_submissions_routes.py:623); we only READ it here.
        baseline_metrics: dict[str, Any] = {}
        baseline_id: str | None = None
        try:
            session_dir = self._session.session_logger.session_dir
            sub_path = session_dir / f"hub_{multi_task_id}_submissions.json"
            if sub_path.is_file():
                hub_data = _json.loads(sub_path.read_text(encoding="utf-8"))
                rows = hub_data.get("submissions") or []
                # Prefer rows flagged isBaseline=True; pick the first (the
                # WebUI's overlay handles tie-breaking by NDCG, but for a
                # single-writer auto-analyze we just need a stable pick).
                for row in rows:
                    if row.get("isBaseline") and row.get("finalMetrics"):
                        baseline_metrics = dict(row.get("finalMetrics") or {})
                        baseline_id = row.get("id") or row.get("submission_id")
                        break
        except Exception as e:
            logger.warning(
                "auto-analyze: baseline lookup failed for hub %s: %s",
                multi_task_id,
                e,
            )

        # Compute primary-metric delta. NDCG@10 is the conventional
        # north-star; fall back to HR@10 / MRR if the row lacks it.
        primary_keys = ["ndcg10", "hr10", "mrr"]
        primary_key = next(
            (k for k in primary_keys if k in final_metrics),
            None,
        )
        delta_pct: float | None = None
        verdict = "neutral"
        verdict_label = "no baseline"
        if primary_key and primary_key in baseline_metrics:
            try:
                cand = float(final_metrics[primary_key])
                base = float(baseline_metrics[primary_key])
                if base != 0:
                    delta_pct = (cand - base) / abs(base) * 100.0
                    if delta_pct >= 1.0:
                        verdict = "win"
                        verdict_label = f"+{delta_pct:.2f}%"
                    elif delta_pct <= -1.0:
                        verdict = "loss"
                        verdict_label = f"{delta_pct:.2f}%"
                    else:
                        verdict = "neutral"
                        verdict_label = f"{delta_pct:+.2f}%"
            except (TypeError, ValueError):
                pass
        elif primary_key:
            verdict_label = f"{primary_key}={final_metrics[primary_key]}"

        # Assemble the analysis markdown. TODO (Plan v7 C1 follow-up):
        # replace this heuristic body with a DualInferencer call against
        # combo_analysis/main/initial.jinja2 so the verdict comes with a
        # narrative + recommended follow-ups. The scaffolding above is
        # already DualInferencer-ready: the workspace, cache_dir, and
        # outputs_dir all match the bridge's conventions.
        flags_section = "\n".join(f"  - `{f}`" for f in (enable_flags or []))
        traj_section = "\n".join(
            f"  - epoch {row.get('epoch')}: "
            + ", ".join(f"{k}={row[k]}" for k in primary_keys if k in row)
            for row in (epoch_trajectory or [])[-10:]
        )
        baseline_section = (
            f"baseline: `{baseline_id}` "
            f"({primary_key}={baseline_metrics.get(primary_key)})"
            if baseline_id
            else "baseline: _not set for this hub_"
        )
        md_body = (
            f"# Auto-analysis: `{submission_id}`\n\n"
            f"**Verdict:** {verdict.upper()} — {verdict_label}\n\n"
            f"**Experiment:** {experiment_name}\n\n"
            f"**Setup:** `{setup_id}`\n\n"
            f"## Final metrics\n\n"
            + "\n".join(
                f"- {k}: {final_metrics[k]}" for k in primary_keys if k in final_metrics
            )
            + "\n\n"
            f"## Vs baseline\n\n{baseline_section}\n\n"
            f"## Enabled flags\n\n{flags_section or '  - _(none)_'}\n\n"
            f"## Trajectory (last 10 epochs)\n\n{traj_section or '  - _(no trajectory)_'}\n\n"
            "---\n"
            "_Generated by auto-analysis. DualInferencer narrative integration "
            "is pending (Plan v7 C1 follow-up)._\n"
        )
        analysis_file = outputs_dir / "analysis.md"
        analysis_file.write_text(md_body, encoding="utf-8")

        # Step 5 — PATCH the submission row with all analysis-summary
        # fields in a single submission_state event so the JobMonitorView
        # row updates atomically (poll_responses applies it under the
        # per-hub lock at hub_submissions_routes.py:593).
        analysis_summary = (
            f"{verdict.upper()} ({verdict_label})"
            if verdict != "neutral"
            else f"NEUTRAL ({verdict_label})"
        )
        await emit_state(
            {
                "analysisFile": str(analysis_file.absolute()),
                "analysisSummary": analysis_summary[:600],
                "verdict": verdict,
                "verdictLabel": verdict_label,
                "deltaPct": delta_pct,
                "finalMetrics": final_metrics,
                "epochTrajectory": epoch_trajectory[-100:],
            }
        )

        # Step 6 — analysis subtab chip flips to "completed" so the
        # spinner clears. Mirrors the run subtab's terminal task_status
        # emit at the bottom of _exec_submission_run.
        if interactive is not None and hasattr(interactive, "_send_response"):
            try:
                import asyncio as _asyncio

                end_msg = {
                    "type": "task_status",
                    "session_id": session_id,
                    "task_id": analysis_task_id,
                    "status": "completed",
                    "multi_task_id": multi_task_id,
                }
                await _asyncio.to_thread(
                    interactive._send_response,
                    end_msg,
                    InteractionFlags.MessageOnly,
                )
            except Exception as e:
                logger.warning(
                    "auto-analyze: failed to send terminal task_status: %s", e
                )

        # Time spent on the heuristic body is sub-second; for the future
        # DualInferencer integration this is the wallclock budget the
        # caller allocates per submission. Logged for ops visibility.
        logger.info(
            "auto-analyze: completed for submission=%s in hub=%s "
            "(verdict=%s, delta=%s, file=%s)",
            submission_id,
            multi_task_id,
            verdict,
            verdict_label,
            analysis_file,
        )
        # Underscore the wallclock so future DualInferencer swap can
        # measure regression against this baseline.
        _ = _time.time()
        return analysis_task_id

    async def _persist_task_status(self, task_id: str, status: str) -> None:
        """F4: persist ``metadata.task_status`` on the matching task_ref row,
        so a WebSocket reconnect after disconnect-during-emit shows the
        correct chip status (instead of defaulting to 'queued' forever).

        Best-effort: failures here MUST NOT break the WS task_status emit
        that follows. Called immediately before each task_status WS emit
        site in this class so on-disk state mirrors what live clients see.
        """
        try:
            if self._session.conversation.update_task_ref_status(task_id, status):
                await self._persist()
        except Exception as e:
            logger.warning(
                "F4 _persist_task_status(task_id=%s, status=%s) failed: %s",
                task_id,
                status,
                e,
            )

    @staticmethod
    def _make_task_status_payload(
        entry: dict[str, Any] | None,
        session_id: str,
        task_id: str,
        status: str,
        **extra: Any,
    ) -> dict[str, Any]:
        """Build a `task_status` notification payload with consistent fields.

        Routes per-entry metadata (multi_task_id, scope) into the event so
        the WebUI reducer can route correctly. Centralizing this in one
        helper means all task_status emit sites stay in sync — adding a
        new field (e.g. `scope`) doesn't require auditing every emit
        site to confirm it propagates.

        ``entry`` may be None for callers that emit task_status before the
        queue entry exists (e.g. multi-task hub creation at line ~370);
        in that case only the explicitly-passed fields are included.
        """
        payload: dict[str, Any] = {
            "type": "task_status",
            "session_id": session_id,
            "task_id": task_id,
            "status": status,
            **extra,
        }
        if entry is not None:
            mid = entry.get("multi_task_id")
            if mid:
                payload["multi_task_id"] = mid
            entry_scope = entry.get("scope")
            if entry_scope:
                payload["scope"] = entry_scope
        return payload

    async def enqueue_and_maybe_execute(
        self,
        tool_name: str,
        request: str,
        title: str,
        args: dict[str, Any],
        hypothesis_id: str = "",
        phase: str = "",
        multi_task_id: str = "",
        batch_id: str = "",
        batch_label: str = "",
        on_complete_handler: str = "",
        scope: str = "",
    ) -> str:
        """Add a task to the queue and start it if a slot is available.

        batch_id / batch_label: first-class metadata for hub-managed tasks
        (set by create_experiment_hub / add_to_experiment_hub). Resume
        rehydration reads these directly instead of parsing the title string.

        on_complete_handler: optional KEY into self._completion_handlers
        (string only — must be JSON-serializable so it survives persistence
        and agent-server restart). The handler is invoked from
        _try_start_next_task once the task transitions to a terminal state.

        scope: optional discriminator for the frontend reducer. The hub's
        runQueue routing in useSessionManager is gated by scope — entries
        with scope="hub_setup" fall through to the top-level subtab branch
        instead of being routed into the hub's runQueue display, so setup
        tasks become their own session-level subtabs (alongside Codebase
        Investigation / Research & Proposal) rather than appearing inside
        the Experiment Hub's Progress tab. Backend completion routing is
        unaffected — multi_task_id remains on the entry for the
        _setup_completion_hook → _apply_setup_completed path.

        Returns the task_id for tracking.
        """
        import uuid

        wc = self._session.workflow_context
        task_id = f"task-{uuid.uuid4().hex[:8]}"
        entry = wc.enqueue_task(
            task_id=task_id,
            tool_name=tool_name,
            request=request,
            title=title,
            args=args,
            hypothesis_id=hypothesis_id,
            phase=phase,
        )
        if multi_task_id:
            entry["multi_task_id"] = multi_task_id
        if batch_id:
            entry["batch_id"] = batch_id
        if batch_label:
            entry["batch_label"] = batch_label
        if scope:
            entry["scope"] = scope
        if on_complete_handler:
            # Normalize legacy template-version names (see
            # _normalize_template_version) so callers passing the
            # pre-rename string still validate against the renamed dict key.
            on_complete_handler = _normalize_template_version(on_complete_handler)
            # Reject unknown keys early — a typo here would silently lose
            # the hook on completion (the lookup at fire-time would no-op).
            if on_complete_handler not in self._completion_handlers:
                raise ValueError(
                    f"Unknown on_complete_handler: {on_complete_handler!r}. "
                    f"Known: {sorted(self._completion_handlers)}"
                )
            entry["on_complete_handler"] = on_complete_handler

        # Notify frontend: task queued (creates subtab in "waiting" state)
        interactive = getattr(self._session, "interactive", None)
        if interactive and hasattr(interactive, "_send_response"):
            try:
                import asyncio as _asyncio

                from agent_foundation.ui.interactive_base import (
                    InteractionFlags,
                )

                notification = self._make_task_status_payload(
                    entry,
                    session_id=getattr(self._session.info, "session_id", ""),
                    task_id=task_id,
                    status="queued",
                    request=title[:80],
                    hypothesis_id=hypothesis_id,
                    queue_position=len(
                        [e for e in wc.task_queue if e["status"] == "queued"]
                    ),
                    queue_total=len(wc.task_queue),
                )
                # F4: persist task_ref.metadata.task_status BEFORE WS emit
                # so reconnect clients restore correct chip status from disk.
                await self._persist_task_status(task_id, "queued")
                await _asyncio.to_thread(
                    interactive._send_response,
                    notification,
                    InteractionFlags.MessageOnly,
                )
            except Exception:
                pass

        # Try to start the next task if a slot is available
        import asyncio

        asyncio.create_task(self._try_start_next_task())

        return task_id

    async def _try_start_next_task(self) -> None:
        """Start the next queued task if a slot is available. Non-recursive."""
        wc = self._session.workflow_context
        next_entry = wc.get_next_runnable()
        if next_entry is None:
            return

        task_id = next_entry["task_id"]
        tool_name = next_entry["tool_name"]
        args = next_entry.get("args", {})

        logger.info("Task queue: starting %s (tool=%s)", task_id, tool_name)
        # Pass workspace=None (the new sentinel) so any existing workspace value
        # is preserved (e.g., set by Layer 2 reconciliation). Workspace gets
        # filled inside _exec_task once the bridge is constructed.
        wc.mark_running(task_id, workspace=None)
        await self._persist()

        # Register the queue task in the session's per-task handle map so
        # TASK_CANCEL_BY_ID can reach it. _try_start_next_task itself runs
        # in a create_task() — we capture that handle via the current task.
        # Removed in finally below so a stale handle doesn't outlive the run.
        try:
            current_handle = asyncio.current_task()
        except RuntimeError:
            current_handle = None
        if current_handle is not None and hasattr(
            self._session, "running_task_handles"
        ):
            self._session.running_task_handles[task_id] = current_handle

        # Outer try/finally guarantees the handle is dropped from the
        # registry AND the queue is chained even on CancelledError —
        # without this, cancelling one submission_run would stall the
        # entire queue (next queued task never starts).
        try:
            try:
                if tool_name in ("task", "understand_codebase"):
                    result = await self._exec_task(args, queue_task_id=task_id)
                elif tool_name == "submission_run":
                    # Submission runs go through their own sibling — separate
                    # from _exec_task (no SOP/PTI plumbing applies). Handles
                    # its own queue-entry mark_completed/mark_error via the
                    # standard outer try/except below.
                    result = await self._exec_submission_run(
                        args, queue_task_id=task_id
                    )
                else:
                    result = ToolExecutionResult(
                        result=f"Unknown queued tool: {tool_name}"
                    )

                # Skip duplicate mark_completed: _exec_task already calls
                # mark_completed at line 737 for queue-managed tasks. Only
                # fire here if the entry is still non-terminal (e.g., for
                # a code path that didn't reach that line).
                entry_now = wc.get_entry(task_id)
                if entry_now is not None and entry_now.get("status") not in (
                    "completed",
                    "error",
                ):
                    wc.mark_completed(
                        task_id,
                        summary=str(result.result)[:200] if result else "",
                    )
                logger.info("Task queue: completed %s", task_id)
            except asyncio.CancelledError:
                # User cancellation via TASK_CANCEL_BY_ID propagates here.
                # CancelledError is a BaseException (not Exception) in
                # py3.8+, so the broad `except Exception` below would NOT
                # catch it — handle it explicitly. We must:
                #   (a) Mark the queue entry terminal so _post_cancel_cleanup
                #       sees it as already-handled (eliminates the dual-
                #       writer race the prior plan called out).
                #   (b) Persist under asyncio.shield so the cancel state
                #       survives a restart even though the outer task is
                #       being torn down.
                #   (c) Fire the completion handler — also shielded — so
                #       a setup PTI cancel surfaces 'error' to the WebUI
                #       immediately rather than leaving the per-hub setup
                #       file stuck at 'in_progress' until the next WS
                #       reconnect's recovery pass.
                #   (d) Re-raise so the awaiting create_task sees the cancel.
                # The outer finally still runs and chains the next task —
                # critical: a cancel must not stall the queue.
                entry_now = wc.get_entry(task_id)
                if entry_now is not None and entry_now.get("status") not in (
                    "completed",
                    "error",
                ):
                    wc.mark_error(task_id, error="cancelled by user")
                try:
                    await asyncio.shield(self._persist())
                except (asyncio.CancelledError, Exception):
                    pass
                # Fire the completion handler on cancel — see (c) above.
                # The handler reads queue status and naturally emits
                # 'error' for cancelled-as-error entries (see
                # _setup_completion_hook's first branch).
                cancel_handler_key = (
                    (next_entry.get("on_complete_handler") or "")
                    if isinstance(next_entry, dict)
                    else ""
                )
                if cancel_handler_key:
                    cancel_handler_key = _normalize_template_version(cancel_handler_key)
                    cancel_handler = self._completion_handlers.get(cancel_handler_key)
                    if cancel_handler is not None:
                        try:
                            fresh = wc.get_entry(task_id) or next_entry
                            await asyncio.shield(cancel_handler(fresh))
                        except (asyncio.CancelledError, Exception) as hook_err:
                            logger.warning(
                                "cancel-time completion handler %r failed for %s: %s",
                                cancel_handler_key,
                                task_id,
                                hook_err,
                            )
                raise
            except Exception as e:
                wc.mark_error(task_id, error=str(e)[:200])
                logger.error("Task queue: error on %s: %s", task_id, e)
            await self._persist()

            # Fire the post-completion handler (if registered on the entry).
            # Restart-safe design: the entry stores a string KEY (not a
            # callable), so reload-from-disk works. The handler runs
            # OUTSIDE _exec_task so we don't add tool-specific layering
            # inside the generic dispatch method. Errors here MUST NOT
            # crash the queue runner — they're logged and the next
            # chained _try_start_next_task continues. Skipped on
            # CancelledError because the raise above unwinds past this
            # block straight into the outer finally.
            handler_key = (
                (next_entry.get("on_complete_handler") or "")
                if isinstance(next_entry, dict)
                else ""
            )
            if handler_key:
                handler_key = _normalize_template_version(handler_key)
                handler = self._completion_handlers.get(handler_key)
                if handler is None:
                    logger.warning(
                        "on_complete_handler %r registered on task %s is "
                        "unknown; skipping (handler may have been removed "
                        "across restart)",
                        handler_key,
                        task_id,
                    )
                else:
                    try:
                        # Re-read the entry — _exec_task may have updated
                        # workspace / status / mast_job after we took the
                        # snapshot above.
                        fresh_entry = wc.get_entry(task_id) or next_entry
                        await handler(fresh_entry)
                        await self._persist()
                    except Exception as hook_err:
                        logger.error(
                            "Completion handler %r failed for task %s: %s",
                            handler_key,
                            task_id,
                            hook_err,
                            exc_info=True,
                        )

            # Check if all tasks for this phase are done
            phase = next_entry.get("phase", "")
            if phase and wc.is_phase_complete(phase):
                logger.info("Task queue: phase %s fully complete", phase)
                # NOTE: previously auto-cleared wc.active_multi_task_id here.
                # Removed (Layer 1, Issue #18): "all current runs done" does
                # NOT mean "hub closed" — the multi-round Selection View flow
                # REQUIRES adding more runs to a complete hub. Hub closure now
                # requires an explicit wc.close_multi_task(id) call, which
                # create_experiment_hub implicitly handles when starting a new
                # hub (the new active_multi_task_id displaces the previous one).
                sop_outputs = {}
                # Collect all completed workspaces
                phase_tasks = [
                    e
                    for e in wc.task_queue
                    if e["phase"] == phase and e["status"] == "completed"
                ]
                if phase_tasks:
                    sop_outputs["experiment_result"] = [
                        e.get("workspace", "") for e in phase_tasks
                    ]
                wc.complete_phase(
                    phase,
                    summary=f"All {len(phase_tasks)} tasks complete",
                    **sop_outputs,
                )
                await self._persist()
        finally:
            # Drop the queue-task handle from the registry — even on cancel.
            if hasattr(self._session, "running_task_handles"):
                self._session.running_task_handles.pop(task_id, None)
            # Chain the next queued task — even on cancel. Critical:
            # cancelling one submission_run must not stall subsequent
            # queued tasks. asyncio.create_task is safe to invoke from
            # cleanup (the new task is independent of this one).
            try:
                asyncio.create_task(self._try_start_next_task())
            except RuntimeError:
                # No running loop (we're in a cleanup path during
                # shutdown). Nothing to chain — log and move on.
                logger.debug(
                    "Task queue: no event loop available to chain after %s",
                    task_id,
                )

    async def _exec_task(
        self, args: dict[str, Any], queue_task_id: str = ""
    ) -> ToolExecutionResult:
        """Execute a /task command via DualInferencerBridge.

        Args:
            args: Tool arguments (request, flags, etc.)
            queue_task_id: If set, this task was started from the task queue.
                Phase completion is managed by the queue (not called here).
        """
        from rankevolve.src.server.dual_inferencer_bridge import DualInferencerBridge
        from rankevolve.src.server.task_types import TaskMode

        request = args.get("request", "")
        if not request:
            return ToolExecutionResult(
                result="Error: 'request' argument is required for the task tool."
            )

        # Guard: reject direct /task invocations when hypotheses are already queued.
        # The task queue handles execution automatically — the LLM should not
        # invoke /task manually for queued hypotheses.
        if not queue_task_id:
            wc = self._session.workflow_context
            active_queue = [
                e for e in wc.task_queue if e.get("status") in ("queued", "running")
            ]
            if active_queue:
                queued_ids = [
                    e.get("hypothesis_id", e.get("task_id", "")) for e in active_queue
                ]
                return ToolExecutionResult(
                    result=(
                        f"Task queue is active with {len(active_queue)} tasks "
                        f"({', '.join(queued_ids)}). The system executes queued "
                        f"tasks automatically. Do NOT invoke /task manually."
                    )
                )

        root = Path(
            self._session.info.session_root_path
            if hasattr(self._session.info, "session_root_path")
            and self._session.info.session_root_path
            else "."
        )

        # Map flag arguments to bridge constructor kwargs
        bridge_kwargs: dict[str, Any] = {}
        if args.get("model"):
            bridge_kwargs["claude_model"] = args["model"]
        if args.get("claude_only"):
            bridge_kwargs["use_claude_only"] = True
        if args.get("analysis"):
            bridge_kwargs["enable_analysis"] = True
        if args.get("multi_iter") or args.get("multi-iter"):
            bridge_kwargs["enable_multiple_iterations"] = True
        if args.get("no_planning") or args.get("no-planning"):
            bridge_kwargs["enable_planning"] = False
        if args.get("no_implementation") or args.get("no-implementation"):
            bridge_kwargs["enable_implementation"] = False
        if args.get("resume") or args.get("--resume"):
            bridge_kwargs["resume_workspace"] = args.get("resume") or args.get(
                "--resume"
            )
            # Default to in-place on resume (no copy) unless explicitly overridden.
            # Copying is wasteful when resuming a completed task just to conclude it.
            if "copy_workspace" not in bridge_kwargs:
                bridge_kwargs["copy_workspace"] = False
        if args.get("base_inferencer") or args.get("base-inferencer"):
            bridge_kwargs["base_inferencer_type"] = args.get(
                "base_inferencer"
            ) or args.get("base-inferencer")
        if args.get("review_inferencer") or args.get("review-inferencer"):
            bridge_kwargs["review_inferencer_type"] = args.get(
                "review_inferencer"
            ) or args.get("review-inferencer")
        if args.get("template_version"):
            bridge_kwargs["template_version"] = args["template_version"]

        # Determine SOP phase ID from tool_phase_map (extracted from SOP).
        # The map may have been populated by the conversational inferencer
        # (via prior_context) even if session.session_context failed to load
        # the SOP from importlib.resources (buck2 link-tree packaging issue).
        tool_map = self._session.workflow_context.tool_phase_map
        if not tool_map:
            # Try to get tool_phase_map from the inferencer's prior_context
            ci = getattr(self._session, "conversation_inferencer", None)
            if ci and hasattr(ci, "prior_context"):
                tool_map = ci.prior_context.get("tool_phase_map", {})
                if tool_map:
                    self._session.workflow_context.tool_phase_map = tool_map
        template_version = _normalize_template_version(args.get("template_version", ""))
        sop_phase = tool_map.get(template_version, tool_map.get("task", "3"))

        # Setup tasks (e.g., the experiment_runner_creation PTI run that
        # produces outputs/submit_v1.py + outputs/launch.json) are NOT part
        # of the main SOP workflow — they generate auxiliary artifacts. If we
        # ran start_phase / complete_phase / fail_phase for them, the SOP
        # tracker would mistakenly mark a real workflow phase as running /
        # completed mid-setup, polluting the user-visible status. The queue
        # entry's `phase=""` already short-circuits the queue-side
        # is_phase_complete check (see _try_start_next_task). This flag does
        # the same on the bridge side.
        is_non_sop_task = template_version == "experiment_runner_creation"

        # P4: refuse to start sop_phase when any dependency carries the
        # `requires confirmation` SOP directive AND is not yet in
        # completed_phases. Hard guarantee that the LLM cannot bypass a
        # gate phase like Phase 1b by emitting the next-phase tool
        # directly. The LLM's response handler interprets `[BLOCKED]` as
        # a structured precondition failure and re-emits the correct
        # confirmation widget.
        if not is_non_sop_task:
            gate_check = self._check_confirmation_gates_satisfied(sop_phase)
            if gate_check is not None:
                return gate_check

        # P3: auto-complete gate dependencies that genuinely don't need user
        # interaction (no tools, no outputs, no `requires confirmation`).
        # Replaces the previous inline duplicate that auto-completed
        # `requires_confirmation` gates with a false "Confirmed by user"
        # summary — that backdoor is now closed.
        wc = self._session.workflow_context
        if not is_non_sop_task:
            self._try_auto_complete_gate_dependencies(sop_phase)

        # Update workflow_context BEFORE bridge construction (snapshot timing).
        # Skip for setup tasks — see is_non_sop_task above.
        if not is_non_sop_task:
            self._session.workflow_context.start_phase(sop_phase, request[:80])

        bridge = DualInferencerBridge(
            root_folder=root,
            knowledge_bridge=getattr(self._session, "knowledge_bridge", None),
            session_context=self._session.session_context,
            # Round 9: per-session task workspaces.
            output_dir=self._session.session_tasks_dir,
            **bridge_kwargs,
        )
        workspace_abs = str(Path(bridge.workspace).absolute())
        self._session.workflow_context.active_workspace = workspace_abs

        # Layer 1: fill the queue entry's workspace with the absolute path AND
        # write a .task_meta.json sidecar BEFORE bridge.run() executes. The
        # sidecar lets Layer 2 reconciliation map workspace dirs back to queue
        # entries by exact task_id (instead of fragile request-text matching).
        if queue_task_id:
            self._session.workflow_context.update_entry(
                queue_task_id, workspace=workspace_abs
            )
            try:
                import json as _meta_json

                queue_entry = self._session.workflow_context.get_entry(queue_task_id)
                # Round 9: persist session_id + session_dir as a direct FK +
                # tool_name for parity with submission_run sidecars.
                _sess_logger = getattr(self._session, "session_logger", None)
                _session_dir_name = (
                    _sess_logger.session_dir.name if _sess_logger is not None else ""
                )
                meta = {
                    "task_id": queue_task_id,
                    "multi_task_id": (queue_entry or {}).get("multi_task_id", ""),
                    "tool_name": "task",
                    "hypothesis_id": (queue_entry or {}).get("hypothesis_id", ""),
                    "batch_id": (queue_entry or {}).get("batch_id", ""),
                    "batch_label": (queue_entry or {}).get("batch_label", ""),
                    "session_id": self._session.info.session_id,
                    "session_dir": _session_dir_name,
                }
                meta_path = Path(bridge.workspace) / ".task_meta.json"
                meta_path.write_text(_meta_json.dumps(meta), encoding="utf-8")
            except Exception as _meta_err:
                logger.warning(
                    "Failed to write .task_meta.json sidecar for %s: %s",
                    queue_task_id,
                    _meta_err,
                )
            await self._persist()

        # Notify frontend to create a task subtab
        import uuid

        task_id = queue_task_id or f"task-{uuid.uuid4().hex[:8]}"
        # Pre-look up the queue entry so we can both decide whether to write
        # a chip (skip per-batch sub-tasks) and pass it to the WS payload.
        queue_entry = None
        if queue_task_id:
            wc = self._session.workflow_context
            queue_entry = next(
                (e for e in wc.task_queue if e.get("task_id") == queue_task_id),
                None,
            )

        # Persist a chronological task_ref BEFORE the WS emit so a crash in
        # the persist→emit window doesn't cost positional fidelity. Skip
        # per-batch sub-tasks (multi_task_id present + tool_name=="task") —
        # those render inside the hub panel, not as top-level chips. Use the
        # template_version as the chip's tool_name so frontend correlation
        # picks up `understand_codebase` (delegated through _exec_task)
        # distinctly from a plain `/task` invocation.
        is_sub_task = bool(queue_entry and queue_entry.get("multi_task_id"))
        chip_tool_name = template_version or "task"
        if self._session.conversation and not is_sub_task and not is_non_sop_task:
            chip_label = (request or "Task")[:60]
            # Best-effort: chip-write failures MUST NOT abort the task
            # launch — chip placement is auxiliary UI metadata. Failure
            # here only affects resume positioning.
            try:
                self._session.conversation.add_task_ref(
                    task_id=task_id,
                    label=chip_label,
                    tool_name=chip_tool_name,
                )
                await self._persist()
            except Exception as chip_err:
                logger.warning(
                    "add_task_ref failed for task_id=%s tool=%s — task "
                    "will still launch, chip placement may be missing "
                    "on resume: %s",
                    task_id,
                    chip_tool_name,
                    chip_err,
                )

        # When queue-managed, send 'starting' to transition the subtab from 'queued' state.
        # For non-queued tasks, send 'starting' to create the subtab.
        interactive = getattr(self._session, "interactive", None)
        if interactive and hasattr(interactive, "asend_response"):
            from agent_foundation.ui.interactive_base import (
                InteractionFlags,
            )

            try:
                import asyncio as _asyncio
                import logging as _logging

                _log = _logging.getLogger(__name__)
                _log.info(
                    "task_status: sending 'starting' notification for task_id=%s",
                    task_id,
                )
                # Use _send_response directly, NOT asend_response/send_response.
                # send_response calls iter_() on the dict which iterates its keys,
                # sending each key as a separate string message instead of the whole dict.
                starting_notification = self._make_task_status_payload(
                    queue_entry,
                    session_id=getattr(self._session.info, "session_id", ""),
                    task_id=task_id,
                    status="starting",
                    request=request[:80],
                    workspace=str(bridge.workspace),
                )
                # F4: persist task_ref status BEFORE WS emit.
                await self._persist_task_status(task_id, "starting")
                await _asyncio.to_thread(
                    interactive._send_response,
                    starting_notification,
                    InteractionFlags.MessageOnly,
                )
                _log.info("task_status: 'starting' notification sent successfully")
            except Exception as _e:
                import logging as _logging

                _logging.getLogger(__name__).error(
                    "task_status: failed to send notification: %s", _e, exc_info=True
                )

        # Determine task mode
        task_mode = TaskMode.FULL_WORKFLOW
        if args.get("plan"):
            task_mode = TaskMode.PLAN_ONLY
        elif args.get("execute"):
            task_mode = TaskMode.EXECUTE_ONLY
        elif args.get("confirm"):
            task_mode = TaskMode.PLAN_THEN_CONFIRM

        try:
            result = await bridge.run(request, task_mode=task_mode)
            # Look up the SOP-expected output variable for this phase.
            # The output name comes from the SOP phase heading (e.g.,
            # "Phase 1 -- ...: `codebase_understanding`"). We need to set
            # it in phase_outputs so the SOP tracker doesn't show "Missing outputs".
            sop_outputs = {}
            try:
                from rankevolve.src.utils.string_utils.formatting.template_manager.sop_manager import (
                    SOPManager,
                )

                ci = getattr(self._session, "conversation_inferencer", None)
                sop_obj = (
                    ci.prior_context.get("_sop")
                    if ci and hasattr(ci, "prior_context")
                    else None
                )
                if sop_obj:
                    phase_node = sop_obj.get_phase(sop_phase)
                    if phase_node and hasattr(phase_node, "outputs"):
                        for out_name in phase_node.outputs:
                            sop_outputs[out_name] = str(bridge.workspace)
            except Exception:
                pass
            # Resolve tool-registered viewable artifact path. Skip for setup
            # tasks — the WebUI's script editor drawer handles their outputs
            # directly (via the completion hook + canonical setup_scripts
            # store), and there is no experiment_runner_creation/tool.json
            # to load (would log a spurious error every run).
            if not is_non_sop_task:
                try:
                    from rankevolve.src.resources.tools.registry import load_tool

                    effective_tool = args.get("template_version") or "task"
                    tool_def = load_tool(effective_tool)
                    resolved = self._resolve_field_templates(
                        tool_def, args, Path(bridge.workspace)
                    )
                    if "viewable_output_path" in resolved:
                        sop_outputs["viewable_artifact_path"] = resolved[
                            "viewable_output_path"
                        ]
                        # Fix-RT: propagate _exists so downstream consumers
                        # (Fix-AA auto-advance, ConfirmationHandler) can give
                        # honest guidance instead of guessing from path
                        # presence alone.
                        sop_outputs["viewable_artifact_path_exists"] = bool(
                            resolved.get("viewable_output_path_exists", False)
                        )
                        if tool_def.viewable_output_label:
                            sop_outputs["viewable_artifact_label"] = (
                                tool_def.viewable_output_label
                            )
                        logger.info(
                            "viewable_artifact_path resolved: %s (exists=%s)",
                            resolved["viewable_output_path"],
                            sop_outputs["viewable_artifact_path_exists"],
                        )
                    else:
                        logger.info(
                            "viewable_output_path NOT resolved. tool=%s template=%s rules=%s",
                            effective_tool,
                            getattr(tool_def, "viewable_output_path", "(none)"),
                            getattr(tool_def, "arg_template_rules", "(none)"),
                        )
                except Exception as e:
                    logger.error(
                        "_resolve_field_templates failed: %s", e, exc_info=True
                    )

            # Complete phase — skip if queue-managed (queue handles completion
            # via is_phase_complete() after ALL tasks for the phase are done)
            # OR if this is a non-SOP setup task (see is_non_sop_task above).
            if not queue_task_id and not is_non_sop_task:
                self._session.workflow_context.complete_phase(
                    sop_phase,
                    summary=request[:80],
                    workspace_path=str(bridge.workspace),
                    **sop_outputs,
                )
                # Flush phase_status="completed" to disk so a reconnecting
                # WebUI (or F2 client-side widget reconciliation) sees the
                # actual phase state instead of a stale "running".
                await self._persist()
            elif queue_task_id:
                # Queue-managed: update workspace on the queue entry
                wc.mark_completed(queue_task_id, summary=request[:80])
                # Avoid stomping wc.active_workspace for setup tasks — the
                # active hub's experiment workspace is unrelated to the
                # transient PTI workspace that produced the setup script.
                if not is_non_sop_task:
                    wc.active_workspace = str(bridge.workspace)
                # Persist immediately so the completion survives a restart
                # before the outer _try_start_next_task gets a chance to persist.
                await self._persist()
            # Notify frontend task completed
            if interactive and hasattr(interactive, "_send_response"):
                try:
                    import asyncio as _asyncio

                    # Include multi_task_id + scope so the frontend can route to
                    # the parent multi-task's RUN_QUEUE_STATUS reducer (or
                    # fall through to top-level subtab branch when scope is
                    # set, e.g. scope="hub_setup" for setup tasks).
                    queue_entry = None
                    if queue_task_id:
                        queue_entry = next(
                            (
                                e
                                for e in wc.task_queue
                                if e.get("task_id") == queue_task_id
                            ),
                            None,
                        )
                    completed_notification = self._make_task_status_payload(
                        queue_entry,
                        session_id=getattr(self._session.info, "session_id", ""),
                        task_id=task_id,
                        status="completed",
                    )
                    # F4: persist task_ref status BEFORE WS emit so reconnect
                    # clients see "Complete" instead of stuck "Queued"/"Running".
                    await self._persist_task_status(task_id, "completed")
                    await _asyncio.to_thread(
                        interactive._send_response,
                        completed_notification,
                        InteractionFlags.MessageOnly,
                    )
                except Exception:
                    pass
            result_text = f"Task completed. Workspace: {bridge.workspace}. Result: {str(result)[:2000]}"
            # Auto-advance: inject synthetic message to advance workflow
            # For hub-managed tasks (multi_task_id set), skip auto-advance —
            # the hub's queue self-advances via _try_start_next_task().
            skip_auto_advance = False
            if queue_task_id:
                _qa_entry = next(
                    (e for e in wc.task_queue if e.get("task_id") == queue_task_id),
                    None,
                )
                if _qa_entry and _qa_entry.get("multi_task_id"):
                    skip_auto_advance = True
                    logger.info(
                        "Auto-advance: skipping for hub-managed task (multi_task_id=%s, task_id=%s)",
                        _qa_entry["multi_task_id"],
                        queue_task_id,
                    )

            # For queue-managed tasks, include queue progress
            if (
                self._queue_service
                and not skip_auto_advance
                and not getattr(self._session, "_is_auto_advance_turn", False)
            ):
                import asyncio as _asyncio

                _session_id = getattr(self._session.info, "session_id", "")
                if queue_task_id:
                    # Queue-managed: include remaining count
                    remaining = len(
                        [e for e in wc.task_queue if e["status"] == "queued"]
                    )
                    queue_summary = wc.get_queue_summary(sop_phase)
                    if remaining > 0:
                        auto_msg = (
                            f"[System notification: Task {queue_task_id} completed. "
                            f"Queue progress: {queue_summary}. "
                            f"{remaining} more hypothesis tasks queued — executing next automatically.]"
                        )
                    else:
                        auto_msg = (
                            f"[System notification: All Phase {sop_phase} tasks completed. "
                            f"Queue progress: {queue_summary}. "
                            f"Present a summary of the results to the user and proceed to the next phase.]"
                        )
                else:
                    # Fix-AA: interpolate the resolved viewable_artifact_path
                    # (and view_label) directly into the synthetic message.
                    # Eliminates LLM guessing for canonical paths — the LLM
                    # can copy the exact string into its `confirmation` tool
                    # invocation. When the artifact wasn't produced (per
                    # Fix-RT's _exists flag), tell the LLM explicitly so it
                    # emits `confirmation` WITHOUT `view` (Fix-V then keeps
                    # the widget free of fallback overlays).
                    _va_path = sop_outputs.get("viewable_artifact_path")
                    _va_exists = sop_outputs.get("viewable_artifact_path_exists", False)
                    _va_label = sop_outputs.get("viewable_artifact_label", "")
                    if _va_path and _va_exists:
                        _label_part = (
                            f" and view_label='{_va_label}'" if _va_label else ""
                        )
                        view_instruction = (
                            f"A viewable artifact was produced at: {_va_path}. "
                            f"When emitting the `confirmation` tool, set "
                            f"view='{_va_path}'{_label_part} so the user can "
                            f"open it from the widget."
                        )
                    elif _va_path and not _va_exists:
                        view_instruction = (
                            f"The tool's expected artifact path "
                            f"({_va_path}) was not produced. Emit the "
                            f"`confirmation` tool WITHOUT a `view` argument."
                        )
                    else:
                        view_instruction = (
                            "No viewable artifact was registered for this "
                            "tool — emit the `confirmation` tool WITHOUT a "
                            "`view` argument."
                        )
                    auto_msg = (
                        f"[System notification: Phase {sop_phase} task completed successfully. "
                        f"IMPORTANT: The workflow status has been updated — Phase {sop_phase} "
                        f"is now COMPLETED. Ignore any previous messages in the conversation "
                        f"that say '(running)' — those are from before the task finished. "
                        f"Workspace: {bridge.workspace}. "
                        f"Present a summary of the task results to the user. "
                        f"The user must review and confirm before proceeding to the next workflow phase. "
                        f"{view_instruction}]"
                    )
                logger.info(
                    "Auto-advance: queueing synthetic message for session=%s phase=%s",
                    _session_id,
                    sop_phase,
                )
                await _asyncio.to_thread(
                    self._queue_service.put,
                    f"user_input_{_session_id}",
                    {
                        "type": "chat_message",
                        "content": auto_msg,
                        "session_id": _session_id,
                        "auto_advance": True,
                    },
                )
                logger.info(
                    "Auto-advance: synthetic message queued successfully for session=%s",
                    _session_id,
                )
            elif not skip_auto_advance:
                logger.warning(
                    "Auto-advance SKIPPED for session=%s phase=%s (task): "
                    "queue_service=%s, is_auto_advance_turn=%s. "
                    "Next phase's auto-advance will not fire.",
                    getattr(self._session.info, "session_id", ""),
                    sop_phase,
                    bool(self._queue_service),
                    getattr(self._session, "_is_auto_advance_turn", False),
                )
            return ToolExecutionResult(
                result=result_text,
                context_updates=self._get_workflow_context_updates(),
            )
        except Exception as e:
            # Skip fail_phase for non-SOP setup tasks — they're not part of
            # the workflow and shouldn't appear in completed_phases / the
            # status text. The queue still records the failure via mark_error
            # in _try_start_next_task's outer except.
            if not is_non_sop_task:
                self._session.workflow_context.fail_phase(
                    sop_phase,
                    error=str(e)[:80],
                )
            # Notify frontend task failed
            if interactive and hasattr(interactive, "_send_response"):
                try:
                    import asyncio as _asyncio

                    # Include multi_task_id + scope so the frontend can route
                    # to the parent multi-task's RUN_QUEUE_STATUS reducer (or
                    # fall through to top-level subtab branch when scope is
                    # set, e.g. scope="hub_setup" for setup tasks).
                    queue_entry = None
                    if queue_task_id:
                        wc = self._session.workflow_context
                        queue_entry = next(
                            (
                                e2
                                for e2 in wc.task_queue
                                if e2.get("task_id") == queue_task_id
                            ),
                            None,
                        )
                    error_notification = self._make_task_status_payload(
                        queue_entry,
                        session_id=getattr(self._session.info, "session_id", ""),
                        task_id=task_id,
                        status="error",
                        message=str(e)[:200],
                    )
                    # F4: persist task_ref status BEFORE WS emit.
                    await self._persist_task_status(task_id, "error")
                    await _asyncio.to_thread(
                        interactive._send_response,
                        error_notification,
                        InteractionFlags.MessageOnly,
                    )
                except Exception:
                    pass
            raise

    async def _exec_research_propose(self, args: dict[str, Any]) -> ToolExecutionResult:
        """Execute /research-propose via ResearchProposeBridge."""
        from rankevolve.src.server.research_propose_bridge import (  # @manual -- lazy import; dep declared in rankevolve_service_lib
            ResearchProposeBridge,
        )

        request = args.get("request", "")
        if not request:
            return ToolExecutionResult(result="Error: 'request' argument is required.")

        root = Path(
            self._session.info.session_root_path
            if hasattr(self._session.info, "session_root_path")
            and self._session.info.session_root_path
            else "."
        )

        rp_phase = self._session.workflow_context.tool_phase_map.get(
            "research_propose", "2"
        )

        # P4: gate-check before research_propose starts (mirrors _exec_task).
        # Refuses the call with [BLOCKED] if any dep has `requires confirmation`
        # and is not in completed_phases.
        gate_check = self._check_confirmation_gates_satisfied(rp_phase)
        if gate_check is not None:
            return gate_check

        # P3: honest auto-complete-gate (skips `requires_confirmation` deps;
        # uses honest summary string instead of the false "Confirmed by user").
        self._try_auto_complete_gate_dependencies(rp_phase)

        self._session.workflow_context.start_phase(rp_phase, request[:80])

        # Override root_folder if --workflow-target-path provided
        # Auto-populate from session's workflow_target_path if not explicitly given
        workflow_target = args.get("workflow_target_path") or args.get(
            "--workflow-target-path"
        )
        if not workflow_target:
            wt = getattr(self._session.info, "workflow_target_path", None)
            if wt:
                workflow_target = wt
        if workflow_target:
            target_path = Path(workflow_target)
            if target_path.is_file():
                root = target_path.parent
            elif target_path.is_dir():
                root = target_path

        # Auto-populate --docs-path from Phase 1 output if not explicitly given
        docs_path = args.get("docs_path") or args.get("--docs-path")
        if not docs_path:
            # Check phase_outputs for codebase_understanding (Phase 1's output)
            phase_outputs = self._session.workflow_context.phase_outputs
            codebase_ws = phase_outputs.get("codebase_understanding")
            if codebase_ws:
                # The workspace path contains the generated documentation
                docs_dir = Path(codebase_ws) / "outputs"
                if docs_dir.is_dir():
                    docs_path = str(docs_dir)
                elif Path(codebase_ws).is_dir():
                    docs_path = str(codebase_ws)

        # Merge paths into session_context
        session_ctx = dict(self._session.session_context or {})
        if workflow_target:
            session_ctx["workflow_target_path"] = workflow_target
        if docs_path:
            session_ctx["docs_path"] = docs_path

        # Auto-discover existing completed research workspace if --resume not
        # explicitly provided.  Scans THIS session's tasks directory for the
        # newest research_* directory that contains results/research_output.txt
        # (the completion marker).  Per-session scoping (was global tasks/
        # under the flat layout): cross-session research resumption was an
        # unintended leak — research outputs are session-specific context.
        resume_ws = args.get("resume") or args.get("--resume")
        # Round 9: per-session scope — was a cross-session leak under flat layout.
        _sess_tasks = self._session.session_tasks_dir
        if not resume_ws and _sess_tasks.is_dir():
            try:
                candidates = sorted(
                    (
                        d
                        for d in _sess_tasks.iterdir()
                        if d.is_dir() and d.name.startswith("research_")
                    ),
                    key=lambda d: d.name,
                    reverse=True,  # newest first
                )
                for cand in candidates:
                    if (cand / "results" / "research_output.txt").is_file():
                        resume_ws = str(cand)
                        logger.info(
                            "Auto-discovered completed research workspace: %s",
                            resume_ws,
                        )
                        break
            except Exception:
                pass

        bridge = ResearchProposeBridge(
            root_folder=root,
            model=args.get("model"),
            research_only=args.get("research_only", False),
            disable_unified_proposal=args.get("disable_unified_proposal", False),
            breakdown_only=args.get("breakdown_only", False),
            max_breakdown=args.get(
                "max_breakdown",
                args.get("max_queries", "5 to 20 (or you really want to suggest more)"),
            ),
            max_researches=args.get("max_researches"),
            # Round 9: per-session task workspaces.
            output_dir=self._session.session_tasks_dir,
            knowledge_bridge=self._session.knowledge_bridge,
            session_context=session_ctx,
            resume_workspace=resume_ws,
            base_inferencer_type=args.get("base_inferencer"),
            research_inferencer_type=args.get("research_inferencer"),
            proposal_inferencer_type=args.get("proposal_inferencer"),
        )
        self._session.workflow_context.active_workspace = str(bridge.workspace)

        # Send task_status so the frontend creates a task subtab with
        # workspace info, even for resumed/instant-completing tasks.
        try:
            import asyncio as _asyncio

            from agent_foundation.ui.interactive_base import (
                InteractionFlags,
            )

            task_id = f"research-{int(__import__('time').time())}"
            interactive = self._session.interactive
            # Persist a chronological task_ref BEFORE the WS emit (see
            # _exec_task / multi-task hub for the same pattern).
            # Best-effort: chip-write failures MUST NOT abort the task
            # launch — chip placement is auxiliary UI metadata.
            if self._session.conversation:
                try:
                    self._session.conversation.add_task_ref(
                        task_id=task_id,
                        label="Research & Proposal",
                        tool_name="research_propose",
                    )
                    await self._persist()
                except Exception as chip_err:
                    logger.warning(
                        "add_task_ref failed for research_propose "
                        "task_id=%s — task will still launch, chip "
                        "placement may be missing on resume: %s",
                        task_id,
                        chip_err,
                    )
            await _asyncio.to_thread(
                interactive._send_response,
                {
                    "type": "task_status",
                    "session_id": getattr(self._session.info, "session_id", ""),
                    "task_id": task_id,
                    "status": "starting",
                    "request": request[:80],
                    "workspace": str(bridge.workspace),
                },
                InteractionFlags.MessageOnly,
            )
        except Exception:
            task_id = None

        try:
            result = await bridge.run(request)

            # Send task_status: completed so the frontend marks the task subtab
            if task_id:
                try:
                    await _asyncio.to_thread(
                        interactive._send_response,
                        {
                            "type": "task_status",
                            "session_id": getattr(self._session.info, "session_id", ""),
                            "task_id": task_id,
                            "status": "completed",
                        },
                        InteractionFlags.MessageOnly,
                    )
                except Exception:
                    pass

            # Set SOP-expected output variables for this phase
            sop_outputs = {}
            try:
                ci = getattr(self._session, "conversation_inferencer", None)
                sop_obj = (
                    ci.prior_context.get("_sop")
                    if ci and hasattr(ci, "prior_context")
                    else None
                )
                if sop_obj:
                    phase_node = sop_obj.get_phase(rp_phase)
                    if phase_node and hasattr(phase_node, "outputs"):
                        for out_name in phase_node.outputs:
                            sop_outputs[out_name] = str(bridge.workspace)
            except Exception:
                pass
            # Resolve tool-registered viewable artifact path
            try:
                from rankevolve.src.resources.tools.registry import load_tool

                tool_def = load_tool("research_propose")
                resolved = self._resolve_field_templates(
                    tool_def, args, Path(bridge.workspace)
                )
                if "viewable_output_path" in resolved:
                    sop_outputs["viewable_artifact_path"] = resolved[
                        "viewable_output_path"
                    ]
                    if tool_def.viewable_output_label:
                        sop_outputs["viewable_artifact_label"] = (
                            tool_def.viewable_output_label
                        )
                    logger.info(
                        "research_propose viewable_artifact_path resolved: %s",
                        resolved["viewable_output_path"],
                    )
            except Exception as e:
                logger.error(
                    "research_propose _resolve_field_templates failed: %s",
                    e,
                    exc_info=True,
                )

            # Parse proposals and store in phase_outputs for fast retrieval
            # at confirmation time (avoids re-parsing unified_plan.md)
            try:
                import json as _json

                from agent_foundation.ui.proposal_parser import (
                    parse_proposals,
                )

                proposals_data = parse_proposals(bridge.workspace)
                if proposals_data:
                    sop_outputs["research_proposals_data"] = _json.dumps(
                        proposals_data.to_dict()
                    )
                    logger.info(
                        "Parsed %d proposals for phase_outputs",
                        proposals_data.total_count,
                    )
                # Store unified plan path for "View Full Research" button
                unified = (
                    Path(bridge.workspace)
                    / "checkpoints"
                    / "bta"
                    / "aggregator"
                    / "outputs"
                    / "unified_plan.md"
                )
                if unified.exists():
                    sop_outputs["unified_plan_path"] = str(unified)
            except Exception:
                logger.warning(
                    "Failed to parse proposals from workspace", exc_info=True
                )

            self._session.workflow_context.complete_phase(
                rp_phase,
                summary=request[:80],
                workspace_path=str(bridge.workspace),
                **sop_outputs,
            )
            result_text = f"Research-propose completed. Result: {str(result)[:2000]}"
            # Auto-advance for research_propose
            if self._queue_service and not getattr(
                self._session, "_is_auto_advance_turn", False
            ):
                import asyncio as _asyncio

                _session_id = getattr(self._session.info, "session_id", "")
                auto_msg = (
                    f"[System notification: Phase {rp_phase} (Research & Proposal) completed successfully. "
                    f"IMPORTANT: The workflow status has been updated — Phase {rp_phase} "
                    f"is now COMPLETED. Ignore any previous messages in the conversation "
                    f"that say '(running)' — those are from before the task finished. "
                    f"Workspace: {bridge.workspace}. "
                    f"Present a summary of the research and proposal results to the user. "
                    f"The user must review and confirm before proceeding to the next workflow phase.]"
                )
                logger.info(
                    "Auto-advance: queueing synthetic message for session=%s phase=%s",
                    _session_id,
                    rp_phase,
                )
                await _asyncio.to_thread(
                    self._queue_service.put,
                    f"user_input_{_session_id}",
                    {
                        "type": "chat_message",
                        "content": auto_msg,
                        "session_id": _session_id,
                        "auto_advance": True,
                    },
                )
                logger.info(
                    "Auto-advance: synthetic message queued successfully for session=%s",
                    _session_id,
                )
            else:
                logger.warning(
                    "Auto-advance SKIPPED for session=%s phase=%s (research_propose): "
                    "queue_service=%s, is_auto_advance_turn=%s. "
                    "Next phase's auto-advance will not fire.",
                    getattr(self._session.info, "session_id", ""),
                    rp_phase,
                    bool(self._queue_service),
                    getattr(self._session, "_is_auto_advance_turn", False),
                )
            return ToolExecutionResult(
                result=result_text,
                context_updates=self._get_workflow_context_updates(),
            )
        except Exception as e:
            self._session.workflow_context.fail_phase(
                rp_phase,
                error=str(e)[:80],
            )
            raise

    async def _exec_knowledge(self, args: dict[str, Any]) -> ToolExecutionResult:
        """Execute a /kn subcommand via route_kn_command."""
        from rankevolve.src.server.kn_command_router import route_kn_command

        subcmd = args.get("subcommand", args.get("name", ""))
        if not subcmd:
            return ToolExecutionResult(
                result="Error: knowledge tool requires a 'subcommand' (e.g., 'search', 'add')."
            )

        # Build raw args string from structured arguments
        raw_parts = [subcmd]
        for key in (
            "text",
            "query",
            "path",
            "piece_id",
            "new_content",
            "file_path",
            "action",
        ):
            if key in args:
                raw_parts.append(str(args[key]))
        for key, value in args.items():
            if key in (
                "subcommand",
                "name",
                "text",
                "query",
                "path",
                "piece_id",
                "new_content",
                "file_path",
                "action",
            ):
                continue
            if isinstance(value, bool) and value:
                raw_parts.append(f"--{key}")
            elif not isinstance(value, bool):
                raw_parts.append(f"--{key}")
                raw_parts.append(str(value))

        raw_args = " ".join(raw_parts)
        result = route_kn_command(
            raw_args, self._session.knowledge_bridge, self._session.conversation
        )
        return ToolExecutionResult(
            result=f"{'Success' if result.success else 'Failed'}: {result.message}"
        )

    async def _exec_set_session_root(self, args: dict[str, Any]) -> ToolExecutionResult:
        """Set or show the session root path."""
        import asyncio

        raw_path = args.get("path", "")
        if not raw_path:
            current = getattr(self._session.info, "session_root_path", "not set")
            return ToolExecutionResult(result=f"Current session root path: {current}")

        path = Path(raw_path).expanduser().resolve()
        if not path.is_dir():
            return ToolExecutionResult(result=f"Not a valid directory: {path}")

        self._session.info.session_root_path = str(path)

        # Notify the frontend of the config change via the interactive queue
        interactive = getattr(self._session, "interactive", None)
        if interactive and hasattr(interactive, "_send_response"):
            from agent_foundation.ui.interactive_base import (
                InteractionFlags,
            )

            try:
                await asyncio.to_thread(
                    interactive._send_response,
                    {
                        "type": "config_update",
                        "session_id": getattr(self._session, "session_id", ""),
                        "config": {"target_path": str(path)},
                    },
                    InteractionFlags.MessageOnly,
                )
            except Exception:
                logger.debug("Could not send config_update for session root change")

        return ToolExecutionResult(
            result=f"Session root path set to: {path}",
            context_updates={"session_root_path": str(path)},
        )

    async def _exec_set_workflow_target_path(
        self, args: dict[str, Any]
    ) -> ToolExecutionResult:
        """Set the workflow target path — must be a subpath of session_root_path."""
        from pathlib import Path

        path = args.get("path", "")
        if not path:
            current = getattr(self._session.info, "workflow_target_path", "not set")
            return ToolExecutionResult(
                result=f"Current workflow target path: {current}"
            )

        # Validate it's a subpath of session_root_path
        session_root_path = getattr(self._session.info, "session_root_path", "")
        if session_root_path:
            try:
                resolved = Path(path).resolve()
                root_resolved = Path(session_root_path).resolve()
                if not str(resolved).startswith(str(root_resolved)):
                    return ToolExecutionResult(
                        result=f"Error: workflow target path '{path}' is not under "
                        f"the session root path '{session_root_path}'. "
                        f"Please specify a subpath.",
                    )
            except Exception:
                pass  # If paths can't be resolved, skip validation

        self._session.info.workflow_target_path = path
        # Update phase_outputs for SOP phase completion tracking
        wc = self._session.workflow_context
        wc.phase_outputs["workflow_target_path"] = path
        if wc.state_tracker is not None:
            wc.state_tracker.state_outputs["workflow_target_path"] = path
        # Update variable manager if available
        self._set_variable("workflow_target_path", path)

        # Auto-complete Phase 0 if both setup outputs are now present
        if (
            "workflow_target_path" in wc.phase_outputs
            and "strategy" in wc.phase_outputs
        ):
            if wc.current_phase == "idle":
                wc.complete_phase("0", "Setup complete")

        return ToolExecutionResult(
            result=f"Workflow target path set to: {path}",
            context_updates={
                "workflow_target_path": path,
                "phase_outputs": dict(wc.phase_outputs),
                **self._get_workflow_context_updates(),
            },
        )

    async def _exec_set_strategy(self, args: dict[str, Any]) -> ToolExecutionResult:
        """Set the evolution strategy and update employee mindset accordingly."""
        strategy = args.get("strategy", "")
        if not strategy:
            current = getattr(self._session.workflow_context, "strategy", "not set")
            return ToolExecutionResult(result=f"Current strategy: {current}")

        # Update workflow context
        self._session.workflow_context.strategy = strategy

        # Update phase_outputs for SOP phase completion tracking
        wc = self._session.workflow_context
        wc.phase_outputs["strategy"] = strategy
        if wc.state_tracker is not None:
            wc.state_tracker.state_outputs["strategy"] = strategy

        # Use variable manager to override employee.mindset via alias
        self._set_variable("strategy", strategy)

        # Auto-complete Phase 0 if both setup outputs are now present
        if (
            "workflow_target_path" in wc.phase_outputs
            and "strategy" in wc.phase_outputs
        ):
            if wc.current_phase == "idle":
                wc.complete_phase("0", "Setup complete")

        return ToolExecutionResult(
            result=f"Evolution strategy set to: {strategy}",
            context_updates={
                # selected_strategy is the chosen KEY (e.g.
                # "paradigm_shifting_innovation"). It must NOT be put
                # under the bare name `strategy` because `strategy` is
                # an alias in .variables.yaml resolving to the full
                # employee.mindset dict; overloading the same name
                # silently shadows the alias.
                "selected_strategy": strategy,
                "phase_outputs": dict(wc.phase_outputs),
                **self._get_workflow_context_updates(),
            },
        )

    def _set_variable(self, key: str, value: Any) -> None:
        """Set a variable via the prompt renderer's variable manager, if available."""
        try:
            inferencer = getattr(self._session, "conversation_inferencer", None)
            if inferencer is None:
                return
            renderer = getattr(inferencer, "prompt_renderer", None)
            if renderer is None:
                return
            vm = getattr(renderer, "variable_manager", None)
            if vm is not None and hasattr(vm, "set"):
                vm.set(key, value)
        except Exception as e:
            logger.debug("Failed to set variable %s: %s", key, e)

    async def _exec_set_model(self, args: dict[str, Any]) -> ToolExecutionResult:
        """Change the LLM model."""
        model_name = args.get("model_name", "")
        if not model_name:
            return ToolExecutionResult(
                result="Error: 'model_name' argument is required."
            )
        if self._session.app_config:
            self._session.app_config.model = model_name
        return ToolExecutionResult(
            result=f"Model set to: {model_name}",
            context_updates={"model": model_name},
        )

    async def _exec_clear(self, args: dict[str, Any]) -> ToolExecutionResult:
        """Clear conversation history."""
        if self._session.conversation:
            self._session.conversation.clear()
        return ToolExecutionResult(result="Conversation cleared.")

    # Per-(session_id, multi_task_id) async lock cache for atomic writes
    # to ``hub_<mid>_implementations.json`` from the inline sidecar
    # writer below. Replaces the BUCK-broken lazy import of
    # ``chatbot_demo_react.backend.routes.hub_implementations_store``
    # (which would have created a webui→server cycle if added as a
    # runtime dep). Same JSON format as the webui's
    # ``load_hub_implementations`` reader expects.
    _hub_impl_locks: ClassVar[dict[tuple[str, str], Any]] = {}

    async def _append_hub_implementation_row(
        self,
        *,
        session_dir: Path,
        multi_task_id: str,
        row: dict[str, Any],
    ) -> None:
        """Atomic-append a row to ``hub_<mid>_implementations.json``.

        Mirrors the format of
        ``rankevolve/src/webui/backend/routes/hub_implementations_store.py``
        (the canonical reader). Concurrent BTA workers serialize via a
        per-(session, mid) ``asyncio.Lock`` so updates don't lose each
        other; cross-process writes are atomic via tempfile + rename.
        """
        import asyncio as _asyncio
        import json as _json
        import os as _os
        import tempfile as _tempfile

        session_id = getattr(self._session.info, "session_id", "") or ""
        lock_key = (session_id, multi_task_id)
        lock = self._hub_impl_locks.get(lock_key)
        if lock is None:
            lock = _asyncio.Lock()
            self._hub_impl_locks[lock_key] = lock

        path = session_dir / f"hub_{multi_task_id}_implementations.json"

        def _read_rows() -> list[dict[str, Any]]:
            if not path.is_file():
                return []
            try:
                doc = _json.loads(path.read_text(encoding="utf-8"))
                rows = doc.get("implementations", [])
                return rows if isinstance(rows, list) else []
            except Exception as e:
                logger.warning("Failed to load %s: %s", path, e)
                return []

        def _atomic_write(rows: list[dict[str, Any]]) -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "multi_task_id": multi_task_id,
                "implementations": rows,
            }
            fd, tmp_path = _tempfile.mkstemp(
                dir=str(path.parent),
                prefix=f"hub_{multi_task_id}_impls_",
                suffix=".tmp",
            )
            try:
                with _os.fdopen(fd, "w", encoding="utf-8") as f:
                    _json.dump(payload, f, indent=2)
                _os.replace(tmp_path, path)
            except Exception:
                try:
                    _os.unlink(tmp_path)
                except OSError:
                    pass
                raise

        async with lock:
            rows = await _asyncio.to_thread(_read_rows)
            batch_id = row.get("batch_id")
            merged: dict[str, Any] | None = None
            if batch_id:
                for i, existing in enumerate(rows):
                    if existing.get("batch_id") == batch_id:
                        merged = {**existing, **row}
                        rows[i] = merged
                        break
            if merged is None:
                rows.append(dict(row))
            await _asyncio.to_thread(_atomic_write, rows)

    def _collect_hypothesis_metadata_for_grouper(
        self, selected_ids: set[str]
    ) -> tuple[
        list[dict[str, Any]],
        dict[str, str],
        dict[str, list[str]],
        list[tuple[str, str, str]],
    ]:
        """Phase A2 plumbing — read the proposals tree the WebUI also
        reads (workflow_context.phase_outputs.research_proposals_data,
        same source as agent_websocket_routes.py:281-287's
        ``selection_snapshot.proposals``) and project the per-H
        metadata, phase membership, slot assignments, and conflict
        pairs the grouper template now consumes.

        All return values are degraded-gracefully — missing data
        produces empty containers, and the bridge / template render
        defensive ``{% if %}`` guards.
        """
        try:
            wc = getattr(self._session, "workflow_context", None)
            phase_outputs = (
                getattr(wc, "phase_outputs", None) if wc is not None else None
            )
            raw = (phase_outputs or {}).get("research_proposals_data")
            if isinstance(raw, str):
                import json as _json

                try:
                    raw = _json.loads(raw)
                except Exception:
                    raw = None
            if not isinstance(raw, dict):
                return [], {}, {}, []

            metadata: list[dict[str, Any]] = []
            phase_map: dict[str, str] = {}
            slots_map: dict[str, list[str]] = {}
            for phase in raw.get("phases") or []:
                phase_label = (phase or {}).get("label") or ""
                for proposal in (phase or {}).get("proposals") or []:
                    pid = (proposal or {}).get("id")
                    if not pid or pid not in selected_ids:
                        continue
                    metadata.append(
                        {
                            "id": pid,
                            "title": proposal.get("title") or "",
                            "description": proposal.get("description")
                            or proposal.get("approach")
                            or proposal.get("problem")
                            or "",
                            "category": proposal.get("category") or phase_label,
                            "phase": phase_label,
                            "slots": list(proposal.get("slots") or []),
                            "impact": proposal.get("impact") or "",
                        }
                    )
                    if phase_label:
                        phase_map[pid] = phase_label
                    slots = list(proposal.get("slots") or [])
                    if slots:
                        slots_map[pid] = slots

            # Conflict pairs from combo_constraints when present
            # (lazy — most hubs don't carry this today; safe empty fallback).
            conflict_pairs: list[tuple[str, str, str]] = []
            for constraint in raw.get("combo_constraints") or []:
                if not isinstance(constraint, dict):
                    continue
                # Each entry is something like {hypotheses: [H1, H8],
                # reason: "..."} — restrict to selected hypothesis pairs
                # so the grouper isn't asked about Hs it can't place.
                pair_ids = [
                    h
                    for h in (constraint.get("hypotheses") or [])
                    if isinstance(h, str) and h in selected_ids
                ]
                if len(pair_ids) < 2:
                    continue
                reason = str(constraint.get("reason") or "")
                # Emit each unordered pair within the conflict set once.
                for i in range(len(pair_ids)):
                    for j in range(i + 1, len(pair_ids)):
                        conflict_pairs.append((pair_ids[i], pair_ids[j], reason))

            return metadata, phase_map, slots_map, conflict_pairs
        except Exception as e:  # pragma: no cover — best-effort
            logger.warning(
                "implement_hypothesis: collect_hypothesis_metadata "
                "failed; grouper falls back to bare-id input (%s)",
                e,
            )
            return [], {}, {}, []

    async def _exec_implement_hypothesis(
        self, args: dict[str, Any]
    ) -> ToolExecutionResult:
        """Execute /implement-hypothesis via :class:`ImplementHypothesisBridge`.

        Round 11 — Stage 1 of the split-experiment plan. See
        :class:`ImplementHypothesisBridge` for the BTA composition.
        Mirrors :meth:`_exec_research_propose` pattern (lazy import for
        cycle avoidance, workspace under session-tasks, summary returned
        as the tool result).

        Plan: implement-selected-auto-mode-and-hub-nesting.md (L0a-e).
        Emits an outer multi-task ``task_status`` chip + one per-batch
        ``task_status`` chip per LLM-grouped batch + per-batch
        lifecycle transitions (``running`` → ``completed``/``error``)
        so the run appears as subtasks under the Experiment Hub's
        Progress tab. Per-batch completions also write the canonical
        ``hub_<mid>_implementations.json`` sidecar (the function with
        zero callers before this PR) so downstream consumers
        (Selection-tab "Done" badges, Apply Combos preflight gate)
        see the implementation evidence.
        """
        import asyncio as _asyncio
        import uuid

        from rankevolve.src.server.implement_hypothesis_bridge import (  # @manual -- lazy import; cycle avoidance
            ImplementHypothesisBridge,
        )

        selected_ids = args.get("selected_ids") or []
        if not selected_ids:
            return ToolExecutionResult(
                result="[/implement-hypothesis] no hypotheses selected. "
                "Pass --select H1,H17,..."
            )

        plan_text = ""
        plan_path = args.get("plan_path") or args.get("--plan") or ""
        if plan_path:
            try:
                plan_text = Path(plan_path).read_text(encoding="utf-8")
            except OSError as e:
                return ToolExecutionResult(
                    result=f"[/implement-hypothesis] could not read --plan {plan_path!r}: {e}"
                )

        workflow_target = (
            args.get("workflow_target_path")
            or args.get("--workflow-target-path")
            or getattr(self._session.info, "workflow_target_path", "")
            or ""
        )
        session_ctx = dict(self._session.session_context or {})
        if workflow_target:
            session_ctx["workflow_target_path"] = workflow_target

        # L0e — `--hub-id <mid>` flag binds this implementation to an
        # Experiment Hub: per-batch rows land in the HUB's
        # `hub_<hub_id>_implementations.json` (visible to Selection-tab
        # badges + Apply Combos preflight gate). Standalone callers
        # (CLI, tests) omit the flag → bridge falls back to its own
        # multi_task_id as the sidecar key.
        hub_id: str | None = args.get("hub_id") or None
        max_batch_size = int(args.get("max_batch_size") or 5)
        max_parallel = int(args.get("max_parallel") or 2)
        reuse_task = args.get("reuse_task") or None

        # L0a — mint outer multi-task id and emit `starting` chip
        # BEFORE the bridge runs. multi_task_id namespace
        # `implhyp-<8hex>` keeps it distinct from legacy
        # `create_experiment_hub` ids.
        if reuse_task:
            multi_task_id = (
                reuse_task
                if str(reuse_task).startswith("implhyp-")
                else f"implhyp-{uuid.uuid4().hex[:8]}"
            )
        else:
            multi_task_id = f"implhyp-{uuid.uuid4().hex[:8]}"

        # Phase A2: pull structured per-H metadata + phase + slots +
        # conflict_pairs out of the workflow_context's
        # `phase_outputs.research_proposals_data` (the same source the
        # WebUI's selection_snapshot reads from at
        # `agent_websocket_routes.py:281-287`). This gives the grouper
        # LLM real signal for category/relatedness batching instead of
        # bare H IDs.
        hypothesis_metadata, hypothesis_phase, hypothesis_slots, conflict_pairs = (
            self._collect_hypothesis_metadata_for_grouper(set(selected_ids))
        )

        bridge = ImplementHypothesisBridge(
            session_tasks_dir=self._session.session_tasks_dir,
            plan_text=plan_text,
            selected_ids=selected_ids,
            model=args.get("model"),
            base_inferencer_type=(args.get("base_inferencer") or "devmate_cli"),
            max_batch_size=max_batch_size,
            max_parallel=max_parallel,
            workflow_target_path=workflow_target,
            reuse_task=reuse_task,
            session_context=session_ctx,
            hub_id=hub_id,
            hypothesis_metadata=hypothesis_metadata,
            hypothesis_phase=hypothesis_phase,
            hypothesis_slots=hypothesis_slots,
            conflict_pairs=conflict_pairs,
        )

        session_id = getattr(self._session.info, "session_id", "")
        # Sidecar destination — Hub's mid when bound; else fall back to
        # the implhyp's own id (standalone path; isolated sidecar).
        sidecar_mid = hub_id or multi_task_id

        interactive = getattr(self._session, "interactive", None)
        InteractionFlags = None
        if interactive and hasattr(interactive, "_send_response"):
            from agent_foundation.ui.interactive_base import (
                InteractionFlags as _IF,
            )

            InteractionFlags = _IF

        async def _emit(payload: dict[str, Any]) -> None:
            """Best-effort task_status emit. Failures must NOT fail the
            implementation run."""
            if interactive is None or InteractionFlags is None:
                return
            try:
                await _asyncio.to_thread(
                    interactive._send_response,
                    payload,
                    InteractionFlags.MessageOnly,
                )
            except Exception as e:  # pragma: no cover — best-effort
                logger.warning(
                    "implement_hypothesis: task_status emit failed (%s): %s",
                    payload.get("status"),
                    e,
                )

        # Phase B1 — when `hub_id` is set (the WebUI path), emit ALL
        # implhyp chips with `task_type:"task"`, `multi_task_id=hub_id`,
        # `parent_task_id=hub_id` so they nest into the existing Hub's
        # runQueue (visible in the Hub's Implementation sub-tab) instead
        # of spawning a brand-new top-level Hub. Standalone path
        # (no hub_id, e.g. CLI) keeps the existing top-level multi-task
        # behavior so a fresh Hub is created.
        outer_multi_id: str = hub_id if hub_id else multi_task_id
        outer_task_type: str = "task" if hub_id else "multi"
        nested_in_hub: bool = bool(hub_id)

        # L0a — outer wrapper chip (a runQueue entry of the Hub when
        # nested; a top-level multi-task otherwise).
        await _emit(
            {
                "type": "task_status",
                "task_id": multi_task_id,  # implhyp-<8hex> — bridge run id
                "task_type": outer_task_type,
                **({"parent_task_id": hub_id} if nested_in_hub else {}),
                "multi_task_id": outer_multi_id,
                "status": "starting",
                "session_id": session_id,
                "label": "Implement Selected",
                "request": (
                    f"Implement Selected: {len(selected_ids)} hypotheses "
                    f"(max_batch_size={max_batch_size}, max_parallel={max_parallel})"
                ),
                "workspace": str(bridge.workspace),
                "metadata": {
                    "tool_name": "implement_hypothesis",
                    "selected_ids": list(selected_ids),
                    "max_batch_size": max_batch_size,
                    "max_parallel": max_parallel,
                    "hub_id": hub_id,
                    "sidecar_multi_task_id": sidecar_mid,
                    # Phase C3: bridge-emitted notices (e.g. max_parallel
                    # silently capped to 5). Frontend renders each entry
                    # under the chip label so the user sees what got
                    # changed without needing to grep server logs.
                    "notices": list(bridge.notices),
                    # Phase B1: distinguish wrapper vs per-batch rows so
                    # the frontend can render the Resume button (wrapper
                    # only) and optionally indent batch rows.
                    "implhyp_kind": "wrapper",
                    "implhyp_task_id": multi_task_id,
                },
            }
        )

        # Phase A1 — mirror the wrapper chip into wc.task_queue so it
        # survives session_state.json round-trips. Without this, the
        # WS-only chip lives only in the React reducer's in-memory state
        # and disappears on session reconnect (the original bug). Mirror
        # of the WS payload's shape; status starts at "running" so the
        # dispatcher's get_next_runnable never picks it up (Phase A5
        # adds a tool_name guard as additional defense).
        from datetime import datetime, timezone

        wc = self._session.workflow_context
        _now = datetime.now(timezone.utc).isoformat()
        wc.task_queue.append(
            {
                "task_id": multi_task_id,
                "tool_name": "implement_hypothesis",
                "title": "Implement Selected",
                "request": (
                    f"Implement Selected: {len(selected_ids)} hypotheses "
                    f"(max_batch_size={max_batch_size}, max_parallel={max_parallel})"
                ),
                "args": {},
                "status": "running",
                "workspace": str(bridge.workspace),
                "multi_task_id": outer_multi_id,
                "parent_task_id": hub_id if nested_in_hub else None,
                "hypothesis_id": ",".join(selected_ids),
                "phase": "3",
                "created_at": _now,
                "updated_at": _now,
                "metadata": {
                    "tool_name": "implement_hypothesis",
                    "selected_ids": list(selected_ids),
                    "max_batch_size": max_batch_size,
                    "max_parallel": max_parallel,
                    "hub_id": hub_id,
                    "sidecar_multi_task_id": sidecar_mid,
                    "notices": list(bridge.notices),
                    "implhyp_kind": "wrapper",
                    "implhyp_task_id": multi_task_id,
                },
            }
        )
        await self._persist()

        # L0b — `on_batches_grouped`: emit one queued chip per batch
        # AFTER the LLM grouper returns. This populates the Hub's
        # Implementation sub-tab so users see the planned batches before
        # workers spawn.
        async def _on_batches_grouped(batches: list[Any]) -> None:
            _now2 = datetime.now(timezone.utc).isoformat()
            for b in batches:
                await _emit(
                    {
                        "type": "task_status",
                        "task_id": f"{multi_task_id}-{b.batch_id}",
                        "task_type": "task",
                        # When nested in a Hub: parent IS the Hub directly
                        # (siblings of the wrapper chip). When standalone:
                        # parent is the implhyp wrapper (legacy nesting).
                        "parent_task_id": (hub_id if nested_in_hub else multi_task_id),
                        "multi_task_id": outer_multi_id,
                        "status": "queued",
                        "session_id": session_id,
                        "label": f"B{b.batch_id}: {','.join(b.items)}",
                        "request": f"Implement batch {b.batch_id}: {','.join(b.items)}",
                        "workspace": str(bridge.workspace / "batches" / b.batch_id),
                        "metadata": {
                            "batchId": b.batch_id,
                            "batchLabel": getattr(b, "label", "") or b.batch_id,
                            "hypothesisIds": list(b.items),
                            "rationale": getattr(b, "rationale", "") or "",
                            "implhyp_kind": "batch",
                            "implhyp_task_id": multi_task_id,
                        },
                    }
                )
                # Phase A2 — mirror per-batch chip into wc.task_queue.
                # Status "queued" matches the WS chip; Phase A5's
                # tool_name filter ensures the dispatcher never grabs
                # it (the bridge owns batch execution).
                wc.task_queue.append(
                    {
                        "task_id": f"{multi_task_id}-{b.batch_id}",
                        "tool_name": "implement_hypothesis_batch",
                        "title": f"B{b.batch_id}: {','.join(b.items)}",
                        "request": f"Implement batch {b.batch_id}: {','.join(b.items)}",
                        "args": {},
                        "status": "queued",
                        "workspace": str(bridge.workspace / "batches" / b.batch_id),
                        "multi_task_id": outer_multi_id,
                        "parent_task_id": (hub_id if nested_in_hub else multi_task_id),
                        "hypothesis_id": ",".join(b.items),
                        "phase": "3",
                        "created_at": _now2,
                        "updated_at": _now2,
                        "metadata": {
                            "batchId": b.batch_id,
                            "batchLabel": getattr(b, "label", "") or b.batch_id,
                            "hypothesisIds": list(b.items),
                            "rationale": getattr(b, "rationale", "") or "",
                            "implhyp_kind": "batch",
                            "implhyp_task_id": multi_task_id,
                        },
                    }
                )
            # One persist after all batches appended — single whole-file
            # write covers all N appends (mirrors the cost profile of the
            # original Hub creation path).
            await self._persist()

        # L0b/c — `on_batch_status`: emit per-batch lifecycle transitions
        # AND populate the canonical implementations sidecar on
        # completion/error.
        async def _on_batch_status(batch: Any, status: str, **kw: Any) -> None:
            error_msg = kw.get("error_message")
            payload: dict[str, Any] = {
                "type": "task_status",
                "task_id": f"{multi_task_id}-{batch.batch_id}",
                "task_type": "task",
                "parent_task_id": (hub_id if nested_in_hub else multi_task_id),
                "multi_task_id": outer_multi_id,
                "status": status,
                "session_id": session_id,
                "workspace": str(bridge.workspace / "batches" / batch.batch_id),
                "metadata": {
                    "batchId": batch.batch_id,
                    "batchLabel": getattr(batch, "label", "") or batch.batch_id,
                    "hypothesisIds": list(batch.items),
                    "implhyp_kind": "batch",
                    "implhyp_task_id": multi_task_id,
                    **({"error_message": error_msg} if error_msg else {}),
                },
            }
            if error_msg:
                payload["error_message"] = error_msg
            await _emit(payload)

            # Phase A3 — mirror status onto the persisted task_queue
            # entry. Persist only on terminal transitions
            # (running→completed/error) to keep the hot path light;
            # the WS emit above is sufficient for live UI updates.
            entry_id = f"{multi_task_id}-{batch.batch_id}"
            entry = wc.get_entry(entry_id)
            if entry is not None:
                entry["status"] = status
                entry["updated_at"] = datetime.now(timezone.utc).isoformat()
                if "metadata" not in entry:
                    entry["metadata"] = {}
                entry["metadata"]["batchWorkspace"] = batch.workspace
                if error_msg:
                    # Match the 4096-byte cap already enforced at
                    # chip-emit time (tool_executor.py:4674's
                    # `str(error_message)[:4096]` convention). Bounds
                    # session_state.json size; full traceback stays in
                    # the bridge's per-batch log file for forensics.
                    entry["metadata"]["error_message"] = str(error_msg)[:4096]
                if status in ("completed", "error"):
                    await self._persist()

            # L0c — sidecar callsite. ONE write per batch on terminal
            # transition (completed | error). `append_hub_implementation`
            # is async-locked per (session, mid) so concurrent BTA
            # workers serialize correctly.
            if status in ("completed", "error"):
                try:
                    # Hotfix (was: lazy import of
                    # `chatbot_demo_react.backend.routes.hub_implementations_store.append_hub_implementation`
                    # — that target is exposed by `webui:agent_routes`, which
                    # already depends on `:server_lib`. Adding the reverse dep
                    # would create a BUCK cycle. Inline the writer here using
                    # stdlib only; same JSON file format so the webui's
                    # `load_hub_implementations` reader keeps working).
                    session_dir = (
                        self._session.session_logger.session_dir
                        if getattr(self._session, "session_logger", None)
                        else None
                    )
                    if session_dir is not None and session_id:
                        from datetime import datetime, timezone

                        now = (
                            datetime.now(timezone.utc)
                            .isoformat()
                            .replace("+00:00", "Z")
                        )
                        # Phase A6: prefer the bridge-set ``batch.workspace``
                        # (which now matches BTA's actual ``worker_<i>``
                        # rebind) over the phantom ``batches/<bid>/``
                        # path BTA never writes to. Fall back to the old
                        # path only if ``batch.workspace`` is unset (e.g.,
                        # tests that bypass the worker factory).
                        actual_workspace = batch.workspace or str(
                            bridge.workspace / "batches" / batch.batch_id
                        )
                        await self._append_hub_implementation_row(
                            session_dir=Path(session_dir),
                            multi_task_id=sidecar_mid,
                            row={
                                "batch_id": batch.batch_id,
                                "hypothesis_ids": list(batch.items),
                                "status": status,
                                "workspace_path": actual_workspace,
                                "error_message": error_msg,
                                "createdAt": now,
                                "updatedAt": now,
                            },
                        )
                except Exception as e:  # pragma: no cover — best-effort
                    logger.warning(
                        "implement_hypothesis: append_hub_implementation "
                        "failed for batch=%s status=%s: %s",
                        batch.batch_id,
                        status,
                        e,
                    )

        # Run the bridge with both callbacks wired.
        try:
            summary = await bridge.run(
                plan_text,
                on_batches_grouped=_on_batches_grouped,
                on_batch_status=_on_batch_status,
            )
            outer_status = "completed"
            error_msg = None
        except Exception as e:
            logger.exception("implement_hypothesis bridge raised: %s", e)
            summary = (
                f"[/implement-hypothesis] bridge failed: {e}\n"
                f"workspace: {bridge.workspace}"
            )
            outer_status = "error"
            error_msg = str(e)

        # L0d — outer chip terminal status. Phase B1: same parentage
        # rules as the L0a starting emit so the terminal status updates
        # the right entry in the Hub's runQueue (or the standalone
        # multi-task page).
        # Phase D2: read error_message from implementation_summary.json
        # (D1 writes it there) so the wrapper chip's metadata carries
        # a structured error the frontend can surface via "View error".
        # Use the file-local `_json` alias convention (no top-level
        # `import json` in this module).
        import json as _json

        terminal_error: str | None = error_msg
        try:
            summary_path = bridge.workspace / "results" / "implementation_summary.json"
            if summary_path.is_file():
                _summary_doc = _json.loads(summary_path.read_text(encoding="utf-8"))
                if (
                    isinstance(_summary_doc, dict)
                    and _summary_doc.get("status") == "error"
                ):
                    terminal_error = (
                        _summary_doc.get("error_message")
                        or terminal_error
                        or "Bridge failed; see workspace for details."
                    )
        except (OSError, ValueError):
            pass

        terminal_payload: dict[str, Any] = {
            "type": "task_status",
            "task_id": multi_task_id,
            "task_type": outer_task_type,
            **({"parent_task_id": hub_id} if nested_in_hub else {}),
            "multi_task_id": outer_multi_id,
            "status": outer_status,
            "session_id": session_id,
            "workspace": str(bridge.workspace),
            "summary": {
                "report_path": str(
                    bridge.workspace / "results" / "implementation_summary.json"
                ),
            },
            "metadata": {
                "tool_name": "implement_hypothesis",
                "selected_ids": list(selected_ids),
                "max_batch_size": max_batch_size,
                "max_parallel": max_parallel,
                "hub_id": hub_id,
                "sidecar_multi_task_id": sidecar_mid,
                "notices": list(bridge.notices),
                "implhyp_kind": "wrapper",
                "implhyp_task_id": multi_task_id,
                **({"error_message": terminal_error} if terminal_error else {}),
            },
        }
        if terminal_error:
            terminal_payload["error_message"] = terminal_error
        await _emit(terminal_payload)

        # Phase A4 — mirror outer_status onto the persisted wrapper
        # entry so reconnect sees the final completed/error state.
        # The existing `await self._persist()` below covers this update.
        wrapper_entry = wc.get_entry(multi_task_id)
        if wrapper_entry is not None:
            wrapper_entry["status"] = outer_status
            wrapper_entry["updated_at"] = datetime.now(timezone.utc).isoformat()
            if terminal_error:
                if "metadata" not in wrapper_entry:
                    wrapper_entry["metadata"] = {}
                # Same 4096-byte cap as A3 (matches tool_executor.py:4674's
                # chip-side cap; bounds session_state.json size).
                wrapper_entry["metadata"]["error_message"] = str(terminal_error)[:4096]

        await self._persist()
        return ToolExecutionResult(result=summary)

    async def _exec_experiment_combos(
        self, args: dict[str, Any]
    ) -> ToolExecutionResult:
        """Execute /experiment-hypothesis-combos via :class:`ExperimentBridge`.

        Round 11 — Stage 2 of the split-experiment plan. Standalone path
        that takes a manual `--combos` list (no dependency on Stage 1).
        Stage 1's outputs land in the codebase as feature flags; this
        stage just toggles flag subsets per combo.

        Reuses the existing ExperimentBridge for now (Stage 2 is the
        breakdown-disabled case of that bridge); a future refactor can
        carve out a narrower ExperimentCombosBridge if the shared code
        becomes a maintenance burden.
        """
        from rankevolve.src.server.experiment_combos_bridge import (  # @manual -- lazy import; cycle avoidance
            aggregate_only_run,
            ExperimentCombosBridge,
            find_latest_experiment_workspace,
            parse_combos_arg,
            preflight_check_flags,
        )

        # Aggregator-only refresh path — re-runs the LLM aggregator over
        # per-combo analyses already on disk. Standalone, fast, idempotent.
        if args.get("aggregate_only"):
            return await self._exec_aggregator_only_refresh(
                args,
                aggregate_only_run=aggregate_only_run,
                find_latest_experiment_workspace=find_latest_experiment_workspace,
            )

        combos_raw = args.get("combos") or args.get("--combos") or ""
        combos = parse_combos_arg(combos_raw)
        if not combos:
            return ToolExecutionResult(
                result="[/experiment-hypothesis-combos] no combos parsed. "
                "Pass --combos 'H1;H17,H8;H56_BASELINE'"
            )

        skip_preflight = bool(
            args.get("skip_preflight") or args.get("--skip-preflight")
        )
        preflight_root_arg = (
            args.get("preflight_root") or args.get("--preflight-root") or ""
        )
        if not skip_preflight and preflight_root_arg:
            blocked = preflight_check_flags(combos, Path(preflight_root_arg))
            if blocked:
                lines = [
                    f"  • combo '{key}' missing flags: {', '.join(flags)}"
                    for key, flags in blocked.items()
                ]
                return ToolExecutionResult(
                    result=(
                        "[/experiment-hypothesis-combos] pre-flight failed — "
                        "the following combos reference flags not yet declared "
                        "in the codebase. Run /implement-hypothesis first or "
                        "pass --skip-preflight to override.\n" + "\n".join(lines)
                    )
                )

        workflow_target = (
            args.get("workflow_target_path")
            or args.get("--workflow-target-path")
            or getattr(self._session.info, "workflow_target_path", "")
            or ""
        )
        session_ctx = dict(self._session.session_context or {})
        if workflow_target:
            session_ctx["workflow_target_path"] = workflow_target

        bridge = ExperimentCombosBridge(
            session_tasks_dir=self._session.session_tasks_dir,
            plan_text="",  # combos are explicit; no plan parsing needed
            selected_ids=[],
            combos=combos,
            model=args.get("model"),
            base_inferencer_type=(args.get("base_inferencer") or "devmate_cli"),
            max_concurrency=int(args.get("max_concurrency") or 2),
            workflow_target_path=workflow_target,
            session_context=session_ctx,
            rounds=int(args.get("rounds") or 1),
        )
        summary = await bridge.run("")
        await self._persist()
        return ToolExecutionResult(result=summary)

    async def _exec_aggregator_only_refresh(
        self,
        args: dict[str, Any],
        *,
        aggregate_only_run: Any,
        find_latest_experiment_workspace: Any,
    ) -> ToolExecutionResult:
        """Run the aggregation-only BTA over per-combo analyses on disk.

        Plan: ``humming-tinkering-wirth.md`` §3.4. Auto-resolves the
        active session's latest experiment workspace; bypasses the
        --combos requirement and the pre-flight grep check.

        Materializes a sub-task chip in the conversation (mirroring the
        ``_exec_task`` pattern) so the user can see the refresh in flight
        and click into a workspace tab that shows the LLM input / output
        for inspection. The chip transitions starting → running →
        completed/error.

        Writes the LLM-rendered narrative through
        ``learnings_generator.regenerate_accumulated_learnings(..., override_md=...)``
        so the deterministic ``learnings_actions`` JSON fence is preserved
        and merged with the LLM's enriched prose.
        """
        import json as _json
        import secrets
        from datetime import datetime, timezone

        from rankevolve.src.server.experiment_bridge import ExperimentBridge  # @manual

        session_tasks_dir = self._session.session_tasks_dir
        session_dir = Path(session_tasks_dir).parent
        session_id = getattr(self._session.info, "session_id", None) or "unknown"
        # First-checkpoint log: confirms the slash command made it past the
        # WS, message handler, and command router into the executor. If this
        # line is absent from the server log after a click, the failure is
        # client-side (browser console will tell you which hop).
        logger.info(
            "aggregate_only_refresh: invoked session=%s session_dir=%s args_keys=%s",
            session_id,
            session_dir,
            sorted(args.keys()),
        )

        # ── Chip lifecycle: mint task_id + workspace BEFORE early-returns
        # so even fast-fail paths (no workspace, validation, no-op) leave a
        # final chip state instead of an orphan "starting".
        task_id = (
            f"agg_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
            f"_{secrets.token_hex(3)}"
        )
        task_workspace = Path(session_tasks_dir) / task_id
        task_workspace.mkdir(parents=True, exist_ok=True)

        # Streaming-gap-fix L3: bootstrap canonical sub-dirs so the chip
        # workspace matches the reference task layout from the very first
        # second (panel renders OUTPUTS / RESULTS / LOGS / ANALYSIS /
        # ARTIFACTS / CHECKPOINTS categories even before any artifact lands).
        # ExperimentBridge.__init__ also creates outputs/results/logs/combos/
        # /_runtime/{inferencer_cache,tmp_output_files} via _agg_factory, but
        # we need analysis/, artifacts/, and checkpoints/ which it doesn't.
        for _sub in (
            "outputs",
            "results",
            "logs",
            "analysis",
            "artifacts",
            "checkpoints",
        ):
            try:
                (task_workspace / _sub).mkdir(parents=True, exist_ok=True)
            except OSError as _bs_err:
                logger.warning(
                    "aggregate_only_refresh: bootstrap %s mkdir failed: %s",
                    _sub,
                    _bs_err,
                )

        # Streaming-gap-fix L3: per-task log handler. Filters on `task_id=<id>`
        # so the chip-scoped log captures only this refresh's events. Detached
        # in `_finalize`'s outer try/finally below to prevent handler leaks.
        # Soft guarantee — server-wide log remains the source of truth.
        _per_task_fh: logging.FileHandler | None = None
        try:
            _per_task_fh = logging.FileHandler(str(task_workspace / "logs" / "run.log"))
            _per_task_fh.setFormatter(
                logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
            )
            _task_id_token = f"task_id={task_id}"
            _per_task_fh.addFilter(
                lambda r, _tok=_task_id_token: _tok in (r.getMessage() or "")
            )
            logger.addHandler(_per_task_fh)
        except OSError as _fh_err:
            _per_task_fh = None
            logger.warning(
                "aggregate_only_refresh: logs/run.log handler attach failed: %s",
                _fh_err,
            )

        # Sidecar — same convention _exec_task uses for chip↔workspace
        # correlation on restart (line 2222-2233).
        try:
            session_logger = getattr(self._session, "session_logger", None)
            session_dir_name = (
                session_logger.session_dir.name if session_logger is not None else ""
            )
            (task_workspace / ".task_meta.json").write_text(
                _json.dumps(
                    {
                        "task_id": task_id,
                        "tool_name": "aggregate_only_refresh",
                        "session_id": session_id,
                        "session_dir": session_dir_name,
                    }
                ),
                encoding="utf-8",
            )
        except OSError as _meta_err:
            logger.warning(
                "aggregate_only_refresh: .task_meta.json write failed: %s",
                _meta_err,
            )

        chip_label = "Refresh Learnings"
        if self._session.conversation:
            try:
                self._session.conversation.add_task_ref(
                    task_id=task_id,
                    label=chip_label,
                    tool_name="aggregate_only_refresh",
                )
                await self._persist()
            except Exception as _chip_err:
                logger.warning(
                    "aggregate_only_refresh: add_task_ref failed for %s: %s",
                    task_id,
                    _chip_err,
                )

        async def _emit_status(status: str, **extra: Any) -> None:
            """Mirror _exec_task's emit pattern: persist on disk BEFORE
            the WS notification so a reconnect after disconnect-during-
            emit still sees the correct chip status. Best-effort —
            failures here MUST NOT break the pipeline."""
            interactive = getattr(self._session, "interactive", None)
            if interactive is None or not hasattr(interactive, "_send_response"):
                # Persist-only path (no WS yet); chip still updates on disk.
                await self._persist_task_status(task_id, status)
                return
            from agent_foundation.ui.interactive_base import (  # @manual
                InteractionFlags,
            )

            try:
                payload = self._make_task_status_payload(
                    None,  # no queue_entry — top-level one-shot task
                    session_id=session_id,
                    task_id=task_id,
                    status=status,
                    workspace=str(task_workspace),
                    # Tag every emit so the React reducer can route a
                    # `learningsVersion` bump on completion without
                    # inspecting the workspace path. Plan v5 §C.3 hook.
                    tool_name="aggregate_only_refresh",
                    **extra,
                )
                await self._persist_task_status(task_id, status)
                await asyncio.to_thread(
                    interactive._send_response,
                    payload,
                    InteractionFlags.MessageOnly,
                )
            except Exception as _ws_err:
                logger.warning(
                    "aggregate_only_refresh: task_status emit (%s) failed: %s",
                    status,
                    _ws_err,
                )

        async def _finalize(
            status: str,
            summary_md: str,
            result_text: str,
            *,
            error_message: str | None = None,
        ) -> ToolExecutionResult:
            """Single exit point: write summary.md → flip chip status →
            return ToolExecutionResult. Used for both success and every
            failure early-return so no path leaves an orphan chip state.

            ``error_message`` (Layer 3) is forwarded to the WS payload on
            error so the React workspace tab can render it inline,
            instead of leaving the user staring at "Waiting for task
            output…" with no clue what failed. Truncated defensively to
            4 KB to keep the WS frame small.

            Streaming-gap-fix L3: also detaches the per-task FileHandler
            (`logs/run.log`) here so it never leaks across runs. Idempotent.
            """
            # Detach per-task FileHandler before status emit so any
            # late-arriving log lines don't write to a closed file.
            nonlocal _per_task_fh
            if _per_task_fh is not None:
                try:
                    logger.removeHandler(_per_task_fh)
                    _per_task_fh.close()
                except Exception:
                    pass
                _per_task_fh = None

            try:
                (task_workspace / "summary.md").write_text(summary_md, encoding="utf-8")
            except OSError as _sum_err:
                logger.warning(
                    "aggregate_only_refresh: summary.md write failed: %s",
                    _sum_err,
                )
            extras: dict[str, Any] = {}
            if status == "error" and error_message:
                extras["error_message"] = str(error_message)[:4096]
            await _emit_status(status, **extras)
            await self._persist()
            return ToolExecutionResult(result=result_text)

        await _emit_status("starting", request=chip_label)

        # ── Pipeline pre-checks: hub-driven inputs first, picker fallback
        # second. The picker now requires a `combos/*/analysis/combo_*.md`
        # shape (Layer 1) so hub-only sessions correctly miss the picker.
        # Layer 2 fills that gap by sourcing inputs from the hub manifest.
        from chatbot_demo_react.backend.services.learnings_generator import (  # @manual
            _load_baseline_choice_id,
            _load_session_inputs,
            precompute_actions,
        )
        from rankevolve.src.server.experiment_combos_bridge import (  # @manual
            collect_aggregator_input_from_submissions,
            resolve_active_multi_task_id,
        )

        # Load submissions ONCE — reused for hub-fallback inputs AND for
        # the precompute envelope inside the lock.
        try:
            _submissions, _proposals_data, _overrides = _load_session_inputs(
                session_dir,
            )
        except Exception as _load_err:
            logger.warning(
                "aggregate_only_refresh: _load_session_inputs failed: %s",
                _load_err,
            )
            _submissions, _proposals_data, _overrides = [], None, None

        # Hub-resolution: explicit --reuse-hub → workflow_context →
        # exactly-one heuristic. Errors are diagnostic only at this stage;
        # they only become fatal if the picker also returns None.
        explicit_mid = args.get("reuse_hub") or args.get("--reuse-hub")
        wc_active = (
            getattr(self._session.workflow_context, "active_multi_task_id", None)
            if getattr(self._session, "workflow_context", None)
            else None
        )
        mid, mid_err = resolve_active_multi_task_id(
            session_dir,
            explicit=explicit_mid,
            workflow_context_active=wc_active,
        )

        # Plan v3 Layer 4 — aggregation settings (filter noise upstream).
        # Server defaults preserve back-compat (no flag = no filter); the
        # WebUI sends stricter defaults via the popover.
        min_epochs = int(args.get("min_epochs") or 0)
        exclude_incomparable = bool(
            args.get("exclude_incomparable") or args.get("--exclude-incomparable")
        )
        exclude_errored = bool(
            args.get("exclude_errored") or args.get("--exclude-errored")
        )

        hub_inputs: list[dict[str, str]] = []
        if _submissions:
            hub_inputs = collect_aggregator_input_from_submissions(
                _submissions,
                session_dir,
                min_epochs=min_epochs,
                include_incomparable=not exclude_incomparable,
                include_errored=not exclude_errored,
            )

        # Picker only consulted when hub fallback is empty (back-compat
        # for any future Stage-2 `--combos` workflow).
        workspace = (
            None
            if hub_inputs
            else find_latest_experiment_workspace(Path(session_tasks_dir))
        )

        source = (
            f"hub:{mid}"
            if hub_inputs
            else f"exp_glob:{workspace.name}"
            if workspace
            else "none"
        )

        if not hub_inputs and workspace is None:
            err = mid_err or (
                "No hub submissions and no qualifying exp_*/combos/* "
                "workspace found. Run /experiment-hypothesis-combos with "
                "--combos first, OR wait for at least one hub submission "
                "to reach a terminal status."
            )
            return await _finalize(
                "error",
                f"# Refresh Learnings — failed\n\n{err}\n",
                f"[/experiment-hypothesis-combos --aggregate-only] {err}",
                error_message=err,
            )

        target_path_arg = (
            args.get("aggregate_target") or args.get("--aggregate-target") or ""
        )
        if target_path_arg:
            target_path = Path(target_path_arg)
        else:
            target_path = session_dir / "_learnings" / "accumulated_learnings.md"

        # Build the aggregator inferencer via a temporary ExperimentBridge
        # — reuses the bridge's _build_dual + LLM-inferencer wiring without
        # actually running the worker chain.
        session_ctx = dict(self._session.session_context or {})

        def _agg_factory():
            # Streaming-gap-fix L1: pass `workspace_path=task_workspace` so
            # ExperimentBridge._create_llm_inferencer (line 440-457) bakes
            # `cache_folder=str(task_workspace / "_runtime" / "inferencer_cache")`
            # into the DevmateCli at construction. This is what controls
            # where stream_*.txt files get written; setting DualInferencer's
            # _workspace post-hoc does NOT change DevmateCli's cache_folder
            # (verified: cache_folder is a baked attribute, not derived).
            # Side benefit: ExperimentBridge auto-creates the canonical
            # subdirs (outputs/, results/, logs/, combos/, _runtime/...)
            # under task_workspace, so the chip workspace matches the
            # reference task layout for free. Also eliminates the orphan
            # `tasks/exp_<ts>_<hex>/` dir created per refresh.
            tmp_bridge = ExperimentBridge(
                session_tasks_dir=session_tasks_dir,
                plan_text="",
                selected_ids=[],
                combos=[],
                model=args.get("model"),
                base_inferencer_type=(args.get("base_inferencer") or "devmate_cli"),
                max_concurrency=1,
                workflow_target_path="",
                session_context=session_ctx,
                rounds=1,
                workspace_path=Path(task_workspace),
            )
            # Variant selection is via `template_version`, NOT
            # `template_variables`. The latter is an aspirational API
            # (load_variable() doesn't exist on TemplateManager); the
            # working mechanism is FileBasedVariableManager's Phase 2
            # versioned-folder fallback at file_based.py:691-697 which
            # resolves `{{ task_preamble }}` against
            # `_variables/task_preamble/<version>/default.jinja2` (or
            # the only file in that folder).
            _agg_inf = tmp_bridge._build_dual(
                role="accumulated_learnings",
                template_space="aggregation",
                template_version="accumulated_learnings",
                # Streaming-gap-fix: enable real DualInferencer behavior.
                # max_iterations=5 → propose → review → fix (up to 4
                # additional cycles) with consensus early-exit when the
                # reviewer's overall_severity ≤ COSMETIC (threshold
                # default per ConsensusConfig). Aggregation-specific
                # review.jinja2 + followup.jinja2 templates already exist
                # under aggregation/main/ and are well-designed for
                # synthesis review (severity-tracked issues + counter-
                # feedback support). Worst case ~5x baseline LLM time;
                # typical 2-3x with consensus early-exit.
                # debug_mode=True → captures DEBUG-level structured log
                # events (RawBaseResponse, RawReviewResponse, Raw-
                # FollowupResponse, InferenceResponse, Message,
                # ParentChildDebuggableLink) at logs/session/<Inferencer>
                # .jsonl.parts/ — without this, only INFO-level events
                # land there, missing the dual loop's review/fix outputs.
                max_iterations=5,
                debug_mode=True,
            )

            # Streaming-gap-fix L7: attach a SessionLogger (JsonLogger)
            # mirroring `dual_inferencer_bridge._setup_session_logging`
            # so structured per-inferencer logs land at
            # `<task_workspace>/logs/session/<Inferencer>.jsonl{,.parts/
            # {InferenceInput,InferenceResponse,Message,...}/}`.
            # Without this the `logs/session/` dir is missing and the user
            # sees only `logs/run.log` (the per-task FileHandler tail) —
            # NOT the rich structured per-inferencer captures the reference
            # `task_*/` workspaces have. ExperimentBridge._build_dual does
            # NOT do this wiring (DualInferencerBridge does); we replicate
            # the same pattern here so agg chips match the reference shape.
            try:
                from rich_python_utils.common_objects.debuggable import (  # @manual
                    LoggerConfig,
                )
                from rankevolve.src.utils.io_utils.json_io import (  # @manual
                    JsonLogger,
                    SpaceExtMode,
                )

                _logs_dir = Path(task_workspace) / "logs"
                _logs_dir.mkdir(parents=True, exist_ok=True)
                # `space_ext_mode=MOVE` causes the .jsonl extension on
                # file_path to MOVE into the per-space filename — i.e.
                # `<logs_dir>/session.jsonl` becomes the directory
                # `<logs_dir>/session/` and per-inferencer files land at
                # `<logs_dir>/session/<inferencer.id>.jsonl`. Matches the
                # reference task layout exactly.
                # `parts_file_namer=lambda obj: obj.get("type", "")` causes
                # log entries with `type: InferenceInput` to land under
                # `<file>.jsonl.parts/InferenceInput/...` — same parts
                # split the reference uses.
                _session_logger = JsonLogger(
                    file_path=str(_logs_dir / "session.jsonl"),
                    append=True,
                    is_artifact=True,
                    parts_min_size=0,
                    space_ext_mode=SpaceExtMode.MOVE,
                    parts_file_namer=lambda obj: obj.get("type", "")
                    if isinstance(obj, dict)
                    else "",
                )
                _logger_chain = [
                    (
                        _session_logger,
                        LoggerConfig(pass_item_key_as="parts_key_path_root"),
                    )
                ]

                # Attach to the DualInferencer + its child base/review
                # inferencers (which are the actual DevmateCli that
                # streams tokens). For DualInferencer constructed via
                # ExperimentBridge._build_dual line 500-501,
                # `base_inferencer is review_inferencer` (same instance),
                # so we attach once to the underlying child and once to
                # the wrapper. After post-construct mutation we MUST
                # re-normalize via `_normalize_loggers()` so the dict
                # form Debuggable.log() iterates over is rebuilt.
                #
                # `debug_mode=True` is now set at construction via
                # `_build_dual(debug_mode=True)` above — covers the
                # DualInferencer wrapper. The base/review children are
                # the same DevmateCli instance, but DevmateCli doesn't
                # emit DEBUG-level structured-logger events itself
                # (those fire from the DualInferencer wrapper around
                # the inferencer call), so child debug_mode isn't load-
                # bearing for the missing log types.
                for _target in (
                    _agg_inf,
                    getattr(_agg_inf, "base_inferencer", None),
                    getattr(_agg_inf, "review_inferencer", None),
                ):
                    if _target is None:
                        continue
                    _target.logger = list(_logger_chain)
                    if hasattr(_target, "_normalize_loggers"):
                        _target._normalize_loggers()
            except Exception as _slog_err:
                logger.warning(
                    "aggregate_only_refresh: SessionLogger attach failed: "
                    "%s — logs/session/ will be empty",
                    _slog_err,
                )

            return _agg_inf

        # Plan v5 §A.9 — stage→validate→archive→swap pipeline.
        from chatbot_demo_react.backend.services import (  # @manual
            learnings_archive as la,
        )
        from chatbot_demo_react.backend.services.learnings_generator import (  # @manual
            regenerate_accumulated_learnings,
        )

        force_refresh = bool(args.get("force_refresh") or args.get("--force-refresh"))
        archive_keep = int(
            args.get("archive_keep")
            or args.get("--archive-keep")
            or la.DEFAULT_KEEP_LAST_N
        )
        archive_reason = (
            args.get("archive_reason")
            or args.get("--archive-reason")
            or "refresh from UI"
        )
        archive_source = (
            args.get("archive_source") or args.get("--archive-source") or "refresh-llm"
        )
        triggered_by = args.get("triggered_by") or "system"

        # Streaming-gap-fix L3: write `request.txt` matching regular task
        # convention (`dual_inferencer_bridge.py:666` writes one for /task).
        # Best-effort — never breaks the pipeline.
        try:
            (task_workspace / "request.txt").write_text(
                f"aggregate_only_refresh "
                f"source={source!r} "
                f"min_epochs={min_epochs} "
                f"exclude_incomparable={exclude_incomparable} "
                f"exclude_errored={exclude_errored} "
                f"force_refresh={force_refresh} "
                f"archive_keep={archive_keep} "
                f"archive_source={archive_source!r} "
                f"triggered_by={triggered_by!r}\n",
                encoding="utf-8",
            )
        except OSError as _req_err:
            logger.warning(
                "aggregate_only_refresh: request.txt write failed: %s",
                _req_err,
            )

        # Streaming-gap-fix L3: write per-combo input audit index. Lighter
        # than re-parsing the 105 KB prompt body to figure out which combos
        # made the cut after the Layer-4 filters (min_epochs / exclude_*).
        try:
            inputs_index = [
                {
                    "combo_id": e.get("combo_id", ""),
                    "path": e.get("path", "") or "",
                    "summary_bytes": len((e.get("summary") or "").encode("utf-8")),
                    "source": source,
                }
                for e in hub_inputs
            ]
            (task_workspace / "analysis" / "inputs.json").write_text(
                _json.dumps(inputs_index, indent=2),
                encoding="utf-8",
            )
        except OSError as _idx_err:
            logger.warning(
                "aggregate_only_refresh: analysis/inputs.json write failed: %s",
                _idx_err,
            )

        await _emit_status("running")
        logger.info(
            "aggregate_only_refresh: workspace_resolved task_id=%s "
            "source=%s hub_inputs=%d glob_workspace=%s mid_err=%s "
            "min_epochs=%d exclude_incomparable=%s exclude_errored=%s "
            "force=%s archive_keep=%s archive_source=%s",
            task_id,
            source,
            len(hub_inputs),
            workspace.name if workspace else None,
            mid_err,
            min_epochs,
            exclude_incomparable,
            exclude_errored,
            force_refresh,
            archive_keep,
            archive_source,
        )

        # Acquire per-session lock for the entirety of the staging pipeline.
        lock = await la._refresh_lock_for(session_id)
        async with lock:
            logger.info(
                "aggregate_only_refresh: lock_acquired task_id=%s",
                task_id,
            )
            # GC any stale staging dirs from prior crashed attempts (>24h old).
            la._clean_staging(session_dir, run_id=None)

            run_id = la.mint_run_id()
            staging_dir = la.staging_dir_for(session_dir, run_id)
            staged_md_path = staging_dir / la.LIVE_MD_NAME
            la.write_stage_meta(
                staging_dir,
                {
                    "schema_version": la.SCHEMA_VERSION,
                    "run_id": run_id,
                    "kind": "aggregate_only_refresh",
                    "source": archive_source,
                    "status": "running",
                    "started_at": la._utc_iso(),
                    "reason": archive_reason,
                    "triggered_by": triggered_by,
                    "source_experiment_workspace": (
                        str(workspace) if workspace else f"hub:{mid or 'unknown'}"
                    ),
                    "task_id": task_id,
                },
            )

            # Compute the deterministic precompute envelope BEFORE the LLM
            # call so the aggregator can fill rationale/title/risk/openQs
            # for the structural rerank+combo rows. Reuses `_submissions`
            # already loaded above (no second disk read). Best-effort: on
            # failure, log and proceed without it (the LLM will emit
            # empty rerank/combo arrays per the task_instructions
            # fallback rule).
            precompute_envelope = None
            try:
                _baseline_id = _load_baseline_choice_id(session_dir)
                precompute_envelope = precompute_actions(
                    _submissions,
                    _proposals_data,
                    _overrides,
                    baseline_submission_id=_baseline_id,
                )
            except Exception as e:
                logger.warning(
                    "aggregate_only_refresh: failed to compute precompute "
                    "envelope (%s); LLM will emit empty rerank/combo arrays.",
                    e,
                )

            # Streaming-gap-fix L3: serialize the deterministic envelope
            # for forensics. Distinct from llm_input.md (which embeds a
            # JSON-stringified version inside the prompt body). Best-effort.
            if precompute_envelope is not None:
                try:
                    (
                        task_workspace / "analysis" / "precompute_envelope.json"
                    ).write_text(
                        _json.dumps(precompute_envelope, indent=2, default=str),
                        encoding="utf-8",
                    )
                except (OSError, TypeError) as _env_err:
                    logger.warning(
                        "aggregate_only_refresh: precompute_envelope.json "
                        "write failed: %s",
                        _env_err,
                    )

            # Run the LLM aggregator into staging. The bridge captures
            # llm_input.md + llm_response.md into task_workspace for
            # inspection from the chip's sub-task tab.
            try:
                llm_md = await aggregate_only_run(
                    # When `inputs` is supplied (hub path), this arg is
                    # used only as a logging/context breadcrumb. Pass
                    # session_dir as a harmless context path so we don't
                    # invent a phantom workspace dir.
                    workspace if workspace else session_dir,
                    staged_md_path,
                    aggregator_factory=_agg_factory,
                    precompute_envelope=precompute_envelope,
                    task_workspace=task_workspace,
                    inputs=hub_inputs if hub_inputs else None,
                )
                logger.info(
                    "aggregate_only_refresh: llm_returned task_id=%s "
                    "response_bytes=%d precompute=%s source=%s",
                    task_id,
                    len(llm_md.encode("utf-8")),
                    precompute_envelope is not None,
                    source,
                )
            except ValueError as e:
                la.update_stage_meta(
                    staging_dir,
                    status="failed",
                    validation_errors=[f"aggregator: {e}"],
                )
                return await _finalize(
                    "error",
                    f"# Refresh Learnings — failed\n\nAggregator error: {e}\n",
                    f"[/experiment-hypothesis-combos --aggregate-only] {e}",
                    error_message=f"Aggregator error: {e}",
                )

            # Build the merged body (LLM body + re-fenced learnings_actions JSON)
            # AND the staged precomputed sidecar — both written into staging_dir.
            try:
                regenerate_accumulated_learnings(
                    session_dir,
                    override_md=llm_md,
                    target_path=staged_md_path,
                )
            except Exception as e:
                logger.exception(
                    "aggregate_only_refresh: building staged content failed: %s", e
                )
                la.update_stage_meta(
                    staging_dir,
                    status="failed",
                    validation_errors=[f"merge: {e}"],
                )
                return await _finalize(
                    "error",
                    f"# Refresh Learnings — failed\n\nMerge step failed: {e}\n",
                    f"[/experiment-hypothesis-combos --aggregate-only] merge failed: {e}",
                    error_message=f"Merge step failed: {e}",
                )

            la.update_stage_meta(
                staging_dir,
                status="staged",
                llm_response_size_bytes=len(llm_md.encode("utf-8")),
            )

            # Streaming-gap-fix L3: capture pre-validation staged content
            # for forensics. Done BEFORE validation so failures are
            # inspectable. Best-effort.
            try:
                import shutil as _shutil

                _shutil.copy2(
                    str(staged_md_path),
                    str(task_workspace / "checkpoints" / f"staged_{run_id}.md"),
                )
            except OSError as _ck_err:
                logger.warning(
                    "aggregate_only_refresh: checkpoints/staged_*.md copy failed: %s",
                    _ck_err,
                )

            # Validate staged content; md5 match → graceful no-op.
            v = la._validate_staged(
                staged_md_path,
                current_md_path=la._live_md(session_dir),
            )
            logger.info(
                "aggregate_only_refresh: staged task_id=%s ok=%s no_op=%s errors=%s",
                task_id,
                v["ok"],
                v["no_op"],
                v.get("errors") or [],
            )

            # Streaming-gap-fix L3: serialize the validation verdict for
            # forensics. Best-effort. Captures the same v dict contents
            # used by the validate-failed branch below.
            try:
                (task_workspace / "results" / "staging_verdict.json").write_text(
                    _json.dumps(
                        {
                            "ok": v["ok"],
                            "no_op": v["no_op"],
                            "errors": v.get("errors") or [],
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )
            except OSError as _vd_err:
                logger.warning(
                    "aggregate_only_refresh: results/staging_verdict.json "
                    "write failed: %s",
                    _vd_err,
                )

            if not v["ok"]:
                la.update_stage_meta(
                    staging_dir,
                    status="invalid",
                    validation_errors=v["errors"],
                )
                errs = "; ".join(v["errors"])
                return await _finalize(
                    "error",
                    f"# Refresh Learnings — validation failed\n\n"
                    f"Errors: {errs}\n\n"
                    f"Staging kept at `{staging_dir}` for inspection.\n",
                    "[/experiment-hypothesis-combos --aggregate-only] "
                    f"validation failed: {errs}. "
                    f"Staging kept at {staging_dir} for inspection.",
                    error_message=f"Validation failed: {errs}",
                )
            if v["no_op"] and not force_refresh:
                # Drop staging and emit a no-op result. Chip lands on
                # "completed" with a clear no-change note.
                la._clean_staging(session_dir, run_id=run_id)
                return await _finalize(
                    "completed",
                    "# Refresh Learnings — no change\n\n"
                    "The LLM produced output identical to the live doc "
                    "(md5 match). No archive entry created. Use "
                    "`--force-refresh` to override.\n",
                    "[/experiment-hypothesis-combos --aggregate-only] "
                    "no effective change since last refresh (md5 match). "
                    "Use --force-refresh to override.",
                )

            # Phase 2 — archive + atomic swap. Already under the lock.
            commit = await la.archive_current_and_promote_staged(
                session_dir,
                staging_dir,
                run_id=run_id,
                kind="aggregate_only_refresh",
                source=archive_source,
                reason=archive_reason,
                triggered_by=triggered_by,
                source_combo_hashes=None,  # TODO: populated by bridge in a follow-up
                baseline_submission_id=None,
                keep_last_n=archive_keep,
                already_locked=True,
            )
            logger.info(
                "aggregate_only_refresh: committed task_id=%s archive_id=%s "
                "version=%s first_ever=%s pruned=%s",
                task_id,
                commit.get("archive_id"),
                commit.get("version"),
                commit.get("first_ever"),
                commit.get("archives_pruned", 0),
            )

            # Streaming-gap-fix L3: chip-scoped copies of the post-swap
            # artifacts. `outputs/accumulated_learnings.md` shows what THIS
            # chip produced (matches regular task workspaces' `outputs/`
            # convention). `outputs/archive_commit.json` captures the
            # archive metadata as JSON for programmatic inspection.
            try:
                _live_text = la._live_md(session_dir).read_text(encoding="utf-8")
                (task_workspace / "outputs" / "accumulated_learnings.md").write_text(
                    _live_text,
                    encoding="utf-8",
                )
            except OSError as _live_err:
                logger.warning(
                    "aggregate_only_refresh: outputs/accumulated_learnings.md "
                    "copy failed: %s",
                    _live_err,
                )
            try:
                (task_workspace / "outputs" / "archive_commit.json").write_text(
                    _json.dumps(commit, indent=2, default=str),
                    encoding="utf-8",
                )
            except (OSError, TypeError) as _ac_err:
                logger.warning(
                    "aggregate_only_refresh: outputs/archive_commit.json "
                    "write failed: %s",
                    _ac_err,
                )

        target_str = str(la._live_md(session_dir))

        # First-ever refresh on a brand-new session: there was no prior
        # live doc to preserve, so the archive ceremony was skipped (see
        # `_archive_and_swap_sync.have_prior` invariant). Reflect that in
        # the chip summary instead of pointing at a non-existent dir.
        first_ever = bool(commit.get("first_ever"))
        if first_ever:
            heading = "# Refresh Learnings — initial (no prior version)"
            archive_id_line = "- **Archive id**: _none — first-ever refresh_"
            archive_dir_line = "- **Archive dir**: _none — nothing to preserve_"
            result_lines = [
                f"- New live narrative at `{target_str}`",
                "- No archive entry created (no prior version existed); "
                "the next refresh will archive THIS content as v1.",
            ]
            result_text = (
                "[/experiment-hypothesis-combos --aggregate-only] "
                f"initial narrative committed at {target_str} "
                "(no prior version to archive)"
            )
        else:
            archive_dir = la._archive_root(session_dir) / commit["archive_id"]
            heading = f"# Refresh Learnings — v{commit['version']}"
            archive_id_line = f"- **Archive id**: `{commit['archive_id']}`"
            archive_dir_line = f"- **Archive dir**: `{archive_dir}`"
            result_lines = [
                f"- New live narrative at `{target_str}`",
                f"- Prior version archived at `{archive_dir}`",
            ]
            result_text = (
                "[/experiment-hypothesis-combos --aggregate-only] refreshed "
                f"narrative at {target_str} · archive {commit['archive_id']} "
                f"(v{commit['version']}, source={archive_source}"
                + (
                    f", pruned {commit['archives_pruned']}"
                    if commit.get("archives_pruned")
                    else ""
                )
                + ")"
            )

        success_summary = "\n".join(
            [
                heading,
                "",
                archive_id_line,
                f"- **Source**: `{archive_source}`",
                f"- **Reason**: {archive_reason}",
                f"- **Triggered by**: `{triggered_by}`",
                f"- **Live doc**: `{target_str}`",
                archive_dir_line,
                f"- **Archives pruned**: {commit.get('archives_pruned', 0)}",
                f"- **Precompute envelope supplied**: "
                f"{'yes' if precompute_envelope is not None else 'no'}",
                "",
                "## Inputs",
                f"- Per-combo analyses: `{workspace}/combos/*/analysis/combo_*.md`",
                "",
                "## Workspace artifacts (this folder)",
                "",
                "### Pre-template (what we built)",
                "- `llm_input.md` — body fed to `{{ input }}` in "
                "`aggregation/main/initial.jinja2`. Does NOT include the template "
                "wrapping (`task_preamble`, `<UserRequest>` envelope, etc.).",
                "",
                "### Post-template (what the LLM actually saw)",
                "- `logs/session/<Inferencer>.jsonl.parts/InferenceInput/<ts>_*.txt` "
                "— canonical SessionLogger capture of the fully-rendered prompt "
                "(template + variables + input). One file per round.",
                "- `logs/session/<Inferencer>.jsonl.parts/InferenceResponse/<ts>_*.txt` "
                "— canonical SessionLogger capture of the LLM response (per round, "
                "structured).",
                "- `logs/session/<Inferencer>.jsonl` — consolidated structured log.",
                "",
                "### Pipeline artifacts",
                "- `request.txt` — canonical CLI form of refresh args",
                "- `analysis/precompute_envelope.json` — deterministic structural "
                "inputs from `precompute_actions(...)`",
                "- `analysis/inputs.json` — per-combo input audit index",
                "- `outputs/accumulated_learnings.md` — chip-scoped copy of the "
                "produced live doc (post-swap; absent for no-op runs)",
                "- `outputs/archive_commit.json` — archive metadata "
                "(archive_id, version, etc.)",
                "- `results/staging_verdict.json` — validation outcome",
                "- `checkpoints/staged_<run_id>.md` — pre-validation staged content "
                "(forensics; present even on validation failure)",
                "- `logs/run.log` — per-task log tail filtered to this task_id",
                "",
                "### Convenience captures",
                "- `llm_response.md` — raw LLM response at workspace root "
                "(== latest `InferenceResponse/<ts>.txt`; root for discoverability)",
                "- `summary.md` — this file",
                "- `_runtime/inferencer_cache/...` — live token stream cache "
                "(debug-only; surfaced via the streaming panel above)",
                "",
                "## Result",
                *result_lines,
            ]
        )
        return await _finalize("completed", success_summary, result_text)

    async def _exec_experiment(self, args: dict[str, Any]) -> ToolExecutionResult:
        """Execute /experiment as a thin sequencer over the two sub-commands.

        Round 11: /experiment is now a thin wrapper that runs
        /implement-hypothesis (Stage 1) followed by
        /experiment-hypothesis-combos (Stage 2). When the user supplies
        only --select (no --combos), Stage 2 is skipped — the user can
        run combos later via the explicit sub-command.

        Behavior (per plan §"locked design decisions"):
          - --select H1,H17,...           → run Stage 1 only.
          - --combos H1;H17,H8;...        → run Stage 2 only (assumes
                                            flags already implemented).
          - both --select and --combos    → Stage 1 then Stage 2 sequential.
          - neither, just --plan          → use plan's hypothesis IDs as
                                            --select (Stage 1 only).

        Mirrors :meth:`_exec_research_propose` shape; lazy-imports both
        sub-bridges (`:server_lib` ↔ `agentic_foundation` cycle pattern).
        """
        from rankevolve.src.server.experiment_bridge import (  # @manual -- lazy import; cycle avoidance
            parse_combos_arg,
            parse_hypothesis_ids,
        )

        # Resolve plan text.
        plan_path_arg = args.get("plan_path") or args.get("plan") or ""
        plan_text = ""
        if plan_path_arg:
            try:
                plan_text = Path(plan_path_arg).read_text(encoding="utf-8")
            except OSError as e:
                return ToolExecutionResult(
                    result=f"[/experiment] could not read --plan {plan_path_arg!r}: {e}"
                )
        else:
            plan_text = args.get("request", "") or ""

        # Resolve selected_ids: explicit --select wins; else mine from plan.
        selected_ids: list[str] = list(args.get("selected_ids") or [])
        if not selected_ids:
            select_raw = args.get("select") or ""
            if select_raw:
                selected_ids = [s.strip() for s in select_raw.split(",") if s.strip()]
        if not selected_ids and plan_text:
            selected_ids = parse_hypothesis_ids(plan_text)

        combos_raw = args.get("combos") or ""
        combos = parse_combos_arg(combos_raw) if combos_raw else []

        run_stage1 = bool(selected_ids)
        run_stage2 = bool(combos)
        if not run_stage1 and not run_stage2:
            return ToolExecutionResult(
                result=(
                    "[/experiment] nothing to run. Provide either --select "
                    "(Stage 1: implement hypotheses) or --combos (Stage 2: "
                    "run training combos), or both. See /help."
                )
            )

        summaries: list[str] = []
        if run_stage1:
            stage1_args = dict(args)
            stage1_args["selected_ids"] = selected_ids
            stage1_args["plan_path"] = plan_path_arg
            summaries.append("─── Stage 1: /implement-hypothesis ───")
            res = await self._exec_implement_hypothesis(stage1_args)
            summaries.append(res.result)

        if run_stage2:
            stage2_args = dict(args)
            stage2_args["combos"] = combos_raw
            summaries.append("\n─── Stage 2: /experiment-hypothesis-combos ───")
            res = await self._exec_experiment_combos(stage2_args)
            summaries.append(res.result)

        await self._persist()
        return ToolExecutionResult(result="\n".join(summaries))

    async def _exec_experiment_status(
        self, args: dict[str, Any]
    ) -> ToolExecutionResult:
        """Render a comprehensive experiment-status report.

        Accepts a flow URL / bare ID / MAST job name as the positional
        ``identifier`` (or no positional argument to list persisted
        submissions for this session).

        See ``src/resources/tools/experiment_status/tool.json`` for the
        full flag surface.
        """
        # Lazy import to keep tool_executor's startup import graph small.
        from rankevolve.src.integrations.fblearner.exceptions import (  # @manual -- dep declared on server_lib via fblearner integration
            FlowNotFoundError as _FlowNotFoundError,
            MastClientError as _MastClientError,
        )
        from rankevolve.src.integrations.fblearner.experiment_status_report import (  # @manual
            build_report,
            format_experiment_status_markdown,
        )
        from rankevolve.src.integrations.fblearner.utils import (  # @manual
            parse_experiment_identifier,
        )

        identifier_text = (
            args.get("identifier") or args.get("--identifier") or args.get("text") or ""
        )
        identifier_text = (identifier_text or "").strip()

        # No-arg listing mode: enumerate persisted submissions in the
        # session_dir if available. Honest about its empty state today.
        if not identifier_text:
            session_dir = self._resolve_session_dir()
            if session_dir is None:
                return ToolExecutionResult(
                    result=(
                        "No identifier supplied and no session_dir is "
                        "available; cannot list persisted submissions."
                    )
                )
            submissions_path = session_dir / "submissions.json"
            if not submissions_path.is_file():
                return ToolExecutionResult(
                    result=(
                        "No identifier supplied and no persisted "
                        "submissions found at "
                        f"`{submissions_path}`. The persistence layer "
                        "(persist_experiment_status) is not yet enabled — "
                        "run with a flow URL / ID / MAST job name."
                    )
                )
            try:
                import json as _json

                raw = submissions_path.read_text(encoding="utf-8")
                data = _json.loads(raw)
            except Exception as e:
                return ToolExecutionResult(
                    result=f"Failed to read submissions.json: {e}"
                )
            entries: list[dict[str, Any]] = []
            if isinstance(data, list):
                entries = [d for d in data if isinstance(d, dict)]
            elif isinstance(data, dict):
                e2 = data.get("entries", [])
                if isinstance(e2, list):
                    entries = [d for d in e2 if isinstance(d, dict)]
            lines = [
                "## Persisted submissions",
                "",
                f"Found {len(entries)} entry(ies) in `{submissions_path}`:",
                "",
            ]
            for e in entries[:50]:
                lines.append(
                    f"- `{e.get('experiment_id', e.get('flow_id', '?'))}`  "
                    f"mast=`{e.get('mast_job', '')}`  "
                    f"status={e.get('status', '')}  "
                    f"started={e.get('start_time', '')}"
                )
            return ToolExecutionResult(result="\n".join(lines) + "\n")

        # Identified mode: parse → build → format.
        try:
            identifier = parse_experiment_identifier(identifier_text)
        except ValueError as e:
            return ToolExecutionResult(
                result=f"Error: {e}",
            )

        # Flag-set parsing (compose --metrics-only / --status-only).
        metrics_only = bool(args.get("metrics_only") or args.get("--metrics-only"))
        status_only = bool(args.get("status_only") or args.get("--status-only"))

        include_flow = not bool(args.get("no_flow") or args.get("--no-flow"))
        include_mast = not bool(args.get("no_mast") or args.get("--no-mast"))
        include_system_metrics = not bool(
            args.get("no_system_metrics") or args.get("--no-system-metrics")
        )
        include_metrics = not bool(args.get("no_metrics") or args.get("--no-metrics"))
        include_history = not bool(args.get("no_history") or args.get("--no-history"))
        include_links = not bool(args.get("no_links") or args.get("--no-links"))
        if metrics_only:
            include_flow = False
            include_mast = False
            include_system_metrics = False
            include_history = False
            include_links = False
        if status_only:
            include_system_metrics = False
            include_metrics = False
            include_history = False

        include_timeseries = bool(
            args.get("include_timeseries") or args.get("--include-timeseries")
        )
        metric_pattern = args.get("metric_pattern") or args.get("--metric-pattern")
        try:
            max_samples = int(
                args.get("max_samples") or args.get("--max-samples") or 200
            )
        except (TypeError, ValueError):
            max_samples = 200
        # Hard cap.
        max_samples = max(1, min(max_samples, 500))

        child = args.get("child") or args.get("--child")
        try:
            child_version_raw = args.get("child_version") or args.get("--child-version")
            child_version: int | None = (
                int(child_version_raw) if child_version_raw is not None else None
            )
        except (TypeError, ValueError):
            child_version = None
        try:
            child_attempt_raw = args.get("child_attempt") or args.get("--child-attempt")
            child_attempt: int | None = (
                int(child_attempt_raw) if child_attempt_raw is not None else None
            )
        except (TypeError, ValueError):
            child_attempt = None

        session_dir = self._resolve_session_dir()

        try:
            report = await build_report(
                identifier,
                include_flow=include_flow,
                include_mast=include_mast,
                include_system_metrics=include_system_metrics,
                include_metrics=include_metrics,
                include_timeseries=include_timeseries,
                metric_pattern=metric_pattern,
                max_samples=max_samples,
                child=child,
                child_version=child_version,
                child_attempt=child_attempt,
                include_history=include_history,
                include_links=include_links,
                session_dir=session_dir,
            )
        except _FlowNotFoundError as e:
            return ToolExecutionResult(result=f"Flow not found: {e}")
        except _MastClientError as e:
            return ToolExecutionResult(result=f"MAST client error: {e}")
        except Exception as e:
            logger.error("experiment_status build_report failed: %s", e, exc_info=True)
            return ToolExecutionResult(
                result=f"Error building experiment status report: {e}"
            )

        markdown = format_experiment_status_markdown(report)
        return ToolExecutionResult(result=markdown)

    def _resolve_session_dir(self) -> Path | None:
        """Resolve ``session_logger.session_dir`` defensively.

        ``self._session.session_context`` is a ``dict`` (NOT an object) so a
        naive ``getattr(self._session.session_context, "session_dir", None)``
        would silently return ``None``. The double-getattr chain reads the
        actual ``SessionLogger`` attribute and falls back to ``None`` when
        either layer is missing.
        """
        session_logger = getattr(self._session, "session_logger", None)
        if session_logger is None:
            return None
        session_dir = getattr(session_logger, "session_dir", None)
        if session_dir is None:
            return None
        try:
            return Path(session_dir)
        except Exception:
            return None
