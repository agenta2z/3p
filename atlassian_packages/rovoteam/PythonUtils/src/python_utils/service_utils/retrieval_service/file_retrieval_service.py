"""
File Retrieval Service

File-based indexed document retrieval service using JSON files on disk.
Each document is stored as a separate JSON file at:
    {base_dir}/{namespace_path}/{encoded_doc_id}.json

Namespace paths use hierarchical directories — a namespace like
``user:tony-chen`` becomes the nested path ``user/tony-chen/``.

Supports BM25-based text search (via optional ``rank-bm25`` library)
or a term-overlap fallback when rank-bm25 is not installed. Both modes
normalize scores to [0.0, 1.0].

Doc IDs are percent-encoded to produce safe filenames:
    '%' → '%25'  (first, to avoid double-encoding)
    ':' → '%3A'
    '/' → '%2F'
    '\\' → '%5C'

Best suited for:
- Persistent storage without external dependencies
- Single-process applications
- Human-readable data inspection on disk
- Moderate document collections where file I/O is acceptable

Limitations:
- Not thread-safe (single-process only)
- Performance degrades with very large numbers of documents per namespace
- No atomic multi-document operations
- BM25 index is rebuilt on each search (no persistent index)

Usage:
    from python_utils.service_utils.retrieval_service.file_retrieval_service import (
        FileRetrievalService
    )

    service = FileRetrievalService(base_dir="/tmp/my_retrieval_store")
    doc = Document(doc_id="d1", content="Python is great for data science")
    service.add(doc)

    results = service.search("python data")
    # [(Document(...), 0.85)]

    # With namespaces
    service.add(doc, namespace="project_a")

    # Context manager
    with FileRetrievalService(base_dir="/tmp/store") as svc:
        svc.add(Document(doc_id="d1", content="hello world"))
        results = svc.search("hello")

Validates: Requirements 5.2
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from attr import attrs, attrib

from .document import Document
from .filter_utils import matches_filters
from .retrieval_service_base import RetrievalServiceBase

logger = logging.getLogger(__name__)

_DEFAULT_NAMESPACE = "_default"

# Try to import rank-bm25 for BM25 scoring; fall back to term overlap if unavailable
try:
    from rank_bm25 import BM25Okapi  # type: ignore[import-untyped]

    _HAS_BM25 = True
except ImportError:
    _HAS_BM25 = False


# ── Namespace encoding (hierarchical directories) ───────────────────────


def _encode_namespace(namespace: str) -> str:
    """Encode a namespace for use as a directory path.

    Converts ':' to os.sep so that ``user:tony-chen`` becomes a nested
    directory ``user/tony-chen`` instead of the flat ``user%3Atony-chen``.

    Other unsafe characters are still percent-encoded for filesystem safety.

    Args:
        namespace: The raw namespace string (typically an entity_id).

    Returns:
        A filesystem-safe path component (may contain os.sep for nesting).
    """
    return (
        namespace
        .replace("%", "%25")
        .replace("\\", "%5C")
        .replace(":", os.sep)
        # '/' left as-is — it creates nested dirs (desired behavior)
    )


def _decode_namespace(encoded: str) -> str:
    """Reverse of _encode_namespace. Reconstructs the original namespace
    from a relative directory path.

    Args:
        encoded: The encoded namespace path (may contain os.sep).

    Returns:
        The original namespace string with ':' restored.
    """
    return (
        encoded
        .replace(os.sep, ":")
        .replace("%5C", "\\")
        .replace("%25", "%")
    )


# ── Percent-encoding helpers (same scheme as FileKeyValueService) ────────


def _encode_doc_id(doc_id: str) -> str:
    """Percent-encode a doc_id for use as a filename.

    Uses the same encoding scheme as FileKeyValueService:
        '%' → '%25'  (must be first to avoid double-encoding)
        ':' → '%3A'
        '/' → '%2F'
        '\\' → '%5C'

    Args:
        doc_id: The raw document ID string.

    Returns:
        A filesystem-safe encoded string.
    """
    return (
        doc_id
        .replace("%", "%25")
        .replace(":", "%3A")
        .replace("/", "%2F")
        .replace("\\", "%5C")
    )


def _decode_doc_id(encoded: str) -> str:
    """Reverse of _encode_doc_id. Decodes percent-encoded doc_id.

    Decodes in reverse order of encoding to ensure correctness:
        '%5C' → '\\\\'
        '%2F' → '/'
        '%3A' → ':'
        '%25' → '%'  (must be last to avoid premature decoding)

    Args:
        encoded: The percent-encoded doc_id string.

    Returns:
        The original doc_id string.
    """
    return (
        encoded
        .replace("%5C", "\\")
        .replace("%2F", "/")
        .replace("%3A", ":")
        .replace("%25", "%")
    )


from python_utils.nlp_utils.semantic_search import (
    tokenize,
    term_overlap_search,
)


# ── FileRetrievalService ────────────────────────────────────────────────


@attrs(slots=False, repr=False)
class FileRetrievalService(RetrievalServiceBase):
    """
    File-based indexed document retrieval service with BM25 search.

    Stores each document as a JSON file at:
        {base_dir}/{namespace}/{encoded_doc_id}.json

    Doc IDs are percent-encoded to produce safe filenames.
    Namespace=None maps to "_default" internally.

    Search uses BM25 scoring via ``rank-bm25`` if installed, otherwise
    falls back to simple term-overlap scoring. Both modes normalize
    scores to [0.0, 1.0].

    Attributes:
        base_dir: Root directory for all document files.
    """

    base_dir: str = attrib()
    _closed: bool = attrib(init=False, default=False)

    def __attrs_post_init__(self):
        """Create the base directory on initialization."""
        os.makedirs(self.base_dir, exist_ok=True)

    # ── Internal helpers ─────────────────────────────────────────────

    def _resolve_namespace(self, namespace: Optional[str]) -> str:
        """Resolve namespace, mapping None to '_default'."""
        return namespace if namespace is not None else _DEFAULT_NAMESPACE

    def _namespace_dir(self, namespace: str) -> str:
        """Return the directory path for a namespace.

        Uses hierarchical encoding: ``user:tony-chen`` → ``user/tony-chen/``.
        """
        return os.path.join(self.base_dir, _encode_namespace(namespace))

    def _doc_path(self, namespace: str, doc_id: str) -> str:
        """Return the file path for a document within a namespace."""
        encoded = _encode_doc_id(doc_id)
        return os.path.join(self._namespace_dir(namespace), f"{encoded}.json")

    def _load_document(self, filepath: str) -> Optional[Document]:
        """Load a Document from a JSON file.

        Args:
            filepath: Path to the JSON file.

        Returns:
            The deserialized Document, or None if the file is malformed.
        """
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Document.from_dict(data)
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            logger.warning("Skipping malformed document file %s: %s", filepath, exc)
            return None

    def _load_all_from_namespace(self, namespace: str) -> List[Document]:
        """Load all valid Document objects from a namespace directory.

        Args:
            namespace: The resolved namespace string.

        Returns:
            A list of successfully loaded Document objects.
        """
        ns_dir = self._namespace_dir(namespace)
        if not os.path.isdir(ns_dir):
            return []

        docs = []
        for filename in os.listdir(ns_dir):
            if not filename.endswith(".json"):
                continue
            filepath = os.path.join(ns_dir, filename)
            doc = self._load_document(filepath)
            if doc is not None:
                docs.append(doc)
        return docs

    def _find_doc_in_namespace(self, namespace: str, doc_id: str) -> Optional[str]:
        """Return the file path for a doc_id in a specific namespace, or None.

        Args:
            namespace: The resolved namespace string.
            doc_id: The document ID to look for.

        Returns:
            The full file path if found, or None.
        """
        path = self._doc_path(namespace, doc_id)
        if os.path.isfile(path):
            return path
        return None

    # ── BM25 / term-overlap search ───────────────────────────────────

    @staticmethod
    def _doc_searchable_text(doc: Document) -> str:
        """Build the searchable text for a document (content).

        Args:
            doc: The document.

        Returns:
            The content text used for search scoring.
        """
        return doc.content

    def _search_bm25(
        self,
        docs: List[Document],
        query_tokens: List[str],
        top_k: int,
    ) -> List[Tuple[Document, float]]:
        """Score documents using BM25Okapi from rank-bm25.

        Builds a BM25 index over the tokenized corpus of document texts,
        scores the query, and normalizes scores to [0.0, 1.0].

        Args:
            docs: Pre-filtered candidate documents.
            query_tokens: Tokenized query terms.
            top_k: Maximum results to return.

        Returns:
            Sorted list of (Document, normalized_score) tuples.
        """
        corpus = [tokenize(self._doc_searchable_text(d), stem=True) for d in docs]
        bm25 = BM25Okapi(corpus)
        raw_scores = bm25.get_scores(query_tokens)

        max_score = max(raw_scores) if raw_scores.size > 0 else 0.0

        scored = []
        for doc, score in zip(docs, raw_scores):
            normalized = float(score / max_score) if max_score > 0 else 0.0
            if normalized > 0.0:
                scored.append((doc, normalized))

        # Sort by score descending, then by doc_id for determinism
        scored.sort(key=lambda x: (-x[1], x[0].doc_id))
        return scored[:top_k]

    def _search_term_overlap(
        self,
        docs: List[Document],
        query_tokens: List[str],
        top_k: int,
    ) -> List[Tuple[Document, float]]:
        """Score documents using term overlap between query and document text.

        Delegates to the shared ``term_overlap_search`` utility.

        Args:
            docs: Pre-filtered candidate documents.
            query_tokens: Tokenized query terms.
            top_k: Maximum results to return.

        Returns:
            Sorted list of (Document, score) tuples.
        """
        return term_overlap_search(
            items=docs,
            query_tokens=query_tokens,
            text_fn=self._doc_searchable_text,
            id_fn=lambda doc: doc.doc_id,
            top_k=top_k,
            stem=True,
        )

    # ── Public API ───────────────────────────────────────────────────

    def add(self, doc: Document, namespace: Optional[str] = None) -> str:
        """
        Add a document to the store.

        Writes the document as a JSON file under the namespace directory.

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
        path = self._doc_path(ns, doc.doc_id)

        if os.path.isfile(path):
            raise ValueError(
                f"Document with doc_id '{doc.doc_id}' already exists "
                f"in namespace '{ns}'"
            )

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(doc.to_dict(), f, indent=2, ensure_ascii=False)

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
        filepath = self._find_doc_in_namespace(ns, doc_id)
        if filepath is None:
            return None
        return self._load_document(filepath)

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
        filepath = self._find_doc_in_namespace(ns, doc.doc_id)
        if filepath is None:
            return False

        doc.updated_at = datetime.now(timezone.utc).isoformat()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(doc.to_dict(), f, indent=2, ensure_ascii=False)
        return True

    def remove(self, doc_id: str, namespace: Optional[str] = None) -> bool:
        """
        Remove a document from the store.

        Finds and deletes the document file.

        Args:
            doc_id: The unique document identifier.
            namespace: Optional namespace to scope the removal.
                      None maps to "_default" internally.

        Returns:
            True if the document existed and was removed, False if not found.
        """
        ns = self._resolve_namespace(namespace)
        filepath = self._find_doc_in_namespace(ns, doc_id)
        if filepath is None:
            return False

        os.remove(filepath)

        # Clean up empty namespace directory
        ns_dir = self._namespace_dir(ns)
        if os.path.isdir(ns_dir) and not os.listdir(ns_dir):
            os.rmdir(ns_dir)

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

        If ``rank-bm25`` is installed, uses BM25Okapi scoring. Otherwise,
        falls back to term-overlap scoring. Both modes normalize scores to
        [0.0, 1.0].

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
        docs = self._load_all_from_namespace(ns)

        # Apply metadata filters before scoring
        if filters:
            docs = [d for d in docs if matches_filters(d.metadata, filters)]

        if not docs:
            return []

        query_tokens = tokenize(query, stem=True)
        if not query_tokens:
            return []

        if _HAS_BM25:
            return self._search_bm25(docs, query_tokens, top_k)
        else:
            return self._search_term_overlap(docs, query_tokens, top_k)

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
        docs = self._load_all_from_namespace(ns)

        if not filters:
            return docs

        return [d for d in docs if matches_filters(d.metadata, filters)]

    def size(self, namespace: Optional[str] = None) -> int:
        """
        Get the number of documents in a namespace.

        Args:
            namespace: Optional namespace to get the size of.
                      None maps to "_default" internally.

        Returns:
            Number of JSON files in the namespace directory.
        """
        ns = self._resolve_namespace(namespace)
        ns_dir = self._namespace_dir(ns)

        if not os.path.isdir(ns_dir):
            return 0

        return sum(1 for f in os.listdir(ns_dir) if f.endswith(".json"))

    def clear(self, namespace: Optional[str] = None) -> int:
        """
        Remove all documents in a namespace by deleting all JSON files.

        Also removes the namespace directory if it becomes empty.

        Args:
            namespace: Optional namespace to clear.
                      None maps to "_default" internally.

        Returns:
            Number of documents removed.
        """
        ns = self._resolve_namespace(namespace)
        ns_dir = self._namespace_dir(ns)

        if not os.path.isdir(ns_dir):
            return 0

        count = 0
        for filename in os.listdir(ns_dir):
            if filename.endswith(".json"):
                os.remove(os.path.join(ns_dir, filename))
                count += 1

        # Clean up empty namespace directory (and empty parents up to base_dir)
        current = ns_dir
        while current != self.base_dir:
            if os.path.isdir(current) and not os.listdir(current):
                os.rmdir(current)
                current = os.path.dirname(current)
            else:
                break

        return count

    def namespaces(self) -> List[str]:
        """
        List all namespaces that contain documents.

        Walks the directory tree under base_dir to find leaf directories
        that contain JSON files. Supports both flat namespaces (e.g.,
        ``_default/``) and hierarchical namespaces (e.g., ``user/tony-chen/``).

        Returns:
            List of namespace strings.
        """
        if not os.path.isdir(self.base_dir):
            return []

        result = []
        for dirpath, _dirnames, filenames in os.walk(self.base_dir):
            if any(f.endswith(".json") for f in filenames):
                rel = os.path.relpath(dirpath, self.base_dir)
                result.append(_decode_namespace(rel))
        return result

    def get_stats(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics about the service.

        Args:
            namespace: Optional namespace to get stats for.
                      If None, returns stats for all namespaces.

        Returns:
            Dictionary with service statistics including:
            - backend: "file"
            - base_dir: the base directory path
            - bm25_available: whether rank-bm25 is installed
            - namespace_count / total_documents (when no namespace specified)
            - namespace / documents (when namespace specified)
        """
        if namespace is not None:
            ns = namespace
            return {
                "backend": "file",
                "base_dir": self.base_dir,
                "bm25_available": _HAS_BM25,
                "namespace": ns,
                "documents": self.size(namespace=ns),
            }
        else:
            all_ns = self.namespaces()
            total_docs = sum(self.size(namespace=ns) for ns in all_ns)
            return {
                "backend": "file",
                "base_dir": self.base_dir,
                "bm25_available": _HAS_BM25,
                "namespace_count": len(all_ns),
                "total_documents": total_docs,
                "namespaces": {
                    ns: self.size(namespace=ns) for ns in all_ns
                },
            }

    def ping(self) -> bool:
        """
        Check if service is responsive.

        Returns:
            True if the base directory exists and service is not closed,
            False otherwise.
        """
        return not self._closed and os.path.isdir(self.base_dir)

    def close(self) -> None:
        """
        Close the service.

        This method is idempotent — calling it multiple times is safe.
        Note: does not delete any files on disk.
        """
        self._closed = True

    # ── Context manager protocol ─────────────────────────────────────

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit — delegates to close()."""
        self.close()

    def __repr__(self) -> str:
        """String representation of the service."""
        ns_count = len(self.namespaces())
        total_docs = sum(self.size(namespace=ns) for ns in self.namespaces())
        return (
            f"FileRetrievalService("
            f"base_dir='{self.base_dir}', "
            f"bm25_available={_HAS_BM25}, "
            f"namespaces={ns_count}, "
            f"total_documents={total_docs}, "
            f"closed={self._closed})"
        )
