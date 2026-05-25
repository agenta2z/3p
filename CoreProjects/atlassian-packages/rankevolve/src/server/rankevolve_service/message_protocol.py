# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.

"""Message type constants for the RankEvolve server-client protocol.

Input types (client -> server via input queue):
    CHAT_MESSAGE, SLASH_COMMAND, TASK_CANCEL, AGENT_CONTROL, CONFIG_QUERY, PING

Output types (server -> client via response queue):
    TOKEN_BATCH, STREAM_END, COMMAND_RESPONSE, CONFIG_UPDATE,
    TASK_STATUS, ERROR, PENDING_INPUT, HEARTBEAT, PONG
"""

from __future__ import annotations


# Input message types (client -> server)
CHAT_MESSAGE = "chat_message"
SLASH_COMMAND = "slash_command"
TASK_CANCEL = "task_cancel"
AGENT_CONTROL = "agent_control"
CONFIG_QUERY = "config_query"
PING = "ping"

# Implementation Hub: submission-script setup + run + cancel.
# Setup proxies the SetupWizardModal POST to the agent server's
# tool_executor.setup_submission_script. Run launches the generated script as
# a subprocess via tool_executor.run_submission_script. Cancel-by-id targets
# a specific queued task (used by the JobMonitor "Cancel run" button) and
# cleans up the queue entry — distinct from the legacy TASK_CANCEL which
# generically cancels session.active_task.
SETUP_SUBMISSION = "setup_submission"
RUN_SUBMISSION = "run_submission"
TASK_CANCEL_BY_ID = "task_cancel_by_id"

# Output message types (server -> client)
TOKEN_BATCH = "token_batch"
STREAM_END = "stream_end"
COMMAND_RESPONSE = "command_response"
CONFIG_UPDATE = "config_update"
TASK_STATUS = "task_status"
ERROR = "error"
PENDING_INPUT = "pending_input"
WIDGET_UPDATE = "widget_update"  # Display-only widget update (no input expected)
# Server-confirmed widget approval/submission. Emitted after the server has
# persisted a structured `widget_response` row to the conversation; the client
# uses this to install a transcript-resident "flat" card that survives session
# resume. The client may already have rendered an optimistic version (via the
# clientId field on the original pending_input_response) — the reducer dedupes
# by clientId/id.
WIDGET_RESPONSE_COMMITTED = "widget_response_committed"
HEARTBEAT = "heartbeat"
PONG = "pong"

# Implementation Hub events emitted by the agent server when a setup-script
# generation or submission run reaches a state-change milestone. Consumed by
# WebUI's poll_responses pipeline (single-writer for hub_*_setup.json and
# hub_*_submissions.json — see Section 5/6 of the design doc).
SETUP_COMPLETED = "setup_completed"
SUBMISSION_STATE = "submission_state"

# Input message types for interactive responses (client -> server)
PENDING_INPUT_RESPONSE = "pending_input_response"

# Session sync types (client <-> server)
SESSION_SYNC_REQUEST = "session_sync_request"
SESSION_SYNC_RESPONSE = "session_sync_response"

# Queue status types (client <-> server)
QUEUE_STATUS_REQUEST = "queue_status_request"
QUEUE_STATUS_RESPONSE = "queue_status_response"

# Session notification (server -> client, lightweight change signal)
SESSION_NOTIFICATION = "session_notification"
