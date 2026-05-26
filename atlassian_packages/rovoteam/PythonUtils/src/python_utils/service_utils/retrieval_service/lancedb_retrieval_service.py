"""
LanceDB Retrieval Service

LanceDB-backed indexed document retrieval service with hybrid search
combining vector similarity (ANN) and full-text search (BM25 via Tantivy).
Ported from ``LanceDBKnowledgePieceStore`` and generalized to the ``Document`` model.

Architecture:
    - One LanceDB table per service instance.
    - Table columns: doc_id, content, embedding_text, metadata_json,
      namespace, created_at, updated_at, vector.
    - Hybrid search: ``score = hybrid_alpha * vector_score + (1 - hybrid_alpha) * bm25_score``
    - ``hybrid_alpha`` defaults to 0.7 (70% vector, 30% BM25).
    - SQL WHERE filter on ``namespace``. Post-query ``filter_utils.matches_filters()``
      on deserialized ``metadata_json``.

Requires: ``lancedb``
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from attr import attrs, attrib

from .document import Document
from .filter_utils import matches_filters
from .retrieval_service_base import RetrievalServiceBase

logger = logging.getLogger(__name__)

_DEFAULT_NAMESPACE = "_default"


def _escape_sql(value: str) -> str:
    """Escape single quotes for SQL WHERE clauses."""
    return value.replace("'", "''")


@attrs(slots=False, repr=False)
class LanceDBRetrievalService(RetrievalServiceBase):
    """LanceDB-backed retrieval service with hybrid vector + BM25 search.

    Attributes:
        db_path: Directory for LanceDB data files.
        embedding_function: Callable accepting a string, returning a list of floats.
        table_name: Name of the LanceDB table.
        hybrid_alpha: Balance between vector and FTS search.
            0.0 = pure FTS, 1.0 = pure vector. Default 0.7.
    """

    db_path: str = attrib()
    embedding_function: Callable = attrib()
    table_name: str = attrib(default="documents")
    hybrid_alpha: float = attrib(default=0.7)
    _db: Any = attrib(init=False, default=None)
    _table: Any = attrib(init=False, default=None)
    _fts_index_created: bool = attrib(init=False, default=False)
    _closed: bool = attrib(init=False, default=False)

    def __attrs_post_init__(self):
        import lancedb as _lancedb

        os.makedirs(self.db_path, exist_ok=True)
        self._db = _lancedb.connect(self.db_path)
        existing = self._db.list_tables()
        if self.table_name in existing:
            self._table = self._db.open_table(self.table_name)
            self._fts_index_created = True
        else:
            self._table = None
            self._fts_index_created = False

    # ── helpers ──

    def _resolve_namespace(self, namespace: Optional[str]) -> str:
        return namespace if namespace is not None else _DEFAULT_NAMESPACE

    def _embed(self, text: str) -> list:
        result = self.embedding_function(text)
        if hasattr(result, "tolist"):
            return result.tolist()
        return list(result)

    def _doc_to_record(self, doc: Document, namespace: str) -> dict:
        vector = self._embed(doc.embedding_text if doc.embedding_text else doc.content)
        return {
            "doc_id": doc.doc_id,
            "content": doc.content,
            "embedding_text": doc.embedding_text or "",
            "metadata_json": json.dumps(doc.metadata, ensure_ascii=False),
            "namespace": namespace,
            "created_at": doc.created_at or "",
            "updated_at": doc.updated_at or "",
            "vector": vector,
        }

    @staticmethod
    def _record_to_doc(record: dict) -> Document:
        try:
            metadata = json.loads(record.get("metadata_json", "{}"))
        except (json.JSONDecodeError, TypeError):
            metadata = {}
        embedding_text = record.get("embedding_text", "")
        if embedding_text == "":
            embedding_text = None
        return Document(
            doc_id=record.get("doc_id", ""),
            content=record.get("content", ""),
            metadata=metadata,
            embedding_text=embedding_text,
            created_at=record.get("created_at") or None,
            updated_at=record.get("updated_at") or None,
        )

    def _ensure_table(self, first_record: dict):
        if self._table is not None:
            return
        self._table = self._db.create_table(self.table_name, [first_record])
        self._create_fts_index()

    def _create_fts_index(self):
        if self._fts_index_created or self._table is None:
            return
        try:
            self._table.create_fts_index("content", replace=True)
            self._fts_index_created = True
        except Exception as exc:
            logger.warning("Failed to create FTS index: %s", exc)

    def _rebuild_fts_index(self):
        if self._table is None:
            return
        try:
            self._table.create_fts_index("content", replace=True)
            self._fts_index_created = True
        except Exception as exc:
            logger.warning("Failed to rebuild FTS index: %s", exc)

    # ── RetrievalServiceBase implementation ──

    def add(self, doc: Document, namespace: Optional[str] = None) -> str:
        ns = self._resolve_namespace(namespace)
        if self._table is not None:
            existing = (
                self._table.search()
                .where(f"doc_id = '{_escape_sql(doc.doc_id)}' AND namespace = '{_escape_sql(ns)}'")
                .limit(1)
                .to_list()
            )
            if existing:
                raise ValueError(f"Duplicate doc_id: '{doc.doc_id}' already exists in namespace '{ns}'")
        record = self._doc_to_record(doc, ns)
        if self._table is None:
            self._ensure_table(record)
        else:
            self._table.add([record])
            self._rebuild_fts_index()
        return doc.doc_id

    def get_by_id(self, doc_id: str, namespace: Optional[str] = None) -> Optional[Document]:
        if self._table is None:
            return None
        ns = self._resolve_namespace(namespace)
        try:
            results = (
                self._table.search()
                .where(f"doc_id = '{_escape_sql(doc_id)}' AND namespace = '{_escape_sql(ns)}'")
                .limit(1)
                .to_list()
            )
        except Exception as exc:
            logger.warning("LanceDB get_by_id error for '%s': %s", doc_id, exc)
            return None
        if not results:
            return None
        return self._record_to_doc(results[0])

    def update(self, doc: Document, namespace: Optional[str] = None) -> bool:
        if self._table is None:
            return False
        ns = self._resolve_namespace(namespace)
        existing = (
            self._table.search()
            .where(f"doc_id = '{_escape_sql(doc.doc_id)}' AND namespace = '{_escape_sql(ns)}'")
            .limit(1)
            .to_list()
        )
        if not existing:
            return False
        doc.updated_at = datetime.now(timezone.utc).isoformat()
        self._table.delete(f"doc_id = '{_escape_sql(doc.doc_id)}' AND namespace = '{_escape_sql(ns)}'")
        record = self._doc_to_record(doc, ns)
        self._table.add([record])
        self._rebuild_fts_index()
        return True

    def remove(self, doc_id: str, namespace: Optional[str] = None) -> bool:
        if self._table is None:
            return False
        ns = self._resolve_namespace(namespace)
        existing = (
            self._table.search()
            .where(f"doc_id = '{_escape_sql(doc_id)}' AND namespace = '{_escape_sql(ns)}'")
            .limit(1)
            .to_list()
        )
        if not existing:
            return False
        self._table.delete(f"doc_id = '{_escape_sql(doc_id)}' AND namespace = '{_escape_sql(ns)}'")
        self._rebuild_fts_index()
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
        if self._table is None:
            return []

        ns = self._resolve_namespace(namespace)
        where_clause = f"namespace = '{_escape_sql(ns)}'"
        fetch_limit = top_k * 5 if filters else top_k

        # Vector search
        vector_scores: Dict[str, float] = {}
        try:
            query_vector = self._embed(query)
            vector_results = (
                self._table.search(query_vector)
                .metric("cosine")
                .where(where_clause)
                .limit(fetch_limit)
                .to_list()
            )
            for row in vector_results:
                did = row.get("doc_id", "")
                distance = row.get("_distance", 1.0)
                vector_scores[did] = max(0.0, 1.0 - distance)
        except Exception as exc:
            logger.warning("LanceDB vector search error: %s", exc)

        # BM25 search
        bm25_scores: Dict[str, float] = {}
        if self._fts_index_created:
            try:
                fts_results = (
                    self._table.search(query, query_type="fts")
                    .where(where_clause)
                    .limit(fetch_limit)
                    .to_list()
                )
                if fts_results:
                    raw = [(r.get("doc_id", ""), float(r.get("_score", 0.0) or 0.0)) for r in fts_results]
                    max_s = max((s for _, s in raw), default=0.0)
                    for did, s in raw:
                        bm25_scores[did] = (s / max_s) if max_s > 0 else 0.0
            except Exception as exc:
                logger.warning("LanceDB FTS search error: %s", exc)

        # Combine
        all_ids = set(vector_scores) | set(bm25_scores)
        if not all_ids:
            return []

        alpha = self.hybrid_alpha
        combined: Dict[str, float] = {}
        for did in all_ids:
            combined[did] = alpha * vector_scores.get(did, 0.0) + (1.0 - alpha) * bm25_scores.get(did, 0.0)

        scored: List[Tuple[Document, float]] = []
        for did, score in combined.items():
            doc = self.get_by_id(did, namespace=namespace)
            if doc is None:
                continue
            if filters and not matches_filters(doc.metadata, filters):
                continue
            scored.append((doc, max(0.0, min(1.0, score))))

        scored.sort(key=lambda x: (-x[1], x[0].doc_id))
        return scored[:top_k]

    def list_all(
        self,
        filters: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None,
    ) -> List[Document]:
        if self._table is None:
            return []
        ns = self._resolve_namespace(namespace)
        try:
            results = (
                self._table.search()
                .where(f"namespace = '{_escape_sql(ns)}'")
                .limit(100000)
                .to_list()
            )
        except Exception as exc:
            logger.warning("LanceDB list_all error: %s", exc)
            return []
        docs = [self._record_to_doc(r) for r in results]
        if filters:
            docs = [d for d in docs if matches_filters(d.metadata, filters)]
        return docs

    def size(self, namespace: Optional[str] = None) -> int:
        return len(self.list_all(namespace=namespace))

    def clear(self, namespace: Optional[str] = None) -> int:
        if self._table is None:
            return 0
        ns = self._resolve_namespace(namespace)
        docs = self.list_all(namespace=namespace)
        count = len(docs)
        if count > 0:
            self._table.delete(f"namespace = '{_escape_sql(ns)}'")
            self._rebuild_fts_index()
        return count

    def namespaces(self) -> List[str]:
        if self._table is None:
            return []
        try:
            results = self._table.search().limit(100000).to_list()
        except Exception:
            return []
        ns_set: set = set()
        for r in results:
            ns = r.get("namespace")
            if ns is not None:
                ns_set.add(ns)
        return list(ns_set)

    def get_stats(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        if namespace is not None:
            return {
                "backend": "lancedb",
                "db_path": self.db_path,
                "table_name": self.table_name,
                "namespace": namespace,
                "documents": self.size(namespace=namespace),
            }
        all_ns = self.namespaces()
        total = sum(self.size(namespace=ns) for ns in all_ns)
        return {
            "backend": "lancedb",
            "db_path": self.db_path,
            "table_name": self.table_name,
            "namespace_count": len(all_ns),
            "total_documents": total,
            "namespaces": {ns: self.size(namespace=ns) for ns in all_ns},
        }

    def ping(self) -> bool:
        if self._closed or self._db is None:
            return False
        try:
            self._db.list_tables()
            return True
        except Exception:
            return False

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._table = None
            self._db = None
            self._fts_index_created = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __repr__(self) -> str:
        return (
            f"LanceDBRetrievalService("
            f"db_path='{self.db_path}', "
            f"table='{self.table_name}', "
            f"hybrid_alpha={self.hybrid_alpha}, "
            f"closed={self._closed})"
        )
