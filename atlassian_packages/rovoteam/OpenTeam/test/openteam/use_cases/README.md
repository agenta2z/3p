# code_optimization SOP — 4-Script Simulation Prototype

This directory simulates the **code_optimization** workflow defined at
`AgentFoundation/src/agent_foundation/resources/prompt_templates/conversation/main/_variables/workflow_sop/code_optimization.md`
by stitching four independent single-shot scripts together, one per SOP phase.

We built this hacky stand-in because the SOP engine itself isn't ready yet —
this lets us demo the full pipeline within a few hours per codebase.

## Phase → Script mapping

| SOP Phase | Script | Sentinel-success token |
|---|---|---|
| Phase 1 — Codebase Investigation | `codebase_investigation/` | `INVESTIGATION_COMPLETE` |
| Phase 2 — System & Signals Investigation | `system_and_signals_investigation/` | `SYSTEM_INVESTIGATION_COMPLETE` |
| Phase 3 — Research, Proposal & Jira Epic Creation | `research_and_propose/` | `EPIC_CREATION_COMPLETE` |
| Phase 4 — Auto-execution (PR creation + monitoring) | `proposal_implementation/` | (long-running; per-task sentinels) |

## Workspace layout (NEW: 2026-05-21)

All four scripts now use a shared per-workstream workspace under
`~/.ai-employee/projects/<workstream-slug>/` (overridable via
`$AI_EMPLOYEE_HOME` env var or `--runtime-root` CLI flag).

```
~/.ai-employee/projects/<workstream-slug>/
├── artifacts/                                         ← DURABLE, LATEST-ONLY
│   ├── codebase_documentation/                        ← Phase 1 final docs
│   ├── system_and_signals_documentation/              ← Phase 2 final docs
│   └── proposals/                                     ← Phase 3 final proposal + audit
└── _runtime/                                          ← FULL HISTORY (debug, ok-to-delete)
    ├── codebase_investigation/run_<ts>_<uuid>/...
    ├── system_and_signals_investigation/run_<ts>_<uuid>/...
    ├── research_and_propose/run_<ts>_<uuid>/...
    └── proposal_implementation/run_<ts>_<uuid>/...
```

Each successful run **promotes** its `docs/` into `artifacts/<phase-folder>/`
(wiping the previous copy). `_runtime/` accumulates a full per-run debug
trail (`prompt.md` + `stream.log` + `clean_output.md` + `_meta.json` for
every inferencer call).

### Workstream slug

The slug is derived from the codebase basename (kebab-case-lowercase). E.g.
`/Users/foo/MyProjects/atlassian_packages/conversational-ai-platform`
→ slug `conversational-ai-platform`. Override with `--workstream-slug`.

### Override hierarchy for the workspace root

1. **`--runtime-root <path>`** CLI flag (most specific)
2. **`AI_EMPLOYEE_HOME`** environment variable
3. **`~/.ai-employee`** (default)

For script 4 only, the legacy `--runtime-base-dir` flag also still works
and takes absolute precedence over the new resolution chain.

## Run order

```bash
# Set up PYTHONPATH once (same for every script)
export PYTHONPATH=test:\
/Users/tchen7/MyProjects/CoreProjects/AgentFoundation/src:\
/Users/tchen7/MyProjects/CoreProjects/PythonUtils/src:\
/Users/tchen7/MyProjects/CoreProjects/ScienceModelingTools/src:\
/Users/tchen7/MyProjects/CoreProjects/SciencePythonUtils/src
cd /Users/tchen7/MyProjects/CoreProjects/OpenTeam

CODEBASE=/Users/tchen7/MyProjects/atlassian_packages/conversational-ai-platform

# Phase 1: codebase static analysis (~15-30 min)
python -m openteam.use_cases.codebase_investigation.run --codebase $CODEBASE

# Phase 2: system & ops signals (auto-finds Phase-1 artifacts) (~15-30 min)
python -m openteam.use_cases.system_and_signals_investigation.run --codebase $CODEBASE

# Phase 3: proposal + Jira Epic + child issues (auto-finds Phase 1+2 artifacts)
python -m openteam.use_cases.research_and_propose.run --codebase $CODEBASE

# Phase 4: assign 1+ child issues to yourself, then start the orchestrator.
# --codebase is the canonical flag (--workspace still accepted as alias).
python -m openteam.use_cases.proposal_implementation.run \
    --epic https://hello.atlassian.net/browse/<EPIC_KEY> \
    --assignee-account-id <YOUR_AAID> \
    --assignee-hint "<Your Name>" \
    --codebase $CODEBASE
```

