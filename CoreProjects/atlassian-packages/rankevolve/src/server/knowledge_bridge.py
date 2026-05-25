# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict

"""
KnowledgeBridge — Manages knowledge ingestion and retrieval for the chat CLI.

Provides two modes of operation:
1. Basic mode: Direct piece storage without LLM classification (fallback)
2. Full mode: LLM-powered ingestion with domain/tag classification

When the knowledge module is unavailable (e.g., during refactoring),
the bridge degrades gracefully — all operations return warnings but
the CLI continues to function.

Progress Callbacks:
    The bridge supports optional progress callbacks for real-time UI updates.
    Set the `on_progress` attribute to receive status messages during ingestion.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, List, Optional

logger = logging.getLogger(__name__)

# ---------- Guarded knowledge imports ----------
KNOWLEDGE_AVAILABLE = False

try:
    from rankevolve.src.agentic_foundation.knowledge.retrieval.knowledge_base import (
        KnowledgeBase,
    )
    from rankevolve.src.agentic_foundation.knowledge.retrieval.models.knowledge_piece import (
        KnowledgePiece,
    )
    from rankevolve.src.agentic_foundation.knowledge.retrieval.stores.graph.graph_adapter import (
        GraphServiceEntityGraphStore,
    )
    from rankevolve.src.agentic_foundation.knowledge.retrieval.stores.metadata.keyvalue_adapter import (
        KeyValueMetadataStore,
    )
    from rankevolve.src.agentic_foundation.knowledge.retrieval.stores.pieces.retrieval_adapter import (
        RetrievalKnowledgePieceStore,
    )
    from rankevolve.src.agentic_foundation.knowledge.services.graph_service.file_graph_service import (
        FileGraphService,
    )
    from rankevolve.src.agentic_foundation.knowledge.services.keyvalue_service.file_keyvalue_service import (
        FileKeyValueService,
    )
    from rankevolve.src.agentic_foundation.knowledge.services.retrieval_service.file_retrieval_service import (
        FileRetrievalService,
    )

    KNOWLEDGE_AVAILABLE = True
except ImportError as e:
    logger.warning(
        "Knowledge module not available (under refactoring?): %s. "
        "CLI will launch without knowledge features.",
        e,
    )

# Type alias for progress callback function
ProgressCallback = Callable[[str], None]


def _noop_progress(message: str) -> None:
    """Default no-op progress callback."""
    pass


class KnowledgeBridge:
    """Manages a persistent KnowledgeBase instance for the chat CLI.

    Uses file-backed services so knowledge persists across sessions.
    Data is stored at ~/.cache/rankevolve/knowledge/ by default.

    When the knowledge module is unavailable, all methods degrade gracefully:
    - add_knowledge / load_file / load_directory → return warning strings
    - query → returns empty string
    - list_knowledge → returns empty list

    When an inferencer is provided, enables full LLM-powered ingestion
    with domain classification. Otherwise falls back to basic storage.

    Supports optional progress callbacks for real-time UI updates during
    long-running ingestion operations.

    Attributes:
        kb: The underlying KnowledgeBase instance (None if unavailable).
        ingester: Optional DocumentIngester for LLM-powered classification.
        has_llm: Whether LLM-powered ingestion is available.
        on_progress: Callback for progress updates (settable).
    """

    def __init__(
        self,
        data_dir: Path | None = None,
        inferencer: Optional[Callable[[str], Any]] = None,
        on_progress: Optional[ProgressCallback] = None,
    ) -> None:
        """Initialize the KnowledgeBridge.

        Args:
            data_dir: Directory for persistent storage. Defaults to
                ~/.cache/rankevolve/knowledge/
            inferencer: Optional LLM inference callable (prompt -> response).
                If provided, enables full classification pipeline.
            on_progress: Optional callback for progress updates.
        """
        self._on_progress = on_progress or _noop_progress
        self._inferencer = inferencer
        self.ingester = None
        self.has_llm = False

        if not KNOWLEDGE_AVAILABLE:
            logger.warning(
                "KnowledgeBridge: knowledge module unavailable — "
                "running in disabled mode."
            )
            self.kb = None  # type: ignore[assignment]
            return

        data_dir = data_dir or Path.home() / ".cache" / "rankevolve" / "knowledge"
        data_dir.mkdir(parents=True, exist_ok=True)

        kv = FileKeyValueService(base_path=str(data_dir / "metadata"))
        retrieval = FileRetrievalService(base_dir=str(data_dir / "pieces"))
        graph = FileGraphService(base_dir=str(data_dir / "graph"))

        self.kb = KnowledgeBase(
            metadata_store=KeyValueMetadataStore(kv_service=kv),
            piece_store=RetrievalKnowledgePieceStore(retrieval_service=retrieval),
            graph_store=GraphServiceEntityGraphStore(graph_service=graph),
        )

        if inferencer is not None:
            self._init_ingester()

    @property
    def on_progress(self) -> ProgressCallback:
        """Get the current progress callback."""
        return self._on_progress

    @on_progress.setter
    def on_progress(self, callback: Optional[ProgressCallback]) -> None:
        """Set the progress callback and update ingester if present.

        Args:
            callback: New progress callback, or None for no-op.
        """
        self._on_progress = callback or _noop_progress
        if self.ingester is not None:
            self.ingester.on_progress = self._on_progress

    def _init_ingester(self) -> None:
        """Initialize the DocumentIngester with current progress callback."""
        if self._inferencer is None:
            return

        try:
            from rankevolve.src.agentic_foundation.knowledge.ingestion.document_ingester import (
                DocumentIngester,
                IngesterConfig,
            )

            config = IngesterConfig(
                max_retries=3,
                full_schema=True,
                merge_graphs=True,
                dedupe_pieces=True,
            )
            self.ingester = DocumentIngester(
                self._inferencer,
                config,
                on_progress=self._on_progress,
            )
            self.has_llm = True
            logger.info("KnowledgeBridge: LLM-powered ingestion enabled")
        except Exception as e:
            logger.warning("Failed to initialize DocumentIngester: %s", e)

    def add_knowledge(
        self,
        text: str,
        use_llm: bool = True,
        spaces: list[str] | None = None,
    ) -> str:
        """Add knowledge with optional LLM classification.

        If LLM is available and use_llm=True, sends text to LLM for
        structuring and classification. Otherwise, creates a basic
        piece with default values.

        Args:
            text: The knowledge text to ingest.
            use_llm: Whether to use LLM classification (default True).

        Returns:
            Status message indicating what was created.
        """
        if not KNOWLEDGE_AVAILABLE or self.kb is None:
            return "[Knowledge unavailable] Cannot add knowledge — module is under refactoring."

        if self.ingester is not None and use_llm:
            try:
                self._on_progress("Starting LLM classification...")
                result = self.ingester.ingest_text(text, self.kb)
                if result.success:
                    return (
                        f"Ingested: {result.pieces_created} pieces, "
                        f"{result.metadata_created} metadata, "
                        f"{result.graph_nodes_created} nodes"
                    )
                else:
                    errors = "; ".join(result.errors[:3])
                    return (
                        f"Partial ingestion ({result.pieces_created} pieces): {errors}"
                    )
            except Exception as e:
                self._on_progress(f"LLM ingestion failed: {e}")
                logger.warning("LLM ingestion failed, falling back to basic: %s", e)

        # Basic mode: direct piece creation without classification
        self._on_progress("Adding as basic piece (no classification)...")
        piece = KnowledgePiece(content=text, spaces=spaces or [])
        piece_id = self.kb.add_piece(piece)
        return f"Added (basic): {piece_id[:8]}..."

    def load_file(self, file_path: str) -> str:
        """Load and ingest a file with LLM classification.

        Requires LLM inferencer to be configured. Uses DocumentIngester
        to chunk the file (if needed) and classify each chunk.

        Args:
            file_path: Path to the file to ingest.

        Returns:
            Status message indicating what was created.

        Raises:
            ValueError: If LLM inferencer is not available.
            FileNotFoundError: If the file doesn't exist.
        """
        if not KNOWLEDGE_AVAILABLE or self.kb is None:
            return "[Knowledge unavailable] Cannot load file — module is under refactoring."

        if self.ingester is None:
            raise ValueError(
                "File ingestion requires LLM. "
                "Initialize KnowledgeBridge with an inferencer."
            )

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        self._on_progress(f"Reading '{path.name}'...")
        result = self.ingester.ingest_file(str(path), self.kb)
        if result.success:
            return (
                f"Ingested '{path.name}': {result.pieces_created} pieces, "
                f"{result.chunks_processed} chunks processed"
            )
        else:
            errors = "; ".join(result.errors[:3])
            return f"Failed to ingest '{path.name}': {errors}"

    def load_directory(self, directory: str, pattern: str = "*.md") -> str:
        """Load and ingest all matching files in a directory.

        Requires LLM inferencer to be configured. Uses DocumentIngester
        to process each file with the full classification pipeline.

        Args:
            directory: Directory path to scan.
            pattern: Glob pattern for matching files (default "*.md").

        Returns:
            Status message summarizing ingestion results.

        Raises:
            ValueError: If LLM inferencer is not available or path is not a directory.
        """
        if not KNOWLEDGE_AVAILABLE or self.kb is None:
            return "[Knowledge unavailable] Cannot load directory — module is under refactoring."

        if self.ingester is None:
            raise ValueError(
                "Directory ingestion requires LLM. "
                "Initialize KnowledgeBridge with an inferencer."
            )

        from rankevolve.src.agentic_foundation.knowledge.ingestion.document_ingester import (
            ingest_directory,
        )

        self._on_progress(f"Scanning directory '{directory}'...")
        results = ingest_directory(
            directory, self.kb, self.ingester.inferencer, pattern, self.ingester.config
        )

        total_pieces = sum(r.pieces_created for r in results.values())
        total_errors = sum(len(r.errors) for r in results.values())
        succeeded = sum(1 for r in results.values() if r.success)

        return (
            f"Ingested {succeeded}/{len(results)} files: "
            f"{total_pieces} pieces, {total_errors} errors"
        )

    def query(self, query: str) -> str:
        """Retrieve relevant knowledge for a query.

        .. note::
            TODO: retrieve() does not currently filter out inactive (soft-deleted)
            pieces. The proper fix belongs in KnowledgeBase.retrieve()'s piece
            retrieval path, which should add ``is_active=True`` filtering.
        """
        if not KNOWLEDGE_AVAILABLE or self.kb is None:
            return ""
        return self.kb(query)

    def query_for_task(self, request: str) -> str:
        """Retrieve knowledge relevant to a /task request.

        Queries task-specific spaces first (task_results, experiment_results),
        then falls back to general knowledge (excluding task spaces to avoid
        duplication). Combines both into a formatted context block.

        Args:
            request: The task request string.

        Returns:
            Formatted context string, or empty string if nothing found.
        """
        if not KNOWLEDGE_AVAILABLE or self.kb is None:
            return ""

        parts: list[str] = []
        task_spaces = ["task_results", "experiment_results"]

        # Task-specific knowledge
        try:
            task_kb = self.kb(
                request, spaces=task_spaces
            )
            if task_kb and task_kb.strip():
                parts.append(f"## Prior Task Knowledge\n{task_kb}")
        except Exception:
            logger.debug("Task-specific KB retrieval failed", exc_info=True)

        # General knowledge — deduplicate against task knowledge
        try:
            general_kb = self.kb(request)
            if general_kb and general_kb.strip():
                existing_text = "\n".join(parts)
                task_content = existing_text.replace(
                    "## Prior Task Knowledge\n", ""
                ).strip()
                if general_kb.strip() != task_content:
                    parts.append(f"## General Knowledge\n{general_kb}")
        except Exception:
            logger.debug("General KB retrieval failed", exc_info=True)

        if not parts:
            return ""

        combined = "\n\n".join(parts)
        # Truncate to ~4000 chars to avoid overwhelming the request
        if len(combined) > 4000:
            combined = combined[:4000] + "\n... (truncated)"
        return combined

    def add_task_result(
        self,
        request: str,
        response: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Ingest a structured task result into the knowledge base.

        Constructs a Markdown document from the task request/response and
        stores it in the ``task_results`` space. Uses ``use_llm=False`` to
        avoid async deadlock issues.

        Args:
            request: The original task request.
            response: The task response text.
            metadata: Optional dict with task_mode, workspace, etc.

        Returns:
            Status message from ingestion, or error string.
        """
        if not KNOWLEDGE_AVAILABLE or self.kb is None:
            return "[Knowledge unavailable]"

        meta = metadata or {}
        now = datetime.now(timezone.utc).isoformat()

        # Extract structured sections if present, otherwise take tail
        excerpt = response[:2000] if len(response) <= 2000 else self._extract_excerpt(response)

        text = (
            f"# Task Result: {request[:100]}\n"
            f"**Date**: {now}\n"
            f"**Mode**: {meta.get('task_mode', 'unknown')}\n"
            f"**Workspace**: {meta.get('workspace', 'N/A')}\n\n"
            f"## Request\n{request}\n\n"
            f"## Key Outcomes\n{excerpt}\n"
        )

        try:
            return self.add_knowledge(
                text, use_llm=False, spaces=["task_results"]
            )
        except Exception as e:
            logger.warning("Failed to ingest task result: %s", e)
            return f"[Ingestion failed: {e}]"

    @staticmethod
    def _extract_excerpt(response: str, max_chars: int = 2000) -> str:
        """Extract the most useful excerpt from a long response.

        Prefers structured sections (## Summary, ## Results) if found,
        otherwise returns the last N characters.
        """
        for heading in ("## Summary", "## Results", "## Key Outcomes"):
            idx = response.find(heading)
            if idx != -1:
                section = response[idx:idx + max_chars]
                return section
        # Fallback: last max_chars lines
        return "..." + response[-max_chars:]

    def list_knowledge(self) -> list:
        """List all stored knowledge pieces."""
        if not KNOWLEDGE_AVAILABLE or self.kb is None:
            return []
        return self.kb.piece_store.list_all()

    def clear(self) -> None:
        """Remove all stored knowledge pieces (hard delete)."""
        if not KNOWLEDGE_AVAILABLE or self.kb is None:
            return
        for piece in self.list_knowledge():
            self.kb.remove_piece(piece.piece_id, hard=True)

    # ── Extended methods (Phase 2) ──────────────────────────────────────

    def get_piece(self, piece_id: str) -> Any:
        """Retrieve a single knowledge piece by ID."""
        if not KNOWLEDGE_AVAILABLE or self.kb is None:
            return None
        return self.kb.piece_store.get_by_id(piece_id)

    def query_filtered(
        self,
        query: str,
        domain: Optional[str] = None,
        tags: Optional[List[str]] = None,
        top_k: Optional[int] = None,
        entity_id: Optional[str] = None,
        spaces: Optional[List[str]] = None,
    ) -> Any:
        """Search knowledge with full filtering support.

        Returns a RetrievalResult with metadata, pieces, and graph context.
        """
        if not KNOWLEDGE_AVAILABLE or self.kb is None:
            return None
        return self.kb.retrieve(
            query,
            entity_id=entity_id,
            top_k=top_k,
            domain=domain,
            tags=tags,
            spaces=spaces,
        )

    def update_piece(
        self,
        piece_id: str,
        new_content: str,
        domain: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> str:
        """Update an existing knowledge piece.

        Attempts to use KnowledgeUpdater for versioned updates.
        Falls back to direct KnowledgeBase.update_piece() if unavailable.
        """
        if not KNOWLEDGE_AVAILABLE or self.kb is None:
            return "[Knowledge unavailable]"

        piece = self.kb.piece_store.get_by_id(piece_id)
        if piece is None:
            return f"Piece not found: {piece_id}"

        piece.content = new_content
        if domain is not None:
            piece.domain = domain
        if tags is not None:
            piece.tags = tags

        success = self.kb.update_piece(piece)
        if success:
            return f"Updated piece {piece_id[:8]}"
        return f"Failed to update piece {piece_id[:8]}"

    def delete_by_id(
        self,
        piece_id: str,
        hard: bool = False,
        reason: Optional[str] = None,
    ) -> str:
        """Delete a single knowledge piece by ID.

        Args:
            piece_id: The piece to delete.
            hard: If True, permanently remove. Otherwise soft-delete.
            reason: Optional reason for the deletion.
        """
        if not KNOWLEDGE_AVAILABLE or self.kb is None:
            return "[Knowledge unavailable]"

        try:
            from rankevolve.src.agentic_foundation.knowledge.ingestion.knowledge_deleter import (
                KnowledgeDeleter,
                DeleteConfig,
            )
            from rankevolve.src.agentic_foundation.knowledge.retrieval.models.enums import (
                DeleteMode,
            )

            deleter = KnowledgeDeleter(self.kb.piece_store, DeleteConfig())
            mode = DeleteMode.HARD if hard else DeleteMode.SOFT
            result = deleter.delete_by_id(piece_id, mode=mode, reason=reason)
            if result.success:
                mode_label = "hard-deleted" if hard else "soft-deleted"
                return f"Piece {piece_id[:8]} {mode_label}"
            return f"Failed to delete {piece_id[:8]}: {result.error}"
        except ImportError:
            success = self.kb.remove_piece(piece_id, hard=hard)
            if success:
                return f"Piece {piece_id[:8]} {'hard-deleted' if hard else 'soft-deleted'}"
            return f"Piece not found: {piece_id}"

    def find_delete_candidates(
        self,
        query: str,
        entity_id: Optional[str] = None,
        domain: Optional[str] = None,
    ) -> list:
        """Find pieces matching a query for potential deletion."""
        if not KNOWLEDGE_AVAILABLE or self.kb is None:
            return []
        try:
            from rankevolve.src.agentic_foundation.knowledge.ingestion.knowledge_deleter import (
                KnowledgeDeleter,
                DeleteConfig,
            )

            deleter = KnowledgeDeleter(self.kb.piece_store, DeleteConfig())
            return deleter.find_candidates_for_deletion(
                query, entity_id=entity_id, domain=domain
            )
        except ImportError:
            results = self.kb.retrieve(query, entity_id=entity_id, domain=domain)
            return results.pieces if results and results.pieces else []

    def restore_by_id(self, piece_id: str) -> str:
        """Restore a soft-deleted knowledge piece."""
        if not KNOWLEDGE_AVAILABLE or self.kb is None:
            return "[Knowledge unavailable]"

        try:
            from rankevolve.src.agentic_foundation.knowledge.ingestion.knowledge_deleter import (
                KnowledgeDeleter,
                DeleteConfig,
            )

            deleter = KnowledgeDeleter(self.kb.piece_store, DeleteConfig())
            result = deleter.restore_by_id(piece_id)
            if result.success:
                return f"Restored piece {piece_id[:8]}"
            return f"Failed to restore {piece_id[:8]}: {result.error}"
        except ImportError:
            piece = self.kb.piece_store.get_by_id(piece_id)
            if piece is None:
                return f"Piece not found: {piece_id}"
            piece.is_active = True
            self.kb.piece_store.update(piece)
            return f"Restored piece {piece_id[:8]}"

    def rollback_to_timestamp(self, timestamp: str) -> dict:
        """Rollback all knowledge to a given ISO 8601 timestamp."""
        if not KNOWLEDGE_AVAILABLE or self.kb is None:
            return {"error": "Knowledge unavailable"}
        return self.kb.rollback_to(timestamp)

    def rollback_operation(self, operation_id: str) -> dict:
        """Undo all changes from a specific batch operation."""
        if not KNOWLEDGE_AVAILABLE or self.kb is None:
            return {"error": "Knowledge unavailable"}
        return self.kb.rollback_operation(operation_id)

    def get_recent_operations(self, since_timestamp: str) -> list:
        """Return operation history since a given timestamp."""
        if not KNOWLEDGE_AVAILABLE or self.kb is None:
            return []
        return self.kb.get_operations_since(since_timestamp)

    def export_knowledge(self, file_path: str) -> str:
        """Export all knowledge pieces to a JSON file."""
        if not KNOWLEDGE_AVAILABLE or self.kb is None:
            return "[Knowledge unavailable]"

        import json as _json

        pieces = self.kb.piece_store.list_all()
        data = [p.to_dict() for p in pieces]
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            _json.dump(data, f, indent=2, ensure_ascii=False)
        return f"Exported {len(data)} pieces to {file_path}"

    def import_knowledge(self, file_path: str) -> str:
        """Import knowledge pieces from a JSON file."""
        if not KNOWLEDGE_AVAILABLE or self.kb is None:
            return "[Knowledge unavailable]"

        count = self.kb.bulk_load(file_path)
        return f"Imported {count} pieces from {file_path}"

    def review_spaces(self) -> list:
        """Return pieces with pending space suggestions."""
        if not KNOWLEDGE_AVAILABLE or self.kb is None:
            return []
        pieces = self.kb.piece_store.list_all()
        return [
            p
            for p in pieces
            if getattr(p, "pending_space_suggestions", None)
            and getattr(p, "space_suggestion_status", "") == "pending"
        ]

    def close(self) -> None:
        """Close the underlying KnowledgeBase."""
        if not KNOWLEDGE_AVAILABLE or self.kb is None:
            return
        self.kb.close()
