#!/bin/bash
# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
#
# Quick launcher for the RankEvolve Chat CLI (Python version).
#
# Usage:
#   ./launch.sh                                        # defaults (plugboard, claude-sonnet-4.5)
#   ./launch.sh -m claude-opus-4.1                     # use Opus 4.1
#   ./launch.sh -m claude-sonnet-4.5                   # use Sonnet 4.5
#   ./launch.sh -m claude-haiku-4.5                    # use Haiku 4.5
#   ./launch.sh -m gemini-3-0-pro                      # use Gemini 3.0 Pro
#   ./launch.sh -m gpt-5-2                             # use GPT-5.2
#   ./launch.sh -r /path/to/code                       # override root folder
#
# Dual Agent Options:
#   ./launch.sh --claude-model opus                    # use Opus for dual agent tasks
#   ./launch.sh --use-claude-only                      # bypass Devmate, use Claude for both agents
#   ./launch.sh --base-inferencer claude_code_cli       # use Claude Code CLI as base inferencer
#   ./launch.sh --review-inferencer devmate_cli         # use Devmate CLI as review inferencer
#   ./launch.sh -e plan                                # default to plan-only mode for /task
#   ./launch.sh -o /path/to/output                     # custom output directory for artifacts
#
# Inline /task options (inside the chat):
#   /task --plan <request>                             # run in plan-only mode
#   /task --claude-only <request>                      # use Claude for both agents
#   /task --model opus <request>                       # use Opus model
#   /task --plan --claude-only --model opus <request>  # combine options
#
# Available Plugboard models (as of 2025-02):
#   Claude:  claude-sonnet-4.5, claude-haiku-4.5, claude-opus-4.1
#            claude-opus-4.5, claude-opus-4.6  (auto-routed to 3PAI pipeline)
#   Gemini:  gemini-3-0-pro, gemini-3-0-flash, gemini-2-5-pro
#   GPT:     gpt-5-2, gpt-5-1, gpt-5, gpt-5-2-codex, gpt-5-1-codex
#
# Options:
#   -m, --model              Model name for chat (passed to provider as-is)
#   -p, --provider           plugboard | anthropic | openai
#   -r, --root-folder        Root code folder for dual agent tasks
#   --claude-model           Claude model for dual agent (sonnet, opus, etc.)
#   --use-claude-only        Use Claude for both planner and reviewer agents
#   -e, --execution-mode     Default /task mode: plan, full, confirm, execute
#   -o, --output-dir         Custom output directory for dual agent artifacts
#
# All arguments are forwarded to the CLI.

set -euo pipefail

# Resolve the fbcode root relative to this script's location.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FBCODE_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

# Only auto-set --root-folder if the user didn't pass one.
HAS_ROOT_FOLDER=false
for arg in "$@"; do
  case "$arg" in
    --root-folder|-r) HAS_ROOT_FOLDER=true ;;
  esac
done

if $HAS_ROOT_FOLDER; then
  exec buck2 run fbcode//rankevolve/src/cli/chat_cli:chat_cli -- "$@"
else
  exec buck2 run fbcode//rankevolve/src/cli/chat_cli:chat_cli -- \
    --root-folder "$FBCODE_ROOT" \
    "$@"
fi
