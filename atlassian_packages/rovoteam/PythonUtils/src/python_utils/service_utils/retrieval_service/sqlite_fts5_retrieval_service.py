"""
SQLite FTS5 Retrieval Service

SQLite-based indexed document retrieval service using FTS5 full-text search.
Uses Python's built-in ``sqlite3`` module with FTS5 for proper tokenized
BM25 ranking with zero external dependencies. SQLite and FTS5 ship with
Python 3.7+.

Architecture:
    - A main ``documents`` table stores structured data (doc_id, content,
      metadata_json, embedding_text, created_at, updated_at, namespace).
    - An FTS5 virtual table ``documents_fts`` indexes ``content`` for
      full-text search.
    - INSERT/DELETE/UPDATE triggers keep the FTS5 index in sync with the
      main table automatically.

Search uses FTS5 MATCH with the built-in ``bm25()`` ranking function.
Raw BM25 scores (negative, lower = better) are normalized to [0.0, 1.0]
by dividing by the magnitude of the best score in the result set.

Metadata filtering is done post-query using ``filter_utils.matches_filters``
since FTS5 cannot do JSON containment checks.

Best suited for:
- Persistent storage without external dependencies
- Single-process or multi-threaded applications
- Moderate to large document collections needing full-text search
- Applications needing ACID guarantees with proper BM25 ranking

Limitations:
- Not suitable for vector similarity search
- Metadata filtering is post-query (not pushed into the index)
- Single-writer concurrency model (WAL mode helps with reads)

Usage:
    from python_utils.service_utils.retrieval_service.sqlite_fts5_retrieval_service import (
        SQLiteFTS5RetrievalService
    )

    service = SQLiteFTS5RetrievalService(db_path="/tmp/my_docs.db")
    doc = Document(doc_id="d1", content="Python is great for data science")
    service.add(doc)

    results = service.search("python data")
    # [(Document(...), 1.0)]

    # With namespaces
    service.add(doc, namespace="project_a")

    # Context manager
    with SQLiteFTS5RetrievalService(db_path="/tmp/docs.db") as svc:
        svc.add(Document(doc_id="d1", content="hello world"))
        results = svc.search("hello")

Validates: Requirements 5.3
"""

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from attr import attrs, attrib

from .document import Document
from .filter_utils import matches_filters
from .retrieval_service_base import RetrievalServiceBase

logger = logging.getLogger(__name__)

_DEFAULT_NAMESPACE = "_default"

# ── SQL Statements ───────────────────────────────────────────────────────

_CREATE_DOCUMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS documents (
    doc_id         TEXT NOT NULL,
    content        TEXT NOT NULL,
    metadata_json  TEXT NOT NULL DEFAULT '{}',
    embedding_text TEXT,
    created_at     TEXT,
    updated_at     TEXT,
    namespace      TEXT NOT NULL,
    PRIMARY KEY (namespace, doc_id)
)
"""

_CREATE_NAMESPACE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_documents_namespace ON documents (namespace)
"""

# FTS5 virtual table — external content mode synced with the documents table.
# The ``content=documents`` option tells FTS5 to read content from the
# documents table rather than storing its own copy.
# ``content_rowid=rowid`` maps the FTS5 rowid to the documents table's
# implicit rowid.
_CREATE_FTS_TABLE = """
CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
    content,
    content=documents,
    content_rowid=rowid,
    tokenize='{tokenizer}'
)
"""

# Triggers to keep FTS5 index in sync with the main documents table.
# For external content tables, we must manually update the FTS index.
_CREATE_INSERT_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
    INSERT INTO documents_fts (rowid, content) VALUES (new.rowid, new.content);
END
"""

_CREATE_DELETE_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
    INSERT INTO documents_fts (documents_fts, rowid, content)
        VALUES ('delete', old.rowid, old.content);
END
"""

_CREATE_UPDATE_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
    INSERT INTO documents_fts (documents_fts, rowid, content)
        VALUES ('delete', old.rowid, old.content);
    INSERT INTO documents_fts (rowid, content) VALUES (new.rowid, new.content);
