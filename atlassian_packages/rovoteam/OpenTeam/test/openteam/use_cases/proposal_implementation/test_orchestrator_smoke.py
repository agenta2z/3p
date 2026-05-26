"""Smoke tests for the orchestrator's resiliency guarantees.

These tests MOCK the inferencer so they run without any real LLM cost or
network access. They verify:
1. The handler-emit-follow-ups loop works (constant monitoring).
2. The safety re-enqueue fires when the inferencer crashes.
3. Idempotency: re-enqueueing the same task while in-flight is a no-op.

Run:
    cd /Users/.../OpenTeam
    python3 -m pytest test/openteam/use_cases/proposal_implementation/test_orchestrator_smoke.py -v
"""

from __future__ import annotations

import asyncio
import logging
import os

import pytest

from openteam.use_cases.proposal_implementation import orchestrator, state, tasks


@pytest.fixture(autouse=True)
def _disable_min_gap(monkeypatch):
    """Tests must NOT honor the prod min-gap floor (3-15 min) or async sleeps hang the suite."""
    monkeypatch.setenv("JIRA_BOARD_MONITOR_DISABLE_MIN_GAP", "1")


@pytest.fixture
def fresh_state(tmp_path) -> state.OrchestratorState:
    return state.OrchestratorState()


@pytest.fixture
def state_path(tmp_path) -> str:
    return str(tmp_path / "queue.json")


@pytest.mark.asyncio
async def test_monitor_epic_constantly_re_enqueues(monkeypatch, fresh_state, state_path):
    """Successful epic poll → returns at least the self-re-enqueue."""
    call_count = {"n": 0}

    async def fake_infer(prompt, ws, orch, **kwargs):
        call_count["n"] += 1
        return "STATUS: EPIC_POLL_COMPLETE\n"

    monkeypatch.setattr(tasks, "_run_inferencer", fake_infer)

    orch = orchestrator.Orchestrator(
        state=fresh_state, state_path=state_path,
        workspace_path="/tmp", num_workers=1, max_parallel_inferencers=1,
    )
    seed = tasks.MonitorEpicTask(
        epic_key="AI-236", assignee_hint="Tony Chen", assignee_account_id="abc",
        workspace_path="/tmp", delay_seconds=0,
    )
    await orch.start([seed])
    await asyncio.sleep(2.0)
    orch._shutdown.set()
    await asyncio.sleep(1.5)

    assert call_count["n"] >= 1
    assert "MonitorEpic:AI-236" in fresh_state.in_flight, (
        "After 1 successful poll, the self-re-enqueue should be in flight "
        "(sleeping for its delay)."
    )


@pytest.mark.asyncio
async def test_safety_reenqueue_on_inferencer_crash(monkeypatch, fresh_state, state_path):
    """A crashing inferencer must NOT silently kill the monitor loop."""

    async def crashing_infer(prompt, ws, orch, **kwargs):
        raise RuntimeError("simulated transient inferencer crash")

    monkeypatch.setattr(tasks, "_run_inferencer", crashing_infer)

    orch = orchestrator.Orchestrator(
        state=fresh_state, state_path=state_path,
        workspace_path="/tmp", num_workers=1, max_parallel_inferencers=1,
    )
    seed = tasks.MonitorEpicTask(
        epic_key="AI-236", assignee_hint="Tony Chen", assignee_account_id="abc",
        workspace_path="/tmp", delay_seconds=0,
    )
    await orch.start([seed])
    await asyncio.sleep(2.0)
    orch._shutdown.set()
    await asyncio.sleep(1.5)

    # Self-healing — safety re-enqueue puts the task BACK in flight after a
    # crash, with a min-gap floor. The task should be in flight either:
    # (a) directly (re-enqueued and still waiting on the priority queue), OR
    # (b) recorded in the in_flight set, OR
    # (c) re-running by the next worker.
    # Anything else means the safety net is broken.
    queue_has_task = orch.queue.qsize() > 0
    in_flight_has_task = "MonitorEpic:AI-236" in fresh_state.in_flight
    assert queue_has_task or in_flight_has_task, (
        f"Safety re-enqueue must keep task alive after crash. "
        f"queue.qsize={orch.queue.qsize()}, in_flight={fresh_state.in_flight}"
    )


@pytest.mark.asyncio
async def test_trigger_create_pr_enqueues_create_pr_task(monkeypatch, fresh_state, state_path):
    """When the inferencer emits TRIGGER_CREATE_PR: lines, the orchestrator
    must enqueue corresponding CreatePRTasks."""

    epic_call_done = asyncio.Event()
    create_calls: list[str] = []

    async def fake_infer(prompt, ws, orch, **kwargs):
        if "Epic curator" in prompt:
            epic_call_done.set()
            return "TRIGGER_CREATE_PR: AI-243\nTRIGGER_CREATE_PR: AI-247\nSTATUS: EPIC_POLL_COMPLETE\n"
        if "senior Atlassian engineer" in prompt:
            # Extract issue key from prompt
            import re
            m = re.search(r"\*\*Jira issue:\*\* (\S+)", prompt)
            if m:
                create_calls.append(m.group(1))
            # Return a fake PR url so the orchestrator stops at MonitorPR
            return (
                f"PR_URL: https://bitbucket.org/atlassian/conversational-ai-platform/pull-requests/9999\n"
                f"STATUS: PR_OPENED\n"
            )
        # Monitor PR — just stay in flight
        return "STATUS: AWAITING_REVIEWER\n"

    monkeypatch.setattr(tasks, "_run_inferencer", fake_infer)

    orch = orchestrator.Orchestrator(
        state=fresh_state, state_path=state_path,
        workspace_path="/tmp", num_workers=4, max_parallel_inferencers=2,
    )
    seed = tasks.MonitorEpicTask(
        epic_key="AI-236", assignee_hint="Tony Chen", assignee_account_id="abc",
        workspace_path="/tmp", delay_seconds=0,
    )
    await orch.start([seed])
    # Give time for Epic poll + 2 CreatePR runs
    await asyncio.wait_for(epic_call_done.wait(), timeout=5.0)
    await asyncio.sleep(3.0)
    orch._shutdown.set()
    await asyncio.sleep(1.5)

    assert set(create_calls) >= {"AI-243", "AI-247"}, (
        f"Expected CreatePR for AI-243 and AI-247; got {create_calls}"
    )


