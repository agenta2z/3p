# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict
"""
Output formatters for /kn subcommand results.

Each function takes structured data and returns a Rich-markup string
for display in the chat CLI console.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def truncate_content(content: str, max_len: int = 200) -> str:
    """Truncate content, appending '...' if truncated."""
    if len(content) <= max_len:
        return content
    return content[:max_len] + "..."


# ── Search / List ────────────────────────────────────────────────────────


def format_search_results(
    results: List[Tuple[Any, float]],
) -> str:
    """Format search results as a tabular display.

    Args:
        results: List of (KnowledgePiece, score) tuples.
    """
    if not results:
        return "[dim]No results found.[/dim]"

    lines = [f"[bold]{'ID':<10} {'Score':<7} {'Domain':<15} {'Type':<12} Content[/bold]"]
    lines.append("─" * 70)
    for piece, score in results:
        pid = piece.piece_id[:8] if hasattr(piece, "piece_id") else "?"
        domain = getattr(piece, "domain", "")[:15]
        ktype = ""
        kt = getattr(piece, "knowledge_type", "")
        if hasattr(kt, "value"):
            ktype = kt.value[:12]
        else:
            ktype = str(kt)[:12]
        content = truncate_content(piece.content, 80)
        lines.append(f"{pid:<10} {score:<7.2f} {domain:<15} {ktype:<12} {content}")
    return "\n".join(lines)


def format_list_results(
    pieces: List[Any],
    include_inactive: bool = False,
) -> str:
    """Format a list of KnowledgePiece objects as a table."""
    if not pieces:
        return "[dim]No knowledge pieces found.[/dim]"

    if include_inactive:
        header = f"[bold]{'ID':<10} {'Domain':<15} {'Type':<12} {'Active':<8} Content[/bold]"
    else:
        header = f"[bold]{'ID':<10} {'Domain':<15} {'Type':<12} Content[/bold]"
    lines = [header, "─" * 70]

    for piece in pieces:
        pid = piece.piece_id[:8] if hasattr(piece, "piece_id") else "?"
        domain = getattr(piece, "domain", "")[:15]
        kt = getattr(piece, "knowledge_type", "")
        ktype = kt.value[:12] if hasattr(kt, "value") else str(kt)[:12]
        content = truncate_content(piece.content, 80)

        if include_inactive:
            active = "Yes" if getattr(piece, "is_active", True) else "No"
            lines.append(f"{pid:<10} {domain:<15} {ktype:<12} {active:<8} {content}")
        else:
            lines.append(f"{pid:<10} {domain:<15} {ktype:<12} {content}")
    return "\n".join(lines)


# ── Single piece detail ──────────────────────────────────────────────────


def format_piece_detail(piece: Any) -> str:
    """Format a single KnowledgePiece with all fields."""
    if piece is None:
        return "[red]Piece not found.[/red]"

    kt = getattr(piece, "knowledge_type", "")
    ktype = kt.value if hasattr(kt, "value") else str(kt)
    spaces = ", ".join(getattr(piece, "spaces", []))
    tags = ", ".join(getattr(piece, "tags", []))

    lines = [
        f"[bold]Piece ID:[/bold] {piece.piece_id}",
        f"[bold]Domain:[/bold]   {getattr(piece, 'domain', 'N/A')}",
        f"[bold]Type:[/bold]     {ktype}",
        f"[bold]Info:[/bold]     {getattr(piece, 'info_type', 'N/A')}",
        f"[bold]Spaces:[/bold]   [{spaces}]",
        f"[bold]Tags:[/bold]     [{tags}]",
        f"[bold]Active:[/bold]   {getattr(piece, 'is_active', True)}",
        f"[bold]Version:[/bold]  {getattr(piece, 'version', 1)}",
        f"[bold]Created:[/bold]  {getattr(piece, 'created_at', 'N/A')}",
        f"[bold]Updated:[/bold]  {getattr(piece, 'updated_at', 'N/A')}",
        "",
        "[bold]Content:[/bold]",
        piece.content,
    ]
    return "\n".join(lines)


# ── Ingestion ────────────────────────────────────────────────────────────


def format_ingestion_result(result: Any) -> str:
    """Format an IngestionResult from DocumentIngester."""
    if result is None:
        return "[dim]No result.[/dim]"
    pieces = getattr(result, "pieces_created", 0)
    meta = getattr(result, "metadata_created", 0)
    nodes = getattr(result, "graph_nodes_created", 0)
    return f"Ingested: {pieces} pieces, {meta} metadata, {nodes} graph nodes"


# ── Delete ───────────────────────────────────────────────────────────────


def format_delete_candidates(
    candidates: List[Tuple[Any, float]],
) -> str:
    """Format delete candidates as a numbered list for user confirmation."""
    if not candidates:
        return "[dim]No matching pieces found.[/dim]"

    lines = [f"[bold]Found {len(candidates)} candidate(s):[/bold]"]
    for i, (piece, score) in enumerate(candidates, 1):
        pid = piece.piece_id[:8]
        preview = truncate_content(piece.content, 100)
        lines.append(f'  {i}. {pid} "{preview}" (score: {score:.2f})')
    lines.append("")
    lines.append("[dim]Use /kn delete <piece_id> to delete a specific piece.[/dim]")
    return "\n".join(lines)


# ── Rollback ─────────────────────────────────────────────────────────────


def format_rollback_result(result: Dict[str, Any]) -> str:
    """Format a rollback result dict."""
    pieces = result.get("pieces", 0)
    meta = result.get("metadata", 0)
    nodes = result.get("graph_nodes", 0)
    edges = result.get("graph_edges", 0)
    total = pieces + meta + nodes + edges
    return (
        f"Rolled back {total} entities: "
        f"{pieces} pieces, {meta} metadata, {nodes} nodes, {edges} edges"
    )


# ── History ──────────────────────────────────────────────────────────────


def format_history(operations: List[Any]) -> str:
    """Format operation history entries."""
    if not operations:
        return "[dim]No operations found.[/dim]"

    lines = [f"[bold]{'Timestamp':<26} {'Operation ID':<24} Description[/bold]"]
    lines.append("─" * 70)
    for op in operations:
        ts = getattr(op, "timestamp", "?")[:25]
        op_id = getattr(op, "operation_id", "?")[:23]
        desc = getattr(op, "description", "?")
        lines.append(f"{ts:<26} {op_id:<24} {desc}")
    return "\n".join(lines)


# ── Status ───────────────────────────────────────────────────────────────


def format_status(
    bridge: Any,
    model: str = "N/A",
) -> str:
    """Format enhanced knowledge bridge status."""
    if bridge is None:
        return "[dim]Knowledge bridge not available.[/dim]"

    llm_status = (
        "[green]enabled[/green]"
        if bridge.has_llm
        else "[yellow]disabled (basic mode)[/yellow]"
    )

    pieces = bridge.list_knowledge()
    total = len(pieces)
    active = sum(1 for p in pieces if getattr(p, "is_active", True))
    inactive = total - active

    space_counts: Dict[str, int] = {}
    for p in pieces:
        for s in getattr(p, "spaces", ["main"]):
            space_counts[s] = space_counts.get(s, 0) + 1

    spaces_display = ", ".join(f"{k}({v})" for k, v in sorted(space_counts.items()))

    lines = [
        "[bold]Knowledge Status:[/bold]",
        f"  LLM Ingestion: {llm_status}",
        f"  Model:         {model}",
        f"  Total Pieces:  {total} ({active} active, {inactive} inactive)",
        f"  Spaces:        {spaces_display or 'none'}",
    ]
    return "\n".join(lines)


# ── Spaces review ────────────────────────────────────────────────────────


def format_space_review(pieces: List[Any]) -> str:
    """Format pieces with pending space suggestions."""
    if not pieces:
        return "[dim]No pending space suggestions.[/dim]"

    lines = [f"[bold]Pending space suggestions ({len(pieces)}):[/bold]", ""]
    for piece in pieces:
        pid = piece.piece_id[:8]
        summary = truncate_content(piece.content, 100)
        current = ", ".join(getattr(piece, "spaces", []))
        suggested = ", ".join(getattr(piece, "pending_space_suggestions", []))
        reasons = getattr(piece, "space_suggestion_reasons", [])

        lines.append(f"  {pid}")
        lines.append(f"    Summary:   {summary}")
        lines.append(f"    Current:   [{current}]")
        lines.append(f"    Suggested: [{suggested}]")
        if reasons:
            for reason in reasons:
                lines.append(f"    Reason:    {reason}")
        lines.append("")
    return "\n".join(lines)


# ── Help ─────────────────────────────────────────────────────────────────


def format_help() -> str:
    """Return comprehensive /kn help text."""
    return (
        "[dim]Usage: /kn <subcommand> [args]\n"
        "\n"
        "  [bold]Core Commands:[/bold]\n"
        "  /kn add <text> [--space S] [--no-llm]       Add knowledge\n"
        "  /kn load <path> [--pattern *.md] [--space S] Load file or directory\n"
        "  /kn search <query> [--domain D] [--tags T]   Search with filters\n"
        "         [--limit N] [--space S] [--entity-id ID]\n"
        "  /kn list [--inactive] [--domain D] [--limit N] List pieces\n"
        "  /kn get <piece_id>                           Show piece detail\n"
        "  /kn status                                   Show KB status\n"
        "  /kn clear                                    Remove all knowledge\n"
        "\n"
        "  [bold]Lifecycle:[/bold]\n"
        "  /kn update <piece_id> <text> [--domain D]    Update a piece\n"
        "  /kn delete <piece_id> [--hard]               Delete a piece\n"
        "  /kn delete --query <text>                    Find & delete by query\n"
        "  /kn restore <piece_id>                       Restore soft-deleted piece\n"
        "\n"
        "  [bold]History & Rollback:[/bold]\n"
        "  /kn history --since <timestamp>              Show operation history\n"
        "  /kn rollback --op <operation_id>             Undo an operation\n"
        "  /kn rollback --to <timestamp>                Rollback to timestamp\n"
        "\n"
        "  [bold]Import/Export:[/bold]\n"
        "  /kn export <file>                            Export KB to JSON\n"
        "  /kn import <file>                            Import from JSON\n"
        "\n"
        "  [bold]Spaces:[/bold]\n"
        "  /kn spaces review                            Review space suggestions\n"
        "  /kn spaces migrate [--confirm]               Reclassify all pieces[/dim]"
    )
