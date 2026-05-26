# Plan: `--real-sessions` Flag for OpenTeam

> **Author:** Rovo Dev  
> **Date:** 2026-04-06  
> **Status:** Proposal  
> **Reference implementation:** `CoreProjects/atlassian-packages/rankevolve/src/webui/backend/services/session_store_service.py`

---

## 1. Executive Summary

Currently, the OpenTeam sidebar's **"Manager Sessions"** panel renders sessions loaded from a static JSON fixture file (`server/fixtures/manager_sessions.json`). This plan introduces a `--real-sessions` CLI flag that, when passed, replaces the mock session data with **real session data read from disk** — following the proven pattern established by rankevolve's `SessionStoreService`.

The change is **surgically scoped**: only the session data source is swapped. All other data (teams, projects, tasks, employees, conversations, intelligence) continues to serve from mock fixtures. The UI requires **zero changes** — it already consumes sessions via `/api/sessions` and `/api/sessions/:id` and renders whatever data those endpoints return.

---

## 2. Current Architecture (Deep Analysis)

### 2.1 Data Flow — Mock Sessions

```
┌─────────────────────┐     GET /api/sessions      ┌──────────────────────┐
│  Sidebar.js         │ ──────────────────────────► │  session_routes.py   │
│  useApiData('/ses…')│ ◄────────────────────────── │  list_sessions()     │
│  groups by agent    │     { data: [...] }         │                      │
└─────────────────────┘                             └──────────┬───────────┘
                                                               │
                                                    svc.get_sessions()
                                                               │
                                                    ┌──────────▼───────────┐
                                                    │  MockDataService     │
                                                    │  self._sessions      │
                                                    │  (from fixture JSON) │
                                                    └──────────────────────┘
```

### 2.2 Session List API Contract

`GET /api/sessions` returns `{ "data": [...] }` where each item has:

```json
{
  "id": "session-001",
  "title": "Sprint planning for Q1 auth migration",
  "created_at": "2026-03-26T14:22:00Z",
  "updated_at": "2026-03-26T14:45:00Z",
  "message_count": 8,
  "primary_agent": {
    "id": "emp-001",
    "name": "Agent-Alpha"
  }
}
```

**How `primary_agent` is derived:** The helper `_primary_agent_from_messages()` in `data_service.py` scans the messages array for the first message with `role == "assistant"` and extracts `agent_id` + `agent_name`. The Sidebar uses this to group sessions by agent in the left panel.

### 2.3 Session Detail API Contract

`GET /api/sessions/:id` returns `{ "data": { ... } }` — the full session object:

```json
{
  "id": "session-001",
  "title": "Sprint planning for Q1 auth migration",
  "created_at": "2026-03-26T14:22:00Z",
  "updated_at": "2026-03-26T14:45:00Z",
  "messages": [
    {
      "id": "s1-msg-001",
      "role": "manager",
      "content": "Alpha, I need a status check on…",
      "timestamp": "2026-03-26T14:22:00Z"
    },
    {
      "id": "s1-msg-002",
      "role": "assistant",
      "agent_name": "Agent-Alpha",
      "agent_id": "emp-001",
      "content": "Good afternoon. Here's the current…",
      "timestamp": "2026-03-26T14:23:00Z",
      "widgets": [
        {
          "type": "sprint_progress",
          "data": { "sprint": "Sprint 3 of 4", "overall_percent": 85, "tasks": [...] }
        }
      ]
    }
  ]
}
```

**Key fields consumed by `ManagerChatView.js`:**
- `message.role` — determines left-aligned (assistant) vs right-aligned (manager) rendering
- `message.agent_name` — displayed as agent label on assistant messages
- `message.content` — rendered as message body (supports markdown via `whiteSpace: pre-wrap`)
- `message.timestamp` — formatted via `formatTime()` → `toLocaleTimeString`
- `message.widgets` — rendered by `ChatWidgetRenderer` component (supports types: `sprint_progress`, `approval`, `choice`, `task_list`, `project_summary`, `workload_chart`, `task_assignment`)

### 2.4 Widget Types (for reference)

The `ChatWidgetRenderer` component handles these widget types embedded in assistant messages:

