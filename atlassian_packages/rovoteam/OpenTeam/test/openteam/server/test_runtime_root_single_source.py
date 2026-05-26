"""CI preflight (I21): runtime_root.py's ``apply_runtime_root`` must write to ``os.environ``.

Single source of truth: every code path that asks "what's the runtime root?"
reads ``OPENTEAM_RUNTIME_DIR`` via ``find_runtime_root``. The CLI flag
sets that env var (rather than threading a separate value through), so
this preflight pins down the implementation strategy.

AST scan: ``apply_runtime_root`` must contain ``os.environ[...] = ...`` for
the ``OPENTEAM_RUNTIME_DIR`` key. Any future refactor that stores the value
in a private module global would silently break the single-source guarantee.
"""
from __future__ import annotations

import ast
from pathlib import Path


def _module_path() -> Path:
    import openteam.server.runtime_root as mod
    return Path(mod.__file__)


def test_apply_runtime_root_writes_env_var():
    tree = ast.parse(_module_path().read_text(encoding="utf-8"))
    apply_fn = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "apply_runtime_root":
            apply_fn = node
            break
    assert apply_fn is not None, "apply_runtime_root not found"

    found_env_write = False
    for stmt in ast.walk(apply_fn):
        # Match: os.environ["OPENTEAM_RUNTIME_DIR"] = ...
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if (
                    isinstance(target, ast.Subscript)
                    and isinstance(target.value, ast.Attribute)
                    and target.value.attr == "environ"
                    and isinstance(target.slice, ast.Constant)
                    and target.slice.value == "OPENTEAM_RUNTIME_DIR"
                ):
                    found_env_write = True
                    break
    assert found_env_write, (
        "I21 violation: apply_runtime_root MUST set os.environ['OPENTEAM_RUNTIME_DIR']. "
        "If you stored the value in a private global instead, callers using "
        "find_runtime_root() will silently disagree with the CLI flag."
    )
