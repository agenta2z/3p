# Server Discovery & Unified Frontend Session Protocol (v6)

This document describes the on-disk registry format, the HTTP attach
endpoint, and the mode discipline that lets multiple frontends (React
WebUI, RovoDev TUI, future Slack bot, etc.) share one OpenTeam server
in a single coherent session model.

## What problem does this solve?

Before v6, the only way to talk to an OpenTeam server was the React WebUI
hardcoded to `REACT_APP_BACKEND_PORT`. Other frontends had no way to:

1. **Discover** whether a server was running.
2. **Auto-launch** one if it wasn't.
3. **Attach** to a session in the running server (the WebUI's session
   IDs are server-minted and not externally addressable).

v6 closes all three gaps with a single mechanism modeled on the Jupyter
discovery pattern (~10 years of production use).

## The three layers (L1 / L2 / L3)

```
                    ┌─────────────────────────────────────────┐
                    │  Browser tab (React WebUI, JavaScript)  │
                    │   ↓ connects to URL the launcher prints │
                    └─────────────────────────────────────────┘
                                       ▲
┌──────────────────────────┐ ┌─────────┴────────┐ ┌──────────────────────┐
│ RovoDev TUI (Python)     │ │ openteam-webui   │ │ VS Code ext (TS)     │
│ uses L3 directly         │ │ launcher (Py)    │ │ reads L1 JSON +      │
│                          │ │ uses L3 directly │ │ shells out to L2     │
└──────┬───────────────────┘ └──────┬───────────┘ └──────┬───────────────┘
       │                            │                    │
       ▼                            ▼                    ▼
       ┌──────────────────────────────────────────────────────┐
       │  L3: openteam.client.{discovery,supervisor,attach}   │
       │  Python helper library (stdlib + lazy httpx).         │
       │  Used by any Python frontend.                         │
       └────────────────────┬─────────────────────────────────┘
                            │ writes/reads
                            ▼
       ┌──────────────────────────────────────────────────────┐
       │  L1: JSON registry at ~/.openteam/_runtime/registry/  │
       │  Language-agnostic. ANY frontend can read it.         │
       │  Server lifecycle: see L2.                            │
       └──────────────────────────────────────────────────────┘
                            ▲
                            │ starts/stops
       ┌────────────────────┴─────────────────────────────────┐
       │  L2: ``openteam-server`` console script               │
       │  (+ future ``openteam-server stop|status|restart``)   │
       │  Language-agnostic subprocess.                        │
       └──────────────────────────────────────────────────────┘
```

## Registry file format (L1)

Each live server writes ONE JSON file at:

```
~/.openteam/_runtime/registry/server_<id>.json
```

Override the directory with `OPENTEAM_REGISTRY_DIR=<path>` (test isolation,
multi-user systems).

### Schema (v1)

```json
{
  "schema_version": 1,
  "service": "openteam",
  "server_id": "server_3a1b2c4d5e6f",
  "pid": 12345,
  "host": "127.0.0.1",
  "port": 8000,
  "runtime_root": "/Users/alice/projects/openstartup/_runtime",
  "server_dir_name": "server_20260518_001234_a1b2c3d4",
  "started_at": "2026-05-18T00:12:34.567Z",
  "version": "0.1.0",
  "process_command": ["openteam-server", "--port", "8000", "--runtime-root", "..."]
}
```

Field notes:
- **`server_id`**: deterministic, `sha256(runtime_root|host|port)[:12]`. Two
  OpenTeam checkouts on the same machine get distinct ids; one checkout
  with two ports (dev + staging) gets distinct ids.
- **`service`**: literal `"openteam"`. Clients assert both this field AND
  the same field on `GET /api/health` match — defends against a foreign
  process happening to listen on port 8000.
- **`server_dir_name`**: basename only (movable). Full path:
  `Path(runtime_root) / "servers" / server_dir_name`.
- **`schema_version`**: bumps are intentional and CI-gated
  (`test_discovery_schema_immutable.py`). Older clients silently skip
  newer-than-known entries (forward-compat).

### Lifecycle