| Widget Type | Purpose | Key Data Fields |
|---|---|---|
| `sprint_progress` | Sprint task breakdown | `sprint`, `overall_percent`, `tasks[]` |
| `approval` | Yes/No decision prompt | `question`, `context`, `approve_label`, `reject_label` |
| `choice` | Multi-option selection | `prompt`, `options[]` with `id`, `label`, `description` |
| `task_list` | Task priority list | `title`, `tasks[]` with `title`, `status`, `priority` |
| `project_summary` | Project status card | `name`, `status`, `progress_percent`, `sprint`, `blockers` |
| `workload_chart` | Team utilization | `employees[]` with `utilization_percent`, `status` |
| `task_assignment` | Reassignment proposal | `task_title`, `from`, `to`, `reason` |

### 2.5 Server Startup Chain

```
run.sh
  └─► run_server.py (argparse → sets app.state.mode)
        └─► main.py lifespan()
              └─► if mode == "mock": MockDataService(fixtures_dir)
              └─► app.state.data_service = data_svc
```

### 2.6 DataService Abstraction

`DataService` is an abstract base class with 20+ methods. `MockDataService` implements all of them by loading JSON fixtures at init and building O(1) lookup indices. The session methods are:

```python
# Abstract interface
def get_sessions(self) -> list[dict]: ...
def get_session(self, session_id: str) -> dict | None: ...

# MockDataService implementation
def get_sessions(self):
    # Builds list summaries with message_count + primary_agent derived from messages
    ...

def get_session(self, session_id: str):
    # Returns raw fixture data by ID lookup
    return self._session_idx.get(session_id)
```

---

## 3. Reference: Rankevolve's SessionStoreService

### 3.1 Architecture

Rankevolve uses a **file-based session store** where an external process (the "server") writes `session_state.json` files atomically to disk, and the WebUI backend reads them:

```
<server_dir>/sessions/
  ├── sessions_index.json          (optional fast-path index)
  ├── session-abc_20260401_120000/
  │   └── session_state.json
  ├── session-def_20260401_130000/
  │   └── session_state.json
  └── ...
```

### 3.2 Key Design Patterns (adopted for OpenTeam)

| Pattern | Rankevolve Implementation | OpenTeam Adaptation |
|---|---|---|
| **Directory naming** | `<session_id>_<YYYYMMDD_HHMMSS>` | Same convention |
| **Fast-path index** | `sessions_index.json` for O(1) list | Adopt — write index on session create |
| **Fallback scan** | `_scan_sessions()` iterates directories | Adopt — for when index is missing |
| **Atomic reads** | Server writes via `tmp + os.replace` | Same — readers always see complete files |
| **Service injection** | `app.state.session_store` set in lifespan | Inject via `DataService` subclass instead |
| **Async wrapping** | `asyncio.to_thread(store.method)` | Not needed — `MockDataService` is already sync |
| **Route guarding** | `_get_store()` returns 503 if not available | Not needed — `DataService` always exists |

### 3.3 What We Borrow vs. What We Adapt

**Borrow directly:**
- `SessionStoreService` class structure (init with dir path, `list_sessions`, `get_session_state`, `_find_session_dir`, `_scan_sessions`)
- Directory naming convention (`<id>_<timestamp>`)
- Atomic read safety guarantees
- `sessions_index.json` fast-path

**Adapt for OpenTeam:**
- Rankevolve's `session_state.json` has fields like `info.session_id`, `info.model`, `conversation.messages[]` — we map to OpenTeam's schema (`id`, `title`, `messages[]` with `role`, `content`, `agent_name`, `widgets`)
- We integrate via the existing `DataService` abstraction rather than a separate `app.state.session_store`
- We wrap the service in a `DataService` subclass that inherits `MockDataService` for all non-session methods

---

## 4. Detailed Implementation Plan

### 4.1 File Changes Overview

| File | Change Type | Description |
|---|---|---|
| `run.sh` | Modify | Add `--real-sessions [DIR]` argument |
| `run_server.py` | Modify | Add `--real-sessions` argparse argument, pass to app.state |
| `main.py` | Modify | Check `real_sessions_dir`, instantiate appropriate DataService |
| `services/real_session_service.py` | **New** | `RealSessionService` — reads sessions from disk |
| `services/data_service.py` | Modify | Add `RealSessionDataService(MockDataService)` subclass |
| `fixtures/real_sessions/` | **New** | Sample session directories for testing |

