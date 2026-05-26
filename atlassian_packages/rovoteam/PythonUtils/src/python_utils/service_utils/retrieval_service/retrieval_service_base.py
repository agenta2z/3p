"""
Retrieval Service Base Class

Abstract base class defining the interface for indexed document retrieval services.
All retrieval service implementations should inherit from this class.

This ensures a consistent API across different backend implementations
(memory, file, SQLite FTS5, ChromaDB, LanceDB, Elasticsearch, etc.).
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from attr import attrs

from python_utils.service_utils.retrieval_service.document import Document


@attrs(slots=False)
class RetrievalServiceBase(ABC):
    """
    Abstract base class for indexed document retrieval services.

    Defines the standard interface that all retrieval service implementations
    must implement. This allows different backends (memory, file, SQLite FTS5,
    ChromaDB, LanceDB, Elasticsearch, etc.) to be used interchangeably.

    Core Operations:
        - add: Add a document to the index
        - get_by_id: Retrieve a document by its ID
        - update: Update an existing document
        - remove: Remove a document from the index
        - search: Search for documents by query with optional metadata filters
        - list_all: List all documents with optional metadata filters
        - size: Get the number of documents in a namespace
        - clear: Remove all documents in a namespace
        - namespaces: List all namespaces
        - get_stats: Get statistics about the service
        - ping: Check if service is responsive
        - close: Close the service connection

    Namespace Semantics:
        - namespace=None maps to "_default" internally
        - Each backend handles this mapping in its own implementation

    Filter Semantics:
        - Scalar value (str, int, float, bool): exact equality match
        - List value: AND containment — all items in filter list must be
          present in the document's metadata value
        - Missing key in metadata: filter not matched

    Search Results:
        - Returned as (Document, float) tuples
        - Ordered by descending relevance score
        - Scores normalized to [0.0, 1.0]

    Context Manager Support:
        Services support the 'with' statement for automatic cleanup.
    """

    @abstractmethod
    def add(self, doc: Document, namespace: Optional[str] = None) -> str:
        """
        Add a document to the index.

        Args:
            doc: The Document to add.
            namespace: Optional namespace to scope the storage.
                      None maps to "_default" internally.

        Returns:
            The doc_id of the added document.

        Raises:
            ValueError: If a document with the same doc_id already exists
                       in the namespace.
        """
        pass

    @abstractmethod
    def get_by_id(self, doc_id: str, namespace: Optional[str] = None) -> Optional[Document]:
        """
        Retrieve a document by its ID.

        Args:
            doc_id: The unique document identifier.
            namespace: Optional namespace to scope the lookup.
                      None maps to "_default" internally.

        Returns:
            The Document if found, or None if no document with that ID exists.
        """
        pass

    @abstractmethod
    def update(self, doc: Document, namespace: Optional[str] = None) -> bool:
        """
        Update an existing document.

        Args:
            doc: The Document with updated fields. The doc_id must match
                an existing document.
            namespace: Optional namespace to scope the update.
                      None maps to "_default" internally.

        Returns:
            True if the document was updated, False if no document with
            that doc_id exists.
        """
        pass

    @abstractmethod
    def remove(self, doc_id: str, namespace: Optional[str] = None) -> bool:
        """
        Remove a document from the index.

        Args:
            doc_id: The unique document identifier.
            namespace: Optional namespace to scope the removal.
                      None maps to "_default" internally.

        Returns:
            True if the document was removed, False if no document with
            that doc_id existed.
        """
        pass

    @abstractmethod
    def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Tuple[Document, float]]:
        """
        Search for documents by query with optional metadata filters.

        Args:
            query: The search query string.
            filters: Optional metadata filters. Scalar values require exact
                    match; list values require AND containment.
            namespace: Optional namespace to scope the search.
                      None maps to "_default" internally.
            top_k: Maximum number of results to return.

        Returns:
            List of (Document, score) tuples ordered by descending relevance
            score. Scores are normalized to [0.0, 1.0].
        """
        pass

    @abstractmethod
    def list_all(
        self,
        filters: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None,
    ) -> List[Document]:
        """
        List all documents with optional metadata filters.

        Args:
            filters: Optional metadata filters. Scalar values require exact
                    match; list values require AND containment.
            namespace: Optional namespace to scope the listing.
                      None maps to "_default" internally.

        Returns:
            List of Document objects matching the filters.
        """
        pass

    @abstractmethod
    def size(self, namespace: Optional[str] = None) -> int:
        """
        Get the number of documents in a namespace.

        Args:
            namespace: Optional namespace to get the size of.
                      None maps to "_default" internally.

        Returns:
            Number of documents in the namespace.
        """
        pass

    @abstractmethod
    def clear(self, namespace: Optional[str] = None) -> int:
        """
        Remove all documents in a namespace.

        Args:
            namespace: Optional namespace to clear.
                      None maps to "_default" internally.

        Returns:
            Number of documents removed.
        """
        pass

    @abstractmethod
    def namespaces(self) -> List[str]:
        """
        List all namespaces that contain documents.

        Returns:
            List of namespace strings.
        """
        pass

    @abstractmethod
    def get_stats(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics about the service.

        Args:
            namespace: Optional namespace to get stats for.
                      If None, returns stats for all namespaces.

        Returns:
            Dictionary with service statistics.
        """
        pass

    @abstractmethod
    def ping(self) -> bool:
        """
        Check if service is responsive.

        Returns:
            True if service is responsive, False otherwise.
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """
        Close the service connection and clean up resources.

        This method is idempotent — calling it multiple times is safe.
        """
        pass

    # ── Context manager protocol ──

    @abstractmethod
    def __enter__(self):
        """Context manager entry."""
        pass

    @abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        pass

    @abstractmethod
    def __repr__(self) -> str:
        """String representation of the service."""
        pass