@pytest.mark.asyncio
async def test_resume_monitor_pr_enqueues_monitor_pr_task(monkeypatch, fresh_state, state_path):
    """When the inferencer emits RESUME_MONITOR_PR: lines (Enhancement 1:
    PR-presence reconciliation for stranded PRs), the orchestrator must
    enqueue MonitorPRTask without going through CreatePR — and must record
    the issue→PR mapping in state."""

    epic_call_done = asyncio.Event()
    monitor_pr_calls: list[tuple[str, str]] = []

    async def fake_infer(prompt, ws, orch, **kwargs):
        if "Epic curator" in prompt:
            epic_call_done.set()
            # Simulate a stranded-PR scenario: AI-243 is In Progress with an
            # existing open PR; AI-247 is a fresh To Do.
            return (
                "TRIGGER_CREATE_PR: AI-247\n"
                "JIRA_STATUS: AI-247=In Progress\n"
                "RESUME_MONITOR_PR: AI-243 https://bitbucket.org/atlassian/conversational-ai-platform/pull-requests/12345\n"
                "JIRA_STATUS: AI-243=In Progress\n"
                "STATUS: EPIC_POLL_COMPLETE\n"
            )
        if "PR custodian" in prompt:
            # MonitorPR — extract the (issue_key, pr_url) inputs
            import re
            issue_m = re.search(r"\*\*Jira issue:\*\* (\S+)", prompt)
            pr_m = re.search(r"\*\*PR URL:\*\* (\S+)", prompt)
            if issue_m and pr_m:
                monitor_pr_calls.append((issue_m.group(1), pr_m.group(1)))
            return "STATUS: AWAITING_REVIEWER\n"
        # CreatePR fake (for AI-247 fresh issue) — matches the "senior engineer" preamble
        return (
            "PR_URL: https://bitbucket.org/atlassian/conversational-ai-platform/pull-requests/9999\n"
            "STATUS: PR_OPENED\n"
            "JIRA_STATUS: AI-247=In Review\n"
        )

    monkeypatch.setattr(tasks, "_run_inferencer", fake_infer)

    orch = orchestrator.Orchestrator(
        state=fresh_state, state_path=state_path,
        workspace_path="/tmp", num_workers=4, max_parallel_inferencers=2,
    )
    seed = tasks.MonitorEpicTask(
        epic_key="AI-236", assignee_hint="Tony Chen", assignee_account_id="abc",
        workspace_path="/tmp", delay_seconds=0,
    )
    await orch.start([seed])
    await asyncio.wait_for(epic_call_done.wait(), timeout=5.0)
    await asyncio.sleep(3.0)
    orch._shutdown.set()
    await asyncio.sleep(1.5)

    # Verify the resume MonitorPR ran with the right (issue_key, pr_url)
    expected = ("AI-243", "https://bitbucket.org/atlassian/conversational-ai-platform/pull-requests/12345")
    assert expected in monitor_pr_calls, (
        f"Expected MonitorPR call for AI-243 with stranded PR url; got {monitor_pr_calls}"
    )
    # Verify state.issue_to_pr was updated for the resume — record must be PRRecord
    rec = fresh_state.issue_to_pr.get("AI-243")
    assert rec is not None, f"issue_to_pr missing AI-243; got {fresh_state.issue_to_pr}"
    assert rec.pr_url == expected[1], f"pr_url mismatch: {rec.pr_url} vs {expected[1]}"
    assert rec.pr_id == 12345 and rec.workspace == "atlassian" and rec.repo == "conversational-ai-platform"


def test_load_state_purges_stale_one_shot_markers(tmp_path):
    """Enhancement 2: orphan-purge — stale CreatePR / RescueIssue markers
    left over from a prior crashed run must be removed on startup, so
    MonitorEpic does not falsely skip the issue as 'already in flight'."""
    import json
    state_path = str(tmp_path / "queue.json")
    # Write a state file simulating a crashed prior run
    initial = {
        "in_flight": [
            "CreatePR:AI-243",          # one-shot — should be purged
            "RescueIssue:AI-244",       # one-shot — should be purged
            "MonitorEpic:AI-236",       # round-based — should survive
            "MonitorPR:AI-243#https://bitbucket.org/atlassian/conversational-ai-platform/pull-requests/9999",  # round-based
        ],
        "issue_to_pr": {
            "AI-243": {
                "workspace": "atlassian",
                "repo": "conversational-ai-platform",
                "pr_id": 9999,
                "pr_url": "https://bitbucket.org/atlassian/conversational-ai-platform/pull-requests/9999",
            },
        },
        "completed": [],
        "stuck": [],
    }
    with open(state_path, "w") as f:
        json.dump(initial, f)

    loaded = state.load_state(state_path)
    assert "CreatePR:AI-243" not in loaded.in_flight, "CreatePR should be purged"
    assert "RescueIssue:AI-244" not in loaded.in_flight, "RescueIssue should be purged"
    assert "MonitorEpic:AI-236" in loaded.in_flight, "MonitorEpic must survive"
    survivor = [m for m in loaded.in_flight if m.startswith("MonitorPR:AI-243#")]
    assert survivor, f"MonitorPR must survive; saw {loaded.in_flight}"
    record = loaded.issue_to_pr.get("AI-243")
    assert record is not None, "issue_to_pr must survive"
    assert record.pr_id == 9999, f"PRRecord round-trip failed: {record}"


