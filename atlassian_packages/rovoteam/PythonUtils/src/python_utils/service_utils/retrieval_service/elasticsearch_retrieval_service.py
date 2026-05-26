"""
Elasticsearch Retrieval Service

Elasticsearch-backed indexed document retrieval service with BM25 full-text search.
Ported from ``ElasticsearchKnowledgePieceStore`` and generalized to the ``Document`` model.

Architecture:
    - One Elasticsearch index per service instance.
    - Index mapping: doc_id (keyword), content (text/standard analyzer),
      embedding_text (text, not indexed), metadata (text, not indexed,
      JSON-serialized string), namespace (keyword), created_at/updated_at (date).
    - Metadata stored as a JSON string to avoid ES dynamic mapping conflicts
      when metadata values have inconsistent types across documents.
    - Document ``_id`` = ``f"{namespace}:{doc_id}"`` for cross-namespace uniqueness.
    - BM25 full-text search on ``content`` via ``bool`` query: ``must`` for
      content match, ``filter`` for ``term`` on namespace. All metadata
      filtering done post-query via ``matches_filters()``.
    - Scores normalized to [0, 1] by dividing by ``max_score``.
    - Duplicate detection uses ``op_type='create'`` -> ``ConflictError`` -> ``ValueError``.

Requires: ``elasticsearch``
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from attr import attrs, attrib

from .document import Document
from .filter_utils import matches_filters
from .retrieval_service_base import RetrievalServiceBase

logger = logging.getLogger(__name__)

_DEFAULT_NAMESPACE = "_default"

_INDEX_MAPPINGS = {
    "mappings": {
        "dynamic": "true",
        "properties": {
            "doc_id": {"type": "keyword"},
            "content": {"type": "text", "analyzer": "standard"},
            "embedding_text": {"type": "text", "index": False},
            "metadata": {"type": "text", "index": False},
            "namespace": {"type": "keyword"},
            "created_at": {"type": "date"},
            "updated_at": {"type": "date"},
        },
    }
}


@attrs(slots=False, repr=False)
class ElasticsearchRetrievalService(RetrievalServiceBase):
    """Elasticsearch-backed retrieval service with BM25 search.

    Attributes:
        hosts: List of Elasticsearch host URLs (e.g. ``["http://localhost:9200"]``).
        index_name: Name of the Elasticsearch index.
        auth: Optional ``(username, password)`` tuple.
    """

    hosts: List[str] = attrib()
    index_name: str = attrib(default="documents")
    auth: Optional[Tuple[str, str]] = attrib(default=None)
    _client: Any = attrib(init=False, default=None)
    _closed: bool = attrib(init=False, default=False)

    def __attrs_post_init__(self):
        from elasticsearch import Elasticsearch

        kwargs: Dict[str, Any] = {"hosts": self.hosts}
        if self.auth is not None:
            kwargs["basic_auth"] = self.auth
        self._client = Elasticsearch(**kwargs)
        self._ensure_index()

    def _ensure_index(self):
        if not self._client.indices.exists(index=self.index_name):
            self._client.indices.create(index=self.index_name, body=_INDEX_MAPPINGS)

    # ── helpers ──

    def _resolve_namespace(self, namespace: Optional[str]) -> str:
        return namespace if namespace is not None else _DEFAULT_NAMESPACE

    def _es_id(self, doc_id: str, namespace: str) -> str:
        """Build the Elasticsearch ``_id``: ``{namespace}:{doc_id}``."""
        return f"{namespace}:{doc_id}"

    def _doc_to_body(self, doc: Document, namespace: str) -> Dict[str, Any]:
        return {
            "doc_id": doc.doc_id,
            "content": doc.content,
            "embedding_text": doc.embedding_text or "",
            "metadata": json.dumps(doc.metadata, ensure_ascii=False) if doc.metadata else "{}",
            "namespace": namespace,
            "created_at": doc.created_at or "",
            "updated_at": doc.updated_at or "",
        }

    @staticmethod
    def _source_to_doc(source: Dict[str, Any]) -> Document:
        embedding_text = source.get("embedding_text", "")
        if embedding_text == "":
            embedding_text = None
        metadata = source.get("metadata", {})
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except (json.JSONDecodeError, TypeError):
                metadata = {}
        return Document(
            doc_id=source.get("doc_id", ""),
            content=source.get("content", ""),
            metadata=metadata,
            embedding_text=embedding_text,
            created_at=source.get("created_at") or None,
            updated_at=source.get("updated_at") or None,
        )

    # ── RetrievalServiceBase implementation ──

    def add(self, doc: Document, namespace: Optional[str] = None) -> str:
        from elasticsearch import ConflictError

        ns = self._resolve_namespace(namespace)
        body = self._doc_to_body(doc, ns)
        try:
            self._client.index(
                index=self.index_name,
                id=self._es_id(doc.doc_id, ns),
                document=body,
                op_type="create",
            )
        except ConflictError:
            raise ValueError(f"Duplicate doc_id: '{doc.doc_id}' already exists in namespace '{ns}'")
        self._client.indices.refresh(index=self.index_name)
        return doc.doc_id

    def get_by_id(self, doc_id: str, namespace: Optional[str] = None) -> Optional[Document]:
        from elasticsearch import NotFoundError

        ns = self._resolve_namespace(namespace)
        try:
            result = self._client.get(index=self.index_name, id=self._es_id(doc_id, ns))
            return self._source_to_doc(result["_source"])
        except NotFoundError:
            return None

    def update(self, doc: Document, namespace: Optional[str] = None) -> bool:
        from elasticsearch import NotFoundError

        ns = self._resolve_namespace(namespace)
        try:
            self._client.get(index=self.index_name, id=self._es_id(doc.doc_id, ns))
        except NotFoundError:
            return False
        doc.updated_at = datetime.now(timezone.utc).isoformat()
        body = self._doc_to_body(doc, ns)
        self._client.update(
            index=self.index_name,
            id=self._es_id(doc.doc_id, ns),
            doc=body,
        )
        self._client.indices.refresh(index=self.index_name)
        return True

    def remove(self, doc_id: str, namespace: Optional[str] = None) -> bool:
        from elasticsearch import NotFoundError

        ns = self._resolve_namespace(namespace)
        try:
            self._client.delete(index=self.index_name, id=self._es_id(doc_id, ns))
            self._client.indices.refresh(index=self.index_name)
            return True
        except NotFoundError:
            return False

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

        must_clauses = [{"match": {"content": {"query": query, "operator": "or"}}}]
        filter_clauses = [{"term": {"namespace": ns}}]

        # All metadata filtering done post-query since metadata is stored as JSON string
        query_body = {
            "query": {"bool": {"must": must_clauses, "filter": filter_clauses}},
            "size": top_k * 5 if filters else top_k,
        }

        try:
            response = self._client.search(index=self.index_name, body=query_body)
        except Exception as exc:
            logger.warning("Elasticsearch search error for '%s': %s", query, exc)
            return []

        hits = response.get("hits", {})
        hit_list = hits.get("hits", [])
        max_score = hits.get("max_score")
        if not hit_list or max_score is None or max_score <= 0:
            return []

        results: List[Tuple[Document, float]] = []
        for hit in hit_list:
            doc = self._source_to_doc(hit["_source"])
            # Post-query metadata filter matching
            if filters and not matches_filters(doc.metadata, filters):
                continue
            raw = hit.get("_score", 0.0)
            score = max(0.0, min(1.0, raw / max_score))
            results.append((doc, score))

        results.sort(key=lambda x: (-x[1], x[0].doc_id))
        return results[:top_k]

    def list_all(
        self,
        filters: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None,
    ) -> List[Document]:
        ns = self._resolve_namespace(namespace)
        filter_clauses = [{"term": {"namespace": ns}}]
        query_body = {
            "query": {"bool": {"filter": filter_clauses}},
            "size": 10000,
            "sort": [{"doc_id": "asc"}],
        }
        try:
            response = self._client.search(index=self.index_name, body=query_body)
        except Exception as exc:
            logger.warning("Elasticsearch list_all error: %s", exc)
            return []
        hits = response.get("hits", {}).get("hits", [])
        docs = [self._source_to_doc(h["_source"]) for h in hits]
        if filters:
            docs = [d for d in docs if matches_filters(d.metadata, filters)]
        return docs

    def size(self, namespace: Optional[str] = None) -> int:
        ns = self._resolve_namespace(namespace)
        try:
            response = self._client.count(
                index=self.index_name,
                body={"query": {"term": {"namespace": ns}}},
            )
            return response.get("count", 0)
        except Exception:
            return 0

    def clear(self, namespace: Optional[str] = None) -> int:
        ns = self._resolve_namespace(namespace)
        count = self.size(namespace=namespace)
        if count > 0:
            self._client.delete_by_query(
                index=self.index_name,
                body={"query": {"term": {"namespace": ns}}},
            )
            self._client.indices.refresh(index=self.index_name)
        return count

    def namespaces(self) -> List[str]:
        try:
            response = self._client.search(
                index=self.index_name,
                body={
                    "size": 0,
                    "aggs": {"ns": {"terms": {"field": "namespace", "size": 10000}}},
                },
            )
            buckets = response.get("aggregations", {}).get("ns", {}).get("buckets", [])
            return [b["key"] for b in buckets]
        except Exception:
            return []

    def get_stats(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        if namespace is not None:
            return {
                "backend": "elasticsearch",
                "hosts": self.hosts,
                "index_name": self.index_name,
                "namespace": namespace,
                "documents": self.size(namespace=namespace),
            }
        all_ns = self.namespaces()
        total = sum(self.size(namespace=ns) for ns in all_ns)
        return {
            "backend": "elasticsearch",
            "hosts": self.hosts,
            "index_name": self.index_name,
            "namespace_count": len(all_ns),
            "total_documents": total,
            "namespaces": {ns: self.size(namespace=ns) for ns in all_ns},
        }

    def ping(self) -> bool:
        if self._closed or self._client is None:
            return False
        try:
            return self._client.ping()
        except Exception:
            return False

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            if self._client is not None:
                self._client.close()
                self._client = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __repr__(self) -> str:
        return (
            f"ElasticsearchRetrievalService("
            f"hosts={self.hosts!r}, "
            f"index='{self.index_name}', "
            f"closed={self._closed})"
        )
