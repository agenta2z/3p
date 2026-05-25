# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.

"""Queue lifecycle management for session-aware services."""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from rankevolve.src.utils.service_utils.queue_service.storage_based_queue_service import (
    StorageBasedQueueService,
)


class QueueManager:
    """Manages queue directory lifecycle and StorageBasedQueueService instantiation.

    Creates a server directory under _runtime/servers/ with a timestamped name
    and UUID suffix for uniqueness. The queue service operates within the
    server directory's queues/ subdirectory.

    Folder layout created/expected:
        _runtime/servers/server_<YYYYMMDD_HHMMSS>_<uuid8>/
            queues/          <-- StorageBasedQueueService root
            sessions/        <-- Per-session state & logs (persist across runs)
                <session>/
                    tasks/   <-- Per-session task workspaces (persist across runs)
            logs/
                runs/        <-- Per-run global logs (new each server restart)
    """

    def __init__(self, runtime_root: str | None = None) -> None:
        self._runtime_root = (
            Path(runtime_root) if runtime_root else Path("rankevolve/_runtime")
        )
        self._queue_service: StorageBasedQueueService | None = None
        self._queue_root: Path | None = None
        self._server_dir: Path | None = None
        self._run_log_dir: Path | None = None

    def initialize(self, server_dir: str | None = None) -> StorageBasedQueueService:
        """Create or open a server directory and instantiate queue service.

        Args:
            server_dir: Path to an existing server directory (for resume).
                        If None, creates a new timestamped server directory.
        """
        if server_dir:
            self._server_dir = Path(server_dir)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            short_uuid = uuid.uuid4().hex[:8]
            servers_base = self._runtime_root / "servers"
            self._server_dir = servers_base / f"server_{timestamp}_{short_uuid}"

        # Create the persistent directory structure
        self._server_dir.mkdir(parents=True, exist_ok=True)
        self._queue_root = self._server_dir / "queues"
        self._queue_root.mkdir(parents=True, exist_ok=True)
        (self._server_dir / "sessions").mkdir(parents=True, exist_ok=True)
        # Note: per-session task workspaces live at
        # <server>/sessions/<session>/tasks/ — created lazily by each task
        # launcher (DualInferencerBridge, ResearchProposeBridge, etc.) via
        # mkdir(parents=True, exist_ok=True). No global <server>/tasks/.

        # Create per-run log directory (new each server start/restart)
        run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._run_log_dir = self._server_dir / "logs" / "runs" / f"run_{run_timestamp}"
        self._run_log_dir.mkdir(parents=True, exist_ok=True)

        self._queue_service = StorageBasedQueueService(root_path=str(self._queue_root))
        return self._queue_service

    def create_queues(self, queue_ids: list[str]) -> None:
        """Create multiple named queues."""
        if self._queue_service is None:
            raise RuntimeError("QueueManager not initialized. Call initialize() first.")
        for queue_id in queue_ids:
            self._queue_service.create_queue(queue_id)

    def get_queue_root_path(self) -> Path:
        """Return the queue root path for client discovery."""
        if self._queue_root is None:
            raise RuntimeError("QueueManager not initialized. Call initialize() first.")
        return self._queue_root

    def get_server_dir(self) -> Path:
        """Return the server directory path."""
        if self._server_dir is None:
            raise RuntimeError("QueueManager not initialized. Call initialize() first.")
        return self._server_dir

    def get_run_log_dir(self) -> Path:
        """Return the per-run log directory path."""
        if self._run_log_dir is None:
            raise RuntimeError("QueueManager not initialized. Call initialize() first.")
        return self._run_log_dir

    def get_sessions_dir(self) -> Path:
        """Return the persistent sessions directory path."""
        if self._server_dir is None:
            raise RuntimeError("QueueManager not initialized. Call initialize() first.")
        return self._server_dir / "sessions"

    # Round 9: get_tasks_dir() removed — there is no longer a global
    # <server>/tasks/ directory. Per-session task workspaces live at
    # <server>/sessions/<session_dir>/tasks/, accessed via
    # session.session_tasks_dir on each RankEvolveSession instance.

    @property
    def queue_service(self) -> StorageBasedQueueService:
        if self._queue_service is None:
            raise RuntimeError("QueueManager not initialized. Call initialize() first.")
        return self._queue_service

    def close(self) -> None:
        """Close the queue service."""
        if self._queue_service is not None:
            self._queue_service.close()
            self._queue_service = None

    def __enter__(self) -> QueueManager:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