### 4.2 `run.sh` — Add `--real-sessions` Flag

**Location:** `CoreProjects/OpenTeam/src/run.sh`

Add to the argument parser block:

```bash
# In the case statement:
--real-sessions)
  if [[ $# -gt 1 && ! "$2" =~ ^-- ]]; then
    REAL_SESSIONS_DIR="$2"
    shift 2
  else
    REAL_SESSIONS_DIR="$HOME/.openstartup/sessions"
    shift
  fi
  SERVER_EXTRA_ARGS+=("--real-sessions" "$REAL_SESSIONS_DIR")
  ;;
```

Add to the startup banner:

```bash
if [[ -n "${REAL_SESSIONS_DIR:-}" ]]; then
  ok "  Sessions: Real (from $REAL_SESSIONS_DIR)"
fi
```

Update the usage comment header to document the new flag.

### 4.3 `run_server.py` — Accept and Forward the Flag

**Location:** `CoreProjects/OpenTeam/src/server/run_server.py`

```python
parser.add_argument(
    "--real-sessions",
    type=str,
    default=None,
    metavar="DIR",
    help="Enable real session data from DIR (default: mock fixture data)",
)

# After app import:
app.state.real_sessions_dir = args.real_sessions
```

Print in startup info:

```python
if args.real_sessions:
    print(f"  Real Sessions: {args.real_sessions}")
```

### 4.4 `services/real_session_service.py` — New File

**Location:** `CoreProjects/OpenTeam/src/server/services/real_session_service.py`

This is the core new component, modeled after rankevolve's `SessionStoreService` but adapted to output OpenTeam's session schema.