- Server writes the file atomically (`tempfile.mkstemp` + `os.replace`)
  on startup.
- Server removes the file on graceful shutdown via `atexit` +
  `SIGTERM/SIGINT` handlers.
- Clients reap stale entries (dead PID, corrupt JSON) on every read —
  ungraceful shutdowns self-heal at the cost of one stale-read cycle.

### Atomic launch

Concurrent client launches (e.g., two TUIs starting simultaneously) are
serialised by an `O_EXCL` lock at `~/.openteam/_runtime/registry/.launch.lock`.
After acquiring the lock, the launcher re-checks the registry (another
process may have just registered) before spawning a new server.

## HTTP attach endpoint (L2 / wire contract)

```
POST /api/sessions/attach
Content-Type: application/json

{
  "external_id": "rovodev-<uuid4>",
  "frontend_id": "rovodev",
  "frontend_metadata": {"workspace": "/path/to/repo"},
  "title": "Optional human-readable title"
}
```

Response (200 OK):

```json
{
  "session_id": "rovodev-<uuid4>",
  "session_root": "/abs/path/to/sessions/rovodev-<uuid4>_<TS>",
  "created": true
}
```

- **Idempotent**: same `external_id` always returns the same session
  (`created=false` on subsequent calls).
- **Single writer (I9)**: this is the SOLE HTTP path that creates
  frontend-prefixed sessions. The server is the sole writer; subprocess
  clients (e.g., `openteam-task`) call `get_session` only.

### Validation rules

The `external_id` must match `<prefix>-<remainder>` where:
- `prefix` ∈ `{"rovodev", "webui", "mcp", "session", "slack", "vscode"}`
  (the whitelist is locked by `test_session_store_attach.py`).
- `remainder` matches `^[A-Za-z0-9_.\-]{1,128}$` (rejects path traversal,
  shell metachars, overly long ids).

Invalid IDs → HTTP 400 with explanatory message.

### Mock-mode safety (I18)

When the server is in mock mode (no real session store), the endpoint
returns HTTP 400 `"Session attach not available in mock mode"`. Mirrors
the existing capability check on `POST /api/sessions`.

## Mode discipline (I9 + I15)

A subprocess invoked by a frontend (e.g., `openteam-task` spawned by the
TUI) operates in exactly ONE of two modes, signaled via `OPENTEAM_MODE`:

| Mode | When | Subprocess behavior |
|---|---|---|
| `server` | TUI POSTed `/api/sessions/attach` first | Calls `get_session` only (read-only). Session-missing → FAIL FAST (Invariant I9). |
| `subprocess` | No live server, OR `OPENTEAM_DISABLE_AUTO_LAUNCH=1` | Calls `attach_or_create_session` directly via filesystem. No race because there's only one writer (us). |

The mode is fixed for the lifetime of the slash invocation. The
subprocess MUST NOT switch modes mid-execution — that would re-introduce
the `_update_index` race that I9 was designed to eliminate.

**Failure mode (I9 fail-fast)**: if a Server-Mode subprocess can't find
its session (server crashed mid-task, or `OPENTEAM_SESSION_ID` was
tampered with), it raises `RuntimeError("[I9] OPENTEAM_MODE=server but
session ... missing")` rather than silently creating a second writer.

## Env-var protocol (subprocess receives)

```
OPENTEAM_MODE              "server" | "subprocess"  (required; default "subprocess")
OPENTEAM_SERVER_DIR        absolute path; required in Server Mode, absent in Subprocess Mode
OPENTEAM_SESSION_ID        external session id (e.g. rovodev-<uuid4>); required in Server Mode
OPENTEAM_FRONTEND_ID       frontend tag; defaults to parsed prefix
OPENTEAM_FRONTEND_METADATA JSON object string; optional
```

**Important** (Round-9 M2): when the TUI ends up in Subprocess Mode, it
MUST scrub any inherited `OPENTEAM_SERVER_DIR` / `OPENTEAM_SESSION_ID` /
`OPENTEAM_FRONTEND_ID` / `OPENTEAM_FRONTEND_METADATA` from the spawned
subprocess's env. Without this scrub, a user with `OPENTEAM_SERVER_DIR`
exported in `~/.zshrc` would have it leak into the subprocess, defeating
the "zero regression for Subprocess Mode" guarantee.