def test_purge_stale_one_shot_markers_helper():
    """Direct unit test for the purge helper."""
    s = state.OrchestratorState()
    s.in_flight = {
        "CreatePR:AI-1",
        "CreatePR:AI-2",
        "RescueIssue:AI-1",
        "MonitorEpic:AI-99",
        "MonitorPR:AI-1#https://bb/pr/1",
    }
    purged = state.purge_stale_one_shot_markers(s)
    assert set(purged) == {"CreatePR:AI-1", "CreatePR:AI-2", "RescueIssue:AI-1"}
    assert s.in_flight == {"MonitorEpic:AI-99", "MonitorPR:AI-1#https://bb/pr/1"}


def test_resume_monitor_pr_regex_parses_valid_lines():
    """The RESUME_MONITOR_PR sentinel regex must accept canonical lines
    and reject malformed ones."""
    from openteam.use_cases.proposal_implementation.tasks import _RESUME_MONITOR_RE
    valid = (
        "RESUME_MONITOR_PR: AI-243 https://bitbucket.org/atlassian/conversational-ai-platform/pull-requests/12345\n"
        "RESUME_MONITOR_PR: PROJ-7  https://example.com/pr/1\n"   # extra space ok
    )
    matches = _RESUME_MONITOR_RE.findall(valid)
    assert matches == [
        ("AI-243", "https://bitbucket.org/atlassian/conversational-ai-platform/pull-requests/12345"),
        ("PROJ-7", "https://example.com/pr/1"),
    ]
    # Missing PR url
    bad = "RESUME_MONITOR_PR: AI-243\n"
    assert _RESUME_MONITOR_RE.findall(bad) == []


# ─── Catastrophe-prevention tests (revised 2026-05-20 — min-gap floor model) ─
# Earlier design used 3 count-based defenses (rapid-window breaker, per-task
# lifetime cap, global lifetime cap → shutdown). That worked but was too brittle:
# transient infra outages (Jira down >3h) would exhaust the budget and need a
# human restart. Replaced with a single time-based defense: unlimited
# re-enqueues, but a MINIMUM 5-min gap on every crash-path re-enqueue. This is
# self-healing AND bounds dir-creation rate to ≤ 288/day per task.
#
# Hard backstop: RunWorkspace.G-3 (1000 disk dirs → quarantine) is still in
# place for any edge case that bypasses the gap floor.

def _make_orch_for_defense_test(fresh_state, state_path):
    from openteam.use_cases.proposal_implementation.orchestrator import Orchestrator
    return Orchestrator(state=fresh_state, state_path=state_path, workspace_path="/tmp")


def _make_monitor_epic_task(key: str = "AI-T", steady: int = 600):
    return tasks.MonitorEpicTask(
        epic_key=key, assignee_hint="", assignee_account_id="",
        workspace_path="/tmp", delay_seconds=0, steady_state_delay_seconds=steady,
    )


def _make_monitor_pr_task(key: str = "AI-T", steady: int = 1800):
    return tasks.MonitorPRTask(
        issue_key=key, pr_url=f"https://example.com/pr/{key}",
        workspace_path="/tmp", delay_seconds=0, steady_state_delay_seconds=steady,
    )


def test_safety_reenqueue_uses_steady_state_not_zero(fresh_state, state_path):
    """The crash-path re-enqueue must NEVER carry forward task.delay_seconds=0
    (kickoff value), which would cause a tight loop. Uses steady_state floored
    by _MIN_REENQUEUE_GAP_SECONDS_CRASH."""
    o = _make_orch_for_defense_test(fresh_state, state_path)
    fresh_state.in_flight.discard("MonitorEpic:AI-T")
    # steady=600, crash_floor=300 → expect max(600,300)=600
    o._safety_reenqueue_on_error(_make_monitor_epic_task("AI-T", steady=600))
    t = o.queue.get_nowait()
    assert t.delay_seconds == 600, (
        f"Regression: safety re-enqueue produced delay={t.delay_seconds} "
        f"(should be 600 = steady_state, NOT 0 from kickoff)"
    )


