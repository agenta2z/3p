#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# test_role_setup.sh
#
# End-to-end live-LLM smoke-test launcher for the role_setup tool CLI.
#
# Purpose:
#   - Generic, portable script that runs on any developer's machine.
#   - Auto-discovers Python interpreter, repo layout, and credentials.
#   - Launches the role_setup CLI with a user-supplied role document path.
#   - Streams output to a timestamped log in the repo root (or override).
#
# Usage:
#   ./test_role_setup.sh ./roles/devops_engineer.md
#   ./test_role_setup.sh --max-facets 5 --max-inner-facets 3 ./roles/ml_engineer.md
#   ./test_role_setup.sh --background ./roles/product_manager.md
#
# Options (before the positional ROLE_DOCUMENT_PATH):
#   --max-facets N             Max outer skill/tool subtasks (default 3)
#   --max-inner-facets N       Max inner research subtasks per skill (default 2)
#   --background               Launch in background (nohup) and exit immediately
#   --log-dir DIR              Directory for log file (default: repo root)
#   --python PATH              Explicit Python interpreter path (overrides auto-discovery)
#   --help                     Show this help and exit
#
# Credentials:
#   Required env vars: ROVOCHAT_EMAIL, ROVOCHAT_API_TOKEN
#   Auto-derived from JIRA_EMAIL / JIRA_API_TOKEN if available
#   Checked from (in order): current env, ~/.zshrc, ~/.bashrc, ~/.env, ./.env
#   If unset, script prompts user to provide them.
#
# Exit codes:
#   0 = launched successfully (or completed if foreground)
#   1 = missing dependencies / credentials / arguments
#   2 = launch failed
# ---------------------------------------------------------------------------

set -euo pipefail

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------
readonly SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
readonly SCRIPT_DIR="$(dirname "${SCRIPT_PATH}")"
readonly TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

# -----------------------------------------------------------------------------
# Color output (only if tty)
# -----------------------------------------------------------------------------
if [ -t 1 ]; then
    readonly RED='\033[0;31m'
    readonly GREEN='\033[0;32m'
    readonly YELLOW='\033[1;33m'
    readonly BLUE='\033[0;34m'
    readonly BOLD='\033[1m'
    readonly NC='\033[0m'
else
    readonly RED='' GREEN='' YELLOW='' BLUE='' BOLD='' NC=''
fi

log_info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()      { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC}  $*" >&2; }
log_error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }
die()         { log_error "$@"; exit 1; }

# -----------------------------------------------------------------------------
# Help
# -----------------------------------------------------------------------------
show_help() {
    # Print only the top doc-block (everything between first "# ---" line
    # and the FIRST closing "# ---" line, exclusive).
    awk '
        /^# ----/ {
            count++
            if (count == 1) { in_block=1; next }
            if (count == 2) { exit }
        }
        in_block && /^# / { sub(/^# ?/, ""); print }
    ' "${SCRIPT_PATH}"
    exit 0
}

# -----------------------------------------------------------------------------
# Argument parsing
# -----------------------------------------------------------------------------
MAX_FACETS=3
MAX_INNER_FACETS=2
BACKGROUND=0
LOG_DIR=""
PYTHON_BIN=""
ROLE_DOCUMENT_PATH=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --max-facets)        MAX_FACETS="$2"; shift 2 ;;
        --max-inner-facets)  MAX_INNER_FACETS="$2"; shift 2 ;;
        --background)        BACKGROUND=1; shift ;;
        --log-dir)           LOG_DIR="$2"; shift 2 ;;
        --python)            PYTHON_BIN="$2"; shift 2 ;;
        --help|-h)           show_help ;;
        --*)                 die "Unknown option: $1 (use --help for usage)" ;;
        *)
            if [ -z "${ROLE_DOCUMENT_PATH}" ]; then
                ROLE_DOCUMENT_PATH="$1"
            else
                die "Multiple positional arguments. Provide only one role document path."
            fi
            shift
            ;;
    esac
done

if [ -z "${ROLE_DOCUMENT_PATH}" ]; then
    die "Missing role document path.

Usage:
  $0 [OPTIONS] <role_document_path>

Examples:
  $0 ./roles/devops_engineer.md
  $0 --max-facets 5 --max-inner-facets 3 ./roles/ml_engineer.md
  $0 --background ./roles/product_manager.md

Run $0 --help for full option list."
fi

