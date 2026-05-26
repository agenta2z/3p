"""Queue + worker-pool orchestrator with a parallel-inferencer cap.

Design:
- One asyncio.Queue of generic tasks (any of MonitorEpicTask / CreatePRTask /
  MonitorPRTask).
- N worker coroutines pull tasks; for each task they:
    1) Sleep for `task.delay_seconds` (cheap, releases control)
    2) If task.needs_inferencer → acquire `inferencer_semaphore`
    3) Dispatch to the task-type's handler
    4) Enqueue any follow-up tasks the handler returned
    5) Persist state
- The semaphore caps how many RovoDevCliInferencer instances run concurrently.
  Cheap HTTP polls are NOT semaphore-bound.

Idempotency:
- `state.in_flight` tracks "task_type:primary_key" pairs to prevent the same
  unit of work being queued twice (e.g. if monitor_epic runs twice while a
  CreatePR is in flight, we don't double-enqueue).

Shutdown:
- Ctrl+C → cancel workers → save final state. In-flight inferencers can take
  up to their idle timeout to terminate.
"""

from __future__ import annotations

import asyncio
import logging
import signal
from typing import List, Optional

from . import tasks as task_mod
from .state import OrchestratorState, save_state

logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(
        self,
        *,
        state: OrchestratorState,
        state_path: str,
        workspace_path: str,
        num_workers: int = 4,
        max_parallel_inferencers: int = 2,
        runtime_ws: "object | None" = None,  # openteam.use_cases.proposal_implementation.runtime.RunWorkspace
    ) -> None:
        self.state = state
        self.state_path = state_path
        self.workspace_path = workspace_path
        self.queue: asyncio.Queue = asyncio.Queue()
        self.num_workers = num_workers
        self.inferencer_semaphore = asyncio.Semaphore(max_parallel_inferencers)
        self.runtime_ws = runtime_ws
        self._shutdown = asyncio.Event()
        self._workers: List[asyncio.Task] = []

    def enqueue(self, task: object) -> None:
        """Enqueue a task if not already in flight (idempotency)."""
        marker = f"{task.task_type}:{task.primary_key}"
        if marker in self.state.in_flight:
            logger.debug("Skipping duplicate enqueue: %s", marker)
            return
        self.state.in_flight.add(marker)
        self.queue.put_nowait(task)
        save_state(self.state, self.state_path)

    def _mark_done(self, task: object) -> None:
        marker = f"{task.task_type}:{task.primary_key}"
        self.state.in_flight.discard(marker)
        save_state(self.state, self.state_path)

    async def _worker(self, worker_id: int) -> None:
        logger.info("Worker %d started", worker_id)
        while not self._shutdown.is_set():
            try:
                task = await asyncio.wait_for(self.queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            try:
                if task.delay_seconds > 0:
                    logger.debug("Worker %d sleeping %ds before %s:%s",
                                 worker_id, task.delay_seconds,
                                 task.task_type, task.primary_key)
                    await asyncio.sleep(task.delay_seconds)
                follow_ups = await self._dispatch(task)
                # Mark current as done BEFORE enqueuing follow-ups so a follow-up
                # with the same primary_key (e.g. MonitorEpic re-enqueuing itself)
                # is not considered a duplicate.
                self._mark_done(task)
                for f in follow_ups:
                    self.enqueue(f)
            except Exception:
                logger.exception("Worker %d: task %s:%s failed",
                                 worker_id, task.task_type, task.primary_key)
                self._mark_done(task)
                # Safety re-enqueue: long-running monitor tasks (MonitorEpic /
                # MonitorPR) must NOT silently disappear on a single transient
                # failure. Re-enqueue them at a slowed cadence (>= 10 min) so
                # the loop keeps going. CreatePR tasks are NOT auto-retried —
                # they should be re-triggered by the next MonitorEpic poll
                # (which sees the Jira issue still In Progress / To Do).
                self._safety_reenqueue_on_error(task)
                # Yield to the event loop so a hot crash loop doesn't starve
                # other coroutines (incl. shutdown-event listeners). Critical
                # for tests where the same crash path repeats every iteration.
                await asyncio.sleep(0)
            finally:
                self.queue.task_done()
        logger.info("Worker %d shutting down", worker_id)

    # ─── Catastrophe prevention — single-layer min-gap floor ──────────────────
    # Design choice (2026-05-20, after the 896,692-dir incident):
    #
    # Earlier we had 3 separate count-based defenses (#3 rapid-window breaker,
    # G-1a per-task lifetime cap, G-1b global lifetime cap with shutdown).
    # Those caught the bug but made the orchestrator brittle: a transient
    # infra outage (Jira down for 30 min) would exhaust the per-task budget
    # (20) within a few hours and require a human to restart.
    #
    # The user proposed (and we adopted) a simpler, self-healing model:
    # "Unlimited re-enqueues, but enforce a minimum time gap on every
    # re-enqueue." That bounds dir-creation rate to a manageable level
    # (default 5 min → max 288 round dirs/day per task) while staying
    # self-healing across long outages.
    #
    # If the actual cause of the crashes is something deterministic (e.g.
    # missing PYTHONPATH), the system will keep trying forever — which is
    # fine because: (a) RunWorkspace.G-3 caps disk at 1000 dirs regardless,
    # (b) human-visible LATEST logs flag the issue, (c) ops dashboards / Slack
    # alerts surface persistent CrashLoopBackoff-style patterns.
    _MIN_REENQUEUE_GAP_SECONDS_CRASH = 300.0  # 5 min for crash-path re-enqueues
    # Successful re-enqueues use the task's own steady_state_delay_seconds
    # (already floored by tasks.MIN_*_POLL_SECONDS in dataclass __post_init__).

    def _safety_reenqueue_on_error(self, task: object) -> None:
        """If a long-running monitor task dies in-flight, re-enqueue it with
        AT LEAST `_MIN_REENQUEUE_GAP_SECONDS_CRASH` of delay so the loop
        survives transient failures without runaway disk/CPU growth.

        We only re-enqueue MonitorEpicTask + MonitorPRTask. CreatePRTask is
        single-shot per Jira-issue-transition; if it fails, the next Epic poll
        will notice the issue is still In Progress without a linked PR and
        the inferencer can re-attempt (or the prompt's idempotency check
        in Step 0 can short-circuit if a PR was partially opened).

        Self-healing guarantee: this method ALWAYS re-enqueues (no count
        limit). The disk cap (RunWorkspace.max_call_dirs) is the hard
        backstop in case re-enqueue rate × time-running ever exceeds 1000.
        """

        # Apply the crash-path min-gap floor: the next attempt MUST be at
        # least _MIN_REENQUEUE_GAP_SECONDS_CRASH (5 min) out, even if the
        # task's steady-state delay is shorter. This is THE catastrophe
        # prevention — bounds re-enqueue rate regardless of crash frequency.
        crash_floor = self._MIN_REENQUEUE_GAP_SECONDS_CRASH
        effective_delay = max(task.steady_state_delay_seconds, crash_floor)

        if isinstance(task, task_mod.MonitorEpicTask):
            new_task = task_mod.MonitorEpicTask(
                epic_key=task.epic_key,
                assignee_hint=task.assignee_hint,
                assignee_account_id=task.assignee_account_id,
                workspace_path=task.workspace_path,
                delay_seconds=int(effective_delay),
                steady_state_delay_seconds=task.steady_state_delay_seconds,
            )
            self.enqueue(new_task)
            logger.warning(
                "Safety re-enqueued MonitorEpic:%s with delay=%ds "
                "(steady=%ds, crash_floor=%ds)",
                task.epic_key, new_task.delay_seconds,
                new_task.steady_state_delay_seconds, int(crash_floor),
            )
        elif isinstance(task, task_mod.MonitorPRTask):
            new_task = task_mod.MonitorPRTask(
                issue_key=task.issue_key,
                pr_url=task.pr_url,
                workspace_path=task.workspace_path,
                delay_seconds=int(effective_delay),
                steady_state_delay_seconds=task.steady_state_delay_seconds,
            )
            self.enqueue(new_task)
            logger.warning(
                "Safety re-enqueued MonitorPR:%s with delay=%ds "
                "(steady=%ds, crash_floor=%ds)",
                task.issue_key, new_task.delay_seconds,
                new_task.steady_state_delay_seconds, int(crash_floor),
            )

    async def _dispatch(self, task: object) -> List[object]:
        # NOTE: ALL handlers invoke the inferencer; the semaphore is acquired
        # inside tasks._run_inferencer(), not here. This lets cheap pre/post
        # work (e.g. state lookups) run unbounded while only the actual LLM
        # call is rate-limited.
        if isinstance(task, task_mod.MonitorEpicTask):
            return await task_mod.handle_monitor_epic(task, self)
        if isinstance(task, task_mod.CreatePRTask):
            return await task_mod.handle_create_pr(task, self)
        if isinstance(task, task_mod.MonitorPRTask):
            return await task_mod.handle_monitor_pr(task, self)
        if isinstance(task, task_mod.RescueIssueTask):
            return await task_mod.handle_rescue_issue(task, self)
        raise TypeError(f"Unknown task type: {type(task)}")

    async def start(self, initial_tasks: List[object]) -> None:
        for t in initial_tasks:
            self.enqueue(t)
        self._workers = [
            asyncio.create_task(self._worker(i), name=f"worker-{i}")
            for i in range(self.num_workers)
        ]

    async def shutdown(self) -> None:
        logger.info("Shutdown requested; waiting for workers to drain")
        self._shutdown.set()
        for w in self._workers:
            try:
                await asyncio.wait_for(w, timeout=30.0)
            except asyncio.TimeoutError:
                w.cancel()
        save_state(self.state, self.state_path)
        logger.info("Shutdown complete. Final state persisted to %s", self.state_path)


def install_sigint_handler(orch: Orchestrator) -> None:
    loop = asyncio.get_running_loop()
    def _on_sig() -> None:
        logger.warning("SIGINT received; initiating graceful shutdown")
        asyncio.create_task(orch.shutdown())
    try:
        loop.add_signal_handler(signal.SIGINT, _on_sig)
        loop.add_signal_handler(signal.SIGTERM, _on_sig)
    except NotImplementedError:
        # Windows
        pass