After each phase succeeds you can inspect the final outputs at:
```
~/.ai-employee/projects/conversational-ai-platform/artifacts/codebase_documentation/
~/.ai-employee/projects/conversational-ai-platform/artifacts/system_and_signals_documentation/
~/.ai-employee/projects/conversational-ai-platform/artifacts/proposals/
```

## Design choices (deliberately hacky for prototyping)

| Decision | Rationale |
|---|---|
| **Only one required param (`--codebase`)** for scripts 1-3 | Per explicit requirement |
| **`artifacts/` keeps latest only** | No history clutter for humans / Phase-2/3 consumers |
| **`_runtime/` keeps full history** | Full debuggability without polluting artifacts/ |
| **Sentinel-based completion contract** | `STATUS: <PHASE>_COMPLETE` (orchestrator-parseable, simple) |
| **Per-run workspace** under `_runtime/<script>/run_<ts>/call_01_<phase>/` | `prompt.md` + `stream.log` + `clean_output.md` + per-call meta |
| **Auto-discovery between phases** | Phase 2 reads Phase 1 artifacts; Phase 3 reads both |
| **Backward-compat fallback** | `autodiscover_phase_artifacts` also looks in legacy in-package `_runtime/` |
| **Only AgentFoundation's `RovoDevCliInferencer`** | No additional orchestration glue |
| **NO confirmation gates** in prompts | Phase-1b/2b/3b user-review gates skipped — orchestrator-parseable sentinels only |

## Privacy + format rules baked into the prompts

| Constraint | Where enforced |
|---|---|
| Phase 1 + 2: read-only on the codebase | Prompt "Hard constraints" |
| Phase 3: no local filesystem paths in Jira | Step 3 "Privacy + format rules (HARD)" |
| Phase 3: no internal infra codenames in Jira | Step 3 |
| Phase 3: no credentials / tokens in any output | Step 3 |
| Phase 3: estimate vocabulary is "human engineer-weeks" | Step 2 EFFORT field |
| Phase 3: explicit priority calibration (no default-Minor) | Step 4 rubric |
| Phase 3: post-creation privacy audit pass | Step 6 |
| Phase 4: WHY/WHAT/IMPACT/TEST/ROLLBACK/DoD PR body | `proposal_implementation/prompts/create_pr.md` |

## What this prototype proves

1. The 4 phases of code_optimization CAN be composed end-to-end.
2. Each phase's output is in the right shape for the next phase to consume
   (artifacts/<phase-folder>/ pattern + auto-discovery).
3. Phase 4 is fully autonomous once a human transitions an issue to the
   "assigned to me" state (proven in the 10h test run on 2026-05-20).

## What this prototype does NOT do

- Phase-1b / Phase-2b "user review gates" (skipped intentionally — the
  prompt's `STATUS:` sentinel is the only contract).
- Phase-3b "review proposal tool" (skipped — Epic creation is direct).
- Phase 0 path-clarification UX (skipped — `--codebase` is the only input).
- Distributed execution / multi-node concurrency.
- Robust failure recovery between phases (each script is a fresh run; if
  Phase 2 fails, you just re-run it).

## Migration notes (2026-05-21)

If you have runs from before the workspace migration:

| Old location | New location |
|---|---|
| `test/openteam/use_cases/<script>/_runtime/run_*/docs/` | `~/.ai-employee/projects/<workstream>/_runtime/<script>/run_*/call_01_*/docs/` |
| `test/openteam/use_cases/<script>/_runtime/run_*/call_01_*/docs/` | (same as above) |

**Auto-discovery is fully backward-compatible** — `autodiscover_phase_artifacts`
falls back to the old in-package `_runtime/` locations when the new ones are
empty, so existing Phase-1 runs are still found by Phase 2/3 without
manual migration.

To preserve a legacy run as a "blessed" artifact, copy it manually:
```bash
mkdir -p ~/.ai-employee/projects/<workstream>/artifacts/codebase_documentation
cp -r test/openteam/use_cases/codebase_investigation/_runtime/run_<ts>/call_01_codebase/docs/* \
      ~/.ai-employee/projects/<workstream>/artifacts/codebase_documentation/
```