```python
"""RealSessionService — read-only access to session files on disk.

Reads session data from a directory structure:

    <sessions_dir>/
      ├── sessions_index.json                    (optional fast-path)
      ├── <session_id>_<YYYYMMDD_HHMMSS>/
      │   └── session_state.json
      └── ...

Each session_state.json follows the OpenTeam session schema:

    {
      "id": "session-001",
      "title": "Sprint planning for Q1 auth migration",
      "created_at": "2026-03-26T14:22:00Z",
      "updated_at": "2026-03-26T14:45:00Z",
      "messages": [
        {
          "id": "s1-msg-001",
          "role": "manager" | "assistant",
          "content": "...",
          "timestamp": "2026-03-26T14:22:00Z",
          "agent_name": "Agent-Alpha",       // assistant msgs only
          "agent_id": "emp-001",             // assistant msgs only
          "widgets": [...]                   // optional
        }
      ]
    }
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class RealSessionService:
    """Read-only service for session data stored on disk."""

    def __init__(self, sessions_dir: str | Path) -> None:
        self._sessions_dir = Path(sessions_dir)
        if not self._sessions_dir.is_dir():
            logger.warning("Sessions directory does not exist: %s", self._sessions_dir)

    @property
    def sessions_dir(self) -> Path:
        return self._sessions_dir

    def list_sessions(self) -> list[dict[str, Any]]:
        """List all sessions with metadata.

        Prefers sessions_index.json for fast reads.
        Falls back to scanning session directories.
        """
        index_path = self._sessions_dir / "sessions_index.json"
        if index_path.is_file():
            try:
                data = json.loads(index_path.read_text(encoding="utf-8"))
                return data.get("sessions", [])
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to read sessions_index.json: %s", e)

        return self._scan_sessions()

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Read full session data for a given session_id."""
        # Try flat file first: <sessions_dir>/<session_id>.json
        flat_file = self._sessions_dir / f"{session_id}.json"
        if flat_file.is_file():
            try:
                return json.loads(flat_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to read %s: %s", flat_file, e)
                return None

        # Try directory structure: <sessions_dir>/<session_id>_<timestamp>/session_state.json
        session_dir = self._find_session_dir(session_id)
        if session_dir is None:
            return None

        state_file = session_dir / "session_state.json"
        if not state_file.is_file():
            return None

        try:
            return json.loads(state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to read session_state.json for %s: %s", session_id, e)
            return None

    def _find_session_dir(self, session_id: str) -> Path | None:
        """Find the session directory for a session_id.

        Directories are named <session_id>_<YYYYMMDD_HHMMSS>.
        Returns the most recent if multiple match.
        Also checks for exact-name directory (no timestamp suffix).
        """
        if not self._sessions_dir.is_dir():
            return None

        # Exact match first
        exact = self._sessions_dir / session_id
        if exact.is_dir():
            return exact

        # Prefix match with timestamp suffix
        prefix = f"{session_id}_"
        candidates = [
            d for d in self._sessions_dir.iterdir()
            if d.is_dir() and d.name.startswith(prefix)
        ]
        if not candidates:
            return None

        candidates.sort(key=lambda d: d.name, reverse=True)
        return candidates[0]

    def _scan_sessions(self) -> list[dict[str, Any]]:
        """Scan for sessions — supports both flat files and directory structures."""
        if not self._sessions_dir.is_dir():
            return []

        sessions = []

        # Scan .json files directly in sessions_dir
        for json_file in sorted(self._sessions_dir.glob("*.json")):
            if json_file.name == "sessions_index.json":
                continue
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                if isinstance(data, dict) and "id" in data:
                    sessions.append(self._to_summary(data))
            except (json.JSONDecodeError, OSError):
                continue

        # Scan subdirectories for session_state.json
        for subdir in sorted(self._sessions_dir.iterdir()):
            if not subdir.is_dir():
                continue
            state_file = subdir / "session_state.json"
            if not state_file.is_file():
                continue
            try:
                data = json.loads(state_file.read_text(encoding="utf-8"))
                if isinstance(data, dict) and "id" in data:
                    sessions.append(self._to_summary(data))
            except (json.JSONDecodeError, OSError):
                continue

        return sessions

    @staticmethod
    def _to_summary(session: dict[str, Any]) -> dict[str, Any]:
        """Convert a full session dict into a list-view summary."""
        messages = session.get("messages", [])
        primary_agent = {"id": None, "name": "New conversation"}
        for msg in messages:
            if msg.get("role") == "assistant":
                agent_id = msg.get("agent_id")
                agent_name = msg.get("agent_name")
                if agent_id is not None or agent_name is not None:
                    primary_agent = {
                        "id": agent_id,
                        "name": agent_name or str(agent_id) if agent_id else "Assistant",
                    }
                    break

        return {
            "id": session["id"],
            "title": session.get("title", "Untitled"),
            "created_at": session.get("created_at"),
            "updated_at": session.get("updated_at"),
            "message_count": len(messages),
            "primary_agent": primary_agent,
        }
```

**Design decisions:**
1. **Supports two storage layouts** — flat JSON files (`session-001.json`) and directory-based (`session-001_20260401/session_state.json`). This gives flexibility: simple testing with flat files, production-grade with directories.
2. **`_to_summary()` replicates the exact logic** from `_primary_agent_from_messages()` in `data_service.py` — ensuring the Sidebar grouping works identically.
3. **Read-only, no caching** — each request reads from disk, matching rankevolve's pattern. Safe for concurrent access since external writers use atomic writes.

### 4.5 `services/data_service.py` — Add RealSessionDataService

Add a new subclass at the bottom of the file:

```python
class RealSessionDataService(MockDataService):
    """MockDataService with session data overridden by real disk-based sessions.

    Inherits all mock data for teams, projects, tasks, employees, etc.
    Only get_sessions() and get_session() are overridden to read from disk.
    """

    def __init__(self, fixtures_dir: Path, real_sessions_dir: Path) -> None:
        super().__init__(fixtures_dir)
        from server.services.real_session_service import RealSessionService
        self._real_session_svc = RealSessionService(real_sessions_dir)
        logger.info(
            "RealSessionDataService: sessions from %s, all other data from fixtures",
            real_sessions_dir,
        )

    def get_sessions(self) -> list[dict]:
        return self._real_session_svc.list_sessions()

    def get_session(self, session_id: str) -> dict | None:
        return self._real_session_svc.get_session(session_id)
```

