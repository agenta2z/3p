"""Data operation record for tracking knowledge unit history.

Each knowledge unit (piece, metadata, graph node/edge) maintains a list
of DataOperationRecord instances representing its full operation history.
This enables time-point and operation-based rollback.
"""

import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import attrs
from attrs import Factory


@attrs.define
class DataOperationRecord:
    """One operation in a knowledge unit's history.

    Attributes:
        operation: The type of operation performed.
            One of "add", "update", "delete", "restore", "reclassify".
        timestamp: ISO 8601 UTC timestamp of when the operation occurred.
        operation_id: Shared identifier for records from one batch operation.
            Multiple records with the same operation_id indicate they came
            from a single logical operation (e.g. dedup merging 3 pieces).
        reason: Human-readable or LLM-generated explanation of why the
            operation was performed.
        source: What triggered the operation (e.g. "KnowledgeUpdater",
            "KnowledgeDeleter", "manual", "space_classifier").
        content_before: Content prior to an UPDATE operation. Full snapshot,
            not a diff. Only populated for UPDATE operations on pieces.
        content_after: Content after an UPDATE operation. Only populated
            for UPDATE operations on pieces.
        properties_before: Properties dict prior to an UPDATE operation.
            Used for EntityMetadata and graph entities.
        properties_after: Properties dict after an UPDATE operation.
        fields_changed: Field-level change tracking for updates beyond
            content. E.g. {"spaces": {"before": ["main"], "after": ["main", "personal"]}}.
        details: Additional context such as LLM confidence, merge strategy,
            reasoning, etc.
    """

    operation: str
    timestamp: str
    operation_id: Optional[str] = None
    reason: Optional[str] = None
    source: Optional[str] = None
    content_before: Optional[str] = None
    content_after: Optional[str] = None
    properties_before: Optional[Dict[str, Any]] = None
    properties_after: Optional[Dict[str, Any]] = None
    fields_changed: Optional[Dict[str, Any]] = None
    details: Dict[str, Any] = Factory(dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a dictionary."""
        d: Dict[str, Any] = {
            "operation": self.operation,
            "timestamp": self.timestamp,
        }
        if self.operation_id is not None:
            d["operation_id"] = self.operation_id
        if self.reason is not None:
            d["reason"] = self.reason
        if self.source is not None:
            d["source"] = self.source
        if self.content_before is not None:
            d["content_before"] = self.content_before
        if self.content_after is not None:
            d["content_after"] = self.content_after
        if self.properties_before is not None:
            d["properties_before"] = self.properties_before
        if self.properties_after is not None:
            d["properties_after"] = self.properties_after
        if self.fields_changed is not None:
            d["fields_changed"] = self.fields_changed
        if self.details:
            d["details"] = self.details
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DataOperationRecord":
        """Reconstruct from a dictionary."""
        return cls(
            operation=data["operation"],
            timestamp=data["timestamp"],
            operation_id=data.get("operation_id"),
            reason=data.get("reason"),
            source=data.get("source"),
            content_before=data.get("content_before"),
            content_after=data.get("content_after"),
            properties_before=data.get("properties_before"),
            properties_after=data.get("properties_after"),
            fields_changed=data.get("fields_changed"),
            details=data.get("details", {}),
        )


def generate_operation_id(source: str, description: str = "") -> str:
    """Generate a unique operation ID for grouping related records.

    Args:
        source: What triggered the operation (e.g. "updater", "deleter").
        description: Short description of the operation.

    Returns:
        A unique operation ID string.
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    rand = secrets.token_hex(2)
    slug = description[:20].replace(" ", "-").lower() if description else ""
    return f"op-{ts}-{rand}-{source}-{slug}".rstrip("-")
