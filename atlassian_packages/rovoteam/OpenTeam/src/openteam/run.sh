#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# run.sh — Start both the FastAPI server and React UI for OpenStartup.
#
# Usage:
#   ./run.sh              # Start both server (port 8000) and UI (port 3000)
#   ./run.sh --server     # Start only the backend server
#   ./run.sh --ui         # Start only the React UI
#   ./run.sh --build      # Build the React UI for production, then serve
#   ./run.sh --port 9000           # Use a custom backend port
#   ./run.sh --real-sessions            # Persistent sessions from <project>/_runtime (always new server)
#   ./run.sh --real-sessions /dir       # Persistent sessions from custom runtime root
#   ./run.sh --resume-latest-server     # Resume the most recently created server
#   ./run.sh --resume-server <name>     # Resume a specific server by name (e.g., server_20260406_...)
#   ./run.sh --new-server               # Force a new server (same as default, kept for compatibility)
#   ./run.sh --llm-backend claude_cli   # Default conversation backend (mock|rovodev|claude_cli)
#   ./run.sh --llm-model sonnet         # Default model for the backend factory (claude_cli only)
#
# Requires: python3, node/npm (node_modules installed in src/ui)
# ─────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Resolve script directory (works even when symlinked) ─────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$SCRIPT_DIR/server"
UI_DIR="$SCRIPT_DIR/ui"

# ── Python path for shared libraries ─────────────────────────────────
# Resolve the project root (2 levels up from this script: OpenStartup/)
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CORE_PROJECTS="$(cd "$PROJECT_ROOT/.." && pwd)"

# Add AgentFoundation and RichPythonUtils src/ to PYTHONPATH if they exist
_extra_paths=""
for _lib_src in \
    "$CORE_PROJECTS/AgentFoundation/src" \
    "$CORE_PROJECTS/RichPythonUtils/src" \
    "$PROJECT_ROOT/src"; do
  if [[ -d "$_lib_src" ]]; then
    _extra_paths="${_extra_paths:+$_extra_paths:}$_lib_src"
  fi
done
if [[ -n "$_extra_paths" ]]; then
  export PYTHONPATH="${_extra_paths}${PYTHONPATH:+:$PYTHONPATH}"
fi

# ── Defaults ─────────────────────────────────────────────────────────
PYTHON="${OPENSTARTUP_PYTHON:-/opt/homebrew/anaconda3/bin/python}"
SERVER_PORT=8000
SERVER_HOST="127.0.0.1"
RUN_SERVER=true
RUN_UI=true
BUILD_UI=false
SERVER_EXTRA_ARGS=()

# ── Parse arguments ──────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --server)  RUN_UI=false;    shift ;;
    --ui)      RUN_SERVER=false; shift ;;
    --build)   BUILD_UI=true;    shift ;;
    --port)    SERVER_PORT="$2"; shift 2 ;;
    --host)    SERVER_HOST="$2"; shift 2 ;;
    --reload)  SERVER_EXTRA_ARGS+=("--reload"); shift ;;
    --debug)   SERVER_EXTRA_ARGS+=("--debug");  shift ;;
    --real-sessions)
      if [[ $# -gt 1 && ! "$2" =~ ^-- ]]; then
        REAL_SESSIONS_DIR="$2"
        shift 2
      else
        # Default: _runtime under the project root (2 levels up from openteam/)
        PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
        REAL_SESSIONS_DIR="$PROJECT_ROOT/_runtime"
        shift
      fi
      SERVER_EXTRA_ARGS+=("--real-sessions" "$REAL_SESSIONS_DIR")
      ;;
    --resume-server)
      # Resume a specific named server: --resume-server server_20260406_...
      SERVER_EXTRA_ARGS+=("--resume-server" "$2")
      shift 2
      ;;
    --resume-latest-server)
      # Resume the most recently created server
      SERVER_EXTRA_ARGS+=("--resume-latest-server")
      shift
      ;;
    --new-server)
      # Explicit new server (same as default — kept for backwards compatibility)
      SERVER_EXTRA_ARGS+=("--resume-server" "new")
      shift
      ;;
    --llm-backend)
      SERVER_EXTRA_ARGS+=("--llm-backend" "$2")
      shift 2
      ;;
    --llm-model)
      SERVER_EXTRA_ARGS+=("--llm-model" "$2")
      shift 2
      ;;
    -h|--help)
      sed -n '2,/^# ─\{5,\}$/{ s/^# \?//; p }' "$0"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

# ── Colours (disabled when output is not a terminal) ─────────────────
if [[ -t 1 ]]; then
  CYAN='\033[0;36m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
  RED='\033[0;31m'; NC='\033[0m'
else
  CYAN=''; GREEN=''; YELLOW=''; RED=''; NC=''
