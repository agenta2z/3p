"""
Document Model

Generic indexed document for search and retrieval services.
Used by all RetrievalServiceBase implementations.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from attr import attrs, attrib


@attrs
class Document:
    """A generic indexed document for search and retrieval.

    Attributes:
        doc_id: Unique document identifier.
        content: The main text content of the document.
        metadata: Arbitrary key-value metadata associated with the document.
        embedding_text: Optional text used for generating embeddings.
            If None, backends typically fall back to content.
        created_at: ISO 8601 timestamp of document creation.
            Auto-generated if not provided.
        updated_at: ISO 8601 timestamp of last update.
            Auto-generated if not provided.
    """

    doc_id: str = attrib()
    content: str = attrib()
    metadata: Dict[str, Any] = attrib(factory=dict)
    embedding_text: Optional[str] = attrib(default=None)
    created_at: str = attrib(default=None)
    updated_at: str = attrib(default=None)

    def __attrs_post_init__(self):
        now = datetime.now(timezone.utc).isoformat()
        if self.created_at is None:
            self.created_at = now
        if self.updated_at is None:
            self.updated_at = now

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the document to a dictionary.

        Returns:
            Dictionary containing all document fields.
        """
        return {
            "doc_id": self.doc_id,
            "content": self.content,
            "metadata": dict(self.metadata),
            "embedding_text": self.embedding_text,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Document":
        """Reconstruct a Document from a dictionary.

        Args:
            data: Dictionary containing document fields.
                Must include 'doc_id' and 'content'.
                Optional fields default to their standard defaults.

        Returns:
            A new Document instance.
        """
        return cls(
            doc_id=data["doc_id"],
            content=data["content"],
            metadata=data.get("metadata", {}),
            embedding_text=data.get("embedding_text"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )
