"""
Chroma Retrieval Service

ChromaDB-backed indexed document retrieval service with vector similarity search.
Ported from ``ChromaKnowledgePieceStore`` and generalized to the ``Document`` model.

Architecture:
    - A single Chroma collection stores documents. Namespace is stored as a
      Chroma metadata field (sentinel ``"_default"`` for ``None``).
    - ``Document.content`` is stored in Chroma metadata; the Chroma "document"
      field holds ``embedding_text`` (or ``content`` as fallback) for embedding.
    - ``Document.metadata`` is stored as a JSON string in a ``metadata_json``
      Chroma metadata field (Chroma values must be str/int/float/bool).
    - Vector similarity search with cosine distance converted to [0, 1] score
      via ``score = max(0.0, 1.0 - (distance / 2.0))``.
    - All ``Document.metadata`` filtering is done post-query via
      ``filter_utils.matches_filters()`` on deserialized ``metadata_json``.
      Chroma ``where``-filters are only used for namespace filtering.

Requires: ``chromadb``
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from attr import attrs, attrib

from .document import Document
from .filter_utils import matches_filters
from .retrieval_service_base import RetrievalServiceBase

logger = logging.getLogger(__name__)

_DEFAULT_NAMESPACE = "_default"


def _distance_to_score(distance: float) -> float:
    """Convert Chroma cosine distance [0, 2] to similarity score [0, 1]."""
    return max(0.0, 1.0 - (distance / 2.0))


@attrs(slots=False, repr=False)
class ChromaRetrievalService(RetrievalServiceBase):
    """ChromaDB-backed retrieval service with vector similarity search.

    Attributes:
        collection_name: Name of the Chroma collection.
        persist_directory: Directory for persistent storage. ``None`` → in-memory.
        embedding_function: Optional Chroma embedding function. ``None`` →
            Chroma default (all-MiniLM-L6-v2 via sentence-transformers).
    """

    collection_name: str = attrib(default="documents")
    persist_directory: Optional[str] = attrib(default=None)
    embedding_function: Optional[Any] = attrib(default=None)
    _client: Any = attrib(init=False, default=None)
    _collection: Any = attrib(init=False, default=None)
    _closed: bool = attrib(init=False, default=False)

    def __attrs_post_init__(self):
        import chromadb

        if self.persist_directory:
            self._client = chromadb.PersistentClient(path=self.persist_directory)
        else:
            self._client = chromadb.Client()

        kwargs: Dict[str, Any] = {
            "name": self.collection_name,
            "metadata": {"hnsw:space": "cosine"},
        }
        if self.embedding_function is not None:
            kwargs["embedding_function"] = self.embedding_function

        self._collection = self._client.get_or_create_collection(**kwargs)

    # ── helpers ──

    def _resolve_namespace(self, namespace: Optional[str]) -> str:
        return namespace if namespace is not None else _DEFAULT_NAMESPACE

    @staticmethod
    def _make_chroma_id(namespace: str, doc_id: str) -> str:
        """Build compound Chroma ID: ``{namespace}:{doc_id}``.

        Chroma IDs are globally unique within a collection.  Using a
        compound key ensures documents in different namespaces do not
        collide even if they share the same ``doc_id``.
        """
        return f"{namespace}:{doc_id}"

    @staticmethod
    def _doc_to_chroma(doc: Document, namespace: str) -> dict:
        """Prepare Chroma add/update kwargs for a Document."""
        chroma_doc_text = doc.embedding_text if doc.embedding_text else doc.content
        chroma_meta: Dict[str, Any] = {
            "namespace": namespace,
            "doc_id": doc.doc_id,
            "content": doc.content,
            "embedding_text": doc.embedding_text or "",
            "metadata_json": json.dumps(doc.metadata, ensure_ascii=False),
            "created_at": doc.created_at or "",
            "updated_at": doc.updated_at or "",
        }
        chroma_id = f"{namespace}:{doc.doc_id}"
        return {"id": chroma_id, "document": chroma_doc_text, "metadata": chroma_meta}

    @staticmethod
    def _chroma_to_doc(meta: Dict[str, Any]) -> Document:
        """Reconstruct a Document from Chroma metadata."""
        try:
            metadata = json.loads(meta.get("metadata_json", "{}"))
        except (json.JSONDecodeError, TypeError):
            metadata = {}
        embedding_text = meta.get("embedding_text", "")
        if embedding_text == "":
            embedding_text = None
        return Document(
            doc_id=meta.get("doc_id", ""),
            content=meta.get("content", ""),
            metadata=metadata,
            embedding_text=embedding_text,
            created_at=meta.get("created_at") or None,
            updated_at=meta.get("updated_at") or None,
        )

    # ── RetrievalServiceBase implementation ──

    def add(self, doc: Document, namespace: Optional[str] = None) -> str:
        ns = self._resolve_namespace(namespace)
        chroma_id = self._make_chroma_id(ns, doc.doc_id)
        # Duplicate check using compound ID (unique per namespace)
        existing = self._collection.get(ids=[chroma_id])
        if existing and existing["ids"]:
            raise ValueError(f"Duplicate doc_id: '{doc.doc_id}' already exists in namespace '{ns}'")
        rec = self._doc_to_chroma(doc, ns)
        self._collection.add(ids=[rec["id"]], documents=[rec["document"]], metadatas=[rec["metadata"]])
        return doc.doc_id

    def get_by_id(self, doc_id: str, namespace: Optional[str] = None) -> Optional[Document]:
        ns = self._resolve_namespace(namespace)
        chroma_id = self._make_chroma_id(ns, doc_id)
        result = self._collection.get(ids=[chroma_id])
        if not result or not result["ids"]:
            return None
        meta = result["metadatas"][0]
        return self._chroma_to_doc(meta)

    def update(self, doc: Document, namespace: Optional[str] = None) -> bool:
        ns = self._resolve_namespace(namespace)
        chroma_id = self._make_chroma_id(ns, doc.doc_id)
        existing = self._collection.get(ids=[chroma_id])
        if not existing or not existing["ids"]:
            return False
        doc.updated_at = datetime.now(timezone.utc).isoformat()
        rec = self._doc_to_chroma(doc, ns)
        self._collection.update(ids=[rec["id"]], documents=[rec["document"]], metadatas=[rec["metadata"]])
        return True

    def remove(self, doc_id: str, namespace: Optional[str] = None) -> bool:
        ns = self._resolve_namespace(namespace)
        chroma_id = self._make_chroma_id(ns, doc_id)
        existing = self._collection.get(ids=[chroma_id])
        if not existing or not existing["ids"]:
            return False
        self._collection.delete(ids=[chroma_id])
        return True

    def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Tuple[Document, float]]:
        if not query or not query.strip():
            return []
        ns = self._resolve_namespace(namespace)
        collection_count = self._collection.count()
        if collection_count == 0:
            return []

        # Fetch extra to allow for post-query metadata filtering
        n_results = min(top_k * 5 if filters else top_k, collection_count)
        where_filter = {"namespace": {"$eq": ns}}

        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where_filter,
            )
        except Exception as exc:
            logger.warning("Chroma query error for '%s': %s", query, exc)
            return []

        if not results or not results["ids"] or not results["ids"][0]:
            return []

        distances = results["distances"][0]
        metadatas = results["metadatas"][0]

        scored: List[Tuple[Document, float]] = []
        for distance, meta in zip(distances, metadatas):
            doc = self._chroma_to_doc(meta)
            if filters and not matches_filters(doc.metadata, filters):
                continue
            score = _distance_to_score(distance)
            scored.append((doc, score))

        scored.sort(key=lambda x: (-x[1], x[0].doc_id))
        return scored[:top_k]

    def list_all(
        self,
        filters: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None,
    ) -> List[Document]:
        ns = self._resolve_namespace(namespace)
        where_filter = {"namespace": {"$eq": ns}}
        result = self._collection.get(where=where_filter)
        if not result or not result["ids"]:
            return []
        docs: List[Document] = []
        for meta in result["metadatas"]:
            doc = self._chroma_to_doc(meta)
            if filters and not matches_filters(doc.metadata, filters):
                continue
            docs.append(doc)
        return docs

    def size(self, namespace: Optional[str] = None) -> int:
        return len(self.list_all(namespace=namespace))

    def clear(self, namespace: Optional[str] = None) -> int:
        ns = self._resolve_namespace(namespace)
        where_filter = {"namespace": {"$eq": ns}}
        result = self._collection.get(where=where_filter)
        if not result or not result["ids"]:
            return 0
        count = len(result["ids"])
        self._collection.delete(ids=result["ids"])
        return count

    def namespaces(self) -> List[str]:
        result = self._collection.get()
        if not result or not result["ids"]:
            return []
        ns_set: set = set()
        for meta in result["metadatas"]:
            ns = meta.get("namespace")
            if ns is not None:
                ns_set.add(ns)
        return list(ns_set)

    def get_stats(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        if namespace is not None:
            return {
                "backend": "chroma",
                "collection_name": self.collection_name,
                "namespace": namespace,
                "documents": self.size(namespace=namespace),
            }
        all_ns = self.namespaces()
        return {
            "backend": "chroma",
            "collection_name": self.collection_name,
            "namespace_count": len(all_ns),
            "total_documents": self._collection.count(),
            "namespaces": {ns: self.size(namespace=ns) for ns in all_ns},
        }

    def ping(self) -> bool:
        if self._closed or self._client is None:
            return False
        try:
            self._collection.count()
            return True
        except Exception:
            return False

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._collection = None
            self._client = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __repr__(self) -> str:
        return (
            f"ChromaRetrievalService("
            f"collection='{self.collection_name}', "
            f"closed={self._closed})"
        )
