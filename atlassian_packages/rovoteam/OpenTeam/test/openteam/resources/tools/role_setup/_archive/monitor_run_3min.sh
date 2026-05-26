#!/usr/bin/env bash
# Poll role_setup resume/full run status every 3 minutes. Logs to MONITOR_LOG (default: workspace/artifacts/monitor_3min.log).
# Usage:
#   ./monitor_run_3min.sh /path/to/workspace
#   WORKSPACE=/path/to/_runtime/20260409_041135 ./monitor_run_3min.sh

set -uo pipefail

WORKSPACE="${1:-${WORKSPACE:-}}"
if [[ -z "${WORKSPACE}" ]]; then
  echo "Usage: $0 /path/to/role_setup/_runtime/<timestamp>" >&2
  exit 1
fi

INTERVAL_SEC="${INTERVAL_SEC:-180}"
MONITOR_LOG="${MONITOR_LOG:-$WORKSPACE/artifacts/monitor_3min.log}"
mkdir -p "$(dirname "$MONITOR_LOG")"

log() {
  # shellcheck disable=SC2320
  printf '%s %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*" | tee -a "$MONITOR_LOG"
}

log "=== monitor_run_3min: workspace=$WORKSPACE interval=${INTERVAL_SEC}s log=$MONITOR_LOG ==="

while true; do
  log "--- tick ---"
  out=$(pgrep -fl "test_role_setup" 2>/dev/null | head -5 || true)
  if [[ -n "$out" ]]; then
    while IFS= read -r line; do log "proc $line"; done <<< "$out"
  else
    log "(no matching test_role_setup process)"
  fi
  out=$(pgrep -fl "acli rovodev run" 2>/dev/null | head -3 || true)
  if [[ -n "$out" ]]; then
    while IFS= read -r line; do log "proc $line"; done <<< "$out"
  else
    log "(no acli rovodev run child)"
  fi
  for f in "$WORKSPACE/artifacts/resume_output.md" "$WORKSPACE/artifacts/summary.json"; do
    if [[ -f "$f" ]]; then
      log "file $(basename "$f"): $(stat -f '%Sm %z bytes' -t '%Y-%m-%d %H:%M:%S' "$f" 2>/dev/null || stat -c '%y %s bytes' "$f" 2>/dev/null)"
    else
      log "missing $f"
    fi
  done
  sess_dir="$WORKSPACE/logs/session"
  if [[ -d "$sess_dir" ]]; then
    latest_session=$(find "$sess_dir" -name '*.jsonl' -type f -print0 2>/dev/null | xargs -0 stat -f '%m %N' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2- || true)
    if [[ -n "${latest_session:-}" ]]; then
      log "newest session log: $latest_session"
    fi
  fi
  sleep "$INTERVAL_SEC"
done
