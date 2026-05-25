# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict

"""Pure structured routing for /kn subcommands — no Console, no I/O.

Provides a KnResult dataclass and route_kn_command() that delegates to the
existing kn_arg_parser parsers and KnowledgeBridge methods, returning
structured results instead of printing to Console.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

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


@dataclass
class KnResult:
    """Structured result from a /kn subcommand."""

    success: bool
    message: str
    data: Any = None


def route_kn_command(
    raw_args: str,
    knowledge_bridge: Any,
    conversation: Any,
) -> KnResult:
    """Route a /kn subcommand and return a structured result. No Console, no I/O.

    Args:
        raw_args: Everything after "/kn " (e.g., "add hello world --space main").
        knowledge_bridge: The KnowledgeBridge instance (may be None).
        conversation: The Conversation object (for fallback context injection).

    Returns:
        KnResult with success, message, and optional data.
    """
    parts = raw_args.strip().split(None, 1)
    subcmd = parts[0].lower() if parts else ""
    rest = parts[1] if len(parts) > 1 else ""

    if not subcmd or subcmd == "help":
        return KnResult(
            success=True,
            message=(
                "Knowledge commands: /kn add, /kn load, /kn search, /kn list, "
                "/kn get, /kn update, /kn delete, /kn restore, /kn status, "
                "/kn clear, /kn history, /kn rollback, /kn export, /kn import, "
                "/kn spaces"
            ),
        )

    if knowledge_bridge is None:
        return KnResult(
            success=False,
            message="Knowledge bridge not available (use --enable-knowledge).",
        )

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
    if handler is None:
        return KnResult(
            success=False,
            message=f"Unknown /kn subcommand: {subcmd}. Use /kn help for available commands.",
        )

    try:
        return handler(rest, knowledge_bridge, conversation)
    except Exception as e:
        return KnResult(success=False, message=f"Error in /kn {subcmd}: {e}")


def _handle_add(rest: str, kb: Any, conv: Any) -> KnResult:
    parsed = parse_kn_add(rest)
    if "error" in parsed:
        return KnResult(success=False, message=parsed["error"])
    result = kb.add(parsed["content"], space=parsed.get("space", "default"))
    return KnResult(success=True, message="Knowledge added.", data=result)


def _handle_load(rest: str, kb: Any, conv: Any) -> KnResult:
    parsed = parse_kn_load(rest)
    if "error" in parsed:
        return KnResult(success=False, message=parsed["error"])
    path = parsed["path"]
    if not os.path.exists(path):
        return KnResult(success=False, message=f"Path not found: {path}")
    result = kb.load(path, space=parsed.get("space", "default"))
    return KnResult(success=True, message=f"Loaded from {path}.", data=result)


def _handle_search(rest: str, kb: Any, conv: Any) -> KnResult:
    parsed = parse_kn_search(rest)
    if "error" in parsed:
        return KnResult(success=False, message=parsed["error"])
    results = kb.search(parsed["query"], space=parsed.get("space"), limit=parsed.get("limit", 5))
    return KnResult(success=True, message=f"Found {len(results)} results.", data=results)


def _handle_list(rest: str, kb: Any, conv: Any) -> KnResult:
    parsed = parse_kn_list(rest)
    results = kb.list_pieces(space=parsed.get("space"), limit=parsed.get("limit", 20))
    return KnResult(success=True, message=f"Listed {len(results)} pieces.", data=results)


def _handle_get(rest: str, kb: Any, conv: Any) -> KnResult:
    parsed = parse_kn_get(rest)
    if "error" in parsed:
        return KnResult(success=False, message=parsed["error"])
    piece = kb.get(parsed["piece_id"])
    if piece is None:
        return KnResult(success=False, message=f"Piece not found: {parsed['piece_id']}")
    return KnResult(success=True, message="Piece retrieved.", data=piece)


def _handle_update(rest: str, kb: Any, conv: Any) -> KnResult:
    parsed = parse_kn_update(rest)
    if "error" in parsed:
        return KnResult(success=False, message=parsed["error"])
    result = kb.update(parsed["piece_id"], parsed["content"])
    return KnResult(success=True, message="Piece updated.", data=result)


def _handle_delete(rest: str, kb: Any, conv: Any) -> KnResult:
    parsed = parse_kn_delete(rest)
    if "error" in parsed:
        return KnResult(success=False, message=parsed["error"])
    result = kb.delete(parsed["piece_id"])
    return KnResult(success=True, message="Piece deleted.", data=result)


def _handle_restore(rest: str, kb: Any, conv: Any) -> KnResult:
    parsed = parse_kn_restore(rest)
    if "error" in parsed:
        return KnResult(success=False, message=parsed["error"])
    result = kb.restore(parsed["piece_id"])
    return KnResult(success=True, message="Piece restored.", data=result)


def _handle_status(rest: str, kb: Any, conv: Any) -> KnResult:
    status = kb.status()
    return KnResult(success=True, message="Knowledge base status.", data=status)


def _handle_clear(rest: str, kb: Any, conv: Any) -> KnResult:
    result = kb.clear()
    return KnResult(success=True, message="Knowledge base cleared.", data=result)


def _handle_history(rest: str, kb: Any, conv: Any) -> KnResult:
    parsed = parse_kn_history(rest)
    if "error" in parsed:
        return KnResult(success=False, message=parsed["error"])
    history = kb.history(parsed.get("piece_id"))
    return KnResult(success=True, message="History retrieved.", data=history)


def _handle_rollback(rest: str, kb: Any, conv: Any) -> KnResult:
    parsed = parse_kn_rollback(rest)
    if "error" in parsed:
        return KnResult(success=False, message=parsed["error"])
    result = kb.rollback(parsed["piece_id"], parsed.get("version"))
    return KnResult(success=True, message="Rollback completed.", data=result)


def _handle_export(rest: str, kb: Any, conv: Any) -> KnResult:
    parsed = parse_kn_export(rest)
    if "error" in parsed:
        return KnResult(success=False, message=parsed["error"])
    result = kb.export_data(parsed.get("path", "knowledge_export.json"))
    return KnResult(success=True, message="Export completed.", data=result)


def _handle_import(rest: str, kb: Any, conv: Any) -> KnResult:
    parsed = parse_kn_import(rest)
    if "error" in parsed:
        return KnResult(success=False, message=parsed["error"])
    path = parsed["path"]
    if not os.path.exists(path):
        return KnResult(success=False, message=f"File not found: {path}")
    result = kb.import_data(path)
    return KnResult(success=True, message="Import completed.", data=result)


def _handle_spaces(rest: str, kb: Any, conv: Any) -> KnResult:
    parsed = parse_kn_spaces(rest)
    spaces = kb.list_spaces()
    return KnResult(success=True, message=f"Found {len(spaces)} spaces.", data=spaces)
