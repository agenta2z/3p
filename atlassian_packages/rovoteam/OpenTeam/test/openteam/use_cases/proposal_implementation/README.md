# proposal_implementation — All-Inferencer Prototype

End-to-end PoC that turns Jira-Epic board state into auto-created &
auto-monitored Bitbucket PRs. **EVERY Atlassian operation (Jira read/write,
Bitbucket read/write) is performed by `RovoDevCliInferencer` via prompts** —
the Python orchestrator only schedules, parallelism-caps, parses sentinels,
and persists state.

## What it does

1. **Watches one Epic** (e.g. `AI-236`) by periodically invoking the inferencer
   with `prompts/monitor_epic.md`. That prompt:
   - Lists child issues assigned to the configured user
   - Skips issues already in flight (orchestrator passes the in-flight list in)
   - Transitions To-Do/Open issues to **In Progress**
   - Emits one `TRIGGER_CREATE_PR: <key>` line per such issue
2. For each `TRIGGER_CREATE_PR:`, the orchestrator enqueues a `CreatePRTask`
   which invokes the inferencer with `prompts/create_pr.md`:
   - Idempotency check (no duplicate PR)
   - Reads issue + code/system-understanding refs
   - Implements smallest correct change + adds task spec
   - Validates locally (compile + test + lint)
   - Opens branch + commit + PR via Bitbucket REST API
   - Transitions issue to **In Review** + posts PR-link comment
   - Emits `PR_URL: <url>` + `STATUS: PR_OPENED` (or `PR_ALREADY_OPEN`)
3. The orchestrator enqueues a `MonitorPRTask` which invokes the inferencer
   with `prompts/monitor_pr_full.md`:
   - Polls PR state (OPEN/MERGED/DECLINED/SUPERSEDED)
   - On FAILED CI: triages GENUINE / FLAKE / INFRA, fixes or re-triggers
   - On unresolved review comments: ACCEPT-FIX / ACCEPT-DISCUSS / DECLINE-JUSTIFY
   - On MERGED: transitions issue to **Done**
   - Emits `STATUS: MERGED` (terminal) or one of the in-flight statuses
4. Tasks re-enqueue themselves until terminal. The orchestrator persists state
   on every mutation so Ctrl+C / resume works.

## Concurrency model

- Single `asyncio.Queue` (FIFO). N worker coroutines.
- `asyncio.Semaphore(MAX_PARALLEL_INFERENCERS)` is held ONLY while the actual
  LLM call is happening (acquired inside `tasks._run_inferencer`). Queue
  scheduling, state lookups, and prompt construction are unbounded.
- Idempotency via `state.in_flight = {"task_type:primary_key"}` — re-enqueue
  is a no-op if already present.
- Defense-in-depth: the `monitor_epic.md` prompt ALSO receives the in-flight
  set and is instructed not to trigger duplicates.

## What this is NOT

- NOT production-grade.
- NOT a replacement for proper Jira automation / Forge apps.
- NOT autonomous across processes — you must keep the script running.

## Running

### Prereqs (one-time, interactive)

- `acli rovodev` installed and authenticated (try `acli rovodev --version`).
- The inferencer needs working MCP-Atlassian + MCP-Bitbucket tools — these
  ship with Rovo Dev CLI, so just confirm by running `acli rovodev run
  "ping atlassian"` once.

### Invocation

```bash
cd /Users/tchen7/MyProjects/CoreProjects/OpenTeam

python3 -m test.openteam.use_cases.proposal_implementation.run \
    --epic AI-236 \
    --assignee-hint "Tony Chen" \
    --assignee-account-id "712020:5cf4b2db-f12d-4739-867d-9fe8ecb66d54" \
    --workspace /Users/tchen7/MyProjects/atlassian_packages/conversational-ai-platform \
    --max-parallel-inferencers 2 \
    --epic-poll-interval-seconds 600 \
    --pr-poll-interval-seconds 300
```

Ctrl+C → graceful shutdown (drains in-flight inferencers, persists state).

## Files

