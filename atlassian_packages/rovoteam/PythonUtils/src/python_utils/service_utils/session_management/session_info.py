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
