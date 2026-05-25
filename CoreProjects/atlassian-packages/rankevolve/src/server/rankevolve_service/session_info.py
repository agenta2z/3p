# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.

"""RankEvolve session info with agent-specific fields."""

from __future__ import annotations

from dataclasses import dataclass

from rankevolve.src.utils.service_utils.session_management.session_info import (
    SessionInfo,
)


@dataclass
class RankEvolveSessionInfo(SessionInfo):
    """Extends SessionInfo with RankEvolve-specific fields."""

    model: str = ""
    session_root_path: str = ""
    workflow_target_path: str = ""
    provider: str = ""
    active_task_id: str | None = None

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dictionary."""
        d = super().to_dict()
        d.update({
            "model": self.model,
            "target_path": self.session_root_path,
            "workflow_target_path": self.workflow_target_path,
            "provider": self.provider,
            "active_task_id": self.active_task_id,
        })
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "RankEvolveSessionInfo":
        """Deserialize from a dictionary, ignoring unknown keys."""
        return cls(
            session_id=data["session_id"],
            created_at=data["created_at"],
            last_active=data["last_active"],
            session_type=data["session_type"],
            initialized=data.get("initialized", False),
            model=data.get("model", ""),
            session_root_path=data.get("target_path", ""),
            workflow_target_path=data.get("workflow_target_path", ""),
            provider=data.get("provider", ""),
            active_task_id=data.get("active_task_id"),
        )
