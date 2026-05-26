"""Session manifest data model for indexing logs and artifacts.

Provides dataclasses for representing the session manifest structure:
- ArtifactEntry: metadata for a single artifact file
- TurnEntry: metadata for a single agent turn
- SessionManifest: top-level session manifest indexing all logs and artifacts
"""

import json
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ArtifactEntry:
    """A single artifact's metadata in the manifest."""

    path: str              # relative path from session dir
    type: str              # log type (e.g., ReasonerInput, Screenshot)
    producer: str          # class/component that produced it
    timestamp: str
    step: int              # step counter within the turn

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "path": self.path,
            "producer": self.producer,
            "step": self.step,
            "timestamp": self.timestamp,
            "type": self.type,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ArtifactEntry":
        """Deserialize from a dictionary.

        Supports legacy key ``class_name`` as fallback for ``producer``.
        """
        return cls(
            path=data["path"],
            type=data["type"],
            producer=data.get("producer", data.get("class_name", "")),
            timestamp=data["timestamp"],
            step=data["step"],
        )


@dataclass
class TurnEntry:
    """A single turn's metadata in the manifest."""

    turn_number: int
    start_timestamp: str
    log_file: str          # relative path from session dir
    artifacts: List[ArtifactEntry] = field(default_factory=list)
    end_timestamp: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dictionary."""
        d = {
            "artifacts": [a.to_dict() for a in self.artifacts],
            "end_timestamp": self.end_timestamp,
            "log_file": self.log_file,
            "start_timestamp": self.start_timestamp,
            "turn_number": self.turn_number,
        }
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "TurnEntry":
        """Deserialize from a dictionary."""
        return cls(
            turn_number=data["turn_number"],
            start_timestamp=data["start_timestamp"],
            log_file=data["log_file"],
            artifacts=[ArtifactEntry.from_dict(a) for a in data.get("artifacts", [])],
            end_timestamp=data.get("end_timestamp"),
        )


@dataclass
class SessionManifest:
    """Session manifest indexing all logs and artifacts."""

    session_id: str
    creation_timestamp: str
    session_type: str
    status: str                    # "running", "completed", "error"
    session_dir: str               # absolute path
    session_log_file: str          # relative path to session.jsonl
    turns: List[TurnEntry] = field(default_factory=list)
    end_timestamp: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dictionary with consistent key ordering."""
        return {
            "creation_timestamp": self.creation_timestamp,
            "end_timestamp": self.end_timestamp,
            "session_dir": self.session_dir,
            "session_id": self.session_id,
            "session_log_file": self.session_log_file,
            "session_type": self.session_type,
            "status": self.status,
            "turns": [t.to_dict() for t in self.turns],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionManifest":
        """Deserialize from a dictionary.

        Supports legacy key ``agent_type`` as fallback for ``session_type``.
        """
        return cls(
            session_id=data["session_id"],
            creation_timestamp=data["creation_timestamp"],
            session_type=data.get("session_type", data.get("agent_type", "")),
            status=data["status"],
            session_dir=data["session_dir"],
            session_log_file=data["session_log_file"],
            turns=[TurnEntry.from_dict(t) for t in data.get("turns", [])],
            end_timestamp=data.get("end_timestamp"),
        )

    def to_json(self, indent: int = 2) -> str:
        """Serialize to a pretty-printed JSON string with consistent key ordering.

        Keys are sorted alphabetically for deterministic output.
        """
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    @classmethod
    def from_json(cls, json_str: str) -> "SessionManifest":
        """Deserialize from a JSON string."""
        return cls.from_dict(json.loads(json_str))