**Why subclass `MockDataService`?**
- The user wants *only* sessions to be real — all 18+ other DataService methods (teams, projects, tasks, etc.) should continue serving mock data.
- Inheritance gives us this for free with zero code duplication.
- Future: when more "real" data sources are added, they can override additional methods.

### 4.6 `main.py` — Wire Up in Lifespan

Modify the `lifespan()` function:

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    fixtures_dir = Path(__file__).parent / "fixtures"
    mode = getattr(app.state, "mode", "mock")
    real_sessions_dir = getattr(app.state, "real_sessions_dir", None)

    if mode == "mock":
        if real_sessions_dir:
            from server.services.data_service import RealSessionDataService
            data_svc = RealSessionDataService(fixtures_dir, Path(real_sessions_dir))
            logger.info("Real sessions enabled: %s", real_sessions_dir)
        else:
            data_svc = MockDataService(fixtures_dir)
        intel_svc = MockIntelligenceService(fixtures_dir)
    else:
        raise ValueError(f"Unsupported mode: {mode}. Only 'mock' is implemented.")

    app.state.data_service = data_svc
    app.state.intelligence_service = intel_svc

    logger.info("OpenTeam API started in %s mode", mode)
    yield
    logger.info("OpenTeam API shutting down")
```

**Import note:** `RealSessionDataService` is imported inside the `if` branch to avoid loading `RealSessionService` when not needed.

### 4.7 Sample Session Data — `fixtures/real_sessions/`

Create sample data for testing at `server/fixtures/real_sessions/`:

**Layout option A — flat files (simpler for testing):**

```
fixtures/real_sessions/
  ├── session-real-001.json
  ├── session-real-002.json
  └── session-real-003.json
```

Each file is a complete session following the OpenTeam schema. Example `session-real-001.json`:

```json
{
  "id": "session-real-001",
  "title": "Production deployment review",
  "created_at": "2026-04-05T09:00:00Z",
  "updated_at": "2026-04-05T09:25:00Z",
  "messages": [
    {
      "id": "r1-msg-001",
      "role": "manager",
      "content": "Alpha, walk me through the production deployment plan for tomorrow.",
      "timestamp": "2026-04-05T09:00:00Z"
    },
    {
      "id": "r1-msg-002",
      "role": "assistant",
      "agent_name": "Agent-Alpha",
      "agent_id": "emp-001",
      "content": "The deployment is scheduled for tomorrow at 2am PT...",
      "timestamp": "2026-04-05T09:02:00Z"
    }
  ]
}
```

---

## 5. Usage Examples

```bash
# Default — mock sessions (no change to existing behavior)
./run.sh

# Real sessions from default directory
./run.sh --real-sessions

# Real sessions from custom directory
./run.sh --real-sessions /path/to/my/sessions

# Real sessions from bundled samples (for testing)
./run.sh --real-sessions ./server/fixtures/real_sessions

# Combine with other flags
./run.sh --real-sessions --reload --debug
./run.sh --real-sessions /data/sessions --port 9000

# Server-only with real sessions
./run.sh --server --real-sessions ./server/fixtures/real_sessions

