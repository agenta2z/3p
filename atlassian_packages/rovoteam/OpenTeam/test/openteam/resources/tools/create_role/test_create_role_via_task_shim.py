"""Phase 3 — real-LLM verification of /create_role's thin shim.

Invokes the shim directly (mirrors how ToolDispatcher would). Proves:
  - Shim's _run_topology delegation works end-to-end with opus[1m]
  - context_updates are re-keyed to original schema (role_document_path, role_document_working_dir)
  - Real role_document.md artifact is produced
  - Per-task workspace allocated under _runtime/tasks/ (R5b safety)

Persists the produced doc path to LATEST_DOC.txt for Phase 5 handoff.

Usage:
    cd OpenTeam
    python -m test.openteam.resources.tools.create_role.test_create_role_via_task_shim
"""

import asyncio
import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Bootstrap sys.path
_HERE = Path(__file__).resolve()
_OPENSTARTUP = _HERE.parents[5]
_REPO_ROOT = _OPENSTARTUP.parent
for _dep in [_OPENSTARTUP / "src",
             _REPO_ROOT / "AgentFoundation" / "src",
             _REPO_ROOT / "PythonUtils" / "src"]:
    p = str(_dep)
    if p not in sys.path:
        sys.path.insert(0, p)


def _claude_available() -> bool:
    try:
        r = subprocess.run("claude --version", shell=True,
                           capture_output=True, text=True, timeout=10)
        return r.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def _opus_1m_smoke_check():
    try:
        r = subprocess.run(
            'claude --print --model "opus[1m]" "Reply with the single word: pong"',
            shell=True, capture_output=True, text=True, timeout=60,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        return False, f"smoke check raised: {e}"
    out = (r.stdout or "").strip()
    err = (r.stderr or "").strip()
    if r.returncode != 0:
        return False, f"exit={r.returncode}, stderr={err[:300]}"
    bad = ("Execution error", "model not found", "unknown model",
           "invalid model", "Unsupported model")
    for m in bad:
        if m.lower() in out.lower() or m.lower() in err.lower():
            return False, f"got error marker {m!r}: out={out[:200]} err={err[:200]}"
    if not out:
        return False, f"empty stdout, stderr={err[:200]}"
    return True, f"opus[1m] responded ({len(out)}B): {out[:120]}"


SHIM_TEST_ROOT = _HERE.parent / "_runtime" / "shim_test"
ROLE_DESCRIPTION = "Senior Backend Engineer focused on microservices."


async def main():
    if not _claude_available():
        print("ERROR: claude CLI not available", file=sys.stderr)
        return 2

    print("[pre-flight] Checking opus[1m] availability ...", flush=True)
    ok, diag = _opus_1m_smoke_check()
    if not ok:
        print(f"ERROR: opus[1m] pre-flight failed: {diag}", file=sys.stderr)
        return 3
    print(f"[pre-flight] OK -- {diag}", flush=True)

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")

    SHIM_TEST_ROOT.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    workspace = SHIM_TEST_ROOT / ts
    workspace.mkdir()
    print(f"[workspace] {workspace}", flush=True)

    arguments = {
        "role_description": ROLE_DESCRIPTION,
        "--max-facets": 2,  # cap cost
    }
    session_context = {
        "interactive": None,
        "task_id": f"shim-cr-{ts}",
        "working_dir": str(workspace),  # safe per-task dir → _run_topology respects it
    }

    print(f"[input] role_description: {ROLE_DESCRIPTION!r}", flush=True)
    print(f"[input] max_facets: 2", flush=True)
    print(f"[input] session_context.working_dir: {workspace}", flush=True)

    from openteam.server.resources.tools.create_role.executor import execute
    print(f"\n[run] await create_role.execute(...) — opus[1m] BTA, ~$15-30", flush=True)

    try:
        result = await execute(arguments, session_context)
    except Exception:
        import traceback
        traceback.print_exc()
        print(f"\nFAIL — exception during execute(). Workspace: {workspace}",
              file=sys.stderr)
        return 1

    # Assertions
    print("\n=== ASSERTIONS ===", flush=True)
    ctx = result.context_updates or {}
    assert hasattr(result, "result"), "Result is not a ToolExecutionResult"
    print(f"  OK   result is ToolExecutionResult")
    assert ctx.get("success") is not False, f"success flag is False: {ctx}"
    print(f"  OK   context_updates.success: {ctx.get('success')}")
    # Original schema keys preserved (BC requirement)
    assert "role_document_working_dir" in ctx, f"missing role_document_working_dir: {sorted(ctx)}"
    print(f"  OK   role_document_working_dir: {ctx['role_document_working_dir']}")
    assert "role_document_path" in ctx, f"missing role_document_path: {sorted(ctx)}"
    role_doc = Path(ctx["role_document_path"])
    print(f"  OK   role_document_path: {role_doc}")
    assert role_doc.is_file(), f"role_document.md not on disk: {role_doc}"
    size = role_doc.stat().st_size
    assert size > 1000, f"role_document.md too short: {size}B"
    print(f"  OK   role_document.md size: {size}B")
    # Workspace allocated under _runtime/tasks/ (R5b safety)
    ws_posix = Path(ctx["role_document_working_dir"]).as_posix()
    assert "/_runtime/" in ws_posix or "/tasks/" in ws_posix, \
        f"workspace not under _runtime/ or tasks/: {ws_posix}"
    print(f"  OK   workspace path safe: {ws_posix}")
    # Result text is non-trivial
    assert len(str(result.result)) > 100, f"result text too short: {len(str(result.result))}B"
    print(f"  OK   result.result length: {len(str(result.result))}B")

    # Phase 3 → Phase 5 handoff (explicit marker, not glob)
    marker = SHIM_TEST_ROOT / "LATEST_DOC.txt"
    marker.write_text(str(role_doc), encoding="utf-8")
    print(f"\n[handoff] LATEST_DOC.txt → {role_doc}", flush=True)

    print(f"\n=== PHASE 3 OK ===")
    print(f"  workspace:     {workspace}")
    print(f"  role_doc:      {role_doc}")
    print(f"  doc size:      {size}B")
    print(f"  marker:        {marker}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
