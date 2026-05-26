# OpenTeam

OpenTeam is a FastAPI backend + React UI for orchestrating multi-agent workflows
(role/skill simulation, project onboarding, task topologies, manager/employee
conversations) on top of the **AgentFoundation** inferencer stack.

The backend can drive conversations through three pluggable inferencer backends:

| Backend     | Description                                                            | Requires                                          |
| ----------- | ---------------------------------------------------------------------- | ------------------------------------------------- |
| `mock`      | Canned responses for UI testing — no external dependencies.            | Nothing.                                          |
| `claude_cli`| Anthropic Claude Code via the `claude` binary.                         | [Claude Code](https://claude.com/claude-code).    |
| `rovodev`   | Atlassian Rovo Dev via the `acli` binary.                              | `acli` on PATH (Atlassian CLI).                   |

---

## Repository layout

This server lives inside the `rovoteam` mirror and depends on two sibling
packages from the same workspace:

```
rovoteam/
├── OpenTeam/                  # ← this project
│   └── src/openteam/
│       ├── run.sh             # Linux/macOS launcher
│       ├── run.ps1            # Windows launcher
│       ├── server/            # FastAPI app
│       └── ui/                # React (CRA) UI
├── AgentFoundation/           # inferencers, tool registry, flow graph
│   └── src/agent_foundation/
└── PythonUtils/               # shared Python utilities
    └── src/python_utils/
```

The launcher scripts also work from the upstream `CoreProjects` layout
(`OpenTeam` + `PythonUtils`) — the path discovery in `run.sh`,
`run.ps1`, and `run_server.py` tries both layouts.

---

## Prerequisites

* **Python 3.10+** with `fastapi`, `uvicorn`, `pydantic` (the launcher will
  `pip install` them on first run if missing).
* **Node.js 16+** with `npm`. The launcher will run `npm install` automatically
  if `ui/node_modules` is missing.
* **Optional**: `claude` and/or `acli` binaries on `PATH` if you want to use
  the `claude_cli` or `rovodev` backends. Without these, `mock` still works.

By default the launcher uses `/opt/homebrew/anaconda3/bin/python`. Override
with the `OPENSTARTUP_PYTHON` env var (kept for backwards compatibility):

```bash
export OPENSTARTUP_PYTHON=/usr/local/bin/python3
```

---

## Quick start (macOS / Linux)

From the OpenTeam project root:

```bash
cd src/openteam
./run.sh
```

This starts:

* FastAPI server on `http://127.0.0.1:8000` (API docs at `/docs`)
* React dev server on `http://localhost:3000` (proxied → `:8000`)

Press `Ctrl+C` to stop both.

### Common flags

```bash
./run.sh --server                  # backend only
./run.sh --ui                      # UI only
./run.sh --build                   # build UI for production (no dev server)
./run.sh --port 9000               # backend port (UI proxy auto-updated)
./run.sh --host 0.0.0.0            # backend bind host
./run.sh --reload                  # backend auto-reload (dev)
./run.sh --debug                   # backend debug logging
./run.sh --llm-backend claude_cli  # default backend (mock | claude_cli | rovodev)
./run.sh --llm-model sonnet        # default model name (claude_cli specific)
```

### Persistent sessions

By default the server runs in fresh-mock mode (no persistence). To persist
session state on disk:

```bash
./run.sh --real-sessions                    # default: <project>/_runtime
./run.sh --real-sessions /path/to/runtime   # custom runtime root
./run.sh --resume-latest-server             # reuse the most recent server dir
./run.sh --resume-server server_20260406_123456_abc   # reuse a specific one
./run.sh --new-server                       # explicit new server (default)
```

A "server" here is a named directory under the runtime root that holds the
session store and on-disk artifacts.

---

## Quick start (Windows)

From the OpenTeam project root:

```powershell
cd src\openteam
.\run.ps1
```

The PowerShell script mirrors `run.sh`. Notable parameter renames:

| Bash flag                  | PowerShell parameter         |
| -------------------------- | ---------------------------- |
| `--host`                   | `-BindHost`                  |
| `--debug`                  | `-DebugMode`                 |
| `--server`                 | `-Server`                    |
| `--ui`                     | `-UI`                        |
| `--build`                  | `-Build`                     |
| `--port`                   | `-Port`                      |
| `--reload`                 | `-Reload`                    |
| `--real-sessions [DIR]`    | `-RealSessions auto` *or* `-RealSessions <path>` |
| `--resume-latest-server`   | `-ResumeLatestServer`        |
| `--resume-server <name>`   | `-ResumeServer <name>`       |
| `--llm-backend <name>`     | `-LlmBackend <name>`         |
| `--llm-model <name>`       | `-LlmModel <name>`           |

Examples:

```powershell
.\run.ps1 -Server -Port 9000 -DebugMode
.\run.ps1 -UI
$env:OPENSTARTUP_PYTHON = "C:\Users\me\miniforge3\python.exe"; .\run.ps1
```

---

## Running the server directly (without the launcher)

If you'd rather call Python directly (for tests, IDE debugging, etc.):

```bash
# From the OpenTeam project root, with sibling packages on PYTHONPATH:
export PYTHONPATH=$PWD/../AgentFoundation/src:$PWD/../PythonUtils/src:$PWD/src
python src/openteam/server/run_server.py --port 8000
```

`run_server.py` also has a fallback that auto-discovers sibling packages from
its own location, so this typically works even without setting `PYTHONPATH`:

```bash
python /Users/tchen7/MyProjects/rovoteam/OpenTeam/src/openteam/server/run_server.py
```

### `run_server.py` flags

```
--host HOST                Bind host (default: 127.0.0.1)
--port PORT                Listen port (default: 8000)
--mode {mock,live}         Server mode (default: mock)
--reload                   Uvicorn auto-reload
--debug                    DEBUG-level logs
--real-sessions DIR        Persist sessions under DIR
--resume-server NAME       Resume server NAME (e.g. server_YYYYMMDD_...)
--resume-latest-server     Resume the most recently created server
--llm-backend NAME         Default backend: mock | claude_cli | rovodev
--llm-model NAME           Default model name (backend-specific)
--list-backends            Print registered backends + availability and exit
```

Inspect what's available:

```bash
python src/openteam/server/run_server.py --list-backends
```

---

## Configuration

### `.env` (optional)

Several tools (`create_role`, `role_setup`, etc.) call `RovoChatInferencer`
which needs Atlassian credentials. Copy the example file and fill in values:

```bash
cp src/openteam/server/.env.example src/openteam/server/.env
```

Pick **one** auth method:

```dotenv
# --- Basic Auth (recommended) ---
ROVOCHAT_EMAIL=your-email@company.com
ROVOCHAT_API_TOKEN=your-atlassian-api-token
ROVOCHAT_BASE_URL=https://your-site.atlassian.net

# --- Or UCT token ---
# ROVOCHAT_UCT_TOKEN=...

# --- Or ASAP credentials ---
# ROVOCHAT_ASAP_ISSUER=...
# ROVOCHAT_ASAP_PRIVATE_KEY=...
# ROVOCHAT_ASAP_KEY_ID=...
```

### Environment variables

| Variable                | Purpose                                                       |
| ----------------------- | ------------------------------------------------------------- |
| `OPENSTARTUP_PYTHON`    | Path to the Python interpreter used by `run.sh` / `run.ps1`.  |
| `OPENTEAM_LLM_BACKEND`  | Default backend (overridden by `--llm-backend`).              |
| `OPENTEAM_LLM_MODEL`    | Default model name (overridden by `--llm-model`).             |
| `REACT_APP_BACKEND_PORT`| Set automatically by `run.sh` so the UI proxies to the right port. |

---

## API surface

Once running, browse:

* `http://127.0.0.1:8000/docs` — interactive Swagger UI
* `http://127.0.0.1:8000/openapi.json` — raw OpenAPI spec

Top-level routers (under `src/openteam/server/routes/`):

* `health_routes` — liveness/readiness
* `conversation_routes` — chat sessions, message streaming
* `session_routes` — session lifecycle
* `dashboard_routes`, `view_routes` — UI views
* `team_routes`, `org_routes`, `employee_routes`, `manager_websocket_routes`
  — org/team modeling
* `role_skill_routes` — role + skill management
* `project_routes`, `task_routes`, `task_topology_routes` — project/task
  orchestration (topologies live in
  `server/resources/tools/task/topologies/`)
* `intelligence_routes`, `meta_routes` — server-side meta APIs

---

## UI

The UI is a Create React App in `src/openteam/ui/`. The launcher proxies
`/api/*` calls to the backend port.

Manual workflow (without the launcher):

```bash
cd src/openteam/ui
npm install      # first time only
npm start        # dev server on :3000
npm run build    # production build → ui/build/
npm test         # CRA test runner
```

---

## Troubleshooting

* **`No module named 'agent_foundation'` / `'python_utils'`** —
  You bypassed the launcher and `PYTHONPATH` isn't set. Either run via
  `./run.sh` / `.\run.ps1`, or export PYTHONPATH manually as shown above.
  `run_server.py`'s fallback should handle this automatically as long as the
  sibling repos are at `../AgentFoundation/src` and `../PythonUtils/src`
  relative to OpenTeam.
* **`Missing Python dependencies`** — the launcher will try
  `pip install fastapi uvicorn pydantic`. If that fails (e.g. read-only
  Python env), install them in your environment manually.
* **`claude_cli` / `rovodev` shows "unavailable"** — install the binary
  (`brew install …` or follow the vendor docs) and re-run
  `--list-backends`. The check uses `shutil.which(...)` so it picks up newly
  installed binaries on subsequent runs.
* **Port already in use** — pass `--port 9001` (the UI dev proxy is updated
  automatically because `run.sh` exports `REACT_APP_BACKEND_PORT`).
* **Stale `acli` / `rovodev` processes** — `run.sh` proactively kills any
  leftover `acli rovodev` processes on startup to keep things clean.
