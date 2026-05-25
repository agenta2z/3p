---
# AgentFoundation agentic freeform config.
#
# Extends the built-in freeform config (inherits all default tools) and
# properly declares ``model_name``, ``max_iterations``, and
# ``max_output_tokens`` as template variables so they are substituted
# into the YAML frontmatter instead of being silently ignored.
#
# Usage (CLI):
#   devmate run fbcode/agent_foundation/.../configs/freeform_agentic \
#       prompt="..." model_name="claude-opus-4.6" max_iterations=200
#
# Usage (Python - DevmateCliInferencer / DevmateSDKInferencer):
#   inferencer = DevmateCliInferencer(
#       config_name=DevmateConfig.AGENT_FOUNDATION_AGENTIC,
#       model_name="claude-opus-4.6",
#   )
#
# @param prompt string The task prompt.
# @param model_name string Model to use (default: claude-opus-4.6).
# @param max_iterations int Max agent iterations (default: 200).
# @param max_output_tokens int Max LLM output tokens (default: 64000).
# @param thinking_budget_tokens int Extended thinking budget (default: 10000).
# @param enable_shell bool Enable shell/command execution (default: true).

extends: 'freeform.md'

orchestrator:
  model_name: ${{ model_name:str = claude-opus-4.6 }}
  # Bumped 200 → 500 for headroom across long dual_inferencer runs.
  # Observed pattern: 4-round impl phase × ~50 iterations per call = 200,
  # which is ZERO headroom at 200. 500 gives 2.5× safety margin.
  # F3's NEW_SESSION_PER_CALL (default for dual_inferencer ctor-sites)
  # resets the counter per call, so this cap binds only for callers using
  # SAME_SESSION_ACROSS_ROUNDS (e.g., chat_cli's long-running flows).
  max_iterations: ${{ max_iterations:int = 500 }}
  # Bumped 60 → 240 minutes — long dual_inferencer runs (4+ rounds with
  # multi-section RST documentation generation) take 1.5+ hours wall-clock
  # cumulative across rounds within a single devmate session.
  max_time_mins: 240
  # Bumped 10M → 50M tokens — sustained long runs with file investigation
  # easily consume >10M cumulative tokens across rounds.
  max_total_tokens: 50000000
  create_commit: false
  backup_commit: false

# ⚠️ CRITICAL: max_output_tokens (below) is the ORCHESTRATOR LLM's output cap.
# It does NOT extend devmate's `edit`/PATCH tool, which routes through a
# SEPARATE patchgen LLM with a HARDCODED max_tokens=8192 cap (in
# devai/config/patchgen.py — NOT configurable from rankevolve or this preset).
#
# Practical implication: a single `edit`/PATCH operation that emits >8192
# output tokens (~5 KB of file content) WILL TRUNCATE MID-CONTENT, leaving
# the orchestrator with an unfinished PATCH and no token budget for the
# closing `</PATCH>` or any structured `<Response>` block. This causes the
# 607-byte template-echo bug class (see forensics_round_template_echo_bug
# in _runtime/.../tasks/_orphans/_archived/).
#
# Mitigation: use the `write_file` tool (below in mcp_servers) for any file
# >5 KB. `write_file` bypasses patchgen entirely — only the orchestrator's
# max_output_tokens applies. Prompts in plan/main/followup.jinja2 +
# implementation/main/followup.jinja2 explicitly steer the model toward
# `write_file` for large content.
#
# See also: docs/dev/issues/devmate/patchgen_max_tokens_8192.md
llm:
  max_output_tokens: ${{ max_output_tokens:int = 64000 }}
  thinking_budget_tokens: ${{ thinking_budget_tokens:int = 10000 }}
  # temperature must be 1 when extended thinking is enabled (Anthropic API requirement)
  temperature: 1

mcp_servers:
  tools:
    # write_file: direct file write with content — NO patchgen LLM call, NO 8192
    # token limit. Use this for creating/overwriting files with large content
    # (e.g., documentation). The content is limited only by max_output_tokens above.
    write_file:
      llm_enabled: true
      config:
        allow_paths_outside_repository: true
    # str_replace_edit: deterministic search/replace — NO patchgen LLM call.
    # Use this for targeted edits instead of the default "edit" tool (which
    # goes through patchgen and is capped at 8192 output tokens).
    str_replace_edit:
      llm_enabled: true
    execute_command:
      tool_name: shell
      llm_enabled: ${{ enable_shell:bool = true }}
      config:
        enable_preapproved_commands: true
        timeout_seconds: 1800
    search_files:
      config:
        allow_paths_outside_repository: true
    # --- Additional tools (not enabled by default in devmate) ---
    # File browsing / discovery
    list_files:
      llm_enabled: true
    read_directory:
      llm_enabled: true
    glob:
      llm_enabled: true
    # NOTE: ``find_file`` is intentionally NOT enabled here — devmate's
    # built-in MCP servers ``www`` and ``mcp-server-devmate`` BOTH expose
    # a tool named ``find_file``, and explicitly enabling it here causes
    # devmate to fail at session-startup with:
    #   ``ValueError: Duplicate tool name find_file found in servers
    #     www and mcp-server-devmate``
    # Use ``glob`` or ``list_files`` for file-discovery; they don't collide.
    create_file:
      llm_enabled: true
    # Code search (semantic)
    search_class:
      llm_enabled: true
    search_method:
      llm_enabled: true
    search_method_in_class:
      llm_enabled: true
    # History / diff
    read_file_history:
      llm_enabled: true
    get_local_changes:
      llm_enabled: true
    # Reasoning / planning
    think:
      llm_enabled: true
    sequential_thinking:
      llm_enabled: true
    write_todo_list:
      llm_enabled: true
    # Batch editing — multiple search/replace in one call, NO patchgen
    str_replace_multi_edits:
      llm_enabled: true
    # Knowledge — load content from URLs, diffs, tasks, SEVs, pastes
    knowledge_load_vsc:
      llm_enabled: true
    # Knowledge — search Meta internal knowledge base
    knowledge_search_vsc:
      llm_enabled: true
---

${{ prompt:str }}
