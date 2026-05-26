# rovoteam

A uv workspace monorepo for the **OpenTeam** AI-employee platform and its
internal dependencies.

```
rovoteam/
├── PythonUtils/        # shared low-level utilities (path, io, workflow, …)
├── AgentFoundation/    # inference, prompting, agentic primitives
├── OpenTeam/           # server, MCP, role/task tools, UI
├── pyproject.toml      # uv workspace root
└── uv.lock
```

Each package is independently importable (`python_utils`, `agent_foundation`,
`openteam`) and resolved via `[tool.uv.workspace]`.

## Setup

```bash
# from the repo root
uv sync                     # creates .venv with all 3 packages + dev deps
source .venv/bin/activate
```

After sync, the OpenTeam console scripts (`openteam-task`, `openteam-create-role`,
`openteam-role-setup`, `openteam-project-onboarding`, `openteam-mcp`,
`openteam-server`) are on `$PATH`.

---

## Ready-to-use tools

The following tools are **production-ready and validated end-to-end**:

| Tool | Command | Status |
|---|---|---|
| **Task (plan mode)** | `openteam-task "..." --plan` | **Ready** — produces plan artifacts; tested & recommended |
| **Create Role** | `openteam-create-role "..."` | **Ready** — synthesises AI-employee role documents via BTA |
| **Role Setup** | `openteam-role-setup ./role.md` | **Ready** — decomposes role into skills/tools via nested BTA |

## OpenTeam tools as standalone CLIs

OpenTeam exposes its agent tools through **three equivalent surfaces**, all
backed by the same `executor.execute()` function — zero behavioural drift:

| Surface | When to use |
|---|---|
| **Console script** (`openteam-task …`) | After `uv sync`; everyday CLI use |
| **`python -m` module form** | No install needed; CI / one-off invocation |
| **MCP server** (`openteam-mcp`) | Tool calls from any MCP-aware host |

Every tool is **driven entirely by its `tool.json` schema** — flags defined
there appear automatically in `--help`, in the rovodev TUI slash command, and
in the MCP wrapper. To add a flag, you edit one file.

> Common conventions
> - Quote multi-word `<request>` / `<description>` arguments — they are a single positional.
> - All tools call `openteam.bootstrap.ensure_siblings_on_path()` first, so they
>   work whether invoked from the workspace root, a sibling repo, or anywhere
>   `OPENTEAM_SIBLINGS_ROOT` points to.
> - Outputs land in `./children/` (BTA workspaces) and `./roles/` (role docs) under
>   the user's CWD by default.

### `openteam-task` — run an agent topology on a request

Runs the default `PlanThenImplement` topology with dual-consensus per phase.
Bring-your-own topology via `--agent-config`.

> **Maturity status (2026-05-26)**
>
> | Mode | Status |
> |---|---|
> | **`--plan`** | **Ready.** Produces a plan artifact only; no code is executed. Validated end-to-end — the recommended default. |
> | `--execute` · `--full` (default) · `--confirm` | Under active testing. Code-execution paths, dual-consensus loops, multi-iteration refinement, and resume flows are still being shaken out. |
>
> **Recommendation:** prefer `--plan` for shared / production-bound workflows.

```bash
# ✅ TESTED — planning only (no code execution); the recommended default for now
openteam-task "Refactor the payment service" --plan

# 🚧 UNDER TESTING — full plan-then-implement (default mode if you omit a flag)
openteam-task "Build an auth system with JWT and refresh tokens"

# 🚧 UNDER TESTING — explicit topology + model
openteam-task "Write API docs" --agent-config breakdown-multiflow-plan --model opus

# 🚧 UNDER TESTING — resume a previous workspace
openteam-task "Continue session" --resume ./children/task-2026-05-18-abc123

# module form (no install) — same maturity caveats apply
python -m openteam.server.resources.tools.task "Refactor payments" --plan
```