| File | Purpose |
|---|---|
| `run.py` | CLI entry point. Parses args, bootstraps orchestrator, handles SIGINT |
| `orchestrator.py` | The queue + worker-pool. Tiny — just dispatch + semaphore |
| `tasks.py` | Task dataclasses + handlers. Each handler: load prompt → run inferencer → parse sentinels → return follow-up tasks |
| `state.py` | JSON persistence (resume after Ctrl+C) |
| `prompts/monitor_epic.md` | Poll Epic, transition assigned To-Do issues to In Progress, emit `TRIGGER_CREATE_PR:` lines |
| `prompts/create_pr.md` | Implement issue + open PR + transition to In Review + emit `PR_URL:` |
| `prompts/monitor_pr_full.md` | Poll PR + address CI / comments + on MERGED transition to Done + emit `STATUS:` |

## Sentinel contract (orchestrator parses these)

| Sentinel | Producer | Action |
|---|---|---|
| `TRIGGER_CREATE_PR: <KEY>` | monitor_epic | Enqueue `CreatePRTask` |
| `PR_URL: <url>` | create_pr | Record (issue → PR), enqueue `MonitorPRTask` |
| `STATUS: EPIC_POLL_COMPLETE` | monitor_epic | Normal — re-enqueue self |
| `STATUS: PR_OPENED` | create_pr | Normal — used with `PR_URL:` |
| `STATUS: PR_ALREADY_OPEN` | create_pr | Normal — used with `PR_URL:` |
| `STATUS: MERGED` | monitor_pr_full | Mark completed, STOP |
| `STATUS: DECLINED` or `SUPERSEDED` | monitor_pr_full | Drop from active tracking, STOP |
| `STATUS: AWAITING_REVIEWER` | monitor_pr_full | Re-enqueue self |
| `STATUS: ALL_COMMENTS_RESOLVED` | monitor_pr_full | Re-enqueue self |
| `STATUS: FIXED_PUSHED` | monitor_pr_full | Re-enqueue self |
| `STATUS: FLAKE_RETRIGGERED` | monitor_pr_full | Re-enqueue self |
| `STATUS: INFRA_RETRIGGERED` | monitor_pr_full | Re-enqueue self |
| `STATUS: NEEDS_HUMAN -- <reason>` | any | Log; for monitor_pr_full → re-enqueue at slower (30min) cadence |

## Cost notes

Each inferencer call can take 5-30 minutes. With default settings (10min Epic
poll, 5min PR poll, 2 parallel cap), expect:
- Epic with 1 active issue → ~30 inferencer-calls/hour (≈$ depending on
  Rovo Dev pricing — measure empirically before scaling).
- Default `--max-parallel-inferencers 2` keeps the burn rate bounded.

## Reliability semantics (what "constantly monitors" actually means)

The orchestrator guarantees the Epic monitor and per-PR monitors keep running
through transient failures:

- **Normal path**: handler runs → returns a list of follow-up tasks → those
  are enqueued (including a self-re-enqueue with `delay_seconds`).
- **Exception path**: handler raises → worker catches → logs full traceback →
  invokes `_safety_reenqueue_on_error` which re-enqueues `MonitorEpicTask` /
  `MonitorPRTask` at a slowed cadence (≥ 10 min). The loop survives.
- **`CreatePRTask` is intentionally NOT auto-retried** — it's single-shot per
  Jira-issue-transition. If it fails, the next Epic poll will notice the
  issue is still in flight without a linked PR (the prompt's Step 0
  idempotency check handles "PR already partially opened" gracefully).
- **Terminal STATUS values** (`MERGED`, `DECLINED`, `SUPERSEDED`) intentionally
  do NOT re-enqueue — those are end-of-life for that PR's monitor.

## Known limitations

1. **`acli rovodev` must be pre-authenticated.** Script does NOT do OAuth dances.
2. **Inferencer prompt failure modes.** If the inferencer doesn't emit the exact
   sentinel format, the orchestrator skips downstream steps (logged, no retry).
3. **Single-process state.** State file is JSON; not safe for multiple
   concurrent script instances. Run only one at a time.
4. **No conflict-resolution.** If a PR has merge conflicts, the inferencer is
   expected to detect & fix; if it can't, it must emit `STATUS: NEEDS_HUMAN`.
5. **Hard-coded reference paths.** Code/system-understanding paths are
   hard-coded in `tasks.py` (`_CODE_UNDERSTANDING_PATH`,
   `_SYSTEM_UNDERSTANDING_PATH`). Make them args before any real use.
