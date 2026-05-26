"""
Memory Retrieval Service

In-memory indexed document retrieval service using Python dictionaries.
Supports basic keyword search using term overlap scoring.

Best suited for:
- Testing and development
- Single-process applications
- Quick prototyping without external dependencies
- Small document collections where persistence is not required

Search Method:
    Term overlap scoring — splits query and document content into
    lowercase words, counts overlapping terms, and normalizes the
    score to [0.0, 1.0] by dividing by the number of query terms.

Limitations:
- Data is lost when the process exits (not persistent)
- Not suitable for inter-process communication
- Memory-bound by available RAM
- Search quality is basic (no TF-IDF, BM25, or vector similarity)

Usage:
    from python_utils.service_utils.retrieval_service.memory_retrieval_service import (
        MemoryRetrievalService
    )

    service = MemoryRetrievalService()
    doc = Document(doc_id="d1", content="Python is great for data science")
    service.add(doc)

    results = service.search("python data")
    # [(Document(...), 1.0)]  — both query terms found in content

    # With namespaces
    service.add(doc, namespace="project_a")

    # Context manager
    with MemoryRetrievalService() as svc:
        svc.add(Document(doc_id="d1", content="hello world"))
        results = svc.search("hello")
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from attr import attrs, attrib

from .document import Document
from .filter_utils import matches_filters
from .retrieval_service_base import RetrievalServiceBase

_DEFAULT_NAMESPACE = "_default"


@attrs(slots=False, repr=False)
class MemoryRetrievalService(RetrievalServiceBase):
    """
    In-memory indexed document retrieval service.

    Stores documents in a nested dictionary structure:
    ``Dict[str, Dict[str, Document]]`` where the outer key is the namespace
    and the inner key is the doc_id.

    Search uses term overlap scoring: the query and document content are
    split into lowercase words, overlapping terms are counted, and the
    score is normalized to [0.0, 1.0] by dividing by the number of
    unique query terms.

    Attributes:
        _store: Nested dictionary for namespace-scoped document storage.
        _closed: Flag indicating if the service has been closed.
    """

    _store: Dict[str, Dict[str, Document]] = attrib(init=False, factory=dict)
    _closed: bool = attrib(init=False, default=False)

    def _resolve_namespace(self, namespace: Optional[str]) -> str:
        """Resolve namespace, mapping None to '_default'."""
        return namespace if namespace is not None else _DEFAULT_NAMESPACE

    def _score_document(self, query: str, content: str) -> float:
        """
        Compute term overlap score between query and document content.

        Splits both query and content into lowercase words, counts the
        number of query terms that appear in the content, and normalizes
        by the number of unique query terms.

        Args:
            query: The search query string.
            content: The document content string.

        Returns:
            A float in [0.0, 1.0]. Returns 0.0 if the query is empty.
        """
        query_terms = set(query.lower().split())
        if not query_terms:
            return 0.0
        content_terms = set(content.lower().split())
        overlap = query_terms & content_terms
        return len(overlap) / len(query_terms)

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
        ns = self._resolve_namespace(namespace)
        if ns not in self._store:
            self._store[ns] = {}
        if doc.doc_id in self._store[ns]:
            raise ValueError(
                f"Document with doc_id '{doc.doc_id}' already exists "
                f"in namespace '{ns}'"
            )
        self._store[ns][doc.doc_id] = doc
        return doc.doc_id

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
        ns = self._resolve_namespace(namespace)
        ns_store = self._store.get(ns)
        if ns_store is None:
            return None
        return ns_store.get(doc_id)

    def update(self, doc: Document, namespace: Optional[str] = None) -> bool:
        """
        Update an existing document.

        Updates the document's updated_at timestamp to the current time.

        Args:
            doc: The Document with updated fields. The doc_id must match
                an existing document.
            namespace: Optional namespace to scope the update.
                      None maps to "_default" internally.

        Returns:
            True if the document was updated, False if no document with
            that doc_id exists.
        """
        ns = self._resolve_namespace(namespace)
        ns_store = self._store.get(ns)
        if ns_store is None or doc.doc_id not in ns_store:
            return False
        doc.updated_at = datetime.now(timezone.utc).isoformat()
        ns_store[doc.doc_id] = doc
        return True

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
        ns = self._resolve_namespace(namespace)
        ns_store = self._store.get(ns)
        if ns_store is None or doc_id not in ns_store:
            return False
        del ns_store[doc_id]
        # Clean up empty namespaces
        if not ns_store:
            del self._store[ns]
        return True

    def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Tuple[Document, float]]:
        """
        Search for documents by query with optional metadata filters.

        Uses term overlap scoring: splits query and content into lowercase
        words, counts overlapping terms, normalizes to [0.0, 1.0].

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
        if not query:
            return []

        ns = self._resolve_namespace(namespace)
        ns_store = self._store.get(ns)
        if ns_store is None:
            return []

        scored_results: List[Tuple[Document, float]] = []
        for doc in ns_store.values():
            # Apply metadata filters
            if filters and not matches_filters(doc.metadata, filters):
                continue
            score = self._score_document(query, doc.content)
            if score > 0.0:
                scored_results.append((doc, score))

        # Sort by descending score
        scored_results.sort(key=lambda x: x[1], reverse=True)
        return scored_results[:top_k]

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
        ns = self._resolve_namespace(namespace)
        ns_store = self._store.get(ns)
        if ns_store is None:
            return []

        if not filters:
            return list(ns_store.values())

        return [
            doc for doc in ns_store.values()
            if matches_filters(doc.metadata, filters)
        ]

    def size(self, namespace: Optional[str] = None) -> int:
        """
        Get the number of documents in a namespace.

        Args:
            namespace: Optional namespace to get the size of.
                      None maps to "_default" internally.

        Returns:
            Number of documents in the namespace.
        """
        ns = self._resolve_namespace(namespace)
        ns_store = self._store.get(ns)
        if ns_store is None:
            return 0
        return len(ns_store)

    def clear(self, namespace: Optional[str] = None) -> int:
        """
        Remove all documents in a namespace.

        Args:
            namespace: Optional namespace to clear.
                      None maps to "_default" internally.

        Returns:
            Number of documents removed.
        """
        ns = self._resolve_namespace(namespace)
        ns_store = self._store.get(ns)
        if ns_store is None:
            return 0
        count = len(ns_store)
        del self._store[ns]
        return count

    def namespaces(self) -> List[str]:
        """
        List all namespaces that contain documents.

        Returns:
            List of namespace strings.
        """
        return list(self._store.keys())

    def get_stats(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics about the service.

        Args:
            namespace: Optional namespace to get stats for.
                      If None, returns stats for all namespaces.

        Returns:
            Dictionary with service statistics including:
            - backend: "memory"
            - namespace_count: number of namespaces
            - total_documents: total number of documents
            - namespaces: per-namespace document counts (when no namespace specified)
            - documents: number of documents (when namespace specified)
        """
        if namespace is not None:
            ns = namespace
            ns_store = self._store.get(ns)
            return {
                "backend": "memory",
                "namespace": ns,
                "documents": len(ns_store) if ns_store else 0,
            }
        else:
            total_docs = sum(len(v) for v in self._store.values())
            return {
                "backend": "memory",
                "namespace_count": len(self._store),
                "total_documents": total_docs,
                "namespaces": {
                    ns: len(store) for ns, store in self._store.items()
                },
            }

    def ping(self) -> bool:
        """
        Check if service is responsive.

        Returns:
            True if service is not closed, False otherwise.
        """
        return not self._closed

    def close(self) -> None:
        """
        Close the service and clean up resources.

        This method is idempotent — calling it multiple times is safe.
        """
        self._closed = True

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit — delegates to close()."""
        self.close()

    def __repr__(self) -> str:
        """String representation of the service."""
        ns_count = len(self._store)
        total_docs = sum(len(v) for v in self._store.values())
        return (
            f"MemoryRetrievalService("
            f"namespaces={ns_count}, "
            f"total_documents={total_docs}, "
            f"closed={self._closed})"
        )