if [ ! -f "${ROLE_DOCUMENT_PATH}" ]; then
    die "Role document path does not exist or is not a file: ${ROLE_DOCUMENT_PATH}"
fi

# Resolve to absolute path so the CLI sees an unambiguous location
ROLE_DOCUMENT_PATH="$(cd "$(dirname "${ROLE_DOCUMENT_PATH}")" && pwd)/$(basename "${ROLE_DOCUMENT_PATH}")"

# -----------------------------------------------------------------------------
# Step 1: Discover OpenStartup repo root
#
# Strategy: walk up from script location until we find a dir containing
# both `src/openteam/` and `test/openteam/`, which is the OpenStartup root.
# -----------------------------------------------------------------------------
log_info "Discovering OpenStartup repo root..."

discover_repo_root() {
    local cur="${SCRIPT_DIR}"
    while [ "${cur}" != "/" ]; do
        if [ -d "${cur}/src/openteam" ] && [ -d "${cur}/test/openteam" ]; then
            echo "${cur}"
            return 0
        fi
        cur="$(dirname "${cur}")"
    done
    return 1
}

REPO_ROOT="$(discover_repo_root)" || die "Could not find OpenStartup repo root (no parent with src/openteam + test/openteam)"
log_ok "Repo root: ${REPO_ROOT}"

# -----------------------------------------------------------------------------
# Step 2: Discover sibling repos (AgentFoundation, RichPythonUtils, OpenTeam)
#
# Try common layouts:
#   <CoreProjects>/AgentFoundation/src    (same parent dir as OpenStartup)
#   <CoreProjects>/RichPythonUtils/src
#   <CoreProjects>/../rovoteam/OpenTeam/src
# -----------------------------------------------------------------------------
log_info "Discovering sibling repos for PYTHONPATH..."

CORE_PROJECTS_DIR="$(dirname "${REPO_ROOT}")"  # e.g., .../CoreProjects
PYTHONPATH_PARTS=("${REPO_ROOT}/src")

# AgentFoundation
if [ -d "${CORE_PROJECTS_DIR}/AgentFoundation/src" ]; then
    PYTHONPATH_PARTS+=("${CORE_PROJECTS_DIR}/AgentFoundation/src")
    log_ok "  AgentFoundation found: ${CORE_PROJECTS_DIR}/AgentFoundation/src"
else
    log_warn "  AgentFoundation/src not found at expected sibling location"
fi

# RichPythonUtils
if [ -d "${CORE_PROJECTS_DIR}/RichPythonUtils/src" ]; then
    PYTHONPATH_PARTS+=("${CORE_PROJECTS_DIR}/RichPythonUtils/src")
    log_ok "  RichPythonUtils found: ${CORE_PROJECTS_DIR}/RichPythonUtils/src"
else
    log_warn "  RichPythonUtils/src not found at expected sibling location"
fi

# OpenTeam (one level up from CoreProjects, under rovoteam/)
PARENT_DIR="$(dirname "${CORE_PROJECTS_DIR}")"
if [ -d "${PARENT_DIR}/rovoteam/OpenTeam/src" ]; then
    PYTHONPATH_PARTS+=("${PARENT_DIR}/rovoteam/OpenTeam/src")
    log_ok "  OpenTeam found: ${PARENT_DIR}/rovoteam/OpenTeam/src"
elif [ -d "${CORE_PROJECTS_DIR}/OpenTeam/src" ]; then
    PYTHONPATH_PARTS+=("${CORE_PROJECTS_DIR}/OpenTeam/src")
    log_ok "  OpenTeam found: ${CORE_PROJECTS_DIR}/OpenTeam/src"
else
    log_warn "  OpenTeam/src not found in common locations"
fi

# Build PYTHONPATH (preserve any existing entries)
NEW_PYTHONPATH="$(IFS=:; echo "${PYTHONPATH_PARTS[*]}")"
if [ -n "${PYTHONPATH:-}" ]; then
    NEW_PYTHONPATH="${NEW_PYTHONPATH}:${PYTHONPATH}"
fi
export PYTHONPATH="${NEW_PYTHONPATH}"

# -----------------------------------------------------------------------------
# Step 3: Discover Python interpreter
#
# Priority:
#   1. --python flag
#   2. PYTHON env var
#   3. /opt/homebrew/anaconda3/bin/python  (macOS arm64 Anaconda)
#   4. /usr/local/anaconda3/bin/python      (macOS intel Anaconda)
#   5. python3.11 / python3.10 / python3    (system)
#   6. python                                (last resort)
# -----------------------------------------------------------------------------
log_info "Discovering Python interpreter..."

