"""CI preflight (I20): single-worker uvicorn for v1.

``run_server.py`` must NOT pass ``workers=N`` (N>1) to ``uvicorn.run``. The
server-as-single-writer guarantee (I9) and the FastAPI event-loop
serialisation argument both presuppose one process per
``(runtime_root, host, port)`` triple. A future operator running
``uvicorn --workers 4`` would re-introduce the ``_update_index`` race.

Multi-worker support is POST-4 (requires ``fcntl.flock`` around
``_update_index``).

AST scan: load run_server.py source, walk for ``Call(func=Attribute(attr='run'))``
on a ``Name('uvicorn')`` and assert none of them pass ``workers``.
"""
from __future__ import annotations

import ast
from pathlib import Path


def _run_server_path() -> Path:
    import openteam.server.run_server as mod
    return Path(mod.__file__)


def _is_uvicorn_run_call(node: ast.Call) -> bool:
    """Return True if ``node`` is ``uvicorn.run(...)`` or ``uvicorn.Server(...)`` etc."""
    return (
        isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "uvicorn"
    )


def test_uvicorn_run_does_not_pass_workers():
    tree = ast.parse(_run_server_path().read_text(encoding="utf-8"))
    offenders: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _is_uvicorn_run_call(node):
            for kw in node.keywords:
                if kw.arg == "workers":
                    # Try to extract the numeric literal for a friendlier message
                    val = None
                    if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, int):
                        val = kw.value.value
                    if val is None or val > 1:
                        offenders.append((node.lineno, f"workers={val if val is not None else ast.unparse(kw.value)}"))
    assert not offenders, (
        "I20 violation: run_server.py passes workers=N>1 to uvicorn. "
        "Multi-worker uvicorn breaks the server-as-single-writer guarantee "
        "(see I9). Offenders:\n"
        + "\n".join(f"  line {ln}: {desc}" for ln, desc in offenders)
    )