## Fork-bomb guard (I17)

When `openteam.client.auto_launch_server` spawns a server, it sets
`OPENTEAM_AUTO_LAUNCH=0` in the spawned process's env. The supervisor's
`ensure_server()` refuses to auto-launch when it sees this guard. This
prevents recursive auto-launch if a future server-side helper ever
imports `openteam.client`.

## Runtime root resolution (I21)

The CLI flag `--runtime-root` does NOT bypass `find_runtime_root()` — it
**sets** `OPENTEAM_RUNTIME_DIR` at parse time, then delegates. One source
of truth: every code path that asks "what's the runtime root?" eventually
reads the env var.

Accepted values:
- `auto` (default) — use the 4-tier fallback chain
- `repo-root` — force walk-up to a `src/` ancestor; fail loudly
- `user-home` — `~/.openteam/_runtime` (pip-install default)
- explicit path (absolute, or relative-to-CWD per Unix convention)

## Single-worker uvicorn (I20)

`run_server.py` must NOT pass `workers=N>1` to `uvicorn.run`. The
server-as-single-writer guarantee (I9) and the FastAPI event-loop
serialisation argument both presuppose ONE process per
`(runtime_root, host, port)` triple. Multi-worker support is POST-4
(requires `fcntl.flock` around `_update_index`).

CI-enforced by `test_no_uvicorn_workers.py`.

## Out of scope (v6 boundaries)

The following are deliberately deferred:

- **`openteam-server stop|status|restart`** subcommands (POST-2).
- **Server idle shutdown** after N minutes of no clients (POST-3).
- **Multi-host federation** — v1 is loopback-only.
- **Authentication** — local-only deployment, out of threat model.
- **Windows-native daemon** — OpenTeam is POSIX-only.
- **`openteam-sdk` PyPI extraction** — the `openteam.client/` split is
  in place; PyPI packaging is for when there are 3+ external consumers.

## Anti-features (will NOT be added even if requested)

- **Auto-stop server when last TUI disconnects.** Breaks the "server is
  up" mental model; React UI users would lose sessions.
- **Global lock at `~/.openteam/global.lock`.** Replaces fine-grained
  per-server discovery with one shared mutex — bad scaling property.
- **Server PID stored in TUI workspace's `.rovodev/`.** Breaks if user
  kills server (TUI keeps trying stale PID); registry-driven discovery
  via `~/.openteam/_runtime/registry/` is self-healing.

## Implementation entry points

| Where | What |
|---|---|
| `src/openteam/client/discovery.py` | `ServerHandle`, `discover_servers`, `find_server`, `compute_server_id`, `pid_alive`, `health_check` |
| `src/openteam/client/supervisor.py` | `ensure_server`, `auto_launch_server`, `NoServerAvailable` |
| `src/openteam/client/attach.py` | `attach_session_via_http`, `AttachResult`, `AttachFailed` |
| `src/openteam/server/_register.py` | `register_server` (write side; imports schema from `openteam.client.discovery`) |
| `src/openteam/server/routes/session_routes.py` | `POST /api/sessions/attach` endpoint |
| `src/openteam/server/routes/health_routes.py` | `service: "openteam"` defensive marker |
| `src/openteam/server/runtime_root.py` | `RuntimeRoot` enum, `apply_runtime_root` |
| `src/openteam/server/services/session_store.py` | `attach_or_create_session`, `validate_external_id`, `_VALID_FRONTEND_PREFIXES` |
| `src/openteam/server/services/frontend_context.py` | Mode-aware env-var → session_context resolver (used by tool_cli + mcp_server) |

## See also

- `docs/MCP_INTEGRATION.md` — MCP wrapper integration notes
- The cli-rovodev-tui side: `rovodev_tui.openteam_session` +
  `rovodev_tui.openteam_discovery` (stdlib-only mirror of L1+L2)