**Key flags** (full list via `--help`):
- Mutually-exclusive modes: **`--plan`** ✅ tested · `--execute` 🚧 · `--full` (default) 🚧 · `--confirm` 🚧
- `--agent-config NAME` — pick a topology under `task/topologies/`
- `--override key=val` — override topology parameters (repeatable)
- `--model {opus,sonnet,haiku}` — model selector
- `--no-dual` / `--analysis` / `--multi-iter` / `--max-iterations N`
- `--resume DIR` / `--in-place` / `--copy-workspace` / `--initial-plan FILE`

### `openteam-create-role` — synthesise a new AI-employee role

Researches responsibilities, skills, collaboration patterns, success metrics,
and growth paths via Atlassian Rovo knowledge search, then writes a single
self-contained role document.

```bash
openteam-create-role "AI DevOps Engineer specializing in CI/CD and infrastructure automation"

# tune facet decomposition
openteam-create-role "Senior ML Engineer for recommendation systems" --max-facets 10

# control output location
openteam-create-role "Tech Lead — Payments" --output-path ./roles/payments_lead.md
```

### `openteam-role-setup` — wire an existing role into a working agent

Takes a role document (produced by `create-role` or hand-written), decomposes
its responsibilities into required skills + tools, researches missing
capabilities via nested breakdown-then-aggregate, and produces a comprehensive
**Role Setup Report** plus the skill/tool scaffolding.

```bash
openteam-role-setup ./roles/devops_engineer.md

# nested decomposition depth
openteam-role-setup ./roles/ml_engineer.md --max-facets 10 --max-inner-facets 5
```

### Bonus: server + MCP

```bash
openteam-server --port 8000              # FastAPI server (powers the React UI)
openteam-mcp                             # MCP server exposing all 4 tools
```

---

## Ongoing work: rovodev ↔ OpenTeam integration

Two coordinated initiatives are bringing OpenTeam's agent tools and live
topology view directly into the rovodev TUI. Authoritative plans live in
`CoreProjects/OpenTeam/_dev/_plan/` (mirrored copies of design docs).

### 1. Unified tool surface (slash commands · MCP · CLI)

> **Status: design converged (v6, 2026-05-16). Ready for Phase-0 implementation (~30 min).**
> Plans: `openteam_rovodev_integration/openteam-rovodev-integration-INTEGRATED-v6.md`

**Why.** OpenTeam already exposes `task`, `create-role`, `role-setup`, and
`project-onboarding` as a Python API and a React-UI tool. The rovodev TUI has
no way to invoke them; slash commands currently dump raw text after a 5–30
minute silent wait, and the tools have no installable entry points outside
OpenTeam's source tree.

**Shape.** One substrate, three surfaces:

```
                ┌─────────────────────────────────────────────────┐
                │            executor.execute()  (single source)  │
                └─────────────────────────────────────────────────┘
                  ▲              ▲                        ▲
                  │              │                        │
        ┌─────────┴───────┐   ┌──┴──────────────┐   ┌─────┴────────────┐
        │ console script  │   │  MCP tool       │   │ rovodev TUI      │
        │ (openteam-task) │   │ (openteam-mcp)  │   │ /task /role-setup│
        └─────────────────┘   └─────────────────┘   └──────────────────┘
```

**Key deliverables (in flight).**
- 4 console scripts wired in `OpenTeam/pyproject.toml` (`openteam-task`,
  `openteam-create-role`, `openteam-role-setup`, `openteam-project-onboarding`) ✅ shipped.
- `openteam.bootstrap.ensure_siblings_on_path()` — idempotent sys.path injector,
  called by every entry point ✅ shipped.
- MCP server with 4 typed tool wrappers — Phase 2.
- `tool_cli.run_cli()` rendering fix + suffix-discovery for artifact keys — Phase 0a.
- rovodev TUI slash registrar (`/task`, `/create-role`, `/role-setup`,
  `/project-onboarding`) using the existing 64-command registry — Phase 3.

**Critical path.** Phase 0 (rendering + bootstrap + shims) → Phase 1 (root
packaging) → Phase 2 (MCP) → Phase 3 (TUI slash) → Phase 4 (templates).

### 2. Unified frontend session (discovery · auto-launch · attach)

