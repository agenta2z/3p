"""Task dataclasses + handler implementations.

ALL Atlassian operations (Jira reads/writes + Bitbucket reads/writes) flow
through `RovoDevCliInferencer` via prompts. The orchestrator's only jobs are:
1. Queue scheduling (FIFO with delay)
2. Inferencer parallelism cap (semaphore)
3. Parsing structured sentinels (`TRIGGER_CREATE_PR:`, `PR_URL:`, `STATUS:`)
4. Persistence of (issue_key → pr_url) + completed set

Three task types orchestrate the loop:
  MonitorEpicTask  — inferencer polls Epic, transitions To-Do → In Progress,
                     emits `TRIGGER_CREATE_PR: <key>` lines per actionable issue
  CreatePRTask     — inferencer implements + opens PR, transitions In-Progress
                     → In Review, emits `PR_URL: <url>`
  MonitorPRTask    — inferencer polls PR, addresses CI / comments, on MERGED
                     transitions In-Review → Done; emits `STATUS: ...`
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, TYPE_CHECKING

from .state import PRRecord

if TYPE_CHECKING:
    from .orchestrator import Orchestrator

logger = logging.getLogger(__name__)

# Reference paths for the inferencer prompts.
#
# CODE_UNDERSTANDING + SYSTEM_UNDERSTANDING are auto-discovered per-codebase
# from the new `~/.ai-employee/projects/<workstream>/artifacts/` workspace
# (populated by codebase_investigation + system_and_signals_investigation
# scripts in earlier SOP phases). See `_resolve_understanding_paths()` below.
#
# TEST_SOP_PATH is a separate per-repo testing-convention reference (NOT one
# of our SOP outputs); kept as a hard-coded fallback for the PoC.
_LEGACY_CODE_UNDERSTANDING_PATH = (
    "/Users/tchen7/MyProjects/CoreProjects/OpenTeam/_dev/convo_ai_hack/code_understanding"
)
_LEGACY_SYSTEM_UNDERSTANDING_PATH = (
    "/Users/tchen7/MyProjects/CoreProjects/OpenTeam/_dev/convo_ai_hack/system_understanding"
)
_TEST_SOP_PATH = (
    "/Users/tchen7/MyProjects/CoreProjects/OpenTeam/_dev/convo_ai_hack/test_sop"
)


def _resolve_understanding_paths(workspace_path: str) -> tuple[str, str]:
    """Resolve CODE_UNDERSTANDING_PATH + SYSTEM_UNDERSTANDING_PATH for the
    given codebase.

    Resolution order:
      1. `~/.ai-employee/projects/<workstream>/artifacts/<phase>/` (canonical)
      2. `~/.ai-employee/projects/<workstream>/_runtime/...` (un-promoted)
      3. Legacy in-package `_runtime/` of the corresponding script
      4. Hard-coded legacy fallback (for backward compat with existing demos)

    Cached per-process: autodiscover is cheap but called many times per loop.
    """
    cached = _UNDERSTANDING_CACHE.get(workspace_path)
    if cached is not None:
        return cached

    from pathlib import Path
    try:
        # Import lazily to keep tasks.py importable in isolation.
        from openteam.use_cases._shared_runtime import autodiscover_phase_artifacts
        codebase = Path(workspace_path).expanduser().resolve()

        code_dir = autodiscover_phase_artifacts(codebase=codebase, phase_name="codebase")
        signals_dir = autodiscover_phase_artifacts(codebase=codebase, phase_name="signals")

        code_str = str(code_dir) if code_dir else _LEGACY_CODE_UNDERSTANDING_PATH
        signals_str = str(signals_dir) if signals_dir else _LEGACY_SYSTEM_UNDERSTANDING_PATH

        if code_dir is None:
            logger.info(
                "Phase-4: no auto-discovered code_understanding for codebase=%s; "
                "falling back to legacy hard-coded path %s",
                workspace_path, _LEGACY_CODE_UNDERSTANDING_PATH,
            )
        else:
            logger.info("Phase-4: auto-discovered code_understanding -> %s", code_str)

        if signals_dir is None:
            logger.info(
                "Phase-4: no auto-discovered system_understanding for codebase=%s; "
                "falling back to legacy hard-coded path %s",
                workspace_path, _LEGACY_SYSTEM_UNDERSTANDING_PATH,
            )
        else:
            logger.info("Phase-4: auto-discovered system_understanding -> %s", signals_str)

        _UNDERSTANDING_CACHE[workspace_path] = (code_str, signals_str)
        return code_str, signals_str
    except Exception as e:
        # Robustness: if anything goes wrong with autodiscovery, fall back to
        # legacy paths rather than crashing the whole orchestrator.
        logger.warning(
            "Phase-4: _resolve_understanding_paths failed (%s); falling back to legacy paths.",
            e,
        )
        result = (_LEGACY_CODE_UNDERSTANDING_PATH, _LEGACY_SYSTEM_UNDERSTANDING_PATH)
        _UNDERSTANDING_CACHE[workspace_path] = result
        return result


# Process-local cache so repeated handler calls don't re-walk the disk.
# Key: absolute workspace path (str). Value: (code_path_str, signals_path_str).
_UNDERSTANDING_CACHE: dict[str, tuple[str, str]] = {}

# Minimum polling intervals — hard floor enforced everywhere we set a
# `delay_seconds` for a self-re-enqueuing task. Even if a CLI flag or constructor
# arg passes a smaller value, the task's effective delay will be clamped UP to
# these floors. Rationale: inferencer calls cost ~$0.10-0.30 + 30-120s wall time;
# without a floor a config typo / bug could DDoS the LLM and burn $100/hr.
#
# Defaults (in the dataclass field initializers below) are chosen to be HIGHER
# than these floors for cost-effective steady-state operation; the floors are
# the safety net.
#
# To bypass for unit tests, set env var JIRA_BOARD_MONITOR_DISABLE_MIN_GAP=1.
MIN_EPIC_POLL_SECONDS = 180   # 3 min — fast enough for human-triggered events
MIN_PR_POLL_SECONDS = 900     # 15 min — paced for CI build cycles (~10-30 min)


def _floor(seconds: int, floor: int) -> int:
    """Clamp `seconds` up to `floor`, with two exceptions:
    1. `seconds == 0` is preserved — used for the initial seed kickoff
       (we want the first poll to run immediately, not after a 3-min wait).
       Subsequent re-enqueues from inside the handler use the user-configured
       interval which IS clamped to the floor.
    2. env var JIRA_BOARD_MONITOR_DISABLE_MIN_GAP=1 disables clamping entirely
       (for unit tests that want tight loops).
    """
    if seconds == 0:
        return 0
    if os.environ.get("JIRA_BOARD_MONITOR_DISABLE_MIN_GAP") == "1":
        return seconds
    return max(seconds, floor)

_PROMPTS_DIR = Path(__file__).parent / "prompts"

# Regex sentinels parsed from inferencer output
_TRIGGER_RE = re.compile(r"^TRIGGER_CREATE_PR:\s*([A-Z][A-Z0-9]+-\d+)\s*$", re.MULTILINE)
# Self-healing: "an In Progress / In Review issue already has an open PR with no
# orchestrator record" — orchestrator should pick up MonitorPR for it.
# Format: RESUME_MONITOR_PR: <ISSUE_KEY> <FULL_PR_URL>
_RESUME_MONITOR_RE = re.compile(
    r"^RESUME_MONITOR_PR:\s*([A-Z][A-Z0-9]+-\d+)\s+(https?://\S+)\s*$",
    re.MULTILINE,
)
_PR_URL_RE = re.compile(
    r"PR_URL:\s*(https://bitbucket\.org/([^/\s]+)/([^/\s]+)/pull-requests/(\d+))"
)
_STATUS_RE = re.compile(r"^STATUS:\s*([A-Z_]+)(?:\s*--\s*(.*))?\s*$", re.MULTILINE)
# JIRA_STATUS: <KEY>=<status text> — the LLM's self-report of a transition it performed.
# Captured as (key, status). Status may contain spaces (e.g. "In Progress", "In Review").
_JIRA_STATUS_RE = re.compile(r"^JIRA_STATUS:\s*([A-Z][A-Z0-9]+-\d+)\s*=\s*(.+?)\s*$", re.MULTILINE)


def _parse_jira_status_reports(output: str) -> dict[str, str]:
    """Parse all JIRA_STATUS: <KEY>=<status> sentinels from inferencer output.
    Returns {key: status_string}.
    """
    return {m.group(1): m.group(2) for m in _JIRA_STATUS_RE.finditer(output)}


def _verify_jira_status(
    reports: dict[str, str],
    expected: dict[str, set[str]],
    context: str,
) -> list[tuple[str, str, set[str]]]:
    """Compare inferencer-reported statuses against expected. Logs warnings
    for drift. Returns list of (key, reported, expected_set) for any mismatch.
    """
    drift: list[tuple[str, str, set[str]]] = []
    for key, exp_set in expected.items():
        reported = reports.get(key)
        if reported is None:
            logger.warning(
                "[%s] No JIRA_STATUS reported for %s — expected one of %s. "
                "LLM may have skipped the transition. Next poll will recheck.",
                context, key, sorted(exp_set),
            )
            drift.append((key, "<unreported>", exp_set))
            continue
        # Case-insensitive prefix match (e.g. "in progress" matches "In Progress")
        if not any(reported.strip().lower() == e.lower() for e in exp_set):
            logger.warning(
                "[%s] JIRA_STATUS drift for %s: reported=%r expected one of %s",
                context, key, reported, sorted(exp_set),
            )
            drift.append((key, reported, exp_set))
    return drift


# ---------- task dataclasses ----------

@dataclass
class MonitorEpicTask:
    epic_key: str
    assignee_hint: str            # e.g. "Tony Chen"
    assignee_account_id: str      # e.g. "712020:5cf4b2db-..."
    workspace_path: str
    # Default 600s (10 min). Hard floor MIN_EPIC_POLL_SECONDS (180s / 3 min)
    # is enforced in __post_init__ — any caller passing a smaller value will
    # be silently clamped UP (with a warning log).
    delay_seconds: int = 600
    # The steady-state cadence used when this task re-enqueues itself. If
    # delay_seconds is 0 (initial seed kickoff), the handler reads this
    # field to know what cadence to use for the NEXT iteration. Default 0
    # means "fall back to delay_seconds or dataclass default of 600".
    steady_state_delay_seconds: int = 0

    def __post_init__(self) -> None:
        clamped = _floor(self.delay_seconds, MIN_EPIC_POLL_SECONDS)
        if clamped != self.delay_seconds:
            logger.warning(
                "MonitorEpicTask delay_seconds=%d clamped UP to floor %d "
                "(MIN_EPIC_POLL_SECONDS). Set env JIRA_BOARD_MONITOR_DISABLE_MIN_GAP=1 "
                "to bypass (tests only).",
                self.delay_seconds, clamped,
            )
            self.delay_seconds = clamped
        # Also clamp steady_state_delay_seconds (which IS the steady-state
        # cadence — must respect the floor even if delay_seconds is 0).
        if self.steady_state_delay_seconds > 0:
            ss_clamped = _floor(self.steady_state_delay_seconds, MIN_EPIC_POLL_SECONDS)
            if ss_clamped != self.steady_state_delay_seconds:
                logger.warning(
                    "MonitorEpicTask steady_state_delay_seconds=%d clamped UP to %d",
                    self.steady_state_delay_seconds, ss_clamped,
                )
                self.steady_state_delay_seconds = ss_clamped

    @property
    def task_type(self) -> str:
        return "MonitorEpic"

    @property
    def primary_key(self) -> str:
        return self.epic_key


@dataclass
class CreatePRTask:
    issue_key: str
    workspace_path: str
    delay_seconds: int = 0

    @property
    def task_type(self) -> str:
        return "CreatePR"

    @property
    def primary_key(self) -> str:
        return self.issue_key


@dataclass
class MonitorPRTask:
    issue_key: str
    pr_url: str                   # full URL incl. workspace + repo + id
    workspace_path: str
    # Default 1800s (30 min). Hard floor MIN_PR_POLL_SECONDS (900s / 15 min)
    # is enforced in __post_init__. CI build cycles typically take 10-30 min,
    # so polling more often than every 15 min is just burning inferencer cost
    # without seeing new state. NEEDS_HUMAN paths slow further to 1800s+ inside
    # the handler.
    delay_seconds: int = 1800
    steady_state_delay_seconds: int = 0   # see MonitorEpicTask docstring

    def __post_init__(self) -> None:
        clamped = _floor(self.delay_seconds, MIN_PR_POLL_SECONDS)
        if clamped != self.delay_seconds:
            logger.warning(
                "MonitorPRTask delay_seconds=%d clamped UP to floor %d "
                "(MIN_PR_POLL_SECONDS). Set env JIRA_BOARD_MONITOR_DISABLE_MIN_GAP=1 "
                "to bypass (tests only).",
                self.delay_seconds, clamped,
            )
            self.delay_seconds = clamped
        if self.steady_state_delay_seconds > 0:
            ss_clamped = _floor(self.steady_state_delay_seconds, MIN_PR_POLL_SECONDS)
            if ss_clamped != self.steady_state_delay_seconds:
                logger.warning(
                    "MonitorPRTask steady_state_delay_seconds=%d clamped UP to %d",
                    self.steady_state_delay_seconds, ss_clamped,
                )
                self.steady_state_delay_seconds = ss_clamped

    @property
    def task_type(self) -> str:
        return "MonitorPR"

    @property
    def primary_key(self) -> str:
        return f"{self.issue_key}#{self.pr_url}"


@dataclass
class RescueIssueTask:
    """Dispatched when a CreatePR fails — transitions the issue back to To Do
    so the next Epic poll can re-pick it (preventing the stuck-in-progress
    dead-letter scenario)."""
    issue_key: str
    reason: str
    workspace_path: str
    delay_seconds: int = 0

    @property
    def task_type(self) -> str:
        return "RescueIssue"

    @property
    def primary_key(self) -> str:
        return self.issue_key


# ---------- shared inferencer helper ----------

async def _run_inferencer(
    prompt: str,
    workspace_path: str,
    orch: "Orchestrator",
    *,
    call_ctx: "CallContext | None" = None,
    prompt_vars: "dict | None" = None,
) -> str:
    """Invoke RovoDevCliInferencer under the orchestrator semaphore.

    If `call_ctx` is provided, this also persists the prompt, streams chunks
    to a log file, captures the clean output to a file, and writes call meta —
    all into `call_ctx.call_dir` (created by `RunWorkspace.begin_call`).

    Returns the full clean output string (empty if failed). Logs but does not
    raise on inferencer failure — caller checks for expected sentinels.
    """
    from agent_foundation.common.inferencers.agentic_inferencers.external.rovodev.rovodev_cli_inferencer import (
        RovoDevCliInferencer,
    )
    # Late import so the runtime module is optional / no circular imports.
    from openteam.use_cases.proposal_implementation.runtime import RunWorkspace

    # Persist the prompt up-front so we can debug even if the inferencer hangs.
    if call_ctx is not None:
        RunWorkspace.write_prompt(call_ctx, prompt)

    async with orch.inferencer_semaphore:
        # Use the call_dir as the rovodev --output-file location so the clean
        # output ends up next to the prompt.
        output_file_arg = str(call_ctx.clean_output_path) if call_ctx else None

        inf = RovoDevCliInferencer(
            target_path=workspace_path,
            idle_timeout_seconds=600,           # 10 min idle ceiling
            tool_use_idle_timeout_seconds=900,  # 15 min tool-use ceiling
            output_file=output_file_arg,
        )
        success = False
        clean_output = ""
        stderr_tail = ""
        try:
            if call_ctx is not None:
                # Stream chunks into stream.log for real-time tail-ability.
                # Per RovoDevCliInferencer.ainfer_streaming(): yields chunks
                # as they arrive; final clean output is also persisted to the
                # output_file via the CLI's --output-file flag.
                async for chunk in inf.ainfer_streaming(prompt):
                    text = getattr(chunk, "text", None) or str(chunk)
                    if text:
                        RunWorkspace.append_stream_chunk(call_ctx, text)
                # After streaming completes, the clean output file is populated.
                # Read it (RovoDevCliInferencer also stores it in _last_clean_output).
                try:
                    clean_output = call_ctx.clean_output_path.read_text(encoding="utf-8").strip()
                    success = bool(clean_output)
                except FileNotFoundError:
                    clean_output = getattr(inf, "_last_clean_output", "") or ""
                    success = bool(clean_output)
            else:
                # Legacy path: no runtime workspace, use simple ainfer()
                result = await inf.ainfer(prompt)
                clean_output = getattr(result, "output", "") or ""
                stderr_tail = (getattr(result, "stderr", "") or "")[-500:]
                success = bool(getattr(result, "success", False))
        except Exception as e:
            logger.exception("Inferencer crashed: %s", e)
            stderr_tail = f"EXCEPTION: {type(e).__name__}: {e}"
            # Try to capture whatever output exists so far
            if call_ctx is not None:
                try:
                    clean_output = call_ctx.clean_output_path.read_text(encoding="utf-8").strip()
                except Exception:
                    pass

    if not success:
        logger.error("Inferencer FAILED. stderr tail: %s", stderr_tail[-500:])

    # Persist final artifacts
    if call_ctx is not None:
        if clean_output and not call_ctx.clean_output_path.exists():
            RunWorkspace.write_clean_output(call_ctx, clean_output)
        RunWorkspace.finalize_call(
            call_ctx,
            success=success,
            prompt_vars=prompt_vars,
            extra_meta={"stderr_tail": stderr_tail[-500:]} if stderr_tail else None,
        )

    return clean_output


def _load_prompt(name: str, substitutions: dict[str, str]) -> str:
    text = (_PROMPTS_DIR / name).read_text(encoding="utf-8")
    for k, v in substitutions.items():
        text = text.replace("{{" + k + "}}", v)
    return text


# ---------- handlers ----------

async def handle_monitor_epic(
    task: MonitorEpicTask, orch: "Orchestrator"
) -> List[object]:
    """Invoke the inferencer to list+transition assigned issues; enqueue
    CreatePRTask per emitted TRIGGER_CREATE_PR line. Always re-enqueue self.
    """
    logger.info("[MonitorEpic %s] invoking inferencer (poll cadence %ds)",
                task.epic_key, task.delay_seconds)

    in_flight_issue_keys = sorted({
        marker.split(":", 1)[1].split("#", 1)[0]
        for marker in orch.state.in_flight
        if marker.startswith(("CreatePR:", "MonitorPR:", "RescueIssue:"))
    })
    # Stuck issues are treated like completed-but-unhappy: the prompt should
    # leave them alone. Bundle them into the COMPLETED_KEYS list passed to the
    # LLM since the contract there is "do NOT re-touch".
    completed_keys = sorted(orch.state.completed | orch.state.stuck)

    prompt_vars = {
        "EPIC_KEY": task.epic_key,
        "ASSIGNEE_HINT": task.assignee_hint,
        "ASSIGNEE_ACCOUNT_ID": task.assignee_account_id,
        "IN_FLIGHT_KEYS": "\n".join(f"- {k}" for k in in_flight_issue_keys) or "- (none)",
        "COMPLETED_KEYS": "\n".join(f"- {k}" for k in completed_keys) or "- (none)",
    }
    prompt = _load_prompt("monitor_epic.md", prompt_vars)

    call_ctx = None
    if orch.runtime_ws is not None:
        call_ctx = await orch.runtime_ws.begin_call(
            task_type="MonitorEpic", primary_key=task.epic_key, is_round_based=True,
        )
    output = await _run_inferencer(prompt, task.workspace_path, orch,
                                   call_ctx=call_ctx, prompt_vars=prompt_vars)

    triggered = _TRIGGER_RE.findall(output)
    # Self-healing sentinel: (issue_key, pr_url) tuples to start MonitorPR for
    # stranded PRs whose issues the orchestrator has no in-flight record of.
    resumes: List[tuple] = _RESUME_MONITOR_RE.findall(output)
    status_match = _STATUS_RE.search(output)
    status = status_match.group(1) if status_match else "UNKNOWN"
    logger.info(
        "[MonitorEpic %s] STATUS=%s; triggered=%s; resumes=%s",
        task.epic_key, status, triggered,
        [f"{k}={u}" for k, u in resumes],
    )

    # P2 — verify each triggered issue was actually reported transitioned to In Progress
    status_reports = _parse_jira_status_reports(output)
    expected = {k: {"In Progress"} for k in triggered}
    _verify_jira_status(status_reports, expected, context=f"MonitorEpic {task.epic_key}")

    if call_ctx is not None:
        from openteam.use_cases.proposal_implementation.runtime import RunWorkspace
        RunWorkspace.write_sentinels(call_ctx, {
            "status": status,
            "triggered": triggered,
            "resumes": [{"issue_key": k, "pr_url": u} for k, u in resumes],
            "jira_status_reports": status_reports,
        })

    follow_ups: List[object] = []
    for issue_key in triggered:
        if issue_key in orch.state.completed:
            logger.info("[MonitorEpic] skipping %s — already in completed set", issue_key)
            continue
        if issue_key in orch.state.stuck:
            logger.info("[MonitorEpic] skipping %s — marked stuck (rescue failed)", issue_key)
            continue
        marker = f"CreatePR:{issue_key}"
        any_pr_marker = f"MonitorPR:{issue_key}"
        rescue_marker = f"RescueIssue:{issue_key}"
        if (marker in orch.state.in_flight
                or rescue_marker in orch.state.in_flight
                or any(m.startswith(any_pr_marker + "#") for m in orch.state.in_flight)):
            logger.info("[MonitorEpic] skipping %s — already in flight", issue_key)
            continue
        follow_ups.append(CreatePRTask(
            issue_key=issue_key,
            workspace_path=task.workspace_path,
        ))

    # Self-healing path: STRANDED_PR issues — orchestrator has no record but
    # Jira shows an `In Progress`/`In Review` issue with an open PR. Start
    # MonitorPR for it (it will detect MERGED/DECLINED/etc. and transition
    # the issue appropriately on the next cycle).
    for resume_key, resume_pr_url in resumes:
        if resume_key in orch.state.completed:
            logger.info("[MonitorEpic] skipping resume %s — in completed set", resume_key)
            continue
        if resume_key in orch.state.stuck:
            logger.info("[MonitorEpic] skipping resume %s — marked stuck", resume_key)
            continue
        # Compose the orchestrator's MonitorPR primary key (matches enqueue() format)
        pr_marker = f"MonitorPR:{resume_key}#{resume_pr_url}"
        create_marker = f"CreatePR:{resume_key}"
        if (pr_marker in orch.state.in_flight
                or create_marker in orch.state.in_flight
                or any(m.startswith(f"MonitorPR:{resume_key}#") for m in orch.state.in_flight)):
            logger.info("[MonitorEpic] skipping resume %s — already in flight", resume_key)
            continue
        logger.info("[MonitorEpic] RESUME monitoring %s => %s", resume_key, resume_pr_url)
        # Mirror the same persistence the CreatePR success path does so
        # subsequent restarts find this mapping. Parse the canonical bitbucket
        # URL into a PRRecord; if it doesn't match, skip the record but still
        # enqueue the monitor (URL is enough for the monitor prompt).
        m = _PR_URL_RE.search(f"PR_URL: {resume_pr_url}")
        if m:
            _, ws_slug, repo_slug, pr_id_str = m.groups()
            try:
                orch.state.issue_to_pr[resume_key] = PRRecord(
                    workspace=ws_slug, repo=repo_slug, pr_id=int(pr_id_str), pr_url=resume_pr_url,
                )
            except (TypeError, ValueError) as e:
                logger.warning("[MonitorEpic] could not build PRRecord for %s: %s", resume_key, e)
        else:
            logger.warning(
                "[MonitorEpic] resume URL %r doesn't match canonical Bitbucket pattern; "
                "monitoring will still be enqueued but state.issue_to_pr will lack this record",
                resume_pr_url,
            )
        follow_ups.append(MonitorPRTask(
            issue_key=resume_key,
            pr_url=resume_pr_url,
            workspace_path=task.workspace_path,
            delay_seconds=0,  # poll immediately on first observation
        ))

    # Always re-enqueue self to keep watching. If this iteration was the
    # immediate-kickoff seed (delay_seconds == 0), use the configured steady-
    # state interval instead so we don't loop tightly. The dataclass default
    # (600s) is the canonical steady-state value when the user didn't override.
    next_delay = task.steady_state_delay_seconds or task.delay_seconds or 600
    follow_ups.append(MonitorEpicTask(
        epic_key=task.epic_key,
        assignee_hint=task.assignee_hint,
        assignee_account_id=task.assignee_account_id,
        workspace_path=task.workspace_path,
        delay_seconds=next_delay,
        steady_state_delay_seconds=task.steady_state_delay_seconds,
    ))
    return follow_ups


async def handle_create_pr(
    task: CreatePRTask, orch: "Orchestrator"
) -> List[object]:
    """Invoke the inferencer to implement + open a PR; on success enqueue MonitorPR."""
    logger.info("[CreatePR %s] invoking inferencer", task.issue_key)

    code_path, signals_path = _resolve_understanding_paths(task.workspace_path)
    prompt_vars = {
        "ISSUE_KEY": task.issue_key,
        "WORKSPACE_PATH": task.workspace_path,
        "CODE_UNDERSTANDING_PATH": code_path,
        "SYSTEM_UNDERSTANDING_PATH": signals_path,
        "TEST_SOP_PATH": _TEST_SOP_PATH,
    }
    prompt = _load_prompt("create_pr.md", prompt_vars)

    call_ctx = None
    if orch.runtime_ws is not None:
        call_ctx = await orch.runtime_ws.begin_call(
            task_type="CreatePR", primary_key=task.issue_key, is_round_based=False,
        )
    output = await _run_inferencer(prompt, task.workspace_path, orch,
                                   call_ctx=call_ctx, prompt_vars=prompt_vars)

    pr_match = _PR_URL_RE.search(output)
    status_match = _STATUS_RE.search(output)
    status = status_match.group(1) if status_match else "UNKNOWN"
    status_reports = _parse_jira_status_reports(output)

    if call_ctx is not None:
        from openteam.use_cases.proposal_implementation.runtime import RunWorkspace
        RunWorkspace.write_sentinels(call_ctx, {
            "status": status,
            "pr_url": pr_match.group(1) if pr_match else None,
            "jira_status_reports": status_reports,
        })

    if status == "NEEDS_HUMAN":
        reason = (status_match.group(2) if status_match else "") or "(no reason given)"
        logger.warning("[CreatePR %s] NEEDS_HUMAN: %s", task.issue_key, reason)
        # P1 — guard against stuck-in-progress dead-letter. Verify the prompt's
        # mandatory failure-path rollback actually happened. If reported status
        # is still In Progress (or not reported), dispatch a rescue task to
        # transition the issue back to To Do.
        reported = status_reports.get(task.issue_key, "<unreported>")
        if reported.strip().lower() not in ("to do", "open", "backlog"):
            logger.warning(
                "[CreatePR %s] LLM did not roll back (reported=%r). Dispatching RescueIssueTask.",
                task.issue_key, reported,
            )
            return [RescueIssueTask(
                issue_key=task.issue_key,
                reason=f"CreatePR NEEDS_HUMAN: {reason}",
                workspace_path=task.workspace_path,
            )]
        return []

    if not pr_match:
        logger.error(
            "[CreatePR %s] inferencer did not emit a valid PR_URL line; status=%s",
            task.issue_key, status,
        )
        # No PR_URL AND not NEEDS_HUMAN → malformed output; treat as failure
        # and dispatch rescue so the issue isn't left stuck.
        return [RescueIssueTask(
            issue_key=task.issue_key,
            reason=f"CreatePR returned malformed output (status={status}, no PR_URL)",
            workspace_path=task.workspace_path,
        )]

    pr_url, workspace, repo, pr_id_str = pr_match.group(1), pr_match.group(2), pr_match.group(3), pr_match.group(4)
    pr_id = int(pr_id_str)
    logger.info("[CreatePR %s] PR opened: %s (status=%s)", task.issue_key, pr_url, status)

    # P2 — verify the issue is now reported as In Review
    _verify_jira_status(
        status_reports, {task.issue_key: {"In Review"}},
        context=f"CreatePR {task.issue_key}",
    )

    orch.state.issue_to_pr[task.issue_key] = PRRecord(
        workspace=workspace, repo=repo, pr_id=pr_id, pr_url=pr_url,
    )

    # First MonitorPR after PR creation: kickoff immediately (delay=0). The
    # handler's _re_enqueue will then use the steady-state cadence. We don't
    # have the user's --pr-poll-interval-seconds here; the dataclass default
    # (1800s = 30 min) is the fallback, which is sensible for "just-opened
    # PR" first-poll cadence. If the user wants tighter, they'd seed the task
    # directly in run.py with their preferred steady_state_delay_seconds.
    return [MonitorPRTask(
        issue_key=task.issue_key,
        pr_url=pr_url,
        workspace_path=task.workspace_path,
        delay_seconds=0,
        steady_state_delay_seconds=0,  # use dataclass default of 1800s
    )]


async def handle_monitor_pr(
    task: MonitorPRTask, orch: "Orchestrator"
) -> List[object]:
    """Invoke the inferencer to poll + act on PR state. Re-enqueue unless
    terminal (MERGED / DECLINED / SUPERSEDED)."""
    logger.info("[MonitorPR %s] invoking inferencer (poll cadence %ds)",
                task.issue_key, task.delay_seconds)

    code_path, signals_path = _resolve_understanding_paths(task.workspace_path)
    prompt_vars = {
        "ISSUE_KEY": task.issue_key,
        "PR_URL": task.pr_url,
        "WORKSPACE_PATH": task.workspace_path,
        "CODE_UNDERSTANDING_PATH": code_path,
        "SYSTEM_UNDERSTANDING_PATH": signals_path,
        "TEST_SOP_PATH": _TEST_SOP_PATH,
    }
    prompt = _load_prompt("monitor_pr_full.md", prompt_vars)

    call_ctx = None
    if orch.runtime_ws is not None:
        call_ctx = await orch.runtime_ws.begin_call(
            task_type="MonitorPR",
            primary_key=f"{task.issue_key}#{task.pr_url}",
            is_round_based=True,
        )
    output = await _run_inferencer(prompt, task.workspace_path, orch,
                                   call_ctx=call_ctx, prompt_vars=prompt_vars)

    status_match = _STATUS_RE.search(output)
    status = status_match.group(1) if status_match else "UNKNOWN"
    reason = status_match.group(2) if status_match and status_match.group(2) else None
    status_reports = _parse_jira_status_reports(output)
    logger.info("[MonitorPR %s] STATUS=%s %s",
                task.issue_key, status, f"({reason})" if reason else "")

    if call_ctx is not None:
        from openteam.use_cases.proposal_implementation.runtime import RunWorkspace
        RunWorkspace.write_sentinels(call_ctx, {
            "status": status,
            "reason": reason,
            "jira_status_reports": status_reports,
        })

    if status == "MERGED":
        _verify_jira_status(
            status_reports, {task.issue_key: {"Done"}},
            context=f"MonitorPR {task.issue_key}",
        )
        orch.state.completed.add(task.issue_key)
        orch.state.issue_to_pr.pop(task.issue_key, None)
        return []

    if status in ("DECLINED", "SUPERSEDED"):
        # No status-set expectation here — workflow may allow rollback OR not.
        # Just log whatever the LLM reported.
        reported = status_reports.get(task.issue_key)
        if reported is not None:
            logger.info("[MonitorPR %s] post-%s status reported as %r",
                        task.issue_key, status, reported)
        else:
            logger.warning(
                "[MonitorPR %s] %s but no JIRA_STATUS report — verify manually.",
                task.issue_key, status,
            )
        orch.state.issue_to_pr.pop(task.issue_key, None)
        return []

    if status == "NEEDS_HUMAN":
        slowed = _re_enqueue(task)
        slowed.delay_seconds = max(task.delay_seconds, 1800)  # 30 min
        return [slowed]

    # AWAITING_REVIEWER, FIXED_PUSHED, FLAKE_RETRIGGERED, INFRA_RETRIGGERED,
    # ALL_COMMENTS_RESOLVED, UNKNOWN → keep watching
    return [_re_enqueue(task)]


async def handle_rescue_issue(
    task: RescueIssueTask, orch: "Orchestrator"
) -> List[object]:
    """Transition a stuck issue back to To Do so the next Epic poll can re-pick.

    The rescue prompt itself is responsible for figuring out the right
    workflow-compatible target status. If even the rescue fails, the issue
    is added to state.stuck so we don't infinitely retry.
    """
    logger.info("[Rescue %s] invoking inferencer; reason=%s",
                task.issue_key, task.reason)

    code_path, signals_path = _resolve_understanding_paths(task.workspace_path)
    prompt_vars = {
        "ISSUE_KEY": task.issue_key,
        "REASON": task.reason,
        "CODE_UNDERSTANDING_PATH": code_path,
        "SYSTEM_UNDERSTANDING_PATH": signals_path,
        "TEST_SOP_PATH": _TEST_SOP_PATH,
    }
    prompt = _load_prompt("rescue_issue.md", prompt_vars)

    call_ctx = None
    if orch.runtime_ws is not None:
        call_ctx = await orch.runtime_ws.begin_call(
            task_type="RescueIssue", primary_key=task.issue_key, is_round_based=False,
        )
    output = await _run_inferencer(prompt, task.workspace_path, orch,
                                   call_ctx=call_ctx, prompt_vars=prompt_vars)

    status_match = _STATUS_RE.search(output)
    status = status_match.group(1) if status_match else "UNKNOWN"
    status_reports = _parse_jira_status_reports(output)
    reported = status_reports.get(task.issue_key, "<unreported>")
    logger.info("[Rescue %s] STATUS=%s; final status=%r",
                task.issue_key, status, reported)

    if call_ctx is not None:
        from openteam.use_cases.proposal_implementation.runtime import RunWorkspace
        RunWorkspace.write_sentinels(call_ctx, {
            "status": status,
            "final_status_reported": reported,
            "jira_status_reports": status_reports,
        })

    if status in ("ROLLED_BACK", "ALREADY_ROLLED_BACK"):
        # Verify the actual reported status really is To Do
        if reported.strip().lower() in ("to do", "open", "backlog"):
            logger.info("[Rescue %s] successful rollback; issue will be re-picked on next Epic poll", task.issue_key)
        else:
            logger.warning(
                "[Rescue %s] STATUS=%s but reported status=%r doesn't match To-Do family",
                task.issue_key, status, reported,
            )
        return []

    if status == "PR_EXISTS_NO_ROLLBACK_NEEDED":
        logger.info("[Rescue %s] PR exists; no rollback needed", task.issue_key)
        # Don't enqueue a MonitorPR here — we don't know the PR URL. The next
        # Epic poll will see the issue in In Review and skip it; the human
        # owns it from here.
        return []

    if status == "ALREADY_DONE":
        logger.info("[Rescue %s] already Done; marking completed", task.issue_key)
        orch.state.completed.add(task.issue_key)
        return []

    # NEEDS_HUMAN / UNKNOWN — mark as stuck so we don't infinitely retry
    logger.error(
        "[Rescue %s] rescue failed (status=%s, reported=%r). Marking as stuck. Human intervention required.",
        task.issue_key, status, reported,
    )
    orch.state.stuck.add(task.issue_key)
    return []


def _re_enqueue(task: MonitorPRTask) -> MonitorPRTask:
    # If this was the initial kickoff (delay=0), fall back to the steady-state
    # cadence (or the dataclass default if neither is set).
    next_delay = task.steady_state_delay_seconds or task.delay_seconds or 1800
    return MonitorPRTask(
        issue_key=task.issue_key,
        pr_url=task.pr_url,
        workspace_path=task.workspace_path,
        delay_seconds=next_delay,
        steady_state_delay_seconds=task.steady_state_delay_seconds,
    )
