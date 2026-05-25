# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict
"""
Argument parsing for /kn subcommands.

Splits raw argument strings into typed dicts consumed by
``kn_command_handler.py``.  Inspired by WebAxon's ``kb_arg_parser.py``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


# ── Core utilities ───────────────────────────────────────────────────────


def _split_flags(args: str) -> Tuple[str, Dict[str, str]]:
    """Split raw argument string into positional text and flag dict.

    Flags are ``--key value`` pairs.  Boolean flags like ``--hard`` have
    no value and are stored with the value ``"true"``.  Positional text is
    everything that appears before the first flag.
    """
    tokens = args.split()
    positional_parts: List[str] = []
    flags: Dict[str, str] = {}
    i = 0
    found_flag = False
    while i < len(tokens):
        token = tokens[i]
        if token.startswith("--"):
            found_flag = True
            key = token[2:]
            if i + 1 < len(tokens) and not tokens[i + 1].startswith("--"):
                flags[key] = tokens[i + 1]
                i += 2
            else:
                flags[key] = "true"
                i += 1
        else:
            if not found_flag:
                positional_parts.append(token)
            i += 1
    positional = " ".join(positional_parts)
    return positional, flags


def _extract_spaces(flags: Dict[str, str]) -> Optional[List[str]]:
    """Extract space filter from parsed flags.

    ``--spaces`` (comma-separated) takes precedence over ``--space`` (single).
    """
    if "spaces" in flags:
        return [s.strip() for s in flags["spaces"].split(",") if s.strip()]
    if "space" in flags:
        value = flags["space"].strip()
        return [value] if value else None
    return None


def _extract_tags(flags: Dict[str, str]) -> Optional[List[str]]:
    """Extract ``--tags T1,T2`` from flags."""
    if "tags" in flags:
        return [t.strip() for t in flags["tags"].split(",") if t.strip()]
    return None


def _extract_int(flags: Dict[str, str], key: str) -> Optional[int]:
    """Extract an optional positive integer flag."""
    if key in flags:
        try:
            val = int(flags[key])
            return val if val > 0 else None
        except (ValueError, TypeError):
            return None
    return None


# ── Command-specific parsers ─────────────────────────────────────────────


def parse_kn_add(args: str) -> Dict[str, Any]:
    """Parse ``/kn add <text> [--space S] [--spaces S1,S2] [--no-llm]``."""
    positional, flags = _split_flags(args)
    text = positional.strip()
    if not text:
        raise ValueError("Usage: /kn add <text> [--space S] [--no-llm]")
    return {
        "text": text,
        "spaces": _extract_spaces(flags),
        "use_llm": flags.get("no-llm") != "true",
    }


def parse_kn_load(args: str) -> Dict[str, Any]:
    """Parse ``/kn load <path> [--pattern *.md] [--space S]``."""
    positional, flags = _split_flags(args)
    path = positional.strip()
    if not path:
        raise ValueError("Usage: /kn load <path> [--pattern *.md] [--space S]")
    return {
        "path": path,
        "pattern": flags.get("pattern", "*.md"),
        "spaces": _extract_spaces(flags),
    }


def parse_kn_search(args: str) -> Dict[str, Any]:
    """Parse ``/kn search <query> [--domain D] [--tags T] [--limit N] [--space S] [--entity-id ID]``."""
    positional, flags = _split_flags(args)
    query = positional.strip()
    if not query:
        raise ValueError(
            "Usage: /kn search <query> [--domain D] [--tags T] [--limit N]"
        )
    return {
        "query": query,
        "domain": flags.get("domain"),
        "tags": _extract_tags(flags),
        "top_k": _extract_int(flags, "limit"),
        "entity_id": flags.get("entity-id"),
        "spaces": _extract_spaces(flags),
    }


def parse_kn_list(args: str) -> Dict[str, Any]:
    """Parse ``/kn list [--inactive] [--domain D] [--space S] [--limit N]``."""
    _, flags = _split_flags(args)
    return {
        "include_inactive": flags.get("inactive") == "true",
        "domain": flags.get("domain"),
        "spaces": _extract_spaces(flags),
        "limit": _extract_int(flags, "limit"),
    }


def parse_kn_get(args: str) -> Dict[str, Any]:
    """Parse ``/kn get <piece_id>``."""
    piece_id = args.strip()
    if not piece_id:
        raise ValueError("Usage: /kn get <piece_id>")
    return {"piece_id": piece_id}


def parse_kn_update(args: str) -> Dict[str, Any]:
    """Parse ``/kn update <piece_id> <new_content> [--domain D] [--tags T]``."""
    positional, flags = _split_flags(args)
    parts = positional.split(None, 1)
    if len(parts) < 2:
        raise ValueError("Usage: /kn update <piece_id> <new_content> [--domain D]")
    return {
        "piece_id": parts[0],
        "new_content": parts[1],
        "domain": flags.get("domain"),
        "tags": _extract_tags(flags),
    }


def parse_kn_delete(args: str) -> Dict[str, Any]:
    """Parse ``/kn delete <piece_id> [--hard]`` or ``/kn delete --query <text>``.

    Returns one of:
        ``{"mode": "direct", "piece_id": str, "hard": bool}``
        ``{"mode": "query", "query": str}``
    """
    positional, flags = _split_flags(args)

    if "query" in flags:
        query = flags["query"]
        if not query or query == "true":
            raise ValueError("Usage: /kn delete --query <text>")
        return {"mode": "query", "query": query}

    if "id" in flags:
        piece_id = flags["id"]
        if not piece_id or piece_id == "true":
            raise ValueError("Usage: /kn delete --id <piece_id> [--hard]")
        return {
            "mode": "direct",
            "piece_id": piece_id,
            "hard": flags.get("hard") == "true",
        }

    piece_id = positional.strip()
    if not piece_id:
        raise ValueError(
            "Usage: /kn delete <piece_id> [--hard]\n"
            "       /kn delete --query <text>"
        )
    return {
        "mode": "direct",
        "piece_id": piece_id,
        "hard": flags.get("hard") == "true",
    }


def parse_kn_restore(args: str) -> Dict[str, Any]:
    """Parse ``/kn restore <piece_id>``."""
    piece_id = args.strip()
    if not piece_id:
        raise ValueError("Usage: /kn restore <piece_id>")
    return {"piece_id": piece_id}


def parse_kn_history(args: str) -> Dict[str, Any]:
    """Parse ``/kn history --since <timestamp>``."""
    _, flags = _split_flags(args)
    since = flags.get("since")
    if not since:
        raise ValueError("Usage: /kn history --since <ISO-timestamp>")
    return {"since": since}


def parse_kn_rollback(args: str) -> Dict[str, Any]:
    """Parse ``/kn rollback --op <id>`` or ``/kn rollback --to <timestamp>``."""
    _, flags = _split_flags(args)
    if "op" in flags:
        op_id = flags["op"]
        if not op_id or op_id == "true":
            raise ValueError("Usage: /kn rollback --op <operation_id>")
        return {"mode": "operation", "operation_id": op_id}
    if "to" in flags:
        ts = flags["to"]
        if not ts or ts == "true":
            raise ValueError("Usage: /kn rollback --to <ISO-timestamp>")
        return {"mode": "timestamp", "timestamp": ts}
    raise ValueError(
        "Usage: /kn rollback --op <operation_id>\n"
        "       /kn rollback --to <ISO-timestamp>"
    )


def parse_kn_export(args: str) -> Dict[str, Any]:
    """Parse ``/kn export <file>``."""
    path = args.strip()
    if not path:
        raise ValueError("Usage: /kn export <file_path>")
    return {"file_path": path}


def parse_kn_import(args: str) -> Dict[str, Any]:
    """Parse ``/kn import <file>``."""
    path = args.strip()
    if not path:
        raise ValueError("Usage: /kn import <file_path>")
    return {"file_path": path}


def parse_kn_spaces(args: str) -> Dict[str, Any]:
    """Parse ``/kn spaces review`` or ``/kn spaces migrate [--confirm]``."""
    positional, flags = _split_flags(args)
    action = positional.strip().lower()
    if action == "review":
        return {"action": "review"}
    if action == "migrate":
        return {"action": "migrate", "confirm": flags.get("confirm") == "true"}
    raise ValueError(
        "Usage: /kn spaces review\n"
        "       /kn spaces migrate [--confirm]"
    )