def test_safety_reenqueue_honors_min_gap_floor(fresh_state, state_path):
    """If a task's steady_state is below the orchestrator's crash_floor (300s),
    the floor must win on the crash-path re-enqueue. This is THE core
    catastrophe-prevention guarantee — bounds crash re-enqueue rate to
    AT MOST once per 300s = 288 dirs/day per task, no matter what.

    NOTE: in normal runs the dataclass MIN_*_POLL_SECONDS floor (180s for
    Epic, 900s for PR) already prevents tiny steady_state values. This
    test bypasses the dataclass floor (autouse fixture sets
    JIRA_BOARD_MONITOR_DISABLE_MIN_GAP=1) to verify the orchestrator-side
    floor is a real second line of defense."""
    o = _make_orch_for_defense_test(fresh_state, state_path)
    fresh_state.in_flight.discard("MonitorEpic:AI-T")
    # In test mode the dataclass floor is bypassed, so steady=10 stays 10.
    task = _make_monitor_epic_task("AI-T", steady=10)
    assert task.steady_state_delay_seconds == 10, (
        f"Test setup: env var should bypass dataclass floor, "
        f"got {task.steady_state_delay_seconds}"
    )
    # Orchestrator must enforce max(10, 300) = 300.
    o._safety_reenqueue_on_error(task)
    t = o.queue.get_nowait()
    assert t.delay_seconds == 300, (
        f"Crash-floor regression: orch should enforce max(10, 300) = 300, "
        f"got {t.delay_seconds}"
    )


def test_unlimited_reenqueues_no_count_limit(fresh_state, state_path):
    """Self-healing guarantee — there must be NO count-based limit on
    re-enqueues. Even after 1000 simulated crashes, every one re-enqueues
    successfully. The defense is purely time-based (gap floor)."""
    o = _make_orch_for_defense_test(fresh_state, state_path)
    re_enqueued = 0
    for _ in range(1000):
        fresh_state.in_flight.discard("MonitorEpic:AI-T")
        before = o.queue.qsize()
        o._safety_reenqueue_on_error(_make_monitor_epic_task("AI-T"))
        if o.queue.qsize() > before:
            re_enqueued += 1
        try:
            o.queue.get_nowait()
            o.queue.task_done()
        except Exception:
            pass
    assert re_enqueued == 1000, (
        f"Self-healing regression: a count-based defense was reintroduced. "
        f"All 1000 attempts should have re-enqueued; only {re_enqueued} did."
    )


def test_defense_g3_disk_hard_cap(tmp_path):
    """Defense G-3 — RunWorkspace.begin_call refuses to create more than
    max_call_dirs per-call directories. Above the cap, returns a quarantine
    context whose call_dir is shared across all subsequent calls (no disk growth)."""
    from openteam.use_cases.proposal_implementation.runtime import RunWorkspace
    import asyncio

    async def _run():
        ws = RunWorkspace.create(tmp_path, max_call_dirs=3)
        # First 3 calls succeed with real per-call dirs
        for i in range(3):
            ctx = await ws.begin_call(
                task_type="MonitorEpic", primary_key=f"I-{i}", is_round_based=True,
            )
            assert "epic_monitor_I-" in ctx.call_dir.name, ctx.call_dir.name
        # Subsequent 100 calls all funnel into the shared quarantine dir
        for j in range(100):
            ctx = await ws.begin_call(
                task_type="MonitorEpic", primary_key=f"I-EX-{j}", is_round_based=True,
            )
            assert ctx.call_dir.name == "_runaway_quarantine", (
                f"Defense G-3 regression: call #{j+4} should be quarantined, "
                f"got {ctx.call_dir.name}"
            )
        total = sum(1 for p in ws.run_dir.iterdir() if p.is_dir())
        assert total == 4, (
            f"Defense G-3 regression: 103 calls produced {total} disk dirs "
            f"(expected exactly 4 = 3 real + 1 quarantine)"
        )

    asyncio.run(_run())