> **Status: design integrated (v5). ~14h focused implementation.**
> Plans: `openteam_rovodev_integration/openteam-unified-frontend-session-INTEGRATED-v5.md`

**Why.** Any frontend (rovodev TUI, web UI, future surfaces) needs to (a)
discover whether an OpenTeam server is running for a given workspace, (b)
auto-launch one if not, and (c) register sessions so per-workspace queries
route to the correct server instance.

**Shape.** Server-as-single-writer model (eliminates index races), plus a
hard split between `openteam.client/` (stdlib + httpx only) and
`openteam.server/` (FastAPI, heavy deps — never imported by clients).

```
~/.openteam/servers/<server_id>.json    ← triple-keyed discovery
       (runtime_root | host | port)
                │
       ┌────────┴────────┐
       │                 │
  client.supervisor    server._register
  (ensure-or-launch)   (write hook on start)
                            │
                            ▼
                /api/sessions/attach
                /api/health  (service: openteam-server)
```

**Mode discipline** via `OPENTEAM_MODE` env var: subprocess shims are
read-only; the TUI/WebUI is the only creator.

**Key deliverables.**
- Discovery file schema + `openteam.client.supervisor` (auto-launch).
- `/api/sessions/attach` endpoint + `/api/health` enrichment.
- ~325 LOC OpenTeam + 85 LOC rovodev TUI; 10+ TIER-1 tests; E2E scenario:
  fresh machine, no server → `/task` auto-launches server → task lands.

### 3. Live topology view in the rovodev TUI

> **Status: architecture settled (round 4); Round-10 post-convergence.**
> Plans: `rovodev_tui_graph_view/rovodev-tui-graph-view-v4.md`

**Why.** Today `/task "…"` in the TUI runs silently for 5–30 minutes then
dumps text. The OpenTeam React UI already shows a live graph of the same
execution — we want parity in the terminal.

**Shape — purely a transport-layer change.** OpenTeam's
`BreakdownThenAggregateInferencer` already emits 4 event types via the
duck-typed `graph_reporter` protocol. We add a **second consumer** alongside
the existing `WebSocketGraphReporter`:

```
BreakdownThenAggregateInferencer
     │ emits: on_graph_topology / on_node_status /
     │        on_graph_reconcile / on_node_stream
     ├─► WebSocketGraphReporter ──► React UI    (existing)
     └─► StdioGraphReporter      ──► fd 3 NDJSON ──► rovodev TUI Tree + RichLog panels (new)
```

Three executor attach-sites (`task`, `project_onboarding`, `mock_task`) get a
~25-LOC factory patch. No `tool_cli` changes, no `session_context` indirection.

**Outcome.** `/task "…"` in the rovodev TUI gets a live, cancellable,
snapshot-testable tree of nodes streaming their content — same data the React
UI sees, rendered with Textual `Tree` + `ContentSwitcher`-of-`RichLog`s.

---

## Repository conventions

- **Source of truth** for the three packages: `~/MyProjects/CoreProjects/{RichPythonUtils,AgentFoundation,OpenStartup}`.
- **Workspace mirror**: `rovoteam/{PythonUtils,AgentFoundation,OpenTeam}` is kept in lock-step;
  imports are rewritten (`rich_python_utils → python_utils`, `RichPythonUtils → PythonUtils`,
  `OpenStartup → OpenTeam`) during sync. Dev-only folders (`_dev/`, `_runtime/`, etc.) are NOT mirrored.
- **Branch model**: `main` is the integrated state; CoreProjects use a parallel
  `dev_xinli_<date>` branch for in-flight work.
- **Testing**: `pytest` from each package root, or `uv run pytest` from the workspace root.

## Further reading

- `OpenTeam/src/openteam/server/resources/tools/<tool>/tool.json` — authoritative schema for each tool.
- `OpenTeam/src/openteam/bootstrap.py` — sibling-repo path resolution rules.
- `CoreProjects/OpenStartup/_dev/_plan/openteam_rovodev_integration/` — full integration design history (v1 → v6).
- `CoreProjects/OpenStartup/_dev/_plan/rovodev_tui_graph_view/` — TUI graph design (v1 → v4).