discover_python() {
    if [ -n "${PYTHON_BIN}" ] && [ -x "${PYTHON_BIN}" ]; then
        echo "${PYTHON_BIN}"; return 0
    fi
    if [ -n "${PYTHON:-}" ] && command -v "${PYTHON}" >/dev/null 2>&1; then
        command -v "${PYTHON}"; return 0
    fi
    local candidates=(
        "/opt/homebrew/anaconda3/bin/python"
        "/usr/local/anaconda3/bin/python"
        "/opt/homebrew/bin/python3.11"
        "/usr/local/bin/python3.11"
        "python3.11"
        "python3.10"
        "python3"
        "python"
    )
    for cand in "${candidates[@]}"; do
        if [ -x "${cand}" ]; then echo "${cand}"; return 0; fi
        if command -v "${cand}" >/dev/null 2>&1; then command -v "${cand}"; return 0; fi
    done
    return 1
}

PYTHON_BIN="$(discover_python)" || die "No Python interpreter found. Install Python 3.10+ or specify --python <path>."
PY_VERSION="$(${PYTHON_BIN} -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")')"
log_ok "Python: ${PYTHON_BIN} (v${PY_VERSION})"

# -----------------------------------------------------------------------------
# Step 4: Resolve credentials
#
# Resolution order for ROVOCHAT_EMAIL / ROVOCHAT_API_TOKEN:
#   1. Already set in environment
#   2. Derive from JIRA_EMAIL / JIRA_API_TOKEN in current env
#   3. Source from common rc files if they define the vars
#   4. Source from .env files (./.env, ~/.env, <repo>/.env)
#   5. Prompt user
# -----------------------------------------------------------------------------
log_info "Resolving RovoChat credentials..."

# Helper: try to extract VAR=value from a file (handles export VAR=value too)
extract_var_from_file() {
    local var="$1" file="$2"
    [ -f "${file}" ] || return 1
    grep -E "^(export[[:space:]]+)?${var}=" "${file}" 2>/dev/null | tail -1 | \
        sed -E "s/^(export[[:space:]]+)?${var}=//; s/^['\"]//; s/['\"]\$//" | head -1
}

resolve_cred() {
    local primary="$1" fallback="$2"  # e.g. ROVOCHAT_EMAIL, JIRA_EMAIL

    # 1. Already in env?
    if [ -n "${!primary:-}" ]; then
        log_ok "  ${primary} already set in env"
        return 0
    fi

    # 2. Fallback var already in env?
    if [ -n "${!fallback:-}" ]; then
        export "${primary}=${!fallback}"
        log_ok "  ${primary} derived from ${fallback} (env)"
        return 0
    fi

    # 3. Search rc files for either primary or fallback
    local rc_files=(
        "${HOME}/.zshrc"
        "${HOME}/.bashrc"
        "${HOME}/.bash_profile"
        "${HOME}/.profile"
        "${HOME}/.env"
        "${REPO_ROOT}/.env"
        "$(pwd)/.env"
    )
    for rc in "${rc_files[@]}"; do
        local val
        val="$(extract_var_from_file "${primary}" "${rc}" 2>/dev/null || true)"
        if [ -n "${val}" ]; then
            export "${primary}=${val}"
            log_ok "  ${primary} loaded from ${rc}"
            return 0
        fi
        val="$(extract_var_from_file "${fallback}" "${rc}" 2>/dev/null || true)"
        if [ -n "${val}" ]; then
            export "${primary}=${val}"
            log_ok "  ${primary} derived from ${fallback} in ${rc}"
            return 0
        fi
    done

    return 1
}

if ! resolve_cred "ROVOCHAT_EMAIL" "JIRA_EMAIL"; then
    log_warn "ROVOCHAT_EMAIL not found in any env source"
    read -r -p "  Enter ROVOCHAT_EMAIL (or your Atlassian/Jira email): " ROVOCHAT_EMAIL
    [ -n "${ROVOCHAT_EMAIL}" ] || die "Email is required"
    export ROVOCHAT_EMAIL
fi

if ! resolve_cred "ROVOCHAT_API_TOKEN" "JIRA_API_TOKEN"; then
    log_warn "ROVOCHAT_API_TOKEN not found in any env source"
    echo "  Generate one at: https://id.atlassian.com/manage-profile/security/api-tokens"
    read -r -s -p "  Enter ROVOCHAT_API_TOKEN: " ROVOCHAT_API_TOKEN
    echo
    [ -n "${ROVOCHAT_API_TOKEN}" ] || die "API token is required"
    export ROVOCHAT_API_TOKEN