# Direct Python invocation (bypassing run.sh)
python run_server.py --real-sessions ./server/fixtures/real_sessions
```

---

## 6. Data Schema Compatibility Matrix

| Field | Mock Fixture | Real Session File | Sidebar Needs | ChatView Needs |
|---|---|---|---|---|
| `id` | ✅ Required | ✅ Required | ✅ | ✅ |
| `title` | ✅ Required | ✅ Required | ✅ | ✅ |
| `created_at` | ✅ ISO 8601 | ✅ ISO 8601 | ❌ | ❌ |
| `updated_at` | ✅ ISO 8601 | ✅ ISO 8601 | ✅ (relative time) | ❌ |
| `messages` | ✅ Array | ✅ Array | count only | ✅ full |
| `messages[].id` | ✅ | ✅ | ❌ | ✅ (React key) |
| `messages[].role` | ✅ `manager`/`assistant` | ✅ same | ❌ | ✅ |
| `messages[].content` | ✅ | ✅ | ❌ | ✅ |
| `messages[].timestamp` | ✅ ISO 8601 | ✅ ISO 8601 | ❌ | ✅ |
| `messages[].agent_name` | ✅ (assistant only) | ✅ (assistant only) | ❌ | ✅ |
| `messages[].agent_id` | ✅ (assistant only) | ✅ (assistant only) | ❌ | ❌ |
| `messages[].widgets` | ✅ (optional) | ✅ (optional) | ❌ | ✅ |
| `primary_agent` | derived at runtime | derived at runtime | ✅ (grouping) | ❌ |
| `message_count` | derived at runtime | derived at runtime | ✅ (display) | ❌ |

---

## 7. Testing Strategy

### 7.1 Manual Testing Checklist

1. **Default mode unchanged:** `./run.sh` → sidebar shows 4 mock sessions grouped by Agent-Alpha, Agent-Delta, Orchestrator
2. **Real sessions (bundled samples):** `./run.sh --real-sessions ./server/fixtures/real_sessions` → sidebar shows sample real sessions
3. **Real sessions (empty dir):** `./run.sh --real-sessions /tmp/empty` → sidebar shows "No sessions yet"
4. **Real sessions (nonexistent dir):** `./run.sh --real-sessions /nonexistent` → server starts with warning, sidebar shows "No sessions yet"
5. **Session detail click:** Click any real session → ManagerChatView renders messages correctly
6. **Widget rendering:** Verify real sessions with widgets render correctly in ChatView
7. **Hot reload:** Add a new `.json` file to the sessions dir → refresh browser → new session appears

### 7.2 Automated Testing (Future)

```python
# test_real_session_service.py
def test_list_sessions_from_flat_files(tmp_path):
    """Flat .json files in sessions dir are discovered."""

def test_list_sessions_from_directories(tmp_path):
    """session_state.json in subdirectories are discovered."""

def test_list_sessions_prefers_index(tmp_path):
    """sessions_index.json is used when present."""

def test_get_session_flat_file(tmp_path):
    """Get session by ID from flat file."""

def test_get_session_directory(tmp_path):
    """Get session by ID from directory structure."""

def test_get_session_not_found(tmp_path):
    """Returns None for nonexistent session."""

def test_primary_agent_derivation(tmp_path):
    """Primary agent is correctly derived from first assistant message."""

def test_empty_directory(tmp_path):
    """Empty sessions dir returns empty list."""

def test_nonexistent_directory():
    """Nonexistent dir returns empty list with warning."""
```

---

## 8. Risk Assessment & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Large sessions dir causes slow list endpoint | Low | Medium | `sessions_index.json` fast-path; pagination in future |
| Malformed JSON files crash server | Low | High | Every `json.loads()` is wrapped in try/except |
| Race condition: file written while being read | Very Low | Low | External writer uses atomic writes (tmp + rename) |
| User forgets `--real-sessions` and sees mock data | Medium | Low | Startup banner clearly shows "Real Sessions: DIR" |
| Breaking change to session schema | Low | Medium | Schema compatibility matrix (§6) ensures contract is documented |

---

## 9. Future Extensions

1. **Live session updates via WebSocket** — push new messages to the UI in real-time when `session_state.json` changes (use `watchdog` or `inotify`)
2. **Write-back support** — allow the manager to send messages that are written to `session_state.json` (currently read-only)
3. **Session creation** — "New Session" button creates a new `session_state.json` on disk
4. **Mixed mode** — show both mock and real sessions simultaneously (for demo purposes)
5. **`sessions_index.json` auto-generation** — build the index file automatically when sessions are scanned

---

## 10. Implementation Order

| Step | Task | Estimated Effort |
|---|---|---|
| 1 | Create `services/real_session_service.py` | Core logic, ~120 lines |
| 2 | Add `RealSessionDataService` to `data_service.py` | ~15 lines |
| 3 | Modify `main.py` lifespan to check flag | ~10 lines |
| 4 | Add `--real-sessions` to `run_server.py` argparse | ~8 lines |
| 5 | Add `--real-sessions` to `run.sh` | ~15 lines |
| 6 | Create sample data in `fixtures/real_sessions/` | 2-3 JSON files |
| 7 | Manual testing | All 7 checklist items |
