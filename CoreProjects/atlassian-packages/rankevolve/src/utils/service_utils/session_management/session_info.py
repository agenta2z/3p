"""Generic session information data container.

Provides the SessionInfo dataclass with common session tracking fields
used by any service that manages sessions.
"""
from dataclasses import dataclass


@dataclass
class SessionInfo:
    """Base session data shared across services.

    Attributes:
        session_id: Unique identifier for the session.
        created_at: Timestamp (epoch seconds) when session was created.
        last_active: Timestamp (epoch seconds) of last activity.
        session_type: Type/variant of session (e.g. agent type, service type).
        initialized: True once the session's primary resource is created and locked.
    """
    session_id: str
    created_at: float
    last_active: float
    session_type: str
    initialized: bool = False

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "last_active": self.last_active,
            "session_type": self.session_type,
            "initialized": self.initialized,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionInfo":
        """Deserialize from a dictionary, ignoring unknown keys."""
        return cls(
            session_id=data["session_id"],
            created_at=data["created_at"],
            last_active=data["last_active"],
            session_type=data["session_type"],
            initialized=data.get("initialized", False),
        )