fi

# -----------------------------------------------------------------------------
# Step 5: Resolve log file (output goes into workspace, not a tmp path)
# -----------------------------------------------------------------------------
# Per 2026-05-18 surfacing fix, role_setup writes its deliverable under:
#   <workspace>/outputs/final_deliverables/role_setup_output.md
# where <workspace> = <REPO_ROOT>/_runtime/tasks/role_setup/role_setup_<TS>_<UUID>/
if [ -z "${LOG_DIR}" ]; then
    LOG_DIR="${REPO_ROOT}"
fi
mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/role_setup_${TIMESTAMP}.log"

log_ok "Log file:    ${LOG_FILE}"
log_ok "Workspace:   ${REPO_ROOT}/_runtime/tasks/role_setup/role_setup_<TS>_<UUID>/"
log_ok "Deliverable: <workspace>/outputs/final_deliverables/role_setup_output.md"

# -----------------------------------------------------------------------------
# Step 6: Sanity check role_setup module is importable
# -----------------------------------------------------------------------------
log_info "Verifying role_setup module is importable..."

if ! ${PYTHON_BIN} -c "import openteam.server.resources.tools.role_setup" >/dev/null 2>&1; then
    log_error "Cannot import openteam.server.resources.tools.role_setup"
    log_error "PYTHONPATH: ${PYTHONPATH}"
    ${PYTHON_BIN} -c "import openteam.server.resources.tools.role_setup" 2>&1 | tail -5
    die "Module import failed - check PYTHONPATH or install missing dependencies"
fi
log_ok "Module importable"

# -----------------------------------------------------------------------------
# Step 7: Display launch summary
# -----------------------------------------------------------------------------
echo
echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  role_setup test launch — ${TIMESTAMP}${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo "  Role document:     ${ROLE_DOCUMENT_PATH}"
echo "  Max facets:        ${MAX_FACETS}"
echo "  Max inner facets:  ${MAX_INNER_FACETS}"
echo "  Log file:          ${LOG_FILE}"
echo "  Python:            ${PYTHON_BIN}"
echo "  Repo root:         ${REPO_ROOT}"
echo "  Mode:              $([ ${BACKGROUND} -eq 1 ] && echo 'background (nohup)' || echo 'foreground')"
echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo

# -----------------------------------------------------------------------------
# Step 8: Launch
# -----------------------------------------------------------------------------
export OPENTEAM_RUNTIME_DIR="${REPO_ROOT}/_runtime"
cd "${REPO_ROOT}"

CMD=(
    "${PYTHON_BIN}"
    -m openteam.server.resources.tools.role_setup
    --max-facets "${MAX_FACETS}"
    --max-inner-facets "${MAX_INNER_FACETS}"
    "${ROLE_DOCUMENT_PATH}"
)

if [ ${BACKGROUND} -eq 1 ]; then
    nohup "${CMD[@]}" > "${LOG_FILE}" 2>&1 &
    PID=$!
    sleep 2
    if kill -0 "${PID}" 2>/dev/null; then
        log_ok "Launched in background. PID=${PID}"
        echo
        echo "Monitor progress:"
        echo "  tail -f ${LOG_FILE}"
        echo
        echo "Check status:"
        echo "  ps -p ${PID}"
        echo
        echo "When complete, find workspace under:"
        echo "  ${REPO_ROOT}/_runtime/tasks/role_setup/role_setup_${TIMESTAMP}_*"
        exit 0
    else
        log_error "Background process exited immediately. Check log:"
        tail -20 "${LOG_FILE}"
        exit 2
    fi
else
    log_info "Launching foreground (output streamed below + to log)..."
    echo
    # tee to capture output to log while still showing to user
    if "${CMD[@]}" 2>&1 | tee "${LOG_FILE}"; then
        echo
        log_ok "Run completed successfully"
        log_ok "Log: ${LOG_FILE}"
        log_ok "Deliverable: see <workspace>/outputs/final_deliverables/role_setup_output.md"
        log_ok "  (workspace path is printed early in the log; grep for 'workspace')"
        exit 0
    else
        echo
        log_error "Run failed (see ${LOG_FILE})"
        exit 2
    fi
fi
