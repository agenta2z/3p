# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict
"""
Unified command handler for /kn subcommands.

Single entry point ``handle_kn_command()`` that routes each subcommand
through the appropriate parser → bridge method → formatter chain.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from rich.console import Console

from rankevolve.src.server.kn_arg_parser import (
    parse_kn_add,
    parse_kn_delete,
    parse_kn_export,
    parse_kn_get,
    parse_kn_history,
    parse_kn_import,
    parse_kn_list,
    parse_kn_load,
    parse_kn_restore,
    parse_kn_rollback,
    parse_kn_search,
    parse_kn_spaces,
    parse_kn_update,
)
from rankevolve.src.cli.chat_cli.kn_formatters import (
    format_delete_candidates,
    format_help,
    format_history,
    format_list_results,
    format_piece_detail,
    format_rollback_result,
    format_search_results,
    format_space_review,
    format_status,
)


def _show_progress(console: Console, msg: str) -> None:
    """Print a dim progress message."""
    console.print(f"[dim]  {msg}[/dim]")


def _not_available(console: Console) -> None:
    """Print the not-available warning."""
    console.print("[dim]Knowledge bridge not available (use --enable-knowledge).[/dim]")


def handle_kn_command(
    raw_args: str,
    knowledge_bridge: Any,
    console: Console,
    conversation: Any,
) -> None:
    """Route a /kn subcommand to the appropriate handler.

    Args:
        raw_args: Everything after "/kn " (e.g., "add hello world --space main").
        knowledge_bridge: The KnowledgeBridge instance (may be None).
        console: Rich Console for output.
        conversation: The Conversation object (for fallback context injection).
    """
    parts = raw_args.strip().split(None, 1)
    subcmd = parts[0].lower() if parts else ""
    rest = parts[1] if len(parts) > 1 else ""

    # ── Route to handler ─────────────────────────────────────────────

    handler_map = {
        "add": _handle_add,
        "load": _handle_load,
        "search": _handle_search,
        "list": _handle_list,
        "get": _handle_get,
        "update": _handle_update,
        "delete": _handle_delete,
        "restore": _handle_restore,
        "status": _handle_status,
        "clear": _handle_clear,
        "history": _handle_history,
        "rollback": _handle_rollback,
        "export": _handle_export,
        "import": _handle_import,
        "spaces": _handle_spaces,
    }

    handler = handler_map.get(subcmd)
    if handler is not None:
        handler(rest, knowledge_bridge, console, conversation)
        return

    # Smart auto-detection: file path → load, plain text → add
    if raw_args.strip():
        potential_path = raw_args.strip()
        is_file_path = (
            potential_path.startswith("/")
            or potential_path.startswith("./")
            or potential_path.startswith("~/")
            or potential_path.startswith("../")
        ) and (
            potential_path.endswith(".md")
            or potential_path.endswith(".txt")
            or potential_path.endswith(".json")
            or os.path.isfile(os.path.expanduser(potential_path))
        )
        if is_file_path:
            _handle_load(potential_path, knowledge_bridge, console, conversation)
        else:
            _handle_add(raw_args.strip(), knowledge_bridge, console, conversation)
        return

    # No subcommand — show help
    console.print(format_help())


# ── Individual handlers ──────────────────────────────────────────────────


def _handle_add(
    args: str,
    bridge: Any,
    console: Console,
    conversation: Any,
) -> None:
    if bridge is None:
        _not_available(console)
        return
    try:
        parsed = parse_kn_add(args)
    except ValueError as e:
        console.print(f"[dim]{e}[/dim]")
        return

    try:
        bridge.on_progress = lambda msg: _show_progress(console, msg)
        status_msg = bridge.add_knowledge(
            parsed["text"],
            use_llm=parsed["use_llm"],
            spaces=parsed["spaces"],
        )
        console.print(f"[green]✓ {status_msg}[/green]")
    except Exception as e:
        console.print(f"[red]✗ Failed to add knowledge: {e}[/red]")
    finally:
        bridge.on_progress = None


def _handle_load(
    args: str,
    bridge: Any,
    console: Console,
    conversation: Any,
) -> None:
    if bridge is None:
        _not_available(console)
        return
    try:
        parsed = parse_kn_load(args)
    except ValueError as e:
        console.print(f"[dim]{e}[/dim]")
        return

    path = parsed["path"]
    expanded = os.path.expanduser(path)

    try:
        bridge.on_progress = lambda msg: _show_progress(console, msg)
        if os.path.isdir(expanded):
            console.print(f"[dim]Scanning directory '{path}'...[/dim]")
            status_msg = bridge.load_directory(expanded, pattern=parsed["pattern"])
        else:
            console.print(f"[dim]Loading '{path}'...[/dim]")
            status_msg = bridge.load_file(expanded)
        console.print(f"[green]✓ {status_msg}[/green]")
    except FileNotFoundError as e:
        console.print(f"[red]✗ File not found: {e}[/red]")
    except ValueError as e:
        console.print(f"[red]✗ {e}[/red]")
    except Exception as e:
        console.print(f"[red]✗ Failed to load: {e}[/red]")
    finally:
        bridge.on_progress = None


def _handle_search(
    args: str,
    bridge: Any,
    console: Console,
    conversation: Any,
) -> None:
    if bridge is None:
        _not_available(console)
        return
    try:
        parsed = parse_kn_search(args)
    except ValueError as e:
        console.print(f"[dim]{e}[/dim]")
        return

    try:
        result = bridge.query_filtered(
            parsed["query"],
            domain=parsed.get("domain"),
            tags=parsed.get("tags"),
            top_k=parsed.get("top_k"),
            entity_id=parsed.get("entity_id"),
            spaces=parsed.get("spaces"),
        )
        if result is not None and hasattr(result, "pieces") and result.pieces:
            console.print(format_search_results(result.pieces))
        else:
            console.print("[dim]No relevant knowledge found.[/dim]")
    except Exception as e:
        console.print(f"[red]Search error: {e}[/red]")


def _handle_list(
    args: str,
    bridge: Any,
    console: Console,
    conversation: Any,
) -> None:
    if bridge is None:
        _not_available(console)
        return
    try:
        parsed = parse_kn_list(args)
    except ValueError as e:
        console.print(f"[dim]{e}[/dim]")
        return

    try:
        pieces = bridge.list_knowledge()

        # Apply filters
        include_inactive = parsed.get("include_inactive", False)
        if not include_inactive:
            pieces = [p for p in pieces if getattr(p, "is_active", True)]

        domain = parsed.get("domain")
        if domain:
            pieces = [p for p in pieces if getattr(p, "domain", "") == domain]

        spaces_filter = parsed.get("spaces")
        if spaces_filter:
            pieces = [
                p for p in pieces
                if set(getattr(p, "spaces", [])) & set(spaces_filter)
            ]

        limit = parsed.get("limit")
        if limit and limit > 0:
            pieces = pieces[:limit]

        console.print(format_list_results(pieces, include_inactive=include_inactive))
    except Exception as e:
        console.print(f"[red]List error: {e}[/red]")


def _handle_get(
    args: str,
    bridge: Any,
    console: Console,
    conversation: Any,
) -> None:
    if bridge is None:
        _not_available(console)
        return
    try:
        parsed = parse_kn_get(args)
    except ValueError as e:
        console.print(f"[dim]{e}[/dim]")
        return

    try:
        piece = bridge.get_piece(parsed["piece_id"])
        console.print(format_piece_detail(piece))
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


def _handle_update(
    args: str,
    bridge: Any,
    console: Console,
    conversation: Any,
) -> None:
    if bridge is None:
        _not_available(console)
        return
    try:
        parsed = parse_kn_update(args)
    except ValueError as e:
        console.print(f"[dim]{e}[/dim]")
        return

    try:
        result = bridge.update_piece(
            parsed["piece_id"],
            parsed["new_content"],
            domain=parsed.get("domain"),
            tags=parsed.get("tags"),
        )
        console.print(f"[green]✓ {result}[/green]")
    except Exception as e:
        console.print(f"[red]✗ Update failed: {e}[/red]")


def _handle_delete(
    args: str,
    bridge: Any,
    console: Console,
    conversation: Any,
) -> None:
    if bridge is None:
        _not_available(console)
        return
    try:
        parsed = parse_kn_delete(args)
    except ValueError as e:
        console.print(f"[dim]{e}[/dim]")
        return

    try:
        if parsed["mode"] == "direct":
            result = bridge.delete_by_id(
                parsed["piece_id"],
                hard=parsed.get("hard", False),
            )
            console.print(f"[green]✓ {result}[/green]")
        elif parsed["mode"] == "query":
            candidates = bridge.find_delete_candidates(parsed["query"])
            console.print(format_delete_candidates(candidates))
    except Exception as e:
        console.print(f"[red]✗ Delete failed: {e}[/red]")


def _handle_restore(
    args: str,
    bridge: Any,
    console: Console,
    conversation: Any,
) -> None:
    if bridge is None:
        _not_available(console)
        return
    try:
        parsed = parse_kn_restore(args)
    except ValueError as e:
        console.print(f"[dim]{e}[/dim]")
        return

    try:
        result = bridge.restore_by_id(parsed["piece_id"])
        console.print(f"[green]✓ {result}[/green]")
    except Exception as e:
        console.print(f"[red]✗ Restore failed: {e}[/red]")


def _handle_status(
    args: str,
    bridge: Any,
    console: Console,
    conversation: Any,
) -> None:
    console.print(format_status(bridge))


def _handle_clear(
    args: str,
    bridge: Any,
    console: Console,
    conversation: Any,
) -> None:
    if bridge is None:
        _not_available(console)
        return
    try:
        bridge.clear()
        console.print("[dim]All knowledge cleared.[/dim]")
    except Exception as e:
        console.print(f"[red]Clear error: {e}[/red]")


def _handle_history(
    args: str,
    bridge: Any,
    console: Console,
    conversation: Any,
) -> None:
    if bridge is None:
        _not_available(console)
        return
    try:
        parsed = parse_kn_history(args)
    except ValueError as e:
        console.print(f"[dim]{e}[/dim]")
        return

    try:
        operations = bridge.get_recent_operations(parsed["since"])
        console.print(format_history(operations))
    except Exception as e:
        console.print(f"[red]History error: {e}[/red]")


def _handle_rollback(
    args: str,
    bridge: Any,
    console: Console,
    conversation: Any,
) -> None:
    if bridge is None:
        _not_available(console)
        return
    try:
        parsed = parse_kn_rollback(args)
    except ValueError as e:
        console.print(f"[dim]{e}[/dim]")
        return

    try:
        if parsed["mode"] == "operation":
            result = bridge.rollback_operation(parsed["operation_id"])
        else:
            result = bridge.rollback_to_timestamp(parsed["timestamp"])
        console.print(f"[green]✓ {format_rollback_result(result)}[/green]")
    except Exception as e:
        console.print(f"[red]✗ Rollback failed: {e}[/red]")


def _handle_export(
    args: str,
    bridge: Any,
    console: Console,
    conversation: Any,
) -> None:
    if bridge is None:
        _not_available(console)
        return
    try:
        parsed = parse_kn_export(args)
    except ValueError as e:
        console.print(f"[dim]{e}[/dim]")
        return

    try:
        result = bridge.export_knowledge(parsed["file_path"])
        console.print(f"[green]✓ {result}[/green]")
    except Exception as e:
        console.print(f"[red]✗ Export failed: {e}[/red]")


def _handle_import(
    args: str,
    bridge: Any,
    console: Console,
    conversation: Any,
) -> None:
    if bridge is None:
        _not_available(console)
        return
    try:
        parsed = parse_kn_import(args)
    except ValueError as e:
        console.print(f"[dim]{e}[/dim]")
        return

    try:
        result = bridge.import_knowledge(parsed["file_path"])
        console.print(f"[green]✓ {result}[/green]")
    except Exception as e:
        console.print(f"[red]✗ Import failed: {e}[/red]")


def _handle_spaces(
    args: str,
    bridge: Any,
    console: Console,
    conversation: Any,
) -> None:
    if bridge is None:
        _not_available(console)
        return
    try:
        parsed = parse_kn_spaces(args)
    except ValueError as e:
        console.print(f"[dim]{e}[/dim]")
        return

    try:
        if parsed["action"] == "review":
            pieces = bridge.review_spaces()
            console.print(format_space_review(pieces))
        elif parsed["action"] == "migrate":
            if not parsed.get("confirm", False):
                console.print(
                    "[yellow]⚠ Space migration modifies all pieces. "
                    "Use --confirm to proceed:[/yellow]\n"
                    "[dim]  /kn spaces migrate --confirm[/dim]"
                )
                return
            console.print("[dim]Running space migration...[/dim]")
            try:
                from rankevolve.src.agentic_foundation.knowledge.ingestion.space_migration import (
                    SpaceMigrationUtility,
                )
                from rankevolve.src.agentic_foundation.knowledge.ingestion.space_classifier import (
                    SpaceClassifier,
                )

                migrator = SpaceMigrationUtility(bridge.kb, SpaceClassifier())
                report = migrator.migrate()
                console.print(
                    f"[green]✓ Migration complete: "
                    f"{report.pieces_updated} pieces, "
                    f"{report.metadata_updated} metadata updated[/green]"
                )
            except ImportError:
                console.print("[red]✗ Space migration module not available.[/red]")
    except Exception as e:
        console.print(f"[red]✗ Spaces error: {e}[/red]")
