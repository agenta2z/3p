

"""Base configuration for session-aware queue-based services."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BaseServiceConfig:
    """Configuration shared by all session-aware server implementations."""

    session_idle_timeout: int = 1800
    cleanup_check_interval: int = 300
    debug_mode: bool = True
    input_queue_id: str = "user_input"
    response_queue_id: str = "agent_response"
    client_control_queue_id: str = "client_control"
    server_control_queue_id: str = "server_control"
    queue_root_path: str | None = None
    log_root_path: str = "_runtime"
    poll_interval: float = 0.1
    server_dir: str | None = None