fi

log()  { echo -e "${CYAN}[run.sh]${NC} $*"; }
ok()   { echo -e "${GREEN}[run.sh]${NC} $*"; }
warn() { echo -e "${YELLOW}[run.sh]${NC} $*"; }
err()  { echo -e "${RED}[run.sh]${NC} $*" >&2; }

# ── Track child PIDs for cleanup ─────────────────────────────────────
PIDS=()

cleanup() {
  echo ""
  log "Shutting down…"
  for pid in "${PIDS[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  wait 2>/dev/null || true
  ok "All processes stopped."
}

trap cleanup EXIT INT TERM

# ── Kill stale acli/rovodev processes from previous sessions ─────────
# These accumulate when servers are restarted without clean shutdown.
# Only kill processes that are NOT children of the current shell.
_cleanup_stale_acli() {
  local current_ppid=$$
  local killed=0
  while IFS= read -r pid; do
    # Skip if it's a child of current shell
    if [[ "$pid" != "$current_ppid" ]]; then
      if kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null && killed=$((killed+1)) || true
      fi
    fi
  done < <(pgrep -f "acli rovodev\|atlassian_cli_rovodev" 2>/dev/null || true)
  [[ $killed -gt 0 ]] && log "Cleaned up $killed stale acli/rovodev process(es)." || true
}
_cleanup_stale_acli

# ── Pre-flight checks ───────────────────────────────────────────────
if $RUN_SERVER; then
  if [[ ! -x "$PYTHON" ]] && ! command -v "$PYTHON" &>/dev/null; then
    err "Python not found at: $PYTHON"
    err "Set OPENSTARTUP_PYTHON to your Python 3.10+ interpreter."
    exit 1
  fi
  if ! "$PYTHON" -c "import fastapi, uvicorn" 2>/dev/null; then
    warn "Missing Python dependencies. Attempting: pip install fastapi uvicorn"
    "$PYTHON" -m pip install --quiet fastapi uvicorn pydantic || {
      err "Failed to install Python dependencies. Please install them manually:"
      err "  $PYTHON -m pip install fastapi uvicorn pydantic"
      exit 1
    }
  fi
fi

if $RUN_UI; then
  if ! command -v node &>/dev/null; then
    err "node not found. Please install Node.js 16+."
    exit 1
  fi
  if [[ ! -d "$UI_DIR/node_modules" ]]; then
    log "node_modules not found — running npm install…"
    (cd "$UI_DIR" && npm install) || {
      err "npm install failed."
      exit 1
    }
  fi
fi

# ── Start backend server ────────────────────────────────────────────
if $RUN_SERVER; then
  log "Starting FastAPI server on ${SERVER_HOST}:${SERVER_PORT}…"
  (
    cd "$SERVER_DIR" && \
    "$PYTHON" run_server.py \
      --host "$SERVER_HOST" \
      --port "$SERVER_PORT" \
      "${SERVER_EXTRA_ARGS[@]+"${SERVER_EXTRA_ARGS[@]}"}"
  ) &
  PIDS+=($!)
  ok "Server PID: ${PIDS[-1]}"
fi

# ── Start React UI (or build for production) ─────────────────────────
if $RUN_UI; then
  if $BUILD_UI; then
    log "Building React UI for production…"
    (cd "$UI_DIR" && npm run build)
    ok "Production build created at $UI_DIR/build"
    if ! $RUN_SERVER; then
      log "Tip: start the server with --server to serve the built UI."
    fi
  else
    # Tell the CRA dev proxy which backend port to use
    export REACT_APP_BACKEND_PORT="$SERVER_PORT"
    log "Starting React dev server on http://localhost:3000 (proxy → :${SERVER_PORT})…"
    (cd "$UI_DIR" && npm start) &
    PIDS+=($!)
    ok "UI PID: ${PIDS[-1]}"
  fi
fi

# ── Wait for all background processes ────────────────────────────────
if [[ ${#PIDS[@]} -gt 0 ]]; then
  echo ""
  ok "════════════════════════════════════════════════════"
  ok "  OpenStartup is running!"
  if $RUN_UI && ! $BUILD_UI; then
    ok "  UI:     http://localhost:3000"
  fi
  if $RUN_SERVER; then
    ok "  API:    http://${SERVER_HOST}:${SERVER_PORT}"
    ok "  Docs:   http://${SERVER_HOST}:${SERVER_PORT}/docs"
  fi
  if [[ -n "${REAL_SESSIONS_DIR:-}" ]]; then
    ok "  Sessions: Real (from $REAL_SESSIONS_DIR)"
  fi
  ok "  Press Ctrl+C to stop all services."
  ok "════════════════════════════════════════════════════"
  echo ""
  wait
fi
