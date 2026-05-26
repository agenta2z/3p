"""Wrapper-side helpers shared by all four tool wrappers in server.py."""
from __future__ import annotations
from typing import Any


def to_dash_form(d: dict[str, Any]) -> dict[str, Any]:
    """Python kwargs (foo_bar) -> executor key convention (foo-bar)."""
    return {k.replace("_", "-"): v for k, v in d.items()}


def strip_unset(d: dict[str, Any]) -> dict[str, Any]:
    """Remove unset / default-bool / empty parameters before forwarding.

    Each clause is intentional; DO NOT collapse to ``v in (None, False, "", [])``:
    that form drops ``0`` because ``0 == False`` is True in Python.
    """
    return {k: v for k, v in d.items()
            if v is not None and v is not False and v != "" and v != []}


def render_result(result: Any) -> str:
    """Duck-typed render of ToolExecutionResult / dict / str into a string."""
    if hasattr(result, "result") and hasattr(result, "context_updates"):
        text = result.result or ""
        ctx = dict(result.context_updates or {})
    elif isinstance(result, dict):
        text = result.get("result") or result.get("text") or ""
        ctx = dict(result.get("context_updates") or {})
    else:
        return str(result)

    artifacts = [
        f"  {k}: {v}"
        for k, v in sorted(ctx.items())
        if (k.endswith("_path") or k.endswith("_dir")) and isinstance(v, str) and v
    ]
    if artifacts:
        text += "\n\nArtifacts:\n" + "\n".join(artifacts)
    return text