END
"""


def _row_to_document(row: sqlite3.Row) -> Document:
    """Convert a sqlite3.Row from the documents table to a Document.

    Args:
        row: A sqlite3.Row with columns matching the documents table schema.

    Returns:
        A Document instance.
    """
    try:
        metadata = json.loads(row["metadata_json"])
    except (json.JSONDecodeError, TypeError):
        metadata = {}

    return Document(
        doc_id=row["doc_id"],
        content=row["content"],
        metadata=metadata,
        embedding_text=row["embedding_text"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@attrs(slots=False, repr=False)
class SQLiteFTS5RetrievalService(RetrievalServiceBase):
    """SQLite FTS5-based indexed document retrieval service.

    Stores documents in a SQLite database with a main ``documents`` table
    and an FTS5 virtual table ``documents_fts`` for full-text search.
    Triggers keep the FTS5 index in sync with the main table automatically.

    Search uses FTS5 MATCH with the built-in ``bm25()`` ranking function.
    Scores are normalized to [0.0, 1.0].

    Metadata filtering is done post-query using ``filter_utils.matches_filters``
    since FTS5 cannot do JSON containment checks.

    Attributes:
        db_path: Path to the SQLite database file.
        tokenizer: FTS5 tokenizer to use. Options: ``"unicode61"``
            (multilingual default), ``"porter"`` (English stemming),
            ``"ascii"``. Defaults to ``"unicode61"``.
    """

    db_path: str = attrib()
    tokenizer: str = attrib(default="unicode61")
    _conn: Any = attrib(init=False, default=None)
    _closed: bool = attrib(init=False, default=False)

    def __attrs_post_init__(self):
        """Create the database file, tables, indexes, and triggers."""
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    def _create_tables(self):
        """Create the documents table, FTS5 virtual table, indexes, and triggers."""
        with self._conn:
            self._conn.execute(_CREATE_DOCUMENTS_TABLE)
            self._conn.execute(_CREATE_NAMESPACE_INDEX)
            # Create FTS5 table with the configured tokenizer
            fts_sql = _CREATE_FTS_TABLE.replace("{tokenizer}", self.tokenizer)
            self._conn.execute(fts_sql)
            # Create sync triggers
            self._conn.execute(_CREATE_INSERT_TRIGGER)
            self._conn.execute(_CREATE_DELETE_TRIGGER)
            self._conn.execute(_CREATE_UPDATE_TRIGGER)

    def _resolve_namespace(self, namespace: Optional[str]) -> str:
        """Resolve namespace, mapping None to '_default'."""
        return namespace if namespace is not None else _DEFAULT_NAMESPACE

    # ── RetrievalServiceBase ABC implementation ──────────────────────────

    def add(self, doc: Document, namespace: Optional[str] = None) -> str:
        """Add a document to the index.

        Inserts into the ``documents`` table. The FTS5 index is updated
        automatically via the INSERT trigger.

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

        # Check for duplicate
        cursor = self._conn.execute(
            "SELECT 1 FROM documents WHERE namespace = ? AND doc_id = ?",
            (ns, doc.doc_id),
        )
        if cursor.fetchone() is not None:
            raise ValueError(
                f"Document with doc_id '{doc.doc_id}' already exists "
                f"in namespace '{ns}'"
            )

        metadata_json = json.dumps(doc.metadata, ensure_ascii=False)
        with self._conn:
            self._conn.execute(
                "INSERT INTO documents "
                "(doc_id, content, metadata_json, embedding_text, "
                "created_at, updated_at, namespace) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    doc.doc_id,
                    doc.content,
                    metadata_json,
                    doc.embedding_text,
                    doc.created_at,
                    doc.updated_at,
                    ns,
                ),
            )
        return doc.doc_id

    def get_by_id(self, doc_id: str, namespace: Optional[str] = None) -> Optional[Document]:
        """Retrieve a document by its ID.

        Args:
            doc_id: The unique document identifier.
            namespace: Optional namespace to scope the lookup.
                      None maps to "_default" internally.

        Returns:
            The Document if found, or None if no document with that ID exists.
        """
        ns = self._resolve_namespace(namespace)
        cursor = self._conn.execute(
            "SELECT * FROM documents WHERE namespace = ? AND doc_id = ?",
            (ns, doc_id),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return _row_to_document(row)

    def update(self, doc: Document, namespace: Optional[str] = None) -> bool:
        """Update an existing document.

        Updates the ``documents`` table row. The FTS5 index is updated
        automatically via the UPDATE trigger.

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
        metadata_json = json.dumps(doc.metadata, ensure_ascii=False)
        now = datetime.now(timezone.utc).isoformat()
        with self._conn:
            cursor = self._conn.execute(
                "UPDATE documents SET "
                "content = ?, metadata_json = ?, embedding_text = ?, "
                "updated_at = ? "
                "WHERE namespace = ? AND doc_id = ?",
                (
                    doc.content,
                    metadata_json,
                    doc.embedding_text,
                    now,
                    ns,
                    doc.doc_id,
                ),
            )
        return cursor.rowcount > 0

    def remove(self, doc_id: str, namespace: Optional[str] = None) -> bool:
        """Remove a document from the index.

        Deletes from the ``documents`` table. The FTS5 index is cleaned up
        automatically via the DELETE trigger.

        Args:
            doc_id: The unique document identifier.
            namespace: Optional namespace to scope the removal.
                      None maps to "_default" internally.

        Returns:
            True if the document existed and was removed, False if not found.
        """
        ns = self._resolve_namespace(namespace)
        with self._conn:
            cursor = self._conn.execute(
                "DELETE FROM documents WHERE namespace = ? AND doc_id = ?",
                (ns, doc_id),
            )
        return cursor.rowcount > 0

    def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Tuple[Document, float]]:
        """Full-text search using FTS5 MATCH with BM25 ranking.

        Joins the main ``documents`` table with the ``documents_fts`` FTS5
        table using rowid. FTS5's built-in ``bm25()`` function provides BM25
        scoring. Raw scores (negative, lower = better match) are normalized
        to [0.0, 1.0] by dividing by the magnitude of the best score.

        Metadata filtering is done post-query using ``filter_utils.matches_filters``
        since FTS5 cannot do JSON containment checks.

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
        if not query or not query.strip():
            return []

        # Sanitize the query for FTS5
        sanitized_query = self._sanitize_fts_query(query)
        if not sanitized_query:
            return []

        ns = self._resolve_namespace(namespace)

        # Build the SQL query
        sql_parts = [
            "SELECT d.*, bm25(documents_fts) AS bm25_score",
            "FROM documents d",
            "JOIN documents_fts fts ON d.rowid = fts.rowid",
            "WHERE documents_fts MATCH ?",
            "AND d.namespace = ?",
        ]
        params: list = [sanitized_query, ns]

        # Order by BM25 score (lower = better in FTS5, so ascending)
        sql_parts.append("ORDER BY bm25_score")

        # Fetch more than top_k to allow for metadata filtering post-query
        fetch_limit = top_k * 5 if filters else top_k
        sql_parts.append("LIMIT ?")
        params.append(fetch_limit)

        sql = "\n".join(sql_parts)

        try:
            cursor = self._conn.execute(sql, params)
            rows = cursor.fetchall()
        except sqlite3.OperationalError as exc:
            # FTS5 query syntax error — log and return empty
            logger.warning("FTS5 query error for '%s': %s", query, exc)
            return []

        if not rows:
            return []

        # Convert rows to documents with raw BM25 scores
        raw_results: List[Tuple[Document, float]] = []
        for row in rows:
            doc = _row_to_document(row)
            raw_results.append((doc, row["bm25_score"]))

        # Apply metadata filtering post-query
        if filters:
            raw_results = [
                (doc, score)
                for doc, score in raw_results
                if matches_filters(doc.metadata, filters)
            ]

        if not raw_results:
            return []

        # Normalize BM25 scores to [0.0, 1.0].
        # FTS5 bm25() returns negative values where lower (more negative) = better.
        # We normalize by dividing each score by the best (most negative) score's
        # magnitude, so the best match gets 1.0.
        best_score = min(score for _, score in raw_results)  # most negative
        best_magnitude = abs(best_score) if best_score != 0 else 1.0

        normalized: List[Tuple[Document, float]] = []
        for doc, raw_score in raw_results:
            # raw_score is negative; abs(raw_score) / best_magnitude gives [0, 1]
            norm_score = abs(raw_score) / best_magnitude if best_magnitude > 0 else 0.0
            # Clamp to [0.0, 1.0] for safety
            norm_score = max(0.0, min(1.0, norm_score))
            normalized.append((doc, norm_score))

        # Sort by score descending, then by doc_id for determinism
        normalized.sort(key=lambda x: (-x[1], x[0].doc_id))

        return normalized[:top_k]

    def list_all(
        self,
        filters: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None,
    ) -> List[Document]:
        """List all documents matching the given filters.

        No FTS involved — uses simple SQL WHERE clauses for namespace,
        then applies metadata filtering in Python.

        Args:
            filters: Optional metadata filters. Scalar values require exact
                    match; list values require AND containment.
            namespace: Optional namespace to scope the listing.
                      None maps to "_default" internally.

        Returns:
            List of Document objects matching the filters.
        """
        ns = self._resolve_namespace(namespace)
        cursor = self._conn.execute(
            "SELECT * FROM documents WHERE namespace = ?",
            (ns,),
        )
        docs = [_row_to_document(row) for row in cursor.fetchall()]

        if not filters:
            return docs

        return [d for d in docs if matches_filters(d.metadata, filters)]

    def size(self, namespace: Optional[str] = None) -> int:
        """Get the number of documents in a namespace.

        Args:
            namespace: Optional namespace to get the size of.
                      None maps to "_default" internally.

        Returns:
            Number of documents in the namespace.
        """
        ns = self._resolve_namespace(namespace)
        cursor = self._conn.execute(
            "SELECT COUNT(*) FROM documents WHERE namespace = ?",
            (ns,),
        )
        return cursor.fetchone()[0]

    def clear(self, namespace: Optional[str] = None) -> int:
        """Remove all documents in a namespace.

        Args:
            namespace: Optional namespace to clear.
                      None maps to "_default" internally.

        Returns:
            Number of documents removed.
        """
        ns = self._resolve_namespace(namespace)
        cursor = self._conn.execute(
            "SELECT COUNT(*) FROM documents WHERE namespace = ?",
            (ns,),
        )
        count = cursor.fetchone()[0]
        with self._conn:
            self._conn.execute(
                "DELETE FROM documents WHERE namespace = ?",
                (ns,),
            )
        return count

    def namespaces(self) -> List[str]:
        """List all namespaces that contain documents.

        Returns:
            List of distinct namespace strings.
        """
        cursor = self._conn.execute(
            "SELECT DISTINCT namespace FROM documents"
        )
        return [row[0] for row in cursor.fetchall()]

    def get_stats(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """Get statistics about the service.

        Args:
            namespace: Optional namespace to get stats for.
                      If None, returns stats for all namespaces.

        Returns:
            Dictionary with service statistics.
        """
        if namespace is not None:
            ns = namespace
            return {
                "backend": "sqlite_fts5",
                "db_path": self.db_path,
                "tokenizer": self.tokenizer,
                "namespace": ns,
                "documents": self.size(namespace=ns),
            }
        else:
            all_ns = self.namespaces()
            cursor = self._conn.execute("SELECT COUNT(*) FROM documents")
            total_docs = cursor.fetchone()[0]
            return {
                "backend": "sqlite_fts5",
                "db_path": self.db_path,
                "tokenizer": self.tokenizer,
                "namespace_count": len(all_ns),
                "total_documents": total_docs,
                "namespaces": {
                    ns: self.size(namespace=ns) for ns in all_ns
                },
            }

    def ping(self) -> bool:
        """Check if service is responsive.

        Returns:
            True if the database connection is alive and service is not closed,
            False otherwise.
        """
        if self._closed or self._conn is None:
            return False
        try:
            self._conn.execute("SELECT 1")
            return True
        except sqlite3.Error:
            return False

    def close(self) -> None:
        """Close the SQLite connection and clean up resources.

        This method is idempotent — calling it multiple times is safe.
        """
        if not self._closed:
            self._closed = True
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    # ── Context manager protocol ─────────────────────────────────────────

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit — delegates to close()."""
        self.close()

    def __repr__(self) -> str:
        """String representation of the service."""
        if self._closed:
            return (
                f"SQLiteFTS5RetrievalService("
                f"db_path='{self.db_path}', "
                f"tokenizer='{self.tokenizer}', "
                f"closed=True)"
            )
        ns_count = len(self.namespaces())
        cursor = self._conn.execute("SELECT COUNT(*) FROM documents")
        total_docs = cursor.fetchone()[0]
        return (
            f"SQLiteFTS5RetrievalService("
            f"db_path='{self.db_path}', "
            f"tokenizer='{self.tokenizer}', "
            f"namespaces={ns_count}, "
            f"total_documents={total_docs}, "
            f"closed={self._closed})"
        )

    # ── Internal helpers ─────────────────────────────────────────────────

    @staticmethod
    def _sanitize_fts_query(query: str) -> str:
        """Sanitize a user query for FTS5 MATCH syntax.

        Tokenizes the query into words and wraps each in double quotes to
        prevent FTS5 syntax errors from special characters. Tokens are
        joined with spaces (implicit AND in FTS5).

        Args:
            query: The raw user query string.

        Returns:
            A sanitized FTS5 query string, or empty string if no valid tokens.
        """
        tokens = []
        for word in query.strip().split():
            # Strip non-alphanumeric characters for safety
            cleaned = "".join(ch for ch in word if ch.isalnum())
            if cleaned:
                tokens.append(f'"{cleaned}"')
        return " ".join(tokens)
